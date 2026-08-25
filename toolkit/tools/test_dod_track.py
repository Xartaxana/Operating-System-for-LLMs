"""Unit/smoke tests for tools/dod_track.py -- direct calls to the pure
functions (build_fact/determine_outcome/is_verification_command) plus
an echo-JSON subprocess smoke test.

Run from the repo root: python -m pytest tools/test_dod_track.py
"""

import io
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dod_track  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "dod_track.py"


# ---------------------------------------------------------------------
# helpers for the in-process main() mechanism battery below (total try/
# atomic write/non-dict guards) -- mirrors the toolkit's other
# in-process _run_main_inprocess pattern (see test_journal_echo_r3.py).
# ---------------------------------------------------------------------


class _FakeStdin:
    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


def _run_main_inprocess(payload_bytes: bytes, monkeypatch) -> int:
    monkeypatch.setattr(dod_track.sys, "stdin", _FakeStdin(payload_bytes))
    return dod_track.main()


def _edit_payload(cwd: Path, session_id: str = "s-1", file_path=None) -> dict:
    fp = file_path if file_path is not None else str(cwd / "some_file.py")
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": fp},
        "session_id": session_id,
        "cwd": str(cwd),
    }


def _install_truncating_write_text_mock(monkeypatch):
    """A mock that REALLY truncates the file (opens 'w', writes HALF the
    text, flushes) and only THEN raises -- not a json.dumps-before-open
    fake. Patched at the pathlib.Path CLASS level -- the same method
    both the old (unsafe) direct-write code and _atomic_write_text()'s
    fresh tmp-path write would call -- the difference in `self` (the
    live path vs. a fresh tmp path) is the discriminating mechanism
    itself."""
    def fake_write_text(self, text, *args, **kwargs):
        half = text[: max(1, len(text) // 2)]
        with open(str(self), "w", encoding="utf-8") as fh:
            fh.write(half)
            fh.flush()
        raise RuntimeError("simulated mid-write truncation (test)")

    monkeypatch.setattr(Path, "write_text", fake_write_text)


def _chmod_readonly(path: Path):
    os.chmod(path, stat.S_IREAD)


def _chmod_writable(path: Path):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


def _run_hook(payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# build_fact -- pure logic.
# ---------------------------------------------------------------------


def test_build_fact_edit_tool_logged():
    for tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        kind, entry = dod_track.build_fact({"tool_name": tool_name})
        assert kind == "edit"
        assert entry["tool_name"] == tool_name
        assert "ts" in entry
        # No tool_input at all -- file_path is unknown -> None.
        assert entry["file_path"] is None


def test_build_fact_irrelevant_tool_ignored():
    assert dod_track.build_fact({"tool_name": "Read"}) is None
    assert dod_track.build_fact({"tool_name": "Grep"}) is None


def test_build_fact_bash_non_verification_command_ignored():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
        "tool_response": {"stdout": "ok", "stderr": ""},
    }
    assert dod_track.build_fact(payload) is None


def test_build_fact_bash_verification_command_green():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -m pytest tools/ -q"},
        "tool_response": {"stdout": "5 passed in 0.12s", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "green"
    assert entry["command"] == "python -m pytest tools/ -q"


def test_build_fact_powershell_verification_command_green():
    # Some harness environments run shell commands via the PowerShell
    # tool rather than Bash -- verification runs must be visible to
    # the track regardless of which shell tool ran them.
    payload = {
        "tool_name": "PowerShell",
        "tool_input": {"command": "python -m pytest tools/ -q"},
        "tool_response": {"stdout": "131 passed in 2.64s", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "green"
    assert entry["tool_name"] == "PowerShell"


def test_build_fact_powershell_non_verification_command_ignored():
    payload = {
        "tool_name": "PowerShell",
        "tool_input": {"command": "Get-ChildItem tools"},
        "tool_response": {"stdout": "ok", "stderr": ""},
    }
    assert dod_track.build_fact(payload) is None


def test_build_fact_bash_verification_command_red_on_failure_text():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tools/"},
        "tool_response": {
            "stdout": "",
            "stderr": "Traceback (most recent call last):\n1 failed, 0 passed",
        },
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "red"


def test_build_fact_bash_verification_command_red_on_ambiguous_output():
    # Neither a failure nor a success indicator -- the safe default is
    # "red" (an unrecognized output is not a confirmed green run).
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -m pytest --collect-only"},
        "tool_response": {"stdout": "no tests ran", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "red"


def test_determine_outcome_bare_xfailed_is_green_not_red():
    # The bug this fix closes: a bare substring "failed" (no word
    # boundary) used to false-match inside "xfailed", turning an honest
    # xfail submission into a "red" outcome and blocking a clean
    # dod_gate stop. "2 xfailed" carries no OTHER summary word (no
    # "passed", no "error", no "Traceback") -- must resolve to green.
    assert dod_track.determine_outcome({"stdout": "2 xfailed", "stderr": ""}) == "green"


def test_determine_outcome_xfailed_alongside_passed_still_green():
    assert dod_track.determine_outcome(
        {"stdout": "10 passed, 2 xfailed in 1.23s", "stderr": ""}
    ) == "green"


def test_determine_outcome_word_boundary_does_not_match_failed_as_prefix_of_longer_word():
    # \bfailed\b must not match "failed" as a PREFIX of a longer token
    # either (not just as a suffix like "xfailed") -- boundary test on
    # both sides of the word-boundary fix.
    assert dod_track.determine_outcome({"stdout": "10 passed, 0 scaffailed", "stderr": ""}) == "green"


def test_determine_outcome_real_failed_word_still_red():
    # The word-boundary fix must not blind the detector to a REAL
    # standalone "failed" -- the boundary case just beyond xfailed's
    # false-positive.
    assert dod_track.determine_outcome({"stdout": "1 failed, 9 passed", "stderr": ""}) == "red"


def test_determine_outcome_bare_xpassed_still_green_incidental_substring():
    # Documented incidental behavior (unchanged by this fix): "xpassed"
    # matches SUCCESS_INDICATORS_RE only because "passed" occurs inside
    # it as a substring, same as before.
    assert dod_track.determine_outcome({"stdout": "1 xpassed", "stderr": ""}) == "green"


def test_build_fact_bash_verification_command_xfailed_green():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tools/"},
        "tool_response": {"stdout": "1 xfailed in 0.5s", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "green"


def test_build_fact_rc_field_overrides_text_when_present():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -m pytest tools/"},
        "tool_response": {"stdout": "something failed", "rc": 0},
    }
    kind, entry = dod_track.build_fact(payload)
    assert entry["outcome"] == "green"

    payload2 = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -m pytest tools/"},
        "tool_response": {"stdout": "5 passed", "exit_code": 1},
    }
    _, entry2 = dod_track.build_fact(payload2)
    assert entry2["outcome"] == "red"


def test_is_verification_command_matches_spec_forms():
    assert dod_track.is_verification_command("pytest")
    assert dod_track.is_verification_command("python -m pytest tools/ -q")
    assert dod_track.is_verification_command("python test_something.py")
    assert not dod_track.is_verification_command("ls -la")
    assert not dod_track.is_verification_command("git status")


def test_is_verification_command_one_off_script_wrapper_convention():
    # The one-off script wrapper convention (see the comment above
    # VERIFICATION_COMMAND_RE): a bare script run with no "test"/
    # "pytest" word is NOT recognized on its own; wrapping it with the
    # convention's `&& echo "verification test passed: ..."` makes it
    # recognized, with NO regex change (the word "test" inside the echo
    # string matches the existing third alternative).
    assert not dod_track.is_verification_command("python docs/tasks/x.py")
    assert dod_track.is_verification_command(
        'python docs/tasks/x.py && echo "verification test passed: probe"'
    )


def test_determine_outcome_wrapper_convention_marker_is_green():
    # The convention's own marker word "passed" is what makes
    # determine_outcome classify the wrapped one-off script run as
    # green -- without it, the command would be recognized (previous
    # test) but still fall to the safe "red" default here.
    payload = {
        "tool_name": "Bash",
        "tool_input": {
            "command": 'python docs/tasks/x.py && echo "verification test passed: probe"'
        },
        "tool_response": {
            "stdout": "verification test passed: probe",
            "stderr": "",
        },
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "green"


def test_gate_infra_self_tests_are_verification_commands():
    # Testing the gates themselves is a legitimate deliverable in this
    # deployment -- running their own test files IS a valid witness,
    # both the canonical and a narrow target.
    for cmd in [
        "pytest tools/test_dod_gate.py",
        "python -m pytest tools/test_dispatch_gate.py -q",
        "pytest tools/test_dod_track.py",
        "python -m pytest tools/test_main_gate.py -q",
    ]:
        assert dod_track.is_verification_command(cmd), cmd


def test_gate_infra_self_test_build_fact_produces_run():
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tools/test_dod_gate.py -q"},
        "tool_response": {"stdout": "5 passed in 0.01s", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "green"
    assert entry["command"] == "pytest tools/test_dod_gate.py -q"


def test_canonical_command_recognized_as_verification():
    assert dod_track.is_verification_command("python -m pytest tools/ gateway/ -q")


def test_narrow_target_command_recognized_as_verification():
    assert dod_track.is_verification_command("pytest tools/test_dispatch_gate.py -q")


def test_both_canonical_and_narrow_forms_produce_run_facts():
    canonical_payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "python -m pytest tools/ gateway/ -q"},
        "tool_response": {"stdout": "381 passed in 4.20s", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(canonical_payload)
    assert kind == "run"
    assert entry["outcome"] == "green"

    narrow_payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tools/test_dispatch_gate.py -q"},
        "tool_response": {"stdout": "30 passed in 0.50s", "stderr": ""},
    }
    kind2, entry2 = dod_track.build_fact(narrow_payload)
    assert kind2 == "run"
    assert entry2["outcome"] == "green"


# ---------------------------------------------------------------------
# Non-pytest witness forms -- a Node script, a UI screenshot run.
# ---------------------------------------------------------------------


def test_node_script_recognized_as_verification_command():
    assert dod_track.is_verification_command("node run_check.js")
    assert dod_track.is_verification_command("node scripts/verify.mjs")
    assert not dod_track.is_verification_command("node --version")


def test_ui_screenshot_command_recognized_as_verification_command():
    assert dod_track.is_verification_command("node take_screenshot.js")
    assert dod_track.is_verification_command("python run_playwright_check.py --screenshot")
    assert dod_track.is_verification_command("python capture_ui.py --puppeteer")


def test_node_script_outcome_uses_same_text_heuristics():
    green_payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "node run_check.js"},
        "tool_response": {"stdout": "All checks passed", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(green_payload)
    assert kind == "run"
    assert entry["outcome"] == "green"

    red_payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "node run_check.js"},
        "tool_response": {"stdout": "", "stderr": "Error: check failed"},
    }
    kind2, entry2 = dod_track.build_fact(red_payload)
    assert entry2["outcome"] == "red"


def test_ui_witness_command_silent_output_defaults_red():
    # A documented limitation: a script with no textual confirmation
    # (neither passed/ok nor failed/error/traceback) still lands on
    # the safe "red" default -- even though the command is now
    # recognized (visible in the track) rather than invisible entirely.
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "node take_screenshot.js"},
        "tool_response": {"stdout": "screenshot.png saved", "stderr": ""},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "run"
    assert entry["outcome"] == "red"


# ---------------------------------------------------------------------
# build_fact() edit records carry file_path.
# ---------------------------------------------------------------------


def test_build_fact_edit_includes_file_path_from_tool_input():
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "tools/dod_gate.py", "old_string": "a", "new_string": "b"},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] == "tools/dod_gate.py"


def test_build_fact_edit_file_path_missing_key_defaults_to_none():
    payload = {"tool_name": "Write", "tool_input": {"content": "x"}}
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] is None


