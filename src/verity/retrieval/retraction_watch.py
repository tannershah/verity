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
"""

from __future__ import annotations

import csv
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


def render_record(findings: dict[str, str]) -> str:
    """`"{key}: {value}"` joined by single spaces, empties skipped. Do not change."""
    return " ".join(f"{name}: {value}" for name, value in findings.items() if value)


def read(key: ExternalKey, table: Path | None = None) -> WorkRecord | None:
    """Match `key` against the table. `None` when the table is not on disk at all."""
    path = Path(table) if table is not None else TABLE
    if not path.exists():
        return None

    fetched_at = datetime.now(UTC)
    column = _COLUMNS[key.type]
    if column is None:
        # The table indexes papers by DOI and PMID. It has no column an NCT could match,
        # so it was never in a position to answer — which is not the same as having looked.
        return unanswered(
            SOURCE,
            fetched_at,
            key,
            reason=UnansweredReason.NOT_APPLICABLE,
            because=f"the retraction watch table indexes papers, not {key.type.value}s",
        )

    csv.field_size_limit(10_000_000)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                if ExternalKey(type=key.type, value=raw).value != key.value:
                    continue
            except (InvalidKeyError, ValueError):
                continue

            findings = {
                name: (row.get(column_name) or "").strip() for name, column_name in _FIELDS
            }
            present = {name: value for name, value in findings.items() if value}
            return WorkRecord(
                source=SOURCE,
                outcome=ReadingOutcome.FOUND,
                fetched_at=fetched_at,
                source_url="https://gitlab.com/crossref/retraction-watch-data",
                key=key,
                title=(row.get("Title") or "").strip() or None,
                record=render_record(findings),
                raw_findings=present,
            )
    return absent(SOURCE, fetched_at, key)
