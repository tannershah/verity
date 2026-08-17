"""Parser contracts, and the malformations that would otherwise pass silently.

Every case here is one where a wrong answer looks like a right one: an invented alias that
points at a real record, a year that raises `IndexError` on a legitimate work, a rendering
change that makes five committed seed quotes unfindable, a URL that truncates at a `#` and
resolves to the wrong paper. None of them fail loudly on their own.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from verity.ids import normalize_text
from verity.keys import ExternalKey, KeyType
from verity.models.common import ConfidenceTier
from verity.retrieval import crossref, openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.errors import MalformedResponseError, UnreachableReadingError
from verity.retrieval.record import (
    ReadingOutcome,
    UnansweredReason,
    WorkRecord,
    absent,
    from_missing,
    unanswered,
)

pytestmark = pytest.mark.usefixtures("poisoned_socket")

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
CHOCOLATE = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
HESPERIDIN = ExternalKey(type=KeyType.PMID, value="31844967")
SEED = Path(__file__).resolve().parents[1] / "seed" / "alethiology.jsonl"


# -- Retraction Watch: the rendering is a contract with the seed corpus -------------


def test_the_record_rendering_is_exactly_what_the_seed_quotes_expect() -> None:
    record = rw.read(CHOCOLATE, rw.SAMPLE_TABLE)
    assert record is not None and record.found
    assert record.record is not None
    # `rw-17524-retraction` quotes this literal string. It exists only because the fields
    # are joined as "{key}: {value}" with single spaces, in the order `_FIELDS` declares.
    assert record.record.startswith("record_id: 17524 nature: Retraction retraction_date: ")
    assert "nature: Retraction" in record.record


def test_every_committed_quote_against_the_retraction_watch_row_is_still_findable() -> None:
    """Iterates the seed file rather than asserting a count, so a new row is covered."""
    text = normalize_text(rw.read(CHOCOLATE, rw.SAMPLE_TABLE).record)
    rows = [json.loads(line) for line in SEED.read_text().splitlines() if line.strip()]
    quoting_rw = [
        row
        for row in rows
        if row.get("attributed_to") == "Retraction Watch" and row.get("quote")
    ]
    assert quoting_rw, "no seed row quotes Retraction Watch; this test has lost its subject"
    for row in quoting_rw:
        if row["key"] != "doi:10.3823/1654":
            continue
        assert normalize_text(row["quote"]) in text, f"{row['slug']} can no longer be quoted"


def test_render_record_skips_empty_fields_without_leaving_double_spaces() -> None:
    rendered = rw.render_record({"record_id": "1", "nature": "", "reasons": "x"})
    assert rendered == "record_id: 1 reasons: x"


def test_an_absent_table_is_never_consulted_rather_than_finding_nothing(tmp_path: Path) -> None:
    assert rw.read(CHOCOLATE, tmp_path / "nope.csv") is None
    looked = rw.read(ExternalKey(type=KeyType.DOI, value="10.9999/absent"), rw.SAMPLE_TABLE)
    assert looked is not None and looked.outcome is ReadingOutcome.ABSENT


def test_a_pmid_keyed_row_matches_the_pubmed_column() -> None:
    record = rw.read(HESPERIDIN, rw.SAMPLE_TABLE)
    assert record is not None and record.found
    assert record.raw_findings["record_id"] == "71483"


# -- OpenAlex ----------------------------------------------------------------------


def test_aliases_are_read_by_name_so_a_mag_id_is_not_mistaken_for_a_pmid() -> None:
    """A MAG id is a bare integer; `ExternalKey.parse` reads it as a real PubMed record."""
    payload = {
        "id": "https://openalex.org/W1",
        "title": "T",
        "ids": {
            "openalex": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1136/bmj.283.6307.1671",
            "mag": "2144219960",
        },
    }
    record = openalex.parse_work(payload, CHOCOLATE, NOW)
    assert [str(alias) for alias in record.aliases] == ["doi:10.1136/bmj.283.6307.1671"]


def test_an_alias_identical_to_the_queried_key_is_not_repeated() -> None:
    payload = {"id": "https://openalex.org/W1", "ids": {"doi": "https://doi.org/10.3823/1654"}}
    assert openalex.parse_work(payload, CHOCOLATE, NOW).aliases == []


def test_a_gapped_inverted_index_reconstructs_what_was_served() -> None:
    payload = {"abstract_inverted_index": {"alpha": [0], "gamma": [5]}}
    assert openalex.reconstruct_abstract(payload) == "alpha gamma"


def test_an_absent_or_empty_index_is_a_work_without_an_abstract() -> None:
    assert openalex.reconstruct_abstract({}) is None
    assert openalex.reconstruct_abstract({"abstract_inverted_index": None}) is None
    assert openalex.reconstruct_abstract({"abstract_inverted_index": {}}) is None
    assert openalex.reconstruct_abstract({"abstract_inverted_index": []}) is None


@pytest.mark.parametrize(
    "index", [{"a": "nope"}, {"a": [1, "two"]}, {"a": None}, "prose", 7]
)
def test_a_malformed_index_raises_rather_than_reconstructing_part_of_one(
    index: object,
) -> None:
    """A shorter abstract still looks like an abstract, and its quotes stop being findable."""
    with pytest.raises(MalformedResponseError):
        openalex.reconstruct_abstract({"abstract_inverted_index": index})


def test_the_retraction_flag_travels_verbatim_and_concludes_nothing() -> None:
    retracted = openalex.parse_work({"is_retracted": True, "id": "W1"}, CHOCOLATE, NOW)
    clean = openalex.parse_work({"is_retracted": False, "id": "W1"}, CHOCOLATE, NOW)
    silent = openalex.parse_work({"id": "W1"}, CHOCOLATE, NOW)

    assert retracted.raw_findings["is_retracted"] == "true"
    assert openalex.retraction_flag(retracted) is True
    assert openalex.retraction_flag(clean) is False
    # Never asked is not the same as asked and clean, one level down from `RetractionStatus`.
    assert openalex.retraction_flag(silent) is None


def test_the_doi_is_percent_encoded_into_the_path() -> None:
    """A DOI carrying `#` would otherwise truncate the URL and resolve to another work."""
    hostile = ExternalKey(type=KeyType.DOI, value="10.1234/abc#def")
    url = openalex.work_request(hostile).url
    assert "%23" in url and "#" not in url.split("works/", 1)[1]


def test_a_real_bracketed_doi_survives_encoding() -> None:
    bracketed = ExternalKey(
        type=KeyType.DOI, value="10.1579/0044-7447(2008)37[114:ecitbs]2.0.co;2"
    )
    assert "%5B114%3Aecitbs%5D" in openalex.work_request(bracketed).url


def test_openalex_indexes_works_so_an_nct_produces_no_request() -> None:
    assert openalex.work_request(ExternalKey(type=KeyType.NCT, value="NCT04280705")) is None


def test_a_singleton_declares_the_credit_cost_the_meter_confirmed() -> None:
    """Both costs are live-verified; a list costs ten times a singleton, and T1b spends it."""
    assert openalex.work_request(CHOCOLATE).credit_cost_hint == openalex.WORK_COST == 1
    assert openalex.LIST_COST == 10


# -- Crossref ----------------------------------------------------------------------


def test_an_empty_date_part_yields_no_year_rather_than_an_index_error() -> None:
    """`{"date-parts": [[]]}` occurs, and the previous expression raised on it."""
    payload = {"message": {"title": ["T"], "issued": {"date-parts": [[]]}}}
    assert crossref.parse_work(payload, CHOCOLATE, NOW).year is None


@pytest.mark.parametrize(
    "issued",
    [{"date-parts": []}, {"date-parts": None}, {}, {"date-parts": [["1981"]]}, None],
)
def test_every_malformed_issued_shape_yields_no_year(issued: object) -> None:
    payload = {"message": {"title": ["T"], "issued": issued}}
    assert crossref.parse_work(payload, CHOCOLATE, NOW).year is None


def test_a_well_formed_issued_still_yields_its_year() -> None:
    payload = {"message": {"title": ["T"], "issued": {"date-parts": [[1981, 12, 19]]}}}
    assert crossref.parse_work(payload, CHOCOLATE, NOW).year == 1981


def test_an_empty_title_list_yields_no_title() -> None:
    assert crossref.parse_work({"message": {"title": []}}, CHOCOLATE, NOW).title is None


def test_non_dict_update_entries_are_skipped_rather_than_assumed() -> None:
    payload = {"message": {"update-to": ["nonsense", {"type": "retraction"}, None]}}
    record = crossref.parse_work(payload, CHOCOLATE, NOW)
    assert crossref.update_types(record) == ("retraction",)


def test_jats_tags_become_spaces_so_two_words_never_fuse() -> None:
    payload = {"message": {"abstract": "<jats:p>first</jats:p><jats:p>second</jats:p>"}}
    abstract = crossref.parse_work(payload, CHOCOLATE, NOW).abstract
    assert "firstsecond" not in abstract
    assert normalize_text(abstract) == "first second"


def test_an_update_is_not_a_retraction() -> None:
    """The seed's cocoa Cochrane row carries `new_version`; M7-T1 owns the cut, not this."""
    payload = {"message": {"update-to": [{"type": "new_version"}]}}
    record = crossref.parse_work(payload, CHOCOLATE, NOW)
    assert crossref.update_types(record) == ("new_version",)
    assert set(crossref.update_types(record)) <= crossref.NON_RETRACTION_UPDATE_TYPES
    # Nothing in the record concludes a status. `RetractionStatus` is not reachable here.
    assert "retraction" not in record.raw_findings


