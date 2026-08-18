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
import subprocess
import sys
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
                rc_path: Path = None) -> prep.CheckFormResult:
    proto = write_protocol(tmp_path, body)
    rc = rc_path or default_rc(tmp_path)
    return prep.run_check_form(proto, rc, require_all)


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
    result = prep.run_check_form(p, default_rc(tmp_path), False)
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
    entries = prep.read_registry(reg)
    assert len(entries) == 1
    assert entries[0]["alive_count"] == report["alive_count"]


def test_control_mode_periodic_trigger(tmp_path):
    reg = tmp_path / "registry.jsonl"
    for i in range(3):
        with open(reg, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"mode": "обычный (x)"}) + "\n")
    mode, reason = prep.determine_mode(prep.read_registry(reg), str(REPO_ROOT),
                                        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md", False)
    assert mode == "КОНТРОЛЬНЫЙ"
    assert "N=4" in reason


def test_control_mode_explicit_flag(tmp_path):
    mode, reason = prep.determine_mode([], str(REPO_ROOT),
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


def test_cli_check_form_exit0_on_clean(tmp_path):
    proto = write_protocol(tmp_path, CHK0_VALID)
    rc = default_rc(tmp_path)
    proc = run_cli(["--check-form", "--protocol", str(proto), "--rule-coverage", str(rc)])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_cli_check_form_exit1_on_defect(tmp_path):
    body = "0. **Чек.**\n<!--CHK 0|src:неизвестно|pred:always|rules:RC§1/R6|status:живой-->\n    тело.\n\n"
    proto = write_protocol(tmp_path, body)
    rc = default_rc(tmp_path)
    proc = run_cli(["--check-form", "--protocol", str(proto), "--rule-coverage", str(rc)])
    assert proc.returncode == 1, proc.stdout + proc.stderr


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
    result = prep.run_check_form(prep.DEFAULT_PROTOCOL, prep.DEFAULT_RULE_COVERAGE, False)
    assert result.defects == [], "\n".join(result.defects)


def test_real_protocol_has_pilot_headers():
    result = prep.run_check_form(prep.DEFAULT_PROTOCOL, prep.DEFAULT_RULE_COVERAGE, False)
    ids = {h.id_str for h in result.headers}
    for expected in ("0", "3", "13", "26", "33", "12(а)", "12(б)"):
        assert expected in ids, f"пилотная шапка {expected} не найдена"


def test_real_protocol_window_run_exit0():
    proc = run_cli(["--window-start", "2026-08-14T12:12:34"])
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "ИТОГ:" in proc.stdout
