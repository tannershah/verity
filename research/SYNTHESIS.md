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

Targeted existence search performed 2026-08-13; no counterexample found.

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

Targeted existence search performed 2026-08-13; no counterexample found.

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

The matrix kills H3 as stated: Ground News (product-001) is `verdict_behavior: transparency-only` + `symmetric_contrasting_evidence: yes` as its core product ("we keep our team's subjective opinions out of the product"), Penn MBD (product-004) is transparency-only by design ("our goal is not to adjudicate what is true"), and scite (product-002) shows symmetric supporting/contrasting citations while rating sources only. I agree with report A's "FAILS (partially)" and record it as a clean death at the stated formulation. The pivot H3' survives by enumeration: the five transparency-only rows span article level (Ground News, product-001; Penn MBD, product-004), claim level (Perplexity, product-006; Loki, product-009), and argument-graph level (Kialo, product-019) — none at the decomposed-premise level of a composite claim. The claim-level candidates each fail H3' for independent reasons: Perplexity has no symmetric contrasting evidence and no decomposition (product-006, `symmetric_contrasting_evidence: no`, `claim_decomposition: none`, lowest-confidence row in the matrix); Loki decomposes into independent atomic facts not entailment-linked premises, and ultimately produces a verdict (product-009). The argument-graph candidate (Kialo) is fully manual with no evidence layer (product-019). SAFE and FActScore also issue verdicts (product-010, -011). H3' is adopted for all downstream positioning.

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
    "phrasing_note": "Proxy-only for entailment-structured decomposition faithfulness; gold benchmarks exist only for atomic-claim identification (CACDD, Zhang et al. 2025, Chinese/WebCPM; cf. FactLens, Mitra et al., ACL Findings 2025, fine-grained sub-claim verification). Neither tests joint sufficiency / load-bearing structure. None found for entailment-preserving decomposition as of Aug 2026."
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

H4b targeted search performed 2026-08-13: CACDD (Zhang et al. 2025, "A Claim Decomposition Benchmark for Long-Form Answer Verification," SpringerLink, doi:10.1007/978-981-96-1710-4_4) tests atomic-claim identification in Chinese/WebCPM context only; FactLens (Mitra et al., ACL Findings 2025, aclanthology.org/2025.findings-acl.929) tests fine-grained sub-claim verification. Neither tests joint sufficiency or load-bearing entailment structure. Ruling (pass 4.6): proxy-only; both added to literature.jsonl as lit-029 and lit-030, bucket claim-decomposition-factuality.
H4c targeted existence search performed 2026-08-13; no counterexample found.

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

Targeted existence search performed 2026-08-13; no counterexample found.

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

Targeted existence search performed 2026-08-13; no counterexample found.

Verified: every shipping retraction tool in the matrix is direct-status or 1-hop — scite Reference Check ("direct-status only", product-020), Zotero+Retraction Watch ("one hop, no propagation", product-021), RetractoBot ("1-hop emails", product-022), RetractionCheck/Crossref API ("federated lookup only", product-023). RedacTek (product-024) is the strongest counterexample and the paper-level→claim-level gap is the load-bearing distinction; note its row is all-inferred from a third-party review and is a high-priority verify-before-proposal item (EXTRACTION_NOTES). The only paradigm that does true dependency-directed retraction — truth maintenance systems (JTMS lit-026, ATMS lit-027) — has never been applied to scholarly retractions (report B, Area 6b). Report A's qualified-survive verdict is confirmed.

---

## 2. Positioning statement

