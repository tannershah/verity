"""M5 — fact-store policy: what may be stored, and what may ground a premise.

Storage lives in `verity.store.facts`; this package owns the rules over it. Three pieces:

- `service.Alethiology` — the read side. Exact-key lookup plus the grounding decision, and
  a `FactLookup` the render boundary can consume. No text query exists here, and the type
  signatures are the enforcement: every lookup takes an `ExternalKey`, never a `str`.
- `grounding` — the grounding predicate (unchanged from evaluation.md §2) and, more to the
  point, the reason a premise did *not* ground, including the by-design partition
  build-plan.md §4's supplementary rate needs.
- `seed` / `resolution` / `verify_keys` — the curated corpus and the gate it passes: keys
  resolved against the registries and recorded, statements attributive by construction, a
  grounding-eligible tier earned from a verbatim quote or not granted.

**Blocker this tier hands forward to M8-T1.** No JTMS justifications are written for
seeded facts. `Justification` models Doyle's IN-list only, so a premise justification with
no antecedents is vacuously satisfied, and a status recomputation would restore a demoted
seed fact to IN forever — the resurrection failure, arriving through the JTMS. Seeded facts
are IN with no justification until `Justification` carries an out-list (Doyle 1979's
SL-justification); M8-T1 rules on what that state means rather than inheriting a decision
made here.

**Not built here.** Promotion, tier assignment from retrieved evidence, the approval queue
and the drift audit are M5-T2. The similarity index is M5-T3 and is flagged non-grounding.
Corroboration counting is deliberately absent: under attributive statements two works never
share a statement hash, so corroboration has to be computed over the object-level assertion
and over distinct *works* rather than distinct keys — an identity `Fact` does not yet carry.
M5-T2 needs it before it can promote to `corroborated-multi-secondary`.
"""

from verity.alethiology.grounding import (
    GroundingAttempt,
    GroundingReason,
    attempt_grounding,
)
from verity.alethiology.resolution import KeyResolution, ResolutionArtifact, SourceReading
from verity.alethiology.seed import (
    SeedError,
    SeedFact,
    SeedLoadReport,
    load_seed,
    read_seed,
)
from verity.alethiology.service import Alethiology

__all__ = [
    "Alethiology",
    "GroundingAttempt",
    "GroundingReason",
    "KeyResolution",
    "ResolutionArtifact",
    "SeedError",
    "SeedFact",
    "SeedLoadReport",
    "SourceReading",
    "attempt_grounding",
    "load_seed",
    "read_seed",
]
