"""The cut: three sources' readings to one retraction status. Pure, and the only decider.

**Reads `WorkRecord`s, never `key_resolution.json`.** That artifact is a curation record for
the seed gate and stores `found` as a boolean, which cannot hold `NOT_INDEXED` apart from
`CLEAN` — the distinction the whole policy turns on. Nothing persists a `WorkRecord`, so the
cut runs against live or replayed client output and is recomputed rather than loaded.

**The verdict is asymmetric on purpose** (build-plan.md M7-T1). `retracted` needs the
Retraction Watch table or both APIs; `clean` needs one source that answered and found
nothing. The costs are not symmetric: a missed retraction is the failure this module exists
to prevent, while a false flag is bounded by the ≤5% threshold M10-T4b measures.

**A source that could not answer contributes no check**, rather than a check saying it had
no opinion. `retraction_checks` then means exactly "sources that answered", which is what
`checked_sources` and `asserting_sources` already assume, and the reason it could not travels
on the assessment where a reader sees it.

**Absence means different things to different sources, and that is not a subtlety to smooth
over.** Retraction Watch indexes retractions, so a work absent from the bulk table is
evidence the work stands — `CLEAN`, and the strongest clean signal available. OpenAlex and
Crossref index *works*, so a 404 there is a work they have never heard of, which is
`NOT_INDEXED` and no opinion at all. Reading either as the other breaks the cut in a
direction nothing would report: RW absence as `NOT_INDEXED` makes `clean` unreachable and
M5-T2's promotion gate unsatisfiable, registry absence as `CLEAN` lets an unindexed DOI
outvote a source that found a retraction.
"""

from __future__ import annotations

import textwrap
from datetime import datetime

from pydantic import Field

from verity.base import FrozenModel
from verity.keys import ExternalKey
from verity.models.common import (
    NOT_RETRACTED_FINDINGS,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
)
from verity.models.evidence import EvidenceQuality, RetractionCheck
from verity.retrieval import crossref, openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.record import ReadingOutcome, WorkRecord

#: What a status produced here does and does not mean. Carried on every assessment as data,
#: the way `binder.PARTIAL_BASIS` is, so copy that forgets the label cannot drop it.
PARTIAL_BASIS = (
    "Labelled partial of M7-T1. The three-source cut is complete and is applied to "
    "alethiology facts; what is not built is the rest of the tier. No evidence item is "
    "checked, because M6-T2 has not produced a bundle to check. A disagreement is recorded "
    "and reported but no curator queue persists it. A retracted fact is NOT flipped OUT and "
    "nothing propagates to premises standing on it — that is M8-T2's JTMS. Linkage "
    "precision and recall, and the false-flag rate against the 5% threshold, are unmeasured "
    "until M10-T4b. And 'three sources agree' means three sources were consulted, not that "
    "their evidence is independent: Crossref carries Retraction-Watch-sourced updates "
    "verbatim and OpenAlex ingests Crossref, so agreement between the two APIs can be one "
    "primary record seen twice. Where it is, the record id is reported beside the verdict."
)

#: The Retraction Watch nature that is a retraction. The table also carries expressions of
#: concern, corrections and reinstatements — 5,512 of 71,799 rows — which are notices and
#: not retractions.
_RETRACTION_NATURE = "retraction"


def basis_lines(width: int = 88, indent: str = "  ") -> list[str]:
    """`PARTIAL_BASIS` as indented display lines. One wrapper, two surfaces."""
    return [f"{indent}{line}" for line in textwrap.wrap(PARTIAL_BASIS, width)]


class RetractionAssessment(FrozenModel):
    """One identifier, every source that answered, and the status they add up to."""

    key: ExternalKey
    status: RetractionStatus
    checks: dict[RetractionSource, RetractionCheck] = Field(default_factory=dict)
    #: Sources that produced no check, and why — a registry that cannot index this kind of
    #: identifier, a transport failure, a table that is not on disk, or a table too small
    #: for its silence to mean anything.
    not_consulted: dict[RetractionSource, str] = Field(default_factory=dict)
    #: Structural, not a comment: this tier is a partial and the record says so.
    is_partial: bool = True
    basis: str = PARTIAL_BASIS

    @property
    def asserting_sources(self) -> set[RetractionSource]:
        return {
            source
            for source, check in self.checks.items()
            if check.result is RetractionFinding.RETRACTED
        }

    @property
    def has_disagreement(self) -> bool:
        """Whether a source found a retraction while another found the work standing."""
        return bool(self.asserting_sources) and any(
            check.result in NOT_RETRACTED_FINDINGS for check in self.checks.values()
        )

    @property
    def derived_records(self) -> tuple[str, ...]:
        """Retraction Watch record ids that a *registry* check cites for its finding.

        The echo, made visible. A Crossref retraction sourced from RW is that RW record
        seen a second time, and a reader counting sources is entitled to know which of
        them were looking at the same paperwork.
        """
        return tuple(
            dict.fromkeys(
                record
                for source, check in sorted(self.checks.items())
                if source is not RetractionSource.RETRACTION_WATCH
                for record in (check.detail or "").split()
                if record.startswith("record-id=")
            )
        )

    def as_evidence_quality(self, existing: EvidenceQuality | None = None) -> EvidenceQuality:
        """This assessment, written into a quality record, leaving M7-T2/T3's fields alone.

        The seam an evidence item will use once M6-T2 produces one: the retraction fields
        are replaced wholesale — a check the current pass did not make must not survive it
        (see `verity.quality.apply`) — and study design, sample size and citation intent are
        carried through untouched, because this tier neither writes nor invalidates them.
        """
        base = existing or EvidenceQuality()
        return base.model_copy(
            update={"retraction": self.status, "retraction_checks": dict(self.checks)}
        )

    def render(self) -> list[str]:
        """The assessment as lines. One shape for the CLI and the apply report alike."""
        lines = [f"{self.key}  {self.status.value}"]
        for source in sorted(RetractionSource):
            check = self.checks.get(source)
            if check is None:
                why = self.not_consulted.get(source, "not consulted")
                lines.append(f"  {source.value:<17} — {why}")
                continue
            detail = f"  ({check.detail})" if check.detail else ""
            lines.append(f"  {source.value:<17} {check.result.value}{detail}")
        if self.has_disagreement:
            lines.append(
                "  sources disagree: "
                + ", ".join(sorted(s.value for s in self.asserting_sources))
                + " report a retraction and another source finds the work standing"
            )
        if self.derived_records:
            lines.append(
                "  a registry check cites "
                + ", ".join(self.derived_records)
                + " — that is a Retraction Watch record seen again, not a second source"
            )
        return lines


def _detail(pairs: dict[str, str]) -> str | None:
    """`"k=v"` pairs, space-separated. What a disagreement report cites."""
    return " ".join(f"{k}={v}" for k, v in pairs.items() if v) or None


def _check(
    source: RetractionSource,
    result: RetractionFinding,
    fetched_at: datetime,
    *,
    detail: str | None = None,
    source_url: str | None = None,
) -> RetractionCheck:
    return RetractionCheck(
        source=source,
        result=result,
        checked_at=fetched_at,
        detail=detail,
        source_url=source_url,
    )


def openalex_finding(record: WorkRecord) -> RetractionCheck | None:
    """OpenAlex's `is_retracted`, read as a finding. `None` when it could not answer.

    The boolean collapses correction, expression of concern and retraction and has a
    documented false-positive history (arXiv:2403.13339), which is why a `true` here alone
    can only reach `retraction-flagged-unconfirmed` — never `retracted`.
    """
    if record.outcome is ReadingOutcome.UNANSWERED:
        return None
    flag = None if record.outcome is ReadingOutcome.ABSENT else openalex.retraction_flag(record)
    if flag is None:
        # Two ways to have no opinion, and both are `NOT_INDEXED` rather than `CLEAN`.
        # OpenAlex indexes works, so a work it has never heard of is not a work it cleared;
        # and a work served without the field is an answer with no opinion in it.
        return _check(
            RetractionSource.OPENALEX, RetractionFinding.NOT_INDEXED, record.fetched_at
        )
    return _check(
        RetractionSource.OPENALEX,
        RetractionFinding.RETRACTED if flag else RetractionFinding.CLEAN,
        record.fetched_at,
        detail=_detail({"is_retracted": str(flag).lower()}),
        source_url=record.source_url,
    )


def crossref_finding(record: WorkRecord) -> RetractionCheck | None:
    """Crossref's `updated-by` notices, read as a finding. `None` when it could not answer.

    `updated-by` and not `update-to` — the two name opposite ends of one link, and only
    notices filed *against* this work can say it was retracted (build-plan.md M7-T1). A work
    may carry several notices, so the test is that some entry is a retraction; a work
    carrying only a correction or a new version is standing, with a notice on it.
    """
    if record.outcome is ReadingOutcome.UNANSWERED:
        return None
    if record.outcome is ReadingOutcome.ABSENT:
        return _check(
            RetractionSource.CROSSREF, RetractionFinding.NOT_INDEXED, record.fetched_at
        )
    types = crossref.updated_by_types(record)
    if _RETRACTION_NATURE in types:
        result = RetractionFinding.RETRACTED
    elif types:
        result = RetractionFinding.NOTICE_NOT_RETRACTION
    else:
        result = RetractionFinding.CLEAN
    return _check(
        RetractionSource.CROSSREF,
        result,
        record.fetched_at,
        detail=_detail(
            {
                "updated-by": ",".join(types),
                "source": ",".join(crossref.updated_by_sources(record)),
                "record-id": ",".join(crossref.updated_by_record_ids(record)),
            }
        ),
        source_url=record.source_url,
    )


def table_finding(record: WorkRecord, table: rw.TableSource) -> RetractionCheck | None:
    """The Retraction Watch row, read as a finding. `None` when the table could not answer.

    **Absence is a finding only against the complete table.** The bulk download is a census
    of recorded retractions, so a work absent from it is a work that stands. The committed
    two-row sample is not a census of anything, and reading its silence as `clean` would
    manufacture this tier's strongest negative out of the smallest file in the repository —
    on a fresh clone, for every key. So a miss there produces no check at all, and the
    reason travels on the assessment.
    """
    if record.outcome is ReadingOutcome.UNANSWERED:
        return None
    if record.outcome is ReadingOutcome.ABSENT:
        if not table.complete:
            return None
        return _check(
            RetractionSource.RETRACTION_WATCH,
            RetractionFinding.CLEAN,
            record.fetched_at,
            detail=_detail({"table": str(table.path)}),
        )
    nature = record.raw_findings.get("nature", "")
    return _check(
        RetractionSource.RETRACTION_WATCH,
        RetractionFinding.RETRACTED
        if _RETRACTION_NATURE in nature.casefold()
        else RetractionFinding.NOTICE_NOT_RETRACTION,
        record.fetched_at,
        detail=_detail(
            {
                "nature": nature,
                "record-id": record.raw_findings.get("record_id", ""),
                "table": str(table.path),
            }
        ),
        source_url=record.source_url,
    )


def decide(checks: dict[RetractionSource, RetractionCheck]) -> RetractionStatus:
    """The cut. `checks` holds only sources that answered.

    Retraction Watch is decisive where it has a record: it is the curated authority, and
    the alternative reading — that any disagreement demotes to flagged — would make the RW
    leg unreachable whenever an API disagreed, contradicting the policy it sits in
    (build-plan.md M7-T1 records this resolution). The two APIs are decisive only together,
    because each alone is a single index with a known error mode.
    """
    asserting = {
        source
        for source, check in checks.items()
        if check.result is RetractionFinding.RETRACTED
    }
    if RetractionSource.RETRACTION_WATCH in asserting:
        return RetractionStatus.RETRACTED
    if {RetractionSource.OPENALEX, RetractionSource.CROSSREF} <= asserting:
        return RetractionStatus.RETRACTED
    if asserting:
        # One index, on its own. Renders as flagged, never as retracted.
        return RetractionStatus.FLAGGED_UNCONFIRMED
    if any(check.result is RetractionFinding.CLEAN for check in checks.values()):
        return RetractionStatus.CLEAN
    # Nothing was asked, or everything that answered had no opinion — a work absent from
    # both registries, or one carrying a notice that settles nothing about retraction.
    # `clean` would assert a source looked and found nothing, and none did.
    return RetractionStatus.UNKNOWN
