"""The throwaway sequential driver: claim → premises → step scores → grounding → render.

**Delete this when M1-T2's orchestrator lands.** It composes the tiers that exist by
hand, in order, with no caching, no replay, no stage records and no failure isolation
beyond reporting a refusal — all four of which are M1-T2's, and none of which should be
half-built here. What it must not do is hide anything the tiers report: a refusal carries
the cost of the call that produced it, an uninstalled scorer is stated rather than left to
read as a graph nobody scored, and every cap the passes file travels on the graph into the
render.

**`apply_groundings` is policy, and its home is `Alethiology`.** design.md §4.2 pins
`verified` to exactly one thing — exact-key grounding in a fact that is IN and in an
eligible tier — and nothing in the codebase writes it, so the projection's downgrade path
has never had an upgrade to undo and a demo would show `grounded · live` beside
`unverified` on the same row. It is written here, as a pure function over models taking
the service as an argument, so that moving it into `verity.alethiology` at integration is
a file move rather than a rewrite. M6-T3 owns evidence state once it lands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from verity.alethiology.grounding import GroundingAttempt
from verity.alethiology.service import Alethiology
from verity.config import RetrievalConfig, VerityConfig
from verity.decomposition.backward_chain import (
    DecompositionContext,
    assemble_graph,
    decompose_step,
)
from verity.decomposition.errors import DecompositionError
from verity.ids import make_id
from verity.llm.base import LLMAdapter
from verity.models.claim import Claim, ClaimGraph, GraphMetadata
from verity.models.common import EvidenceState, utc_now
from verity.models.manifest import LLMSettings, Usage
from verity.retrieval.binder import BindingOutcome, bind_candidate_keys
from verity.retrieval.http import CacheMode, build_client

VERIFIER_ABSENT_NOTE = (
    "the entailment scorer is not installed, so no step carries a score — "
    "`uv pip install -e '.[dev,verifier]'` scores them"
)


@dataclass
class RunResult:
    """What one claim produced. `graph` is None only when the decomposer refused."""

    claim: Claim
    graph: ClaimGraph | None = None
    usage: Usage | None = None
    llm_settings: LLMSettings | None = None
    attempts: tuple[GroundingAttempt, ...] = ()
    notes: list[str] = field(default_factory=list)
    refusal: DecompositionError | None = None


def apply_groundings(
    graph: ClaimGraph,
    service: Alethiology,
    *,
    grounded_at: datetime | None = None,
) -> tuple[ClaimGraph, list[GroundingAttempt]]:
    """Ground every premise that carries a bound key, and record what grounded.

    A premise that grounds is `verified` by definition (design.md §4.2), so the state is
    written here alongside the `Grounding` row — provisional, because M8-T3 owns the
    settled semantics and M6-T3 owns the producer. Nothing else is upgraded: a premise
    with evidence but no grounding stays `unverified`, which is what a bundle can support.

    Re-grounding an already-grounded graph replaces each premise's row rather than adding
    a second one. `ClaimGraph.grounding_for` takes the first match, so a duplicate row
    would be invisible until the two disagreed — and its permanent home is exactly where
    M8-T3 re-grounds a graph after an invalidation, which is the second call this function
    has to survive.

    Returns a rebuilt graph rather than a mutated one, so construction re-runs every
    invariant — including the one that refuses `verified` without a grounding.
    """
    attempts = service.ground_all(graph.premises.values(), grounded_at=grounded_at)
    grounded = {a.premise_id: a.grounding for a in attempts if a.grounding is not None}
    if not grounded:
        return graph, attempts

    kept = [g for g in graph.groundings if g.premise_id not in grounded]

    premises = {
        pid: (
            premise.model_copy(
                update={
                    "evidence_state": EvidenceState.VERIFIED,
                    "evidence_state_provisional": True,
                }
            )
            if pid in grounded
            else premise
        )
        for pid, premise in graph.premises.items()
    }
    rebuilt = ClaimGraph(
        root_claim=graph.root_claim,
        premises=premises,
        steps=graph.steps,
        groundings=[*kept, *grounded.values()],
        bundles=graph.bundles,
        metadata=graph.metadata,
    )
    return rebuilt, attempts


def bind_keys(
    graph: ClaimGraph, *, config: RetrievalConfig, mode: CacheMode
) -> tuple[ClaimGraph, list[str]]:
    """Promote candidate keys the registries resolve, and say what that does not mean.

    Without this, `Alethiology.ground` answers `NO_BOUND_KEY` for every premise of every
    run — a decomposition-time candidate key is a hint, and only a `bound_key` grounds. So
    the grounding column stays empty not because nothing grounds but because nothing was
    ever asked.

    Two things travel back as notes rather than staying in the report object. The cache
    mode, because a graph built from replayed bytes is a different epistemic object from
    one built live and a recorded demo has to show which it is; and the binder's own
    `basis`, because a premise that grounds through a key the *decomposer proposed* is
    circular evidence and must never be read as the pre-registered grounding rate.
    """
    client = build_client(config=config, mode=mode)
    bound, report = bind_candidate_keys(graph, client)

    counts = report.counts
    notes = [
        f"candidate-key binding ran in cache mode {mode.value}: "
        + (", ".join(f"{name} {count}" for name, count in counts.items()) or "nothing to bind")
    ]
    for decision in report.with_outcome(BindingOutcome.COULD_NOT_BE_CHECKED):
        # Not a negative: a transport failure or a spent budget left the question open,
        # and recording it as "did not resolve" would blame the decomposer for the network.
        notes.append(
            f"{decision.candidate_key} could not be checked "
            f"({', '.join(f'{k}: {v}' for k, v in decision.unchecked.items())})"
        )
    if report.with_outcome(BindingOutcome.BOUND):
        notes.append(report.basis)
    return bound, notes


def run_claim(
    claim: Claim,
    *,
    config: VerityConfig,
    adapter: LLMAdapter,
    service: Alethiology | None = None,
    score: bool = True,
    bind: bool = True,
    cache_mode: CacheMode = CacheMode.LIVE,
    now: datetime | None = None,
) -> RunResult:
    """Decompose one claim, score its step, ground what it can, and hand back the graph.

    One step, not a descent: recursion, the depth budget and termination reasons are
    M3-T2's, and inventing them here would put numbers in the render that no tier
    produced. The graph shape the renderer draws is the same either way — a nested graph
    renders through the same path the moment the descent lands.

    `now` is injectable, and the run id is derived from it together with the claim and the
    configuration rather than drawn at random: a committed artifact has to be tied to the
    settings that produced it, and a random id would make byte-equality — the check M1-T2's
    replay rests on — unreachable even when the run genuinely reproduced.
    """
    now = now or utc_now()
    result = RunResult(claim=claim)
    try:
        step = decompose_step(
            claim,
            adapter=adapter,
            config=config.decomposition,
            depth=0,
            context=DecompositionContext(root_claim=claim),
            now=now,
        )
    except DecompositionError as error:
        result.refusal = error
        result.usage = error.usage
        return result

    result.usage = step.usage
    result.llm_settings = step.llm_settings
    config_hash = config.config_hash()
    graph = assemble_graph(
        claim,
        [step],
        config=config.decomposition,
        metadata=GraphMetadata(
            run_id=make_id("run", claim.id, config_hash, now.isoformat()),
            config_hash=config_hash,
            created_at=now,
        ),
        now=now,
    )

    if step.restates_root_claim:
        result.notes.append(
            "a premise restates the claim; that step entails trivially and its score "
            "measures nothing about the decomposition"
        )
    arity = step.step.arity
    if not config.decomposition.min_premises <= arity <= config.decomposition.max_premises:
        # Stored and reported, never corrected (build-plan.md M3-T1): out-of-range arity
        # is a measurement about the decomposer.
        result.notes.append(
            f"arity {arity} is outside the configured "
            f"{config.decomposition.min_premises}-{config.decomposition.max_premises} range"
        )

    if score:
        graph, note = score_steps(graph, config)
        if note:
            result.notes.append(note)
    else:
        result.notes.append("scoring was skipped by request, so no step carries a score")

    if bind:
        graph, binding_notes = bind_keys(graph, config=config.retrieval, mode=cache_mode)
        result.notes.extend(binding_notes)

    if service is not None:
        graph, attempts = apply_groundings(graph, service, grounded_at=now)
        result.attempts = tuple(attempts)
        missed = [a for a in result.attempts if a.reason.value == "alias-only"]
        for attempt in missed:
            # An invisible deflation made visible: the premise cites one identifier for a
            # work the alethiology holds under another.
            result.notes.append(
                f"{attempt.key} did not ground, but the alethiology holds facts under "
                f"{', '.join(str(k) for k in attempt.alias_keys)}"
            )

    result.graph = graph
    return result


def score_steps(graph: ClaimGraph, config: VerityConfig) -> tuple[ClaimGraph, str | None]:
    """Score every step, or say why none were scored.

    The two reasons a row can read `unscored` are kept apart: a checkpoint that is not
    installed produces a note here, and a step too large for the checkpoint's context
    files an `oversize_steps_unscored` cap that travels on the graph into the render's cap
    line. Collapsing them would let a missing dependency look like a measured refusal.
    """
    try:
        from verity.verifier.registry import build_scorer

        scorer = build_scorer(config.verifier)
    except ImportError:
        return graph, VERIFIER_ABSENT_NOTE

    from verity.verifier.scoring import score_graph

    result = score_graph(graph, scorer)
    note = None
    if result.oversize_step_ids:
        note = (
            f"{len(result.oversize_step_ids)} step(s) exceeded the checkpoint's "
            f"{scorer.spec.max_input_tokens}-token budget and are unscored"
        )
    return result.graph, note
