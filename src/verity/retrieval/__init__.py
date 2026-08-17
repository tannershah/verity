"""M6 — evidence acquisition. Produces `WorkRecord`s now, `EvidenceBundle`s from T2.

**What M6-T1a owns.** The shared infrastructure every later client is built on — a
mandatory disk cache, header-driven rate limiting, a credit budget, retries, and a fixture
harness (`verity.retrieval.http`) — plus the first two clients, `openalex` and `crossref`,
and the local `retraction_watch` table reader. `binder` is a **labelled partial** of M6-T3
described below.

**Where the rules live.** Each module's docstring states the invariant it holds and why the
failure is silent without it; the four the whole layer rests on are listed in
`http/__init__.py`. The short version: a credential never enters a URL, a cache hit never
restamps the clock, a credential that missed its pool is a loud error, and a credentialed
404 is a reading while everything else that goes wrong is an exception.

**Nothing persists a `WorkRecord`.** The committed resolution artifact is a curation record
for the seed gate and stores `found` as a boolean, so M7-T1's retraction cut — which needs
`NOT_INDEXED` apart from `CLEAN` — has to run against client output rather than reconstruct
readings from that file, which will look sufficient and is not.

**A reading has three outcomes** (`record.ReadingOutcome`), and the third is the one a
boolean kept swallowing: `UNANSWERED` covers a source that could not be asked — OpenAlex
indexes works rather than NCT registry entries, Crossref holds no PMIDs — and a 404 whose
request went out without the credential the source expects. Neither is the source saying
the identifier is fictional, and both were reading as exactly that. Branch on `answered`
before treating `not found` as a negative.

**What this layer never does.** It reconciles nothing across sources — `10.3823/1654` is
retracted according to all three and identifies two different papers according to two of
them, and that is the finding rather than a defect to smooth over. It concludes no
retraction status: OpenAlex's `is_retracted` and Crossref's `update-to` types travel
verbatim, because the vocabulary includes `correction` and `new_version` and the cut
between them is M7-T1's. And it assigns no grounding-eligible confidence tier: a fetch
establishes that an identifier resolves, never that an attribution is supported.

**The binder is partial, and the label is data.** M6-T3 owns key attribution properly — the
top supporting evidence item above the stance floor. What ships here is narrower: an
M3-T1 `candidate_key` is promoted to `Premise.bound_key` **only when a registry resolves
it**, because blind promotion binds hallucinated identifiers. Retraction Watch is excluded
from that check on purpose: a curated index is not a registry, and a key present only in a
CSV would otherwise "resolve" with nothing confirming the work exists. Aliases are excluded
for the same reason grounding excludes them — widening the predicate would change a
pre-registered definition. `BindingReport` carries its own partial-ness so a grounding rate
derived from it cannot be quoted as evaluation.md §2's measurement in copy that forgot.
"""
