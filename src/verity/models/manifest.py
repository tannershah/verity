"""Run manifest: per-stage timing, cost, and every bound that was applied.

Two things this exists for beyond bookkeeping:

- `caps` is the structural home for evaluation.md §6's "no silent caps" rule. If a run
  bounded coverage, the manifest says what was dropped.
- `config` is a redacted snapshot. Secrets never enter this object — the manifest records
  *which* credentials were configured, never their values, and
  `tests/test_secrets_redaction.py` scans serialized output for the real values.

M1-T2 replays a run from its manifest, so anything replay needs belongs here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from verity.base import FrozenModel, VerityModel
from verity.models.common import CapRecord, utc_now


class Usage(VerityModel):
    """Token and cost accounting for LLM calls.

    Pricing tables are recorded as a *set*, not a single label. A total summed across two
    tables belongs to neither, and labelling it with whichever call came first is the one
    outcome the field exists to prevent — a stale price has to be recomputable from the
    token counts, which needs to know that more than one table was involved.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    cost_usd: float = 0.0
    #: Pricing table versions this total was computed against, sorted and deduplicated.
    price_bases: tuple[str, ...] = ()

    @property
    def price_basis(self) -> str | None:
        """The single pricing table this total rests on, or None if it spans several."""
        return self.price_bases[0] if len(self.price_bases) == 1 else None

    @property
    def has_mixed_price_basis(self) -> bool:
        return len(self.price_bases) > 1

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
            price_bases=tuple(sorted(set(self.price_bases) | set(other.price_bases))),
        )


class LLMSettings(FrozenModel):
    """The settings a stage's calls actually ran under, not the ones configured.

    A per-request override, a model fallback, or an effort that never reached the wire
    all make these differ from the config snapshot — and only these explain the output.
    """

    model: str
    effort: str | None = None
    thinking: bool | None = None
    max_tokens: int | None = None


class StageRecord(VerityModel):
    """One pipeline stage's execution record.

    M1-T2's exit criterion is that "re-running an unchanged claim is a cache hit
    end-to-end", over stages described as "composable steps with content-hash caching".
    Verifying that needs the stage to say *what was hashed*: `input_hash` is the content
    the key was built from, `cache_key` is the key itself, and `output_hash` is what came
    back — so a replay can be checked for having reproduced a run rather than merely
    re-executed it.
    """

    name: str
    started_at: datetime
    duration_ms: float
    status: Literal["ok", "error", "skipped", "cache-hit"] = "ok"
    llm_calls: int = 0
    usage: Usage = Field(default_factory=Usage)
    cache_hits: int = 0
    caps: list[CapRecord] = Field(default_factory=list)
    error: str | None = None

    #: Digest of the stage's inputs, and the key derived from it together with the config
    #: hash. Both recorded because a key that cannot be rebuilt cannot be checked.
    input_hash: str | None = None
    cache_key: str | None = None
    output_hash: str | None = None
    llm_settings: LLMSettings | None = None
    #: Calls that stopped on `max_tokens`. A truncated response can still validate, so a
    #: silent truncation would otherwise read as a real measurement about the producer.
    truncated_calls: int = 0


class RunManifest(VerityModel):
    """Everything needed to understand — and replay — one run."""

    run_id: str
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    code_version: str | None = None  # git sha
    code_dirty: bool | None = None
    #: Redacted config snapshot. See `verity.config.VerityConfig.snapshot()`.
    config: dict[str, Any] = Field(default_factory=dict)
    #: Which credentials were present, as booleans. Never the values.
    credentials_configured: dict[str, bool] = Field(default_factory=dict)
    stages: list[StageRecord] = Field(default_factory=list)
    graph_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def total_usage(self) -> Usage:
        total = Usage()
        for stage in self.stages:
            total = total + stage.usage
        return total

    @property
    def caps_applied(self) -> list[CapRecord]:
        """Every bound that actually bit during this run."""
        return [cap for stage in self.stages for cap in stage.caps if cap.applied]
