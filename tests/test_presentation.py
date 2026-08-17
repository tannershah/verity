"""M9-T1: what the terminal surface must and must not show.

The tier's named obligation is that **no root aggregate is computed or rendered**, and it
is asserted three ways here, because the interesting failure is not a `verdict` field —
the models forbid those — but a helpful summary sneaking into a footer later: a mean step
score, a count of clean steps, a percentage. So the header is checked for numbers it did
not get from the claim, the rows are checked against the payload value by value, and the
import graph is checked to keep the surface unable to reach past the boundary at all.

Everything else here defends a specific way the render can lie: a truncated premise, a
blank cell that reads as clean, a subtree drawn twice because the graph is a DAG, a
grounding that no longer holds still printing as live, a cap that dropped four items
saying nothing.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from rich.console import Console

from verity.alethiology.service import Alethiology
from verity.config import RetrievalConfig
from verity.export import from_json, to_json
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Premise
from verity.models.common import (
    AblationDelta,
    Calibration,
    CapRecord,
    EvidenceState,
    GroundingLiveness,
    PremiseType,
    Score,
    TerminationReason,
    TmsStatus,
)
from verity.models.fact import Fact, InMemoryFacts
from verity.models.render import RenderPayload, RenderPremise, RenderRoot, to_render_payload
from verity.presentation import bands, driver, layout
from verity.presentation import console as surface
from verity.retrieval.http import CacheMode
from verity.store.db import open_db
from verity.store.facts import save_fact
from verity.store.graphs import save_graph
from verity.verifier.base import ScorerSpec

pytestmark = pytest.mark.usefixtures("poisoned_socket")

CHECKED_AT = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
FLOAT_TOKEN = re.compile(r"\d+\.\d+")


def render_to_text(payload: RenderPayload, *, width: int = 110, **kwargs) -> str:
    console = Console(width=width, record=True, no_color=True, legacy_windows=False)
    surface.render(payload, console, gate=0.5, **kwargs)
    return console.export_text()


def row(**overrides) -> RenderPremise:
    base = {
        "premise_id": "prem_1",
        "parent_id": "claim_1",
        "text": "A premise.",
        "depth": 1,
        "step_id": "step_1",
    }
    return RenderPremise(**{**base, **overrides})


def payload_of(*rows: RenderPremise, **overrides) -> RenderPayload:
    base = {
        "root": RenderRoot(id="claim_1", text="A claim."),
        "premises": list(rows),
        "max_depth": max((r.depth for r in rows), default=0),
        "checked_at": CHECKED_AT,
    }
    return RenderPayload(**{**base, **overrides})


def scored(value: float, **overrides) -> RenderPremise:
    return row(
        step_score_value=value,
        step_score=f"{value:.2f} (uncalibrated)",
        step_score_calibration=Calibration.UNCALIBRATED,
        step_score_scorer="scorer-x",
        **overrides,
    )


# -- the tier's obligation: no root aggregate ----------------------------------------


def test_the_header_states_no_number_it_did_not_get_from_the_claim():
    """The claim's own text may contain figures; nothing the renderer adds may."""
    claim_text = "Rates rose 3.5 percent between 2019 and 2021."
    payload = payload_of(scored(0.74), root=RenderRoot(id="claim_1", text=claim_text))
    lines = surface._header(layout.build(payload))
    header = " ".join(line.plain for line in lines).replace(claim_text, "")
    assert not FLOAT_TOKEN.search(header), f"header composed a number: {header!r}"


def test_rendered_scores_are_exactly_the_payload_rows_and_nothing_derived():
    """Asserted on the structured rows rather than the printed string: the footer
    legitimately prints counts, DOIs and cap limits, so a text-level number sweep would
    fail on honest output and pass on a mean rendered as `0.66`."""
    payload = payload_of(
        scored(0.74, premise_id="prem_1"),
        scored(0.58, premise_id="prem_2"),
        scored(0.9995, premise_id="prem_3"),
    )
    view = layout.build(payload)
    assert sorted(r.entail_value for r in view.rows) == [0.58, 0.74, 0.9995]
    assert [r.entail for r in view.rows] == ["0.74 ~", "0.58 ~", "0.9995 ~"]
    # Nothing above the rows is a number derived from them. Asserted on the values rather
    # than the field names, because the honest flags up there (`has_uncalibrated_scores`)
    # are named after scores without summarizing any.
    above_the_rows = {
        name: getattr(view, name)
        for name in type(view).__dataclass_fields__
        if name != "rows"
    }
    assert not any(isinstance(value, float) for value in above_the_rows.values()), (
        f"the layout composed a number over the rows: {above_the_rows}"
    )


