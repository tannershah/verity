"""Retrieval commands: record fixtures, and inspect what a key resolves to.

    python -m verity.retrieval record --from-seed        # write committed fixtures
    python -m verity.retrieval resolve doi:10.3823/1654  # read one key, from cache
    python -m verity.retrieval resolve doi:10.3823/1654 --live

Recording is deliberately a separate verb from seeding. A fixture is a verbatim recording
of what a registry served at a stated time; it is committed, and re-recording it is a
decision someone makes, not a side effect of running the demo.

Run as a module rather than a console script, so this tier adds no entry point to
`pyproject.toml` — one less file for parallel sessions to collide on.
"""

from __future__ import annotations

import argparse
import sys

from verity.alethiology.seed import read_seed
from verity.config import load_config
from verity.keys import ExternalKey, InvalidKeyError
from verity.retrieval import crossref, openalex
from verity.retrieval import retraction_watch as rw
from verity.retrieval.errors import RetrievalError
from verity.retrieval.http import CacheMode, build_client


def main(argv: list[str] | None = None) -> int:
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m verity.retrieval")
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="record registry responses as committed fixtures")
    record.add_argument("keys", nargs="*", help="e.g. doi:10.3823/1654")
    record.add_argument("--from-seed", action="store_true", help="every key in the seed file")
    record.add_argument("--seed", default=config.paths.alethiology_seed)
    record.add_argument(
        "--refresh", action="store_true", help="re-fetch keys already recorded"
    )

    resolve = sub.add_parser("resolve", help="show what each source says about a key")
    resolve.add_argument("keys", nargs="+")
    resolve.add_argument(
        "--live", action="store_true", help="allow network calls (default: replay only)"
    )

    args = parser.parse_args(argv)

    try:
        keys = [_parse(raw) for raw in args.keys]
        if args.command == "record":
            if getattr(args, "from_seed", False):
                keys += [row.external_key() for row in read_seed(args.seed)]
            if not keys:
                parser.error("give at least one key, or --from-seed")
            return _record(sorted(set(keys), key=str), refresh=args.refresh)
        return _resolve(keys, live=args.live)
    except (RetrievalError, InvalidKeyError) as exc:
        print(f"retrieval failed: {exc}", file=sys.stderr)
        return 1


def _parse(raw: str) -> ExternalKey:
    """Accept both `doi:10.1/2` and a bare identifier."""
    prefix, _, rest = raw.partition(":")
    if rest and prefix in ("doi", "pmid", "nct"):
        return ExternalKey(type=prefix, value=rest)  # type: ignore[arg-type]
    return ExternalKey.parse(raw)


def _record(keys: list[ExternalKey], *, refresh: bool) -> int:
    mode = CacheMode.REFRESH if refresh else CacheMode.RECORD
    client = build_client(mode=mode)
    for key in keys:
        for module in (openalex, crossref):
            record = module.fetch_work(client, key)
            line = f"  {key} {module.SOURCE:<9} found={record.found!s:<5} {record.title or ''}"
            print(line[:110])
    log = client.summary()
    print(
        f"{log.network_calls} network call(s), {log.cache_hits} cache hit(s), "
        f"{log.credits_spent} OpenAlex credit(s) spent, {log.sleep_seconds:.1f}s rate-limited"
    )
    for cap in log.caps():
        if cap.applied:
            print(f"  cap {cap.name} applied, dropped {cap.dropped}")
    return 0


def _show(record) -> None:  # noqa: ANN001
    """One source's line. Prints the *outcome*, never a bare `found=False`.

    `unanswered` and `absent` are different claims — one is the source saying it has no
    such work, the other is nobody having asked — and a boolean in a curator's terminal
    erases the difference just as thoroughly as a boolean in the artifact does.
    """
    summary = record.title or record.record or "—"
    print(f"  {record.source:<16} {record.outcome.value:<10} {summary}"[:110])
    if record.unanswered_because:
        print(f"  {'':<16} {record.unanswered_because}"[:110])
    findings = " ".join(f"{k}={v}" for k, v in sorted(record.raw_findings.items()))
    if findings:
        print(f"  {'':<16} {findings}"[:110])


def _resolve(keys: list[ExternalKey], *, live: bool) -> int:
    client = build_client(mode=CacheMode.LIVE if live else CacheMode.REPLAY)
    for key in keys:
        print(f"{key}")
        for module in (openalex, crossref):
            _show(module.fetch_work(client, key))
        source = rw.resolve_table()
        if source is None:
            # Absent table means never consulted, and that is reported rather than
            # rendered as a source with no opinion.
            print(f"  {'retraction-watch':<16} table not on disk — source not consulted")
        else:
            _show(rw.read(key, source.path))
            print(f"  {'':<16} read from {source.describe()}"[:110])
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
