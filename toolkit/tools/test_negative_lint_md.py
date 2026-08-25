"""tools/test_negative_lint_md.py -- K-class resolver battery, synced
from HQ's tools/test_negative_lint_md.py (its K1 fix: an explicitly
requested sibling that does not exist fails LOUDLY -- pytest.fail
naming the requested path -- instead of a silent fallback to the live
file).

SCOPE UPDATE (supersedes the SCOPE ADAPTATION note this docstring carried
under D5 -- kept below in history form for the record): this kit's
tools/negative_lint.py is NOW region-aware (imports tools/md_regions.py,
recognizes fenced/blockquote/inline_code spans, the same B1 policy and
_classify priority order as HQ's own tools/negative_lint.py) -- ported
in the same node as this test update. D5's earlier reasoning ("md_regions
integration is out of scope for this port") no longer holds; the region
test groups it explicitly did NOT port are ADDED below.

NEGATIVE CONTROL, WITHOUT the sibling/live split: HQ's own
tools/test_negative_lint_md.py claims MODULE_UNDER_TEST=live turns its
"discrimination" assertion red (region-aware vs non-region-aware
targets) -- empirically checked against the live HQ repo (command
hygiene point 6) and found STALE: HQ folded its region logic directly
into the live tools/negative_lint.py itself (same as this kit does,
same history this file's own K1-resolver docstring already notes: "the
sibling name is a historical artifact") -- MODULE_UNDER_TEST=live and
the default both resolve to the SAME region-aware file on HQ's side
too, so the claimed red run is no longer produced by that mechanism
(`MODULE_UNDER_TEST=live python -m pytest tools/test_negative_lint_md.py
-q -k discrimination` on HQ's own tree: 1 passed, not red) -- a finding
worth flagging upstream, not fixed here (out of this kit's owns). This
port does not inherit the stale claim: the region tests below use
monkeypatch on `m.scan` (the SAME mechanism the ported И-0 tests already
exercise) as the honest region-on/region-off pair -- scan raising /
degraded is a real "no region" state this module's own I-0 fallback
promises to behave under, giving a genuine green (region working,
quoted control does not silence) / red (region unavailable, quoted
control silences, "today" behavior) split with no extra machinery
invented.

  - No tools/negative_lint_md.py sibling exists in this template (nor
    in HQ's own tree -- see above). The K1 resolver below stays
    UNCHANGED (same fork: empty -> sibling-if-exists-else-live,
    silently; "live" -> live explicitly; anything else -> loud
    pytest.fail if the requested sibling is absent) -- infrastructure,
    forward-compatible with a future region-aware sibling landing here.
  - HQ's region-specific test groups (И-0 md_regions-failure fallback,
    И-1 lazy-scan-call-count, B1 fenced/blockquote/inline_code policy,
    and the "discrimination" pair) ARE now ported below, adapted to the
    monkeypatch-based negative control described above (HQ's own
    MODULE_UNDER_TEST=live split is not reproduced -- see above for why).
  - The target-agnostic groups (window ±3 positional invariant, base
    decide()/find_violations() regression, and the subprocess
    adversarial battery), already present since D5, are UNCHANGED.

Run:  python -m pytest tools/test_negative_lint_md.py -q
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # K1 form (synced verbatim from HQ, docs/tasks/2026-08-25_
    # queue8-mechbatch-spec.md): default (MODULE_UNDER_TEST empty) --
    # sibling, IF it exists, else the live file, SILENTLY (no sibling
    # exists in this template today -- resolves to live). An explicitly
    # REQUESTED sibling (MODULE_UNDER_TEST set and not "live") that does
    # not exist -> LOUD pytest.fail, not a silent live substitution.
    live = TOOLS_DIR / "negative_lint.py"
    if MODULE_UNDER_TEST == "live":
        return live
    sibling = TOOLS_DIR / "negative_lint_md.py"
    if MODULE_UNDER_TEST == "":
        return sibling if sibling.exists() else live
    if not sibling.exists():
        pytest.fail(
            f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested sibling "
            f"{sibling} but it does not exist -- no silent live fallback (K1)"
        )
    return sibling


SCRIPT = _resolve_script_path()


def _load_module():
    alias = f"negative_lint_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module()


def _agent_payload(text) -> dict:
    return {"tool_name": "Task", "tool_input": {}, "tool_response": text}


def _run_hook(raw_input, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        **kwargs,
    )


# ---------------------------------------------------------------------
# I-0: any md_regions failure -> this guard behaves EXACTLY as before
# region-awareness (see the module docstring, "SCOPE UPDATE", for why
# monkeypatch on m.scan is this port's negative-control mechanism, not
# HQ's stale MODULE_UNDER_TEST=live split).
# ---------------------------------------------------------------------


def test_i0_scan_raises_falls_back_to_today_behavior(monkeypatch):
    """monkeypatch scan to raise (the literal shape HQ's own port
    tests). Text where the region ACTUALLY changes the result (see
    test_discrimination_* below) -- with a broken scan(), this guard
    must behave like a NON-region-aware linter (a quoted control
    silences -- i.e. NO violations), not like the region-aware default
    (which would find 1 violation)."""

    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    text = (
        "File config.yaml not found in the repository.\n"
        "> Sample of someone else's report: control passed successfully.\n"
    )
    violations = m.find_violations(text)
    assert violations == []  # byte-for-byte like a non-region linter: the quoted control silences


def test_i0_scan_degraded_falls_back_to_today_behavior(monkeypatch):
    """Second I-0 trigger -- scan() does not raise, but returns
    degraded=True (e.g. a limit exceeded). The same byte-for-byte
    fallback."""

    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    text = (
        "File config.yaml not found in the repository.\n"
        "> Sample of someone else's report: control passed successfully.\n"
    )
    violations = m.find_violations(text)
    assert violations == []


# ---------------------------------------------------------------------
# I-1: the scanner is called only AFTER the cheap pre-filter (laziness)
# ---------------------------------------------------------------------


def test_i1_scan_not_called_when_no_negative_marker(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    text = "Everything found, the file exists, the task completed normally."
    violations = m.find_violations(text)
    assert violations == []
    assert calls["n"] == 0


def test_i1_scan_called_exactly_once_when_negative_marker_present(monkeypatch):
    """Positive control of the same form (command hygiene point 6): the
    same counting substitution, the same text class, but WITH a
    negative marker -- scan() must be called (otherwise the zero count
    above would prove a broken call, not laziness)."""
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    text = "Checked directory docs/book -- no such path exists."
    violations = m.find_violations(text)
    assert len(violations) == 1
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# B1 policy: fenced/blockquote -- not a violation, inline_code -- a violation
# ---------------------------------------------------------------------


def test_b1_negative_inside_fenced_block_is_not_a_violation():
    text = (
        "Sample from someone else's report:\n"
        "```\n"
        "File not found in the directory.\n"
        "```\n"
    )
    assert m.find_violations(text) == []


def test_b1_negative_inside_blockquote_is_not_a_violation():
    text = "> File not found in the directory.\n"
    assert m.find_violations(text) == []


def test_b1_negative_inside_inline_code_is_a_violation():
    text = "See the example: `file not found in the directory` -- like so.\n"
    violations = m.find_violations(text)
    assert len(violations) == 1


def test_b1_negative_in_plain_prose_is_still_a_violation_regression():
    text = "No such file exists in the repository."
    violations = m.find_violations(text)
    assert len(violations) == 1


def test_b1_unterminated_fence_treated_as_prose_is_a_violation():
    """Silence-looks-like-success lesson -- an unterminated fence does
    NOT widen the silence zone, its content counts as prose."""
    text = "```\nFile not found.\n"
    violations = m.find_violations(text)
    assert len(violations) == 1


# ---------------------------------------------------------------------
# DISCRIMINATION NEGATIVE CONTROL (mandatory): a quoted "control ..."
# must NOT silence a real violation sitting in prose -- proven as a
# green/red PAIR against the SAME text (region working / region broken
# via monkeypatch, see test_i0_* above for the red half).
# ---------------------------------------------------------------------


def test_discrimination_control_in_quote_does_not_silence_prose_negative():
    """GREEN half (region filter active, the default): a quoted
    "control ..." does NOT silence a real violation in prose. The RED
    half of this pair is test_i0_scan_raises_falls_back_to_today_behavior
    above -- the SAME text, scan() broken via monkeypatch -> violations
    == [] (the quoted control DOES silence without region filtering) --
    both halves verified, verbatim in the builder report per command
    hygiene point 6."""
    text = (
        "File config.yaml not found in the repository.\n"
        "> Sample of someone else's report: control passed successfully.\n"
    )
    violations = m.find_violations(text)
    assert len(violations) == 1
    assert violations[0][0] == 1


# ---------------------------------------------------------------------
# Positional invariant: control window is +/-3 lines by original index
# ---------------------------------------------------------------------


def test_control_exactly_3_lines_away_triggers_window_suppresses_warn():
    lines = [
        "filler line 1",
        "filler line 2",
        "filler line 3",
        "0 matches found in the search.",
        "filler line A",
        "filler line B",
        "control: known-present sample checked same form.",
    ]
    text = "\n".join(lines)
    violations = m.find_violations(text)
    assert violations == []


def test_control_4_lines_away_does_not_trigger_window_warn_remains():
    lines = [
        "filler line 1",
        "filler line 2",
        "filler line 3",
        "0 matches found in the search.",
        "filler line A",
        "filler line B",
        "filler line C",
        "control: known-present sample checked same form.",
    ]
    text = "\n".join(lines)
    violations = m.find_violations(text)
    assert len(violations) == 1
    assert violations[0][0] == 4


# ---------------------------------------------------------------------
# Base behavior regression (target-agnostic: same for live and any
# future region-aware sibling)
# ---------------------------------------------------------------------


def test_decide_non_agent_tool_is_silent():
    payload = {"tool_name": "Bash", "tool_response": "file not found"}
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is None


def test_decide_text_without_negatives_is_silent():
    text = "Everything found, the file exists, the task completed normally."
    exit_code, output = m.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_marker_case_insensitive_and_mid_word_absent():
    text = "The file is ABSENT from the project directory."
    violations = m.find_violations(text)
    assert len(violations) == 1


def test_control_marker_suppresses_warn():
    text = (
        "File not found at the given path.\n"
        "control: verified by a positive run against a sample known to exist, same form.\n"
    )
    exit_code, output = m.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_decide_async_launched_payload_is_silent():
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "isAsync": True,
            "status": "async_launched",
            "prompt": "Check: file not found nowhere without a control.",
        },
    }
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# Adversarial battery (subprocess, hook path)
# ---------------------------------------------------------------------


def test_cli_broken_json_stdin_exit0_silent():
    result = _run_hook(b"{not valid json")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_empty_stdin_exit0_silent():
    result = _run_hook(b"")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_payload_without_tool_response_exit0_silent():
    payload = {"tool_name": "Task", "tool_input": {}}
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_nested_content_object_result_detected():
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "content": [
                {"type": "text", "text": "Checked docs/book: the directory does not exist."},
            ]
        },
    }
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    assert result.returncode == 0
    out = json.loads(result.stdout.decode("utf-8"))
    assert "NEGATIVE LINT" in out["hookSpecificOutput"]["additionalContext"]


def test_cli_1mb_text_no_catastrophic_blowup():
    line = "just a plain report line with no markers, padded for length. " * 3
    big_text = (line + "\n") * 15000
    assert len(big_text.encode("utf-8")) > 1_000_000
    payload = {"tool_name": "Task", "tool_response": big_text}
    started = time.perf_counter()
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    elapsed = time.perf_counter() - started
    assert result.returncode == 0
    assert elapsed < 5.0, f"took {elapsed:.2f}s -- wall-clock guard"


def test_cli_non_utf8_bytes_exit0_no_traceback():
    result = _run_hook(b"\xff\xfe\x00\x01not json either")
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr


def test_cli_emoji_unicode_no_crash():
    payload = {"tool_name": "Task", "tool_response": "Done \U0001F389 file not found \U0001F50E nowhere"}
    result = _run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert result.returncode == 0
    out = json.loads(result.stdout.decode("utf-8"))
    assert "NEGATIVE LINT" in out["hookSpecificOutput"]["additionalContext"]


def test_cli_text_mode_warns_on_negative_without_control(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("Such a file does not exist in the repository.", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", str(f)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert b"NEGATIVE LINT" in result.stdout


def test_cli_text_mode_silent_on_clean_text(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("Everything found and confirmed normally.", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", str(f)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_text_mode_missing_file_exit0_no_traceback(tmp_path):
    missing = tmp_path / "does_not_exist_at_all.txt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", str(missing)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr
