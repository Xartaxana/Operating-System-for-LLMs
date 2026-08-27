"""Тесты машинного слоя тел карты «правило -> сторож» (docs/RULE_COVERAGE.md
-> docs/rule_coverage/RC-0N.md) -- спека docs/tasks/2026-08-20_rule-coverage-
bodies-spec.md, §4, ключи K1-K7 + адверсариальная батарея.

Каждый ключ несёт позитивную И негативную синтетику в tmp_path (спека,
§4, вводное предложение) -- живые файлы репозитория НЕ портятся; два
интеграционных теста (аналог образца test_corpus_growth.py "ключ 10")
сверяют ЖИВОЕ дерево read-only.

К2 (сирота), уточнение формы: спека формулирует "каждый
docs/rule_coverage/*.md сослан РОВНО одной строкой", но §3 спеки прямо
предписывает ОДИН файл на СЕКЦИЮ карты -- секция 1 несёт ТРИ якоря в
ОДНОМ файле (RC-01.md), т.е. один и тот же ФАЙЛ законно получает
несколько указателей с разными якорями. Разрешение (аналог PAIR-пары
пре-пасса, которая проверяет 1:1 на грануляции id, не файла): К2 здесь
реализован на грануляции (файл, ЯКОРЬ) -- КАЖДЫЙ якорь резолвится РОВНО
ОДНИМ указателем (не 0, не 2+); отдельно проверяется, что ни один
поставленный файл целиком не остаётся без единого входящего указателя.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_prepass as prep  # noqa: E402
import md_regions  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_RULE_COVERAGE = REPO_ROOT / "docs" / "RULE_COVERAGE.md"
LIVE_BODY_DIR = REPO_ROOT / "docs" / "rule_coverage"
LIVE_PROTOCOL = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"

# "Развёртка (...) -- тело: docs/rule_coverage/RC-0N.md#anchor" --
# путь и якорь захватываются отдельно; лениво до конца строки таблицы
# (не заходит за следующую "|"), якорь -- слово из букв/цифр/дефисов.
POINTER_RE = re.compile(
    r"тело:\s*(docs/rule_coverage/RC-\d+\.md)#([A-Za-z0-9\-]+)"
)
ANCHOR_HEADING_RE = re.compile(r"^## ([a-z0-9]+-[a-z0-9-]+)\s*$", re.MULTILINE)
HEADER_MARKERS = ("ВЛАДЕЛЕЦ:", "ОБРАТНАЯ ССЫЛКА:", "ПРАВИЛО ВЕДЕНИЯ:")


# ---------------------------------------------------------------------------
# Библиотечные функции -- используются и живыми, и синтетическими тестами
# ---------------------------------------------------------------------------

def find_pointers_prose_only(rule_coverage_text: str) -> List[Tuple[str, str, int]]:
    """(файл, якорь, offset) для каждого указателя, ЛЕЖАЩЕГО В ПРОЗЕ
    (Р9 спеки, md_regions): указатель внутри ```-фенса/цитаты карты НЕ
    засчитывается -- иначе фенс "усыновляет" сироту."""
    result = md_regions.scan(rule_coverage_text)
    out = []
    for m in POINTER_RE.finditer(rule_coverage_text):
        offset = m.start()
        kinds = md_regions.kind_at(result, offset)
        if md_regions.KIND_FENCED in kinds or md_regions.KIND_BLOCKQUOTE in kinds:
            continue
        out.append((m.group(1), m.group(2), offset))
    return out


def find_anchors_in_body(body_text: str) -> List[str]:
    return ANCHOR_HEADING_RE.findall(body_text)


def check_k1_pointer_resolves_to_file(pointers: List[Tuple[str, str, int]], root: Path) -> List[str]:
    errors = []
    for path, anchor, _off in pointers:
        full = root / path
        if not full.exists() or not full.is_file():
            errors.append(f"K1: указатель на {path}#{anchor} -- файл не найден: {full}")
    return errors


def check_k2_orphan(pointers: List[Tuple[str, str, int]], body_files: Dict[str, str]) -> List[str]:
    """Грануляция (файл, якорь): каждый якорь тела резолвится РОВНО
    одним указателем; каждый поставленный файл несёт хотя бы один
    входящий указатель (не сирота целиком)."""
    errors = []
    counts: Dict[Tuple[str, str], int] = {}
    for path, anchor, _off in pointers:
        counts[(path, anchor)] = counts.get((path, anchor), 0) + 1
    for path, text in body_files.items():
        anchors = find_anchors_in_body(text)
        if not any(p == path for p, _a, _o in pointers):
            errors.append(f"K2: файл-сирота (ни один указатель на него) -- {path}")
        for a in anchors:
            n = counts.get((path, a), 0)
            if n == 0:
                errors.append(f"K2: якорь-сирота (0 указателей) -- {path}#{a}")
            elif n > 1:
                errors.append(f"K2: якорь сослан {n} раз (ожидалась 1) -- {path}#{a}")
    return errors


def check_k3_anchor(pointers: List[Tuple[str, str, int]], body_files: Dict[str, str]) -> List[str]:
    errors = []
    anchors_by_file: Dict[str, List[str]] = {p: find_anchors_in_body(t) for p, t in body_files.items()}
    for path, anchor, _off in pointers:
        anchors = anchors_by_file.get(path, [])
        if anchor not in anchors:
            errors.append(f"K3: якорь {anchor} не найден в теле {path}")
    all_anchors: List[str] = []
    for path, anchors in anchors_by_file.items():
        for a in anchors:
            all_anchors.append(f"{path}#{a}")
    seen = set()
    for key in all_anchors:
        anchor_only = key.split("#", 1)[1]
        if anchor_only in seen:
            errors.append(f"K3: дубль якоря (не уникален глобально) -- {anchor_only}")
        seen.add(anchor_only)
    return errors


def check_k4_form(path: str, raw: bytes) -> List[str]:
    errors = []
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"K4: BOM в {path}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"K4: не UTF-8 в {path}: {exc}")
        return errors
    if "\r\n" in text or "\r" in text:
        errors.append(f"K4: CRLF/CR в {path} (ожидается LF)")
    for marker in HEADER_MARKERS:
        if marker not in text:
            errors.append(f"K4: маркер шапки {marker!r} отсутствует в {path}")
    return errors


def check_k5_chek_n_resolves(body_files: Dict[str, str], valid_check_numbers: set) -> List[str]:
    errors = []
    for path, text in body_files.items():
        for e in prep.validate_rules_backward(text, valid_check_numbers):
            errors.append(f"K5: {path}: {e}")
    return errors


_MODE_WORDS = (
    "БЛОК-ХУК", "WARN-ХУК", "ГЕЙТ КОММИТА", "ВСПЛЫТИЕ", "ЧЕК",
    "AI-СЛОЙ", "КОНФИГ", "ЭКЗАМЕН", "ДИСЦИПЛИНА+ДЕТЕКТОР", "ГЕЙТ ФОРМЫ",
)


def check_k6_sufficiency_minimum(rows: List[Tuple[str, str, str]]) -> List[str]:
    """rows: (норма, режим, носитель) для КАЖДОЙ строки-записи С
    указателем ("- тело: docs/rule_coverage/" в тексте строки). Форма,
    не смысл: режим непуст и содержит слово легенды; носитель несёт
    хотя бы один резолвимый признак ("чек N" ИЛИ путь вида a/b.py ИЛИ
    tools/имя.py ИЛИ обратный тик-идентификатор с точкой/слешем)."""
    errors = []
    carrier_re = re.compile(r"чек\s+\d+|[\w./]+\.py|`[\w./]+`")
    for norm, mode, carrier in rows:
        if not mode.strip():
            errors.append(f"K6: пустой режим у строки {norm[:40]!r}")
        elif not any(w in mode for w in _MODE_WORDS):
            errors.append(f"K6: режим без слова легенды у строки {norm[:40]!r}: {mode!r}")
        if not carrier_re.search(carrier):
            errors.append(f"K6: носитель нерезолвим у строки {norm[:40]!r}")
    return errors


def rows_with_pointer_from_table(rule_coverage_text: str) -> List[Tuple[str, str, str]]:
    """Разбирает строки markdown-таблицы карты (| a | b | c |), несущие
    подстроку 'тело: docs/rule_coverage/'; возвращает (норма, режим,
    носитель) по трём первым ячейкам."""
    rows = []
    for line in rule_coverage_text.splitlines():
        if not line.startswith("|"):
            continue
        if "тело: docs/rule_coverage/" not in line:
            continue
        cells = _split_table_row(line)
        if len(cells) >= 3:
            rows.append((cells[0], cells[1], cells[2]))
    return rows


def _split_table_row(line: str) -> List[str]:
    """Разбивает '| a | b | c |' на ['a','b','c'], уважая экранированный
    '\\|' внутри ячейки (И-4 карты)."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    parts = re.split(r"(?<!\\)\|", body)
    return [p.strip() for p in parts]


# ---------------------------------------------------------------------------
# K7: молчаливый ноль запрещён
# ---------------------------------------------------------------------------

def assert_nonzero_if_dir_nonempty(body_dir: Path, pointers: List[Tuple[str, str, int]]):
    if not body_dir.exists():
        return
    body_files = list(body_dir.glob("*.md"))
    if not body_files:
        return
    if len(pointers) == 0:
        pytest.fail(
            f"K7: каталог {body_dir} непуст ({len(body_files)} файлов), но "
            f"распознано 0 указателей -- молчаливый ноль запрещён"
        )


# ---------------------------------------------------------------------------
# Живое дерево (интеграция, read-only)
# ---------------------------------------------------------------------------

def _load_live():
    rc_text = LIVE_RULE_COVERAGE.read_text(encoding="utf-8")
    body_files = {}
    for f in sorted(LIVE_BODY_DIR.glob("*.md")):
        rel = f.relative_to(REPO_ROOT).as_posix()
        body_files[rel] = f.read_text(encoding="utf-8")
    return rc_text, body_files


def test_live_k1_all_pointers_resolve_to_existing_file():
    rc_text, _ = _load_live()
    pointers = find_pointers_prose_only(rc_text)
    assert len(pointers) >= 6, f"ожидались >=6 указателей на живой карте, найдено {len(pointers)}"
    errors = check_k1_pointer_resolves_to_file(pointers, REPO_ROOT)
    assert errors == []


def test_live_k2_no_orphans_either_direction():
    rc_text, body_files = _load_live()
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k2_orphan(pointers, body_files)
    assert errors == []


def test_live_k3_anchors_exist_and_unique():
    rc_text, body_files = _load_live()
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k3_anchor(pointers, body_files)
    assert errors == []


def test_live_k4_form_markers_utf8_lf_no_bom():
    for f in sorted(LIVE_BODY_DIR.glob("*.md")):
        rel = f.relative_to(REPO_ROOT).as_posix()
        raw = f.read_bytes()
        errors = check_k4_form(rel, raw)
        assert errors == [], errors


def test_live_k5_chek_n_in_bodies_resolves_without_touching_prepass():
    _, bounds_titles = None, None
    lines, bounds, titles = prep.load_protocol_structure(LIVE_PROTOCOL)
    valid_numbers = {t.number for t in titles}
    _, body_files = _load_live()
    errors = check_k5_chek_n_resolves(body_files, valid_numbers)
    assert errors == []


def test_live_k6_sufficiency_minimum_form():
    # 5 узнанных ТАБЛИЧНЫХ строк (60/64/66/96/122); шестой указатель
    # (справочник "чек 26") -- строка-буллет "- чек 26 —", НЕ таблица
    # ("| a | b | c |"), поэтому K6's 3-колоночная форма к ней не
    # применяется -- она проверена отдельно тестом test_live_k1..k3/k7
    # через find_pointers_prose_only (тот работает по всему тексту, не
    # только по таблице).
    rc_text, _ = _load_live()
    rows = rows_with_pointer_from_table(rc_text)
    assert len(rows) >= 5
    errors = check_k6_sufficiency_minimum(rows)
    assert errors == []


def test_live_k7_nonsilent_zero_guard_passes_on_live_tree():
    rc_text, _ = _load_live()
    pointers = find_pointers_prose_only(rc_text)
    assert_nonzero_if_dir_nonempty(LIVE_BODY_DIR, pointers)


def test_live_positional_invariant_no_new_numbered_sections():
    """И-2/позиционный инвариант карты: заголовки '## N. ' в живом
    RULE_COVERAGE.md -- РОВНО секции 1..8, вынос тел не добавил новых."""
    rc_text, _ = _load_live()
    heading_re = re.compile(r"^## (\d+)\. ", re.MULTILINE)
    numbers = [int(m.group(1)) for m in heading_re.finditer(rc_text)]
    assert numbers == list(range(1, 9)), numbers


def test_live_records_still_62():
    """И-3: вынос тел не есть удаление строк -- 62 записи таблицы карты
    (тот же счётчик, что и tools/corpus_growth.py record_re).
    61 -> 62: строка R1(d)/D-0111 добавлена посадкой 69cdf4b 2026-08-27
    (пин обновляется тем же ходом, что добавляет строку карты; пропуск
    обновления при посадке D-0111 вскрыт BATCH CANON петли, итерация 1
    -- экземпляр класса spec-recidiv в копилку счётчика 13(г))."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import corpus_growth as cg  # noqa: E402
    rc_text, _ = _load_live()
    normalized = rc_text.replace("\r\n", "\n").replace("\r", "\n")
    n = cg.count_records(normalized, r"^\| + exclude разделители/шапки")
    assert n == 62


# ---------------------------------------------------------------------------
# Синтетика в tmp_path -- позитив + адверсариальная батарея (§4)
# ---------------------------------------------------------------------------

_GOOD_HEADER = (
    "# Тело секции 9 (тест)\n\n"
    "ВЛАДЕЛЕЦ: Lead.\n\n"
    "ОБРАТНАЯ ССЫЛКА: docs/RULE_COVERAGE.md, секция «## 9. Тест».\n\n"
    "ПРАВИЛО ВЕДЕНИЯ: тестовая синтетика.\n\n"
)


def _rc_row(norm: str, mode: str, carrier_prefix: str, path: str, anchor: str) -> str:
    return f"| {norm} | {mode} | {carrier_prefix}. Развёртка — тело: {path}#{anchor} |\n"


def test_synthetic_k1_broken_pointer_detected(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    (body_dir / "RC-09.md").write_text(_GOOD_HEADER + "## rc9-a\n\nтекст\n", encoding="utf-8", newline="\n")
    rc_text = _rc_row("Норма X", "ЧЕК 1", "tools/x.py", "docs/rule_coverage/RC-99.md", "rc9-a")
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k1_pointer_resolves_to_file(pointers, tmp_path)
    assert any("RC-99.md" in e for e in errors)


def test_synthetic_k1_positive_control_no_defect(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    (body_dir / "RC-09.md").write_text(_GOOD_HEADER + "## rc9-a\n\nтекст\n", encoding="utf-8", newline="\n")
    rc_text = _rc_row("Норма X", "ЧЕК 1", "tools/x.py", "docs/rule_coverage/RC-09.md", "rc9-a")
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k1_pointer_resolves_to_file(pointers, tmp_path)
    assert errors == []


def test_synthetic_k2_orphan_file_no_pointer(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    (body_dir / "RC-09.md").write_text(_GOOD_HEADER + "## rc9-a\n\nтекст\n", encoding="utf-8", newline="\n")
    body_files = {"docs/rule_coverage/RC-09.md": (body_dir / "RC-09.md").read_text(encoding="utf-8")}
    errors = check_k2_orphan([], body_files)
    assert any("файл-сирота" in e for e in errors)


def test_synthetic_k2_orphan_anchor_zero_refs(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    text = _GOOD_HEADER + "## rc9-a\n\nтекст a\n\n## rc9-b\n\nтекст b\n"
    (body_dir / "RC-09.md").write_text(text, encoding="utf-8", newline="\n")
    body_files = {"docs/rule_coverage/RC-09.md": text}
    rc_text = _rc_row("Норма X", "ЧЕК 1", "tools/x.py", "docs/rule_coverage/RC-09.md", "rc9-a")
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k2_orphan(pointers, body_files)
    assert any("rc9-b" in e and "якорь-сирота" in e for e in errors)


def test_synthetic_k2_duplicate_reference_to_same_anchor(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    text = _GOOD_HEADER + "## rc9-a\n\nтекст a\n"
    (body_dir / "RC-09.md").write_text(text, encoding="utf-8", newline="\n")
    body_files = {"docs/rule_coverage/RC-09.md": text}
    rc_text = (
        _rc_row("Норма X", "ЧЕК 1", "tools/x.py", "docs/rule_coverage/RC-09.md", "rc9-a")
        + _rc_row("Норма Y", "ЧЕК 1", "tools/y.py", "docs/rule_coverage/RC-09.md", "rc9-a")
    )
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k2_orphan(pointers, body_files)
    assert any("сослан 2 раз" in e for e in errors)


def test_synthetic_k3_dangling_anchor(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    text = _GOOD_HEADER + "## rc9-a\n\nтекст\n"
    (body_dir / "RC-09.md").write_text(text, encoding="utf-8", newline="\n")
    body_files = {"docs/rule_coverage/RC-09.md": text}
    rc_text = _rc_row("Норма X", "ЧЕК 1", "tools/x.py", "docs/rule_coverage/RC-09.md", "rc9-ghost")
    pointers = find_pointers_prose_only(rc_text)
    errors = check_k3_anchor(pointers, body_files)
    assert any("rc9-ghost" in e for e in errors)


def test_synthetic_k3_duplicate_anchor_across_files(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    t1 = _GOOD_HEADER + "## rc9-dup\n\nтекст 1\n"
    t2 = _GOOD_HEADER + "## rc9-dup\n\nтекст 2\n"
    (body_dir / "RC-09.md").write_text(t1, encoding="utf-8", newline="\n")
    (body_dir / "RC-10.md").write_text(t2, encoding="utf-8", newline="\n")
    body_files = {
        "docs/rule_coverage/RC-09.md": t1,
        "docs/rule_coverage/RC-10.md": t2,
    }
    pointers = [
        ("docs/rule_coverage/RC-09.md", "rc9-dup", 0),
        ("docs/rule_coverage/RC-10.md", "rc9-dup", 1),
    ]
    errors = check_k3_anchor(pointers, body_files)
    assert any("дубль якоря" in e for e in errors)


def test_synthetic_k4_empty_body_missing_markers(tmp_path):
    errors = check_k4_form("x.md", b"")
    assert any("ВЛАДЕЛЕЦ" in e for e in errors)


def test_synthetic_k4_bom_detected(tmp_path):
    raw = b"\xef\xbb\xbf" + _GOOD_HEADER.encode("utf-8") + b"## rc9-a\n\ntext\n"
    errors = check_k4_form("x.md", raw)
    assert any("BOM" in e for e in errors)


def test_synthetic_k4_crlf_detected(tmp_path):
    raw = (_GOOD_HEADER + "## rc9-a\n\ntext\n").replace("\n", "\r\n").encode("utf-8")
    errors = check_k4_form("x.md", raw)
    assert any("CRLF" in e for e in errors)


def test_synthetic_k4_positive_control_clean_file_no_defects(tmp_path):
    raw = (_GOOD_HEADER + "## rc9-a\n\ntext\n").encode("utf-8")
    errors = check_k4_form("x.md", raw)
    assert errors == []


def test_synthetic_k5_chek_99_in_body_flagged(tmp_path):
    valid_numbers = {1, 2, 3, 30}
    body_files = {"docs/rule_coverage/RC-09.md": "текст ссылается на чек 99 внутри тела"}
    errors = check_k5_chek_n_resolves(body_files, valid_numbers)
    assert any("чек 99" in e for e in errors)


def test_synthetic_k5_positive_control_known_chek_clean(tmp_path):
    valid_numbers = {1, 2, 3, 30}
    body_files = {"docs/rule_coverage/RC-09.md": "текст ссылается на чек 30 внутри тела"}
    errors = check_k5_chek_n_resolves(body_files, valid_numbers)
    assert errors == []


def test_synthetic_k6_empty_mode_flagged():
    rows = [("Норма Z", "", "tools/z.py")]
    errors = check_k6_sufficiency_minimum(rows)
    assert any("пустой режим" in e for e in errors)


def test_synthetic_k6_mode_without_legend_word_flagged():
    rows = [("Норма Z", "НЕИЗВЕСТНЫЙ РЕЖИМ", "tools/z.py")]
    errors = check_k6_sufficiency_minimum(rows)
    assert any("без слова легенды" in e for e in errors)


def test_synthetic_k6_carrier_unresolvable_flagged():
    rows = [("Норма Z", "ЧЕК 1", "просто слова без пути и без чек-номера")]
    errors = check_k6_sufficiency_minimum(rows)
    assert any("нерезолвим" in e for e in errors)


def test_synthetic_k6_positive_control_clean_row():
    rows = [("Норма Z", "ЧЕК 1", "tools/z.py — развёртка в теле")]
    errors = check_k6_sufficiency_minimum(rows)
    assert errors == []


def test_synthetic_k7_silent_zero_fails_loudly(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage"
    body_dir.mkdir(parents=True)
    (body_dir / "RC-09.md").write_text(_GOOD_HEADER + "## rc9-a\n\ntext\n", encoding="utf-8", newline="\n")
    with pytest.raises(pytest.fail.Exception):
        assert_nonzero_if_dir_nonempty(body_dir, [])


def test_synthetic_k7_empty_dir_is_not_a_violation(tmp_path):
    body_dir = tmp_path / "docs" / "rule_coverage_empty"
    body_dir.mkdir(parents=True)
    assert_nonzero_if_dir_nonempty(body_dir, [])  # не бросает


def test_synthetic_pointer_inside_fence_not_counted():
    """Р9: указатель внутри ```-фенса карты НЕ засчитывается -- фенс не
    должен "усыновлять" сироту (адверсариальная батарея §4)."""
    rc_text = (
        "```\n"
        "| Норма X | ЧЕК 1 | tools/x.py. Развёртка — тело: docs/rule_coverage/RC-09.md#rc9-a |\n"
        "```\n"
    )
    pointers = find_pointers_prose_only(rc_text)
    assert pointers == []


def test_synthetic_pointer_inside_blockquote_not_counted():
    rc_text = "> | Норма X | ЧЕК 1 | tools/x.py. — тело: docs/rule_coverage/RC-09.md#rc9-a |\n"
    pointers = find_pointers_prose_only(rc_text)
    assert pointers == []


def test_synthetic_pointer_in_prose_positive_control_counted():
    rc_text = "| Норма X | ЧЕК 1 | tools/x.py. — тело: docs/rule_coverage/RC-09.md#rc9-a |\n"
    pointers = find_pointers_prose_only(rc_text)
    assert len(pointers) == 1
    assert pointers[0][0] == "docs/rule_coverage/RC-09.md"
    assert pointers[0][1] == "rc9-a"
