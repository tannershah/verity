"""Refusals.

The rule this module encodes is the mirror of the decomposition tier's: a scorer may
never return a number for a premise set other than the one it was given. Every refusal
here is a case where scoring anyway would produce a plausible float that measures a
different step than the one it would be stored on.

Each is a `VerifierError`, so `score_graph` isolates one bad step — leaving it unscored
and recording a `CapRecord` — instead of losing the graph.
"""

from __future__ import annotations


class VerifierError(RuntimeError):
    """Base: this (conclusion, premises) pair produced no storable score."""


class OversizeStepError(VerifierError):
    """The rendered input exceeds the checkpoint's input budget.

    Truncating would drop premises off the end of the document, and the resulting score
    would belong to a premise set nobody proposed. Refusing leaves the step unscored and
    the run says so, which is the reading evaluation.md §6 forces.

    The guard is explicit rather than delegated to the tokenizer. `truncation=True` is
    silent by construction, and T5's relative position embeddings mean the model will
    happily consume input past any nominal limit without raising — so a scorer that waited
    for an exception would never see one.
    """

    def __init__(self, message: str, *, tokens: int, limit: int) -> None:
        super().__init__(message)
        self.tokens = tokens
        self.limit = limit


class EmptyPremiseSetError(VerifierError):
    """No premises were supplied.

    M4-T2's leave-one-out on a one-premise step produces exactly this, and both candidate
    checkpoints will cheerfully score a claim against an empty document — returning the
    model's prior on the conclusion, which is the one quantity this tier must never emit as
    an entailment score.
    """


class DuplicatePremiseError(VerifierError):
    """The same premise was supplied twice.

    `EntailmentStep` refuses a step that lists a premise twice, so this can only arrive
    from a hand-assembled call. Deduplicating would be entailment-preserving but would
    silently score a different arity than the caller believes it passed.
    """


class LabelOrderUnverifiedError(VerifierError):
    """The checkpoint's label conventions did not survive verification at init.

    Never a warning. A checkpoint whose head is permuted relative to what its config
    declares produces confident scores with the sign inverted, and nothing downstream can
    detect it — the number is in range, the calibration label is honest, and every
    consumer reads it as an entailment score.
    """
