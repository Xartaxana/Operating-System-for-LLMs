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


def _edit_entry(ts, agent_id=None, tool_name="Edit", file_path="tools/x.py"):
    # VG-4: та же форма "edits"-записи, что tools/dod_track.py.build_fact
    # пишет для Edit/Write/MultiEdit/NotebookEdit (см. её докстринг).
    return {"ts": ts, "tool_name": tool_name, "agent_id": agent_id, "file_path": file_path}


def _write_track(root: Path, session_id: str, runs: list, edits: list = None) -> Path:
    # VG-4: edits -- НОВЫЙ опциональный параметр (по умолчанию [] --
    # байт-в-байт прежнее поведение для ВСЕХ существующих вызовов этого
    # хелпера, ни один из которых не передаёт edits).
    track_dir = root / ".claude" / "dod_track"
    track_dir.mkdir(parents=True, exist_ok=True)
    path = track_dir / f"{session_id}.json"
    path.write_text(json.dumps({"edits": edits or [], "runs": runs}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    return path


# =======================================================================
# helpers -- запуск хука
# =======================================================================


_NO_ORIGINAL_FILE = object()  # sentinel -- omit tool_response.originalFile
# entirely (t-277/t-279: exercises the FALLBACK path of
# journal_echo._resolve_echo_base -- identical to the pre-t-279
# HEAD-diff computation). The default preserves every EXISTING call
# site's payload shape byte-for-byte.


def _post_tool_use_payload(file_path, cwd, session_id="sess-1", tool_name="Edit",
                            original_file=_NO_ORIGINAL_FILE) -> dict:
    tool_response = {"filePath": str(file_path), "success": True}
    if original_file is not _NO_ORIGINAL_FILE:
        # t-277/t-279: tool_response.originalFile -- the empirically
        # confirmed field (Edit/Write Zod schemas, see journal_echo.py's
        # "PAYLOAD-SCOPED ECHO BASE" section) carrying the full file
        # content immediately BEFORE this call. Passing it exercises the
        # PRIMARY (non-fallback) payload-scoped base path.
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
# _load_witness_edits -- pure logic (VG-4, mirrors _load_witness_runs
# battery above -- same class of failure, symmetric coverage per R9)
# =======================================================================


def test_load_witness_edits_missing_session_id_none():
    assert we._load_witness_edits(".", None) is None
    assert we._load_witness_edits(".", "") is None


def test_load_witness_edits_missing_file_returns_none(tmp_path):
    assert we._load_witness_edits(str(tmp_path), "no-such-session") is None


def test_load_witness_edits_empty_file_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("   \n", encoding="utf-8")
    assert we._load_witness_edits(str(tmp_path), "sess-1") is None


def test_load_witness_edits_malformed_json_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("{not valid json", encoding="utf-8")
    assert we._load_witness_edits(str(tmp_path), "sess-1") is None


def test_load_witness_edits_not_a_dict_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert we._load_witness_edits(str(tmp_path), "sess-1") is None


def test_load_witness_edits_no_edits_key_returns_none(tmp_path):
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text(json.dumps({"runs": []}), encoding="utf-8")
    assert we._load_witness_edits(str(tmp_path), "sess-1") is None


def test_load_witness_edits_empty_edits_list_returns_empty_list(tmp_path):
    _write_track(tmp_path, "sess-1", runs=[], edits=[])
    assert we._load_witness_edits(str(tmp_path), "sess-1") == []


def test_load_witness_edits_valid_returns_edits(tmp_path):
    edits = [_edit_entry("2026-07-21T10:00:00.000000")]
    _write_track(tmp_path, "sess-1", runs=[], edits=edits)
    assert we._load_witness_edits(str(tmp_path), "sess-1") == edits


# =======================================================================
# _last_edit_ts / _last_green_ts / _detect_staleness -- pure logic (VG-4,
# требуемое усиление (в): "последний зелёный прогон трека датирован
# ПОЗЖЕ последней правки кода в треке")
# =======================================================================


def test_last_edit_ts_empty_list_none():
    assert we._last_edit_ts([]) is None


def test_last_edit_ts_single_entry():
    edits = [_edit_entry("2026-07-21T10:00:00.000000")]
    assert we._last_edit_ts(edits) == "2026-07-21T10:00:00.000000"


def test_last_edit_ts_returns_max_of_several():
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000"),
        _edit_entry("2026-07-21T12:00:00.000000"),
        _edit_entry("2026-07-21T11:00:00.000000"),
    ]
    assert we._last_edit_ts(edits) == "2026-07-21T12:00:00.000000"


def test_last_edit_ts_skips_malformed_entries_without_raising():
    edits = [
        "not a dict",
        {"ts": 12345},  # ts not a string
        {"no_ts_field": True},
        _edit_entry("2026-07-21T10:00:00.000000"),
    ]
    assert we._last_edit_ts(edits) == "2026-07-21T10:00:00.000000"


def test_last_edit_ts_all_malformed_returns_none():
    assert we._last_edit_ts(["not a dict", {"ts": 1}, {}]) is None


def test_last_green_ts_no_green_runs_none():
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest -q", "red")]
    assert we._last_green_ts(runs) is None


def test_last_green_ts_empty_runs_none():
    assert we._last_green_ts([]) is None


def test_last_green_ts_returns_max_of_green_only():
    runs = [
        _run_entry("2026-07-21T09:00:00.000000", "pytest -q", "green"),
        _run_entry("2026-07-21T11:00:00.000000", "pytest -q", "red"),  # later, but red
        _run_entry("2026-07-21T10:00:00.000000", "pytest -q", "green"),
    ]
    assert we._last_green_ts(runs) == "2026-07-21T10:00:00.000000"


def test_detect_staleness_no_edits_none_regardless_of_runs():
    # "если трек не несёт ts правок" -- edits пуст -- сравнивать не с
    # чем, тихо, ДАЖЕ если runs пуст/red/несуществующий зелёный тоже.
    assert we._detect_staleness([], []) is None
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest -q", "red")]
    assert we._detect_staleness(runs, []) is None


def test_detect_staleness_edits_no_green_run_ever_stale():
    edits = [_edit_entry("2026-07-21T10:00:00.000000")]
    runs = [_run_entry("2026-07-21T09:00:00.000000", "pytest -q", "red")]
    result = we._detect_staleness(runs, edits)
    assert result == ("2026-07-21T10:00:00.000000", None)


def test_detect_staleness_edit_after_last_green_stale():
    edits = [_edit_entry("2026-07-21T10:00:01.000000")]
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest -q", "green")]
    result = we._detect_staleness(runs, edits)
    assert result == ("2026-07-21T10:00:01.000000", "2026-07-21T10:00:00.000000")


def test_detect_staleness_green_after_last_edit_silent():
    edits = [_edit_entry("2026-07-21T10:00:00.000000")]
    runs = [_run_entry("2026-07-21T10:00:01.000000", "pytest -q", "green")]
    assert we._detect_staleness(runs, edits) is None


def test_detect_staleness_boundary_equal_ts_silent():
    # Граница правила 6а: правка РОВНО в тот же ts, что последний
    # зелёный -- строгое ">" тихо на равенстве (см. _detect_staleness
    # докстринг), симметрично _detect_ts_drift выше в этом файле.
    same_ts = "2026-07-21T10:00:00.000000"
    edits = [_edit_entry(same_ts)]
    runs = [_run_entry(same_ts, "pytest -q", "green")]
    assert we._detect_staleness(runs, edits) is None


def test_detect_staleness_boundary_one_microsecond_after_is_stale():
    # Та же граница, один шаг ЗА неё -- правка на 1 микросекунду позже
    # зелёного -- уже нарушение.
    edits = [_edit_entry("2026-07-21T10:00:00.000001")]
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest -q", "green")]
    result = we._detect_staleness(runs, edits)
    assert result == ("2026-07-21T10:00:00.000001", "2026-07-21T10:00:00.000000")


# =======================================================================
# _is_doc_only_edit_path / doc-only filtering of _last_edit_ts (VG-4
# attempt 2, критик-BLOCKER attempt 1 -- журнальная/doc-only правка не
# должна сама себя делать "последней правкой кода")
# =======================================================================


def test_is_doc_only_edit_path_jsonl_true():
    assert we._is_doc_only_edit_path("logs/routing-log.jsonl") is True


def test_is_doc_only_edit_path_md_true():
    assert we._is_doc_only_edit_path("docs/SOMETHING.md") is True


def test_is_doc_only_edit_path_json_true():
    assert we._is_doc_only_edit_path("tools/parity_manifest.json") is True


def test_is_doc_only_edit_path_dotfile_true():
    assert we._is_doc_only_edit_path(".gitignore") is True


def test_is_doc_only_edit_path_py_false():
    assert we._is_doc_only_edit_path("tools/journal_echo.py") is False


def test_is_doc_only_edit_path_unknown_conservatively_false():
    # Неизвестный/пустой/не-строковый file_path -- КОНСЕРВАТИВНО НЕ
    # doc-only (fail-safe, зеркало tools/dod_gate.py._is_doc_only_file):
    # отсутствие информации не даёт права на исключение.
    assert we._is_doc_only_edit_path(None) is False
    assert we._is_doc_only_edit_path("") is False
    assert we._is_doc_only_edit_path(123) is False


def test_is_doc_only_edit_path_matches_dod_gate_extension_list_exactly():
    # R9: расхождение списков -- новый класс дефекта пары. Сверка САМИХ
    # констант (не только поведения на образцах) -- ловит дрейф списков
    # даже на РАСШИРЕНИИ, не покрытом остальными тестами этого файла.
    assert we.DOC_ONLY_EXTENSIONS == dod_gate.DOC_ONLY_EXTENSIONS
    assert we.DOC_ONLY_DOTFILES == dod_gate.DOC_ONLY_DOTFILES


def test_last_edit_ts_excludes_jsonl_journal_edit():
    # Живой сценарий блокера: code-правка (.py) + ПОЗЖЕ правка самого
    # журнала (logs/routing-log.jsonl, .jsonl -- doc-only) -- журнальная
    # правка НЕ считается "последней правкой кода".
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000", file_path="tools/x.py"),
        _edit_entry("2026-07-21T10:05:00.000000", file_path="logs/routing-log.jsonl"),
    ]
    assert we._last_edit_ts(edits) == "2026-07-21T10:00:00.000000"


