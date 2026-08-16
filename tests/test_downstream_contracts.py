"""Can the tiers that consume this model actually be written against it?

M1-T1's exit criterion — round-trip a hand-built graph — passes for a data model that is
deeply wrong. These tests are the other check: the smallest executable stub of what each
named downstream tier will need, run against a hand-built graph and nothing else. A tier
that cannot be expressed today is a defect today, not in session 24.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from verity.models.claim import ClaimGraph
from verity.models.common import (
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
    TerminationReason,
)
from verity.models.evidence import EvidenceQuality, RetractionCheck
from verity.models.fact import InMemoryFacts
from verity.models.render import to_render_payload

CHECKED_AT = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

# -- M10-T1: metrics computed from a run's artifacts ---------------------------------


def test_termination_mix_and_budget_exit_rate_are_computable(hand_built_graph: ClaimGraph):
    """M10-T1's metrics logger computes "grounding rate (exact-key definition), mean/max
    depth, termination-reason mix, budget-exit rate" per run. Everything but grounding
    comes off the graph alone, and this is that computation."""
    leaves = hand_built_graph.leaves()
    assert leaves, "fixture must have terminals to measure"

    mix = Counter(p.termination_reason for p in leaves)
    assert set(mix) <= set(TerminationReason)
    assert None not in mix, "every terminal must record why it stopped"

    budget_exit_rate = mix[TerminationReason.BUDGET_EXIT] / len(leaves)
    assert 0.0 <= budget_exit_rate <= 1.0

    # The depth reported next to a budget-exit rate has to be the depth the budget was
    # spent to, which is recorded by the decomposer rather than inferred from the shape.
    budget = hand_built_graph.metadata.depth_budget
    recorded = hand_built_graph.recorded_depth()
    assert recorded is not None, "a run whose depth nothing recorded cannot report one"
    assert recorded <= budget


def test_the_grounding_denominator_includes_unverifiable_terminals(
    hand_built_graph: ClaimGraph,
):
    """build-plan.md §4: `unverifiable-by-design` terminals "count in the pre-registered
    grounding-rate denominator (conservative: they deflate, never inflate). A supplementary
    rate over citable branches only is reported alongside, labeled."

    Both denominators have to be derivable, which means every terminal needs a
    termination reason *and* a premise type. This asserts the model carries both.
    """
    leaves = hand_built_graph.leaves()
    assert all(p.termination_reason is not None for p in leaves)
    assert all(p.premise_type is not None for p in leaves), (
        "the citable-only supplementary rate needs premise typing on every terminal"
    )

    headline_denominator = len(leaves)
    unverifiable = TerminationReason.UNVERIFIABLE_BY_DESIGN
    citable_denominator = sum(1 for p in leaves if p.termination_reason is not unverifiable)
    assert citable_denominator <= headline_denominator


def test_the_grounding_numerator_consults_the_facts_it_claims(
    hand_built_graph: ClaimGraph, fact_lookup
):
    """ "Grounds" is defined as a match to a grounding-eligible fact (evaluation.md §2).
    The numerator therefore has to read the alethiology, not just the graph's own row —
    otherwise the headline rate is computable only in the sense that a number comes out.
    """
    payload = to_render_payload(hand_built_graph, fact_lookup)
    grounded = [row for row in payload.premises if row.grounded]
    assert len(grounded) == 1

    # The same graph against an empty alethiology grounds nothing, and says why.
    empty = to_render_payload(hand_built_graph, InMemoryFacts())
    assert not [row for row in empty.premises if row.grounded]
    assert empty.has_stale_groundings

    rate = len(grounded) / len(hand_built_graph.leaves())
    assert 0.0 <= rate <= 1.0


# -- M9-T1: the CLI render needs four columns per premise ----------------------------


def test_every_render_row_exposes_the_four_columns_m9_renders(
    hand_built_graph: ClaimGraph, fact_lookup
):
    """M9-T1 renders "per-step verifier confidence, plus placeholder columns that light
    up as producers land (grounding status, termination reason, evidence state)"."""
    payload = to_render_payload(hand_built_graph, fact_lookup)
    assert payload.premises

    for row in payload.premises:
        assert hasattr(row, "step_score")
        assert hasattr(row, "grounded")
        assert hasattr(row, "termination_reason")
        assert hasattr(row, "evidence_state")


