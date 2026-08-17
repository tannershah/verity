"""Resolve seed identifiers against the sources, once, and record what came back.

**The transport this module used to carry is gone.** It was direct `urllib` with no disk
cache, no rate limiter and no retry policy, written because the seed cannot be gated without
a resolution record and M5-T1 precedes M6-T1a in the ordering. M6-T1a built all three, so
the reading now goes through `verity.retrieval` — cached, rate-limited, credit-budgeted,
and pool-asserted — and the request and parsing shapes moved to the clients that own them.
What survives here is the curator's command, which is the part that was never provisional:
adding a key to the seed still has to produce a checked record of what each source said.

The swap was gated rather than asserted. Raw registry responses were recorded first, both
parser sets were run over the same bytes, and the resulting `SourceReading`s and every
`TierAssessment` across the seed corpus were compared — because re-recording live and
diffing against the committed artifact cannot separate parser drift from API drift, and the
gate is sensitive to exactly that: quote matching is substring containment over a
reconstructed abstract, so a space-level change in the inverted-index join silently demotes
`verified-primary` rows. `tests/test_seed_parity.py` keeps that comparison running.

Run it when a key is added to the seed, never as part of a normal run, and after
`python -m verity.retrieval record` has captured what the registries serve for it:

    python -m verity.alethiology verify-keys --from-seed
    python -m verity.alethiology verify-keys doi:10.1136/bmj.283.6307.1671
    python -m verity.alethiology verify-keys --from-seed --refresh --cache-mode replay

**Nothing unchecked reaches the artifact.** Two claims a resolution cannot make are refused
here rather than written and discovered later. When a source could have answered and did
not, the key is left out entirely and reported — the artifact stores `found` as a boolean,
and the gate reads a resolution with nothing found as "resolves in no source consulted …
correct it or drop the row", so a network failure recorded as `False` tells a curator to
delete a good row. And when the Retraction Watch table (`data/retraction_watch.csv`,
gitignored) is absent, that source is reported as unconsulted rather than silently omitted,
because an artifact missing a source and an artifact whose source found nothing are
different claims. A source that structurally cannot answer — Crossref holds no PMIDs — is
neither: `found=False` is true of it, and is what the committed artifact already carries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ConfigDict, Field

from verity.alethiology.resolution import KeyResolution, ResolutionArtifact
from verity.base import FrozenModel
from verity.keys import ExternalKey
from verity.retrieval import crossref, openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.http import CacheMode, HttpClient, build_client


class KeyReading(FrozenModel):
    """One key resolved across every source, and whether it may be committed.

    **Recordability is a property of the reading, not a formatting concern.** The artifact
    stores `found` as a boolean and the gate reads a resolution where nothing was found as
    "resolves in no source consulted … correct it or drop the row" — a claim about the
    identifier. A run that could not reach a registry does not have that claim, so writing
    the key at all would tell a curator to delete a good row on the strength of a network
    failure. That is the fabrication `ReadingOutcome` prevents at the record layer, arriving
    one layer up through a schema that cannot express the difference.
    """

    key: ExternalKey
    resolution: KeyResolution | None
    #: Sources that could have answered and did not, with the reason.
    unreachable: dict[str, str] = Field(default_factory=dict)
    #: Sources structurally unable to speak to this key type — Crossref holds no PMIDs.
    #: Recorded for the report; these do not block a write, because `found=False` is true
    #: of them and is already what the committed artifact carries for the PMID rows.
    not_applicable: dict[str, str] = Field(default_factory=dict)
    #: Whether the Retraction Watch table was on disk to consult at all.
    table_consulted: bool = False

    @property
    def recordable(self) -> bool:
        """Whether this reading may be written to the artifact.

        Two ways to fail. Any source that could have answered and did not leaves the
        reading incomplete. And a key that *no* source was able to speak to has been
        checked by nobody — an NCT identifier today, since ClinicalTrials.gov arrives with
        M6-T1b — so recording it would put a row in the artifact that the gate then rejects
        as nonexistent.
        """
        return self.resolution is not None and not self.unreachable

    def why_not(self) -> str:
        reasons = self.unreachable or {"all sources": "no source indexes this identifier type"}
        return "; ".join(f"{source}: {reason}" for source, reason in sorted(reasons.items()))


def resolve(key: ExternalKey, client: HttpClient, *, table: Path | None = None) -> KeyReading:
    """Ask every source about `key`, reconciling nothing.

    `table` names which Retraction Watch copy to read — the bulk download by default, and
    the committed sample when a clean checkout has to reproduce the corpus without it.
    """
    records = {
        openalex.SOURCE: openalex.fetch_work(client, key),
        crossref.SOURCE: crossref.fetch_work(client, key),
    }
    table_reading = rw.read(key, table)
    if table_reading is not None:
        records[rw.SOURCE] = table_reading

    unreachable = {
        source: record.unanswered_because or "unanswered"
        for source, record in records.items()
        if record.unreachable
    }
    not_applicable = {
        source: record.unanswered_because or "not applicable"
        for source, record in records.items()
        if record.not_applicable
    }
    if unreachable or not any(record.answered for record in records.values()):
        return KeyReading(
            key=key,
            resolution=None,
            unreachable=unreachable,
            not_applicable=not_applicable,
            table_consulted=table_reading is not None,
        )

    work = records[openalex.SOURCE]
    return KeyReading(
        key=key,
        resolution=KeyResolution(
            key=key,
            aliases=sorted(set(work.aliases) - {key}, key=str),
            readings={source: record.as_source_reading() for source, record in records.items()},
        ),
        not_applicable=not_applicable,
        table_consulted=table_reading is not None,
    )


class VerifyReport(FrozenModel):
    """What was written, and everything that was not."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid", frozen=True)

    artifact: ResolutionArtifact
    #: Keys deliberately left out of the artifact because nothing could check them.
    unrecordable: list[KeyReading] = Field(default_factory=list)
    #: Keys whose Retraction Watch reading was skipped because the table is not on disk.
    table_unconsulted: list[ExternalKey] = Field(default_factory=list)
    #: Whether the file on disk actually changed. See `verify` for why it usually should not.
    written: bool = False

    @property
    def resolving(self) -> int:
        return sum(
            1
            for resolution in self.artifact.resolutions.values()
            if any(reading.found for reading in resolution.readings.values())
        )


