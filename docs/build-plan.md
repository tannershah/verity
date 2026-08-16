# Build Plan — Modules, Tiers, Ordering

The engineering decomposition of the v0 prototype and the path beyond it. Refines the
eight work packages in [design.md](design.md) §6 into ten modules with tiered climbs;
the D-package ↔ module mapping is in §1. A tier is sized to one working session.

The design decisions this plan depends on are recorded in their owning docs
([design.md](design.md) §4, §7; [evaluation.md](evaluation.md) §2); §5 tracks what
remains open. External facts below (API contracts, library states, dataset counts)
were verified 2026-08-15; anything marked *unconfirmed* needs a check before its
tier starts.

---

## 1. Modules

Ten modules. Completing every tier in the §3 ordering yields the complete v0 engine
(`claim → 3–7 premises → evidence → per-premise confidence`, inspectable, with
invalidation); the 38+ block is hardening and extension.

| Module | Function | D-package |
|---|---|---|
| **M1 Spine** | Data model, persistence, orchestration, LLM adapter, run logs | implicit in all |
| **M2 Intake** | Text → canonical, decontextualized, check-worthy claims | **absent from D1–D8** — added |
| **M3 Decomposition** | Backward chaining: claim → 3–7 load-bearing premises, recursive | D1 |
| **M4 Verifier gate** | Joint-sufficiency scoring per step; leave-one-out non-redundancy | D1 |
| **M5 Alethiology** | Persistent fact store: schema, exact-key grounding, promotion policy | D2 |
| **M6 Retrieval** | Evidence acquisition for unknown premises (five free APIs, agentic) | D3 |
| **M7 Evidence quality** | Retraction cross-check, study design, citation intent, sample size | D4 |
| **M8 Invalidation** | JTMS over the alethiology; retraction propagation | D5 |
| **M9 Presentation** | Inspectable claim graph: CLI then Streamlit; per-premise confidence | D6 |
| **M10 Evaluation** | Claim sets, termination metrics, benchmarks, human protocol, linkage eval | D7 |

D8 (polish, run logs) is distributed: run logs in M1, demo polish in M9-T4.

**Why M2 exists:** the thesis says "input: text containing claims," but D1–D8 starts
at decomposition. v0 accepts a single claim string; extraction from passages is a
tier, not an assumption.

**Deferred by decision, not dropped:** bias annotation (the "bias graphs" half of the
thesis pipeline, Penn MBD template per evaluation §4) is news-domain roadmap — the
beachhead's evidence-quality metadata plays that role for scientific claims.
Confidence graphs are covered (M4 + M9). The disagreement-localization study is
roadmap by the same ruling (evaluation §2).

---

## 2. Tiers

Format per tier: **goal — how — exit criterion.** Exit criteria are checkable at the
tier's slot in the §3 ordering, with the artifacts that exist by then.

### M1 Spine

- **T1 — Scaffold and data model.** Package layout (pyproject, pytest, ruff), typed
  models for Claim, Premise, EntailmentStep, EvidenceItem, Fact, Justification,
  ClaimGraph (design §4); SQLite persistence + JSON export; config object (depth
  budget, beam caps, thresholds) plus secrets handling (env-var convention, `.env`
  loading, keys excluded from manifests and logs); LLM adapter interface
  (provider-agnostic, one concrete backend); run manifest with per-stage timing/cost.
  The ClaimGraph type has **no root-aggregate field, and a test asserts the renderer
  never receives one**.
  *Exit:* round-trip a hand-built claim graph through store → load → JSON.
- **T2 — Orchestrator.** Pipeline stages as composable steps with content-hash
  caching; deterministic replay of any run from its manifest; failure isolation (a
  stage error yields a partial graph, not a crash). Replaces the throwaway driver
  written during M9-T1's session.
  *Exit:* re-running an unchanged claim is a cache hit end-to-end.
