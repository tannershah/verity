"""Two batteries: states that must be impossible, and states that must stay possible.

The second half matters as much as the first. An over-constrained model is as damaging
as an under-constrained one over a thirty-session build — M3 will return eight premises,
M5 will share a premise between steps, M6 will produce a bundle with nothing in it. Those
must be *recorded*, not raised. The split this file asserts is:

    structural invariants raise;  policy violations are recorded and reported.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Premise
from verity.models.common import (
    AblationDelta,
    Calibration,
    CapRecord,
    ConfidenceTier,
    Extraction,
    LabeledField,
    Provenance,
    QueryClass,
    Score,
)
from verity.models.evidence import EvidenceBundle, EvidenceQuality, IssuedQuery
from verity.models.fact import Fact, Justification

KEY = ExternalKey(type=KeyType.DOI, value="10.1136/bmj.283.6307.1671")
ACCESSED = datetime(2026, 8, 16, tzinfo=UTC)


# -- must be impossible --------------------------------------------------------------


def test_an_unknown_field_is_refused_by_every_record_type():
    """Pydantic ignores unknown fields by default, so a field renamed in one place and not
    another — or a typo at a call site — vanishes silently and takes its value with it.
    The record still validates and still round-trips; it just stops carrying what the
    caller said it carried.

    That is the most likely way for drift to become permanent in a codebase written mostly
    by agents, so it is checked over every model reachable from the data layer rather than
    left to the base class being remembered.
    """
    import inspect

    from verity import base, keys
    from verity.llm import base as llm_base
    from verity.models import claim, common, evidence, fact, manifest, render

    checked = 0
    for module in (keys, common, claim, evidence, fact, manifest, render, llm_base):
        for _, model in inspect.getmembers(module, inspect.isclass):
            if not issubclass(model, BaseModel) or model.__module__ != module.__name__:
                continue
            assert model.model_config.get("extra") == "forbid", (
                f"{module.__name__}.{model.__name__} silently accepts unknown fields; "
                f"it should inherit from {base.VerityModel.__name__}"
            )
            checked += 1
    assert checked >= 20, f"only {checked} models scanned — the sweep is not finding them"


def test_the_guard_bites_on_a_renamed_field():
    """The concrete case it caught: a field removed from `EvidenceQuality` was still being
    passed by two tests, which passed while asserting nothing."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceQuality(retraction_sources=["retraction-watch"])


def test_a_score_cannot_be_nan_or_infinite():
    """`nan` is the dangerous one: every comparison against a threshold returns False, so
    a broken verifier would read as a confidently-failing step rather than as an error,
    and the M4-T1 gate would fail closed while looking like it worked."""
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            Score(value=bad, scorer="test")


def test_a_score_stays_inside_the_unit_interval():
    """Every scorer in the plan (MiniCheck, DeBERTa-NLI stance) emits a probability. A
    logit or a percentage arriving unnoticed would silently pass every gate and render as
    a confidence bar longer than the bar."""
    with pytest.raises(ValidationError):
        Score(value=17.0, scorer="test")
    with pytest.raises(ValidationError):
        Score(value=-0.1, scorer="test")


def test_an_ablation_delta_is_bounded_by_the_scores_it_came_from():
    """Signed, because removing a premise can raise a step's score — but each side is
    still a probability."""
    with pytest.raises(ValidationError):
        AblationDelta(step_score=1.4, ablated_score=0.2, scorer="test")
    with pytest.raises(ValidationError):
        AblationDelta(step_score=float("nan"), ablated_score=0.2, scorer="test")


def test_a_calibrated_score_must_record_its_basis():
    """evaluation.md §6 and M4-T3's exit criterion: the calibration basis is recorded in
    graph metadata *with* the distribution-shift caveat. A score claiming calibration
    with no basis is the uncalibrated label removed and nothing put in its place."""
    with pytest.raises(ValidationError):
        Score(value=0.9, scorer="test", calibration=Calibration.CALIBRATED)
    with pytest.raises(ValidationError):
        AblationDelta(
            step_score=0.9,
            ablated_score=0.4,
            scorer="test",
            calibration=Calibration.CALIBRATED,
        )
    assert (
        Score(
            value=0.9, scorer="test", calibration=Calibration.CALIBRATED, basis="ROC on EB"
        ).label()
        == "0.90"
    )


def test_an_applied_cap_says_what_it_dropped():
    """evaluation.md §6: "If coverage is bounded — top-N, sampling, no-retry — say what
    was dropped." A cap that bit with no count is the silent cap the rule names."""
    with pytest.raises(ValidationError):
        CapRecord(name="retrieval_top_k", limit=10, applied=True)


def test_a_cap_may_say_the_count_is_unavailable_but_must_say_so():
    """A no-retry cap drops attempts nobody enumerated. "Uncounted" is an honest answer;
    silence is not."""
    cap = CapRecord(name="no_retry", limit=0, applied=True, dropped="uncounted")
    assert cap.dropped == "uncounted"


def test_a_cap_that_did_not_apply_reports_no_drop():
    with pytest.raises(ValidationError):
        CapRecord(name="retrieval_top_k", limit=10, applied=False, dropped=3)


def test_a_verified_fact_carries_provenance():
    """design.md §4.1 defines a fact as "addressable and provenance-carrying", and M5-T2
    promotes to a grounding-eligible tier on source confidence tier — which is read from
    the provenance."""
    with pytest.raises(ValidationError):
        Fact(statement="s", key=KEY, tier=ConfidenceTier.VERIFIED_PRIMARY, provenance=[])
    # A tier that cannot ground anything has nothing to substantiate yet.
    assert Fact(statement="s", key=KEY, tier=ConfidenceTier.INFERRED).provenance == []


