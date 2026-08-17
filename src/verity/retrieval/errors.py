"""Failures the retrieval layer raises, and the one outcome that is not a failure.

**An absent work is data; everything else is an error or an unanswered reading.** A 404 to
a properly credentialed request means a source was asked and had no record — that is
`ReadingOutcome.ABSENT`, and the only negative a policy may treat as evidence. A timeout, a
500, an exhausted retry budget, a spent credit budget, or a request that reached the wrong
rate-limit pool are *not* readings, and they raise from here. Between the two sits
`ReadingOutcome.UNANSWERED`, for a question nothing was in a position to answer: a source
that does not index this kind of identifier, or a 404 whose request went out degraded.

All three lines exist for one reason. The seed gate reads "resolves in no source consulted"
as grounds to abort a row, and the binder reads it as grounds to refuse a key — so a
transport failure, or a registry that was never asked, quietly rendered as a miss would
delete curated facts and refuse real identifiers. This is
`RetractionFinding.NOT_INDEXED` against `CLEAN`, one layer down and for the same reason.

Every error here carries only the redacted request descriptor, never headers — credentials
live in `_credentials` and are applied at the transport boundary, so there is nothing in an
exception's `str()` or `repr()` to leak.
"""

from __future__ import annotations


class RetrievalError(RuntimeError):
    """Base class for every failure in M6."""


class TransportError(RetrievalError):
    """The request did not complete, or completed with a status nothing can read."""


class RateLimitedError(RetrievalError):
    """A source returned 429 and the retry budget was exhausted."""


class BudgetExhaustedError(RetrievalError):
    """The credit budget fell below its configured floor, so nothing more was spent."""


class DegradedCredentialError(RetrievalError):
    """A configured credential did not reach the pool it pays for.

    Header authentication fails *open*: a renamed, revoked, or dropped credential does not
    produce a 401 — the request succeeds against the anonymous pool and spends a shared
    budget until something unrelated breaks. The pool is therefore asserted on every
    response rather than assumed from the fact that a key was configured.
    """


class MalformedResponseError(RetrievalError):
    """A source answered 200 with something its own schema does not describe.

    Distinct from a 404, and the distinction is the whole point: a payload that will not
    parse is a broken contract, not a work the source has never heard of. Reading it as
    `found=False` would turn a registry schema change into a silent, corpus-wide demotion —
    every seed row keyed to that source drops a tier, and the load report says the
    identifiers stopped resolving.
    """


class UnreachableReadingError(RetrievalError):
    """An unreachable reading was asked to become a record that cannot express it.

    The committed resolution artifact stores `found` as a boolean, and the seed gate reads
    a resolution with nothing found as grounds to delete the row. So a reading from a source
    that could have answered and did not has no honest projection into that schema, and
    saying so is better than writing a `False` that means something else.
    """


class CacheMissError(RetrievalError):
    """Replay mode was asked for something no cache or fixture holds.

    Replay never falls through to the network — a mode whose failure mode is "spend real
    credits" is not a replay mode.
    """
