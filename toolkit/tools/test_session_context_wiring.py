"""Delta tests for the WIRING-INTEGRITY machinery this kit ships,
split across tools/session_context.py (`hooks_path_autofix_line`,
`wiring_summary_line`) and tools/wiring_check.py (the read-only
`check_*` functions it wraps). This file exists ONLY to close a gap
found by comparing a sibling deployment's single-module wiring-channel
battery (git-channel: core.hooksPath + required .githooks/* files;
harness-channel: .claude/settings.json hook commands; python-channel:
shutil.which("python")) against this kit's OWN, already extensive
coverage in tools/test_wiring_check.py and tools/test_session_context.py
-- see the DELTA DECISION section below for exactly what was found
already covered, what does not apply here, and what was missing.

DELTA DECISION (checked BEFORE writing a single test here, per this
kit's sweep-before-porting practice):

 - git-channel (core.hooksPath correctness, required-hook presence/
   mode/tracking): tools/test_wiring_check.py already covers unset,
   correct, wrong-target, missing-entirely, mode-100644 vs 100755,
   present-but-untracked (test_hookspath_unset_is_an_issue,
   test_hookspath_correct_no_issue, test_hookspath_wrong_target_is_an_
   issue, test_required_hooks_missing_entirely, test_required_hooks_
   committed_mode_100644_is_an_issue, test_required_hooks_committed_
   mode_100755_is_clean, test_required_hooks_file_present_but_not_
   tracked); the WRITE side (self-heal on an unset hooksPath) is
   covered by tools/test_session_context.py's test_hooks_path_autofix_
   line_unset_autofixes / _write_failure_degrades_to_warning /
   _reports_failure_when_hook_files_missing / _already_set_returns_
   empty / _already_set_elsewhere_returns_empty / _never_raises_when_
   git_missing. NOT re-ported here. GENUINE GAP found and ported below
   (test_hookspath_relative_equivalent_spelling_is_clean): neither
   suite exercises a hooksPath value that is a DIFFERENT SPELLING of
   the same directory (e.g. "./.githooks" vs ".githooks") -- both
   existing suites only ever set the exact canonical string or an
   unrelated wrong path.
 - harness-channel (settings.json hook commands): tools/test_wiring_
   check.py already covers a missing hook file, a clean existing file,
   no settings.json at all, invalid JSON, an unparsed command shape,
   and de-duplication of a repeated filename (test_harness_hooks_*).
   Unlike the sibling deployment's harness_channel, this kit's
   check_harness_hooks does EXISTENCE ONLY -- it deliberately never
   imports the target file (see wiring_check.py's own docstring:
   "importing arbitrary host code as a side effect of a read-only
   auditor is out of scope"). The sibling suite's whole "unimportable
   -- SyntaxError / other exception / stdout-suppression-during-
   import" test group therefore has NO analog here at all -- not a
   gap, a documented scope difference; NOT ported. GENUINE GAP found
   and ported below: neither suite exercises (a) a settings.json whose
   "hooks" key is absent entirely, or present but with an empty hooks
   list (as opposed to no settings.json file at all, which IS
   covered) -- both are legal, "nothing to check" states that must
   not crash; (b) a hook command naming a file whose PATH CONTAINS
   SPACES -- wiring_check.py's own _HOOK_COMMAND_RE docstring
   explicitly claims this is handled ("deliberately allows spaces in
   the filename"), but no existing test exercises it, so the claim was
   unverified.
 - python-channel (shutil.which("python")): CONFIRMED ABSENT from this
   kit entirely -- grep across tools/session_context.py and
   tools/wiring_check.py finds no shutil.which call, no python_channel
   function, and no line reporting Python's own interpreter
   discoverability anywhere in the wiring machinery. This channel is
   NOT invented here; there is nothing to port it FROM within this
   kit's own architecture.

FINDING (reported, not fixed here -- outside this file's owns; see the
builder's handoff report for the full account): probing
check_git_hooks_path's own documented ASCII-only output invariant
("every string this module prints is plain ASCII") against a
non-ASCII (Cyrillic) core.hooksPath VALUE empirically produces a
NON-ASCII issue string (the raw configured value is interpolated via
`!r`, unsanitized) -- a real discrepancy between the module's own
claim and its behavior. Not pinned as a red test here (this file does
not own wiring_check.py); flagged for whoever does.

Run from the repo root: python -m pytest toolkit/tools/test_session_context_wiring.py -q
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wiring_check as wc  # noqa: E402


def _git(args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


def _init_repo(tmp_path) -> Path:
    root = tmp_path / "host_repo"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@example.com"], root)
    _git(["config", "user.name", "Test"], root)
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    _git(["add", "README.md"], root)
    _git(["commit", "-q", "-m", "init"], root)
    return root


def _write_settings(root: Path, payload: dict) -> None:
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / "settings.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_hook_commands(root: Path, commands: list) -> None:
    _write_settings(
        root,
        {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": c} for c in commands]}]}},
    )


# ---------------------------------------------------------------------------
# GAP 1: check_git_hooks_path -- a relative-but-EQUIVALENT spelling of
# .githooks (not the exact canonical string, and not "elsewhere" either)
# must resolve as clean, same as the exact spelling.
# ---------------------------------------------------------------------------


def test_hookspath_relative_equivalent_spelling_is_clean(tmp_path):
    repo = _init_repo(tmp_path)
    _git(["config", "--local", "core.hooksPath", "./.githooks"], repo)
    issues = wc.check_git_hooks_path(repo)
    assert issues == []
    # The value is left exactly as configured -- nothing needed fixing,
    # so nothing should have been rewritten.
    result = _git(["config", "core.hooksPath"], repo)
    assert result.stdout.strip() == "./.githooks"


# ---------------------------------------------------------------------------
# GAP 2: check_harness_hooks -- a settings.json that legally has NOTHING
# to check (no "hooks" key at all, or a "hooks" key with an empty hook
# list) must not crash and must report zero issues -- distinct from "no
# settings.json file at all", which IS already covered elsewhere.
# ---------------------------------------------------------------------------


def test_harness_hooks_no_hooks_key_does_not_crash(tmp_path):
    repo = _init_repo(tmp_path)
    _write_settings(repo, {})
    assert wc.check_harness_hooks(repo) == []


def test_harness_hooks_empty_hooks_list_does_not_crash(tmp_path):
    repo = _init_repo(tmp_path)
    _write_hook_commands(repo, [])
    assert wc.check_harness_hooks(repo) == []


# ---------------------------------------------------------------------------
# GAP 3: check_harness_hooks -- a hook command whose file path contains
# SPACES is parsed and checked correctly, not silently misparsed or
# skipped (both the "the file exists" and "the file is missing" sides).
# _HOOK_COMMAND_RE's own docstring claims this; empirically unverified
# until this test.
# ---------------------------------------------------------------------------


def test_harness_hooks_path_with_spaces_existing_file_is_clean(tmp_path):
    repo = _init_repo(tmp_path)
    tools_dir = repo / "tools"
    tools_dir.mkdir()
    (tools_dir / "weird name.py").write_text("X = 1\n", encoding="utf-8")
    _write_hook_commands(repo, ["python tools/weird name.py"])
    assert wc.check_harness_hooks(repo) == []


def test_harness_hooks_path_with_spaces_missing_file_is_an_issue(tmp_path):
    repo = _init_repo(tmp_path)
    _write_hook_commands(repo, ["python tools/missing name with spaces.py"])
    issues = wc.check_harness_hooks(repo)
    assert issues == ["hook file not found: tools/missing name with spaces.py"]