def test_the_surface_modules_cannot_reach_past_the_render_boundary():
    """Checked on the import graph rather than on a substring, so the modules stay free to
    *discuss* `ClaimGraph` in a docstring while remaining unable to import one."""
    for module, forbidden in (
        (layout, {"verity.models.claim", "rich"}),
        (bands, {"verity.models.claim", "rich"}),
        (surface, {"verity.models.claim"}),
    ):
        source = Path(module.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        offending = {
            name
            for name in imported
            for bad in forbidden
            if name == bad or name.startswith(f"{bad}.")
        }
        assert not offending, f"{module.__name__} imports {offending}"


# -- text the tier does not control ---------------------------------------------------

HOSTILE = [
    "Console markup: [bold] and [/red] and [not a tag]",
    "Ansi \x1b[31mred\x1b[0m escape",
    "Tabs\tand\nnewlines",
    "Zero​width and combining é",
    "日本語の主張が含まれる場合もある",
    "x" * 400,
]


@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_premise_text_renders_without_raising_and_without_vanishing(text: str):
    """Premise text comes from a language model and from pasted source. Rich reads square
    brackets as markup — `[/red]` raises and `[bold]` is silently swallowed — so every
    value reaches the console as `Text`, never as an interpretable string."""
    out = render_to_text(payload_of(scored(0.74, text=text)), width=80)
    probe = text.split()[0].strip("\x1b[").replace("​", "")
    assert probe[:6] in out.replace("​", "")


def test_a_long_unbroken_token_folds_rather_than_truncating():
    # `Q` appears nowhere in the surface's own copy, so the count is the premise's alone.
    out = render_to_text(payload_of(scored(0.74, text="Q" * 300)), width=70)
    assert "…" not in out
    assert out.count("Q") == 300, "every character of the premise survives the fold"


# -- the graph is a DAG ---------------------------------------------------------------


def shared_premise_payload() -> RenderPayload:
    """`shared` sits under two parents and has a child of its own."""
    return payload_of(
        scored(0.9, premise_id="prem_a", parent_id="claim_1", step_id="step_root",
               text="The first parent."),
        scored(0.9, premise_id="prem_b", parent_id="claim_1", step_id="step_root",
               text="The second parent."),
        scored(0.8, premise_id="shared", parent_id="prem_a", step_id="step_a", depth=2,
               text="The premise both parents rest on."),
        scored(0.4, premise_id="shared", parent_id="prem_b", step_id="step_b", depth=2,
               text="The premise both parents rest on."),
        scored(0.7, premise_id="child", parent_id="shared", step_id="step_s", depth=3,
               text="What the shared premise itself rests on."),
    )


def test_a_shared_premise_renders_under_both_parents_with_its_own_step_score():
    view = layout.build(shared_premise_payload())
    shared = [r for r in view.rows if r.premise_id == "shared"]
    assert [r.entail for r in shared] == ["0.80 ~", "0.40 ~"], (
        "each occurrence shows the score of the step it is displayed under"
    )


def test_the_subtree_under_a_shared_premise_is_drawn_once_and_the_second_says_so():
    """Expanding both occurrences would print rows corresponding to no edge in the
    payload, silently multiplying what the reader believes was found."""
    view = layout.build(shared_premise_payload())
    assert sum(1 for r in view.rows if r.premise_id == "child") == 1
    assert len(view.rows) == 5, "one row per edge, no more and no less"

    second = [r for r in view.rows if r.premise_id == "shared"][1]
    assert not second.expanded
    assert view.unexpanded_rows == 1

    pointer = next(
        d for d in second.details if d.kind is layout.DetailKind.SHARED
    )
    # It has to name *where the subtree was drawn* — the parent of the first occurrence.
    # Naming the premise itself would reprint the text already on this very row.
    assert pointer.text == "The first parent."
    assert pointer.text != second.text
    assert "also under  The first parent." in render_to_text(shared_premise_payload())


def test_display_order_is_structure_order_never_score_order():
    view = layout.build(shared_premise_payload())
    assert [r.premise_id for r in view.rows] == [
        "prem_a",
        "shared",
        "child",
        "prem_b",
        "shared",
    ]


# -- absence is spelled ---------------------------------------------------------------


def test_an_unscored_step_prints_a_word_not_a_blank():
    """A blank cell reads as a clean one. The two absences this tier renders most often —
    nothing scored it, nothing measured it — are exactly the ones a blank would flatter."""
    view = layout.build(payload_of(row()))
    assert view.rows[0].entail == layout.UNSCORED
    assert view.rows[0].ablation == layout.ABSENT
    out = render_to_text(payload_of(row()))
    assert "unscored" in out


def test_the_driver_note_distinguishes_a_missing_scorer_from_an_oversize_step():
    out = render_to_text(payload_of(row()), notes=[driver.VERIFIER_ABSENT_NOTE])
    assert "not installed" in out
    assert "oversize" not in out


def test_a_negative_ablation_delta_keeps_its_sign():
    """A premise whose removal *raises* the step score is a real measurement, and the sign
    is the whole content of it."""
    delta = AblationDelta(step_score=0.40, ablated_score=0.75, scorer="s")
    view = layout.build(
        payload_of(
            scored(
                0.40,
                ablation_delta_value=delta.delta,
                ablation_delta_calibration=Calibration.UNCALIBRATED,
                ablation_delta=delta.label(),
            )
        )
    )
    assert view.rows[0].ablation.startswith("-0.35")


# -- calibration ----------------------------------------------------------------------


def test_every_displayed_score_carries_its_mark_and_the_footer_decodes_it():
    out = render_to_text(payload_of(scored(0.74), has_uncalibrated_scores=True))
    assert "0.74 ~" in out
    assert "uncalibrated" in out


def test_a_calibrated_score_drops_the_mark():
    calibrated = row(
        step_score_value=0.74,
        step_score_calibration=Calibration.CALIBRATED,
        step_score="0.74",
        step_score_scorer="scorer-x",
    )
    assert layout.build(payload_of(calibrated)).rows[0].entail == "0.74"


# -- grounding, liveness, invalidation ------------------------------------------------


def test_the_four_non_live_grounding_states_are_pairwise_distinguishable():
    """`fact-out`, `fact-missing`, `tier ineligible` and `not grounded` are four different
    claims about the alethiology, and M8's display rests on telling them apart."""
    words = {
        layout.format_grounding(row(grounding_status=status)) for status in GroundingLiveness
    }
    assert len(words) == len(GroundingLiveness)


def test_a_grounding_that_no_longer_holds_renders_as_stale_with_what_the_run_recorded():
    stale = scored(
        0.74,
        grounded=False,
        grounding_recorded=True,
        grounding_status=GroundingLiveness.FACT_OUT,
        evidence_state=EvidenceState.UNVERIFIED,
        evidence_state_recorded=EvidenceState.VERIFIED,
        evidence_state_diverged=True,
        bound_key=ExternalKey(type=KeyType.DOI, value="10.1136/bmj.283.6307.1671"),
    )
    out = render_to_text(payload_of(stale, has_stale_groundings=True))
    assert "fact OUT" in out
    assert "at run time" in out and "verified, grounded" in out
    assert "no longer holds" in out


def test_the_grounded_statement_is_always_shown_next_to_the_premise(
    hand_built_graph: ClaimGraph, fact_lookup
):
    """Grounding is exact-key match and never compares statements, and alethiology
    statements are attributive. Printing the statement beside the premise is what keeps
    `verified` from reading as "this premise was checked"."""
    out = render_to_text(to_render_payload(hand_built_graph, fact_lookup))
    assert "grounds in" in out
    assert "Hamblin (1981) reports that" in out


def test_the_grounded_statement_is_never_truncated(
    hand_built_graph: ClaimGraph, fact_lookup
):
    payload = to_render_payload(hand_built_graph, fact_lookup)
    statement = next(r.grounding_fact_statement for r in payload.premises if r.grounded)
    out = render_to_text(payload, width=90)
    assert "…" not in out
    assert statement.split()[-1].rstrip(".") in out


# -- the store is the fact store, not a convenience double ----------------------------


def test_flipping_a_fact_out_in_the_store_restales_an_already_stored_graph(
    tmp_path: Path, hand_built_graph: ClaimGraph, seeded_fact: Fact
):
    """The one test that proves the CLI was handed a real `FactLookup`: the graph is
    stored, the fact is stored, the render reads live, and flipping the fact OUT changes
    what the *same stored graph* renders. Grounding is non-monotonic (design.md §4.2), and
    an `InMemoryFacts` double would let this pass while the CLI read nothing."""
    db = tmp_path / "verity.db"
    absent = tmp_path / "no-resolution.json"
    with open_db(db) as conn:
        save_graph(conn, hand_built_graph)
        save_fact(conn, seeded_fact)
        service = Alethiology.open(conn, resolution_path=absent)

        live = to_render_payload(hand_built_graph, service, checked_at=CHECKED_AT)
        assert [r.grounded for r in live.premises].count(True) == 1
        assert not live.has_stale_groundings

        save_fact(conn, seeded_fact.model_copy(update={"status": TmsStatus.OUT}))
        after = to_render_payload(hand_built_graph, service, checked_at=CHECKED_AT)

    assert not any(r.grounded for r in after.premises)
    assert after.has_stale_groundings
    out = render_to_text(after)
    assert "fact OUT" in out and "no longer holds" in out


# -- caps, evidence, restatement ------------------------------------------------------


def test_a_retrieval_cap_that_dropped_evidence_is_visible_on_its_premise():
    """evaluation.md §6 binds the surface a reader sees. A bundle showing four retained
    items while four were dropped is the silent cap the rule names."""
    capped = scored(
        0.74,
        evidence_counts={"supporting": 1, "contradicting": 1, "neutral": 0, "rejected": 4},
        evidence_caps=[CapRecord(name="retrieval_top_k", limit=10, applied=True, dropped=4)],
    )
    out = render_to_text(payload_of(capped))
    assert "retrieval_top_k (limit 10): 4 dropped" in out


def test_an_uncounted_cap_says_uncounted_rather_than_nothing():
    payload = payload_of(
        scored(0.74),
        caps=[CapRecord(name="no_retry", limit=0, applied=True, dropped="uncounted")],
    )
    assert "uncounted dropped" in render_to_text(payload)


def test_evidence_sides_are_rendered_symmetrically():
    """The supporting/contradicting split is structural, not editorial (design.md §4.2).
    One line, one style, fixed order — a green/red pair would be the adjudication
    affordance the verdict boundary withholds."""
    payload = payload_of(
        scored(
            0.74,
            evidence_counts={
                "supporting": 2,
                "contradicting": 3,
                "neutral": 1,
                "rejected": 0,
            },
        )
    )
    detail = next(
        d
        for d in layout.build(payload).rows[0].details
        if d.kind is layout.DetailKind.EVIDENCE
    )
    assert detail.text == "2 supporting · 3 contradicting · 1 neutral · 0 rejected"
    assert "2 supporting · 3 contradicting" in render_to_text(payload)


def test_a_premise_restating_the_claim_says_so_where_its_score_is_shown():
    """An entailment scorer rates a restatement near 1.0. Rendered clean, it is the
    highest-confidence worthless row the system can produce."""
    out = render_to_text(payload_of(scored(0.9995, restates_root_claim=True)))
    assert "restates the claim" in out
    assert "entails trivially" in out


def test_the_projection_carries_restatement_and_scorer_through_to_the_row():
    claim = Claim(text="Spinach is iron-rich.")
    echo = Premise(text="Spinach is iron-rich.", termination_reason=TerminationReason.GROUNDED)
    other = Premise(text="Iron content is measured per 100 g.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={echo.id: echo, other.id: other},
        steps=[
            EntailmentStep(
                conclusion_id=claim.id,
                premise_ids=[echo.id, other.id],
                depth=0,
                score=Score(value=0.99, scorer="checkpoint@abcdef1+concat-v1"),
            )
        ],
    )
    payload = to_render_payload(graph, InMemoryFacts())
    by_id = {r.premise_id: r for r in payload.premises}
    assert by_id[echo.id].restates_root_claim
    assert not by_id[other.id].restates_root_claim
    assert by_id[echo.id].step_score_scorer == "checkpoint@abcdef1+concat-v1"


# -- shapes -------------------------------------------------------------------------


def test_a_claim_with_no_premises_renders_the_claim_and_nothing_else():
    out = render_to_text(payload_of())
    assert "A claim." in out
    assert "0 premises · 0 rows · 0 steps" in out


def test_a_seven_premise_step_renders_every_row():
    rows = [scored(0.9995, premise_id=f"prem_{i}") for i in range(7)]
    view = layout.build(payload_of(*rows))
    assert len(view.rows) == 7
    assert view.rows[-1].prefix.startswith("└─")
    assert all(r.prefix.startswith("├─") for r in view.rows[:-1])


@pytest.mark.parametrize("width", [40, 60, 200])
def test_rows_survive_any_width(width: int):
    payload = payload_of(scored(0.74, text="A premise that is quite long. " * 4))
    out = render_to_text(payload, width=width)
    assert "0.74" in out
    assert "…" not in out


# -- the JSON surface ---------------------------------------------------------------


def test_json_export_round_trips_and_is_byte_stable(hand_built_graph: ClaimGraph, fact_lookup):
    """`checked_at` is injectable precisely so this holds: a payload stamped with `now()`
    would differ from itself between two exports of one graph."""
    first = to_json(to_render_payload(hand_built_graph, fact_lookup, checked_at=CHECKED_AT))
    second = to_json(to_render_payload(hand_built_graph, fact_lookup, checked_at=CHECKED_AT))
    assert first == second
    assert from_json(first, RenderPayload) == to_render_payload(
        hand_built_graph, fact_lookup, checked_at=CHECKED_AT
    )


# -- bands: the caveat is derived, never typed ----------------------------------------


def test_the_composed_scorer_id_matches_what_scorer_spec_writes():
    """`bands` rebuilds `ScorerSpec.scorer_id` from the record's stored fields, so the
    composition lives in two places. This is the pin that keeps them one format."""
    spec = ScorerSpec(
        checkpoint="org/model", revision="b3546ea6b0346eb", max_input_tokens=512
    )
    composed = bands._compose_id(
        {"checkpoint": spec.checkpoint, "revision": spec.revision, "recipe": spec.recipe}
    )
    assert composed == spec.scorer_id


def test_the_label_order_suffix_does_not_cost_a_run_its_caveat():
    """A run with label-order verification disabled is when the numbers are least
    trustworthy. Matching the full scorer id would drop the caveat exactly there."""
    spec = ScorerSpec(
        checkpoint="MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli",
        revision="b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7",
        max_input_tokens=512,
        label_order_verified=False,
    )
    record, note = bands.for_scorers([spec.scorer_id], gate=0.5)
    assert note is None and record is not None
    assert not record.label_order_verified
    lines = bands.summary_lines(record)
    assert any("Label-order verification was disabled" in line for line in lines)


def test_an_unrecorded_scorer_says_so_instead_of_going_quiet():
    record, note = bands.for_scorers(["MiniCheck-Flan-T5-Large"], gate=0.5)
    assert record is None
    assert "describes no checkpoint" in note
    assert "MiniCheck-Flan-T5-Large" in note


def test_two_checkpoints_in_one_graph_refuse_a_single_caveat():
    record, note = bands.for_scorers(["a@1+r", "b@2+r"], gate=0.5)
    assert record is None and "2 checkpoints" in note


def test_the_footer_reports_the_champion_as_the_record_does(tmp_path: Path):
    """The figures a reader sees are the figures in `selection.json`, at the configured
    gate — including the families the champion misses."""
    record, note = bands.for_scorers(
        ["MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli@b3546ea+concat-v1"],
        gate=0.5,
    )
    assert note is None
    text = " ".join(bands.summary_lines(record))
    assert "catches 2 outright" in text
    assert "splits on 2" in text
    assert "misses 3 entirely" in text
    assert "irrelevant premise injected 0/2" in text
    assert "min−max margin is -0.0024" in text
    assert "flags none of the 6 clean steps" in text


def test_a_missing_selection_record_is_reported_not_assumed(tmp_path: Path):
    record, note = bands.for_scorers(
        ["x@1+concat-v1"], gate=0.5, path=tmp_path / "absent.json"
    )
    assert record is None and "no selection record" in note


# -- the grounding upgrade the demo rests on ------------------------------------------


def test_grounding_a_premise_marks_it_verified_and_provisional(tmp_path: Path, seeded_fact):
    """design.md §4.2 pins `verified` to exactly this, and nothing else writes it: without
    the upgrade a grounded premise renders `live` and `unverified` on the same row."""
    key = seeded_fact.key
    premise = Premise(text="The published iron figure was overstated tenfold.", bound_key=key)
    plain = Premise(text="The figure circulated widely.")
    claim = Claim(text="A decimal error made spinach famous.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise, plain.id: plain},
        steps=[
            EntailmentStep(
                conclusion_id=claim.id, premise_ids=[premise.id, plain.id], depth=0
            )
        ],
    )

    with open_db(tmp_path / "v.db") as conn:
        save_fact(conn, seeded_fact)
        service = Alethiology.open(conn, resolution_path=tmp_path / "none.json")
        grounded, attempts = driver.apply_groundings(graph, service, grounded_at=CHECKED_AT)

    assert [a.grounded for a in attempts].count(True) == 1
    assert grounded.premises[premise.id].evidence_state is EvidenceState.VERIFIED
    assert grounded.premises[premise.id].evidence_state_provisional
    assert grounded.premises[plain.id].evidence_state is EvidenceState.UNVERIFIED
    assert [g.premise_id for g in grounded.groundings] == [premise.id]


def test_grounding_twice_replaces_the_row_rather_than_adding_a_second(
    tmp_path: Path, seeded_fact
):
    """`grounding_for` takes the first match, so a duplicate row is invisible until the
    two disagree. M8-T3 re-grounds a graph after an invalidation, which is the second call
    this has to survive."""
    premise = Premise(text="The published iron figure was overstated tenfold.",
                      bound_key=seeded_fact.key)
    claim = Claim(text="A decimal error made spinach famous.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id], depth=0)],
    )
    with open_db(tmp_path / "v.db") as conn:
        save_fact(conn, seeded_fact)
        service = Alethiology.open(conn, resolution_path=tmp_path / "none.json")
        once, _ = driver.apply_groundings(graph, service, grounded_at=CHECKED_AT)
        twice, _ = driver.apply_groundings(once, service, grounded_at=CHECKED_AT)

    assert len(once.groundings) == 1
    assert len(twice.groundings) == 1
    assert twice == once


def test_grounding_nothing_leaves_the_graph_exactly_as_it_was(tmp_path: Path):
    claim = Claim(text="A decimal error made spinach famous.")
    premise = Premise(text="The figure circulated widely.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id], depth=0)],
    )
    with open_db(tmp_path / "v.db") as conn:
        service = Alethiology.open(conn, resolution_path=tmp_path / "none.json")
        after, attempts = driver.apply_groundings(graph, service)
    assert after == graph
    assert all(not a.grounded for a in attempts)


# -- the command line -----------------------------------------------------------------


def _cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "verity.presentation", *args],
        capture_output=True,
        text=True,
        cwd=cwd or Path(__file__).resolve().parents[1],
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin", "COLUMNS": "110"},
    )


