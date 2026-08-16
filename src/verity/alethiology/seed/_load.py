"""Parsing, gating and writing the corpus — the pipeline the CLI drives."""

from __future__ import annotations

import json
from pathlib import Path

from verity.alethiology.resolution import ResolutionArtifact
from verity.alethiology.seed._constants import SEED_OWNED_FIELDS
from verity.alethiology.seed._gate import TierAssessment, assess
from verity.alethiology.seed._project import to_fact
from verity.alethiology.seed._report import SeedLoadReport, SeedRowOutcome
from verity.alethiology.seed._row import SeedError, SeedFact
from verity.ids import content_hash, normalize_text
from verity.keys import InvalidKeyError
from verity.models.fact import Fact, fact_identity
from verity.store.facts import load_fact, save_facts


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
                identity_matched_titles=assessment.identity_matched_titles,
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

    # `status` is absent from `SEED_OWNED_FIELDS`, which is what keeps a re-seed from
    # resurrecting a fact the JTMS flipped OUT — design.md §4.2 makes a correction a new
    # fact asserted and the old one demoted, never an edit that erases the invalidation.
    data = existing.model_dump()
    data.update({name: getattr(fact, name) for name in SEED_OWNED_FIELDS})
    merged = Fact.model_validate(data)
    return (existing, "unchanged") if merged == existing else (merged, "updated")


def report_to_json(report: SeedLoadReport) -> str:
    return json.dumps(
        report.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False
    )
