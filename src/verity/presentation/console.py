"""The terminal surface: one table, per-premise rows, and a footer that states its terms.

**No bar is drawn.** The M4-T1 champion is near-binary — every step of both demo claims
scores above 0.99 — so a proportional bar would render as full on every row of a system
whose own selection record says the checkpoint misses three of seven corruption families.
A bar is the polish design.md §3.4 forbids: it would carry precision the number does not
have, in the one direction that flatters. The number is printed, marked uncalibrated, and
the footer states what the checkpoint catches and misses, derived from the record.

**Every text value arrives as `rich.text.Text`.** Premise text comes from a language model
and from pasted source material, and Rich interprets square brackets as console markup: a
premise containing `[/red]` raises `MarkupError` and kills the render, while one containing
`[bold]` is silently swallowed from the display. The one input this tier does not control
cannot be the one input it trusts.

**Colour is decoration.** Every state is a word before it is a style, so a `NO_COLOR`
terminal, a pipe, and a screenshot pasted into a document all carry the same information.
Nothing here colours supporting evidence differently from contradicting evidence: the
split is structural rather than editorial (design.md §4.2), and a green/red pair would be
the adjudication affordance the verdict boundary exists to withhold.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.table import Column, Table
from rich.text import Text

from verity.models.render import STEP_SCORE_SCOPE_NOTE, RenderPayload
from verity.presentation import bands, layout
from verity.presentation.layout import ABSENT, UNCALIBRATED_MARK, DetailKind, Layout

#: Styles are decoration only — the same words print without them.
_DETAIL_STYLES: dict[DetailKind, str] = {
    DetailKind.RESTATEMENT: "yellow",
    DetailKind.RETRACTION: "red",
    DetailKind.SHARED: "dim",
    DetailKind.TERMINATION: "dim",
    DetailKind.GROUNDING: "cyan",
    DetailKind.DIVERGENCE: "yellow",
    DetailKind.EVIDENCE: "dim",
    DetailKind.CAP: "dim",
}

#: Widths of the metric columns, in the order they are drawn. `Column` is stateful — Rich
#: writes measurement and index onto the instance — so the columns are rebuilt per table
#: rather than shared from module scope: a reused instance renders the second graph in a
#: process differently from the first, which `run --pilot` would hit on its second claim.
_METRIC_HEADERS: tuple[tuple[str, str, int], ...] = (
    ("step\nentail.", "right", 8),
    ("Δ if\nremoved", "right", 7),
    ("evidence\nstate", "left", 11),
    ("grounding", "left", 15),
)


def _metric_columns() -> list[Column]:
    return [
        Column(header, justify=justify, min_width=width, overflow="fold")
        for header, justify, width in _METRIC_HEADERS
    ]


#: Never let the premise column collapse to nothing on a narrow terminal. Rich folds
#: rather than truncates at this width, so the text survives even when the layout does not.
_MIN_TEXT_WIDTH = 20

#: Width of the `CLAIM  ` label. Continuations align under the claim text, not under the
#: label, so a wrapped claim reads as one sentence.
_HEADER_INDENT = 7


def _text_width(console: Console) -> int:
    fixed = sum(width for _, _, width in _METRIC_HEADERS)
    padding = 2 * (len(_METRIC_HEADERS) + 1)
    return max(_MIN_TEXT_WIDTH, console.width - fixed - padding)


def _wrapped(console: Console, body: Text, width: int) -> list[Text]:
    """Wrap by display cells, folding long tokens. Never truncates, never ellipsizes."""
    lines = body.wrap(console, max(width, 1), overflow="fold")
    return list(lines) or [Text("")]


def _premise_lines(console: Console, row: layout.Row, width: int) -> list[Text]:
    """The premise's own lines: tree glyphs on the first, the gutter on every other."""
    out = []
    body = _wrapped(console, Text(row.text), width - len(row.prefix))
    for index, line in enumerate(body):
        gutter = Text(row.prefix if index == 0 else row.continuation, style="dim")
        out.append(gutter + line)
    return out


def _detail_lines(console: Console, row: layout.Row, width: int) -> list[Text]:
    """Sub-lines under a premise: alarms, then the apparatus. Indented under the gutter."""
    out = []
    for detail in row.details:
        style = _DETAIL_STYLES.get(detail.kind, "")
        head = Text(f"{detail.label}  " if detail.label else "", style=style)
        available = width - len(row.continuation) - 2 - len(head)
        body = _wrapped(console, Text(detail.text, style=style), available)
        for index, line in enumerate(body):
            gutter = Text(f"{row.continuation}  ", style="dim")
            lead = head if index == 0 else Text(" " * len(head))
            out.append(gutter + lead + line)
    return out