def test_last_edit_ts_excludes_md_edit():
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000", file_path="tools/x.py"),
        _edit_entry("2026-07-21T10:05:00.000000", file_path="docs/NOTES.md"),
    ]
    assert we._last_edit_ts(edits) == "2026-07-21T10:00:00.000000"


def test_last_edit_ts_all_doc_only_returns_none():
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000", file_path="logs/routing-log.jsonl"),
        _edit_entry("2026-07-21T10:05:00.000000", file_path="docs/NOTES.md"),
    ]
    assert we._last_edit_ts(edits) is None


def test_last_edit_ts_counts_py_edit_after_green_boundary_control():
    # Граница-контроль (не убит фильтром): .py-правка ПОСЛЕ doc-only
    # правок -- всё ещё считается, детектор жив.
    edits = [
        _edit_entry("2026-07-21T10:05:00.000000", file_path="logs/routing-log.jsonl"),
        _edit_entry("2026-07-21T10:10:00.000000", file_path="tools/x.py"),
    ]
    assert we._last_edit_ts(edits) == "2026-07-21T10:10:00.000000"


def test_last_edit_ts_missing_file_path_conservatively_counted():
    # Запись без file_path -- КОНСЕРВАТИВНО НЕ doc-only -- учитывается
    # как правка кода (fail-safe по умолчанию).
    edits = [_edit_entry("2026-07-21T10:00:00.000000", file_path=None)]
    assert we._last_edit_ts(edits) == "2026-07-21T10:00:00.000000"


