"""Tests for tools/spend_model.py (B1, spend-analytics spec 2026-08-13).

Isolation pattern -- same as tools/test_token_usage_stats.py: a fresh
tmp sqlite DB with cc_usage created directly via usage_report.SCHEMA
(no transcript scan), synthetic journal fixtures on tmp_path (same
write_journal/ev helpers as tools/test_calibration_counts.py). Every
call into spend_model passes explicit `deploys=`/`deploy_project=`
overrides (no test touches the real 3-deploy DEPLOYS config or the
real gateway/requests.db).

Run: python -m pytest tools/test_spend_model.py -q
"""
import json
import os
import subprocess
import sqlite3
from datetime import datetime, timedelta

import pytest

import spend_model as sm
import token_usage_stats as tus
import usage_report
from wallclock_guard import WALLCLOCK_HARNESS_TIMEOUT


@pytest.fixture(autouse=True)
def _isolate_run_units_path(tmp_path, monkeypatch):
    """B4: rebuild() now ALSO imports sm.RUN_UNITS_PATH internally (own
    table, own transaction, E7-legal-absent) -- isolate EVERY test in
    this module, including the pre-existing rebuild() call sites
    (B1/B2), from the real repo's logs/run_units.jsonl, matching this
    module's own stated isolation contract (module docstring: "no test
    touches the real 3-deploy DEPLOYS config or the real
    gateway/requests.db"). Without this, a rebuild() call anywhere in
    this file would silently read whatever the REAL logs/run_units.jsonl
    happens to contain the day a skill first writes to it -- a latent
    flakiness class (D-0043: fixed at the class, once, here, rather than
    threading an explicit override through every one of the ~15 existing
    rebuild() call sites)."""
    monkeypatch.setattr(sm, "RUN_UNITS_PATH", tmp_path / "run_units.jsonl")


# ---------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------
def write_journal(path, lines):
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            if isinstance(line, str):
                fh.write(line + "\n")
            else:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def ev(ts, event, **kw):
    d = {"ts": ts, "event": event}
    d.update(kw)
    return d


def make_db(tmp_path):
    db_file = tmp_path / "requests.db"
    conn = sqlite3.connect(db_file)
    conn.execute(usage_report.SCHEMA)
    conn.commit()
    conn.close()
    return db_file


def insert_cc_row(db_file, ts, project, agent_id=None, model="claude-sonnet-5",
                   input_tokens=100, output_tokens=50, is_sidechain=0,
                   session_id="s-1", dedupe_suffix=None, cache_creation=0, cache_read=0,
                   force_unpriced=False):
    if force_unpriced:
        cost = None
    else:
        cost, _ = usage_report.accounted_cost(model, input_tokens, output_tokens,
                                               cache_creation, cache_read)
    dedupe = f"{session_id}:{dedupe_suffix or ts}:{agent_id}"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        INSERT INTO cc_usage
            (ts, project, session_id, turn_index, model, input_tokens, output_tokens,
             cache_creation_tokens, cache_read_tokens, accounted_cost_usd, traffic_kind,
             is_sidechain, agent_id, agent_type, dedupe_key)
        VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, 'real', ?, ?, NULL, ?)
        """,
        (ts, project, session_id, model, input_tokens, output_tokens,
         cache_creation, cache_read, cost, is_sidechain, agent_id, dedupe),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------
# norm_worker_ref (O1/E2/E9)
# ---------------------------------------------------------------------
def test_norm_worker_ref_strips_agent_prefix():
    assert sm.norm_worker_ref("agent:ad426657432db0805") == "ad426657432db0805"


def test_norm_worker_ref_none_for_cli_form():
    assert sm.norm_worker_ref("cli:2026-08-13T00:00:00") is None


def test_norm_worker_ref_none_for_retro_form():
    assert sm.norm_worker_ref("retro:t-001") is None


def test_norm_worker_ref_none_for_missing():
    assert sm.norm_worker_ref(None) is None


def test_norm_worker_ref_none_for_non_string():
    assert sm.norm_worker_ref(123) is None


def test_norm_worker_ref_boundary_empty_suffix():
    # "agent:" with nothing after the prefix -- boundary of the form
    # parse itself (not one of the spec's named forms), must not crash
    # and must not be treated as a valid key.
    assert sm.norm_worker_ref("agent:") is None


def test_norm_worker_ref_boundary_nonempty_suffix():
    assert sm.norm_worker_ref("agent:x") == "x"


# ---------------------------------------------------------------------
# E1: clock normalization, boundary +-1s on both sides.
# ---------------------------------------------------------------------
def _utc_z_for_local(local_dt):
    """Builds a UTC-'Z' string that normalize_cc_ts_to_local_naive() will
    convert back to exactly `local_dt`, using the MACHINE's actual
    configured UTC offset (TZ-independent test, exact precision --
    unlike the wide +-12h margin test_token_usage_stats.py uses)."""
    offset = datetime.now().astimezone().utcoffset()
    utc_dt = local_dt - offset
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def test_normalize_cc_ts_basic_roundtrip():
    local_dt = datetime(2026, 6, 14, 12, 0, 0)
    ts = _utc_z_for_local(local_dt)
    assert sm.normalize_cc_ts_to_local_naive(ts) == local_dt


def test_normalize_cc_ts_one_second_before_midnight_boundary():
    local_dt = datetime(2026, 6, 13, 23, 59, 59)
    ts = _utc_z_for_local(local_dt)
    result = sm.normalize_cc_ts_to_local_naive(ts)
    assert result == local_dt
    assert tus.window_of(result) == (2026, 5)


def test_normalize_cc_ts_one_second_after_midnight_boundary():
    local_dt = datetime(2026, 6, 14, 0, 0, 1)
    ts = _utc_z_for_local(local_dt)
    result = sm.normalize_cc_ts_to_local_naive(ts)
    assert result == local_dt
    assert tus.window_of(result) == (2026, 6)


def test_normalize_cc_ts_exact_midnight_boundary_is_new_window():
    local_dt = datetime(2026, 6, 14, 0, 0, 0)
    ts = _utc_z_for_local(local_dt)
    result = sm.normalize_cc_ts_to_local_naive(ts)
    assert tus.window_of(result) == (2026, 6)


def test_normalize_cc_ts_none_for_absent():
    assert sm.normalize_cc_ts_to_local_naive(None) is None
    assert sm.normalize_cc_ts_to_local_naive("") is None


def test_normalize_cc_ts_none_for_unparsable():
    assert sm.normalize_cc_ts_to_local_naive("not-a-date") is None


# ---------------------------------------------------------------------
# calibrated_windows / _window_for_ts
# ---------------------------------------------------------------------
def test_calibrated_windows_empty_list_no_crash():
    # E3-adjacent: a deploy with 0 calibrated events (live ao3 fact,
    # 2026-08-13) -- must not crash, must not synthesize a window.
    assert sm.calibrated_windows("x", []) == []


def test_calibrated_windows_first_partial_and_count():
    tss = [datetime(2026, 1, i) for i in range(1, 7)]
    windows = sm.calibrated_windows("shtab", tss)
    assert len(windows) == 6
    assert windows[0]["partial"] == 1
    assert all(w["partial"] == 0 for w in windows[1:])
    assert windows[0]["window_start"] is None
    assert windows[0]["window_end"] == tss[0]
    assert windows[1]["window_start"] == tss[0]
    assert windows[-1]["window_end"] == tss[-1]


def test_window_for_ts_exact_boundary_belongs_to_next_window():
    tss = [datetime(2026, 1, 1), datetime(2026, 1, 2)]
    windows = sm.calibrated_windows("x", tss)
    # exactly at calibrated#1's ts -> window 2 (half-open [start,end))
    w = sm._window_for_ts(windows, datetime(2026, 1, 1))
    assert w["window_id"] == "x:calibrated:2"


def test_window_for_ts_one_microsecond_before_boundary_belongs_to_prev_window():
    tss = [datetime(2026, 1, 1), datetime(2026, 1, 2)]
    windows = sm.calibrated_windows("x", tss)
    w = sm._window_for_ts(windows, datetime(2026, 1, 1) - timedelta(microseconds=1))
    assert w["window_id"] == "x:calibrated:1"


def test_window_for_ts_after_last_window_end_is_none():
    tss = [datetime(2026, 1, 1), datetime(2026, 1, 2)]
    windows = sm.calibrated_windows("x", tss)
    assert sm._window_for_ts(windows, datetime(2026, 1, 2)) is None
    assert sm._window_for_ts(windows, datetime(2027, 1, 1)) is None


def test_window_for_ts_none_input_is_none():
    windows = sm.calibrated_windows("x", [datetime(2026, 1, 1)])
    assert sm._window_for_ts(windows, None) is None


# ---------------------------------------------------------------------
# _agent_stats_for_project -- E6 (NULL cost when all-unpriced)
# ---------------------------------------------------------------------
def test_agent_stats_cost_none_when_all_unpriced(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="aXXX",
                  model="unknown-model-xyz", force_unpriced=True)
    conn = sqlite3.connect(db)
    stats = sm._agent_stats_for_project(conn, "projA")
    assert stats["aXXX"]["cost_usd"] is None
    assert stats["aXXX"]["unpriced_turns"] == 1
    assert stats["aXXX"]["turns"] == 1


def test_agent_stats_cost_is_sum_when_mixed_priced_unpriced(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="aXXX",
                  model="claude-sonnet-5", dedupe_suffix="1")
    insert_cc_row(db, "2026-06-01T00:01:00Z", "projA", agent_id="aXXX",
                  model="unknown-model-xyz", force_unpriced=True, dedupe_suffix="2")
    conn = sqlite3.connect(db)
    stats = sm._agent_stats_for_project(conn, "projA")
    assert stats["aXXX"]["cost_usd"] is not None
    assert stats["aXXX"]["cost_usd"] > 0
    assert stats["aXXX"]["unpriced_turns"] == 1
    assert stats["aXXX"]["turns"] == 2


def test_agent_stats_empty_project_returns_empty_dict(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    assert sm._agent_stats_for_project(conn, "nonexistent") == {}
    assert sm._agent_stats_for_project(conn, None) == {}


# ---------------------------------------------------------------------
# E5: orphan sidechain bucket
# ---------------------------------------------------------------------
def test_orphan_sidechain_bucket_collects_unmatched(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="matched",
                  is_sidechain=1, dedupe_suffix="1")
    insert_cc_row(db, "2026-06-01T00:01:00Z", "projA", agent_id="orphan1",
                  is_sidechain=1, dedupe_suffix="2")
    insert_cc_row(db, "2026-06-01T00:02:00Z", "projA", agent_id="orphan2",
                  is_sidechain=1, dedupe_suffix="3")
    # main-chain traffic (agent_id NULL, is_sidechain 0) never counted.
    insert_cc_row(db, "2026-06-01T00:03:00Z", "projA", agent_id=None,
                  is_sidechain=0, dedupe_suffix="4")
    conn = sqlite3.connect(db)
    bucket = sm._orphan_sidechain_bucket(conn, "projA", matched_keys={"matched"})
    assert bucket is not None
    assert bucket["turns"] == 2
    assert bucket["cost_usd"] is not None and bucket["cost_usd"] > 0


def test_orphan_sidechain_bucket_none_when_all_matched(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="matched",
                  is_sidechain=1)
    conn = sqlite3.connect(db)
    bucket = sm._orphan_sidechain_bucket(conn, "projA", matched_keys={"matched"})
    assert bucket is None


# ---------------------------------------------------------------------
# t-428 fix-batch BLOCKER 0: shared-key cc_usage rows must be split by
# TIME across the stages that reused a key, not aggregated whole onto
# EVERY one of them (the double/triple-counting bug).
# ---------------------------------------------------------------------
def _sonnet_row_cost():
    cost, _w = usage_report.accounted_cost("claude-sonnet-5", 100, 50, 0, 0)
    return cost


def test_fix0_assign_rows_unparsable_ts_clamps_to_last_slot():
    slots = [{"ts_dt": datetime(2026, 7, 1, 0, 0, 0), "rows": []},
             {"ts_dt": datetime(2026, 7, 1, 1, 0, 0), "rows": []}]
    rows = [{"ts_dt": None, "cost_usd": 1.0}]
    sm._assign_rows_to_stage_slots(slots, rows)
    assert slots[0]["rows"] == []
    assert slots[1]["rows"] == rows


def test_fix0_assign_rows_no_ts_having_slot_is_noop():
    slots = [{"ts_dt": None, "rows": []}]
    rows = [{"ts_dt": datetime(2026, 7, 1), "cost_usd": 1.0}]
    sm._assign_rows_to_stage_slots(slots, rows)
    assert slots[0]["rows"] == []


def test_fix0_aggregate_cc_rows_empty_is_all_zero_null():
    agg = sm._aggregate_cc_rows([])
    assert agg == {"turns": 0, "input_tokens": 0, "output_tokens": 0,
                    "cache_creation_tokens": 0, "cache_read_tokens": 0,
                    "cost_usd": None, "unpriced_turns": 0, "models_measured": None}


def test_fix0_shared_key_two_stages_same_task_no_double_count(tmp_path):
    """The blocker itself: 2 delegated stages reuse ONE worker_ref (a
    retry landing on the same dispatch id), 2 cc_usage rows exist for
    that key -- Σ task_cost must equal the TWO rows' real cost, never
    4x (pre-fix: each of the 2 stages got the WHOLE 2-row aggregate)."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared1", notes="n"),
        ev("2026-07-01T00:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-1", attempt=1, failure_class="spec", category="implementation", notes="n"),
        ev("2026-07-01T00:20:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared1",
           attempt=2, notes="n"),
    ])
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projA",
                  agent_id="shared1", dedupe_suffix="1")
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 25, 0)), "projA",
                  agent_id="shared1", dedupe_suffix="2")
    conn = sqlite3.connect(db)
    stage_rows, task_rows, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    assert len(stage_rows) == 2
    one_row_cost = _sonnet_row_cost()
    total = sum(s["cost_usd"] or 0 for s in stage_rows)
    assert total == pytest.approx(one_row_cost * 2)  # NOT 4x (the pre-fix bug)
    assert task_rows[0]["cost_usd"] == pytest.approx(one_row_cost * 2)
    s1 = next(s for s in stage_rows if s["stage_index"] == 1)
    s2 = next(s for s in stage_rows if s["stage_index"] == 2)
    assert s1["cost_usd"] == pytest.approx(one_row_cost)
    assert s2["cost_usd"] == pytest.approx(one_row_cost)


