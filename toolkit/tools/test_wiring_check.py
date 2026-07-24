"""Tests for tools/wiring_check.py (D-0092/D-0093 -- generalized host-
wiring checker). All checks run subprocess `git` calls, so every test
builds an isolated tmp-repo fixture (`git init` in tmp_path) rather than
touching this repo's own .git; tests never assume anything about the
state of the OS repo they happen to run inside.

Boundaries covered per the task's DoD: a hook committed at mode 100644
(the class F-53/D-0093 exists to catch), a missing hook file, an
adoption-ledger "adopt" row with no live wiring behind it, and a
corrupt/unreadable ledger failing OPEN (a WARN, not a crash).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wiring_check  # noqa: E402


def _git(args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "host_repo"
    root.mkdir()
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@example.com"], root)
    _git(["config", "user.name", "Test"], root)
    # An initial commit so ls-files/log have something to operate against.
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    _git(["add", "README.md"], root)
    _git(["commit", "-q", "-m", "init"], root)
    return root


def _write_settings(root: Path, commands: list):
    settings_dir = root / ".claude"
    settings_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": c} for c in commands]}
            ]
        }
    }
    (settings_dir / "settings.json").write_text(json.dumps(payload), encoding="utf-8")


def _add_githook(root: Path, name: str, executable: bool):
    githooks = root / ".githooks"
    githooks.mkdir(exist_ok=True)
    hook_path = githooks / name
    hook_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    _git(["add", str(hook_path.relative_to(root))], root)
    if executable:
        _git(["update-index", "--chmod=+x", str(hook_path.relative_to(root))], root)
    _git(["commit", "-q", "-m", f"add {name}"], root)


# ---------------------------------------------------------------------
# check_git_hooks_path
# ---------------------------------------------------------------------


def test_hookspath_unset_is_an_issue(repo):
    issues = wiring_check.check_git_hooks_path(repo)
    assert issues == ["core.hooksPath not set"]


def test_hookspath_correct_no_issue(repo):
    _git(["config", "--local", "core.hooksPath", ".githooks"], repo)
    issues = wiring_check.check_git_hooks_path(repo)
    assert issues == []


def test_hookspath_wrong_target_is_an_issue(repo):
    _git(["config", "--local", "core.hooksPath", "some/other/dir"], repo)
    issues = wiring_check.check_git_hooks_path(repo)
    assert len(issues) == 1
    assert "does not resolve to" in issues[0]


# ---------------------------------------------------------------------
# check_required_hooks -- the mode-100644 boundary (F-53/D-0093)
# ---------------------------------------------------------------------


def test_required_hooks_missing_entirely(repo):
    issues = wiring_check.check_required_hooks(repo)
    # Both "file missing" AND "untracked in index" fire independently
    # for each of the two required hooks -- 4 issues total.
    assert any("hook file missing: .githooks/pre-commit" in i for i in issues)
    assert any("hook file missing: .githooks/commit-msg" in i for i in issues)
    assert any("pre-commit untracked" in i for i in issues)
    assert any("commit-msg untracked" in i for i in issues)


def test_required_hooks_committed_mode_100644_is_an_issue(repo):
    # The exact boundary this check exists for: a hook file present and
    # tracked, but committed WITHOUT the executable bit -- a dead gate
    # on a Linux clone even though it looks fine on Windows/NTFS.
    _add_githook(repo, "pre-commit", executable=False)
    _add_githook(repo, "commit-msg", executable=False)
    issues = wiring_check.check_required_hooks(repo)
    assert any("pre-commit" in i and "100644" in i for i in issues)
    assert any("commit-msg" in i and "100644" in i for i in issues)
    assert not any("missing" in i for i in issues)
    assert not any("untracked" in i for i in issues)


def test_required_hooks_committed_mode_100755_is_clean(repo):
    _add_githook(repo, "pre-commit", executable=True)
    _add_githook(repo, "commit-msg", executable=True)
    issues = wiring_check.check_required_hooks(repo)
    assert issues == []


def test_required_hooks_file_present_but_not_tracked(repo):
    # On disk, never git-added -- must report "untracked", NOT a mode
    # issue (there is no index entry to have a mode at all).
    githooks = repo / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (githooks / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    issues = wiring_check.check_required_hooks(repo)
    assert any("pre-commit untracked" in i for i in issues)
    assert any("commit-msg untracked" in i for i in issues)
    assert not any("missing" in i for i in issues)


# ---------------------------------------------------------------------
# check_harness_hooks
# ---------------------------------------------------------------------


def test_harness_hooks_missing_file_is_an_issue(repo):
    _write_settings(repo, ["python tools/nonexistent_hook.py"])
    issues = wiring_check.check_harness_hooks(repo)
    assert issues == ["hook file not found: tools/nonexistent_hook.py"]


def test_harness_hooks_existing_file_is_clean(repo):
    (repo / "tools").mkdir()
    (repo / "tools" / "my_hook.py").write_text("pass\n", encoding="utf-8")
    _write_settings(repo, ["python tools/my_hook.py"])
    issues = wiring_check.check_harness_hooks(repo)
    assert issues == []


def test_harness_hooks_no_settings_file_is_an_issue(repo):
    issues = wiring_check.check_harness_hooks(repo)
    assert len(issues) == 1
    assert "not readable" in issues[0]


def test_harness_hooks_invalid_json_is_an_issue(repo):
    settings_dir = repo / ".claude"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text("{not valid json", encoding="utf-8")
    issues = wiring_check.check_harness_hooks(repo)
    assert len(issues) == 1
    assert "not valid JSON" in issues[0]


def test_harness_hooks_unparsed_command_form_is_an_issue(repo):
    _write_settings(repo, ["python3 tools/my_hook.py --flag"])
    issues = wiring_check.check_harness_hooks(repo)
    assert issues == ["unparsed hook command: python3 tools/my_hook.py --flag"]


def test_harness_hooks_dedupes_repeated_filename(repo):
    _write_settings(repo, ["python tools/missing.py", "python tools/missing.py"])
    issues = wiring_check.check_harness_hooks(repo)
    assert issues == ["hook file not found: tools/missing.py"]


# ---------------------------------------------------------------------
# check_untracked_enforcement_files
# ---------------------------------------------------------------------


def test_untracked_extra_file_under_githooks_is_an_issue(repo):
    _add_githook(repo, "pre-commit", executable=True)
    (repo / ".githooks" / "stray-script.sh").write_text("echo hi\n", encoding="utf-8")
    issues = wiring_check.check_untracked_enforcement_files(repo)
    assert issues == ["untracked enforcement file: .githooks/stray-script.sh"]


def test_untracked_no_extra_files_is_clean(repo):
    _add_githook(repo, "pre-commit", executable=True)
    issues = wiring_check.check_untracked_enforcement_files(repo)
    assert issues == []


def test_untracked_no_githooks_dir_is_clean(repo):
    # Absence of .githooks/ entirely is check_required_hooks's job to
    # report, not this check's.
    issues = wiring_check.check_untracked_enforcement_files(repo)
    assert issues == []


# ---------------------------------------------------------------------
# check_adoption_ledger (D-0092) -- adopt-row-without-live-wiring
# boundary, and the fail-open-on-corrupt-ledger boundary
# ---------------------------------------------------------------------


_LEDGER_TEMPLATE = """# Adoption Ledger

