"""Tests for the Guard budget enforcement. No API keys required:
the hook is exercised directly against a seeded SQLite log.

Run: python -m pytest gateway/test_guard.py
"""

import asyncio
import datetime
import sqlite3

import pytest


def seed_request(db, model, cost_usd, ts=None):
    conn = sqlite3.connect(db)
    from sqlite_logger import SCHEMA

    conn.execute(SCHEMA)
    conn.execute(
        "INSERT INTO requests (ts, model, status, cost_usd) VALUES (?, ?, 'success', ?)",
        (ts or datetime.datetime.now().isoformat(), model, cost_usd),
    )
    conn.commit()
    conn.close()


def events(db):
    conn = sqlite3.connect(db)
    try:
        return conn.execute(
            "SELECT model, level, spent_usd, budget_usd FROM budget_events"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def run_hook(model):
    from guard import guard_instance

    return asyncio.run(
        guard_instance.async_pre_call_hook(None, None, {"model": model}, "completion")
    )


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "requests.db"
    budgets = tmp_path / "budgets.yaml"
    budgets.write_text(
        "warn_ratio: 0.8\ndaily_usd:\n  lead: 1.00\n", encoding="utf-8"
    )
    # GATEWAY_DB_PATH already points at this db: the autouse fixture in
    # conftest.py sets it to tmp_path / "requests.db" for every test.
    monkeypatch.setenv("GATEWAY_BUDGETS_PATH", str(budgets))
    return db


def test_under_budget_passes(env):
    seed_request(env, "lead", 0.10)
    data = run_hook("lead")
    assert data == {"model": "lead"}
    assert events(env) == []


def test_no_budget_model_passes(env):
    seed_request(env, "other", 999.0)
    run_hook("other")
    assert events(env) == []


def test_warn_at_80_percent_once_per_day(env):
    seed_request(env, "lead", 0.85)
    run_hook("lead")
    run_hook("lead")
    assert [e[:2] for e in events(env)] == [("lead", "warn")]


def test_block_at_100_percent(env):
    from fastapi import HTTPException

    seed_request(env, "lead", 1.20)
    with pytest.raises(HTTPException) as exc:
        run_hook("lead")
    assert exc.value.status_code == 429
    assert "budget exhausted" in exc.value.detail
    assert ("lead", "block") in [e[:2] for e in events(env)]


def test_yesterday_spend_does_not_count(env):
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat()
    seed_request(env, "lead", 5.00, ts=yesterday)
    run_hook("lead")
    assert events(env) == []
