# Pass 3+4 — Synthesis & Red-Team (strongest available model, max effort)

You are running in the Verity repo. Inputs: `research/matrix/*.jsonl`,
`research/matrix/EXTRACTION_NOTES.md`, `research/schema.json` (hypotheses H1–H7),
`research/raw/` (raw reports).

IMPORTANT — the deep-research reports already pre-adjudicate H1/H2/H3/H7 and
pre-build an evaluation-status map (Bucket 1/2/3 in report B). Your job on those
items is to VERIFY against the extracted matrix and finalize — not re-derive
from scratch. Where you disagree with a report's verdict, say so and why.

Context: Verity is an epistemic transparency engine. Given text containing claims,
it recursively decomposes each claim into load-bearing premises (backward chaining:
premises jointly entail the claim, each easier to verify), checks premises against
a persistent verified-fact KB ("alethiology"), retrieves evidence agentically for
unknown premises, and surfaces per-premise evidence-quality metadata. Verdicts
exist only at the leaves; contested composite claims get transparency-only
treatment. Deliverable this feeds: Wharton Generative AI Studio application
(cover letter + <=2pp proposal), due 2026-08-17.

## Pass 3 — write `research/SYNTHESIS.md`

1. **Hypothesis adjudication.** One verdict object per hypothesis
   (`hypothesis_verdict_format`), then 2–4 sentences citing matrix rows.
   Constraints from the evidence:
   - H3 FAILS as stated (Ground News, Penn MBD, scite are transparency-only at
     source/article/citation level). Record the pivot: H3' = "no symmetric
     transparency-only inspection at the decomposed-premise level." Adopt H3'.
   - H4 needs a three-way split, not one verdict: entailment-STEP validity has
     an established benchmark (EntailmentBank Leaves/Steps/Intermediates/
     Overall-AllCorrect); decomposition FAITHFULNESS is proxy-only (DecompScore,
     entailment coverage, verifier-confidence deltas); decomposition of
     CONTESTED real-world claims has no evaluation at all. State all three.
   - H1/H2/H7: verify the reports' qualified-survive verdicts. Loki/
     OpenFactVerification is the strongest counterexample to H1 (atomic claims,
     not entailment-linked premises; researcher-facing; verdict-oriented) and
     RedacTek to H7 (paper-level 3-generation risk scores, not claim-level
     invalidation). Name both explicitly in the verdict objects.
   - H5/H6: adjudicate from the matrix. For H6, report A states the
     decomposition x study-level-metadata intersection is empty — confirm.
   - Negative claims phrased "none found as of Aug 2026".
2. **Positioning statement.** One paragraph. Lead with the CONJUNCTION, not any
   single feature: concede decomposition exists (Loki/SAFE), transparency-only
   exists (Ground News/Penn MBD), study-level metadata exists (scite), persistent
   fact stores exist (Wolfram/ClaimReview) — then show the empty cell where all
   four meet. Name NELLIE as the architecturally closest research system (recursive
   backward chaining grounded in a fact store) and state its three missing layers:
   evidence-quality metadata, invalidation propagation, no-verdict output. Name
   Kialo as the manual analog of the argument graph.
3. **Evaluation plan.** Adopt report B's Bucket 1/2/3 map; compress to
   proposal-ready form. Map the three decomposition validity criteria to
   concrete evals: joint sufficiency -> EntailmentBank step metrics +
   NLProofS-style verifier; verifiability descent -> termination tests against
   the alethiology; non-redundancy -> leave-one-out entailment ablation. Include
   the Bucket-3 plan for the two no-benchmark components: contested-claim
   decomposition (extend AVeriTeC Conflicting/Cherry-picking cases into
   entailment trees — flag as a publishable contribution) and invalidation
   propagation (JTMS layer + synthetic retraction-injection tests).
4. **Proposal skeleton.** <=1 page: problem, gap (from #1–2), approach, eval
   (from #3), 8-day build plan to v0. Bake in these decisions:
   - Beachhead domain: scientific/health claims (machine-readable retractions,
     strongest invalidation moat, matches the low-valence demo rule); news as
     roadmap.
   - v0 metadata via FREE APIs only: retraction = OpenAlex is_retracted
     cross-checked against Crossref update-to; study design = PubMed MeSH
     publication types; citation intent = Semantic Scholar (coarse); sample
     size = text-mined and labeled low-confidence, or deferred.
   - Invalidation = explicit JTMS (Doyle 1979) layer over the alethiology;
     note TMS has never been applied to scholarly retractions.
   - Cite DebunkBot as motivating-but-contested: pair with the June 2026
     Science EEoC, the PNAS Nexus 2025 replication, and the "Just the facts"
     mechanism preprint.

## Pass 4 — append `## Red Team` to SYNTHESIS.md

Argue, at full strength and in order: (a) "Verity is Loki + scite + Ground News
with a UI" — use Loki's decomposition-and-evidence UI as the sharpest version;
(b) "the Debunkbot result does not support the polarization thesis" — use the
June 2026 Science Editorial Expression of Concern, the skill-transfer critique
(no lasting discernment), and the dual-use persuasion result, and specify exactly
how the proposal should cite DebunkBot; (c) "backward chaining over an
alethiology cannot terminate reliably on contested real-world claims" — note
every entailment-tree system terminates by grounding in a curated known-true
corpus, which contested claims lack, and AVeriTeC's Conflicting/Cherry-picking
class is the worst-performing (<7% of data, near-zero F1 for many systems).
Then select the TWO strongest objections overall and draft a 2–3 sentence
pre-emption of each for the proposal.

## Rules
- Single context. Do not spawn subagents. No new external research.
- Everything traceable to matrix rows or raw reports.
- Uncertainty is fine; unsupported confidence is not.
- Commit with message "pass3-4: synthesis, eval plan, red team".
