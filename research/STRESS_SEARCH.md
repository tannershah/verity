# STRESS_SEARCH.md — Pass 4.5

**Date:** 2026-08-13
**Purpose:** Negative-hypothesis targeted existence searches (§C), RedacTek row verification (§D), and targeted source burndown (§E).
**Rule:** ESCALATE items are decided by Tanner. No verdict changes made here.

---

## C. Negative-hypothesis stress searches

### H1 — "No consumer product auto-decomposes claims into entailment-linked load-bearing premises with per-premise evidence."

**Query used:** `consumer fact-checking tool entailment premise decomposition evidence 2025 2026`
**Date:** 2026-08-13

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | PrimeFacts (arxiv 2605.06006) | arxiv.org/abs/2605.06006 | NOT-A-COUNTEREXAMPLE | Academic resource/pipeline for building premise-level evidence resources from PolitiFact articles; not a deployed consumer product. |
| 2 | SIFT (arxiv 2502.10855) | arxiv.org/pdf/2502.10855 | NOT-A-COUNTEREXAMPLE | Research prototype decomposing claims into 5W1H spans via NLI; no consumer deployment documented. |
| 3 | HallDetect | — | NOT-A-COUNTEREXAMPLE | Hallucination detection tool for LLM pipelines, not a consumer claim-checking product. |
| 4 | DyDecomp / DAD (Lu et al. 2025 / Magomere et al. 2026) | — | NOT-A-COUNTEREXAMPLE | RL-based decomposition optimization; academic research, no product deployment. |
| 5 | FEVER9 shared task (fever.ai) | fever.ai | NOT-A-COUNTEREXAMPLE | Academic benchmark for EACL 2026; not a consumer product. |

**Verdict: No counterexample found.** Targeted existence search performed 2026-08-13; no counterexample found.

---

### H2 — "scite has no argument-structure layer above citations."

**Query used:** `scite.ai argument structure claim decomposition premise 2025 2026`
**Date:** 2026-08-13

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | scite Smart Citations (2025–26 reviews) | buildfastwithai.com, effortlessacademic.com, fahimai.com | NOT-A-COUNTEREXAMPLE | Confirms citation-level classification (Supporting/Contrasting/Mentioning) only; no argument-structure or premise decomposition found in any 2025–2026 source. |
| 2 | scite Assistant | techpoint.africa | NOT-A-COUNTEREXAMPLE | Chat wrapper over citation data; no structural decomposition described. |

**Verdict: No counterexample found.** Targeted existence search performed 2026-08-13; no counterexample found.

---

### H4b — "No gold standard exists for decomposition faithfulness."

**Query used:** `claim decomposition faithfulness benchmark gold standard evaluation 2025 2026`
**Date:** 2026-08-13

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | FAITHCOT-BENCH (ICLR 2026, arXiv 2510.04040) | arxiv.org/pdf/2510.04040 | NOT-A-COUNTEREXAMPLE | Benchmarks CoT faithfulness, not claim-to-premise entailment decomposition faithfulness; different target. |
| 2 | DecMetrics (Huang 2025) | — | NOT-A-COUNTEREXAMPLE | NLI-based metric proposal (completeness, correctness, semantic entropy); not a gold-standard human-annotated decomposition faithfulness corpus. |
| 3 | DnDScore (arXiv 2412.13175) | arxiv.org/pdf/2412.13175 | NOT-A-COUNTEREXAMPLE | Factuality benchmark for atomic claims; not a decomposition-faithfulness (entailment-preservation) benchmark. |
| 4 | Zhang et al. 2025, "A Claim Decomposition Benchmark for Long-Form Answer Verification" (SpringerLink) | SpringerLink | **ESCALATE** | Title directly implies a benchmark for evaluating claim decomposition; need to determine whether it tests entailment-preservation of decompositions (faithfulness) or only downstream verification accuracy. Tanner decides. |

**H4b: ONE ESCALATE (Zhang et al. 2025).** No verdict change. Tanner to read Zhang et al. 2025 (SpringerLink) and determine whether it constitutes a gold standard for decomposition faithfulness (entailment-preservation). If confirmed, H4b weakens but does not necessarily die — the question is whether entailment-preservation is the measured property or only downstream verdict accuracy.

