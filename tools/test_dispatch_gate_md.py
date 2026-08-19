"""tools/test_dispatch_gate_md.py -- батарея сиблинга tools/
dispatch_gate_md.py (партия 2 сканера регионов, УЗЕЛ C, t-529 /
docs/tasks/2026-08-19_scanner-party2-spec.md). MODULE_UNDER_TEST
переключает цель (образец конвенции F61_TARGET, tools/
test_f61_halfstate.py; тот же паттерн, что tools/test_negative_lint_md.py
партии 1 уже несёт): default -> сиблинг tools/dispatch_gate_md.py
(region-aware); MODULE_UNDER_TEST=live -> живой tools/dispatch_gate.py
БЕЗ единой правки -- используется здесь ТОЛЬКО как цель негативного
контроля дискриминации (C3, §8 п.4 родительской спеки): region-
специфичные assert'ы, зелёные на сиблинге, обязаны стать КРАСНЫМИ на
живой (нерегионной) цели.

Модуль резолвится через importlib.util по явному пути (не sys.path-игру
и не хардкод боевого пути в константе) -- сиблинг и живой файл РАЗНЫЕ
имена (dispatch_gate_md.py / dispatch_gate.py), поэтому обычный
`import dispatch_gate_md` не смог бы переключиться на живой файл под
тем же именем модуля; та же индирекция, что test_f61_halfstate.py._load()
и test_negative_lint_md.py._load_module() уже используют. f61-форма
резолвера (default -> сиблинг, ЕСЛИ существует, иначе живой файл) --
temporal-край 5.4 родительской спеки: до посадки default-прогон не
падает FileNotFoundError.

Существующий tools/test_dispatch_gate.py (батарея живого файла) НЕ
ТРОГАЕТСЯ этим диспатчем -- прогоняется отдельно как подтверждение
"живой не задет" (DoD п.3 отчёта билдера).

Run (дефолт, сиблинг):    python -m pytest tools/test_dispatch_gate_md.py -q
Контр-прогон (дискриминация, C3): MODULE_UNDER_TEST=live python -m
    pytest tools/test_dispatch_gate_md.py -q -k discrimination
"""

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from wallclock_guard import WALLCLOCK_CATASTROPHE_CEILING  # noqa: E402

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # f61-форма (temporal-край 5.4): default -- сиблинг, ЕСЛИ он существует,
    # иначе живой файл; после посадки байт-копией default-прогон не падает
    # на FileNotFoundError.
    if MODULE_UNDER_TEST == "live":
        return TOOLS_DIR / "dispatch_gate.py"
    sibling = TOOLS_DIR / "dispatch_gate_md.py"
    return sibling if sibling.exists() else TOOLS_DIR / "dispatch_gate.py"


SCRIPT = _resolve_script_path()


def _load_module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module(
    SCRIPT, f"dispatch_gate_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
)

_REGION_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live",
    reason="region API (m._region_at/_is_quoted/_safe_scan/_region_aware_*/"
    "dod_quoted_warn/manifest_quoted_warn) exists only on the sibling; "
    "MODULE_UNDER_TEST=live targets tools/dispatch_gate.py verbatim, which "
    "has none of it",
)

_REPO_ROOT = str(TOOLS_DIR.parent)


def _builder_payload(prompt: str, description=None) -> dict:
    tool_input = {"subagent_type": "builder", "prompt": prompt}
    if description is not None:
        tool_input["description"] = description
    return {"tool_name": "Task", "tool_input": tool_input, "cwd": _REPO_ROOT}


def _agent_payload(subagent_type=None, description=None, prompt="noop", cwd=None) -> dict:
    tool_input = {"prompt": prompt}
    if subagent_type is not None:
        tool_input["subagent_type"] = subagent_type
    if description is not None:
        tool_input["description"] = description
    payload = {"tool_name": "Task", "tool_input": tool_input}
    payload["cwd"] = cwd if cwd is not None else _REPO_ROOT
    return payload


def _run_hook(raw_input, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        **kwargs,
    )


