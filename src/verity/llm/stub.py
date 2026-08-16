"""Deterministic adapter for tests and offline development.

Scripted by `purpose`, so a test says what a stage should receive rather than matching on
prompt text that will change as prompts are tuned. Missing scripts raise instead of
returning empty output — a silently empty completion is the failure mode that makes a
broken pipeline look like a working one.

Response *recording* (cassettes keyed by content hash) belongs to M1-T2's caching layer;
this is the interface it will slot behind.
"""

from __future__ import annotations

from pydantic import BaseModel

from verity.llm.base import (
    LLMError,
    LLMRequest,
    LLMResponse,
    StructuredResponse,
    TSchema,
)
from verity.models.manifest import Usage


class StubAdapter:
    """An `LLMAdapter` that returns pre-scripted results and records every call."""

    name = "stub"

    def __init__(
        self,
        completions: dict[str, str] | None = None,
        structured: dict[str, BaseModel] | None = None,
        model: str = "stub-model",
        stop_reason: str = "end_turn",
    ) -> None:
        self._completions = completions or {}
        self._structured = structured or {}
        self._model = model
        #: Scriptable so a caller can exercise the truncation path without a network.
        self._stop_reason = stop_reason
        self.calls: list[LLMRequest] = []

    def _envelope(self, request: LLMRequest, text: str = "") -> LLMResponse:
        return LLMResponse(
            text=text,
            model=self._model,
            usage=Usage(price_bases=("stub",)),
            stop_reason=self._stop_reason,
            effort=request.effort,
            thinking=request.thinking,
        )

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        if request.purpose not in self._completions:
            raise LLMError(f"StubAdapter has no completion scripted for {request.purpose!r}")
        return self._envelope(request, self._completions[request.purpose])

    def structured(
        self, request: LLMRequest, schema: type[TSchema]
    ) -> StructuredResponse[TSchema]:
        self.calls.append(request)
        if request.purpose not in self._structured:
            raise LLMError(f"StubAdapter has no structured result for {request.purpose!r}")
        result = self._structured[request.purpose]
        if not isinstance(result, schema):
            raise LLMError(
                f"scripted result for {request.purpose!r} is {type(result).__name__}, "
                f"expected {schema.__name__}"
            )
        return StructuredResponse[schema](  # type: ignore[valid-type]
            parsed=result, response=self._envelope(request)
        )
