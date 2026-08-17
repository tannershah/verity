"""Deterministic replay: re-execute a recorded run and say whether it reproduced.

**Replay is not a cache read.** It pins the clock to the run's own, forces the cassette to
replay-only and the HTTP client to `OFFLINE`, and then **turns the stage cache off** — so
every deterministic line runs again against the provider answers the original run received.
A replay that reproduces the graph has re-derived it, which is the whole point: a stage
cache trusted at replay time would report success for a codebase that had silently changed
underneath its stored results.

**Replay writes nothing.** Storage is one row per claim, so a divergent replay that wrote
would overwrite the artifact it was checking with the wrong version of it. Its product is a
report.

**The grounding stage is allowed to differ, and that is a finding rather than a failure.**
Grounding is non-monotonic (design.md §4.2): if the alethiology has moved since the run,
the same code on the same inputs legitimately reaches a different answer. The report keeps
that separate from a decompose, verify or bind hash that moved, which is drift.

**A stage the two machines did not both produce is not a stage that disagreed**, and this
holds in both directions. The reviewer this claim exists for follows the README's base
install, which has no `verifier` extra — so `verify` raises `ImportError`, produces no
digest, and a missing optional dependency must not emit the strongest negative signal the
tool has. The mirror is just as real: a run recorded *before* the extra was installed,
replayed after it, produced more than the recording rather than something different. So the
comparison keys on which side produced a digest, never on either side's status.

**And a gap contaminates everything downstream of it.** `bind` and `ground` digest the whole
graph, not their own increment, so a graph missing `verify`'s scores differs from one
carrying them at every later stage — for a reason that says nothing about whether the later
stage's code reproduces. Comparing them anyway is what made the README's own base install
report `DRIFT in bind`: the strongest negative signal the tool has, emitted because an
optional dependency was absent. Once a stage is incomparable, every stage after it is too.

Three outcomes rather than two. `reproduced` means every comparable stage matched and
nothing was left unchecked; `drifted` means code moved, and is the only failure; `incomplete`
means the two machines were not in the same condition, which is a statement about the
environment. An incomplete replay also declines to compare the whole graph — a graph missing
one side's stage output is an unfinished comparison, not a mismatch.
"""

from __future__ import annotations

import sqlite3

from pydantic import Field

from verity.base import VerityModel
from verity.cache import BlobCache
from verity.config import VerityConfig
from verity.llm.cassette import CassetteMode
from verity.models.manifest import RunManifest
from verity.orchestration.context import graph_fingerprint
from verity.orchestration.pipeline import RunOutcome, run_claim
from verity.orchestration.stages import PIPELINE
from verity.retrieval.http import CacheMode
from verity.store.graphs import load_graph
from verity.store.manifests import load_manifest


def _may_differ(stage_name: str) -> str | None:
    """Why `stage_name` is entitled to a different answer on replay, or None if it is not.

    Read off the stage's own `may_differ_because` rather than from a list here. A list has to
    be edited by whoever adds a stage, and it fails silently in the permissive direction — an
    unlisted stage would be excused from every drift check, so its regressions would never be
    reported. Today exactly one stage answers non-None: `ground`, whose input is a store that
    is allowed to have moved.

    A stage in an old manifest that no longer exists is treated as deterministic, which
    reports a difference it cannot explain rather than excusing one. `verdict` then has
    something to cite, which is the invariant that direction protects.
    """
    stage = next((s for s in PIPELINE if s.name == stage_name), None)
    return stage.may_differ_because if stage is not None else None


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
    #: False when either side produced no digest — the stage was skipped, or it failed on
    #: one of the two machines. Two absent hashes must not compare equal (a stage nobody ran
    #: would read as reproduced), and one absent hash must not compare unequal (a stage this
    #: machine could not run would read as drift).
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
    def incomplete(self) -> bool:
        """Whether this machine could not re-execute part of the run.

        A statement about the environment, not about the code — kept apart from `drifted`
        because conflating them makes an absent optional dependency indistinguishable from
        a regression.
        """
        return bool(self.partial_because)

    @property
    def unexplained_divergence(self) -> bool:
        """The graph differs while nothing entitled to differ did.

        `ground` is allowed to move — the alethiology is not frozen — so a graph difference
        it accounts for is a finding, not a defect. A difference nothing accounts for is a
        real defect, and it needs its own name: an earlier version folded it into the
        verdict directly, which turned the *documented good case* of a moved store into
        `drifted` with an empty `drifted` list — a failure verdict citing no stage.
        """
        return (
            self.graph_matches is False and not self.drifted and not self.grounding_moved
        )

    @property
    def verdict(self) -> str:
        """`reproduced | drifted | incomplete`.

        The invariant: **a `drifted` verdict always cites something** — a stage in
        `drifted`, or `unexplained_divergence`. Anything else that merely differs is either
        an environment gap (`incomplete`) or a store that moved, which is reported beside
        the verdict rather than inside it.
        """
        if self.drifted or self.unexplained_divergence:
            return "drifted"
        if self.incomplete or self.graph_matches is None:
            return "incomplete"
        return "reproduced"

    @property
    def reproduced(self) -> bool:
        return self.verdict == "reproduced"


