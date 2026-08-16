"""Config is tunable; pre-registered thresholds are not.

evaluation.md §2 fixes the thresholds before the build starts "so they can't be moved to
fit results". Keeping them out of the settings object is what makes that true in code:
changing one requires a commit, not an environment variable.
"""

from __future__ import annotations

import pytest

from verity import thresholds
from verity.config import VerityConfig, load_config


def test_operational_knobs_are_env_overridable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VERITY_DECOMPOSITION__DEPTH_BUDGET", "2")
    monkeypatch.setenv("VERITY_RETRIEVAL__TOP_K", "25")

    config = load_config()

    assert config.decomposition.depth_budget == 2
    assert config.retrieval.top_k == 25


def test_thresholds_are_not_reachable_through_config(monkeypatch: pytest.MonkeyPatch):
    """Setting a threshold-shaped environment variable changes nothing."""
    monkeypatch.setenv("VERITY_GROUNDING_RATE_FLOOR", "0.10")
    monkeypatch.setenv("VERITY_STEP_VALIDITY_FLOOR", "0.10")
    monkeypatch.setenv("VERITY_RETRACTION_FALSE_FLAG_CEILING", "0.99")

    config = load_config()

    assert not hasattr(config, "grounding_rate_floor")
    threshold_names = {name.lower() for name in dir(thresholds) if name.isupper()}
    snapshot = config.snapshot()
    assert not set(snapshot) & threshold_names
    for section in snapshot.values():
        assert not set(section) & threshold_names

    assert thresholds.GROUNDING_RATE_FLOOR == 0.50
    assert thresholds.STEP_VALIDITY_FLOOR == 0.80
    assert thresholds.RETRACTION_FALSE_FLAG_CEILING == 0.05


def test_config_hash_is_stable_and_sensitive():
    a = VerityConfig()
    b = VerityConfig()
    assert a.config_hash() == b.config_hash()

    c = VerityConfig()
    c.decomposition.depth_budget = 4
    assert c.config_hash() != a.config_hash()


def test_default_depth_budget_matches_the_evaluated_setting():
    """Grounding rate is pre-registered at a depth-3 budget; the default must match."""
    assert VerityConfig().decomposition.depth_budget == 3
    assert VerityConfig().decomposition.min_premises == 3
    assert VerityConfig().decomposition.max_premises == 7
