"""Payload to display rows: ordering, tree position, and the strings a surface prints.

Everything here is a pure function of a `RenderPayload`. It imports neither `rich` nor
`ClaimGraph` — the first so the layout can be asserted on without a console, the second
because reaching past the render boundary is exactly what that boundary exists to prevent.
A test pins both absences.

**One row per edge, and the edge is drawn once.** The payload is per-(step, premise) and
the graph is a DAG, so a premise reached from two steps has two rows carrying two
different step scores. Walking children by `parent_id` naively would redraw that premise's
whole subtree under each parent — output corresponding to no row in the payload, silently
multiplying what the reader believes was found. So a node's children are expanded at its
first occurrence only; later occurrences render their own row, carrying their own step's
score, and say where the subtree was drawn instead of dropping it wordlessly
(evaluation.md §6).

**Indentation is tree position, never `row.depth`.** `walk()` is breadth-first and assigns
a shared premise the depth of its shallowest parent; these rows are re-ordered
depth-first, so the payload's depth and the printed nesting are different numbers. Depth
is reported once, as the graph's, and labelled as traversal depth — the payload carries no
descent depth, and printing a traversal number next to a `budget-exit` reason invites the
reading that it was measured against the budget.

**Absence is spelled, never blank.** An unscored step prints `unscored` and a missing
ablation delta prints an em dash. A blank cell reads as a clean one, and the two states
this tier renders most often — nothing scored it yet, nothing measured it yet — are
precisely the ones a blank would flatter.

Rows are frozen dataclasses rather than pydantic models on purpose: they are display
structures, not records, and nothing persists or transports them.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from verity.models.common import Calibration, CapRecord, GroundingLiveness
from verity.models.render import RenderPayload, RenderPremise

#: Printed where a number does not exist yet. Distinct from `0`, and distinct from blank.
ABSENT = "—"
UNSCORED = "unscored"
#: Appended to every uncalibrated number. Decoded once, in the footer.
UNCALIBRATED_MARK = "~"

#: C0 and C1 control characters, minus nothing — every one of them is stripped from text
#: this tier did not write. A premise carrying `\x1b[2J` clears the reader's terminal, and
#: one carrying a cursor-position sequence rewrites the row above it; both survive
#: `rich.text.Text`, which escapes markup but treats control *bytes* as ordinary
#: characters. Stripping is deliberate rather than interpreting them (`Text.from_ansi`
#: would render the colours the string asks for, which is the same defect with better
#: manners): the premise is evidence, and evidence does not get to style the page.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def sanitize(text: str) -> str:
    """Strip terminal control sequences from text this tier did not author.

    Tabs and newlines go too: the layout owns line breaks, and a premise that supplies its
    own would break out of its gutter. They become spaces, so the words stay separated.
    """
    return _CONTROL_CHARS.sub("", text.replace("\t", " ").replace("\n", " "))


_GROUNDING_WORDS: dict[GroundingLiveness, str] = {
    GroundingLiveness.NOT_GROUNDED: "not grounded",
    GroundingLiveness.LIVE: "live",
    GroundingLiveness.FACT_MISSING: "fact missing",
    GroundingLiveness.FACT_OUT: "fact OUT",
    GroundingLiveness.FACT_INELIGIBLE_TIER: "tier ineligible",
}

#: Flag suffixes `to_render_payload` emits, mapped to what a reader is being told. The two
#: are different claims — M7-T1's exit criterion is that a disagreement between sources
#: renders as flagged rather than retracted — so they never share a word or a glyph.
_RETRACTION_WORDS = {
    "retracted": "retracted",
    "retraction-flagged-unconfirmed": "retraction flagged, unconfirmed",
}


class DetailKind(StrEnum):
    """What a sub-line under a premise is saying.

    A surface may style these differently; none may be dropped, and none may be conveyed
    by styling alone — every kind carries its own words.
    """

    RESTATEMENT = "restatement"
    RETRACTION = "retraction"
    SHARED = "shared"
    TERMINATION = "termination"
    GROUNDING = "grounding"
    DIVERGENCE = "divergence"
    EVIDENCE = "evidence"
    CAP = "cap"


@dataclass(frozen=True)
class Detail:
    """One labelled sub-line. `text` is literal — no surface may interpret it as markup."""

    kind: DetailKind
    label: str
    text: str


@dataclass(frozen=True)
class Row:
    """One edge of the graph, positioned in the tree and formatted for a column layout."""

    premise_id: str
    text: str
    prefix: str
    """Tree glyphs preceding the premise text on its first line."""
    continuation: str
    """Gutter for this row's wrapped lines and sub-lines."""
    entail: str
    entail_value: float | None
    ablation: str
    state: str
    grounding: str
    details: tuple[Detail, ...] = ()
    expanded: bool = True
    """False when this premise's subtree was drawn under an earlier occurrence."""


