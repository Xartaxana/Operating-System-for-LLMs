"""tools/test_owns_gate_retry.py -- батарея сиблинга tools/owns_gate_retry.py
(узел I, 2026-08-25, t-587 живой случай, docs/tasks/2026-08-25_
warn-population-class.md "ТРЕТИЙ ЭКЗЕМПЛЯР ПОДКЛАССА I"): пересдача
после `rejected` (R6 CLAUDE.md кита её ПРЕДПИСЫВАЕТ) пересекается САМА
С СОБОЙ по построению -- реестр logs/owns_registry.jsonl пишет НАЧАЛО
диспатча и никогда не узнаёт о его завершении. Фикс -- К1 спеки:
запись реестра ИСКЛЮЧАЕТСЯ из warn целиком, если она (а) той же сессии
И (б) её множество owns -- подмножество (в т.ч. равное) множества owns
нового диспатча.

MODULE_UNDER_TEST переключает цель (та же конвенция, что tools/
test_owns_gate_md.py / tools/test_dispatch_gate_md.py уже несут):
пусто/не задано -> сиблинг tools/owns_gate_retry.py (фикс узла I), ЕСЛИ
он существует, иначе МОЛЧА живой tools/owns_gate.py (temporal-край,
поведение неизменно); MODULE_UNDER_TEST=live -> живой tools/owns_gate.py
БЕЗ единой правки -- используется ТОЛЬКО как цель негативного контроля
дискриминации: тесты, имя которых содержит "discrimination", зелёные на
сиблинге, ОБЯЗАНЫ быть КРАСНЫМИ на живой (нерегионной, без фикса узла I)
цели -- живой код не различает пересдачу и параллельный конфликт вовсе,
поэтому те же сценарии на нём warn'ят; ЛЮБОЕ ДРУГОЕ непустое значение
(например MODULE_UNDER_TEST=sibling) -- сиблинг ЗАПРОШЕН ЯВНО, при его
отсутствии ГРОМКИЙ КРАС (pytest.fail, называющий запрошенный путь), не
тихая подмена живым (F1, ФИКС-РАУНД docs/tasks/2026-08-25_queue8-
mechbatch-spec.md).

Существующий tools/test_owns_gate.py (батарея живого файла) НЕ
ТРОГАЕТСЯ этим диспатчем -- прогоняется отдельно как подтверждение
"живой не задет".

Run (дефолт, сиблинг):        python -m pytest tools/test_owns_gate_retry.py -q
Контр-прогон (дискриминация): MODULE_UNDER_TEST=live python -m pytest
    tools/test_owns_gate_retry.py -q -k discrimination
"""

import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # f61-форма (образец test_owns_gate_md.py._resolve_script_path):
    # default (MODULE_UNDER_TEST пуст) -- сиблинг, ЕСЛИ он существует,
    # иначе живой файл, МОЛЧА (поведение как сегодня). Сиблинг ЗАПРОШЕН
    # ЯВНО (MODULE_UNDER_TEST задан и НЕ "live") -- при отсутствии
    # сиблинга ГРОМКИЙ КРАС, не тихая подмена живым (F1, ФИКС-РАУНД
    # docs/tasks/2026-08-25_queue8-mechbatch-spec.md).
    live = TOOLS_DIR / "owns_gate.py"
    if MODULE_UNDER_TEST == "live":
        return live
    sibling = TOOLS_DIR / "owns_gate_retry.py"
    if MODULE_UNDER_TEST == "":
        return sibling if sibling.exists() else live
    if not sibling.exists():
        pytest.fail(
            f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested sibling "
            f"{sibling} but it does not exist -- no silent live fallback (F1)"
        )
    return sibling


SCRIPT = _resolve_script_path()


def _load_module():
    alias = f"owns_gate_retry_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module()

_NOW = datetime(2026, 8, 25, 12, 0, 0)


