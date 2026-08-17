"""M5-T1's exit criterion: exact-key hit/miss behaves, and fuzzy lookup does not exist.

Both halves are load-bearing in opposite directions, exactly as `test_key_corpus.py` says
of canonicalization. A key that should match and does not deflates the pre-registered
grounding rate silently; a key that should not match and does inflates it. So the two
tables below are paired: every canonicalization-equivalent spelling of a seeded key must
ground, and every near-miss must not.

"Fuzzy lookup does not exist" is asserted three ways rather than trusted: the lookup
signatures take `ExternalKey` and never `str`, so a text query cannot be written; the
package imports no similarity machinery; and the near-miss table is the behavioural proof.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from pathlib import Path
from typing import get_type_hints

import pytest

from verity.alethiology import grounding as grounding_module
from verity.alethiology.grounding import (
    CandidateReason,
    GroundingReason,
    attempt_grounding,
    select,
)
from verity.alethiology.resolution import ResolutionArtifact
from verity.alethiology.service import Alethiology
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Premise
from verity.models.common import (
    ConfidenceTier,
    EvidenceState,
    PremiseType,
    Provenance,
    TerminationReason,
    TmsStatus,
)
from verity.models.fact import Fact, FactLookup
from verity.models.render import to_render_payload
from verity.store.db import connect
from verity.store.facts import save_fact

REPO = Path(__file__).resolve().parents[1]
SEEDED = ExternalKey(type=KeyType.DOI, value="10.1136/bmj.283.6307.1671")
ACCESSED = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)

#: Spellings of the same identifier. Canonicalization is a total syntactic transform
#: (design.md §4.1), so every one of these is the same key and must ground.
EQUIVALENT_SPELLINGS = [
    "10.1136/bmj.283.6307.1671",
    "https://doi.org/10.1136/bmj.283.6307.1671",
    "doi:10.1136/bmj.283.6307.1671",
    "10.1136/BMJ.283.6307.1671",
    "(10.1136/bmj.283.6307.1671).",
    "  10.1136/bmj.283.6307.1671  ",
    "https://doi.org/10.1136/bmj.283.6307.1671?utm_source=x",
]

#: Different identifiers that a similarity layer would be tempted to merge. Each must miss.
NEAR_MISSES = [
    (KeyType.DOI, "10.1136/bmj.283.6307.1672"),
    (KeyType.DOI, "10.1136/bmj.283.6307.167"),
    (KeyType.DOI, "10.1136/bmj.283.6307.16710"),
    (KeyType.DOI, "10.1137/bmj.283.6307.1671"),
    (KeyType.PMID, "6797606"),
]

_SIMILARITY_LIBRARIES = frozenset(
    {
        "difflib",
        "rapidfuzz",
        "fuzzywuzzy",
        "Levenshtein",
        "jellyfish",
        "numpy",
        "torch",
        "sklearn",
        "transformers",
        "sentence_transformers",
        "faiss",
    }
)


def _provenance() -> Provenance:
    return Provenance(
        source="openalex", accessed_at=ACCESSED, confidence_tier=ConfidenceTier.VERIFIED_PRIMARY
    )


_STATEMENT = "Hamblin (1981) reports that the figure was overstated."


def _fact(statement: str = _STATEMENT, **over) -> Fact:
    defaults = {
        "statement": statement,
        "key": SEEDED,
        "tier": ConfidenceTier.VERIFIED_PRIMARY,
        "provenance": [_provenance()],
        "created_at": ACCESSED,
    }
    return Fact(**{**defaults, **over})


def _premise(key: ExternalKey | None = SEEDED, **over) -> Premise:
    return Premise(
        text=over.pop("text", "The published iron figure for spinach was overstated tenfold."),
        premise_type=over.pop("premise_type", PremiseType.EMPIRICAL_CITABLE),
        bound_key=key,
        **over,
    )


@pytest.fixture
def store(tmp_path):
    conn = connect(tmp_path / "alethiology.db")
    save_fact(conn, _fact())
    yield conn
    conn.close()


# -- exact-key hit and miss, both directions -----------------------------------------


@pytest.mark.parametrize("spelling", EQUIVALENT_SPELLINGS)
def test_every_canonical_spelling_of_a_seeded_key_grounds(store, spelling: str):
    attempt = Alethiology(store).ground(_premise(ExternalKey.parse(spelling)))
    assert attempt.grounded, f"{spelling!r} is the same identifier and must ground"
    assert attempt.grounding is not None
    assert attempt.grounding.matched_key.matches(SEEDED)


@pytest.mark.parametrize(("key_type", "value"), NEAR_MISSES)
def test_a_near_miss_key_grounds_nothing(store, key_type: KeyType, value: str):
    attempt = Alethiology(store).ground(_premise(ExternalKey(type=key_type, value=value)))
    assert not attempt.grounded
    assert attempt.reason is GroundingReason.NO_FACT_FOR_KEY


def test_a_pmid_and_a_doi_are_never_the_same_key(store):
    """Two key types holding the same digits are two keys. The grounding predicate is
    `(type, value)` equality, and collapsing the type would be fuzzy matching by another
    name."""
    digits = ExternalKey(type=KeyType.PMID, value="6797607")
    assert not Alethiology(store).ground(_premise(digits)).grounded


# -- fuzzy lookup does not exist ------------------------------------------------------


def test_no_lookup_accepts_free_text():
    """The type signature is the enforcement: a caller cannot express a text query."""
    for name in ("facts_for", "aliases_of", "aliases_holding_facts"):
        # `from __future__ import annotations` makes annotations strings, so they are
        # resolved rather than compared as text — a `str` parameter must fail this.
        hints = get_type_hints(getattr(Alethiology, name))
        assert hints["key"] is ExternalKey, (
            f"{name} must take an ExternalKey, not {hints['key']}"
        )


def test_the_alethiology_package_imports_no_similarity_machinery():
    """A similarity assist is M5-T3, flagged non-grounding, and belongs in its own module.

    Scanned rather than assumed: an embedding import added to this package would make the
    ban a comment.

    Honest about its reach: this catches imported machinery, not a similarity function
    written by hand, and the review that would catch that is a human one. It walks the
    package recursively so a submodule cannot sit outside it.
    """
    offenders: dict[str, set[str]] = {}
    for path in sorted((REPO / "src" / "verity" / "alethiology").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        if hit := imported & _SIMILARITY_LIBRARIES:
            offenders[path.name] = hit
    assert not offenders, f"similarity machinery reached the grounding path: {offenders}"


def test_selection_reads_no_statement():
    """An earlier draft preferred a candidate whose statement matched the premise. Under
    attributive statements that comparison is false by construction, and any statement
    comparison in the grounding path is a step toward matching on meaning."""
    source = inspect.getsource(grounding_module)
    assert "statement_hash" not in source
    assert "normalize_text" not in source


# -- why a premise did not ground ----------------------------------------------------


def test_a_premise_with_no_bound_key_says_so(store):
    attempt = Alethiology(store).ground(_premise(None))
    assert attempt.reason is GroundingReason.NO_BOUND_KEY
    assert attempt.candidates == []


def test_an_out_fact_and_an_ineligible_fact_report_separately(tmp_path):
    """A key holding one retracted fact and one below-tier fact has no single reason.

    Collapsing them would tell an operator to re-check tiers when the actual problem was a
    retraction, or the reverse.
    """
    conn = connect(tmp_path / "mixed.db")
    save_fact(conn, _fact("Hamblin (1981) reports A.", status=TmsStatus.OUT))
    save_fact(conn, _fact("Hamblin (1981) reports B.", tier=ConfidenceTier.SINGLE_SECONDARY))

    attempt = Alethiology(conn).ground(_premise())
    assert attempt.reason is GroundingReason.NO_ELIGIBLE_CANDIDATE
    assert {v.reason for v in attempt.candidates} == {
        CandidateReason.FACT_OUT,
        CandidateReason.INELIGIBLE_TIER,
    }
    conn.close()


def test_a_fact_under_an_alias_of_the_key_is_reported_not_grounded(tmp_path):
    """One work, two identifiers: binding the PMID when the seed holds the DOI misses.

    evaluation.md §2 defines grounding as exact key only and is silent on synonyms, so
    widening the predicate here would move a pre-registered number by fiat. Reporting the
    near-miss neither inflates the rate nor hides the deflation.
    """
    conn = connect(tmp_path / "alias.db")
    save_fact(conn, _fact())
    pmid = ExternalKey(type=KeyType.PMID, value="6797607")
    service = Alethiology(conn, aliases={str(pmid): [SEEDED], str(SEEDED): [pmid]})

    attempt = service.ground(_premise(pmid))
    assert attempt.reason is GroundingReason.ALIAS_ONLY
    assert attempt.alias_keys == [SEEDED]
    assert not attempt.grounded
    conn.close()


# -- the by-design partition build-plan §4 needs --------------------------------------


@pytest.mark.parametrize(
    ("premise_type", "termination", "applicable", "basis"),
    [
        (PremiseType.DEFINITIONAL, None, False, "premise-type"),
        (PremiseType.BACKGROUND, None, False, "premise-type"),
        (PremiseType.EMPIRICAL_CITABLE, None, True, "premise-type"),
        (None, None, True, "default"),
        # The recorded decision wins over the classification: the decomposer terminated
        # this branch as unverifiable, whatever the type says.
        (
            PremiseType.EMPIRICAL_CITABLE,
            TerminationReason.UNVERIFIABLE_BY_DESIGN,
            False,
            "termination-reason",
        ),
        (
            PremiseType.DEFINITIONAL,
            TerminationReason.CITATION_SHAPED,
            True,
            "termination-reason",
        ),
        # The descent-imposed reasons carry no information about groundability: a branch
        # that hit the depth budget, met a cap, or refused has said nothing about whether an
        # identifier could verify it. Reading `not UNVERIFIABLE_BY_DESIGN` off one of these
        # would count a definitional premise as citable and inflate the supplementary
        # denominator build-plan.md §4 reports beside the headline rate.
        (
            PremiseType.DEFINITIONAL,
            TerminationReason.BUDGET_EXIT,
            False,
            "premise-type",
        ),
        (
            PremiseType.DEFINITIONAL,
            TerminationReason.CAP_EXIT,
            False,
            "premise-type",
        ),
        (
            PremiseType.EMPIRICAL_CITABLE,
            TerminationReason.DECOMPOSITION_REFUSED,
            True,
            "premise-type",
        ),
        (None, TerminationReason.BUDGET_EXIT, True, "default"),
    ],
)
def test_applicability_partitions_the_supplementary_denominator(
    store, premise_type, termination, applicable, basis
):
    attempt = Alethiology(store).ground(
        _premise(None, premise_type=premise_type, termination_reason=termination)
    )
    assert attempt.applicable is applicable
    assert attempt.applicability_basis == basis


def test_a_by_design_premise_that_does_ground_still_grounds(store):
    """Applicability is a property of the premise, not a veto on the outcome. A
    definitional premise that happens to carry a key with a fact under it is grounded, and
    the supplementary rate excludes it from its denominator — those are separate facts
    about the row and the model keeps them separate."""
    attempt = Alethiology(store).ground(_premise(premise_type=PremiseType.DEFINITIONAL))
    assert attempt.grounded
    assert not attempt.applicable


# -- determinism ----------------------------------------------------------------------


def test_selection_prefers_tier_then_creation_then_id():
    stronger = _fact("Hamblin (1981) reports A.", tier=ConfidenceTier.VERIFIED_PRIMARY)
    weaker = _fact(
        "Hamblin (1981) reports B.",
        tier=ConfidenceTier.CORROBORATED_MULTI_SECONDARY,
        created_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    assert select([weaker, stronger]) is stronger
    assert select([stronger, weaker]) is stronger


def test_selection_cannot_change_whether_a_premise_grounded(store):
    """The tie-break decides which fact is named, never whether grounding happened."""
    save_fact(store, _fact("Hamblin (1981) reports B.", tier=ConfidenceTier.SINGLE_SECONDARY))
    save_fact(store, _fact("Hamblin (1981) reports C."))
    service = Alethiology(store)
    attempt = service.ground(_premise())
    assert attempt.grounded
    assert len(attempt.candidates) == 3
    assert sum(1 for v in attempt.candidates if v.reason is CandidateReason.ELIGIBLE) == 2


def test_grounded_at_is_injectable_so_a_replay_reproduces_its_graph(store):
    """`Grounding.grounded_at` defaults to now(), and a fresh timestamp in a stored graph
    payload is what M1-T2's replay check would diff against."""
    stamp = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    first = Alethiology(store).ground(_premise(), grounded_at=stamp)
    second = Alethiology(store).ground(_premise(), grounded_at=stamp)
    assert first.grounding == second.grounding
    assert first.grounding is not None and first.grounding.grounded_at == stamp


