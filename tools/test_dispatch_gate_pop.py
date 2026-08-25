"""tools/test_dispatch_gate_pop.py -- батарея сиблинга tools/
dispatch_gate_pop.py (узел A DAG-фикса класса warn-слоёв, 2026-08-25,
docs/tasks/2026-08-25_warn-class-fix-dag.md). Имя `_pop`, не `_md` --
Р-А1 (см. докстринг dispatch_gate_pop.py за обоснование: появление
tools/dispatch_gate_md.py молча переключило бы f61-резолвер
test_dispatch_gate_md.py на СЕБЯ).

MODULE_UNDER_TEST переключает цель (та же конвенция F61_TARGET, что
test_dispatch_gate_md.py уже несёт): default -> сиблинг tools/
dispatch_gate_pop.py; MODULE_UNDER_TEST=live -> живой tools/
dispatch_gate.py БЕЗ единой правки -- ТОЛЬКО как цель негативного
контроля дискриминации (тесты, чьё имя несёт "discrimination":
зелёные на сиблинге, ОБЯЗАНЫ стать красными на живом -- узел A
сужает исключения GIVEN_PATH и расщепляет ROLE_TYPE_WARN_UNKNOWN_ROLE,
которых на живом файле нет вовсе или которые ведут себя иначе).

Run (дефолт, сиблинг):
    python -m pytest tools/test_dispatch_gate_pop.py -q
Контр-прогон (дискриминация, DoD п.3 спеки узла A):
    MODULE_UNDER_TEST=live python -m pytest tools/test_dispatch_gate_pop.py -q -k discrimination
А-К8, замер (тот же дефолтный прогон, но с -s чтобы увидеть печать):
    python -m pytest tools/test_dispatch_gate_pop.py -q -k a_k8 -s
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
REPO_ROOT_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(REPO_ROOT_DIR))

from tools.warn_density import (  # noqa: E402
    enumerate_corpus_files,
    is_sidechain_file,
    _default_transcripts_dir,
)

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # f61-форма (temporal-край, см. докстринг dispatch_gate_pop.py):
    # default -- сиблинг, ЕСЛИ он существует, иначе живой файл.
    if MODULE_UNDER_TEST == "live":
        return TOOLS_DIR / "dispatch_gate.py"
    sibling = TOOLS_DIR / "dispatch_gate_pop.py"
    return sibling if sibling.exists() else TOOLS_DIR / "dispatch_gate.py"


SCRIPT = _resolve_script_path()


def _load_module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module(
    SCRIPT, f"dispatch_gate_pop_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
)

# _live -- ВСЕГДА живой файл, независимо от MODULE_UNDER_TEST -- нужен для
# матрицы РАВЕНСТВА exit_code (DoD п.2: exit_code сиблинга == exit_code
# живого на КАЖДОМ кейсе батареи) -- сравнение ДОЛЖНО состояться даже
# когда `m` сам указывает на живой файл (тривиально сойдётся).
_live = _load_module(TOOLS_DIR / "dispatch_gate.py", "dispatch_gate_pop_live_ref")

_SIBLING_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live",
    reason="функции узла A (_is_template_token/_token_occurrence_sections/"
    "ROLE_TYPE_WARN_PROJECT/BUILTIN_TYPE/...) существуют только на сиблинге; "
    "MODULE_UNDER_TEST=live целится в tools/dispatch_gate.py дословно, "
    "которого этого узла нет",
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


def _run_hook_json(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


# ---------------------------------------------------------------------
# Позитивный контроль резолвера (командная гигиена п.6): m и _live --
# РАЗНЫЕ объекты по умолчанию (сиблинг реально загрузился, не совпал с
# живым файлом случайно).
# ---------------------------------------------------------------------


def test_resolver_sibling_and_live_are_distinct_modules_by_default():
    if MODULE_UNDER_TEST == "live":
        pytest.skip("MODULE_UNDER_TEST=live -- m IS _live умышленно")
    if not (Path(__file__).resolve().parent / "dispatch_gate_pop.py").exists():
        # МИР ПОСЛЕ ПОСАДКИ (Lead, 2026-08-25): сиблинг удалён, резолвер
        # штатно упал на живой файл -- он теперь и НЕСЁТ узел A. Ограда
        # «сиблинг отличен от живого» имела смысл только ДО посадки;
        # здесь проверяем противоположное -- фича доехала до живого.
        # (`m is _live` невозможно и там: модули грузятся под разными
        # алиасами -- сверяем ПУТЬ и наличие фичи в ОБОИХ.)
        assert SCRIPT == TOOLS_DIR / "dispatch_gate.py"
        assert hasattr(m, "_is_template_token")
        assert hasattr(_live, "_is_template_token")
        return
    assert m is not _live
    assert hasattr(m, "_is_template_token")
    assert not hasattr(_live, "_is_template_token")


# =======================================================================
# А-К1 (форма а, Р4 -- решение Lead): токен, объявленный в owns-секции
# (>=1 вхождение), свободен ВЕЗДЕ -- если given не выкупает.
# =======================================================================

_AK1_SIBLING_TOKEN = "tools/negative_lint_md.py"  # реальный сиблинг-паттерн D-0069


def _ak1_prompt_owns_and_prose():
    # "Форма сдачи" -- ДО заголовка "Дано:" (секция "none"), не МЕЖДУ
    # given/owns -- given-секция (как и non-goals) НЕ закрывается пустой
    # строкой (D-2/D-3), строка между заголовками попала бы В given и
    # выкупила бы токен ПО given-приоритету, замаскировав именно то,
    # что тест обязан проверить (owns-декларацию, форму (а)).
    return (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"Форма сдачи: сиблинг {_AK1_SIBLING_TOKEN} (D-0069, самоактивирующийся файл).\n\n"
        "Дано: репо целиком.\n\n"
        f"owns: {_AK1_SIBLING_TOKEN}\n"
    )


def test_a_k1_discrimination_owns_declared_sibling_freed_everywhere():
    # НЕ существует на диске (реальный, но НЕсозданный сиблинг) -- на
    # сиблинге освобождается (объявлен в owns), на живом ОСТАЁТСЯ
    # проверяемым (occurrence в прозе "Форма сдачи:" -- вне owns).
    warn = m.given_path_warn(_builder_payload(_ak1_prompt_owns_and_prose()))
    assert _AK1_SIBLING_TOKEN not in warn


def test_a_k1_residual_prose_only_without_owns_declaration_still_warns():
    # ОСТАТОК, названный докстрингом: сиблинг упомянут в прозе, НО НЕ
    # объявлен в owns -- давление ОСТАЁТСЯ на ОБОИХ таргетах (не
    # дискриминация -- правильное поведение, не чинится этим узлом).
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"Форма сдачи: сиблинг {_AK1_SIBLING_TOKEN} (D-0069).\n\n"
        "Дано: репо целиком.\n\n"
        "owns: D:/repo/tools/other_file.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK1_SIBLING_TOKEN in warn


def test_a_k1_given_beats_owns_declaration_token_still_checked():
    # А-К6 против А-К1: тот же токен ТАКЖЕ назван в given -> given
    # выигрывает, токен ПРОВЕРЯЕТСЯ несмотря на owns-декларацию (то же
    # поведение на обоих таргетах -- не дискриминация).
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано:\n"
        f"- {_AK1_SIBLING_TOKEN}\n\n"
        "owns:\n"
        f"- {_AK1_SIBLING_TOKEN}\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK1_SIBLING_TOKEN in warn


@_SIBLING_ONLY
def test_a_k1_owns_bullet_form_declares_token_directly():
    # Позитивный контроль: токен НАЗВАН ТОЛЬКО в owns (не в прозе вовсе)
    # -- освобождается на сиблинге (форма owns и ДО этой правки уже
    # освобождала такие токены -- регресс-пин, не новое поведение).
    # Однострочная форма "owns: <token>" -- НЕ буллет-список: буллет-
    # продолжение owns-секции (_is_owns_continuation_line) требует
    # path-подобный (абсолютный/glob) первый токен, ОТНОСИТЕЛЬНЫЙ путь
    # его не проходит (D-3, поведение ДО узла A, не тронуто) -- та же
    # форма, что test_dispatch_gate.py уже несёт для относительных
    # owns-путей ("f59_owns_declaration_relative_path_only...").
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n"
        f"owns: {_AK1_SIBLING_TOKEN}\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK1_SIBLING_TOKEN not in warn


# =======================================================================
# А-К2 (форма б): токен, КАЖДОЕ вхождение которого непосредственно
# после `python`/`pytest`, свободен -- если given не выкупает.
# =======================================================================

_AK2_TOKEN = "tools/test_фейк_AK2_нет_такого_файла.py"


# Строка прогона -- ДО заголовка "Дано:" (секция "none"), той же
# причине, что _ak1_prompt_owns_and_prose() выше: given-секция не
# закрывается пустой строкой, строка МЕЖДУ given/owns попала бы в
# given и выкупила бы токен, замаскировав именно форму (б).


def test_a_k2_discrimination_run_line_token_freed():
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"Проверочный прогон: python {_AK2_TOKEN} -q\n\n"
        "Дано: репо целиком.\n\n"
        "owns: D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK2_TOKEN not in warn


def test_a_k2_discrimination_pytest_launch_word_freed():
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"pytest {_AK2_TOKEN} -q\n\n"
        "Дано: репо целиком.\n\n"
        "owns: D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK2_TOKEN not in warn


def test_a_k2_given_beats_run_line_token_still_checked():
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано:\n"
        f"- {_AK2_TOKEN}\n\n"
        f"python {_AK2_TOKEN} -q\n\n"
        "owns: D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK2_TOKEN in warn


def test_a_k2_not_every_occurrence_after_launch_word_still_checked():
    # Токен встречается ДВАЖДЫ: один раз после `python`, второй раз в
    # прозе -- НЕ все вхождения после запускающего слова -> проверяется
    # (не свобождается частично, форма "каждое вхождение"). Обе строки
    # -- ДО "Дано:" (секция "none"), чтобы given-приоритет не маскировал
    # именно то, что проверяет тест.
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"python {_AK2_TOKEN} -q\n\n"
        f"Файл {_AK2_TOKEN} несёт саму батарею.\n\n"
        "Дано: репо целиком.\n\n"
        "owns: D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK2_TOKEN in warn


def test_a_k2_word_between_launcher_and_token_not_immediate_still_checked():
    # `python -q tools/x.py` -- между лаунчером и токеном стоит флаг ->
    # НЕ "непосредственно после" -> не освобождается (не дискриминация:
    # ни один таргет не освобождал бы этот случай).
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"python -q {_AK2_TOKEN}\n\n"
        "Дано: репо целиком.\n\n"
        "owns: D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK2_TOKEN in warn


# =======================================================================
# А-К3 (форма в1): шаблон имени -- БЕЗУСЛОВНО, given НЕ выкупает.
# Граница: >=2 ОДИНАКОВЫХ заглавных латинских ПОДРЯД.
# =======================================================================

_AK3_TOKEN = "PROCESS/checks/CHK-NN.md"
_AK3_TOKEN_1LETTER = "PROCESS/checks/CHK-N.md"
_AK3_TOKEN_3LETTERS = "PROCESS/checks/CHK-NNN.md"


def test_a_k3_discrimination_template_token_freed_unconditionally():
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n"
        f"Предложи схему по образцу {_AK3_TOKEN} (шаблон имени, не путь).\n\n"
        "owns:\n- D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK3_TOKEN not in warn


def test_a_k3_discrimination_template_beats_given_buyback():
    # А-К3 против А-К6: даже НАЗВАННЫЙ в given шаблон исключается --
    # дефект ФОРМЫ корзины, роль токена не спасает (спека, конфликт 3).
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано:\n"
        f"- {_AK3_TOKEN}\n\n"
        "owns:\n- D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK3_TOKEN not in warn


@_SIBLING_ONLY
def test_a_k3_boundary_two_identical_uppercase_excluded():
    assert m._is_template_token(_AK3_TOKEN) is True  # CHK-NN.md -- на границе


@_SIBLING_ONLY
def test_a_k3_boundary_single_uppercase_not_excluded():
    assert m._is_template_token(_AK3_TOKEN_1LETTER) is False  # CHK-N.md -- ДО границы


@_SIBLING_ONLY
def test_a_k3_boundary_three_identical_uppercase_excluded():
    assert m._is_template_token(_AK3_TOKEN_3LETTERS) is True  # CHK-NNN.md -- ЗА границей


@_SIBLING_ONLY
def test_a_k3_angle_bracket_form_excluded():
    assert m._is_template_token("tools/session_context_<ROLE>.py") is True


@_SIBLING_ONLY
def test_a_k3_brace_form_excluded():
    assert m._is_template_token("tools/session_context_{ROLE}.py") is True


@_SIBLING_ONLY
def test_a_k3_no_template_marker_not_excluded():
    assert m._is_template_token("tools/dispatch_gate.py") is False


@_SIBLING_ONLY
def test_a_k3_real_word_with_double_letter_not_false_positive():
    # PROCESS -- "SS" НЕ изолирован (СРАЗУ после буквы "E") -> НЕ шаблон.
    # Регресс-страховка против ложного срабатывания на реальных именах.
    assert m._is_template_token("PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md") is False
    assert m._is_template_token("docs/BOOT.md") is False


def test_a_k3_full_pipeline_boundary_via_find_missing_given_paths():
    # Тот же граничный набор, но через ПОЛНЫЙ пайплайн (не только
    # предикат напрямую) -- CHK-N.md (1 буква) ДОЛЖЕН остаться missing
    # (не шаблон, вне owns, не given), CHK-NN.md/CHK-NNN.md -- НЕТ.
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n"
        f"Файлы для примера: {_AK3_TOKEN_1LETTER}, {_AK3_TOKEN}, {_AK3_TOKEN_3LETTERS}.\n\n"
        "owns:\n- D:/repo/tools/x.py\n"
    )
    missing = m.find_missing_given_paths(prompt, _REPO_ROOT)
    assert _AK3_TOKEN_1LETTER in missing
    assert _AK3_TOKEN not in missing
    assert _AK3_TOKEN_3LETTERS not in missing


# =======================================================================
# А-К4 (форма в2): список НЕ-ЦЕЛЕЙ -- своя метка секции, а не "other".
# Токен, ВСЕ вхождения которого внутри non-goals, свободен -- если
# given не выкупает.
# =======================================================================

_AK4_TOKEN = "tools/фейк_AK4_нет_такого_файла.py"


@pytest.mark.parametrize(
    "header",
    ["## НЕ-ЦЕЛИ", "не-цели:", "не цели:", "non-goals:"],
)
def test_a_k4_discrimination_non_goals_section_forms_free_confined_token(header):
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n"
        f"{header}\n"
        f"НЕ трогать {_AK4_TOKEN} (иллюстрация).\n\n"
        "owns:\n- D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK4_TOKEN not in warn, f"header={header!r}"


def test_a_k4_token_outside_non_goals_still_checked():
    # Позитивный контроль: тот же токен упомянут ВНЕ non-goals (в прозе
    # выше) -> НЕ все вхождения внутри секции -> проверяется (на ОБОИХ
    # таргетах, регресс-подтверждение, что фикс не разболтал общий случай).
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        f"Файл {_AK4_TOKEN} упомянут в прозе выше секции.\n\n"
        "Дано: репо целиком.\n\n"
        "## НЕ-ЦЕЛИ\n"
        f"НЕ трогать {_AK4_TOKEN} тоже.\n\n"
        "owns:\n- D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK4_TOKEN in warn


def test_a_k4_given_beats_non_goals_confinement_still_checked():
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано:\n"
        f"- {_AK4_TOKEN}\n\n"
        "## НЕ-ЦЕЛИ\n"
        f"НЕ трогать {_AK4_TOKEN}.\n\n"
        "owns:\n- D:/repo/tools/x.py\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert _AK4_TOKEN in warn


@_SIBLING_ONLY
def test_a_k4_blank_line_does_not_close_non_goals_section():
    # Симметрия с given/other (НЕ с owns): пустая строка секцию НЕ
    # закрывает -- метка держится до следующего заголовка манифеста.
    prompt = (
        "## НЕ-ЦЕЛИ\n"
        "Первая строка не-целей.\n"
        "\n"
        f"НЕ трогать {_AK4_TOKEN} (после пустой строки, ещё та же секция).\n"
    )
    offsets, sections = m._section_map(prompt)
    lines = prompt.splitlines(keepends=True)
    idx = next(i for i, l in enumerate(lines) if _AK4_TOKEN in l)
    assert sections[idx] == "non-goals"


@_SIBLING_ONLY
def test_a_k4_owns_without_blank_line_before_non_goals_header_closes_owns():
    # `owns:` без пустой строки перед `## НЕ-ЦЕЛИ` -- заголовок сам
    # закрывает owns и открывает non-goals НА ТОЙ ЖЕ строке (приоритет
    # заголовка в _section_map, не нужна пустая строка).
    prompt = (
        "owns:\n"
        "- D:/repo/tools/x.py\n"
        "## НЕ-ЦЕЛИ\n"
        f"НЕ трогать {_AK4_TOKEN}.\n"
    )
    offsets, sections = m._section_map(prompt)
    lines = prompt.splitlines(keepends=True)
    idx_header = next(i for i, l in enumerate(lines) if "НЕ-ЦЕЛИ" in l)
    idx_token = next(i for i, l in enumerate(lines) if _AK4_TOKEN in l)
    assert sections[idx_header] == "non-goals"
    assert sections[idx_token] == "non-goals"


@_SIBLING_ONLY
def test_a_k4_non_goals_header_inside_fence_still_opens_section_known_hole():
    # НАЗВАННЫЙ ОСТАТОК (Ф12, ослабленно): _section_map() НЕ фенс-
    # осведомлён -- тот же класс, что уже есть у owns/given сегодня
    # (докстринг модуля, "новых дыр не создано"). Тест ДОКУМЕНТИРУЕТ
    # фактическое (эмпирически проверенное) поведение, не желаемое.
    prompt = (
        "Пример формата для иллюстрации:\n"
        "```\n"
        "## НЕ-ЦЕЛИ\n"
        f"НЕ трогать {_AK4_TOKEN} (внутри фенса).\n"
        "```\n"
    )
    offsets, sections = m._section_map(prompt)
    lines = prompt.splitlines(keepends=True)
    idx = next(i for i, l in enumerate(lines) if _AK4_TOKEN in l)
    assert sections[idx] == "non-goals"  # известная дыра: фенс не защищает


# =======================================================================
# А-К5/positional: ни одно правило не ДОБАВЛЯЕТ в missing; несколько
# правил, применимых разом, не конфликтуют (коммутативность).
# =======================================================================


def test_a_k5_filter_never_adds_tokens_only_removes():
    candidates = [("tools/a.py", False), ("tools/b.py", False), ("C:/x/y.txt", True)]
    prompt = "просто текст без секций манифеста вовсе"
    filtered = m._filter_given_candidates(prompt, candidates)
    filtered_set = {t for t, _ in filtered}
    assert filtered_set <= {t for t, _ in candidates}


@_SIBLING_ONLY
def test_a_positional_multiple_rules_apply_simultaneously_no_conflict():
    # Токен объявлен в owns И, ОТДЕЛЬНО, упомянут в non-goals -- две
    # разные причины исключения не конфликтуют, результат один (не
    # двойной подсчёт, не исключение). Однострочная форма "owns: <tok>"
    # -- буллет-продолжение owns требует path-подобный (абсолютный/
    # glob) первый токен (_is_owns_continuation_line, D-3),
    # относительный путь его не проходит -- см.
    # test_a_k1_owns_bullet_form_declares_token_directly.
    tok = "tools/фейк_AK_multi_нет_такого_файла.py"
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n"
        f"owns: {tok}\n\n"
        "## НЕ-ЦЕЛИ\n"
        f"НЕ трогать {tok} параллельно.\n"
    )
    warn = m.given_path_warn(_builder_payload(prompt))
    assert tok not in warn


# =======================================================================
# А-К7: ROLE_TYPE_WARN расщепление PROJECT/BUILTIN_TYPE.
# =======================================================================


@_SIBLING_ONLY
def test_a_k7_both_texts_share_byte_identical_prefix():
    prefix = "ROLE-TYPE WARN:"
    assert m.ROLE_TYPE_WARN_PROJECT.startswith(prefix)
    assert m.ROLE_TYPE_WARN_BUILTIN_TYPE.startswith(prefix)


@_SIBLING_ONLY
def test_a_k7_both_texts_carry_nет_rol_faila_substring():
    assert "нет роль-файла" in m.ROLE_TYPE_WARN_PROJECT
    assert "нет роль-файла" in m.ROLE_TYPE_WARN_BUILTIN_TYPE


@pytest.mark.parametrize(
    "builtin_type", ["general-purpose", "claude-code-guide", "Explore", "Plan", "statusline-setup"]
)
def test_a_k7_builtin_type_uses_builtin_text(builtin_type):
    warn = m.role_type_warn(
        _agent_payload(subagent_type=builtin_type, description="sonnet: сделай что-то")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "нет роль-файла" in warn
    if MODULE_UNDER_TEST != "live":
        assert "это ожидаемо" in warn  # BUILTIN_TYPE-специфичная фраза


def test_a_k7_unknown_type_not_in_list_uses_project_text():
    warn = m.role_type_warn(
        _agent_payload(subagent_type="totally-unknown-role-xyz", description="fable: что-то")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "нет роль-файла" in warn
    if MODULE_UNDER_TEST != "live":
        assert "заведи роль-файл" in warn
        assert "не известный списку" in warn  # промах списка -- Р-А3


@_SIBLING_ONLY
def test_a_k7_builtin_match_is_case_insensitive():
    for variant in ("GENERAL-PURPOSE", "General-Purpose", " general-purpose "):
        warn = m.role_type_warn(
            _agent_payload(subagent_type=variant, description="sonnet: x")
        )
        assert "это ожидаемо" in warn, f"variant={variant!r}"


@_SIBLING_ONLY
def test_a_k7_mismatch_case_unaffected_by_split():
    # Регресс: MISMATCH-ветка (роль-файл найден, семейство разошлось)
    # не тронута расщеплением -- дословно старый текст.
    warn = m.role_type_warn(
        _agent_payload(subagent_type="builder", description="opus: правь файл")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "opus" in warn
    assert "builder" in warn
    assert "sonnet" in warn
    assert "нет роль-файла" not in warn


# --- четыре живых пина tools/test_dispatch_gate.py, которые ОБЯЗАНЫ
# остаться зелёными при посадке (см. "Что ломается" отчёта билдера) ---


@_SIBLING_ONLY
def test_a_k7_landing_pin_general_purpose_no_class_label():
    warn = m.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="opus: ревью диффа")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "general-purpose" in warn
    assert "нет роль-файла" in warn
    assert "класс general-purpose" not in warn


@_SIBLING_ONLY
def test_a_k7_landing_pin_arbitrary_unknown_role():
    warn = m.role_type_warn(
        _agent_payload(subagent_type="totally-unknown-role", description="fable: что-то")
    )
    assert "ROLE-TYPE WARN" in warn
    assert "totally-unknown-role" in warn
    assert "нет роль-файла" in warn


@_SIBLING_ONLY
def test_a_k7_landing_pin_c10_builtin_after_judge_match():
    warn_judge = m.role_type_warn(
        _agent_payload(subagent_type="judge", description="sonnet: приёмка диспатча")
    )
    assert warn_judge == ""
    warn_unknown = m.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="sonnet: приёмка диспатча")
    )
    assert "ROLE-TYPE WARN" in warn_unknown
    assert "нет роль-файла" in warn_unknown


@_SIBLING_ONLY
def test_a_k7_landing_pin_n6_builtin_harness_types():
    for builtin_type in ("Explore", "statusline-setup"):
        warn = m.role_type_warn(
            _agent_payload(subagent_type=builtin_type, description="sonnet: сделай что-то")
        )
        assert "ROLE-TYPE WARN" in warn
        assert "нет роль-файла" in warn


@_SIBLING_ONLY
def test_a_k7_landing_pin_agents_dir_exists_but_empty_warns_project(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "AGENTS_DIR", tmp_path)
    warn = m.role_type_warn(_agent_payload(subagent_type="builder", description="opus: x"))
    assert "ROLE-TYPE WARN" in warn
    assert "нет роль-файла" in warn


# =======================================================================
# RENAME BLOCK_MESSAGE_NO_MANIFEST -- правило трёх, провенанс в хвосте.
# =======================================================================


@_SIBLING_ONLY
def test_rename_block_message_names_what_is_wrong():
    assert "given/owns" in m.BLOCK_MESSAGE_NO_MANIFEST


@_SIBLING_ONLY
def test_rename_block_message_names_what_breaks():
    assert "пересекается с параллельными писателями" in m.BLOCK_MESSAGE_NO_MANIFEST
    assert "без корзины и" in m.BLOCK_MESSAGE_NO_MANIFEST


@_SIBLING_ONLY
def test_rename_block_message_names_the_fix_action():
    assert "Дано:" in m.BLOCK_MESSAGE_NO_MANIFEST
    assert "owns:" in m.BLOCK_MESSAGE_NO_MANIFEST
    assert "один переход" in m.BLOCK_MESSAGE_NO_MANIFEST
    assert "строго инлайн" in m.BLOCK_MESSAGE_NO_MANIFEST


@_SIBLING_ONLY
def test_rename_block_message_provenance_is_at_the_tail():
    assert m.BLOCK_MESSAGE_NO_MANIFEST.rstrip().endswith("(правило 11/D-0073)")


def test_rename_exit_code_behavior_unchanged_no_manifest_blocks():
    exit_code, message = m.decide(
        _builder_payload("DoD: тест зелёный. Правь файл x.py по спеке.", description="sonnet: x")
    )
    assert exit_code == 2
    live_exit, _ = _live.decide(
        _builder_payload("DoD: тест зелёный. Правь файл x.py по спеке.", description="sonnet: x")
    )
    assert exit_code == live_exit


def test_rename_exit_code_behavior_unchanged_with_manifest_passes():
    prompt = (
        "DoD: тест зелёный, witness приложен. Дано: репо целиком. "
        "owns: tools/x.py. Создай файл x.py."
    )
    exit_code, message = m.decide(_builder_payload(prompt, description="sonnet: x"))
    assert exit_code == 0, message


# =======================================================================
# DoD п.2 -- exit_code сиблинга == exit_code живого на матрице форм,
# ЗАТРАГИВАЮЩИХ ИМЕННО узел A (given-path/role-type тексты не влияют на
# exit_code -- decide() их не читает).
# =======================================================================

_EXIT_CODE_MATRIX = [
    ("ak1_owns_sibling_prose", _ak1_prompt_owns_and_prose(), "sonnet: x"),
    (
        "ak2_run_line_token",
        f"DoD: критерии приёмки — тест, witness приложен.\nДано: репо целиком.\n"
        f"python {_AK2_TOKEN} -q\nowns:\n- D:/repo/tools/x.py\n",
        "sonnet: x",
    ),
    (
        "ak3_template_token",
        f"DoD: критерии приёмки — тест, witness приложен.\nДано: репо целиком.\n"
        f"Схема: {_AK3_TOKEN}.\nowns:\n- D:/repo/tools/x.py\n",
        "sonnet: x",
    ),
    (
        "ak4_non_goals_token",
        f"DoD: критерии приёмки — тест, witness приложен.\nДано: репо целиком.\n"
        f"## НЕ-ЦЕЛИ\nНЕ трогать {_AK4_TOKEN}.\nowns:\n- D:/repo/tools/x.py\n",
        "sonnet: x",
    ),
    (
        "role_type_builtin_general_purpose",
        "DoD: тест зелёный.",
        "opus: x",
    ),
    (
        "no_manifest_still_blocks",
        "DoD: тест зелёный. Правь файл x.py.",
        "sonnet: x",
    ),
]


@pytest.mark.parametrize("name,prompt,description", _EXIT_CODE_MATRIX, ids=[n for n, _, _ in _EXIT_CODE_MATRIX])
def test_exit_code_equality_sibling_vs_live(name, prompt, description):
    payload = _builder_payload(prompt, description=description)
    sib_exit, _ = m.decide(payload)
    live_exit, _ = _live.decide(payload)
    assert sib_exit == live_exit, f"{name}: sibling={sib_exit} live={live_exit}"


# =======================================================================
# А-К8: замер снятого, КОНТРФАКТ (Р-А4) -- исторический корпус, сегодняшний
# гейт. Прогон-скрипт ВНУТРИ батареи (не файл в docs/).
# =======================================================================

_AK8_NAMED_TOKENS = (
    "tools/negative_lint_md.py",
    "tools/session_context_autoboot.py",
    "PROCESS/checks/CHK-NN.md",
)


def _ak8_measure_counterfactual(transcripts_dir: Path):
    files = enumerate_corpus_files(transcripts_dir)
    removed_by_rule = {
        "template(А-К3)": [],
        "owns(А-К1)": [],
        "non_goals(А-К4)": [],
        "run_line(А-К2)": [],
    }
    total_candidates = 0
    patterns = (m.GIVEN_ABS_WIN_PATH_RE, m.GIVEN_REPO_REL_PATH_RE)
    for f in files:
        if is_sidechain_file(f):
            continue
        try:
            fh = open(f, "r", encoding="utf-8-sig", errors="replace", newline=None)
        except OSError:
            continue
        with fh:
            for raw_ln in fh:
                ln = raw_ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict) or rec.get("type") != "assistant":
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    if item.get("name") not in ("Task", "Agent"):
                        continue
                    inp = item.get("input")
                    if not isinstance(inp, dict):
                        continue
                    prompt = inp.get("prompt")
                    if not isinstance(prompt, str) or not prompt:
                        continue
                    candidates = m.extract_given_candidates(prompt)
                    if not candidates:
                        continue
                    total_candidates += len(candidates)
                    templated = {tok for tok, _ in candidates if m._is_template_token(tok)}
                    occ = m._token_occurrence_sections(prompt, patterns)
                    given_tokens = m._tokens_any_in_section(occ, "given")
                    owns_declared = m._tokens_any_in_section(occ, "owns")
                    non_goals_confined = m._tokens_all_in_section(occ, "non-goals")
                    run_line_confined = m._tokens_all_after_launch_word(prompt, patterns)
                    for tok, _is_abs in candidates:
                        if tok in templated:
                            removed_by_rule["template(А-К3)"].append(tok)
                            continue
                        if tok in given_tokens:
                            continue
                        if tok in owns_declared:
                            removed_by_rule["owns(А-К1)"].append(tok)
                        elif tok in non_goals_confined:
                            removed_by_rule["non_goals(А-К4)"].append(tok)
                        elif tok in run_line_confined:
                            removed_by_rule["run_line(А-К2)"].append(tok)
    return removed_by_rule, total_candidates


@_SIBLING_ONLY
def test_a_k8_counterfactual_measurement_snatched_over_zero_and_names_known_token():
    transcripts_dir = _default_transcripts_dir()
    if not transcripts_dir.exists():
        pytest.skip(f"корпус отсутствует: {transcripts_dir}")
    removed_by_rule, total_candidates = _ak8_measure_counterfactual(transcripts_dir)
    total_snatched = sum(len(v) for v in removed_by_rule.values())
    print("=== А-К8, КОНТРФАКТ: сегодняшний гейт (узел A) о старых промптах ===")
    all_removed_names = set()
    for rule, toks in removed_by_rule.items():
        uniq = sorted(set(toks))
        print(f"  {rule}: снято {len(toks)} (уникальных {len(uniq)})")
        for t in uniq[:15]:
            print(f"    - {t}")
        all_removed_names.update(toks)
    print(f"  снято всего: {total_snatched} (кандидатов всего в корпусе: {total_candidates})")
    hit = sorted(all_removed_names & set(_AK8_NAMED_TOKENS))
    print(f"  поимённые совпадения с перечнем критика {_AK8_NAMED_TOKENS}: {hit}")
    assert total_snatched > 0, "А-К8: снято всего должно быть > 0"
    assert hit, f"А-К8: ни один из {_AK8_NAMED_TOKENS} не снят среди {sorted(all_removed_names)[:30]} -- rejected"


# =======================================================================
# Адверсариальная батарея (представительный срез, R11(f) потолок скоупа).
# =======================================================================


def test_adversarial_1mb_prompt_with_500_tokens_completes_quickly():
    tokens = "\n".join(f"tools/фейк_perf_{i}_нет_такого_файла.py" for i in range(500))
    padding = "x" * (1_000_000 - len(tokens))
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n" + tokens + "\n\nowns:\n- D:/repo/tools/x.py\n\n" + padding
    )
    start = time.perf_counter()
    warn = m.given_path_warn(_builder_payload(prompt))
    elapsed = time.perf_counter() - start
    assert isinstance(warn, str)
    assert elapsed < 10.0, f"1MB/500 tokens took {elapsed:.2f}s"


def test_adversarial_redos_pattern_no_catastrophic_slowdown():
    prompt = "tools/" * 5000 + "a" * 5000  # без точки -- не матчит extension
    start = time.perf_counter()
    warn = m.given_path_warn(_builder_payload(prompt))
    elapsed = time.perf_counter() - start
    assert warn == ""
    assert elapsed < 5.0, f"ReDoS-паттерн took {elapsed:.2f}s"


def test_adversarial_crlf_line_endings_non_goals_section_still_detected():
    prompt = (
        "## \u041d\u0415-\u0426\u0415\u041b\u0418\r\n"
        f"\u041d\u0415 \u0442\u0440\u043e\u0433\u0430\u0442\u044c {_AK4_TOKEN}.\r\n"
    )
    warn = m.given_path_warn(_builder_payload("DoD: тест зелёный, witness приложен.\nДано: репо целиком.\n" + prompt + "\nowns:\n- D:/repo/tools/x.py\n"))
    assert _AK4_TOKEN not in warn


def test_adversarial_form_sdachi_inside_fence_without_owns_declaration_still_checked():
    # "Форма сдачи" ВНУТРИ фенса, БЕЗ owns-декларации токена -- поведение
    # НАЗВАНО, не унаследовано молча (Ф12): без owns-объявления А-К1 не
    # освобождает (см. test_a_k1_residual...), фенс тут ни при чём.
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n\n"
        "Дано: репо целиком.\n\n"
        "```\n"
        f"Форма сдачи: сиблинг {_AK1_SIBLING_TOKEN}\n"
        "```\n\n"
        "owns:\n- D:/repo/tools/other.py\n"
    )
    missing = m.find_missing_given_paths(prompt, _REPO_ROOT)
    assert _AK1_SIBLING_TOKEN in missing


def test_adversarial_description_claude_prefix_role_type_silent():
    warn = m.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="claude: сделай что-то")
    )
    assert warn == ""


def test_adversarial_description_without_model_prefix_role_type_silent():
    warn = m.role_type_warn(
        _agent_payload(subagent_type="general-purpose", description="fix the bug")
    )
    assert warn == ""
