"""The wire. The only module in Verity that opens a socket.

Stdlib `urllib` behind a one-method protocol rather than a third-party client: requests are
sequential and rate-limited to single-digit req/s, so connection pooling buys nothing we
can measure, retries and backoff are ours either way, and the protocol is what tests and
the fixture harness substitute. Swapping in `httpx` later is this one file.

**A status is data; a dead connection is not.** An HTTP error response is returned like any
other — 404, 429 and 5xx all mean something specific upstream, and deciding what is the
client's job, not the socket's. Only a request that never produced a status raises.
"""

from __future__ import annotations

import http.client
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Protocol

from verity.base import FrozenModel
from verity.retrieval.errors import TransportError
from verity.retrieval.http._model import RETAINED_RESPONSE_HEADERS


class RawResponse(FrozenModel):
    """What came back, before anything interprets it."""

    status: int
    body: str
    headers: dict[str, str]


class Transport(Protocol):
    def send(self, url: str, headers: Mapping[str, str], timeout_s: float) -> RawResponse: ...


def retained(headers: object) -> dict[str, str]:
    """Lowercase and allowlist response headers. The redaction boundary for what we store."""
    items = headers.items() if hasattr(headers, "items") else headers  # type: ignore[union-attr]
    return {
        name.lower(): value
        for name, value in items  # type: ignore[union-attr]
        if name.lower() in RETAINED_RESPONSE_HEADERS
    }


class UrllibTransport:
    """`urllib.request` with a timeout and no other opinions."""

    def send(self, url: str, headers: Mapping[str, str], timeout_s: float) -> RawResponse:
        request = urllib.request.Request(url, headers=dict(headers))
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                body = response.read().decode("utf-8", errors="replace")
                return RawResponse(
                    status=response.status, body=body, headers=retained(response.headers)
                )
        except urllib.error.HTTPError as exc:
            # A status is an answer. 404 is a reading, 429 and 5xx are retryable, and the
            # client owns both decisions — swallowing them here would make an absent work
            # and an overloaded server indistinguishable.
            body = exc.read().decode("utf-8", errors="replace")
            return RawResponse(status=exc.code, body=body, headers=retained(exc.headers))
        except urllib.error.URLError as exc:
            raise TransportError(f"{url} did not complete: {exc.reason}") from exc
        except http.client.HTTPException as exc:
            # `IncompleteRead`, `BadStatusLine` and `LineTooLong` derive from
            # `HTTPException`, not `OSError`, so they escaped a `(TimeoutError, OSError)`
            # clause entirely — and a truncated body on the wire is the most retryable
            # condition there is. Escaping meant it was neither retried nor typed, and
            # propagated raw out of `get()` past a retry loop that only catches
            # `TransportError`.
            name = type(exc).__name__
            raise TransportError(f"{url} did not complete: {name}: {exc}") from exc
        except (TimeoutError, OSError) as exc:
            raise TransportError(f"{url} did not complete: {exc}") from exc
