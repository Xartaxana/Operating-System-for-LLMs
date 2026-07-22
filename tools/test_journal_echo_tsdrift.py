"""Тесты TS DRIFT-слоя (ts-drift защита, слово оператора 2026-07-22
«делай сразу с защитой в journal_echo») -- реализован в
tools/journal_echo_staged.py (D-0069 sibling-файл, тот же приём, что
tools/test_witness_echo.py уже применил для узла N2:
tools/journal_echo.py -- ЖИВОЙ, не трогается; Lead ставит staged-копию
на живой путь при приёмке и УДАЛЯЕТ этот staged-файл -- при постановке
РЕТАРГЕТИТ импорт ниже (`import journal_echo_staged as je`) на
`import journal_echo as je`, ничего больше менять не нужно: все имена
использованы через алиас `je`).

РАСШИРЕНИЕ (t-277/t-279, диагноз критика по задаче t-263): критик нашёл
корневую причину, разделяемую ВСЕМИ ТРЕМЯ эхо-коллекторами этого файла
(TIER/WITNESS/TS-DRIFT) -- new_lines строился как HEAD-дифф-срез,
КУМУЛЯТИВНЫЙ между коммитами, поэтому каждый последующий вызов хука
переоценивал ВСЕ незакоммиченные строки заново, не только строку,
добавленную ИМЕННО этим tool-вызовом (для TS-DRIFT это классовая
ошибка: одна и та же старейшая строка "стареет" на каждом следующем
вызове, хотя её ts не менялся -- см. секцию "PAYLOAD-SCOPED ECHO BASE"
в tools/journal_echo.py за полный разбор и эмпирическую базу). Эта
задача добавляет секцию тестов НОВОГО payload-scoped механизма
(`je._extract_original_file`/`je._resolve_echo_base`) -- общего для всех
трёх коллекторов, хотя исторически этот файл называется по TS-DRIFT.

Стиль/самодостаточность -- по образцу tools/test_witness_echo.py (тоже
staged-тест того же класса): файл НЕ импортирует test_journal_echo.py
(тот -- чужой, non-goals этой задачи) -- хелперы (git-репо, запуск
хука, журнальные строки, транскрипты субагентов, dod_track-фикстура)
продублированы локально. Смок существующего функционала (последняя
секция) -- МИНИМАЛЬНЫЙ якорный набор, не полный импорт test_journal_echo
батареи: параметризация целого чужого тест-модуля потребовала бы
монки-патчить его внутренний SCRIPT/module-указатель на другой файл --
это создало бы скрытую связь с не-owns файлом (риск: любая будущая
правка test_journal_echo.py тихо меняет и это покрытие); анкорные тесты
-- та же степень изоляции, что уже выбрал test_witness_echo.py для
TIER ECHO/WITNESS ECHO смока.

Покрывает DoD-батарею спеки этой задачи буквально:
 1. свежий ts (0 дрейфа) -- тихо.
 2. future РОВНО на пороге (TS_FUTURE_TOLERANCE_SECONDS) -- тихо.
 3. future порог+1с -- warn.
 4. stale РОВНО на пороге (TS_STALE_TOLERANCE_SECONDS) -- тихо.
 5. stale порог+1с -- warn.
 6. сильно старый ts (часы) -- warn (STALE).
 7. непарсибельный ts -- тихо в дрейф-слое (fail-open), существующая
    диагностика формы (JOURNAL ECHO "не ISO-формат") не тронута/не
    задублирована.
 8. несколько строк батча с ОДНИМ ts -- по-событийно (каждая своя
    запись, не дедуплицируется).
 9. не-журнальные правки -- слой не активен (сквозной путь main()).
Плюс смок: минимальный якорный набор существующего функционала
staged-копии (JOURNAL ECHO/TIER ECHO/WITNESS ECHO/combine_context
обратная совместимость) -- зелёный после аддитивной правки.

РАСШИРЕНИЕ (t-277/t-279) -- новая секция "PAYLOAD-SCOPED ECHO BASE",
покрывает диагноз критика буквально:
 10. `_extract_original_file`/`_resolve_echo_base` -- pure-logic (не
     Edit/Write -> недоступно; tool_response не dict/без ключа/не
     str|None -> недоступно; originalFile=None -> ""; хвостовое
     расширение диска -> primary path; не-хвостовое -> фолбэк).
 11. корневая регрессия (DoD п.1/4): старая незакоммиченная строка ВНЕ
     payload этого вызова -- ноль ts-drift событий, даже если она сама
     по себе давно устарела по настенным часам; на неё же с ДРУГОЙ
     новой строкой в scope -- помечена только новая.
 12. граница TS_STALE_TOLERANCE через payload-scoped (не фолбэк) путь
     (DoD п.2).
 13. батч N строк одним tool-вызовом, payload-scoped (не фолбэк) путь
     -- по-событийно (DoD п.3).
 14. Write-путь: create (originalFile=None) и update (originalFile=
     прежний диск) -- корректный отбор; отсутствующий ключ
     originalFile -- фолбэк (DoD п.5).
 15. не-хвостовая правка / no-op -- ноль (DoD п.6).
 16. фолбэк-пометка (FALLBACK_MARKER_TEXT) видна вместе с другим
     выводом, но НЕ появляется на полностью чистом вызове (собственное
     инженерное решение, задокументировано в journal_echo.py).
 17. (сиблинг DoD п.8, TS-DRIFT-версия) TS DRIFT, помеченный на call #1,
     не переэхается на call #2 (TIER/WITNESS-версии -- см.
     tools/test_journal_echo.py/tools/test_witness_echo.py).

Run from the repo root: python -m pytest tools/test_journal_echo_tsdrift.py -q
"""

