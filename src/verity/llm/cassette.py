"""Recorded provider answers, so replay re-runs our code instead of trusting our output.

This is the lower of M1-T2's two cache layers, and the division between them is the point.
The stage cache stores what a stage *concluded*; a hit skips the code entirely. A cassette
stores what the *provider said*, and a hit re-executes every line downstream of the call —
materialization, dedup, the cyclic-premise refusal, id derivation, graph assembly. So a
replay that reproduces a graph has re-derived it, and a replay that does not reports drift
rather than hiding it.

That division is also what makes the stage cache affordable to key on the whole source
tree: the conservative choice re-runs deterministic code against a recorded answer, and
costs nothing.

**The recording is re-validated, not restored.** A structured call stores the provider's
own JSON and passes it back through the schema on replay, so the schema's validators run
again. Where the provider returned no text blocks the entry stores a re-serialization of
the parsed object instead and says so in `raw_form` — a weaker claim, kept distinguishable
from the stronger one rather than collapsed into it.

**A refusal is recorded too.** `AnthropicAdapter._guard_refusal` raises before an envelope
exists, so without this a run that was declined would re-call the provider on every replay
— the same reason `HttpCache` keeps a negative namespace for a 404.

**The key is the resolved settings, not the request.** `LLMRequest.model`, `effort`,
`thinking` and `max_tokens` are all `None` on an unmodified request and are filled from
`LLMConfig`; keying on the request as passed would key every call on nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from verity.base import VerityModel
from verity.cache import BlobCache
from verity.config import LLMConfig
from verity.ids import content_hash
from verity.llm.base import (
    LLMAdapter,
    LLMError,
    LLMRefusalError,
    LLMRequest,
    LLMResponse,
    StructuredResponse,
    TSchema,
    resolve_settings,
)
from verity.models.common import utc_now
from verity.models.manifest import LLMSettings, Usage

#: Cache namespace. Separate from the stage cache's so one can be cleared without the other.
NAMESPACE = "llm"


class CassetteMode(StrEnum):
    """Where a provider answer may come from.

    Recorded per run rather than configured, for the reason `CacheMode` gives: a graph
    built from replayed answers is a different epistemic object from one built live, and a
    demo writeup has to be able to say which it is.
    """

    #: Read the cassette, call the provider on a miss, record what comes back.
    LIVE = "live"
    #: Read only. A miss raises rather than reaching the provider.
    REPLAY = "replay"


class CassetteMiss(LLMError):
    """Replay mode has no recording for a call it was asked to make."""


class CassetteEntry(VerityModel):
    """One recorded call. Everything needed to reproduce its outcome and nothing more."""

    kind: Literal["complete", "structured", "refusal"]
    purpose: str
    settings: LLMSettings
    response: LLMResponse | None = None
    schema_name: str | None = None
    #: `provider` = the model's own serialization, re-validated through the schema on
    #: replay. `dump` = a re-serialization of an object that had already validated, which
    #: is a recording of our parse rather than of the provider's answer.
    raw_form: Literal["provider", "dump"] | None = None
    refusal_message: str | None = None
    refusal_category: str | None = None
    recorded_at: datetime = Field(default_factory=utc_now)


class CassetteCall(VerityModel):
    """What one call through the cassette cost, and whether it was paid for."""

    key: str
    purpose: str
    hit: bool
    usage: Usage = Field(default_factory=Usage)
    truncated: bool = False


class CassetteUsage(VerityModel):
    """What a span of calls cost this run, and what its replayed ones cost before.

    A cache hit costs nothing, so `spent` excludes it — a total that added both would
    report money this run did not pay. `replayed` is kept beside it rather than discarded,
    because "served from cache; the recorded run cost $X" is what makes a free run legible.
    """

    spent: Usage = Field(default_factory=Usage)
    replayed: Usage = Field(default_factory=Usage)
    #: Calls that reached the provider. A replayed one is a `hit`, never one of these.
    provider_calls: int = 0
    hits: int = 0
    truncated: int = 0


class CassetteAdapter:
    """An `LLMAdapter` that records provider answers and replays them.

    `inner` is a factory rather than an adapter so a fully-replayed run never constructs a
    provider client — which is what lets the recorded demo run from a clean checkout with
    no API key.
    """

    name = "cassette"

    def __init__(
        self,
        inner: Callable[[], LLMAdapter] | None,
        *,
        config: LLMConfig,
        cache: BlobCache,
        mode: CassetteMode = CassetteMode.LIVE,
    ) -> None:
        self._factory = inner
        self._inner: LLMAdapter | None = None
        self._config = config
        self._cache = cache
        self.mode = mode
        self.calls: list[CassetteCall] = []

    # -- accounting ------------------------------------------------------------------

    def usage_since(self, first_call: int = 0) -> CassetteUsage:
        """What the calls from `first_call` onward cost. The only accounting entry point.

        Deliberately span-based rather than a set of cumulative properties. Cumulative
        totals read correctly while exactly one stage calls a provider and silently
        misattribute the moment a second does — every such stage would report the run's
        running total as its own, and `RunManifest.total_usage`, which sums the stages,
        would multiply it. A caller that must pass a starting point cannot make that
        mistake by omission.
        """
        usage = CassetteUsage()
        for call in self.calls[first_call:]:
            if call.hit:
                usage.replayed = usage.replayed + call.usage
                usage.hits += 1
            else:
                usage.spent = usage.spent + call.usage
                usage.provider_calls += 1
            usage.truncated += int(call.truncated)
        return usage

    # -- internals -------------------------------------------------------------------

    def _adapter(self) -> LLMAdapter:
        if self._inner is None:
            if self._factory is None:
                raise CassetteMiss(
                    "this cassette has no provider behind it, so a miss cannot be filled; "
                    "record the call first, or pass an adapter factory"
                )
            self._inner = self._factory()
        return self._inner

    def _key(
        self, request: LLMRequest, kind: str, schema: type[BaseModel] | None
    ) -> tuple[str, LLMSettings]:
        settings = resolve_settings(request, self._config)
        schema_digest = (
            content_hash(schema.__name__, schema.model_json_schema()) if schema else None
        )
        key = content_hash(
            kind,
            request.purpose,
            settings,
            request.system,
            request.prompt,
            schema_digest,
        )
        return key, settings

    def _read(self, key: str) -> CassetteEntry | None:
        entry = self._cache.get(NAMESPACE, key, CassetteEntry)
        return entry  # type: ignore[return-value]

    def _record(
        self, key: str, purpose: str, hit: bool, response: LLMResponse | None
    ) -> None:
        self.calls.append(
            CassetteCall(
                key=key,
                purpose=purpose,
                hit=hit,
                usage=response.usage if response else Usage(),
                truncated=bool(response and response.truncated),
            )
        )

    def _miss(self, request: LLMRequest, key: str) -> None:
        if self.mode is CassetteMode.REPLAY:
            raise CassetteMiss(
                f"no recording for {request.purpose!r} (key {key[:12]}…); replay mode does "
                "not reach the provider. Record the call first rather than letting a "
                "replay quietly become a live run."
            )

    def _replay_refusal(self, entry: CassetteEntry, key: str, purpose: str) -> None:
        self._record(key, purpose, hit=True, response=None)
        raise LLMRefusalError(
            entry.refusal_message or "provider declined the request (replayed)",
            category=entry.refusal_category,
        )

    # -- interface -------------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        key, settings = self._key(request, "complete", None)
        entry = self._read(key)
        if entry is not None:
            if entry.kind == "refusal":
                self._replay_refusal(entry, key, request.purpose)
            if entry.response is not None:
                self._record(key, request.purpose, hit=True, response=entry.response)
                return entry.response
        self._miss(request, key)

        try:
            response = self._adapter().complete(request)
        except LLMRefusalError as refusal:
            self._write_refusal(key, request, settings, refusal)
            self._record(key, request.purpose, hit=False, response=None)
            raise
        self._cache.put(
            NAMESPACE,
            key,
            CassetteEntry(
                kind="complete",
                purpose=request.purpose,
                settings=settings,
                response=response,
            ),
        )
        self._record(key, request.purpose, hit=False, response=response)
        return response

    def structured(
        self, request: LLMRequest, schema: type[TSchema]
    ) -> StructuredResponse[TSchema]:
        key, settings = self._key(request, "structured", schema)
        entry = self._read(key)
        if entry is not None:
            if entry.kind == "refusal":
                self._replay_refusal(entry, key, request.purpose)
            replayed = self._rebuild(entry, schema)
            if replayed is not None:
                self._record(key, request.purpose, hit=True, response=replayed.response)
                return replayed
        self._miss(request, key)

        try:
            result = self._adapter().structured(request, schema)
        except LLMRefusalError as refusal:
            self._write_refusal(key, request, settings, refusal)
            self._record(key, request.purpose, hit=False, response=None)
            raise
        raw = result.response.raw_output
        stored = result.response
        if raw is None:
            # No provider text to record, so what goes to disk is a re-serialization of an
            # object that already validated. Labelled `dump` so a replay through it cannot
            # be mistaken for a replay through the provider's own bytes.
            stored = result.response.model_copy(
                update={"raw_output": result.parsed.model_dump_json()}
            )
        self._cache.put(
            NAMESPACE,
            key,
            CassetteEntry(
                kind="structured",
                purpose=request.purpose,
                settings=settings,
                response=stored,
                schema_name=schema.__name__,
                raw_form="provider" if raw is not None else "dump",
            ),
        )
        self._record(key, request.purpose, hit=False, response=result.response)
        return result

    # -- replay ----------------------------------------------------------------------

    def _rebuild(
        self, entry: CassetteEntry, schema: type[TSchema]
    ) -> StructuredResponse[TSchema] | None:
        """Re-validate a recording through the schema, or treat it as absent.

        A schema that has since gained a required field, or been renamed, makes the entry
        undeserializable — which has to read as a miss rather than as a call nobody can
        reproduce. The name is checked as well as the parse, because two schemas can be
        structurally compatible and mean different things.
        """
        if entry.response is None or entry.response.raw_output is None:
            return None
        if entry.schema_name is not None and entry.schema_name != schema.__name__:
            return None
        try:
            parsed = schema.model_validate_json(entry.response.raw_output)
        except ValueError:
            return None
        return StructuredResponse[schema](  # type: ignore[valid-type]
            parsed=parsed, response=entry.response
        )

    def _write_refusal(
        self,
        key: str,
        request: LLMRequest,
        settings: LLMSettings,
        refusal: LLMRefusalError,
    ) -> None:
        self._cache.put(
            NAMESPACE,
            key,
            CassetteEntry(
                kind="refusal",
                purpose=request.purpose,
                settings=settings,
                refusal_message=str(refusal),
                refusal_category=refusal.category,
            ),
        )