def test_build_fact_edit_file_path_non_string_defaults_to_none():
    payload = {"tool_name": "MultiEdit", "tool_input": {"file_path": 12345}}
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] is None


def test_build_fact_edit_file_path_for_each_edit_tool_name():
    for tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        payload = {"tool_name": tool_name, "tool_input": {"file_path": f"docs/{tool_name}.md"}}
        kind, entry = dod_track.build_fact(payload)
        assert kind == "edit"
        assert entry["file_path"] == f"docs/{tool_name}.md"


# ---------------------------------------------------------------------
# Scratchpad-path exclusion from main-edit scope entirely.
# ---------------------------------------------------------------------


def test_build_fact_scratchpad_path_excluded_from_edit_scope():
    payload = {
        "tool_name": "Write",
        "cwd": "D:/repo",
        "tool_input": {
            "file_path": (
                "C:/Users/someone/AppData/Local/Temp/claude/repo/"
                "some-session-id/scratchpad/script.py"
            )
        },
    }
    assert dod_track.build_fact(payload) is None


def test_build_fact_scratchpad_uppercase_path_still_excluded():
    payload = {
        "tool_name": "Edit",
        "cwd": "D:/repo",
        "tool_input": {"file_path": "C:/Temp/Claude/Scratchpad/tmp.py"},
    }
    assert dod_track.build_fact(payload) is None


