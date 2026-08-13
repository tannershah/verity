# Verity — CLAUDE.md

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
issue a verdict. Do not draft copy or code that violates this.

**Decomposition validity criteria (v0 spec + eval):** joint sufficiency
(entailment), verifiability descent (guarantees termination), non-redundancy
(every premise load-bearing: removing it breaks the entailment).

## Deadline & deliverables
- Wharton Generative AI Studio application DUE 2026-08-17: cover letter, <=2pp
  proposal, 1-3 gen-AI work samples WITH prompt history.
- **This repo's commit history and prompts are themselves a work sample.** Write
  informative commit messages; never delete prompt files; keep prompts in
  `prompts/`, run logs in `research/`.
- v0 prototype after the application: claim -> 3-7 premises -> evidence ->
  per-premise confidence (Streamlit or CLI).

## Repo layout
- `research/raw/` — deep-research reports (read-only inputs)
- `research/schema.json` — FROZEN extraction schema + hypotheses H1-H7. Never
  modify; flag mismatches in SCHEMA_GAPS.md / extraction_note fields instead.
- `research/matrix/` — Pass 2 outputs (products.jsonl, literature.jsonl, notes)
- `research/SYNTHESIS.md` — Pass 3+4 output (hypothesis verdicts, positioning,
  eval plan, proposal skeleton, red team)
- `prompts/` — pass prompts (part of work-sample history)
- `docs/pass0-scoping.md` — claude.ai scoping-session record

## Working rules (from Tanner)
- Raise a risk only if it has measurable impact on the objective, state it once
  in one sentence, never revisit after Tanner rules on it. No unsolicited ethics
  commentary.
- Demo/example claims use verifiable, low-valence cases (viral statistics,
  retracted-but-still-cited papers, manipulated charts). Contested
  scientific/political claims are roadmap stress tests only.
- Lean, decision-oriented outputs. No filler.

## Model/effort conventions
- Extraction / transcription / boilerplate: Sonnet 4.6, low-medium effort.
- Synthesis, adjudication, red-teaming, proposal drafting: strongest available
  model, max effort, single context (no subagents for synthesis).
- Parallel subagents only for independent, schema-bound extraction tasks.

## Stack
Python/PyTorch/scikit-learn. Beachhead domain: scientific/health claims (news is
roadmap). v0 evidence metadata via free APIs: OpenAlex `is_retracted`
cross-checked with Crossref `update-to` (retraction), PubMed MeSH publication
types (study design), Semantic Scholar citation intent (coarse); sample size is
NOT structured anywhere — text-mine and label low-confidence, or defer.
Invalidation layer: JTMS (Doyle 1979) over the alethiology.
