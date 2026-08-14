"""Tests for tools/spend_report.py (B3, spend-analytics spec 2026-08-13).

Isolation pattern -- same as tools/test_spend_model.py: fresh tmp sqlite
DB + synthetic journal fixtures; every call passes explicit --db /
monkeypatched spend_model.DEPLOYS+DEPLOY_PROJECT (no test touches the
real 3-deploy config or the real gateway/requests.db). --skip-import is
used throughout (no real ~/.claude/projects scan in tests).

Run: python -m pytest tools/test_spend_report.py -q
"""
import json
import os
import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest

import spend_model as sm
import spend_report as sr
import usage_report


# ---------------------------------------------------------------------
# Fixture helpers (mirrors tools/test_spend_model.py's own conventions)
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
                   session_id="s-1", dedupe_suffix=None, force_unpriced=False):
    if force_unpriced:
        cost = None
    else:
        cost, _ = usage_report.accounted_cost(model, input_tokens, output_tokens, 0, 0)
    dedupe = f"{session_id}:{dedupe_suffix or ts}:{agent_id}"
    conn = sqlite3.connect(db_file)
    conn.execute(
        """
        INSERT INTO cc_usage
            (ts, project, session_id, turn_index, model, input_tokens, output_tokens,
             cache_creation_tokens, cache_read_tokens, accounted_cost_usd, traffic_kind,
             is_sidechain, agent_id, agent_type, dedupe_key)
        VALUES (?, ?, ?, 0, ?, ?, ?, 0, 0, ?, 'real', ?, ?, NULL, ?)
        """,
        (ts, project, session_id, model, input_tokens, output_tokens, cost, is_sidechain,
         agent_id, dedupe),
    )
    conn.commit()
    conn.close()


def _three_task_fixture(tmp_path, deploy_key="shtab"):
    """3 accepted tasks (sonnet/opus/fable-drift), 1 calibrated event
    (window 1, partial) -- basis for R4.1/R4.2/R4.3 smoke tests and the
    live M10/D4-collapse check."""
    db = make_db(tmp_path)
    j = tmp_path / "logs" / "routing-log.jsonl"
    j.parent.mkdir(parents=True)
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:05:00", "accepted", agent="builder", model="sonnet",
           task_id="t-1", by="fable", category="implementation", witness="w", notes="n"),
        ev("2026-07-01T01:00:00", "delegated", agent="critic", model="opus",
           task_id="t-2", category="review", worker_ref="agent:a2", notes="n"),
        ev("2026-07-01T01:05:00", "accepted", agent="critic", model="opus",
           task_id="t-2", by="fable", category="review", witness="w", notes="n"),
        ev("2026-07-01T02:00:00", "delegated", agent="lead", model="fable-5",
           task_id="t-3", category="calibration", worker_ref="agent:a3", notes="n"),
        ev("2026-07-01T02:05:00", "accepted", agent="lead", model="fable-5",
           task_id="t-3", by="fable", category="calibration", witness="w", notes="n"),
        ev("2026-07-05T00:00:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="1"),
    ])
    insert_cc_row(db, "2026-07-01T00:00:30Z", "projA", agent_id="a1", model="claude-sonnet-5",
                  dedupe_suffix="1")
    insert_cc_row(db, "2026-07-01T01:00:30Z", "projA", agent_id="a2", model="claude-opus-5",
                  dedupe_suffix="2")
    insert_cc_row(db, "2026-07-01T02:00:30Z", "projA", agent_id="a3", model="claude-fable-5",
                  dedupe_suffix="3")
    # orphan sidechain (E5) + one unpriced turn (E6/O3)
    insert_cc_row(db, "2026-07-01T02:10:00Z", "projA", agent_id="orphan1", is_sidechain=1,
                  dedupe_suffix="4")
    insert_cc_row(db, "2026-07-01T02:20:00Z", "projA", agent_id="a1", model="unknown-model-xyz",
                  force_unpriced=True, dedupe_suffix="5")
    deploys = [(deploy_key, str(j))]
    deploy_project = {deploy_key: "projA"}
    return db, deploys, deploy_project, j


