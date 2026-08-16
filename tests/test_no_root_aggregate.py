"""The verdict boundary, enforced structurally.

design.md §3.1: verdicts exist only at the leaves, and **no root aggregate is ever
displayed**. Rendering per-premise confidence only, never a root aggregate, is what
enforces that in code — so these tests check the *shape* of the models rather than the
behaviour of any one renderer. They fail on drift: adding a score field to `Claim`, or a
summary number to `RenderPayload`, breaks the build rather than shipping quietly.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from verity.export import to_json
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Premise
from verity.models.render import (
    ROOT_AGGREGATE_FORBIDDEN_FIELDS,
    RenderPayload,
    RenderPremise,
    RenderRoot,
    to_render_payload,
)

#: Everything a renderer is allowed to see above the per-premise rows. A new entry here
#: is a deliberate act that has to be argued for, not an accident.
ALLOWED_PAYLOAD_FIELDS = {
    "root",
    "premises",
    "max_depth",
    "caps",
    "has_uncalibrated_scores",
    "has_stale_groundings",
    "checked_at",
}


def _field_names(model: type[BaseModel]) -> set[str]:
    return set(model.model_fields)


def test_root_types_declare_no_aggregate_field():
    for model in (Claim, ClaimGraph, RenderRoot, RenderPayload):
        offending = _field_names(model) & ROOT_AGGREGATE_FORBIDDEN_FIELDS
        assert not offending, f"{model.__name__} declares root-aggregate field(s) {offending}"


def test_premise_carries_no_standalone_confidence():
    """Confidence lives on the step the verifier scores, not on the premise.

    A float on `Premise` would be a number nothing computes. The premise's honest
    display is its step's score plus its own ablation delta.
    """
    assert "score" not in _field_names(Premise)
    assert "confidence" not in _field_names(Premise)
    assert "score" in _field_names(EntailmentStep)


def test_render_payload_exposes_nothing_above_the_premise_rows():
    assert _field_names(RenderPayload) == ALLOWED_PAYLOAD_FIELDS
    assert _field_names(RenderRoot) == {"id", "text"}


def test_exported_graph_has_no_root_level_aggregate(hand_built_graph: ClaimGraph):
    payload = json.loads(to_json(hand_built_graph))
    assert not set(payload) & ROOT_AGGREGATE_FORBIDDEN_FIELDS
    assert not set(payload["root_claim"]) & ROOT_AGGREGATE_FORBIDDEN_FIELDS


def test_renderer_receives_per_premise_scores_only(hand_built_graph: ClaimGraph, fact_lookup):
    payload = to_render_payload(hand_built_graph, fact_lookup)
    rendered = json.loads(to_json(payload))

    assert not set(rendered) & ROOT_AGGREGATE_FORBIDDEN_FIELDS
    assert not set(rendered["root"]) & ROOT_AGGREGATE_FORBIDDEN_FIELDS

    # Every score that reaches the renderer is attached to a premise row and is scoped
    # to a single step. Nothing composes them.
    scored = [row for row in payload.premises if row.step_score is not None]
    assert scored, "fixture should exercise at least one scored step"
    for row in scored:
        assert row.step_id is not None
        assert "single-step" in row.step_score_scope


def test_scores_reach_the_renderer_labelled_uncalibrated(
    hand_built_graph: ClaimGraph, fact_lookup
):
    """evaluation.md §6: a model-produced number says so until it has a human anchor."""
    payload = to_render_payload(hand_built_graph, fact_lookup)
    assert payload.has_uncalibrated_scores
    labelled = [r for r in payload.premises if r.step_score]
    assert all("uncalibrated" in r.step_score for r in labelled)


def test_render_premise_rows_carry_their_own_evidence(
    hand_built_graph: ClaimGraph, fact_lookup
):
    payload = to_render_payload(hand_built_graph, fact_lookup)
    by_text = {row.text: row for row in payload.premises}

    grounded = next(r for r in payload.premises if r.grounded)
    assert grounded.bound_key is not None

    contested_row = by_text[
        "A widely circulated figure reported roughly ten times that amount."
    ]
    assert contested_row.evidence_counts == {
        "supporting": 1,
        "contradicting": 1,
        "neutral": 0,
        "rejected": 4,
    }
    assert contested_row.retraction_flags, "a retracted source must surface on its premise"


def test_no_module_composes_step_scores():
    """There is no aggregation helper anywhere on the model surface."""
    import inspect

    from verity.models import claim as claim_module
    from verity.models import render as render_module

    forbidden = ("aggregate", "overall", "compose_scores", "root_score", "tree_score")
    for module in (claim_module, render_module):
        callables = [
            name
            for name, obj in vars(module).items()
            if not name.startswith("_")
            and (inspect.isfunction(obj) or inspect.isclass(obj))
            and getattr(obj, "__module__", "") == module.__name__
        ]
        for name in callables:
            assert not any(token in name.lower() for token in forbidden), (
                f"{module.__name__}.{name} looks like a score-composition helper"
            )
    assert not _field_names(RenderPremise) & ROOT_AGGREGATE_FORBIDDEN_FIELDS
