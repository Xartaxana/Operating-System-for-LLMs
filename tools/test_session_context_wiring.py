"""Tests for the WIRING-INTEGRITY block in tools/session_context.py
(N1, docs/tasks/2026-07-21_validation-import.md). Three channels:
git-channel (core.hooksPath + required .githooks/* files), harness-channel
(.claude/settings.json hook commands exist + import cleanly), python-channel
(shutil.which("python")). Battery per CLAUDE.md R11: acceptance keys +
boundaries, no full regress.

Run from the repo root: python -m pytest tools/test_session_context_wiring.py -q
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import session_context as sc

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=10
    )


def _init_repo_with_hooks(tmp_path, hookspath="own"):
    """Builds a minimal git repo under tmp_path with a working .githooks/
    (pre-commit + commit-msg present) and core.hooksPath pointed at it,
    unless hookspath overrides that (None = leave unset; a Path = point
    hooksPath there instead)."""
    _git(["init", "-q"], tmp_path)
    githooks = tmp_path / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (githooks / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    if hookspath == "own":
        _git(["config", "core.hooksPath", str(githooks)], tmp_path)
    elif hookspath is None:
        pass  # leave unset
    else:
        _git(["config", "core.hooksPath", str(hookspath)], tmp_path)
    return tmp_path


def _write_settings(root, commands):
    """commands: list of raw command strings; wraps each into its own
    matcher/hook entry under a single SessionStart-like event so
    _parse_hook_commands() walks them all."""
    claude_dir = root / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": c} for c in commands]}
            ]
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Current repo, everything green -> exactly one OK line
# ---------------------------------------------------------------------------


def test_wiring_ok_on_current_repo():
    lines = sc.wiring_lines(REPO_ROOT)
    assert len(lines) == 1, lines
    assert lines[0].startswith("WIRING: OK ("), lines
    assert "git hooks: pre-commit, commit-msg" in lines[0]
    assert "harness hooks:" in lines[0] and "files importable" in lines[0]
    assert "python:" in lines[0]
    assert lines[0].isascii(), lines[0]


def test_git_hooks_channel_clean_on_current_repo():
    assert sc.git_hooks_channel(REPO_ROOT) == []


def test_harness_channel_clean_on_current_repo():
    warnings, count = sc.harness_channel(REPO_ROOT)
    assert warnings == []
    assert count >= 1


def test_python_channel_found():
    assert sc.python_channel() is not None


# ---------------------------------------------------------------------------
# 2. git-channel: missing required hook file
# ---------------------------------------------------------------------------


def test_git_channel_missing_required_file(tmp_path):
    _init_repo_with_hooks(tmp_path)
    (tmp_path / ".githooks" / "commit-msg").unlink()
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("commit-msg" in w and "missing" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 3. git-channel: hooksPath not set at all (boundary: bare/unset)
# ---------------------------------------------------------------------------


def test_git_channel_hookspath_unset(tmp_path):
    _init_repo_with_hooks(tmp_path, hookspath=None)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("core.hooksPath not set" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 4. git-channel: hooksPath points to a directory that exists but is not
#    <root>/.githooks (boundary: past the edge -- configured-but-wrong)
# ---------------------------------------------------------------------------


def test_git_channel_hookspath_points_elsewhere(tmp_path):
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    _init_repo_with_hooks(tmp_path, hookspath=other_dir)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("does not resolve to" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 5. git-channel: hooksPath points to a nonexistent directory
# ---------------------------------------------------------------------------


def test_git_channel_hookspath_points_to_missing_dir(tmp_path):
    missing = tmp_path / "does_not_exist_at_all"
    _init_repo_with_hooks(tmp_path, hookspath=missing)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("does not resolve to" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 6. harness-channel: file listed but does not exist on disk
# ---------------------------------------------------------------------------


def test_harness_channel_missing_file(tmp_path):
    _write_settings(tmp_path, ["python tools/does_not_exist.py"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any(w == "hook file not found: tools/does_not_exist.py" for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 7. harness-channel: file exists but fails to import (SyntaxError)
# ---------------------------------------------------------------------------


def test_harness_channel_unimportable_syntax_error(tmp_path):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "broken.py").write_text("def f(:\n    pass\n", encoding="utf-8")
    _write_settings(tmp_path, ["python tools/broken.py"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any(w == "import failed: tools/broken.py (SyntaxError)" for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 8. harness-channel: import raises some other exception class (not
#    SyntaxError) -- the class name must still surface, not just "broken"
# ---------------------------------------------------------------------------


def test_harness_channel_unimportable_runtime_error(tmp_path):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "explodes.py").write_text(
        "raise ValueError('boom at import time')\n", encoding="utf-8"
    )
    _write_settings(tmp_path, ["python tools/explodes.py"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any(w == "import failed: tools/explodes.py (ValueError)" for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 9. harness-channel: malformed settings.json -> WARNING, not an exception
# ---------------------------------------------------------------------------


def test_harness_channel_malformed_settings_json(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("{not valid json", encoding="utf-8")
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any("not valid JSON" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


def test_harness_channel_missing_settings_json(tmp_path):
    # No .claude/settings.json at all -- must warn, not raise.
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any("not readable" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 10. harness-channel: empty hooks list -> must not crash
# ---------------------------------------------------------------------------


def test_harness_channel_empty_hooks_does_not_crash(tmp_path):
    _write_settings(tmp_path, [])
    warnings, count = sc.harness_channel(tmp_path)
    assert warnings == []
    assert count == 0


def test_harness_channel_no_hooks_key_does_not_crash(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(json.dumps({}), encoding="utf-8")
    warnings, count = sc.harness_channel(tmp_path)
    assert warnings == []
    assert count == 0


# ---------------------------------------------------------------------------
# 11. harness-channel: command of a different shape (not "python ...")
#     -> honest "unparsed command" WARNING, not a crash
# ---------------------------------------------------------------------------


def test_harness_channel_unparsed_command_form(tmp_path):
    _write_settings(tmp_path, ["node tools/foo.js"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any(w == "unparsed hook command: node tools/foo.js" for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


def test_harness_channel_command_with_extra_flags_is_unparsed(tmp_path):
    # Boundary: same interpreter, same file, but an extra flag makes the
    # line not match the exact recognized shape -- still an honest
    # "unparsed" warning, not a silent skip and not a crash.
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "ok.py").write_text("X = 1\n", encoding="utf-8")
    _write_settings(tmp_path, ["python tools/ok.py --flag"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any("unparsed hook command" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 12. harness-channel: a path with spaces in the command is still parsed
#     and checked correctly (not misparsed, not silently skipped)
# ---------------------------------------------------------------------------


def test_harness_channel_path_with_spaces_ok(tmp_path):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "weird name.py").write_text("X = 1\n", encoding="utf-8")
    _write_settings(tmp_path, ["python tools/weird name.py"])
    warnings, count = sc.harness_channel(tmp_path)
    assert warnings == []
    assert count == 1


def test_harness_channel_path_with_spaces_missing_file_warns(tmp_path):
    _write_settings(tmp_path, ["python tools/missing name with spaces.py"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any(
        w == "hook file not found: tools/missing name with spaces.py" for w in warnings
    ), warnings
    assert all(w.isascii() for w in warnings), warnings


# ---------------------------------------------------------------------------
# 13. python-channel: not found -> WARNING (via wiring_lines(), monkeypatched)
# ---------------------------------------------------------------------------


def test_wiring_lines_python_not_found(tmp_path, monkeypatch):
    _init_repo_with_hooks(tmp_path)
    _write_settings(tmp_path, [])
    monkeypatch.setattr(sc, "python_channel", lambda: None)
    lines = sc.wiring_lines(tmp_path)
    assert lines == ["WIRING WARNING: python not found on PATH"], lines
    assert not any(line.startswith("WIRING: OK") for line in lines)


# ---------------------------------------------------------------------------
# 14. wiring_lines() aggregates multiple simultaneous discrepancies as
#     separate WARNING lines (git channel + harness channel together)
# ---------------------------------------------------------------------------


def test_wiring_lines_multiple_warnings(tmp_path):
    _init_repo_with_hooks(tmp_path, hookspath=None)  # git-channel warning
    _write_settings(tmp_path, ["python tools/nope.py"])  # harness-channel warning
    lines = sc.wiring_lines(tmp_path)
    assert all(line.startswith("WIRING WARNING:") for line in lines)
    assert all(line.isascii() for line in lines), lines
    assert len(lines) >= 2, lines
    assert not any(line.startswith("WIRING: OK") for line in lines)


# ---------------------------------------------------------------------------
# 15. fail-open backstop: an unforeseen exception inside the channel
#     computation degrades to ONE WARNING line, never propagates
# ---------------------------------------------------------------------------


def test_wiring_lines_never_raises_on_internal_failure(tmp_path, monkeypatch):
    def _boom(_root):
        raise RuntimeError("unexpected internal failure")

    monkeypatch.setattr(sc, "git_hooks_channel", _boom)
    lines = sc.wiring_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0].startswith("WIRING WARNING:")
    assert "RuntimeError" in lines[0]
    assert lines[0].isascii(), lines[0]


# ---------------------------------------------------------------------------
# ASCII invariant boundary: a non-ASCII exception message (e.g. from a
# hook file whose SyntaxError points at non-ASCII source text) must not
# break the file's plain-ASCII output invariant -- this is exactly the
# risk _ascii_sanitize exists to close (Lead ruling on the N1 spec
# correction).
# ---------------------------------------------------------------------------


def test_harness_channel_import_error_with_non_ascii_message_stays_ascii(tmp_path):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    # A module whose import raises with a non-ASCII message (Cyrillic) --
    # class name alone is used in the WARNING text (spec's literal
    # example format), so this also guards against a future change that
    # starts interpolating str(exc) without sanitizing it first.
    (tools_dir / "nonascii.py").write_text(
        "raise ValueError('Ошибка импорта')\n",
        encoding="utf-8",
    )
    _write_settings(tmp_path, ["python tools/nonascii.py"])
    warnings, count = sc.harness_channel(tmp_path)
    assert count == 0
    assert any(w == "import failed: tools/nonascii.py (ValueError)" for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


def test_wiring_lines_stays_ascii_with_non_ascii_hooks_path(tmp_path):
    # A hooksPath value containing non-ASCII characters (e.g. a Cyrillic
    # path component) must not break the ASCII invariant of the final
    # WARNING line -- _ascii_sanitize replaces the offending characters
    # rather than letting them through or crashing print().
    other_dir = tmp_path / "другой"  # "elsewhere" in Cyrillic
    other_dir.mkdir()
    _init_repo_with_hooks(tmp_path, hookspath=other_dir)
    lines = sc.wiring_lines(tmp_path)
    assert all(line.isascii() for line in lines), lines
    assert any("does not resolve to" in line for line in lines), lines


# ---------------------------------------------------------------------------
# 16. build_context_lines() carries the wiring block through into the
#     same output stream as boot_budget_lines() etc., and main() still
#     never raises / always exits 0 (outer fail-open untouched).
# ---------------------------------------------------------------------------


def test_build_context_lines_includes_wiring(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "config.yaml").write_text("model_list: []\n", encoding="utf-8")
    (tmp_path / "gateway" / "budgets.yaml").write_text("quota_windows: {}\n", encoding="utf-8")
    lines = sc.build_context_lines(root=tmp_path)
    assert any(line.startswith("WIRING") for line in lines), lines


# ---------------------------------------------------------------------------
# 17. _WIRING_LINE_MAX_LEN boundary (critic-gate finding, R11: a limit
#     this module introduces needs a test AT it and BEYOND it). The
#     boundary is genuinely reachable in practice: a hooksPath mismatch
#     warning interpolates two paths (raw + expected), each already
#     capped at 150 chars by git_hooks_channel's own per-component
#     _ascii_sanitize call, plus ~100 chars of fixed English text --
#     comfortably over 300 once the "WIRING WARNING: " prefix is added.
#     Reproducing that organically requires OS-level long paths, which
#     hit Windows' MAX_PATH limit in this environment when attempted
#     (verified: a single 220-char path component under a short temp
#     dir failed with WinError 3, "path not found", well short of a
#     realistic hooksPath value) -- so these tests drive the exact same
#     code path (wiring_lines()'s final _ascii_sanitize backstop) via a
#     monkeypatched channel instead, which is deterministic and portable
#     rather than dependent on the test host's filesystem path limits.
# ---------------------------------------------------------------------------


def _wiring_prefix() -> str:
    return "WIRING WARNING: "


def test_wiring_line_at_max_len_boundary_not_truncated(monkeypatch):
    prefix = _wiring_prefix()
    fact = "B" * (sc._WIRING_LINE_MAX_LEN - len(prefix))  # exactly at the boundary
    monkeypatch.setattr(sc, "git_hooks_channel", lambda root: [fact])
    monkeypatch.setattr(sc, "harness_channel", lambda root: ([], 0))
    monkeypatch.setattr(sc, "python_channel", lambda: "/usr/bin/python")

    lines = sc.wiring_lines(REPO_ROOT)

    assert len(lines) == 1
    assert len(lines[0]) == sc._WIRING_LINE_MAX_LEN
    assert lines[0] == prefix + fact  # unchanged: right at the limit, nothing cut


def test_wiring_line_one_past_max_len_truncated_by_exactly_one(monkeypatch):
    prefix = _wiring_prefix()
    fact = "C" * (sc._WIRING_LINE_MAX_LEN - len(prefix) + 1)  # exactly one past the boundary
    monkeypatch.setattr(sc, "git_hooks_channel", lambda root: [fact])
    monkeypatch.setattr(sc, "harness_channel", lambda root: ([], 0))
    monkeypatch.setattr(sc, "python_channel", lambda: "/usr/bin/python")

    lines = sc.wiring_lines(REPO_ROOT)

    assert len(lines) == 1
    assert len(lines[0]) == sc._WIRING_LINE_MAX_LEN
    assert lines[0] == (prefix + fact)[: sc._WIRING_LINE_MAX_LEN]


def test_wiring_line_far_past_max_len_truncated_to_limit(monkeypatch):
    # The realistic case the critic pointed at: a hooksPath-mismatch-shaped
    # message well over 300 chars (two 150-char-capped paths + boilerplate).
    long_warning = "A" * 500
    monkeypatch.setattr(sc, "git_hooks_channel", lambda root: [long_warning])
    monkeypatch.setattr(sc, "harness_channel", lambda root: ([], 0))
    monkeypatch.setattr(sc, "python_channel", lambda: "/usr/bin/python")

    lines = sc.wiring_lines(REPO_ROOT)

    assert len(lines) == 1
    assert len(lines[0]) == sc._WIRING_LINE_MAX_LEN
    prefix = _wiring_prefix()
    assert lines[0] == (prefix + long_warning)[: sc._WIRING_LINE_MAX_LEN]
    assert lines[0].isascii()


# ---------------------------------------------------------------------------
# 18. Hardening (Lead ruling on critic-gate note): exec_module during the
#     harness-channel import check redirects stdout/stderr to os.devnull.
#     All 8 hook files checked in THIS repo are silent at import time
#     (t-256), so this changes nothing today -- but a future hook file
#     that prints at import time (a debug leftover, a library that logs
#     on load) must not be able to leak arbitrary, non-ASCII-sanitized
#     text straight into this hook's own console output, bypassing
#     _ascii_sanitize entirely. capsys captures whatever reaches the
#     REAL stdout/stderr at the end of the test process -- if the
#     redirect inside harness_channel() did not work, the module's
#     print() would land in capsys's buffer, because redirect_stdout
#     temporarily replaces the very sys.stdout object capsys is also
#     patching.
# ---------------------------------------------------------------------------


def test_harness_channel_suppresses_top_level_print_during_import(tmp_path, capsys):
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "noisy.py").write_text(
        "print('Кириллица leak')\n"
        "import sys\n"
        "print('stderr leak too', file=sys.stderr)\n"
        "X = 1\n",
        encoding="utf-8",
    )
    _write_settings(tmp_path, ["python tools/noisy.py"])

    warnings, count = sc.harness_channel(tmp_path)
    captured = capsys.readouterr()

    assert warnings == []  # the module still imports successfully -- printing is not an error
    assert count == 1
    assert captured.out == ""
    assert captured.err == ""


def test_harness_channel_suppresses_print_even_when_import_then_fails(tmp_path, capsys):
    # Boundary: a module that prints AND THEN raises -- the suppression
    # must hold on the failure path too, not just the success path.
    tools_dir = tmp_path / "tools"
    tools_dir.mkdir()
    (tools_dir / "noisy_broken.py").write_text(
        "print('leak before failure')\n"
        "raise RuntimeError('boom')\n",
        encoding="utf-8",
    )
    _write_settings(tmp_path, ["python tools/noisy_broken.py"])

    warnings, count = sc.harness_channel(tmp_path)
    captured = capsys.readouterr()

    assert count == 0
    assert any(w == "import failed: tools/noisy_broken.py (RuntimeError)" for w in warnings), warnings
    assert captured.out == ""
    assert captured.err == ""


def test_main_never_raises_and_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    (tmp_path / "logs").mkdir()
    (tmp_path / "gateway").mkdir()
    (tmp_path / "gateway" / "config.yaml").write_text("model_list: []\n", encoding="utf-8")
    (tmp_path / "gateway" / "budgets.yaml").write_text("quota_windows: {}\n", encoding="utf-8")
    assert sc.main(root=tmp_path) == 0
