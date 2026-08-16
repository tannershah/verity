"""Alethiology persistence — storage only.

This module stores and retrieves facts and justifications. It does **not** decide what
may be stored: promotion policy, tier assignment, dedup rules, and the drift audit are
M5's, and the JTMS that maintains `status` is M8's. Exact-key lookup is the only
grounding path exposed, and no fuzzy or similarity lookup exists here by design
(design.md §4.1) — the M5-T3 similarity index is a separate, non-grounding layer.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from verity.export import from_json, to_json
from verity.keys import ExternalKey
from verity.models.fact import Fact, Justification


class StoreConflictError(RuntimeError):
    """A write violated a store constraint. Raised instead of a driver exception.

    A `sqlite3.IntegrityError` escaping the repository layer tells a caller which index
    complained, not what it did wrong. Since a fact's id is derived from (key, statement),
    the only way to reach one is a digest collision between two genuinely different facts.
    """


def save_fact(conn: sqlite3.Connection, fact: Fact) -> str:
    """Write one fact in its own transaction."""
    try:
        with conn:
            _write_fact(conn, fact)
    except sqlite3.IntegrityError as exc:  # pragma: no cover - digest collision only
        raise StoreConflictError(
            f"fact {fact.id} conflicts with a stored row on ({fact.key}, statement): {exc}"
        ) from exc
    return fact.id


def save_facts(conn: sqlite3.Connection, facts: Iterable[Fact]) -> list[str]:
    """Write many facts in **one** transaction — all of them land, or none do.

    A caller that has already decided the whole batch is writable needs the write to be
    as atomic as the decision was. Looping over `save_fact` commits per row, so a failure
    partway leaves a store that is neither the old one nor the new one; M5-T1's seed
    loader validates every row before writing any, and that guarantee would end at the
    first `INSERT` without this.
    """
    written = list(facts)
    try:
        with conn:
            for fact in written:
                _write_fact(conn, fact)
    except sqlite3.IntegrityError as exc:  # pragma: no cover - digest collision only
        raise StoreConflictError(f"batch write rolled back: {exc}") from exc
    return [fact.id for fact in written]


def _write_fact(conn: sqlite3.Connection, fact: Fact) -> None:
    """The statement itself. Transaction-free, so callers compose one around a batch."""
    conn.execute(
        """
        INSERT INTO facts
            (id, key_type, key_value, statement_hash, tier, status,
             revalidated_at, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            key_type = excluded.key_type,
            key_value = excluded.key_value,
            statement_hash = excluded.statement_hash,
            tier = excluded.tier,
            status = excluded.status,
            revalidated_at = excluded.revalidated_at,
            payload = excluded.payload
        """,
        (
            fact.id,
            fact.key.type.value,
            fact.key.value,
            fact.statement_hash,
            fact.tier.value,
            fact.status.value,
            fact.revalidated_at.isoformat() if fact.revalidated_at else None,
            to_json(fact),
        ),
    )


def load_fact(conn: sqlite3.Connection, fact_id: str) -> Fact | None:
    row = conn.execute("SELECT payload FROM facts WHERE id = ?", (fact_id,)).fetchone()
    return from_json(row["payload"], Fact) if row else None


def facts_by_key(conn: sqlite3.Connection, key: ExternalKey) -> list[Fact]:
    """Exact-key lookup. The only grounding path — never widen this predicate."""
    rows = conn.execute(
        "SELECT payload FROM facts WHERE key_type = ? AND key_value = ?",
        (key.type.value, key.value),
    ).fetchall()
    return [from_json(row["payload"], Fact) for row in rows]


def facts_by_statement_hash(conn: sqlite3.Connection, statement_hash: str) -> list[Fact]:
    rows = conn.execute(
        "SELECT payload FROM facts WHERE statement_hash = ?", (statement_hash,)
    ).fetchall()
    return [from_json(row["payload"], Fact) for row in rows]


def save_justification(conn: sqlite3.Connection, justification: Justification) -> str:
    with conn:
        conn.execute(
            """
            INSERT INTO justifications (id, consequent_fact_id, payload)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                consequent_fact_id = excluded.consequent_fact_id,
                payload = excluded.payload
            """,
            (justification.id, justification.consequent_fact_id, to_json(justification)),
        )
        conn.execute(
            "DELETE FROM justification_antecedents WHERE justification_id = ?",
            (justification.id,),
        )
        conn.executemany(
            "INSERT INTO justification_antecedents (justification_id, fact_id) VALUES (?, ?)",
            [(justification.id, fid) for fid in justification.antecedent_fact_ids],
        )
    return justification.id


def justifications_for(conn: sqlite3.Connection, fact_id: str) -> list[Justification]:
    """Justifications whose consequent is `fact_id`."""
    rows = conn.execute(
        "SELECT payload FROM justifications WHERE consequent_fact_id = ?", (fact_id,)
    ).fetchall()
    return [from_json(row["payload"], Justification) for row in rows]


class SqliteFacts:
    """A `FactLookup` backed by the store — what the render boundary reads.

    Grounding is non-monotonic (design.md §4.2), so a projection has to be able to ask
    the alethiology what a fact says *now* rather than trusting what a run recorded.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self, fact_id: str) -> Fact | None:
        return load_fact(self._conn, fact_id)

    def facts_for(self, key: ExternalKey) -> list[Fact]:
        return facts_by_key(self._conn, key)


def justifications_depending_on(conn: sqlite3.Connection, fact_id: str) -> list[Justification]:
    """Justifications with `fact_id` among their antecedents — the propagation edge."""
    rows = conn.execute(
        """
        SELECT j.payload FROM justifications j
        JOIN justification_antecedents a ON a.justification_id = j.id
        WHERE a.fact_id = ?
        """,
        (fact_id,),
    ).fetchall()
    return [from_json(row["payload"], Justification) for row in rows]
