"""Gated row plus resolution record -> `Fact`. The one place a seed becomes a record.

**No retraction reading is written here, and that is the whole of this tier's position on
retraction.** The seed once projected the artifact's Retraction Watch reading into a check,
which meant two modules encoded what an absence from that table means — and only one of
them could do it honestly. The artifact records `found` as a boolean with no note of which
copy of the table answered, so a seed reading a miss cannot tell "absent from 71,799
recorded retractions", which is evidence the work stands, from "absent from the committed
two-row sample", which is evidence of nothing. M7-T1 resolves the table before it reads it
and therefore can. A freshly seeded fact carries an empty check map and `unknown`, which is
what a work nobody has checked is entitled to; `python -m verity.quality apply` fills it,
and `SEED_OWNED_FIELDS` excludes `evidence_quality`, so a re-seed cannot clobber what that
found.
"""

from __future__ import annotations

from verity.alethiology.resolution import REGISTRY_SOURCES, KeyResolution, ResolutionArtifact
from verity.alethiology.seed._gate import TierAssessment
from verity.alethiology.seed._row import SeedFact
from verity.models.common import ConfidenceTier, Provenance
from verity.models.fact import Fact


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
        created_at=checked_at,
    )
