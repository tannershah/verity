"""Gated row plus resolution record -> `Fact`. The one place a seed becomes a record."""

from __future__ import annotations

from verity.alethiology.resolution import (
    REGISTRY_SOURCES,
    RETRACTION_WATCH,
    KeyResolution,
    ResolutionArtifact,
)
from verity.alethiology.seed._gate import TierAssessment
from verity.alethiology.seed._row import SeedFact
from verity.models.common import (
    ConfidenceTier,
    Provenance,
    RetractionFinding,
    RetractionSource,
    RetractionStatus,
)
from verity.models.evidence import EvidenceQuality, RetractionCheck
from verity.models.fact import Fact


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
