# Verity — Prompting Pipeline
### Work sample: prompt history — Wharton Generative AI Studio application

Two eras, plus one audit episode that sits across both. Era 1 produced the
research and application drafts; a self-invoked "examining committee" audit
sits between the eras and rewrote part of the record; Era 2 built the v0
prototype. Every prompt quoted below is literal text that was sent, recovered
from git history, run artifacts, and session transcripts — not reconstructed
from memory.

---

## Era 1 — Research & positioning (Aug 13–15)

A linear relay of single-purpose prompts ("passes"), each a separate Claude
Code session, executed against the repo and committed. A **separate,
persistent claude.ai conversation ("the orchestrating agent")** held the
project's continuity between passes — it drafted and dispatched each pass
prompt and carried the vision across sessions, but could not touch the
filesystem itself. Tanner relayed prompts between that conversation and the
Claude Code sessions that actually edited the repo.

**Pass 0 (upstream of the repo, no commit).** Two deep-research reports
commissioned and produced (`research/raw/report_a.md` = product landscape,
`report_b.md` = literature), seven differentiation hypotheses drafted
(H1–H7), and the extraction schema (`research/schema.json`) frozen — all
before Claude Code was involved. The repo's first commit is already
"pass2." Launch-prompt excerpt from the product-landscape report:

```
TASK 2 — Hypothesis testing. Test each hypothesis explicitly, state whether
it SURVIVES or FAILS, and give the single strongest counterexample found
(or state "none found as of Aug 2026" if no counterexample exists):
- H1: No consumer product auto-decomposes claims into premises with
  per-premise evidence display.
- H2: scite.ai has no argument-structure layer above citations...
- H3: No fact-checker offers symmetric, transparency-only inspection (no
  verdicts) as the core product.
- H7: No product does dependency-propagated invalidation...
Phrase all negative findings as "none found as of Aug 2026" rather than
absolute claims.
```

**Pass 2 — Structured extraction** (Sonnet 4.6, low/medium effort,
headless/unattended). Full prompt:

```
# Pass 2 — Structured Extraction (headless, Sonnet 4.6, low/medium effort)

You are running unattended in the Verity repo. Deep-research reports are in
`research/raw/` (report A = product landscape, report B = literature). The
frozen extraction schema is `research/schema.json`. Do not modify the
schema.

## Tasks (in order)
1. Read `research/schema.json` fully before extracting anything.
2. For EACH product in report A, emit one JSON object conforming to
   `feature_matrix_row` into `research/matrix/products.jsonl`.
   - Every cell gets provenance {source_url, access_date, confidence}. If
     report A gives no source for a cell, mark confidence "inferred" and
     use the report itself as source. Never invent URLs.
   - If a value doesn't fit an allowed enum, use the closest enum and add
     an `extraction_note` explaining the mismatch. Do not extend the enums.
3. For EACH paper in report B, emit one JSON object conforming to
   `literature_row` into `research/matrix/literature.jsonl`.
4. Spot-check pass: validate JSON parses line-by-line, verify enum
   conformance, list any rows you are <70% confident in inside
   `EXTRACTION_NOTES.md`, along with any products/papers skipped and why.
5. Commit: "pass2: structured extraction from deep research".

## Rules
- Extraction only. No synthesis, no hypothesis verdicts, no
  editorializing — that is Pass 3's job.
- Do not attempt web research to fill gaps. Stay inside the repo.
```

Output: `products.jsonl`, `literature.jsonl`, `sources.jsonl` against the
frozen schema — explicitly forbidden from fetching external URLs or filling
gaps with its own research.

**Pass 2.5 — Extraction gate check** (Sonnet 4.6, low effort, read-mostly).
A second, independent pass whose only job is to check Pass 2's work against
the raw reports:

```
# Pass 2.5 — Extraction Gate Check (Sonnet 4.6, low effort, read-mostly)

You are verifying Pass 2's extraction in the Verity repo before synthesis
runs. This is a CHECK, not a redo. Do not modify `research/schema.json`, do
not re-extract, do not editorialize.
```

