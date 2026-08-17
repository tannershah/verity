"""MiniCheck-Flan-T5-Large backend.

**This checkpoint is not a classifier.** It is a `T5ForConditionalGeneration` fine-tuned to
emit the single character `1` when a document supports a claim and `0` when it does not.
Scoring is one forward pass with a one-token decoder input, reading the position-0 logits
for those two tokens and softmaxing over just that pair.

**The label token ids are derived, not copied.** The reference implementation hardcodes
`logits[:, torch.tensor([3, 209])]` with the comment "3 for no support and 209 for
support" and no further explanation. Verified against the tokenizer: `encode("0")` is
`[3, 632, 1]` and `encode("1")` is `[209, 1]`, so 3 is the *first token of* "0" and 209 is
"1" — the constants are right, and they are the first-token-of-the-label rule rather than
two magic numbers. Deriving them means a re-tokenized release of this checkpoint moves the
ids and this code follows, instead of reading two unrelated logits with total confidence.

**Two deviations from the reference implementation, both recorded.** It chunks long
documents and takes the maximum support probability across chunks; we refuse oversize
input instead, because max-over-subsets is monotonically at least the joint score and
would blunt exactly the non-redundancy signal M4-T2 measures. And its nominal input budget
is 2048 rather than the tokenizer's advertised 512, since T5's relative position
embeddings carry past the latter. Consequence to carry into any comparison: **published
MiniCheck numbers do not describe this recipe.**
"""

from __future__ import annotations

from collections.abc import Sequence

from verity.config import VerifierConfig
from verity.models.common import Score
from verity.verifier import probes
from verity.verifier.base import ScorerSpec, build_score, render_document
from verity.verifier.errors import LabelOrderUnverifiedError, OversizeStepError
from verity.verifier.registry import resolve_checkpoint, resolve_revision

#: The reference implementation's `max_input_length`. Stated here rather than read from
#: the tokenizer, whose advertised 512 is a Flan-T5 default this checkpoint's own inference
#: code overrides — and which T5's relative position embeddings do not enforce, so a scorer
#: waiting for the model to complain about a long input would wait forever.
REFERENCE_MAX_INPUT_TOKENS = 2048


class MiniCheckScorer:
    """`StepScorer` over MiniCheck's binary support head."""

    def __init__(self, config: VerifierConfig, *, checkpoint: str | None = None) -> None:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self._torch = torch
        checkpoint = resolve_checkpoint(config, type(self), checkpoint)
        revision = resolve_revision(config, checkpoint)

        self._tokenizer = AutoTokenizer.from_pretrained(checkpoint, revision=revision)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(checkpoint, revision=revision)
        self._model.eval()
        self._model.to(config.device)

        self._no_support_id, self._support_id = self._resolve_label_tokens()

        self.spec = ScorerSpec(
            checkpoint=checkpoint,
            revision=str(getattr(self._model.config, "_commit_hash", None) or revision),
            max_input_tokens=REFERENCE_MAX_INPUT_TOKENS,
            device=config.device,
            label_order_verified=config.verify_label_order_at_init,
        )

        if config.verify_label_order_at_init:
            self._verify_label_order()

    def _resolve_label_tokens(self) -> tuple[int, int]:
        """The first token of "0" and of "1", which is what the decoder emits first."""
        no_support = self._tokenizer.encode("0")[0]
        support = self._tokenizer.encode("1")[0]
        if no_support == support:
            raise LabelOrderUnverifiedError(
                f"'0' and '1' share a first token ({no_support}); the two-token slice this "
                "backend softmaxes over would compare a logit against itself"
            )
        return int(no_support), int(support)

    def _verify_label_order(self) -> None:
        """Two checks: the label tokens are what the head emits, and in the right order."""
        for premise, hypothesis in probes.ENTAILED:
            top = self._top_tokens(premise, hypothesis)
            if {self._no_support_id, self._support_id} != set(top):
                raise LabelOrderUnverifiedError(
                    f"the two highest-scoring tokens at decoder position 0 are {top}, not "
                    f"the label pair ({self._no_support_id}, {self._support_id}); this "
                    "checkpoint is not emitting a binary support label and the pair "
                    "softmax would read two arbitrary logits as a probability"
                )
        for premise, hypothesis in probes.ENTAILED:
            for negative_premise, negative_hypothesis in probes.CONTRADICTED:
                high = self._support_probability(premise, hypothesis)
                low = self._support_probability(negative_premise, negative_hypothesis)
                if not high > low:
                    raise LabelOrderUnverifiedError(
                        f"entailed probe scored {high:.4f} and contradicted probe scored "
                        f"{low:.4f}; the support and no-support tokens are the wrong way "
                        "round and every score would be confidently inverted"
                    )
        # The template above is reverse-engineered from the reference implementation and
        # is the least externally-documented thing here. The pairs below hold the claim
        # fixed and vary only the document, so they fail if the document is not reaching
        # the document slot — which the label-order probes above cannot detect.
        for hypothesis, supporting, opposing in probes.SHARED_HYPOTHESIS:
            high = self._support_probability(supporting, hypothesis)
            low = self._support_probability(opposing, hypothesis)
            if not high > low:
                raise LabelOrderUnverifiedError(
                    f"two documents sharing one claim scored {high:.4f} and {low:.4f}; "
                    "the premises are not reaching the document slot, so the score is not "
                    "a function of what this step rests on"
                )

    def _position_zero_logits(self, document: str, conclusion: str):
        text = "predict: " + self._tokenizer.eos_token.join([document, conclusion])
        encoded = self._tokenizer([text], return_tensors="pt", truncation=False)
        tokens = int(encoded["input_ids"].shape[-1])
        if tokens > self.spec.max_input_tokens:
            raise OversizeStepError(
                f"rendered step is {tokens} tokens against a limit of "
                f"{self.spec.max_input_tokens}; the reference implementation would chunk "
                "and take the maximum, which scores a subset rather than the step",
                tokens=tokens,
                limit=self.spec.max_input_tokens,
            )
        encoded = {k: v.to(self.spec.device) for k, v in encoded.items()}
        with self._torch.no_grad():
            decoder_input_ids = self._torch.zeros(
                (encoded["input_ids"].size(0), 1), dtype=self._torch.long
            ).to(self.spec.device)
            output = self._model(
                input_ids=encoded["input_ids"],
                attention_mask=encoded["attention_mask"],
                decoder_input_ids=decoder_input_ids,
            )
        return output.logits.squeeze(1)[0]

    def _top_tokens(self, document: str, conclusion: str) -> list[int]:
        logits = self._position_zero_logits(document, conclusion)
        return [int(i) for i in self._torch.topk(logits, 2).indices]

    def _support_probability(self, document: str, conclusion: str) -> float:
        logits = self._position_zero_logits(document, conclusion)
        pair = logits[self._torch.tensor([self._no_support_id, self._support_id])]
        return float(self._torch.softmax(pair, dim=-1)[1].item())

    def score(self, conclusion: str, premises: Sequence[str]) -> Score:
        value = self._support_probability(render_document(premises), conclusion)
        return build_score(value, self.spec)
