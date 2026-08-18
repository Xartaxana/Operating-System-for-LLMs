"""Юнит-смоки tools/dispatch_gate.py (t-152, policy-as-code «ход вниз»).
Прямые вызовы decide() для всех веток + echo-JSON смок подпроцессом
(спека явно требует "юнит-тесты всех веток").

Штабной вариант: dispatch_gate.py в tools/ этого репо -- БЕЗ изменений
относительно кита (см. exam_fullgates_kit/staging_hq/README.md, п.
"dispatch_gate.py -- БЕЗ изменений"), поэтому тест-кейсы перенесены
как есть из exam_fullgates_kit/tools/test_dispatch_gate.py (t-159)."""

import json
import subprocess
import sys
import time
from pathlib import Path

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
    for tok in [
        "/etc/x",
        "/a",
        "D:\\x",
        "D:/x",
        "D:\\AI CRM\\x\\AGENTS.md",
        "logs/*.jsonl",
        "/*.py",
    ]:
        assert dispatch_gate.is_path_like_token(tok) is True, tok
    # Один длинный сегмент (5000 символов) после корня -- граница
    # длины, тоже True (правило 6а: тест на длинной границе).
    assert dispatch_gate.is_path_like_token("/" + ("a" * 5000)) is True


def test_doubled_root_with_segment_is_a_path():
    # Уточнение критика t-476: класс -- "корень БЕЗ сегмента", а не
    # "ровно один слэш". Удвоенный корень С сегментом -- это путь
    # (сегмент есть); `/+`/`[\\/]+` их принимает. Прежняя форма
    # `^/[^/\\s]` ошибочно роняла "//foo".
    for tok in ["//foo", "//server/share", "D://x", "///a"]:
        assert dispatch_gate.is_path_like_token(tok) is True, tok
    # Но голый удвоенный/утроенный корень БЕЗ сегмента остаётся False
    # (граница класса не сдвинута) -- дублирует контроль в
    # test_root_only_absolute_token_is_not_a_path, держится здесь рядом
    # с позитивами как парная граница.
    for tok in ["//", "///", "D://"]:
        assert dispatch_gate.is_path_like_token(tok) is False, tok


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
