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

## 4. Data model — SETTLED

The record shapes below are the ones the spine implements. What remains consequential and unbuilt is not the fact record's fields but the **policy governing what enters it** — promotion, tier assignment, dedup, and the drift audit, all owned by M5.

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

Keys are stored canonicalized, and canonicalization is the boundary of what exact-key matching tolerates: case-folding, whitespace, a closed set of known URI and label prefixes, and the debris an identifier collects in transit — sentence punctuation, unmatched wrapping brackets, zero-width characters, and the query or fragment of a URL it was lifted from. So `10.3823/1654`, `https://doi.org/10.3823/1654`, and `(10.3823/1654).` are one key, while a DOI that legitimately contains balanced brackets keeps them. The transform is total, deterministic, and syntactic — it contains no edit distance or token overlap, and admits none. Without it the grounding rate is silently *deflated* and retraction linkage misses; with anything fuzzier both move the other way.

**Confidence tiers.** The research matrix used `verified | inferred | marketing-claim`, which proved too coarse — it conflates verified-against-primary with corroborated-by-one-secondary. The alethiology should encode the finer vocabulary natively: **verified-primary / corroborated-multi-secondary / single-secondary / inferred / marketing-claim**.

### 4.2 JTMS layer

Following Doyle 1979 (`lit-026`):

```
justification    { consequent: fact_id, antecedents: [fact_id], type }
node status      IN if some justification has all antecedents IN; else OUT
retract(fact)    mark OUT → propagate → re-render every affected claim graph flagged
```

**Conflicted-state semantics — SETTLED.** Two orthogonal axes. The JTMS carries structural support only (IN/OUT). A per-premise **evidence state** — `verified | contested | unverified` — is computed alongside it:

- `verified` requires exact-key grounding in an alethiology fact that is IN — never derived from retrieved-evidence bundles;
- `contested` is cut mechanically: at least one evidence item on each side above a pre-registered stance-score floor — no judgment call in the cut;
- `unverified` covers everything else, including bundle-supported-but-ungrounded premises (rendered *with* their evidence) and budget exits.

Contested premises **never enter the JTMS as justifications** and render symmetrically, verdict-free — the verdict boundary as a type distinction, not a convention.

**JTMS suffices for v0 — SETTLED.** Contested states never enter the TMS, so multi-context maintenance is not required. ATMS (`lit-027`) is revisited only if a later need forces holding incompatible evidential contexts simultaneously.

**Non-monotonic grounding is a real consequence, not an edge case.** Every terminating system in the matrix grounds in a fixed curated corpus. Ours can flip: a tree that terminated yesterday can be un-grounded today. Grounding results must therefore be timestamped and re-validated, not cached as permanent — which is why the render projection reads the alethiology rather than the graph's stored grounding row (§4.3).

**A fact's (key, statement) pair is immutable.** Identity is that pair, so editing a statement in place would change what the fact *is* while every justification that named it kept pointing at the old identity. A correction is therefore a new fact asserted and the old one flipped OUT — which is the JTMS's own idiom for a belief that stopped holding, and keeps the invalidation record intact instead of erasing it.

### 4.3 Claim graph

```
node      claim | premise | fact
edge      entails (premise → parent), justified-by (fact → premise)
per-step  verifier confidence, leave-one-out ablation delta per premise,
          descent depth
per-node  evidence-quality summary, evidence state, termination reason,
          grounding key (premises)
derived   traversal depth
```

Entailment steps are **native n-ary — SETTLED**: 3–7 premises per step, no binarization into 2-premise intermediates. The verifier scores the n-ary step and leave-one-out ablation operates on it, matching EntailmentBank's step convention. A step's identity is its conclusion and the *set* of its premises, so re-ordering a decomposition does not produce a second step.

**Confidence attaches to the step, not the node — SETTLED**, and so does everything else the verifier measures. The verifier answers "do these premises jointly entail this conclusion", so that is the only place a verifier score exists. Neither a claim nor a premise carries a confidence field, because nothing computes one. What §3.4 requires the UI to render *per premise* is assembled from three parts, each read against one step: the step's score, the premise's leave-one-out ablation delta within that step, and its evidence state. A step score is scoped to its own step and is never composed with another — which is what keeps the root step's score an entailment measurement rather than a verdict on the claim.

**The graph is a DAG, and the display is over edges.** Two branches that reach the same premise reach the same node: identity is the statement. Such a premise carries a score and an ablation delta per step it belongs to, and renders once under each — a value stored on the node would belong to whichever producer ran last, and would be shown beside a step the reader is not looking at.

**Depth is two numbers, and they are not interchangeable.** *Traversal depth* is where a node sits in the graph as it stands; it is derived, never stored, which is what keeps the reported depth and the rendered depth the same number. *Descent depth* is how far the decomposer had gone when it built a step, and it is recorded on the step because nothing can recover it afterwards: deduplicating premises by statement can leave a node reachable by a shorter route than the one that reached it. The budget is enforced along the descent and `budget-exit` fires there, so **the depth reported beside the budget-exit rate is the recorded one** — measuring depth off the shortened graph would put the two metrics over two different objects. A run that recorded no descent depth reports that it has none.

**There is no root-aggregate field** — the absence is the enforcement. Renderers consume a projection of the graph that exposes per-premise rows and the claim's text, and nothing above them. That projection reads the alethiology as well as the graph: a recorded grounding is what a run concluded, and whether it still holds is a question only the fact store can answer (§4.2). Both readings reach the row, because the difference between them is the invalidation result.

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

The engineering decomposition of these packages — ten modules, session-sized tiers,
and the build ordering — is in [build-plan.md](build-plan.md).

**Unresolved before D7:** the second annotator for the step-validity protocol. Tracked in [open-questions.md](open-questions.md).

**Two design pressures to hold in mind from D2 onward:**
1. The alethiology **starts empty** and is populated by the system's own least-validated outputs (agentic retrieval + free-API metadata). NELL (`lit-025`) is the cautionary tale: semantic drift, "mitigated but not solved."
2. Grounding is **non-monotonic** under JTMS (§4.2).

---

## 7. Stack — SETTLED

Python 3.12 / PyTorch / scikit-learn. v0 surface: CLI first, then Streamlit ([build-plan.md](build-plan.md) M9). Claim-side LLM calls go through a provider-agnostic adapter with the Claude API as the default backend; NLI and embedding models run locally (Hugging Face checkpoints). Invalidation: JTMS over the alethiology.

---

## 8. Where the rest lives

| Question | Document |
|---|---|
| How do we build it, session by session? | [build-plan.md](build-plan.md) |
| What do we believe about the competitive landscape? | [hypotheses.md](hypotheses.md) |
| How do we position and cite? | [positioning.md](positioning.md) |
| How do we measure it? | [evaluation.md](evaluation.md) |
| What's undecided? | [open-questions.md](open-questions.md) |
| What's the evidence? | [research/matrix/](../research/matrix/README.md) |
