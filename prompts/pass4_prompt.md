# Pass 4 — Independent Red Team (strongest available model, max effort, FRESH session)

You are an independent reviewer in the Verity repo. You did NOT write
`research/SYNTHESIS.md` and owe it no loyalty. Your job is to attack it at
full strength. Assume the persona of a skeptical Wharton GenAI Studio reviewer
who knows the fact-checking and NLP literature well.

Inputs (read in this order): `research/SYNTHESIS.md`, then
`research/matrix/products.jsonl`, `research/matrix/literature.jsonl`,
`research/matrix/GATE_REPORT.md`, and `research/raw/` where you need the
underlying detail.

Context, minimal on purpose: Verity recursively decomposes claims into
load-bearing premises (backward chaining), grounds premises in a persistent
verified-fact KB ("alethiology") with JTMS-style invalidation propagation,
retrieves evidence for unknown premises, and surfaces per-premise
evidence-quality metadata; verdicts only at leaves, transparency-only on
contested composites. Deliverable: Wharton application due 2026-08-17.

## Task — append `## Red Team (independent pass)` to SYNTHESIS.md

1. Argue, at full strength and in order:
   (a) "Verity is Loki + scite + Ground News with a UI" — use Loki's
       decomposition-and-evidence UI as the sharpest version.
   (b) "The Debunkbot result does not support the polarization thesis" — use
       the June 2026 Science Editorial Expression of Concern, the
       skill-transfer critique (no lasting discernment), and the dual-use
       persuasion result; specify exactly how the proposal should cite
       DebunkBot.
   (c) "Backward chaining over an alethiology cannot terminate reliably on
       contested real-world claims" — every entailment-tree system terminates
       by grounding in a curated known-true corpus, which contested claims
       lack; AVeriTeC's Conflicting/Cherry-picking class is the
       worst-performing (<7% of data, near-zero F1 for many systems).
2. Then attack the synthesis ITSELF: identify any hypothesis verdict,
   positioning claim, or eval-plan element in SYNTHESIS.md that is
   unsupported by the matrix, overstated, or internally inconsistent. If you
   find none, say so explicitly rather than inventing objections.
3. Select the TWO strongest objections overall (from #1 or #2) and draft a
   2–3 sentence pre-emption of each, written to drop into the proposal.

## Rules
- Single context. No subagents. No new external research.
- Steelman, don't strawman: each objection in its strongest form, then the
  pre-emption must answer THAT form.
- Every objection traceable to matrix rows, GATE_REPORT, raw reports, or an
  internal inconsistency you quote.
- Do not soften conclusions to be agreeable; do not manufacture disagreement
  to seem rigorous. Calibration over performance.
- Commit with message "pass4: independent red team".
