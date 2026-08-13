# GATE_REPORT.md — Pass 2.5 Extraction Gate Check
**Date:** 2026-08-13  
**Inputs:** research/matrix/products.jsonl, research/matrix/literature.jsonl, research/matrix/EXTRACTION_NOTES.md, research/raw/report_a.md, research/raw/report_b.md, research/matrix/sources.jsonl

---

## Check 1 — Row count and roster (products.jsonl)

**PASS**

**Row count:** 24 lines, 24 valid JSON objects, 0 parse errors.

**Duplicate check:** No duplicates.

**All product values (alphabetical):**
- AVeriTeC
- ClaimBuster / Duke Squash + Tech & Check
- FActScore
- FEVER
- Factiverse
- Full Fact AI
- Ground News
- Kialo
- Logically / Logically Facts
- Loki / Libr-AI OpenFactVerification
- Meedan Check
- Originality.ai Fact-Check
- Penn Media Bias Detector (CSSLab / Duncan Watts)
- Perplexity
- PolitiFact
- RedacTek
- RetractionCheck / Crossref–Retraction Watch API
- RetractoBot
- SAFE (Search-Augmented Factuality Evaluator, Google DeepMind)
- SciFact
- Wolfram Alpha
- Zotero + Retraction Watch
- scite Reference Check
- scite.ai

**Roster reconciliation against report A:**

| Required system | Present? | Row ID |
|---|---|---|
| Ground News | ✓ | product-001 |
| scite.ai | ✓ | product-002 |
| PolitiFact | ✓ | product-003 |
| Penn Media Bias Detector | ✓ | product-004 |
| Factiverse | ✓ | product-005 |
| Perplexity | ✓ | product-006 |
| Originality.ai | ✓ | product-007 |
| Wolfram Alpha | ✓ | product-008 |
| Loki/OpenFactVerification | ✓ | product-009 |
| SAFE | ✓ | product-010 |
| FActScore | ✓ | product-011 |
| FEVER | ✓ | product-012 |
| SciFact | ✓ | product-013 |
| AVeriTeC | ✓ | product-014 |
| ClaimBuster/Squash | ✓ | product-015 |
| Full Fact | ✓ | product-016 |
| Meedan | ✓ | product-017 |
| Logically | ✓ | product-018 |
| Kialo | ✓ | product-019 |
| scite Reference Check | ✓ | product-020 |
| Zotero + Retraction Watch | ✓ | product-021 |
| RetractoBot | ✓ | product-022 |
| RetractionCheck / Crossref API | ✓ | product-023 |
| RedacTek | ✓ | product-024 |

All 24 required systems present. No missing rows, no duplicates.

---

## Check 2 — Adversary rows carry their qualifications

### Loki / Libr-AI OpenFactVerification (adversary to H1)

**FAIL → FIX APPLIED**

**Qualification (i): decomposes into independent atomic claims, NOT entailment-linked load-bearing premises**  
Present in extraction_note: *"decomposes into *independent atomic claims*, not entailment-linked load-bearing premises, and has no persistent structured KB."* ✓

**Qualification (ii): verdict-oriented / human-in-the-loop verdict**  
Before fix: Missing. The extraction_note said only "withholds final judgment for the user; automation_level 'hybrid' per human-in-the-loop design." The `verdict_behavior: transparency-only` enum was chosen, but this qualification existed only in the raw report (report A: *"Verdict: Human-in-the-loop verdict (semi-automated; withholds final judgment for the user)"*; H1 hypothesis section: *"(c) it produces verdicts/credibility"*). Per check rules, FAIL if qualification exists only in raw reports.

**Fix applied:** Appended to extraction_note (sourced from report A Loki bullet + H1 section): *"ADVERSARY QUALIFICATION (H1): per report A, Loki issues a 'human-in-the-loop verdict (semi-automated; withholds final judgment for the user)' — i.e., it does produce a verdict/credibility rating; verdict_behavior='transparency-only' captures the withholding-from-user aspect but understates that a verdict is ultimately produced."*