def test_fix0_shared_key_cross_task_not_doubled(tmp_path):
    """O1's own 'кросс-задачное' -- the SAME key reused across TWO
    DIFFERENT tasks; the second task must not also inherit the first
    task's money."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared2", notes="n"),
        ev("2026-07-02T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-2", category="implementation", worker_ref="agent:shared2", notes="n"),
    ])
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projA",
                  agent_id="shared2", dedupe_suffix="1")
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 2, 0, 5, 0)), "projA",
                  agent_id="shared2", dedupe_suffix="2")
    conn = sqlite3.connect(db)
    _stage_rows, task_rows, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    by_task = {t["task_id"]: t for t in task_rows}
    one_row_cost = _sonnet_row_cost()
    assert by_task["t-1"]["cost_usd"] == pytest.approx(one_row_cost)
    assert by_task["t-2"]["cost_usd"] == pytest.approx(one_row_cost)
    assert (by_task["t-1"]["cost_usd"] + by_task["t-2"]["cost_usd"]) == pytest.approx(one_row_cost * 2)


def test_fix0_stage_after_last_row_gets_null_cost_not_zero(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared3", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared3",
           attempt=2, notes="n"),
    ])
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projA",
                  agent_id="shared3", dedupe_suffix="1")
    conn = sqlite3.connect(db)
    stage_rows, _t, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    s1 = next(s for s in stage_rows if s["stage_index"] == 1)
    s2 = next(s for s in stage_rows if s["stage_index"] == 2)
    assert s1["cost_usd"] is not None
    assert s2["cost_usd"] is None  # no row landed in stage 2's slot -- NULL, never 0
    assert s2["turns"] == 0


def test_fix0_row_ts_exact_boundary_goes_to_later_stage(tmp_path):
    """Boundary AT: row.ts == later stage's own ts -> the LATER stage
    (half-open interval, O1's 'ts_local <= ts строки' -- the LAST
    qualifying stage wins)."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared4", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared4",
           attempt=2, notes="n"),
    ])
    ts_at_boundary = _utc_z_for_local(datetime(2026, 7, 1, 1, 0, 0))
    insert_cc_row(db, ts_at_boundary, "projA", agent_id="shared4", dedupe_suffix="1")
    conn = sqlite3.connect(db)
    stage_rows, _t, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    s1 = next(s for s in stage_rows if s["stage_index"] == 1)
    s2 = next(s for s in stage_rows if s["stage_index"] == 2)
    assert s1["cost_usd"] is None
    assert s2["cost_usd"] is not None


def test_fix0_row_ts_one_second_before_boundary_goes_to_earlier_stage(tmp_path):
    """Boundary BEYOND (one second earlier): row.ts < later stage's ts
    -> the EARLIER stage."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared5", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared5",
           attempt=2, notes="n"),
    ])
    ts_before = _utc_z_for_local(datetime(2026, 7, 1, 0, 59, 59))
    insert_cc_row(db, ts_before, "projA", agent_id="shared5", dedupe_suffix="1")
    conn = sqlite3.connect(db)
    stage_rows, _t, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    s1 = next(s for s in stage_rows if s["stage_index"] == 1)
    s2 = next(s for s in stage_rows if s["stage_index"] == 2)
    assert s1["cost_usd"] is not None
    assert s2["cost_usd"] is None


def test_fix0_row_ts_before_all_stages_clamps_to_first_stage(tmp_path):
    """A row's ts precedes EVERY stage sharing the key (R12 journal-
    write batching lag) -- clamps to the FIRST stage, money never
    silently dropped (O3)."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T01:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared6", notes="n"),
        ev("2026-07-01T02:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:shared6",
           attempt=2, notes="n"),
    ])
    ts_early = _utc_z_for_local(datetime(2026, 7, 1, 0, 30, 0))
    insert_cc_row(db, ts_early, "projA", agent_id="shared6", dedupe_suffix="1")
    conn = sqlite3.connect(db)
    stage_rows, _t, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    s1 = next(s for s in stage_rows if s["stage_index"] == 1)
    s2 = next(s for s in stage_rows if s["stage_index"] == 2)
    assert s1["cost_usd"] is not None
    assert s2["cost_usd"] is None