def _write_registry_line(path: Path, ts: str, session_key, cwd: str, description: str, owns) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": ts, "session_key": session_key, "cwd": cwd, "description": description, "owns": owns}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _writing_payload(owns_text: str, session_id="s-1", cwd="D:\\repo", description="sonnet: write") -> dict:
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        f"owns: {owns_text}.\n"
        "Правь файлы."
    )
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": description},
        "session_id": session_id,
        "cwd": cwd,
    }


def _ts(now: datetime) -> str:
    return now.strftime(m._TS_FORMAT)


# ---------------------------------------------------------------------
# К1 -- пересдача той же сессии, owns-подмножество/равенство -- warn
# ИСКЛЮЧЁН. Дискриминационные тесты: КРАСНЫЕ на живом owns_gate.py
# (живой код не знает о сессии/подмножестве вовсе -- warn всегда).
# ---------------------------------------------------------------------


def test_discrimination_same_session_superset_owns_excluded_t587_real_case(tmp_path):
    # Дословное воспроизведение живого случая t-587: attempt 1 owns
    # {session_context_layer_a.py, test_session_context_layer_a.py,
    # test_session_context_autoboot.py}, attempt 2 -- ТЕ ЖЕ три плюс
    # четвёртый test_session_context.py, ТА ЖЕ session_key координатора.
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-lead-1", "D:\\repo", "sonnet: attempt 1 (rejected)",
        [
            "D:\\repo\\tools\\session_context_layer_a.py",
            "D:\\repo\\tools\\test_session_context_layer_a.py",
            "D:\\repo\\tools\\test_session_context_autoboot.py",
        ],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\session_context_layer_a.py, "
        "D:\\repo\\tools\\test_session_context_layer_a.py, "
        "D:\\repo\\tools\\test_session_context_autoboot.py, "
        "D:\\repo\\tools\\test_session_context.py",
        session_id="s-lead-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None, "пересдача т-587 attempt 2 против attempt 1 -- НЕ конфликт (К1)"


def test_discrimination_same_session_equal_owns_excluded_no_expansion(tmp_path):
    # Пересдача БЕЗ расширения owns -- множества РАВНЫ (edge спеки:
    # "равны -- это подмножество, исключается").
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: attempt 1 (rejected)",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None


