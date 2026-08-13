# REMEDIATION_LOG.md — Pass 4.5

**Date:** 2026-08-13
**Pass:** 4.5 — Red-team remediation + negative-hypothesis stress searches
**Rule:** Every edit logged here with file, row/section, before → after, and red-team finding answered.

---

## A. Matrix corrections (literature.jsonl)

### A.1 — lit-022: corrected "independent replication" note
**File:** `research/matrix/literature.jsonl`, row `lit-022`
**Field:** `not_handled_relative_to_verity`
**Red-team finding answered:** 2.1 ("§4 'independently corroborated' is unsupported") and 1b(3) (prescription to reword lit-022 row note)

**Before:**
> "Corroborates Costello et al. 2024 direction despite the EoC; motivation not component evaluation. Messenger-irrelevance finding is independent replication value for Verity's motivation section."

**After:**
> "Corroborates Costello et al. 2024 direction despite the EoC; motivation not component evaluation. Same-team replication with partial author overlap (Boissin, Costello, Spinoza-Martín, Rand & Pennycook — three of five authors shared with lit-020: Costello, Rand, Pennycook); not an independent replication."

---

### A.2 — lit-017: baseline-attribution erratum
**File:** `research/matrix/literature.jsonl`, row `lit-017`
**Field:** `metrics_and_best_numbers`
**Red-team finding answered:** 2.7 ("Matrix erratum: baseline 0.202 attached to 2024 metric as well as 2025; report B gives 0.202 only for the 2025 Ev2R metric")

**Before:**
> "2024 shared task (Hungarian METEOR): TUDA_MAI 63%, AIC CTU 50.4%, baseline 0.202. 2025 (Ev2R metric): CTU AIC 0.332, HerO2 0.271, baseline 0.202. Conflicting/Cherry-picking class near-zero F1 for most systems."

**After:**
> "2024 shared task (Hungarian METEOR): TUDA_MAI 63%, AIC CTU 50.4% (no baseline figure reported for 2024 metric). 2025 (Ev2R metric): CTU AIC 0.332, HerO2 0.271, baseline 0.202. Conflicting/Cherry-picking class near-zero F1 for most systems. Note: 2024 and 2025 metric scores are not comparable (different metric formulas)."

---

## B. SYNTHESIS.md corrections

### B.1 — §4: replaced "independently corroborated" with accurate language
**File:** `research/SYNTHESIS.md`, §4 Proposal skeleton — "Motivation citation (baked in)" paragraph
**Red-team finding answered:** 2.1 / 1b(3) ("Both corroborating citations are same-team; 'independently corroborated' is false as written")

**Before:**
> "...paired with the PNAS Nexus 2025 perceived-human replication (lit-022) and the 'Just the facts' mechanism preprint (lit-021) — the direction (evidence exposure moves beliefs) is independently corroborated; exact effect sizes are treated as upper bounds pending correction. Verity's human endpoint is discernment, not persuasion (lit-023)."

**After:**
> "...paired with the PNAS Nexus 2025 perceived-human replication (lit-022, three shared authors: Costello, Rand, Pennycook) and the 'Just the facts' mechanism preprint (lit-021, same authors, unreviewed) — the direction (evidence exposure moves beliefs) is corroborated by same-team replications only; no fully independent replication is in the matrix; exact effect sizes are treated as upper bounds pending correction. Verity's human endpoint is discernment, not persuasion (lit-023); the verdict boundary is further motivated by lit-024 (same machinery amplifies conspiracy beliefs when directed at persuasion, not inspection)."

---

### B.4 — §4: added lit-024 to proposal skeleton citation rule (combined with B.1 edit above)
**File:** `research/SYNTHESIS.md`, §4 Proposal skeleton — "Motivation citation (baked in)" paragraph
**Red-team finding answered:** 1b(4) ("lit-024 currently appears nowhere in the proposal skeleton — add it")

Change: Added "the verdict boundary is further motivated by lit-024 (same machinery amplifies conspiracy beliefs when directed at persuasion, not inspection)" to the motivation citation paragraph. See B.1 above (same edit).

---

### B.2 — H3' enumeration sentence corrected
**File:** `research/SYNTHESIS.md`, §1 H3 verdict paragraph
**Red-team finding answered:** 2.4 ("H3' enumeration sentence is false as written — 'every transparency-only row sits at article, source, or citation level' — three of five transparency-only rows are not at those levels")

**Before:**
> "The pivot H3' survives by enumeration: every transparency-only row sits at article, source, or citation level; the decomposed-premise-level candidates all fail it — SAFE and FActScore issue verdicts (product-010, -011), Loki is atomic-not-entailment and ultimately verdict-producing (product-009), Kialo is premise-structured and no-verdict but fully manual with no evidence layer (product-019). H3' is adopted for all downstream positioning."

**After:**
> "The pivot H3' survives by enumeration: the five transparency-only rows span article level (Ground News, product-001; Penn MBD, product-004), claim level (Perplexity, product-006; Loki, product-009), and argument-graph level (Kialo, product-019) — none at the decomposed-premise level of a composite claim. The claim-level candidates each fail H3' for independent reasons: Perplexity has no symmetric contrasting evidence and no decomposition (product-006, `symmetric_contrasting_evidence: no`, `claim_decomposition: none`, lowest-confidence row in the matrix); Loki decomposes into independent atomic facts not entailment-linked premises, and ultimately produces a verdict (product-009). The argument-graph candidate (Kialo) is fully manual with no evidence layer (product-019). SAFE and FActScore also issue verdicts (product-010, -011). H3' is adopted for all downstream positioning."

---

### B.3 — §2: AVeriTeC knowledge store contradiction resolved
**File:** `research/SYNTHESIS.md`, §2 Positioning statement
**Red-team finding answered:** 2.5 ("§2 contradicts the matrix on AVeriTeC's knowledge store: product-014 codes `persistent_knowledge_reuse: none` — a benchmark artifact, not a reusable persistent KB")

**Before:**
> "Persistent fact stores ship today (Wolfram Alpha's curated Knowledgebase, product-008; the ClaimReview fact-check cache behind Squash, product-015; AVeriTeC's knowledge store, product-014) — but none is dependency-tracked..."

**After:**
> "Persistent fact stores ship today (Wolfram Alpha's curated Knowledgebase, product-008; the ClaimReview fact-check cache behind Squash, product-015) — but none is dependency-tracked... [Note: AVeriTeC's knowledge store (product-014) codes `persistent_knowledge_reuse: none` — it is a benchmark artifact, not a reusable persistent KB, and has been removed from this list per red-team finding 2.5.]"

---

## C. Negative-hypothesis stress searches

See `research/STRESS_SEARCH.md` (written after web search agent returned results, 2026-08-13).

## D. RedacTek row verification

See `research/STRESS_SEARCH.md` §D (written after URL fetch, 2026-08-13).

## E. Targeted source verification

See `research/STRESS_SEARCH.md` §E (written after URL fetch, 2026-08-13).
