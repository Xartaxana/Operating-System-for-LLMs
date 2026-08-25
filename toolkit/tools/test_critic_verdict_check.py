"""Battery for tools/critic_verdict_check.py.

Covers: valid verdict/*, invalid combinations, fence extraction (missing /
unclosed / duplicate blocks), broken/non-object JSON, per-field required
checks, non-ASCII data vs ASCII diagnostics, empty input, a large-text
boundary, and non-UTF-8 input (utf-16 file, arbitrary invalid-UTF-8 bytes).

NOTE (manifest gap, flagged in the builder report rather than resolved
silently): the reference implementation this file was ported from also
carries an anti-drift battery comparing its hardcoded rules against a
tools/critic_verdict.schema.json file. That schema file is not part of
this task's owns/write basket for this toolkit, so it is not shipped
here and those anti-drift cases are not reproduced -- every other case
(acceptance keys, cross-field rules, fence extraction, ASCII/non-ASCII,
boundaries, CLI contract) IS reproduced below, hardcoded directly
against this file's own VERDICT_ENUM/validate_verdict rather than
derived from a schema.

Run: python -m pytest tools/test_critic_verdict_check.py -q
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import critic_verdict_check as cvc

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = REPO_ROOT / "tools" / "critic_verdict_check.py"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _wrap(obj, prefix="Findings go here.\n\n", suffix="\n"):
    return prefix + "```json\n" + json.dumps(obj, ensure_ascii=False, indent=2) + "\n```" + suffix


def _base_fit():
    return {
        "verdict": "fit",
        "blockers": [],
        "class_completeness": "axis 3 covered, no analogs found",
        "trail": {
            "read": ["tools/critic_verdict_check.py"],
            "reruns": [
                {
                    "command": "python -m pytest tools/test_critic_verdict_check.py -q",
                    "result": "42 passed",
                }
            ],
        },
    }


def _base_fit_with_fixes():
    obj = _base_fit()
    obj["verdict"] = "fit_with_fixes"
    obj["fixes"] = ["add a boundary test for N"]
    return obj


def _base_blocker():
    obj = _base_fit()
    obj["verdict"] = "blocker"
    obj["blockers"] = ["critical finding: race condition in X"]
    return obj


def _run_cli(args, input_text=None):
    # critic_verdict_check now decodes stdin as BYTES, strictly UTF-8 (the
    # stdin-deadline helper this task adds), not via sys.stdin.read()'s
    # locale-dependent text mode -- text=True with no explicit encoding=
    # would encode input in this machine's LOCALE encoding (not
    # necessarily UTF-8), which would desync from the child's now-strict
    # UTF-8 decode on non-ASCII content. encoding="utf-8" here pins BOTH
    # sides (the parent writes the input as UTF-8 bytes -- the same form
    # a real harness uses; the output is decoded as UTF-8 for the str
    # asserts) -- changes no test's semantics, only the transport.
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)] + args,
        cwd=str(REPO_ROOT),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )


# ---------------------------------------------------------------------------
# valid verdicts (acceptance keys)
# ---------------------------------------------------------------------------


def test_valid_fit_empty_blockers():
    ok, errors, obj = cvc.check_text(_wrap(_base_fit()))
    assert ok, errors
    assert obj["verdict"] == "fit"


def test_valid_fit_with_fixes_nonempty_fixes():
    ok, errors, obj = cvc.check_text(_wrap(_base_fit_with_fixes()))
    assert ok, errors


def test_valid_blocker_nonempty_blockers():
    ok, errors, obj = cvc.check_text(_wrap(_base_blocker()))
    assert ok, errors


# ---------------------------------------------------------------------------
# verdict/blockers/fixes cross-field rules
# ---------------------------------------------------------------------------


def test_fit_with_fixes_missing_fixes_fails():
    obj = _base_fit_with_fixes()
    del obj["fixes"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("fixes" in e for e in errors)


def test_fit_with_fixes_empty_fixes_fails():
    obj = _base_fit_with_fixes()
    obj["fixes"] = []
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("fixes" in e for e in errors)


def test_blocker_with_empty_blockers_fails():
    obj = _base_blocker()
    obj["blockers"] = []
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("blockers" in e for e in errors)


def test_fit_with_nonempty_blockers_fails():
    obj = _base_fit()
    obj["blockers"] = ["not actually empty"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("blockers" in e for e in errors)


def test_verdict_outside_enum_fails():
    obj = _base_fit()
    obj["verdict"] = "meh"
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("verdict" in e for e in errors)


# ---------------------------------------------------------------------------
# fence extraction
# ---------------------------------------------------------------------------


def test_no_json_block_fails():
    ok, errors, _ = cvc.check_text("Just prose, no fenced block anywhere.")
    assert not ok
    assert any("no fenced" in e for e in errors)


def test_two_blocks_uses_last():
    first = {"verdict": "meh"}  # malformed on purpose - must NOT be used
    second = _base_fit_with_fixes()
    text = (
        "Draft:\n```json\n"
        + json.dumps(first)
        + "\n```\n\nFinal:\n```json\n"
        + json.dumps(second)
        + "\n```\n"
    )
    ok, errors, obj = cvc.check_text(text)
    assert ok, errors
    assert obj["verdict"] == "fit_with_fixes"


def test_unclosed_fence_reports_no_block():
    text = "Findings.\n```json\n" + json.dumps(_base_fit())
    ok, errors, _ = cvc.check_text(text)
    assert not ok
    assert any("no fenced" in e for e in errors)


def test_broken_json_fails():
    text = "Findings.\n```json\n{not valid json,,,\n```\n"
    ok, errors, _ = cvc.check_text(text)
    assert not ok
    assert any("invalid JSON" in e for e in errors)


def test_json_array_instead_of_object_fails():
    text = "Findings.\n```json\n[1, 2, 3]\n```\n"
    ok, errors, _ = cvc.check_text(text)
    assert not ok
    assert any("not an object" in e for e in errors)


# ---------------------------------------------------------------------------
# per-field required checks (named field in diagnostic)
# ---------------------------------------------------------------------------


def test_missing_verdict_field():
    obj = _base_fit()
    del obj["verdict"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("verdict" in e for e in errors)


def test_missing_blockers_field():
    obj = _base_fit()
    del obj["blockers"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("blockers" in e for e in errors)


def test_missing_class_completeness_field():
    obj = _base_fit()
    del obj["class_completeness"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("class_completeness" in e for e in errors)


def test_missing_trail_field():
    obj = _base_fit()
    del obj["trail"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("trail" in e for e in errors)


def test_trail_without_read_fails():
    obj = _base_fit()
    del obj["trail"]["read"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("trail.read" in e for e in errors)


def test_trail_without_reruns_fails():
    obj = _base_fit()
    del obj["trail"]["reruns"]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("trail.reruns" in e for e in errors)


def test_reruns_element_without_command_fails():
    obj = _base_fit()
    obj["trail"]["reruns"] = [{"result": "3 passed"}]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("command" in e for e in errors)


def test_reruns_element_without_result_fails():
    obj = _base_fit()
    obj["trail"]["reruns"] = [{"command": "pytest -q"}]
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert not ok
    assert any("result" in e for e in errors)


# ---------------------------------------------------------------------------
# ASCII diagnostics vs non-ASCII data; empty input; large input boundary
# ---------------------------------------------------------------------------


def test_cyrillic_data_is_valid_and_output_is_ascii():
    obj = _base_blocker()
    obj["blockers"] = ["Кириллический текст находки блокера"]
    obj["class_completeness"] = "ось 3 покрыта, ось 7 в очередь порта"
    ok, errors, _ = cvc.check_text(_wrap(obj))
    assert ok, errors

    result = _run_cli(["-"], input_text=_wrap(obj))
    assert result.returncode == 0
    assert result.stdout.strip().startswith("VERDICT OK:")
    result.stdout.encode("ascii")  # raises UnicodeEncodeError if not ASCII


def test_diagnostics_are_ascii_even_with_cyrillic_input():
    obj = _base_fit()
    obj["blockers"] = ["Кириллический не-пустой blockers при fit"]
    result = _run_cli(["-"], input_text=_wrap(obj))
    assert result.returncode == 1
    result.stderr.encode("ascii")  # raises UnicodeEncodeError if not ASCII


def test_empty_input_fails():
    ok, errors, _ = cvc.check_text("")
    assert not ok
    assert any("no fenced" in e for e in errors)


def test_large_input_with_trailing_block_works():
    padding = "x" * 120_000
    text = padding + "\n\n" + _wrap(_base_fit_with_fixes())
    ok, errors, obj = cvc.check_text(text)
    assert ok, errors
    assert obj["verdict"] == "fit_with_fixes"


# ---------------------------------------------------------------------------
# non-UTF-8 input (the file-open branch must not leak a raw traceback on
# decode failure -- fail-closed with an ASCII line)
# ---------------------------------------------------------------------------


def test_cli_utf16_file_fails_clean_no_traceback(tmp_path):
    p = tmp_path / "verdict_utf16.txt"
    p.write_text(_wrap(_base_fit()), encoding="utf-16")
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout
    assert "INVALID VERDICT: input is not valid UTF-8" in result.stderr
    result.stderr.encode("ascii")
    result.stdout.encode("ascii")


def test_cli_arbitrary_invalid_bytes_file_fails_clean_no_traceback(tmp_path):
    p = tmp_path / "verdict_garbage.bin"
    p.write_bytes(bytes([0xFF, 0xFE, 0x00, 0xD8, 0xFF, 0xFF, 0x80, 0x81] * 50))
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "Traceback" not in result.stdout
    assert "INVALID VERDICT: input is not valid UTF-8" in result.stderr
    result.stderr.encode("ascii")
    result.stdout.encode("ascii")


def test_cli_stdin_invalid_bytes_fails_clean_no_traceback():
    # Same failure class as the file branch (fix the class, not the
    # instance): invalid bytes on stdin. PYTHONIOENCODING pins the
    # child's stdin to strict utf-8 so the case is deterministic across
    # locales (a default Windows locale may decode 0xFF permissively as
    # cp1251).
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, str(CHECKER_PATH), "-"],
        cwd=str(REPO_ROOT),
        input=bytes([0xFF, 0xFE, 0x80, 0x81] * 20),
        capture_output=True,
        timeout=15,
        env=env,
    )
    assert result.returncode == 1
    stderr = result.stderr.decode("ascii")
    stdout = result.stdout.decode("ascii")
    assert "Traceback" not in stderr
    assert "Traceback" not in stdout
    assert "INVALID VERDICT: input is not valid UTF-8" in stderr


# ---------------------------------------------------------------------------
# CLI contract (file path and stdin "-")
# ---------------------------------------------------------------------------


def test_cli_valid_file_exit_zero(tmp_path):
    p = tmp_path / "verdict.txt"
    p.write_text(_wrap(_base_fit()), encoding="utf-8")
    result = _run_cli([str(p)])
    assert result.returncode == 0
    assert "VERDICT OK: fit, blockers: 0, fixes: 0" in result.stdout


def test_cli_invalid_file_exit_one(tmp_path):
    p = tmp_path / "verdict.txt"
    obj = _base_fit()
    del obj["class_completeness"]
    p.write_text(_wrap(obj), encoding="utf-8")
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert "INVALID VERDICT" in result.stderr
    assert "class_completeness" in result.stderr


def test_cli_stdin_dash_valid():
    result = _run_cli(["-"], input_text=_wrap(_base_blocker()))
    assert result.returncode == 0
    assert "VERDICT OK: blocker" in result.stdout


def test_cli_missing_argument_exit_one():
    result = _run_cli([])
    assert result.returncode == 1


# ---------------------------------------------------------------------------
# enum values -- each verdict enum member is individually accepted
# (a bounded, hardcoded mirror of the schema-driven anti-drift test the
# reference implementation carries -- see the module docstring's note)
# ---------------------------------------------------------------------------


def test_verdict_enum_each_value_accepted_one_case_per_value():
    builders = {
        "fit": _base_fit,
        "fit_with_fixes": _base_fit_with_fixes,
        "blocker": _base_blocker,
    }
    assert set(builders) == set(cvc.VERDICT_ENUM)
    for value, builder in builders.items():
        ok, errors, obj = cvc.check_text(_wrap(builder()))
        assert ok, errors
        assert obj["verdict"] == value


# ---------------------------------------------------------------------------
# stdin deadline (this task's addition): a non-draining/never-closing
# writer on stdin must not hang this script forever -- a daemon reader
# thread + a join(deadline), the same helper form this toolkit's other
# stdin-reading hooks already carry, ported here as a local copy.
# ---------------------------------------------------------------------------


_STDIN_DEADLINE_MSG = "stdin deadline exceeded -- fail-open, payload discarded"


@pytest.mark.parametrize("raw_value,expected", [
    ("", 10.0),
    ("abc", 10.0),
    ("0", 10.0),
    ("-1", 10.0),
    ("1e9", 10.0),
    ("600.1", 10.0),  # BEYOND the MAX boundary -> default (rule 6a)
    ("600", 600.0),  # EXACTLY at the MAX boundary -> passes through (rule 6a)
    ("5", 5.0),
])
def test_stdin_deadline_env_parsing_branches(raw_value, expected, monkeypatch):
    monkeypatch.setenv(cvc._STDIN_DEADLINE_ENV, raw_value)
    assert cvc._stdin_deadline_seconds() == expected


def test_stdin_deadline_env_absent_uses_default(monkeypatch):
    monkeypatch.delenv(cvc._STDIN_DEADLINE_ENV, raising=False)
    assert cvc._stdin_deadline_seconds() == cvc._STDIN_DEADLINE_DEFAULT == 10.0


def _run_holding_stdin_open(deadline, extra_wait=5.0):
    """Holds the process's stdin open, closing and writing nothing -- a
    real "writer that never closed" (Popen, NOT Popen.communicate(),
    which itself closes stdin and would cancel the simulation)."""
    env = os.environ.copy()
    env["OSLLM_STDIN_TIMEOUT"] = str(deadline)
    proc = subprocess.Popen(
        [sys.executable, str(CHECKER_PATH), "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )
    try:
        proc.wait(timeout=deadline + extra_wait)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    out = proc.stdout.read()
    err = proc.stderr.read()
    proc.stdin.close()
    proc.stdout.close()
    proc.stderr.close()
    return proc.returncode, out, err


def test_stdin_deadline_timeout_rc_matches_empty_input_one_stderr_line():
    # On timeout: rc == the same failure code an empty/invalid input gets
    # (1, not 0 -- this script is not a hook), stdout is EMPTY, stderr is
    # exactly one line with the script's own filename prefix. Also proves
    # the __main__ escalation (os._exit) doesn't crash the process with a
    # "Fatal Python error" -- rc==1 is a clean exit, not a crash code.
    rc, out, err = _run_holding_stdin_open(1.0)
    assert rc == 1
    assert out == b""
    expected_err = f"{CHECKER_PATH.name}: {_STDIN_DEADLINE_MSG}\n".encode("utf-8")
    assert err.replace(b"\r\n", b"\n") == expected_err
    assert b"Fatal Python error" not in err


def test_stdin_deadline_timeout_lands_within_deadline_plus_margin_boundary():
    # A short deadline (0.3s): the actual elapsed time stays within
    # deadline+margin, never hangs forever (a lower bound of ~0.25s --
    # join(timeout) sometimes returns slightly early -- same tolerance
    # class as journal_echo.py's own stdout-deadline test battery).
    t0 = time.monotonic()
    rc, out, err = _run_holding_stdin_open(0.3)
    elapsed = time.monotonic() - t0
    assert rc == 1
    assert out == b""
    assert 0.25 <= elapsed < 1.3, f"timeout should land within deadline+margin, took {elapsed:.3f}s"


def test_stdin_deadline_quick_close_before_deadline_still_valid():
    # A positive control on the NON-timeout path: the writer closes the
    # channel BEFORE the deadline -- the ordinary path must not have
    # regressed after moving to the byte-deadline helper.
    env = os.environ.copy()
    env["OSLLM_STDIN_TIMEOUT"] = "5.0"
    payload = _wrap(_base_fit()).encode("utf-8")
    proc = subprocess.Popen(
        [sys.executable, str(CHECKER_PATH), "-"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env,
    )
    proc.stdin.write(payload)
    proc.stdin.close()
    proc.wait(timeout=5.0)
    out = proc.stdout.read()
    err = proc.stderr.read()
    proc.stdout.close()
    proc.stderr.close()
    assert proc.returncode == 0
    assert out.decode("utf-8").strip().startswith("VERDICT OK:")
    assert err == b""
