"""Guard: deterministic budget enforcement in the request path.

ARCHITECTURE.md, "Guard"; D-0027. No LLM involved.

Why not LiteLLM's native budgets (D-0030 evaluation, 2026-07-03):
they require Postgres (and Redis for cross-worker counters), both
explicitly deferred by ARCHITECTURE.md until the MVP stack fails,
and they have no per-model 80%-warning semantics. This hook reuses
the SQLite request log the gateway already writes.

Budgets are configuration, not code: budgets.yaml next to this file,
overridable via GATEWAY_BUDGETS_PATH.

Semantics (per gateway alias, per local calendar day):
- spend >= warn_ratio * budget: a 'warn' row in budget_events
  (once per model per day) and a proxy log line;
- spend >= budget: request refused with HTTP 429, a 'block' row
  in budget_events.
"""

import datetime
import os
import sqlite3
from pathlib import Path

import yaml
from litellm.integrations.custom_logger import CustomLogger

from sqlite_logger import db_path

EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS budget_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    model TEXT NOT NULL,
    level TEXT NOT NULL,
    spent_usd REAL NOT NULL,
    budget_usd REAL NOT NULL
);
"""


def budgets_path() -> Path:
    return Path(os.environ.get("GATEWAY_BUDGETS_PATH", Path(__file__).parent / "budgets.yaml"))


def load_budgets() -> dict:
    path = budgets_path()
    if not path.exists():
        return {"warn_ratio": 0.8, "daily_usd": {}}
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    config.setdefault("warn_ratio", 0.8)
    config.setdefault("daily_usd", {})
    return config


def daily_budget(config: dict, model: str):
    budgets = config["daily_usd"]
    return budgets.get(model, budgets.get("default"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute(EVENTS_SCHEMA)
    return conn


def spent_today(conn: sqlite3.Connection, model: str, today: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) FROM requests"
        " WHERE model = ? AND substr(ts, 1, 10) = ?",
        (model, today),
    ).fetchone()
    return row[0]


def _record_event(conn, model, level, spent, budget, now):
    conn.execute(
        "INSERT INTO budget_events (ts, model, level, spent_usd, budget_usd)"
        " VALUES (?, ?, ?, ?, ?)",
        (now, model, level, spent, budget),
    )
    conn.commit()


def _warned_today(conn, model, today) -> bool:
    row = conn.execute(
        "SELECT 1 FROM budget_events"
        " WHERE model = ? AND level = 'warn' AND substr(ts, 1, 10) = ? LIMIT 1",
        (model, today),
    ).fetchone()
    return row is not None


def check_budget(model: str) -> None:
    """Raise fastapi.HTTPException(429) when the daily budget is exhausted."""
    config = load_budgets()
    budget = daily_budget(config, model)
    if budget is None:
        return

    now = datetime.datetime.now()
    today = now.date().isoformat()
    conn = _connect()
    try:
        # The requests table may not exist before the first logged request.
        try:
            spent = spent_today(conn, model, today)
        except sqlite3.OperationalError:
            return

        if spent >= budget:
            _record_event(conn, model, "block", spent, budget, now.isoformat())
            from fastapi import HTTPException

            raise HTTPException(
                status_code=429,
                detail=(
                    f"Guard: daily budget exhausted for model '{model}':"
                    f" spent ${spent:.4f} of ${budget:.2f}. Refusing request."
                ),
            )

        if spent >= config["warn_ratio"] * budget and not _warned_today(conn, model, today):
            _record_event(conn, model, "warn", spent, budget, now.isoformat())
            print(
                f"Guard WARNING: model '{model}' at ${spent:.4f}"
                f" of ${budget:.2f} daily budget"
            )
    finally:
        conn.close()


class Guard(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        check_budget(data.get("model", ""))
        return data


guard_instance = Guard()