# -- the seam to the render boundary --------------------------------------------------


def test_the_service_is_a_fact_lookup_the_renderer_can_consume(store):
    service = Alethiology(store)
    assert isinstance(service, FactLookup)

    claim = Claim(text="A misplaced decimal made spinach famous as an iron-rich food.")
    premise = _premise(evidence_state=EvidenceState.VERIFIED)
    attempt = service.ground(premise)
    assert attempt.grounding is not None

    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
        groundings=[attempt.grounding],
    )
    row = to_render_payload(graph, service).premises[0]
    assert row.grounded
    assert row.grounding_fact_statement == _fact().statement
    assert row.text != row.grounding_fact_statement, (
        "the premise is object-level and the fact is attributive; showing both is what "
        "keeps `verified` from reading as `this premise's content was checked`"
    )


def test_the_alias_index_from_a_recorded_artifact_is_symmetric():
    """OpenAlex reports a work's other ids only when asked by one of them, so the raw
    readings are one-directional. A miss has to be reportable from either side."""
    artifact = ResolutionArtifact.load(REPO / "seed" / "key_resolution.json")
    index = artifact.alias_index()
    for key, aliases in index.items():
        for alias in aliases:
            assert key in {str(k) for k in index[str(alias)]}


# -- repairs from the 2B red-team pass ------------------------------------------------