# =======================================================================
# _detect_staleness -- doc-only edits do not falsely trigger (VG-4
# attempt 2, direct regression of the critic's live-scenario finding)
# =======================================================================


def test_detect_staleness_journal_edit_after_green_not_stale():
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000", file_path="tools/x.py"),
        _edit_entry("2026-07-21T10:05:00.000000", file_path="logs/routing-log.jsonl"),
    ]
    runs = [_run_entry("2026-07-21T10:01:00.000000", "pytest tools/x.py -q", "green")]
    assert we._detect_staleness(runs, edits) is None


def test_detect_staleness_md_edit_after_green_not_stale():
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000", file_path="tools/x.py"),
        _edit_entry("2026-07-21T10:05:00.000000", file_path="docs/NOTES.md"),
    ]
    runs = [_run_entry("2026-07-21T10:01:00.000000", "pytest tools/x.py -q", "green")]
    assert we._detect_staleness(runs, edits) is None


def test_detect_staleness_py_edit_after_green_still_stale_boundary_control():
    # Тот же трек, но правка ПОСЛЕ зелёного -- .py, не doc-only -- всё
    # ещё нарушение (детектор не убит фильтром).
    edits = [
        _edit_entry("2026-07-21T10:00:00.000000", file_path="logs/routing-log.jsonl"),
        _edit_entry("2026-07-21T10:10:00.000000", file_path="tools/x.py"),
    ]
    runs = [_run_entry("2026-07-21T10:01:00.000000", "pytest tools/x.py -q", "green")]
    result = we._detect_staleness(runs, edits)
    assert result == ("2026-07-21T10:10:00.000000", "2026-07-21T10:01:00.000000")


