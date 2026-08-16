"""Resolve seed identifiers against the registries, once, and record what came back.

**Provisional, and scheduled for deletion.** This is direct `urllib` with no disk cache,
no rate limiter, and no retry policy — M6-T1a builds all three, and this module is removed
when it does, its callers moving to those clients. It exists now because the seed cannot be
gated without a resolution record and M5-T1 precedes M6-T1a in the ordering. The artifact
it writes is not throwaway: it is committed, it makes seed loading offline and
reproducible, and it is M6-T1a's first recorded fixture.

Run it when a key is added to the seed, never as part of a normal run:

    python -m verity.alethiology verify-keys --from-seed
    python -m verity.alethiology verify-keys doi:10.1136/bmj.283.6307.1671

Retraction Watch is read from the local table (`data/retraction_watch.csv`, gitignored) and
its matched rows are copied into the artifact, so a clean checkout can seed without the
71,799-row download.
"""

from __future__ import annotations

import csv
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from verity.alethiology.resolution import (
    RETRACTION_WATCH,
    KeyResolution,
    ResolutionArtifact,
    SourceReading,
)
from verity.keys import ExternalKey, InvalidKeyError, KeyType
from verity.secrets import Secrets

RW_TABLE = Path("data/retraction_watch.csv")
_TIMEOUT = 30.0
_JATS = re.compile(r"<[^>]+>")


def _get(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "verity/0.0.1 (research)"})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 410):
            return None
        raise


def _now() -> datetime:
    return datetime.now(UTC)


def _openalex_abstract(work: dict) -> str | None:
    """Reconstruct prose from OpenAlex's inverted index.

    Token order survives; original spacing and punctuation do not, which is exactly why
    the seed's quote check normalizes before testing containment.
    """
    inverted = work.get("abstract_inverted_index")
    if not inverted:
        return None
    positions: dict[int, str] = {}
    for word, indices in inverted.items():
        for index in indices:
            positions[index] = word
    return " ".join(positions[i] for i in sorted(positions)) or None


#: OpenAlex `ids` entries that are identifiers we ground on. Read by name rather than by
#: parsing every value: a MAG id is a bare integer, so `ExternalKey.parse` reads it as a
#: PMID and invents an alias to a real, unrelated PubMed record.
_OPENALEX_ID_FIELDS = ("doi", "pmid")


def _openalex_aliases(work: dict) -> list[ExternalKey]:
    keys: list[ExternalKey] = []
    ids = work.get("ids") or {}
    for field in _OPENALEX_ID_FIELDS:
        raw = ids.get(field)
        if not isinstance(raw, str):
            continue
        try:
            keys.append(ExternalKey.parse(raw))
        except InvalidKeyError:
            continue
    return keys


def read_openalex(
    key: ExternalKey, api_key: str | None
) -> tuple[SourceReading, list[ExternalKey]]:
    match key.type:
        case KeyType.DOI:
            path = f"https://doi.org/{key.value}"
        case KeyType.PMID:
            path = f"pmid:{key.value}"
        case KeyType.NCT:
            # OpenAlex indexes works, not registry entries. Recorded as not-found rather
            # than skipped, so "asked and absent" stays distinct from "never asked".
            return SourceReading(source="openalex", found=False, checked_at=_now()), []
    url = f"https://api.openalex.org/works/{path}"
    if api_key:
        url += f"?api_key={urllib.parse.quote(api_key)}"

    work = _get(url)
    checked_at = _now()
    if work is None:
        return SourceReading(source="openalex", found=False, checked_at=checked_at), []

    detail = {}
    if work.get("is_retracted") is not None:
        detail["is_retracted"] = str(bool(work["is_retracted"])).lower()
    if work.get("id"):
        detail["openalex_id"] = str(work["id"])
    return (
        SourceReading(
            source="openalex",
            found=True,
            checked_at=checked_at,
            url=str(work.get("id")) if work.get("id") else None,
            title=work.get("title"),
            year=work.get("publication_year"),
            abstract=_openalex_abstract(work),
            detail=detail,
        ),
        _openalex_aliases(work),
    )


