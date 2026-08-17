"""Shared value objects and the enum vocabulary.

Four types here do enforcement work rather than mere modelling:

- `Score` carries its own calibration status *and* its domain, so evaluation.md §6's
  standing rule ("every model-produced number is paired with a human anchor or explicitly
  labeled uncalibrated") holds by construction, and a number that cannot be a probability
  cannot be one. `nan` is the reason the domain matters: every comparison against a
  threshold returns False, so a broken scorer would read as a confidently-failing step.
- `AblationDelta` is a *difference* of two step scores and therefore signed — a separate
  type rather than a `Score`, and one that records both scores it was measured from.
- `LabeledField` carries extraction provenance, so design.md §5's rule that "a registry N
  and a text-mined N must never be indistinguishable" is a type distinction.
- `CapRecord` gives evaluation.md §6's "no silent caps" a structural home: a cap that bit
  must say what it dropped, or say the count is unavailable.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from verity.base import FrozenModel

#: Scores are probabilities. `allow_inf_nan=False` is stated rather than implied by the
#: bounds, so the error a caller sees names the actual problem.
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]


def utc_now() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)


class ConfidenceTier(StrEnum):
    """Source confidence, per design.md §4.1.

    Supersedes the research matrix's coarser `verified | inferred | marketing-claim`,
    which conflated verified-against-primary with corroborated-by-one-secondary.
    """

    VERIFIED_PRIMARY = "verified-primary"
    CORROBORATED_MULTI_SECONDARY = "corroborated-multi-secondary"
    SINGLE_SECONDARY = "single-secondary"
    INFERRED = "inferred"
    MARKETING_CLAIM = "marketing-claim"


class Calibration(StrEnum):
    UNCALIBRATED = "uncalibrated"
    CALIBRATED = "calibrated"


class Extraction(StrEnum):
    """How a metadata field was obtained. Never collapse these."""

    REGISTRY = "registry"  # e.g. ClinicalTrials.gov enrollment, ACTUAL
    STRUCTURED = "structured"  # e.g. PubMed MeSH publication type
    MODEL_EXTRACTED = "model-extracted"  # e.g. LLM-mined sample size (M7-T4)


class PremiseType(StrEnum):
    EMPIRICAL_CITABLE = "empirical-citable"
    STATISTICAL = "statistical"
    DEFINITIONAL = "definitional"
    BACKGROUND = "background"


class TerminationReason(StrEnum):
    """Why a branch stopped descending (M3-T2). Reported per run, never inferred.

    Six values in two kinds, and the split is load-bearing. The first three are properties
    of the *premise*: it stands on a fact, a source could settle it, or nothing
    paper-shaped could. The last three are properties of the *run*: the descent would have
    expanded this premise and did not. Only the first kind says anything about whether an
    external key could verify the premise, which is why `alethiology.grounding` reads a
    recorded reason for the applicability partition and falls through to the premise type
    for the rest.

    `CAP_EXIT` and `DECOMPOSITION_REFUSED` extend build-plan.md M3-T2's original four.
    Folding either into `BUDGET_EXIT` would corrupt the budget-exit rate evaluation.md §1
    publishes — a run stopped by a node cap would read as one that ran out of depth —
    and leaving them unrecorded would put a hole in a mix whose denominator is every leaf.

    `DECOMPOSITION_REFUSED` means *no step exists here because the attempt was refused* —
    by the descent before calling (a premise restating the root claim), or by the tier's
    drop rule after (a cyclic premise, an empty proposal, a truncated response, a provider
    refusal). The enum stays coarse deliberately; which of those happened is recorded in
    the decompose stage's `counts`, so **M10-T1 reads the manifest alongside the graph**.
    The one sub-reason recoverable from the graph alone is the restatement, through
    `ClaimGraph.restating_premise_ids()`.

    `GROUNDED` is unreachable while the pipeline runs `decompose → verify → bind → ground`:
    nothing is bound during the descent, and the only key available then is the one the
    decomposer proposed, which the binder already records as circular evidence. The run
    says so rather than letting a zero read as "no branch grounded".
    """

    GROUNDED = "grounded"
    CITATION_SHAPED = "citation-shaped"
    UNVERIFIABLE_BY_DESIGN = "unverifiable-by-design"
    BUDGET_EXIT = "budget-exit"
    CAP_EXIT = "cap-exit"
    DECOMPOSITION_REFUSED = "decomposition-refused"


#: Reasons that describe the premise rather than the descent's own limits. Shipped as a
#: set so no consumer re-derives the partition by listing names — `applicability` reads a
#: reason only when it is one of these.
EPISTEMIC_TERMINATIONS: frozenset[TerminationReason] = frozenset(
    {
        TerminationReason.GROUNDED,
        TerminationReason.CITATION_SHAPED,
        TerminationReason.UNVERIFIABLE_BY_DESIGN,
    }
)

#: The terminal a premise type carries *by what the type means*, independent of any run's
#: configuration. This is the whole bridge between the two vocabularies, and it is a map
#: rather than a pair of conditionals because the epistemic reasons are consumed as claims
#: about the premise: `applicability` reads `citation-shaped` as "a source could settle
#: this", so nothing but the type is entitled to write it. A type absent from this map has
#: no honest terminal of its own — `statistical` is the case, since no paper settles
#: arithmetic and yet "unverifiable" is false of it — and `DecompositionConfig` therefore
#: requires such a type to be recursable, so the descent never has to invent a label for it.
#:
#: Adding a fifth `PremiseType` forces that choice rather than defaulting to one: give it an
#: intrinsic terminal here, or the configuration validator refuses every predicate that
#: omits it.
INTRINSIC_TERMINALS: dict[PremiseType, TerminationReason] = {
    PremiseType.EMPIRICAL_CITABLE: TerminationReason.CITATION_SHAPED,
    PremiseType.DEFINITIONAL: TerminationReason.UNVERIFIABLE_BY_DESIGN,
    PremiseType.BACKGROUND: TerminationReason.UNVERIFIABLE_BY_DESIGN,
}

#: Premise types no external identifier can verify. Derived from the map above rather than
#: listed again: two tiers read this — M3-T2 terminates them without spending depth budget,
#: M5's grounding partition excludes them from the supplementary citable-only denominator
#: (build-plan.md §4) — and a second literal is how the headline and supplementary rates
#: come to be computed over two different partitions.
UNGROUNDABLE_TYPES: frozenset[PremiseType] = frozenset(
    kind
    for kind, reason in INTRINSIC_TERMINALS.items()
    if reason is TerminationReason.UNVERIFIABLE_BY_DESIGN
)

#: Types the descent cannot terminate on its own authority, so a predicate must expand them.
RECURSION_REQUIRED_TYPES: frozenset[PremiseType] = frozenset(
    kind for kind in PremiseType if kind not in INTRINSIC_TERMINALS
)


class GroundingLiveness(StrEnum):
    """Whether a recorded grounding still holds *now* (design.md §4.2).

    Grounding is non-monotonic: "a tree that terminated yesterday can be un-grounded
    today." A `Grounding` row records what the run concluded; this records what the
    alethiology says at render time, which is why the two are separate.
    """

    NOT_GROUNDED = "not-grounded"
    LIVE = "live"
    FACT_MISSING = "fact-missing"
    FACT_OUT = "fact-out"
    FACT_INELIGIBLE_TIER = "fact-ineligible-tier"


class EvidenceState(StrEnum):
    """Per-premise evidence state (design.md §4.2), orthogonal to JTMS IN/OUT.

    `VERIFIED` is pinned to exact-key alethiology grounding and can never be derived
    from a retrieved-evidence bundle. `CONTESTED` is cut mechanically at the
    pre-registered stance floor and never enters the JTMS as a justification.
    """

    VERIFIED = "verified"
    CONTESTED = "contested"
    UNVERIFIED = "unverified"


class TmsStatus(StrEnum):
    IN = "IN"
    OUT = "OUT"


class Stance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class RetractionStatus(StrEnum):
    """Verdict of the three-source retraction policy (M7-T1).

    `RETRACTED` requires the Retraction Watch table or agreement between both APIs;
    a single API source yields `FLAGGED_UNCONFIRMED`, which must render as flagged
    rather than retracted. `UNKNOWN` is the default because "not checked" and "checked
    and clean" are different claims and only one of them is safe to render.

    This is the *conclusion*. What each source actually returned is a `RetractionCheck`,
    and the policy that turns those into this is M7-T1's.
    """

    CLEAN = "clean"
    RETRACTED = "retracted"
    FLAGGED_UNCONFIRMED = "retraction-flagged-unconfirmed"
    UNKNOWN = "unknown"


class RetractionSource(StrEnum):
    """The three sources the policy consults. Closed by design — the cut counts them."""

    RETRACTION_WATCH = "retraction-watch"
    CROSSREF = "crossref"
    OPENALEX = "openalex"


class RetractionFinding(StrEnum):
    """What one source returned when it was asked.

    `NOT_INDEXED` is separate from `CLEAN` deliberately: a source that has never heard of
    a work has no opinion about it, and counting that as clean would let an unindexed DOI
    silently outvote a source that did find a retraction.
    """

    RETRACTED = "retracted"
    CLEAN = "clean"
    NOT_INDEXED = "not-indexed"


class QueryClass(StrEnum):
    """Which side of the symmetric search a query was issued for (M6-T2)."""

    SUPPORTING = "supporting"
    CONTRASTING = "contrasting"


class ClaimType(StrEnum):
    CAUSAL = "causal"
    CORRELATIONAL = "correlational"
    STATISTICAL = "statistical"
    EXISTENCE = "existence"


class Provenance(FrozenModel):
    """Where a piece of information came from, and when it was read.

    `accessed_at` is mandatory: grounding is non-monotonic (design.md §4.2), so every
    external fact needs an access time for M5-T3's TTL re-validation.
    """

    source: str  # "openalex" | "crossref" | "pubmed" | "ctgov" | "s2" | "seed" | "llm"
    source_url: str | None = None
    #: Mandatory, never defaulted to now(): a default would hand a seed record — or any
    #: row rebuilt from a file that omits the field — a freshness it never had, and the
    #: M5-T3 TTL re-validation reads exactly this field to decide what is stale. It must
    #: also carry a zone: that re-validation compares this against a deadline, and a naive
    #: reading is silently interpreted in whatever zone the comparison happens to use
    #: rather than rejected, which turns "stale" into a function of where the process runs.
    accessed_at: datetime
    confidence_tier: ConfidenceTier = ConfidenceTier.INFERRED

    @model_validator(mode="after")
    def _access_time_carries_a_zone(self) -> Provenance:
        if self.accessed_at.tzinfo is None:
            raise ValueError(
                f"provenance from {self.source!r} has a naive accessed_at "
                f"({self.accessed_at.isoformat()}); an access is a time in a zone"
            )
        return self


class Score(FrozenModel):
    """A model-produced probability, carrying its calibration status.

    Defaults to `UNCALIBRATED` deliberately: a score becomes calibrated only when
    something records the basis on which it was calibrated (M4-T3, M10-T3) — so claiming
    calibration without a basis is the uncalibrated label removed and nothing put in its
    place, and is rejected.
    """

    value: UnitInterval
    scorer: str  # model or checkpoint identifier, e.g. "MiniCheck-Flan-T5-Large"
    calibration: Calibration = Calibration.UNCALIBRATED
    basis: str | None = None  # e.g. "ROC on EntailmentBank; distribution-shifted"

    @model_validator(mode="after")
    def _calibration_carries_its_basis(self) -> Score:
        if self.calibration is Calibration.CALIBRATED and not self.basis:
            raise ValueError("a calibrated score must record the basis it was calibrated on")
        return self

    @property
    def is_uncalibrated(self) -> bool:
        return self.calibration is Calibration.UNCALIBRATED

    def label(self) -> str:
        """Display string. An uncalibrated score always says so."""
        suffix = " (uncalibrated)" if self.is_uncalibrated else ""
        return f"{self.value:.2f}{suffix}"


class AblationDelta(FrozenModel):
    """Leave-one-out measurement for one premise *within one step* (M4-T2).

    A premise is load-bearing iff removing it drops the step's score by more than
    `VerifierConfig.ablation_delta`. Both scores are recorded rather than the difference
    alone, so the measurement can be re-read against a different floor without re-running
    the verifier — and so a delta is never separable from what it was measured against.

    Signed by construction, which is why this is not a `Score`: an ablation can raise a
    step's score, and a type constrained to probabilities could not say so.
    """

    step_score: UnitInterval
    ablated_score: UnitInterval
    scorer: str
    calibration: Calibration = Calibration.UNCALIBRATED
    basis: str | None = None

    @model_validator(mode="after")
    def _calibration_carries_its_basis(self) -> AblationDelta:
        if self.calibration is Calibration.CALIBRATED and not self.basis:
            raise ValueError("a calibrated delta must record the basis it was calibrated on")
        return self

    @property
    def delta(self) -> float:
        """How far the step's score falls when this premise is removed."""
        return self.step_score - self.ablated_score

    @property
    def is_uncalibrated(self) -> bool:
        return self.calibration is Calibration.UNCALIBRATED

    def label(self) -> str:
        suffix = " (uncalibrated)" if self.is_uncalibrated else ""
        return f"{self.delta:+.2f}{suffix}"