def test_detect_staleness_missing_file_path_after_green_still_stale():
    edits = [_edit_entry("2026-07-21T10:10:00.000000", file_path=None)]
    runs = [_run_entry("2026-07-21T10:01:00.000000", "pytest tools/x.py -q", "green")]
    result = we._detect_staleness(runs, edits)
    assert result == ("2026-07-21T10:10:00.000000", "2026-07-21T10:01:00.000000")


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


def test_match_witness_prefix_boundary_full_command_matches():
    # VG-4 DoD 2: witness несёт ПОЛНУЮ (после нормализации) команду
    # трека плюс результат -- граница "совпало".
    runs = [_run_entry("2026-07-21T10:00:00.000000", "python -m pytest tools/ -q", "green")]
    matched, loud = we._match_witness("python -m pytest tools/ -q -> 1298 passed", runs)
    assert matched is True
    assert loud == []


def test_match_witness_prefix_boundary_one_char_short_does_not_match():
    # Та же граница, РАЗОШЛАСЬ на один символ (усечена команда witness'а
    # -- отсутствует последний символ трековой команды) -- НЕ матчится.
    runs = [_run_entry("2026-07-21T10:00:00.000000", "python -m pytest tools/ -q", "green")]
    truncated = "python -m pytest tools/ -"  # "q" отсутствует
    matched, loud = we._match_witness(truncated + " -> 1298 passed", runs)
    assert matched is False
    assert loud == []


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


