"""Seeding the alethiology: the curated corpus, and the gate it has to pass.

design.md §6 names the standing risk — the alethiology "starts empty and is populated by
the system's own least-validated outputs," with NELL (`lit-025`) as the cautionary tale.
A hand-curated seed is a sharper version of the same problem: an agent asserting
propositions about works it may not have read, keyed to identifiers that may not exist, at
tiers that feed the numerator of a pre-registered measurement.

So a seed row is not a fact record. It is a claim about a work, and the loader is what
decides how much of that claim survives:

- **The key must resolve, to the work the curator named.** Checked against the committed
  `key_resolution.json`. An identifier absent from every registry aborts the load; one
  that resolves to a *different* title loads with its tier capped and the mismatch
  reported, because that case is real — Retraction Watch and both registries disagree
  about what `10.3823/1654` identifies while agreeing it is retracted.
- **Statements are attributive by construction.** `attributed_to` and `assertion` are
  separate fields and the statement is composed from them, so "Hamblin (1981) reports that
  X" is representable and a bare "X" is not. This matters because grounding is exact-key
  match and never reads a statement: an object-level fact would ground any premise sharing
  its identifier as `verified`, and a quote from an abstract cannot establish that a
  proposition is true — only that a work asserts it.
- **A grounding-eligible tier has to be earned from quoted text.** `verified-primary`
  requires a verbatim quote from the work's own abstract as the registry served it. A
  quote that matches nothing aborts the load; no quote at all caps the row at `inferred`.
  `corroborated-multi-secondary` is refused outright — the seed has no mechanism that
  could justify it, and both tiers feed the pre-registered rate.

**What is machine-checked, stated plainly.** That the key resolves, that it resolves to
the named work, and that the quote is verbatim from that work. That the *assertion*
follows from the quote is curator judgment, recorded next to it in the seed file for
audit. The gate narrows what can be claimed; it does not read for meaning.

**Field ownership on re-load.** The seed owns `statement`, `key`, `tier`, provenance and
`created_at`. The store owns `status`, `revalidated_at`, `justification_ids`, and any
`evidence_quality` written after curation. Re-seeding never resurrects a fact the JTMS
flipped OUT — that is the same resurrection failure as an M8 recomputation over a
vacuously-satisfied justification, arriving through the loader instead.

**No justifications are written.** `Justification` models Doyle's IN-list only, so a
premise justification with no antecedents is vacuously satisfied and any M8-T1 status
recomputation would restore a demoted seed fact to IN forever. **Blocker on M8-T1:**
`Justification` needs an out-list (Doyle 1979's SL-justification) before a seeded fact can
carry one. Until then seed facts are IN with no justification, and M8-T1 decides what that
means rather than inheriting a decision made here.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from verity.alethiology.resolution import (
    REGISTRY_SOURCES,
    RETRACTION_WATCH,
    KeyResolution,
    ResolutionArtifact,
)
from verity.base import FrozenModel, VerityModel
from verity.ids import content_hash, normalize_text
from verity.keys import ExternalKey, InvalidKeyError
from verity.models.common import (
    ConfidenceTier,
    Provenance,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
)
from verity.models.evidence import EvidenceQuality, RetractionCheck
from verity.models.fact import Fact, fact_identity
from verity.store.facts import load_fact, save_facts

#: Strongest-first, so a *higher* rank is a weaker claim and capping is `max` on the rank.
#: Mirrors `grounding.TIER_RANK`. Stated carefully because reordering this tuple to match
#: a wrong comment would invert the cap in `assess` into an amplifier, silently.
_TIER_ORDER = (
    ConfidenceTier.VERIFIED_PRIMARY,
    ConfidenceTier.CORROBORATED_MULTI_SECONDARY,
    ConfidenceTier.SINGLE_SECONDARY,
    ConfidenceTier.INFERRED,
    ConfidenceTier.MARKETING_CLAIM,
)
_TIER_RANK = {tier: rank for rank, tier in enumerate(_TIER_ORDER)}

#: Sources are searched for a quote in this order, and the first match is the one
#: recorded. Registries before the curated index, so a quote that could come from either
#: is attributed to the work rather than to a database about the work.
_QUOTE_SOURCE_ORDER = (*REGISTRY_SOURCES, RETRACTION_WATCH)
#: Within a source: the work's own prose before its title, since a title match supports
#: far less than an abstract match and the tier cap distinguishes them.
_QUOTE_FIELD_ORDER = ("abstract", "record", "title")

#: Fields the seed owns on re-load. Everything else on an existing row is the store's.
_SEED_OWNED = ("statement", "key", "tier", "provenance", "created_at", "supporting_quote")

#: Words a quote must have before it can carry `verified-primary`. Substring containment
#: is not evidence on its own: measured against the committed corpus, every quote that
#: earns the top tier is 5-23 words and occurs exactly once in the abstract it matched,
#: while the degenerate cases this floor exists to exclude ("a", "the", "iron") are single
#: words occurring 3-84 times. Short quotes are still legitimate for a curated index's
#: record fields — an author name is two words and is the whole datum — so the floor gates
#: the tier rather than aborting the row.
MIN_PRIMARY_QUOTE_WORDS = 5


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
    #: What the curator believes `key` identifies. Compared to what the registries return.
    expected_title: str
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
        if self.tier is ConfidenceTier.CORROBORATED_MULTI_SECONDARY:
            raise ValueError(
                "a seed row cannot claim corroborated-multi-secondary: corroboration is "
                "agreement between independent sources on one assertion, and the seed has "
                "no mechanism that establishes it (M5-T2 owns promotion)"
            )
        return self


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
    for source in _QUOTE_SOURCE_ORDER:
        reading = resolution.reading(source)
        if reading is None or not reading.found:
            continue
        texts = reading.quotable_text
        for field in _QUOTE_FIELD_ORDER:
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

    identity = resolution.titles_matching(row.expected_title)
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

    effective = row.tier if _TIER_RANK[row.tier] >= _TIER_RANK[allowed] else allowed
    if effective is not row.tier:
        notes.append(f"requested {row.tier.value}, capped to {effective.value}")

    return TierAssessment(
        allowed_tier=allowed,
        effective_tier=effective,
        identity_confirmed_by=identity,
        identity_mismatch=not identity,
        registry_identity_conflict=conflict,
        quote_match=match,
        notes=notes,
    )


def _retraction_check(resolution: KeyResolution) -> dict[RetractionSource, RetractionCheck]:
    """The Retraction Watch reading, as a check. A reading, not a policy cut (M7-T1 owns that).

    Only Retraction Watch is seeded. OpenAlex `is_retracted` and Crossref `update-to` stay
    in the resolution artifact as fixture data so the Phase-4 retraction path produces them
    live — a demo that renders three hand-typed agreements shows nothing a checker did.
    """
    reading = resolution.reading(RETRACTION_WATCH)
    if reading is None:
        return {}
    if not reading.found:
        result = RetractionFinding.NOT_INDEXED
        detail = None
    else:
        nature = reading.detail.get("nature", "")
        # The table mixes notice types: over the 71,799-row snapshot, 66,287 rows are
        # `Retraction` and 5,512 are `Expression of concern`, `Correction`,
        # `Reinstatement`, or blank. Only the first is a retraction.
        #
        # The others are NOT_INDEXED rather than CLEAN, which is the conservative reading
        # of a three-value enum that cannot say "indexed, with a notice that is not a
        # retraction". `RetractionFinding.CLEAN` asserts a source looked and found nothing;
        # reporting an expression of concern that way is the same error the enum's own
        # docstring rules out one step over — it would let a flagged work read as checked
        # and clean, and outvote a source that did find something. The nature travels in
        # `detail` either way, so M7-T1 has what it needs when it writes the policy.
        #
        # **Input to M7-T1:** the honest fix is a fourth finding for "indexed with a
        # non-retraction notice". Introducing it here would set the vocabulary that tier's
        # cut is written against, which is not this tier's call.
        result = (
            RetractionFinding.RETRACTED
            if "retraction" in nature.casefold()
            else RetractionFinding.NOT_INDEXED
        )
        detail = "; ".join(f"{k}={v}" for k, v in sorted(reading.detail.items())) or None
    return {
        RetractionSource.RETRACTION_WATCH: RetractionCheck(
            source=RetractionSource.RETRACTION_WATCH,
            result=result,
            checked_at=reading.checked_at,
            source_url=reading.url,
            detail=detail,
        )
    }


def to_fact(
    row: SeedFact,
    assessment: TierAssessment,
    resolution: KeyResolution,
    artifact: ResolutionArtifact,
    *,
    seed_path: str,
) -> Fact:
    """Project a gated seed row into a fact record.

    Provenance is two entries, deliberately. The backing entry says a source served this
    text at this time, and its `confidence_tier` is set by *what the quote matched* — never
    by the fact that a request returned successfully. "This identifier resolves" and "this
    source is primary-verified" are different claims, and `Fact` says M5-T2's promotion
    reads the source tier off this list. The curation entry says a curator asserted the
    statement, and is always `inferred`.

    `created_at` is the backing source's check time rather than a load-time `now()`:
    grounding's tie-break orders on it, and a wall-clock value would make which fact a
    graph names depend on when the store happened to be seeded.
    """
    backing_source = (
        assessment.quote_match.source
        if assessment.quote_match
        else next(
            (s for s in REGISTRY_SOURCES if (r := resolution.reading(s)) and r.found), None
        )
    )
    reading = resolution.reading(backing_source) if backing_source else None
    checked_at = reading.checked_at if reading else artifact.generated_at

    provenance = [
        Provenance(
            source=backing_source or "unresolved",
            source_url=reading.url if reading else None,
            accessed_at=checked_at,
            confidence_tier=assessment.allowed_tier,
        ),
        Provenance(
            source="seed",
            source_url=f"{seed_path}#{row.slug}",
            accessed_at=artifact.generated_at,
            confidence_tier=ConfidenceTier.INFERRED,
        ),
    ]

    return Fact(
        statement=row.statement,
        key=row.external_key(),
        tier=assessment.effective_tier,
        provenance=provenance,
        supporting_quote=row.quote,
        evidence_quality=EvidenceQuality(
            # The cut between `retracted` and `flagged-unconfirmed` is M7-T1's; the seed
            # records what Retraction Watch said and concludes nothing.
            retraction=RetractionStatus.UNKNOWN,
            retraction_checks=_retraction_check(resolution),
        ),
        created_at=checked_at,
    )


class SeedRowOutcome(VerityModel):
    """What happened to one row. Every cap and mismatch is named, never aggregated away."""

    slug: str
    claim_scope: str
    fact_id: str
    key: ExternalKey
    action: Literal["inserted", "updated", "unchanged", "assessed"]
    requested_tier: ConfidenceTier
    effective_tier: ConfidenceTier
    capped: bool
    grounding_eligible: bool
    identity_confirmed_by: list[str] = Field(default_factory=list)
    identity_mismatch: bool = False
    registry_identity_conflict: bool = False
    quote_source: str | None = None
    quote_field: str | None = None
    notes: list[str] = Field(default_factory=list)


class SeedLoadReport(VerityModel):
    """The load, in full. Deterministic: no field is a wall-clock reading."""

    seed_path: str
    seed_digest: str
    resolution_generated_at: datetime
    applied: bool
    rows: list[SeedRowOutcome] = Field(default_factory=list)

    @property
    def by_action(self) -> dict[str, int]:
        return dict(sorted(Counter(row.action for row in self.rows).items()))

    @property
    def by_tier(self) -> dict[str, int]:
        return dict(sorted(Counter(row.effective_tier.value for row in self.rows).items()))

    @property
    def by_scope(self) -> dict[str, int]:
        return dict(sorted(Counter(row.claim_scope for row in self.rows).items()))

    @property
    def by_key_type(self) -> dict[str, int]:
        return dict(sorted(Counter(row.key.type.value for row in self.rows).items()))

    @property
    def grounding_eligible(self) -> int:
        return sum(1 for row in self.rows if row.grounding_eligible)

    @property
    def capped(self) -> list[SeedRowOutcome]:
        return [row for row in self.rows if row.capped]

    @property
    def identity_mismatches(self) -> list[SeedRowOutcome]:
        """Rows where no source, or no registry, identifies the key as the named work."""
        return [
            row for row in self.rows if row.identity_mismatch or row.registry_identity_conflict
        ]

    def render(self) -> str:
        """A text summary. Counts are reported, never targeted (evaluation.md §6)."""
        lines = [
            f"seed:            {self.seed_path} ({self.seed_digest[:12]})",
            f"resolution:      recorded {self.resolution_generated_at.isoformat()}",
            f"mode:            {'applied' if self.applied else 'dry run (nothing written)'}",
            f"rows:            {len(self.rows)}",
            f"  by action:     {self.by_action}",
            f"  by scope:      {self.by_scope}",
            f"  by key type:   {self.by_key_type}",
            f"  by tier:       {self.by_tier}",
            f"grounding-eligible facts: {self.grounding_eligible}",
        ]
        if self.capped:
            lines.append(f"tier-capped rows ({len(self.capped)}):")
            lines += [f"  - {row.slug}: {'; '.join(row.notes)}" for row in self.capped]
        if self.identity_mismatches:
            lines.append(f"work-identity mismatches ({len(self.identity_mismatches)}):")
            lines += [f"  - {row.slug} ({row.key})" for row in self.identity_mismatches]
        return "\n".join(lines)


def read_seed(path: Path | str) -> list[SeedFact]:
    """Parse the JSONL, refusing duplicates and anything the row model does not declare.

    Duplicates are judged on `fact_identity` — the store's own derivation — rather than on
    the raw text. The two are not the same question: `statement_hash` folds case and
    collapses whitespace, so two rows differing only in capitalization are two strings and
    one fact. Checking the raw text let such a pair through, and because the id they share
    is what the store keys on, the second silently overwrote the first while the load
    report claimed both were inserted. Keying the check on the same derivation the store
    uses is what makes the report's counts true.
    """
    text = Path(path).read_text(encoding="utf-8")
    rows: list[SeedFact] = []
    seen_slugs: dict[str, str] = {}
    seen_facts: dict[tuple[str, str], str] = {}

    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            row = SeedFact.model_validate_json(line)
        except Exception as exc:
            raise SeedError(f"{path}:{number}: {exc}") from exc
        try:
            key = row.external_key()
        except InvalidKeyError as exc:
            raise SeedError(f"{path}:{number}: {exc}") from exc

        # Slugs become the anchor a reader follows from a fact's provenance back to the
        # row that argued for it, so two that differ only in case are one ambiguous anchor.
        slug = normalize_text(row.slug)
        if slug in seen_slugs:
            raise SeedError(f"{path}:{number}: duplicate slug {row.slug!r}")
        identity = fact_identity(key, row.statement)
        if identity in seen_facts:
            raise SeedError(
                f"{path}:{number}: same (key, statement) as row {seen_facts[identity]!r} "
                "once case and whitespace are folded; a fact's identity is that pair, so "
                "the two rows are one fact and the second would overwrite the first"
            )
        seen_slugs[slug] = row.slug
        seen_facts[identity] = row.slug
        rows.append(row)

    if not rows:
        raise SeedError(f"{path} contains no seed rows")
    return rows


def load_seed(
    conn,
    seed_path: Path | str,
    resolution_path: Path | str,
    *,
    apply: bool = True,
) -> SeedLoadReport:
    """Gate every row, then write the survivors. Aborts before writing anything.

    Parsing and assessment run over the whole file first, so a malformed row on line 40
    cannot leave rows 1-39 in the store. `apply=False` runs the gate and reports without
    touching the database.
    """
    seed_path = Path(seed_path)
    artifact = ResolutionArtifact.load(resolution_path)
    rows = read_seed(seed_path)
    seed_ref = seed_path.as_posix()

    prepared: list[tuple[SeedFact, TierAssessment, Fact]] = []
    for row in rows:
        resolution = artifact.get(row.external_key())
        if resolution is None:
            raise SeedError(
                f"{row.slug}: {row.external_key()} is absent from {resolution_path}. "
                "Re-run `python -m verity.alethiology verify-keys` before seeding it."
            )
        assessment = assess(row, resolution)
        fact = to_fact(row, assessment, resolution, artifact, seed_path=seed_ref)
        prepared.append((row, assessment, fact))

    # Merge against what is already stored, then write the whole batch in one
    # transaction: the gate rules on every row before anything is written, and a
    # per-row commit would end that guarantee at the first INSERT.
    outcomes: list[SeedRowOutcome] = []
    resolved: list[tuple[SeedFact, TierAssessment, Fact, str]] = []
    for row, assessment, fact in prepared:
        merged, action = _merge(conn, fact) if apply else (fact, "assessed")
        resolved.append((row, assessment, merged, action))

    if apply:
        save_facts(conn, [fact for _, _, fact, action in resolved if action != "unchanged"])

    for row, assessment, fact, action in resolved:
        outcomes.append(
            SeedRowOutcome(
                slug=row.slug,
                claim_scope=row.claim_scope,
                fact_id=fact.id,
                key=fact.key,
                action=action,  # type: ignore[arg-type]
                requested_tier=row.tier,
                effective_tier=fact.tier,
                capped=assessment.capped,
                grounding_eligible=fact.is_verified,
                identity_confirmed_by=assessment.identity_confirmed_by,
                identity_mismatch=assessment.identity_mismatch,
                registry_identity_conflict=assessment.registry_identity_conflict,
                quote_source=assessment.quote_match.source if assessment.quote_match else None,
                quote_field=assessment.quote_match.field if assessment.quote_match else None,
                notes=assessment.notes,
            )
        )

    return SeedLoadReport(
        seed_path=seed_ref,
        seed_digest=content_hash(seed_path.read_text(encoding="utf-8")),
        resolution_generated_at=artifact.generated_at,
        applied=apply,
        rows=outcomes,
    )


def _merge(conn, fact: Fact) -> tuple[Fact, str]:
    """The fact as it should be stored, preserving every field the store owns.

    Decides; does not write. The write is one batched transaction in `load_seed`, so the
    atomicity of the gate and the atomicity of the store match.
    """
    existing = load_fact(conn, fact.id)
    if existing is None:
        return fact, "inserted"

    # `status` is absent from `_SEED_OWNED`, which is what keeps a re-seed from
    # resurrecting a fact the JTMS flipped OUT — design.md §4.2 makes a correction a new
    # fact asserted and the old one demoted, never an edit that erases the invalidation.
    data = existing.model_dump()
    data.update({name: getattr(fact, name) for name in _SEED_OWNED})
    merged = Fact.model_validate(data)
    return (existing, "unchanged") if merged == existing else (merged, "updated")


def report_to_json(report: SeedLoadReport) -> str:
    return json.dumps(
        report.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False
    )