import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal_echo as je  # noqa: E402 -- ретаргет постановки Lead 2026-07-22 (t-263): staged -> live

SCRIPT = Path(__file__).resolve().parent / "journal_echo.py"  # ретаргет постановки Lead 2026-07-22 (t-263)


# =======================================================================
# helpers -- фиксированные часы для pure-тестов _detect_ts_drift
# =======================================================================

NOW = dt.datetime(2026, 7, 22, 12, 0, 0)


def _iso(delta_seconds: float) -> str:
    return (NOW + dt.timedelta(seconds=delta_seconds)).isoformat()


# =======================================================================
# helpers -- журнальные строки (по образцу test_journal_echo._line)
# =======================================================================


def _line(ts, event="delegated", agent="builder", category="implementation",
          notes="note", worker_ref="cli:2026-07-10T08:00:00", **kw) -> str:
    obj = {"ts": ts, "event": event, "agent": agent, "category": category,
           "notes": notes, "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(ts="2026-07-10T08:00:00", task_id="t-001", model="sonnet")
HEAD_TEXT = HEAD_LINE + "\n"


# =======================================================================
# helpers -- real git repos (по образцу test_journal_validator/test_journal_echo)
# =======================================================================


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def _init_repo(root: Path):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def _write_journal(root: Path, text: str) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-log.jsonl").write_text(text, encoding="utf-8")


def _seed_committed_journal(root: Path, text: str = HEAD_TEXT) -> Path:
    _init_repo(root)
    _write_journal(root, text)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    return root / "logs" / "routing-log.jsonl"


# =======================================================================
# helpers -- запуск хука
# =======================================================================


_NO_ORIGINAL_FILE = object()  # sentinel -- omit tool_response.originalFile
# entirely (t-277/t-279: exercises the FALLBACK path of
# je._resolve_echo_base -- identical to the pre-t-279 HEAD-diff
# computation). Default preserves every pre-existing call site's payload
# shape byte-for-byte.


def _post_tool_use_payload(file_path, cwd=".", session_id="sess-1", tool_name="Edit",
                            original_file=_NO_ORIGINAL_FILE) -> dict:
    tool_response = {"filePath": str(file_path), "success": True}
    if original_file is not _NO_ORIGINAL_FILE:
        # t-277/t-279: tool_response.originalFile (Edit/Write Zod
        # schemas -- see journal_echo.py's "PAYLOAD-SCOPED ECHO BASE").
        tool_response["originalFile"] = original_file
    return {
        "session_id": session_id,
        "transcript_path": "/x/transcript.jsonl",
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": tool_response,
        "tool_use_id": "tu-1",
    }


def _write_journal_full(root: Path, text: str) -> Path:
    """Пишет ПОЛНОЕ содержимое журнала (не через _write_journal, которая
    предполагает наличие logs/ уже -- эта версия создаёт каталог тоже) --
    используется Write-path тестами (DoD п.5), где main() читает диск
    ПОСЛЕ операции, а payload несёт tool_response.originalFile ОТДЕЛЬНО."""
    (root / "logs").mkdir(parents=True, exist_ok=True)
    path = root / "logs" / "routing-log.jsonl"
    path.write_text(text, encoding="utf-8")
    return path


def _run_hook(payload, timeout=10, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=env,
    )


def _parse_stdout_json(stdout: str) -> dict:
    payload = json.loads(stdout)
    hook_output = payload["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PostToolUse"
    return hook_output


# =======================================================================
# _detect_ts_drift -- pure logic, границы обоих порогов (правило 6а)
# =======================================================================


def test_detect_ts_drift_fresh_zero_delta_silent():
    assert je._detect_ts_drift(_iso(0), NOW) is None


def test_detect_ts_drift_small_jitter_silent():
    assert je._detect_ts_drift(_iso(5), NOW) is None
    assert je._detect_ts_drift(_iso(-5), NOW) is None


def test_detect_ts_drift_future_exactly_threshold_boundary_silent():
    assert je._detect_ts_drift(_iso(je.TS_FUTURE_TOLERANCE_SECONDS), NOW) is None


def test_detect_ts_drift_future_threshold_plus_one_warns():
    result = je._detect_ts_drift(_iso(je.TS_FUTURE_TOLERANCE_SECONDS + 1), NOW)
    assert result is not None
    kind, delta = result
    assert kind == "future"
    assert delta == pytest.approx(je.TS_FUTURE_TOLERANCE_SECONDS + 1)


def test_detect_ts_drift_stale_exactly_threshold_boundary_silent():
    assert je._detect_ts_drift(_iso(-je.TS_STALE_TOLERANCE_SECONDS), NOW) is None


def test_detect_ts_drift_stale_threshold_plus_one_warns():
    result = je._detect_ts_drift(_iso(-(je.TS_STALE_TOLERANCE_SECONDS + 1)), NOW)
    assert result is not None
    kind, delta = result
    assert kind == "stale"
    # delta -- ПОЛОЖИТЕЛЬНАЯ величина отставания (magnitude), не "сырая"
    # (parsed-now) разность -- см. _detect_ts_drift: stale_delta = -delta,
    # тот же принцип, что _format_ts_drift_line ожидает (округляет abs()).
    assert delta == pytest.approx(je.TS_STALE_TOLERANCE_SECONDS + 1)


def test_detect_ts_drift_hours_old_warns_stale():
    # DoD п.7 (диагноз t-277): этот тест остаётся ВЕРНЫМ под новой
    # payload-scoped семантикой -- он проверяет ЧИСТУЮ функцию сравнения
    # ts-vs-now (_detect_ts_drift), которая не знает НИЧЕГО о выборе
    # new_lines/базы и не участвует в баге, который t-277 диагностировал
    # (растущая устарелость СТАРОЙ уже-проверенной строки при повторных
    # вызовах хука -- это баг СЕЛЕКЦИИ строк, не баг сравнения одного
    # конкретного ts с одним конкретным now). Значение здесь моделирует
    # ДРУГОЙ, ортогональный и по-прежнему легитимный случай: ts,
    # заявленный как "5 часов назад" В МОМЕНТ ЗАПИСИ НОВОЙ строки -- это
    # само по себе нарушение F-29 (ts должен браться с часов
    # непосредственно перед записью), не растущая устарелость уже
    # проверенной строки -- и должно предупреждаться независимо от
    # версии базы. См. test_echo_tsdrift_hours_old_warns_stale ниже за
    # тот же комментарий на уровне e2e и новую регрессионную секцию
    # "PAYLOAD-SCOPED ECHO BASE" за тест, который ловит ИМЕННО баг
    # t-277 (растущую устарелость).
    result = je._detect_ts_drift(_iso(-3600 * 5), NOW)
    assert result is not None
    assert result[0] == "stale"


def test_detect_ts_drift_unparsable_string_returns_none():
    assert je._detect_ts_drift("not-a-timestamp", NOW) is None
    assert je._detect_ts_drift("2026-13-99T99:99:99", NOW) is None


def test_detect_ts_drift_non_string_returns_none():
    assert je._detect_ts_drift(None, NOW) is None
    assert je._detect_ts_drift(42, NOW) is None


def test_detect_ts_drift_empty_string_returns_none():
    assert je._detect_ts_drift("", NOW) is None


# =======================================================================
# _collect_ts_drift_events -- pure logic
# =======================================================================


def test_collect_ts_drift_events_empty_new_lines():
    assert je._collect_ts_drift_events([], [], NOW) == []


def test_collect_ts_drift_events_clean_line_silent():
    line = _line(ts=_iso(0), task_id="t-002", model="sonnet")
    assert je._collect_ts_drift_events([line], [], NOW) == []


def test_collect_ts_drift_events_future_line_reported():
    future_ts = _iso(je.TS_FUTURE_TOLERANCE_SECONDS + 10)
    line = _line(ts=future_ts, task_id="t-002", model="sonnet")
    events = je._collect_ts_drift_events([line], [], NOW)
    assert len(events) == 1
    line_no, kind, delta = events[0]
    assert (line_no, kind) == (1, "future")


def test_collect_ts_drift_events_batch_same_ts_reported_per_event():
    # DoD п.8: несколько строк с ОДНИМ и тем же ts -- каждая своя запись,
    # не схлопывается в одну.
    future_ts = _iso(je.TS_FUTURE_TOLERANCE_SECONDS + 10)
    lines = [
        _line(ts=future_ts, task_id="t-002", model="sonnet"),
        _line(ts=future_ts, task_id="t-003", model="sonnet"),
        _line(ts=future_ts, task_id="t-004", model="sonnet"),
    ]
    events = je._collect_ts_drift_events(lines, [], NOW)
    assert len(events) == 3
    assert [e[0] for e in events] == [1, 2, 3]
    assert all(e[1] == "future" for e in events)


def test_collect_ts_drift_events_malformed_json_line_skipped_not_raised():
    assert je._collect_ts_drift_events(["{not valid json"], [], NOW) == []


def test_collect_ts_drift_events_not_a_dict_line_skipped():
    assert je._collect_ts_drift_events(["[1, 2, 3]"], [], NOW) == []


def test_collect_ts_drift_events_line_numbering_accounts_for_head_lines():
    future_ts = _iso(je.TS_FUTURE_TOLERANCE_SECONDS + 10)
    head_lines = ["dummy head 1", "dummy head 2"]
    line = _line(ts=future_ts, task_id="t-002", model="sonnet")
    events = je._collect_ts_drift_events([line], head_lines, NOW)
    assert events[0][0] == 3  # len(head_lines) + idx(0) + 1


def test_collect_ts_drift_events_missing_ts_field_skipped():
    obj = json.loads(_line(ts=_iso(0), task_id="t-002", model="sonnet"))
    del obj["ts"]
    assert je._collect_ts_drift_events([json.dumps(obj)], [], NOW) == []


# =======================================================================
# _format_ts_drift_line -- pure logic, буквальный формат FUTURE (спека п.2)
# =======================================================================


def test_format_ts_drift_line_future_exact_literal():
    line = je._format_ts_drift_line((2, "future", 125.0))
    assert line == (
        "TS DRIFT: line 2 event ts is 125s in the FUTURE "
        "(F-29: ts must be read from the system clock immediately before writing)"
    )


def test_format_ts_drift_line_stale_contains_marker_and_seconds():
    line = je._format_ts_drift_line((3, "stale", 1801.0))
    assert "TS DRIFT: line 3 event ts is 1801s STALE" in line
    assert line.isascii()


def test_format_ts_drift_line_rounds_fractional_seconds():
    line = je._format_ts_drift_line((1, "future", 125.6))
    assert "126s" in line


def test_format_ts_drift_line_is_ascii_always():
    assert je._format_ts_drift_line((1, "future", 999.0)).isascii()
    assert je._format_ts_drift_line((1, "stale", 9999.0)).isascii()


# =======================================================================
# build_ts_drift_segment -- pure logic
# =======================================================================


def test_build_ts_drift_segment_empty_list():
    assert je.build_ts_drift_segment([]) == ""


def test_build_ts_drift_segment_single_event():
    ev = (2, "future", 125.0)
    seg = je.build_ts_drift_segment([ev])
    assert seg == je._format_ts_drift_line(ev)


def test_build_ts_drift_segment_joins_multiple_with_semicolon():
    events = [(2, "future", 125.0), (3, "stale", 1801.0)]
    seg = je.build_ts_drift_segment(events)
    assert seg.count("TS DRIFT") == 2
    assert "; " in seg


# ---------------------------------------------------------------------
# build_ts_drift_segment -- граница MAX_TS_DRIFT_LINES (BLOCKER 1, R11 6а)
# ---------------------------------------------------------------------


def test_build_ts_drift_segment_exactly_five_boundary_no_more_suffix():
    events = [(i, "future", 200.0) for i in range(1, je.MAX_TS_DRIFT_LINES + 1)]
    seg = je.build_ts_drift_segment(events)
    assert seg.count("TS DRIFT") == je.MAX_TS_DRIFT_LINES
    assert "more" not in seg


def test_build_ts_drift_segment_beyond_boundary_six_adds_one_more():
    events = [(i, "future", 200.0) for i in range(1, je.MAX_TS_DRIFT_LINES + 2)]
    seg = je.build_ts_drift_segment(events)
    assert seg.count("TS DRIFT") == je.MAX_TS_DRIFT_LINES
    assert seg.endswith("; +1 more")


def test_build_ts_drift_segment_far_beyond_boundary_counts_correctly():
    events = [(i, "future", 200.0) for i in range(1, je.MAX_TS_DRIFT_LINES + 6)]
    seg = je.build_ts_drift_segment(events)
    assert seg.count("TS DRIFT") == je.MAX_TS_DRIFT_LINES
    assert seg.endswith("; +5 more")


# =======================================================================
# combine_context -- обратная совместимость 2-/3-арг форм + новый сегмент
# =======================================================================


def test_combine_context_two_arg_form_unaffected():
    violations = ["line 2: msg one"]
    assert je.combine_context(violations, []) == je.build_context(violations)


def test_combine_context_three_arg_witness_form_unaffected():
    violations = ["v"]
    ctx = je.combine_context(violations, [], [])
    assert ctx == je.build_context(violations)


def test_combine_context_ts_drift_only_segment():
    ev = (2, "future", 125.0)
    ctx = je.combine_context([], [], None, [ev])
    assert ctx == je.build_ts_drift_segment([ev])
    assert "JOURNAL ECHO" not in ctx


def test_combine_context_all_four_segments_joined_in_order():
    violations = ["v"]
    tier_ev = (2, "mismatch", "fable", {"claude-opus-4-8": 1})
    ts_ev = (3, "future", 125.0)
    ctx = je.combine_context(violations, [tier_ev], [], [ts_ev])
    assert ctx == (
        je.build_context(violations) + "; " + je.build_tier_segment([tier_ev])
        + "; " + je.build_ts_drift_segment([ts_ev])
    )


def test_combine_context_all_empty_yields_empty_string():
    assert je.combine_context([], [], None, None) == ""


# =======================================================================
# main() end-to-end -- subprocess-смок, DoD 1-9
# =======================================================================


def test_echo_tsdrift_fresh_ts_silent(tmp_path):
    # DoD 1: свежий ts (0 дрейфа) -- тихо.
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    new_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="fresh")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tsdrift_future_beyond_threshold_warns(tmp_path):
    # DoD 3 (сквозной путь, generous margin -- точная граница проверена
    # pure-тестом test_detect_ts_drift_future_threshold_plus_one_warns;
    # здесь -- реальные часы процесса, запас против subprocess-джиттера).
    journal_path = _seed_committed_journal(tmp_path)
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    new_line = _line(ts=future_ts, task_id="t-002", model="sonnet", notes="future drift")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TS DRIFT" in ctx
    assert "FUTURE" in ctx
    assert "F-29" in ctx


def test_echo_tsdrift_stale_beyond_threshold_warns(tmp_path):
    # DoD 5 (сквозной путь, generous margin).
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    new_line = _line(ts=stale_ts, task_id="t-002", model="sonnet", notes="stale drift")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TS DRIFT" in ctx
    assert "STALE" in ctx
    assert "D-0079" in ctx


def test_echo_tsdrift_hours_old_warns_stale(tmp_path):
    # DoD 6, DoD п.7 (диагноз t-277): этот сценарий тоже остаётся верным
    # под новой payload-scoped семантикой -- ОДНА строка добавляется В
    # ЭТОМ ЖЕ вызове (single-call append, без originalFile -> фолбэк на
    # HEAD-дифф, который здесь СОВПАДАЕТ с payload-scoped базой: и там,
    # и там "новое" -- ровно эта одна строка). Её ts "5 часов назад" В
    # МОМЕНТ ЗАПИСИ -- легитимный F-29-варн независимо от версии базы
    # (см. комментарий test_detect_ts_drift_hours_old_warns_stale выше
    # за разбор, ЧЕМ этот класс отличается от бага t-277: растущей
    # устарелости УЖЕ проверенной строки на ПОЗДНЕЙШЕМ, другом вызове --
    # см. регрессионный тест в секции "PAYLOAD-SCOPED ECHO BASE" ниже).
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(hours=5)).isoformat()
    new_line = _line(ts=stale_ts, task_id="t-002", model="sonnet", notes="hours old")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "STALE" in hook_output["additionalContext"]


