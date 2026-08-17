"""A content-addressed store for recorded work, shared by the cassette and the stage cache.

Deliberately the same shape as `verity.retrieval.http._cache`, which solved this problem
first for HTTP responses: an ordered list of read roots, zero or more write roots,
digest-sharded paths, and write-then-rename. The duplication is in the *values*, not the
mechanism — that module stores a `Fetched` and enforces the negative-entry and
degraded-request rules a registry answer needs, none of which apply to a decomposition.
Generalizing one store over both would put those rules where nothing reads them.

**Two roots, for the reason the HTTP layer has two.** A working root under `.cache/` is
gitignored and disposable; a committed root under `tests/fixtures/` is curated and part of
the source. That is what lets a reviewer replay a recorded run from a clean checkout, and
what keeps a developer's local cache from shadowing the recording under test.

**A corrupt or stale-shaped entry is a miss, never a crash.** An interrupted write leaves
half a JSON object, and a model that has since gained a field leaves entries that no
longer validate. Both must read as "not cached" — an entry parsed into a record with empty
fields would be served as real work nobody did.

Nothing here decides *what* is cacheable. That is the caller's, and for the grounding
stage the answer is nothing at all (design.md §4.2).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ValidationError

#: The two roots resolve differently, and the rule is which of them is *source*.
#:
#: A committed recording is source: it is checked in, it is what a replay is checked
#: against, and it must be found from the module rather than from wherever the process was
#: launched — a CWD-relative path would silently read a different tree per invocation, and
#: `verity.retrieval.http._client.FIXTURE_ROOT` resolves its own fixtures the same way.
#:
#: The working cache is workspace state, not source. It follows the working directory,
#: matching `RetrievalConfig.cache_dir`, which is the same decision made where a user can
#: also override it. Launching from a subdirectory therefore starts a fresh cache instead
#: of reading one from elsewhere in the tree: that costs a re-run and can never produce a
#: wrong answer, which is the direction this codebase resolves cache ambiguity in
#: everywhere else.
WORKING_ROOT = Path(".cache/verity")
COMMITTED_ROOT = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "recordings"


class BlobCache:
    """Reads an ordered list of roots; writes to zero or more of them."""

    def __init__(self, roots: Sequence[Path], write_roots: Sequence[Path] = ()) -> None:
        self._roots = [Path(root) for root in roots]
        self._write_roots = [Path(root) for root in write_roots]

    @classmethod
    def open(
        cls, *, working_root: Path | None = None, writable: bool = True
    ) -> BlobCache:
        """The construction path callers should use: working root first, fixtures behind it."""
        working = Path(working_root or WORKING_ROOT)
        return cls([working, COMMITTED_ROOT], [working] if writable else [])

    def path_for(self, root: Path, namespace: str, key: str) -> Path:
        return root / namespace / key[:2] / f"{key}.json"

    def get(self, namespace: str, key: str, schema: type[BaseModel]) -> BaseModel | None:
        """The first readable, still-valid entry across the roots."""
        for root in self._roots:
            path = self.path_for(root, namespace, key)
            if not path.exists():
                continue
            try:
                return schema.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValidationError, ValueError, OSError):
                continue
        return None

    def put(self, namespace: str, key: str, entry: BaseModel) -> list[Path]:
        """Write to every write root. Returns the paths written."""
        written: list[Path] = []
        for root in self._write_roots:
            path = self.path_for(root, namespace, key)
            path.parent.mkdir(parents=True, exist_ok=True)
            # `os.replace` is atomic within a filesystem, which is what keeps an
            # interrupted write from becoming the truncated file `get` has to tolerate.
            temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            temporary.write_text(
                entry.model_dump_json(indent=2) + "\n", encoding="utf-8"
            )
            os.replace(temporary, path)
            written.append(path)
        return written
