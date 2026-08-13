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
import sqlite3
from datetime import datetime, timedelta

import pytest

import spend_model as sm
import token_usage_stats as tus
import usage_report


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
    # boundary: zero cc_usage rows at all -- invariant (0, None) must
    # still match before/after, no crash.
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    conn = sqlite3.connect(db)
    before = sm.cc_usage_invariant(conn)
    sm.rebuild(conn, [("d", str(j))], {"d": "projX"})
    after = sm.cc_usage_invariant(conn)
    assert before == after == {"count": 0, "sum": None}


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
