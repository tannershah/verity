"""M7-T1's retraction layer: the cut, the readings it is made from, and where it lands.

Offline by construction. The registry half runs from the committed fixtures and the module
poisons sockets, so a test that reached the network fails loudly rather than spending
OpenAlex credits; the Retraction Watch half runs from the committed two-row sample except
where a test is explicitly about the bulk table, which is gitignored and skipped for.

The corpus does the heavy lifting. Every shape the policy has to separate is a real work
with committed bytes behind it — a three-source retraction, a retraction OpenAlex alone
knows about under a PMID Crossref cannot index, a publisher-filed correction, a review that
carries `update-to: new_version` because it *is* the new version, and fifteen clean works.
Constructed readings appear only where the corpus has no occupant: the disagreement case,
which needs a source to be wrong, and the totality of the outcome map.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from verity.alethiology.seed import load_seed
from verity.alethiology.service import Alethiology
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, GraphMetadata, Premise
from verity.models.common import (
    PremiseType,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
    TerminationReason,
)
from verity.models.evidence import EvidenceQuality, RetractionCheck
from verity.models.render import to_render_payload
from verity.presentation import layout
from verity.quality import retraction
from verity.quality.apply import apply_retractions, stored_keys
from verity.quality.retraction import PARTIAL_BASIS, decide
from verity.quality.service import assess_key, assess_keys
from verity.retrieval import openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.http import FIXTURE_ROOT, CacheMode, HttpCache, build_client
from verity.retrieval.record import ReadingOutcome, UnansweredReason, WorkRecord, unanswered
from verity.store.db import open_db

pytestmark = pytest.mark.usefixtures("poisoned_socket")

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "seed" / "alethiology.jsonl"
ARTIFACT = ROOT / "seed" / "key_resolution.json"
CHECKED_AT = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

CHOCOLATE = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
HESPERIDIN_PMID = ExternalKey(type=KeyType.PMID, value="31844967")
#: The hesperidin work's DOI. Deliberately *not* in the fixtures: nothing may follow the
#: alias from the PMID to it.
HESPERIDIN_DOI = ExternalKey(type=KeyType.DOI, value="10.1007/s00394-019-02105-2")
CORRECTED = ExternalKey(type=KeyType.DOI, value="10.1371/journal.pmed.0020124")
COCHRANE = ExternalKey(type=KeyType.DOI, value="10.1002/14651858.cd008893.pub3")
HAMBLIN = ExternalKey(type=KeyType.DOI, value="10.1136/bmj.283.6307.1671")


@pytest.fixture
def client():  # noqa: ANN201
    """Committed fixtures only. Never the working cache, never the network."""
    return build_client(mode=CacheMode.REPLAY, cache=HttpCache([FIXTURE_ROOT], []))


@pytest.fixture
def seeded(tmp_path: Path):  # noqa: ANN201
    """A store built the way the quickstart builds one: seed, and nothing else."""
    with open_db(tmp_path / "verity.db") as conn:
        load_seed(conn, SEED, ARTIFACT)
        yield conn


def check(source: RetractionSource, result: RetractionFinding) -> RetractionCheck:
    return RetractionCheck(source=source, result=result, checked_at=CHECKED_AT)


# -- the cut ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("findings", "expected"),
    [
        pytest.param({}, RetractionStatus.UNKNOWN, id="nothing-consulted"),
        pytest.param(
            {RetractionSource.RETRACTION_WATCH: RetractionFinding.RETRACTED},
            RetractionStatus.RETRACTED,
            id="the-table-alone-is-decisive",
        ),
        pytest.param(
            {
                RetractionSource.OPENALEX: RetractionFinding.RETRACTED,
                RetractionSource.CROSSREF: RetractionFinding.RETRACTED,
            },
            RetractionStatus.RETRACTED,
            id="both-apis-agreeing",
        ),
        pytest.param(
            {RetractionSource.OPENALEX: RetractionFinding.RETRACTED},
            RetractionStatus.FLAGGED_UNCONFIRMED,
            id="one-api-alone",
        ),
        pytest.param(
            {
                RetractionSource.OPENALEX: RetractionFinding.RETRACTED,
                RetractionSource.CROSSREF: RetractionFinding.CLEAN,
                RetractionSource.RETRACTION_WATCH: RetractionFinding.CLEAN,
            },
            RetractionStatus.FLAGGED_UNCONFIRMED,
            id="the-disagreement-case-renders-flagged-not-retracted",
        ),
        pytest.param(
            {
                RetractionSource.RETRACTION_WATCH: RetractionFinding.RETRACTED,
                RetractionSource.OPENALEX: RetractionFinding.CLEAN,
            },
            RetractionStatus.RETRACTED,
            id="the-table-outranks-an-api-that-disagrees",
        ),
        pytest.param(
            {
                RetractionSource.OPENALEX: RetractionFinding.CLEAN,
                RetractionSource.CROSSREF: RetractionFinding.NOTICE_NOT_RETRACTION,
            },
            RetractionStatus.CLEAN,
            id="a-notice-that-is-not-a-retraction-leaves-the-work-standing",
        ),
        pytest.param(
            {
                RetractionSource.OPENALEX: RetractionFinding.NOT_INDEXED,
                RetractionSource.CROSSREF: RetractionFinding.NOT_INDEXED,
            },
            RetractionStatus.UNKNOWN,
            id="no-opinion-is-not-clean",
        ),
        pytest.param(
            {RetractionSource.CROSSREF: RetractionFinding.NOTICE_NOT_RETRACTION},
            RetractionStatus.UNKNOWN,
            id="a-notice-alone-settles-nothing-about-retraction",
        ),
    ],
)
def test_the_cut(findings: dict, expected: RetractionStatus) -> None:
    """build-plan.md M7-T1: RW-table or both-API agreement → retracted; single API source →
    flagged. `clean` needs one source that answered and found nothing, which is the
    deliberate asymmetry — a missed retraction is the failure this module exists to prevent.
    """
    checks = {source: check(source, finding) for source, finding in findings.items()}
    assert decide(checks) is expected


def test_the_cut_is_total_over_the_finding_vocabulary() -> None:
    """Every finding a source can return has to reach a status, or a new enum value would
    fall through to whichever branch happened to be last."""
    for finding in RetractionFinding:
        for source in RetractionSource:
            status = decide({source: check(source, finding)})
            assert isinstance(status, RetractionStatus)
            if finding is not RetractionFinding.RETRACTED:
                assert status is not RetractionStatus.RETRACTED
                assert status is not RetractionStatus.FLAGGED_UNCONFIRMED


def test_a_status_the_cut_produces_is_always_representable_on_a_fact() -> None:
    """`EvidenceQuality` refuses a flag no consulted source asserts and refuses `clean`
    while one does. A cut that produced a status the model rejects would raise a
    `ValidationError` at write time, which no stage isolates — a traceback on the demo path
    from a check that had already succeeded."""
    for finding in RetractionFinding:
        for source in RetractionSource:
            checks = {source: check(source, finding)}
            quality = EvidenceQuality(retraction=decide(checks), retraction_checks=checks)
            assert quality.retraction is decide(checks)


# -- one source's reading to one finding -----------------------------------------------


def test_the_three_source_agreement_on_the_demo_doi(client) -> None:  # noqa: ANN001
    """The retraction beat, read off committed bytes rather than asserted."""
    assessment = assess_key(client, CHOCOLATE, table=rw.SAMPLE_TABLE)

    assert assessment.status is RetractionStatus.RETRACTED
    assert set(assessment.checks) == set(RetractionSource)
    assert all(
        c.result is RetractionFinding.RETRACTED for c in assessment.checks.values()
    )
    assert not assessment.has_disagreement


def test_agreement_between_the_two_apis_can_be_one_record_seen_twice(client) -> None:  # noqa: ANN001
    """Crossref carries Retraction-Watch-sourced updates verbatim and OpenAlex ingests
    Crossref, so "three sources agree" is a claim about consultation, not independence. The
    record id is what makes the echo visible instead of counting as a second vote."""
    assessment = assess_key(client, CHOCOLATE, table=rw.SAMPLE_TABLE)

    assert assessment.derived_records == ("record-id=17524",)
    crossref_check = assessment.checks[RetractionSource.CROSSREF]
    assert "source=retraction-watch" in (crossref_check.detail or "")
    table_check = assessment.checks[RetractionSource.RETRACTION_WATCH]
    assert "record-id=17524" in (table_check.detail or "")
    assert "not a second source" in "\n".join(assessment.render())


def test_a_publisher_filed_correction_is_a_notice_and_not_a_retraction(client) -> None:  # noqa: ANN001
    """The case that makes the fourth finding earn its place, and the case that makes
    `updated-by` the right field: this work's correction appears only there, so an
    `update-to` reader would see nothing on a work that was corrected."""
    assessment = assess_key(client, CORRECTED, table=rw.SAMPLE_TABLE)

    assert assessment.status is RetractionStatus.CLEAN
    assert (
        assessment.checks[RetractionSource.CROSSREF].result
        is RetractionFinding.NOTICE_NOT_RETRACTION
    )
    assert not assessment.has_disagreement, (
        "a correction and an absence of notices agree that the work stands; reporting that "
        "as a disagreement would mark every clean row in the demo"
    )


def test_a_work_that_is_itself_a_new_version_carries_no_notice_against_it(client) -> None:  # noqa: ANN001
    """`update-to: new_version` says this review *is* the new version. Read as a notice on
    the work it would invert the link, which is the defect `updated-by` fixes."""
    assessment = assess_key(client, COCHRANE, table=rw.SAMPLE_TABLE)

    assert assessment.status is RetractionStatus.CLEAN
    assert assessment.checks[RetractionSource.CROSSREF].result is RetractionFinding.CLEAN


def test_several_notices_are_read_as_a_set_not_as_a_joined_string() -> None:
    """`_joined` renders the whole `updated-by` list, so a work corrected and later
    retracted yields `"correction,retraction"`. Equality against that string finds no
    retraction; membership does."""
    record = WorkRecord(
        source="crossref",
        outcome=ReadingOutcome.FOUND,
        fetched_at=CHECKED_AT,
        key=CHOCOLATE,
        raw_findings={"updated_by_type": "correction,retraction"},
    )
    assert retraction.crossref_finding(record).result is RetractionFinding.RETRACTED


def test_a_pmid_is_settled_without_following_an_alias_to_an_unrecorded_doi(client) -> None:  # noqa: ANN001
    """OpenAlex reports this work's DOI, and handing it to Crossref would turn a
    `not-applicable` into an answer — about an identifier this run was not given, whose
    bytes are in no fixture. The binder and the grounding predicate refuse aliases for the
    same reason, and a replay miss here would prove the request went out."""
    assessment = assess_key(client, HESPERIDIN_PMID, table=rw.SAMPLE_TABLE)

    assert assessment.status is RetractionStatus.RETRACTED
    assert RetractionSource.CROSSREF in assessment.not_consulted
    assert "pmid" in assessment.not_consulted[RetractionSource.CROSSREF]
    assert RetractionSource.CROSSREF not in assessment.checks

    with pytest.raises(Exception, match="replay mode has no entry"):
        # The alias, asked for directly: no fixture exists, which is what makes the
        # assertion above a statement about behaviour rather than about coverage.
        openalex.fetch_work(client, HESPERIDIN_DOI)


@pytest.mark.parametrize(
    "reason", [UnansweredReason.NOT_APPLICABLE, UnansweredReason.UNREACHABLE]
)
@pytest.mark.parametrize(
    "reader",
    [retraction.openalex_finding, retraction.crossref_finding],
    ids=["openalex", "crossref"],
)
def test_no_answer_is_never_a_finding(reader, reason: UnansweredReason) -> None:  # noqa: ANN001
    """Neither way of having no answer may become a check. `NOT_APPLICABLE` is permanent
    and says nothing about the work; `UNREACHABLE` says nothing about anything."""
    record = unanswered(
        "either", CHECKED_AT, CHOCOLATE, reason=reason, because="no answer to be had"
    )
    assert reader(record) is None


def test_a_degraded_404_is_never_clean() -> None:
    """Header authentication fails open onto an anonymous pool, so a 404 to an
    uncredentialed request may be that pool declining to look. `from_missing` reads it as
    unreachable, and the finding readers must not turn it back into a negative."""
    from verity.retrieval.record import from_missing

    for degraded, expected in ((True, None), (False, RetractionFinding.NOT_INDEXED)):
        record = from_missing("openalex", CHOCOLATE, CHECKED_AT, degraded=degraded)
        finding = retraction.openalex_finding(record)
        assert (finding.result if finding else None) is expected


def test_an_absent_work_is_not_indexed_rather_than_clean() -> None:
    """A registry indexes works, so a 404 is a work it has never heard of — no opinion.
    Counting it as clean would let an unindexed DOI outvote a source that found a
    retraction."""
    from verity.retrieval.record import absent

    for reader in (retraction.openalex_finding, retraction.crossref_finding):
        assert reader(absent("s", CHECKED_AT, CHOCOLATE)).result is (
            RetractionFinding.NOT_INDEXED
        )


# -- which copy of the table answered --------------------------------------------------


def test_a_miss_against_the_committed_sample_is_not_a_reading(client) -> None:  # noqa: ANN001
    """The whole reason `resolve_table` returns an identity. Both tables produce an
    identical `WorkRecord` for a key they do not hold, so a policy branching on the outcome
    would answer "checked, and clean" for every key on a fresh clone — this tier's
    strongest negative, manufactured from the smallest file in the repository."""
    assessment = assess_key(client, HAMBLIN, table=rw.SAMPLE_TABLE)

    assert RetractionSource.RETRACTION_WATCH not in assessment.checks
    reason = assessment.not_consulted[RetractionSource.RETRACTION_WATCH]
    assert "sample" in reason and str(rw.TABLE) in reason
    assert assessment.status is RetractionStatus.CLEAN, (
        "the registries still answered, so the work is clean on their evidence alone"
    )


@pytest.mark.skipif(
    not rw.TABLE.exists(), reason="data/retraction_watch.csv not present (data/ is gitignored)"
)
def test_a_miss_against_the_bulk_table_is_evidence_the_work_stands(client) -> None:  # noqa: ANN001
    """The same key, the other table. Absence from a census of 71,799 recorded retractions
    is the strongest clean signal available, and without it no work could ever reach
    `clean` and M5-T2's retraction-clean promotion gate would be unsatisfiable."""
    assessment = assess_key(client, HAMBLIN, table=rw.TABLE)

    table_check = assessment.checks[RetractionSource.RETRACTION_WATCH]
    assert table_check.result is RetractionFinding.CLEAN
    assert str(rw.TABLE) in (table_check.detail or "")