def verify(
    keys: list[ExternalKey],
    artifact_path: Path,
    *,
    refresh: bool = False,
    client: HttpClient | None = None,
    cache_mode: CacheMode | None = None,
    table: Path | None = None,
) -> VerifyReport:
    """Resolve `keys` into the artifact, keeping existing entries unless `refresh`.

    **`refresh` and `cache_mode` are two decisions that used to be one.** `refresh` says
    which *artifact* entries may be rewritten; `cache_mode` says where the *bytes* behind
    them may come from. Conflating them meant a re-verification could only be a live one,
    so re-recording the artifact after a parser change had to go back to the network — and
    a live re-read moves both the parser's output and the API's, which is the confusion
    `tests/test_seed_parity.py` exists to prevent. Passing `replay` resolves from the
    committed fixtures instead, which is deterministic: a cache hit replays `fetched_at`
    rather than restamping it, so every registry reading reproduces to the microsecond and
    the only values that move are the ones generated locally — the Retraction Watch read,
    which the table cannot date, and a not-applicable reading, whose time is all there is.

    **A key that could not be checked is not written.** Every unrecordable reading is
    returned instead, so the curator is told "2 key(s) could not be checked" rather than
    handed an artifact asserting those identifiers do not exist.

    **A run that resolved nothing new leaves the file alone.** `generated_at` stamps every
    seeded fact and travels into the load report, so rewriting it on a no-op produces a
    committed diff that says the corpus was re-verified when nothing was — and a *failed*
    run that also rewrote the file would modify tracked state on its way to exiting
    non-zero. Existing entries are never removed either, so a `--refresh` that finds a key
    unreachable keeps the reading it already had and reports the failure.
    """
    # An explicit mode wins over the one `refresh` implies. Without that precedence
    # `--refresh --cache-mode replay` would silently fetch, which is the one combination
    # the flag exists for.
    mode = cache_mode or (CacheMode.REFRESH if refresh else CacheMode.LIVE)
    client = client or build_client(mode=mode)
    existing = (
        ResolutionArtifact.load(artifact_path).resolutions if artifact_path.exists() else {}
    )
    resolutions = dict(existing)
    unrecordable: list[KeyReading] = []
    table_unconsulted: list[ExternalKey] = []

    for key in keys:
        if not refresh and str(key) in resolutions:
            continue
        reading = resolve(key, client, table=table)
        if not reading.table_consulted:
            table_unconsulted.append(key)
        if reading.recordable:
            assert reading.resolution is not None
            resolutions[str(key)] = reading.resolution
        else:
            unrecordable.append(reading)

    changed = resolutions != existing
    artifact = ResolutionArtifact(
        generated_at=datetime.now(UTC) if changed else _generated_at(artifact_path),
        resolutions=resolutions,
    )
    if changed:
        artifact.dump(artifact_path)
    return VerifyReport(
        artifact=artifact,
        unrecordable=unrecordable,
        table_unconsulted=table_unconsulted,
        written=changed,
    )


def _generated_at(artifact_path: Path) -> datetime:
    """The stamp already on disk, or now for a file that does not exist yet."""
    if artifact_path.exists():
        return ResolutionArtifact.load(artifact_path).generated_at
    return datetime.now(UTC)
