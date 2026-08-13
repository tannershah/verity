# EXTRACTION_NOTES.md — Pass 2 spot-check results

All three JSONL files validate: 24 product rows, 28 literature rows, 96 source rows; all JSON parses line-by-line; all enum values conform to schema.

---

## Rows flagged (<70% confidence)

### Products

**product-006 (Perplexity)** — Low confidence overall. Nine of ten cells are inferred from secondary/aggregator sources (llmpulse.ai, wpseoai.com, clickrank.ai) rather than primary product documentation. The distinction between verdict_behavior='transparency-only' and 'synthesis-with-citations' is genuinely ambiguous for Perplexity; the report's own characterization is 'transparency-ish/synthesis.' Recommend re-verifying against perplexity.ai help-center before using in proposal.

**product-012 (FEVER)** — All cells inferred. Primary source URL is the report itself (research/raw/report_a.md). The sources_a.md entry labeled '(FEVER)' at https://aclanthology.org/2020.emnlp-main.609 is likely a mislabeling — EMNLP 2020 is SciFact's venue, not FEVER (NAACL 2018). Do not cite this URL for FEVER. Canonical FEVER URL would be ACL Anthology N18-1074; confirm before using.

**product-015 (ClaimBuster/Squash)** — All cells inferred; project is wound down. Report cites only Reporters Lab secondary sources.

**product-016 (Full Fact AI)** — All cells except automation_level inferred; tool is internal/licensed with limited public documentation.

**product-018 (Logically)** — All cells inferred; primary sources are logically.ai announcements (marked marketing-claim) and a 2021 Forbes article. Accuracy figures are marketing claims.

**product-022 (RetractoBot)** — All cells inferred from brief report A description + GitHub repo.

**product-024 (RedacTek)** — All cells inferred from Doody's Collection Development Monthly review (third-party). No primary vendor URL available from either report. High-priority verify_before_proposal item.

### Literature

**lit-002, lit-003, lit-004 (METGEN, IRGR, RLET)** — Specific quantitative metrics not reported in report B; metrics_and_best_numbers fields are marked with extractor-inferred derivation notes.

**lit-008 (Entailer)** — No external URL in sources_b.md; full citation confirmed (Tafjord, Dalvi Mishra & Clark, EMNLP 2022) but dataset and metrics not specified in report B. All extractor-inferred.

**lit-022 (Boissin et al. PNAS Nexus 2025)** — PNAS Nexus URL not in sources_b.md; source is report B text only. Reference is pgaf325, confirmed DOI-resolvable in principle but not verified in this pass per prompt rules (no external fetch).

**lit-026, lit-027 (Doyle 1979 JTMS, de Kleer 1986 ATMS)** — Primary journal paper URLs not in sources_b.md. Sources include an MIT DSpace record and academia.edu link (for ATMS) that were in sources_b but not directly used as primary citations. Both papers are foundational and well-known; DOIs should be confirmed before proposal citation.

---

## Papers/products from the reports that were SKIPPED and why

### Skipped literature (mentioned briefly, insufficient detail for a full row)

- **Bago & Bonnefon Perspective** (Science 2024, 385:1164–1165) — perspective piece on Costello 2024; no independent methodology or metrics. Relevant only as a context citation; use Costello et al. 2024 (lit-020) as the primary row.

- **Hornsey et al. (Curr. Opin. Psychol. 2026), Bretter et al. (Nat. Energy 2025), Czarnek et al. (2025), Hou et al. (Nat. Med. 2025)** — mentioned as thematic extensions of the belief-updating line in Area 5; no methodology, metrics, or dataset detail provided in report B; no URLs in sources_b.md.

- **Molecular Facts (Gunjal & Durrett 2024), CORE (Jiang et al. 2024), WiCE (Kamoi et al. 2023)** — mentioned as related work within the DnDScore (lit-014) entry; no independent methodology description or metrics in report B; incorporated into lit-014's method_summary.

