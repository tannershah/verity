"""The scorer interface, its identity, and the input recipe.

**The recipe is the mechanism worth arguing about.** Off-the-shelf entailment models have
no native "N premises jointly entail C" input format, so the premises are concatenated
into one document. That is a workaround, not a validated multi-premise architecture — it
is distribution-shifted twice on our steps, and build-plan.md §6 names it the weakest
scientific link in the project. M4-T2's hand-labeled sanity check and M4-T3's ROC are the
guards; nothing here should be read as evidence the workaround is sound.

**What we do control is that the workaround is deterministic and order-invariant.**
design.md §4.3 settles that a step's identity is its conclusion and the *set* of its
premises, so the same decomposition emitted in a different order is the same step. If the
document followed the order premises were proposed in, one step id would carry two
different scores across two runs, and M1-T2's replay would hand back a graph whose numbers
moved with nothing recorded to explain it. So `render_document` sorts, and it sorts by the
same derived premise id that `EntailmentStep` sorts by — which is why it can recompute
those ids from text alone rather than requiring a caller to pass them in the right order.
A caller cannot get the order wrong, because a caller does not choose it.

**Identity travels with the number.** `ScorerSpec.scorer_id` goes into `Score.scorer`, and
it names the checkpoint, its resolved commit, the recipe version, and — loudly — whether
label-order verification was skipped. A stored graph read without its run manifest must
still be able to say what produced its numbers and whether that producer's conventions were
ever confirmed; a checkpoint name alone answers neither question.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from verity.base import FrozenModel
from verity.ids import make_id
from verity.models.common import Score
from verity.verifier.errors import DuplicatePremiseError, EmptyPremiseSetError

#: Version of the input recipe below. Travels in `ScorerSpec.scorer_id` and therefore into
#: every stored `Score`, so changing how the document is built invalidates rather than
#: silently re-interprets the numbers already on disk.
RECIPE_ID = "concat-v1"

#: Stored scores are rounded to this many decimals. A score whose seventh decimal
#: reproduces across torch builds, devices, and BLAS backends is not a claim this project
#: can make, and rounding is the honest way to stop making it. It also keeps M1-T2's
#: byte-equality replay check from failing on float noise.
SCORE_DECIMALS = 4


class ScorerSpec(FrozenModel):
    """What produced a score, in enough detail to reproduce or supersede it."""

    checkpoint: str
    #: Resolved commit on the model hub. A checkpoint name without one is not a
    #: reproducible scorer: the same id can serve different weights a month apart.
    revision: str
    recipe: str = RECIPE_ID
    max_input_tokens: int
    device: str = "cpu"
    #: False only when `VerifierConfig.verify_label_order_at_init` was turned off. It is
    #: surfaced in `scorer_id` rather than kept here alone, so the scores themselves carry
    #: the warning into any artifact that holds them.
    label_order_verified: bool = True

    @property
    def scorer_id(self) -> str:
        """The string written to `Score.scorer`."""
        base = f"{self.checkpoint}@{self.revision[:7]}+{self.recipe}"
        return base if self.label_order_verified else f"{base}+label-order-unverified"


@runtime_checkable
class StepScorer(Protocol):
    """Scores one entailment step. Knows nothing about graphs.

    Graph-agnostic on purpose: M4-T2's leave-one-out calls this with a premise subset, and
    M3-T3's verifier-guided search calls it on candidate decompositions that are not in any
    graph yet.
    """

    spec: ScorerSpec

    def score(self, conclusion: str, premises: Sequence[str]) -> Score:
        """The probability that `premises` jointly entail `conclusion`."""
        ...


def canonical_order(premises: Sequence[str]) -> list[str]:
    """Premise texts in the order step identity is derived from.

    Sorted by the premise id each text derives — the same key `EntailmentStep` sorts by —
    so the document a scorer sees is a function of the premise *set* and nothing else.
    Recomputing the id from text is exact rather than approximate: `Premise` derives its id
    from its text and nothing else, so this reproduces the id the node would have.
    """
    if not premises:
        raise EmptyPremiseSetError(
            "no premises to score; a conclusion scored against an empty document returns "
            "the model's prior on the conclusion, not an entailment measurement"
        )
    keyed = [(make_id("prem", text), text) for text in premises]
    seen: dict[str, str] = {}
    for premise_id, text in keyed:
        if premise_id in seen:
            raise DuplicatePremiseError(
                f"premise supplied twice, so the arity scored is not the arity passed: {text!r}"
            )
        seen[premise_id] = text
    return [text for _, text in sorted(keyed)]


def render_document(premises: Sequence[str]) -> str:
    """The premise side of the scorer input: one canonical premise per line."""
    return "\n".join(canonical_order(premises))


def build_score(value: float, spec: ScorerSpec) -> Score:
    """A rounded, uncalibrated `Score` stamped with the scorer's full identity.

    Calibration is left at its default because nothing here has a basis to claim
    otherwise — evaluation.md §6's standing rule, and `Score` refuses a calibrated score
    with no recorded basis anyway.
    """
    return Score(value=round(value, SCORE_DECIMALS), scorer=spec.scorer_id)
