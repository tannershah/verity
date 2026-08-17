"""The disk cache, which is also the fixture store.

Mandatory rather than an optimization: OpenAlex spends credits per request — including on
a 404 — and Crossref's polite pool is single-digit req/s. But two properties matter more
than the saving.

**A cache hit does not restamp the clock.** `Fetched.fetched_at` is replayed out of the
entry, so `Provenance.accessed_at` records when the network answered rather than when we
read our own disk. M5-T3's TTL re-validation reads exactly that field, and a cache that
refreshed freshness on every read would defeat non-monotonic grounding while appearing to
work.

**Negative entries are a separate namespace, and a degraded request never writes one.**
OpenAlex indexing lag means a real DOI 404s for days after publication, and an immortal
cached 404 makes `found=False` permanent — which the seed gate reads as "resolves in no
source consulted; correct it or drop the row" and the binder reads as "do not bind". The
namespace gives a future TTL a hook and lets `refresh` target misses alone. And a 404
returned to a request that went out without its credential is not credibly a miss at all,
so one exhausted anonymous run cannot poison every key it touched.

**Fixtures are this format in a different directory.** `.cache/http/` is gitignored and
ephemeral; `tests/fixtures/http/` is committed and curated. Record mode writes both. That
makes the "fixture-recording harness" a directory choice rather than a second
implementation, and it makes a fixture a verbatim recording — bodies are never pruned,
because a pruned fixture is a claim about what an API returned that the API never made.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from verity.ids import content_hash
from verity.retrieval.http._model import Fetched, HttpRequest

#: Entries a lookup can land in. Separate directories rather than a field, so a miss is
#: targetable by `refresh` and removable by deleting a tree.
FOUND = "found"
MISSING = "missing"


def entry_digest(request: HttpRequest) -> str:
    """The cache key. Content-derived, so a URL can never become a path.

    `_DOI_RE` accepts `10.1234/../../../etc/passwd` — canonicalization is syntactic and
    makes no claim about filesystem safety — so the key is a digest and the identifier
    never reaches a path component. Readable filenames would be nicer and are exactly the
    refactor this note exists to refuse.
    """
    return content_hash("GET", request.url)


class HttpCache:
    """Reads an ordered list of roots; writes to zero or more of them."""

    def __init__(self, roots: Sequence[Path], write_roots: Sequence[Path] = ()) -> None:
        self._roots = [Path(root) for root in roots]
        self._write_roots = [Path(root) for root in write_roots]

    def path_for(self, root: Path, request: HttpRequest, namespace: str) -> Path:
        digest = entry_digest(request)
        return root / namespace / request.source / digest[:2] / f"{digest}.json"

    def get(self, request: HttpRequest) -> Fetched | None:
        """The first readable entry across the roots, in either namespace."""
        for root in self._roots:
            for namespace in (FOUND, MISSING):
                entry = self._read(self.path_for(root, request, namespace))
                if entry is not None:
                    return entry.model_copy(update={"from_cache": True})
        return None

    def put(self, fetched: Fetched) -> list[Path]:
        """Write to every write root. Returns the paths written."""
        namespace = MISSING if fetched.missing else FOUND
        written: list[Path] = []
        for root in self._write_roots:
            path = self.path_for(root, fetched.request, namespace)
            self._write(path, fetched.for_cache())
            written.append(path)
        return written

    # -- internals -----------------------------------------------------------------

    @staticmethod
    def _read(path: Path) -> Fetched | None:
        """Parse an entry, or treat it as absent.

        A truncated file is what an interrupted run leaves behind, and half a JSON object
        must be a miss rather than a record with empty fields — a `Fetched` with an empty
        body would be parsed as a work with no title and cached as a real reading.
        """
        if not path.exists():
            return None
        try:
            return Fetched.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, ValueError, OSError):
            return None

    @staticmethod
    def _write(path: Path, fetched: Fetched) -> None:
        """Write-then-rename, so a reader never sees a partial entry.

        `os.replace` is atomic within a filesystem, which is what keeps an interrupted
        write from becoming the truncated file `_read` has to tolerate.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        temporary.write_text(
            fetched.model_dump_json(indent=2, exclude_none=False) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