---

### RedacTek (adversary to H7)

**PASS**

**Required qualification:** paper-level 3-generation retraction-risk scoring, NOT claim-level invalidation.

Current extraction_note (verbatim): *"RedacTek is the closest deployed approximation to H7 (dependency-propagated invalidation), but operates at PAPER level across three citation generations (primary/secondary/tertiary), NOT claim-level invalidation. verdict_behavior: 'rates-sources-only' because the output is a paper-level 'issue association value' / 'retraction association value', not a claim verdict."*

Enum support: `unit_of_analysis: citation`, `claim_decomposition: none`, `verdict_behavior: rates-sources-only`. All three qualifications encoded. ✓

---

### scite.ai (adversary to H2/H6)

**PASS**

**Required qualification:** citation-statement-level operation with no argument/premise layer.

Enum support: `unit_of_analysis: citation` + `claim_decomposition: none` fully encode citation-statement-level operation with no argument/premise layer. Enums can express this qualification without additional extraction_note. Confirmed against report A H2: *"scite classifies citation statements as supporting/contrasting/mentioning and flags retractions, but builds no premise/argument graph over claims."* ✓

---

## Check 3 — Load-bearing literature rows

### DebunkBot / Costello et al. 2024 (lit-020)

**FAIL → FIX APPLIED** (finding_status)  
**PASS** (EoC date/venue, replications)

**finding_status field:** Before fix, field was absent from lit-020 JSON. Fix applied: added `"finding_status": "expression-of-concern"` after the `method_summary` field. Sourced from report B key findings: *"received a formal Editorial Expression of Concern from Science on June 11, 2026 over data-reproducibility and screening-criteria inconsistencies."*

**EoC date and venue:** method_summary already contained *"Subject to Science Editorial Expression of Concern (June 11, 2026)"* and paper field confirms venue = Science. ✓

**Replications present:**
- Boissin et al. PNAS Nexus 2025 → lit-022 ✓
- "Just the facts" mechanism preprint (OSF 2025) → lit-021 ✓  
Both also named explicitly in lit-020 `not_handled_relative_to_verity`: *"pair with independent replications (Boissin et al. PNAS Nexus 2025, 'Just the facts' OSF 2025)."* ✓

---

### EntailmentBank / Dalvi et al. 2021 (lit-001)

**FAIL → FIX APPLIED**

**Required:** metrics_and_best_numbers names all four dimensions: Leaves / Steps / Intermediates / Overall-AllCorrect.

Before fix: `"Task 2 Overall-AllCorrect ≈ 20.9% for EntailmentWriter (per NLProofS comparison table); Leaves-AllCorrect ≈ 35.6%."` — only two of four dimensions named. Steps-AllCorrect and Intermediates-AllCorrect missing from the field (they appeared in method_summary but the check requires them in metrics_and_best_numbers).

Fix applied (sourced from report B EntailmentBank section: *"Four dimensions after Jaccard-based node alignment — Leaves (F1, AllCorrect), Steps (F1, AllCorrect), Intermediates (F1, AllCorrect), Overall-AllCorrect (=1 only if all three are perfect). Task 2 Overall-AllCorrect ≈ 20.9% for EntailmentWriter (per NLProofS comparison table)."*):

`"Four EntailmentBank dimensions on Task 2 (per NLProofS comparison table): Overall-AllCorrect ≈ 20.9%, Leaves-AllCorrect ≈ 35.6% for EntailmentWriter baseline. Steps-AllCorrect and Intermediates-AllCorrect are tracked but specific baseline numbers for EntailmentWriter not reported in report B."`

All four dimensions now named. ✓

---

## Check 4 — Skipped-papers audit (EXTRACTION_NOTES.md)

**PASS**

**Required papers — none may be skipped:**

