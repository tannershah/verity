"""Applying the grounding decision to a whole graph.

`grounding.py` decides one premise; `service.py` reads the store. This is the third piece:
writing what those two concluded onto a `ClaimGraph`. It lives in its own module because it
needs both, and `grounding.py` importing the service would close a cycle.

**This is the only thing in the codebase that writes `EvidenceState.VERIFIED`**, and
design.md §4.2 pins that state to exactly one cause — exact-key grounding in a fact that is
IN and in an eligible tier. Nothing else is upgraded: a premise with evidence and no
grounding stays `unverified`, which is all a bundle can support. M6-T3 owns evidence state
once it lands; M8-T3 replaces the provisional flag.

**A re-confirmed grounding does not restamp itself.** `grounded_at` records when a
grounding was *reached*, and re-running against an unchanged alethiology reaches no new
conclusion — so an unchanged (premise, fact, matched key) triple keeps the timestamp it
already had. This is the same argument `HttpCache` makes for not refreshing `fetched_at` on
a cache hit, pointed the other way: there nothing was read, here nothing was concluded.
Where "when did we last look" lives is already settled — `RenderPayload.checked_at`, written
at render time, plus the stage record of the run that looked.

Without that rule the whole byte-identity claim collapses: the grounding stage is never
cached, so a second run of an unchanged claim would stamp a fresh time into the artifact
and every downstream comparison would report a change that did not happen.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from verity.alethiology.grounding import GroundingAttempt
from verity.alethiology.service import Alethiology
from verity.models.claim import ClaimGraph, Grounding
from verity.models.common import EvidenceState


def _triple(grounding: Grounding) -> tuple[str, str, str]:
    return (grounding.premise_id, grounding.fact_id, str(grounding.matched_key))


def apply_groundings(
    graph: ClaimGraph,
    service: Alethiology,
    *,
    grounded_at: datetime | None = None,
    preserve_from: Iterable[Grounding] = (),
) -> tuple[ClaimGraph, list[GroundingAttempt]]:
    """Ground every premise that carries a bound key, and record what grounded.

    `preserve_from` is the previously stored graph's groundings. A new row whose
    (premise, fact, matched key) triple appears there keeps that row's `grounded_at`;
    anything else is stamped now.

    Rows come back sorted by premise id. `ClaimGraph.grounding_for` takes the first match,
    so a stable order is what keeps two runs of one claim from producing two orderings of
    one set — which, once some rows are preserved and others stamped, no longer falls out
    of insertion order.

    Returns a rebuilt graph rather than a mutated one, so construction re-runs every
    invariant — including the one that refuses `verified` without a grounding.
    """
    attempts = service.ground_all(graph.premises.values(), grounded_at=grounded_at)
    grounded = {a.premise_id: a.grounding for a in attempts if a.grounding is not None}
    if not grounded:
        return graph, attempts

    previous = {_triple(g): g for g in preserve_from}
    rows = [previous.get(_triple(g), g) for g in grounded.values()]
    kept = [g for g in graph.groundings if g.premise_id not in grounded]

    premises = {
        pid: (
            premise.model_copy(
                update={
                    "evidence_state": EvidenceState.VERIFIED,
                    "evidence_state_provisional": True,
                }
            )
            if pid in grounded
            else premise
        )
        for pid, premise in graph.premises.items()
    }
    rebuilt = ClaimGraph(
        root_claim=graph.root_claim,
        premises=premises,
        steps=graph.steps,
        groundings=sorted([*kept, *rows], key=lambda g: g.premise_id),
        bundles=graph.bundles,
        metadata=graph.metadata,
    )
    return rebuilt, attempts