def test_build_fact_path_outside_repo_root_excluded_even_without_scratchpad_word():
    payload = {
        "tool_name": "Edit",
        "cwd": "D:/repo",
        "tool_input": {"file_path": "C:/Windows/Temp/other/file.py"},
    }
    assert dod_track.build_fact(payload) is None


def test_build_fact_normal_repo_relative_path_not_excluded():
    payload = {"tool_name": "Edit", "cwd": "D:/repo", "tool_input": {"file_path": "tools/x.py"}}
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] == "tools/x.py"


def test_build_fact_normal_repo_absolute_path_not_excluded(tmp_path):
    inner = tmp_path / "tools" / "x.py"
    payload = {"tool_name": "Edit", "cwd": str(tmp_path), "tool_input": {"file_path": str(inner)}}
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] == str(inner)


def test_build_fact_scratchpad_word_without_cwd_no_longer_excluded():
    # DIVERGENCE from prior behavior, documented not silent: a bare "scratchpad"
    # substring (no cwd) no longer excludes on its own -- the criterion
    # is now solely "outside cwd", which cannot be evaluated without
    # cwd at all -- fail-safe: NOT excluded.
    payload = {"tool_name": "Write", "tool_input": {"file_path": "/tmp/scratchpad/x.py"}}
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] == "/tmp/scratchpad/x.py"


