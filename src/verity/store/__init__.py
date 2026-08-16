"""SQLite persistence. `payload` JSON is authoritative; columns are derived indexes."""

from verity.store.db import connect, open_db, schema_version

__all__ = ["connect", "open_db", "schema_version"]
