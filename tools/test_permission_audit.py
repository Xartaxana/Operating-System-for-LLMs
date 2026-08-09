# -*- coding: utf-8 -*-
"""Тесты tools/permission_audit.py (порт t-106 из D:\\AO3_tests, пилот принят).

Покрывает: matches_allow (префикс-семантика *, cd-префикс ломает совпадение),
sandbox-эвристики (многострочность, $(...), цикл for), broad-wildcard детектор
(доработка b пилота, позитив/негатив), и снапшот транскриптов (доработка a
пилота — скан не должен видеть байты, дописанные ПОСЛЕ снапшота).

П6 (разбивка по классам гигиены, замер, см. докстринг tools/permission_audit.py):
classify_hygiene/collect_hygiene_class_stats -- по одному позитивному тесту на
класс, известные ложноположительные случаи, унаследованные от hygiene_gate
(git-statement, 2>&1 внутри commit-сообщения, кавычённый `>`), краевые
None/не-строка/пустая, D3 (несущий ноль), D5 (двойной счёт), новый блок
`--summary` (позиция, заголовок, пустой снапшот), адверсариальная батарея CLI.

Пересдача (t-364 attempt 2, вердикт критика): F9 -- collect_audit_stats()
пин-тест "один проход" (iter_tool_calls зовётся РОВНО один раз на общий
вызов, total/классовые счёты согласованы); F10 -- равенство classify_hygiene()
и прямой атрибуции hygiene_gate (_collect_warn_classes + _is_journal_bypass)
на матрице команд.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import permission_audit as pa
import hygiene_gate


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


# --- _resolve_claude_projects / CLAUDE_PROJECTS env override (очередь п.1) ---


def test_resolve_claude_projects_env_override_takes_full_path(tmp_path, monkeypatch):
    override_dir = tmp_path / "custom_projects_dir"
    monkeypatch.setenv("CLAUDE_PROJECTS", str(override_dir))
    resolved = pa._resolve_claude_projects()
    assert resolved == override_dir


def test_resolve_claude_projects_no_env_falls_back_to_hardcoded_key(monkeypatch):
    monkeypatch.delenv("CLAUDE_PROJECTS", raising=False)
    resolved = pa._resolve_claude_projects()
    expected = Path.home() / ".claude" / "projects" / pa.PROJECT_KEY
    assert resolved == expected


def test_claude_projects_env_override_works_end_to_end(tmp_path, monkeypatch):
    # Оверрайд — полный путь, вступающий в силу до самого скана
    # транскриптов; тот же паттерн, что и остальные тесты этого файла
    # используют для указания CLAUDE_PROJECTS на фикстурный каталог —
    # но здесь путь получен через env-переменную, а не напрямую.
    override_dir = tmp_path / "custom_projects_dir"
    override_dir.mkdir()
    transcript = override_dir / "session.jsonl"
    _write_tool_use(transcript, "echo overridden-transcript")
    monkeypatch.setenv("CLAUDE_PROJECTS", str(override_dir))

    resolved = pa._resolve_claude_projects()
    assert resolved == override_dir
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", resolved)

    calls = list(pa.iter_tool_calls(None))
    cmds = [c[4] for c in calls]
    assert "echo overridden-transcript" in " ".join(cmds)


# --- check_transcripts_present: предупреждение при пустом каталоге (очередь п.1) ---


def test_check_transcripts_present_warns_when_dir_missing(tmp_path, capsys):
    missing = tmp_path / "does_not_exist"
    warned = pa.check_transcripts_present(missing)
    assert warned is True
    err = capsys.readouterr().err
    assert "ВНИМАНИЕ" in err
    assert str(missing) in err
    assert "CLAUDE_PROJECTS" in err


def test_check_transcripts_present_warns_when_dir_empty(tmp_path, capsys):
    empty = tmp_path / "empty_projects"
    empty.mkdir()
    warned = pa.check_transcripts_present(empty)
    assert warned is True
    err = capsys.readouterr().err
    assert "ВНИМАНИЕ" in err


def test_check_transcripts_present_no_warn_when_populated(tmp_path, capsys):
    populated = tmp_path / "populated_projects"
    populated.mkdir()
    _write_tool_use(populated / "session.jsonl", "echo something")
    warned = pa.check_transcripts_present(populated)
    assert warned is False
    err = capsys.readouterr().err
    assert err == ""


# --- П6: classify_hygiene -- по одному позитивному тесту на класс -------
# Классификация ИМПОРТИРУЕТСЯ из tools/hygiene_gate.py (D-0043, единственный
# источник) -- эти тесты проверяют, что импорт подключён и хелперы гейта
# реально вызываются, не что сама логика гейта верна (это уже покрыто
# tools/test_hygiene_gate.py).

def test_classify_hygiene_class_redirect_stderr():
    assert pa.classify_hygiene("python tools/foo.py 2>&1") == ["2>&1"]


def test_classify_hygiene_class_cd_set_location():
    assert pa.classify_hygiene("cd tools && python foo.py") == ["cd/Set-Location"]
    assert pa.classify_hygiene("Set-Location tools; python foo.py") == ["cd/Set-Location"]


def test_classify_hygiene_class_python_dash_c():
    assert pa.classify_hygiene('python -c "print(1)"') == ["python -c/heredoc"]


def test_classify_hygiene_class_journal_bypass():
    assert pa.classify_hygiene("echo '{}' >> logs/routing-log.jsonl") == ["журнал мимо Edit/Write"]


# --- П6: известные ложноположительные случаи, унаследованные от hygiene_gate,
# должны корректно переноситься через импорт (не срабатывать здесь тоже) ---

def test_classify_hygiene_known_fp_git_statement_with_journal_path_in_args():
    # git add/commit/push статемент -- git не пишет в журнал, путь журнала в
    # аргументах add не должен триггерить класс (г) (GIT_STATEMENT_RE маскирует).
    cmd = ('git add logs/routing-log.jsonl && git commit -m "add journal file" '
           '&& git push origin main')
    assert "журнал мимо Edit/Write" not in pa.classify_hygiene(cmd)


def test_classify_hygiene_known_fp_2_greater_1_inside_commit_message():
    # " 2>&1" внутри ТЕКСТА -m commit-сообщения -- не реальный shell-редирект
    # stderr, _strip_commit_message_arg_only должен его вырезать.
    cmd = 'git commit -m "ran tests 2>&1 output captured"'
    assert "2>&1" not in pa.classify_hygiene(cmd)


def test_classify_hygiene_known_fp_quoted_greater_reading_journal():
    # `>` внутри кавычек (аргумент-строка grep, не редирект) -- read-only,
    # не должен триггерить класс (г) (_mask_quoted_segments, F-53-2).
    cmd = 'grep -c ">" logs/routing-log.jsonl'
    assert pa.classify_hygiene(cmd) == []


# --- П6: краевое поведение classify_hygiene -- command не строка/None/пустая -

def test_classify_hygiene_command_none():
    assert pa.classify_hygiene(None) == []


def test_classify_hygiene_command_not_a_string():
    assert pa.classify_hygiene(123) == []
    assert pa.classify_hygiene({"a": 1}) == []


def test_classify_hygiene_command_empty_string():
    assert pa.classify_hygiene("") == []


# --- П6: адверсариальная батарея -- размер/кодировка --------------------

def test_classify_hygiene_100kb_command_no_crash_and_correct():
    huge = "echo " + ("x" * 100_000) + " 2>&1"
    result = pa.classify_hygiene(huge)
    assert result == ["2>&1"]


def test_classify_hygiene_cyrillic_and_replacement_char_no_crash():
    cmd = "echo привет мир 2>&1 �"
    assert pa.classify_hygiene(cmd) == ["2>&1"]


# --- П6: collect_hygiene_class_stats -- D2 (обе базы), D5 (двойной счёт) ---

def test_collect_hygiene_class_stats_counts_all_scanned_not_only_suspects(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    # allowlist разрешает всё -- команда НЕ suspect, но класс всё равно
    # должен засчитаться (D2: база счёта -- все просканированные вызовы).
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
    assert class_suspect_counts["2>&1"] == 0  # allow(*) -> не suspect
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
    assert class_counts["журнал мимо Edit/Write"] == 0
    # D5: одна команда, но сумма попаданий по классам == 3 != число команд (1)
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


# --- F9 (пересдача t-364 attempt 2): collect_audit_stats -- ОДИН проход -----
# ДО фикса total/suspects (collect_suspects) и классовые счёты
# (collect_hygiene_class_stats) собирались ДВУМЯ независимыми обходами
# iter_tool_calls, каждый со СВОИМ пересчётом mtime-отсечки -- "числа
# плывут" между проходами. Пин-тест: единственный вызов collect_audit_stats
# делает РОВНО один вызов iter_tool_calls, и total/классовые счёты из этого
# ОДНОГО вызова взаимно согласованы (сумма попаданий по классам >= числа
# команд с хотя бы одним классом, и обе цифры <= total одного и того же
# прохода).

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

    # minutes=120 (не None) -- именно ветка, где iter_tool_calls вычисляет
    # mtime-отсечку через time.time(); пин-тест должен ловить регресс
    # именно на этой ветке (при minutes=None cutoff вообще не считается).
    suspects, total, class_counts, class_suspect_counts, any_class_count = (
        pa.collect_audit_stats(120))

    # РОВНО один обход -- та самая выборка, зафиксированная один раз.
    assert call_count["n"] == 1
    assert total == 2
    assert any_class_count == 1
    assert class_counts["2>&1"] == 1
    # сумма попаданий по классам согласована с числом просканированных
    # вызовов ИЗ ТОГО ЖЕ ПРОХОДА (не может её превышать -- на этой выборке
    # только одна команда несёт один класс).
    assert sum(class_counts.values()) <= total
    assert any_class_count <= total


def test_collect_audit_stats_total_and_class_counts_come_from_same_snapshot(tmp_path, monkeypatch):
    # Регресс-форма самого F9-бага: main() ДО фикса делал два отдельных
    # вызова (collect_suspects + collect_hygiene_class_stats), каждый заново
    # звал iter_tool_calls (и заново пересчитывал mtime-отсечку). Здесь
    # проверяем, что main() теперь зовёт iter_tool_calls ровно один раз за
    # весь прогон --summary (а не дважды, как было бы при раздельных вызовах).
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


# --- F10 (пересдача t-364 attempt 2): equality classify_hygiene == hygiene_gate
# Классификация classify_hygiene() копирует не только регексы hygiene_gate, но
# и СБОРКУ отдельных проверок (порядок применения _strip_commit_message_arg_only
# для класса 2>&1 и т.п.) -- если сборка внутри hygiene_gate._collect_warn_classes
# сменится, а classify_hygiene не будет обновлён синхронно, расхождение будет
# МОЛЧАЛИВЫМ (переименование хелпера упало бы громко, дрейф сборки -- нет).
# Тест сравнивает classify_hygiene() с ПРЯМОЙ атрибуцией самого hygiene_gate
# (_collect_warn_classes для классов а/б/в + _is_journal_bypass для класса г)
# на матрице команд: все 4 класса, 3 известных FP, компаунды с несколькими
# классами сразу.

_GATE_MSG_TO_LABEL = {
    hygiene_gate.MSG_CD_PREFIX: "cd/Set-Location",
    hygiene_gate.MSG_REDIRECT_STDERR: "2>&1",
    hygiene_gate.MSG_PYTHON_DASH_C: "python -c/heredoc",
}


def _gate_attribution(cmd: str) -> set[str]:
    """Атрибуция классов НАПРЯМУЮ от hygiene_gate (не через classify_hygiene) --
    эталон для сравнения в тесте равенства."""
    labels = {_GATE_MSG_TO_LABEL[msg] for msg in hygiene_gate._collect_warn_classes(cmd)}
    if hygiene_gate._is_journal_bypass(cmd):
        labels.add("журнал мимо Edit/Write")
    return labels


_GATE_ATTRIBUTION_MATRIX = [
    "python tools/foo.py 2>&1",                                    # класс б
    "cd tools && python foo.py",                                   # класс а
    "Set-Location tools; python foo.py",                           # класс а (PowerShell-форма)
    'python -c "print(1)"',                                        # класс в
    "echo '{}' >> logs/routing-log.jsonl",                         # класс г
    ('git add logs/routing-log.jsonl && git commit -m "add journal file" '
     '&& git push origin main'),                                   # известный FP -- git-statement
    'git commit -m "ran tests 2>&1 output captured"',               # известный FP -- 2>&1 в -m
    'grep -c ">" logs/routing-log.jsonl',                           # известный FP -- кавычённый >
    'cd tools && python -c "print(1)" 2>&1',                        # компаунд: а+б+в
    'cd tools && echo x >> logs/routing-log.jsonl && python -c "1" 2>&1',  # компаунд: а+б+в+г
]


@pytest.mark.parametrize("cmd", _GATE_ATTRIBUTION_MATRIX)
def test_classify_hygiene_matches_gate_attribution(cmd):
    assert set(pa.classify_hygiene(cmd)) == _gate_attribution(cmd)


# --- П6: main() --summary -- новый блок, D3 (нули всегда), позиция, заголовок ---

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
    # ни одна команда ничего не триггерит -- ноль должен быть НЕСУЩИМ, не опущенным.
    _write_tool_use(projects / "session.jsonl", "git status")
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    assert "По классам гигиены (все просканированные вызовы; в скобках — сколько из них suspects):" in out
    for label in pa.HYGIENE_CLASS_LABELS:
        assert label in out
    assert "журнал мимо Edit/Write" in out  # несущий ноль разбора №6, явно


def test_main_summary_hygiene_block_position_between_reasons_and_recommendations(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "some-suspicious-tool --flag")
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    reasons_pos = out.index("По причинам:")
    classes_pos = out.index("По классам гигиены")
    recs_pos = out.index("Рекомендации по категориям:")
    assert reasons_pos < classes_pos < recs_pos


def test_main_summary_double_count_line_printed_separately(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", 'cd tools && python -c "print(1)" 2>&1')
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    assert "команд с ≥1 классом: 1" in out


def test_main_summary_empty_transcripts_dir_prints_zero_block_no_crash(tmp_path, monkeypatch, capsys):
    # D6: пустой снапшот транскриптов -> блок печатается с нулями, скрипт не падает.
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(pa, "CLAUDE_PROJECTS", missing)
    repo = tmp_path / "repo"
    (repo / ".claude").mkdir(parents=True)
    (repo / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"allow": []}}), encoding="utf-8")
    monkeypatch.setattr(pa, "REPO", repo)

    pa.main(["--all", "--summary"])
    out, err = capsys.readouterr()
    assert "ВНИМАНИЕ" in err
    assert "По классам гигиены" in out
    for label in pa.HYGIENE_CLASS_LABELS:
        assert label in out
    assert "команд с ≥1 классом: 0" in out


def test_main_non_summary_mode_has_no_hygiene_block(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "some-suspicious-tool --flag")
    pa.main(["--all"])
    out = capsys.readouterr().out
    assert "По классам гигиены" not in out


# --- П6: адверсариальная батарея CLI -------------------------------------

def test_main_minutes_non_numeric_raises_clean_systemexit(capsys):
    with pytest.raises(SystemExit):
        pa.main(["--minutes", "not-a-number"])


def test_main_minutes_negative_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "git status")
    pa.main(["--minutes", "-5", "--summary"])
    out = capsys.readouterr().out
    assert "По классам гигиены" in out


def test_main_minutes_zero_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "git status")
    pa.main(["--minutes", "0", "--summary"])
    out = capsys.readouterr().out
    assert "По классам гигиены" in out


def test_main_all_together_with_minutes_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session.jsonl", "python tools/foo.py 2>&1")
    pa.main(["--all", "--minutes", "30", "--summary"])
    out = capsys.readouterr().out
    assert "команд с ≥1 классом: 1" in out


def test_main_session_substring_not_found_anywhere_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session-abc.jsonl", "git status")
    pa.main(["--all", "--summary", "--session", "zzz-nowhere-zzz"])
    out = capsys.readouterr().out
    assert "команд с ≥1 классом: 0" in out


def test_main_session_special_path_chars_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    _write_tool_use(projects / "session-abc.jsonl", "git status")
    pa.main(["--all", "--summary", "--session", "../../etc; drop table"])
    out = capsys.readouterr().out
    assert "команд с ≥1 классом: 0" in out


def test_transcript_broken_json_line_skipped_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    transcript = projects / "session.jsonl"
    with open(transcript, "a", encoding="utf-8") as f:
        f.write('{"tool_use": broken json not parseable\n')
    _write_tool_use(transcript, "python tools/foo.py 2>&1")
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    assert "2>&1" in out
    assert "команд с ≥1 классом: 1" in out


def test_transcript_tool_use_without_input_field_no_crash(tmp_path, monkeypatch, capsys):
    projects = _setup_repo_and_projects(tmp_path, monkeypatch)
    transcript = projects / "session.jsonl"
    line = {
        "timestamp": "2026-07-14T10:00:00Z",
        "message": {"content": [{"type": "tool_use", "name": "Bash"}]},
    }
    with open(transcript, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    pa.main(["--all", "--summary"])
    out = capsys.readouterr().out
    assert "команд с ≥1 классом: 0" in out


def test_read_snapshot_lines_truncated_mid_line_no_crash(tmp_path):
    p = tmp_path / "t.jsonl"
    full_line = json.dumps({"a": 1}) + "\n"
    partial = '{"b": 2, "trunca'
    p.write_bytes((full_line + partial).encode("utf-8"))
    size = len(full_line.encode("utf-8")) + 5  # обрезает вторую строку посередине
    lines = pa._read_snapshot_lines(p, size)
    assert lines == [full_line.strip()]
