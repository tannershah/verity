# Verity Literature & Product Survey: Six Research Areas and Evaluation-Status Map

## TL;DR
- **Verity's individually-evaluable components sit on mature benchmarks** (evidence retrieval + verdict via FEVER/SciFact/AVeriTeC; entailment-step validity via EntailmentBank), **but its distinctive whole — recursive decomposition of *contested* real-world claims, symmetric no-verdict presentation, per-premise evidence-quality bias graphs, and KB invalidation propagation — has no established benchmark**, only proxy or nearest-neighbor evaluations.
- **The evidence-quality metadata Verity wants is only partly machine-readable today**: retraction status (OpenAlex `is_retracted`, Crossref `update-to`/Retraction Watch, PubMed "Retracted Publication") and study design (PubMed MeSH publication types like RCT/Meta-Analysis) are available via free APIs; citation intent (supporting/contrasting) is available only via Semantic Scholar (free, coarse 3-class, full-text-only) or scite (commercial); **sample size is NOT a structured field anywhere** and must be text-mined.
- **The belief-updating literature Verity leans on is real but now contested**: Costello, Pennycook & Rand's DebunkBot (Science 2024, ~20% reduction, durable at 2 months) received a formal **Editorial Expression of Concern from Science on June 11, 2026** over data-reproducibility and screening-criteria inconsistencies — this materially affects how Verity should cite the "facts change minds" claim.

