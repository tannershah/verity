"""M3 — backward-chaining decomposition. Consumes `Claim`, produces `EntailmentStep`s.

`decompose_step` is the recursion step: it takes a `Claim` or a `Premise` as its
conclusion and records the descent depth it was called at, so M3-T2's descent drives it
unchanged. `assemble_graph` merges the steps a descent produced into one `ClaimGraph`.

The prompt lives in `prompt` and nothing else in the package reads it, so a rewrite
touches one file. Its text is digested into every stage's input hash, which is what stops
a rewritten prompt from being served the previous prompt's cached decompositions.
"""

from verity.decomposition.backward_chain import (
    PURPOSE,
    Conclusion,
    DecomposedStep,
    DecompositionContext,
    assemble_graph,
    decompose_step,
    normalize_display_text,
)
from verity.decomposition.errors import (
    CyclicPremiseError,
    DecompositionError,
    DepthBudgetExceededError,
    EmptyDecompositionError,
    TruncatedDecompositionError,
)
from verity.decomposition.schema import ProposedDecomposition, ProposedPremise

__all__ = [
    "PURPOSE",
    "Conclusion",
    "CyclicPremiseError",
    "DecomposedStep",
    "DecompositionContext",
    "DecompositionError",
    "DepthBudgetExceededError",
    "EmptyDecompositionError",
    "ProposedDecomposition",
    "ProposedPremise",
    "TruncatedDecompositionError",
    "assemble_graph",
    "decompose_step",
    "normalize_display_text",
]
