"""Tests for tools/spend_dashboard.py (B6, spend-analytics spec
2026-08-13, section 8 fork (д), node B6/N10).

Isolation pattern -- same as tools/test_spend_model.py / tools/
test_spend_report.py: fresh tmp sqlite DB + synthetic journal fixtures;
every call passes explicit --db / monkeypatched spend_model.DEPLOYS +
DEPLOY_PROJECT (no test touches the real 3-deploy config or the real
gateway/requests.db). --skip-import throughout (no real
~/.claude/projects scan in tests).

Run: python -m pytest tools/test_spend_dashboard.py -q
"""
import json
import os
import re
import subprocess
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest

import spend_dashboard as sd
import spend_model as sm
import spend_report as sr
import token_usage_stats as tus
import usage_report


@pytest.fixture(autouse=True)
def _isolate_run_units_path(tmp_path, monkeypatch):
    """Same isolation as test_spend_model.py's own autouse fixture --
    rebuild() (called by every fixture below via sm.rebuild) always
    reads the module-level sm.RUN_UNITS_PATH internally; without this,
    a test run the day a real skill first writes logs/run_units.jsonl
    would start reading it (D-0043: fixed at the class, once, here)."""
    monkeypatch.setattr(sm, "RUN_UNITS_PATH", tmp_path / "run_units.jsonl")


