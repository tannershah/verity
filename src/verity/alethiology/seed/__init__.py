"""Seeding the alethiology: the curated corpus, and the gate it has to pass.

design.md §6 names the standing risk — the alethiology "starts empty and is populated by
the system's own least-validated outputs," with NELL (`lit-025`) as the cautionary tale.
A hand-curated seed is a sharper version of the same problem: an agent asserting
propositions about works it may not have read, keyed to identifiers that may not exist, at
tiers that feed the numerator of a pre-registered measurement.

So a seed row is not a fact record. It is a claim about a work, and the loader is what
decides how much of that claim survives:

- **The key must resolve, to the work the curator named.** Checked against the committed
  `key_resolution.json`. An identifier absent from every registry aborts the load; one
  that resolves to a *different* title loads with its tier capped and the mismatch
  reported, because that case is real — Retraction Watch and both registries disagree
  about what `10.3823/1654` identifies while agreeing it is retracted.
- **Statements are attributive by construction.** `attributed_to` and `assertion` are
  separate fields and the statement is composed from them, so "Hamblin (1981) reports that
  X" is representable and a bare "X" is not. This matters because grounding is exact-key
  match and never reads a statement: an object-level fact would ground any premise sharing
  its identifier as `verified`, and a quote from an abstract cannot establish that a
  proposition is true — only that a work asserts it.
- **A grounding-eligible tier has to be earned from quoted text.** `verified-primary`
  requires a verbatim quote from the work's own abstract as the registry served it. A
  quote that matches nothing aborts the load; no quote at all caps the row at `inferred`.
  `corroborated-multi-secondary` is refused outright — the seed has no mechanism that
  could justify it, and both tiers feed the pre-registered rate.

**What the gate establishes, stated exactly.** That the identifier resolves; that it
resolves to the work the curator named; and that the curator quoted that work accurately
and substantially. That is the whole of it.

**What it does not establish is that the assertion is warranted.** A quote can be
verbatim, five words or more, unique in the abstract, and still sit under an assertion the
work contradicts — "comes from consuming a can of the stuff" is a real sentence in
Hamblin's abstract and would back an assertion that spinach is richly iron-bearing. The
gate makes a tier *falsifiable in three respects*; it does not read for meaning, and no
containment rule can. That link is human judgement, recorded in each row's `note` so a
reviewer can audit it, and the natural closer is M4's entailment scorer applied to
(quote → assertion) once one exists — an input to M5-T2, not a claim made here.

**Field ownership on re-load.** The seed owns `statement`, `key`, `tier`, provenance and
`created_at`. The store owns `status`, `revalidated_at`, `justification_ids`, and any
`evidence_quality` written after curation. Re-seeding never resurrects a fact the JTMS
flipped OUT — that is the same resurrection failure as an M8 recomputation over a
vacuously-satisfied justification, arriving through the loader instead.

**No justifications are written.** `Justification` models Doyle's IN-list only, so a
premise justification with no antecedents is vacuously satisfied and any M8-T1 status
recomputation would restore a demoted seed fact to IN forever. **Blocker on M8-T1:**
`Justification` needs an out-list (Doyle 1979's SL-justification) before a seeded fact can
carry one. Until then seed facts are IN with no justification, and M8-T1 decides what that
means rather than inheriting a decision made here.
"""

from verity.alethiology.seed._gate import (
    MIN_PRIMARY_QUOTE_WORDS,
    QuoteMatch,
    TierAssessment,
    assess,
    find_quote,
)
from verity.alethiology.seed._load import (
    load_seed,
    read_seed,
    report_to_json,
)
from verity.alethiology.seed._project import to_fact
from verity.alethiology.seed._report import SeedLoadReport, SeedRowOutcome
from verity.alethiology.seed._row import SeedError, SeedFact

__all__ = [
    "MIN_PRIMARY_QUOTE_WORDS",
    "QuoteMatch",
    "SeedError",
    "SeedFact",
    "SeedLoadReport",
    "SeedRowOutcome",
    "TierAssessment",
    "assess",
    "find_quote",
    "load_seed",
    "read_seed",
    "report_to_json",
    "to_fact",
]
