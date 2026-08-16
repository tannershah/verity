# Differentiation Hypotheses

What we claim is missing from the landscape, and the evidence behind each claim.

Every negative claim is a **search bound, not a proof of nonexistence**: two deep-research sweeps over the landscape plus targeted existence searches, all as of **August 2026**. Each hypothesis below carries the candidates that were actually evaluated and why each was rejected. A claim without that table is unsupported.

Evidence rows are cited by ID (`product-009`, `lit-005`) — see [research/matrix/](../research/matrix/README.md).

---

## Summary

| # | Claim | Status |
|---|---|---|
| H1 | No consumer product auto-decomposes claims into entailment-linked load-bearing premises with per-premise evidence | holds |
| H2 | scite has no argument-structure layer above citations | holds |
| H3 | No **automated** system offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim | holds |
| H4a | Entailment-step validity has no standard benchmark | **false** — EntailmentBank exists |
| H4b | No gold benchmark for entailment-preserving decomposition faithfulness | holds (proxy-only) |
| H4c | No evaluation exists for decomposition of contested real-world claims | holds |
| H5 | The belief-updating line is productized only as **persuasion**, not self-serve symmetric inspection | holds |
| H6 | No system combines argument-structure decomposition with evidence-quality metadata | holds |
| H7 | No product does **claim-level** dependency-propagated invalidation | holds |

H3 and H5 are narrower than first stated — both original formulations were falsified and are recorded below, because how they failed constrains how the current versions should be read. H4 could not be answered as one question and splits three ways.

---

## H1 — Consumer premise decomposition

**Claim.** No consumer product auto-decomposes claims into entailment-linked load-bearing premises with per-premise evidence. Three conjuncts: *consumer packaging* + *entailment-linked decomposition* + *per-premise evidence*.

**Closest system.** Loki / Libr-AI OpenFactVerification (`product-009`) — automatic decomposition with per-claim evidence in a UI. Excluded because it decomposes into **independent atomic claims** rather than entailment-linked premises; it is journalist/researcher-facing; and it ultimately produces a verdict.

**Candidates evaluated** — query: `consumer fact-checking tool entailment premise decomposition evidence 2025 2026`

| Candidate | Why not a counterexample |
|---|---|
| PrimeFacts (arXiv:2605.06006) | Academic pipeline for building premise-level evidence resources from PolitiFact articles; not a deployed product |
| SIFT (arXiv:2502.10855) | Research prototype decomposing claims into 5W1H spans via NLI; no consumer deployment |
| HallDetect | Hallucination detection for LLM pipelines, not consumer claim-checking |
| DyDecomp / DAD | RL-based decomposition optimization; academic, no deployment |
| FEVER9 shared task | Academic benchmark |

**Weakness worth carrying.** Of the three conjuncts, "consumer" is not a field in the extraction schema at all and the boundary is a judgment call; the verdict qualifier had to be added to Loki's row after the fact. That leaves the atomic-vs-entailment distinction carrying most of the weight. H1 should never be presented as load-bearing alone — it is one conjunct of the [positioning](positioning.md) argument.

**Falsified by.** A consumer product shipping recursive premise decomposition with per-premise evidence.

---

## H2 — scite has no argument layer

**Claim.** scite operates at the citation statement and builds no premise or argument graph above it.

**Evidence.** scite.ai (`product-002`) and scite Reference Check (`product-020`) both code `unit_of_analysis: citation` and `claim_decomposition: none`, verified against primary feature pages. The full surface — Smart Citations (Supporting / Contrasting / Mentioning), Reports, Reference Check, Collections, Assistant, MCP integration — contains no argument layer.

**Candidates evaluated** — query: `scite.ai argument structure claim decomposition premise 2025 2026`

| Candidate | Why not a counterexample |
|---|---|
| scite Smart Citations (2025–26 reviews) | Citation-level classification only; no argument structure in any source |
| scite Assistant | Chat wrapper over citation data; no structural decomposition |

**Falsified by.** scite shipping a premise or argument graph over claims.

---

## H3 — Symmetric transparency at the premise level

**Current claim:**

> **No automated system offers symmetric transparency-only inspection at the decomposed-premise level of a composite claim.**

**The original version was false.** As first stated — "no checker offers symmetric transparency-only inspection as core product" — it is falsified outright by Ground News (`product-001`), whose core product *is* symmetric left/center/right comparison with explicit no-adjudication positioning. Penn Media Bias Detector (`product-004`) and scite are further counterexamples at article and citation level. Symmetric no-verdict presentation is not novel; **doing it below the article level is.**

**One qualifier — *automated* — and only one.** A second qualifier ("user-submitted composite claim") was considered and dropped: it was forced only by ARGUMEND, which is excluded on the transparency-only term anyway. Adding conjuncts until a cell empties is how a whitespace claim becomes indefensible; if a new counterexample forces a third qualifier, that is a signal to abandon the claim rather than narrow it again.

