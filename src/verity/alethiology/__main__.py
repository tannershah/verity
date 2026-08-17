"""Alethiology commands: resolve seed keys, then seed the store.

    python -m verity.alethiology verify-keys --from-seed
    python -m verity.alethiology verify-keys doi:10.1136/bmj.283.6307.1671 --refresh
    python -m verity.alethiology verify-keys --from-seed --refresh --cache-mode replay
    python -m verity.alethiology seed --check
    python -m verity.alethiology seed

Run as a module rather than a console script so this tier adds no entry point to
`pyproject.toml` — one less file for parallel sessions to collide on.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verity.alethiology.seed import SeedError, load_seed, read_seed, report_to_json
from verity.alethiology.verify_keys import verify
from verity.config import load_config
from verity.keys import ExternalKey
from verity.retrieval import retraction_watch as rw
from verity.retrieval.http import CacheMode
from verity.store.db import open_db


def main(argv: list[str] | None = None) -> int:
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m verity.alethiology")
    sub = parser.add_subparsers(dest="command", required=True)

    verify_cmd = sub.add_parser("verify-keys", help="resolve identifiers and record readings")
    verify_cmd.add_argument("keys", nargs="*", help="e.g. doi:10.1136/bmj.283.6307.1671")
    verify_cmd.add_argument(
        "--from-seed", action="store_true", help="also resolve every key in the seed file"
    )
    verify_cmd.add_argument(
        "--refresh", action="store_true", help="re-read keys already in the artifact"
    )
    verify_cmd.add_argument(
        "--cache-mode",
        choices=[mode.value for mode in CacheMode],
        default=None,
        help=(
            "where the registry bytes may come from; `replay` re-reads the committed "
            "fixtures instead of the network, which is how the artifact is re-recorded "
            "after a parser change without the API moving underneath it"
        ),
    )
    verify_cmd.add_argument("--seed", type=Path, default=config.paths.alethiology_seed)
    verify_cmd.add_argument("--artifact", type=Path, default=config.paths.key_resolution)

    seed_cmd = sub.add_parser("seed", help="gate the seed file and load it into the store")
    seed_cmd.add_argument(
        "--check", action="store_true", help="run the gate and report; write nothing"
    )
    seed_cmd.add_argument("--seed", type=Path, default=config.paths.alethiology_seed)
    seed_cmd.add_argument("--artifact", type=Path, default=config.paths.key_resolution)
    seed_cmd.add_argument("--db", type=Path, default=config.paths.db_path)
    seed_cmd.add_argument("--json", action="store_true", help="emit the report as JSON")

    args = parser.parse_args(argv)

    try:
        if args.command == "verify-keys":
            keys = [ExternalKey.parse(raw) for raw in args.keys]
            if args.from_seed:
                keys += [row.external_key() for row in read_seed(args.seed)]
            if not keys:
                parser.error("give at least one key, or --from-seed")
            report = verify(
                keys,
                args.artifact,
                refresh=args.refresh,
                cache_mode=CacheMode(args.cache_mode) if args.cache_mode else None,
            )
            state = "rewritten" if report.written else "unchanged"
            print(
                f"{args.artifact} ({state}): {len(report.artifact.resolutions)} key(s) "
                f"recorded, {report.resolving} resolving in at least one source"
            )
            if report.unrecordable:
                # Not written, and said out loud. The artifact's `found` is a boolean and
                # the gate reads a resolution with nothing found as grounds to delete the
                # row — so a key nothing could check has to be reported as unchecked rather
                # than recorded as nonexistent.
                print(
                    f"{len(report.unrecordable)} key(s) could not be checked and were not "
                    "recorded:",
                    file=sys.stderr,
                )
                for reading in report.unrecordable:
                    print(f"  {reading.key}: {reading.why_not()}", file=sys.stderr)
            if report.table_unconsulted:
                # An absent table is a source that was never asked, and saying so is the
                # difference between a recorded miss and a silent one.
                print(
                    f"warning: {rw.TABLE} is not on disk, so retraction-watch was not "
                    f"consulted for {len(report.table_unconsulted)} key(s)",
                    file=sys.stderr,
                )
            return 1 if report.unrecordable else 0

        with open_db(args.db) as conn:
            report = load_seed(conn, args.seed, args.artifact, apply=not args.check)
        print(report_to_json(report) if args.json else report.render())
        return 0
    except SeedError as exc:
        print(f"seed refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
