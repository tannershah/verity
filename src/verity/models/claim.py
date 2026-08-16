"""The claim graph: claims, premises, entailment steps, and groundings.

**Where confidence lives.** The verifier scores an *entailment step* — "do these 3-7
premises jointly entail this conclusion?" — so `Score` lives on `EntailmentStep` and
nowhere else. Neither `Claim` nor `Premise` has a confidence field, because nothing
computes one. A premise's honest display is the score of the step it participates in,
plus its leave-one-out ablation delta *in that step* (M4-T2), plus its evidence state.

**Everything step-scoped lives on the step.** That rule is what makes the graph a DAG
rather than a tree with extra edges. A premise reached from two steps has two entailment
scores, two ablation deltas, and two depths; any of those stored on the node would be
overwritten by whichever producer ran last, and the display would show a number belonging
to a step the reader is not looking at. So ablation deltas are keyed by premise *on the
step*, and depth is derived from traversal rather than stored at all.

**Traversal is over edges, not nodes.** `walk()` yields one `GraphEdge` per
(step, premise) pair. A node-keyed walk with a `seen` set would visit a shared premise
once and silently drop the second step's row — a step displaying with a premise missing is
exactly the polished-tree-hiding-a-bad-step failure design.md §3.4 exists to prevent.

**No root aggregate.** `Claim` carries no score, and no function anywhere composes step
scores across depths. The root step's score is a single-step entailment score — it says
whether *these* premises entail the claim, not whether the claim is true — and the render
payload labels it as such. `tests/test_no_root_aggregate.py` enforces both halves.

Structure is a flat node map plus explicit edge lists rather than nested objects: it
round-trips to rows without recursion, and M8's JTMS wiring and M1-T3's dirty-subgraph
recompute both need edge-indexed access.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from pydantic import Field, model_validator

from verity.base import VerityModel
from verity.ids import ConclusionId, FactId, PremiseId, StepId, check_id, make_id
from verity.keys import ExternalKey
from verity.models.common import (
    AblationDelta,
    CapRecord,
    ClaimType,
    EvidenceState,
    PremiseType,
    Score,
    TerminationReason,
    utc_now,
)
from verity.models.evidence import EvidenceBundle

SCHEMA_VERSION = 1


class Claim(VerityModel):
    """The root node. Deliberately has no score, status, or verdict field."""

    id: str = ""
    text: str
    source_text: str | None = None
    claim_type: ClaimType | None = None  # populated by M2-T1
    #: How the claim was decontextualized, if it was. DnDScore (`lit-014`) shows the
    #: strategy shifts downstream scores, so it travels as metadata.
    decontextualization: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _assign_id(self) -> Claim:
        if not self.id:
            self.id = make_id("claim", self.text)
        check_id("claim", self.id)
        return self


class Premise(VerityModel):
    """A load-bearing premise.

    Identity is the statement. Two branches that arrive at the same premise are the same
    node — which is what makes the graph a DAG, and why nothing step-scoped (score,
    ablation delta, depth) may live here.
    """

    id: str = ""
    text: str
    premise_type: PremiseType | None = None
    termination_reason: TerminationReason | None = None
    #: The authoritative grounding key, bound by M6-T3's key attribution. A
    #: decomposition-time candidate key from M3-T1 is a hint to verify, not a binding,
    #: and lives in `candidate_key` until M6-T3 confirms it.
    bound_key: ExternalKey | None = None
    candidate_key: ExternalKey | None = None
    #: What the run concluded. `VERIFIED` is checked against an actual `Grounding` at
    #: graph construction; whether that grounding still holds is decided at render time
    #: against the alethiology, because grounding is non-monotonic (design.md §4.2).
    evidence_state: EvidenceState = EvidenceState.UNVERIFIED
    #: True until M8-T3's settled semantics replace M6-T3's provisional state.
    evidence_state_provisional: bool = True

    @model_validator(mode="after")
    def _assign_id(self) -> Premise:
        if not self.id:
            self.id = make_id("prem", self.text)
        check_id("prem", self.id)
        return self


class EntailmentStep(VerityModel):
    """A native n-ary step: premises jointly entail a conclusion.

    No binarization into 2-premise intermediates (design.md §4.3) — the verifier scores
    the whole step and leave-one-out ablation operates on it, matching EntailmentBank's
    step convention. `conclusion_id` may be the root claim or any premise, which is what
    makes recursion work.

    A step's identity is its conclusion and the *set* of its premises: the same
    decomposition emitted in a different order is the same step, so re-ordering is a cache
    hit for M1-T2 rather than a duplicate node for M4-T2 to ablate twice. `Justification`
    sorts its antecedents for the same reason.

    Arity is not constrained here. 3-7 is a `DecompositionConfig` value, so a model
    returning eight premises is a measurement about the decomposer that M3-T1 must be able
    to store and M10-T1 must be able to report — `arity` is what they read.

    `depth` is the one thing here that traversal cannot recover. It records how deep the
    decomposer had descended when it created this step — which is what the depth budget is
    spent against and what `budget-exit` fires on. Once premises are deduplicated by
    statement the graph can be reached by a shorter route than the one that was walked, so
    a traversal reports the shape of the graph rather than the cost of building it. Both
    numbers are legitimate and they are not the same number; this is the one M10-T1's
    depth and budget-exit rate have to be measured against, so it is recorded at the
    moment it is known rather than inferred later.
    """

    id: str = ""
    conclusion_id: ConclusionId
    premise_ids: list[PremiseId]
    #: Descent depth of the conclusion when the decomposer created this step. `None` on
    #: hand-built graphs and anything predating M3; recorded for every step or for none.
    depth: int | None = Field(default=None, ge=0)
    score: Score | None = None
    #: Leave-one-out deltas for this step, keyed by the premise removed (M4-T2). Keyed on
    #: the step because that is what the verifier re-scored.
    ablation_deltas: dict[PremiseId, AblationDelta] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def arity(self) -> int:
        return len(self.premise_ids)

    def ablation_for(self, premise_id: str) -> AblationDelta | None:
        return self.ablation_deltas.get(premise_id)

    @model_validator(mode="after")
    def _validate(self) -> EntailmentStep:
        if not self.premise_ids:
            raise ValueError("an entailment step with no premises entails nothing")
        if len(set(self.premise_ids)) != len(self.premise_ids):
            # Leave-one-out over a step listing a premise twice removes one copy and
            # measures nothing.
            raise ValueError(f"step {self.conclusion_id} lists a premise more than once")
        stray = set(self.ablation_deltas) - set(self.premise_ids)
        if stray:
            raise ValueError(f"ablation deltas for premises not in this step: {sorted(stray)}")
        if not self.id:
            self.id = make_id("step", self.conclusion_id, sorted(self.premise_ids))
        check_id("step", self.id)
        return self


class Grounding(VerityModel):
    """A premise matched to an alethiology fact by exact key.

    `matched_key` is stored rather than re-derived so that a later key change is visible
    as a change, and so re-validation can tell what the match was made on. The graph
    checks it against the premise's bound key: the pre-registered grounding rate is
    counted off these rows, and a row whose key agrees with neither side is a grounding
    that never happened.
    """

    premise_id: PremiseId
    fact_id: FactId
    matched_key: ExternalKey
    grounded_at: datetime = Field(default_factory=utc_now)


class GraphEdge(VerityModel):
    """One (step, premise) pair, with the depth at which it was reached.

    The unit of traversal and of display. A shared premise produces one edge per step it
    belongs to, so each step renders with every premise it actually rests on.

    Two depths, because they answer different questions. `depth` is where this edge sits
    in the graph as it now stands — what a renderer indents by. `descent_depth` is how
    deep the decomposer had gone when it built the step, which is what the budget was
    spent against; it is `None` when the producer did not record one.
    """

    step_id: StepId
    parent_id: ConclusionId
    premise_id: PremiseId
    depth: int
    descent_depth: int | None = None


class GraphMetadata(VerityModel):
    """Run-level context for a graph. Never contains secrets."""

    run_id: str | None = None
    config_hash: str | None = None
    depth_budget: int | None = None
    caps: list[CapRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ClaimGraph(VerityModel):
    """A claim and everything computed about it.

    There is no root-aggregate field. The absence is the enforcement.

    Construction validates the structure the renderer and the metrics both assume: node
    maps keyed by identity, every reference resolvable, one decomposition per node, no
    cycles, and every premise reachable from the root. Those are not stylistic — a
    mis-keyed map drops a premise from the render with no error, a mis-keyed bundle
    attributes one premise's retraction flags to another, a cycle empties `leaves()` and
    so zeroes the grounding-rate denominator, and an unreachable premise is counted by the
    depth metric while never appearing in the display.

    A cap that orphans a subtree is a legitimate event, not a bug. `build()` is the path
    for it: it prunes what became unreachable and hands back a `CapRecord` saying how
    much, so the drop is reported rather than either crashing or vanishing.
    """

    id: str = ""
    schema_version: int = SCHEMA_VERSION
    root_claim: Claim
    premises: dict[PremiseId, Premise] = Field(default_factory=dict)
    steps: list[EntailmentStep] = Field(default_factory=list)
    groundings: list[Grounding] = Field(default_factory=list)
    bundles: dict[PremiseId, EvidenceBundle] = Field(default_factory=dict)
    metadata: GraphMetadata = Field(default_factory=GraphMetadata)

    # -- construction ------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        root_claim: Claim,
        premises: dict[str, Premise] | None = None,
        steps: list[EntailmentStep] | None = None,
        groundings: list[Grounding] | None = None,
        bundles: dict[str, EvidenceBundle] | None = None,
        metadata: GraphMetadata | None = None,
    ) -> tuple[ClaimGraph, list[CapRecord]]:
        """Construct, dropping anything the root cannot reach and reporting the drop.

        Producers that bound coverage — a beam cap, a node budget — can orphan a subtree
        by dropping its parent. This removes the orphans and returns a `CapRecord` for
        them, so evaluation.md §6's "no silent caps" holds for a drop nobody asked for.
        """
        premises = dict(premises or {})
        steps = list(steps or [])
        reachable = _reachable_nodes(root_claim.id, steps)

        orphans = {pid for pid in premises if pid not in reachable}
        caps: list[CapRecord] = []
        if orphans:
            premises = {pid: p for pid, p in premises.items() if pid not in orphans}
            steps = [
                s
                for s in steps
                if s.conclusion_id not in orphans and not (set(s.premise_ids) & orphans)
            ]
            groundings = [g for g in (groundings or []) if g.premise_id not in orphans]
            bundles = {pid: b for pid, b in (bundles or {}).items() if pid not in orphans}
            caps.append(
                CapRecord(
                    name="unreachable_premises_pruned",
                    limit=0,
                    applied=True,
                    dropped=len(orphans),
                )
            )

        graph = cls(
            root_claim=root_claim,
            premises=premises,
            steps=steps,
            groundings=list(groundings or []),
            bundles=dict(bundles or {}),
            metadata=metadata or GraphMetadata(),
        )
        return graph, caps

    @model_validator(mode="after")
    def _validate(self) -> ClaimGraph:
        for key, premise in self.premises.items():
            if key != premise.id:
                raise ValueError(
                    f"premise map key {key!r} does not match premise id {premise.id!r}"
                )
        for key, bundle in self.bundles.items():
            if key != bundle.premise_id:
                raise ValueError(
                    f"bundle map key {key!r} does not match bundle premise "
                    f"{bundle.premise_id!r}"
                )
            if key not in self.premises:
                raise ValueError(f"bundle {key!r} has no premise in this graph")

        nodes = {self.root_claim.id} | set(self.premises)
        concluded: set[str] = set()
        for step in self.steps:
            if step.conclusion_id not in nodes:
                raise ValueError(f"step concludes unknown node {step.conclusion_id!r}")
            if step.conclusion_id in concluded:
                raise ValueError(
                    f"node {step.conclusion_id!r} is decomposed by more than one step"
                )
            concluded.add(step.conclusion_id)
            unknown = set(step.premise_ids) - set(self.premises)
            if unknown:
                raise ValueError(
                    f"step {step.id} references unknown premises {sorted(unknown)}"
                )

        recorded = [step.depth is not None for step in self.steps]
        if any(recorded) and not all(recorded):
            # A max taken over some of the descent is not a shallower measurement, it is
            # a different graph's measurement. Either the producer records depth or the
            # metric reports that nothing did.
            raise ValueError(
                "descent depth is recorded on some steps and not others; "
                "record it on every step or on none"
            )

        _reject_cycles(self.steps)

        reachable = _reachable_nodes(self.root_claim.id, self.steps)
        unreachable = set(self.premises) - reachable
        if unreachable:
            raise ValueError(
                f"{len(unreachable)} premise(s) unreachable from the root: "
                f"{sorted(unreachable)[:3]}; use ClaimGraph.build() to prune and report them"
            )

        grounded_premises: set[str] = set()
        for grounding in self.groundings:
            premise = self.premises.get(grounding.premise_id)
            if premise is None:
                raise ValueError(
                    f"grounding references unknown premise {grounding.premise_id!r}"
                )
            if premise.bound_key is None:
                raise ValueError(f"premise {premise.id} is grounded but carries no bound key")
            if not premise.bound_key.matches(grounding.matched_key):
                raise ValueError(
                    f"grounding key {grounding.matched_key} does not match the bound key "
                    f"{premise.bound_key} of the premise it grounds"
                )
            grounded_premises.add(grounding.premise_id)

        for premise in self.premises.values():
            # design.md §4.2: `verified` requires exact-key grounding in an alethiology
            # fact, and is never derived from an evidence bundle.
            if (
                premise.evidence_state is EvidenceState.VERIFIED
                and premise.id not in grounded_premises
            ):
                raise ValueError(f"premise {premise.id} claims `verified` with no grounding")

        if not self.id:
            self.id = make_id("graph", self.root_claim.id)
        check_id("graph", self.id)
        return self

    # -- traversal ---------------------------------------------------------------

    def step_concluding(self, node_id: str) -> EntailmentStep | None:
        """The step whose conclusion is `node_id`, if the node was decomposed."""
        return next((s for s in self.steps if s.conclusion_id == node_id), None)

    def steps_containing(self, premise_id: str) -> list[EntailmentStep]:
        """Every step in which `premise_id` appears as a premise.

        Plural because the graph is a DAG. A caller that takes the first match attributes
        one step's score to a premise being displayed under another.
        """
        return [s for s in self.steps if premise_id in s.premise_ids]

    def children_of(self, node_id: str) -> list[Premise]:
        step = self.step_concluding(node_id)
        if step is None:
            return []
        return [self.premises[pid] for pid in step.premise_ids if pid in self.premises]

    def walk(self) -> list[GraphEdge]:
        """Breadth-first walk from the root, one edge per (step, premise) pair.

        Depth is the shortest path from the root to the edge's parent, plus one — a
        property of the edge, since a shared premise sits at different depths under
        different parents.
        """
        edges: list[GraphEdge] = []
        depth_of: dict[str, int] = {self.root_claim.id: 0}
        expanded: set[str] = set()
        queue: deque[str] = deque([self.root_claim.id])

        while queue:
            node = queue.popleft()
            if node in expanded:
                continue
            expanded.add(node)
            step = self.step_concluding(node)
            if step is None:
                continue
            depth = depth_of[node] + 1
            descent = None if step.depth is None else step.depth + 1
            for premise_id in step.premise_ids:
                depth_of.setdefault(premise_id, depth)
                edges.append(
                    GraphEdge(
                        step_id=step.id,
                        parent_id=node,
                        premise_id=premise_id,
                        depth=depth,
                        descent_depth=descent,
                    )
                )
                queue.append(premise_id)
        return edges

    def leaves(self) -> list[Premise]:
        """Premises that were not themselves decomposed."""
        seen: set[str] = set()
        out: list[Premise] = []
        for edge in self.walk():
            if edge.premise_id in seen or self.step_concluding(edge.premise_id) is not None:
                continue
            seen.add(edge.premise_id)
            out.append(self.premises[edge.premise_id])
        return out

    def grounding_for(self, premise_id: str) -> Grounding | None:
        return next((g for g in self.groundings if g.premise_id == premise_id), None)

    def max_depth(self) -> int:
        """Deepest edge in the graph as it stands — the number the renderer displays.

        Not the depth the budget was spent to: see `recorded_depth`.
        """
        return max((edge.depth for edge in self.walk()), default=0)

    def recorded_depth(self) -> int | None:
        """Deepest descent the decomposer actually made, or None if nothing recorded it.

        This is the number M10-T1 reports alongside the budget-exit rate, because it is
        the one the budget was enforced against. `max_depth` can be smaller: dedup can
        leave a premise reachable by a shorter route than the one that reached it, and
        reporting a depth measured off the shortened graph against a budget enforced along
        the original descent would be two metrics over two different objects.
        """
        depths = [e.descent_depth for e in self.walk() if e.descent_depth is not None]
        return max(depths) if depths else None

    def depth_of(self, premise_id: str) -> int | None:
        """Shallowest depth at which `premise_id` is reached."""
        depths = [e.depth for e in self.walk() if e.premise_id == premise_id]
        return min(depths) if depths else None


def _adjacency(steps: list[EntailmentStep]) -> dict[str, list[str]]:
    return {step.conclusion_id: list(step.premise_ids) for step in steps}


def _reachable_nodes(root_id: str, steps: list[EntailmentStep]) -> set[str]:
    adjacency = _adjacency(steps)
    reachable: set[str] = set()
    queue = deque([root_id])
    while queue:
        node = queue.popleft()
        for child in adjacency.get(node, ()):
            if child not in reachable:
                reachable.add(child)
                queue.append(child)
    return reachable


def _reject_cycles(steps: list[EntailmentStep]) -> None:
    """Raise if the entailment edges contain a cycle.

    A cycle makes `leaves()` empty, which zeroes the grounding-rate denominator, and it is
    exactly the well-foundedness condition Doyle 1979 rules out for a JTMS. Detecting it
    here means neither M8 nor M10 has to.
    """
    adjacency = _adjacency(steps)
    state: dict[str, int] = {}  # 1 = on the current path, 2 = finished

    def visit(node: str, path: list[str]) -> None:
        state[node] = 1
        for child in adjacency.get(node, ()):
            if state.get(child) == 1:
                cycle = path[path.index(child) :] if child in path else [child]
                raise ValueError(f"entailment cycle: {' -> '.join([*cycle, child])}")
            if state.get(child) is None:
                visit(child, [*path, child])
        state[node] = 2

    for start in adjacency:
        if state.get(start) is None:
            visit(start, [start])
