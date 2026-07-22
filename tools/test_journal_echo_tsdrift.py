"""Тесты TS DRIFT-слоя (ts-drift защита, слово оператора 2026-07-22
«делай сразу с защитой в journal_echo») -- реализован в
tools/journal_echo_staged.py (D-0069 sibling-файл, тот же приём, что
tools/test_witness_echo.py уже применил для узла N2:
tools/journal_echo.py -- ЖИВОЙ, не трогается; Lead ставит staged-копию
на живой путь при приёмке и УДАЛЯЕТ этот staged-файл -- при постановке
РЕТАРГЕТИТ импорт ниже (`import journal_echo_staged as je`) на
`import journal_echo as je`, ничего больше менять не нужно: все имена
использованы через алиас `je`).

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


def _post_tool_use_payload(file_path, cwd=".", session_id="sess-1", tool_name="Edit") -> dict:
    return {
        "session_id": session_id,
        "transcript_path": "/x/transcript.jsonl",
        "cwd": str(cwd),
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"filePath": str(file_path), "success": True},
        "tool_use_id": "tu-1",
    }


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
    # DoD 6: сильно старый ts (часы) -- warn.
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
