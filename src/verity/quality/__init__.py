"""M7 — evidence quality. **A labelled partial: only the retraction layer exists.**

M7-T1's three-source retraction check, and nothing else from the module. Study design and
registered N (T2), citation intent and the per-premise quality summary (T3), and text-mined
extraction (T4) are unbuilt; `EvidenceQuality` carries their fields and this tier writes
none of them.

Three modules, mirroring `verity.alethiology`, because the same three jobs recur and mixing
them is how a policy comes to depend on a transport:

- `retraction` decides — pure, no I/O, one source's reading to one finding and the findings
  to a status.
- `service` gathers — the two registry clients and the local table, resolved and read.
- `apply` writes — assessments onto stored facts, preserving everything the store owns.

**What this tier does not do**, stated here because a reader looking for it will look here
first. It does not propagate: a retracted fact is not flipped `OUT`, because that is M8-T2's
JTMS and `Justification` still needs an out-list before a seeded fact can carry one. It does
not persist a disagreement log; a disagreement is observable on the record and printed by
the command, and the curator queue is the full tier's. And it reaches evidence items only in
principle — `EvidenceBundle`s arrive with M6-T2, so today the only thing carrying quality
metadata is a `Fact`.
"""

from verity.quality.retraction import (
    PARTIAL_BASIS,
    RetractionAssessment,
    decide,
)
from verity.quality.service import assess_key, assess_keys

__all__ = [
    "PARTIAL_BASIS",
    "RetractionAssessment",
    "assess_key",
    "assess_keys",
    "decide",
]
