"""SQLite request logger for the LiteLLM gateway.

Every request passing through the gateway is recorded in a SQLite log.
The schema already contains what the Ledger (Phase 1 step 3) needs,
including raw prompt text for the context-repetition ratio.

The database path is taken from the GATEWAY_DB_PATH environment variable,
defaulting to requests.db next to this file.
"""

import json
import os
import sqlite3
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    model TEXT,
    provider_model TEXT,
    status TEXT NOT NULL,
    latency_ms REAL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cost_usd REAL,
    prompt TEXT,
    response TEXT,
    error TEXT
);
"""


def db_path() -> Path:
    return Path(os.environ.get("GATEWAY_DB_PATH", Path(__file__).parent / "requests.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute(SCHEMA)
    return conn


def _insert(row: dict) -> None:
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    with _connect() as conn:
        conn.execute(
            f"INSERT INTO requests ({columns}) VALUES ({placeholders})",
            list(row.values()),
        )


def _base_row(kwargs, start_time, end_time) -> dict:
    messages = kwargs.get("messages")
    litellm_params = kwargs.get("litellm_params") or {}
    metadata = litellm_params.get("metadata") or {}
    # Through the proxy, kwargs["model"] is the resolved provider model;
    # the gateway alias the client asked for is metadata["model_group"].
    return {
        "ts": start_time.isoformat() if start_time else None,
        "model": metadata.get("model_group") or kwargs.get("model"),
        "provider_model": kwargs.get("model"),
        "latency_ms": (end_time - start_time).total_seconds() * 1000
        if start_time and end_time
        else None,
        "prompt": json.dumps(messages, ensure_ascii=False) if messages else None,
    }


def _success_row(kwargs, response_obj, start_time, end_time) -> dict:
    row = _base_row(kwargs, start_time, end_time)
    usage = getattr(response_obj, "usage", None)
    choices = getattr(response_obj, "choices", None)
    row.update(
        {
            "status": "success",
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
            "cost_usd": kwargs.get("response_cost"),
            "response": choices[0].message.content if choices else None,
        }
    )
    return row


def _failure_row(kwargs, start_time, end_time) -> dict:
    row = _base_row(kwargs, start_time, end_time)
    row.update(
        {
            "status": "failure",
            "error": str(kwargs.get("exception") or ""),
        }
    )
    return row


class SQLiteLogger(CustomLogger):
    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        _insert(_success_row(kwargs, response_obj, start_time, end_time))

    def log_failure_event(self, kwargs, response_obj, start_time, end_time):
        _insert(_failure_row(kwargs, start_time, end_time))

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        _insert(_success_row(kwargs, response_obj, start_time, end_time))

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        _insert(_failure_row(kwargs, start_time, end_time))


logger_instance = SQLiteLogger()