def test_a_generator_of_candidates_grounds_exactly_as_a_list_does():
    """`attempt_grounding` reads its candidates twice — once for verdicts, once to select.

    It used to consume the iterable on the first pass and select from an exhausted one, so
    a generator produced `no-eligible-candidate` beside a verdict list saying `eligible`:
    self-contradictory, silent, and in the direction that deflates the pre-registered rate.
    """
    fact = _fact()
    premise = _premise()
    from_list = attempt_grounding(premise, [fact])
    from_generator = attempt_grounding(premise, (f for f in [fact]))

    assert from_generator.grounded
    assert from_generator.reason is from_list.reason
    assert from_generator.candidates == from_list.candidates


def test_an_attempt_whose_summary_contradicts_its_verdicts_is_refused():
    """The invariant that would have caught the bug above, stated on the type."""
    from verity.alethiology.grounding import CandidateVerdict, GroundingAttempt

    eligible = CandidateVerdict(
        fact_id="fact_x",
        tier=ConfidenceTier.VERIFIED_PRIMARY,
        status=TmsStatus.IN,
        reason=CandidateReason.ELIGIBLE,
    )
    with pytest.raises(ValueError, match="no eligible candidate while"):
        GroundingAttempt(
            premise_id="prem_x",
            reason=GroundingReason.NO_ELIGIBLE_CANDIDATE,
            candidates=[eligible],
        )
    with pytest.raises(ValueError, match="no candidate verdict says a fact qualified"):
        GroundingAttempt(premise_id="prem_x", reason=GroundingReason.GROUNDED)


