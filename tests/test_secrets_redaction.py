"""Secrets must not reach any artifact a human or a repo ever sees.

The property being tested is structural, not filtered: no secret is a field on a config,
a graph, or a manifest, so there is nothing to accidentally forget to strip. These tests
assert that by injecting recognisable values and scanning everything we serialize.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from verity.config import VerityConfig
from verity.export import to_json
from verity.models.manifest import RunManifest
from verity.secrets import Secrets

CANARIES = {
    "OPENALEX_API_KEY": "canary-openalex-8f3a",
    "NCBI_API_KEY": "canary-ncbi-2b71",
    "CROSSREF_MAILTO": "canary-mailto@example.invalid",
    "SEMANTIC_SCHOLAR_API_KEY": "canary-s2-4d90",
    "ANTHROPIC_API_KEY": "canary-anthropic-c105",
}


@pytest.fixture
def canary_secrets(monkeypatch: pytest.MonkeyPatch) -> Secrets:
    for name, value in CANARIES.items():
        monkeypatch.setenv(name, value)
    return Secrets()


def test_secrets_repr_never_prints_values(canary_secrets: Secrets):
    text = f"{canary_secrets!r} {canary_secrets!s}"
    for value in CANARIES.values():
        assert value not in text
    assert "openalex_api_key" in text  # names are fine; values are not


def test_secret_str_hides_value_on_direct_access(canary_secrets: Secrets):
    assert str(canary_secrets.openalex_api_key) != CANARIES["OPENALEX_API_KEY"]
    # Revealing is explicit, greppable, and only at the point of use.
    assert canary_secrets.reveal("openalex_api_key") == CANARIES["OPENALEX_API_KEY"]


def test_configured_map_is_booleans_only(canary_secrets: Secrets):
    configured = canary_secrets.configured()
    assert configured["openalex_api_key"] is True
    assert all(isinstance(v, bool) for v in configured.values())
    assert not set(CANARIES.values()) & set(map(str, configured.values()))


def test_config_snapshot_carries_no_secret(canary_secrets: Secrets):
    snapshot = json.dumps(VerityConfig().snapshot())
    for value in CANARIES.values():
        assert value not in snapshot


def test_manifest_serialization_carries_no_secret(canary_secrets: Secrets):
    manifest = RunManifest(
        run_id="run_secret_check",
        config=VerityConfig().snapshot(),
        credentials_configured=canary_secrets.configured(),
    )
    serialized = to_json(manifest)
    for value in CANARIES.values():
        assert value not in serialized
    assert '"openalex_api_key": true' in serialized


def test_real_env_values_do_not_appear_in_artifacts():
    """Belt and braces: scan with the developer's actual credentials, if present."""
    live = Secrets()
    values = [v for v in (live.reveal(name) for name in live.field_names()) if v]
    if not values:
        pytest.skip("no credentials configured in this environment")

    artifacts = to_json(
        RunManifest(
            run_id="run_live_check",
            config=VerityConfig().snapshot(),
            credentials_configured=live.configured(),
        )
    )
    for value in values:
        assert value not in artifacts


def test_env_file_is_gitignored():
    gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
    assert ".env" in gitignore.read_text(encoding="utf-8").split()
