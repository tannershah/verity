"""Pre-registered evaluation thresholds.

These are the pass/fail lines from evaluation.md §2, fixed before the build started so
they cannot be moved to fit results. They are module constants — **not** configuration,
not environment variables, not settable at runtime. Changing one requires editing this
file and evaluation.md together, which leaves a diff and a rationale in git.

Operational knobs that *are* meant to be tuned (depth budget, beam caps, stance floor,
entailment gate) live in `verity.config`.
"""

from __future__ import annotations

from typing import Final

#: Fraction of branches that must ground in an alethiology fact by exact key,
#: within a depth-3 budget, on the 20-claim beachhead set. Judged at session 31
#: against a populated KB (build-plan.md §4).
GROUNDING_RATE_FLOOR: Final[float] = 0.50

#: Fraction of generated entailment steps that must pass human validity judgement
#: (N=30 trees, two annotators). Below this floor there is no public demo.
STEP_VALIDITY_FLOOR: Final[float] = 0.80

#: Maximum fraction of claims that may be wrongly marked retraction-dependent.
#: Above this ceiling the tool is net-harmful.
RETRACTION_FALSE_FLAG_CEILING: Final[float] = 0.05

#: Fraction of contested items that must localize to <=2 premises, at the stated
#: inter-annotator agreement. Roadmap, not v0 — the threshold travels with the deferral.
DISAGREEMENT_LOCALIZATION_FLOOR: Final[float] = 0.40
DISAGREEMENT_LOCALIZATION_KAPPA_FLOOR: Final[float] = 0.60