def test_echo_tsdrift_unparsable_ts_silent_in_drift_layer_existing_diagnostic_intact(tmp_path):
    # DoD 7: непарсибельный ts -- тихо в дрейф-слое (fail-open), НЕ
    # дублирует диагностику -- существующая JOURNAL ECHO-жалоба ("не
    # ISO-формат") остаётся ЕДИНСТВЕННЫМ источником сигнала об этом поле.
    journal_path = _seed_committed_journal(tmp_path)
    new_line = _line(ts="not-a-timestamp", task_id="t-002", model="sonnet", notes="bad ts")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "не ISO-формат" in ctx
    assert "TS DRIFT" not in ctx


def test_echo_tsdrift_batch_two_lines_same_future_ts_per_event(tmp_path):
    # DoD 8: несколько строк батча с ОДНИМ ts -- по-событийно, две
    # отдельные TS DRIFT-записи, не одна схлопнутая.
    journal_path = _seed_committed_journal(tmp_path)
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    lines = [
        _line(ts=future_ts, task_id="t-002", model="sonnet", notes="batch one"),
        _line(ts=future_ts, task_id="t-003", model="sonnet", notes="batch two"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TS DRIFT") == 2


def _standalone_batch(tmp_path, n, future_ts):
    # head_text=None (git НИКОГДА не init'ed) -> ВСЕ n строк диска -- "новые"
    # (см. MAX_TS_DRIFT_LINES докстринг: мотивация потолка -- ровно этот
    # сценарий). Каждая -- валидный delegated с последовательным task_id
    # (валидатор требует max+1) и своим worker_ref (D-0076).
    lines = [
        _line(ts=future_ts, task_id=f"t-{i + 1:03d}", model="sonnet",
              worker_ref=f"cli:seed-{i}", notes=f"standalone drift #{i}")
        for i in range(n)
    ]
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text("".join(l + "\n" for l in lines), encoding="utf-8")
    return journal_path


def test_echo_tsdrift_standalone_exactly_max_lines_no_more_suffix(tmp_path):
    # Граница (правило 6а): РОВНО MAX_TS_DRIFT_LINES строк -- без "+more",
    # сквозной путь (standalone-режим, head_text=None -- см. мотивацию
    # потолка в докстринге MAX_TS_DRIFT_LINES).
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    journal_path = _standalone_batch(tmp_path, je.MAX_TS_DRIFT_LINES, future_ts)
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TS DRIFT") == je.MAX_TS_DRIFT_LINES
    assert "more" not in ctx


def test_echo_tsdrift_standalone_beyond_max_lines_adds_more_suffix(tmp_path):
    # Граница+1: MAX_TS_DRIFT_LINES+1 строк -- "+1 more".
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    journal_path = _standalone_batch(tmp_path, je.MAX_TS_DRIFT_LINES + 1, future_ts)
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TS DRIFT") == je.MAX_TS_DRIFT_LINES
    assert "+1 more" in ctx


def test_echo_tsdrift_non_journal_path_silent(tmp_path):
    # DoD 9: не-журнальная правка -- слой не активен (сквозной путь main()
    # выходит на _is_journal_path раньше, чем ts-drift вообще вычисляется).
    other_file = tmp_path / "not-a-journal.txt"
    other_file.write_text('{"ts": "not-a-timestamp"}', encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(other_file))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tsdrift_defect_and_drift_together_one_context(tmp_path):
    # Форма-дефект (пустая category) + TS DRIFT вместе -- оба сегмента в
    # одном additionalContext, склеены "; " (спека п.3, комбинированный
    # тест по образцу test_echo_tier_dod_e_form_defect_and_mismatch_together
    # живого test_journal_echo.py).
    journal_path = _seed_committed_journal(tmp_path)
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    bad_line = _line(ts=future_ts, task_id="t-002", model="sonnet", category="", notes="defect+drift")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов)" in ctx
    assert "TS DRIFT" in ctx
    assert "; TS DRIFT" in ctx


def test_echo_tsdrift_ascii_output_stdout(tmp_path):
    # Спека п.4: ASCII-вывод по конвенции файла -- wire-байты стдаута
    # остаются чистым ASCII (json.dumps ensure_ascii=True), TS DRIFT сам
    # по себе никогда не несёт не-ASCII динамики (только целые числа).
    journal_path = _seed_committed_journal(tmp_path)
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    new_line = _line(ts=future_ts, task_id="t-002", model="sonnet", notes="ascii check")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.stdout.isascii()


# =======================================================================
# смок: минимальный якорный набор существующего функционала staged-копии
# (JOURNAL ECHO / TIER ECHO / WITNESS ECHO / combine_context) -- зелёный
# после аддитивной ts-drift-правки. Хелперы для TIER/WITNESS -- см.
# докстринг модуля за обоснование самодостаточности.
# =======================================================================


def test_smoke_non_journal_path_silent(tmp_path):
    other_file = tmp_path / "not-a-journal.txt"
    other_file.write_text("irrelevant content", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(other_file))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_smoke_clean_new_line_silent(tmp_path):
    # ВАЖНО (реальная находка, не домысел): фиксированная историческая
    # ts-фикстура ("2026-07-10T08:10:00", как в живом test_journal_echo.py)
    # ТЕПЕРЬ (после этой правки) законно ловится TS DRIFT STALE -- реальные
    # часы машины давно ушли вперёд относительно этой даты. Это НЕ дефект
    # нового слоя (он и должен ловить старый ts), а ожидаемое следствие:
    # смок обязан использовать СВЕЖИЙ ts (текущие часы), чтобы проверять
    # ИМЕННО "существующая функциональность не сломана", не пересекаясь с
    # новым слоем. См. отчёт билдера за явную фиксацию этой находки.
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    new_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="clean")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_smoke_missing_category_defect_reported(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(ts="2026-07-10T08:10:00", task_id="t-002", model="sonnet", category="")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов) в новых строках:" in ctx
    assert "'category'" in ctx


