"""The seed gate: what a curated row has to prove before it becomes a fact.

The seed is the one place in the system where a human — in practice an agent — writes
facts directly into the store, at tiers that feed a pre-registered measurement. These
tests are the record of what the loader refuses. Two of them exist because of things
actually found in this repository: `10.1080/00071668108416780` sat in the test fixtures as
a `verified-primary` grounding target and resolves in no registry, and `10.3823/1654`
resolves in both registries to a paper other than the one Retraction Watch records under
it.

The committed corpus is exercised as itself rather than through a stand-in. A quote that
stopped matching its source, a key that stopped resolving, or a tier that quietly became
grounding-eligible are all regressions in the artifact, not only in the code.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from verity.alethiology.seed import SeedError, load_seed, read_seed
from verity.alethiology.service import Alethiology
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Premise
from verity.models.common import (
    ConfidenceTier,
    PremiseType,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
    TmsStatus,
)
from verity.models.evidence import EvidenceQuality
from verity.store.db import connect
from verity.store.facts import load_fact, save_fact

REPO = Path(__file__).resolve().parents[1]
SEED = REPO / "seed" / "alethiology.jsonl"
ARTIFACT = REPO / "seed" / "key_resolution.json"
CHOCOLATE = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
HAMBLIN = ExternalKey(type=KeyType.DOI, value="10.1136/bmj.283.6307.1671")


@pytest.fixture
def conn(tmp_path):
    connection = connect(tmp_path / "seeded.db")
    yield connection
    connection.close()


@pytest.fixture
def report(conn):
    return load_seed(conn, SEED, ARTIFACT)


# -- the committed corpus ------------------------------------------------------------


def test_the_committed_seed_loads_and_every_quote_still_matches_its_source(report):
    """A quote that no longer appears in the text its source serves aborts the load, so
    reaching this assertion is the check."""
    assert report.by_action == {"inserted": len(report.rows)}
    assert report.grounding_eligible > 0


def test_the_seed_exercises_both_key_types_it_claims_to(report):
    """DOI and PMID paths are both live. NCT is not: no registered trial is load-bearing
    for either demo claim, and seeding one to look complete would be filler. The gap is
    reported here rather than left to be inferred from a passing suite."""
    assert set(report.by_key_type) == {"doi", "pmid"}
    assert report.by_key_type["pmid"] >= 2
    assert "nct" not in report.by_key_type


def test_both_demo_claims_are_covered(report):
    assert set(report.by_scope) == {"spinach-iron", "chocolate-hoax"}
    assert min(report.by_scope.values()) >= 5


def test_the_count_is_reported_rather_than_targeted(report):
    """build-plan.md §5 sizes this seed at ~50-100 facts. Two claims do not support that
    many quote-backed rows, and padding a fact store toward a number is the drift design.md
    §6 names NELL for. The honest count travels in the report and the seed README."""
    assert len(report.rows) == sum(report.by_scope.values())


# -- the identity conflict, as a first-class outcome ----------------------------------


def test_the_chocolate_doi_identity_conflict_is_reported_and_caps_the_tier(report):
    """Retraction Watch records `10.3823/1654` as the chocolate hoax; both registries serve
    a different paper under it; all three agree it is retracted. The retraction trail
    survives, the work identity does not, and no row keyed to it may ground anything."""
    rows = [row for row in report.rows if row.key == CHOCOLATE and "rw-17524" in row.slug]
    assert rows, "the chocolate trail must be seeded"
    for row in rows:
        assert row.registry_identity_conflict
        assert row.identity_confirmed_by == ["retraction-watch"]
        assert row.effective_tier is ConfidenceTier.SINGLE_SECONDARY
        assert not row.grounding_eligible
    assert any(row.capped for row in rows), "the requested tier must be visibly capped"


def test_a_row_asking_for_more_than_it_can_prove_loads_capped_not_refused(report):
    """A tier cap and a refusal are different events. The row still carries information;
    what it may not do is ground."""
    capped = [row for row in report.rows if row.capped]
    assert capped
    assert all(row.notes for row in capped), "a cap has to say why"


def test_a_registry_abstract_quote_is_what_earns_grounding_eligibility(report):
    eligible = [row for row in report.rows if row.grounding_eligible]
    assert eligible
    for row in eligible:
        assert row.quote_field == "abstract"
        assert row.quote_source in ("openalex", "crossref")
        assert row.effective_tier is ConfidenceTier.VERIFIED_PRIMARY


def test_no_seeded_fact_reaches_corroborated_multi_secondary(report):
    """Both grounding-eligible tiers feed the pre-registered numerator, and the seed has no
    mechanism that could establish corroboration. M5-T2 owns that promotion."""
    assert ConfidenceTier.CORROBORATED_MULTI_SECONDARY.value not in report.by_tier


# -- what the loader refuses ----------------------------------------------------------


def _row(**overrides) -> str:
    base = {
        "slug": "row-1",
        "claim_scope": "test",
        "key": str(HAMBLIN).split(":", 1)[1],
        "expected_title": "Fake.",
        "attributed_to": "Hamblin (1981)",
        "verb": "reports",
        "assertion": "his claims for spinach are spurious",
        "tier": "verified-primary",
        "quote": "his claims for spinach are spurious",
        "note": "test row",
    }
    return json.dumps({**base, **overrides})


def _write(tmp_path: Path, *lines: str) -> Path:
    path = tmp_path / "seed.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_quote_that_appears_in_no_source_is_refused(conn, tmp_path):
    """The fabrication case. A curator can write any sentence; only a verbatim one loads."""
    path = _write(tmp_path, _row(quote="spinach contains no iron whatsoever"))
    with pytest.raises(SeedError, match="appears in no text"):
        load_seed(conn, path, ARTIFACT)


def test_an_identifier_that_resolves_nowhere_is_refused(conn, tmp_path, monkeypatch):
    """`10.1080/00071668108416780`, verbatim from this repository's own fixtures before it
    was corrected: well-formed, authoritative-looking, and indexed by nobody."""
    invented = "10.1080/00071668108416780"
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    artifact["resolutions"][f"doi:{invented}"] = {
        "key": {"type": "doi", "value": invented},
        "aliases": [],
        "readings": {
            source: {"source": source, "found": False, "checked_at": "2026-08-16T20:00:00Z"}
            for source in ("openalex", "crossref")
        },
    }
    artifact_path = tmp_path / "resolution.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    path = _write(tmp_path, _row(key=invented, quote=None))
    with pytest.raises(SeedError, match="resolves in no source"):
        load_seed(conn, path, artifact_path)


def test_a_key_absent_from_the_artifact_is_refused(conn, tmp_path):
    """Adding a row without re-running the resolution pass would load an unchecked key."""
    path = _write(tmp_path, _row(key="10.1038/nature12373", quote=None))
    with pytest.raises(SeedError, match="absent from"):
        load_seed(conn, path, ARTIFACT)


def test_a_tier_no_seed_row_can_justify_is_refused(conn, tmp_path):
    path = _write(tmp_path, _row(tier="corroborated-multi-secondary"))
    with pytest.raises(SeedError, match="corroborated-multi-secondary"):
        load_seed(conn, path, ARTIFACT)


def test_duplicate_slugs_and_duplicate_facts_are_refused(conn, tmp_path):
    with pytest.raises(SeedError, match="duplicate slug"):
        load_seed(conn, _write(tmp_path, _row(), _row()), ARTIFACT)
    with pytest.raises(SeedError, match="a fact's identity is that pair"):
        load_seed(conn, _write(tmp_path, _row(), _row(slug="row-2")), ARTIFACT)


def test_a_field_the_row_model_does_not_declare_is_refused(conn, tmp_path):
    """`extra="forbid"` is the house rule: a renamed or invented field fails at the row
    rather than vanishing with its value."""
    path = _write(tmp_path, _row(confidence="high"))
    with pytest.raises(SeedError):
        load_seed(conn, path, ARTIFACT)


def test_a_malformed_row_leaves_the_store_untouched(conn, tmp_path):
    """The load is transactional across the file: a bad row on line two must not leave
    line one committed, or a re-run would see a half-seeded store as partly `unchanged`."""
    path = _write(tmp_path, _row(), _row(slug="row-2", quote="not in any abstract"))
    with pytest.raises(SeedError):
        load_seed(conn, path, ARTIFACT)
    assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


def test_check_mode_writes_nothing(conn):
    report = load_seed(conn, SEED, ARTIFACT, apply=False)
    assert report.by_action == {"assessed": len(report.rows)}
    assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


# -- re-loading, and the fields the seed does not own ---------------------------------


def test_re_loading_an_unchanged_seed_changes_nothing(conn, report):
    again = load_seed(conn, SEED, ARTIFACT)
    assert again.by_action == {"unchanged": len(again.rows)}
    assert again.seed_digest == report.seed_digest


def test_re_seeding_does_not_resurrect_a_fact_the_jtms_flipped_out(conn, report):
    """The resurrection failure, arriving through the loader. `status` is the store's, and
    design.md §4.2 makes a correction a new fact asserted rather than an old one edited."""
    fact_id = report.rows[0].fact_id
    fact = load_fact(conn, fact_id)
    assert fact is not None
    save_fact(conn, fact.model_copy(update={"status": TmsStatus.OUT}))

    load_seed(conn, SEED, ARTIFACT)
    after = load_fact(conn, fact_id)
    assert after is not None and after.status is TmsStatus.OUT
    assert not after.is_verified


def test_re_seeding_preserves_evidence_quality_written_after_curation(conn, report):
    """M7-T1 writes retraction findings onto facts the seed created. A loader that
    overwrote them would erase a live check with a curation-time reading."""
    fact_id = next(row.fact_id for row in report.rows if row.key == CHOCOLATE)
    fact = load_fact(conn, fact_id)
    assert fact is not None
    save_fact(
        conn,
        fact.model_copy(
            update={
                "evidence_quality": EvidenceQuality(
                    retraction=RetractionStatus.RETRACTED,
                    retraction_checks=fact.evidence_quality.retraction_checks,
                )
            }
        ),
    )

    load_seed(conn, SEED, ARTIFACT)
    after = load_fact(conn, fact_id)
    assert after is not None
    assert after.evidence_quality.retraction is RetractionStatus.RETRACTED


# -- what a seeded fact carries -------------------------------------------------------


def test_a_seeded_fact_records_the_source_and_the_curator_separately(conn, report):
    """Two provenance entries. The backing entry's tier is set by what the quote matched,
    never by a request having succeeded — `Fact` says M5-T2 reads the source tier off this
    list, and "this identifier resolves" is not "this source is primary-verified"."""
    row = next(r for r in report.rows if r.grounding_eligible)
    fact = load_fact(conn, row.fact_id)
    assert fact is not None

    backing, curation = fact.provenance
    assert backing.source in ("openalex", "crossref")
    assert backing.confidence_tier is ConfidenceTier.VERIFIED_PRIMARY
    assert curation.source == "seed"
    assert curation.confidence_tier is ConfidenceTier.INFERRED
    assert curation.source_url is not None and row.slug in curation.source_url


def test_statements_are_attributive_so_grounding_cannot_read_as_endorsement(conn, report):
    """Grounding is exact-key match and never compares statements, so an object-level fact
    would ground any premise sharing its identifier as `verified`. Every seeded statement
    names who is asserting it."""
    for row in report.rows:
        fact = load_fact(conn, row.fact_id)
        assert fact is not None
        assert fact.statement.startswith(
            (
                "Hamblin",
                "Rekdal",
                "Noonan",
                "Gillooly",
                "Piskin",
                "Van der Elst",
                "Bortolus",
                "Di Domenico",
                "Retraction Watch",
                "OpenAlex",
                "Ioannidis",
                "Simmons",
                "Shen",
                "Eriksson",
                "Ried",
                "the Cochrane",
                "West",
            )
        )
        assert " that " in fact.statement


def test_created_at_is_the_recorded_check_time_not_the_load_time(conn, report):
    """Grounding's tie-break orders on `created_at`. A load-time `now()` would make which
    fact a graph names depend on when the store was seeded."""
    for row in report.rows[:5]:
        fact = load_fact(conn, row.fact_id)
        assert fact is not None
        assert fact.created_at <= report.resolution_generated_at
        assert fact.created_at.tzinfo is not None


def test_the_seed_records_the_retraction_watch_reading_and_withholds_the_verdict(conn, report):
    """M7-T1 owns the cut. The seed records what one source said and concludes nothing, so
    the Phase-4 checker produces the other two readings live and can disagree with this."""
    fact_id = next(row.fact_id for row in report.rows if row.key == CHOCOLATE)
    fact = load_fact(conn, fact_id)
    assert fact is not None

    checks = fact.evidence_quality.retraction_checks
    assert set(checks) == {RetractionSource.RETRACTION_WATCH}
    assert checks[RetractionSource.RETRACTION_WATCH].result is RetractionFinding.RETRACTED
    assert fact.evidence_quality.retraction is RetractionStatus.UNKNOWN


def test_no_justifications_are_written_for_seeded_facts(conn, report):
    """`Justification` models Doyle's IN-list only, so a premise justification with no
    antecedents is vacuously satisfied and a status recomputation would restore a demoted
    seed fact to IN forever. Blocker on M8-T1: the type needs an out-list first."""
    assert conn.execute("SELECT COUNT(*) FROM justifications").fetchone()[0] == 0
    for row in report.rows[:5]:
        fact = load_fact(conn, row.fact_id)
        assert fact is not None and fact.justification_ids == []


# -- the seam this tier exists to open ------------------------------------------------


def test_every_grounding_eligible_seeded_fact_actually_grounds_its_key(conn, report):
    """The exit criterion end to end: a premise bound to a seeded key grounds in the store
    that was just seeded, through the same service the render boundary uses."""
    service = Alethiology(conn)
    stamp = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
    eligible = [row for row in report.rows if row.grounding_eligible]
    assert eligible

    for row in eligible:
        premise = Premise(
            text=f"An object-level premise bound to {row.key}.",
            premise_type=PremiseType.EMPIRICAL_CITABLE,
            bound_key=row.key,
        )
        attempt = service.ground(premise, grounded_at=stamp)
        assert attempt.grounded, f"{row.slug} is grounding-eligible but did not ground"


def test_a_capped_row_grounds_nothing(conn, report):
    service = Alethiology(conn)
    for row in report.rows:
        if row.grounding_eligible:
            continue
        facts = service.facts_for(row.key)
        assert not any(fact.id == row.fact_id and fact.is_verified for fact in facts)


def test_a_naive_timestamp_in_the_artifact_is_refused(tmp_path):
    """`checked_at` becomes `Provenance.accessed_at`, which M5-T3's TTL re-validation reads
    to decide what is stale. The artifact is a hand-editable JSON file, so a naive value
    has to fail loudly rather than be interpreted in whatever zone the reader assumes."""
    from verity.alethiology.resolution import ResolutionArtifact

    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    key = f"doi:{HAMBLIN.value}"
    artifact["resolutions"][key]["readings"]["openalex"]["checked_at"] = "2026-08-16T20:00:00"
    with pytest.raises(ValueError, match="naive checked_at"):
        ResolutionArtifact.model_validate(artifact)


def test_the_seed_file_parses_without_a_database(tmp_path):
    """`read_seed` is the half the CLI uses to collect keys before anything is resolved."""
    rows = read_seed(SEED)
    assert len({row.slug for row in rows}) == len(rows)
    assert all(row.note.strip() for row in rows), "every row has to argue for itself"


# -- repairs from the 2B red-team pass ------------------------------------------------


def _resolution_for(key: ExternalKey):
    from verity.alethiology.resolution import ResolutionArtifact

    return ResolutionArtifact.load(ARTIFACT).get(key)


def _probe(quote: str, **overrides):
    """A row asserting the opposite of what Hamblin says, backed by `quote`."""
    from verity.alethiology.seed import SeedFact, assess

    row = SeedFact(
        slug="probe",
        claim_scope="probe",
        key=HAMBLIN.value,
        expected_title="Fake.",
        attributed_to="Hamblin (1981)",
        verb="reports",
        assertion="spinach is an outstanding source of dietary iron",
        tier=ConfidenceTier.VERIFIED_PRIMARY,
        quote=quote,
        note="probe",
        **overrides,
    )
    return assess(row, _resolution_for(HAMBLIN))


@pytest.mark.parametrize("quote", ["a", "the", "iron", "spinach"])
def test_a_word_that_merely_occurs_in_an_abstract_cannot_carry_the_top_tier(quote: str):
    """The gate blocks a fabricated quote; it also has to block a vacuous one.

    Containment alone let any assertion ride into `verified-primary` on a common word —
    "a" occurs 84 times in Hamblin's abstract — which made the tier's headline integrity
    mechanism decorative. Substantiality and specificity are what turn a match into a
    quotation.
    """
    assessment = _probe(quote)
    assert assessment.effective_tier is ConfidenceTier.SINGLE_SECONDARY
    assert assessment.capped
    assert any("word(s)" in note or "occurs" in note for note in assessment.notes)


def test_a_real_clause_quote_still_earns_the_top_tier():
    """The floor must not be paid for by the corpus: this is the shortest quote in it."""
    assessment = _probe("his claims for spinach are spurious")
    assert assessment.effective_tier is ConfidenceTier.VERIFIED_PRIMARY
    assert assessment.notes == []


def test_every_grounding_eligible_row_carries_its_quote_on_the_fact(conn, report):
    """A tier is a claim about how well an attribution is supported. The words it rests on
    belong on the record, not only in the file that produced it."""
    for row in report.rows:
        fact = load_fact(conn, row.fact_id)
        assert fact is not None
        assert fact.supporting_quote, f"{row.slug} carries no quote"
        if row.grounding_eligible:
            assert len(fact.supporting_quote.split()) >= 5


def test_a_non_retraction_notice_is_not_reported_as_clean():
    """Retraction Watch indexes expressions of concern, corrections and reinstatements —
    5,512 of the 71,799 rows. Mapping those to `CLEAN` claims the source looked and found
    nothing, which is the error `RetractionFinding`'s own docstring rules out one step
    over: it would let a flagged work outvote a source that did find a retraction."""
    from datetime import datetime as dt

    from verity.alethiology.resolution import KeyResolution, SourceReading
    from verity.alethiology.seed import _retraction_check

    def check_for(nature: str) -> RetractionFinding:
        resolution = KeyResolution(
            key=HAMBLIN,
            readings={
                "retraction-watch": SourceReading(
                    source="retraction-watch",
                    found=True,
                    checked_at=dt(2026, 8, 16, tzinfo=UTC),
                    detail={"nature": nature, "record_id": "1"},
                )
            },
        )
        return _retraction_check(resolution)[RetractionSource.RETRACTION_WATCH].result

    assert check_for("Retraction") is RetractionFinding.RETRACTED
    for nature in ("Expression of concern", "Correction", "Reinstatement", ""):
        assert check_for(nature) is RetractionFinding.NOT_INDEXED, nature


def test_the_nature_of_a_non_retraction_notice_survives_for_m7(conn, report):
    """`NOT_INDEXED` is the conservative reading of a three-value enum, not the whole
    truth. The raw nature travels in `detail` so M7-T1 can introduce the fourth finding
    the vocabulary actually needs."""
    fact_id = next(row.fact_id for row in report.rows if row.key == CHOCOLATE)
    fact = load_fact(conn, fact_id)
    assert fact is not None
    detail = fact.evidence_quality.retraction_checks[RetractionSource.RETRACTION_WATCH].detail
    assert detail is not None and "nature=Retraction" in detail


def test_the_write_is_as_atomic_as_the_gate(conn, monkeypatch):
    """The gate rules on every row before anything is written; the write has to match, or
    a failure partway leaves a store that is neither the old one nor the new one."""
    import verity.alethiology.seed as seed_module

    calls = {"n": 0}
    real = seed_module.save_facts

    def explode(connection, facts):
        calls["n"] += 1
        real(connection, list(facts)[:1])
        raise RuntimeError("simulated failure mid-write")

    monkeypatch.setattr(seed_module, "save_facts", explode)
    with pytest.raises(RuntimeError):
        load_seed(conn, SEED, ARTIFACT)

    assert calls["n"] == 1, "the loader must write in one batch, not one call per row"


def test_rows_differing_only_in_case_or_spacing_are_one_fact_and_are_refused(conn, tmp_path):
    """Identity has to be judged the way the store judges it, or a duplicate slips through.

    `Fact.id` derives from `statement_hash`, which folds case and collapses whitespace, so
    two rows differing only in capitalization are two strings and one fact. The in-file
    check used to compare raw text: both rows passed, the second silently overwrote the
    first, and the load report said "inserted" twice for one stored row — the counts in the
    report and the README were then wrong in a way nothing surfaced.
    """
    variants = [
        ("case", {"attributed_to": "HAMBLIN (1981)"}),
        ("spacing", {"assertion": "his  claims for spinach   are spurious"}),
    ]
    for label, override in variants:
        path = _write(tmp_path, _row(), _row(slug=f"row-{label}", **override))
        with pytest.raises(SeedError, match="case and whitespace are folded"):
            load_seed(conn, path, ARTIFACT)
        assert conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


def test_slugs_are_unique_case_insensitively(conn, tmp_path):
    """A slug is the anchor a reader follows from a fact's provenance back to the row that
    argued for it. Two that differ only in case are one ambiguous anchor."""
    path = _write(
        tmp_path,
        _row(),
        _row(
            slug="ROW-1",
            assertion="the propaganda was fraudulent",
            quote="Unfortunately, the propaganda was fraudulent",
        ),
    )
    with pytest.raises(SeedError, match="duplicate slug"):
        load_seed(conn, path, ARTIFACT)


def test_the_report_row_count_equals_what_the_store_holds(conn, report):
    """The counts the README quotes come off this report, so they have to be the store's."""
    stored = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    assert stored == len(report.rows)
    assert len({row.fact_id for row in report.rows}) == len(report.rows)