def test_build_fact_repo_internal_scratchpad_named_file_not_excluded():
    # An in-repo path whose NAME merely contains "scratchpad" is NOT
    # excluded from main scope -- cwd matches the root, so "outside cwd"
    # is false, and the standalone substring branch no longer exists.
    payload = {
        "tool_name": "Edit",
        "cwd": "D:/repo",
        "tool_input": {"file_path": "D:/repo/tools/scratchpad_utils.py"},
    }
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] == "D:/repo/tools/scratchpad_utils.py"


def test_build_fact_no_cwd_and_no_scratchpad_word_not_excluded():
    payload = {"tool_name": "Edit", "tool_input": {"file_path": "some/relative/path.py"}}
    kind, entry = dod_track.build_fact(payload)
    assert kind == "edit"
    assert entry["file_path"] == "some/relative/path.py"


def test_is_scratchpad_path_direct_boundary_cases():
    # Without cwd, a "scratchpad" name is no longer enough by itself -- the criterion
    # is entirely "outside cwd", which cannot be evaluated without cwd
    # -> False (fail-safe).
    assert dod_track._is_scratchpad_path("C:/x/scratchpad/y.py", None) is False
    assert dod_track._is_scratchpad_path("C:/x/SCRATCHPAD/y.py", None) is False
    assert dod_track._is_scratchpad_path(None, "D:/repo") is False
    assert dod_track._is_scratchpad_path("", "D:/repo") is False
    assert dod_track._is_scratchpad_path("tools/x.py", "D:/repo") is False
    # the existing outside-cwd case stays green as before.
    assert dod_track._is_scratchpad_path("C:/x/scratchpad/y.py", "D:/repo") is True
    # an in-repo path with "scratchpad" in the name is NOT excluded.
    assert dod_track._is_scratchpad_path("D:/repo/scratchpad_utils.py", "D:/repo") is False


