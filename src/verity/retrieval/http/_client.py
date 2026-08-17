"""The client: cache, limiter, budget, retries and pool assertion, composed once.

Order matters and each step is here for a reason.

1. **Cache first, and a hit acquires nothing.** No limiter, no sleep, no budget check. The
   limiter starts at one request per second, so charging hits for it would make a replay of
   19 identifiers across two registries take about forty seconds — and the fix someone
   reaches for when a suite is slow is weakening the limiter, not the thing that made it
   slow.
2. **Budget before wire.** The floor is checked against the last observed remaining, so a
   run stops at the floor instead of discovering the wall mid-graph.
3. **Limiter before wire**, keyed on the endpoint class the call site declared.
4. **Pool assertion after any real answer**, including a 404, because a degraded 404 is
   precisely the response that must not be cached as a miss.
5. **Cache last**, and never a negative entry from a degraded request.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

from verity.config import RetrievalConfig
from verity.retrieval.errors import (
    BudgetExhaustedError,
    CacheMissError,
    RateLimitedError,
    TransportError,
)
from verity.retrieval.http._cache import HttpCache
from verity.retrieval.http._clock import Clock, SystemClock
from verity.retrieval.http._credentials import (
    Credential,
    CrossrefCredential,
    OpenAlexCredential,
)
from verity.retrieval.http._limits import CreditBudget, LimiterSet
from verity.retrieval.http._model import CacheMode, Fetched, FetchLog, HttpRequest
from verity.retrieval.http._transport import Transport, UrllibTransport
from verity.secrets import Secrets

#: Committed recordings, resolved from this file rather than the working directory. A
#: fixture is part of the source, and a CWD-relative path silently reads — or in `RECORD`
#: mode writes — a different tree depending on where the process was launched.
FIXTURE_ROOT = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "http"

#: Statuses worth trying again. Everything else is either an answer (200, 404, 410) or a
#: refusal no amount of waiting fixes.
_RETRYABLE = frozenset({429, 500, 502, 503, 504})
#: OpenAlex returns these when an allowance is spent rather than when a work is absent.
_QUOTA_STATUSES = frozenset({403, 409})


class HttpClient:
    """Cached, rate-limited, retrying GETs against one process's worth of sources."""

    def __init__(
        self,
        *,
        credentials: Sequence[Credential],
        config: RetrievalConfig | None = None,
        mode: CacheMode = CacheMode.LIVE,
        cache: HttpCache | None = None,
        transport: Transport | None = None,
        clock: Clock | None = None,
        budgets: Sequence[CreditBudget] = (),
    ) -> None:
        self.config = config or RetrievalConfig()
        self.mode = mode
        self._credentials = {credential.source: credential for credential in credentials}
        self._transport = transport or UrllibTransport()
        self._clock = clock or SystemClock()
        self._limiters = LimiterSet(self.config.default_rate_per_s)
        self._budgets = {budget.source: budget for budget in budgets}
        self._cache = cache or self._default_cache(mode, self.config.cache_dir)
        self.log = FetchLog(
            mode=mode,
            max_retries=self.config.max_retries,
            credit_floor=self.config.openalex_credit_floor,
            max_retry_after_s=int(self.config.max_retry_after_s),
        )

    @staticmethod
    def _default_cache(mode: CacheMode, cache_dir: Path) -> HttpCache:
        """Which recordings a mode may read, and which it may write.

        `REPLAY` reads the committed fixtures and nothing else. A developer's working cache
        is not part of the recording being replayed, and letting it shadow a fixture would
        mean a passing suite proves the fixture is *reproducible on that machine* rather
        than that it is correct. Every other mode reads the working cache first — that is
        what it is for — and falls back to the fixtures.

        `OFFLINE` is the exception that proves the distinction: replaying a *recorded run*
        must read the bytes that run wrote, which live in the working cache, so it reads
        both roots and writes neither. Fixtures-only is a claim about a fixture; offline is
        a claim about the network.
        """
        match mode:
            case CacheMode.REPLAY:
                return HttpCache([FIXTURE_ROOT], [])
            case CacheMode.OFFLINE:
                return HttpCache([cache_dir, FIXTURE_ROOT], [])
            case CacheMode.RECORD:
                return HttpCache([cache_dir, FIXTURE_ROOT], [cache_dir, FIXTURE_ROOT])
            case _:
                return HttpCache([cache_dir, FIXTURE_ROOT], [cache_dir])

    # -- the one entry point -------------------------------------------------------

    def get(self, request: HttpRequest) -> Fetched:
        """Fetch `request`, from cache or wire. 404 and 410 return; nothing else does."""
        self.log.requests += 1

        if self.mode.may_read_cache:
            hit = self._cache.get(request)
            if hit is not None:
                self.log.cache_hits += 1
                if hit.missing:
                    self.log.negative_hits += 1
                return hit

        if not self.mode.may_fetch:
            raise CacheMissError(
                f"replay mode has no entry for {request.url}; record it first rather than "
                "falling through to the network"
            )

        fetched = self._fetch(request)

        # A miss recorded from a request that went out without its credential is not
        # credibly "asked and absent", and an immortal negative entry is the one kind of
        # staleness this tier cannot tolerate.
        if not (fetched.missing and fetched.degraded):
            self._cache.put(fetched)
        return fetched

    # -- wire ----------------------------------------------------------------------

    def _fetch(self, request: HttpRequest) -> Fetched:
        """Send `request`, retrying what is worth retrying.

        Every exit is explicit. An earlier version broke out of the loop on any terminal
        condition and counted a retry exhaustion at the bottom, so a 400 — never retried
        once — reported the retry bound as having bitten, while a spent allowance raised
        past the budget counter and reported no bound at all. The manifest was wrong in
        both directions, and `CapRecord` cannot catch that: `applied=True` with a `dropped`
        count is a legal record of something that never happened.
        """
        credential = self._credentials.get(request.source)
        if credential is None:
            raise TransportError(f"no credential configured for source {request.source!r}")
        budget = self._budgets.get(request.source)

        for attempt in range(self.config.max_retries + 1):
            last_attempt = attempt == self.config.max_retries
            if budget is not None:
                refusal = budget.refusal_reason(request.credit_cost_hint)
                if refusal is not None:
                    self._refuse_on_budget(refusal)

            self.log.sleep_seconds += self._limiters.for_key(request.limiter_key).acquire(
                self._clock
            )

            try:
                raw = self._transport.send(
                    request.url, credential.headers(), self.config.request_timeout_s
                )
            except TransportError:
                if last_attempt:
                    self.log.retry_exhaustions += 1
                    raise
                self._backoff(attempt, None)
                continue

            fetched = Fetched(
                request=request,
                status=raw.status,
                body=raw.body,
                headers=raw.headers,
                fetched_at=datetime.now(UTC),
                degraded=credential.degraded,
            )
            self._limiters.observe(fetched)
            if budget is not None:
                budget.observe(fetched)

            if fetched.found or fetched.missing:
                # Asserted on a miss too: a 404 from an unpaid pool is the response that
                # must never become a cached negative.
                credential.assert_pool(fetched)
                self.log.network_calls += 1
                return fetched

            if fetched.status in _QUOTA_STATUSES:
                self._refuse_on_budget(
                    f"{request.source} returned {fetched.status} for {request.url}; the "
                    "allowance for this credential is spent"
                )

            if fetched.status not in _RETRYABLE:
                raise TransportError(
                    f"{request.url} returned {fetched.status}, which no amount of waiting "
                    "changes"
                )
            if last_attempt:
                self.log.retry_exhaustions += 1
                if fetched.status == 429:
                    raise RateLimitedError(
                        f"{request.source} rate-limited {request.url} through "
                        f"{self.config.max_retries} retries"
                    )
                raise TransportError(
                    f"{request.url} returned {fetched.status} through "
                    f"{self.config.max_retries} retries"
                )
            self._backoff(attempt, fetched.retry_after_s)

        raise TransportError(f"{request.url} did not complete")  # pragma: no cover

    def _refuse_on_budget(self, reason: str) -> NoReturn:
        """The one place a budget refusal is counted and raised.

        Both refusals go through here — the pre-flight floor check and a source telling us
        outright that the allowance is spent — because a run that stopped for want of
        credits and a manifest that reports no bound applied is precisely the silent cap
        evaluation §6 forbids.
        """
        self.log.budget_blocks += 1
        raise BudgetExhaustedError(reason)

    def _backoff(self, attempt: int, retry_after_s: float | None) -> None:
        """Honour `Retry-After` within reason; otherwise exponential with injected jitter.

        A `Retry-After` past the ceiling is refused rather than capped. Capping it and
        retrying early would ignore an instruction the server gave explicitly; sleeping it
        out would let one header hang a run for as long as the header says, and the header
        is not ours. Stopping is the only response that neither disobeys nor blocks.
        """
        if retry_after_s is not None and retry_after_s > self.config.max_retry_after_s:
            self.log.retry_after_refusals += 1
            ceiling = self.config.max_retry_after_s
            raise RateLimitedError(
                f"asked to wait {retry_after_s:.0f}s, past the {ceiling:.0f}s ceiling; "
                "stopping rather than ignoring the instruction or blocking on it"
            )
        self.log.retries += 1
        delay = (
            retry_after_s
            if retry_after_s is not None
            else self.config.retry_base_delay_s * (2**attempt) * (1.0 + self._clock.jitter())
        )
        self._clock.sleep(delay)
        self.log.sleep_seconds += delay

    # -- reporting -----------------------------------------------------------------

    @property
    def credits_spent(self) -> int:
        return sum(budget.spent for budget in self._budgets.values())

    def summary(self) -> FetchLog:
        self.log.credits_spent = self.credits_spent
        return self.log


def build_client(
    *,
    config: RetrievalConfig | None = None,
    secrets: Secrets | None = None,
    mode: CacheMode = CacheMode.LIVE,
    transport: Transport | None = None,
    clock: Clock | None = None,
    cache: HttpCache | None = None,
) -> HttpClient:
    """The construction path callers should use: credentials and budget wired from config."""
    config = config or RetrievalConfig()
    secrets = secrets or Secrets()
    return HttpClient(
        credentials=[
            OpenAlexCredential(secrets.reveal("openalex_api_key")),
            CrossrefCredential(secrets.reveal("crossref_mailto")),
        ],
        budgets=[CreditBudget("openalex", config.openalex_credit_floor)],
        config=config,
        mode=mode,
        transport=transport,
        clock=clock,
        cache=cache,
    )