| Required paper | Present in literature.jsonl? | Row ID |
|---|---|---|
| NELLIE (Weir, Clark & Van Durme 2024) | ✓ | lit-009 |
| LAMBADA (Kazemi et al. 2023) | ✓ | lit-006 |
| NLProofS (Yang, Deng & Chen 2022) | ✓ | lit-005 |
| Wanner et al. 2024 (DecompScore) | ✓ | lit-013 |
| DnDScore (Wanner et al. 2025) | ✓ | lit-014 |
| Doyle 1979 (JTMS) | ✓ | lit-026 |
| de Kleer 1986 (ATMS) | ✓ | lit-027 |
| VeriScore (Song, Kim & Iyyer 2024) | ✓ | lit-012 |

All 8 required papers present.

**Acceptable skips from EXTRACTION_NOTES.md (verified as permissible per check rules):**
- Bago & Bonnefon Perspective (Science 2024) — no independent methodology/metrics ✓
- Hornsey, Bretter, Czarnek, Hou — no methodology/metrics/URLs in report B ✓
- Molecular Facts, CORE, WiCE — incorporated into lit-014 method_summary ✓
- Wikidata provenance model — no single foundational paper, no row-required fields ✓
- van der Vet & Nijveen — insufficient citation detail ✓
- "Persistence of Retracted Papers on Wikipedia" — in sources.jsonl with verify flag ✓
- Usman & Balke TPDL 2024 — report A (product landscape) not report B; in sources.jsonl ✓
- "A Logical Pattern Memory Pre-trained Model..." — listed in sources but not described in report B ✓
- arXiv:2606.17041 — described as search term, not full citation ✓
- Retraction Watch/Crossref acquisition paper, NLM/PubMed MeSH documentation — infrastructure, not papers ✓

No impermissible skips found.

---

## Check 5 — Sources file integrity (sources.jsonl)

**PASS**

**Row count:** 96 entries, all valid JSON, 0 parse errors.

**Duplicate URLs:** None.

**Provenance spot-check (10 random cells, random seed 42, full join impractical — 253 http URLs collected across both JSONL files):**

| Result | Row/field | URL (truncated) |
|---|---|---|
| OK | product-018/verdict_behavior | https://logically.ai/announcements |
| OK | product-003/automation_level | https://wral.com/how-we-determine-truth-o-meter-ratings |
| OK | product-001/interactivity | https://stationx.net/ground-news-review |
| OK | product-020/access_model | https://scite.ai/features |
| OK | product-008/unit_of_analysis | https://wolframalpha.com/tour |
| OK | product-007/evidence_quality_metadata | https://originality.ai/automated-fact-checker |
| OK | product-006/coverage_domain | https://perplexity.ai/help-center/en/articles/10352895 |
| OK | product-004/persistent_knowledge_reuse | https://penntoday.upenn.edu/news/conversation-duncan-watts |
| OK | product-020/automation_level | https://scite.ai/features |
| OK | product-003/interactivity | https://politifact.com/article/2018/feb/12/principles-truth-o-meter |

10/10 URLs found in sources.jsonl. ✓

---

## Fixes Applied

| # | File | Row | Field | Rationale | Source |
|---|---|---|---|---|---|
| 1 | products.jsonl | product-009 (Loki) | extraction_note | Adversary qualification (ii) — "human-in-the-loop verdict" — present in report A but not encoded in extraction_note | Report A Loki bullet: "Verdict: Human-in-the-loop verdict (semi-automated; withholds final judgment for the user)"; H1 hypothesis: "(c) it produces verdicts/credibility" |
| 2 | literature.jsonl | lit-020 (Costello 2024) | finding_status (new field) | Field required by check; was absent from JSON | Report B Key Findings: "received a formal Editorial Expression of Concern from Science on June 11, 2026" |
| 3 | literature.jsonl | lit-001 (EntailmentBank) | metrics_and_best_numbers | Only named Leaves and Overall; Steps and Intermediates missing; check requires all four dimensions named | Report B EntailmentBank section: "Four dimensions after Jaccard-based node alignment — Leaves (F1, AllCorrect), Steps (F1, AllCorrect), Intermediates (F1, AllCorrect), Overall-AllCorrect" |

---

## VERDICT: CLEAR FOR PASS 3