Checked: row-count arithmetic, that three specific "adversary rows" (Loki,
RedacTek, scite — load-bearing for hypothesis adjudication) actually carry
their disqualifying qualifications, a skipped-paper audit against a named
must-not-skip list, and source-integrity spot checks. Reported PASS/FAIL
per item with quoted evidence, surgical fixes only (every fix logged),
closing in `VERDICT: CLEAR FOR PASS 3` or `VERDICT: BLOCKED — <reason>`.
Ambiguity was marked AMBIGUOUS and left for Tanner rather than guessed.

**Pass 3 — Synthesis** (strongest available model, max effort, single
context, no subagents):

```
# Pass 3+4 — Synthesis & Red-Team (strongest available model, max effort)

You are running in the Verity repo. Inputs: research/matrix/*.jsonl,
EXTRACTION_NOTES.md, schema.json (hypotheses H1–H7), research/raw/.

IMPORTANT — the deep-research reports already pre-adjudicate H1/H2/H3/H7
and pre-build an evaluation-status map. Your job on those items is to
VERIFY against the extracted matrix and finalize — not re-derive from
scratch. Where you disagree with a report's verdict, say so and why.

## Pass 3 — write research/SYNTHESIS.md
1. Hypothesis adjudication. One verdict object per hypothesis, then 2–4
   sentences citing matrix rows.
   - H3 FAILS as stated (Ground News, Penn MBD, scite are transparency-only
     at source/article/citation level). Record the pivot: H3' = "no
     symmetric transparency-only inspection at the decomposed-premise
     level." Adopt H3'.
   - H4 needs a three-way split: entailment-STEP validity has an
     established benchmark; decomposition FAITHFULNESS is proxy-only;
     decomposition of CONTESTED real-world claims has no evaluation at all.
```

Also wrote the positioning statement (explicitly told to lead with the
**conjunction** of features, not any single one), the evaluation plan
mapping the three decomposition-validity criteria to concrete evals, and a
proposal skeleton. Explicitly told **not** to write its own red-team
section, by design.

**Pass 3.1** — a one-line correction pass: H5 pivoted to H5′ after
discovering debunkbot.com is a shipped product, not just a research
prototype.

**Pass 4 — Independent red team** (strongest model, max effort, **fresh
session** — deliberately not a continuation):

```
# Pass 4 — Independent Red Team (strongest available model, max effort,
FRESH session)

You are an independent reviewer in the Verity repo. You did NOT write
research/SYNTHESIS.md and owe it no loyalty. Your job is to attack it at
full strength. Assume the persona of a skeptical Wharton GenAI Studio
reviewer who knows the fact-checking and NLP literature well.

Inputs (read in this order): SYNTHESIS.md, products.jsonl, literature.jsonl,
GATE_REPORT.md, research/raw/ where you need underlying detail.

## Task — append `## Red Team (independent pass)` to SYNTHESIS.md
1. Argue, at full strength and in order:
   (a) "Verity is Loki + scite + Ground News with a UI"...
   (b) "The Debunkbot result does not support the polarization thesis"...
```

Argued the three strongest attacks on the whole thesis at full strength
(steelman, not strawman), then separately attacked the synthesis document
itself for unsupported/overstated/inconsistent claims — told explicitly
"if you find none, say so explicitly rather than inventing objections" —
then distilled the two strongest objections into short pre-emptive rebuttal
text for the proposal. Found 7 real defects, the sharpest being a same-team
replication mislabeled as independent corroboration of the DebunkBot
result.

**Pass 4.5 — Red-team remediation + stress search** (Sonnet 4.6, **web
search permitted** — the first pass allowed to leave the repo):

```
# Pass 4.5 — Red-Team Remediation & Pre-Draft Hardening (Sonnet 4.6, web
search PERMITTED)

