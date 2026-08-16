# -*- coding: utf-8 -*-
"""Тесты tools/savings_report.py (чек 18 калибровки): математика
контрфакта, деление окон, API-срез — на tmp-базе с обеими схемами.

t-444: контрфакт делегирования теперь резолвится через
mechanism_gate.resolve_lead_binding() (roles.lead в
delegation.config.yaml), не через зашитый id claude-fable-5.
НОРМАТИВНАЯ ЛОВУШКА (спека, К1): не более ОДНОГО теста в этом файле
читает живой корневой delegation.config.yaml — это
test_a5_k1_live_config_consistency_no_literal ниже, и он сверяет
СОГЛАСОВАННОСТЬ с mg.resolve_lead_binding(), без литерала id. Все
остальные тесты арифметики цен инъектируют config_text явно (через
lead_counterfactual/counterfactual_summary/print_report) или
изолируют mg.CONFIG_PATH на tmp-файл — ни один из них не должен стать
ложно-красным в день следующей перепривязки roles.lead.
"""
import sqlite3

import pytest

import mechanism_gate as mg
import savings_report as sr
from savings_report import (
    api_contour_summary,
    counterfactual_summary,
    fable_counterfactual,
    lead_counterfactual,
    print_report,
    window_summary,
)
from usage_report import CACHE_READ_MULTIPLIER, CACHE_WRITE_MULTIPLIER, PRICES_PER_TOKEN_USD

CONFIG_OPUS = "roles:\n  lead:\n    subscription:\n      model: claude-opus-5\n"
CONFIG_FABLE = "roles:\n  lead:\n    subscription:\n      model: claude-fable-5\n"
CONFIG_UNKNOWN_MODEL = "roles:\n  lead:\n    subscription:\n      model: gpt-5\n"
CONFIG_EMPTY_SUBSCRIPTION = "roles:\n  lead:\n    subscription: {}\n    api: {}\n"
CONFIG_BROKEN_YAML = "roles: [unterminated"


