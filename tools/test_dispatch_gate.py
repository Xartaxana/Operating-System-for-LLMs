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
    # пишущим (WRITE_INDICATORS_RE уже несёт `\bowns\b` с retry t-152,
    # "owns_gate.py" её не триггерит), проверка 2 пропускается целиком.
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


def test_extract_given_candidates_pathological_input_under_5s():
    # Форма критика: "C:/"*20000 + "a"*20000 -- без точки-расширения
    # вовсе (обрыв замера критика: 89.5с на 240КБ ДО фикса). Порог 5с
    # -- запас на медленный CI; реально ожидается <1с.
    pathological = "C:/" * 20000 + "a" * 20000
    start = time.monotonic()
    candidates = dispatch_gate.extract_given_candidates(pathological)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"took {elapsed:.2f}s -- quadratic regression?"
    assert candidates == []


def test_extract_given_candidates_1000_real_paths_previous_behavior():
    names = [f"tools/fake{i}.py" for i in range(1000)]
    prompt = "Given: " + ", ".join(names) + ". Read them all."
    start = time.monotonic()
    candidates = dispatch_gate.extract_given_candidates(prompt)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"took {elapsed:.2f}s"
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
