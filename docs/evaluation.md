# Evaluation

What we measure, with what, and against which thresholds.

---

## 1. Validity criteria → concrete evals

| Criterion | Meaning | Eval | Anchors |
|---|---|---|---|
| **Joint sufficiency** | Premises jointly entail the claim | EntailmentBank Steps / Overall-AllCorrect on generated trees, plus a learned verifier scoring every step — also used as an inference-time gate | `lit-001`, `lit-005` |
| **Verifiability descent** | Each premise strictly easier to verify; termination enforced by depth budget | Termination tests against the alethiology: % of branches grounding in a KB fact within budget; mean/max depth; budget-exit rate. NELLIE's ground-or-recurse pattern is the model | `lit-009` |
| **Non-redundancy** | Every premise load-bearing | Leave-one-out ablation: removing any premise must drop verifier entailment confidence below threshold | `lit-013` |

Grounding rate, depth, and budget-exit rate are **reported metrics, not internal diagnostics**. A procedure with guaranteed termination has no budget-exit rate; ours does, and publishing it is the honest form of the termination claim.

---

## 2. Thresholds

Pass/fail lines, set before the build starts so they can't be moved to fit results. Failing one is a result to report, not a problem to hide. Revising one requires stating what was learned that justifies the change.

### Grounding rate ≥ 50%

Of branches grounding within a depth-3 budget on the 20-claim beachhead set.

**"Grounds" means** the branch descends to a citation-shaped premise matched to an alethiology fact by **exact key only** — DOI, PMID, or NCT. Fuzzy matching would silently inflate this number; keep exact-key matching separate from any later similarity layer.

**If it fails:** verifiability descent doesn't work for current retrieval, and the approach pivots to curated-domain alethiologies.

### Human-judged step validity ≥ 80%

30 generated trees from the beachhead set. Every step judged by two annotators on (i) entailment holds, (ii) premise verifiable as written, (iii) load-bearing — with ablation spot-checks, disagreements adjudicated, and Cohen's κ reported.

**Below this floor, no public demo.** A visible structural error in one step of five is disqualifying for a tool whose only product is trust.

**Open:** annotator roster and pilot N. If the builder self-annotates, the protocol must disclose it as a bias.

### Retraction false-flag rate ≤ 5%

On the real-claim linkage eval: ~50 real claims sourced by crossing Retraction Watch against public claim corpora, measuring premise-to-retracted-DOI linkage precision and recall, and the rate of claims wrongly marked retraction-dependent.

Candidate seed corpora: the Wikipedia retracted-citations dataset (arXiv:2509.18403) and VITALITY's 4,095 contaminated meta-analyses (`lit-031`).

**If it fails:** the tool is net-harmful. Alarm fatigue destroys the value proposition the invalidation differentiator rests on.

### Disagreement localization ≥ 40% at κ ≥ 0.6

Of contested items localizing to ≤ 2 premises. The annotation task must include a mandated **"does not localize"** label with worked examples and neutral incentives, or the measurement is rigged.

**If it fails:** localization is not the organizing idea, and the discernment endpoint carries the welfare claim alone. Both endpoints are treated as co-primary regardless — the answer to endpoint-shopping is to commit to both up front, not to swap after seeing results.

The 40% / κ 0.6 numbers are stipulative. Their value is being fixed in advance, not their precision.

**Study design** (to be committed before the study runs): N=40 reader pairs; within-item, between-pairs; Verity tree vs. the same evidence as a flat list; pair-level κ on disagreement locus; mixed-effects with item random effects; pilot before locking power.

---

## 3. Established benchmarks — run first, report comparable numbers

**Leaf verification** — this evaluates the leaf module only, consistent with the verdict boundary:

| Benchmark | Row | Why |
|---|---|---|
| SciFact | `lit-016` | Biomedical — matches the beachhead |
| FEVER | `lit-015` | Scale |
| AVeriTeC | `lit-017` | Real-world claims |

