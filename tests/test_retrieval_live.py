"""The live half of M6-T1a's exit criterion. Opt in with `pytest -m live`.

Excluded from the default suite so that running the tests spends no OpenAlex credits and
needs no network — everything else in the retrieval suite runs from committed fixtures.
What only a live call can establish is that the recorded fixtures still describe the API:
that the request shapes resolve, that the meters and pools are still advertised under the
header names the limiter and the credit budget read, and that the pool assertion passes
against a real credential rather than a scripted one.

Deliberately small. Four singleton GETs cost two OpenAlex credits and prove the contract;
re-recording the corpus is `python -m verity.retrieval record --from-seed`, which is a
decision someone makes, not a test.
"""

from __future__ import annotations

import pytest

from verity.keys import ExternalKey, KeyType
from verity.retrieval import crossref, openalex
from verity.retrieval.http import CacheMode, build_client
from verity.secrets import Secrets

pytestmark = pytest.mark.live

CHOCOLATE = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
ABSENT = ExternalKey(type=KeyType.DOI, value="10.9999/verity-does-not-exist")


@pytest.fixture
def client():  # noqa: ANN201
    secrets = Secrets()
    if secrets.reveal("openalex_api_key") is None:
        pytest.skip("OPENALEX_API_KEY is not configured")
    # REFRESH so the assertions are made against the wire, not against a recording.
    return build_client(mode=CacheMode.REFRESH, secrets=secrets)


def test_both_clients_return_a_normalized_record_live(client) -> None:  # noqa: ANN001
    work = openalex.fetch_work(client, CHOCOLATE)
    doi = crossref.fetch_work(client, CHOCOLATE)

    for record in (work, doi):
        assert record.found and record.title
        assert record.fetched_at.tzinfo is not None
        assert not record.from_cache
        assert record.source_url and "api." not in record.source_url


def test_the_credit_meter_and_the_pool_are_still_advertised_where_we_read_them(
    client,  # noqa: ANN001
) -> None:
    """The pool assertion passing at all is the check: it raises when a meter is absent."""
    openalex.fetch_work(client, CHOCOLATE)
    crossref.fetch_work(client, CHOCOLATE)

    log = client.summary()
    assert log.credits_spent > 0, "OpenAlex stopped reporting x-ratelimit-credits-used"
    rates = client._limiters.rates  # noqa: SLF001
    assert any(rate > 1.0 for rate in rates.values()), (
        "no source advertised a rate, so the limiter never left its conservative default"
    )


def test_an_absent_identifier_is_a_reading_not_a_failure(client) -> None:  # noqa: ANN001
    assert openalex.fetch_work(client, ABSENT).found is False
    assert crossref.fetch_work(client, ABSENT).found is False


def test_the_identity_conflict_the_demo_rests_on_is_still_live(client) -> None:  # noqa: ANN001
    """Both registries serve a different paper under the chocolate hoax's DOI."""
    work = openalex.fetch_work(client, CHOCOLATE)
    assert openalex.retraction_flag(work) is True
    assert "resilience and spirituality" in (work.title or "").lower()
