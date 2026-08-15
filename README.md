# Verity

**An epistemic transparency engine.** Input: text containing claims. Verity recursively decomposes each claim into its load-bearing premises, checks those premises against a persistent store of verified facts, retrieves evidence for the ones it doesn't know, attaches evidence-quality metadata to every premise, and renders the result as an inspectable graph — never as a verdict on the composite claim.

The bet is that a reader confronting "X causes Y" should be able to see *which premises the claim stands on*, *how strong the evidence under each one is*, and *whether a load-bearing source has been retracted* — and that no shipping product lets them do that.

---

## Contents

- [Pipeline](#pipeline)
- [Hard design constraints](#hard-design-constraints)
- [Current state](#current-state)
- [Repo map](#repo-map)
- [What the research established](#what-the-research-established)
- [Build plan](#build-plan)
- [Evaluation](#evaluation)
- [Stack and data sources](#stack-and-data-sources)
- [Working conventions](#working-conventions)
- [Recorded verification debts](#recorded-verification-debts)
- [Glossary](#glossary)
- [Origin](#origin)

---

## Pipeline

```
claim
  └─▶ backward-chaining decomposition ──▶ 3–7 load-bearing premises
        │                                   (joint sufficiency · verifiability descent · non-redundancy)
        │                                   verifier gate scores every step
        ├─▶ premise known?  ──yes──▶ alethiology (persistent verified-fact KB, per-fact provenance)
        │                    ──no───▶ agentic retrieval (OpenAlex · Crossref · PubMed · Semantic Scholar)
        ├─▶ evidence-quality metadata per premise
        │     retraction status · study design · citation intent · sample size
        ├─▶ JTMS layer: retract a leaf ──▶ every dependent premise flips OUT ──▶ affected graphs re-render flagged
        └─▶ render: per-premise confidence, symmetric evidence on contested premises, no root aggregate
```

Recursion terminates by depth budget, not by assumption. A branch that exhausts verifiability descent surfaces as an *unverified premise with its symmetric evidence attached* — on contested material that is the intended output, not a failure mode.

---

## Hard design constraints

These are settled decisions, not preferences. Code or copy that violates them is wrong.

**1. The verdict boundary.** Verdicts exist **only at the leaves** — verified premises in the alethiology. Contested composite claims get transparency-only treatment: surface the evidence and critiques on all sides, adjudicate nothing. **No root aggregate is ever displayed.**

The known gotcha, recorded as red-team finding 2.6 in [research/SYNTHESIS.md](research/SYNTHESIS.md): joint sufficiency plus all-leaves-verified mechanically *implies* a composite verdict, so on fully resolvable claims the no-verdict posture is presentational. The substantive commitment is **no editorial adjudication where evidence conflicts**. Pin the boundary to conflicting-evidence states when writing about it.

**2. Decomposition validity criteria** (v0 spec and eval target):

| Criterion | Meaning | How it's checked |
|---|---|---|
| **Joint sufficiency** | Premises jointly entail the claim | Learned verifier scores every step; also an inference-time gate (NLProofS-style) |
| **Verifiability descent** | Each premise strictly easier to verify; **termination enforced by depth budget** | Grounding rate, mean/max depth, and budget-exit rate measured and reported |
| **Non-redundancy** | Every premise load-bearing | Leave-one-out ablation: removing any premise must drop verifier entailment confidence below threshold |

Termination is **enforced, not guaranteed** — a depth budget plus a per-step verifier gate. Any wording that upgrades this to a guarantee is banned repo-wide; see [CLAIMS.md](CLAIMS.md) for the exact phrase and its replacement.

**3. Demo-claim valence rule.** Demo and example claims use verifiable, low-valence cases: viral statistics, retracted-but-still-cited papers, manipulated charts. Contested scientific and political claims are roadmap stress tests only.

**4. The frozen schema.** [research/matrix/schema.json](research/matrix/schema.json) is FROZEN — extraction enums plus hypotheses H1–H7. Never modify it. Structural mismatches get flagged in [research/matrix/SCHEMA_GAPS.md](research/matrix/SCHEMA_GAPS.md) or in a row's `extraction_note` instead. Eight gaps are recorded there; gap 8 documents a provenance-tier vocabulary that *couldn't* be encoded because the schema is frozen.

---

## Current state

**Research: complete through pass 7.** Seven hypotheses adjudicated, positioning locked, evaluation plan built, evaluation floors pre-registered, an adversarial review pass run and remediated, and a committee remediation pass closed.

**Build: not started.** No code exists in this repository. [EVAL_PREREG.md](EVAL_PREREG.md) is stamped *"Committed 2026-08-13 (pass 7), before D1 of the v0 build"* — D1 through D8 are all ahead.

The research record was produced in numbered passes, each committed separately:

| Pass | What it produced |
|---|---|
| 2 | Schema-bound extraction from two deep-research reports → the matrix |
| 2.5 | Extraction gate check → [GATE_REPORT.md](research/matrix/GATE_REPORT.md), verdict *clear for pass 3* |
| 3 | Hypothesis adjudication, positioning, eval plan, proposal skeleton |
| 3.1 | H5 amended — debunkbot.com found shipped; pivot to H5′ |
| 4 | Adversarial review with pre-registered attack surfaces, plus an unscripted audit (findings 2.1–2.7) |
| 4.5 | Red-team remediation + negative-hypothesis existence searches → [STRESS_SEARCH.md](research/STRESS_SEARCH.md) |
| 4.6 | Escalation rulings — H4b refined, RedacTek row corrected |
| 5 | Proposal drafting + bibliographic debt burndown |
| 6 | H3′/H5′ multi-vocabulary existence battery |
| 7 | Committee remediation — H3″ adopted, near-miss rows added, prereg floors and claims lint created |

Every edit made in passes 4.5 through 7 is logged before → after in [research/matrix/REMEDIATION_LOG.md](research/matrix/REMEDIATION_LOG.md).

---

## Repo map

| Path | What it is | Read it when |
|---|---|---|
| [.claude/CLAUDE.md](.claude/CLAUDE.md) | Project rules for agents — design constraints, working rules, model/effort conventions, stack | Always, first |
| [proposal.md](proposal.md) | The ≤2-page proposal, drafted at pass 5 — problem, gap, approach, evaluation, build plan | You want the narrative version of the thesis |
| [research/SYNTHESIS.md](research/SYNTHESIS.md) | **Source of truth for positioning and hypothesis verdicts.** Adjudication (§1), positioning (§2), eval plan (§3), proposal skeleton (§4), red team appended | Any question about what was decided and why |
| [EVAL_PREREG.md](EVAL_PREREG.md) | Pre-registered pass/fail floors and the falsification line, committed before D1 | Before writing any eval code |
| [CLAIMS.md](CLAIMS.md) | Banned-phrase lint. Each `BAN:` is a literal phrase; `WHY:` gives the falsification, `USE:` the corrected replacement | Before writing any outward-facing copy |
| [research/STRESS_SEARCH.md](research/STRESS_SEARCH.md) | Existence-search record — §C single-query pass, §D RedacTek verification, §E source burndown, §F multi-vocabulary battery | You need the search bound behind a "none found" claim |
| [research/matrix/](research/matrix/) | The evidence base — see below | You need a primary row rather than a summary |
| [research/raw/](research/raw/) | Two deep-research reports + their source lists. **Read-only inputs** | You want the unextracted original |

### The matrix

| File | Rows | Contents |
|---|---|---|
| [products.jsonl](research/matrix/products.jsonl) | 29 | Competitive landscape, one row per product, ten schema-enum cells + per-cell provenance + extraction note |
| [literature.jsonl](research/matrix/literature.jsonl) | 34 | Papers across six buckets: entailment trees, claim-decomposition factuality, fact-verification benchmarks, discourse decomposition, belief updating, knowledge substrate |
| [sources.jsonl](research/matrix/sources.jsonl) | 98 | Every URL with access date, confidence tier, and `verify_before_proposal` flag |
| [schema.json](research/matrix/schema.json) | — | FROZEN row schemas, hypotheses H1–H7, verdict format |
| [EXTRACTION_NOTES.md](research/matrix/EXTRACTION_NOTES.md) | — | Low-confidence rows, skipped papers with reasons, marketing-claim cells needing verification |
| [SCHEMA_GAPS.md](research/matrix/SCHEMA_GAPS.md) | — | Eight structural gaps between the frozen schema and reality |
| [GATE_REPORT.md](research/matrix/GATE_REPORT.md) | — | Pass-2.5 five-check gate, three fixes applied, verdict *clear for pass 3* |
| [REMEDIATION_LOG.md](research/matrix/REMEDIATION_LOG.md) | — | Every post-red-team edit, before → after, with the finding it answers |

Row counts in `EXTRACTION_NOTES.md` and `GATE_REPORT.md` (24 / 28 / 96) describe the pass-2 state those documents audited; pass 7 added `product-025`–`029` and `lit-031`–`034`.

---

## What the research established

### Hypothesis verdicts

All negative claims are phrased **"none found as of Aug 2026"** — a search bound over two deep-research sweeps plus targeted existence batteries, not a proof of nonexistence.

| # | Final formulation | Verdict | Killed by / nearest miss |
|---|---|---|---|
| **H1** | No *consumer* product auto-decomposes claims into entailment-linked load-bearing premises with per-premise evidence | **survives** (three conjuncts) | Loki / OpenFactVerification (`product-009`) — automatic but *atomic*, researcher-facing, ultimately verdict-producing |
| **H2** | scite has no argument-structure layer above citations | **survives** | No counterexample |
| **H3** | *as stated* — no checker offers symmetric transparency-only inspection as core product | **dies** | Ground News (`product-001`) — that *is* its core product |
| **H3″** | **No *automated* system offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim** — ADOPTED, use in all downstream copy | **survives** | Consensus (`product-025`) and ARGUMEND (`product-027`) excluded on *transparency-only* (both render root-level aggregates); The Society Library (`product-026`) and Kialo (`product-019`) excluded on *automated* (human-curated) |
| **H4a** | Entailment-*step* validity has no standard benchmark | **dies** | EntailmentBank (`lit-001`) — four-metric suite, mature method line. Adopt its metrics; never claim they're missing |
| **H4b** | No gold benchmark for entailment-preserving decomposition *faithfulness* | **survives** (proxy-only) | CACDD (`lit-029`) and FactLens (`lit-030`) test atomic-claim identification / sub-claim verification, not joint sufficiency |
| **H4c** | No evaluation exists for decomposition of *contested* real-world claims | **survives** | AVeriTeC's Conflicting/Cherry-picking class (`lit-017`) is a verdict class, not a decomposition eval |
| **H5** | *as stated* — DebunkBot line not productized as a self-serve tool | **dies** | debunkbot.com — live, self-serve, announced in *MIT Technology Review* Oct 2025 |
| **H5′** | The belief-updating line is productized **only as persuasion**, not as self-serve symmetric inspection — ADOPTED | **survives** | Watch item: Belief Explorer (`lit-034`, CHI 2026 prototype). If it or the Meyer paradigm commercializes, H5′ dies |
| **H6** | No system combines argument-structure decomposition with evidence-quality metadata | **survives** | Loki — atomic not argument-structure, source-level not study-level: one level short on both axes |
| **H7** | No product does *claim-level* dependency-propagated invalidation | **survives** | RedacTek (`product-024`) — genuine three-generation propagation, but of **paper-level** suspicion scores |

Two of seven died in synthesis adjudication (H3, H4a), a third in the pass-3.1 amendment (H5), and H4 split three ways. The adversarial review pass changed no verdicts; it found seven further defects in the synthesis itself (§2.1–2.7 of [SYNTHESIS.md](research/SYNTHESIS.md)), all remediated.

### Positioning

**Lead with the conjunction argument and the invalidation moat — not the empty cell.** (Committee-adopted, pass 7.)

Every ingredient ships somewhere today; the conjunction does not:

- **Automatic decomposition** — Loki, SAFE — but into independent atomic facts, verdict-oriented, no persistent KB
- **Study-level evidence metadata** — scite — but per citation statement, no argument layer above it
- **Symmetric no-verdict presentation** — Ground News, Penn Media Bias Detector — but at article/source level, never below
- **Persistent fact stores** — Wolfram's curated Knowledgebase, the ClaimReview caches — but none dependency-tracked

The conjunction is **load-bearing, not gerrymandered**, because the layers only function together: retraction propagation needs entailment-linked premises to propagate *along* — atomic-fact decomposition hands a dependency tracker a graph with no edges — and per-premise evidence quality only matters when premises are load-bearing rather than independent trivia. That is why NELLIE (`lit-009`, IJCAI 2024), the architecturally closest research system, built a recursive KB-grounded core rather than extending a Loki-style atomic pipeline. NELLIE lacks exactly Verity's three added layers: evidence-quality metadata, invalidation propagation, no-verdict output.

**Near-misses are demand evidence, not just exclusions.** Four independent teams shipped adjacent pieces of this design (Consensus, ARGUMEND, The Society Library, Elicit). That answers *"is the cell empty because nobody wants it?"* better than any other line in this record. Name them in downstream copy.

**The moat's evidence splits, and the split must be preserved.** Conflating these is banned:

| Link | Evidence | What it shows |
|---|---|---|
| **Impact** | VITALITY (`lit-031`) | Excluding retracted RCTs reverses pooled-effect direction in 8.4% and changes statistical significance in 16.0% of contaminated meta-analyses |
| **Uptake** | RetractoBot RCT (`lit-033`) | **Null** — −0.007 (95% CI −0.055 to 0.041). Post-hoc, out-of-workflow notification to past citers does not change citing behavior; 80.6% of responding authors were unaware of the retraction |
| **Bet** | — | Decision-time surfacing to readers, editors, and synthesists is Verity's **stated bet**, not a demonstrated result |

### The two strongest external objections

Both are pre-empted in [SYNTHESIS.md](research/SYNTHESIS.md) §3 of the red team, with drop-in responses:

1. **"Verity is Loki + scite + Ground News with a UI."** Answered by the conjunction argument above.
2. **"Backward chaining over an alethiology cannot terminate reliably on contested real-world claims."** Answered by enforced termination plus treating where grounding stops as signal — and by the beachhead choice, which puts leaves on machine-readable fact rather than contested testimony.

### Beachhead

**Scientific and health claims. News is roadmap.** Chosen because leaves ground in machine-readable fact — retraction status, study design — rather than contested testimony, and because the invalidation moat is strongest exactly where scite and RedacTek stop, at citation and paper level.

---

## Build plan

Eight work packages, D1–D8, from [SYNTHESIS.md](research/SYNTHESIS.md) §4. Target: `claim → 3–7 premises → evidence → per-premise confidence`, Streamlit or CLI.

| | Package |
|---|---|
| **D1** | Decomposition harness — backward chaining to 3–7 premises; verifier check for joint sufficiency |
| **D2** | Alethiology schema — facts + provenance + confidence + justification links; seed with demo-domain facts |
| **D3** | Retrieval agent for unknown premises — OpenAlex / Crossref / PubMed / Semantic Scholar clients |
| **D4** | Evidence-quality layer — retraction cross-check, MeSH study design, citation intent, sample size |
| **D5** | JTMS invalidation over the alethiology; retraction-injection demo (retract a leaf → dependent claims flag) |
| **D6** | Per-premise confidence + inspectable claim-graph rendering (Streamlit) |
| **D7** | Eval harness — EntailmentBank step-metric sample, leave-one-out ablation, termination stats; two demo claims (a viral statistic; a retracted-but-still-cited finding) |
| **D8** | Polish; run logs |

**Deferred to the build**, explicitly (pass-7 log, "Not done in this pass"): conflicted-state semantics, binarization intermediates, and the annotator roster for the human step-validity protocol.

**Two known design pressures on D2.** The alethiology starts *empty* and is populated by the system's own least-validated outputs; and its leaves can flip OUT under JTMS, so grounding is **non-monotonic** — a tree that terminated yesterday can be un-grounded today. Every terminating system in the matrix grounds in a fixed curated corpus instead. NELL (`lit-025`) is the matrix's cautionary tale for a self-populating KB: semantic drift, "mitigated but not solved."

---

## Evaluation

### Pre-registered floors

From [EVAL_PREREG.md](EVAL_PREREG.md) — pass/fail lines, not aspirations. Failing one is a reportable result. No floor may be revised after D1 except by a logged, dated amendment stating what was learned.

| Floor | Line | If it fails |
|---|---|---|
| **Grounding rate** | ≥ 50% of branches ground within a depth-3 budget on the 20-claim beachhead set. *"Grounds"* means descent to a citation-shaped premise matched to an alethiology fact by **exact key only** (DOI / PMID / NCT) | Verifiability descent fails in practice for current retrieval; thesis pivots to curated-domain alethiologies |
| **Human-judged step validity** | ≥ 80%, via the Q18 protocol: 30 generated trees, every step judged by two annotators on (i) entailment holds, (ii) premise verifiable as written, (iii) load-bearing; disagreements adjudicated; report with Cohen's κ | **Below the floor: no public demo.** A visible structural error in one step of five is disqualifying for a tool whose only product is trust |
| **Retraction false-flag rate** | ≤ 5% on the real-claim linkage eval — ~50 real claims from crossing Retraction Watch with public claim corpora | The professional tool is net-harmful: alarm fatigue destroys the value proposition the moat rests on |

**Display consequence, baked in:** 80% per-step validity implies ~0.8⁵ ≈ 33% of five-premise trees are fully clean — consistent with field SOTA. **The UI must therefore render per-premise verifier confidence, never tree-level polish alone.**

**Falsification line (disagreement localization).** If fewer than 40% of contested items localize to ≤ 2 premises at κ ≥ 0.6, localization fails as the organizing center and the discernment endpoint carries the welfare claim alone. Both endpoints are co-primary regardless — the answer to endpoint-shopping is to pre-register both, not to swap. The thresholds are stipulative; prereg's value is the timestamp, not the number.

### Benchmark map

**Bucket 1 — established benchmarks, run first, report comparable numbers.**
- Leaf verification: SciFact (`lit-016`, biomedical, fits the beachhead), FEVER (`lit-015`) for scale, AVeriTeC (`lit-017`) for real-world claims
- Entailment-step validity: EntailmentBank four-metric suite (`lit-001`), with NLProofS (`lit-005`) the baseline to beat or adopt — Task 2 Overall-AllCorrect 20.9% → 33.3% in-paper (34.4% released checkpoint), strongest baseline EntailmentWriter T5-11B at 25.6%
- **Reference bands must carry their metric** — 2024 and 2025 AVeriTeC scores use different formulas and are not comparable: 2024 top 63% (Hungarian METEOR); 2025 top 0.332 vs. baseline 0.202 (Ev2R)

**Bucket 2 — proxies, reported as proxies.** Entailment coverage; downstream-verdict sensitivity to decomposition strategy as a first-class number (`lit-014`); leave-one-out ablation for non-redundancy; LLM annotation validated by sampled human agreement (the Penn Media Bias Detector template, `lit-019`); Semantic Scholar citation intent with accuracy caveats.

**Bucket 3 — no benchmark exists; both are contributions.**
1. **Contested-claim decomposition** — extend AVeriTeC's Conflicting Evidence/Cherry-picking class (<7% of training data, near-zero F1 for most systems) into entailment-tree annotations where the contest localizes to identifiable premises.
2. **Invalidation propagation** — the real-claim **linkage eval** is the field-facing contribution. Synthetic retraction-injection over the JTMS is a **regression test of our own code, not a contribution** — don't present it as one.

**Roadmap, not v0:** a discernment/calibration study adapting the belief-updating paradigm to Verity's actual endpoint.

### Standing rules

- Every model-produced eval number is paired with a human-anchored calibration sample or explicitly labeled **uncalibrated**.
- EntailmentBank metrics are component calibration on EntailmentBank's own distribution — label them a **distribution-shifted proxy**. The human step-validity protocol is the primary decomposition eval.
- SciFact numbers evaluate the **leaf-verification module only**.
- **DecompScore is dropped** — it measures atomization fidelity and penalizes verifiability descent, making it inapplicable to argument decomposition. The mismatch is itself H4b evidence.
- Grounding rate, depth, and budget-exit rate are **first-class metrics**, not diagnostics.

---

## Stack and data sources

**Python / PyTorch / scikit-learn.** v0 surface: Streamlit or CLI. Invalidation layer: **JTMS** (Doyle 1979, `lit-026`) over the alethiology; **ATMS** (de Kleer 1986, `lit-027`) is the model if multiple incompatible evidential contexts must be held simultaneously without committing to one.

Evidence metadata, free APIs only:

| Signal | Source | Notes |
|---|---|---|
| **Retraction status** | OpenAlex `is_retracted`, cross-checked against Crossref `update-to` | The cross-check is required — OpenAlex's boolean collapses update types and has a known false-positive history. OpenAlex needs a free registered key (100k credits/day) as of 2026-02-13; Crossref needs no key |
| **Study design** | PubMed MeSH publication types | RCT / Meta-Analysis / Systematic Review |
| **Citation intent** | Semantic Scholar | Free, coarse 3-class, full-text only. scite is deferred — commercial, and its per-class precision is vendor-reported and independently disputed |
| **Sample size** | ClinicalTrials.gov enrollment (no key required), linked from PubMed | **Structured only for registered trials.** Text-mine elsewhere and label model-extracted — Elicit (`product-028`) is the production precedent |

---

## Working conventions

**Rules for agents** (from [.claude/CLAUDE.md](.claude/CLAUDE.md)):

- Raise a risk only if it has measurable impact on the objective. State it once, in one sentence. Never revisit after Tanner rules on it. No unsolicited ethics commentary.
- Lean, decision-oriented outputs. No filler.
- Do not set arbitrary deadlines or timeframes.
- Do not set arbitrary rules for the project without consulting Tanner first — especially absolute ones with universal quantifiers.

**Model and effort:**

| Work | Model | Effort |
|---|---|---|
| Extraction, transcription, boilerplate | Sonnet 4.6 | Low–medium |
| Synthesis, adjudication, red-teaming, proposal drafting | Strongest available | Max effort, **single context — no subagents** |

**The claims lint.** [CLAIMS.md](CLAIMS.md) is the authority on corrected phrasings. Each `BAN:` line is a literal phrase that must not appear in outward-facing copy; `WHY:` records the falsification and `USE:` gives the replacement. Seventeen phrases are banned, plus one non-literal rule: **any sentence citing VITALITY as evidence that retraction *surfacing works* is banned** — VITALITY evidences impact, RetractoBot bounds uptake, decision-time surfacing is the bet.

Two scope notes carried in `CLAIMS.md` itself: the red-team section of `SYNTHESIS.md` **intentionally preserves flawed phrases as quoted review record** (rewriting them would falsify the review), and `research/raw/` is read-only input.

---

## Recorded verification debts

Open as of pass 7, per [SYNTHESIS.md](research/SYNTHESIS.md):

- **RedacTek (`product-024`) is single-secondary** — sourced from one third-party review; vendor primary documentation never obtained. This row carries the paper-level/claim-level distinction that H7 and the moat argument rest on.
- **Pricing and vendor-accuracy figures are marketing claims** — see the table in [EXTRACTION_NOTES.md](research/matrix/EXTRACTION_NOTES.md).
- **SEER / NLDR / Task-1 successor figures are embargoed** pending primary-source PDF verification. Two specific numbers are banned until verified.
- **Dartmouth/Nyhan DebunkBot replications are reported-unpublished.**
- **Single-pass pass-7 rows** (`product-026`, `-028`, `-029`; `lit-034`) are flagged verify-before-use in their extraction notes.

Discharged: the FEVER citation, `lit-022`/`lit-026`/`lit-027` primary URLs, and arXiv:2509.18403.

---

## Glossary

| Term | Meaning |
|---|---|
| **Alethiology** | The persistent knowledge base of verified facts ("aletheia") with per-fact provenance, confidence, and justification links. Verity's substrate; where leaf verdicts live |
| **Load-bearing premise** | A premise whose removal breaks the entailment. Contrast with an *atomic fact*, which is independently checkable but carries no structural weight |
| **Entailment-linked vs. atomic** | The distinction carrying H1, H6, and the moat argument. Atomic decomposition yields independent facts; entailment-linked decomposition yields a dependency graph the JTMS can propagate along |
| **JTMS** | Justification-based truth maintenance (Doyle 1979). Beliefs are IN or OUT based on justifications; retracting a justification flips every dependent belief OUT |
| **Verdict boundary** | Verdicts only at the leaves; never a root aggregate on a contested composite |
| **Verifiability descent** | Each premise strictly easier to verify than its parent. Terminates by depth budget, not by proof |
| **Budget-exit rate** | Fraction of branches that terminate by hitting the depth budget rather than by grounding. A first-class reported metric |
| **Near-miss** | A product excluded from a hypothesis by exactly one qualifier. Named in copy as demand evidence, not hidden |
| **Bucket 1 / 2 / 3** | Eval maturity tiers: established benchmark / proxy-only / no benchmark exists |

---

## Origin

The research pipeline in this repository was produced for a Wharton Generative AI Studio application, which is why the record is structured as numbered adjudication passes with a frozen schema and an adversarial review. **The application is not a live workstream** — no agent should be producing or maintaining application materials, prompt logs, or submission artifacts. The research record stands on its own as the design substrate for the v0 build.

The record was built under Verity's own evidentiary standards, which is the point: schema-bound extraction with per-cell provenance, hypothesis adjudication that killed several of its own hypotheses, an adversarial review pass that changed no verdicts but found seven defects, targeted existence searches behind the surviving negative claims, and a banned-phrase lint over the claims the record is willing to make.
