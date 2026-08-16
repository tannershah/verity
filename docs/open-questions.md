# Open Questions

Everything undecided or unverified. Close an item by editing it out and recording the resolution in the document it affects.

---

## 1. Design decisions blocking the build

| # | Question | Why it matters | Blocks |
|---|---|---|---|
| **D-3** | **The second annotator** for the human step-validity protocol. Pilot N=5 is committed; the builder annotates with self-annotation disclosed as a bias ([evaluation.md](evaluation.md) §2); the second seat is unfilled | The ≥80% threshold is measured by this protocol and cannot run one-handed | D7 |

Resolved and recorded elsewhere: conflicted-state semantics and JTMS-vs-ATMS in
[design.md](design.md) §4.2, step shape (native n-ary) in §4.3, promotion policy and
re-validation as the M5 mechanisms in [build-plan.md](build-plan.md).

---

## 2. Unverified evidence

### Load-bearing

**RedacTek (`product-024`) has one source.** Every cell traces to a single third-party review; vendor primary documentation was never obtained. **H7 and the invalidation differentiator rest on this row's paper-level-vs-claim-level distinction.** If the review under-describes the product, or RedacTek has since shipped claim-level features, H7 weakens in the direction most damaging to the positioning.
→ *Obtain vendor primary documentation.*

**Unverified benchmark figures.** SEER, NLDR, and Task-1 successor numbers to NLProofS were never checked against primary PDFs. Don't quote them until they are; NLProofS's own in-paper figures are safe.

### Contextual

| Item | Detail |
|---|---|
| **Vendor and pricing figures** | scite pricing, Factiverse pricing and accuracy, Originality.ai's 86.69%, Logically's accuracy percentages are all marketing claims |
| **Unpublished replications** | Dartmouth / Nyhan DebunkBot replications are reported but unpublished. Do not cite as published |
| **Weakly-sourced rows** | `product-025`–`029`, `lit-034` entered without a second look. See [matrix README](../research/matrix/README.md) |
| **Perplexity (`product-006`)** | Nine of ten cells inferred from aggregators. Not load-bearing for any hypothesis, but don't lean on it |

### Source registry gaps

**19 URLs are cited by matrix rows but absent from `sources.jsonl`** — `lit-015`, `-022`, `-026`, `-027`, `-029`–`-034`, and `product-025`–`029`. Every enum value is legal and every product cell carries provenance, so the rows themselves are sound; the gap is that `sources.jsonl` is no longer a complete registry and can't be used to audit source coverage.

**20 of 98 registered sources still carry `verify_before_proposal: true`** — concentrated in `product-002`, `-006`, `-001`, `-005`, `-018`.

---

## 3. Watch items

| Watch | Consequence |
|---|---|
| **Belief Explorer** (`lit-034`) commercializes | **H5 falsified** |
| **Meyer reflection paradigm** productized | **H5 falsified** |
| **RedacTek or scite** adds claim-level propagation | **H7 falsified or weakened** |
| A **consumer product** ships recursive premise decomposition with per-premise evidence | **H1 falsified** |
| Any **automated** system ships symmetric no-verdict premise-level inspection | **H3 falsified** |
| **scite** ships a premise/argument graph | **H2 falsified** |

If one fires, record it and fall back to the surviving conjuncts of the [positioning](positioning.md) argument — don't narrow the hypothesis again.

---

## 4. Open empirical questions

- **Does transparency-only presentation help?** No evidence exists on either side. Scoped in [evaluation.md](evaluation.md).
- **Is there demand for entailment-structured premise inspection?** Nothing in the research found demand evidence. The four adjacent products are the closest proxy; the prototype is the test.
- **Does decision-time surfacing change decisions?** This is the invalidation bet. RetractoBot's null bounds the post-hoc case only.