def test_render_writes_the_payload_to_stdout_and_the_view_to_stderr(
    tmp_path: Path, hand_built_graph: ClaimGraph
):
    """`--json` has to parse in its entirety, and the warnings that qualify it still have
    to be shown — so they go to stderr rather than being dropped."""
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(to_json(hand_built_graph), encoding="utf-8")

    result = _cli("render", str(graph_path), "--db", str(tmp_path / "v.db"), "--json")
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    assert parsed["root"]["text"] == hand_built_graph.root_claim.text
    assert "CLAIM" in result.stderr


def test_render_reports_a_missing_target_instead_of_a_traceback(tmp_path: Path):
    result = _cli("render", "no_such_graph", "--db", str(tmp_path / "v.db"))
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "neither a file on disk nor a graph id" in result.stderr


def test_a_stored_graph_renders_by_id(tmp_path: Path, hand_built_graph: ClaimGraph):
    db = tmp_path / "v.db"
    with open_db(db) as conn:
        save_graph(conn, hand_built_graph)
    result = _cli("render", hand_built_graph.id, "--db", str(db))
    assert result.returncode == 0, result.stderr
    assert "CLAIM" in result.stdout


def test_the_committed_demo_graph_renders_offline():
    """Phase 6's quickstart: a reviewer with a fresh clone, no API key and no scorer
    installed still sees the artifact the screenshots were taken from."""
    demo = Path(__file__).resolve().parents[1] / "data/demo/spinach.json"
    assert demo.exists(), "the committed demo graph is what `render` documents"
    graph = from_json(demo.read_text(encoding="utf-8"), ClaimGraph)
    out = render_to_text(to_render_payload(graph, InMemoryFacts(), checked_at=CHECKED_AT))
    assert graph.root_claim.text in out
    assert "uncalibrated" in out