def test_fix0_single_use_key_unaffected_fast_path(tmp_path):
    """Regression guard: the overwhelming common case (a key used by
    exactly ONE stage) must produce the IDENTICAL number the pre-fix
    whole-key-aggregate path gave -- fix 0 changes nothing here."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:solo1", notes="n"),
    ])
    insert_cc_row(db, "2026-07-01T00:05:00Z", "projA", agent_id="solo1", dedupe_suffix="1")
    insert_cc_row(db, "2026-07-01T00:06:00Z", "projA", agent_id="solo1", dedupe_suffix="2")
    conn = sqlite3.connect(db)
    stage_rows, _t, _r = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    assert len(stage_rows) == 1
    assert stage_rows[0]["cost_usd"] == pytest.approx(_sonnet_row_cost() * 2)
    assert stage_rows[0]["turns"] == 2


# ---------------------------------------------------------------------
# shared_key_health / agent_id_session_invariant (t-428 item 0 witness).
# ---------------------------------------------------------------------
def test_shared_key_health_counts_only_groups_over_one(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    j_shared = tmp_path / "shared.jsonl"
    write_journal(j_shared, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-shared", category="implementation", worker_ref="agent:hh1", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-shared", category="implementation", worker_ref="agent:hh1",
           attempt=2, notes="n"),
    ])
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projShared",
                  agent_id="hh1", dedupe_suffix="s1")
    deploys = deploys + [("shared", str(j_shared))]
    deploy_project = dict(deploy_project, shared="projShared")
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    h = sm.shared_key_health(conn, ["shared"])
    assert h["keys"] == 1
    assert h["stages"] == 2
    assert h["cost_usd"] == pytest.approx(_sonnet_row_cost())
    # dep1 in the base fixture has a single-use key only -- not counted.
    h_dep1 = sm.shared_key_health(conn, ["dep1"])
    assert h_dep1 == {"stages": 0, "keys": 0, "cost_usd": 0.0}


def test_shared_key_health_empty_deploy_keys_boundary():
    assert sm.shared_key_health(None, []) == {"stages": 0, "keys": 0, "cost_usd": 0.0}


def test_agent_id_session_invariant_clean_when_one_session_per_key(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="a1", session_id="s-1", dedupe_suffix="1")
    insert_cc_row(db, "2026-06-01T00:05:00Z", "projA", agent_id="a1", session_id="s-1", dedupe_suffix="2")
    conn = sqlite3.connect(db)
    assert sm.agent_id_session_invariant(conn, ["projA"]) == {"violations": []}


def test_agent_id_session_invariant_flags_two_sessions_same_key(tmp_path):
    """Boundary: exactly 2 distinct session_ids for one (agent_id,
    project) -- flags; 1 session (above test) does not."""
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="a1", session_id="s-1", dedupe_suffix="1")
    insert_cc_row(db, "2026-06-01T01:00:00Z", "projA", agent_id="a1", session_id="s-2", dedupe_suffix="2")
    conn = sqlite3.connect(db)
    result = sm.agent_id_session_invariant(conn, ["projA"])
    assert result["violations"] == [{"agent_id": "a1", "project": "projA", "sessions": 2}]


def test_agent_id_session_invariant_empty_projects_boundary():
    assert sm.agent_id_session_invariant(None, []) == {"violations": []}


# ---------------------------------------------------------------------
# stages_and_tasks_for_deploy -- E4 (self_exec), E9, E13, E14, stage
# ordering / stage_kind / rework_stages (replacement excluded).
# ---------------------------------------------------------------------
def test_e14_missing_journal_is_spend_only_not_a_crash(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    missing_path = str(tmp_path / "does_not_exist.jsonl")
    stage_rows, task_rows, reason = sm.stages_and_tasks_for_deploy(
        conn, "ghost", missing_path, "projGhost"
    )
    assert stage_rows == []
    assert task_rows == []
    assert reason is not None
    assert "журнал" in reason


def test_e4_self_exec_task_zero_measurable_stages(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="self-exec, no worker_ref"),
        ev("2026-07-01T00:05:00", "accepted", agent="builder", model="sonnet",
           task_id="t-001", by="fable", category="implementation",
           witness="w", notes="n"),
    ])
    conn = sqlite3.connect(db)
    stage_rows, task_rows, reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    assert reason is None
    assert len(stage_rows) == 1
    assert stage_rows[0]["measurable"] == 0
    assert len(task_rows) == 1
    t = task_rows[0]
    assert t["self_exec"] == 1
    assert t["cost_usd"] is None
    assert t["accepted"] == 1


def test_e9_cli_and_retro_forms_not_measurable(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", worker_ref="cli:2026-07-01T00:00:00", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-002", category="recon", worker_ref="retro:x", notes="n"),
    ])
    conn = sqlite3.connect(db)
    stage_rows, _task_rows, reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    assert reason is None
    assert all(s["measurable"] == 0 for s in stage_rows)
    assert all(s["agent_key"] is None for s in stage_rows)


def test_e13_unparsable_line_does_not_kill_the_run(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", worker_ref="agent:aaa", notes="n"),
        "{not valid json!!!",
        ev("2026-07-01T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-002", category="recon", worker_ref="agent:bbb", notes="n"),
    ])
    conn = sqlite3.connect(db)
    stage_rows, task_rows, reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    assert reason is None
    assert len(stage_rows) == 2  # bad line skipped, run stays alive
    assert len(task_rows) == 2
    # candidate form mirrors calibration_counts.unparsable
    analysis = __import__("calibration_counts").analyze_journal(
        str(j), None, None,
        __import__("calibration_counts").parse_ts(
            __import__("calibration_counts").DEFAULT_BY_SINCE
        ),
    )
    assert len(analysis["unparsable"]) == 1
    assert analysis["unparsable"][0]["line"] == 2


def test_stage_ordering_and_indexing(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T02:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a2", notes="n"),
        ev("2026-07-01T01:00:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, failure_class="spec", category="implementation", notes="n"),
    ])
    conn = sqlite3.connect(db)
    stage_rows, _task_rows, _reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    # only one delegated line here -- stage_index starts at 1 regardless
    # of the rejected line's earlier ts (rejected isn't a stage).
    assert len(stage_rows) == 1
    assert stage_rows[0]["stage_index"] == 1
    assert stage_rows[0]["stage_kind"] == "first"


def test_rework_stages_excludes_replacement_branch(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, failure_class="spec", category="implementation", notes="n"),
        # repeat delegated right after a rejected -> calibration_counts
        # classifies this "continuation" (prior_status=="rejected" takes
        # precedence over the attempt>=2 check in its branch order) ->
        # collapses to "other" here, but is still real rework (not
        # "replacement") -- counted below.
        ev("2026-07-01T00:20:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a2",
           attempt=2, notes="n"),
        # worker-death replacement of a2, referencing a2 (a prior
        # worker_ref of this task) -> calibration_counts "replacement"
        # branch -> excluded from rework_stages per O1.
        ev("2026-07-01T00:30:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a3",
           notes="replaces_worker:agent:a2"),
    ])
    conn = sqlite3.connect(db)
    stage_rows, task_rows, _reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    kinds = {s["stage_index"]: s["stage_kind"] for s in stage_rows}
    assert kinds[1] == "first"
    assert kinds[2] == "other"  # continuation, collapsed -- still counted as rework
    assert kinds[3] == "replacement"
    assert task_rows[0]["rework_stages"] == 1  # only stage 2, not stage 3 (replacement)


# ---------------------------------------------------------------------
# E8: task straddling a calibration boundary.
# ---------------------------------------------------------------------
def test_e8_open_at_window_end_when_task_crosses_boundary(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-05T00:00:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="1"),
        # accepted AFTER the calibration boundary -- task straddles it.
        ev("2026-07-06T00:00:00", "accepted", agent="builder", model="sonnet",
           task_id="t-001", by="fable", category="implementation",
           witness="w", notes="n"),
    ])
    conn = sqlite3.connect(db)
    _stage_rows, task_rows, _reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    t = task_rows[0]
    assert t["window_id"] == "d:calibrated:1"
    assert t["open_at_window_end"] == 1


def test_e8_open_at_window_end_zero_when_fully_inside_window(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:05:00", "accepted", agent="builder", model="sonnet",
           task_id="t-001", by="fable", category="implementation",
           witness="w", notes="n"),
        ev("2026-07-05T00:00:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="1"),
    ])
    conn = sqlite3.connect(db)
    _stage_rows, task_rows, _reason = sm.stages_and_tasks_for_deploy(
        conn, "d", str(j), "projA"
    )
    t = task_rows[0]
    assert t["window_id"] == "d:calibrated:1"
    assert t["open_at_window_end"] == 0


# ---------------------------------------------------------------------
# rebuild() -- idempotency (key 3), cc_usage invariant (key 4/E12),
# E15 (same task_id, two deploys, PK holds).
# ---------------------------------------------------------------------
def _two_deploy_fixture(tmp_path):
    db = make_db(tmp_path)
    j1 = tmp_path / "dep1.jsonl"
    j2 = tmp_path / "dep2.jsonl"
    write_journal(j1, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-100", category="implementation", worker_ref="agent:a1", notes="n"),
    ])
    write_journal(j2, [
        ev("2026-07-01T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-100", category="recon", worker_ref="agent:b1", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-100", category="recon", worker_ref="agent:b2", attempt=2, notes="n"),
    ])
    insert_cc_row(db, "2026-07-01T00:00:30Z", "proj1", agent_id="a1")
    insert_cc_row(db, "2026-07-01T00:00:30Z", "proj2", agent_id="b1", dedupe_suffix="x1")
    insert_cc_row(db, "2026-07-01T01:00:30Z", "proj2", agent_id="b2", dedupe_suffix="x2")
    deploys = [("dep1", str(j1)), ("dep2", str(j2))]
    deploy_project = {"dep1": "proj1", "dep2": "proj2"}
    return db, deploys, deploy_project


def test_e15_same_task_id_two_deploys_pk_holds(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    rows = conn.execute(
        "SELECT deploy, task_id, stages FROM task_costs WHERE task_id = 't-100' ORDER BY deploy"
    ).fetchall()
    assert rows == [("dep1", "t-100", 1), ("dep2", "t-100", 2)]


def test_rebuild_idempotent_byte_identical_dump(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    dump1 = sm._dump_derived_tables(conn)
    sm.rebuild(conn, deploys, deploy_project)
    dump2 = sm._dump_derived_tables(conn)
    sm.rebuild(conn, deploys, deploy_project)
    dump3 = sm._dump_derived_tables(conn)
    assert dump1 == dump2 == dump3
    assert "task_stage_costs" in dump1


def test_e12_cc_usage_invariant_unchanged_by_rebuild(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    conn = sqlite3.connect(db)
    before = sm.cc_usage_invariant(conn)
    sm.rebuild(conn, deploys, deploy_project)
    after = sm.cc_usage_invariant(conn)
    assert before == after
    assert before["count"] == 3


def test_e12_cc_usage_invariant_holds_on_empty_cc_usage(tmp_path):
    # boundary: zero cc_usage rows at all -- invariant (0, None, empty
    # hash) must still match before/after, no crash. row_hash of zero
    # rows is sha256() of nothing -- computed, not hardcoded (item 6).
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    conn = sqlite3.connect(db)
    before = sm.cc_usage_invariant(conn)
    sm.rebuild(conn, [("d", str(j))], {"d": "projX"})
    after = sm.cc_usage_invariant(conn)
    assert before == after == {"count": 0, "sum": None, "row_hash": sm.cc_usage_row_hash(conn)}


def test_cc_usage_row_hash_detects_row_level_change_invisible_to_count_sum(tmp_path):
    """t-428 fix-batch item 6: count+sum alone is BLIND to a mutation
    that swaps row CONTENT without changing the total row count or the
    total priced cost -- the hash must still catch it."""
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "projA", agent_id="a1")
    conn = sqlite3.connect(db)
    before = sm.cc_usage_invariant(conn)
    conn.execute("UPDATE cc_usage SET session_id = 'changed-session-id'")
    conn.commit()
    after = sm.cc_usage_invariant(conn)
    assert before["count"] == after["count"]
    assert before["sum"] == after["sum"]
    assert before["row_hash"] != after["row_hash"]


def test_rebuild_creates_run_units_and_window_series_empty(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    assert conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM window_series").fetchone()[0] == 0


def test_rebuild_e14_partial_deploy_missing_journal(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    deploys = deploys + [("ghost", str(tmp_path / "nope.jsonl"))]
    deploy_project = dict(deploy_project, ghost="projGhost")
    conn = sqlite3.connect(db)
    stats = sm.rebuild(conn, deploys, deploy_project)
    assert any(so["deploy"] == "ghost" for so in stats["spend_only"])
    # other deploys unaffected
    assert stats["task_rows"] >= 2


def test_ensure_schema_migrates_pre_b2_table_missing_is_rework(tmp_path):
    """Regression (found live, gateway/requests.db already had
    task_stage_costs from B1's own accepted run, t-420, WITHOUT
    is_rework -- `CREATE TABLE IF NOT EXISTS` is a no-op on an existing
    table, so B2's new column never appeared without an explicit
    migration). Reproduces the exact live shape: a table created by the
    OLD (pre-is_rework) DDL, then _ensure_schema/rebuild must add the
    column via ALTER TABLE, not crash."""
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    old_ddl = """
        CREATE TABLE task_stage_costs (
            deploy TEXT NOT NULL, task_id TEXT NOT NULL, stage_index INTEGER NOT NULL,
            journal_line INTEGER, ts_local TEXT, agent TEXT, model_declared TEXT,
            worker_ref TEXT, agent_key TEXT, project TEXT, turns INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
            cache_creation_tokens INTEGER NOT NULL DEFAULT 0, cache_read_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL, unpriced_turns INTEGER NOT NULL DEFAULT 0, models_measured TEXT,
            stage_kind TEXT, measurable INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (deploy, task_id, stage_index)
        )
    """
    conn.execute(old_ddl)
    conn.commit()
    cols_before = {r[1] for r in conn.execute("PRAGMA table_info(task_stage_costs)")}
    assert "is_rework" not in cols_before

    sm._ensure_schema(conn)
    cols_after = {r[1] for r in conn.execute("PRAGMA table_info(task_stage_costs)")}
    assert "is_rework" in cols_after
    conn.close()

    # rebuild() must now succeed writing rows with the migrated column,
    # on the SAME (already-migrated) db file.
    j = tmp_path / "mig.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
    ])
    insert_cc_row(db, "2026-07-01T00:00:30Z", "projA", agent_id="a1")
    conn = sqlite3.connect(db)
    stats = sm.rebuild(conn, [("d", str(j))], {"d": "projA"})
    assert stats["task_rows"] >= 1
    rework_col = [r[0] for r in conn.execute("SELECT * FROM task_stage_costs LIMIT 1").description]
    assert "is_rework" in rework_col


def test_ensure_schema_idempotent_when_column_already_present(tmp_path):
    """The non-migration path: a fresh (B2-native) DB already has
    is_rework via SCHEMA_TASK_STAGE_COSTS -- _ensure_schema must be a
    pure no-op (no duplicate-column ALTER TABLE error) on repeat calls."""
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    sm._ensure_schema(conn)
    sm._ensure_schema(conn)  # must not raise "duplicate column name"
    cols = {r[1] for r in conn.execute("PRAGMA table_info(task_stage_costs)")}
    assert "is_rework" in cols


# ---------------------------------------------------------------------
# probe_key_form (accept key 1) / slug mapping (accept key 2)
# ---------------------------------------------------------------------
def test_probe_key_form_counts(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    conn = sqlite3.connect(db)
    result = sm.probe_key_form(conn, deploys, deploy_project)
    assert result["dep1"]["total_delegated"] == 1
    assert result["dep1"]["agent_form"] == 1
    assert result["dep1"]["found"] == 1
    assert result["dep1"]["notfound"] == 0
    assert result["dep2"]["total_delegated"] == 2
    assert result["dep2"]["found"] == 2


def test_probe_key_form_notfound_when_no_cc_usage_row(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:dead", notes="n"),
    ])
    conn = sqlite3.connect(db)
    result = sm.probe_key_form(conn, [("d", str(j))], {"d": "projA"})
    assert result["d"]["agent_form"] == 1
    assert result["d"]["found"] == 0
    assert result["d"]["notfound"] == 1


def test_slug_mapping_reports_project_without_spend(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    deploys = deploys + [("empty", str(tmp_path / "e.jsonl"))]
    deploy_project = dict(deploy_project, empty="projEmpty")
    write_journal(tmp_path / "e.jsonl", [])
    conn = sqlite3.connect(db)
    report = sm._slug_mapping_report(conn, deploys, deploy_project)
    assert report["mapping"]["empty"]["status"] == "проект без трат в БД"
    assert report["mapping"]["dep1"]["status"] == "OK"


# ---------------------------------------------------------------------
# E10: mandatory project filter, boundary AT (0 rows) and BEYOND (1 row).
# ---------------------------------------------------------------------
def test_e10_zero_rows_refuses(tmp_path, capsys):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    assert sm.project_has_rows(conn, "ghostproj") is False
    ok = sm.resolve_project_or_refuse(conn, "ghostproj")
    assert ok is False
    captured = capsys.readouterr()
    assert "SELECT DISTINCT project" in captured.out


def test_e10_one_row_passes(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "realproj", agent_id="a1")
    conn = sqlite3.connect(db)
    assert sm.project_has_rows(conn, "realproj") is True
    assert sm.resolve_project_or_refuse(conn, "realproj") is True


def test_e10_none_project_is_zero_rows(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    assert sm.project_has_rows(conn, None) is False


# ---------------------------------------------------------------------
# Monthly windows / convergence with token_usage_stats (accept key 7).
# ---------------------------------------------------------------------
def test_convergence_check_matches_token_usage_stats_on_fixture(tmp_path):
    db = make_db(tmp_path)
    # Well inside a COMPLETED window: 14.05.2026-14.06.2026 (fixed
    # calendar dates, always in the past relative to any real run of
    # this repo -- no `now` dependency needed for "completed").
    insert_cc_row(db, "2026-05-20T12:00:00Z", "projA", agent_id="a1",
                  model="claude-sonnet-5", input_tokens=1000, output_tokens=500)
    insert_cc_row(db, "2026-05-25T12:00:00Z", "projA", agent_id="a2",
                  model="claude-haiku-4-5", input_tokens=2000, output_tokens=300,
                  dedupe_suffix="x2")
    conn = sqlite3.connect(db)
    rows = sm.convergence_check(conn, "projA", now=datetime(2026, 8, 1))
    assert len(rows) == 1
    assert rows[0]["window"] == "14.05.2026-14.06.2026"
    assert rows[0]["match"] is True
    assert rows[0]["own_cost"] == rows[0]["official_cost"]
    assert rows[0]["own_cost"] > 0


def test_convergence_check_skips_incomplete_window(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-05-20T12:00:00Z", "projA", agent_id="a1")
    conn = sqlite3.connect(db)
    # `now` still inside the same window -> not completed -> skipped.
    rows = sm.convergence_check(conn, "projA", now=datetime(2026, 5, 21))
    assert rows == []


def test_convergence_check_skips_unpriced_window(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-05-20T12:00:00Z", "projA", agent_id="a1",
                  model="unknown-model-xyz", force_unpriced=True)
    conn = sqlite3.connect(db)
    rows = sm.convergence_check(conn, "projA", now=datetime(2026, 8, 1))
    assert rows == []


def test_convergence_check_empty_project(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    assert sm.convergence_check(conn, "nonexistent", now=datetime(2026, 8, 1)) == []


# ---------------------------------------------------------------------
# run_selftest / render_selftest / main() CLI smoke.
# ---------------------------------------------------------------------
def test_run_selftest_end_to_end_skip_import(tmp_path):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    report = sm.run_selftest(db, deploys, deploy_project, skip_import=True)
    assert report["import"]["elapsed_sec"] >= 0
    assert report["import"]["over_60s"] is False
    assert "dep1" in report["key_probe"]
    assert report["rebuild"]["idempotent"] is True
    assert report["cc_usage_invariant"]["match"] is True
    text = sm.render_selftest(report)
    assert "SPEND_MODEL SELFTEST" in text
    assert "dep1" in text


def test_main_selftest_json_smoke(tmp_path, capsys, monkeypatch):
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    monkeypatch.setattr(sm, "DEPLOYS", deploys)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", deploy_project)
    rc = sm.main(["--selftest", "--json", "--skip-import", "--db", str(db)])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "key_probe" in data
    assert data["rebuild"]["idempotent"] is True


def test_main_project_flag_zero_rows_exits_2(tmp_path, capsys):
    db = make_db(tmp_path)
    rc = sm.main(["--project", "ghostproj", "--db", str(db)])
    assert rc == 2
    assert "SELECT DISTINCT project" in capsys.readouterr().out


def test_main_project_flag_valid_project_exits_0(tmp_path):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "realproj", agent_id="a1")
    rc = sm.main(["--project", "realproj", "--db", str(db)])
    assert rc == 0


def test_main_no_args_prints_help(capsys):
    rc = sm.main([])
    assert rc == 0
    assert "usage" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------
# stage_kind collapse mapping -- direct unit coverage of the enum
# collapse (first|retry|critic|replacement|other).
# ---------------------------------------------------------------------
@pytest.mark.parametrize("branch,expected", [
    (None, "first"),
    ("critic-вход", "critic"),
    ("retry", "retry"),
    ("replacement", "replacement"),
    ("кандидат-дубль", "other"),
    ("continuation", "other"),
    ("replacement-фиктивный", "other"),
    ("other", "other"),
    ("some-unknown-future-branch", "other"),
])
def test_stage_kind_collapse(branch, expected):
    assert sm._stage_kind(branch) == expected


# =======================================================================
# B2 -- metrics M1-M14/M4b and detectors D1-D9
# (docs/tasks/2026-08-13_spend-analytics.md, sections 1/5, node B2)
# =======================================================================

def _task(deploy="d", task_id="t-1", accepted=1, stages=1, cost_usd=10.0,
          unpriced_turns=0, rework_stages=0, critic_entries=0, escalated_count=0):
    return {"deploy": deploy, "task_id": task_id, "accepted": accepted, "stages": stages,
            "cost_usd": cost_usd, "unpriced_turns": unpriced_turns,
            "rework_stages": rework_stages, "critic_entries": critic_entries,
            "escalated_count": escalated_count}


def _stage(deploy="d", task_id="t-1", cost_usd=1.0, is_rework=0, agent="builder",
           model_declared="sonnet", measurable=1, agent_key="a1", turns=1,
           input_tokens=0, output_tokens=0, cache_creation_tokens=0, cache_read_tokens=0):
    return {"deploy": deploy, "task_id": task_id, "cost_usd": cost_usd, "is_rework": is_rework,
            "agent": agent, "model_declared": model_declared, "measurable": measurable,
            "agent_key": agent_key, "turns": turns, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "cache_creation_tokens": cache_creation_tokens,
            "cache_read_tokens": cache_read_tokens}


def _cc(cost, is_sidechain=0, model="claude-sonnet-5", agent_id=None,
        input_tokens=0, output_tokens=0, cache_creation_tokens=0, cache_read_tokens=0,
        session_id="s-1", ts="2026-06-01T00:00:00Z"):
    return {"ts": ts, "project": "projA", "model": model, "is_sidechain": is_sidechain,
            "agent_id": agent_id, "accounted_cost_usd": cost, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "cache_creation_tokens": cache_creation_tokens,
            "cache_read_tokens": cache_read_tokens, "session_id": session_id}


# -----------------------------------------------------------------------
# _sum_optional / _metric / _ts_in_window
# -----------------------------------------------------------------------
def test_sum_optional_none_when_all_none():
    assert sm._sum_optional([None, None]) is None


def test_sum_optional_skips_none_sums_rest():
    assert sm._sum_optional([1, None, 2]) == 3.0


def test_sum_optional_empty_iterable_is_none():
    assert sm._sum_optional([]) is None


def test_ts_in_window_half_open_boundaries():
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 2)
    assert sm._ts_in_window(start, start, end) is True
    assert sm._ts_in_window(end, start, end) is False
    assert sm._ts_in_window(end - timedelta(microseconds=1), start, end) is True
    assert sm._ts_in_window(None, start, end) is False


# -----------------------------------------------------------------------
# is_rework stage flag (B2 refactor of B1's rework_stages computation --
# regression guard: same scenario as B1's
# test_rework_stages_excludes_replacement_branch, now also checking the
# per-stage flag the count is derived from).
# -----------------------------------------------------------------------
def test_is_rework_flag_matches_rework_stages_count(tmp_path):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, failure_class="spec", category="implementation", notes="n"),
        ev("2026-07-01T00:20:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a2",
           attempt=2, notes="n"),
        ev("2026-07-01T00:30:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:a3",
           notes="replaces_worker:agent:a2"),
    ])
    conn = sqlite3.connect(db)
    stage_rows, task_rows, _reason = sm.stages_and_tasks_for_deploy(conn, "d", str(j), "projA")
    flags = {s["stage_index"]: s["is_rework"] for s in stage_rows}
    assert flags == {1: 0, 2: 1, 3: 0}
    assert task_rows[0]["rework_stages"] == sum(flags.values()) == 1


# -----------------------------------------------------------------------
# M1
# -----------------------------------------------------------------------
def test_m1_basic():
    tasks = [_task(accepted=1, stages=3), _task(accepted=1, stages=2), _task(accepted=0, stages=1)]
    m = sm._m1(tasks)
    assert m["value"] == 3.0
    assert m["denominator_kind"] == "accepted_tasks"
    assert m["denominator_value"] == 2
    assert m["reason"] is None


def test_m1_empty_window_e3():
    m = sm._m1([])
    assert m["value"] is None
    assert "пустое окно" in m["reason"]


def test_m1_zero_accepted_boundary():
    m = sm._m1([_task(accepted=0, stages=5)])
    assert m["value"] is None
    assert m["denominator_value"] == 0
    assert "0 принятых" in m["reason"]


def test_m1_one_accepted_beyond_boundary():
    m = sm._m1([_task(accepted=1, stages=5)])
    assert m["value"] == 5.0


# -----------------------------------------------------------------------
# M2
# -----------------------------------------------------------------------
def test_m2_basic():
    tasks = [_task(cost_usd=10.0, stages=2), _task(cost_usd=20.0, stages=3)]
    m = sm._m2(tasks)
    assert m["value"] == 6.0
    assert m["denominator_value"] == 5


def test_m2_all_unpriced_never_zero():
    tasks = [_task(cost_usd=None, stages=2, unpriced_turns=1),
             _task(cost_usd=None, stages=1, unpriced_turns=1)]
    m = sm._m2(tasks)
    assert m["value"] is None
    assert m["unpriced_turns"] == 2
    assert "без цены" in m["reason"]


def test_m2_zero_stages_boundary():
    m = sm._m2([_task(cost_usd=10.0, stages=0)])
    assert m["value"] is None
    assert m["denominator_value"] == 0


# -----------------------------------------------------------------------
# M3
# -----------------------------------------------------------------------
def test_m3_no_rework_is_real_zero():
    tasks = [_task(cost_usd=10.0)]
    stages = [_stage(cost_usd=10.0, is_rework=0)]
    m = sm._m3(tasks, stages)
    assert m["value"] == 0.0
    assert m["reason"] is None


def test_m3_with_rework_share():
    tasks = [_task(cost_usd=10.0)]
    stages = [_stage(cost_usd=6.0, is_rework=0), _stage(cost_usd=4.0, is_rework=1)]
    m = sm._m3(tasks, stages)
    assert m["value"] == pytest.approx(0.4)


def test_m3_all_task_cost_none():
    m = sm._m3([_task(cost_usd=None, unpriced_turns=1)], [])
    assert m["value"] is None
    assert "без цены" in m["reason"]


def test_m3_rework_stages_unpriced_boundary():
    tasks = [_task(cost_usd=10.0)]
    stages = [_stage(cost_usd=None, is_rework=1)]
    m = sm._m3(tasks, stages)
    assert m["value"] is None
    assert "переделочные" in m["reason"]


# -----------------------------------------------------------------------
# M4 -- LIVE CONTROL (accept key 8): calibration #6 numbers, journal
# line 1019 ("сайдчейны окна $789.35 против main $1527.29 = 34%").
# B1's own test-isolation convention (module docstring) means this test
# never touches the real gateway/requests.db -- a fixture reproducing
# the exact two totals, per the spec's own fallback clause ("если живая
# БД в тестах недоступна конвенцией B1 -- фикстурный тест с этими
# числами и docstring-ссылкой на событие журнала 1019").
# -----------------------------------------------------------------------
def test_m4_live_control_calibration6_numbers():
    cc_rows = [_cc(1527.29, is_sidechain=0), _cc(789.35, is_sidechain=1)]
    m = sm._m4(cc_rows)
    assert m["value"] == pytest.approx(1527.29 / (1527.29 + 789.35), abs=1e-9)
    assert round(m["value"], 2) == 0.66


def test_m4_empty_window_e3():
    m = sm._m4([])
    assert m["value"] is None
    assert "пустое окно" in m["reason"]


def test_m4_all_unpriced_never_zero():
    m = sm._m4([_cc(None, is_sidechain=0), _cc(None, is_sidechain=1)])
    assert m["value"] is None
    assert m["unpriced_turns"] == 2


def test_m4_no_main_chain_is_real_zero():
    m = sm._m4([_cc(5.0, is_sidechain=1)])
    assert m["value"] == 0.0


# -----------------------------------------------------------------------
# M4b
# -----------------------------------------------------------------------
def test_m4b_per_model_rows_carry_caveat():
    cc_rows = [_cc(3.0, is_sidechain=0, model="claude-sonnet-5"),
               _cc(5.0, is_sidechain=0, model="claude-opus-5")]
    tasks = [_task(accepted=1), _task(accepted=1)]
    out = sm._m4b(cc_rows, tasks)
    assert out["M4b:claude-sonnet-5"]["value"] == pytest.approx(1.5)
    assert out["M4b:claude-opus-5"]["value"] == pytest.approx(2.5)
    assert out["M4b:claude-sonnet-5"]["reason"] == sm.M4B_CAVEAT


def test_m4b_zero_accepted_boundary():
    out = sm._m4b([_cc(3.0, is_sidechain=0)], [_task(accepted=0)])
    assert out["M4b:claude-sonnet-5"]["value"] is None
    assert "0 принятых" in out["M4b:claude-sonnet-5"]["reason"]


def test_m4b_no_main_chain_traffic():
    out = sm._m4b([_cc(3.0, is_sidechain=1)], [_task(accepted=1)])
    assert out["M4b"]["value"] is None
    assert "main-chain" in out["M4b"]["reason"]


# -----------------------------------------------------------------------
# M5 / top_n_tasks
# -----------------------------------------------------------------------
def test_top_n_tasks_ranks_desc_and_limits():
    tasks = [_task(task_id="t-1", cost_usd=5.0), _task(task_id="t-2", cost_usd=20.0),
              _task(task_id="t-3", cost_usd=None), _task(task_id="t-4", cost_usd=10.0)]
    ranked = sm.top_n_tasks(tasks, top_n=2)
    assert [t["task_id"] for t in ranked] == ["t-2", "t-4"]


def test_m5_top1_and_empty():
    out = sm._m5([_task(task_id="t-1", cost_usd=5.0), _task(task_id="t-2", cost_usd=20.0)])
    assert out["M5"]["value"] == 20.0
    assert "t-2" in out["M5"]["denominator_kind"]
    empty = sm._m5([])
    assert empty["M5"]["value"] is None


# -----------------------------------------------------------------------
# M9
# -----------------------------------------------------------------------
def test_m9_basic(tmp_path):
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:05:00", "accepted", agent="builder", model="sonnet",
           task_id="t-1", by="fable", category="implementation", witness="w", notes="n"),
    ])
    m4 = sm._metric(10.0, "cc_usage_cost_all", 10.0, 0, None)
    m = sm._m9([("d", str(j))], datetime(2026, 7, 1), datetime(2026, 7, 2), m4)
    assert m["denominator_value"] == 2
    assert m["value"] == pytest.approx(5.0)


def test_m9_zero_events_boundary(tmp_path):
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    m4 = sm._metric(10.0, "cc_usage_cost_all", 10.0, 0, None)
    m = sm._m9([("d", str(j))], None, None, m4)
    assert m["value"] is None
    assert m["denominator_value"] == 0


def test_m9_missing_journal_reason(tmp_path):
    m4 = sm._metric(10.0, "cc_usage_cost_all", 10.0, 0, None)
    m = sm._m9([("d", str(tmp_path / "nope.jsonl"))], None, None, m4)
    assert m["value"] is None
    assert "недоступны" in m["reason"]


# -----------------------------------------------------------------------
# M10 (per-tier -- see the module docstring's judgment-call note on
# 'ярус' = model_declared, not the `agent` role field)
# -----------------------------------------------------------------------
def test_m10_per_tier_basic():
    tasks = [_task(task_id="t-1", accepted=1), _task(task_id="t-2", accepted=1)]
    stages = [
        _stage(task_id="t-1", cost_usd=4.0, model_declared="sonnet"),
        _stage(task_id="t-2", cost_usd=6.0, model_declared="sonnet"),
        _stage(task_id="t-2", cost_usd=8.0, model_declared="opus"),
    ]
    out = sm._m10(tasks, stages)
    assert out["M10:sonnet"]["value"] == pytest.approx(10.0 / 2)
    assert out["M10:opus"]["value"] == pytest.approx(8.0 / 1)
    # t-428 fix-batch "мелочь": M10's caveat rides alongside a real
    # value too (same convention as M4B_CAVEAT), never silent about a
    # multi-tier task landing in several M10 denominators.
    assert out["M10:sonnet"]["reason"] == sm.M10_CAVEAT
    assert out["M10:opus"]["reason"] == sm.M10_CAVEAT


def test_m10_zero_accepted_for_tier_boundary():
    tasks = [_task(task_id="t-1", accepted=0)]
    stages = [_stage(task_id="t-1", cost_usd=4.0, model_declared="sonnet")]
    out = sm._m10(tasks, stages)
    assert out["M10:sonnet"]["value"] is None
    assert out["M10:sonnet"]["denominator_value"] == 0


def test_m10_no_model_declared_stages():
    out = sm._m10([_task()], [])
    assert out["M10"]["value"] is None


# -----------------------------------------------------------------------
# normalize_tier_family (B3 point-fix, finding 8в.1) -- 5 boundary tests
# named verbatim by the spec DoD: fable, fable-5, claude-fable-5, gpt-5,
# empty/None.
# -----------------------------------------------------------------------
def test_normalize_tier_family_exact_fable():
    assert sm.normalize_tier_family("fable") == ("fable", None)


def test_normalize_tier_family_fable_5_collapses():
    assert sm.normalize_tier_family("fable-5") == ("fable", None)


def test_normalize_tier_family_claude_fable_5_collapses():
    assert sm.normalize_tier_family("claude-fable-5") == ("fable", None)


def test_normalize_tier_family_unknown_string_stays_raw_not_lost():
    # gpt-5 matches none of the 4 tier words -- returned AS-IS, never
    # silently mapped, never dropped (spec's own "не теряется и не
    # мапится молча").
    assert sm.normalize_tier_family("gpt-5") == ("gpt-5", None)


def test_normalize_tier_family_empty_or_none_buckets_unknown_with_reason():
    fam, reason = sm.normalize_tier_family("")
    assert fam == "unknown"
    assert reason is not None
    fam2, reason2 = sm.normalize_tier_family(None)
    assert fam2 == "unknown"
    assert reason2 is not None


@pytest.mark.parametrize("raw,expected", [
    ("haiku", "haiku"), ("sonnet", "sonnet"), ("opus", "opus"),
    ("HAIKU", "haiku"), ("Claude-Sonnet-5", "sonnet"),
])
def test_normalize_tier_family_other_tiers_and_case_insensitivity(raw, expected):
    assert sm.normalize_tier_family(raw)[0] == expected


def test_m10_d4_collapse_drifted_fable_declarations_into_one_row():
    """Live finding 8в.1 reproduced with a fixture: model_declared drift
    (fable / fable-5 / claude-fable-5) across 3 stages of 3 DIFFERENT
    tasks must land in ONE M10:fable row (and one D4:fable row via
    _compute_detectors' M10-key mirroring), not three fragmented rows."""
    tasks = [_task(task_id="t-1", accepted=1), _task(task_id="t-2", accepted=1),
             _task(task_id="t-3", accepted=1)]
    stages = [
        _stage(task_id="t-1", cost_usd=1.0, model_declared="fable"),
        _stage(task_id="t-2", cost_usd=2.0, model_declared="fable-5"),
        _stage(task_id="t-3", cost_usd=3.0, model_declared="claude-fable-5"),
    ]
    out = sm._m10(tasks, stages)
    assert list(out.keys()) == ["M10:fable"]
    assert out["M10:fable"]["value"] == pytest.approx(6.0 / 3)
    metrics = dict(out)
    metrics.update({"M1": sm._metric(1.0), "M2": sm._metric(1.0),
                     "M3": sm._metric(0.0), "M4": sm._metric(0.5)})
    detectors = sm._compute_detectors(metrics, {})
    assert "D4:fable" in detectors
    assert "D4:fable-5" not in detectors
    assert "D4:claude-fable-5" not in detectors


# -----------------------------------------------------------------------
# M11 -- git numstat (real tmp git repos; subprocess allowed, section 9)
# -----------------------------------------------------------------------
def _git(*args, cwd, env=None):
    # F-60 (класс A): timeout -- сетка против зависшего git-процесса, не
    # утверждение о предмете; WALLCLOCK_HARNESS_TIMEOUT -- общий источник
    # значения.
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                               env=env, timeout=WALLCLOCK_HARNESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"git {' '.join(args)} exceeded WALLCLOCK_HARNESS_TIMEOUT="
            f"{WALLCLOCK_HARNESS_TIMEOUT}s -- сторож стенных часов: "
            "проверь загрузку машины прежде, чем считать это дефектом (F-60)"
        )