@pytest.fixture()
def db(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute(
        "CREATE TABLE cc_usage (ts TEXT, project TEXT, session_id TEXT,"
        " model TEXT, input_tokens INT, output_tokens INT,"
        " cache_creation_tokens INT, cache_read_tokens INT,"
        " accounted_cost_usd REAL, is_sidechain INT, agent_type TEXT)")
    conn.execute(
        "CREATE TABLE requests (ts TEXT, model TEXT, cost_usd REAL,"
        " traffic_kind TEXT)")
    return conn


def _cc(conn, ts, model, side, i=100, o=50, cw=0, cr=0, cost=1.0,
        agent=None, sess="s1"):
    conn.execute(
        "INSERT INTO cc_usage VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (ts, "p", sess, model, i, o, cw, cr, cost, side, agent))


def _reset_config_cache(monkeypatch):
    """Каждый тест, задевающий сентинел-путь (config_text не передан),
    стартует со свежим кэшем _read_real_config_text() -- иначе порядок
    исполнения тестов в файле мог бы отравить друг друга (тот же класс
    риска, что у tools/journal_validator.py's _cached_real_config_text).
    monkeypatch откатывает атрибут модуля автоматически после теста."""
    monkeypatch.setattr(sr, "_cached_real_config_text", sr._CONFIG_TEXT_UNSET)


# ---------------------------------------------------------------------
# A2/A3: арифметика контрфакта -- обе точки инъектируют config_text.
# ---------------------------------------------------------------------

def test_a2_opus_binding_matches_manual_formula():
    op = PRICES_PER_TOKEN_USD["claude-opus-5"]
    expected = (1000 * op[0] + 200 * op[1]
                + 400 * op[0] * CACHE_WRITE_MULTIPLIER
                + 8000 * op[0] * CACHE_READ_MULTIPLIER)
    got = lead_counterfactual(1000, 200, 400, 8000, config_text=CONFIG_OPUS)
    assert got == pytest.approx(expected)


def test_a3_pin_fable_config_matches_pre_fix_arithmetic():
    # Пин: правка меняет БАЗУ (откуда берётся модель), не арифметику
    # _cost(). Инъекция roles.lead=claude-fable-5 обязана дать ЧИСЛЕННО
    # то же самое число, что старый хардкод FABLE_MODEL давал до правки.
    fp = PRICES_PER_TOKEN_USD["claude-fable-5"]
    expected = (1000 * fp[0] + 200 * fp[1]
                + 400 * fp[0] * CACHE_WRITE_MULTIPLIER
                + 8000 * fp[0] * CACHE_READ_MULTIPLIER)
    got = lead_counterfactual(1000, 200, 400, 8000, config_text=CONFIG_FABLE)
    assert got == pytest.approx(expected)
    # Алиас (R-6) обязан вести себя идентично под тем же вызовом.
    got_alias = fable_counterfactual(1000, 200, 400, 8000, config_text=CONFIG_FABLE)
    assert got_alias == pytest.approx(expected)


def test_r9_alias_is_same_object_as_lead_counterfactual():
    assert fable_counterfactual is lead_counterfactual


# ---------------------------------------------------------------------
# A4: ветка R-5 (fail-soft "н/д") -- оба подслучая.
# ---------------------------------------------------------------------

def test_a4_r5_subcase_a_no_lead_key_returns_none_with_warning(capsys):
    # roles.lead есть, subscription/api пусты -> resolve_lead_binding
    # падает на дефолт голого семейства "fable" -- цены на голое слово
    # в PRICES_PER_TOKEN_USD нет.
    got = lead_counterfactual(1000, 200, 0, 0, config_text=CONFIG_EMPTY_SUBSCRIPTION)
    assert got is None
    err = capsys.readouterr().err
    assert "WARNING" in err


def test_a4_r5_subcase_b_unknown_valid_model_returns_none_with_warning(capsys):
    # gpt-5 -- валидный id (не голое семейство), но не-Claude привязка,
    # цены на него в usage_report.PRICES_PER_TOKEN_USD нет.
    got = lead_counterfactual(1000, 200, 0, 0, config_text=CONFIG_UNKNOWN_MODEL)
    assert got is None
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert "gpt-5" in err  # ФАКТИЧЕСКАЯ строка привязки, из-за которой цены нет


def test_a4_r5_subcase_a_mg_none_no_typeerror(monkeypatch, capsys):
    # R-3: mg is None (mechanism_gate недоступен) -- та же ветка R-5,
    # никакого TypeError (cf += None класс дефекта, который эта ветка
    # обязана закрыть). Форма инъекции -- monkeypatch.setattr на атрибут
    # модуля (tools/test_journal_validator.py:1424-1433), НЕ sys.modules.
    monkeypatch.setattr(sr, "mg", None)
    got = sr.lead_counterfactual(1000, 200, 400, 8000, config_text=CONFIG_OPUS)
    assert got is None
    assert "WARNING" in capsys.readouterr().err
    # K2(8): импорт savings_report успешен даже когда mg недоступен --
    # модуль уже импортирован (topmost import в этом файле) и остаётся
    # пригоден к вызову после monkeypatch, никакого падения на импорте.
    assert sr.lead_counterfactual is not None


def test_r5_broken_yaml_returns_none_with_warning(capsys):
    got = lead_counterfactual(1000, 200, 0, 0, config_text=CONFIG_BROKEN_YAML)
    assert got is None
    assert "WARNING" in capsys.readouterr().err


# ---------------------------------------------------------------------
# A5/K1: РОВНО один тест читает живой корневой delegation.config.yaml,
# и он не содержит литерала модели -- сверяет согласованность.
# ---------------------------------------------------------------------

def test_a5_k1_live_config_consistency_no_literal(monkeypatch):
    _reset_config_cache(monkeypatch)
    live_text = (mg.CONFIG_PATH.read_text(encoding="utf-8", errors="replace")
                 if mg.CONFIG_PATH.exists() else None)
    expected_binding = mg.resolve_lead_binding(live_text)
    got = sr._resolve_counterfactual_binding()  # сентинел -> тот же файл
    assert got == expected_binding


# ---------------------------------------------------------------------
# A6/K2: пустые/отсутствующие входы.
# ---------------------------------------------------------------------

def test_k2_1_empty_window_is_zero_not_none(db, tmp_path):
    c = counterfactual_summary(db, "ts >= ?", ("2026-07-08",), config_text=CONFIG_OPUS)
    assert c["detail"] == []
    assert c["actual"] == 0.0
    assert c["as_lead"] == 0.0
    assert c["gross_savings"] == 0.0
    assert c["savings_pct"] == 0.0
    # печать не падает на пустом окне
    print_report(str(tmp_path / "t.db"), "2026-07-08", config_text=CONFIG_OPUS)


def test_k2_2_null_tokens_zero_not_typeerror():
    got = lead_counterfactual(None, None, None, None, config_text=CONFIG_OPUS)
    assert got == 0.0


def test_k2_3_null_accounted_cost_actual_zero(db):
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=1000, o=100, cost=None, agent="scout")
    c = counterfactual_summary(db, "ts >= ?", ("2026-07-08",), config_text=CONFIG_OPUS)
    assert c["actual"] == 0.0
    assert c["as_lead"] is not None


def test_k2_4_cf_zero_actual_positive_no_zerodivision(db):
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=0, o=0, cw=0, cr=0, cost=5.0, agent="scout")
    c = counterfactual_summary(db, "ts >= ?", ("2026-07-08",), config_text=CONFIG_OPUS)
    assert c["as_lead"] == 0.0
    assert c["actual"] == pytest.approx(5.0)
    assert c["savings_pct"] == 0.0
    assert c["gross_savings"] == pytest.approx(-5.0)


