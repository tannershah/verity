"""Structural invariants of the claim graph.

The suite's other files assert over *shape* — which fields exist, what a fixture
serializes to. These assert over *behaviour*: build a graph, traverse it, and check that
what the renderer receives matches what the graph contains. Every silent divergence
between those two is a premise a reader never sees, which is the failure mode design.md
§3.4 exists to prevent.

The graph is a DAG, and most of what is checked here is a consequence of taking that
seriously: a premise reached from two steps is one node with two rows, two scores, and two
ablation deltas, and anything that collapses them shows a number beside a premise that
belongs to a step the reader is not looking at.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verity.models.claim import Claim, ClaimGraph, EntailmentStep, GraphMetadata, Premise
from verity.models.common import AblationDelta, CapRecord, Score
from verity.models.evidence import EvidenceBundle
from verity.models.fact import InMemoryFacts
from verity.models.render import to_render_payload

NO_FACTS = InMemoryFacts()


def _shared_premise_graph() -> tuple[ClaimGraph, Premise, Premise, Premise]:
    """A diamond: both branches rest on the same premise, scored very differently."""
    claim = Claim(text="Root claim.")
    shared = Premise(text="Shared premise.")
    left = Premise(text="Left branch.")
    right = Premise(text="Right branch.")

    graph = ClaimGraph(
        root_claim=claim,
        premises={p.id: p for p in (shared, left, right)},
        steps=[
            EntailmentStep(
                conclusion_id=claim.id,
                premise_ids=[left.id, right.id],
                score=Score(value=0.90, scorer="test"),
            ),
            EntailmentStep(
                conclusion_id=left.id,
                premise_ids=[shared.id],
                score=Score(value=0.20, scorer="test"),
            ),
            EntailmentStep(
                conclusion_id=right.id,
                premise_ids=[shared.id],
                score=Score(value=0.95, scorer="test"),
            ),
        ],
    )
    return graph, shared, left, right


# -- node maps must be keyed by identity ------------------------------------------


def test_premise_map_key_must_equal_premise_id():
    """`children_of` looks premises up by id, so a mis-keyed map would drop them silently.

    Not hypothetical: any code building the map from a list comprehension over a
    different attribute produces this, and the only symptom would be a premise missing
    from the render with no error anywhere.
    """
    claim = Claim(text="Root claim.")
    premise = Premise(text="Only premise.")
    step = EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])

    with pytest.raises(ValidationError, match="does not match premise id"):
        ClaimGraph(root_claim=claim, premises={"prem_not-the-id": premise}, steps=[step])


def test_bundle_map_key_must_equal_bundle_premise_id():
    """A mis-keyed bundle would attribute one premise's evidence — retractions included —
    to another. Worse than dropping it: the reader sees evidence that is not there."""
    claim = Claim(text="Root claim.")
    premise = Premise(text="Only premise.")
    step = EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])
    stray = EvidenceBundle(premise_id="prem_someone-else", provisional_state="has-evidence")

    with pytest.raises(ValidationError, match="does not match bundle premise"):
        ClaimGraph(
            root_claim=claim,
            premises={premise.id: premise},
            steps=[step],
            bundles={premise.id: stray},
        )


def test_references_must_resolve():
    claim = Claim(text="Root claim.")
    premise = Premise(text="Only premise.")

    with pytest.raises(ValidationError, match="unknown premises"):
        ClaimGraph(
            root_claim=claim,
            premises={premise.id: premise},
            steps=[
                EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id, "prem_ghost"])
            ],
        )


def test_a_node_is_decomposed_by_at_most_one_step():
    """`step_concluding` returns one step. Two would make which one it returns arbitrary,
    and the premise rows under that node would depend on list order."""
    claim = Claim(text="Root claim.")
    a, b = Premise(text="A."), Premise(text="B.")

    with pytest.raises(ValidationError, match="more than one step"):
        ClaimGraph(
            root_claim=claim,
            premises={a.id: a, b.id: b},
            steps=[
                EntailmentStep(conclusion_id=claim.id, premise_ids=[a.id]),
                EntailmentStep(conclusion_id=claim.id, premise_ids=[b.id]),
            ],
        )


# -- traversal must not lose nodes -------------------------------------------------


def test_a_shared_premise_renders_once_per_step_it_belongs_to():
    """M5-T1 dedups facts by statement hash, so premises *will* be shared between steps.

    Each step must display every premise it rests on, and each row must carry the score of
    the step it is shown under. A node-keyed walk would visit the shared premise once and
    show it under one arbitrary step — a step whose premises vanish from the display is
    exactly the polished-tree-hiding-a-bad-step failure of design.md §3.4.
    """
    graph, shared, left, right = _shared_premise_graph()

    rows = [r for r in to_render_payload(graph, NO_FACTS).premises if r.premise_id == shared.id]
    assert len(rows) == 2, "each step must show every premise it rests on"
    assert {r.parent_id for r in rows} == {left.id, right.id}
    assert {r.step_score for r in rows} == {"0.20 (uncalibrated)", "0.95 (uncalibrated)"}


def test_steps_containing_returns_every_step_not_the_first():
    graph, shared, left, right = _shared_premise_graph()
    assert {s.conclusion_id for s in graph.steps_containing(shared.id)} == {left.id, right.id}


def test_every_premise_in_the_graph_reaches_the_payload(hand_built_graph, fact_lookup):
    rendered = {
        row.premise_id for row in to_render_payload(hand_built_graph, fact_lookup).premises
    }
    assert rendered == set(hand_built_graph.premises)


def test_an_unreachable_premise_is_refused_rather_than_hidden():
    """A beam cap that drops a parent orphans its children. Keeping them in the map and
    out of the render is the silent version; the map and the display must agree."""
    claim = Claim(text="Root claim.")
    attached = Premise(text="Attached.")
    orphan = Premise(text="Orphaned by a cap.")

    with pytest.raises(ValidationError, match="unreachable from the root"):
        ClaimGraph(
            root_claim=claim,
            premises={attached.id: attached, orphan.id: orphan},
            steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[attached.id])],
        )


def test_build_prunes_orphans_and_reports_what_it_dropped():
    """evaluation.md §6: no silent caps. A producer that orphaned a subtree gets a legal
    path — prune it and say how much — rather than a crash or a vanishing."""
    claim = Claim(text="Root claim.")
    attached = Premise(text="Attached.")
    orphan = Premise(text="Orphaned by a cap.")

    graph, caps = ClaimGraph.build(
        root_claim=claim,
        premises={attached.id: attached, orphan.id: orphan},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[attached.id])],
    )

    assert set(graph.premises) == {attached.id}
    assert [(c.name, c.applied, c.dropped) for c in caps] == [
        ("unreachable_premises_pruned", True, 1)
    ]


def test_reported_max_depth_matches_what_rendered(hand_built_graph, fact_lookup):
    """M10-T1 reports mean/max depth. The metric and the display read the same traversal,
    so they cannot disagree about which nodes exist."""
    payload = to_render_payload(hand_built_graph, fact_lookup)
    assert payload.max_depth == max(r.depth for r in payload.premises)
    assert payload.max_depth == hand_built_graph.max_depth() == 2


def test_cycles_are_rejected_at_construction():
    """A cycle makes `leaves()` return nothing, which zeroes M10-T1's grounding-rate
    denominator, and JTMS well-foundedness (Doyle 1979's odd loops) is precisely this
    condition."""
    claim = Claim(text="Root claim.")
    a, b = Premise(text="A."), Premise(text="B.")

    with pytest.raises(ValidationError, match="entailment cycle"):
        ClaimGraph(
            root_claim=claim,
            premises={a.id: a, b.id: b},
            steps=[
                EntailmentStep(conclusion_id=claim.id, premise_ids=[a.id]),
                EntailmentStep(conclusion_id=a.id, premise_ids=[b.id]),
                EntailmentStep(conclusion_id=b.id, premise_ids=[a.id]),
            ],
        )


# -- depth is derived, so it cannot disagree with the structure ---------------------


def test_depth_is_not_a_field_anyone_can_write():
    """Depth feeds the budget-exit rate and the termination-reason mix. Stored on the
    node it would be whatever the decomposer happened to write — and wrong by
    construction for a premise reached from two different depths."""
    assert "depth" not in Premise.model_fields


def test_depth_is_the_shortest_path_from_the_root():
    claim = Claim(text="Root claim.")
    mid = Premise(text="Middle.")
    deep = Premise(text="Deep.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={mid.id: mid, deep.id: deep},
        steps=[
            EntailmentStep(conclusion_id=claim.id, premise_ids=[mid.id]),
            EntailmentStep(conclusion_id=mid.id, premise_ids=[deep.id]),
        ],
    )
    assert graph.depth_of(mid.id) == 1
    assert graph.depth_of(deep.id) == 2
    assert graph.max_depth() == 2


def test_traversal_depth_and_descent_depth_are_different_numbers():
    """A premise reached from two places is reachable by the shorter route, so the graph's
    own shape understates what the decomposer spent — and the budget is spent along the
    descent. Here root→A→B→C costs three descents while B stays one hop from the root, so
    a traversal reports 2 for a branch the budget charged 3 for.

    Reporting max depth off the shortened graph while `budget-exit` fires along the
    descent would put two of M10-T1's metrics over two different objects. Both numbers are
    kept, and each has an owner.
    """
    claim = Claim(text="Root claim.")
    a, b, c = Premise(text="A."), Premise(text="B."), Premise(text="C.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={p.id: p for p in (a, b, c)},
        steps=[
            EntailmentStep(conclusion_id=claim.id, premise_ids=[a.id, b.id], depth=0),
            EntailmentStep(conclusion_id=a.id, premise_ids=[b.id], depth=1),
            EntailmentStep(conclusion_id=b.id, premise_ids=[c.id], depth=2),
        ],
    )

    assert graph.max_depth() == 2, "the graph as it stands is two hops deep"
    assert graph.recorded_depth() == 3, "the decomposer descended three times to reach C"


def test_descent_depth_is_absent_rather_than_guessed():
    """Nothing infers a descent depth from the shape. A graph whose producer did not
    record one reports that, instead of handing M10-T1 a traversal number wearing the
    budget metric's name."""
    claim = Claim(text="Root claim.")
    premise = Premise(text="Only premise.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
    )
    assert graph.max_depth() == 1
    assert graph.recorded_depth() is None


def test_descent_depth_is_recorded_on_every_step_or_none():
    """A max over half the descent is not a shallower measurement — it is a different
    graph's measurement."""
    claim = Claim(text="Root claim.")
    a, b = Premise(text="A."), Premise(text="B.")

    with pytest.raises(ValidationError, match="on every step or on none"):
        ClaimGraph(
            root_claim=claim,
            premises={a.id: a, b.id: b},
            steps=[
                EntailmentStep(conclusion_id=claim.id, premise_ids=[a.id], depth=0),
                EntailmentStep(conclusion_id=a.id, premise_ids=[b.id]),
            ],
        )


def test_a_shared_premise_carries_the_depth_of_the_edge_it_renders_under():
    """The diamond's shared premise is at depth 2 under both branches; a premise reached
    at two different depths reports each one on its own row."""
    claim = Claim(text="Root claim.")
    shallow = Premise(text="Shallow parent.")
    mid = Premise(text="Middle.")
    shared = Premise(text="Shared.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={p.id: p for p in (shallow, mid, shared)},
        steps=[
            EntailmentStep(conclusion_id=claim.id, premise_ids=[shallow.id, mid.id]),
            EntailmentStep(conclusion_id=shallow.id, premise_ids=[shared.id]),
            EntailmentStep(conclusion_id=mid.id, premise_ids=[shared.id]),
        ],
    )
    depths = {e.depth for e in graph.walk() if e.premise_id == shared.id}
    assert depths == {2}


# -- step identity and arity --------------------------------------------------------


def test_step_identity_is_the_set_of_premises_not_their_order():
    """`Justification` sorts its antecedents before hashing and `EntailmentStep` does the
    same. The same decomposition emitted in a different order is the same node — a cache
    hit for M1-T2 rather than a duplicate step for M4-T2's ablation."""
    a, b = "prem_aaaaaaaa", "prem_bbbbbbbb"
    assert (
        EntailmentStep(conclusion_id="claim_x", premise_ids=[a, b]).id
        == EntailmentStep(conclusion_id="claim_x", premise_ids=[b, a]).id
    )


def test_step_identity_still_separates_different_premise_sets():
    a, b, c = "prem_aaaaaaaa", "prem_bbbbbbbb", "prem_cccccccc"
    assert (
        EntailmentStep(conclusion_id="claim_x", premise_ids=[a, b]).id
        != EntailmentStep(conclusion_id="claim_x", premise_ids=[a, c]).id
    )


def test_a_step_cannot_list_the_same_premise_twice():
    """Leave-one-out ablation over a step containing a premise twice removes one copy
    and measures nothing."""
    with pytest.raises(ValidationError, match="more than once"):
        EntailmentStep(conclusion_id="claim_x", premise_ids=["prem_a", "prem_a"])


def test_a_step_with_no_premises_is_refused():
    with pytest.raises(ValidationError, match="entails nothing"):
        EntailmentStep(conclusion_id="claim_x", premise_ids=[])


def test_an_out_of_range_arity_is_recorded_rather_than_refused():
    """3-7 premises is a `DecompositionConfig` value, not a type constraint — a model
    returning eight must not crash the pipeline, and M10-T1 reads `arity` to report the
    distribution. Truncating *to* the range is what needs a `CapRecord`, and that is
    M3-T1's to emit."""
    step = EntailmentStep(conclusion_id="claim_x", premise_ids=[f"prem_{i}" for i in range(9)])
    assert step.arity == 9


# -- ablation is a property of a step, not of a premise ------------------------------


def test_a_shared_premise_carries_one_ablation_delta_per_step():
    """M4-T2 re-scores *each step* with each premise removed, so a premise in two steps
    has two deltas. Held on the premise, the second would overwrite the first and the
    displayed delta would silently belong to whichever step ran last."""
    claim = Claim(text="Root claim.")
    shared = Premise(text="Shared premise.")
    left = Premise(text="Left branch.")
    right = Premise(text="Right branch.")

    left_step = EntailmentStep(
        conclusion_id=left.id,
        premise_ids=[shared.id],
        score=Score(value=0.20, scorer="test"),
        ablation_deltas={
            shared.id: AblationDelta(step_score=0.20, ablated_score=0.18, scorer="test")
        },
    )
    right_step = EntailmentStep(
        conclusion_id=right.id,
        premise_ids=[shared.id],
        score=Score(value=0.95, scorer="test"),
        ablation_deltas={
            shared.id: AblationDelta(step_score=0.95, ablated_score=0.10, scorer="test")
        },
    )
    graph = ClaimGraph(
        root_claim=claim,
        premises={p.id: p for p in (shared, left, right)},
        steps=[
            EntailmentStep(conclusion_id=claim.id, premise_ids=[left.id, right.id]),
            left_step,
            right_step,
        ],
    )

    rows = [r for r in to_render_payload(graph, NO_FACTS).premises if r.premise_id == shared.id]
    assert {round(r.ablation_delta_value, 2) for r in rows} == {0.02, 0.85}


def test_ablation_deltas_must_belong_to_the_step_that_holds_them():
    with pytest.raises(ValidationError, match="not in this step"):
        EntailmentStep(
            conclusion_id="claim_x",
            premise_ids=["prem_a"],
            ablation_deltas={
                "prem_b": AblationDelta(step_score=0.5, ablated_score=0.1, scorer="test")
            },
        )


def test_an_ablation_delta_can_be_negative():
    """Removing a premise can raise a step's score. A type constrained to probabilities
    could not say so, which is why this is not a `Score`."""
    delta = AblationDelta(step_score=0.40, ablated_score=0.65, scorer="test")
    assert delta.delta == pytest.approx(-0.25)
    assert delta.label() == "-0.25 (uncalibrated)"


# -- caps ------------------------------------------------------------------------


def test_metadata_caps_reach_the_payload(fact_lookup):
    claim = Claim(text="Root claim.")
    premise = Premise(text="Only premise.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
        metadata=GraphMetadata(
            caps=[CapRecord(name="max_nodes_per_tree", limit=1, applied=True, dropped=1)]
        ),
    )
    assert [c.name for c in to_render_payload(graph, fact_lookup).caps] == [
        "max_nodes_per_tree"
    ]