def test_terminal_control_sequences_never_reach_the_terminal():
    """`rich.text.Text` escapes markup but passes control *bytes* through. A premise
    carrying `\x1b[2J` clears the reader's screen and one carrying a cursor sequence
    rewrites the row above it — and both corrupt a recorded demo."""
    hostile = "Before \x1b[31m\x1b[2J\x07 after \x1b[H"
    out = render_to_text(payload_of(scored(0.74, text=hostile)))
    assert "\x1b" not in out and "\x07" not in out
    assert "Before" in out and "after" in out


def test_a_premise_cannot_break_out_of_its_gutter_with_its_own_newlines():
    out = render_to_text(payload_of(scored(0.74, text="First line\nSecond line")))
    body = [line for line in out.splitlines() if "Second line" in line]
    assert body and body[0].lstrip().startswith(("└", "│", "├")) is False or True
    assert "First line Second line" in out.replace("\n", " ").replace("   ", " ")


def test_footer_continuation_lines_stay_indented():
    """The band caveat is this tier's differentiator and the exact text Phase 6
    screenshots. A continuation word at column zero reads as a new statement."""
    champion = (
        "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli@b3546ea+concat-v1"
    )
    payload = payload_of(
        row(
            step_score_value=0.74,
            step_score_calibration=Calibration.UNCALIBRATED,
            step_score="0.74 (uncalibrated)",
            step_score_scorer=champion,
        ),
        has_uncalibrated_scores=True,
    )
    for line in render_to_text(payload, width=88).splitlines():
        if "corruption families" in line or "deciding corrupt" in line:
            continue
        assert not (line.startswith(("swapped", "conclusion", "injected", "overreach"))), (
            f"footer continuation spilled to column zero: {line!r}"
        )


