"""M4-T1 — the off-the-shelf gate.

Offline by construction: every test here runs against `ScriptedScorer`, so the suite needs
no ML stack and no checkpoint. The one test that does load a real model skips when the
`verifier` extra is absent, and carries an explicit reason for it — a skip whose reason
nobody prints is a silent cap, so run the suite with `-rs` to surface them.

What these pin, in descending order of how quietly they would otherwise rot:

- **Order invariance.** A step's identity is its conclusion and the *set* of its premises,
  so a score that moved with proposal order would put two numbers on one step id and
  M1-T2's replay would return a graph whose numbers changed with nothing recorded.
- **One scorer call per step.** Batching changes logits through padding; a later
  performance pass that batched would move every number in every stored graph with the
  config hash unmoved.
- **Refuse rather than truncate.** A score computed on the premises that fit belongs to a
  step nobody proposed.
- **The gate is derived.** A stored pass/fail boolean goes stale the moment the threshold
  moves, leaving the graph carrying a decision no configuration made.
"""

from __future__ import annotations

import inspect
import os

import pytest

from verity.config import VerifierConfig
from verity.models.claim import ClaimGraph
from verity.models.common import Calibration
from verity.verifier import (
    SCORE_DECIMALS,
    DuplicatePremiseError,
    EmptyPremiseSetError,
    ScorerSpec,
    ScriptedScorer,
    canonical_order,
    passes_gate,
    render_document,
    score_graph,
)

# -- the exit criterion: every step in a stored graph carries a score ------------------


def test_every_step_gets_a_score_and_no_step_is_re_keyed(hand_built_graph: ClaimGraph):
    result = score_graph(hand_built_graph, ScriptedScorer(default=0.61))

    assert result.scored == len(hand_built_graph.steps)
    assert result.unscored == 0
    assert all(step.score is not None for step in result.graph.steps)
    assert [s.id for s in result.graph.steps] == [s.id for s in hand_built_graph.steps], (
        "a score is not part of step identity, so scoring must not re-key the graph"
    )


def test_scores_are_uncalibrated_and_carry_the_scorer_identity(hand_built_graph: ClaimGraph):
    """evaluation.md §6: a model-produced number says so until it has a human anchor."""
    result = score_graph(hand_built_graph, ScriptedScorer(default=0.61))
    for step in result.graph.steps:
        assert step.score.calibration is Calibration.UNCALIBRATED
        assert step.score.basis is None
        assert step.score.scorer.startswith("stub-scripted@")
        assert "+concat-v1" in step.score.scorer, "the recipe travels with the number"


def test_scores_are_rounded_so_replay_survives_float_noise(hand_built_graph: ClaimGraph):
    result = score_graph(hand_built_graph, ScriptedScorer(default=0.123456789))
    for step in result.graph.steps:
        assert step.score.value == round(0.123456789, SCORE_DECIMALS)


# -- the input recipe -----------------------------------------------------------------


def test_the_document_is_a_function_of_the_premise_set_not_its_order():
    premises = [
        "Raw spinach contains roughly 2.7 mg of iron per 100 g.",
        "A widely circulated figure reported roughly ten times that amount.",
        "A tenfold discrepancy is what a misplaced decimal point produces.",
    ]
    forward = render_document(premises)
    reversed_ = render_document(list(reversed(premises)))
    rotated = render_document([premises[2], premises[0], premises[1]])
    assert forward == reversed_ == rotated


def test_a_reordered_step_scores_identically(hand_built_graph: ClaimGraph):
    """The property the recipe exists for, observed through a scorer rather than a join."""
    scorer = ScriptedScorer(default=0.5)
    step = hand_built_graph.steps[0]
    conclusion = hand_built_graph.conclusion_of(step).text
    premises = [hand_built_graph.premises[pid].text for pid in step.premise_ids]

    assert scorer.score(conclusion, premises) == scorer.score(
        conclusion, list(reversed(premises))
    )


def test_an_empty_premise_set_refuses():
    """M4-T2's leave-one-out on a one-premise step lands here, and both real checkpoints
    would happily return the model's prior on the conclusion instead."""
    with pytest.raises(EmptyPremiseSetError):
        canonical_order([])
    with pytest.raises(EmptyPremiseSetError):
        ScriptedScorer(default=0.5).score("Some conclusion.", [])


