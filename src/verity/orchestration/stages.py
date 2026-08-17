"""The four pipeline stages, and which of them may be cached at all.

Cacheability is a declared property with a recorded reason, not a uniform behaviour, and
two of the four decline it for reasons that are design decisions rather than performance
ones:

- **`ground` must never be cached.** design.md §4.2 makes grounding non-monotonic — "a tree
  that terminated yesterday can be un-grounded today" — and says grounding results are "not
  cached as permanent". A uniform stage cache would quietly repeal that, and the run would
  keep reporting a premise as grounded after the fact beneath it was retracted.
- **`bind` is not stage-cached either.** Its cache is the HTTP transport's, which carries
  the negative-entry namespace and the degraded-request rule a registry answer needs; a
  second cache above it would have neither. Worse, `CacheMode` is deliberately kept out of
  `config_hash()`, so a live run and a replay would share a stage key and a replay could be
  served a decision made from live bytes — erasing the distinction that mode exists to draw.

Each stage owns two digests. `input_digest` is computed *before* the work, because that is
what a cache key needs; `output_digest` is the masked content fingerprint of the graph it
returns, which is what a replay compares. Neither is re-derived from a producer's own
recorded hash — where a producer already computes one, it is exported and shared.
"""

from __future__ import annotations

import sqlite3
from typing import Protocol

from pydantic import Field

from verity.alethiology.apply import apply_groundings
from verity.alethiology.grounding import GroundingAttempt
from verity.base import VerityModel
from verity.decomposition.backward_chain import assemble_graph
from verity.decomposition.descent import decompose_claim
from verity.decomposition.errors import DecompositionError
from verity.ids import content_hash
from verity.llm.base import LLMError
from verity.models.claim import ClaimGraph, GraphMetadata
from verity.models.common import CapRecord
from verity.models.manifest import LLMSettings, Usage
from verity.orchestration.context import RunContext, graph_fingerprint
from verity.retrieval.binder import BindingOutcome, bind_candidate_keys
from verity.retrieval.errors import RetrievalError
from verity.verifier.errors import ScorerIdentityError, VerifierError
from verity.verifier.registry import UnknownCheckpointError

VERIFIER_ABSENT_NOTE = (
    "the entailment scorer is not installed, so no step carries a score — "
    "`uv pip install -e '.[dev,verifier]'` scores them"
)


class StageResult(VerityModel):
    """What a stage produced, before the orchestrator turns it into a `StageRecord`.

    `usage` is what *this run* spent: a call served from the cassette contributes nothing,
    and what it originally cost travels in `note` instead. `caps` holds execution-scoped
    bounds only — artifact-scoped ones are already on `graph.metadata.caps`, and filing
    them in both places would have anything reading the manifest and the graph count them
    twice.
    """

    graph: ClaimGraph
    output_hash: str
    llm_calls: int = 0
    cache_hits: int = 0
    truncated_calls: int = 0
    usage: Usage = Field(default_factory=Usage)
    llm_settings: LLMSettings | None = None
    caps: list[CapRecord] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    note: str | None = None
    #: Grounding attempts, handed back for the caller to report. Never stored on the graph.
    attempts: tuple[GroundingAttempt, ...] = ()


class Stage(Protocol):
    """One composable pipeline step."""

    name: str
    #: Whether the orchestrator may serve this stage's output from the stage cache.
    cacheable: bool
    #: Why not, when it is not. Recorded on the stage record so the refusal is visible in
    #: the artifact rather than only in this file.
    uncacheable_because: str | None
    #: Exceptions this stage isolates. Anything else propagates — swallowing a
    #: `ValidationError` out of `ClaimGraph` would hide the invariant violation the type
    #: system exists to surface.
    isolates: tuple[type[Exception], ...]

    def input_digest(self, ctx: RunContext, graph: ClaimGraph | None) -> str:
        """What this stage is about to be given, digested before it runs."""
        ...

    def run(self, ctx: RunContext, graph: ClaimGraph | None) -> StageResult:
        """Do the work."""
        ...

    def explain(self, error: Exception) -> str:
        """An isolated failure, in the words a reader of the rendered tree needs.

        Required rather than optional, because a stage error otherwise reaches only
        `RunManifest.errors`, which nothing renders. A run whose checkpoint is not installed
        would then draw an unscored column and say nothing about why — which is what the
        column looks like when a scorer ran and refused, so the two would be
        indistinguishable on the one surface a reviewer sees.
        """
        ...


