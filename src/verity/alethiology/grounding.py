"""The grounding decision: does this premise stand on a fact, and if not, why not.

Grounding is exact-key match to an alethiology fact that is IN and in a grounding-eligible
tier (evaluation.md §2). That predicate is pre-registered and this module does not widen
it. What it adds is the *reason* a premise did not ground, because a rate assembled from
unexplained failures cannot be diagnosed, and build-plan.md §4 says out loud that the
headline rate is structurally capped and a miss has to be read correctly.

Three distinctions the reasons carry that a bare boolean cannot:

- **Applicability is a property of the premise, not an outcome.** A definitional or
  background terminal cannot ground — no paper-shaped key can verify it. Those terminals
  count in the pre-registered denominator (build-plan.md §4, conservative: they deflate),
  and the supplementary citable-branches-only rate is computed by excluding them, so the
  partition has to be recorded rather than inferred later. It is a separate field from the
  reason because a by-design premise that *does* ground is a real grounding, not a
  contradiction.
- **`ALIAS_ONLY` makes a deflation visible.** One work carries a DOI and a PMID; if a
  premise binds one and the seed holds the other, exact-key match misses and the miss is
  invisible. Reporting it neither inflates the rate nor hides it. Whether aliases *should*
  ground is a change to a pre-registered definition, so it is a ruling for
  evaluation.md §2 and not a default this code picks.
- **Candidates fail individually.** A key with one OUT fact and one below-tier fact has no
  single reason, so verdicts are per candidate and the summary reason says only that none
  qualified.

Statements are never compared. An earlier draft preferred a candidate whose statement hash
matched the premise; under the seed's attributive-statement rule ("Hamblin (1981) reports
that …" against an object-level premise) that comparison is false by construction, so it
was a tie-break that could never fire. Selection is plain deterministic ordering, and the
gap it papered over is shown instead — `RenderPremise.grounding_fact_statement` puts the
grounded statement next to the premise so a reader can see what `verified` covers.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from verity.base import FrozenModel, VerityModel
from verity.keys import ExternalKey
from verity.models.claim import Grounding, Premise
from verity.models.common import ConfidenceTier, PremiseType, TerminationReason, TmsStatus
from verity.models.fact import Fact

#: Strongest first. Selection order among candidates that all already qualify — it decides
#: *which* fact is named, never *whether* the premise grounded.
TIER_RANK: dict[ConfidenceTier, int] = {
    tier: rank
    for rank, tier in enumerate(
        (
            ConfidenceTier.VERIFIED_PRIMARY,
            ConfidenceTier.CORROBORATED_MULTI_SECONDARY,
            ConfidenceTier.SINGLE_SECONDARY,
            ConfidenceTier.INFERRED,
            ConfidenceTier.MARKETING_CLAIM,
        )
    )
}

#: Premise types no external identifier can verify. build-plan.md §3 terminates these as
#: `unverifiable-by-design` without spending depth budget.
UNGROUNDABLE_TYPES = frozenset({PremiseType.DEFINITIONAL, PremiseType.BACKGROUND})


class CandidateReason(StrEnum):
    ELIGIBLE = "eligible"
    FACT_OUT = "fact-out"
    INELIGIBLE_TIER = "ineligible-tier"


class GroundingReason(StrEnum):
    GROUNDED = "grounded"
    NO_BOUND_KEY = "no-bound-key"
    NO_FACT_FOR_KEY = "no-fact-for-key"
    ALIAS_ONLY = "alias-only"
    NO_ELIGIBLE_CANDIDATE = "no-eligible-candidate"


class CandidateVerdict(FrozenModel):
    """One fact under the premise's key, and why it did or did not qualify."""

    fact_id: str
    tier: ConfidenceTier
    status: TmsStatus
    reason: CandidateReason


class GroundingAttempt(VerityModel):
    """The result of asking the alethiology to ground one premise."""

    premise_id: str
    key: ExternalKey | None = None
    reason: GroundingReason
    grounding: Grounding | None = None
    candidates: list[CandidateVerdict] = Field(default_factory=list)
    #: Populated on `ALIAS_ONLY`: known identifiers for the same work that *do* hold facts.
    alias_keys: list[ExternalKey] = Field(default_factory=list)
    #: False for terminals no identifier can verify. The supplementary citable-only rate
    #: is computed over attempts where this is True.
    applicable: bool = True
    applicability_basis: Literal["termination-reason", "premise-type", "default"] = "default"

    @property
    def grounded(self) -> bool:
        return self.reason is GroundingReason.GROUNDED

    @property
    def eligible_candidates(self) -> list[CandidateVerdict]:
        """Facts under this key that qualified. More than one means the choice was a
        tie-break: `select` names one deterministically, and which one is arbitrary as far
        as the premise's content is concerned, because grounding compares keys only."""
        return [v for v in self.candidates if v.reason is CandidateReason.ELIGIBLE]

    @model_validator(mode="after")
    def _summary_agrees_with_the_verdicts(self) -> GroundingAttempt:
        """The summary reason and the per-candidate verdicts must tell the same story.

        They diverged once already: `attempt_grounding` consumed its `candidates` iterable
        building the verdict list, then re-read the exhausted iterator to select, and
        returned `no-eligible-candidate` beside a verdict list saying `eligible`. It failed
        closed, silently, and in the direction that deflates the pre-registered grounding
        rate. A contradiction the type can state is a contradiction the type can refuse.
        """
        eligible = self.eligible_candidates
        if self.reason is GroundingReason.GROUNDED and not eligible:
            raise ValueError("grounded, but no candidate verdict says a fact qualified")
        if self.reason is GroundingReason.NO_ELIGIBLE_CANDIDATE and eligible:
            raise ValueError(
                f"reported no eligible candidate while {len(eligible)} verdict(s) say eligible"
            )
        return self


