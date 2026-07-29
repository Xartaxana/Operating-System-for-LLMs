"""Tests for tools/wiring_check.py -- the thin standalone CLI wrapping
tools/session_context.py's own WIRING-INTEGRITY channels
(git_hooks_channel, harness_channel, python_channel), plus the ONE new
piece of logic this file adds: skills_casing_channel(). See the
module's own docstring for the origin (coordinator respec, 2026-07-29,
following a builder-reported spec-reality divergence) and the incident
motive (Dog deployment, 2026-07-25/2026-07-29 synk).

к4-class coverage (respec point 4):
  - correct SKILL.md casing -> channel silent.
  - wrong casing -> ONE warning (mocked subprocess output AND a real
    isolated fixture repo via `git update-index --cacheinfo`, which
    inserts an arbitrary-cased path into the git INDEX without
    touching this filesystem's actual case-insensitive file layout --
    the live index is never touched, only a throwaway tmp_path repo).
  - git unavailable/erroring -> ONE "not verifiable" warning, no
    exception.
  - CLI: OK scenario -> exit 0 (against the REAL repo -- see
    `test_cli_real_repo_currently_ok`, empirically verified rather than
    assumed); warning scenario -> exit 1 (isolated fake repo with a
    deliberately mis-cased skill file in its index).

Run from the repo root: python -m pytest tools/test_wiring_check.py -q
"""
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wiring_check  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "wiring_check.py"
REAL_REPO = Path(__file__).resolve().parent.parent


def _fake_run_factory(returncode, stdout):
    def _fake_run(args, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")

    return _fake_run


def _git(repo, *args, **kwargs):
    return subprocess.run(
        ["git"] + list(args), cwd=repo, check=True, capture_output=True, text=True, **kwargs
    )


# ---------------------------------------------------------------------
# skills_casing_channel() -- mocked subprocess output
# ---------------------------------------------------------------------


def test_skills_casing_correct_case_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        wiring_check.subprocess,
        "run",
        _fake_run_factory(
            0, ".claude/skills/onboarding/SKILL.md\n.claude/skills/foo/SKILL.md\n"
        ),
    )
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert warnings == []
    assert ok_count == 2


def test_skills_casing_wrong_case_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(
        wiring_check.subprocess,
        "run",
        _fake_run_factory(0, ".claude/skills/onboarding/skill.md\n"),
    )
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert ok_count == 0
    assert len(warnings) == 1
    assert "skill.md" in warnings[0]
    assert "wrong case" in warnings[0]


def test_skills_casing_mixed_one_ok_one_wrong(tmp_path, monkeypatch):
    monkeypatch.setattr(
        wiring_check.subprocess,
        "run",
        _fake_run_factory(
            0,
            ".claude/skills/onboarding/SKILL.md\n.claude/skills/other/Skill.md\n",
        ),
    )
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert ok_count == 1
    assert len(warnings) == 1
    assert "Skill.md" in warnings[0]


def test_skills_casing_non_skill_files_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(
        wiring_check.subprocess,
        "run",
        _fake_run_factory(0, ".claude/skills/onboarding/README.md\n"),
    )
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert warnings == []
    assert ok_count == 0


def test_skills_casing_no_skills_no_warnings_zero_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(wiring_check.subprocess, "run", _fake_run_factory(0, ""))
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert warnings == []
    assert ok_count == 0


# ---------------------------------------------------------------------
# skills_casing_channel() -- git unavailable / erroring, never raises
# ---------------------------------------------------------------------