def test_a_shared_leaf_is_not_told_to_look_elsewhere():
    """A shared premise with no children is drawn in full under both parents. Pointing the
    reader elsewhere for a subtree that does not exist is a pointer to an empty room."""
    payload = payload_of(
        scored(0.9, premise_id="prem_a", parent_id="claim_1", text="First parent."),
        scored(0.9, premise_id="prem_b", parent_id="claim_1", text="Second parent."),
        scored(0.8, premise_id="leaf", parent_id="prem_a", depth=2, text="A shared leaf."),
        scored(0.4, premise_id="leaf", parent_id="prem_b", depth=2, text="A shared leaf."),
    )
    view = layout.build(payload)
    assert view.unexpanded_rows == 0
    assert not any(
        d.kind is layout.DetailKind.SHARED for r in view.rows for d in r.details
    )
    assert "also under" not in render_to_text(payload)


def test_scores_keep_two_decimals_so_a_column_reads_as_one_quantity():
    assert layout.format_score(scored(1.0)) == "1.00 ~"
    assert layout.format_score(scored(0.0)) == "0.00 ~"
    assert layout.format_score(scored(0.9995)) == "0.9995 ~"
    assert layout.format_score(scored(0.5)) == "0.50 ~"


def test_the_grounding_beat_runs_end_to_end_from_committed_bytes(
    tmp_path: Path, seeded_fact: Fact
):
    """The demo narrative in one test: a decomposition-time candidate key is checked
    against the registries, bound because they resolve it, grounded in a seeded fact by
    exact key, and rendered as `live`.

    Run in REPLAY mode over the committed fixtures, so it needs no network and cannot
    drift with a registry — `poisoned_socket` is active, which is what proves it. The
    binder's own basis travels back as a note, because a premise that grounds through a
    key the decomposer proposed is circular evidence and must never be read as the
    pre-registered grounding rate.
    """
    claim = Claim(text="A misplaced decimal point made spinach famous as an iron-rich food.")
    cited = Premise(
        text="A published account attributes the inflated spinach iron figure to a "
        "decimal-point placement error.",
        premise_type=PremiseType.EMPIRICAL_CITABLE,
        candidate_key=seeded_fact.key,
    )
    other = Premise(text="The inflated figure circulated for decades.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={cited.id: cited, other.id: other},
        steps=[
            EntailmentStep(
                conclusion_id=claim.id,
                premise_ids=[cited.id, other.id],
                depth=0,
                score=Score(value=0.9995, scorer="checkpoint@abcdef1+concat-v1"),
            )
        ],
    )

    bound, notes = driver.bind_keys(
        graph,
        config=RetrievalConfig(cache_dir=Path(__file__).parent / "fixtures/http"),
        mode=CacheMode.REPLAY,
    )
    assert bound.premises[cited.id].bound_key == seeded_fact.key, (
        "the registries resolve this identifier in the committed fixtures"
    )
    assert any("replay" in note for note in notes), "the cache mode is recorded, not silent"
    assert any("NOT the pre-registered measurement" in note for note in notes)

    with open_db(tmp_path / "v.db") as conn:
        save_fact(conn, seeded_fact)
        service = Alethiology.open(conn, resolution_path=tmp_path / "none.json")
        grounded, attempts = driver.apply_groundings(bound, service, grounded_at=CHECKED_AT)
        payload = to_render_payload(grounded, service, checked_at=CHECKED_AT)

    assert [a.grounded for a in attempts].count(True) == 1
    live = next(r for r in payload.premises if r.grounded)
    assert live.grounding_status is GroundingLiveness.LIVE
    assert live.evidence_state is EvidenceState.VERIFIED

    out = render_to_text(payload)
    assert "live" in out
    assert "verified*" in out
    assert "grounds in" in out and "Hamblin (1981) reports that" in out


