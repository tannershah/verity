"""M9-T1 entry points: render a stored graph, or run one claim end to end.

    python -m verity.presentation render data/demo/spinach.json
    python -m verity.presentation render graph_5746363f432dc03d --db data/verity.db
    python -m verity.presentation render data/demo/spinach.json --json
    python -m verity.presentation run "A misplaced decimal point made spinach famous…"
    python -m verity.presentation run --pilot --out data/demo/spinach.json

`render` is offline and free: it reads a graph and the alethiology, and spends nothing.
`run` calls the LLM and costs money. Run as a module rather than a console script so this
tier adds no entry point to `pyproject.toml` — one less file for parallel sessions to
collide on.

**`--json` writes the render payload to stdout and everything else to stderr**, so the
output is parseable in its entirety while the warnings that qualify it are still shown.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console

from verity.alethiology.service import Alethiology
from verity.config import load_config
from verity.decomposition.errors import DecompositionError
from verity.export import graph_from_json, graph_to_json, to_json
from verity.models.claim import Claim, ClaimGraph
from verity.models.render import to_render_payload
from verity.presentation import console as surface
from verity.presentation import driver
from verity.retrieval.http import CacheMode
from verity.store.db import open_db
from verity.store.graphs import load_graph, save_graph

PILOT = Path("data/claimsets/pilot.jsonl")


def _load_target(target: str, conn) -> ClaimGraph:
    """A graph from a JSON file, or from the store by id."""
    path = Path(target)
    if path.exists():
        return graph_from_json(path.read_text(encoding="utf-8"))
    graph = load_graph(conn, target)
    if graph is None:
        raise FileNotFoundError(
            f"{target} is neither a file on disk nor a graph id in the store"
        )
    return graph


def _render(
    graph: ClaimGraph,
    service: Alethiology,
    config,
    *,
    as_json: bool,
    notes: list[str],
) -> None:
    payload = to_render_payload(graph, service)
    if as_json:
        print(to_json(payload))
    surface.render(
        payload,
        Console(stderr=as_json),
        gate=config.verifier.entailment_threshold,
        notes=notes,
    )


def _read_claims(args) -> list[Claim]:
    if args.pilot:
        rows = [
            json.loads(line)
            for line in PILOT.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [Claim(text=r["text"], source_text=r.get("source_text")) for r in rows]
    return [Claim(text=args.claim)]


def cmd_render(args) -> int:
    config = load_config()
    with open_db(args.db or config.paths.db_path) as conn:
        service = Alethiology.open(conn)
        try:
            graph = _load_target(args.target, conn)
        except FileNotFoundError as error:
            print(f"cannot render: {error}", file=sys.stderr)
            return 1
        _render(graph, service, config, as_json=args.json, notes=[])
    return 0


def cmd_run(args) -> int:
    from verity.llm.anthropic_adapter import AnthropicAdapter

    config = load_config()
    adapter = AnthropicAdapter(config.llm)
    claims = _read_claims(args)
    if args.out and len(claims) != 1:
        print("--out writes one graph; give one claim", file=sys.stderr)
        return 2

    status = 0
    with open_db(args.db or config.paths.db_path) as conn:
        service = Alethiology.open(conn)
        for claim in claims:
            result = driver.run_claim(
                claim,
                config=config,
                adapter=adapter,
                service=service,
                score=not args.no_score,
                bind=not args.no_bind,
                cache_mode=CacheMode(args.cache_mode),
            )
            if result.refusal is not None:
                status = 1
                _report_refusal(claim, result.refusal)
                continue

            graph = result.graph
            save_graph(conn, graph)
            destination = Path(args.out) if args.out else _run_path(config, graph)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(graph_to_json(graph), encoding="utf-8")

            notes = [*result.notes, f"graph {graph.id} stored, written to {destination}"]
            if result.usage is not None:
                notes.append(_cost_note(result))
            _render(graph, service, config, as_json=args.json, notes=notes)
    return status


def _run_path(config, graph: ClaimGraph) -> Path:
    return Path(config.paths.runs_dir) / f"{graph.id}.json"


def _cost_note(result: driver.RunResult) -> str:
    usage = result.usage
    settings = result.llm_settings
    where = f" [{settings.model} effort={settings.effort}]" if settings else ""
    return (
        f"{usage.input_tokens} in / {usage.output_tokens} out  "
        f"${usage.cost_usd:.4f}{where}"
    )


def _report_refusal(claim: Claim, error: DecompositionError) -> None:
    """A refusal is a result. It prints with the cost of the call that produced it."""
    print(f"refused  {claim.text}", file=sys.stderr)
    print(f"         {type(error).__name__}: {error}", file=sys.stderr)
    if error.usage is not None:
        print(
            f"         ${error.usage.cost_usd:.4f} spent before the refusal",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m verity.presentation")
    sub = parser.add_subparsers(dest="command", required=True)

    render_cmd = sub.add_parser("render", help="render a stored graph")
    render_cmd.add_argument("target", help="path to a graph JSON file, or a graph id")
    render_cmd.add_argument("--db", type=Path, help="alethiology and graph store")
    render_cmd.add_argument(
        "--json", action="store_true", help="render payload to stdout, view to stderr"
    )
    render_cmd.set_defaults(func=cmd_render)

    run_cmd = sub.add_parser("run", help="decompose, score, ground and render one claim")
    run_cmd.add_argument("claim", nargs="?", help="the claim text")
    run_cmd.add_argument("--pilot", action="store_true", help="run the committed pilot set")
    run_cmd.add_argument("--no-score", action="store_true", help="skip the entailment gate")
    run_cmd.add_argument(
        "--no-bind", action="store_true", help="skip candidate-key binding (no registry calls)"
    )
    run_cmd.add_argument(
        "--cache-mode",
        choices=[mode.value for mode in CacheMode],
        default=CacheMode.LIVE.value,
        help="where the binder's registry bytes may come from; recorded in the run's notes",
    )
    run_cmd.add_argument("--out", type=Path, help="also write the graph here")
    run_cmd.add_argument("--db", type=Path, help="alethiology and graph store")
    run_cmd.add_argument("--json", action="store_true")
    run_cmd.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    if args.command == "run" and not args.claim and not args.pilot:
        run_cmd.error("give a claim, or --pilot")
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
