# SPRINT — Wharton application, submit by Mon 2026-08-17 17:00

**Temporary coordination doc. Delete this file and the CLAUDE.md sprint pointer
after submission.** For this window only, this doc scopes and re-orders
[docs/build-plan.md](docs/build-plan.md) §3. Every hard constraint still binds
(verdict boundary, no root aggregate, per-premise confidence, valence rule,
uncalibrated labels, no silent caps). Tier definitions and exit criteria come from
build-plan.md; this doc only selects, sequences, and assigns them.

**Objective:** an application-ready prototype — not v0. **Application materials
(résumé, cover letter, proposal, work-sample writeups) are Tanner's lane,
handled by him in parallel — agents do not draft, edit, or plan for them.**
The agent deliverable is the prototype plus its repo presentation: README
quickstart, recorded demo run, screenshots.

---

## Target state by Mon 12:00 (code freeze)

Build-plan sessions 1–8 complete, plus two **demo-cuts** (partial tiers, labeled):

> Demo narrative: *claim → recursive premise tree → per-premise verifier
> confidence → one premise grounded in a seeded alethiology fact → that fact's
> source flagged retracted.*

- **Floor** (integration goes badly): sessions 1–4 only. Stop building by
  Mon 10:00 and shift to repo presentation (README, screenshots, demo recording).
- **Ceiling** (ahead of schedule): add M1-T3 + full M10-T1, and only then a
  stripped Streamlit tree view (confidence bars only, no evidence panels).

**Do not attempt, even if ahead:** M6-T1b/T2/T3, M5-T2/T3, all of M8, full M9-T2,
M2, any threshold eval (M10-T2+). A half-built differentiator reads worse in a work
sample than a well-scoped one.

---

## Phases and lanes

Phase 1 is sequential and blocks everything: it defines the interfaces. Lanes in
Phase 2 run as parallel sessions — disjoint package directories or worktrees,
merged only in Phase 3. One tier per session; honor its exit criterion.

| Phase | When | Model | Work |
|---|---|---|---|
| **0 — human setup** | Sat night | Tanner | ✅ **COMPLETE.** Keys registered and live-verified; secrets in gitignored `.env` (never in `.env.example`). See status below |
| **1 — spine** | Sun early | Opus | ✅ **COMPLETE.** M1-T1 done: package layout, typed model, SQLite store, config/secrets, LLM adapter, run manifest, enforcement tests. See status below |
| **2A — core loop** | Sun | Opus | M3-T1 (serviceable decomposition prompt — do **not** polish; Fable rewrites it Monday) → M4-T1 → M9-T1 |
| **2B — grounding** | Sun, parallel | Opus | M5-T1 (seed facts for the two demo claims) → M6-T1a |
| **3 — integrate** | Sun night | Opus | Single session: merge lanes, M1-T2, M3-T2 |
| **4 — demo-cuts** | Sun night / Mon early | Opus | (i) Retraction flag: RW-table + Crossref/OpenAlex check on the demo claim's DOIs — a labeled partial of M7-T1 (no full disagreement policy). (ii) Metrics logger over a 5–10 claim mini-set — a labeled partial of M10-T1 |
| **5 — quality pass** | Mon 00:00–12:00 | **Fable** (fresh reset) | Rewrite the decomposition prompt, re-run demo claims until trees pass eyeball review against the three validity criteria. Optional Streamlit strip only if ahead. **Code freeze 12:00** |
| **6 — repo presentation** | Mon 12:00–17:00 | Fable | Screenshots; recorded demo run; README quickstart so a reviewer can run the demo; GitHub cleanup. (Tanner handles application materials and submission in parallel — not agent work) |

**Phase 0 status (complete; live-verified):** OpenAlex and NCBI keys work —
keyed OpenAlex GET returned 200 with rate headers (limit 10,000 shown for this
key tier; ample for the sprint), keyed E-utilities esummary returned 200. Load
both from `.env` (with `CROSSREF_MAILTO` for the polite pool) — never hardcode.
RW CSV at
`data/retraction_watch.csv` (71,799 records; `data/` gitignored). Chocolate-hoax
trail confirmed as a **three-source agreement** on DOI `10.3823/1654`: RW record
17524 (`RetractionNature: Retraction`), Crossref `update-to`/`updated-by`
(`type: retraction`, `source: retraction-watch`, `record-id: 17524`), OpenAlex
`is_retracted: true` (W209123019) — no demo-claim swap needed. Also confirmed
live: CT.gov v2 `enrollmentInfo {count, type: ACTUAL}` and the PubMed
DataBank/`AccessionNumber` NCT linkage (PMID 32445440 → NCT04280705). OpenAlex
answered one keyless singleton GET (demo tier, 100 credits/day) — do not rely on
keyless access for Sunday sessions.