**Candidates evaluated** — six queries spanning symmetric inspection, argument mapping, both-sides tooling, deliberation technology, and Product Hunt launches

| Candidate | Why not a counterexample |
|---|---|
| Consensus (`product-025`) | Renders a root-level stance aggregate over an atomically treated question; no premise decomposition |
| ARGUMEND (`product-027`) | Curated maps carry a root-level verdict axis ("Balance shows which way the evidence tips"). Its Analyze mode accepts pasted text but performs local document argument-mining, not claim decomposition with external evidence retrieval |
| The Society Library (`product-026`) | Multi-level argument maps with evidence links — **human-curated**; deployment partial |
| Kialo (`product-019`) | Fully deployed, symmetric, no-verdict, premise-structured — and entirely community-authored, no evidence-quality metadata |
| Symbai | Debate-training product; AI argues a selected position against the user (adversarial), not symmetric inspection |
| TruthSplit (arXiv:2606.09251) | Research preprint on conditional validity via worldview-specific NLI; not deployed |

**Prior-art obligation.** ARGUMEND's **"Crux Identification"** ships the disagreement-localization concept editorially. Any claim to that contribution must cite it and claim only what is new: *automated, evidence-verified, premise-level* localization.

**Falsified by.** Any automated system rendering symmetric, no-verdict, decomposed-premise inspection.

---

## H4 — Decomposition benchmarks

One verdict cannot represent this honestly. All three facets must appear wherever it is discussed.

### H4a — entailment-step validity: **FALSE**

EntailmentBank (`lit-001`) is an established four-metric benchmark — Leaves (F1, AllCorrect), Steps, Intermediates, Overall-AllCorrect — with a mature method line: METGEN (`lit-002`), IRGR (`lit-003`), RLET (`lit-004`), NLProofS (`lit-005`).

**Never claim step-validity benchmarks are missing. Adopt EntailmentBank's metrics directly.**

### H4b — decomposition faithfulness: holds, proxy-only

No gold benchmark exists for *entailment-preserving* decomposition. Gold benchmarks exist only for atomic-claim identification.

**Candidates evaluated** — query: `claim decomposition faithfulness benchmark gold standard evaluation 2025 2026`

| Candidate | Why not a counterexample |
|---|---|
| CACDD (Zhang et al. 2025, `lit-029`) | Tests atomic-claim identification, Chinese/WebCPM context only; not joint sufficiency or load-bearing structure |
| FactLens (Mitra et al. 2025, `lit-030`) | Fine-grained sub-claim verification; sub-claims are independent units, not load-bearing premises |
| FAITHCOT-BENCH (arXiv:2510.04040) | Benchmarks chain-of-thought faithfulness, a different target |
| DecMetrics (Huang 2025) | NLI-based metric proposal, not a human-annotated gold corpus |
| DnDScore (arXiv:2412.13175) | Factuality benchmark for atomic claims, not entailment-preservation |

Wanner et al. (`lit-013`) showed FActScore is sensitive to the decomposition method itself and introduced DecompScore precisely because no gold standard exists; DnDScore (`lit-014`) confirms factuality scores are unstable across decomposition and decontextualization strategies.

**Consequence:** DecompScore is **dropped from our eval** — it measures atomization fidelity and penalizes verifiability descent. The mismatch is itself evidence for H4b. See [evaluation.md](evaluation.md).

### H4c — contested-claim decomposition: holds

No evaluation exists at all. The nearest neighbour, AVeriTeC's Conflicting Evidence / Cherry-picking class (`lit-017`), is a *verdict class*, not a decomposition eval — and is the field's worst-performing class, near-zero F1 for most systems at under 7% of training data.

**Candidates evaluated** — query: `contested claim decomposition entailment benchmark evaluation 2025 2026`

| Candidate | Why not a counterexample |
|---|---|
| "Does Claim Decomposition Boost or Burden Fact-Checking?" (NAACL 2025) | Evaluates decomposition utility for verdict accuracy, not contested premise structures |
| CREDENCE (arXiv:2606.19819) | Semantic convergence metrics for decomposition; not contested-claim specific |
| "A Closer Look at Claim Decomposition" (ACL 2024) | General decomposition analysis on fact-checking datasets |
| Warrant Gap / SIFT (arXiv:2606.24627) | Warrant retrieval and scoring; not a premise structure benchmark |

This is a build opportunity, not just a gap — see [evaluation.md](evaluation.md).

---

## H5 — Belief updating is productized only as persuasion

**Current claim:**

> **The belief-updating line is productized only as persuasion — verdict-shaped counterarguments — not as self-serve symmetric inspection.**

