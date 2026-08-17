"""DeBERTa-v3-large NLI backend.

Scores P(entailment) over the 3-class head, with the concatenated premises as the NLI
premise and the step's conclusion as the hypothesis.

**Raw P(entailment), not renormalized against contradiction.** Dividing entailment by
(entailment + contradiction) would fold `neutral` away, and `neutral` is the single most
informative outcome this checkpoint produces on our inputs: a decomposition whose premises
are topically right and jointly insufficient lands there, and that is exactly the step
M4-T2 needs to see as weak rather than as merely unrefuted.

torch and transformers are imported inside `__init__` so that importing this module — and
therefore `verity.verifier` — costs nothing on a machine with no ML stack. Only building a
real scorer requires the `verifier` extra.
"""

from __future__ import annotations

from collections.abc import Sequence

from verity.config import VerifierConfig
from verity.models.common import Score
from verity.verifier import probes
from verity.verifier.base import ScorerSpec, build_score, render_document
from verity.verifier.errors import LabelOrderUnverifiedError, OversizeStepError
from verity.verifier.registry import resolve_checkpoint, resolve_revision

#: The three labels this head must declare, lowercased. A checkpoint in this family that
#: declares anything else is not the model this backend was written against.
_EXPECTED_LABELS = frozenset({"entailment", "neutral", "contradiction"})


class NliScorer:
    """`StepScorer` over a 3-class NLI checkpoint."""

    def __init__(self, config: VerifierConfig, *, checkpoint: str | None = None) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        checkpoint = resolve_checkpoint(config, type(self), checkpoint)
        revision = resolve_revision(config, checkpoint)

        self._tokenizer = AutoTokenizer.from_pretrained(checkpoint, revision=revision)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            checkpoint, revision=revision
        )
        self._model.eval()
        self._model.to(config.device)

        self._entailment_index = self._resolve_entailment_index()

        # The tokenizer's nominal maximum and the model's positional capacity are separate
        # numbers and either can be the binding one; the smaller is the only safe budget.
        limit = min(
            int(self._model.config.max_position_embeddings),
            int(self._tokenizer.model_max_length),
        )

        self.spec = ScorerSpec(
            checkpoint=checkpoint,
            revision=str(getattr(self._model.config, "_commit_hash", None) or revision),
            max_input_tokens=limit,
            device=config.device,
            label_order_verified=config.verify_label_order_at_init,
        )

        if config.verify_label_order_at_init:
            self._verify_label_order()

    def _resolve_entailment_index(self) -> int:
        """Which logit is entailment, read off the config rather than assumed to be 0."""
        id2label = {
            int(i): str(label).lower() for i, label in self._model.config.id2label.items()
        }
        if set(id2label.values()) != _EXPECTED_LABELS:
            raise LabelOrderUnverifiedError(
                f"checkpoint declares labels {sorted(id2label.values())}, expected "
                f"{sorted(_EXPECTED_LABELS)}; this backend cannot say which logit is "
                "entailment"
            )
        return next(i for i, label in id2label.items() if label == "entailment")

    def _verify_label_order(self) -> None:
        """Assert the declared head is the actual head, and the input slots are right.

        Hard failure, never a warning.
        """
        for premise, hypothesis in probes.ENTAILED:
            for negative_premise, negative_hypothesis in probes.CONTRADICTED:
                high = self._entailment_probability(premise, hypothesis)
                low = self._entailment_probability(negative_premise, negative_hypothesis)
                if not high > low:
                    raise LabelOrderUnverifiedError(
                        f"entailed probe scored {high:.4f} and contradicted probe scored "
                        f"{low:.4f}; logit {self._entailment_index} is not entailment, and "
                        "every score this scorer produced would be confidently inverted"
                    )
        for hypothesis, supporting, opposing in probes.SHARED_HYPOTHESIS:
            high = self._entailment_probability(supporting, hypothesis)
            low = self._entailment_probability(opposing, hypothesis)
            if not high > low:
                raise LabelOrderUnverifiedError(
                    f"two documents sharing one hypothesis scored {high:.4f} and "
                    f"{low:.4f}; the premises are not reaching the document slot, so the "
                    "score is not a function of what this step rests on"
                )

    def _entailment_probability(self, document: str, conclusion: str) -> float:
        encoded = self._tokenizer(document, conclusion, return_tensors="pt", truncation=False)
        tokens = int(encoded["input_ids"].shape[-1])
        if tokens > self.spec.max_input_tokens:
            raise OversizeStepError(
                f"rendered step is {tokens} tokens against a limit of "
                f"{self.spec.max_input_tokens}; truncating would drop premises off the end "
                "and score a premise set nobody proposed",
                tokens=tokens,
                limit=self.spec.max_input_tokens,
            )
        encoded = {k: v.to(self.spec.device) for k, v in encoded.items()}
        # One forward pass per step, batch size one. Padding changes logits, so a later
        # performance pass that batched would silently move every number in every stored
        # graph with the config hash unmoved; `tests/test_verifier_gate.py` pins this.
        with self._torch.no_grad():
            logits = self._model(**encoded).logits[0]
        return float(self._torch.softmax(logits, dim=-1)[self._entailment_index].item())

    def score(self, conclusion: str, premises: Sequence[str]) -> Score:
        value = self._entailment_probability(render_document(premises), conclusion)
        return build_score(value, self.spec)