- **Wikidata provenance model** — described in Area 6 as an approach/system, not a specific paper with authors/venue/metrics. The schema `literature_row` requires "paper: string (authors, year, venue)"; Wikidata has no single foundational paper citation in the report. Skipped; the relevant technical point (statement-level provenance with deprecated rank) is captured in lit-028 (scite) method_summary context.

- **van der Vet & Nijveen error-propagation study** — mentioned in one sentence in Area 5 of report B without citation details (no authors year venue metrics); skipped.

- **"Persistence of Retracted Papers on Wikipedia" (arXiv:2509.18403)** — mentioned in report B Area 6 recommendations; no methodology or metrics described. Sources_b.md flags this as "verify; located via search, confirm before citing." Included in sources.jsonl with verify_before_proposal=true; not added to literature.jsonl due to absence of extractable row fields.

- **Usman & Balke (TPDL 2024)** — mentioned as a product-adjacent academic paper on retraction cascade ranking; appears in report A's retraction-tracking section. Brief description: "ranks non-retracted-but-likely-retractable citing papers; prioritization for human review, not automatic invalidation." The DOI (doi.org/10.1007/978-3-031-72437-4_7) is in sources.jsonl (cited_by product-024). Not added to literature.jsonl because the paper is described in report A (product landscape), not report B (literature survey), and the schema's literature_row is for report B papers.

- **"A Logical Pattern Memory Pre-trained Model for Entailment Tree Generation" (arXiv:2403.06410)** — listed as a reference in sources_b.md Area 1 but not described in report B text with methodology or metrics; skipped.

- **arXiv:2606.17041 (companion to arXiv:2604.22864, sample-size extraction)** — listed in sources_b.md but described only as a search term, not a full citation; skipped.

- **Retraction Watch / Crossref acquisition paper** and **NLM/PubMed MeSH documentation** — these are data sources/infrastructure, not research papers; skipped from literature.jsonl.

### Skipped products (not listed in report A or too peripheral)

None — all products and tools described in report A with sufficient detail were extracted. The following were included despite minimal description because the report explicitly surveys them: ClaimBuster/Squash (product-015), Full Fact AI (product-016), RetractoBot (product-022), RetractionCheck/Crossref API (product-023). FEVER, SciFact, and AVeriTeC were included as product rows (product-012, -013, -014) because report A explicitly lists them under "Additional systems."

---

## URL anomaly: FEVER misattribution in sources_a.md

`sources_a.md` labels `https://aclanthology.org/2020.emnlp-main.609` as "(FEVER)" but this URL resolves to the EMNLP 2020 proceedings slot — which is SciFact's publication venue (Wadden et al. 2020), not FEVER (Thorne et al. NAACL 2018). This URL was used for product-013 (SciFact) with confidence "inferred" and is flagged verify_before_proposal=true. Product-012 (FEVER) uses report_a.md as its source with all fields inferred.

---

## Marketing-claim cells requiring pre-proposal verification

| Row | Field | Claim | Source |
|-----|-------|-------|--------|
| product-002 | access_model | $20/mo–$200/yr individual; $5k–$25k institutional | visionsparksolutions.com (third-party) |
| product-005 | access_model | ~$10.86/mo | theresanaiforthat.com (aggregator) |
| product-005 | claim_decomposition | "outperforming GPT-4" accuracy | factiverse.ai blog (marketing) |
| product-007 | verdict_behavior | 86.69% accuracy | originality.ai (vendor) |
| product-018 | evidence_quality_metadata | Logically accuracy percentages | logically.ai announcements (marketing) |
| product-024 | all cells | RedacTek feature description | dcdm.doody.com review (third-party) |

---

## scite index size inconsistency (noted in report A caveats)

Report A explicitly flags: scite's own pages cite "1.6B+ Smart Citations" on features page vs. "over 1.8 billion unique citations" on the coverage page (updated June 2026). product-002 uses "1.6B+" from the features page (more conservative, primary product page). Treat as approximate.
