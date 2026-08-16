"""M6 — evidence acquisition. Produces `EvidenceBundle`s and binds `Premise.bound_key`.

**M6-T1a starts here, and it inherits two things from M5-T1.**

*A module to delete.* `verity.alethiology.verify_keys` is a provisional direct-`urllib`
path with no disk cache, no rate limiter and no retry policy, written because the seed
could not be gated without a resolution record and M5-T1 precedes M6-T1a in the ordering.
Its request and parsing shapes are verified against the live APIs and are the useful part
to carry over: the OpenAlex `works/https://doi.org/{doi}` and `works/pmid:{id}` forms, the
inverted-index abstract reconstruction, the `ids`-by-name alias read (parsing every value
instead reads a MAG id as a PMID and invents an alias to a real, unrelated record), the
Crossref JATS strip, and the `update-to` / `updated-by` capture. Once those live behind the
cached, rate-limited clients, delete the module — it exists on borrowed time and says so.

*A fixture to keep.* `seed/key_resolution.json` is a recorded reading of 19 identifiers
across OpenAlex, Crossref and the Retraction Watch table, committed so seed loading is
offline and reproducible. It is the fixture-recording harness's first fixture, and the
shape it should record: per source, `found` as a first-class answer, the text served, and
source-specific findings kept verbatim and unreconciled, because M7-T1 owns the cut that
turns them into a status.

**Then the binder, which is what the grounding path is still missing.** Nothing yet writes
`Premise.bound_key`, so `Alethiology.ground` is reachable only from tests and seeded keys.
M6-T3 owns key attribution properly (top supporting evidence item above the stance floor);
the labelled partial that unblocks the demo is narrower — promote an M3-T1 `candidate_key`
to `bound_key` **only when the key resolves live through the client built here**. Blind
promotion would bind hallucinated identifiers, which is the failure the whole seed gate
exists to prevent. Label it partial, and label any grounding rate it produces as not the
pre-registered measurement: "the decomposer emitted an identifier that resolves and is in
our seed" is a circular enough claim that it must not be quoted as evaluation.md §2's number.
"""
