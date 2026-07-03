"""Tests for the Ledger digest. Run: python -m pytest gateway/test_metrics.py"""

import datetime
import sqlite3

import pytest

from metrics import categorize, common_prefix_len, daily_digest, repetition_by_model
from sqlite_logger import SCHEMA
from guard import EVENTS_SCHEMA


@pytest.fixture()
def conn(tmp_path):
    conn = sqlite3.connect(tmp_path / "requests.db")
    conn.execute(SCHEMA)
    conn.execute(EVENTS_SCHEMA)
    return conn


def seed(conn, model, prompt, cost=0.01, tokens=(100, 20), status="success", ts=None):
    conn.execute(
        "INSERT INTO requests (ts, model, status, prompt_tokens, completion_tokens,"
        " cost_usd, latency_ms, prompt, response) VALUES (?, ?, ?, ?, ?, ?, 100, ?, 'ok')",
        (
            ts or datetime.datetime.now().isoformat(),
            model, status, tokens[0], tokens[1], cost, prompt,
        ),
    )
    conn.commit()


def test_common_prefix_len():
    assert common_prefix_len("abcd", "abXY") == 2
    assert common_prefix_len("", "abc") == 0
    assert common_prefix_len("same", "same") == 4


def test_repetition_by_model():
    rows = [
        ("lead", "AB"),
        ("lead", "ABCD"),   # 2 of 4 chars repeated
        ("other", "XY"),    # different model, separate chain
        ("lead", "ABCDEF"), # 4 of 6 chars repeated
    ]
    ratios = repetition_by_model(rows)
    assert ratios["lead"] == pytest.approx(6 / 10)
    assert "other" not in ratios  # single request, no consecutive pair


def test_categorize():
    assert categorize("Please summarize this article") == "summarization"
    assert categorize("def main(): ...") == "coding"
    assert categorize("Convert this to JSON") == "extraction"
    assert categorize("hello there") == "other"


def test_daily_digest_aggregates(conn):
    seed(conn, "lead", "AB", cost=0.01)
    seed(conn, "lead", "ABCD", cost=0.02)
    seed(conn, "lead", "fail", cost=0.0, status="failure")
    conn.execute(
        "INSERT INTO budget_events (ts, model, level, spent_usd, budget_usd)"
        " VALUES (?, 'lead', 'warn', 0.8, 1.0)",
        (datetime.datetime.now().isoformat(),),
    )
    conn.commit()

    digest = daily_digest(conn, days=1)

    (day_row,) = digest["per_day"]
    assert day_row["model"] == "lead"
    assert day_row["requests"] == 3
    assert day_row["failures"] == 1
    assert day_row["cost_usd"] == pytest.approx(0.03)
    assert day_row["prompt_tokens"] == 300

    assert digest["context_repetition_ratio"]["lead"] > 0
    assert digest["categories_heuristic"]["other"]["requests"] == 3
    assert digest["budget_events"][0]["level"] == "warn"


def test_old_rows_excluded(conn):
    old = (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()
    seed(conn, "lead", "old prompt", ts=old)
    digest = daily_digest(conn, days=1)
    assert digest["per_day"] == []
