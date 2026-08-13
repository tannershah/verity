# SYNTHESIS.md — Pass 3: Hypothesis Verdicts, Positioning, Evaluation Plan, Proposal Skeleton

**Date:** 2026-08-13
**Inputs:** `research/matrix/{products,literature,sources}.jsonl`, `EXTRACTION_NOTES.md`, `GATE_REPORT.md` (verdict: clear for Pass 3), `research/matrix/schema.json` (frozen; H1–H7), `research/raw/report_a.md`, `research/raw/report_b.md`.
**Scope:** Red-teaming is a separate, independent pass and is deliberately absent here.

---

## 1. Hypothesis adjudication

Verdicts follow `hypothesis_verdict_format`. Surviving negative claims are phrased "none found as of Aug 2026" — a search bound over two deep-research sweeps (24 product rows, 28 literature rows), not a proof of nonexistence.

### H1 — No consumer product auto-decomposes claims into premises with per-premise evidence

```json
{
  "hypothesis_id": "H1",
  "verdict": "survives",
  "strongest_counterexample": "Loki / Libr-AI OpenFactVerification (product-009): automatic decomposition with per-claim evidence display in a UI — but into independent atomic claims, not entailment-linked load-bearing premises; journalist/researcher-facing, not consumer; and ultimately verdict-producing (human-in-the-loop verdict).",
  "required_pivot_if_dead": null,
  "phrasing_note": "None found as of Aug 2026 combining consumer packaging + entailment-linked premise decomposition + per-premise evidence."
}
```

Verified against the matrix: the only rows with `claim_decomposition: automatic` are Loki (product-009), SAFE (product-010), and FActScore (product-011) — all researcher-facing tools or evaluators, all decomposing into independent atomic facts, none consumer products (report A, H1; schema gap 5 records that the consumer/professional boundary is a judgment call, per report A's own caveat). Every consumer-facing row has `claim_decomposition: none` — Ground News (product-001), PolitiFact (product-003), Factiverse (product-005), Perplexity (product-006), Originality.ai (product-007) — with Factiverse and Originality.ai doing claim *detection*, not decomposition (schema gap 6); Kialo (product-019) reaches the argument-graph level but is fully `manual`. Report A's qualified-survive verdict is confirmed, with one tension carried forward: product-009's `verdict_behavior: transparency-only` enum understates that Loki ultimately produces a verdict (gate-checked adversary qualification in the row's extraction_note), which makes Loki a weaker counterexample on the no-verdict axis than the enum alone suggests.

### H2 — scite has no argument-structure layer above citations

```json
{
  "hypothesis_id": "H2",
  "verdict": "survives",
  "strongest_counterexample": null,
  "required_pivot_if_dead": null,
  "phrasing_note": "None found as of Aug 2026: scite's own feature documentation describes citation-level operation only."
}
```

scite.ai (product-002) and scite Reference Check (product-020) both carry `unit_of_analysis: citation` and `claim_decomposition: none`, verified against scite's primary feature pages. The full product surface — Smart Citation classification (supporting/contrasting/mentioning), Reports, Reference Check, Collections, Assistant, MCP integration — contains no premise or argument graph above the citation statement (report A, H2). Confirmed with no counterexample.

### H3 — No checker offers symmetric transparency-only inspection as core product

```json
{
  "hypothesis_id": "H3",
  "verdict": "dies",
  "strongest_counterexample": "Ground News (product-001): the core product IS symmetric left/center/right coverage comparison with explicit no-adjudication positioning, at the article/source level. Penn Media Bias Detector (product-004) and scite (product-002) are further counterexamples at article and citation level.",
  "required_pivot_if_dead": "H3' = 'No checker offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim' — none found as of Aug 2026. ADOPTED.",
  "phrasing_note": "H3 as stated is dead; all downstream copy must use H3'."
}
```

The matrix kills H3 as stated: Ground News (product-001) is `verdict_behavior: transparency-only` + `symmetric_contrasting_evidence: yes` as its core product ("we keep our team's subjective opinions out of the product"), Penn MBD (product-004) is transparency-only by design ("our goal is not to adjudicate what is true"), and scite (product-002) shows symmetric supporting/contrasting citations while rating sources only. I agree with report A's "FAILS (partially)" and record it as a clean death at the stated formulation. The pivot H3' survives by enumeration: every transparency-only row sits at article, source, or citation level; the decomposed-premise-level candidates all fail it — SAFE and FActScore issue verdicts (product-010, -011), Loki is atomic-not-entailment and ultimately verdict-producing (product-009), Kialo is premise-structured and no-verdict but fully manual with no evidence layer (product-019). H3' is adopted for all downstream positioning.

