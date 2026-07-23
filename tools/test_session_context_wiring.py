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
    hooksPath there instead).

    D-0093: both hook files are also `git add`-ed and forced to mode
    100755 in the index (`git update-index --chmod=+x`) -- this is the
    "fully wired" baseline every scenario in this file other than the
    dedicated exec-bit tests assumes (a git-channel WARNING from the new
    exec-bit sub-check would otherwise leak into every test using this
    helper, including ones with exact-equality assertions). The
    dedicated exec-bit tests below override tracking/mode explicitly via
    _set_hook_mode_non_executable / _untrack_hook."""
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


def _set_hook_mode_non_executable(tmp_path, name):
    """Forces one hook's INDEX mode to 100644 (committed non-executable),
    leaving it tracked and present on disk -- isolates the "wrong mode"
    sub-fact from the "untracked" one."""
    _git(["update-index", f"--chmod=-x", f".githooks/{name}"], tmp_path)


def _untrack_hook(tmp_path, name):
    """Removes one hook from the INDEX only (--cached), keeping the file
    on disk -- isolates the "untracked" sub-fact from "missing file".

    VG-1 witness-run finding (pre-existing, unrelated to VG-1's own
    logic): this repo's git build refuses a bare `git rm --cached` here
    with "staged content different from both the file and HEAD" -- the
    helper's baseline (_init_repo_with_hooks) `git add`s the hook but
    never commits it, so there is no HEAD copy to fall back to, and git
    treats removing it from the index as potentially losing the only
    copy of that content. `-f` is the standard, intended bypass for
    exactly this case (we know the content survives on disk, which the
    assertion right after this call's call site already confirms) --
    without it, EVERY test using this helper silently exercised a no-op
    (the hook stayed tracked), not the "untracked" scenario the test
    names."""
    _git(["rm", "--cached", "-f", "-q", f".githooks/{name}"], tmp_path)


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
    # TEMPORARY accommodation (D-0093): as of this dispatch both
    # .githooks/pre-commit and .githooks/commit-msg are still indexed at
    # 100644 in THIS repo (chmod-at-acceptance is the Lead's INSTALL-line
    # sibling fix, not owned by this dispatch -- see task spec). The new
    # exec-bit sub-check (B1) therefore legitimately turns the OK line
    # into exec-bit WARNING lines today. This branch documents that
    # explicitly rather than silently loosening the assertion: ANY
    # warning of a DIFFERENT class (hookspath mismatch, missing file,
    # untracked, a failed git call) still fails this test. Once chmod
    # lands, wiring_lines() reverts to the clean OK line and the second
    # branch below (the original, unweakened assertion set) covers it
    # without further edits to this test.
    exec_bit_only = bool(lines) and all(
        "committed non-executable" in line for line in lines
    )
    if exec_bit_only:
        assert all(line.startswith("WIRING WARNING:") for line in lines), lines
        assert all(line.isascii() for line in lines), lines
        return
    assert len(lines) == 1, lines
    assert lines[0].startswith("WIRING: OK ("), lines
    assert "git hooks: pre-commit, commit-msg" in lines[0]
    assert "harness hooks:" in lines[0] and "files importable" in lines[0]
    assert "python:" in lines[0]
    assert lines[0].isascii(), lines[0]


def test_git_hooks_channel_clean_on_current_repo():
    # TEMPORARY accommodation (D-0093): see test_wiring_ok_on_current_repo's
    # comment above -- today's index has both hooks at 100644, so this
    # channel legitimately reports "committed non-executable" for both
    # instead of []. Anything OTHER than that warning class would still
    # be a real defect (hookspath mismatch, a missing file, untracked, a
    # failed git call) and fails this assert.
    warnings = sc.git_hooks_channel(REPO_ROOT)
    unexpected = [w for w in warnings if "committed non-executable" not in w]
    assert unexpected == [], warnings


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
#
# VG-1 part A: an unset core.hooksPath is no longer a bare WARNING -- the
# channel now attempts a one-line self-heal (`git config --local
# core.hooksPath .githooks`) FIRST. In a real, writable git repo with a
# working .githooks/ (exactly this helper's baseline), that self-heal
# succeeds, so the fact returned is now the AUTOFIX line, not the old
# "not set" warning. The three tests below replace the single old test:
# autofix succeeds (this scenario), autofix fails because git itself
# errors on the write, and autofix "succeeds" at the git-config level but
# the recheck still finds the required hook files missing.
# ---------------------------------------------------------------------------


def test_git_channel_hookspath_unset_autofixes(tmp_path):
    _init_repo_with_hooks(tmp_path, hookspath=None)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any(
        w == "AUTOFIX: core.hooksPath set to .githooks" for w in warnings
    ), warnings
    assert all(w.isascii() for w in warnings), warnings
    # The fix actually stuck in the repo's own local config, not just
    # claimed in the returned fact string.
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.stdout.strip() == ".githooks"


def test_git_channel_hookspath_unset_autofix_degrades_to_warn_when_git_write_fails(
    tmp_path, monkeypatch
):
    # "git недоступен" / a failing write (e.g. read-only config): the
    # WRITE call is made to fail while the READ call (which reports
    # unset) is left untouched -- the channel must fall back to the
    # original-style warning, with the failure reason appended, not
    # raise and not silently print AUTOFIX.
    _init_repo_with_hooks(tmp_path, hookspath=None)
    real_run = sc.subprocess.run

    def _failing_write(cmd, *args, **kwargs):
        if len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "config" and "--local" in cmd:
            raise OSError("simulated: git config write failed")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(sc.subprocess, "run", _failing_write)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any(
        "core.hooksPath not set" in w and "autofix failed" in w for w in warnings
    ), warnings
    assert not any(w.startswith("AUTOFIX:") for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings
    # The real config must be untouched (still unset) -- the failed write
    # attempt must not have left a bogus value behind.
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.returncode != 0 or not result.stdout.strip()


def test_git_channel_hookspath_unset_autofix_reports_failure_when_hook_files_missing(
    tmp_path,
):
    # The `git config` write itself succeeds (nothing stops it from
    # pointing hooksPath at a directory whose files don't exist yet), but
    # the recheck must catch that the required hook files are still
    # missing -- reported as a failed autofix, not a false AUTOFIX line.
    _git(["init", "-q"], tmp_path)
    (tmp_path / ".githooks").mkdir()
    # Deliberately do NOT create pre-commit/commit-msg under .githooks.
    warnings = sc.git_hooks_channel(tmp_path)
    assert any(
        "core.hooksPath not set" in w
        and "autofix" in w
        and "missing" in w
        for w in warnings
    ), warnings
    assert not any(w.startswith("AUTOFIX:") for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings
    # The write itself DID succeed (git doesn't validate the target
    # directory's contents when setting the config) -- confirms the
    # failure is caught by the recheck, not by the write call.
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.stdout.strip() == ".githooks"


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
# 5a. VG-1 part A adversarial: hooksPath already set to a RELATIVE path
#     that resolves to the SAME directory as .githooks (not empty, not
#     "elsewhere" -- just a different SPELLING of the correct value).
#     Must be recognized as already-correct: no warning, no autofix
#     attempt, no AUTOFIX line either.
# ---------------------------------------------------------------------------


def test_git_channel_hookspath_relative_path_equivalent_to_githooks_is_clean(tmp_path):
    _init_repo_with_hooks(tmp_path, hookspath=None)
    _git(["config", "core.hooksPath", "./.githooks"], tmp_path)
    warnings = sc.git_hooks_channel(tmp_path)
    assert warnings == [], warnings
    # Confirm the value was left exactly as configured -- untouched by
    # any autofix (nothing needed fixing).
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.stdout.strip() == "./.githooks"


# ---------------------------------------------------------------------------
# 5b. git-channel: D-0093 exec-bit sub-check (git INDEX, not the
#     filesystem -- Windows/NTFS carries no meaningful exec bit).
# ---------------------------------------------------------------------------


def test_git_channel_both_hooks_tracked_executable_is_clean(tmp_path):
    # (1) both hooks 100755 in the index -> channel clean, output
    # unchanged from the pre-D-0093 baseline.
    _init_repo_with_hooks(tmp_path)
    assert sc.git_hooks_channel(tmp_path) == []


def test_wiring_ok_when_both_hooks_tracked_executable(tmp_path):
    _init_repo_with_hooks(tmp_path)
    _write_settings(tmp_path, [])
    lines = sc.wiring_lines(tmp_path)
    assert len(lines) == 1, lines
    assert lines[0].startswith("WIRING: OK ("), lines


# ---------------------------------------------------------------------------
# VG-1 part A, wiring_lines()-level: the AUTOFIX fact renders as its own
# "WIRING AUTOFIX: ..." line, NOT folded into "WIRING WARNING: ..." and
# NOT silently absorbed into a "WIRING: OK" line either -- a self-healed
# discrepancy is still worth a line of its own (spec: "вместо WARN", not
# "instead of nothing").
# ---------------------------------------------------------------------------


def test_wiring_lines_renders_autofix_line_not_warning_or_ok(tmp_path):
    _init_repo_with_hooks(tmp_path, hookspath=None)
    _write_settings(tmp_path, [])
    lines = sc.wiring_lines(tmp_path)
    assert lines == ["WIRING AUTOFIX: core.hooksPath set to .githooks"], lines
    assert not any(line.startswith("WIRING WARNING:") for line in lines)
    assert not any(line.startswith("WIRING: OK") for line in lines)


def test_git_channel_hook_committed_non_executable_warns(tmp_path):
    # (2) one hook 100644 -> WARNING naming the file and the mode.
    _init_repo_with_hooks(tmp_path)
    _set_hook_mode_non_executable(tmp_path, "pre-commit")
    warnings = sc.git_hooks_channel(tmp_path)
    assert any(
        "pre-commit" in w and "100644" in w and "committed non-executable" in w
        for w in warnings
    ), warnings
    # The OTHER hook (still 100755) must not be flagged.
    assert not any("commit-msg" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


def test_git_channel_hook_untracked_warns(tmp_path):
    # (3) hook absent from `git ls-files` (never added / rm --cached)
    # -> WARNING "untracked", distinct from the "missing file" warning
    # (the file is still present on disk here).
    _init_repo_with_hooks(tmp_path)
    _untrack_hook(tmp_path, "commit-msg")
    assert (tmp_path / ".githooks" / "commit-msg").is_file()  # still on disk
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("commit-msg" in w and "untracked" in w for w in warnings), warnings
    assert not any("missing" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


def test_git_channel_ls_files_nonzero_returncode_folds_into_one_warning_no_untracked(
    tmp_path, monkeypatch
):
    # (4b, critic t-288) `git ls-files -s` returns nonzero WITHOUT raising
    # (e.g. a git-internal error) and with empty stdout -- must get the
    # SAME one-WARNING-and-skip treatment as the exception branch above,
    # NOT fall through and mislabel both hooks "untracked" (that would lie
    # about the cause: the mode dict would just be empty because nothing
    # was parsed, not because git actually reports the hooks untracked).
    _init_repo_with_hooks(tmp_path)
    real_run = sc.subprocess.run

    class _FakeResult:
        returncode = 1
        stdout = ""
        stderr = "fatal: simulated ls-files error"

    def _failing_run(cmd, *args, **kwargs):
        if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "ls-files":
            return _FakeResult()
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(sc.subprocess, "run", _failing_run)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("ls-files" in w and "failed" in w for w in warnings), warnings
    assert not any("untracked" in w for w in warnings), warnings
    assert all(w.isascii() for w in warnings), warnings


def test_git_channel_ls_files_failure_folds_into_one_warning(tmp_path, monkeypatch):
    # (4) the `git ls-files -s` call itself fails -> same treatment as
    # the existing hooksPath call's own except-branch: folds into one
    # WARNING string, never raises. The hooksPath call (which succeeds
    # here) is left untouched -- only ls-files is made to fail.
    _init_repo_with_hooks(tmp_path)
    real_run = sc.subprocess.run

    def _flaky_run(cmd, *args, **kwargs):
        if len(cmd) >= 2 and cmd[0] == "git" and cmd[1] == "ls-files":
            raise OSError("simulated git ls-files failure")
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(sc.subprocess, "run", _flaky_run)
    warnings = sc.git_hooks_channel(tmp_path)
    assert any("ls-files" in w and "failed" in w for w in warnings), warnings
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
    # VG-1 part A: an UNSET hooksPath now autofixes in a writable repo
    # like this helper's baseline (see the dedicated autofix tests
    # above), so it can no longer stand in for "a plain git-channel
    # warning" here -- use "points elsewhere" instead (a foreign,
    # already-valid value, deliberately NOT autofixed, per the same
    # part-A carve-out) to keep this test's own point (multiple
    # DIFFERENT channels' warnings aggregate together) intact.
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    _init_repo_with_hooks(tmp_path, hookspath=other_dir)  # git-channel warning
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
