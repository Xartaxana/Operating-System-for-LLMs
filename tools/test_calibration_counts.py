"""Тесты tools/calibration_counts.py (t-040). Синтетические журналы-фикстуры
на tmp_path, по одному кейсу на класс из спеки, плюс smoke-тест CLI."""
import json

from calibration_counts import (
    SPEC_RECIDIV_MIN_COUNT,
    SPEC_RECIDIV_MIN_RATIO,
    analyze_journal,
    main,
    parse_ts,
    render_text,
)


def write_journal(path, lines):
    """lines: список dict ИЛИ сырых строк (для непарсящихся/AO3-с-пробелами)."""
    with open(path, "w", encoding="utf-8") as fh:
        for line in lines:
            if isinstance(line, str):
                fh.write(line + "\n")
            else:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def ev(ts, event, **kw):
    d = {"ts": ts, "event": event}
    d.update(kw)
    return d


# ---------------------------------------------------------------------
# 1. rule-6 пара без escalated -> кандидат
# ---------------------------------------------------------------------
def test_rule6_pair_without_escalated_is_candidate(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "journal_created", notes="init"),
        ev("2026-07-08T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T01:10:00", "rejected", agent="scout", model="haiku",
           task_id="t-001", attempt=1, failure_class="tooling", category="recon", notes="n"),
        ev("2026-07-08T01:20:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T01:30:00", "rejected", agent="scout", model="haiku",
           task_id="t-001", attempt=2, failure_class="tooling", category="recon", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert len(report["rule6_candidates"]) == 1
    assert report["rule6_candidates"][0]["task_id"] == "t-001"


# ---------------------------------------------------------------------
# 2. rule-6 пара С escalated -> НЕ кандидат
# ---------------------------------------------------------------------
def test_rule6_pair_with_escalated_not_candidate(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "journal_created", notes="init"),
        ev("2026-07-08T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T01:10:00", "rejected", agent="scout", model="haiku",
           task_id="t-001", attempt=1, failure_class="tooling", category="recon", notes="n"),
        ev("2026-07-08T01:20:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T01:30:00", "rejected", agent="scout", model="haiku",
           task_id="t-001", attempt=2, failure_class="tooling", category="recon", notes="n"),
        ev("2026-07-08T01:40:00", "escalated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert report["rule6_candidates"] == []


# ---------------------------------------------------------------------
# 3. rejected без failure_class -> нарушение
# ---------------------------------------------------------------------
def test_rejected_missing_failure_class_is_violation(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-09T00:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, category="implementation", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    viol = [v for v in report["field_violations"] if v["event"] == "rejected"]
    assert len(viol) == 1
    assert "failure_class" in viol[0]["missing_fields"]


# ---------------------------------------------------------------------
# 4. accepted(builder) без witness -> нарушение
# ---------------------------------------------------------------------
def test_accepted_builder_missing_witness_is_violation(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-09T00:10:00", "accepted", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    viol = [v for v in report["field_violations"] if v["event"] == "accepted"]
    assert len(viol) == 1
    assert "witness" in viol[0]["missing_fields"]


# ---------------------------------------------------------------------
# 5. by-пропуск после отсечки vs легальность до
# ---------------------------------------------------------------------
def test_by_missing_after_cutoff_legal_before(tmp_path):
    p = tmp_path / "j.jsonl"
    by_since = "2026-07-10T13:14:00"
    write_journal(p, [
        ev("2026-07-09T00:00:00", "accepted", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),  # до отсечки, без by -> легально
        ev("2026-07-10T14:00:00", "accepted", agent="scout", model="haiku",
           task_id="t-002", category="recon", notes="n"),  # после отсечки, без by -> кандидат
        ev("2026-07-10T15:00:00", "accepted", agent="scout", model="haiku",
           task_id="t-003", category="recon", notes="n", by="fable"),  # после, с by -> ок
    ])
    report = analyze_journal(str(p), None, None, parse_ts(by_since))
    assert len(report["by_violations"]) == 1
    assert report["by_violations"][0]["task_id"] == "t-002"


# ---------------------------------------------------------------------
# 6. дубль task_id: после accepted / critic-вход / continuation / retry
# ---------------------------------------------------------------------
def test_duplicate_delegate_after_accepted_is_candidate(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T00:10:00", "accepted", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T00:20:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),  # дубль/reopen без attempt>=2, не critic
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "кандидат-дубль"


def test_duplicate_delegate_critic_entry_is_legal_branch(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-08T00:10:00", "accepted", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n", witness="ok"),
        ev("2026-07-08T00:20:00", "delegated", agent="critic", model="opus",
           task_id="t-001", category="review", notes="n"),  # critic-вход по открытой/закрытой задаче
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "critic-вход"


def test_duplicate_delegate_continuation_after_rejected(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-08T00:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, failure_class="spec", category="implementation", notes="n"),
        ev("2026-07-08T00:20:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),  # continuation, тот же ярус
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "continuation"


def test_duplicate_delegate_retry_attempt_2(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-08T00:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, failure_class="tooling", category="implementation", notes="n"),
        ev("2026-07-08T00:20:00", "escalated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-08T00:30:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", attempt=2, category="implementation", notes="n"),  # retry, post-escalation
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "retry"


# ---------------------------------------------------------------------
# 7. ts-немонотонность
# ---------------------------------------------------------------------
def test_ts_non_monotonic_detected(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T10:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T09:00:00", "accepted", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),  # раньше предыдущей строки
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert len(report["ts_anomalies"]) == 1
    assert report["ts_anomalies"][0]["line"] == 2


# ---------------------------------------------------------------------
# 8. непарсящаяся строка
# ---------------------------------------------------------------------
def test_unparsable_line_reported(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "journal_created", notes="init"),
        "{ this is not valid json",
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert len(report["unparsable"]) == 1
    assert report["unparsable"][0]["line"] == 2


# ---------------------------------------------------------------------
# 9. AO3-формат с пробелами после двоеточий
# ---------------------------------------------------------------------
def test_ao3_format_with_spaces_parses(tmp_path):
    p = tmp_path / "j.jsonl"
    raw = ('{"ts": "2026-07-08T00:00:00", "event": "delegated", "agent": "builder", '
           '"category": "implementation", "notes": "n", "task_id": "at-bug-001"}')
    write_journal(p, [raw])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert report["parsed_lines"] == 1
    assert report["unparsable"] == []
    assert report["counts"]["by_event"]["delegated"] == 1


# ---------------------------------------------------------------------
# 10. окно-фильтр
# ---------------------------------------------------------------------
def test_window_filter_excludes_outside_events(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-09T00:00:00", "accepted", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-10T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-002", category="recon", notes="n"),
    ])
    start = parse_ts("2026-07-09T00:00:00")
    end = parse_ts("2026-07-10T00:00:00")
    report = analyze_journal(str(p), start, end, parse_ts("2026-07-10T13:14:00"))
    assert report["in_window_count"] == 1
    assert report["counts"]["by_event"] == {"accepted": 1}


# ---------------------------------------------------------------------
# 11. legacy-секция до-D-0053
# ---------------------------------------------------------------------
def test_legacy_events_before_d0053_not_counted_as_violation(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        # до LEGACY_CUTOFF (2026-07-08T20:00:00), rejected без failure_class -- legacy
        ev("2026-07-08T10:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-08T10:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-001", attempt=1, category="implementation", notes="n"),
        # после LEGACY_CUTOFF, тот же дефект -- настоящее нарушение
        ev("2026-07-09T10:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-002", category="implementation", notes="n"),
        ev("2026-07-09T10:10:00", "rejected", agent="builder", model="sonnet",
           task_id="t-002", attempt=1, category="implementation", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert len(report["legacy_events"]) == 1
    assert report["legacy_events"][0]["task_id"] == "t-001"
    field_viol_task_ids = [v["task_id"] for v in report["field_violations"]]
    assert "t-002" in field_viol_task_ids
    assert "t-001" not in field_viol_task_ids


# ---------------------------------------------------------------------
# smoke-тест CLI
# ---------------------------------------------------------------------
def test_cli_json_smoke(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "journal_created", notes="init"),
        ev("2026-07-08T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-08T01:10:00", "accepted", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
    ])
    # прямой вызов модульного main() надёжнее subprocess (не завязан на cwd/PYTHONPATH)
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["--journal", str(p), "--json"])
    assert code == 0
    parsed = json.loads(buf.getvalue())
    assert "journals" in parsed
    assert len(parsed["journals"]) == 1
    assert parsed["journals"][0]["counts"]["by_event"]["delegated"] == 1


def test_cli_text_mode_exit_zero(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-08T00:00:00", "journal_created", notes="init"),
    ])
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = main(["--journal", str(p)])
    assert code == 0
    assert "journal_created" in buf.getvalue()


def test_cli_invalid_window_start_exit_2(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [ev("2026-07-08T00:00:00", "journal_created", notes="init")])
    code = main(["--journal", str(p), "--window-start", "not-a-date"])
    assert code == 2


def test_cli_missing_file_exit_2(tmp_path):
    code = main(["--journal", str(tmp_path / "does-not-exist.jsonl")])
    assert code == 2


# ---------------------------------------------------------------------
# Синхронизация схемных констант с journal_validator (critic t-040,
# находка 1): обе копии кодируют ОДНУ схему D-0053 (гейт на записи,
# счётчик на чтении); молчаливое расхождение тихо уводит счёт калибровки.
# ---------------------------------------------------------------------
def test_schema_constants_match_journal_validator():
    import journal_validator as jv
    import calibration_counts as cc
    assert cc.MODEL_REQUIRED_EVENTS == jv.MODEL_REQUIRED_EVENTS
    assert cc.TASK_ID_REQUIRED_EVENTS == jv.TASK_ID_REQUIRED_EVENTS
    assert cc.FAILURE_CLASSES == jv.FAILURE_CLASSES
    # t-129 M1: REPLACES_WORKER_RE -- продублированный literal (правило
    # 9в2), не импорт -- .pattern сравнивается, т.к. re.Pattern не
    # определяет __eq__ по значению (два скомпилированных regex с
    # одинаковым исходником не равны через ==, если это не тот же объект).
    assert cc.REPLACES_WORKER_RE.pattern == jv.REPLACES_WORKER_RE.pattern


# ---------------------------------------------------------------------
# Ветка other (critic t-040, находка 2): повторный delegated ПОСЛЕ
# escalated без attempt (живой прецедент OS line 98, t-015) -> честный
# catch-all, surfaced в отчёт с prior_status для вердикта Lead.
# ---------------------------------------------------------------------
def test_duplicate_delegate_after_escalated_without_attempt_is_other(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T01:00:00", "delegated", agent="scout", model="m",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-09T01:10:00", "rejected", agent="scout", model="m",
           task_id="t-001", attempt=1, failure_class="tooling", category="recon", notes="n"),
        ev("2026-07-09T01:15:00", "rejected", agent="scout", model="m",
           task_id="t-001", attempt=2, failure_class="tooling", category="recon", notes="n"),
        ev("2026-07-09T01:20:00", "escalated", agent="scout", model="m",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-09T01:30:00", "delegated", agent="scout", model="m",
           task_id="t-001", category="recon", notes="attempt 3 без поля attempt"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    other = [d for d in report["duplicate_delegates"] if d["branch"] == "other"]
    assert len(other) == 1
    assert other[0]["prior_status"] == "escalated"
    assert other[0]["attempt"] is None


# ---------------------------------------------------------------------
# Чек 13б: false-accept rate по ярусам (critic t-040, находка 3).
# ---------------------------------------------------------------------
def test_false_accept_rate_per_agent(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T01:00:00", "delegated", agent="builder", model="m",
           task_id="t-001", category="i", notes="n"),
        ev("2026-07-09T01:10:00", "accepted", agent="builder", model="m",
           task_id="t-001", witness="w", category="i", notes="n"),
        ev("2026-07-09T01:20:00", "delegated", agent="builder", model="m",
           task_id="t-002", category="i", notes="n"),
        ev("2026-07-09T01:30:00", "accepted", agent="builder", model="m",
           task_id="t-002", witness="w", category="i", notes="n"),
        ev("2026-07-09T02:00:00", "defect_found", agent="builder", model="m",
           task_id="t-003", ref="t-001", category="i", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    fa = report["false_accept"]["builder"]
    assert fa == {"defect_found": 1, "accepted": 2, "rate": 0.5}


# ---------------------------------------------------------------------
# Чек 5 (журнальная сторона): пары деградации — closed и незакрытый хвост.
# ---------------------------------------------------------------------
def test_degradation_pairs_closed_and_open_tail(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T01:00:00", "lead_degraded", agent="lead", model="opus",
           category="degradation", notes="switch down"),
        ev("2026-07-09T02:00:00", "lead_restored", agent="lead", model="fable",
           category="degradation", notes="разбор окна: пусто"),
        ev("2026-07-09T03:00:00", "lead_degraded", agent="lead", model="sonnet",
           category="degradation", notes="switch down again"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    pairs = report["degradation_pairs"]
    assert len(pairs) == 2
    assert pairs[0]["note"] == "closed"
    assert pairs[0]["restored_line"] == 2
    assert pairs[1]["restored_line"] is None
    assert "НЕЗАКРЫТА" in pairs[1]["note"]


# ---------------------------------------------------------------------
# Чек 13г: распределение rejected по failure_class x agent x model.
# ---------------------------------------------------------------------
def test_rejected_distribution_grouping(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-09T01:10:00", "rejected", agent="scout", model="haiku",
           task_id="t-001", attempt=1, failure_class="tooling", category="recon", notes="n"),
        ev("2026-07-09T01:20:00", "delegated", agent="builder", model="sonnet",
           task_id="t-002", category="i", notes="n"),
        ev("2026-07-09T01:30:00", "rejected", agent="builder", model="sonnet",
           task_id="t-002", attempt=1, failure_class="spec", category="i", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    dist = {(d["failure_class"], d["agent"], d["model"]): d["count"]
            for d in report["rejected_distribution"]}
    assert dist == {("tooling", "scout", "haiku"): 1, ("spec", "builder", "sonnet"): 1}


# ---------------------------------------------------------------------
# 9в2 (t-129 M1): классификация ветки replaces_worker -- зеркало
# journal_validator 9в2 на стороне СЧЁТЧИКА (не гейта). Ветка вставлена
# после retry и перед other; existing branches (critic-вход/кандидат-
# дубль/continuation/retry/other) не меняются -- регресс уже покрыт
# существующими тестами выше (в т.ч. test_duplicate_delegate_after_
# escalated_without_attempt_is_other -- та же позиция в цепочке, но БЕЗ
# маркера, всё ещё "other").
# ---------------------------------------------------------------------
def test_duplicate_delegate_replacement_valid_marker(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n", worker_ref="agent:OLD"),
        ev("2026-07-15T00:10:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:NEW",
           notes="критик остановлен без вердикта, продолжает новый воркер "
                 "replaces_worker:agent:OLD"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "replacement"


def test_duplicate_delegate_replacement_fake_handle(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n", worker_ref="agent:OLD"),
        ev("2026-07-15T00:10:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:NEW",
           notes="replaces_worker:agent:NEVER_EXISTED"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "replacement-фиктивный"


def test_duplicate_delegate_replacement_self_reference_is_fake(tmp_path):
    # маркер ссылается на worker_ref ЭТОЙ ЖЕ (новой) строки, не прежней --
    # ещё не harvest'нут в task_worker_refs на момент классификации ->
    # фиктивная замена, зеркалит негатив (б) валидатора t-129 M3.
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n", worker_ref="agent:OLD"),
        ev("2026-07-15T00:10:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:SELF",
           notes="replaces_worker:agent:SELF"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "replacement-фиктивный"


def test_duplicate_delegate_no_marker_still_other_regression(tmp_path):
    # регресс: повторный delegated без маркера в той же позиции цепочки
    # (agent совпадает, prior не accepted/rejected, attempt не >=2) --
    # классификация остаётся "other", как до t-129 M1.
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n", worker_ref="agent:OLD"),
        ev("2026-07-15T00:10:00", "escalated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", notes="n"),
        ev("2026-07-15T00:20:00", "delegated", agent="builder", model="sonnet",
           task_id="t-001", category="implementation", worker_ref="agent:NEW",
           notes="no marker here"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    dups = report["duplicate_delegates"]
    assert len(dups) == 1
    assert dups[0]["branch"] == "other"


# ---------------------------------------------------------------------
# Незакрытые задачи: последний lifecycle-эвент delegated -> в списке.
# ---------------------------------------------------------------------
def test_unclosed_tasks_listed(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-09T01:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        ev("2026-07-09T01:10:00", "delegated", agent="builder", model="sonnet",
           task_id="t-002", category="i", notes="n"),
        ev("2026-07-09T01:30:00", "accepted", agent="builder", model="sonnet",
           task_id="t-002", witness="w", category="i", notes="n"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert report["unclosed_tasks"] == ["t-001"]


# ---------------------------------------------------------------------
# Находка t-293: семантика закрытия в "незакрытых задачах" -- closes:
# токен в notes ЛЮБОГО позднего события и decomposable как закрывающий
# статус. Кейс 3 (regress-guard: чисто открытая delegated -> ЕСТЬ в
# незакрытых) уже покрыт test_unclosed_tasks_listed выше -- не дублируем.
# ---------------------------------------------------------------------
def test_unclosed_closed_by_closes_token_in_later_event(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-001", category="recon", notes="n"),
        # позднее событие -- НЕ lifecycle-эвент (calibrated), но closes:
        # токен в его notes всё равно должен закрыть t-001
        ev("2026-07-15T01:00:00", "calibrated", agent="lead", model="fable",
           category="calibration", notes="еженедельный прогон closes:t-001"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    assert report["unclosed_tasks"] == []


# ---------------------------------------------------------------------
# Находка t-305: ts-неупорядоченный сегмент -- живой класс t-029.
# Задача закрыта accepted, но ФАЙЛОВАЯ позиция лжёт: строго ПОСЛЕ этого
# accepted в файле встречается ещё один (orphan) delegated того же
# task_id, чей ts на самом деле РАНЬШЕ accepted (ts правдив, позиция
# нет) -- зеркало живого дефекта в logs/routing-log.jsonl, задокументи-
# рованного в session_context.py (open_dispatches() docstring, "t-029
# (orphan delegated inserted mid-file AFTER its accepted -- file
# position lies, ts is true)"). Эталон (session_context.py boot-сканер)
# закрывает такую задачу безусловно, ЛЮБОЙ accepted -- JOURNAL LAW,
# независимо от файловой позиции/ts; до находки t-305 calibration_counts
# листил её "открытой", т.к. последним ПО ФАЙЛОВОЙ ПОЗИЦИИ lifecycle-
# эвентом был delegated.
# ---------------------------------------------------------------------
def test_unclosed_not_falsely_listed_when_ts_disordered_orphan_delegated_after_accepted(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-10T09:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-029", category="implementation", notes="n",
           worker_ref="cli:2026-07-10T09:00:00"),
        ev("2026-07-10T09:30:00", "accepted", agent="builder", model="sonnet",
           task_id="t-029", by="sonnet", witness="w", category="implementation",
           notes="n"),
        # orphan: файловая позиция ПОСЛЕ accepted выше, но собственный ts
        # (09:05) на самом деле РАНЬШЕ accepted (09:30) -- ts-неупорядо-
        # ченный исторический сегмент, позиция файла лжёт.
        ev("2026-07-10T09:05:00", "delegated", agent="builder", model="sonnet",
           task_id="t-029", category="implementation",
           notes="orphan, ts lies, file position true",
           worker_ref="cli:2026-07-10T09:05:00"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-11T00:00:00"))
    assert report["unclosed_tasks"] == []
    assert "t-029" not in report["unclosed_tasks"]


def test_unclosed_closed_by_decomposable(tmp_path):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="scout", model="haiku",
           task_id="t-002", category="recon", notes="n"),
        ev("2026-07-15T00:10:00", "decomposable", agent="scout", model="haiku",
           task_id="t-002", category="recon", notes="разложимо на части"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    assert report["unclosed_tasks"] == []
    assert report["closed_by_decomposable"] == ["t-002"]


# ---------------------------------------------------------------------
# SPEC-RECIDIV (R11(n), C1 t-646/2026-08-27, форма [Б]). Порог
# ДВУЧАСТНЫЙ: N_spec >= SPEC_RECIDIV_MIN_COUNT (3) И доля >=
# SPEC_RECIDIV_MIN_RATIO (0.40). Окно -- "с последнего calibrated" ПО
# ПОЗИЦИИ В ФАЙЛЕ, независимо от --window-start/--window-end,
# переданных analyze_journal (те управляют остальными чеками отчёта).
# ---------------------------------------------------------------------
def _rej(ts, task_id, failure_class=None, by=None, notes="n", agent="builder", model="sonnet"):
    d = {"ts": ts, "event": "rejected", "agent": agent, "model": model,
         "task_id": task_id, "attempt": 1, "category": "implementation", "notes": notes}
    if failure_class is not None:
        d["failure_class"] = failure_class
    if by is not None:
        d["by"] = by
    return d


def test_spec_recidiv_present_in_report_structure_c1f1_detector(tmp_path):
    """Детектор смерти слоя (C1-F1): непустая фикстура ОБЯЗАНА нести ключ
    spec_recidiv с полным набором подполей -- исчезновение поля из отчёта
    красит этот тест."""
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-08-20T14:24:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="calibration-N"),
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus"),
        _rej("2026-08-20T15:10:00", "t-002", failure_class="capability", by="opus"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    assert "spec_recidiv" in report
    sr = report["spec_recidiv"]
    for key in ("window_start", "numerator", "denominator", "ratio",
                "unclassified", "retro", "threshold_hit", "spec_lines"):
        assert key in sr, f"пропало поле {key}"
    assert sr["numerator"] == 1
    assert sr["denominator"] == 2
    # структура вывода: блок присутствует в тексте секции чека 13г
    text = render_text(report)
    assert "SPEC-RECIDIV (R11(n))" in text
    assert "spec = дефект ДИСПЕТЧЕРА (R11(n)), не исполнителя" in text


def _window9_journal(tmp_path, rejected_lines):
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-08-20T14:24:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="calibration-N"),
        *rejected_lines,
    ])
    return p


def test_spec_recidiv_count_below_threshold_quiet(tmp_path):
    # 2 spec / 5 rejected = 40% (доля НА пороге), но count=2 < MIN_COUNT=3
    # -> тихо (двучастный порог требует ОБА условия).
    rejected = [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus"),
        _rej("2026-08-20T15:01:00", "t-002", failure_class="spec", by="opus"),
        _rej("2026-08-20T15:02:00", "t-003", failure_class="capability", by="opus"),
        _rej("2026-08-20T15:03:00", "t-004", failure_class="capability", by="opus"),
        _rej("2026-08-20T15:04:00", "t-005", failure_class="capability", by="opus"),
    ]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert (sr["numerator"], sr["denominator"]) == (2, 5)
    assert abs(sr["ratio"] - 0.40) < 1e-9
    assert sr["threshold_hit"] is False
    assert "ПОРОГ СРАБОТАЛ" not in render_text(report)


def test_spec_recidiv_count_and_ratio_at_edge_hits(tmp_path):
    # 3 spec / 7 rejected ~= 42.9% -- НА границе целочисленного знаменателя:
    # m=7 -- последнее значение, при котором доля ещё >= 0.40 (m=8 уже
    # ниже, см. следующий тест) -- ровно требование п.6а "тест на границе".
    rejected = [_rej(f"2026-08-20T15:0{i}:00", f"t-00{i}", failure_class="spec", by="opus")
                for i in range(3)]
    rejected += [_rej(f"2026-08-20T15:1{i}:00", f"t-01{i}", failure_class="capability", by="opus")
                 for i in range(4)]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert (sr["numerator"], sr["denominator"]) == (3, 7)
    assert sr["threshold_hit"] is True
    assert "ПОРОГ СРАБОТАЛ (предварительный, базлайн 5/7 окна №9)" in render_text(report)


def test_spec_recidiv_ratio_just_beyond_edge_quiet(tmp_path):
    # 3 spec / 8 rejected = 37.5% -- ОДИН rejected больше, чем предыдущий
    # тест (m=8 вместо m=7): count=3 удовлетворён, доля падает ниже 0.40
    # -> тихо. "За границей" двойника предыдущего теста.
    rejected = [_rej(f"2026-08-20T15:0{i}:00", f"t-00{i}", failure_class="spec", by="opus")
                for i in range(3)]
    rejected += [_rej(f"2026-08-20T15:1{i}:00", f"t-01{i}", failure_class="capability", by="opus")
                 for i in range(5)]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert (sr["numerator"], sr["denominator"]) == (3, 8)
    assert sr["ratio"] < SPEC_RECIDIV_MIN_RATIO
    assert sr["threshold_hit"] is False
    assert "ПОРОГ СРАБОТАЛ" not in render_text(report)


def test_spec_recidiv_4_of_8_hits_without_duplication(tmp_path):
    # 4 spec / 8 rejected = 50% -> порог срабатывает; строка порога не
    # дублируется (ровно ОДНО вхождение в тексте).
    rejected = [_rej(f"2026-08-20T15:0{i}:00", f"t-00{i}", failure_class="spec", by="opus")
                for i in range(4)]
    rejected += [_rej(f"2026-08-20T15:1{i}:00", f"t-01{i}", failure_class="capability", by="opus")
                 for i in range(4)]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert (sr["numerator"], sr["denominator"]) == (4, 8)
    assert sr["threshold_hit"] is True
    text = render_text(report)
    assert text.count("ПОРОГ СРАБОТАЛ (предварительный, базлайн 5/7 окна №9)") == 1


def test_spec_recidiv_empty_window_zero_over_zero_no_division_error(tmp_path):
    # Нет rejected после calibrated -> 0 из 0, без строки порога, без
    # ZeroDivisionError.
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-08-20T14:24:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="calibration-N"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert (sr["numerator"], sr["denominator"]) == (0, 0)
    assert sr["ratio"] is None
    assert sr["threshold_hit"] is False
    text = render_text(report)
    assert "0 spec из 0 rejected" in text
    assert "ПОРОГ СРАБОТАЛ" not in text


def test_spec_recidiv_no_calibrated_event_at_all_whole_file_is_window(tmp_path):
    # Нет ни одного calibrated в журнале вовсе -- окно = весь файл (тот же
    # приём, что _in_window(start=None)), не крэш и не путаница с "0 из 0".
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert sr["window_start"] is None
    assert (sr["numerator"], sr["denominator"]) == (1, 1)


def test_spec_recidiv_unclassified_separated_from_numerator(tmp_path):
    # rejected без failure_class -- пропуск в отдельный счёт unclassified,
    # НЕ в числитель (форму поля failure_class валидирует journal_
    # validator, не этот скрипт); знаменатель = ВСЕ rejected окна (п.1
    # спеки), unclassified остаётся включён в него.
    rejected = [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus"),
        _rej("2026-08-20T15:01:00", "t-002", failure_class=None, by="opus"),  # нет поля вовсе
    ]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert sr["numerator"] == 1
    assert sr["unclassified"] == 1
    assert sr["denominator"] == 2  # unclassified остаётся в "ВСЕ rejected окна"


def test_spec_recidiv_attribution_by_field_and_missing_by(tmp_path):
    # Фикс C1-F2: spec-строки несут ярус ДИСПЕТЧЕРА (поле by), не
    # agent/model исполнителя; отсутствующий by -> "<нет>", не крэш.
    rejected = [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus",
             agent="builder", model="sonnet"),
        _rej("2026-08-20T15:01:00", "t-002", failure_class="spec", by=None,
             agent="builder", model="sonnet"),
    ]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    by_values = {sl["task_id"]: sl["by"] for sl in sr["spec_lines"]}
    assert by_values == {"t-001": "opus", "t-002": "<нет>"}
    text = render_text(report)
    assert "line" in text and "by=opus" in text and "by=<нет>" in text


def test_spec_recidiv_retro_counted_separately_same_line(tmp_path):
    rejected = [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus",
             notes="retroactive fix of missed reject; bounds fixed"),
        _rej("2026-08-20T15:01:00", "t-002", failure_class="capability", by="opus"),
    ]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    assert sr["retro"] == 1
    text = render_text(report)
    # ретро печатается в ТОЙ ЖЕ строке, что n/m -- строка SPEC-RECIDIV
    # несёт и долю, и число ретро.
    line = [l for l in text.splitlines() if "SPEC-RECIDIV (R11(n)):" in l][0]
    assert "ретро: 1" in line


def test_spec_recidiv_window_independent_of_cli_window_args(tmp_path):
    # rejected(spec) ДО calibrated -- вне окна SPEC-RECIDIV, даже когда
    # общий --window-start/--window-end прогона (None/None здесь) его бы
    # включил в остальные чеки отчёта (rejected_distribution и т.п.).
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        _rej("2026-08-19T00:00:00", "t-000", failure_class="spec", by="opus"),
        ev("2026-08-20T14:24:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="calibration-N"),
        _rej("2026-08-20T15:00:00", "t-001", failure_class="capability", by="opus"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    sr = report["spec_recidiv"]
    # t-000 (spec, до calibrated) исключён из окна SPEC-RECIDIV
    assert sr["denominator"] == 1
    assert sr["numerator"] == 0
    # но он ВИДЕН в общем rejected_distribution (общее окно None/None
    # включает весь файл) -- доказывает, что окна разные, не молчаливая
    # потеря данных
    dist_fcs = [d["failure_class"] for d in report["rejected_distribution"]]
    assert "spec" in dist_fcs


def test_unclosed_closes_token_trailing_punctuation(tmp_path):
    # "closes:t-042;" -- закрывает по форме сканера (session_context.py
    # _CLOSES_RE: t-\d+, хвостовая пунктуация естественно отсекается
    # \d+, отдельная обрезка не нужна).
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-07-15T00:00:00", "delegated", agent="builder", model="sonnet",
           task_id="t-042", category="implementation", notes="n"),
        ev("2026-07-15T00:10:00", "dispatch_skipped", agent="builder", model="sonnet",
           category="implementation", notes="батч мелочей; closes:t-042; продолжение в t-050"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-16T00:00:00"))
    assert report["unclosed_tasks"] == []


# ---------------------------------------------------------------------
# Строка популяции SPEC-RECIDIV (ось 15 карты, диспатч 2026-08-28,
# п.1: "недостижимый объём ПЕЧАТАЕТСЯ отдельной строкой, а не молчит").
# Текст строки ЗАДАН ДОСЛОВНО спекой -- константа модуля, не зависит от
# чисел; N1 -- детектор смерти строки (красный контроль см. отчёт
# билдера); N2 -- регрессия I1 (числа/строки блока не меняются) живёт
# отдельным прогоном на КОПИИ живого журнала (не здесь -- гигиена
# запрещает мутацию боевого сайдкара в юнит-тесте); N3-N5 -- края.
# ---------------------------------------------------------------------

POPULATION_LINE = (
    "  популяция: знаменатель — только события rejected окна; самопризнанные "
    "дефекты диспетчера без события rejected в него НЕ входят и машинно не "
    "считаются (норма и пробел — чек 13(г))"
)


def test_n1_population_line_present_verbatim_and_positioned(tmp_path):
    """N1: детектор смерти строки популяции -- КРАСНЕЕТ, если строка
    отсутствует или текст разошёлся с заданным дословно. Позиция (I2):
    ПОСЛЕ перечня 'line NNNN task_id=... by=...', ПЕРЕД 'unclassified'."""
    rejected = [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus"),
        _rej("2026-08-20T15:01:00", "t-002", failure_class=None, by="opus"),
    ]
    p = _window9_journal(tmp_path, rejected)
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    text = render_text(report)
    assert POPULATION_LINE in text
    lines = text.splitlines()
    pop_idx = lines.index(POPULATION_LINE)
    spec_line_idxs = [i for i, l in enumerate(lines) if l.startswith("    line ")]
    assert spec_line_idxs, "фикстура обязана нести хотя бы одну строку 'line NNNN...'"
    assert pop_idx > max(spec_line_idxs)
    unclassified_idxs = [i for i, l in enumerate(lines) if l.startswith("  unclassified")]
    assert unclassified_idxs, "фикстура обязана нести unclassified (t-002 без failure_class)"
    assert pop_idx < min(unclassified_idxs)


def test_n3_empty_window_still_prints_population_line(tmp_path):
    """N3: пустое окно (calibrated без единого rejected) -> доля н/д,
    но строка популяции печатается тем же текстом, exit не влияет
    (analyze_journal сам не даёт exit -- проверяется через main())."""
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-08-20T14:24:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="calibration-N"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    text = render_text(report)
    assert "0 spec из 0 rejected (н/д)" in text
    assert POPULATION_LINE in text
    rc = main(["--journal", str(p)])
    assert rc == 0


def test_n4_no_calibrated_event_still_prints_population_line(tmp_path):
    """N4: журнал без единого calibrated -> окно = весь файл, строка
    популяции печатается тем же текстом (второе правило окна не
    заведено)."""
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        _rej("2026-08-20T15:00:00", "t-001", failure_class="spec", by="opus"),
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    text = render_text(report)
    assert POPULATION_LINE in text


def test_n5_notes_absent_or_broken_no_crash_population_line_intact(tmp_path):
    """N5: notes отсутствует/не строка/пустая/очень длинная -- не крэш,
    поведение как сейчас; строка популяции всё равно печатается."""
    p = tmp_path / "j.jsonl"
    write_journal(p, [
        ev("2026-08-20T14:24:00", "calibrated", agent="lead", model="opus",
           category="calibration", notes="calibration-N"),
        {"ts": "2026-08-20T15:00:00", "event": "rejected", "agent": "builder", "model": "sonnet",
         "task_id": "t-001", "attempt": 1, "category": "implementation", "failure_class": "spec",
         "by": "opus"},  # notes отсутствует вовсе
        {"ts": "2026-08-20T15:01:00", "event": "rejected", "agent": "builder", "model": "sonnet",
         "task_id": "t-002", "attempt": 1, "category": "implementation", "failure_class": "spec",
         "by": "opus", "notes": None},  # notes не строка
        {"ts": "2026-08-20T15:02:00", "event": "rejected", "agent": "builder", "model": "sonnet",
         "task_id": "t-003", "attempt": 1, "category": "implementation", "failure_class": "spec",
         "by": "opus", "notes": ""},  # notes пустая
        {"ts": "2026-08-20T15:03:00", "event": "rejected", "agent": "builder", "model": "sonnet",
         "task_id": "t-004", "attempt": 1, "category": "implementation", "failure_class": "spec",
         "by": "opus", "notes": "x" * 5000},  # notes очень длинная
    ])
    report = analyze_journal(str(p), None, None, parse_ts("2026-07-10T13:14:00"))
    text = render_text(report)
    sr = report["spec_recidiv"]
    assert sr["numerator"] == 4
    assert sr["denominator"] == 4
    assert POPULATION_LINE in text