def _init_repo_with_commit(repo_dir, commit_dt):
    repo_dir.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=str(repo_dir))
    _git("config", "user.email", "t@example.com", cwd=str(repo_dir))
    _git("config", "user.name", "T", cwd=str(repo_dir))
    (repo_dir / "f.txt").write_text("a\nb\nc\n", encoding="utf-8")
    env = dict(os.environ)
    date_str = commit_dt.strftime("%Y-%m-%dT%H:%M:%S")
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str
    _git("add", "f.txt", cwd=str(repo_dir))
    r = _git("commit", "-q", "-m", "init", cwd=str(repo_dir), env=env)
    assert r.returncode == 0, r.stderr


def test_git_numstat_zero_commits_in_repo_is_zero_not_none(tmp_path):
    repo = tmp_path / "repo0"
    repo.mkdir()
    _git("init", "-q", cwd=str(repo))
    total, reason = sm._git_numstat_added_deleted(str(repo), None, None)
    assert total == 0
    assert reason is None


def test_git_numstat_not_a_repo_returns_reason(tmp_path):
    not_repo = tmp_path / "not_a_repo"
    not_repo.mkdir()
    total, reason = sm._git_numstat_added_deleted(str(not_repo), None, None)
    assert total is None
    assert reason is not None


def test_git_numstat_counts_added_lines_in_range(tmp_path):
    repo = tmp_path / "repo1"
    _init_repo_with_commit(repo, datetime(2026, 6, 15, 12, 0, 0))
    total, reason = sm._git_numstat_added_deleted(
        str(repo), datetime(2026, 6, 15, 0, 0, 0), datetime(2026, 6, 16, 0, 0, 0))
    assert reason is None
    assert total == 3  # f.txt: 3 added lines, 0 deleted


