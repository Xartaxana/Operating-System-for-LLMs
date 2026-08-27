"""Юнит-смоки tools/dispatch_gate.py (t-152, policy-as-code «ход вниз»).
Прямые вызовы decide() для всех веток + echo-JSON смок подпроцессом
(спека явно требует "юнит-тесты всех веток").

Штабной вариант: dispatch_gate.py в tools/ этого репо -- БЕЗ изменений
относительно кита (см. exam_fullgates_kit/staging_hq/README.md, п.
"dispatch_gate.py -- БЕЗ изменений"), поэтому тест-кейсы перенесены
как есть из exam_fullgates_kit/tools/test_dispatch_gate.py (t-159)."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dispatch_gate  # noqa: E402
import owns_gate  # noqa: E402 -- t-384: эталон истинности для теста равенства
from wallclock_guard import WALLCLOCK_CATASTROPHE_CEILING  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "dispatch_gate.py"


def _run_hook(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _builder_payload(prompt: str, description=None) -> dict:
    tool_input = {"subagent_type": "builder", "prompt": prompt}
    if description is not None:
        tool_input["description"] = description
    return {"tool_name": "Task", "tool_input": tool_input}


# ---------------------------------------------------------------------
# Не Task/Agent -- всегда пропуск.
# ---------------------------------------------------------------------


def test_non_task_tool_passes():
    exit_code, message = dispatch_gate.decide({"tool_name": "Bash", "tool_input": {}})
    assert exit_code == 0
    assert message == ""


def test_missing_tool_input_does_not_crash():
    exit_code, message = dispatch_gate.decide({"tool_name": "Task"})
    assert exit_code == 0


# ---------------------------------------------------------------------
# Проверка 1: DoD-маркеры для builder'а.
# ---------------------------------------------------------------------


def test_builder_without_dod_markers_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload("Просто поправь опечатку в файле x.py.", description="sonnet: fix typo")
    )
    assert exit_code == 2
    assert "без DoD" in message
    assert "правило 11" in message


def test_builder_with_dod_literal_passes_check1():
    # "Почини" (не "поправь") -- намеренно избегаем подстроки "правь"
    # из WRITE_INDICATORS_RE, см. test_write_indicator_substring_
    # collision_in_pravj_is_a_known_finding ниже про эту коллизию.
    exit_code, message = dispatch_gate.decide(
        _builder_payload("Почини опечатку. DoD: тест зелёный.", description="sonnet: fix")
    )
    assert exit_code == 0


def test_builder_with_criteria_priyomki_passes_check1():
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "Почини опечатку. Критерии приёмки: тест проходит.", description="sonnet: fix"
        )
    )
    assert exit_code == 0


def test_builder_with_criteria_priyomki_genitive_singular_passes_check1():
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "Нет критерия приёмки указано явно тут.", description="sonnet: fix"
        )
    )
    assert exit_code == 0


def test_builder_with_witness_passes_check1():
    exit_code, message = dispatch_gate.decide(
        _builder_payload("Почини опечатку, приложи witness.", description="sonnet: fix")
    )
    assert exit_code == 0


def test_builder_with_verification_run_passes_check1():
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "Почини опечатку и прогони проверочный прогон.", description="sonnet: fix"
        )
    )
    assert exit_code == 0
    # /проверочн\w+ прогон/i требует буквально слово "прогон" СРАЗУ
    # после "проверочн\w+ " -- "проверочную команду" НЕ матчится (нет
    # слова "прогон"), это отдельная (валидная) ветка -- проверяем
    # блок, а не пропуск, чтобы не выдать чужое поведение за DoD-маркер.
    exit_code2, message2 = dispatch_gate.decide(
        _builder_payload(
            "Почини опечатку и прогони проверочную команду.", description="sonnet: fix"
        )
    )
    assert exit_code2 == 2
    assert "без DoD" in message2

    exit_code3, _ = dispatch_gate.decide(
        _builder_payload(
            "Почини опечатку и прогони проверочную прогон.", description="sonnet: fix"
        )
    )
    assert exit_code3 == 0


def test_pravj_word_boundary_does_not_match_poprav_or_isprav():
    """НЕГАТИВНЫЙ ЛОК (решение координатора, t-152 retry): исходная
    находка (WRITE_INDICATORS_RE без \\b матчил "правь" ПОДСТРОКОЙ
    внутри "поправь"/"исправь") пофикшена \\b-границами -- "поправь"
    и "исправь" (обычные синонимы "почини", не сигнал владения
    путями) БОЛЬШЕ НЕ триггерят write-признак/требование манифеста.
    До фикса этот же промпт давал exit_code=2, "манифеста" in message
    (см. git-историю этого теста)."""
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный. Пожалуйста, поправь опечатку в файле x.py.",
            description="sonnet: fix typo",
        )
    )
    assert exit_code == 0

    exit_code2, message2 = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный. Пожалуйста, исправь опечатку в файле x.py.",
            description="sonnet: fix typo",
        )
    )
    assert exit_code2 == 0


def test_pravj_word_boundary_still_matches_standalone_word():
    # "Правь" как отдельное слово-императив (после пробела/начала
    # строки) -- ДОЛЖЕН по-прежнему триггерить write-признак; \b не
    # выключил проверку целиком, только убрал ложные подстроки.
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный. Правь файл x.py по спеке.",
            description="sonnet: fix",
        )
    )
    assert exit_code == 2
    assert "манифеста" in message


def test_dod_marker_case_insensitive():
    exit_code, _ = dispatch_gate.decide(
        _builder_payload("правка. dod: тест зелёный.", description="sonnet: x")
    )
    assert exit_code == 0


# ---------------------------------------------------------------------
# Критик t-336 (fit_with_fixes), F1: та же подстрочная слабость -- на
# этот раз в DOD_MARKERS_RE проверки 1 (симметрично дыре t-332/OWNS_WORD_RE
# в проверке 2). \bDoD\b и \bwitness\b -- границы слова.
# ---------------------------------------------------------------------


def test_f_dod_marker_only_as_filename_substring_now_blocks_closed_hole():
    # ЗАКРЫТАЯ ДЫРА (эмпирика критика t-336): промпт БЕЗ настоящего DoD-
    # маркера, называющий tools/dod_gate.py и tools/dod_track.py в
    # корзине "дано" -- ДО фикса голый r"DoD" (IGNORECASE) матчил
    # подстроку "dod" внутри "dod_gate.py"/"dod_track.jsonl" -> проверка 1
    # ложно пропускала (exit_code был 0). ПОСЛЕ фикса (\bDoD\b) -- границы
    # нет ("_" словесный символ), реального DoD-маркера тоже нет -> БЛОК.
    prompt = (
        "Дано: tools/dod_gate.py, tools/dod_track.py, tools/dod_track.jsonl. "
        "Прочитай оба и сравни поведение."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: read")
    )
    assert exit_code == 2
    assert "без DoD" in message


def test_g_dod_word_boundary_recognizes_colon_and_hyphen_forms():
    # "DoD:" (двоеточие -- не-словесный символ, граница есть) и
    # "DoD-маркер" (дефис -- не-словесный символ, граница есть) --
    # ОБЕ формы по-прежнему признаются DoD-маркером после \b-фикса.
    exit_code1, _ = dispatch_gate.decide(
        _builder_payload("DoD: тест зелёный.", description="sonnet: fix")
    )
    assert exit_code1 == 0

    exit_code2, _ = dispatch_gate.decide(
        _builder_payload("Приложи DoD-маркер к диспатчу.", description="sonnet: fix")
    )
    assert exit_code2 == 0


def test_h_witness_word_boundary_does_not_match_test_witness_echo_filename():
    # "test_witness_echo.py" -- "_" сразу после "witness", границы нет,
    # НЕ признаётся DoD-маркером; настоящего DoD-слова в промпте тоже
    # нет -> БЛОК. Позитивный контроль -- отдельное слово "witness" по-
    # прежнему матчит (test_builder_with_witness_passes_check1 выше).
    prompt = "Дано: tools/test_witness_echo.py. Прочитай и опиши поведение."
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: read")
    )
    assert exit_code == 2
    assert "без DoD" in message


# ---------------------------------------------------------------------
# Проверка 2: манифест на пишущем builder-диспатче.
# ---------------------------------------------------------------------


def test_builder_readonly_no_write_indicators_skips_check2():
    # DoD есть, признаков записи нет -- манифест не требуется.
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "Прочитай файл x.py и скажи, что там. DoD: явный ответ да/нет.",
            description="sonnet: read",
        )
    )
    assert exit_code == 0


def test_builder_write_indicator_without_manifest_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный. Правь файл x.py по спеке.", description="sonnet: fix"
        )
    )
    assert exit_code == 2
    assert "манифеста" in message
    assert "D-0073" in message


def test_builder_write_indicator_with_full_manifest_passes():
    prompt = (
        "DoD: тест зелёный, witness приложен. Создай файл x.py. "
        "МАНИФЕСТ: дано — репо целиком; owns — tools/x.py."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 0


def test_builder_write_indicator_with_only_owns_blocks():
    # "owns" сам по себе -- write-признак И один из двух манифест-
    # маркеров, но "дано"/given отсутствует -- манифест НЕПОЛОН.
    prompt = "DoD: witness есть. owns: tools/x.py. Измени файл x.py."
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 2
    assert "манифеста" in message


def test_builder_write_indicator_with_only_given_blocks():
    prompt = "DoD: witness есть. Given: репо целиком. Создай файл x.py."
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 2
    assert "манифеста" in message


def test_builder_dano_and_given_english_variant_recognized():
    prompt = (
        "DoD: witness есть. Given: репо целиком. owns: tools/x.py. Создай файл x.py."
    )
    exit_code, _ = dispatch_gate.decide(_builder_payload(prompt, description="sonnet: write x"))
    assert exit_code == 0


# ---------------------------------------------------------------------
# Батч 07-28 п.(б): дыра t-332 в проверке 2 -- owns-маркер манифеста
# считался присутствующим по голому MANIFEST_OWNS_RE (подстрока без
# границы слова), теперь -- ТОЛЬКО по OWNS_WORD_RE (граница слова).
# ---------------------------------------------------------------------


def test_a_writing_dispatch_with_real_given_and_owns_manifest_passes():
    # (а) регресс: реальный "дано" + "owns (ABSOLUTE write paths): путь".
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/x.py\n"
        "Правь файл x.py по спеке."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 0, message


def test_b_owns_only_as_filename_substring_in_given_now_blocks_closed_hole():
    # (б) ЗАКРЫТАЯ ДЫРА (доклад t-332, эмпирически подтверждено): "owns"
    # встречается ТОЛЬКО подстрокой внутри имени файла "owns_gate.py" на
    # Given-строке -- НЕ настоящая owns-декларация. ДО этой правки голый
    # MANIFEST_OWNS_RE матчил эту подстроку -> has_manifest ложно True ->
    # exit_code БЫЛ 0 (пишущий диспатч без реального манифеста молча
    # проходил гейт, D-0073 нарушалось). ПОСЛЕ правки (OWNS_WORD_RE,
    # граница слова) -- "owns_gate.py" не матчится, реального
    # owns-манифеста нет -> БЛОК.
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
        "Дано: tools/owns_gate.py — образец экстракции.\n"
        "Правь файл x.py по спеке."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 2
    assert "манифеста" in message
    assert "D-0073" in message


def test_c_readonly_dispatch_mentioning_owns_gate_filename_in_given_not_blocked():
    # (в) обратная грань класса (проверено эмпирически, факт кода -- НЕ
    # по гипотезе спеки): read-only builder-промпт БЕЗ write-слов,
    # упоминающий owns_gate.py в корзине "дано" -- НЕ классифицируется
    # пишущим. ОБНОВЛЕНО F-59 подкласс 2 (2026-08-10): owns УДАЛЁН из
    # WRITE_INDICATORS_RE целиком (см. докстринг dispatch_gate.py,
    # "F-59 ПОДКЛАСС 2") -- "owns_gate.py" её тем более не триггерит
    # (регекс больше не несёт owns-альтернативу вовсе, не только по
    # границе слова, как было с retry t-152), проверка 2 пропускается
    # целиком.
    prompt = (
        "Прочитай tools/owns_gate.py и tools/dispatch_gate.py, опиши логику "
        "extract_owns_paths. DoD: явный ответ да/нет."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: read")
    )
    assert exit_code == 0, message


def test_d_markdown_bold_owns_marker_recognized_as_manifest():
    # (г) markdown-форма "**owns**: путь" -- граница слова на звёздах:
    # `\b` матчит между "*" (не-словесный символ) и "o".
    prompt = (
        "DoD: witness приложен. **Дано**: репо целиком. "
        "**owns**: D:/repo/tools/x.py. Создай файл x.py."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 0, message


def test_e_owns_word_boundary_regex_direct():
    # (д) прямая проверка регекса: "owns_gate" (словесный символ "_"
    # сразу после "owns") НЕ матчится, "owns:" -- матчится.
    assert dispatch_gate.OWNS_WORD_RE.search("owns_gate.py") is None
    assert dispatch_gate.OWNS_WORD_RE.search("owns:") is not None
    assert dispatch_gate.OWNS_WORD_RE.search("**owns**:") is not None


# ---------------------------------------------------------------------
# F-59 подкласс 2 (2026-08-10, T1): owns УДАЛЁН из WRITE_INDICATORS_RE
# целиком -- owns остаётся манифест-маркером (OWNS_WORD_RE, тест выше),
# но больше НЕ write-признак сам по себе. См. докстринг модуля,
# "F-59 ПОДКЛАСС 2".
# ---------------------------------------------------------------------


def test_f59_owns_no_longer_in_write_indicators_re_direct():
    # Прямая проверка регекса (симметрично test_e выше, но для
    # WRITE_INDICATORS_RE): "owns" НИ В КАКОЙ форме больше не совпадает
    # с write-индикатором -- ни голым словом, ни с двоеточием, ни
    # markdown-жирным.
    assert dispatch_gate.WRITE_INDICATORS_RE.search("owns") is None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("owns:") is None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("**owns**:") is None
    # Позитивный контроль (правило 6 гигиены -- негатив без контроля не
    # доказателен): остальные альтернативы по-прежнему совпадают.
    assert dispatch_gate.WRITE_INDICATORS_RE.search("правь файл x.py") is not None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("создай файл x.py") is not None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("запиши результат") is not None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("измени файл x.py") is not None


def test_f59_pin_a_readonly_recon_discussing_owns_as_topic_not_blocked():
    # Пин (а), реконструкция живого образца сессии F-59: read-only
    # builder-разведка, ОБСУЖДАЮЩАЯ owns КАК ТЕМУ (точку правки
    # подкласса owns №2 в WRITE_INDICATORS_RE), без единого пути
    # записи и без write-глагола -- ДО фикса owns-подстрока/слово
    # триггерила write-признак и требовала манифест ложно; ПОСЛЕ --
    # молчит (check2 не включается вовсе, манифест read-only не нужен,
    # правило 11 CLAUDE.md кита).
    prompt = (
        "Найди точку правки подкласса owns №2 в WRITE_INDICATORS_RE и "
        "опиши, где она живёт и как влияет на owns_gate.py. "
        "DoD: явный ответ да/нет по расположению."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: recon")
    )
    assert exit_code == 0, message


def test_f59_pin_b_critic_review_quoting_owns_norm_text_not_blocked():
    # Пин (б), реконструкция живого образца сессии F-59: critic-ревью,
    # ЦИТИРУЮЩЕЕ норму правила 11 CLAUDE.md кита дословно ("owns
    # (ABSOLUTE write paths): <path>") как иллюстрацию требования, БЕЗ
    # реального write-глагола в теле ревью-промпта -- subagent_type
    # != "builder", поэтому проверки 1/2 не применяются НИ В КАКОМ
    # случае (пункт 4 спеки хука), но подтверждаем эмпирически, что
    # даже гипотетически (если бы применялись) owns-цитата одна не
    # триггерит write-признак после фикса.
    prompt = (
        "Ревью диффа: спека требует owns (ABSOLUTE write paths): <path> "
        "по правилу 11 CLAUDE.md кита -- проверь, что диспатч несёт этот "
        "маркер дословно."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "critic",
            "prompt": prompt,
            "description": "opus: review",
        },
    }
    exit_code, message = dispatch_gate.decide(payload)
    assert exit_code == 0, message
    # Позитивный контроль: даже если бы subagent_type был "builder" (не
    # критик), тот же промпт не даёт write-признака (owns-цитата без
    # write-глагола) -- DoD-маркер отсутствует в этом тексте, добавляем
    # его отдельно, чтобы изолировать именно проверку 2.
    exit_code2, message2 = dispatch_gate.decide(
        _builder_payload(prompt + " DoD: явный ответ.", description="sonnet: review")
    )
    assert exit_code2 == 0, message2


def test_f59_owns_declaration_relative_path_only_still_no_manifest_required():
    # ПЕРЕСМОТРЕНО t-384 (прежнее имя/докстринг заявляли "owns без
    # глагола больше НЕ пишущий" как НАМЕРЕННОЕ общее следствие -- это
    # было СНЯТО критиком как эмпирически ложное, см. докстринг модуля
    # "T-384 ИСПРАВЛЕНИЕ": канонические owns-манифесты БЕЗ глагола
    # ОБЯЗАНЫ распознаваться пишущими -- см. test_f59_t384_owns_
    # absolute_path_without_verb_requires_manifest_again ниже). ЭТОТ
    # конкретный промпт остаётся exit 0 по ДРУГОЙ причине: "tools/x.py"
    # -- ОТНОСИТЕЛЬНЫЙ путь (нет буквы диска/ведущего слэша/глоба),
    # owns_declaration_has_path_token() его не признаёт path-подобным
    # (R11 CLAUDE.md кита требует АБСОЛЮТНЫЕ owns-пути) -- совпадение
    # формы теста, не общее правило "owns без глагола не пишущий".
    prompt = "DoD: witness есть. owns: tools/x.py."
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 0, message


def test_f59_t384_owns_absolute_path_without_verb_requires_manifest_again():
    # t-384 ГЛАВНЫЙ ПИН (критик, живой корпус): канонический owns-
    # манифест с АБСОЛЮТНЫМ путём и БЕЗ единого write-глагола -- ИМЕННО
    # класс, который критик замерил как 78 из 87 живых манифестов --
    # ОБЯЗАН СНОВА распознаваться проверкой 2 как пишущий и требовать
    # given.
    prompt = "DoD: witness есть. owns (ABSOLUTE write paths): D:/repo/tools/x.py."
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 2, message
    assert "манифеста" in message


def test_f59_t384_owns_absolute_path_with_given_no_verb_passes():
    # Позитивный контроль в паре: тот же owns+путь, given ЕСТЬ -- манифест
    # полный, exit 0 (без единого write-глагола в тексте вовсе).
    prompt = (
        "DoD: witness есть.\n"
        "Дано: репо целиком.\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/x.py."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 0, message


def test_f59_t384_historical_class_b6_escalation_guard_e1_blocked_again():
    # ГОЛОВНОЙ ПИН критика (t-384, реконструкция описанного примера):
    # "sonnet: B6 эскалационный страж E1" -- манифест owns+путь, БЕЗ
    # given, БЕЗ глагола -- ДО t-384 (после T1, ДО этой правки) давал
    # ложный exit 0 (потерянный блок, один из 14 исторических); ПОСЛЕ
    # t-384 -- снова exit 2, "манифеста" in message.
    prompt = (
        "DoD: критерии приёмки -- тест зелёный, witness приложен.\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/escalation_guard.py\n"
        "Реализуй эскалационный страж E1 по спеке."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: B6 escalation guard E1")
    )
    assert exit_code == 2, message
    assert "манифеста" in message

    # Позитивный контроль -- тот же манифест С given проходит.
    prompt_with_given = (
        "DoD: критерии приёмки -- тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/escalation_guard.py\n"
        "Реализуй эскалационный страж E1 по спеке."
    )
    exit_code2, message2 = dispatch_gate.decide(
        _builder_payload(prompt_with_given, description="sonnet: B6 escalation guard E1")
    )
    assert exit_code2 == 0, message2


def test_manifest_given_word_boundary_prodano_false_positive_fixed():
    # ОСМОТР MANIFEST_GIVEN_RE (п.2 спеки батча): "продано" содержит
    # подстроку "дано" БЕЗ границы слова -- ДО правки голый r"дано|given"
    # матчил её как ложный given-маркер, хотя ни "Дано:", ни "Given:" в
    # промпте не было. С границей слова (`\bдано\b|\bgiven\b`) "продано"
    # больше НЕ матчится -> owns-манифест признаётся НЕПОЛНЫМ (нет
    # настоящего given) -> БЛОК, а не ложный пропуск.
    assert dispatch_gate.MANIFEST_GIVEN_RE.search("Всё продано на складе.") is None
    assert dispatch_gate.MANIFEST_GIVEN_RE.search("Дано: репо целиком.") is not None
    assert dispatch_gate.MANIFEST_GIVEN_RE.search("Given: репо целиком.") is not None

    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Всё продано на складе.\n"
        "owns: tools/x.py\n"
        "Правь файл x.py по спеке."
    )
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 2
    assert "манифеста" in message


# ---------------------------------------------------------------------
# Проверка 3: лейбл description начинается с модели воркера.
# ---------------------------------------------------------------------


def test_missing_description_skips_check3():
    # DoD есть, признаков записи нет -- description вообще не передан.
    exit_code, message = dispatch_gate.decide(
        _builder_payload("Прочитай файл. DoD: явный ответ.")
    )
    assert exit_code == 0
    assert message == ""


def test_description_without_model_prefix_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload("Прочитай файл. DoD: явный ответ.", description="fix the bug")
    )
    assert exit_code == 2
    assert "модели воркера" in message
    assert "правило 7" in message


def test_description_with_model_prefix_variants_pass():
    for prefix in ["sonnet: ", "sonnet-", "sonnet ", "haiku: ", "opus: ", "fable: ", "claude: "]:
        exit_code, message = dispatch_gate.decide(
            _builder_payload(
                "Прочитай файл. DoD: явный ответ.", description=f"{prefix}делает работу"
            )
        )
        assert exit_code == 0, f"prefix {prefix!r} should pass, got {message!r}"


def test_description_model_prefix_case_insensitive():
    exit_code, _ = dispatch_gate.decide(
        _builder_payload("Прочитай файл. DoD: явный ответ.", description="Sonnet: делает работу")
    )
    assert exit_code == 0


def test_description_check_applies_to_critic():
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "critic", "prompt": "Ревью диффа.", "description": "review diff"},
    }
    exit_code, message = dispatch_gate.decide(payload)
    assert exit_code == 2
    assert "модели воркера" in message


def test_description_check_applies_to_scout():
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "scout", "prompt": "Найди файл.", "description": "find file"},
    }
    exit_code, message = dispatch_gate.decide(payload)
    assert exit_code == 2
    assert "модели воркера" in message


def test_description_check_passes_for_critic_with_model_label():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "critic",
            "prompt": "Ревью диффа.",
            "description": "opus: review diff",
        },
    }
    exit_code, message = dispatch_gate.decide(payload)
    assert exit_code == 0


# ---------------------------------------------------------------------
# Пункт 4: critic/scout -- проверки 1 и 2 НЕ применяются.
# ---------------------------------------------------------------------


def test_critic_without_dod_markers_not_blocked_by_check1():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "critic",
            "prompt": "Ревью диффа, без единого DoD-слова тут.",
            "description": "opus: review",
        },
    }
    exit_code, message = dispatch_gate.decide(payload)
    assert exit_code == 0


def test_scout_write_indicator_without_manifest_not_blocked_by_check2():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "scout",
            "prompt": "Правь файл и создай файл заметок (это НЕ builder, проверка 2 не применяется).",
            "description": "haiku: scout",
        },
    }
    exit_code, message = dispatch_gate.decide(payload)
    assert exit_code == 0


# ---------------------------------------------------------------------
# Приоритет 1 -> 2 -> 3 при нескольких одновременных нарушениях.
# ---------------------------------------------------------------------


def test_priority_dod_wins_over_label():
    # Нет DoD И плохой лейбл одновременно -- сообщение про DoD (check 1).
    exit_code, message = dispatch_gate.decide(
        _builder_payload("Правь файл x.py.", description="fix it now")
    )
    assert exit_code == 2
    assert "без DoD" in message


def test_priority_manifest_wins_over_label():
    prompt = "DoD: witness есть. Правь файл x.py."
    exit_code, message = dispatch_gate.decide(_builder_payload(prompt, description="fix it now"))
    assert exit_code == 2
    assert "манифеста" in message


# ---------------------------------------------------------------------
# echo-JSON смок подпроцессом.
# ---------------------------------------------------------------------


def test_echo_json_blocks_builder_without_dod():
    result = _run_hook(_builder_payload("Просто поправь.", description="sonnet: fix"))
    assert result.returncode == 2
    assert "без DoD" in result.stderr


def test_echo_json_passes_builder_with_dod():
    result = _run_hook(
        _builder_payload("Почини. DoD: тест зелёный.", description="sonnet: fix")
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_echo_json_blocks_missing_manifest():
    result = _run_hook(
        _builder_payload("DoD: тест зелёный. Правь файл x.py.", description="sonnet: fix")
    )
    assert result.returncode == 2
    assert "манифеста" in result.stderr


def test_echo_json_blocks_bad_label():
    result = _run_hook(
        _builder_payload("Прочитай файл. DoD: ответ.", description="fix the bug")
    )
    assert result.returncode == 2
    assert "модели воркера" in result.stderr


def test_echo_json_malformed_json_fails_open():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{not valid json",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stderr == ""


# ---------------------------------------------------------------------
# t-159 (очередь v5 п.3): кодировка stdin -- кириллические маркеры
# («Дано:», «критерии приёмки») обязаны распознаваться ДВУМЯ формами
# передачи -- ASCII-safe \uXXXX-эскейпы (json.dumps default,
# ensure_ascii=True) И сырые UTF-8 байты (ensure_ascii=False, без
# text=True/encoding на subprocess -- ровно то, как харнесс реально
# кормит stdin дочернего процесса). До фикса (sys.stdin.read() без
# явного UTF-8) форма (2) давала mojibake и ложный блок манифеста
# (cp1251 -- платформенная кодировка этой машины) -- см. докстринг
# dispatch_gate.py за эмпирику воспроизведения.
# ---------------------------------------------------------------------

_CYRILLIC_MANIFEST_PAYLOAD = {
    "tool_name": "Task",
    "tool_input": {
        "subagent_type": "builder",
        "prompt": (
            "DoD: критерии приёмки — тест зелёный, witness приложен. "
            "Дано: репо целиком. owns: tools/x.py. Правь файл x.py по спеке."
        ),
        "description": "sonnet: fix",
    },
}


def test_cyrillic_markers_recognized_via_ascii_safe_json_escapes():
    # ensure_ascii=True (json.dumps default) -- \uXXXX-эскейпы, форма,
    # которая "случайно работала" бы и ДО фикса (чистый ASCII на
    # проводе, платформенная кодировка stdin не участвует).
    raw = json.dumps(_CYRILLIC_MANIFEST_PAYLOAD, ensure_ascii=True).encode("ascii")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


def test_cyrillic_markers_recognized_via_raw_utf8_bytes():
    # ensure_ascii=False + сырые UTF-8-байты БЕЗ text=True/encoding на
    # subprocess -- эта форма ловит регресс: ДО фикса давала
    # exit_code=2 (mojibake на маркерах "Дано:"/"owns" под cp1251).
    raw = json.dumps(_CYRILLIC_MANIFEST_PAYLOAD, ensure_ascii=False).encode("utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------
# ЧАСТЬ A (t-343): WARN-слой "given-пути существуют" -- given_path_warn.
# repo_root -- реальный корень этого репо (родитель tools/), см.
# докстринг dispatch_gate.py "ЧАСТЬ A" за обоснование "известный
# корень" = payload["cwd"].
# ---------------------------------------------------------------------

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)


def _task_payload(prompt: str, cwd: str = None) -> dict:
    tool_input = {"subagent_type": "builder", "prompt": prompt}
    payload = {"tool_name": "Task", "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def test_given_path_warn_existing_relative_path_no_warn():
    # tools/dispatch_gate.py -- этот самый файл, точно существует.
    warn = dispatch_gate.given_path_warn(
        _task_payload("Дано: tools/dispatch_gate.py. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert warn == ""


def test_given_path_warn_existing_absolute_path_no_warn():
    abs_path = str(Path(_REPO_ROOT) / "tools" / "dispatch_gate.py")
    warn = dispatch_gate.given_path_warn(
        _task_payload(f"Дано: {abs_path}. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert warn == ""


def test_given_path_warn_missing_relative_path_warns_with_name():
    warn = dispatch_gate.given_path_warn(
        _task_payload("Дано: tools/фейк.py. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк.py" in warn
    assert "D-0096" in warn


def test_given_path_warn_missing_absolute_path_under_own_root_warns():
    # СОБСТВЕННОЕ РЕШЕНИЕ билдера (см. докстринг dispatch_gate.py,
    # "ИЗВЕСТНЫЙ КОРЕНЬ И ЧУЖИЕ ДЕРЕВЬЯ"): абсолютные пути ПОД cwd
    # ПРОВЕРЯЮТСЯ -- иначе абсолютные owns-манифесты этого же кита
    # никогда бы не ловились.
    missing_abs = str(Path(_REPO_ROOT) / "tools" / "дефект_нет_такого_файла.py")
    warn = dispatch_gate.given_path_warn(
        _task_payload(f"Дано: {missing_abs}. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert "GIVEN-PATH WARN" in warn
    assert missing_abs in warn


# --- V-2 (2026-08-25, docs/tasks/2026-08-25_kopilka-wave-spec.md,
# находка №4 t-599): "logs" добавлен в _GIVEN_REPO_REL_PREFIX --
# logs/routing-log.jsonl (самый цитируемый носитель фактов) теперь
# ПРОВЕРЯЕТСЯ given-слоем на существование, как и tools/gateway/etc. ---

def test_given_path_warn_existing_logs_path_no_warn():
    # logs/routing-log.jsonl -- живой журнал маршрутизации, реально
    # существует в этом репо.
    warn = dispatch_gate.given_path_warn(
        _task_payload("Дано: logs/routing-log.jsonl. Прочитай его хвост.", cwd=_REPO_ROOT)
    )
    assert warn == ""


def test_given_path_warn_missing_logs_path_warns_with_name():
    warn = dispatch_gate.given_path_warn(
        _task_payload("Дано: logs/несуществующий-журнал.jsonl. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert "GIVEN-PATH WARN" in warn
    assert "logs/несуществующий-журнал.jsonl" in warn
    assert "D-0096" in warn


def test_given_path_warn_placeholders_and_globs_no_warn():
    prompt = (
        "Дано: tools/<имя>.py, tools/*.py, gateway/{name}.py, docs/$VAR.md. "
        "Это примеры плейсхолдеров, не реальные пути."
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert warn == ""


def test_given_path_warn_foreign_tree_dog_no_warn():
    # "чужое дерево" -- D:\Dog\нет.py лежит ВНЕ payload["cwd"] (этого
    # репо) -- не проверяется вовсе, ни warn.
    warn = dispatch_gate.given_path_warn(
        _task_payload(r"Дано: D:\Dog\нет.py. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert warn == ""


def test_given_path_warn_threshold_boundary_10_vs_11():
    # Граница 10/11 (правило 6а): 10 отсутствующих -- полная форма
    # (список всех имён, БЕЗ префикса "N путей не существует"); 11 --
    # сводка ("N путей не существует, первые 3: ...").
    names_10 = [f"tools/fake{i}.py" for i in range(1, 11)]
    prompt_10 = "Дано: " + ", ".join(names_10) + ". Прочитай все."
    warn_10 = dispatch_gate.given_path_warn(_task_payload(prompt_10, cwd=_REPO_ROOT))
    assert "путей не существует" not in warn_10
    for name in names_10:
        assert name in warn_10

    names_11 = [f"tools/fake{i}.py" for i in range(1, 12)]
    prompt_11 = "Дано: " + ", ".join(names_11) + ". Прочитай все."
    warn_11 = dispatch_gate.given_path_warn(_task_payload(prompt_11, cwd=_REPO_ROOT))
    assert "11 путей не существует, первые 3:" in warn_11
    assert "tools/fake1.py" in warn_11
    assert "tools/fake2.py" in warn_11
    assert "tools/fake3.py" in warn_11
    # Полный список НЕ печатается в сводке -- 11-й элемент отсутствует
    # дословно (только "первые 3" перечислены).
    assert "tools/fake11.py" not in warn_11


# --- F2 (критик): {0,300}-граница тела пути вместо жадной `*` --------
# (защита от квадратичного бэктрекинга на патологическом промпте).

def test_extract_given_candidates_body_exactly_300_chars_extracted():
    body = "a" * 300
    prompt = f"Given: D:\\{body}.py for reference."
    candidates = dispatch_gate.extract_given_candidates(prompt)
    toks = [c[0] for c in candidates]
    assert f"D:\\{body}.py" in toks


def test_extract_given_candidates_body_301_chars_not_extracted():
    # 301 -- усечение, задокументированное поведение (докстринг
    # GIVEN_ABS_WIN_PATH_RE/GIVEN_REPO_REL_PATH_RE): warn по такому
    # пути не обещан, регекс просто не находит совпадение целиком (все
    # 301 символа -- "a", точка расширения появляется только ПОСЛЕ
    # 301-го символа, {0,300} не может дотянуться до неё).
    body = "a" * 301
    prompt = f"Given: D:\\{body}.py for reference."
    candidates = dispatch_gate.extract_given_candidates(prompt)
    toks = [c[0] for c in candidates]
    assert f"D:\\{body}.py" not in toks
    assert candidates == []


def test_extract_given_candidates_pathological_input_no_catastrophic_blowup():
    # Форма критика: "C:/"*20000 + "a"*20000 -- без точки-расширения
    # вовсе (обрыв замера критика: 89.5с на 240КБ ДО фикса -- катастрофа,
    # которую ловит этот сторож).
    #
    # F-60 (класс B): сторож катастрофы, не SLO задержки. Здоровое время
    # ~0.07с (замер этого прогона, --durations, t-453); катастрофа --
    # 89.5с на 240 КБ до фикса (см. выше). СУЖЕНИЕ ПОКРЫТИЯ (было ->
    # стало): раньше тест утверждал "укладывается в 5 секунд"; теперь --
    # "предмет не деградировал на порядок".
    pathological = "C:/" * 20000 + "a" * 20000
    start = time.monotonic()
    candidates = dispatch_gate.extract_given_candidates(pathological)
    elapsed = time.monotonic() - start
    assert elapsed < WALLCLOCK_CATASTROPHE_CEILING, (
        f"took {elapsed:.2f}s -- сторож стенных часов: проверь загрузку "
        "машины прежде, чем считать это дефектом (F-60)"
    )
    assert candidates == []


def test_extract_given_candidates_1000_real_paths_previous_behavior():
    names = [f"tools/fake{i}.py" for i in range(1000)]
    prompt = "Given: " + ", ".join(names) + ". Read them all."
    start = time.monotonic()
    candidates = dispatch_gate.extract_given_candidates(prompt)
    elapsed = time.monotonic() - start
    # F-60 (класс B): сторож катастрофы, не SLO задержки. Здоровое время
    # <0.005с (замер этого прогона, --durations, t-453); катастрофа --
    # 89.5с на 240 КБ до фикса (см. test_extract_given_candidates_
    # pathological_input_no_catastrophic_blowup выше -- тот же регресс,
    # другой вход). СУЖЕНИЕ ПОКРЫТИЯ (было -> стало): раньше тест
    # утверждал "укладывается в 5 секунд"; теперь -- "предмет не
    # деградировал на порядок".
    assert elapsed < WALLCLOCK_CATASTROPHE_CEILING, (
        f"took {elapsed:.2f}s -- сторож стенных часов: проверь загрузку "
        "машины прежде, чем считать это дефектом (F-60)"
    )
    toks = [c[0] for c in candidates]
    assert toks == names


def test_given_path_warn_non_task_agent_tool_no_warn():
    warn = dispatch_gate.given_path_warn(
        {"tool_name": "Bash", "tool_input": {"prompt": "tools/фейк.py"}}
    )
    assert warn == ""


def test_given_path_warn_missing_cwd_falls_back_without_crashing():
    # payload без "cwd" -- фоллбек на os.getcwd() (см. докстринг), не
    # должен падать; результат не проверяем содержательно (зависит от
    # реального os.getcwd() на машине прогона), только отсутствие
    # исключения.
    warn = dispatch_gate.given_path_warn(_task_payload("Дано: tools/фейк.py."))
    assert isinstance(warn, str)


# ---------------------------------------------------------------------
# ЧАСТЬ A: интеграция в main() -- exit_code decide() НЕ меняется ни в
# одной ветке (к1 DoD), WARN печатается ТОЛЬКО в additionalContext на
# stdout при exit 0, и НЕ печатается вовсе, если гейт уже блокирует
# (спека п.3).
# ---------------------------------------------------------------------


def test_echo_json_given_path_warn_printed_as_additional_context_on_pass():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": (
                "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
                "Дано: tools/фейк.py.\n"
                "Прочитай его."
            ),
            "description": "sonnet: read",
        },
        "cwd": _REPO_ROOT,
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    stdout_text = result.stdout.decode("utf-8", errors="replace")
    out = json.loads(stdout_text)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "GIVEN-PATH WARN" in ctx
    assert "tools/фейк.py" in ctx


def test_echo_json_given_path_warn_not_printed_when_gate_blocks():
    # Гейт блокирует по check1 (нет DoD) -- WARN-слой не обязан
    # печататься (спека п.3, "не усложняй"); stdout остаётся пустым.
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": "Дано: tools/фейк.py. Просто поправь.",
            "description": "sonnet: fix",
        },
        "cwd": _REPO_ROOT,
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 2
    assert result.stdout == b""


def test_echo_json_no_given_path_warn_when_all_paths_exist():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": (
                "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
                "Дано: tools/dispatch_gate.py.\n"
                "Прочитай его."
            ),
            "description": "sonnet: read",
        },
        "cwd": _REPO_ROOT,
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout == b""


# ---------------------------------------------------------------------
# ЧАСТЬ B (П3, attempt 2 -- пересдача): WARN-слой "тип агента != заявленный
# ярус" -- role_type_warn(). Носитель резолюции -- .claude/agents/*.md
# (НЕ delegation.config.yaml, см. докстринг dispatch_gate.py "ЧАСТЬ B",
# "НОСИТЕЛЬ РЕЗОЛЮЦИИ" -- находка F1 attempt 1). Реальные фронтматтеры
# этого репо на момент правки: scout.md -> model: haiku, builder.md ->
# model: sonnet, critic.md -> model: opus, designer.md -> model: opus,
# judge.md -> model: sonnet -- позволяет тестировать C4'/C5'/C10 БЕЗ
# инъекции, используя реальный каталог AGENTS_DIR.
# ---------------------------------------------------------------------


def _agent_payload(subagent_type=None, description=None, prompt="noop", cwd=None):
    tool_input = {"prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    if description is not None:
        tool_input["description"] = description
    payload = {"tool_name": "Task", "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def _scout_families():
    """(живое_семейство, заведомо_чужое_семейство) привязки scout.

    Тесты role-type-warn выводят match/mismatch-лейблы из ЖИВОГО
    роль-файла тем же резолвером, что и гейт, а не прибивают имя
    модели: класс «имя модели как критерий» (реестр режимов отказа
    карты) — прежние haiku-пины этих тестов сломались на перепривязке
    scout D-0102 (2026-08-16) ровно этим классом, при полностью
    исправном гейте. Предмет тестов — ЛОГИКА срабатывания
    (mismatch -> WARN, match -> тишина), не конкретная привязка."""
    known, model = dispatch_gate._find_agent_role_model("scout")
    assert known and model, "scout.md обязан существовать и нести model: (иначе C4-тесты беспредметны)"
    fam = dispatch_gate._model_family(model)
    assert fam, f"model {model!r} роль-файла scout не резолвится в семейство"
    return fam, ("haiku" if fam != "haiku" else "sonnet")


# C4': известный тип (роль-файл есть), семейства расходятся -> WARN,
# называющий заявленный ярус, тип и модель роль-файла.


def test_role_type_warn_c4_known_role_family_mismatch_warns():
    # Лейбл заявляет семейство, заведомо ЧУЖОЕ живой привязке scout.md
    # (binding-agnostic, см. _scout_families) -- расхождение.
    live, foreign = _scout_families()
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description=f"{foreign}: делает разведку")
    )
    assert "ROLE-TYPE WARN" in warn
    assert foreign in warn
    assert "scout" in warn
    assert live in warn


def test_role_type_warn_c4_known_role_family_match_silent():
    # Позитивный контроль (симметрично mismatch выше): тот же тип, лейбл
    # совпадает с ЖИВОЙ моделью роль-файла -> "".
    live, _foreign = _scout_families()
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description=f"{live}: делает разведку")
    )
    assert warn == ""


def test_role_type_warn_c4_builder_opus_label_mismatch_warns():
    # builder.md несёт model: sonnet; лейбл заявляет "opus:" -- расхождение.
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="builder", description="opus: правь файл")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "opus" in warn
    assert "builder" in warn
    assert "sonnet" in warn


# C5': роль-файла для типа нет (класс general-purpose, а также ЛЮБОЙ
# другой встроенный/несуществующий тип) -> WARN, текст -- утверждение, не
# обвинение (ярлык "класс general-purpose" из текста убран).


def test_role_type_warn_c5_unknown_role_general_purpose_warns():
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="opus: ревью диффа")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "general-purpose" in warn
    assert "нет роль-файла" in warn
    assert "класс general-purpose" not in warn  # ярлык убран (спека пересдачи)


def test_role_type_warn_c5_unknown_role_arbitrary_string_warns():
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="totally-unknown-role", description="fable: что-то")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "totally-unknown-role" in warn
    assert "нет роль-файла" in warn


# --- C10: пин находки F1 (attempt 1) -- пара негатив + позитивный контроль
# в одном тесте, чтобы тишина не оказалась тишиной сломанного слоя.


def test_c10_judge_sonnet_label_silent_general_purpose_same_label_warns():
    # НЕГАТИВ (пин F1): subagent_type='judge' с лейблом 'sonnet:' -- ровно
    # находка критика attempt 1 -- .claude/agents/judge.md существует и
    # несёт model: sonnet -> совпадение -> МОЛЧИТ.
    warn_judge = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="judge", description="sonnet: приёмка диспатча")
    )
    assert warn_judge == ""

    # ПОЗИТИВНЫЙ КОНТРОЛЬ (тот же лейбл, тип БЕЗ роль-файла) -- слой
    # действительно работает, тишина выше -- не тишина сломанного кода.
    warn_unknown = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="sonnet: приёмка диспатча")
    )
    assert "ROLE-TYPE WARN" in warn_unknown
    assert "нет роль-файла" in warn_unknown


# --- C11: регистр/пробелы имени типа -- сопоставляется регистронезависимо
# и с обрезкой пробелов.


def test_c11_subagent_type_case_and_whitespace_variants_silent():
    for variant in ("Builder", "BUILDER", "builder ", " Builder", "BuIlDeR"):
        warn = dispatch_gate.role_type_warn(
            _agent_payload(subagent_type=variant, description="sonnet: правь файл")
        )
        assert warn == "", f"variant {variant!r} should be silent, got {warn!r}"


def test_c11_subagent_type_case_mismatch_still_warns_on_real_mismatch():
    # Регресс-страховка на пару с C11 выше: регистр НЕ маскирует реальное
    # расхождение семейств -- "Scout" (в другом регистре) с лейблом
    # чужого семейства по-прежнему WARN (binding-agnostic).
    _live, foreign = _scout_families()
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="Scout", description=f"{foreign}: делает разведку")
    )
    assert "ROLE-TYPE WARN" in warn


# ---------------------------------------------------------------------
# N3 (attempt 3, критик живым прогоном на 15 формах): кавычки вокруг
# name:/model: снимаются -- ДО фикса кавычённый name: делал роль-файл
# ЛОЖНО НЕВИДИМЫМ (WARN "нет роль-файла" для реально загружаемой роли --
# ложь, не тишина; см. также отдельную before/after-пробу вне pytest,
# приложенную в отчёте дословно).
# ---------------------------------------------------------------------


def test_n3_strip_quotes_double_quotes():
    assert dispatch_gate._strip_quotes('"scout"') == "scout"


def test_n3_strip_quotes_single_quotes():
    assert dispatch_gate._strip_quotes("'sonnet'") == "sonnet"


def test_n3_strip_quotes_unquoted_unchanged():
    assert dispatch_gate._strip_quotes("scout") == "scout"


def test_n3_strip_quotes_mismatched_quotes_unchanged():
    # Разные кавычки на границах -- НЕ пара, не снимается.
    assert dispatch_gate._strip_quotes("'scout\"") == "'scout\""


def test_n3_strip_quotes_quote_inside_value_not_stripped():
    # Негативный контроль (спека прямо требует): кавычка ВНУТРИ значения,
    # не на ОБЕИХ границах разом -- не пара обрамляющих, не снимается.
    assert dispatch_gate._strip_quotes('sco"ut') == 'sco"ut'
    assert dispatch_gate._strip_quotes('scout"') == 'scout"'
    assert dispatch_gate._strip_quotes('"scout') == '"scout'


def test_n3_strip_quotes_too_short_unchanged():
    # Граница: одиночный символ-кавычка -- len==1, первый и последний
    # символ ФИЗИЧЕСКИ один и тот же индекс, не пара -- не снимается.
    assert dispatch_gate._strip_quotes('"') == '"'
    assert dispatch_gate._strip_quotes("") == ""


def test_n3_quoted_name_field_now_matches_and_reveals_real_mismatch(tmp_path, monkeypatch):
    # ТОЧНЫЙ репро критика: роль-файл с произвольным именем файла, name:
    # "scout" В КАВЫЧКАХ, model: "haiku" (тоже в кавычках -- критик:
    # "у model: это уцелело случайно"). subagent_type=scout, лейбл
    # "sonnet:" -- ДО фикса: WARN "нет роль-файла" (ложь, файл грузится).
    # ПОСЛЕ фикса: роль найдена по name:, модель haiku != заявленный
    # sonnet -> WARN MISMATCH (верный вердикт).
    (tmp_path / "randomname.md").write_text(
        '---\nname: "scout"\nmodel: "haiku"\n---\n\n# scout (quoted)\n', encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="sonnet: делает разведку")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "нет роль-файла" not in warn  # НЕ ложный UNKNOWN
    assert "haiku" in warn  # верный MISMATCH, модель роли названа


def test_n3_quoted_model_single_quotes_family_still_resolved(tmp_path, monkeypatch):
    (tmp_path / "custom.md").write_text(
        "---\nname: custom\nmodel: 'opus'\n---\n\n# custom\n", encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn_match = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="custom", description="opus: ревью")
    )
    assert warn_match == ""
    warn_mismatch = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="custom", description="sonnet: ревью")
    )
    assert "ROLE-TYPE WARN" in warn_mismatch
    assert "opus" in warn_mismatch


# ---------------------------------------------------------------------
# N4 (attempt 3, критик): приоритет совпадения по ИМЕНИ ФАЙЛА над
# совпадением по фронтматтерному полю name: при конфликте двух файлов.
# ---------------------------------------------------------------------


def test_n4_filename_match_takes_priority_over_name_field_conflict(tmp_path, monkeypatch):
    # Два файла претендуют на тип "scout": scout.md (имя файла совпадает,
    # но name: внутри -- ДРУГОЕ значение) и other.md (name: поле -- "scout",
    # но имя файла другое). Приоритет -- у scout.md (model: sonnet).
    (tmp_path / "scout.md").write_text(
        "---\nname: not-scout\nmodel: sonnet\n---\n\n# scout by filename\n", encoding="utf-8"
    )
    (tmp_path / "other.md").write_text(
        "---\nname: scout\nmodel: haiku\n---\n\n# scout by name field\n", encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    # Если бы резолюция взяла other.md (model: haiku), лейбл "sonnet:" дал
    # бы MISMATCH. Резолюция берёт scout.md (model: sonnet) -> тишина.
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="sonnet: делает разведку")
    )
    assert warn == ""

    # Позитивный контроль резолюции в файл scout.md, не other.md: лейбл
    # "haiku:" (совпал бы с other.md) ДОЛЖЕН дать MISMATCH, не тишину.
    warn_control = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="haiku: делает разведку")
    )
    assert "ROLE-TYPE WARN" in warn_control
    assert "sonnet" in warn_control


# ---------------------------------------------------------------------
# N6 (attempt 3, критик живым хуком): встроенные типы харнесса без
# проектного роль-файла законно получают WARN "нет роль-файла" -- не
# дефект слоя.
# ---------------------------------------------------------------------


def test_n6_builtin_harness_type_without_role_file_warns_legitimately():
    for builtin_type in ("Explore", "statusline-setup"):
        warn = dispatch_gate.role_type_warn(
            _agent_payload(subagent_type=builtin_type, description="sonnet: сделай что-то")
        )
        assert "ROLE-TYPE WARN" in warn
        assert "нет роль-файла" in warn


# Ограничение (переписано по факту фронтматтеров, докстринг "ЧАСТЬ B"):
# слой сверяет ЯРУС, не ФУНКЦИЮ -- критic.md/designer.md ОБА opus,
# builder.md/judge.md ОБА sonnet -- пары неразличимы между собой.


def test_role_type_warn_documented_limitation_critic_designer_opus_indistinguishable():
    warn_critic = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="critic", description="opus: ревью диффа")
    )
    warn_designer = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="designer", description="opus: драфт спеки")
    )
    assert warn_critic == ""
    assert warn_designer == ""


def test_role_type_warn_documented_limitation_builder_judge_sonnet_indistinguishable():
    warn_builder = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="builder", description="sonnet: правь файл")
    )
    warn_judge = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="judge", description="sonnet: приёмка диспатча")
    )
    assert warn_builder == ""
    assert warn_judge == ""


# --- Таблица пустых/отсутствующих входов (спека, дословно) -------------


def test_role_type_warn_non_task_agent_tool_silent():
    warn = dispatch_gate.role_type_warn({"tool_name": "Bash", "tool_input": {}})
    assert warn == ""


def test_role_type_warn_claude_prefix_label_silent():
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="claude: делает разведку")
    )
    assert warn == ""


def test_role_type_warn_missing_description_silent():
    warn = dispatch_gate.role_type_warn(_agent_payload(subagent_type="scout"))
    assert warn == ""


def test_role_type_warn_empty_description_silent():
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="")
    )
    assert warn == ""


def test_role_type_warn_description_not_string_silent():
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "scout", "prompt": "x", "description": 12345},
    }
    warn = dispatch_gate.role_type_warn(payload)
    assert warn == ""


def test_role_type_warn_description_without_model_prefix_silent():
    # Ни один из других WARN-случаев не триггерится -- лейбл вообще не
    # совпадает с LABEL_MODEL_PREFIX_RE (check3 блокировала бы это на
    # уровне decide(), но role_type_warn() сам по себе тоже молчит).
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="fix it now")
    )
    assert warn == ""


def test_role_type_warn_subagent_type_missing_silent():
    warn = dispatch_gate.role_type_warn(_agent_payload(description="opus: x"))
    assert warn == ""


def test_role_type_warn_subagent_type_none_silent():
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": None, "prompt": "x", "description": "opus: x"},
    }
    warn = dispatch_gate.role_type_warn(payload)
    assert warn == ""


def test_role_type_warn_subagent_type_empty_string_silent():
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="", description="opus: x")
    )
    assert warn == ""


def test_role_type_warn_subagent_type_whitespace_only_silent():
    # Обрезка пробелов (C11) не должна превращать "только пробелы" в
    # непустую строку -- край того же класса, что пустая строка выше.
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="   ", description="opus: x")
    )
    assert warn == ""


def test_role_type_warn_subagent_type_number_silent():
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": 42, "prompt": "x", "description": "opus: x"},
    }
    warn = dispatch_gate.role_type_warn(payload)
    assert warn == ""


def test_role_type_warn_subagent_type_dict_silent():
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": {"a": 1}, "prompt": "x", "description": "opus: x"},
    }
    warn = dispatch_gate.role_type_warn(payload)
    assert warn == ""


# --- Адверсариальная батарея: форма payload/tool_input целиком ---------


def test_role_type_warn_payload_not_dict_silent():
    assert dispatch_gate.role_type_warn(None) == ""
    assert dispatch_gate.role_type_warn("not a dict") == ""
    assert dispatch_gate.role_type_warn([1, 2, 3]) == ""


def test_role_type_warn_tool_name_missing_silent():
    warn = dispatch_gate.role_type_warn({"tool_input": {"subagent_type": "scout"}})
    assert warn == ""


def test_role_type_warn_tool_input_not_dict_silent():
    warn = dispatch_gate.role_type_warn({"tool_name": "Task", "tool_input": "nope"})
    assert warn == ""


def test_role_type_warn_tool_input_missing_silent():
    warn = dispatch_gate.role_type_warn({"tool_name": "Task"})
    assert warn == ""


def test_role_type_warn_huge_description_does_not_hang():
    # Регресс F2 (квадратичный разбор): role_type_warn() вообще не читает
    # tool_input["prompt"] -- проверяем, что 100КБ description и 240КБ
    # prompt тоже не вызывают зависания (LABEL_MODEL_PREFIX_RE заякорен
    # ^ -- анализирует только начало строки; AGENTS_DIR -- всего 5 файлов).
    _live, _foreign = _scout_families()
    huge_description = f"{_foreign}: " + ("x" * 100_000)
    huge_prompt = "y" * 240_000
    start = time.monotonic()
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description=huge_description, prompt=huge_prompt)
    )
    elapsed = time.monotonic() - start
    # F-60 (класс B): сторож катастрофы, не SLO задержки. Здоровое время
    # <0.005с (замер этого прогона, --durations, t-453); катастрофа --
    # 89.5с на 240 КБ до фикса (тот же регресс F2, см. test_extract_
    # given_candidates_pathological_input_no_catastrophic_blowup выше).
    # СУЖЕНИЕ ПОКРЫТИЯ (было -> стало): раньше тест утверждал
    # "укладывается в 5 секунд"; теперь -- "предмет не деградировал на
    # порядок".
    assert elapsed < WALLCLOCK_CATASTROPHE_CEILING, (
        f"took {elapsed:.2f}s -- сторож стенных часов: проверь загрузку "
        "машины прежде, чем считать это дефектом (F-60)"
    )
    assert "ROLE-TYPE WARN" in warn  # чужое семейство != живой привязки scout -- реальный mismatch


# --- Известный тип, роль-файл без model: во фронтматтере -> молчит по ней


def test_role_type_warn_known_role_without_model_in_frontmatter_silent(tmp_path, monkeypatch):
    (tmp_path / "custom.md").write_text(
        "---\nname: custom\ntools: Read\n---\n\n# custom\n", encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="custom", description="opus: делает что-то")
    )
    assert warn == ""


def test_role_type_warn_known_role_model_family_unrecognized_silent(tmp_path, monkeypatch):
    (tmp_path / "custom.md").write_text(
        "---\nname: custom\nmodel: llama-3.3-70b-versatile\n---\n\n# custom\n", encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="custom", description="opus: делает что-то")
    )
    assert warn == ""


def test_role_type_warn_matches_by_frontmatter_name_field_not_filename(tmp_path, monkeypatch):
    # Имя файла ("xyz.md") НЕ совпадает с subagent_type -- совпадение
    # только по фронтматтерному полю name: (С4'/C5' п.а/б спеки).
    (tmp_path / "xyz.md").write_text(
        "---\nname: mytype\nmodel: opus\n---\n\n# mytype\n", encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="mytype", description="sonnet: делает что-то")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "opus" in warn


def test_role_type_warn_malformed_frontmatter_no_closing_fence_silent(tmp_path, monkeypatch):
    # Совпадение по ИМЕНИ ФАЙЛА ("broken.md" -> "broken") есть -- тип
    # известен; фронтматтер без закрывающего "---" не заякорен -> модель
    # не резолвится -> молчит (не крашится, не WARN unknown).
    (tmp_path / "broken.md").write_text(
        "---\nname: broken\nmodel: opus\nTELo без закрывающего fence.\n", encoding="utf-8"
    )
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="broken", description="sonnet: делает что-то")
    )
    assert warn == ""


def test_role_type_warn_agents_dir_missing_entirely_silent(tmp_path, monkeypatch):
    # Свежий клон/кит -- каталог .claude/agents/ отсутствует вовсе.
    missing_dir = tmp_path / "does_not_exist"
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", missing_dir)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="opus: x")
    )
    assert warn == ""


def test_role_type_warn_agents_dir_exists_but_empty_warns_unknown(tmp_path, monkeypatch):
    # Отличается от теста выше: каталог ЕСТЬ, но пуст -- НЕ тот же случай,
    # что "каталог отсутствует целиком" (таблица спеки различает их) --
    # ни один тип не резолвится -> WARN unknown, как обычная не-роль.
    monkeypatch.setattr(dispatch_gate, "AGENTS_DIR", tmp_path)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="builder", description="opus: x")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "нет роль-файла" in warn


# --- C7: fail-open на любое исключение внутри слоя ----------------------


def test_role_type_warn_c7_unexpected_exception_inside_layer_fails_open(monkeypatch):
    def _boom(subagent_type_norm):
        raise RuntimeError("boom")

    monkeypatch.setattr(dispatch_gate, "_find_agent_role_model", _boom)
    warn = dispatch_gate.role_type_warn(
        _agent_payload(subagent_type="scout", description="sonnet: делает разведку")
    )
    assert warn == ""


def test_role_type_warn_c7_agents_dir_present_positive_control():
    # Позитивный контроль в паре с тестами выше -- реальный AGENTS_DIR
    # существует в этом тестовом окружении (репо не свежий клон).
    assert dispatch_gate.AGENTS_DIR.is_dir()


# ---------------------------------------------------------------------
# Инварианты 1/2/3/4 (докстринг "ЧАСТЬ B") на уровне main()/subprocess --
# WARN не подменяет блок, exit-2-ветки недостижимы для нового кода,
# stdout остаётся ОДНИМ JSON-объектом.
# ---------------------------------------------------------------------


def test_i1_role_type_warn_not_computed_when_gate_blocks_check1():
    # Инвариант 1 -- пин-тест спеки: builder-промпт без DoD + лейбл с
    # моделью + subagent_type=general-purpose (что дало бы WARN C5', если
    # бы вычислялось) -- гейт блокирует ПО ПРОВЕРКЕ 1 раньше, stdout пуст.
    payload = _builder_payload("Просто поправь опечатку.", description="opus: fix")
    payload["tool_input"]["subagent_type"] = "builder"
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 2
    assert b"\xd0\xb1\xd0\xb5\xd0\xb7 DoD" in result.stderr or "без DoD" in result.stderr.decode(
        "utf-8", errors="replace"
    )
    assert result.stdout == b""


def test_i2_role_type_warn_never_sets_exit_2_or_permission_decision():
    # C6: mismatch-случай (WARN точно сработает) -- exit_code остаётся 0,
    # JSON не содержит "permissionDecision".
    _live, _foreign = _scout_families()
    payload = _agent_payload(subagent_type="scout", description=f"{_foreign}: делает разведку")
    payload["tool_input"]["prompt"] = "DoD: тест зелёный."  # subagent_type != builder, не влияет
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    out = json.loads(result.stdout.decode("utf-8"))
    assert "permissionDecision" not in json.dumps(out)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "ROLE-TYPE WARN" in ctx


def test_i4_both_warn_layers_fire_single_json_object_given_path_first():
    # Оба слоя срабатывают одновременно: given-path (несуществующий путь
    # в "дано") И role-type (лейбл чужого семейства против живой привязки
    # scout, binding-agnostic).
    # Результат -- ОДИН JSON-объект, given-path сообщение ПЕРЕД role-type.
    _live, _foreign = _scout_families()
    payload = _agent_payload(
        subagent_type="scout",
        description=f"{_foreign}: разведка",
        prompt="Дано: tools/фейк_не_существует.py. Найди упоминания.",
        cwd=_REPO_ROOT,
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    stdout_lines = [ln for ln in result.stdout.decode("utf-8").splitlines() if ln.strip()]
    assert len(stdout_lines) == 1, "stdout must carry exactly one JSON object"
    out = json.loads(stdout_lines[0])
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "GIVEN-PATH WARN" in ctx
    assert "ROLE-TYPE WARN" in ctx
    assert ctx.index("GIVEN-PATH WARN") < ctx.index("ROLE-TYPE WARN")


def test_role_type_warn_silent_on_existing_dispatch_gate_own_test_suite_labels():
    # Регресс-страховка: все существующие echo-тесты этого файла используют
    # description="sonnet: ..." с subagent_type="builder" -- builder.md
    # тоже несёт model: sonnet, слой ЧАСТИ B молчит -- ЧАСТЬ A не получает
    # попутчика в существующих сценариях.
    warn = dispatch_gate.role_type_warn(
        _builder_payload("Почини. DoD: тест зелёный.", description="sonnet: fix")
    )
    assert warn == ""


# ---------------------------------------------------------------------
# t-384 (2026-08-10, критик, живой корпус 454 диспатчей): дискриминатор
# "owns-декларация с path-подобным токеном" -- is_path_like_token() и
# owns_declaration_has_path_token(). См. докстринг модуля,
# "T-384 ИСПРАВЛЕНИЕ" / "ОБЩИЙ ПРЕДИКАТ".
# ---------------------------------------------------------------------


def test_t384_is_path_like_token_direct():
    assert dispatch_gate.is_path_like_token("D:/repo/tools/a.py") is True
    assert dispatch_gate.is_path_like_token("D:\\repo\\tools\\a.py") is True
    assert dispatch_gate.is_path_like_token("/repo/tools/a.py") is True
    assert dispatch_gate.is_path_like_token("tools/*.py") is True
    # F6: голая "*" без слэша (markdown-decoration) -- НЕ путь.
    assert dispatch_gate.is_path_like_token("**Внимание**:") is False
    assert dispatch_gate.is_path_like_token("обратная сторона.**") is False
    # Относительный путь без диска/слэша -- не путь (R11: ABSOLUTE).
    assert dispatch_gate.is_path_like_token("tools/x.py") is False
    assert dispatch_gate.is_path_like_token("") is False
    assert dispatch_gate.is_path_like_token(None) is False


def test_root_only_absolute_token_is_not_a_path():
    # Дефект (найден и исправлен этой правкой): корень БЕЗ сегмента
    # пути ("/", "D:\\") ложно засчитывался путём -- normalize_path("/")
    # самопересекается с любым другим "/", normalize_path("D:\\")=="d:"
    # пересекает весь диск D. AK1/edge-batter: голый/вырожденный корень
    # -- False.
    for tok in ["/", "//", "///", "/ ", "D:\\", "D:/", "\\", "", "   ", "."]:
        assert dispatch_gate.is_path_like_token(tok) is False, tok
    # relative / bare-star -- контроль регресса (AK3), должны остаться
    # False и после этой правки (не тронуты фиксом).
    assert dispatch_gate.is_path_like_token("src/foo.py") is False
    assert dispatch_gate.is_path_like_token("*.py") is False


def test_root_with_segment_absolute_token_is_a_path():
    # AK2: реальный путь с >=1 символом сегмента СРАЗУ после корневого
    # слэша остаётся True -- позиционный инвариант (регексы всё ещё
    # проверяются первыми, до глоб-ветки) сохранён.
    #
    # УЗЕЛ D ремедиации калибровки #8 (Р7, "Фантомный токен", форма 1,
    # 2026-08-20): POSIX-ветка сузилась -- см.
    # test_p7_posix_bare_single_segment_no_extension_now_false ниже за
    # ЯВНОЕ сужение прежнего покрытия ("/a" и другие голые 1-сегментные
    # POSIX-токены БЕЗ расширения были True здесь ДО этой правки, теперь
    # False). Windows-ветка (_PATH_TOKEN_WIN_ABS_RE) этой формой НЕ
    # затронута -- решение называет буквально "POSIX-ветка".
    for tok in [
        "/etc/x",  # POSIX, 2 сегмента -- проходит по форме 1 без расширения
        "D:\\x",
        "D:/x",
        "D:\\AI CRM\\x\\AGENTS.md",
        "logs/*.jsonl",
        "/*.py",  # POSIX, 1 сегмент, но несёт расширение ".py" -- форма 1 пропускает
    ]:
        assert dispatch_gate.is_path_like_token(tok) is True, tok
    # Длинный СЕГМЕНТ (5000 символов) без расширения -- граница длины
    # (правило 6а), но теперь ОДИН POSIX-сегмент без расширения -- см.
    # test_p7_posix_bare_single_segment_no_extension_now_false за перенос
    # ЭТОГО конкретного значения; здесь -- эквивалент С расширением,
    # остающийся True.
    assert dispatch_gate.is_path_like_token("/" + ("a" * 5000) + ".py") is True


def test_doubled_root_with_segment_is_a_path():
    # Уточнение критика t-476: класс -- "корень БЕЗ сегмента", а не
    # "ровно один слэш". Удвоенный корень С сегментом -- это путь
    # (сегмент есть); `/+`/`[\\/]+` их принимает. Прежняя форма
    # `^/[^/\\s]` ошибочно роняла "//foo".
    #
    # УЗЕЛ D (Р7, форма 1): "//foo"/"///a" -- ОДИН сегмент без расширения
    # -- см. test_p7_posix_bare_single_segment_no_extension_now_false за
    # перенос (ДО этой правки были True здесь). "//server/share" -- ДВА
    # сегмента -- остаётся True без изменений.
    for tok in ["//server/share", "D://x"]:
        assert dispatch_gate.is_path_like_token(tok) is True, tok
    # Но голый удвоенный/утроенный корень БЕЗ сегмента остаётся False
    # (граница класса не сдвинута) -- дублирует контроль в
    # test_root_only_absolute_token_is_not_a_path, держится здесь рядом
    # с позитивами как парная граница.
    for tok in ["//", "///", "D://"]:
        assert dispatch_gate.is_path_like_token(tok) is False, tok


# ---------------------------------------------------------------------
# УЗЕЛ D ремедиации калибровки #8 (2026-08-20), Р7 "Фантомный токен",
# форма 1 (решение Lead): POSIX-ветка is_path_like_token сузилась --
# токен обязан НЕ нести пробелов И нести расширение ЛИБО >=2 сегмента
# после корня. Мотив: короткие прозаические обрывки с одним слэшем
# ложно проходили путём (см. Р7 форму 2 отдельно за класс
# "owns/non-goals/handoff" -- ТА форма ловится границей маркер/слэш,
# НЕ этой). Правило 6а: граница тестирована ОБЕИМИ сторонами.
# ---------------------------------------------------------------------


def test_p7_posix_bare_single_segment_no_extension_now_false():
    # СУЖЕНИЕ прежнего покрытия (было True в test_root_with_segment_
    # absolute_token_is_a_path/test_doubled_root_with_segment_is_a_path
    # ДО этой правки, задокументировано явно, не молчаливая правка пина):
    # один POSIX-сегмент БЕЗ расширения -- теперь False.
    for tok in ["/a", "//foo", "///a", "/" + ("a" * 5000)]:
        assert dispatch_gate.is_path_like_token(tok) is False, tok


def test_p7_posix_two_segments_no_extension_still_true():
    # Граница "ЗА" п.6а (парная к предыдущему тесту): >=2 сегмента без
    # расширения -- остаётся True (не тронуто формой 1).
    for tok in ["/etc/x", "/a/b"]:
        assert dispatch_gate.is_path_like_token(tok) is True, tok


def test_p7_posix_single_segment_with_extension_still_true():
    # Граница "ЗА": 1 сегмент, но С расширением -- остаётся True.
    for tok in ["/a.py", "/x.md"]:
        assert dispatch_gate.is_path_like_token(tok) is True, tok


def test_p7_posix_token_with_space_now_false_even_with_extension():
    # Форма 1 требует ОТСУТСТВИЯ пробелов -- даже с расширением/>=2
    # сегментами пробел внутри токена теперь блокирует POSIX-ветку.
    assert dispatch_gate.is_path_like_token("/a b/c.py") is False
    assert dispatch_gate.is_path_like_token("/a b") is False


def test_t384_owns_declaration_has_path_token_canonical_forms():
    assert dispatch_gate.owns_declaration_has_path_token(
        "owns (ABSOLUTE write paths): D:/repo/tools/x.py"
    ) is True
    assert dispatch_gate.owns_declaration_has_path_token(
        "owns (АБСОЛЮТНЫЕ пути записи): D:/repo/tools/x.py"
    ) is True
    assert dispatch_gate.owns_declaration_has_path_token(
        "**owns (ABSOLUTE write paths):**\n- D:/a.py\n- D:/b.py\n"
    ) is True
    assert dispatch_gate.owns_declaration_has_path_token("owns: tools/x.py.") is False
    assert dispatch_gate.owns_declaration_has_path_token("owns:") is False
    assert dispatch_gate.owns_declaration_has_path_token("") is False
    assert dispatch_gate.owns_declaration_has_path_token(None) is False


def test_owns_declaration_has_path_token_agrees_with_owns_gate_extract_on_matrix():
    # T3/t-384 (спека handoff): эталон истинности -- owns_gate.
    # extract_owns_paths(prompt) непустой. Матрица: девять живых
    # образцов сессии (реконструкции, см. отчёт билдера) + канонические
    # манифесты + голое слово в прозе -- ОБЯЗАНЫ давать ОДИНАКОВЫЙ
    # булев вердикт на обоих независимых предикатах.
    matrix = [
        ("canonical_en", "owns (ABSOLUTE write paths): D:/repo/tools/x.py"),
        (
            "canonical_ru",
            "owns (АБСОЛЮТНЫЕ пути записи): D:/repo/tools/x.py",
        ),
        (
            "bold_bullet_continuation",
            "**owns (ABSOLUTE write paths):**\n- D:/a.py\n- D:/b.py\n",
        ),
        (
            "prose_topic_no_path",
            "Найди точку правки подкласса owns №2 в WRITE_INDICATORS_RE.",
        ),
        (
            "prose_then_real_declaration_below",
            "Задача: правка гейта.\n"
            "Не выходи за owns этой задачи.\n"
            "D:/repo/readme.md -- прочитать перед началом\n"
            "\n"
            "owns: D:/repo/real_target.py\n",
        ),
        (
            "prose_mid_sentence_alone",
            "Задача: правка гейта.\n"
            "Не выходи за owns этой задачи.\n"
            "D:/repo/readme.md -- прочитать перед началом\n",
        ),
        (
            "f6_bold_no_slash",
            "owns: обратная сторона.** Пишущий диспатч",
        ),
        (
            "owns_filename_substring_then_real_below",
            "Дано: D:/x/tools/owns_gate.py, D:/x/tools/dispatch_gate.py, D:/x/CLAUDE.md\n"
            "owns (ABSOLUTE write paths): D:/x/tools/owns_gate.py\n",
        ),
        ("relative_path_only", "owns: tools/x.py."),
        ("owns_bare_no_content", "owns:"),
        ("backtick_single_line", "owns: `D:/repo/tools/a.py`"),
    ]
    mismatches = []
    for name, prompt in matrix:
        dg_result = dispatch_gate.owns_declaration_has_path_token(prompt)
        og_result = bool(owns_gate.extract_owns_paths(prompt))
        if dg_result != og_result:
            mismatches.append((name, dg_result, og_result))
    assert mismatches == [], f"path-token predicate disagreement: {mismatches}"


def test_t384_dispatch_gate_check2_recognizes_owns_with_path_without_verb():
    # Критик: 78 из 87 живых манифестов не несут ни одного write-глагола
    # -- write-признак ОБЯЗАН срабатывать через owns+путь напрямую.
    prompt = "DoD: witness есть. owns (ABSOLUTE write paths): D:/repo/tools/x.py."
    exit_code, message = dispatch_gate.decide(
        _builder_payload(prompt, description="sonnet: write x")
    )
    assert exit_code == 2
    assert "манифеста" in message

    prompt_with_given = (
        "DoD: witness есть.\nДано: репо целиком.\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/x.py."
    )
    exit_code2, message2 = dispatch_gate.decide(
        _builder_payload(prompt_with_given, description="sonnet: write x")
    )
    assert exit_code2 == 0, message2


# =======================================================================
# УЗЕЛ D ремедиации калибровки #8 (2026-08-20) -- Р1 (чужие деплои),
# Р2 (owns-секция), Р7 (фантомный токен, обе формы). Красные тесты ДО
# фикса / зелёные ПОСЛЕ, копилка узла D носителя хода.
# =======================================================================


# --- Р1: GIVEN-PATH и чужие деплои = ГРОМКОСТЬ, не резолюция ----------


def test_r1_deploy_marker_by_name_exempts_relative_candidate_from_check():
    # Копилка п.1/5 (t-544/t-551): относительный путь чужого деплоя,
    # упомянутый РЯДОМ с явным маркером деплоя (имя ключа `deploys`
    # конфига, "ao3" из delegation.config.yaml) -- не проверяется вовсе,
    # даже если он не существует в ЭТОМ репо (PROCESS/ -- один из шести
    # репо-относительных префиксов GIVEN_REPO_REL_PATH_RE).
    prompt = (
        "Речь о репо AO3. Дано: PROCESS/некий_чужой_чек.md -- сверь его "
        "форму на том дереве."
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert warn == ""


def test_r1_no_deploy_marker_same_relative_candidate_still_warns():
    # Позитивный контроль той же формы (правило 6 гигиены): БЕЗ маркера
    # деплоя -- тот же путь (не существует в этом репо) продолжает
    # предупреждать, как раньше.
    prompt = "Дано: PROCESS/некий_чужой_чек.md -- сверь его форму."
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "PROCESS/некий_чужой_чек.md" in warn


def test_r1_deploy_marker_by_path_text_also_exempts():
    # "маркер = имя ключа ИЛИ его путь" -- деплой-путь `D:\AO3_tests`,
    # процитированный в тексте, тоже считается явным маркером.
    prompt = (
        r"Смотри дерево D:\AO3_tests и его PROCESS/некий_чужой_чек.md."
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert warn == ""


# --- Р2: GIVEN-PATH и создаваемые пути (owns-секция) -------------------


def test_r2_owns_section_only_path_not_checked_given_basket_stays_warn():
    # DoD п.2 узла D: путь, названный ТОЛЬКО в owns-секции (диспатч его
    # СОЗДАЁТ), не проверяется; протухший путь в корзине "дано" ОБЯЗАН
    # остаться в WARN -- "тише, но не слепее".
    prompt = (
        "Дано: tools/фейк_дано.py -- прочитай перед началом.\n\n"
        "owns:\n"
        "- D:/repo/tools/новый_создаваемый_файл.py\n"
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_дано.py" in warn  # given-корзина -- ПРОТУХШИЙ путь, WARN держится
    assert "новый_создаваемый_файл.py" not in warn  # owns-секция -- диспатч его создаёт


def test_r2_same_path_named_in_given_and_owns_still_checked():
    # Путь, повторённый И в given, И в owns -- given-вхождение "выкупает"
    # его из молчания (позиционный инвариант не расширяет зону молчания
    # шире, чем owns-секция буквально).
    prompt = (
        "Дано: tools/фейк_дважды.py -- прочитай, затем перепиши его.\n\n"
        "owns:\n"
        "- D:/repo/tools/фейк_дважды.py\n"
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_дважды.py" in warn


# --- Р7 форма 1: is_path_like_token POSIX-ветка -- уже пинована выше
# (test_p7_posix_*). Форма 2: marker_immediately_followed_by_slash. ----


def test_r7_form2_marker_immediately_followed_by_slash_direct():
    assert dispatch_gate.marker_immediately_followed_by_slash("/non-goals/handoff") is True
    assert dispatch_gate.marker_immediately_followed_by_slash(": /d/x.py") is False
    assert dispatch_gate.marker_immediately_followed_by_slash(" /d/x.py") is False
    assert dispatch_gate.marker_immediately_followed_by_slash("") is False
    assert dispatch_gate.marker_immediately_followed_by_slash(None) is False


def test_r7_form2_owns_declaration_has_path_token_ignores_canonical_prose():
    # "given/owns/non-goals/handoff" -- каноническое перечисление секций
    # манифеста (правило 11 CLAUDE.md кита) -- owns СРАЗУ за которым "/"
    # без разделителя -- НЕ декларация, is_write НЕ должен ловить это.
    prompt = "Секции манифеста: given/owns/non-goals/handoff -- см. правило 11."
    assert dispatch_gate.owns_declaration_has_path_token(prompt) is False


def test_r7_form2_real_owns_declaration_with_colon_unaffected():
    # Позитивный контроль (правило 6 гигиены): настоящая декларация с
    # разделителем ДО ЭТОГО как была True, так и осталась.
    prompt = "owns: /d/repo/tools/real.py"
    assert dispatch_gate.owns_declaration_has_path_token(prompt) is True


# --- Пин-набор: сохраняемые истинные срабатывания ----------------------


def test_pin_stale_given_path_in_own_root_still_warns_after_node_d():
    # "Протухший путь в корзине «дано» своего корня -> WARN" -- держится
    # после Р1/Р2 (без owns-секции, без маркера деплоя -- ни один фильтр
    # не применяется).
    warn = dispatch_gate.given_path_warn(
        _task_payload("Дано: tools/фейк_совсем.py. Прочитай его.", cwd=_REPO_ROOT)
    )
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_совсем.py" in warn


# =======================================================================
# ВЕРДИКТ КРИТИК-ГЕЙТА t-554 (2026-08-20) -- обязательные фиксы партии
# узлов C+D: D-1 (локальность маркера деплоя), D-2 (markdown-заголовок/
# буллет манифест-секции), D-3 (верхняя граница owns-секции).
# =======================================================================


# --- D-1: маркер деплоя освобождает кандидата ТОЛЬКО в СВОЁМ абзаце ----


def test_d1_marker_in_different_paragraph_from_path_still_warns():
    # Критик t-554: 73% всего снятого шума Р1+Р2 давал именно Р1 в
    # прежней (глобальной) редакции -- маркер деплоя в ОДНОМ абзаце,
    # кандидат в ДРУГОМ (пустая строка между ними) -- освобождение
    # больше НЕ действует, WARN держится.
    prompt = (
        "Речь о репо AO3.\n\n"
        "Дано: PROCESS/некий_чужой_чек.md -- сверь его форму."
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "PROCESS/некий_чужой_чек.md" in warn


def test_d1_token_occurs_twice_one_outside_marker_paragraph_still_warns():
    # "Одно вхождение вне маркерного абзаца -- кандидат ПРОВЕРЯЕТСЯ как
    # свой" -- даже если ДРУГОЕ вхождение того же токена стоит рядом с
    # маркером.
    prompt = (
        "Речь о репо AO3. Дано: PROCESS/некий_чужой_чек.md -- сверь.\n\n"
        "Ещё раз для памяти: PROCESS/некий_чужой_чек.md."
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "PROCESS/некий_чужой_чек.md" in warn


def test_d1_prompt_without_blank_line_marker_still_frees_whole_prompt():
    # КРАЯ (спека узла, ПРИНЯТО сознательно, не дефект): промпт БЕЗ
    # единой пустой строки -- один абзац целиком, п.1 ведёт себя как ДО
    # этой правки (маркер освобождает весь промпт). Закреплено тестом,
    # чтобы следующая правка не сочла это багом.
    prompt = (
        "Речь о репо AO3, без единой пустой строки во всём тексте. "
        "Дано: PROCESS/некий_чужой_чек.md -- сверь его форму на том дереве."
    )
    assert "\n\n" not in prompt
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert warn == ""


# --- D-2: owns-секция markdown-заголовком / буллетом -------------------


def test_d2_owns_section_recognized_as_markdown_header():
    # Боевая форма t-550 (копилка узла D п.3): "## OWNS (...)".
    prompt = (
        "Дано: tools/фейк_дано2_d2.py -- прочитай перед началом.\n\n"
        "## OWNS (§1 спеки, абсолютные пути)\n"
        "- D:/repo/tools/новый_из_заголовка_d2.py\n"
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_дано2_d2.py" in warn  # given -- протухший путь держится
    assert "новый_из_заголовка_d2.py" not in warn  # owns-секция распознана


def test_d2_owns_section_recognized_as_bullet_form():
    prompt = (
        "Дано: tools/фейк_дано3_d2.py -- прочитай перед началом.\n\n"
        "- owns:\n"
        "- D:/repo/tools/новый_из_буллета_d2.py\n"
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_дано3_d2.py" in warn
    assert "новый_из_буллета_d2.py" not in warn  # owns-секция распознана


# --- D-3: верхняя граница owns-секции -----------------------------------


def test_d3_prosaic_owns_line_does_not_silence_paths_below():
    # ДО фикса: "owns не нужен -- read-only" открывала "owns"-секцию,
    # которая держалась ДО КОНЦА промпта -- given-путь НИЖЕ гасился
    # молча. ПОСЛЕ: прозаическая строка продолжения (не буллет/не путь)
    # закрывает секцию СРАЗУ, given-путь снова проверяется.
    prompt = (
        "owns не нужен -- read-only.\n"
        "Прочитай также tools/фейк_после_прозы_d3.py для контекста.\n"
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_после_прозы_d3.py" in warn


def test_d3_genuine_multiline_owns_block_still_silenced():
    # Позитивный контроль (правило 6 гигиены): настоящий многострочный
    # owns-список (буллет + path-подобный первый токен на каждой строке)
    # по-прежнему держит секцию "owns" -- НЕ регрессия D-3.
    prompt = (
        "Дано: tools/фейк_дано4_d3.py -- прочитай перед началом.\n\n"
        "owns:\n"
        "- D:/repo/tools/a_d3.py\n"
        "- D:/repo/tools/b_d3.py\n"
    )
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/фейк_дано4_d3.py" in warn
    assert "a_d3.py" not in warn
    assert "b_d3.py" not in warn


# ---------------------------------------------------------------------
# K2 (docs/tasks/2026-08-25_queue8-mechbatch-spec.md): словарь
# WRITE_INDICATORS_RE расширен -- `\bпосади\b` голой альтернативой,
# «добавь» только СВЯЗАННОЙ формой (≤60 симв. до файлового объекта, без
# перевода строки). «внеси» ИЗНАЧАЛЬНО была голой альтернативой (см.
# ниже test_k2_vnesi_bare_form_no_longer_matches_superseded_by_f2) --
# СУПЕРСЕДЕНО F2 (ФИКС-РАУНД той же спеки): переведена в ту же связанную
# форму, что «добавь» (см. блок F2 ниже за полную батарею). Общий
# потолок трёх слоёв (write_quoted_warn, owns_gate QUOTED_OWNS/
# BLIND_OWNS) и самого is_write -- все они читают ОДИН И ТОТ ЖЕ
# скомпилированный объект, отдельных
# тестов на каждый слой не требуется сверх прямых assert'ов на регекс и
# сквозного decide()/owns_gate прогона ниже.
# ---------------------------------------------------------------------


def test_k2_posadi_bare_alternative_matches():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("посади узел") is not None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("ПОСАДИ узел") is not None


def test_k2_vnesi_bare_form_no_longer_matches_superseded_by_f2():
    # СУПЕРСЕДЕНО F2 (ФИКС-РАУНД, docs/tasks/2026-08-25_queue8-mechbatch-
    # spec.md): "внеси" переведена из голой альтернативы в СВЯЗАННУЮ
    # форму (та же, что "добавь") -- "внеси" БЕЗ файлового объекта в
    # пределах 60 симв. больше НЕ матчит (было наоборот в исходном K2 --
    # см. git-историю этого теста, прежнее имя test_k2_vnesi_bare_
    # alternative_matches). Позитивный контроль формы С объектом --
    # test_f2_vnesi_connected_form_with_object_matches ниже.
    assert dispatch_gate.WRITE_INDICATORS_RE.search("внеси правку") is None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("Внеси правку") is None


def test_k2_dobav_connected_form_matches_with_object_word():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь строку в X.md") is not None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь файл в репо") is not None
    assert dispatch_gate.WRITE_INDICATORS_RE.search("ДОБАВЬ раздел в X.md") is not None


def test_k2_dobav_bare_without_object_word_does_not_match():
    # «добавь в дайджест вывод» -- нет ни одного файлового объекта
    # (файл/строку/строки/запись/блок/секцию/раздел/путь) нигде в
    # тексте -- НЕ матч (иначе ложный БЛОК read-only диспатчей, ось 15).
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь в дайджест вывод") is None


def test_k2_dobav_newline_between_verb_and_object_does_not_match():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь\n…файл") is None


def test_k2_dobav_boundary_60_chars_matches():
    # ГРАНИЦА (правило 6а): РОВНО 60 символов между «добавь» и объектом --
    # матч (включительно).
    text = "добавь" + (" " * 60) + "файл"
    assert dispatch_gate.WRITE_INDICATORS_RE.search(text) is not None


def test_k2_dobav_boundary_61_chars_does_not_match():
    # ГРАНИЦА ЗА пределом: 61 символ между «добавь» и объектом -- НЕ матч.
    text = "добавь" + (" " * 61) + "файл"
    assert dispatch_gate.WRITE_INDICATORS_RE.search(text) is None


def test_k2_decide_posadi_without_manifest_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload("DoD: тест зелёный. Посади узел в X.md.", description="sonnet: fix")
    )
    assert exit_code == 2
    assert "манифеста" in message


def test_k2_decide_posadi_with_manifest_passes():
    prompt = (
        "DoD: тест зелёный, witness приложен. Посади узел в X.md. "
        "Дано: репо целиком. owns: tools/x.py."
    )
    exit_code, message = dispatch_gate.decide(_builder_payload(prompt, description="sonnet: write x"))
    assert exit_code == 0, message


def test_k2_decide_vnesi_without_manifest_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload("DoD: тест зелёный. Внеси правку в файл x.py.", description="sonnet: fix")
    )
    assert exit_code == 2
    assert "манифеста" in message


def test_k2_decide_dobav_connected_without_manifest_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload("DoD: тест зелёный. Добавь строку в X.md.", description="sonnet: fix")
    )
    assert exit_code == 2
    assert "манифеста" in message


def test_k2_decide_dobav_readonly_digest_not_blocked():
    # Позитивный контроль: «добавь в дайджест вывод» -- read-only
    # диспатч (нет файлового объекта рядом с «добавь») -- проверка 2
    # НЕ включается, exit 0.
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: явный ответ да/нет. Прочитай файл и добавь в дайджест вывод.",
            description="sonnet: read",
        )
    )
    assert exit_code == 0, message


def test_k2_owns_gate_blind_owns_warn_uses_extended_dictionary():
    # owns_gate.py импортирует WRITE_INDICATORS_RE (тот же объект) --
    # BLIND_OWNS слой (:1761) обязан видеть новые альтернативы без
    # отдельной правки owns_gate.py (форма-образец --
    # test_decide_blind_owns_warn_when_marker_present_but_no_paths_parsed
    # в test_owns_gate.py, "Правь файлы." заменено на "Посади узел.").
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "owns: непонятно что тут написано без путей.\n"
        "Посади узел."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-k2",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "конфликт владения" in ctx


# ---------------------------------------------------------------------
# K3 (docs/tasks/2026-08-25_queue8-mechbatch-spec.md): пост-фильтр
# _filter_given_candidates режет по бэктику кандидата, тело которого
# несёт буквальный `` ` `` (склейка двух бэктик-путей БЕЗ пробельного
# разделителя между ними -- _GIVEN_PATH_BODY_CHAR исключает пробел, но
# НЕ бэктик). GIVEN_*_RE извлечения (:1220-1233) НЕ тронуты -- прямые
# тесты на них не нужны, регресс проверен полным прогоном файла.
# ---------------------------------------------------------------------


def test_k3_acceptance_key_two_backtick_paths_with_space_two_candidates():
    # Акцентанс-ключ (исторический, спека дословно): «`tools/a.py` и
    # `tools/b.py`» -- ДВА кандидата-пути, не один склеенный. С пробелом
    # между обёртками GIVEN_REPO_REL_PATH_RE УЖЕ останавливается на
    # бэктике (пробел исключён из тела регекса) -- эта форма уже была
    # корректна ДО K3 (эмпирически проверено); тест фиксирует её как
    # регресс-пин, K3 не обязан её чинить, но обязан не сломать.
    prompt = "Дано: `tools/фейк_k3_key_a.py` и `tools/фейк_k3_key_b.py`."
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert missing == ["tools/фейк_k3_key_a.py", "tools/фейк_k3_key_b.py"]


def test_k3_two_backtick_paths_glued_without_whitespace_split_into_two():
    # РЕАЛЬНЫЙ дефект K3: БЕЗ пробела между обёртками ("`a.py`и`b.py`")
    # тело кандидата несёт буквальный бэктик -- ДО фикса ОДИН склеенный
    # мусорный токен "tools/.../a.py`и`tools/.../b.py"; ПОСЛЕ -- оба пути
    # присутствуют как отдельные кандидаты. F3 (ФИКС-РАУНД) добавил
    # fullmatch-фильтр НА разрезанные сегменты -- связка "и" между путями
    # (не путь целиком) больше НЕ входит в missing вовсе (было допущено
    # спекой K3 как временный артефакт, F3 закрыл дыру).
    prompt = "Дано: `tools/фейк_k3_glued_a.py`и`tools/фейк_k3_glued_b.py`."
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert "tools/фейк_k3_glued_a.py" in missing
    assert "tools/фейк_k3_glued_b.py" in missing
    assert not any("`" in tok for tok in missing)  # ни один токен не несёт сырой бэктик
    assert "и" not in missing  # F3: связка-мусор отфильтрована fullmatch'ем
    assert len(missing) == 2  # ровно два пути, ничего лишнего


def test_k3_split_backtick_body_direct_two_segments():
    assert dispatch_gate._split_backtick_body("a`и`b") == ["a", "и", "b"]


def test_k3_split_backtick_body_all_backticks_empty_result():
    # Край: кандидат из одних бэктиков -> ноль сегментов.
    assert dispatch_gate._split_backtick_body("```") == []


def test_k3_split_backtick_body_trailing_single_backtick_trimmed():
    # Край: одиночный бэктик на конце -> хвостовая пустая часть срезается.
    assert dispatch_gate._split_backtick_body("tools/a.py`") == ["tools/a.py"]


def test_k3_candidate_without_backtick_unchanged_regression():
    # Регресс: кандидат без бэктика -- проходит фильтр как прежде
    # (существующие 243 теста не задеты).
    prompt = "Дано: tools/фейк_k3_no_backtick_regress.py. Прочитай его."
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert missing == ["tools/фейк_k3_no_backtick_regress.py"]


def test_k3_split_only_applies_after_exemption_owns_section_still_exempts_glued_token():
    # Позиционный аргумент докстринга: exemption-множества читают ЦЕЛЫЙ
    # (возможно склеенный) кандидат -- если он попадает в owns-секцию
    # (А-К1), исключение срабатывает НА ЦЕЛОМ кандидате, split не
    # реанимирует его в проверку существования (А-К5: split не может
    # ДОБАВИТЬ путь в missing сверх решения exemption).
    prompt = (
        "Дано: репо целиком.\n"
        "owns: `tools/фейк_k3_owns_a.py`и`tools/фейк_k3_owns_b.py`\n"
        "Правь файл x.py по спеке."
    )
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert "tools/фейк_k3_owns_a.py" not in missing
    assert "tools/фейк_k3_owns_b.py" not in missing


# ---------------------------------------------------------------------
# F3 (ФИКС-РАУНД, docs/tasks/2026-08-25_queue8-mechbatch-spec.md):
# сегменты после бэктик-разреза (K3) обязаны пройти fullmatch по
# GIVEN_ABS_WIN_PATH_RE/GIVEN_REPO_REL_PATH_RE -- мусор ("и") не попадает
# ни в варн, ни в порог GIVEN_PATH_WARN_SUMMARY_THRESHOLD (10). Точка
# разреза (после exemption) НЕ сдвинута -- fullmatch добавлен как фильтр
# ПОВЕРХ уже разрезанного результата.
# ---------------------------------------------------------------------


def test_f3_critic_control_two_paths_no_connector_junk():
    # Контроль критика дословно: "Дано: `tools/nofile_a.py`и`tools/
    # nofile_b.py`." -> ровно два пути, без "и".
    prompt = "Дано: `tools/nofile_a.py`и`tools/nofile_b.py`."
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert missing == ["tools/nofile_a.py", "tools/nofile_b.py"]


def test_f3_given_path_warn_text_does_not_mention_connector_junk():
    prompt = "Дано: `tools/nofile_a.py`и`tools/nofile_b.py`."
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN" in warn
    assert "tools/nofile_a.py" in warn
    assert "tools/nofile_b.py" in warn
    # "и" отдельным токеном в тексте WARN не появляется (не входит в
    # список missing вовсе -- значит не может быть напечатан построчно).
    assert "\nи\n" not in warn
    assert not warn.rstrip().endswith("- и") and "- и\n" not in warn


def test_f3_connector_junk_does_not_count_toward_summary_threshold():
    # Порог GIVEN_PATH_WARN_SUMMARY_THRESHOLD = 10: 8 НАСТОЯЩИХ
    # отсутствующих путей + склеенная пара (2 РЕАЛЬНЫХ пути) = РОВНО 10
    # -- ПОД порогом (полная форма WARN, "GIVEN-PATH WARN: в тексте
    # диспатча названы"). ЕСЛИ БЫ связка "и" считалась кандидатом (до
    # F3), итог был бы 11 -- НАД порогом (summary-форма "N путей не
    # существует"). Дискриминирующая проверка формата, не только счёта.
    paths = [f"tools/фейк_f3_thresh_{i}.py" for i in range(8)]
    given_list = ", ".join(paths)
    prompt = (
        f"Дано: {given_list}, `tools/фейк_f3_thresh_glued_a.py`и"
        f"`tools/фейк_f3_thresh_glued_b.py`.\n"
    )
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert "и" not in missing
    assert len(missing) == 10  # 8 + 2 (glued pair split cleanly), не 11
    warn = dispatch_gate.given_path_warn(_task_payload(prompt, cwd=_REPO_ROOT))
    assert "GIVEN-PATH WARN: в тексте диспатча названы" in warn  # полная форма, порог НЕ пробит
    assert "путей не существует" not in warn  # НЕ summary-форма


def test_f3_split_point_after_exemption_unchanged_owns_section_still_exempts():
    # Регресс-пин: F3 не сдвинула точку разреза (после exemption) --
    # тот же тест, что K3 уже проверял, обязан остаться зелёным без
    # изменений после добавления fullmatch-фильтра.
    prompt = (
        "Дано: репо целиком.\n"
        "owns: `tools/фейк_f3_owns_a.py`и`tools/фейк_f3_owns_b.py`\n"
        "Правь файл x.py по спеке."
    )
    missing = dispatch_gate.find_missing_given_paths(prompt, _REPO_ROOT)
    assert "tools/фейк_f3_owns_a.py" not in missing
    assert "tools/фейк_f3_owns_b.py" not in missing


# ---------------------------------------------------------------------
# F2 (ФИКС-РАУНД, docs/tasks/2026-08-25_queue8-mechbatch-spec.md):
# "внеси" -> связанная форма, идентичная "добавь" (объект -- закрытый
# список из восьми слов ИЛИ путь-подобный токен со слэшем); обеим формам
# -- негативная защита от ложного срабатывания на тексте ВОЗВРАТА
# воркера ("в отчёт/дайджест/доклад/ответ" перед объектом). "посади"
# остаётся голой. Пять контрольных фраз критика (негативы) + три
# позитива, дословно.
# ---------------------------------------------------------------------


def test_f2_negative_vnesi_v_otchyot_chislo_no_match():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("внеси в отчёт число зелёных тестов") is None


def test_f2_negative_dobav_v_otchyot_zapis_no_match():
    # "запись" -- одно из восьми слов объекта, но здесь это ЧАСТЬ фразы
    # "в отчёт запись" (цель-возврат), не запись в ФС -- НЕ матч.
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь в отчёт запись о результате") is None


def test_f2_negative_dobav_v_daydzhest_put_no_match():
    # "путь" -- тоже одно из восьми слов, тот же класс ложного матча.
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь в дайджест путь к носителю") is None


def test_f2_negative_dobav_v_daydzhest_vyvod_no_match():
    # Регресс-контроль (без слова объекта вовсе -- уже некликмо было ДО F2).
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь в дайджест вывод прогона") is None


def test_f2_negative_no_verb_at_all_no_match():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("просто почини баг, ничего не пиши") is None


def test_f2_positive_vnesi_pravku_v_real_path_matches():
    # Акцептанс-ключ критика: "внеси правку в tools/x.py" -- ни одного из
    # восьми слов объекта, только реальный путь-подобный токен.
    assert dispatch_gate.WRITE_INDICATORS_RE.search("внеси правку в tools/x.py") is not None


def test_f2_positive_dobav_stroku_v_x_md_matches():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("добавь строку в X.md") is not None


def test_f2_positive_posadi_uzel_bare_still_matches():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("посади узел") is not None


def test_f2_vnesi_connected_form_with_object_matches():
    assert dispatch_gate.WRITE_INDICATORS_RE.search("внеси запись в файл x.py") is not None


def test_f2_boundary_vnesi_60_chars_matches():
    text = "внеси" + (" " * 60) + "файл"
    assert dispatch_gate.WRITE_INDICATORS_RE.search(text) is not None


def test_f2_boundary_vnesi_61_chars_does_not_match():
    text = "внеси" + (" " * 61) + "файл"
    assert dispatch_gate.WRITE_INDICATORS_RE.search(text) is None


def test_f2_decide_negative_control_return_target_phrase_not_blocked():
    # Сквозной decide(): read-only диспатч, обсуждающий СВОЙ БУДУЩИЙ
    # ОТВЕТ координатору ("внеси в отчёт число зелёных тестов") -- НЕ
    # признаётся пишущим, проверка 2 не включается, exit 0.
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "Прогони батарею и внеси в отчёт число зелёных тестов. DoD: явный ответ.",
            description="sonnet: recon",
        )
    )
    assert exit_code == 0, message


def test_f2_decide_positive_vnesi_real_path_without_manifest_blocks():
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный. Внеси правку в tools/x.py.", description="sonnet: fix"
        )
    )
    assert exit_code == 2
    assert "манифеста" in message


# ===========================================================================
# УЗЕЛ FRESHNESS (docs/tasks/2026-08-25_freshness-layer-spec.md, t-599):
# freshness_warn -- класс (в) якорь путь:строка ЗА концом файла (M3),
# класс (а) ссылка "чек NN(х)" на несуществующий подпункт/номер/гомоглиф
# (M1/M2/M4). Battery A1-A17 из спеки помечена инлайн-комментариями.
# ===========================================================================


def _fw(prompt: str, cwd: str = _REPO_ROOT) -> str:
    return dispatch_gate.freshness_warn(_task_payload(prompt, cwd=cwd))


# --- базовые молчания (не Task/Agent, не dict, пустой/нестроковый prompt) --


def test_freshness_non_task_agent_tool_no_warn():
    warn = dispatch_gate.freshness_warn(
        {"tool_name": "Bash", "tool_input": {"prompt": "tools/dispatch_gate.py:999999"}}
    )
    assert warn == ""


def test_freshness_payload_not_dict_no_warn():
    assert dispatch_gate.freshness_warn("not a dict") == ""


def test_freshness_prompt_missing_no_warn():
    warn = dispatch_gate.freshness_warn(
        {"tool_name": "Task", "tool_input": {"subagent_type": "builder"}}
    )
    assert warn == ""


def test_freshness_prompt_empty_string_no_warn():
    assert _fw("") == ""


def test_freshness_prompt_not_string_no_warn():
    # A16: нестроковый prompt.
    warn = dispatch_gate.freshness_warn(
        {"tool_name": "Task", "tool_input": {"subagent_type": "builder", "prompt": None}}
    )
    assert warn == ""


def test_freshness_no_candidates_no_warn():
    assert _fw("Дано: репо целиком. Прочитай файлы внимательно.") == ""


def test_freshness_no_candidates_zero_filesystem_opens(monkeypatch):
    # К5: предфильтр -- ни одного кандидата -> "" ДО файловой системы
    # (тест счётчиком open, как того требует DoD).
    calls = {"n": 0}
    real_open = open

    def counting_open(*args, **kwargs):
        calls["n"] += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)
    warn = _fw("Дано: репо целиком. Ничего похожего на якорь тут нет.")
    assert warn == ""
    assert calls["n"] == 0


# --- К6: региональный сканер недоступен -> слой молчит ЦЕЛИКОМ (в отличие
# от given_path_warn, у freshness_warn НЕТ И-0 bare-фоллбека). ------------


def test_freshness_scan_unavailable_layer_silent_wholly(monkeypatch):
    monkeypatch.setattr(dispatch_gate, "_safe_scan", lambda text: None)
    assert _fw("tools/dispatch_gate.py:999999") == ""
    assert _fw("чек 77(а)") == ""


# ---------------------------------------------------------------------
# Класс (в): якорь путь:строка ЗА концом файла (M3).
# ---------------------------------------------------------------------


def test_freshness_class_v_within_bounds_no_warn():
    assert _fw("Дано: tools/dispatch_gate.py:10.") == ""


def test_freshness_class_v_beyond_eof_warns_m3():
    warn = _fw("Дано: tools/dispatch_gate.py:9999999.")
    assert "FRESHNESS WARN:" in warn
    assert "tools/dispatch_gate.py:9999999" in warn
    assert "D-0096" in warn


def test_freshness_class_v_missing_file_no_warn():
    assert _fw("Дано: tools/фейк_свежесть_нет_такого.py:5.") == ""


def test_freshness_class_v_absolute_within_bounds_no_warn():
    abs_path = str(Path(_REPO_ROOT) / "tools" / "dispatch_gate.py")
    assert _fw(f"Дано: {abs_path}:10.") == ""


def test_freshness_class_v_absolute_beyond_eof_warns():
    abs_path = str(Path(_REPO_ROOT) / "tools" / "dispatch_gate.py")
    warn = _fw(f"Дано: {abs_path}:9999999.")
    assert "FRESHNESS WARN:" in warn
    assert abs_path in warn


def test_freshness_class_v_foreign_tree_not_under_root_no_warn():
    # A14: путь вне репо (_is_under_root) -- не проверяется вовсе.
    assert _fw(r"Дано: D:\Dog\фейк.py:999999.") == ""


def test_freshness_class_v_directory_anchor_no_warn(tmp_path):
    d = tmp_path / "sub.py"
    d.mkdir()
    warn = _fw(f"{d}:1", cwd=str(tmp_path))
    assert warn == ""


def test_freshness_class_v_range_anchor_uses_max_bound():
    # "N-M" -- граница max(N, M): N сам по себе укладывается, но M -- нет.
    warn = _fw("Дано: tools/dispatch_gate.py:5-9999999.")
    assert "FRESHNESS WARN:" in warn
    assert "tools/dispatch_gate.py:5-9999999" in warn


def test_freshness_class_v_range_anchor_within_both_bounds_no_warn():
    assert _fw("Дано: tools/dispatch_gate.py:5-10.") == ""


def test_freshness_class_v_zero_line_never_warns():
    # A13: ":0" -- отброшен (max(0, None)=0, строк < 0 невозможно).
    assert _fw("Дано: tools/dispatch_gate.py:0.") == ""


def test_freshness_class_v_negative_number_not_extracted():
    # A13: ":-5" -- регекс не матчит вовсе (нет минуса в \d{1,7}).
    assert dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:-5") is None
    assert _fw("Дано: tools/dispatch_gate.py:-5.") == ""


def test_freshness_class_v_leading_zeros_parsed_as_int_beyond_eof_warns():
    # A13: ":00012" -- ведущие нули не мешают int().
    assert _fw("Дано: tools/фейк_leading_zero_свежесть.py:00012.") == ""  # файла нет -- молчание
    m = dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:00012")
    assert m.group("n") == "00012"


def test_freshness_class_v_eight_digit_line_number_l5_boundary_not_extracted():
    # L5 граница (правило 6а): 7 цифр -- матчит, 8 -- нет.
    assert dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search(
        "tools/dispatch_gate.py:9999999"
    ) is not None
    assert dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search(
        "tools/dispatch_gate.py:99999999"
    ) is None
    # A13: :99999999 -- восьмизначный, не извлекается -> молчание целиком.
    assert _fw("Дано: tools/dispatch_gate.py:99999999.") == ""


def test_freshness_class_v_double_colon_form_a12():
    # A12: "x.py:12:34" -- якорь ловит только первую пару, хвост игнорируется.
    m = dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:12:34")
    assert m is not None
    assert m.group(0) == "tools/dispatch_gate.py:12"
    assert m.group("m") is None
    assert _fw("Дано: tools/dispatch_gate.py:12:34.") == ""  # 12 < реального счёта строк


def test_freshness_class_v_mixed_cyrillic_path_a5_no_crash():
    # A5: смешанный путь (латиница+кириллица), несуществующий -- молчание,
    # но извлечение НЕ должно падать.
    warn = _fw("Дано: tools/тест_x.py:10.")
    assert warn == ""
    assert dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search("tools/тест_x.py:10") is not None


def test_freshness_class_v_bom_crlf_no_crash_a2():
    prompt = "\ufeffДано: tools/dispatch_gate.py:9999999.\r\nВторая строка.\r\n"
    warn = _fw(prompt)
    assert "FRESHNESS WARN:" in warn


def test_freshness_class_v_null_byte_no_crash_a16():
    warn = _fw("tools/dispatch_gate.py:9999999\x00хвост")
    assert "FRESHNESS WARN:" in warn


def test_freshness_class_v_mojibake_bytes_no_crash_a1():
    warn = _fw("tools/dispatch_gate.py:9999999 \ufffd\ufffd")
    assert "FRESHNESS WARN:" in warn


# --- региональная осведомлённость (А6/А7/А8) ------------------------------


def test_freshness_class_v_fenced_quote_suppresses_warn_a6():
    prompt = "текст\n```\ntools/dispatch_gate.py:9999999\n```\nконец"
    assert _fw(prompt) == ""


def test_freshness_class_v_blockquote_suppresses_warn_a6():
    prompt = "> tools/dispatch_gate.py:9999999\nобычный текст"
    assert _fw(prompt) == ""


def test_freshness_class_v_inline_code_backtick_still_warns_a6():
    prompt = "см. `tools/dispatch_gate.py:9999999` тут"
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_class_v_guillemets_not_a_quote_still_warns_a6():
    prompt = "см. «tools/dispatch_gate.py:9999999» тут"
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_class_v_unterminated_fence_reads_as_prose_a7():
    # A7: незакрытый фенс -- единая полярность, читается ПРОЗОЙ, не цитатой.
    prompt = "```\ntools/dispatch_gate.py:9999999\nконец без закрытия фенса"
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_class_v_quoted_and_prose_occurrence_still_checked_a8():
    prompt = "```\ntools/dispatch_gate.py:9999999\n```\nи ещё раз: tools/dispatch_gate.py:9999999 в прозе"
    assert "FRESHNESS WARN:" in _fw(prompt)


# --- дедуп/сводка/лимиты (К9, L1) -----------------------------------------


def test_freshness_class_v_dedup_five_thousand_repeats_one_mention_a10():
    prompt = " ".join(["tools/dispatch_gate.py:9999999"] * 5000)
    warn = _fw(prompt)
    assert warn.count("tools/dispatch_gate.py:9999999") == 1


def test_freshness_class_v_summary_threshold_boundary_20_vs_21_a11():
    # L1: 20 -- полная форма (каждый M3 отдельно), 21 -- сводка "первые 3".
    files_20 = [f"tools/фейк_thresh_v_{i}.py" for i in range(20)]
    prompt_20 = "\n".join(f"{p}:1" for p in files_20)
    warn_20 = _fw(prompt_20)
    assert warn_20 == ""  # ни один из этих файлов не существует -- 0 hits

    # Реальные hits нужны -- используем ОДИН существующий файл с 20/21
    # разными диапазонами (каждый -- отдельный ключ дедупа по (path, n, m)).
    ranges_20 = [f"tools/dispatch_gate.py:{9000000 + i}" for i in range(20)]
    prompt_v20 = "\n".join(ranges_20)
    warn_v20 = _fw(prompt_v20)
    assert "первые 3" not in warn_v20
    for tok in ranges_20:
        assert tok in warn_v20

    ranges_21 = [f"tools/dispatch_gate.py:{9000000 + i}" for i in range(21)]
    prompt_v21 = "\n".join(ranges_21)
    warn_v21 = _fw(prompt_v21)
    assert "21 якорей" in warn_v21
    assert "первые 3" in warn_v21
    assert ranges_21[0] in warn_v21
    assert ranges_21[20] not in warn_v21


def test_freshness_class_v_25_broken_anchors_summary_a11():
    ranges_25 = [f"tools/dispatch_gate.py:{9100000 + i}" for i in range(25)]
    warn = _fw("\n".join(ranges_25))
    assert "25 якорей" in warn
    assert "первые 3" in warn


# --- L2 (2 МиБ/файл) / L4 (8 файлов/вызов) ---------------------------------


def test_freshness_class_v_file_size_limit_l2_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(dispatch_gate, "_FRESHNESS_MAX_FILE_BYTES", 5)
    f_at = tmp_path / "at.py"
    f_over = tmp_path / "over.py"
    f_at.write_bytes(b"a" * 5)
    f_over.write_bytes(b"a" * 6)
    warn_at = _fw(f"{f_at}:100", cwd=str(tmp_path))
    warn_over = _fw(f"{f_over}:100", cwd=str(tmp_path))
    assert "FRESHNESS WARN:" in warn_at  # РОВНО на лимите -- ещё читается
    assert warn_over == ""  # за лимитом -- молчание


def test_freshness_class_v_files_per_call_limit_l4_boundary(tmp_path):
    files = []
    for i in range(9):
        fp = tmp_path / f"f{i}.py"
        fp.write_text("x\n", encoding="utf-8")
        files.append(fp)
    prompt = " ".join(f"{fp}:100" for fp in files)
    warn = _fw(prompt, cwd=str(tmp_path))
    for fp in files[:8]:
        assert str(fp) in warn
    assert str(files[8]) not in warn  # L4: 9-й файл -- молчание, не упомянут


# --- ВРЕМЕННОЙ КРАЙ / А-К1/А-К2/А-К4 подавление (А15) ----------------------


def test_freshness_class_v_owns_declared_suppresses_warn():
    prompt = (
        "Дано: репо целиком.\n"
        "owns: tools/dispatch_gate.py\n"
        "Правь файл tools/dispatch_gate.py:9999999 по спеке."
    )
    assert _fw(prompt) == ""


def test_freshness_class_v_run_line_suppresses_warn():
    assert _fw("Прогон: python tools/dispatch_gate.py:9999999 -q") == ""


def test_freshness_class_v_non_goals_suppresses_warn():
    assert _fw("non-goals: tools/dispatch_gate.py:9999999\n") == ""


def test_freshness_class_v_control_prose_without_suppression_still_warns():
    warn = _fw("Прочитай tools/dispatch_gate.py:9999999 внимательно.")
    assert "FRESHNESS WARN:" in warn


# --- L3: длина промпта --------------------------------------------------


def test_freshness_l3_boundary_exactly_300000_still_scans():
    anchor = " tools/dispatch_gate.py:9999999 "
    pad = "x" * (300000 - len(anchor))
    warn = _fw(pad + anchor)
    assert "FRESHNESS WARN:" in warn


def test_freshness_l3_boundary_300001_layer_silent_no_disk(monkeypatch):
    calls = {"n": 0}
    real_open = open

    def counting_open(*args, **kwargs):
        calls["n"] += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)
    anchor = " tools/dispatch_gate.py:9999999 "
    pad = "x" * (300001 - len(anchor))
    warn = _fw(pad + anchor)
    assert warn == ""
    assert calls["n"] == 0


# ---------------------------------------------------------------------
# Класс (а): ссылка "чек NN(х)" (M1/M2/M4).
# ---------------------------------------------------------------------


def test_freshness_class_a_existing_subitem_via_o1_no_warn():
    assert _fw("чек 13(б)") == ""


def test_freshness_class_a_check_not_exist_m2():
    warn = _fw("чек 77(а)")
    assert "FRESHNESS WARN:" in warn
    assert "77" in warn
    assert "НОМЕРЕ" in warn


def test_freshness_class_a_subitem_not_exist_m1_lists_existing_letters():
    warn = _fw("чек 13(я)")
    assert "FRESHNESS WARN:" in warn
    assert "13(я)" in warn
    assert "реально есть" in warn
    assert "а" in warn  # известная реальная буква чека 13


def test_freshness_class_a_latin_homoglyph_m4():
    warn = _fw("чек 13(a)")  # латинская 'a', не кириллическая 'а'
    assert "FRESHNESS WARN:" in warn
    assert "латиница" in warn


def test_freshness_class_a_bare_form_without_anchor_word_not_extracted():
    # Ф2а: голая форма "13(а)" без якорного слова -- не извлекается.
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("см. 13(а) для деталей") is None
    assert _fw("см. 13(а) для деталей") == ""


def test_freshness_class_a_via_o2_prose_reference_no_warn():
    # "11(в)" упомянут прозой протокола (не якорем О1) -- ловится О2.
    assert _fw("чек 11(в)") == ""


def test_freshness_class_a_via_o3_region_only_no_warn():
    # "18(г)" -- голая форма "(г)" в РЕГИОНЕ чека 18, БЕЗ буквального
    # "18(г)" где-либо в тексте (проверено сверкой: только О3 находит).
    assert dispatch_gate._freshness_o2_found(
        dispatch_gate._freshness_load_protocol_text(), "18", "г"
    ) is False
    assert dispatch_gate._freshness_o3_found(
        dispatch_gate._freshness_load_protocol_text(), "18", "г"
    ) is True
    assert _fw("чек 18(г)") == ""


def test_freshness_class_a_nonexistent_letter_in_o3_check_still_m1():
    warn = _fw("чек 18(х)")
    assert "FRESHNESS WARN:" in warn
    assert "18(х)" in warn


@pytest.mark.parametrize(
    "form", ["чек", "чека", "чеку", "чеке", "чеки", "check", "CHK", "ЧЕК", "Check"]
)
def test_freshness_class_a_anchor_word_forms_recognized(form):
    prompt = f"{form} 13(б)"
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search(prompt) is not None


def test_freshness_class_a_l6_boundary_2_digit_matches_3_digit_does_not():
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("чек 99(а)") is not None
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("чек 100(а)") is None


def test_freshness_class_a_nbsp_between_word_and_number_not_extracted_a3():
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("чек\u00a013(а)") is None
    assert _fw("чек\u00a013(а)") == ""


def test_freshness_class_a_zero_width_space_not_extracted_a3():
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("чек\u200b13(а)") is None


def test_freshness_class_a_fenced_quote_suppresses_warn_a6():
    prompt = "```\nчек 77(а)\n```\n"
    assert _fw(prompt) == ""


def test_freshness_class_a_quoted_and_prose_still_checked_a8():
    prompt = "```\nчек 77(а)\n```\nещё раз чек 77(а) в прозе"
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_class_a_dedup_repeated_pair_one_mention():
    warn = _fw(" ".join(["чек 77(а)"] * 50))
    assert warn.count("FRESHNESS WARN:") == 1
    assert "77" in warn


def test_freshness_class_a_summary_threshold_boundary_20_vs_21():
    toks_20 = [f"чек 77({chr(0x430 + i)})" for i in range(20)]  # а..т (кириллица)
    warn_20 = _fw(" ".join(toks_20))
    assert "первые 3" not in warn_20

    toks_21 = [f"чек 77({chr(0x430 + i)})" for i in range(21)]
    warn_21 = _fw(" ".join(toks_21))
    assert "21 ссылок" in warn_21
    assert "первые 3" in warn_21


# --- протокол отсутствует/пуст/без CHK (А17, Ф7а) -------------------------


def test_freshness_class_a_protocol_missing_no_warn(monkeypatch):
    monkeypatch.setattr(
        dispatch_gate, "_FRESHNESS_PROTOCOL_PATH", Path("D:/нет/такого/протокола.md")
    )
    assert _fw("чек 77(а)") == ""


def test_freshness_class_a_protocol_empty_no_warn(monkeypatch):
    monkeypatch.setattr(dispatch_gate, "_freshness_load_protocol_text", lambda: "")
    assert _fw("чек 77(а)") == ""


def test_freshness_class_a_protocol_without_any_chk_no_warn_a17(monkeypatch):
    monkeypatch.setattr(
        dispatch_gate, "_freshness_load_protocol_text", lambda: "текст без единого якоря чек-листа"
    )
    assert _fw("чек 13(б)") == ""


# ---------------------------------------------------------------------
# Позиционный инвариант: decide() не тронута, склейка в main(), хвост.
# ---------------------------------------------------------------------


def test_freshness_decide_unaffected_by_stale_check_reference():
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный. Посади узел, ссылается на чек 77(а).",
            description="sonnet: fix",
        )
    )
    # DoD-маркер есть, манифеста нет -- блокирует ПО ТОЙ ЖЕ причине, что
    # и без FRESHNESS-содержимого; freshness_warn не участвует в decide().
    assert exit_code == 2
    assert "манифеста" in message


def test_echo_json_freshness_warn_printed_as_additional_context_last():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": (
                "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
                "Дано: tools/фейк_freshness_echo.py, tools/dispatch_gate.py:9999999.\n"
                "owns: tools/x.py\n"
                "Прочитай его."
            ),
            "description": "sonnet: read",
        },
        "cwd": _REPO_ROOT,
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    out = json.loads(result.stdout.decode("utf-8", errors="replace"))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "GIVEN-PATH WARN" in ctx
    assert "FRESHNESS WARN" in ctx
    # C6/Ф13а: FRESHNESS -- в САМОМ ХВОСТЕ склейки warn_parts.
    assert ctx.rindex("GIVEN-PATH WARN") < ctx.rindex("FRESHNESS WARN")


def test_freshness_live_probe_positive_negative_pair_ф15a():
    # Ф15а: детектор -- пин-тесты позитив/негатив в каноне (живая проба
    # спеки, координаторский witness item 3): "чек 30(щ)" -- буква,
    # реально НЕ существующая у чека 30 (реальные -- а/б/в/г/д) -> M1;
    # "чек 30(д)" -- РЕАЛЬНЫЙ бэрформ-подпункт (О3, PROCESS/WEEKLY_
    # CALIBRATION_PROTOCOL.md, регион чека 30) -> тишина.
    def probe(prompt):
        payload = {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "builder",
                "prompt": prompt,
                "description": "sonnet: probe",
            },
            "cwd": _REPO_ROOT,
        }
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    base = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
        "Дано: tools/dispatch_gate.py.\n"
        "owns: tools/x.py\n"
        "Сверься с {check} и якорем tools/dispatch_gate.py:{line}."
    )

    pos = probe(base.format(check="чек 30(щ)", line="999999"))
    assert pos.returncode == 0, pos.stderr.decode("utf-8", errors="replace")
    out_pos = json.loads(pos.stdout.decode("utf-8", errors="replace"))
    ctx_pos = out_pos["hookSpecificOutput"]["additionalContext"]
    assert "FRESHNESS WARN" in ctx_pos
    assert "tools/dispatch_gate.py:999999" in ctx_pos
    assert "30(щ)" in ctx_pos

    neg = probe(base.format(check="чек 30(д)", line="100"))
    assert neg.returncode == 0, neg.stderr.decode("utf-8", errors="replace")
    assert neg.stdout.decode("utf-8", errors="replace") == ""


def test_echo_json_no_freshness_warn_when_gate_blocks():
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": "Дано: tools/dispatch_gate.py:9999999. Просто поправь.",
            "description": "sonnet: fix",
        },
        "cwd": _REPO_ROOT,
    }
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 2
    assert result.stdout.decode("utf-8", errors="replace") == ""


# ===========================================================================
# ФИКС-РАУНД FRESHNESS (критик-гейт t-606, 2026-08-25): Б1 (logs/ мёртв),
# Б2 (ложный варн на кит-ссылки), Ф1 (WRITE_RETURN_TARGET_GUARD, живые
# ложные блоки), Ф2 (левая граница слова класса (а)), Ф3 (кэш на вызов),
# Ф5 (порядок М2/М4).
# ===========================================================================


# --- Б1: logs/-якорь -- параметризованный _filter_given_candidates -------


def _b1_tmp_logs_root(tmp_path):
    # Фикс 2026-08-27: три Б1-теста стояли на ЖИВОМ logs/routing-log.jsonl
    # -- растущий носитель пересёк кап L2 (2 МиБ) и слой замолчал по
    # дизайну, красня/вакуумно зеленя тесты (класс "тест на живом
    # растущем носителе"; вскрыто BATCH CANON петли, итерация 1).
    # Синтетика: маленький журнал в tmp-корне, L2 недостижим.
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "routing-log.jsonl").write_text(
        "\n".join('{"ts":"2026-01-01T00:00:00","event":"x"}' for _ in range(20)),
        encoding="utf-8",
    )
    return str(tmp_path)


def test_fixround_b1_logs_prefix_beyond_eof_warns(tmp_path):
    warn = _fw("logs/routing-log.jsonl:9999999", cwd=_b1_tmp_logs_root(tmp_path))
    assert "FRESHNESS WARN:" in warn
    assert "logs/routing-log.jsonl:9999999" in warn


def test_fixround_b1_logs_prefix_within_bounds_silent(tmp_path):
    assert _fw("logs/routing-log.jsonl:10", cwd=_b1_tmp_logs_root(tmp_path)) == ""


def test_fixround_b1_logs_owns_suppression_still_works(tmp_path):
    # logs/ теперь ДОХОДИТ до owns-подавления (не молчит по умолчанию),
    # но owns-декларация всё равно освобождает его -- симметрия с
    # остальными шестью префиксами.
    prompt = (
        "Дано: репо целиком.\n"
        "owns: logs/routing-log.jsonl\n"
        "Правь файл logs/routing-log.jsonl:9999999 по спеке."
    )
    assert _fw(prompt, cwd=_b1_tmp_logs_root(tmp_path)) == ""


def test_fixround_b1_live_journal_over_l2_cap_stays_silent():
    # Пин ПРИЧИНЫ фикса выше: живой журнал ПЕРЕРОС кап L2 -- слой на нём
    # молчит по дизайну (оценка L2 -- dispatch_gate._FRESHNESS_MAX_FILE_BYTES);
    # если журнал когда-то ужмётся ниже капа, этот пин отвалится и Б1-тесты
    # можно вернуть на живой носитель осознанным решением.
    live = os.path.join(_REPO_ROOT, "logs", "routing-log.jsonl")
    assert os.path.getsize(live) > dispatch_gate._FRESHNESS_MAX_FILE_BYTES
    assert _fw("logs/routing-log.jsonl:9999999") == ""


@pytest.mark.parametrize(
    "path", [
        "tools/dispatch_gate.py",
        "gateway/shadow_eval.py",
        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        "docs/RULE_COVERAGE.md",
        ".claude/agents/builder.md",
    ],
)
def test_fixround_b1_other_prefixes_regress_beyond_eof(path):
    warn = _fw(f"{path}:9999999")
    if os.path.exists(os.path.join(_REPO_ROOT, path)):
        assert "FRESHNESS WARN:" in warn
        assert f"{path}:9999999" in warn
    else:
        assert warn == ""  # молчание -- не файл этого дерева, не регресс


def test_fixround_b1_githooks_prefix_extracted_but_no_extensioned_file_here():
    # .githooks/ этого репо не несёт файлов С РАСШИРЕНИЕМ (commit-msg,
    # pre-commit -- без .ext) -- регекс СТРУКТУРНО требует \.ext, значит
    # безрасширительные хуки этого дерева никогда не станут якорем; сам
    # префикс распознаётся регексом (проверено НАПРЯМУЮ, не через
    # freshness_warn -- живого расширенного файла для позитива тут нет).
    assert dispatch_gate.FRESHNESS_LINE_ANCHOR_RE.search(".githooks/pre-commit.sh:1") is not None
    assert _fw(".githooks/pre-commit.sh:1") == ""  # файла с таким именем нет -- молчание


# --- Б2: класс (а) получает owns/non-goals/run-line/деплой+кит/toolkit ---


def test_fixround_b2_kit_hyphen_prefix_suppresses_warn():
    assert _fw("кит-чек 22(b)") == ""


def test_fixround_b2_toolkit_word_suppresses_warn():
    assert _fw("toolkit-обвязка … check 22(d)") == ""


def test_fixround_b2_bare_check_without_kit_context_still_warns():
    warn = _fw("чек 22(b)")
    assert "FRESHNESS WARN:" in warn


def test_fixround_b2_shtabnoy_check_32_true_positive_m1():
    warn = _fw("штабной чек 32(д)")
    assert "FRESHNESS WARN:" in warn
    assert "32(д)" in warn
    assert "реально есть" in warn or "подпунктов с буквами не найдено" in warn


def test_fixround_b2_owns_declared_check_token_suppressed():
    prompt = (
        "Дано: репо целиком.\n"
        "owns: чек 77(а)\n"
        "Сверься со сводкой."
    )
    assert _fw(prompt) == ""


def test_fixround_b2_run_line_check_token_suppressed():
    assert _fw("Прогон: python чек 77(а) -q") == ""


def test_fixround_b2_class_v_population_unaffected_by_kit_word():
    # Б2 -- ТОЛЬКО класс (а); кит-слово НЕ должно освобождать класс (в).
    warn = _fw("кит-обвязка ссылается на tools/dispatch_gate.py:9999999")
    assert "FRESHNESS WARN:" in warn


# --- Ф1: _WRITE_RETURN_TARGET_GUARD -- падеж + <=2 промежуточных слова ---


@pytest.mark.parametrize(
    "phrase",
    [
        "добавь в отчёте строку про результат",
        "добавь в дайджесте запись",
        "добавь в ответ ссылку на docs/x.md",
        "внеси в доклад краткий путь",
        "внеси в свой отчёт запись",
    ],
)
def test_fixround_f1_return_target_phrases_do_not_match(phrase):
    assert dispatch_gate.WRITE_INDICATORS_RE.search(phrase) is None


@pytest.mark.parametrize(
    "phrase",
    [
        "внеси правку в tools/x.py",
        "добавь строку в X.md",
        "добавь файл в репо",
        "ДОБАВЬ раздел в X.md",
    ],
)
def test_fixround_f1_previous_positives_still_match(phrase):
    assert dispatch_gate.WRITE_INDICATORS_RE.search(phrase) is not None


def test_fixround_f1_decide_return_target_phrase_not_blocked_as_write():
    # Живой блок критика: DoD+манифеста нет, но "добавь в отчёте..." --
    # НЕ write-индикатор -- проверка 2 (is_write) не включается вовсе.
    exit_code, message = dispatch_gate.decide(
        _builder_payload(
            "DoD: тест зелёный, witness приложен. Добавь в отчёте строку про результат.",
            description="sonnet: report",
        )
    )
    assert exit_code == 0, message


# --- Ф2: левая граница слова якорного слова класса (а) -------------------


def test_fixround_f2_word_inside_larger_word_not_matched():
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("число строчек 30(щ) велико") is None
    assert _fw("число строчек 30(щ) велико") == ""


def test_fixround_f2_start_of_string_still_matches():
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("чек 13(б)") is not None


def test_fixround_f2_after_punctuation_still_matches():
    assert dispatch_gate.FRESHNESS_CHECK_TOKEN_RE.search("(см. чек 13(б))") is not None


# --- Ф5: порядок веток -- существование ПЕРЕД латиницей -------------------


def test_fixround_f5_nonexistent_check_with_latin_letter_gives_m2_not_m4():
    warn = _fw("чек 77(b)")
    assert "НОМЕРЕ" in warn
    assert "латиница" not in warn


def test_fixround_f5_existing_check_with_latin_letter_gives_m4():
    warn = _fw("чек 22(b)")
    assert "латиница" in warn


# --- Ф3: кэш на вызов -- файл не перечитывается за каждый якорь ----------


def test_fixround_f3_same_file_multiple_anchors_reads_once(monkeypatch):
    real_open = open
    opened_paths = []

    def counting_open(path, *args, **kwargs):
        opened_paths.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)
    abs_path = str(Path(_REPO_ROOT) / "tools" / "dispatch_gate.py")
    prompt = " ".join(f"{abs_path}:{9000000 + i}" for i in range(5))
    warn = _fw(prompt)
    assert warn  # все 5 -- за концом файла
    reads_of_target = [p for p in opened_paths if os.path.normcase(p) == os.path.normcase(abs_path)]
    assert len(reads_of_target) == 1  # Ф3: РОВНО одно чтение на файл за вызов


def test_fixround_f3_check_token_verdict_cache_consistent_across_repeats():
    # Дедуп + кэш вместе -- 100 повторов одной пары даёт РОВНО одно
    # сообщение (регресс К9, застрахованный явным кэшем Ф3).
    warn = _fw(" ".join(["чек 77(а)"] * 100))
    assert warn.count("FRESHNESS WARN:") == 1
