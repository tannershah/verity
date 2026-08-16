"""External keys — DOI, PMID, NCT — and their canonicalization.

Grounding is defined as **exact-key match only** (design.md §4.1, evaluation.md §2).
`ExternalKey` is the type that definition rests on.

**Canonicalization is not fuzzy matching.** The transform here is total, deterministic,
and syntactic: case-folding, whitespace stripping, removal of a closed set of known
URI/label prefixes, and removal of the surrounding debris an identifier picks up in
transit. It contains no edit distance, no token overlap, no similarity of any kind, and
none may be added — a similarity layer belongs in M5-T3, flagged non-grounding, and must
never reach this module. Without canonicalization the grounding rate is silently
*deflated* (the same DOI written two ways fails to match) and retraction linkage silently
misses; with anything fuzzier it would be silently inflated.

**Debris is where the deflation actually comes from.** A curated table of identifiers
proves totality on clean input only; the shapes retrieval produces are lifted from prose
and links — a DOI carrying its sentence's full stop, wrapped in parentheses, trailing a
`utm_source` query, or pasted from a PDF with a zero-width space inside it. Each becomes a
distinct key, so the same work fails to match itself.

Stripping is bounded so it cannot corrupt a legitimate identifier: `10.1016/S0140-6736(09)
60329-9` contains parentheses and keeps them, because a closing bracket is dropped only
when it is unmatched, and query strings and fragments are dropped only when a URL prefix
was the thing that matched.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Self

from pydantic import model_validator

from verity.base import FrozenModel


class KeyType(StrEnum):
    DOI = "doi"
    PMID = "pmid"
    NCT = "nct"


_DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi.org/",
    "doi:",
    "doi ",
)
_PMID_PREFIXES = ("pmid:", "pmid ", "pubmed:", "pubmed ")
_NCT_PREFIXES = (
    "https://clinicaltrials.gov/study/",
    "https://clinicaltrials.gov/ct2/show/",
    "http://clinicaltrials.gov/ct2/show/",
    "nct:",
)

_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
_PMID_RE = re.compile(r"^\d{1,9}$")
_NCT_RE = re.compile(r"^NCT\d{8}$")

#: Invisible characters that survive a copy-paste out of a PDF or a rendered page. They
#: are not whitespace, so `.strip()` leaves them inside the identifier.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
#: Openers an identifier picks up when it is quoted or parenthesised in prose.
_LEADING_WRAPPERS = "([<{\"'"
#: Sentence punctuation that can trail an identifier. None of it is legal in a DOI suffix
#: in final position, and none of it is legal in a PMID or an NCT number at all.
_TRAILING_PUNCT = ".,;:!?\"'"
_CLOSERS = {")": "(", "]": "[", ">": "<", "}": "{"}


class InvalidKeyError(ValueError):
    """Raised when a string cannot be canonicalized into an ExternalKey."""


def _strip_prefixes(raw: str, prefixes: tuple[str, ...]) -> tuple[str, str | None]:
    """Return `raw` without a known prefix, and which prefix matched."""
    lowered = raw.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return raw[len(prefix) :], prefix
    return raw, None


def _strip_debris(raw: str) -> str:
    """Remove invisible characters and leading wrappers. Total and order-independent."""
    value = unicodedata.normalize("NFC", raw.translate(_ZERO_WIDTH)).strip()
    while value and value[0] in _LEADING_WRAPPERS:
        value = value[1:].lstrip()
    return value


def _strip_trailing(value: str) -> str:
    """Drop trailing sentence punctuation and *unmatched* closing brackets."""
    while value:
        last = value[-1]
        if last in _TRAILING_PUNCT:
            value = value[:-1]
            continue
        opener = _CLOSERS.get(last)
        # A DOI may legitimately contain balanced brackets; only an unmatched closer came
        # from the surrounding prose.
        if opener is not None and value.count(last) > value.count(opener):
            value = value[:-1]
            continue
        break
    return value


def canonicalize(key_type: KeyType, raw: str) -> str:
    """Canonical form of `raw` for `key_type`. Raises InvalidKeyError if malformed."""
    prefixes = _PREFIXES[key_type]
    value, matched = _strip_prefixes(_strip_debris(raw), prefixes)
    value = _strip_debris(value)

    # Query strings and fragments are URL syntax, so they are only debris when the thing
    # stripped was a URL. A bare identifier keeps every character it was given.
    if matched is not None and "/" in matched:
        value = value.split("#", 1)[0].split("?", 1)[0].rstrip("/")

    value = _strip_trailing(value)

    match key_type:
        case KeyType.DOI:
            # DOIs are case-insensitive by spec; lowercase so the comparison is total.
            value = value.lower()
        case KeyType.NCT:
            value = value.upper()

    if not _PATTERNS[key_type].match(value):
        raise InvalidKeyError(f"{raw!r} is not a well-formed {key_type.value}")
    return value


_PATTERNS = {KeyType.DOI: _DOI_RE, KeyType.PMID: _PMID_RE, KeyType.NCT: _NCT_RE}
_PREFIXES = {
    KeyType.DOI: _DOI_PREFIXES,
    KeyType.PMID: _PMID_PREFIXES,
    KeyType.NCT: _NCT_PREFIXES,
}


class ExternalKey(FrozenModel):
    """A canonicalized external identifier. Equality is exact string equality."""

    type: KeyType
    value: str

    @model_validator(mode="after")
    def _canonicalize(self) -> Self:
        canonical = canonicalize(self.type, self.value)
        if canonical != self.value:
            object.__setattr__(self, "value", canonical)
        return self

    @classmethod
    def parse(cls, raw: str) -> ExternalKey:
        """Infer the key type from `raw` and canonicalize.

        Always raises `InvalidKeyError` on bad input — never a pydantic
        `ValidationError` — so callers handling untrusted strings catch one thing.
        """
        candidate = _strip_debris(raw)
        lowered = candidate.lower()
        if lowered.startswith(("nct", *(p.lower() for p in _NCT_PREFIXES))):
            key_type = KeyType.NCT
        elif "10." in candidate or lowered.startswith(_DOI_PREFIXES):
            key_type = KeyType.DOI
        elif _PMID_RE.match(_strip_trailing(_strip_prefixes(candidate, _PMID_PREFIXES)[0])):
            key_type = KeyType.PMID
        else:
            raise InvalidKeyError(f"cannot infer key type from {raw!r}")

        # Surface the canonicalization failure directly rather than wrapped by pydantic.
        canonicalize(key_type, candidate)
        return cls(type=key_type, value=candidate)

    def matches(self, other: ExternalKey) -> bool:
        """Exact-key match — the only grounding predicate. No fuzziness, ever."""
        return self.type == other.type and self.value == other.value

    def __str__(self) -> str:
        return f"{self.type.value}:{self.value}"