class LabeledField[T](FrozenModel):
    """A metadata value that cannot be separated from how it was obtained."""

    value: T
    extraction: Extraction
    provenance: Provenance

    @property
    def is_model_extracted(self) -> bool:
        return self.extraction is Extraction.MODEL_EXTRACTED


class CapRecord(FrozenModel):
    """A bound that was actually applied during a run. Reported, never silent.

    evaluation.md §6: "If coverage is bounded — top-N, sampling, no-retry — say what was
    dropped." Some caps genuinely cannot produce a count (a no-retry cap drops attempts
    nobody enumerated), so `"uncounted"` is a legal answer — but it has to be *given*.
    Leaving `dropped` unset on an applied cap is the silent cap the rule names.
    """

    name: str  # e.g. "max_premises_per_node", "retrieval_top_k"
    limit: int
    applied: bool
    dropped: int | Literal["uncounted"] | None = None

    @model_validator(mode="after")
    def _applied_caps_say_what_they_dropped(self) -> CapRecord:
        if self.applied and self.dropped is None:
            raise ValueError(
                f"cap {self.name!r} was applied but does not say what it dropped; "
                "pass a count, or 'uncounted' if the count is unavailable"
            )
        if not self.applied and self.dropped is not None:
            raise ValueError(f"cap {self.name!r} did not apply but reports a drop")
        return self
