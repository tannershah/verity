"""The parity gate: replacing the seed's resolver changed nothing the gate reads.

M6-T1a deleted the provisional `urllib` resolver and moved its request and parsing shapes
into `verity.retrieval`. That swap is uncheckable by comparing a fresh live run against the
committed `seed/key_resolution.json`, because both the parser *and* the API moved between
the two recordings and the diff cannot say which. So raw registry responses were recorded
first, and this compares the new parsers over those bytes against the old parser's output
already committed in the artifact.

**Why the gate is the thing compared, and not just the readings.** Quote matching is
substring containment over an abstract reconstructed from an inverted index, and identity is
title equality with containment deliberately removed. A single space added to the
reconstruction join demotes a `verified-primary` row to `single-secondary` while every
reading still looks plausible. `TierAssessment` is where that surfaces — it carries the
effective tier, which sources confirmed identity, the registry-identity conflict, and the
quote's source, field, word count and occurrence count.

**Offline by construction.** Only the committed fixture directory is read — never
`.cache/http` — so this proves a clean checkout reproduces the corpus, and the Retraction
Watch reading comes from the committed sample rather than the 66 MB gitignored table. The
five rows that quote that table are the most drift-sensitive in the corpus, and skipping
them for want of a bulk download would be the silent cap `-rs` exists to expose.

The corpus is iterated, never counted: adding a seed row extends this test rather than
editing it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from verity.alethiology import verify_keys
from verity.alethiology.resolution import REGISTRY_SOURCES, KeyResolution, ResolutionArtifact
from verity.alethiology.seed import read_seed
from verity.alethiology.seed._gate import assess
from verity.alethiology.seed._row import SeedFact
from verity.keys import ExternalKey
from verity.retrieval import retraction_watch as rw
from verity.retrieval.http import FIXTURE_ROOT, CacheMode, HttpCache, build_client

pytestmark = pytest.mark.usefixtures("poisoned_socket")

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "seed" / "alethiology.jsonl"
ARTIFACT_PATH = ROOT / "seed" / "key_resolution.json"

#: Fields of a `SourceReading` that say what a source returned. `checked_at` is excluded
#: because two recordings are two times by definition.
CONTENT_FIELDS = ("source", "found", "url", "title", "year", "abstract", "record", "detail")


@pytest.fixture(scope="module")
def rows() -> list[SeedFact]:
    return read_seed(SEED_PATH)


@pytest.fixture(scope="module")
def committed() -> ResolutionArtifact:
    return ResolutionArtifact.load(ARTIFACT_PATH)


@pytest.fixture(scope="module")
def recorded(rows: list[SeedFact]) -> dict[str, KeyResolution]:
    """Every seed key resolved through the new clients, from committed fixtures alone."""
    client = build_client(mode=CacheMode.REPLAY, cache=HttpCache([FIXTURE_ROOT], []))
    keys = sorted({row.external_key() for row in rows}, key=str)
    readings = {
        str(key): verify_keys.resolve(key, client, table=rw.SAMPLE_TABLE) for key in keys
    }
    unrecordable = {key: r.why_not() for key, r in readings.items() if not r.recordable}
    assert not unrecordable, f"the committed fixtures do not settle {unrecordable}"
    return {key: reading.resolution for key, reading in readings.items()}


def content(reading: object) -> dict[str, object]:
    return {field: getattr(reading, field) for field in CONTENT_FIELDS}


def test_every_seed_key_has_a_committed_fixture(
    rows: list[SeedFact], recorded: dict[str, KeyResolution]
) -> None:
    """A missing fixture must fail here, not silently narrow every test below it."""
    missing = sorted({str(row.external_key()) for row in rows} - set(recorded))
    assert not missing, f"no recorded response for {missing}"


def test_the_retraction_watch_sample_covers_the_rows_that_quote_it(
    rows: list[SeedFact], recorded: dict[str, KeyResolution]
) -> None:
    quoting = {
        str(row.external_key())
        for row in rows
        if row.attributed_to == "Retraction Watch" and row.quote
    }
    assert quoting, "no seed row quotes Retraction Watch; this test has lost its subject"
    for key in sorted(quoting):
        reading = recorded[key].reading(rw.SOURCE)
        assert reading is not None and reading.found, (
            f"{key} is quoted from the Retraction Watch table but the committed sample "
            "does not carry its row"
        )


def test_readings_are_identical_to_the_committed_artifact(
    committed: ResolutionArtifact, recorded: dict[str, KeyResolution]
) -> None:
    """New parser over new bytes against old parser over old bytes, field by field."""
    differences: list[str] = []
    for rendered, resolution in sorted(recorded.items()):
        prior = committed.resolutions.get(rendered)
        assert prior is not None, f"{rendered} is not in the committed artifact"
        assert sorted(resolution.readings) == sorted(prior.readings), (
            f"{rendered} was consulted at a different set of sources"
        )
        for source, reading in sorted(resolution.readings.items()):
            new, old = content(reading), content(prior.readings[source])
            for field in CONTENT_FIELDS:
                if new[field] != old[field]:
                    differences.append(
                        f"{rendered} {source}.{field}: {old[field]!r} -> {new[field]!r}"
                    )
    assert not differences, "\n".join(differences)


def test_aliases_are_unchanged(
    committed: ResolutionArtifact, recorded: dict[str, KeyResolution]
) -> None:
    for rendered, resolution in sorted(recorded.items()):
        prior = committed.resolutions[rendered]
        assert [str(a) for a in resolution.aliases] == [str(a) for a in prior.aliases], rendered


def test_the_gate_reaches_the_same_verdict_on_every_row(
    rows: list[SeedFact], committed: ResolutionArtifact, recorded: dict[str, KeyResolution]
) -> None:
    """The assessment, not just the reading — this is what a tier demotion shows up in."""
    differences: list[str] = []
    for row in rows:
        rendered = str(row.external_key())
        before = assess(row, committed.resolutions[rendered])
        after = assess(row, recorded[rendered])
        if before != after:
            differences.append(
                f"{row.slug}:\n    committed={before!r}\n    recorded ={after!r}"
            )
    assert not differences, "\n".join(differences)


def test_the_demo_findings_survive_the_swap(
    rows: list[SeedFact], recorded: dict[str, KeyResolution]
) -> None:
    """The three rows the demo narrative rests on, checked by name rather than in bulk."""
    by_slug = {row.slug: row for row in rows}
    conflict = assess(by_slug["rw-17524-retraction"], recorded["doi:10.3823/1654"])
    # Retraction Watch names the chocolate paper; both registries serve a different work.
    assert conflict.registry_identity_conflict
    assert conflict.quote_match is not None and conflict.quote_match.field == "record"
    assert conflict.capped, "the identity conflict stopped capping the row"

    hamblin = assess(by_slug["hamblin-1981-decimal"], recorded["doi:10.1136/bmj.283.6307.1671"])
    assert hamblin.quote_match is not None and hamblin.quote_match.field == "abstract"
    assert hamblin.quote_match.occurrences == 1


def test_grounding_eligibility_is_unchanged_across_the_corpus(
    rows: list[SeedFact], committed: ResolutionArtifact, recorded: dict[str, KeyResolution]
) -> None:
    """The numerator of a pre-registered measurement must not move because a parser did."""

    def eligible(artifact: dict[str, KeyResolution]) -> set[str]:
        return {
            row.slug
            for row in rows
            if assess(row, artifact[str(row.external_key())]).effective_tier.value
            in ("verified-primary", "corroborated-multi-secondary")
        }

    assert eligible(recorded) == eligible(committed.resolutions)


def test_a_key_absent_from_every_source_is_still_refused(
    recorded: dict[str, KeyResolution]
) -> None:
    """The gate's abort path, on the identifier that motivated it."""
    invented = ExternalKey.parse("10.1080/00071668108416780")
    assert str(invented) not in recorded