def test_collect_witness_events_edits_read_once_per_call(tmp_path, monkeypatch):
    # VG-4 симметрия: _load_witness_edits -- ТОЖЕ ленивый кэш, ОДИН раз
    # за вызов (свой независимый флаг от runs_cache, см. докстринг
    # _collect_witness_events).
    _write_track(tmp_path, "sess-1",
                  runs=[_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green")],
                  edits=[_edit_entry("2026-07-21T09:00:00.000000")])
    calls = {"n": 0}
    real = we._load_witness_edits

    def counting(cwd, session_id):
        calls["n"] += 1
        return real(cwd, session_id)
    monkeypatch.setattr(we, "_load_witness_edits", counting)
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    lines = [
        _accepted_line(ts="2026-07-10T08:10:00", task_id="t-001", witness="pytest tools/x.py -q"),
        _accepted_line(ts="2026-07-10T08:11:00", task_id="t-001", witness="pytest tools/x.py -q"),
    ]
    we._collect_witness_events(lines, [], payload)
    assert calls["n"] == 1


# =======================================================================
# _collect_witness_events -- staleness axis (VG-4, требуемое усиление (в))
# =======================================================================


def test_collect_witness_events_stale_no_green_run_ever(tmp_path):
    # Правки есть, зелёного прогона не было НИКОГДА (только red) --
    # warn_stale с last_green_ts=None, ДАЖЕ если команда не матчится
    # (комбинируется с warn_soft для этой же строки).
    _write_track(tmp_path, "sess-1",
                  runs=[_run_entry("2026-07-21T09:00:00.000000", "pytest tools/x.py -q", "red")],
                  edits=[_edit_entry("2026-07-21T10:00:00.000000")])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 1 failed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    kinds = {e[0] for e in events}
    assert "warn_stale" in kinds
    stale = next(e for e in events if e[0] == "warn_stale")
    assert stale == ("warn_stale", 1, "2026-07-21T10:00:00.000000", None)
    # ПЛЮС warn_loud (команда матчится, её последний прогон red) --
    # оси независимы, обе видны для одной строки.
    assert "warn_loud" in kinds


def test_collect_witness_events_stale_edit_after_matched_green_command(tmp_path):
    # Заявленная команда матчится и её СОБСТВЕННЫЙ последний прогон
    # green (п.5 -- тишина по КОМАНДНОЙ оси), но трек в целом несёт
    # более позднюю правку без перепрогона -- staleness срабатывает
    # НЕЗАВИСИМО, ортогонально командному матчингу (VG-4 мотив: конкретная
    # команда честно подтверждена, witness в целом всё равно устарел).
    _write_track(tmp_path, "sess-1",
                  runs=[_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green")],
                  edits=[_edit_entry("2026-07-21T11:00:00.000000")])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == [("warn_stale", 1, "2026-07-21T11:00:00.000000", "2026-07-21T10:00:00.000000")]


def test_collect_witness_events_not_stale_green_after_last_edit(tmp_path):
    # Зелёный прогон ПОЗЖЕ последней правки -- инвариант держится,
    # никакого warn_stale (полная тишина по обеим осям).
    _write_track(tmp_path, "sess-1",
                  runs=[_run_entry("2026-07-21T11:00:00.000000", "pytest tools/x.py -q", "green")],
                  edits=[_edit_entry("2026-07-21T10:00:00.000000")])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_no_edits_in_track_no_staleness_check(tmp_path):
    # Трек без единой правки (edits=[]) -- "если трек не несёт ts правок"
    # -- сравнивать не с чем, staleness тихо пропускается (не warn, не
    # note -- отдельная ось, командный матчинг работает как раньше).
    _write_track(tmp_path, "sess-1",
                  runs=[_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green")],
                  edits=[])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_track_missing_edits_key_no_staleness(tmp_path):
    # Трек-файл битый по форме edits (не список) -- _load_witness_edits
    # отдаёт None -- staleness тихо пропускается (fail-open), не роняет
    # остальную сверку.
    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "sess-1.json").write_text(
        json.dumps({"edits": "not a list",
                    "runs": [_run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "green")]}),
        encoding="utf-8")
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_retro_suppresses_staleness_too(tmp_path):
    # DoD 5 расширен VG-4: retro в notes -> note, БЕЗ warn ЛЮБОГО вида
    # -- ДАЖЕ если трек одновременно и командно противоречит (red), и
    # устарел (правка после зелёного).
    _write_track(tmp_path, "sess-1",
                  runs=[_run_entry("2026-07-21T09:00:00.000000", "pytest tools/x.py -q", "green")],
                  edits=[_edit_entry("2026-07-21T10:00:00.000000")])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed",
                           notes="retroactive acceptance, bounds fixed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    assert events[0][0] == "note"


def test_collect_witness_events_track_empty_note_suppresses_staleness(tmp_path):
    # Трек пуст (runs=[]) -- NOTE_TRACK_EMPTY -- staleness не
    # вычисляется вовсе, ДАЖЕ если файл несёт edits (нечего сравнивать
    # без runs).
    _write_track(tmp_path, "sess-1", runs=[],
                  edits=[_edit_entry("2026-07-21T10:00:00.000000")])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    assert events[0][0] == "note"
    assert events[0][2] == we.NOTE_TRACK_EMPTY


# =======================================================================
# _collect_witness_events -- live-scenario regression (VG-4 attempt 2,
# критик-BLOCKER attempt 1): code-правка -> зелёный прогон -> ПОЗЖЕ
# doc-only правка (журнал/.md) -- witness НЕ должен ложно состариваться
# =======================================================================


def test_collect_witness_events_journal_edit_after_green_no_false_stale(tmp_path):
    # (а) DoD attempt 2: .py-правка -> зелёный прогон -> ПОЗЖЕ Edit
    # logs/routing-log.jsonl (та же строка, что несёт САМ accepted --
    # живой сценарий блокера) -- warn_stale НЕ выдаётся.
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-21T10:01:00.000000",
                                    "pytest tools/x.py -q", "green")],
                 edits=[
                     _edit_entry("2026-07-21T10:00:00.000000", file_path="tools/x.py"),
                     _edit_entry("2026-07-21T10:05:00.000000",
                                 file_path="logs/routing-log.jsonl"),
                 ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_md_edit_after_green_no_false_stale(tmp_path):
    # (б) то же с .md-правкой вместо журнальной.
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-21T10:01:00.000000",
                                    "pytest tools/x.py -q", "green")],
                 edits=[
                     _edit_entry("2026-07-21T10:00:00.000000", file_path="tools/x.py"),
                     _edit_entry("2026-07-21T10:05:00.000000", file_path="docs/NOTES.md"),
                 ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == []


def test_collect_witness_events_py_edit_after_green_still_stale_boundary_control(tmp_path):
    # (в) граница-контроль: .py-правка ПОСЛЕ зелёного (не doc-only) --
    # детектор жив, warn_stale ВЫДАЁТСЯ.
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-21T10:01:00.000000",
                                    "pytest tools/x.py -q", "green")],
                 edits=[
                     _edit_entry("2026-07-21T10:00:00.000000", file_path="logs/routing-log.jsonl"),
                     _edit_entry("2026-07-21T10:10:00.000000", file_path="tools/x.py"),
                 ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == [("warn_stale", 1, "2026-07-21T10:10:00.000000", "2026-07-21T10:01:00.000000")]


def test_collect_witness_events_missing_file_path_edit_after_green_still_stale(tmp_path):
    # (г) правка без file_path ПОСЛЕ зелёного -- консервативный дефолт,
    # НЕ doc-only -- warn_stale ВЫДАЁТСЯ.
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-21T10:01:00.000000",
                                    "pytest tools/x.py -q", "green")],
                 edits=[_edit_entry("2026-07-21T10:10:00.000000", file_path=None)])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness="pytest tools/x.py -q -> 5 passed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert events == [("warn_stale", 1, "2026-07-21T10:10:00.000000", "2026-07-21T10:01:00.000000")]


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
# build_witness_segment / _format_witness_line -- "warn_stale" (VG-4)
# =======================================================================


