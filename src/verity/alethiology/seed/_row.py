"""A seed row as written: the curator's claim, before the gate has ruled on it."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from verity.base import VerityModel
from verity.ids import normalize_text
from verity.keys import ExternalKey
from verity.models.common import ConfidenceTier


class SeedError(RuntimeError):
    """The seed is malformed or makes a claim the gate cannot accept. Aborts the load.

    Distinct from a tier cap, which is a row loading at less than it asked for. This is a
    row that must not load at all: an invented identifier, a quote that appears in no
    source, a duplicate, or a tier no seed row can ever justify.
    """


class SeedFact(VerityModel):
    """One curated claim about one work, before the gate has ruled on it."""

    #: Stable, human-readable row id. Appears in the fact's curation provenance, so a
    #: reader who finds a fact can find the seed row and the note that argued for it.
    slug: str
    #: Which demo claim this row supports, e.g. `spinach-iron`. Reported, not enforced.
    claim_scope: str
    #: Raw identifier; canonicalized on load. A fact without a key grounds nothing.
    key: str
    #: What the curator believes `key` identifies. Compared, by equality, to what the
    #: registries return.
    expected_title: str
    #: Other exact spellings a source is known to use for the same work — OpenAlex prefixes
    #: retracted works with `RETRACTED ARTICLE:`. Declared per row rather than absorbed by
    #: a containment rule, so a variant is a recorded curation decision and not a hole.
    #: Each must contain `expected_title`, so a variant can only *extend* the title the
    #: curator claimed and cannot quietly substitute a different work's. That is
    #: containment between two strings the same curator wrote, checked in a reviewed file —
    #: not between a curator's guess and whatever a registry returned, which is the rule
    #: `titles_matching` deleted.
    expected_title_variants: list[str] = Field(default_factory=list)
    #: The attribution, e.g. `Hamblin (1981)`.
    attributed_to: str
    #: Closed set, singular and plural, so the composed statement agrees with a one-author
    #: or many-author attribution without letting a curator write an arbitrary predicate.
    verb: Literal[
        "reports", "report", "asserts", "assert", "records", "record", "concludes", "conclude"
    ] = "reports"
    #: The object-level proposition, as a clause. Never stored on its own.
    assertion: str
    tier: ConfidenceTier
    #: Verbatim text from the work, as the registry served it. Required for any tier above
    #: `inferred`; checked as a substring under `normalize_text`.
    quote: str | None = None
    #: Why the curator holds that `assertion` follows from `quote`. The audit trail for
    #: the one link in the chain no machine here checks.
    note: str

    @property
    def statement(self) -> str:
        """The attributive proposition that becomes `Fact.statement`."""
        return f"{self.attributed_to} {self.verb} that {self.assertion}"

    def external_key(self) -> ExternalKey:
        return ExternalKey.parse(self.key)

    @model_validator(mode="after")
    def _validate(self) -> SeedFact:
        for name in (
            "slug",
            "claim_scope",
            "expected_title",
            "attributed_to",
            "assertion",
            "note",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"seed row field {name!r} is empty")
        if self.quote is not None and not self.quote.strip():
            raise ValueError("quote is present but empty; omit it instead")
        primary = normalize_text(self.expected_title)
        for variant in self.expected_title_variants:
            if primary not in normalize_text(variant):
                raise ValueError(
                    f"declared title variant {variant!r} does not contain the expected "
                    f"title {self.expected_title!r}; a variant may extend the title this "
                    "row claims, never replace it with another work's"
                )
        if self.tier is ConfidenceTier.CORROBORATED_MULTI_SECONDARY:
            raise ValueError(
                "a seed row cannot claim corroborated-multi-secondary: corroboration is "
                "agreement between independent sources on one assertion, and the seed has "
                "no mechanism that establishes it (M5-T2 owns promotion)"
            )
        return self
