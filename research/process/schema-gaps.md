# SCHEMA_GAPS.md — Pass 2 structural gaps

Seven structural gaps found. No schema modification made; all cells mapped to closest enum with extraction_note.

---

## Gap 1 — `interactivity` enum too binary

Enum: ["static", "inspectable-drilldown"]. Does not capture:
- Active search/query interfaces (scite, Wolfram Alpha, Perplexity)
- Side-by-side comparison/juxtaposition views (Ground News Blindspot, Penn Media Bias Detector topic/publisher comparisons)
- Browser-extension overlays (Ground News)
- API-as-primary-access (RetractionCheck, Crossref API, SAFE/FActScore as code libraries)

Products with rich but non-drilldown UI (Ground News, scite, Penn Media Bias Detector, Wolfram Alpha) were all mapped to "inspectable-drilldown" as closest; this loses meaningful interactivity distinctions.

## Gap 2 — `access_model` missing "open-source" bucket

Enum: ["free", "freemium", "API", "institutional"]. Three products are open-source GitHub releases with no usage restriction: Loki/OpenFactVerification, SAFE (Google DeepMind), FActScore. Open-source is structurally distinct from "free" (no code access/self-hosting) and "API" (programmatic paid access). Mapped to "free" with extraction_notes throughout.

## Gap 3 — `unit_of_analysis` missing "computational-query" bucket

Enum: ["article", "claim", "citation", "argument-graph"]. Wolfram Alpha's input is a mathematical/computational query — not an epistemic claim, article, citation, or argument in the fact-checking sense. No enum fits; mapped to "claim" with extraction_note. Also: FActScore, SAFE, and the entailment-tree benchmarks use "atomic fact" as their unit, which sits between "claim" (too broad) and "citation" (too specific); mapped to "claim" throughout.

## Gap 4 — `coverage_domain` missing "computational-facts" bucket

Enum: ["news", "scientific-literature", "political-claims", "general"]. Wolfram Alpha covers math, geography, finance, physics, chemistry — computational factual queries, not any of the above. Mapped to "general" as closest.

## Gap 5 — No "product_type" / "target_audience" column

Report explicitly distinguishes consumer products, professional/journalist tools, developer/researcher libraries, and academic benchmarks. This distinction is load-bearing for H1 ("No *consumer* product..."). No schema field captures it; the distinction is carried only in extraction_notes and EXTRACTION_NOTES.md.

## Gap 6 — `claim_decomposition` conflates "claim detection" with "premise decomposition"

Enum: ["none", "manual", "automatic"]. The report distinguishes:
- Claim *detection* (identifying check-worthy sentences from a document): Factiverse, Originality.ai, Full Fact AI
- Premise *decomposition* (splitting a composite claim into load-bearing premises that jointly entail it): Loki, SAFE, FActScore, entailment-tree systems

Both Factiverse and Originality.ai perform automatic claim detection but NOT decomposition. "automatic" would suggest decomposition; "none" loses the detection capability. Mapped to "none" with extraction_note for detection-only products.

## Gap 7 — `symmetric_contrasting_evidence` binary can't capture partial symmetry

Enum: ["yes", "no"]. Penn Media Bias Detector compares publishers across ideological spectrum but not supporting/contrasting evidence per claim — "partial" is the most accurate characterization. Logically shows support/contradict/partial per source breakdown. Mapped to "yes" with extraction_note noting partial applicability.

## Gap 8 — provenance `confidence` enum lacks tier granularity (added pass 7)

Enum: verified | inferred | marketing-claim. The RedacTek episode (committee Q7: cells upgraded to "verified" by re-reading the same single secondary review they were inferred from) showed "verified" conflates verified-against-primary with corroborated-by-one-secondary. Adopted tier vocabulary — **verified-primary / corroborated-multi-secondary / single-secondary / inferred / marketing-claim** — cannot be encoded because the schema is frozen. Carried instead in extraction_notes ("single-secondary", "single-pass characterization — verify before proposal use") per this gap. product-024 (RedacTek) is single-secondary throughout; pass-7 rows added from unreplicated committee findings (product-026, -028, -029; lit-034) are single-pass.
