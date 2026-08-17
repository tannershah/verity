# The demo, explained

This directory is the demo's record: verbatim terminal output captured on
2026-08-17, the day of submission. Nothing here is mocked or hand-edited — each
file is the output of one command, and every command runs offline on a fresh
clone with no API key (recorded LLM answers and registry responses are
committed with the repo; the one live LLM call behind each claim's first-ever
decomposition cost a few cents and was recorded then). The root README's "See
it run" section has the commands to reproduce all of it.

## The two demo claims, and why these two

Demo claims are deliberately **verifiable and low-valence** — the repo's design
docs bar contested political claims from the demo until the machinery has
earned trust — and each claim was picked to carry a different part of the
story:

1. **"A misplaced decimal point made spinach famous as an iron-rich food."**
   The famous myth-about-a-myth of spinach's inflated iron content. This is
   the committed, replayable run: decomposition plus per-premise verification.
2. **"Eating dark chocolate accelerates weight loss."** The claim behind the
   2015 chocolate-hoax study — deliberately bad science, published, gone
   viral, retracted, and still cited. It carries the retraction story, and,
   as it turned out, the deepest recursion of the demo.

## How a run works

Every capture below sits on the same four-stage pipeline. **Decompose**: an
LLM proposes 3–7 premises that jointly entail the claim; each premise is
typed, and the descent recurses on types that warrant it, bounded by a depth
budget and a node cap, with every terminal recording *why* it stopped.
Malformed proposals are refused and counted, never silently repaired.
**Verify**: a locally-run entailment model (DeBERTa-v3, run on this machine —
no API) scores every decomposition step; the score ships labeled
*uncalibrated* and the render prints the model's known misses beside its
numbers. **Bind**: any identifier a premise carries (DOI, PMID) is resolved
against scholarly registries. **Ground**: a bound identifier is looked up in
the alethiology — the store of verified facts — by exact key. Then the run is
stored and rendered.

## The captures, file by file

### `00-store-build.txt` — building the fact store

Two commands. `verity.alethiology seed` loads 33 curated facts (19 about the
spinach story, 14 about the chocolate hoax; 30 keyed by DOI, 3 by PMID)
against committed records of what each registry returned. The interesting part
is what the gate **refused to take at face value**: six facts requested
"verified-primary" status and were *downgraded* to "single-secondary" because
the registries disagree about what work DOI `10.3823/1654` even is —
Retraction Watch says *"Chocolate with high Cocoa content as a weight-loss
accelerator"*, while Crossref and OpenAlex both return a completely different
paper (*"The comparison of resilience and spirituality in addicted and
non-addicted women"*). That is a real data-integrity problem in the world's
scholarly infrastructure, surfaced and recorded by the seed gate instead of
papered over: the capture lists all four affected rows under "work-identity
mismatches."

Then `verity.quality apply` checks all 19 identifiers in the store against
three retraction sources — Retraction Watch's bulk table, Crossref's
update metadata, and OpenAlex's `is_retracted` flag — and writes the result
onto each fact. Final tally, printed in the capture: **27 facts clean, 6
flagged retracted** (five resting on the chocolate-hoax DOI, one on a
retracted hesperidin trial, PMID 31844967). Two subtleties visible in the
output: two papers carry Crossref *correction* notices that the checker
correctly reports as `notice-not-retraction` rather than lumping them in with
retractions, and PMID-keyed facts show `crossref — crossref indexes DOIs, and
this is a pmid` — the checker says what each source *could not* answer instead
of silently skipping it. The tool ends by printing its own scope caveat: this
is a labelled partial of the full retraction tier, and a flagged fact does
not yet propagate its flag to premises standing on it.

### `01-retraction-check.txt` — one identifier, three sources

The same check pointed at a single identifier: `verity.quality check
doi:10.3823/1654`. Output: verdict `retracted`, with each source's own reading
beside it, and then the line that keeps the agreement honest —

> a registry check cites record-id=17524 — that is a Retraction Watch record
> seen again, not a second source

Crossref's retraction notice for this DOI is itself sourced from Retraction
Watch (same record id), and OpenAlex ingests Crossref — so "three sources
agree" here means three sources were *consulted*, and the tool says so rather
than claiming independent corroboration it doesn't have.

### `02-spinach-render.txt` — the committed run

The premise tree for the spinach claim, rendered from the committed graph
(`data/demo/spinach.json`). How to read it: the header states **"Verity issues
no verdict on this claim. Every number below scores one step"** — that line is
the product's core design decision, printed on every render. Each premise row
shows the step's entailment score (`0.9995` here, tilde-marked as
uncalibrated), a `Δ if removed` column (unmeasured yet — shown as `—` rather
than faked), an evidence state, and a grounding status.

