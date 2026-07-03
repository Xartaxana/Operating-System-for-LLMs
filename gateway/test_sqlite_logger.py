"""Tests for the SQLite request logger. No API keys required:
litellm's mock_response short-circuits the network call while still
firing the logging callbacks.

Run: python -m pytest gateway/test_sqlite_logger.py
"""

import json
import os
import sqlite3
import time

import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    path = tmp_path / "requests.db"
    monkeypatch.setenv("GATEWAY_DB_PATH", str(path))
    return path


def wait_for_row(path, status, timeout=10):
    """Sync callbacks run in a worker thread; poll until the row lands."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists():
            rows = sqlite3.connect(path).execute(
                "SELECT * FROM requests WHERE status = ?", (status,)
            ).fetchall()
            if rows:
                return rows
        time.sleep(0.2)
    raise AssertionError(f"no '{status}' row appeared in {path} within {timeout}s")


def test_success_is_logged(db):
    import litellm
    from sqlite_logger import logger_instance

    litellm.callbacks = [logger_instance]
    litellm.completion(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "ping"}],
        mock_response="pong",
    )

    rows = wait_for_row(db, "success")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM requests WHERE status = 'success'").fetchone()

    assert row["model"] == "gpt-3.5-turbo"
    assert row["response"] == "pong"
    assert json.loads(row["prompt"]) == [{"role": "user", "content": "ping"}]
    assert row["total_tokens"] is not None
    assert row["latency_ms"] is not None


def test_failure_is_logged(db):
    import litellm
    from sqlite_logger import logger_instance

    litellm.callbacks = [logger_instance]
    with pytest.raises(Exception):
        litellm.completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "ping"}],
            mock_response="litellm.InternalServerError",
        )

    rows = wait_for_row(db, "failure")
    assert any("InternalServerError" in (r[-1] or "") for r in rows)
