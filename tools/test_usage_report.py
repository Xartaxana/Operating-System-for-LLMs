"""Tests for tools/usage_report.py. No network, no LLM calls -- pure
parsing/SQL over a small sanitized fixture transcript
(tools/fixtures/sample_transcript.jsonl, synthetic usage numbers only,
no real prompt content).

Run from tools/: python -m pytest test_usage_report.py
"""

import sqlite3
from pathlib import Path

import pytest

from usage_report import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    PRICES_PER_TOKEN_USD,
    accounted_cost,
    build_report,
    import_transcripts,
    iter_assistant_turns,
)

FIXTURE = str(Path(__file__).parent / "fixtures" / "sample_transcript.jsonl")


@pytest.fixture()
def db_file(tmp_path):
    return tmp_path / "requests.db"


# ---- parsing ----

def test_parses_only_assistant_lines_and_skips_synthetic():
    turns = list(iter_assistant_turns(FIXTURE))
    models = [t["model"] for t in turns]
    assert "<synthetic>" not in models
    # 8 lines in the fixture: 1 user line and 1 <synthetic> line must be
    # excluded, leaving 6 assistant turns (including the 2 duplicate-
    # requestId lines, which iter_assistant_turns does NOT dedupe --
    # that's import_transcripts's job via the UNIQUE constraint).
    assert len(turns) == 6


def test_skips_non_assistant_line_types():
    turns = list(iter_assistant_turns(FIXTURE))
    for t in turns:
        assert t["model"] != "<synthetic>"
    # the 'user' line in the fixture carries no usage field and no
    # model -- confirm nothing resembling it leaked through.
    assert all(t["model"] for t in turns)


def test_session_id_prefers_json_field_over_filename():
    turns = list(iter_assistant_turns(FIXTURE))
    sessions = {t["session_id"] for t in turns}
    assert sessions == {"session-aaa", "session-bbb"}


def test_dedupe_key_shared_by_split_turn():
    turns = list(iter_assistant_turns(FIXTURE))
    keyed = {t["dedupe_key"]: t for t in turns}
    # req-0002 appears on two JSONL lines (uuid-0002, uuid-0003) with
    # identical usage -- both must produce the SAME dedupe_key so the
    # importer's UNIQUE constraint collapses them to one row.
    dupe_keys = [t["dedupe_key"] for t in turns if t["dedupe_key"].endswith(":req-0002")]
    assert len(dupe_keys) == 2
    assert dupe_keys[0] == dupe_keys[1]


# ---- idempotent import / dedup ----

def test_import_is_idempotent(db_file):
    rows1, sessions1, warnings1 = import_transcripts(FIXTURE, db_file)
    rows2, sessions2, warnings2 = import_transcripts(FIXTURE, db_file)

    conn = sqlite3.connect(db_file)
    count = conn.execute("SELECT COUNT(*) FROM cc_usage").fetchone()[0]

    # 6 assistant turns in the fixture, but req-0002's split lines
    # collapse to 1 row -> 5 distinct API turns.
    assert count == 5
    assert rows1 == 5
    # Second run finds nothing new to insert (INSERT OR IGNORE).
    assert rows2 == 0


def test_import_does_not_touch_requests_table(db_file):
    # Pre-seed a `requests` table row (as the gateway would) and verify
    # the importer never touches it -- cc_usage is a new table, spec
    # explicitly forbids touching `requests`.
    conn = sqlite3.connect(db_file)
    conn.execute(
        "CREATE TABLE requests (id INTEGER PRIMARY KEY, model TEXT)"
    )
    conn.execute("INSERT INTO requests (model) VALUES ('sentinel')")
    conn.commit()
    conn.close()

    import_transcripts(FIXTURE, db_file)

    conn = sqlite3.connect(db_file)
    row = conn.execute("SELECT model FROM requests").fetchone()
    assert row == ("sentinel",)


def test_cc_usage_schema_has_required_columns(db_file):
    import_transcripts(FIXTURE, db_file)
    conn = sqlite3.connect(db_file)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(cc_usage)")}
    for expected in (
        "ts", "project", "session_id", "turn_index", "model",
        "input_tokens", "output_tokens", "cache_creation_tokens",
        "cache_read_tokens", "accounted_cost_usd", "traffic_kind",
        "is_sidechain",
    ):
        assert expected in columns


