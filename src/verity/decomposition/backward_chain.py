"""One backward-chaining step: a conclusion, and the premises it rests on.

This is the recursion step that T1 happens to call once. `conclusion` is `Claim | Premise`
because `ConclusionId` admits both prefixes — that is what makes recursion work — and
`depth` is a required keyword because the graph refuses a half-recorded descent, so a
caller cannot forget to record it. M3-T2's descent drives this function unchanged.

**The drop rule.** A drop is permitted only when it is entailment-preserving; anything
that changes what the step asserts is a refusal (see `errors`). Deduplication is
`P ∧ P ≡ P`, an empty premise asserts nothing, and a malformed candidate key is metadata
the premise survives without. A cycle-closing premise is none of those, so it refuses.

**Identity is the statement, so text is normalized before the node is built.** `make_id`
NFC-normalizes for hashing while `Premise.text` stores what it was handed, so two premises
differing only by Unicode composition share an id and differ in text: dedup keyed on text
would miss the pair and `EntailmentStep` would then reject the step for listing a premise
twice. Normalizing first makes stored text and identity agree, and dedup keys on the id.

**Circularity is judged on statements, not on ids, and against the graph rather than the
path.** `verity.ids.normalize_text` is where this codebase draws the line on two spellings
being one statement, so a premise that reproduces its conclusion in a different case is a
restatement even though its id differs — and refuses, since a step that rests on its own
conclusion is circular whether or not `ClaimGraph`'s id-level cycle check happens to catch
it. The conclusion's *upstream* set (`DecompositionContext.upstream_statements`) extends
that to every node the conclusion is reachable from, which is what a descent supplies and
what catches a cycle closed across two branches rather than along one path.

**Restatement of the root claim is kept, not repaired.** A premise identical to the root
claim builds a valid graph — `Claim` and `Premise` ids differ by prefix, so there is no
cycle — and it is the highest-confidence worthless step the system can produce, since an
entailment scorer will rate it near 1.0. It is exactly the decomposer failure the
pre-registered step validity measures, so discarding it would inflate the number of the
thing under test. It is stored, flagged on the result for a descent that wants to act on
it immediately, and recoverable from the stored graph forever through
`ClaimGraph.restating_premise_ids()`. Under a *premise* conclusion the same text is a
genuine cycle and refuses instead.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from datetime import datetime

from pydantic import Field

from verity.base import VerityModel
from verity.config import DecompositionConfig
from verity.decomposition import prompt as prompt_module
from verity.decomposition.errors import (
    CyclicPremiseError,
    DecompositionError,
    DepthBudgetExceededError,
    EmptyDecompositionError,
    TruncatedDecompositionError,
)
from verity.decomposition.schema import ProposedDecomposition
from verity.ids import content_hash, normalize_text
from verity.keys import ExternalKey, InvalidKeyError
from verity.llm.base import LLMAdapter, LLMRequest
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, GraphMetadata, Premise
from verity.models.common import CapRecord, TerminationReason, utc_now
from verity.models.manifest import LLMSettings, Usage

#: Stage label. Scripts the stub, keys the manifest, and names the call in run logs.
PURPOSE = "decompose:step"

Conclusion = Claim | Premise

#: Premise fields this tier can set, and therefore the ones two steps can disagree about
#: when they propose the same statement. Everything else on `Premise` is written by a
#: later tier, which owns its own merge.
_MERGEABLE_FIELDS = ("premise_type", "candidate_key")


def normalize_display_text(text: str) -> str:
    """Collapse whitespace and apply NFC. Nothing else.

    Deliberately not `verity.ids.normalize_text`, which case-folds: this text is displayed
    verbatim, so folding it would change what a reader sees. It only has to make stored
    text agree with the identity derived from it. The names are kept apart because the two
    functions answer different questions and a premise built through the wrong one gets a
    different id.
    """
    return unicodedata.normalize("NFC", " ".join(text.split()))


class DecompositionContext(VerityModel):
    """Where the conclusion sits, for the prompt and for cycle detection.

    Two fields, deliberately not one, because they answer different questions.

    `ancestors` is the expansion path above the conclusion: what the model reads to place
    the target, rendered into the prompt and therefore into the cache key. Empty at the
    root.

    `upstream_statements` is the soundness guard: the normalized statement of every node
    from which the conclusion is reachable in the graph as it stands. Edges run
    conclusion → premise, so adding `C → P` closes a cycle exactly when `C` is reachable
    from `P` — that is, when `P` is upstream of `C`. The path is a subset of it, and the
    difference is the cross-branch case a path check cannot see: root → {A, B}, expand B
    into {A}, expand A into {B}. Neither call has the other on its path, and the cycle
    surfaces only in `ClaimGraph`, after every call in the tree has been paid for.

    **The root claim is never in this set.** `Claim` and `Premise` ids differ by prefix, so
    a premise carrying the claim's text is a new node rather than an edge back to the root:
    no cycle, and the restatement is kept and flagged rather than refused (see the module
    docstring). Putting the root's statement here would silently repeal that rule.

    Keeping the guard out of `ancestors` keeps prompt shaping and circularity independent:
    conflated, a decision about how much context to show the model would quietly redefine
    what counts as circular.
    """

    root_claim: Claim | None = None
    ancestors: tuple[Premise, ...] = ()
    upstream_statements: frozenset[str] = frozenset()


class DecomposedStep(VerityModel):
    """A materialized step plus what the call cost and what it dropped.

    Carries exactly what a `StageRecord` needs; assembling one is the orchestrator's job,
    because timing is. Nothing here holds a score — the tier has no way to produce one.
    """

    conclusion_id: str
    step: EntailmentStep
    #: Proposal order, which is display order. Step identity sorts, so order never
    #: changes what the step *is*.
    premises: dict[str, Premise] = Field(default_factory=dict)
    caps: list[CapRecord] = Field(default_factory=list)
    #: Premises in this step that reproduce the root claim. Structurally legal, and a
    #: decomposition failure. The stored form is `ClaimGraph.restating_premise_ids()`; this
    #: is the same fact in flight, for a descent deciding what to do next — which needs the
    #: ids rather than a flag, since re-deriving them by comparing normalized text would put
    #: that rule in a third place alongside `_materialize` and the graph.
    restating_premise_ids: tuple[str, ...] = ()
    usage: Usage = Field(default_factory=Usage)
    #: Read off the response envelope, never off config: a per-request override or a
    #: provider fallback makes them differ, and only the resolved values explain the output.
    llm_settings: LLMSettings
    prompt_id: str
    #: Digest of what this stage was given — the rendered turns themselves, so anything
    #: that reaches the model is covered whether or not anyone remembered to list it. The
    #: cache key is this together with the config hash (M1-T2 owns that combination).
    input_hash: str
    #: Digest of what came back. Time-free and over content, not over ids alone: premise
    #: ids derive from text, so a hash of ids reproduces across a run that typed every
    #: premise differently — and typing is what splits the grounding-rate denominators.
    output_hash: str

    @property
    def restates_root_claim(self) -> bool:
        """Whether any premise here reproduces the root claim."""
        return bool(self.restating_premise_ids)


def _materialize(
    proposal: ProposedDecomposition,
    *,
    conclusion: Conclusion,
    context: DecompositionContext,
) -> tuple[dict[str, Premise], list[CapRecord], tuple[str, ...]]:
    """Wire types to graph nodes. Every hallucination is handled exactly here."""
    conclusion_statement = normalize_text(conclusion.text)
    # Both, not either. The path check is what a caller supplying only `ancestors` relies
    # on, and the upstream set is what catches the cross-branch case; a descent supplies a
    # superset of the path, so the union costs nothing and a bug in the reachability
    # computation cannot regress the case the path already covered.
    circular = {normalize_text(ancestor.text) for ancestor in context.ancestors}
    circular |= context.upstream_statements
    # A caller that passed no context still decomposed *something*; when that something is
    # the claim itself, a premise reproducing it is the same failure as at any other depth.
    root = context.root_claim or (conclusion if isinstance(conclusion, Claim) else None)
    root_statement = normalize_text(root.text) if root is not None else None

    premises: dict[str, Premise] = {}
    empty = 0
    duplicates = 0
    bad_keys = 0
    restating: list[str] = []

    for proposed in proposal.premises:
        text = normalize_display_text(proposed.text)
        if not text:
            empty += 1
            continue

        candidate_key: ExternalKey | None = None
        if proposed.candidate_key:
            try:
                candidate_key = ExternalKey.parse(proposed.candidate_key)
            except InvalidKeyError:
                # A hint the model could not spell is not a reason to lose the premise.
                # M6-T3 owns binding; nothing renders a candidate key, so an invented
                # identifier cannot reach a reader from here.
                bad_keys += 1

        statement = normalize_text(text)
        if statement in circular or (
            statement == conclusion_statement and isinstance(conclusion, Premise)
        ):
            raise CyclicPremiseError(
                f"a premise restates the conclusion of {conclusion.id}, or a node the "
                f"conclusion is reachable from, which would rest the step on itself: "
                f"{text!r}"
            )

        premise = Premise(
            text=text, premise_type=proposed.premise_type, candidate_key=candidate_key
        )
        if premise.id in premises:
            duplicates += 1
            continue
        premises[premise.id] = premise
        if statement == root_statement:
            # Legal at any depth: the root is a `Claim`, so no premise id collides with it.
            restating.append(premise.id)

    caps = [
        CapRecord(name=name, limit=0, applied=True, dropped=count)
        for name, count in (
            ("empty_premises_dropped", empty),
            ("duplicate_premises_dropped", duplicates),
            ("unparseable_candidate_keys_dropped", bad_keys),
        )
        if count
    ]

    if not premises:
        raise EmptyDecompositionError(
            f"no premise survived materialization for {conclusion.id} "
            f"({len(proposal.premises)} proposed, {empty} empty, {duplicates} duplicate)"
        )
    return premises, caps, tuple(restating)


def decompose_step(
    conclusion: Conclusion,
    *,
    adapter: LLMAdapter,
    config: DecompositionConfig,
    depth: int,
    context: DecompositionContext | None = None,
    now: datetime | None = None,
) -> DecomposedStep:
    """Decompose `conclusion` into the premises that jointly entail it.

    `depth` is the descent depth of the conclusion, which is what the budget is spent
    against and what `budget-exit` fires on. `now` is injectable so a replay reproduces a
    graph byte-for-byte rather than only hitting the cache.

    A refusal raised after the call carries that call's `usage`, so a descent that refuses
    a branch still reports what the branch cost.
    """
    if config.candidates_per_step != 1:
        raise ValueError(
            f"candidates_per_step is {config.candidates_per_step}; sampling k candidates "
            "and choosing between them is M3-T3, and this tier issues exactly one call. "
            "Set it to 1 rather than receiving one sample without notice."
        )
    if not 0 <= depth < config.depth_budget:
        raise DepthBudgetExceededError(
            f"step requested at descent depth {depth} against a budget of "
            f"{config.depth_budget}; the deepest legal step is {config.depth_budget - 1}, "
            "since its premises sit one level below it"
        )

    context = context or DecompositionContext()
    root_claim = context.root_claim
    request = LLMRequest(
        prompt=prompt_module.render_user(
            conclusion.text,
            root_claim_text=root_claim.text if root_claim else None,
            source_text=root_claim.source_text if root_claim else None,
            ancestors=tuple(ancestor.text for ancestor in context.ancestors),
        ),
        system=prompt_module.render_system(config),
        purpose=PURPOSE,
    )

    result = adapter.structured(request, ProposedDecomposition)
    try:
        if result.truncated:
            raise TruncatedDecompositionError(
                f"decomposition of {conclusion.id} stopped on max_tokens; a truncated "
                "structured response still validates, so storing it would record a fact "
                "about the token limit as a fact about the decomposer"
            )
        premises, caps, restating = _materialize(
            result.parsed, conclusion=conclusion, context=context
        )
    except DecompositionError as error:
        # Attached in one place rather than at each raise, so a refusal added later
        # reports its cost without anyone remembering to thread it through.
        error.usage = result.usage
        raise

    step = EntailmentStep(
        conclusion_id=conclusion.id,
        premise_ids=list(premises),
        depth=depth,
        created_at=now or utc_now(),
    )

    return DecomposedStep(
        conclusion_id=conclusion.id,
        step=step,
        premises=premises,
        caps=caps,
        restating_premise_ids=restating,
        usage=result.usage,
        llm_settings=LLMSettings(
            model=result.response.model,
            effort=result.response.effort,
            thinking=result.response.thinking,
        ),
        prompt_id=prompt_module.PROMPT_ID,
        input_hash=content_hash(
            conclusion.id,
            depth,
            prompt_module.fingerprint(),
            request.system,
            request.prompt,
        ),
        output_hash=content_hash(
            step.id,
            [premises[pid] for pid in sorted(premises)],
            caps,
            sorted(restating),
        ),
    )


def _merge_premises(
    results: list[DecomposedStep],
) -> tuple[dict[str, Premise], list[CapRecord]]:
    """One node per statement, keeping every annotation the steps agree on.

    Premise identity is the statement, so two steps reaching the same premise are one node
    — but `premise_type` and `candidate_key` are not part of that identity, and a plain
    `dict.update` lets whichever step ran last decide them. A premise typed
    `empirical-citable` in one step and left untyped in another would silently become
    untyped, and premise typing is what separates the headline grounding denominator from
    the citable-only one.

    An absent annotation loses to a present one, which recovers information rather than
    picking a winner. Only two present values that disagree are a real conflict: the
    first-seen wins, for determinism, and the loss is recorded because a discarded
    annotation is a silent drop otherwise (evaluation.md §6).
    """
    premises: dict[str, Premise] = {}
    conflicts = 0

    for result in results:
        for premise_id, incoming in result.premises.items():
            existing = premises.get(premise_id)
            if existing is None:
                premises[premise_id] = incoming
                continue
            updates = {}
            for field in _MERGEABLE_FIELDS:
                held, offered = getattr(existing, field), getattr(incoming, field)
                if held is None and offered is not None:
                    updates[field] = offered
                elif held is not None and offered is not None and held != offered:
                    conflicts += 1
            if updates:
                premises[premise_id] = existing.model_copy(update=updates)

    caps: list[CapRecord] = []
    if conflicts:
        caps.append(
            CapRecord(
                name="conflicting_premise_metadata_dropped",
                limit=0,
                applied=True,
                dropped=conflicts,
            )
        )
    return premises, caps


def _apply_terminations(
    premises: dict[str, Premise], terminations: dict[str, TerminationReason]
) -> dict[str, Premise]:
    """Write each reason onto the merged node, refusing one that names no premise.

    A reason for a premise the graph does not hold is not harmless: it means the producer's
    bookkeeping and its output disagree about which nodes exist, and the check that every
    terminal carries a reason would then pass on a map describing a different tree.
    """
    stray = sorted(set(terminations) - set(premises))
    if stray:
        raise ValueError(
            f"termination reasons name {len(stray)} premise(s) this graph does not hold: "
            f"{stray[:3]}"
        )
    return {
        pid: (
            premise
            if pid not in terminations
            else premise.model_copy(update={"termination_reason": terminations[pid]})
        )
        for pid, premise in premises.items()
    }


def assemble_graph(
    root_claim: Claim,
    results: list[DecomposedStep],
    *,
    config: DecompositionConfig,
    terminations: dict[str, TerminationReason] | None = None,
    caps: Sequence[CapRecord] = (),
    metadata: GraphMetadata | None = None,
    now: datetime | None = None,
) -> ClaimGraph:
    """Merge steps into one graph, carrying every cap that bit along the way.

    `terminations` is applied *after* the merge, on the premise map the graph will hold.
    Premise identity is the statement, so a premise two steps reached is one node, and
    `termination_reason` is not among `_MERGEABLE_FIELDS` — annotating premise objects
    during a descent would let one occurrence's reason be dropped by whichever copy the
    merge kept. Applying it here means the reason is written exactly once, to the node that
    survives. `ClaimGraph` then checks the two rules that make the map trustworthy: every
    terminal carries a reason or none does, and a decomposed premise carries none.

    `caps` are bounds the descent applied that belong to no single step — the node cap. They
    are artifact-scoped (the tree is smaller than it would have been), so they join
    `metadata.caps` rather than the stage record, per the rule that a cap is filed on
    exactly one record.

    Goes through `ClaimGraph.build()` because a bound applied during descent can orphan a
    subtree, and `build()` is the path that prunes and reports rather than crashing.

    `config` is required because the depth budget is not context the graph can do without:
    M10-T1 reports `recorded_depth()` against `metadata.depth_budget`, and a graph that
    records depths but not the budget they were spent against cannot be checked against the
    guarantee `DepthBudgetExceededError` exists to give. It is stamped here rather than
    left to the orchestrator for the same reason `build()` files its own caps.

    `now` stamps the graph's own timestamp for the same reason `decompose_step` takes one:
    a replay that reproduces every id but a different `created_at` has reproduced the
    graph's content and not its bytes, and byte-equality is the check M1-T2 rests on. It
    overrides a supplied `metadata`'s timestamp, because the caller that supplies metadata
    is the one that most needs the injection to work — `GraphMetadata` stamps wall-clock
    time on construction, so any orchestrator filling in a `run_id` would otherwise defeat
    the injection silently.
    """
    for result in results:
        depth = result.step.depth
        if depth is not None and depth >= config.depth_budget:
            raise DepthBudgetExceededError(
                f"step {result.step.id} records descent depth {depth}, which its premises "
                f"put at {depth + 1}, past the budget of {config.depth_budget} this graph "
                "would claim to have been built under"
            )

    premises, merge_caps = _merge_premises(results)
    premises = _apply_terminations(premises, terminations or {})

    metadata = metadata or GraphMetadata(created_at=now or utc_now())
    if metadata.depth_budget is not None and metadata.depth_budget != config.depth_budget:
        raise ValueError(
            f"metadata claims a depth budget of {metadata.depth_budget} and the config "
            f"the steps were produced under says {config.depth_budget}"
        )
    updates: dict[str, object] = {"depth_budget": config.depth_budget}
    if now is not None:
        updates["created_at"] = now
    applied = [
        *metadata.caps,
        *(cap for result in results for cap in result.caps),
        *merge_caps,
        *caps,
    ]
    if applied:
        updates["caps"] = applied
    metadata = metadata.model_copy(update=updates)

    graph, _ = ClaimGraph.build(
        root_claim=root_claim,
        premises=premises,
        steps=[result.step for result in results],
        metadata=metadata,
    )
    return graph