def test_a_key_nothing_could_check_is_not_written_to_the_artifact(tmp_path: Path) -> None:
    """A network failure is not "resolves in no source consulted", which the gate deletes on.

    Without a credential every registry 404 comes back `unreachable`, and an artifact that
    recorded those as `found=False` would tell a curator to drop a real, curated DOI.
    """
    from verity.retrieval.http import CrossrefCredential, HttpClient, OpenAlexCredential

    class Refusing:
        def send(self, url: str, headers, timeout_s: float) -> object:  # noqa: ANN001
            from verity.retrieval.http import RawResponse

            return RawResponse(status=404, body="", headers={"x-api-pool": "public-single"})

    client = HttpClient(
        credentials=[OpenAlexCredential(None), CrossrefCredential(None)],
        mode=CacheMode.LIVE,
        cache=HttpCache([tmp_path], []),
        transport=Refusing(),
    )
    hamblin = ExternalKey.parse("10.1136/bmj.283.6307.1671")
    artifact_path = tmp_path / "resolution.json"
    report = verify_keys.verify([hamblin], artifact_path, client=client, table=rw.SAMPLE_TABLE)

    assert str(hamblin) not in report.artifact.resolutions
    assert [r.key for r in report.unrecordable] == [hamblin]
    assert "openalex" in report.unrecordable[0].why_not()


def test_a_pmid_key_is_still_recordable_though_crossref_cannot_speak(tmp_path: Path) -> None:
    """The corpus has three, and a blanket refusal on `unanswered` would drop all of them."""
    client = build_client(mode=CacheMode.REPLAY, cache=HttpCache([FIXTURE_ROOT], []))
    reading = verify_keys.resolve(
        ExternalKey.parse("25272616"), client, table=rw.SAMPLE_TABLE
    )
    assert reading.recordable
    assert set(reading.not_applicable) == {"crossref"} and not reading.unreachable
    assert reading.resolution.readings["crossref"].found is False


