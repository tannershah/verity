"""What code produced a result, in two forms that answer two different questions.

**The source digest is part of every stage-cache key.** A stage's recorded `input_hash`
covers its inputs, and `config_hash()` covers its knobs, but neither covers the code that
turned one into the other: `_materialize`'s dedup rules, the cyclic-premise refusal,
`_merge_premises`' conflict policy and every id derivation sit outside both. Change one and
the key does not move, so the cache serves a graph built by rules that no longer exist —
silently, and in a direction that moves the grounding-rate denominator.

**It digests the whole tree, not a declared list per stage.** A hand-maintained list of
"modules this stage depends on" is the same discipline failure the digest exists to remove,
moved one level up: `decompose` transitively reaches `ids`, `base`, `keys`, `config`,
`models.claim`, `models.common` and all of `decomposition`, and a list that misses one
under-invalidates. Complete and zero-maintenance beats precise and forgettable. It
over-invalidates — a docstring edit re-runs the deterministic stages — and that costs
nothing, because the cassette holds the provider answers the money was spent on.

**Git identity is recorded and never keyed.** `code_version` and `code_dirty` say which
commit a run happened on, which is what a reader of a manifest wants. Putting them in a
cache key would bust every entry on every commit, including docs-only ones.

Two limits, stated rather than papered over. Dependency versions are outside the digest, so
a `transformers` upgrade that moves a checkpoint's context window, or a torch build that
moves a float, reuses a cache built under the old one — the second is bounded by
`SCORE_DECIMALS`. And a digest only means anything within one working tree; it is not a
distributed identity.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

import verity
from verity.ids import content_hash

#: The tree digested. Everything importable as `verity.*`.
SOURCE_ROOT = Path(verity.__file__).resolve().parent


@lru_cache(maxsize=1)
def source_digest() -> str:
    """A digest over every `.py` under `verity/`, by relative path and bytes.

    Cached for the process: the tree cannot change under a running interpreter in any way
    that already-imported modules would reflect, so re-reading it per stage would only cost
    file system calls and invite two stages in one run to disagree about what code they are.
    """
    parts: list[tuple[str, str]] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        parts.append(
            (
                path.relative_to(SOURCE_ROOT).as_posix(),
                content_hash(path.read_bytes().decode("utf-8", errors="surrogateescape")),
            )
        )
    if not parts:
        # A digest over nothing is a constant, and a constant key never moves — so the whole
        # "the cache key moves when the code moves" guarantee would void, silently, in
        # exactly the deployments where the source is not on disk as `.py` (a zipimport, a
        # frozen bundle). Refusing is the only outcome that cannot be mistaken for working.
        raise RuntimeError(
            f"no Python source found under {SOURCE_ROOT}; the stage cache cannot be keyed "
            "on code that is not readable, and a digest over nothing would never invalidate"
        )
    return content_hash(parts)


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=SOURCE_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


@lru_cache(maxsize=1)
def code_version() -> tuple[str | None, bool | None]:
    """`(commit sha, working tree is dirty)`, or `(None, None)` outside a repository.

    `None` rather than a guess: "we do not know which commit this ran on" and "it ran on a
    clean checkout" are different claims about a run, and a manifest must not make the
    second when it means the first.
    """
    sha = _git("rev-parse", "HEAD")
    if sha is None:
        return None, None
    status = _git("status", "--porcelain")
    return sha, None if status is None else bool(status)
