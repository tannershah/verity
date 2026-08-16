# Positioning

How Verity is positioned against the landscape, and the citation discipline that positioning requires.

**Lead with the conjunction argument and the invalidation differentiator — not the empty matrix cell.** An empty cell in a self-defined matrix is weak evidence of an opportunity; the null hypothesis a sharp reader applies is that the cell is unoccupied because it isn't worth occupying. The conjunction argument and the adjacent-product demand evidence answer that. The empty cell alone does not.

---

## 1. The conjunction argument

Every ingredient ships somewhere today. The conjunction does not.

| Layer | Ships in | But |
|---|---|---|
| Automatic claim decomposition | Loki (`product-009`), SAFE (`product-010`) | Into **independent atomic facts**; verdict-oriented; no persistent KB |
| Study-level evidence metadata | scite (`product-002`) | Per **citation statement**; no argument layer above it |
| Symmetric no-verdict presentation | Ground News (`product-001`), Penn MBD (`product-004`) | At **article/source level**, never below |
| Persistent fact stores | Wolfram Knowledgebase (`product-008`), ClaimReview caches (`product-015`) | None **dependency-tracked**; no product propagates a retraction to dependent claims |

**Why the conjunction is load-bearing rather than gerrymandered — this is the argument, not the table:**

The layers only function together. Retraction propagation needs entailment-linked premises to propagate *along* — atomic-fact decomposition hands a dependency tracker a graph with no edges. And per-premise evidence quality only matters when premises are load-bearing rather than independent trivia.

That is why NELLIE (`lit-009`, IJCAI 2024), the architecturally closest research system, built a recursive KB-grounded core rather than extending a Loki-style atomic pipeline. **A fast-follower forking Loki reproduces the interface, not the dependency structure the invalidation runs on.** NELLIE already does recursive backward-chaining decomposition grounded in a fact store and lacks exactly the three layers Verity adds: evidence-quality metadata, invalidation propagation, no-verdict output.

The closest analog to the argument graph itself is Kialo (`product-019`) — human-authored, no evidence retrieval, no quality metadata: the manual version of what Verity automates.

Do not cite AVeriTeC's knowledge store as a shipping persistent fact store. `product-014` codes `persistent_knowledge_reuse: none` — it is a benchmark artifact, not a reusable KB.

---

## 2. Adjacent products are demand evidence

Four independent teams shipped adjacent pieces of this design. **Name them** — they answer "is the cell empty because nobody wants it?"

| Product | Row | Shipped | Missing |
|---|---|---|---|
| Consensus | `product-025` | Atomic claim + study-level metadata + stance aggregate | Root-level verdict; no premise decomposition |
| ARGUMEND | `product-027` | Automated symmetric maps + **crux identification** | Root evidence-direction verdicts; no external evidence retrieval |
| The Society Library | `product-026` | Premise-level maps + evidence links | Human-curated; partial deployment |
| Elicit | `product-028` | Production study-metadata extraction | No decomposition |

Demand for the *ingredients* is priced: scite and Ground News both sustain paid subscription tiers for citation-level evidence metadata and symmetric coverage respectively. **Demand for the conjunction is what the prototype is built to test — an open question, not a proven market.** State it that way.

Elicit is also direct precedent for the text-mining plan: it does production sample-size and study-design extraction, which is the model for the one evidence field that isn't cleanly structured.

---

## 3. The invalidation differentiator — keep impact, uptake, and bet separate

Conflating these is the most likely way to overclaim here.

| Link | Evidence | What it establishes |
|---|---|---|
| **Impact** | VITALITY (`lit-031`) | Retraction contamination *matters*: excluding retracted RCTs reverses pooled-effect direction in **8.4%** (95% CI 6.8–10.1) and changes statistical significance in **16.0%** (95% CI 14.2–17.9) of contaminated meta-analyses |
| **Uptake** | RetractoBot RCT (`lit-033`) | **Null.** Mean citation-rate difference −0.007 (95% CI −0.055 to 0.041) across 15,921 papers. **80.6%** of responding authors were unaware of the retraction. Post-hoc, out-of-workflow notification to past citers does not change behavior |
| **Bet** | — | **Decision-time** surfacing to readers, editors, and synthesists evaluating a claim *now*. Not a demonstrated result |

Never write a sentence citing VITALITY as evidence that retraction *surfacing works*. VITALITY evidences impact; RetractoBot bounds uptake; the bet is a bet — label it.

