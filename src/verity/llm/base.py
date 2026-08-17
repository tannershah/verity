"""Provider-agnostic LLM adapter interface.

Claim-side LLM calls (decomposition, normalization, query reformulation, restatement)
go through this interface. NLI and embedding models run locally and do not.

The interface is deliberately small: one text completion and one typed extraction. Typed
extraction is what M3 actually uses — a decomposition is a structured object, and letting
the provider enforce the schema removes a whole class of parse-and-retry code.

**Both methods return the same envelope.** A structured response that validates is not
the same as a structured response that finished: a decomposition cut off at `max_tokens`
can still parse as three premises where seven were being written, and returning only the
parsed object would make silent truncation read as a real measurement about the
decomposer. The envelope carries `stop_reason`, and the resolved `effort` and `thinking`
settings the call actually ran under, so a run manifest records what happened rather than
what was configured.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from verity.base import VerityModel
from verity.config import LLMConfig
from verity.models.manifest import LLMSettings, Usage

TSchema = TypeVar("TSchema", bound=BaseModel)

#: Efforts at which the provider accepts thinking being turned off.
_NO_THINKING_MAX_EFFORT = frozenset({"low", "medium", "high"})


class LLMError(RuntimeError):
    """Base class for adapter failures."""


class LLMRefusalError(LLMError):
    """The provider's safety classifiers declined the request.

    Distinct from a transport error: the call succeeded and returned no usable content.
    Carries the refusal category when the provider supplies one.
    """

    def __init__(self, message: str, category: str | None = None) -> None:
        super().__init__(message)
        self.category = category


class LLMRequest(VerityModel):
    """One call. Kept provider-neutral; adapters translate."""

    prompt: str
    system: str | None = None
    max_tokens: int | None = None
    model: str | None = None
    effort: str | None = None
    thinking: bool | None = None
    #: Free-form label used in run manifests and cache keys, e.g. "decompose:step".
    purpose: str = "unlabeled"


class LLMResponse(VerityModel):
    """One call's outcome, including how it ended and what it ran under."""

    text: str = ""
    #: The provider's own serialization of a structured result, when it emitted one.
    #: Deliberately not `text`: on the `complete()` path that field is free-text output a
    #: caller reads, and overloading it with a serialized schema instance would give one
    #: field two meanings in a model four tiers consume. It exists so a cassette can
    #: re-validate a recorded response *through the schema* rather than storing an object
    #: that already validated — replaying a parse that never re-ran is exactly the
    #: code-changed-underneath-a-stored-result failure the cassette exists to catch.
    raw_output: str | None = None
    model: str
    usage: Usage = Field(default_factory=Usage)
    stop_reason: str | None = None
    #: The settings actually sent, which is what a manifest should record. Configured and
    #: resolved values can differ, and only the resolved one explains the output.
    effort: str | None = None
    thinking: bool | None = None

    @property
    def truncated(self) -> bool:
        """Whether the model was cut off rather than finishing.

        A truncated structured response can still validate, so callers that treat a short
        result as a measurement have to check this first.
        """
        return self.stop_reason == "max_tokens"


class StructuredResponse[T: BaseModel](VerityModel):
    """A validated object plus the envelope of the call that produced it."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    parsed: T
    response: LLMResponse

    @property
    def usage(self) -> Usage:
        return self.response.usage

    @property
    def truncated(self) -> bool:
        return self.response.truncated


def resolve_settings(request: LLMRequest, config: LLMConfig) -> LLMSettings:
    """The settings a request will actually run under, before it is sent.

    One implementation, for two callers that must not disagree. The adapter needs them to
    build the call; the cassette needs them to build its key, and every field is `None` on
    an unmodified `LLMRequest` — a key built from the request as passed would key every
    call on nothing. Resolving twice in two files would let the cassette key on settings
    the adapter did not use, which surfaces only as a cache that hits when it should miss.

    Deriving them without a client is also what lets a fully-replayed run need no
    provider credential at all.
    """
    thinking = config.thinking if request.thinking is None else request.thinking
    effort = request.effort or config.effort
    if not thinking and effort not in _NO_THINKING_MAX_EFFORT:
        # Refused here rather than paying a round trip for a 400.
        raise LLMError(
            f"thinking cannot be disabled at effort {effort!r}; "
            f"use effort in {sorted(_NO_THINKING_MAX_EFFORT)} or leave thinking on"
        )
    return LLMSettings(
        model=request.model or config.model,
        effort=effort,
        thinking=thinking,
        max_tokens=request.max_tokens or config.max_tokens,
    )


@runtime_checkable
class LLMAdapter(Protocol):
    """What every backend must provide."""

    name: str

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Free-text completion."""
        ...

    def structured(
        self, request: LLMRequest, schema: type[TSchema]
    ) -> StructuredResponse[TSchema]:
        """Completion constrained to `schema`, with the envelope of the call."""
        ...