---

### H4c — "No evaluation exists for contested real-world claim decomposition into premise structures."

**Query used:** `contested claim decomposition entailment benchmark evaluation 2025 2026`
**Date:** 2026-08-13

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | "Does Claim Decomposition Boost or Burden Fact-Checking?" (NAACL 2025, openreview.net) | openreview.net | NOT-A-COUNTEREXAMPLE | Evaluates decomposition utility for verdict accuracy on real claims; not a benchmark for contested-claim premise structures specifically. |
| 2 | CREDENCE (arXiv 2606.19819) | arxiv.org/html/2606.19819 | NOT-A-COUNTEREXAMPLE | Semantic convergence metrics for decomposition; no indication it focuses on contested claims specifically. |
| 3 | "A Closer Look at Claim Decomposition" (ACL Anthology 2024) | aclanthology.org | NOT-A-COUNTEREXAMPLE | General decomposition analysis on fact-checking datasets; not a contested-claim-specific benchmark. |
| 4 | Warrant Gap / SIFT (arXiv 2606.24627) | arxiv.org/html/2606.24627 | NOT-A-COUNTEREXAMPLE | Warrant retrieval/scoring for fact-checking; not a contested premise structure benchmark. |

**Verdict: No counterexample found.** Targeted existence search performed 2026-08-13; no counterexample found.

---

### H6 — "No system combines argument-structure decomposition with evidence-quality metadata."

**Query used:** `fact checking argument decomposition study design metadata evidence quality system 2025 2026`
**Date:** 2026-08-13

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | "When automated fact-checking meets argumentation" (Cabrio et al., SAGE 2025) | SAGE | NOT-A-COUNTEREXAMPLE | Uses argument structure for verdict classification; no evidence-quality metadata (study design, retraction status, sample N) layer. |
| 2 | ProgramFC / SAFE variants | — | NOT-A-COUNTEREXAMPLE | Sub-question decomposition and evidence retrieval; no structured evidence-quality metadata (study design, retraction, N). |
| 3 | Speaker/KG metadata approaches | — | NOT-A-COUNTEREXAMPLE | Contextual metadata (claimant provenance), not evidence-quality metadata of supporting studies. |

**Verdict: No counterexample found.** Targeted existence search performed 2026-08-13; no counterexample found.

---

### H7 — "No product does claim-level dependency-propagated invalidation from retracted sources."

**Query used:** `retraction claim dependency propagation invalidation fact checking system 2025 2026`
**Date:** 2026-08-13

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | RedacTek | dcdm.doody.com (see §D) | NOT-A-COUNTEREXAMPLE | Paper-level retraction propagation across three citation generations, NOT claim-level logical dependency invalidation. Confirmed in §D. |
| 2 | ConvMemory v3 (arXiv 2606.26753) | arxiv.org/pdf/2606.26753 | NOT-A-COUNTEREXAMPLE | Validity propagation over dependency graphs for conversational memory; targets conversational memory, not scientific claim-retraction. |
| 3 | Cochrane/CENTRAL retraction flagging (Retraction Watch, 2026) | — | NOT-A-COUNTEREXAMPLE | Flags retracted papers in systematic reviews at paper level; no claim-level dependency graph. |
| 4 | Plato's Cave (arXiv 2603.23526) | arxiv.org/pdf/2603.23526 | NOT-A-COUNTEREXAMPLE | Human-centered research verification system; no evidence of claim-level dependency propagation in search results. |

**Verdict: No counterexample found.** Targeted existence search performed 2026-08-13; no counterexample found.

---

## D. RedacTek Row Verification (product-024)

**Source 1 fetched:** `https://dcdm.doody.com/2025/10/a-review-of-redactek` — YES
**Source 2 fetched:** `https://www.nature.com/nature-index/news/new-bot-flags-scientific-research-studies-that-cite-retracted-papers` — YES

### Source 1: Doody's CDMR review (Oct 2025)

Cell-by-cell results:

