# Pass 2 — Structured Extraction (headless, Sonnet 4.6, low/medium effort)

You are running unattended in the Verity repo. Deep-research reports are in
`research/raw/` (report A = product landscape, report B = literature). The frozen
extraction schema is `research/schema.json`. Do not modify the schema.

## Tasks (in order)

1. Read `research/schema.json` fully before extracting anything.
   Then skim both reports once and write `research/matrix/SCHEMA_GAPS.md`:
   anything structurally unrepresentable in the schema (a product category,
   metadata type, or research area with no matching column/bucket/enum), or
   "none". Do NOT modify the schema — flag only. Then extract.
2. For EACH product in report A, emit one JSON object conforming to
   `feature_matrix_row` into `research/matrix/products.jsonl` (one object per line).
   - Every cell gets provenance {source_url, access_date, confidence}. If report A
     gives no source for a cell, mark confidence "inferred" and use the report
     itself as source. Never invent URLs.
   - If a value doesn't fit an allowed enum, use the closest enum and add an
     `extraction_note` field explaining the mismatch. Do not extend the enums.
3. For EACH paper in report B, emit one JSON object conforming to
   `literature_row` into `research/matrix/literature.jsonl`.
   - `not_handled_relative_to_verity` is mandatory; if the report doesn't state
     it, derive it from the method description and flag with
     `"derivation": "extractor-inferred"`.
4. Emit `research/matrix/sources.jsonl`: one object per unique URL cited in any
   provenance cell across both jsonl files — {url, access_date, confidence,
   cited_by: [row ids], verify_before_proposal: bool}. Set
   verify_before_proposal=true for anything tagged inferred/marketing-claim or
   flagged in the reports' own caveats (third-party pricing, low-reliability
   secondary sources). Dedupe by URL.
5. Spot-check pass: re-read all jsonl files, validate JSON parses line-by-line,
   verify enum conformance, list any rows you are <70% confident in inside
   `research/matrix/EXTRACTION_NOTES.md` along with any products/papers the
   reports mentioned but you skipped, and why.
6. Commit everything with message "pass2: structured extraction from deep research".

## Rules
- Extraction only. No synthesis, no hypothesis verdicts, no editorializing —
  that is Pass 3's job.
- If a report file is missing or empty, write what you found to
  EXTRACTION_NOTES.md, commit, and stop. Do not attempt web research to fill gaps.
- Stay inside the repo. Do not fetch external URLs.