def test_build_witness_segment_stale_exact_format_with_last_green():
    ev = ("warn_stale", 4, "2026-07-21T11:00:00.000000", "2026-07-21T10:00:00.000000")
    seg = we.build_witness_segment([ev])
    assert seg == (
        "WITNESS ECHO: line 4 track staleness - last code edit at "
        "2026-07-21T11:00:00.000000 is after the last green run "
        "(last green: 2026-07-21T10:00:00.000000) - witness not confirmed "
        "by a green run after the last edit")


def test_build_witness_segment_stale_no_green_run_shows_none_literal():
    ev = ("warn_stale", 4, "2026-07-21T11:00:00.000000", None)
    seg = we.build_witness_segment([ev])
    assert "last green: none" in seg


def test_build_witness_segment_stale_sanitizes_control_chars_in_ts():
    ev = ("warn_stale", 4, "2026-07-21T11:00:00\x00\x1f.000000", "2026-07-21T10:00:00.000000")
    seg = we.build_witness_segment([ev])
    assert "\x00" not in seg
    assert "\x1f" not in seg


def test_build_witness_segment_stale_ascii_only_replaces_non_ascii_ts():
    ev = ("warn_stale", 4, "клод-2026-07-21T11:00:00", "2026-07-21T10:00:00.000000")
    seg = we.build_witness_segment([ev], ascii_only=True)
    assert "клод" not in seg
    assert "?" in seg


def test_build_witness_segment_stale_and_soft_mixed_five_boundary():
    # Потолок общий на все виды -- 3 warn_soft + 2 warn_stale = 5, тишина
    # по "more" (граница правила 6а -- ровно MAX_WITNESS_LINES событий
    # суммарно, независимо от их вида).
    events = ([("warn_soft", i) for i in range(1, 4)] +
              [("warn_stale", i, f"2026-07-21T1{i}:00:00.000000", None) for i in range(4, 6)])
    seg = we.build_witness_segment(events)
    assert seg.count("WITNESS ECHO") == 5
    assert "more" not in seg


def test_build_witness_segment_stale_and_soft_mixed_six_adds_one_more():
    events = ([("warn_soft", i) for i in range(1, 4)] +
              [("warn_stale", i, f"2026-07-21T1{i}:00:00.000000", None) for i in range(4, 7)])
    seg = we.build_witness_segment(events)
    assert seg.count("WITNESS ECHO") == 5
    assert seg.endswith("; +1 more")


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


