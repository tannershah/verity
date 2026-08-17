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

**Status:** spine in place — typed data model, SQLite persistence with forward migration, config and secrets handling, LLM adapter, run manifests. The pipeline is orchestrated: four composable stages with content-hash caching, a run manifest that records what each one was given and what it returned, failure isolation that yields a partial graph rather than a crash, and replay that re-derives a recorded run instead of reading it back. The alethiology is seeded and grounding works: a premise carrying an exact DOI or PMID resolves to a verified fact, and when it doesn't, the store says which of the reasons it was. Backward chaining descends: a claim becomes a tree of steps, bounded by a depth budget and a node cap, and every leaf records why it stopped — a source could settle it, none could, the budget ran out, a cap bit, or the decomposition was refused. A local entailment scorer scores every step, labelled uncalibrated — the checkpoint was picked by a committed bake-off whose decision rule was fixed before the numbers existed, and whose [record](data/verifier/README.md) states what the winner still gets wrong. Retrieval reaches OpenAlex and Crossref through a client that caches to disk, reads each source's rate limit off its own responses, and refuses to spend past a credit floor — and it proves its credential reached the pool it pays for, because header authentication otherwise fails open onto an anonymous allowance. Every registry response the seed rests on is recorded and committed, so the suite runs offline and a swapped parser has to reproduce the corpus tier-for-tier. The hard constraints are enforced by the types rather than by convention, so a violation is a build failure: see [tests/](tests/). A claim renders in the terminal as its premise tree, one score per step beside the grounding, evidence and termination columns each producer fills as it lands — and the footer says what the checkpoint behind those numbers catches and what it misses, derived from its selection record rather than described. No evaluation number exists yet: the pre-registered thresholds in [docs/evaluation.md](docs/evaluation.md) are unmeasured, the grounding rate is not yet judged, and the metrics harness that will compute them is not built (build-plan M10). Beachhead is scientific and health claims; news is roadmap.

---

## Start here

| Question | Document |
|---|---|
| What are we building? Data model, constraints, build plan | [docs/design.md](docs/design.md) |
| How do we build it? Modules, tiers, session ordering | [docs/build-plan.md](docs/build-plan.md) |
| What do we claim is missing from the landscape, and why? | [docs/hypotheses.md](docs/hypotheses.md) |
| How do we position and cite? | [docs/positioning.md](docs/positioning.md) |
| How do we evaluate it, and against what thresholds? | [docs/evaluation.md](docs/evaluation.md) |
| What's undecided or unverified? | [docs/open-questions.md](docs/open-questions.md) |
| What's the underlying evidence? | [research/matrix/](research/matrix/README.md) |

---

## Layout

```
src/verity/models/    the claim graph, facts, evidence, run manifests, and the render projection
src/verity/store/     SQLite persistence — JSON payload authoritative, columns derived, schema versioned
src/verity/llm/       provider-agnostic adapter (Claude default), a scripted stub, and the cassette
src/verity/orchestration/  the pipeline: four stages, the stage cache, the manifest, replay
src/verity/decomposition/  backward chaining — one step, and the bounded descent that drives it; the prompt is one file
src/verity/alethiology/  fact-store policy: exact-key grounding, the curated seed and its gate
src/verity/verifier/  the entailment gate: one score per step, two backends, the smoke set that picked between them
src/verity/retrieval/ registry clients over a cached, rate-limited, credit-budgeted transport
src/verity/quality/   evidence quality — the three-source retraction check, and so far nothing else
src/verity/presentation/  the terminal render — tree layout and the scorer's own caveat
src/verity/           the CLI entry point, plus keys, ids, config, secrets, thresholds, and the content-addressed store the recordings live in
seed/                 the curated facts and the key-resolution record they were checked against
data/demo/            one real graph and the store that produced it, committed so render and replay run on a fresh clone with no key
data/verifier/        the pilot decompositions, the review that ruled on them, the smoke set built from both, and the selection record
demo/                 terminal captures of the demo commands, committed so a reader sees the output without running anything
tests/                enforcement tests for the hard constraints, plus the round-trip suite
tests/fixtures/       recorded registry responses — verbatim, so the suite needs no network
docs/                 current thinking — design, hypotheses, positioning, evaluation, open questions
research/raw/         the two deep-research reports and their source lists
research/matrix/      structured extraction: 29 products · 34 papers · 98 sources, with per-cell provenance
```

`docs/` is where decisions live. `research/` is the evidence they rest on — every claim in `docs/` cites a row by ID (`product-009`, `lit-005`).

Setup: `uv venv --python 3.12 && uv pip install -e ".[dev]"`, then `cp .env.example .env` and fill in the keys. The entailment scorer is an opt-in extra — `uv pip install -e ".[dev,verifier]"` adds torch and pulls the ~2GB champion checkpoint on first use (the bake-off loads both candidates, ~5GB); without it the suite still runs green and the model-layer test says why it skipped. `pytest` runs the suite offline and spends nothing; `pytest -m live` opts into the calls that check the registry contracts are still what we recorded.

