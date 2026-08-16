# The seed alethiology

The curated facts the two demo claims stand on, and the record they were checked against.

| File | What it is |
|---|---|
| `alethiology.jsonl` | One curated claim per line: an attribution, an assertion, a verbatim quote, and the curator's argument that the one follows from the other |
| `key_resolution.json` | What OpenAlex, Crossref, and the Retraction Watch table returned for every key in the seed, at one recorded time |

```
python -m verity.alethiology verify-keys --from-seed   # refresh the resolution record
python -m verity.alethiology seed --check              # gate the corpus, write nothing
python -m verity.alethiology seed                      # gate it and load it
```

Loading is offline and deterministic: the gate reads `key_resolution.json`, never the
network, so a clean checkout reproduces the same store without the gitignored 71,799-row
Retraction Watch table.

---

## Why a seed row is not a fact

A hand-curated corpus is an agent asserting propositions about works it may not have read,
keyed to identifiers that may not exist, at tiers that feed the numerator of a
pre-registered measurement ([evaluation.md](../docs/evaluation.md) §2). Two of those
assertions can be checked mechanically, and the loader checks them:

- **The key resolves, to the work the curator named.** An identifier absent from every
  source aborts the load. One that resolves to a *different* title loads with its tier
  capped and the conflict named in the report.

  Titles are compared by **equality**, never containment. Containment has no substantiality
  floor, so `expected_title: "e"` would match every source, promote the row, and erase the
  identity mismatch from the report — the demo's centerpiece finding, lost to a typo. Where
  a registry genuinely spells a title differently — OpenAlex prefixes retracted works with
  `RETRACTED ARTICLE:` — the curator declares that spelling in `expected_title_variants`,
  so a variant is a recorded decision rather than a hole. A variant must *contain* the
  title the row declared, so it can only widen that claim, and the load report names which
  declared title each source matched — auditing a variant does not mean opening this file.
- **The quote is verbatim, and it is a quotation.** `verified-primary` requires a quote
  that appears in the work's own abstract as a registry served it, compared under
  whitespace-collapse and case-fold (`normalize_text`) because OpenAlex serves an inverted
  index rather than prose. A quote found in no source aborts the load; no quote at all caps
  the row at `inferred`.

  Containment alone is not evidence — `"a"` occurs 84 times in Hamblin's abstract, so a
  gate that asked only "does this string appear" would let any assertion ride a common word
  into the top tier. A primary-verification quote must therefore be **at least five words**
  and **occur exactly once** in the text it matched. Both conditions are measured against
  this corpus: every quote that earns the top tier is 5–23 words and unique, while the
  degenerate cases are single words occurring 3–84 times. Shorter quotes still load —
  an author name is two words and is the whole datum for a Retraction Watch row — they just
  cap at `single-secondary`.

The quote travels onto the fact as `supporting_quote`, not only in this file. A tier is a
claim about how well an attribution is supported, and the words it rests on belong on the
record a reader is inspecting.

**Statements are attributive** — "Hamblin (1981) reports that …", composed by the loader
from separate `attributed_to` and `assertion` fields, so a bare object-level claim is not
representable. Grounding is exact-key match and never compares statements, so an
object-level fact would ground any premise sharing its identifier as `verified`. A quote
from an abstract establishes what a work *says*, never that the proposition is true, and
the statement says exactly that much.

**What the gate establishes, exactly:** that the identifier resolves, that it resolves to
the work the curator named, and that the curator quoted that work accurately and
substantially.

**What it does not establish is that the assertion is warranted.** A quote can be verbatim,
substantial, and unique and still sit under an assertion the work contradicts — "comes from
consuming a can of the stuff" is a real sentence in Hamblin's abstract and would back the
claim that spinach is richly iron-bearing. No containment rule can close that; it is human
judgement, recorded in each row's `note` for audit. The natural closer is M4's entailment
scorer applied to (quote → assertion) once one exists, which is an input to M5-T2 rather
than a claim made here. Read a tier as "this attribution is checkable in three respects,"
not as "this proposition was verified."

`corroborated-multi-secondary` is refused outright. Both it and `verified-primary` are
grounding-eligible, and nothing in a seed establishes corroboration — that is M5-T2's
promotion policy, and it needs an assertion-level identity the fact record does not yet
carry.

---

## What is in it