def test_a_confidence_bar_can_be_drawn_without_parsing_a_display_string(
    hand_built_graph: ClaimGraph, fact_lookup
):
    """design.md §3.4 requires per-premise confidence in the UI, and the sprint's Streamlit
    strip is "confidence bars only". A bar needs a number; parsing it back out of
    `"0.74 (uncalibrated)"` would break silently on a locale, a formatting change, or a
    `nan`. The calibration status travels as a field beside the value, which is what makes
    withholding the number unnecessary.
    """
    scored = [
        row
        for row in to_render_payload(hand_built_graph, fact_lookup).premises
        if row.step_score_value is not None
    ]
    assert scored

    for row in scored:
        assert isinstance(row.step_score_value, float)
        assert 0.0 <= row.step_score_value <= 1.0
        assert row.step_score_calibration is not None
        assert row.step_score == f"{row.step_score_value:.2f} (uncalibrated)"


# -- M7-T1: the three-source retraction policy ----------------------------------------


def _check(source: RetractionSource, result: RetractionFinding) -> RetractionCheck:
    return RetractionCheck(source=source, result=result, checked_at=CHECKED_AT)


def test_the_three_source_retraction_policy_is_representable():
    """M7-T1: "RW-table or both-API agreement → `retracted`; single API source →
    `retraction-flagged-unconfirmed`; disagreements logged", and its exit criterion is
    that "a disagreement case renders as flagged, not retracted".

    A list of asserters could not express any of the three inputs that policy reads. This
    is the disagreement case: OpenAlex says retracted, Crossref checked and says clean, and
    Retraction Watch was never asked. All three are distinguishable, so the cut is
    computable and the disagreement is loggable.
    """
    quality = EvidenceQuality(
        retraction=RetractionStatus.FLAGGED_UNCONFIRMED,
        retraction_checks={
            RetractionSource.OPENALEX: _check(
                RetractionSource.OPENALEX, RetractionFinding.RETRACTED
            ),
            RetractionSource.CROSSREF: _check(
                RetractionSource.CROSSREF, RetractionFinding.CLEAN
            ),
        },
    )

    assert quality.asserting_sources == {RetractionSource.OPENALEX}
    assert RetractionSource.CROSSREF in quality.checked_sources, "checked and clean"
    assert RetractionSource.RETRACTION_WATCH not in quality.checked_sources, "never asked"
    assert quality.has_retraction_disagreement


def test_a_source_with_no_opinion_is_not_a_disagreement():
    """A work absent from an index is not that index contradicting one that found it —
    counting `not-indexed` as clean would let an unindexed DOI outvote a real finding."""
    quality = EvidenceQuality(
        retraction=RetractionStatus.FLAGGED_UNCONFIRMED,
        retraction_checks={
            RetractionSource.OPENALEX: _check(
                RetractionSource.OPENALEX, RetractionFinding.RETRACTED
            ),
            RetractionSource.CROSSREF: _check(
                RetractionSource.CROSSREF, RetractionFinding.NOT_INDEXED
            ),
        },
    )
    assert not quality.has_retraction_disagreement
    assert quality.asserting_sources == {RetractionSource.OPENALEX}


def test_a_retraction_flag_cannot_come_from_nothing():
    """Where the line between retracted and flagged falls is M7-T1's to decide. That a
    work cannot be flagged while every consulted source says clean is not a policy
    question — it is a soundness floor."""
    with pytest.raises(ValidationError):
        EvidenceQuality(
            retraction=RetractionStatus.RETRACTED,
            retraction_checks={
                RetractionSource.CROSSREF: _check(
                    RetractionSource.CROSSREF, RetractionFinding.CLEAN
                )
            },
        )
    with pytest.raises(ValidationError):
        EvidenceQuality(
            retraction=RetractionStatus.CLEAN,
            retraction_checks={
                RetractionSource.OPENALEX: _check(
                    RetractionSource.OPENALEX, RetractionFinding.RETRACTED
                )
            },
        )


def test_unknown_is_the_retraction_default_not_clean():
    """ "Not checked" and "checked and clean" are different claims, and only one of them is
    safe to render. The default is the conservative one — this keeps it that way."""
    assert EvidenceQuality().retraction is RetractionStatus.UNKNOWN


# -- M8-T3: the contested state never becomes a justification -------------------------


def test_a_contested_premise_has_no_path_into_the_alethiology(hand_built_graph: ClaimGraph):
    """design.md §4.2: contested premises "never enter the JTMS as justifications".
    Structurally, the only thing that links a premise to the alethiology is a `Grounding`,
    and `Justification` links facts to facts — so a premise cannot appear as an antecedent
    by any route that does not first make it a fact. That separation is the guarantee;
    this test pins the shape it rests on."""
    from verity.models.fact import Justification

    assert "premise_id" not in Justification.model_fields
    assert "bundle_id" not in Justification.model_fields
    assert set(Justification.model_fields) == {
        "id",
        "consequent_fact_id",
        "antecedent_fact_ids",
        "type",
    }
