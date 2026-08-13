# Work Samples — Manifest

**Sample 1 — Verity research pipeline (this repository).** A multi-pass competitive and literature analysis produced entirely with generative AI under a frozen extraction schema: deep-research sweeps, schema-bound extraction into a provenance-carrying matrix, hypothesis adjudication, an independent red-team pass, and post-red-team remediation with targeted existence searches. Read it in commit order: prompts in `prompts/` (one file per pass), outputs in `research/` (the matrix, `SYNTHESIS.md` with the red team appended, remediation logs). The prompt-history requirement is satisfied by `prompts/` plus the commit log — every pass's instructions and outputs are versioned together.

**Sample 2 — Verity v0 prototype.** `[TODO-16th: repo link + demo]` Claim → 3–7 premises → evidence → per-premise confidence (Streamlit), built via Claude Code; the build prompt history ships with the repo.

**Sample 3 (optional — Tanner's call) — CIS 5190 political-bias detector.** Include only if non-generative-AI-adjacent samples are permitted, or reframe it through its generative-AI comparison: the three-class classifier that beat a GPT-4 baseline.