**Building the store takes two commands, in this order.** `python -m verity.alethiology seed` loads the curated facts — offline and deterministic, against a committed record of what each registry returned; what that gate refuses, and why, is in [seed/README.md](seed/README.md). Then `python -m verity.quality apply` checks every identifier in the store against all three retraction sources and writes what they said onto the facts. **Seeding alone leaves the retraction column empty**, because a seeded fact records that nobody has checked it yet rather than that it is clean — so a store that skipped the second command renders a clean tree over a retracted source. Both are offline and free: the committed fixtures answer for every key in the corpus, and `--live` is the opt-in that spends credits.

`python -m verity.quality check doi:10.3823/1654` runs the same check on one identifier and prints what each source returned beside the verdict, writing nothing. `python -m verity.retrieval resolve doi:10.3823/1654` shows the underlying readings, and `record --from-seed` re-records the fixtures the corpus is checked against.

The render is where the pipeline becomes readable. `python -m verity render data/demo/spinach.json` draws a committed graph and costs nothing — no key, no checkpoint, no network — and `--json` writes the render payload to stdout with the view on stderr. `python -m verity run "<claim>"` runs the pipeline for one claim instead: decompose, score every step, bind the identifiers a registry resolves, ground what binds, store, render. The first such run spends an LLM call; **a second run of the same claim spends nothing and returns a byte-identical graph**, because every stage that may be cached is, and the two that may not — binding, which caches at the transport, and grounding, which must not be cached at all — say why in the run's own record. `python -m verity runs` lists what has been run, and `python -m verity replay <run_id>` re-derives one from its manifest: the clock is pinned, the provider's recorded answers are replayed, the stage cache is switched off, and the result is compared stage by stage. A decomposition, scoring or binding digest that moved is drift and fails; a grounding that moved is the alethiology having changed under a stored graph, which is reported as exactly that. The committed demo ships this whole chain: `python -m verity runs --db data/demo/store.db` lists the recorded run, and `replay` against the same `--db` re-derives it on a fresh clone with no key — the recordings under `tests/fixtures/recordings/` answer for the provider.

`--out data/demo/spinach.json` is how the committed graph is re-recorded — the decomposer is not deterministic, so a fresh run replaces it rather than reproducing it.

Both caches live under `.cache/`, and the two are disposable in different senses. The stage cache keys on a digest of the whole source tree, so deleting it costs a re-run of deterministic code and can never change an answer. The cassette holds the provider's recorded answers, which is the money: deleting it means the next run calls the model again, and the decomposer is not deterministic, so that run can reach a different tree. Committed recordings under `tests/fixtures/recordings/` are read behind the working cache and survive the delete. `--no-cache` recomputes every stage without deleting anything.

**What the committed graph does and does not show.** It is one unedited run, stamped with the run id and configuration hash that produced it, and it is a descent artifact: every leaf records why it stopped, and the run reports its own fan-out and termination mix beside the tree. **How deep the tree goes is a fact about the decomposer, not about the descent.** Recursion runs on the premise types the configured predicate names — `statistical` by default, since a premise typed `empirical-citable` *is* the grounding target and one typed `definitional` or `background` is what no identifier can settle — so a claim whose premises are all citable in one step produces a shallow tree, and the render says so rather than hiding it. **No premise in this graph grounds**: every leaf stopped at `no-candidate-key`. Until M6-T3 binds identifiers from retrieval, grounding depends on the decomposer volunteering a key, and most decompositions don't — of the ten recorded so far, two proposed one, and the run this graph replaced was among the two, so grounding presence varies run to run and a re-record rolls that die. When a run does ground this way it is still **not** the pre-registered measurement in [evaluation.md](docs/evaluation.md) §2: a decomposer-proposed identifier is circular, and such a run says so in its own notes. The seeded store behind the graph is the surface that does not vary: 33 verified facts checked against all three retraction sources, six flagged — `python -m verity.quality check doi:10.3823/1654` prints the three-source verdict on the retracted chocolate-hoax paper beside what each source returned. The evidence and retraction columns of this tree stay empty until retrieval fills them.

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

Python / PyTorch / scikit-learn. v0 surface: CLI first, then Streamlit. Claim-side LLM calls go through a provider-agnostic adapter (Claude API default); NLI and embedding models run locally. Invalidation layer: JTMS (Doyle 1979) over the alethiology. Evidence metadata from free APIs — OpenAlex cross-checked against Crossref for retraction, PubMed MeSH for study design, Semantic Scholar for citation intent, ClinicalTrials.gov for registered-trial enrollment.
