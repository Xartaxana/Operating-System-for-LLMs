"""Tests for tools/session_context.py. No network, no LLM calls; every
test builds a synthetic repo-shaped tmp directory (logs/routing-log.jsonl
+ gateway/{config.yaml,budgets.yaml,*.db}) and points build_context_lines()
/ main() at it via root=. Mirrors tools/test_usage_report.py's style.

Run from the repo root: python -m pytest tools/test_session_context.py
"""

import datetime
import importlib
import json
import sqlite3
import sys
from pathlib import Path

import yaml

from session_context import (
    build_context_lines,
    gemini_aliases,
    journal_path,
    last_calibration_line,
    last_event_line,
    main,
    now_line,
    open_degradation_window,
    read_journal_events,
)

# t-043 (B3 remainder): the new MODEL / BOOT BUDGET functions live in the
# draft tools/session_context_b3.py (D-0069 -- a SessionStart hook is a
# self-activating enforcement file, so a builder session lands it under a
# neighboring name and Lead moves it onto the live path at acceptance).
# This indirection means the test suite keeps working unchanged once that
# move happens: only this import line needs to flip.
try:
    import session_context_d0076 as sc
except ImportError:
    import session_context as sc

REQUESTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    model TEXT,
    provider_model TEXT,
    status TEXT NOT NULL,
    total_tokens INTEGER,
    traffic_kind TEXT NOT NULL DEFAULT 'real'
);
"""

CONFIG = {
    "model_list": [
        {"model_name": "middle-groq", "litellm_params": {"model": "groq/llama-3.3-70b-versatile"}},
        {"model_name": "lead-gemini", "litellm_params": {"model": "gemini/gemini-2.5-flash"}},
        {"model_name": "judge-gemini", "litellm_params": {"model": "gemini/gemini-3.5-flash"}},
    ]
}

BUDGETS = {
    "quota_windows": {
        "middle-groq": [{"window_seconds": 86400, "limit_tokens": 100000}],
    }
}


def _seed_repo(tmp_path, events=None, config=None, budgets=None) -> Path:
    root = tmp_path
    (root / "logs").mkdir(parents=True, exist_ok=True)
    gateway = root / "gateway"
    gateway.mkdir(exist_ok=True)

    if events is not None:
        with open(root / "logs" / "routing-log.jsonl", "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    with open(gateway / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config if config is not None else CONFIG, f)
    with open(gateway / "budgets.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(budgets if budgets is not None else BUDGETS, f)

    conn = sqlite3.connect(gateway / "requests.db")
    conn.execute(REQUESTS_SCHEMA)
    conn.commit()
    conn.close()

    return root


def _event(event, ts="2026-07-10T08:00:00", **kw):
    e = {"ts": ts, "event": event}
    e.update(kw)
    return e


# ---- NOW line: ASCII, system clock ----

def test_now_line_is_ascii_and_uses_given_clock():
    now = datetime.datetime(2026, 7, 10, 8, 41, 23)  # a Friday
    line = now_line(now)
    assert line.isascii()
    assert "2026-07-10 08:41:23" in line
    assert "Friday" in line


# ---- journal tail ----

def test_read_journal_events_empty_when_missing(tmp_path):
    root = _seed_repo(tmp_path, events=None)
    assert read_journal_events(root) == []


def test_journal_path_location(tmp_path):
    root = _seed_repo(tmp_path, events=[])
    assert journal_path(root) == root / "logs" / "routing-log.jsonl"


def test_last_event_line_reports_tail():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("accepted", ts="2026-07-10T08:10:00", agent="builder", task_id="t-001"),
    ]
    line = last_event_line(events)
    assert "ts=2026-07-10T08:10:00" in line
    assert "event=accepted" in line
    assert "agent=builder" in line
    assert "task_id=t-001" in line


def test_last_event_line_empty_journal():
    assert "empty or missing" in last_event_line([])


# ---- VG-1 part B: CLOCK DRIFT line ----------------------------------------
# Field precedent (2026-07-23): a session's journal tail carried
# ts=20:16:32 while the system clock read 19:45:56 -- a previous
# environment's clock ran ahead. Threshold: > 60s. Battery per CLAUDE.md
# R11: acceptance keys (fires when ahead, silent when not) + the boundary
# itself (60s exactly vs 61s) + adversarial fail-open inputs.


def test_clock_drift_line_absent_when_journal_ts_behind_system_clock():
    # The ordinary case: journal ts is BEFORE now (system clock ahead, or
    # equal) -- no drift, no line.
    events = [_event("delegated", ts="2026-07-10T08:00:00")]
    now = datetime.datetime(2026, 7, 10, 9, 0, 0)
    assert sc.clock_drift_line(events, now) == ""


def test_clock_drift_line_at_threshold_boundary_is_silent():
    # Exactly 60s ahead: the spec's threshold is "> 60s" -- AT the
    # boundary must NOT fire.
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [_event("delegated", ts="2026-07-10T08:01:00")]  # +60s
    assert sc.clock_drift_line(events, now) == ""


def test_clock_drift_line_one_second_past_threshold_fires():
    # 61s ahead -- one second past the boundary -- must fire.
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [_event("delegated", ts="2026-07-10T08:01:01")]  # +61s
    line = sc.clock_drift_line(events, now)
    assert line.startswith("CLOCK DRIFT: last journal ts is ")
    assert "min ahead of system clock" in line
    assert "D-0089" in line
    assert "non-monotonic" in line
    assert line.isascii()


def test_clock_drift_line_reports_minutes_ahead():
    # Field-precedent-shaped magnitude: ~30 minutes ahead.
    now = datetime.datetime(2026, 7, 23, 19, 45, 56)
    events = [_event("delegated", ts="2026-07-23T20:16:32")]
    line = sc.clock_drift_line(events, now)
    assert "CLOCK DRIFT: last journal ts is 31 min ahead of system clock" in line


def test_clock_drift_line_empty_journal_is_silent():
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    assert sc.clock_drift_line([], now) == ""


def test_clock_drift_line_missing_ts_field_is_silent():
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [{"event": "delegated"}]  # no 'ts' key at all
    assert sc.clock_drift_line(events, now) == ""


def test_clock_drift_line_malformed_non_iso_ts_is_silent():
    # Adversarial: a broken/non-ISO tail ts must fail open (no line, no
    # crash), not raise out of build_context_lines()/main().
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [_event("delegated", ts="not-a-timestamp-at-all")]
    assert sc.clock_drift_line(events, now) == ""


def test_clock_drift_line_non_string_ts_is_silent():
    # Adversarial: a malformed journal line where ts ended up a number
    # (not the contractual string) must not crash with an AttributeError
    # from parse_ts()'s own .strip() call.
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [{"event": "delegated", "ts": 12345}]
    assert sc.clock_drift_line(events, now) == ""


def test_build_context_lines_includes_clock_drift_when_present(tmp_path):
    events = [_event("delegated", ts="2026-07-10T09:05:00", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    now = datetime.datetime(2026, 7, 10, 9, 0, 0)  # journal ts is +5min ahead
    lines = sc.build_context_lines(root, now)
    assert any(l.startswith("CLOCK DRIFT:") for l in lines), lines


def test_build_context_lines_omits_clock_drift_when_absent(tmp_path):
    events = [_event("delegated", ts="2026-07-10T08:00:00", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    now = datetime.datetime(2026, 7, 10, 9, 0, 0)  # journal ts is BEHIND now
    lines = sc.build_context_lines(root, now)
    assert not any(l.startswith("CLOCK DRIFT:") for l in lines), lines


def test_main_survives_malformed_tail_ts_no_clock_drift_crash(tmp_path, capsys):
    # Adversarial (journal missing entirely): main() must still run
    # clean, and clock_drift_line's own empty-journal branch must not be
    # the source of any crash.
    root = tmp_path
    (root / "logs").mkdir()
    # No routing-log.jsonl file at all.
    (root / "gateway").mkdir()
    with open(root / "gateway" / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG, f)
    with open(root / "gateway" / "budgets.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(BUDGETS, f)
    conn = sqlite3.connect(root / "gateway" / "requests.db")
    conn.execute(REQUESTS_SCHEMA)
    conn.commit()
    conn.close()
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert not any(l.startswith("CLOCK DRIFT:") for l in out)


def test_main_survives_broken_tail_ts_no_clock_drift_crash(tmp_path, capsys):
    # Adversarial (journal PRESENT but tail ts is not ISO at all): must
    # not crash main(), and must simply omit the CLOCK DRIFT line rather
    # than raise.
    events = [_event("delegated", ts="garbage-not-a-timestamp", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert not any(l.startswith("CLOCK DRIFT:") for l in out)


# ---- degradation window: open vs closed ----

def test_open_degradation_window_detects_unclosed():
    events = [
        _event("delegated", ts="2026-07-10T07:00:00"),
        _event("lead_degraded", ts="2026-07-10T07:30:00"),
        _event("delegated", ts="2026-07-10T08:00:00"),
    ]
    assert open_degradation_window(events) == "2026-07-10T07:30:00"


def test_open_degradation_window_none_when_closed():
    events = [
        _event("lead_degraded", ts="2026-07-10T07:30:00"),
        _event("lead_restored", ts="2026-07-10T07:45:00"),
        _event("delegated", ts="2026-07-10T08:00:00"),
    ]
    assert open_degradation_window(events) is None


def test_open_degradation_window_scans_whole_journal_not_just_tail():
    # An unclosed window far from the tail must still be caught -- the
    # scan is over the WHOLE journal (D-0039 p.4: a safety-reset can
    # leave no lead_restored anywhere after it).
    events = [
        _event("lead_degraded", ts="2026-07-01T00:00:00"),
        *[_event("delegated", ts=f"2026-07-0{d}T00:00:00") for d in range(2, 9)],
    ]
    assert open_degradation_window(events) == "2026-07-01T00:00:00"


def test_build_context_lines_shows_open_window(tmp_path):
    events = [_event("lead_degraded", ts="2026-07-10T07:30:00")]
    root = _seed_repo(tmp_path, events=events)
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    lines = build_context_lines(root, now)
    assert any("OPEN DEGRADATION WINDOW since 2026-07-10T07:30:00" in l for l in lines)


def test_build_context_lines_no_open_window_line_when_closed(tmp_path):
    events = [
        _event("lead_degraded", ts="2026-07-10T07:30:00"),
        _event("lead_restored", ts="2026-07-10T07:45:00"),
    ]
    root = _seed_repo(tmp_path, events=events)
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    lines = build_context_lines(root, now)
    assert not any("OPEN DEGRADATION WINDOW" in l for l in lines)


# ---- last calibration: NONE vs dated ----

def test_last_calibration_none_when_absent():
    events = [_event("delegated")]
    assert last_calibration_line(events) == "Last calibration: NONE"


def test_last_calibration_reports_ts_and_age():
    events = [_event("calibrated", ts="2026-07-03T00:00:00")]
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    line = last_calibration_line(events, now)
    assert "2026-07-03T00:00:00" in line
    assert "7 days ago" in line


def test_last_calibration_uses_most_recent_of_several():
    events = [
        _event("calibrated", ts="2026-06-20T00:00:00"),
        _event("calibrated", ts="2026-07-08T00:00:00"),
    ]
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    line = last_calibration_line(events, now)
    assert "2026-07-08T00:00:00" in line
    assert "2 days ago" in line


# ---- gemini alias detection ----

def test_gemini_aliases_filters_by_raw_provider_prefix():
    assert set(gemini_aliases(CONFIG)) == {"lead-gemini", "judge-gemini"}


# ---- full assembly: <=25 lines, ASCII ----

def test_build_context_lines_within_line_budget_and_ascii(tmp_path):
    events = [_event("delegated", task_id="t-001"), _event("calibrated", ts="2026-07-08T00:00:00")]
    root = _seed_repo(tmp_path, events=events)
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    lines = build_context_lines(root, now)
    assert len(lines) <= 25
    for line in lines:
        assert line.isascii()


# ---- fail-open: broken journal never raises, always prints one warning, exit 0 ----

def test_main_fail_open_on_broken_journal(tmp_path, capsys):
    root = _seed_repo(tmp_path, events=None)
    (root / "logs" / "routing-log.jsonl").write_text("{not valid json\n", encoding="utf-8")
    code = main(root)
    assert code == 0
    captured = capsys.readouterr()
    out = (captured.out + captured.err).strip().splitlines()
    assert len(out) == 1
    assert out[0].startswith("session-context warning:")


def test_main_survives_gateway_dir_missing_with_real_context(tmp_path, capsys):
    # t-275 (CURRENT_CONTEXT batch item б, Finding B / D-0043): a repo
    # root with no gateway/ directory at all (config.yaml/budgets.yaml
    # unreachable) used to make preflight_quota.load_config's bare
    # open() raise FileNotFoundError from inside quota_lines() (which
    # has NO local try/except by design), which propagated to THIS
    # main()'s single fail-open boundary and blanked the ENTIRE context
    # block (NOW/MODEL/JOURNAL/boot-budget/wiring, not just the quota
    # line) -- exit 0, but only one bare warning line, real context lost.
    # After load_config's exists-guard (mirrors load_budgets), a missing
    # gateway/ dir no longer raises at all: quota_lines() returns
    # cleanly (empty, since there is no config.yaml-declared alias to
    # report on), and the REST of the context survives intact. This is
    # the direct, empirically-verified consequence of the load_config
    # fix, not a change made to this file (tools/session_context.py
    # itself is untouched by this batch, per its owns/non-goals fence).
    root = tmp_path
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    # No longer the single fail-open warning line -- real context lines
    # are present (NOW/MODEL/JOURNAL at least), and quota_lines()
    # produced no exception-triggered warning.
    assert not any(l.startswith("session-context warning:") for l in out)
    assert any(l.startswith("NOW:") for l in out)
    assert any(l.startswith("MODEL:") for l in out)
    assert any(l.startswith("JOURNAL:") for l in out)


def test_quota_lines_missing_gateway_dir_returns_empty_not_raises(tmp_path):
    # Narrower, direct test of the same fix at the quota_lines() level
    # (independent of main()'s outer boundary): a gateway/ root that does
    # not exist at all must not raise out of quota_lines() -- there is
    # simply nothing to report (no config.yaml -> no aliases -> no
    # budgets.yaml-declared window can be resolved).
    gateway_root = tmp_path / "gateway"
    assert not gateway_root.exists()
    assert sc.quota_lines(gateway_root) == []


def test_main_survives_config_yaml_specifically_missing_budgets_present(tmp_path, capsys):
    # Narrower absence than "whole gateway/ dir missing": the directory
    # exists (budgets.yaml is present and readable) but config.yaml
    # specifically is not there -- the exact scenario named in the spec
    # ("config.yaml отсутствует"). Must degrade the same way: real
    # context survives, no bare fail-open warning.
    root = tmp_path
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    gateway = root / "gateway"
    gateway.mkdir()
    with open(gateway / "budgets.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(BUDGETS, f)
    # config.yaml deliberately NOT written.
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert any(l.startswith("NOW:") for l in out)


# ---- t-278 п.6: config.yaml EXISTING but unparseable (corrupt YAML) ----


def test_quota_lines_malformed_config_yaml_returns_single_marker_line(tmp_path):
    gateway_root = tmp_path / "gateway"
    gateway_root.mkdir()
    (gateway_root / "config.yaml").write_text("key: [unclosed\n", encoding="utf-8")
    lines = sc.quota_lines(gateway_root)
    assert len(lines) == 1
    assert lines[0].startswith("quota: config unreadable (")
    assert lines[0].isascii()
    assert "\n" not in lines[0]


def test_quota_lines_malformed_config_yaml_reason_single_line_even_if_error_is_multiline(tmp_path):
    # yaml.YAMLError's own str() is typically MULTI-LINE (a "problem"
    # line plus a "in <file>, line N, column N" continuation) -- the
    # marker line itself must stay single-line regardless.
    gateway_root = tmp_path / "gateway"
    gateway_root.mkdir()
    (gateway_root / "config.yaml").write_text("key: [unclosed\n", encoding="utf-8")
    lines = sc.quota_lines(gateway_root)
    assert len(lines) == 1
    assert len(lines[0].splitlines()) == 1


def test_main_survives_malformed_config_yaml_with_real_context(tmp_path, capsys):
    root = tmp_path
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    gateway = root / "gateway"
    gateway.mkdir()
    (gateway / "config.yaml").write_text("key: [unclosed\n", encoding="utf-8")
    with open(gateway / "budgets.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(BUDGETS, f)
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert any(l.startswith("NOW:") for l in out)
    assert any(l.startswith("MODEL:") for l in out)
    assert any(l.startswith("JOURNAL:") for l in out)
    assert any(l.startswith("BOOT BUDGET:") for l in out)
    assert any(l.startswith("quota: config unreadable (") for l in out)


# ---- t-278-дельта п.3: budgets.yaml EXISTING but unparseable ----


def test_quota_lines_malformed_budgets_yaml_surfaces_reason_but_keeps_rest(tmp_path):
    # В отличие от битого config.yaml (п.6, гасит quota_lines() целиком
    # до ОДНОЙ строки-маркера), битый budgets.yaml гардится ВНУТРИ
    # load_budgets() -- остальные секции quota_lines() (per-alias
    # QUOTA/REQUESTS из config) печатаются штатно рядом с маркером.
    gateway_root = tmp_path / "gateway"
    gateway_root.mkdir()
    with open(gateway_root / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG, f)
    (gateway_root / "budgets.yaml").write_text(
        "quota_windows: [this is not: valid: yaml: at all\n", encoding="utf-8"
    )
    conn = sqlite3.connect(gateway_root / "requests.db")
    conn.execute(REQUESTS_SCHEMA)
    conn.commit()
    conn.close()

    lines = sc.quota_lines(gateway_root)
    assert any(l.startswith("quota: budgets unreadable (") for l in lines)
    assert any(l.startswith("REQUESTS ") for l in lines)  # gemini-alias line, unaffected


def test_main_survives_malformed_budgets_yaml_with_real_context(tmp_path, capsys):
    root = tmp_path
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    gateway = root / "gateway"
    gateway.mkdir()
    with open(gateway / "config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(CONFIG, f)
    (gateway / "budgets.yaml").write_text(
        "quota_windows: [this is not: valid: yaml: at all\n", encoding="utf-8"
    )
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert any(l.startswith("NOW:") for l in out)
    assert any(l.startswith("MODEL:") for l in out)
    assert any(l.startswith("JOURNAL:") for l in out)
    assert any(l.startswith("BOOT BUDGET:") for l in out)
    assert any(l.startswith("quota: budgets unreadable (") for l in out)


def test_main_success_path_prints_lines_and_exits_zero(tmp_path, capsys):
    events = [_event("delegated", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) >= 2  # at least NOW + LAST EVENT
    assert any(l.startswith("NOW:") for l in out)
    assert not any(l.startswith("session-context warning:") for l in out)


# ---- N4 (critic t-027): import-time failure must ALSO fail open ----

def test_deferred_import_error_reaches_mains_fail_open_boundary(tmp_path, capsys, monkeypatch):
    # Runtime half of the fix: once import has failed and the stub raises
    # on call, main()'s single try/except boundary must still catch it
    # (proves the deferred-raise wiring, independent of the real import
    # machinery exercised by the end-to-end test below).
    import session_context as sc

    def _boom(*_a, **_kw):
        raise ImportError("simulated: no module named 'yaml'")

    monkeypatch.setattr(sc, "load_config", _boom)
    monkeypatch.setattr(sc, "load_budgets", _boom)
    monkeypatch.setattr(sc, "alias_provider_models", _boom)
    monkeypatch.setattr(sc, "usage_in_window", _boom)

    root = _seed_repo(tmp_path, events=[_event("delegated", task_id="t-001")])
    code = sc.main(root)
    assert code == 0
    captured = capsys.readouterr()
    out = (captured.out + captured.err).strip().splitlines()
    assert len(out) == 1
    assert out[0].startswith("session-context warning:")


def test_module_survives_broken_preflight_quota_import_and_fails_open(tmp_path, capsys, monkeypatch):
    # End-to-end, real import failure (no mock of the failure mode): a
    # syntactically broken preflight_quota.py shadows the real one via
    # sys.path priority. Before the N4 fix, this SyntaxError happened
    # DURING `import session_context` itself (module-level code, outside
    # main()'s try/except, which does not exist yet at that point) and
    # would have crashed with a bare traceback instead of failing open --
    # exactly the failure mode a SessionStart hook cannot afford.
    broken_dir = tmp_path / "broken_pkg"
    broken_dir.mkdir()
    (broken_dir / "preflight_quota.py").write_text("def broken(:\n    pass\n", encoding="utf-8")

    root = _seed_repo(tmp_path, events=[_event("delegated", task_id="t-001")])

    saved_modules = {name: sys.modules.get(name) for name in ("session_context", "preflight_quota")}
    for name in saved_modules:
        sys.modules.pop(name, None)
    monkeypatch.syspath_prepend(str(broken_dir))

    try:
        broken_sc = importlib.import_module("session_context")  # must NOT raise
        code = broken_sc.main(root)
    finally:
        sys.modules.pop("session_context", None)
        sys.modules.pop("preflight_quota", None)
        for name, mod in saved_modules.items():
            if mod is not None:
                sys.modules[name] = mod
            else:
                importlib.import_module(name)

    assert code == 0
    captured = capsys.readouterr()
    out = (captured.out + captured.err).strip().splitlines()
    assert len(out) == 1
    assert out[0].startswith("session-context warning:")


# ==== t-043 (B3 remainder): MODEL line (D-0056a) ====================


class _FakeStdin:
    """Minimal stand-in for sys.stdin used to test the isatty() guard
    and the JSON read without touching the real process stdin."""

    def __init__(self, text, tty=False):
        self._text = text
        self._tty = tty

    def isatty(self):
        return self._tty

    def read(self):
        return self._text


def test_extract_model_id_top_level_string():
    assert sc.extract_model_id({"model": "claude-sonnet-5"}) == "claude-sonnet-5"


def test_extract_model_id_dict_with_id_key():
    assert sc.extract_model_id({"model": {"id": "claude-opus-4"}}) == "claude-opus-4"


def test_extract_model_id_dict_with_model_key():
    assert sc.extract_model_id({"model": {"model": "claude-haiku-3"}}) == "claude-haiku-3"


def test_extract_model_id_top_level_model_id_fallback():
    assert sc.extract_model_id({"model_id": "claude-fable-5"}) == "claude-fable-5"


def test_extract_model_id_missing_returns_none():
    assert sc.extract_model_id({}) is None
    assert sc.extract_model_id(None) is None
    assert sc.extract_model_id("not a dict") is None


def test_model_tier_mapping_all_known_tiers():
    # B1(a) (пересдача, блокер): config_text=None ЯВНО -- изоляция от
    # реального delegation.config.yaml, который скоро появится в корне
    # (иначе привязка к opus молча превратила бы это в другую метку).
    assert sc.model_tier("claude-fable-5", config_text=None) == "Lead(top)"
    assert sc.model_tier("claude-opus-4", config_text=None) == "critic-tier"
    assert sc.model_tier("claude-sonnet-5", config_text=None) == "builder-tier"
    assert sc.model_tier("claude-haiku-3", config_text=None) == "scout-tier"


def test_model_tier_mapping_unknown_string():
    assert sc.model_tier("some-other-model") == "unknown"


# ---- D-0099 (2026-08-04): binding-aware label -- config_text is ALWAYS
# injected here (never the real delegation.config.yaml, which does not
# exist in this repo yet -- CLAUDE.md/dispatch instruction: tests must
# inject config_text/path, not rely on the real file). ----

_LEAD_BINDING_OPUS_YAML = """
roles:
  lead:
    subscription:
      model: claude-opus-5