The result, honestly: **six premises, one step, depth 1, and nothing
grounds.** All six premises terminated `citation-shaped` (they are the kind of
statement a citation could settle — which makes them grounding targets, not
recursion candidates), and the binding stage reports `no-candidate-key 6`: the
decomposer volunteered no DOI or PMID, so there was nothing to look up in the
store. The footer is worth reading in full — the verifier prints its own
selection record (of 7 corruption families in its smoke set, it catches 2,
splits on 2, misses 3) and the sentence that keeps its high scores honest:
*"A high score means the step was not caught, not that the step is that
likely to hold."*

### `03-replay.txt` — reproducibility, with no key present

`verity replay` re-derives the committed run from its manifest: the clock is
pinned, the recorded LLM answers are replayed, the stage cache is off, and
each stage's output digest is compared against the stored run. The capture
shows all four stage digests matching and the verdict **`reproduced`** — with
`ANTHROPIC_API_KEY` unset and the working caches moved aside, so every answer
demonstrably came from the committed recordings. One printed note is worth
noticing: the replay says the store it read was overridden relative to the
one the run recorded — the tool reports the substitution rather than letting
it pass silently.

### `04-chocolate-attempt.txt` — the deepest tree, and the honest miss

The chocolate claim produced the demo's richest decomposition: **17 premises
across 3 steps, recursing to depth 3.** The recursion is visible in the
capture — the premise "the calories a serving supplies are fewer than the
intake reduction it produces" breaks down into a sub-tree of measurable
statements, and the comparison itself bottoms out in premises like *"180
kilocalories is less than 200 kilocalories"* and the general rule *"if A is
no greater than T and B is strictly greater than T, then A is less than B"*.
The termination accounting is printed beside the tree: 2 branches stopped at
the depth budget (`budget-exit`), 7 at citation-shaped statements, 6 at
statements marked `unverifiable-by-design` (definitions and arithmetic that
no citation could or should settle).

And the miss, kept deliberately: `no-candidate-key 17`. The decomposer
volunteered no identifier on any premise, so nothing bound, nothing grounded —
and the tree never touches the retracted chocolate-hoax DOI sitting six rows
deep in the very store this run read from. Grounding currently depends on the
decomposer happening to volunteer an identifier (two of the ten recorded
decompositions did), and this capture shows what a miss looks like instead of
re-rolling until it looked better. The retraction story therefore lives in
captures `00` and `01`, where it is systematic rather than luck-dependent.

## What the demo establishes — and what it doesn't

**Establishes:** the pipeline runs end to end on real claims; every premise
carries its own score from a verifier that prints its own blind spots;
recursion is bounded and every stop is accounted for; the retraction check
consults three sources and names shared provenance instead of inflating
agreement; the seed gate downgrades facts when registries disagree; and the
committed run reproduces byte-for-byte offline, key-free, on anyone's machine.

**Does not establish:** any evaluation result — the pre-registered thresholds
in `docs/evaluation.md` are unmeasured and every number here is a smoke test;
grounding — no capture shows a premise resolving against the store, because
no run in the demo window volunteered an identifier; calibration — the
verifier's scores are explicitly unanchored; and propagation — a retracted
fact does not yet flip the premises standing on it (that layer is designed,
not built).
