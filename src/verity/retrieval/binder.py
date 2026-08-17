"""Promote a decomposition-time candidate key to a binding — but only if it resolves.

**A labelled partial of M6-T3.** That tier owns key attribution properly: the top
supporting evidence item above the stance floor binds its identifier to the premise. This
is narrower and exists because nothing else yet writes `Premise.bound_key`, so
`Alethiology.ground` is reachable only from tests and seeded keys, and the grounding step
of the demo never happens.

Three rules, each of which is the difference between a binding and a fabrication:

- **A candidate key is a hint to verify, not a binding.** M3-T1 fills it when the model
  claims to know the specific work, and a language model naming a DOI is exactly the shape
  of assertion the seed gate exists to catch — `10.1080/00071668108416780` sat in this
  repository's own fixtures as a `verified-primary` target and resolves nowhere. Blind
  promotion binds hallucinated identifiers.
- **Only a registry resolves a key.** `resolution.REGISTRY_SOURCES` — OpenAlex and Crossref
  — speak for a work's own metadata. Retraction Watch is a curated index: authoritative
  about retractions, secondary about works, and capped at `single-secondary` by the seed
  gate for that reason. A key present only in a local CSV must not read as a confirmed work.
- **Aliases are never a binding path.** A registry reporting that a work also carries a PMID
  does not make that PMID the premise's key. Grounding excludes aliases because widening the
  predicate would move a pre-registered definition; binding excludes them for the same
  reason, one step earlier.

**"Could not be checked" is not "did not resolve."** A budget floor, an exhausted retry, or
a replay miss leaves the question unanswered, and recording that as a negative would make a
transport failure look like evidence against an identifier — the same distinction
`RetractionFinding.NOT_INDEXED` draws against `CLEAN`.

**The label travels as data.** `BindingReport.basis` states what a rate computed off these
bindings does and does not mean, so it cannot be dropped by copy that forgot.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from verity.base import FrozenModel
from verity.keys import ExternalKey
from verity.models.claim import ClaimGraph, Premise
from verity.retrieval import crossref, openalex
from verity.retrieval.errors import RetrievalError
from verity.retrieval.http import HttpClient

#: The sources whose answer counts as "this identifier names a real work". Deliberately
#: not `retraction_watch`, and deliberately the same constant the seed gate reads.
RESOLVING_SOURCES = (openalex, crossref)

#: What a grounding rate derived from these bindings means. Carried on every report.
PARTIAL_BASIS = (
    "Labelled partial of M6-T3. A key is bound because the decomposer proposed it and a "
    "registry resolves it — not because retrieval found evidence for the premise. Any "
    "grounding rate computed from these bindings is NOT the pre-registered measurement in "
    "evaluation.md §2: 'the decomposer emitted an identifier that resolves and is in our "
    "seed' is circular, and must never be quoted as that number."
)


class BindingOutcome(StrEnum):
    """What happened to one premise's candidate key."""

    BOUND = "bound"
    ALREADY_BOUND = "already-bound"
    NO_CANDIDATE = "no-candidate-key"
    #: Every registry consulted said it has no such work.
    DID_NOT_RESOLVE = "did-not-resolve"
    #: No registry could answer — budget, transport, or a replay miss. Not a negative.
    COULD_NOT_BE_CHECKED = "could-not-be-checked"


class KeyCheck(FrozenModel):
    """What each registry made of one identifier — including which ones never answered.

    Whether a registry answered is a separate channel rather than something inferred from
    `resolved_by` being empty. Inferring it was wrong in the one case this module's own
    rule names: an NCT identifier produces no request at either registry, so both lists
    came back empty and the absence of an answer read as a unanimous negative.

    **Two ways to have no answer, and they are not the same.** A registry that does not
    index a kind of identifier can never answer, and waiting for it would leave every PMID
    permanently unchecked even though OpenAlex indexes PMIDs and its answer settles the
    question. A registry that *could* have answered and did not — a transport failure, a
    spent budget, a 404 from an uncredentialed pool — leaves the check genuinely
    incomplete. Only the second blocks a negative.
    """

    #: Registries that looked, under their own credential, and said something either way.
    answered: list[str] = Field(default_factory=list)
    #: Registries that returned a record.
    resolved_by: list[str] = Field(default_factory=list)
    #: Could have answered and did not, with the reason. These make a check incomplete.
    unreachable: dict[str, str] = Field(default_factory=dict)
    #: Structurally unable to answer — Crossref holds no PMIDs, OpenAlex no NCT entries.
    not_applicable: dict[str, str] = Field(default_factory=dict)

    @property
    def unchecked(self) -> dict[str, str]:
        """Every registry that gave no usable answer, for the report."""
        return {**self.not_applicable, **self.unreachable}

    @property
    def resolves(self) -> bool:
        return bool(self.resolved_by)

    @property
    def complete(self) -> bool:
        """Whether every registry that could speak to this identifier actually did."""
        return not self.unreachable

    @property
    def refutes(self) -> bool:
        """Whether the identifier was really checked and really found nowhere."""
        return not self.resolves and bool(self.answered) and self.complete


class BindingDecision(FrozenModel):
    """One premise, one candidate key, and why it was or was not bound."""

    premise_id: str
    candidate_key: ExternalKey | None
    outcome: BindingOutcome
    #: Registries that returned a record for the key. Empty on every outcome but `BOUND`.
    resolved_by: list[str] = Field(default_factory=list)
    #: Registries that gave no usable answer, and why — a transport failure, a spent
    #: budget, or a registry that does not index this kind of identifier at all.
    unchecked: dict[str, str] = Field(default_factory=dict)


