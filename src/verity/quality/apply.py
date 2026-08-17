"""Writing assessments onto stored facts. The third piece, and the only writer.

`retraction.py` decides, `service.py` reads the sources, and this puts what they concluded
into the alethiology — where `to_render_payload` already looks for it. No render code
changes for this tier: a premise's flags are gathered from every fact under its bound key,
which is a rule `models/render.py` states and this tier satisfies.

**A fact's quality is replaced, never merged across runs.** Preserving a check the current
pass did not make would let a status be computed from two runs at once — an OpenAlex reading
from a machine with the bulk table beside a Crossref reading from a machine without it — and
the timestamp rule below is exactly what would make that invisible. So a source not consulted
this run loses its check, and the reason is reported. The one thing carried forward is time:

- consulted, same finding as stored → keep the stored `checked_at`
- consulted, different finding → replace, stamped with this reading's time
- not consulted → dropped

**A re-confirmed check keeps its time** for the reason `apply_groundings` keeps
`grounded_at`: re-reading and reaching the same conclusion concludes nothing new, and the
Retraction Watch table has no per-row date, so its reading is stamped at read time and would
otherwise rewrite every fact payload on every invocation. The cost — that a re-confirmation
is not itself dated — is paid where it can be seen: the report says how many checks were
confirmed unchanged, so a run that verified the whole store is visible even when the store
does not move.

**Nothing here propagates.** A retracted fact keeps its `TmsStatus` and its tier. Flipping a
fact `OUT` is M8-T2's, over a JTMS that does not exist yet — and `Justification` still models
Doyle's IN-list only, so a status recomputation would restore a demoted fact to IN forever.
`revalidated_at` is left alone too: it is M5-T3's record of a *full* re-validation, and a
retraction pass re-reads one dimension. Each check carries its own `checked_at`, which is the
honest record of what was actually re-read.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from pydantic import Field

from verity.base import VerityModel
from verity.keys import ExternalKey
from verity.models.common import RetractionSource, RetractionStatus
from verity.models.evidence import RetractionCheck
from verity.models.fact import Fact
from verity.quality.retraction import PARTIAL_BASIS, RetractionAssessment, basis_lines
from verity.quality.service import assess_keys
from verity.retrieval.http import HttpClient
from verity.store.facts import facts_by_key, save_facts


class FactOutcome(VerityModel):
    """What happened to one fact."""

    fact_id: str
    key: ExternalKey
    statement: str
    status: RetractionStatus
    #: `written` when the stored quality moved, `unchanged` when this pass re-confirmed it.
    disposition: str


class ApplyReport(VerityModel):
    """Every assessment made and every fact touched, plus the label they travel under."""

    assessments: list[RetractionAssessment] = Field(default_factory=list)
    outcomes: list[FactOutcome] = Field(default_factory=list)
    applied: bool = True
    is_partial: bool = True
    basis: str = PARTIAL_BASIS

    @property
    def counts(self) -> dict[str, int]:
        """Facts per status, plus how many rows the store actually took."""
        counts = {status.value: 0 for status in RetractionStatus}
        for outcome in self.outcomes:
            counts[outcome.status.value] += 1
        counts["written"] = sum(1 for o in self.outcomes if o.disposition == "written")
        counts["unchanged"] = sum(1 for o in self.outcomes if o.disposition == "unchanged")
        return counts

    @property
    def flagged(self) -> list[FactOutcome]:
        """Facts this pass marked retracted or flagged — what the demo is looking for."""
        return [
            outcome
            for outcome in self.outcomes
            if outcome.status
            in (RetractionStatus.RETRACTED, RetractionStatus.FLAGGED_UNCONFIRMED)
        ]

    def render(self) -> str:
        lines = ["retraction check (labelled partial of M7-T1)", ""]
        for assessment in self.assessments:
            lines.extend(assessment.render())
        lines += ["", "  " + ", ".join(f"{k}: {v}" for k, v in self.counts.items() if v)]
        if not self.applied:
            lines.append("  nothing written (--check)")
        for outcome in self.flagged:
            lines.append(f"  flagged  {outcome.key}  {outcome.statement[:70]}")
        lines += ["", *basis_lines()]
        return "\n".join(lines)


def _dated(
    assessment: RetractionAssessment, stored: Fact
) -> dict[RetractionSource, RetractionCheck]:
    """This pass's checks, each keeping its stored time where it re-confirmed a finding."""
    previous = stored.evidence_quality.retraction_checks
    dated: dict[RetractionSource, RetractionCheck] = {}
    for source, check in assessment.checks.items():
        before = previous.get(source)
        if before is not None and before.result is check.result:
            dated[source] = check.model_copy(update={"checked_at": before.checked_at})
        else:
            dated[source] = check
    return dated


def apply_retractions(
    conn: sqlite3.Connection,
    client: HttpClient,
    keys: Iterable[ExternalKey],
    *,
    apply: bool = True,
) -> ApplyReport:
    """Assess every key, write what changed, and report all of it.

    Assesses each key once and writes it to every fact stored under it — the chocolate DOI
    carries five — because retraction is a property of the work, not of any one attribution
    a curator wrote about it.

    The write is one transaction, matching `load_seed`: a pass that decided the whole batch
    lands whole or not at all.
    """
    wanted = sorted(set(keys), key=str)
    assessments = assess_keys(client, wanted, table=None)

    outcomes: list[FactOutcome] = []
    to_write: list[Fact] = []
    for key in wanted:
        assessment = assessments[str(key)]
        for stored in facts_by_key(conn, key):
            quality = assessment.as_evidence_quality(stored.evidence_quality).model_copy(
                update={"retraction_checks": _dated(assessment, stored)}
            )
            updated = stored.model_copy(update={"evidence_quality": quality})
            changed = updated.evidence_quality != stored.evidence_quality
            if changed and apply:
                to_write.append(updated)
            outcomes.append(
                FactOutcome(
                    fact_id=stored.id,
                    key=stored.key,
                    statement=stored.statement,
                    status=assessment.status,
                    disposition="written" if changed else "unchanged",
                )
            )

    if to_write:
        save_facts(conn, to_write)
    return ApplyReport(
        assessments=[assessments[str(key)] for key in wanted],
        outcomes=outcomes,
        applied=apply,
    )


def stored_keys(conn: sqlite3.Connection) -> list[ExternalKey]:
    """Every distinct identifier the alethiology holds a fact under.

    Read off the store rather than the seed file: a fact promoted by M5-T2 from retrieval
    would never appear in the seed, and a retraction layer that only checked curated keys
    would go quiet exactly as the KB started growing.
    """
    rows = conn.execute(
        "SELECT DISTINCT key_type, key_value FROM facts ORDER BY key_type, key_value"
    ).fetchall()
    return [ExternalKey(type=row["key_type"], value=row["key_value"]) for row in rows]
