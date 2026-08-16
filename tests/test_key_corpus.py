"""Canonicalization measured against real identifiers, not hand-picked ones.

`keys.py` claims the transform is "total, deterministic, and syntactic". Totality and
injectivity are the two ways that claim can fail, and they fail in opposite directions:

  * reject a well-formed identifier and the grounding rate is silently **deflated**;
  * collapse two distinct identifiers onto one form and it is silently **inflated**.

The Retraction Watch table is ~65k real DOIs and ~33k real PMIDs sitting on disk for
M7-T1 and M10-T1 already, so both directions can be measured rather than asserted. `data/`
is gitignored, so this skips cleanly wherever the table is absent.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import pytest

from verity.keys import InvalidKeyError, KeyType, canonicalize

RW_TABLE = Path(__file__).resolve().parents[1] / "data" / "retraction_watch.csv"
#: A retracted-paper table is curated, so near-total acceptance is the expectation. The
#: floor exists to catch a regression, not to leave slack.
MIN_ACCEPT_RATE = 0.999
_MISSING = {"", "unavailable", "n/a", "none", "0"}

pytestmark = pytest.mark.skipif(
    not RW_TABLE.exists(), reason="data/retraction_watch.csv not present (data/ is gitignored)"
)


def _column(name: str) -> list[str]:
    csv.field_size_limit(10_000_000)
    with RW_TABLE.open(encoding="utf-8", errors="replace") as handle:
        return [
            value
            for row in csv.DictReader(handle)
            if (value := (row.get(name) or "").strip()).lower() not in _MISSING
        ]


@pytest.fixture(scope="module")
def dois() -> list[str]:
    return _column("OriginalPaperDOI")


@pytest.fixture(scope="module")
def pmids() -> list[str]:
    return _column("OriginalPaperPubMedID")


def test_canonicalization_accepts_real_dois(dois: list[str]):
    """Deflation guard: a rejected DOI is a grounding that silently cannot happen."""
    rejected = [d for d in dois if not _accepts(KeyType.DOI, d)]
    rate = 1 - len(rejected) / len(dois)
    assert rate >= MIN_ACCEPT_RATE, (
        f"{len(rejected)}/{len(dois)} real DOIs rejected; first few: {rejected[:5]}"
    )


def test_canonicalization_accepts_real_pmids(pmids: list[str]):
    rejected = [p for p in pmids if not _accepts(KeyType.PMID, p)]
    rate = 1 - len(rejected) / len(pmids)
    assert rate >= MIN_ACCEPT_RATE, (
        f"{len(rejected)}/{len(pmids)} real PMIDs rejected; first few: {rejected[:5]}"
    )


def test_canonicalization_never_merges_two_distinct_dois(dois: list[str]):
    """Inflation guard, and the one that matters more.

    Case and surrounding whitespace are *meant* to collapse — DOIs are case-insensitive
    by spec. Anything beyond that is fuzzy matching arriving through the back door, which
    design.md §4.1 rules out precisely because it would inflate the headline metric.
    """
    by_canonical: dict[str, set[str]] = defaultdict(set)
    for raw in dois:
        try:
            by_canonical[canonicalize(KeyType.DOI, raw)].add(raw.strip().lower())
        except InvalidKeyError:
            continue

    collisions = {k: v for k, v in by_canonical.items() if len(v) > 1}
    assert not collisions, (
        f"{len(collisions)} canonical form(s) reached by textually distinct DOIs: "
        f"{list(collisions.items())[:3]}"
    )


def test_canonicalization_is_idempotent(dois: list[str], pmids: list[str]):
    """`canonicalize(canonicalize(x)) == canonicalize(x)`. Without it, a value that has
    been through the store once and a value fresh from an API are different keys."""
    for key_type, values in ((KeyType.DOI, dois[:5000]), (KeyType.PMID, pmids[:5000])):
        for raw in values:
            try:
                once = canonicalize(key_type, raw)
            except InvalidKeyError:
                continue
            assert canonicalize(key_type, once) == once


def _accepts(key_type: KeyType, raw: str) -> bool:
    try:
        canonicalize(key_type, raw)
    except InvalidKeyError:
        return False
    return True