def _assistant_line(model):
    return {"type": "assistant", "message": {"model": model}}


def _write_agent_transcript(home: Path, agent_id: str, lines,
                            proj="proj-slug", sess="sess-id") -> Path:
    path = home / ".claude" / "projects" / proj / sess / "subagents" / f"agent-{agent_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(line) if not isinstance(line, str) else line for line in lines) + "\n",
        encoding="utf-8",
    )
    return path


def _env_with_home(home: Path) -> dict:
    env = dict(os.environ)
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    return env


def test_smoke_tier_echo_mismatch_still_works(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(home, "fbl001", [_assistant_line("claude-opus-4-8")])
    new_line = _line(ts="2026-07-10T08:10:00", task_id="t-002", model="fable",
                      worker_ref="agent:fbl001", notes="mismatch case")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TIER ECHO" in ctx
    assert "MISMATCH" in ctx


def _write_track(root: Path, session_id: str, runs: list) -> Path:
    track_dir = root / ".claude" / "dod_track"
    track_dir.mkdir(parents=True, exist_ok=True)
    path = track_dir / f"{session_id}.json"
    path.write_text(json.dumps({"edits": [], "runs": runs}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    return path


def test_smoke_witness_echo_red_warn_still_works(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        {"ts": "2026-07-10T08:05:00.000000", "tool_name": "Bash",
         "command": "python -m pytest tools/ -q", "outcome": "red", "agent_id": None},
    ])
    new_line = _line(ts="2026-07-10T08:10:00", event="accepted", agent="builder",
                      task_id="t-001", by="opus", model="sonnet",
                      witness="ran: python -m pytest tools/ -q", notes="accepted with red witness")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=str(tmp_path), session_id="sess-1"))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "WITNESS ECHO" in ctx
    assert "contradiction" in ctx