def test_k2_5_empty_string_config_text_is_no_config():
    got = lead_counterfactual(1000, 200, 0, 0, config_text="")
    assert got is None


def test_k2_6_lead_key_present_subscription_and_api_empty():
    got = lead_counterfactual(1000, 200, 0, 0, config_text=CONFIG_EMPTY_SUBSCRIPTION)
    assert got is None


def test_k2_7_non_claude_binding():
    got = lead_counterfactual(1000, 200, 0, 0, config_text=CONFIG_UNKNOWN_MODEL)
    assert got is None


def test_k2_8_mg_none_and_import_successful(monkeypatch):
    monkeypatch.setattr(sr, "mg", None)
    assert sr.lead_counterfactual(100, 50, 0, 0, config_text=CONFIG_OPUS) is None
    # модуль остаётся полностью рабочим (импорт не падает на mg is None)
    assert callable(sr.print_report)


# ---------------------------------------------------------------------
# A7: print_report называет фактическую модель + строку разрыва базы,
# без подписи "по-Fable" когда привязка не Fable.
# ---------------------------------------------------------------------

def test_a7_print_report_shows_actual_model_and_disruption_no_fable_label(
        db, tmp_path, capsys):
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=1000, o=100, cost=0.002, agent="scout")
    db.commit()
    print_report(str(tmp_path / "t.db"), "2026-07-08", config_text=CONFIG_OPUS)
    out = capsys.readouterr().out
    assert "claude-opus-5" in out
    assert "БАЗА КОНТРФАКТА СМЕНЕНА 2026-08-16" in out
    assert "по-Fable" not in out


def test_a7_print_report_na_label_on_unresolved_binding(db, tmp_path, capsys):
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=1000, o=100, cost=0.002, agent="scout")
    db.commit()
    print_report(str(tmp_path / "t.db"), "2026-07-08",
                 config_text=CONFIG_UNKNOWN_MODEL)
    out = capsys.readouterr().out
    assert "н/д" in out
    assert "по-Fable" not in out


# ---------------------------------------------------------------------
# A8: регресс-пин R-8 -- флаг/оверрайд.
# ---------------------------------------------------------------------

def test_a8_no_override_reproduces_equivalent_injected_config(tmp_path, monkeypatch):
    # "Отсутствие флага воспроизводит поведение без флага байт-в-байт":
    # редиректим mg.CONFIG_PATH на КОНТРОЛИРУЕМЫЙ tmp-файл (не живой
    # корневой конфиг -- К1 запрещает второй тест на живом файле) и
    # сверяем сентинел-путь с эквивалентной явной инъекцией того же
    # текста. Числового литерала цены здесь нет -- сравнение
    # структурное (два пути дают одно и то же число).
    cfg = tmp_path / "delegation.config.yaml"
    cfg.write_text(CONFIG_OPUS, encoding="utf-8")
    monkeypatch.setattr(mg, "CONFIG_PATH", cfg)
    _reset_config_cache(monkeypatch)
    no_override = sr.lead_counterfactual(1000, 200, 400, 8000)
    injected = sr.lead_counterfactual(1000, 200, 400, 8000, config_text=CONFIG_OPUS)
    assert no_override == pytest.approx(injected)