"""


def test_model_tier_binding_aware_no_config_regression_pin():
    # "нет конфига" -- injected None (same signal as a real absent file,
    # by design) -> today's static label, unchanged.
    assert sc.model_tier("claude-fable-5", config_text=None) == "Lead(top)"


def test_model_tier_binding_aware_opus_binding_labels_opus_session_bound():
    assert sc.model_tier("claude-opus-4", config_text=_LEAD_BINDING_OPUS_YAML) == "Lead(bound)"


def test_model_tier_binding_aware_opus_binding_labels_fable_session_top_reserve():
    assert sc.model_tier("claude-fable-5", config_text=_LEAD_BINDING_OPUS_YAML) == "top-reserve"


def test_model_tier_binding_aware_opus_binding_other_sessions_unchanged():
    # "остальные -- как сегодня": sonnet/haiku sessions under an opus
    # binding are neither the bound family nor fable -- static label.
    assert sc.model_tier("claude-sonnet-5", config_text=_LEAD_BINDING_OPUS_YAML) == "builder-tier"
    assert sc.model_tier("claude-haiku-3", config_text=_LEAD_BINDING_OPUS_YAML) == "scout-tier"


def test_model_tier_binding_aware_unknown_model_ignores_binding():
    # ГРАНИЦА: no session family to compare at all -- "unknown" regardless
    # of what the binding resolves to.
    assert sc.model_tier("some-other-model", config_text=_LEAD_BINDING_OPUS_YAML) == "unknown"


def test_model_tier_binding_aware_fail_open_on_resolver_exception(monkeypatch):
    # ЛЮБОЕ исключение при резолюции привязки (не только отсутствие файла)
    # -- fail-open к статической метке, SessionStart-хук не должен падать.
    import mechanism_gate as mg

    def _boom(_config_text):
        raise RuntimeError("simulated resolver crash")

    monkeypatch.setattr(mg, "resolve_lead_binding", _boom)
    assert sc.model_tier("claude-fable-5", config_text=_LEAD_BINDING_OPUS_YAML) == "Lead(top)"


def test_model_line_found_string_form():
    # B1(a)/(b) (пересдача, блокер): config_text=None ЯВНО через модельный
    # шов -- изоляция от реального delegation.config.yaml (иначе "Lead
    # tier = fable" (B5) стало бы "Lead tier = opus" под реальной привязкой).
    line = sc.model_line({"model": "claude-fable-5"}, config_text=None)
    # F-37: the payload id is a harness declaration, not a measurement --
    # the line must say so (present-but-stale stated confidently is the
    # failure mode this marker exists to prevent).
    assert line == (
        "MODEL: claude-fable-5 -> tier Lead(top)"
        " (declared by harness, not measured -- F-37; Lead tier = fable)"
    )


def test_model_line_found_dict_form():
    # B1(a)/(b): same isolation as above -- the "Lead tier = fable" clause
    # is B5-dynamic now, not a hardcoded literal.
    line = sc.model_line({"model": {"id": "claude-sonnet-5"}}, config_text=None)
    assert line == (
        "MODEL: claude-sonnet-5 -> tier builder-tier"
        " (declared by harness, not measured -- F-37; Lead tier = fable)"
    )


def test_model_line_found_string_form_lead_binding_opus_positive():
    # П2 добора t-353 (2026-08-05): ПОЗИТИВНАЯ сторона пина B5, в паре с
    # test_model_line_found_string_form выше (та пинует "нет конфига ->
    # Lead tier = fable"). Тот же шов инъекции (config_text=...), что уже
    # используют test_model_tier_binding_aware_* -- _LEAD_BINDING_OPUS_YAML
    # (переиспользован, второй способ не изобретён). Дословная подстрока
    # (не regex "opus где-то есть") сравнивается ПОЛНОЙ строкой '==',
    # включая маркер F-37 "declared by harness, not measured" в ТОЙ ЖЕ
    # строке -- пропажа маркера тоже уронит этот тест.
    line = sc.model_line({"model": "claude-opus-5"}, config_text=_LEAD_BINDING_OPUS_YAML)
    assert line == (
        "MODEL: claude-opus-5 -> tier Lead(bound)"
        " (declared by harness, not measured -- F-37; Lead tier = opus)"
    )


def test_model_line_missing_payload():
    assert sc.model_line(None) == (
        "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    )


def test_model_line_empty_payload():
    assert sc.model_line({}) == (
        "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    )


# ---- t-043 attempt 2 (critic-confirmed): model_line() ASCII/single-line
# sanitization of the externally-sourced model id ----------------------


def test_model_line_cyrillic_model_id_is_sanitized():
    line = sc.model_line({"model": "клод\nX"})
    assert line.isascii()
    assert "\n" not in line
    assert len(line.splitlines()) == 1


def test_model_line_emoji_model_id_is_sanitized():
    line = sc.model_line({"model": "sonnet\U0001F600rocket"})
    assert line.isascii()
    assert "\n" not in line
    assert len(line.splitlines()) == 1


def test_model_line_injection_attempt_stays_single_line():
    line = sc.model_line({"model": "x\nINJECTED FAKE LINE"})
    assert line.isascii()
    assert "\n" not in line
    assert len(line.splitlines()) == 1
    assert "INJECTED FAKE LINE" in line  # content kept, just de-lineified


def test_model_line_whitespace_only_falls_back_to_not_provided():
    assert sc.model_line({"model": "   "}) == (
        "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    )


def test_model_line_long_model_id_is_truncated():
    # R9 (класс B1(a)/(b), пересдача): та же изоляция от реального
    # конфига -- exact-match на "Lead tier = fable" (B5) точно так же
    # уязвим, хоть координатор явно не назвал эту строку.
    long_id = "sonnet-" + ("a" * 100)
    line = sc.model_line({"model": long_id}, config_text=None)
    assert line.isascii()
    assert "\n" not in line
    # "MODEL: " prefix + sanitized (<=80 chars) + " -> tier ... " suffix
    sanitized = sc._ascii_sanitize(long_id)
    assert len(sanitized) == 80
    assert line == (
        f"MODEL: {sanitized} -> tier builder-tier"
        " (declared by harness, not measured -- F-37; Lead tier = fable)"
    )


def test_ascii_sanitize_direct_cases():
    assert sc._ascii_sanitize("   ") == ""
    assert sc._ascii_sanitize("x\nINJECTED FAKE LINE") == "xINJECTED FAKE LINE"
    assert sc._ascii_sanitize("клодX").isascii()
    assert sc._ascii_sanitize("a" * 200, max_len=80) == "a" * 80


def test_read_stdin_payload_skips_when_tty(monkeypatch):
    # The isatty() guard must prevent any read() call at all when stdin
    # is a TTY (a manual run from an interactive shell must not block).
    def _boom():
        raise AssertionError("read() must not be called when stdin is a TTY")

    fake = _FakeStdin("", tty=True)
    fake.read = _boom
    monkeypatch.setattr(sys, "stdin", fake)
    assert sc.read_stdin_payload() is None


def test_read_stdin_payload_parses_json_when_piped(monkeypatch):
    fake = _FakeStdin(json.dumps({"model": "claude-opus-4"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    assert sc.read_stdin_payload() == {"model": "claude-opus-4"}


def test_read_stdin_payload_returns_none_on_malformed_json(monkeypatch):
    fake = _FakeStdin("{not valid json", tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    assert sc.read_stdin_payload() is None


def test_read_stdin_payload_returns_none_on_empty_input(monkeypatch):
    fake = _FakeStdin("", tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    assert sc.read_stdin_payload() is None


def test_build_context_lines_model_line_placed_right_after_now(tmp_path):
    # B1(b) (пересдача, блокер): config_text=None ЯВНО через
    # build_context_lines()'s собственный шов -- та же изоляция.
    root = _seed_repo(tmp_path, events=[])
    now = datetime.datetime(2026, 7, 11, 9, 0, 0)
    lines = sc.build_context_lines(
        root, now, stdin_payload={"model": "claude-fable-5"}, config_text=None)
    assert lines[0].startswith("NOW:")
    assert lines[1] == (
        "MODEL: claude-fable-5 -> tier Lead(top)"
        " (declared by harness, not measured -- F-37; Lead tier = fable)"
    )


# ==== t-043 (B3 remainder): BOOT BUDGET (D-0068/D-0038) ==============


def _seed_boot_files(root: Path, file_sizes: dict, boot_md_names=None):
    """Writes BOOT.md whose body references boot_md_names via "Read
    X.md" lines (defaults to the keys of file_sizes minus CLAUDE.md,
    since CLAUDE.md is always added by the code under test, not by
    BOOT.md's own list), plus each file in file_sizes at the given byte
    size (content is padding bytes, exact bytes matter for the budget
    arithmetic, not readability)."""
    if boot_md_names is None:
        boot_md_names = [n for n in file_sizes if n != "CLAUDE.md"]
    body = "\n".join(f"1. Read {name}." for name in boot_md_names)
    (root / "BOOT.md").write_text(body + "\n", encoding="utf-8")
    for name, size in file_sizes.items():
        (root / name).write_bytes(b"x" * size)


def test_boot_path_files_parses_boot_md_and_always_adds_claude_md(tmp_path):
    root = tmp_path
    (root / "BOOT.md").write_text(
        "1. Read README.md.\n2. Read PROJECT_CHARTER.md.\n", encoding="utf-8"
    )
    names = sc.boot_path_files(root)
    assert names == ["README.md", "PROJECT_CHARTER.md", "CLAUDE.md"]


def test_boot_path_files_missing_boot_md_still_yields_claude_md(tmp_path):
    assert sc.boot_path_files(tmp_path) == ["CLAUDE.md"]


def test_boot_path_files_pins_post_restructure_set():
    # F8 (boot restructure 2026-08-18, critic-on-plan t-479): pin the REAL
    # boot-load set so a silent budget miscount fails LOUDLY. boot_path_files
    # derives the budget from BOOT.md's literal `Read <FILE>.md` lines, so a
    # Read line added/removed (or BOOT.md rewritten into prose that drops the
    # literal form) would silently change the budget with no error. This test
    # is the tripwire. Layer A (orientation) + Layer B (state) + the auto-
    # appended CLAUDE.md.
    root = sc.repo_root()
    assert sc.boot_path_files(root) == [
        "README.md",
        "PROJECT_CHARTER.md",
        "ANTI_GOALS.md",
        "PROJECT_PHILOSOPHY.md",
        "ARCHITECTURE_BOOT.md",
        "CURRENT_CONTEXT.md",
        "CLAUDE.md",
    ]


def test_boot_budget_normal_under_warn_threshold(tmp_path):
    root = tmp_path
    _seed_boot_files(root, {"README.md": 100, "CLAUDE.md": 200})
    lines = sc.boot_budget_lines(root)
    assert lines == ["BOOT BUDGET: 300 bytes / 100000 (2 files) | CLAUDE.md: 200/35815"]


def test_boot_budget_warn_includes_top3(tmp_path):
    root = tmp_path
    _seed_boot_files(
        root,
        {
            "README.md": 40000,
            "PROJECT_CHARTER.md": 30000,
            "ANTI_GOALS.md": 25000,
            "CLAUDE.md": 100,
        },
    )
    lines = sc.boot_budget_lines(root)
    total = 40000 + 30000 + 25000 + 100
    assert total > sc.BOOT_WARN_THRESHOLD
    assert total <= sc.BOOT_BREACH_THRESHOLD
    assert lines[0] == (
        f"BOOT BUDGET: {total} bytes / 100000 (4 files) WARN | CLAUDE.md: 100/35815"
    )
    assert lines[1] == "  40000  README.md"
    assert lines[2] == "  30000  PROJECT_CHARTER.md"
    assert lines[3] == "  25000  ANTI_GOALS.md"
    assert len(lines) == 4


def test_boot_budget_breach_includes_hint_and_top3(tmp_path):
    root = tmp_path
    _seed_boot_files(
        root,
        {
            "README.md": 60000,
            "PROJECT_CHARTER.md": 30000,
            "ANTI_GOALS.md": 20000,
            "CLAUDE.md": 100,
        },
    )
    lines = sc.boot_budget_lines(root)
    total = 60000 + 30000 + 20000 + 100
    assert total > sc.BOOT_BREACH_THRESHOLD
    assert lines[0] == (
        f"BOOT BUDGET: {total} bytes / 100000 (4 files) BREACH -> boot-diet due "
        "(D-0068; report first, operator word starts it) | CLAUDE.md: 100/35815"
    )
    assert lines[1] == "  60000  README.md"
    assert lines[2] == "  30000  PROJECT_CHARTER.md"
    assert lines[3] == "  20000  ANTI_GOALS.md"


def test_boot_budget_missing_file_counts_zero_and_is_flagged(tmp_path):
    root = tmp_path
    # BOOT.md references a file that is never actually written.
    (root / "BOOT.md").write_text("1. Read GHOST_FILE.md.\n", encoding="utf-8")
    (root / "CLAUDE.md").write_bytes(b"x" * 50)
    lines = sc.boot_budget_lines(root)
    assert lines[0] == (
        "BOOT BUDGET: 50 bytes / 100000 (2 files) [missing: GHOST_FILE.md]"
        " | CLAUDE.md: 50/35815"
    )


# ---- W2b-8: CLAUDE.md's own personal ratchet suffix -- four worlds ----


def test_claude_budget_suffix_under_warn(tmp_path):
    root = tmp_path
    _seed_boot_files(root, {"README.md": 100, "CLAUDE.md": sc.CLAUDE_WARN - 1})
    lines = sc.boot_budget_lines(root)
    assert lines[0].endswith(f"| CLAUDE.md: {sc.CLAUDE_WARN - 1}/{sc.CLAUDE_WARN}")
    assert "OVER" not in lines[0]


def test_claude_budget_suffix_exactly_at_warn_no_flag(tmp_path):
    # Boundary: strictly ">" -- a file sitting exactly ON CLAUDE_WARN is
    # NOT flagged (mirrors the BOOT_WARN/BREACH boundary convention).
    root = tmp_path
    _seed_boot_files(root, {"README.md": 100, "CLAUDE.md": sc.CLAUDE_WARN})
    lines = sc.boot_budget_lines(root)
    assert lines[0].endswith(f"| CLAUDE.md: {sc.CLAUDE_WARN}/{sc.CLAUDE_WARN}")
    assert "OVER" not in lines[0]


def test_claude_budget_suffix_over_warn_flags_over(tmp_path):
    # Boundary + 1: crosses strictly over CLAUDE_WARN -> OVER flag fires.
    root = tmp_path
    _seed_boot_files(root, {"README.md": 100, "CLAUDE.md": sc.CLAUDE_WARN + 1})
    lines = sc.boot_budget_lines(root)
    assert lines[0].endswith(
        f"| CLAUDE.md: {sc.CLAUDE_WARN + 1}/{sc.CLAUDE_WARN}"
        " OVER -> boot-diet (CLAUDE layer)"
    )


def test_claude_budget_suffix_missing_claude_md(tmp_path):
    root = tmp_path
    # No BOOT.md, no CLAUDE.md -- boot_path_files() still always appends
    # CLAUDE.md (D-0041); its stat() fails, and the suffix reports the
    # gap explicitly rather than reading as "under budget".
    lines = sc.boot_budget_lines(root)
    assert lines[0] == (
        "BOOT BUDGET: 0 bytes / 100000 (1 files) [missing: CLAUDE.md]"
        " | CLAUDE.md: missing"
    )


def test_boot_budget_lines_within_output_budget(tmp_path):
    root = tmp_path
    _seed_boot_files(
        root,
        {
            "README.md": 60000,
            "PROJECT_CHARTER.md": 30000,
            "ANTI_GOALS.md": 20000,
            "CLAUDE.md": 100,
        },
    )
    lines = sc.boot_budget_lines(root)
    assert len(lines) <= 4  # 1 summary + top-3, never more


# ==== t-043: full assembly still ASCII and within MAX_LINES =========


def test_build_context_lines_b3_ascii_and_within_max_lines(tmp_path):
    root = _seed_repo(
        tmp_path,
        events=[_event("delegated", task_id="t-001"), _event("calibrated", ts="2026-07-08T00:00:00")],
    )
    _seed_boot_files(
        root,
        {
            "README.md": 60000,
            "PROJECT_CHARTER.md": 30000,
            "ANTI_GOALS.md": 20000,
            "CLAUDE.md": 100,
        },
    )
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    lines = sc.build_context_lines(root, now, stdin_payload={"model": "claude-fable-5"})
    assert len(lines) <= sc.MAX_LINES
    for line in lines:
        line.encode("ascii")  # must not raise
        assert line.isascii()
    assert any(l.startswith("MODEL:") for l in lines)
    assert any(l.startswith("BOOT BUDGET:") for l in lines)


def test_build_context_lines_malicious_stdin_payload_stays_ascii_single_line(tmp_path):
    # t-043 attempt 2 (critic-confirmed): a malicious/garbled model id in
    # the hook's stdin payload must not break the ASCII/single-line
    # invariant of ANY line in the assembled context, nor inject extra
    # lines past MAX_LINES via embedded '\n'.
    root = _seed_repo(
        tmp_path,
        events=[_event("delegated", task_id="t-001")],
    )
    now = datetime.datetime(2026, 7, 11, 9, 0, 0)
    lines = sc.build_context_lines(
        root, now, stdin_payload={"model": "клод\nX\U0001F600" + ("y" * 200)}
    )
    for line in lines:
        assert line.isascii()
        assert "\n" not in line
        assert len(line.splitlines()) == 1
    assert len(lines) <= sc.MAX_LINES


def test_main_b3_success_path_includes_model_and_boot_budget(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path, events=[_event("delegated", task_id="t-001")])
    _seed_boot_files(root, {"README.md": 100, "CLAUDE.md": 50})
    fake = _FakeStdin(json.dumps({"model": "claude-sonnet-5"}), tty=False)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert any(l.startswith("MODEL: claude-sonnet-5 -> tier builder-tier") for l in out)
    assert any(l.startswith("BOOT BUDGET:") for l in out)
    assert len(out) <= sc.MAX_LINES


# ==== D-0076: OPEN DISPATCH lines ====================================


def test_open_dispatches_delegated_last_is_open():
    events = [_event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001")]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"
    assert opens[0]["event"] == "delegated"


def test_open_dispatches_accepted_closes():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("accepted", ts="2026-07-10T08:10:00", agent="builder", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_retry_branch_open():
    # delegated -> rejected -> delegated (attempt 2) = still open: the
    # last lifecycle event for t-001 is 'delegated'.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("rejected", ts="2026-07-10T08:10:00", agent="builder", task_id="t-001",
               attempt=1, failure_class="spec"),
        _event("delegated", ts="2026-07-10T08:20:00", agent="builder", task_id="t-001",
               attempt=2),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["ts"] == "2026-07-10T08:20:00"


def test_open_dispatches_continuation_open():
    # delegated to builder, then delegated to critic (acceptance-gate
    # entry) on the same task_id = still open: last event is 'delegated'.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("delegated", ts="2026-07-10T08:10:00", agent="critic", task_id="t-001"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["agent"] == "critic"


def test_open_dispatches_decomposable_closes():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("decomposable", ts="2026-07-10T08:10:00", agent="builder", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_escalated_closes():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("escalated", ts="2026-07-10T08:10:00", agent="builder", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_dispatch_skipped_never_opens():
    # dispatch_skipped is outside _OPEN_LIFECYCLE_EVENTS entirely -- it
    # neither opens nor closes a task_id, even with no delegated at all.
    events = [_event("dispatch_skipped", ts="2026-07-10T08:00:00", agent="scout",
                     task_id="t-001")]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_file_order_lies_ts_wins():
    # t-029 mirror (F1 blocker, attempt 2): a retroactive `delegated` was
    # inserted mid-file via Edit -- it physically sits AFTER its closing
    # `accepted` in the journal, but its ts is earlier. File position must
    # NOT decide "last" here; ts is the true order, so the task is CLOSED.
    events = [
        _event("delegated", ts="2026-07-10T09:23:00", agent="builder", task_id="t-001"),
        _event("accepted", ts="2026-07-10T09:30:00", agent="builder", task_id="t-001"),
        _event("delegated", ts="2026-07-10T09:03:00", agent="builder", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_same_ts_later_line_wins():
    # Retro pairs (D-0056b) write delegated and its closing event with the
    # SAME ts -- the tie must break by file position (later line wins), so
    # a delegated+accepted pair sharing one ts is closed...
    events = [
        _event("delegated", ts="2026-07-10T09:00:00", agent="builder", task_id="t-001"),
        _event("accepted", ts="2026-07-10T09:00:00", agent="builder", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []

    # ...while a single delegated at that same ts, with nothing after it,
    # stays open.
    events_open = [
        _event("delegated", ts="2026-07-10T09:00:00", agent="builder", task_id="t-001"),
    ]
    opens = sc.open_dispatches(events_open)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"


def test_open_dispatches_accepted_closes_even_when_ts_lies():
    # t-007 mirror (t-097 escalation): the delegated's ts was WRITTEN
    # WRONG (later than the accepted's ts), and the accepted physically
    # follows it -- ts lies, file position is true. The opposite of
    # t-029. No ordering rule resolves both; journal LAW does: any
    # `accepted` closes its task unconditionally (reopen is forbidden,
    # D-0060), regardless of ts or position.
    events = [
        _event("delegated", ts="2026-07-09T13:05:00", agent="scout", task_id="t-001"),
        _event("accepted", ts="2026-07-09T12:37:30", agent="scout", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatch_lines_cap_three_plus_summary():
    events = [
        _event("delegated", ts=f"2026-07-10T08:0{i}:00", agent="builder", task_id=f"t-00{i}")
        for i in range(1, 6)
    ]
    lines = sc.open_dispatch_lines(events)
    assert len(lines) == 4
    assert lines[0].startswith("OPEN DISPATCH: t-001")
    assert lines[1].startswith("OPEN DISPATCH: t-002")
    assert lines[2].startswith("OPEN DISPATCH: t-003")
    assert lines[3] == "OPEN DISPATCHES: 5 total, 2 more not shown"


def test_open_dispatch_lines_sanitizes_external_values():
    events = [_event("delegated", ts="2026-07-10T08:00:00", agent="строитель",
                     task_id="t-001")]
    lines = sc.open_dispatch_lines(events)
    assert lines
    for line in lines:
        assert line.isascii()
        assert "\n" not in line


def test_open_dispatch_lines_empty_journal():
    assert sc.open_dispatch_lines([]) == []


# ==== t-133 remainder: closes:t-NNN marker convention =================


def test_open_dispatches_closes_marker_in_later_lifecycle_event_closes_delegated():
    # A closes: token can sit in the notes of ANY later event, including
    # a lifecycle event for a DIFFERENT task -- t-002's own event stays
    # closed too (its last lifecycle event is 'rejected', not 'delegated').
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("rejected", ts="2026-07-10T09:00:00", agent="builder", task_id="t-002",
               attempt=1, failure_class="spec", notes="closes:t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_closes_marker_in_non_lifecycle_event_closes():
    # calibrated is outside _OPEN_LIFECYCLE_EVENTS -- it must not open or
    # close anything BY ITS TYPE, but its notes are still scanned.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes:t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_multiple_closes_tokens_in_one_notes():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("delegated", ts="2026-07-10T08:05:00", agent="scout", task_id="t-002"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes:t-001 closes:t-002"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_delegated_after_closes_marker_reopens():
    # Retry/replacement: a delegated LATER than the marker reopens the
    # task, same as a retry does past a rejected event.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-10T08:30:00", notes="closes:t-001"),
        _event("delegated", ts="2026-07-10T09:00:00", agent="builder", task_id="t-001", attempt=2),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["ts"] == "2026-07-10T09:00:00"


def test_open_dispatches_closes_marker_on_nonexistent_task_is_harmless():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes:t-999"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"


# ---- closes: marker format boundaries (exact, like replaces_worker:) --


def test_open_dispatches_closes_marker_trailing_comma_still_closes():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-133"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes:t-133, done"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_closes_marker_space_after_colon_does_not_close():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-133"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes: t-133"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-133"


def test_open_dispatches_closes_marker_wrong_prefix_does_not_close():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-133"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes:x-133"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-133"


def test_open_dispatches_closes_marker_wrong_case_does_not_close():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-133"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="CLOSES:t-133"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-133"


# ---- t-325 (P1, внешнее ревью, attempt 2): GATE BREAK-GLASS surfacing ----
# tools/main_gate.py and tools/dod_gate.py's "skip the 3rd consecutive
# block" safety valve now APPENDS a persistent unsafe_completion fact into
# the dod_track file itself (sibling edit, same task; new plural
# "unsafe_completions" list key, "unsafe_completion" singular kept readable
# for backward compat). This block is the surfacing half -- see
# session_context.py's own docstring above _break_glass_candidates() for
# the full attempt-2 rationale (ack-only-shown-lines, the 5-line cap,
# the read-only-tracks + sidecar-ack fix, and the list-not-overwrite fix).


def _write_dod_track(track_dir: Path, session_id: str, data: dict) -> Path:
    track_dir.mkdir(parents=True, exist_ok=True)
    path = track_dir / f"{session_id}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _read_ack_sidecar(track_dir: Path) -> dict:
    path = track_dir / "break_glass_ack.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def test_break_glass_lines_no_dod_track_dir_is_silent(tmp_path):
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_empty_dod_track_dir_is_silent(tmp_path):
    (tmp_path / ".claude" / "dod_track").mkdir(parents=True)
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_track_without_any_unsafe_completion_is_silent(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-clean",
        {"edits": [], "runs": [], "main_gate_state": {"consecutive_blocks": 0}},
    )
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_surfaces_main_gate_unsafe_completion(tmp_path):
    # Legacy singular key ("unsafe_completion") -- backward-compat read
    # path (point 4).
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-a",
        {
            "main_gate_state": {
                "consecutive_blocks": 0,
                "unsafe_completion": {"ts": "2026-07-24T10:00:00.000000", "reason": "no-green-run"},
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0].startswith("GATE BREAK-GLASS:")
    assert "sess-a" in lines[0]
    assert "main" in lines[0]
    assert "no-green-run" in lines[0]
    assert lines[0].isascii()


def test_break_glass_lines_surfaces_dod_gate_unsafe_completion_per_agent(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-b",
        {
            "gate_state": {
                "per_agent": {
                    "agent-1": {
                        "consecutive_blocks": 0,
                        "unsafe_completion": {
                            "ts": "t1",
                            "reason": "no-green-run",
                            "agent_id": "agent-1",
                        },
                    }
                }
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 1
    assert "sess-b" in lines[0]
    assert "dod" in lines[0]


def test_break_glass_lines_surfaces_multiple_agents_in_same_track(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-multi",
        {
            "gate_state": {
                "per_agent": {
                    "agent-1": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}},
                    "agent-2": {"unsafe_completion": {"ts": "t2", "reason": "green-before-last-edit"}},
                }
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 2


def test_break_glass_lines_reads_new_plural_list_key_multiple_facts(tmp_path):
    # New shape (attempt 2, point 4): "unsafe_completions" is a LIST --
    # every fact in it must surface, not just the last one.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-list",
        {
            "main_gate_state": {
                "unsafe_completions": [
                    {"ts": "t1", "reason": "no-green-run"},
                    {"ts": "t2", "reason": "green-before-last-edit"},
                ]
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 2
    assert any("no-green-run" in l for l in lines)
    assert any("green-before-last-edit" in l for l in lines)


def test_break_glass_lines_reads_both_legacy_singular_and_new_plural_keys(tmp_path):
    # Tolerance for a track file carrying BOTH shapes at once (e.g. one
    # fact written before the plural-key fix, one after) -- both surface.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-mixed-keys",
        {
            "main_gate_state": {
                "unsafe_completion": {"ts": "t0", "reason": "legacy"},
                "unsafe_completions": [{"ts": "t1", "reason": "no-green-run"}],
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 2


# ---- point 3 (D-0060): tracks are READ-ONLY, ack lives in the sidecar ----


def test_break_glass_lines_does_not_modify_the_track_file(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    path = _write_dod_track(
        track_dir,
        "sess-c",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    original_bytes = path.read_bytes()
    sc.break_glass_lines(tmp_path)
    assert path.read_bytes() == original_bytes


def test_break_glass_lines_never_writes_to_any_track_file(tmp_path):
    # Critic-required invariant (point 3): scanning MULTIPLE track files
    # must leave every one of them byte-for-byte unchanged.
    track_dir = tmp_path / ".claude" / "dod_track"
    paths = [
        _write_dod_track(
            track_dir,
            f"sess-ro-{i}",
            {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
        )
        for i in range(3)
    ]
    originals = {p: p.read_bytes() for p in paths}
    sc.break_glass_lines(tmp_path)
    for p, original in originals.items():
        assert p.read_bytes() == original


def test_break_glass_lines_records_acknowledgement_in_sidecar_file(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-c",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    sc.break_glass_lines(tmp_path)
    ack = _read_ack_sidecar(track_dir)
    assert len(ack) == 1
    # Key carries a trailing fact-index (critic-gate accept-with-fixup:
    # "ts" alone can collide -- see _unsafe_completion_facts' docstring);
    # legacy singular key -> index 0.
    assert "sess-c:main::t1:0" in ack
    assert ack["sess-c:main::t1:0"]  # non-empty ack timestamp


def test_break_glass_lines_ignores_its_own_sidecar_file_as_a_track(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "break_glass_ack.json").write_text("{}", encoding="utf-8")
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_repeat_call_is_silent_exactly_once_boundary(tmp_path):
    # DoD (г): the same fact must surface EXACTLY ONCE -- a second scan of
    # the same (now-acknowledged-in-the-sidecar) file is silent.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-d",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    first = sc.break_glass_lines(tmp_path)
    assert len(first) == 1
    second = sc.break_glass_lines(tmp_path)
    assert second == []


def test_break_glass_lines_preexisting_sidecar_ack_never_reprints(tmp_path):
    # A fact already acknowledged in the SIDECAR (e.g. by a previous
    # SessionStart process) must not print even on this process's very
    # first scan.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-e",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    (track_dir / "break_glass_ack.json").write_text(
        json.dumps({"sess-e:main::t1:0": "2026-07-24T09:00:00.000000"}), encoding="utf-8"
    )
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_two_facts_with_identical_ts_get_distinct_ack_keys(tmp_path):
    # Critic-gate probe (attempt-2 accept-with-fixup): two facts of the
    # same session/gate/agent can carry a byte-identical "ts" (Windows
    # wall-clock granularity). Without the index in the ack key, the
    # SECOND fact would silently collapse onto the first's key and never
    # surface once the first is acknowledged. Both facts here share the
    # exact same ts string.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-dup-ts",
        {
            "main_gate_state": {
                "unsafe_completions": [
                    {"ts": "2026-07-24T10:00:00.000000", "reason": "no-green-run"},
                    {"ts": "2026-07-24T10:00:00.000000", "reason": "green-before-last-edit"},
                ]
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 2
    ack = _read_ack_sidecar(track_dir)
    assert len(ack) == 2  # two DISTINCT keys, not collapsed into one

    # Nothing left pending -- both were shown and acked.
    assert sc.break_glass_lines(tmp_path) == []


def test_select_and_ack_identical_ts_facts_budget_cut_between_them_shows_only_first(tmp_path):
    # Exact reproduction of the coordinator's requested boundary: two
    # facts with a byte-identical ts, space_left=1 -- only the FIRST is
    # shown and acked; the second must resurface on the next call, not be
    # silently swallowed by a collapsed ack key.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-dup-ts-budget",
        {
            "main_gate_state": {
                "unsafe_completions": [
                    {"ts": "2026-07-24T10:00:00.000000", "reason": "no-green-run"},
                    {"ts": "2026-07-24T10:00:00.000000", "reason": "green-before-last-edit"},
                ]
            }
        },
    )
    filler = ["x"] * (sc.MAX_LINES - 1)  # space_left == 1
    shown = sc.select_and_ack_break_glass_lines(tmp_path, filler)
    assert len(shown) == 1
    assert "no-green-run" in shown[0]

    remaining = sc.select_and_ack_break_glass_lines(tmp_path, [])
    assert len(remaining) == 1
    assert "green-before-last-edit" in remaining[0]


def test_break_glass_lines_broken_json_file_does_not_block_sibling(tmp_path):
    # DoD (д): a corrupt track file next to a good one must not hide the
    # good one's fact.
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-broken.json").write_text("{not valid json", encoding="utf-8")
    _write_dod_track(
        track_dir,
        "sess-ok",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 1
    assert "sess-ok" in lines[0]


def test_break_glass_lines_non_dict_json_file_is_skipped(tmp_path):
    # Adversarial: a track file whose top-level JSON value is a list (or
    # any non-dict) must not crash the scan.
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-list.json").write_text("[1, 2, 3]", encoding="utf-8")
    _write_dod_track(
        track_dir,
        "sess-ok2",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 1
    assert "sess-ok2" in lines[0]


def test_break_glass_lines_ignores_non_json_files_in_dod_track_dir(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "README.txt").write_text("not a track file", encoding="utf-8")
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_sanitizes_non_ascii_reason(tmp_path):
    # reason/ts are journal/track-sourced (a hook could in principle carry
    # anything) -- same ASCII discipline as MODEL/OPEN DISPATCH/WIRING.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-cyr",
        {
            "main_gate_state": {
                "unsafe_completion": {"ts": "t1", "reason": "причина-с-кириллицей"}
            }
        },
    )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0].isascii()


# ---- point 2: CAP at 5 fact lines + trailing summary line ----------------


def test_break_glass_lines_cap_boundary_exactly_five_no_summary_line(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    for i in range(5):
        _write_dod_track(
            track_dir,
            f"sess-{i:02d}",
            {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
        )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 5
    assert not any("more unsafe-completion facts pending" in l for l in lines)


def test_break_glass_lines_cap_limits_to_five_plus_summary_line(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    for i in range(7):
        _write_dod_track(
            track_dir,
            f"sess-{i:02d}",
            {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
        )
    lines = sc.break_glass_lines(tmp_path)
    assert len(lines) == 6  # 5 facts + 1 summary
    fact_lines = [l for l in lines if l.startswith("GATE BREAK-GLASS: session")]
    summary_lines = [l for l in lines if "more unsafe-completion facts pending" in l]
    assert len(fact_lines) == 5
    assert len(summary_lines) == 1
    assert "2 more" in summary_lines[0]


def test_break_glass_lines_cap_remainder_not_acked_resurfaces_next_call(tmp_path):
    # Point 2: facts beyond the cap are NOT acked -- they must surface on
    # a later call once the earlier ones have been acknowledged.
    track_dir = tmp_path / ".claude" / "dod_track"
    for i in range(7):
        _write_dod_track(
            track_dir,
            f"sess-{i:02d}",
            {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
        )
    first = sc.break_glass_lines(tmp_path)
    assert len(first) == 6  # 5 facts + summary

    second = sc.break_glass_lines(tmp_path)
    assert len(second) == 2
    assert all(l.startswith("GATE BREAK-GLASS: session") for l in second)

    third = sc.break_glass_lines(tmp_path)
    assert third == []


# ---- point 1: ack ONLY lines surviving the MAX_LINES cut ------------------


def test_select_and_ack_break_glass_lines_no_space_left_does_not_ack(tmp_path):
    # Lead ruling point 1's own test boundary: the preceding context lines
    # already fill the whole MAX_LINES budget -> the pending fact must be
    # neither shown NOR acked -- it must resurface once space frees up.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-full",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    filler = ["x"] * sc.MAX_LINES
    shown = sc.select_and_ack_break_glass_lines(tmp_path, filler)
    assert shown == []

    shown_again = sc.select_and_ack_break_glass_lines(tmp_path, [])
    assert len(shown_again) == 1
    assert shown_again[0].startswith("GATE BREAK-GLASS:")


def test_select_and_ack_break_glass_lines_partial_space_acks_only_shown(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    for i in range(3):
        _write_dod_track(
            track_dir,
            f"sess-p{i}",
            {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
        )
    # Exactly 2 slots left out of MAX_LINES -- 3 facts pending, only 2 fit.
    filler = ["x"] * (sc.MAX_LINES - 2)
    shown = sc.select_and_ack_break_glass_lines(tmp_path, filler)
    assert len(shown) == 2

    # The unshown third fact must resurface with room to spare.
    remaining = sc.select_and_ack_break_glass_lines(tmp_path, [])
    assert len(remaining) == 1


def test_select_and_ack_break_glass_lines_exact_boundary_one_slot_short(tmp_path):
    # Adjacent boundary to the "no space at all" case: MAX_LINES - 1 slots
    # used, exactly 1 left -- the single pending fact DOES fit and IS acked.
    track_dir = tmp_path / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-boundary",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    filler = ["x"] * (sc.MAX_LINES - 1)
    shown = sc.select_and_ack_break_glass_lines(tmp_path, filler)
    assert len(shown) == 1

    shown_again = sc.select_and_ack_break_glass_lines(tmp_path, [])
    assert shown_again == []  # already acked -- does not resurface


def test_build_context_lines_includes_break_glass_line(tmp_path):
    root = _seed_repo(tmp_path, events=[_event("delegated", task_id="t-001")])
    track_dir = root / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-live",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    lines = sc.build_context_lines(root)
    assert any(l.startswith("GATE BREAK-GLASS:") for l in lines)


def test_build_context_lines_no_break_glass_line_when_none_pending(tmp_path):
    root = _seed_repo(tmp_path, events=[_event("delegated", task_id="t-001")])
    lines = sc.build_context_lines(root)
    assert not any(l.startswith("GATE BREAK-GLASS:") for l in lines)


def test_main_prints_break_glass_line_once_then_silent_on_rerun(tmp_path, capsys):
    # DoD (в) + (г) at the main()/SessionStart level: prints once, silent
    # on the next SessionStart of the same repo state.
    root = _seed_repo(tmp_path, events=[_event("delegated", task_id="t-001")])
    track_dir = root / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-live",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )

    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out
    assert "GATE BREAK-GLASS:" in out

    code2 = sc.main(root)
    assert code2 == 0
    out2 = capsys.readouterr().out
    assert "GATE BREAK-GLASS:" not in out2


def test_open_dispatches_closes_marker_inside_longer_word_does_not_close():
    # Critic-gate finding (t-133 remainder attempt 2): an unanchored
    # regex would match "closes:" INSIDE "discloses:" too -- the
    # dangerous direction, a silent false close of a task nobody meant
    # to close. Left-anchor ((?<!\w)) must reject this.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="discloses:t-001"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"


def test_open_dispatches_closes_marker_at_start_of_notes_closes():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="closes:t-001 done"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_closes_marker_after_punctuation_closes():
    # A non-word character (here: an opening parenthesis) immediately
    # before "closes:" is legal -- only a preceding word character
    # (letter/digit/underscore, as in "discloses:") is rejected.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-10T09:00:00", notes="see (closes:t-001) for context"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_empty_notes_harmless():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001", notes=""),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"


def test_open_dispatches_absent_notes_harmless():
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"


def test_open_dispatches_closes_marker_in_own_delegated_notes_closes_via_contract():
    # Contract (c) from the spec: a closes:t-X token in the notes of
    # task X's OWN delegated event is a mis-written journal line, but
    # the documented deterministic behavior is that the marker wins at
    # the tie -- (ts, idx, 1) > (ts, idx, 0) -- so this delegated is
    # treated as already closed, not open.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001",
               notes="closes:t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_non_string_notes_does_not_raise():
    # Adversarial input: a malformed journal line where notes ended up
    # a number or None in JSON (not the contractual string) must not
    # crash open_dispatches() with a TypeError from re.findall.
    events = [
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001", notes=12345),
        _event("calibrated", ts="2026-07-10T09:00:00", notes=None),
    ]
    opens = sc.open_dispatches(events)
    assert len(opens) == 1
    assert opens[0]["task_id"] == "t-001"


def test_build_context_lines_shows_open_dispatch(tmp_path):
    events = [
        _event("lead_degraded", ts="2026-07-10T07:30:00"),
        _event("delegated", ts="2026-07-10T08:00:00", agent="builder", task_id="t-001"),
        _event("calibrated", ts="2026-07-08T00:00:00"),
    ]
    root = _seed_repo(tmp_path, events=events)
    now = datetime.datetime(2026, 7, 10, 12, 0, 0)
    lines = sc.build_context_lines(root, now)
    assert any(l.startswith("OPEN DISPATCH: t-001") for l in lines)
    degradation_idx = next(i for i, l in enumerate(lines) if l.startswith("OPEN DEGRADATION WINDOW"))
    dispatch_idx = next(i for i, l in enumerate(lines) if l.startswith("OPEN DISPATCH:"))
    calibration_idx = next(i for i, l in enumerate(lines) if l.startswith("Last calibration:"))
    assert degradation_idx < dispatch_idx < calibration_idx
    assert len(lines) <= sc.MAX_LINES
    for line in lines:
        assert line.isascii()
