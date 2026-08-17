"""OpenAlex: request shapes, and the parsing that must not drift.

Request shapes verified live. A singleton `works/…` costs 1 credit and a filtered list
costs 10, and the response says which — `X-RateLimit-Credits-Used` — so cost is read off
the wire rather than inferred from the URL.

Three parsing decisions carry over from the provisional resolver, each because getting it
wrong is silent rather than loud:

- **Aliases are read from `ids` by name, never by parsing every value.** A MAG id is a bare
  integer, so `ExternalKey.parse` reads it as a PMID and invents an alias pointing at a
  real, unrelated PubMed record.
- **Abstracts are reconstructed from an inverted index**, so token order survives while
  original spacing and punctuation do not. That is exactly why the seed's quote check
  normalizes before testing containment, and why a change to this join demotes
  `verified-primary` rows without failing anything.
- **The DOI is percent-encoded into the path.** Every DOI in the corpus happens to survive
  unencoded — including `10.1579/0044-7447(2008)37[114:ecitbs]2.0.co;2`, checked live — but
  a DOI containing `#` or `?` would truncate the URL at that character and resolve to the
  wrong work, or to none.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from verity.keys import ExternalKey, InvalidKeyError, KeyType
from verity.retrieval.errors import MalformedResponseError
from verity.retrieval.http import HttpClient, HttpRequest
from verity.retrieval.record import (
    ReadingOutcome,
    UnansweredReason,
    WorkRecord,
    from_missing,
    unanswered,
)

SOURCE = "openalex"
API = "https://api.openalex.org"

#: `ids` entries that are identifiers we ground on, read by name. See the module docstring
#: for what parsing every value instead produces.
ID_FIELDS = ("doi", "pmid")

#: Singleton GET = 1 credit, filtered list = 10. Verified live 2026-08-16.
WORK_COST = 1
LIST_COST = 10


def work_request(key: ExternalKey) -> HttpRequest | None:
    """The singleton request for `key`, or `None` when OpenAlex cannot answer for it."""
    match key.type:
        case KeyType.DOI:
            path = f"https://doi.org/{quote(key.value, safe='/')}"
        case KeyType.PMID:
            path = f"pmid:{quote(key.value, safe='')}"
        case KeyType.NCT:
            # OpenAlex indexes works, not registry entries. `None` means there is no
            # request to make, and `fetch_work` turns that into an *unanswered* reading —
            # not an absent one, because a source that cannot be asked has said nothing.
            return None
    return HttpRequest(
        url=f"{API}/works/{path}",
        source=SOURCE,
        endpoint_class="work",
        credit_cost_hint=WORK_COST,
    )


def reconstruct_abstract(work: dict[str, Any]) -> str | None:
    """Prose from OpenAlex's inverted index. Order survives; spacing and punctuation do not.

    **A malformed index raises rather than reconstructing part of one.** Skipping entries
    that are not the shape they should be yields a shorter abstract that still looks like
    an abstract, and the seed gate tests verbatim quote containment against exactly this
    text — so a silently truncated reconstruction demotes `verified-primary` rows to
    `single-secondary` and reports the quote as unfindable. That is the same failure class
    as a 200 that will not parse, and it gets the same answer: a partial parse of a
    structure the source's own schema describes is a schema change, not a shorter work.

    An absent or empty index is not malformed — it is a work served without an abstract.
    """
    inverted = work.get("abstract_inverted_index")
    if inverted is None or inverted == {} or inverted == []:
        return None
    if not isinstance(inverted, dict):
        raise MalformedResponseError(
            "openalex served an abstract_inverted_index that is not an object "
            f"({type(inverted).__name__}); this is a schema change, not a missing abstract"
        )
    positions: dict[int, str] = {}
    for word, indices in inverted.items():
        if not isinstance(indices, list) or not all(isinstance(i, int) for i in indices):
            raise MalformedResponseError(
                f"openalex served position list {indices!r} for token {word!r}; a partial "
                "reconstruction would read as a shorter abstract and unfind its quotes"
            )
        for index in indices:
            positions[index] = word
    # Gaps between positions collapse to a single space. That is the source withholding a
    # token, not malforming the structure, and it is why the seed's quote check normalizes
    # whitespace before testing containment.
    return " ".join(positions[i] for i in sorted(positions)) or None


def read_aliases(work: dict[str, Any]) -> list[ExternalKey]:
    keys: list[ExternalKey] = []
    ids = work.get("ids")
    if not isinstance(ids, dict):
        return keys
    for field in ID_FIELDS:
        raw = ids.get(field)
        if not isinstance(raw, str):
            continue
        try:
            keys.append(ExternalKey.parse(raw))
        except InvalidKeyError:
            continue
    return keys


def _venue(work: dict[str, Any]) -> str | None:
    location = work.get("primary_location")
    if isinstance(location, dict):
        source = location.get("source")
        if isinstance(source, dict):
            name = source.get("display_name")
            if isinstance(name, str) and name:
                return name
    return None


def parse_work(
    payload: Any, key: ExternalKey, fetched_at: datetime, *, from_cache: bool = False
) -> WorkRecord:
    """A `WorkRecord` from one OpenAlex work payload.

    A payload that is not a work object raises rather than reading as an absent work: only
    a 404 means OpenAlex has no such identifier, and a schema change read as `found=False`
    demotes every seed row keyed to this source at once.
    """
    if not isinstance(payload, dict):
        raise MalformedResponseError(
            f"openalex returned 200 for {key} with a payload that is not a work object; "
            "this is a schema change, not an identifier OpenAlex has never heard of"
        )

    findings: dict[str, str] = {}
    if payload.get("is_retracted") is not None:
        # Verbatim. OpenAlex's boolean collapses correction, expression of concern and
        # retraction and has a documented false-positive history; the cut is M7-T1's.
        findings["is_retracted"] = str(bool(payload["is_retracted"])).lower()
    identifier = payload.get("id")
    if isinstance(identifier, str) and identifier:
        findings["openalex_id"] = identifier

    # `title` and `display_name` carry the same string on every work in the corpus;
    # OpenAlex documents `title` as an alias of `display_name` and has been migrating
    # toward the latter. Both are read because either alone would leave the identity gate
    # with no title on a work that served the other — and the gate reads titles by
    # equality, so a missing title is a mismatch rather than a shrug.
    title = payload.get("title") or payload.get("display_name")
    year = payload.get("publication_year")
    return WorkRecord(
        source=SOURCE,
        outcome=ReadingOutcome.FOUND,
        fetched_at=fetched_at,
        source_url=identifier if isinstance(identifier, str) and identifier else None,
        key=key,
        aliases=[alias for alias in read_aliases(payload) if alias != key],
        title=title if isinstance(title, str) else None,
        abstract=reconstruct_abstract(payload),
        year=year if isinstance(year, int) else None,
        venue=_venue(payload),
        raw_findings=findings,
        from_cache=from_cache,
    )


def fetch_work(client: HttpClient, key: ExternalKey) -> WorkRecord:
    """Ask OpenAlex about `key`. A credentialed 404 is a reading; anything else raises."""
    request = work_request(key)
    if request is None:
        return unanswered(
            SOURCE,
            datetime.now(UTC),
            key,
            reason=UnansweredReason.NOT_APPLICABLE,
            because=f"openalex indexes works, not {key.type.value} registry entries",
        )
    fetched = client.get(request)
    if fetched.missing:
        return from_missing(SOURCE, key, fetched.fetched_at, degraded=fetched.degraded)
    return parse_work(fetched.json(), key, fetched.fetched_at, from_cache=fetched.from_cache)


def retraction_flag(record: WorkRecord) -> bool | None:
    """OpenAlex's `is_retracted`, verbatim. Not a status — M7-T1 owns that cut."""
    raw = record.raw_findings.get("is_retracted")
    return None if raw is None else raw == "true"
