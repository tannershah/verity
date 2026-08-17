# Verity — Prompting Pipeline
### Work sample: prompt history — Wharton Generative AI Studio application

## Summary — how this was built

This document is the prompting record of Verity: every prompt quoted below is
literal text that was sent, recovered from git history, run artifacts, and
Claude Code session transcripts — not reconstructed from memory. Where the log
has a gap, the gap is marked rather than filled in.

The project was built in five days, in five distinct modes of working:

1. **Research by relay (Aug 13–15).** A persistent claude.ai conversation
   ("the orchestrating agent") held the project's continuity and drafted
   single-purpose prompts — extraction, gate-check, synthesis, independent
   red team, remediation — which Tanner relayed into separate Claude Code
   sessions that did the work and committed it. Agents were repeatedly bound
   to *escalate ambiguity rather than resolve it*; only Tanner ruled.
2. **A self-invoked adversarial audit (Aug 15).** Tanner reframed the whole
   pipeline as a PhD thesis under defense and asked a fresh session to be the
   examining committee. It fanned out its own multi-agent examination, ran
   two rounds of adversarial verification, and then wrote and executed its
   own remediation.
3. **The sprint designed itself (Aug 15, night).** The phase structure that
   governed the entire build — the module/tier decomposition, the parallel
   lanes, the phase ordering, SPRINT.md itself — was authored by a planning
   agent, not by Tanner. Tanner supplied the goal and ratified its judgment
   calls, mostly by delegating them back.
4. **The build, orchestrated by hand (Aug 16–17).** For each tier, Tanner ran
   two Claude Code sessions in parallel — a **working agent** and a
   **red-team agent** — and relayed a fixed sequence of prompts between them:
   independent proposal and test design, cross-examination, revise-or-argue,
   green light, build, break attempt, structural fixes, final sweep, cleanup.
   Single verification-pass sessions gated each phase boundary.
5. **The relay, mechanized (Aug 17, overnight).** The same hand-run protocol
   was encoded into a bash script driving two headless Claude Code sessions,
   and the last build tiers ran unattended. The pattern did not change —
   only who was passing the messages.

The division of labor was constant throughout: agents propose, build, attack,
and verify; Tanner sets direction, arbitrates disputes, and owns every ruling
that matters.

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

This audit shape recurred later without being asked for: the post-Phase-3
verification pass (below) spun up its own internal audit fleet across eight
review dimensions with adversarial passes, then stopped it partway once the
remaining dimensions were already covered — the committee pattern,
reinvented mid-sprint by a different session.

---

## The sprint designed itself (Aug 15, 21:34 → Aug 16, 11:23)

The committee session closed at 20:12 on Aug 15. At 21:34 a new session
opened — and this is the answer to a question the record should state
plainly: **the sprint and its phase structure were designed by an agent,
not by Tanner.** Tanner's kickoff set the goal and the decomposition
criteria, nothing more:

```
We are building a technical design and scoping plan for a prototype of
Verity. Read through the existing files carefully… 1) break the
transparency engine prototype into modules… 2) For every module, break it
into tiers… 3) Give an ordering…
```

What followed, all inside one session (transcript
`29533f7c-09c6-4d6d-9026-38f35259bcfc.jsonl`):

- The agent dispatched **its own research fleet** — five parallel subagents
  (`verity-scoping-research`) grounding the plan in the repo's research
  matrix — and then **its own critique fleet** — three adversarial critics
  (`verity-plan-critique`) attacking the draft plan before any of it was
  written to disk.
- It wrote `docs/build-plan.md` (21:52), whose module/tier decomposition
  became the vocabulary of the whole build (`M1-T1`, `M3-T2`, …), each tier
  sized to one working session with a stated goal, method, and checkable
  exit criterion.
- It raised six open questions. Tanner's answers delegated four of the six
  straight back — *"I agree with your recommendation… I don't know what
  this means but make your best judgment… Yes, this is fine… If everything
  looks good commit and we will terminate this session."*
- Unprompted, it proposed the parallel-lane schedule that became the
  sprint's shape: *"After M1-T1 lands, run three lanes: (A) M3-T1→M4-T1→
  M9-T1, (B) M5-T1 + M6-T1a, (C) an Opus documents lane…"*
- Offered a coarse choice — *"Do what you think is best now out of the two
  options… a) create a doc that is a more formal sprint plan… b) nothing"*
  — it chose (a) and wrote `SPRINT.md` (23:08), including the Phases-and-
  lanes table (Phases 0–6), the floor/ceiling scoping, and the demo
  narrative. The committed file matches the session's `Write` call
  byte-for-byte (commit `771589c`).