| Schema cell | Proposed value | Result | Action |
|---|---|---|---|
| unit_of_analysis | citation | PARTIAL | Paper/article level propagated via citation generations; "citation" defensible but "paper" more precise. Note in STRESS_SEARCH; confidence stays inferred. |
| claim_decomposition | none | CONFIRMED | "validates sources holistically rather than decomposing arguments into constituent claims" | Confidence upgraded to **verified** in products.jsonl. |
| evidence_quality_metadata | study-level | PARTIAL | Tracks retraction status + PubPeer flags + self-citation rate; does NOT include study design (RCT vs. observational) or sample N. "study-level" overstates the metadata richness. ESCALATE. |
| verdict_behavior | rates-sources-only | CONFIRMED | Issues paper-level "issue association value" risk scores, not claim verdicts. | Confidence upgraded to **verified** in products.jsonl. |
| persistent_knowledge_reuse | structured-KB-with-provenance | CONFIRMED | Draws from Retraction Watch, PubPeer, OpenAlex, Crossref with source attribution. | Confidence upgraded to **verified** in products.jsonl. |
| automation_level | fully-automated | CONFIRMED | Chrome extension, algorithmic scoring. | Confidence upgraded to **verified** in products.jsonl. Source URL corrected from Nature Index to Doody's review. |
| access_model | institutional | **ESCALATE** | Doody's review states $3/month or $30/year individual subscription as the primary model; institutional IP authentication also available. Current cell value ("institutional") is incorrect — primary access is individual subscription. Tanner decides whether to change cell value. |

**Key architectural question answered:** RedacTek operates at paper level (propagating paper-level retraction/issue scores across three citation generations: primary, secondary, tertiary) but NOT at claim level (no logical dependency invalidation, no premise-level tracking). This confirms the load-bearing distinction for H7.

### Source 2: Nature Index article

**ESCALATE — Attribution error:** The fetched Nature Index article (`nature.com/nature-index/news/new-bot-flags-scientific-research-studies-that-cite-retracted-papers`) describes **scite Reference Check** (product-020), not RedacTek (product-024). It is currently listed as the provenance source for product-024's `automation_level` cell. The article describes a primary-citation-only flagging system (no three-generation propagation), which contradicts RedacTek's three-generation scope. Tanner decides whether to remove this URL from product-024's provenance or retain it with a corrective note. (Source correctly stays as product-020 provenance.)

---

## E. Targeted Source Burndown

Scope: flagged sources supporting claims in the proposal skeleton or the two red-team pre-emptions only. Deferred sources at bottom.

### lit-021 — `https://doi.org/10.31234/osf.io/h7n8u`
**Claim supported:** §4 motivation — mechanism is facts/evidence not framing; Costello, Pennycook & Rand.
**Fetched:** No (OSF DOI redirect returned no extractable content).
**Via web search:** Title confirmed as "Just the facts: How dialogues with AI reduce conspiracy beliefs" by Costello, Pennycook & Rand. Authorship and topic confirmed. Specific framing-vs-evidence mechanism argument not directly verified from page text.
**Action:** PARTIAL CONFIRM. `verify_before_proposal` remains `true`. Recommend using the published *Science* paper (lit-020, doi:10.1126/science.adq1814) as primary citation and citing this OSF preprint only for the mechanism-specificity argument; the preprint's main point (facts-not-framing) is consistent with the broader line but needs direct read.

### lit-023 — `https://arxiv.org/abs/2510.01537`
**Claim supported:** §4 "Verity's human endpoint is discernment, not persuasion (lit-023)" and §3.4 roadmap.
**Fetched:** YES.
**Confirmed:** YES. Title: "Dialogues with AI Reduce Beliefs in Misinformation but Build No Lasting Discernment Skills." Authors: Rani, Danry, Liang, Lippman, Maes. N=67; immediate +21% gain but independent performance declined 15.3% by week 4. Belief shifts do not transfer to lasting discernment skills.
**Action:** `verify_before_proposal` → `false`. `verified_note`: "Confirmed 2026-08-13: N=67; immediate belief shift does not transfer to lasting discernment skills. Directly supports Verity's discernment-not-persuasion endpoint."

