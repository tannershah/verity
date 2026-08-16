"""M1-T1 exit criterion: round-trip a hand-built claim graph through store -> load -> JSON."""

from __future__ import annotations

from verity.export import graph_from_json, graph_to_json
from verity.models.claim import ClaimGraph
from verity.store import connect, schema_version
from verity.store.facts import (
    facts_by_key,
    facts_by_statement_hash,
    load_fact,
    save_fact,
)
from verity.store.graphs import (
    graphs_depending_on_fact,
    list_graph_ids,
    load_graph,
    save_graph,
)
from verity.store.manifests import list_run_ids, load_manifest, save_manifest


def test_graph_survives_store_load_json(tmp_path, hand_built_graph: ClaimGraph):
    conn = connect(tmp_path / "verity.db")
    assert schema_version(conn) == 1

    save_graph(conn, hand_built_graph)
    loaded = load_graph(conn, hand_built_graph.id)

    assert loaded is not None
    assert loaded == hand_built_graph
    assert graph_to_json(loaded) == graph_to_json(hand_built_graph)
    assert graph_from_json(graph_to_json(loaded)) == hand_built_graph
    conn.close()


def test_export_is_canonical(hand_built_graph: ClaimGraph):
    """Two exports of the same graph are byte-identical, so diffs are meaningful."""
    assert graph_to_json(hand_built_graph) == graph_to_json(hand_built_graph)


def test_graph_structure_survives(tmp_path, hand_built_graph: ClaimGraph):
    conn = connect(tmp_path / "verity.db")
    save_graph(conn, hand_built_graph)
    loaded = load_graph(conn, hand_built_graph.id)
    assert loaded is not None

    assert len(loaded.walk()) == len(hand_built_graph.walk())
    assert loaded.max_depth() == 2
    assert {p.id for p in loaded.leaves()} == {p.id for p in hand_built_graph.leaves()}
    root_step = loaded.step_concluding(loaded.root_claim.id)
    assert root_step is not None and root_step.score is not None
    assert root_step.score.is_uncalibrated
    conn.close()


def test_saving_twice_rebuilds_derived_indexes(tmp_path, hand_built_graph: ClaimGraph):
    """Derived columns are rebuilt, not appended, so a re-save cannot duplicate rows."""
    conn = connect(tmp_path / "verity.db")
    save_graph(conn, hand_built_graph)
    save_graph(conn, hand_built_graph)

    premise_rows = conn.execute("SELECT COUNT(*) FROM graph_premises").fetchone()[0]
    grounding_rows = conn.execute("SELECT COUNT(*) FROM graph_groundings").fetchone()[0]
    assert premise_rows == len(hand_built_graph.premises)
    assert grounding_rows == len(hand_built_graph.groundings)
    assert list_graph_ids(conn) == [hand_built_graph.id]
    conn.close()


def test_fact_roundtrip_and_exact_key_lookup(tmp_path, seeded_fact, hand_built_graph):
    conn = connect(tmp_path / "verity.db")
    save_fact(conn, seeded_fact)
    save_graph(conn, hand_built_graph)

    assert load_fact(conn, seeded_fact.id) == seeded_fact
    assert facts_by_key(conn, seeded_fact.key) == [seeded_fact]
    assert facts_by_statement_hash(conn, seeded_fact.statement_hash) == [seeded_fact]

    # The query M8-T2 retraction propagation and M1-T3 recompute both depend on.
    assert graphs_depending_on_fact(conn, seeded_fact.id) == [hand_built_graph.id]
    conn.close()


def test_manifest_roundtrip(tmp_path):
    from datetime import UTC, datetime

    from verity.models.common import CapRecord
    from verity.models.manifest import RunManifest, StageRecord, Usage

    manifest = RunManifest(
        run_id="run_test_0001",
        started_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
        code_version="abc1234",
        code_dirty=False,
        config={"decomposition": {"depth_budget": 3}},
        credentials_configured={"openalex_api_key": True, "ncbi_api_key": True},
        stages=[
            StageRecord(
                name="decompose",
                started_at=datetime(2026, 8, 16, 12, 0, tzinfo=UTC),
                duration_ms=1830.5,
                llm_calls=2,
                usage=Usage(input_tokens=1200, output_tokens=800, cost_usd=0.026),
                caps=[
                    CapRecord(name="max_premises_per_node", limit=7, applied=True, dropped=1)
                ],
            )
        ],
        graph_ids=["graph_x"],
    )

    conn = connect(tmp_path / "verity.db")
    save_manifest(conn, manifest)
    assert load_manifest(conn, manifest.run_id) == manifest
    assert list_run_ids(conn) == [manifest.run_id]

    assert manifest.total_usage.input_tokens == 1200
    assert [cap.name for cap in manifest.caps_applied] == ["max_premises_per_node"]
    conn.close()