**Gate 0 complete.** `ANTHROPIC_API_KEY` is in `.env` and the adapter is live-verified on
both paths: `complete()` and `messages.parse` structured extraction each returned
`stop_reason: end_turn`, with the configured effort echoed back on the response and cost
priced against the recorded table. The structured path carries `output_config` alongside
`output_format`, so decomposition runs at the configured effort rather than the API
default — the one request shape that unit tests against a stub could not confirm.

**Phase 1 status (complete):** `uv` venv on **Python 3.12** — pinned deliberately, since
Phase 2A's local NLI checkpoints need `torch`/`transformers` wheels and the system
default is 3.14. 158 tests green, ruff clean, no `xfail`. Three rulings were taken and
recorded in their owning docs: verifier confidence lives on the entailment step, not the
node (design §4.3); pre-registered thresholds are frozen constants, not configuration
(evaluation §2); external keys are stored canonicalized, with canonicalization bounded
to syntax (design §4.1). Lane-2A and lane-2B package directories exist with ownership
docstrings so Phase 3 merges additively.

**What the spine records beyond the obvious**, because each is a rule that cannot be
checked from results alone: retraction is a per-source map of what each of the three
sources *returned* — checked-and-clean, retracted, or not-indexed — so M7-T1's cut and its
disagreement log both have inputs; an `EvidenceBundle` records the queries issued, so
M6-T2's mandatory contrasting branch is distinguishable from one that found nothing; a
`StageRecord` carries the input digest, cache key, and resolved LLM settings that M1-T2's
cache-hit criterion has to verify against; a step records the **descent depth** it was
built at, since dedup can leave the graph shorter than the path that built it and the
budget was spent along the path; and a fact's identity is its (key, statement) pair, with
a supplied id checked against that derivation rather than trusted. The schema is versioned
forward: a newer database is refused rather than re-stamped, an older one is migrated.

### Reading in for Phase 2

Start with `src/verity/models/claim.py` — its module docstring states where confidence
lives, why traversal is over edges, and why nothing step-scoped sits on a node. Then
`models/render.py` for the renderer boundary, and `tests/test_downstream_contracts.py`,
which is an executable stub of what M10-T1, M9-T1, M7-T1 and M8-T3 each need from the
model.

Four obligations the spine places on the tiers that come next:

- **M3-T1 must set `EntailmentStep.depth`** as it descends. A graph records descent depth
  on every step or on none — a half-recorded descent is refused, so this cannot be
  half-done, but it does have to be done.
- **M3/M6 build graphs through `ClaimGraph.build()`** when a cap can orphan a subtree. It
  prunes what the root cannot reach and returns a `CapRecord`; direct construction refuses
  an unreachable premise rather than hiding it.
- **M9 calls `to_render_payload(graph, facts)`** — the fact store is required, because
  whether a recorded grounding still holds is a question only the alethiology can answer.
- **M4 writes ablation to `EntailmentStep.ablation_deltas`**, keyed by the premise removed,
  not to the premise.

Unknown fields are rejected everywhere (`verity.base`), so a renamed field fails at the
call site instead of vanishing. Take that as the house style rather than an obstacle: when
a constructor call errors, the field name is stale, not the guard.

**Model rules for this sprint:** Opus = infrastructure, clients, integration
(Sonnet fine for pure transcription chores). Fable = decomposition-prompt
quality, demo re-runs, repo presentation — nothing else. The noon code freeze
is hard.

---

## Demo items (two)

1. **Chocolate-weight-loss hoax** — carries the retraction demo-cut. **Verify
   first** (Phase 0): the trail must appear in the RW table. If it does not, swap
   in a cleanly-retracted, low-valence health paper *chosen from the RW table
   itself* and note the swap here. The demo narrative depends on this check.
2. **Spinach-iron decimal myth** — carries decomposition + grounding-in-seeded-fact.
   No retraction DOI exists for it; do not force one.

## Sprint-agent rules

- Demo-cut code is labeled partial in comments and README — it must not
  masquerade as the completed tier; the full tiers still run post-sprint per
  build-plan.md.
- Don't edit `docs/` during the sprint except where code makes a factual line
  stale; SPRINT.md is the only sprint-state file.
- The README/demo writeup states the honest limitations (verifier uncalibrated,
  thresholds unmeasured, grounding rate not yet judged) — the pre-registration
  posture is the presentation.
- Application materials (résumé, cover letter, proposal, work-sample writeups)
  are Tanner's lane — out of scope for every agent session unless otherwise directed.
- After submission: delete SPRINT.md, remove the CLAUDE.md sprint pointer, and
  resume the build-plan.md ordering at the next incomplete tier.
