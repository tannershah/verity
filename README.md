# Verity

**An epistemic transparency engine.** Input: text containing claims. Verity recursively decomposes each claim into its load-bearing premises, checks those premises against a persistent store of verified facts, retrieves evidence for the ones it doesn't know, attaches evidence-quality metadata to every premise, and renders the result as an inspectable graph — never as a verdict on the composite claim.

A reader confronting "X causes Y" should be able to see *which premises the claim stands on*, *how strong the evidence under each one is*, and *whether a load-bearing source has been retracted*.

```
claim
  └─▶ backward-chaining decomposition ──▶ 3–7 load-bearing premises
        │                                   verifier gate scores every step
        ├─▶ premise known?  ──yes──▶ alethiology (persistent verified-fact KB)
        │                    ──no───▶ agentic retrieval (OpenAlex · Crossref · PubMed · Semantic Scholar)
        ├─▶ evidence-quality metadata attached per premise
        ├─▶ JTMS: retract a leaf ──▶ dependents flip OUT ──▶ affected graphs re-render flagged
        └─▶ render: per-premise confidence · symmetric evidence · no root aggregate
```

---

## Arriving from the application?

Three places to look, in order:

1. **This page** — what exists right now, what doesn't yet, and how to see it run.
2. **[PROMPT_HISTORY.md](PROMPT_HISTORY.md)** — how this was built. The project is almost entirely agent-built: research passes, an adversarial "examining committee" audit, and scripted worker/red-team build loops. Every prompt quoted there is the literal text that was sent, recovered from git history and run artifacts.
3. **[demo/](demo/README.md)** — captured terminal output from the demo, with a guide explaining what each capture shows. You can read the results without installing anything.

The two-page proposal describes the vision; this repository is the v0 prototype of it, as of **2026-08-17**.

---

## What works today — and what doesn't yet

**Working, end to end:**

- **Decomposition.** A claim becomes 3–7 load-bearing premises by backward chaining (an LLM proposes premises that jointly entail the claim; malformed proposals are refused and counted, never silently repaired). The descent recurses on premise types that warrant it, bounded by depth and node budgets, and **every leaf records why it stopped** — grounded, no source could settle it, budget ran out, a cap bit, or the decomposition was refused.
- **Per-premise verification.** A locally-run entailment model scores every decomposition step. The checkpoint was picked by a committed bake-off whose decision rule was fixed before the numbers existed; it ships **labeled uncalibrated**, and the terminal render prints what it catches and what it misses, derived from the [selection record](data/verifier/README.md) rather than described.
- **A seeded fact store ("alethiology").** 33 curated, source-verified facts, loaded offline against committed registry records. A premise carrying an exact DOI or PMID resolves against it; when it doesn't, the store says which of the reasons it was.
- **A three-source retraction check.** Every identifier in the store is checked against Retraction Watch, Crossref, and OpenAlex; six facts come back flagged. When sources agree, the tool reports whether the "agreement" is actually one primary record seen through three windows — see [demo/01-retraction-check.txt](demo/01-retraction-check.txt) for the retracted chocolate-hoax paper.
- **An honest render.** The terminal view shows the premise tree with one verifier score per step, grounding status, and a termination reason per leaf. **No aggregate score for the whole claim is ever computed or displayed** — that is a design decision enforced by tests, not a missing feature.
- **Reproducibility.** The committed demo run replays **offline, with no API key**, byte-stable: recorded LLM answers and registry responses are committed, and `verity replay` re-derives the run and compares every stage digest. See [demo/03-replay.txt](demo/03-replay.txt).

