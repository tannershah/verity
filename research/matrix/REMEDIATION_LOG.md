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

---

# REMEDIATION_LOG.md — Pass 4.6

**Date:** 2026-08-13
**Pass:** 4.6 — Escalation rulings (Tanner)
**Rule:** Every edit logged here with file, row/section, before → after, and escalation resolved.

---

## F. H4b verdict refinement (SYNTHESIS.md + literature.jsonl)

### F.1 — H4b phrasing_note refined
**File:** `research/SYNTHESIS.md`, §1 H4 verdict — H4b JSON object
**Escalation resolved:** Zhang et al. 2025 (CACDD) ruled to test atomic-claim identification only (Chinese/WebCPM), not joint sufficiency / load-bearing entailment structure; FactLens (Mitra et al., ACL Findings 2025) likewise tests fine-grained sub-claim verification, not entailment-preserving decomposition. H4b remains proxy-only.

**Before:**
> `"phrasing_note": "None found as of Aug 2026: no gold standard exists; measurement is proxy-only (DecompScore, entailment coverage, verifier-confidence deltas)."`

**After:**
> `"phrasing_note": "Proxy-only for entailment-structured decomposition faithfulness; gold benchmarks exist only for atomic-claim identification (CACDD, Zhang et al. 2025, Chinese/WebCPM; cf. FactLens, Mitra et al., ACL Findings 2025, fine-grained sub-claim verification). Neither tests joint sufficiency / load-bearing structure. None found for entailment-preserving decomposition as of Aug 2026."`

---

### F.2 — H4b escalation text resolved
**File:** `research/SYNTHESIS.md`, §1 H4 — paragraph following the JSON array
**Escalation resolved:** same as F.1.

**Before:**
> "H4b targeted search performed 2026-08-13: one ESCALATE (Zhang et al. 2025, "A Claim Decomposition Benchmark for Long-Form Answer Verification," SpringerLink) — Tanner to determine whether it tests entailment-preservation of decompositions or only downstream verification accuracy; verdict on hold."

**After:**
> "H4b targeted search performed 2026-08-13: CACDD (Zhang et al. 2025, "A Claim Decomposition Benchmark for Long-Form Answer Verification," SpringerLink, doi:10.1007/978-981-96-1710-4_4) tests atomic-claim identification in Chinese/WebCPM context only; FactLens (Mitra et al., ACL Findings 2025, aclanthology.org/2025.findings-acl.929) tests fine-grained sub-claim verification. Neither tests joint sufficiency or load-bearing entailment structure. Ruling (pass 4.6): proxy-only; both added to literature.jsonl as lit-029 and lit-030, bucket claim-decomposition-factuality."

---

### F.3 — lit-029 (CACDD) added to literature.jsonl
**File:** `research/matrix/literature.jsonl`
**Row added:** `lit-029` — Zhang et al. (2025), CACDD, SpringerLink/CCKS 2024, doi:10.1007/978-981-96-1710-4_4, arxiv.org/pdf/2410.12558
**Bucket:** claim-decomposition-factuality
**not_handled field:** states CACDD tests atomic-claim identification only; neither CACDD nor FactLens tests joint sufficiency / load-bearing entailment structure; confirms proxy-only for H4b.

---

### F.4 — lit-030 (FactLens) added to literature.jsonl
**File:** `research/matrix/literature.jsonl`
**Row added:** `lit-030` — Mitra et al. (2025), FactLens, ACL Findings 2025, aclanthology.org/2025.findings-acl.929
**Bucket:** claim-decomposition-factuality
**not_handled field:** states FactLens tests fine-grained sub-claim verification only; sub-claims are independent units, not load-bearing premises; confirms proxy-only for H4b.

---

## G. product-024 access_model correction (products.jsonl)

### G.1 — RedacTek access_model set from 'institutional' to 'freemium', confidence verified
**File:** `research/matrix/products.jsonl`, row `product-024`
**Escalation resolved:** Doody's review confirms individual subscription ~$3/mo as primary access model; not institutional-only. 'subscription' is not a schema enum value; 'freemium' is the closest available enum.

