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

**Status:** spine in place — typed data model, SQLite persistence with forward migration, config and secrets handling, LLM adapter, run manifests. The alethiology is seeded and grounding works: a premise carrying an exact DOI or PMID resolves to a verified fact, and when it doesn't, the store says which of the reasons it was. Backward chaining produces steps, and a local entailment scorer scores every one of them, labelled uncalibrated — the checkpoint was picked by a committed bake-off whose decision rule was fixed before the numbers existed, and whose [record](data/verifier/README.md) states what the winner still gets wrong. Retrieval reaches OpenAlex and Crossref through a client that caches to disk, reads each source's rate limit off its own responses, and refuses to spend past a credit floor — and it proves its credential reached the pool it pays for, because header authentication otherwise fails open onto an anonymous allowance. Every registry response the seed rests on is recorded and committed, so the suite runs offline and a swapped parser has to reproduce the corpus tier-for-tier. The hard constraints are enforced by the types rather than by convention, so a violation is a build failure: see [tests/](tests/). Rendering is in progress. Beachhead is scientific and health claims; news is roadmap.

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
src/verity/llm/       provider-agnostic adapter (Claude default) and a scripted stub
src/verity/decomposition/  backward chaining — one step, recursion-shaped; the prompt is one file
src/verity/alethiology/  fact-store policy: exact-key grounding, the curated seed and its gate
src/verity/verifier/  the entailment gate: one score per step, two backends, the smoke set that picked between them
src/verity/retrieval/ registry clients over a cached, rate-limited, credit-budgeted transport
src/verity/           keys, ids, config, secrets, thresholds, and one package per unbuilt module
seed/                 the curated facts and the key-resolution record they were checked against
data/verifier/        the smoke set, the decomposition review it rests on, and the selection record
tests/                enforcement tests for the hard constraints, plus the round-trip suite
tests/fixtures/       recorded registry responses — verbatim, so the suite needs no network
docs/                 current thinking — design, hypotheses, positioning, evaluation, open questions
research/raw/         the two deep-research reports and their source lists
research/matrix/      structured extraction: 29 products · 34 papers · 98 sources, with per-cell provenance
```

`docs/` is where decisions live. `research/` is the evidence they rest on — every claim in `docs/` cites a row by ID (`product-009`, `lit-005`).

Setup: `uv venv --python 3.12 && uv pip install -e ".[dev]"`, then `cp .env.example .env` and fill in the keys. The entailment scorer is an opt-in extra — `uv pip install -e ".[dev,verifier]"` adds torch and pulls ~2GB of checkpoint on first use; without it the suite still runs green and the model-layer test says why it skipped. `pytest` runs the suite offline and spends nothing; `pytest -m live` opts into the calls that check the registry contracts are still what we recorded. `python -m verity.alethiology seed` loads the curated facts into the store — offline and deterministic, against a committed record of what each registry returned. What that gate refuses, and why, is in [seed/README.md](seed/README.md). `python -m verity.retrieval resolve doi:10.3823/1654` shows what each source says about one identifier, and `record --from-seed` re-records the fixtures the corpus is checked against.

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
