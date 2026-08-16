"""Content-derived identifiers and the id vocabulary.

IDs are a truncated SHA-256 over a canonical identity tuple rather than random UUIDs, so
that a replayed run reproduces the same graph byte-for-byte (M1-T2 deterministic replay)
and JSON exports diff cleanly. Two nodes with the same identity tuple *are* the same node.

**The digest refuses input it cannot canonicalize.** A `default=str` fallback would digest
an unhandled object's `repr` — which contains its memory address — so the same input would
hash differently in every process and surface only as a cache that never hits. Types that
have a canonical form get one, tagged so a value and its rendering cannot collide; anything
else raises.

Reference ids carry a type prefix, and the annotated aliases below turn that prefix into a
validated constraint. That is what makes design.md §4.2's "the verdict boundary as a type
distinction, not a convention" hold for `Justification`: a premise id cannot be passed
where a fact id belongs.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, StringConstraints

_ID_BYTES = 8  # 16 hex chars

#: A reference id: a lowercase type prefix, an underscore, then the identity digest.
_ID_RE = re.compile(r"^[a-z]+_[A-Za-z0-9_-]+$")


def _id_alias(prefix: str) -> Any:
    return Annotated[str, StringConstraints(pattern=rf"^{prefix}_[A-Za-z0-9_-]+$")]


ClaimId = _id_alias("claim")
PremiseId = _id_alias("prem")
StepId = _id_alias("step")
FactId = _id_alias("fact")
JustificationId = _id_alias("just")
#: A step's conclusion is the root claim or a premise — that is what makes recursion work.
ConclusionId = Annotated[str, StringConstraints(pattern=r"^(claim|prem)_[A-Za-z0-9_-]+$")]


class UnhashableInputError(TypeError):
    """Raised when `content_hash` is given a value with no canonical form."""


def _canonical(value: Any) -> Any:
    """A JSON-serializable form of `value` in which distinct types stay distinct."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Enum):
        return {"__t": "enum", "c": type(value).__name__, "v": _canonical(value.value)}
    if isinstance(value, datetime):
        return {"__t": "datetime", "v": value.isoformat()}
    if isinstance(value, Path):
        return {"__t": "path", "v": str(value)}
    if isinstance(value, BaseModel):
        return {"__t": "model", "c": type(value).__name__, "v": value.model_dump(mode="json")}
    if isinstance(value, str):
        # NFC is canonical equivalence, not a similarity transform: the two forms are the
        # same text by Unicode's own definition, and API responses mix them freely.
        return unicodedata.normalize("NFC", value)
    if isinstance(value, int | float):
        return value
    if isinstance(value, Mapping):
        return {
            str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, set | frozenset):
        return sorted(json.dumps(_canonical(v), sort_keys=True) for v in value)
    if isinstance(value, Sequence):
        return [_canonical(v) for v in value]
    raise UnhashableInputError(
        f"{type(value).__name__} has no canonical form; give it one in verity.ids "
        "rather than letting it hash as its memory address"
    )


def content_hash(*parts: Any) -> str:
    """Stable hex digest over `parts`. Ordering and nesting are significant."""
    payload = json.dumps(
        [_canonical(part) for part in parts],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_id(prefix: str, *parts: Any) -> str:
    """A deterministic `<prefix>_<hex>` id derived from `parts`."""
    return f"{prefix}_{content_hash(*parts)[: _ID_BYTES * 2]}"


def check_id(prefix: str, value: str) -> str:
    """Assert `value` is a well-formed id of `prefix`'s type. Returns it unchanged.

    Models assign their own ids, so the annotated aliases above cannot guard the field
    (it is empty until the validator runs). This is the same check, applied after.
    """
    if not value.startswith(f"{prefix}_") or not _ID_RE.match(value):
        raise ValueError(f"{value!r} is not a well-formed {prefix} id")
    return value


def statement_hash(statement: str) -> str:
    """Normalized hash of a fact statement, for alethiology dedup (M5-T1 owns the policy).

    Normalization is Unicode NFC, whitespace collapse, and case-folding — deliberately not
    semantic. Two statements that differ in wording are different statements here; the same
    statement arriving as NFC from one API and NFD from another is one statement.
    """
    collapsed = unicodedata.normalize("NFC", " ".join(statement.split()))
    folded = unicodedata.normalize("NFC", collapsed.casefold())
    return hashlib.sha256(folded.encode("utf-8")).hexdigest()