def test_updated_by_sources_are_recorded_for_the_policy_that_counts_them() -> None:
    payload = {
        "message": {"updated-by": [{"source": "retraction-watch"}, {"source": "publisher"}]}
    }
    record = crossref.parse_work(payload, CHOCOLATE, NOW)
    assert crossref.updated_by_sources(record) == ("publisher", "retraction-watch")


def test_crossref_speaks_only_doi_so_a_pmid_produces_no_request() -> None:
    assert crossref.work_request(HESPERIDIN) is None


@pytest.mark.parametrize("payload", [{"status": "ok"}, {"message": []}, None, "text"])
def test_a_200_that_does_not_parse_raises_rather_than_reading_as_absent(
    payload: object,
) -> None:
    """A schema change read as `found=False` demotes every row keyed to that source."""
    with pytest.raises(MalformedResponseError):
        crossref.parse_work(payload, CHOCOLATE, NOW)


@pytest.mark.parametrize("payload", [None, [], "text", 3])
def test_openalex_refuses_a_payload_that_is_not_a_work(payload: object) -> None:
    with pytest.raises(MalformedResponseError):
        openalex.parse_work(payload, CHOCOLATE, NOW)


def test_only_a_404_produces_a_not_found_reading() -> None:
    """The one path to `found=False` from a live source, kept narrow on purpose."""
    assert absent("crossref", NOW, CHOCOLATE).found is False