def test_a_justification_accepts_only_fact_ids():
    """design.md §4.2 calls this "the verdict boundary as a type distinction, not a
    convention", and M8-T3's exit criterion is "a contested premise cannot justify
    anything". The ids below are a premise and a bundle."""
    with pytest.raises(ValidationError):
        Justification(
            consequent_fact_id="fact_ok",
            antecedent_fact_ids=["prem_contested", "bundle_derived"],
        )
    assert Justification(
        consequent_fact_id="fact_ok", antecedent_fact_ids=["fact_a", "fact_b"]
    ).antecedent_fact_ids == ["fact_a", "fact_b"]


def test_provenance_access_time_is_never_fabricated():
    """design.md §4.2 makes grounding non-monotonic and M5-T3 re-validates on a TTL read
    from this field. A default of `now()` would give a seed record — or any row rebuilt
    from a file that omits the field — a freshness it never had, and the TTL would never
    fire."""
    with pytest.raises(ValidationError):
        Provenance(source="seed")


# -- must stay possible --------------------------------------------------------------


def test_a_premise_may_be_shared_between_two_steps():
    """M5-T1 dedups by statement hash; the graph is a DAG. Construction must allow it,
    and the renderer shows it under each step (see test_graph_invariants)."""
    claim = Claim(text="Root claim.")
    shared = Premise(text="Shared.")
    left = Premise(text="Left.")
    right = Premise(text="Right.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={p.id: p for p in (shared, left, right)},
        steps=[
            EntailmentStep(conclusion_id=claim.id, premise_ids=[left.id, right.id]),
            EntailmentStep(conclusion_id=left.id, premise_ids=[shared.id]),
            EntailmentStep(conclusion_id=right.id, premise_ids=[shared.id]),
        ],
    )
    assert len(graph.steps) == 3


def test_a_step_outside_the_configured_arity_does_not_raise():
    """3-7 is a `DecompositionConfig` value. An LLM returning eight premises is a
    measurement about the decomposer, not a crash — M3-T1 has to be able to store it and
    report it."""
    step = EntailmentStep(conclusion_id="claim_x", premise_ids=[f"prem_{i}" for i in range(8)])
    assert step.arity == 8


def test_a_claim_with_no_decomposition_is_a_valid_graph():
    """The state after intake and before M3 runs, and the state after a stage error —
    M1-T2's failure isolation yields "a partial graph, not a crash"."""
    claim = Claim(text="Nothing decomposed yet.")
    graph = ClaimGraph(root_claim=claim)
    assert graph.leaves() == []
    assert graph.max_depth() == 0


def test_a_premise_may_hold_a_candidate_key_without_a_binding():
    """M3-T1 fills a candidate key when the model happens to know the work; M6-T3 is the
    authoritative binding. The hint must never be mistaken for the binding — the two are
    separate fields, and only `bound_key` is read for grounding."""
    premise = Premise(text="p", candidate_key=KEY)
    assert premise.bound_key is None
    assert premise.candidate_key == KEY


def test_an_empty_bundle_is_representable():
    """M6-T2 can legitimately find nothing. `provisional_state` carries that."""
    bundle = EvidenceBundle(premise_id="prem_x")
    assert bundle.provisional_state == "none"
    assert bundle.counts == {"supporting": 0, "contradicting": 0, "neutral": 0, "rejected": 0}


def test_a_bundle_distinguishes_searched_and_empty_from_never_searched():
    """M6-T2 makes contrasting-evidence queries "a mandatory branch, not an afterthought,
    so one-sided bundles can't happen silently". Silence is exactly what an empty result
    list is — so the query itself is recorded, and the two bundles below no longer
    serialize identically.
    """
    never_searched = EvidenceBundle(premise_id="prem_x")
    searched_found_nothing = EvidenceBundle(
        premise_id="prem_x",
        queries=[
            IssuedQuery(
                query_class=QueryClass.CONTRASTING,
                text="evidence against the premise",
                source="openalex",
                issued_at=ACCESSED,
                returned=0,
            )
        ],
    )

    assert never_searched.model_dump() != searched_found_nothing.model_dump()
    assert never_searched.counts == searched_found_nothing.counts, (
        "the results are identical — the difference is entirely in what was asked"
    )
    assert not never_searched.contrasting_search_ran
    assert searched_found_nothing.contrasting_search_ran


def test_a_one_sided_bundle_cannot_hide_that_it_is_one_sided():
    """The failure M6-T2's mandatory branch exists to prevent: supporting evidence found,
    contrasting evidence never sought, and nothing in the bundle saying so."""
    one_sided = EvidenceBundle(
        premise_id="prem_x",
        provisional_state="has-evidence",
        queries=[
            IssuedQuery(
                query_class=QueryClass.SUPPORTING,
                text="evidence for the premise",
                source="openalex",
                issued_at=ACCESSED,
                returned=5,
            )
        ],
    )
    assert one_sided.searched_classes == {QueryClass.SUPPORTING}
    assert not one_sided.contrasting_search_ran


def test_a_model_extracted_field_is_distinguishable_from_a_registry_one():
    """design.md §5: "a registry N and a text-mined N must never be indistinguishable"."""
    provenance = Provenance(source="ctgov", accessed_at=ACCESSED)
    registry = LabeledField[int](
        value=180, extraction=Extraction.REGISTRY, provenance=provenance
    )
    mined = LabeledField[int](
        value=16, extraction=Extraction.MODEL_EXTRACTED, provenance=provenance
    )
    assert not registry.is_model_extracted
    assert mined.is_model_extracted
    assert EvidenceQuality(sample_size=mined).has_model_extracted_fields