def test_a_repeated_premise_refuses():
    """Deduplicating would be entailment-preserving but would score a different arity
    than the caller believes it passed."""
    with pytest.raises(DuplicatePremiseError):
        canonical_order(["The same premise.", "The same premise."])


# -- refuse rather than truncate -------------------------------------------------------


def test_an_oversize_step_is_left_unscored_and_reported(hand_built_graph: ClaimGraph):
    # Chosen to bite on the root step and not the nested one, so the partial case is the
    # one under test rather than a whole-graph refusal.
    scorer = ScriptedScorer(default=0.9, max_input_tokens=35)
    result = score_graph(hand_built_graph, scorer)

    assert result.unscored == 1
    assert result.scored == len(hand_built_graph.steps) - 1
    assert len(result.oversize_step_ids) == 1

    unscored = [s for s in result.graph.steps if s.score is None]
    assert [s.id for s in unscored] == result.oversize_step_ids

    caps = [c for c in result.graph.metadata.caps if c.name == "oversize_steps_unscored"]
    assert len(caps) == 1
    assert caps[0].applied and caps[0].dropped == 1, (
        "evaluation.md §6: a cap that bit must say what it dropped"
    )


def test_an_oversize_step_does_not_keep_a_previous_scorers_number(
    hand_built_graph: ClaimGraph,
):
    """The fixture arrives pre-scored. A number left standing beside this pass's spec
    would read as this pass's output."""
    assert hand_built_graph.steps[0].score is not None
    result = score_graph(hand_built_graph, ScriptedScorer(default=0.9, max_input_tokens=35))
    assert result.graph.steps[0].score is None


# -- one call per step -----------------------------------------------------------------


def test_the_scorer_is_called_exactly_once_per_step(hand_built_graph: ClaimGraph):
    scorer = ScriptedScorer(default=0.61)
    score_graph(hand_built_graph, scorer)
    assert len(scorer.calls) == len(hand_built_graph.steps)


# -- re-scoring ------------------------------------------------------------------------


def test_re_scoring_replaces_every_score_so_a_graph_never_mixes_checkpoints(
    hand_built_graph: ClaimGraph,
):
    first = score_graph(hand_built_graph, ScriptedScorer(default=0.20))
    second = score_graph(first.graph, ScriptedScorer(default=0.80))

    assert {s.score.value for s in second.graph.steps} == {0.80}
    assert [s.id for s in second.graph.steps] == [s.id for s in hand_built_graph.steps]
    assert {s.score.scorer for s in second.graph.steps} == {second.spec.scorer_id}


# -- the gate --------------------------------------------------------------------------


def test_the_gate_is_derived_and_reads_the_stored_value(hand_built_graph: ClaimGraph):
    config = VerifierConfig(entailment_threshold=0.50)
    above = score_graph(hand_built_graph, ScriptedScorer(default=0.61)).graph
    below = score_graph(hand_built_graph, ScriptedScorer(default=0.30)).graph

    assert all(passes_gate(s, config) is True for s in above.steps)
    assert all(passes_gate(s, config) is False for s in below.steps)


def test_the_gate_boundary_is_inclusive(hand_built_graph: ClaimGraph):
    config = VerifierConfig(entailment_threshold=0.50)
    at = score_graph(hand_built_graph, ScriptedScorer(default=0.50)).graph
    assert all(passes_gate(s, config) is True for s in at.steps)


def test_an_unscored_step_has_no_gate_answer(hand_built_graph: ClaimGraph):
    result = score_graph(hand_built_graph, ScriptedScorer(default=0.9, max_input_tokens=35))
    unscored = next(s for s in result.graph.steps if s.score is None)
    assert passes_gate(unscored, VerifierConfig()) is None


def test_no_gate_verdict_is_stored_anywhere():
    """A stored boolean derived from a config knob goes stale when the knob moves."""
    from verity.models.claim import EntailmentStep
    from verity.models.render import RenderPremise

    forbidden = {"passes_gate", "gate", "gate_passed", "passed", "entails"}
    assert not set(EntailmentStep.model_fields) & forbidden
    assert not set(RenderPremise.model_fields) & forbidden


# -- scorer identity -------------------------------------------------------------------


def test_a_scorer_with_verification_disabled_is_visible_in_every_score_it_produces():
    verified = ScorerSpec(checkpoint="some/checkpoint", revision="a" * 40, max_input_tokens=512)
    unverified = verified.model_copy(update={"label_order_verified": False})

    assert verified.scorer_id == "some/checkpoint@aaaaaaa+concat-v1"
    assert unverified.scorer_id.endswith("+label-order-unverified")
    assert verified.scorer_id != unverified.scorer_id


