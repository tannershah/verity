"""Determinism, and whether a run can actually be replayed from what it recorded.

`ids.py` states the contract: content-derived ids exist "so that a replayed run
reproduces the same graph byte-for-byte (M1-T2 deterministic replay)". That only holds if
the hash is stable across processes and sensitive to everything that changes an output —
and if the manifest records enough to rebuild the key in the first place.
"""

from __future__ import annotations

import subprocess
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import pytest

import verity
from verity.config import VerityConfig
from verity.export import to_json
from verity.ids import UnhashableInputError, content_hash, make_id, statement_hash
from verity.keys import ExternalKey, KeyType
from verity.models.claim import Claim
from verity.models.manifest import LLMSettings, RunManifest, StageRecord, Usage

_SRC = str(Path(verity.__file__).resolve().parents[1])


def _in_subprocess(body: str) -> str:
    code = f"import sys; sys.path.insert(0, {_SRC!r})\n{body}"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


# -- hashing --------------------------------------------------------------------------


def test_content_hash_is_stable_across_processes_for_serializable_input():
    """PYTHONHASHSEED randomises dict/str hashing per process; `sort_keys` is what makes
    this hold. A replay in a fresh process has to land on the same ids."""
    here = content_hash({"b": 2, "a": [1, {"c": 3}]})
    there = _in_subprocess(
        "from verity.ids import content_hash;print(content_hash({'a': [1, {'c': 3}], 'b': 2}))"
    )
    assert here == there


def test_ids_are_stable_across_processes():
    here = make_id("claim", "A misplaced decimal point made spinach famous.")
    there = _in_subprocess(
        "from verity.ids import make_id;"
        "print(make_id('claim', 'A misplaced decimal point made spinach famous.'))"
    )
    assert here == there


def test_content_hash_refuses_input_it_cannot_canonicalize():
    """A `default=str` fallback would turn anything unserializable into its `str()`. For
    an object without a custom `__repr__` that is `<object at 0x7f…>` — a memory address,
    so the same input would hash differently in every process. Silent, and it would only
    show up as a cache that never hits.

    Either raise, or canonicalize explicitly. Falling back to `str()` is the one option
    that cannot be made correct.
    """
    with pytest.raises(UnhashableInputError):
        content_hash({"unserializable": object()})


def test_content_hash_canonicalizes_the_types_the_model_actually_carries():
    """Every type reachable from a cache key has an explicit form, so adding one is a
    decision rather than a silent fallback."""
    key = ExternalKey(type=KeyType.DOI, value="10.3823/1654")
    digest = content_hash(
        {
            "when": datetime(2026, 1, 1, tzinfo=UTC),
            "where": Path("data/verity.db"),
            "what": KeyType.DOI,
            "which": key,
            "some": {"a", "b"},
        }
    )
    assert len(digest) == 64


def test_content_hash_distinguishes_a_datetime_from_its_string_form():
    """A cache key built from a timestamp must not collide with one built from its
    rendering — which is exactly what an untagged `str()` fallback would produce."""
    assert content_hash(datetime(2026, 1, 1, tzinfo=UTC)) != content_hash(
        "2026-01-01 00:00:00+00:00"
    )


def test_statement_dedup_survives_unicode_normalization():
    """M5-T1 dedups facts by statement hash. Retrieved text arrives in whatever form the
    API returns: OpenAlex and Crossref titles are not normalized, so the same statement
    can arrive as NFC from one source and NFD from another and land as two facts."""
    composed = unicodedata.normalize("NFC", "The caf\u00e9 study reported an effect.")
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed, "fixture must actually differ in normal form"
    assert statement_hash(composed) == statement_hash(decomposed)


# -- canonical export -----------------------------------------------------------------


