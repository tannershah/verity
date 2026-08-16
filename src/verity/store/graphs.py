"""Claim-graph persistence.

`payload` is authoritative; `graph_premises` and `graph_groundings` are derived indexes
rebuilt on every save. Loading never reads the derived columns, so a bug in index
maintenance can degrade a query but cannot corrupt a graph.

Depth is one of those derived values. It is a property of a path, not of a premise — a
shared premise sits at different depths under different parents — so the graph computes
it by traversal and the column stores the shallowest occurrence, which is what a
"how deep did this branch go" query wants.
"""

from __future__ import annotations

import sqlite3

from verity.export import graph_from_json, graph_to_json
from verity.models.claim import ClaimGraph


def save_graph(conn: sqlite3.Connection, graph: ClaimGraph) -> str:
    payload = graph_to_json(graph)
    depth_of: dict[str, int] = {}
    for edge in graph.walk():
        depth_of[edge.premise_id] = min(edge.depth, depth_of.get(edge.premise_id, edge.depth))
    with conn:
        conn.execute(
            """
            INSERT INTO claim_graphs
                (id, root_claim_id, schema_version, run_id, created_at, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                root_claim_id = excluded.root_claim_id,
                schema_version = excluded.schema_version,
                run_id = excluded.run_id,
                created_at = excluded.created_at,
                payload = excluded.payload
            """,
            (
                graph.id,
                graph.root_claim.id,
                graph.schema_version,
                graph.metadata.run_id,
                graph.metadata.created_at.isoformat(),
                payload,
            ),
        )
        # Derived indexes: dropped and rebuilt so a removed premise cannot linger.
        conn.execute("DELETE FROM graph_premises WHERE graph_id = ?", (graph.id,))
        conn.execute("DELETE FROM graph_groundings WHERE graph_id = ?", (graph.id,))
        conn.executemany(
            """
            INSERT INTO graph_premises
                (graph_id, premise_id, depth, bound_key_type, bound_key_value,
                 evidence_state, termination_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    graph.id,
                    premise.id,
                    depth_of.get(premise.id, 0),
                    premise.bound_key.type.value if premise.bound_key else None,
                    premise.bound_key.value if premise.bound_key else None,
                    premise.evidence_state.value,
                    premise.termination_reason.value if premise.termination_reason else None,
                )
                for premise in graph.premises.values()
            ],
        )
        conn.executemany(
            "INSERT INTO graph_groundings (graph_id, premise_id, fact_id) VALUES (?, ?, ?)",
            [(graph.id, g.premise_id, g.fact_id) for g in graph.groundings],
        )
    return graph.id


def load_graph(conn: sqlite3.Connection, graph_id: str) -> ClaimGraph | None:
    row = conn.execute("SELECT payload FROM claim_graphs WHERE id = ?", (graph_id,)).fetchone()
    return graph_from_json(row["payload"]) if row else None


def list_graph_ids(conn: sqlite3.Connection, run_id: str | None = None) -> list[str]:
    if run_id is None:
        rows = conn.execute("SELECT id FROM claim_graphs ORDER BY created_at").fetchall()
    else:
        rows = conn.execute(
            "SELECT id FROM claim_graphs WHERE run_id = ? ORDER BY created_at", (run_id,)
        ).fetchall()
    return [row["id"] for row in rows]


def graphs_depending_on_fact(conn: sqlite3.Connection, fact_id: str) -> list[str]:
    """Graph ids with a premise grounded in `fact_id`.

    This is the query M8-T2's retraction propagation and M1-T3's dirty-subgraph
    recompute both stand on, which is why `graph_groundings(fact_id)` is indexed.
    """
    rows = conn.execute(
        "SELECT DISTINCT graph_id FROM graph_groundings WHERE fact_id = ?", (fact_id,)
    ).fetchall()
    return [row["graph_id"] for row in rows]
