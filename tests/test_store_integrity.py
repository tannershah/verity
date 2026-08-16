"""Persistence edge cases the happy-path round-trip does not reach.

The alethiology is the one store that outlives a run — it is written by M5-T2's promotion
queue, mutated by M8's JTMS, and re-validated by M5-T3 — so its write path has to be
idempotent, its constraints have to agree with each other, and its schema has to be able
to change without losing what is in it.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from verity.export import graph_to_json
from verity.keys import ExternalKey, KeyType
from verity.models.common import ConfidenceTier, Provenance, TmsStatus
from verity.models.fact import Fact, Justification
from verity.store.db import (
    USER_VERSION,
    MissingMigrationError,
    SchemaTooNewError,
    connect,
    schema_version,
)
from verity.store.facts import (
    StoreConflictError,
    facts_by_key,
    justifications_depending_on,
    justifications_for,
    load_fact,
    save_fact,
    save_justification,
)
from verity.store.graphs import load_graph, save_graph

KEY = ExternalKey(type=KeyType.DOI, value="10.1080/00071668108416780")
NEAR_MISS = ExternalKey(type=KeyType.DOI, value="10.1080/00071668108416781")
ACCESSED = datetime(2026, 8, 16, 12, 34, 56, 789123, tzinfo=UTC)
PROVENANCE = Provenance(
    source="openalex", accessed_at=ACCESSED, confidence_tier=ConfidenceTier.VERIFIED_PRIMARY
)


def _fact(**overrides) -> Fact:
    defaults = dict(
        statement="Published iron content for raw spinach is approximately 2.7 mg per 100 g.",
        key=KEY,
        tier=ConfidenceTier.VERIFIED_PRIMARY,
        provenance=[PROVENANCE],
    )
    return Fact(**{**defaults, **overrides})


# -- the write path has to be idempotent --------------------------------------------


def test_saving_the_same_fact_twice_is_an_upsert(tmp_path):
    conn = connect(tmp_path / "upsert.db")
    fact = _fact()
    save_fact(conn, fact)
    fact.status = TmsStatus.OUT
    save_fact(conn, fact)

    assert conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"] == 1
    assert load_fact(conn, fact.id).status is TmsStatus.OUT


def test_a_fact_id_that_disagrees_with_its_content_is_refused(tmp_path):
    """`facts` carries two constraints — `PRIMARY KEY(id)` and
    `UNIQUE(key_type, key_value, statement_hash)` — and they can only ever agree if the id
    is the pair. A caller inventing one (M5-T2's promotion queue, a seed JSONL) would
    satisfy the first and violate the second, arriving as a raw `sqlite3.IntegrityError`
    out of the repository layer.

    Resolved at the type: an id is checked against its own derivation, so the two
    constraints cannot disagree and the store never sees the conflict.
    """
    conn = connect(tmp_path / "conflict.db")

    with pytest.raises(ValidationError, match="does not match the id derived"):
        _fact(id="fact_invented")

    # The same content twice is one fact, whether or not the id was written out.
    first = _fact()
    save_fact(conn, first)
    save_fact(conn, _fact(id=first.id, tier=ConfidenceTier.INFERRED))
    assert conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"] == 1
    assert load_fact(conn, first.id).tier is ConfidenceTier.INFERRED
    conn.close()


def test_a_stored_fact_loads_back_with_its_id_intact(tmp_path):
    """The reason the check is equality rather than refusing supplied ids outright:
    every load supplies one."""
    conn = connect(tmp_path / "reload.db")
    fact = _fact()
    save_fact(conn, fact)
    assert load_fact(conn, fact.id) == fact
    conn.close()


def test_a_constraint_violation_surfaces_as_a_domain_error(tmp_path):
    """With ids derived from (key, statement) the remaining route to this is a digest
    collision, which cannot be constructed through the model — so the colliding row is
    written by hand. What matters is that the repository layer does not leak `sqlite3`
    upward when it happens."""
    conn = connect(tmp_path / "domain.db")
    fact = _fact()
    with conn:
        conn.execute(
            "INSERT INTO facts (id, key_type, key_value, statement_hash, tier, status,"
            " revalidated_at, payload) VALUES (?, ?, ?, ?, ?, ?, NULL, '{}')",
            (
                "fact_adifferentid00",
                fact.key.type.value,
                fact.key.value,
                fact.statement_hash,
                fact.tier.value,
                fact.status.value,
            ),
        )

    with pytest.raises(StoreConflictError):
        save_fact(conn, fact)
    conn.close()


def test_a_missing_row_reads_as_none(tmp_path):
    conn = connect(tmp_path / "missing.db")
    assert load_fact(conn, "fact_nonexistent") is None
    assert load_graph(conn, "graph_nonexistent") is None


# -- the JTMS write path M8 inherits ---------------------------------------------------


def test_justifications_round_trip_with_their_antecedent_index(tmp_path):
    """M8-T2's propagation walks from a retracted fact to everything resting on it, which
    is the `justification_antecedents` index. The tables and the write path are M1-T1's;
    the policy that decides what may become a justification is M8's."""
    conn = connect(tmp_path / "jtms.db")
    supported = _fact(statement="The effect was replicated.")
    antecedent = _fact()
    save_fact(conn, supported)
    save_fact(conn, antecedent)

    justification = Justification(
        consequent_fact_id=supported.id, antecedent_fact_ids=[antecedent.id]
    )
    save_justification(conn, justification)

    assert justifications_for(conn, supported.id) == [justification]
    assert justifications_depending_on(conn, antecedent.id) == [justification]
    assert justifications_depending_on(conn, supported.id) == []
    conn.close()


def test_re_saving_a_justification_rebuilds_its_antecedents(tmp_path):
    """Antecedents are a derived index like every other, so a re-save replaces them
    rather than accumulating — an antecedent removed by a later pass has to disappear."""
    conn = connect(tmp_path / "jtms-resave.db")
    justification = Justification(
        consequent_fact_id="fact_consequent0", antecedent_fact_ids=["fact_a", "fact_b"]
    )
    save_justification(conn, justification)
    save_justification(conn, justification)

    rows = conn.execute("SELECT COUNT(*) AS n FROM justification_antecedents").fetchone()
    assert rows["n"] == 2
    conn.close()


# -- exact-key lookup, and only exact ------------------------------------------------


def test_key_lookup_is_exact_and_reaches_through_canonicalization(tmp_path):
    """The grounding predicate is exact-key match (design.md §4.1). Canonicalization must
    reach the store — the same DOI written as a URL has to find the row — and nothing
    weaker than equality may."""
    conn = connect(tmp_path / "keys.db")
    fact = _fact()
    save_fact(conn, fact)

    for spelling in (
        "10.1080/00071668108416780",
        "https://doi.org/10.1080/00071668108416780",
        "DOI: 10.1080/00071668108416780",
        "10.1080/00071668108416780 ",
    ):
        assert [f.id for f in facts_by_key(conn, ExternalKey.parse(spelling))] == [fact.id]

    assert facts_by_key(conn, NEAR_MISS) == []


# -- the payload is authoritative -----------------------------------------------------


def test_a_corrupt_derived_index_cannot_corrupt_a_graph(tmp_path, hand_built_graph):
    """`store/graphs.py` states the property: derived columns are an index, `payload` is
    the record. A bug in index maintenance may degrade a query; it must not change what
    loads back."""
    conn = connect(tmp_path / "derived.db")
    save_graph(conn, hand_built_graph)

    with conn:
        conn.execute("UPDATE graph_premises SET depth = 999, evidence_state = 'verified'")

    assert graph_to_json(load_graph(conn, hand_built_graph.id)) == graph_to_json(
        hand_built_graph
    )


def test_a_stored_graph_re_exports_byte_identically(tmp_path, hand_built_graph):
    conn = connect(tmp_path / "canonical.db")
    save_graph(conn, hand_built_graph)
    once = graph_to_json(load_graph(conn, hand_built_graph.id))
    save_graph(conn, load_graph(conn, hand_built_graph.id))
    assert graph_to_json(load_graph(conn, hand_built_graph.id)) == once


# -- types survive the round trip exactly ---------------------------------------------


def test_datetimes_survive_sqlite_with_timezone_and_microseconds(tmp_path):
    """SQLite has no datetime type, so everything goes through ISO strings. M5-T3's TTL
    re-validation compares these, and a dropped timezone or truncated microsecond makes a
    stale fact look fresh."""
    conn = connect(tmp_path / "time.db")
    fact = _fact(revalidated_at=ACCESSED)
    save_fact(conn, fact)
    restored = load_fact(conn, fact.id)

    assert restored.revalidated_at == ACCESSED
    assert restored.revalidated_at.tzinfo is not None
    assert restored.revalidated_at.microsecond == 789123
    assert restored.provenance[0].accessed_at == ACCESSED
    assert restored == fact


def test_enums_and_keys_come_back_as_types_not_strings(tmp_path):
    """`tier == "verified-primary"` is true for a `StrEnum` either way, so a string
    leaking through is invisible until something calls a member on it."""
    conn = connect(tmp_path / "types.db")
    fact = _fact()
    save_fact(conn, fact)
    restored = load_fact(conn, fact.id)

    assert isinstance(restored.tier, ConfidenceTier)
    assert isinstance(restored.status, TmsStatus)
    assert isinstance(restored.key, ExternalKey)
    assert restored.key.matches(KEY)


# -- schema evolution -------------------------------------------------------------------


def test_opening_a_database_from_a_newer_schema_is_refused(tmp_path):
    """Stamping `USER_VERSION` on every open would silently re-stamp a database written by
    a later build — worse than not checking, because it destroys the only evidence that a
    migration is owed.

    The alethiology persists across the whole build — M5-T2 adds a promotion audit log and
    M8 adds status-flip events, both of which need columns that do not exist yet — so the
    first migration is a certainty, not a hypothetical.
    """
    path = tmp_path / "future.db"
    connect(path).close()

    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {USER_VERSION + 1}")
    raw.commit()
    raw.close()

    with pytest.raises(SchemaTooNewError):
        connect(path)

    # Refused, not rewritten: the version it was written at is still readable.
    raw = sqlite3.connect(path)
    assert raw.execute("PRAGMA user_version").fetchone()[0] == USER_VERSION + 1
    raw.close()


def test_a_database_from_an_older_schema_is_migrated_forward(tmp_path, monkeypatch):
    """The other half. A stored alethiology has to survive a schema change, so an older
    database is brought forward rather than refused — and a version with no migration
    behind it is an error rather than a silent restamp.
    """
    from verity.store import db as db_module

    path = tmp_path / "older.db"
    connect(path).close()

    monkeypatch.setattr(db_module, "USER_VERSION", USER_VERSION + 1)
    with pytest.raises(MissingMigrationError):
        connect(path)

    monkeypatch.setattr(
        db_module,
        "MIGRATIONS",
        {USER_VERSION: "ALTER TABLE facts ADD COLUMN promoted_by TEXT;"},
    )
    conn = connect(path)
    assert schema_version(conn) == USER_VERSION + 1
    assert "promoted_by" in {row["name"] for row in conn.execute("PRAGMA table_info(facts)")}
    conn.close()


def test_reopening_an_up_to_date_database_is_a_no_op(tmp_path):
    conn = connect(tmp_path / "stable.db")
    save_fact(conn, _fact())
    conn.close()

    conn = connect(tmp_path / "stable.db")
    assert schema_version(conn) == USER_VERSION
    assert conn.execute("SELECT COUNT(*) AS n FROM facts").fetchone()["n"] == 1
    conn.close()


def test_schema_version_is_readable(tmp_path):
    assert schema_version(connect(tmp_path / "version.db")) == USER_VERSION


# -- foreign keys are on ----------------------------------------------------------------


def test_foreign_keys_are_enforced(tmp_path):
    """SQLite defaults `foreign_keys` to OFF, which would make every dangling-reference
    test pass vacuously. `connect()` turns it on — this keeps it on."""
    conn = connect(tmp_path / "fk.db")
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute(
            "INSERT INTO graph_premises (graph_id, premise_id, depth, evidence_state)"
            " VALUES ('graph_does_not_exist', 'prem_x', 1, 'unverified')"
        )
