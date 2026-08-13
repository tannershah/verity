# Pass 5 — Application Drafting (strongest model, max effort, single context)

You are drafting the Wharton Generative AI Studio application in the Verity
repo. Read `research/SYNTHESIS.md` END TO END before writing anything — the
main body is the source material and the `## Red Team (independent pass)`
section is binding review feedback. `CLAUDE.md` governs. Due 2026-08-17;
drafts today, polish on the 16th.

Web access: PERMITTED ONLY for bibliographic verification of works the
proposal actually cites (correct authors/venue/year/DOI — the residual debts
are lit-022, lit-026, lit-027, and the FEVER citation). No new research, no
new sources, no verdict changes.

## Task 0 — copy fixes required by the red team (before drafting)
1. In SYNTHESIS.md §3.1 and anywhere else in the repo the phrase appears
   (including CLAUDE.md's validity criteria), replace "guarantees
   termination" with: "termination enforced by depth budget; grounding rate,
   depth, and budget-exit rate measured and reported." (Red team 1c adoption
   requirement.)
2. Log the edits in REMEDIATION_LOG.md.

## Task 1 — `application/proposal.md` (<=2 pages, ~950–1100 words)
Expand §4's skeleton. Structure: Problem, Gap, Approach, Evaluation, Build
Plan & Status, Why This Team. Prose-first; no bullet walls; headers allowed.
Binding constraints:
- Use H3' and H5' formulations everywhere; never the dead H1-naive/H3/H5
  phrasings. Negative claims as "none found as of Aug 2026," and (where true)
  note targeted existence searches were run.
- Gap section: lead with the conjunction, concede each single feature by name
  (Loki, scite, Ground News, Wolfram/ClaimReview), then the empty cell;
  NELLIE as closest architecture missing exactly three layers; integrate the
  1a pre-emption text (adapt, don't quote wholesale).
- Add TWO sentences answering 1a's demand half: ingredient demand is priced
  (scite and Ground News subscriptions), conjunction demand is what the
  prototype + the Bucket-3 discernment study test — framed as fit for a
  build-and-test studio, not as a proven market.
- Approach section: include the one-sentence verdict-boundary pin (finding
  2.6): verdicts exist only at leaves; where evidence conflicts, Verity
  renders the conflict symmetrically and adjudicates nothing — no root
  aggregate is ever displayed.
- Approach/Eval: integrate the 1c pre-emption (termination enforced, not
  assumed; budget-exit as intended output on contested material; grounding
  rate as first-class metric; beachhead chosen so leaves ground in
  machine-readable fact).
- DebunkBot: follow §4's citation rule EXACTLY (direction only, EoC in the
  same sentence, same-team replications named as such, lit-023/lit-024 as
  design rationale, no magnitudes anywhere).
- Evaluation: Bucket 1 numbers first, proxies as proxies, both Bucket-3
  firsts framed as contributions.
- Build Plan & Status: compress D1–D8; near-future tense with explicit
  `[TODO-16th: flip to present tense + live repo/demo link]` markers.
- Every empirical claim must trace to SYNTHESIS.md or a matrix row; if it
  can't, cut it.

## Task 2 — `application/cover_letter.md` (<=1 page)
Voice: direct, concrete, zero filler. Content, in Tanner's voice:
- Who: Tanner, Penn BSE Artificial Intelligence + MSE Data Science
  (submatriculated), expected May 2028.
- Why this project is his: CIS 5190 political-bias-detection project
  (DistilBERT ~98% Fox-vs-NBC classification; 3-class model beat a GPT-4
  baseline; ~1M URLs/outlet scraped); Palantir Foundry/AIP internship — one
  line drawing the ontology -> alethiology lineage; Anthropic badges (MCP,
  Agent Skills, Claude Code, Claude API).
- The meta-point, one short paragraph: the attached research work sample was
  produced under Verity's own evidentiary standards — schema frozen before
  evidence review, per-cell provenance, an independent red-team pass that
  killed two of seven differentiation hypotheses, and targeted existence
  searches behind every negative claim. The pipeline demonstrates the
  product's epistemics.
- One line connecting to the Penn research context the work already cites
  (Media Bias Detector / Watts; Hopkins-coauthored discourse-decomposition
  line) without name-dropping beyond what the research actually engages.
- No superlatives about Verity that the proposal doesn't earn.

## Task 3 — `application/work_samples.md` (manifest, <=half page)
- Sample 1: this repo's research pipeline — prompts/, commit history,
  SYNTHESIS.md with independent red team; 3-sentence description + how to
  read it (prompt history requirement satisfied by prompts/ + commits).
- Sample 2: v0 prototype (placeholder: `[TODO-16th: repo link + demo]`),
  built via Claude Code, build prompt history included.
- Sample 3 (optional slot): CIS 5190 bias-detection project — mark as
  Tanner's call; include only if allowed as non-generative-AI-adjacent or
  reframed via its GPT-4-baseline comparison.

## Rules
- Single context, no subagents. SYNTHESIS.md is authoritative; where the
  skeleton and red team conflict, the red team's prescriptions win.
- Word/page budgets are hard limits.
- End with a short self-check paragraph in your final message: confirm every
  binding constraint above is satisfied, listing any you could not satisfy
  and why.
- Commit: "pass5: proposal, cover letter, work-sample manifest drafts".
