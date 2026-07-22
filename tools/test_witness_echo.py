"""Тесты WITNESS ECHO -- перекрёстной сверки witness/dod_track, узел N2
волны «валидационный импорт» (docs/tasks/2026-07-21_validation-import.md),
реализованной в tools/journal_echo.py (D-0069 sibling-файл --
tools/journal_echo.py живой, не трогается; Lead ставит на путь при
приёмке).

Стиль -- по образцу tools/test_journal_echo.py (юнит-тесты чистой логики
+ subprocess-смок всего хука через stdin, реальные tmp_path git-репо для
git-режима). Файл САМОДОСТАТОЧЕН (не импортирует test_journal_echo) --
хелперы (git-репо, запуск хука, журнальные строки) продублированы
локально, тот же принцип самодостаточности, что и у самого модуля
journal_echo.py.

Покрывает DoD-батарею спеки узла N2 буквально:
 1. green-совпадение -> молчание.
 2. red-противоречие -> громкий WARN с командой.
 3. несколько прогонов одной команды: red->green (последний green) ->
    молчание; green->red (последний red) -> WARN.
 4. непустой трек без совпадений -> мягкий WARN.
 5. retro в notes -> note, не WARN.
 6. трек отсутствует / пуст / битый JSON -> note, не исключение.
 7. прогон под agent_id субагента совпадает -> учтён (молчание).
 8. нормализация: команда с двойными пробелами/табами в witness ->
    совпадает.
 9. witness без единой команды (прозаический текст) при непустом треке
    -> мягкий WARN.
 10. не-builder accepted / accepted без witness / другие события ->
    сверка не запускается.
 11. очень длинный witness (10К+) и трек в сотни runs -> работает без
    квадратичного взрыва.
 12. событие с witness в НЕновой (старой) строке журнала -> не
    перетриггеривается.
Плюс граница правила 6а -- MAX_WITNESS_LINES (ровно 5 / 6-е "+1 more").

Постановочный доп. (критик-вердикт «годен, две доработки», R10(в)/
D-0043 -- закрываем класс "формула пути трека" целиком, не только в
journal_echo): sync-тест сверяет _witness_track_path staged-
модуля И обе ОСТАЛЬНЫЕ живые копии формулы (tools/dod_gate.py,
tools/main_gate.py -- обе несут СВОЙ собственный module-level
_track_path(cwd, session_id), не импортируют dod_track -- та же
самодостаточность хуков кита) с КАНОНОМ tools/dod_track.py._track_path
на одинаковых образцах (tmp_path, session_id) -- дрейф ЛЮБОЙ из трёх
копий относительно канона роняет этот тест. Плюс формат-тест ts:
dod_track._now_iso -- фиксированная ширина (лексикографика == хронология,
допущение, на которое опирается journal_echo._last_by_ts).

Run from the repo root: python -m pytest tools/test_witness_echo.py -q
"""

import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dod_gate  # noqa: E402 -- канон-сверка формулы пути трека (read-only, не owns)
import dod_track  # noqa: E402 -- КАНОН формулы пути трека + _now_iso (read-only, не owns)
import main_gate  # noqa: E402 -- канон-сверка формулы пути трека (read-only, не owns)

import journal_echo as we  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "journal_echo.py"


# =======================================================================
# helpers -- журнальные строки
# =======================================================================


def _delegated_head_line(task_id="t-001", ts="2026-07-10T08:00:00"):
    obj = {"ts": ts, "event": "delegated", "agent": "builder", "category": "implementation",
           "notes": "seed task", "task_id": task_id, "model": "sonnet",
           "worker_ref": "cli:2026-07-10T08:00:00"}
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _delegated_head_line()
HEAD_TEXT = HEAD_LINE + "\n"


def _fresh_ts(offset_seconds=0):
    """Свежий ts для НОВЫХ строк e2e-тестов тишины (миграция при
    постановке ts-drift слоя t-263: историческая дата в новой строке
    даёт легитимный TS DRIFT STALE и ломает assert полной тишины;
    head-строки остаются историческими -- они не «новые»)."""
    return (dt.datetime.now() + dt.timedelta(seconds=offset_seconds)).isoformat(timespec="seconds")


