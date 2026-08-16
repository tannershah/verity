"""What a load did, row by row. Deterministic: no field is a wall-clock reading."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Literal

from pydantic import Field

from verity.base import VerityModel
from verity.keys import ExternalKey
from verity.models.common import ConfidenceTier


class SeedRowOutcome(VerityModel):
    """What happened to one row. Every cap and mismatch is named, never aggregated away."""

    slug: str
    claim_scope: str
    fact_id: str
    key: ExternalKey
    action: Literal["inserted", "updated", "unchanged", "assessed"]
    requested_tier: ConfidenceTier
    effective_tier: ConfidenceTier
    capped: bool
    grounding_eligible: bool
    identity_confirmed_by: list[str] = Field(default_factory=list)
    identity_matched_titles: list[str] = Field(default_factory=list)
    identity_mismatch: bool = False
    registry_identity_conflict: bool = False
    quote_source: str | None = None
    quote_field: str | None = None
    notes: list[str] = Field(default_factory=list)


class SeedLoadReport(VerityModel):
    """The load, in full. Deterministic: no field is a wall-clock reading."""

    seed_path: str
    seed_digest: str
    resolution_generated_at: datetime
    applied: bool
    rows: list[SeedRowOutcome] = Field(default_factory=list)

    @property
    def by_action(self) -> dict[str, int]:
        return dict(sorted(Counter(row.action for row in self.rows).items()))

    @property
    def by_tier(self) -> dict[str, int]:
        return dict(sorted(Counter(row.effective_tier.value for row in self.rows).items()))

    @property
    def by_scope(self) -> dict[str, int]:
        return dict(sorted(Counter(row.claim_scope for row in self.rows).items()))

    @property
    def by_key_type(self) -> dict[str, int]:
        return dict(sorted(Counter(row.key.type.value for row in self.rows).items()))

    @property
    def grounding_eligible(self) -> int:
        return sum(1 for row in self.rows if row.grounding_eligible)

    @property
    def capped(self) -> list[SeedRowOutcome]:
        return [row for row in self.rows if row.capped]

    @property
    def identity_mismatches(self) -> list[SeedRowOutcome]:
        """Rows where no source, or no registry, identifies the key as the named work."""
        return [
            row for row in self.rows if row.identity_mismatch or row.registry_identity_conflict
        ]

    def render(self) -> str:
        """A text summary. Counts are reported, never targeted (evaluation.md §6)."""
        lines = [
            f"seed:            {self.seed_path} ({self.seed_digest[:12]})",
            f"resolution:      recorded {self.resolution_generated_at.isoformat()}",
            f"mode:            {'applied' if self.applied else 'dry run (nothing written)'}",
            f"rows:            {len(self.rows)}",
            f"  by action:     {self.by_action}",
            f"  by scope:      {self.by_scope}",
            f"  by key type:   {self.by_key_type}",
            f"  by tier:       {self.by_tier}",
            f"grounding-eligible facts: {self.grounding_eligible}",
        ]
        if self.capped:
            lines.append(f"tier-capped rows ({len(self.capped)}):")
            lines += [f"  - {row.slug}: {'; '.join(row.notes)}" for row in self.capped]
        if self.identity_mismatches:
            lines.append(f"work-identity mismatches ({len(self.identity_mismatches)}):")
            lines += [f"  - {row.slug} ({row.key})" for row in self.identity_mismatches]
        return "\n".join(lines)