**The original version was false, and how it failed matters.** As first stated — "the DebunkBot line is not productized as a self-serve tool" — it was killed instantly by debunkbot.com, a live self-serve deployment announced in *MIT Technology Review* ten months earlier. Neither deep-research sweep had queried for consumer deployments. **That is a measured failure rate for landscape sweeps**, and the reason every other negative claim here now carries its own targeted search table.

**Candidates evaluated** — seven queries spanning street epistemology, Socratic questioning apps, reflective-thinking coaches, and belief-examination products

| Candidate | Why not a counterexample |
|---|---|
| debunkbot.com | Confirms the persuasion pole: fine-tuned to issue counterarguments against the user's stated belief. Explicitly verdict-shaped |
| Meyer et al. 2024 (`lit-032`) | Research study, N=2,036 — chatbot prompts reflection on uncertainty. Not a deployed product |
| Belief Explorer (`lit-034`, CHI 2026) | Research prototype: Socratic interface + multi-perspective analysis. **Closest design match; if productized, this claim dies** |
| Reflection.app | Deployed AI journaling/coaching; general reflection, not claim-against-evidence inspection |
| Socra | Deployed Socratic tutoring platform; knowledge acquisition, not belief inspection |
| TITAN Socratic prototype (ACM IMX 2024) | Research prototype |

**Research-line concession, carried affirmatively.** The reflection paradigm already exists *in research*: Meyer et al. is an independent **conceptual** replication in the reflection direction, zero author overlap — the closest empirical support on record for Verity's mechanism, with a high-predisposition null as the honest audience boundary. Cite it as conceptual, never as a direct replication.

Citation discipline for this whole line is in [positioning.md](positioning.md) §6.

**Falsified by.** Belief Explorer or the Meyer paradigm commercializing.

---

## H6 — Decomposition × evidence-quality metadata

**Claim.** No system combines argument-structure decomposition with evidence-quality metadata.

**Closest system.** Loki (`product-009`) — automatic but *atomic* decomposition, at *source-level* metadata. One level short on both axes.

**Evidence by enumeration.** Rows with any decomposition: Loki, SAFE, FActScore (automatic, all atomic, source-level or below) and Kialo (manual argument graphs, no evidence metadata). Rows with `study-level` metadata: `product-002`, `product-020`–`024` — **every one** codes `claim_decomposition: none`. All entailment-tree systems (`lit-001`–`lit-009`) assume leaves true with no evidence-quality metadata.

**Candidates evaluated** — query: `fact checking argument decomposition study design metadata evidence quality system 2025 2026`

| Candidate | Why not a counterexample |
|---|---|
| Cabrio et al. 2025, "When automated fact-checking meets argumentation" | Uses argument structure for verdict classification; no evidence-quality metadata layer |
| ProgramFC / SAFE variants | Sub-question decomposition and retrieval; no structured evidence-quality metadata |
| Speaker / KG metadata approaches | Claimant provenance, not evidence quality of supporting studies |

**Falsified by.** Any decomposing system attaching study-design, retraction, or sample-size metadata per premise.

---

## H7 — Claim-level dependency-propagated invalidation

**Claim.** No product performs claim-level dependency-propagated invalidation. This is the hardest technical differentiator in the [positioning](positioning.md).

**Closest system.** RedacTek (`product-024`) — genuine multi-hop propagation of a paper-level "issue association value" across three citation generations. It propagates **paper-level suspicion scores**, not claim-level invalidation of downstream conclusions. That gap is the load-bearing distinction.

⚠ **This rests on the weakest row in the matrix.** `product-024` is sourced entirely from one third-party review; vendor primary documentation was never obtained. If that review under-describes the product, H7 weakens in the direction most damaging to the positioning. Tracked in [open-questions.md](open-questions.md).

**Evidence.** Every other shipping retraction tool is direct-status or 1-hop: scite Reference Check (direct-status only), Zotero + Retraction Watch (one hop, no propagation), RetractoBot (1-hop emails), RetractionCheck / Crossref API (federated lookup only). The only paradigm doing true dependency-directed retraction — truth maintenance systems (`lit-026` JTMS, `lit-027` ATMS) — has never been applied to scholarly retractions.

**Candidates evaluated** — query: `retraction claim dependency propagation invalidation fact checking system 2025 2026`

| Candidate | Why not a counterexample |
|---|---|
| RedacTek (`product-024`) | Paper-level propagation across three citation generations; no claim-level logical dependency |
| ConvMemory v3 (arXiv:2606.26753) | Validity propagation over dependency graphs for conversational memory, not scientific retraction |
| Cochrane / CENTRAL retraction flagging | Flags retracted papers in systematic reviews at paper level; no claim-level graph |
| Plato's Cave (arXiv:2603.23526) | Human-centered research verification; no claim-level dependency propagation |

**Falsified by.** RedacTek or scite adding claim-level propagation.