def test_e2e_witness_payload_scoped_not_reechoed_on_later_unrelated_call(tmp_path):
    # t-277/t-279 DoD item 8 (regression of the tier/witness base): a
    # WITNESS ECHO contradiction reported on call #1 must NOT be
    # re-echoed on a LATER, unrelated call #2 that appends a different
    # clean line -- call #2's original_file already includes call #1's
    # accepted+witness line, so it's out of scope for call #2 (see
    # journal_echo._resolve_echo_base).
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-10T08:05:00.000000", "python -m pytest tools/ gateway/ -q", "red"),
    ])
    contradicting_line = _accepted_line(ts=_fresh_ts(),
                                         witness="python -m pytest tools/ gateway/ -q -> 3 failed",
                                         notes="call #1: contradicting witness")
    after_call_1 = HEAD_TEXT + contradicting_line + "\n"
    journal_path.write_text(after_call_1, encoding="utf-8")
    result1 = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path, original_file=HEAD_TEXT))
    assert result1.returncode == 0
    ctx1 = _parse_stdout_json(result1.stdout)["additionalContext"]
    assert "WITNESS ECHO" in ctx1
    assert "recorded RED" in ctx1

    clean_line = _delegated_line(ts=_fresh_ts(), task_id="t-002", notes="call #2: unrelated clean line")
    journal_path.write_text(after_call_1 + clean_line + "\n", encoding="utf-8")
    result2 = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path, original_file=after_call_1))
    assert result2.returncode == 0
    assert result2.stdout == ""
    assert result2.stderr == ""


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


# =======================================================================
# main() end-to-end -- staleness axis (VG-4, требуемое усиление (в))
# =======================================================================


def test_e2e_stale_edit_after_last_green_loud(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-10T08:00:00.000000",
                                    "python -m pytest tools/ gateway/ -q", "green")],
                 edits=[_edit_entry("2026-07-10T08:04:00.000000")])
    new_line = _accepted_line(witness="python -m pytest tools/ gateway/ -q -> 930 passed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "WITNESS ECHO" in ctx
    assert "track staleness" in ctx
    assert "2026-07-10T08:04:00.000000" in ctx  # last edit ts
    assert ctx in result.stderr


def test_e2e_not_stale_green_after_last_edit_silent(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-10T08:06:00.000000",
                                    "python -m pytest tools/ gateway/ -q", "green")],
                 edits=[_edit_entry("2026-07-10T08:04:00.000000")])
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 930 passed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_retro_suppresses_staleness_warn(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-10T08:00:00.000000",
                                    "python -m pytest tools/ gateway/ -q", "green")],
                 edits=[_edit_entry("2026-07-10T08:04:00.000000")])
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 930 passed",
                               notes="retroactive fix of missed accepted event")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_e2e_staleness_payload_scoped_not_reechoed_on_later_unrelated_call(tmp_path):
    # Ось 10 (docs/SIBLING_MAP.md, D-0069): warn_stale, сообщённый на
    # вызове #1, НЕ должен переоцениваться заново на ПОЗДНЕЙШЕМ,
    # несвязанном вызове #2, добавляющем другую чистую строку -- та же
    # payload-scoped база (_resolve_echo_base), что уже покрыта для
    # warn_loud (см. test_e2e_witness_payload_scoped_not_reechoed_on_later_unrelated_call
    # выше) -- здесь тот же класс инварианта проверен для НОВОГО вида
    # события этой задачи.
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-10T08:00:00.000000",
                                    "python -m pytest tools/ gateway/ -q", "green")],
                 edits=[_edit_entry("2026-07-10T08:04:00.000000")])
    stale_line = _accepted_line(ts=_fresh_ts(),
                                 witness="python -m pytest tools/ gateway/ -q -> 930 passed",
                                 notes="call #1: stale witness")
    after_call_1 = HEAD_TEXT + stale_line + "\n"
    journal_path.write_text(after_call_1, encoding="utf-8")
    result1 = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path, original_file=HEAD_TEXT))
    assert result1.returncode == 0
    ctx1 = _parse_stdout_json(result1.stdout)["additionalContext"]
    assert "track staleness" in ctx1

    clean_line = _delegated_line(ts=_fresh_ts(), task_id="t-002",
                                  notes="call #2: unrelated clean line")
    journal_path.write_text(after_call_1 + clean_line + "\n", encoding="utf-8")
    result2 = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path,
                                                original_file=after_call_1))
    assert result2.returncode == 0
    assert result2.stdout == ""
    assert result2.stderr == ""