def test_several_eligible_facts_under_one_key_are_reported_as_a_tie_break(store):
    """Grounding compares keys only, so which of several eligible facts is named says
    nothing about the premise's content. The count is exposed rather than left for a
    consumer to derive, because the display consequence — `verified` beside a statement
    that happens to be the one the tie-break picked — is a thing to see, not to discover."""
    save_fact(store, _fact("Hamblin (1981) reports B."))
    save_fact(store, _fact("Hamblin (1981) reports C."))
    attempt = Alethiology(store).ground(_premise())

    assert attempt.grounded
    assert len(attempt.eligible_candidates) == 3


def test_the_service_wires_its_alias_index_by_default(tmp_path):
    """`ALIAS_ONLY` exists to make a deflation visible, and a service constructed without
    an alias map can never emit it. `open` is the path that supplies one, so the reason
    code fires on a real run rather than only under a test that passes the map by hand."""
    artifact = REPO / "seed" / "key_resolution.json"
    conn = connect(tmp_path / "aliased.db")
    save_fact(
        conn,
        _fact(
            key=ExternalKey.parse("10.1002/14651858.cd008893.pub3"),
            statement="the Cochrane review of cocoa and blood pressure (2017) reports x.",
        ),
    )

    service = Alethiology.open(conn, resolution_path=artifact)
    attempt = service.ground(_premise(ExternalKey.parse("pmid:28439881")))

    assert attempt.reason is GroundingReason.ALIAS_ONLY
    assert [str(k) for k in attempt.alias_keys] == ["doi:10.1002/14651858.cd008893.pub3"]
    conn.close()


