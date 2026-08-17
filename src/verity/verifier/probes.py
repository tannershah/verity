"""Fixed probe pairs for init-time verification. Two properties, checked separately.

**Label order.** `ENTAILED` and `CONTRADICTED` detect a permuted or misidentified output
head, and nothing else. They are deliberately single-sentence lexical entailments, not
syllogisms: the first draft of this check used a two-premise syllogism, on the reasoning
that our inputs are multi-premise so the probe should be too, and measured against the real
checkpoints that would have rejected a sound model. DeBERTa-v3 scores "All swans in the
lake are white. There is a swan in the lake." -> "There is a white swan in the lake." at
0.08 entailment while scoring "Every metal expands when heated. Copper is a metal." ->
"Copper expands when heated." at 0.997. The weakness is real and it is measured — it is one
of the smoke set's diagnostics — but it is a fact about compositional entailment, not about
label order, and conflating the two would make init failure mean two different things.

**Input format.** `SHARED_HYPOTHESIS` detects a malformed template — document and claim in
the wrong slots, a broken separator, a dropped prefix. The label-order probes cannot: they
pair a document with *its own* hypothesis, so lexical overlap alone ranks them correctly
even through formatting damage. That matters most for MiniCheck, whose
`"predict: " + doc + eos + claim` construction is reverse-engineered from the reference
implementation and is the least externally-documented thing in this package. These pairs
hold the hypothesis fixed and vary only the document, so any separation must come from the
document actually reaching the model in the document slot. Measured: a correct template
gives 0.9971 against 0.0001, and reversing document and claim collapses the supporting case
to 0.0028.

The bar in both cases is ordering, because a permutation or a broken slot inverts or
collapses the ordering and no constant is needed to see that.
"""

from __future__ import annotations

from typing import Final

#: (premise, hypothesis) pairs a correctly-wired entailment scorer must score high.
ENTAILED: Final[tuple[tuple[str, str], ...]] = (
    ("A man is playing a guitar on stage.", "A person is playing an instrument."),
    ("The cat sat on the mat.", "An animal was on the mat."),
)

#: (premise, hypothesis) pairs a correctly-wired entailment scorer must score low.
CONTRADICTED: Final[tuple[tuple[str, str], ...]] = (
    ("Every swan in the lake is black.", "There is a white swan in the lake."),
    ("The museum is closed every day of the week.", "The museum is open on Monday."),
)

#: (hypothesis, supporting document, opposing document). The hypothesis is identical
#: across the pair, so a scorer that separates them is reading the document slot.
SHARED_HYPOTHESIS: Final[tuple[tuple[str, str, str], ...]] = (
    (
        "An animal was on the mat.",
        "The cat sat on the mat.",
        "The mat was completely empty and nothing was on it.",
    ),
    (
        "A person is playing an instrument.",
        "A man is playing a guitar on stage.",
        "The stage was empty and no one was performing.",
    ),
)