# ---------------------------------------------------------------------
# echo-JSON subprocess smoke tests.
# ---------------------------------------------------------------------


def test_echo_json_logs_edit(tmp_path):
    payload = {
        "session_id": "sess-1",
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "x.py"},
    }
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    track_path = tmp_path / ".claude" / "dod_track" / "sess-1.json"
    assert track_path.exists()
    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert len(data["edits"]) == 1
    assert data["edits"][0]["tool_name"] == "Edit"
    assert data["edits"][0]["file_path"] == "x.py"
    assert data["runs"] == []


def test_echo_json_logs_green_and_red_runs_distinctly(tmp_path):
    session_id = "sess-2"
    green_payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": "python -m pytest tools/ -q"},
        "tool_response": {"stdout": "3 passed in 0.05s", "stderr": ""},
    }
    red_payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tools/"},
        "tool_response": {"stdout": "", "stderr": "1 failed, 2 passed"},
    }

    r1 = _run_hook(green_payload, cwd=tmp_path)
    assert r1.returncode == 0, r1.stderr
    r2 = _run_hook(red_payload, cwd=tmp_path)
    assert r2.returncode == 0, r2.stderr

    track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert len(data["runs"]) == 2
    assert data["runs"][0]["outcome"] == "green"
    assert data["runs"][1]["outcome"] == "red"


def test_echo_json_logs_gate_infra_self_test_run(tmp_path):
    payload = {
        "session_id": "sess-gate-infra",
        "cwd": str(tmp_path),
        "tool_name": "Bash",
        "tool_input": {"command": "pytest tools/test_dod_gate.py -q"},
        "tool_response": {"stdout": "12 passed in 0.30s", "stderr": ""},
    }
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    track_path = tmp_path / ".claude" / "dod_track" / "sess-gate-infra.json"
    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert len(data["runs"]) == 1
    assert data["runs"][0]["outcome"] == "green"


def test_echo_json_ignores_unrelated_tool(tmp_path):
    payload = {
        "session_id": "sess-3",
        "cwd": str(tmp_path),
        "tool_name": "Read",
        "tool_input": {"file_path": "x.py"},
    }
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".claude" / "dod_track" / "sess-3.json").exists()


def test_echo_json_preserves_unknown_keys_written_by_other_hook(tmp_path):
    """dod_gate.py/main_gate.py write gate_state/main_gate_state/gate_log
    keys into the same file -- dod_track.py's own read-modify-write must
    not wipe them out."""
    session_id = "sess-4"
    track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
    track_path.parent.mkdir(parents=True)
    track_path.write_text(
        json.dumps(
            {
                "edits": [],
                "runs": [],
                "gate_state": {"consecutive_blocks": 1},
                "gate_log": [{"action": "blocked", "reason": "no-green-run"}],
            }
        ),
        encoding="utf-8",
    )

    payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_name": "Write",
        "tool_input": {"file_path": "y.py"},
    }
    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert len(data["edits"]) == 1
    assert data["gate_state"] == {"consecutive_blocks": 1}
    assert data["gate_log"] == [{"action": "blocked", "reason": "no-green-run"}]


def test_echo_json_scratchpad_edit_not_recorded_and_does_not_break_doc_only(tmp_path):
    """A coordinator writing a scratchpad temp script AFTER a doc-only
    edit must NOT be recorded to the track at all -- so main_gate.py's
    doc-only "whole-or-nothing" fix still fires on what remains: only
    the genuine doc-only edit."""
    session_id = "sess-scratch"
    cwd = str(tmp_path)

    doc_payload = {
        "session_id": session_id,
        "cwd": cwd,
        "tool_name": "Edit",
        "tool_input": {"file_path": "README.md"},
    }
    r1 = _run_hook(doc_payload, cwd=tmp_path)
    assert r1.returncode == 0, r1.stderr

    scratch_payload = {
        "session_id": session_id,
        "cwd": cwd,
        "tool_name": "Write",
        "tool_input": {"file_path": "C:/Users/user/AppData/Local/Temp/claude/xyz/some-session/scratchpad/tmp.py"},
    }
    r2 = _run_hook(scratch_payload, cwd=tmp_path)
    assert r2.returncode == 0, r2.stderr

    track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert len(data["edits"]) == 1
    assert data["edits"][0]["file_path"] == "README.md"