def test_a_pubmed_url_parses_as_the_pmid_it_names():
    """`canonicalize` accepted these and `ExternalKey.parse` rejected them, because parse
    re-derived a partial copy of the normalization rules. Everything that binds a key from
    untrusted text goes through `parse`, and an LLM asked for a PubMed citation emits the
    URL form — so the divergence dropped exactly the candidate keys the demo depends on."""
    expected = ExternalKey(type=KeyType.PMID, value="6797607")
    for spelling in (
        "https://pubmed.ncbi.nlm.nih.gov/6797607/",
        "http://pubmed.ncbi.nlm.nih.gov/6797607/?utm_source=x",
        "https://www.ncbi.nlm.nih.gov/pubmed/6797607",
        "PMID: 6797607",
        "pmid:6797607",
        "6797607",
    ):
        assert ExternalKey.parse(spelling).matches(expected), spelling


def test_a_retraction_is_flagged_through_the_bound_key_without_a_grounding(tmp_path):
    """A retraction warning is not contingent on grounding.

    The seeded chocolate trail is `single-secondary` — the registries serve a different
    work under that DOI — so it grounds nothing, and a flag keyed to the grounding row
    would render the demo's retracted paper as clean. Flagging through the premise's bound
    key is both more correct and what makes the beat visible: not grounded, and retracted.
    """
    from conftest import three_source_agreement
    from verity.models.common import RetractionFinding, RetractionStatus
    from verity.models.evidence import EvidenceQuality

    retracted = _fact(
        key=ExternalKey.parse("10.3823/1654"),
        statement="Retraction Watch records that the paper was retracted.",
        tier=ConfidenceTier.SINGLE_SECONDARY,
        evidence_quality=EvidenceQuality(
            retraction=RetractionStatus.RETRACTED,
            retraction_checks=three_source_agreement(RetractionFinding.RETRACTED),
        ),
    )
    conn = connect(tmp_path / "flagged.db")
    save_fact(conn, retracted)

    claim = Claim(text="Chocolate accelerates weight loss.")
    premise = _premise(retracted.key, text="A 2015 trial reported accelerated weight loss.")
    graph = ClaimGraph(
        root_claim=claim,
        premises={premise.id: premise},
        steps=[EntailmentStep(conclusion_id=claim.id, premise_ids=[premise.id])],
    )

    row = to_render_payload(graph, Alethiology(conn)).premises[0]
    assert not row.grounded, "a single-secondary fact grounds nothing"
    assert row.retraction_flags == ["doi:10.3823/1654: retracted"]
    conn.close()
