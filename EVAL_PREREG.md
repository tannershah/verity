# EVAL_PREREG.md — Pre-registered evaluation floors and falsification lines

**Committed: 2026-08-13 (pass 7), before D1 of the v0 build.** Source: defense
Q20/Q22 as adjudicated by the examining committee. These are pass/fail lines,
not aspirations — failing one is a reportable result, not an embarrassment to
hide. No floor may be revised after D1 except by a logged, dated amendment
stating what was learned that justifies the change.

## Floors (Q20)

1. **Grounding rate ≥ 50%** of branches ground within a depth-3 budget on the
   20-claim beachhead set.
   *Definition (coherence rule, committee Q16):* in v0, "grounds" means the
   branch descends to a citation-shaped premise matched to an alethiology
   metadata fact by **exact key only** (DOI / PMID / NCT). v0's termination
   story is descent into DOI-keyed premises; readers of this number should
   understand it that way.
   *Failure meaning:* verifiability descent fails in practice for current
   retrieval; the thesis pivots to curated-domain alethiologies.

2. **Human-judged step-validity ≥ 80%**, measured by the Q18 protocol
   (30 Verity-generated trees from the beachhead set; every step judged by two
   annotators on (i) entailment holds, (ii) each premise verifiable as written,
   (iii) load-bearing, with ablation spot-checks; disagreements adjudicated;
   report rate with Cohen's κ).
   *Below the floor: no public demo.* A visible structural error in one step of
   five is disqualifying for a tool whose only product is trust.
   *Display consequence (committee note):* 80% per-step implies ~0.8⁵ ≈ 33% of
   five-premise trees are fully clean — consistent with field SOTA — so the UI
   must render per-premise verifier confidence, never tree-level polish alone.
   *Open parameters:* annotator roster (two named annotators; if the builder
   self-annotates, the protocol must disclose it as a bias), pilot N.

3. **Retraction false-flag rate ≤ 5%** on the real-claim linkage eval
   (defense Q21c): ~50 real claims sourced by crossing Retraction Watch with
   public claim corpora (candidate seeds: the Wikipedia retracted-citations
   dataset, arXiv:2509.18403; VITALITY's 4,095 contaminated meta-analyses,
   lit-031), measuring premise-to-retracted-DOI linkage precision/recall and
   the rate of claims wrongly marked retraction-dependent.
   *Failure meaning:* the professional tool is net-harmful — alarm fatigue
   destroys the value proposition the invalidation moat rests on.

## Falsification line — disagreement localization (Q22)

Annotation task design must include a mandated **"does not localize"** label
with worked examples and neutral incentives. Pre-registered line: **if fewer
than 40% of contested items localize to ≤ 2 premises at κ ≥ 0.6, localization
fails as the organizing center** and the discernment endpoint carries the
welfare claim alone. Both endpoints are co-primary regardless — the answer to
endpoint-shopping is to pre-register both, not to swap.

The 40% / κ 0.6 thresholds are stipulative; prereg's value is the timestamp,
not the number. The S4 study design (N=40 reader pairs; within-item,
between-pairs; Verity tree vs. same evidence as flat list; pair-level κ on
disagreement-locus; mixed-effects with item random effects; pilot before power
lock) is recorded in the defense transcript and must be committed here before
the study runs. Prior-art citation obligation: ARGUMEND's "Crux Identification"
(product-027) ships crux-finding editorially; the claimed contribution is
automated, evidence-verified, premise-level localization — not the concept.

## Standing rules

- Every model-produced eval number is paired with a human-anchored calibration
  sample or explicitly labeled *uncalibrated* (Q19).
- EntailmentBank metrics are component calibration on EntailmentBank's own
  distribution, labeled a distribution-shifted proxy; the Q18 human protocol is
  the primary decomposition eval (Q18).
- SciFact numbers evaluate the leaf-verification module only (Q21b).
- DecompScore is inapplicable to argument decomposition (measures atomization
  fidelity; penalizes verifiability descent) — dropped, with the mismatch
  stated as H4b evidence (Q21a).
- The retraction-injection test is a regression test of our own code, not a
  contribution; the linkage eval above is the field-facing contribution (Q21c).