### lit-024 — `https://arxiv.org/abs/2601.05050`
**Claim supported:** Added to §4 via B.4 — dual-use persuasion result supports no-verdict design rationale.
**Fetched:** YES.
**Confirmed:** YES. Title: "Large language models can effectively convince people to believe conspiracies." Authors: Costello, Pelrine, Kowal, Timm, Arechar, Godbout, Gleave, Rand, Pennycook. LLMs substantially increased AND decreased conspiracy belief depending on instructions; conspiracy-promoting LLMs rated as equally or more credible than debunking versions. Full dual-use confirmation.
**Action:** `verify_before_proposal` → `false`. `verified_note`: "Confirmed 2026-08-13: same LLM persuasion architecture increases conspiracy beliefs when directed at amplification. Directly supports no-verdict design rationale."

### `https://arxiv.org/abs/2509.18403` — retracted-papers-on-Wikipedia persistence study
**Claim supported:** §3.4 "retracted-papers-on-Wikipedia persistence study (arXiv:2509.18403)."
**Fetched:** YES.
**Confirmed:** YES. Title: "The Persistence of Retracted Papers on Wikipedia." Authors: Shi, Yu, Romero, Horvát. 71.6% of retracted-paper citations initially problematic; median persistence 3.68 years; higher citation counts slow correction; bot flagging and open access accelerate correction.
**Action:** `verify_before_proposal` → `false`. `verified_note`: "Confirmed 2026-08-13: 71.6% of retracted Wikipedia citations problematic; median persistence 3.68 years. Directly supports §3.4 invalidation-motivation argument."

### lit-027 (ATMS) — `https://www.academia.edu/16674638/An_assumption_based_TMS`
**Claim supported:** §3.4 and pre-emption 1c — ATMS as the model for multiple simultaneous evidential contexts.
**Fetched:** No (HTTP 403 Forbidden — authentication wall).
**Assessment:** Cannot verify URL accessibility. De Kleer 1986 ATMS existence is not in scholarly doubt. URL may be permanently inaccessible to unauthenticated users.
**Action:** ESCALATE. Recommend replacing this source URL with the journal DOI `10.1016/0004-3702(86)90080-9` (Artificial Intelligence, 28(2):127–262). `verify_before_proposal` remains `true`.

### `https://dcdm.doody.com/2025/10/a-review-of-redactek` — product-024 primary source
**Claim supported:** H7 load-bearing distinction (paper-level vs. claim-level) cited throughout §2 and §4.
**Fetched:** YES (see §D above).
**Confirmed:** YES (with two partials and one escalate noted in §D).
**Action:** `verify_before_proposal` → `false`. `verified_note`: "Confirmed 2026-08-13 via Doody's CDMR review: paper-level three-generation propagation confirmed; no claim-level invalidation; individual subscription model (see ESCALATE on access_model)."

---

---

## F. Pass 6 — H3'/H5' existence battery (committee-run)

**Date:** 2026-08-13
**Note:** This battery was run by a committee subagent because the orchestrating agent is unavailable, per Tanner's instruction. Recall was prioritized over economy: ~14 searches conducted plus targeted site fetches. Verdict and copy changes are the committee chair's to adjudicate.

---

### H3' — "No checker offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim."