def test_git_numstat_outside_range_is_zero(tmp_path):
    repo = tmp_path / "repo2"
    _init_repo_with_commit(repo, datetime(2026, 6, 15, 12, 0, 0))
    total, reason = sm._git_numstat_added_deleted(
        str(repo), datetime(2026, 7, 1, 0, 0, 0), datetime(2026, 7, 2, 0, 0, 0))
    assert reason is None
    assert total == 0


def test_m11_zero_commits_boundary_is_none(tmp_path):
    repo = tmp_path / "repo0"
    repo.mkdir()
    _git("init", "-q", cwd=str(repo))
    j = repo / "logs" / "routing-log.jsonl"
    j.parent.mkdir(parents=True)
    write_journal(j, [])
    stages = [_stage(agent="critic", cost_usd=9.0)]
    m = sm._m11([("d", str(j))], stages, None, None)
    assert m["value"] is None
    assert "0 коммитов" in m["reason"]


def test_m11_nonzero_commits_beyond_boundary(tmp_path):
    repo = tmp_path / "repo1"
    _init_repo_with_commit(repo, datetime(2026, 6, 15, 12, 0, 0))
    j = repo / "logs" / "routing-log.jsonl"
    j.parent.mkdir(parents=True)
    write_journal(j, [])
    stages = [_stage(agent="critic", cost_usd=9.0)]
    m = sm._m11([("d", str(j))], stages,
                datetime(2026, 6, 15, 0, 0, 0), datetime(2026, 6, 16, 0, 0, 0))
    assert m["value"] == pytest.approx(3.0)  # 9.0 / 3 lines