def _table(console: Console, view: Layout) -> Table:
    width = _text_width(console)
    table = Table(
        Column("", overflow="fold", min_width=_MIN_TEXT_WIDTH),
        *_metric_columns(),
        box=None,
        show_edge=False,
        pad_edge=False,
        header_style="dim",
        expand=False,
    )
    for row in view.rows:
        lines = _premise_lines(console, row, width)
        # Metrics sit on the premise's first line only. Continuation lines carry empty
        # cells rather than repeating a number beside a fragment of its own premise.
        table.add_row(lines[0], row.entail, row.ablation, row.state, row.grounding)
        for line in lines[1:] + _detail_lines(console, row, width):
            table.add_row(line, "", "", "", "")
    return table


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _header(view: Layout) -> list[Text]:
    """The claim and the no-verdict statement, as lines to be hanging-indented.

    Returned as lines rather than one blob with an embedded newline: the disclaimer is
    load-bearing copy, and at 80 columns — the conventional screenshot width — a tail
    detached at the left margin reads as a rendering fault rather than as the end of the
    sentence above it.
    """
    claim = Text("CLAIM  ", style="bold") + Text(view.root_text)
    disclaimer = Text(
        " " * _HEADER_INDENT
        + "Verity issues no verdict on this claim. Every number below scores one step.",
        style="dim",
    )
    return [claim, disclaimer]


def _footer(view: Layout, *, gate: float, selection_path: Path | str) -> list[Text]:
    lines: list[Text] = []

    # Three counts, because in a DAG they differ: nodes are distinct premises, rows are
    # the (step, premise) edges drawn, and steps are what carries a score.
    shape = (
        f"{_count(view.node_count, 'premise', 'premises')} · "
        f"{_count(view.row_count, 'row')} · {_count(view.step_count, 'step')} · "
        f"graph depth {view.graph_depth} (traversal depth) · "
        f"alethiology read {view.checked_at:%Y-%m-%d %H:%M}Z"
    )
    lines.append(Text(shape, style="dim"))

    if view.has_stale_groundings:
        lines.append(
            Text(
                "⚑  a grounding recorded by the run no longer holds — the rows say which, "
                "and why. Grounding is non-monotonic: this is a reading at the time above.",
                style="yellow",
            )
        )
    if view.unexpanded_rows:
        lines.append(
            Text(
                f"{view.unexpanded_rows} premise row(s) appear under more than one step; "
                "each shows its own step's score and the subtree is drawn once, at the "
                "first occurrence.",
                style="dim",
            )
        )

    if view.has_uncalibrated_scores:
        lines.append(
            Text(
                f"{UNCALIBRATED_MARK}  uncalibrated — no human anchor yet "
                "(evaluation.md §6).",
                style="dim",
            )
        )
    record, note = bands.for_scorers(view.scorers, gate=gate, path=selection_path)
    if record is not None:
        for line in bands.summary_lines(record):
            lines.append(Text(f"   {line}", style="dim"))
    elif note is not None:
        lines.append(Text(f"   {note}", style="yellow"))

    lines.append(
        Text(
            f"   A step score is a {STEP_SCORE_SCOPE_NOTE}. Premises in one step share "
            "it — it scores the step, not the premise — and no score is shown for the "
            "claim.",
            style="dim",
        )
    )
    lines.append(
        Text(
            "   Δ is signed: positive means removing the premise lowers its step's score, "
            f"so the premise is load-bearing. {ABSENT} means nothing measured it yet "
            "(M4-T2); * marks a provisional evidence state (M6-T3, not M8-T3).",
            style="dim",
        )
    )

    if view.caps:
        lines.append(
            Text(
                "caps  " + " · ".join(layout.describe_cap(cap) for cap in view.caps),
                style="dim",
            )
        )
    return lines


def _emit(console: Console, line: Text, *, indent: int | None = None) -> None:
    """Print one line, hanging-indented so a continuation reads as one.

    Rich would wrap back to column zero, which reads as a new statement rather than as the
    rest of the one above it. That matters most on the two lines a reader sees first and
    the caveats they see last, both of which are long by design; `indent` is explicit for
    the header, where continuations align under the claim rather than under its label.
    """
    lead = len(line.plain) - len(line.plain.lstrip())
    indent = " " * (indent if indent is not None else lead + 3)
    # Wrapped against the *indented* width, not the raw one: wrapping to the full width and
    # then prepending the indent pushes every continuation line three cells over, and Rich
    # re-wraps the overflow back to column zero — which is where the band caveat, this
    # tier's most load-bearing paragraph, was spilling a word at a time.
    wrapped = _wrapped(console, line, console.width - len(indent))
    for index, part in enumerate(wrapped):
        console.print(part if index == 0 else Text(indent) + part)


def render(
    payload: RenderPayload,
    console: Console | None = None,
    *,
    gate: float,
    selection_path: Path | str = bands.SELECTION,
    notes: Sequence[str] = (),
) -> None:
    """Print `payload` to `console`. The only entry point a surface needs.

    `notes` are run-level facts the payload cannot carry — that the verifier was not
    installed, for instance, which is why every score reads `unscored`. They print with
    the footer so an absence always has a stated cause.
    """
    console = console or Console()
    view = layout.build(payload)

    for line in _header(view):
        _emit(console, line, indent=_HEADER_INDENT)
    console.print()
    console.print(_table(console, view))
    console.print()
    for line in _footer(view, gate=gate, selection_path=selection_path):
        _emit(console, line)
    for note in notes:
        _emit(console, Text(f"note  {note}", style="yellow"))
