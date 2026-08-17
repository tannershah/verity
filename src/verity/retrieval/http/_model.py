"""The value objects the HTTP layer moves around, and the invariants they carry.

**`HttpRequest` cannot hold a credential.** It has no headers field at all, and its
validator refuses a URL carrying a credential-shaped query parameter. Both registries
authenticate on headers — OpenAlex on `api_key`, Crossref on a `mailto` in the
`User-Agent` — so nothing needs one in a URL, and making the model refuse them means the
cache key can *be* the URL, cache filenames are safe to write, `Provenance.source_url` is
safe to render, and an exception's `repr()` has nothing to leak. Redaction stops being a
filter applied at each boundary and becomes a property of the type, the same way
`VerityConfig.snapshot()` is secret-free by construction rather than by scrubbing.

**Response headers are stored under an allowlist**, because a cache entry is written to
disk and committed as a fixture. The retained set is what the rate limiter, the credit
budget, and the pool assertion read, plus what an audit of a recorded fixture needs.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, model_validator

from verity.base import FrozenModel, VerityModel
from verity.models.common import CapRecord

#: Query parameters that carry, or look like they carry, a credential. `HttpRequest`
#: refuses a URL containing any of them, matched after case-folding and collapsing `-` to
#: `_`, so `api-key` and `API_KEY` are the same name. `mailto` is here for the same reason
#: as `api_key` even though it is only an address: it is `Secrets.crossref_mailto`, it
#: would otherwise land in cache paths and rendered provenance, and Crossref honours it in
#: the `User-Agent` instead.
#:
#: **This is a tripwire, not the guarantee.** A denylist cannot enumerate every name a
#: source might use. What actually keeps credentials off disk is that no model here has a
#: headers field at all and response headers are allowlisted at the transport boundary —
#: there is nowhere for a secret to be, so nothing has to be scrubbed. This catches a
#: construction site that reaches for the obvious spelling.
CREDENTIAL_PARAMS = frozenset(
    {"api_key", "apikey", "key", "token", "access_token", "mailto", "email"}
)

#: Response headers kept in a `Fetched` and therefore written to cache and fixtures.
#: Lowercased on the way in, since HTTP header case is not significant and two spellings
#: of one header would read as two headers.
RETAINED_RESPONSE_HEADERS = frozenset(
    {
        "content-type",
        "date",
        "retry-after",
        # OpenAlex: one meter, denominated in credits. `x-ratelimit-remaining` decrements
        # by exactly `x-ratelimit-credits-used` (verified live: a singleton costs 1, a
        # filtered list costs 10, and remaining fell by 10 across the pair), so these are
        # two views of one budget rather than a request meter and a credit meter.
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-credits-used",
        "x-ratelimit-reset",
        "x-ratelimit-cost-usd",
        "x-ratelimit-limit-usd",
        "x-ratelimit-remaining-usd",
        # Crossref: hyphenated differently, and advertised per response.
        "x-rate-limit-limit",
        "x-rate-limit-interval",
        "x-api-pool",
        "x-concurrency-limit",
    }
)


class CacheMode(StrEnum):
    """Where bytes may come from, and where they may go.

    Recorded per run rather than configured: a graph built entirely from fixtures is a
    different epistemic object from one built live, and for a recorded demo that
    difference has to be visible instead of inferred. It is deliberately *not* a
    `VerityConfig` field — it would enter `config_hash()` and invalidate every M1-T2 stage
    cache on a mode flip, when a stage's result should not depend on where the bytes came
    from.
    """

    #: Read the cache, fetch on a miss, write what comes back.
    LIVE = "live"
    #: `LIVE`, and also promote each entry into the committed fixture directory.
    RECORD = "record"
    #: Read only. A miss raises; the network is never touched.
    REPLAY = "replay"
    #: Ignore existing entries, fetch, overwrite.
    REFRESH = "refresh"

    @property
    def may_fetch(self) -> bool:
        return self is not CacheMode.REPLAY

    @property
    def may_read_cache(self) -> bool:
        return self is not CacheMode.REFRESH


class HttpRequest(FrozenModel):
    """One GET, described in terms the cache can key on and a human can read.

    `endpoint_class` is load-bearing rather than descriptive: it is the rate-limiter key.
    Crossref advertises different limits for different endpoints — a singleton `works/{doi}`
    reports 10/1s under pool `polite-single` while a `works?query…` list reports 3/1s under
    `polite-array` — and predicting the class from the call site, rather than discovering
    the pool from the response, is what keeps a limiter from having to bootstrap through an
    unknown pool on its first request.
    """

    url: str
    source: str  # "openalex" | "crossref"
    endpoint_class: str = "work"  # "work" | "list"
    #: What this shape of request is expected to cost, before the response says what it
    #: actually cost. Used only to refuse a request the budget cannot afford.
    credit_cost_hint: int = 1

    @model_validator(mode="after")
    def _url_carries_no_credential(self) -> HttpRequest:
        query = urlsplit(self.url).query
        if not query:
            return self
        present = {
            name.lower().replace("-", "_")
            for name in parse_qs(query, keep_blank_values=True)
        }
        offenders = sorted(CREDENTIAL_PARAMS.intersection(present))
        if offenders:
            raise ValueError(
                f"{self.source} request URL carries credential parameter(s) "
                f"{', '.join(offenders)}; both registries authenticate on headers, and a "
                "credential in a URL becomes a cache key, a filename, and a rendered "
                "source_url"
            )
        return self

    @property
    def limiter_key(self) -> tuple[str, str]:
        return (urlsplit(self.url).netloc, self.endpoint_class)


class Fetched(FrozenModel):
    """A response, from the network or from disk, with what it said about its own limits.

    `fetched_at` is the time the *network* answered. A cache hit replays the stored value
    rather than stamping `now()` — the whole of M5-T3's TTL re-validation reads this field
    to decide what is stale, and a cache that refreshed the clock on every read would make
    non-monotonic grounding undetectable while looking like it worked.
    """

    request: HttpRequest
    status: int
    body: str
    #: Lowercased and allowlisted. See `RETAINED_RESPONSE_HEADERS`.
    headers: dict[str, str] = Field(default_factory=dict)
    fetched_at: datetime
    from_cache: bool = False
    #: True when the request went out without a credential the source expects. A 404 under
    #: those conditions is not credibly "asked and absent" — it may be an anonymous pool
    #: refusing to look — so a degraded response is never cached as a negative entry.
    degraded: bool = False

    @model_validator(mode="after")
    def _fetch_time_carries_a_zone(self) -> Fetched:
        if self.fetched_at.tzinfo is None:
            raise ValueError(
                f"{self.request.source} response has a naive fetched_at "
                f"({self.fetched_at.isoformat()}); a fetch is a reading at a time in a zone"
            )
        return self

    @model_validator(mode="after")
    def _headers_are_lowercased_and_allowlisted(self) -> Fetched:
        for name in self.headers:
            if name != name.lower():
                raise ValueError(f"response header {name!r} is not lowercased")
            if name not in RETAINED_RESPONSE_HEADERS:
                raise ValueError(
                    f"response header {name!r} is not in the retained allowlist; a cache "
                    "entry is written to disk and committed as a fixture"
                )
        return self

    # -- what the response said about itself ---------------------------------------

    @property
    def found(self) -> bool:
        return self.status == 200

    @property
    def missing(self) -> bool:
        """Asked and absent. The only non-200 status that is a reading rather than a failure."""
        return self.status in (404, 410)

    @property
    def pool(self) -> str | None:
        return self.headers.get("x-api-pool")

    @property
    def retry_after_s(self) -> float | None:
        raw = self.headers.get("retry-after")
        try:
            return float(raw) if raw is not None else None
        except ValueError:  # HTTP-date form; back off on the schedule instead
            return None

    def _int(self, name: str) -> int | None:
        raw = self.headers.get(name)
        try:
            return int(raw) if raw is not None else None
        except ValueError:
            return None

    @property
    def credits_used(self) -> int | None:
        return self._int("x-ratelimit-credits-used")

    @property
    def credits_remaining(self) -> int | None:
        return self._int("x-ratelimit-remaining")

    @property
    def credit_limit(self) -> int | None:
        return self._int("x-ratelimit-limit")

    @property
    def advertised_rate(self) -> tuple[int, float] | None:
        """Crossref's `(limit, interval_seconds)`, when it advertised one."""
        limit = self._int("x-rate-limit-limit")
        interval = self.headers.get("x-rate-limit-interval")
        if limit is None or interval is None:
            return None
        try:
            seconds = float(interval.rstrip("s")) if interval.endswith("s") else float(interval)
        except ValueError:
            return None
        return (limit, seconds) if seconds > 0 else None

    def json(self) -> Any:
        return json.loads(self.body)

    def for_cache(self) -> Fetched:
        """The form written to disk: identical, except it is not itself a cache hit."""
        return self.model_copy(update={"from_cache": False})


