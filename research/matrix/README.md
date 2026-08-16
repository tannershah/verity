# The Matrix — Evidence Base

Structured extraction from the two deep-research reports in [../raw/](../raw/). Every claim in [docs/](../../docs/) traces to a row here.

| File | Rows | Contents |
|---|---|---|
| `schema.json` | — | Row schemas and the enum vocabulary |
| `products.jsonl` | 29 | Competitive landscape — 10 enum cells + per-cell provenance + extraction note |
| `literature.jsonl` | 34 | Papers across six buckets |
| `sources.jsonl` | 98 | URLs with access date and confidence |

Each product cell carries `{source_url, access_date, confidence}` so any claim can be traced to what it was read from.

```python
import json
rows = [json.loads(l) for l in open("research/matrix/products.jsonl")]
```

---

## Reading the data honestly

The schema was designed before extraction and not revised afterward, which keeps the extraction honest but leaves known mismatches. These affect interpretation:

**No `target_audience` field.** The consumer / professional / research distinction is load-bearing for H1 and is carried only in extraction notes. Loki and Full Fact straddle the boundary.

**`claim_decomposition` conflates detection with decomposition.** Identifying check-worthy sentences (Factiverse, Originality.ai, Full Fact) is not splitting a composite claim into load-bearing premises (Loki, SAFE, FActScore). Detection-only products code `none`, which loses that capability.

**Confidence tiers are too coarse.** `verified | inferred | marketing-claim` conflates verified-against-primary with corroborated-by-one-secondary — `product-024`'s cells were once marked verified by re-reading the same single secondary source they were inferred from. The finer vocabulary that should be used going forward: **verified-primary / corroborated-multi-secondary / single-secondary / inferred / marketing-claim**.

Also: `interactivity` is binary and can't express search interfaces vs. comparison views vs. API-only; `access_model` has no open-source bucket (Loki, SAFE, FActScore are mapped to `free`); `symmetric_contrasting_evidence` is binary and can't express partial symmetry (Penn MBD, Logically).

### Rows to treat with caution

| Row | Issue |
|---|---|
| `product-024` RedacTek | **All cells from one third-party review**; no vendor primary documentation. H7 and the invalidation differentiator rest on this row |
| `product-006` Perplexity | Nine of ten cells inferred from aggregator sources. Weakest row in the matrix |
| `product-012` FEVER | All cells inferred; source is the deep-research report itself |
| `product-015` ClaimBuster/Squash | All inferred; project wound down |
| `product-016` Full Fact AI | Internal/licensed tool, limited public documentation |
| `product-018` Logically | All inferred; accuracy figures are marketing claims |
| `product-022` RetractoBot | All inferred from a brief description plus the GitHub repo |
| `product-025`–`029` | Added in a single pass without a second look |
| `lit-002`, `-003`, `-004` | METGEN / IRGR / RLET — quantitative metrics not in the source report; extractor-inferred |
| `lit-008` Entailer | Dataset and metrics not specified in the source report |
| `lit-034` Belief Explorer | Single-pass; CHI 2026 extended abstract |

**Vendor and pricing figures are marketing claims, not verified:** scite pricing (`product-002`), Factiverse pricing and its "outperforming GPT-4" accuracy (`product-005`), Originality.ai's 86.69% accuracy (`product-007`), Logically's accuracy percentages (`product-018`).

**scite's index size is inconsistent across its own pages** — 1.6B+ Smart Citations on the features page vs. "over 1.8 billion unique citations" on the coverage page. Treat as approximate.

**19 URLs are cited by rows but missing from `sources.jsonl`** — see [open-questions.md](../../docs/open-questions.md).

---

## Row index

### Products

