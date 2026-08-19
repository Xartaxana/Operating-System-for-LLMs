"""tools/test_mechanism_gate_md.py -- батарея сиблинга tools/mechanism_
gate_md.py (этап 2, партия 2, узел E, t-530 / docs/tasks/2026-08-19_
scanner-party2-spec.md). MODULE UNDER TEST переключается переменной
окружения MODULE_UNDER_TEST (образец конвенции F61_TARGET, уже применённой
формы tools/test_negative_lint_md.py :43-64 / tools/test_owns_gate_md.py):
default -> сиблинг tools/mechanism_gate_md.py (region-aware);
MODULE_UNDER_TEST=live -> живой tools/mechanism_gate.py БЕЗ единой правки
-- используется здесь ТОЛЬКО как цель негативного контроля дискриминации:
region-специфичные assert'ы, зелёные на сиблинге, обязаны стать КРАСНЫМИ
на живую (нерегионную) цель.

Модуль резолвится через importlib.util по явному пути (сиблинг и живой
файл -- РАЗНЫЕ имена, mechanism_gate_md.py / mechanism_gate.py).

Существующий tools/test_mechanism_gate.py (батарея живого файла) НЕ
ТРОГАЕТСЯ этим диспатчем -- прогоняется отдельно как подтверждение "живой
не задет" (DoD п.3), и ЕЩЁ РАЗ -- equivalence-run -- на КОПИИ дерева с
сиблингом под живым именем (DoD п.4).

Узел E6 (живая красно-зелёная пара на git clone) -- ОТДЕЛЬНАЯ процедура,
НЕ pytest-тест этого файла (git commit side-effects не совместимы с
изолированной pytest-батареей) -- см. отчёт билдера t-530 за 4 прогона
дословно (exit-коды + stderr).

Run (дефолт, сиблинг):        python -m pytest tools/test_mechanism_gate_md.py -q
Контр-прогон (дискриминация): MODULE_UNDER_TEST=live python -m pytest
    tools/test_mechanism_gate_md.py -q -k discrimination
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    if MODULE_UNDER_TEST == "live":
        return TOOLS_DIR / "mechanism_gate.py"
    sibling = TOOLS_DIR / "mechanism_gate_md.py"
    return sibling if sibling.exists() else TOOLS_DIR / "mechanism_gate.py"


SCRIPT = _resolve_script_path()


def _load_module():
    alias = f"mechanism_gate_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mg = _load_module()

_REGION_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live",
    reason="region API (mg.scan/_classify/_maybe_scan/_skip_declared/"
    "_region_filtered_tier_declarations) exists only on the sibling; "
    "MODULE_UNDER_TEST=live targets tools/mechanism_gate.py verbatim, "
    "which has none of it",
)

CONFIG_SAMPLE = """
roles:
  lead:
    subscription:
      model: claude-fable-5
    api:
      provider:
      model:
      api_key_env:
"""


# ---------------------------------------------------------------------
# Регрессия базового поведения (оба таргета -- живой файл не задет).
# ---------------------------------------------------------------------


def test_parse_axes_follows_the_map():
    assert mg.parse_axes("## Ось 1 — X\n## Ось 6 — Y\n") == [1, 6]


def test_mechanism_paths_filters_prefixes_with_boundary():
    staged = ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md", "gateway/metrics.py"]
    assert mg.mechanism_paths(staged) == ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"]


def test_decide_merge_and_non_mechanism_commits_pass():
    code, _ = mg.decide(msg="Merge branch 'x'", block_extra="",
                        staged=["CLAUDE.md"], map_text="## Ось 1 —\n", merging=True)
    assert code == 0
    code, _ = mg.decide(msg="chore: телеметрия", block_extra="",
                        staged=["gateway/metrics.py"], map_text="## Ось 1 —\n")
    assert code == 0


def test_decide_fails_closed_without_map_or_axes():
    code, reason = mg.decide(msg="feat: X", block_extra="", staged=["CLAUDE.md"], map_text=None)
    assert code == 1 and "fail-closed" in reason


def test_explicit_skip_line_in_prose_passes():
    code, _ = mg.decide(
        msg="docs: правка опечатки\n\nоси: не-механизм (опечатка в правиле 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 — Деплои\n")
    assert code == 0


def test_axis_block_satisfies_gate():
    code, _ = mg.decide(
        msg="feat: механизм X\n\nось 1: покрыта — оба деплоя",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0


def test_find_tier_declarations_returns_all_lines_region_blind():
    # find_tier_declarations() -- region-БЛИНД, байт-в-байт (см. докстринг
    # mechanism_gate_md.py "ALL-MUST-PASS") -- НЕ изменилась на сиблинге.
    msg = "feat: X\n\ntier: sonnet\n\nSome other text\ntier: fable\n"
    assert mg.find_tier_declarations(msg) == ["sonnet", "fable"]


def test_decide_full_tier_fable_default_passes():
    code, _ = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 0


def test_decide_full_tier_mismatch_fails():
    code, reason = mg.decide_full(
        msg="feat: механизм X\n\nось 1: покрыта\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "не lead" in reason


# ---------------------------------------------------------------------
# E5: осевые строки find_missing() -- ЯВНО НЕ фильтруются region'ом
# (Ф7, отложено -- см. докстринг mechanism_gate_md.py "ОСЕВЫЕ СТРОКИ").
# ---------------------------------------------------------------------


def test_e5_axis_line_inside_fence_still_counts_documented_non_goal():
    # Осевой блок ВНУТРИ фенса -- НЕ фильтруется (сознательный не-цель):
    # ОБА таргета (сиблинг и живой) дают ОДИНАКОВЫЙ результат -- НЕ
    # дискриминация, регресс-пин объёма ЭТОЙ задачи.
    msg = "feat: механизм X\n\n```\nось 1: покрыта — оба деплоя\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0


# ---------------------------------------------------------------------
# E1/E2: НЕГАТИВНЫЙ КОНТРОЛЬ ДИСКРИМИНАЦИИ -- skip-строка ВНУТРИ фенса/
# цитаты БОЛЬШЕ НЕ гасит гейт на сиблинге; гасит (дыра) на живом.
# ---------------------------------------------------------------------


def test_discrimination_e1_skip_line_inside_fence_does_not_pass_the_gate():
    """С регион-фильтром (дефолт, сиблинг) -- assert ниже ЗЕЛЁН: skip-
    строка внутри тройного backtick-примера НЕ засчитывается, гейт
    ТРЕБУЕТ настоящий осевой блок -> code=1. Без регион-фильтра
    (MODULE_UNDER_TEST=live python -m pytest tools/test_mechanism_gate_md.py
    -q -k test_discrimination_e1) живой mechanism_gate.py гасит гейт на
    ЦИТИРУЕМОМ примере синтаксиса -- тот же assert становится КРАСНЫМ
    (остаточная дыра §13 п.3 родительской спеки, ключ E1)."""
    msg = (
        "docs: показываю пример формата отказа читателю\n\n"
        "```\n"
        "оси: не-механизм (пример синтаксиса для документации)\n"
        "```\n"
    )
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 1
    assert "fail-closed" not in reason  # карта есть -- отказ по осевому блоку, не по карте
    assert "Осевой блок" in reason


def test_e2_blockquote_skip_line_structurally_never_matches_skip_re_either_target():
    """НАХОДКА (эмпирическая, правило 3 роли builder), а не заявленная
    дискриминация: SKIP_RE = r"^\\s*оси\\s*:\\s*не-механизм\\s*\\(" несёт
    ЯКОРЬ "^\\s*" (ТОЛЬКО пробельные символы перед литералом "оси") --
    цитата `>` (md_regions._QUOTE_RE = "^ {0,3}>( ?)") добавляет символ
    ">" ПЕРЕД содержимым строки, который ЛОМАЕТ ЭТОТ ЯКОРЬ структурно,
    БЕЗ УЧАСТИЯ региона вообще -- "> оси: не-механизм (...)" НЕ матчит
    SKIP_RE ни на живом файле (эмпирически проверено ниже, control), ни
    на сиблинге -- ОБА таргета дают ОДИНАКОВЫЙ код 1 (отказ по осевому
    блоку) ПО РАЗНЫМ причинам: живой -- потому что подстроки "оси:" нет
    В НАЧАЛЕ строки вовсе; сиблинг -- по ТОЙ ЖЕ причине (регион тут
    попросту не участвует, до него дело не доходит). Симметрично для
    TIER_LINE_RE. Заявленная в спеке узла E формулировка "строка отказа/
    tier в фенсе ИЛИ цитате" покрывается ФЕНСОМ ГЕНУИННО (E1/E4 -- фенс
    НЕ добавляет префиксный символ к содержимым строкам, оставляя якорь
    целым, регион ГЕНУИННО меняет вердикт) и ЦИТАТОЙ ЗАЩИТНО/мёртвым
    кодом для ЭТИХ ДВУХ конкретных regex'ов КАК ОНИ НАПИСАНЫ СЕГОДНЯ --
    _EXCLUDED_KINDS всё равно несёт "blockquote" буквально по тексту
    спеки (безвредно, задокументировано здесь явно как находка, не
    молчаливый пробел)."""
    msg = "docs: цитирую формат отказа\n\n> оси: не-механизм (пример цитаты)\n"
    # Позитивный контроль (гигиена п.6): та же форма без региона вовсе --
    # прямая проверка regex'а, не через decide() (доказывает: причина --
    # сам якорь, не отсутствие/наличие региона).
    assert mg.SKIP_RE.search(msg) is None
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 1
    assert "Осевой блок" in reason


# ---------------------------------------------------------------------
# E4: tier-строка ВНУТРИ фенса -- "нет строки tier", а не проходит.
# ---------------------------------------------------------------------


def test_discrimination_e4_tier_line_inside_fence_gives_no_tier_line_error():
    """С регион-фильтром -- tier-строка внутри фенса НЕ засчитывается,
    ошибка ИМЕННО "нет строки tier" (не "ярус не lead"). На живой цели
    (MODULE_UNDER_TEST=live -k test_discrimination_e4) фенсированная
    tier-строка ЗАСЧИТЫВАЕТСЯ -- code становится 0 (проходит), КРАСНЫЙ
    контроль (ключ E4)."""
    msg = (
        "feat: механизм X\n\nось 1: покрыта\n"
        "Пример формата декларации яруса:\n```\ntier: fable\n```\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "Нет строки" in reason


# ---------------------------------------------------------------------
# E3: ALL-must-pass считает ТОЛЬКО нецитированные tier-строки -- цитата-
# спуфер рядом с настоящей строкой не портит и не подменяет вердикт.
# ---------------------------------------------------------------------


def test_discrimination_e3_fenced_spoofer_wrong_tier_ignored_missing_real_line_rejects():
    """ALL-MUST-PASS считает ТОЛЬКО нецитированные tier-строки (ключ E3):
    фенсированная строка с ЗАВЕДОМО НЕПОДХОДЯЩИМ значением ("sonnet",
    привязка -- дефолт fable) СОСЕДСТВУЕТ с ОТСУТСТВИЕМ настоящей прозной
    tier-строки. На сиблинге фенсированная "sonnet" НЕ засчитывается ->
    список деклараций пуст -> code=1, "Нет строки" (не "ярус не lead").
    На живой цели (MODULE_UNDER_TEST=live -k test_discrimination_e3)
    фенсированная строка ЗАСЧИТЫВАЕТСЯ как настоящая, ярус "sonnet" не
    совпадает с fable -> code=1 ТОЖЕ, НО текст ошибки -- "ярус не lead",
    ОТЛИЧИМЫЙ от "Нет строки" (см. t-278 текстовое различие живого
    файла) -- КРАСНЫЙ контроль на ТЕКСТЕ причины отказа, не на code."""
    msg = (
        "feat: механизм X\n\nось 1: покрыта\n"
        "Пример формата (для документации):\n```\ntier: sonnet\n```\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 1
    assert "Нет строки" in reason
    assert "не lead" not in reason


def test_discrimination_e3b_mixed_fenced_wrong_spoofer_and_real_prose_correct_tier():
    # ЭМПИРИЧЕСКИ проверено (не заявлено заранее): ТА ЖЕ фенсированная
    # "неверная" строка, НО с настоящей прозаической ПРАВИЛЬНОЙ tier-
    # строкой ТОЖЕ присутствующей -- ALL-must-pass на сиблинге считает
    # ТОЛЬКО нецитированную ("fable" в прозе) -> code=0. Это ТОЖЕ
    # дискриминация (не "не дискриминация", как можно было бы
    # предположить по аналогии с E5/block_extra): на живой цели ОБЕ
    # строки (sonnet-в-фенсе И fable-в-прозе) считаются равноправно, а
    # t-278 "ALL must pass" отклоняет коммит, если ХОТЬ ОДНА найденная
    # строка не совпадает с привязкой -- sonnet-в-фенсе один этот факт
    # достаточен для отказа, ДАЖЕ когда рядом стоит правильная -- code=1
    # на живом (см. MODULE_UNDER_TEST=live -k test_discrimination_e3b).
    msg = (
        "feat: механизм X\n\nось 1: покрыта\n"
        "Пример формата (для документации):\n```\ntier: sonnet\n```\n"
        "tier: fable\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n",
        config_text=None)
    assert code == 0, reason


# ---------------------------------------------------------------------
# Block_extra не сканируется (Ф8) -- дифф-текст с "оси"/"tier"-подобными
# фенс-обёртками не даёт региону повод его сканировать вовсе.
# ---------------------------------------------------------------------


def test_block_extra_fenced_axis_text_not_region_scanned_documented_non_goal():
    # block_extra несёт осевую строку внутри фенс-подобного diff-текста —
    # find_missing() читает её как обычно (block_extra region'ом не
    # трогается вовсе, Ф8) — ОБА таргета одинаковы, не дискриминация.
    code, _ = mg.decide(
        msg="feat: механизм X", block_extra="+```\n+ось 1: покрыта\n+```\n",
        staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0


# ---------------------------------------------------------------------
# E7: не-механизменный / merge коммит -- 0 вызовов scan (И-1).
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_e7_scan_not_called_on_non_mechanism_commit(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide_full(
        msg="```\nоси: не-механизм (проверка)\n```\n", block_extra="",
        staged=["gateway/metrics.py"], map_text="## Ось 1 —\n", config_text=None)
    assert calls["n"] == 0


@_REGION_ONLY
def test_e7_scan_not_called_on_merge_commit(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide_full(
        msg="Merge branch 'x'\n```\ntier: fable\n```\n", block_extra="",
        staged=["CLAUDE.md"], map_text="## Ось 1 —\n", config_text=None, merging=True)
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_not_called_without_marker_hint(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    # маркер-хинт "оси"/"tier" отсутствует вовсе -- скан не вызывается,
    # даже несмотря на ">"/"`" в тексте.
    mg.decide(msg="feat: X\n> просто цитата без ключевых слов `code`\n",
               block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_not_called_without_region_chars(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide(msg="feat: X\n\nось 1: покрыта\ntier: fable\n",  # нет `>~ вовсе
               block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_called_exactly_once_per_decide_full_call(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    msg = "feat: X\n\nось 1: покрыта\n```\ntier: fable\n```\ntier: fable\n"
    mg.decide_full(msg=msg, block_extra="", staged=["CLAUDE.md"],
                    map_text="## Ось 1 —\n", config_text=None)
    # ОДИН вызов на весь decide_full (переиспользован skip- И tier-
    # проверками) -- см. докстринг модуля "И-1"/_maybe_scan.
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# E8: И-0 -- отказ md_regions -> сиблинг ведёт себя КАК ЖИВОЙ файл
# БАЙТ-В-БАЙТ, включая "цитированный skip снова глушит" (объявленный
# фоллбек, не новый путь кода).
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_e8_i0_scan_raises_falls_back_to_live_quoted_skip_silences_gate(monkeypatch):
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(mg, "scan", _broken_scan)
    msg = "docs: пример\n\n```\nоси: не-механизм (пример синтаксиса)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    # И-0: фильтр -- но-оп, цитируемый skip СНОВА глушит гейт (тот же
    # остаточный баг живого файла) -- code=0, НЕ 1.
    assert code == 0


@_REGION_ONLY
def test_e8_i0_scan_degraded_falls_back_to_live_quoted_skip_silences_gate(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(mg, "scan", lambda text: _FakeResult())
    # Фенс, не цитата (см. test_e2_blockquote_skip_line_structurally_never_
    # matches_skip_re_either_target -- цитата структурно не матчит SKIP_RE
    # вообще, не годится как И-0 зонд; фенс не ломает якорь, region -- и
    # только region -- решает, засчитывается ли строка).
    msg = "docs: пример\n\n```\nоси: не-механизм (пример)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0


@_REGION_ONLY
def test_e8_i0_scan_module_absent_falls_back_to_live_quoted_skip_silences_gate(monkeypatch):
    monkeypatch.setattr(mg, "scan", None)
    msg = "docs: пример\n\n```\nоси: не-механизм (пример)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Ось 1 —\n")
    assert code == 0