class BindingReport(FrozenModel):
    """Every decision the binder made, and the label the numbers travel under."""

    decisions: list[BindingDecision] = Field(default_factory=list)
    #: Structural, not a comment: this tier is a partial and says so in the record itself.
    is_partial: bool = True
    basis: str = PARTIAL_BASIS

    def with_outcome(self, outcome: BindingOutcome) -> list[BindingDecision]:
        return [decision for decision in self.decisions if decision.outcome is outcome]

    @property
    def counts(self) -> dict[str, int]:
        return {
            outcome.value: len(self.with_outcome(outcome))
            for outcome in BindingOutcome
            if self.with_outcome(outcome)
        }

    def render(self) -> str:
        lines = [
            "candidate-key binding (labelled partial of M6-T3)",
            "  " + ", ".join(f"{name}: {count}" for name, count in self.counts.items()),
        ]
        for decision in self.decisions:
            if decision.outcome in (BindingOutcome.NO_CANDIDATE, BindingOutcome.ALREADY_BOUND):
                continue
            detail = ", ".join(decision.resolved_by) or ", ".join(
                f"{source}: {why}" for source, why in decision.unchecked.items()
            )
            lines.append(
                f"  {decision.premise_id} {decision.candidate_key} "
                f"→ {decision.outcome.value}" + (f" ({detail})" if detail else "")
            )
        lines += ["", *(f"  {line}" for line in _wrap(PARTIAL_BASIS))]
        return "\n".join(lines)


def _wrap(text: str, width: int = 88) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*lines, current] if current else lines


def check_key(client: HttpClient, key: ExternalKey) -> KeyCheck:
    """Ask each registry whether `key` names a work, and record who was able to say.

    The record's own `outcome` decides which channel an answer lands in, so a registry that
    cannot be asked, one whose request failed, and one whose 404 came back from an
    uncredentialed pool are all `unchecked` — never a vote that the identifier is fictional.
    """
    answered: list[str] = []
    resolved_by: list[str] = []
    unreachable: dict[str, str] = {}
    not_applicable: dict[str, str] = {}

    for module in RESOLVING_SOURCES:
        try:
            record = module.fetch_work(client, key)
        except RetrievalError as exc:
            unreachable[module.SOURCE] = type(exc).__name__
            continue
        if not record.answered:
            # The reading classifies itself. Re-deriving capability here from
            # `work_request(key) is None` would be a second copy of a rule the client
            # already applied, free to drift from it.
            channel = not_applicable if record.not_applicable else unreachable
            channel[module.SOURCE] = record.unanswered_because or "unanswered"
            continue
        answered.append(module.SOURCE)
        if record.found:
            resolved_by.append(module.SOURCE)

    return KeyCheck(
        answered=answered,
        resolved_by=resolved_by,
        unreachable=unreachable,
        not_applicable=not_applicable,
    )


def decide(client: HttpClient, premise: Premise) -> BindingDecision:
    """What should happen to `premise`'s candidate key, without changing anything."""
    if premise.bound_key is not None:
        return BindingDecision(
            premise_id=premise.id,
            candidate_key=premise.candidate_key,
            outcome=BindingOutcome.ALREADY_BOUND,
        )
    if premise.candidate_key is None:
        return BindingDecision(
            premise_id=premise.id, candidate_key=None, outcome=BindingOutcome.NO_CANDIDATE
        )

    check = check_key(client, premise.candidate_key)
    if check.resolves:
        outcome = BindingOutcome.BOUND
    elif check.refutes:
        # Some registry looked, under its own credential, and has no such work. This is
        # the only path to a negative — and it stays a negative even if a *second*
        # registry could not be reached, because one registry that looked is enough to
        # say the identifier was checked.
        outcome = BindingOutcome.DID_NOT_RESOLVE
    else:
        # Nobody was in a position to answer. Recording that as a negative would make a
        # transport failure, a spent budget, or a key type these registries do not index
        # look like evidence that the decomposer invented the identifier.
        outcome = BindingOutcome.COULD_NOT_BE_CHECKED
    return BindingDecision(
        premise_id=premise.id,
        candidate_key=premise.candidate_key,
        outcome=outcome,
        resolved_by=check.resolved_by,
        unchecked=check.unchecked,
    )


def bind_candidate_keys(
    graph: ClaimGraph, client: HttpClient
) -> tuple[ClaimGraph, BindingReport]:
    """Return `graph` with resolvable candidate keys bound, and the record of every decision.

    `evidence_state` is untouched. Binding a key says an identifier names a real work; it
    says nothing about whether the premise is supported, and only the alethiology can
    answer that (`Alethiology.ground`). Premise ids are derived from text alone, so binding
    a key leaves every id — and therefore every step and edge — unchanged.
    """
    decisions = [decide(client, premise) for premise in graph.premises.values()]
    bound = {
        decision.premise_id: decision.candidate_key
        for decision in decisions
        if decision.outcome is BindingOutcome.BOUND and decision.candidate_key is not None
    }

    premises = {
        premise_id: (
            premise.model_copy(update={"bound_key": bound[premise_id]})
            if premise_id in bound
            else premise
        )
        for premise_id, premise in graph.premises.items()
    }
    rebuilt, pruned = ClaimGraph.build(
        root_claim=graph.root_claim,
        premises=premises,
        steps=graph.steps,
        groundings=graph.groundings,
        bundles=graph.bundles,
        metadata=graph.metadata,
    )
    if pruned:
        # Binding writes a key onto a premise and changes no edge, so nothing can become
        # unreachable. Asserting that is cheaper than discarding a `CapRecord` — a silent
        # drop here would be a premise vanishing from the graph during a metadata pass.
        raise AssertionError(f"binding pruned reachable nodes: {[cap.name for cap in pruned]}")
    return rebuilt, BindingReport(decisions=decisions)