def test_export_is_byte_stable_across_processes():
    """The id is left to derivation rather than pinned: PYTHONHASHSEED moves between
    processes, so a derived id reproducing across one is the property under test and a
    supplied one would assert nothing."""
    claim = Claim(text="x", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    here = to_json(claim)
    there = _in_subprocess(
        "from datetime import UTC, datetime\n"
        "from verity.models.claim import Claim\n"
        "from verity.export import to_json\n"
        "print(to_json(Claim(text='x',"
        " created_at=datetime(2026, 1, 1, tzinfo=UTC))))"
    )
    assert here == there


# -- config as the other half of a cache key -------------------------------------------


def test_every_config_section_changes_the_hash():
    """A cache key that ignores a knob replays a stale result after that knob moves. This
    walks the sections rather than naming fields, so a new section is covered on arrival.
    """
    baseline = VerityConfig()
    hashes = {baseline.config_hash()}

    mutations = (
        ("decomposition", "depth_budget", 2),
        ("verifier", "entailment_threshold", 0.99),
        ("retrieval", "top_k", 3),
        ("llm", "model", "claude-sonnet-5"),
        ("paths", "db_path", Path("/tmp/other.db")),
    )
    assert {m[0] for m in mutations} == set(VerityConfig.model_fields), (
        "a config section exists that this test does not vary"
    )

    for section, field, value in mutations:
        config = VerityConfig()
        setattr(getattr(config, section), field, value)
        digest = config.config_hash()
        assert digest not in hashes, f"{section}.{field} does not reach the config hash"
        hashes.add(digest)


def test_a_config_snapshot_rebuilds_the_same_config():
    """M1-T2 replays from the manifest, and the manifest stores the snapshot."""
    original = VerityConfig()
    assert VerityConfig(**original.snapshot()).config_hash() == original.config_hash()


# -- what the manifest would need to actually replay --------------------------------------


def test_a_stage_record_can_reconstruct_its_cache_key():
    """M1-T2's exit criterion is "re-running an unchanged claim is a cache hit end-to-end",
    and its stages are "composable steps with content-hash caching". Verifying that needs
    the record to say *what was hashed* — otherwise a replay can re-execute a run but
    cannot check that it reproduced it.

    This is the check itself: rebuild the key from the recorded input digest and config
    hash, and it has to come out the same.
    """
    config = VerityConfig()
    input_hash = content_hash({"claim": "A misplaced decimal point made spinach famous."})
    stage = StageRecord(
        name="decompose",
        started_at=datetime(2026, 8, 16, tzinfo=UTC),
        duration_ms=12.0,
        input_hash=input_hash,
        cache_key=content_hash(input_hash, config.config_hash()),
        output_hash=content_hash({"premises": ["a", "b", "c"]}),
        llm_settings=LLMSettings(
            model="claude-opus-5", effort="high", thinking=True, max_tokens=8000
        ),
    )

    assert stage.cache_key == content_hash(stage.input_hash, config.config_hash())


def test_a_stage_records_the_settings_it_ran_under_not_the_ones_configured():
    """A per-request override or a model fallback makes these differ from the config
    snapshot, and only the resolved ones explain the output."""
    stage = StageRecord(
        name="decompose",
        started_at=datetime(2026, 8, 16, tzinfo=UTC),
        duration_ms=12.0,
        llm_settings=LLMSettings(model="claude-opus-5", effort="low", thinking=True),
    )
    assert stage.llm_settings.effort == "low" != VerityConfig().llm.effort


def test_a_truncated_call_is_counted_rather_than_absorbed():
    """A response cut off at `max_tokens` can still validate, so a stage that made one
    has to say so — otherwise a short decomposition reads as a real measurement about the
    decomposer."""
    stage = StageRecord(
        name="decompose",
        started_at=datetime(2026, 8, 16, tzinfo=UTC),
        duration_ms=12.0,
        llm_calls=3,
        truncated_calls=1,
    )
    assert stage.truncated_calls == 1


def test_summing_usage_across_price_bases_does_not_invent_one():
    """The pricing basis exists so "a stale price is a recomputation, not lost data". A
    total summed across two tables belongs to neither, and labelling it with whichever
    came first is the one thing the field was added to prevent."""
    total = Usage(input_tokens=1, price_bases=("table-A",)) + Usage(
        input_tokens=1, price_bases=("table-B",)
    )
    assert total.price_bases == ("table-A", "table-B")
    assert total.price_basis is None
    assert total.has_mixed_price_basis


def test_summing_usage_under_one_table_keeps_its_basis():
    total = Usage(input_tokens=1, price_bases=("table-A",)) + Usage(
        input_tokens=2, price_bases=("table-A",)
    )
    assert total.price_basis == "table-A"
    assert not total.has_mixed_price_basis


def test_manifest_totals_are_derived_not_stored(tmp_path):
    """Totals recomputed from stages cannot drift from them."""
    manifest = RunManifest(
        run_id="run_x",
        stages=[
            StageRecord(
                name="decompose",
                started_at=datetime(2026, 8, 16, tzinfo=UTC),
                duration_ms=12.0,
                usage=Usage(
                    input_tokens=100, output_tokens=10, cost_usd=0.001, price_bases=("test",)
                ),
            ),
            StageRecord(
                name="verify",
                started_at=datetime(2026, 8, 16, tzinfo=UTC),
                duration_ms=8.0,
                usage=Usage(
                    input_tokens=50, output_tokens=5, cost_usd=0.0005, price_bases=("test",)
                ),
            ),
        ],
    )
    assert manifest.total_usage.input_tokens == 150
    assert manifest.total_usage.output_tokens == 15
    assert "total_usage" not in RunManifest.model_fields


def test_a_failed_stage_still_records_its_timing():
    """M1-T2's failure isolation yields "a partial graph, not a crash", so the manifest
    has to describe the stage that failed as well as the ones that did not."""
    stage = StageRecord(
        name="retrieve",
        started_at=datetime(2026, 8, 16, tzinfo=UTC),
        duration_ms=4.0,
        status="error",
        error="OpenAlex 429",
    )
    assert stage.duration_ms == 4.0
    assert stage.status == "error"
