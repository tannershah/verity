"""Alethiology records: verified facts and their JTMS justifications.

M1-T1 owns these *types* and their storage. M5 owns the policy that governs them —
confidence-tier assignment, statement-hash dedup rules, the promotion queue, the drift
audit — and M8 owns the JTMS that maintains `status`. Nothing here decides whether a
fact deserves to exist; it only says what a fact is.

`FactLookup` is the read side, and it exists so the render boundary can ask whether a
recorded grounding still holds. Grounding is non-monotonic (design.md §4.2), so a
projection that cannot reach the alethiology cannot tell a live grounding from a retracted
one — see `verity.models.render`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from verity.base import VerityModel
from verity.ids import FactId, check_id, make_id, statement_hash
from verity.keys import ExternalKey
from verity.models.common import ConfidenceTier, Provenance, TmsStatus, utc_now
from verity.models.evidence import EvidenceQuality

#: Tiers that may ground a premise, and therefore the numerator of the pre-registered
#: grounding rate (evaluation.md §2). Changing this set changes a pre-registered
#: measurement — `tests/test_grounding_and_invalidation.py` pins it as an explicit table
#: so the diff has to say so out loud.
GROUNDING_ELIGIBLE_TIERS = frozenset(
    {ConfidenceTier.VERIFIED_PRIMARY, ConfidenceTier.CORROBORATED_MULTI_SECONDARY}
)


class Fact(VerityModel):
    """A verified fact, addressable by exact external key.

    The `key` field is load-bearing: grounding is defined as a premise's bound key
    matching a grounding-eligible fact's key exactly (evaluation.md §2). A fact without a
    key cannot ground anything.

    **Identity is the pair (key, statement)**, and the id is derived from it. A supplied
    id is checked against the derivation rather than trusted: the store constrains both
    the id and the pair, so an id that disagreed with its own content would satisfy one
    constraint and violate the other. Loading a stored fact still works — its id was
    derived from the same content — and a caller inventing one is refused here rather
    than as a driver error three layers down.

    The pair is therefore immutable. Correcting a statement produces a *different* fact;
    the correct move is to assert the new one and flip the old to OUT, which is also what
    the JTMS wants — mutating the statement in place would change the id and dangle every
    justification that named it (design.md §4.2).
    """

    id: str = ""
    statement: str
    key: ExternalKey
    tier: ConfidenceTier
    provenance: list[Provenance] = Field(default_factory=list)
    evidence_quality: EvidenceQuality = Field(default_factory=EvidenceQuality)
    status: TmsStatus = TmsStatus.IN
    justification_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    #: When this fact was last re-checked against its sources. Grounding is
    #: non-monotonic, so a fact past its TTL is stale, not permanent (M5-T3).
    revalidated_at: datetime | None = None

    @property
    def statement_hash(self) -> str:
        return statement_hash(self.statement)

    @property
    def is_verified(self) -> bool:
        """Whether this fact may ground a premise: eligible tier and IN state."""
        return self.status is TmsStatus.IN and self.tier in GROUNDING_ELIGIBLE_TIERS

    @model_validator(mode="after")
    def _validate(self) -> Fact:
        if self.tier in GROUNDING_ELIGIBLE_TIERS and not self.provenance:
            # design.md §4.1 defines a fact as provenance-carrying, and M5-T2 promotes to
            # a grounding-eligible tier by reading the source tier off this list.
            raise ValueError(
                f"a {self.tier.value} fact must carry the provenance it was verified against"
            )
        derived = make_id("fact", str(self.key), self.statement_hash)
        if not self.id:
            self.id = derived
        elif self.id != derived:
            raise ValueError(
                f"fact id {self.id!r} does not match the id derived from its key and "
                f"statement ({derived!r}); a fact's identity is that pair"
            )
        check_id("fact", self.id)
        return self


class Justification(VerityModel):
    """A JTMS justification: antecedent facts jointly support a consequent fact.

    M8-T2 constrains what may become one — entailment steps and alethiology groundings
    only. Bundle-derived states never enter the JTMS, and the id types are what enforce
    it: a premise id or a bundle id cannot be passed where a fact id belongs, so
    design.md §4.2's "verdict boundary as a type distinction" is checkable rather than a
    naming convention.
    """

    id: str = ""
    consequent_fact_id: FactId
    antecedent_fact_ids: list[FactId] = Field(default_factory=list)
    type: str = "support"

    @model_validator(mode="after")
    def _assign_id(self) -> Justification:
        if not self.id:
            self.id = make_id(
                "just", self.consequent_fact_id, sorted(self.antecedent_fact_ids), self.type
            )
        check_id("just", self.id)
        return self


@runtime_checkable
class FactLookup(Protocol):
    """Read-only access to the alethiology, by fact id.

    Deliberately minimal: the render boundary needs to ask one question — "is the fact
    this premise stands on still what it was?" — and giving it anything wider would let a
    renderer reach past the projection.
    """

    def get(self, fact_id: str) -> Fact | None: ...


class InMemoryFacts:
    """A `FactLookup` over facts already in hand — seeds, fixtures, a single run."""

    def __init__(self, facts: Iterable[Fact] = ()) -> None:
        self._by_id: dict[str, Fact] = {fact.id: fact for fact in facts}

    def get(self, fact_id: str) -> Fact | None:
        return self._by_id.get(fact_id)

    def add(self, fact: Fact) -> None:
        self._by_id[fact.id] = fact
