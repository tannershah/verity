"""M9-T1's render surface: draw a stored graph, and nothing else.

    python -m verity.presentation render data/demo/spinach.json
    python -m verity.presentation render graph_5746363f432dc03d --db data/verity.db
    python -m verity.presentation render data/demo/spinach.json --json

Offline and free: it reads a graph and the alethiology, and spends nothing. **Running** a
claim is `python -m verity run`, which belongs to the orchestrator — this package draws
what a pipeline produced and does not compose one.

`render_target` is the whole surface, so `python -m verity render` delegates here rather
than growing a second renderer that can drift from this one.

**`--json` writes the render payload to stdout and everything else to stderr**, so the
output is parseable in its entirety while the warnings that qualify it are still shown.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from rich.console import Console

from verity.alethiology.service import Alethiology
from verity.config import VerityConfig, load_config
from verity.export import graph_from_json, to_json
from verity.models.claim import ClaimGraph
from verity.models.render import to_render_payload
from verity.orchestration.stages import decomposition_notes
from verity.presentation import console as surface
from verity.store.db import open_db
from verity.store.graphs import load_graph


def load_target(target: str, conn: sqlite3.Connection) -> ClaimGraph:
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


def render(
    graph: ClaimGraph,
    service: Alethiology,
    config: VerityConfig,
    *,
    as_json: bool = False,
    notes: list[str] | None = None,
) -> None:
    """Project a graph against the current alethiology and draw it.

    The projection is taken here rather than by the caller because it is the boundary: a
    renderer's only legitimate input is a `RenderPayload`, and reading the fact store is
    what makes a stale grounding visible instead of replayed as live.

    `notes` supplied by a caller are run-level — what a stage failed at, what a call cost —
    and are added to, never replaced by, the ones this derives from the graph itself.
    """
    payload = to_render_payload(graph, service)
    derived = decomposition_notes(graph, config.decomposition)
    if as_json:
        print(to_json(payload))
    surface.render(
        payload,
        Console(stderr=as_json),
        gate=config.verifier.entailment_threshold,
        notes=[*(notes or []), *derived],
    )


def render_target(
    target: str, *, db: Path | None = None, as_json: bool = False
) -> int:
    """Render one stored graph. The entry point `python -m verity render` delegates to."""
    config = load_config()
    with open_db(db or config.paths.db_path) as conn:
        service = Alethiology.open(conn, resolution_path=config.paths.key_resolution)
        try:
            graph = load_target(target, conn)
        except FileNotFoundError as error:
            print(f"cannot render: {error}", file=sys.stderr)
            return 1
        render(graph, service, config, as_json=as_json)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m verity.presentation")
    sub = parser.add_subparsers(dest="command", required=True)

    render_cmd = sub.add_parser("render", help="render a stored graph")
    render_cmd.add_argument("target", help="path to a graph JSON file, or a graph id")
    render_cmd.add_argument("--db", type=Path, help="alethiology and graph store")
    render_cmd.add_argument(
        "--json", action="store_true", help="render payload to stdout, view to stderr"
    )

    args = parser.parse_args(argv)
    return render_target(args.target, db=args.db, as_json=args.json)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