### H4 — No standard benchmark for claim-to-premise decomposition quality

One verdict cannot represent H4 honestly; the evidence splits three ways (report B, Buckets 1–3). Flagged as a schema-format mismatch rather than forcing a single value; all three facets must appear in the proposal.

```json
[
  {
    "hypothesis_id": "H4a — entailment-STEP validity",
    "verdict": "dies",
    "strongest_counterexample": "EntailmentBank (lit-001): an established four-metric benchmark — Leaves (F1, AllCorrect), Steps (F1, AllCorrect), Intermediates (F1, AllCorrect), Overall-AllCorrect — with an active method line: METGEN (lit-002), IRGR (lit-003), RLET (lit-004), NLProofS (lit-005).",
    "required_pivot_if_dead": "Never claim step-validity benchmarks are missing; adopt EntailmentBank metrics directly.",
    "phrasing_note": "A standard benchmark exists for entailment-step validity."
  },
  {
    "hypothesis_id": "H4b — decomposition FAITHFULNESS",
    "verdict": "survives",
    "strongest_counterexample": null,
    "required_pivot_if_dead": null,
    "phrasing_note": "None found as of Aug 2026: no gold standard exists; measurement is proxy-only (DecompScore, entailment coverage, verifier-confidence deltas)."
  },
  {
    "hypothesis_id": "H4c — decomposition of CONTESTED real-world claims",
    "verdict": "survives",
    "strongest_counterexample": null,
    "required_pivot_if_dead": null,
    "phrasing_note": "None found as of Aug 2026: no evaluation exists at all; nearest neighbor (AVeriTeC Conflicting/Cherry-picking) is a verdict class, not a decomposition eval."
  }
]
```

H4a: EntailmentBank's four dimensions are the standard, and the method line is mature — NLProofS (lit-005) raised Task 2 Overall-AllCorrect 20.9% → 33.3% and Leaves-AllCorrect 35.6% → 58.8% with a verifier-guided search. H4b: Wanner et al. (lit-013) showed FActScore is sensitive to the decomposition method itself and introduced DecompScore precisely because no gold standard exists; DnDScore (lit-014) confirms factuality scores are unstable across decomposition/decontextualization strategies. H4c: no benchmark decomposes contested claims into premise structures — AVeriTeC's Conflicting/Cherry-picking label (lit-017) is the closest analog and is itself the field's worst-performing class (near-zero F1 for most systems, <7% of training data).

### H5 — DebunkBot line not productized as self-serve tool

```json
{
  "hypothesis_id": "H5",
  "verdict": "dies",
  "strongest_counterexample": "debunkbot.com: a publicly deployed, self-serve consumer product by the DebunkBot authors, confirmed live Aug 13 2026. Also publicly demonstrated at MIT Museum. Authors announced the deployment in MIT Technology Review, Oct 2025.",
  "required_pivot_if_dead": "H5' = 'The belief-updating line is productized only as persuasion — verdict-shaped counterarguments — not as self-serve symmetric inspection; none found as of Aug 2026.' ADOPTED.",
  "phrasing_note": "H5 as stated is dead. All downstream copy must use H5'. Detection note: H5 was originally marked 'survives (moderate confidence)' because neither deep-research run queried for consumer deployments; a targeted post-synthesis search found debunkbot.com."
}
```

H5 dies: debunkbot.com is a live, self-serve consumer deployment of the DebunkBot line, confirmed via the authors' MIT Technology Review piece (Oct 2025) and the site itself (accessed Aug 13 2026). A public MIT Museum demo corroborates deployment. The original pass 3 adjudication assigned moderate confidence precisely because neither deep-research run included a targeted consumer-deployment query; the correction came from a post-synthesis search.

