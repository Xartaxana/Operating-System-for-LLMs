"""Тесты tools/mechanism_gate.py — гейт осевого блока правила 10(б), D-0055."""
from __future__ import annotations

import mechanism_gate as mg

MAP_SAMPLE = """# Sibling Map
## Ось 1 — Деплои
...
## Ось 2 — Контуры
...
## Ось 6 — Внутренние оси
...
## Проверка самой карты (D-0048)
"""


def test_parse_axes_follows_the_map_not_a_constant():
    # D-0048/D-0055: число и номера осей приходят из карты при каждом
    # запуске; разрыв нумерации (2 -> 6) не ломает парсер.
    assert mg.parse_axes(MAP_SAMPLE) == [1, 2, 6]
    assert mg.parse_axes("# пусто\n") == []


def test_mechanism_paths_filters_prefixes_with_boundary():
    staged = ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
              ".claude/agents/scout.md", "gateway/metrics.py",
              "docs/RELATED_WORK.md", "logs/routing-log.jsonl"]
    assert mg.mechanism_paths(staged) == [
        "CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        ".claude/agents/scout.md"]
    # F-D (ревью critic): граница префикса — файловые префиксы матчатся точно.
    assert mg.mechanism_paths(["CLAUDE.md.bak", "DECISIONS.md.orig",
                               "gateway/metrics.py"]) == []


def test_mechanism_paths_d0065_homes_and_self_protection():
    # D-0065 (F-25): дома механизмов + самозащита цепочки в неводе.
    extra = ["ARCHITECTURE.md", "ARCHITECTURE_BOOT.md", "BOOT.md",
             "gateway/PI_HARNESS.md",
             "tools/mechanism_gate.py", ".githooks/commit-msg"]
    assert mg.mechanism_paths(extra) == extra
    # Узость сознательна (D-0055): прочие tools/ и gateway/ вне невода.
    assert mg.mechanism_paths(["tools/usage_report.py",
                               "tools/test_mechanism_gate.py",
                               "gateway/config.yaml",
                               "ARCHITECTURE.md.bak"]) == []


def test_find_missing_reports_absent_axes_case_insensitive():
    text = "ось 1: покрыта — CLAUDE.md обоих деплоев\nОсь 2: н-п (денег не касается)\n"
    assert mg.find_missing(text, [1, 2, 6]) == [6]
    assert mg.find_missing(text + "ось 6: в очередь (AO3 next touch)\n", [1, 2, 6]) == []
    # Граница цифры: «ось 15:» не закрывает ось 1.
    assert mg.find_missing("ось 15: покрыта\n", [1]) == [1]


def test_prose_answer_is_not_an_answer():
    # F-19: recall-проза «оси покрыты» не проходит перечислительный формат.
    assert mg.find_missing("все оси покрыты, проверено", [1, 2]) == [1, 2]


def test_decide_skip_only_from_commit_message():
    # F-A (блокер из ревью critic): строка отказа, процитированная в
    # ДИФФЕ (текст решения), НЕ обходит гейт; действует только сообщение.
    code, reason = mg.decide(
        msg="feat: механизм X",
        block_extra="+ ... легальна строкой «оси: не-механизм (<причина>)» ...",
        staged=["CLAUDE.md"], map_text="## Ось 1 — Деплои\n")
    assert code == 1 and "1" in reason
    code, _ = mg.decide(
        msg="docs: правка опечатки\n\nоси: не-механизм (опечатка в правиле 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 — Деплои\n")
    assert code == 0


def test_decide_block_counted_from_message_and_decisions_diff_only():
    # F-B (ревью critic): посторонний staged-контент не закрывает оси —
    # decide получает дифф ТОЛЬКО DECISIONS_FULL, main так и вызывает.
    code, _ = mg.decide(
        msg="feat: механизм X\n\nось 1: покрыта — оба деплоя",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0
    code, _ = mg.decide(
        msg="feat: механизм X",
        block_extra="+ось 1: покрыта — оба деплоя (текст решения)",
        staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0


def test_decide_merge_and_non_mechanism_commits_pass():
    # F-C (ревью critic): merge не блокируется — слитые коммиты уже
    # проходили гейт поодиночке.
    code, _ = mg.decide(msg="Merge branch 'x'", block_extra="",
                        staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
                        merging=True)
    assert code == 0
    code, _ = mg.decide(msg="chore: телеметрия", block_extra="",
                        staged=["gateway/metrics.py", "logs/routing-log.jsonl"],
                        map_text="## Ось 1 —\n")
    assert code == 0


def test_decide_fails_closed_without_map_or_axes():
    code, reason = mg.decide(msg="feat: X", block_extra="",
                             staged=["CLAUDE.md"], map_text=None)
    assert code == 1 and "fail-closed" in reason
    code, reason = mg.decide(msg="feat: X", block_extra="",
                             staged=["CLAUDE.md"], map_text="# карта без осей\n")
    assert code == 1 and "fail-closed" in reason


def test_explicit_skip_line_matches():
    assert mg.SKIP_RE.search("оси: не-механизм (правка опечатки в CLAUDE.md)")
    assert mg.SKIP_RE.search("Оси: не-механизм (архивная перестановка, D-0038)")
    assert not mg.SKIP_RE.search("оси покрыты не-механизмом")