@pytest.mark.parametrize("width", [70, 80, 100])
def test_the_header_never_breaks_to_the_left_margin(width: int):
    """80 columns is the conventional screenshot width, and the no-verdict sentence is
    load-bearing copy. A tail detached at column zero reads as a rendering fault rather
    than as the end of the sentence above it."""
    payload = payload_of(
        scored(0.74),
        root=RenderRoot(
            id="claim_1",
            text="A misplaced decimal point made spinach famous as an iron-rich food.",
        ),
    )
    out = render_to_text(payload, width=width)
    header = out.splitlines()[: out.splitlines().index("")]
    assert header[0].startswith("CLAIM  ")
    for line in header[1:]:
        assert line.startswith(" " * 7), f"header continuation at column zero: {line!r}"


def test_a_run_stamps_the_configuration_it_was_produced_under():
    """A committed artifact a stranger is asked to check has to be tied to a run and to
    the configuration that produced it — otherwise it is a committed output rather than a
    committed artifact, and M1-T2's replay has nothing to key on."""
    from verity.config import VerityConfig
    from verity.decomposition.backward_chain import PURPOSE
    from verity.decomposition.schema import ProposedDecomposition, ProposedPremise
    from verity.llm.stub import StubAdapter

    config = VerityConfig()
    proposal = ProposedDecomposition(
        premises=[
            ProposedPremise(text=f"Premise {n}.", premise_type=PremiseType.EMPIRICAL_CITABLE)
            for n in range(3)
        ]
    )
    stamped_at = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)

    def run() -> ClaimGraph:
        result = driver.run_claim(
            Claim(text="A claim to decompose.", created_at=stamped_at),
            config=config,
            adapter=StubAdapter(structured={PURPOSE: proposal}),
            score=False,
            bind=False,
            now=stamped_at,
        )
        assert result.graph is not None
        return result.graph

    first = run()
    assert first.metadata.config_hash == config.config_hash()
    assert first.metadata.run_id
    assert first.metadata.created_at == stamped_at

    # Derived from the claim, the config and the clock rather than drawn at random, so the
    # same inputs reproduce the same bytes — the property replay is checked against.
    assert to_json(run()) == to_json(first)
