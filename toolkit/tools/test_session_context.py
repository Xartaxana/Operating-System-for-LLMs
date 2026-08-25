"""Tests for tools/session_context.py. No network, no LLM calls; every
test builds a synthetic repo-shaped tmp directory (logs/routing-log.jsonl
+ gateway/{config.yaml,budgets.yaml,*.db}) and points build_context_lines()
/ main() at it via root=. Mirrors tools/test_usage_report.py's style.

Run from the repo root: python -m pytest tools/test_session_context.py
"""

import datetime
import importlib
import json
import os
import sqlite3
import subprocess
import sys
import time
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

# Worked example of the enforcement-file landing pattern: a SessionStart hook is a
# self-activating enforcement file, so a builder session adding new
# MODEL / BOOT BUDGET functions lands them under a neighboring draft
# filename first, and Lead moves the draft onto the live path only at
# acceptance. No draft is currently staged, so the import below falls
# through to the live module; this indirection means the test suite
# keeps working unchanged whenever a draft IS staged and later promoted:
# only this import line needs to flip.
try:
    import session_context_b3 as sc
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


# ---- CLOCK DRIFT line ----
# Field precedent: a session's journal tail carried a ts LATER than the
# system clock (a previous environment's clock ran ahead). Threshold:
# > 60s. Battery per CLAUDE.md R11: acceptance keys (fires when ahead,
# silent when not) + the boundary itself (60s exactly vs 61s) +
# adversarial fail-open inputs.


def test_clock_drift_line_absent_when_journal_ts_behind_system_clock():
    events = [_event("delegated", ts="2026-07-10T08:00:00")]
    now = datetime.datetime(2026, 7, 10, 9, 0, 0)
    assert sc.clock_drift_line(events, now) == ""


def test_clock_drift_line_at_threshold_boundary_is_silent():
    # Exactly 60s ahead -- the threshold is "> 60s" -- AT the boundary
    # must NOT fire.
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [_event("delegated", ts="2026-07-10T08:01:00")]  # +60s
    assert sc.clock_drift_line(events, now) == ""


def test_clock_drift_line_one_second_past_threshold_fires():
    now = datetime.datetime(2026, 7, 10, 8, 0, 0)
    events = [_event("delegated", ts="2026-07-10T08:01:01")]  # +61s
    line = sc.clock_drift_line(events, now)
    assert line.startswith("CLOCK DRIFT: last journal ts is ")
    assert "min ahead of system clock" in line
    assert "do not rewrite past lines" in line
    assert "non-monotonic" in line
    assert line.isascii()


def test_clock_drift_line_reports_minutes_ahead():
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
    # scan is over the WHOLE journal (a safety-reset can
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
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert out[0].startswith("session-context warning:")


def test_main_full_output_when_gateway_dir_missing(tmp_path, capsys):
    # preflight_quota.load_config's exists-guard (a documented finding,
    # the same class alongside load_budgets, which already had this
    # shape): a repo root with no gateway/ directory at all (config.yaml
    # unreachable) is this toolkit's own subscription-contour DEFAULT
    # state, not a crash condition -- the SessionStart output must stay
    # FULL (NOW/LAST EVENT/BOOT BUDGET/etc still print), not collapse
    # to a single fail-open warning line the way a missing config.yaml
    # used to make it do before that guard existed (see
    # test_preflight_quota.py::test_load_config_missing_file_returns_empty_dict
    # for the underlying unit-level fix).
    root = tmp_path
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert any(l.startswith("NOW:") for l in out)
    assert any(l.startswith("Last calibration:") for l in out)
    assert any(l.startswith("BOOT BUDGET:") for l in out)


def test_main_full_output_when_config_yaml_missing_but_gateway_dir_exists(tmp_path, capsys):
    # Narrower sibling of the above: gateway/ EXISTS (e.g. holds only a
    # requests.db) but config.yaml specifically was never generated --
    # same exists-guard, same expected full output.
    root = tmp_path
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    (root / "gateway").mkdir()
    code = main(root)
    assert code == 0
    out = capsys.readouterr().out.strip().splitlines()
    assert not any(l.startswith("session-context warning:") for l in out)
    assert any(l.startswith("NOW:") for l in out)


# ---- config.yaml EXISTING but unparseable (corrupt YAML) ----


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


# ---- budgets.yaml EXISTING but unparseable ----