def replay_run(
    run_id: str,
    *,
    conn: sqlite3.Connection,
    cache: BlobCache | None = None,
    db_override: bool = False,
    scorer_factory=None,
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
        scorer_factory=scorer_factory,
        score="verify" in requested,
        bind="bind" in requested,
        cache_mode=CacheMode.OFFLINE,
        cassette_mode=CassetteMode.REPLAY,
        use_stage_cache=False,
        persist=False,
    )

    report = ReplayReport(run_id=run_id, notes=list(outcome.notes))
    if db_override:
        # A note, not a partial. `partial_because` means "this machine could not re-execute
        # something", and an overridden store prevents nothing from re-executing — it only
        # changes which alethiology `ground` read, and `ground` is already the stage allowed
        # to differ. Filing it as a partial would make every `--db` replay report
        # `incomplete`, which is the noise that hides a genuinely incomplete one.
        report.notes.append(
            "the store was overridden, so the alethiology this replay read is not the one "
            "the run recorded"
        )

    _compare_stages(manifest, outcome, report)

    stored = load_graph(conn, manifest.graph_ids[0]) if manifest.graph_ids else None
    if stored is not None and outcome.graph is not None and not report.incomplete:
        # Left `None` when the replay was incomplete: a graph missing the output of a stage
        # one side could not run differs from the other for a reason that says nothing
        # about whether the code reproduces.
        report.graph_matches = graph_fingerprint(stored) == graph_fingerprint(outcome.graph)
    return report


def _compare_stages(
    manifest: RunManifest, outcome: RunOutcome, report: ReplayReport
) -> None:
    """Digest against digest, per stage, recording what could not be compared and why.

    Keyed on which side produced a digest, never on either side's status — status is only a
    proxy for that, and reading it in one direction is what left the mirror case reporting
    `drifted` with an empty `drifted` list. One side having output the other does not means
    the two machines were not in the same condition, whichever side is the richer one: the
    recording was made without the `verifier` extra and this machine has it, or the reverse.
    Neither is a disagreement about a result. Both sides empty is not a partial — a stage
    neither run produced was expected of neither.

    A one-sided stage also disqualifies every stage after it, because the later ones digest
    the graph rather than their own contribution: `bind`'s hash moves when `verify` did not
    run on both machines, and reading that as drift blames the binder for a missing
    checkpoint. Stages arrive in pipeline order, so one forward-carried flag is enough.
    """
    fresh = {stage.name: stage for stage in outcome.manifest.stages}
    upstream_gap: str | None = None
    for stage in manifest.stages:
        replayed = fresh.get(stage.name)
        replayed_hash = replayed.output_hash if replayed else None
        one_sided = (stage.output_hash is None) != (replayed_hash is None)

        if stage.output_hash is not None and replayed_hash is None:
            report.partial_because.append(
                f"{stage.name} could not be re-executed here"
                + (f": {replayed.error}" if replayed and replayed.error else "")
            )
        elif stage.output_hash is None and replayed_hash is not None:
            report.partial_because.append(
                f"{stage.name} produced output here that the recorded run did not, so "
                "there is nothing to compare it against"
                + (f" (the run recorded: {stage.error})" if stage.error else "")
            )

        comparable = stage.output_hash is not None and replayed_hash is not None
        if comparable and upstream_gap is not None:
            comparable = False
            report.partial_because.append(
                f"{stage.name} digests the whole graph, and {upstream_gap} did not run on "
                "both machines, so its hash compares two different graphs rather than two "
                "runs of the same code"
            )
        if one_sided:
            upstream_gap = upstream_gap or stage.name

        report.stages.append(
            StageComparison(
                stage=stage.name,
                recorded=stage.output_hash,
                replayed=replayed_hash,
                matches=comparable and replayed_hash == stage.output_hash,
                may_differ=_may_differ(stage.name) is not None,
                comparable=comparable,
            )
        )
