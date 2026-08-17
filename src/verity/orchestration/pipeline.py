"""The orchestrator: run the stages, cache what may be cached, record what happened.

Replaces the throwaway driver M9-T1 wrote. Four things it adds beyond composition.

**Caching is per stage, and two stages decline it** — see `stages.py` for why. A hit skips
the work and reports zero spend, because a cache hit costs nothing; what the work
*originally* cost travels in the stage's note rather than being added to a total this run
did not pay.

**Failure isolation is not a bare `except`.** Each stage declares the exceptions it
isolates; those are recorded, explained to the reader, and the pipeline continues with the
graph as it stands. Everything else propagates, because swallowing a `ValidationError` out
of `ClaimGraph` would hide the invariant violation the type system exists to surface. That
is affordable precisely because the cassette holds the provider answers: a crash costs a
re-run of deterministic code, not another call.

A stage that ran and a stage that failed take the same path through `_record`. A failure is
a completion with no output, not a different kind of event, and the one time they had
separate builders the failure path silently skipped every piece of bookkeeping the success
path did.

**A failed run stores nothing; a failed stage stores what it has, and says what that
cost.** The graph is written once, at the end of a run that produced one — deliberately not
checkpointed per stage, since `ClaimGraph.id` derives from the root claim alone and
`save_graph` upserts on it, so a checkpoint would let a run that crashed at `verify`
overwrite a fully-scored graph with an unscored one. But an *isolated* stage failure still
yields a graph, and that graph still replaces the stored one, so `_report_lost_output`
compares what is about to be written against what is there. Storage is one row per claim;
the loss is the caller's to accept, never the run's to hide.

**The graph is stamped only when its content changed.** A re-run that computed nothing
adopts the stored stamp and is byte-identical; anything else takes this run's. That makes
`claim_graphs.run_id` mean "the run that last produced this content" rather than "the last
process that looked at it".
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import Field

from verity.alethiology.grounding import GroundingAttempt
from verity.base import VerityModel
from verity.cache import BlobCache
from verity.config import VerityConfig
from verity.export import graph_from_json, graph_to_json
from verity.ids import content_hash, make_id
from verity.llm.cassette import CassetteMode, CassetteUsage
from verity.models.claim import Claim, ClaimGraph
from verity.models.common import CapRecord, utc_now
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
    #: Execution-scoped caps the stage filed. None today — the cacheable stages file their
    #: caps on `graph.metadata.caps`, which travels inside the payload — and carried anyway,
    #: because the first execution-scoped cap on a cacheable stage would otherwise become a
    #: silent cap on every hit, which is the one thing evaluation.md §6 forbids outright.
    caps: list[CapRecord] = Field(default_factory=list)
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
        _execute(ctx, manifest, outcome, requested, persist=persist)
    finally:
        manifest.finished_at = utc_now()
        if persist:
            save_manifest(conn, manifest)
    return outcome


def _execute(
    ctx: RunContext,
    manifest: RunManifest,
    outcome: RunOutcome,
    requested: tuple[str, ...],
    *,
    persist: bool,
) -> None:
    graph: ClaimGraph | None = None

    for stage in PIPELINE:
        if stage.name not in requested:
            manifest.stages.append(_skipped(stage, "not requested for this run"))
            continue
        if graph is None and stage.name != "decompose":
            manifest.stages.append(_skipped(stage, "no graph to work on"))
            continue

        record, result, error = _run_stage(stage, ctx, graph)
        manifest.stages.append(record)
        if result is None:
            assert error is not None, "a stage with no result must have raised"
            if stage.name == "decompose":
                # Kept as the exception itself, not re-raised from its message: a caller
                # reporting a refusal prints the type and the usage of the call that
                # produced it, and a rebuilt error has neither.
                outcome.refusal = error
            manifest.errors.append(f"{stage.name}: {record.error}")
            # A failure a reader can act on is a note, not only an error. `errors` is the
            # machine-readable record and nothing renders it; a run whose scorer is not
            # installed must say so where the tree is drawn, or it shows an unscored
            # column with no explanation at all.
            manifest.notes.append(stage.explain(error))
            continue

        graph = result.graph
        manifest.notes.extend(result.notes)
        if result.attempts:
            outcome.attempts = result.attempts

    if graph is None:
        return
    outcome.graph = _stamp(graph, ctx, manifest)
    manifest.graph_ids.append(outcome.graph.id)
    if persist:
        _report_lost_output(ctx, manifest, outcome.graph)


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

    # Where this stage's calls begin; see `CassetteAdapter.usage_since` for why a span
    # rather than a running total.
    first_call = ctx.cassette_calls_so_far

    try:
        result = stage.run(ctx, graph)
    except stage.isolates as error:
        calls = _accounting(ctx, first_call, None)
        return (
            _record(stage, started_at, elapsed(), digest, cache_key, calls, error=error),
            None,
            error,
        )

    # One computation, used by both the record and the cache entry. Two would let the
    # manifest report the provider calls this run made while the entry stored the calls the
    # stage issued, and the cache-hit note then pairs one run's count with another's cost.
    calls = _accounting(ctx, first_call, result)
    record = _record(stage, started_at, elapsed(), digest, cache_key, calls, result=result)
    if cache_key is not None:
        _store(ctx, stage, cache_key, result, calls)
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
    if entry.output_hash != graph_fingerprint(graph):
        # The entry's own two halves disagree, so one of them is not what it says it is.
        # Serving it would put a digest describing no graph into the manifest — and that
        # digest is precisely what a replay compares against, so a corrupt entry would
        # surface as drift in code that never changed. Cacheable stages set
        # `output_hash = graph_fingerprint(graph)`, which is what makes this checkable.
        return None

    result = StageResult(
        graph=graph,
        output_hash=entry.output_hash,
        cache_hits=1,
        counts=entry.counts,
        notes=entry.notes,
        note=entry.note,
        caps=entry.caps,
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


def _store(
    ctx: RunContext, stage: Stage, cache_key: str, result: StageResult, calls: CassetteUsage
) -> None:
    """Record what producing this output costs from cold.

    Not what the recording run happened to pay: a run whose own calls were replayed paid
    nothing, and storing that would make every later hit report a saving of $0.0000 for work
    that costs real money to produce. `spent + replayed` is the number the cache-hit note
    means, and taking both halves from one accounting keeps the count and the cost describing
    the same set of calls.
    """
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
            caps=result.caps,
            recorded_usage=calls.spent + calls.replayed,
            recorded_llm_calls=calls.provider_calls + calls.hits,
            llm_settings=result.llm_settings,
            stored_at=utc_now(),
        ),
    )


def _record(
    stage: Stage,
    started_at: datetime,
    duration_ms: float,
    digest: str,
    cache_key: str | None,
    calls: CassetteUsage,
    *,
    result: StageResult | None = None,
    error: Exception | None = None,
) -> StageRecord:
    """One record builder for a stage that ran, whether or not it produced anything.

    Deliberately not two. A failure is a completion with no output, not a different kind of
    event, and giving it its own builder is what made a refused run report the recorded cost
    of a replayed call as money spent while `llm_calls` stayed at zero — so the run claimed
    it had reached nothing external in the one case where it had reached the provider and
    paid. Everything that describes *how a stage ran* is therefore computed once, in
    `_run_stage`, and handed to this and to the cache entry alike.
    """
    note = result.note if result else None
    if calls.hits:
        served = (
            f"{calls.hits} provider call(s) replayed from the cassette "
            f"(recorded cost ${calls.replayed.cost_usd:.4f})"
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
        status="error" if error is not None else "ok",
        error=f"{type(error).__name__}: {error}" if error is not None else None,
        #: Calls that actually reached the provider. A replayed one is a `cache_hit`.
        llm_calls=calls.provider_calls,
        usage=calls.spent,
        cache_hits=(result.cache_hits if result else 0) + calls.hits,
        caps=result.caps if result else [],
        counts=result.counts if result else {},
        note=note,
        input_hash=digest,
        cache_key=cache_key,
        output_hash=result.output_hash if result else None,
        llm_settings=result.llm_settings if result else None,
        truncated_calls=calls.truncated,
    )


def _accounting(ctx: RunContext, first_call: int, result: StageResult | None) -> CassetteUsage:
    """What *this stage's* calls cost this run, over the span it opened.

    The cassette is the authority on the success path and the failure path alike: a
    `DecompositionError` carries the usage of the *envelope* that produced it, and on a
    replayed call that envelope is the recorded one — real money the first time and zero
    every time after, from a field that cannot tell the difference.
    """
    adapter = ctx.cassette
    if adapter is None:
        # No provider was ever constructed, so nothing went through one. A stage that
        # nonetheless reports calls is a hand-wired test double; take it at its word.
        return CassetteUsage(
            spent=result.usage if result else Usage(),
            provider_calls=result.llm_calls if result else 0,
            truncated=result.truncated_calls if result else 0,
        )
    return adapter.usage_since(first_call)


def _skipped(stage: Stage, why: str) -> StageRecord:
    return StageRecord(
        name=stage.name,
        started_at=utc_now(),
        duration_ms=0.0,
        status="skipped",
        note=why,
    )


def _report_lost_output(
    ctx: RunContext, manifest: RunManifest, graph: ClaimGraph
) -> None:
    """Say so when this run's graph drops output the stored one already carried.

    Compared against the *artifact* rather than attached to any one branch. An earlier
    version fired only when a stage was skipped by request, which left the case that
    matters most silent: an isolated stage error still yields a graph, `store_outcome` still
    writes it, and a checkpoint that failed to load would quietly replace a scored graph
    with an unscored one. That is the same failure the per-stage checkpoint was withdrawn to
    prevent — the isolation mechanism becoming the data loss — and it does not care why the
    output is missing, so neither does this.

    Groundings are excluded on purpose: a grounding that disappears is the alethiology
    having moved (design.md §4.2), which is a finding rather than a loss.

    Called only when the run persists. A replay runs the pipeline with `persist=False`
    precisely so it cannot overwrite the artifact it is checking, so nothing it computes can
    lose anything — and reporting a loss there told a reviewer whose base install cannot
    score that the tool had just destroyed the scores in their store.
    """
    stored = ctx.stored_graph
    if stored is None:
        return
    losses = (
        (
            "scores",
            any(step.score is not None for step in stored.steps),
            any(step.score is not None for step in graph.steps),
        ),
        (
            "bound keys",
            any(p.bound_key for p in stored.premises.values()),
            any(p.bound_key for p in graph.premises.values()),
        ),
    )
    for what, had, has in losses:
        if had and not has:
            manifest.notes.append(
                f"the stored graph for this claim carried {what} and the run replacing it "
                f"does not; that output is gone from the store"
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