Pivot H5′ survives: the belief-updating line's product form is persuasion — a verdict-shaped AI that argues back against the user's stated belief. debunkbot.com delivers counterarguments, not symmetric evidence inspection. No product found as of Aug 2026 that deploys the belief-updating paradigm as a transparency-only, no-verdict, symmetric evidence map (the posture Verity takes). The roadmap note in §3.4 stands: adapt belief-updating to measure discernment/calibration rather than persuasion, since Verity deliberately does not persuade (lit-023).

### H6 — No system combines argument-structure decomposition with evidence-quality metadata

```json
{
  "hypothesis_id": "H6",
  "verdict": "survives",
  "strongest_counterexample": null,
  "required_pivot_if_dead": null,
  "phrasing_note": "None found as of Aug 2026. Nearest miss: Loki (product-009) — automatic but atomic (not argument-structure) decomposition with source-level (not study-level) metadata; one level short on both axes."
}
```

Report A's claim that the decomposition × study-level-metadata intersection is empty is CONFIRMED by enumeration over all 24 rows. Rows with any decomposition: Loki, SAFE, FActScore (`automatic` — all atomic-fact decomposers at `source-level` metadata or below) and Kialo (`manual` argument graphs, `evidence_quality_metadata: none`). Rows with `study-level` metadata: scite.ai, scite Reference Check, Zotero+Retraction Watch, RetractoBot, RetractionCheck, RedacTek (product-002, -020 through -024) — every one has `claim_decomposition: none`. The literature side matches: all entailment-tree systems (lit-001 through lit-009) assume leaves true with no evidence-quality metadata (per each row's not_handled field). The intersection is empty on both the product and research sides.

### H7 — No product does dependency-propagated invalidation

```json
{
  "hypothesis_id": "H7",
  "verdict": "survives",
  "strongest_counterexample": "RedacTek (product-024): genuine multi-hop propagation — a paper-level 'retraction/issue association value' computed across three citation generations (primary/secondary/tertiary) — but of paper-level suspicion scores, NOT claim-level invalidation of downstream conclusions.",
  "required_pivot_if_dead": null,
  "phrasing_note": "None found as of Aug 2026 performing claim-level dependency-propagated invalidation."
}
```

Verified: every shipping retraction tool in the matrix is direct-status or 1-hop — scite Reference Check ("direct-status only", product-020), Zotero+Retraction Watch ("one hop, no propagation", product-021), RetractoBot ("1-hop emails", product-022), RetractionCheck/Crossref API ("federated lookup only", product-023). RedacTek (product-024) is the strongest counterexample and the paper-level→claim-level gap is the load-bearing distinction; note its row is all-inferred from a third-party review and is a high-priority verify-before-proposal item (EXTRACTION_NOTES). The only paradigm that does true dependency-directed retraction — truth maintenance systems (JTMS lit-026, ATMS lit-027) — has never been applied to scholarly retractions (report B, Area 6b). Report A's qualified-survive verdict is confirmed.

---

## 2. Positioning statement