class FetchLog(VerityModel):
    """Per-run retrieval counters and the bounds that actually bit.

    Mutable, because it is an accumulator the client writes to as a run proceeds — the one
    record here that is not a value object.

    The manifest seam. M6-T1a deliberately adds no field to any spine model — with four
    sessions in the tree at once, inventing a `StageRecord` field in parallel with the
    integration session is how a merge loses one. `caps` projects into the
    `list[CapRecord]` slot that already exists.
    """

    requests: int = 0
    cache_hits: int = 0
    network_calls: int = 0
    negative_hits: int = 0
    retries: int = 0
    retry_exhaustions: int = 0
    #: Requests abandoned because `Retry-After` exceeded the ceiling we are willing to wait.
    retry_after_refusals: int = 0
    budget_blocks: int = 0
    credits_spent: int = 0
    sleep_seconds: float = 0.0
    max_retries: int = 0
    credit_floor: int = 0
    max_retry_after_s: int = 0
    mode: CacheMode = CacheMode.LIVE

    @property
    def served_entirely_from_cache(self) -> bool:
        """Whether this run touched the network at all.

        A run in `LIVE` mode whose every identifier was already recorded issues no request,
        and calling that a live run in a demo writeup would be false. The mode says what was
        permitted; this says what happened.
        """
        return self.requests > 0 and self.network_calls == 0

    def caps(self) -> list[CapRecord]:
        """Every retrieval bound, applied or not. Evaluation §6: no silent caps."""
        return [
            CapRecord(
                name="retrieval_max_retries",
                limit=self.max_retries,
                applied=self.retry_exhaustions > 0,
                # A retry cap drops attempts nobody enumerated — the case `CapRecord`
                # admits `"uncounted"` for. What *is* countable is how many requests died
                # against it, and that is `retry_exhaustions`, reported beside this.
                dropped="uncounted" if self.retry_exhaustions > 0 else None,
            ),
            CapRecord(
                name="retrieval_retry_after_ceiling",
                limit=self.max_retry_after_s,
                applied=self.retry_after_refusals > 0,
                dropped=self.retry_after_refusals if self.retry_after_refusals > 0 else None,
            ),
            CapRecord(
                name="openalex_credit_floor",
                limit=self.credit_floor,
                applied=self.budget_blocks > 0,
                dropped=self.budget_blocks if self.budget_blocks > 0 else None,
            ),
        ]
