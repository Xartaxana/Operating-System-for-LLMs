"""Тесты tools/calibration_prepass.py -- Phase 5 W2a (t-491).

Канонический прогон: python -m pytest tools/test_calibration_prepass.py -q

Покрытие: DoD-ключи A10/AM-7 (поля AM-1, предикаты A3+AM-3, вывод
AM-2, --check-form AM-7), адверсариальная батарея A10+AM-7, оба края
каждого лимита (правило 6а builder.md). Фикстуры -- синтетические
маленькие протоколы/журналы в tmp_path; реальный протокол трогается
только READ-ONLY (canon-прогон в конце файла), запись НИКОГДА.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

import calibration_prepass as prep

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Фикстуры-хелперы
# ---------------------------------------------------------------------------

def wrap_protocol(body: str) -> str:
    return (
        "# Test Protocol\n\nВходные данные: тест.\n\n"
        "## Чек-лист (механизм → нарушение → как проверить)\n\n"
        + body
        + "\n## Завершение прогона\n\nхвост\n"
    )


def write_protocol(tmp_path: Path, body: str, name: str = "protocol.md") -> Path:
    p = tmp_path / name
    p.write_text(wrap_protocol(body), encoding="utf-8")
    return p


def write_journal(tmp_path: Path, events: list, name: str = "journal.jsonl") -> Path:
    p = tmp_path / name
    with open(p, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return p


def write_rule_coverage(tmp_path: Path, sections: dict, name: str = "rc.md") -> Path:
    """sections: {n: text_with_tokens}"""
    p = tmp_path / name
    out = ["# RULE_COVERAGE\n"]
    for n in sorted(sections):
        out.append(f"## {n}. Секция {n}\n\n{sections[n]}\n")
    p.write_text("\n".join(out), encoding="utf-8")
    return p


DEFAULT_RC_TOKENS = {1: "| R4/D-0060: пример | ГЕЙТ | dispatch_gate реализует |\n"
                        "| R6/D-0045: эскалация | ЧЕК | реализует |\n"
                        "| R11 (пункты) | ГЕЙТ | dispatch_gate |\n",
                     2: "| D-0053: типы | ГЕЙТ | journal_validator |\n"
                        "| D-0060: append-only | ГЕЙТ | validator |\n",
                     3: "| D-0050/D-0103 handoff | СКИЛЛ | session-handoff |\n",
                     4: "| hygiene_gate: канон | ЧАСТИЧНЫЙ БЛОК-ХУК | hygiene_gate.py |\n",
                     7: "| D-0074: staging | CLI | parity_check.py |\n"}


def default_rc(tmp_path: Path) -> Path:
    return write_rule_coverage(tmp_path, DEFAULT_RC_TOKENS)


def check_form(tmp_path: Path, body: str, require_all: bool = False,
                rc_path: Path = None, repo_root: Path = None) -> prep.CheckFormResult:
    """Изоляция по умолчанию (класс-фикс 2026-08-19, узел W4-2 доделка):
    repo_root, если не задан явно, -- ТОТ ЖЕ tmp_path, что несёт
    протокол, а НЕ библиотечный дефолт REPO_ROOT (реальный корень
    репо). До фикса дефолт "не передавать repo_root вовсе" тихо
    протекал на настоящий PROCESS/checks/ -- любой файл, реально
    лежащий там, ловился как файл-сирота синтетическим протоколом,
    который его не упоминает (см. test_check_form_class_isolation_
    repo_root_pin ниже -- красная/зелёная половины класса)."""
    proto = write_protocol(tmp_path, body)
    rc = rc_path or default_rc(tmp_path)
    root = repo_root if repo_root is not None else tmp_path
    return prep.run_check_form(proto, rc, require_all, repo_root=root)


# ---------------------------------------------------------------------------
# Хелперы W4-1a: тела чеков (body/bodypred, синтетика в tmp_path/PROCESS/checks/)
# ---------------------------------------------------------------------------

def write_body_file(tmp_path: Path, check_number, content: str = None,
                     name: str = None) -> Path:
    checks_dir = tmp_path / "PROCESS" / "checks"
    checks_dir.mkdir(parents=True, exist_ok=True)
    fname = name or f"CHK-{check_number}.md"
    p = checks_dir / fname
    if content is None:
        content = (
            f"# CHK-{check_number}\n\n"
            f"ВЛАДЕЛЕЦ: Lead\n"
            f"ПРАВИЛО ВЕДЕНИЯ: живёт здесь; ядро остаётся в протоколе.\n\n"
            f"ядро -- в протоколе, чек {check_number}.\n"
        )
    p.write_bytes(content.encode("utf-8"))
    return p


def body_header_check(number: int = 0, body_path: str = None, bodypred: str = "always",
                       extra_core: str = "доп. содержимое ядра, чтобы ядро не было пустым.",
                       pointer: bool = True, pointer_body_path: str = None) -> str:
    """Протокольный фрагмент: чек с полями body/bodypred, доп. строкой
    ядра и строкой-указателем ПОСЛЕДНЕЙ строкой ядра (§7.3/A9(8))."""
    body_path = body_path if body_path is not None else f"PROCESS/checks/CHK-{number}.md"
    pointer_body_path = pointer_body_path if pointer_body_path is not None else body_path
    fields = f"<!--CHK {number}|src:журнал|pred:always|rules:RC§1/R6|status:живой"
    if body_path:
        fields += f"|body:{body_path}"
    if bodypred:
        fields += f"|bodypred:{bodypred}"
    fields += "-->\n"
    pointer_line = ""
    if pointer:
        pointer_line = (
            f"полное тело: {pointer_body_path} (читается по вердикту пре-пасса; "
            f"при отказе пре-пасса — читается всегда)\n"
        )
    return (
        f"{number}. **Чек с телом.**\n"
        f"{fields}"
        f"    {extra_core}\n"
        f"{pointer_line}"
        "\n\n"
    )


def defects_str(result: prep.CheckFormResult) -> str:
    return "\n".join(result.defects)


# Простой валидный чек-заголовок (однострочный).
CHK0_VALID = (
    "0. **Тестовый чек ноль.**\n"
    "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
    "    тело чека ноль.\n\n"
)


# ---------------------------------------------------------------------------
# 1. Базовая форма -- позитив
# ---------------------------------------------------------------------------

def test_check_form_ok_single_check(tmp_path):
    result = check_form(tmp_path, CHK0_VALID)
    assert result.defects == [], defects_str(result)
    assert len(result.headers) == 1


def test_check_form_no_headers_is_ok(tmp_path):
    body = "0. **Чек без шапки.**\n    тело.\n\n1. **Второй чек.**\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert result.defects == []
    assert len(result.headers) == 0


def test_render_check_form_ok_text(tmp_path):
    result = check_form(tmp_path, CHK0_VALID)
    text = prep.render_check_form(result)
    assert text.startswith("FORM: OK")


def test_render_check_form_with_defects(tmp_path):
    body = "0. **Чек.**\n<!--CHK 0|src:неизвестно|pred:always|rules:RC§1/R6|status:живой-->\n    тело.\n\n"
    result = check_form(tmp_path, body)
    text = prep.render_check_form(result)
    assert text.startswith("FORM:")
    assert "ИТОГО дефектов" in text


# ---------------------------------------------------------------------------
# 2. Позиция шапки чека (AM-1 П1) -- многострочный заголовок
# ---------------------------------------------------------------------------

def test_header_after_multiline_closing_star_ok(tmp_path):
    body = (
        "0. **Многострочный за-\n"
        "    головок чека.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело чека.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_header_between_multiline_title_lines_rejected(tmp_path):
    """AM-7 битарея: шапка между строками многострочного заголовка."""
    body = (
        "0. **Многострочный за-\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    головок чека.**\n"
        "    тело чека.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("незакрытой пары" in d for d in result.defects), defects_str(result)


def test_header_at_end_of_line_with_text_rejected(tmp_path):
    """AM-7 битарея: шапка в конец строки с текстом (не занимает строку целиком)."""
    body = (
        "0. **Заголовок.**\n"
        "    текст <!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("не занимает строку целиком" in d for d in result.defects), defects_str(result)


def test_header_not_first_line_after_close_rejected(tmp_path):
    body = (
        "0. **Заголовок.**\n"
        "    строка тела ДО шапки.\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    остальное тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("не на первой строке после" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 3. Под-шапки подпунктов (AM-1 П2) -- вплетённые vs line-starting
# ---------------------------------------------------------------------------

def test_subheader_before_line_starting_marker_ok(tmp_path):
    body = (
        "0. **Чек с подпунктами.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    преамбула.\n"
        "<!--CHK 0(а)|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой-->\n"
        "    (а) первый подпункт с начала строки.\n"
        "    хвост подпункта.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_subheader_before_woven_marker_rejected(tmp_path):
    """AM-7 битарея: под-шапка перед вплетённым маркером."""
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "<!--CHK 0(а)|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой-->\n"
        "    преамбула. (а) вплетённый подпункт не с начала строки.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("вплетён" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 4. Поля -- порядок, неизвестные, дубли
# ---------------------------------------------------------------------------

def test_unknown_field_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|foo:bar-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("неизвестное поле" in d for d in result.defects), defects_str(result)


def test_broken_field_order_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|pred:always|src:журнал|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("нарушен порядок полей" in d for d in result.defects), defects_str(result)


def test_missing_required_field_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("обязательное поле отсутствует: rules" in d for d in result.defects), defects_str(result)


def test_duplicate_field_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|src:git|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("повтор поля" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 5. Два id-инварианта: две шапки на id; id != номер в тексте
# ---------------------------------------------------------------------------

def test_two_headers_same_id_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("больше 1 шапки на id" in d for d in result.defects), defects_str(result)


def test_id_mismatch_with_text_number_rejected(tmp_path):
    """id != номер в тексте: шапка ссылается на чек 5, которого нет."""
    body = (
        "0. **Чек.**\n"
        "<!--CHK 5|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("не совпадает ни с одним номером" in d or "чек 5 не найден" in d
                for d in result.defects), defects_str(result)


def test_duplicate_check_number_rejected(tmp_path):
    body = "0. **Первый.**\n    тело.\n\n0. **Дубль.**\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert any("дубль номера чека 0" in d for d in result.defects), defects_str(result)


def test_gap_in_numbering_rejected(tmp_path):
    body = "0. **Первый.**\n    тело.\n\n2. **Разрыв.**\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert any("разрыв нумерации" in d for d in result.defects), defects_str(result)


def test_contiguous_numbering_ok(tmp_path):
    body = "0. **Ноль.**\n    тело.\n\n1. **Один.**\n    тело.\n\n2. **Два.**\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert result.defects == []


# ---------------------------------------------------------------------------
# 6. Лимиты -- оба края (правило 6а)
# ---------------------------------------------------------------------------

def _header_of_len(payload_filler: str) -> str:
    """Строит шапку заданной итоговой длины через note: заполнитель."""
    base = "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|note:{}-->"
    return base.format(payload_filler)


def test_header_300_bytes_ok(tmp_path):
    base_no_note = "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|note:-->"
    pad_needed = 300 - len(base_no_note.encode("utf-8"))
    note = "x" * pad_needed
    header = _header_of_len(note)
    assert len(header.encode("utf-8")) == 300
    body = f"0. **Чек.**\n{header}\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert not any("длиннее 300" in d for d in result.defects), defects_str(result)


def test_header_301_bytes_rejected(tmp_path):
    base_no_note = "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|note:-->"
    pad_needed = 301 - len(base_no_note.encode("utf-8"))
    note = "x" * pad_needed
    header = _header_of_len(note)
    assert len(header.encode("utf-8")) == 301
    body = f"0. **Чек.**\n{header}\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert any("длиннее 300" in d for d in result.defects), defects_str(result)


def test_src_4_values_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал,git,cc_usage,файлы|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_src_5_values_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал,git,cc_usage,файлы,оператор|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("значений 5 > 4" in d for d in result.defects), defects_str(result)


def test_headers_per_id_1_ok(tmp_path):
    result = check_form(tmp_path, CHK0_VALID)
    assert result.defects == []


def test_headers_per_id_2_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("больше 1 шапки" in d for d in result.defects), defects_str(result)


def test_id_len_12_ok(tmp_path):
    # "0(деферред1)" -- 12 символов (посчитано ниже явно, не на глаз).
    id_str = "0(" + "б" * 9 + ")"
    assert len(id_str) == 12
    body = (
        "0. **Чек с подпунктами.**\n"
        f"<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        f"<!--CHK {id_str}|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        f"    ({'б' * 9}) подпункт с начала строки.\n\n"
    )
    result = check_form(tmp_path, body)
    assert not any("длиннее 12" in d for d in result.defects), defects_str(result)


def test_id_len_13_rejected(tmp_path):
    id_str = "0(" + "б" * 10 + ")"
    assert len(id_str) == 13
    body = (
        "0. **Чек с подпунктами.**\n"
        f"<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        f"<!--CHK {id_str}|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        f"    ({'б' * 10}) подпункт.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("длиннее 12" in d for d in result.defects), defects_str(result)


def test_rules_4_values_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6,RC§1/R4,RC§2/D-0053,RC§2/D-0060|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_rules_5_values_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|"
        "rules:RC§1/R6,RC§1/R4,RC§2/D-0053,RC§2/D-0060,RC§7/D-0074|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("значений 5 > 4" in d for d in result.defects), defects_str(result)


def test_fields_8_max_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "cand:manual:x|since:2026-08-18|note:абв-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert not any("полей больше" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 7. Предикаты -- закрытый список, неизвестные, пробел в значении
# ---------------------------------------------------------------------------

def test_unknown_predicate_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:frobnicate|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("не резолвящийся предикат" in d for d in result.defects), defects_str(result)


def test_unknown_src_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:призраки|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("неизвестное значение" in d for d in result.defects), defects_str(result)


def test_space_in_value_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:manual:some reason|rules:RC§1/R6|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("пробел" in d for d in result.defects), defects_str(result)


@pytest.mark.parametrize("pred", [
    "always", "journal.any", "journal.event:rejected",
    "journal.event:accepted,agent=builder", "journal.field:failure_class=spec",
    "journal.parallel_groups", "git.any", "git.paths:tools/**",
    "git.paths:tools/**,gateway/**@OS", "git.diff_lines:>100",
    "path.exists:tools", "deploy.exists:ao3", "script:parity_check",
    "manual:транскрипты",
])
def test_all_closed_predicates_valid(pred):
    assert prep.validate_predicate_value(pred) is None, pred


def test_git_paths_at_deploy_suffix_valid():
    assert prep.validate_predicate_value("git.paths:foo,bar@AO3") is None


# ---------------------------------------------------------------------------
# 8. rules: резолюция в обе стороны
# ---------------------------------------------------------------------------

def test_rules_forward_missing_section_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§99/Foo|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("секции 99 нет" in d for d in result.defects), defects_str(result)


def test_rules_forward_missing_token_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/НЕТТАКОГО|status:живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("token не найден" in d for d in result.defects), defects_str(result)


def test_rules_backward_unknown_check_rejected(tmp_path):
    rc = write_rule_coverage(tmp_path, {
        1: "смотри чек 77 за подробностями (не существует в этом протоколе)",
    })
    body = "0. **Чек.**\n    тело.\n\n"
    result = check_form(tmp_path, body, rc_path=rc)
    assert any("чек 77" in d for d in result.defects), defects_str(result)


def test_rules_backward_known_check_ok(tmp_path):
    rc = write_rule_coverage(tmp_path, {1: "смотри чек 0 за подробностями"})
    body = "0. **Чек.**\n    тело.\n\n"
    result = check_form(tmp_path, body, rc_path=rc)
    assert result.defects == [], defects_str(result)


def test_rule_coverage_missing_file_is_form_error(tmp_path):
    proto = write_protocol(tmp_path, "0. **Чек.**\n    тело.\n\n")
    result = prep.run_check_form(proto, tmp_path / "no-such-rc.md", False)
    assert any("RULE_COVERAGE не найден" in d for d in result.defects)


# ---------------------------------------------------------------------------
# 9. status: живой/ретирован/деферред + AM-1 П3 (cand:, note:)
# ---------------------------------------------------------------------------

def test_retired_without_liveness_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:ретирован:2026-08-18;сторож:x-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("сторож:/живость:" in d for d in result.defects), defects_str(result)


def test_retired_full_form_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|"
        "status:ретирован:2026-08-18;сторож:x;живость:pytest tools/test_x.py -->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_deferred_without_trigger_predicate_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:деферред:frobnicate-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("деферред-предикат невалиден" in d for d in result.defects), defects_str(result)


def test_deferred_valid_trigger_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:деферред:path.exists:tools/x.py-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_cand_at_retired_status_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|"
        "status:ретирован:2026-08-18;сторож:x;живость:y|cand:manual:z-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("cand: легален только при status:живой" in d for d in result.defects), defects_str(result)


def test_cand_unknown_predicate_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|cand:frobnicate-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("cand:" in d and "не резолвящийся" in d for d in result.defects), defects_str(result)


def test_cand_valid_at_live_status_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|cand:path.exists:tools/x.py-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_note_with_trigger_substring_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "note:кандидат(триггер:path.exists)-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("триггер" in d for d in result.defects), defects_str(result)


def test_note_without_trigger_ok(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|note:просто-пометка-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert result.defects == [], defects_str(result)


def test_unknown_status_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:полу-живой-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body)
    assert any("неизвестное значение" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 10. deploy.exists -- AM-3 (хардкод в исходнике -- негатив)
# ---------------------------------------------------------------------------

def test_no_hardcoded_deploy_path_in_source():
    source = Path(prep.__file__).read_text(encoding="utf-8")
    assert prep.validate_no_hardcoded_deploy_path(source) == []


def test_hardcoded_deploy_path_detector_fires_on_injected_copy():
    """Негативный кейс AM-3.6: инжектируем ЛИТЕРАЛЬНЫЙ путь в КОПИЮ
    текста (не трогаем реальный файл, гигиена п.7г) и убеждаемся, что
    детектор ловит форму."""
    fake_source = "AO3_ROOT = r'D:\\\\AO3_tests'  # захардкожено умышленно для теста"
    errors = prep.validate_no_hardcoded_deploy_path(fake_source)
    assert errors, "детектор обязан найти захардкоженный путь в инжектированной копии"


def test_deploy_resolve_cli_priority(tmp_path):
    cfg = tmp_path / "delegation.config.yaml"
    cfg.write_text("deploys:\n  ao3: D:\\from-config\n", encoding="utf-8")
    res = prep.resolve_deploy("ao3", {"ao3": str(tmp_path)}, cfg)
    assert res.source == "CLI --deploy"
    assert res.path == str(tmp_path)
    assert res.exists is True


def test_deploy_resolve_config_when_no_cli(tmp_path):
    target = tmp_path / "real-deploy"
    target.mkdir()
    cfg = tmp_path / "delegation.config.yaml"
    cfg.write_text(f"deploys:\n  ao3: {target.as_posix()}\n", encoding="utf-8")
    res = prep.resolve_deploy("ao3", {}, cfg)
    assert res.source == "delegation.config.yaml"
    assert res.exists is True


def test_deploy_resolve_env_fallback(tmp_path, monkeypatch):
    cfg = tmp_path / "no-such-config.yaml"
    monkeypatch.setenv("OSLLM_DEPLOY_AO3", str(tmp_path))
    res = prep.resolve_deploy("ao3", {}, cfg)
    assert res.source == "env"
    assert res.exists is True


def test_deploy_resolve_unresolved(tmp_path, monkeypatch):
    monkeypatch.delenv("OSLLM_DEPLOY_AO3", raising=False)
    cfg = tmp_path / "no-such-config.yaml"
    res = prep.resolve_deploy("ao3", {}, cfg)
    assert res.source == "unresolved"
    assert res.path is None


def test_deploy_resolve_real_current_config_resolves_ao3():
    """Темпоральный край AM-3 (2) — мир ПОСЛЕ: ключ deploys.ao3 заведён
    посадочным коммитом M1 (Р11(A), акт Lead 2026-08-18) -- шаг 2
    резолюции работает по живому delegation.config.yaml. Мир ДО
    (ключа нет) остаётся покрыт синтетикой на tmp_path-конфигах;
    перевёрнуто Lead тем же коммитом, что завёл ключ (D-0069)."""
    res = prep.resolve_deploy("ao3", {}, prep.DEFAULT_CONFIG)
    assert res.source == "delegation.config.yaml"
    assert res.path == r"D:\AO3_tests"


def test_deploy_empty_cli_value_falls_through(tmp_path, monkeypatch):
    """AM-7 битарея: --deploy с пустым значением."""
    monkeypatch.delenv("OSLLM_DEPLOY_AO3", raising=False)
    cfg = tmp_path / "no-such-config.yaml"
    res = prep.resolve_deploy("ao3", {"ao3": ""}, cfg)
    assert res.source != "CLI --deploy"


def test_parse_deploys_empty_value_ok():
    d = prep.parse_deploys(["ao3="])
    assert d == {"ao3": ""}


def test_parse_deploys_missing_equals_raises():
    with pytest.raises(ValueError):
        prep.parse_deploys(["ao3"])


def test_deploy_exists_predicate_unconfigured_is_alive(tmp_path, monkeypatch):
    monkeypatch.delenv("OSLLM_DEPLOY_AO3", raising=False)
    ctx = prep.build_journal_context([], None, None)
    run_ctx = prep.RunContext(
        journal_ctx=ctx, repo_root=str(tmp_path), window_start_iso="2026-01-01T00:00:00",
        window_end_iso="2026-01-02T00:00:00", cli_deploys={},
        config_path=tmp_path / "no-config.yaml",
    )
    ev = prep.evaluate_predicate("deploy.exists:ao3", run_ctx)
    assert ev.alive is True
    assert "не сконфигурирован" in ev.reason


def test_deploy_exists_predicate_missing_path_is_empty(tmp_path):
    ctx = prep.build_journal_context([], None, None)
    run_ctx = prep.RunContext(
        journal_ctx=ctx, repo_root=str(tmp_path), window_start_iso="2026-01-01T00:00:00",
        window_end_iso="2026-01-02T00:00:00",
        cli_deploys={"ao3": str(tmp_path / "does-not-exist")},
        config_path=tmp_path / "no-config.yaml",
    )
    ev = prep.evaluate_predicate("deploy.exists:ao3", run_ctx)
    assert ev.alive is False
    assert "позитивный контроль" in ev.reason


def test_deploy_exists_predicate_present_path_is_alive(tmp_path):
    d = tmp_path / "deploy-root"
    d.mkdir()
    ctx = prep.build_journal_context([], None, None)
    run_ctx = prep.RunContext(
        journal_ctx=ctx, repo_root=str(tmp_path), window_start_iso="2026-01-01T00:00:00",
        window_end_iso="2026-01-02T00:00:00", cli_deploys={"ao3": str(d)},
        config_path=tmp_path / "no-config.yaml",
    )
    ev = prep.evaluate_predicate("deploy.exists:ao3", run_ctx)
    assert ev.alive is True


# ---------------------------------------------------------------------------
# 11. --require-all
# ---------------------------------------------------------------------------

def test_require_all_flags_unheaded_checks(tmp_path):
    body = "0. **Есть шапка.**\n" + CHK0_VALID.split("\n", 1)[1]
    body += "1. **Без шапки.**\n    тело.\n\n"
    result = check_form(tmp_path, body, require_all=True)
    assert any("--require-all" in d and "чек 1" in d for d in result.defects), defects_str(result)


def test_require_all_off_by_default_ok(tmp_path):
    body = "0. **Есть шапка.**\n" + CHK0_VALID.split("\n", 1)[1]
    body += "1. **Без шапки.**\n    тело.\n\n"
    result = check_form(tmp_path, body, require_all=False)
    assert not any("--require-all" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 12. Пустой протокол / протокол без чеков / не-UTF-8 / CRLF
# ---------------------------------------------------------------------------

def test_protocol_without_any_check_is_protocol_error(tmp_path):
    p = tmp_path / "empty.md"
    p.write_text("## Чек-лист\n\nничего тут нет.\n\n## Завершение прогона\n", encoding="utf-8")
    with pytest.raises(prep.ProtocolError, match="форма не распознана"):
        prep.run_check_form(p, default_rc(tmp_path), False)


def test_protocol_missing_file_is_protocol_error(tmp_path):
    with pytest.raises(prep.ProtocolError, match="не найден"):
        prep.run_check_form(tmp_path / "nope.md", default_rc(tmp_path), False)


def test_protocol_not_utf8_is_protocol_error(tmp_path):
    p = tmp_path / "bad.md"
    p.write_bytes(b"\xff\xfe## \xd0\xa7\xd0\xb5\xd0\xba-\xd0\xbb\xb8\xd1\x81\xd1\x82")
    with pytest.raises(prep.ProtocolError, match="UTF-8"):
        prep.run_check_form(p, default_rc(tmp_path), False)


def test_protocol_crlf_normalized_ok(tmp_path):
    p = tmp_path / "crlf.md"
    p.write_bytes(wrap_protocol(CHK0_VALID).replace("\n", "\r\n").encode("utf-8"))
    result = prep.run_check_form(p, default_rc(tmp_path), False, repo_root=tmp_path)
    assert result.defects == [], defects_str(result)


def test_header_line_over_1mb_is_flagged(tmp_path):
    """Строка >1 МБ -- шапка не матчится штатной формой (превышает лимит
    задолго до 1 МБ), no crash, дефект формы, а не исключение."""
    huge_note = "x" * (1024 * 1024)
    body = f"0. **Чек.**\n<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|note:{huge_note}-->\n    тело.\n\n"
    result = check_form(tmp_path, body)
    assert any("длиннее 300" in d for d in result.defects)


# ---------------------------------------------------------------------------
# 13. Окно / предикаты -- поведение прогона
# ---------------------------------------------------------------------------

def _run_ctx_for(tmp_path, journal_paths, window_start_iso, window_end_iso, deploys=None):
    from datetime import datetime
    ws = prep.cc.parse_ts(window_start_iso)
    we = prep.cc.parse_ts(window_end_iso)
    ctx = prep.build_journal_context(journal_paths, ws, we)
    return prep.RunContext(
        journal_ctx=ctx, repo_root=str(tmp_path), window_start_iso=window_start_iso,
        window_end_iso=window_end_iso, cli_deploys=deploys or {},
        config_path=tmp_path / "no-config.yaml",
    )


def test_journal_any_alive_when_events_present(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-08-15T10:00:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet"},
    ])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.any", run_ctx)
    assert ev.alive is True
    assert ev.observed == 1 and ev.denom == 1


def test_journal_any_empty_window_is_pust_with_denominator(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-01-01T10:00:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet"},
    ])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.any", run_ctx)
    assert ev.alive is False
    assert ev.observed == 0 and ev.denom == 0


def test_journal_event_with_agent_filter(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-08-15T10:00:00", "event": "accepted", "agent": "scout",
         "category": "recon", "notes": "x", "task_id": "t-1", "model": "sonnet", "by": "opus"},
        {"ts": "2026-08-15T11:00:00", "event": "accepted", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-2", "model": "sonnet",
         "by": "opus", "witness": "ok"},
    ])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.event:accepted,agent=builder", run_ctx)
    assert ev.alive is True
    assert ev.observed == 1
    assert ev.denom == 2


def test_journal_field_predicate(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-08-15T10:00:00", "event": "rejected", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet",
         "by": "opus", "attempt": 1, "failure_class": "spec"},
    ])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.field:failure_class=spec", run_ctx)
    assert ev.alive is True and ev.observed == 1


def test_journal_missing_file_predicate_is_alive_fail_closed(tmp_path):
    run_ctx = _run_ctx_for(tmp_path, [str(tmp_path / "no-such-journal.jsonl")],
                            "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.any", run_ctx)
    assert ev.alive is True
    assert "журнал отсутствует" in ev.reason


def test_unparsable_journal_line_warns_and_journal_stays_alive(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"ts": "2026-08-15T10:00:00", "event": "delegated"\n'  # обрезанный JSON
                 '{"ts": "2026-08-15T11:00:00", "event": "delegated", "agent": "builder", '
                 '"category": "implementation", "notes": "ok", "task_id": "t-1", "model": "sonnet"}\n',
                 encoding="utf-8")
    run_ctx = _run_ctx_for(tmp_path, [str(p)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    assert run_ctx.journal_ctx.unparsable_count == 1
    ev = prep.evaluate_predicate("journal.event:delegated", run_ctx)
    assert ev.alive is True


def test_path_exists_predicate_missing_is_alive_fail_closed(tmp_path):
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("path.exists:no/such/path/here", run_ctx)
    assert ev.alive is True
    assert "не существует" in ev.reason


def test_manual_predicate_always_alive():
    run_ctx = _run_ctx_for(Path("."), [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("manual:транскрипты", run_ctx)
    assert ev.alive is True
    assert ev.empty_reasons_needed is False


def test_script_predicate_prints_known_command():
    run_ctx = _run_ctx_for(Path("."), [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("script:parity_check", run_ctx)
    assert ev.alive is True
    assert "parity_check.py" in ev.reason


def test_parallel_groups_detects_overlap(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-08-15T10:00:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet",
         "worker_ref": "agent:aaa"},
        {"ts": "2026-08-15T10:05:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "y", "task_id": "t-2", "model": "sonnet",
         "worker_ref": "agent:bbb"},
        {"ts": "2026-08-15T10:30:00", "event": "accepted", "agent": "builder",
         "category": "implementation", "notes": "z", "task_id": "t-1", "model": "sonnet",
         "by": "opus", "witness": "ok"},
        {"ts": "2026-08-15T10:35:00", "event": "accepted", "agent": "builder",
         "category": "implementation", "notes": "z", "task_id": "t-2", "model": "sonnet",
         "by": "opus", "witness": "ok"},
    ])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.parallel_groups", run_ctx)
    assert ev.alive is True
    assert ev.observed >= 1


def test_parallel_groups_no_overlap_is_empty(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-08-15T10:00:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet",
         "worker_ref": "agent:aaa"},
        {"ts": "2026-08-15T10:10:00", "event": "accepted", "agent": "builder",
         "category": "implementation", "notes": "z", "task_id": "t-1", "model": "sonnet",
         "by": "opus", "witness": "ok"},
        {"ts": "2026-08-15T11:00:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-2", "model": "sonnet",
         "worker_ref": "agent:bbb"},
        {"ts": "2026-08-15T11:10:00", "event": "accepted", "agent": "builder",
         "category": "implementation", "notes": "z", "task_id": "t-2", "model": "sonnet",
         "by": "opus", "witness": "ok"},
    ])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("journal.parallel_groups", run_ctx)
    assert ev.alive is False


# ---------------------------------------------------------------------------
# 14. build_window_report -- вердикты/диапазоны/ИТОГ/сайдкар
# ---------------------------------------------------------------------------

def _pilot_body():
    return (
        "0. **Ноль.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    тело нуля.\n\n"
        "1. **Один, чек-лист-эталон.**\n"
        "<!--CHK 1|src:журнал|pred:journal.event:rejected|rules:RC§1/R6|status:живой-->\n"
        "    тело один.\n\n"
        "2. **Ретированный чек целиком.**\n"
        "<!--CHK 2|src:файлы|pred:always|rules:RC§1/R9|"
        "status:ретирован:2026-08-18;сторож:x;живость:pytest tools/test_x.py -->\n"
        "    тело два (не должно читаться).\n\n"
        "3. **Чек с подпунктами.**\n"
        "<!--CHK 3|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой-->\n"
        "    преамбула.\n"
        "<!--CHK 3(а)|src:журнал|pred:journal.event:defect_found|rules:RC§1/R6|status:живой-->\n"
        "    (а) пустой подпункт с начала строки.\n"
        "<!--CHK 3(б)|src:файлы|pred:always|"
        "rules:RC§1/R9|status:ретирован:2026-08-18;сторож:y;живость:pytest tools/test_y.py -->\n"
        "    (б) ретированный подпункт с начала строки.\n\n"
    )


def test_build_window_report_verdicts(tmp_path):
    j = write_journal(tmp_path, [
        {"ts": "2026-08-15T10:00:00", "event": "rejected", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet",
         "by": "opus", "attempt": 1, "failure_class": "spec"},
    ])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    by_id = {cv.id_str: cv.verdict for cv in report["check_verdicts"]}
    assert by_id["0"] == "ЖИВ"
    assert by_id["1"] == "ЖИВ"
    assert by_id["2"] == "РЕТИРОВАН"
    assert by_id["3"] == "ЖИВ"
    subs = {s.id_str: s.verdict for s in report["subitem_verdicts"][3]}
    assert subs["3(а)"] == "ПУСТ"
    assert subs["3(б)"] == "РЕТИРОВАН"
    assert report["total_checks"] == 4
    # РЕТИРОВАН/ПУСТ байты не входят в to_read (адресный диапазон).
    assert report["to_read_bytes"] < report["total_bytes"]


def test_retired_subitem_range_does_not_bleed_into_alive_tail(tmp_path):
    """Регрессия найденного при посадке K2/K4 дефекта: диапазон
    ПОСЛЕДНЕГО ретированного подпункта тянулся до конца чека и молча
    поглощал НЕСВЯЗАННЫЙ живой хвост (реальный случай -- 12(б)/12(в) в
    протоколе). Без замыкающего живого подпункта после ретированного
    живой хвост обязан ОСТАВАТЬСЯ в "остатке" родителя, не пропадать
    из to_read."""
    body = (
        "0. **Чек с ретированным подпунктом посередине.**\n"
        "<!--CHK 0|src:файлы|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    преамбула.\n"
        "<!--CHK 0(а)|src:файлы|pred:always|rules:RC§1/R6|"
        "status:ретирован:2026-08-18;сторож:x;живость:pytest tools/test_x.py -->\n"
        "    (а) короткий ретированный фрагмент.\n"
        "<!--CHK 0(б)|src:файлы|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    (б) длинный ЖИВОЙ хвост, который НЕ должен быть снят "
        "вместе с (а) только потому, что идёт последним в чеке -- "
        "много слов, чтобы диапазон был заметно больше нуля байт.\n\n"
    )
    proto = write_protocol(tmp_path, body)
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    subs = {s.id_str: s for s in report["subitem_verdicts"][0]}
    assert subs["0(а)"].verdict == "РЕТИРОВАН"
    assert subs["0(б)"].verdict == "ЖИВ"
    # Живой хвост -- не тонет: его собственный размер учтён в to_read.
    assert subs["0(б)"].byte_size > 50
    cv = next(cv for cv in report["check_verdicts"] if cv.id_str == "0")
    remainder = cv.byte_size - sum(s.byte_size for s in subs.values())
    to_read_for_check0 = remainder + subs["0(б)"].byte_size  # 0(а) РЕТИРОВАН снят
    assert report["to_read_bytes"] >= to_read_for_check0


def test_empty_lines_have_denominator_format(tmp_path):
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["empty_lines"], "ожидались пустые чеки"
    for line in report["empty_lines"]:
        assert " из " in line, f"ПУСТ без знаменателя: {line!r}"


def test_empty_window_all_empty_except_always_manual(tmp_path):
    """A3 edge 1: пустое окно -- все не-always/manual ПУСТЫ."""
    j = write_journal(tmp_path, [
        {"ts": "2026-01-01T00:00:00", "event": "delegated", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-0", "model": "sonnet"},
    ])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    by_id = {cv.id_str: cv.verdict for cv in report["check_verdicts"]}
    assert by_id["0"] == "ЖИВ"          # always
    assert by_id["1"] == "ПУСТ"          # journal.event:rejected, окно пусто


def test_perevzvedenie_on_true_cand(tmp_path):
    existing = tmp_path / "existing-marker.py"
    existing.write_text("x", encoding="utf-8")
    body = (
        "0. **Чек с cand.**\n"
        "<!--CHK 0|src:файлы|pred:always|rules:RC§1/R6|status:живой|"
        "cand:path.exists:existing-marker.py-->\n"
        "    тело.\n\n"
    )
    proto = write_protocol(tmp_path, body)
    # cand-предикат резолвится относительно repo_root -- используем
    # tmp_path и как repo_root, и как место фикстуры.
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["perevzvedenie_lines"], "cand-триггер истинен -> обязана быть ПЕРЕВЗВЕДЕНИЕ"
    assert "кандидат-ретирования" in report["perevzvedenie_lines"][0]


def test_perevzvedenie_on_true_deferred_trigger(tmp_path):
    existing = tmp_path / "exists.txt"
    existing.write_text("x", encoding="utf-8")
    body = (
        "0. **Деферред чек.**\n"
        f"<!--CHK 0|src:файлы|pred:always|rules:RC§1/R6|status:деферред:path.exists:exists.txt-->\n"
        "    тело.\n\n"
    )
    proto = write_protocol(tmp_path, body)
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["perevzvedenie_lines"], "триггер истинен -> обязана быть строка ПЕРЕВЗВЕДЕНИЕ"


def test_registry_write_and_read(tmp_path):
    reg = tmp_path / "registry.jsonl"
    proto = write_protocol(tmp_path, _pilot_body())
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    prep.write_registry_entry(reg, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный",
                               "test", report, None)
    entries, bad_count = prep.read_registry(reg)
    assert len(entries) == 1
    assert entries[0]["alive_count"] == report["alive_count"]
    assert bad_count == 0


def _make_hermetic_git_repo(tmp_path: Path) -> Path:
    """Изолированный git-репозиторий БЕЗ единой правки шапок в истории --
    для тестов determine_mode/last_header_touching_commit, которым НЕ
    нужен live REPO_ROOT (класс «неинъектируемый дефолт/боевой артефакт
    тянется в тестовый контекст», фикс-батч калибровки №7, 2026-08-14;
    находка t-493: живой REPO_ROOT в determine_mode ловил РЕАЛЬНЫЙ
    коммит правки шапок M1 (3280086) и молча переключал ветку триггера
    с периодической на событийную -- тест ломался НАВСЕГДА после любого
    коммита, трогающего <!--CHK. Герметичный git-репозиций без такого
    коммита -- честная проверка ИМЕННО периодической/explicit-веток, не
    мок функции: последующая правка шапок в живом репо больше не может
    задеть этот тест, потому что git log здесь смотрит СВОЁ дерево."""
    repo = tmp_path / "hermetic-git-repo"
    repo.mkdir()
    run = lambda *args: subprocess.run(  # noqa: E731
        args, cwd=str(repo), check=True, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    run("git", "init", "-q")
    run("git", "config", "user.email", "hermetic@test.local")
    run("git", "config", "user.name", "hermetic-test")
    (repo / "dummy.txt").write_text("никаких <!--CHK-- здесь нет", encoding="utf-8")
    run("git", "add", "dummy.txt")
    run("git", "commit", "-q", "-m", "init, без правок шапок")
    return repo


def test_control_mode_periodic_trigger(tmp_path):
    hermetic_repo = _make_hermetic_git_repo(tmp_path)
    reg = tmp_path / "registry.jsonl"
    for i in range(3):
        with open(reg, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"mode": "обычный (x)"}) + "\n")
    entries, bad_count = prep.read_registry(reg)
    mode, reason = prep.determine_mode(entries, str(hermetic_repo),
                                        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md", False)
    assert mode == "КОНТРОЛЬНЫЙ"
    assert "N=4" in reason
    assert bad_count == 0


def test_control_mode_event_trigger_after_header_commit(tmp_path):
    """Обратная сторона того же герметичного репо -- живой A3.8(б)-
    сценарий БЕЗ живого REPO_ROOT: коммит, тронувший <!--CHK, обязан
    включить событийный триггер (сильнее периодического), даже когда
    периодический порог N=4 ещё не выбит (всего 1 запись реестра)."""
    hermetic_repo = _make_hermetic_git_repo(tmp_path)
    protocol_rel = "protocol.md"
    (hermetic_repo / protocol_rel).write_text(
        "0. **Чек.**\n<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", protocol_rel], cwd=str(hermetic_repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "добавлена шапка"],
                    cwd=str(hermetic_repo), check=True)
    reg = tmp_path / "registry2.jsonl"
    with open(reg, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"mode": "обычный (x)"}) + "\n")
    entries, bad_count = prep.read_registry(reg)
    mode, reason = prep.determine_mode(entries, str(hermetic_repo),
                                        protocol_rel, False)
    assert mode == "КОНТРОЛЬНЫЙ"
    assert "правк" in reason and "шапок" in reason
    assert bad_count == 0


def test_control_mode_explicit_flag(tmp_path):
    # explicit_control=True возвращает результат ДО обращения к git log
    # (короткое замыкание в самом начале determine_mode) -- repo_root
    # здесь намеренно НЕ живой REPO_ROOT и даже не существующий путь:
    # значение доказуемо не используется в этой ветке (см. R9-перечень
    # в отчёте), заведомо синтетическая строка документирует это.
    mode, reason = prep.determine_mode([], "/nonexistent/repo/for/this/branch",
                                        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md", True)
    assert mode == "КОНТРОЛЬНЫЙ"
    assert "--control" in reason


def test_run_control_check_flags_missing_denominator():
    cv = prep.CheckVerdict(check_number=0, id_str="0", verdict="ПУСТ",
                            line_range=(1, 1), byte_size=10, reason="always -- нет счётчика",
                            has_header=True)
    report = {"check_verdicts": [cv], "subitem_verdicts": {}}
    n_empty, n_disc, lines = prep.run_control_check(report)
    assert n_empty == 1 and n_disc == 1


def test_run_control_check_ok_with_denominator():
    cv = prep.CheckVerdict(check_number=0, id_str="0", verdict="ПУСТ",
                            line_range=(1, 1), byte_size=10,
                            reason="journal.any -> 0 из 5 строк окна", has_header=True)
    report = {"check_verdicts": [cv], "subitem_verdicts": {}}
    n_empty, n_disc, lines = prep.run_control_check(report)
    assert n_empty == 1 and n_disc == 0


# ---------------------------------------------------------------------------
# 15. CLI: аргументы, коды выхода
# ---------------------------------------------------------------------------

def run_cli(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "calibration_prepass.py")] + args,
        capture_output=True, text=True, cwd=cwd or str(REPO_ROOT),
        encoding="utf-8", errors="replace",
        env={**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )


def run_cli_isolated(args, tmp_path):
    """Класс-фикс 2026-08-19 (доделка W4-2): CLI-форма REPO_ROOT
    считает от __file__, не от cwd/env, и --repo-root в CLI нет --
    calibration_prepass.py вне owns этого узла, правка источника
    (сигнатуры main()/run_check_form()) нелегальна. Изоляция БЕЗ
    правки источника: байт-копия calibration_prepass.py + сиблинга
    calibration_counts.py (его единственный внутренний импорт,
    добавляемый в sys.path от СВОЕГО __file__) в <tmp>/iso_repo/tools/
    -- запущенный ОТТУДА процесс резолвит REPO_ROOT = <tmp>/iso_repo,
    где PROCESS/checks/ не существует вовсе -- орфан-проверка (9)
    молчит по КОНСТРУКЦИИ (checks_dir.is_dir() -- False), не потому
    что ослаблена. enforcement_probe.py не копируется: --check-form не
    вызывает evaluate_predicate, отказ импорта (ep=None) безвреден и
    предусмотрен кодом (A14ж)."""
    iso_root = tmp_path / "iso_repo"
    iso_tools = iso_root / "tools"
    iso_tools.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "tools" / "calibration_prepass.py",
                iso_tools / "calibration_prepass.py")
    shutil.copy(REPO_ROOT / "tools" / "calibration_counts.py",
                iso_tools / "calibration_counts.py")
    return subprocess.run(
        [sys.executable, str(iso_tools / "calibration_prepass.py")] + args,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        env={**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
    )


def test_cli_check_form_exit0_on_clean(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    rc = default_rc(tmp_path)
    proc = run_cli_isolated(["--check-form", "--protocol", str(proto),
                              "--rule-coverage", str(rc)], tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cli_check_form_exit1_on_defect(tmp_path):
    """Класс-фикс 2026-08-19 (доделка W4-2, D-0100): изолированное
    дерево -- иначе exit 1 зелен по ЛОЖНОЙ причине (реальный
    PROCESS/checks/ даёт свои орфан-дефекты независимо от того,
    сработал ли ЗАДУМАННЫЙ дефект этого теста); проверяем И код, И
    что в выводе именно ожидаемый дефект (src:неизвестно)."""
    body = "0. **Чек.**\n<!--CHK 0|src:неизвестно|pred:always|rules:RC§1/R6|status:живой-->\n    тело.\n\n"
    proto = write_protocol(tmp_path, body)
    rc = default_rc(tmp_path)
    proc = run_cli_isolated(["--check-form", "--protocol", str(proto),
                              "--rule-coverage", str(rc)], tmp_path)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "src: неизвестное значение" in proc.stdout, proc.stdout + proc.stderr


def test_cli_missing_window_start_exit2():
    proc = run_cli([])
    assert proc.returncode == 2


def test_cli_invalid_window_start_exit2():
    proc = run_cli(["--window-start", "не-ISO-дата"])
    assert proc.returncode == 2


def test_cli_invalid_window_end_exit2():
    proc = run_cli(["--window-start", "2026-08-14T00:00:00", "--window-end", "не-ISO"])
    assert proc.returncode == 2


def test_cli_end_before_start_exit2():
    proc = run_cli(["--window-start", "2026-08-16T00:00:00",
                     "--window-end", "2026-08-14T00:00:00"])
    assert proc.returncode == 2


def test_cli_zero_width_window_exit0(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    proc = run_cli([
        "--window-start", "2026-08-14T00:00:00", "--window-end", "2026-08-14T00:00:00",
        "--protocol", str(proto), "--journal", str(j), "--registry", str(reg),
        "--rule-coverage", str(default_rc(tmp_path)),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cli_protocol_without_checks_exit2(tmp_path):
    p = tmp_path / "empty.md"
    p.write_text("## Чек-лист\n\nпусто.\n\n## Завершение прогона\n", encoding="utf-8")
    j = write_journal(tmp_path, [])
    proc = run_cli(["--window-start", "2026-08-14T00:00:00", "--protocol", str(p),
                     "--journal", str(j), "--registry", str(tmp_path / "reg.jsonl")])
    assert proc.returncode == 2


def test_cli_not_git_repo_git_predicate_fail_closed(tmp_path):
    """Не git-репо: git.* предикаты не крэшат, ЖИВ (fail-closed)."""
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.any", run_ctx)
    assert ev.alive is True


def test_cli_json_output_window_mode(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    proc = run_cli([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(tmp_path / "reg.jsonl"),
        "--rule-coverage", str(default_rc(tmp_path)), "--json",
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert "verdicts" in payload and payload["verdicts"]["0"] == "ЖИВ"


def test_cli_unknown_argument_exit2():
    """AM-7/A10 битарея: неизвестный CLI-аргумент (argparse default)."""
    proc = run_cli(["--window-start", "2026-08-14T00:00:00", "--frobnicate"])
    assert proc.returncode == 2


def test_cli_control_flag_forces_control_mode(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    proc = run_cli([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(tmp_path / "reg.jsonl"),
        "--rule-coverage", str(default_rc(tmp_path)), "--control",
    ])
    assert proc.returncode == 0
    assert "КОНТРОЛЬНЫЙ" in proc.stdout
    assert "контрольный прочит" in proc.stdout


# ---------------------------------------------------------------------------
# 16. Инвариант предиката -- необходимое условие (A3, документируется тестом)
# ---------------------------------------------------------------------------

def test_predicate_never_hides_material_journal_event_superset_of_field():
    """Смысловая регрессия инварианта: predicate journal.any живёт, когда
    ЛЮБОЙ более узкий journal.* предикат жив (необходимое условие)."""
    events = [
        {"ts": "2026-08-15T10:00:00", "event": "rejected", "agent": "builder",
         "category": "implementation", "notes": "x", "task_id": "t-1", "model": "sonnet",
         "by": "opus", "attempt": 1, "failure_class": "spec"},
    ]
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        j = write_journal(Path(d), events)
        run_ctx = _run_ctx_for(Path(d), [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
        any_ev = prep.evaluate_predicate("journal.any", run_ctx)
        narrow_ev = prep.evaluate_predicate("journal.field:failure_class=spec", run_ctx)
        assert any_ev.alive or not narrow_ev.alive


# ---------------------------------------------------------------------------
# 17. Регрессия на реальном протоколе (read-only)
# ---------------------------------------------------------------------------

def test_real_protocol_check_form_clean():
    # A8.1: M2 переключает require_all на каноне -- после сплошной
    # раскладки шапок (34/34) канон обязан оставаться зелёным И ловить
    # регресс (чек без шапки роняет канон), а не только форму полей.
    result = prep.run_check_form(prep.DEFAULT_PROTOCOL, prep.DEFAULT_RULE_COVERAGE, True)
    assert result.defects == [], "\n".join(result.defects)


def test_real_protocol_has_pilot_headers():
    result = prep.run_check_form(prep.DEFAULT_PROTOCOL, prep.DEFAULT_RULE_COVERAGE, True)
    ids = {h.id_str for h in result.headers}
    for expected in ("0", "3", "13", "26", "33", "12(а)", "12(б)"):
        assert expected in ids, f"пилотная шапка {expected} не найдена"


def test_real_protocol_all_35_checks_headered():
    # M2: все чеки (не только пилотная партия M1) несут ВЕРХНЮЮ
    # шапку -- require_all=True не находит ни одного чека без неё.
    # Мир ПОСЛЕ посадки чека 35 (кросс-пункт среза sibling-map AO3,
    # 2026-08-19): живой протокол несёт чеки 0..35 сплошно.
    result = prep.run_check_form(prep.DEFAULT_PROTOCOL, prep.DEFAULT_RULE_COVERAGE, True)
    assert result.defects == [], "\n".join(result.defects)
    top_numbers = {h.check_number for h in result.headers if h.subitem_letter is None}
    assert top_numbers == set(range(36)), sorted(set(range(36)) ^ top_numbers)


def test_real_protocol_window_run_exit0(tmp_path):
    """Критик-фикс №7: --registry на scratch -- иначе каждый прогон
    теста дописывает БОЕВОЙ сайдкар logs/calibration_prepass.jsonl
    строками с window_start==ts калибровки (после W4-1b это двигало бы
    skip-каунтер; класс «неинъектируемый дефолт пути»)."""
    proc = run_cli(["--window-start", "2026-08-14T12:12:34",
                     "--registry", str(tmp_path / "reg.jsonl")])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ИТОГ:" in proc.stdout


# ---------------------------------------------------------------------------
# 18. Инвариант Д1 (остаток узла W3) -- SECTION_BY_CHECK / KNOWN_SCRIPT_
#     COMMANDS обязаны не отставать от живого протокола молчаливо.
#     Реальный протокол -- READ-ONLY (как и раздел 17 выше).
# ---------------------------------------------------------------------------

def test_section_by_check_keys_match_real_protocol_check_numbers():
    """(а): множество ключей SECTION_BY_CHECK == множество фактических
    номеров чеков живого протокола. Парсинг -- ТОЙ ЖЕ формой, что сам
    пре-пасс использует для нумерации чеков (find_check_titles через
    load_protocol_structure), не второй самодельный парсер. Новый чек
    в протоколе без строки в SECTION_BY_CHECK обязан валить этот тест
    (Д1: молчаливое отставание словаря от протокола видно машинно)."""
    _lines, _bounds, titles = prep.load_protocol_structure(prep.DEFAULT_PROTOCOL)
    real_numbers = {t.number for t in titles}
    dict_numbers = set(prep.SECTION_BY_CHECK.keys())
    assert dict_numbers == real_numbers, sorted(dict_numbers ^ real_numbers)


def test_section_by_check_values_are_known_sections():
    """(б): каждое значение-секция SECTION_BY_CHECK лежит в фактическом
    множестве секций §0..§5 (SECTION_NAMES) -- никакой чек не привязан
    к несуществующей секции."""
    assert set(prep.SECTION_BY_CHECK.values()) <= set(prep.SECTION_NAMES.keys())


def test_known_script_commands_names_appear_in_protocol_text():
    """(в) позитив: каждый ключ KNOWN_SCRIPT_COMMANDS упоминается в
    тексте живого протокола (греп имени скрипта)."""
    text = prep.read_protocol_text(prep.DEFAULT_PROTOCOL)
    missing = [name for name in prep.KNOWN_SCRIPT_COMMANDS if name not in text]
    assert missing == [], (
        f"скрипты KNOWN_SCRIPT_COMMANDS отсутствуют в тексте протокола: {missing}"
    )


def test_known_script_commands_negative_control_invented_name_absent():
    """(в) негативный контроль: выдуманное имя не проходит -- доказывает,
    что позитивный тест выше не зелёный "просто потому что подстрока
    короткая/тривиальная"."""
    text = prep.read_protocol_text(prep.DEFAULT_PROTOCOL)
    assert "totally_invented_script_xyz_not_real" not in text


# ---------------------------------------------------------------------------
# 19. W4-1a -- поля body/bodypred: грамматика, MAX_FIELDS_TOTAL 8->10
# ---------------------------------------------------------------------------

def test_field_order_has_body_and_bodypred_between_status_and_cand():
    assert prep.FIELD_ORDER == [
        "src", "pred", "rules", "status", "body", "bodypred", "cand", "since", "note",
    ]


def test_max_fields_total_is_10_now():
    assert prep.MAX_FIELDS_TOTAL == 10


def test_body_bodypred_valid_pair_ok(tmp_path):
    body_dir_content = body_header_check(0)
    write_body_file(tmp_path, 0)
    result = check_form(tmp_path, body_dir_content, repo_root=tmp_path)
    assert result.defects == [], defects_str(result)


def test_body_field_space_in_value_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK 0.md|bodypred:always-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("body: пробел" in d for d in result.defects), defects_str(result)


def test_body_field_empty_value_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:|bodypred:always-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("body: пустое значение" in d for d in result.defects), defects_str(result)


def test_bodypred_unknown_predicate_rejected(tmp_path):
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:frobnicate-->\n"
        "    тело.\n\n"
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("bodypred:" in d and "не резолвящийся" in d for d in result.defects), \
        defects_str(result)


@pytest.mark.parametrize("bodypred", [
    "always", "git.any", "git.paths:tools/**", "path.exists:tools",
    "script:parity_check", "manual:транскрипты",
])
def test_bodypred_reuses_existing_predicate_grammar(bodypred):
    """A1: bodypred валидируется СУЩЕСТВУЮЩЕЙ грамматикой (никаких новых
    форм в W4-1a -- git.pathset заведён W4-1b)."""
    assert prep.validate_predicate_value(bodypred) is None, bodypred


def test_max_fields_total_boundary_all_9_fields_ok(tmp_path):
    """Граница MAX_FIELDS_TOTAL=10 (rule 6a): все 9 полей FIELD_ORDER +
    CHK = 10 -- PASS. "За границей" (11) структурно недостижим замкнутым
    словарём из 9 известных ключей без дублей (то же свойство было и у
    старого MAX=8/7 полей -- не новый пробел, см. отчёт)."""
    write_body_file(tmp_path, 0)
    body = (
        "0. **Чек.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always|cand:manual:x|"
        "since:2026-08-19|note:абв-->\n"
        "    тело.\n"
        "полное тело: PROCESS/checks/CHK-0.md (читается по вердикту "
        "пре-пасса; при отказе пре-пасса — читается всегда)\n\n"
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any("полей больше" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 20. W4-1a -- сверка пары шапка<->тело, 13 проверок (§4.6 (1)-(7) +
#     A9 (8)-(12) + A1 (13)); адверсариальная батарея (а)-(л) для 1a.
# ---------------------------------------------------------------------------

def test_pair_positive_all_13_checks_clean(tmp_path):
    """Позитив-эталон: валидная пара шапка<->тело не даёт ни одного
    PAIR-дефекта (база для всех негативных вариаций ниже)."""
    write_body_file(tmp_path, 0)
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any(d.startswith("PAIR:") for d in result.defects), defects_str(result)


# --- проверка (1): тело существует, читается, LF, непусто ------------------

def test_pair_check_01_missing_file_rejected(tmp_path):
    """Битарея (г): body на несуществующий файл."""
    body = body_header_check(0)  # тело НЕ создаётся
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("не существует" in d for d in result.defects), defects_str(result)


def test_pair_check_01_empty_body_rejected(tmp_path):
    """Битарея (е): тело 0 Б."""
    write_body_file(tmp_path, 0, content="")
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("тело PROCESS/checks/CHK-0.md -- пусто" in d for d in result.defects), \
        defects_str(result)


def test_pair_check_01_crlf_body_rejected(tmp_path):
    """Битарея (ж): тело CRLF (не LF)."""
    content = (
        "# CHK-0\r\n\r\nВЛАДЕЛЕЦ: Lead\r\nПРАВИЛО ВЕДЕНИЯ: тест.\r\n\r\n"
        "ядро -- в протоколе, чек 0.\r\n"
    )
    write_body_file(tmp_path, 0, content=content)
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("не LF" in d for d in result.defects), defects_str(result)


# --- проверка (2): путь относительный, внутри репо, ровно один чек на файл -

def test_pair_check_02_absolute_path_rejected(tmp_path):
    """Битарея (в), часть 1: body абсолютным путём."""
    abs_path = str((tmp_path / "PROCESS" / "checks" / "CHK-0.md")).replace("\\", "/")
    body = body_header_check(0, body_path=abs_path, pointer_body_path=abs_path)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("путь не относительный" in d for d in result.defects), defects_str(result)


def test_pair_check_02_outside_repo_path_rejected(tmp_path):
    """Битарея (в), часть 2: body путём вне репо (escaping .. )."""
    body = body_header_check(0, body_path="../outside/CHK-0.md",
                              pointer_body_path="../outside/CHK-0.md")
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("выходит за пределы репозитория" in d for d in result.defects), \
        defects_str(result)


def test_pair_check_02_duplicate_body_path_rejected(tmp_path):
    """Битарея (д): два чека с одним body."""
    write_body_file(tmp_path, 0)
    shared_path = "PROCESS/checks/CHK-0.md"
    body = (
        body_header_check(0, body_path=shared_path, pointer_body_path=shared_path)
        + body_header_check(1, body_path=shared_path, pointer_body_path=shared_path)
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("указан у нескольких чеков" in d for d in result.defects), defects_str(result)


# --- проверка (3): шапка тела несёт владельца и правило ведения ------------

def test_pair_check_03_missing_owner_marker_rejected(tmp_path):
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nПРАВИЛО ВЕДЕНИЯ: тест.\n\nядро -- в протоколе, чек 0.\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("нет маркера ВЛАДЕЛЕЦ" in d for d in result.defects), defects_str(result)


def test_pair_check_03_missing_rule_marker_rejected(tmp_path):
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\n\nядро -- в протоколе, чек 0.\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("нет маркера ПРАВИЛО ВЕДЕНИЯ" in d for d in result.defects), defects_str(result)


# --- проверка (4): номер в теле == номеру шапки -----------------------------

def test_pair_check_04_missing_check_number_in_body_rejected(tmp_path):
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\nядро -- в протоколе.\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("номер чека 0 не найден" in d for d in result.defects), defects_str(result)


# --- проверка (5): секционированное тело ------------------------------------

def _sectioned_pilot(tmp_path, body_section_id: str, body_extra: str = "",
                      subheader_id: str = "0(а)"):
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n\n"
        f"## {body_section_id}\n\nтекст секции.\n" + body_extra
    ))
    proto_body = (
        "0. **Чек с подпунктом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always-->\n"
        "    преамбула.\n"
        f"<!--CHK {subheader_id}|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой-->\n"
        f"    ({subheader_id[2:-1]}) подпункт с начала строки.\n"
        "полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
        "при отказе пре-пасса — читается всегда)\n\n"
    )
    return check_form(tmp_path, proto_body, repo_root=tmp_path)


def test_pair_check_05_section_matching_known_subheader_ok(tmp_path):
    result = _sectioned_pilot(tmp_path, body_section_id="0(а)")
    assert not any(d.startswith("PAIR:") and "секция" in d for d in result.defects), \
        defects_str(result)


def test_pair_check_05_section_without_subheader_rejected(tmp_path):
    result = _sectioned_pilot(tmp_path, body_section_id="0(я)")
    assert any("без под-шапки в протоколе" in d for d in result.defects), defects_str(result)


def test_pair_check_05_subheader_without_section_is_legal(tmp_path):
    """под-шапка без секции легальна: тело секционировано ДРУГИМ id,
    существующая под-шапка 0(а) не требует своей секции."""
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n"
    ))
    proto_body = (
        "0. **Чек с подпунктом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always-->\n"
        "    преамбула.\n"
        "<!--CHK 0(а)|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой-->\n"
        "    (а) подпункт с начала строки.\n"
        "полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
        "при отказе пре-пасса — читается всегда)\n\n"
    )
    result = check_form(tmp_path, proto_body, repo_root=tmp_path)
    assert not any(d.startswith("PAIR:") for d in result.defects), defects_str(result)


def test_pair_check_05_duplicate_section_id_rejected(tmp_path):
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n\n"
        "## 0(а)\n\nтекст.\n\n## 0(а)\n\nповтор.\n"
    ))
    proto_body = (
        "0. **Чек с подпунктом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always-->\n"
        "    преамбула.\n"
        "<!--CHK 0(а)|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой-->\n"
        "    (а) подпункт с начала строки.\n"
        "полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
        "при отказе пре-пасса — читается всегда)\n\n"
    )
    result = check_form(tmp_path, proto_body, repo_root=tmp_path)
    assert any("повтор секции" in d for d in result.defects), defects_str(result)


