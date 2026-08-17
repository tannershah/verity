"""Cached, rate-limited, retrying HTTP — the layer every M6 client is built on.

The disk cache is mandatory rather than an optimization (OpenAlex spends credits per
request, including on a 404), and the fixture store is the same format in a committed
directory, which is what makes the client suite offline and deterministic.

Four invariants this layer exists to hold, each with a test:

- no credential ever enters a URL (`HttpRequest` refuses one that does);
- a cache hit replays the original fetch time and acquires no limiter;
- a configured credential that did not reach its pool is a loud error, not a log line;
- a 404 is a reading, and everything else that goes wrong is an exception.
"""

from __future__ import annotations

from verity.retrieval.http._cache import FOUND, MISSING, HttpCache, entry_digest
from verity.retrieval.http._client import FIXTURE_ROOT, HttpClient, build_client
from verity.retrieval.http._clock import Clock, ManualClock, SystemClock
from verity.retrieval.http._credentials import (
    ANONYMOUS_OPENALEX_CEILING,
    Credential,
    CrossrefCredential,
    NoCredential,
    OpenAlexCredential,
)
from verity.retrieval.http._limits import CreditBudget, LimiterSet, PoolLimiter
from verity.retrieval.http._model import (
    CREDENTIAL_PARAMS,
    RETAINED_RESPONSE_HEADERS,
    CacheMode,
    Fetched,
    FetchLog,
    HttpRequest,
)
from verity.retrieval.http._transport import RawResponse, Transport, UrllibTransport

__all__ = [
    "ANONYMOUS_OPENALEX_CEILING",
    "CREDENTIAL_PARAMS",
    "FIXTURE_ROOT",
    "FOUND",
    "MISSING",
    "RETAINED_RESPONSE_HEADERS",
    "CacheMode",
    "Clock",
    "CreditBudget",
    "Credential",
    "CrossrefCredential",
    "FetchLog",
    "Fetched",
    "HttpCache",
    "HttpClient",
    "HttpRequest",
    "LimiterSet",
    "ManualClock",
    "NoCredential",
    "OpenAlexCredential",
    "PoolLimiter",
    "RawResponse",
    "SystemClock",
    "Transport",
    "UrllibTransport",
    "build_client",
    "entry_digest",
]
