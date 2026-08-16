"""Shared fixtures.

The hand-built graph is deliberately the *whole* shape rather than a minimal one: root
claim, a scored three-premise step, a recursive second-level step, an ablation delta, a
premise grounded in an alethiology fact by exact key, a symmetric evidence bundle
carrying a retracted source, and an applied cap. Every producer that lands in later
tiers writes into one of these slots, so the round-trip test covers the real payload
rather than an empty envelope.

`fact_lookup` is the other half of the render boundary: the projection reads the
alethiology to decide whether a recorded grounding still holds, so every render test needs
a fact store to read.

The claim is the spinach-iron decimal myth; the retraction trail is the
chocolate-weight-loss hoax DOI, both low-valence per the demo-claim valence rule.

Both identifiers are real and resolve. The alethiology statement is **attributive** —
"Hamblin (1981) reports that …" rather than the bare proposition — because that is what a
quote from a work's own abstract can establish, and because grounding is exact-key match
and never compares statements: a fact asserting an object-level proposition would ground a
premise as `verified` on the strength of a shared identifier alone. The premise it grounds
is object-level, so the fixture exercises the gap the render row's
`grounding_fact_statement` exists to show.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from verity.keys import ExternalKey, KeyType
from verity.models.claim import (
    Claim,
    ClaimGraph,
    EntailmentStep,
    GraphMetadata,
    Grounding,
    Premise,
)
from verity.models.common import (
    AblationDelta,
    Calibration,
    CapRecord,
    ConfidenceTier,
    EvidenceState,
    Extraction,
    LabeledField,
    PremiseType,
    Provenance,
    QueryClass,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
    Score,
    Stance,
    TerminationReason,
)
from verity.models.evidence import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceQuality,
    IssuedQuery,
    RetractionCheck,
)
from verity.models.fact import Fact, InMemoryFacts

ACCESSED = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

#: Hamblin, "Fake." BMJ 1981 — the origin of the spinach decimal-error story.
SPINACH_KEY = ExternalKey(type=KeyType.DOI, value="10.1136/bmj.283.6307.1671")
#: Bohannon et al., Int Arch Med 2015 — retracted; RW record 17524.
CHOCOLATE_KEY = ExternalKey(type=KeyType.DOI, value="10.3823/1654")


def three_source_agreement(
    finding: RetractionFinding, checked_at: datetime = ACCESSED
) -> dict[RetractionSource, RetractionCheck]:
    """All three sources consulted and agreeing — the chocolate-hoax trail's shape."""
    return {
        source: RetractionCheck(source=source, result=finding, checked_at=checked_at)
        for source in RetractionSource
    }


@pytest.fixture
def provenance() -> Provenance:
    return Provenance(
        source="openalex",
        source_url="https://api.openalex.org/works/doi:10.1136/bmj.283.6307.1671",
        accessed_at=ACCESSED,
        confidence_tier=ConfidenceTier.VERIFIED_PRIMARY,
    )


@pytest.fixture
def seeded_fact(provenance: Provenance) -> Fact:
    return Fact(
        statement=(
            "Hamblin (1981) reports that German chemists re-investigating the iron content "
            "of spinach in the 1930s showed the original workers had misplaced the decimal "
            "point and overestimated the value tenfold."
        ),
        key=SPINACH_KEY,
        tier=ConfidenceTier.VERIFIED_PRIMARY,
        provenance=[provenance],
        evidence_quality=EvidenceQuality(
            retraction=RetractionStatus.CLEAN,
            retraction_checks=three_source_agreement(RetractionFinding.CLEAN),
        ),
    )


@pytest.fixture
def fact_lookup(seeded_fact: Fact) -> InMemoryFacts:
    return InMemoryFacts([seeded_fact])


