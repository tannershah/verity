"""LLM adapter contract, exercised without network access."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from verity.config import LLMConfig
from verity.llm import LLMAdapter, LLMError, LLMRequest, StubAdapter
from verity.llm.anthropic_adapter import AnthropicAdapter
from verity.llm.pricing import PRICE_BASIS, cost_usd


class PremiseSet(BaseModel):
    """Stand-in for the structured output M3-T1 will ask for."""

    premises: list[str]


def test_stub_satisfies_the_adapter_protocol():
    assert isinstance(StubAdapter(), LLMAdapter)
    assert isinstance(AnthropicAdapter.__new__(AnthropicAdapter), LLMAdapter)


def test_stub_returns_scripted_completion_and_records_calls():
    stub = StubAdapter(completions={"decompose:step": "premise one\npremise two"})
    request = LLMRequest(prompt="claim text", purpose="decompose:step")

    response = stub.complete(request)

    assert response.text.startswith("premise one")
    assert [call.purpose for call in stub.calls] == ["decompose:step"]


def test_stub_returns_validated_structured_output():
    expected = PremiseSet(premises=["a", "b", "c"])
    stub = StubAdapter(structured={"decompose:step": expected})

    result = stub.structured(LLMRequest(prompt="claim", purpose="decompose:step"), PremiseSet)

    assert result.parsed == expected
    assert result.usage.price_basis == "stub"
    assert not result.truncated


def test_missing_script_raises_rather_than_returning_empty():
    """A silently empty completion makes a broken pipeline look like a working one."""
    stub = StubAdapter()
    with pytest.raises(LLMError):
        stub.complete(LLMRequest(prompt="x", purpose="unscripted"))
    with pytest.raises(LLMError):
        stub.structured(LLMRequest(prompt="x", purpose="unscripted"), PremiseSet)


def test_schema_mismatch_is_caught():
    stub = StubAdapter(structured={"p": PremiseSet(premises=[])})

    class Other(BaseModel):
        value: int

    with pytest.raises(LLMError):
        stub.structured(LLMRequest(prompt="x", purpose="p"), Other)


def test_disabled_thinking_above_high_effort_is_refused_locally():
    """Claude Opus 5 rejects that combination; catch it before spending a round trip."""
    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    adapter.config = LLMConfig(thinking=False, effort="max")

    with pytest.raises(LLMError, match="thinking cannot be disabled"):
        adapter._resolve(LLMRequest(prompt="x"))

    adapter.config = LLMConfig(thinking=False, effort="high")
    model, _, effort, thinking = adapter._resolve(LLMRequest(prompt="x"))
    assert (model, effort, thinking) == ("claude-opus-5", "high", False)


def test_cost_accounting_is_recomputable():
    """Token counts and the price basis are stored, so a stale table is fixable."""
    cost = cost_usd("claude-opus-5", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == pytest.approx(30.0)
    assert cost_usd("some-unknown-model", 100, 100) is None
    assert PRICE_BASIS


def test_a_truncated_structured_response_is_distinguishable_from_a_complete_one():
    """A decomposition cut off at `max_tokens` can still validate — three premises where
    seven were being written — so a caller that reads only the parsed object would take
    silent truncation for a real measurement about the decomposer. M3-T1 is that caller.
    """
    expected = PremiseSet(premises=["a", "b", "c"])
    request = LLMRequest(prompt="claim", purpose="decompose:step")

    complete = StubAdapter(structured={"decompose:step": expected})
    cut_off = StubAdapter(structured={"decompose:step": expected}, stop_reason="max_tokens")

    assert not complete.structured(request, PremiseSet).truncated
    assert cut_off.structured(request, PremiseSet).truncated
    assert cut_off.structured(request, PremiseSet).parsed == expected, (
        "the parsed object alone cannot tell the two apart — which is the point"
    )


class _FakeMessages:
    """Records the request the adapter builds, so the wire shape is what gets asserted."""

    def __init__(self, response: object) -> None:
        self.response = response
        self.kwargs: dict = {}

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response

    def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


class _FakeClient:
    def __init__(self, response: object) -> None:
        self.messages = _FakeMessages(response)


class _FakeResponse:
    stop_reason = "end_turn"
    model = "claude-opus-5"
    usage = None
    content: list = []

    def __init__(self, parsed: BaseModel | None = None) -> None:
        self.parsed_output = parsed


def _adapter(response: object, **config) -> tuple[AnthropicAdapter, _FakeClient]:
    client = _FakeClient(response)
    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    adapter.config = LLMConfig(**config)
    adapter._client = client
    return adapter, client


def test_effort_reaches_the_structured_path():
    """`messages.parse` builds `output_config.format` from the schema and merges it into
    whatever else is passed. Omitting effort here would run the most consequential call in
    the system at the API default while `config_hash()` recorded the configured value —
    a run whose manifest describes something that did not happen.
    """
    adapter, client = _adapter(_FakeResponse(PremiseSet(premises=["a"])), effort="max")

    result = adapter.structured(
        LLMRequest(prompt="claim", purpose="decompose:step"), PremiseSet
    )

    assert client.messages.kwargs["output_config"] == {"effort": "max"}
    assert client.messages.kwargs["thinking"] == {"type": "adaptive"}
    assert result.response.effort == "max"
    assert result.response.thinking is True


def test_both_methods_report_the_settings_they_actually_ran_under():
    """A manifest records what happened, not what was configured — a per-request override
    has to be visible in the response."""
    adapter, _ = _adapter(_FakeResponse(), effort="high")
    response = adapter.complete(LLMRequest(prompt="x", purpose="p", effort="low"))
    assert (response.effort, response.thinking) == ("low", True)


def test_a_structured_response_that_does_not_validate_is_an_error_not_an_empty_object():
    adapter, _ = _adapter(_FakeResponse(parsed=None))
    with pytest.raises(LLMError, match="did not validate"):
        adapter.structured(LLMRequest(prompt="x", purpose="p"), PremiseSet)
