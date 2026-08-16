"""SQLite connection, schema bootstrap, and migration.

Raw `sqlite3` behind a thin repository layer rather than an ORM: pydantic already owns
(de)serialization, the queries are few and explicit, and an ORM would add a second
mapping to keep in sync with the schema.

**The version is compared, not stamped.** The alethiology outlives every run — M5-T2
writes a promotion queue into it, M8 flips statuses in it, M5-T3 re-validates it — so its
schema will change while data is already in it. Re-stamping `user_version` on open would
destroy the only evidence a migration is owed, so a database from a newer build is refused
and one from an older build is migrated forward.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

#: Bumped when `schema.sql` changes shape. Read back with `PRAGMA user_version`.
USER_VERSION = 1

#: Forward migrations, keyed by the version they upgrade *from*. Each entry is applied in
#: order and the version is stamped after it. Adding a table means adding its `CREATE` to
#: `schema.sql` (for fresh databases), an entry here (for existing ones), and bumping
#: `USER_VERSION` — the three together are what make an existing alethiology survive.
MIGRATIONS: dict[int, str] = {}


class SchemaError(RuntimeError):
    """Base class for schema-version problems."""


class SchemaTooNewError(SchemaError):
    """The database was written by a build with a later schema than this one."""


class MissingMigrationError(SchemaError):
    """No migration exists to move the database forward to the current schema."""


def _migrate(conn: sqlite3.Connection, from_version: int) -> None:
    for version in range(from_version, USER_VERSION):
        statements = MIGRATIONS.get(version)
        if statements is None:
            raise MissingMigrationError(
                f"no migration from schema version {version} to {version + 1}"
            )
        conn.executescript(statements)
        conn.execute(f"PRAGMA user_version = {version + 1}")


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (creating if needed) a Verity database at the current schema version."""
    path = Path(db_path)
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, detect_types=0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    current = int(conn.execute("PRAGMA user_version").fetchone()[0])
    if current > USER_VERSION:
        conn.close()
        raise SchemaTooNewError(
            f"{path} was written at schema version {current}; this build knows "
            f"{USER_VERSION}. Upgrade rather than opening it — writing to it here would "
            f"re-stamp the version and lose the record that a migration is owed."
        )
    if current == 0:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.execute(f"PRAGMA user_version = {USER_VERSION}")
    elif current < USER_VERSION:
        _migrate(conn, current)

    conn.commit()
    return conn


@contextmanager
def open_db(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])