def test_m11_no_critic_stages():
    m = sm._m11([], [_stage(agent="builder")], None, None)
    assert m["value"] is None
    assert "critic" in m["reason"]


# -----------------------------------------------------------------------
# M6/M7/M8/M12 -- run_units (E7: table/rows absent -> honest "н/д")
# -----------------------------------------------------------------------
def _run_units_db(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute(sm.SCHEMA_RUN_UNITS)
    conn.commit()
    conn.close()
    return db


def test_m6_m7_m8_m12_e7_empty_registry_is_na(tmp_path):
    db = _run_units_db(tmp_path)
    conn = sqlite3.connect(db)
    out = sm._m6_m7_m8_m12(conn, ["projA"], None, None)
    for key in ("M6", "M7", "M8", "M12"):
        assert out[key]["value"] is None
        assert "н/д" in out[key]["reason"]


def _insert_run_unit(db, **kw):
    row = {"run_id": "r1", "run_kind": "skill", "name": "boot-diet", "phase": None,
           "ts_start": "2026-07-01T00:00:00", "ts_end": "2026-07-01T00:10:00",
           "session_id": "s-1", "unit_kind": "bytes", "unit_count": 100, "source": "test"}
    row.update(kw)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO run_units (run_id, run_kind, name, phase, ts_start, ts_end, session_id,"
        " unit_kind, unit_count, source) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (row["run_id"], row["run_kind"], row["name"], row["phase"], row["ts_start"],
         row["ts_end"], row["session_id"], row["unit_kind"], row["unit_count"], row["source"]),
    )
    conn.commit()
    conn.close()


def test_m6_m8_with_run_units_data(tmp_path):
    db = _run_units_db(tmp_path)
    _insert_run_unit(db)
    # run_units ts_start/ts_end are LOCAL NAIVE (E1); cc_usage.ts is UTC-Z
    # (E1's ~2h gap) -- _utc_z_for_local (this file's own E1 helper, see
    # normalize_cc_ts_* tests above) builds a Z-string that normalizes
    # back to the intended LOCAL point, TZ-independent of this machine.
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projA",
                  agent_id=None, session_id="s-1", input_tokens=1000, output_tokens=500)
    conn = sqlite3.connect(db)
    out = sm._m6_m7_m8_m12(conn, ["projA"], datetime(2026, 7, 1), datetime(2026, 7, 2))
    assert out["M6:skill:boot-diet"]["value"] is not None
    assert out["M6:skill:boot-diet"]["value"] > 0
    assert out["M8:skill:boot-diet"]["value"] == pytest.approx(
        out["M6:skill:boot-diet"]["value"] / 100)


def test_m7_phase_share_with_and_without_labels(tmp_path):
    db = _run_units_db(tmp_path)
    _insert_run_unit(db, run_id="r2", name="permission-audit")
    _insert_run_unit(db, run_id="r2", phase="1", ts_start="2026-07-01T00:00:00",
                      ts_end="2026-07-01T00:05:00")
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 2, 0)), "projA",
                  agent_id=None, session_id="s-1", input_tokens=500, output_tokens=200)
    conn = sqlite3.connect(db)
    out = sm._m6_m7_m8_m12(conn, ["projA"], datetime(2026, 7, 1), datetime(2026, 7, 2))
    assert "M7:skill:permission-audit:1" in out
    assert 0 <= out["M7:skill:permission-audit:1"]["value"] <= 1


def test_m12_with_calibration_run(tmp_path, monkeypatch):
    db = _run_units_db(tmp_path)
    _insert_run_unit(db, run_id="rc", run_kind="calibration", name="calibration",
                      unit_kind=None, unit_count=None)
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projA",
                  agent_id=None, session_id="s-1", input_tokens=1000, output_tokens=500)
    protocol = tmp_path / "protocol.md"
    protocol.write_text("1. **a**\n2. **b**\n", encoding="utf-8")
    monkeypatch.setattr(sm, "PROTOCOL_PATH", protocol)
    conn = sqlite3.connect(db)
    out = sm._m6_m7_m8_m12(conn, ["projA"], datetime(2026, 7, 1), datetime(2026, 7, 2))
    assert out["M12"]["value"] is not None
    assert out["M12"]["denominator_value"] == 2


def test_count_protocol_checks_unavailable_boundary(tmp_path):
    assert sm.count_protocol_checks(tmp_path / "nope.md") is None


def test_count_protocol_checks_real_protocol_is_34():
    """Пин числа чеков живого протокола.

    Это НАМЕРЕННАЯ растяжка, а не хрупкость: пин ловит регресс парсера
    (сломанный regex вернул бы 12, а не 34) и заодно обязывает того, кто
    добавил чек в PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md, обновить пин
    ТЕМ ЖЕ коммитом. До 2026-08-16 обязанность была необъявленной —
    имя теста несло число, а норму нигде не писали; чек 33 (детектор
    heartbeat-fastdeath) уронил этот тест ровно поэтому.
    """
    assert sm.count_protocol_checks() == 34


# -----------------------------------------------------------------------
# import_run_units (B4, docs/tasks/2026-08-13_spend-analytics.md
# section 2/6/7 node B4) -- raw run_units.jsonl -> run_units TABLE.
# -----------------------------------------------------------------------
def test_import_run_units_absent_file_is_legal(tmp_path):
    db = _run_units_db(tmp_path)
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=tmp_path / "nope.jsonl")
    assert report == {"legal_absent": True, "level_rows": 0, "phase_rows": 0, "candidates": []}
    assert conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0] == 0


def test_import_run_units_wipes_stale_rows_when_file_later_absent(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_start", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    sm.import_run_units(conn, path=p)
    assert conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0] == 1
    report = sm.import_run_units(conn, path=tmp_path / "gone.jsonl")
    assert report["legal_absent"] is True
    assert conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0] == 0


