"""Gathering the three readings. The only part of the retraction layer that does I/O.

Split from the cut for the reason `alethiology` splits `grounding` from `service`: a policy
that could also fetch would be untestable without a transport, and every branch of this one
has to be exercised against readings a network would not reliably produce.

**One table pass for many keys.** Matching a key is a linear scan of 71,799 rows, so
`assess_keys` resolves the table once and reads every key from a single pass — checking a
33-fact store one key at a time would spend half a minute on a local file, and the demo path
is where that would show.

**A source that fails degrades that source, not the run.** A `RetrievalError` — a replay
miss, a spent budget, a transport failure — is caught per source and recorded as a reason
that source was not consulted. Losing one key's OpenAlex reading must not cost the other
eighteen their Crossref ones, and it must never read as a finding: `not_consulted` is not
`clean`, which is the same distinction `ReadingOutcome` draws one layer down.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from verity.keys import ExternalKey
from verity.models.common import RetractionSource
from verity.models.evidence import RetractionCheck
from verity.quality.retraction import (
    RetractionAssessment,
    crossref_finding,
    decide,
    openalex_finding,
    table_finding,
)
from verity.retrieval import crossref, openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.errors import RetrievalError
from verity.retrieval.http import HttpClient
from verity.retrieval.record import WorkRecord

#: Registry module, the source it answers for, and the finding reader for it. A tuple rather
#: than three parallel branches, so adding a source is one row and cannot be half-added.
_REGISTRIES = (
    (openalex, RetractionSource.OPENALEX, openalex_finding),
    (crossref, RetractionSource.CROSSREF, crossref_finding),
)

#: Said when no copy of the Retraction Watch table is on disk at all.
TABLE_ABSENT = (
    f"no retraction watch table on disk ({rw.TABLE} is gitignored); the source was not "
    "consulted"
)


def _sample_miss(table: rw.TableSource) -> str:
    return (
        f"no row in {table.describe()}; a miss against the sample is not evidence the work "
        f"stands, so the source is recorded as unconsulted rather than clean — download "
        f"{rw.TABLE} for a reading either way"
    )


def _assess(
    key: ExternalKey,
    registry_records: dict[RetractionSource, WorkRecord | str],
    table_record: WorkRecord | None,
    table: rw.TableSource | None,
) -> RetractionAssessment:
    """Build one assessment from readings already taken. No I/O, no fetching."""
    checks: dict[RetractionSource, RetractionCheck] = {}
    not_consulted: dict[RetractionSource, str] = {}

    for _, source, read_finding in _REGISTRIES:
        record = registry_records.get(source)
        if isinstance(record, str):
            not_consulted[source] = record
            continue
        if record is None:  # pragma: no cover - every registry is asked or excused
            not_consulted[source] = "not consulted"
            continue
        check = read_finding(record)
        if check is None:
            not_consulted[source] = record.unanswered_because or "no answer"
        else:
            checks[source] = check

    if table is None:
        not_consulted[RetractionSource.RETRACTION_WATCH] = TABLE_ABSENT
    elif table_record is None:  # pragma: no cover - a resolved table always answers
        not_consulted[RetractionSource.RETRACTION_WATCH] = "not consulted"
    else:
        check = table_finding(table_record, table)
        if check is None:
            not_consulted[RetractionSource.RETRACTION_WATCH] = (
                table_record.unanswered_because or _sample_miss(table)
            )
        else:
            checks[RetractionSource.RETRACTION_WATCH] = check

    return RetractionAssessment(
        key=key, status=decide(checks), checks=checks, not_consulted=not_consulted
    )


def _fetch_registries(
    client: HttpClient, key: ExternalKey
) -> dict[RetractionSource, WorkRecord | str]:
    """One reading per registry, or the reason there is none. Never raises.

    **No alias is followed.** A PMID's OpenAlex record reports the work's DOI, and handing
    that DOI to Crossref would turn a `not-applicable` into an answer — by asking about an
    identifier this run was not given, whose bytes are in no fixture, and which the binder
    and the grounding predicate both refuse for the same reason: widening what an identifier
    reaches is a change to a pre-registered definition, not a convenience.
    """
    records: dict[RetractionSource, WorkRecord | str] = {}
    for module, source, _ in _REGISTRIES:
        try:
            records[source] = module.fetch_work(client, key)
        except RetrievalError as error:
            records[source] = f"{type(error).__name__}: {error}"
    return records


def assess_key(
    client: HttpClient, key: ExternalKey, *, table: Path | None = None
) -> RetractionAssessment:
    """Ask all three sources about `key` and apply the cut."""
    return assess_keys(client, [key], table=table)[str(key)]


def assess_keys(
    client: HttpClient, keys: Iterable[ExternalKey], *, table: Path | None = None
) -> dict[str, RetractionAssessment]:
    """One assessment per key, keyed by `str(key)`, from one pass over the table."""
    wanted = list(keys)
    source = rw.resolve_table(table)
    readings = rw.read_many(wanted, source.path) if source is not None else None
    return {
        str(key): _assess(
            key,
            _fetch_registries(client, key),
            readings.get(str(key)) if readings is not None else None,
            source,
        )
        for key in wanted
    }