@pytest.fixture
def hand_built_graph(provenance: Provenance, seeded_fact: Fact) -> ClaimGraph:
    claim = Claim(
        text="A misplaced decimal point made spinach famous as an iron-rich food.",
        source_text="Popular nutrition column, 2019.",
    )

    p_measurement = Premise(
        text="The published iron figure for spinach was overstated by a factor of ten.",
        premise_type=PremiseType.EMPIRICAL_CITABLE,
        termination_reason=TerminationReason.GROUNDED,
        bound_key=SPINACH_KEY,
        evidence_state=EvidenceState.VERIFIED,
        evidence_state_provisional=True,
    )
    p_inflated = Premise(
        text="A widely circulated figure reported roughly ten times that amount.",
        premise_type=PremiseType.STATISTICAL,
        termination_reason=TerminationReason.CITATION_SHAPED,
        candidate_key=None,
    )
    p_decimal = Premise(
        text="A tenfold discrepancy is what a misplaced decimal point produces.",
        premise_type=PremiseType.DEFINITIONAL,
        termination_reason=TerminationReason.UNVERIFIABLE_BY_DESIGN,
    )
    # One premise is decomposed further, so the graph exercises recursion.
    p_circulated = Premise(
        text="The inflated figure appeared in widely read secondary sources.",
        premise_type=PremiseType.EMPIRICAL_CITABLE,
        termination_reason=TerminationReason.BUDGET_EXIT,
    )
    p_uncorrected = Premise(
        text="No correction to the inflated figure reached those sources.",
        premise_type=PremiseType.BACKGROUND,
        termination_reason=TerminationReason.UNVERIFIABLE_BY_DESIGN,
    )

    premises = {
        p.id: p for p in (p_measurement, p_inflated, p_decimal, p_circulated, p_uncorrected)
    }

    root_step = EntailmentStep(
        conclusion_id=claim.id,
        premise_ids=[p_measurement.id, p_inflated.id, p_decimal.id],
        depth=0,
        score=Score(
            value=0.74,
            scorer="MiniCheck-Flan-T5-Large",
            calibration=Calibration.UNCALIBRATED,
        ),
        ablation_deltas={
            p_measurement.id: AblationDelta(
                step_score=0.74,
                ablated_score=0.43,
                scorer="MiniCheck-Flan-T5-Large",
                calibration=Calibration.UNCALIBRATED,
            )
        },
    )
    nested_step = EntailmentStep(
        conclusion_id=p_inflated.id,
        premise_ids=[p_circulated.id, p_uncorrected.id],
        depth=1,
        score=Score(
            value=0.58,
            scorer="MiniCheck-Flan-T5-Large",
            calibration=Calibration.UNCALIBRATED,
        ),
    )

    bundle = EvidenceBundle(
        premise_id=p_inflated.id,
        supporting=[
            EvidenceItem(
                id="ev_support_1",
                key=CHOCOLATE_KEY,
                title="Chocolate with high cocoa content as a weight-loss accelerator",
                year=2015,
                stance=Stance.SUPPORTS,
                stance_score=Score(value=0.81, scorer="deberta-v3-large-mnli"),
                quality=EvidenceQuality(
                    retraction=RetractionStatus.RETRACTED,
                    retraction_checks=three_source_agreement(RetractionFinding.RETRACTED),
                    study_design=LabeledField[str](
                        value="Randomized Controlled Trial",
                        extraction=Extraction.STRUCTURED,
                        provenance=provenance,
                    ),
                    sample_size=LabeledField[int](
                        value=16,
                        extraction=Extraction.MODEL_EXTRACTED,
                        provenance=provenance,
                    ),
                ),
                provenance=provenance,
            )
        ],
        contradicting=[
            EvidenceItem(
                id="ev_contra_1",
                title="Reassessment of historical spinach iron figures",
                year=1981,
                stance=Stance.CONTRADICTS,
                stance_score=Score(value=0.66, scorer="deberta-v3-large-mnli"),
                provenance=provenance,
            )
        ],
        provisional_state="has-evidence",
        # M6-T2 issues the contrasting branch as a mandatory query, so the bundle records
        # both sides being asked — not just the items that came back.
        queries=[
            IssuedQuery(
                query_class=QueryClass.SUPPORTING,
                text="spinach iron content 35 mg per 100 g",
                source="openalex",
                issued_at=ACCESSED,
                returned=7,
            ),
            IssuedQuery(
                query_class=QueryClass.CONTRASTING,
                text="spinach iron figure decimal error refutation",
                source="openalex",
                issued_at=ACCESSED,
                returned=3,
            ),
        ],
        caps=[CapRecord(name="retrieval_top_k", limit=10, applied=True, dropped=4)],
        rejected_count=4,
    )

    return ClaimGraph(
        root_claim=claim,
        premises=premises,
        steps=[root_step, nested_step],
        groundings=[
            Grounding(
                premise_id=p_measurement.id,
                fact_id=seeded_fact.id,
                matched_key=SPINACH_KEY,
                grounded_at=ACCESSED,
            )
        ],
        bundles={bundle.premise_id: bundle},
        metadata=GraphMetadata(
            run_id="run_test_0001",
            config_hash="deadbeef",
            depth_budget=3,
            caps=[CapRecord(name="max_premises_per_node", limit=7, applied=False)],
            created_at=ACCESSED,
        ),
    )