def test_discrimination_same_session_subset_owns_different_case_and_separator(tmp_path):
    # Edge спеки: регистр/разделители -- вложенность по normalize_path,
    # не по строковому равенству.
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: attempt 1 (rejected)",
        ["D:/REPO/TOOLS/a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# К2 (ГЛАВНЫЙ тест батареи) -- частичное пересечение, НИ ОДНО множество
# не вложено в другое -- остаётся конфликтом. НЕ дискриминационный:
# живой код тоже warn'ит здесь (он warn'ит на ЛЮБОЕ пересечение) --
# доказывает, что фикс не выключил слой целиком.
# ---------------------------------------------------------------------


def test_partial_overlap_same_session_still_warns_not_full_subset(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: prior write",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    # Новый диспатч владеет {b.py, c.py} -- пересекается по b.py, но НИ
    # ОДНО множество не вложено в другое ({a,b} не подмножество {b,c} и
    # наоборот) -- НАСТОЯЩИЙ конфликт, warn обязан остаться.
    payload = _writing_payload(
        "D:\\repo\\tools\\b.py, D:\\repo\\tools\\c.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


# ---------------------------------------------------------------------
# Д1/Д2 -- ОСТАТОЧНЫЕ ДЫРЫ признака К1 (найдены координатором 2026-08-25,
# ПОСЛЕ первой сдачи узла, спека К1 их не называла). Оба теста -- ПИНЫ
# ТЕКУЩЕГО поведения (warn ложно срабатывает), а НЕ регресс-проверки
# фикса -- см. блок докстринга "УЗЕЛ I" в owns_gate_retry.py, абзацы
# "Д1" и "Д2" за полное обоснование, почему поведение НЕ меняется.
# НЕ ДИСКРИМИНАЦИОННЫЕ: оба пина утверждают ОДИНАКОВОЕ поведение и на
# сиблинге, и на живом файле (признак К1 в обоих мирах не покрывает эти
# случаи) -- дискриминационный прогон им не положен, красноты на живом
# таргете здесь быть не должно.
# ---------------------------------------------------------------------


def test_d1_narrowing_retry_residual_gap_still_warns_documented_limitation(tmp_path):
    # Легальный случай: attempt 2 СУЖАЕТ owns после rejected (владеет
    # {a.py} -- строгим ПОДМНОЖЕСТВОМ owns attempt 1 {a.py, b.py}), ТА
    # ЖЕ сессия. owns ЗАПИСИ ({a,b}) НЕ подмножество owns НОВОГО
    # диспатча ({a}) -- К1 не срабатывает, warn ложно остаётся.
    # Остаточная дыра, названа в УЗЛЕ I (Д1) -- поведение НЕ меняется
    # нарочно (расширение К1 сделало бы его неотличимым от К2).
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: attempt 1 (rejected, шире)",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "остаточная дыра Д1: сужающая пересдача ложно warn'ит -- ожидаемо, названо в УЗЛЕ I"
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


def test_d2_cross_session_retry_residual_gap_still_warns_documented_limitation(tmp_path):
    # Легальный случай: сессия-координатор умерла между attempt 1 и
    # attempt 2, НОВАЯ сессия пересдаёт ТЕ ЖЕ (или расширенные) owns --
    # session_key ДРУГОЙ, хотя это та же логическая задача. К3 (чужая
    # сессия предупреждает ВСЕГДА) отрабатывает буквально -- warn ложно
    # остаётся. Остаточная дыра, названа в УЗЛЕ I (Д2) -- частично
    # гасится окном живости 8ч (запись СТАРШЕ WINDOW_SECONDS уже не
    # "живая"), но ВНУТРИ окна (как здесь -- та же ts) дыра живая.
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-lead-OLD-SESSION", "D:\\repo", "sonnet: attempt 1 (rejected, сессия умерла)",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    # Новая сессия координатора, ТА ЖЕ или РАСШИРЕННАЯ декларация owns
    # (то есть К1 сработал бы, будь session_key тем же).
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py, D:\\repo\\tools\\c.py",
        session_id="s-lead-NEW-SESSION", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "остаточная дыра Д2: межсессионная пересдача ложно warn'ит -- ожидаемо, названо в УЗЛЕ I"
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


# ---------------------------------------------------------------------
# К3 -- чужая сессия предупреждает ВСЕГДА, независимо от вложенности
# (класс D-0060). НЕ дискриминационный: живой код тоже warn'ит здесь.
# ---------------------------------------------------------------------


def test_different_session_subset_owns_still_warns_d0060(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-OTHER", "D:\\repo", "sonnet: другая сессия",
        ["D:\\repo\\tools\\a.py"],
    )
    # Новый диспатч -- superset {a.py, b.py}, но ДРУГАЯ сессия -- не
    # пересдача этой сессии, warn обязан остаться.
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx
    assert "D-0060" in ctx


# ---------------------------------------------------------------------
# Edge: session_key записи отсутствует/None -- считать ЧУЖОЙ сессией
# (fail-closed: предупредить), не своей -- даже при owns-подмножестве.
# ---------------------------------------------------------------------


def test_record_missing_session_key_fail_closed_still_warns(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    # session_key поле ОТСУТСТВУЕТ в записи вовсе.
    entry = {
        "ts": _ts(_NOW), "cwd": "D:\\repo", "description": "sonnet: без session_key",
        "owns": ["D:\\repo\\tools\\a.py"],
    }
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "session_key записи отсутствует -- fail-closed, warn обязан остаться"


def test_record_session_key_none_fail_closed_still_warns(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), None, "D:\\repo", "sonnet: session_key явно None",
        ["D:\\repo\\tools\\a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "session_key записи явно None -- ЧУЖАЯ сессия, warn обязан остаться"


def test_helper_is_own_session_both_none_is_still_false_fail_closed():
    # Прямая проверка на уровне хелпера (спека требует именно этот
    # фланг: "даже если session_key нового диспатча тоже случайно
    # None/отсутствует" -- см. модульный докстринг "УЗЕЛ I",
    # "FAIL-CLOSED НА ЧУЖОЙ СЕССИИ"). Не дискриминационный -- хелпер
    # существует ТОЛЬКО на сиблинге.
    if not hasattr(m, "_is_own_session"):
        return
    rec = {"session_key": None}
    assert m._is_own_session(rec, None) is False
    rec_missing = {}
    assert m._is_own_session(rec_missing, None) is False


# ---------------------------------------------------------------------
# Edge: запись с ПУСТЫМ owns ([] или отсутствует) -- не подмножество
# ничего, и структурно никогда не порождает overlap-совпадение -- тишина.
# ---------------------------------------------------------------------


def test_record_with_empty_owns_list_never_overlaps_stays_silent(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: пустой owns", [],
    )
    payload = _writing_payload("D:\\repo\\tools\\a.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None


def test_helper_is_self_retry_record_empty_owns_returns_false_explicit(tmp_path):
    # Прямая проверка ИМЕННО правила "пустой owns -- не подмножество
    # ничего" на уровне хелпера (не только наблюдаемого эффекта decide()),
    # см. модульный докстринг "УЗЕЛ I", "EDGE -- ПУСТОЙ owns ЗАПИСИ".
    if not hasattr(m, "_is_self_retry_record"):
        # живая цель (MODULE_UNDER_TEST=live) не несёт этот хелпер вовсе --
        # тест относится только к сиблингу.
        return
    rec = {"session_key": "s-1", "owns": []}
    new_owns = {"d:/repo/tools/a.py"}
    assert m._is_self_retry_record(rec, "s-1", new_owns) is False
    rec_missing = {"session_key": "s-1"}
    assert m._is_self_retry_record(rec_missing, "s-1", new_owns) is False


# ---------------------------------------------------------------------
# К4 -- правило трёх: сообщение называет (1) что неизвестно, (2)
# последствие, (3) действие-глагол. Проверяется на СИБЛИНГЕ напрямую
# (не дискриминационный -- живой текст сообщения другой по построению,
# сравнение с живым текстом не имеет смысла для этого узла).
# ---------------------------------------------------------------------


def test_warn_message_rule_of_three_names_unknown_consequence_action(tmp_path):
    if MODULE_UNDER_TEST == "live":
        return  # текст сообщения -- предмет фикса узла I, не живого файла
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: prior write",
        ["D:\\repo\\tools\\a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\c.py", session_id="s-OTHER-2", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    # (1) что неизвестно/неверно -- реестр не знает о завершении.
    assert "не знает" in ctx and "заверш" in ctx
    # (2) последствие (не состояние) -- правки столкнутся/потрутся.
    assert "потр" in ctx or "столкн" in ctx
    # (3) действие-глагол, обращённый к читателю.
    assert "сериализуй" in ctx or "разведи" in ctx


# ---------------------------------------------------------------------
# К5 -- литерал префикса сохранён байт-в-байт (tools/warn_layers.json
# объявляет его для check_liveness в warn_density).
# ---------------------------------------------------------------------


def test_owns_overlap_literal_prefix_preserved_byte_for_byte(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: prior write",
        ["D:\\repo\\tools\\a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\c.py", session_id="s-OTHER-3", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert ctx.startswith("OWNS OVERLAP (warn): ")


# ---------------------------------------------------------------------
# Регресс: батарея живого файла НЕ трогается -- unaffected sanity
# (проверяется отдельным прогоном tools/test_owns_gate.py в witness, не
# здесь; этот тест лишь фиксирует, что сиблинг существует и импортится
# независимо от живого модуля).
# ---------------------------------------------------------------------


def test_sibling_module_loads_independently_of_live_module():
    assert hasattr(m, "decide")
    assert hasattr(m, "_find_overlaps")