@dataclass(frozen=True)
class Layout:
    """Everything a surface needs, with no number above the rows.

    There is deliberately no field here that summarizes the rows: counts describe the
    graph's shape, not its credibility, and nothing in this module composes a score.
    """

    root_id: str
    root_text: str
    rows: tuple[Row, ...]
    node_count: int
    row_count: int
    step_count: int
    graph_depth: int
    checked_at: datetime
    caps: tuple[CapRecord, ...] = ()
    scorers: tuple[str, ...] = ()
    has_uncalibrated_scores: bool = False
    has_stale_groundings: bool = False
    unexpanded_rows: int = 0


def format_score(row: RenderPremise) -> str:
    """The step's score as a column cell.

    Printed at the precision it was stored at rather than padded to a fixed width: the
    scorer rounds to four decimals because more is not reproducible across devices, and
    padding `0.74` to `0.7400` would invent the difference. An uncalibrated number always
    carries its mark.
    """
    if row.step_score_value is None:
        return UNSCORED
    calibrated = row.step_score_calibration is Calibration.CALIBRATED
    number = _number(row.step_score_value)
    return f"{number}{'' if calibrated else f' {UNCALIBRATED_MARK}'}"


def _number(value: float, *, sign: bool = False) -> str:
    """Stored precision, with a floor of two decimals.

    Trailing zeros are dropped because the scorer stores four decimals and padding every
    number to four would invent agreement it does not have — but a bare `1` beside a
    column of `0.9995` reads as a different kind of quantity, so two decimals is the
    floor.
    """
    text = f"{value:{'+' if sign else ''}.4f}".rstrip("0")
    whole, _, fraction = text.partition(".")
    return f"{whole}.{fraction.ljust(2, '0')}"


def format_ablation(row: RenderPremise) -> str:
    """The leave-one-out delta, signed.

    Positive means removing this premise *lowers* its step's score — the premise is
    load-bearing. The sign is the whole content of the measurement, so it is always
    printed, and the column is headed for what it measures rather than named after the
    technique.
    """
    if row.ablation_delta_value is None:
        return ABSENT
    calibrated = row.ablation_delta_calibration is Calibration.CALIBRATED
    number = _number(row.ablation_delta_value, sign=True)
    return f"{number}{'' if calibrated else f' {UNCALIBRATED_MARK}'}"


def format_state(row: RenderPremise) -> str:
    """Evidence state as displayed now, marked while the semantics are provisional."""
    word = row.evidence_state.value
    return f"{word}*" if row.evidence_state_provisional else word


def format_grounding(row: RenderPremise) -> str:
    return _GROUNDING_WORDS[row.grounding_status]


def _retraction_detail(flag: str) -> Detail:
    """Split `"<key>: <status>"` into a labelled line without losing an unknown status.

    `to_render_payload` composes these strings, so the split is a display concern rather
    than a parse of foreign data — but an unrecognized status is printed verbatim instead
    of being dropped or rounded to the more alarming word.
    """
    key, _, status = flag.rpartition(": ")
    label = _RETRACTION_WORDS.get(status, status or flag)
    return Detail(kind=DetailKind.RETRACTION, label=label, text=key or flag)


