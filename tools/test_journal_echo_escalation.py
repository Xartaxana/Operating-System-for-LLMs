"""Тесты ESCALATION ECHO-слоя (batch B6, задача 1 -- R6-эскалация
машинный страж на пути записи, workstream 3 / Phase 4 D-0098), реализован
в tools/journal_echo.py (живой хук -- см. его секцию "ESCALATION ECHO"
за полный разбор дизайна).

ДЫРА (R6, CLAUDE.md): "два rejected одного task_id на одном ярусе ->
эскалация ОБЯЗАТЕЛЬНА" не имела машинного слоя на пути записи -- третий
ретрай тем же ярусом ничто не останавливало (ловил только недельный чек
3, постфактум). Этот файл проверяет WARN-слой (никогда не блок).

Стиль -- по образцу tools/test_journal_echo_tsdrift.py (staged/sibling
эхо-слой того же класса): pure-логика (_escalation_group_unsatisfied,
_check_delegated_retry, _collect_escalation_events, _format_escalation_line,
build_escalation_segment) + subprocess-смок main() через реальные
tmp_path git-репо. Хелперы (git-репо, запуск хука, журнальные строки)
продублированы локально (та же самодостаточность-предпочтение, что
tools/test_journal_echo_tsdrift.py уже объясняет).

Покрывает DoD спеки буквально:
 1. форма 1: delegated attempt>=3 БЕЗ escalated выше -> WARN.
 2. форма 2: delegated БЕЗ attempt, >=2 rejected одинаковой model выше,
    БЕЗ escalated после второго -> WARN.
 3. никогда не блокирует (returncode всегда 0, без permissionDecision).
Легальные случаи БЕЗ WARN (правило 6а -- обе стороны границы):
 4. attempt>=3 при существующем escalated выше того же task_id.
 5. attempt=2 (ровно порог-1) -- тихо; attempt=3 (порог) -- warn.
 6. критик-вход (agent="critic") -- не ретрай.
 7. replaces_worker-токен в notes -- не ретрай.
 8. attempt>=3 при rejected на РАЗНЫХ ярусах (разные model).
Адверсариальные (спека, буквально):
 9. строка-не-JSON среди новых -- не роняет остальные.
 10. пустой payload (new_lines=[]) -- тихо.
Граница MAX_ESCALATION_LINES (правило 6а):
 11. ровно 5 -- без "+more"; 6 -- "+1 more".

Run from the repo root: python -m pytest tools/test_journal_echo_escalation.py -q
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal_echo as je  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "journal_echo.py"


def _fresh_ts() -> str:
    # Свежий (относительно РЕАЛЬНЫХ часов, момент вызова) ts -- та же
    # находка, что tools/test_journal_echo_tsdrift.py._fresh_ts уже
    # документирует: фиксированная историческая ts-фикстура В НОВЫХ
    # строках журнала (за пределами HEAD) ловится ЖИВЫМ TS DRIFT ECHO-
    # слоем как STALE (порог 30 минут) -- ломает assert'ы, ожидающие
    # ПОЛНУЮ тишину/точное совпадение additionalContext. Каждый вызов
    # _line() ниже без явного ts берёт СВЕЖЕЕ значение.
    return datetime.datetime.now().isoformat(timespec="seconds")


# =======================================================================
# helpers -- журнальные строки (по образцу test_journal_echo_tsdrift._line)
# =======================================================================


def _line(event="delegated", ts=None, agent="builder",
          category="implementation", notes="note",
          worker_ref="cli:2026-07-24T08:00:00", **kw) -> str:
    obj = {"ts": ts if ts is not None else _fresh_ts(), "event": event, "agent": agent,
           "category": category, "notes": notes, "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(event="delegated", ts="2026-07-24T08:00:00", task_id="t-001", model="sonnet")
HEAD_TEXT = HEAD_LINE + "\n"


# =======================================================================
# helpers -- real git repos (по образцу test_journal_echo_tsdrift)
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
# convention as test_journal_echo_tsdrift.py's sentinel of the same name).


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
# _escalation_group_unsatisfied -- pure logic
# =======================================================================


def test_group_unsatisfied_no_rejected_false():
    assert je._escalation_group_unsatisfied([], []) is False


def test_group_unsatisfied_single_reject_false():
    assert je._escalation_group_unsatisfied([(1, "sonnet")], []) is False


def test_group_unsatisfied_two_same_model_no_escalated_true():
    assert je._escalation_group_unsatisfied([(1, "sonnet"), (2, "sonnet")], []) is True


def test_group_unsatisfied_two_same_model_escalated_after_second_false():
    assert je._escalation_group_unsatisfied([(1, "sonnet"), (2, "sonnet")], [3]) is False


def test_group_unsatisfied_escalated_before_second_still_true():
    # escalated at pos 1 is BEFORE the second reject at pos 2 -- doesn't count.
    assert je._escalation_group_unsatisfied([(1, "sonnet"), (2, "sonnet")], [1]) is True


def test_group_unsatisfied_two_different_models_false():
    # "rejected на разных ярусах" -- no model reaches count 2.
    assert je._escalation_group_unsatisfied([(1, "sonnet"), (2, "opus")], []) is False


def test_group_unsatisfied_three_rejects_two_matching_one_odd_true():
    assert je._escalation_group_unsatisfied([(1, "sonnet"), (2, "opus"), (3, "sonnet")], []) is True


# =======================================================================
# _check_delegated_retry -- pure logic (excluded triggers, form gating)
# =======================================================================


def _state_with(task_id, rejected=(), escalated=()):
    return {task_id: {"rejected": list(rejected), "escalated": list(escalated)}}


def test_check_delegated_retry_attempt_3_no_escalated_warns():
    obj = {"agent": "builder", "task_id": "t-042", "attempt": 3, "notes": "retry"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "sonnet")])
    result = je._check_delegated_retry(obj, state)
    assert result is not None
    trigger, task_id, attempt_display = result
    assert (trigger, task_id, attempt_display) == ("attempt", "t-042", 3)


def test_check_delegated_retry_attempt_2_below_threshold_silent():
    obj = {"agent": "builder", "task_id": "t-042", "attempt": 2, "notes": "retry"}
    state = _state_with("t-042", rejected=[(1, "sonnet")])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_attempt_3_escalated_above_silent():
    obj = {"agent": "builder", "task_id": "t-042", "attempt": 3, "notes": "retry"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "sonnet")], escalated=[3])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_attempt_3_different_tiers_silent():
    obj = {"agent": "builder", "task_id": "t-042", "attempt": 3, "notes": "retry"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "opus")])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_no_attempt_two_same_model_no_escalated_warns():
    obj = {"agent": "builder", "task_id": "t-042", "notes": "forgot attempt"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "sonnet")])
    result = je._check_delegated_retry(obj, state)
    assert result is not None
    trigger, task_id, attempt_display = result
    assert trigger == "no_attempt"
    assert task_id == "t-042"
    assert attempt_display == 3  # len(rejected) + 1


def test_check_delegated_retry_no_attempt_one_reject_only_silent():
    obj = {"agent": "builder", "task_id": "t-042", "notes": "only one reject so far"}
    state = _state_with("t-042", rejected=[(1, "sonnet")])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_no_attempt_two_different_models_silent():
    obj = {"agent": "builder", "task_id": "t-042", "notes": "different tiers"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "opus")])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_critic_entry_excluded():
    obj = {"agent": "critic", "task_id": "t-042", "attempt": 3, "notes": "critic entry"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "sonnet")])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_replaces_worker_excluded():
    obj = {"agent": "builder", "task_id": "t-042", "attempt": 3,
           "notes": "replaces_worker:agent:dead-worker-1"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "sonnet")])
    assert je._check_delegated_retry(obj, state) is None


def test_check_delegated_retry_missing_task_id_silent():
    obj = {"agent": "builder", "attempt": 3, "notes": "no task_id"}
    assert je._check_delegated_retry(obj, {}) is None


def test_check_delegated_retry_bool_attempt_not_treated_as_number():
    # Адверсариальная защита: bool -- подкласс int в Python, attempt=True
    # НЕ должен трактоваться как число (ни форма 1, ни форма 2 -- т.к.
    # attempt ПРИСУТСТВУЕТ, значит "БЕЗ attempt" тоже не подходит).
    obj = {"agent": "builder", "task_id": "t-042", "attempt": True, "notes": "weird"}
    state = _state_with("t-042", rejected=[(1, "sonnet"), (2, "sonnet")])
    assert je._check_delegated_retry(obj, state) is None


# =======================================================================
# _collect_escalation_events -- pure logic (payload-scoped trigger,
# full-history context, single-pass state accumulation)
# =======================================================================


def test_collect_escalation_events_empty_new_lines():
    assert je._collect_escalation_events([], []) == []


def test_collect_escalation_events_form1_history_in_base_lines():
    base_lines = [
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=1),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=2, notes="retry"),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
    ]
    new_line = _line(event="delegated", task_id="t-042", model="sonnet", attempt=3, notes="retry again")
    events = je._collect_escalation_events([new_line], base_lines)
    assert len(events) == 1
    line_no, trigger, task_id, attempt_display = events[0]
    assert (line_no, trigger, task_id, attempt_display) == (5, "attempt", "t-042", 3)


def test_collect_escalation_events_form1_escalated_in_base_silent():
    base_lines = [
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=1),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=2, notes="retry"),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="escalated", task_id="t-042", model="opus"),
    ]
    new_line = _line(event="delegated", task_id="t-042", model="opus", attempt=3, notes="escalated retry")
    assert je._collect_escalation_events([new_line], base_lines) == []


def test_collect_escalation_events_within_same_batch_state_accumulates():
    # DoD: "историю файла читать для контекста можно" -- rejected/
    # escalated ВНУТРИ ЭТОГО ЖЕ батча (несколько новых строк одним
    # tool-вызовом) тоже должны учитываться в state для ПОСЛЕДУЮЩИХ
    # строк того же батча.
    base_lines = [
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=1),
    ]
    new_lines = [
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=2, notes="retry"),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=3, notes="retry again"),
    ]
    events = je._collect_escalation_events(new_lines, base_lines)
    assert len(events) == 1
    line_no, trigger, task_id, attempt_display = events[0]
    assert (line_no, trigger) == (5, "attempt")  # base(1) + idx(3) + 1


def test_collect_escalation_events_malformed_json_line_skipped_not_raised():
    good_new = _line(event="delegated", task_id="t-042", model="sonnet", attempt=3)
    events = je._collect_escalation_events(["{not valid json", good_new], [
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=1),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-042", model="sonnet", attempt=2, notes="retry"),
        _line(event="rejected", task_id="t-042", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
    ])
    assert len(events) == 1
    assert events[0][0] == 6  # base(4) + idx(1) + 1


def test_collect_escalation_events_not_a_dict_line_skipped():
    assert je._collect_escalation_events(["[1, 2, 3]"], []) == []


# =======================================================================
# _format_escalation_line / build_escalation_segment -- pure logic
# =======================================================================


def test_format_escalation_line_contains_all_fields():
    line = je._format_escalation_line((5, "attempt", "t-042", 3), ascii_only=False)
    assert "R6-ЗЕРКАЛО" in line
    assert "line 5" in line
    assert "attempt 3" in line
    assert "t-042" in line
    assert "escalated" in line


def test_format_escalation_line_ascii_channel_replaces_dynamic_non_ascii():
    # Статический литерал ("R6-ЗЕРКАЛО: ... без escalated по task_id ...")
    # -- кириллица, НЕ проходит ни через один санитайзер (тот же принцип,
    # что build_context уже устанавливает -- см.
    # test_build_context_static_prefix_never_sanitized_in_either_mode в
    # tools/test_journal_echo.py); только ДИНАМИКА (task_id) санитайзится
    # по каналу -- non-ASCII task_id заменяется на '?' в ascii_only=True,
    # остаётся как есть в ascii_only=False.
    task_id_with_cyrillic = "t-042-кириллица"
    raw_line = je._format_escalation_line((1, "attempt", task_id_with_cyrillic, 3), ascii_only=False)
    ascii_line = je._format_escalation_line((1, "attempt", task_id_with_cyrillic, 3), ascii_only=True)
    assert "кириллица" in raw_line
    assert "кириллица" not in ascii_line
    assert "?" in ascii_line


def test_build_escalation_segment_empty_list():
    assert je.build_escalation_segment([]) == ""


def test_build_escalation_segment_single_event():
    ev = (5, "attempt", "t-042", 3)
    seg = je.build_escalation_segment([ev])
    assert seg == je._format_escalation_line(ev, False)


def test_build_escalation_segment_exactly_five_boundary_no_more_suffix():
    events = [(i, "attempt", f"t-{i:03d}", 3) for i in range(1, je.MAX_ESCALATION_LINES + 1)]
    seg = je.build_escalation_segment(events)
    assert seg.count("R6-ЗЕРКАЛО") == je.MAX_ESCALATION_LINES
    assert "more" not in seg


def test_build_escalation_segment_beyond_boundary_six_adds_one_more():
    events = [(i, "attempt", f"t-{i:03d}", 3) for i in range(1, je.MAX_ESCALATION_LINES + 2)]
    seg = je.build_escalation_segment(events)
    assert seg.count("R6-ЗЕРКАЛО") == je.MAX_ESCALATION_LINES
    assert seg.endswith("; +1 more")


# =======================================================================
# combine_context -- backward compat + new 5th positional segment
# =======================================================================


def test_combine_context_backward_compat_two_arg_unaffected():
    violations = ["v"]
    assert je.combine_context(violations, []) == je.build_context(violations)


def test_combine_context_backward_compat_four_arg_unaffected():
    violations = ["v"]
    ts_ev = (2, "future", 125.0)
    ctx = je.combine_context(violations, [], [], [ts_ev])
    assert ctx == je.build_context(violations) + "; " + je.build_ts_drift_segment([ts_ev])


def test_combine_context_escalation_only_segment():
    ev = (5, "attempt", "t-042", 3)
    ctx = je.combine_context([], [], None, None, [ev])
    assert ctx == je.build_escalation_segment([ev])
    assert "JOURNAL ECHO" not in ctx


def test_combine_context_escalation_joined_with_fallback_marker():
    ev = (5, "attempt", "t-042", 3)
    ctx = je.combine_context([], [], None, None, [ev], "MARKER")
    assert ctx == je.build_escalation_segment([ev]) + "; MARKER"


def test_combine_context_all_empty_yields_empty_string():
    assert je.combine_context([], [], None, None, None) == ""


# =======================================================================
# main() end-to-end -- subprocess-смок
# =======================================================================


def test_echo_escalation_form1_warns(tmp_path):
    # DoD 1: attempt>=3, no escalated above -> WARN.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=3,
              worker_ref="cli:d3", notes="retry again"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "R6-ЗЕРКАЛО" in ctx
    assert "t-002" in ctx


def test_echo_escalation_form2_warns(tmp_path):
    # DoD 2: no attempt field, >=2 rejected same model, no escalated after
    # the second -> WARN ("ретрай, забывший attempt").
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet",
              worker_ref="cli:d3", notes="retry, forgot attempt"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "R6-ЗЕРКАЛО" in ctx


def test_echo_escalation_never_blocks_no_permission_decision(tmp_path):
    # DoD 3: returncode всегда 0, JSON никогда не несёт permissionDecision.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=3,
              worker_ref="cli:d3", notes="retry again"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "permissionDecision" not in hook_output


def test_echo_escalation_attempt3_with_escalated_above_silent(tmp_path):
    # DoD 4: attempt>=3, escalated with same task_id already above -> silent.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="escalated", task_id="t-002", model="opus"),
        _line(event="delegated", task_id="t-002", model="opus", attempt=3,
              worker_ref="cli:d3", notes="escalated retry"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_attempt2_boundary_silent(tmp_path):
    # DoD 5 (правило 6а, нижняя граница): attempt=2 (порог-1) -- тихо.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_attempt3_boundary_warns(tmp_path):
    # DoD 5 (правило 6а, ровно на пороге): attempt=3 -- warn (см. также
    # test_echo_escalation_form1_warns за более полный сценарий).
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=3,
              worker_ref="cli:d3", notes="retry"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "R6-ЗЕРКАЛО" in hook_output["additionalContext"]


def test_echo_escalation_critic_entry_silent(tmp_path):
    # DoD 6: critic entry (agent="critic") -- not a retry, no warn even
    # with attempt>=3 and no escalated above.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", agent="critic", model="opus", attempt=3,
              worker_ref="cli:d3", notes="critic entry"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_replaces_worker_silent(tmp_path):
    # DoD 7: replaces_worker token in notes -- not a retry, no warn.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=3,
              worker_ref="cli:d4", notes="replaces_worker:cli:d3"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_different_tiers_silent(tmp_path):
    # DoD 8: attempt>=3, rejected на разных ярусах (разные model) -- тихо,
    # эскалация фактически уже шла.
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="opus", attempt=2,
              worker_ref="cli:d2", notes="escalated by model change"),
        _line(event="rejected", task_id="t-002", model="opus", attempt=2, by="fable",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="opus", attempt=3,
              worker_ref="cli:d3", notes="retry same higher tier"),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_malformed_line_among_new_does_not_crash(tmp_path):
    # Адверсариальная 9: строка-не-JSON среди новых -- существующая
    # JOURNAL ECHO-диагностика ловит её как дефект формы (валидация --
    # накопительная HEAD-дифф-база, не эта задача), ESCALATION ECHO не
    # роняется и не роняет хук.
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = "{not valid json"
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0


def test_echo_escalation_empty_payload_silent(tmp_path):
    # Адверсариальная 10: пустой payload -> тихий exit 0 (существующий
    # fail-open путь main(), payload не dict).
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_non_journal_path_silent(tmp_path):
    other_file = tmp_path / "not-a-journal.txt"
    other_file.write_text("irrelevant content", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(other_file))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_escalation_combined_with_defect_one_context(tmp_path):
    # Форма-дефект (пустая category) + ESCALATION вместе -- оба сегмента
    # в одном additionalContext, склеены "; ".
    journal_path = _seed_committed_journal(tmp_path)
    lines = [
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=1,
              worker_ref="cli:d1"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=1, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=2,
              worker_ref="cli:d2", notes="retry"),
        _line(event="rejected", task_id="t-002", model="sonnet", attempt=2, by="opus",
              failure_class="capability"),
        _line(event="delegated", task_id="t-002", model="sonnet", attempt=3,
              worker_ref="cli:d3", notes="retry again", category=""),
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "R6-ЗЕРКАЛО" in ctx
    assert "; R6-ЗЕРКАЛО" in ctx