def test_skills_casing_git_raises_folds_to_one_warning(tmp_path, monkeypatch):
    def _raise_run(args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(wiring_check.subprocess, "run", _raise_run)
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert ok_count == 0
    assert len(warnings) == 1
    assert "not verifiable" in warnings[0]


def test_skills_casing_git_nonzero_exit_folds_to_one_warning(tmp_path, monkeypatch):
    monkeypatch.setattr(wiring_check.subprocess, "run", _fake_run_factory(128, ""))
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert ok_count == 0
    assert len(warnings) == 1
    assert "not verifiable" in warnings[0]


def test_skills_casing_git_timeout_folds_to_one_warning(tmp_path, monkeypatch):
    def _raise_timeout(args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args, timeout=5)

    monkeypatch.setattr(wiring_check.subprocess, "run", _raise_timeout)
    warnings, ok_count = wiring_check.skills_casing_channel(tmp_path)
    assert ok_count == 0
    assert len(warnings) == 1
    assert "not verifiable" in warnings[0]


# ---------------------------------------------------------------------
# skills_casing_channel() -- real isolated git repo (never the live
# repo's index)
# ---------------------------------------------------------------------


def test_skills_casing_real_repo_correct_case_silent(tmp_path):
    repo = tmp_path / "repo"
    skill_dir = repo / ".claude" / "skills" / "onboarding"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("x", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "a@b.c")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", ".claude/skills/onboarding/SKILL.md")
    warnings, ok_count = wiring_check.skills_casing_channel(repo)
    assert warnings == []
    assert ok_count == 1


def test_skills_casing_real_repo_wrong_case_in_index_warns(tmp_path):
    # Inserts a lowercase-cased path into the git INDEX via
    # `update-index --cacheinfo`, without needing an actual
    # differently-cased FILE on disk (this Windows filesystem cannot
    # hold both "skill.md" and "SKILL.md" side by side) -- the index is
    # a cache independent of on-disk casing, so this reproduces the
    # exact incident shape without any live-index risk (a fresh
    # tmp_path repo).
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "a@b.c")
    _git(repo, "config", "user.name", "t")
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repo,
        input="content",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        [
            "git", "update-index", "--add", "--cacheinfo",
            f"100644,{blob},.claude/skills/onboarding/skill.md",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    warnings, ok_count = wiring_check.skills_casing_channel(repo)
    assert ok_count == 0
    assert len(warnings) == 1
    assert "skill.md" in warnings[0]


def test_skills_casing_not_a_git_repo_folds_to_one_warning(tmp_path):
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    warnings, ok_count = wiring_check.skills_casing_channel(not_a_repo)
    assert ok_count == 0
    assert len(warnings) == 1
    assert "not verifiable" in warnings[0]


# ---------------------------------------------------------------------
# main() / CLI contract -- direct call, stdout/exit code
# ---------------------------------------------------------------------


def test_main_all_channels_clean_prints_ok_line_exit0(monkeypatch, capsys):
    monkeypatch.setattr(
        wiring_check, "_run_channels", lambda root: ([], [], 3, [], 2, "/usr/bin/python")
    )
    monkeypatch.setattr(wiring_check.session_context, "repo_root", lambda: Path("."))
    exit_code = wiring_check.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("WIRING: OK")
    assert "harness hooks: 3 files importable" in out
    assert "skills casing: 2 ok" in out


def test_main_warnings_present_prints_each_line_exit1(monkeypatch, capsys):
    monkeypatch.setattr(
        wiring_check,
        "_run_channels",
        lambda root: (["git broke"], ["harness broke"], 0, ["skills broke"], 0, "/usr/bin/python"),
    )
    monkeypatch.setattr(wiring_check.session_context, "repo_root", lambda: Path("."))
    exit_code = wiring_check.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert len(lines) == 3
    assert all(l.startswith("WIRING WARNING:") for l in lines)
    assert any("git broke" in l for l in lines)
    assert any("harness broke" in l for l in lines)
    assert any("skills broke" in l for l in lines)


# ---------------------------------------------------------------------
# F3 (критик t-339) -- AUTOFIX-факты (session_context._AUTOFIX_FACT_PREFIX)
# НЕ warnings: рендер через session_context._wiring_line_for, не
# учитываются в exit-коде.
# ---------------------------------------------------------------------


def test_main_autofix_fact_alone_prints_autofix_line_and_exit0(monkeypatch, capsys):
    autofix_fact = (
        wiring_check.session_context._AUTOFIX_FACT_PREFIX + "core.hooksPath set to .githooks"
    )
    monkeypatch.setattr(
        wiring_check,
        "_run_channels",
        lambda root: ([autofix_fact], [], 3, [], 2, "/usr/bin/python"),
    )
    monkeypatch.setattr(wiring_check.session_context, "repo_root", lambda: Path("."))
    exit_code = wiring_check.main()
    assert exit_code == 0
    out = capsys.readouterr().out
    lines = [l for l in out.splitlines() if l.strip()]
    assert lines[0] == f"WIRING {autofix_fact}"
    assert lines[1].startswith("WIRING: OK")


def test_main_autofix_fact_plus_real_warning_both_printed_exit1(monkeypatch, capsys):
    autofix_fact = (
        wiring_check.session_context._AUTOFIX_FACT_PREFIX + "core.hooksPath set to .githooks"
    )
    monkeypatch.setattr(
        wiring_check,
        "_run_channels",
        lambda root: (
            [autofix_fact, "hook file missing: .githooks/commit-msg"],
            [],
            3,
            [],
            2,
            "/usr/bin/python",
        ),
    )
    monkeypatch.setattr(wiring_check.session_context, "repo_root", lambda: Path("."))
    exit_code = wiring_check.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    assert f"WIRING {autofix_fact}" in out
    assert "WIRING WARNING: hook file missing: .githooks/commit-msg" in out


def test_cli_fresh_clone_hookspath_unset_autofixes_and_exits_ok(tmp_path):
    # Real end-to-end fixture (respec F3: "сценарий свежего клона: хуки
    # tracked, hooksPath снят -> строка AUTOFIX + exit 0"). Both
    # .githooks/pre-commit and commit-msg exist on disk AND are tracked
    # executable (100755) in the index; core.hooksPath is deliberately
    # left UNSET (a fresh `git clone` never sets local config) --
    # session_context's inherited VG-1 self-heal must fire for real.
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / ".githooks").mkdir(parents=True)
    (repo / ".claude").mkdir(parents=True)
    (repo / "tools" / "wiring_check.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    session_context_src = Path(__file__).resolve().parent / "session_context.py"
    (repo / "tools" / "session_context.py").write_text(
        session_context_src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (repo / ".githooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / ".githooks" / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "a@b.c")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    _git(repo, "update-index", "--chmod=+x", ".githooks/pre-commit")
    _git(repo, "update-index", "--chmod=+x", ".githooks/commit-msg")

    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "wiring_check.py")],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "WIRING AUTOFIX:" in result.stdout
    assert "WIRING: OK" in result.stdout
    # Self-heal actually wrote local git config, isolated to this fake repo.
    check = subprocess.run(
        ["git", "config", "--local", "core.hooksPath"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    assert check.stdout.strip() == ".githooks"


def test_main_python_not_found_adds_warning_exit1(monkeypatch, capsys):
    monkeypatch.setattr(
        wiring_check, "_run_channels", lambda root: ([], [], 1, [], 0, None)
    )
    monkeypatch.setattr(wiring_check.session_context, "repo_root", lambda: Path("."))
    exit_code = wiring_check.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "python not found on PATH" in out


def test_main_internal_crash_prints_one_warning_exit1_fail_closed(monkeypatch, capsys):
    def _boom(root):
        raise RuntimeError("boom")

    monkeypatch.setattr(wiring_check, "_run_channels", _boom)
    monkeypatch.setattr(wiring_check.session_context, "repo_root", lambda: Path("."))
    exit_code = wiring_check.main()
    assert exit_code == 1
    out = capsys.readouterr().out
    assert "WIRING WARNING: check failed internally" in out
    assert "RuntimeError" in out


# ---------------------------------------------------------------------
# CLI, real subprocess: OK scenario against the REAL repo (empirical,
# not assumed -- read-only, no side effects on any of the checks) and
# a warning scenario against an isolated fake repo.
# ---------------------------------------------------------------------


def test_cli_real_repo_currently_ok(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=REAL_REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip().startswith("WIRING: OK")


def test_cli_fake_repo_wrong_skill_casing_exit1(tmp_path):
    # Isolated fake repo (own .git, tools/, .claude/, .githooks/) so
    # this never touches the real repo's index -- same isolation
    # pattern as tools/test_enforcement_probe.py's _init_fake_repo.
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / ".githooks").mkdir(parents=True)
    (repo / ".claude").mkdir(parents=True)
    (repo / "tools" / "wiring_check.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    session_context_src = Path(__file__).resolve().parent / "session_context.py"
    (repo / "tools" / "session_context.py").write_text(
        session_context_src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (repo / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    (repo / ".githooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (repo / ".githooks" / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "a@b.c")
    _git(repo, "config", "user.name", "t")
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=repo,
        input="content",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    subprocess.run(
        [
            "git", "update-index", "--add", "--cacheinfo",
            f"100644,{blob},.claude/skills/onboarding/skill.md",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        [sys.executable, str(repo / "tools" / "wiring_check.py")],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "WIRING WARNING" in result.stdout
    assert "skill.md" in result.stdout