# -- the record ---------------------------------------------------------------------


def test_retrieval_never_assigns_a_grounding_eligible_tier() -> None:
    """A fetch shows an identifier resolves, never that an attribution is supported."""
    record = openalex.parse_work({"id": "W1", "title": "T"}, CHOCOLATE, NOW)
    assert record.provenance().confidence_tier is ConfidenceTier.INFERRED


def test_a_record_refuses_a_naive_fetch_time() -> None:
    with pytest.raises(ValueError, match="naive fetched_at"):
        WorkRecord(
            source="openalex",
            outcome=ReadingOutcome.ABSENT,
            fetched_at=datetime(2026, 8, 16, 12, 0),
        )


# -- a reading has three outcomes ---------------------------------------------------


def test_a_source_that_cannot_be_asked_is_unanswered_not_absent() -> None:
    """OpenAlex indexes works; Crossref indexes DOIs. Neither can speak to an NCT."""
    nct = ExternalKey(type=KeyType.NCT, value="NCT04280705")
    for module in (openalex, crossref):
        assert module.work_request(nct) is None
    table = rw.read(nct, rw.SAMPLE_TABLE)
    assert table is not None
    assert table.outcome is ReadingOutcome.UNANSWERED
    assert not table.answered and not table.found
    assert table.not_applicable and not table.unreachable
    assert "indexes papers" in table.unanswered_because


