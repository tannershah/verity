"""Which backend drives which checkpoint, and which commit of it.

`VerifierConfig.model_id` names the checkpoint the pipeline scores with. Without a registry
that name has nowhere to go: a caller picks a backend class, the class loads whatever it
was compiled to prefer, and `model_id` becomes a string that moves `config_hash()` — and
therefore invalidates every M1-T2 stage cache — while changing nothing about what actually
ran. The stored `Score.scorer` would then name one checkpoint and the run manifest's config
snapshot another, with no error anywhere.

**The revision pin lives here, per checkpoint, and not on the config.** A single
`config.revision` cannot pin two checkpoints at once — setting it to the champion's commit
would make the bake-off ask the model hub for that commit of MiniCheck, which does not
exist. So each entry carries the commit it was selected at, `config.revision` becomes an
override for all of them, and a checkpoint whose weights move under its branch is caught by
`ScorerSpec.revision` disagreeing with the pin rather than by nobody noticing.

The commits below are the ones recorded in `data/verifier/selection.json`; the demo's
scores are reproducible against them and against nothing else.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from verity.config import VerifierConfig
    from verity.verifier.base import StepScorer

NLI_CHECKPOINT = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
MINICHECK_CHECKPOINT = "lytang/MiniCheck-Flan-T5-Large"


class Backend(NamedTuple):
    """A checkpoint's driver and the commit M4-T1 measured it at."""

    module: str
    class_name: str
    revision: str


#: Import is deferred so this module stays torch-free and importable anywhere.
BACKENDS: dict[str, Backend] = {
    NLI_CHECKPOINT: Backend(
        "verity.verifier.nli",
        "NliScorer",
        "b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7",
    ),
    MINICHECK_CHECKPOINT: Backend(
        "verity.verifier.minicheck",
        "MiniCheckScorer",
        "96eafd01cee2d16cf81aaa2fb226b14f422a37b3",
    ),
}


class UnknownCheckpointError(ValueError):
    """No backend drives the requested checkpoint."""


def _entry(checkpoint: str) -> Backend:
    try:
        return BACKENDS[checkpoint]
    except KeyError:
        raise UnknownCheckpointError(
            f"no backend drives {checkpoint!r}; known checkpoints are "
            f"{sorted(BACKENDS)}. A scorer that silently loaded a different checkpoint "
            "would put one model's name in the config snapshot and another's in every "
            "score it produced"
        ) from None


def backend_for(checkpoint: str) -> type:
    entry = _entry(checkpoint)
    return getattr(import_module(entry.module), entry.class_name)


def pinned_revision(checkpoint: str) -> str:
    """The commit this checkpoint was selected at."""
    return _entry(checkpoint).revision


def resolve_checkpoint(config: VerifierConfig, backend: type, explicit: str | None) -> str:
    """The checkpoint a backend should load, checked against what it can actually drive.

    Precedence is explicit argument, then `config.model_id`. There is no third fallback:
    a backend quietly loading its own preferred checkpoint when configuration named a
    different one is the failure this whole module exists to remove.
    """
    checkpoint = explicit or config.model_id
    driver = backend_for(checkpoint)
    if driver is not backend:
        raise UnknownCheckpointError(
            f"{backend.__name__} cannot drive {checkpoint!r}, which is handled by "
            f"{driver.__name__}. Build it through `build_scorer(config)`, or pass an "
            "explicit checkpoint this backend supports"
        )
    return checkpoint


def resolve_revision(config: VerifierConfig, checkpoint: str) -> str:
    """The commit to load: the config override if set, otherwise the recorded pin."""
    return config.revision or pinned_revision(checkpoint)


def build_scorer(config: VerifierConfig, *, checkpoint: str | None = None) -> StepScorer:
    """The scorer `config.model_id` names."""
    target = checkpoint or config.model_id
    return backend_for(target)(config, checkpoint=target)
