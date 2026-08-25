"""tools/test_q503_echobase.py -- узел N3 батареи ремедиации t-503
(builder, 2026-08-19, docs/tasks/2026-08-19_q503-remediation-spec.md,
остаток F-57 -- диагностическая фолбэк-метка + отключение TS DRIFT в
фолбэке).

ФОРМА (по образцу tools/test_f61_halfstate.py:73-112, трёхмирный
резолвер): цель разрешается через переменную окружения Q503_TARGET:
 - Q503_TARGET=live -> ВСЕГДА живой tools/journal_echo.py (контр-прогон
   -- ожидаются КРАСНЫЕ дискриминаторы: TS DRIFT молчит в фолбэке на
   сиблинге, но всё ещё эхается на живом; диагностический код причины
   есть в фолбэк-метке на сиблинге, отсутствует на живом -- живой файл
   ещё несёт старую 3-местную сигнатуру _resolve_echo_base, ЛЮБОЙ прямой
   вызов с распаковкой в 4 переменные -- уже AttributeError/ValueError,
   тоже валидный "красный").
 - Q503_TARGET не задан (default) -> сиблинг tools/journal_echo_q503.py,
   если он существует, иначе живой файл (RERUNNABLE, "сильнее
   негативного контроля", тот же дух, что t-469/t-470/F-61 узлы A/B).
После посадки (Lead сливает сиблинг в живой путь, сиблинг удаляется)
обе ветки резолвера сходятся на живом файле -- контр-режима больше не
существует, эта батарея гоняет починенное поведение на живом пути.

Ключи узла N3 (спека, Р1(б)+K15):
 K14 -- одна семантика фолбэка для пяти эхо-слоёв: TIER/WITNESS/
       ESCALATION остаются на кумулятивной фолбэк-базе (шумные-но-не-
       ложные), NOTES LEN (уже было) и TS DRIFT (эта задача) ПОЛНОСТЬЮ
       отключаются при used_fallback == True (единственные два
       корректностно-ложных слоя -- см. секцию "PAYLOAD-SCOPED ECHO
       BASE" -> "Q503 REMEDIATION" в journal_echo_q503.py).
 K15 -- фолбэк-метка становится диагностической: FALLBACK_MARKER_TEXT
       остаётся ПРЕФИКСОМ ДОСЛОВНО, причина дописывается хвостом
       " (reason: <код>)" -- пять кодов, по числу развилок fail-open
       (_extract_original_file/_resolve_echo_base).
 K16 -- валидация (:1901-1903 живого файла) НЕ тронута этой задачей --
       остаётся на НАКОПИТЕЛЬНОЙ HEAD-дифф базе независимо от
       used_fallback эхо-слоёв (см. test_k16_*).
 K17 -- тишина на чистой записи сохраняется даже в фолбэке (метка
       видна ТОЛЬКО когда что-то ещё печатается).

Края (поимённо, спека узла N3):
 - head_text пуст (журнала нет в HEAD) -- поведение названо и запинено
   (test_edge_head_text_missing_no_head_at_all_pinned).
 - tool_name MultiEdit/Bash при записи в журнал -- фолбэк с кодом
   причины REASON_TOOL_OUTSIDE_EDIT_WRITE (два отдельных теста).
 - originalFile == "" (Write нового файла) -- НЕ фолбэк, существующее
   поведение дословно (test_edge_write_new_file_...).
 - не-строгий аппенд -- код причины "not an append" (буквально из
   спеки).
 - чистая запись в фолбэке -- тишина (test_edge_clean_call_..._k17).

Стиль/самодостаточность -- по образцу tools/test_journal_echo_tsdrift.py
(staged/sibling-тест того же класса): хелперы (git-репо, запуск хука,
журнальные строки) продублированы локально, файл НЕ импортирует чужие
тест-модули.

Run: python -m pytest tools/test_q503_echobase.py -q
Контр-прогон: Q503_TARGET=live python -m pytest tools/test_q503_echobase.py -q
"""

import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from wallclock_guard import WALLCLOCK_HARNESS_TIMEOUT  # noqa: E402

Q503_TARGET = os.environ.get("Q503_TARGET", "").strip().lower()


def _resolve_module_path() -> "tuple[Path, bool]":
    """(путь, is_unpatched) -- трёхмирный резолвер по образцу
    tools/test_f61_halfstate.py:73-112 (см. модульный докстринг за
    полное описание трёх миров: контр-режим с сиблингом / RERUNNABLE
    default / пост-посадочный мир без сиблинга)."""
    live = TOOLS_DIR / "journal_echo.py"
    sibling = TOOLS_DIR / "journal_echo_q503.py"
    if Q503_TARGET == "live":
        return live, sibling.exists()
    if sibling.exists():
        return sibling, False
    return live, False


