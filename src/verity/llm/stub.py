"""Deterministic adapter for tests and offline development.

Scripted by `purpose`, so a test says what a stage should receive rather than matching on
prompt text that will change as prompts are tuned. Missing scripts raise instead of
returning empty output — a silently empty completion is the failure mode that makes a
broken pipeline look like a working one.

**A script may be a callable, and for a descent that is the only correct form.** Every
call a recursive decomposition makes carries the same `purpose`, so a single scripted
object answers every node with the same premises and the second level refuses as circular.
A sequence would answer them in expansion order, which makes a test's assertions depend on
the traversal's iteration order and re-assigns every proposal the first time that order
changes. A callable receives the request — whose prompt carries the conclusion being
decomposed, which is the real key — and stays correct under any traversal. Sequences are
kept for the single-call cases where "the second call behaves differently" is the point.

Response *recording* (cassettes keyed by content hash) is `verity.llm.cassette`; this is
the interface it slots behind.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from pydantic import BaseModel

from verity.llm.base import (
    LLMError,
    LLMRequest,
    LLMResponse,
    StructuredResponse,
    TSchema,
)
from verity.models.manifest import Usage

#: What a purpose may be scripted with: one answer for every call, a callable over the
#: request, or a sequence consumed in order.
type Script[T] = T | Callable[[LLMRequest], T] | Sequence[T]


class StubAdapter:
    """An `LLMAdapter` that returns pre-scripted results and records every call."""

    name = "stub"

    def __init__(
        self,
        completions: dict[str, Script[str]] | None = None,
        structured: dict[str, Script[BaseModel]] | None = None,
        model: str = "stub-model",
        stop_reason: str = "end_turn",
    ) -> None:
        self._completions = completions or {}
        self._structured = structured or {}
        self._model = model
        #: Scriptable so a caller can exercise the truncation path without a network.
        self._stop_reason = stop_reason
        self.calls: list[LLMRequest] = []
        self._consumed: dict[str, int] = {}

    def _envelope(
        self, request: LLMRequest, text: str = "", raw_output: str | None = None
    ) -> LLMResponse:
        return LLMResponse(
            text=text,
            raw_output=raw_output,
            model=self._model,
            usage=Usage(price_bases=("stub",)),
            stop_reason=self._stop_reason,
            effort=request.effort,
            thinking=request.thinking,
        )

    def _next[T](self, scripts: dict[str, Script[T]], request: LLMRequest, what: str) -> T:
        """Resolve one script to one answer, advancing a sequence if that is what it is."""
        if request.purpose not in scripts:
            raise LLMError(f"StubAdapter has no {what} scripted for {request.purpose!r}")
        script = scripts[request.purpose]
        if callable(script):
            return script(request)
        # `BaseModel` is not a Sequence and `str` is, so the model check has to come first
        # for structured scripts and the str check first for completions.
        if isinstance(script, BaseModel | str):
            return script  # type: ignore[return-value]
        if isinstance(script, Sequence):
            index = self._consumed.get(request.purpose, 0)
            if index >= len(script):
                raise LLMError(
                    f"StubAdapter's {what} sequence for {request.purpose!r} is exhausted "
                    f"after {index} call(s); script a callable if the number of calls is "
                    "not fixed"
                )
            self._consumed[request.purpose] = index + 1
            return script[index]
        return script

    def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self._envelope(request, self._next(self._completions, request, "completion"))

    def structured(
        self, request: LLMRequest, schema: type[TSchema]
    ) -> StructuredResponse[TSchema]:
        self.calls.append(request)
        result = self._next(self._structured, request, "structured result")
        if not isinstance(result, schema):
            raise LLMError(
                f"scripted result for {request.purpose!r} is {type(result).__name__}, "
                f"expected {schema.__name__}"
            )
        return StructuredResponse[schema](  # type: ignore[valid-type]
            parsed=result,
            response=self._envelope(request, raw_output=result.model_dump_json()),
        )
