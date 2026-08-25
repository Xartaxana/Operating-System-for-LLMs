"""tools/test_journal_echo_r3.py -- R3-ЗЕРКАЛО слой (узел 1, builder,
2026-08-25, docs/tasks/2026-08-25_r3-mirror-spec.md), реализован в
tools/journal_echo_r3.py (СИБЛИНГ живого tools/journal_echo.py -- см. его
секцию "R3-ЗЕРКАЛО" за полный разбор дизайна; живой journal_echo.py НЕ
несёт этот слой -- посадка байт-копией + фикс шапки -- отдельный узел 2,
Lead, вне owns этой задачи).

ФОРМА (Р2а спеки узла 1, прецедент F61_TARGET): цель разрешается через
переменную окружения R3_TARGET:
 - R3_TARGET не задан (default) -> tools/journal_echo_r3.py (сиблинг).
 - R3_TARGET=live -> tools/journal_echo.py (живой хук) -- ДИСКРИМИНИРУЮЩИЙ
   контр-режим: живой файл НЕ несёт ни одной R3-функции
   (_collect_r3_events/_check_accepted_r3/_format_r3_line/
   build_r3_segment/CRITIC_SKIP_RE/MAX_R3_LINES) -- любой тест, трогающий
   их напрямую, обязан упасть AttributeError в этом режиме (тот же
   принцип, что F61_TARGET=live -- "заведомо непочинена цель", доказывает,
   что сиблинг добавляет НОВОЕ поведение, не переоткрывает уже бывшее).
   Run: `R3_TARGET=live python -m pytest tools/test_journal_echo_r3.py -q`
   (ожидаемо: массовые ошибки на R3-специфичных тестах -- контроль).

Дано (D-0106): tools/journal_echo.py (образец-близнец) ·
tools/journal_validator.py (BASIS_VALUES/JUDGE_BASIS_VALUE, только чтение)
· logs/routing-log.jsonl (образцы + К6 ретро-замер) ·
docs/task_reports/2026-08-20_calibration-8.md §F7 (11+8 task_id) ·
docs/tasks/2026-08-25_r3-mirror-spec.md (спека целиком, решения Р1-Р10,
триггер/сигналы S1-S4, M1/M2, П1-П5, лимиты, края, батарея 1-14, К6/К7).

ПОКРЫВАЕТ АКЦЕПТАНС УЗЛА 1 буквально:
 К1 сигналы S1-S4 по-тестно (глушит + негативный близнец) + M2-детектор.
 К2 тексты M1/M2 дословно (пин точного текста).
 К3 инварианты П1-П5 с пинами.
 К4 края (спека "КРАЯ") + батарея 1-14 (спека "БАТАРЕЯ").
 К5 лимиты MAX_R3_LINES/MAX_MESSAGE_LEN НА и ЗА границей (правило 6а).
 К6 ретро-замер живого logs/routing-log.jsonl (11 F7-утечек / 8 контролей).
 К7 негативный контроль детектора К6 (монкипатч S3, без порчи файлов --
   command hygiene п.7: ни один боевой/новый файл не портится и не
   откатывается, порча целиком в процессе pytest, in-memory).

Run: python -m pytest tools/test_journal_echo_r3.py -q
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
LIVE_JOURNAL = REPO_ROOT / "logs" / "routing-log.jsonl"

R3_TARGET = os.environ.get("R3_TARGET", "").strip().lower()


def _resolve_r3_path() -> Path:
    # ПОСЛЕ ПОСАДКИ (t-609 байт-копией, 2026-08-25): живой файл — цель по
    # умолчанию, сиблинг удалён актом посадки. Явный запрос сиблинга
    # (R3_TARGET=sibling) при его отсутствии падает ГРОМКО на загрузке
    # (FileNotFoundError) — та же дисциплина, что K1 (без тихой подмены).
    live = TOOLS_DIR / "journal_echo.py"
    sibling = TOOLS_DIR / "journal_echo_r3.py"
    if R3_TARGET == "sibling":
        return sibling
    return live


SCRIPT = _resolve_r3_path()
_MODULE_CACHE: dict = {}


def _load_target():
    key = str(SCRIPT)
    if key not in _MODULE_CACHE:
        alias = f"r3_battery_{'live' if R3_TARGET == 'live' else 'sibling'}"
        spec = importlib.util.spec_from_file_location(alias, SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[key] = module
    return _MODULE_CACHE[key]


je = _load_target()


# =======================================================================
# helpers -- построчные журнальные записи (pure-logic тесты, ts не нужен --
# _collect_r3_events не смотрит на ts вовсе)
# =======================================================================


def _l(event="accepted", agent="builder", task_id="t-001", **kw) -> str:
    obj = {"event": event, "agent": agent, "task_id": task_id}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


def _raw(**kw) -> str:
    """Строит строку БЕЗ автоматических event/agent/task_id -- для краевых
    тестов, которым нужен ПОЛНЫЙ контроль над набором ключей (например,
    "task_id вовсе нет")."""
    return json.dumps(kw, ensure_ascii=False)


def _accepted_events(new_lines, base_lines=()):
    return je._collect_r3_events(list(new_lines), list(base_lines))


def _kinds(events):
    return [(e[1], e[2]) for e in events]


# =======================================================================
# К1 -- сигналы S1-S4 по-тестно: глушит + негативный близнец
# =======================================================================


def test_s1_basis_critic_with_matching_delegation_fully_silent():
    base = [_l(event="delegated", agent="critic", task_id="t-001")]
    new = [_l(event="accepted", agent="builder", task_id="t-001", basis="critic")]
    assert _accepted_events(new, base) == []


def test_s1_basis_critic_without_delegation_suppresses_m1_but_m2_fires():
    # S1 глушит M1 (no_input) безусловно; M2 (phantom_basis) -- НЕЗАВИСИМЫЙ
    # детектор, срабатывает именно потому что S1 истинно, а делегирования нет.
    new = [_l(event="accepted", agent="builder", task_id="t-001", basis="critic")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-001")]


def test_s1_negative_twin_no_basis_warns_m1():
    # Тот же journal, без basis="critic" -- негативный близнец: теперь
    # предупреждает M1 (доказывает, что именно S1 гасил M1 выше).
    new = [_l(event="accepted", agent="builder", task_id="t-001")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-001")]


def test_s2_notes_skip_silent():
    new = [_l(task_id="t-002", notes="critic: skipped, small diff")]
    assert _accepted_events(new) == []


def test_s2_negative_twin_unrelated_notes_warns():
    new = [_l(task_id="t-002", notes="just a regular note, no concession")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-002")]


def test_s3_delegated_critic_in_base_lines_silent():
    base = [_l(event="delegated", agent="critic", task_id="t-003")]
    new = [_l(task_id="t-003")]
    assert _accepted_events(new, base) == []


def test_s3_delegated_critic_after_accepted_in_same_batch_silent():
    # Р4(б): скан батча в ОБЕ стороны -- критик-делегирование ПОСЛЕ
    # accepted-строки в том же батче тоже гасит (предварительный проход).
    new = [
        _l(task_id="t-003"),
        _l(event="delegated", agent="critic", task_id="t-003"),
    ]
    assert _accepted_events(new) == []


def test_s3_negative_twin_no_delegation_anywhere_warns():
    new = [_l(task_id="t-003")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-003")]


def test_s3_case_sensitive_task_id_does_not_match():
    # "T-500 vs t-500 -> сравнение СТРОГОЕ -> warn" (лимиты/battery 12).
    base = [_l(event="delegated", agent="critic", task_id="T-500")]
    new = [_l(task_id="t-500")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-500")]


def test_s3_same_task_id_delegated_agent_not_critic_still_warns():
    # "окно S3 без ограничения ... тот же task_id при agent!=critic -> warn"
    base = [_l(event="delegated", agent="builder", task_id="t-003")]
    new = [_l(task_id="t-003")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-003")]


def test_s4_basis_judge_silences_unconditionally():
    # Р3(а): basis=="judge" глушит ДАЖЕ без критик-делегирования --
    # M2-детектор НЕ применяется к judge (только к basis=="critic").
    new = [_l(task_id="t-004", basis="judge")]
    assert _accepted_events(new) == []


def test_s4_negative_twin_no_basis_warns():
    new = [_l(task_id="t-004")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-004")]


# =======================================================================
# М2-детектор -- отдельные позитив/негатив пары
# =======================================================================


def test_m2_phantom_basis_positive():
    new = [_l(task_id="t-005", basis="critic")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-005")]


def test_m2_negative_twin_matching_delegation_no_phantom():
    base = [_l(event="delegated", agent="critic", task_id="t-005")]
    new = [_l(task_id="t-005", basis="critic")]
    assert _accepted_events(new, base) == []


# =======================================================================
# S5 (Ф3 поправки Lead 17:0x, критик-гейт t-609): голый токен
# critic:t-NNN в notes глушит M1 И M2 -- ТОЛЬКО если t-NNN существует в
# файле как delegated(agent=critic).
# =======================================================================


def test_s5_valid_token_silences_m1():
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", notes="closes:t-005 critic:t-609 done")]
    assert _accepted_events(new, base) == []


def test_s5_invalid_token_does_not_silence_m1():
    # Токен указывает на t-609, но delegated(critic) с этим id в файле нет.
    new = [_l(task_id="t-006", notes="critic:t-609 done")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-006")]


def test_s5_valid_token_silences_m2_as_alternative_to_delegation():
    # Спека M2: "закрой: токен critic:t-NNN на покрывший вердикт ЛИБО
    # delegated-запись" -- S5 валиден и для basis="critic" без прямого
    # делегирования под ЭТИМ ЖЕ task_id (бандл-паттерн).
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", basis="critic", notes="critic:t-609")]
    assert _accepted_events(new, base) == []


def test_s5_invalid_token_does_not_silence_m2():
    new = [_l(task_id="t-006", basis="critic", notes="critic:t-999")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-006")]


def test_s5_cross_task_id_by_construction_unlike_s3():
    # S5 явно КРОСС-task_id (в отличие от S3, которое требует ТОТ ЖЕ
    # task_id) -- t-609 в токене НЕ равен task_id самой строки (t-006).
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", notes="critic:t-609")]
    assert _accepted_events(new, base) == []


def test_s5_multiple_tokens_any_valid_silences():
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", notes="critic:t-001 critic:t-609 critic:t-002")]
    assert _accepted_events(new, base) == []


# =======================================================================
# Ф4 (поправка Lead 17:0x): приоритет кодифицирован -- basis=critic без
# делегирования и без S5, но С литералом концессии в notes -- M2 верен
# (S2 не гасит противоречивую запись).
# =======================================================================


def test_f4_priority_basis_critic_plus_concession_literal_no_delegation_gives_m2():
    new = [_l(task_id="t-007", basis="critic", notes="critic: skipped, tiny diff")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-007")]


def test_f4_task_id_empty_string_skips_line():
    new = [_l(task_id="")]
    assert _accepted_events(new) == []


def test_f4_task_id_whitespace_only_skips_line():
    new = [_l(task_id="   ")]
    assert _accepted_events(new) == []


def test_f4_task_id_whitespace_only_in_delegated_critic_not_absorbed():
    # Класс, не экземпляр (R9): та же проверка на стороне критик-
    # присутствия -- delegated(critic) с task_id из пробелов НЕ входит в
    # critic_task_ids.
    base = [_l(event="delegated", agent="critic", task_id="   ")]
    new = [_l(task_id="t-008")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-008")]


# =======================================================================
# К2 -- тексты M1/M2 дословно
# =======================================================================


def test_m1_message_literal_text():
    # Б1(ii), поправка Lead 17:0x (критик-гейт t-609) -- новый, вчетверо
    # короче текст M1, ЗАМЕНЯЕТ старый узла 1.
    event = (7, "no_input", "t-042", None)
    text = je._format_r3_line(event, ascii_only=False)
    expected = (
        "R3-ЗЕРКАЛО: line 7 accepted builder t-042: нет "
        "критик-входа под этим id и нет концессии - чек 2 прочтёт приёмку "
        "как самосертификацию; закрой: delegated(critic) по "
        't-042 / токен critic:t-NNN на покрывший вердикт / '
        '"critic: skipped, <причина>" (приёмщик строго выше)'
    )
    assert text == expected


def test_m2_message_literal_text():
    # Б1(ii), поправка Lead 17:0x -- новый текст M2.
    event = (9, "phantom_basis", "t-777", None)
    text = je._format_r3_line(event, ascii_only=False)
    expected = (
        "R3-ЗЕРКАЛО: line 9 basis=critic по t-777, но "
        "delegated(critic) под ЭТИМ task_id нет - основание механически "
        "не прослеживается; закрой: токен critic:t-NNN на покрывший "
        "вердикт ЛИБО delegated-запись"
    )
    assert text == expected


def test_r3_literal_prefix_pinned():
    m1 = je._format_r3_line((1, "no_input", "t-1", None), False)
    m2 = je._format_r3_line((1, "phantom_basis", "t-1", None), False)
    assert m1.startswith("R3-ЗЕРКАЛО: line ")
    assert m2.startswith("R3-ЗЕРКАЛО: line ")


# =======================================================================
# К3 -- инварианты П1-П5
# =======================================================================


class _FakeStdin:
    def __init__(self, data: bytes):
        import io
        self.buffer = io.BytesIO(data)


def _run_main_inprocess(payload_bytes: bytes, monkeypatch) -> int:
    monkeypatch.setattr(je.sys, "stdin", _FakeStdin(payload_bytes))
    return je.main()


def test_p1_main_never_blocks_on_garbage_input(monkeypatch, capsys):
    rc = _run_main_inprocess(b"not even json{{{", monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert "permissionDecision" not in out.out


def test_p1_logic_not_in_journal_validator_decide():
    import inspect
    source = inspect.getsource(je.journal_validator.decide)
    assert "r3" not in source.lower()
    assert "R3-ЗЕРКАЛО" not in source


def test_p2_full_silence_non_journal_path(monkeypatch, capsys):
    # non-journal путь -> main() тих полностью раньше любых R3-вычислений.
    payload = json.dumps({
        "session_id": "s1", "cwd": ".", "tool_name": "Edit",
        "tool_input": {"file_path": "not-the-journal.txt"},
        "tool_response": {},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


def test_p2_r3_events_joins_the_same_truthiness_check_as_siblings():
    # П2 буквально ("новый источник -- в ТУ ЖЕ проверку истинности") --
    # структурный пин источника main(): r3_events обязан жить в ОДНОМ
    # `if (not violations and not tier_events and ...)` выражении вместе
    # со всеми остальными пятью источниками, не в отдельном условии.
    import inspect
    source = inspect.getsource(je.main)
    match = re.search(r"if \(not violations.*?\):\s*\n\s*return 0", source, re.DOTALL)
    assert match is not None, "silence-check `if` block not found in main() source"
    block = match.group(0)
    for name in ("violations", "tier_events", "witness_visible", "ts_drift_events",
                 "escalation_events", "notes_len_events", "r3_events"):
        assert f"not {name}" in block, f"{name} missing from the shared silence check"


def test_p3_combine_context_six_positional_arg_form_unchanged():
    # Тот же пин, что tools/test_journal_echo_escalation.py:431 /
    # tools/test_journal_echo_noteslen.py -- r3_events ДОБАВЛЕН строго
    # keyword-only, шестипозиционный вызов остаётся побайтово прежним.
    ev = (5, "attempt", "t-042", 3)
    ctx = je.combine_context([], [], None, None, [ev], "MARKER")
    assert ctx == je.build_escalation_segment([ev]) + "; MARKER"


def test_p3_r3_events_keyword_only_enforced():
    with pytest.raises(TypeError):
        je.combine_context([], [], None, None, None, "", [(1, "no_input", "t-1", None)])


def test_p3_r3_events_none_default_equivalent_to_absent():
    a = je.combine_context([], [])
    b = je.combine_context([], [], r3_events=None)
    assert a == b == ""


def test_p4_r3_segment_last_content_before_fallback_marker():
    violations = ["bad line"]
    tier_events = []
    r3_ev = (3, "no_input", "t-9", None)
    ctx = je.combine_context(
        violations, tier_events, None, None, None, "MARKER",
        notes_len_events=[(2, "delegated", 900, 800)],
        r3_events=[r3_ev],
    )
    notes_len_idx = ctx.index("NOTES LEN")
    r3_idx = ctx.index("R3-ЗЕРКАЛО")
    marker_idx = ctx.index("MARKER")
    assert notes_len_idx < r3_idx < marker_idx


def test_p4_build_context_header_unchanged():
    ctx = je.combine_context(["bad"], [])
    assert ctx.startswith("JOURNAL ECHO: 1 дефект(ов) в новых строках: ")


def test_p5_malformed_json_line_does_not_abort_collection():
    new = [
        "not json at all {{{",
        '"just a string"',
        "42",
        _l(task_id="t-010"),
    ]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-010")]


def test_p5_collector_exception_falls_back_to_empty_list(monkeypatch, tmp_path):
    # Внутренний try/except main() вокруг _collect_r3_events -- второй
    # слой fail-open (П5). Монкипатч ломает КОЛЛЕКТОР безусловно на РЕАЛЬНОМ
    # journal-пути (иначе main() возвращается раньше, чем вызовет
    # коллектор, и монкипатч ничего не проверит), main() обязан
    # продолжить без падения (return 0), r3-часть просто отсутствует.
    def _boom(new_lines, base_lines):
        raise RuntimeError("boom")
    monkeypatch.setattr(je, "_collect_r3_events", _boom)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    journal_path.write_text(_l(task_id="t-021") + "\n", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0


# =======================================================================
# К4 -- края
# =======================================================================


def test_edge_task_id_missing_skips_line_entirely():
    new = [_raw(event="accepted", agent="builder")]
    assert _accepted_events(new) == []


def test_edge_task_id_non_string_skips_line_entirely():
    new = [_raw(event="accepted", agent="builder", task_id=12345)]
    assert _accepted_events(new) == []


def test_edge_notes_none_treated_as_no_signal():
    new = [_l(task_id="t-011", notes=None)]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-011")]


def test_edge_basis_missing_falls_through_to_s2_s3():
    new = [_l(task_id="t-012", notes="critic: skipped, tiny")]
    assert _accepted_events(new) == []  # S2 still applies


def test_edge_basis_queued_to_lead_does_not_silence():
    new = [_l(task_id="t-013", basis="queued-to-lead")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-013")]


def test_edge_agent_not_builder_silent():
    for agent in ("critic", "fable", "designer"):
        new = [_l(task_id="t-014", agent=agent)]
        assert _accepted_events(new) == [], agent


def test_edge_repeated_accepted_same_task_id_each_independent_no_signal():
    new = [_l(task_id="t-015"), _l(task_id="t-015")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-015"), ("no_input", "t-015")]


def test_edge_repeated_accepted_same_task_id_each_independent_with_delegation():
    base = [_l(event="delegated", agent="critic", task_id="t-015")]
    new = [_l(task_id="t-015"), _l(task_id="t-015")]
    assert _accepted_events(new, base) == []


def test_edge_retro_not_exempted():
    # Р6(а): ретро-события НЕ глушатся -- в отличие от WITNESS ECHO, этот
    # слой не даёт retro-исключения.
    new = [_l(task_id="t-016", notes="retroactive accepted, retro fixup")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-016")]


def test_edge_used_fallback_layer_emits_r3_warning(monkeypatch, tmp_path, capsys):
    # Р8(а): used_fallback -> слой РАБОТАЕТ (семья TIER/WITNESS/ESCALATION,
    # НЕ NOTES-LEN/TS-DRIFT). tmp_path не git-репо -> _get_head_text ->
    # None -> HEAD-дифф фолбэк тривиально (used_fallback=True).
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    journal_path.write_text(_l(task_id="t-017") + "\n", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    captured = capsys.readouterr()
    assert "echo base: HEAD-diff fallback" in captured.err
    assert "R3-ЗЕРКАЛО" in captured.err
    assert "t-017" in captured.err


def test_edge_empty_journal_silent():
    assert _accepted_events([]) == []


def test_edge_non_journal_payload_early_exit(monkeypatch, capsys, tmp_path):
    other = tmp_path / "not-a-journal.txt"
    other.write_text("x", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(other)},
        "tool_response": {},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_edge_r3xr13_collision_s4_silences():
    new = [_l(task_id="t-018", basis="judge")]
    assert _accepted_events(new) == []


def test_edge_witness_field_ignored_batch_canon_no_effect():
    new = [_l(task_id="t-019", witness="BATCH CANON: 4066 passed, 0 failed")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-019")]


# =======================================================================
# БАТАРЕЯ 1-14
# =======================================================================


def test_battery_1_skip_in_witness_not_notes_still_warns():
    new = [_l(task_id="t-b1", witness="critic: skipped, small", notes="unrelated")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b1")]


@pytest.mark.parametrize("notes", [
    "critic: skipped",
    "Critic: Skipped",
    "critic:   skipped",
    "critic:skipped",
])
def test_battery_2_skip_variants_silence(notes):
    new = [_l(task_id="t-b2", notes=notes)]
    assert _accepted_events(new) == []


@pytest.mark.parametrize("notes", [
    "critic: skip",
    "критик пропущен",
    "без критика",
])
def test_battery_3_non_matching_phrasing_still_warns(notes):
    new = [_l(task_id="t-b3", notes=notes)]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b3")]


def test_battery_4_task_id_with_special_chars_sanitized_not_crashing():
    tid = "t-1  ; DROP TABLE"
    new = [_l(task_id=tid)]
    events = _accepted_events(new)
    line = je._format_r3_line(events[0], ascii_only=False)
    assert je._raw_sanitize(tid) in line


def test_battery_5_task_id_10000_chars_truncated():
    tid = "t-" + ("x" * 10000)
    new = [_l(task_id=tid)]
    events = _accepted_events(new)
    line = je._format_r3_line(events[0], ascii_only=False)
    assert je._raw_sanitize(tid) in line
    assert tid not in line
    assert len(je._raw_sanitize(tid)) == je.MAX_MESSAGE_LEN


def test_battery_6_non_ascii_task_id_both_channels():
    tid = "t-задача-42"
    new = [_l(task_id=tid)]
    events = _accepted_events(new)
    raw_line = je._format_r3_line(events[0], ascii_only=False)
    ascii_line = je._format_r3_line(events[0], ascii_only=True)
    assert tid in raw_line
    assert tid not in ascii_line
    assert "?" in ascii_line


def test_battery_7_non_object_json_skipped():
    new = ["42", "[1, 2, 3]", '"a string"', _l(task_id="t-b7")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b7")]


def test_battery_8_truncated_json_skipped_next_line_lives():
    new = ['{"event": "accepted", "agent": "builder"', _l(task_id="t-b8")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b8")]


def test_battery_9_basis_non_string_not_a_signal():
    new = [_raw(event="accepted", agent="builder", task_id="t-b9", basis=123)]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b9")]


def test_battery_10_event_agent_non_string_outside_trigger():
    new = [
        _raw(event=123, agent="builder", task_id="t-b10a"),
        _raw(event="accepted", agent=123, task_id="t-b10b"),
    ]
    assert _accepted_events(new) == []


def test_battery_11_batch_200_violations_capped_and_rest_counted():
    # НАХОДКА (см. отчёт builder'а, поправка Lead 17:0x): с текущими
    # текстами M1 (Б1(ii), ~931 Б/строка на проводе) MAX_R3_BYTES=2600
    # (Б1(iii)) срабатывает РАНЬШЕ MAX_R3_LINES=5 для ЛЮБОГО реалистичного
    # task_id -- фактически видимых строк 2, не 5 (число вычисляется
    # динамически той же мерой _json_wire_len, что build_r3_segment
    # использует внутри -- тест не завязан на конкретное число НА СЛУЧАЙ
    # будущей правки длины текста M1). "+K more" покрывает ОСТАЛЬНЫЕ
    # 200-visible штук вне зависимости от того, какой из двух потолков
    # сработал первым -- сам коллектор остаётся НЕКАПНУТЫМ (200 событий).
    new = [_l(task_id=f"t-{i:03d}") for i in range(200)]
    events = _accepted_events(new)
    assert len(events) == 200  # collector itself uncapped
    seg = je.build_r3_segment(events)
    m1_line = je._format_r3_line((1, "no_input", "t-000", None), False)
    expected_visible = _greedy_fit_count(m1_line, cap=200)
    assert expected_visible < je.MAX_R3_LINES, (
        "assumption stale: MAX_R3_BYTES no longer binds before MAX_R3_LINES "
        "for this task_id shape -- update this test's expectations"
    )
    assert seg.count("R3-ЗЕРКАЛО") == expected_visible
    assert seg.endswith(f"+{200 - expected_visible} more")


def test_battery_12_strict_case_sensitive_task_id_warns():
    base = [_l(event="delegated", agent="critic", task_id="T-500")]
    new = [_l(task_id="t-500")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-500")]


def test_battery_13_empty_file_silent():
    assert _accepted_events([]) == []


def test_battery_14_non_journal_payload_early_exit(monkeypatch, capsys, tmp_path):
    other = tmp_path / "unrelated.md"
    other.write_text("x", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(other)},
        "tool_response": {},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


# =======================================================================
# К5 -- лимиты НА и ЗА границей (правило 6а)
# =======================================================================


def test_limit_max_r3_lines_exactly_5_no_more_suffix_bytes_permitting(monkeypatch):
    # НАХОДКА (см. отчёт builder'а): с текущими текстами M1 (Б1(ii))
    # MAX_R3_BYTES=2600 (Б1(iii)) срабатывает РАНЬШЕ MAX_R3_LINES=5 для
    # ЛЮБОГО реалистичного task_id (см. test_battery_11 и
    # test_limit_max_r3_bytes_short_batch_unaffected за замер БЕЗ
    # монкипатча) -- MAX_R3_LINES=5 в изоляции недостижим НА РЕАЛЬНОМ
    # тексте. Этот тест ИЗОЛИРУЕТ линейную ветку от байтовой
    # (_json_wire_len монкипатчится в 0 -- байтовый потолок никогда не
    # срабатывает), доказывая, что ветка "len(head) >= MAX_R3_LINES" сама
    # по себе корректна -- правило 6а всё равно требует границу НА и ЗА
    # для ЭТОГО потолка, даже если на практике его обгоняет другой.
    monkeypatch.setattr(je, "_json_wire_len", lambda s: 0)
    events = [(i, "no_input", f"t-{i:03d}", None) for i in range(1, je.MAX_R3_LINES + 1)]
    seg = je.build_r3_segment(events)
    assert seg.count("R3-ЗЕРКАЛО") == je.MAX_R3_LINES
    assert "more" not in seg


def test_limit_max_r3_lines_6_gives_plus_1_more_bytes_permitting(monkeypatch):
    monkeypatch.setattr(je, "_json_wire_len", lambda s: 0)
    events = [(i, "no_input", f"t-{i:03d}", None) for i in range(1, je.MAX_R3_LINES + 2)]
    seg = je.build_r3_segment(events)
    assert seg.count("R3-ЗЕРКАЛО") == je.MAX_R3_LINES
    assert seg.endswith("+1 more")


def test_limit_max_message_len_exactly_500_whole():
    tid = "t-" + ("a" * 498)  # общая длина ровно 500
    assert len(tid) == 500
    assert je._raw_sanitize(tid) == tid


def test_limit_max_message_len_501_truncated():
    tid = "t-" + ("a" * 499)  # общая длина 501
    assert len(tid) == 501
    sanitized = je._raw_sanitize(tid)
    assert len(sanitized) == 500
    assert sanitized == tid[:500]


def test_limit_max_message_len_10000_truncated():
    tid = "t-" + ("a" * 9998)
    assert len(tid) == 10000
    sanitized = je._raw_sanitize(tid)
    assert len(sanitized) == je.MAX_MESSAGE_LEN


# --- MAX_R3_BYTES (Б1(iii), поправка Lead 17:0x) -- НА и ЗА границей ---


def _greedy_fit_count(line: str, cap: int) -> int:
    """Сколько КОПИЙ line поместятся в build_r3_segment по ТОЙ ЖЕ жадной
    мере (_json_wire_len накопленного тела, склеенного "; "), не более
    min(cap, MAX_R3_LINES) штук -- зеркалит build_r3_segment буквально,
    чтобы тесты не были завязаны на конкретное магическое число строк
    (устойчиво к будущим правкам длины текста M1/M2, Б1(ii))."""
    total = 0
    count = 0
    while count < min(cap, je.MAX_R3_LINES):
        add = je._json_wire_len(line) + (2 if count else 0)
        if count and total + add > je.MAX_R3_BYTES:
            break
        total += add
        count += 1
    return count


def _two_line_body_bytes(tid_len: int):
    """Совместный json-провод ДВУХ ИДЕНТИЧНЫХ M1-строк с task_id
    "t-" + "a"*tid_len -- та же мера (_json_wire_len), что build_r3_segment
    использует внутри. Возвращает (байты, tid)."""
    tid = "t-" + ("a" * tid_len)
    line = je._format_r3_line((1, "no_input", tid, None), False)
    body = "; ".join([line, line])
    return je._json_wire_len(body), tid


def test_limit_max_r3_bytes_boundary_at_and_beyond():
    # Программный подбор (не magic-число): растим task_id, пока
    # совместный провод ДВУХ строк не достигнет РОВНО потолка
    # MAX_R3_BYTES (НА границе -- обе строки видны, без "+K more"),
    # затем ОДНА лишняя ASCII-буква (+1 байт ровно) -- ЗА границей
    # (усечение до 1 строки + "+1 more"). Устойчиво к будущим правкам
    # длины текстов M1/M2 (Б1(ii)) -- граница ищется, не жёстко пришита.
    tid_len = 1
    bytes_at, tid_at = _two_line_body_bytes(tid_len)
    while bytes_at < je.MAX_R3_BYTES:
        tid_len += 1
        bytes_at, tid_at = _two_line_body_bytes(tid_len)
    if bytes_at > je.MAX_R3_BYTES:
        tid_len -= 1
        bytes_at, tid_at = _two_line_body_bytes(tid_len)
    assert bytes_at <= je.MAX_R3_BYTES, "could not construct an AT-boundary case"

    events_at = [(1, "no_input", tid_at, None), (2, "no_input", tid_at, None)]
    seg_at = je.build_r3_segment(events_at)
    assert seg_at.count("R3-ЗЕРКАЛО") == 2
    assert "more" not in seg_at

    # ЗА границей: тот же task_id + одна ASCII-буква -- гарантированно
    # +1 байт ровно на КАЖДОЕ вхождение (task_id встречается дважды в
    # тексте M1), сумма строго > MAX_R3_BYTES.
    tid_over = tid_at + "a"
    events_over = [(1, "no_input", tid_over, None), (2, "no_input", tid_over, None)]
    seg_over = je.build_r3_segment(events_over)
    assert seg_over.count("R3-ЗЕРКАЛО") == 1
    assert seg_over.endswith("+1 more")


def test_limit_max_r3_bytes_binds_before_lines_for_typical_short_task_id():
    # НАХОДКА (см. отчёт builder'а поправки Lead 17:0x, замерено, не
    # предположено): С ТЕКУЩИМИ текстами M1 (Б1(ii), ~931 Б/строка на
    # проводе из-за кириллической прозы) MAX_R3_BYTES=2600 срабатывает
    # РАНЬШЕ MAX_R3_LINES=5 ДАЖЕ для КОРОТКИХ типичных task_id ("t-001" и
    # т.п.) -- ровно 2 строки помещаются, 3-я уже уходит в "+K more".
    # Число проверяется динамически (_greedy_fit_count зеркалит
    # build_r3_segment буквально), не жёстко пришито к "2".
    m1_line = je._format_r3_line((1, "no_input", "t-001", None), False)
    fit = _greedy_fit_count(m1_line, cap=je.MAX_R3_LINES)
    assert fit < je.MAX_R3_LINES, (
        "assumption stale: typical short task_id no longer hits the byte "
        "cap before MAX_R3_LINES -- update this test (and the finding note "
        "in the builder's report) if M1's text was shortened further"
    )
    events = [(i, "no_input", f"t-{i:03d}", None) for i in range(1, je.MAX_R3_LINES + 1)]
    seg = je.build_r3_segment(events)
    assert seg.count("R3-ЗЕРКАЛО") == fit
    assert seg.endswith(f"+{je.MAX_R3_LINES - fit} more")
    assert je._json_wire_len(seg) < je.MAX_R3_BYTES


# =======================================================================
# К6 -- ретро-замер (Ф2 поправки Lead 17:0x: ЗАМОРОЖЕННАЯ фикстура-срез,
# не живой logs/routing-log.jsonl -- три ПОСТОЯННЫХ теста ниже
# ассертят на ней; живой проход остаётся разовым К6-witness'ом /
# неутверждающей пробой, см. test_k6_live_journal_probe_witness_only)
# =======================================================================

F7_LEAK_IDS = {
    "t-437", "t-444", "t-447", "t-449", "t-453",
    "t-492", "t-496", "t-501", "t-503", "t-504", "t-537",
}
F7_CONTROL_IDS = {
    "t-509", "t-516", "t-525", "t-529", "t-532", "t-535", "t-536", "t-538",
}

# Ф2 поправки Lead 17:0x: ЗАМОРОЖЕННАЯ фикстура-срез -- ровно 50 строк,
# извлечённые ОДИН РАЗ из живого logs/routing-log.jsonl 2026-08-25 (все
# delegated/accepted/rejected записи 19 известных task_id -- 11 F7-утечек
# + 8 контролей), больше не читаемая заново из живого файла на каждый
# прогон -- три ПОСТОЯННЫХ теста ниже (К6 fixture-детерминизм + К7)
# ассертят на НЕЙ, не на живом (живой файл растёт каждую сессию -- прежняя
# форма узла 1 была недетерминированной по построению, критик-гейт F).
FIXTURE_JOURNAL = TOOLS_DIR / "test_journal_echo_r3_fixture.jsonl"


def _retro_measure(mod, journal_path: Path):
    """Полный ретроспективный проход по ВСЕЙ истории journal-файла
    (base_lines=[] -- каждая строка файла трактуется как "новая" для
    целей этого разового ретро-замера; критик-присутствие ищется по
    ВСЕМУ файлу, тот же _collect_r3_events, что main() использует на
    payload-scoped базе в проде). Возвращает (marked_sorted_list, events)."""
    text = journal_path.read_text(encoding="utf-8", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    events = mod._collect_r3_events(lines, [])
    marked = sorted({ev[2] for ev in events})
    return marked, events


def test_k6_retro_measure_fixture_marks_exactly_the_11_f7_leaks():
    # ПОСТОЯННЫЙ, детерминированный тест (Ф2): фикстура несёт РОВНО 19
    # известных task_id -- marked_set обязан совпасть с F7_LEAK_IDS ТОЧНО
    # (не просто "надмножество"), контролей быть не должно вовсе.
    assert FIXTURE_JOURNAL.exists(), f"frozen fixture not found at {FIXTURE_JOURNAL}"
    marked, events = _retro_measure(je, FIXTURE_JOURNAL)
    marked_set = set(marked)
    print(f"K6 RETRO-MEASURE (frozen fixture): {len(marked)} task_id marked: {marked}")
    by_kind: dict = {}
    for ev in events:
        by_kind.setdefault(ev[1], []).append(ev[2])
    print(f"K6 RETRO-MEASURE by kind: no_input={len(by_kind.get('no_input', []))}, "
          f"phantom_basis={len(by_kind.get('phantom_basis', []))}")
    assert marked_set == F7_LEAK_IDS, (
        f"mismatch on frozen fixture: missing={sorted(F7_LEAK_IDS - marked_set)}, "
        f"unexpected={sorted(marked_set - F7_LEAK_IDS)}"
    )
    assert F7_CONTROL_IDS.isdisjoint(marked_set)


def test_k6_live_journal_probe_witness_only():
    # Ф2: живой logs/routing-log.jsonl остаётся РАЗОВЫМ К6-witness'ом /
    # неутверждающей пробой -- растущий журнал НЕ является постоянной
    # приёмочной цепью (тот файл растёт каждую рабочую сессию, набор
    # "лишних" вне известных 19 меняется со временем по конструкции,
    # НЕ дефект слоя, см. ПОПРАВКУ и отчёт builder'а узла 1 за спот-чек
    # класса "критик-вход под другим/бандл task_id", напр. t-047/t-390).
    # Единственные ЖЁСТКИЕ проверки здесь -- те же два инварианта, что
    # ПОСТОЯННЫЙ fixture-тест выше уже доказывает детерминированно; они
    # не должны исчезнуть и на живых данных, но сам список "лишних" не
    # утверждается точным числом.
    if not LIVE_JOURNAL.exists():
        print("K6 LIVE PROBE: skipped, live journal not found")
        return
    marked, events = _retro_measure(je, LIVE_JOURNAL)
    marked_set = set(marked)
    by_kind: dict = {}
    for ev in events:
        by_kind.setdefault(ev[1], []).append(ev[2])
    extra = sorted(marked_set - F7_LEAK_IDS - F7_CONTROL_IDS)
    print(f"K6 LIVE PROBE: {len(marked)} task_id marked total")
    print(f"K6 LIVE PROBE marked list: {marked}")
    print(f"K6 LIVE PROBE by kind: no_input={len(by_kind.get('no_input', []))}, "
          f"phantom_basis={len(by_kind.get('phantom_basis', []))}")
    print(f"K6 LIVE PROBE extra beyond the known 11+8: {len(extra)}: {extra}")
    assert F7_LEAK_IDS <= marked_set, f"live probe: F7 leaks not marked: {sorted(F7_LEAK_IDS - marked_set)}"
    assert F7_CONTROL_IDS.isdisjoint(marked_set), (
        f"live probe: controls wrongly marked: {sorted(F7_CONTROL_IDS & marked_set)}"
    )


# =======================================================================
# К7 -- негативный контроль детектора К6 (монкипатч S3, без порчи файлов,
# на ЗАМОРОЖЕННОЙ фикстуре -- Ф2, детерминированно)
# =======================================================================


def test_k7_negative_control_breaking_s3_reddens_then_restoring_greens(monkeypatch):
    # Половина 1: базовая (интактная) мера на фикстуре -- ЗЕЛЕНО.
    marked_green_before, _ = _retro_measure(je, FIXTURE_JOURNAL)
    assert F7_CONTROL_IDS.isdisjoint(marked_green_before), "baseline expected green"
    assert F7_LEAK_IDS <= set(marked_green_before)
    print(f"K7 HALF 1 (intact): controls falsely marked = "
          f"{sorted(F7_CONTROL_IDS & set(marked_green_before))} (expected: [])")

    # Ломаем S3: _check_accepted_r3 вызывается с ПУСТЫМ critic_task_ids
    # безусловно -- ни одна S3-проверка больше не может сработать (S1/S2/
    # S4/S5 остаются живыми, S5 здесь не влияет -- фикстура не несёт
    # critic:t-NNN токенов). Чисто in-process монкипатч, ни один файл
    # (боевой или новый) не тронут -- command hygiene п.7 не применяется
    # вовсе (нет порчи диска).
    original_check = je._check_accepted_r3

    def _broken_check(obj, critic_task_ids):
        return original_check(obj, set())

    monkeypatch.setattr(je, "_check_accepted_r3", _broken_check)

    marked_red, _ = _retro_measure(je, FIXTURE_JOURNAL)
    newly_false_positive = F7_CONTROL_IDS & set(marked_red)
    print(f"K7 HALF 2 (S3 broken): controls falsely marked = "
          f"{sorted(newly_false_positive)} (expected: non-empty -- reddened)")
    assert newly_false_positive, "negative control did not turn red: S3 breakage had no effect"

    # Восстановление (monkeypatch auto-undo happens at teardown, но
    # проверяем ЯВНО В ЭТОМ ЖЕ тесте, обе половины К7 в одном witness).
    monkeypatch.setattr(je, "_check_accepted_r3", original_check)
    marked_restored, _ = _retro_measure(je, FIXTURE_JOURNAL)
    print(f"K7 HALF 2b (restored): controls falsely marked = "
          f"{sorted(F7_CONTROL_IDS & set(marked_restored))} (expected: [])")
    assert F7_CONTROL_IDS.isdisjoint(marked_restored)
    assert F7_LEAK_IDS <= set(marked_restored)
    assert marked_restored == marked_green_before, "restore did not reach byte-identical green"


# =======================================================================
# Б1(i) -- stdout-deadline (поправка Lead 17:0x, порт tools/session_context.py
# _write_stdout_deadline/_stdout_deadline_seconds, спека R2-K1). Стиль --
# ПРЯМОЙ порт tools/test_session_context_layer_a.py B20-B23 + subprocess
# E2E негативный контроль: real OS pipe (os.pipe()), НЕ мок -- недренирующий
# потребитель существует только на уровне реальной ОС.
# =======================================================================


def _make_blocking_pipe_writer():
    """Реальный OS pipe -- read-конец НЕ дренируется, запись сверх ёмкости
    ОС-буфера блокируется внутри write() до дедлайна. Порт
    test_session_context_layer_a.py._make_blocking_pipe_writer буквально."""
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "r", encoding="utf-8", newline="")
    writer = os.fdopen(write_fd, "w", encoding="utf-8", newline="")
    return reader, writer


def _best_effort_release_pipe(reader, writer):
    try:
        reader.close()
    except Exception:
        pass
    time.sleep(0.05)
    try:
        writer.close()
    except Exception:
        pass


def test_b1_non_draining_consumer_write_returns_false_within_deadline(monkeypatch):
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(je.sys, "stdout", writer)
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, "0.3")
    big_text = "x" * 200_000  # comfortably over any realistic OS pipe capacity
    t0 = time.monotonic()
    result = je._write_stdout_deadline(big_text)
    elapsed = time.monotonic() - t0
    assert result is False
    assert 0.25 <= elapsed < 1.3, f"should return within deadline+margin, took {elapsed:.3f}s"
    _best_effort_release_pipe(reader, writer)


def test_b1_draining_consumer_returns_true_full_content_delivered(monkeypatch):
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(je.sys, "stdout", writer)
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, "3.0")
    big_text = "y" * 200_000
    collected = []

    def _drain():
        while True:
            chunk = reader.read(65536)
            if not chunk:
                break
            collected.append(chunk)

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()
    result = je._write_stdout_deadline(big_text)
    assert result is True
    writer.close()
    drainer.join(timeout=5)
    assert not drainer.is_alive(), "drainer thread did not see EOF in time"
    assert "".join(collected) == big_text
    reader.close()


@pytest.mark.parametrize(
    "raw_value,expected_is_default",
    [
        ("", True),
        ("abc", True),
        ("0", True),
        ("-1", True),
        ("601", True),
        ("600", False),
        ("0.1", False),
        ("5", False),
    ],
)
def test_b1_env_deadline_parsing_branches(raw_value, expected_is_default, monkeypatch):
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, raw_value)
    result = je._stdout_deadline_seconds()
    if expected_is_default:
        assert result == je._STDOUT_DEADLINE_DEFAULT
    else:
        assert result == float(raw_value)


def test_b1_env_absent_uses_default(monkeypatch):
    monkeypatch.delenv(je._STDOUT_DEADLINE_ENV, raising=False)
    assert je._stdout_deadline_seconds() == je._STDOUT_DEADLINE_DEFAULT == 5.0


def test_b1_small_valid_deadline_blocking_write_returns_false(monkeypatch):
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(je.sys, "stdout", writer)
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, "0.1")
    big_text = "z" * 200_000
    t0 = time.monotonic()
    result = je._write_stdout_deadline(big_text)
    elapsed = time.monotonic() - t0
    assert result is False
    assert elapsed < 1.0, f"a 0.1s deadline should return well under 1s, took {elapsed:.3f}s"
    _best_effort_release_pipe(reader, writer)


def _giant_cyrillic_no_input_payload(tmp_path, count=5):
    """Строит journal-файл, чья additionalContext (JOURNAL ECHO -- живой
    сегмент валидатора, НЕ трогается этой задачей, БЕЗ собственного
    байтового потолка -- non-goal журнал_validator.py -- + R3-ЗЕРКАЛО)
    ЕСТЕСТВЕННО превышает любую реалистичную ёмкость ОС-пайпа: гигантский
    кириллический task_id инфлируется \\uXXXX-эскейпингом ×6 на символ
    (замерено: 5 таких строк -> ~15.6 КБ на проводе, см. отчёт builder'а)."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    huge_tid = "т-" + ("з" * 2000)
    lines = [json.dumps({"event": "accepted", "agent": "builder", "task_id": huge_tid + str(i)},
                         ensure_ascii=False) for i in range(count)]
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return journal_path


def test_e2e_subprocess_undraining_consumer_exits_within_deadline(tmp_path):
    # Полный main()-путь: real OS pipes ЧЕРЕЗ subprocess.PIPE, stdout
    # НИКОГДА не читается ДО proc.wait() (под тестом); stderr ДРЕНИРУЕТСЯ
    # фоновым потоком (Б1(i) намеренно НЕ покрывает stderr -- см. спеку --
    # недренированный stderr иначе заблокировал бы main() РАНЬШЕ, на
    # своей собственной записи, до того, как код вообще дойдёт до
    # проверяемой stdout-ветки -- изолирует именно stdout).
    journal_path = _giant_cyrillic_no_input_payload(tmp_path)
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    })
    env = os.environ.copy()
    env["OSLLM_STDOUT_TIMEOUT"] = "1.0"
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
    )
    stderr_chunks = []

    def _drain_stderr():
        while True:
            chunk = proc.stderr.read(65536)
            if not chunk:
                break
            stderr_chunks.append(chunk)

    drainer = threading.Thread(target=_drain_stderr, daemon=True)
    drainer.start()
    proc.stdin.write(payload.encode("utf-8"))
    proc.stdin.close()
    t0 = time.monotonic()
    rc = proc.wait(timeout=6.0)
    elapsed = time.monotonic() - t0
    assert rc == 0
    assert elapsed < 6.0, f"took {elapsed:.3f}s"
    deadline = float(env["OSLLM_STDOUT_TIMEOUT"])
    assert elapsed >= 0.8 * deadline, (
        f"exited in {elapsed:.3f}s < 0.8*{deadline}s -- write may not have blocked "
        "(pipe capacity assumption stale?)"
    )
    proc.stdout.close()
    drainer.join(timeout=2)
    proc.stderr.close()