SCRIPT, IS_UNPATCHED = _resolve_module_path()


def _load_module():
    alias = f"q503_echobase_{'sibling' if SCRIPT.name.endswith('_q503.py') else 'live'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


je = _load_module()

# Диагностические коды K15 -- ЛОКАЛЬНЫЕ литералы (сознательно НЕ
# je.REASON_* здесь): на живом файле (контр-режим) этих констант ещё
# нет вовсе -- обращение к отсутствующему атрибуту AttributeError'ит
# раньше проверки самого значения, что тоже "красный", но зашумляет
# причину падения; локальные литералы делают дискриминатор явным
# ("текст X отсутствует/другой" вместо "атрибута нет"). Значения --
# буквально те, что определяет journal_echo_q503.py.REASON_* (сверено
# ниже отдельным пином test_reason_constants_match_module_literals).
REASON_TOOL_OUTSIDE = "tool_name outside Edit/Write"
REASON_NO_TOOL_RESPONSE = "no tool_response"
REASON_NO_ORIGINAL_FILE_KEY = "no originalFile key"
REASON_ORIGINAL_FILE_NOT_STR = "originalFile not a string"
REASON_NOT_AN_APPEND = "not an append"


# =======================================================================
# helpers -- журнальные строки/git-репо (по образцу
# tools/test_journal_echo_tsdrift.py)
# =======================================================================