class DecomposeStage:
    name = "decompose"
    cacheable = True
    uncacheable_because = None
    isolates = (DecompositionError, LLMError)

    def input_digest(self, ctx: RunContext, graph: ClaimGraph | None) -> str:
        # Per *claim*, not per step. `DecomposedStep.input_hash` is the descent's unit —
        # under M3-T2 there is one per node — while a stage key has to be computable before
        # anyone knows how many nodes there will be. The two are different granularities of
        # one idea, and the finer one is what the cassette keys on.
        return content_hash(
            self.name,
            ctx.source_digest,
            ctx.config_hash,
            ctx.claim.id,
            ctx.claim.source_text,
        )

    def run(self, ctx: RunContext, graph: ClaimGraph | None) -> StageResult:
        steps = decompose_claim(
            ctx.claim, adapter=ctx.adapter, config=ctx.config.decomposition, now=ctx.now
        )
        built = assemble_graph(
            ctx.claim,
            steps,
            config=ctx.config.decomposition,
            # `config_hash` is stamped here rather than at the end of the run because it is
            # graph *content*, not an execution stamp: the fingerprint that decides whether
            # a re-run changed anything compares it, and a value written after that
            # comparison would make every graph differ from its stored self. `run_id` and
            # `created_at` are the two that identify the execution, and only those are
            # masked and stamped later.
            metadata=GraphMetadata(created_at=ctx.now, config_hash=ctx.config_hash),
            now=ctx.now,
        )
        last = steps[-1]
        return StageResult(
            graph=built,
            output_hash=graph_fingerprint(built),
            llm_calls=len(steps),
            llm_settings=last.llm_settings,
            counts={"steps": len(steps), "premises": len(built.premises)},
            notes=_decomposition_notes(built, ctx),
        )

    def explain(self, error: Exception) -> str:
        return f"the decomposer produced no graph — {type(error).__name__}: {error}"


class VerifyStage:
    name = "verify"
    cacheable = True
    uncacheable_because = None
    # Deliberately not `ValueError`: `pydantic.ValidationError` is one, so isolating it
    # would swallow a `ClaimGraph` invariant violation — the single failure that must
    # always propagate. `UnknownCheckpointError` is the registry refusing a checkpoint it
    # cannot drive, which is a configuration error and not a defect in this run.
    isolates = (ImportError, VerifierError, UnknownCheckpointError)

    def input_digest(self, ctx: RunContext, graph: ClaimGraph | None) -> str:
        from verity.verifier.scoring import input_digest

        assert graph is not None
        # Built from the scorer id the *config* implies rather than from a loaded scorer:
        # constructing one to discover it was not needed would cost a 2GB checkpoint load
        # per cache hit, and would make replay impossible without the `verifier` extra.
        return content_hash(
            self.name,
            ctx.source_digest,
            ctx.config_hash,
            input_digest(graph, ctx.expected_scorer_id),
        )

    def run(self, ctx: RunContext, graph: ClaimGraph | None) -> StageResult:
        from verity.verifier.scoring import score_graph

        assert graph is not None
        scorer = ctx.scorer  # raises ImportError without the extra; isolated above
        if scorer.spec.scorer_id != ctx.expected_scorer_id:
            raise ScorerIdentityError(
                f"the scorer built from this configuration writes "
                f"{scorer.spec.scorer_id!r}, but its cache key was derived from "
                f"{ctx.expected_scorer_id!r}. One checkpoint's numbers would be stored "
                "under another's key"
            )
        result = score_graph(graph, scorer)
        note = None
        if result.oversize_step_ids:
            # The cap itself is already on `graph.metadata.caps`, filed by `score_graph`.
            # This says the same thing in words, and does not file it a second time.
            note = (
                f"{len(result.oversize_step_ids)} step(s) exceeded the checkpoint's "
                f"{scorer.spec.max_input_tokens}-token budget and are unscored"
            )
        return StageResult(
            graph=result.graph,
            output_hash=graph_fingerprint(result.graph),
            counts={"scored": result.scored, "unscored": result.unscored},
            note=note,
        )

    def explain(self, error: Exception) -> str:
        # The reader-facing sentence, not the traceback's. "No module named 'torch'" beside
        # an unscored tree tells a reviewer nothing they can act on; this names the install
        # that fixes it. Everything else keeps its own message, since a scorer that loaded
        # and refused is a different fact about the run.
        if isinstance(error, ImportError):
            return VERIFIER_ABSENT_NOTE
        return f"no step carries a score — {type(error).__name__}: {error}"