- **T3 — Batch and recompute.** Batch runner over claim sets (M10-T1 consumes this);
  dirty-subgraph recompute after a KB status change (M8-T2 consumes this); every
  external fact stamped with access time (feeds M5-T3's re-validation).
  *Exit:* 20-claim batch completes unattended; a KB flip recomputes only affected
  graphs.

### M2 Intake

- **T1 — Single-claim normalization.** LLM pass producing a canonical claim:
  decontextualized, hedges stripped, claim type tagged (causal / correlational /
  statistical / existence), check-worthiness gate with a rejection message for
  non-claims (opinions, predictions). Decontextualization strategy is logged as
  metadata — DnDScore (`lit-014`) shows the strategy shifts downstream scores.
  Loki's MIT-licensed Decomposer/Checkworthiness modules are reference code to adapt,
  not a dependency (no commits since 2024-10; ClaimBuster's API is currently down).
  *Exit:* 10 messy inputs → canonical claims or principled rejections.
- **T2 — Passage extraction.** Paragraph → segmented, check-worthy, decontextualized
  claims (VeriScore's verifiable-claim posture, `lit-012`); dedup.
  *Exit:* a scientific-press paragraph yields the claims a human would list.
- **T3 — Document ingestion.** URL/HTML → text (boilerplate removal) → T2; claim
  clustering across a document. Roadmap-adjacent; scientific articles only.

### M3 Decomposition

- **T1 — Single-step backward chain.** Claim → 3–7 load-bearing premises via LLM
  structured output. The prompt encodes the three validity criteria directly:
  jointly sufficient, each premise strictly easier to verify, none removable; and
  steers leaves toward **citation-shaped premises** (a premise a specific paper or
  registry entry can verify — the grounding target). Each citation-shaped premise
  carries a **candidate-key slot** the model fills when it knows the specific work
  (DOI/PMID/NCT) — usually empty; the authoritative binding happens in M6-T3.
  Steps are native n-ary — no binarization (design §4.3).
  Premise typing: empirical-citable / statistical / definitional / background.
  *Exit:* decompositions for 5 pilot claims pass eyeball review against the criteria.
- **T2 — Recursive descent.** Recurse on premises that are neither citation-shaped
  nor grounded; **depth budget** (default 3) with per-branch termination reason
  recorded: `grounded | citation-shaped | unverifiable-by-design | budget-exit`.
  Definitional/background premises terminate as `unverifiable-by-design` without
  burning depth budget — no paper-shaped key can verify them (see §4 for how they
  count). Beam caps (max premises/node, max nodes/tree) for cost control — caps are
  reported per run (**no silent caps**, evaluation §6).
  *Exit:* trees for the pilot claims with termination-reason and budget-exit rates
  computed and printed.
- **T3 — Verifier-in-the-loop.** Sample k candidate decompositions per step, score
  with M4, take the best above threshold, else re-prompt with verifier feedback;
  backtrack on dead branches. This is NLProofS's verifier-guided search (`lit-005`)
  transplanted to open-domain decomposition.
  *Exit:* measurable step-score lift over T2 on the pilot set at bounded extra cost.
- **T4 — KB-aware decomposition.** Inject nearest alethiology facts (via M5-T3's
  similarity index) and retrieved citations into the decomposition prompt as
  candidate leaves (NELLIE's pattern, `lit-009`) so the chain steers toward
  groundable premises. The single biggest planned lever on grounding rate. The
  post-lever grounding measurement is reported as a **separate, labeled number**,
  never merged into the §4 verdict run.
  *Exit:* grounding-rate lift over the recorded baseline, same budget, same set.

### M4 Verifier gate

- **T1 — Off-the-shelf gate.** Local entailment scorer over concatenated premises →
  claim; candidates: **MiniCheck-Flan-T5-Large** (grounding-tuned, best sub-1B in
  its family) and **DeBERTa-v3-large NLI** (MoritzLaurer mnli-fever-anli-ling-wanli);
  pick by a 10-case smoke set. Known caveats carried in code comments and metadata:
  concatenation is a workaround, not a validated multi-premise architecture; NLI
  label order varies per checkpoint and is verified at init. Configurable threshold;
  per-step score stored and rendered, labeled **uncalibrated** until T3
  (evaluation §6 standing rule).
  *Exit:* every step in every stored graph carries a score; obviously-broken
  decompositions score visibly worse than clean ones on the smoke set.
- **T2 — Leave-one-out ablation.** Re-score each step with each premise removed; a
  premise is load-bearing iff the drop exceeds δ; redundant premises are pruned
  (loops back into M3); ablation deltas stored per premise (M10-T3 and the display
  both consume them). Because concatenation may blunt per-premise deltas, the
  session includes a **sanity check against ~20 hand-labeled steps** (planted
  redundant premise, planted load-bearing premise) before deltas are trusted.
  *Exit:* ablation table per tree; planted-redundant and planted-load-bearing cases
  are separated by the chosen δ.
- **T3 — Calibration (spike + measurement).** Score EntailmentBank gold steps vs
  corrupted steps (premise dropped / irrelevant premise shuffled in / conclusion
  swapped); ROC + threshold selection. Two off-the-shelf comparators to
  spike-install and compare if feasible: the **NLProofS released verifier**
  (checkpoints live on HF `kaiyuy/NLProofS`, but old pins — PyTorch 1.11 — and no
  documented standalone API: custom glue required) and **ReCEval** (NLI-based, MIT,
  no BLEURT/TF dependency). The official EntailmentBank scorer + BLEURT is **not**
  adopted as production tooling: gold-tree-relative by construction, TF1-era
  dependency stack (it appears once, quarantined, in M10-T2a).
  *Exit:* champion picked from a curve we can show; threshold + calibration basis
  recorded in graph metadata with the distribution-shift caveat (EB ≠ our claims).
- **T4 — Fine-tuned verifier.** Train on EntailmentBank steps (closest structural
  match) + WiCE (closest domain/decomposition match, sub-claim evidence
  localization) + synthetic negatives + our human-annotated steps once M10-T3b
  produces them; calibration curve against the human sample.
  *Exit:* beats the T3 champion on held-out EB steps and on our annotated sample.

### M5 Alethiology

- **T1 — Schema, store, seed.** Fact records per design §4.1 with the 5-tier
  confidence vocabulary; SQLite; **exact-key lookup (DOI/PMID/NCT) as the only
  grounding path**; statement-hash dedup; seed script loading a hand-curated
  demo-domain JSONL (~50–100 facts around the two demo claims: the
  chocolate-weight-loss hoax trail and the spinach-iron decimal myth).
  *Exit:* seeded store; exact-key hit/miss behaves; fuzzy lookup does not exist.
- **T2 — Promotion policy (the cold-start rule), including the EvidenceItem→Fact seam.**
  The conversion is owned here: M5 consumes M6-T3 evidence bundles and creates a
  **candidate fact per (premise, grounding evidence item) pair** — `statement` = the
  premise as written (or an LLM restatement, labeled as such), `key` = the linked
  work's external key, `provenance` = the retrieval run. Promotion to `verified-*`
  requires exact key + retraction-clean (M7-T1) + source confidence tier; CLI
  approval queue for borderline cases; audit log of every promotion/demotion;
  periodic drift audit = re-check a random sample (NELL's lesson, `lit-025`:
  mitigation, not solution — the audit is the mitigation).
  *Exit:* an agentic-retrieval run produces candidate facts with statements, keys,
  and provenance; only policy-passing facts reach `verified-*`; the audit report runs.
- **T3 — Grounding service and re-validation.** Similarity assist (embedding index
  over fact statements) **flagged non-grounding, suggestion-only** — it feeds M3-T4
  and the UI, never the grounding metric; TTL-based re-validation: facts past TTL
  are re-checked against the APIs, and status changes emit JTMS events — grounding
  is non-monotonic and never cached as permanent (design §4.2).
  *Exit:* grounding metric provably unchanged by the similarity layer (test); a
  stale fact re-validates and, if flipped, propagates.
- **T4 — Maintenance.** Same-key contradiction detection, merge tooling, KB stats
  (growth, tier mix, staleness), export/import.

### M6 Retrieval

- **T1a — Shared infrastructure + OpenAlex + Crossref.** Disk cache (mandatory, not
  an optimization), rate limiting, retries, fixture-recording harness; then the
  first two clients — current contracts, verified 2026-08-15:
  - **OpenAlex** — key mandatory since 2026-02-13 (free: 100k credits/day; keyless:
    100/day then 409s); costs: singleton GET = 1 credit, filtered list = 10; hard
    100 req/s ceiling; **do not adopt pyalex until its auth-param issue (#91) is
    fixed** — pass `api_key` directly.
  - **Crossref** — no key; `mailto=` on every call for the polite pool; rate limits
    are advertised via `X-Rate-Limit-*` headers and were rebalanced 2025-12-01 —
    **read limits from headers at runtime, don't hardcode**.
  *Exit:* both clients return normalized records live and from fixtures; cache and
  rate limiter demonstrably engaged.
- **T1b — Remaining clients + deterministic search.**
  - **PubMed E-utilities** — free key raises 3 → 10 req/s; `PublicationType` for
    MeSH design labels; NCT linkage via the DataBank/`AccessionNumber` field
    (confirmed against live efetch XML, 2026-08-15).
  - **ClinicalTrials.gov v2** — no key; `GET /api/v2/studies/{NCTid}`;
    `enrollmentInfo.count` + `enrollmentInfo.type` (`ACTUAL` | `ESTIMATED`).
  - **Semantic Scholar** — free key is 1 req/s introductory (oddly *below* the
    shared unauthenticated pool — test both paths); `intents`/`contexts` field
    names on the citations endpoint are *unconfirmed* — verify against live docs in
    this session.
  Deterministic search: premise → keyword query → top-k candidate works with
  external keys; **k and every retry bound reported per run** (no silent caps).
  *Exit:* all five clients live + fixtures; the S2 field-name contract resolved
  in code and noted.
- **T2 — Agentic retrieval.** LLM-generated query reformulations per premise across
  sources; relevance filter (embedding + LLM pass); DOI-level dedup; the
  **symmetric obligation is structural**: contrasting-evidence queries (failed
  replications, contradicting results, critiques) are a mandatory branch, not an
  afterthought, so one-sided bundles can't happen silently. Filter reject counts
  and per-source caps reported per run.
  *Exit:* per-premise candidate bundles on pilot claims include both directions
  where both exist (spot-checked); caps and rejects visible in the run manifest.
- **T3 — Stance, key attribution, and provisional evidence state.** Stance uses a
  **3-class NLI checkpoint chosen independently of the M4-T1 champion** (the
  DeBERTa-v3 mnli-fever-anli model is the default — MiniCheck is binary and cannot
  emit contradicts-vs-neutral): title+abstract vs premise → supports / contradicts /
  neutral with score, **labeled uncalibrated** until M10-T3 supplies the human
  sample. **Key attribution happens here:** the top supporting evidence item above
  a fixed stance floor binds its DOI/PMID/NCT to the premise as its grounding key —
  this is the mechanism that puts a key on the premise side of exact-key grounding
  (decomposition-time candidate keys from M3-T1 are treated as hints to verify, not
  bindings). Output: per-premise **evidence bundle** (symmetric lists + counts) plus
  a **provisional evidence state** (`has-evidence | none`, labeled provisional until
  M8-T3's semantics land); bundles are what M9 renders and M5-T2 promotes from.
  Recomputation owner: this tier's code, re-run whenever a bundle changes.
  *Exit:* bundles with bound keys on the pilot set; stance spot-check ≥
  eyeball-acceptable; stance errors logged for M10-T3's calibration sample.
- **T4 — Full text and contexts.** OA abstract/PDF fetch, S2 citation contexts,
  quote extraction (exact sentences backing an assigned stance) for display.

### M7 Evidence quality

- **T1 — Retraction layer.** Three-source design: the **local Retraction Watch
  table** (built in M10-T1; `RetractionNature` filtered — the file mixes
  retractions, corrections, EoCs) as ground truth, cross-checked with **Crossref
  `update-to`** (type + `source: publisher | retraction-watch`) and **OpenAlex
  `is_retracted`** (documented false-positive history — arXiv:2403.13339). Policy:
  RW-table or both-API agreement → `retracted`; single API source →
  `retraction-flagged-unconfirmed`; disagreements logged. Applied to every evidence
  item and fact.
  *Exit:* known-retracted DOI test set classified correctly; a disagreement case
  renders as flagged, not retracted.
- **T2 — Study design and registered N.** PubMed MeSH publication types → design
  labels; PubMed↔ClinicalTrials.gov link → enrollment with `ACTUAL`-vs-`ESTIMATED`
  labeled; every field carries provenance + confidence tier — a registry N and a
  text-mined N must never be indistinguishable (design §5).
  *Exit:* metadata attached across the pilot bundles; provenance renders.
- **T3 — Citation intent and summary.** S2 citation intent (labeled coarse 3-class;
  full-text-parsed papers only, so coverage skews open-access — labeled);
  supporting/contrasting citation counts where derivable; per-premise
  **evidence-quality summary** object; the **intent badge is added to the Streamlit
  panel in this session** (M9-T2 ships without it).
  *Exit:* summaries render per premise with honest labels on every field; intent
  badge live.
- **T4 — Text-mined N and design fallback.** LLM extraction of sample size from
  abstracts, labeled `model-extracted` (Elicit precedent, `product-028`); design
  inference where MeSH is missing, same labeling.
  *Exit:* extraction accuracy sampled and reported (joins the calibration sample).

### M8 Invalidation

- **T1 — JTMS core.** **Adopt, don't build:** `pisanuw/ltms` (PyPI `ltms` 0.1.0) is
  a pure-Python, MIT, actively-developed Building-Problem-Solvers port whose
  `jtms.py` (~330 lines, dedicated tests incl. well-founded/circular-support cases)
  covers exactly what D5 needs. It is two months old and single-maintainer, so the
  session is: read the source, vendor-pin, run and extend its tests with
  Verity-shaped cases (retraction propagates; re-justification restores; fuzz
  add/retract), and wrap it behind our own interface so a from-scratch fallback
  (~330 LOC, Doyle 1979 / Forbus & de Kleer BPS ch. 7) stays cheap.
  *Exit:* wrapped JTMS passes our test battery; fallback documented.
- **T2 — Wired invalidation.** Facts/premises/claims as TMS nodes; entailment steps
  and **alethiology groundings — only these, never bundle-derived states — become
  justifications**; a retraction event flips the fact OUT and every dependent
  premise/claim re-renders flagged, using M1-T3's dirty-subgraph recompute.
  **Retraction-injection is a regression suite, not a result** (evaluation §5).
  *Exit:* inject retraction on a demo claim's load-bearing fact → tree re-renders
  flagged within one recompute; suite green.
- **T3 — Conflicted-state semantics.** Implements the settled semantics
  (design §4.2): evidence state `verified | contested | unverified` orthogonal to
  JTMS IN/OUT; `verified` pinned to alethiology grounding only; `contested` cut
  mechanically at the pre-registered stance floor and **never entering the JTMS as
  a justification**; symmetric, verdict-free display. Refines M6-T3's provisional
  state in place.
  *Exit:* a contested premise cannot justify anything (test); a bundle cannot
  produce `verified` (test); the three states render distinctly.
- **T4 — ATMS spike (conditional).** Only if a later need forces simultaneous
  incompatible contexts — the settled semantics do not (design §4.2). No maintained
  Python ATMS exists (verified — two dead 2017 toy ports), so this would be a
  from-scratch environments/labels prototype on one contested claim. Default:
  deferred.

### M9 Presentation

- **T1 — CLI render.** Rich tree view rendering what exists at its slot: per-step
  verifier confidence, plus placeholder columns that light up as producers land
  (grounding status, termination reason, evidence state); JSON export; a throwaway
  sequential driver composes M3→M4→render this session (M1-T2 replaces it next).
  **A test asserts no root aggregate is computed or rendered.**
  *Exit:* a stored graph renders legibly in a terminal.
- **T2 — Streamlit inspection.** Expandable claim graph; per-premise panel:
  confidence, symmetric evidence bundle, provisional evidence state, quality badges
  (design, N, retraction — intent arrives with M7-T3), provenance drill-down to
  source URLs. Resolves "Streamlit or CLI": CLI first (T1), Streamlit here.
  *Exit:* a stranger can inspect a demo claim unaided and find the weakest premise.
- **T3 — Invalidation and state UX.** Retraction banners with the justification
  chain that flipped; staleness timestamps; final three-state styling from M8-T3,
  symmetric by construction (no visual adjudication affordance).
  *Exit:* the M8-T2 injection demo is legible end-to-end in the UI; contested and
  unverified premises are visually distinct and verdict-free.
- **T4 — Demo polish.** The two demo claims (chocolate-weight-loss hoax,
  spinach-iron decimal myth — both valence-rule-compliant), instant replay from the
  alethiology (rides M1-T2 caching), export/screenshot. **Gated on M10-T3b's ≥80%
  result — below the floor, no public demo (evaluation §2).**
  *Exit:* cold-start demo runs in under a minute without narration.

### M10 Evaluation

- **T1 — Beachhead set, RW table, instrumentation.** Download and load the
  **Retraction Watch bulk CSV** (`gitlab.com/crossref/retraction-watch-data`,
  verified 71,799 rows on 2026-08-15, refreshed working days) into the local table
  M7-T1 and T4a will consume. Curate the 20-claim beachhead set (low-valence
  science/health; mix of groundable, contested, retraction-affected) sampled from
  **SciFact** (CC BY-NC 2.0) and **PUBHEALTH**, crossed with the RW table. Metrics
  logger computing **grounding rate (exact-key definition), mean/max depth,
  termination-reason mix, budget-exit rate** per run from run manifests, driven by
  M1-T3's batch runner.
  *Exit:* metrics table generated from a 20-claim batch run. Early numbers are
  smoke tests — the threshold verdict is session 31 (§4 cadence).
- **T2a — EntailmentBank harness.** Stand up the official EB scorer stack in a
  **quarantined environment** (BLEURT's TF1-era pins never touch the main deps) or
  adopt a verified reimplementation; build the **EB-mode adapter**: a constrained
  decomposition mode that builds trees from EB's provided gold+distractor leaves
  (Task 2 setting) — free-form decomposition would score near zero on alignment by
  construction, telling us nothing.
  *Exit:* scorer runs on a published system's output, reproducing its reported
  numbers within tolerance; adapter emits EB-format trees.
- **T2b — EntailmentBank run.** Score the M4 champion on EB gold/corrupted steps;
  run the EB-mode decomposer on the EB test split and score with the four metrics;
  report with the distribution-shift caveat and NLProofS baselines quoted correctly.
  *Exit:* comparable numbers table.
- **T3 — Ablation eval and human-protocol pilot.** Leave-one-out ablation stats
  over generated trees; annotation tooling: step export, two-annotator sheets
  (entailment / verifiable-as-written / load-bearing), adjudication flow, Cohen's
  κ; **the stance-accuracy calibration sample is annotated in the same session**
  (pairs M6-T3's model numbers with a human anchor or confirms the uncalibrated
  label stays). Pilot on 5 trees to debug the protocol before T3b. The builder
  annotates, disclosed as a bias; **the second annotator must be recruited by this
  session** (open-questions D-3).
  *Exit:* pilot κ computed; stance sample annotated; protocol doc frozen.
- **T3b — Human step-validity run (the demo gate).** The real N=30-tree,
  two-annotator run under the frozen protocol, on trees from the **final decomposer
  configuration** (post M3-T4), with ablation spot-checks, adjudication, and κ
  reported. **This is the ≥80% threshold measurement; M9-T4 and any public demo
  are gated on it** (evaluation §2).
  *Exit:* the step-validity number and κ, recorded pass/fail against the
  pre-registered floor.
- **T4a — Linkage corpus.** Availability checks the draft flags as *unconfirmed*:
  the Wikipedia retracted-citations dataset (arXiv:2509.18403 — no confirmed public
  release; check the CSCW camera-ready / contact authors) and VITALITY's
  contaminated-meta-analysis list (structured download unconfirmed; check PMC
  supplements). Started early so author-contact latency is absorbed. Then build the
  ~50-real-claim set by crossing the RW table with claim corpora (fallback: RW ×
  SciFact/PubMed crossings), **with retraction-dependence labels** — precision/
  recall are unmeasurable without them.
  *Exit:* labeled claim set versioned in-repo, source documented.
- **T4b — Retraction linkage eval.** Measure premise-to-retracted-DOI linkage
  precision/recall and the **false-flag rate against the ≤5% threshold**. The
  headline eval the differentiator rests on.
  *Exit:* the three numbers, recorded pass/fail.
- **T5 — Leaf benchmark.** SciFact sample run for the leaf verifier only
  (verdict-boundary-consistent — evaluation §3).
  *Exit:* leaf-module numbers comparable to published SciFact baselines.

---

## 3. Ordering

Interleaved to keep an end-to-end system running from session 4 onward, retire the
existential risks earliest, and respect dependencies. **Bold** = decision gate or
headline measurement. Every consumer's producer appears above it.

| # | Tier | Why here |
|---|---|---|
| — | **Gate 0: OpenAlex / NCBI / S2 keys registered; LLM adapter configured (Claude API default — design §7)** | Blocks M1-T1 and M6; OpenAlex is unusable keyless |
| 1 | M1-T1 | Everything stands on the data model |
| 2 | M3-T1 | The existential risk — is decomposition any good? — visible immediately |
| 3 | M4-T1 | Steps get scores; bad decompositions become measurable |
| 4 | M9-T1 | **Walking skeleton:** claim → premises → confidence, in a terminal (throwaway driver) |
| 5 | M1-T2 | Real orchestrator replaces the throwaway; caching + replay from here on |
| 6 | M5-T1 | Grounding target exists (seeded) |
| 7 | M6-T1a | Retrieval infra + OpenAlex + Crossref |
| 8 | M3-T2 | Real trees: recursion, budget, termination reasons |
| 9 | M1-T3 | Batch + recompute, before anything needs them |
| 10 | M10-T1 | Beachhead set + RW table + metrics flowing from here on |
| 11 | M6-T1b | PubMed + CT.gov + S2 + deterministic search (resolves the two unconfirmed contracts) |
| 12 | M6-T2 | Evidence for unknown premises, symmetric by construction |
| 13 | M7-T1 | Retraction layer — the beachhead's sharpest metadata |
| 14 | M10-T4a | Linkage-corpus availability checks start (absorbs author-contact latency) |
| 15 | M6-T3 | Stance + key attribution + bundles (the transparency payload) |
| 16 | M5-T2 | Promotion + EvidenceItem→Fact seam, before the KB grows from retrieval |
| 17 | M7-T2 | Study design + registered N |
| 18 | M9-T2 | **Demoable:** full inspectable transparency view in Streamlit |
| 19 | M4-T2 | Non-redundancy enforced (ablation) |
| 20 | M4-T3 | Verifier calibrated; confidence display gains a stated basis |
| 21 | M3-T3 | Verifier-guided decomposition (needs 19/20) |
| 22 | M2-T1 | Clean claim intake before human-facing eval |
| 23 | M8-T1 | JTMS adopted, wrapped, tested |
| 24 | M8-T2 | **The differentiator demo:** retraction propagates, graph flags (uses 9's recompute) |
| 25 | M8-T3 | Conflicted-state semantics in code |
| 26 | M9-T3 | Invalidation + final states legible in the UI |
| 27 | M7-T3 | Citation intent + quality summaries + intent badge |
| 28 | M10-T2a | EB harness: quarantined scorer + EB-mode adapter |
| 29 | M10-T2b | EB step-validity numbers |
| 30 | M10-T3 | Human protocol piloted + stance calibration sample (**needs the D-3 second annotator**) |
| 31 | **Grounding verdict run** | The pre-registered ≥50% measurement on the populated KB, recorded pass/fail (§4) |
| 32 | M5-T3 | Similarity assist + re-validation under non-monotonic grounding |
| 33 | M3-T4 | KB-aware decomposition lever; post-lever lift reported as a separate labeled number |
| 34 | M10-T3b | **Human step-validity run (N=30) — the ≥80% demo gate**, on the final decomposer |
| 35 | M10-T4b | **Retraction linkage eval — the headline numbers** |
| 36 | M10-T5 | SciFact leaf numbers |
| 37 | M9-T4 | Demo polish — gated on 34's result |
| 38+ | M2-T2, M4-T4, M6-T4, M7-T4, M5-T4, M2-T3, M8-T4 | Hardening and stretch, priority in that order |

**v0-complete line: sessions 1–37.** Rows 31, 34, and 35 are the three
pre-registered measurements; none is optional and none floats outside the schedule.

---

## 4. Measurement cadence — grounding rate

The ≥50% grounding threshold (evaluation §2) is judged against a **populated**
alethiology. The KB starts empty and fills via retrieval + promotion (sessions
12–16), so: metrics flow from session 10, are labeled smoke tests until session 16,
and the threshold verdict is **session 31** — deliberately before the M3-T4 lever, so
the lever's lift is measured against an honest baseline. **The verdict run's result
is recorded and reported pass/fail regardless of subsequent work**; the post-lever
re-measurement (session 33) is a separate, labeled number, and the documented pivot
decision (curated-domain alethiologies) is made on the recorded verdict per
evaluation §2 — levers do not reopen a recorded fail.

**Mechanism note.** "Grounds" requires a key on both sides: the premise side gets its
key from M6-T3's key attribution (top supporting evidence item above the stance
floor), or in M3-T4 mode from injected alethiology facts; the fact side from M5-T2
promotion. Exact-key match of a premise's bound key to a `verified-*` fact = grounded.

**Denominator note.** `unverifiable-by-design` terminals (definitional/background
premises — no paper-shaped key can verify them) **count in the pre-registered
grounding-rate denominator** (conservative: they deflate, never inflate). A
supplementary rate over citable branches only is reported alongside, labeled. This
structurally caps the headline rate — stated here so a miss is diagnosed correctly.

---

## 5. Open items

| Item | Blocks | State |
|---|---|---|
| **Second annotator** for the step-validity protocol (open-questions D-3) | M10-T3/T3b | Pilot N=5 and builder-annotates-with-disclosure are committed (evaluation §2); the second seat is unfilled |
| **Linkage-eval corpora availability** (Wikipedia retracted-citations dataset; VITALITY list) | M10-T4a/T4b | Unconfirmed; M10-T4a resolves early, fallback specified |

---

## 6. Flags — scoped but needing research or experiment

- **Verifier calibration is the weakest scientific link.** Off-the-shelf entailment
  models have no native "N premises jointly entail C" input format — concatenation
  is a workaround (per MiniCheck/WiCE's own design rationale), distribution-shifted
  twice on our steps. M4-T2's hand-labeled sanity check and M4-T3's measurement are
  the guards; M4-T4 is the mitigation. Experiment, not assumption.
- **Combinatorial cost.** Depth 3 × 3–7 premises is ≤ ~400 nodes worst case before
  beam caps; caps are load-bearing for cost and are reported per run — as are
  retrieval's top-k, filter rejects, and retry bounds (no silent caps, anywhere).
- **API limits.** S2's keyed tier starts at 1 req/s; OpenAlex filtered queries cost
  10 credits each against 100k/day; Crossref limits are runtime-discoverable only.
  The M6-T1a disk cache is mandatory, not an optimization.
- **Licenses.** SciFact (CC BY-NC 2.0) and AVeriTeC (CC BY-NC 4.0) are
  non-commercial — fine for the research prototype and eval, flag before any
  commercial framing.
- **Stance assignment on abstracts only** (M6-T3) will mislabel nuanced findings;
  quote-level stance (M6-T4) is the fix; the error rate is measured in M10-T3's
  calibration sample, and stance scores stay labeled uncalibrated until then.
- **Promotion policy strictness** trades KB growth against drift. Start strict
  (exact key + retraction-clean + corroboration for `verified-*`), loosen only with
  audit data in hand.
- **Dependency youth.** `pisanuw/ltms` is two months old, single-maintainer:
  vendor-pin, review source, keep the from-scratch fallback documented (M8-T1).
- **Linkage-eval corpora are unconfirmed** (Wikipedia retracted-citations dataset,
  VITALITY list) — M10-T4a exists to resolve this early; the fallback path is
  specified.