def _accepted_line(ts="2026-07-10T08:10:00", witness="tests pass", notes="accepted",
                    task_id="t-001", by="fable", agent="builder", **kw):
    obj = {"ts": ts, "event": "accepted", "agent": agent, "category": "implementation",
           "notes": notes, "task_id": task_id, "by": by, "model": "sonnet", "witness": witness}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


def _delegated_line(ts="2026-07-10T08:10:00", task_id="t-002", notes="delegated"):
    obj = {"ts": ts, "event": "delegated", "agent": "builder", "category": "implementation",
           "notes": notes, "task_id": task_id, "model": "sonnet",
           "worker_ref": "cli:" + ts}
    return json.dumps(obj, ensure_ascii=False)


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
# helpers -- dod_track фикстура
# =======================================================================


def _run_entry(ts, command, outcome, agent_id=None, tool_name="Bash"):
    return {"ts": ts, "tool_name": tool_name, "command": command, "outcome": outcome,
            "agent_id": agent_id}


def _write_track(root: Path, session_id: str, runs: list) -> Path:
    track_dir = root / ".claude" / "dod_track"
    track_dir.mkdir(parents=True, exist_ok=True)
    path = track_dir / f"{session_id}.json"
    path.write_text(json.dumps({"edits": [], "runs": runs}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    return path


# =======================================================================
# helpers -- запуск хука
# =======================================================================


def _post_tool_use_payload(file_path, cwd, session_id="sess-1", tool_name="Edit") -> dict:
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


def _run_hook(payload, timeout=10) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
    )


def _parse_stdout_json(stdout: str):
    if not stdout:
        return None
    payload = json.loads(stdout)
    hook_output = payload["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PostToolUse"
    return hook_output


# =======================================================================
# _normalize_ws -- pure logic
# =======================================================================


def test_normalize_ws_collapses_multiple_spaces():
    assert we._normalize_ws("pytest   tools/x.py") == "pytest tools/x.py"


def test_normalize_ws_collapses_tabs_and_newlines():
    assert we._normalize_ws("pytest\ttools/x.py\n-q") == "pytest tools/x.py -q"


def test_normalize_ws_strips_edges():
    assert we._normalize_ws("  pytest -q  ") == "pytest -q"


def test_normalize_ws_not_a_string_returns_empty():
    assert we._normalize_ws(None) == ""
    assert we._normalize_ws(42) == ""


# =======================================================================
# _load_witness_runs -- pure logic (DoD 6: missing/empty/malformed)
# =======================================================================


def test_load_witness_runs_missing_session_id_none():
    assert we._load_witness_runs(".", None) is None
    assert we._load_witness_runs(".", "") is None


def test_load_witness_runs_missing_file_returns_none(tmp_path):
    assert we._load_witness_runs(str(tmp_path), "no-such-session") is None


def test_load_witness_runs_empty_file_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("   \n", encoding="utf-8")
    assert we._load_witness_runs(str(tmp_path), "sess-1") is None


def test_load_witness_runs_malformed_json_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("{not valid json", encoding="utf-8")
    assert we._load_witness_runs(str(tmp_path), "sess-1") is None


def test_load_witness_runs_not_a_dict_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert we._load_witness_runs(str(tmp_path), "sess-1") is None


def test_load_witness_runs_no_runs_key_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text(json.dumps({"edits": []}), encoding="utf-8")
    assert we._load_witness_runs(str(tmp_path), "sess-1") is None


def test_load_witness_runs_empty_runs_list_returns_empty_list(tmp_path):
    _write_track(tmp_path, "sess-1", [])
    result = we._load_witness_runs(str(tmp_path), "sess-1")
    assert result == []


def test_load_witness_runs_valid_returns_runs(tmp_path):
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest tools/ -q", "green")]
    _write_track(tmp_path, "sess-1", runs)
    assert we._load_witness_runs(str(tmp_path), "sess-1") == runs


# =======================================================================
# sync-тест формулы пути трека -- R10(в)/D-0043, класс закрыт целиком:
# КАНОН -- tools/dod_track.py._track_path; ТРИ живые копии сверяются
# против него (journal_echo._witness_track_path -- этот дифф;
# dod_gate._track_path и main_gate._track_path -- существовавшие ДО
# этой задачи, читаем read-only, НЕ owns). Любая из трёх, разошедшаяся
# с каноном, роняет соответствующий параметризованный кейс.
# =======================================================================


_TRACK_PATH_SAMPLES = [
    ("plain", "sess-1"),
    ("dashed-session-id", "a8ed966d-1ca6-d4de-7000"),
    ("agent-style-id", "agent:a8ed966d1ca6d4de7"),
]


def _track_path_cases():
    for label, session_id in _TRACK_PATH_SAMPLES:
        yield ("journal_echo", we._witness_track_path, label, session_id)
        yield ("dod_gate", dod_gate._track_path, label, session_id)
        yield ("main_gate", main_gate._track_path, label, session_id)


@pytest.mark.parametrize(
    "module_name,func,label,session_id",
    list(_track_path_cases()),
    ids=[f"{m}-{lbl}" for m, _, lbl, _ in _track_path_cases()],
)
def test_track_path_formula_matches_canon_across_all_copies(tmp_path, module_name, func,
                                                              label, session_id):
    cwd = str(tmp_path)
    canon = dod_track._track_path(cwd, session_id)
    candidate = func(cwd, session_id)
    assert candidate == canon, (
        f"{module_name}'s _track_path formula drifted from dod_track._track_path (canon) "
        f"for sample cwd={cwd!r} session_id={session_id!r}"
    )


def test_track_path_canon_itself_is_self_consistent(tmp_path):
    # Тривиальный, но явный якорь: канон сверен САМ С СОБОЙ на том же
    # образце -- если когда-нибудь _track_path в dod_track.py перестанет
    # быть детерминированной чистой функцией (напр. добавят скрытое
    # состояние), это тоже всплывёт здесь раньше, чем в кросс-сверке.
    cwd = str(tmp_path)
    session_id = "sess-1"
    assert dod_track._track_path(cwd, session_id) == dod_track._track_path(cwd, session_id)


def test_track_path_empty_cwd_falls_back_to_dot_consistently():
    # Граница формулы (Path(cwd or ".") -- все четыре реализации
    # буквально идентичны в этой ветке): cwd="" -- дефолт "." одинаков
    # у канона и у обеих сверяемых копий.
    session_id = "sess-1"
    canon = dod_track._track_path("", session_id)
    assert we._witness_track_path("", session_id) == canon
    assert dod_gate._track_path("", session_id) == canon
    assert main_gate._track_path("", session_id) == canon


# =======================================================================
# ts-формат -- dod_track._now_iso фиксированной ширины (лексикографика
# == хронология, допущение journal_echo._last_by_ts)
# =======================================================================


_TS_FIXED_WIDTH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}$")


def test_dod_track_now_iso_matches_fixed_width_format():
    sample = dod_track._now_iso()
    assert _TS_FIXED_WIDTH_RE.match(sample), f"unexpected ts shape: {sample!r}"
    assert len(sample) == 26  # YYYY-MM-DDTHH:MM:SS.ffffff -- ширина фиксирована


def test_ts_format_string_ordering_matches_chronological_ordering():
    # Прямая проверка допущения _last_by_ts (строковый sort вместо
    # datetime-парсинга): два момента, один -- на границе секунды/дня
    # (микросекунды 999999 -> 000001 через полночь), отформатированные
    # ТЕМ ЖЕ форматом, что dod_track._now_iso ("%Y-%m-%dT%H:%M:%S.%f")
    # -- строковое сравнение обязано согласовываться с datetime-сравнением.
    fmt = "%Y-%m-%dT%H:%M:%S.%f"
    t1 = dt.datetime(2026, 7, 21, 23, 59, 59, 999999)
    t2 = dt.datetime(2026, 7, 22, 0, 0, 0, 1)
    assert t1 < t2
    s1, s2 = t1.strftime(fmt), t2.strftime(fmt)
    assert s1 < s2
    assert len(s1) == len(s2) == 26


# =======================================================================
# _match_witness -- pure logic (DoD 1-4, 7, 8)
# =======================================================================


def test_match_witness_green_last_no_loud():
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green")]
    matched, loud = we._match_witness("run: pytest tools/x.py -q -> 5 passed", runs)
    assert matched is True
    assert loud == []


def test_match_witness_red_last_is_loud():
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red")]
    matched, loud = we._match_witness("run: pytest tools/x.py -q -> 1 failed", runs)
    assert matched is True
    assert len(loud) == 1
    cmd, ts = loud[0]
    assert cmd == "pytest tools/x.py -q"
    assert ts == "2026-07-21T10:00:00.000000"


def test_match_witness_red_then_green_last_green_silent():
    runs = [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red"),
        _run_entry("2026-07-21T10:05:00.000000", "pytest tools/x.py -q", "green"),
    ]
    matched, loud = we._match_witness("pytest tools/x.py -q", runs)
    assert matched is True
    assert loud == []


def test_match_witness_green_then_red_last_red_loud():
    runs = [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green"),
        _run_entry("2026-07-21T10:05:00.000000", "pytest tools/x.py -q", "red"),
    ]
    matched, loud = we._match_witness("pytest tools/x.py -q", runs)
    assert matched is True
    assert len(loud) == 1
    assert loud[0][1] == "2026-07-21T10:05:00.000000"


def test_match_witness_no_command_found_not_matched():
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green")]
    matched, loud = we._match_witness("a prose paragraph describing manual review", runs)
    assert matched is False
    assert loud == []


def test_match_witness_normalization_double_spaces_and_tabs_in_witness():
    runs = [_run_entry("2026-07-21T10:00:00.000000", "python -m pytest tools/ -q", "green")]
    witness = "control run:\tpython  -m  pytest\ttools/  -q  -> 900 passed"
    matched, loud = we._match_witness(witness, runs)
    assert matched is True
    assert loud == []


def test_match_witness_subagent_agent_id_counts():
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green",
                        agent_id="a8ed966d1ca6d4de7")]
    matched, loud = we._match_witness("pytest tools/x.py -q -> 5 passed", runs)
    assert matched is True
    assert loud == []