**Entailment-step validity** — EntailmentBank's four-metric suite (`lit-001`), with NLProofS (`lit-005`) the baseline to beat or adopt: Task 2 Overall-AllCorrect **20.9% → 33.3%** in-paper (released checkpoint reports 34.4%), Leaves-AllCorrect 35.6% → 58.8%, achieved with T5-large. Strongest baseline in the same table is EntailmentWriter T5-11B at 25.6%.

Successor figures (SEER, NLDR, Task-1 bests) were never verified against primary PDFs — don't quote them until they are.

**Reference bands must carry their metric.** 2024 and 2025 AVeriTeC scores use different formulas and are **not comparable**:

- 2024 (Hungarian METEOR): top 63%, AIC CTU 50.4%
- 2025 (Ev2R): top 0.332, HerO 2 at 0.271, baseline 0.202

**Field context, stated plainly:** in the friendliest available setting — curated science claims with gold plus distractor leaves handed over — the best method line tops out at 33.3% Overall-AllCorrect. Two-thirds of trees contain at least one structural error when the true leaves are provided. Verity's setting is harder on every axis: open retrieval, contested claims, recursive depth, a moving KB.

---

## 4. Proxy-only — report proxies as proxies

- **Decomposition faithfulness** — entailment coverage, and the **sensitivity of downstream verdicts to decomposition strategy reported as a first-class number** (`lit-014`).
- **Non-redundancy** — leave-one-out ablation.
- **LLM annotation of premises and bias** — sampled human agreement + downstream classification + expert construct-validity checks, following the Penn Media Bias Detector template (`lit-019`): RA audits of a random label sample, comparison against expert raters, explicit refusal to score against "truth."
- **Evidence-quality tagging** — Semantic Scholar citation intent (free, coarse 3-class) with accuracy caveats. scite deferred: commercial, and its per-class precision is vendor-reported and independently disputed (`lit-028`).

**DecompScore is dropped** — it measures atomization fidelity and penalizes verifiability descent, so it is inapplicable to argument decomposition. The mismatch is stated as evidence for H4b rather than hidden as a tooling choice.

---

## 5. No benchmark exists — design new

### Contested-claim decomposition

Extend AVeriTeC's Conflicting Evidence / Cherry-picking cases (`lit-017` — under 7% of training data, near-zero F1 for most systems) into **entailment-tree annotations where the contest localizes to identifiable premises**. Publishable in its own right, and it is the eval H4c says does not exist.

### Invalidation propagation

**The real-claim linkage eval is the contribution** (§2). Synthetic retraction-injection over the JTMS — retract a leaf, assert every dependent premise flips OUT and every affected graph re-renders flagged — is a **regression test of our own code, not a research result.** Necessary, and not to be presented as a contribution. Nearest neighbours for test design: NELL belief demotion (`lit-025`), Wikidata deprecated-rank handling.

### Transparency-only presentation quality — open

No empirical support exists on either side for whether symmetric no-verdict presentation helps or hurts. Roadmap, not v0: adapt the belief-updating paradigm to measure **discernment and calibration**, not persuasion — since Verity deliberately does not persuade, and belief shifts from AI dialogue build no lasting discernment skills (`lit-023`).

---

## 6. Standing rules

- Every model-produced number is paired with a human-anchored calibration sample, or is explicitly labeled **uncalibrated**.
- EntailmentBank metrics are component calibration on EntailmentBank's own distribution — a **distribution-shifted proxy**. The human step-validity protocol is the primary decomposition eval.
- SciFact numbers evaluate the leaf-verification module only.
- **No silent caps.** If coverage is bounded — top-N, sampling, no-retry — say what was dropped.

---

## 7. Display consequence — binds the UI, not just the eval

80% per-step validity implies ~0.8⁵ ≈ **33% of five-premise trees are fully clean.** That is consistent with field SOTA and is not a reason to lower the threshold.

It *is* a hard constraint on rendering: **the UI must show per-premise verifier confidence, never tree-level polish alone.** A clean-looking tree hiding one bad step is exactly the failure this project cannot afford. See [design.md](design.md).
