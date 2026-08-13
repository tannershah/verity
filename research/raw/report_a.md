# Competitive Landscape Survey: "Verity" Epistemic Transparency Engine

## TL;DR
- As of August 2026, **no shipping consumer product combines all four of Verity's load-bearing features** — automatic recursive claim→premise decomposition, per-premise study-level evidence quality, a dependency-tracked persistent knowledge base, and transparency-only (no-verdict) output. The closest analogs each cover one or two dimensions.
- The **strongest competitors on individual axes** are: scite.ai (study-level evidence + retraction flagging, but citation-level not premise-level), Loki/OpenFactVerification and DeepMind's SAFE (automatic atomic-claim decomposition, but verdict-oriented and no persistent KB), and Ground News / Penn Media Bias Detector (transparency-only philosophy, but article/source-level not claim-level).
- Verity's genuinely defensible white-space is the **combination of recursive premise decomposition + a dependency-tracked verified-fact KB with propagated invalidation**; true dependency-propagated invalidation (flagging downstream claims when a base fact is overturned) does not exist as a shipping product as of Aug 2026 — the closest is RedacTek, which per Nature Index "is creating a retraction analysis tool that assigns a 'retraction association value', which is calculated by measuring the retraction status of primary, secondary and tertiary citations" (i.e., paper-level, not claim-level).