def test_is_sidechain_flag_recorded(db_file):
    import_transcripts(FIXTURE, db_file)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM cc_usage WHERE model = 'claude-opus-4-8'"
    ).fetchone()
    assert row["is_sidechain"] == 1
    assert row["traffic_kind"] == "real"


# ---- price math including cache rates ----

def test_accounted_cost_known_model():
    cost, warning = accounted_cost(
        "claude-sonnet-5",
        input_tokens=1000, output_tokens=200,
        cache_creation_tokens=500, cache_read_tokens=4000,
    )
    assert warning is None
    input_price, output_price = PRICES_PER_TOKEN_USD["claude-sonnet-5"]
    expected = (
        1000 * input_price
        + 200 * output_price
        + 500 * input_price * CACHE_WRITE_MULTIPLIER
        + 4000 * input_price * CACHE_READ_MULTIPLIER
    )
    assert cost == pytest.approx(expected)


def test_accounted_cost_cache_rates_are_distinct_from_base_input():
    # cache write and cache read must NOT be priced the same as a bare
    # input token, or D-0032's "cache write/read price distinction"
    # requirement is violated.
    base_cost, _ = accounted_cost("claude-sonnet-5", 1000, 0, 0, 0)
    write_cost, _ = accounted_cost("claude-sonnet-5", 0, 0, 1000, 0)
    read_cost, _ = accounted_cost("claude-sonnet-5", 0, 0, 0, 1000)
    assert write_cost > base_cost  # 1.25x premium
    assert read_cost < base_cost  # 0.1x discount
    assert write_cost != read_cost


# ---- unknown-model warning path ----

def test_unknown_model_cost_is_none_with_warning():
    cost, warning = accounted_cost("claude-unknown-model-x", 500, 100, 0, 0)
    assert cost is None
    assert warning is not None
    assert "claude-unknown-model-x" in warning
    assert "WARNING" in warning


def test_unknown_model_never_silently_zero(db_file):
    import_transcripts(FIXTURE, db_file)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM cc_usage WHERE model = 'claude-unknown-model-x'"
    ).fetchone()
    assert row is not None
    assert row["accounted_cost_usd"] is None  # None, never 0.0


def test_report_surfaces_unknown_model_warning(db_file):
    _, _, warnings = import_transcripts(FIXTURE, db_file)
    assert any("claude-unknown-model-x" in w for w in warnings)


# ---- report building ----

def test_build_report_totals_exclude_unknown_cost_from_sum(db_file):
    import_transcripts(FIXTURE, db_file)
    report = build_report(db_file, days=None)
    assert report["totals"]["rows"] == 5
    assert report["totals"]["unknown_cost_rows"] == 1
    # accounted_cost_usd sum should be a real float, not NaN/None, and
    # should not silently include the unknown-model row as $0 hidden
    # inside a total that looks complete.
    assert report["totals"]["accounted_cost_usd"] > 0


def test_build_report_per_project_and_per_session(db_file):
    import_transcripts(FIXTURE, db_file)
    report = build_report(db_file, days=None)
    # both fixture rows share one project dir (the fixture file's own
    # parent directory name), but two distinct session_ids.
    assert len(report["per_project"]) == 1
    session_keys = {s["session_id"] for s in report["top_sessions_by_cost"]}
    assert "session-aaa" in session_keys
    assert "session-bbb" in session_keys


def test_build_report_cache_read_share_of_input(db_file):
    import_transcripts(FIXTURE, db_file)
    report = build_report(db_file, days=None)
    share = report["cache_read_share_of_input"]
    assert share is not None
    assert 0 <= share <= 1


def test_build_report_sidechain_share(db_file):
    import_transcripts(FIXTURE, db_file)
    report = build_report(db_file, days=None)
    assert report["sidechain_tokens"] > 0
    assert report["sidechain_share_of_tokens"] is not None
    assert 0 < report["sidechain_share_of_tokens"] < 1


def test_build_report_days_filter_excludes_old_rows(db_file):
    # The fixture's timestamps are 2026-07-01; a days=1 window relative
    # to "now" (run date is long after the fixture dates) should
    # exclude everything.
    import_transcripts(FIXTURE, db_file)
    report = build_report(db_file, days=1)
    assert report["totals"]["rows"] == 0