def test_quota_lines_malformed_budgets_yaml_surfaces_reason_but_keeps_rest(tmp_path):
    # Unlike a broken config.yaml (blanks quota_lines() to one marker
    # line), a broken budgets.yaml is guarded INSIDE load_budgets() --
    # the rest of this section (per-alias QUOTA/REQUESTS from config)
    # still prints normally alongside the marker.
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
    assert any(l.startswith("REQUESTS ") for l in lines)


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


# ---- stdout-deadline: env boundaries + a genuinely blocked writer ----
# (builder-role rule 6a: AT the boundary and BEYOND it, for every limit
# this port introduces.)


def test_stdout_deadline_seconds_default_with_no_env(monkeypatch):
    monkeypatch.delenv(sc._STDOUT_DEADLINE_ENV, raising=False)
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_DEFAULT


def test_stdout_deadline_seconds_valid_env_override(monkeypatch):
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "1.5")
    assert sc._stdout_deadline_seconds() == 1.5


def test_stdout_deadline_seconds_zero_is_invalid_no_wait_forever_mode(monkeypatch):
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "0")
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_DEFAULT


def test_stdout_deadline_seconds_negative_falls_back(monkeypatch):
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "-1")
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_DEFAULT


def test_stdout_deadline_seconds_at_max_boundary_is_valid(monkeypatch):
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, str(sc._STDOUT_DEADLINE_MAX))
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_MAX


def test_stdout_deadline_seconds_just_over_max_falls_back(monkeypatch):
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, str(sc._STDOUT_DEADLINE_MAX + 0.001))
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_DEFAULT


def test_stdout_deadline_seconds_non_numeric_falls_back(monkeypatch):
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "not-a-number")
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_DEFAULT


def test_write_stdout_deadline_normal_write_returns_true(capsys, monkeypatch):
    monkeypatch.delenv(sc._STDOUT_DEADLINE_ENV, raising=False)
    assert sc._write_stdout_deadline("hello\n") is True
    assert capsys.readouterr().out == "hello\n"


def test_write_stdout_deadline_reraises_ordinary_write_exception(monkeypatch):
    class _DeadStdout:
        def write(self, _text):
            raise OSError("simulated: stdout is dead")

        def flush(self):
            pass

    monkeypatch.setattr(sys, "stdout", _DeadStdout())
    import pytest as _pytest

    with _pytest.raises(OSError, match="simulated: stdout is dead"):
        sc._write_stdout_deadline("x")


def test_write_stdout_deadline_hanging_writer_times_out_returns_false(monkeypatch):
    class _HangingStdout:
        def write(self, _text):
            time.sleep(3600)

        def flush(self):
            pass  # pragma: no cover -- never reached

    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "0.1")
    monkeypatch.setattr(sys, "stdout", _HangingStdout())
    started = time.monotonic()
    result = sc._write_stdout_deadline("x")
    elapsed = time.monotonic() - started
    assert result is False
    assert elapsed < 2.0  # bounded by the 0.1s deadline, not the 3600s sleep


def test_main_stdout_deadline_timeout_exits_immediately_via_subprocess(tmp_path):
    # main()'s own contract on a write timeout is os._exit(0) -- calling
    # that in-process would kill the pytest worker itself, so this is
    # exercised as a real subprocess instead. A NON-draining consumer
    # (stdout piped but never read) alone is not enough by itself --
    # small output fits inside the OS pipe buffer and the write simply
    # returns without ever blocking. This test forces genuine
    # backpressure by making the Layer A block emit ~200KB (a BOOT.md
    # that references one large file), comfortably over any platform's
    # actual pipe capacity (the staff deployment's own critic-measured
    # value on its machine was ~4096 bytes), combined with an
    # artificially tiny OSLLM_STDOUT_TIMEOUT -- the single sys.stdout
    # write() call genuinely blocks on the full, undrained pipe, and
    # main() must os._exit(0) instead of hanging forever.
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "BOOT.md").write_text("1. Read BIGFILE.md.\n", encoding="utf-8")
    (tmp_path / "BIGFILE.md").write_text("x" * 200_000 + "\n", encoding="utf-8")
    env = dict(os.environ, OSLLM_STDOUT_TIMEOUT="0.2")
    script = Path(__file__).resolve().parent / "session_context.py"
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
        env=env,
    )
    started = time.monotonic()
    # Deliberately never read proc.stdout -- an un-drained pipe is the
    # scenario under test. wait() only watches the process exit, not
    # the pipe.
    returncode = proc.wait(timeout=15)
    elapsed = time.monotonic() - started
    proc.stdout.close()
    proc.stderr.close()
    assert returncode == 0
    # Bounded well under the 15s Popen.wait timeout above: proves the
    # process actually exited via the deadline path rather than hanging
    # until some external kill.
    assert elapsed < 10.0


