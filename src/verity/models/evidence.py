"""Retrieved evidence and its quality metadata.

Bundles are what M9 renders and what M5-T2 promotes facts from. A bundle can never by
itself produce `EvidenceState.VERIFIED` — that is pinned to exact-key alethiology
grounding (design.md §4.2) — so the state carried here is explicitly provisional until
M8-T3 lands the settled semantics.

**What was asked is recorded, not just what came back.** Two rules depend on it and
neither can be checked from results alone. M7-T1's retraction policy counts sources and
logs disagreements, so it needs to know that a source was consulted and returned clean —
distinct from never having been consulted. M6-T2 makes contrasting-evidence queries a
mandatory branch "so one-sided bundles can't happen silently", and an empty list is
exactly that silence: a search that found nothing and a search nobody ran look identical
unless the query itself is recorded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from verity.base import FrozenModel, VerityModel
from verity.keys import ExternalKey
from verity.models.common import (
    CapRecord,
    Extraction,
    LabeledField,
    Provenance,
    QueryClass,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
    Score,
    Stance,
)


class RetractionCheck(FrozenModel):
    """One source, asked once, and what it said.

    `checked_at` is mandatory for the same reason `Provenance.accessed_at` is: a
    retraction check is a reading at a time, and a check with no time cannot be
    re-validated or aged out.
    """

    source: RetractionSource
    result: RetractionFinding
    checked_at: datetime
    source_url: str | None = None
    #: Whatever identifies the finding in that source — an RW record id, a Crossref
    #: `update-to` type, an OpenAlex work id. This is what a disagreement report cites.
    detail: str | None = None


class EvidenceQuality(VerityModel):
    """Per-work quality metadata (M7). Every field carries its own provenance."""

    #: The policy's conclusion. M7-T1 owns the cut that produces it from `retraction_checks`;
    #: the floor enforced here is only that a flag cannot come from nothing.
    retraction: RetractionStatus = RetractionStatus.UNKNOWN
    #: What each consulted source returned, keyed by source. An absent key means that
    #: source was never asked — which is why this is a map and not a list of asserters.
    retraction_checks: dict[RetractionSource, RetractionCheck] = Field(default_factory=dict)
    study_design: LabeledField[str] | None = None
    sample_size: LabeledField[int] | None = None
    citation_intent: LabeledField[str] | None = None
    supporting_citations: int | None = None
    contrasting_citations: int | None = None

    @property
    def checked_sources(self) -> set[RetractionSource]:
        return set(self.retraction_checks)

    @property
    def asserting_sources(self) -> set[RetractionSource]:
        """Sources that returned a retraction — the count M7-T1's cut is made on."""
        return {
            source
            for source, check in self.retraction_checks.items()
            if check.result is RetractionFinding.RETRACTED
        }

    @property
    def has_retraction_disagreement(self) -> bool:
        """Whether consulted sources returned different answers.

        M7-T1's exit criterion logs exactly this, so it is an observation about the
        checks rather than part of the policy that reads them. `NOT_INDEXED` is not a
        disagreement — a source with no opinion is not contradicting one that has one.
        """
        answers = {
            check.result
            for check in self.retraction_checks.values()
            if check.result is not RetractionFinding.NOT_INDEXED
        }
        return len(answers) > 1

    @property
    def has_model_extracted_fields(self) -> bool:
        return any(
            field is not None and field.extraction is Extraction.MODEL_EXTRACTED
            for field in (self.study_design, self.sample_size, self.citation_intent)
        )

    @model_validator(mode="after")
    def _a_flag_cannot_come_from_nothing(self) -> EvidenceQuality:
        """A soundness floor, not the policy cut.

        Where the line between `retracted` and `flagged-unconfirmed` falls is M7-T1's to
        decide. That a work cannot be marked either one while no consulted source says so
        — or marked clean while one does — is not a policy question.
        """
        if not self.retraction_checks:
            return self
        flagged = self.retraction in (
            RetractionStatus.RETRACTED,
            RetractionStatus.FLAGGED_UNCONFIRMED,
        )
        if flagged and not self.asserting_sources:
            raise ValueError(
                f"retraction is {self.retraction.value} but no consulted source asserts it"
            )
        if self.retraction is RetractionStatus.CLEAN and self.asserting_sources:
            raise ValueError(
                "retraction is clean while "
                f"{sorted(s.value for s in self.asserting_sources)} assert a retraction"
            )
        return self


class EvidenceItem(VerityModel):
    """One retrieved work, as it relates to one premise."""

    id: str
    key: ExternalKey | None = None
    title: str
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    stance: Stance | None = None
    stance_score: Score | None = None
    quality: EvidenceQuality = Field(default_factory=EvidenceQuality)
    provenance: Provenance


class IssuedQuery(FrozenModel):
    """A query that was actually sent, and how much it returned.

    Recorded even when it returns nothing — especially then. `returned` is the count
    before any cap, so a bundle's `caps` and this number together say what was found and
    what was kept.
    """

    query_class: QueryClass
    text: str
    source: str  # "openalex" | "crossref" | "pubmed" | "s2"
    issued_at: datetime
    returned: int = Field(ge=0)


class EvidenceBundle(VerityModel):
    """Symmetric evidence for one premise (M6-T3).

    The supporting/contradicting split is structural, not editorial: M6-T2 issues
    contrasting-evidence queries as a mandatory branch so one-sided bundles cannot
    happen silently. `queries` is what makes that checkable — without it, a bundle that
    ran no contrasting query is indistinguishable from one whose contrasting query came
    back empty.
    """

    premise_id: str
    supporting: list[EvidenceItem] = Field(default_factory=list)
    contradicting: list[EvidenceItem] = Field(default_factory=list)
    neutral: list[EvidenceItem] = Field(default_factory=list)
    #: `has-evidence | none` — provisional until M8-T3 refines it in place.
    provisional_state: Literal["has-evidence", "none"] = "none"
    #: Every query issued for this premise, including the ones that returned nothing.
    queries: list[IssuedQuery] = Field(default_factory=list)
    caps: list[CapRecord] = Field(default_factory=list)
    rejected_count: int = 0

    @property
    def counts(self) -> dict[str, int]:
        return {
            "supporting": len(self.supporting),
            "contradicting": len(self.contradicting),
            "neutral": len(self.neutral),
            "rejected": self.rejected_count,
        }

    @property
    def searched_classes(self) -> set[QueryClass]:
        return {query.query_class for query in self.queries}

    @property
    def contrasting_search_ran(self) -> bool:
        """Whether the mandatory contrasting branch was actually issued (M6-T2)."""
        return QueryClass.CONTRASTING in self.searched_classes
