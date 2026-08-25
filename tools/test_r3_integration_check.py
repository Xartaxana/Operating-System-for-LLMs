"""Юнит-тесты tools/r3_integration_check.py -- ТОЛЬКО на фикстурных
строках (numstat-вывод git и строки routing-log.jsonl), без реального
git-репозитория и без сетевых/файловых side-effect'ов (спека: "святое
-- скрипт только ЧИТАЕТ git и журнал"; тесты этой обязанности не
проверяют subprocess, только чистые функции разбора/поиска/классификации).

Покрывает DoD спеки (docs/tasks/2026-08-25_kopilka-wave-spec.md,
раздел "БИЛДЕР SE"): пустое окно, коммит без numstat-пар, журнал без
критик-событий, битые JSON-строки журнала (пропуск), плюс границы
порога >100 строк (100 -- малый, 101 -- крупный) и границы окна ts
(включительно с обеих сторон).

Плюс Ф2-фикс (вердикт критика волны, продолжение t-613): анти-след
"critic: skipped" НЕ считается критик-следом (живая фикстура t-593),
валидная S5-форма "critic:t-NNN" считается, смешанная строка --
валидный токен перевешивает анти-след, печатаемый фрагмент notes
корректно обрезается на границах строки и санитайзит переводы строк."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import r3_integration_check as r3  # noqa: E402


COMMIT = r3.COMMIT_MARKER
SEP = "\x1f"


def _header(commit_hash: str, ts: str) -> str:
    return f"{COMMIT}{commit_hash}{SEP}{ts}"


# ---------------------------------------------------------------------
# parse_git_log_numstat
# ---------------------------------------------------------------------


def test_parse_empty_window_returns_empty_list():
    assert r3.parse_git_log_numstat("") == []


def test_parse_single_commit_sums_added_and_deleted():
    raw = "\n".join(
        [
            _header("aaa111", "2026-08-25T10:00:00"),
            "10\t5\ttools/x.py",
            "3\t2\ttools/y.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert len(commits) == 1
    assert commits[0]["hash"] == "aaa111"
    assert commits[0]["ts"] == "2026-08-25T10:00:00"
    assert commits[0]["lines_changed"] == 20  # 10+5+3+2


def test_parse_commit_without_numstat_pairs_is_zero_lines():
    """Край DoD: merge-коммит (или пустой коммит) -- заголовок есть,
    numstat-строк нет вовсе. Запись создаётся, lines_changed=0."""
    raw = "\n".join(
        [
            _header("mmm000", "2026-08-25T09:00:00"),
            "",
            _header("bbb222", "2026-08-25T11:00:00"),
            "1\t1\ttools/z.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert len(commits) == 2
    assert commits[0]["hash"] == "mmm000"
    assert commits[0]["lines_changed"] == 0
    assert commits[1]["lines_changed"] == 2


def test_parse_binary_file_numstat_contributes_zero():
    raw = "\n".join(
        [
            _header("ccc333", "2026-08-25T12:00:00"),
            "-\t-\tassets/image.png",
            "4\t1\ttools/w.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert commits[0]["lines_changed"] == 5  # бинарник вклад 0, только 4+1


def test_parse_multiple_commits_preserves_order():
    raw = "\n".join(
        [
            _header("first0", "2026-08-25T08:00:00"),
            "1\t1\ta.py",
            _header("second0", "2026-08-25T09:00:00"),
            "2\t2\tb.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert [c["hash"] for c in commits] == ["first0", "second0"]


def test_parse_garbage_before_first_header_ignored():
    raw = "\n".join(
        [
            "some stray line not matching numstat format",
            _header("ddd444", "2026-08-25T13:00:00"),
            "6\t0\tc.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert len(commits) == 1
    assert commits[0]["lines_changed"] == 6


# ---------------------------------------------------------------------
# classify_commits -- порог >100 (границы 100/101) и window_start.
# ---------------------------------------------------------------------


def test_classify_threshold_boundary_at_100_is_small():
    commits = [{"hash": "h1", "ts": "2026-08-25T10:00:00", "lines_changed": 100}]
    classified = r3.classify_commits(commits)
    assert classified["large"] == []
    assert len(classified["small"]) == 1


def test_classify_threshold_boundary_at_101_is_large():
    commits = [{"hash": "h1", "ts": "2026-08-25T10:00:00", "lines_changed": 101}]
    classified = r3.classify_commits(commits)
    assert len(classified["large"]) == 1
    assert classified["small"] == []


def test_classify_window_start_is_previous_commit_ts_any_size():
    """Соседний коммит для нижней границы окна -- ЛЮБОЙ коммит списка
    (не только крупный) -- дизайн-решение билдера, задокументировано в
    докстринге classify_commits."""
    commits = [
        {"hash": "small1", "ts": "2026-08-25T08:00:00", "lines_changed": 10},
        {"hash": "large1", "ts": "2026-08-25T09:00:00", "lines_changed": 200},
    ]
    classified = r3.classify_commits(commits)
    assert len(classified["large"]) == 1
    assert classified["large"][0]["window_start"] == "2026-08-25T08:00:00"
    assert classified["large"][0]["window_end"] == "2026-08-25T09:00:00"


def test_classify_first_commit_has_no_window_start():
    commits = [{"hash": "large1", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    classified = r3.classify_commits(commits)
    assert classified["large"][0]["window_start"] is None


# ---------------------------------------------------------------------
# find_critic_trail
# ---------------------------------------------------------------------


def _line(obj) -> str:
    import json

    return json.dumps(obj)


def test_find_critic_trail_empty_journal_no_critic_events():
    """Край DoD: журнал без критик-событий -- пустой результат, не
    ошибка."""
    lines = [_line({"ts": "2026-08-25T10:00:00", "event": "accepted", "agent": "builder"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_matches_delegated_critic():
    lines = [
        _line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"})
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_matches_accepted_basis_critic():
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "basis": "critic",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_matches_notes_substring_critic_colon():
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: ACCEPT, ноль находок",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_skipped_form_is_anti_trail_not_a_match():
    """Ф2-фикс (вердикт критика волны, продолжение t-613): "critic:
    skipped" -- запись об ОТСУТСТВИИ критика, не след. Живая фикстура
    t-593 (900-строчный коммит с ровно такой notes-строкой) до фикса
    печаталась как НАЙДЕН -- регресс на это."""
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: skipped -- концессия резерва (D-0058)",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_skipped_form_no_space_is_also_anti_trail():
    """Регистр и отсутствие пробела после ":" не должны обходить
    анти-след ("critic:skipped", "Critic: SKIPPED")."""
    lines = [
        _line({"ts": "2026-08-25T10:00:00", "event": "accepted", "agent": "builder", "notes": "critic:skipped"}),
        _line({"ts": "2026-08-25T10:00:01", "event": "accepted", "agent": "builder", "notes": "Critic: SKIPPED, reason"}),
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_s5_token_form_is_a_match():
    """Валидная S5-форма "critic:t-NNN" -- считается следом как
    раньше (Ф2 её не трогает)."""
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "закрыто ссылкой critic:t-593 на вердикт",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1
    assert result[0]["_notes_fragment"] is not None
    assert "critic:t-593" in result[0]["_notes_fragment"]


def test_find_critic_trail_mixed_skip_and_valid_token_is_a_match():
    """Смешанная строка -- анти-след ПЛЮС валидный токен дальше по
    тексту -- валидный токен перевешивает (Ф2, явное требование)."""
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: skipped на первом проходе, повторно closed critic:t-593",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1
    assert "critic:t-593" in result[0]["_notes_fragment"]


def test_find_critic_trail_notes_fragment_none_for_non_notes_match():
    """У совпадения через delegated/basis (не через notes) фрагмент
    должен быть None -- построитель отчёта не печатает пустую строку
    фрагмента для этих форм."""
    lines = [_line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result[0]["_notes_fragment"] is None


def test_find_critic_notes_match_fragment_trimmed_at_string_start():
    """Граница ±40: совпадение у самого начала notes -- фрагмент не
    падает за пределы строки (нет ValueError/отрицательного индекса,
    просто обрезается)."""
    notes = "critic:t-1 " + ("x" * 60)
    matched, fragment = r3._find_critic_notes_match(notes)
    assert matched is True
    assert fragment.startswith("critic:t-1")


def test_find_critic_notes_match_fragment_trimmed_at_string_end():
    notes = ("y" * 60) + "critic:t-1"
    matched, fragment = r3._find_critic_notes_match(notes)
    assert matched is True
    assert fragment.endswith("critic:t-1")


def test_find_critic_notes_match_sanitizes_newlines_in_fragment():
    notes = "line one\ncritic:t-1\r\nline two"
    matched, fragment = r3._find_critic_notes_match(notes)
    assert matched is True
    assert "\n" not in fragment
    assert "\r" not in fragment


def test_find_critic_notes_match_no_occurrence_returns_false_none():
    matched, fragment = r3._find_critic_notes_match("нет упоминаний вообще")
    assert matched is False
    assert fragment is None


def test_find_critic_trail_delegated_critic_outside_event_type_not_matched():
    """basis=critic на НЕ-accepted событии не должен совпасть (условие
    привязано к event=='accepted')."""
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "delegated",
                "agent": "builder",
                "basis": "critic",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_malformed_json_line_is_skipped():
    """Край DoD: битые JSON-строки журнала -- пропуск, не исключение."""
    lines = [
        "{not valid json",
        _line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"}),
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1  # вторая строка разобралась, первая тихо пропущена


def test_find_critic_trail_blank_lines_are_skipped():
    lines = ["", "   ", _line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_event_missing_ts_is_skipped():
    lines = [_line({"event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_window_boundary_inclusive_start():
    """Граница ЗАПОЛНЕНА -- ts ровно на window_start считается ВНУТРИ
    окна (включительная граница)."""
    lines = [_line({"ts": "2026-08-25T09:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_window_boundary_inclusive_end():
    lines = [_line({"ts": "2026-08-25T11:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_before_window_start_excluded():
    """Граница ЗА пределами -- на одну секунду раньше окна -- НЕ
    засчитывается (тест "за" границей рядом с тестом "на" границе,
    гигиена п.6а)."""
    lines = [_line({"ts": "2026-08-25T08:59:59", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_after_window_end_excluded():
    lines = [_line({"ts": "2026-08-25T11:00:01", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_unbounded_window_start_none_accepts_any_earlier_ts():
    """window_start=None -- нижняя граница не ограничена (край "самый
    ранний коммит окна, нет предыдущего коммита репозитория")."""
    lines = [_line({"ts": "2000-01-01T00:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, None, "2026-08-25T11:00:00")
    assert len(result) == 1


# ---------------------------------------------------------------------
# build_report -- сквозной формат вывода (кандидат / найден / малые).
# ---------------------------------------------------------------------


def test_build_report_prints_candidate_label_when_no_trail_found():
    commits = [{"hash": "large1longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    report = r3.build_report("24 hours ago", commits, [])
    assert "КАНДИДАТ" in report
    assert "чек 2 решает" in report


def test_build_report_prints_found_label_when_trail_present():
    commits = [{"hash": "large1longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    journal_lines = [_line({"ts": "2026-08-25T08:30:00", "event": "delegated", "agent": "critic"})]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T08:00:00")
    assert "НАЙДЕН" in report
    assert "КАНДИДАТ" not in report


def test_build_report_t593_style_fixture_skip_only_notes_is_candidate():
    """Ф2 фикстура критика волны, дословно из требования: единственная
    accepted-строка с "critic: skipped" в окне + крупный (900-строчный
    аналог) коммит -> КАНДИДАТ, не НАЙДЕН."""
    commits = [{"hash": "t593likehash", "ts": "2026-08-25T13:00:00", "lines_changed": 900}]
    journal_lines = [
        _line(
            {
                "ts": "2026-08-25T12:47:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: skipped -- концессия резерва (D-0058)",
            }
        )
    ]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T12:00:00")
    assert "КАНДИДАТ" in report
    assert "критик-след НАЙДЕН" not in report
    assert "критик-след НЕ НАЙДЕН" in report


def test_build_report_prints_notes_fragment_for_notes_based_match():
    """Ф2 п.2: печать следа несёт фрагмент notes, по которому
    сработало совпадение."""
    commits = [{"hash": "large2longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    journal_lines = [
        _line(
            {
                "ts": "2026-08-25T08:30:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "закрыто ссылкой critic:t-593 на вердикт",
            }
        )
    ]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T08:00:00")
    assert "НАЙДЕН" in report
    assert "notes-фрагмент" in report
    assert "critic:t-593" in report


def test_build_report_no_fragment_line_for_delegated_critic_match():
    """У delegated/basis-совпадений фрагмента нет -- строка
    "notes-фрагмент" не должна появляться в отчёте для такого случая."""
    commits = [{"hash": "large3longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    journal_lines = [_line({"ts": "2026-08-25T08:30:00", "event": "delegated", "agent": "critic"})]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T08:00:00")
    assert "НАЙДЕН" in report
    assert "notes-фрагмент" not in report


def test_build_report_counts_small_commits_for_d0110_cumulative():
    commits = [
        {"hash": "s1", "ts": "2026-08-25T08:00:00", "lines_changed": 10},
        {"hash": "s2", "ts": "2026-08-25T08:30:00", "lines_changed": 40},
    ]
    report = r3.build_report("24 hours ago", commits, [])
    assert "малых" in report.lower() or "МАЛЫЕ" in report
    assert "D-0110" in report


def test_build_report_exit_semantics_line_present():
    report = r3.build_report("24 hours ago", [], [])
    assert "exit: 0" in report


def test_main_exits_zero_even_on_internal_exception(monkeypatch):
    """Р-О5: информатор, не гейт -- ЛЮБАЯ внутренняя ошибка (здесь --
    git недоступен/бросает) не должна поднимать код выхода."""

    def _boom(_since):
        raise RuntimeError("git недоступен (симуляция)")

    monkeypatch.setattr(r3, "fetch_window_commits", _boom)
    exit_code = r3.main(["--since", "24 hours ago"])
    assert exit_code == 0