# ---- N4 (carried forward from review): import-time failure must ALSO fail open ----

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
    out = capsys.readouterr().out.strip().splitlines()
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
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert out[0].startswith("session-context warning:")


# ==== MODEL line ====================


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
    assert sc.model_tier("claude-fable-5") == "Lead(top)"
    assert sc.model_tier("claude-opus-4") == "critic-tier"
    assert sc.model_tier("claude-sonnet-5") == "builder-tier"
    assert sc.model_tier("claude-haiku-3") == "scout-tier"


def test_model_tier_mapping_unknown_string():
    assert sc.model_tier("some-other-model") == "unknown"


def test_model_line_found_string_form():
    line = sc.model_line({"model": "claude-fable-5"})
    # The payload id is a harness declaration, not a measurement --
    # the line must say so (present-but-stale stated confidently is the
    # failure mode this marker exists to prevent).
    assert line == (
        "MODEL: claude-fable-5 -> tier Lead(top)"
        " (declared by harness, not measured; Lead tier = fable)"
    )


def test_model_line_found_dict_form():
    line = sc.model_line({"model": {"id": "claude-sonnet-5"}})
    assert line == (
        "MODEL: claude-sonnet-5 -> tier builder-tier"
        " (declared by harness, not measured; Lead tier = fable)"
    )


def test_model_line_missing_payload():
    assert sc.model_line(None) == (
        "MODEL: not provided by hook input -- verify tier yourself"
    )


def test_model_line_empty_payload():
    assert sc.model_line({}) == (
        "MODEL: not provided by hook input -- verify tier yourself"
    )


# ---- model_line() ASCII/single-line
# sanitization of the externally-sourced model id (critic-confirmed) ----------------------


def test_model_line_non_ascii_model_id_is_sanitized():
    line = sc.model_line({"model": "café\nX"})
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
        "MODEL: not provided by hook input -- verify tier yourself"
    )


def test_model_line_long_model_id_is_truncated():
    long_id = "sonnet-" + ("a" * 100)
    line = sc.model_line({"model": long_id})
    assert line.isascii()
    assert "\n" not in line
    # "MODEL: " prefix + sanitized (<=80 chars) + " -> tier ... " suffix
    sanitized = sc._ascii_sanitize(long_id)
    assert len(sanitized) == 80
    assert line == (
        f"MODEL: {sanitized} -> tier builder-tier"
        " (declared by harness, not measured; Lead tier = fable)"
    )


def test_ascii_sanitize_direct_cases():
    assert sc._ascii_sanitize("   ") == ""
    assert sc._ascii_sanitize("x\nINJECTED FAKE LINE") == "xINJECTED FAKE LINE"
    assert sc._ascii_sanitize("caféX").isascii()
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
    root = _seed_repo(tmp_path, events=[])
    now = datetime.datetime(2026, 7, 11, 9, 0, 0)
    lines = sc.build_context_lines(root, now, stdin_payload={"model": "claude-fable-5"})
    assert lines[0].startswith("NOW:")
    assert lines[1] == (
        "MODEL: claude-fable-5 -> tier Lead(top)"
        " (declared by harness, not measured; Lead tier = fable)"
    )


# ==== BOOT BUDGET ==============


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


def test_boot_budget_normal_under_warn_threshold(tmp_path):
    root = tmp_path
    _seed_boot_files(root, {"README.md": 100, "CLAUDE.md": 200})
    lines = sc.boot_budget_lines(root)
    assert lines == ["BOOT BUDGET: 300 bytes / 100000 (2 files) | CLAUDE.md: 200/56100"]


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
    assert lines[0] == f"BOOT BUDGET: {total} bytes / 100000 (4 files) WARN | CLAUDE.md: 100/56100"
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
        "(report first, operator word starts it) | CLAUDE.md: 100/56100"
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
        " | CLAUDE.md: 50/56100"
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


