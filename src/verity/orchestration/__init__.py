"""M1-T2 — the orchestrator. Composable stages, content-hash caching, replay, isolation.

Two cache layers with different jobs, and the split is the design:

- **The cassette** (`verity.llm.cassette`) records what the *provider said*. A hit replays
  the answer and re-executes every line downstream of it.
- **The stage cache** (`pipeline`) records what a *stage concluded*. A hit skips the work.

Because the cassette holds the money, the stage cache can afford to key on the whole source
tree — the conservative choice re-runs deterministic code for free rather than serving a
result built by rules that no longer exist.

Two of the four stages decline the stage cache for reasons that are design decisions:
`ground` because grounding is non-monotonic (design.md §4.2), and `bind` because its cache
is the HTTP transport's, which owns semantics a stage cache cannot reproduce.
"""

from verity.orchestration.pipeline import RunOutcome, run_claim, store_outcome
from verity.orchestration.replay import ReplayError, ReplayReport, replay_run

__all__ = [
    "ReplayError",
    "ReplayReport",
    "RunOutcome",
    "replay_run",
    "run_claim",
    "store_outcome",
]
