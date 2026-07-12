"""DoD witness for t-085: live migration check on a copy of gateway/requests.db.

Copies the real requests.db to a temp file, runs _connect() on it
(triggers category column migration if absent), then verifies:
- PRAGMA table_info shows category column
- row count is unchanged

Run: python -m pytest gateway/test_live_migration_check.py -v -s

Named with 'test_live_migration_check' so it runs inside the normal
pytest glob. Uses tmp_path provided by pytest, not a raw tempfile,
so the copy is guaranteed to be cleaned up.
"""

import shutil
import sqlite3
from pathlib import Path


def test_live_migration_adds_category_column_to_real_db_copy(tmp_path, monkeypatch):
    """Copy gateway/requests.db and run the migration; verify the category
    column appears and no existing rows are lost."""
    src = Path(__file__).parent / "requests.db"
    if not src.exists():
        import pytest
        pytest.skip("gateway/requests.db not found (skip in CI without real DB)")

    dest = tmp_path / "requests_copy.db"
    shutil.copy2(src, dest)

    conn_before = sqlite3.connect(dest)
    count_before = conn_before.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    # Collect column names before migration
    cols_before = {row[1] for row in conn_before.execute("PRAGMA table_info(requests)")}
    conn_before.close()

    # Point GATEWAY_DB_PATH at the copy so _connect() migrates it
    monkeypatch.setenv("GATEWAY_DB_PATH", str(dest))

    import importlib
    import sys
    # Force sqlite_logger to re-read the env var
    if "sqlite_logger" in sys.modules:
        importlib.reload(sys.modules["sqlite_logger"])
    import sqlite_logger
    importlib.reload(sqlite_logger)

    conn = sqlite_logger._connect()
    cols_after = conn.execute("PRAGMA table_info(requests)").fetchall()
    count_after = conn.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
    conn.close()

    col_names = {c[1] for c in cols_after}

    print("\nPRAGMA table_info(requests) after migration:")
    for c in cols_after:
        print(" ", c)
    print(f"Rows before: {count_before}  Rows after: {count_after}")
    print(f"category column present: {'category' in col_names}")

    assert "category" in col_names, "category column missing after migration"
    assert count_before == count_after, "row count changed — data lost!"
