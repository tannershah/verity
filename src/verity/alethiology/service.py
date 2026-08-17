"""The alethiology's read side: one object M3, M6, M9 and M10 all talk to.

Composes the store's exact-key lookup with the grounding policy in
`verity.alethiology.grounding`, and satisfies `FactLookup`, so the same object can be
handed to `to_render_payload` and asked to ground a premise.

**Write-only-through-policy.** Nothing here inserts a fact. Seeding goes through
`verity.alethiology.seed`, promotion is M5-T2, and status is M8's; a service that could
both decide grounding and create the facts it grounds against would make the two
indistinguishable in a stack trace.

**No text query exists, and the type signatures are the enforcement.** Every lookup takes
an `ExternalKey`, never a `str`, so "find me facts about spinach" cannot be expressed here
— not merely discouraged. The M5-T3 similarity index is a separate, explicitly
non-grounding layer and does not belong in this module.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from verity.alethiology.grounding import GroundingAttempt, attempt_grounding
from verity.alethiology.resolution import ResolutionArtifact
from verity.config import load_config
from verity.keys import ExternalKey
from verity.models.claim import Premise
from verity.models.fact import Fact
from verity.store.facts import facts_by_key, load_fact


class Alethiology:
    """Read access to the persistent fact store, plus the grounding decision.

    `aliases` maps a rendered key to other identifiers for the same work, and is
    diagnostic only — it is consulted after exact-key lookup has already failed, so it can
    turn a silent miss into a reported one and cannot turn a miss into a hit.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        aliases: dict[str, list[ExternalKey]] | None = None,
    ) -> None:
        self._conn = conn
        self._aliases = aliases or {}

    @classmethod
    def open(
        cls, conn: sqlite3.Connection, *, resolution_path: Path | str | None = None
    ) -> Alethiology:
        """The construction path callers should use: aliases wired in by default.

        `__init__` defaults `aliases` to empty, which means a service built directly can
        never report `ALIAS_ONLY` — the reason code exists to make an invisible deflation
        visible, and a default that silently disables it is worse than not having it. The
        alias map is derived from the committed resolution artifact; when that file is
        absent the service still works and simply has no synonyms to report.
        """
        path = Path(resolution_path or load_config().paths.key_resolution)
        aliases = ResolutionArtifact.load(path).alias_index() if path.exists() else {}
        return cls(conn, aliases=aliases)

    # -- FactLookup ----------------------------------------------------------------

    def get(self, fact_id: str) -> Fact | None:
        return load_fact(self._conn, fact_id)

    # -- exact-key access ----------------------------------------------------------

    def facts_for(self, key: ExternalKey) -> list[Fact]:
        """Every fact stored under `key`, eligible or not. The only lookup path."""
        return facts_by_key(self._conn, key)

    def aliases_of(self, key: ExternalKey) -> list[ExternalKey]:
        """Known identifiers for the same work. Never a grounding path — see `ground`."""
        return list(self._aliases.get(str(key), ()))

    def aliases_holding_facts(self, key: ExternalKey) -> list[ExternalKey]:
        """Aliases of `key` that hold at least one fact — the reportable near-miss."""
        return [alias for alias in self.aliases_of(key) if self.facts_for(alias)]

    # -- grounding -----------------------------------------------------------------

    def ground(
        self, premise: Premise, *, grounded_at: datetime | None = None
    ) -> GroundingAttempt:
        """Attempt to ground `premise`, returning the outcome and its reason."""
        if premise.bound_key is None:
            return attempt_grounding(premise, (), grounded_at=grounded_at)
        candidates = self.facts_for(premise.bound_key)
        aliases = () if candidates else self.aliases_holding_facts(premise.bound_key)
        return attempt_grounding(
            premise, candidates, alias_keys=aliases, grounded_at=grounded_at
        )

    def ground_all(
        self, premises: Iterable[Premise], *, grounded_at: datetime | None = None
    ) -> list[GroundingAttempt]:
        """One attempt per premise, in the order given.

        M10-T1 counts off these rows, so the *caller* owns the denominator: `apply_groundings`
        passes the leaves, because the pre-registered rate is over branches that terminated
        (evaluation.md §2) and a decomposed premise terminated nothing.
        """
        return [self.ground(premise, grounded_at=grounded_at) for premise in premises]