def _details(row: RenderPremise, *, shared_with: str | None) -> tuple[Detail, ...]:
    """Sub-lines for one row, alarms first.

    Order is fixed rather than data-dependent: a restatement and a retraction are what a
    reader most needs to see before reading the premise's supporting apparatus, and a
    layout that ordered by whichever field happened to be populated would move them.
    """
    details: list[Detail] = []

    if row.restates_root_claim:
        details.append(
            Detail(
                kind=DetailKind.RESTATEMENT,
                label="restates the claim",
                text="this step entails trivially and its score does not measure the "
                "decomposition",
            )
        )
    for flag in row.retraction_flags:
        details.append(_retraction_detail(flag))
    if shared_with is not None:
        details.append(
            Detail(
                kind=DetailKind.SHARED,
                label="also under",
                text=shared_with,
            )
        )

    context = []
    if row.termination_reason is not None:
        context.append(row.termination_reason.value)
    if row.bound_key is not None:
        context.append(str(row.bound_key))
    if context:
        details.append(
            Detail(kind=DetailKind.TERMINATION, label="", text=" · ".join(context))
        )

    if row.grounding_fact_statement is not None:
        text = f'"{row.grounding_fact_statement}"'
        if row.grounding_fact_id:
            text = f"{text}  {row.grounding_fact_id}"
        details.append(Detail(kind=DetailKind.GROUNDING, label="grounds in", text=text))

    if row.evidence_state_diverged or (
        row.grounding_recorded and row.grounding_status is not GroundingLiveness.LIVE
    ):
        # The invalidation story: what the run concluded, against what the alethiology
        # says now. Rendered whenever the two differ, including when only the grounding
        # moved and the state had nowhere lower to go.
        recorded = row.evidence_state_recorded.value
        if row.grounding_recorded:
            recorded = f"{recorded}, grounded"
        details.append(
            Detail(
                kind=DetailKind.DIVERGENCE,
                label="at run time",
                text=f"{recorded} — re-read against the alethiology since",
            )
        )

    if row.evidence_counts is not None:
        counts = row.evidence_counts
        details.append(
            Detail(
                kind=DetailKind.EVIDENCE,
                label="evidence",
                # Fixed order and identical weight on both sides: the split is structural,
                # not editorial (design.md §4.2), so nothing here may rank one over the
                # other. `rejected` is shown because a filtered item is a dropped one.
                text=(
                    f"{counts.get('supporting', 0)} supporting · "
                    f"{counts.get('contradicting', 0)} contradicting · "
                    f"{counts.get('neutral', 0)} neutral · "
                    f"{counts.get('rejected', 0)} rejected"
                ),
            )
        )
    for cap in row.evidence_caps:
        details.append(
            Detail(kind=DetailKind.CAP, label="dropped", text=describe_cap(cap))
        )

    return tuple(details)


def describe_cap(cap: CapRecord) -> str:
    """A cap as one line. An applied cap always says what it dropped, including
    `uncounted` — that answer is legal, and leaving it unsaid is the silent cap."""
    if not cap.applied:
        return f"{cap.name} (limit {cap.limit}): not applied"
    return f"{cap.name} (limit {cap.limit}): {cap.dropped} dropped"


def build(payload: RenderPayload) -> Layout:
    """Order the payload's rows depth-first and position them in a tree."""
    children: dict[str, list[RenderPremise]] = defaultdict(list)
    for row in payload.premises:
        children[row.parent_id].append(row)

    # Where a premise's subtree was actually drawn, so a later occurrence can point at it.
    # Keyed to the *parent* it was expanded under: naming the premise itself would print
    # the text already on the row the reader is looking at, which says nothing.
    labels = {payload.root.id: sanitize(payload.root.text)}
    for row in payload.premises:
        labels.setdefault(row.premise_id, sanitize(row.text))

    rows: list[Row] = []
    expanded_under: dict[str, str] = {}
    unexpanded = 0

    def walk(parent_id: str, ancestors: tuple[bool, ...]) -> None:
        nonlocal unexpanded
        siblings = children.get(parent_id, [])
        for index, row in enumerate(siblings):
            last = index == len(siblings) - 1
            stem = "".join("   " if done else "│  " for done in ancestors)
            prefix = f"{stem}{'└─ ' if last else '├─ '}"
            continuation = f"{stem}{'   ' if last else '│  '}"

            shared_with = None
            expand = row.premise_id not in expanded_under
            if not expand:
                # Only when there is a subtree to point at. A shared leaf is drawn in full
                # under both parents, and telling the reader to look elsewhere for nothing
                # is a pointer to an empty room.
                if children.get(row.premise_id):
                    shared_with = labels.get(
                        expanded_under[row.premise_id], "an earlier premise"
                    )
                    unexpanded += 1
            else:
                expanded_under[row.premise_id] = parent_id

            rows.append(
                Row(
                    premise_id=row.premise_id,
                    text=sanitize(row.text),
                    prefix=prefix,
                    continuation=continuation,
                    entail=format_score(row),
                    entail_value=row.step_score_value,
                    ablation=format_ablation(row),
                    state=format_state(row),
                    grounding=format_grounding(row),
                    details=_details(row, shared_with=shared_with),
                    expanded=expand,
                )
            )
            if expand:
                walk(row.premise_id, (*ancestors, last))

    walk(payload.root.id, ())

    scorers = tuple(
        dict.fromkeys(r.step_score_scorer for r in payload.premises if r.step_score_scorer)
    )
    return Layout(
        root_id=payload.root.id,
        root_text=sanitize(payload.root.text),
        rows=tuple(rows),
        node_count=len({r.premise_id for r in payload.premises}),
        row_count=len(payload.premises),
        step_count=len({r.step_id for r in payload.premises if r.step_id}),
        graph_depth=payload.max_depth,
        checked_at=payload.checked_at,
        caps=tuple(payload.caps),
        scorers=scorers,
        has_uncalibrated_scores=payload.has_uncalibrated_scores,
        has_stale_groundings=payload.has_stale_groundings,
        unexpanded_rows=unexpanded,
    )