def read_crossref(key: ExternalKey, mailto: str | None) -> SourceReading:
    if key.type is not KeyType.DOI:
        return SourceReading(source="crossref", found=False, checked_at=_now())
    url = f"https://api.crossref.org/works/{urllib.parse.quote(key.value)}"
    if mailto:
        url += f"?mailto={urllib.parse.quote(mailto)}"

    payload = _get(url)
    checked_at = _now()
    if payload is None:
        return SourceReading(source="crossref", found=False, checked_at=checked_at)

    work = payload["message"]
    abstract = work.get("abstract")
    detail = {}
    updates = [u.get("type", "") for u in work.get("update-to", []) if isinstance(u, dict)]
    if updates:
        detail["update_to"] = ",".join(sorted(set(updates)))
    sources = [u.get("source", "") for u in work.get("updated-by", []) if isinstance(u, dict)]
    if sources:
        detail["updated_by_source"] = ",".join(sorted(set(sources)))
    issued = (work.get("issued", {}).get("date-parts") or [[None]])[0][0]
    return SourceReading(
        source="crossref",
        found=True,
        checked_at=checked_at,
        url=f"https://doi.org/{key.value}",
        title=(work.get("title") or [None])[0],
        year=issued if isinstance(issued, int) else None,
        abstract=_JATS.sub(" ", abstract) if abstract else None,
        detail=detail,
    )


def read_retraction_watch(key: ExternalKey, table: Path = RW_TABLE) -> SourceReading | None:
    """Match `key` against the local Retraction Watch table. `None` when it is absent.

    Returning `None` rather than a not-found reading matters: with no table on disk the
    source was never consulted, and `RetractionFinding.NOT_INDEXED` would claim it was.
    """
    if not table.exists():
        return None
    column = {
        KeyType.DOI: "OriginalPaperDOI",
        KeyType.PMID: "OriginalPaperPubMedID",
        KeyType.NCT: None,
    }[key.type]
    checked_at = _now()
    if column is None:
        return SourceReading(source=RETRACTION_WATCH, found=False, checked_at=checked_at)

    csv.field_size_limit(10_000_000)
    with table.open(encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                if ExternalKey(type=key.type, value=raw).value != key.value:
                    continue
            except (InvalidKeyError, ValueError):
                continue
            detail = {
                "record_id": (row.get("Record ID") or "").strip(),
                "nature": (row.get("RetractionNature") or "").strip(),
                "retraction_date": (row.get("RetractionDate") or "").strip(),
                "reasons": (row.get("Reason") or "").strip(),
                "journal": (row.get("Journal") or "").strip(),
                "author": (row.get("Author") or "").strip(),
            }
            return SourceReading(
                source=RETRACTION_WATCH,
                found=True,
                checked_at=checked_at,
                url="https://gitlab.com/crossref/retraction-watch-data",
                title=(row.get("Title") or "").strip() or None,
                record=" ".join(f"{k}: {v}" for k, v in detail.items() if v),
                detail={k: v for k, v in detail.items() if v},
            )
    return SourceReading(source=RETRACTION_WATCH, found=False, checked_at=checked_at)


def resolve(key: ExternalKey, secrets: Secrets) -> KeyResolution:
    """Ask every source about `key` and record all of it, reconciling nothing."""
    openalex, aliases = read_openalex(key, secrets.reveal("openalex_api_key"))
    readings = {
        "openalex": openalex,
        "crossref": read_crossref(key, secrets.reveal("crossref_mailto")),
    }
    rw = read_retraction_watch(key)
    if rw is not None:
        readings[RETRACTION_WATCH] = rw
    return KeyResolution(
        key=key,
        aliases=sorted(set(aliases) - {key}, key=str),
        readings=readings,
    )


def verify(
    keys: list[ExternalKey],
    artifact_path: Path,
    *,
    refresh: bool = False,
    secrets: Secrets | None = None,
) -> ResolutionArtifact:
    """Resolve `keys` into the artifact, keeping existing entries unless `refresh`."""
    secrets = secrets or Secrets()
    existing = (
        ResolutionArtifact.load(artifact_path).resolutions if artifact_path.exists() else {}
    )
    resolutions = dict(existing)
    for key in keys:
        if not refresh and str(key) in resolutions:
            continue
        resolutions[str(key)] = resolve(key, secrets)

    artifact = ResolutionArtifact(generated_at=_now(), resolutions=resolutions)
    artifact.dump(artifact_path)
    return artifact
