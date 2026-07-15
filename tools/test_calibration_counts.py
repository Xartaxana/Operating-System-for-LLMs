"""Тесты tools/calibration_counts.py (t-040). Синтетические журналы-фикстуры
на tmp_path, по одному кейсу на класс из спеки, плюс smoke-тест CLI."""
import json

from calibration_counts import analyze_journal, main, parse_ts


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
