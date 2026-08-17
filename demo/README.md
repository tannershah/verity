# Demo captures

Terminal output from the committed demo, recorded 2026-08-17. Every command shown
runs offline on a fresh clone — no API key, no network; the root README's
quickstart gives the commands themselves.

- `00-store-build.txt` — building the store: `verity.alethiology seed` loads 33
  curated facts against committed registry records, then `verity.quality apply`
  checks every identifier against all three retraction sources and writes the
  result onto the facts — six come back flagged.
- `01-retraction-check.txt` — the three-source verdict on the retracted
  chocolate-hoax paper (`doi:10.3823/1654`): Retraction Watch, Crossref, and
  OpenAlex all say retracted, and the tool prints the shared-provenance caveat
  beside the agreement — two of the three readings trace to the same primary
  record, and "three sources agree" is not allowed to pretend otherwise.
- `02-spinach-render.txt` — the committed spinach graph: premise tree, one
  entailment score per step, ablation deltas, and a termination reason on every
  leaf.
- `03-replay.txt` — `verity replay` re-deriving the committed run from the
  committed store with no API key present: every stage digest reproduced.
- `04-chocolate-attempt.txt` — an honest miss, kept deliberately: two live runs
  of the chocolate-hoax claim in which the decomposer volunteered no identifier,
  so no premise grounds. This is the run-to-run grounding variance the root
  README describes, shown rather than summarized.