def test_smoke_combine_context_backward_compat_two_arg():
    assert je.combine_context(["v"], []) == je.build_context(["v"])


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE (t-277/t-279) -- _extract_original_file, pure
# =======================================================================


def test_extract_original_file_non_edit_write_tool_unavailable():
    payload = {"tool_response": {"originalFile": "x"}}
    assert je._extract_original_file(payload, "Bash") is je._ORIGINAL_FILE_UNAVAILABLE
    assert je._extract_original_file(payload, "MultiEdit") is je._ORIGINAL_FILE_UNAVAILABLE
    assert je._extract_original_file(payload, None) is je._ORIGINAL_FILE_UNAVAILABLE


def test_extract_original_file_tool_response_not_dict_unavailable():
    payload = {"tool_response": "not-a-dict"}
    assert je._extract_original_file(payload, "Edit") is je._ORIGINAL_FILE_UNAVAILABLE


def test_extract_original_file_tool_response_missing_unavailable():
    assert je._extract_original_file({}, "Edit") is je._ORIGINAL_FILE_UNAVAILABLE


def test_extract_original_file_key_absent_unavailable():
    payload = {"tool_response": {"filePath": "x"}}
    assert je._extract_original_file(payload, "Write") is je._ORIGINAL_FILE_UNAVAILABLE