def test_match_witness_mixed_agent_ids_all_counted():
    runs = [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red", agent_id=None),
        _run_entry("2026-07-21T10:05:00.000000", "pytest tools/x.py -q", "green",
                   agent_id="sub-1"),
    ]
    matched, loud = we._match_witness("pytest tools/x.py -q", runs)
    assert matched is True
    assert loud == []  # last (by ts) among BOTH agent_ids is green


# =======================================================================
# _collect_witness_events -- pure logic (full lattice, DoD 1-6, 9, 10, 12)
# =======================================================================


def _new_lines(*lines):
    return list(lines)


def test_collect_witness_events_green_match_silent(tmp_path):
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_red_contradiction_loud(tmp_path):
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 1 failed (fixed by hand after)")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    kind, line_no, cmd, ts = events[0]
    assert kind == "warn_loud"
    assert line_no == 1
    assert cmd == "pytest tools/x.py -q"


def test_collect_witness_events_no_match_soft_warn(tmp_path):
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="reviewed manually, looks correct")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    assert events[0][0] == "warn_soft"
    assert events[0][1] == 1


def test_collect_witness_events_prose_witness_no_commands_soft_warn(tmp_path):
    # DoD 9: witness -- чисто прозаический текст, трек непуст -> мягкий WARN.
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "python -m pytest tools/ gateway/ -q", "green"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="All checks look good, reviewed the diff by eye and it is fine.")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    assert events[0][0] == "warn_soft"


