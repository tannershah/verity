"""Deterministic replay: re-execute a recorded run and say whether it reproduced.

**Replay is not a cache read.** It pins the clock to the run's own, forces the cassette to
replay-only and the HTTP client to `REPLAY`, and then **turns the stage cache off** — so
every deterministic line runs again against the provider answers the original run received.
A replay that reproduces the graph has re-derived it. A replay that does not has found
drift, which is the whole point: a stage cache trusted at replay time would report success
for a codebase that had silently changed underneath its stored results.

**Replay writes nothing.** Storage is one row per claim, so a divergent replay that wrote
would overwrite the artifact it was checking with the wrong version of it. Its product is a
report.

**The grounding stage is allowed to differ, and that is a finding rather than a failure.**
Grounding is non-monotonic (design.md §4.2): if the alethiology has moved since the run,
the same code on the same inputs legitimately reaches a different answer. The report keeps
that separate from a decompose, verify or bind hash that moved, which is drift.

**Verify is the one stage replay may serve from cache.** Re-executing it needs the ~2GB
`verifier` extra, and requiring that of the reviewer the reproducibility claim exists for
would make the claim unexercisable. When it is served, or cannot run at all, the report
says the replay was partial and why.
"""

from __future__ import annotations

import sqlite3

from pydantic import Field

from verity.base import VerityModel
from verity.cache import BlobCache
from verity.config import VerityConfig
from verity.llm.cassette import CassetteMode
from verity.orchestration.context import graph_fingerprint
from verity.orchestration.pipeline import run_claim
from verity.retrieval.http import CacheMode
from verity.store.graphs import load_graph
from verity.store.manifests import load_manifest

#: Stages whose output hash must match for a replay to count as a reproduction. `ground` is
#: excluded because the store it reads is allowed to have moved.
DETERMINISTIC = ("decompose", "verify", "bind")


class ReplayError(RuntimeError):
    """The recorded run cannot be replayed from what was stored."""


class StageComparison(VerityModel):
    """One stage's recorded digest against the one the replay produced."""

    stage: str
    recorded: str | None = None
    replayed: str | None = None
    matches: bool = False
    #: True for `ground`, whose inputs are a store that is allowed to have changed.
    may_differ: bool = False
    #: False when the recorded run produced no digest for this stage — it was skipped or it
    #: failed. Two absent hashes are not a reproduction, and letting them compare equal
    #: would report a stage nobody ran as one that reproduced.
    comparable: bool = True


class ReplayReport(VerityModel):
    """What a replay found."""

    run_id: str
    stages: list[StageComparison] = Field(default_factory=list)
    #: None when the original run stored no graph to compare against.
    graph_matches: bool | None = None
    #: Reasons this replay is not a full re-execution. Empty means it was.
    partial_because: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def drifted(self) -> list[StageComparison]:
        """Deterministic stages whose output moved. Any entry here is a defect."""
        return [s for s in self.stages if s.comparable and not s.may_differ and not s.matches]

    @property
    def grounding_moved(self) -> bool:
        """Whether the alethiology answered differently than it did for the recorded run."""
        return any(s.comparable and s.may_differ and not s.matches for s in self.stages)

    @property
    def reproduced(self) -> bool:
        return not self.drifted and self.graph_matches is not False


def replay_run(
    run_id: str,
    *,
    conn: sqlite3.Connection,
    cache: BlobCache | None = None,
    db_override: bool = False,
) -> ReplayReport:
    """Re-execute the run `run_id` recorded, and compare what comes out."""
    manifest = load_manifest(conn, run_id)
    if manifest is None:
        raise ReplayError(f"no run {run_id!r} in this store")
    if manifest.inputs is None:
        raise ReplayError(
            f"run {run_id!r} predates the input record, so its claim cannot be "
            "reconstructed; re-run it rather than guessing at what it was given"
        )

    # Rebuilt from the snapshot rather than the environment: replaying under a config the
    # run did not use reproduces a different run.
    config = VerityConfig(**manifest.config)
    requested = set(manifest.inputs.stages_requested)

    outcome = run_claim(
        manifest.inputs.claim_text,
        source_text=manifest.inputs.source_text,
        config=config,
        conn=conn,
        now=manifest.started_at,
        cache=cache or BlobCache.open(writable=False),
        score="verify" in requested,
        bind="bind" in requested,
        cache_mode=CacheMode.REPLAY,
        cassette_mode=CassetteMode.REPLAY,
        use_stage_cache=False,
        persist=False,
    )

    report = ReplayReport(run_id=run_id, notes=list(outcome.notes))
    if db_override:
        report.partial_because.append(
            "the store was overridden, so the alethiology this replay read is not the one "
            "the run recorded"
        )

    fresh = {stage.name: stage for stage in outcome.manifest.stages}
    for stage in manifest.stages:
        name = stage.name
        replayed = fresh.get(name)
        if replayed is not None and replayed.status == "cache-hit" and name == "verify":
            report.partial_because.append(
                "verify was served from the stage cache rather than re-executed"
            )
        if replayed is not None and replayed.status == "error":
            report.partial_because.append(f"{name} could not run: {replayed.error}")
        comparable = stage.output_hash is not None
        report.stages.append(
            StageComparison(
                stage=name,
                recorded=stage.output_hash,
                replayed=replayed.output_hash if replayed else None,
                matches=comparable
                and bool(replayed and replayed.output_hash == stage.output_hash),
                may_differ=name not in DETERMINISTIC,
                comparable=comparable,
            )
        )

    stored = load_graph(conn, manifest.graph_ids[0]) if manifest.graph_ids else None
    if stored is not None and outcome.graph is not None:
        report.graph_matches = graph_fingerprint(stored) == graph_fingerprint(outcome.graph)
    return report