def test_no_table_on_disk_is_reported_rather_than_read_as_silence(
    client, tmp_path: Path  # noqa: ANN001
) -> None:
    """An absent table is a source nobody asked, which `rw.read` already refuses to render
    as a not-found reading. The assessment says so instead of omitting the source."""
    assessment = assess_key(client, CHOCOLATE, table=tmp_path / "nothing.csv")

    assert RetractionSource.RETRACTION_WATCH not in assessment.checks
    assert RetractionSource.RETRACTION_WATCH in assessment.not_consulted


def test_read_many_answers_exactly_as_read_does() -> None:
    """`read` delegates to `read_many`, so the two cannot drift — this pins that they do
    not, over a hit, a miss, and a key type the table has no column for."""
    nct = ExternalKey(type=KeyType.NCT, value="NCT04280705")
    keys = [CHOCOLATE, HESPERIDIN_PMID, HAMBLIN, nct]
    batch = rw.read_many(keys, rw.SAMPLE_TABLE)

    assert {r.outcome for r in batch.values()} == {
        ReadingOutcome.FOUND,
        ReadingOutcome.ABSENT,
        ReadingOutcome.UNANSWERED,
    }
    for key in keys:
        one = rw.read(key, rw.SAMPLE_TABLE)
        assert one.model_dump(exclude={"fetched_at"}) == batch[str(key)].model_dump(
            exclude={"fetched_at"}
        )


