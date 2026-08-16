# Design

What Verity is and what we are building.

Sections are marked **SETTLED** (decided), **PROPOSED** (a sketch to build from, not yet ruled on), or **OPEN** (tracked in [open-questions.md](open-questions.md)).

## 1. Thesis — SETTLED

An **epistemic transparency engine**. Input: text containing claims.

Verity recursively decomposes each claim into its load-bearing premises, checks those premises against a persistent store of verified facts, retrieves evidence for the ones it doesn't know, attaches evidence-quality metadata to every premise, and renders the result as an inspectable graph — **never as a verdict on the composite claim**.

A reader confronting "X causes Y" should be able to see *which premises the claim stands on*, *how strong the evidence under each one is*, and *whether a load-bearing source has been retracted*.

**Beachhead: scientific and health claims. News is roadmap.** Rationale in [positioning.md](positioning.md) §4.

---

## 2. Pipeline — SETTLED

```
claim
  └─▶ backward-chaining decomposition ──▶ 3–7 load-bearing premises
        │                                   verifier gate scores every step
        ├─▶ premise known?  ──yes──▶ alethiology (persistent verified-fact KB)
        │                    ──no───▶ agentic retrieval (OpenAlex · Crossref · PubMed · Semantic Scholar)
        ├─▶ evidence-quality metadata attached per premise
        ├─▶ JTMS: retract a leaf ──▶ dependents flip OUT ──▶ affected graphs re-render flagged
        └─▶ render: per-premise confidence · symmetric evidence on contested premises · no root aggregate
```

Recursion terminates by **depth budget**, not by assumption. A branch that exhausts verifiability descent surfaces as an **unverified premise with its symmetric evidence attached** — on contested material that is the intended output, not a failure mode.

---

## 3. Hard constraints — SETTLED

Code or copy that violates these is wrong.

### 3.1 The verdict boundary

**Verdicts exist only at the leaves** — verified premises in the alethiology. Contested composite claims get transparency-only treatment: surface the evidence and critiques on all sides, adjudicate nothing. **No root aggregate is ever displayed.**

**The known gotcha, carried deliberately.** Joint sufficiency plus all-leaves-verified mechanically *implies* a composite verdict: the system possesses one and declines to render it. So on fully resolvable claims the no-verdict posture is presentational, and on contested claims there are no leaf verdicts to withhold. The design survives because the substantive commitment is narrower and sharper:

> **No editorial adjudication where evidence conflicts.**

Pin the boundary to conflicting-evidence states in all copy. Rendering per-premise confidence only, never a root aggregate, is what enforces it in code.

### 3.2 Decomposition validity criteria

| Criterion | Meaning | Enforced by |
|---|---|---|
| **Joint sufficiency** | Premises jointly entail the claim | Learned verifier scores every step; also an inference-time gate |
| **Verifiability descent** | Each premise strictly easier to verify | Depth budget; grounding rate / depth / budget-exit rate measured and reported |
| **Non-redundancy** | Every premise load-bearing | Leave-one-out ablation must drop verifier confidence below threshold |

**Termination is enforced, not guaranteed.** Never write wording that upgrades it to a guarantee — the eval reports a budget-exit rate precisely because branches do exit by budget.

### 3.3 Demo-claim valence rule

Demo and example claims use **verifiable, low-valence cases**: viral statistics, retracted-but-still-cited papers, manipulated charts. Contested scientific and political claims are **roadmap stress tests only**.

### 3.4 Display constraint

**The UI must render per-premise verifier confidence, never tree-level polish alone.** At the 80% per-step floor, only ~33% of five-premise trees are fully clean; a polished tree hiding one bad step is the failure mode this project cannot afford. See [evaluation.md](evaluation.md) §6.

---

## 4. Data model — PROPOSED

⚠ **Not ruled on. This is a starting sketch for D2, not a decision.** The alethiology schema is the single most consequential unbuilt thing in the project.

### 4.1 Alethiology fact record

A verified fact, addressable and provenance-carrying:

```
fact
  id                 stable internal id
  statement          natural-language proposition
  key                exact external key — DOI | PMID | NCT     ← grounding depends on this
  provenance[]       {source_url, accessed, confidence_tier}
  evidence_quality   { retraction_status, study_design, citation_intent, sample_size }
  status             IN | OUT                                   ← maintained by the JTMS
  justifications[]   → justification ids
```

**The `key` field is load-bearing.** The grounding-rate threshold defines "grounds" as descent to a citation-shaped premise matched to an alethiology fact **by exact key only** (DOI / PMID / NCT). Fuzzy matching would silently inflate the headline metric. Keep exact-key matching separate from any later similarity layer.