## Key Findings
1. **Entailment-tree work gives Verity a ready-made, well-defined metric for step validity** (EntailmentBank's Leaves/Steps/Intermediates/Overall-AllCorrect with BLEURT-based intermediate matching), but every system in this line grounds in a *closed WorldTree-style corpus of known-true science facts* and terminates by axiom-matching in that corpus — none decomposes contested claims or attaches evidence-quality metadata.
2. **Claim-decomposition-for-factuality work has directly confronted Verity's hardest measurement problem** — how to score decomposition quality with no gold standard — and the answer is uniformly a *proxy* (entailment-based coverage, DecompScore, verifier-confidence deltas), plus the demonstrated finding that FActScore is *sensitive to the decomposition method itself*.
3. **Fact-verification benchmarks supply Verity's retrieval + verdict evaluation**, and AVeriTeC uniquely includes a "Conflicting Evidence/Cherry-picking" label — the closest existing analog to Verity's contested-claim stance — but that class is the worst-performing (near-zero F1 for many systems) and under-represented (<7% of data).
4. **LLM-annotation validation in ideological-discourse work (Nakshatri et al. 2025; Penn CSSLab Media Bias Detector) is done by human-agreement sampling and downstream classification, not gold benchmarks** — a direct template for how Verity should validate its bias graphs and decomposition of political claims.
5. **The belief-updating evidence is genuinely two-sided now**: replications and mechanism studies support a fact-driven effect, but a Science Expression of Concern (June 2026) plus skill-transfer critiques temper the strength.
6. **Knowledge-substrate reality check**: TMS (Doyle JTMS 1979; de Kleer ATMS 1986) offers the formal machinery Verity needs for premise invalidation; NELL is the cautionary tale on error/semantic drift in a never-ending KB; and the machine-readable-metadata layer is real but uneven.

---

## Details

### Area 1 — Entailment trees & natural-language proof generation

**EntailmentBank (Dalvi et al., EMNLP 2021, arXiv:2104.08661).**
- (a) *Task*: Given a hypothesis (question+answer), generate a multi-step entailment tree whose leaves are corpus facts and whose internal nodes are intermediate conclusions. Three task variants: (1) gold leaves only, (2) gold + distractor leaves, (3) full corpus retrieval.
- (b) *Method*: T5-based "EntailmentWriter" generating the whole tree in one shot.
- (c) *Metrics*: Four dimensions after Jaccard-based node alignment — **Leaves (F1, AllCorrect)**, **Steps (F1, AllCorrect)**, **Intermediates (F1, AllCorrect)**, **Overall-AllCorrect** (=1 only if all three are perfect). Intermediate correctness uses BLEURT to judge textual similarity of generated conclusions to gold. Task 2 Overall-AllCorrect ≈ 20.9% for EntailmentWriter (per NLProofS comparison table).
- (d) *Dataset*: EntailmentBank (~1,840 trees) built on ARC science questions + WorldTree V2 fact corpus.
- (e) *Does NOT handle relative to Verity*: no evidence-quality metadata; leaves assumed *true* (no provenance, no retraction/invalidation); grounds only in curated science facts; issues an answer/verdict rather than symmetric no-verdict presentation; termination = using all provided facts / matching corpus facts, not KB-grounding with confidence.

**METGEN (Hong et al., Findings of NAACL 2022, arXiv:2205.02593).** Module-based stepwise generation with a controller (ALBERT-xxlarge) selecting reasoning-type modules on T5-large; decomposes n-premise (n>2) steps into 2-premise steps. Uses EntailmentBank metrics; human expert validity check by three students per step/tree. Improves Steps/Overall over EntailmentWriter. *NOT*: same closed-corpus grounding, no evidence metadata, no invalidation.

**IRGR (Ribeiro et al., NAACL 2022, arXiv:2205.09224).** Iterative Retrieval-Generation Reasoner: alternates retrieval of premises with step generation; same four EntailmentBank metrics. *NOT*: no per-premise quality, no contested-claim handling.

**RLET (Liu et al., EMNLP 2022, arXiv:2210.17095).** Reinforcement-learning tree construction over EntailmentBank, rewarding correct step structure; same metrics. *NOT*: closed corpus, no metadata.

**NLProofS (Yang, Deng & Chen, EMNLP 2022, arXiv:2205.12443).** Verifier-guided stepwise proof search; a learned verifier scores steps to control search and reduce hallucinated steps. On EntailmentBank Task 2 it raised **Overall-AllCorrect from 20.9% → 33.3%** and **Leaves-AllCorrect from 35.6% → 58.8%**, beating T5-11B EntailmentWriter with only T5-large. *NOT*: verifier judges entailment validity, not evidence quality; no provenance/invalidation; closed corpus.

**LAMBADA (Kazemi et al., ACL 2023, arXiv:2212.13894).**
- (a) *Task*: Logical reasoning over natural-language rule bases; decide if a goal is provable and produce the proof.
- (b) *Method*: **Backward chaining** decomposed into four LM-prompted sub-modules (Fact Check, Rule Selection, Goal Decomposition, Sign Agreement) — the closest published analog to Verity's recursive premise decomposition.
- (c) *Metrics*: label accuracy + proof accuracy; large gains over Chain-of-Thought and Selection-Inference at depth, and ~11.8× fewer inference calls than SI at Depth-5.
- (d) *Datasets*: ProofWriter (esp. Depth-5), PrOntoQA, ParaRules.
- (e) *NOT relative to Verity*: operates over *given synthetic axioms* (closed-world toy rule bases), not retrieved real-world evidence; termination = axiom/fact match in the provided theory; no evidence-quality metadata; produces a proved/disproved verdict.

**ProofWriter (Tafjord, Dalvi & Clark, Findings ACL-IJCNLP 2021, arXiv:2012.13048).** T5 generative model producing implications + proofs over natural-language theories (RuleTaker/ParaRules); iterating a 1-step generator yields reliable proofs; +9% proof accuracy over PRover, generalizes to unseen depths. Supports abduction (minimal missing facts). *NOT*: synthetic closed-world theories, no evidence grounding/metadata, verdict-issuing.

**Entailer (Tafjord, Dalvi Mishra & Clark, EMNLP 2022).** Answers questions with faithful chains of reasoning by generating and self-verifying proofs grounded in the model's own beliefs. *NOT*: grounds in model parametric belief rather than an external provenance-tracked KB; no evidence-quality layer; produces answers.

**NELLIE (Weir, Clark & Van Durme, IJCAI 2024, arXiv:2209.07662).**
- (a) *Task*: Grounded, compositional QA as entailment-tree proof search over an NL corpus of authoritative facts.
- (b) *Method*: Prolog-style backward-chaining inference engine where handcrafted rules are replaced by an LLM dynamic rule generator + guided generation + semiparametric dense retrieval; recursively decomposes a hypothesis into subqueries proved from the knowledge store or recursively.
- (c) *Metrics*: QA accuracy + grounded-explanation quality; outperforms a similar-sized SOTA reasoner (Entailer/Tafjord 2022).
- (d) *Datasets*: EntailmentBank + science QA; exploits both semi-structured and NL corpora.
- (e) *NOT relative to Verity*: this is architecturally the closest system — recursive decomposition + KB grounding + termination on store facts — but it has **no evidence-quality metadata (study design, retraction, source diversity), no invalidation propagation, and issues an answer** rather than symmetric no-verdict output; corpus is "authoritative facts," not contested real-world claims with contrasting evidence.

*Termination/validity synthesis for Verity*: across this area, a "valid decomposition step" is defined structurally (correct premises selected + correct intermediate conclusion, matched to gold by alignment + BLEURT), and recursion **terminates by grounding leaves in a fixed corpus of assumed-true facts** (WorldTree) or the provided axiom set. None models leaf *trustworthiness*, retraction, or continued validity — exactly Verity's KB-invalidation gap.

### Area 2 — Claim decomposition for factuality

**FActScore (Min et al., EMNLP 2023, arXiv:2305.14251).** Breaks a generation into atomic facts; % supported by a reliable source (Wikipedia). Human annotation inter-annotator agreement 96%/90%/88% (InstructGPT/ChatGPT/PerplexityAI); automated estimator <2% error vs. humans; ChatGPT biographies score ~58%. Dataset: 549 biography prompts. *NOT relative to Verity*: no recursive premise entailment (flat atomic facts), binary supported/unsupported (no evidence-quality gradient, no study design/retraction), single-source grounding, no invalidation.

**SAFE / Long-form factuality (Wei et al., NeurIPS 2024, arXiv:2403.18802).** Decompose response → atomic facts → multi-step Google-Search reasoning per fact; metric F1@K (LongFact prompt set, 2,280 prompts, 38 topics). SAFE agrees with crowd humans **72%** on ~16k facts; wins **76%** of 100 disagreement cases; >20× cheaper. *NOT relative to Verity*: dynamic web references (no persistent provenance-tracked KB, no invalidation), no evidence-quality metadata, no recursive entailment, no symmetric contested-claim treatment.

**VeriScore (Song, Kim & Iyyer, Findings of EMNLP 2024, arXiv:2406.19276).** Extracts only *verifiable* claims (rejecting the FActScore/SAFE assumption that all claims are verifiable), with inter-sentence context for self-contained claims; retrieve + verify (supported/unsupported/inconclusive); F1 combining precision + recall over 8 tasks. *NOT relative to Verity*: still flat verifiable-claim extraction, no premise-entailment recursion, no evidence-quality bias graph, no invalidation.

**A Closer Look at Claim Decomposition (Wanner, Ebner, Jiang, Dredze & Van Durme, \*SEM 2024, arXiv:2403.11903).** Shows FActScore is **sensitive to the decomposition method** — error can come from the decomposer, not just the generator. Introduces **DecompScore** (adaptation of FActScore) to measure decomposition quality without gold, and a Russellian/neo-Davidsonian LLM decomposition improving quality. This is the core "no-gold-standard decomposition quality" answer: measure quality by number of *supported* subclaims / coverage proxy. *NOT relative to Verity*: still Wikipedia-grounded, no entailment structure, no evidence metadata.

**DnDScore (Wanner, Van Durme & Dredze, EMNLP 2025, arXiv:2412.13175).** Studies the tension between decomposition (isolating atomic facts) and decontextualization (re-inserting context so subclaims are verifiable); finds the choice of strategy materially changes factuality scores. Related: Molecular Facts (Gunjal & Durrett 2024), CORE (Jiang et al. 2024, informative subclaim selection), WiCE (Kamoi et al. 2023, real-world subclaim entailment). *NOT relative to Verity*: measures verification-score stability, not per-premise evidence quality; no invalidation; no contested-claim symmetry.

*Synthesis for Verity*: The field's consensus is that decomposition **has no gold standard**; quality is measured by *entailment/coverage proxies* (does the union of subclaims entail the original? is each subclaim atomic, decontextualized, verifiable?) and by *downstream verifier sensitivity*. This is precisely a Bucket-2 (proxy-only) status for Verity's decomposition faithfulness.

### Area 3 — Fact-verification benchmarks

**FEVER (Thorne et al., NAACL 2018).** 185k claims over Wikipedia; labels **Supported / Refuted / NotEnoughInfo**; requires retrieving evidence sentences + verdict; FEVER score credits verdict only if correct evidence retrieved. Dominant retrieval: TF-IDF/BM25 → dense retrieval → LLM query generation over successive FEVER workshops. *NOT relative to Verity*: single-source (Wikipedia) closed corpus, no evidence-quality metadata, verdict-issuing, no premise entailment tree.

**SciFact (Wadden et al., EMNLP 2020).** 1.4K expert-written biomedical claims from citances; corpus of 5,183 abstracts; labels **SUPPORTS / REFUTES / NOINFO** with **rationale sentences**; pipeline = abstract retrieval → rationale selection → label prediction. SciFact-Open (2022) expands corpus to 500K abstracts. *NOT relative to Verity*: rationale = evidence *sentences*, not study-design/sample-size/retraction metadata; no per-premise recursion; verdict-issuing; no invalidation.

**AVeriTeC (Schlichtkrull et al., EMNLP 2023, arXiv:2305.13117).** 4,568 real-world fact-checked claims from 50 organizations; QA-pair evidence from the web; four labels: **Supported / Refuted / Not Enough Evidence / Conflicting Evidence/Cherry-picking**. **AVeriTeC score** = fraction of claims with correct label AND evidence quality above a threshold (originally Hungarian METEOR ≥0.25; 2025 uses Ev2R recall with LLaMA-3.3-70B).
- *SOTA*: 2024 shared task (FEVER workshop, arXiv:2410.23850) — 21 submissions, 18 beat baseline; **winner TUDA_MAI, AVeriTeC score 63%**; leaderboard dominated by GPT-4o; AIC CTU reported 50.4% (Aug 2024). 2025 (AVeriTeC 2.0, 8th FEVER workshop, Ev2R metric) — **CTU AIC 0.332**, HerO 2 0.271, baseline 0.202 on test; a separate 2025 line (VILLAIN) reported a veracity score of 0.546. Conflicting/Cherry-picking is the hardest class — near-zero F1 for many systems, <7% of training data.
- (e) *NOT relative to Verity*: AVeriTeC's Conflicting/Cherry-picking label is the *closest analog* to Verity's contested-claim stance, but it is still a **verdict** (a fifth category), not symmetric no-verdict presentation; no evidence-quality metadata per premise (study design/retraction); no recursive entailment tree; no KB invalidation.

*Retrieval architectures across the three*: BM25/TF-IDF baselines → dense retrieval (DPR, mxbai/FAISS in CTU AIC) → LLM query/question generation (AVeriTeC systems generate QA pairs). This gives Verity established retrieval evaluation, but only for verdict-oriented tasks.

### Area 4 — Ideological discourse decomposition & LLM-annotation validation

**Talking Point based Ideological Discourse Analysis (Nakshatri et al., Findings of ACL 2025, arXiv:2504.07400).**
- (a) *Task*: Analyze ideological discourse in news events; represent articles via relational **talking points** (entities, roles, media frames, topic), build a vocabulary of prominent talking points, generate ideology-specific partisan perspectives.
- (b) *Method*: Theory-driven (ideological discourse analysis) framework layering LLM extraction + clustering (PTP clusters) over news events.
- (c) *Validation/metrics (the critical question)*: **Ideology classification** (predict left/right for unseen articles using generated perspectives) and **partisan classification** at the PTP-cluster level, plus **human assessments** and automated evaluations of intermediate steps. No gold ideology benchmark exists, so validity = downstream classification performance + human ratings.
- (d) *Dataset*: KeyEvents (Nakshatri et al. 2023), sampled from NELA-2021.
- (e) *NOT relative to Verity*: characterizes *perspectives*, not per-premise evidence quality; no entailment grounding, no KB provenance/invalidation; but its validation-by-downstream-classification + human-agreement is a direct template for Verity's contested-claim decomposition validation.

**Penn CSSLab Media Bias Detector (Watts et al., PennMAP; launched June 2024).** Scrapes **10 online newspapers four times a day** (per The Pennsylvania Gazette quoting Watts: "scraping articles from 10 online newspapers four times a day"; The Daily Pennsylvanian, March 2026, notes it "initially collected information from 10 publications" with a January plan "to expand to cover 22 publications," extracting the 20 "most prominent" articles per site). GPT-4 classifies article topic/subtopic, tone, and political lean; events via sliding-window semantic similarity.
- *Validation (critical question)*: (1) **human-in-the-loop** — Penn undergraduate RAs monitor a random sample of GPT labels and adjust; (2) **construct validity** — outputs compared to expert human evaluators (PhD students in media/politics), reported "correlation was really high," with GPT-4 sometimes *outperforming* humans on some tasks; (3) explicitly refuses to score bias against "truth," instead comparing outlets to each other ("you can't really measure bias directly"). This last point is a direct precedent for Verity's *symmetric, no-verdict* philosophy.
- *NOT relative to Verity*: no premise entailment, no evidence-quality metadata on sources, no KB invalidation; validation is by sampled human agreement, not a benchmark.

### Area 5 — Belief updating via evidence exposure

**Costello, Pennycook & Rand, "Durably reducing conspiracy beliefs through dialogues with AI" (Science, Sept 13 2024, 385(6714):eadq1814; DOI 10.1126/science.adq1814).**
- *Design*: 2,190 conspiracy believers engaged in personalized, evidence-based dialogues with GPT-4 Turbo across two experiments.
- *Effects (verbatim Science abstract)*: "The intervention reduced conspiracy belief by ~20%. The effect remained 2 months later, generalized across a wide range of conspiracy theories, and occurred even among participants with deeply entrenched beliefs." Perspective by Bago & Bonnefon (Science 2024, 385:1164-1165). Won the 2026 AAAS Newcomb Cleveland Prize; cited 192 times per Clarivate's Web of Science.
- *NOT relative to Verity*: measures *persuasion/attitude change*, not decomposition/verification quality; the AI issues persuasive verdicts (opposite of Verity's no-verdict stance) — relevant as *motivation* (facts+evidence move beliefs) not as a component evaluation.

**Follow-ups / replications supporting the effect**:
- Costello, Pennycook & Rand, "Just the facts: How dialogues with AI reduce conspiracy beliefs" (OSF preprint 2025, 10.31234/osf.io/h7n8u): mechanism study, 8 treatment arms (N≈1,297); effect robust across manipulations (whether told the AI aims to persuade, whether asked to debate, whether concise) — supports that **facts/evidence, not framing, drive the effect**.
- Boissin, Costello, Spinoza-Martín, Rand & Pennycook, "Dialogues with large language models reduce conspiracy beliefs even when the AI is perceived as human" (PNAS Nexus 4(11), Nov 2025, pgaf325; preregistered, N=955): the messenger being AI is not necessary — the *message* drives it.
- Related extensions: Hornsey et al. (Curr. Opin. Psychol. 2026) science skepticism; Bretter et al. (Nat. Energy 2025) EV misinformation; Czarnek et al. (2025) climate; Hou et al. (Nat. Med. 2025) HPV vaccine chatbot RCT.

**Criticisms / disputes (presented symmetrically)**:
- **Science Editorial Expression of Concern (Thorp, Science, June 11 2026, 392(6803):1131; PMID 42275523).** Per Retraction Watch (June 11 2026), authors learned of issues with the public dataset that "made it challenging to reproduce some of the specific values reported in the manuscript," and discovered "inconsistencies in the application of screening criteria between" experiments. Costello (to Retraction Watch): "grateful that these issues were surfaced and to have a chance to correct some methodological and supporting details." This is a formal flag, not a retraction — but it materially weakens confidence in the exact effect sizes.
- **Skill-transfer critique**: "Dialogues with AI Reduce Beliefs in Misinformation but Build No Lasting Discernment Skills" (arXiv:2510.01537, 2025) — belief shifts do not teach users to detect misinformation independently.
- **Dual-use caution**: "Large language models can effectively convince people to believe conspiracies" (arXiv:2601.05050, 2026) — the same persuasion machinery works in the *wrong* direction.
- *Sample caveat*: the studies rely on online panels (Prolific/CloudResearch-style), raising demand-effect and generalizability questions common to this literature.

### Area 6 — Knowledge substrate: verified facts, provenance, invalidation

**(a) NELL (Never-Ending Language Learning).** Foundational: Carlson et al., "Toward an Architecture for Never-Ending Language Learning," AAAI 2010, pp. 1306–1313; canonical: Mitchell et al., "Never-Ending Learning," CACM 61(5):103–115, 2018 (DOI 10.1145/3191513; expands AAAI 2015). Architecture = coupled semi-supervised learning across components — **CPL** (contextual pattern learner), **CSEAL** (semi-structured/table extractor), **CMC** (morphological classifier), **RL** (first-order rule learner), unified by a **Knowledge Integrator (KI)** that promotes candidate beliefs. Runs EM-like loop; couples thousands of learning tasks via mutual-exclusion/subset constraints to generate implicit negatives. **Promotion**: candidate → believed when supported by a high-confidence source or multiple independent sources (posterior thresholds cited as 0.75 in AAAI 2010; ≥0.9 in NELL2RDF). Each promoted fact tagged with iteration-of-promotion, score, and source components (provenance). **Demotion/revision**: KI (aka ErrorBasedIntegrator) can delete beliefs via consistency/coupling violations; ~10–15 min/day human oversight approving rules. **Scale**: ~1.78M concepts, 623 relations, ~2.2M beliefs by iteration 905 (arXiv:1606.06361); ran to iteration 1115 (Sept 3 2018). **Failure mode**: acknowledged accumulation of incorrect beliefs / **semantic drift** over iterations, mitigated (not solved) by coupling and periodic human rule approval. *Lesson for Verity*: provenance-tagged promotion + coupling constraints are exactly the KB pattern Verity needs, and drift is the central risk of a persistent verified-fact KB.

**(b) Truth maintenance systems.**
- **Doyle, "A Truth Maintenance System," Artificial Intelligence 12(3):231–272, 1979** (JTMS): nodes carry **justifications**; belief status labeled **IN/OUT**; **dependency-directed backtracking** traces contradictions to responsible assumptions and retracts precisely those; when an upstream premise is retracted, IN/OUT propagation automatically makes dependent conclusions OUT — i.e., automatic conclusion retraction. Maintains one consistent belief set.
- **de Kleer, "An Assumption-based TMS," Artificial Intelligence 28(2):127–162, 1986** (ATMS; companions "Extending the ATMS" pp.163–196, "Problem Solving with the ATMS" pp.197–224; foundations de Kleer & Reiter, AAAI 1987): tracks **assumptions**, **environments** (assumption sets), **nogoods** (inconsistent environments), and **labels** (minimal consistent environments per node), enabling simultaneous **multiple contexts** — "context switching is free, and most backtracking (and all retraction) is avoided." Invalidating a premise marks environments nogood; conclusions lose validity only in those environments.
- *Lesson for Verity*: JTMS is the direct formal model for **premise invalidation propagation** when upstream evidence is retracted; ATMS is the model if Verity wants to hold multiple evidential contexts (e.g., contested claims) simultaneously without committing to one.

**(c) Wikidata-style provenance.** Statement-level **references**, **qualifiers**, and **ranks** (preferred/normal/**deprecated**) provide a working model of per-statement provenance and soft invalidation (deprecated rank ≈ "known-superseded but retained"). Directly analogous to Verity's per-premise provenance + invalidation flags.

**(d) scite Smart Citations.** Nicholson et al., "scite: A smart citation index...," Quantitative Science Studies 2(3):882–898, 2021 (DOI 10.1162/qss_a_00146). Classifies citation statements as **Supporting / Contrasting(disputing) / Mentioning** via a SciBERT classifier (explicitly not sentiment). Class distribution highly imbalanced — verbatim: "the average distribution of citation statements [is] 92.6% mentioning, 6.5% supporting, and 0.8% contrasting statements." Coverage: 880M classified citation statements at 2021 publication; **1.6B+ citation statements / ~300M full-text articles** currently (scite.ai, part of Research Solutions). Accuracy: the paper reports production per-class precision >80%, but an independent 2023 evaluation (*Hypothesis* journal) found scite heavily over-labels supporting/contrasting citations as "mentioning" on a retracted-paper sample. **API**: commercial only (Developer plan via sales; no free public API tier); Personal plan ~$20/user/month. *Lesson for Verity*: scite gives supporting/contrasting metadata but is paid and coarse; Semantic Scholar is the free alternative (see below).

**(e) Retraction tracking.** The **Retraction Watch database — now part of Crossref — had just shy of 55,000 retraction entries as of its Dec 26, 2024 year-in-review** (the Sept 2023 Crossref acquisition announcement itself cited ~43,000), updated on working days and made **free/public** by Crossref; propagated into Crossref (`update-to`/`updated-by`, source `retraction-watch`) and OpenAlex (`is_retracted`).

**Machine-readable evidence-quality metadata via public APIs (as of 2025–2026):**

| API | Retraction status | Study design / publication type | Citation intent/context | Sample size (N) | Access / cost |
|---|---|---|---|---|---|
| **OpenAlex** | `is_retracted` boolean (from Retraction Watch via Crossref) — but a single boolean *collapses* correction/EoC/retraction, causing mislabels (arXiv:2403.13339; false positives Dec 22 2023–Mar 19 2024) | `type` field (article/preprint/etc.), not study design | No | No | Free, open |
| **Crossref** | `update-to`/`updated-by` with `type` (retraction), `source` (publisher/retraction-watch); Crossmark; filter `update-type:retraction` | `type` (journal-article etc.), not RCT/meta-analysis | No | No | Free (Plus tier optional) |
| **PubMed/Entrez** | MeSH "Retracted Publication" (D016441, 1996) and "Retraction of Publication" (D016440) as PublicationType | **Yes** — MeSH PublicationType includes "Randomized Controlled Trial," "Meta-Analysis," "Systematic Review" | No | No | Free; 3 req/s (no key), 10 req/s (free key) |
| **Semantic Scholar Graph API** | No dedicated field | No | **Yes** — citation intents (Background/Method/Result) + citation contexts, full-text papers only | No | Free; optional key for dedicated limits; 214M+ papers |
| **scite** | Yes (retraction alerts) | No | **Yes** — Supporting/Contrasting/Mentioning | No | Commercial only |

**Sample size is NOT a structured field in any of these** — confirmed. Nicholson et al. (2021) themselves note (verbatim) it "would be exceedingly difficult to also classify the sample size, statistics, and other parameters that define how robust a finding is" (adding that "a supporting citation statement might come from a paper where the experimental evidence is weak and vice versa"); recent systematic-review NLP corpora (arXiv:2604.22864; arXiv:2606.17041) extract N from OCR'd full text via LLM pipelines precisely because metadata lacks it. **Verity must text-mine N from abstracts/full text, with attendant accuracy risk.**

---

## Recommendations

**Stage 1 — Build on established benchmarks first (Bucket 1).**
- Evaluate Verity's retrieval + any internal verdict-classification module on **FEVER** (Supported/Refuted/NEI) and **SciFact** (biomedical, with rationale selection) to get comparable numbers; use **AVeriTeC** for real-world claims and lean on its Conflicting/Cherry-picking subset as your closest contested-claim testbed.
- Evaluate entailment-step validity with **EntailmentBank's Leaves/Steps/Intermediates/Overall-AllCorrect** metrics on your decomposition trees; adopt **NLProofS-style verifier-guided search** to raise step validity.
- *Threshold to advance*: reach an AVeriTeC score competitive with the 2024 shared-task band (baseline 0.202 → top 0.63 on the old Hungarian-METEOR metric; new Ev2R metric top ≈0.33) on a held-out contested-claim set before trusting decomposition on live claims.

**Stage 2 — Instrument proxy evaluations for components without gold (Bucket 2).**
- Measure decomposition faithfulness with **entailment-based coverage + DecompScore** (Wanner et al. 2024) and **verifier-confidence deltas** (dynamic-decomposition MDP line); report the *sensitivity* of downstream verdicts to decomposition method as a first-class metric.
- Validate LLM annotation of premises and bias exactly as **Nakshatri et al. 2025 and the Penn Media Bias Detector** do: sampled human-agreement (RA audits), inter-model agreement, expert construct-validity checks, and downstream classification. Report correlation with expert PhD raters.
- Wire evidence-quality metadata from **free APIs today**: OpenAlex/Crossref for retraction, PubMed MeSH PublicationType for study design (RCT/meta-analysis), Semantic Scholar for citation intent (Background/Method/Result). Defer scite unless budget allows its Supporting/Contrasting granularity. **Text-mine sample size**; treat it as low-confidence.

**Stage 3 — Design first-of-kind evaluations for Bucket-3 components.**
- **KB invalidation propagation correctness**: implement a **JTMS (Doyle 1979)** layer so that retracting an upstream premise (e.g., a source flagged retracted via Retraction Watch) automatically demotes dependent premises; test with synthetic retraction-injection (nearest neighbor: NELL demotion tests, Wikidata deprecated-rank handling, "Persistence of Retracted Papers on Wikipedia" arXiv:2509.18403 propagation study).
- **Symmetric no-verdict presentation quality** and **bias-graph usefulness**: no benchmark exists; run controlled human-subject studies borrowing the **belief-updating paradigm (Costello/Pennycook/Rand)** — but measure *calibration/discernment* (per the arXiv:2510.01537 skill-transfer critique), not persuasion, since Verity deliberately does not persuade.
- **Recursive decomposition of contested claims**: extend AVeriTeC's Conflicting/Cherry-picking cases into an entailment-tree annotation; this is a publishable contribution in itself.

**Citing the belief-updating motivation**: cite Costello et al. 2024 **with the June 2026 Editorial Expression of Concern noted**, and pair it with the PNAS Nexus 2025 replication and the "Just the facts" mechanism preprint so the proposal's motivation does not rest on a single flagged paper.

## Caveats
- **Numbers are metric-dependent and shifting**: AVeriTeC's 2024 (Hungarian METEOR, top 63%) and 2025 (Ev2R, top ≈0.33) scores are *not comparable*; cite the metric explicitly.
- **The DebunkBot Expression of Concern (June 2026) is not a retraction** but does undercut exact effect sizes; the direction of the effect is corroborated by independent replications.
- **Some NELL precision figures (74%/85%) and the "117M beliefs" claim trace to a low-reliability secondary source (Grokipedia)**; the peer-reviewed snapshot (~2.2M beliefs, iteration 905) is the citable figure.
- **scite accuracy is disputed**: vendor reports >80% per-class precision; an independent 2023 study found heavy over-labeling as "mentioning."
- **OpenAlex `is_retracted` is known to have had false positives** (Dec 2023–Mar 2024) and collapses distinct update types; cross-check against Crossref `update-nature` / PubMed.
- **No system in Areas 1–4 combines all of Verity's pipeline** (recursive entailment + provenance-tracked KB + evidence-quality metadata + invalidation + symmetric no-verdict). NELLIE is architecturally closest but lacks the metadata, invalidation, and no-verdict layers. This confirms Verity's novelty and its Bucket-3 evaluation burden.

---

### Evaluation-Status Map (Conclusion)

**Bucket 1 — Established benchmarks exist:**
- Evidence retrieval + verdict classification → FEVER (2018), SciFact (2020), AVeriTeC (2023–2025).
- Entailment-step validity → EntailmentBank Leaves/Steps/Intermediates/Overall-AllCorrect (2021), with NLProofS/METGEN/RLET/IRGR as method baselines.

**Bucket 2 — Proxy evaluations only:**
- Decomposition faithfulness → DecompScore/entailment-coverage/verifier-confidence deltas (Wanner 2024; DnDScore 2025); no gold standard.
- LLM annotation of premises/bias → human-agreement sampling + downstream classification + expert construct validity (Nakshatri 2025; Penn Media Bias Detector).
- Citation-intent / evidence-quality tagging → Semantic Scholar (free, 3-class) or scite (paid), each with accuracy caveats.

**Bucket 3 — No established evaluation (design new; nearest neighbors noted):**
- Symmetric no-verdict presentation quality → nearest neighbor: belief-calibration studies (adapt Costello 2024 paradigm to measure discernment, not persuasion).
- Bias-graph usefulness → nearest neighbor: Media Bias Detector human-agreement + user studies.
- Recursive decomposition of *contested* real-world claims → nearest neighbor: AVeriTeC Conflicting/Cherry-picking subset extended to entailment trees.
- KB invalidation-propagation correctness → nearest neighbor: JTMS/ATMS formal consistency tests + synthetic retraction-injection + retracted-citation-propagation studies (arXiv:2509.18403).