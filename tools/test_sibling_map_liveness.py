"""Детектор потери оси docs/SIBLING_MAP.md -- фикс-батч калибровки №7
(2026-08-14).

Живая карта несёт инвариант, который tools/mechanism_gate.py НЕ
проверяет: заголовки `## Ось N` образуют НЕПРЕРЫВНЫЙ ряд 1..N без
пропусков и без дублей. mg.parse_axes() намеренно ТОЛЕРАНТЕН к
разрывам нумерации -- это закреплённое свойство ПАРСЕРА
(test_parse_axes_follows_the_map_not_a_constant в
tools/test_mechanism_gate.py, трогать нельзя); данный модуль проверяет
ДОКУМЕНТ, не парсер -- он читает живую карту через mg.MAP_PATH и
mg.parse_axes() как есть, не переопределяя и не дублируя их регэксп.

Прецедент: коммит 7bd21cc (2026-08-12, критик-вход AT-BUG-064) внёс
новый буллет оси 6 и молча стёр заголовок `## Ось 7` вместе с пустой
строкой перед ним -- содержимое оси 7 (таблица штаб/staging, правило,
пара D-0091, VG-6, мораторий D-0074) осталось в файле, но без
заголовка читалось как продолжение оси 6, а `mg.parse_axes()` живой
карты возвращал [1,2,3,4,5,6,8,9,10,11,12] -- разрыв, которого никто
не заметил, потому что сам parse_axes() к разрывам толерантен.
"""
from __future__ import annotations

from pathlib import Path

import mechanism_gate as mg


def continuity_error(axes: list[int]) -> str | None:
    """None, если axes -- непрерывный ряд 1..N без пропусков и дублей
    (N = max(axes)); иначе -- сообщение, называющее конкретную ось."""
    if not axes:
        return "карта не содержит ни одного заголовка «## Ось N»"
    seen: set[int] = set()
    for n in axes:
        if n in seen:
            return f"дубль заголовка оси {n}"
        seen.add(n)
    n_max = max(axes)
    missing = [n for n in range(1, n_max + 1) if n not in seen]
    if missing:
        return f"пропущена ось {missing[0]} (заголовок «## Ось {missing[0]}» отсутствует)"
    return None


def check_map_text(map_text: str) -> str | None:
    """Разбирает текст карты mg.parse_axes() и проверяет непрерывность."""
    return continuity_error(mg.parse_axes(map_text))


def check_map_file(path: Path) -> str | None:
    """Как check_map_text, но читает файл; отсутствующий/нечитаемый файл
    -- тоже провал детектора (НЕ skip, см. DoD 2в кейс 7)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"карта нечитаема: {path} ({exc})"
    return check_map_text(text)


# --- 2а: самоприменимость к ЖИВОЙ карте (docs/SIBLING_MAP.md) ---
# ДО п.1 спеки (заголовок оси 7 отсутствует) -- красный.
# ПОСЛЕ п.1 -- зелёный. Порядок работ спекой предписан именно так;
# живая карта здесь НЕ портится -- она уже красная де-факто (коммит
# 7bd21cc), синтетика ниже отдельно, в tmp_path.

def test_live_map_axis_numbering_is_continuous():
    err = check_map_file(mg.MAP_PATH)
    assert err is None, err


# --- 2в: семь синтетических кейсов (файлы -- только tmp_path) ---

def test_case1_continuous_1_2_3_passes():
    assert continuity_error([1, 2, 3]) is None


def test_case2_gap_1_2_4_fails():
    err = continuity_error([1, 2, 4])
    assert err is not None
    assert "3" in err


def test_case3_single_1_passes():
    assert continuity_error([1]) is None


def test_case4_missing_1_in_2_3_fails():
    err = continuity_error([2, 3])
    assert err is not None
    assert "1" in err


def test_case5_empty_axes_fails(tmp_path):
    map_no_axes = tmp_path / "map_no_axes.md"
    map_no_axes.write_text(
        "# Sibling Map\n\nв этом документе нет заголовков осей.\n",
        encoding="utf-8",
    )
    err = check_map_file(map_no_axes)
    assert err is not None


def test_case6_duplicate_axis_2_fails():
    err = continuity_error([1, 2, 2, 3])
    assert err is not None
    assert "2" in err


def test_case7_map_file_missing_fails(tmp_path):
    absent = tmp_path / "does_not_exist.md"
    err = check_map_file(absent)
    assert err is not None