def test_collect_witness_events_retro_note_no_warn(tmp_path):
    # DoD 5: retro в notes -> note, БЕЗ warn, ДАЖЕ если трек противоречит.
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 1 failed",
                           notes="retroactive acceptance, bounds fixed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    kind, line_no, text = events[0]
    assert kind == "note"
    assert text == we.NOTE_RETRO


def test_collect_witness_events_missing_track_note(tmp_path):
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}  # no track file written
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    kind, line_no, text = events[0]
    assert kind == "note"
    assert text == we.NOTE_TRACK_EMPTY


def test_collect_witness_events_empty_track_file_note(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("", encoding="utf-8")
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events[0][0] == "note"
    assert events[0][2] == we.NOTE_TRACK_EMPTY


def test_collect_witness_events_malformed_json_track_note(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("{not valid", encoding="utf-8")
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events[0][0] == "note"
    assert events[0][2] == we.NOTE_TRACK_EMPTY


def test_collect_witness_events_empty_runs_list_note(tmp_path):
    # runs=[] -- валидный JSON, валидный трек, но сравнивать не с чем.
    _write_track(tmp_path, "sess-1", [])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events[0][0] == "note"
    assert events[0][2] == we.NOTE_TRACK_EMPTY


def test_collect_witness_events_no_exception_on_bad_track(tmp_path):
    # DoD 6: битый трек -- НЕ исключение (сама сборка не падает).
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("not json at all {{{", encoding="utf-8")
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)  # must not raise
    assert events[0][0] == "note"


def test_collect_witness_events_non_builder_agent_skipped(tmp_path):
    # DoD 10: не-builder accepted -> сверка не запускается.
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 1 failed", agent="critic")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_missing_witness_skipped(tmp_path):
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    obj = json.loads(_accepted_line())
    del obj["witness"]
    events = we._collect_witness_events(_new_lines(json.dumps(obj)), [], payload)
    assert events == []


def test_collect_witness_events_empty_witness_skipped(tmp_path):
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="   ")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_other_event_skipped(tmp_path):
    # DoD 10: событие != accepted -> сверка не запускается вовсе (несмотря
    # на то, что 'delegated' формально мог бы нести поле witness).
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    obj = json.loads(_delegated_line())
    obj["witness"] = "pytest tools/x.py -q -> 1 failed"
    events = we._collect_witness_events(_new_lines(json.dumps(obj)), [], payload)
    assert events == []