# ---------------------------------------------------------------------
# Byte-safe stdin: a subprocess smoke test with raw UTF-8 bytes
# (ensure_ascii=False, input=bytes, no text=True/encoding on
# subprocess). A Cyrillic file_path is a meaningful check: if the raw-
# byte read + explicit UTF-8 decode were broken or absent, the
# platform's locale encoding could mangle non-ASCII text into
# mojibake, and entry["file_path"] would not match the original string.
# ---------------------------------------------------------------------


def test_echo_json_raw_utf8_bytes_stdin_preserves_cyrillic_file_path(tmp_path):
    session_id = "sess-utf8"
    payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": "докстринг/файл.py"},
    }
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw,
        cwd=str(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

    track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert data["edits"][0]["file_path"] == "докстринг/файл.py"


# =======================================================================
# total try in main() -- an unexpected exception collapses to ONE loud
# stderr line, rc=0; existing recognized non-events stay silent.
# =======================================================================


def test_main_uncaught_write_failure_becomes_single_stderr_line_rc0(
    tmp_path, monkeypatch, capsys,
):
    def _boom(_path, _data):
        raise PermissionError("simulated locked track file (test)")

    monkeypatch.setattr(dod_track, "_save_track", _boom)

    payload = _edit_payload(tmp_path)
    rc = _run_main_inprocess(json.dumps(payload).encode("utf-8"), monkeypatch)
    err = capsys.readouterr().err

    assert rc == 0
    lines = [ln for ln in err.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected EXACTLY one stderr line, got: {lines!r}"
    assert lines[0] == (
        "dod_track.py: FAILED to save track "
        "(PermissionError: simulated locked track file (test))"
    )


def test_main_recognized_nonevents_stay_silent_rc0(tmp_path, monkeypatch, capsys):
    # Edges: broken JSON / a non-fact / no session_id stay SILENT (no
    # stderr) -- the total try must not turn expected early returns into
    # noisy diagnostics.
    rc = _run_main_inprocess(b"{not valid json", monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""

    payload = {"tool_name": "SomeIrrelevantTool", "session_id": "s-1", "cwd": str(tmp_path)}
    rc = _run_main_inprocess(json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""

    payload = _edit_payload(tmp_path, session_id="")
    rc = _run_main_inprocess(json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""


# =======================================================================
# guard non-dict root AND non-dict tool_input -- silent rc=0, no track
# directory created.
# =======================================================================


@pytest.mark.parametrize("bad_root", [[], "just a string", 5, None, True])
def test_main_non_dict_root_returns_zero_silently(bad_root, tmp_path, monkeypatch, capsys):
    rc = _run_main_inprocess(json.dumps(bad_root).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""
    assert not (tmp_path / ".claude").exists()


@pytest.mark.parametrize("bad_tool_input", [[1, 2], "oops", 5, True])
def test_main_non_dict_tool_input_returns_zero_silently(
    bad_tool_input, tmp_path, monkeypatch, capsys,
):
    payload = {
        "tool_name": "Edit",
        "tool_input": bad_tool_input,
        "session_id": "s-1",
        "cwd": str(tmp_path),
    }
    rc = _run_main_inprocess(json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""
    assert not (tmp_path / ".claude").exists()

    # Direct call on the pure function -- the same guard, no I/O.
    assert dod_track.build_fact({"tool_name": "Edit", "tool_input": bad_tool_input}) is None
    assert dod_track.build_fact({"tool_name": "Bash", "tool_input": bad_tool_input}) is None


# =======================================================================
# atomic write -- tmp suffix ".tmp" last (never ".json"), orphaned tmp
# after a replace failure stays invisible to session_context.py's own
# glob("*.json"), and the discriminating atomicity test itself: a
# mid-write failure must never corrupt the ORIGINAL file.
# =======================================================================


def test_atomic_write_tmp_name_suffix_is_tmp_last_and_not_json(tmp_path, monkeypatch):
    seen_names = []
    real_mkstemp = tempfile.mkstemp

    def spy_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        seen_names.append(name)
        return fd, name

    monkeypatch.setattr(tempfile, "mkstemp", spy_mkstemp)

    target = tmp_path / "some_track.json"
    dod_track._atomic_write_text(target, '{"ok": true}\n')

    assert seen_names, "mkstemp was never called -- the atomic write path wasn't taken"
    for name in seen_names:
        assert name.endswith(".tmp"), f"the .tmp suffix must be LAST: {name!r}"
        assert not name.endswith(".json"), (
            f"a leftover fragment must not end in .json (a *.json glob "
            f"elsewhere could mistake it for someone else's track): {name!r}"
        )
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'


def test_atomic_write_orphaned_tmp_after_replace_failure_invisible_to_json_glob(
    tmp_path, monkeypatch,
):
    def flaky_replace(_src, _dst):
        raise OSError("simulated replace failure (test)")

    monkeypatch.setattr(os, "replace", flaky_replace)

    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    target = track_dir / "s-orphan.json"

    with pytest.raises(OSError):
        dod_track._save_track(target, {"edits": [], "runs": []})

    matched = sorted(track_dir.glob("*.json"))
    assert matched == [], f"an orphan fragment was picked up by glob('*.json'): {matched!r}"
    leftovers = list(track_dir.glob("*"))
    for f in leftovers:
        assert f.name.endswith(".tmp"), f"unexpected leftover: {f}"


def test_atomic_write_mid_write_failure_never_corrupts_the_original_file(
    tmp_path, monkeypatch,
):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    target = track_dir / "s-atomicity.json"
    original = json.dumps({"edits": [], "runs": [], "marker": "SEED-ORIGINAL"}) + "\n"
    target.write_bytes(original.encode("utf-8"))

    _install_truncating_write_text_mock(monkeypatch)

    with pytest.raises(RuntimeError):
        dod_track._save_track(target, {"edits": [{"marker": "NEW"}], "runs": []})

    after = target.read_bytes()
    original_bytes = original.encode("utf-8")
    assert after == original_bytes, (
        f"the ORIGINAL was not preserved after an injected mid-write "
        f"failure: {after!r} != seed {original_bytes!r}"
    )

    leftovers = list(target.parent.glob("*.tmp"))
    assert not leftovers, f"an orphaned .tmp fragment was left behind: {leftovers}"


# =======================================================================
# a real artifact unwritable at the moment of the write: (i) a read-only
# track file, (ii) the track path occupied by a directory. Both must
# stay LOUD-fail-open (rc=0 + one stderr line), never crash, never
# corrupt/replace the pre-existing artifact.
# =======================================================================


def test_readonly_target_file_stays_loud_fail_open_original_untouched(
    tmp_path, monkeypatch, capsys,
):
    track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
    track_path.parent.mkdir(parents=True)
    original = json.dumps({"edits": [], "runs": []}) + "\n"
    track_path.write_bytes(original.encode("utf-8"))
    _chmod_readonly(track_path)
    try:
        payload = _edit_payload(tmp_path)
        rc = _run_main_inprocess(json.dumps(payload).encode("utf-8"), monkeypatch)
        err = capsys.readouterr().err
        assert rc == 0
        assert "FAILED to save track" in err
        assert track_path.read_bytes() == original.encode("utf-8"), (
            "a read-only live file was modified -- open(mode='w') on a "
            "read-only file must not even begin truncating it"
        )
    finally:
        _chmod_writable(track_path)


def test_path_occupied_by_directory_stays_loud_fail_open_directory_untouched(
    tmp_path, monkeypatch, capsys,
):
    track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
    track_path.parent.mkdir(parents=True)
    track_path.mkdir()  # the track "file" path is occupied by a directory

    payload = _edit_payload(tmp_path)
    rc = _run_main_inprocess(json.dumps(payload).encode("utf-8"), monkeypatch)
    err = capsys.readouterr().err

    assert rc == 0
    assert "FAILED to save track" in err
    assert track_path.is_dir(), "the directory must not vanish/become a file on failure"
    leftovers = list(track_path.parent.glob("*.tmp"))
    assert not leftovers, f"an orphaned .tmp fragment next to the (untouched) directory: {leftovers}"
