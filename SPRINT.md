# SPRINT — Wharton application, submit by Mon 2026-08-17 17:00

**Temporary coordination doc. Delete this file and the CLAUDE.md sprint pointer
after submission.** For this window only, this doc scopes and re-orders
[docs/build-plan.md](docs/build-plan.md) §3. Every hard constraint still binds
(verdict boundary, no root aggregate, per-premise confidence, valence rule,
uncalibrated labels, no silent caps). Tier definitions and exit criteria come from
build-plan.md; this doc only selects, sequences, and assigns them.

**Objective:** an application-ready prototype + application documents — not v0.
Deliverables: résumé (Tanner), cover letter, ≤2-page project proposal, 2 work
samples (the Verity repo itself; the prototype with a recorded demo run).

---

## Target state by Mon 12:00 (code freeze)

Build-plan sessions 1–8 complete, plus two **demo-cuts** (partial tiers, labeled):

> Demo narrative: *claim → recursive premise tree → per-premise verifier
> confidence → one premise grounded in a seeded alethiology fact → that fact's
> source flagged retracted.*

- **Floor** (integration goes badly): sessions 1–4 only + documents. Stop building
  by Mon 10:00 and write.
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
| **0 — human setup** | Sat night | Tanner | Register OpenAlex key (mandatory — API is unusable without it) + NCBI key; skip S2 (out of sprint scope). Download the Retraction Watch CSV (`gitlab.com/crossref/retraction-watch-data`). Verify the chocolate-hoax retraction trail exists in it — see Demo items below |
| **1 — spine** | Sun early | Opus | M1-T1 (sequential, alone) |
| **2A — core loop** | Sun | Opus | M3-T1 (serviceable decomposition prompt — do **not** polish; Fable rewrites it Monday) → M4-T1 → M9-T1 |
| **2B — grounding** | Sun, parallel | Opus | M5-T1 (seed facts for the two demo claims) → M6-T1a |
| **2C — documents** | Sun, parallel | Opus | Draft proposal skeleton from positioning.md (conjunction argument, §5 objections) + hypotheses.md + open-questions.md §4 ("open questions / issues raised" sections). Draft cover-letter structure — flag every spot needing Tanner's personal input. Collate prompt history / git history for both work samples |
| **3 — integrate** | Sun night | Opus | Single session: merge lanes, M1-T2, M3-T2 |
| **4 — demo-cuts** | Sun night / Mon early | Opus | (i) Retraction flag: RW-table + Crossref/OpenAlex check on the demo claim's DOIs — a labeled partial of M7-T1 (no full disagreement policy). (ii) Metrics logger over a 5–10 claim mini-set — a labeled partial of M10-T1 |
| **5 — quality pass** | Mon 00:00–12:00 | **Fable** (fresh reset) | Rewrite the decomposition prompt, re-run demo claims until trees pass eyeball review against the three validity criteria. Optional Streamlit strip only if ahead. **Code freeze 12:00** |
| **6 — ship** | Mon 12:00–17:00 | Fable | Finalize proposal + cover letter + work-sample self-assessments; screenshots; README quickstart so a reviewer can run the demo; GitHub cleanup. Reserve ≥1h for the submission portal |

**Model rules for this sprint:** Opus = infrastructure, clients, integration, doc
drafts (Sonnet fine for pure transcription chores). Fable = decomposition-prompt
quality, demo re-runs, final application prose — nothing else. At least half of
Monday's Fable goes to documents; the noon freeze is hard.

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
- Work-sample self-assessments state the honest limitations (verifier
  uncalibrated, thresholds unmeasured, grounding rate not yet judged) — the
  pre-registration posture is the self-assessment.
- After submission: delete SPRINT.md, remove the CLAUDE.md sprint pointer, and
  resume the build-plan.md ordering at the next incomplete tier.