def test_a_credentialed_miss_is_absence_and_a_degraded_one_is_not() -> None:
    credentialed = from_missing("openalex", CHOCOLATE, NOW, degraded=False)
    degraded = from_missing("openalex", CHOCOLATE, NOW, degraded=True)

    assert credentialed.outcome is ReadingOutcome.ABSENT and credentialed.answered
    # The cache already refuses to store this; the reading must not assert it either.
    assert degraded.outcome is ReadingOutcome.UNANSWERED and not degraded.answered
    # Transient, and about this run rather than about the identifier.
    assert degraded.unreachable and not degraded.not_applicable
    assert "without the credential" in degraded.unanswered_because


def test_an_unanswered_reading_must_say_why_and_an_answered_one_may_not() -> None:
    with pytest.raises(ValueError, match="does not say why"):
        WorkRecord(source="openalex", outcome=ReadingOutcome.UNANSWERED, fetched_at=NOW)
    with pytest.raises(ValueError, match="does not say why"):
        WorkRecord(
            source="openalex",
            outcome=ReadingOutcome.UNANSWERED,
            fetched_at=NOW,
            unanswered_because="a reason with no type",
        )
    with pytest.raises(ValueError, match="carries an unanswered reason"):
        WorkRecord(
            source="openalex",
            outcome=ReadingOutcome.ABSENT,
            fetched_at=NOW,
            unanswered_because="should not be here",
        )


def test_a_structurally_inapplicable_source_still_projects_as_not_found() -> None:
    """Crossref genuinely holds no record under a PMID, and the artifact already says so."""
    record = unanswered(
        "crossref",
        NOW,
        HESPERIDIN,
        reason=UnansweredReason.NOT_APPLICABLE,
        because="crossref indexes DOIs, and this is a pmid",
    )
    assert record.as_source_reading().found is False


def test_an_unreachable_reading_refuses_to_project_into_the_artifact() -> None:
    """`found=False` there means "exists nowhere", which is what the seed gate deletes on."""
    record = unanswered(
        "openalex",
        NOW,
        CHOCOLATE,
        reason=UnansweredReason.UNREACHABLE,
        because="the request went out without a credential",
    )
    with pytest.raises(UnreachableReadingError, match="resolves"):
        record.as_source_reading()
    assert absent("openalex", NOW, CHOCOLATE).as_source_reading().found is False


def test_source_url_is_public_and_never_the_api_url() -> None:
    openalex_record = openalex.parse_work(
        {"id": "https://openalex.org/W209123019"}, CHOCOLATE, NOW
    )
    crossref_record = crossref.parse_work({"message": {"title": ["T"]}}, CHOCOLATE, NOW)
    assert openalex_record.source_url == "https://openalex.org/W209123019"
    assert crossref_record.source_url == "https://doi.org/10.3823/1654"
    assert "api." not in (openalex_record.source_url + crossref_record.source_url)


def test_the_source_reading_projection_carries_the_curated_record_field() -> None:
    """Five committed seed rows quote this field; dropping it aborts the seed load."""
    reading = rw.read(CHOCOLATE, rw.SAMPLE_TABLE).as_source_reading()
    assert reading.record is not None
    assert "record" in reading.quotable_text
    assert reading.detail["nature"] == "Retraction"


def test_absent_is_a_reading_with_a_time() -> None:
    record = absent("openalex", NOW, CHOCOLATE)
    assert record.found is False and record.fetched_at == NOW
    assert record.as_source_reading().found is False