def test_e2e_live_scenario_journal_write_itself_not_false_stale(tmp_path):
    # VG-4 attempt 2 -- прямой e2e-регресс живого сценария блокера
    # (критик, диагноз координатора): .py-правка -> зелёный прогон ->
    # ПОЗЖЕ Edit самого logs/routing-log.jsonl (ИМЕННО ТОТ Edit-вызов,
    # что дописывает эту accepted-строку -- живой хук пишет trek-запись
    # ДО или наравне с тем же вызовом, здесь смоделирован явной
    # doc-only-записью с более поздним ts, тот же практический эффект,
    # что вызвал 6/6 ложных срабатываний). Ожидание: main() полностью
    # тих (returncode 0, пустые stdout/stderr) -- НЕ "track staleness".
    journal_path = _seed_committed_journal(tmp_path)
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry("2026-07-10T08:01:00.000000",
                                    "python -m pytest tools/ gateway/ -q", "green")],
                 edits=[
                     _edit_entry("2026-07-10T08:00:00.000000", file_path="tools/journal_echo.py"),
                     _edit_entry("2026-07-10T08:04:00.000000", file_path="logs/routing-log.jsonl"),
                 ])
    new_line = _accepted_line(ts=_fresh_ts(),
                               witness="python -m pytest tools/ gateway/ -q -> 930 passed")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, cwd=tmp_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# =======================================================================
# adversarial battery -- VG-4 DoD 3 (fail-open, existing behaviour intact)
# =======================================================================


def test_collect_witness_events_witness_not_a_string_skipped(tmp_path):
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", "pytest tools/x.py -q", "red"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    for bad_witness in (123, True, ["pytest", "tools/x.py"], {"cmd": "pytest"}, 3.14, None):
        obj = json.loads(_accepted_line())
        obj["witness"] = bad_witness
        events = we._collect_witness_events(_new_lines(json.dumps(obj)), [], payload)
        assert events == [], f"unexpected events for witness={bad_witness!r}"


def test_collect_witness_events_witness_100kb_no_quadratic_blowup(tmp_path):
    # DoD 3: witness 100 КБ -- существующая производительность/сборка не
    # ломается (расширяет DoD 11 узла N2, который тестировал 10К -- это
    # тест ИМЕННО заявленной в спеке VG-4 границы 100 КБ).
    _write_track(tmp_path, "sess-1",
                 runs=[_run_entry(f"2026-07-21T10:{i % 60:02d}:00.000000",
                                    f"pytest tools/test_module_{i}.py -q", "green")
                       for i in range(200)],
                 edits=[_edit_entry("2026-07-21T09:00:00.000000")])
    filler = "x" * 50_000
    witness = f"{filler} manual review only, no command referenced {filler}"
    assert len(witness) > 100_000
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness=witness)
    start = time.perf_counter()
    events = we._collect_witness_events(_new_lines(line), [], payload)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0
    kinds = {e[0] for e in events}
    assert "warn_soft" in kinds  # ни одна из 200 команд не встречается


def test_collect_witness_events_unicode_emoji_in_track_command_survives(tmp_path):
    # DoD 3: юникод/эмодзи в КОМАНДЕ трека -- не роняет сборку/сравнение,
    # доходит до вывода читаемым (raw-канал) и безопасно заменённым
    # (ascii-канал).
    emoji_cmd = "pytest tools/x.py -q  # 🚀 релиз-прогон"
    normalized_cmd = we._normalize_ws(emoji_cmd)  # matched cmd is the GROUPED (normalized) key
    _write_track(tmp_path, "sess-1", [
        _run_entry("2026-07-21T10:00:00.000000", emoji_cmd, "red"),
    ])
    payload = {"session_id": "sess-1", "cwd": str(tmp_path)}
    line = _accepted_line(witness=emoji_cmd + " -> 1 failed")
    events = we._collect_witness_events(_new_lines(line), [], payload)
    assert len(events) == 1
    kind, line_no, cmd, ts = events[0]
    assert kind == "warn_loud"
    assert cmd == normalized_cmd
    raw_seg = we.build_witness_segment(events, ascii_only=False)
    assert "🚀" in raw_seg
    ascii_seg = we.build_witness_segment(events, ascii_only=True)
    assert "🚀" not in ascii_seg
    assert "?" in ascii_seg


def test_detect_staleness_unicode_ts_does_not_raise():
    # DoD 3: юникод/эмодзи в ПОЛЕ ts стороннего (адверсариального) трека
    # -- строковый max() работает на любых строках, не роняет вычисление;
    # sanitize на выводе (см. test_build_witness_segment_stale_*) уже
    # проверяет безопасность отображения.
    edits = [_edit_entry("🚀-not-a-real-ts")]
    runs = [_run_entry("2026-07-21T10:00:00.000000", "pytest -q", "green")]
    result = we._detect_staleness(runs, edits)  # must not raise
    assert result is not None  # "🚀..." > ISO-строка лексикографически -> "stale"
