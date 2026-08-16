# Verity — CLAUDE.md

**⏱ ACTIVE SPRINT (temporary — remove this block after the 2026-08-17 submission):**
read `SPRINT.md` before starting any work. It scopes, re-orders, and assigns
`docs/build-plan.md` tiers for this window; where they differ, SPRINT.md wins until
it is deleted.

Epistemic transparency engine. Input: text containing claims. Pipeline: recursively
decompose each claim into load-bearing premises (backward chaining — premises
jointly entail the claim, each easier to verify), check premises against the
alethiology (persistent KB of verified facts, "aletheia"; cf. entailment-tree /
NELLIE line), agentic retrieval for unknown premises, per-premise evidence-quality
metadata (study design, N, retraction status, supporting vs contrasting citations),
rendered as inspectable confidence/bias graphs.

**Verdict boundary (core design decision):** verdicts exist only at the leaves —
verified premises in the alethiology. Contested composite claims get
transparency-only treatment: surface evidence and critiques on all sides, never
issue a verdict. Do not draft copy or code that violates this. The substantive
commitment is no editorial adjudication where evidence conflicts; no root aggregate
is ever displayed.

**Decomposition validity criteria (v0 spec + eval):** joint sufficiency
(entailment), verifiability descent (termination enforced by depth budget;
grounding rate, depth, and budget-exit rate measured and reported), non-redundancy
(every premise load-bearing: removing it breaks the entailment).

**Display constraint:** render per-premise verifier confidence, never tree-level
polish alone.

**Demo-claim valence rule:** demo/example claims use verifiable, low-valence cases
(viral statistics, retracted-but-still-cited papers, manipulated charts). Contested
scientific/political claims are roadmap stress tests only.

- v0 prototype: claim -> 3-7 premises -> evidence -> per-premise confidence
  (CLI first, then Streamlit).

## Where to look

Substance lives in `docs/`. Do not duplicate it here; do not trust a summary here
over the owning document.

| Question | File |
|---|---|
| What are we building? Data model, build plan | `docs/design.md` |
| How do we build it? Modules, tiers, ordering | `docs/build-plan.md` |
| What do we claim is missing from the landscape? | `docs/hypotheses.md` |
| How do we position and cite? | `docs/positioning.md` |
| How do we evaluate, and against what thresholds? | `docs/evaluation.md` |
| What is undecided or unverified? | `docs/open-questions.md` |
| The underlying evidence | `research/matrix/` |

## Repo layout
- `docs/` — current thinking; amend in place
- `research/raw/` — the two deep-research reports and source lists (read-only)
- `research/matrix/` — structured extraction: `products.jsonl`,
  `literature.jsonl`, `sources.jsonl`, `schema.json`. Every claim in `docs/`
  cites a row by ID. Known limitations and low-confidence rows are documented in
  `research/matrix/README.md` — read it before leaning on a row.

Git carries the history. Do not add change logs, pass records, or process
narration to the repository.

## Working rules (from Tanner)
- Never modify these rules yourself
- Be questioning, curious, and skeptical. If something seems off, explore and alert. This is a fully agent-driven project, so drifting, assumptions, and random garbage can become ingrained in the codebase. We want to prevent this as much as possible. The research, planning, and theory of this system is also agent-generated, so do NOT see this as golden truth but as something that must be iterated on and constantly reimagined.
- Raise a risk only if it is directly relevant to Verity or your current task.
- Lean, decision-oriented outputs. No filler.
- Do not set arbitrary deadlines, timeframes, or gates unless specifically told to do so. 
- Do not set arbitrary rules for yourself or the project without directly consulting Tanner beforehand, especially absolute ones with universal quantifiers
- Report and Remove any vestigial artifacts serving no purpose you come across during your work
- Build for production-level design, organization, and maintainability. 
- After completing the task you were given, review this file, README.md, and the files in /docs for changes, so they are kept up to date. Changes to these files should keep them fresh, lean, and agnostic to the modifications you just made, meaning do not make any references in a corrective/risk-averse way that would signify some sort of patch. These are CLAUDE.md, README.md, and documentation files built to be production-grade, not change logs, version histories, or record books. Also, unless otherwise instructed, do not modify areas of the files that your task did not pertain to.

## Model/effort conventions
- Extraction / transcription / boilerplate: Sonnet 4.6, low-medium effort.
- Synthesis, adjudication, red-teaming, proposal drafting: strongest available model, max effort.

## Stack
Python/PyTorch/scikit-learn. Beachhead domain: scientific/health claims (news is
roadmap). v0 evidence metadata via free APIs: OpenAlex `is_retracted`
cross-checked with Crossref `update-to` (retraction; the cross-check is required —
OpenAlex collapses update types and has a known false-positive history), PubMed
MeSH publication types (study design), Semantic Scholar citation intent (coarse);
sample size is structured only for registered trials (ClinicalTrials.gov
enrollment, linked from PubMed) — text-mine elsewhere and label model-extracted.
OpenAlex needs a free registered key; Crossref and ClinicalTrials.gov need none.
Claim-side LLM calls: provider-agnostic adapter, Claude API default; NLI and
embedding models run locally. Invalidation layer: JTMS (Doyle 1979) over the
alethiology.