**Confidence tiers.** The research matrix used `verified | inferred | marketing-claim`, which proved too coarse — it conflates verified-against-primary with corroborated-by-one-secondary. The alethiology should encode the finer vocabulary natively: **verified-primary / corroborated-multi-secondary / single-secondary / inferred / marketing-claim**.

### 4.2 JTMS layer

Following Doyle 1979 (`lit-026`):

```
justification    { consequent: fact_id, antecedents: [fact_id], type }
node status      IN if some justification has all antecedents IN; else OUT
retract(fact)    mark OUT → propagate → re-render every affected claim graph flagged
```

ATMS (`lit-027`) is the model **if** we need to hold multiple incompatible evidential contexts simultaneously without committing to one — the natural fit for contested claims. **OPEN:** whether v0 needs ATMS or JTMS suffices. Start with JTMS; the eval that would force the question is contested-claim rendering.

**Non-monotonic grounding is a real consequence, not an edge case.** Every terminating system in the matrix grounds in a fixed curated corpus. Ours can flip: a tree that terminated yesterday can be un-grounded today. Grounding results must therefore be timestamped and re-validated, not cached as permanent.

### 4.3 Claim graph

```
node    claim | premise | fact
edge    entails (premise → parent), justified-by (fact → premise)
per-node: verifier confidence, evidence-quality summary, status, depth
```

Rendering reads confidence per node. **There is no root-aggregate field** — the absence is the enforcement.

---

## 5. Evidence layer — SETTLED (sources) / PROPOSED (contracts)

Free APIs only for v0.

| Signal | Source | Contract notes |
|---|---|---|
| **Retraction status** | OpenAlex `is_retracted`, **cross-checked against** Crossref `update-to` | The cross-check is required, not optional: OpenAlex's boolean collapses correction / EoC / retraction and has a known false-positive history. OpenAlex needs a free registered key (100k credits/day) as of 2026-02-13; Crossref needs no key |
| **Study design** | PubMed MeSH publication types | RCT / Meta-Analysis / Systematic Review. A free structured field — this is why the beachhead is scientific claims |
| **Citation intent** | Semantic Scholar Graph API | Free, coarse 3-class, full-text papers only. **scite deferred** — commercial, and its per-class precision is vendor-reported and independently disputed |
| **Sample size** | ClinicalTrials.gov enrollment (no key), linked from PubMed | **Structured only for registered trials.** Text-mine elsewhere and label model-extracted. Elicit (`product-028`) is the production precedent |

**Every extracted field carries its confidence tier and provenance into the fact record.** A text-mined N and a registry N must not be indistinguishable downstream.

---

## 6. Build plan — SETTLED

Eight work packages. Target: `claim → 3–7 premises → evidence → per-premise confidence`, Streamlit or CLI.

| | Package | Produces |
|---|---|---|
| **D1** | Decomposition harness — backward chaining to 3–7 premises; verifier check for joint sufficiency | The core loop |
| **D2** | Alethiology schema — facts + provenance + confidence + justification links; seed with demo-domain facts | §4.1 becomes real; split this file |
| **D3** | Retrieval agent for unknown premises — OpenAlex / Crossref / PubMed / Semantic Scholar clients | §5 contracts become real |
| **D4** | Evidence-quality layer — retraction cross-check, MeSH study design, citation intent, sample size | Per-premise metadata |
| **D5** | JTMS invalidation + retraction-injection demo | §4.2 becomes real |
| **D6** | Per-premise confidence + inspectable claim-graph rendering (Streamlit) | §4.3 + §3.4 |
| **D7** | Eval harness — EntailmentBank step-metric sample, leave-one-out ablation, termination stats; two demo claims | Bucket 1/2 numbers |
| **D8** | Polish; run logs | — |

**Unresolved before D1:** conflicted-state semantics, binarization intermediates, annotator roster. Tracked in [open-questions.md](open-questions.md); conflicted-state semantics is the one to settle first.

**Two design pressures to hold in mind from D2 onward:**
1. The alethiology **starts empty** and is populated by the system's own least-validated outputs (agentic retrieval + free-API metadata). NELL (`lit-025`) is the cautionary tale: semantic drift, "mitigated but not solved."
2. Grounding is **non-monotonic** under JTMS (§4.2).

---

## 7. Stack — SETTLED

Python / PyTorch / scikit-learn. v0 surface: Streamlit or CLI. Invalidation: JTMS over the alethiology.

---

## 8. Where the rest lives

| Question | Document |
|---|---|
| What do we believe about the competitive landscape? | [hypotheses.md](hypotheses.md) |
| How do we position and cite? | [positioning.md](positioning.md) |
| How do we measure it? | [evaluation.md](evaluation.md) |
| What's undecided? | [open-questions.md](open-questions.md) |
| What's the evidence? | [research/matrix/](../research/matrix/README.md) |