def applicability(
    premise: Premise,
) -> tuple[bool, Literal["termination-reason", "premise-type", "default"]]:
    """Whether an external key could verify this premise, and what decided it.

    The recorded termination reason wins when there is one: it is what the decomposer
    concluded, and the premise type is a classification that may disagree with it.
    """
    if premise.termination_reason is not None:
        applicable = premise.termination_reason is not TerminationReason.UNVERIFIABLE_BY_DESIGN
        return applicable, "termination-reason"
    if premise.premise_type is not None:
        return premise.premise_type not in UNGROUNDABLE_TYPES, "premise-type"
    return True, "default"


def _verdict(fact: Fact) -> CandidateVerdict:
    if fact.status is TmsStatus.OUT:
        reason = CandidateReason.FACT_OUT
    elif not fact.is_verified:
        reason = CandidateReason.INELIGIBLE_TIER
    else:
        reason = CandidateReason.ELIGIBLE
    return CandidateVerdict(fact_id=fact.id, tier=fact.tier, status=fact.status, reason=reason)


def select(candidates: Iterable[Fact]) -> Fact | None:
    """The eligible fact a premise grounds in, chosen deterministically.

    Ordered by tier strength, then creation time, then id. `created_at` participates only
    as a tie-break *below* tier, and seeded facts carry an explicit resolution timestamp
    rather than a load-time `now()` — ordering by wall clock would make which fact a graph
    names depend on when the store happened to be seeded, which M1-T2's replay check
    compares.
    """
    eligible = [fact for fact in candidates if fact.is_verified]
    if not eligible:
        return None
    return min(eligible, key=lambda f: (TIER_RANK[f.tier], f.created_at, f.id))


def attempt_grounding(
    premise: Premise,
    candidates: Iterable[Fact],
    *,
    alias_keys: Iterable[ExternalKey] = (),
    grounded_at: datetime | None = None,
) -> GroundingAttempt:
    """Decide whether `premise` grounds in one of `candidates`, and record why.

    `candidates` are the facts stored under the premise's bound key — the caller does the
    exact-key lookup, this decides. It is read twice, so it is materialized first: a
    generator would be exhausted by the verdict pass and leave the selection pass with
    nothing. `alias_keys` are identifiers for the same work that hold facts of their own;
    passing them turns an invisible miss into a reported one. `grounded_at` is injectable
    so a replayed run reproduces its graph byte-for-byte.
    """
    candidates = list(candidates)
    applicable, basis = applicability(premise)
    base = {
        "premise_id": premise.id,
        "key": premise.bound_key,
        "applicable": applicable,
        "applicability_basis": basis,
    }

    if premise.bound_key is None:
        # design.md §4.3: a decomposition-time `candidate_key` is a hint to verify, not a
        # binding. Only `bound_key` grounds, which is why the binder is a named producer.
        return GroundingAttempt(**base, reason=GroundingReason.NO_BOUND_KEY)

    verdicts = [_verdict(fact) for fact in candidates]
    chosen = select(candidates)

    if chosen is not None:
        grounding = Grounding(
            premise_id=premise.id,
            fact_id=chosen.id,
            matched_key=premise.bound_key,
            **({"grounded_at": grounded_at} if grounded_at is not None else {}),
        )
        return GroundingAttempt(
            **base,
            reason=GroundingReason.GROUNDED,
            grounding=grounding,
            candidates=verdicts,
        )

    if verdicts:
        return GroundingAttempt(
            **base, reason=GroundingReason.NO_ELIGIBLE_CANDIDATE, candidates=verdicts
        )

    aliases = list(alias_keys)
    if aliases:
        return GroundingAttempt(**base, reason=GroundingReason.ALIAS_ONLY, alias_keys=aliases)
    return GroundingAttempt(**base, reason=GroundingReason.NO_FACT_FOR_KEY)