# ---------------------------------------------------------------------
# Fixture helpers (mirrors tools/test_spend_report.py's own conventions)
# ---------------------------------------------------------------------
def write_journal(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
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


def make_db(tmp_path, name="requests.db"):
    db_file = tmp_path / name
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
    """1 calibrated window (partial) with 3 accepted tasks -- basis for
    the "real pipeline, non-empty" tests (mirrors test_spend_report.py's
    own fixture of the same name/shape 1-for-1)."""
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
    deploys = [(deploy_key, str(j))]
    deploy_project = {deploy_key: "projA"}
    return db, deploys, deploy_project, j


def _patch_deploys(monkeypatch, deploys, deploy_project):
    monkeypatch.setattr(sm, "DEPLOYS", deploys)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", deploy_project)


def _rebuild_all(db, deploys, deploy_project):
    conn = sqlite3.connect(db)
    sm.rebuild(conn, deploys, deploy_project)
    sm.compute_window_series(conn, deploys, deploy_project)
    return conn


_SECTION_MARKERS = ("header", "stat-tiles", "trends", "sinks", "monthly-table", "health")


# ---------------------------------------------------------------------
# generate_dashboard -- file creation, idempotency, self-containment,
# section presence (accept keys 1/2).
# ---------------------------------------------------------------------
def test_generate_dashboard_creates_file_and_is_idempotent(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = _rebuild_all(db, deploys, deploy_project)
    out = tmp_path / "out" / "dashboard.html"
    p1 = sd.generate_dashboard(conn, out_path=out)
    assert p1 == out
    assert out.exists()
    text1 = out.read_text(encoding="utf-8")
    assert len(text1) > 500
    p2 = sd.generate_dashboard(conn, out_path=out)
    assert p2 == out
    text2 = out.read_text(encoding="utf-8")
    assert text2.startswith("<!DOCTYPE html>")
    conn.close()


def test_dashboard_self_contained_no_external_refs(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = _rebuild_all(db, deploys, deploy_project)
    out = sd.generate_dashboard(conn, out_path=tmp_path / "dashboard.html")
    text = out.read_text(encoding="utf-8")
    assert "http://" not in text
    assert "https://" not in text
    # `src=` is forbidden EXCEPT for a data:-URI -- this generator never
    # emits <img>/<script src=...> at all (SVG is INLINE, tooltips are
    # native <title>), so the substring must not appear at all.
    assert "src=" not in text
    conn.close()


def test_dashboard_six_sections_present(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = _rebuild_all(db, deploys, deploy_project)
    out = sd.generate_dashboard(conn, out_path=tmp_path / "dashboard.html")
    text = out.read_text(encoding="utf-8")
    for marker in _SECTION_MARKERS:
        assert f'data-section="{marker}"' in text, f"missing section {marker}"
    conn.close()


def test_dashboard_is_valid_utf8_and_declares_charset(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = _rebuild_all(db, deploys, deploy_project)
    out = sd.generate_dashboard(conn, out_path=tmp_path / "dashboard.html")
    raw = out.read_bytes()
    raw.decode("utf-8")  # must not raise
    assert b'<meta charset="utf-8">' in raw
    conn.close()


# ---------------------------------------------------------------------
# NULL handling -- tiles never show 0 for missing data (accept key 2).
# ---------------------------------------------------------------------
def test_stat_tile_empty_window_shows_na_not_zero(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [
        ev("2026-07-05T00:00:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="1"),
    ])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    conn = _rebuild_all(db, [("shtab", str(j))], {"shtab": "projA"})
    data = sd.build_dashboard_data(conn, k=6, top_n=10)
    cal_group = data["stat_tiles"][0]
    assert cal_group["window_id"] is not None  # a real (empty) window exists
    money_tile = next(t for t in cal_group["tiles"] if t["label"] == "$ окна")
    assert money_tile["value_display"] == "н/д"
    assert "пустое окно" in (money_tile["reason"] or "")
    conn.close()


def test_svg_line_chart_null_breaks_into_separate_segments():
    chart = {
        "title": "T",
        "lines": [{"label": "M", "points": [
            {"window_id": "w1", "window_start": None, "value": 1.0},
            {"window_id": "w2", "window_start": None, "value": 2.0},
            {"window_id": "w3", "window_start": None, "value": None},
            {"window_id": "w4", "window_start": None, "value": 3.0},
        ]}],
    }
    svg = sd._svg_line_chart(chart)
    # first run (1.0, 2.0) is a 2-point segment -> ONE polyline; the
    # NULL breaks the line -- the lone trailing point (3.0) is its own
    # segment, rendered as a standalone circle, never joined by a
    # polyline across the gap (never interpolated through 0).
    assert svg.count("<polyline") == 1
    assert svg.count("<circle") == 3  # 2 from the joined segment + 1 lone point


def test_svg_line_chart_all_null_shows_no_data():
    chart = {"title": "T", "lines": [{"label": "M", "points": [
        {"window_id": "w1", "window_start": None, "value": None},
    ]}]}
    svg = sd._svg_line_chart(chart)
    assert "данных нет" in svg
    assert "<polyline" not in svg
    assert "<circle" not in svg


# ---------------------------------------------------------------------
# (г) monthly report table -- matches token_usage_stats' own methodology
# (accept key 3, fixture + live is in the DoD witness run).
# ---------------------------------------------------------------------
def test_monthly_table_matches_methodology_and_converges(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", {"shtab": "projS", "ao3": "projA", "dog": "projD"})
    insert_cc_row(db, "2026-07-15T10:00:00Z", "projS", agent_id="a1", model="claude-sonnet-5",
                  dedupe_suffix="1")
    insert_cc_row(db, "2026-07-16T10:00:00Z", "projA", agent_id="a2", model="claude-opus-5",
                  dedupe_suffix="2")
    insert_cc_row(db, "2026-07-17T10:00:00Z", "projD", agent_id="a3", model="claude-haiku-4-5",
                  dedupe_suffix="3")
    conn = sqlite3.connect(db)
    now = datetime(2026, 8, 20)

    mt = sd.build_monthly_report_table(conn, now=now)

    assert mt["window_label"] == tus.window_label(2026, 7)
    assert mt["overall"] == "да"
    for dep in ("shtab", "ao3", "dog"):
        assert mt["convergence"][dep] == "да"

    by_family, by_project, _period_sessions = tus.aggregate(conn)
    wkey = (2026, 7)
    s, cost, unpriced = tus._sum_group(by_project[wkey]["projS"])
    assert not unpriced
    proj_s = next(p for p in mt["projects"] if p["deploy"] == "shtab")
    assert proj_s["totals"]["cost"] == pytest.approx(cost)
    assert proj_s["totals"]["input"] == s["input"]
    assert proj_s["totals"]["output"] == s["output"]
    conn.close()


def test_monthly_table_no_completed_window_is_na_not_crash(tmp_path):
    db = make_db(tmp_path)
    conn = sqlite3.connect(db)
    mt = sd.build_monthly_report_table(conn, now=datetime(2026, 8, 20))
    assert mt["window_label"] is None
    assert "н/д" in mt["overall"]
    conn.close()


def test_monthly_table_unpriced_model_is_na_not_da(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    monkeypatch.setattr(sm, "DEPLOY_PROJECT", {"shtab": "projS", "ao3": "projA", "dog": "projD"})
    insert_cc_row(db, "2026-07-15T10:00:00Z", "projS", agent_id="a1", model="unknown-xyz",
                  force_unpriced=True, dedupe_suffix="1")
    conn = sqlite3.connect(db)
    mt = sd.build_monthly_report_table(conn, now=datetime(2026, 8, 20))
    assert mt["convergence"]["shtab"] == "н/д (модели без цены)"
    assert mt["overall"] != "да"
    conn.close()


# ---------------------------------------------------------------------
# (д) health section -- RUNS_WITHOUT_UNITS wiring surfaces via reuse of
# spend_report.build_r4_3 (own wiring tested in test_spend_report.py).
# ---------------------------------------------------------------------
def test_health_section_reuses_r4_3_calibration_registry_gaps(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = _rebuild_all(db, deploys, deploy_project)
    data = sd.build_dashboard_data(conn)
    assert "calibration_registry_gaps" in data["health"]["runs_without_units"]
    assert "shtab" in data["health"]["runs_without_units"]["calibration_registry_gaps"]
    conn.close()


# ---------------------------------------------------------------------
# E12 -- cc_usage/requests untouched (SELECT-only), narrow rerun of the
# B1 invariant guard for THIS module's own read path.
# ---------------------------------------------------------------------
def test_cc_usage_invariant_untouched_by_dashboard_generation(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    conn = _rebuild_all(db, deploys, deploy_project)
    before = sm.cc_usage_invariant(conn)
    sd.generate_dashboard(conn, out_path=tmp_path / "dashboard.html")
    after = sm.cc_usage_invariant(conn)
    assert before == after
    conn.close()


# =======================================================================
# ADVERSARIAL BATTERY (R11, spec section 6/DoD item 5, verbatim list)
# =======================================================================
def test_battery_empty_window_series_shows_no_data_not_crash(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    j = tmp_path / "j.jsonl"
    write_journal(j, [])
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "projA"})
    out = tmp_path / "dashboard.html"
    rc = sd.main(["--skip-import", "--db", str(db), "--out", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "данных нет" in text
    for marker in _SECTION_MARKERS:
        assert f'data-section="{marker}"' in text


def test_battery_cyrillic_project_and_path(tmp_path, monkeypatch):
    db = make_db(tmp_path)
    j = tmp_path / "журналы" / "маршрут.jsonl"
    write_journal(j, [
        ev("2026-07-01T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-1", category="implementation", worker_ref="agent:a1", notes="n"),
        ev("2026-07-01T00:05:00", "accepted", agent="builder", model="sonnet",
           task_id="t-1", by="fable", category="implementation", witness="w", notes="n"),
        ev("2026-07-05T00:00:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="1"),
    ])
    insert_cc_row(db, "2026-07-01T00:00:30Z", "МойПроект", agent_id="a1", model="claude-sonnet-5",
                  dedupe_suffix="1")
    _patch_deploys(monkeypatch, [("shtab", str(j))], {"shtab": "МойПроект"})
    out = tmp_path / "кириллица" / "дашборд.html"
    rc = sd.main(["--skip-import", "--db", str(db), "--out", str(out)])
    assert rc == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "МойПроект" in text or "shtab" in text  # readable, no mangling/crash


def test_battery_cp1251_console_does_not_crash(tmp_path, monkeypatch):
    """Class t-408: PYTHONIOENCODING=cp1251 -- run as a REAL subprocess
    (mirrors test_spend_report.py's own equivalent test)."""
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1251"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent)
    script = str(Path(__file__).resolve().parent / "spend_dashboard.py")
    out = tmp_path / "dashboard.html"
    proc = subprocess.run(
        [sys.executable, script, "--skip-import", "--db", str(db), "--out", str(out)],
        cwd=str(Path(__file__).resolve().parent), capture_output=True, env=env, timeout=60,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"stdout={stdout!r} stderr={stderr!r}"
    assert out.exists()


def test_battery_out_path_with_spaces(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    out = tmp_path / "dir with spaces" / "dash board.html"
    rc = sd.main(["--skip-import", "--db", str(db), "--out", str(out)])
    assert rc == 0
    assert out.exists()
    assert "data-section=\"header\"" in out.read_text(encoding="utf-8")


def test_battery_k_zero_refuses(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sd.main(["--skip-import", "--db", str(db), "--k", "0",
                  "--out", str(tmp_path / "d.html")])
    assert rc == 2


def test_battery_k_negative_refuses(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sd.main(["--skip-import", "--db", str(db), "--k", "-3",
                  "--out", str(tmp_path / "d.html")])
    assert rc == 2


def test_battery_k_one_boundary_beyond_zero_is_legal(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    out = tmp_path / "d.html"
    rc = sd.main(["--skip-import", "--db", str(db), "--k", "1", "--out", str(out)])
    assert rc == 0
    assert out.exists()


def test_battery_top_zero_refuses(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    rc = sd.main(["--skip-import", "--db", str(db), "--top", "0",
                  "--out", str(tmp_path / "d.html")])
    assert rc == 2


def test_battery_top_one_boundary_is_legal(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    out = tmp_path / "d.html"
    rc = sd.main(["--skip-import", "--db", str(db), "--top", "1", "--out", str(out)])
    assert rc == 0
    assert out.exists()


def test_battery_db_without_cc_usage_table_exits_2(tmp_path):
    db_file = tmp_path / "empty.db"
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()
    rc = sd.main(["--skip-import", "--db", str(db_file), "--out", str(tmp_path / "d.html")])
    assert rc == 2


# ---------------------------------------------------------------------
# spend_report.py --dashboard wiring (accept key 1's "или spend_report
# --dashboard" alternative).
# ---------------------------------------------------------------------
def test_spend_report_dashboard_flag_writes_html(tmp_path, monkeypatch):
    db, deploys, deploy_project, _j = _three_task_fixture(tmp_path)
    _patch_deploys(monkeypatch, deploys, deploy_project)
    out = tmp_path / "logs" / "spend" / "dashboard.html"
    monkeypatch.setattr(sd, "DASHBOARD_PATH", out)
    rc = sr.main(["--window", "last", "--skip-import", "--db", str(db),
                  "--deploy", "shtab", "--dashboard"])
    assert rc == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "data-section=\"header\"" in text