**Before:**
- `access_model`: "institutional"
- `provenance.access_model.confidence`: "inferred"
- extraction_note: "access_model ESCALATED (Doody's review shows $3/mo individual subscription as primary model, not institutional-only)"

**After:**
- `access_model`: "freemium"
- `provenance.access_model.confidence`: "verified"
- extraction_note: "access_model set to 'freemium' (closest enum; Doody's review confirms individual subscription ~$3/mo as primary model, confidence verified; 'subscription' not in schema enum)"

---

## H. Nature Index URL attribution fix (products.jsonl)

### H.1 — Nature Index URL moved from product-024 to product-020 extraction_note
**File:** `research/matrix/products.jsonl`, rows `product-020` and `product-024`
**Escalation resolved:** Nature Index article (nature.com/nature-index/news/new-bot-flags-scientific-research-studies-that-cite-retracted-papers) describes scite Reference Check (product-020), not RedacTek (product-024). URL was removed from product-024 provenance in pass 4.5; now added to product-020 extraction_note as corroborating provenance for automation_level.

**product-020 extraction_note — appended:**
> "Automation_level corroborated by Nature Index article (nature.com/nature-index/news/new-bot-flags-scientific-research-studies-that-cite-retracted-papers; describes scite Reference Check's primary-citation flagging, consistent with 'direct-status only' characterization; moved from product-024 provenance per pass 4.6)."

**product-024 extraction_note — updated:**
> "...moved to product-020 extraction_note per pass 4.6. See STRESS_SEARCH.md §D. Single-source row (Doody's only)."

---

# REMEDIATION_LOG.md — Pass 5

**Date:** 2026-08-13
**Pass:** 5 — Application drafting; Task 0 copy fixes required by the red team before drafting.

---

## I. "guarantees termination" replaced repo-wide (red team 1c adoption requirement)

