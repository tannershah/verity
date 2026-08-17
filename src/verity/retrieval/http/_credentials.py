"""Credentials, applied at the wire and asserted on the way back.

Two rules, and the second is the one that is easy to skip.

**Apply them as headers, never as query parameters.** Verified live: OpenAlex authenticates
on an `api_key` request header and bills the keyed pool, and Crossref reaches the polite
pool on a `User-Agent` carrying `mailto:` — `polite-single` at 10 req/s against
`public-single` at 5. So no credential ever needs to enter a URL, and `HttpRequest` refuses
one that does.

**Assert the pool the response came back on.** Header authentication fails *open*. A
renamed header, a revoked key, or a dropped `User-Agent` does not return 401 — it returns
200 from the anonymous pool, silently spending a shared budget until something unrelated
breaks two stages later. This was observed rather than imagined: a keyless probe during
this tier's design returned a perfectly ordinary 200 against a 1,000-credit anonymous
allowance. Landing on an unpaid pool with a credential configured is therefore a loud
error, not a log line.
"""

from __future__ import annotations

from typing import Protocol

from verity.retrieval.errors import DegradedCredentialError
from verity.retrieval.http._model import Fetched

#: The anonymous OpenAlex credit ceiling, observed 2026-08-16 (`X-RateLimit-Limit: 1000`
#: keyless against `10000` for a registered key). The keyed assertion is `limit > this`
#: rather than an equality against a known tier, so a tier change surfaces as one loud
#: failure here instead of as a run that quietly spends someone else's allowance.
ANONYMOUS_OPENALEX_CEILING = 1000

USER_AGENT = "verity/0.0.1 (research prototype)"


class Credential(Protocol):
    """What a source needs on the wire, and what it must prove on the way back."""

    source: str

    @property
    def degraded(self) -> bool:
        """True when this source expects a credential and none is configured."""
        ...

    def headers(self) -> dict[str, str]:
        """Request headers. The only place a secret value is read."""
        ...

    def assert_pool(self, fetched: Fetched) -> None:
        """Raise if the response proves the credential did not reach its pool."""
        ...


class OpenAlexCredential:
    """`api_key` as a request header. A key is expected; absence is degraded, not fatal."""

    source = "openalex"

    def __init__(self, api_key: str | None) -> None:
        self._api_key = api_key

    @property
    def degraded(self) -> bool:
        return self._api_key is None

    def headers(self) -> dict[str, str]:
        base = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if self._api_key is not None:
            base["api_key"] = self._api_key
        return base

    def assert_pool(self, fetched: Fetched) -> None:
        if self._api_key is None:
            return
        limit = fetched.credit_limit
        if limit is None:
            # No meter at all on a response that should carry one. Treated as unproven
            # rather than assumed good: the whole point is that success proves nothing.
            raise DegradedCredentialError(
                "openalex returned no credit meter, so a configured key cannot be shown "
                f"to have reached its pool ({fetched.request.url})"
            )
        if limit <= ANONYMOUS_OPENALEX_CEILING:
            raise DegradedCredentialError(
                f"openalex answered on a {limit}-credit allowance while a key is "
                f"configured; at or below {ANONYMOUS_OPENALEX_CEILING} this is the "
                "anonymous pool, so the key did not reach the wire"
            )


class CrossrefCredential:
    """`mailto` inside the `User-Agent`. Crossref needs no key; the address buys the pool."""

    source = "crossref"

    def __init__(self, mailto: str | None) -> None:
        self._mailto = mailto

    @property
    def degraded(self) -> bool:
        return self._mailto is None

    def headers(self) -> dict[str, str]:
        if self._mailto is None:
            return {"User-Agent": USER_AGENT, "Accept": "application/json"}
        agent = f"{USER_AGENT[:-1]}; mailto:{self._mailto})"
        return {"User-Agent": agent, "Accept": "application/json"}

    def assert_pool(self, fetched: Fetched) -> None:
        if self._mailto is None:
            return
        pool = fetched.pool
        if pool is None:
            raise DegradedCredentialError(
                "crossref returned no x-api-pool, so a configured mailto cannot be shown "
                f"to have reached the polite pool ({fetched.request.url})"
            )
        if not pool.startswith("polite"):
            raise DegradedCredentialError(
                f"crossref answered on pool {pool!r} while a mailto is configured; the "
                "polite pool is what the address pays for, so it did not reach the wire"
            )


class NoCredential:
    """A source that needs nothing and can therefore prove nothing. Never degraded."""

    def __init__(self, source: str) -> None:
        self.source = source

    @property
    def degraded(self) -> bool:
        return False

    def headers(self) -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}

    def assert_pool(self, fetched: Fetched) -> None:
        return