33 rows across two scopes — 19 for the spinach-iron decimal myth, 14 for the
chocolate-weight-loss hoax. 27 are grounding-eligible; 6 are capped at `single-secondary`.
30 are keyed by DOI, 3 by PMID.

[build-plan.md](../docs/build-plan.md) §2 sizes this seed at ~50–100 facts. Two claims do
not support that many quote-backed rows, and padding a fact store toward a number is the
drift [design.md](../docs/design.md) §6 names NELL for. The count above is what the
material supports, reported rather than targeted.

**The NCT path is unexercised.** No registered trial is load-bearing for either demo
claim, and seeding one to make the three key types look covered would be filler. DOI and
PMID are live; NCT is written and untested against real data.

### The spinach trail

Hamblin's 1981 BMJ note (`10.1136/bmj.283.6307.1671`) is the origin of the decimal-point
story. Rekdal's 2014 *Academic urban legends* (`10.1177/0306312714535679`) is the paper
that treats it as a worked example of a rumor reproducing inside the literature. **The seed
never asserts the decimal error as fact** — both rows are attributive, Rekdal's preserves
his own hedge ("appears to have"), and a decomposition of the root claim is supposed to
surface the tension rather than resolve it. The remaining rows carry the bioavailability
premises (oxalate binding, absorption inhibitors) and the citation-propagation premises the
claim rests on.

Each of these two works is seeded once by DOI and once by PMID, which is also the alias
case: one work, two identifiers, and exact-key match sees two keys.

### The chocolate trail

Retraction Watch record 17524 records `10.3823/1654` as *Chocolate with high Cocoa content
as a weight-loss accelerator*, retracted 2015-06-10 for falsification and forged
authorship. Both OpenAlex and Crossref return `is_retracted: true` and a
`retraction`-typed `update-to` for that DOI — **and both return a different paper's title
and abstract under it**, *The comparison of resilience and spirituality in addicted and
non-addicted women*.

All three sources agree the identifier is retracted. Two of three disagree with the third
about what it identifies. That is seeded as it stands: the Retraction Watch rows are capped
at `single-secondary` and ground nothing, and one further row records the registries' side
of the conflict as its own attributive fact. Both are true statements about what a source
says. Reconciling them would be inventing an answer none of the three sources gives.

A second retracted work (`pmid:31844967`, a hesperidin trial) is seeded so the retraction
path is not demonstrated on a single DOI whose metadata is contested.

The rest of the scope is the surrounding evidence a decomposition needs: why a small
flexible study produces a positive result, why a venue publishes it, and — the symmetric
obligation in seed form — the real cocoa literature, which is mixed rather than empty.

---

## What the seed deliberately does not write

**No JTMS justifications.** `Justification` models Doyle's IN-list only, so a premise
justification with no antecedents is vacuously satisfied, and a status recomputation would
restore a demoted seed fact to IN forever. Seeded facts are IN with no justification.
**This is a blocker on M8-T1:** the type needs an out-list (Doyle 1979's SL-justification)
before a seeded fact can carry one.

**No retraction verdict.** The loader records what the Retraction Watch table said as a
`RetractionCheck` and leaves `retraction` at `unknown`. The cut between `retracted` and
`retraction-flagged-unconfirmed` is M7-T1's, and the two API readings stay in
`key_resolution.json` as fixture data so the retraction path produces them live and can
disagree with what was seeded.

Only `RetractionNature: Retraction` is read as a retraction. The table also carries
expressions of concern, corrections and reinstatements — 5,512 of its 71,799 rows — and
those are recorded as `not-indexed` rather than `clean`, because `clean` asserts a source
looked and found nothing. The raw nature travels in the check's `detail`. **Input to
M7-T1:** the vocabulary needs a fourth finding for "indexed, with a notice that is not a
retraction"; introducing it here would set the terms of a cut that tier owns.

**A seeded retraction reading is write-once.** `evidence_quality` is store-owned, so a
re-load will not refresh it on a row that already exists — that is the same rule that stops
a re-seed from clobbering M7-T1's live findings, and the cost is that a corrected reading
needs the row dropped or the store rebuilt. Rebuilding is cheap: delete the database and
re-seed.

**Nothing the store owns.** Re-loading rewrites `statement`, `key`, `tier`, provenance and
`created_at`. It never touches `status`, `revalidated_at`, `justification_ids`, or an
`evidence_quality` written after curation — so a re-seed cannot resurrect a fact the JTMS
flipped OUT.