def test_a_run_that_resolved_nothing_new_leaves_the_artifact_alone(tmp_path: Path) -> None:
    """`generated_at` stamps every seeded fact, so a no-op run must not produce a diff."""
    client = build_client(mode=CacheMode.REPLAY, cache=HttpCache([FIXTURE_ROOT], []))
    artifact_path = tmp_path / "resolution.json"
    key = ExternalKey.parse("10.1136/bmj.283.6307.1671")

    first = verify_keys.verify([key], artifact_path, client=client, table=rw.SAMPLE_TABLE)
    assert first.written
    before = artifact_path.read_text()

    again = verify_keys.verify([key], artifact_path, client=client, table=rw.SAMPLE_TABLE)
    assert not again.written
    assert artifact_path.read_text() == before


def test_a_failed_run_does_not_create_an_artifact(tmp_path: Path) -> None:
    """Exiting non-zero and modifying tracked state on the way out is the worse outcome."""
    from verity.retrieval.http import (
        CrossrefCredential,
        HttpClient,
        OpenAlexCredential,
        RawResponse,
    )

    class Refusing:
        def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
            return RawResponse(status=404, body="", headers={"x-api-pool": "public-single"})

    artifact_path = tmp_path / "never-written.json"
    report = verify_keys.verify(
        [ExternalKey.parse("10.1136/bmj.283.6307.1671")],
        artifact_path,
        client=HttpClient(
            credentials=[OpenAlexCredential(None), CrossrefCredential(None)],
            mode=CacheMode.LIVE,
            cache=HttpCache([tmp_path], []),
            transport=Refusing(),
        ),
        table=rw.SAMPLE_TABLE,
    )
    assert report.unrecordable and not report.written
    assert not artifact_path.exists()


def test_an_unreachable_key_never_erases_the_entry_it_already_had(tmp_path: Path) -> None:
    """A flaky network must not delete a good committed reading under `--refresh`."""
    from verity.retrieval.http import (
        CrossrefCredential,
        HttpClient,
        OpenAlexCredential,
        RawResponse,
    )

    class Refusing:
        def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
            return RawResponse(status=404, body="", headers={"x-api-pool": "public-single"})

    artifact_path = tmp_path / "resolution.json"
    key = ExternalKey.parse("10.1136/bmj.283.6307.1671")
    good = build_client(mode=CacheMode.REPLAY, cache=HttpCache([FIXTURE_ROOT], []))
    verify_keys.verify([key], artifact_path, client=good, table=rw.SAMPLE_TABLE)
    recorded = artifact_path.read_text()

    report = verify_keys.verify(
        [key],
        artifact_path,
        refresh=True,
        client=HttpClient(
            credentials=[OpenAlexCredential(None), CrossrefCredential(None)],
            mode=CacheMode.LIVE,
            cache=HttpCache([tmp_path / "cache"], []),
            transport=Refusing(),
        ),
        table=rw.SAMPLE_TABLE,
    )
    assert report.unrecordable
    assert str(key) in report.artifact.resolutions, "a network failure deleted a good entry"
    assert artifact_path.read_text() == recorded


def test_a_replay_refresh_re_reads_the_fixtures_rather_than_the_network(
    rows: list[SeedFact], committed: ResolutionArtifact, tmp_path: Path
) -> None:
    """`--refresh --cache-mode replay` is how the artifact is re-recorded after a parser
    change: `refresh` says which entries may be rewritten, `cache_mode` says where the
    bytes come from, and only separating them makes the re-record offline.

    Two properties, and the second is the one that makes the first usable. It reaches no
    network — the module's poisoned socket is the enforcement. And what it writes is
    *reproducible*: a cache hit replays the fixture's `fetched_at` rather than restamping
    it, so two refreshes agree to the microsecond on every registry reading and the diff of
    a re-record is what the parser changed and nothing else. Only values generated locally
    move between refreshes — the Retraction Watch read, which the table cannot date, and a
    not-applicable reading, whose time is all the time there is.

    Reproducible is not the same as equal to what is committed. The artifact was recorded
    before the fixtures were, so a replay refresh moves each registry `checked_at` forward
    once, to the time the recording it now reads was actually taken. Content is what must
    not move, and content is what this compares.
    """
    keys = sorted({row.external_key() for row in rows}, key=str)

    def refresh_into(name: str) -> ResolutionArtifact:
        artifact_path = tmp_path / name
        artifact_path.write_text(ARTIFACT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        report = verify_keys.verify(
            keys,
            artifact_path,
            refresh=True,
            cache_mode=CacheMode.REPLAY,
            table=rw.SAMPLE_TABLE,
        )
        assert not report.unrecordable, (
            "the committed fixtures no longer settle every seed key"
        )
        return ResolutionArtifact.load(artifact_path)

    first, second = refresh_into("first.json"), refresh_into("second.json")

    for rendered in sorted(str(key) for key in keys):
        before, after = committed.resolutions[rendered], first.resolutions[rendered]
        assert sorted(before.readings) == sorted(after.readings), rendered
        for source in sorted(before.readings):
            assert content(before.readings[source]) == content(after.readings[source]), (
                f"{rendered} {source}"
            )
            if source in REGISTRY_SOURCES and after.readings[source].found:
                assert (
                    after.readings[source].checked_at
                    == second.resolutions[rendered].readings[source].checked_at
                ), f"{rendered} {source} stamped a clock instead of replaying the fixture's"