One footnote for the model-routing record: this planning session ran on
**Fable** — before the sprint's own "Fable is reserved for the final
quality and presentation passes" rule existed, because that rule is *in*
the document this session was writing. The rule governed the build window
that followed it.

---

## The build: a hand-run worker/red-team relay (Aug 16 → Aug 17)

This is the framework the rest of the build ran on, and the direct ancestor
of the automation that finished it. For every tier, **two Claude Code
sessions ran in parallel — a working agent and a red-team agent — and
Tanner relayed a fixed sequence of prompts between them**, pasting each
agent's output into the other's next prompt. The sequence: independent
proposal and test-suite design (neither sees the other first) →
cross-examination → revise-or-argue → green light → build → break attempt →
structural-fixes-not-patches → final sweep → cleanup and docs.

The prompts below are Tanner's, verbatim from his own orchestration log
(typos preserved — these are literal records). Where his log is silent or
trails off, that is marked; nothing is reconstructed.

### Phase 1 — the spine (M1-T1), Aug 16 morning

The two Phase 1 kickoffs, recovered from the session transcripts
(`be0b6526…` working, kickoff 11:31; `864622cb…` red-team, 11:35). The
relay pattern is already here, in an earlier phrasing than the later
phases settled into:

Working agent:

```
You are helping me work on Verity. Read /.claude/CLAUDE.md, README.md, and
/docs to get an idea of the overall project. Then, read SPRINT.md and
build-plan.md to get an idea of our current state and where we're going.
You are going to be conducting Phase 1 of the Sprint, M1T1: scaffolding and
the data model. This is a crucial task with implications for the entirety
of the model, so spare no expense in ensuring that you have the most clear
understanding of what we need. Think through potential design options, ask
any questions, conduct any research, and then give me a detailed proposal
here of how you plan to complete this task.
```

Red-team agent:

```
You are helping me work on Verity. Read /.claude/CLAUDE.md, README.md, and
/docs to get an idea of the overall project. Then, read SPRINT.md and
build-plan.md to get an idea of our current state and where we're going.
You are going to be red-teaming Phase 1 of the Sprint, M1T1: scaffolding
and the data model. This is a crucial task with implications for the
entirety of the model, so spare no expense in ensuring that you have the
most clear understanding of what we need. There is a model currently
working on constructing a detailed proposal for the phase. Your goal: give
me a detailed proposal (in prose is fine) for a test suite built to assess
the data model. I want you to consider every possible criterion necessary
for a model to successfully build this phase out and what you will do to
identify them. Do your best to break this solution they propose.
```

### Phase 2 — two lanes in parallel (Aug 16 afternoon)

Parts 2A (core loop: M3-T1 → M4-T1 → M9-T1) and 2B (grounding: M5-T1 →
M6-T1a) ran **simultaneously — four sessions live at once** (a working and
a red-team agent per lane), Opus 5 at max effort for all four, with Tanner
relaying all four sides. Each kickoff told the agent about the other three,
so no session believed it was working alone.

The canonical relay, as run for **M3-T1** (the single-step backward
chaining mechanism) — Tanner's prompts in sequence:

Working agent:

```
You are working on Verity. Read /.claude/Claude.md, README.md, /docs, and
SPRINT.md to get a thorough understanding of the project and its current
state. You are going to be working on Phase 2A--Core loop. This means
building out M3T1, the single-step backward chaining mechanism. This is a
core mechanism that will define our recursion step, so it is crucial that
we get this right on the first try. Carefully read through the current code
and scaffolding for it, read through any research, and ask any necessary
questions. Then, give me a detailed proposal in prose for how you want to
implement this. Note that 3 other agents are working in sync with you: a
2A red-team, a 2B working, and a 2B red-team
```

Red-team agent:

```
You are working on Verity. Read /.claude/Claude.md, README.md, /docs, and
SPRINT.md to get a thorough understanding of the project and its current
state. You are red-teaming Phase 2A--Core loop. This is M3T1, the
single-step backward chaining mechanism. This is a core mechanism that will
define our recursion step, so it is crucial that we get this right on the
first try and identify any potential errors that may arise. Carefully read
through the current code and come up a test suite design in prose for me to
look at and feed to the working agent to verify its implementation
proposal.
```

Then the relay proper, each prompt carrying the other agent's actual output:

```
red-team:  "Cross reference this design proposal with your red-team flags
            and report any of conern or any other issues you see: <proposal>"

working:   "Here is what your red-team agent had to say about your
            proposal: <feedback>. Carefully read through what it had to say
            and then revise your proposal or argue why the concern is
            invalid."

red-team:  "Here is what working said for context: <response>. You are on
            standby and will do a thorough investigation and edge-case
            analysis when the build is complete."

working:   "build."

red-team:  "build is complete. Here is the summary the working agent gave:
            <summary>. Do the thorough red-team analysis and try your best
            to find a break."

working:   "This is what the red-team agent found broke in your product:
            <errors>. Look at each one carefully, determine if it is truly
            an error, then make the correct structural fix, not a patch.
            Summarize the repairs/reasons for your actions."

red-team:  "Here is the report from the working agent on the bugs you
            detected earlier: <report>. Do one last final sweep of the 2A
            deliverables to ensure everything is in order."

working:   "The red-team agent has determined your deliverable is solid.
            Here is its review: <review> Prepare to terminate this session.
            Make a sweep through the code you wrote to ensure we have a
            clean, lean, modular, well-organized codebase that will be
            maintainable long-term. Make any necessary updates to
            documentation that have not already been done."
```

The other four tiers ran the same relay with tier-specific openers (M4T1
"the off-the-shelf gate… will define our verification"; M9T1 "the CLI
render… will define our presentation"; M5T1 "the shema, store, and seed of
the Alethiology… will define our final product"; M6T1a "the retrieval
shared infrastructure (OpenAlex, Crossref)"). The real variations, as
logged:

- **A green-light stage appeared after M3-T1** and stayed: the red-team is
  asked to formally clear the build (*"Give the green light and build will
  start--You will be on standby…"*) and the worker's build prompt carries
  it (*"Here is the green light from red-team to build: <red-team>. Start
  building."*). M3-T1 itself had only the bare "build."
- **M5-T1: Tanner delegating rulings mid-relay.** The build prompt was
  *"On the rulings, do whatever you feel is best. Start the build."* — the
  same delegation pattern as the planning session, now inside a tier.
- **Extra repair rounds when the sweep found gaps.** M5-T1's final sweep
  came back with *"The red-team agent has found some gaps still in the
  deliverable"*, and the relay looped (gaps → fixes → re-review) before the
  cleanup prompt. M6-T1a hit the same (*"there are still gaps: <gaps>"*);
  its log trails off mid-loop ("…") before the standard cleanup prompt
  resumes — the intervening rounds went unlogged.
- **M9-T1's log jumps** from the build green-light straight to the
  bugs-report/final-sweep prompts — the break-attempt round is absent from
  the log as kept. Marked as a log gap, not evidence the round was skipped.
- **M6-T1a's red-team kickoff** also carried the "3 other agents are
  working in sync with you" line — the cross-lane awareness was symmetric.

### Verification passes at the phase boundaries

Between phases, a **single fresh session** (Opus 5; "ultra effort" in
Tanner's log) audited everything before the next phase could start.
Post-Phase-2 kickoff, verbatim:

```
You are working on Verity. Read /.claude/Claude.md, README.md, /docs, and
SPRINT.md to get a thorough understanding of the project and its current
state. You are going to be verifying that the 2A and 2B Phases of the
sprint are fully correct and that we are completely ready for phase 3 to
start. Be as thorough as possible with you analysis, and ensure absolutely
no stone is unturned when looking through the work done. The 2 parts of
the phase were done in parallel with agents often colliding on files, so
be sure everything makes complete sense before you give the go ahead. Look
through anything necessary in order to come to a conclusion.
```

That pass (transcript `6e517120…`, Aug 16 22:14–22:43) found and fixed
four issues — among them a test whose assertion was a vacuous `or True`,
and the venv editable-install defect — relocated the pilot decompositions
out of gitignored storage so the committed smoke set reproduces from a
fresh clone, and signed off 2A/2B with explicit non-claims recorded
("near-binary champion missing three corruption families").

The post-Phase-3 pass (transcript `71baa161…`, Aug 17 10:07–10:56) is the
one that reinvented the committee: it spun up an internal audit fleet
across eight review dimensions with adversarial passes, stopped it after
six ("I'd already covered both [remaining] ground myself"), fixed four
blockers plus a replay-determinism conflation, and deliberately left its
diff **uncommitted** for the next session to fold in — which the record
confirms happened (commit `4781c65`).

### Phase 3 — integration, half by hand, half by script (Aug 16 night)

**M1-T2 (the orchestrator)** ran as the same hand relay, now a single
worker/red-team pair (Opus 5, max effort), kickoffs verbatim per the
pattern above ("…building out M1T2, the spine's orchestrator… Note that a
red-team agent will be working in sync with you."), through the same
green-light → build → break → fix → sweep → cleanup sequence.

**M3-T2 (the recursive descent) is where the relay stopped being manual.**
Per Tanner's log: *"session orchestrated similar to the prior ones by a
Claude.ai agent writing a bash script that was then run in the terminal."*
The claude.ai orchestrating conversation — the same one that ran Era 1's
relay, whose transcripts live off this machine — was given the hand-relay
pattern above and returned `run-m3t2.sh`: a bash script that drives the
**headless Claude Code CLI** (`claude -p`), one persistent session per
role via `--resume`, and relays the same stages automatically. The local
record corroborates the hand-off without capturing the drafting: the
script appears on disk fully formed at 01:44 (its own header: *"Relays the
SPRINT.md protocol between one working agent and one red-…"*), no local
session drafted it, and the two sessions it then drove (`4dbddfcb…`,
`b6a2f963…`) discover it by `ls`, read it, and are driven by it to the
M3-T2 commits.

---

## The scripted worker/red-team loop (M3-T2, then Phase 4)

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

Every prompt is fed **verbatim as a shell string** — and the stages are the
hand relay's stages, near word-for-word. Every kickoff opens the same way,
forcing both agents to re-ground in the same governing documents:

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

## Model routing, as applied

- **Fable** — the sprint-planning session that wrote `build-plan.md` and
  `SPRINT.md` (before the routing rule it authored took effect), and the
  final demo/presentation passes the rule reserved it for.
- **Opus, max effort** — every build tier's working and red-team agent,
  and both verification passes (hand-run and scripted alike).
- **Sonnet** — pure transcription/extraction/boilerplate chores (the same
  rule Era 1 used for the extraction and gate-check passes), plus
  delegated mechanical execution in the publication phase.

## The constants that shaped every prompt in both eras

Pulled from `.claude/CLAUDE.md`, which every build-phase kickoff prompt
explicitly directs the agent to read first, and which Era 1's passes
inherit implicitly:

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
  ESCALATE, the committee's `[T]` tags, the build relay's "note any open
  questions and take your own ruling on them, recording the ruling") — and
  its complement, Tanner delegating rulings back when he judged the agent
  better placed ("make your best judgment"; "On the rulings, do whatever
  you feel is best").
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
| `docs/build-plan.md`, `SPRINT.md` (the sprint's own design) | Planning session `29533f7c…`, with its own research + critique subagent fleets |
| Phase 1–2 tier builds (`M1-T1` through `M6-T1a`) | Hand-run worker/red-team relay, four sessions in parallel at peak |
| Phase-boundary sign-offs (post-2, post-3) | Single verification-pass sessions `6e517120…`, `71baa161…` |
| `run-m3t2.sh` build + `phase3-m3t2` commits | Era 2, M3-T2 (script from the claude.ai orchestrating conversation, run in-terminal) |
| `run-phase4.sh` / `run-m10t1.sh` builds + `phase4-demo-cuts` commits, `runs/PHASE4-REPORT.md` | Era 2, M7-T1 / M10-T1 |

---

## Source map, for verification

- `prompts/pass{2,2_5,3,3_4,4,4_5,4_6,5,6,7}*.md` — deleted from the working
  tree at commit `a42b47d`; recovered via `git show 5dd7a483ab:prompts/<file>`.
- `run-m3t2.sh` — committed once at `3ba3b93`, untracked again at `4781c65`.
  `run-phase4.sh`, `run-m10t1.sh` — gitignored (`run-*.sh`), never committed.
- `runs/phase3-m3t2/`, `runs/phase4-m7t1/`, `runs/phase4-m10t1/` — ten-stage
  output files and `cost.log` per tier (local artifacts; `runs/` is gitignored).
- `docs/build-plan.md`, `.claude/CLAUDE.md` — current working tree.
  `SPRINT.md` — retired at submission per its own header; full text in git
  history.
- Phase 1–3 hand-relay prompts — Tanner's orchestration log (this document),
  cross-checked against session transcripts where noted.
- Session transcripts (Claude Code project directory), the load-bearing ones:
  `29533f7c-09c6-4d6d-9026-38f35259bcfc` (sprint planning, Aug 15–16);
  `be0b6526…`/`864622cb…` (Phase 1 worker/red-team); `6e517120…` (post-Phase-2
  verification); `715aaccd…`/`ba741987…` (Phase 3 M1-T2 worker/red-team);
  `4dbddfcb…`/`b6a2f963…` (M3-T2, script-driven); `71baa161…` (post-Phase-3
  verification); `207fe6f1-3bc7-44d0-b3ab-948dd76a4599` (examining committee,
  Aug 15).