| ID | Product | | ID | Product |
|---|---|---|---|---|
| `product-001` | Ground News | | `product-016` | Full Fact AI |
| `product-002` | scite.ai | | `product-017` | Meedan Check |
| `product-003` | PolitiFact | | `product-018` | Logically / Logically Facts |
| `product-004` | Penn Media Bias Detector | | `product-019` | Kialo |
| `product-005` | Factiverse | | `product-020` | scite Reference Check |
| `product-006` | Perplexity | | `product-021` | Zotero + Retraction Watch |
| `product-007` | Originality.ai Fact-Check | | `product-022` | RetractoBot |
| `product-008` | Wolfram Alpha | | `product-023` | RetractionCheck / Crossref API |
| `product-009` | Loki / OpenFactVerification | | `product-024` | RedacTek |
| `product-010` | SAFE (Google DeepMind) | | `product-025` | Consensus |
| `product-011` | FActScore | | `product-026` | The Society Library |
| `product-012` | FEVER | | `product-027` | ARGUMEND |
| `product-013` | SciFact | | `product-028` | Elicit |
| `product-014` | AVeriTeC | | `product-029` | Community Notes (X) |
| `product-015` | ClaimBuster / Duke Squash | | | |

**Rows the hypotheses turn on:** `product-009` Loki (H1, H6) · `product-001` Ground News (falsified original H3) · `product-002` scite (H2, H6) · `product-024` RedacTek (H7) · `product-019`/`025`/`026`/`027` (H3 near-misses).

### Literature

| ID | Paper | Bucket |
|---|---|---|
| `lit-001` | Dalvi et al. 2021 — EntailmentBank | entailment-trees |
| `lit-002` | Hong et al. 2022 — METGEN | entailment-trees |
| `lit-003` | Ribeiro et al. 2022 — IRGR | entailment-trees |
| `lit-004` | Liu et al. 2022 — RLET | entailment-trees |
| `lit-005` | Yang, Deng & Chen 2022 — NLProofS | entailment-trees |
| `lit-006` | Kazemi et al. 2023 — LAMBADA | entailment-trees |
| `lit-007` | Tafjord et al. 2021 — ProofWriter | entailment-trees |
| `lit-008` | Tafjord et al. 2022 — Entailer | entailment-trees |
| `lit-009` | Weir, Clark & Van Durme 2024 — **NELLIE** | entailment-trees |
| `lit-010` | Min et al. 2023 — FActScore | claim-decomposition |
| `lit-011` | Wei et al. 2024 — SAFE | claim-decomposition |
| `lit-012` | Song, Kim & Iyyer 2024 — VeriScore | claim-decomposition |
| `lit-013` | Wanner et al. 2024 — DecompScore | claim-decomposition |
| `lit-014` | Wanner et al. 2025 — DnDScore | claim-decomposition |
| `lit-015` | Thorne et al. 2018 — FEVER | benchmarks |
| `lit-016` | Wadden et al. 2020 — SciFact | benchmarks |
| `lit-017` | Schlichtkrull et al. 2023 — AVeriTeC | benchmarks |
| `lit-018` | Nakshatri et al. 2025 — talking points | discourse |
| `lit-019` | Watts et al. 2024 — Penn Media Bias Detector | discourse |
| `lit-020` | Costello, Pennycook & Rand 2024 — DebunkBot *(Expression of Concern)* | belief-updating |
| `lit-021` | Costello et al. 2025 — "Just the facts" *(preprint)* | belief-updating |
| `lit-022` | Boissin et al. 2025 — PNAS Nexus | belief-updating |
| `lit-023` | 2025 — no lasting discernment skills | belief-updating |
| `lit-024` | Costello et al. 2026 — dual-use persuasion | belief-updating |
| `lit-025` | Carlson / Mitchell et al. — NELL | knowledge-substrate |
| `lit-026` | Doyle 1979 — **JTMS** | knowledge-substrate |
| `lit-027` | de Kleer 1986 — ATMS | knowledge-substrate |
| `lit-028` | Nicholson et al. 2021 — scite | knowledge-substrate |
| `lit-029` | Zhang et al. 2025 — CACDD | claim-decomposition |
| `lit-030` | Mitra et al. 2025 — FactLens | claim-decomposition |
| `lit-031` | VITALITY Study I 2025 — retraction **impact** | knowledge-substrate |
| `lit-032` | Meyer et al. 2024 — street epistemologist | belief-updating |
| `lit-033` | RetractoBot RCT 2025 — retraction **uptake** (null) | knowledge-substrate |
| `lit-034` | Belief Explorer 2026 — H5 watch item | belief-updating |
