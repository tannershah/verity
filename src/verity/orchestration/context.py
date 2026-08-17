"""What a run carries: its clock, its resources, and the graph it may be replacing.

**Resources are lazy and shared.** The scorer is a ~2GB checkpoint and the HTTP client
holds a rate limiter with per-endpoint state; building either per stage would make M1-T3's
batch runner load the checkpoint once per claim. Lazy, because a run whose stages all hit
the cache should need neither — nor an API key, which is what lets a recorded run replay
from a clean checkout.

**One clock reading per run.** `now` is taken once and every timestamp that reaches the
graph derives from it, including `Claim.created_at` — which is why the orchestrator builds
the claim rather than accepting one. It contributes nothing to the claim's id and is
serialized into the graph, so a claim built a few milliseconds earlier produces a graph
whose every id matches and whose bytes do not. The committed demo graph shows exactly that
gap, 11ms wide, between `root_claim.created_at` and everything else.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from verity.alethiology.service import Alethiology
from verity.cache import BlobCache
from verity.config import VerityConfig
from verity.ids import content_hash
from verity.llm.base import LLMAdapter
from verity.llm.cassette import CassetteAdapter, CassetteMode
from verity.models.claim import Claim, ClaimGraph
from verity.orchestration.fingerprint import source_digest
from verity.retrieval.http import CacheMode, HttpClient, build_client

if TYPE_CHECKING:
    from verity.verifier.base import StepScorer


def graph_fingerprint(graph: ClaimGraph) -> str:
    """A digest of a graph's content, with the run stamps masked out.

    `metadata.run_id` and `metadata.created_at` identify the *execution*, not the content,
    and masking them is required rather than tidy: on a cache hit `assemble_graph` writes
    this run's clock into `created_at` while the cached steps keep the previous run's, so
    an unmasked comparison always differs and the "stamp only when the content changed"
    rule degenerates into stamping always.
    """
    payload: dict[str, Any] = graph.model_dump(mode="json")
    metadata = dict(payload.get("metadata") or {})
    metadata.pop("run_id", None)
    metadata.pop("created_at", None)
    payload["metadata"] = metadata
    return content_hash(payload)


@dataclass
class RunContext:
    """Everything a stage may reach, built once per run."""

    claim: Claim
    config: VerityConfig
    conn: sqlite3.Connection
    now: datetime
    cache: BlobCache
    cache_mode: CacheMode = CacheMode.LIVE
    #: The graph this run may be replacing, read once before any stage runs. Used three
    #: ways: to carry an unchanged grounding's timestamp forward, to decide whether the
    #: run stamps the graph, and to warn when a skipped stage would drop stored output.
    stored_graph: ClaimGraph | None = None
    #: Whether the orchestrator may serve cacheable stages from the stage cache.
    use_stage_cache: bool = True
    adapter_factory: Any = None
    #: Injectable so a batch shares one loaded checkpoint (M1-T3) and so a test can score
    #: without the `verifier` extra. `None` builds the one `config.verifier` names.
    scorer_factory: Any = None
    cassette_mode: CassetteMode = CassetteMode.LIVE

    _adapter: CassetteAdapter | None = field(default=None, init=False, repr=False)
    _scorer: StepScorer | None = field(default=None, init=False, repr=False)
    _client: HttpClient | None = field(default=None, init=False, repr=False)
    _service: Alethiology | None = field(default=None, init=False, repr=False)

    # -- derived identity ------------------------------------------------------------

    @property
    def config_hash(self) -> str:
        return self.config.config_hash()

    @property
    def source_digest(self) -> str:
        return source_digest()

    @property
    def expected_scorer_id(self) -> str:
        from verity.verifier.registry import expected_scorer_id

        return expected_scorer_id(self.config.verifier)

    # -- resources -------------------------------------------------------------------

    @property
    def adapter(self) -> LLMAdapter:
        """The cassette, wrapping a provider client that is built only on a miss."""
        if self._adapter is None:
            self._adapter = CassetteAdapter(
                self.adapter_factory,
                config=self.config.llm,
                cache=self.cache,
                mode=self.cassette_mode,
            )
        return self._adapter

    @property
    def cassette(self) -> CassetteAdapter | None:
        """The cassette, if a stage has caused one to be built. Never builds one itself.

        The accounting pass asks after every stage, including ones that make no LLM call;
        constructing an adapter to discover it was not used would defeat the laziness that
        lets a fully-cached run need no provider.
        """
        return self._adapter

    @property
    def scorer(self) -> StepScorer:
        if self._scorer is None:
            if self.scorer_factory is not None:
                self._scorer = self.scorer_factory()
            else:
                from verity.verifier.registry import build_scorer

                self._scorer = build_scorer(self.config.verifier)
        return self._scorer

    @property
    def http_client(self) -> HttpClient:
        if self._client is None:
            self._client = build_client(config=self.config.retrieval, mode=self.cache_mode)
        return self._client

    @property
    def service(self) -> Alethiology:
        if self._service is None:
            # Passed explicitly. `Alethiology.open` falls back to `load_config()`, which
            # would read the environment rather than the configuration this run recorded —
            # and every key derived from that snapshot would then describe a config that
            # did not run.
            self._service = Alethiology.open(
                self.conn, resolution_path=self.config.paths.key_resolution
            )
        return self._service