def test_a8_flag_reproduces_pre_fix_number():
    fp = PRICES_PER_TOKEN_USD["claude-fable-5"]
    expected = (1000 * fp[0] + 200 * fp[1]
                + 400 * fp[0] * CACHE_WRITE_MULTIPLIER
                + 8000 * fp[0] * CACHE_READ_MULTIPLIER)
    got = sr.lead_counterfactual(1000, 200, 400, 8000,
                                  override_model="claude-fable-5")
    assert got == pytest.approx(expected)


def test_a8_cli_flag_wired_through_main(db, tmp_path, capsys):
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=1000, o=100, cost=0.002, agent="scout")
    db.commit()
    code = sr.main(["--db", str(tmp_path / "t.db"), "--routed-start", "2026-07-08",
                     "--counterfactual-model", "claude-fable-5"])
    assert code == 0
    out = capsys.readouterr().out
    assert "claude-fable-5" in out
    assert "н/д" not in out


def test_a8_cli_unknown_flag_model_goes_to_r5(db, tmp_path, capsys):
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=1000, o=100, cost=0.002, agent="scout")
    db.commit()
    code = sr.main(["--db", str(tmp_path / "t.db"), "--routed-start", "2026-07-08",
                     "--counterfactual-model", "gpt-5"])
    assert code == 0
    out = capsys.readouterr().out
    assert "н/д" in out


# ---------------------------------------------------------------------
# Прежняя математика/агрегация -- сохранена, инъектирует config_text.
# ---------------------------------------------------------------------

def test_window_split_pre_vs_routed(db):
    _cc(db, "2026-07-05T10:00:00", "claude-sonnet-5", 0, cost=2.0)
    _cc(db, "2026-07-09T10:00:00", "claude-fable-5", 0, cost=5.0)
    pre = window_summary(db, "ts < ?", ("2026-07-08",))
    routed = window_summary(db, "ts >= ?", ("2026-07-08",))
    assert pre["total_cost"] == pytest.approx(2.0)
    assert routed["total_cost"] == pytest.approx(5.0)
    assert pre["days"] == 1 and routed["days"] == 1


def test_counterfactual_only_sidechains_in_window(db):
    # сайдчейн в окне — считается; main и до-оконный сайдчейн — нет
    _cc(db, "2026-07-09T10:00:00", "claude-haiku-4-5-20251001", 1,
        i=1000, o=100, cost=0.002, agent="scout")
    _cc(db, "2026-07-09T11:00:00", "claude-fable-5", 0, cost=9.0)
    _cc(db, "2026-07-01T10:00:00", "claude-sonnet-5", 1, cost=1.0, agent="builder")
    c = counterfactual_summary(db, "ts >= ?", ("2026-07-08",), config_text=CONFIG_OPUS)
    assert len(c["detail"]) == 1
    assert c["detail"][0]["agent_type"] == "scout"
    assert c["actual"] == pytest.approx(0.002)
    assert c["as_lead"] == pytest.approx(
        lead_counterfactual(1000, 100, 0, 0, config_text=CONFIG_OPUS))
    assert c["gross_savings"] == pytest.approx(c["as_lead"] - 0.002)


def test_api_contour_summary_groups_by_kind(db):
    db.execute("INSERT INTO requests VALUES ('2026-07-09','judge-groq',0.01,'judge')")
    db.execute("INSERT INTO requests VALUES ('2026-07-09','lead-sonnet',0.02,'synthetic')")
    db.execute("INSERT INTO requests VALUES ('2026-07-10','lead-sonnet',0.03,'synthetic')")
    a = api_contour_summary(db)
    assert a["total_n"] == 3
    assert a["total_cost"] == pytest.approx(0.06)
    kinds = {k: (n, c) for k, n, c in a["kinds"]}
    assert kinds["synthetic"][0] == 2