def test_the_stub_scorer_is_unmistakable_in_an_artifact():
    """A graph accidentally scored by the test double must be identifiable forever."""
    assert ScriptedScorer().spec.checkpoint.startswith("stub-")
    assert ScriptedScorer().spec.scorer_id.startswith("stub-")


def test_no_verifier_module_composes_step_scores():
    """M4 is the module most likely to grow a `mean_step_score`. It must not."""
    from verity.verifier import bakeoff, base, scoring, smoke_set, stub

    forbidden = ("aggregate", "overall", "compose_scores", "root_score", "tree_score")
    for module in (bakeoff, base, scoring, smoke_set, stub):
        for name, obj in vars(module).items():
            if name.startswith("_") or getattr(obj, "__module__", "") != module.__name__:
                continue
            if inspect.isfunction(obj) or inspect.isclass(obj):
                assert not any(token in name.lower() for token in forbidden), (
                    f"{module.__name__}.{name} looks like a score-composition helper"
                )


# -- the checkpoint registry -----------------------------------------------------------


def test_config_model_id_decides_which_checkpoint_loads():
    """`model_id` moves `config_hash()` and therefore invalidates every M1-T2 stage cache.
    If it did not also decide what actually loads, the config snapshot and the stored
    `Score.scorer` would name different checkpoints with no error anywhere."""
    from verity.verifier.registry import (
        MINICHECK_CHECKPOINT,
        NLI_CHECKPOINT,
        backend_for,
    )

    assert backend_for(NLI_CHECKPOINT).__name__ == "NliScorer"
    assert backend_for(MINICHECK_CHECKPOINT).__name__ == "MiniCheckScorer"


def test_every_checkpoint_is_pinned_to_the_commit_it_was_selected_at():
    """A checkpoint name without a commit is not a reproducible scorer — the same id can
    serve different weights a month later, and the demo's recorded scores would stop
    reproducing with nothing to show why.

    The pin is per checkpoint rather than on the config because one `revision` field
    cannot name the right commit for two checkpoints, and the bake-off loads both: pinning
    the champion's commit globally would make MiniCheck ask the hub for a commit that does
    not exist in its repository.
    """
    import json
    from pathlib import Path

    from verity.verifier.registry import BACKENDS, pinned_revision

    recorded = {
        spec["checkpoint"]: spec["revision"]
        for spec in json.loads(
            Path("data/verifier/selection.json").read_text(encoding="utf-8")
        )["scorers"].values()
    }
    assert recorded, "the selection record must name the commits it measured"

    for checkpoint in BACKENDS:
        pin = pinned_revision(checkpoint)
        assert len(pin) == 40, f"{checkpoint} is pinned to {pin!r}, not a full commit sha"
        assert pin == recorded[checkpoint], (
            f"{checkpoint} is pinned to {pin} but was selected at {recorded[checkpoint]}"
        )


def test_the_config_can_override_a_pin_but_does_not_have_to():
    from verity.verifier.registry import NLI_CHECKPOINT, pinned_revision, resolve_revision

    assert resolve_revision(VerifierConfig(), NLI_CHECKPOINT) == pinned_revision(NLI_CHECKPOINT)
    override = VerifierConfig(revision="f" * 40)
    assert resolve_revision(override, NLI_CHECKPOINT) == "f" * 40


def test_an_unknown_checkpoint_names_the_ones_that_exist():
    from verity.verifier.registry import UnknownCheckpointError, backend_for

    with pytest.raises(UnknownCheckpointError, match="known checkpoints"):
        backend_for("MoritzLaurer/DeBERTa-v3-base-mnli")


def test_a_backend_refuses_a_checkpoint_it_cannot_drive():
    """The failure this closes: `model_id` names MiniCheck, someone builds `NliScorer`,
    and a sequence-classification head is asked to load a seq2seq checkpoint — or worse,
    quietly loads its own preferred one instead."""
    from verity.verifier.nli import NliScorer
    from verity.verifier.registry import (
        MINICHECK_CHECKPOINT,
        UnknownCheckpointError,
        resolve_checkpoint,
    )

    config = VerifierConfig(model_id=MINICHECK_CHECKPOINT)
    with pytest.raises(UnknownCheckpointError, match="cannot drive"):
        resolve_checkpoint(config, NliScorer, None)