def _line(ts, event="delegated", agent="builder", category="implementation",
          notes="note", worker_ref="cli:2026-08-19T08:00:00", **kw) -> str:
    obj = {"ts": ts, "event": event, "agent": agent, "category": category,
           "notes": notes, "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(ts="2026-08-19T08:00:00", task_id="t-001", model="sonnet")
HEAD_TEXT = HEAD_LINE + "\n"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def _init_repo(root: Path):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def _write_journal_full(root: Path, text: str) -> Path:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    path = root / "logs" / "routing-log.jsonl"
    path.write_text(text, encoding="utf-8")
    return path


def _seed_committed_journal(root: Path, text: str = HEAD_TEXT) -> Path:
    _init_repo(root)
    path = _write_journal_full(root, text)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    return path


def _seed_uncommitted_repo(root: Path, text: str) -> Path:
    """git-репо БЕЗ единого коммита -- HEAD не существует вовсе (край
    "head_text пуст, журнала нет в HEAD")."""
    _init_repo(root)
    return _write_journal_full(root, text)


_NO_ORIGINAL_FILE = object()  # sentinel -- omit tool_response.originalFile / use default tool_response


def _post_tool_use_payload(file_path, cwd=".", session_id="sess-1", tool_name="Edit",
                            original_file=_NO_ORIGINAL_FILE,
                            tool_response_override=_NO_ORIGINAL_FILE) -> dict:
    if tool_response_override is not _NO_ORIGINAL_FILE:
        tool_response = tool_response_override
    else:
        tool_response = {"filePath": str(file_path), "success": True}
        if original_file is not _NO_ORIGINAL_FILE:
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


def _run_hook(payload, timeout=WALLCLOCK_HARNESS_TIMEOUT, env=None) -> subprocess.CompletedProcess:
    # F-60 (класс A): сетка против зависшего хука, не утверждение о
    # предмете.
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


def _stale_ts() -> str:
    return (dt.datetime.now() - dt.timedelta(seconds=je.TS_STALE_TOLERANCE_SECONDS + 60)).isoformat()


# =======================================================================
# sanity -- локальные REASON_* литералы этого файла совпадают с
# module-level константами сиблинга (не расходятся молча)
# =======================================================================


@pytest.mark.skipif(Q503_TARGET == "live" and IS_UNPATCHED,
                     reason="живой файл ещё не несёт REASON_* констант (контр-режим,"
                            " см. отдельные reason-тесты ниже за красный дискриминатор)")
def test_reason_constants_match_module_literals():
    assert je.REASON_TOOL_OUTSIDE_EDIT_WRITE == REASON_TOOL_OUTSIDE
    assert je.REASON_NO_TOOL_RESPONSE == REASON_NO_TOOL_RESPONSE
    assert je.REASON_NO_ORIGINAL_FILE_KEY == REASON_NO_ORIGINAL_FILE_KEY
    assert je.REASON_ORIGINAL_FILE_NOT_STR == REASON_ORIGINAL_FILE_NOT_STR
    assert je.REASON_NOT_AN_APPEND == REASON_NOT_AN_APPEND


# =======================================================================
# pure logic -- _extract_original_file / _resolve_echo_base, K15 reason
# codes (Q503 API: 2-tuple / 4-tuple return -- UNCONDITIONAL, NOT
# is_unpatched-branched: fails naturally on живом контр-режиме -- ЭТО и
# есть дискриминатор DoD п.2)
# =======================================================================


def test_extract_original_file_reason_tool_outside_edit_write_bash():
    value, reason = je._extract_original_file({"tool_response": {"originalFile": "x"}}, "Bash")
    assert value is je._ORIGINAL_FILE_UNAVAILABLE
    assert reason == REASON_TOOL_OUTSIDE


def test_extract_original_file_reason_tool_outside_edit_write_multiedit():
    value, reason = je._extract_original_file({"tool_response": {"originalFile": "x"}}, "MultiEdit")
    assert value is je._ORIGINAL_FILE_UNAVAILABLE
    assert reason == REASON_TOOL_OUTSIDE


def test_extract_original_file_reason_no_tool_response():
    value, reason = je._extract_original_file({}, "Edit")
    assert value is je._ORIGINAL_FILE_UNAVAILABLE
    assert reason == REASON_NO_TOOL_RESPONSE


def test_extract_original_file_reason_tool_response_not_dict():
    value, reason = je._extract_original_file({"tool_response": None}, "Edit")
    assert value is je._ORIGINAL_FILE_UNAVAILABLE
    assert reason == REASON_NO_TOOL_RESPONSE


def test_extract_original_file_reason_no_original_file_key():
    value, reason = je._extract_original_file({"tool_response": {"filePath": "x"}}, "Edit")
    assert value is je._ORIGINAL_FILE_UNAVAILABLE
    assert reason == REASON_NO_ORIGINAL_FILE_KEY


def test_extract_original_file_reason_original_file_not_str():
    value, reason = je._extract_original_file({"tool_response": {"originalFile": 42}}, "Edit")
    assert value is je._ORIGINAL_FILE_UNAVAILABLE
    assert reason == REASON_ORIGINAL_FILE_NOT_STR


def test_extract_original_file_write_new_file_none_is_not_fallback():
    # originalFile == None (Write создаёт новый файл) -- НЕ фолбэк,
    # reason=None (край спеки: "существующее поведение дословно").
    value, reason = je._extract_original_file({"tool_response": {"originalFile": None}}, "Write")
    assert value == ""
    assert reason is None


def test_resolve_echo_base_primary_path_reason_none():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1", "b1"]
    payload = {"tool_response": {"originalFile": "h1\na1\n"}}
    base, new, fallback, reason = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is False
    assert reason is None
    assert base == ["h1", "a1"]
    assert new == ["b1"]


def test_resolve_echo_base_reason_not_an_append():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1", "b1"]
    payload = {"tool_response": {"originalFile": "different\n"}}
    base, new, fallback, reason = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is True
    assert reason == REASON_NOT_AN_APPEND
    assert base == head_lines


def test_resolve_echo_base_reason_no_original_file_key_propagates():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1"]
    payload = {"tool_response": {}}
    base, new, fallback, reason = je._resolve_echo_base(payload, "Edit", staged_lines, head_lines)
    assert fallback is True
    assert reason == REASON_NO_ORIGINAL_FILE_KEY
    assert new == ["a1"]


def test_resolve_echo_base_reason_tool_outside_propagates():
    head_lines = ["h1"]
    staged_lines = ["h1", "a1"]
    payload = {"tool_response": {"originalFile": "h1\n"}}  # would be valid -- but tool_name overrides
    base, new, fallback, reason = je._resolve_echo_base(payload, "Bash", staged_lines, head_lines)
    assert fallback is True
    assert reason == REASON_TOOL_OUTSIDE


def test_resolve_echo_base_reason_none_write_new_file_empty_original():
    # originalFile == "" (Write, None -> "") -- НЕ фолбэк -- край спеки
    # "существующее поведение дословно" на уровне pure-функции.
    staged_lines = ["a1", "a2"]
    payload = {"tool_response": {"originalFile": None}}
    base, new, fallback, reason = je._resolve_echo_base(payload, "Write", staged_lines, [])
    assert fallback is False
    assert reason is None
    assert base == []
    assert new == ["a1", "a2"]


# =======================================================================
# e2e -- фолбэк-метка диагностическая (K15), TS DRIFT отключён в
# фолбэке (K14) -- ГЛАВНЫЙ дискриминатор DoD п.2
# =======================================================================


def test_e2e_fallback_marker_carries_reason_code_no_tool_response(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(ts=_stale_ts(), task_id="t-002", model="sonnet", category="",
                      notes="defect + stale, fallback path (no tool_response)")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_response_override=None)
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO" in ctx  # валидация (K16) не тронута -- дефект виден на обоих мирах
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_NO_TOOL_RESPONSE})" in ctx
    # K14 дискриминатор: TS DRIFT отключён в фолбэке -- на сиблинге ЭТА
    # строка молчит несмотря на wall-clock-стал ts; на живом файле
    # (контр-режим) TS DRIFT всё ещё эхается -- ассерт красный там.
    assert "TS DRIFT" not in ctx


