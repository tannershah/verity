"""The binder: what may promote a candidate key, and what may not.

The failure this guards is quiet by construction. A language model naming a DOI is an
assertion, not a citation — `10.1080/00071668108416780` sat in this repository's own
fixtures as a `verified-primary` target and resolves nowhere — so a binder that promotes
without checking manufactures grounding keys, and the grounding rate rises because the
decomposer got more confident.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Premise
from verity.models.common import EvidenceState, PremiseType
from verity.retrieval import crossref, openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.binder import (
    PARTIAL_BASIS,
    RESOLVING_SOURCES,
    BindingOutcome,
    bind_candidate_keys,
    check_key,
)
from verity.retrieval.errors import TransportError
from verity.retrieval.http import (
    CacheMode,
    CrossrefCredential,
    HttpCache,
    HttpClient,
    ManualClock,
    NoCredential,
    OpenAlexCredential,
    RawResponse,
)

pytestmark = pytest.mark.usefixtures("poisoned_socket")

REAL = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
INVENTED = ExternalKey(type=KeyType.DOI, value="10.1080/00071668108416780")
HEADERS = {
    "x-api-pool": "polite-single",
    "x-rate-limit-limit": "10",
    "x-rate-limit-interval": "1s",
}


class Registry:
    """Answers 200 for the keys it knows and 404 for the rest."""

    def __init__(self, *known: ExternalKey) -> None:
        self._known = {key.value for key in known}
        self.calls: list[str] = []

    def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
        self.calls.append(url)
        if not any(value in url for value in self._known):
            return RawResponse(status=404, body="Resource not found.", headers=HEADERS)
        # Each registry has its own envelope, and a 200 in the wrong shape now raises
        # rather than reading as an absent work — so the fake has to answer in kind.
        work = {"id": "https://openalex.org/W1", "title": "A real work"}
        body = {"message": work} if "crossref" in url else work
        return RawResponse(status=200, body=json.dumps(body), headers=HEADERS)


class Unreachable:
    """Never answers. Every source is left unable to say anything."""

    def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
        raise TransportError(f"{url} did not complete: refused")


def client(tmp_path, transport) -> HttpClient:  # noqa: ANN001
    return HttpClient(
        credentials=[NoCredential("openalex"), NoCredential("crossref")],
        mode=CacheMode.LIVE,
        cache=HttpCache([tmp_path], [tmp_path]),
        transport=transport,
        clock=ManualClock(),
    )


def graph_with(*premises: Premise) -> ClaimGraph:
    claim = Claim(text="A misplaced decimal made spinach famous as an iron-rich food.")
    step = EntailmentStep(
        conclusion_id=claim.id, premise_ids=[p.id for p in premises], depth=0
    )
    built, _ = ClaimGraph.build(
        root_claim=claim, premises={p.id: p for p in premises}, steps=[step]
    )
    return built


def premise(text: str, **kwargs) -> Premise:
    return Premise(text=text, premise_type=PremiseType.EMPIRICAL_CITABLE, **kwargs)


# -- promotion ---------------------------------------------------------------------


def test_a_candidate_key_that_resolves_is_bound(tmp_path) -> None:  # noqa: ANN001
    subject = premise("The paper reports a weight-loss effect.", candidate_key=REAL)
    bound, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry(REAL)))

    decision = report.decisions[0]
    assert decision.outcome is BindingOutcome.BOUND
    assert decision.resolved_by == ["openalex", "crossref"]
    assert bound.premises[subject.id].bound_key == REAL


def test_a_candidate_key_that_resolves_nowhere_is_not_bound(tmp_path) -> None:  # noqa: ANN001
    subject = premise("A study the model invented supports this.", candidate_key=INVENTED)
    bound, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry(REAL)))

    assert report.decisions[0].outcome is BindingOutcome.DID_NOT_RESOLVE
    assert bound.premises[subject.id].bound_key is None


def test_an_unanswerable_check_is_not_a_negative(tmp_path) -> None:  # noqa: ANN001
    """A transport failure is the absence of evidence, not evidence of absence."""
    subject = premise("A premise nobody could check.", candidate_key=REAL)
    bound, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Unreachable()))

    decision = report.decisions[0]
    assert decision.outcome is BindingOutcome.COULD_NOT_BE_CHECKED
    assert set(decision.unchecked) == {"openalex", "crossref"}
    assert bound.premises[subject.id].bound_key is None


def test_a_premise_with_no_candidate_key_is_recorded(tmp_path) -> None:  # noqa: ANN001
    subject = premise("A premise the decomposer named no work for.")
    _, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry(REAL)))
    assert report.decisions[0].outcome is BindingOutcome.NO_CANDIDATE


def test_an_existing_binding_is_never_overwritten(tmp_path) -> None:  # noqa: ANN001
    subject = premise("Already attributed.", bound_key=REAL, candidate_key=INVENTED)
    caller = client(tmp_path, Registry(INVENTED))
    bound, report = bind_candidate_keys(graph_with(subject), caller)

    assert report.decisions[0].outcome is BindingOutcome.ALREADY_BOUND
    assert bound.premises[subject.id].bound_key == REAL


# -- what may not resolve a key ----------------------------------------------------


def test_only_registries_resolve_a_key(tmp_path) -> None:  # noqa: ANN001
    """Retraction Watch holds this DOI. A curated index must not confirm a work exists."""
    assert rw.read(REAL, rw.SAMPLE_TABLE).found, "the sample no longer carries the DOI"
    assert rw not in RESOLVING_SOURCES
    assert [module.SOURCE for module in RESOLVING_SOURCES] == ["openalex", "crossref"]

    subject = premise("The chocolate paper says so.", candidate_key=REAL)
    _, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry()))
    assert report.decisions[0].outcome is BindingOutcome.DID_NOT_RESOLVE


def test_an_alias_is_never_a_binding_path(tmp_path) -> None:  # noqa: ANN001
    """A registry reporting a second identifier does not make that identifier the key."""
    pmid = ExternalKey(type=KeyType.PMID, value="25272616")

    class WithAlias:
        def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
            if pmid.value in url:
                return RawResponse(status=404, body="", headers=HEADERS)
            body = json.dumps({"id": "W1", "ids": {"pmid": f"pmid:{pmid.value}"}})
            return RawResponse(status=200, body=body, headers=HEADERS)  # pragma: no cover

    check = check_key(client(tmp_path, WithAlias()), pmid)
    assert check.resolved_by == [] and check.answered == ["openalex"]


def test_a_registry_silent_on_a_key_type_does_not_block_a_verdict(tmp_path) -> None:  # noqa: ANN001
    """Crossref has no PMIDs. OpenAlex does, so its answer settles the question alone."""
    pmid = ExternalKey(type=KeyType.PMID, value="25272616")
    assert crossref.work_request(pmid) is None
    assert openalex.work_request(pmid) is not None

    check = check_key(client(tmp_path, Registry(pmid)), pmid)
    assert check.resolved_by == ["openalex"]
    # Structurally unable to answer, so it is reported but does not make the check partial.
    assert set(check.not_applicable) == {"crossref"} and check.complete


def test_a_key_no_registry_can_speak_to_is_unchecked_not_refuted(tmp_path) -> None:  # noqa: ANN001
    """An NCT reaches neither registry, and silence from both is not a unanimous no."""
    nct = ExternalKey(type=KeyType.NCT, value="NCT04280705")
    registry = Registry()
    subject = premise("A registered trial enrolled 500 people.", candidate_key=nct)
    _, report = bind_candidate_keys(graph_with(subject), client(tmp_path, registry))

    assert registry.calls == [], "a request went out for a key no registry indexes"
    decision = report.decisions[0]
    assert decision.outcome is BindingOutcome.COULD_NOT_BE_CHECKED
    assert set(decision.unchecked) == {"openalex", "crossref"}


def test_a_degraded_miss_is_unchecked_not_refuted(tmp_path) -> None:  # noqa: ANN001
    """No key configured: a 404 from an anonymous pool is not the registry's answer.

    The cache already refuses to store this. Before the reading carried its own outcome,
    it was still handed back as absence — so a reviewer cloning the repo without a key got
    `did-not-resolve` for every candidate key outside the fixture set.
    """
    caller = HttpClient(
        credentials=[OpenAlexCredential(None), CrossrefCredential(None)],
        mode=CacheMode.LIVE,
        cache=HttpCache([tmp_path], [tmp_path]),
        transport=Registry(),
        clock=ManualClock(),
    )
    subject = premise("The paper reports a weight-loss effect.", candidate_key=REAL)
    _, report = bind_candidate_keys(graph_with(subject), caller)

    decision = report.decisions[0]
    assert decision.outcome is BindingOutcome.COULD_NOT_BE_CHECKED
    assert "without the credential" in decision.unchecked["openalex"]


def test_one_registry_looking_is_enough_to_refute(tmp_path) -> None:  # noqa: ANN001
    """A DOI absent from OpenAlex is checked, even though Crossref also answered."""
    subject = premise("A study the model invented supports this.", candidate_key=INVENTED)
    _, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry(REAL)))
    assert report.decisions[0].outcome is BindingOutcome.DID_NOT_RESOLVE


def test_a_partial_check_never_refutes(tmp_path) -> None:  # noqa: ANN001
    """One registry says no, the other cannot be reached — that is not a completed check."""

    class HalfDown:
        def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
            if "crossref" in url:
                raise TransportError(f"{url} did not complete: refused")
            return RawResponse(status=404, body="", headers=HEADERS)

    check = check_key(client(tmp_path, HalfDown()), INVENTED)
    assert check.answered == ["openalex"] and set(check.unreachable) == {"crossref"}
    assert not check.complete and not check.refutes

    subject = premise("Unverifiable right now.", candidate_key=INVENTED)
    _, report = bind_candidate_keys(graph_with(subject), client(tmp_path, HalfDown()))
    assert report.decisions[0].outcome is BindingOutcome.COULD_NOT_BE_CHECKED


# -- what binding does not claim ---------------------------------------------------


def test_binding_a_key_does_not_make_a_premise_verified(tmp_path) -> None:  # noqa: ANN001
    """An identifier naming a real work says nothing about whether the premise holds."""
    subject = premise("The paper reports a weight-loss effect.", candidate_key=REAL)
    bound, _ = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry(REAL)))
    assert bound.premises[subject.id].evidence_state is EvidenceState.UNVERIFIED
    assert bound.groundings == []


def test_binding_leaves_every_identity_untouched(tmp_path) -> None:  # noqa: ANN001
    """Premise ids derive from text, so steps and edges must survive a binding pass."""
    subject = premise("The paper reports a weight-loss effect.", candidate_key=REAL)
    other = premise("A second premise.")
    before = graph_with(subject, other)
    after, _ = bind_candidate_keys(before, client(tmp_path, Registry(REAL)))

    assert set(after.premises) == set(before.premises)
    assert [s.id for s in after.steps] == [s.id for s in before.steps]
    assert after.root_claim.id == before.root_claim.id


def test_the_report_carries_its_own_partial_label(tmp_path) -> None:  # noqa: ANN001
    subject = premise("The paper reports a weight-loss effect.", candidate_key=REAL)
    _, report = bind_candidate_keys(graph_with(subject), client(tmp_path, Registry(REAL)))

    assert report.is_partial
    assert "NOT the pre-registered measurement" in report.basis
    # The label is data, so a renderer cannot drop it by forgetting to mention it.
    rendered = " ".join(report.render().split())
    assert " ".join(PARTIAL_BASIS.split()) in rendered
    assert "bound: 1" in rendered


def test_the_report_counts_every_outcome_it_saw(tmp_path) -> None:  # noqa: ANN001
    subject = premise("Resolves.", candidate_key=REAL)
    invented = premise("Does not resolve.", candidate_key=INVENTED)
    plain = premise("No candidate at all.")
    _, report = bind_candidate_keys(
        graph_with(subject, invented, plain), client(tmp_path, Registry(REAL))
    )
    assert report.counts == {"bound": 1, "no-candidate-key": 1, "did-not-resolve": 1}


def test_a_decision_is_recorded_for_every_premise(tmp_path) -> None:  # noqa: ANN001
    premises = [premise(f"Premise {i}.") for i in range(4)]
    graph = graph_with(*premises)
    _, report = bind_candidate_keys(graph, client(tmp_path, Registry()))
    assert {d.premise_id for d in report.decisions} == set(graph.premises)


def test_binding_records_when_the_registry_answered(tmp_path) -> None:  # noqa: ANN001
    """Nothing here stamps `now()` onto a reading — the check is the client's."""
    subject = premise("The paper reports a weight-loss effect.", candidate_key=REAL)
    caller = client(tmp_path, Registry(REAL))
    bind_candidate_keys(graph_with(subject), caller)
    record = openalex.fetch_work(caller, REAL)
    assert record.from_cache and record.fetched_at < datetime.now(UTC)
