"""Run-manifest persistence. M1-T2 replays a run from what is stored here."""

from __future__ import annotations

import sqlite3

from verity.export import from_json, to_json
from verity.models.manifest import RunManifest


def save_manifest(conn: sqlite3.Connection, manifest: RunManifest) -> str:
    with conn:
        conn.execute(
            """
            INSERT INTO run_manifests (run_id, started_at, finished_at, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                started_at = excluded.started_at,
                finished_at = excluded.finished_at,
                payload = excluded.payload
            """,
            (
                manifest.run_id,
                manifest.started_at.isoformat(),
                manifest.finished_at.isoformat() if manifest.finished_at else None,
                to_json(manifest),
            ),
        )
    return manifest.run_id


def load_manifest(conn: sqlite3.Connection, run_id: str) -> RunManifest | None:
    row = conn.execute(
        "SELECT payload FROM run_manifests WHERE run_id = ?", (run_id,)
    ).fetchone()
    return from_json(row["payload"], RunManifest) if row else None


def list_run_ids(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT run_id FROM run_manifests ORDER BY started_at").fetchall()
    return [row["run_id"] for row in rows]