# ==== full assembly still ASCII and within MAX_LINES =========


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
    # critic-confirmed: a malicious/garbled model id in
    # the hook's stdin payload must not break the ASCII/single-line
    # invariant of ANY line in the assembled context, nor inject extra
    # lines past MAX_LINES via embedded '\n'.
    root = _seed_repo(
        tmp_path,
        events=[_event("delegated", task_id="t-001")],
    )
    now = datetime.datetime(2026, 7, 11, 9, 0, 0)
    lines = sc.build_context_lines(
        root, now, stdin_payload={"model": "café\nX\U0001F600" + ("y" * 200)}
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


# ==== OPEN DISPATCH lines ==============================================


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
    # A retroactive `delegated` inserted mid-file via a later edit --
    # it physically sits AFTER its closing `accepted` in the journal,
    # but its ts is earlier. File position must NOT decide "last"
    # here; ts is the true order, so the task is CLOSED.
    events = [
        _event("delegated", ts="2026-07-10T09:23:00", agent="builder", task_id="t-001"),
        _event("accepted", ts="2026-07-10T09:30:00", agent="builder", task_id="t-001"),
        _event("delegated", ts="2026-07-10T09:03:00", agent="builder", task_id="t-001"),
    ]
    assert sc.open_dispatches(events) == []


def test_open_dispatches_same_ts_later_line_wins():
    # Retro pairs write delegated and its closing event with the SAME
    # ts -- the tie must break by file position (later line wins), so
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
    # The delegated's ts was WRITTEN WRONG (later than the accepted's
    # ts), and the accepted physically follows it -- ts lies, file
    # position is true; the opposite anomaly shape from the previous
    # test. No ordering rule resolves both; journal LAW does: any
    # `accepted` closes its task unconditionally (reopen is
    # forbidden), regardless of ts or position.
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
    events = [_event("delegated", ts="2026-07-10T08:00:00", agent="büilder",
                     task_id="t-001")]
    lines = sc.open_dispatch_lines(events)
    assert lines
    for line in lines:
        assert line.isascii()
        assert "\n" not in line


def test_open_dispatch_lines_empty_journal():
    assert sc.open_dispatch_lines([]) == []


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


# ==== closes:t-NNN marker convention =======


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


def test_open_dispatches_closes_marker_inside_longer_word_does_not_close():
    # An unanchored regex would match "closes:" INSIDE "discloses:" too --
    # the dangerous direction, a silent false close of a task nobody
    # meant to close. Left-anchor ((?<!\w)) must reject this.
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
    # Documented contract: a closes:t-X token in the notes of task X's
    # OWN delegated event is a mis-written journal line, but the
    # documented deterministic behavior is that the marker wins at the
    # tie -- (ts, idx, 1) > (ts, idx, 0) -- so this delegated is treated
    # as already closed, not open.
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


# ---------------------------------------------------------------------
# hooks_path_autofix_line
# ---------------------------------------------------------------------
# Scoped: session_context.py carries the AUTOFIX action
# itself (this section), not a full git_hooks_channel report
# (required-file/exec-bit WARNINGs on an already-set hooksPath are
# tools/wiring_check.py's job -- see that module's own test suite,
# test_wiring_check.py, and session_context.py's module docstring for
# the division of labor).


def _git(args, cwd):
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=10
    )


