"""Тесты NOTES LEN ECHO-слоя (t-447, замер 2026-08-16), реализован
ПРЯМО в живом tools/journal_echo.py (Ф8 спеки t-447 -- этот слой правит
ЖИВОЙ hook-путь напрямую, БЕЗ staged-копии; в отличие от
tools/test_journal_echo_tsdrift.py/tools/test_journal_echo_escalation.py,
чьи докстринги всё ещё документируют staged-конвенцию ДЛЯ СВОИХ будущих
добавлений -- она к этому файлу не относится).

ПОВОД: замер по logs/routing-log.jsonl (1239 событий) -- медиана длины
notes 550, p75 768, p90 1047, p99 2040, max 13352; 43% событий длиннее
600; последние 30 событий -- 22 из 30 длиннее 600. WARN при записи
журнальной строки, чьё notes длиннее порога, назначенного ТИПУ события
-- НИКОГДА не блок (returncode всегда 0, ни один канал не несёт
permissionDecision).

Стиль -- по образцу tools/test_journal_echo_escalation.py (сиблинг того
же класса: pure-логика + subprocess-смок main() через реальные tmp_path
git-репо). Хелперы (git-репо, запуск хука, журнальные строки) продублированы
локально (та же самодостаточность-предпочтение, что сиблинги уже
объясняют).

Покрывает DoD-батарею спеки t-447 буквально:
 Границы (правило 6а, обе стороны каждого лимита):
  B1/B2/B3 -- порог 800 (диспетчерский цикл): 800 тихо, 801 warn, 799 тихо.
  B4/B5 -- порог 15000 (calibrated): 13352 (реальный max) тихо, 15001 warn
           (+ 15000 ровно на пороге -- тихо, собственное усиление сверх
           буквального текста спеки, тот же принцип "лимит без граничного
           теста -- незакрытый DoD").
 Потолок строк (MAX_NOTES_LEN_LINES=5):
  B6 -- ровно 5 без хвоста; 6 -- "; +1 more".
 Пустые/битые (E4-E11):
  B7/B8/B9 -- notes отсутствует/пустая-из-пробелов/не строка -- молчим,
             дефект формы (journal_validator) не задвоен.
  B10 -- битая JSON-строка + вторая валидная длинная -- warn ровно по
         второй, хук не падает.
  B11 -- неизвестный event / отсутствующий event -- молчим.
 База отбора (Ф5, регресс-пин класса F-57):
  B12 -- старая длинная незакоммиченная строка ВНЕ payload -- ноль событий.
  B13 -- фолбэк-режим -- слой ПОЛНОСТЬЮ отключён (ноль событий), маркер
         фолбэка на месте.
  B14 -- не-журнальная правка -- слой не активен.
 Адверсариальная мини-батарея:
  B15 -- notes 200000 символов -- ровно одно сообщение, сегмент не раздут,
         фрагмент notes не протекает в сообщение (Ф6).
  B16 -- control-chars и кириллица в notes -- stdout валидный JSON, хук
         не падает.
  B17 -- батч 200 строк, 100 длинных -- 5 сообщений + "; +95 more".
 Ловушка 2 / R-4 (keyword-only):
  B18 -- пин: `je.combine_context([], [], None, None, [ev], "MARKER")`
         (6 позиционных) даёт прежний результат, notes_len_events не
         вклинивается позиционно.
 Порядок сегментов (R-6):
  B19 -- violations первым (литерал заголовка неизменен), notes_len
         между escalation и fallback_marker, marker последним.
 B20 -- returncode 0 везде, без permissionDecision (сквозь всю батарею).

Run from the repo root: python -m pytest tools/test_journal_echo_noteslen.py -q
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal_echo as je  # noqa: E402 -- живой файл, прямой импорт (Ф8)
from wallclock_guard import WALLCLOCK_HARNESS_TIMEOUT  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "journal_echo.py"


def _fresh_ts() -> str:
    # Свежий (относительно РЕАЛЬНЫХ часов) ts -- та же находка, что
    # tools/test_journal_echo_escalation.py._fresh_ts уже документирует:
    # фиксированная историческая ts-фикстура в НОВЫХ строках ловится
    # живым TS DRIFT ECHO как STALE и загрязняет additionalContext
    # посторонним сегментом. Каждый вызов _line() без явного ts берёт
    # свежее значение.
    return datetime.datetime.now().isoformat(timespec="seconds")


# =======================================================================
# helpers -- журнальные строки (по образцу test_journal_echo_escalation._line)
# =======================================================================


def _line(event="delegated", ts=None, agent="builder",
          category="implementation", notes="note",
          worker_ref="cli:2026-08-16T08:00:00", **kw) -> str:
    obj = {"ts": ts if ts is not None else _fresh_ts(), "event": event, "agent": agent,
           "category": category, "notes": notes, "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(event="delegated", ts="2026-08-16T08:00:00", task_id="t-001", model="sonnet")
HEAD_TEXT = HEAD_LINE + "\n"


# =======================================================================
# helpers -- real git repos (по образцу сиблингов)
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


_NO_ORIGINAL_FILE = object()  # sentinel -- omit tool_response.originalFile entirely
# (exercises the HEAD-diff fallback path of _resolve_echo_base -- same
# convention as the sibling echo test files).


def _post_tool_use_payload(file_path, tool_name="Edit", original_file=_NO_ORIGINAL_FILE) -> dict:
    tool_response = {"filePath": str(file_path), "success": True}
    if original_file is not _NO_ORIGINAL_FILE:
        tool_response["originalFile"] = original_file
    return {
        "session_id": "sess-1",
        "transcript_path": "/x/transcript.jsonl",
        "cwd": ".",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": tool_response,
        "tool_use_id": "tu-1",
    }


def _run_hook(payload, timeout=WALLCLOCK_HARNESS_TIMEOUT, env=None) -> subprocess.CompletedProcess:
    # F-60 (класс A): сетка против зависшего хука, не утверждение о
    # предмете; WALLCLOCK_HARNESS_TIMEOUT -- общий источник значения.
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"journal_echo hook exceeded WALLCLOCK_HARNESS_TIMEOUT={timeout}s -- "
            "сторож стенных часов: проверь загрузку машины прежде, чем "
            "считать это дефектом (F-60)"
        )


def _parse_stdout_json(stdout: str) -> dict:
    payload = json.loads(stdout)
    hook_output = payload["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PostToolUse"
    return hook_output


# =======================================================================
# A1 -- constants, literal values (Ф1/Ф2/R-1)
# =======================================================================


def test_notes_len_thresholds_literal_values():
    assert je.NOTES_LEN_THRESHOLDS_CHARS == {
        "delegated": 800, "accepted": 800, "rejected": 800,
        "dispatch_skipped": 800, "escalated": 800, "defect_found": 800,
        "decomposable": 800, "calibrated": 15000,
    }
    assert je.MAX_NOTES_LEN_LINES == 5


# =======================================================================
# _collect_notes_len_events -- pure logic, границы обоих порогов (B1-B5)
# =======================================================================


def test_collect_notes_len_events_empty_new_lines():
    assert je._collect_notes_len_events([], []) == []


def test_collect_notes_len_events_short_notes_silent():
    line = _line(event="delegated", notes="short note", task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_exactly_threshold_800_silent():
    # B1
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * threshold
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_threshold_plus_one_801_warns():
    # B2
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    events = je._collect_notes_len_events([line], [])
    assert events == [(1, "delegated", threshold + 1, threshold)]


def test_collect_notes_len_events_threshold_minus_one_799_silent():
    # B3
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold - 1)
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_threshold_applies_per_event_type():
    # Тот же порог 800 у всех событий диспетчерского цикла -- проверим
    # ещё пару, не только delegated.
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["accepted"]
    assert threshold == 800
    notes = "x" * (threshold + 1)
    line = _line(event="accepted", notes=notes, task_id="t-002", model="sonnet",
                 by="opus", witness="ran: ok")
    events = je._collect_notes_len_events([line], [])
    assert events == [(1, "accepted", threshold + 1, threshold)]


def test_collect_notes_len_events_calibrated_real_max_13352_silent():
    # B4 -- реальный живой max замера (2026-08-16), НИЖЕ порога 15000.
    notes = "x" * 13352
    line = _line(event="calibrated", notes=notes)
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_calibrated_exactly_threshold_15000_silent():
    # Собственное усиление сверх буквальной спеки (правило 6а: граница
    # САМА тиха, симметрично порогу 800 -- B1).
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["calibrated"]
    notes = "x" * threshold
    line = _line(event="calibrated", notes=notes)
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_calibrated_15001_warns():
    # B5
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["calibrated"]
    notes = "x" * (threshold + 1)
    line = _line(event="calibrated", notes=notes)
    events = je._collect_notes_len_events([line], [])
    assert events == [(1, "calibrated", threshold + 1, threshold)]


def test_collect_notes_len_events_line_numbering_accounts_for_base_lines():
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    base_lines = ["dummy1", "dummy2"]
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    events = je._collect_notes_len_events([line], base_lines)
    assert events[0][0] == 3  # len(base_lines) + idx(0) + 1


def test_collect_notes_len_events_batch_several_lines_per_event():
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    long_notes = "x" * (threshold + 1)
    lines = [
        _line(event="delegated", notes=long_notes, task_id="t-002", model="sonnet", worker_ref="cli:a"),
        _line(event="delegated", notes="short", task_id="t-003", model="sonnet", worker_ref="cli:b"),
        _line(event="delegated", notes=long_notes, task_id="t-004", model="sonnet", worker_ref="cli:c"),
    ]
    events = je._collect_notes_len_events(lines, [])
    assert [e[0] for e in events] == [1, 3]


# =======================================================================
# _collect_notes_len_events -- пустые/битые (B7-B11, E4-E11)
# =======================================================================


def test_collect_notes_len_events_missing_notes_field_silent():
    # B7
    obj = json.loads(_line(event="delegated", task_id="t-002", model="sonnet"))
    del obj["notes"]
    assert je._collect_notes_len_events([json.dumps(obj)], []) == []


def test_collect_notes_len_events_empty_notes_silent():
    # B8
    line = _line(event="delegated", notes="", task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_whitespace_only_notes_silent():
    # B8
    line = _line(event="delegated", notes="   \n\t  ", task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_non_string_notes_silent():
    # B9 -- int/list/None/dict, len() по не-строке не вызывается (без исключения)
    for bad in (12345, ["a", "list"], None, {"k": "v"}):
        obj = json.loads(_line(event="delegated", task_id="t-002", model="sonnet"))
        obj["notes"] = bad
        assert je._collect_notes_len_events([json.dumps(obj)], []) == []


def test_collect_notes_len_events_malformed_json_line_among_valid_not_raised():
    # B10
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    good_notes = "x" * (threshold + 1)
    good = _line(event="delegated", notes=good_notes, task_id="t-002", model="sonnet")
    events = je._collect_notes_len_events(["{not valid json", good], [])
    assert len(events) == 1
    assert events[0][0] == 2  # second line, first skipped


def test_collect_notes_len_events_not_a_dict_line_skipped():
    assert je._collect_notes_len_events(["[1, 2, 3]"], []) == []


def test_collect_notes_len_events_unknown_event_silent():
    # B11
    line = _line(event="journal_created", notes="x" * 5000)
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_missing_event_field_silent():
    # B11
    obj = json.loads(_line(event="delegated", notes="x" * 5000, task_id="t-002", model="sonnet"))
    del obj["event"]
    assert je._collect_notes_len_events([json.dumps(obj)], []) == []


def test_collect_notes_len_events_event_field_unhashable_type_no_crash():
    # Адверсариальная защита сверх буквальной спеки: event -- НЕ строка,
    # а несравнимый/unhashable тип (список) -- не должно ронять сбор.
    obj = json.loads(_line(event="delegated", notes="x" * 5000, task_id="t-002", model="sonnet"))
    obj["event"] = [1, 2, 3]
    assert je._collect_notes_len_events([json.dumps(obj)], []) == []


# =======================================================================
# _format_notes_len_line -- pure logic, буквальный формат (Ф6)
# =======================================================================


def test_format_notes_len_line_literal():
    line = je._format_notes_len_line((3, "delegated", 950, 800))
    assert line == (
        "NOTES LEN: line 3 event=delegated notes 950 chars > threshold 800 "
        "- an oversized note risks burying load-bearing "
        "facts in prose where they will not be found later; move load-bearing "
        "facts to typed fields / task carrier, keep only a pointer in notes"
    )


def test_format_notes_len_line_is_ascii():
    assert je._format_notes_len_line((1, "accepted", 1000, 800)).isascii()


def test_format_notes_len_line_never_contains_notes_fragment():
    # Ф6: сообщение никогда не несёт фрагмент notes -- проверяем на
    # известном "секретном" маркере, которого в формате быть не может
    # структурно (формат строит строку только из чисел и имени события).
    line = je._format_notes_len_line((1, "calibrated", 20000, 15000))
    assert "chars" in line  # Ф4: слово "chars" присутствует


# =======================================================================
# build_notes_len_segment -- потолок MAX_NOTES_LEN_LINES (B6, E2, правило 6а)
# =======================================================================


def test_build_notes_len_segment_empty_list():
    assert je.build_notes_len_segment([]) == ""


def test_build_notes_len_segment_single_event():
    ev = (1, "delegated", 900, 800)
    assert je.build_notes_len_segment([ev]) == je._format_notes_len_line(ev)


def test_build_notes_len_segment_exactly_five_no_more_suffix():
    events = [(i, "delegated", 900, 800) for i in range(1, je.MAX_NOTES_LEN_LINES + 1)]
    seg = je.build_notes_len_segment(events)
    assert seg.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert "more" not in seg


def test_build_notes_len_segment_six_adds_one_more():
    events = [(i, "delegated", 900, 800) for i in range(1, je.MAX_NOTES_LEN_LINES + 2)]
    seg = je.build_notes_len_segment(events)
    assert seg.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert seg.endswith("; +1 more")


def test_build_notes_len_segment_far_beyond_boundary_counts_correctly():
    events = [(i, "delegated", 900, 800) for i in range(1, je.MAX_NOTES_LEN_LINES + 6)]
    seg = je.build_notes_len_segment(events)
    assert seg.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert seg.endswith("; +5 more")


def test_build_notes_len_segment_ascii_only_param_is_noop():
    ev = (1, "delegated", 900, 800)
    assert je.build_notes_len_segment([ev], ascii_only=True) == je.build_notes_len_segment([ev], ascii_only=False)


# =======================================================================
# combine_context -- keyword-only notes_len_events (R-4, ловушка 2, B18)
# =======================================================================


def test_combine_context_notes_len_only_segment():
    ev = (6, "delegated", 900, 800)
    ctx = je.combine_context([], [], None, None, None, "", notes_len_events=[ev])
    assert ctx == je.build_notes_len_segment([ev])


def test_combine_context_notes_len_keyword_only_enforced():
    # R-4: попытка передать notes_len_events СЕДЬМЫМ позиционным
    # аргументом обязана падать TypeError -- keyword-only барьер держит.
    with pytest.raises(TypeError):
        je.combine_context([], [], None, None, None, "", [(6, "delegated", 900, 800)])


def test_combine_context_six_positional_arg_form_unchanged_trap2_pin():
    # B18 -- буквальный пин ловушки 2: живой тест
    # tools/test_journal_echo_escalation.py:431 вызывает ИМЕННО эту форму
    # (6 позиционных аргументов, fallback_marker="MARKER" ПОЗИЦИОННО) --
    # результат обязан остаться побайтово прежним после добавления
    # notes_len_events.
    ev = (5, "attempt", "t-042", 3)
    ctx = je.combine_context([], [], None, None, [ev], "MARKER")
    assert ctx == je.build_escalation_segment([ev]) + "; MARKER"


def test_combine_context_all_empty_yields_empty_string():
    assert je.combine_context([], [], None, None, None, "", notes_len_events=None) == ""


def test_combine_context_notes_len_between_escalation_and_marker():
    esc_ev = (5, "attempt", "t-042", 3)
    notes_ev = (6, "delegated", 900, 800)
    ctx = je.combine_context([], [], None, None, [esc_ev], "MARKER", notes_len_events=[notes_ev])
    assert ctx == (je.build_escalation_segment([esc_ev]) + "; "
                   + je.build_notes_len_segment([notes_ev]) + "; MARKER")


def test_combine_context_full_order_and_header_literal():
    # B19 -- порядок ВСЕХ семи сегментов: violations первым (литерал
    # заголовка неизменен), notes_len между escalation и marker, marker
    # последним.
    violations = ["v"]
    tier_ev = (2, "mismatch", "fable", {"m": 1})
    witness_ev = ("warn_soft", 3)
    ts_ev = (4, "future", 10.0)
    esc_ev = (5, "attempt", "t-1", 3)
    notes_ev = (6, "delegated", 900, 800)
    ctx = je.combine_context(violations, [tier_ev], [witness_ev], [ts_ev], [esc_ev], "MARKER",
                              notes_len_events=[notes_ev])
    assert ctx.startswith("JOURNAL ECHO: 1 дефект(ов) в новых строках: ")
    assert ctx.endswith("MARKER")
    i_journal = ctx.index("JOURNAL ECHO")
    i_tier = ctx.index("TIER ECHO")
    i_witness = ctx.index("WITNESS ECHO")
    i_ts = ctx.index("TS DRIFT")
    i_esc = ctx.index("R6-ЗЕРКАЛО")
    i_notes = ctx.index("NOTES LEN")
    i_marker = ctx.rindex("MARKER")
    assert i_journal < i_tier < i_witness < i_ts < i_esc < i_notes < i_marker


# =======================================================================
# main() end-to-end -- subprocess-смок
# =======================================================================


def test_echo_noteslen_e2e_800_silent(tmp_path):
    # B1, сквозной путь
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * threshold
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:d1")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_noteslen_e2e_801_warns(tmp_path):
    # B2, сквозной путь
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:d1")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert "NOTES LEN" in ctx
    assert f"notes {threshold + 1} chars" in ctx
    assert f"threshold {threshold}" in ctx


def test_echo_noteslen_e2e_never_blocks_no_permission_decision(tmp_path):
    # B20
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:d1")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "permissionDecision" not in hook_output
    assert "permissionDecision" not in result.stderr
    assert "deny" not in result.stderr


def test_echo_noteslen_non_journal_path_silent(tmp_path):
    # B14
    other_file = tmp_path / "not-a-journal.txt"
    other_file.write_text("irrelevant content", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(other_file))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_noteslen_earlier_uncommitted_long_line_outside_scope_silent(tmp_path):
    # B12 -- регресс-пин класса F-57: строка A (длинная) добавлена РАНЕЕ
    # (не этим вызовом -- уже входит в originalFile), строка B (этим
    # вызовом) -- короткая и чистая -> ноль NOTES LEN событий.
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    line_a = _line(event="delegated", notes="x" * (threshold + 500), task_id="t-002",
                    model="sonnet", worker_ref="cli:a")
    after_call_a = HEAD_TEXT + line_a + "\n"
    line_b = _line(event="delegated", notes="short and clean", task_id="t-003",
                    model="sonnet", worker_ref="cli:b")
    journal_path.write_text(after_call_a + line_b + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=after_call_a))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_noteslen_fallback_disables_layer_entirely(tmp_path):
    # B13 -- Ф5: used_fallback==True -> слой полностью отключён, ноль
    # событий, даже когда notes реально длиннее порога; фолбэк-пометка
    # печатается как и раньше (видна вместе с другим дефектом -- пустая
    # category делает JOURNAL ECHO видимым).
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    bad_line = _line(event="delegated", notes="x" * (threshold + 500), task_id="t-002",
                      model="sonnet", worker_ref="cli:a", category="")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path)  # no original_file -> fallback engaged
    result = _run_hook(payload)
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "NOTES LEN" not in ctx
    assert je.FALLBACK_MARKER_TEXT in ctx


def test_echo_noteslen_giant_notes_one_message_not_bloated(tmp_path):
    # B15 -- адверсариальная: notes 200000 символов -- ровно одно
    # сообщение, сегмент не раздут, фрагмент notes не протекает в текст
    # (Ф6).
    journal_path = _seed_committed_journal(tmp_path)
    marker_inside = "SECRET_MARKER_SHOULD_NOT_LEAK_INTO_MESSAGE"
    notes = marker_inside + ("y" * 200000)
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:giant")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert ctx.count("NOTES LEN") == 1
    assert marker_inside not in ctx
    assert len(ctx) < 1000


def test_echo_noteslen_control_chars_and_cyrillic_notes_no_crash(tmp_path):
    # B16 -- control-chars и кириллица в notes -- stdout валидный JSON,
    # хук не падает ни на каком канале.
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    weird_notes = "\x01\x02\x03" + ("кириллица-контроль " * 60)
    assert len(weird_notes) > threshold
    new_line = _line(event="delegated", notes=weird_notes, task_id="t-002", model="sonnet",
                      worker_ref="cli:weird")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "NOTES LEN" in ctx
    assert ctx.isascii()  # json.dumps(ensure_ascii=True) на стдауте


def test_echo_noteslen_batch_200_lines_100_long_ceiling_and_more_suffix(tmp_path):
    # B17 -- батч 200 строк, 100 длинных -- 5 сообщений + "; +95 more".
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    long_notes = "x" * (threshold + 1)
    lines = []
    for i in range(200):
        notes = long_notes if i % 2 == 0 else "short"
        lines.append(_line(event="delegated", notes=notes, task_id=f"t-{i + 2:03d}",
                            model="sonnet", worker_ref=f"cli:batch-{i}"))
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert ctx.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert "; +95 more" in ctx


def test_echo_noteslen_combined_with_defect_one_context(tmp_path):
    # Форма-дефект (пустая category) + NOTES LEN вместе -- оба сегмента в
    # одном additionalContext, склеены "; " -- тот же комбинированный
    # паттерн, что сиблинги уже проверяют для своих слоёв.
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    bad_line = _line(event="delegated", notes="x" * (threshold + 1), task_id="t-002",
                      model="sonnet", worker_ref="cli:d1", category="")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "NOTES LEN" in ctx
    assert "; NOTES LEN" in ctx