def test_extract_original_file_none_means_new_file_empty_string():
    payload = {"tool_response": {"originalFile": None}}
    assert je._extract_original_file(payload, "Write") == ""
    assert je._extract_original_file(payload, "Edit") == ""


def test_extract_original_file_wrong_type_unavailable():
    payload = {"tool_response": {"originalFile": 42}}
    assert je._extract_original_file(payload, "Edit") is je._ORIGINAL_FILE_UNAVAILABLE


def test_extract_original_file_valid_string_returned():
    payload = {"tool_response": {"originalFile": "line1\nline2\n"}}
    assert je._extract_original_file(payload, "Edit") == "line1\nline2\n"
    assert je._extract_original_file(payload, "Write") == "line1\nline2\n"


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE (t-277/t-279) -- _resolve_echo_base, pure
# =======================================================================


def test_resolve_echo_base_primary_path_tail_append():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1", "b1"]
    payload = {"tool_response": {"originalFile": "h1\na1\n"}}
    base, new, fallback = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is False
    assert base == ["h1", "a1"]
    assert new == ["b1"]


def test_resolve_echo_base_falls_back_when_unavailable():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1"]
    payload = {"tool_response": {}}  # no originalFile key at all
    base, new, fallback = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is True
    assert base == head_lines
    assert new == ["a1"]


def test_resolve_echo_base_falls_back_on_non_tail_edit():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1", "b1"]
    # originalFile claims a DIFFERENT prior state -- disk doesn't extend
    # it as a prefix (a non-tail edit).
    payload = {"tool_response": {"originalFile": "different\n"}}
    base, new, fallback = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is True
    assert base == head_lines
    assert new == staged_lines[len(head_lines):]