def _patch_deploys(monkeypatch, deploys, deploy_project):
    monkeypatch.setattr(sm, "DEPLOYS", deploys)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", deploy_project)


# ---------------------------------------------------------------------
# Isolation from the live logs/run_units.jsonl registry (fix-batch
# calibration #7, 2026-08-14): every rebuild() call in this module goes
# through the tools/conftest.py autouse fixture, which redirects
# spend_model.RUN_UNITS_PATH to tmp_path for the duration of each test.
# A silent fixture is indistinguishable from a broken one (3г) -- this
# test names the isolation explicitly instead of relying on every other
# test in the module to prove it indirectly.
# ---------------------------------------------------------------------
def test_run_units_path_is_isolated_under_tmp_path(tmp_path):
    assert sm.RUN_UNITS_PATH == tmp_path / "run_units.jsonl"
    assert not sm.RUN_UNITS_PATH.exists()


# ---------------------------------------------------------------------
# resolve_window / _resolve_prev_window_id
# ---------------------------------------------------------------------
def test_resolve_window_last_no_calibrated_events_is_named_reason(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    conn = sqlite3.connect(db)
    window_id, err = sr.resolve_window(conn, "shtab", "last")
    assert window_id is None
    assert "нет окон" in err


def test_resolve_window_explicit_id_not_found(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    window_id, err = sr.resolve_window(conn, "shtab", "x:calibrated:1")
    assert window_id is None
    assert "не найдено" in err


def test_resolve_prev_window_id_first_window_is_none(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    window_id, err = sr.resolve_window(conn, "shtab", "last")
    assert err is None
    row = sr._window_metric_rows(conn, window_id)[0]
    assert sr._resolve_prev_window_id(conn, row) is None


def test_resolve_prev_window_id_custom_window_never_matches(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    fake_row = {"window_id": "custom:shtab:open:open"}
    assert sr._resolve_prev_window_id(conn, fake_row) is None


# ---------------------------------------------------------------------
# build_r4_1 -- "н/д (первое окно)" for the FIRST window (accept key 1)
# ---------------------------------------------------------------------
def test_r4_1_first_window_past_is_na_not_zero(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    window_id, err = sr.resolve_window(conn, "shtab", "last")
    assert err is None
    metric_rows = sr._window_metric_rows(conn, window_id)
    window_row = metric_rows[0]
    r1 = sr.build_r4_1(conn, window_row, metric_rows)
    m1_row = next(r for r in r1["rows"] if r["metric"] == "M1")
    assert m1_row["past_available"] is False
    assert m1_row["delta"] is None
    # never a silent 0 -- the flag text must say so explicitly.
    d1_row = next(r for r in r1["rows"] if r["metric"] == "D1")
    assert "первое окно" in d1_row["flag"] or d1_row["flag"] == "" or "н/д" in (d1_row["flag"] or "")


def test_flag_for_row_plain_metric_has_no_flag():
    row = sm._metric(3.0)
    assert sr._flag_for_row("M1", row, None) == ""


def test_flag_for_row_d7_verdict_when_escalation_costlier():
    row = sm._metric(10.0, "absolute", 4.0, 0, None)
    assert "ФЛАГ" in sr._flag_for_row("D7", row, None)


def test_flag_for_row_d7_in_norm_when_not_costlier():
    row = sm._metric(3.0, "absolute", 4.0, 0, None)
    assert sr._flag_for_row("D7", row, None) == "в норме (контрфакт не дешевле факта)"


def test_flag_for_row_d8_flags_on_any_positive():
    assert "ФЛАГ" in sr._flag_for_row("D8", sm._metric(1.0, "absolute", 3.0, 0, None), None)
    assert sr._flag_for_row("D8", sm._metric(0.0, "absolute", 3.0, 0, None), None) == "чисто"


def test_flag_for_row_undetermined_threshold_detector_tags_preliminary():
    row = sm._metric(0.5)
    prev = {"value": 0.4}
    flag = sr._flag_for_row("D5", row, prev)
    assert "ПРЕДВАРИТЕЛЬНЫЙ ПОРОГ" in flag
    assert "↑" in flag


# ---------------------------------------------------------------------
# M10/D4 collapse -- live pipeline check (finding 8в.1, accept key 2)
# ---------------------------------------------------------------------
def test_m10_collapses_fable_family_after_full_pipeline_run(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    keys = {r[0] for r in conn.execute(
        "SELECT DISTINCT metric_key FROM window_series WHERE metric_key LIKE 'M10:%'"
    )}
    assert "M10:fable" in keys
    assert "M10:fable-5" not in keys
    assert "M10:claude-fable-5" not in keys


# ---------------------------------------------------------------------
# build_r4_2 -- top-N + D-строки
# ---------------------------------------------------------------------
def test_r4_2_top_tasks_and_detector_rows(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    window_id, _err = sr.resolve_window(conn, "shtab", "last")
    metric_rows = sr._window_metric_rows(conn, window_id)
    window_row = metric_rows[0]
    r2 = sr.build_r4_2(conn, window_row, metric_rows, top_n=10, trend_k=6)
    assert len(r2["top_tasks"]) == 3
    assert all(t["share"] is not None for t in r2["top_tasks"])
    assert any(d["sink"] == "D8" for d in r2["detectors"])


def test_top_n_boundary_exact_and_plus_one(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    window_id, _err = sr.resolve_window(conn, "shtab", "last")
    metric_rows = sr._window_metric_rows(conn, window_id)
    window_row = metric_rows[0]
    # exactly 3 sinks in the fixture
    r_exact = sr.build_r4_2(conn, window_row, metric_rows, top_n=3, trend_k=6)
    assert len(r_exact["top_tasks"]) == 3
    r_plus1 = sr.build_r4_2(conn, window_row, metric_rows, top_n=4, trend_k=6)
    assert len(r_plus1["top_tasks"]) == 3  # no more than actually exist -- no crash


# ---------------------------------------------------------------------
# build_r4_3 -- ALWAYS built, empty subsections say "чисто" explicitly
# ---------------------------------------------------------------------
def test_r4_3_always_built_even_without_calibrated_windows(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    conn = sqlite3.connect(db)
    sm.rebuild(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
    sm.compute_window_series(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
    report = sr.build_report(conn, "shtab", "last", True, 10, None, 6)
    assert "window_error" in report
    assert "r4_3" in report  # health section present regardless


def test_r4_3_empty_subsections_say_chisto(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    r3 = sr.build_r4_3(conn, "shtab")
    text = sr.render_text({"r4_3": r3, "window_error": "не проверяется в этом тесте"}, "shtab")
    assert "чисто" in text or "реестр пуст" in text


def test_r4_3_runs_without_units_empty_registry_literal_reason(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    r3 = sr.build_r4_3(conn, "shtab")
    assert r3["runs_without_units"]["status"] == "реестр пуст, метрики скиллов н/д"
    # B6 wiring (calibration_runs_missing_from_registry, B4 handoff
    # question): the ADDITIVE field is present alongside the literal
    # status regardless -- the fixture has a calibrated event and a
    # totally empty run_units registry, so this deploy's ONE calibrated
    # window is named.
    assert r3["runs_without_units"]["calibration_registry_gaps"]["shtab"] == ["shtab:calibrated:1"]


def test_r4_3_runs_without_units_calibrated_present_no_calibration_rows_names_window(tmp_path, monkeypatch):
    """DoD B6 accept key 4's own fixture wording: "calibrated есть,
    строк calibration нет -> секция называет окно" -- this time with
    the registry NON-empty (>=1 unrelated run_kind row present, total>0)
    so the code path goes through the `dead`-computing branch, not the
    total==0 early return, and the gap is still surfaced."""
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm._ensure_schema(conn)
    conn.execute(
        "INSERT INTO run_units (run_id, run_kind, name, phase, ts_start, ts_end,"
        " session_id, unit_kind, unit_count, source) VALUES"
        " ('r-1', 'boot-diet', 'boot-diet', NULL, '2026-07-01T00:00:00',"
        " '2026-07-01T00:10:00', 's-1', 'bytes', 100, 'test')"
    )
    conn.commit()
    r3 = sr.build_r4_3(conn, "shtab")
    rwu = r3["runs_without_units"]
    assert rwu["status"] != "реестр пуст, метрики скиллов н/д"  # total>0 branch taken
    assert rwu["calibration_registry_gaps"]["shtab"] == ["shtab:calibrated:1"]
    text = sr.render_text({"r4_3": r3, "window_error": "не проверяется в этом тесте"}, "shtab")
    assert "shtab:calibrated:1" in text


def test_r4_3_unparsable_journal_line_is_surfaced(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
        "",  # empty line -- must be skipped silently, not a candidate
        "{not valid json!!!",
    ])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    conn = sqlite3.connect(db)
    sm.rebuild(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
    r3 = sr.build_r4_3(conn, "shtab")
    assert "shtab" in r3["unparsable_journal_lines"]
    assert len(r3["unparsable_journal_lines"]["shtab"]) == 1
    assert r3["unparsable_journal_lines"]["shtab"][0]["line"] == 3


def test_r4_3_wires_shared_key_split_and_invariant(tmp_path, monkeypatch):
    """t-428 fix-batch item 0 wiring into R4.3."""
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    r3 = sr.build_r4_3(conn, "shtab")
    assert r3["shared_key_split"] == {"stages": 0, "keys": 0, "cost_usd": 0.0}  # fixture has no shared keys
    assert r3["agent_id_session_invariant"] == {"violations": []}


# ---------------------------------------------------------------------
# t-428 fix-batch item 3: missing_calibrated_windows snapshot fix --
# pre-fix, main()'s own compute_window_series() ALWAYS ran right before
# build_report(), so the section structurally never fired; the snapshot
# param restores real detection.
# ---------------------------------------------------------------------
def test_missing_calibrated_windows_uses_snapshot_when_given(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    # NO rebuild()/compute_window_series() yet -- window_series is empty.
    # A snapshot taken NOW (before anything is computed) is also empty,
    # so passing it explicitly must still report the gap (same as the
    # live-table fallback when no snapshot is given).
    snap = sr.snapshot_calibrated_window_ids(conn)
    assert snap == set()
    missing = sr._missing_calibrated_windows(conn, ["shtab"], snap)
    assert missing == {"shtab": ["shtab:calibrated:1"]}


def test_missing_calibrated_windows_snapshot_frozen_even_after_recompute(tmp_path, monkeypatch):
    """The core of the fix: even though compute_window_series() below
    backfills the gap, a snapshot taken BEFORE it still reports the
    window as having been missing at the run's START."""
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    snap = sr.snapshot_calibrated_window_ids(conn)  # empty, taken BEFORE recompute
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)  # NOW window_series is fully populated
    live_missing = sr._missing_calibrated_windows(conn, ["shtab"])  # no snapshot -> live table
    assert live_missing == {}  # structurally never fires post-recompute (the pre-fix bug)
    snapshot_missing = sr._missing_calibrated_windows(conn, ["shtab"], snap)
    assert snapshot_missing == {"shtab": ["shtab:calibrated:1"]}  # snapshot restores detection


def test_snapshot_calibrated_window_ids_reflects_prior_state(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    snap = sr.snapshot_calibrated_window_ids(conn)
    assert "shtab:calibrated:1" in snap


# ---------------------------------------------------------------------
# t-428 fix-batch item 4: RUNS_WITHOUT_UNITS session_id/dead split.
# ---------------------------------------------------------------------
def test_runs_without_units_no_session_id_not_counted_as_dead(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm._ensure_schema(conn)
    conn.execute(
        "INSERT INTO run_units (run_id, run_kind, name, phase, ts_start, ts_end,"
        " session_id, unit_kind, unit_count, source) VALUES"
        " ('r-nosid', 'skill', 'next-task', NULL, '2026-07-01T00:00:00',"
        " '2026-07-01T00:10:00', NULL, NULL, 1, 'test')"
    )
    conn.commit()
    r3 = sr.build_r4_3(conn, "shtab")
    rwu = r3["runs_without_units"]
    assert not any(d["run_id"] == "r-nosid" for d in rwu["dead"])
    assert any(d["run_id"] == "r-nosid" for d in rwu["no_session_id"])


def test_runs_without_units_open_run_no_end_is_dead(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm._ensure_schema(conn)
    conn.execute(
        "INSERT INTO run_units (run_id, run_kind, name, phase, ts_start, ts_end,"
        " session_id, unit_kind, unit_count, source) VALUES"
        " ('r-open', 'skill', 'kit-release', NULL, '2026-07-01T00:00:00',"
        " NULL, 's-1', NULL, NULL, 'test')"
    )
    conn.commit()
    r3 = sr.build_r4_3(conn, "shtab")
    rwu = r3["runs_without_units"]
    dead = next(d for d in rwu["dead"] if d["run_id"] == "r-open")
    assert "run_end" in dead["reason"]
    assert not any(d["run_id"] == "r-open" for d in rwu["no_session_id"])


# ---------------------------------------------------------------------
# t-428 fix-batch item 5: "из них <skill>: $X" near M4b.
# ---------------------------------------------------------------------
def test_skill_cost_breakdown_only_lists_skills_present_in_window():
    metric_rows = [
        {"metric_key": "M4", "value": 1.0, "reason": None},
        {"metric_key": "M6:skill:boot-diet", "value": 3.5, "reason": None},
        {"metric_key": "M6:calibration:calibration", "value": 1.0, "reason": None},  # NOT a skill
    ]
    out = sr._skill_cost_breakdown(metric_rows)
    assert out == [{"name": "boot-diet", "value": 3.5, "reason": None}]


def test_skill_cost_breakdown_empty_when_no_skill_ran():
    assert sr._skill_cost_breakdown([{"metric_key": "M4", "value": 1.0, "reason": None}]) == []


def test_build_r4_1_carries_skill_breakdown_key(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    window_id, _err = sr.resolve_window(conn, "shtab", "last")
    metric_rows = sr._window_metric_rows(conn, window_id)
    window_row = metric_rows[0]
    r1 = sr.build_r4_1(conn, window_row, metric_rows)
    assert r1["skill_breakdown"] == []  # no run_units registry in this fixture -- nothing printed


# ---------------------------------------------------------------------
# JSON validity with None values (accept key 1)
# ---------------------------------------------------------------------
def test_json_output_valid_with_none_values(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window", "last", "--compare", "prev", "--json", "--skip-import",
                  "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)  # must not raise -- proves None-safety
    assert "r4_1" in data
    assert any(row["past_available"] is False for row in data["r4_1"]["rows"])


def test_text_output_smoke(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window", "last", "--compare", "prev", "--skip-import",
                  "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "R4.1" in out and "R4.2" in out and "R4.3" in out
    assert "первое окно" in out


# =======================================================================
# ADVERSARIAL BATTERY (R11, section 6 of the spec, verbatim DoD list)
# =======================================================================
def test_battery_invalid_iso_window_start_exits_2(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window-start", "not-a-date", "--skip-import", "--db", str(db)])
    assert rc == 2


def test_battery_valid_iso_window_start_beyond_boundary_does_not_exit_2(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window-start", "2026-07-01T00:00:00", "--window-end", "2026-07-02T00:00:00",
                  "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


def test_battery_start_after_end_refuses(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window-start", "2026-07-02T00:00:00", "--window-end", "2026-07-01T00:00:00",
                  "--skip-import", "--db", str(db)])
    assert rc == 2


def test_battery_start_equals_end_boundary_is_legal(tmp_path, monkeypatch):
    # AT the boundary (start == end, not >) -- a legal (if empty) window.
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window-start", "2026-07-01T00:00:00", "--window-end", "2026-07-01T00:00:00",
                  "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


def test_battery_top_zero_refuses(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--top", "0", "--skip-import", "--db", str(db)])
    assert rc == 2


def test_battery_top_negative_refuses(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--top", "-1", "--skip-import", "--db", str(db)])
    assert rc == 2


def test_battery_top_one_boundary_beyond_zero_is_legal(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--top", "1", "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


def test_battery_top_huge_does_not_crash(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--top", str(10**9), "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


def test_battery_top_exact_sink_count_and_plus_one_cli(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc1 = sr.main(["--top", "3", "--json", "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc1 == 0
    data1 = json.loads(capsys.readouterr().out)
    assert len(data1["r4_2"]["top_tasks"]) == 3
    rc2 = sr.main(["--top", "4", "--json", "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc2 == 0
    data2 = json.loads(capsys.readouterr().out)
    assert len(data2["r4_2"]["top_tasks"]) == 3


def test_battery_empty_journal_stays_alive(tmp_path, monkeypatch, capsys):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "R4.3" in out  # health section still prints


def test_battery_empty_line_and_one_unparsable_line_prints_candidate_stays_alive(
        tmp_path, monkeypatch, capsys):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
        "",
        "{not valid json!!!",
    ])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "line 3" in out  # candidate printed (empty line skipped, not counted)


def test_battery_cp1251_console_does_not_crash(tmp_path, monkeypatch):
    """Class t-408: PYTHONIOENCODING=cp1251 -- run as a REAL subprocess
    (the module's own reconfigure() only fires once at import time in a
    fresh interpreter, so an in-process call would not exercise it) --
    DEPLOYS/DEPLOY_PROJECT monkeypatching does NOT cross the subprocess
    boundary, so this test's --deploy shtab resolves via the REAL
    sm.DEPLOY_PROJECT mapping; a cc_usage row under that REAL project
    name is added so the t-428 item-6 E10 guard does not refuse (this
    db already has non-empty cc_usage under "projA" for OTHER
    assertions -- E10 fires precisely because some project has rows and
    the resolved one doesn't, unless this row is present)."""
    db, deploys, deploy_project, j = _three_task_fixture(tmp_path)
    insert_cc_row(db, "2026-07-01T00:00:30Z", sm.DEPLOY_PROJECT["shtab"], agent_id="real-shtab-a1",
                  model="claude-sonnet-5", dedupe_suffix="real-shtab-1")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1251"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent)
    script = str(Path(__file__).resolve().parent / "spend_report.py")
    proc = subprocess.run(
        [sys.executable, script, "--window", "last", "--compare", "prev", "--skip-import",
         "--db", str(db), "--deploy", "shtab"],
        cwd=str(Path(__file__).resolve().parent), capture_output=True, env=env, timeout=60,
    )
    # decode explicitly as utf-8 (what the child's own reconfigure()
    # produces, per module docstring "class t-408") -- the PARENT
    # process's own locale-preferred codepage (cp1251 on this machine)
    # is irrelevant here and must not be used to decode the child's
    # output (that would test the harness, not the child).
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"


def test_battery_out_path_with_spaces(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    out_dir = tmp_path / "dir with spaces"
    out_path = out_dir / "report.txt"
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab", "--out", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    assert "R4.3" in out_path.read_text(encoding="utf-8")


def test_battery_db_without_cc_usage_table_exits_2(tmp_path, monkeypatch):
    db_file = tmp_path / "empty.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()
    rc = sr.main(["--skip-import", "--db", str(db_file)])
    assert rc == 2


def test_battery_db_with_cc_usage_table_passes(tmp_path, monkeypatch):
    db = make_db(tmp_path)  # has cc_usage (empty) -- legitimate bootstrap state, stays alive
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


# ---------------------------------------------------------------------
# t-428 fix-batch item 6: E10 loud refusal, SCOPED (sm.resolve_project_
# or_refuse_if_data_elsewhere) -- boundary AT (0 rows for the resolved
# project, but OTHER projects on this "machine" have data -> refuse)
# and BEYOND (>=1 row for the resolved project -> passes).
# ---------------------------------------------------------------------
def test_battery_e10_zero_rows_for_project_others_have_data_refuses(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "someOtherProject", agent_id="a1")
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 2


def test_battery_e10_beyond_boundary_project_has_rows_passes(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


def test_battery_e10_totally_empty_db_is_bootstrap_not_refused(tmp_path, monkeypatch):
    """Control: cc_usage has ZERO rows for EVERY project -- the
    legitimate first-run state, must stay alive (this is what
    test_battery_db_with_cc_usage_table_passes already covers; repeated
    here explicitly as the E10 predicate's own negative control)."""
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0


def test_battery_e10_deploy_all_skips_the_check(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    insert_cc_row(db, "2026-06-01T00:00:00Z", "someOtherProject", agent_id="a1")
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "all"])
    assert rc == 0


# ---------------------------------------------------------------------
# --deploy=all / --series / --out (misc R4.4 coverage)
# ---------------------------------------------------------------------
def test_deploy_all_uses_monthly_all_scope(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window", "last", "--skip-import", "--db", str(db), "--deploy", "all", "--json"])
    assert rc == 0


def test_series_flag_returns_points(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--window", "last", "--series", "M1", "--last", "6", "--json",
                  "--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["series"]["metric"] == "M1"
    assert len(data["series"]["points"]) >= 1


def test_out_flag_writes_file_not_stdout(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    out_path = tmp_path / "report.json"
    rc = sr.main(["--json", "--skip-import", "--db", str(db), "--deploy", "shtab",
                  "--out", str(out_path)])
    assert rc == 0
    assert out_path.exists()
    json.loads(out_path.read_text(encoding="utf-8"))  # valid JSON on disk


# ---------------------------------------------------------------------
# t-428 fix-batch item 6: full-pipeline runtime print (E11 threshold on
# the SUM, not just import) -- boundary AT 60s (no marker) and BEYOND
# (>60s -> marker), plus the print is now UNCONDITIONAL.
# ---------------------------------------------------------------------
def test_full_runtime_printed_unconditionally_under_60s(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "полный прогон" in err
    assert "E11" not in err


def test_full_runtime_e11_boundary_at_60s_no_marker(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    calls = {"n": 0}
    real_time = sr.time.time

    def fake_time():
        calls["n"] += 1
        return 1000.0 if calls["n"] == 1 else 1060.0  # exactly 60.0s elapsed

    monkeypatch.setattr(sr.time, "time", fake_time)
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "60.0" in err
    assert "E11" not in err


def test_full_runtime_e11_boundary_beyond_60s_has_marker(tmp_path, monkeypatch, capsys):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    calls = {"n": 0}

    def fake_time():
        calls["n"] += 1
        return 1000.0 if calls["n"] == 1 else 1060.1  # one tenth of a second beyond

    monkeypatch.setattr(sr.time, "time", fake_time)
    rc = sr.main(["--skip-import", "--db", str(db), "--deploy", "shtab"])
    assert rc == 0
    err = capsys.readouterr().err
    assert "E11" in err
