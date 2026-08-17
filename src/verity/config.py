"""Operational configuration.

These are knobs that are *meant* to be tuned: depth budget, beam caps, the entailment
gate, retrieval bounds, model selection, paths. Pre-registered evaluation thresholds are
deliberately **not** here — they live as frozen constants in `verity.thresholds`, so they
cannot be moved by an environment variable to fit a result.

Every value is overridable as `VERITY_<SECTION>__<FIELD>`, e.g.
`VERITY_DECOMPOSITION__DEPTH_BUDGET=2`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from verity.ids import content_hash


class DecompositionConfig(BaseModel):
    """M3. Caps are load-bearing for cost and are reported per run, never silent."""

    depth_budget: int = 3
    min_premises: int = 3
    max_premises: int = 7
    max_nodes_per_tree: int = 60
    #: Sampled candidate decompositions per step (M3-T3 verifier-in-the-loop).
    candidates_per_step: int = 1
    #: How the decomposer was told to write premises relative to their ancestors.
    #: `standalone` = the model sees the ancestor chain and must still write every premise
    #: so it stands without it. DnDScore (`lit-014`) shows the strategy moves downstream
    #: scores, so it travels in the config snapshot and the config hash rather than living
    #: unrecorded in prompt text. Distinct from `Claim.decontextualization`, which records
    #: what M2 did to the claim before the decomposer ever saw it.
    decontextualization: str = "standalone"


class VerifierConfig(BaseModel):
    """M4. The threshold is an inference-time gate, not an evaluation threshold."""

    #: M4-T1's champion, selected under the rule fixed before scoring — see
    #: `data/verifier/selection.json` for the numbers and `data/verifier/README.md` for
    #: what they do and do not establish. Changing this invalidates `entailment_threshold`
    #: below, which is scorer-relative.
    model_id: str = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
    #: **Scorer-relative, a placeholder, and — against the champion — inert.** Measured on
    #: the M4-T1 smoke set, this checkpoint is bimodal: clean steps land in 0.9971-0.9995
    #: and caught-corrupt steps in 0.0001-0.0033, with nothing between. Every step in every
    #: demo tree clears 0.50, and any value in (0.01, 0.99) would classify identically, so
    #: the knob has no operating range to tune. M3-T3 inherits a gate that never fires and
    #: should not read that as every step being sound. Its basis arrives with M4-T3's ROC;
    #: the smoke set is not permitted to fit it.
    entailment_threshold: float = 0.50
    #: Leave-one-out drop above which a premise counts as load-bearing (M4-T2).
    #: **Out of scale against the champion, and M4-T2 must reset it before pruning.** The
    #: champion's clean-case dynamic range is 0.0024, so most deltas sit near zero. Two
    #: measured points: dropping a load-bearing premise moved a step 0.9995 -> 0.4172
    #: (delta 0.58), dropping a non-load-bearing one moved it 0.9986 -> 0.9985
    #: (delta 0.0001). The gap is real but the floor between them is not 0.10 by anything
    #: measured — and M4-T2 prunes what falls below this and loops it back into M3, so a
    #: floor set too high deletes load-bearing premises. This is what M4-T2's ~20
    #: hand-labelled sanity check exists to set.
    ablation_delta: float = 0.10
    #: NLI checkpoints disagree on label order; verified at init rather than assumed.
    #: Turning this off is recorded in every score the scorer produces, not just here.
    verify_label_order_at_init: bool = True
    #: Override for the checkpoint's commit. `None` — the default — uses the per-checkpoint
    #: pin recorded in `verity.verifier.registry`, which is the commit M4-T1 measured each
    #: candidate at. It cannot be pinned here instead: one field cannot name the right
    #: commit for two different checkpoints, and the bake-off loads both.
    revision: str | None = None
    #: CPU by default, deliberately. MPS and CUDA produce different floats for the same
    #: input, and a score that depends on which device happened to be free is not the
    #: replayable number M1-T2 rests on.
    device: str = "cpu"


class RetrievalConfig(BaseModel):
    """M6. Every bound here is reported in the run manifest.

    Cache mode is deliberately absent: it is a per-run argument recorded in the fetch log,
    not configuration. Putting it here would fold it into `config_hash()` and make a mode
    flip invalidate every M1-T2 stage cache, when where the bytes came from is not part of
    what a stage computed.
    """

    top_k: int = 10
    per_source_cap: int = 20
    max_retries: int = 3
    request_timeout_s: float = 30.0
    #: Disk cache is mandatory, not an optimization: OpenAlex costs credits and
    #: Crossref/S2 rate limits are tight.
    cache_dir: Path = Path(".cache/http")
    #: Minimum stance score for an evidence item to bind its key to a premise (M6-T3).
    stance_floor: float = 0.60


class LLMConfig(BaseModel):
    """Claim-side LLM calls. Provider-agnostic adapter, Claude API default."""

    provider: str = "anthropic"
    model: str = "claude-opus-5"
    max_tokens: int = 8000
    effort: str = "high"  # low | medium | high | xhigh | max
    thinking: bool = True


class PathsConfig(BaseModel):
    db_path: Path = Path("data/verity.db")
    runs_dir: Path = Path("data/runs")
    #: Tracked in git, not under `data/`: the curated seed and the key-resolution record
    #: it is checked against are source the demo's reproducibility depends on, while
    #: `data/` holds the derived and the bulky (the database, the Retraction Watch table).
    alethiology_seed: Path = Path("seed/alethiology.jsonl")
    key_resolution: Path = Path("seed/key_resolution.json")


class VerityConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VERITY_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    decomposition: DecompositionConfig = Field(default_factory=DecompositionConfig)
    verifier: VerifierConfig = Field(default_factory=VerifierConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)

    def snapshot(self) -> dict[str, Any]:
        """Serializable, secret-free view for the run manifest.

        Safe by construction rather than by filtering: no secret is ever a field on this
        object. `tests/test_secrets_redaction.py` asserts the property holds.
        """
        return self.model_dump(mode="json")

    def config_hash(self) -> str:
        """Stable hash of the snapshot, for cache keys and replay checks (M1-T2)."""
        return content_hash(self.snapshot())


def load_config() -> VerityConfig:
    return VerityConfig()
