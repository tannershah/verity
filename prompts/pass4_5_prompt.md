# Pass 4.5 — Red-Team Remediation & Pre-Draft Hardening (Sonnet 4.6, web search PERMITTED)

You are fixing specific defects identified by the independent red team
(`## Red Team (independent pass)` in `research/SYNTHESIS.md`) and hardening
the surviving negative hypotheses before the proposal is drafted. Unlike
passes 3 and 4, you MAY use web search — but only for the tasks that
explicitly call for it. Surgical edits only; log every change; do not
re-synthesize or restructure anything.

## A. Matrix corrections (literature.jsonl)
1. lit-022 (Boissin et al., PNAS Nexus 2025): correct the "independent
   replication" note — it shares three of five authors with lit-020
   (Costello/Rand/Pennycook line). Reword to "same-team replication with
   partial author overlap". Keep the row's facts otherwise intact.
2. lit-017: fix the baseline-attribution erratum exactly as described in the
   red team's finding 2.7 (read the finding; apply its correction; quote the
   before/after in your log).

## B. SYNTHESIS.md corrections (main body; leave the Red Team section verbatim)
1. §4: replace the "independently corroborated" claim about DebunkBot with
   accurate language: replications are same-team (lit-021 authors identical;
   lit-022 3/5 overlap); no fully independent replication is in the matrix.
2. Fix the H3' support sentence flagged in red-team finding 3: re-enumerate
   the transparency-only rows correctly from products.jsonl and restate the
   sentence so it is true. H3' itself stands.
3. Resolve the §2 vs. matrix contradiction on AVeriTeC's knowledge store per
   the red-team finding: make §2 consistent with the matrix row, citing it.
4. Incorporate the red team's five-point DebunkBot citation prescription
   (attack 1b) into the proposal skeleton's citation rule, including adding
   lit-024 (dual-use persuasion result) — the skeleton currently omits it.

## C. Negative-hypothesis stress searches (web search REQUIRED)
The red team observed that the only surviving negative hypothesis that got a
targeted search (H5) died on it. Run the red team's listed queries — one per
surviving negative: H1, H2, H4b, H4c, H6, H7 (use its exact queries where
given; otherwise construct one tight existence-check query per hypothesis).
Write `research/STRESS_SEARCH.md`: for each hypothesis — query used, date,
top 3-5 candidate results, and a judgment per candidate: NOT-A-COUNTEREXAMPLE
(one line why) or ESCALATE (looks like a genuine counterexample).
- You may NOT change any hypothesis verdict. ESCALATE items are decided by
  Tanner. If nothing escalates for a hypothesis, append one line to its
  verdict in SYNTHESIS.md: "Targeted existence search performed 2026-08-13;
  no counterexample found." — this strengthens every negative claim in the
  proposal.

## D. RedacTek row verification (web search permitted)
product-024 is all-inferred and load-bearing for H7. Fetch its two primary
sources (the Doody's review URL and Nature Index article in the row's
provenance). Where the fetched text confirms a cell, upgrade its confidence
to "verified"; where it does not, flag the cell in STRESS_SEARCH.md as
ESCALATE. Do not touch other rows.

## E. Targeted verify_before_proposal burndown (web search permitted)
The skeleton now exists, so the deferred source check is scoped: from
`research/matrix/sources.jsonl`, take ONLY the flagged sources that support
claims appearing in the proposal skeleton or in the two red-team pre-emptions.
For each: fetch, confirm the claim it supports, set verify_before_proposal to
false with a `verified_note`, or ESCALATE with what you found instead. List
skipped flagged sources (those not touching the skeleton) at the bottom of
STRESS_SEARCH.md as "deferred — not cited by proposal".

## Rules
- Every edit logged in `research/matrix/REMEDIATION_LOG.md`: file, row/section,
  before -> after, red-team finding it answers.
- No verdict changes, no new hypotheses, no restructuring, no tone edits.
- Ambiguity -> ESCALATE, never guess.
- End your final message with the count: edits applied / escalations / searches
  clean.
- Commit with message "pass4.5: red-team remediation + negative-hypothesis
  stress searches".
