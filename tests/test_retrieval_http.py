"""The four invariants the HTTP layer exists to hold, plus the failure modes that are silent.

Every test here runs against a scripted transport and a manual clock, with sockets poisoned,
so nothing waits and nothing spends a credit.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from verity.config import RetrievalConfig
from verity.keys import ExternalKey, KeyType
from verity.retrieval.errors import (
    BudgetExhaustedError,
    CacheMissError,
    DegradedCredentialError,
    RateLimitedError,
    TransportError,
)
from verity.retrieval.http import (
    CREDENTIAL_PARAMS,
    FIXTURE_ROOT,
    CacheMode,
    CreditBudget,
    CrossrefCredential,
    Fetched,
    HttpCache,
    HttpClient,
    HttpRequest,
    ManualClock,
    NoCredential,
    OpenAlexCredential,
    RawResponse,
    UrllibTransport,
    entry_digest,
)

pytestmark = pytest.mark.usefixtures("poisoned_socket")

OPENALEX_URL = "https://api.openalex.org/works/https://doi.org/10.3823/1654"
CROSSREF_URL = "https://api.crossref.org/works/10.3823/1654"

#: A keyed OpenAlex response, as observed. The credit meter and the ceiling both matter.
OPENALEX_HEADERS = {
    "x-ratelimit-limit": "10000",
    "x-ratelimit-remaining": "9886",
    "x-ratelimit-credits-used": "1",
    "x-ratelimit-reset": "5685",
}
CROSSREF_HEADERS = {
    "x-api-pool": "polite-single",
    "x-rate-limit-limit": "10",
    "x-rate-limit-interval": "1s",
}


def crossref_headers(limit: str, pool: str = "polite-single") -> dict[str, str]:
    return {"x-api-pool": pool, "x-rate-limit-limit": limit, "x-rate-limit-interval": "1s"}


class ScriptedTransport:
    """Returns queued responses and counts what it was asked for."""

    def __init__(self, *responses: RawResponse) -> None:
        self._responses = list(responses)
        self.sent: list[str] = []
        self.headers_seen: list[dict[str, str]] = []

    def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
        self.sent.append(url)
        self.headers_seen.append(dict(headers))
        if not self._responses:
            raise AssertionError(f"transport asked for {url} with nothing scripted")
        response = self._responses.pop(0)
        if isinstance(response, Exception):  # pragma: no cover - defensive
            raise response
        return response

    @property
    def calls(self) -> int:
        return len(self.sent)


class FailingTransport:
    """Raises the same transport error every time. Counts attempts."""

    def __init__(self) -> None:
        self.calls = 0

    def send(self, url: str, headers, timeout_s: float) -> RawResponse:  # noqa: ANN001
        self.calls += 1
        raise TransportError(f"{url} did not complete: refused")


def ok(body: dict | None = None, headers: dict[str, str] | None = None) -> RawResponse:
    return RawResponse(
        status=200, body=json.dumps(body or {"id": "W1"}), headers=headers or OPENALEX_HEADERS
    )


def status(code: int, headers: dict[str, str] | None = None) -> RawResponse:
    return RawResponse(status=code, body="", headers=headers or OPENALEX_HEADERS)


def request(url: str = OPENALEX_URL, source: str = "openalex", **kwargs) -> HttpRequest:
    return HttpRequest(url=url, source=source, **kwargs)


def client(
    tmp_path: Path,
    transport,  # noqa: ANN001
    *,
    mode: CacheMode = CacheMode.LIVE,
    credentials=None,  # noqa: ANN001
    budgets=(),
    clock: ManualClock | None = None,
    config: RetrievalConfig | None = None,
) -> HttpClient:
    return HttpClient(
        credentials=credentials or [OpenAlexCredential("secret-key"), NoCredential("crossref")],
        config=config or RetrievalConfig(),
        mode=mode,
        cache=HttpCache([tmp_path], [] if mode is CacheMode.REPLAY else [tmp_path]),
        transport=transport,
        clock=clock or ManualClock(),
        budgets=budgets,
    )


# -- invariant 1: no credential in a URL -------------------------------------------


@pytest.mark.parametrize("param", sorted(CREDENTIAL_PARAMS))
def test_request_refuses_a_credential_in_the_url(param: str) -> None:
    with pytest.raises(ValueError, match="credential parameter"):
        HttpRequest(url=f"https://api.openalex.org/works?{param}=abc123", source="openalex")


@pytest.mark.parametrize("spelling", ["api-key", "API_KEY", "Api-Key", "MAILTO"])
def test_the_tripwire_matches_a_name_however_it_is_spelled(spelling: str) -> None:
    """Case and hyphens are not a way past it — though the denylist is not the guarantee."""
    with pytest.raises(ValueError, match="credential parameter"):
        HttpRequest(url=f"https://api.openalex.org/works?{spelling}=abc", source="openalex")


def test_credentials_travel_as_headers_and_never_reach_the_cache(tmp_path: Path) -> None:
    transport = ScriptedTransport(ok())
    api_key = "sk-openalex-do-not-leak"
    caller = client(
        tmp_path, transport, credentials=[OpenAlexCredential(api_key), NoCredential("crossref")]
    )
    caller.get(request())

    assert transport.headers_seen[0]["api_key"] == api_key
    written = list(tmp_path.rglob("*.json"))
    assert written, "nothing was cached"
    for path in written:
        assert api_key not in path.read_text(), f"{path} leaked the credential"
        assert api_key not in str(path)


def test_mailto_reaches_the_user_agent_not_the_url() -> None:
    headers = CrossrefCredential("someone@example.org").headers()
    assert "mailto:someone@example.org" in headers["User-Agent"]


def test_transport_errors_carry_no_headers(tmp_path: Path) -> None:
    caller = client(
        tmp_path,
        FailingTransport(),
        credentials=[OpenAlexCredential("sk-leak-me"), NoCredential("crossref")],
    )
    with pytest.raises(TransportError) as excinfo:
        caller.get(request())
    assert "sk-leak-me" not in str(excinfo.value)
    assert "sk-leak-me" not in repr(excinfo.value)


# -- invariant 2: a cache hit replays the clock and acquires nothing ----------------


def test_cache_hit_issues_no_request_and_keeps_the_original_fetch_time(tmp_path: Path) -> None:
    transport = ScriptedTransport(ok())
    caller = client(tmp_path, transport)
    first = caller.get(request())

    second = caller.get(request())
    assert transport.calls == 1
    assert second.from_cache and not first.from_cache
    # The whole of M5-T3's TTL re-validation reads this field.
    assert second.fetched_at == first.fetched_at
    assert caller.log.cache_hits == 1


def test_cache_hit_acquires_no_limiter_and_sleeps_not_at_all(tmp_path: Path) -> None:
    clock = ManualClock()
    transport = ScriptedTransport(ok(), ok())
    caller = client(tmp_path, transport, clock=clock)

    caller.get(request())
    caller.get(request(CROSSREF_URL, "crossref"))
    baseline = list(clock.sleeps)

    for _ in range(20):
        caller.get(request())
        caller.get(request(CROSSREF_URL, "crossref"))

    assert clock.sleeps == baseline, "cache hits waited on the rate limiter"
    assert caller.log.cache_hits == 40


def test_a_truncated_entry_is_a_miss_not_an_empty_record(tmp_path: Path) -> None:
    transport = ScriptedTransport(ok(), ok({"id": "W2"}))
    caller = client(tmp_path, transport)
    caller.get(request())

    entry = next(iter(tmp_path.rglob("*.json")))
    entry.write_text(entry.read_text()[: len(entry.read_text()) // 2])

    refetched = caller.get(request())
    assert transport.calls == 2
    assert json.loads(refetched.body)["id"] == "W2"


def test_writes_leave_no_temporary_files(tmp_path: Path) -> None:
    caller = client(tmp_path, ScriptedTransport(ok()))
    caller.get(request())
    assert not list(tmp_path.rglob("*.tmp")), "a partial write survived"


def test_cache_paths_are_digests_so_an_identifier_cannot_escape(tmp_path: Path) -> None:
    """`_DOI_RE` accepts `10.1234/../../../etc/passwd`; the cache must not care."""
    hostile = ExternalKey(type=KeyType.DOI, value="10.1234/../../../etc/passwd")
    hostile_request = request(f"https://api.openalex.org/works/https://doi.org/{hostile.value}")
    caller = client(tmp_path, ScriptedTransport(ok()))
    caller.get(hostile_request)

    written = list(tmp_path.rglob("*.json"))
    assert len(written) == 1
    assert ".." not in str(written[0])
    assert written[0].name.startswith(entry_digest(hostile_request))
    assert tmp_path in written[0].parents


# -- invariant 3: a credential that missed its pool is loud ------------------------


def test_openalex_on_the_anonymous_allowance_with_a_key_configured_raises(
    tmp_path: Path,
) -> None:
    anonymous = dict(
        OPENALEX_HEADERS, **{"x-ratelimit-limit": "1000", "x-ratelimit-remaining": "986"}
    )
    caller = client(tmp_path, ScriptedTransport(ok(headers=anonymous)))
    with pytest.raises(DegradedCredentialError, match="anonymous pool"):
        caller.get(request())


def test_openalex_with_no_meter_at_all_is_unproven_not_assumed_good(tmp_path: Path) -> None:
    meterless = ok(headers={"content-type": "application/json"})
    caller = client(tmp_path, ScriptedTransport(meterless))
    with pytest.raises(DegradedCredentialError, match="no credit meter"):
        caller.get(request())


def test_crossref_on_the_public_pool_with_a_mailto_configured_raises(tmp_path: Path) -> None:
    public = crossref_headers("5", pool="public-single")
    caller = client(
        tmp_path,
        ScriptedTransport(ok(headers=public)),
        credentials=[CrossrefCredential("someone@example.org")],
    )
    with pytest.raises(DegradedCredentialError, match="polite pool"):
        caller.get(request(CROSSREF_URL, "crossref"))


def test_a_source_with_no_credential_configured_asserts_nothing(tmp_path: Path) -> None:
    caller = client(
        tmp_path,
        ScriptedTransport(ok(headers=CROSSREF_HEADERS)),
        credentials=[CrossrefCredential(None)],
    )
    fetched = caller.get(request(CROSSREF_URL, "crossref"))
    assert fetched.found and fetched.degraded


# -- invariant 4: a 404 is a reading, everything else raises -----------------------


def test_404_is_a_reading_and_lands_in_the_negative_namespace(tmp_path: Path) -> None:
    caller = client(tmp_path, ScriptedTransport(status(404)))
    fetched = caller.get(request())
    assert fetched.missing and not fetched.found
    assert list((tmp_path / "missing").rglob("*.json"))
    assert not list((tmp_path / "found").rglob("*.json"))


def test_a_degraded_404_is_never_cached(tmp_path: Path) -> None:
    """One exhausted anonymous run must not poison every key it touched."""
    caller = client(
        tmp_path,
        ScriptedTransport(status(404, CROSSREF_HEADERS), status(404, CROSSREF_HEADERS)),
        credentials=[CrossrefCredential(None)],
    )
    first = caller.get(request(CROSSREF_URL, "crossref"))
    assert first.degraded and first.missing
    assert not list(tmp_path.rglob("*.json"))

    caller.get(request(CROSSREF_URL, "crossref"))
    assert caller.log.cache_hits == 0, "a degraded miss was cached and replayed"


def test_a_credentialed_404_is_cached_and_counted_separately(tmp_path: Path) -> None:
    """A run served from cached misses is worth telling apart from one that found things."""
    caller = client(tmp_path, ScriptedTransport(status(404)))
    caller.get(request())
    assert list((tmp_path / "missing").rglob("*.json"))

    caller.get(request())
    log = caller.summary()
    assert log.cache_hits == 1 and log.negative_hits == 1


def test_a_non_retryable_status_reports_no_retry_cap(tmp_path: Path) -> None:
    """A 400 is never retried, so a manifest saying the retry bound bit is a fabrication."""
    transport = ScriptedTransport(status(400))
    caller = client(tmp_path, transport, clock=ManualClock())

    with pytest.raises(TransportError, match="no amount of waiting"):
        caller.get(request())

    log = caller.summary()
    assert transport.calls == 1 and log.retries == 0 and log.retry_exhaustions == 0
    cap = next(c for c in log.caps() if c.name == "retrieval_max_retries")
    assert not cap.applied and cap.dropped is None


def test_a_spent_allowance_reports_the_credit_cap(tmp_path: Path) -> None:
    """The mirror of the above: a run that stopped for want of credits must say so."""
    budget = CreditBudget("openalex", 200)
    caller = client(tmp_path, ScriptedTransport(status(403)), budgets=[budget])

    with pytest.raises(BudgetExhaustedError):
        caller.get(request())

    cap = next(c for c in caller.summary().caps() if c.name == "openalex_credit_floor")
    assert cap.applied and cap.dropped == 1


def test_a_retry_after_past_the_ceiling_stops_rather_than_sleeping_it_out(
    tmp_path: Path,
) -> None:
    """One upstream header must not hang a run for a day."""
    headers = dict(OPENALEX_HEADERS, **{"retry-after": "86400"})
    clock = ManualClock()
    caller = client(
        tmp_path,
        ScriptedTransport(status(429, headers)),
        clock=clock,
        config=RetrievalConfig(max_retries=3, max_retry_after_s=60.0),
    )

    with pytest.raises(RateLimitedError, match="ceiling"):
        caller.get(request())

    assert clock.slept == 0.0, "the run slept on a header past the ceiling"
    caps = caller.summary().caps()
    cap = next(c for c in caps if c.name == "retrieval_retry_after_ceiling")
    assert cap.applied and cap.dropped == 1


def test_a_retry_after_within_the_ceiling_is_still_honoured(tmp_path: Path) -> None:
    headers = dict(OPENALEX_HEADERS, **{"retry-after": "30"})
    clock = ManualClock(jitter=0.0)
    caller = client(
        tmp_path,
        ScriptedTransport(status(429, headers), ok()),
        clock=clock,
        config=RetrievalConfig(max_retries=1, max_retry_after_s=60.0),
    )
    caller.get(request())
    assert 30.0 in clock.sleeps


def test_500_retries_to_the_bound_then_raises_and_reports_a_cap(tmp_path: Path) -> None:
    config = RetrievalConfig(max_retries=2)
    transport = ScriptedTransport(status(500), status(500), status(500))
    clock = ManualClock(jitter=0.0)
    caller = client(tmp_path, transport, clock=clock, config=config)

    with pytest.raises(TransportError):
        caller.get(request())

    assert transport.calls == 3
    assert clock.sleeps[-2:] == [0.5, 1.0], "backoff is not exponential from the base"
    cap = next(c for c in caller.summary().caps() if c.name == "retrieval_max_retries")
    assert cap.applied and cap.dropped == "uncounted"


def test_429_honours_retry_after_over_the_backoff_schedule(tmp_path: Path) -> None:
    headers = dict(OPENALEX_HEADERS, **{"retry-after": "7"})
    transport = ScriptedTransport(status(429, headers), ok())
    clock = ManualClock(jitter=0.0)
    caller = client(tmp_path, transport, clock=clock, config=RetrievalConfig(max_retries=1))

    caller.get(request())
    assert 7.0 in clock.sleeps


def test_429_to_exhaustion_raises_rate_limited_not_a_generic_transport_error(
    tmp_path: Path,
) -> None:
    transport = ScriptedTransport(status(429), status(429))
    caller = client(
        tmp_path, transport, clock=ManualClock(), config=RetrievalConfig(max_retries=1)
    )
    with pytest.raises(RateLimitedError):
        caller.get(request())


def test_a_quota_status_is_a_budget_failure_not_a_retry(tmp_path: Path) -> None:
    transport = ScriptedTransport(status(403))
    caller = client(tmp_path, transport)
    with pytest.raises(BudgetExhaustedError):
        caller.get(request())
    assert transport.calls == 1, "a spent allowance was retried"


def test_a_dead_connection_retries_then_raises(tmp_path: Path) -> None:
    transport = FailingTransport()
    caller = client(
        tmp_path, transport, clock=ManualClock(), config=RetrievalConfig(max_retries=2)
    )
    with pytest.raises(TransportError):
        caller.get(request())
    assert transport.calls == 3


# -- the limiter -------------------------------------------------------------------


def test_the_limiter_adopts_an_advertised_rate_and_then_only_tightens(tmp_path: Path) -> None:
    fast, slow = crossref_headers("10"), crossref_headers("2")
    clock = ManualClock()
    caller = client(
        tmp_path,
        ScriptedTransport(ok(headers=fast), ok({"id": "W2"}, slow), ok({"id": "W3"}, fast)),
        clock=clock,
        credentials=[CrossrefCredential(None)],
    )
    key = request(CROSSREF_URL, "crossref").limiter_key
    limiter = caller._limiters.for_key(key)  # noqa: SLF001

    caller.get(request(CROSSREF_URL, "crossref"))
    assert limiter.rate_per_s == 10.0
    caller.get(request(CROSSREF_URL + "/2", "crossref"))
    assert limiter.rate_per_s == 2.0
    caller.get(request(CROSSREF_URL + "/3", "crossref"))
    assert limiter.rate_per_s == 2.0, "an advertised rate raised a limiter back up"


def test_endpoint_classes_get_independent_limiters(tmp_path: Path) -> None:
    single = request(CROSSREF_URL, "crossref", endpoint_class="work")
    array = request(CROSSREF_URL + "?q=x", "crossref", endpoint_class="list")
    assert single.limiter_key != array.limiter_key
    assert single.limiter_key[0] == array.limiter_key[0]


def test_the_first_request_against_a_new_endpoint_class_does_not_wait(tmp_path: Path) -> None:
    clock = ManualClock()
    caller = client(tmp_path, ScriptedTransport(ok()), clock=clock)
    caller.get(request())
    assert clock.sleeps == []


# -- the credit budget -------------------------------------------------------------


def test_the_credit_floor_blocks_before_the_wire_and_reports_what_it_refused(
    tmp_path: Path,
) -> None:
    low = dict(OPENALEX_HEADERS, **{"x-ratelimit-remaining": "205"})
    transport = ScriptedTransport(ok(headers=low))
    budget = CreditBudget("openalex", 200)
    caller = client(tmp_path, transport, budgets=[budget], config=RetrievalConfig(top_k=10))

    caller.get(request())
    assert budget.remaining == 205 and budget.spent == 1

    with pytest.raises(BudgetExhaustedError):
        caller.get(request("https://api.openalex.org/works/W2", credit_cost_hint=10))
    assert transport.calls == 1

    cap = next(c for c in caller.summary().caps() if c.name == "openalex_credit_floor")
    assert cap.applied and cap.dropped == 1


def test_credit_cost_is_read_from_the_response_not_predicted(tmp_path: Path) -> None:
    listing = dict(OPENALEX_HEADERS, **{"x-ratelimit-credits-used": "10"})
    budget = CreditBudget("openalex", 0)
    caller = client(tmp_path, ScriptedTransport(ok(headers=listing)), budgets=[budget])
    caller.get(request(credit_cost_hint=1))
    assert budget.spent == 10, "cost was taken from the hint rather than the meter"


def test_an_http_exception_is_typed_and_retried_like_any_other_dead_connection(
    tmp_path: Path,
) -> None:
    """`IncompleteRead` is not an `OSError`, so it escaped the transport contract entirely."""
    import http.client
    import urllib.request

    class Truncating:
        calls = 0

        def __call__(self, request, timeout):  # noqa: ANN001, ARG002
            Truncating.calls += 1
            raise http.client.IncompleteRead(b"half a bod")

    monkey = Truncating()
    original = urllib.request.urlopen
    urllib.request.urlopen = monkey
    try:
        caller = client(
            tmp_path,
            UrllibTransport(),
            clock=ManualClock(),
            config=RetrievalConfig(max_retries=1),
        )
        with pytest.raises(TransportError, match="IncompleteRead"):
            caller.get(request())
    finally:
        urllib.request.urlopen = original

    assert Truncating.calls == 2, "a truncated body was not retried"


# -- cache roots by mode -------------------------------------------------------------


def test_replay_reads_the_committed_fixtures_and_not_a_working_cache(tmp_path: Path) -> None:
    """A local cache shadowing a fixture would prove reproducibility on one machine only."""
    caller = HttpClient(
        credentials=[OpenAlexCredential("k"), NoCredential("crossref")],
        config=RetrievalConfig(cache_dir=tmp_path),
        mode=CacheMode.REPLAY,
        transport=ScriptedTransport(),
    )
    roots = caller._cache._roots  # noqa: SLF001
    assert roots == [FIXTURE_ROOT]
    assert tmp_path not in roots


def test_live_reads_the_working_cache_first_then_the_fixtures(tmp_path: Path) -> None:
    caller = HttpClient(
        credentials=[OpenAlexCredential("k")],
        config=RetrievalConfig(cache_dir=tmp_path),
        mode=CacheMode.LIVE,
        transport=ScriptedTransport(),
    )
    assert caller._cache._roots == [tmp_path, FIXTURE_ROOT]  # noqa: SLF001
    assert caller._cache._write_roots == [tmp_path]  # noqa: SLF001


def test_the_fixture_root_does_not_move_with_the_working_directory() -> None:
    """A CWD-relative fixture path reads — or in RECORD mode writes — a different tree."""
    assert FIXTURE_ROOT.is_absolute()
    assert FIXTURE_ROOT.exists(), "the committed fixtures are not where the client looks"


def test_a_run_that_touched_no_network_says_so(tmp_path: Path) -> None:
    """`mode=live` describes what was permitted; a demo writeup needs what happened."""
    caller = client(tmp_path, ScriptedTransport(ok()))
    caller.get(request())
    assert not caller.summary().served_entirely_from_cache

    replayer = client(tmp_path, ScriptedTransport(), mode=CacheMode.REPLAY)
    replayer._cache = HttpCache([tmp_path], [])  # noqa: SLF001
    replayer.get(request())
    assert replayer.summary().served_entirely_from_cache


# -- replay ------------------------------------------------------------------------


def test_replay_never_falls_through_to_the_network(tmp_path: Path) -> None:
    caller = client(tmp_path, ScriptedTransport(), mode=CacheMode.REPLAY)
    with pytest.raises(CacheMissError):
        caller.get(request())


def test_replay_serves_a_recorded_entry(tmp_path: Path) -> None:
    client(tmp_path, ScriptedTransport(ok())).get(request())
    replayer = client(tmp_path, ScriptedTransport(), mode=CacheMode.REPLAY)
    assert replayer.get(request()).from_cache


def test_refresh_ignores_an_existing_entry(tmp_path: Path) -> None:
    transport = ScriptedTransport(ok(), ok({"id": "W-fresh"}))
    client(tmp_path, transport).get(request())
    refreshed = client(tmp_path, transport, mode=CacheMode.REFRESH).get(request())
    assert json.loads(refreshed.body)["id"] == "W-fresh"
    assert transport.calls == 2


# -- the record itself -------------------------------------------------------------


def test_fetched_refuses_a_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="naive fetched_at"):
        Fetched(
            request=request(), status=200, body="{}", fetched_at=datetime(2026, 8, 16, 12, 0)
        )


def test_fetched_refuses_a_header_outside_the_allowlist() -> None:
    with pytest.raises(ValueError, match="retained allowlist"):
        Fetched(
            request=request(),
            status=200,
            body="{}",
            headers={"set-cookie": "session=abc"},
            fetched_at=datetime.now(UTC),
        )