def test_e2e_fallback_marker_reason_tool_outside_edit_write_bash(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(ts=_stale_ts(), task_id="t-002", model="sonnet", category="",
                      notes="defect + stale, tool_name outside Edit/Write (Bash)")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="Bash")
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_TOOL_OUTSIDE})" in ctx
    assert "TS DRIFT" not in ctx


def test_e2e_fallback_marker_reason_tool_outside_edit_write_multiedit(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(ts=_stale_ts(), task_id="t-002", model="sonnet", category="",
                      notes="defect + stale, tool_name outside Edit/Write (MultiEdit)")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="MultiEdit")
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_TOOL_OUTSIDE})" in ctx
    assert "TS DRIFT" not in ctx


def test_e2e_fallback_marker_reason_not_an_append(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(ts=_stale_ts(), task_id="t-002", model="sonnet", category="",
                      notes="defect + stale, non-tail originalFile")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, original_file="{totally unrelated content}\n")
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_NOT_AN_APPEND})" in ctx
    assert "TS DRIFT" not in ctx


def test_e2e_fallback_marker_reason_original_file_not_str(tmp_path):
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(ts=_stale_ts(), task_id="t-002", model="sonnet", category="",
                      notes="defect + stale, originalFile wrong type")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, original_file=12345)
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_ORIGINAL_FILE_NOT_STR})" in ctx
    assert "TS DRIFT" not in ctx


# =======================================================================
# e2e -- K14, "шумные-но-не-ложные" (TIER/WITNESS/ESCALATION) НЕ
# отключаются в фолбэке -- ESCALATION ECHO смок (форма 1 спеки B6, по
# образцу tools/test_journal_echo_escalation.py:302-315)
# =======================================================================


def test_e2e_escalation_echo_still_fires_in_fallback(tmp_path):
    # K14: ESCALATION ECHO -- ШУМНЫЙ-НО-НЕ-ЛОЖНЫЙ слой -- ПРОДОЛЖАЕТ
    # работать в фолбэке (в отличие от TS DRIFT, отключённого этой
    # задачей): history (2 rejected одной модели без escalated) живёт в
    # COMMITTED HEAD (== фолбэковый base_lines), триггер -- в
    # незакоммиченной delegated-строке attempt=3.
    history = "\n".join([
        _line(ts="2026-08-19T08:00:00", event="delegated", task_id="t-042", model="sonnet", attempt=1),
        _line(ts="2026-08-19T08:05:00", event="rejected", task_id="t-042", model="sonnet", attempt=1,
              by="opus", failure_class="capability"),
        _line(ts="2026-08-19T08:10:00", event="delegated", task_id="t-042", model="sonnet", attempt=2,
              notes="retry"),
        _line(ts="2026-08-19T08:15:00", event="rejected", task_id="t-042", model="sonnet", attempt=2,
              by="opus", failure_class="capability"),
    ]) + "\n"
    journal_path = _seed_committed_journal(tmp_path, text=history)
    new_line = _line(ts="2026-08-19T08:20:00", event="delegated", task_id="t-042", model="sonnet",
                      attempt=3, notes="retry again")
    journal_path.write_text(history + new_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path)  # no originalFile key -> fallback
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "R6-ЗЕРКАЛО" in ctx  # ESCALATION ECHO -- НЕ отключён в фолбэке (K14)
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_NO_ORIGINAL_FILE_KEY})" in ctx


# =======================================================================
# K16 -- валидация остаётся на накопительной HEAD-дифф базе, НЕ тронута
# =======================================================================