# =======================================================================
# Б1 WITNESS -- субпроцессный замер stdout-байтов на "кейсе критика"
# (4 строки accepted/builder, ДО было 6835 Б при старых текстах M1/M2,
# см. поправку Lead 17:0x) -- РЕАЛЬНЫЙ subprocess (не in-process import),
# stdout ДРЕНИРУЕТСЯ нормально (это измерение объёма, не тест блокировки
# -- тот отдельно выше).
# =======================================================================


def test_witness_critic_case_4_lines_stdout_byte_count(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    lines = [json.dumps({
        "ts": now, "event": "accepted", "agent": "builder", "model": "sonnet",
        "task_id": f"t-{600 + i}", "category": "implementation", "by": "opus",
        "witness": "python -m pytest tools/ -q -> 100 passed",
        "notes": "Приёмка без критик-входа и без пометки concession -- реалистичная запись.",
    }, ensure_ascii=False) for i in range(4)]
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    })
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
    )
    assert result.returncode == 0
    stdout_bytes = len(result.stdout)
    print(f"B1 WITNESS: critic case (4 accepted/builder lines) stdout bytes AFTER fix = {stdout_bytes} "
          f"(ДО поправки, старые тексты M1/M2: 6835 Б, критик-замер t-595)")
    assert stdout_bytes < 4096, (
        f"AFTER-fix stdout for the critic's 4-line case is {stdout_bytes} B -- "
        "expected comfortably under the measured pipe capacity class (4096 B)"
    )
