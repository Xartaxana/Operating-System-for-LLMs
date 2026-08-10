# -*- coding: utf-8 -*-
"""Tests for tools/permission_audit.py.

Ported from HQ 2026-07-20.

Covers: matches_allow (the * prefix semantics, a cd prefix breaking a
match), sandbox heuristics (multi-line, $(...), a for loop), the
broad-wildcard detector (refinement b, positive/negative), and the
transcript snapshot (refinement a -- the scan must not see bytes
appended AFTER the snapshot).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import hygiene_gate
import permission_audit as pa


# --- matches_allow: prefix semantics ---

def test_matches_allow_prefix_star():
    patterns = [("Bash", "git push *")]
    assert pa.matches_allow("Bash", "git push origin main", patterns)
    assert not pa.matches_allow("Bash", "git pull", patterns)


def test_matches_allow_exact_tool_only_no_pattern():
    # a bare tool name with no "(...)" -> pattern == "" -> allows any command for that tool
    patterns = [("WebSearch", "")]
    assert pa.matches_allow("WebSearch", "anything at all", patterns)


def test_matches_allow_cd_prefix_breaks_match():
    # the allowlist pattern starts with "python", but the call starts with
    # "cd dir && python" -- a cd prefix breaks the from-the-start match
    # (command hygiene point 3).
    patterns = [("Bash", "python metrics.py*")]
    assert not pa.matches_allow("Bash", "cd gateway && python metrics.py", patterns)
    assert pa.matches_allow("Bash", "python metrics.py --days 1", patterns)


def test_matches_allow_wrong_tool_no_match():
    patterns = [("PowerShell", "git add *")]
    assert not pa.matches_allow("Bash", "git add -A", patterns)


# --- sandbox_flags: "cannot be statically analyzed" heuristics ---

def test_sandbox_flags_multiline():
    flags = pa.sandbox_flags("echo one\necho two")
    assert any("multi-line" in f for f in flags)


def test_sandbox_flags_command_substitution():
    flags = pa.sandbox_flags('echo "$(date)"')
    assert any("substitution" in f for f in flags)


def test_sandbox_flags_for_loop():
    flags = pa.sandbox_flags("for f in *.txt; do cat $f; done")
    assert any("for...do" in f for f in flags)


def test_sandbox_flags_clean_command_no_flags():
    assert pa.sandbox_flags("git status") == []


# --- is_broad_wildcard / scan_broad_wildcards: refinement (b) ---

def test_is_broad_wildcard_bare_interpreter_positive():
    # a known finding: Bash(python *) in settings.local.json
    reason = pa.is_broad_wildcard("Bash", "python *")
    assert reason is not None
    assert "python" in reason


def test_is_broad_wildcard_code_flag_positive():
    reason = pa.is_broad_wildcard("Bash", "python -c *")
    assert reason is not None
    reason2 = pa.is_broad_wildcard("Bash", "bash -c *")
    assert reason2 is not None


def test_is_broad_wildcard_code_flag_with_open_quote_positive():
    # a real-world shape: "python -c ' *" -- -c with an unclosed opening
    # quote right before the asterisk, the same arbitrary code as a bare
    # "python -c *".
    reason = pa.is_broad_wildcard("Bash", "python -c ' *")
    assert reason is not None


def test_is_broad_wildcard_env_prefix_before_interpreter_positive():
    # "PYTHONUTF8=1 python -c ' *" -- the pattern's head is VAR=val, not
    # the interpreter name; the detector must skip the assignment prefix.
    reason = pa.is_broad_wildcard("Bash", "PYTHONUTF8=1 python -c ' *")
    assert reason is not None


def test_is_broad_wildcard_narrow_pattern_negative():
    # a specific script with a flag after the interpreter -- not bare arbitrary code
    assert pa.is_broad_wildcard("Bash", "python metrics.py *") is None
    assert pa.is_broad_wildcard("Bash", "git push *") is None


def test_is_broad_wildcard_module_flag_positive():
    # `python -m *` lets through an arbitrary MODULE -- the same class of
    # arbitrary execution as -c/-e; a SPECIFIC module (python -m pytest
    # ...) is not a finding.
    assert pa.is_broad_wildcard("Bash", "python -m *") is not None
    assert pa.is_broad_wildcard("Bash", "python -m pytest tools/ gateway/ -q") is None


def test_is_broad_wildcard_non_matching_tool_negative():
    assert pa.is_broad_wildcard("WebFetch", "python *") is None


def test_scan_broad_wildcards_reads_both_settings_files(tmp_path, monkeypatch):
    repo = tmp_path
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(git fetch *)"]}}), encoding="utf-8")
    (claude_dir / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(python *)", "Bash(git add *)"]}}),
        encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)
    found = pa.scan_broad_wildcards()
    assert len(found) == 1
    fname, tool, pat, reason = found[0]
    assert fname == "settings.local.json"
    assert tool == "Bash"
    assert pat == "python *"


# --- transcript snapshot: refinement (a) ---

def _write_tool_use(path, cmd, ts="2026-07-14T10:00:00Z"):
    line = {
        "timestamp": ts,
        "message": {"content": [
            {"type": "tool_use", "name": "Bash", "input": {"command": cmd}}
        ]},
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def test_iter_tool_calls_ignores_bytes_written_after_snapshot(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    projects.mkdir()
    transcript = projects / "session.jsonl"
    _write_tool_use(transcript, "echo before-snapshot")
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    snapshot = pa.snapshot_transcripts()
    assert len(snapshot) == 1
    assert snapshot[0][2] == transcript.stat().st_size  # size_at_snapshot is fixed

    # a live session keeps appending to the transcript AFTER the snapshot
    _write_tool_use(transcript, "echo after-snapshot")

    calls = list(pa.iter_tool_calls(None, snapshot=snapshot))
    cmds = [c[4] for c in calls]
    assert "echo before-snapshot" in " ".join(cmds)
    assert not any("after-snapshot" in c for c in cmds)


def test_iter_tool_calls_without_snapshot_sees_full_current_file(tmp_path, monkeypatch):
    # with no explicit snapshot (snapshot=None), iter_tool_calls takes a
    # fresh one itself -- so it sees everything written BEFORE the call.
    projects = tmp_path / "projects"
    projects.mkdir()
    transcript = projects / "session.jsonl"
    _write_tool_use(transcript, "echo one")
    _write_tool_use(transcript, "echo two")
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    calls = list(pa.iter_tool_calls(None))
    cmds = [c[4] for c in calls]
    assert "echo one" in cmds
    assert "echo two" in cmds


# --- collect_suspects: end-to-end assembly ---

def test_collect_suspects_flags_missing_allowlist_match(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    projects = tmp_path / "projects"
    projects.mkdir()
    transcript = projects / "session.jsonl"
    _write_tool_use(transcript, "some-random-tool --flag")
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    suspects, total = pa.collect_suspects(None)
    assert total == 1
    assert len(suspects) == 1
    assert "no allowlist match" in suspects[0][4]


# --- _default_project_key / PROJECT_KEY: generic derivation (this port's addition) ---


def test_default_project_key_replaces_colon_backslash_underscore():
    # Empirically verified against a live ~/.claude/projects listing:
    # colon, backslash, and underscore each become a dash.

    class _FakeResolved:
        def __str__(self):
            return r"D:\Some_Repo"

    class _FakePath:
        def resolve(self):
            return _FakeResolved()

    assert pa._default_project_key(_FakePath()) == "D--Some-Repo"


def test_default_project_key_is_deterministic_for_real_repo_path(tmp_path):
    repo = tmp_path / "a_b" / "c-d"
    repo.mkdir(parents=True)
    key1 = pa._default_project_key(repo)
    key2 = pa._default_project_key(repo)
    assert key1 == key2
    assert "\\" not in key1 and "/" not in key1 and ":" not in key1 and "_" not in key1


class _FakeResolved:
    def __init__(self, s):
        self._s = s

    def __str__(self):
        return self._s


class _FakePath:
    def __init__(self, s):
        self._s = s

    def resolve(self):
        return _FakeResolved(self._s)


def test_default_project_key_dot_and_space_boundaries_deterministic():
    # Slug-boundary check (queue item 1, toolkit-release-v040): the
    # replacement regex is [\\/:_] -> "-" -- it does NOT touch dots or
    # spaces. This is UNVERIFIED AGAINST REAL HARNESS NAMING (the
    # function's own docstring says so); do not treat the asserted value
    # below as "the correct slug" -- it only locks in this function's
    # CURRENT, deterministic output as a regression contract, so a future
    # change to the regex shows up as a diff instead of silently drifting.
    # If a real install's actual ~/.claude/projects/<slug> differs on a
    # dot/space path, the escape hatch is the CLAUDE_PROJECTS env
    # override (_resolve_claude_projects), not "fixing" this regex blind.
    dot_path = r"D:\Repo.With.Dots"
    key_a = pa._default_project_key(_FakePath(dot_path))
    key_b = pa._default_project_key(_FakePath(dot_path))
    assert key_a == key_b  # deterministic
    assert key_a == "D--Repo.With.Dots"  # current behavior: dots pass through

    space_path = r"D:\Repo With Spaces"
    key_c = pa._default_project_key(_FakePath(space_path))
    key_d = pa._default_project_key(_FakePath(space_path))
    assert key_c == key_d  # deterministic
    assert key_c == "D--Repo With Spaces"  # current behavior: spaces pass through


# --- _resolve_claude_projects / CLAUDE_PROJECTS env override (queue item 1) ---


def test_resolve_claude_projects_env_override_takes_full_path(tmp_path, monkeypatch):
    override_dir = tmp_path / "custom_projects_dir"
    monkeypatch.setenv("CLAUDE_PROJECTS", str(override_dir))
    resolved = pa._resolve_claude_projects(pa.REPO)
    assert resolved == override_dir


def test_resolve_claude_projects_no_env_falls_back_to_slug(monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECTS", raising=False)
    resolved = pa._resolve_claude_projects(pa.REPO)
    expected = Path.home() / ".claude" / "projects" / pa._default_project_key(pa.REPO)
    assert resolved == expected


def test_claude_projects_env_override_works_end_to_end(tmp_path, monkeypatch):
    # The override is a FULL path, taking effect before the transcripts
    # scan even runs -- wire it the way main() would (CLAUDE_PROJECTS
    # resolved once at import time; here we simulate that by setting the
    # module attribute directly, same pattern the rest of this file uses
    # to point CLAUDE_PROJECTS at a fixture directory) and confirm a
    # transcript placed there is actually read.
    override_dir = tmp_path / "custom_projects_dir"
    override_dir.mkdir()
    transcript = override_dir / "session.jsonl"
    _write_tool_use(transcript, "echo overridden-transcript")
    monkeypatch.setenv("CLAUDE_PROJECTS", str(override_dir))

    resolved = pa._resolve_claude_projects(pa.REPO)
    assert resolved == override_dir
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", resolved)

    calls = list(pa.iter_tool_calls(None))
    cmds = [c[4] for c in calls]
    assert "echo overridden-transcript" in " ".join(cmds)


# --- check_transcripts_present: warn-on-empty (queue item 1) ---


def test_check_transcripts_present_warns_when_dir_missing(tmp_path, capsys):
    missing = tmp_path / "does_not_exist"
    warned = pa.check_transcripts_present(missing)
    assert warned is True
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert str(missing) in err
    assert "CLAUDE_PROJECTS" in err


def test_check_transcripts_present_warns_when_dir_empty(tmp_path, capsys):
    empty = tmp_path / "empty_projects"
    empty.mkdir()
    warned = pa.check_transcripts_present(empty)
    assert warned is True
    err = capsys.readouterr().err
    assert "WARNING" in err


def test_check_transcripts_present_no_warn_when_populated(tmp_path, capsys):
    populated = tmp_path / "populated_projects"
    populated.mkdir()
    _write_tool_use(populated / "session.jsonl", "echo something")
    warned = pa.check_transcripts_present(populated)
    assert warned is False
    err = capsys.readouterr().err
    assert err == ""


# --- classify_hygiene -- one positive test per class ---------------------
# Classification is IMPORTED from tools/hygiene_gate.py (a single
# source of truth) -- these tests check that the import is wired up and
# the gate's own helpers are actually called, not that the gate's own
# logic is correct (already covered by tools/test_hygiene_gate.py).


def test_classify_hygiene_class_redirect_stderr():
    assert pa.classify_hygiene("python tools/foo.py 2>&1") == ["2>&1"]


def test_classify_hygiene_class_cd_set_location():
    assert pa.classify_hygiene("cd tools && python foo.py") == ["cd/Set-Location"]
    assert pa.classify_hygiene("Set-Location tools; python foo.py") == ["cd/Set-Location"]


def test_classify_hygiene_class_python_dash_c():
    assert pa.classify_hygiene('python -c "print(1)"') == ["python -c/heredoc"]


def test_classify_hygiene_class_journal_bypass():
    assert pa.classify_hygiene("echo '{}' >> logs/routing-log.jsonl") == [
        "journal write bypassing Edit/Write"
    ]


# --- known false positives inherited from hygiene_gate, must carry
# through the import correctly (must not trigger here either) ---------


def test_classify_hygiene_known_fp_git_statement_with_journal_path_in_args():
    cmd = ('git add logs/routing-log.jsonl && git commit -m "add journal file" '
           '&& git push origin main')
    assert "journal write bypassing Edit/Write" not in pa.classify_hygiene(cmd)


def test_classify_hygiene_known_fp_2_greater_1_inside_commit_message():
    cmd = 'git commit -m "ran tests 2>&1 output captured"'
    assert "2>&1" not in pa.classify_hygiene(cmd)


def test_classify_hygiene_known_fp_quoted_greater_reading_journal():
    cmd = 'grep -c ">" logs/routing-log.jsonl'
    assert pa.classify_hygiene(cmd) == []


# --- classify_hygiene edge behavior -- command not a string/None/empty --


def test_classify_hygiene_command_none():
    assert pa.classify_hygiene(None) == []


def test_classify_hygiene_command_not_a_string():
    assert pa.classify_hygiene(123) == []
    assert pa.classify_hygiene({"a": 1}) == []


def test_classify_hygiene_command_empty_string():
    assert pa.classify_hygiene("") == []


# --- adversarial battery -- size/encoding ---------------------------------


def test_classify_hygiene_100kb_command_no_crash_and_correct():
    huge = "echo " + ("x" * 100_000) + " 2>&1"
    result = pa.classify_hygiene(huge)
    assert result == ["2>&1"]


def test_classify_hygiene_cyrillic_and_replacement_char_no_crash():
    cmd = "echo привет мир 2>&1 �"
    assert pa.classify_hygiene(cmd) == ["2>&1"]


# --- collect_hygiene_class_stats: both bases (all scanned, not only
# suspects), double-counting when one command trips >1 class ----------


def test_collect_hygiene_class_stats_counts_all_scanned_not_only_suspects(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    # the allowlist allows everything -- the command is NOT a suspect,
    # but the class must still be counted (the count base is ALL
    # scanned calls).
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(*)"]}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    projects = tmp_path / "projects"
    projects.mkdir()
    transcript = projects / "session.jsonl"
    _write_tool_use(transcript, "python tools/foo.py 2>&1")
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    class_counts, class_suspect_counts, any_class_count = pa.collect_hygiene_class_stats(None)
    assert class_counts["2>&1"] == 1
    assert class_suspect_counts["2>&1"] == 0  # allow(*) -> not a suspect
    assert any_class_count == 1


def test_collect_hygiene_class_stats_double_count_one_command_multiple_classes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    projects = tmp_path / "projects"
    projects.mkdir()
    transcript = projects / "session.jsonl"
    _write_tool_use(transcript, 'cd tools && python -c "print(1)" 2>&1')
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    class_counts, class_suspect_counts, any_class_count = pa.collect_hygiene_class_stats(None)
    assert class_counts["2>&1"] == 1
    assert class_counts["cd/Set-Location"] == 1
    assert class_counts["python -c/heredoc"] == 1
    assert class_counts["journal write bypassing Edit/Write"] == 0
    # one command, but the sum of class hits == 3 != the command count (1)
    assert sum(class_counts.values()) == 3
    assert any_class_count == 1


def test_collect_hygiene_class_stats_empty_scan_returns_zero_dict(tmp_path, monkeypatch):
    projects = tmp_path / "empty_projects"
    projects.mkdir()
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)
    class_counts, class_suspect_counts, any_class_count = pa.collect_hygiene_class_stats(None)
    assert class_counts == {label: 0 for label in pa.HYGIENE_CLASS_LABELS}
    assert class_suspect_counts == {label: 0 for label in pa.HYGIENE_CLASS_LABELS}
    assert any_class_count == 0


# --- collect_audit_stats: a SINGLE pass -----------------------------------
# Before the fix, total/suspects (collect_suspects) and the class
# counts (collect_hygiene_class_stats) were collected by TWO
# independent walks of iter_tool_calls, each recomputing its own mtime
# cutoff -- "numbers drift" between passes. Pin: the single call to
# collect_audit_stats makes EXACTLY one call to iter_tool_calls, and
# total/class counts from that ONE call are mutually consistent (the
# sum of class hits >= the count of commands with at least one class,
# and both numbers <= total of that same pass).


def test_collect_audit_stats_single_iter_tool_calls_pass(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    projects = tmp_path / "projects"
    projects.mkdir()
    transcript = projects / "session.jsonl"
    now_ts = datetime.now(timezone.utc).isoformat()
    _write_tool_use(transcript, "python tools/foo.py 2>&1", ts=now_ts)
    _write_tool_use(transcript, "git status", ts=now_ts)
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    call_count = {"n": 0}
    original_iter = pa.iter_tool_calls

    def counting_iter(*args, **kwargs):
        call_count["n"] += 1
        return original_iter(*args, **kwargs)

    monkeypatch.setattr(pa, "iter_tool_calls", counting_iter)

    # minutes=120 (not None) -- the branch where iter_tool_calls
    # computes the mtime cutoff via time.time(); the pin must catch a
    # regression specifically on this branch (at minutes=None, no
    # cutoff is computed at all).
    suspects, total, class_counts, class_suspect_counts, any_class_count = (
        pa.collect_audit_stats(120))

    # EXACTLY one walk -- the very sample fixed once.
    assert call_count["n"] == 1
    assert total == 2
    assert any_class_count == 1
    assert class_counts["2>&1"] == 1
    assert sum(class_counts.values()) <= total
    assert any_class_count <= total


def test_collect_audit_stats_total_and_class_counts_come_from_same_snapshot(tmp_path, monkeypatch):
    # A regression form of the bug itself: main() before the fix made
    # two separate calls (collect_suspects + collect_hygiene_class_stats),
    # each calling iter_tool_calls afresh. Here we check main() now
    # calls iter_tool_calls exactly once for the whole --summary run.
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    projects = tmp_path / "projects"
    projects.mkdir()
    _write_tool_use(projects / "session.jsonl", "python tools/foo.py 2>&1")
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)

    call_count = {"n": 0}
    original_iter = pa.iter_tool_calls

    def counting_iter(*args, **kwargs):
        call_count["n"] += 1
        return original_iter(*args, **kwargs)

    monkeypatch.setattr(pa, "iter_tool_calls", counting_iter)

    pa.main(["--all", "--summary"])
    assert call_count["n"] == 1


# --- classify_hygiene() == hygiene_gate's own attribution, on a matrix --
# classify_hygiene() must copy not only hygiene_gate's regexes but its
# ASSEMBLY of individual checks too -- if hygiene_gate's internal
# assembly drifts and classify_hygiene isn't updated in lockstep, the
# divergence would be SILENT (renaming a helper would fail loudly,
# assembly drift would not). This test compares classify_hygiene()
# against a DIRECT attribution built from hygiene_gate._collect_signals
# (the same function _classify itself uses) on a matrix of commands:
# all 4 classes, 3 known FPs, compounds with several classes at once.


def _gate_attribution(cmd: str) -> set[str]:
    signals = hygiene_gate._collect_signals(cmd)
    labels = set()
    if signals["redirect"]:
        labels.add("2>&1")
    if signals["cd"]:
        labels.add("cd/Set-Location")
    if signals["pyc"]:
        labels.add("python -c/heredoc")
    if signals["journal"]:
        labels.add("journal write bypassing Edit/Write")
    return labels


_GATE_ATTRIBUTION_MATRIX = [
    "python tools/foo.py 2>&1",
    "cd tools && python foo.py",
    "Set-Location tools; python foo.py",
    'python -c "print(1)"',
    "echo '{}' >> logs/routing-log.jsonl",
    ('git add logs/routing-log.jsonl && git commit -m "add journal file" '
     '&& git push origin main'),
    'git commit -m "ran tests 2>&1 output captured"',
    'grep -c ">" logs/routing-log.jsonl',
    'cd tools && python -c "print(1)" 2>&1',
    'cd tools && echo x >> logs/routing-log.jsonl && python -c "1" 2>&1',
    f"cd {hygiene_gate._REPO_ROOT_NAME}\ngit status",
]


@pytest.mark.parametrize("cmd", _GATE_ATTRIBUTION_MATRIX)
def test_classify_hygiene_matches_gate_attribution(cmd):
    assert set(pa.classify_hygiene(cmd)) == _gate_attribution(cmd)


# --- main() --summary: the new hygiene-class block -- zeros are always
# printed, block position, header wording -----------------------------


def _setup_repo_and_projects(tmp_path, monkeypatch, allow=None):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": allow or []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)
    projects = tmp_path / "projects"
    projects.mkdir()
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", projects)
    return projects


def test_main_summary_prints_all_four_classes_including_zero(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    # no command triggers anything -- a zero must be LOAD-BEARING, not omitted.
    _write_tool_use(projects / "session.jsonl", "git status")
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    assert "By hygiene class (all scanned calls; in parens -- how many of them are suspects):" in out
    for label in pa.HYGIENE_CLASS_LABELS:
        assert label in out
    assert "journal write bypassing Edit/Write" in out  # a load-bearing zero, explicit


def test_main_summary_hygiene_block_position_between_reasons_and_recommendations(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "some-suspicious-tool --flag")
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    reasons_pos = out.index("By reason:")
    classes_pos = out.index("By hygiene class")
    recs_pos = out.index("Recommendations by category:")
    assert reasons_pos < classes_pos < recs_pos


def test_main_summary_double_count_line_printed_separately(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", 'cd tools && python -c "print(1)" 2>&1')
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    assert "commands with >=1 class: 1" in out


def test_main_summary_empty_transcripts_dir_prints_zero_block_no_crash(tmp_path, monkeypatch, capsys):
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", missing)
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    pa.main(["--all", "--summary"])
    out, err = capsys.readouterr()
    assert "WARNING" in err
    assert "By hygiene class" in out
    for label in pa.HYGIENE_CLASS_LABELS:
        assert label in out
    assert "commands with >=1 class: 0" in out


def test_main_non_summary_mode_has_no_hygiene_block(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "some-suspicious-tool --flag")
    pa.main(["--all"])
    out = capsys.readouterr().out
    assert "By hygiene class" not in out


# --- adversarial CLI battery ----------------------------------------------


def test_main_minutes_non_numeric_raises_clean_systemexit():
    with pytest.raises(SystemExit):
        pa.main(["--minutes", "not-a-number"])


def test_main_minutes_negative_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "git status")
    pa.main(["--minutes", "-5", "--summary"])
    out = capsys.readouterr().out
    assert "By hygiene class" in out


def test_main_minutes_zero_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "git status")
    pa.main(["--minutes", "0", "--summary"])
    out = capsys.readouterr().out
    assert "By hygiene class" in out


def test_main_all_together_with_minutes_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "python tools/foo.py 2>&1")
    pa.main(["--all", "--minutes", "30", "--summary"])
    out = capsys.readouterr().out
    assert "By hygiene class" in out