You are fixing specific defects identified by the independent red team.
Unlike passes 3 and 4, you MAY use web search — but only for the tasks
that explicitly call for it. Surgical edits only; log every change; do not
re-synthesize or restructure anything.
```

Also ran "negative-hypothesis stress searches": actually executing the
existence queries a claim of absence implicitly depends on, for every
surviving negative hypothesis, and judging each result NOT-A-COUNTEREXAMPLE
or ESCALATE. Bound explicitly: *"You may NOT change any hypothesis verdict.
ESCALATE items are decided by Tanner... Ambiguity → ESCALATE, never guess."*

**Pass 4.6 — Escalation rulings** (Sonnet, surgical, no search). Applied
Tanner's literal rulings on the three items Pass 4.5 escalated — the
pattern throughout Era 1: an agent may flag and stop; only Tanner resolves.

**Pass 5 — Application drafting** (strongest model, max effort, single
context). Drafted `proposal.md` (≤2pp), `cover_letter.md` (≤1pp, "in
Tanner's voice," his actual biographical facts supplied verbatim in the
prompt so nothing is invented), and `work_samples.md`. Carried a long list
of binding phrasing constraints inherited from the red-team pass (e.g.
"termination enforced by depth budget" — never "guarantees termination";
a literal citation rule for how DebunkBot may and may not be cited). Ended
with a mandatory self-check paragraph confirming every binding constraint
was satisfied, or explaining which weren't.

**Governing rule throughout Era 1:** application materials are Tanner's own
lane even here — Pass 5 drafts them once, but every subsequent agent is
explicitly told not to touch `application/`.

---

## The "examining committee" audit (Aug 15) — a self-invoked adversarial layer above Era 1

Separately from the pass-by-pass relay, Tanner opened a distinct Claude Code
session and reframed the entire pipeline-so-far as a PhD thesis under
defense:

```
Imagine that what you have presented to you is the initial research,
scoping, and proposal of a phd thesis... and you are the examining
committee for it. The PhD student is the agent I've been running a session
with concurrently... This is their work to carry out my vision, and I want
it subject to the highest grade of scrutiny. You should question their
methodology, analysis, content produced... Pay special attention and try to
break apart the plan.
```

That single session then, on its own initiative:

- **fanned out its own internal multi-agent examination** — separate
  subagent lines for methodology, technical feasibility, external
  verification of factual claims, and critique of the proposal documents
  themselves;
- ran **two rounds of adversarial verification**, where every finding had
  to survive a dedicated attempt to refute it before being reported — final
  tally: **15 critical, 32 major, 17 minor findings, zero refuted**;
- delivered a committee report with each question tagged `[T]` (Tanner's to
  answer) or `[A]` (the orchestrating agent's), and Tanner answered every
  one directly, using explicit rulings — e.g. telling the committee which
  classes of finding to set aside for now (application copy — his own lane;
  timeline estimates — expected to move; prompt-log completeness — to be
  reconciled in bulk before submission, since sessions live in different
  places and policing it per-commit is wasted motion);
- **wrote the next pass's prompt itself** — a "Pass 6" existence-search
  battery for the two pivot hypotheses (H3′, H5′) that the committee
  discovered had never actually been searched — and handed it to the
  orchestrating agent's session to execute;
- **Pass 6 ran as a delegated "committee subagent" battery** (per its own
  header: "run by committee subagent because orchestrating agent
  unavailable, per Tanner's instruction") against a protocol with mandated
  candidate products the results *had* to address, and a closed judgment
  vocabulary — COUNTEREXAMPLE / NEAR-MISS-FORCES-QUALIFIER /
  NOT-A-COUNTEREXAMPLE / ESCALATE — where research prototypes can never
  count as a COUNTEREXAMPLE against a claim about *products*, by
  definition, but are still logged because they constrain the phrasing;
- **Pass 7 was "chair-executed"**: the committee session applied its own
  final rulings straight to the repo (adopting a further-refined H3″,
  correcting a misattributed source, adding two new governance files — a
  banned-phrase lint and a pre-registered floors/falsification-line doc) —
  in its own words, "the orchestrating agent (claude.ai) cannot act on the
  repo";
- closing verdict: **"pass, with major revisions — the revisions now
  specified, most already executed."**

This is the most distinctive piece of the whole pipeline: a same-model,
role-played adversarial audit (skeptical committee vs. "PhD candidate"
agent) that didn't just criticize — it authored and then executed its own
remediation, closing the loop without waiting for the orchestrating
conversation. The interactive defense session described in the research
summary above ran in parallel with this and answered the same committee's
`[A]`-tagged questions.

---

## Era 2 — Build (Aug 15 evening → Aug 17)

`docs/build-plan.md` decomposes the system into 10 modules and tiers
(`M1-T1`, `M3-T2`, etc.), each sized to one working session, with a stated
goal, method, and checkable exit criterion, in dependency order. `SPRINT.md`
is a **temporary** doc (deleted after submission) that re-orders and selects
a subset of those tiers for the application deadline, without altering
their definitions.

**Model routing** (from `CLAUDE.md` and `SPRINT.md`, applied consistently):
- **Opus, max effort** — infrastructure, clients, integration, and every
  build/red-team cycle.
- **Sonnet** — pure transcription/extraction/boilerplate chores (the same
  rule Era 1 used for the extraction and gate-check passes).
- **Fable**, fresh reset — reserved for exactly two things at the end:
  rewriting the decomposition prompt for quality and re-running the demo
  claims, and the repo-presentation pass (screenshots, recorded demo,
  README). Nothing else.

**Phase structure:** Phase 0 (human — API keys live-verified, secrets in
gitignored `.env`) → Phase 1 "spine" → Phase 2A/2B (two parallel lanes in
separate package directories) → Phase 3 "integrate" (merge + two more
tiers) → Phase 4 "demo-cuts" (two explicitly labeled *partial* tiers,
scoped down for the demo narrative) → Phase 5 "quality pass" (Fable) →
Phase 6 "repo presentation" (Fable). Phases 1–3 read as interactively-run
Opus sessions (their `SPRINT.md` write-ups are first-person session
retrospectives, not a fixed artifact trail). Starting at **M3-T2** (back
half of Phase 3), the process is formalized into a scripted, unattended
two-agent loop — reused as-is for Phase 4.

### The scripted worker/red-team loop

`run-m3t2.sh`, generalized as `run_tier()` in `run-phase4.sh`. Mechanics: a
bash script drives the **headless Claude Code CLI** (`claude -p`), one
persistent session per role via `--resume <session_id>`, `--model opus`,
effort forced to `max` via a throwaway `/effort max` turn before the real
prompt, `--permission-mode acceptEdits --allowedTools Bash`, output parsed
as JSON via `jq` (`.result` for text, `.total_cost_usd` for spend). Both
scripts share an operational fix: Claude Code interleaves MCP chatter on
stdout, so the wrapper greps for the first line starting `{`. Git commits
snapshot state after the build, fixes, and cleanup stages (`snap()`), so a
tier's history is legible even if the run is interrupted.

Every prompt is fed **verbatim as a shell string**, and every kickoff opens
the same way, forcing both agents to re-ground in the same governing
documents before doing anything:

```
Read /.claude/Claude.md, README.md, /docs, and SPRINT.md to get a thorough
understanding of the project and its current state.
```

**Ten fixed stages per tier**, one working agent and one red-team agent
running in the same two sessions throughout, each stage's prompt built by
interpolating the *previous stage's actual output file* rather than
trusting either agent's memory of it:

1. **Worker bootstrap + proposal** — read project state, rule on any open
   questions found (recording the ruling and reasoning), propose an
   implementation in prose. Told explicitly a red-team agent works in sync.
2. **Red-team bootstrap + test-suite design** — independently reads the
   same state and designs a test suite in prose, *before* seeing the
   worker's proposal.
3. **Red-team cross-reference** — now shown the worker's proposal, reports
   concerns against its own test design.
4. **Worker revise-or-argue** — shown the red-team's concerns, must either
   revise the proposal or argue explicitly why a concern is invalid.
5. **Red-team green light** — told the build is about to start; standby
   for a post-build break-attempt.
6. **Worker BUILD** — implements. Git commit.
7. **Red-team try to break it** — adversarial pass over the finished build,
   scoped to "anything that would not fly in front of a reviewer on a live
   demo" (and, on Phase-4 partial tiers, explicitly told *not* to flag the
   tier for being incomplete against the full spec — an intentional cut).
8. **Worker structural fixes** — for each reported break, judge whether
   it's real, then apply "the correct structural fix, not a patch." Commit.
9. **Red-team final sweep** — one last pass confirming everything will hold
   up on the actual demo path.
10. **Worker cleanup + docs** — a maintainability pass over everything
    touched this tier, docs brought current, and (Phase 4 only)
    confirmation that partial-tier labeling is present everywhere needed.
    Commit.

Verbatim example, the M7-T1 worker bootstrap (Phase 4, chained off M1-T3 and
M7-T1's predecessor):

```
M1T3's batch runner does not exist and is out of scope for this sprint, so
decide how the mini-set gets run and record the ruling. M7T1 landed
immediately before you--read what it built. This closes out the demo
narrative, so it is crucial that we get this right on the first try.
Carefully read through the current code and scaffolding for it, read
through any research, and note any open questions and take your own ruling
on them, recording the ruling and your reasoning. Then, give me a detailed
proposal in prose for how you want to implement this. Note that a red-team
agent will be working in sync with you.
```

And the matching M10-T1 red-team test-design bootstrap:

```
You are working on Verity. Read /.claude/Claude.md, README.md, /docs, and
SPRINT.md to get a thorough understanding of the project and its current
state. You are red-teaming Phase 4--Demo-cuts. This is M10T1, the metrics
logger over a 5-10 claim mini-set. This is a labeled partial, not the full
tier, so do not flag it for being incomplete against build-plan.md--the
20-claim beachhead set and the threshold verdict are explicitly out of
scope. What you are hunting for is anything that would not fly in front of
a reviewer on a live demo: a smoke-test number presented as if it were the
pre-registered measurement, a metric computed off a denominator that does
not match build-plan.md section 4, a cap or a reject count that is applied
silently and never reported, a crash on the mini-set, or a claim in the
README or the comments that the code does not actually support.
```

And stage 10 (worker cleanup) for M10-T1, showing the closing pattern:

```
Prepare to terminate this session. Make a sweep through the code you
wrote/modified to ensure we have a clean, lean, modular, well-organized
codebase that will be maintainable long-term. Make any necessary updates
to documentation that have not already been done, and confirm the partial
is labeled as a partial everywhere it needs to be.
```

**`run_tier()` generalization.** `run-phase4.sh` runs the same ten stages
twice — once for M7-T1 (retraction check, partial: ships without the full
disagreement-policy leg) and once for M10-T1 (metrics logger over a
5–10-claim mini-set, smoke numbers rather than the pre-registered
threshold verdict, which `docs/build-plan.md` §4 fixes at session 31) —
so M7-T1's loop finishes and commits before M10-T1's sessions are even
created. Both land on one branch, `phase4-demo-cuts`, six commits total,
ending in a single generated report:

```
{
  echo "# Phase 4 demo-cuts — $(date)"
  echo
  echo "## cost (priced at API rates; billed to subscription)"
  for t in m7t1 m10t1; do
    printf '%-6s $%s\n' "$t" "$(paste -sd+ "$REPO/runs/phase4-$t/cost.log" | bc)"
  done
  echo
  echo '## pytest'
  (cd "$REPO" && python -m pytest -q 2>&1 | tail -20)
  echo
  echo '## ruff'
  (cd "$REPO" && ruff check . 2>&1 | tail -10)
  echo
  echo '## commits'
  git log --oneline "$BASE..phase4-demo-cuts"
} > "$REPO/runs/PHASE4-REPORT.md" 2>&1
```

When the run needed to be split at the tier boundary, a standalone
`run-m10t1.sh` reran the same ten stages and prompts at `xhigh` effort
instead of `max`, additionally logging session IDs to
`runs/phase4-m10t1/sessions.txt` so effort could be adjusted mid-run next
time. `MODEL="opus"` was flagged as the deeper available cost cut — M10-T1
only reads manifests and computes four numbers, well within Sonnet's
range, and a bigger saving against the weekly cap than the effort change.
One standing correction worth keeping: running headless overnight is
*cheaper* on prompt cache than hand-relaying would have been, since nothing
is idling between turns waiting on a human to read.

**Cost, as actually spent** (`total_cost_usd`, summed per stage, from
`runs/*/cost.log`): M3-T2 ≈ **$72.08**, M7-T1 ≈ **$36.82**, M10-T1 recorded
**$0** across all ten stages — flagged as a likely instrumentation gap
(cache hits reporting `$0`, or a cost field the script wasn't capturing
correctly for that run) rather than an actual zero-cost Opus/max-effort
tier.

---

## The constants that shaped every prompt in both eras

Pulled from `.claude/CLAUDE.md`, which every Era 2 kickoff prompt explicitly
directs the agent to read first, and which Era 1's passes inherit
implicitly:

- **The verdict boundary is non-negotiable in prompt text, not just in
  code**: verdicts exist only at leaves; contested composite claims get
  transparency-only treatment; no root aggregate, ever. Multiple passes and
  tiers carry an explicit test or stated rule enforcing this (e.g. M9-T1's
  "a test asserts no root aggregate is computed or rendered").
- **No silent caps, anywhere** — any bound (depth, retries, top-k, node
  counts) must be reported in the run, never invisibly truncate.
- **Refuse rather than repair** — malformed model output that would
  require the pipeline to edit the model's own proposal is refused and
  counted, not silently corrected. This shows up as a hard rule in both
  `build-plan.md` M3-T1 and in Era 1's "ambiguity → escalate/flag, never
  guess" instruction — the same epistemic posture applied to the product
  being built and to the process building it.
- **Uncalibrated stays labeled uncalibrated** until an actual calibration
  tier runs.
- **Escalation, not adjudication, is the agent's job** whenever a call is
  Tanner's to make — the one rule that appears, worded differently, in
  nearly every prompt across both eras (Pass 2.5's AMBIGUOUS, Pass 4.5's
  ESCALATE, the committee's `[T]` tags, M3-T1's instruction to take and
  record a ruling but flag it).
- **Process narration doesn't belong in the repo.** `CLAUDE.md`: "Git
  carries the history. Do not add change logs, pass records, or process
  narration to the repository." This is why the `prompts/` directory
  itself was deleted (commit `a42b47d`, Aug 15) once its contents had done
  their job — prompt texts had to be recovered from git history, not read
  from a live file. Anchor claims to git history and run artifacts, not to
  files assumed still present.

---

## Summary of artifacts produced

| Artifact | Produced by |
|---|---|
| `research/schema.json`, H1–H7 hypothesis set | Pass 0 |
| `research/matrix/products.jsonl`, `literature.jsonl`, `sources.jsonl` | Pass 2, hardened through 4.6 |
| `GATE_REPORT.md`, `EXTRACTION_NOTES.md` | Pass 2.5 |
| `research/SYNTHESIS.md` (incl. independent red-team section) | Passes 3–3.1, 4 |
| `REMEDIATION_LOG.md` | Passes 4.5–4.6 |
| `application/proposal.md`, `cover_letter.md`, `work_samples.md` | Pass 5 |
| Committee report, H3″ refinement, banned-phrase lint, floors/falsification doc | Examining-committee audit (Pass 6 delegated, Pass 7 chair-executed) |
| `run-m3t2.sh` build + `phase3-m3t2` commits | Era 2, M3-T2 |
| `run-phase4.sh` / `run-m10t1.sh` builds + `phase4-demo-cuts` commits, `runs/PHASE4-REPORT.md` | Era 2, M7-T1 / M10-T1 |

---

## Source map, for verification

- `prompts/pass{2,2_5,3,3_4,4,4_5,4_6,5,6,7}*.md` — deleted from the working
  tree at commit `a42b47d`; recovered via `git show 5dd7a483ab:prompts/<file>`.
- `run-m3t2.sh` — committed once at `3ba3b93`. `run-phase4.sh`, `run-m10t1.sh` —
  gitignored (`run-*.sh`), never committed.
- `runs/phase3-m3t2/`, `runs/phase4-m7t1/`, `runs/phase4-m10t1/` — ten-stage
  output files and `cost.log` per tier (local artifacts; `runs/` is gitignored).
- `docs/build-plan.md`, `.claude/CLAUDE.md` — current working tree.
  `SPRINT.md` — retired at submission per its own header; full text in git
  history.
- The examining-committee session — Claude Code project transcript
  `207fe6f1-3bc7-44d0-b3ab-948dd76a4599.jsonl`, dated 2026-08-15.