**Not built yet (stated here so the demo can't oversell):**

- **No evaluation numbers.** The thresholds in [docs/evaluation.md](docs/evaluation.md) are pre-registered but unmeasured; the metrics harness is unbuilt. Every number the demo shows is a smoke test, not a result.
- **Retrieval doesn't fill the tree yet.** The evidence and retraction columns of a rendered tree stay empty until agentic retrieval (build-plan M6) lands; today the retraction check lives on the fact store, not on freshly-retrieved evidence.
- **Grounding is luck-dependent.** Until identifiers are bound from retrieval, a premise only grounds if the decomposer happens to volunteer a DOI — two of the ten recorded decompositions did. The committed demo run grounds nothing, and [demo/04-chocolate-attempt.txt](demo/04-chocolate-attempt.txt) shows two live attempts missing — kept deliberately, because the variance is the finding.
- **No propagation yet.** The dependency-tracked invalidation layer (retract a leaf → dependents flip) is designed (JTMS) but not implemented.
- **CLI only.** The v0 surface is the terminal; a Streamlit view is roadmap.

---

## See it run

Setup (Python 3.12):

```bash
uv venv --python 3.12 && uv pip install -e ".[dev]"
cp .env.example .env    # keys only needed for live runs; the demo below needs none
```

Then four commands, all offline and free:

```bash
python -m verity.alethiology seed        # load the curated fact store (offline, deterministic)
python -m verity.quality apply           # three-source retraction check onto every fact
python -m verity render data/demo/spinach.json          # draw the committed premise tree
python -m verity.quality check doi:10.3823/1654         # the retracted-paper verdict, source by source
```

And the reproducibility beat — replay the committed run with no API key:

```bash
python -m verity runs --db data/demo/store.db            # list the recorded run
python -m verity replay <run_id> --db data/demo/store.db # re-derive it; every digest must match
```

Expected output for each is captured in [demo/](demo/README.md). To run the pipeline live on a new claim (`python -m verity run "<claim>"`), put an Anthropic API key in `.env` — a run costs a few cents; a second run of the same claim spends nothing and returns a byte-identical graph.

The entailment scorer is an opt-in extra — `uv pip install -e ".[dev,verifier]"` adds torch and pulls the ~2GB checkpoint on first use; without it the suite still runs green and says why it skipped. `pytest` runs the whole suite offline against committed fixtures.

---

## Where everything lives

| Question | Document |
|---|---|
| How was this built? Prompt-by-prompt history | [PROMPT_HISTORY.md](PROMPT_HISTORY.md) |
| What does the demo show? | [demo/](demo/README.md) |
| What are we building? Data model, constraints | [docs/design.md](docs/design.md) |
| How do we build it? Modules, tiers, ordering | [docs/build-plan.md](docs/build-plan.md) |
| What do we claim is missing from the landscape, and why? | [docs/hypotheses.md](docs/hypotheses.md) |
| How do we position and cite? | [docs/positioning.md](docs/positioning.md) |
| How do we evaluate, and against what thresholds? | [docs/evaluation.md](docs/evaluation.md) |
| What is undecided or unverified? | [docs/open-questions.md](docs/open-questions.md) |
| The underlying research evidence | [research/matrix/](research/matrix/README.md) |

```
src/verity/models/    the claim graph, facts, evidence, run manifests, and the render projection
src/verity/store/     SQLite persistence — JSON payload authoritative, schema versioned
src/verity/llm/       provider-agnostic adapter (Claude default), a scripted stub, and the cassette
src/verity/orchestration/  the pipeline: four stages, the stage cache, the manifest, replay
src/verity/decomposition/  backward chaining — one step, and the bounded descent that drives it
src/verity/alethiology/  fact-store policy: exact-key grounding, the curated seed and its gate
src/verity/verifier/  the entailment gate: one score per step, and the smoke set that picked the model
src/verity/retrieval/ registry clients over a cached, rate-limited, credit-budgeted transport
src/verity/quality/   evidence quality — the three-source retraction check, and so far nothing else
src/verity/presentation/  the terminal render — tree layout and the scorer's own caveat
seed/                 the curated facts and the key-resolution record they were checked against
data/demo/            one real graph and the store that produced it, committed for keyless replay
data/verifier/        the pilot decompositions, the smoke set, and the champion-selection record
demo/                 captured demo output a reader can inspect without running anything
tests/                enforcement tests for the hard constraints, plus the round-trip suite
tests/fixtures/       recorded registry and LLM responses — the suite runs with no network
docs/                 current thinking — design, hypotheses, positioning, evaluation, open questions
research/             two deep-research reports and a structured extraction: 29 products · 34 papers · 98 sources
```

`docs/` is where decisions live. `research/` is the evidence they rest on — every claim in `docs/` cites a matrix row by ID.

---

## What the committed graph does and does not show

It is one unedited run, stamped with the run id and configuration hash that produced it, and it is a descent artifact: every leaf records why it stopped, and the run reports its own fan-out and termination mix beside the tree. **How deep the tree goes is a fact about the decomposer, not about the descent.** Recursion runs on the premise types the configured predicate names — `statistical` by default, since a premise typed `empirical-citable` *is* the grounding target and one typed `definitional` or `background` is what no identifier can settle — so a claim whose premises are all citable in one step produces a shallow tree, and the render says so rather than hiding it. **No premise in this graph grounds**: every leaf stopped at `no-candidate-key`. Until M6-T3 binds identifiers from retrieval, grounding depends on the decomposer volunteering a key, and most decompositions don't — of the ten recorded so far, two proposed one, and the run this graph replaced was among the two, so grounding presence varies run to run and a re-record rolls that die. When a run does ground this way it is still **not** the pre-registered measurement in [evaluation.md](docs/evaluation.md) §2: a decomposer-proposed identifier is circular, and such a run says so in its own notes. The seeded store behind the graph is the surface that does not vary: 33 verified facts checked against all three retraction sources, six flagged. The evidence and retraction columns of this tree stay empty until retrieval fills them.

Two cache layers stand behind the "second run is free" behavior: a cassette records what the *provider said*, and a stage cache records what a *stage concluded*, keyed on a digest of the whole source tree — the conservative choice re-runs deterministic code for free rather than serving a graph built by rules that no longer exist. Grounding is never cached, because the fact store can change underneath a stored graph; a replay that finds it has says exactly that.

---

## The constraints that bind everything

Stated in full in [docs/design.md](docs/design.md) §3. Code or copy that violates them is wrong.

**The verdict boundary.** Verdicts exist only at the leaves. Contested composites get transparency-only treatment. **No root aggregate is ever displayed.** The substantive commitment is *no editorial adjudication where evidence conflicts*.

**Decomposition validity criteria.** Joint sufficiency (premises jointly entail the claim) · verifiability descent (**termination enforced by depth budget**, with grounding rate, depth, and budget-exit rate measured and reported) · non-redundancy (every premise load-bearing).

**Display constraint.** Render per-premise verifier confidence, never tree-level polish alone. At the 80% per-step threshold, only ~33% of five-premise trees are fully clean.

**Demo-claim valence rule.** Verifiable, low-valence cases — viral statistics, retracted-but-still-cited papers, manipulated charts. Contested scientific and political claims are roadmap stress tests only.

---

## Positioning in one paragraph

Every ingredient ships somewhere today; the conjunction does not. Automatic decomposition ships in Loki — into independent atomic facts, verdict-oriented. Study-level evidence metadata ships in scite — per citation statement, no argument layer above it. Symmetric no-verdict presentation ships in Ground News — at article level, never below. Persistent fact stores ship in Wolfram's Knowledgebase and the ClaimReview caches — none dependency-tracked. The conjunction is load-bearing rather than gerrymandered because the layers only function together: retraction propagation needs entailment-linked premises to propagate *along*, and per-premise evidence quality only matters when premises are load-bearing. Full argument, adjacent-product landscape, and citation discipline in [docs/positioning.md](docs/positioning.md).

---

## Stack

Python / PyTorch / scikit-learn. v0 surface: CLI first, then Streamlit. Claim-side LLM calls go through a provider-agnostic adapter (Claude API default); NLI and embedding models run locally. Invalidation layer: JTMS (Doyle 1979) over the alethiology. Evidence metadata from free APIs — OpenAlex cross-checked against Crossref for retraction, PubMed MeSH for study design, Semantic Scholar for citation intent, ClinicalTrials.gov for registered-trial enrollment. Beachhead domain: scientific and health claims; news is roadmap.