def test_collect_witness_events_malformed_json_line_skipped_not_raised(tmp_path):
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    events = we._collect_witness_events(_new_lines("{not valid json"), [], payload)
    assert events == []


def test_collect_witness_events_line_numbering_accounts_for_head_lines(tmp_path):
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    head_lines = ["dummy 1", "dummy 2"]
    line = _accepted_line(witness="reviewed by eye, no matching command")
    events = we._collect_witness_events(_new_lines(line), head_lines, payload)
    assert events[0][1] == 3  # len(head_lines) + idx(0) + 1


def test_collect_witness_events_track_read_once_per_call(tmp_path, monkeypatch):
    # Ленивая загрузка ОДИН раз за вызов (докстринг _collect_witness_events):
    # две accepted-строки -> _load_witness_runs зовётся ровно один раз.
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green"),
    ])
    calls = {"n": 0}
    real = we._load_witness_runs

    def counting(cwd, session_id):
        calls["n"] += 1
        return real(cwd, session_id)
    monkeypatch.setattr(we, "_load_witness_runs", counting)
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    lines = [
        _accepted_line(ts="2026-07-10T08:10:00", task_id="t-001", witness="pytest tools/x.py -q"),
        _accepted_line(ts="2026-07-10T08:11:00", task_id="t-001", witness="pytest tools/x.py -q"),
    ]
    we._collect_witness_events(lines, [], payload)
    assert calls["n"] == 1


# =======================================================================
# performance -- DoD 11 (10K+ witness, сотни runs, без квадратичного взрыва)
# =======================================================================


def test_collect_witness_events_large_witness_and_track_performs(tmp_path):
    runs = [
        _run_entry(f"2026-07-21T10:{i % 60:02d}:00.000000", f"pytest tools/test_module_{i}.py -q",
                   "green" if i % 3 else "red", agent_id=(f"sub-{i}" if i % 5 == 0 else None))
        for i in range(300)
    ]
    _write_track(tmp_path, "sess-1", runs)
    filler = "x" * 10_000
    witness = f"{filler} manual review only, no command referenced {filler}"
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness=witness)
    start = time.perf_counter()
    events = we._collect_witness_events(_new_lines(line), [], payload)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0
    assert len(events) == 1
    assert events[0][0] == "warn_soft"  # ни одна из 300 команд не встречается в witness