| Kit mechanism | Status | Basis / trigger |
|---|---|---|
| Mechanism gate + symmetry map (`tools/mechanism_gate.py`, `.githooks/commit-msg`, `docs/SIBLING_MAP.md`) | adopt | |
| Skills (`.claude/skills/*`) | adopt | |
"""


def test_ledger_adopt_row_without_live_git_wiring_warns(repo):
    (repo / "ADOPTION_LEDGER.md").write_text(_LEDGER_TEMPLATE, encoding="utf-8")
    git_issues = ["core.hooksPath not set"]
    issues = wiring_check.check_adoption_ledger(repo, git_issues, [])
    assert len(issues) == 1
    assert "Mechanism gate" in issues[0]
    assert "adopt" in issues[0]
    # The "Skills" row is not reconciled at all -- deliberately out of
    # this check's narrow scope (see module docstring).
    assert not any("Skills" in i for i in issues)


def test_ledger_adopt_row_with_clean_git_wiring_no_warn(repo):
    (repo / "ADOPTION_LEDGER.md").write_text(_LEDGER_TEMPLATE, encoding="utf-8")
    issues = wiring_check.check_adoption_ledger(repo, [], [])
    assert issues == []


def test_ledger_absent_is_not_an_issue(repo):
    issues = wiring_check.check_adoption_ledger(repo, ["core.hooksPath not set"], [])
    assert issues == []


def test_ledger_non_adopt_status_not_reconciled(repo):
    text = (
        "| Kit mechanism | Status | Basis / trigger |\n"
        "|---|---|---|\n"
        "| Mechanism gate + symmetry map (`.githooks/commit-msg`) | deferred(x) | not yet |\n"
    )
    (repo / "ADOPTION_LEDGER.md").write_text(text, encoding="utf-8")
    issues = wiring_check.check_adoption_ledger(repo, ["core.hooksPath not set"], [])
    assert issues == []


def test_ledger_broken_encoding_fails_open_with_warn(repo):
    # Invalid UTF-8 bytes -- read_text(encoding="utf-8") raises
    # UnicodeDecodeError; must fail OPEN to a WARN, not propagate.
    (repo / "ADOPTION_LEDGER.md").write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    issues = wiring_check.check_adoption_ledger(repo, ["core.hooksPath not set"], [])
    assert len(issues) == 1
    assert "not readable" in issues[0]


def test_ledger_harness_keyword_row_reconciled_against_harness_issues(repo):
    text = (
        "| Kit mechanism | Status | Basis / trigger |\n"
        "|---|---|---|\n"
        "| Tier verification / SessionStart (`tools/session_context.py`) | adopt | |\n"
    )
    (repo / "ADOPTION_LEDGER.md").write_text(text, encoding="utf-8")
    issues = wiring_check.check_adoption_ledger(repo, [], ["hook file not found: tools/x.py"])
    assert len(issues) == 1
    assert "harness-hooks wiring" in issues[0]


# ---------------------------------------------------------------------
# check_wiring() aggregation + never-raises contract
# ---------------------------------------------------------------------


def test_check_wiring_all_clean_ok_true(repo):
    _git(["config", "--local", "core.hooksPath", ".githooks"], repo)
    _add_githook(repo, "pre-commit", executable=True)
    _add_githook(repo, "commit-msg", executable=True)
    _write_settings(repo, [])
    result = wiring_check.check_wiring(repo)
    assert result == {"ok": True, "issues": []}


def test_check_wiring_aggregates_multiple_issue_sources(repo):
    # Nothing configured at all -- hooksPath unset, hooks missing,
    # no settings.json.
    result = wiring_check.check_wiring(repo)
    assert result["ok"] is False
    assert any("core.hooksPath not set" in i for i in result["issues"])
    assert any("not readable" in i for i in result["issues"])


def test_check_wiring_never_raises_on_totally_empty_dir(tmp_path):
    # Not even a git repo -- every git subprocess call fails to run
    # meaningfully; must degrade to issue strings, never an exception.
    empty = tmp_path / "not_a_repo"
    empty.mkdir()
    result = wiring_check.check_wiring(empty)
    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["issues"]


# ---------------------------------------------------------------------
# CLI form
# ---------------------------------------------------------------------

SCRIPT = Path(__file__).resolve().parent / "wiring_check.py"


def test_cli_exit_0_when_clean(repo, monkeypatch):
    _git(["config", "--local", "core.hooksPath", ".githooks"], repo)
    _add_githook(repo, "pre-commit", executable=True)
    _add_githook(repo, "commit-msg", executable=True)
    _write_settings(repo, [])
    monkeypatch.setattr(wiring_check, "repo_root", lambda: repo)
    exit_code = wiring_check.main(["--check"])
    assert exit_code == 0


def test_cli_exit_1_when_issues(repo, monkeypatch):
    monkeypatch.setattr(wiring_check, "repo_root", lambda: repo)
    exit_code = wiring_check.main(["--check"])
    assert exit_code == 1


def test_cli_subprocess_smoke_runs_against_real_repo():
    # Smoke: the script runs standalone against ITS OWN real host repo
    # (this toolkit) without crashing, exits 0 or 1 (never anything
    # else, never a traceback on stderr).
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode in (0, 1)
    assert "Traceback" not in result.stderr
