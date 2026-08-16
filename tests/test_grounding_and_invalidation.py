"""Grounding semantics and the invalidation seam.

Grounding is the one thing in the system with a pre-registered number attached
(evaluation.md §2, ≥50%), and design.md §4.2 makes it explicitly non-monotonic: "a tree
that terminated yesterday can be un-grounded today", so grounding results "must be
timestamped and re-validated, not cached as permanent."

These tests exercise that by mutating a fact and re-reading through the render boundary —
the path the M8-T2 retraction demo and the Phase-4 demo-cut both travel.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from conftest import three_source_agreement
from verity.export import graph_from_json, graph_to_json
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Grounding, Premise
from verity.models.common import (
    ConfidenceTier,
    EvidenceState,
    GroundingLiveness,
    Provenance,
    RetractionFinding,
    RetractionStatus,
    TmsStatus,
)
from verity.models.evidence import EvidenceQuality
from verity.models.fact import Fact, InMemoryFacts
from verity.models.render import to_render_payload
from verity.store.facts import SqliteFacts, save_fact
from verity.store.graphs import graphs_depending_on_fact, save_graph

RETRACTED_KEY = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
PROVENANCE = Provenance(
    source="retraction-watch",
    accessed_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
    confidence_tier=ConfidenceTier.VERIFIED_PRIMARY,
)


def _fact(**overrides) -> Fact:
    defaults = dict(
        statement="A 2015 trial reported the effect.",
        key=RETRACTED_KEY,
        tier=ConfidenceTier.VERIFIED_PRIMARY,
        provenance=[PROVENANCE],
    )
    return Fact(**{**defaults, **overrides})


def _grounded_graph(fact: Fact) -> tuple[ClaimGraph, Premise]:
    claim = Claim(text="A retracted trial supports this claim.")
    premise = Premise(
        text="A 2015 trial reported the effect.",
        bound_key=fact.key,
        evidence_state=EvidenceState.VERIFIED,
    )
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
        groundings=[Grounding(premise_id=premise.id, fact_id=fact.id, matched_key=fact.key)],
    )
    return graph, premise


# -- the tier predicate, pinned ----------------------------------------------------


def test_grounding_eligible_tiers_are_exactly_the_recorded_ruling():
    """`Fact.is_verified` decides the numerator of the ≥50% grounding rate, so which
    tiers count is a recorded decision rather than an implementation detail. This table
    is the record: changing it changes a pre-registered measurement, and the diff has to
    say so out loud.
    """
    eligible = {
        tier: Fact(
            statement="s", key=RETRACTED_KEY, tier=tier, provenance=[PROVENANCE]
        ).is_verified
        for tier in ConfidenceTier
    }
    assert eligible == {
        ConfidenceTier.VERIFIED_PRIMARY: True,
        ConfidenceTier.CORROBORATED_MULTI_SECONDARY: True,
        ConfidenceTier.SINGLE_SECONDARY: False,
        ConfidenceTier.INFERRED: False,
        ConfidenceTier.MARKETING_CLAIM: False,
    }


def test_an_out_fact_grounds_nothing_regardless_of_tier():
    for tier in (ConfidenceTier.VERIFIED_PRIMARY, ConfidenceTier.CORROBORATED_MULTI_SECONDARY):
        assert not _fact(tier=tier, status=TmsStatus.OUT).is_verified


# -- grounding must not outlive the fact it rests on -------------------------------


def test_grounding_does_not_survive_the_fact_being_retracted():
    """The Phase-4 demo-cut in one assertion: retract the fact a premise stands on, and
    the premise stops reporting itself as grounded.

    The row keeps both readings — `grounding_recorded` is what the run concluded,
    `grounded` is what the alethiology says now — because the difference between them is
    the invalidation story, not an error to hide.
    """
    fact = _fact()
    graph, _ = _grounded_graph(fact)
    facts = InMemoryFacts([fact])

    before = to_render_payload(graph, facts).premises[0]
    assert before.grounded
    assert before.grounding_status is GroundingLiveness.LIVE
    assert before.evidence_state is EvidenceState.VERIFIED

    facts.add(
        _fact(
            status=TmsStatus.OUT,
            evidence_quality=EvidenceQuality(
                retraction=RetractionStatus.RETRACTED,
                retraction_checks=three_source_agreement(RetractionFinding.RETRACTED),
            ),
        )
    )

    after = to_render_payload(graph, facts).premises[0]
    assert not after.grounded
    assert after.grounding_recorded, "the run's own record is not rewritten"
    assert after.grounding_status is GroundingLiveness.FACT_OUT
    assert after.evidence_state is EvidenceState.UNVERIFIED
    assert after.evidence_state_recorded is EvidenceState.VERIFIED
    assert after.evidence_state_diverged


def test_a_stale_grounding_is_announced_once_at_the_payload_level():
    fact = _fact()
    graph, _ = _grounded_graph(fact)

    assert not to_render_payload(graph, InMemoryFacts([fact])).has_stale_groundings
    assert to_render_payload(
        graph, InMemoryFacts([_fact(status=TmsStatus.OUT)])
    ).has_stale_groundings


def test_a_fact_demoted_below_the_eligible_tier_un_grounds_its_premise():
    """M5's promotion policy can demote as well as promote, and a demotion moves the same
    pre-registered number a retraction does."""
    fact = _fact()
    graph, _ = _grounded_graph(fact)
    demoted = _fact(id=fact.id, tier=ConfidenceTier.SINGLE_SECONDARY)

    row = to_render_payload(graph, InMemoryFacts([demoted])).premises[0]
    assert not row.grounded
    assert row.grounding_status is GroundingLiveness.FACT_INELIGIBLE_TIER


def test_a_grounding_whose_fact_is_gone_reports_it():
    """A fact removed by a dedup pass leaves the graph's row pointing at nothing. Reading
    that as "still grounded" is the failure; reading it as "not grounded" without saying
    why is barely better."""
    graph, _ = _grounded_graph(_fact())
    row = to_render_payload(graph, InMemoryFacts()).premises[0]
    assert not row.grounded
    assert row.grounding_status is GroundingLiveness.FACT_MISSING


def test_a_retracted_grounding_fact_is_flagged_on_its_premise():
    """The demo narrative ends "…and that fact's source is flagged retracted." The
    retraction here is reachable only through the alethiology — nothing retrieval
    returned — so the flag has to come from the fact the premise is grounded in."""
    fact = _fact(
        evidence_quality=EvidenceQuality(
            retraction=RetractionStatus.RETRACTED,
            retraction_checks=three_source_agreement(RetractionFinding.RETRACTED),
        )
    )
    graph, _ = _grounded_graph(fact)

    row = to_render_payload(graph, InMemoryFacts([fact])).premises[0]
    assert row.retraction_flags == ["doi:10.3823/1654: retracted"]


def test_the_render_boundary_reads_the_same_store_the_run_wrote(tmp_path):
    """The seam end to end: save, retract in the store, re-render from SQLite."""
    from verity.store.db import connect

    fact = _fact()
    graph, _ = _grounded_graph(fact)
    conn = connect(tmp_path / "seam.db")
    save_fact(conn, fact)
    save_graph(conn, graph)

    assert to_render_payload(graph, SqliteFacts(conn)).premises[0].grounded

    save_fact(conn, _fact(id=fact.id, status=TmsStatus.OUT))
    assert not to_render_payload(graph, SqliteFacts(conn)).premises[0].grounded
    conn.close()


def test_the_dependent_graph_query_backing_propagation_works(tmp_path):
    """M8-T2 and M1-T3 both need "which graphs does this fact hold up?"."""
    from verity.store.db import connect

    fact = _fact()
    graph, _ = _grounded_graph(fact)

    conn = connect(tmp_path / "propagation.db")
    save_fact(conn, fact)
    save_graph(conn, graph)

    assert graphs_depending_on_fact(conn, fact.id) == [graph.id]
    assert graphs_depending_on_fact(conn, "fact_that_does_not_exist") == []
    conn.close()


# -- `verified` is pinned to grounding, never asserted ------------------------------


def test_verified_requires_a_grounding():
    """design.md §4.2: `verified` "requires exact-key grounding in an alethiology fact
    that is IN — never derived from retrieved-evidence bundles". M8-T3's exit criterion
    ("a bundle cannot produce `verified`") needs the enum to be unassignable on its own."""
    claim = Claim(text="Root claim.")
    premise = Premise(text="Ungrounded.", evidence_state=EvidenceState.VERIFIED)

    with pytest.raises(ValidationError, match="claims `verified` with no grounding"):
        ClaimGraph(
            root_claim=claim,
            premises={premise.id: premise},
            steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
        )


def test_a_grounding_key_must_match_the_premise_it_grounds():
    """The ≥50% rate is counted off these rows. A `matched_key` agreeing with neither the
    premise's bound key nor the fact's key is a grounding that never happened."""
    other = ExternalKey(type=KeyType.DOI, value="10.1038/nature12373")
    claim = Claim(text="Root claim.")
    premise = Premise(text="p", bound_key=RETRACTED_KEY)

    with pytest.raises(ValidationError, match="does not match the bound key"):
        ClaimGraph(
            root_claim=claim,
            premises={premise.id: premise},
            steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
            groundings=[Grounding(premise_id=premise.id, fact_id="fact_x", matched_key=other)],
        )


def test_a_grounded_premise_must_carry_a_bound_key():
    claim = Claim(text="Root claim.")
    premise = Premise(text="p")

    with pytest.raises(ValidationError, match="carries no bound key"):
        ClaimGraph(
            root_claim=claim,
            premises={premise.id: premise},
            steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
            groundings=[
                Grounding(premise_id=premise.id, fact_id="fact_x", matched_key=RETRACTED_KEY)
            ],
        )


# -- grounding survives serialization ------------------------------------------------


def test_grounding_survives_the_json_round_trip():
    fact = _fact()
    graph, premise = _grounded_graph(fact)
    restored = graph_from_json(graph_to_json(graph))

    grounding = restored.grounding_for(premise.id)
    assert grounding is not None
    assert grounding.matched_key.matches(RETRACTED_KEY)
    assert grounding.grounded_at == graph.groundings[0].grounded_at