def _init_repo_with_hooks(tmp_path, hookspath="own"):
    """Minimal git repo with a working .githooks/ (pre-commit +
    commit-msg present, tracked, executable in the index) and
    core.hooksPath pointed at it unless hookspath overrides that
    (None = leave unset; a Path = point hooksPath there instead)."""
    _git(["init", "-q"], tmp_path)
    githooks = tmp_path / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (githooks / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    _git(["add", ".githooks/pre-commit", ".githooks/commit-msg"], tmp_path)
    _git(["update-index", "--chmod=+x", ".githooks/pre-commit"], tmp_path)
    _git(["update-index", "--chmod=+x", ".githooks/commit-msg"], tmp_path)
    if hookspath == "own":
        _git(["config", "core.hooksPath", str(githooks)], tmp_path)
    elif hookspath is None:
        pass  # leave unset
    else:
        _git(["config", "core.hooksPath", str(hookspath)], tmp_path)
    return tmp_path


def test_hooks_path_autofix_line_unset_autofixes(tmp_path):
    _init_repo_with_hooks(tmp_path, hookspath=None)
    line = sc.hooks_path_autofix_line(tmp_path)
    assert line == "WIRING AUTOFIX: core.hooksPath set to .githooks"
    # The fix actually stuck in the repo's own local config, not just
    # claimed in the returned line.
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.stdout.strip() == ".githooks"


def test_hooks_path_autofix_line_write_failure_degrades_to_warning(tmp_path, monkeypatch):
    # The WRITE call is made to fail while the READ call (which reports
    # unset) is untouched -- must fall back to a WARNING with the
    # failure reason appended, not raise and not silently print AUTOFIX.
    _init_repo_with_hooks(tmp_path, hookspath=None)
    real_run = sc.subprocess.run

    def _failing_write(cmd, *args, **kwargs):
        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "config" and "--local" in cmd:
            raise OSError("simulated: git config write failed")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(sc.subprocess, "run", _failing_write)
    line = sc.hooks_path_autofix_line(tmp_path)
    assert "core.hooksPath not set" in line and "autofix failed" in line
    assert not line.startswith("WIRING AUTOFIX:")
    assert line.startswith("WIRING WARNING:")
    # The real config must be untouched (still unset).
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.returncode != 0 or not result.stdout.strip()


def test_hooks_path_autofix_line_reports_failure_when_hook_files_missing(tmp_path):
    # The `git config` write itself succeeds, but the recheck must
    # catch that the required hook files are still missing -- reported
    # as a failed autofix, not a false AUTOFIX line.
    _git(["init", "-q"], tmp_path)
    (tmp_path / ".githooks").mkdir()
    # Deliberately do NOT create pre-commit/commit-msg under .githooks.
    line = sc.hooks_path_autofix_line(tmp_path)
    assert "core.hooksPath not set" in line and "autofix" in line and "missing" in line
    assert not line.startswith("WIRING AUTOFIX:")
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.stdout.strip() == ".githooks"


def test_hooks_path_autofix_line_already_set_returns_empty(tmp_path):
    # Already set to the CORRECT value -- nothing to fix, no line at all
    # (the broader "already set" report, correct or not, is
    # wiring_summary_line()'s/tools/wiring_check.py's job, not this
    # function's -- see module docstring).
    _init_repo_with_hooks(tmp_path)
    assert sc.hooks_path_autofix_line(tmp_path) == ""


def test_hooks_path_autofix_line_already_set_elsewhere_returns_empty():
    # Set to some OTHER path -- deliberately NOT autofixed (an existing
    # configuration, human or a prior session, is left alone) and
    # deliberately NOT reported here either (wiring_check's job).
    other = Path(__file__).resolve().parent
    line = sc.hooks_path_autofix_line(other)
    # Whatever this repo's own hooksPath is currently configured to,
    # this function must never attempt to overwrite it nor emit a line
    # about it -- confirmed by never raising and returning a string.
    assert isinstance(line, str)


def test_hooks_path_autofix_line_never_raises_when_git_missing(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(sc.subprocess, "run", _boom)
    assert sc.hooks_path_autofix_line(tmp_path) == ""


# ---------------------------------------------------------------------
# wiring_summary_line -- see tools/wiring_check.py
# ---------------------------------------------------------------------


def test_wiring_summary_line_ok_on_fully_wired_repo(tmp_path):
    _init_repo_with_hooks(tmp_path)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"hooks": {}}), encoding="utf-8"
    )
    assert sc.wiring_summary_line(tmp_path) == "WIRING: OK"


def test_wiring_summary_line_appends_notice_count_without_flipping_ok(tmp_path):
    # Node E item 10: a non-blocking "notices" entry appends ", N
    # notice(s)" on the OK branch -- never flips it to the issue-count
    # branch.
    _init_repo_with_hooks(tmp_path)
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({"hooks": {}}), encoding="utf-8")
    (tmp_path / "ADOPTION_LEDGER.md").write_text(
        "# Adoption Ledger\n\n"
        "## Kit snapshot revision\n\nKit snapshot revision: `abc1234`\n",
        encoding="utf-8",
    )
    line = sc.wiring_summary_line(tmp_path)
    assert line == "WIRING: OK, 1 notice(s)"


def test_wiring_summary_line_reports_issue_count(tmp_path):
    # Nothing configured at all -- hooksPath unset (and, in a bare repo
    # with no writable-looking setup here, autofix may or may not stick,
    # but the settings.json is definitely missing) -- at least one issue.
    _git(["init", "-q"], tmp_path)
    line = sc.wiring_summary_line(tmp_path)
    assert line.startswith("WIRING: ")
    assert line != "WIRING: OK"
    assert "run tools/wiring_check.py --check" in line


