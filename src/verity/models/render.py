"""The renderer boundary.

`RenderPayload` is the only structure a renderer (M9 CLI, M9 Streamlit) is permitted to
consume. Making it a distinct type means "the renderer never receives a root aggregate"
is a property that can be tested now, in M1-T1, rather than a convention M9 is trusted to
honour later.

The payload is per-edge by construction: one row per (step, premise) pair, each carrying
the score of *its own* step, labelled with its calibration status. There is no field a
renderer could use to draw a single number over the claim, and no function here composes
scores across steps.

**The projection reads the alethiology, not just the graph.** A `Grounding` row records
what a run concluded; whether that grounding still holds is a question only the fact store
can answer, and design.md §4.2 makes the answer non-monotonic — "a tree that terminated
yesterday can be un-grounded today". So `to_render_payload` takes a `FactLookup` and each
row reports both: what was recorded, and what is true now. The divergence between them is
the invalidation story, rendered rather than hidden.

Scores reach the renderer as a number *and* a label. Requiring the calibration status
alongside the value is what enforces evaluation.md §6; withholding the number instead
would only force a confidence bar to parse its own display string back into a float.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from pydantic import Field

from verity.base import VerityModel
from verity.keys import ExternalKey
from verity.models.claim import ClaimGraph
from verity.models.common import (
    Calibration,
    CapRecord,
    EvidenceState,
    GroundingLiveness,
    TerminationReason,
    utc_now,
)
from verity.models.fact import Fact, FactLookup

#: Field names that would constitute a root aggregate. No model reachable from a
#: renderer may declare one; `tests/test_no_root_aggregate.py` enforces this over
#: `model_fields`, so the check survives future edits to the models.
ROOT_AGGREGATE_FORBIDDEN_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "score",
        "confidence",
        "verdict",
        "truth",
        "truth_score",
        "overall_score",
        "overall_confidence",
        "aggregate",
        "aggregate_score",
        "rating",
        "credibility",
        "credibility_score",
        "accuracy",
        "veracity",
    }
)

#: Attached to every step score in the payload. A step score answers "do these premises
#: entail this conclusion", not "is this claim true", and is never composed with another.
STEP_SCORE_SCOPE_NOTE: Final[str] = (
    "single-step entailment score; not composed with any other step"
)

_FLAGGED_RETRACTION_STATES = ("retracted", "retraction-flagged-unconfirmed")


class RenderRoot(VerityModel):
    """The claim, as a renderer sees it: identity and text. Nothing else."""

    id: str
    text: str


class RenderPremise(VerityModel):
    """One premise row, within one step.

    A premise shared by two steps produces two rows — each showing the score of the step
    it is displayed under, and its ablation delta within that step. Collapsing them would
    put a number beside a premise that belongs to a step the reader is not looking at.
    """

    premise_id: str
    parent_id: str
    text: str
    depth: int
    step_id: str | None = None

    #: The step's score, three ways: the number a bar is drawn from, the calibration
    #: status that must accompany it, and the display string for text surfaces.
    step_score_value: float | None = None
    step_score_calibration: Calibration | None = None
    step_score: str | None = None
    step_score_scope: str = STEP_SCORE_SCOPE_NOTE

    #: This premise's leave-one-out delta within *this* step (M4-T2). Signed.
    ablation_delta_value: float | None = None
    ablation_delta_calibration: Calibration | None = None
    ablation_delta: str | None = None

    #: What the alethiology says now. `evidence_state_recorded` is what the run concluded.
    evidence_state: EvidenceState = EvidenceState.UNVERIFIED
    evidence_state_recorded: EvidenceState = EvidenceState.UNVERIFIED
    evidence_state_diverged: bool = False
    evidence_state_provisional: bool = True

    termination_reason: TerminationReason | None = None

    #: `grounded` is the live answer; `grounding_recorded` is what the run stored. They
    #: differ exactly when a fact has been retracted, demoted, or removed since the run.
    grounded: bool = False
    grounding_recorded: bool = False
    grounding_status: GroundingLiveness = GroundingLiveness.NOT_GROUNDED
    grounding_fact_id: str | None = None
    #: The statement of the fact this premise grounded in, shown beside the premise.
    #: Grounding is exact-key match (evaluation.md §2) and never compares statements, so
    #: `verified` on its own says a work with this identifier sits in the alethiology at
    #: an eligible tier — not that the premise's own content was checked. Alethiology
    #: statements are attributive by construction ("Rekdal (2014) reports that …"), so
    #: printing the grounded statement next to the premise is what makes the difference
    #: between the two visible instead of collapsed into one word. Present whenever the
    #: fact was found, including when it is OUT or below the eligible tier.
    grounding_fact_statement: str | None = None
    bound_key: ExternalKey | None = None

    #: supporting / contradicting / neutral / rejected counts, or None if no bundle yet.
    evidence_counts: dict[str, int] | None = None
    #: Retractions reachable from this premise — through its evidence bundle *and*
    #: through the alethiology fact it is grounded in.
    retraction_flags: list[str] = Field(default_factory=list)


class RenderPayload(VerityModel):
    """What a renderer gets. Per-premise rows and nothing above them."""

    root: RenderRoot
    premises: list[RenderPremise] = Field(default_factory=list)
    max_depth: int = 0
    caps: list[CapRecord] = Field(default_factory=list)
    #: Set when any displayed score is uncalibrated, so the UI can say so once.
    has_uncalibrated_scores: bool = False
    #: Set when any recorded grounding no longer holds — the invalidation banner.
    has_stale_groundings: bool = False
    #: When the alethiology was consulted. Grounding is non-monotonic, so a payload is a
    #: reading at a time, not a permanent fact about the graph.
    checked_at: datetime = Field(default_factory=utc_now)


def _grounding_status(fact: Fact | None) -> GroundingLiveness:
    if fact is None:
        return GroundingLiveness.FACT_MISSING
    if fact.status.value == "OUT":
        return GroundingLiveness.FACT_OUT
    if not fact.is_verified:
        return GroundingLiveness.FACT_INELIGIBLE_TIER
    return GroundingLiveness.LIVE


def _retraction_flags(quality: object, label: str) -> list[str]:
    status = getattr(getattr(quality, "retraction", None), "value", None)
    if status in _FLAGGED_RETRACTION_STATES:
        return [f"{label}: {status}"]
    return []


def to_render_payload(
    graph: ClaimGraph,
    facts: FactLookup,
    *,
    checked_at: datetime | None = None,
) -> RenderPayload:
    """Project a stored graph into the renderer's view, against the current alethiology.

    `facts` is required. A projection that cannot reach the fact store would report a
    premise as grounded after the fact beneath it was retracted, which is the one thing
    the invalidation layer exists to prevent.
    """
    rows: list[RenderPremise] = []
    uncalibrated = False
    stale = False

    for edge in graph.walk():
        premise = graph.premises[edge.premise_id]
        step = graph.step_concluding(edge.parent_id)

        score = step.score if step else None
        if score is not None:
            uncalibrated = uncalibrated or score.is_uncalibrated

        ablation = step.ablation_for(premise.id) if step else None
        if ablation is not None:
            uncalibrated = uncalibrated or ablation.is_uncalibrated

        grounding = graph.grounding_for(premise.id)
        fact = facts.get(grounding.fact_id) if grounding else None
        status = _grounding_status(fact) if grounding else GroundingLiveness.NOT_GROUNDED
        live = status is GroundingLiveness.LIVE
        if grounding is not None and not live:
            stale = True

        recorded_state = premise.evidence_state
        live_state = (
            recorded_state
            if recorded_state is not EvidenceState.VERIFIED
            else (EvidenceState.VERIFIED if live else EvidenceState.UNVERIFIED)
        )

        flags: list[str] = []
        bundle = graph.bundles.get(premise.id)
        if bundle is not None:
            for item in (*bundle.supporting, *bundle.contradicting, *bundle.neutral):
                flags.extend(_retraction_flags(item.quality, str(item.key or item.id)))
        # Every fact the alethiology holds under the key this premise cites — not only the
        # one it grounded in. A retraction warning is not contingent on grounding: a fact
        # below the eligible tier grounds nothing, and a premise citing a retracted work is
        # exactly the case most worth flagging. Keying the warning to the grounding row
        # would have made the seeded chocolate trail — single-secondary by the tier gate,
        # therefore never a grounding — render clean.
        for known in facts.facts_for(premise.bound_key) if premise.bound_key else ():
            flags.extend(_retraction_flags(known.evidence_quality, str(known.key)))
        if fact is not None and (
            premise.bound_key is None or not fact.key.matches(premise.bound_key)
        ):
            flags.extend(_retraction_flags(fact.evidence_quality, str(fact.key)))
        flags = list(dict.fromkeys(flags))

        rows.append(
            RenderPremise(
                premise_id=premise.id,
                parent_id=edge.parent_id,
                text=premise.text,
                depth=edge.depth,
                step_id=edge.step_id,
                step_score_value=score.value if score else None,
                step_score_calibration=score.calibration if score else None,
                step_score=score.label() if score else None,
                ablation_delta_value=ablation.delta if ablation else None,
                ablation_delta_calibration=ablation.calibration if ablation else None,
                ablation_delta=ablation.label() if ablation else None,
                evidence_state=live_state,
                evidence_state_recorded=recorded_state,
                evidence_state_diverged=live_state is not recorded_state,
                evidence_state_provisional=premise.evidence_state_provisional,
                termination_reason=premise.termination_reason,
                grounded=live,
                grounding_recorded=grounding is not None,
                grounding_status=status,
                grounding_fact_id=grounding.fact_id if grounding else None,
                grounding_fact_statement=fact.statement if fact else None,
                bound_key=premise.bound_key,
                evidence_counts=bundle.counts if bundle else None,
                retraction_flags=flags,
            )
        )

    return RenderPayload(
        root=RenderRoot(id=graph.root_claim.id, text=graph.root_claim.text),
        premises=rows,
        max_depth=max((row.depth for row in rows), default=0),
        caps=graph.metadata.caps,
        has_uncalibrated_scores=uncalibrated,
        has_stale_groundings=stale,
        checked_at=checked_at or utc_now(),
    )