### I.1 — SYNTHESIS.md §3.1 verifiability-descent row
**File:** `research/SYNTHESIS.md`, §3.1 table, "Verifiability descent" row, Meaning column
**Red-team finding answered:** 1c (termination is enforced, not guaranteed; the same row's own eval defines a non-terminating-branch rate) via the adoption requirement stated at the end of §3 of the red team.

**Before:**
> "each premise strictly easier to verify; guarantees termination"

**After:**
> "each premise strictly easier to verify; termination enforced by depth budget; grounding rate, depth, and budget-exit rate measured and reported."

### I.2 — CLAUDE.md decomposition validity criteria
**File:** `.claude/CLAUDE.md`, "Decomposition validity criteria (v0 spec + eval)" paragraph
**Red-team finding answered:** same as I.1.

**Before:**
> "verifiability descent (guarantees termination)"

**After:**
> "verifiability descent (termination enforced by depth budget; grounding rate, depth, and budget-exit rate measured and reported)"

### I.3 — Occurrences intentionally left unchanged
The four remaining occurrences of "guarantees termination" in `research/SYNTHESIS.md` (red-team section, findings 1c and the §3 adoption note) are the red team *quoting* the flawed phrase in order to criticize it. Rewriting them would falsify the review record; they are left as-is. No occurrence exists anywhere else in the repo (verified by grep, 2026-08-13).

---

## J. Bibliographic verification of residual citation debts (pass 5; web access per pass5 prompt)

All four residual debts verified 2026-08-13; `literature.jsonl` rows updated (source_url + derivation only, plus one page-number correction). No verdict or content-field changes.

### J.1 — lit-015 (FEVER)
Verified via aclanthology.org/N18-1074: Thorne, Vlachos, Christodoulopoulos & Mittal (2018), NAACL-HLT 2018 Volume 1 (Long Papers), pp. 809–819, doi:10.18653/v1/N18-1074. `source_url` set from `research/raw/report_b.md` to the ACL Anthology page. Confirms the EXTRACTION_NOTES suspicion: the sources_a.md "(FEVER)" label on aclanthology.org/2020.emnlp-main.609 was a mislabeling (that URL is SciFact, EMNLP 2020).

### J.2 — lit-022 (Boissin et al.)
Verified via Oxford Academic: PNAS Nexus 4(11):pgaf325, Nov 2025, doi:10.1093/pnasnexus/pgaf325; authors Boissin, Costello, Spinoza-Martín, Rand & Pennycook — the matrix row's citation string was already exactly correct. `source_url` set to the DOI.

### J.3 — lit-026 (Doyle 1979, JTMS)
Verified: Artificial Intelligence 12(3):231–272, doi:10.1016/0004-3702(79)90008-0. `source_url` set to the DOI.

### J.4 — lit-027 (de Kleer 1986, ATMS) — page-number correction
Verified via ACM DL journal record: "An assumption-based TMS," Artificial Intelligence 28(2):**127–162**, doi:10.1016/0004-3702(86)90080-9. The row's prior span 127–262 conflated the three-paper ATMS series with the ATMS paper proper; `paper` field corrected. DOI replaces the 403-walled academia.edu URL, as recommended in STRESS_SEARCH.md §E.

---

# REMEDIATION_LOG.md — Pass 7

**Date:** 2026-08-13
**Pass:** 7 — Committee-adjudicated remediation, chair-executed (see prompts/pass7_prompt.md for provenance). Committee record: 15 critical / 32 major / 17 minor findings, zero refuted under adversarial verification; defense responses (CONCEDE/HOLD/FIX) adjudicated; defense-introduced evidence independently verified by committee sweep before entering this log.

## K. Pass-6 §F chair corrections (STRESS_SEARCH.md)

### K.1 — ARGUMEND row corrected
**Finding answered:** chair re-verification (direct browser-UA fetch of argumend.org home/analyze/about, 2026-08-13) against the battery's single-pass judgment.
**Before:** judgment NEAR-MISS-FORCES-QUALIFIER; "operates over pre-selected topic positions, not... user-submitted composite claim"; described as no-verdict.
**After:** judgment NOT-A-COUNTEREXAMPLE (chair correction, pass 7): curated maps carry root-level Balance/Weight evidence-direction verdicts ("Balance shows which way the evidence tips") → excluded on the transparency-only term (same axis as Loki); the Analyze mode accepts user-pasted text but performs local document argument-mining without external evidence retrieval. "Crux Identification" recorded as prior art + demand evidence for the localization framing.

### K.2 — H3' verdict line amended; H3″ adopted
**Before:** two qualifiers recommended ("automated" + "user-submitted composite claim").
**After:** one qualifier ("automated", forced by Society Library + Kialo); second qualifier withdrawn per K.1. **H3″: "No automated system offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim."** Qualifier accretion resisted per red-team 1a.

## L. Matrix additions (committee findings Q8, battery §F, verification sweep)

- **product-025 Consensus** (sweep-verified: Meter, Study Snapshots, tiers) — strongest consumer near-neighbor; fast-follower #2; excluded from H3″ on transparency-only (root stance aggregate), from H1 on decomposition.
- **product-026 The Society Library** (single-pass; forces "automated" qualifier jointly with Kialo).
- **product-027 ARGUMEND** (chair-verified; root Balance/Weight verdicts; crux prior art).
- **product-028 Elicit** (single-pass; production N/study-design extraction — validates text-mining plan).
- **product-029 Community Notes** (single-pass; landscape honesty; touches no hypothesis).
- **lit-031 VITALITY Study I** (sweep-verified: direction reversed 8.4%, significance changed 16.0% of contaminated meta-analyses) — moat IMPACT evidence; linkage-eval seed corpus.
- **lit-032 Meyer et al. 2024** (sweep-verified: n=2,036, zero author overlap) — independent CONCEPTUAL replication, reflection paradigm.
- **lit-033 RetractoBot RCT** (sweep-verified: null, −0.007 [−0.055, 0.041]; 15,921 papers; 15,667 respondents, 80.6% unaware) — moat UPTAKE boundary condition.
- **lit-034 Belief Explorer** (single-pass; CHI 2026 prototype; H5′ watch item).

## M. Literature corrections

### M.1 — lit-005 (NLProofS) baseline attribution
**Finding answered:** committee Q9 (verified by sweep against arXiv:2205.12443).
**Before:** "...35.6% → 58.8% vs. T5-11B EntailmentWriter using only T5-large."
**After:** 20.9/35.6 attributed to EntailmentWriter **T5-large**; strongest baseline T5-11B at 25.6% named; released-checkpoint README 34.4% noted; SEER/NLDR/Task-1 successor figures EMBARGOED pending PDF verification (CLAIMS.md).

### M.2 — lit-020 (Costello et al.) EoC quoted, not characterized
**Finding answered:** committee Q10; new matrix rule "cells describing a source's status quote, never characterize."
**Before:** "Effect sizes materially weakened by the June 2026 Editorial Expression of Concern — treat as upper-bound estimates pending correction."
**After:** EoC quoted (reproducibility of specific values; screening-criteria inconsistencies); authors' corrected analyses reportedly match direction/significance/substantive size; under evaluation, no correction published as of 2026-08-13.

### M.3 — lit-020 replication-record note corrected
**Finding answered:** committee Q11.
**Before:** "...should not be cited without pairing with independent replications (Boissin..., 'Just the facts'...)."
**After:** replication record stated accurately: same-team (lit-021, lit-022) + independent-conceptual (Meyer, lit-032).

### M.4 — lit-024 authorship completed
**Before:** "Anonymous (2026)." **After:** Costello, Pelrine, Kowal, Timm, Arechar, Godbout, Gleave, Rand & Pennycook (recovered pass 4.5, §E).

## N. SYNTHESIS.md edits

- **N.1** H3 section: Pass 6/7 addendum — H3″ adopted, near-misses named, qualifier-withdrawal rationale.
- **N.2** H5 section: Pass 6/7 addendum — H5′ holds; research-line concession (lit-032, lit-034); watch item.
- **N.3** H4a paragraph: baseline attribution + embargo note.
- **N.4** §2 positioning: Pass 7 addendum — near-miss landscape named; conjunction-and-moat-first framing adopted; near-misses recast as demand evidence; impact/uptake split (VITALITY vs RetractoBot null) with conflation ban.
- **N.5** §3.4: arXiv:2509.18403 marked verified (was stale "verify_before_proposal=true").
- **N.6** §4 Problem: retraction count refreshed to 66,000+ (as-of-2026-08-13 citation; end-2024 figure retained parenthetically).
- **N.7** Verification-debts paragraph: discharged items marked; remaining debts restated (RedacTek single-secondary; marketing-claims; embargoed figures; reported-unpublished replications; single-pass pass-7 rows).

## O. New governance files

- **O.1** CLAIMS.md — banned-phrase lint (defense Q6 mechanism), scoped to application/ (red-team quotes preserved per I.3).
- **O.2** EVAL_PREREG.md — Q20 floors (grounding ≥50% depth-3 with the exact-key coherence rule; step-validity ≥80% with the 0.8⁵ display consequence; false-flag ≤5%), Q22 localization falsification line (<40% at κ≥0.6), standing eval rules (Q18/Q19/Q21).
- **O.3** SCHEMA_GAPS.md gap 8 — provenance tiers documented as gap (schema frozen); single-secondary/single-pass carried in extraction notes.
- **O.4** prompts/pass7_prompt.md — pass provenance record.

**Not done in this pass (deliberately):** application/ untouched (Tanner drafts application copy); CLAUDE.md untouched; D1 spec items (conflicted-state semantics, binarization intermediates, annotator roster) deferred to the build; RedacTek vendor-primary documentation still outstanding.
