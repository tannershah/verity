"""The gate: how much of a row's claim survives, and why it went no higher.

Reads the committed resolution record and returns a `TierAssessment`. Decides nothing
about storage and writes nothing — `_project` turns an assessment into a fact.
"""

from __future__ import annotations

from pydantic import Field

from verity.alethiology.resolution import REGISTRY_SOURCES, KeyResolution
from verity.alethiology.seed._constants import (
    MIN_PRIMARY_QUOTE_WORDS,
    QUOTE_FIELD_ORDER,
    QUOTE_SOURCE_ORDER,
    TIER_RANK,
)
from verity.alethiology.seed._row import SeedError, SeedFact
from verity.base import FrozenModel
from verity.ids import normalize_text
from verity.models.common import ConfidenceTier


class QuoteMatch(FrozenModel):
    """Where a row's quote was found, and how much of a quotation it is.

    Containment alone is not evidence. A one-word quote is contained in almost any
    abstract — `"a"` occurs 84 times in Hamblin's — so a gate that asked only "does this
    string appear" would let an arbitrary assertion ride on a common word into the top
    tier. `words` and `occurrences` are what make the match a quotation rather than a
    coincidence, and the tier ladder reads both.
    """

    source: str
    field: str
    #: Words in the normalized quote. Substantiality: a clause, not a token.
    words: int
    #: Times the normalized quote occurs in the matched text. Specificity: a quotation
    #: points at one passage.
    occurrences: int


class TierAssessment(FrozenModel):
    """What the gate concluded about one row, before anything is written."""

    allowed_tier: ConfidenceTier
    effective_tier: ConfidenceTier
    identity_confirmed_by: list[str] = Field(default_factory=list)
    #: The declared titles those sources actually returned, so an audit can tell identity
    #: resting on the row's own `expected_title` from identity resting on a variant the
    #: same curator supplied — without opening the seed file.
    identity_matched_titles: list[str] = Field(default_factory=list)
    #: No source's title matched the one the curator named.
    identity_mismatch: bool = False
    #: A registry returned a title, and it is not the work the curator named. Distinct
    #: from `identity_mismatch`: this is the state `10.3823/1654` is in — Retraction Watch
    #: names the chocolate paper under that DOI while both registries serve a different
    #: article, and all three agree it is retracted. A disagreement about *what a key
    #: identifies* has no other home in the model, and it caps the tier.
    registry_identity_conflict: bool = False
    quote_match: QuoteMatch | None = None
    notes: list[str] = Field(default_factory=list)

    @property
    def capped(self) -> bool:
        return self.effective_tier is not self.allowed_tier or bool(self.notes)


def find_quote(quote: str, resolution: KeyResolution) -> QuoteMatch | None:
    """First source and field whose text contains `quote`, under `normalize_text`."""
    needle = normalize_text(quote)
    for source in QUOTE_SOURCE_ORDER:
        reading = resolution.reading(source)
        if reading is None or not reading.found:
            continue
        texts = reading.quotable_text
        for field in QUOTE_FIELD_ORDER:
            if field in texts and needle in texts[field]:
                return QuoteMatch(
                    source=source,
                    field=field,
                    words=len(needle.split()),
                    occurrences=texts[field].count(needle),
                )
    return None


def assess(row: SeedFact, resolution: KeyResolution) -> TierAssessment:
    """Decide the highest tier `row` has earned, and why it is not higher.

    Raises `SeedError` for claims the gate cannot let through at any tier.
    """
    key = row.external_key()
    if not resolution.readings:
        raise SeedError(f"{row.slug}: no source was ever asked about {key}")
    if not any(reading.found for reading in resolution.readings.values()):
        raise SeedError(
            f"{row.slug}: {key} resolves in no source consulted. An identifier that "
            "exists nowhere cannot carry a fact; correct it or drop the row."
        )

    matches = resolution.title_matches(row.expected_title, *row.expected_title_variants)
    identity = sorted(matches)
    registry_identity = any(source in REGISTRY_SOURCES for source in identity)
    returned = "; ".join(
        f"{source}={reading.title!r}"
        for source, reading in sorted(resolution.readings.items())
        if reading.found and reading.title
    )
    conflict = not registry_identity and any(
        reading.title for reading in resolution.registry_readings
    )
    notes: list[str] = []
    if not identity:
        notes.append(
            f"no source's title matches the expected title {row.expected_title!r}; "
            f"sources returned {returned}"
        )
    elif conflict:
        notes.append(
            f"only {', '.join(identity)} identifies {key} as {row.expected_title!r}; "
            f"registries returned {returned}"
        )

    match = find_quote(row.quote, resolution) if row.quote else None
    if row.quote and match is None:
        raise SeedError(
            f"{row.slug}: the quote appears in no text any source returned for {key}. "
            "A quote that cannot be found is the fabrication this gate exists to catch."
        )

    if match is None:
        allowed = ConfidenceTier.INFERRED
        notes.append("no quote, so nothing above `inferred` is supported")
    elif (
        match.source in REGISTRY_SOURCES
        and registry_identity
        and match.field == "abstract"
        and match.words >= MIN_PRIMARY_QUOTE_WORDS
        and match.occurrences == 1
    ):
        allowed = ConfidenceTier.VERIFIED_PRIMARY
    else:
        allowed = ConfidenceTier.SINGLE_SECONDARY
        if match.field != "abstract":
            notes.append(f"quote matched the {match.field}, not the work's own abstract")
        if not registry_identity:
            notes.append("work identity is unconfirmed by any registry")
        if match.words < MIN_PRIMARY_QUOTE_WORDS:
            notes.append(
                f"the quote is {match.words} word(s); primary verification needs at least "
                f"{MIN_PRIMARY_QUOTE_WORDS}, because a shorter string is contained in a "
                "source without quoting it"
            )
        if match.occurrences > 1:
            notes.append(
                f"the quote occurs {match.occurrences} times in the matched text, so it "
                "identifies no particular passage"
            )

    effective = row.tier if TIER_RANK[row.tier] >= TIER_RANK[allowed] else allowed
    if effective is not row.tier:
        notes.append(f"requested {row.tier.value}, capped to {effective.value}")

    return TierAssessment(
        allowed_tier=allowed,
        effective_tier=effective,
        identity_confirmed_by=identity,
        identity_matched_titles=sorted(set(matches.values())),
        identity_mismatch=not identity,
        registry_identity_conflict=conflict,
        quote_match=match,
        notes=notes,
    )