# -- the smoke set's own integrity ------------------------------------------------------


def test_no_negation_case_is_built_from_a_negation_ineligible_decomposition():
    """The defect this exists to prevent, having already happened once.

    Negating a premise whose content another premise also asserts or presupposes yields an
    internally inconsistent set that still contains a sub-entailment of the conclusion. A
    high score there is defensible, so scoring it as a corruption manufactures a finding —
    which is exactly what a mislabelled Mozart case did in the first pass, producing a
    published claim that both checkpoints were blind to negation.

    **What this can and cannot catch.** It cross-checks a smoke case against a declared
    field, so it cannot detect a review verdict that is simply wrong — the semantic
    judgement stays builder-made and reviewable only by reading `case_review.json`. What it
    does prevent is the failure that actually occurred: the question going unasked for a
    given case. `test_every_review_case_was_examined_under_every_lens` is the half that
    closes that hole, by refusing a review entry with no verdict under a lens.
    """
    import json
    from pathlib import Path

    review = {
        case["id"]: case
        for case in json.loads(
            Path("data/verifier/case_review.json").read_text(encoding="utf-8")
        )["cases"]
    }
    cases = [
        json.loads(line)
        for line in Path("data/verifier/smoke_set.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    negations = [c for c in cases if c["label"] == "corrupt-premise-negated"]
    assert negations, "the deciding set must still contain negation cases"
    for case in negations:
        source = review[case["review_id"]]
        assert source["negation_eligible"], (
            f"{case['case_id']} negates a premise of {case['review_id']}, which the "
            "review marked negation-ineligible"
        )
        assert source["negation_uniqueness"], "eligibility must record its reasoning"


def test_every_review_case_was_examined_under_every_lens():
    """The root cause was a lens applied to one case and not another."""
    import json
    from pathlib import Path

    review = json.loads(Path("data/verifier/case_review.json").read_text(encoding="utf-8"))
    for case in review["cases"]:
        for lens in ("joint_sufficiency", "restatement", "presupposition"):
            assert case.get(lens), f"{case['id']} has no verdict under the {lens} lens"
        assert "negation_eligible" in case, f"{case['id']} does not state its eligibility"


def test_the_committed_smoke_set_is_what_its_builder_produces():
    """The artifact a checkpoint was selected against must stay regenerable.

    `smoke_set.jsonl` is tracked and `selection.json` rests on it, so a hand-edit to the
    file — or a drift between it and the corruptions in `smoke_set.build()` — would leave
    the published numbers describing a stimulus set no code can reproduce.
    """
    from verity.verifier import smoke_set as smoke_set_module

    assert [c.model_dump() for c in smoke_set_module.build()] == [
        c.model_dump() for c in smoke_set_module.load_smoke_set()
    ]


def test_review_flags_travel_into_the_smoke_set():
    """ "Clean" in the smoke set means "passed the review", and a reader of the smoke set
    alone has to be able to see what it passed with."""
    import json
    from pathlib import Path

    cases = [
        json.loads(line)
        for line in Path("data/verifier/smoke_set.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    reviewed = [c for c in cases if "review_id" in c]
    assert reviewed
    assert all("review_flags" in c for c in reviewed)


# -- the model layer, when it is installed ---------------------------------------------


@pytest.mark.skipif(
    os.environ.get("VERITY_SKIP_MODEL_TESTS") == "1",
    reason="VERITY_SKIP_MODEL_TESTS=1 set explicitly",
)
def test_the_champion_checkpoint_loads_and_verifies_its_label_order():
    """Loads a real checkpoint. Skips with a stated reason without the extra."""
    pytest.importorskip(
        "torch", reason="the `verifier` extra is not installed (pip install -e '.[verifier]')"
    )
    pytest.importorskip("transformers", reason="the `verifier` extra is not installed")

    from verity.verifier.nli import NliScorer

    scorer = NliScorer(VerifierConfig())
    assert scorer.spec.label_order_verified
    assert scorer.spec.revision != "unresolved", "a score must name the commit that made it"

    entailed = scorer.score(
        "A person is playing an instrument.", ["A man is playing a guitar on stage."]
    )
    contradicted = scorer.score(
        "There is a white swan in the lake.", ["Every swan in the lake is black."]
    )
    assert entailed.value > contradicted.value
    assert entailed.calibration is Calibration.UNCALIBRATED
