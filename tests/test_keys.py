"""Exact-key grounding: canonicalization must be total, and must not be fuzzy.

Both halves matter to the headline metrics. Without canonicalization the grounding rate
is silently deflated and retraction linkage misses; with anything fuzzier the grounding
rate is silently inflated and the false-flag rate rises.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from verity.keys import ExternalKey, InvalidKeyError, KeyType, canonicalize

DOI_FORMS = [
    "10.3823/1654",
    "10.3823/1654 ",
    " 10.3823/1654",
    "https://doi.org/10.3823/1654",
    "http://dx.doi.org/10.3823/1654",
    "doi:10.3823/1654",
    "DOI:10.3823/1654",
    "10.3823/1654".upper(),
]


@pytest.mark.parametrize("raw", DOI_FORMS)
def test_doi_forms_canonicalize_to_one_key(raw: str):
    assert canonicalize(KeyType.DOI, raw) == "10.3823/1654"
    assert ExternalKey.parse(raw).value == "10.3823/1654"


def test_pmid_and_nct_canonicalization():
    assert canonicalize(KeyType.PMID, "PMID: 32445440") == "32445440"
    assert canonicalize(KeyType.NCT, "nct04280705") == "NCT04280705"
    assert (
        canonicalize(KeyType.NCT, "https://clinicaltrials.gov/study/NCT04280705")
        == "NCT04280705"
    )


def test_key_type_inference():
    assert ExternalKey.parse("10.3823/1654").type is KeyType.DOI
    assert ExternalKey.parse("NCT04280705").type is KeyType.NCT
    assert ExternalKey.parse("32445440").type is KeyType.PMID


def test_equal_keys_match_and_near_misses_do_not():
    """The grounding predicate is exact equality. No edit distance, ever."""
    key = ExternalKey.parse("https://doi.org/10.3823/1654")
    assert key.matches(ExternalKey.parse("DOI:10.3823/1654"))

    for near_miss in ("10.3823/1655", "10.3823/165", "10.3824/1654", "10.3823/1654x"):
        assert not key.matches(ExternalKey(type=KeyType.DOI, value=near_miss))

    # Same digits, different registry -> different key.
    assert not ExternalKey.parse("32445440").matches(
        ExternalKey(type=KeyType.NCT, value="NCT32445440")
    )


def test_malformed_keys_are_rejected_rather_than_coerced():
    for bad in ("", "not-a-doi", "10.x/abc", "doi:", "https://example.com/paper"):
        with pytest.raises(InvalidKeyError):
            ExternalKey.parse(bad)

    # Direct construction goes through pydantic, which wraps the same ValueError.
    with pytest.raises(ValidationError):
        ExternalKey(type=KeyType.PMID, value="abc123")


def test_keys_are_hashable_and_frozen():
    a = ExternalKey.parse("10.3823/1654")
    b = ExternalKey.parse("doi:10.3823/1654")
    assert a == b
    assert len({a, b}) == 1


# -- spellings the curated corpus cannot exercise -------------------------------------


def test_dois_lifted_from_prose_and_links_canonicalize_to_one_key():
    """The Retraction Watch table is curated, so `tests/test_key_corpus.py` proves
    totality on *clean* input only. These are the shapes M6 actually produces:

      * a DOI at the end of a sentence keeps the sentence's punctuation,
      * a DOI lifted from a link keeps the query string, fragment, or trailing slash,
      * a DOI pasted from a PDF keeps a zero-width space.

    Each would become a distinct key, so the same work would fail to match itself and the
    ≥50% grounding rate would be silently *deflated* — the exact failure `keys.py` says
    canonicalization exists to prevent, in the direction the corpus test cannot see.

    The stripping stays syntactic and total, so no fuzziness enters.
    """
    canonical = ExternalKey.parse("10.1234/abc").value
    for spelling in (
        "10.1234/abc.",
        "10.1234/abc,",
        "(10.1234/abc)",
        "https://doi.org/10.1234/abc/",
        "https://doi.org/10.1234/abc?utm_source=newsletter",
        "https://doi.org/10.1234/abc#page=2",
        "10.1234/abc​",
    ):
        assert ExternalKey.parse(spelling).value == canonical, spelling


def test_stripping_cannot_corrupt_an_identifier_that_legitimately_contains_brackets():
    """A closing bracket is dropped only when it is unmatched. `10.1016/S0140-6736(09)…`
    is a real DOI shape and has to survive intact, or the fix for one silent deflation
    creates another."""
    balanced = "10.1016/s0140-6736(09)60329-9"
    assert ExternalKey.parse(balanced).value == balanced
    assert ExternalKey.parse(f"({balanced})").value == balanced
    assert ExternalKey.parse("10.1002/(sici)1097-0258(19970330)16:6<621::aid-1>3.0.co;2-1")


def test_a_bare_identifier_keeps_characters_a_url_would_have_lost():
    """Query and fragment syntax is only debris when the thing stripped was a URL. A DOI
    written bare is taken as given."""
    assert ExternalKey.parse("10.1234/abc?x=1").value == "10.1234/abc?x=1"