def test_collect_witness_events_large_witness_finds_embedded_command(tmp_path):
    runs = [
        _run_entry(f"2026-07-21T10:{i % 60:02d}:00.000000", f"pytest tools/test_module_{i}.py -q",
                   "green", agent_id=None)
        for i in range(300)
    ]
    _write_track(tmp_path, "sess-1", runs)
    filler = "x" * 10_000
    witness = f"{filler} ran pytest tools/test_module_150.py -q -> 3 passed {filler}"
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness=witness)
    start = time.perf_counter()
    events = we._collect_witness_events(_new_lines(line), [], payload)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0
    assert events == []  # matched, green -> silence


# =======================================================================
# build_witness_segment / _format_witness_line -- pure logic, границы (6а)
# =======================================================================


def test_build_witness_segment_empty_list():
    assert we.build_witness_segment([]) == ""


def test_build_witness_segment_notes_excluded_from_output():
    assert we.build_witness_segment([("note", 1, "whatever")]) == ""


def test_build_witness_segment_loud_exact_format():
    ev = ("warn_loud", 2, "pytest tools/x.py -q", "2026-07-21T10:00:00.000000")
    seg = we.build_witness_segment([ev])
    assert seg == ("WITNESS ECHO: line 2 contradiction - command 'pytest tools/x.py -q' "
                    "recorded RED in session track (last red at 2026-07-21T10:00:00.000000)")


def test_build_witness_segment_loud_sanitizes_ts_control_chars():
    # Критик-хардининг (постановочный доп.): ts -- ТОЖЕ динамика (значение
    # из стороннего JSON-трека, не литерал модуля), обязана проходить
    # sanitize симметрично с cmd -- control-chars в ts вырезаются, как в
    # command (см. _raw_sanitize/_ascii_sanitize).
    ev = ("warn_loud", 2, "pytest tools/x.py -q", "2026-07-21T10:00:00\x00\x1f.000000")
    seg = we.build_witness_segment([ev])
    assert "\x00" not in seg
    assert "\x1f" not in seg
    assert "2026-07-21T10:00:00.000000" in seg


def test_build_witness_segment_loud_ts_ascii_only_replaces_non_ascii():
    ev = ("warn_loud", 2, "pytest tools/x.py -q", "клод-2026-07-21T10:00:00")
    seg = we.build_witness_segment([ev], ascii_only=True)
    assert "клод" not in seg
    assert "?" in seg


def test_build_witness_segment_loud_ts_truncated_at_max_message_len():
    giant_ts = "9" * (we.MAX_MESSAGE_LEN + 50)
    ev = ("warn_loud", 2, "pytest tools/x.py -q", giant_ts)
    seg = we.build_witness_segment([ev])
    assert ("9" * we.MAX_MESSAGE_LEN) in seg
    assert ("9" * (we.MAX_MESSAGE_LEN + 1)) not in seg


def test_build_witness_segment_soft_exact_format():
    ev = ("warn_soft", 3)
    seg = we.build_witness_segment([ev])
    assert seg == ("WITNESS ECHO: line 3 witness command(s) not observed in session track "
                    "(batch/cross-session/retro acceptance legitimate - verify manually)")


def test_build_witness_segment_exactly_five_boundary_no_more_suffix():
    events = [("warn_soft", i) for i in range(1, 6)]
    seg = we.build_witness_segment(events)
    assert seg.count("WITNESS ECHO") == 5
    assert "more" not in seg


def test_build_witness_segment_beyond_boundary_six_adds_one_more():
    events = [("warn_soft", i) for i in range(1, 7)]
    seg = we.build_witness_segment(events)
    assert seg.count("WITNESS ECHO") == 5
    assert seg.endswith("; +1 more")


def test_build_witness_segment_ascii_only_true_sanitizes_command():
    ev = ("warn_loud", 2, "команда с кириллицей", "2026-07-21T10:00:00.000000")
    seg = we.build_witness_segment([ev], ascii_only=True)
    assert "команда с кириллицей" not in seg
    assert "?" in seg


def test_build_witness_segment_ascii_only_false_keeps_command_readable():
    ev = ("warn_loud", 2, "команда с кириллицей", "2026-07-21T10:00:00.000000")
    seg = we.build_witness_segment([ev], ascii_only=False)
    assert "команда с кириллицей" in seg


# =======================================================================
# combine_context -- extended with witness_events (backward compatibility)
# =======================================================================