Verity's defensible position is a conjunction, not any single feature. Automatic claim decomposition ships today (Loki, product-009; SAFE, product-010) — but into independent atomic facts, verdict-oriented, with no persistent KB. Transparency-only presentation ships today (Ground News, product-001; Penn Media Bias Detector, product-004) — but at the article/source level, never below it. Study-level evidence metadata ships today (scite, product-002: supporting/contrasting citations, retraction and editorial-concern flags) — but per citation statement, with no argument layer above it (H2). Persistent fact stores ship today (Wolfram Alpha's curated Knowledgebase, product-008; the ClaimReview fact-check cache behind Squash, product-015) — but none is dependency-tracked, and no shipping product propagates a retraction to the claims that depend on it (H7; nearest: RedacTek's paper-level three-generation risk scores, product-024). [Note: AVeriTeC's knowledge store (product-014) codes `persistent_knowledge_reuse: none` — it is a benchmark artifact, not a reusable persistent KB, and has been removed from this list per red-team finding 2.5.] The cell where all four meet — recursive, entailment-structured premise decomposition + per-premise study-level evidence quality + a dependency-tracked verified-fact KB + symmetric no-verdict treatment of contested composites — is empty as of Aug 2026 (H1, H3', H6, H7). The architecturally closest research system is NELLIE (lit-009), which already does recursive backward-chaining decomposition grounded in a fact store and is missing exactly Verity's three distinctive layers: evidence-quality metadata, invalidation propagation, and no-verdict output. The closest analog to the argument graph itself is Kialo (product-019) — human-authored, no evidence retrieval, no quality metadata: the manual version of what Verity automates.

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

**Motivation citation (baked in).** Cite DebunkBot as motivating-but-contested: Costello et al. 2024 (lit-020) always with the June 11, 2026 Science Editorial Expression of Concern noted, paired with the PNAS Nexus 2025 perceived-human replication (lit-022, three shared authors: Costello, Rand, Pennycook) and the "Just the facts" mechanism preprint (lit-021, same authors, unreviewed) — the direction (evidence exposure moves beliefs) is corroborated by same-team replications only; no fully independent replication is in the matrix; exact effect sizes are treated as upper bounds pending correction. Verity's human endpoint is discernment, not persuasion (lit-023); the verdict boundary is further motivated by lit-024 (same machinery amplifies conspiracy beliefs when directed at persuasion, not inspection).

---

**Verification debts before proposal submission** (tracked in EXTRACTION_NOTES.md): RedacTek row all-inferred from one third-party review; FEVER URL mislabeling in sources_a.md; PNAS Nexus (lit-022) and JTMS/ATMS (lit-026/-027) primary URLs unverified; arXiv:2509.18403 unconfirmed; pricing and vendor-accuracy figures are marketing-claims.

---

## Red Team (independent pass)

**Date:** 2026-08-13. **Stance:** independent reviewer; did not write the synthesis above and owes it no loyalty. Persona: skeptical Wharton GenAI Studio reviewer fluent in the fact-checking and NLP literature. Every objection is traced to matrix rows, GATE_REPORT.md, the raw reports, or a quoted internal inconsistency. No new external research was performed; where a search is needed to settle a point, it is listed as a pre-submission action, not performed here.

### 1. External objections at full strength

#### 1a. "Verity is Loki + scite + Ground News with a UI"

The sharp version of this objection is not that each feature exists somewhere — the synthesis concedes that. It is that Verity's own matrix shows the assembly is nearly done and the distinctions holding the whitespace open are the softest cells in the schema.

Take Loki (product-009) as the base. On the frozen schema's own enums, Loki already sits in most of H1's cell: `claim_decomposition: automatic`, `verdict_behavior: transparency-only`, `symmetric_contrasting_evidence: yes`, `interactivity: inspectable-drilldown` — an automatic decomposer whose Evidence & Reasoning panel shows supporting/refuting/contextualizing evidence per claim in a UI and "withholds final judgment for the user" (report A, which calls it "the single closest existing system to Verity's decomposition + transparency ethic"). It is open-source (SCHEMA_GAPS gap 2) — not merely prior art but a fork target. Exactly three qualifiers keep Loki out of Verity's cell: (i) atomic rather than entailment-linked decomposition; (ii) journalist/researcher-facing rather than consumer; (iii) a verdict is ultimately produced. Now weigh those qualifiers against Verity's own records. (ii) is not a schema field at all — gap 5 states the consumer/professional distinction "is load-bearing for H1" and "is carried only in extraction_notes"; report A's caveats concede "'Consumer product' is a judgment boundary; Loki and Full Fact straddle research/professional/consumer lines. H1 and H3 verdicts depend on that boundary and are stated conditionally." (iii) failed the extraction gate — GATE_REPORT Check 2 found the verdict qualification "exists only in raw reports" and had to patch it into the row — and it is thinner than it looks: Loki withholds judgment from the user while computing one internally, and per finding 2.6 below, Verity on a fully grounded claim likewise possesses a derivable composite verdict and declines to render it. On resolvable claims the two postures converge; the difference is real only on contested composites — which is exactly where Verity has no evaluation evidence yet (Bucket 3). That leaves (i), a single technical distinction, carrying the entire H1 verdict.

The pattern generalizes, and a reviewer will see it. Of seven hypotheses: H3 died and was replaced by narrower H3'; H5 died and was replaced by narrower H5'; H4 split three ways with H4a dying; H1 survives only as a three-conjunct formulation ("consumer packaging + entailment-linked premise decomposition + per-premise evidence"). Each move is documented and individually defensible, but the cumulative shape is a whitespace claim maintained by adding conjuncts until the cell empties. An empty cell in an analyst-defined 24×10 matrix is weak evidence of an opportunity; the null hypothesis a reviewer will apply is that the cell is unoccupied because it is not worth occupying, and nothing in either sweep rules that out — no row and no literature entry shows user demand for entailment-structured premise inspection.

The business form is strongest. The components are commodities: the evidence layer is explicitly assembled from free APIs (§4 — OpenAlex, Crossref, PubMed MeSH, Semantic Scholar), data scite (product-002) already owns at 1.6B-citation scale with an MCP integration shipping; the decomposition layer is open-source (Loki); the presentation posture is Ground News's (product-001). scite plus a Loki fork plus a comparison UI is a plausible fast-follow, and the conjunction is an architecture claim, not a moat claim, until the alethiology has accumulated facts worth reusing — and it starts empty (§4, D2: "seed with demo-domain facts").

#### 1b. "The DebunkBot result does not support the polarization thesis"

The proposal needs the DebunkBot line to license one premise: exposing readers to evidence improves their beliefs — the thesis the motivation paragraph rides on. At full strength, the objection is that the line does not support that premise for Verity's product in any of its states.

**Magnitude is formally in question.** Costello et al. 2024 (lit-020) carries a Science Editorial Expression of Concern (Thorp, June 11, 2026; Science 392(6803):1131) over data issues that "made it challenging to reproduce some of the specific values reported in the manuscript" and "inconsistencies in the application of screening criteria between" experiments (report B, Area 5). The matrix row itself says effect sizes are "materially weakened" and to treat them as upper bounds. A prize-winning, 192-citation result under an EoC is precisely the profile of findings that later shrink.

**The corroboration is not independent.** Both papers cited as corroborating the direction are same-team: "Just the facts" (lit-021) is Costello, Pennycook & Rand themselves, in an unreviewed OSF preprint; Boissin et al. (lit-022) shares three of five authors with the original (Costello, Rand, Pennycook). §4's claim that the direction is "independently corroborated" is false as written (finding 2.1). The evidentiary base for "evidence moves beliefs" is one flagged paper plus two same-lab follow-ups drawn from the same online-panel methodology report B itself caveats.

**Even at face value, it motivates the competitor, not Verity.** What the line demonstrates is persuasion by verdict-shaped counterargument — the design Verity rejects and the design its authors shipped (debunkbot.com; H5 died on it). The only matrix evidence on Verity's actual endpoint — durable discernment — is lit-023, and it is a null: "belief shifts do not transfer to independent discernment skills." (lit-023 is itself an unreviewed preprint with N unreported in the matrix — but the burden sits with the proposal, which currently cites no positive evidence on its endpoint at all.) No study in either sweep tests whether a symmetric no-verdict evidence map moves beliefs, discernment, or calibration. And lit-024 shows the same machinery amplifies conspiracy beliefs — which supports Verity's no-verdict design as risk mitigation, but also means the "evidence moves beliefs" premise is a category liability, and Verity's mitigation (refusing to persuade) removes the very mechanism whose efficacy the motivation cites.

**How the proposal should cite DebunkBot — exactly:**
1. Cite Costello et al. 2024 once, in the motivation paragraph, for direction only ("evidence-based AI dialogue can shift beliefs"); never cite the ~20% / 2-month magnitudes, even as upper bounds.
2. The EoC rides in the same sentence — "(Editorial Expression of Concern, Science, June 11, 2026)" — never a footnote.
3. Replace "independently corroborated" with "corroborated by same-team replications," naming them as such: Boissin et al. PNAS Nexus 2025 (lit-022, three shared authors) and the "Just the facts" OSF preprint (lit-021, same authors, unreviewed).
4. Use the critiques as design rationale, not adversaries: lit-023 (no skill transfer) is the stated reason Verity's human endpoint is discernment/calibration; lit-024 (dual-use persuasion) is the stated reason for the verdict boundary. lit-024 currently appears nowhere in the proposal skeleton — add it.
5. Claim no empirical support for transparency-only efficacy; label it Bucket 3 / open question (§3.4), and cite debunkbot.com (H5') in the differentiation paragraph as the persuasion-shaped productization Verity is not.

#### 1c. "Backward chaining over an alethiology cannot terminate reliably on contested real-world claims"

**The termination property Verity cites is inherited from a substrate Verity does not have.** Every terminating system in the matrix grounds in a curated known-true corpus: EntailmentBank's "termination = axiom-matching in corpus" (lit-001), LAMBADA's "termination = axiom/fact match in the provided theory" (lit-006), NELLIE's corpus of "authoritative facts" (lit-009). Report B's Area 1 synthesis states it flatly: recursion "terminates by grounding leaves in a fixed corpus of assumed-true facts," and "None models leaf trustworthiness, retraction, or continued validity." The alethiology is not such a corpus. It starts empty (§4, D2: "seed with demo-domain facts"); it is populated by the system's own least-validated outputs (agentic retrieval plus free-API metadata); and — uniquely among all systems surveyed — its leaves can flip OUT under JTMS invalidation (lit-026), so grounding is non-monotonic: a tree that terminated yesterday can be un-grounded today. NELL (lit-025) is the matrix's own cautionary tale for a self-populating KB: semantic drift, "mitigated but not solved."

**"Verifiability descent" is asserted, not defined.** §3.1 says each premise is "strictly easier to verify" and that this "guarantees termination." No measure of verification difficulty appears anywhere in the matrix or the eval plan; nothing enforces strict descent. For contested claims the descent premise is empirically false in the field's hardest data: AVeriTeC's Conflicting Evidence/Cherry-picking class exists precisely because the conflict lives at the level of the supporting facts — the contest does not localize into easier subproblems. That class is <7% of training data and near-zero F1 for most systems (lit-017): the field collapses on exactly the claims Verity is built for.

**The synthesis quietly concedes the point.** The same §3.1 row that claims descent "guarantees termination" defines its own eval as "% of branches grounding in a KB fact within a depth budget; mean/max depth; non-terminating-branch rate." A procedure with guaranteed termination has no non-terminating-branch rate. What is actually guaranteed is a depth cutoff — termination by giving up — and the honest form of the objection is: on contested real-world claims, most branches will exit by budget rather than by grounding, and the product will render trees of unverified premises.

**Step error compounds with depth.** In the friendliest available setting — curated science claims, gold + distractor leaves provided (EntailmentBank Task 2) — the best method line tops out at 33.3% Overall-AllCorrect (NLProofS, lit-005): two-thirds of trees contain at least one structural error when the true leaves are handed over. Verity's setting is harder on every axis: open retrieval instead of gold leaves, contested instead of curated claims, recursive depth instead of shallow trees, a moving KB instead of a frozen corpus. And the non-redundancy criterion means step errors are never padding — every premise is load-bearing, so a single invalid step breaks the entailment for the whole branch. A reviewer with this background will ask for the expected grounding rate on the beachhead domain and will not accept "guarantees termination" as written.

### 2. Attacks on the synthesis itself

Findings ordered by severity. Each is traceable; direction of error noted where it matters.

**2.1 — §4 "independently corroborated" is unsupported (fix before submission).** The motivation paragraph states "the direction (evidence exposure moves beliefs) is independently corroborated." Both corroborating citations are same-team: lit-021 is Costello, Pennycook & Rand (the original authors); lit-022 is Boissin, Costello, Spinoza-Martín, Rand & Pennycook. The matrix plants the error — lit-022's not_handled field calls it "independent replication value" — and the synthesis inherited it. Reword per 1b(3), and fix the lit-022 row note.

**2.2 — The H5 miss is a measured failure rate for the sweeps, and the synthesis does not propagate it.** §1's preamble states the search bound honestly, but the record is stronger than a caveat: the only surviving-negative hypothesis that received a targeted post-synthesis query (H5) died instantly, on a deployment publicly announced ten months earlier (MIT Technology Review, Oct 2025). Zero of H1, H2, H4b, H4c, H6, H7 have received such a query. Pre-submission action: one targeted search per surviving negative — consumer decomposition products (H1), decomposition × study-metadata products (H6), RedacTek product documentation (H7, which also clears the verification debt).

**2.3 — H7's counterexample analysis rests on the least-verified row in the matrix.** RedacTek (product-024) is all-inferred from one third-party review (EXTRACTION_NOTES: "High-priority verify_before_proposal item"), yet §2 stakes "no shipping product propagates a retraction to the claims that depend on it," and report A stakes the "most defensible technical moat," on the paper-level/claim-level distinction read out of that single review. If the review under-describes the product — or RedacTek has shipped claim-level features since the Oct 2025 review — H7 weakens in the direction most damaging to the proposal. The debt is disclosed at the end of the synthesis, but the §2 positioning language carries none of the uncertainty.

**2.4 — The H3' enumeration sentence is false as written.** §1 (H3): "every transparency-only row sits at article, source, or citation level." The matrix has five transparency-only rows and three are not at those levels: Perplexity (product-006, claim), Loki (product-009, claim), Kialo (product-019, argument-graph). The synthesis's own next clause treats Loki and Kialo as premise-level candidates, contradicting the "every" sentence, and Perplexity is never addressed in the H3' argument at all. H3' still survives — Perplexity has `claim_decomposition: none`, `symmetric_contrasting_evidence: no`, and is the matrix's lowest-confidence row (nine of ten cells inferred, EXTRACTION_NOTES) — but this is the kind of checkable error a reviewer with the matrix in hand finds in five minutes. Rewrite the sentence.

**2.5 — §2 contradicts the matrix on AVeriTeC's knowledge store.** The positioning statement cites "AVeriTeC's knowledge store (product-014)" as a shipping persistent fact store; product-014 codes `persistent_knowledge_reuse: none` with the note "a benchmark artifact, not a reusable persistent KB." Benign in direction (it concedes prior art the matrix says doesn't exist) but it is a positioning/matrix contradiction: cite Wolfram (product-008) and the ClaimReview cache (product-015) only.

**2.6 — "Verdicts exist only at the leaves" + joint sufficiency ⇒ derivable root verdicts.** §3.1's first criterion requires premises that "jointly entail the claim"; the verdict boundary says verdicts exist only at leaves. When every leaf of a claim verifies IN, entailment transmits truth to the root mechanically: the system possesses a composite verdict and declines to render it. So for resolvable claims the no-verdict posture is presentational, and for contested claims there are no leaf verdicts to withhold. The design survives — the substantive commitment is no editorial adjudication where evidence conflicts, and D6 renders per-premise confidence only, never a root aggregate — but the current copy invites the "you compute verdicts and hide them" gotcha (and it is the same gotcha the synthesis runs on Loki in H1). The proposal needs one sentence pinning the boundary to conflicting-evidence states.

**2.7 — Matrix erratum, handled correctly by the synthesis.** lit-017's metrics field attaches "baseline 0.202" to the 2024 Hungarian-METEOR shared task as well as 2025; report B gives 0.202 only for the 2025 Ev2R metric. §3.2 cites it correctly (0.202 against 2025 only). Fix the row so the proposal cannot inherit the error.

**What held up.** Re-derived from all 24 product rows: the H1 enumeration (automatic decomposers are exactly products-009/-010/-011) and the H6 double enumeration (study-level rows are exactly products-002 and -020 through -024, all with `claim_decomposition: none`) are correct. H2 is confirmed with no counterexample. The NLProofS and EntailmentBank numbers match lit-001/lit-005; the ~55,000-retraction figure matches report B Area 6e; §3.2's metric non-comparability warning is right. The H4 three-way split and the H5 death-and-detection note are honest handling, not spin. Beyond the seven findings above, no other unsupported verdict, positioning claim, or eval-plan element was found.

### 3. The two strongest objections, with pre-emptions

Selected: **1a** (the mashup/whitespace attack) and **1c** (the termination attack) — respectively, whether the empty cell is worth occupying and whether the core loop functions, the two questions an informed reviewer will actually ask. 1b is neutralized by citation discipline (the prescription in 1b plus fix 2.1); the §2 findings are line edits.

**Pre-emption of 1a (drop-in):**

> Each of Verity's layers ships somewhere today — automatic decomposition in Loki, study-level evidence metadata in scite, symmetric no-verdict presentation in Ground News — and we cite them as prior art rather than discovering them. The conjunction is load-bearing, not gerrymandered, because the layers only function together: retraction propagation needs entailment-linked premises to propagate along (atomic-fact decomposition hands a JTMS a graph with no edges), and per-premise evidence quality only matters when premises are load-bearing rather than independent trivia. That is why the closest research system, NELLIE (IJCAI 2024), had to build the same recursive KB-grounded core rather than extend a Loki-style atomic pipeline — a fast-follower forking Loki reproduces the UI, not the dependency structure the invalidation moat runs on.

**Pre-emption of 1c (drop-in):**

> Verity does not assume contested branches will ground; it enforces termination — depth budget plus a per-step NLProofS-style verifier gate — and treats where grounding stops as signal: a branch that exhausts verifiability descent surfaces as an unverified premise with its symmetric evidence attached, which on contested material is the product's intended output, not a failure mode. Grounding rate, decomposition depth, and budget-exit rate are therefore reported as first-class metrics (§3.1), and the beachhead is chosen so leaves ground in machine-readable fact — retraction status, MeSH study design — rather than contested testimony. The field's near-zero F1 on AVeriTeC's Conflicting/Cherry-picking class is a failure of forcing verdicts onto contested claims — Verity's argument, not its refutation — and extending that subset to premise-level annotation is scoped in §3.4 as a contribution precisely because the eval Verity needs does not yet exist.

Adopting the 1c pre-emption requires the copy fix implied by finding 2.6's neighbor: in §3.1 and the v0 spec, replace "guarantees termination" with "termination enforced by depth budget; grounding rate measured and reported."