Supporting context: 71.6% of retracted-paper citations on Wikipedia were initially problematic, with median persistence 3.68 years (arXiv:2509.18403).

---

## 4. Beachhead

**Scientific and health claims. News is roadmap.**

Chosen because leaves ground in **machine-readable fact** — retraction status via Crossref/Retraction Watch, study design via a free MeSH field — rather than contested testimony; and because the invalidation differentiator is strongest exactly where scite and RedacTek stop, at citation and paper level. It also satisfies the low-valence demo rule ([design.md](design.md)).

Current retraction volume: **66,000+** (Retraction Watch, as of August 2026).

---

## 5. The two strongest objections

### "Verity is Loki + scite + Ground News with a UI"

> Each of Verity's layers ships somewhere today — automatic decomposition in Loki, study-level evidence metadata in scite, symmetric no-verdict presentation in Ground News — and we cite them as prior art rather than discovering them. The conjunction is load-bearing, not gerrymandered, because the layers only function together: retraction propagation needs entailment-linked premises to propagate along (atomic-fact decomposition hands a dependency tracker a graph with no edges), and per-premise evidence quality only matters when premises are load-bearing rather than independent trivia. That is why the closest research system, NELLIE, had to build the same recursive KB-grounded core rather than extend a Loki-style atomic pipeline — a fast-follower forking Loki reproduces the UI, not the dependency structure the invalidation runs on.

**Concede what's true:** the components are commodities. The evidence layer is assembled from free APIs; the decomposition layer is open-source; the presentation posture is Ground News's. The conjunction is an **architecture claim, not a moat claim**, until the alethiology has accumulated facts worth reusing — and it starts empty. Say so before a reader does.

### "Backward chaining over an alethiology cannot terminate reliably on contested claims"

> Verity does not assume contested branches will ground; it enforces termination — depth budget plus a per-step verifier gate — and treats where grounding stops as signal: a branch that exhausts verifiability descent surfaces as an unverified premise with its symmetric evidence attached, which on contested material is the intended output, not a failure mode. Grounding rate, decomposition depth, and budget-exit rate are therefore reported as first-class metrics, and the beachhead is chosen so leaves ground in machine-readable fact — retraction status, MeSH study design — rather than contested testimony. The field's near-zero F1 on AVeriTeC's Conflicting/Cherry-picking class is a failure of forcing verdicts onto contested claims — Verity's argument, not its refutation — and extending that subset to premise-level annotation is scoped as a contribution precisely because the eval Verity needs does not yet exist.

---

## 6. Citation discipline — the belief-updating line

This line motivates the design and is contested. These rules are not stylistic.

1. **Cite Costello et al. 2024 (`lit-020`) once, for direction only** — "evidence-based AI dialogue can shift beliefs." **Never cite the ~20% / 2-month magnitudes**, even as upper bounds.
2. **The Editorial Expression of Concern rides in the same sentence** — "(Editorial Expression of Concern, *Science*, June 11, 2026)" — never a footnote. **Quote the EoC language; never characterize it.**
3. **State the replication record precisely.** Same-team: Boissin et al., *PNAS Nexus* 2025 (`lit-022`, three shared authors) and the "Just the facts" preprint (`lit-021`, same authors, unreviewed). **Plus one independent conceptual replication:** Meyer et al. 2024 (`lit-032`, reflective-dialogue paradigm). Claiming full independence overstates it; claiming same-team-only understates it.
4. **Use the critiques as design rationale, not as adversaries.** No lasting discernment skills from belief shifts (`lit-023`) is why the endpoint is discernment and calibration. Dual-use persuasion (`lit-024`) is why the verdict boundary exists.
5. **Cite debunkbot.com** as the persuasion-shaped productization Verity is *not*.
6. **Claim no empirical support for transparency-only efficacy.** There is none on either side. See [evaluation.md](evaluation.md).

---

## 7. Known soft spots

Carry these; do not paper over them.

- **H1 rests largely on one distinction** — atomic vs. entailment-linked — once the consumer boundary and verdict qualifiers are discounted.
- **H7 rests on a single third-party source.** See [open-questions.md](open-questions.md).
- **The alethiology starts empty**, so the differentiator is prospective. The architecture claim is what's defensible today.
- **Several hypotheses are narrower than first stated.** H3 and H5 were each falsified and restated; H4 split three ways. The answer to "you narrowed until the cell emptied" is the conjunction argument plus the demand evidence — not further qualifiers.
- **No user-demand evidence for entailment-structured premise inspection** appears anywhere in the research. The adjacent products are the closest proxy.