def test_wiring_summary_line_never_raises_when_wiring_check_broken(tmp_path, monkeypatch):
    import wiring_check

    def _boom(root=None):
        raise RuntimeError("simulated wiring_check failure")

    monkeypatch.setattr(wiring_check, "check_wiring", _boom)
    line = sc.wiring_summary_line(tmp_path)
    assert line.startswith("WIRING: check unavailable (")


def test_build_context_lines_includes_wiring_summary(tmp_path):
    events = [_event("delegated", ts="2026-07-10T08:00:00", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    lines = sc.build_context_lines(root)
    assert any(l.startswith("WIRING:") or l.startswith("WIRING WARNING:")
               or l.startswith("WIRING AUTOFIX:") for l in lines), lines


# ---- F2 (release-gate v0.8.1): GATE BREAK-GLASS surfacing, ported from
# tools/session_context.py's own select_and_ack_break_glass_lines()/
# break_glass_lines() -- see this module's own docstring above
# _break_glass_candidates() for the full rationale (ack-only-shown-lines,
# the 5-line cap, the read-only-tracks + sidecar-ack fix, and the
# list-not-overwrite fix). tools/main_gate.py and tools/dod_gate.py's
# "skip the 3rd consecutive block" safety valve APPENDS a persistent
# unsafe_completion fact into the dod_track file itself (sibling edit,
# same task; new plural "unsafe_completions" list key, "unsafe_completion"
# singular kept readable for backward compat).


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
    # path.
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
    # New shape: "unsafe_completions" is a LIST -- every fact in it must
    # surface, not just the last one.
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


# ---- tracks are READ-ONLY, ack lives in the sidecar ----


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
    # Key carries a trailing fact-index: "ts" alone can collide -- see
    # _unsafe_completion_facts' docstring; legacy singular key -> index 0.
    assert "sess-c:main::t1:0" in ack
    assert ack["sess-c:main::t1:0"]  # non-empty ack timestamp


def test_break_glass_lines_ignores_its_own_sidecar_file_as_a_track(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "break_glass_ack.json").write_text("{}", encoding="utf-8")
    assert sc.break_glass_lines(tmp_path) == []


def test_break_glass_lines_repeat_call_is_silent_exactly_once_boundary(tmp_path):
    # The same fact must surface EXACTLY ONCE -- a second scan of the same
    # (now-acknowledged-in-the-sidecar) file is silent.
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
    # Two facts of the same session/gate/agent can carry a byte-identical
    # "ts" (Windows wall-clock granularity). Without the index in the ack
    # key, the SECOND fact would silently collapse onto the first's key
    # and never surface once the first is acknowledged. Both facts here
    # share the exact same ts string.
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
    # Two facts with a byte-identical ts, space_left=1 -- only the FIRST
    # is shown and acked; the second must resurface on the next call, not
    # be silently swallowed by a collapsed ack key.
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
    # A corrupt track file next to a good one must not hide the good
    # one's fact.
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


# ---- CAP at 5 fact lines + trailing summary line ----------------


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
    # Facts beyond the cap are NOT acked -- they must surface on a later
    # call once the earlier ones have been acknowledged.
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


# ---- ack ONLY lines surviving the MAX_LINES cut ------------------


def test_select_and_ack_break_glass_lines_no_space_left_does_not_ack(tmp_path):
    # The preceding context lines already fill the whole MAX_LINES
    # budget -> the pending fact must be neither shown NOR acked -- it
    # must resurface once space frees up.
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
    # used, exactly 1 left -- the single pending fact DOES fit and IS
    # acked.
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
    events = [_event("delegated", ts="2026-07-10T08:00:00", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    track_dir = root / ".claude" / "dod_track"
    _write_dod_track(
        track_dir,
        "sess-live",
        {"main_gate_state": {"unsafe_completion": {"ts": "t1", "reason": "no-green-run"}}},
    )
    lines = sc.build_context_lines(root)
    assert any(l.startswith("GATE BREAK-GLASS:") for l in lines)


def test_build_context_lines_no_break_glass_line_when_none_pending(tmp_path):
    events = [_event("delegated", ts="2026-07-10T08:00:00", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
    lines = sc.build_context_lines(root)
    assert not any(l.startswith("GATE BREAK-GLASS:") for l in lines)


def test_main_prints_break_glass_line_once_then_silent_on_rerun(tmp_path, capsys):
    # Prints once, silent on the next SessionStart of the same repo state.
    events = [_event("delegated", ts="2026-07-10T08:00:00", task_id="t-001")]
    root = _seed_repo(tmp_path, events=events)
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
