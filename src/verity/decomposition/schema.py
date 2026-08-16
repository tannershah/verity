"""What the model is constrained to return.

**These are wire types, not graph types.** Model output is an untrusted proposal; a
`Premise` is a node in a validated DAG. Keeping them separate gives every hallucination
exactly one place to be handled — `backward_chain.materialize` — instead of letting a
fabricated DOI or a restated conclusion travel as far as it can before something raises.

`extra="forbid"` (inherited from `VerityModel`) is what emits the `additionalProperties:
false` that structured outputs require, and `PremiseType` constrains typing provider-side.

**Arity is deliberately not constrained here.** Array-length keywords are not supported by
structured outputs — the SDK strips them and validates client-side — so `min_items` /
`max_items` would read as an enforced contract while enforcing nothing. 3-7 is prompt text
plus a recorded measurement, exactly as `EntailmentStep` already documents. `arity` is a
property of any stored step, so the distribution stays computable for M10-T1 forever.

**No field here may carry a score.** The decomposer proposes structure; nothing at this
tier computes confidence, and the verdict boundary is enforced by there being no field to
put one in. `tests/test_decomposition.py` checks that against
`render.ROOT_AGGREGATE_FORBIDDEN_FIELDS`.
"""

from __future__ import annotations

from pydantic import Field

from verity.base import VerityModel
from verity.models.common import PremiseType


class ProposedPremise(VerityModel):
    """One premise as the model wrote it, before any of it is believed."""

    text: str = Field(
        description=(
            "The premise as a single self-contained declarative statement, understandable "
            "without reading the claim or any other premise."
        )
    )
    premise_type: PremiseType = Field(
        description=(
            "empirical-citable: a specific study, dataset, or registry entry could verify "
            "it. statistical: a numeric or arithmetic relationship. definitional: true by "
            "the meaning of the terms. background: general context no paper is about."
        )
    )
    candidate_key: str | None = Field(
        default=None,
        description=(
            "A DOI, PMID, or NCT number for the specific work this premise rests on, only "
            "when that exact work is known. Null otherwise. Never guess an identifier."
        ),
    )


class ProposedDecomposition(VerityModel):
    """One backward-chaining step as proposed."""

    premises: list[ProposedPremise] = Field(
        description="The load-bearing premises that jointly entail the statement."
    )
