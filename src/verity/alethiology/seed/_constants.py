"""Package-internal constants for the seed gate and loader."""

from __future__ import annotations

from verity.alethiology.resolution import REGISTRY_SOURCES, RETRACTION_WATCH
from verity.models.common import ConfidenceTier

#: Strongest-first, so a *higher* rank is a weaker claim and capping is `max` on the rank.
#: Mirrors `grounding.TIER_RANK`. Stated carefully because reordering this tuple to match
#: a wrong comment would invert the cap in `assess` into an amplifier, silently.
TIER_ORDER = (
    ConfidenceTier.VERIFIED_PRIMARY,
    ConfidenceTier.CORROBORATED_MULTI_SECONDARY,
    ConfidenceTier.SINGLE_SECONDARY,
    ConfidenceTier.INFERRED,
    ConfidenceTier.MARKETING_CLAIM,
)
TIER_RANK = {tier: rank for rank, tier in enumerate(TIER_ORDER)}

#: Sources are searched for a quote in this order, and the first match is the one
#: recorded. Registries before the curated index, so a quote that could come from either
#: is attributed to the work rather than to a database about the work.
QUOTE_SOURCE_ORDER = (*REGISTRY_SOURCES, RETRACTION_WATCH)
#: Within a source: the work's own prose before its title, since a title match supports
#: far less than an abstract match and the tier cap distinguishes them.
QUOTE_FIELD_ORDER = ("abstract", "record", "title")

#: Fields the seed owns on re-load. Everything else on an existing row is the store's.
SEED_OWNED_FIELDS = ("statement", "key", "tier", "provenance", "created_at", "supporting_quote")

#: Words a quote must have before it can carry `verified-primary`. Substring containment
#: is not evidence on its own: measured against the committed corpus, every quote that
#: earns the top tier is 5-23 words and occurs exactly once in the abstract it matched,
#: while the degenerate cases this floor exists to exclude ("a", "the", "iron") are single
#: words occurring 3-84 times. Short quotes are still legitimate for a curated index's
#: record fields — an author name is two words and is the whole datum — so the floor gates
#: the tier rather than aborting the row.
MIN_PRIMARY_QUOTE_WORDS = 5