# --- проверка (6): body/bodypred у под-шапки -- дефект ----------------------

def test_pair_check_06_body_at_subheader_rejected(tmp_path):
    """Битарея (б): body у под-шапки."""
    write_body_file(tmp_path, 0)
    proto_body = (
        "0. **Чек с подпунктом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    преамбула.\n"
        "<!--CHK 0(а)|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md-->\n"
        "    (а) подпункт с начала строки.\n\n"
    )
    result = check_form(tmp_path, proto_body, repo_root=tmp_path)
    assert any("под-шапка 0(а)" in d and "легально только у шапки чека" in d
               for d in result.defects), defects_str(result)


def test_pair_check_06_bodypred_at_subheader_rejected(tmp_path):
    proto_body = (
        "0. **Чек с подпунктом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
        "    преамбула.\n"
        "<!--CHK 0(а)|src:журнал|pred:journal.any|rules:RC§1/R6|status:живой|"
        "bodypred:always-->\n"
        "    (а) подпункт с начала строки.\n\n"
    )
    result = check_form(tmp_path, proto_body, repo_root=tmp_path)
    assert any("под-шапка 0(а)" in d and "легально только у шапки чека" in d
               for d in result.defects), defects_str(result)


# --- проверка (7): чек с body обязан иметь непустое ядро --------------------

