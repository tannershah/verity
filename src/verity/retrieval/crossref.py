"""Crossref: request shapes, and the parsing that must not drift.

No key. A `mailto` in the `User-Agent` buys the polite pool — verified live at 10 req/s on
`polite-single` against 5 on `public-single` — so no credential enters a URL here either.
Limits are advertised per response and differ per endpoint (`polite-single` 10/1s,
`polite-array` 3/1s), which is why the limiter reads them rather than assuming them.

Parsing decisions that carry over or were repaired:

- **Abstracts arrive as JATS markup.** Tags are replaced with a *space*, never with the
  empty string, or two words fuse across a removed tag and a verbatim quote stops matching.
- **`issued.date-parts` can be `[[]]`.** The previous expression indexed straight into it
  and raised `IndexError` on any work published with an empty date part; the year is now
  read defensively and left `None`.
- **`title` can be `[]` and `update-to` can hold non-dicts**, both of which occur, and both
  of which are skipped rather than assumed.
- **`update-to` types are recorded, never interpreted.** The vocabulary includes
  `correction`, `new_version` and `expression_of_concern` — the seed's cocoa Cochrane row
  carries `new_version` — so "has an update" is not "is retracted". M7-T1 owns that cut.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from verity.keys import ExternalKey, KeyType
from verity.retrieval.errors import MalformedResponseError
from verity.retrieval.http import HttpClient, HttpRequest
from verity.retrieval.record import (
    ReadingOutcome,
    UnansweredReason,
    WorkRecord,
    from_missing,
    unanswered,
)

SOURCE = "crossref"
API = "https://api.crossref.org"

#: JATS tags in an abstract. Replaced with a space — see the module docstring.
_JATS = re.compile(r"<[^>]+>")

#: Update types that are not retractions. Kept as a named set so the distinction is
#: greppable from M7-T1's side; nothing in this module reads it to make a decision.
NON_RETRACTION_UPDATE_TYPES = frozenset({"correction", "new_version", "expression_of_concern"})


def work_request(key: ExternalKey) -> HttpRequest | None:
    """The singleton request for `key`, or `None` — Crossref speaks only DOI."""
    if key.type is not KeyType.DOI:
        return None
    return HttpRequest(
        url=f"{API}/works/{quote(key.value, safe='/')}",
        source=SOURCE,
        endpoint_class="work",
    )


def strip_jats(abstract: str) -> str:
    return _JATS.sub(" ", abstract)


def _first_string(value: Any) -> str | None:
    """The first usable string in a Crossref list field. `[]` and non-strings yield `None`.

    Crossref serves `title` and `container-title` as arrays because a work can carry a
    translated or alternate title. The first entry is the primary one, and it is what the
    identity gate compares by equality; a curator who needs one of the others declares it
    as an `expected_title_variant`, which is a recorded decision rather than a parser
    silently preferring a different string.
    """
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item:
                return item
    elif isinstance(value, str) and value:
        return value
    return None


def _issued_year(work: dict[str, Any]) -> int | None:
    """The publication year, or `None`. `date-parts` is `[[]]` on some works."""
    issued = work.get("issued")
    if not isinstance(issued, dict):
        return None
    parts = issued.get("date-parts")
    if not isinstance(parts, list) or not parts:
        return None
    first = parts[0]
    if not isinstance(first, list) or not first:
        return None
    year = first[0]
    return year if isinstance(year, int) else None


def _joined(entries: Any, field: str) -> str | None:
    """Sorted, deduplicated `field` values across `update-to` / `updated-by` entries."""
    if not isinstance(entries, list):
        return None
    values = {
        entry[field]
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get(field), str) and entry[field]
    }
    return ",".join(sorted(values)) if values else None


def parse_work(
    payload: Any, key: ExternalKey, fetched_at: datetime, *, from_cache: bool = False
) -> WorkRecord:
    """A `WorkRecord` from one Crossref `works/{doi}` payload.

    A payload with no `message` object raises rather than reading as an absent work: only
    a 404 means Crossref has no such DOI, and treating a schema change as a corpus of
    identifiers that stopped resolving is the silent failure `MalformedResponseError`
    exists to prevent.
    """
    work = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(work, dict):
        raise MalformedResponseError(
            f"crossref returned 200 for {key} with no `message` object; this is a schema "
            "change, not a work Crossref has never heard of"
        )

    findings: dict[str, str] = {}
    update_to = _joined(work.get("update-to"), "type")
    if update_to:
        findings["update_to"] = update_to
    updated_by = _joined(work.get("updated-by"), "source")
    if updated_by:
        findings["updated_by_source"] = updated_by

    abstract = work.get("abstract")
    return WorkRecord(
        source=SOURCE,
        outcome=ReadingOutcome.FOUND,
        fetched_at=fetched_at,
        source_url=f"https://doi.org/{key.value}",
        key=key,
        title=_first_string(work.get("title")),
        abstract=strip_jats(abstract) if isinstance(abstract, str) and abstract else None,
        year=_issued_year(work),
        venue=_first_string(work.get("container-title")),
        raw_findings=findings,
        from_cache=from_cache,
    )


def fetch_work(client: HttpClient, key: ExternalKey) -> WorkRecord:
    """Ask Crossref about `key`. A credentialed 404 is a reading; anything else raises."""
    request = work_request(key)
    if request is None:
        return unanswered(
            SOURCE,
            datetime.now(UTC),
            key,
            reason=UnansweredReason.NOT_APPLICABLE,
            because=f"crossref indexes DOIs, and this is a {key.type.value}",
        )
    fetched = client.get(request)
    if fetched.missing:
        return from_missing(SOURCE, key, fetched.fetched_at, degraded=fetched.degraded)
    return parse_work(fetched.json(), key, fetched.fetched_at, from_cache=fetched.from_cache)


def update_types(record: WorkRecord) -> tuple[str, ...]:
    """Crossref's `update-to` types, verbatim. Not a status — M7-T1 owns that cut."""
    raw = record.raw_findings.get("update_to")
    return tuple(raw.split(",")) if raw else ()


def updated_by_sources(record: WorkRecord) -> tuple[str, ...]:
    """Who filed the update — `publisher` or `retraction-watch`. M7-T1's second input."""
    raw = record.raw_findings.get("updated_by_source")
    return tuple(raw.split(",")) if raw else ()
