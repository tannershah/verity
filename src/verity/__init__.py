"""Verity — an epistemic transparency engine.

Public surface for downstream modules. Everything a pipeline stage needs to read or
write state is re-exported here so tiers do not reach into module internals.
"""

from verity.config import VerityConfig, load_config
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim, ClaimGraph, EntailmentStep, Grounding, Premise
from verity.models.common import (
    Calibration,
    CapRecord,
    ConfidenceTier,
    EvidenceState,
    Extraction,
    LabeledField,
    PremiseType,
    Provenance,
    RetractionStatus,
    Score,
    Stance,
    TerminationReason,
    TmsStatus,
)
from verity.models.evidence import EvidenceBundle, EvidenceItem, EvidenceQuality
from verity.models.fact import Fact, Justification
from verity.models.manifest import RunManifest, StageRecord, Usage
from verity.models.render import RenderPayload, to_render_payload
from verity.secrets import Secrets

__all__ = [
    "CapRecord",
    "Calibration",
    "Claim",
    "ClaimGraph",
    "ConfidenceTier",
    "EntailmentStep",
    "EvidenceBundle",
    "EvidenceItem",
    "EvidenceQuality",
    "EvidenceState",
    "ExternalKey",
    "Extraction",
    "Fact",
    "Grounding",
    "Justification",
    "KeyType",
    "LabeledField",
    "Premise",
    "PremiseType",
    "Provenance",
    "RenderPayload",
    "RetractionStatus",
    "RunManifest",
    "Score",
    "Secrets",
    "StageRecord",
    "Stance",
    "TerminationReason",
    "TmsStatus",
    "Usage",
    "VerityConfig",
    "load_config",
    "to_render_payload",
]