def test_pair_check_07_empty_core_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    body = body_header_check(0, extra_core="")
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("пустое ядро" in d for d in result.defects), defects_str(result)


def test_pair_check_07_nonempty_core_ok(tmp_path):
    write_body_file(tmp_path, 0)
    body = body_header_check(0, extra_core="непустое содержимое ядра.")
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any("пустое ядро" in d for d in result.defects), defects_str(result)


# --- проверка (8): строка-указатель -- присутствие/позиция -----------------

def test_pair_check_08_pointer_missing_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    body = body_header_check(0, pointer=False)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("строка-указатель на тело отсутствует" in d for d in result.defects), \
        defects_str(result)


def test_pair_check_08_pointer_not_last_line_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    body = (
        "0. **Чек с телом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always-->\n"
        "    доп. содержимое ядра.\n"
        "полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
        "при отказе пре-пасса — читается всегда)\n"
        "    хвост ПОСЛЕ указателя -- нарушает позицию.\n\n"
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("не последней строкой ядра" in d for d in result.defects), defects_str(result)


def test_pair_check_08_duplicate_pointer_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    ptr = ("полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
           "при отказе пре-пасса — читается всегда)\n")
    body = (
        "0. **Чек с телом.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always-->\n"
        "    доп. содержимое ядра.\n" + ptr + ptr + "\n\n"
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("больше одной строки-указателя" in d for d in result.defects), \
        defects_str(result)


# --- проверка (9): файл-сирота в PROCESS/checks/ ----------------------------

def test_pair_check_09_orphan_file_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    (tmp_path / "PROCESS" / "checks" / "CHK-99.md").write_text(
        "# CHK-99\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: сирота.\n", encoding="utf-8",
    )
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("файл-сирота" in d and "CHK-99.md" in d for d in result.defects), \
        defects_str(result)


def test_pair_check_09_no_orphan_when_referenced(tmp_path):
    write_body_file(tmp_path, 0)
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any("файл-сирота" in d for d in result.defects), defects_str(result)


def test_check_form_class_isolation_repo_root_pin(tmp_path):
    """Класс-пин (2026-08-19, узел W4-2 доделка). Орфан-проверка §4.6(9)
    сканирует ФАЙЛОВУЮ СИСТЕМУ repo_root/PROCESS/checks/, не содержимое
    протокола -- поэтому изоляция теста держится ИСКЛЮЧИТЕЛЬНО на том,
    какой repo_root передан вызовом, а не на том, что написано в
    синтетическом протоколе. КРАСНАЯ половина: repo_root указывает НА
    каталог с посторонним файлом в PROCESS/checks/ -- он ловится
    файлом-сиротой (проверка (9) остаётся строгой, класс не ослаблен).
    ЗЕЛЁНАЯ половина: тот же синтетический протокол (без единого поля
    body:), но repo_root указывает на ИЗОЛИРОВАННЫЙ каталог без
    PROCESS/checks/ вовсе -- посторонний файл невидим, дефектов нет
    (это и есть свойство, которое чинит дефолт check_form() выше)."""
    other_root = tmp_path / "other_root"
    isolated_root = tmp_path / "isolated_root"
    other_checks = other_root / "PROCESS" / "checks"
    other_checks.mkdir(parents=True)
    isolated_root.mkdir()
    (other_checks / "CHK-0.md").write_text(
        "ВЛАДЕЛЕЦ: Lead.\nПРАВИЛО ВЕДЕНИЯ: тест.\nядро -- в протоколе, чек 0.\n",
        encoding="utf-8",
    )

    proto = write_protocol(tmp_path, CHK0_VALID)
    rc = default_rc(tmp_path)

    red = prep.run_check_form(proto, rc, False, repo_root=other_root)
    assert any("файл-сирота" in d for d in red.defects), defects_str(red)

    green = prep.run_check_form(proto, rc, False, repo_root=isolated_root)
    assert not any("файл-сирота" in d for d in green.defects), defects_str(green)


# --- проверка (10): запрет строк <!--CHK внутри тела ------------------------

def test_pair_check_10_chk_marker_inside_body_rejected(tmp_path):
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n"
        "<!--CHK 5|src:журнал|pred:always|rules:RC§1/R6|status:живой-->\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("запрещённый маркер <!--CHK" in d for d in result.defects), defects_str(result)


# --- проверка (11): BOM -----------------------------------------------------

def test_pair_check_11_bom_rejected(tmp_path):
    content = (
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n"
    )
    p = tmp_path / "PROCESS" / "checks" / "CHK-0.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("содержит BOM" in d for d in result.defects), defects_str(result)


# --- проверка (12): имя файла выводится из id -------------------------------

def test_pair_check_12_filename_mismatch_rejected(tmp_path):
    write_body_file(tmp_path, 0, name="WRONG-NAME.md")
    body = body_header_check(0, body_path="PROCESS/checks/WRONG-NAME.md",
                              pointer_body_path="PROCESS/checks/WRONG-NAME.md")
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("не выводится из id" in d for d in result.defects), defects_str(result)


# --- проверка (13, A1): body без bodypred / bodypred без body ---------------

def test_pair_check_13_body_without_bodypred_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    body = body_header_check(0, bodypred=None)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("body без bodypred" in d for d in result.defects), defects_str(result)


def test_pair_check_13_bodypred_without_body_rejected(tmp_path):
    body = body_header_check(0, body_path="", bodypred="always", pointer=False)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("bodypred без body" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 21. W4-1a -- учёт байт тел (Р2(A)/A7/A8): M = протокол + ВСЕ тела,
#     "к чтению" += байты ЖИВЫХ по bodypred; печать адресов; К2/тест(п).
# ---------------------------------------------------------------------------

def test_body_accounting_no_bodies_all_zero_k2_test_p(tmp_path):
    """DoD п / К2 (A7): протокол без единой body-шапки -- добавки
    нулевые, числа to_read/total/alive идентичны миру до W4. Решение Lead
    (фикс 8а критика): оба слагаемых ИТОГ печатаются ВСЕГДА симметрично
    (включая нули) -- "из них тела 0 Б · принудительно 0 Б"."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["body_verdicts"] == []
    assert report["bodies_total_bytes"] == 0
    assert report["bodies_to_read_bytes"] == 0
    assert report["bodies_forced_bytes"] == 0
    assert report["protocol_total_bytes"] == report["total_bytes"]
    assert report["protocol_to_read_bytes"] == report["to_read_bytes"]
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "из них тела 0 Б · принудительно 0 Б" in rendered
    assert "ТЕЛА К ЧТЕНИЮ" not in rendered
    assert "ТЕЛА ПРОПУЩЕНЫ" not in rendered
    assert "ДЕФЕКТЫ ТЕЛ" not in rendered


def test_body_accounting_alive_body_bytes_included_in_to_read(tmp_path):
    write_body_file(tmp_path, 0)
    body_size = (tmp_path / "PROCESS" / "checks" / "CHK-0.md").stat().st_size
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="always"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert len(report["body_verdicts"]) == 1
    bv = report["body_verdicts"][0]
    assert bv.alive is True and bv.exists is True
    assert report["bodies_to_read_bytes"] == body_size
    assert report["bodies_total_bytes"] == body_size
    assert report["to_read_bytes"] == report["protocol_to_read_bytes"] + body_size
    assert report["total_bytes"] == report["protocol_total_bytes"] + body_size
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "ТЕЛА К ЧТЕНИЮ:" in rendered
    assert "PROCESS/checks/CHK-0.md" in rendered
    assert f"из них тела {body_size} Б" in rendered


def test_body_accounting_dead_body_excluded_from_to_read_but_in_total(tmp_path):
    """bodypred=journal.any на ПУСТОМ окне -> тело ПУСТ (не читается),
    но его байты входят в M (знаменатель, A8) через bodies_total_bytes."""
    write_body_file(tmp_path, 0)
    body_size = (tmp_path / "PROCESS" / "checks" / "CHK-0.md").stat().st_size
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    bv = report["body_verdicts"][0]
    assert bv.alive is False
    assert report["bodies_to_read_bytes"] == 0
    assert report["bodies_total_bytes"] == body_size
    assert report["total_bytes"] == report["protocol_total_bytes"] + body_size
    assert report["to_read_bytes"] == report["protocol_to_read_bytes"]
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "ТЕЛА ПРОПУЩЕНЫ:" in rendered
    assert "из них тела 0 Б" in rendered


def test_body_accounting_missing_file_alive_verdict_is_defect(tmp_path):
    """§4.7: тело отсутствует ПРИ ЖИВОМ вердикте -> дефект формы + 0 Б
    (файл тела не создаётся вовсе; bodypred=always -> alive)."""
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="always"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    bv = report["body_verdicts"][0]
    assert bv.alive is True and bv.exists is False and bv.byte_size == 0
    assert bv.defect is not None and "ТЕЛО ОТСУТСТВУЕТ" in bv.defect
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "ДЕФЕКТЫ ТЕЛ" in rendered
    assert "ТЕЛО ОТСУТСТВУЕТ" in rendered


# ---------------------------------------------------------------------------
# 22. W4-1a -- fail-closed (§4.7 + A10): сайдкар-счётчик, перехват
#     оконного тракта в main(), тест-пин "--check-form сайдкар не пишет".
# ---------------------------------------------------------------------------

def test_sidecar_bad_line_counted(tmp_path):
    reg = tmp_path / "reg.jsonl"
    reg.write_text('{"ts": "x"}\nне-json-строка\n{"ts": "y"}\n', encoding="utf-8")
    entries, bad = prep.read_registry(reg)
    assert len(entries) == 2
    assert bad == 1


def test_sidecar_bad_line_zero_when_clean(tmp_path):
    reg = tmp_path / "reg.jsonl"
    reg.write_text('{"ts": "x"}\n', encoding="utf-8")
    entries, bad = prep.read_registry(reg)
    assert bad == 0


def test_sidecar_missing_file_zero_bad(tmp_path):
    entries, bad = prep.read_registry(tmp_path / "no-such-registry.jsonl")
    assert entries == [] and bad == 0


def test_sidecar_bad_count_printed_in_render_when_nonzero(tmp_path):
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto, sidecar_bad_count=2,
    )
    assert "САЙДКАР: битых строк 2" in rendered


def test_sidecar_bad_count_not_printed_when_zero(tmp_path):
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto, sidecar_bad_count=0,
    )
    assert "САЙДКАР" not in rendered


def test_check_form_does_not_write_sidecar(tmp_path):
    """A10 тест-пин: --check-form НЕ пишет (и не читает) сайдкар --
    проверка формы не окно."""
    proto = write_protocol(tmp_path, CHK0_VALID)
    rc = default_rc(tmp_path)
    reg = tmp_path / "reg.jsonl"
    assert not reg.exists()
    proc = run_cli_isolated(["--check-form", "--protocol", str(proto), "--rule-coverage", str(rc),
                              "--registry", str(reg)], tmp_path)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not reg.exists(), "check-form не должен создавать/писать сайдкар"


def test_main_fail_closed_generic_exception_from_build_window_report(tmp_path, monkeypatch, capsys):
    """Тест monkeypatch build_window_report (§4.7/P4)."""
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(prep, "build_window_report", _boom)
    rc = prep.main([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "ПРЕ-ПАСС НЕ ОТРАБОТАЛ: RuntimeError" in captured.err
    assert "ЧИТАЕТСЯ ВСЁ: протокол +" in captured.err
    assert "ГЕЙТ (а): НЕ ИЗМЕРЕН" in captured.err
    assert not reg.exists(), "сайдкар не пишется при отказе пре-пасса"


def test_main_fail_closed_protocol_error_uses_new_format(tmp_path, capsys):
    """ProtocolError (ожидаемый класс) идёт через ТОТ ЖЕ перехват --
    единый формат оконного тракта, не старое "calibration_prepass: ...""."""
    missing_proto = tmp_path / "does-not-exist.md"
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    rc = prep.main([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(missing_proto),
        "--journal", str(j), "--registry", str(reg),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "ПРЕ-ПАСС НЕ ОТРАБОТАЛ: ProtocolError" in captured.err
    assert "ГЕЙТ (а): НЕ ИЗМЕРЕН" in captured.err


def test_fallback_body_listing_directory_exists_lists_files(tmp_path):
    checks_dir = tmp_path / "PROCESS" / "checks"
    checks_dir.mkdir(parents=True)
    (checks_dir / "CHK-0.md").write_text("x", encoding="utf-8")
    (checks_dir / "CHK-1.md").write_text("x", encoding="utf-8")
    proto = write_protocol(tmp_path, CHK0_VALID)
    listing = prep._fallback_body_listing(proto, repo_root=tmp_path)
    assert "PROCESS/checks/CHK-0.md" in listing
    assert "PROCESS/checks/CHK-1.md" in listing


def test_fallback_body_listing_directory_absent_uses_headers(tmp_path):
    proto = write_protocol(tmp_path, body_header_check(0))
    listing = prep._fallback_body_listing(proto, repo_root=tmp_path)
    assert "PROCESS/checks/CHK-0.md" in listing
    assert "каталога PROCESS/checks/ нет" in listing


def test_fallback_body_listing_directory_absent_no_bodies(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    listing = prep._fallback_body_listing(proto, repo_root=tmp_path)
    assert "не найдено" in listing


# ---------------------------------------------------------------------------
# 23. W4-1a -- CLI --window-start мусор -> exit 2 (битарея (л); уже
#     покрыто test_cli_invalid_window_start_exit2 выше -- регрессия
#     подтверждена явным дубль-пином здесь на случай переноса).
# ---------------------------------------------------------------------------

def test_battery_l_window_start_garbage_exit2_pin(tmp_path):
    proc = run_cli(["--window-start", "совсем-не-дата-мусор"])
    assert proc.returncode == 2


# --- битарея (а): шапка 300/301 Б С body ------------------------------------

def _header_with_body_of_len(payload_filler: str) -> str:
    base = ("<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
            "body:PROCESS/checks/CHK-0.md|bodypred:always|note:{}-->")
    return base.format(payload_filler)


def test_battery_a_header_300_bytes_with_body_ok(tmp_path):
    write_body_file(tmp_path, 0)
    base_no_note = ("<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
                     "body:PROCESS/checks/CHK-0.md|bodypred:always|note:-->")
    pad_needed = 300 - len(base_no_note.encode("utf-8"))
    header = _header_with_body_of_len("x" * pad_needed)
    assert len(header.encode("utf-8")) == 300
    pointer = ("полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
               "при отказе пре-пасса — читается всегда)\n")
    proto_body = f"0. **Чек.**\n{header}\n    доп. содержимое ядра.\n{pointer}\n\n"
    result = check_form(tmp_path, proto_body, repo_root=tmp_path)
    assert not any("длиннее 300" in d for d in result.defects), defects_str(result)


def test_battery_a_header_301_bytes_with_body_rejected(tmp_path):
    write_body_file(tmp_path, 0)
    base_no_note = ("<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
                     "body:PROCESS/checks/CHK-0.md|bodypred:always|note:-->")
    pad_needed = 301 - len(base_no_note.encode("utf-8"))
    header = _header_with_body_of_len("x" * pad_needed)
    assert len(header.encode("utf-8")) == 301
    pointer = ("полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
               "при отказе пре-пасса — читается всегда)\n")
    proto_body = f"0. **Чек.**\n{header}\n    доп. содержимое ядра.\n{pointer}\n\n"
    result = check_form(tmp_path, proto_body, repo_root=tmp_path)
    assert any("длиннее 300" in d for d in result.defects), defects_str(result)


# ---------------------------------------------------------------------------
# 24. Критик-фиксы W4-1a (fit_with_fixes, семь пунктов + решение Lead 8а)
# ---------------------------------------------------------------------------

# --- фикс 1: шапка с ЛЮБОЙ ошибкой формы не должна ронять тело из учёта ----

def test_critic_fix1_header_with_unrelated_form_error_still_counts_body(tmp_path):
    """Красная половина ДО фикса: since:НЕ-ДАТА (ошибка формы, к body
    отношения не имеющая) роняла тело из body_verdicts/M/"к чтению"
    целиком. После фикса: тело ЖИВО fail-closed с причиной, байты
    считаются."""
    write_body_file(tmp_path, 0)
    body_size = (tmp_path / "PROCESS" / "checks" / "CHK-0.md").stat().st_size
    proto_body = (
        "0. **Чек с дефектной шапкой.**\n"
        "<!--CHK 0|src:журнал|pred:always|rules:RC§1/R6|status:живой|"
        "body:PROCESS/checks/CHK-0.md|bodypred:always|since:НЕ-ДАТА-->\n"
        "    доп. содержимое ядра.\n"
        "полное тело: PROCESS/checks/CHK-0.md (читается по вердикту пре-пасса; "
        "при отказе пре-пасса — читается всегда)\n\n"
    )
    proto = write_protocol(tmp_path, proto_body)
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert len(report["body_verdicts"]) == 1, "тело не должно пропадать из учёта"
    bv = report["body_verdicts"][0]
    assert bv.alive is True
    assert "дефектом формы" in bv.reason
    assert report["bodies_total_bytes"] == body_size
    assert report["bodies_to_read_bytes"] == body_size


def test_critic_fix1_clean_header_unaffected(tmp_path):
    """Позитив-контроль фикса 1: шапка БЕЗ ошибок формы по-прежнему
    считается обычным путём (через bodypred), не через fail-closed
    ветку дефектной шапки."""
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="always"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    bv = report["body_verdicts"][0]
    assert bv.alive is True
    assert "дефектом формы" not in bv.reason


# --- фикс 2: не-UTF8 сайдкар не должен ронять UnicodeDecodeError наружу ----

def test_critic_fix2_non_utf8_sidecar_no_crash_exit0_with_bad_count(tmp_path, capsys):
    """ДО фикса: не-UTF8 байт в сайдкаре давал необработанный
    UnicodeDecodeError -- exit 1 без «ЧИТАЕТСЯ ВСЁ»/«ГЕЙТ (а): НЕ
    ИЗМЕРЕН». После errors="replace" строка декодируется без исключения,
    не парсится JSON-ом -> считается битой (не крэш, не fail-closed
    оконного тракта целиком -- прогон состоялся, битая строка сайдкара
    отражена счётчиком, W4-1b добавит форсирование)."""
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    reg.write_bytes(b'{"mode": "\xff\xfe\x00broken"}\n')
    rc = prep.main([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg),
    ])
    captured = capsys.readouterr()
    assert rc == 0, captured.out + captured.err
    assert "САЙДКАР: битых строк 1" in captured.out
    assert "ПРЕ-ПАСС НЕ ОТРАБОТАЛ" not in captured.err


def test_critic_fix2_registry_path_is_directory_is_fail_closed(tmp_path, capsys):
    """Фикс 2, вторая половина: read_registry/determine_mode -- ПОД ТЕМ
    ЖЕ перехватом, что build_window_report. Ошибка, которую errors=
    "replace" не лечит (--registry указывает на КАТАЛОГ, не файл ->
    PermissionError/IsADirectoryError на open()) -- обязана уйти через
    единый fail-closed, не наружу необработанным исключением."""
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg_as_dir = tmp_path / "reg-is-a-dir"
    reg_as_dir.mkdir()
    rc = prep.main([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg_as_dir),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "ПРЕ-ПАСС НЕ ОТРАБОТАЛ" in captured.err
    assert "ГЕЙТ (а): НЕ ИЗМЕРЕН" in captured.err


def test_critic_fix2_read_registry_non_utf8_no_crash():
    """read_registry сама по себе не падает на не-UTF8 байтах (errors=
    "replace"); строка не парсится JSON-ом -> считается битой."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "reg.jsonl"
        p.write_bytes(b'{"ts": "ok"}\n\xff\xfe\x00broken\n')
        entries, bad = prep.read_registry(p)
        assert len(entries) == 1
        assert bad == 1


# --- фикс 3: секцией считается ТОЛЬКО форма "## N(буква)", не проза;    ----
# --- фенсы игнорируются                                                 ----

def test_critic_fix3_prose_heading_owner_rule_no_false_defect(tmp_path):
    """Проба критика: тело с шапкой файла в форме markdown H2 "##
    ВЛАДЕЛЕЦ"/"## ПРАВИЛО ВЕДЕНИЯ" (буквально форма §4.1) НЕ должно
    давать ложных PAIR-дефектов "секция без под-шапки"."""
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\n"
        "## ВЛАДЕЛЕЦ\nLead\n\n"
        "## ПРАВИЛО ВЕДЕНИЯ\nчто живёт здесь.\n\n"
        "ядро -- в протоколе, чек 0.\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any("секция" in d and "без под-шапки" in d for d in result.defects), \
        defects_str(result)


def test_critic_fix3_section_form_without_subheader_still_a_defect(tmp_path):
    """Позитив-контроль: форма "## N(буква)" по-прежнему детектится и
    по-прежнему даёт дефект без под-шапки (регресс не в одну сторону)."""
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n\n## 0(я)\n\nтекст.\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("без под-шапки в протоколе" in d for d in result.defects), defects_str(result)


def test_critic_fix3_section_marker_inside_fence_ignored(tmp_path):
    """"## 5(а)" внутри ```-фенса (пример кода в теле) -- не секция,
    игнорируется целиком."""
    write_body_file(tmp_path, 0, content=(
        "# CHK-0\n\nВЛАДЕЛЕЦ: Lead\nПРАВИЛО ВЕДЕНИЯ: тест.\n\n"
        "ядро -- в протоколе, чек 0.\n\n"
        "```\n## 5(а)\nпример разметки внутри кода\n```\n"
    ))
    body = body_header_check(0)
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any("5(а)" in d for d in result.defects), defects_str(result)


# --- фикс 4: нормализация body в posix-форму -- дедуп и сирота ------------

def test_critic_fix4_dedup_not_bypassed_by_separator_style(tmp_path):
    """ДО фикса: два чека, один и тот же файл, но записанный '/' и '\\'
    -- дедуп (проверка №2) не срабатывал, т.к. ключом был НЕнормализо-
    ванный body_value."""
    write_body_file(tmp_path, 0)
    body = (
        body_header_check(0, body_path="PROCESS/checks/CHK-0.md",
                           pointer_body_path="PROCESS/checks/CHK-0.md")
        + body_header_check(1, body_path="PROCESS\\checks\\CHK-0.md",
                             pointer_body_path="PROCESS\\checks\\CHK-0.md")
    )
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert any("указан у нескольких чеков" in d for d in result.defects), defects_str(result)


def test_critic_fix4_no_false_orphan_with_backslash_body_path(tmp_path):
    """ДО фикса: body: с обратными слэшами давал ложную сироту (glob
    всегда отдаёт posix-путь, сравнение шло с НЕнормализованным
    значением)."""
    write_body_file(tmp_path, 0)
    body = body_header_check(0, body_path="PROCESS\\checks\\CHK-0.md",
                              pointer_body_path="PROCESS\\checks\\CHK-0.md")
    result = check_form(tmp_path, body, repo_root=tmp_path)
    assert not any("файл-сирота" in d for d in result.defects), defects_str(result)


# --- фикс 5: живое-но-отсутствующее тело -- ТОЛЬКО в "ДЕФЕКТЫ ТЕЛ" --------

def test_critic_fix5_alive_missing_body_not_in_skipped_section(tmp_path):
    """ДО фикса: тело с alive=True (bodypred:always) и отсутствующим
    файлом попадало И в "ДЕФЕКТЫ ТЕЛ" (правильно), И в "ТЕЛА ПРОПУЩЕНЫ"
    с причиной "always" (самопротиворечие -- "пропущено, потому что
    always жив"?)."""
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="always"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "ДЕФЕКТЫ ТЕЛ" in rendered and "ТЕЛО ОТСУТСТВУЕТ" in rendered
    assert "ТЕЛА ПРОПУЩЕНЫ" not in rendered, (
        "живое-но-отсутствующее тело не должно попадать в 'ТЕЛА ПРОПУЩЕНЫ'"
    )


# --- фикс 6: диагностика fail-closed несёт текст исключения, не только ----
# --- имя класса                                                        ----

def test_critic_fix6_fail_closed_message_carries_exception_text(tmp_path, monkeypatch, capsys):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"

    def _boom(*args, **kwargs):
        raise RuntimeError("причина-маркер-XYZ")

    monkeypatch.setattr(prep, "build_window_report", _boom)
    rc = prep.main([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg),
    ])
    captured = capsys.readouterr()
    assert rc == 2
    assert "RuntimeError: причина-маркер-XYZ" in captured.err, captured.err


# --- решение Lead 8а: оба слагаемых ИТОГ ВСЕГДА симметрично ---------------

def test_lead_8a_itog_always_prints_both_addends_symmetrically(tmp_path):
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "из них тела 0 Б · принудительно 0 Б" in rendered


# ---------------------------------------------------------------------------
# 25. W4-1b -- kind (Р7(A)/§4.4)
# ---------------------------------------------------------------------------

def _journal_ctx_all(tmp_path, events, name="j.jsonl"):
    j = write_journal(tmp_path, events, name)
    return prep.build_journal_context([str(j)], None, None)


def test_determine_kind_explicit_flag_overrides(tmp_path):
    ctx = _journal_ctx_all(tmp_path, [])
    kind, reason = prep.determine_kind(datetime(2026, 8, 14), ctx, True)
    assert kind == "калибровка"
    assert "--calibration" in reason


def test_determine_kind_journal_unavailable_is_calibration(tmp_path):
    ctx = prep.build_journal_context([str(tmp_path / "no-such.jsonl")], None, None)
    kind, reason = prep.determine_kind(datetime(2026, 8, 14), ctx, False)
    assert kind == "калибровка"
    assert "недоступен" in reason


def test_determine_kind_window_start_matches_last_calibrated_is_calibration(tmp_path):
    ctx = _journal_ctx_all(tmp_path, [
        {"ts": "2026-08-14T12:12:34", "event": "calibrated", "category": "x",
         "notes": "x", "model": "opus", "by": "opus"},
    ])
    ws = prep.cc.parse_ts("2026-08-14T12:12:34")
    kind, reason = prep.determine_kind(ws, ctx, False)
    assert kind == "калибровка"
    assert "совпадает" in reason


def test_determine_kind_window_start_mismatch_is_adhoc(tmp_path):
    ctx = _journal_ctx_all(tmp_path, [
        {"ts": "2026-08-14T12:12:34", "event": "calibrated", "category": "x",
         "notes": "x", "model": "opus", "by": "opus"},
    ])
    ws = prep.cc.parse_ts("2026-08-15T00:00:00")
    kind, reason = prep.determine_kind(ws, ctx, False)
    assert kind == "ad-hoc"


def test_determine_kind_no_calibrated_event_is_adhoc(tmp_path):
    ctx = _journal_ctx_all(tmp_path, [
        {"ts": "2026-08-14T12:12:34", "event": "delegated", "category": "x", "notes": "x",
         "model": "sonnet", "task_id": "t-1", "worker_ref": "cli:1"},
    ])
    ws = prep.cc.parse_ts("2026-08-14T12:12:34")
    kind, reason = prep.determine_kind(ws, ctx, False)
    assert kind == "ad-hoc"


def test_find_last_calibrated_ts_picks_max(tmp_path):
    ctx = _journal_ctx_all(tmp_path, [
        {"ts": "2026-08-10T00:00:00", "event": "calibrated", "category": "x",
         "notes": "x", "model": "opus", "by": "opus"},
        {"ts": "2026-08-14T12:12:34", "event": "calibrated", "category": "x",
         "notes": "x", "model": "opus", "by": "opus"},
    ])
    ts = prep.find_last_calibrated_ts(ctx)
    assert ts == prep.cc.parse_ts("2026-08-14T12:12:34")


def test_find_last_calibrated_ts_none_when_absent(tmp_path):
    ctx = _journal_ctx_all(tmp_path, [
        {"ts": "2026-08-10T00:00:00", "event": "delegated", "category": "x", "notes": "x",
         "model": "sonnet", "task_id": "t-1", "worker_ref": "cli:1"},
    ])
    assert prep.find_last_calibrated_ts(ctx) is None


# ---------------------------------------------------------------------------
# 26. W4-1b -- compute_skip_streak (§4.4/A3), границы 2/3/4 (rule 6a)
# ---------------------------------------------------------------------------

def _calib_entry(window_start, bodies):
    return {"kind": "калибровка", "window_start": window_start, "bodies": bodies}


def _adhoc_entry(window_start, bodies):
    return {"kind": "ad-hoc", "window_start": window_start, "bodies": bodies}


def test_skip_streak_zero_no_history():
    assert prep.compute_skip_streak([], "26") == 0


def test_skip_streak_two_below_threshold():
    entries = [
        _calib_entry("2026-08-01T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 2


def test_skip_streak_three_at_threshold():
    entries = [
        _calib_entry("2026-08-01T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 3


def test_skip_streak_four_over_threshold():
    entries = [_calib_entry(f"2026-08-0{i}T00:00:00", {"26": "ПРОПУЩЕНО"})
               for i in range(1, 5)]
    assert prep.compute_skip_streak(entries, "26") == 4


def test_skip_streak_stops_at_prochitano():
    entries = [
        _calib_entry("2026-08-01T00:00:00", {"26": "ПРОЧИТАНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 2


def test_skip_streak_stops_at_prinuditelno():
    entries = [
        _calib_entry("2026-08-01T00:00:00", {"26": "ПРИНУДИТЕЛЬНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 1


def test_skip_streak_ignores_adhoc_entries():
    entries = [
        _calib_entry("2026-08-01T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _adhoc_entry("2026-08-05T00:00:00", {"26": "ПРОЧИТАНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 2, (
        "ad-hoc не двигает и не рвёт калибровочный streak (К8)"
    )


def test_skip_streak_ignores_entries_without_bodies():
    entries = [
        {"kind": "калибровка", "window_start": "2026-08-01T00:00:00"},  # без bodies вовсе
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 2


def test_skip_streak_ignores_entries_without_this_id_in_bodies():
    entries = [
        _calib_entry("2026-08-01T00:00:00", {"18": "ПРОЧИТАНО"}),  # другое тело
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 2

# (монотонная свёртка группы window_start -- A14(б), блокер 2 -- см.
# секцию "33. A14(б), блокер 2" ниже: тесты не дублируются здесь.)


# ---------------------------------------------------------------------------
# 27. W4-1b -- apply_skip_counter: forcing, bodies-статус, К2-нейтральность
# ---------------------------------------------------------------------------

def _write_registry_lines(path: Path, lines: list) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for ln in lines:
            fh.write(json.dumps(ln, ensure_ascii=False) + "\n")


def test_apply_skip_counter_no_bodies_is_k2_neutral(tmp_path):
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    before_to_read = report["to_read_bytes"]
    before_total = report["total_bytes"]
    reg = tmp_path / "reg.jsonl"
    report2 = prep.apply_skip_counter(report, [], reg, "калибровка", "test")
    assert report2["to_read_bytes"] == before_to_read
    assert report2["total_bytes"] == before_total
    assert report2["bodies_status"] == {}
    assert report2["forced_lines"] == []


def test_apply_skip_counter_below_threshold_no_forcing(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["body_verdicts"][0].alive is False

    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    bv = report2["body_verdicts"][0]
    assert bv.alive is False
    assert report2["bodies_status"]["0"] == "ПРОПУЩЕНО"
    assert report2["forced_lines"] == []
    assert report2["bodies_forced_bytes"] == 0


def test_apply_skip_counter_forces_at_streak_3_with_print_and_reset(tmp_path):
    write_body_file(tmp_path, 0)
    body_size = (tmp_path / "PROCESS" / "checks" / "CHK-0.md").stat().st_size
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["body_verdicts"][0].alive is False

    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    bv = report2["body_verdicts"][0]
    assert bv.alive is True
    expected_msg = ("ПРИНУДИТЕЛЬНО ЖИВ: 0 — тело пропущено 3 калибровки подряд "
                     "(skip-каунтер), предикат journal.any ложен")
    assert bv.reason == expected_msg
    assert expected_msg in report2["forced_lines"]
    assert report2["bodies_status"]["0"] == "ПРИНУДИТЕЛЬНО"
    assert report2["bodies_forced_bytes"] == body_size
    assert report2["to_read_bytes"] == report2["protocol_to_read_bytes"] + body_size

    # "Обнуление streak": запись, которую этот прогон допишет в сайдкар,
    # несёт bodies["0"]=="ПРИНУДИТЕЛЬНО" -- следующий скан стопится СРАЗУ,
    # streak==0 для будущего прогона.
    prep.write_registry_entry(reg, "2026-08-22T00:00:00", "2026-08-24T00:00:00",
                               "обычный", "test", report2, None)
    entries_after, _bad2 = prep.read_registry(reg)
    assert prep.compute_skip_streak(entries_after, "0") == 0


def test_apply_skip_counter_streak_4_prints_overflow_line(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)

    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry(f"2026-08-0{i}T00:00:00", {"0": "ПРОПУЩЕНО"}) for i in range(1, 5)
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    assert report2["body_verdicts"][0].alive is True
    assert any("счётчик перешагнул порог — разобрать" in ln and "streak=4" in ln
               for ln in report2["forced_lines"]), report2["forced_lines"]


def test_apply_skip_counter_bodies_status_prochitano_when_naturally_alive(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="always"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    reg = tmp_path / "reg.jsonl"
    report2 = prep.apply_skip_counter(report, [], reg, "калибровка", "test")
    assert report2["bodies_status"]["0"] == "ПРОЧИТАНО"
    assert report2["forced_lines"] == []


def test_apply_skip_counter_forced_lines_rendered(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    rendered = prep.render_window_report(
        report2, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "=== ПРИНУДИТЕЛЬНО ЖИВЫЕ ТЕЛА" in rendered
    assert "ПРИНУДИТЕЛЬНО ЖИВ: 0 — тело пропущено 3 калибровки подряд" in rendered
    assert "СКИП-КАУНТЕР: kind=калибровка (test) · сайдкар:" in rendered


# ---------------------------------------------------------------------------
# 28. W4-1b -- А10: сайдкар-дефект форсирует ВСЕ тела (окно ПОСЛЕ
#     последней валидной калибровки, не вечно)
# ---------------------------------------------------------------------------

def test_sidecar_bad_after_last_valid_calibration_no_valid_entry_any_bad_forces(tmp_path):
    reg = tmp_path / "reg.jsonl"
    reg.write_text("не-json-мусор\n", encoding="utf-8")
    forces, bad = prep.sidecar_bad_after_last_valid_calibration(reg)
    assert forces is True and bad == 1


def test_sidecar_bad_after_last_valid_calibration_bad_after_valid_forces(tmp_path):
    reg = tmp_path / "reg.jsonl"
    reg.write_text(
        json.dumps(_calib_entry("x", {})) + "\n" + "мусор-после\n",
        encoding="utf-8",
    )
    forces, bad = prep.sidecar_bad_after_last_valid_calibration(reg)
    assert forces is True and bad == 1


def test_sidecar_bad_after_last_valid_calibration_bad_before_valid_does_not_force(tmp_path):
    """A10: не форсирует ВЕЧНО -- битая строка ДО последней валидной
    калибровочной записи не форсирует текущий прогон."""
    reg = tmp_path / "reg.jsonl"
    reg.write_text(
        "мусор-до\n" + json.dumps(_calib_entry("x", {})) + "\n",
        encoding="utf-8",
    )
    forces, bad = prep.sidecar_bad_after_last_valid_calibration(reg)
    assert forces is False and bad == 1


def test_sidecar_bad_after_last_valid_calibration_no_bad_lines(tmp_path):
    reg = tmp_path / "reg.jsonl"
    reg.write_text(json.dumps(_calib_entry("x", {})) + "\n", encoding="utf-8")
    forces, bad = prep.sidecar_bad_after_last_valid_calibration(reg)
    assert forces is False and bad == 0


def test_sidecar_bad_after_last_valid_calibration_missing_file(tmp_path):
    forces, bad = prep.sidecar_bad_after_last_valid_calibration(tmp_path / "no-such.jsonl")
    assert forces is False and bad == 0


def test_apply_skip_counter_sidecar_defect_forces_remaining_skipped_bodies(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)

    reg = tmp_path / "reg.jsonl"
    reg.write_text("мусор\n", encoding="utf-8")  # ни одной валидной записи -> форсирует
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    bv = report2["body_verdicts"][0]
    assert bv.alive is True
    assert "САЙДКАР ДЕФЕКТЕН (1 битых строк)" in bv.reason
    assert report2["bodies_status"]["0"] == "ПРИНУДИТЕЛЬНО"
    assert report2["sidecar_forces_all"] is True
    rendered = prep.render_window_report(
        report2, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "САЙДКАР ДЕФЕКТЕН (1 битых строк)" in rendered


def test_apply_skip_counter_sidecar_clean_after_valid_calibration_no_forcing(tmp_path):
    """A10 позитив-контроль: битая строка ДО последней валидной
    калибровки -- НЕ форсирует, тело остаётся честно ПРОПУЩЕНО."""
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)

    reg = tmp_path / "reg.jsonl"
    reg.write_text(
        "мусор-давно-исправленный\n" + json.dumps(_calib_entry("2026-08-01T00:00:00", {})) + "\n",
        encoding="utf-8",
    )
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    bv = report2["body_verdicts"][0]
    assert bv.alive is False
    assert report2["bodies_status"]["0"] == "ПРОПУЩЕНО"
    assert report2["sidecar_forces_all"] is False


# ---------------------------------------------------------------------------
# 29. W4-1b -- §4.5 сторож живости git.paths/git.pathset (класс
#     «молчаливый ноль»): X из Y с настоящим контролем, красные половины.
# ---------------------------------------------------------------------------

def _git(repo: Path, *args, env=None):
    return subprocess.run(
        ["git"] + list(args), cwd=str(repo), check=True, capture_output=True,
        encoding="utf-8", errors="replace", env=env,
    )


def _make_git_repo_with_commits(tmp_path: Path, commits, name: str = "git-repo") -> Path:
    """commits: [(relpath, content, iso_ts), ...] -- один герметичный
    git-репозиторий, коммиты с ЯВНЫМИ датами (GIT_AUTHOR_DATE/
    GIT_COMMITTER_DATE) для детерминированной фильтрации окном."""
    repo = tmp_path / name
    repo.mkdir(exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@test.local")
    _git(repo, "config", "user.name", "test")
    for relpath, content, iso_ts in commits:
        p = repo / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        _git(repo, "add", relpath)
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = iso_ts
        env["GIT_COMMITTER_DATE"] = iso_ts
        _git(repo, "commit", "-q", "-m", f"commit {relpath}", env=env)
    return repo


def test_git_paths_alive_when_pathspec_matches_in_window(tmp_path):
    repo = _make_git_repo_with_commits(tmp_path, [
        ("tools/x.py", "x", "2026-08-15T10:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:tools/**", run_ctx)
    assert ev.alive is True
    assert ev.observed == 1


def test_git_paths_empty_with_real_positive_control_denominator(tmp_path):
    """§4.5: ПУСТ по pathspec, но окно НЕ пусто по коммитам вообще --
    Y обязан быть настоящим числом коммитов без pathspec, не 0."""
    repo = _make_git_repo_with_commits(tmp_path, [
        ("other.txt", "x", "2026-08-15T10:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:nomatch/**", run_ctx)
    assert ev.alive is False
    assert ev.observed == 0
    assert ev.denom == 1, "контроль обязан отразить РЕАЛЬНОЕ число коммитов окна (1), не 0"


def test_git_paths_window_with_zero_commits_second_stage_alive_form(tmp_path):
    """Настоящий (не мок) репозиторий БЕЗ единого коммита В ОКНЕ (но с
    историей вне окна, значит `git log` успешен -- HEAD существует) --
    вторая ступень git rev-parse --git-dir подтверждает живость git,
    verdict остаётся ПУСТ с явным "форма жива", не молчаливым нулём."""
    repo = _make_git_repo_with_commits(tmp_path, [
        ("outside-window.txt", "x", "2020-01-01T00:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:tools/**", run_ctx)
    assert ev.alive is False
    assert ev.observed == 0 and ev.denom == 0
    assert "форма жива" in ev.reason
    assert "-> 0 из 0" in ev.reason


def test_git_paths_not_git_repo_is_alive_fail_closed(tmp_path):
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:tools/**", run_ctx)
    assert ev.alive is True


def test_git_paths_guard_red_half_run_git_none_is_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: None)
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:tools/**", run_ctx)
    assert ev.alive is True, ev.reason


def test_git_paths_guard_red_half_run_git_empty_string_is_alive(tmp_path, monkeypatch):
    """«0 из 0» без настоящего контроля структурно недостижим: даже
    когда ВСЕ вызовы _run_git (включая git rev-parse --git-dir) отдают
    пустую строку -- не None -- сторож не принимает это за живой git."""
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: "")
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:tools/**", run_ctx)
    assert ev.alive is True, ev.reason
    assert "rev-parse" in ev.reason


# ---------------------------------------------------------------------------
# 30. W4-1b -- git.pathset:hooks (A6/Р4/DoD-3), переиспользует
#     enforcement_probe._chain_paths
# ---------------------------------------------------------------------------

def test_bodypred_git_pathset_hooks_valid_grammar():
    assert prep.validate_predicate_value("git.pathset:hooks") is None


def test_git_pathset_hooks_alive_when_settings_touched_in_window(tmp_path, monkeypatch):
    # A14(е): settings.json ОБЯЗАН парситься как JSON И дать хотя бы один
    # член СВЕРХ двух безусловно посеянных (settings.json+wiring_check) --
    # валидный JSON, несущий строку с "python tools/....py" где-то внутри
    # (тот же regex-разбор, что и в реальном hook-command).
    settings_json = json.dumps({"note": "python tools/hook_liveness_probe.py"})
    repo = _make_git_repo_with_commits(tmp_path, [
        (".claude/settings.json", settings_json, "2026-08-15T10:00:00"),
    ])
    monkeypatch.setattr(prep.ep, "SETTINGS_PATH", str(repo / ".claude" / "settings.json"))
    monkeypatch.setattr(prep.ep, "GITHOOKS_DIR", str(repo / ".githooks"))
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True, ev.reason
    assert ev.observed == 1


def test_git_pathset_hooks_positive_control_size_and_sample_on_live_repo():
    """Позитивный контроль DoD-3 на РЕАЛЬНОМ settings.json этого репо
    (given: tools/enforcement_probe.py read-only) -- множество непусто и
    несёт .claude/settings.json."""
    run_ctx = _run_ctx_for(REPO_ROOT, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert "нечитаем" not in ev.reason
    assert "вырожден" not in ev.reason


def test_git_pathset_hooks_settings_unreadable_is_alive_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(prep.ep, "SETTINGS_PATH", str(tmp_path / "no-such-settings.json"))
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True
    assert "нечитаем" in ev.reason


def test_git_pathset_hooks_degenerate_chain_is_alive_fail_closed(monkeypatch):
    """DoD-3: контроль размера/образца -- множество вырождено (пусто)
    -> ЖИВ fail-closed, а не тихий пропуск."""
    monkeypatch.setattr(prep.ep, "_chain_paths", lambda: set())
    run_ctx = _run_ctx_for(REPO_ROOT, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True
    assert "вырожден" in ev.reason


def test_git_pathset_unknown_name_is_alive_fail_closed(tmp_path):
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:frobnicate", run_ctx)
    assert ev.alive is True
    assert "неизвестное имя pathset" in ev.reason


def test_git_pathset_not_git_repo_is_alive_fail_closed(tmp_path):
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True


def test_git_pathset_guard_red_half_run_git_empty_string_is_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: "")
    run_ctx = _run_ctx_for(REPO_ROOT, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True, ev.reason


# ---------------------------------------------------------------------------
# 31. W4-1b -- CLI: --calibration, kind в JSON/witness
# ---------------------------------------------------------------------------

def test_cli_calibration_flag_prints_kind_calibration(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    proc = run_cli([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg), "--calibration",
        "--rule-coverage", str(default_rc(tmp_path)),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "kind=калибровка" in proc.stdout
    assert "явный флаг --calibration" in proc.stdout
    entries, _bad = prep.read_registry(reg)
    assert entries[-1]["kind"] == "калибровка"
    assert entries[-1]["bodies"] == {}


def test_cli_without_calibration_flag_default_kind_present(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    proc = run_cli([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg),
        "--rule-coverage", str(default_rc(tmp_path)),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "СКИП-КАУНТЕР: kind=" in proc.stdout
    assert "сайдкар:" in proc.stdout


def test_cli_json_output_includes_kind_and_bodies(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    proc = run_cli([
        "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
        "--journal", str(j), "--registry", str(reg), "--calibration", "--json",
        "--rule-coverage", str(default_rc(tmp_path)),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "калибровка"
    assert payload["bodies"] == {}


# =============================================================================
# КРИТИК t-536 (blocker, A14) -- 2 блокера + 6 фиксов
# =============================================================================

# ---------------------------------------------------------------------------
# 32. A14(а), блокер 1: вердикт гейта (а) считается от N-F, не от N
# ---------------------------------------------------------------------------

def test_gate_verdict_base_is_n_minus_f_not_n(tmp_path, monkeypatch):
    """A14(a) блокер 1: гейт (а) и ±d считаются от N-F ("к чтению" МИНУС
    "принудительно"), не от N. Порог выставлен РОВНО в N-F -> ВЗЯТ (+0),
    хотя порог < N (что раньше давало НЕ ВЗЯТ (+F Б) -- witness
    критика: «порог==к-чтению-без-принудительных давал НЕ ВЗЯТ
    (+181 Б)»)."""
    write_body_file(tmp_path, 0)
    body_size = (tmp_path / "PROCESS" / "checks" / "CHK-0.md").stat().st_size
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)

    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    assert report2["bodies_forced_bytes"] == body_size  # F > 0 -- тело форсировано

    n = report2["to_read_bytes"]
    f = report2["bodies_forced_bytes"]
    threshold = n - f  # порог РОВНО в N-F
    monkeypatch.setattr(prep, "GATE_A_THRESHOLD_BYTES", threshold)
    rendered = prep.render_window_report(
        report2, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    # W4-3: провенанс храповика ("храповик от замера ...") теперь ВСЕГДА
    # печатается между порогом и вердиктом -- порог сам монки-патчен, но
    # провенанс читается из GATE_A_HISTORY (не патчен здесь) -- проверяем
    # обе части раздельно, не одной жёсткой строкой.
    assert f"гейт (а) ≤{threshold} Б (храповик от замера" in rendered, rendered
    assert "): ВЗЯТ (+0 Б)" in rendered, rendered
    # N печатается КАК ЕСТЬ (не N-F) -- строка ИТОГ не меняется формой (§4.3).
    assert f"к чтению {n} Б из" in rendered


def test_gate_verdict_base_old_bug_would_reject_at_same_threshold(tmp_path, monkeypatch):
    """Регресс-пин ошибки ДО фикса: если бы база вердикта считалась от N
    (не N-F), порог==N-F дал бы «НЕ ВЗЯТ (+F Б)» -- явно демонстрируем,
    что F>0 и что порог строго МЕНЬШЕ N (иначе тест не различал бы
    старую/новую формулу)."""
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    n = report2["to_read_bytes"]
    f = report2["bodies_forced_bytes"]
    assert f > 0 and (n - f) < n, "F>0 -- иначе N-F==N и блокер1 не различим этим тестом"


# ---------------------------------------------------------------------------
# 33. A14(б), блокер 2: монотонная свёртка группы window_start
# ---------------------------------------------------------------------------

def test_skip_streak_group_monotonic_fold_read_then_skip_stays_read(tmp_path):
    """A14(б): МОНОТОННАЯ свёртка -- ПРОЧИТАНО где-то в группе делает
    группу "читалась" НАВСЕГДА; более поздняя запись той же группы с
    ПРОПУЩЕНО НЕ откатывает это назад (это и была дыра A3 -- 'последняя
    запись группы' допускала недолговечное обнуление)."""
    entries = [
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОЧИТАНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 0


def test_skip_streak_group_monotonic_fold_skip_then_read_becomes_read(tmp_path):
    entries = [
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОЧИТАНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 0


def test_skip_streak_group_all_skipped_counts_group_once(tmp_path):
    """Группа БЕЗ единой записи ПРОЧИТАНО/ПРИНУДИТЕЛЬНО -- ПРОПУЩЕНО
    (даже при нескольких записях ПРОПУЩЕНО внутри -- РОВНО ОДИН вклад в
    streak на группу, не по числу записей)."""
    entries = [
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"26": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"26": "ПРОПУЩЕНО"}),
    ]
    assert prep.compute_skip_streak(entries, "26") == 2  # 2 ГРУППЫ, не 3 записи


def test_skip_streak_blocker2_four_reruns_of_one_window_stable_after_forcing(tmp_path):
    """A14(б) дословно по witness критика: история трёх ПРОПУЩЕНО (три
    разных window_start) -> streak=3 -> 1-й прогон окна W4 форсирует
    (ПРИНУДИТЕЛЬНО); 2-й/3-й/4-й прогоны ТОГО ЖЕ window_start W4 (при
    предикате, всё ещё ложном) обязаны быть СТАБИЛЬНЫ: streak==0 у
    каждого (не растёт до 4), никакого "перешагнул порог"."""
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")

    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-15T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])

    w4 = "2026-08-22T00:00:00"
    report1 = prep.build_window_report(proto, run_ctx)
    entries, _bad = prep.read_registry(reg)
    report1 = prep.apply_skip_counter(report1, entries, reg, "калибровка", "test")
    assert report1["body_verdicts"][0].alive is True
    assert report1["bodies_status"]["0"] == "ПРИНУДИТЕЛЬНО"
    assert not any("перешагнул порог" in ln for ln in report1["forced_lines"])
    prep.write_registry_entry(reg, w4, "2026-08-24T00:00:00", "обычный", "test", report1, None)

    for _ in range(3):
        report_n = prep.build_window_report(proto, run_ctx)
        entries, _bad = prep.read_registry(reg)
        report_n = prep.apply_skip_counter(report_n, entries, reg, "калибровка", "test")
        assert report_n["body_verdicts"][0].alive is False, (
            "предикат по-прежнему ложен -- НЕ форсируется повторно"
        )
        assert report_n["bodies_status"]["0"] == "ПРОПУЩЕНО"
        assert report_n["skip_streaks"]["0"] == 0, (
            "streak после форсированного окна обязан быть стабильно 0 (A14б)"
        )
        assert report_n["forced_lines"] == [], "никакого 'перешагнул порог' на повторах"
        prep.write_registry_entry(reg, w4, "2026-08-24T00:00:00", "обычный", "test",
                                   report_n, None)

    entries_final, _bad = prep.read_registry(reg)
    assert prep.compute_skip_streak(entries_final, "0") == 0


# ---------------------------------------------------------------------------
# 34. A14(в), фикс 3: форма §4.3 дословно -- skip-streak видим ДО
#     срабатывания; "X из Y" на ОБЕИХ ветках (ЖИВОЙ/ПУСТ)
# ---------------------------------------------------------------------------

def test_body_pust_line_matches_para_4_3_form_literally(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    reg = tmp_path / "reg.jsonl"
    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    assert report2["skip_streaks"]["0"] == 1, "счётчик виден ДО срабатывания (1/3)"
    rendered = prep.render_window_report(
        report2, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert ("  PROCESS/checks/CHK-0.md (journal.any -> 0 из 0 строк окна; "
            "skip-streak 1/3)") in rendered, rendered


def test_body_pust_line_streak_visible_at_zero_and_two(tmp_path):
    write_body_file(tmp_path, 0)
    proto = write_protocol(tmp_path, body_header_check(0, bodypred="journal.any"))
    j = write_journal(tmp_path, [])
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    reg = tmp_path / "reg.jsonl"

    entries, _bad = prep.read_registry(reg)  # сайдкар пуст -- streak 0
    report0 = prep.apply_skip_counter(report, entries, reg, "калибровка", "test")
    rendered0 = prep.render_window_report(
        report0, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "skip-streak 0/3" in rendered0

    _write_registry_lines(reg, [
        _calib_entry("2026-08-01T00:00:00", {"0": "ПРОПУЩЕНО"}),
        _calib_entry("2026-08-08T00:00:00", {"0": "ПРОПУЩЕНО"}),
    ])
    entries2, _bad = prep.read_registry(reg)
    report2 = prep.apply_skip_counter(prep.build_window_report(proto, run_ctx), entries2,
                                       reg, "калибровка", "test")
    rendered2 = prep.render_window_report(
        report2, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "skip-streak 2/3" in rendered2


def test_body_alive_line_shows_observed_out_of_control_for_git_bodypred(tmp_path):
    repo = _make_git_repo_with_commits(tmp_path, [
        ("tools/x.py", "x", "2026-08-15T10:00:00"),
    ])
    write_body_file(repo, 0)
    body_size = (repo / "PROCESS" / "checks" / "CHK-0.md").stat().st_size
    proto = write_protocol(repo, body_header_check(0, bodypred="git.paths:tools/**"))
    j = write_journal(repo, [])
    run_ctx = _run_ctx_for(repo, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    bv = report["body_verdicts"][0]
    assert bv.alive is True
    assert bv.reason.endswith("-> 1 из 1 коммитов окна"), bv.reason
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert (f"  PROCESS/checks/CHK-0.md ({body_size} Б, предикат git.paths:tools/** "
            f"-> 1 из 1 коммитов окна)") in rendered, rendered


# ---------------------------------------------------------------------------
# 35. A14(г), фикс 5: денoминатор git-предикатов -- "коммитов окна"
# ---------------------------------------------------------------------------

def test_git_paths_pust_denominator_labeled_commits_not_rows(tmp_path):
    repo = _make_git_repo_with_commits(tmp_path, [
        ("other.txt", "x", "2026-08-15T10:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.paths:nomatch/**", run_ctx)
    assert ev.denom_unit == "коммитов окна"
    assert ev.alive is False and ev.denom == 1


def test_check_level_git_paths_pust_rendered_says_commits_not_rows(tmp_path):
    """Денoминатор газеты «коммитов окна», а не «строк окна» -- на
    БОЕВОМ пути (build_window_report + render_window_report), не
    только в EvalResult (A14з, класс «публичный шов»)."""
    repo = _make_git_repo_with_commits(tmp_path, [
        ("other.txt", "x", "2026-08-15T10:00:00"),
    ])
    proto = write_protocol(repo, (
        "0. **Чек git.paths.**\n"
        "<!--CHK 0|src:git|pred:git.paths:nomatch/**|rules:RC§1/R6|status:живой-->\n"
        "    тело чека.\n\n"
    ))
    j = write_journal(repo, [])
    run_ctx = _run_ctx_for(repo, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "-> 0 из 1 коммитов окна" in rendered
    assert "строк окна" not in rendered


# ---------------------------------------------------------------------------
# 36. A14(д), фикс 6: git.any/git.diff_lines -- та же вторая ступень
# ---------------------------------------------------------------------------

def test_git_any_zero_commits_window_second_stage_form_alive(tmp_path):
    repo = _make_git_repo_with_commits(tmp_path, [
        ("outside.txt", "x", "2020-01-01T00:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.any", run_ctx)
    assert ev.alive is False
    assert "форма жива" in ev.reason
    assert "коммитов окна" in ev.reason


def test_git_any_red_half_run_git_empty_string_is_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: "")
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.any", run_ctx)
    assert ev.alive is True, ev.reason


def test_git_any_red_half_run_git_none_is_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: None)
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.any", run_ctx)
    assert ev.alive is True, ev.reason


def test_git_diff_lines_zero_second_stage_form_alive(tmp_path):
    repo = _make_git_repo_with_commits(tmp_path, [
        ("outside.txt", "x", "2020-01-01T00:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.diff_lines:>100", run_ctx)
    assert ev.alive is False
    assert "форма жива" in ev.reason


def test_git_diff_lines_red_half_run_git_empty_string_is_alive(tmp_path, monkeypatch):
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: "")
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.diff_lines:>100", run_ctx)
    assert ev.alive is True, ev.reason


def test_git_diff_lines_small_nonzero_not_guarded(tmp_path):
    """Малое, но НАСТОЯЩЕЕ число (n>0, <=threshold) -- НЕ проходит через
    гвард (не искажаем честный малый диф второй ступенью)."""
    repo = _make_git_repo_with_commits(tmp_path, [
        ("x.txt", "abc\ndef\n", "2026-08-15T10:00:00"),
    ])
    run_ctx = _run_ctx_for(repo, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.diff_lines:>100", run_ctx)
    assert ev.alive is False
    assert "форма жива" not in ev.reason


# ---------------------------------------------------------------------------
# 37. A14(е), фикс 7: позитивный контроль pathset ОБЯЗАН МОЧЬ УПАСТЬ
# ---------------------------------------------------------------------------

def test_git_pathset_hooks_settings_invalid_json_is_alive_fail_closed(tmp_path, monkeypatch):
    bad_settings = tmp_path / "bad-settings.json"
    bad_settings.write_text("{не валидный json", encoding="utf-8")
    monkeypatch.setattr(prep.ep, "SETTINGS_PATH", str(bad_settings))
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True
    assert "не парсится как JSON" in ev.reason


def test_git_pathset_hooks_exactly_two_seeded_members_is_alive_fail_closed(tmp_path, monkeypatch):
    """A14(е): позитивный контроль ОБЯЗАН МОЧЬ УПАСТЬ -- валидный JSON,
    но множество несёт РОВНО два безусловно посеянных члена (ни одного
    сверх) -> ЖИВ fail-closed, не тихий пропуск (ДО фикса контроль,
    построенный только на присутствии двух посеянных членов, никогда не
    мог упасть -- это и есть 'молчаливый ноль' не по букве)."""
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(prep.ep, "SETTINGS_PATH", str(settings))
    monkeypatch.setattr(prep.ep, "_chain_paths",
                         lambda: {".claude/settings.json", "tools/wiring_check.py"})
    run_ctx = _run_ctx_for(tmp_path, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True
    assert "вырождено" in ev.reason
    assert "членов сверх двух безусловно посеянных -- 0" in ev.reason


def test_git_pathset_hooks_one_extra_member_control_passes(tmp_path, monkeypatch):
    """Позитив-контроль симметрии: РОВНО ОДИН член сверх посеянных --
    контроль ПРОХОДИТ (не вырождено)."""
    settings = tmp_path / "settings.json"
    settings.write_text('{"hint": "python tools/x.py"}', encoding="utf-8")
    monkeypatch.setattr(prep.ep, "SETTINGS_PATH", str(settings))
    monkeypatch.setattr(prep.ep, "_chain_paths",
                         lambda: {".claude/settings.json", "tools/wiring_check.py",
                                   "tools/x.py"})
    chain, reason = prep._resolve_pathset("hooks")
    assert chain is not None, reason
    assert "1 членов сверх посеянных" in reason


# ---------------------------------------------------------------------------
# 38. A14(ж), фикс 8: import enforcement_probe под try/except
# ---------------------------------------------------------------------------

def test_git_pathset_ep_none_is_alive_fail_closed_with_reason(monkeypatch):
    """Быстрый юнит-пин нижестоящей ветки (ep is None) -- без файлового
    ввода-вывода."""
    monkeypatch.setattr(prep, "ep", None)
    monkeypatch.setattr(prep, "_EP_IMPORT_ERROR", "ImportError: имитация сбоя импорта")
    run_ctx = _run_ctx_for(REPO_ROOT, [], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    ev = prep.evaluate_predicate("git.pathset:hooks", run_ctx)
    assert ev.alive is True
    assert "enforcement_probe недоступен" in ev.reason
    assert "имитация сбоя импорта" in ev.reason


def test_broken_enforcement_probe_import_does_not_crash_module(tmp_path):
    """A14(ж) полный контур: import enforcement_probe падает НАСТОЯЩИМ
    импортом (не моком) -- window-прогон и --check-form живут (rc по
    контракту §4.7, не traceback). Порча КОПИИ дерева (command hygiene
    п.7г) -- живой tools/enforcement_probe.py НЕ трогается (см. отчёт:
    хеш-witness ДО и ПОСЛЕ этого теста идентичен, копия делает даже сам
    откат ненужным -- ничего не портится)."""
    scratch_tools = tmp_path / "tools"
    scratch_tools.mkdir()
    shutil.copy(REPO_ROOT / "tools" / "calibration_prepass.py", scratch_tools)
    shutil.copy(REPO_ROOT / "tools" / "calibration_counts.py", scratch_tools)
    (scratch_tools / "enforcement_probe.py").write_text(
        "raise ImportError('deliberately broken for A14ж test')\n", encoding="utf-8",
    )
    proto = write_protocol(tmp_path, CHK0_VALID)
    rc = default_rc(tmp_path)
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    proc_window = subprocess.run(
        [sys.executable, str(scratch_tools / "calibration_prepass.py"),
         "--window-start", "2026-08-14T00:00:00", "--protocol", str(proto),
         "--journal", str(j), "--registry", str(reg), "--rule-coverage", str(rc)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert proc_window.returncode == 0, proc_window.stdout + proc_window.stderr
    assert "Traceback" not in proc_window.stderr
    assert "ПРЕ-ПАСС НЕ ОТРАБОТАЛ" not in proc_window.stderr

    proc_form = subprocess.run(
        [sys.executable, str(scratch_tools / "calibration_prepass.py"), "--check-form",
         "--protocol", str(proto), "--rule-coverage", str(rc)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )
    assert proc_form.returncode == 0, proc_form.stdout + proc_form.stderr
    assert "Traceback" not in proc_form.stderr


# ---------------------------------------------------------------------------
# 39. A14(з), фикс 4: красные/зелёные половины §4.5 пинят БОЕВОЙ вывод
#     (render_window_report/CLI), не только evaluate_predicate
# ---------------------------------------------------------------------------

def test_battery_z_full_pipeline_git_paths_future_window_form_alive_render(tmp_path):
    """Зелёная половина на БОЕВОМ пути: build_window_report +
    render_window_report на РЕАЛЬНОМ (не моканом) окне без коммитов --
    строка чека в РЕНДЕРЕ несёт "форма жива", не только EvalResult."""
    proto = write_protocol(REPO_ROOT, (
        "0. **Чек git.paths будущее окно.**\n"
        "<!--CHK 0|src:git|pred:git.paths:no-such-path-xyz-abc/**|rules:RC§1/R6|"
        "status:живой-->\n"
        "    тело чека.\n\n"
    ), name="future_window_proto.md")
    try:
        j = write_journal(tmp_path, [])
        run_ctx = _run_ctx_for(REPO_ROOT, [str(j)], "2099-01-01T00:00:00",
                                "2099-01-02T00:00:00")
        report = prep.build_window_report(proto, run_ctx)
        rendered = prep.render_window_report(
            report, "2099-01-01T00:00:00", "2099-01-02T00:00:00", "обычный", "test",
            [str(j)], proto,
        )
        assert "0: ПУСТ" in rendered
        assert "форма жива" in rendered
        assert "коммитов окна" in rendered
    finally:
        proto.unlink(missing_ok=True)


def test_battery_z_red_half_full_pipeline_run_git_empty_string_render(tmp_path, monkeypatch):
    """Красная половина на БОЕВОМ пути: monkeypatch _run_git -> "" ->
    рендер чека остаётся ЖИВ (fail-closed), а НЕ "форма жива" -- сторож
    не даёт красной половине притвориться зелёной на публичном пути."""
    proto = write_protocol(tmp_path, (
        "0. **Чек git.paths.**\n"
        "<!--CHK 0|src:git|pred:git.paths:tools/**|rules:RC§1/R6|status:живой-->\n"
        "    тело чека.\n\n"
    ))
    j = write_journal(tmp_path, [])
    monkeypatch.setattr(prep, "_run_git", lambda *a, **k: "")
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "0: ЖИВ" in rendered
    assert "fail-closed" in rendered
    assert "форма жива" not in rendered


def test_battery_z_cli_git_paths_future_window_form_alive_end_to_end(tmp_path):
    """То же зелёное поведение через CLI end-to-end (subprocess) --
    реальный REPO_ROOT, окно в будущем без коммитов."""
    proto = write_protocol(tmp_path, (
        "0. **Чек git.paths будущее окно.**\n"
        "<!--CHK 0|src:git|pred:git.paths:no-such-path-xyz-abc/**|rules:RC§1/R6|"
        "status:живой-->\n"
        "    тело чека.\n\n"
    ))
    j = write_journal(tmp_path, [])
    reg = tmp_path / "reg.jsonl"
    proc = run_cli([
        "--window-start", "2099-01-01T00:00:00", "--window-end", "2099-01-02T00:00:00",
        "--protocol", str(proto), "--journal", str(j), "--registry", str(reg),
        "--rule-coverage", str(default_rc(tmp_path)),
    ])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0: ПУСТ" in proc.stdout
    assert "форма жива" in proc.stdout
    assert "коммитов окна" in proc.stdout


# ---------------------------------------------------------------------------
# 40. К2-контроль после фикс-раунда A14 -- см. отчёт (числа N/M/живых
#     идентичны; гейт-строка на реальном окне без принудительных тел не
#     меняется, т.к. F==0 там).
# ---------------------------------------------------------------------------

def test_k2_window_gate_line_unchanged_when_no_forced_bytes(tmp_path):
    """A14(a): на окне БЕЗ форсированных тел (F==0) гейт-строка (база,
    вердикт, ±d) идентична и ДО, и ПОСЛЕ блокера 1 -- дельта базы
    N-F==N-0==N. Регресс-пин K2-нейтральности блокера 1 на синтетике
    (реальный прогон -- в witness отчёта)."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    run_ctx = _run_ctx_for(tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00")
    report = prep.build_window_report(proto, run_ctx)
    assert report["bodies_forced_bytes"] == 0
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    to_read = report["to_read_bytes"]
    gate_diff = to_read - prep.GATE_A_THRESHOLD_BYTES
    sign = "+" if gate_diff >= 0 else ""
    verdict = "ВЗЯТ" if to_read <= prep.GATE_A_THRESHOLD_BYTES else "НЕ ВЗЯТ"
    entry = prep.gate_a_active_entry()
    # Р-D: суффикс подъёма строится ТЕМ ЖЕ правилом, что и продакшн-код.
    raised = entry.get("raised") or {}
    raise_suffix = ""
    if raised:
        raise_no = sum(1 for e in prep.GATE_A_HISTORY
                       if not e.get("annulled") and e.get("raised"))
        raise_suffix = (
            f"; ПОДЪЁМ №{raise_no} словом оператора {entry.get('date')} "
            f"с {raised.get('from')} Б от замера {raised.get('measured_breach')} Б"
        )
    assert (
        f"гейт (а) ≤{prep.GATE_A_THRESHOLD_BYTES} Б (храповик от замера "
        f"{entry['date']}, окно {entry['window_kind']}, K={entry['K']}"
        f"{raise_suffix}): "
        f"{verdict} ({sign}{gate_diff} Б)"
    ) in rendered


# =============================================================================
# W4-3 (§4.8/A2/Р9): ХРАПОВИК ГЕЙТА (а) -- GATE_A_HISTORY, провенанс ИТОГ,
# монотонность, границы порога. Арифметика witness: measured=139042 (N-F
# типового окна на посаженном дереве после W4-2, окно закреплено ts
# 2026-08-14T12:12:34, A11) -> ceil(139042*1.05/100)*100 == 146000.
# Р-D (2026-08-20, слово оператора, t-568): подъём -- та же формула от
# нового замера: measured=146664 (диета узла B, +664 сверх 146000) ->
# ceil(146664*1.05/100)*100 == 154000; прежняя запись 146000 остаётся в
# истории нетронутой (пристройка, не переписывание).
# =============================================================================


def test_gate_a_history_first_entry_is_annulled_pre_m2_bet():
    """A2: элемент 57500 (ставка до-M2-мира) несёт annulled со словом
    Архитектора Р1(B') и является ПЕРВЫМ, но не активным, элементом
    истории."""
    first = prep.GATE_A_HISTORY[0]
    assert first["threshold"] == 57_500
    assert first.get("annulled"), "первый элемент обязан нести annulled (A2)"
    assert "Р1(B" in first["annulled"]
    assert "08-19" in first["annulled"]


def test_gate_a_threshold_bytes_equals_last_history_entry():
    """§4.8(ii): GATE_A_THRESHOLD_BYTES == GATE_A_HISTORY[-1]["threshold"]."""
    assert prep.GATE_A_THRESHOLD_BYTES == prep.GATE_A_HISTORY[-1]["threshold"]
    assert prep.GATE_A_THRESHOLD_BYTES == 154_000


def test_gate_a_active_entry_arithmetic_w4_3_measured_to_threshold():
    """Арифметика порога -- переведена на АКТИВНУЮ запись после подъёма Р-D:
    measured=146664, K=1.05 -> ceil(measured*K/100)*100 == 154000 ==
    GATE_A_HISTORY[-1] (прежняя арифметика 139042->146000 не потеряна --
    отдельный тест ниже, test_gate_a_history_previous_entry_untouched_by_raise)."""
    entry = prep.gate_a_active_entry()
    assert entry["measured"] == 146_664
    assert entry["K"] == 1.05
    assert entry["window_start"] == "2026-08-14T12:12:34"
    assert entry["window_kind"] == "типовое"
    p = math.ceil(entry["measured"] * entry["K"] / 100) * 100
    assert p == entry["threshold"] == 154_000


def test_gate_a_history_previous_entry_untouched_by_raise():
    """Тест-прецедент на разграничение форм (К2): подъём -- ПРИСТРОЙКА,
    не переписывание. Прежняя запись 146000 остаётся в истории НЕТРОНУТОЙ
    -- на предпоследнем месте, measured==139_042, поля annulled у неё НЕТ
    (annulled = "записи не должно было быть", raised = "запись была верна
    и превзойдена фактом" -- разные вещи и разные поля). Прежняя арифметика
    W4-3 (139042 -> 146000) не потеряна подъёмом."""
    entry = prep.GATE_A_HISTORY[-2]
    assert entry["measured"] == 139_042
    assert entry["K"] == 1.05
    assert entry["window_start"] == "2026-08-14T12:12:34"
    assert entry["window_kind"] == "типовое"
    p = math.ceil(entry["measured"] * entry["K"] / 100) * 100
    assert p == entry["threshold"] == 146_000
    assert not entry.get("annulled")
    assert "raised" not in entry


def test_gate_a_history_monotonic_real_history_ok():
    """Реальная константа GATE_A_HISTORY проходит собственный храповик --
    не только синтетика."""
    ok, msg = prep.check_gate_a_history_monotonic()
    assert ok, msg


def test_gate_a_history_annulled_entry_excluded_from_monotonicity():
    """A2: аннулированная запись НЕ участвует в монотонности -- синтетика,
    где аннулированный порог ВЫШЕ активного, не красит тест (аннулированный
    элемент попросту не рассматривается цепочкой)."""
    synthetic = [
        {"threshold": 999_999, "annulled": "тест: старая ставка"},
        {"threshold": 146_000, "date": "x", "measured": 1, "window_start": "x",
         "window_end": "x", "window_kind": "типовое", "K": 1.05, "basis": "x"},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(synthetic)
    assert ok, msg


def test_gate_a_history_monotonic_red_half_growth_without_basis_flags():
    """Красная половина храповика: активная цепочка РАСТЁТ (100 -> 150) без
    блока raised -- check_gate_a_history_monotonic ОБЯЗАНА вернуть False с
    сообщением, называющим легальный выход дословно (Р-D §1): снизить --
    легально всегда; поднять -- только явным словом оператора, записанным
    блоком raised."""
    synthetic = [
        {"threshold": 100, "date": "d1", "measured": 90, "window_start": "s1",
         "window_end": "e1", "window_kind": "типовое", "K": 1.05, "basis": "b1"},
        {"threshold": 150, "date": "d2", "measured": 140, "window_start": "s2",
         "window_end": "e2", "window_kind": "типовое", "K": 1.05, "basis": "b2"},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(synthetic)
    assert not ok
    assert "легально всегда" in msg
    assert "словом оператора" in msg
    assert "raised" in msg


def test_gate_a_history_monotonic_plateau_and_decrease_are_legal():
    """§7.1: новое==прежнему -> плато легально; снижение -- тоже легально
    (граница и обе стороны -- одним тестом, правило 6а)."""
    plateau = [{"threshold": 100, "date": "d1"}, {"threshold": 100, "date": "d2"}]
    ok, msg = prep.check_gate_a_history_monotonic(plateau)
    assert ok, msg

    decrease = [{"threshold": 200, "date": "d1"}, {"threshold": 100, "date": "d2"}]
    ok, msg = prep.check_gate_a_history_monotonic(decrease)
    assert ok, msg


def test_gate_a_itog_provenance_verbatim_form(tmp_path):
    """§4.3 дословно: «гейт (а) ≤P Б (храповик от замера <дата>, окно <тип>,
    K=<K>): ВЗЯТ/НЕ ВЗЯТ (±d)» -- провенанс читается из активной записи
    истории, НЕ из параметров текущего прогона (mode/mode_reason здесь
    заведомо другие -- "обычный"/"test")."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    entry = prep.gate_a_active_entry()
    # Р-D: активная запись сегодня несёт raised -- суффикс строится ТЕМ ЖЕ
    # правилом, что и продакшн-код (render_window_report), иначе пин ломается
    # первым же подъёмом.
    raised = entry.get("raised") or {}
    raise_suffix = ""
    if raised:
        raise_no = sum(1 for e in prep.GATE_A_HISTORY
                       if not e.get("annulled") and e.get("raised"))
        raise_suffix = (
            f"; ПОДЪЁМ №{raise_no} словом оператора {entry.get('date')} "
            f"с {raised.get('from')} Б от замера {raised.get('measured_breach')} Б"
        )
    assert (
        f"(храповик от замера {entry['date']}, окно {entry['window_kind']}, "
        f"K={entry['K']}{raise_suffix}):"
    ) in rendered


def test_gate_a_empty_window_reference_line_printed(tmp_path):
    """Р9 "число пустого окна печатается справочно": строка присутствует
    рядом с ИТОГ, помечена как НЕ входящая в формулу порога -- на ЛЮБОМ
    окне (даже типовом), т.к. это фиксированная справочная константа
    замера, а не пересчёт текущего окна."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert f"{prep.GATE_A_EMPTY_WINDOW_REFERENCE_BYTES} Б" in rendered
    assert "не входит в формулу порога" in rendered


def test_gate_a_threshold_boundary_at_p_taken_and_p_plus_1_not_taken(tmp_path, monkeypatch):
    """§7.1 порог P: измерено == P -> ВЗЯТ (+0); измерено == P+1 -> НЕ ВЗЯТ
    (+1 Б) -- граница и её пересечение одним тестом (правило 6а)."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))
    measured = report["to_read_bytes"] - report.get("bodies_forced_bytes", 0)

    monkeypatch.setattr(prep, "GATE_A_THRESHOLD_BYTES", measured)
    rendered_at = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "): ВЗЯТ (+0 Б)" in rendered_at, rendered_at

    monkeypatch.setattr(prep, "GATE_A_THRESHOLD_BYTES", measured - 1)
    rendered_over = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "): НЕ ВЗЯТ (+1 Б)" in rendered_over, rendered_over


def test_gate_a_k2_invariant_numbers_unchanged_across_threshold_bump(tmp_path, monkeypatch):
    """К2-инвариант W4-3: смена активного порога (57500 аннулированный ->
    146000 W4-3) НЕ имеет права двигать to_read/total/alive -- один и тот
    же report рендерится при ОБОИХ значениях, ОБЕ строки ИТОГ показаны
    ниже в тексте теста (assert message): совпадает всё до "· гейт (а)",
    расходится только гейт-подстрока."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))

    monkeypatch.setattr(prep, "GATE_A_THRESHOLD_BYTES", 57_500)
    rendered_old = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    monkeypatch.setattr(prep, "GATE_A_THRESHOLD_BYTES", 146_000)
    rendered_new = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    prefix_old = rendered_old.split("· гейт (а)")[0]
    prefix_new = rendered_new.split("· гейт (а)")[0]
    assert prefix_old == prefix_new, (
        "К2-инвариант нарушен -- числа to_read/total/alive/тела/принудительно "
        f"разошлись:\nСТАРЫЙ: {prefix_old!r}\nНОВЫЙ: {prefix_new!r}"
    )
    itog_old = [ln for ln in rendered_old.splitlines() if ln.startswith("ИТОГ:")][0]
    itog_new = [ln for ln in rendered_new.splitlines() if ln.startswith("ИТОГ:")][0]
    assert "≤57500 Б" in itog_old, itog_old
    assert "≤146000 Б" in itog_new, itog_new
    assert itog_old != itog_new  # гейт-подстрока обязана отличаться -- обе строки выше


# =============================================================================
# Р-D (2026-08-20, t-568): ПОДЪЁМ ХРАПОВИКА 146000 -> 154000 словом
# оператора. Блок raised, его четыре поля, всплытие в ИТОГ, границы нового
# порога, отказ --check-form на битой синтетике. В КОНЕЦ существующей
# секции W4-3, новой секции не заводим.
# =============================================================================


def test_gate_a_raise_entry_carries_full_provenance():
    """К3: активная запись 154000 несёт ПОЛНЫЙ блок raised -- from==146000,
    measured_breach==146664>from, word/reason непустые -- и сама реальная
    история проходит собственный храповик (не только синтетика)."""
    entry = prep.gate_a_active_entry()
    raised = entry.get("raised")
    assert isinstance(raised, dict)
    assert raised["from"] == 146_000
    assert raised["measured_breach"] == 146_664
    assert raised["measured_breach"] > raised["from"]
    assert raised["word"].strip()
    assert raised["reason"].strip()
    ok, msg = prep.check_gate_a_history_monotonic()
    assert ok, msg


def test_gate_a_raise_without_raised_block_is_red():
    """Рост без блока raised вовсе (ключ отсутствует) -- красный, сообщение
    называет легальный выход дословно."""
    synthetic = [
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2"},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(synthetic)
    assert not ok
    assert "БЕЗ ОБЪЯВЛЕННОГО ПОДЪЁМА" in msg


@pytest.mark.parametrize("bad_raised", [[], "текст", True, None])
def test_gate_a_raise_block_non_dict_is_red(bad_raised):
    """raised не-словарь (list/str/bool/None) -- красный той же веткой, что
    и полное отсутствие блока (изоморфно not isinstance(raised, dict))."""
    synthetic = [
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2", "raised": bad_raised},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(synthetic)
    assert not ok
    assert "БЕЗ ОБЪЯВЛЕННОГО ПОДЪЁМА" in msg


def test_gate_a_raise_with_incomplete_raised_block_is_red():
    """Битый провенанс: по прогону на каждое из четырёх полей -- красный,
    сообщение называет ИМЕННО отсутствующее поле; пустая строка и строка
    из одних пробелов считаются пустыми той же веткой (проверка на
    ЛОЖНОСТЬ значения, не на наличие ключа)."""
    base_raised = {
        "from": 100, "word": "слово оператора", "measured_breach": 200,
        "reason": "тестовая причина",
    }
    for field in ("from", "word", "measured_breach", "reason"):
        raised = dict(base_raised)
        del raised[field]
        synthetic = [
            {"threshold": 100, "date": "d1"},
            {"threshold": 150, "date": "d2", "raised": raised},
        ]
        ok, msg = prep.check_gate_a_history_monotonic(synthetic)
        assert not ok, f"поле {field} отсутствует, но вердикт зелёный"
        assert field in msg, f"сообщение не называет отсутствующее поле {field}: {msg}"

    raised_empty = dict(base_raised)
    raised_empty["word"] = ""
    ok, msg = prep.check_gate_a_history_monotonic([
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2", "raised": raised_empty},
    ])
    assert not ok
    assert "word" in msg

    raised_blank = dict(base_raised)
    raised_blank["word"] = "   "
    ok, msg = prep.check_gate_a_history_monotonic([
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2", "raised": raised_blank},
    ])
    assert not ok, "строка из одних пробелов обязана считаться пустой"
    assert "word" in msg


def test_gate_a_raise_without_measured_breach_is_red():
    """Граница measured_breach с ОБЕИХ сторон (правило 6а): ==from ->
    красный (не пробил), ==from-1 -> красный -- обе ветки решаются ДО
    проверки measured/K (порядок функции), так что синтетика может их не
    нести. ==from+1 -> зелёный ТРЕБУЕТ (Ф3 t-569, ремедиация критик-гейта)
    валидных measured/K, согласованных с формулой (Ф3) и равных
    measured_breach (Ф1) -- порог 150 недостижим НИКАКОЙ формулой (не
    кратен 100 по построению ceil(...)*100), поэтому зелёная ветка несёт
    отдельный порог 200, достижимый формулой."""
    def synthetic(breach):
        return [
            {"threshold": 100, "date": "d1"},
            {"threshold": 150, "date": "d2", "raised": {
                "from": 100, "word": "слово оператора", "measured_breach": breach,
                "reason": "причина",
            }},
        ]

    ok, msg = prep.check_gate_a_history_monotonic(synthetic(100))
    assert not ok, msg
    assert "БЕЗ ПРОБИТОГО ЗАМЕРА" in msg

    ok, msg = prep.check_gate_a_history_monotonic(synthetic(99))
    assert not ok, msg
    assert "БЕЗ ПРОБИТОГО ЗАМЕРА" in msg

    green = [
        {"threshold": 100, "date": "d1"},
        {"threshold": 200, "date": "d2", "measured": 101, "K": 1.05, "raised": {
            "from": 100, "word": "слово оператора", "measured_breach": 101,
            "reason": "причина",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(green)
    assert ok, msg


def test_gate_a_raise_off_formula_is_red():
    """Подъём с полным валидным raised (measured_breach==cur['measured'],
    Ф1 t-569 удовлетворён), но threshold НЕ по формуле
    ceil(measured*K/100)*100 -- красный."""
    synthetic = [
        {"threshold": 100, "date": "d1"},
        {"threshold": 999, "date": "d2", "measured": 200, "K": 1.05,
         "raised": {
             "from": 100, "word": "слово оператора", "measured_breach": 200,
             "reason": "причина",
         }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(synthetic)
    assert not ok
    assert "не по формуле" in msg


def test_gate_a_raise_from_mismatch_is_red():
    """raised['from'] не совпадает с предыдущим активным порогом -- красный,
    провенанс указывает не на ту запись."""
    synthetic = [
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2", "raised": {
            "from": 999, "word": "слово оператора", "measured_breach": 1000,
            "reason": "причина",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(synthetic)
    assert not ok
    assert "указывает не на ту запись" in msg


def test_gate_a_itog_prints_raise_mark_verbatim(tmp_path):
    """К6/Д3: строка ИТОГ несёт метку "ПОДЪЁМ №N словом оператора <дата> с
    <прежний> Б от замера <measured_breach> Б" -- дословный пин на реальной
    GATE_A_HISTORY (154000, raised from=146000, measured_breach=146664),
    без монки-патча. Ф6 (критик-гейт t-569): measured_breach обязан
    печататься в ИТОГ -- выдуманный замер самоопровергается прогоном."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))
    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert (
        "ПОДЪЁМ №1 словом оператора 2026-08-20 с 146000 Б от замера 146664 Б"
        in rendered
    ), rendered


def test_gate_a_itog_without_raise_is_byte_identical(tmp_path, monkeypatch):
    """К6: мир БЕЗ подъёма (активная запись без raised) печатает строку ИТОГ
    в ПРЕЖНЕЙ форме байт в байт -- суффикс пуст, между K=<K> и ): нет ничего
    сверх этого (никакого "; ПОДЪЁМ")."""
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))

    synthetic_history = [
        {"date": "2099-01-01", "threshold": 100, "measured": 90,
         "window_start": "s", "window_end": "e", "window_kind": "типовое",
         "K": 1.05, "basis": "синтетика без подъёма"},
    ]
    monkeypatch.setattr(prep, "GATE_A_HISTORY", synthetic_history)
    monkeypatch.setattr(prep, "GATE_A_THRESHOLD_BYTES", 100)

    rendered = prep.render_window_report(
        report, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    to_read = report["to_read_bytes"]
    gate_diff = to_read - 100
    sign = "+" if gate_diff >= 0 else ""
    verdict = "ВЗЯТ" if to_read <= 100 else "НЕ ВЗЯТ"
    expected_gate = (
        f"гейт (а) ≤100 Б (храповик от замера 2099-01-01, окно типовое, "
        f"K=1.05): {verdict} ({sign}{gate_diff} Б)"
    )
    assert expected_gate in rendered, rendered
    assert "ПОДЪЁМ" not in rendered


def test_gate_a_boundary_at_real_threshold_154000_and_154001(tmp_path):
    """К7: реальный (не монкипатченный) порог 154000 -- измерено==154000 ->
    ВЗЯТ (+0 Б); ==154001 -> НЕ ВЗЯТ (+1 Б)."""
    assert prep.GATE_A_THRESHOLD_BYTES == 154_000
    j = write_journal(tmp_path, [])
    proto = write_protocol(tmp_path, _pilot_body())
    report = prep.build_window_report(proto, _run_ctx_for(
        tmp_path, [str(j)], "2026-08-14T00:00:00", "2026-08-16T00:00:00"))

    report_at = dict(report)
    report_at["to_read_bytes"] = 154_000
    report_at["bodies_forced_bytes"] = 0
    rendered_at = prep.render_window_report(
        report_at, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "): ВЗЯТ (+0 Б)" in rendered_at, rendered_at

    report_over = dict(report)
    report_over["to_read_bytes"] = 154_001
    report_over["bodies_forced_bytes"] = 0
    rendered_over = prep.render_window_report(
        report_over, "2026-08-14T00:00:00", "2026-08-16T00:00:00", "обычный", "test",
        [str(j)], proto,
    )
    assert "): НЕ ВЗЯТ (+1 Б)" in rendered_over, rendered_over


def test_gate_a_check_form_reports_broken_ratchet(monkeypatch):
    """Д5: --check-form зовёт check_gate_a_history_monotonic -- битая
    (растущая без raised) синтетика красит ДЕФЕКТ. Живой файл НЕ портится
    (гигиена п.7(г)) -- монки-патч атрибута модуля, не запись на диск."""
    broken_history = [
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2"},
    ]
    monkeypatch.setattr(prep, "GATE_A_HISTORY", broken_history)
    result = prep.run_check_form(prep.DEFAULT_PROTOCOL, prep.DEFAULT_RULE_COVERAGE, True)
    ratchet_defects = [d for d in result.defects if "ХРАПОВИК ГЕЙТА (а)" in d]
    assert ratchet_defects, result.defects
    assert "БЕЗ ОБЪЯВЛЕННОГО ПОДЪЁМА" in ratchet_defects[0]


def test_gate_a_history_monotonic_adversarial_battery():
    """Адверсариальная мини-батарея сторожа (§4): его вход -- структура
    данных, и он на пути прогона. threshold как None (значение, не
    отсутствие ключа); пустой список; список из одной записи; история, где
    ВСЕ записи annulled; measured=0/K=0 на raised -- КРАСНЫЙ (Ф3 t-569:
    ремедиация критик-гейта закрыла атаку 5б -- "измерение ложно, формула
    пропущена" БОЛЬШЕ НЕ пропускает ветку, красит); отрицательный
    threshold на плато; лишние неизвестные ключи (игнорируются)."""
    ok, msg = prep.check_gate_a_history_monotonic(
        [{"threshold": 100}, {"threshold": None}]
    )
    assert not ok, msg

    ok, msg = prep.check_gate_a_history_monotonic([])
    assert not ok, msg

    ok, msg = prep.check_gate_a_history_monotonic([{"threshold": 100}])
    assert ok, msg

    ok, msg = prep.check_gate_a_history_monotonic([
        {"threshold": 100, "annulled": "тест"},
        {"threshold": 200, "annulled": "тест"},
    ])
    assert not ok, msg

    ok, msg = prep.check_gate_a_history_monotonic([
        {"threshold": 100, "date": "d1"},
        {"threshold": 150, "date": "d2", "measured": 0, "K": 0, "raised": {
            "from": 100, "word": "слово оператора", "measured_breach": 120,
            "reason": "причина",
        }},
    ])
    assert not ok, msg
    assert "НЕотключаема" in msg

    ok, msg = prep.check_gate_a_history_monotonic([
        {"threshold": -100, "date": "d1"}, {"threshold": -100, "date": "d2"},
    ])
    assert ok, msg

    ok, msg = prep.check_gate_a_history_monotonic([
        {"threshold": 100, "date": "d1", "unknown_key": "x"},
        {"threshold": 200, "date": "d2", "unknown_key": "y", "measured": 101,
         "K": 1.05, "raised": {
            "from": 100, "word": "слово оператора", "measured_breach": 101,
            "reason": "причина", "extra_field": "z",
        }},
    ])
    assert ok, msg


# =============================================================================
# t-569 (критик-гейт, ремедиация храповика (а)): ШЕСТЬ АТАК критика --
# каждая была зелёной ДО этого узла (см. отчёт: скрипт red-control
# attack_redcontrol.py, OLD-копия функции против NEW), обязана быть
# красной ПОСЛЕ. Ф1 закрывает атаки 1/2 (measured_breach отвязан от
# cur.measured); Ф2 закрывает атаку 4 (K не сверялся с 1.05); Ф3 закрывает
# атаки 5/5б (measured/K отключали формулу); Ф4 закрывает СБРОС
# (аннулирование как обнуление цепочки).
# =============================================================================


def test_gate_a_attack1_measured_breach_disconnected_from_cur_measured_is_red():
    """АТАКА 1 (критик): подъём 154000->525000 при РЕАЛЬНОМ пробое всего
    +1 Б (measured_breach=154001), но формула считается от сфабрикованного
    cur['measured']=500000 -- Ф1 обязан покраснеть: провенанс пробоя и
    замер формулы -- РАЗНЫЕ числа."""
    hist = [
        {"threshold": 154_000, "date": "d1", "measured": 146_664, "K": 1.05},
        {"threshold": 525_000, "date": "d2", "measured": 500_000, "K": 1.05, "raised": {
            "from": 154_000, "word": "слово оператора (атака)",
            "measured_breach": 154_001,
            "reason": "атака 1: замер формулы не тот же замер, что доказал пробой",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert not ok, msg
    assert "не совпадает с cur['measured']" in msg


def test_gate_a_attack2_emergency_window_measured_vs_typical_breach_is_red():
    """АТАКА 2 (критик): порог считается от "аварийного" замера (200000),
    а провенанс пробоя доказан "типовым" окном (+10 Б от прежнего порога)
    -- та же линия Ф1, другой замер -- обязан покраснеть тем же
    сообщением о несовпадении чисел."""
    hist = [
        {"threshold": 100_000, "date": "d1", "measured": 95_000, "K": 1.05},
        {"threshold": 210_000, "date": "d2", "measured": 200_000, "K": 1.05, "raised": {
            "from": 100_000, "word": "слово оператора (атака)",
            "measured_breach": 100_010,
            "reason": "атака 2: порог от аварийного окна, пробой типового +10 Б",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert not ok, msg
    assert "не совпадает с cur['measured']" in msg


def test_gate_a_attack4_k_not_1_05_is_red():
    """АТАКА 4 (критик): та же пара measured/measured_breach (Ф1
    удовлетворён), формула самосогласована, но K=1.2 вместо канонического
    1.05 -- Ф2 обязан покраснеть."""
    hist = [
        {"threshold": 100_000, "date": "d1", "measured": 95_000, "K": 1.05},
        {"threshold": 120_100, "date": "d2", "measured": 100_001, "K": 1.2, "raised": {
            "from": 100_000, "word": "слово оператора (атака)",
            "measured_breach": 100_001,
            "reason": "атака 4: K=1.2 вместо 1.05",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert not ok, msg
    assert "другой K" in msg


def test_gate_a_attack5_no_measured_k_at_all_is_red():
    """АТАКА 5 (критик): запись БЕЗ measured/K вовсе, порог 900000,
    реальный пробой +1 Б -- Ф3 обязан покраснеть (формула НЕотключаема на
    raised-записи)."""
    hist = [
        {"threshold": 800_000, "date": "d1"},
        {"threshold": 900_000, "date": "d2", "raised": {
            "from": 800_000, "word": "слово оператора (атака)",
            "measured_breach": 800_001,
            "reason": "атака 5: запись без measured/K, порог 900000",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert not ok, msg
    assert "НЕотключаема" in msg


def test_gate_a_attack5b_measured_zero_k_zero_is_red():
    """АТАКА 5б (критик): measured=0/K=0 -- ложные (falsy), формула должна
    была бы пропуститься по старому правилу -- Ф3 обязан покраснеть."""
    hist = [
        {"threshold": 800_000, "date": "d1"},
        {"threshold": 900_000, "date": "d2", "measured": 0, "K": 0, "raised": {
            "from": 800_000, "word": "слово оператора (атака)",
            "measured_breach": 800_001,
            "reason": "атака 5б: measured=0/K=0",
        }},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert not ok, msg
    assert "НЕотключаема" in msg


def test_gate_a_attack_reset_mass_annul_of_measured_entries_is_red():
    """СБРОС (критик): вся реальная цепочка (несущая measured) аннулирована
    + две фиктивные записи 900000 БЕЗ raised (плато, легально молча) --
    Ф4 обязан покраснеть на первой же аннулированной записи с реальным
    measured, ДО того как вычисляется активная цепочка."""
    hist = [
        {"threshold": 57_500, "annulled": "тест: до-M2 ставка (measured=None)"},
        {"threshold": 146_000, "measured": 139_042,
         "annulled": "СБРОС: попытка обнулить цепочку массовым аннулированием"},
        {"threshold": 154_000, "measured": 146_664,
         "annulled": "СБРОС: попытка обнулить цепочку массовым аннулированием"},
        {"threshold": 900_000, "date": "x1"},
        {"threshold": 900_000, "date": "x2"},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert not ok, msg
    assert "аннулирование реальной, когда-либо активной записи запрещено" in msg


def test_gate_a_ф4_bet_entry_without_measured_stays_annullable():
    """Позитивный контроль Ф4 той же формы: запись-СТАВКА (measured
    отсутствует/None, как настоящий entry[0]) легально аннулируема --
    инвариант бьёт только по РЕАЛЬНЫМ (measured) записям, не по ставкам."""
    hist = [
        {"threshold": 999_999, "annulled": "тест: ставка без замера"},
        {"threshold": 146_000, "date": "x", "measured": 1, "window_start": "x",
         "window_end": "x", "window_kind": "типовое", "K": 1.05, "basis": "x"},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist)
    assert ok, msg


def test_gate_a_ф1_measured_breach_equals_measured_boundary():
    """Правило 6а: measured_breach == cur['measured'] -> зелёный;
    расхождение на 1 в ЛЮБУЮ сторону -> красный (граница и оба пересечения
    одним тестом). breach выбран строго выше from=100000 во всех трёх
    вариантах, чтобы срабатывала ИМЕННО проверка Ф1, а не более ранняя
    "БЕЗ ПРОБИТОГО ЗАМЕРА"."""
    def hist_with(breach):
        return [
            {"threshold": 100_000, "date": "d1", "measured": 95_000, "K": 1.05},
            {"threshold": 105_100, "date": "d2", "measured": 100_010, "K": 1.05, "raised": {
                "from": 100_000, "word": "слово оператора", "measured_breach": breach,
                "reason": "причина",
            }},
        ]
    ok, msg = prep.check_gate_a_history_monotonic(hist_with(100_010))
    assert ok, msg
    ok, msg = prep.check_gate_a_history_monotonic(hist_with(100_009))
    assert not ok, msg
    assert "не совпадает с cur['measured']" in msg
    ok, msg = prep.check_gate_a_history_monotonic(hist_with(100_011))
    assert not ok, msg
    assert "не совпадает с cur['measured']" in msg


def test_gate_a_ф2_k_boundary_1_05_only():
    """Границы: K == 1.05 -> зелёный; 1.04 и 1.06 -> красный (обе стороны
    одним тестом, правило 6а). Порог/measured пересчитаны под каждый K,
    чтобы формула сама по себе была самосогласована -- красит именно
    сверка с 1.05, не формула."""
    def hist_with(k, threshold):
        return [
            {"threshold": 100_000, "date": "d1", "measured": 95_000, "K": 1.05},
            {"threshold": threshold, "date": "d2", "measured": 100_001, "K": k, "raised": {
                "from": 100_000, "word": "слово оператора", "measured_breach": 100_001,
                "reason": "причина",
            }},
        ]
    # K=1.05: ceil(100001*1.05/100)*100 = 105100.
    ok, msg = prep.check_gate_a_history_monotonic(hist_with(1.05, 105_100))
    assert ok, msg
    # K=1.04: ceil(100001*1.04/100)*100 = 104100 -- формула сама сходится,
    # но K != 1.05 -- красный.
    ok, msg = prep.check_gate_a_history_monotonic(hist_with(1.04, 104_100))
    assert not ok, msg
    assert "другой K" in msg
    # K=1.06: ceil(100001*1.06/100)*100 = 106100 -- формула сходится, K
    # != 1.05 -- красный.
    ok, msg = prep.check_gate_a_history_monotonic(hist_with(1.06, 106_100))
    assert not ok, msg
    assert "другой K" in msg


def test_gate_a_ф5_non_numeric_raised_and_cur_fields_no_typeerror():
    """Ф5 (критик-гейт t-569): три ранее необработанных TypeError --
    raised['measured_breach'] строкой, cur['measured'] строкой,
    cur['K'] строкой -- ни один НЕ роняет функцию исключением, все три
    дают явный красный вердикт с именем типа. Плюс: raised['from']='100'
    (строка) даёт сообщение, называющее ТИП, а не два визуально
    одинаковых числа."""
    base_raised = {
        "from": 100_000, "word": "слово оператора", "measured_breach": 100_001,
        "reason": "причина",
    }

    # (1) raised['measured_breach'] строкой.
    r1 = dict(base_raised)
    r1["measured_breach"] = "100001"
    hist1 = [
        {"threshold": 100_000, "date": "d1"},
        {"threshold": 105_000, "date": "d2", "measured": 100_001, "K": 1.05,
         "raised": r1},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist1)
    assert not ok, msg
    assert "не число" in msg and "str" in msg

    # (2) cur['measured'] строкой.
    hist2 = [
        {"threshold": 100_000, "date": "d1"},
        {"threshold": 105_000, "date": "d2", "measured": "100001", "K": 1.05,
         "raised": dict(base_raised)},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist2)
    assert not ok, msg
    assert "не число" in msg

    # (3) cur['K'] строкой.
    hist3 = [
        {"threshold": 100_000, "date": "d1"},
        {"threshold": 105_000, "date": "d2", "measured": 100_001, "K": "1.05",
         "raised": dict(base_raised)},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist3)
    assert not ok, msg
    assert "не число" in msg

    # (4) raised['from']='100' (строка) -- тип назван явно, не "100 vs 100".
    r4 = dict(base_raised)
    r4["from"] = "100000"
    hist4 = [
        {"threshold": 100_000, "date": "d1"},
        {"threshold": 105_000, "date": "d2", "measured": 100_001, "K": 1.05,
         "raised": r4},
    ]
    ok, msg = prep.check_gate_a_history_monotonic(hist4)
    assert not ok, msg
    assert "тип str" in msg


def test_gate_a_check_form_broken_numeric_types_gives_defect_not_traceback(monkeypatch):
    """Ф5 боевое последствие: --check-form на истории с нечисловыми
    raised/measured/K полями обязан дать ДЕФЕКТ + exit 1 (main() ->
    return 1), а НЕ трейсбек (SystemExit не поднимается прямым исключением
    из check_gate_a_history_monotonic -- run_check_form ловит (ok, msg)
    как обычный кортеж)."""
    broken_history = [
        {"threshold": 100_000, "date": "d1"},
        {"threshold": 105_000, "date": "d2", "measured": "100001", "K": 1.05, "raised": {
            "from": 100_000, "word": "слово оператора", "measured_breach": 100_001,
            "reason": "причина",
        }},
    ]
    monkeypatch.setattr(prep, "GATE_A_HISTORY", broken_history)
    rc = prep.main(["--check-form"])
    assert rc == 1


def test_gate_a_empty_history_pin_index_error_on_import_path():
    """Пустой вход (Р6(б)/§7 края): GATE_A_HISTORY == [] СЕГОДНЯ роняет
    IndexError на модульном пути вычисления активной записи (та же
    операция, что и GATE_A_THRESHOLD_BYTES = GATE_A_HISTORY[-1]["threshold"]
    при импорте) -- поведение НЕ меняется этим узлом, только пинуется
    тестом. check_gate_a_history_monotonic([]) -- ДРУГОЙ путь: он
    fail-closed красным (см. test_gate_a_history_monotonic_adversarial_
    battery), а не крашем -- это два разных механизма на одном пустом
    входе, и оба закрыты явно."""
    with pytest.raises(IndexError):
        prep.gate_a_active_entry(history=[])