def _run_hook_json(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


# ---------------------------------------------------------------------
# C1: четыре формы given-пути -- фенс нет-WARN / проза WARN / бэктики
# WARN / цитата нет-WARN. Позиция полярности -- W1 (given_path_warn),
# см. докстринг dispatch_gate_md.py, "ПОЛЯРНОСТЬ ЦИТАТА".
# ---------------------------------------------------------------------

_C1_MISSING = "tools/фейк_C1_нет_такого_файла.py"


def test_c1_discrimination_given_path_fenced_no_warn():
    # критик-фикс 3: given_path_warn() СУЩЕСТВУЕТ на живом файле (live
    # :860-881) -- не региональный API, вызов на MODULE_UNDER_TEST=live
    # не падает. Это НАСТОЯЩИЙ дискриминатор: живой (без региона) ВСЕГДА
    # предупреждает о недостающем пути независимо от фенса -> assert
    # "warn == ''" (ожидание сиблинга) КРАСНЕЕТ на живом (замер критика).
    prompt = f"Пример:\n```\nДано: {_C1_MISSING}\n```\n"
    warn = m.given_path_warn(_builder_payload(prompt))
    assert warn == ""


@_REGION_ONLY
def test_c1_given_path_prose_warns():
    prompt = f"Дано: {_C1_MISSING}. Прочитай его."
    warn = m.given_path_warn(_builder_payload(prompt))
    assert "GIVEN-PATH WARN" in warn
    assert _C1_MISSING in warn


@_REGION_ONLY
def test_c1_given_path_inline_code_backticks_warns():
    prompt = f"Дано: `{_C1_MISSING}`. Прочитай его."
    warn = m.given_path_warn(_builder_payload(prompt))
    assert "GIVEN-PATH WARN" in warn
    assert _C1_MISSING in warn


def test_c1_discrimination_given_path_blockquote_no_warn():
    # критик-фикс 3: симметричный дискриминатор для цитаты (см. докстринг
    # теста fenced выше за полное обоснование).
    prompt = f"> Дано: {_C1_MISSING}\n"
    warn = m.given_path_warn(_builder_payload(prompt))
    assert warn == ""


# ---------------------------------------------------------------------
# C2: "любое вхождение вне цитаты -> проверяем" -- тот же путь дважды
# (один раз в фенсе, один раз в прозе) -- дедуп сохраняется, WARN
# упоминает путь РОВНО один раз.
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_c2_any_unquoted_occurrence_qualifies_dedup_preserved():
    path = "tools/фейк_C2_нет_такого_файла.py"
    prompt = f"Пример:\n```\nДано: {path}\n```\nДано: {path}. Прочитай его."
    warn = m.given_path_warn(_builder_payload(prompt))
    assert "GIVEN-PATH WARN" in warn
    assert warn.count(path) == 1


# ---------------------------------------------------------------------
# C3: ДИСКРИМИНАЦИОННАЯ ПАРА -- цитируемая (фенсированная) owns-декларация
# "чужого манифеста" (owns+путь есть, given нигде нет вовсе, ни в цитате,
# ни в прозе). БЕЗ регион-фильтра (живой алгоритм / MODULE_UNDER_TEST=live)
# bare owns_declaration_has_path_token находит owns+путь ВНУТРИ фенса ->
# is_write=True -> has_manifest=False (given отсутствует совсем) -> БЛОК
# exit 2 -- КРАСНЫЙ на сиблинге же тест НЕ должен быть (см. ниже, сиблинг
# ждёт exit 0). Это ЕДИНСТВЕННОЕ место во всём узле C, где decide()
# сиблинга РЕАЛЬНО отличается от живого (Ф3а -- write-половина
# фильтруется региональноstrictly, снятие блока).
# ---------------------------------------------------------------------

_C3_PROMPT_FENCED = (
    "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
    "Пример чужого манифеста для иллюстрации формата:\n"
    "```\n"
    "owns (ABSOLUTE write paths): D:/repo/tools/foreign_example.py\n"
    "```\n"
    "Обсуди подход, ничего не делай сам."
)

_C3_PROMPT_UNFENCED = (
    "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
    "Пример чужого манифеста для иллюстрации формата:\n"
    "owns (ABSOLUTE write paths): D:/repo/tools/foreign_example.py\n"
    "Обсуди подход, ничего не делай сам."
)


def test_c3_discrimination_quoted_foreign_owns_declaration_lifts_block():
    # На сиблинге (default target) -- цитируемая owns-декларация не
    # включает проверку 2, блок СНИМАЕТСЯ (exit 0). На живом (MODULE_
    # UNDER_TEST=live) -- ТОТ ЖЕ assert становится КРАСНЫМ: bare-регекс
    # находит owns+путь независимо от фенса, given нигде нет -> exit 2.
    exit_code, message = m.decide(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert exit_code == 0, message


def test_c3_same_text_without_fence_still_blocks_on_both():
    # Позитивный контроль в паре (командная гигиена п.6): БЕЗ фенса
    # цитатных символов нет вовсе -- фильтровать нечего, ОБА (сиблинг и
    # живой) блокируют одинаково, как сегодня -- это НЕ дискриминация.
    exit_code, message = m.decide(
        _builder_payload(_C3_PROMPT_UNFENCED, description="sonnet: x")
    )
    assert exit_code == 2, message
    assert "манифеста" in message


@_REGION_ONLY
def test_c3_manifest_quoted_warn_fires_on_lifted_block():
    warn = m.manifest_quoted_warn(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert "MANIFEST-QUOTED WARN" in warn
    assert "owns" in warn


# --- критик-фикс 2 (решение Lead: "сигналить флип, не молчать") --------
# ДЫРА: write-глагол ТОЛЬКО в фенсе/цитате, БЕЗ единого манифест-маркера
# (given/owns) вообще -- bare is_write True (live блокирует), региональный
# is_write False (Ф3а снимает блок), но manifest_quoted_warn/dod_quoted_warn
# ОБА молчат (нет given/owns/DoD совпадений вовсе -- нечего флагировать) ->
# молчаливый флип exit2->exit0 БЕЗ единого WARN. write_quoted_warn() ниже
# закрывает эту дыру -- обе формы (фенс, blockquote).

_WRITE_QUOTED_FENCED_PROMPT = (
    "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
    "Пример инструкции для другого диспатча:\n"
    "```\n"
    "Правь файл x.py по спеке.\n"
    "```\n"
    "Обсуди подход, ничего не делай сам."
)

_WRITE_QUOTED_BLOCKQUOTE_PROMPT = (
    "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
    "> Правь файл x.py по спеке.\n"
    "Обсуди подход, ничего не делай сам."
)


@_REGION_ONLY
def test_fix2_write_quoted_warn_fenced_form_fires():
    payload = _builder_payload(_WRITE_QUOTED_FENCED_PROMPT, description="sonnet: x")
    exit_code, _ = m.decide(payload)
    assert exit_code == 0  # блок снят (Ф3а) -- проверяем, что WARN не немой
    warn = m.write_quoted_warn(payload)
    assert "WRITE-QUOTED WARN" in warn


@_REGION_ONLY
def test_fix2_write_quoted_warn_blockquote_form_fires():
    payload = _builder_payload(_WRITE_QUOTED_BLOCKQUOTE_PROMPT, description="sonnet: x")
    exit_code, _ = m.decide(payload)
    assert exit_code == 0
    warn = m.write_quoted_warn(payload)
    assert "WRITE-QUOTED WARN" in warn


@_REGION_ONLY
def test_fix2_write_quoted_warn_silent_when_manifest_marker_present():
    # Позитивный контроль (не задваивать сообщение): _C3_PROMPT_FENCED несёт
    # owns-маркер (квотированный) -- write_quoted_warn молчит, это покрыто
    # manifest_quoted_warn (C3) уже.
    warn = m.write_quoted_warn(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert warn == ""


@_REGION_ONLY
def test_fix2_write_quoted_warn_silent_when_no_flip():
    # Позитивный контроль: write-глагол НЕ квотирован -- региональный
    # is_write тоже True, флипа нет, write_quoted_warn молчит.
    prompt = "DoD: критерии приёмки — тест зелёный. Правь файл x.py по спеке."
    warn = m.write_quoted_warn(_builder_payload(prompt, description="sonnet: x"))
    assert warn == ""


# ---------------------------------------------------------------------
# C4: DoD ТОЛЬКО в фенсе -- decide() НЕ ЗАТРОНУТА (Ф1а/B1), exit 0 КАК
# СЕГОДНЯ на ОБОИХ таргетах (не дискриминация) + DOD_QUOTED_WARN
# появляется дополнительно на сиблинге.
# ---------------------------------------------------------------------

_C4_PROMPT = (
    "Пример корректного маркера приёмки для другого диспатча:\n"
    "```\n"
    "DoD: критерии приёмки — тест зелёный.\n"
    "```\n"
    "Прочитай файл x.py и опиши поведение, ничего не пиши."
)


def test_c4_dod_only_in_fence_exit0_same_as_today():
    exit_code, message = m.decide(_builder_payload(_C4_PROMPT, description="sonnet: read"))
    assert exit_code == 0, message


@_REGION_ONLY
def test_c4_dod_only_in_fence_warns():
    warn = m.dod_quoted_warn(_builder_payload(_C4_PROMPT, description="sonnet: read"))
    assert "DOD-QUOTED WARN" in warn
    assert "DoD" in warn  # preview -- ПЕРВОЕ найденное совпадение ("DoD", не вся строка)


# ---------------------------------------------------------------------
# C5: МАТРИЦА РАВЕНСТВА decide() сиблинг == живой на >=20 формах (пины
# батареи tools/test_dispatch_gate.py + канонический манифест). ВСЕ
# формы этой матрицы -- БЕЗ маркеров цитирования (`>~) -- регион-фильтр
# для них структурный no-op (нет цитаты -> нечего фильтровать), сиблинг
# обязан совпасть с живым ПОБАЙТНО (exit_code И message). ИСКЛЮЧЕНИЯ
# (поимённо, НЕ входят в эту матрицу -- тестируются ОТДЕЛЬНО как
# дискриминация): _C3_PROMPT_FENCED (C3, cодержит фенс -- РЕАЛЬНОЕ
# расхождение) и _C4_PROMPT (C4, содержит фенс -- decide() совпадает по
# exit_code, но НЕ входит в эту матрицу ради чистоты "формы без
# цитирования", уже покрыт отдельным тестом выше).
# ---------------------------------------------------------------------

_live = _load_module(TOOLS_DIR / "dispatch_gate.py", "dispatch_gate_c5_live")
_sib_path = TOOLS_DIR / "dispatch_gate_md.py"
# критик-фикс 1 (блокер посадки): _sib_path грузился БЕЗ exists()-охраны --
# после посадки байт-копией сиблинг снимается (temporal-край 5.4), и
# _load_module() падает FileNotFoundError НА СБОРЕ (не на прогоне) --
# критик воспроизвёл живым прогоном на копии: "3199 tests collected,
# 1 error, Interrupted". Та же f61-форма охраны, что уже несут соседи
# по классу (test_negative_lint_md.py:53, test_claim_control_gate_md.py:41,
# test_owns_gate_md.py:50, test_mechanism_gate_md.py:48) и что уже
# несёт _resolve_script_path() выше (:50-57) -- этот файл был
# ЕДИНСТВЕННЫМ в семье без такой охраны.
_C5_SIBLING_AVAILABLE = _sib_path.exists()
_sibling_for_c5 = _load_module(_sib_path, "dispatch_gate_c5_sibling") if _C5_SIBLING_AVAILABLE else None

_C5_MATRIX = [
    ("non_task_tool", {"tool_name": "Bash", "tool_input": {}}),
    ("missing_tool_input", {"tool_name": "Task"}),
    (
        "builder_without_dod_blocks",
        _builder_payload("Просто поправь опечатку в файле x.py.", description="sonnet: fix typo"),
    ),
    (
        "builder_with_dod_literal_passes",
        _builder_payload("Почини опечатку. DoD: тест зелёный.", description="sonnet: fix"),
    ),
    (
        "builder_with_criteria_priyomki_passes",
        _builder_payload(
            "Почини опечатку. Критерии приёмки: тест проходит.", description="sonnet: fix"
        ),
    ),
    (
        "builder_with_witness_passes",
        _builder_payload("Почини опечатку, приложи witness.", description="sonnet: fix"),
    ),
    (
        "pravj_substring_in_poprav_no_block",
        _builder_payload(
            "DoD: тест зелёный. Пожалуйста, поправь опечатку в файле x.py.",
            description="sonnet: fix typo",
        ),
    ),
    (
        "pravj_standalone_word_blocks",
        _builder_payload("DoD: тест зелёный. Правь файл x.py по спеке.", description="sonnet: fix"),
    ),
    (
        "write_indicator_with_full_manifest_passes",
        _builder_payload(
            "DoD: тест зелёный, witness приложен. Создай файл x.py. "
            "МАНИФЕСТ: дано — репо целиком; owns — tools/x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "write_indicator_with_only_owns_blocks",
        _builder_payload(
            "DoD: witness есть. owns: tools/x.py. Измени файл x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "write_indicator_with_only_given_blocks",
        _builder_payload(
            "DoD: witness есть. Given: репо целиком. Создай файл x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "dano_and_given_english_variant_recognized",
        _builder_payload(
            "DoD: witness есть. Given: репо целиком. owns: tools/x.py. Создай файл x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "owns_filename_substring_in_given_still_blocks",
        _builder_payload(
            "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
            "Дано: tools/owns_gate.py — образец экстракции.\n"
            "Правь файл x.py по спеке.",
            description="sonnet: write x",
        ),
    ),
    (
        "readonly_mentioning_owns_gate_filename_not_blocked",
        _builder_payload(
            "Прочитай tools/owns_gate.py и tools/dispatch_gate.py, опиши логику "
            "extract_owns_paths. DoD: явный ответ да/нет.",
            description="sonnet: read",
        ),
    ),
    (
        "markdown_bold_owns_marker_recognized",
        _builder_payload(
            "DoD: witness приложен. **Дано**: репо целиком. "
            "**owns**: D:/repo/tools/x.py. Создай файл x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "f59_pin_a_readonly_recon_discussing_owns_as_topic",
        _builder_payload(
            "Найди точку правки подкласса owns №2 в WRITE_INDICATORS_RE и "
            "опиши, где она живёт и как влияет на owns_gate.py. "
            "DoD: явный ответ да/нет по расположению.",
            description="sonnet: recon",
        ),
    ),
    (
        "f59_pin_b_critic_review_quoting_owns_norm_text",
        {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "critic",
                "prompt": (
                    "Ревью диффа: спека требует owns (ABSOLUTE write paths): <path> "
                    "по правилу 11 CLAUDE.md кита -- проверь, что диспатч несёт этот "
                    "маркер дословно."
                ),
                "description": "opus: review",
            },
            "cwd": _REPO_ROOT,
        },
    ),
    (
        "f59_owns_declaration_relative_path_only_no_manifest_required",
        _builder_payload("DoD: witness есть. owns: tools/x.py.", description="sonnet: write x"),
    ),
    (
        "f59_t384_owns_absolute_path_without_verb_requires_manifest",
        _builder_payload(
            "DoD: witness есть. owns (ABSOLUTE write paths): D:/repo/tools/x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "f59_t384_owns_absolute_path_with_given_no_verb_passes",
        _builder_payload(
            "DoD: witness есть.\nДано: репо целиком.\n"
            "owns (ABSOLUTE write paths): D:/repo/tools/x.py.",
            description="sonnet: write x",
        ),
    ),
    (
        "f59_t384_historical_class_b6_blocked",
        _builder_payload(
            "DoD: критерии приёмки -- тест зелёный, witness приложен.\n"
            "owns (ABSOLUTE write paths): D:/repo/tools/escalation_guard.py\n"
            "Реализуй эскалационный страж E1 по спеке.",
            description="sonnet: B6 escalation guard E1",
        ),
    ),
    (
        "f59_t384_historical_class_b6_with_given_passes",
        _builder_payload(
            "DoD: критерии приёмки -- тест зелёный, witness приложен.\n"
            "Дано: репо целиком.\n"
            "owns (ABSOLUTE write paths): D:/repo/tools/escalation_guard.py\n"
            "Реализуй эскалационный страж E1 по спеке.",
            description="sonnet: B6 escalation guard E1",
        ),
    ),
    (
        "manifest_given_word_boundary_prodano_false_positive",
        _builder_payload(
            "DoD: тест зелёный, witness приложен.\nВсё продано на складе.\n"
            "owns: tools/x.py\nПравь файл x.py по спеке.",
            description="sonnet: write x",
        ),
    ),
    (
        "missing_description_skips_check3",
        _builder_payload("Прочитай файл. DoD: явный ответ."),
    ),
    (
        "description_without_model_prefix_blocks",
        _builder_payload("Прочитай файл. DoD: явный ответ.", description="fix the bug"),
    ),
    (
        "priority_dod_wins_over_label",
        _builder_payload("Правь файл x.py.", description="fix it now"),
    ),
    (
        "priority_manifest_wins_over_label",
        _builder_payload("DoD: witness есть. Правь файл x.py.", description="fix it now"),
    ),
    (
        "scout_write_indicator_without_manifest_not_blocked",
        {
            "tool_name": "Task",
            "tool_input": {
                "subagent_type": "scout",
                "prompt": "Правь файл и создай файл заметок (это НЕ builder).",
                "description": "haiku: scout",
            },
            "cwd": _REPO_ROOT,
        },
    ),
    (
        "backtick_wrapped_owns_declaration_inline_code_not_filtered",
        # содержит quote-триггер (бэктик), но инлайн-код НЕ цитата в
        # полярности узла C -- scan() реально вызывается (не no-op по
        # предфильтру), результат ОБЯЗАН совпасть с живым (см. докстринг
        # "ПОЛЯРНОСТЬ ЦИТАТА").
        _builder_payload(
            "DoD: witness есть. owns: `D:/repo/tools/a.py`.", description="sonnet: write x"
        ),
    ),
]


def test_c5_matrix_has_at_least_20_forms():
    assert len(_C5_MATRIX) >= 20, len(_C5_MATRIX)


@pytest.mark.skipif(
    not _C5_SIBLING_AVAILABLE,
    reason="сиблинг tools/dispatch_gate_md.py снят (посадка байт-копией уже "
    "прошла) -- матрица равенства сиблинг-vs-живой беспредметна: сиблинга "
    "больше нет как отдельного файла, живой tools/dispatch_gate.py теперь "
    "и есть region-aware код; см. tools/test_dispatch_gate.py за пост-"
    "посадочную канонический батарею",
)
@pytest.mark.parametrize("name,payload", _C5_MATRIX, ids=[n for n, _ in _C5_MATRIX])
def test_c5_decide_equality_sibling_vs_live(name, payload):
    live_result = _live.decide(payload)
    sib_result = _sibling_for_c5.decide(payload)
    assert sib_result == live_result, f"{name}: sibling={sib_result} live={live_result}"


# ---------------------------------------------------------------------
# C6: порядок WARN -- given первым (не тронут), новые слои (dod/manifest
# quoted) -- В ХВОСТ существующего списка (given, role).
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_c6_warn_order_given_role_dod_manifest():
    prompt = (
        "Пример корректного маркера приёмки:\n```\nDoD: критерии приёмки — тест зелёный.\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/foreign_example.py\n```\n"
        "Дано: tools/фейк_C6_нет_такого_файла.py.\n"
        "Прочитай его и опиши поведение, ничего не пиши."
    )
    payload = _builder_payload(prompt, description="opus: делает что-то")
    result = _run_hook_json(payload)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    out = json.loads(result.stdout.decode("utf-8"))
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "GIVEN-PATH WARN" in ctx
    assert "ROLE-TYPE WARN" in ctx
    assert "DOD-QUOTED WARN" in ctx
    assert "MANIFEST-QUOTED WARN" in ctx
    i_given = ctx.index("GIVEN-PATH WARN")
    i_role = ctx.index("ROLE-TYPE WARN")
    i_dod = ctx.index("DOD-QUOTED WARN")
    i_manifest = ctx.index("MANIFEST-QUOTED WARN")
    assert i_given < i_role < i_dod < i_manifest


# ---------------------------------------------------------------------
# C7: ПОЗИЦИОННЫЙ ИНВАРИАНТ -- exit 2 ДО вычисления любого WARN. Блок
# приходит с check3 (лейбл), ХОТЯ WARN-условия (quoted DoD, missing
# given) технически истинны -- на заблокированном диспатче ни один
# новый слой не исполняется, stdout пуст.
# ---------------------------------------------------------------------


def test_c7_exit2_before_any_warn_stdout_empty():
    prompt = (
        "Пример корректного маркера приёмки:\n```\nDoD: критерии приёмки — тест зелёный.\n```\n"
        "Дано: tools/фейк_C7_нет_такого_файла.py. Прочитай его."
    )
    payload = _builder_payload(prompt, description="fix it now")  # без модели -> check3 блок
    result = _run_hook_json(payload)
    assert result.returncode == 2
    assert result.stdout == b""


# ---------------------------------------------------------------------
# C8: И-0 -- ТРИ формы отказа md_regions -> сиблинг ведёт себя КАК
# ЖИВОЙ файл побайтно на C3-тексте (месте, где регион РЕАЛЬНО меняет
# результат).
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_c8_i0_scan_is_none_matches_live(monkeypatch):
    # НЕ сравнивается с _live.decide() (класс temporal-хрупкости, найден
    # критиком, DoD п.4/пост-посадочная симуляция): _live -- ОТДЕЛЬНЫЙ
    # модульный инстанс, загруженный из TOOLS_DIR/"dispatch_gate.py" --
    # ДО посадки это гарантированно живой (не региональный) файл, ПОСЛЕ
    # посадки этот же путь несёт region-aware код (_live == m по
    # содержимому, разные инстансы) -- сравнение "m с патченным scan"
    # против "_live с настоящим scan" перестало бы проверять И-0
    # (bare-фоллбек), а начало бы проверять "фоллбек m совпадает с
    # регион-осведомлённым _live", что и ДОЛЖНО расходиться на C3-тексте
    # (см. C3). Утверждение -- напрямую то, что И-0 обещает: bare-фоллбек
    # (см. докстринг owns_declaration_has_path_token()) даёт ТОТ ЖЕ
    # результат, что и живой bare-алгоритм всегда давал на этом тексте --
    # exit 2, "манифеста" (given отсутствует, owns+путь есть) -- та же
    # хардкод-форма, что sиблинг-тесты raises/degraded ниже уже несут.
    monkeypatch.setattr(m, "scan", None)
    exit_code, message = m.decide(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert exit_code == 2
    assert "манифеста" in message


@_REGION_ONLY
def test_c8_i0_scan_raises_matches_live(monkeypatch):
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    exit_code, message = m.decide(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert exit_code == 2
    assert "манифеста" in message


@_REGION_ONLY
def test_c8_i0_scan_degraded_matches_live(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    exit_code, message = m.decide(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert exit_code == 2
    assert "манифеста" in message


# --- критик-фикс 6: три подмены C8 распространены на dod_quoted_warn/
# manifest_quoted_warn -- ДО фикса пинилась только decide(); оба новых
# WARN-слоя обязаны отдавать "" под КАЖДОЙ из трёх форм отказа модуля
# (И-0), симметрично decide() выше. Позитивный контроль (что слои вообще
# способны дать НЕпустой warn на этих же промптах при ЖИВОМ scan) уже
# покрыт test_c3_manifest_quoted_warn_fires_on_lifted_block /
# test_c4_dod_only_in_fence_warns -- эти три теста ловят именно РЕГРЕСС
# ПОД ОТКАЗОМ модуля, не общее "функция всегда молчит".


@_REGION_ONLY
def test_c8_fix6_dod_and_manifest_quoted_warn_scan_is_none_silent(monkeypatch):
    monkeypatch.setattr(m, "scan", None)
    assert m.dod_quoted_warn(_builder_payload(_C4_PROMPT, description="sonnet: read")) == ""
    assert (
        m.manifest_quoted_warn(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x")) == ""
    )


@_REGION_ONLY
def test_c8_fix6_dod_and_manifest_quoted_warn_scan_raises_silent(monkeypatch):
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    assert m.dod_quoted_warn(_builder_payload(_C4_PROMPT, description="sonnet: read")) == ""
    assert (
        m.manifest_quoted_warn(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x")) == ""
    )


@_REGION_ONLY
def test_c8_fix6_dod_and_manifest_quoted_warn_scan_degraded_silent(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    assert m.dod_quoted_warn(_builder_payload(_C4_PROMPT, description="sonnet: read")) == ""
    assert (
        m.manifest_quoted_warn(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x")) == ""
    )


# ---------------------------------------------------------------------
# C9: И-1 -- scan() <=1 раз за вызов, только после двухчастного
# предфильтра (маркерный хит И символ из "`>~ в тексте).
# ---------------------------------------------------------------------


def _counting_scan(calls, real_scan):
    def _wrapped(text):
        calls["n"] += 1
        return real_scan(text)

    return _wrapped


@_REGION_ONLY
def test_c9_is_write_no_marker_at_all_scan_not_called(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    prompt = "DoD: тест зелёный. Просто почитай файл, ничего не пиши."
    m.decide(_builder_payload(prompt, description="sonnet: read"))
    assert calls["n"] == 0


@_REGION_ONLY
def test_c9_is_write_marker_present_no_quote_trigger_scan_not_called(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    prompt = "DoD: witness есть. owns (ABSOLUTE write paths): D:/repo/tools/x.py."
    exit_code, _ = m.decide(_builder_payload(prompt, description="sonnet: write x"))
    assert calls["n"] == 0
    assert exit_code == 2  # bare-результат применён напрямую, без сканирования


@_REGION_ONLY
def test_c9_is_write_marker_and_quote_trigger_scan_called_once(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    m.decide(_builder_payload(_C3_PROMPT_FENCED, description="sonnet: x"))
    assert calls["n"] == 1


@_REGION_ONLY
def test_c9_given_path_warn_no_candidates_scan_not_called(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    m.given_path_warn(_builder_payload("Просто прочитай файл, ничего интересного тут нет."))
    assert calls["n"] == 0


@_REGION_ONLY
def test_c9_given_path_warn_candidates_no_quote_trigger_scan_not_called(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    m.given_path_warn(_builder_payload(f"Дано: {_C1_MISSING}. Прочитай его."))
    assert calls["n"] == 0


@_REGION_ONLY
def test_c9_given_path_warn_candidates_and_quote_trigger_scan_called_once(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    prompt = f"Пример:\n```\nДано: {_C1_MISSING}\n```\nДано: {_C1_MISSING}. Прочитай его."
    m.given_path_warn(_builder_payload(prompt))
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# B3/W2: структурные поля -- сканер НЕ применяется (регресс-пин: role_
# type_warn/label-check не завязаны на scan() вовсе, даже когда текст
# лейбла/типа содержит quote-триггер символы).
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_b3_w2_label_and_role_checks_never_call_scan(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(m, "scan", _counting_scan(calls, m.scan))
    payload = _agent_payload(subagent_type="builder", description="`sonnet`: fix", prompt="noop")
    exit_code, _ = m.decide(payload)
    m.role_type_warn(payload)
    assert calls["n"] == 0


# ---------------------------------------------------------------------
# Регрессия базового поведения (не привязана к региону -- ОБА таргета).
# ---------------------------------------------------------------------


def test_regression_readonly_dispatch_not_blocked():
    exit_code, message = m.decide(
        _builder_payload(
            "Прочитай файл x.py и скажи, что там. DoD: явный ответ да/нет.",
            description="sonnet: read",
        )
    )
    assert exit_code == 0, message


def test_regression_write_with_full_manifest_passes():
    prompt = (
        "DoD: тест зелёный, witness приложен. Создай файл x.py. "
        "МАНИФЕСТ: дано — репо целиком; owns — tools/x.py."
    )
    exit_code, message = m.decide(_builder_payload(prompt, description="sonnet: write x"))
    assert exit_code == 0, message


def test_echo_json_blocks_builder_without_dod():
    result = _run_hook_json(_builder_payload("Просто поправь.", description="sonnet: fix"))
    assert result.returncode == 2
    assert "без DoD" in result.stderr.decode("utf-8", errors="replace")


def test_echo_json_passes_builder_with_dod():
    result = _run_hook_json(
        _builder_payload("Почини. DoD: тест зелёный.", description="sonnet: fix")
    )
    assert result.returncode == 0
    assert result.stdout in (b"", result.stdout)  # может нести WARN, не должен ронять хук
    assert result.stderr == b""


def test_echo_json_malformed_json_fails_open():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=b"{not valid json",
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stderr == b""