## Key Findings
1. **Claim decomposition is now common in research/academic systems but rare in consumer products.** Loki (Libr-AI), SAFE (Google DeepMind), FActScore, ProgramFC, and AVeriTeC systems all automatically decompose text into atomic claims/subquestions. But these decompose into *independent atomic facts*, not *load-bearing premises that jointly entail a composite claim* — and almost all issue verdicts. None recursively decompose into an entailment structure and withhold verdicts.
2. **Study-level evidence metadata is essentially unique to scite.ai** among the surveyed products (study design, retraction status, supporting/contrasting citation counts). Consumer fact-checkers stop at source-level credibility ratings.
3. **Transparency-only positioning exists but only at the article/source level** (Ground News, Penn Media Bias Detector), never at a decomposed-premise level.
4. **Persistent verified-fact stores exist** (Wolfram Alpha's curated Knowledgebase; ClaimReview/Squash's fact-check database; AVeriTeC's knowledge store) but none is a *dependency-tracked* KB that propagates invalidation to derived claims.
5. **Dependency-propagated invalidation does not exist in shipping products.** The closest is RedacTek (paper-level, 3-generation retraction-risk propagation) and Usman & Balke's academic "retraction cascade" ranking; the only true dependency-invalidation paradigm (Truth Maintenance Systems) has never been applied to scholarly retractions.

## Details

### Feature Matrix

Legend for tags: **V** = verified (primary source/product/docs), **I** = inferred, **M** = marketing-claim.

#### Ground News
1. **Unit of analysis:** Article/story cluster and news outlet (not individual claims). [V — help.ground.news/en/articles/485057; ground.news/frequently-asked-questions; accessed Aug 13 2026]
2. **Claim decomposition:** None. [V — same]
3. **Evidence-quality metadata:** Source-level (bias rating, factuality rating, ownership). [V — help.ground.news; ground.news/rating-system; accessed Aug 13 2026]
4. **Verdict behavior:** Transparency-only ("we keep our team's subjective opinions out of the product"; "does not fact-check"). [V — help.ground.news; libguides.depauw.edu; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** Yes — deliberately shows left/center/right coverage side by side; Blindspot feature. [V — ground.news/blindspot/about; accessed Aug 13 2026]
6. **Persistent knowledge reuse:** Cache (aggregated story clusters, source bias database); not a structured claim KB. [I — ground.news/frequently-asked-questions; accessed Aug 13 2026]
7. **Interactivity:** Compare sources by bias/factuality/ownership/location; Blindspot feed; browser extension overlay; bias distribution per story. [V — stationx.net/ground-news-review; accessed Aug 13 2026]
8. **Coverage domain:** News/politics. [V — ground.news; accessed Aug 13 2026]
9. **Automation level:** Automated aggregation with human-rated bias inputs (uses third-party rating agencies). [I — ground.news/rating-system; accessed Aug 13 2026]
10. **Access model:** Freemium; paid "Vantage"/subscription tiers unlock Blindspot, ownership data, My News Bias. [V — stationx.net; en.wikipedia.org/wiki/Ground_News; accessed Aug 13 2026]

#### scite.ai
1. **Unit of analysis:** Citation statement (per scientific paper). [V — scite.ai/features; direct.mit.edu/qss/article/2/3/882; accessed Aug 13 2026]
2. **Claim decomposition:** None (no premise/argument decomposition; operates on citation statements). [V — scite.ai/features; accessed Aug 13 2026]
3. **Evidence-quality metadata:** Study-level (supporting/contrasting/mentioning classification; retraction and editorial-concern flags via Crossref/PubMed). [V — scite.ai/features; belmont.libguides.com; accessed Aug 13 2026]
4. **Verdict behavior:** Source-ratings-only (classifies citations; no truth verdict on claims). [V — direct.mit.edu/qss; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** Yes — displays supporting AND contrasting citation counts and contexts. [V — scite.ai/features; guides.erau.edu/scite-ai; accessed Aug 13 2026]
6. **Persistent knowledge reuse:** Structured KB — per scite.ai its index spans "300M+ articles, preprints, books, patents, and datasets" with 1.6B+ classified Smart Citations (scite's coverage page cites "over 1.8 billion unique citations," last updated June 2026 — figures vary by page), but it is citation-indexed, not dependency-tracked. [V — scite.ai/features; scite.ai/coverage; accessed Aug 13 2026]
7. **Interactivity:** Search, Smart Citation visualization maps, Reports per paper, Reference Check (upload manuscript), Collections/alerts, Assistant, MCP integration. [V — scite.ai/features; guides.erau.edu; accessed Aug 13 2026]
8. **Coverage domain:** Scientific literature. [V — scite.ai/features; accessed Aug 13 2026]
9. **Automation level:** Fully automatic (deep-learning classification). [V — direct.mit.edu/qss; accessed Aug 13 2026]
10. **Access model:** Freemium/subscription — individual subscriptions start at $20/month or $200/year, with institutional licenses reported at $5,000–$25,000 annually; free tier + 7-day trial. [V — visionsparksolutions.com "Scite.ai Review 2026"; corroborated by University LibGuides; accessed Aug 13 2026]

#### PolitiFact
1. **Unit of analysis:** Individual statement/claim by a public figure. [V — politifact.com/article/2018/feb/12/principles-truth-o-meter; accessed Aug 13 2026]
2. **Claim decomposition:** None (manual holistic analysis of one statement). [V — same]
3. **Evidence-quality metadata:** None systematic (narrative sourcing; on-the-record sourcing policy). [I — politifact.com methodology; accessed Aug 13 2026]
4. **Verdict behavior:** Verdicts (six-point Truth-O-Meter, True→Pants on Fire). [V — politifact.com/article/2018/feb/12; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** No (delivers a single adjudicated rating). [I — same]
6. **Persistent knowledge reuse:** Cache/archive of past fact-checks (ClaimReview-tagged); not a structured premise KB. [I — reporterslab.org; accessed Aug 13 2026]
7. **Interactivity:** Read fact-check articles; browse by person/topic/rating; promise trackers. [V — politifact.com; accessed Aug 13 2026]
8. **Coverage domain:** US politics. [V — politifact.com; accessed Aug 13 2026]
9. **Automation level:** Fully manual editorial (three-editor panel votes on rating). [V — wral.com/how-we-determine-truth-o-meter-ratings; accessed Aug 13 2026]
10. **Access model:** Free (nonprofit, Poynter Institute). [V — politifact.com; accessed Aug 13 2026]

#### Penn Media Bias Detector (CSSLab / Duncan Watts)
1. **Unit of analysis:** Article, aggregated to publisher level (topics, tone, lean, facts). [V — engineering.upenn.edu/stories/mapping-media-bias; css.seas.upenn.edu/project/penn-map; accessed Aug 13 2026]
2. **Claim decomposition:** None in the entailment sense; it extracts/classifies "facts" and framing per article via LLMs but does not decompose into premises. [I — CHI '25 paper, dl.acm.org/doi/10.1145/3706598.3713716; accessed Aug 13 2026]
3. **Evidence-quality metadata:** None (analyzes tone/lean/fact-selection, not study quality). [V — engineering.upenn.edu; accessed Aug 13 2026]
4. **Verdict behavior:** Transparency-only ("Our goal is not to adjudicate what is true or even who is more biased"). [V — engineering.upenn.edu/stories/mapping-media-bias; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** Partial — compares publishers across the ideological spectrum on a topic, but not supporting/contrasting evidence per claim. [I — same]
6. **Persistent knowledge reuse:** Cache/database of analyzed articles over time. [I — penntoday.upenn.edu/news/conversation-duncan-watts; accessed Aug 13 2026]
7. **Interactivity:** Drop-down selection of topics/publishers/time periods; visualize story counts by lean/tone. [V — engineering.upenn.edu; accessed Aug 13 2026]
8. **Coverage domain:** News/politics (major US publishers). [V — same]
9. **Automation level:** Fully automatic LLM analysis (GPT infrastructure) with expert consultation. [V — penntoday.upenn.edu; accessed Aug 13 2026]
10. **Access model:** Free (academic research tool). [V — engineering.upenn.edu; accessed Aug 13 2026]

#### Factiverse
1. **Unit of analysis:** Claim/sentence (check-worthy claim detection). [V — factiverse.ai/blog/revolutionising-fact-checking; hellofuture.orange.com; accessed Aug 13 2026]
2. **Claim decomposition:** Automatic claim *detection* (identifies check-worthy sentences), but not decomposition into premises. [V — factiverse.ai/web; accessed Aug 13 2026]
3. **Evidence-quality metadata:** Source-level (credible-source filtering; supporting/disputing sources). [V — factiverse.webflow.io; accessed Aug 13 2026]
4. **Verdict behavior:** Source-ratings-only / veracity prediction with disputing/supporting sources shown (also outputs "veracity prediction" in benchmarks). [V — factiverse.ai/blog; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** Yes — surfaces sources that support AND dispute each statement. [V — factiverse.webflow.io; accessed Aug 13 2026]
6. **Persistent knowledge reuse:** Cache/Factisearch database (300k+ fact-checks) plus live search (Google/Bing/Wikipedia/Semantic Scholar). [V — factiverse.ai/blog/our-takeaways; accessed Aug 13 2026]
7. **Interactivity:** AI editor, live fact-checking, API, claim highlighting, source lists. [V — factiverse.ai; accessed Aug 13 2026]
8. **Coverage domain:** News, politics, general (multilingual, 100+ languages). [V — hellofuture.orange.com; accessed Aug 13 2026]
9. **Automation level:** Fully automatic with human-in-the-loop for journalists. [V — factiverse.ai/blog/introducing-live; accessed Aug 13 2026]
10. **Access model:** Freemium/subscription/API (AI Editor from ~$10.86/mo per aggregator). [I — theresanaiforthat.com/ai/factiverse; accessed Aug 13 2026]

#### Perplexity
1. **Unit of analysis:** Answer/response to a query (with inline citations). [V — perplexity.ai/help-center/en/articles/10352895; accessed Aug 13 2026]
2. **Claim decomposition:** None explicit for the user (RAG pipeline; Deep Research does multi-pass but does not present a premise decomposition). [I — perplexity.ai help center; accessed Aug 13 2026]
3. **Evidence-quality metadata:** None (source URLs/dates only; ranks by authority but does not expose study-level quality). [I — llmpulse.ai/blog/how-perplexity-works; accessed Aug 13 2026]
4. **Verdict behavior:** Transparency-ish/synthesis — provides an answer with citations, not a truth verdict; presents multiple perspectives on conflict. [I — perplexity.ai help center; wpseoai.com; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** No systematic side-by-side; "sometimes" presents multiple perspectives (not deliberate). [I — wpseoai.com; accessed Aug 13 2026]
6. **Persistent knowledge reuse:** None persistent across users (real-time retrieval each query; refreshed web index). [I — llmpulse.ai; accessed Aug 13 2026]
7. **Interactivity:** Ask/follow-up; click citations; Pro Search; Deep Research; model routing. [V — perplexity.ai help center; accessed Aug 13 2026]
8. **Coverage domain:** General web. [V — same]
9. **Automation level:** Fully automatic. [V — same]
10. **Access model:** Freemium (free + Pro/Enterprise subscription). [V — clickrank.ai/perplexity-ai; accessed Aug 13 2026]

#### Originality.ai Fact-Check feature
1. **Unit of analysis:** Statement of fact within a document. [V — help.originality.ai/en/article/fact-checker-dqwo21; accessed Aug 13 2026]
2. **Claim decomposition:** Automatic identification of factual statements (not premise decomposition). [V — same]
3. **Evidence-quality metadata:** Source-level (≥1 source per fact with URL/title/date). [V — originality.ai/automated-fact-checker; accessed Aug 13 2026]
4. **Verdict behavior:** Verdicts ("Potentially True"/"Potentially False" per statement) plus sources. [V — help.originality.ai; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** No (provides sources to verify; not deliberate supporting/contrasting split). [I — same]
6. **Persistent knowledge reuse:** None persistent (live search per scan). [I — originality.ai/blog/exploring-fact-checking-solutions; accessed Aug 13 2026]
7. **Interactivity:** Paste/upload text; per-statement true/false; generate citations (APA/MLA/Chicago/IEEE). [V — originality.ai/blog/feature-fact-checking-citations; accessed Aug 13 2026]
8. **Coverage domain:** General web / content writing. [V — originality.ai; accessed Aug 13 2026]
9. **Automation level:** Fully automatic. [V — help.originality.ai; accessed Aug 13 2026]
10. **Access model:** Subscription (credit-based; part of Originality.ai suite). [V — originality.ai; accessed Aug 13 2026]

#### Wolfram Alpha
1. **Unit of analysis:** Computational/factual query. [V — wolframalpha.com/tour; accessed Aug 13 2026]
2. **Claim decomposition:** None (linguistic parse to computation, not premise decomposition). [I — wolframalpha.com/about; accessed Aug 13 2026]
3. **Evidence-quality metadata:** None per se; provides "Sources" references but no study-level metadata. [V — wolframalpha.com/faqs; accessed Aug 13 2026]
4. **Verdict behavior:** Computes answers (authoritative outputs, not truth verdicts on contested claims). [V — wolframalpha.com/tour; accessed Aug 13 2026]
5. **Symmetric contrasting-evidence:** No. [I — same]
6. **Persistent knowledge reuse:** Structured KB — the curated Wolfram Knowledgebase, per its own Tour page comprising "10+ trillion pieces of data from primary sources with continuous updating" and "50,000+ types of algorithms & equations." [V — wolframalpha.com/tour; wolframalpha.com/about; accessed Aug 13 2026]
7. **Interactivity:** Natural-language query; pods/subpods; step-by-step (Pro); API/widgets. [V — wolframalpha.com/faqs; accessed Aug 13 2026]
8. **Coverage domain:** Computational facts (math, science, geography, finance, etc.). [V — wolframalpha.com/tour; accessed Aug 13 2026]
9. **Automation level:** Fully automatic computation over expert-curated data. [V — wolframalpha.com/about; accessed Aug 13 2026]
10. **Access model:** Freemium (free + Pro subscription; API/enterprise). [V — futureaimind.com; accessed Aug 13 2026]

### Additional systems (decomposition and/or persistent fact-store)

#### Loki / Libr-AI OpenFactVerification
- **Unit:** Atomic claim (decomposed from long text). **Decomposition:** Automatic (five-step pipeline: decompose→checkworthiness→query→retrieve→verify). **Evidence metadata:** Source-level with transparency (evidence snippets + URL + support/refute/irrelevant relationship). **Verdict:** Human-in-the-loop verdict (semi-automated; withholds final judgment for the user). **Symmetric contrasting:** Yes (Evidence & Reasoning panel shows refuting/contextualizing/supporting evidence). **Persistent KB:** Check History (cache), not a dependency-tracked KB. **Domain:** General. **Automation:** Human-in-the-loop. **Access:** Open-source + Supporter Edition. [V — arxiv.org/abs/2410.01794; aclanthology.org/2025.coling-demos.4; github.com/Libr-AI/OpenFactVerification; accessed Aug 13 2026]
- **Significance:** The single closest existing system to Verity's decomposition + transparency ethic, but decomposes into *independent atomic claims* (not entailment-linked load-bearing premises) and has no persistent structured KB.

#### SAFE (Search-Augmented Factuality Evaluator, Google DeepMind)
- Automatic decomposition of long-form output into individual self-contained facts; per-fact agentic Google Search + reasoning; rates each supported/not-supported/irrelevant. Verdict-oriented (research evaluator, not consumer product); no persistent KB. [V — arxiv.org/pdf/2403.18802; github.com/google-deepmind/long-form-factuality; accessed Aug 13 2026]

#### FActScore
- Breaks a generation into atomic facts; computes % supported by a reliable knowledge source (Wikipedia). Evaluation metric, not a product; no dependency tracking. Verbatim: "we introduce FACTSCORE, a new evaluation that breaks a generation into a series of atomic facts and computes the percentage of atomic facts supported by a reliable knowledge source." [V — arxiv.org/abs/2305.14251; accessed Aug 13 2026]

#### FEVER / SciFact / AVeriTeC (academic benchmarks + systems)
- **FEVER:** 185k claims verified against Wikipedia; supports/refutes/NEI. **SciFact:** 1,409 scientific claims vs. 5,183 abstracts with rationale sentences; supports/refutes/neutral. **AVeriTeC:** per Schlichtkrull et al., "a new dataset of 4,568 real-world claims covering fact-checks by 50 different organizations. Each claim is annotated with question-answer pairs supported by evidence available online," reaching "inter-annotator agreement of κ=0.619 on verdicts"; verdicts include "conflicting evidence/cherry-picking"; provides a "knowledge store." All are verdict-oriented benchmarks; AVeriTeC's structured QA decomposition and knowledge store are the most Verity-adjacent. [V — aclanthology.org/2020.emnlp-main.609; arxiv.org/abs/2410.23850; arxiv.org/abs/2305.13117; accessed Aug 13 2026]

#### ClaimBuster / Duke Squash + Tech & Check
- **ClaimBuster:** Scores sentences for check-worthiness. **Squash:** Live automated fact-checking matching a speaker's claims to previously published ClaimReview fact-checks (a persistent fact-check database of ~60k claims); human "Gardener" selects matches. Verdict-oriented (displays existing fact-check ratings); reuses a persistent cache of prior fact-checks, not a dependency-tracked KB; project wound down. [V — reporterslab.org/tech-and-check; reporterslab.org/2021/06/28/the-lessons-of-squash; accessed Aug 13 2026]

#### Full Fact AI
- Automatic claim detection + matching against existing fact-checks + statistical claim checking; human-in-the-loop; internal/licensed tool; source/cache reuse. [V — fullfact.org/ai; poynter.org/fact-checking/2022; accessed Aug 13 2026]

#### Meedan Check
- Tipline-based workflow: claim clustering/matching (similarity analysis), human editorial fact-checks, persistent workspace of claims/fact-checks. Human-in-the-loop; claim matching not decomposition. [V — meedan.org/check; help.checkmedia.org; accessed Aug 13 2026]

#### Logically / Logically Facts
- AI + human fact-checking; source-credibility ratings (low/med/high); article reliability; verdicts and credibility scores; source breakdown showing support/contradict/partial. Human-in-the-loop; verdict-oriented. [V — logically.ai/announcements; forbes.com/sites/bernardmarr/2021/01/25; accessed Aug 13 2026]

#### Kialo (manual argument graphs)
- Manual pro/con argument trees (claims nested hierarchically under a thesis); collaborative, human-authored; no automated decomposition, no evidence-quality metadata, no verdicts (impact voting). The closest analog to Verity's *argument-graph structure*, but fully manual. [V — en.wikipedia.org/wiki/Kialo; blog.kialo-edu.com; accessed Aug 13 2026]

#### Retraction-tracking / propagation tools (for H7)
- **scite Reference Check:** flags retracted references via Crossref/PubMed; direct-status only. [V — scite.ai/features; nature.com/nature-index/news/new-bot-flags; accessed Aug 13 2026]
- **Zotero + Retraction Watch:** alerts on retracted items in library/citations; direct-status only. [V — library.smu.edu.sg; accessed Aug 13 2026]
- **RetractoBot:** emails authors who cited a now-retracted paper (1-hop); no propagation. [V — retracted.net; github.com/ebmdatalab/retractobot; accessed Aug 13 2026]
- **RetractionCheck / Crossref–Retraction Watch API:** federated retraction lookup only. [V — retractioncheck.com; crossref.org/blog/retraction-watch-retractions-now-in-the-crossref-api; accessed Aug 13 2026]
- **RedacTek:** per Doody's Collection Development Monthly review, "RedacTek assigns an issue association value to all records in the system. This value is calculated using the primary article's retraction status, the primary source retraction ratio, the secondary source retraction ratio, and the tertiary source retraction ratio" — the closest deployed approximation, but paper-level risk score across three citation generations, not claim-level invalidation. [V — dcdm.doody.com/2025/10/a-review-of-redactek; nature.com/nature-index/news/new-bot-flags; accessed Aug 13 2026]
- **Usman & Balke "retraction cascade" (TPDL 2024):** ranks non-retracted-but-likely-retractable citing papers; prioritization for human review, not automatic invalidation. [V — doi.org/10.1007/978-3-031-72437-4_7; accessed Aug 13 2026]

## Hypothesis Testing

### H1: No consumer product auto-decomposes claims into premises with per-premise evidence display.
**SURVIVES (qualified).** No *consumer* product does recursive claim→premise decomposition with per-premise evidence quality. Automatic decomposition exists, but in research tools (Loki, SAFE, FActScore) and it produces independent atomic facts, not entailment-linked premises; those tools are developer/researcher-facing, not consumer products, and are verdict-oriented. **Strongest counterexample:** Loki/OpenFactVerification — it auto-decomposes text into atomic claims and displays per-claim evidence with support/refute/irrelevant relationships in a UI. It weakens H1 most, but (a) it decomposes into atomic claims, not load-bearing premises that jointly entail a composite claim; (b) it is an open-source tool aimed at journalists/researchers, not a consumer product; and (c) it produces verdicts/credibility. So H1 survives for the "consumer + premise-entailment + no-verdict" conjunction.

### H2: scite.ai has no argument-structure layer above citations.
**SURVIVES. None found as of Aug 2026.** scite classifies citation statements as supporting/contrasting/mentioning and flags retractions, but builds no premise/argument graph over claims. No counterexample found; scite's own feature documentation describes only citation-level classification, Reports, Reference Check, and Assistant. [V — scite.ai/features; direct.mit.edu/qss/article/2/3/882; accessed Aug 13 2026]

### H3: No fact-checker offers symmetric, transparency-only inspection (no verdicts) as the core product.
**FAILS (partially).** Transparency-only, symmetric-by-design products DO exist — but at the source/article level, not the decomposed-claim level. **Strongest counterexample:** Ground News, whose core product is symmetric side-by-side left/center/right coverage with explicit no-adjudication positioning ("we keep our team's subjective opinions out of the product"). scite.ai is a second counterexample at the citation level (symmetric supporting/contrasting, no verdicts). H3 as stated fails; the defensible restatement is "no fact-checker offers symmetric transparency-only inspection *at the level of decomposed premises of a composite claim*," which survives.

### H7: No product does dependency-propagated invalidation.
**SURVIVES (qualified). None found as of Aug 2026** that performs true claim-level dependency-propagated invalidation. All shipping retraction tools (scite, Zotero, RetractoBot, RetractionCheck, Scholarcy) flag only the *direct* retraction status of individually cited papers. **Strongest counterexample:** RedacTek, which propagates a paper-level retraction-risk "issue association value" through three citation generations (primary/secondary/tertiary sources) — genuine multi-hop propagation, but of paper-level suspicion scores, not claim-level invalidation of specific downstream conclusions. Academic work (Usman & Balke's retraction-cascade ranking; van der Vet & Nijveen's error-propagation study) analyzes propagation but ships nothing claim-level. The only paradigm doing true dependency-directed invalidation — classical Truth Maintenance Systems — has never been applied to scholarly retractions. This is genuine white-space.

## Synthesis: Where Verity's Differentiation Holds and Where It Is Weakest

**Holds strongly:**
- **Recursive premise decomposition into an entailment structure (load-bearing premises that jointly entail the claim), presented to a consumer, with no verdict on contested composites.** No surveyed product does this. Loki/SAFE decompose into *independent atomic facts* and issue verdicts; Kialo builds entailment-like argument graphs but is fully manual with no automated evidence retrieval or quality scoring.
- **Dependency-tracked KB with propagated invalidation.** True claim-level dependency propagation exists nowhere as a product (H7). This is Verity's most defensible technical moat.
- **Combining study-level evidence quality with premise-level decomposition.** scite has study-level metadata but no decomposition; decomposition tools have only source-level metadata. The intersection is empty.

**Weakest / most contestable:**
- **Claim decomposition alone is not novel** — it is now standard in the fact-checking research literature (Loki, SAFE, FActScore, ProgramFC, AVeriTeC). Verity must frame its novelty as *entailment-structured, recursive, load-bearing premise* decomposition, not decomposition per se, or reviewers will see prior art.
- **Transparency-only positioning is not novel** — Ground News, Penn Media Bias Detector, and scite already occupy it (H3 fails at the source/article/citation level). Verity's novelty is transparency *at the decomposed-premise level*.
- **Persistent verified-fact store is not novel in isolation** — Wolfram Alpha (curated KB), ClaimReview/Squash and Meedan (fact-check caches), and AVeriTeC (knowledge store) all persist facts. Verity's novelty is the *dependency-tracked* nature and reuse for premise verification, not persistence itself.
- **Evidence-quality display is largely scite's turf for scientific literature.** If Verity targets scientific claims, it competes directly with scite's mature index (1.6B+ Smart Citations over 300M+ articles); Verity should differentiate on decomposition + dependency tracking, not on citation classification.

**Net:** Verity's defensible wedge is the *conjunction* — recursive entailment-structured premise decomposition + per-premise study-level evidence + a dependency-tracked KB that propagates invalidation + transparency-only output — not any single feature. Each individual feature has prior art; the combination does not exist as of Aug 2026.

## Recommendations
1. **Lead the proposal with the conjunction, not any single feature.** Explicitly concede that decomposition (Loki/SAFE), transparency-only (Ground News), study-level metadata (scite), and persistent fact stores (Wolfram) each exist — then show the matrix cell that is empty. This is the single most credibility-building move for a Wharton GenAI Studio reviewer who will know the fact-checking literature.
2. **Claim dependency-propagated invalidation as the hardest technical moat** (H7 white-space). Benchmark against RedacTek explicitly and articulate the paper-level→claim-level gap. If a reviewer cites RedacTek or Truth Maintenance Systems, be ready to explain why claim-level propagation over a verified-fact KB is materially harder and more useful than paper-level retraction-risk scoring.
3. **Reframe "decomposition" precisely** as recursive, entailment-structured, load-bearing-premise decomposition to preempt the "this is just SAFE/Loki" objection. Cite Loki as nearest prior art and state the entailment distinction in one sentence.
4. **Pick a beachhead domain.** Scientific/health claims maximize the value of study-level metadata and retraction propagation (and directly exploit the RedacTek/scite gap); general news maximizes the transparency-only differentiation vs. Ground News. Recommend scientific/health first, because the dependency-invalidation moat is strongest where retractions are structured, machine-readable data (Crossref/Retraction Watch).
5. **Benchmarks that would change the strategy:** if a consumer product ships recursive premise decomposition with per-premise evidence (weakens H1), or if RedacTek/scite add claim-level propagation (weakens H7), pivot emphasis to the transparency-only-at-premise-level + dependency-tracked-KB combination and accelerate. Conversely, if user testing shows readers want verdicts (the PolitiFact/Squash UX finding that users "assumed statements must be true if no fact-check was shown"), add an optional confidence display without abandoning the no-verdict default.

## Caveats
- Several pricing figures are third-party rather than primary vendor pricing pages: scite ($20/mo–$200/yr) is from a 2026 review corroborated by university LibGuides; Factiverse (~$10.86/mo) is from an aggregator and is marked inferred. Verify on vendor sites before publication.
- "Consumer product" is a judgment boundary; Loki and Full Fact straddle research/professional/consumer lines. H1 and H3 verdicts depend on that boundary and are stated conditionally.
- Marketing vs. verified functionality: vendor claims of "outperforming GPT-4" (Factiverse) and accuracy percentages (Originality.ai 86.69%, Logically) are vendor/benchmark claims and are not independently verified here.
- scite's index size is cited inconsistently across its own pages (1.6B+ Smart Citations on the features page vs. "over 1.8 billion unique citations" on the coverage page, updated June 2026); treat as approximate.
- Some 2026 arXiv preprints surveyed by the subagent (e.g., "sciwrite-lint") are date-coded but not peer-reviewed; treat the "no tool follows citations into referenced papers" claim as a recent-preprint assertion, though it is consistent with the mature-product survey.
- Penn Media Bias Detector's internal fact-extraction may involve claim-level LLM analysis not fully documented publicly; its "no decomposition" rating is inferred from published descriptions and the CHI '25 paper.