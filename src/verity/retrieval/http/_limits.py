"""Rate limits read off responses, and a credit budget with a floor.

**Limits are advertised, not documented, and they differ per endpoint.** Verified live:
Crossref answers a singleton `works/{doi}` with `x-rate-limit-limit: 10 / 1s` on pool
`polite-single`, and a `works?query…` list with `3 / 1s` on `polite-array`. Nothing about
that is guessable, and a hardcoded rate is wrong on one of the two.

**Keyed by endpoint class, and tightened but never loosened.** The key is
`(host, endpoint_class)` — predicted at the call site — rather than `(host, pool)`
discovered from the response, which removes the bootstrap problem of not knowing a pool
until after the first request. Within a key, the first observation sets the rate and every
later one may only lower it. The pools happen to be disjoint per endpoint class today, so
nothing oscillates; the tighten-only rule is what keeps that true if a source ever serves
two rates under one name, at the cost of degrading to the slower of them.

**OpenAlex has one meter and it is credits.** `X-RateLimit-Remaining` decrements by exactly
`X-RateLimit-Credits-Used` — a singleton costs 1, a filtered list costs 10, and remaining
fell by 10 across the pair. There is no separate request meter to guard. `X-RateLimit-Reset`
came back at roughly 95 minutes, so the window is not a day and the ceiling is not a daily
figure; this is recorded here rather than in the build plan because it is what the code
depends on.
"""

from __future__ import annotations

from verity.retrieval.http._clock import Clock
from verity.retrieval.http._model import Fetched


class PoolLimiter:
    """A minimum-interval gate for one `(host, endpoint_class)`."""

    def __init__(self, rate_per_s: float) -> None:
        self._rate = rate_per_s
        self._observed = False
        self._last: float | None = None

    @property
    def rate_per_s(self) -> float:
        return self._rate

    @property
    def interval_s(self) -> float:
        return 1.0 / self._rate if self._rate > 0 else 0.0

    def observe(self, limit: int, interval_s: float) -> None:
        """Adopt an advertised rate on first sight; afterwards only tighten."""
        if interval_s <= 0 or limit <= 0:
            return
        advertised = limit / interval_s
        self._rate = advertised if not self._observed else min(self._rate, advertised)
        self._observed = True

    def acquire(self, clock: Clock) -> float:
        """Wait until the next request is due. Returns the seconds actually slept."""
        now = clock.monotonic()
        slept = 0.0
        if self._last is not None:
            due = self._last + self.interval_s
            if due > now:
                slept = due - now
                clock.sleep(slept)
                now = clock.monotonic()
        self._last = now
        return slept


class LimiterSet:
    """One limiter per `(host, endpoint_class)`, created on first use."""

    def __init__(self, default_rate_per_s: float) -> None:
        self._default = default_rate_per_s
        self._limiters: dict[tuple[str, str], PoolLimiter] = {}

    def for_key(self, key: tuple[str, str]) -> PoolLimiter:
        limiter = self._limiters.get(key)
        if limiter is None:
            limiter = PoolLimiter(self._default)
            self._limiters[key] = limiter
        return limiter

    def observe(self, fetched: Fetched) -> None:
        advertised = fetched.advertised_rate
        if advertised is not None:
            self.for_key(fetched.request.limiter_key).observe(*advertised)

    @property
    def rates(self) -> dict[tuple[str, str], float]:
        return {key: limiter.rate_per_s for key, limiter in self._limiters.items()}


class CreditBudget:
    """OpenAlex credits: what is left, what we may not spend, and what was refused.

    The floor is checked *before* a request, against the last observed remaining, so a run
    stops at a stated floor rather than discovering the wall mid-graph.

    **This object states the reason and never raises.** Counting a refusal and raising for
    it belong together in one place, and that place is the client — a source answering
    `403 allowance spent` is the same event as the floor being crossed, arrives on a
    different path, and was previously counted on neither. A bound that stopped a run while
    the manifest reported no bound applied is the silent cap evaluation §6 forbids.
    """

    def __init__(self, source: str, floor: int) -> None:
        self.source = source
        self.floor = floor
        self.remaining: int | None = None
        self.spent = 0

    def refusal_reason(self, cost_hint: int) -> str | None:
        """Why this request must not be sent, or `None` if it may be."""
        if self.remaining is None:
            return None
        if self.remaining - cost_hint < self.floor:
            return (
                f"{self.source} has {self.remaining} credits left and the floor is "
                f"{self.floor}; a {cost_hint}-credit request would cross it"
            )
        return None

    def observe(self, fetched: Fetched) -> None:
        used = fetched.credits_used
        if used is not None:
            self.spent += used
        remaining = fetched.credits_remaining
        if remaining is not None:
            self.remaining = remaining
