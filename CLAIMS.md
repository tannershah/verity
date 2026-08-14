# CLAIMS.md — Banned-Phrase Lint

Committee/defense remediation mechanism (defense Q6, adopted pass 7): remediation
that doesn't lint the final artifact is advisory. Before any commit touching
`application/` (and ideally any commit at all), run:

```bash
grep -n -f <(grep -E '^BAN: ' CLAIMS.md | sed 's/^BAN: //') application/*.md && echo "LINT FAIL" || echo "LINT CLEAN"
```

Each `BAN:` line is a literal phrase that must not appear in `application/`.
The `WHY`/`USE` lines explain and give the corrected replacement. Scope note:
`research/SYNTHESIS.md`'s red-team section intentionally preserves flawed
phrases as quoted review record (REMEDIATION_LOG I.3) and `research/raw/` is
read-only input — lint the application artifacts, spot-check the rest by hand.

BAN: transparency tools stop at the article, source, or citation level
WHY: Falsified by the repo's own matrix (Perplexity, Loki claim-level; Kialo argument-graph; red-team 2.4; regressed once already in proposal.md).
USE: "no automated transparency tool operates at the decomposed-premise level of a composite claim" (H3″; name Consensus/ARGUMEND — excluded on transparency-only — and Society Library/Kialo — excluded on automated).

BAN: stop above the premise level
WHY: The pass-7 proposed replacement was itself falsified by Kialo (premise-level, manual). Only the H3″ formulation with the "automated" qualifier survives.
USE: H3″ formulation as above.

BAN: independently corroborated
WHY: Red-team 2.1. Replication record is same-team (Boissin lit-022; Just-the-facts lit-021) plus one independent CONCEPTUAL replication (Meyer lit-032, reflection paradigm).
USE: "corroborated by same-team replications and one independent conceptual replication (reflective-dialogue paradigm; Meyer et al. 2024)".

BAN: corroborated so far only by same-team replications
WHY: Falsified pass 7 — Meyer et al. 2024 (lit-032) is independent (conceptual); Dartmouth/Nyhan replications reported-unpublished.
USE: same replacement as above.

BAN: guarantees termination
WHY: Red-team 1c. Termination is enforced, not guaranteed.
USE: "termination enforced by depth budget; grounding rate, depth, and budget-exit rate measured and reported".

BAN: materially weakened
WHY: EoC gloss the matrix invented (committee Q10). Quote the EoC; never characterize it.
USE: the quoted EoC language in lit-020 metrics_and_best_numbers.

BAN: red team killed two of my seven
WHY: False attribution (committee Q2): H3/H4a died in pass-3 adjudication, H5 in pass 3.1 — all before the red team, which changed no verdicts.
USE: "the synthesis adjudication killed two of seven hypotheses (a third split and partially died); an adversarial review pass with pre-registered attack surfaces plus an unscripted audit found seven further defects".

BAN: independent red-team pass
WHY: Committee Q4 — the marquee objections were scripted pre-synthesis by the same context; only the 2.1–2.7 audit was unscripted.
USE: "adversarial review with pre-registered attack surfaces plus an unscripted audit".

BAN: frozen before any evidence was reviewed
WHY: Committee Q2 — the git history offered as proof shows schema and evidence entering in one commit; the temporal claim is unverifiable from the artifact.
USE: "designed independently of extraction results and marked FROZEN in the project rules before adjudication" (or produce a verifiable ordering).

BAN: every surviving negative claim sits behind a targeted existence search
WHY: Was false for the pivots until pass 6; keep the claim scoped to the actual search record.
USE: "targeted existence searches (single-query pass 4.5; multi-vocabulary battery pass 6 for H3″/H5′) are logged in STRESS_SEARCH.md §C/§F".

BAN: sample size is NOT structured anywhere
WHY: Falsified (committee Q13): ClinicalTrials.gov serves structured enrollment; PubMed links papers to registrations.
USE: "sample size is structured only for registered trials (ClinicalTrials.gov enrollment, linked from PubMed); text-mined and labeled model-extracted elsewhere (Elicit precedent, product-028)".

BAN: Evidence Strength Meter
WHY: No such scite feature exists (committee sweep 2026-08-13); conflation with Smart Citations aggregates/Research Dashboard.
USE: "Smart Citations (Supporting/Contrasting/Mentioning) and the Research Dashboard aggregates".

BAN: 15,901
WHY: Wrong RetractoBot trial count (committee's own error, corrected by sweep).
USE: "15,921 papers (7,958 intervention / 7,963 control); 15,667 responding authors".

BAN: 34.7
WHY: SEER Task-2 figure not verified from primary source (PDF unparsed); embargoed.
USE: "NLProofS 33.3% in-paper (34.4% released checkpoint); successors report further gains [verify exact figures against SEER/NLDR PDFs before quoting]".

BAN: 36.5
WHY: NLDR Task-2 figure not verified from primary source; embargoed (same as above).
USE: same replacement as above.

BAN: keyless
WHY: OpenAlex requires keys for production use since 2026-02-13 (free key, 100k credits/day). "Free" survives; "keyless" doesn't — except Crossref/ClinicalTrials.gov, which remain keyless; scope the word to them explicitly if used.
USE: "free (OpenAlex: free registered key, 100k credits/day; Crossref and ClinicalTrials.gov keyless)".

BAN: nearly 55,000 retractions
WHY: 20 months stale; Retraction Watch homepage shows 66,000+ (accessed 2026-08-13).
USE: "66,000+ retractions (Retraction Watch, accessed 2026-08-13)".

## Impact-vs-uptake rule (not a literal phrase ban)

Any sentence citing VITALITY (lit-031) as evidence that retraction *surfacing
works* is banned. VITALITY evidences IMPACT (contamination changes pooled
effects); the RetractoBot RCT null (lit-033) bounds UPTAKE (post-hoc
notification doesn't change citing behavior); decision-time surfacing is
Verity's stated BET. Copy must keep the three separated.