Verity's defensible position is a conjunction, not any single feature. Automatic claim decomposition ships today (Loki, product-009; SAFE, product-010) — but into independent atomic facts, verdict-oriented, with no persistent KB. Transparency-only presentation ships today (Ground News, product-001; Penn Media Bias Detector, product-004) — but at the article/source level, never below it. Study-level evidence metadata ships today (scite, product-002: supporting/contrasting citations, retraction and editorial-concern flags) — but per citation statement, with no argument layer above it (H2). Persistent fact stores ship today (Wolfram Alpha's curated Knowledgebase, product-008; the ClaimReview fact-check cache behind Squash, product-015; AVeriTeC's knowledge store, product-014) — but none is dependency-tracked, and no shipping product propagates a retraction to the claims that depend on it (H7; nearest: RedacTek's paper-level three-generation risk scores, product-024). The cell where all four meet — recursive, entailment-structured premise decomposition + per-premise study-level evidence quality + a dependency-tracked verified-fact KB + symmetric no-verdict treatment of contested composites — is empty as of Aug 2026 (H1, H3', H6, H7). The architecturally closest research system is NELLIE (lit-009), which already does recursive backward-chaining decomposition grounded in a fact store and is missing exactly Verity's three distinctive layers: evidence-quality metadata, invalidation propagation, and no-verdict output. The closest analog to the argument graph itself is Kialo (product-019) — human-authored, no evidence retrieval, no quality metadata: the manual version of what Verity automates.

---

## 3. Evaluation plan

Adopts report B's Bucket 1/2/3 evaluation-status map, compressed to proposal-ready form.

### 3.1 Decomposition validity criteria → concrete evals

| Criterion (v0 spec) | Meaning | Concrete eval | Anchors |
|---|---|---|---|
| Joint sufficiency | premises jointly entail the claim | EntailmentBank Steps / Overall-AllCorrect metrics on generated trees + an NLProofS-style learned verifier scoring every step (also used as an inference-time gate) | lit-001, lit-005 |
| Verifiability descent | each premise strictly easier to verify; guarantees termination | termination tests against the alethiology: % of branches grounding in a KB fact within a depth budget; mean/max depth; non-terminating-branch rate (NELLIE's ground-or-recurse pattern is the model) | lit-009 |
| Non-redundancy | every premise load-bearing | leave-one-out entailment ablation: removing any single premise must drop verifier entailment confidence below threshold; a premise whose removal doesn't is redundant | lit-013; report B Stage 2 (verifier-confidence deltas) |

### 3.2 Bucket 1 — established benchmarks (run first; report comparable numbers)

- **Premise-verification module** (leaf verdicts only, consistent with the verdict boundary): SciFact (lit-016; biomedical — fits the beachhead), FEVER (lit-015) for scale, AVeriTeC (lit-017) for real-world claims.
- **Entailment-step validity:** EntailmentBank four-metric suite (lit-001) with NLProofS as the method baseline to beat/adopt (lit-005).
- **Reference bands** (cite the metric explicitly — 2024 and 2025 numbers are not comparable): AVeriTeC 2024 shared task top 63% (Hungarian METEOR, TUDA_MAI); 2025 top 0.332 (Ev2R, CTU AIC) vs. baseline 0.202 (lit-017).

### 3.3 Bucket 2 — proxy-only components (report proxies as proxies)

- **Decomposition faithfulness:** DecompScore + entailment coverage (lit-013); report the sensitivity of downstream verdicts to decomposition strategy as a first-class number (lit-014).
- **LLM annotation of premises/bias:** sampled human agreement + downstream classification + expert construct-validity checks — the Nakshatri (lit-018) and Penn Media Bias Detector (lit-019) validation template.
- **Evidence-quality tagging:** Semantic Scholar citation intent (free, coarse 3-class) with accuracy caveats; scite deferred — commercial API, and its per-class precision is vendor-reported and independently disputed (lit-028).

### 3.4 Bucket 3 — no benchmark exists; design new evals (both are contributions)

1. **Contested-claim decomposition.** Extend AVeriTeC's Conflicting Evidence/Cherry-picking cases (lit-017: <7% of training data, near-zero F1 — the field's hardest class) into entailment-tree annotations where the contest localizes to identifiable premises. Flag in the proposal as a publishable contribution in its own right (report B, Stage 3).
2. **Invalidation propagation.** JTMS layer (Doyle 1979, lit-026) over the alethiology + synthetic retraction-injection tests: mark a KB leaf retracted (as a Retraction Watch/Crossref update would), assert every dependent premise flips OUT and every affected claim graph re-renders flagged. Nearest neighbors for test design: NELL belief demotion (lit-025), Wikidata deprecated-rank handling (report B, Area 6c), and the retracted-papers-on-Wikipedia persistence study (arXiv:2509.18403 — in sources.jsonl with verify_before_proposal=true).

Roadmap, not v0: human-facing no-verdict presentation quality — adapt the belief-updating paradigm to measure discernment/calibration rather than persuasion, since Verity deliberately does not persuade (lit-023 makes persuasion the wrong endpoint).

---

## 4. Proposal skeleton (≤1 page)

**Problem.** Composite claims travel as take-it-or-leave-it units. A reader confronting "X causes Y" cannot see which premises the claim stands on, how strong the evidence under each premise is, or whether a load-bearing source has been retracted — nearly 55,000 retractions are machine-readable via Retraction Watch/Crossref as of end-2024 (report B, Area 6e), yet nothing downstream of a retracted paper gets flagged (H7). Existing tools either issue verdicts (PolitiFact, product-003; Originality.ai, product-007) — demanding trust transfer that fails exactly on contested claims — or offer transparency only at the article/source/citation level (H3 counterexamples), leaving the claim itself opaque.

**Gap (from §1–2).** Every ingredient exists; the conjunction does not, as of Aug 2026: decomposition without entailment structure or evidence quality (Loki, SAFE); transparency without decomposition (Ground News, Penn MBD); study-level metadata without an argument layer (scite — H2, H6); persistent fact stores without dependency tracking (Wolfram, ClaimReview caches — H7). NELLIE (lit-009) is the closest research architecture and lacks exactly the three layers Verity adds: evidence-quality metadata, invalidation propagation, no-verdict output.

**Approach.** Recursive backward-chaining decomposition of an input claim into 3–7 load-bearing premises satisfying three validity criteria — joint sufficiency, verifiability descent, non-redundancy (§3.1). Premises are checked against the alethiology (persistent verified-fact KB with per-fact provenance); unknown premises trigger agentic retrieval; every premise carries evidence-quality metadata; a JTMS dependency layer (Doyle 1979 — a formalism never applied to scholarly retractions) propagates any retraction to every dependent claim. Verdicts exist only at the leaves; contested composites render as symmetric evidence maps, never verdicts (H3').

**Beachhead: scientific/health claims; news is roadmap.** Retractions are structured, machine-readable data (Crossref/Retraction Watch), study design is a free MeSH field, and the invalidation moat is strongest exactly where RedacTek and scite stop at paper/citation level (report A, Rec. 4). Also matches the low-valence demo rule (viral statistics, retracted-but-still-cited papers).

**v0 evidence metadata — free APIs only** (report B, Area 6 table): retraction = OpenAlex `is_retracted` cross-checked against Crossref `update-to` (OpenAlex's boolean collapses update types and has a known false-positive history); study design = PubMed MeSH publication types (RCT / Meta-Analysis / Systematic Review); citation intent = Semantic Scholar (free, coarse); sample size = structured nowhere — text-mined and labeled low-confidence, or deferred.

**Evaluation (from §3).** Bucket 1 numbers first (SciFact leaf verification; EntailmentBank step metrics with an NLProofS-style verifier). Bucket 2 proxies reported as proxies (DecompScore, entailment coverage, leave-one-out ablation, downstream-sensitivity). Bucket 3 firsts framed as contributions: contested-claim entailment trees extending AVeriTeC's Conflicting/Cherry-picking subset, and synthetic retraction-injection over the JTMS layer.

**8-day build plan to v0** (claim → 3–7 premises → evidence → per-premise confidence; Streamlit or CLI):
- **D1** — decomposition harness: backward chaining to 3–7 premises; verifier check for joint sufficiency.
- **D2** — alethiology schema: facts + provenance + confidence + justification links; seed with demo-domain facts.
- **D3** — retrieval agent for unknown premises: OpenAlex / Crossref / PubMed / Semantic Scholar clients.
- **D4** — evidence-quality layer: retraction cross-check, MeSH study design, citation intent; N text-mined (low-confidence) or deferred.
- **D5** — JTMS invalidation over the alethiology; retraction-injection demo (retract a leaf → dependent claims flag).
- **D6** — per-premise confidence + inspectable claim-graph rendering (Streamlit).
- **D7** — eval harness: EntailmentBank step-metric sample, leave-one-out ablation, termination stats; two demo claims (a viral statistic; a retracted-but-still-cited finding).
- **D8** — polish; run logs + prompt-history packaging (this repo's commit and prompt history is itself a work sample).

**Motivation citation (baked in).** Cite DebunkBot as motivating-but-contested: Costello et al. 2024 (lit-020) always with the June 11, 2026 Science Editorial Expression of Concern noted, paired with the PNAS Nexus 2025 perceived-human replication (lit-022) and the "Just the facts" mechanism preprint (lit-021) — the direction (evidence exposure moves beliefs) is independently corroborated; exact effect sizes are treated as upper bounds pending correction. Verity's human endpoint is discernment, not persuasion (lit-023).

---

**Verification debts before proposal submission** (tracked in EXTRACTION_NOTES.md): RedacTek row all-inferred from one third-party review; FEVER URL mislabeling in sources_a.md; PNAS Nexus (lit-022) and JTMS/ATMS (lit-026/-027) primary URLs unverified; arXiv:2509.18403 unconfirmed; pricing and vendor-accuracy figures are marketing-claims.
