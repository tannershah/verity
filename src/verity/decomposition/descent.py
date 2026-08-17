"""Claim → the steps that decompose it. One step today; a descent under M3-T2.

The seam exists so the orchestrator never learns the difference. M1-T2's decompose stage
calls this, assembles what comes back, and caches on a key that does not mention how many
calls were made — so M3-T2 lands as a change to this function's body and to nothing else.

**T1 records no termination reasons, deliberately.** build-plan.md M3-T1: "Termination
reasons are M3-T2's alone. A single step is not a descent, so T1 records none rather than
asserting a decision nothing made." An orchestrator that filled them in would put numbers
in the termination mix M10-T1 reports that no tier produced.

Three things M3-T2 owns that are visible from here and have no answer yet:

- **A refused branch has no `TerminationReason`.** `CyclicPremiseError` refuses rather than
  repairing, and the vocabulary has no value for "the decomposer proposed something
  circular here". Inventing one is a measurement decision, not a plumbing one.
- **`TerminationReason.GROUNDED` is unreachable** under `decompose → verify → bind →
  ground`, because nothing is bound while the descent is running: the binder runs after it.
  Either the descent gains a grounding check (which needs M6-T3's key attribution to be
  worth anything), or the run reports that the value is structurally unreachable rather
  than letting it read as "no branch grounded".
- **Cross-branch cycles and double decomposition are caught at assembly**, by
  `ClaimGraph`, after every call in the tree has been paid for. The check belongs inside
  the descent, before payment. Until it is there, such a graph raises out of this function
  and the run reports it — cheaply on a retry, because the cassette holds the calls.
"""

from __future__ import annotations

from datetime import datetime

from verity.config import DecompositionConfig
from verity.decomposition.backward_chain import (
    DecomposedStep,
    DecompositionContext,
    decompose_step,
)
from verity.llm.base import LLMAdapter
from verity.models.claim import Claim


def decompose_claim(
    claim: Claim,
    *,
    adapter: LLMAdapter,
    config: DecompositionConfig,
    now: datetime | None = None,
) -> list[DecomposedStep]:
    """Decompose `claim` into the steps a graph is assembled from.

    Returns steps in the order they were produced, which is display order; step identity
    sorts its premises, so order never changes what a step *is*.

    Raises `DecompositionError` — the caller isolates it and records the cost of the call
    that produced it, since a branch that spends money and yields no step still counts
    against the run.
    """
    step = decompose_step(
        claim,
        adapter=adapter,
        config=config,
        depth=0,
        context=DecompositionContext(root_claim=claim),
        now=now,
    )
    return [step]
