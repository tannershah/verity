"""M4 — entailment scoring.

Writes `Score` onto `EntailmentStep`, and leave-one-out `AblationDelta`s onto the same
step keyed by the premise removed. Both are step-scoped: a premise reached from two steps
is scored twice and ablated twice, and either number stored on the node would be the one
whichever step ran last happened to produce.

**T1 writes scores only.** Ablation is M4-T2; the `StepScorer` interface is shaped so that
tier is a premise-subset call against the same scorer rather than a second scorer.

Importing this package costs nothing on a machine with no ML stack — the backends import
torch inside their constructors, so only building a real scorer needs the `verifier` extra.
`ScriptedScorer` needs neither, which is what keeps the test suite offline.
"""

from verity.verifier.base import (
    RECIPE_ID,
    SCORE_DECIMALS,
    ScorerSpec,
    StepScorer,
    canonical_order,
    render_document,
)
from verity.verifier.errors import (
    DuplicatePremiseError,
    EmptyPremiseSetError,
    LabelOrderUnverifiedError,
    OversizeStepError,
    VerifierError,
)
from verity.verifier.registry import (
    BACKENDS,
    UnknownCheckpointError,
    build_scorer,
)
from verity.verifier.scoring import PURPOSE, ScoringResult, passes_gate, score_graph
from verity.verifier.smoke_set import SmokeCase, load_smoke_set
from verity.verifier.stub import ScriptedScorer

__all__ = [
    "BACKENDS",
    "PURPOSE",
    "RECIPE_ID",
    "SCORE_DECIMALS",
    "DuplicatePremiseError",
    "EmptyPremiseSetError",
    "LabelOrderUnverifiedError",
    "OversizeStepError",
    "ScorerSpec",
    "ScoringResult",
    "ScriptedScorer",
    "SmokeCase",
    "StepScorer",
    "UnknownCheckpointError",
    "VerifierError",
    "build_scorer",
    "canonical_order",
    "load_smoke_set",
    "passes_gate",
    "render_document",
    "score_graph",
]
