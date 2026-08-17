"""Claim → the tree of steps that decomposes it. The recursion M3-T1 left a seam for.

The orchestrator never learns how many calls this made: M1-T2's decompose stage keys on the
claim, and one node's `DecomposedStep.input_hash` is the cassette's finer unit. What changed
above this file is only that the stage now routes three more things the descent produces —
termination reasons, the node cap, and what the branches that produced no step cost.

**What recursion is for, and why it rarely fires.** build-plan.md M3-T2: recurse on premises
that are neither citation-shaped nor grounded. `empirical-citable` is defined as "a specific
study, dataset, or registry entry could verify it", which is what citation-shaped means, so
a premise the decomposer types that way *is* the grounding target and descending past it
buys nothing. Across the five committed pilot decompositions the type mix is 23
empirical-citable, 5 definitional, 2 background, 1 statistical — so under the default
predicate the descent expands one premise in thirty-one, and four of the five pilot claims
produce a depth-1 tree with no recursion at all. That is a measurement about the decomposer
rather than a defect here: the M3-T1 prompt steers toward citable premises, and the lever on
tree depth is the typing guidance in `prompt.py`, not this loop. The run reports its own
fan-out so a flat tree is legible as "every premise was terminal" rather than as "recursion
failed".

**Classification is a total function of the configured predicate**, in this order:

    premise_type is None                  → refuse (impossible through the wire schema)
    restates the root claim               → decomposition-refused (restates-root-claim)
    premise_type not in config.recurse_on → its INTRINSIC_TERMINALS reason
    child depth >= depth_budget           → budget-exit
    the node cap has been reached         → cap-exit
    otherwise                             → expand

**Configuration decides whether a premise is expanded; its type decides what it is called
when it stops.** `citation-shaped` and `unverifiable-by-design` are consumed as claims about
the premise — `applicability` reads the first as "a source could settle this" — so only
`INTRINSIC_TERMINALS` writes them, and a knob can never label an arithmetic premise citable.
What `recurse_on` does change is which types are *candidates*: widening it moves
`empirical-citable` into the expandable set, so a premise that then stops at the budget
records `budget-exit` and the `citation-shaped` bucket cannot occur at all. Two settings
therefore give two mixes that are **not comparable**, which is why the predicate travels in
`config_hash()` and the manifest. A type with no intrinsic terminal cannot be declined at
all: `DecompositionConfig` refuses such a predicate, which is what makes the lookup total.

Two orderings are load-bearing besides. *Restatement precedes everything* because a premise
reproducing the claim has descended nowhere — calling it citation-shaped would assert that a
source can settle a composite claim, and would put it in the citable grounding denominator;
placing it first also keeps `decomposition-refused` partitionable by
`ClaimGraph.restating_premise_ids()` with no leftovers. *Depth precedes the cap* because a
premise at the budget would not have been expanded whatever the cap did.

**Breadth-first, for correctness rather than taste.** Premises are created in
non-decreasing depth order, so the first time a node is reached is the shallowest time and
its classification never has to be revised — under depth-first a node classified
`budget-exit` can be reached again one level up, where it was expandable, and the recorded
reason would be wrong. BFS also makes the node cap truncate the widest, deepest layer
rather than amputating whole late branches.

**A branch that fails is isolated; an environment that fails is not.** A
`DecompositionError` below the root marks that node a terminal and the descent continues,
because a refusal is a statement about one node. `LLMRefusalError` is isolated the same way:
a safety refusal is the most per-premise fact a provider emits, the beachhead is health
claims, and the cassette records refusals — so propagating one would make a single premise
permanently un-runnable, deterministically and for free, on every later run. Every other
`LLMError` propagates: an auth failure, a quota exhaustion or a `CassetteMiss` will recur on
the next call, and a tree of failure-leaves is worse than a re-run the cassette makes nearly
free. At the root every refusal propagates, because there is no graph without a root step.

**`TerminationReason.GROUNDED` is never emitted here.** Under `decompose → verify → bind →
ground` nothing is bound while the descent runs, and the only identifier available is the
one the decomposer proposed — which the binder already records as circular evidence that
must never be read as the pre-registered grounding rate. Synthesising the value from it
would put that circularity into the mix M10-T1 reports, and reading last run's bound keys
off the stored graph would make tree shape a function of run history and break replay. The
value stays in the vocabulary for M6-T3 and M3-T4, and the decompose stage says the bucket
is structurally unreachable so a zero does not read as "no branch grounded".
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from pydantic import Field

from verity.base import VerityModel
from verity.config import DecompositionConfig
from verity.decomposition.backward_chain import (
    DecomposedStep,
    DecompositionContext,
    decompose_step,
)
from verity.decomposition.errors import DecompositionError, DepthBudgetExceededError
from verity.ids import normalize_text
from verity.llm.base import LLMAdapter, LLMRefusalError
from verity.models.claim import Claim, Premise
from verity.models.common import (
    INTRINSIC_TERMINALS,
    CapRecord,
    TerminationReason,
    utc_now,
)
from verity.models.manifest import Usage

#: Cap name for the tree-size bound, matching `DecompositionConfig.max_nodes_per_tree`.
NODE_CAP = "max_nodes_per_tree"

#: Why a branch produced no step, recorded per run beside the `decomposition-refused`
#: terminals it created. The enum stays coarse; this is where the difference lives, which
#: is why M10-T1 reads the manifest alongside the graph.
_REFUSAL_SUB_REASONS = {
    "CyclicPremiseError": "cyclic",
    "EmptyDecompositionError": "empty",
    "TruncatedDecompositionError": "truncated",
    "LLMRefusalError": "provider-refusal",
}

RESTATES_ROOT = "restates-root-claim"


class DescentOutcome(VerityModel):
    """Everything one descent produced, including what it refused and what it bounded.

    Separate from `list[DecomposedStep]` because three of these have no per-step home: a
    termination reason belongs to the merged node rather than to whichever step proposed it,
    the node cap belongs to no step at all, and the cost of a branch that produced no step
    is invisible to a tally over the steps that survived.
    """

    steps: list[DecomposedStep] = Field(default_factory=list)
    #: Premise id → why it has no step. Applied after the merge by `assemble_graph`.
    terminations: dict[str, TerminationReason] = Field(default_factory=dict)
    #: Artifact-scoped: the tree is smaller than it would have been. Filed on the graph.
    caps: list[CapRecord] = Field(default_factory=list)
    #: Calls issued, refusals by sub-reason, and the terminal mix — the half of the record
    #: that is not recoverable from the stored graph.
    counts: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    #: Every call this descent issued, including the ones that refused. The cassette is the
    #: authority when there is one; this is what the stage reports without it.
    usage: Usage = Field(default_factory=Usage)
    calls: int = 0

    @property
    def expanded(self) -> int:
        return len(self.steps)


def terminal_reason(
    premise: Premise, *, restating: bool, config: DecompositionConfig
) -> TerminationReason | None:
    """Why this premise stops here, or None if the predicate would expand it.

    **Configuration decides whether a premise is expanded; the type decides what it is
    called when it stops.** The two are separate on purpose. `citation-shaped` and
    `unverifiable-by-design` are consumed as claims about the premise —
    `alethiology.grounding.applicability` reads the first as "a source could settle this"
    when partitioning the grounding denominators — so only `INTRINSIC_TERMINALS` may write
    them. `recurse_on` chooses which types descend, and a type it declines falls back to
    the terminal its own meaning carries. A type with no such terminal cannot be declined:
    `DecompositionConfig` refuses that predicate, which is what makes the lookup below
    total rather than a lookup with a fallback nobody can name.

    Raises on an untyped premise rather than guessing. `ProposedPremise.premise_type` is
    required and `_materialize` is the only path into a descent, so an untyped premise
    reaching this point is a producer defect, not a policy question — and neither answer
    would be right: terminating it asserts something about verifiability nobody established,
    and expanding it spends budget on the same guess.
    """
    if premise.premise_type is None:
        # Deliberately not a `DecompositionError`: the stage isolates those, and this is a
        # producer defect rather than a refusal by the decomposer, so it must surface
        # rather than read as "the decomposer produced no graph".
        raise ValueError(
            f"premise {premise.id} carries no premise type; the wire schema requires one, "
            "so no descent can have built this premise"
        )
    if restating:
        return TerminationReason.DECOMPOSITION_REFUSED
    if premise.premise_type in config.recurse_on:
        return None
    return INTRINSIC_TERMINALS[premise.premise_type]


def _upstream(
    adjacency: dict[str, list[str]], statements: dict[str, str], node: str
) -> frozenset[str]:
    """Statements of every node from which `node` is reachable.

    Edges run conclusion → premise, so adding `node → P` closes a cycle exactly when P sits
    in here. Walked backwards over the graph as it currently stands, because edges are only
    ever added and each is checked as it is created — which is what makes a cycle
    impossible to form rather than merely detectable afterwards.

    `statements` holds premises only, so the root claim is absent by construction: a premise
    carrying the claim's text is a new node rather than an edge back to the root, and
    treating it as circular would repeal the rule that a restatement is kept and flagged.
    """
    parents: dict[str, list[str]] = {}
    for conclusion, premise_ids in adjacency.items():
        for premise_id in premise_ids:
            parents.setdefault(premise_id, []).append(conclusion)

    seen: set[str] = set()
    queue = deque(parents.get(node, ()))
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        queue.extend(parents.get(current, ()))
    return frozenset(statements[n] for n in seen if n in statements)


def decompose_claim(
    claim: Claim,
    *,
    adapter: LLMAdapter,
    config: DecompositionConfig,
    now: datetime | None = None,
) -> DescentOutcome:
    """Descend from `claim` until every branch terminates, and record why each one did.

    Raises `DecompositionError` only for the root: the caller isolates it and records the
    cost of the call that produced it, since a branch that spends money and yields no step
    still counts against the run. Below the root a refusal terminates its own branch and the
    descent continues.
    """
    now = now or utc_now()
    outcome = DescentOutcome()

    premises: dict[str, Premise] = {}
    statements: dict[str, str] = {}
    adjacency: dict[str, list[str]] = {}
    expanded: set[str] = set()
    classified: set[str] = set()
    refusals: dict[str, int] = {}
    terminal_mix: dict[str, int] = {}

    queue: deque[tuple[Premise | Claim, int, tuple[Premise, ...]]] = deque([(claim, 0, ())])

    def record(premise_id: str, reason: TerminationReason) -> None:
        outcome.terminations[premise_id] = reason
        terminal_mix[reason.value] = terminal_mix.get(reason.value, 0) + 1

    while queue:
        node, depth, path = queue.popleft()

        if node.id in expanded:
            continue
        root = node.id == claim.id
        if not root and len(premises) >= config.max_nodes_per_tree:
            # Checked before the call, not after: a step whose premises we would refuse to
            # keep is a call nobody should pay for. The overshoot is one step's arity, since
            # the expansion that crosses the line runs to completion — so a graph can carry
            # `limit=60, applied=True` and hold rather more than sixty premises.
            #
            # The root is exempt. A cap that refused the first call would yield no graph at
            # all, which is a refusal rather than a bound, and `max_nodes_per_tree=0` would
            # then mean "produce nothing" instead of "do not descend".
            record(node.id, TerminationReason.CAP_EXIT)
            continue

        context = DecompositionContext(
            root_claim=claim,
            ancestors=path,
            upstream_statements=_upstream(adjacency, statements, node.id),
        )
        # Raised rather than asserted: `python -O` strips `assert`, and this is the check
        # that caught the descent building a node into its own ancestor chain. An invariant
        # worth writing is worth surviving an optimized interpreter.
        if not {normalize_text(a.text) for a in path} <= context.upstream_statements:
            raise RuntimeError(
                f"the expansion path above {node.id} is not upstream of it; a guard that "
                "lost the path would stop refusing the cycles the path check already caught"
            )

        try:
            result = decompose_step(
                node,
                adapter=adapter,
                config=config,
                depth=depth,
                context=context,
                now=now,
            )
        except (DecompositionError, LLMRefusalError) as error:
            # `DepthBudgetExceededError` is the one refusal raised *before* the call — which
            # the descent only reaches with a budget of zero, at the root — so it is the one
            # that did not cost a call. `LLMRefusalError` carries no usage for the opposite
            # reason: the provider declined before an envelope existed, which is a call with
            # no recorded cost rather than a call costing nothing.
            if not isinstance(error, DepthBudgetExceededError):
                outcome.calls += 1
            usage = getattr(error, "usage", None)
            if usage is not None:
                outcome.usage = outcome.usage + usage
            if node.id == claim.id:
                raise
            sub = _REFUSAL_SUB_REASONS.get(type(error).__name__, "other")
            refusals[sub] = refusals.get(sub, 0) + 1
            record(node.id, TerminationReason.DECOMPOSITION_REFUSED)
            continue

        outcome.calls += 1
        outcome.usage = outcome.usage + result.usage
        outcome.steps.append(result)
        expanded.add(node.id)
        adjacency[node.id] = list(result.step.premise_ids)
        restating = set(result.restating_premise_ids)
        # The chain a child inherits is this node's ancestors plus this node — and empty
        # under the root, which is a `Claim` and travels in `root_claim` rather than here.
        child_path = (*path, node) if isinstance(node, Premise) else ()

        for premise_id in result.step.premise_ids:
            premise = result.premises[premise_id]
            premises.setdefault(premise_id, premise)
            statements.setdefault(premise_id, normalize_text(premise.text))
            if premise_id in classified:
                # A node reached twice is one node. BFS reached it at its shallowest depth
                # first, so the classification it already has is the one to keep.
                continue
            classified.add(premise_id)

            reason = terminal_reason(
                premise, restating=premise_id in restating, config=config
            )
            if reason is not None:
                if premise_id in restating:
                    refusals[RESTATES_ROOT] = refusals.get(RESTATES_ROOT, 0) + 1
                record(premise_id, reason)
                continue
            if depth + 1 >= config.depth_budget:
                record(premise_id, TerminationReason.BUDGET_EXIT)
                continue
            queue.append((premise, depth + 1, child_path))

    if refusals:
        # One line, and no model text. Per-branch notes repeated the excerpt the arity note
        # was aggregated to avoid, and every one of them carried a statement the decomposer
        # wrote — the run's only free-text channel for untrusted content. Nothing is lost:
        # *which* premises refused is on the graph as `decomposition-refused` terminals, and
        # the restatement partition among them is `ClaimGraph.restating_premise_ids()`.
        breakdown = ", ".join(f"{count} {sub}" for sub, count in sorted(refusals.items()))
        outcome.notes.append(
            f"{sum(refusals.values())} branch(es) were not decomposed ({breakdown}); they "
            "are the `decomposition-refused` terminals on the graph"
        )

    dropped = terminal_mix.get(TerminationReason.CAP_EXIT.value, 0)
    if dropped:
        outcome.caps.append(
            CapRecord(
                name=NODE_CAP,
                limit=config.max_nodes_per_tree,
                applied=True,
                # Not a count of anything removed: nothing was dropped from the artifact,
                # and the subtrees this stopped were never built and cannot be enumerated.
                # How many premises stopped here is `terminal:cap-exit` below, and is
                # recoverable from the stored graph by counting `cap-exit` leaves.
                dropped="uncounted",
            )
        )
        outcome.notes.append(
            f"the node cap of {config.max_nodes_per_tree} stopped the descent with "
            f"{len(premises)} premises; {dropped} branch(es) were left unexpanded"
        )

    unaccounted = set(premises) - expanded - set(outcome.terminations)
    if unaccounted:
        # `ClaimGraph` would catch this too, two layers up and as a message about a graph.
        # Raised here so it names the descent's own bookkeeping, and so `-O` cannot remove
        # the only check that reads in the vocabulary of the thing that went wrong.
        raise RuntimeError(
            f"{len(unaccounted)} premise(s) neither decomposed nor terminated: "
            f"{sorted(unaccounted)[:3]}"
        )

    outcome.counts = {
        "steps": len(outcome.steps),
        "premises": len(premises),
        "expanded": len(expanded),
        **{f"terminal:{reason}": count for reason, count in sorted(terminal_mix.items())},
        **{f"refused:{sub}": count for sub, count in sorted(refusals.items())},
    }
    return outcome

