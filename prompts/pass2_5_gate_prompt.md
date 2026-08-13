# Pass 2.5 — Extraction Gate Check (Sonnet 4.6, low effort, read-mostly)

You are verifying Pass 2's extraction in the Verity repo before synthesis runs.
This is a CHECK, not a redo. Do not modify `research/schema.json`, do not
re-extract, do not editorialize. You may make surgical fixes only where a check
below fails, and every fix must be listed in the report.

Inputs: `research/matrix/products.jsonl`, `research/matrix/literature.jsonl`,
`research/matrix/EXTRACTION_NOTES.md`, `research/raw/` (ground truth).

Output: `research/matrix/GATE_REPORT.md` with one PASS/FAIL line per check
plus evidence (the actual grep/count results or quoted JSON fragments), a
"Fixes applied" section (or "none"), and a final line:
`VERDICT: CLEAR FOR PASS 3` or `VERDICT: BLOCKED — <reason>`.

## Checks

### 1. Row count and roster (products.jsonl)
- Count lines; confirm valid JSON per line.
- List every `product` value. Confirm each appears exactly once (no dupes).
- Reconcile against report A: 8 main products (Ground News, scite.ai,
  PolitiFact, Penn Media Bias Detector, Factiverse, Perplexity, Originality.ai,
  Wolfram Alpha), the additional-systems section (Loki/OpenFactVerification,
  SAFE, FActScore, FEVER/SciFact/AVeriTeC entries, ClaimBuster/Squash,
  Full Fact, Meedan, Logically, Kialo), and the retraction tools (scite
  Reference Check, Zotero+RW, RetractoBot, RetractionCheck, RedacTek).
  FAIL if any named system is missing or duplicated; add a missing row from
  report A (with provenance) as a fix.

### 2. Adversary rows carry their qualifications
These three rows are load-bearing for hypothesis adjudication. For each,
quote the relevant field values in the report:
- **Loki/OpenFactVerification** (adversary to H1): row must encode BOTH
  (i) decomposition into independent atomic claims, NOT entailment-linked
  load-bearing premises, and (ii) verdict-oriented / human-in-the-loop verdict
  — in enum values plus `extraction_note` if the enums cannot express it.
- **RedacTek** (adversary to H7): row must encode paper-level 3-generation
  retraction-risk scoring, NOT claim-level invalidation.
- **scite.ai** (adversary to H2/H6): row must encode citation-statement-level
  operation with no argument/premise layer.
FAIL if a qualification exists only in the raw reports; fix by adding the
missing `extraction_note` sourced from report A's wording.

### 3. Load-bearing literature rows
- **DebunkBot / Costello et al. 2024**: `finding_status` present, value
  expression-of-concern, dated June 11 2026 (Science). Also confirm the
  supporting replications (PNAS Nexus 2025; "Just the facts" mechanism
  preprint) appear as rows or are named in a row.
- **EntailmentBank**: `metrics_and_best_numbers` names the four dimensions
  (Leaves / Steps / Intermediates / Overall-AllCorrect).
FAIL and fix from report B if either is missing/wrong.

### 4. Skipped-papers audit (EXTRACTION_NOTES.md)
- List every skipped paper and its stated reason.
- FAIL if any of the following were skipped: NELLIE, LAMBADA, NLProofS,
  Wanner et al. 2024 (DecompScore), DnDScore, Doyle 1979 (JTMS),
  de Kleer 1986 (ATMS), VeriScore. Fix by extracting the missing row from
  report B.
- Peripheral belief-updating extensions (Hornsey, Bretter, Czarnek, Hou) and
  minor method baselines are acceptable skips — note, do not add.

### 5. Sources file integrity (sources.jsonl)
- Count entries; confirm valid JSON per line; confirm no duplicate URLs.
- Confirm every URL appearing in a products.jsonl or literature.jsonl
  provenance cell appears in sources.jsonl (spot-check 10 random cells if a
  full join is impractical, and say which method you used).
- Do NOT verify the flagged sources' content — that is deferred until after
  Pass 3 by design.

## Rules
- Read-mostly; fixes only where a check FAILs, each logged with a one-line
  rationale and the report-A/B passage it came from.
- If a check is ambiguous, mark AMBIGUOUS with the evidence and leave the
  decision to Tanner — do not guess.
- Commit with message "pass2.5: extraction gate check" (include GATE_REPORT.md
  and any fixed rows).
