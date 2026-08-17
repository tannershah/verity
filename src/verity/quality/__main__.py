"""Retraction commands: check one identifier, or write the alethiology's findings.

    python -m verity.quality check doi:10.3823/1654    # three sources, and the cut
    python -m verity.quality check doi:10.3823/1654 --live
    python -m verity.quality apply --check             # assess the store, write nothing
    python -m verity.quality apply                     # assess the store and write

**Replay by default**, like `python -m verity.retrieval resolve`: the committed fixtures
answer for every key the seed rests on, so a reviewer with no API key and no 66 MB download
gets the real cut at no cost, and `--live` is the opt-in that spends credits.

Run as a module rather than a console script, so this tier adds no entry point to
`pyproject.toml`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verity.config import load_config
from verity.keys import ExternalKey, InvalidKeyError
from verity.quality.apply import apply_retractions, stored_keys
from verity.quality.retraction import basis_lines
from verity.quality.service import assess_keys
from verity.retrieval.errors import RetrievalError
from verity.retrieval.http import CacheMode, build_client
from verity.store.db import open_db


def main(argv: list[str] | None = None) -> int:
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m verity.quality")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="show what each source says about a key, and the cut")
    check.add_argument("keys", nargs="+", help="e.g. doi:10.3823/1654")
    check.add_argument(
        "--live", action="store_true", help="allow network calls (default: replay only)"
    )

    apply_cmd = sub.add_parser(
        "apply", help="check every key in the alethiology and write the findings onto its facts"
    )
    apply_cmd.add_argument(
        "--check", action="store_true", help="assess and report; write nothing"
    )
    apply_cmd.add_argument(
        "--live", action="store_true", help="allow network calls (default: replay only)"
    )
    apply_cmd.add_argument("--db", type=Path, default=config.paths.db_path)

    args = parser.parse_args(argv)
    mode = CacheMode.LIVE if args.live else CacheMode.REPLAY

    try:
        if args.command == "check":
            return _check([_parse(raw) for raw in args.keys], mode=mode)
        return _apply(args.db, mode=mode, apply=not args.check)
    except (RetrievalError, InvalidKeyError) as exc:
        # A replay miss is the expected failure for a key with no committed fixture, and a
        # reviewer typing an identifier the corpus does not hold should get a sentence
        # rather than a traceback. The service degrades per source, so this catches only
        # what escapes it — a key that could not be parsed, or a build that could not start.
        print(f"retraction check failed: {exc}", file=sys.stderr)
        return 1


def _parse(raw: str) -> ExternalKey:
    """Accept both `doi:10.1/2` and a bare identifier."""
    prefix, _, rest = raw.partition(":")
    if rest and prefix in ("doi", "pmid", "nct"):
        return ExternalKey(type=prefix, value=rest)  # type: ignore[arg-type]
    return ExternalKey.parse(raw)


def _check(keys: list[ExternalKey], *, mode: CacheMode) -> int:
    client = build_client(mode=mode)
    assessments = assess_keys(client, keys)
    for key in keys:
        for line in assessments[str(key)].render():
            print(line)
    print()
    for line in basis_lines():
        print(line)
    return 0


def _apply(db: Path, *, mode: CacheMode, apply: bool) -> int:
    with open_db(db) as conn:
        keys = stored_keys(conn)
        if not keys:
            print(
                f"no facts in {db}; run `python -m verity.alethiology seed` first",
                file=sys.stderr,
            )
            return 1
        client = build_client(mode=mode)
        print(apply_retractions(conn, client, keys, apply=apply).render())
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
