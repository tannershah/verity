"""The orchestrator: run the stages, cache what may be cached, record what happened.

Replaces the throwaway driver M9-T1 wrote. What it adds beyond composition is four things,
and the ordering at the end of `run_claim` is where three of them meet.

**Caching is per stage, and two stages decline it** — see `stages.py` for why. A hit skips
the work and reports zero spend, because a cache hit costs nothing; what the work
*originally* cost travels in the stage's note rather than being added to a total this run
did not pay.

**Failure isolation is not a bare `except`.** Each stage declares the exceptions it
isolates; those are recorded and the pipeline continues with the graph as it stands.
Everything else propagates, because swallowing a `ValidationError` out of `ClaimGraph`
would hide the invariant violation the type system exists to surface. That is affordable
precisely because the cassette holds the provider answers: a crash costs a re-run of
deterministic code, not another call.

**Nothing stored is degraded by a failed run.** The graph is written once, at the end of a
run that produced one — deliberately not checkpointed per stage. `ClaimGraph.id` derives
from the root claim alone and `save_graph` upserts on it, so a per-stage checkpoint would
let a run that crashed at `verify` overwrite the previous fully-scored graph with an
unscored one. The isolation mechanism would have been the data loss.

**The graph is stamped only when its content changed.** A re-run that computed nothing
adopts the stored stamp and is byte-identical; anything else takes this run's. That makes
`claim_graphs.run_id` mean "the run that last produced this content" rather than "the last
process that looked at it".
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import Field

from verity.alethiology.grounding import GroundingAttempt
from verity.base import VerityModel
from verity.cache import BlobCache
from verity.config import VerityConfig
from verity.export import graph_from_json, graph_to_json
from verity.ids import content_hash, make_id
from verity.llm.cassette import CassetteMode
from verity.models.claim import Claim, ClaimGraph
from verity.models.common import utc_now
from verity.models.manifest import (
    LLMSettings,
    RunInputs,
    RunManifest,
    StageRecord,
    Usage,
)
from verity.orchestration.context import RunContext, graph_fingerprint
from verity.orchestration.fingerprint import code_version
from verity.orchestration.stages import PIPELINE, Stage, StageResult
from verity.retrieval.http import CacheMode
from verity.secrets import Secrets
from verity.store.graphs import load_graph, save_graph
from verity.store.manifests import save_manifest

#: Cache namespace for stage outputs. Separate from the cassette's, so one can be cleared
#: without the other.
NAMESPACE = "stage"


class CachedStage(VerityModel):
    """One stage's output, as stored. See `verity.cache` for the on-disk discipline.

    The graph travels as its canonical JSON rather than as a nested model, so a hit
    re-validates it through `ClaimGraph` on the way out — an entry written before a model
    gained a constraint has to read as a miss, not as a graph that skipped the constraint.
    """

    stage: str
    cache_key: str
    graph_payload: str
    output_hash: str
    counts: dict[str, int] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    note: str | None = None
    recorded_usage: Usage = Field(default_factory=Usage)
    recorded_llm_calls: int = 0
    llm_settings: LLMSettings | None = None
    stored_at: datetime


@dataclass
class RunOutcome:
    """What one claim produced. `graph` is None only when decomposition never yielded one."""

    claim: Claim
    manifest: RunManifest
    graph: ClaimGraph | None = None
    attempts: tuple[GroundingAttempt, ...] = ()
    refusal: Exception | None = None
    stage_results: dict[str, StageResult] = field(default_factory=dict)

    @property
    def notes(self) -> list[str]:
        return self.manifest.notes

    @property
    def fully_cached(self) -> bool:
        """Whether every cacheable stage that ran was served rather than computed.

        The exit-criterion property, read off the record rather than asserted. Two
        exclusions, both of which would otherwise make the criterion unmeetable by design:
        stages that decline caching (`bind`, `ground`) cannot report a hit, and a stage the
        caller turned off never had the chance to. At least one hit is required, so a run
        with everything switched off does not read as fully cached.
        """
        cacheable = {stage.name for stage in PIPELINE if stage.cacheable}
        seen = [
            s for s in self.manifest.stages if s.name in cacheable and s.status != "skipped"
        ]
        return bool(seen) and all(s.status == "cache-hit" for s in seen)

    @property
    def reached_nothing_external(self) -> bool:
        """Whether this run made a provider call or a network call. The other half.

        Kept separate from `fully_cached` because they are different claims and conflating
        them hides the interesting middle case: a stage whose cache key moved re-executes
        while its *calls* are still served from the cassette, so the run spends nothing and
        is emphatically not a stage-cache hit. `status` therefore means one thing — the
        stage did not run — and what a stage that did run cost is counted here.
        """
        return not any(
            stage.llm_calls or stage.counts.get("network_calls", 0)
            for stage in self.manifest.stages
        )


def run_claim(
    text: str,
    *,
    config: VerityConfig,
    conn: sqlite3.Connection,
    source_text: str | None = None,
    now: datetime | None = None,
    adapter_factory=None,
    scorer_factory=None,
    cache: BlobCache | None = None,
    score: bool = True,
    bind: bool = True,
    cache_mode: CacheMode = CacheMode.LIVE,
    cassette_mode: CassetteMode = CassetteMode.LIVE,
    use_stage_cache: bool = True,
    persist: bool = True,
) -> RunOutcome:
    """Decompose one claim, score it, bind what resolves, ground what binds, record it all.

    Takes claim *text* rather than a `Claim` so `Claim.created_at` comes from the run clock
    and cannot be forgotten — it is serialized into the graph and contributes nothing to the
    claim's id, so a claim built a moment earlier yields a graph whose ids all match and
    whose bytes do not.

    *(When M2-T1 lands the signature inverts: intake produces a canonical `Claim` carrying
    `claim_type` and `decontextualization`, and this receives one rather than constructing
    it. The invariant that has to survive is "`created_at` comes from the run clock" —
    stamp an incoming claim rather than trusting its own.)*

    `persist=False` runs the pipeline without writing a graph or a manifest, which is what
    replay uses: replay is read-and-compare, and under one-row-per-claim storage a divergent
    replay that wrote would overwrite the artifact it was checking.
    """
    now = now or utc_now()
    claim = Claim(text=text, source_text=source_text, created_at=now)
    cache = cache or BlobCache.open()
    requested = tuple(
        stage.name
        for stage in PIPELINE
        if not (stage.name == "verify" and not score)
        and not (stage.name == "bind" and not bind)
    )
    sha, dirty = code_version()

    ctx = RunContext(
        claim=claim,
        config=config,
        conn=conn,
        now=now,
        cache=cache,
        cache_mode=cache_mode,
        stored_graph=load_graph(conn, make_id("graph", claim.id)),
        use_stage_cache=use_stage_cache,
        adapter_factory=adapter_factory,
        scorer_factory=scorer_factory,
        cassette_mode=cassette_mode,
    )
    manifest = RunManifest(
        run_id=make_id("run", claim.id, ctx.config_hash, now.isoformat()),
        started_at=now,
        inputs=RunInputs(
            claim_text=text,
            source_text=source_text,
            cache_mode=cache_mode.value,
            stages_requested=requested,
        ),
        code_version=sha,
        code_dirty=dirty,
        config=config.snapshot(),
        credentials_configured=Secrets().configured(),
    )

    outcome = RunOutcome(claim=claim, manifest=manifest)
    try:
        _execute(ctx, manifest, outcome, requested)
    finally:
        manifest.finished_at = utc_now()
        if persist:
            save_manifest(conn, manifest)
    return outcome


def _execute(
    ctx: RunContext, manifest: RunManifest, outcome: RunOutcome, requested: tuple[str, ...]
) -> None:
    graph: ClaimGraph | None = None

    for stage in PIPELINE:
        if stage.name not in requested:
            manifest.stages.append(
                _skipped(stage, ctx, "not requested for this run")
            )
            _warn_on_skipped_output(stage, ctx, manifest)
            continue
        if graph is None and stage.name != "decompose":
            manifest.stages.append(_skipped(stage, ctx, "no graph to work on"))
            continue

        record, result, error = _run_stage(stage, ctx, graph)
        manifest.stages.append(record)
        if result is None:
            if stage.name == "decompose":
                # Kept as the exception itself, not re-raised from its message: a caller
                # reporting a refusal prints the type and the usage of the call that
                # produced it, and a rebuilt error has neither.
                outcome.refusal = error
            manifest.errors.append(f"{stage.name}: {record.error}")
            continue

        graph = result.graph
        outcome.stage_results[stage.name] = result
        manifest.notes.extend(result.notes)
        if result.attempts:
            outcome.attempts = result.attempts

    if graph is None:
        return
    outcome.graph = _stamp(graph, ctx, manifest)
    manifest.graph_ids.append(outcome.graph.id)


def _run_stage(
    stage: Stage, ctx: RunContext, graph: ClaimGraph | None
) -> tuple[StageRecord, StageResult | None, Exception | None]:
    """Serve or run one stage, returning its record, its result, and any isolated error."""
    started_at = utc_now()
    clock = time.perf_counter()

    def elapsed() -> float:
        return (time.perf_counter() - clock) * 1000.0

    digest = stage.input_digest(ctx, graph)
    cache_key = content_hash(NAMESPACE, digest) if stage.cacheable else None
    if cache_key is not None and ctx.use_stage_cache:
        served = _serve(stage, ctx, cache_key, digest, started_at, elapsed)
        if served is not None:
            return (*served, None)

    try:
        result = stage.run(ctx, graph)
    except stage.isolates as error:
        return (
            _error_record(stage, started_at, elapsed(), error, digest, cache_key),
            None,
            error,
        )

    record = _ok_record(stage, ctx, result, started_at, elapsed(), digest, cache_key)
    if cache_key is not None:
        _store(ctx, stage, cache_key, result)
    return record, result, None


def _serve(
    stage: Stage,
    ctx: RunContext,
    cache_key: str,
    digest: str,
    started_at: datetime,
    elapsed,
) -> tuple[StageRecord, StageResult] | None:
    """A cache hit, rebuilt into a result this run can carry — or None if there is none."""
    entry = ctx.cache.get(NAMESPACE, cache_key, CachedStage)
    if entry is None:
        return None
    try:
        graph = graph_from_json(entry.graph_payload)
    except ValueError:
        # A stored graph that no longer validates is a miss, not a crash: the models can
        # gain a constraint between the write and the read.
        return None

    result = StageResult(
        graph=graph,
        output_hash=entry.output_hash,
        cache_hits=1,
        counts=entry.counts,
        notes=entry.notes,
        note=entry.note,
        llm_settings=entry.llm_settings,
    )
    cost = entry.recorded_usage
    served = (
        f"served from cache; the recorded run made {entry.recorded_llm_calls} LLM call(s) "
        f"costing ${cost.cost_usd:.4f}"
        if entry.recorded_llm_calls
        else "served from cache"
    )
    record = StageRecord(
        name=stage.name,
        started_at=started_at,
        duration_ms=elapsed(),
        status="cache-hit",
        cache_hits=1,
        counts=entry.counts,
        input_hash=digest,
        cache_key=cache_key,
        output_hash=entry.output_hash,
        llm_settings=entry.llm_settings,
        note=served if entry.note is None else f"{served}. {entry.note}",
    )
    return record, result


def _store(ctx: RunContext, stage: Stage, cache_key: str, result: StageResult) -> None:
    ctx.cache.put(
        NAMESPACE,
        cache_key,
        CachedStage(
            stage=stage.name,
            cache_key=cache_key,
            graph_payload=graph_to_json(result.graph),
            output_hash=result.output_hash,
            counts=result.counts,
            notes=result.notes,
            note=result.note,
            recorded_usage=result.usage,
            recorded_llm_calls=result.llm_calls,
            llm_settings=result.llm_settings,
            stored_at=utc_now(),
        ),
    )


def _ok_record(
    stage: Stage,
    ctx: RunContext,
    result: StageResult,
    started_at: datetime,
    duration_ms: float,
    digest: str,
    cache_key: str | None,
) -> StageRecord:
    spent, replayed, provider_calls, hits, truncated = _cassette_accounting(ctx, result)
    note = result.note
    if hits:
        served = (
            f"{hits} provider call(s) replayed from the cassette "
            f"(recorded cost ${replayed.cost_usd:.4f})"
        )
        note = served if note is None else f"{note}. {served}"
    if not stage.cacheable and stage.uncacheable_because:
        note = (
            f"not cached: {stage.uncacheable_because}"
            if note is None
            else f"{note}. Not cached: {stage.uncacheable_because}"
        )
    return StageRecord(
        name=stage.name,
        started_at=started_at,
        duration_ms=duration_ms,
        # The stage ran. `cache-hit` is reserved for a stage that did not — a status that
        # meant "ran, but cheaply" as well would make the exit criterion unreadable off the
        # record, since a stage whose key moved but whose calls were all replayed looks
        # identical to one that was skipped entirely.
        status="ok",
        #: Calls that actually reached the provider. A replayed one is a `cache_hit`.
        llm_calls=provider_calls,
        usage=spent,
        cache_hits=result.cache_hits + hits,
        caps=result.caps,
        counts=result.counts,
        note=note,
        input_hash=digest,
        cache_key=cache_key,
        output_hash=result.output_hash,
        llm_settings=result.llm_settings,
        truncated_calls=truncated,
    )


def _cassette_accounting(
    ctx: RunContext, result: StageResult
) -> tuple[Usage, Usage, int, int, int]:
    """Split what a stage's LLM calls cost this run from what the replayed ones cost before.

    `(spent, replayed, provider calls, cassette hits, truncated)`. A cache hit costs
    nothing, so `spent` excludes it and what it originally cost travels in the note — a
    total that added both would report money this run did not pay.
    """
    adapter = ctx.cassette
    if adapter is None or not result.llm_calls:
        return result.usage, Usage(), result.llm_calls, 0, result.truncated_calls
    return (
        adapter.spent,
        adapter.replayed,
        adapter.provider_calls,
        adapter.hits,
        adapter.truncated_calls,
    )


def _skipped(stage: Stage, ctx: RunContext, why: str) -> StageRecord:
    return StageRecord(
        name=stage.name,
        started_at=utc_now(),
        duration_ms=0.0,
        status="skipped",
        note=why,
    )


def _error_record(
    stage: Stage,
    started_at: datetime,
    duration_ms: float,
    error: Exception,
    digest: str | None = None,
    cache_key: str | None = None,
) -> StageRecord:
    usage = getattr(error, "usage", None)
    return StageRecord(
        name=stage.name,
        started_at=started_at,
        duration_ms=duration_ms,
        status="error",
        error=f"{type(error).__name__}: {error}",
        # A refusal raised after the call carries that call's usage, so a branch that cost
        # money and yielded no step is still counted against the run.
        usage=usage if isinstance(usage, Usage) else Usage(),
        input_hash=digest,
        cache_key=cache_key,
    )


def _warn_on_skipped_output(stage: Stage, ctx: RunContext, manifest: RunManifest) -> None:
    """Say so when skipping a stage will drop output the stored graph already has.

    Storage is one row per claim, so this run's graph replaces the previous one. Skipping
    `verify` on a claim whose stored graph carries scores loses them. A stated loss rather
    than a silent one; whether to accept it is the caller's.
    """
    stored = ctx.stored_graph
    if stored is None:
        return
    if stage.name == "verify" and any(step.score is not None for step in stored.steps):
        manifest.notes.append(
            "this run skipped scoring; the stored graph for this claim carried scores and "
            "the run that replaces it does not"
        )
    if stage.name == "bind" and any(p.bound_key for p in stored.premises.values()):
        manifest.notes.append(
            "this run skipped binding; the stored graph for this claim carried bound keys "
            "and the run that replaces it does not"
        )


def _stamp(graph: ClaimGraph, ctx: RunContext, manifest: RunManifest) -> ClaimGraph:
    """Give the graph this run's stamp, unless this run changed nothing.

    Compared with the run stamps masked, because on a cache hit `assemble_graph` writes
    this run's clock into `metadata.created_at` while the cached steps keep the previous
    run's — an unmasked comparison always differs, and the rule would degenerate into
    stamping always, which is the thing it exists to avoid.
    """
    stored = ctx.stored_graph
    unchanged = stored is not None and graph_fingerprint(stored) == graph_fingerprint(graph)
    run_id = stored.metadata.run_id if unchanged and stored else manifest.run_id
    created_at = stored.metadata.created_at if unchanged and stored else ctx.now
    metadata = graph.metadata.model_copy(update={"run_id": run_id, "created_at": created_at})
    # Rebuilt rather than mutated, so construction re-runs every invariant.
    return ClaimGraph(
        root_claim=graph.root_claim,
        premises=graph.premises,
        steps=graph.steps,
        groundings=graph.groundings,
        bundles=graph.bundles,
        metadata=metadata,
    )


def store_outcome(
    conn: sqlite3.Connection, outcome: RunOutcome, out: Path | None = None
) -> None:
    """Write the graph once, at the end of a run that produced one."""
    if outcome.graph is None:
        return
    save_graph(conn, outcome.graph)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(graph_to_json(outcome.graph), encoding="utf-8")
