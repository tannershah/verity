"""The pipeline's command line.

    python -m verity run "A misplaced decimal point made spinach famous…"
    python -m verity run --pilot
    python -m verity replay run_dc9883fc4529984d
    python -m verity render data/demo/spinach.json
    python -m verity runs

`render` costs nothing and needs no key — it draws a committed graph against the current
alethiology. `run` executes the pipeline and may spend money; a second run of the same
claim spends nothing, which is the property `replay` then checks by re-deriving the graph
rather than reading it back.

**An undeclared failure is caught here and nowhere below.** The library re-raises anything
a stage did not declare, because swallowing it would hide an invariant violation; a demo,
though, should print it and exit non-zero rather than showing a traceback. The manifest is
already on disk by then — it is written in a `finally` — and the cassette holds every
provider answer the run paid for, so nothing is lost by stopping.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verity.cache import BlobCache
from verity.config import load_config
from verity.orchestration import ReplayError, RunOutcome, replay_run, run_claim, store_outcome
from verity.presentation import __main__ as render_surface
from verity.retrieval.http import CacheMode
from verity.store.db import open_db
from verity.store.manifests import list_run_ids, load_manifest

PILOT = Path("data/claimsets/pilot.jsonl")


def _claims(args) -> list[tuple[str, str | None]]:
    if args.pilot:
        rows = [
            json.loads(line)
            for line in PILOT.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [(row["text"], row.get("source_text")) for row in rows]
    return [(args.claim, None)]


def cmd_run(args) -> int:
    config = load_config()
    claims = _claims(args)
    if args.out and len(claims) != 1:
        print("--out writes one graph; give one claim", file=sys.stderr)
        return 2

    def adapter_factory():
        from verity.llm.anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(config.llm)

    status = 0
    with open_db(args.db or config.paths.db_path) as conn:
        from verity.alethiology.service import Alethiology

        service = Alethiology.open(conn, resolution_path=config.paths.key_resolution)
        for text, source_text in claims:
            outcome = run_claim(
                text,
                source_text=source_text,
                config=config,
                conn=conn,
                adapter_factory=adapter_factory,
                cache=BlobCache.open(),
                score=not args.no_score,
                bind=not args.no_bind,
                cache_mode=CacheMode(args.cache_mode),
                use_stage_cache=not args.no_cache,
            )
            if outcome.graph is None:
                status = 1
                _report_failure(text, outcome)
                continue

            store_outcome(conn, outcome, Path(args.out) if args.out else None)
            render_surface.render(
                outcome.graph,
                service,
                config,
                as_json=args.json,
                notes=[*outcome.notes, *_run_summary(outcome, args.out)],
            )
    return status


def _run_summary(outcome: RunOutcome, out: str | None) -> list[str]:
    """What this execution cost and where its artifacts went.

    A run that reached nothing external says so: a graph built from replayed answers is a
    different epistemic object from one built live, and a demo writeup has to be able to
    tell them apart without reading the manifest.
    """
    usage = outcome.manifest.total_usage
    lines = [
        f"run {outcome.manifest.run_id}; graph {outcome.graph.id} stored"
        + (f", written to {out}" if out else "")
    ]
    if outcome.reached_nothing_external:
        lines.append(
            "this run made no provider call and no registry call — every answer came "
            "from a recording on disk"
        )
    else:
        lines.append(
            f"{usage.input_tokens} in / {usage.output_tokens} out  ${usage.cost_usd:.4f}"
        )
    return lines


def _report_failure(text: str, outcome: RunOutcome) -> None:
    """A refusal is a result. It prints with the cost of the call that produced it."""
    print(f"no graph  {text}", file=sys.stderr)
    for error in outcome.manifest.errors:
        print(f"          {error}", file=sys.stderr)
    spent = outcome.manifest.total_usage.cost_usd
    if spent:
        print(f"          ${spent:.4f} spent before stopping", file=sys.stderr)


def cmd_replay(args) -> int:
    config = load_config()
    with open_db(args.db or config.paths.db_path) as conn:
        try:
            report = replay_run(
                args.run_id,
                conn=conn,
                cache=BlobCache.open(writable=False),
                db_override=args.db is not None,
            )
        except ReplayError as error:
            print(f"cannot replay: {error}", file=sys.stderr)
            return 1

    if args.json:
        print(report.model_dump_json(indent=2))
    for stage in report.stages:
        if not stage.comparable:
            mark, detail = "·", "nothing recorded to compare"
        else:
            mark = "=" if stage.matches else ("~" if stage.may_differ else "!")
            detail = stage.recorded or ""
        print(f"  {mark} {stage.stage:<10} {detail}")
    for why in report.partial_because:
        print(f"  partial: {why}")
    for note in report.notes:
        print(f"  note: {note}")
    if report.grounding_moved:
        print("  the alethiology has moved since this run; the grounding differs")
    if report.drifted:
        print(f"  DRIFT in {', '.join(s.stage for s in report.drifted)}", file=sys.stderr)
        return 1
    if report.unexplained_divergence:
        print(
            "  DRIFT: the graph differs while every stage that was compared matched and "
            "the alethiology did not move",
            file=sys.stderr,
        )
        return 1
    # Only drift is a failure. An incomplete replay is a fact about this machine — most
    # often the absent `verifier` extra — and exiting non-zero for it would make a reviewer
    # on the README's base install read a missing optional dependency as a broken tool.
    print(f"  {report.verdict}")
    return 0


def cmd_runs(args) -> int:
    config = load_config()
    with open_db(args.db or config.paths.db_path) as conn:
        run_ids = list_run_ids(conn)
        if not run_ids:
            print("no runs recorded", file=sys.stderr)
            return 0
        for run_id in run_ids:
            manifest = load_manifest(conn, run_id)
            if manifest is None:  # pragma: no cover - listed ids exist
                continue
            claim = manifest.inputs.claim_text if manifest.inputs else "—"
            marker = "!" if manifest.errors else " "
            print(f"{marker} {run_id}  {manifest.started_at:%Y-%m-%d %H:%M}  {claim[:60]}")
    return 0


def cmd_render(args) -> int:
    return render_surface.render_target(args.target, db=args.db, as_json=args.json)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m verity")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="decompose, score, bind, ground and render a claim")
    run_cmd.add_argument("claim", nargs="?", help="the claim text")
    run_cmd.add_argument("--pilot", action="store_true", help="run the committed pilot set")
    run_cmd.add_argument("--no-score", action="store_true", help="skip the entailment gate")
    run_cmd.add_argument(
        "--no-bind", action="store_true", help="skip candidate-key binding (no registry calls)"
    )
    run_cmd.add_argument(
        "--no-cache",
        action="store_true",
        help="recompute every stage instead of serving it from the stage cache",
    )
    run_cmd.add_argument(
        "--cache-mode",
        choices=[mode.value for mode in CacheMode],
        default=CacheMode.LIVE.value,
        help="where the binder's registry bytes may come from; recorded on the run",
    )
    run_cmd.add_argument("--out", type=Path, help="also write the graph here")
    run_cmd.add_argument("--db", type=Path, help="alethiology and graph store")
    run_cmd.add_argument("--json", action="store_true")
    run_cmd.set_defaults(func=cmd_run)

    replay_cmd = sub.add_parser("replay", help="re-derive a recorded run and compare")
    replay_cmd.add_argument("run_id")
    replay_cmd.add_argument("--db", type=Path)
    replay_cmd.add_argument("--json", action="store_true")
    replay_cmd.set_defaults(func=cmd_replay)

    render_cmd = sub.add_parser("render", help="render a stored graph; costs nothing")
    render_cmd.add_argument("target", help="path to a graph JSON file, or a graph id")
    render_cmd.add_argument("--db", type=Path)
    render_cmd.add_argument("--json", action="store_true")
    render_cmd.set_defaults(func=cmd_render)

    runs_cmd = sub.add_parser("runs", help="list recorded runs")
    runs_cmd.add_argument("--db", type=Path)
    runs_cmd.set_defaults(func=cmd_runs)

    args = parser.parse_args(argv)
    if args.command == "run" and not args.claim and not args.pilot:
        run_cmd.error("give a claim, or --pilot")
    try:
        return args.func(args)
    except Exception as error:  # noqa: BLE001 - the boundary, and only here
        # The library re-raises what a stage did not declare, because swallowing it would
        # hide an invariant violation. A command line should still stop rather than show a
        # traceback: the manifest is already written and the cassette holds every answer
        # the run paid for, so the retry is free.
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
