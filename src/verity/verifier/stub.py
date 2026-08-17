"""Deterministic scorer for tests and offline development.

Scripted by (conclusion, premise set) so a test says what a step should score rather than
depending on a checkpoint being present. The identity is unmistakable — every score it
produces is stamped `stub-scripted`, and a `ScorerSpec` whose checkpoint reads `stub-*`
cannot be mistaken for a model's output in a stored graph, a run manifest, or a screenshot,
however far the artifact travels from the test that made it.

Missing scripts raise rather than returning a default: a scorer that quietly answers 0.5
for an unscripted step is the failure mode that makes a broken pipeline look like a
working one.
"""

from __future__ import annotations

from collections.abc import Sequence

from verity.ids import content_hash
from verity.models.common import Score
from verity.verifier.base import ScorerSpec, build_score, canonical_order
from verity.verifier.errors import OversizeStepError, VerifierError

#: Wide enough that no test trips the oversize guard by accident, small enough that a test
#: can trip it on purpose with a plausible premise set.
STUB_MAX_INPUT_TOKENS = 512


class ScriptedScorer:
    """A `StepScorer` returning pre-scripted values, keyed by step content."""

    def __init__(
        self,
        scores: dict[str, float] | None = None,
        *,
        default: float | None = None,
        max_input_tokens: int = STUB_MAX_INPUT_TOKENS,
    ) -> None:
        self._scores = scores or {}
        self._default = default
        self.spec = ScorerSpec(
            checkpoint="stub-scripted",
            revision="0" * 40,
            max_input_tokens=max_input_tokens,
            device="cpu",
        )
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    @staticmethod
    def key(conclusion: str, premises: Sequence[str]) -> str:
        """Content key for a step, over the canonical premise order.

        Keyed on the premise *set* rather than the sequence, so a test that reorders a
        step's premises hits the same script — which is what lets the order-invariance
        test observe the scorer's own behaviour instead of the stub's.
        """
        return content_hash(conclusion, canonical_order(premises))

    def score(self, conclusion: str, premises: Sequence[str]) -> Score:
        ordered = canonical_order(premises)
        self.calls.append((conclusion, tuple(ordered)))

        # Crude but sufficient: the real backends count model tokens, and a whitespace
        # count is monotone in that, which is all the oversize path needs to be exercised.
        tokens = len(" ".join([*ordered, conclusion]).split())
        if tokens > self.spec.max_input_tokens:
            raise OversizeStepError(
                f"scripted step is {tokens} words against a limit of "
                f"{self.spec.max_input_tokens}",
                tokens=tokens,
                limit=self.spec.max_input_tokens,
            )

        key = self.key(conclusion, ordered)
        if key in self._scores:
            return build_score(self._scores[key], self.spec)
        if self._default is not None:
            return build_score(self._default, self.spec)
        raise VerifierError(
            f"ScriptedScorer has no score for conclusion {conclusion[:60]!r} with "
            f"{len(ordered)} premises; script it or pass a default"
        )