**Queries (verbatim):**
1. `symmetric claim transparency decomposed premise level inspection tool 2025 2026`
2. `argument map evidence both sides claim breakdown AI app 2025 2026`
3. `see both sides claim app "break down" evidence premises AI 2025`
4. `AI debate map "both sides" argument breakdown evidence sources app Product Hunt 2025`
5. `"argument mapping" OR "deliberation" tool AI automated evidence quality claim decompose symmetric deployed product 2025`
6. `deliberation technology tool argument decomposition evidence quality both sides public 2025 2026`

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | Consensus (consensus.app) | consensus.app | NOT-A-COUNTEREXAMPLE | Renders a yes/no/possibly/mixed stance distribution over papers for an atomically treated question; no decomposition of the input claim into load-bearing premises. Operates at the atomic-claim level only, not the decomposed-premise level. |
| 2 | The Society Library | societylibrary.org | NEAR-MISS-FORCES-QUALIFIER | Multi-level argument maps linking claims, evidence, and 20+ logical relationships across contested topics — structurally the closest match to decomposed symmetric inspection. However: (a) maps are human-curated (not automated over a user-submitted composite claim); (b) deployment is partial — many topics listed as "Started" or "Not Yet Started" requiring funding. Forces qualifier "automated" into H3' if hypothesis is to survive. Survives with: "No automated system offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim." |
| 3 | Kialo | kialo.com | NEAR-MISS-FORCES-QUALIFIER | Fully deployed public product (32,886 debates, 798,051 claims). Organizes discussion as an interactive tree of pro and con arguments, branching hierarchically from a thesis. Users can attach links/source citations to claims. No evidence quality metadata (study design, retraction status, sample N). No AI automation — entirely user/community-driven. Renders sides symmetrically without verdict. Forces qualifier "automated" and/or "evidence-quality-metadata-attached" into H3' alongside Society Library. |
| 4 | ARGUMEND | argumend.org | NEAR-MISS-FORCES-QUALIFIER | Publicly accessible product covering 140+ topics with AI-synthesized weighted evidence, confidence levels, and "both sides" presentation. Attaches study citations to specific argument nodes (e.g., named 2025 studies). However: (a) operates over pre-selected topic positions, not over a user-submitted composite claim decomposed on-the-fly; (b) evidence quality metadata (study design, retraction, sample N) is absent — citations are narrative-cited without structured metadata. Forces qualifier "user-submitted composite claim" to clarify that H3' targets on-demand decomposition of arbitrary input claims. |
| 5 | Symbai | symbai.ai | NOT-A-COUNTEREXAMPLE | Deployed debate-training product; maps reasoning into claims, evidence, objections and assumptions. AI argues a selected position against the user (adversarial), not symmetric neutral inspection. Verdict-adjacent (practice debate tool). |
| 6 | TruthSplit | arxiv.org/abs/2606.09251 | NOT-A-COUNTEREXAMPLE | arxiv preprint (June 2026): research system extracting claims/premises and assessing conditional validity through worldview-specific NLI. Not a deployed product. |

**H3' Verdict:** No counterexample found. Three NEAR-MISS-FORCES-QUALIFIER candidates collectively force two qualifiers into the hypothesis for it to survive: (1) "automated" — Society Library and Kialo do decomposed symmetric inspection but only via human curation; (2) "of a user-submitted composite claim" — ARGUMEND does AI-automated symmetric inspection with evidence but only over its own pre-selected topic positions, not arbitrary user-submitted claims decomposed on-the-fly. Revised H3' (committee recommendation): "No automated system offers symmetric transparency-only inspection at the decomposed-premise level of a user-submitted composite claim." Tanner to adjudicate qualifier wording.

---

### H5' — "The belief-updating line is productized only as persuasion — verdict-shaped counterarguments — not as self-serve symmetric inspection."

**Queries (verbatim):**
1. `belief updating self-serve inspection symmetric AI product 2026`
2. `street epistemology chatbot AI app productized 2025 2026`
3. `AI help examine your beliefs Socratic questioning app critical thinking 2025 2026`
4. `reflective thinking coach AI belief examination app product 2025 2026`
5. `Socratic AI app "examine your beliefs" misinformation reflection product launch 2024 2025`
6. `"open mind" OR "mindset" OR "epistemics" AI app belief examination self-serve product 2024 2025 productized`
7. `productized Socratic questioning conspiracy belief reflection app iOS Android 2024 2025`

