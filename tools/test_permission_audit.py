# -*- coding: utf-8 -*-
"""Тесты tools/permission_audit.py (порт t-106 из D:\\AO3_tests, пилот принят).

Покрывает: matches_allow (префикс-семантика *, cd-префикс ломает совпадение),
sandbox-эвристики (многострочность, $(...), цикл for), broad-wildcard детектор
(доработка b пилота, позитив/негатив), и снапшот транскриптов (доработка a
пилота — скан не должен видеть байты, дописанные ПОСЛЕ снапшота).
"""
from __future__ import annotations

import json

import permission_audit as pa


# --- matches_allow: префикс-семантика ---

def test_matches_allow_prefix_star():
    patterns = [("Bash", "git push *")]
    assert pa.matches_allow("Bash", "git push origin main", patterns)
    assert not pa.matches_allow("Bash", "git pull", patterns)


def test_matches_allow_exact_tool_only_no_pattern():
    # голое имя тула без "(...)" -> pattern == "" -> разрешает любую команду тула
    patterns = [("WebSearch", "")]
    assert pa.matches_allow("WebSearch", "anything at all", patterns)


def test_matches_allow_cd_prefix_breaks_match():
    # allowlist-паттерн начинается с "python", а вызов начинается с "cd dir && python" —
    # cd-префикс ломает совпадение с начала строки (CLAUDE.md permission hygiene п.3).
    patterns = [("Bash", "python metrics.py*")]
    assert not pa.matches_allow("Bash", "cd gateway && python metrics.py", patterns)
    assert pa.matches_allow("Bash", "python metrics.py --days 1", patterns)


def test_matches_allow_wrong_tool_no_match():
    patterns = [("PowerShell", "git add *")]
    assert not pa.matches_allow("Bash", "git add -A", patterns)


# --- sandbox_flags: эвристики "cannot be statically analyzed" ---

def test_sandbox_flags_multiline():
    flags = pa.sandbox_flags("echo one\necho two")
    assert any("многострочная" in f for f in flags)


def test_sandbox_flags_command_substitution():
    flags = pa.sandbox_flags('echo "$(date)"')
    assert any("подстановка" in f for f in flags)


def test_sandbox_flags_for_loop():
    flags = pa.sandbox_flags("for f in *.txt; do cat $f; done")
    assert any("for...do" in f for f in flags)


def test_sandbox_flags_clean_command_no_flags():
    assert pa.sandbox_flags("git status") == []


# --- is_broad_wildcard / scan_broad_wildcards: доработка (b) пилота ---

def test_is_broad_wildcard_bare_interpreter_positive():
    # находка пилота: Bash(python *) в settings.local.json
    reason = pa.is_broad_wildcard("Bash", "python *")
    assert reason is not None
    assert "python" in reason


def test_is_broad_wildcard_code_flag_positive():
    reason = pa.is_broad_wildcard("Bash", "python -c *")
    assert reason is not None
    reason2 = pa.is_broad_wildcard("Bash", "bash -c *")
    assert reason2 is not None


def test_is_broad_wildcard_code_flag_with_open_quote_positive():
    # реальные записи settings.local.json этого репо: "python -c ' *" —
    # -c с незакрытой открывающей кавычкой сразу перед звёздочкой, тот же
    # произвольный код, что и голый "python -c *".
    reason = pa.is_broad_wildcard("Bash", "python -c ' *")
    assert reason is not None


def test_is_broad_wildcard_env_prefix_before_interpreter_positive():
    # "PYTHONUTF8=1 python -c ' *" -- голова паттерна это VAR=val, не
    # имя интерпретатора; детектор должен пропустить префикс присваивания.
    reason = pa.is_broad_wildcard("Bash", "PYTHONUTF8=1 python -c ' *")
    assert reason is not None


def test_is_broad_wildcard_narrow_pattern_negative():
    # конкретный скрипт с флагом после интерпретатора — не голый произвольный код
    assert pa.is_broad_wildcard("Bash", "python metrics.py *") is None
    assert pa.is_broad_wildcard("Bash", "git push *") is None


def test_is_broad_wildcard_module_flag_positive():
    # F2 ревью t-107: `python -m *` пропускает произвольный модуль —
    # тот же класс произвольного выполнения, что -c/-e; при этом
    # КОНКРЕТНЫЙ модуль (python -m pytest ...) — не находка.
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


# --- снапшот транскриптов: доработка (a) пилота ---

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
    assert snapshot[0][2] == transcript.stat().st_size  # size_at_snapshot зафиксирован

    # живая сессия дописывает транскрипт ПОСЛЕ снапшота
    _write_tool_use(transcript, "echo after-snapshot")

    calls = list(pa.iter_tool_calls(None, snapshot=snapshot))
    cmds = [c[4] for c in calls]
    assert "echo before-snapshot" in " ".join(cmds)
    assert not any("after-snapshot" in c for c in cmds)


def test_iter_tool_calls_without_snapshot_sees_full_current_file(tmp_path, monkeypatch):
    # без явного снапшота (snapshot=None) iter_tool_calls берёт свежий снапшот сам —
    # значит видит всё, что записано ДО вызова.
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


# --- collect_suspects: сквозная сборка ---

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
    assert "нет совпадения с allowlist" in suspects[0][4]
