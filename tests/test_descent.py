"""M3-T2: the recursive descent — what it expands, why each branch stopped, what it cost.

The tier's claim is not "recursion happens". It is that **every leaf says why it is a leaf**,
that the reason is a function of the configured predicate rather than of traversal order,
and that a branch which fails takes only itself down. Most of this file is those three.

No network. The stub is scripted by a callable over the request, which is the only form
that works for a descent: every call carries the same `purpose`, so the discriminator has
to be the conclusion the prompt names.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from verity.config import DecompositionConfig
from verity.decomposition import (
    CyclicPremiseError,
    DecompositionContext,
    DecompositionError,
    DepthBudgetExceededError,
    EmptyDecompositionError,
    ProposedDecomposition,
    ProposedPremise,
    assemble_graph,
    decompose_claim,
    decompose_step,
)
from verity.decomposition.descent import NODE_CAP, RESTATES_ROOT, terminal_reason
from verity.export import graph_to_json
from verity.llm.base import LLMError, LLMRefusalError, LLMRequest
from verity.llm.cassette import CassetteMiss
from verity.llm.stub import StubAdapter
from verity.models.claim import Claim, ClaimGraph, Premise
from verity.models.common import PremiseType, TerminationReason
from verity.models.manifest import Usage

FIXED = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
CONFIG = DecompositionConfig()
WIDENED = DecompositionConfig(
    recurse_on=(PremiseType.STATISTICAL, PremiseType.EMPIRICAL_CITABLE)
)
CLAIM = Claim(
    text="A misplaced decimal point made spinach famous as an iron-rich food.",
    source_text="Popular nutrition column.",
    created_at=FIXED,
)

_TARGET = re.compile(r"<target-([0-9a-f]+)>\n(.*?)\n</target-\1>", re.S)


def _p(
    text: str, kind: PremiseType = PremiseType.EMPIRICAL_CITABLE, key: str | None = None
) -> ProposedPremise:
    return ProposedPremise(text=text, premise_type=kind, candidate_key=key)


def _d(*premises: ProposedPremise) -> ProposedDecomposition:
    return ProposedDecomposition(premises=list(premises))


def target_of(request: LLMRequest) -> str:
    """The statement this call was asked to decompose, read out of its own prompt."""
    match = _TARGET.search(request.prompt)
    assert match is not None, "every decomposition prompt delimits its target"
    return match.group(2)


class Scripted(StubAdapter):
    """Answers by target statement, and refuses to answer a node nobody scripted.

    Keyed on the conclusion rather than on call index, so an assertion never depends on the
    order the descent happened to expand in. An unscripted target raises instead of falling
    back, because a descent that reached a node the test did not anticipate is the thing
    worth failing on.
    """

    def __init__(self, script: dict[str, ProposedDecomposition | Exception], **kwargs):
        from verity.decomposition.backward_chain import PURPOSE

        def answer(request: LLMRequest) -> ProposedDecomposition:
            target = target_of(request)
            if target not in script:
                raise AssertionError(f"the descent reached an unscripted target: {target!r}")
            answer = script[target]
            if isinstance(answer, Exception):
                raise answer
            return answer

        super().__init__(structured={PURPOSE: answer}, **kwargs)
        self.asked: list[str] = []

    def structured(self, request, schema):
        self.asked.append(target_of(request))
        return super().structured(request, schema)


class Costed(Scripted):
    """A stub whose every call costs something, so refused branches are visibly counted."""

    def _envelope(self, request, text: str = "", raw_output: str | None = None):
        envelope = super()._envelope(request, text, raw_output)
        return envelope.model_copy(
            update={"usage": Usage(input_tokens=100, output_tokens=10, cost_usd=0.01)}
        )


# A three-level descent: one statistical premise per level is the recursion candidate, and
# everything else terminates on its own type.
ROOT = "The published iron figure for spinach was overstated tenfold."
MID = "A reported value ten times the correct one is a decimal shifted one place."
DEEP = "Two published values for one quantity differ by exactly a factor of ten."

TREE: dict[str, ProposedDecomposition | Exception] = {
    CLAIM.text: _d(
        _p(MID, PremiseType.STATISTICAL),
        _p("Modern tables give spinach iron as 2.7 mg per 100 g."),
        _p("A decimal point separates units from tenths.", PremiseType.DEFINITIONAL),
    ),
    MID: _d(
        _p(DEEP, PremiseType.STATISTICAL),
        _p("Nutrition textbooks repeated the higher figure.", PremiseType.BACKGROUND),
    ),
    DEEP: _d(
        _p("One of the two values was transcribed.", PremiseType.STATISTICAL),
        _p("Nineteenth-century analyses reported 35 mg per 100 g."),
    ),
}


def _descend(script=None, *, config: DecompositionConfig = CONFIG, adapter=None, claim=CLAIM):
    adapter = adapter or Scripted(script if script is not None else TREE)
    outcome = decompose_claim(claim, adapter=adapter, config=config, now=FIXED)
    return outcome, adapter


def _graph(outcome, *, config: DecompositionConfig = CONFIG, claim=CLAIM) -> ClaimGraph:
    return assemble_graph(
        claim,
        outcome.steps,
        config=config,
        terminations=outcome.terminations,
        caps=outcome.caps,
        now=FIXED,
    )


def _mix(graph: ClaimGraph) -> dict[TerminationReason, int]:
    mix: dict[TerminationReason, int] = {}
    for premise in graph.leaves():
        assert premise.termination_reason is not None
        mix[premise.termination_reason] = mix.get(premise.termination_reason, 0) + 1
    return mix


# -- the predicate decides the shape, and it is recorded -------------------------------


def test_the_descent_expands_what_the_predicate_names_and_nothing_else():
    outcome, adapter = _descend()
    graph = _graph(outcome)

    assert adapter.asked == [CLAIM.text, MID, DEEP], "breadth-first, in proposal order"
    assert outcome.expanded == 3
    assert graph.recorded_depth() == 3 == graph.metadata.depth_budget
    assert _mix(graph) == {
        TerminationReason.CITATION_SHAPED: 2,
        TerminationReason.UNVERIFIABLE_BY_DESIGN: 2,
        TerminationReason.BUDGET_EXIT: 1,
    }


def test_widening_the_predicate_changes_what_the_buckets_mean():
    """The two mixes are not one metric at two settings. Under a predicate containing
    `empirical-citable` that type is expandable, so `citation-shaped` cannot occur at all
    and premises that stop do so on depth — which is why the predicate travels in
    `config_hash()` and a mix is only readable against the run that recorded it."""
    script = {
        CLAIM.text: _d(_p("Modern tables give spinach iron as 2.7 mg per 100 g.")),
        "Modern tables give spinach iron as 2.7 mg per 100 g.": _d(
            _p("The USDA publishes a food-composition table.")
        ),
        "The USDA publishes a food-composition table.": _d(_p("The table lists spinach.")),
    }
    narrow, _ = _descend(script, config=CONFIG)
    wide, _ = _descend(script, config=WIDENED)

    assert _mix(_graph(narrow)) == {TerminationReason.CITATION_SHAPED: 1}
    assert narrow.expanded == 1

    wide_mix = _mix(_graph(wide, config=WIDENED))
    assert TerminationReason.CITATION_SHAPED not in wide_mix
    assert wide_mix == {TerminationReason.BUDGET_EXIT: 1}
    assert wide.expanded == 3


def test_a_premise_the_predicate_would_not_expand_records_its_own_reason_at_the_budget():
    """`budget-exit` is reserved for a branch the budget actually cut short. A citable
    premise sitting at the deepest level would have terminated under an infinite budget, so
    recording `budget-exit` there would make the published rate measure tree width."""
    outcome, _ = _descend(config=DecompositionConfig(depth_budget=2))
    graph = _graph(outcome, config=DecompositionConfig(depth_budget=2))

    deepest = {
        graph.premises[edge.premise_id].termination_reason
        for edge in graph.walk()
        if edge.depth == 2
    }
    assert deepest == {
        TerminationReason.BUDGET_EXIT,  # the statistical premise, which we would have expanded
        TerminationReason.UNVERIFIABLE_BY_DESIGN,  # the background one, which we would not
    }


def test_a_depth_budget_of_one_reproduces_a_single_step():
    """The descent degenerates to M3-T1 rather than behaving differently at the boundary."""
    outcome, adapter = _descend(config=DecompositionConfig(depth_budget=1))
    graph = _graph(outcome, config=DecompositionConfig(depth_budget=1))

    assert adapter.asked == [CLAIM.text]
    assert len(graph.steps) == 1 and graph.recorded_depth() == 1
    assert _mix(graph) == {
        TerminationReason.BUDGET_EXIT: 1,
        TerminationReason.CITATION_SHAPED: 1,
        TerminationReason.UNVERIFIABLE_BY_DESIGN: 1,
    }


def test_a_depth_budget_of_zero_refuses_before_spending_anything():
    adapter = Scripted(TREE)
    with pytest.raises(DepthBudgetExceededError) as refusal:
        decompose_claim(
            CLAIM, adapter=adapter, config=DecompositionConfig(depth_budget=0), now=FIXED
        )
    assert not adapter.asked
    assert refusal.value.usage is None, "no call was made, which is not a call costing zero"


def test_grounded_is_never_emitted_by_a_descent():
    """Nothing is bound while the descent runs, and the only key available is the one the
    decomposer proposed — which the binder records as circular evidence. A `grounded`
    terminal here would put that circularity into the mix M10-T1 reports."""
    keyed = {
        CLAIM.text: _d(_p("Spinach iron is 2.7 mg/100 g.", key="https://doi.org/10.3823/1654"))
    }
    outcome, _ = _descend(keyed)
    graph = _graph(outcome)

    (premise,) = graph.premises.values()
    assert premise.candidate_key is not None and premise.bound_key is None
    assert TerminationReason.GROUNDED not in _mix(graph)
    assert not any(r is TerminationReason.GROUNDED for r in outcome.terminations.values())


def test_configuration_cannot_write_an_epistemic_terminal_it_has_no_standing_to_write():
    """`citation-shaped` is consumed as a claim about the premise — `applicability` reads it
    as "a source could settle this" when partitioning the grounding denominators — so it is
    written by the type and never by the predicate. A knob that could name an arithmetic
    premise citable would put its own decision into a pre-registered denominator.

    The predicate therefore cannot decline a type that carries no terminal of its own: the
    configuration is refused, rather than the descent inventing a label at classification
    time. Declining to descend at all is `depth_budget=1`, which says so directly.
    """
    from verity.models.common import INTRINSIC_TERMINALS

    for kind, reason in INTRINSIC_TERMINALS.items():
        assert (
            terminal_reason(
                Premise(text=f"A {kind.value} premise.", premise_type=kind),
                restating=False,
                config=DecompositionConfig(recurse_on=(PremiseType.STATISTICAL,)),
            )
            is reason
        ), "a declined type falls back to the terminal its own meaning carries"

    for predicate in ((), (PremiseType.EMPIRICAL_CITABLE,)):
        with pytest.raises(ValidationError, match="carry no terminal of their own"):
            DecompositionConfig(recurse_on=predicate)


def test_an_untyped_premise_is_a_producer_defect_and_not_a_policy_question():
    """The wire schema requires a type, so this cannot arise through `_materialize`. It
    raises a `ValueError` rather than a `DecompositionError` deliberately: the stage
    isolates the latter, and a producer bug must not read as "the decomposer refused"."""

    with pytest.raises(ValueError, match="no premise type"):
        terminal_reason(Premise(text="Untyped."), restating=False, config=CONFIG)


# -- every leaf says why, and no decomposed node does -----------------------------------


def test_every_terminal_carries_exactly_one_reason_and_expanded_nodes_carry_none():
    outcome, _ = _descend()
    graph = _graph(outcome)

    expanded = {s.conclusion_id for s in graph.steps} - {CLAIM.id}
    assert expanded and set(outcome.terminations).isdisjoint(expanded)
    assert set(outcome.terminations) == {p.id for p in graph.leaves()}
    assert all(graph.premises[pid].termination_reason is None for pid in expanded)


def test_the_termination_mix_and_budget_exit_rate_survive_a_round_trip():
    """M10-T1 reads these off a stored graph, so they have to survive serialization."""
    graph = _graph(_descend()[0])
    reloaded = ClaimGraph.model_validate_json(graph_to_json(graph))

    leaves = reloaded.leaves()
    rate = sum(
        1 for p in leaves if p.termination_reason is TerminationReason.BUDGET_EXIT
    ) / len(leaves)
    assert rate == pytest.approx(0.2)
    assert reloaded.recorded_depth() == reloaded.metadata.depth_budget


# -- cycles are refused inside the descent, before the subtree is paid for --------------


def test_a_cycle_closed_across_two_branches_is_refused_where_it_is_created():
    """Neither branch has the other on its path, so a path-only check accepts both and the
    cycle surfaces in `ClaimGraph` after every call in the tree has been paid for. The
    guard is reachability: adding `C → P` closes a cycle exactly when P is upstream of C."""
    a, b = "Statement A holds.", "Statement B holds."
    outcome, adapter = _descend(
        {
            CLAIM.text: _d(_p(a, PremiseType.STATISTICAL), _p(b, PremiseType.STATISTICAL)),
            a: _d(_p(b, PremiseType.STATISTICAL), _p("Something else entirely.")),
            b: _d(_p(a, PremiseType.STATISTICAL), _p("Another thing.")),
        }
    )
    graph = _graph(outcome)

    assert adapter.asked == [CLAIM.text, a, b], "both branches were attempted"
    assert outcome.counts["refused:cyclic"] == 1
    assert graph.premises[Premise(text=b).id].termination_reason is (
        TerminationReason.DECOMPOSITION_REFUSED
    )
    assert graph.step_concluding(Premise(text=a).id) is not None, "the other branch survives"


def test_the_upstream_guard_refuses_what_a_path_check_would_admit():
    """The mechanism on its own: a conclusion with no ancestors on its path still refuses a
    premise reproducing a node it is reachable from."""
    conclusion = Premise(text="Statement B holds.")
    with pytest.raises(CyclicPremiseError):
        decompose_step(
            conclusion,
            adapter=StubAdapter(
                structured={
                    "decompose:step": _d(_p("Statement A holds.", PremiseType.STATISTICAL))
                }
            ),
            config=CONFIG,
            depth=1,
            context=DecompositionContext(
                root_claim=CLAIM,
                ancestors=(),
                upstream_statements=frozenset({"statement a holds."}),
            ),
            now=FIXED,
        )


def test_a_unicode_variant_of_an_ancestor_still_closes_a_cycle_two_levels_down():
    """Identity is the statement, and `normalize_text` is where this codebase draws that
    line — so a decomposed spelling of an ancestor is the ancestor, however deep."""
    mid = "Iron content in spinach purée is 2.7 mg per 100 g."
    assert unicodedata.normalize("NFD", mid) != mid, "fixture must actually decompose"

    outcome, _ = _descend(
        {
            CLAIM.text: _d(_p(mid, PremiseType.STATISTICAL)),
            mid: _d(_p("A second level.", PremiseType.STATISTICAL)),
            "A second level.": _d(_p(unicodedata.normalize("NFD", mid))),
        }
    )
    assert outcome.counts["refused:cyclic"] == 1
    graph = _graph(outcome)
    assert graph.premises[Premise(text="A second level.").id].termination_reason is (
        TerminationReason.DECOMPOSITION_REFUSED
    )


# -- a branch that fails takes only itself down -----------------------------------------


def test_a_refusal_below_the_root_terminates_its_branch_and_the_call_is_still_counted():
    # Costed, so the refused call's usage is visible: the stub's default envelope is free,
    # and a total that cannot tell a refused call from no call at all proves nothing.
    outcome, _ = _descend(adapter=Costed({CLAIM.text: TREE[CLAIM.text], MID: _d()}))
    graph = _graph(outcome)

    assert outcome.calls == 2 and outcome.expanded == 1
    assert outcome.usage.cost_usd == pytest.approx(0.02), (
        "a descent that refuses a branch and reports only what it kept under-reports itself"
    )
    assert outcome.counts["refused:empty"] == 1
    assert graph.premises[Premise(text=MID).id].termination_reason is (
        TerminationReason.DECOMPOSITION_REFUSED
    )
    assert any("1 branch(es) were not decomposed (1 empty)" in n for n in outcome.notes)


def test_a_refusal_at_the_root_propagates_because_there_is_no_graph_without_it():
    with pytest.raises(EmptyDecompositionError) as refusal:
        _descend({CLAIM.text: _d()})
    assert refusal.value.usage is not None, "the call that produced it was paid for"


def test_every_branch_of_the_root_step_refusing_still_yields_a_graph():
    a, b = "Statement A holds.", "Statement B holds."
    outcome, _ = _descend(
        {
            CLAIM.text: _d(_p(a, PremiseType.STATISTICAL), _p(b, PremiseType.STATISTICAL)),
            a: _d(),
            b: _d(),
        }
    )
    graph = _graph(outcome)

    assert len(graph.steps) == 1 and len(graph.premises) == 2
    assert _mix(graph) == {TerminationReason.DECOMPOSITION_REFUSED: 2}
    assert outcome.counts["refused:empty"] == 2


def test_a_provider_refusal_isolates_per_node_and_every_other_llm_error_propagates():
    """A safety refusal is the most per-premise fact a provider emits, and the cassette
    records refusals — so propagating one would make a single premise permanently
    un-runnable, deterministically and for free. An auth failure or a cassette miss will
    recur on the next call, so a partial tree of failure-leaves is worse than a re-run."""
    refused, _ = _descend({CLAIM.text: TREE[CLAIM.text], MID: LLMRefusalError("declined")})
    graph = _graph(refused)
    assert refused.counts["refused:provider-refusal"] == 1
    assert graph.premises[Premise(text=MID).id].termination_reason is (
        TerminationReason.DECOMPOSITION_REFUSED
    )

    for error in (LLMError("no credentials"), CassetteMiss("nothing recorded")):
        with pytest.raises(type(error)):
            _descend({CLAIM.text: TREE[CLAIM.text], MID: error})


def test_a_premise_restating_the_root_claim_is_kept_flagged_and_never_expanded():
    """Expanding it would spend budget re-deriving the claim, and — because its prompt is
    byte-identical to the root's — would be served the root's own recorded answer. It is
    `decomposition-refused` because the descent refused before calling, and the restatement
    partition stays recoverable from the graph alone."""
    outcome, adapter = _descend(
        {CLAIM.text: _d(_p(CLAIM.text, PremiseType.STATISTICAL), _p("Something else."))}
    )
    graph = _graph(outcome)

    assert adapter.asked == [CLAIM.text], "the restatement was never decomposed"
    assert outcome.counts[f"refused:{RESTATES_ROOT}"] == 1
    echo = graph.premises[Premise(text=CLAIM.text).id]
    assert echo.termination_reason is TerminationReason.DECOMPOSITION_REFUSED
    refused = [
        pid
        for pid, p in graph.premises.items()
        if p.termination_reason is TerminationReason.DECOMPOSITION_REFUSED
    ]
    assert refused == graph.restating_premise_ids(), "partitionable without the manifest"


def test_a_root_restating_premise_would_have_been_served_the_roots_own_prompt():
    """Pinned rather than merely avoided. `render_user` omits the `<claim-…>` block when the
    conclusion is the root claim, and a depth-1 premise has no premise ancestors — so the
    two prompts are byte-identical and the cassette, which keys on the prompt, would answer
    the restatement with the root's own decomposition. Relaxing the no-expand rule without
    noticing this would duplicate the tree at zero marginal cost."""
    from verity.decomposition import prompt as prompt_module

    root_turn = prompt_module.render_user(
        CLAIM.text, root_claim_text=CLAIM.text, source_text=CLAIM.source_text
    )
    echo_turn = prompt_module.render_user(
        CLAIM.text, root_claim_text=CLAIM.text, source_text=CLAIM.source_text, ancestors=()
    )
    assert root_turn == echo_turn


# -- caps report what they did, and never quietly drop a premise -------------------------


def test_the_node_cap_stops_the_descent_and_reports_without_claiming_a_drop():
    capped = DecompositionConfig(depth_budget=3, max_nodes_per_tree=3)
    outcome, adapter = _descend(config=capped)
    graph = _graph(outcome, config=capped)

    assert adapter.asked == [CLAIM.text], "the cap is checked before the call, not after"
    (cap,) = graph.metadata.caps
    assert cap.name == NODE_CAP and cap.applied and cap.limit == 3
    assert cap.dropped == "uncounted", (
        "nothing was removed from the artifact; the subtrees this stopped were never built"
    )
    assert outcome.counts["terminal:cap-exit"] == 1
    assert sum(
        1 for p in graph.leaves() if p.termination_reason is TerminationReason.CAP_EXIT
    ) == 1, "the count the cap cannot carry is recoverable from the graph"


def test_the_cap_may_overshoot_its_limit_and_drops_no_premise_from_any_step():
    """Checking before expanding means the expansion that crosses the line runs to
    completion, so a graph can carry `limit=1, applied=True` and hold three premises. That
    is the honest trade: truncating a step would destroy the joint sufficiency M4 scores."""
    capped = DecompositionConfig(depth_budget=3, max_nodes_per_tree=1)
    outcome, _ = _descend(config=capped)
    graph = _graph(outcome, config=capped)

    assert len(graph.premises) == 3 > capped.max_nodes_per_tree
    for step in graph.steps:
        assert set(step.premise_ids) <= set(graph.premises)
    assert [s.arity for s in graph.steps] == [3]


def test_the_root_is_never_capped_because_a_cap_that_refuses_it_yields_no_graph():
    zero = DecompositionConfig(depth_budget=3, max_nodes_per_tree=0)
    outcome, adapter = _descend(config=zero)
    graph = _graph(outcome, config=zero)

    assert adapter.asked == [CLAIM.text]
    assert len(graph.premises) == 3
    assert _mix(graph)[TerminationReason.CAP_EXIT] == 1


# -- the DAG, and determinism over it ----------------------------------------------------


def test_a_premise_two_branches_reach_is_expanded_once_at_its_shallowest_depth():
    """BFS creates premises in non-decreasing depth order, so the first reach is the
    shallowest and a classification never has to be revised. Depth-first would classify this
    node at depth 2 and then meet it again at depth 1, with the recorded reason wrong."""
    shared, other = "A shared statement.", "A branch statement."
    outcome, adapter = _descend(
        {
            CLAIM.text: _d(
                _p(other, PremiseType.STATISTICAL), _p(shared, PremiseType.STATISTICAL)
            ),
            other: _d(_p(shared, PremiseType.STATISTICAL), _p("Filler.")),
            shared: _d(_p("A leaf under the shared node.")),
        }
    )
    graph = _graph(outcome)

    assert adapter.asked.count(shared) == 1
    shared_id = Premise(text=shared).id
    assert graph.step_concluding(shared_id).depth == 1, "expanded at the depth it was reached"
    assert graph.depth_of(shared_id) == 1
    assert len(graph.steps_containing(shared_id)) == 2, "a diamond, and still one node"


def test_a_shared_node_is_asked_with_the_chain_of_the_branch_that_reached_it_first():
    """The ancestor chain reaches the prompt and therefore the cassette key. Nothing else
    pins it, so a change in traversal order would surface as a replay miss rather than as a
    visible defect."""
    shared, first = "A shared statement.", "The first branch."
    _, adapter = _descend(
        {
            CLAIM.text: _d(
                _p(first, PremiseType.STATISTICAL), _p("Second.", PremiseType.STATISTICAL)
            ),
            first: _d(_p(shared, PremiseType.STATISTICAL), _p("Filler.")),
            "Second.": _d(_p(shared, PremiseType.STATISTICAL), _p("More filler.")),
            shared: _d(_p("A leaf.")),
        }
    )
    (call,) = [c for c in adapter.calls if target_of(c) == shared]
    assert "<established-" in call.prompt and first in call.prompt
    assert "Second." not in call.prompt, "the chain is the branch that reached it first"


def test_two_identical_descents_export_identical_bytes_and_ask_in_the_same_order():
    first, first_adapter = _descend()
    second, second_adapter = _descend()

    assert first_adapter.asked == second_adapter.asked
    assert graph_to_json(_graph(first)) == graph_to_json(_graph(second))
    assert first.counts == second.counts


# -- what the committed pilots say this will do -------------------------------------------


def test_the_committed_pilots_record_the_fan_out_the_default_predicate_produces():
    """A recorded measurement of the M3-T1 decomposer, not a target.

    Across the five pilot decompositions the type mix is 23 empirical-citable, 5
    definitional, 2 background, 1 statistical — so the default predicate expands one premise
    in thirty-one and four of the five claims produce a depth-1 tree. That is a fact about
    the decomposer rather than about this loop: the prompt steers toward citable premises,
    and the typing guidance is the lever on tree depth. Pinned so a re-recorded pilot set
    has to restate the number rather than move it silently.
    """
    import json
    from pathlib import Path


    expandable = terminals = 0
    for path in sorted(Path("data/verifier/pilot").glob("*.json")):
        graph = ClaimGraph.model_validate(json.loads(path.read_text(encoding="utf-8")))
        for premise in graph.premises.values():
            terminals += 1
            if terminal_reason(premise, restating=False, config=CONFIG) is None:
                expandable += 1

    assert (expandable, terminals) == (1, 31)
    widened = sum(
        1
        for path in sorted(Path("data/verifier/pilot").glob("*.json"))
        for premise in ClaimGraph.model_validate(
            json.loads(path.read_text(encoding="utf-8"))
        ).premises.values()
        if terminal_reason(premise, restating=False, config=WIDENED) is None
    )
    assert widened == 24, "the widened predicate is what a deeper demo tree costs"


# -- the assembly contract ----------------------------------------------------------------


def test_an_epistemic_reason_must_describe_the_premise_the_graph_will_store():
    """The descent classifies against the step that first proposed a premise, and the merge
    keeps the first-seen annotation — they agree only because both read one list in one
    order. That coupling is invisible, and a plausible edit (sorting steps for determinism)
    would break it by storing a premise typed `empirical-citable` under a reason saying
    nothing could cite it. Checked at assembly, where it is a property of the result rather
    than of the traversal.
    """
    outcome, _ = _descend()
    reversed_steps = list(reversed(outcome.steps))

    # Unchanged order still assembles: the check is on agreement, not on ordering.
    assemble_graph(
        CLAIM, reversed_steps, config=CONFIG, terminations=outcome.terminations, now=FIXED
    )

    citable = next(
        pid
        for pid, reason in outcome.terminations.items()
        if reason is TerminationReason.UNVERIFIABLE_BY_DESIGN
    )
    with pytest.raises(ValueError, match="which its type does not carry"):
        assemble_graph(
            CLAIM,
            outcome.steps,
            config=CONFIG,
            terminations={**outcome.terminations, citable: TerminationReason.CITATION_SHAPED},
            now=FIXED,
        )


def test_a_reason_naming_a_premise_the_graph_does_not_hold_is_refused():
    """Bookkeeping and output disagreeing about which nodes exist would let the
    every-terminal-has-a-reason check pass over a map describing a different tree."""
    outcome, _ = _descend()
    with pytest.raises(ValueError, match="does not hold"):
        assemble_graph(
            CLAIM,
            outcome.steps,
            config=CONFIG,
            terminations={**outcome.terminations, "prem_notreal": TerminationReason.CAP_EXIT},
            now=FIXED,
        )


def test_the_descent_refuses_to_leave_a_premise_neither_decomposed_nor_terminated():
    """The internal invariant, asserted where it can name the bug rather than surfacing two
    layers up as a pydantic error about a graph."""
    outcome, _ = _descend()
    accounted = set(outcome.terminations) | {
        s.conclusion_id for s in outcome.steps if s.conclusion_id != CLAIM.id
    }
    every = {pid for step in outcome.steps for pid in step.step.premise_ids}
    assert every == accounted


def test_a_refusal_carries_its_type_through_to_the_counts_and_the_enum_stays_coarse():
    """M10-T1 reads the manifest alongside the graph, and this is why: the artifact says a
    branch was refused, the counts say a truncation is not a cyclic premise is not a
    declined expansion."""
    from verity.decomposition.backward_chain import PURPOSE

    truncating = StubAdapter(
        structured={PURPOSE: lambda r: TREE.get(target_of(r), _d(_p("Anything.")))},
        stop_reason="max_tokens",
    )
    with pytest.raises(DecompositionError):
        decompose_claim(CLAIM, adapter=truncating, config=CONFIG, now=FIXED)

    def once(request: LLMRequest) -> ProposedDecomposition:
        if target_of(request) == MID:
            raise LLMRefusalError("declined")
        return TREE[target_of(request)]

    outcome = decompose_claim(
        CLAIM,
        adapter=StubAdapter(structured={PURPOSE: once}),
        config=CONFIG,
        now=FIXED,
    )
    assert outcome.counts["refused:provider-refusal"] == 1
    assert "refused:truncated" not in outcome.counts