| # | Candidate | URL | Judgment | Reason |
|---|---|---|---|---|
| 1 | debunkbot.com | debunkbot.com | NOT-A-COUNTEREXAMPLE | Confirms the hypothesis's "persuasion" pole: fine-tuned to issue "calm, cool, collected" counterarguments against the user's conspiracy belief; rated as more credible than debunking alternatives; achieved 20% belief reduction. Explicitly verdict-shaped. The pivot's origin point. |
| 2 | Meyer et al. 2024 "street epistemologist" chatbot | misinforeview.hks.harvard.edu/article/using-an-ai-powered-street-epistemologist-chatbot-and-reflection-tasks-to-diminish-conspiracy-theory-beliefs/ | NOT-A-COUNTEREXAMPLE | Research study (HKS Misinformation Review, DOI 10.37016/mr-2020-164), N=2000+. Chatbot prompts reflection on uncertainty underlying beliefs; not a deployed self-serve product. Constrains H5' phrasing: any productized version of this paradigm (reflection, not counterargument) would be a counterexample. |
| 3 | Belief Explorer (CHI 2026) | dl.acm.org/doi/10.1145/3772363.3799391 | NOT-A-COUNTEREXAMPLE | Research prototype evaluated in CHI 2026 Extended Abstracts. Three-component AI system: Socratic Dialogue Interface, multi-perspective analysis, analytical feedback. Recruited via Prolific; not a deployed public product. Closest in design to the H5' counterexample pattern — symmetric, reflection-oriented, non-verdict. If productized, would be a counterexample. |
| 4 | Reflection.app | reflection.app | NOT-A-COUNTEREXAMPLE | Deployed AI journaling and coaching app (iOS/Android/macOS/Web, updated June 2026). AI coach prompts self-reflection via journal entries. General emotional/goal reflection; not designed to examine a specific claim or belief against evidence symmetrically. Fails "symmetric inspection" and "belief-against-evidence" terms. |
| 5 | Socra (hisocra.com) | hisocra.com | NOT-A-COUNTEREXAMPLE | Deployed AI learning platform using Socratic questioning and Feynman method. Purpose is tutoring/knowledge acquisition, not symmetric inspection of a user's held belief against evidence. Fails the "belief-updating" and "symmetric inspection" terms. |
| 6 | Socratic AI Against Disinformation (TITAN prototype) | dl.acm.org/doi/10.1145/3639701.3663640 | NOT-A-COUNTEREXAMPLE | Research prototype (ACM IMX 2024). Socratic dialogue to increase users' awareness of reasoning processes and detect misinformation. Not a deployed product. |

**H5' Verdict:** No counterexample found. The hypothesis holds as stated. The belief-updating product space remains cleanly bifurcated: persuasion products (DebunkBot) dominate; the symmetric Socratic-reflection paradigm (Meyer et al. 2024, Belief Explorer CHI 2026) exists only as research prototypes. No productized self-serve symmetric inspection tool in the belief-updating line was found as of 2026-08-13. Note: Belief Explorer (CHI 2026 Extended Abstracts) is the highest-risk future threat — it is the closest design match and may be commercialized. Recommend monitoring.

---

## Deferred — not cited by proposal

The following `verify_before_proposal: true` sources do not support claims in the proposal skeleton or the two red-team pre-emptions. Deferred to post-submission or pre-proposal-revision pass:

- `https://libguides.depauw.edu` (product-001 — Ground News libguide)
- `https://stationx.net/ground-news-review` (product-001 — Ground News review)
- `https://belmont.libguides.com` (product-002 — scite libguide)
- `https://guides.erau.edu/scite-ai` (product-002 — scite guide)
- `https://visionsparksolutions.com` (product-002 — scite pricing)
- `https://theresanaiforthat.com/ai/factiverse` (product-005 — Factiverse pricing)
- `https://llmpulse.ai/blog/how-perplexity-works` (product-006 — Perplexity)
- `https://wpseoai.com` (product-006 — Perplexity)
- `https://clickrank.ai/perplexity-ai` (product-006 — Perplexity)
- `https://futureaimind.com` (product-008 — Wolfram pricing)
- `https://aclanthology.org/2020.emnlp-main.609` (product-013/lit-016 — SciFact/FEVER URL label ambiguity; SciFact is correctly EMNLP 2020 for lit-016 but label confusion with FEVER in sources_a.md)
- `https://poynter.org/fact-checking/2022` (product-016 — Full Fact)
- `https://logically.ai/announcements` (product-018 — marketing-claim)
- `https://forbes.com/sites/bernardmarr/2021/01/25` (product-018 — Logically)
- `https://library.smu.edu.sg` (product-021 — Zotero/Retraction Watch)
- `https://hellofuture.orange.com` (product-005 — Factiverse)
- `http://rtw.ml.cmu.edu/papers/carlson-aaai10.pdf` (lit-025 — NELL AAAI paper; CACM version is verified via dl.acm.org)