def test_resolve_table_prefers_the_bulk_download_and_names_what_it_found() -> None:
    sample = rw.resolve_table(rw.SAMPLE_TABLE)
    assert sample is not None and not sample.complete
    assert "committed sample" in sample.describe()

    resolved = rw.resolve_table()
    if rw.TABLE.exists():
        assert resolved is not None and resolved.complete and resolved.path == rw.TABLE


# -- writing it onto the alethiology ---------------------------------------------------


def test_apply_writes_the_finding_and_preserves_everything_the_store_owns(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    """The status has to land where `to_render_payload` looks for it, and nothing else may
    move: tier and status are M5's and M8's, and `revalidated_at` is M5-T3's record of a
    *full* re-validation that a one-dimension re-read has not performed."""
    before = {f.id: f for f in _facts(seeded)}
    report = apply_retractions(seeded, client, stored_keys(seeded))
    after = {f.id: f for f in _facts(seeded)}

    assert report.is_partial and report.basis == PARTIAL_BASIS
    assert before.keys() == after.keys(), "a retraction pass created or destroyed a fact"
    for fact_id, was in before.items():
        now = after[fact_id]
        assert (now.tier, now.status, now.revalidated_at, now.provenance, now.created_at) == (
            was.tier,
            was.status,
            was.revalidated_at,
            was.provenance,
            was.created_at,
        )

    chocolate = [f for f in after.values() if f.key.matches(CHOCOLATE)]
    assert len(chocolate) == 5, "the demo DOI carries five attributions"
    for fact in chocolate:
        assert fact.evidence_quality.retraction is RetractionStatus.RETRACTED
        assert fact.status.value == "IN", "flipping a fact OUT is M8-T2's, not this tier's"


def test_a_second_pass_confirms_without_rewriting(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    """The Retraction Watch reading is stamped at read time because the table has no
    per-row date, so a pass that restamped every confirmation would rewrite the whole store
    on every invocation. A re-confirmed check keeps its time — the same rule
    `apply_groundings` applies to `grounded_at` — and the report is where the re-check
    stays visible."""
    apply_retractions(seeded, client, stored_keys(seeded))
    first = {f.id: f.evidence_quality for f in _facts(seeded)}

    report = apply_retractions(seeded, client, stored_keys(seeded))
    assert report.counts["written"] == 0
    assert report.counts["unchanged"] == len(first)
    assert {f.id: f.evidence_quality for f in _facts(seeded)} == first


def test_a_source_that_could_not_be_reached_loses_its_check_rather_than_keeping_it(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    """Merging per source across runs would let a status be computed from two runs at once
    — an OpenAlex reading taken with the bulk table beside a Crossref one taken without it
    — and the timestamp rule is exactly what would hide it. So a source not consulted this
    pass is dropped, not preserved."""
    apply_retractions(seeded, client, [CHOCOLATE])
    stored = _facts_for(seeded, CHOCOLATE)[0]
    assert RetractionSource.RETRACTION_WATCH in stored.evidence_quality.retraction_checks

    from verity.store.facts import save_fact

    save_fact(
        seeded,
        stored.model_copy(
            update={
                "evidence_quality": EvidenceQuality(
                    retraction=RetractionStatus.RETRACTED,
                    retraction_checks={
                        **stored.evidence_quality.retraction_checks,
                        RetractionSource.OPENALEX: check(
                            RetractionSource.OPENALEX, RetractionFinding.RETRACTED
                        ),
                    },
                )
            }
        ),
    )
    # A pass that cannot reach any registry: the table alone still settles the DOI.
    offline = build_client(
        mode=CacheMode.REPLAY, cache=HttpCache([Path("/nonexistent")], [])
    )
    apply_retractions(seeded, offline, [CHOCOLATE])
    after = _facts_for(seeded, CHOCOLATE)[0].evidence_quality
    assert set(after.retraction_checks) == {RetractionSource.RETRACTION_WATCH}


def test_one_unresolvable_key_does_not_cost_the_others_their_readings(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    """A `CacheMissError` is a `RetrievalError`, and one key with no committed fixture must
    degrade that key rather than abort a pass over the whole store."""
    unrecorded = ExternalKey(type=KeyType.DOI, value="10.9999/verity-has-no-fixture")
    assessments = assess_keys(client, [unrecorded, CHOCOLATE], table=rw.SAMPLE_TABLE)

    assert assessments[str(unrecorded)].status is RetractionStatus.UNKNOWN
    assert set(assessments[str(unrecorded)].not_consulted) == {
        RetractionSource.OPENALEX,
        RetractionSource.CROSSREF,
        RetractionSource.RETRACTION_WATCH,
    }
    assert assessments[str(CHOCOLATE)].status is RetractionStatus.RETRACTED


def test_a_three_source_check_map_survives_the_store_with_its_zones(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    """`RetractionCheck` refuses a naive `checked_at`, so a serializer that dropped the
    offset would turn a re-load into a `ValidationError` at render time — a crash on the
    demo path, from the one field nothing else exercises with three sources at once."""
    apply_retractions(seeded, client, [CHOCOLATE])
    reloaded = _facts_for(seeded, CHOCOLATE)[0].evidence_quality

    assert set(reloaded.retraction_checks) == set(RetractionSource)
    for source, stored in reloaded.retraction_checks.items():
        assert stored.checked_at.tzinfo is not None, source


def test_nothing_is_written_under_check(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    before = {f.id: f.evidence_quality for f in _facts(seeded)}
    report = apply_retractions(seeded, client, stored_keys(seeded), apply=False)

    assert not report.applied and report.flagged
    assert {f.id: f.evidence_quality for f in _facts(seeded)} == before


# -- and where it shows up -------------------------------------------------------------


def test_a_seeded_store_flags_nothing_until_the_pass_runs(
    seeded: sqlite3.Connection, client  # noqa: ANN001
) -> None:
    """The quickstart's ordering, made executable. Seeding creates the facts and concludes
    nothing about retraction; `python -m verity.quality apply` is what fills the column. A
    reviewer who skips it sees an empty column, so the README has to list it — and a
    committed store has to be a post-apply one."""
    graph = _graph_binding(CHOCOLATE)
    service = Alethiology.open(seeded, resolution_path=ARTIFACT)

    before = to_render_payload(graph, service)
    assert before.premises[0].retraction_flags == []

    apply_retractions(seeded, client, stored_keys(seeded))
    after = to_render_payload(graph, service)
    assert after.premises[0].retraction_flags == ["doi:10.3823/1654: retracted"]

    detail = next(
        d for d in layout.build(after).rows[0].details if d.kind is layout.DetailKind.RETRACTION
    )
    assert detail.label == "retracted" and detail.text == "doi:10.3823/1654"


def test_the_committed_demo_graph_carries_no_flag(client) -> None:  # noqa: ANN001
    """An empty retraction column on the shipped artifact is the checker being right, not
    the checker being broken. The spinach claim's one bound key is Hamblin's BMJ note,
    which every source finds standing."""
    from verity.export import graph_from_json

    graph = graph_from_json((ROOT / "data" / "demo" / "spinach.json").read_text())
    assert {str(p.bound_key) for p in graph.premises.values() if p.bound_key} == {
        f"doi:{HAMBLIN.value}"
    }
    assert assess_key(client, HAMBLIN, table=rw.SAMPLE_TABLE).status is RetractionStatus.CLEAN


def test_the_committed_chocolate_decomposition_binds_no_identifier() -> None:
    """The tree-level beat depends on the decomposer volunteering a key, and on the one
    committed chocolate decomposition it volunteered none — every premise's `candidate_key`
    is null, so nothing binds and nothing can carry a flag however correct the checker is.
    Phase 5's prompt rewrite is what moves this; recorded here so it is measured rather than
    remembered."""
    from verity.export import graph_from_json

    path = ROOT / "data" / "verifier" / "pilot" / "chocolate.json"
    graph = graph_from_json(path.read_text())
    assert graph.premises, "the pilot decomposition is empty"
    assert all(p.candidate_key is None for p in graph.premises.values())
    assert all(p.bound_key is None for p in graph.premises.values())


def test_writing_a_retraction_does_not_drift_a_recorded_run(tmp_path: Path, client) -> None:  # noqa: ANN001
    """The invalidation beat, stated exactly. Running the pass moves the *alethiology*, not
    the graph — so the stored graph re-renders with a flag it did not have, and `replay`
    still reports `reproduced` because nothing the run computed changed.

    This is the regression test for the two rules that make that true: `apply` does not
    touch `tier`, so a fact stays grounding-eligible, and it does not flip `TmsStatus`, so a
    grounded premise stays grounded. Break either and `ground`'s digest moves, the replay
    reports the store as having moved under the run, and the demo's claim that the graph is
    unchanged stops being true.

    The run is built here rather than read from a store, so the test does not depend on this
    machine having run the pipeline.
    """
    from tests.test_orchestration import _run

    from verity.cache import BlobCache
    from verity.config import VerityConfig
    from verity.orchestration import replay_run, store_outcome

    config = VerityConfig()
    config.paths.db_path = tmp_path / "verity.db"
    cache = BlobCache([tmp_path / "cache"], [tmp_path / "cache"])
    with open_db(config.paths.db_path) as conn:
        load_seed(conn, SEED, ARTIFACT)
        workspace = (config, conn, cache)
        outcome, _ = _run(workspace, bind=True, cache_mode=CacheMode.REPLAY)
        store_outcome(conn, outcome)
        assert outcome.graph is not None
        assert any(g for g in outcome.graph.groundings), "the run must ground something"

        before = replay_run(outcome.manifest.run_id, conn=conn, cache=cache)
        assert before.reproduced and not before.grounding_moved

        report = apply_retractions(conn, client, stored_keys(conn))
        assert report.counts["written"], "the pass wrote nothing, so it proves nothing here"

        after = replay_run(outcome.manifest.run_id, conn=conn, cache=cache)
        assert after.reproduced, f"a retraction pass drifted the run: {after.verdict}"
        assert not after.drifted and not after.grounding_moved
        assert after.graph_matches


def test_every_status_the_payload_can_carry_has_a_word_to_render_it() -> None:
    """R2 keeps `RetractionStatus` at four values, so nothing needs changing today. These
    are what make "nothing needs changing" survive the status that gets added next."""
    from verity.models.render import _FLAGGED_RETRACTION_STATES

    statuses = {status.value for status in RetractionStatus}
    assert set(_FLAGGED_RETRACTION_STATES) <= statuses
    assert set(_FLAGGED_RETRACTION_STATES) <= set(layout._RETRACTION_WORDS)


# -- helpers ---------------------------------------------------------------------------


def _facts(conn: sqlite3.Connection) -> list:
    from verity.export import from_json
    from verity.models.fact import Fact

    return [
        from_json(row["payload"], Fact)
        for row in conn.execute("SELECT payload FROM facts").fetchall()
    ]


def _facts_for(conn: sqlite3.Connection, key: ExternalKey) -> list:
    from verity.store.facts import facts_by_key

    return facts_by_key(conn, key)


def _graph_binding(key: ExternalKey) -> ClaimGraph:
    """A one-step graph whose single premise binds `key`. Synthetic, and named as such —
    no committed graph binds the chocolate DOI."""
    now = datetime(2026, 8, 17, tzinfo=UTC)
    claim = Claim(text="Eating dark chocolate accelerates weight loss.", created_at=now)
    premise = Premise(
        text="A published trial reported faster weight loss with daily dark chocolate.",
        premise_type=PremiseType.EMPIRICAL_CITABLE,
        termination_reason=TerminationReason.CITATION_SHAPED,
        bound_key=key,
    )
    return ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id], depth=0)],
        metadata=GraphMetadata(created_at=now),
    )