def test_combine_context_two_arg_call_unchanged():
    # Старая 2-позиционная форма (test_journal_echo.py) -- witness_events
    # по умолчанию None -> поведение идентично дотиерной сигнатуре.
    violations = ["line 2: msg one"]
    assert we.combine_context(violations, []) == we.build_context(violations)


def test_combine_context_witness_only_no_violations_no_tier():
    ev = ("warn_soft", 2)
    ctx = we.combine_context([], [], [ev])
    assert ctx == we.build_witness_segment([ev])
    assert "JOURNAL ECHO" not in ctx
    assert "TIER ECHO" not in ctx


def test_combine_context_all_three_segments_joined():
    violations = ["line 2: msg"]
    tier_ev = (3, "mismatch", "fable", {"claude-opus-4-8": 1})
    witness_ev = ("warn_soft", 4)
    ctx = we.combine_context(violations, [tier_ev], [witness_ev])
    expected = (we.build_context(violations) + "; " + we.build_tier_segment([tier_ev]) +
                "; " + we.build_witness_segment([witness_ev]))
    assert ctx == expected


def test_combine_context_witness_none_defaults_to_empty():
    assert we.combine_context([], [], None) == ""


# =======================================================================
# main() end-to-end -- subprocess-смок (DoD 1, 2, 5, 6, 12 + wiring)
# =======================================================================


def test_e2e_green_witness_silent(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "green"),
    ])
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 930 passed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_red_witness_contradiction_loud_warn(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "red"),
    ])
    new_line = _accepted_line(witness="python -m pytest tools/ gateway/ -q -> 3 failed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "WITNESS ECHO" in ctx
    assert "recorded RED" in ctx
    assert "python -m pytest tools/ gateway/ -q" in ctx
    assert ctx in result.stderr  # ASCII-only, идентичен на обоих каналах


def test_e2e_retro_no_warn_even_with_red_track(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "red"),
    ])
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 3 failed",
                               notes="retroactive fix of missed accepted event")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_missing_track_silent_note_not_exception(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    # НЕТ .claude/dod_track вовсе.
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 930 passed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_malformed_track_silent_note_not_exception(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("{not valid json at all", encoding="utf-8")
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 930 passed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_no_match_soft_warn(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "green"),
    ])
    new_line = _accepted_line(witness="reviewed by eye, everything checks out")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "WITNESS ECHO" in ctx
    assert "not observed in session track" in ctx


def test_e2e_old_line_witness_not_retriggered(tmp_path):
    # DoD 12: witness в СТАРОЙ (HEAD, уже committed) строке -- новая
    # (чистая, не accepted) строка добавляется, но старый accepted не
    # переоценивается заново (та же "новые строки" механика, что живой
    # journal_echo.py уже использует для TIER ECHO/дефектов формы).
    old_accepted = _accepted_line(ts="2026-07-10T08:05:00", task_id="t-001",
                                   witness="python -m pytest tools/ gateway/ -q -> 3 failed")
    head_text = HEAD_TEXT + old_accepted + "\n"
    journal_path = _seed_committed_journal(tmp_path, text=head_text)
    # Трек существует и ПРОТИВОРЕЧИТ старому witness (red) -- если бы
    # механика перетриггерилась на старую строку, здесь был бы громкий WARN.
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:04:00.000000", "python -m pytest tools/ gateway/ -q", "red"),
    ])
    new_clean_line = _delegated_line(ts=_fresh_ts(), task_id="t-002",
                                      notes="unrelated new clean line")
    journal_path.write_text(head_text + new_clean_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_non_builder_accepted_no_witness_check(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "red"),
    ])
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 3 failed",
                               agent="critic")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_existing_journal_echo_defect_and_witness_warn_together(tmp_path):
    # Регресс-проверка: JOURNAL ECHO (дефект формы) и WITNESS ECHO
    # склеиваются в одном additionalContext (спека п.3), существующая
    # механика дефектов формы НЕ сломана добавлением WITNESS ECHO.
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "red"),
    ])
    bad_line = _accepted_line(witness="python -m pytest tools/ gateway/ -q -> 3 failed",
                               category="")  # дефект формы: category пуст
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов)" in ctx
    assert "'category'" in ctx
    assert "WITNESS ECHO" in ctx
    assert "; WITNESS ECHO" in ctx
