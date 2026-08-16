"""Refusals.

The split this module encodes is the tier's central rule:

    A drop is permitted only when it is entailment-preserving. Anything that changes
    what the step asserts is a refusal, not a repair.

Deduplicating an exact duplicate (`P ∧ P ≡ P`), dropping a premise that asserts nothing,
and discarding a malformed candidate key all leave the step asserting what the decomposer
proposed, so they are recorded and the run continues. Everything here would leave a step
the decomposer never proposed — which M4 would then score and M10-T1 would then report as
a measurement of the decomposer rather than of our repair.

Each is a `DecompositionError`, so a batch runner isolates one bad claim instead of losing
the run (M1-T2 owns that isolation; these are what it catches).
"""

from __future__ import annotations

from verity.models.manifest import Usage


class DecompositionError(RuntimeError):
    """Base: this conclusion produced no storable step.

    Carries the `usage` of the call that produced the refusal, because every refusal here
    except the depth budget happens *after* the model has answered and been paid for. A
    descent that refuses several steps and reports only the cost of the ones it kept
    under-reports itself, and cost is a pre-registered number. `None` means no call was
    made, which is a different fact from a call that cost nothing.
    """

    def __init__(self, *args: object, usage: Usage | None = None) -> None:
        super().__init__(*args)
        self.usage = usage


class EmptyDecompositionError(DecompositionError):
    """Nothing survived materialization.

    `EntailmentStep` refuses a premise-less step anyway; refusing here says which of the
    two things happened — the model returned nothing, or everything it returned was
    dropped as empty or duplicate.
    """


class TruncatedDecompositionError(DecompositionError):
    """The call stopped on `max_tokens`.

    A truncated structured response still validates: three premises where seven were
    being written parse cleanly. Storing that would put a fact about `max_tokens` into
    the arity distribution and the grounding-rate denominator, where it reads as a fact
    about the decomposer.
    """


class CyclicPremiseError(DecompositionError):
    """A premise restates its conclusion or an ancestor, so the step rests on itself.

    Keeping it loses the whole tree where `ClaimGraph`'s cycle check catches it; dropping
    it changes what the step asserts. Neither is T1's call to make — the descent (M3-T2)
    owns what a branch does when it cannot go further, because it owns termination
    reasons.

    Judged on statements rather than ids, so it also refuses the variants the graph would
    accept: a premise differing from its conclusion only in case is one statement by this
    codebase's own definition, and a step resting on its own conclusion is circular
    whether or not the id-level check happens to see it.
    """


class DepthBudgetExceededError(DecompositionError):
    """A step was requested, or assembled, at or beyond the depth budget.

    Enforced at the producer because that is the only place it *can* be enforced: the
    budget is spent along the descent, and a graph assembled after the fact can only
    report the depth it was given. Re-checked at assembly because a graph records the
    budget it claims to have been built under, and steps produced under a different one
    would make that record false. A step at descent `d` puts its premises at `d + 1`, so
    the deepest legal step is `depth_budget - 1` and `recorded_depth()` tops out at the
    budget — which is the relation `tests/test_downstream_contracts.py` asserts.
    """