def test_k16_validation_stays_on_cumulative_head_diff_base_unaffected_by_fallback(tmp_path):
    # K16: валидация (:1901-1903 живого файла) НЕ тронута этой задачей --
    # старая (не этим вызовом добавленная) невалидная строка ВСЁ ЕЩЁ
    # ловится JOURNAL ECHO даже вне payload-scope этого вызова (в отличие
    # от TIER/WITNESS/TS-DRIFT/ESCALATION/NOTES-LEN, которые видят ТОЛЬКО
    # echo_new_lines) -- накопительная HEAD-дифф база валидации не
    # путается с payload-scoped базой эхо-слоёв, независимо от
    # used_fallback этого вызова (здесь -- primary path, NOT фолбэк).
    journal_path = _seed_committed_journal(tmp_path)
    prior_defect = _line(ts=dt.datetime.now().isoformat(), task_id="t-777", model="sonnet",
                          category="", notes="prior call, invalid category, still uncommitted")
    after_prior_call = HEAD_TEXT + prior_defect + "\n"
    new_line = _line(ts=dt.datetime.now().isoformat(), task_id="t-778", model="sonnet",
                      worker_ref="cli:this-call", notes="this call's own clean line")
    journal_path.write_text(after_prior_call + new_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, original_file=after_prior_call)  # primary path
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    # V-1 (2026-08-25, t-611): тексты валидатора переписаны по правилу
    # трёх — пин обновлён на новую форму, предмет (дефект category
    # виден сквозь эхо-базу) прежний.
    assert "поле 'category' отсутствует/невалидно" in ctx
    assert je.FALLBACK_MARKER_TEXT not in ctx  # primary path -- НЕ фолбэк


# =======================================================================
# Края поимённо (спека узла N3)
# =======================================================================


def test_edge_head_text_missing_no_head_at_all_pinned(tmp_path):
    # "head_text пуст (журнала нет в HEAD)" -- репо БЕЗ единого коммита:
    # `git show HEAD:...` падает (нет HEAD вовсе), _get_head_text() ->
    # None -> head_lines=[] -- ПОВЕДЕНИЕ ЗАПИНЕНО: фолбэк с head_lines=[]
    # трактует ВЕСЬ диск как новые строки (append_ok тривиально True
    # против пустой базы), тот же принцип, что "СТАНДАЛОН-ФОЛБЭК" секции
    # модульного докстринга для validate().
    line = _line(ts=_stale_ts(), task_id="t-001", model="sonnet", category="",
                 notes="no HEAD at all yet, invalid category too (visibility anchor)")
    journal_path = _seed_uncommitted_repo(tmp_path, line + "\n")
    payload = _post_tool_use_payload(journal_path, tool_name="Bash")
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert f"{je.FALLBACK_MARKER_TEXT} (reason: {REASON_TOOL_OUTSIDE})" in ctx
    # TS DRIFT молчит (K14), несмотря на реально старый ts и head_lines
    # пустой -- дискриминатор той же природы, что выше.
    assert "TS DRIFT" not in ctx


def test_edge_write_new_file_original_file_empty_string_not_fallback(tmp_path):
    # "originalFile == '' (Write нового файла) -> существующее поведение
    # дословно": НЕ фолбэк -- метка отсутствует вовсе, TS DRIFT работает
    # как обычно (primary path, не отключён -- K14 говорит только о
    # ФОЛБЭКЕ).
    (tmp_path / "logs").mkdir(parents=True)
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    line = _line(ts=_stale_ts(), task_id="t-001", model="sonnet",
                 notes="brand new journal via Write, stale line")
    journal_path.write_text(line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path, tool_name="Write", original_file=None)
    result = _run_hook(payload)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "TS DRIFT" in ctx  # primary path -- слой активен как раньше
    assert je.FALLBACK_MARKER_TEXT not in ctx  # НЕ фолбэк -- метки нет вовсе


def test_edge_clean_call_in_fallback_stays_silent_k17(tmp_path):
    # K17: полностью чистый вызов остаётся тихим ДАЖЕ в фолбэке -- метка
    # видна ТОЛЬКО когда что-то ещё печатается (то же самое, что
    # tools/test_journal_echo_tsdrift.py:1127
    # test_echo_fallback_marker_not_shown_on_otherwise_clean_call, но
    # добавлено сюда как явный именованный край узла N3, DoD-обязательно).
    journal_path = _seed_committed_journal(tmp_path)
    fresh_ts = dt.datetime.now().isoformat()
    clean_line = _line(ts=fresh_ts, task_id="t-002", model="sonnet", notes="clean, fallback path")
    journal_path.write_text(HEAD_TEXT + clean_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path)  # no originalFile -> fallback engaged
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