def test_import_run_units_basic_run_start_end(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-08-13T15:00:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
        {"ts": "2026-08-13T15:40:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_end", "session_id": "s-1", "unit_kind": "sync_pairs",
         "unit_count": 86, "source": "kit-release/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["legal_absent"] is False
    assert report["level_rows"] == 1
    assert report["phase_rows"] == 0
    assert report["candidates"] == []
    row = conn.execute(
        "SELECT ts_start, ts_end, unit_kind, unit_count, session_id FROM run_units"
        " WHERE run_id='r1' AND phase IS NULL"
    ).fetchone()
    assert row == ("2026-08-13T15:00:00", "2026-08-13T15:40:00", "sync_pairs", 86, "s-1")


def test_import_run_units_idempotent_byte_identical(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-08-13T15:00:00", "run_id": "r1", "run_kind": "skill", "name": "boot-diet",
         "phase": None, "event": "run_start", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "boot-diet/SKILL.md"},
        {"ts": "2026-08-13T15:10:00", "run_id": "r1", "run_kind": "skill", "name": "boot-diet",
         "phase": None, "event": "run_end", "session_id": None, "unit_kind": "boot_bytes",
         "unit_count": 61234, "source": "boot-diet/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    sm.import_run_units(conn, path=p)
    dump1 = sm._dump_derived_tables(conn)
    sm.import_run_units(conn, path=p)
    dump2 = sm._dump_derived_tables(conn)
    sm.import_run_units(conn, path=p)
    dump3 = sm._dump_derived_tables(conn)
    assert dump1 == dump2 == dump3
    assert "run_units" in dump1


def test_import_run_units_unparsable_line_candidate_import_stays_alive(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("{not json\n")
        fh.write(json.dumps({
            "ts": "2026-08-13T15:00:00", "run_id": "r1", "run_kind": "skill",
            "name": "permission-audit", "phase": None, "event": "run_start",
            "session_id": None, "unit_kind": None, "unit_count": None,
            "source": "permission-audit/SKILL.md",
        }, ensure_ascii=False) + "\n")
        fh.write(json.dumps({
            "ts": "2026-08-13T15:05:00", "run_id": "r1", "run_kind": "skill",
            "name": "permission-audit", "phase": None, "event": "run_end",
            "session_id": None, "unit_kind": "prompts_analyzed", "unit_count": 40,
            "source": "permission-audit/SKILL.md",
        }, ensure_ascii=False) + "\n")
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["legal_absent"] is False
    assert report["level_rows"] == 1
    assert len(report["candidates"]) == 1
    assert report["candidates"][0]["line"] == 1


def test_import_run_units_missing_run_id_is_candidate(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [{"ts": "2026-07-01T00:00:00", "run_kind": "skill", "name": "x",
                        "phase": None, "event": "run_start", "session_id": None,
                        "unit_kind": None, "unit_count": None, "source": "x"}])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 0
    assert any("run_id" in c["error"] for c in report["candidates"])


def test_import_run_units_unknown_event_is_candidate(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [{"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill",
                        "name": "x", "phase": None, "event": "run_pause", "session_id": None,
                        "unit_kind": None, "unit_count": None, "source": "x"}])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 0
    assert any("event" in c["error"] for c in report["candidates"])


def test_import_run_units_bad_ts_is_candidate(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [{"ts": "not-a-date", "run_id": "r1", "run_kind": "skill", "name": "x",
                        "phase": None, "event": "run_start", "session_id": None,
                        "unit_kind": None, "unit_count": None, "source": "x"}])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 0
    assert any("ts" in c["error"] for c in report["candidates"])


def test_import_run_units_open_run_no_end_is_na(tmp_path):
    # E7/M6 boundary: run_start with NO run_end -- "прогон открыт".
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-08-13T15:00:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 1
    row = conn.execute(
        "SELECT ts_start, ts_end FROM run_units WHERE run_id='r1' AND phase IS NULL"
    ).fetchone()
    assert row == ("2026-08-13T15:00:00", None)
    cols = ["run_id", "run_kind", "name", "phase", "ts_start", "ts_end", "session_id",
            "unit_kind", "unit_count", "source"]
    run_row = dict(zip(cols, conn.execute(
        "SELECT * FROM run_units WHERE run_id='r1' AND phase IS NULL").fetchone()))
    m = sm.m6_run_cost(conn, ["projA"], run_row)
    assert m["value"] is None
    assert "н/д" in m["reason"]


def test_import_run_units_closed_run_with_cc_usage_computes_m6(tmp_path):
    # contrast case for the open-run boundary above -- a CLOSED run
    # with matching cc_usage rows computes a real M6/M8.
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "boot-diet",
         "phase": None, "event": "run_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "boot-diet/SKILL.md"},
        {"ts": "2026-07-01T00:10:00", "run_id": "r1", "run_kind": "skill", "name": "boot-diet",
         "phase": None, "event": "run_end", "session_id": "s-1", "unit_kind": "boot_bytes",
         "unit_count": 100, "source": "boot-diet/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    sm.import_run_units(conn, path=p)
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 5, 0)), "projA",
                  agent_id=None, session_id="s-1", input_tokens=1000, output_tokens=500)
    conn2 = sqlite3.connect(db)
    out = sm._m6_m7_m8_m12(conn2, ["projA"], datetime(2026, 7, 1), datetime(2026, 7, 2))
    assert out["M6:skill:boot-diet"]["value"] is not None
    assert out["M8:skill:boot-diet"]["value"] == pytest.approx(
        out["M6:skill:boot-diet"]["value"] / 100)


def test_import_run_units_unit_count_zero_boundary_is_na(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "session-handoff",
         "phase": None, "event": "run_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "session-handoff/SKILL.md"},
        {"ts": "2026-07-01T00:05:00", "run_id": "r1", "run_kind": "skill", "name": "session-handoff",
         "phase": None, "event": "run_end", "session_id": "s-1", "unit_kind": "checks_passed",
         "unit_count": 0, "source": "session-handoff/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    sm.import_run_units(conn, path=p)
    row = conn.execute(
        "SELECT unit_count FROM run_units WHERE run_id='r1' AND phase IS NULL"
    ).fetchone()
    assert row == (0,)  # explicit zero preserved (not coerced to None)
    insert_cc_row(db, _utc_z_for_local(datetime(2026, 7, 1, 0, 2, 0)), "projA",
                  agent_id=None, session_id="s-1", input_tokens=500, output_tokens=200)
    conn2 = sqlite3.connect(db)
    out = sm._m6_m7_m8_m12(conn2, ["projA"], datetime(2026, 7, 1), datetime(2026, 7, 2))
    assert out["M8:skill:session-handoff"]["value"] is None  # deliberate: never a division by 0
    assert "unit_count" in out["M8:skill:session-handoff"]["reason"]


def test_import_run_units_unit_count_missing_beyond_boundary(tmp_path):
    # one step beyond zero: unit_count entirely absent on both lines.
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "next-task",
         "phase": None, "event": "run_start", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "next-task/SKILL.md"},
        {"ts": "2026-07-01T00:05:00", "run_id": "r1", "run_kind": "skill", "name": "next-task",
         "phase": None, "event": "run_end", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "next-task/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    sm.import_run_units(conn, path=p)
    row = conn.execute(
        "SELECT unit_count FROM run_units WHERE run_id='r1' AND phase IS NULL"
    ).fetchone()
    assert row == (None,)


def test_import_run_units_two_runs_same_skill_both_imported(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
        {"ts": "2026-07-01T00:10:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_end", "session_id": "s-1", "unit_kind": "sync_pairs",
         "unit_count": 80, "source": "kit-release/SKILL.md"},
        {"ts": "2026-07-05T00:00:00", "run_id": "r2", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_start", "session_id": "s-2", "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
        {"ts": "2026-07-05T00:10:00", "run_id": "r2", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_end", "session_id": "s-2", "unit_kind": "sync_pairs",
         "unit_count": 86, "source": "kit-release/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 2
    count = conn.execute(
        "SELECT COUNT(*) FROM run_units WHERE run_kind='skill' AND name='kit-release'"
        " AND phase IS NULL"
    ).fetchone()[0]
    assert count == 2


def test_import_run_units_phase_ts_end_chain(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "permission-audit",
         "phase": None, "event": "run_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "permission-audit/SKILL.md"},
        {"ts": "2026-07-01T00:01:00", "run_id": "r1", "run_kind": "skill", "name": "permission-audit",
         "phase": "1", "event": "phase_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "permission-audit/SKILL.md"},
        {"ts": "2026-07-01T00:02:00", "run_id": "r1", "run_kind": "skill", "name": "permission-audit",
         "phase": "2", "event": "phase_start", "session_id": "s-1", "unit_kind": None,
         "unit_count": None, "source": "permission-audit/SKILL.md"},
        {"ts": "2026-07-01T00:05:00", "run_id": "r1", "run_kind": "skill", "name": "permission-audit",
         "phase": None, "event": "run_end", "session_id": "s-1", "unit_kind": "prompts_analyzed",
         "unit_count": 40, "source": "permission-audit/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 1
    assert report["phase_rows"] == 2
    rows = {r[0]: (r[1], r[2]) for r in conn.execute(
        "SELECT phase, ts_start, ts_end FROM run_units WHERE run_id='r1' AND phase IS NOT NULL"
    ).fetchall()}
    assert rows["1"] == ("2026-07-01T00:01:00", "2026-07-01T00:02:00")
    assert rows["2"] == ("2026-07-01T00:02:00", "2026-07-01T00:05:00")


def test_import_run_units_phase_start_missing_phase_is_candidate(tmp_path):
    db = _run_units_db(tmp_path)
    p = tmp_path / "ru.jsonl"
    write_journal(p, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "run_start", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
        {"ts": "2026-07-01T00:01:00", "run_id": "r1", "run_kind": "skill", "name": "kit-release",
         "phase": None, "event": "phase_start", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "kit-release/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    report = sm.import_run_units(conn, path=p)
    assert report["level_rows"] == 1
    assert report["phase_rows"] == 0
    assert any("phase_start без phase" in c["error"] for c in report["candidates"])


def test_rebuild_imports_run_units_from_default_path(tmp_path):
    # the autouse _isolate_run_units_path fixture points sm.RUN_UNITS_PATH
    # at tmp_path/"run_units.jsonl" -- proves rebuild() wires the importer
    # in end-to-end, not just via an explicit `path=` override.
    db, deploys, deploy_project = _two_deploy_fixture(tmp_path)
    write_journal(sm.RUN_UNITS_PATH, [
        {"ts": "2026-07-01T00:00:00", "run_id": "r1", "run_kind": "skill", "name": "boot-diet",
         "phase": None, "event": "run_start", "session_id": None, "unit_kind": None,
         "unit_count": None, "source": "boot-diet/SKILL.md"},
        {"ts": "2026-07-01T00:10:00", "run_id": "r1", "run_kind": "skill", "name": "boot-diet",
         "phase": None, "event": "run_end", "session_id": None, "unit_kind": "boot_bytes",
         "unit_count": 100, "source": "boot-diet/SKILL.md"},
    ])
    conn = sqlite3.connect(db)
    stats = sm.rebuild(conn, deploys, deploy_project)
    assert stats["run_units"]["legal_absent"] is False
    assert stats["run_units"]["level_rows"] == 1
    assert conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0] == 1


# -----------------------------------------------------------------------
# calibration_runs_missing_from_registry (B4 point 4 -- the RUNS_WITHOUT_
# UNITS report data primitive; wiring into tools/spend_report.py itself
# is OUT OF B4's owns, see the handoff report).
# -----------------------------------------------------------------------
def test_calibration_runs_missing_from_registry_reports_calibrated_events(tmp_path):
    db = _run_units_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "calibrated", notes="n"),
        ev("2026-07-08T00:00:00", "calibrated", notes="n"),
    ])
    conn = sqlite3.connect(db)
    out = sm.calibration_runs_missing_from_registry(conn, deploys=[("d", str(j))])
    assert out == {"d": ["2026-07-01T00:00:00", "2026-07-08T00:00:00"]}


def test_calibration_runs_missing_from_registry_clean_when_registry_has_calibration(tmp_path):
    db = _run_units_db(tmp_path)
    # ts_start must PRECEDE the calibrated event's own ts (window end is
    # exclusive, half-open [start,end)) -- a real calibration run always
    # runs BEFORE the `calibrated` line that closes its window (item 3's
    # per-window fix, t-428).
    _insert_run_unit(db, run_id="rc", run_kind="calibration", name="calibration",
                      unit_kind=None, unit_count=None,
                      ts_start="2026-06-30T23:00:00", ts_end="2026-06-30T23:30:00")
    j = tmp_path / "j.jsonl"
    write_journal(j, [ev("2026-07-01T00:00:00", "calibrated", notes="n")])
    conn = sqlite3.connect(db)
    out = sm.calibration_runs_missing_from_registry(conn, deploys=[("d", str(j))])
    assert out == {}


def test_calibration_runs_missing_from_registry_per_window_not_all_or_nothing(tmp_path):
    """t-428 fix-batch item 3's own regression: TWO calibrated windows,
    a registry row covers only the FIRST -- pre-fix, ANY registry row
    anywhere silenced the WHOLE deploy's list; post-fix, the SECOND
    window (uncovered) must still be reported."""
    db = _run_units_db(tmp_path)
    _insert_run_unit(db, run_id="rc", run_kind="calibration", name="calibration",
                      unit_kind=None, unit_count=None,
                      ts_start="2026-06-25T00:00:00", ts_end="2026-06-25T00:30:00")
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "calibrated", notes="n"),   # window 1: covered
        ev("2026-07-08T00:00:00", "calibrated", notes="n"),   # window 2: NOT covered
    ])
    conn = sqlite3.connect(db)
    out = sm.calibration_runs_missing_from_registry(conn, deploys=[("d", str(j))])
    assert out == {"d": ["2026-07-08T00:00:00"]}


def test_calibration_runs_missing_from_registry_no_calibrated_events_is_clean(tmp_path):
    db = _run_units_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [ev("2026-07-01T00:00:00", "delegated", agent="x", model="sonnet",
                          task_id="t-1", category="c", worker_ref="agent:z", notes="n")])
    conn = sqlite3.connect(db)
    out = sm.calibration_runs_missing_from_registry(conn, deploys=[("d", str(j))])
    assert out == {}


def test_calibration_runs_missing_from_registry_unreadable_journal_skipped(tmp_path):
    db = _run_units_db(tmp_path)
    conn = sqlite3.connect(db)
    out = sm.calibration_runs_missing_from_registry(
        conn, deploys=[("ghost", str(tmp_path / "nope.jsonl"))]
    )
    assert out == {}


# -----------------------------------------------------------------------
# M13 (ПРОКСИ, always-present caveat)
# -----------------------------------------------------------------------
def test_m13_proxy_caveat_always_present():
    stages = [_stage(agent="scout", cost_usd=2.0, turns=4)]
    m = sm._m13(stages)
    assert m["value"] == pytest.approx(0.5)
    assert "ПРОКСИ" in m["reason"]


def test_m13_no_scout_stages():
    m = sm._m13([_stage(agent="builder")])
    assert m["value"] is None
    assert "ПРОКСИ" in m["reason"]


# -----------------------------------------------------------------------
# M14 + D7 (fable_counterfactual)
# -----------------------------------------------------------------------
def test_m14_no_escalations_boundary():
    m = sm._m14([_task(escalated_count=0)], [])
    assert m["value"] is None
    assert m["denominator_value"] == 0
    assert m["counterfactual_avg"] is None


def test_m14_with_escalation_and_counterfactual():
    tasks = [_task(task_id="t-1", cost_usd=8.0, escalated_count=1, unpriced_turns=0)]
    stages = [_stage(task_id="t-1", cost_usd=8.0, input_tokens=10000, output_tokens=2000)]
    m = sm._m14(tasks, stages)
    assert m["value"] == 8.0
    expected_cf = sm.fable_counterfactual(10000, 2000, 0, 0)
    assert m["counterfactual_avg"] == pytest.approx(expected_cf)


def test_d7_flags_when_counterfactual_cheaper():
    m14 = sm._metric(10.0, "escalated_tasks", 1, 0, None)
    m14["counterfactual_avg"] = 4.0
    d7 = sm._d7(m14)
    assert d7["value"] == 10.0
    assert d7["denominator_value"] == 4.0
    assert d7["value"] > d7["denominator_value"]  # эскалация дороже прямого


def test_d7_no_counterfactual_reason():
    m14 = sm._metric(reason="нет эскалаций в окне")
    m14["counterfactual_avg"] = None
    d7 = sm._d7(m14)
    assert d7["value"] is None


# -----------------------------------------------------------------------
# D5 (disjoint cc_usage columns, F-38 -- NOT gateway/metrics.py's formula)
# -----------------------------------------------------------------------
def test_d5_disjoint_formula():
    cc_rows = [_cc(1.0, input_tokens=100, output_tokens=50, cache_creation_tokens=10, cache_read_tokens=40)]
    m = sm._d5(cc_rows)
    assert m["value"] == pytest.approx(40 / 200)


def test_d5_zero_tokens_boundary():
    m = sm._d5([_cc(1.0, input_tokens=0, output_tokens=0, cache_creation_tokens=0, cache_read_tokens=0)])
    assert m["value"] is None


def test_d5_empty_window_e3():
    m = sm._d5([])
    assert m["value"] is None
    assert "пустое окно" in m["reason"]


# -----------------------------------------------------------------------
# D8 (silent-$0 count, always flagged when >0)
# -----------------------------------------------------------------------
def test_d8_counts_null_cost_rows():
    m = sm._d8([_cc(None), _cc(1.0), _cc(None)])
    assert m["value"] == 2.0
    assert m["denominator_value"] == 3.0


def test_d8_zero_boundary_is_legitimate_zero():
    m = sm._d8([_cc(1.0), _cc(2.0)])
    assert m["value"] == 0.0


def test_d8_empty_window_e3():
    m = sm._d8([])
    assert m["value"] is None


# -----------------------------------------------------------------------
# D9 (two labeled rows)
# -----------------------------------------------------------------------
def test_d9_cost_outside_tasks_share():
    cc_rows = [_cc(6.0, agent_id="a1"), _cc(4.0, agent_id="orphan")]
    stages = [_stage(agent_key="a1", measurable=1)]
    out = sm._d9([], stages, cc_rows)
    assert out["D9:cost_outside_tasks"]["value"] == pytest.approx(0.4)


def test_d9_stages_no_transcript_share():
    stages = [_stage(measurable=1), _stage(measurable=0)]
    out = sm._d9([], stages, [])
    assert out["D9:stages_no_transcript"]["value"] == pytest.approx(0.5)


def test_d9_empty_boundaries():
    out = sm._d9([], [], [])
    assert out["D9:cost_outside_tasks"]["value"] is None
    assert out["D9:stages_no_transcript"]["value"] is None


# -----------------------------------------------------------------------
# D1-D6 baseline deltas (Е3 -- no thresholds in v1)
# -----------------------------------------------------------------------
def test_baseline_delta_first_window_reason():
    m = sm._metric(5.0, "accepted_tasks", 2, 0, None)
    d = sm._baseline_delta(m, None)
    assert d["value"] == 5.0
    assert d["denominator_kind"] == "baseline"
    assert d["denominator_value"] is None
    assert "первое окно" in d["reason"]


def test_baseline_delta_with_prev_value():
    m = sm._metric(5.0, "accepted_tasks", 2, 0, None)
    d = sm._baseline_delta(m, 3.0)
    assert d["denominator_value"] == pytest.approx(2.0)
    assert d["reason"] is None


def test_baseline_delta_none_value_propagates_reason():
    m = sm._metric(reason="0 принятых задач в окне")
    d = sm._baseline_delta(m, None)
    assert d["value"] is None
    assert d["reason"] == "0 принятых задач в окне"


def test_compute_detectors_mirrors_and_d4_per_tier():
    metrics = {
        "M1": sm._metric(3.0), "M2": sm._metric(2.0), "M3": sm._metric(0.1), "M4": sm._metric(0.66),
        "M10:sonnet": sm._metric(1.5), "M10:opus": sm._metric(4.0),
    }
    out = sm._compute_detectors(metrics, {"M4": 0.60, "M10:sonnet": 1.0})
    assert out["D1"]["denominator_value"] == pytest.approx(0.06)
    assert out["D2"]["value"] == 0.1
    assert out["D3"]["value"] == 2.0
    assert out["D6"]["value"] == 3.0
    assert out["D4:sonnet"]["denominator_value"] == pytest.approx(0.5)
    assert out["D4:opus"]["reason"] == "первое окно (нет прошлой точки ряда)"


# -----------------------------------------------------------------------
# compute_all_window_metrics / compute_window_series orchestration
# -----------------------------------------------------------------------
def _calibrated_fixture(tmp_path, deploy_key="shtab"):
    db = make_db(tmp_path)
    j = tmp_path / "logs" / "routing-log.jsonl"
    j.parent.mkdir(parents=True)
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:05:00", "accepted", agent="builder", model="sonnet",
           task_id="t-1", by="fable", category="implementation", witness="w", notes="n"),
        ev("2026-07-05T00:00:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="1"),
    ])
    insert_cc_row(db, "2026-07-01T00:00:30Z", "projA", agent_id="a1", dedupe_suffix="1")
    deploys = [(deploy_key, str(j))]
    deploy_project = {deploy_key: "projA"}
    return db, deploys, deploy_project


def test_compute_all_window_metrics_smoke(tmp_path):
    db, deploys, deploy_project = _calibrated_fixture(tmp_path)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    window = sm.resolve_last_calibrated_window(conn, "shtab", deploys)
    metrics = sm.compute_all_window_metrics(conn, window, deploy_project, deploys)
    assert metrics["M1"]["value"] == pytest.approx(1.0)
    assert "M4b:claude-sonnet-5" in metrics


def test_compute_window_series_idempotent(tmp_path):
    db, deploys, deploy_project = _calibrated_fixture(tmp_path)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    dump1 = sm._dump_window_series(conn)
    sm.compute_window_series(conn, deploys, deploy_project)
    dump2 = sm._dump_window_series(conn)
    assert dump1 == dump2
    assert "window_series" not in dump1  # sanity: this dump has no table-name header line
    rows = conn.execute("SELECT COUNT(*) FROM window_series").fetchone()[0]
    assert rows > 0


def test_compute_window_series_covers_both_scopes(tmp_path):
    db, deploys, deploy_project = _calibrated_fixture(tmp_path)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    scopes = {r[0] for r in conn.execute("SELECT DISTINCT scope FROM window_series")}
    assert scopes == {"deploy", "all"}
    kinds = {r[0].split(":")[1] for r in conn.execute("SELECT DISTINCT window_id FROM window_series")}
    assert "calibrated" in kinds or "monthly" in kinds


def test_compute_window_series_empty_deploy_no_journal_e14(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    deploys = [("ghost", str(tmp_path / "nope.jsonl"))]
    deploy_project = {"ghost": "projGhost"}
    result = sm.compute_window_series(conn, deploys, deploy_project)
    assert result["calibrated_windows"]["ghost"] == 0
    # monthly all-scope series still gets written (current-month row via `now`)
    rows = conn.execute("SELECT COUNT(*) FROM window_series WHERE scope='all'").fetchone()[0]
    assert rows > 0


def test_cli_compute_window_last_json(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project = _calibrated_fixture(tmp_path, deploy_key="shtab")
    monkeypatch.setattr(sm, "DEPLOYS", deploys)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", deploy_project)
    rc = sm.main(["--compute-window", "last", "--json", "--skip-import", "--db", str(db)])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "calibrated_last_shtab" in data
    assert "monthly_all_scope_last" in data
    assert data["calibrated_last_shtab"]["metrics"]
    m1_rows = [r for r in data["calibrated_last_shtab"]["metrics"] if r["metric_key"] == "M1"]
    assert m1_rows and m1_rows[0]["value"] == pytest.approx(1.0)


def test_cli_compute_window_last_text_smoke(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project = _calibrated_fixture(tmp_path, deploy_key="shtab")
    monkeypatch.setattr(sm, "DEPLOYS", deploys)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", deploy_project)
    rc = sm.main(["--compute-window", "last", "--skip-import", "--db", str(db)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "calibrated_last_shtab" in out
    assert "M1" in out


def test_cli_compute_window_no_calibrated_windows_reports_error(tmp_path, monkeypatch, capsys):
    db = make_db(tmp_path)
    j = tmp_path / "logs" / "routing-log.jsonl"
    j.parent.mkdir(parents=True)
    write_journal(j, [])
    deploys = [("shtab", str(j))]
    deploy_project = {"shtab": "projA"}
    monkeypatch.setattr(sm, "DEPLOYS", deploys)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", deploy_project)
    rc = sm.main(["--compute-window", "last", "--json", "--skip-import", "--db", str(db)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "error" in data["calibrated_last_shtab"]
