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
from verity.ids import FactId, derive_id, statement_hash
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


def fact_identity(key: ExternalKey, statement: str) -> tuple[str, str]:
    """The pair a fact's id is derived from — the one definition of what a fact *is*.

    Exported because producers need to ask "would this be the same fact?" before they can
    build one, and a producer that answers by comparing raw text asks a different question
    than the store does: `statement_hash` folds case and collapses whitespace, so two
    statements differing only in capitalization are one fact here and two strings there.
    A second, informal derivation is how a duplicate slips past a caller's own check and
    then silently overwrites its twin.
    """
    return (str(key), statement_hash(statement))


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
    #: The verbatim text from the source that the statement was written against, where one
    #: exists. It travels on the record rather than only in the file that produced it: the
    #: statement is attributive ("X reports that …"), a tier is a claim about how well that
    #: attribution is supported, and a reader inspecting a `verified-primary` fact should
    #: find the words it rests on without following a provenance URL out to another file.
    #: `None` for facts from sources that quote nothing — M5-T2 promotion from an evidence
    #: bundle among them.
    supporting_quote: str | None = None
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
        self.id = derive_id(
            "fact",
            *fact_identity(self.key, self.statement),
            supplied=self.id,
            identity="its key and statement",
        )
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
        self.id = derive_id(
            "just",
            self.consequent_fact_id,
            sorted(self.antecedent_fact_ids),
            self.type,
            supplied=self.id,
            identity="its consequent, antecedents, and type",
        )
        return self


@runtime_checkable
class FactLookup(Protocol):
    """Read-only access to the alethiology: by fact id, and by exact external key.

    Two questions, and the projection needs both. `get` answers "is the fact this premise
    stands on still what it was?" — the non-monotonic-grounding question. `facts_for`
    answers "what does the alethiology know about the work this premise cites?", which is
    a different question because **a retraction warning is not contingent on grounding**.
    A premise bound to a retracted DOI deserves the flag whether or not the fact under
    that DOI reached a grounding-eligible tier; tying the warning to eligibility would
    hide exactly the citations most worth flagging.

    Still deliberately narrow: both take an identifier, neither takes text, so a caller
    cannot search the alethiology for a topic. And the consumer is `to_render_payload`,
    which is the boundary itself — a renderer sees `RenderPayload` and never this.
    """

    def get(self, fact_id: str) -> Fact | None: ...

    def facts_for(self, key: ExternalKey) -> list[Fact]: ...


class InMemoryFacts:
    """A `FactLookup` over facts already in hand — seeds, fixtures, a single run."""

    def __init__(self, facts: Iterable[Fact] = ()) -> None:
        self._by_id: dict[str, Fact] = {fact.id: fact for fact in facts}

    def get(self, fact_id: str) -> Fact | None:
        return self._by_id.get(fact_id)

    def facts_for(self, key: ExternalKey) -> list[Fact]:
        return [fact for fact in self._by_id.values() if fact.key.matches(key)]

    def add(self, fact: Fact) -> None:
        self._by_id[fact.id] = fact