class BindStage:
    name = "bind"
    cacheable = False
    uncacheable_because = (
        "its cache is the HTTP transport's, which owns the negative-entry and "
        "degraded-request rules a registry answer needs; and `CacheMode` is deliberately "
        "outside `config_hash()`, so a stage key would let a replay be served a decision "
        "made from live bytes"
    )
    isolates = (RetrievalError,)

    def input_digest(self, ctx: RunContext, graph: ClaimGraph | None) -> str:
        assert graph is not None
        return content_hash(
            self.name,
            ctx.source_digest,
            ctx.config_hash,
            sorted(
                str(p.candidate_key)
                for p in graph.premises.values()
                if p.candidate_key is not None
            ),
        )

    def run(self, ctx: RunContext, graph: ClaimGraph | None) -> StageResult:
        assert graph is not None
        client = ctx.http_client
        bound, report = bind_candidate_keys(graph, client)
        log = client.summary()

        notes = [
            f"candidate-key binding ran in cache mode {ctx.cache_mode.value}: "
            + (
                ", ".join(f"{name} {count}" for name, count in report.counts.items())
                or "nothing to bind"
            )
        ]
        for decision in report.with_outcome(BindingOutcome.COULD_NOT_BE_CHECKED):
            # Not a negative: a transport failure or a spent budget left the question open,
            # and recording it as "did not resolve" would blame the decomposer for the
            # network.
            notes.append(
                f"{decision.candidate_key} could not be checked "
                f"({', '.join(f'{k}: {v}' for k, v in decision.unchecked.items())})"
            )
        if report.with_outcome(BindingOutcome.BOUND):
            # A premise that grounds through a key the *decomposer* proposed is circular
            # evidence and must never be read as the pre-registered grounding rate.
            notes.append(report.basis)

        served = log.requests == 0 or log.served_entirely_from_cache
        return StageResult(
            graph=bound,
            output_hash=graph_fingerprint(bound),
            cache_hits=log.cache_hits,
            caps=[cap for cap in log.caps() if cap.applied],
            counts={**report.counts, "network_calls": log.network_calls},
            notes=notes,
            note=(
                "every registry answer came from disk"
                if served
                else f"{log.network_calls} registry call(s) went to the network"
            ),
        )

    def explain(self, error: Exception) -> str:
        # Load-bearing rather than cosmetic: without binding, no premise carries a bound key
        # and `Alethiology.ground` answers `NO_BOUND_KEY` for every one of them. The
        # grounding column then reads empty because nothing was asked, not because nothing
        # grounded, and only this sentence distinguishes the two.
        return (
            f"no candidate key was checked against a registry, so nothing could ground — "
            f"{type(error).__name__}: {error}"
        )


class GroundStage:
    name = "ground"
    cacheable = False
    uncacheable_because = (
        "design.md §4.2: grounding is non-monotonic — a tree that terminated yesterday can "
        "be un-grounded today — so a grounding result is never cached as permanent"
    )
    isolates = (sqlite3.Error,)

    def input_digest(self, ctx: RunContext, graph: ClaimGraph | None) -> str:
        assert graph is not None
        return content_hash(
            self.name,
            ctx.source_digest,
            # Included for the same reason the other three include it, even though this
            # stage is never cached: a digest that omits the configuration is a trap for
            # whoever changes `cacheable` without re-reading how the key is built.
            ctx.config_hash,
            sorted(
                (p.id, str(p.bound_key))
                for p in graph.premises.values()
                if p.bound_key is not None
            ),
        )

    def run(self, ctx: RunContext, graph: ClaimGraph | None) -> StageResult:
        assert graph is not None
        preserve = ctx.stored_graph.groundings if ctx.stored_graph else ()
        grounded, attempts = apply_groundings(
            graph, ctx.service, grounded_at=ctx.now, preserve_from=preserve
        )

        counts: dict[str, int] = {}
        for attempt in attempts:
            counts[attempt.reason.value] = counts.get(attempt.reason.value, 0) + 1

        notes = []
        for attempt in attempts:
            if attempt.reason.value == "alias-only":
                # An invisible deflation made visible: the premise cites one identifier for
                # a work the alethiology holds under another.
                notes.append(
                    f"{attempt.key} did not ground, but the alethiology holds facts under "
                    f"{', '.join(str(k) for k in attempt.alias_keys)}"
                )

        return StageResult(
            graph=grounded,
            # The reasons are part of the output, not only the groundings: a replay has to
            # be able to see a *diagnosis* change even when the grounded set did not.
            output_hash=content_hash(
                graph_fingerprint(grounded),
                sorted((a.premise_id, a.reason.value) for a in attempts),
            ),
            counts=counts,
            notes=notes,
            attempts=tuple(attempts),
        )

    def explain(self, error: Exception) -> str:
        return (
            f"the alethiology was not consulted, so no premise is grounded — "
            f"{type(error).__name__}: {error}"
        )


def _decomposition_notes(graph: ClaimGraph, ctx: RunContext) -> list[str]:
    """What the decomposition says about itself — derived from the graph, never in flight.

    Both facts are recoverable from the stored artifact, and they have to be read off it:
    a run served from the stage cache never sees a `DecomposedStep`, and notes derived from
    one would leave a cached run rendering with no caveats at all. A polished tree with its
    warnings dropped is precisely the failure design.md §3.4 exists to prevent.
    """
    notes: list[str] = []
    if graph.restating_premise_ids():
        notes.append(
            "a premise restates the claim; that step entails trivially and its score "
            "measures nothing about the decomposition"
        )
    config = ctx.config.decomposition
    for step in graph.steps:
        if not config.min_premises <= step.arity <= config.max_premises:
            # Stored and reported, never corrected (build-plan.md M3-T1): out-of-range
            # arity is a measurement about the decomposer.
            notes.append(
                f"step {step.id} has arity {step.arity}, outside the configured "
                f"{config.min_premises}-{config.max_premises} range"
            )
    return notes


#: The pipeline, in order. A stage's position is a dependency, not a preference: binding
#: needs premises, grounding needs bound keys.
PIPELINE: tuple[Stage, ...] = (DecomposeStage(), VerifyStage(), BindStage(), GroundStage())