def test_resolve_echo_base_no_op_edit_yields_empty_new_lines():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1"]
    payload = {"tool_response": {"originalFile": "h1\na1\n"}}  # identical to disk -- nothing added
    base, new, fallback = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is False
    assert new == []


def test_resolve_echo_base_write_new_file_none_original():
    staged_lines = ["a1", "a2"]
    payload = {"tool_response": {"originalFile": None}}
    base, new, fallback = je._resolve_echo_base(payload, "Write", staged_lines, [])
    assert fallback is False
    assert base == []
    assert new == ["a1", "a2"]


def test_resolve_echo_base_fallback_when_head_diff_also_non_append_only():
    # Both bases fail -> the fallback branch itself yields [] (append_ok
    # False against head_lines too) -- matches this file's pre-existing
    # behavior for the old HEAD-diff append-only-violation case.
    head_lines = ["h1", "h2"]
    staged_lines = ["DIFFERENT"]
    payload = {"tool_response": {}}
    base, new, fallback = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is True
    assert new == []


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE (t-277/t-279) -- e2e, root regression (DoD 1/4)
# =======================================================================


def test_echo_payload_scoped_earlier_uncommitted_line_outside_scope_silent(tmp_path):
    # DoD п.1/4 (диагноз t-277): A -- строка, добавленная РАНЕЕ (не этим
    # вызовом), её ts настолько стар, что по настенным часам она
    # действительно STALE -- но она НЕ входит в payload ЭТОГО вызова
    # (originalFile этого вызова УЖЕ включает её) -> ноль ts-drift
    # событий, несмотря на то что старая HEAD-дифф-логика переоценила бы
    # и её тоже (это и есть баг, который данная задача чинит).
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 600)).isoformat()
    line_a = _line(ts=stale_ts, task_id="t-002", model="sonnet",
                   notes="A: written earlier, now stale by wall clock")
    after_call_a = HEAD_TEXT + line_a + "\n"
    fresh_ts = dt.datetime.now().isoformat()
    line_b = _line(ts=fresh_ts, task_id="t-003", model="sonnet", worker_ref="cli:call-b",
                   notes="B: this call's own new line, fresh")
    journal_path.write_text(after_call_a + line_b + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=after_call_a))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_payload_scoped_only_current_call_line_flagged_not_earlier_stale(tmp_path):
    # Surgical variant: BOTH A and B are stale by wall clock -- only B
    # (this call's own line) may be reported; A must not reappear.
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts_a = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 600)).isoformat()
    line_a = _line(ts=stale_ts_a, task_id="t-002", model="sonnet", notes="A: earlier call, stale")
    after_call_a = HEAD_TEXT + line_a + "\n"
    stale_ts_b = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    line_b = _line(ts=stale_ts_b, task_id="t-003", model="sonnet", worker_ref="cli:call-b",
                   notes="B: this call's own new line, also stale")
    journal_path.write_text(after_call_a + line_b + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=after_call_a))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TS DRIFT") == 1
    assert "line 3" in ctx  # HEAD=1 line, A=line 2 (out of scope), B=line 3 (in scope)


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE -- e2e, TS_STALE_TOLERANCE boundary via the
# PRIMARY (not fallback) path (DoD 2). Exact-boundary precision is
# already proven by the pure _detect_ts_drift tests above (fixed NOW,
# no subprocess jitter) -- these e2e tests only prove the primary path
# reaches the same detector, with a generous margin against subprocess
# start-up jitter, the same style the rest of this file already uses.
# =======================================================================


def test_echo_payload_scoped_fresh_ts_silent(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    new_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="fresh, payload-scoped path")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_payload_scoped_stale_beyond_threshold_warns(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    new_line = _line(ts=stale_ts, task_id="t-002", model="sonnet", notes="stale, payload-scoped path")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TS DRIFT" in ctx
    assert "STALE" in ctx


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE -- e2e, batch of N lines in ONE call, PRIMARY
# path, per-event (DoD 3)
# =======================================================================


def test_echo_payload_scoped_batch_lines_one_call_per_event(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    future_ts = (dt.datetime.now() + dt.timedelta(seconds=je.TS_FUTURE_TOLERANCE_SECONDS + 60)).isoformat()
    lines = [
        _line(ts=future_ts, task_id=f"t-{i:03d}", model="sonnet", worker_ref=f"cli:batch-{i}",
              notes=f"batch line #{i}")
        for i in (2, 3, 4)
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TS DRIFT") == 3


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE -- e2e, Write path (DoD 5)
# =======================================================================


def test_echo_write_new_file_originalfile_none_correct_scoping(tmp_path):
    # DoD п.5: Write создаёт НОВЫЙ файл -- originalFile=None по
    # Zod-схеме Write (см. journal_echo.py) -- вся content-строка стала
    # "своей" для этого вызова; она чиста -> тишина.
    (tmp_path / "logs").mkdir(parents=True)
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    fresh_ts = dt.datetime.now().isoformat()
    line = _line(ts=fresh_ts, task_id="t-001", model="sonnet", notes="brand new journal via Write")
    journal_path.write_text(line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="Write", original_file=None)
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_write_new_file_stale_line_flagged(tmp_path):
    (tmp_path / "logs").mkdir(parents=True)
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    line = _line(ts=stale_ts, task_id="t-001", model="sonnet", notes="brand new journal, stale first line")
    journal_path.write_text(line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="Write", original_file=None)
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TS DRIFT" in ctx
    assert "STALE" in ctx


def test_echo_write_update_existing_file_correct_scoping(tmp_path):
    # DoD п.5: Write ПЕРЕЗАПИСЫВАЕТ существующий файл целиком --
    # originalFile = прежнее полное содержимое; только добавленный
    # хвост попадает в scope, старые (уже бывшие на диске ДО этого
    # конкретного вызова) строки -- нет, даже если сами по себе стары
    # по часам.
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts_prior = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 600)).isoformat()
    prior_extra = _line(ts=stale_ts_prior, task_id="t-002", model="sonnet", notes="prior extra line, stale")
    prior_full = HEAD_TEXT + prior_extra + "\n"
    fresh_ts = dt.datetime.now().isoformat()
    new_line = _line(ts=fresh_ts, task_id="t-003", model="sonnet", worker_ref="cli:write-update",
                      notes="freshly written via Write, appended to prior_full")
    journal_path.write_text(prior_full + new_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="Write", original_file=prior_full)
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_write_missing_originalfile_key_falls_back_with_marker(tmp_path):
    # DoD п.5, часть "или fail-open с пометкой": Write-tool_response БЕЗ
    # originalFile вовсе -- фолбэк на HEAD-дифф + видимая пометка
    # (проверяем это вместе с реальным дефектом, чтобы пометка была
    # видна -- см. секцию про фолбэк-пометку ниже за отдельный тест
    # "чистый вызов остаётся тихим").
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    new_line = _line(ts=stale_ts, task_id="t-002", model="sonnet", notes="stale, Write without originalFile")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="Write")  # no original_file kwarg -> key absent
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TS DRIFT" in ctx
    assert je.FALLBACK_MARKER_TEXT in ctx


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE -- e2e, non-tail edit / no-op (DoD 6)
# =======================================================================


