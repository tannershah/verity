"""The Retraction Watch table — a local file, and the third source the policy consults.

No HTTP. It lives here rather than beside the seed because M6 owns acquisition and because
M7-T1's cut needs all three sources reachable from one place; the table itself arrives with
M10-T1 (`gitlab.com/crossref/retraction-watch-data`, 71,799 rows, gitignored under `data/`).

**A curated index is not a registry.** Retraction Watch is authoritative about retractions
and secondary about works, which is why `resolution.REGISTRY_SOURCES` excludes it, why the
seed gate caps a row quoting it at `single-secondary`, and why the binder will not treat a
hit here as an identifier resolving. Any of those three collapsing would let a key that
exists only in a curated CSV read as a confirmed work.

**The rendering of `record` is a contract with the seed corpus.** `rw-17524-retraction`
quotes the literal string `"nature: Retraction"`, and four sibling rows quote other
fragments of the same line. That string exists because the fields below are joined as
`"{key}: {value}"`, space-separated, in the order they are written here, skipping empties.
Reordering the dict or changing the separator makes five committed rows unquotable and the
seed load aborts. `tests/test_retrieval_parsers.py` pins it.

**Absent table means never consulted.** `read` returns `None` rather than a not-found
reading when the file is missing, because `found=False` claims a source looked.

**And which copy answered is part of the answer.** A miss against the bulk table says the
work is not among 71,799 recorded retractions; a miss against the committed two-row sample
says nothing at all. Both produce the same `WorkRecord`, because a reading carries no room
for the file behind it — so `resolve_table` hands the caller the table's *identity* and a
policy branches on that rather than on the outcome. Without it a clean checkout would
answer "checked, and clean" for every key, off a file holding two rows.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from verity.alethiology.resolution import RETRACTION_WATCH
from verity.keys import ExternalKey, InvalidKeyError, KeyType
from verity.retrieval.record import (
    ReadingOutcome,
    UnansweredReason,
    WorkRecord,
    absent,
    unanswered,
)

SOURCE = RETRACTION_WATCH

#: The bulk table, as M10-T1 lands it. `data/` is gitignored.
TABLE = Path("data/retraction_watch.csv")

#: A minimal committed recording — header plus the rows the seed corpus depends on — so a
#: clean checkout can run the parity gate and the rendering test without the 66 MB
#: download. Same precedent as `seed/key_resolution.json`: the artifact exists so
#: reproduction does not require a bulk file nobody committed.
#: Resolved from this file rather than the working directory: `TABLE` is operational data
#: and follows `PathsConfig`'s relative convention, but a recording shipped with the source
#: is part of the source, and reading a different tree depending on where the process was
#: launched is the kind of difference nothing reports.
SAMPLE_TABLE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "retraction_watch"
    / "sample.csv"
)

#: Which column an identifier is matched against. NCT has none — the table indexes papers.
_COLUMNS = {
    KeyType.DOI: "OriginalPaperDOI",
    KeyType.PMID: "OriginalPaperPubMedID",
    KeyType.NCT: None,
}

#: Read in this order, rendered in this order. See the module docstring — this tuple is
#: what five committed seed quotes are matched against.
_FIELDS = (
    ("record_id", "Record ID"),
    ("nature", "RetractionNature"),
    ("retraction_date", "RetractionDate"),
    ("reasons", "Reason"),
    ("journal", "Journal"),
    ("author", "Author"),
)


@dataclass(frozen=True)
class TableSource:
    """Which copy of the table is on disk, and what a miss against it is worth.

    `complete` is the whole point. Only the bulk download can turn "no row for this key"
    into evidence that the work was not retracted; against the sample that same absence is
    a file that was never in a position to say, and a policy reading it as clean would
    fabricate the strongest negative it has from the smallest file in the repository.
    """

    path: Path
    complete: bool

    def describe(self) -> str:
        return f"{self.path}" if self.complete else f"{self.path} (committed sample)"


def resolve_table(table: Path | str | None = None) -> TableSource | None:
    """The table to read, or `None` when no copy is on disk at all.

    Prefers the bulk download and falls back to the committed sample, so a clean checkout
    still reads the rows the demo rests on. An explicit path is taken at its word and
    judged complete unless it *is* the sample — a caller naming a file has already made
    the choice this function otherwise makes.
    """
    if table is not None:
        path = Path(table)
        return TableSource(path=path, complete=path.resolve() != SAMPLE_TABLE.resolve())
    if TABLE.exists():
        return TableSource(path=TABLE, complete=True)
    if SAMPLE_TABLE.exists():
        return TableSource(path=SAMPLE_TABLE, complete=False)
    return None


def render_record(findings: dict[str, str]) -> str:
    """`"{key}: {value}"` joined by single spaces, empties skipped. Do not change."""
    return " ".join(f"{name}: {value}" for name, value in findings.items() if value)


def read(key: ExternalKey, table: Path | None = None) -> WorkRecord | None:
    """Match `key` against the table. `None` when the table is not on disk at all."""
    readings = read_many([key], table)
    return None if readings is None else readings[str(key)]


def read_many(
    keys: Iterable[ExternalKey], table: Path | None = None
) -> dict[str, WorkRecord] | None:
    """One reading per key, from a single pass. `None` when the table is not on disk.

    The pass is the point. Matching is a linear scan of 71,799 rows — about a second — so a
    caller checking every key in the alethiology one at a time waits half a minute on a
    local file, and the demo path is where that shows up. `read` delegates here rather than
    keeping its own loop, so the two can never answer differently about the same row.

    Keyed by `str(key)`, because two `ExternalKey`s that canonicalize alike are one key and
    the rendered form is already how the resolution artifact indexes them.
    """
    path = Path(table) if table is not None else TABLE
    if not path.exists():
        return None

    fetched_at = datetime.now(UTC)
    readings: dict[str, WorkRecord] = {}
    #: (key type, canonical value) -> the keys waiting on it. A list, since one caller may
    #: pass two spellings of one identifier and both are owed an answer.
    wanted: dict[tuple[KeyType, str], list[ExternalKey]] = {}

    for key in keys:
        if _COLUMNS[key.type] is None:
            # The table indexes papers by DOI and PMID. It has no column an NCT could
            # match, so it was never in a position to answer — which is not the same as
            # having looked.
            readings[str(key)] = unanswered(
                SOURCE,
                fetched_at,
                key,
                reason=UnansweredReason.NOT_APPLICABLE,
                because=f"the retraction watch table indexes papers, not {key.type.value}s",
            )
        else:
            wanted.setdefault((key.type, key.value), []).append(key)

    if wanted:
        columns = {kind: _COLUMNS[kind] for kind, _ in wanted}
        csv.field_size_limit(10_000_000)
        with path.open(encoding="utf-8", errors="replace") as handle:
            for row in csv.DictReader(handle):
                for kind, column in columns.items():
                    raw = (row.get(column) or "").strip()
                    if not raw:
                        continue
                    try:
                        value = ExternalKey(type=kind, value=raw).value
                    except (InvalidKeyError, ValueError):
                        continue
                    # The first matching row wins, and later rows for a key already
                    # answered are skipped — `read`'s behaviour, kept because a work with
                    # two notices would otherwise depend on scan order.
                    for key in wanted.pop((kind, value), ()):
                        readings[str(key)] = _found(row, key, fetched_at)
                if not wanted:
                    break

    for pending in wanted.values():
        for key in pending:
            readings[str(key)] = absent(SOURCE, fetched_at, key)
    return readings


def _found(row: dict[str, str], key: ExternalKey, fetched_at: datetime) -> WorkRecord:
    findings = {name: (row.get(column) or "").strip() for name, column in _FIELDS}
    return WorkRecord(
        source=SOURCE,
        outcome=ReadingOutcome.FOUND,
        fetched_at=fetched_at,
        source_url="https://gitlab.com/crossref/retraction-watch-data",
        key=key,
        title=(row.get("Title") or "").strip() or None,
        record=render_record(findings),
        raw_findings={name: value for name, value in findings.items() if value},
    )
