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

    model_id: str = "lytang/MiniCheck-Flan-T5-Large"
    entailment_threshold: float = 0.50
    #: Leave-one-out drop above which a premise counts as load-bearing (M4-T2).
    ablation_delta: float = 0.10
    #: NLI checkpoints disagree on label order; verified at init rather than assumed.
    verify_label_order_at_init: bool = True


class RetrievalConfig(BaseModel):
    """M6. Every bound here is reported in the run manifest."""

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