def test_echo_non_tail_edit_falls_back_silently_when_no_actual_drift(tmp_path):
    # DoD п.6: originalFile присутствует, но НЕ является префиксом
    # текущего диска (не-хвостовая правка) -- фолбэк на HEAD-дифф; в
    # этом сценарии обе базы согласны, что единственная новая строка
    # чиста -- ноль событий.
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    new_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="clean new line")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, original_file="{totally unrelated content}\n")
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_no_op_edit_identical_original_file_zero_events(tmp_path):
    # DoD п.6, "no-op": originalFile == текущий диск буквально -- ничего
    # не добавлено этим вызовом -> ноль новых строк, ноль событий.
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    new_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="already-committed-equivalent state")
    full_text = HEAD_TEXT + new_line + "\n"
    journal_path.write_text(full_text, encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, original_file=full_text)
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE -- e2e, fallback-marker visibility (own
# engineering completion of "so degradation is visible, not silent")
# =======================================================================


def test_echo_fallback_marker_appears_alongside_other_output(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    bad_line = _line(ts=stale_ts, task_id="t-002", model="sonnet", category="",
                      notes="defect + stale, fallback path")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path)  # no original_file -> fallback engaged
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "TS DRIFT" in ctx
    assert je.FALLBACK_MARKER_TEXT in ctx
    assert ("; " + je.FALLBACK_MARKER_TEXT) in ctx  # joined as the trailing segment


def test_echo_fallback_marker_not_shown_on_otherwise_clean_call(tmp_path):
    # Собственное инженерное решение (см. journal_echo.py, "PAYLOAD-
    # SCOPED ECHO BASE"): фолбэк САМ ПО СЕБЕ не делает чистый вызов
    # шумным -- та же гарантия "без шума на чистой записи", что этот
    # хук несёт с самого начала.
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    clean_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="clean, fallback path")
    journal_path.write_text(HEAD_TEXT + clean_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path)  # no original_file -> fallback engaged
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# =======================================================================
# PAYLOAD-SCOPED ECHO BASE -- e2e, DoD 8 sibling (TS-DRIFT version of
# the tier/witness re-echo regression -- see tools/test_journal_echo.py/
# tools/test_witness_echo.py for the TIER/WITNESS versions)
# =======================================================================


def test_echo_tsdrift_payload_scoped_not_reechoed_on_later_unrelated_call(tmp_path):
    # Диагноз t-277, корневой тест: строка A помечена STALE на call #1;
    # call #2 добавляет ДРУГУЮ (свежую) строку B -- A НЕ должна снова
    # появиться в выводе call #2 (она уже вне payload этого вызова).
    journal_path = _seed_committed_journal(tmp_path)
    stale_ts = (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()
    line_a = _line(ts=stale_ts, task_id="t-002", model="sonnet", notes="call #1: stale")
    after_call_1 = HEAD_TEXT + line_a + "\n"
    journal_path.write_text(after_call_1, encoding="utf-8")
    result1 = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result1.returncode == 0
    ctx1 = _parse_stdout_json(result1.stdout)["additionalContext"]
    assert "TS DRIFT" in ctx1
    assert "STALE" in ctx1

    fresh_ts = dt.datetime.now().isoformat()
    line_b = _line(ts=fresh_ts, task_id="t-003", model="sonnet", worker_ref="cli:call-b",
                   notes="call #2: unrelated fresh line")
    journal_path.write_text(after_call_1 + line_b + "\n", encoding="utf-8")
    result2 = _run_hook(_post_tool_use_payload(journal_path, original_file=after_call_1))
    assert result2.returncode == 0
    assert result2.stdout == ""
    assert result2.stderr == ""
