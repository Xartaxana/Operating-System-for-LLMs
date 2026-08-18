"""Пре-пасс еженедельной калибровки -- Phase 5 W2a (t-491).

Семья calibration_* (сиблинг tools/calibration_counts.py). Решает
ВСТРЕЧУ (какие чеки чек-листа PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md
имеют материал в заданном окне) и печатает причины пропуска;
смысловой вердикт остаётся калибрующему Lead (D-0063).

Носитель нормы -- машиночитаемая шапка чека, однострочный HTML-
комментарий:
    <!--CHK 13(к)|src:журнал|pred:journal.parallel_groups|
        rules:RC§1/R4|status:живой|since:2026-08-09-->
Поля (фиксированный порядок): CHK <id> | src: | pred: | rules: |
status: | cand: (опц.) | since: (опц.) | note: (опц.). Позиция шапки
чека -- первая строка ПОСЛЕ строки с ЗАКРЫВАЮЩИМ ** жирного заголовка
(заголовок может быть многострочным). Под-шапка подпункта ставится
ТОЛЬКО перед подпунктом, чей маркер "(x)" начинает строку; вплетённый
в абзац подпункт под-шапки не получает и наследует предикат/статус
родителя (гибрид-нормализация -- кандидат W2c, не делается здесь).

Закрытый список предикатов (без композиции): always, journal.any,
journal.event:<E>[,agent=<A>][,deploy=<D>], journal.field:<f>=<v>,
journal.parallel_groups, git.any, git.paths:<glob>[,...][@OS|@AO3],
git.diff_lines:><N>, path.exists:<путь>, deploy.exists:<имя>,
script:<имя>, manual:<почему>.

CLI:
    python tools/calibration_prepass.py --window-start <ISO>
        [--window-end <ISO>] [--protocol PATH] [--journal PATH ...]
        [--deploy имя=путь ...] [--rule-coverage PATH] [--json]
        [--control] [--registry PATH]
    python tools/calibration_prepass.py --check-form [--require-all]
        [--protocol PATH] [--rule-coverage PATH]

Коды выхода: 0 -- прогон состоялся; 1 -- ТОЛЬКО у --check-form
(дефекты формы найдены); 2 -- IO/аргументы (файл не найден, не
парсится, протокол без единого чека и т.п.). Скрипт-измеритель:
window-прогон возвращает 0 даже когда чеки ПУСТЫ/ЖИВЫ -- вердикты не
гейт (тот же принцип, что и calibration_counts.py).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # безопасность вывода на Windows-консолях с не-UTF8 codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    import yaml  # той же библиотекой, что tools/mechanism_gate.py
except ImportError:  # pragma: no cover -- pyyaml всегда в окружении репо
    yaml = None

# calibration_counts -- сиблинг, НЕ переписываем, только импортируем
# (given манифеста диспатча t-491): load_journal, analyze_journal,
# _in_window, parse_ts.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import calibration_counts as cc  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROTOCOL = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
DEFAULT_JOURNAL = REPO_ROOT / "logs" / "routing-log.jsonl"
DEFAULT_RULE_COVERAGE = REPO_ROOT / "docs" / "RULE_COVERAGE.md"
DEFAULT_CONFIG = REPO_ROOT / "delegation.config.yaml"
DEFAULT_REGISTRY = REPO_ROOT / "logs" / "calibration_prepass.jsonl"

# Абсолют гейта (а) Phase 5 (docs/tasks/2026-08-18_phase5-norm-corpus.md,
# AM-6(5)) -- НЕ путь к деплою, поэтому пункт AM-3.6 (запрет
# захардкоженного деплой-пути) его не касается.
GATE_A_THRESHOLD_BYTES = 57_500

# ---------------------------------------------------------------------------
# Форма шапки
# ---------------------------------------------------------------------------

HEADER_LINE_RE = re.compile(r"^\s*<!--CHK\s+(\S+?)\|(.*?)-->\s*$")
HEADER_ANYWHERE_RE = re.compile(r"<!--CHK\b")
CHECK_TITLE_RE = re.compile(r"^\s*(\d+)\.\s+\*\*")
CHECK_ID_RE = re.compile(r"^(\d+)(?:\((.+)\))?$")

FIELD_ORDER = ["src", "pred", "rules", "status", "cand", "since", "note"]
REQUIRED_FIELDS = ["src", "pred", "rules", "status"]
MAX_FIELDS_TOTAL = 8  # CHK + 7 остальных максимум
MAX_HEADER_BYTES = 300
MAX_SRC_VALUES = 4
MAX_RULES_VALUES = 4
MAX_HEADERS_PER_ID = 1
MAX_ID_LEN = 12

SRC_CLOSED = {
    "журнал", "журнал-AO3", "git", "git-AO3", "cc_usage",
    "транскрипты", "файлы", "файлы-AO3", "оператор",
}
SRC_SCRIPT_RE = re.compile(r"^скрипт:(\S+)$")

STATUS_LIVE = "живой"
STATUS_RETIRED_RE = re.compile(
    r"^ретирован:(\d{4}-\d{2}-\d{2});сторож:([^;\s]+);живость:(.+)$"
)
STATUS_DEFERRED_PREFIX = "деферред:"

RULES_ENTRY_RE = re.compile(r"^RC§(\d+)/(\S+)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Раскладка src -> секция -> pred полностью задана A2 (драфт) + AM-8
# (замена pred у 15/17/27/28/33). Секция -- НЕ поле шапки: это
# структурная классификация чек-листа, нужная для группировки вывода
# и для расчёта "живых N/34"/ИТОГ по всем 34 checам одинаково, есть у
# них шапка или нет (A3 edge 2: без шапки -- ЖИВ по умолчанию).
SECTION_BY_CHECK = {
    0: 0, 1: 4, 2: 2, 3: 1, 4: 4, 5: 4, 6: 1, 7: 4, 8: 2, 9: 3, 10: 3,
    11: 4, 12: 3, 13: 1, 14: 2, 15: 5, 16: 2, 17: 5, 18: 4, 19: 4,
    20: 1, 21: 1, 22: 1, 23: 1, 24: 3, 25: 4, 26: 3, 27: 5, 28: 5,
    29: 3, 30: 1, 31: 1, 32: 2, 33: 5,
}
SECTION_NAMES = {
    0: "§0 РЕТРО-КОНТУР",
    1: "§1 ЖУРНАЛ (оба деплоя)",
    2: "§2 GIT-ДИФФЫ (оба репо)",
    3: "§3 ФАЙЛЫ И ЯКОРЯ",
    4: "§4 ТРАНСКРИПТЫ/cc_usage/ДЕНЬГИ",
    5: "§5 ВНЕШНИЙ ДЕПЛОЙ AO3",
}

# Известные команды скриптовых предикатов (script:<имя>) -- печатаются
# в причине "ЖИВ" вместо голого имени; список -- удобство вывода, НЕ
# закрытый источник истины (неизвестное имя печатает generic-строку).
KNOWN_SCRIPT_COMMANDS = {
    "parity_check": "python tools/parity_check.py --check",
    "hook_liveness_probe": "python tools/hook_liveness_probe.py",
    "permission_audit": "python tools/permission_audit.py --minutes <окно>",
    "savings_report": "python tools/savings_report.py --until <конец окна>",
    "requests": "см. gateway/requests.db (traffic_kind-скан)",
    "spend_report": "python tools/spend_report.py --window last --compare prev",
}


# ---------------------------------------------------------------------------
# Чтение и нормализация протокола
# ---------------------------------------------------------------------------

class ProtocolError(Exception):
    """IO/структурная ошибка протокола -- маппится на exit 2."""


def read_protocol_text(path: Path) -> str:
    if not path.exists():
        raise ProtocolError(f"протокол не найден: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtocolError(f"протокол не в UTF-8: {exc}") from exc
    # CRLF -> LF (В: мелочи драфта); одинокий CR тоже нормализуем.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def split_lines(text: str) -> List[str]:
    """0-indexed построчный список БЕЗ финального перевода строки на
    каждой строке (последняя пустая запись от split('\\n') на файле с
    финальным \\n отбрасывается, как это делает splitlines())."""
    return text.split("\n")


def line_byte_offsets(lines: List[str]) -> List[int]:
    """offsets[i] -- байтовое смещение НАЧАЛА строки i (0-indexed) в
    UTF-8-перекодированном нормализованном тексте (строки соединены
    '\\n'). offsets[len(lines)] -- общий размер текста в байтах."""
    offsets = [0]
    total = 0
    for i, ln in enumerate(lines):
        total += len(ln.encode("utf-8"))
        if i != len(lines) - 1:
            total += 1  # '\n' между строками
        offsets.append(total)
    return offsets


# ---------------------------------------------------------------------------
# Структура чек-листа: заголовки чеков, диапазоны, шапки
# ---------------------------------------------------------------------------

@dataclass
class CheckTitle:
    number: int
    title_start: int   # 0-indexed line, "N. **..."
    title_close: int    # 0-indexed line с закрывающим ** заголовка


@dataclass
class RawHeader:
    line_no: int         # 0-indexed
    id_str: str
    fields_raw: str
    malformed: bool = False
    malformed_reason: str = ""


@dataclass
class ParsedHeader:
    line_no: int
    id_str: str
    check_number: int
    subitem_letter: Optional[str]
    fields: "dict[str, str]"
    field_order_seen: List[str]
    errors: List[str] = field(default_factory=list)


def load_protocol_structure(path: Path) -> Tuple[List[str], Tuple[int, int], List[CheckTitle]]:
    """Общая точка входа для обоих режимов: читает протокол, находит
    границы чек-листа и заголовки чеков. Пустой протокол/протокол без
    единого числового заголовка -> ProtocolError (A8.5: "форма не
    распознана", exit 2 у обоих режимов)."""
    text = read_protocol_text(path)
    lines = split_lines(text)
    bounds = find_checklist_bounds(lines)
    titles = find_check_titles(lines, bounds)
    if not titles:
        raise ProtocolError("форма не распознана: в протоколе не найдено ни одного чека")
    return lines, bounds, titles


def find_checklist_bounds(lines: List[str]) -> Tuple[int, int]:
    """(start, end) 0-indexed, [start, end) -- строки между "## Чек-лист"
    и "## Завершение прогона" включительно с точки начала первого чека.
    Если секции не найдены -- ProtocolError (форма не распознана)."""
    start = None
    end = None
    for i, ln in enumerate(lines):
        if start is None and ln.strip().startswith("## Чек-лист"):
            start = i
        if ln.strip().startswith("## Завершение прогона"):
            end = i
            break
    if start is None:
        raise ProtocolError("форма не распознана: секция \"## Чек-лист\" не найдена")
    if end is None:
        end = len(lines)
    return start, end


def find_check_titles(lines: List[str], bounds: Tuple[int, int]) -> List[CheckTitle]:
    start, end = bounds
    titles: List[CheckTitle] = []
    i = start
    while i < end:
        m = CHECK_TITLE_RE.match(lines[i])
        if m:
            number = int(m.group(1))
            close = _find_title_close(lines, i, end)
            titles.append(CheckTitle(number=number, title_start=i, title_close=close))
        i += 1
    return titles


def _find_title_close(lines: List[str], title_start: int, hard_end: int,
                       max_scan: int = 40) -> int:
    """Индекс строки, несущей ЗАКРЫВАЮЩИЙ ** жирного заголовка чека,
    считая от title_start (заголовок может быть многострочным, AM-1 П1)."""
    count = 0
    scan_end = min(title_start + max_scan, hard_end)
    for i in range(title_start, scan_end):
        count += lines[i].count("**")
        if count >= 2:
            return i
    # Не нашли закрытия в разумных пределах -- считаем, что заголовок
    # занимает только свою строку (защита от вечного скана).
    return title_start


def check_ranges(titles: List[CheckTitle], checklist_end: int) -> "dict[int, Tuple[int, int]]":
    """number -> (start_line, end_line) 0-indexed ВКЛЮЧИТЕЛЬНО -- до
    следующего заголовка чека или до конца секции чек-листа (В:
    мелочи драфта)."""
    ordered = sorted(titles, key=lambda t: t.title_start)
    ranges: Dict[int, Tuple[int, int]] = {}
    for idx, t in enumerate(ordered):
        next_start = ordered[idx + 1].title_start if idx + 1 < len(ordered) else checklist_end
        ranges[t.number] = (t.title_start, next_start - 1)
    return ranges


def validate_check_numbering(titles: List[CheckTitle]) -> List[str]:
    """Инвариант Lead 1: сплошной 0..N, без дублей (--check-form)."""
    errors = []
    numbers = [t.number for t in titles]
    seen: Dict[int, int] = {}
    for n in numbers:
        seen[n] = seen.get(n, 0) + 1
    for n, c in seen.items():
        if c > 1:
            errors.append(f"FORM: дубль номера чека {n} ({c} вхождений)")
    if numbers:
        uniq = sorted(set(numbers))
        expected = list(range(0, uniq[-1] + 1))
        missing = [n for n in expected if n not in uniq]
        for n in missing:
            errors.append(f"FORM: разрыв нумерации -- чек {n} отсутствует")
    return errors


def find_raw_headers(lines: List[str], bounds: Tuple[int, int]) -> List[RawHeader]:
    start, end = bounds
    out: List[RawHeader] = []
    for i in range(start, end):
        ln = lines[i]
        m = HEADER_LINE_RE.match(ln)
        if m:
            out.append(RawHeader(line_no=i, id_str=m.group(1), fields_raw=m.group(2)))
            continue
        if HEADER_ANYWHERE_RE.search(ln):
            out.append(RawHeader(
                line_no=i, id_str="", fields_raw="", malformed=True,
                malformed_reason="шапка не занимает строку целиком (текст до/после "
                                  "<!--CHK ... --> на той же строке)",
            ))
    return out


def parse_header_fields(fields_raw: str) -> Tuple[Dict[str, str], List[str], List[str]]:
    """Возвращает (fields, order_seen, errors). Разбор по '|', каждый
    кусок 'key:value'. Значения содержат ':' внутри (пример status:) --
    split(':', 1)."""
    errors: List[str] = []
    fields: Dict[str, str] = {}
    order_seen: List[str] = []
    if fields_raw == "":
        errors.append("пустой список полей")
        return fields, order_seen, errors
    pieces = fields_raw.split("|")
    for piece in pieces:
        if ":" not in piece:
            errors.append(f"поле без ':': {piece!r}")
            continue
        key, value = piece.split(":", 1)
        key = key.strip()
        if key not in FIELD_ORDER:
            errors.append(f"неизвестное поле: {key!r}")
            continue
        if key in fields:
            errors.append(f"повтор поля: {key!r}")
            continue
        fields[key] = value
        order_seen.append(key)
    # Порядок: order_seen должен быть подпоследовательностью FIELD_ORDER
    # в том же относительном порядке.
    expected_positions = [FIELD_ORDER.index(k) for k in order_seen]
    if expected_positions != sorted(expected_positions):
        errors.append(f"нарушен порядок полей: {order_seen}")
    return fields, order_seen, errors


def _has_bare_space(value: str) -> bool:
    return " " in value


def validate_src(value: str) -> List[str]:
    errors = []
    parts = value.split(",")
    if len(parts) > MAX_SRC_VALUES:
        errors.append(f"src: значений {len(parts)} > {MAX_SRC_VALUES}")
    for p in parts:
        if _has_bare_space(p):
            errors.append(f"src: пробел в значении {p!r}")
            continue
        if p in SRC_CLOSED:
            continue
        if SRC_SCRIPT_RE.match(p):
            continue
        errors.append(f"src: неизвестное значение {p!r}")
    return errors


# Закрытый список предикатов (A3 + AM-3). PREDICATE_KINDS -- имя ->
# regex, применяемый к value ЦЕЛИКОМ (после "pred:"/"cand:"/"деферред:").
_EVENT_NAME_RE = r"[A-Za-z_]+"
PREDICATE_PATTERNS = {
    "always": re.compile(r"^always$"),
    "journal.any": re.compile(r"^journal\.any$"),
    "journal.event": re.compile(
        rf"^journal\.event:{_EVENT_NAME_RE}(,agent={_EVENT_NAME_RE})?(,deploy=\S+)?$"
    ),
    "journal.field": re.compile(r"^journal\.field:[A-Za-z_]+=\S+$"),
    "journal.parallel_groups": re.compile(r"^journal\.parallel_groups$"),
    "git.any": re.compile(r"^git\.any$"),
    "git.paths": re.compile(r"^git\.paths:[^,@]+(,[^,@]+)*(@(OS|AO3))?$"),
    "git.diff_lines": re.compile(r"^git\.diff_lines:>\d+$"),
    "path.exists": re.compile(r"^path\.exists:\S+$"),
    "deploy.exists": re.compile(r"^deploy\.exists:[A-Za-z0-9_-]+$"),
    "script": re.compile(r"^script:\S+$"),
    "manual": re.compile(r"^manual:\S+$"),
}


def validate_predicate_value(value: str) -> Optional[str]:
    """None -- валиден; иначе строка ошибки. Пробел в значении --
    отдельная явная проверка (сообщение точнее голого 'не резолвится')."""
    if _has_bare_space(value):
        return f"предикат содержит пробел: {value!r}"
    for pat in PREDICATE_PATTERNS.values():
        if pat.match(value):
            return None
    return f"неизвестный/не резолвящийся предикат: {value!r}"


def validate_rules(value: str) -> List[str]:
    errors = []
    parts = value.split(",")
    if len(parts) > MAX_RULES_VALUES:
        errors.append(f"rules: значений {len(parts)} > {MAX_RULES_VALUES}")
    for p in parts:
        if _has_bare_space(p):
            errors.append(f"rules: пробел в значении {p!r}")
            continue
        if not RULES_ENTRY_RE.match(p):
            errors.append(f"rules: не резолвится форма RC§N/token: {p!r}")
    return errors


def validate_status(value: str) -> Tuple[List[str], str, Optional[str]]:
    """Возвращает (errors, kind, retired_guard_or_none). kind in
    {"живой","ретирован","деферред","неизвестно"}."""
    errors: List[str] = []
    if value == STATUS_LIVE:
        return errors, "живой", None
    if value.startswith("ретирован:"):
        m = STATUS_RETIRED_RE.match(value)
        if not m:
            errors.append(
                "status: ретирован без сторож:/живость: (форма "
                "ретирован:<дата>;сторож:<id>;живость:<команда>)"
            )
            return errors, "ретирован", None
        date_s, guard, liveness = m.group(1), m.group(2), m.group(3)
        if not DATE_RE.match(date_s):
            errors.append(f"status: дата ретирования не YYYY-MM-DD: {date_s!r}")
        if _has_bare_space(guard):
            errors.append(f"status: пробел в сторож: {guard!r}")
        if not liveness.strip():
            errors.append("status: пустая живость:")
        # живость: -- КОМАНДА (может содержать пробелы -- см. AM-4
        # K4-пример буквально с пробелами; исключение из общего "нет
        # пробелов в значениях", ограниченное этим одним под-полем).
        return errors, "ретирован", guard
    if value.startswith(STATUS_DEFERRED_PREFIX):
        pred_val = value[len(STATUS_DEFERRED_PREFIX):]
        err = validate_predicate_value(pred_val)
        if err:
            errors.append(f"status: деферред-предикат невалиден: {err}")
        return errors, "деферред", None
    errors.append(f"status: неизвестное значение {value!r}")
    return errors, "неизвестно", None


def validate_note(value: str) -> List[str]:
    errors = []
    if _has_bare_space(value):
        errors.append(f"note: пробел в значении {value!r}")
    if "триггер" in value.lower():
        errors.append("note: содержит запрещённую подстроку 'триггер' (AM-1 П3.iii)")
    return errors


def validate_since(value: str) -> List[str]:
    if not DATE_RE.match(value):
        return [f"since: не дата YYYY-MM-DD: {value!r}"]
    return []


def validate_cand(value: str, status_kind: str) -> List[str]:
    errors = []
    if status_kind != "живой":
        errors.append("cand: легален только при status:живой (AM-1 П3.i)")
    err = validate_predicate_value(value)
    if err:
        errors.append(f"cand: {err}")
    return errors


# ---------------------------------------------------------------------------
# Полная семантическая проверка одной шапки (id, поля, лимиты)
# ---------------------------------------------------------------------------

def validate_header_semantics(raw: RawHeader) -> ParsedHeader:
    errors: List[str] = []
    id_str = raw.id_str
    if len(id_str) > MAX_ID_LEN:
        errors.append(f"id длиннее {MAX_ID_LEN} символов: {id_str!r}")
    m = CHECK_ID_RE.match(id_str)
    if not m:
        errors.append(f"id не резолвится в форму <N> или <N>(<буква>): {id_str!r}")
        check_number = -1
        letter = None
    else:
        check_number = int(m.group(1))
        letter = m.group(2)

    fields, order_seen, field_errors = parse_header_fields(raw.fields_raw)
    errors.extend(field_errors)

    if len(order_seen) + 1 > MAX_FIELDS_TOTAL:  # +1 за CHK
        errors.append(f"полей больше {MAX_FIELDS_TOTAL}: {len(order_seen) + 1}")

    for req in REQUIRED_FIELDS:
        if req not in fields:
            errors.append(f"обязательное поле отсутствует: {req}")

    status_kind = "неизвестно"
    if "src" in fields:
        errors.extend(validate_src(fields["src"]))
    if "pred" in fields:
        err = validate_predicate_value(fields["pred"])
        if err:
            errors.append(f"pred: {err}")
    if "rules" in fields:
        errors.extend(validate_rules(fields["rules"]))
    if "status" in fields:
        st_errors, status_kind, _guard = validate_status(fields["status"])
        errors.extend(st_errors)
    if "cand" in fields:
        errors.extend(validate_cand(fields["cand"], status_kind))
    if "since" in fields:
        errors.extend(validate_since(fields["since"]))
    if "note" in fields:
        errors.extend(validate_note(fields["note"]))

    # Лимит длины строки шапки в UTF-8 байтах (включая '<!--CHK '/'-->' --
    # реконструируем итоговую строку как она стоит в файле).
    full_line = f"<!--CHK {id_str}|{raw.fields_raw}-->"
    line_bytes = len(full_line.encode("utf-8"))
    if line_bytes > MAX_HEADER_BYTES:
        errors.append(f"шапка длиннее {MAX_HEADER_BYTES} Б UTF-8: {line_bytes} Б")

    return ParsedHeader(
        line_no=raw.line_no, id_str=id_str, check_number=check_number,
        subitem_letter=letter, fields=fields, field_order_seen=order_seen,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Позиционные инварианты AM-1 П1/П2/П3
# ---------------------------------------------------------------------------

def _stars_between(lines: List[str], from_line: int, to_line_exclusive: int) -> int:
    return sum(lines[i].count("**") for i in range(from_line, to_line_exclusive))


def validate_header_position(
    ph: ParsedHeader, lines: List[str], titles_by_number: Dict[int, CheckTitle],
) -> List[str]:
    errors: List[str] = []
    title = titles_by_number.get(ph.check_number)
    if title is None:
        errors.append(f"шапка {ph.id_str}: чек {ph.check_number} не найден в тексте")
        return errors

    # AM-1 П3: счёт '**' от начала чека до строки шапки должен быть чётным
    # (шапка не внутри незакрытой пары **).
    stars = _stars_between(lines, title.title_start, ph.line_no)
    if stars % 2 != 0:
        errors.append(
            f"шапка {ph.id_str}: находится внутри незакрытой пары ** "
            f"(счёт ** = {stars})"
        )

    if ph.subitem_letter is None:
        # Шапка чека: П1 -- первая строка ПОСЛЕ строки с закрывающим **.
        expected_line = title.title_close + 1
        if ph.line_no != expected_line:
            errors.append(
                f"шапка чека {ph.id_str}: не на первой строке после "
                f"закрывающего ** заголовка (строка {ph.line_no + 1}, "
                f"ожидалась {expected_line + 1})"
            )
    else:
        # Под-шапка подпункта: П2 -- только перед маркером, начинающим
        # строку; следующая (после шапки) строка обязана начинаться
        # именно с "(<буква>)".
        next_line_idx = ph.line_no + 1
        marker = f"({ph.subitem_letter})"
        if next_line_idx >= len(lines) or not lines[next_line_idx].lstrip().startswith(marker):
            errors.append(
                f"под-шапка {ph.id_str}: не перед подпунктом, чей маркер "
                f"начинает строку (П2 -- вплетённые маркеры под-шапки не "
                f"получают)"
            )
    return errors


def validate_ids_unique(headers: List[ParsedHeader]) -> List[str]:
    errors = []
    counts: Dict[str, int] = {}
    for h in headers:
        counts[h.id_str] = counts.get(h.id_str, 0) + 1
    for id_str, c in counts.items():
        if c > MAX_HEADERS_PER_ID:
            errors.append(f"больше {MAX_HEADERS_PER_ID} шапки на id {id_str!r}: {c}")
    return errors


def validate_no_hardcoded_deploy_path(source_text: str) -> List[str]:
    """AM-3.6: захардкоженный деплой-путь в исходнике инструмента --
    дефект формы. Ищем ЛИТЕРАЛЬНЫЙ абсолютный путь (буква диска + ':' +
    слэш(и) + 'AO3_tests'), не голое упоминание имени/оси/деплоя в
    прозе (docstring может свободно называть 'ao3'/'AO3' как имя)."""
    pat = re.compile(r"[A-Za-z]:[\\/]{1,2}AO3_tests", re.IGNORECASE)
    if pat.search(source_text):
        return ["в исходнике calibration_prepass.py обнаружен захардкоженный "
                "путь к внешнему деплою (AM-3.6)"]
    return []


def validate_rules_forward(headers: List[ParsedHeader], rule_coverage_text: str) -> List[str]:
    """Каждая RC§N/token шапок резолвится: секция N существует, token
    встречается словом внутри её блока текста."""
    errors: List[str] = []
    sections = _split_rule_coverage_sections(rule_coverage_text)
    for h in headers:
        rules_val = h.fields.get("rules")
        if not rules_val:
            continue
        for entry in rules_val.split(","):
            m = RULES_ENTRY_RE.match(entry)
            if not m:
                continue  # уже сообщено validate_rules
            n, token = int(m.group(1)), m.group(2)
            if n not in sections:
                errors.append(
                    f"rules: {h.id_str}: RC§{n} -- секции {n} нет в RULE_COVERAGE.md"
                )
                continue
            if not re.search(rf"\b{re.escape(token)}\b", sections[n]):
                errors.append(
                    f"rules: {h.id_str}: RC§{n}/{token} -- token не найден в секции {n}"
                )
    return errors


def _split_rule_coverage_sections(text: str) -> Dict[int, str]:
    """N -> текст блока секции '## N. ...' до следующего '## '."""
    heading_re = re.compile(r"^## (\d+)\. ", re.MULTILINE)
    matches = list(heading_re.finditer(text))
    sections: Dict[int, str] = {}
    for i, m in enumerate(matches):
        n = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[n] = text[start:end]
    return sections


def validate_rules_backward(rule_coverage_text: str, valid_check_numbers: set) -> List[str]:
    """Каждое 'чек N' в RULE_COVERAGE.md резолвится в id протокола."""
    errors = []
    for m in re.finditer(r"чек\s+(\d+)", rule_coverage_text):
        n = int(m.group(1))
        if n not in valid_check_numbers:
            errors.append(
                f"RULE_COVERAGE.md ссылается на 'чек {n}', которого нет в протоколе"
            )
    return errors


def validate_line_coverage(
    titles: List[CheckTitle], bounds: Tuple[int, int],
) -> List[str]:
    """A8.3: ни одна строка тела не остаётся вне диапазона -- каждая
    непустая строка чек-листа принадлежит РОВНО одному чеку (диапазоны
    чеков уже сплошные по построению check_ranges; проверяем только,
    что сами диапазоны покрывают [bounds) без дыр -- т.е. что титулы
    отсортированы и первый начинается с bounds[0])."""
    start, end = bounds
    errors = []
    ordered = sorted(titles, key=lambda t: t.title_start)
    if not ordered:
        return ["FORM: покрытие строк -- в чек-листе не найдено ни одного чека"]
    covered_end = start
    for t in ordered:
        if t.title_start < covered_end:
            errors.append(f"FORM: покрытие строк -- чек {t.number} начинается раньше "
                           f"конца предыдущего диапазона")
        covered_end = t.title_start
    if ordered[-1].title_start >= end:
        errors.append("FORM: покрытие строк -- последний чек начинается за концом "
                       "секции чек-листа")
    return errors


# ---------------------------------------------------------------------------
# --check-form: оркестрация
# ---------------------------------------------------------------------------

@dataclass
class CheckFormResult:
    defects: List[str]
    titles: List[CheckTitle]
    headers: List[ParsedHeader]


def run_check_form(
    protocol_path: Path, rule_coverage_path: Path, require_all: bool,
) -> CheckFormResult:
    lines, bounds, titles = load_protocol_structure(protocol_path)
    titles_by_number = {t.number: t for t in titles}

    defects: List[str] = []
    defects.extend(validate_check_numbering(titles))
    defects.extend(validate_line_coverage(titles, bounds))

    raw_headers = find_raw_headers(lines, bounds)
    parsed_headers: List[ParsedHeader] = []
    for raw in raw_headers:
        if raw.malformed:
            defects.append(f"FORM: строка {raw.line_no + 1}: {raw.malformed_reason}")
            continue
        ph = validate_header_semantics(raw)
        parsed_headers.append(ph)
        for e in ph.errors:
            defects.append(f"FORM: шапка {ph.id_str} (строка {ph.line_no + 1}): {e}")

    defects.extend(f"FORM: {e}" for e in validate_ids_unique(parsed_headers))

    for ph in parsed_headers:
        if ph.check_number == -1:
            continue
        for e in validate_header_position(ph, lines, titles_by_number):
            defects.append(f"FORM: {e}")

    # id должен совпадать с номером в тексте (A1 инвариант "чек-лист --
    # единственный дом номеров"): номер части id обязан существовать
    # среди titles; для подпунктов -- принадлежать диапазону чека.
    for ph in parsed_headers:
        if ph.check_number != -1 and ph.check_number not in titles_by_number:
            defects.append(
                f"FORM: шапка {ph.id_str}: номер {ph.check_number} не совпадает ни "
                f"с одним номером чека в тексте"
            )

    source_text = Path(__file__).read_text(encoding="utf-8")
    defects.extend(f"FORM: {e}" for e in validate_no_hardcoded_deploy_path(source_text))

    rule_coverage_text = None
    if rule_coverage_path.exists():
        rule_coverage_text = rule_coverage_path.read_text(encoding="utf-8", errors="replace")
        defects.extend(f"FORM: {e}" for e in
                        validate_rules_forward(parsed_headers, rule_coverage_text))
        valid_numbers = set(titles_by_number.keys())
        defects.extend(f"FORM: {e}" for e in
                        validate_rules_backward(rule_coverage_text, valid_numbers))
    else:
        defects.append(f"FORM: RULE_COVERAGE не найден по пути {rule_coverage_path}")

    if require_all:
        headered_numbers = {ph.check_number for ph in parsed_headers if ph.subitem_letter is None}
        for n in titles_by_number:
            if n not in headered_numbers:
                defects.append(f"FORM: --require-all: чек {n} без шапки чека")

    return CheckFormResult(defects=defects, titles=titles, headers=parsed_headers)


def render_check_form(result: CheckFormResult) -> str:
    if not result.defects:
        return f"FORM: OK (0 дефектов; {len(result.titles)} чеков, {len(result.headers)} шапок)"
    lines = list(result.defects)
    lines.append(f"FORM: ИТОГО дефектов: {len(result.defects)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Резолюция внешнего деплоя (AM-3)
# ---------------------------------------------------------------------------

@dataclass
class DeployResolution:
    name: str
    path: Optional[str]
    source: str  # "CLI --deploy" | "delegation.config.yaml" | "env" | "unresolved"
    exists: Optional[bool] = None  # None пока не проверено isdir


def _read_config_deploys(config_path: Path) -> Dict[str, str]:
    if yaml is None or not config_path.exists():
        return {}
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    deploys = data.get("deploys") or {}
    if not isinstance(deploys, dict):
        return {}
    return {str(k): str(v) for k, v in deploys.items()}


def resolve_deploy(
    name: str, cli_deploys: Dict[str, str], config_path: Path,
) -> DeployResolution:
    if name in cli_deploys and cli_deploys[name]:
        path = cli_deploys[name]
        return DeployResolution(name=name, path=path, source="CLI --deploy",
                                 exists=os.path.isdir(path))
    config_deploys = _read_config_deploys(config_path)
    if name in config_deploys and config_deploys[name]:
        path = config_deploys[name]
        return DeployResolution(name=name, path=path, source="delegation.config.yaml",
                                 exists=os.path.isdir(path))
    env_key = "OSLLM_DEPLOY_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    env_val = os.environ.get(env_key)
    if env_val:
        return DeployResolution(name=name, path=env_val, source="env",
                                 exists=os.path.isdir(env_val))
    return DeployResolution(name=name, path=None, source="unresolved", exists=None)


# ---------------------------------------------------------------------------
# git-предикаты
# ---------------------------------------------------------------------------

def _run_git(args: List[str], cwd: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", cwd] + args, capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def git_commit_count(cwd: str, since_iso: str, until_iso: str,
                      pathspecs: Optional[List[str]] = None) -> Optional[int]:
    args = ["log", f"--since={since_iso}", f"--until={until_iso}", "--oneline"]
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    out = _run_git(args, cwd)
    if out is None:
        return None
    return len([ln for ln in out.splitlines() if ln.strip()])


def git_diff_lines_total(cwd: str, since_iso: str, until_iso: str,
                          pathspecs: Optional[List[str]] = None) -> Optional[int]:
    args = ["log", f"--since={since_iso}", f"--until={until_iso}", "--numstat",
            "--pretty=format:"]
    if pathspecs:
        args.append("--")
        args.extend(pathspecs)
    out = _run_git(args, cwd)
    if out is None:
        return None
    total = 0
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 2:
            for p in parts[:2]:
                if p.isdigit():
                    total += int(p)
    return total


# ---------------------------------------------------------------------------
# Журнальный контекст (импорт calibration_counts -- given манифеста)
# ---------------------------------------------------------------------------

@dataclass
class JournalContext:
    journal_paths: List[str]
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    parsed_lines: List[Any] = field(default_factory=list)   # cc.ParsedLine, все журналы вместе
    in_window: List[Any] = field(default_factory=list)
    unparsable_count: int = 0
    warnings: List[str] = field(default_factory=list)
    journal_missing: List[str] = field(default_factory=list)

    @property
    def in_window_count(self) -> int:
        return len(self.in_window)

    @property
    def journal_available(self) -> bool:
        """A8.5: отсутствующий журнал -> журнальные чеки ЖИВЫ (fail-closed),
        это НЕ то же самое, что присутствующий журнал с нулём событий в
        окне (A3.1 -- легитимный ПУСТ). False только когда ВСЕ заданные
        пути отсутствуют."""
        return len(self.journal_missing) < len(self.journal_paths)


def build_journal_context(
    journal_paths: List[str], window_start: Optional[datetime], window_end: Optional[datetime],
) -> JournalContext:
    ctx = JournalContext(journal_paths=journal_paths, window_start=window_start,
                          window_end=window_end)
    for path in journal_paths:
        if not os.path.exists(path):
            ctx.journal_missing.append(path)
            ctx.warnings.append(f"журнал отсутствует: {path}")
            continue
        try:
            lines = cc.load_journal(path)
        except OSError as exc:
            ctx.warnings.append(f"не удалось прочитать журнал {path}: {exc}")
            continue
        for pl in lines:
            if pl.data is None:
                ctx.unparsable_count += 1
                ctx.warnings.append(
                    f"непарсящаяся строка журнала {path}:{pl.line_no}: {pl.parse_error}"
                )
                continue
            ctx.parsed_lines.append(pl)
            if cc._in_window(pl, window_start, window_end):
                ctx.in_window.append(pl)
    return ctx


@dataclass
class EvalResult:
    alive: bool
    observed: Optional[int] = None
    denom: Optional[int] = None
    reason: str = ""
    empty_reasons_needed: bool = True  # False для always/manual/script/deploy-ЖИВ и т.п.


def _count_journal_event(ctx: JournalContext, event: str,
                          agent: Optional[str], deploy: Optional[str]) -> int:
    n = 0
    for pl in ctx.in_window:
        d = pl.data
        if d.get("event") != event:
            continue
        if agent is not None and d.get("agent") != agent:
            continue
        if deploy is not None and d.get("deploy") != deploy:
            continue
        n += 1
    return n


def _count_journal_field(ctx: JournalContext, field_name: str, value: str) -> int:
    return sum(1 for pl in ctx.in_window if str(pl.data.get(field_name)) == value)


def detect_parallel_groups(ctx: JournalContext) -> int:
    """Число ГРУПП delegated с пересекающимися окнами delegated..(accepted|
    rejected|escalated) и РАЗНЫМИ worker_ref (норма R4, 2026-08-09; чек
    13(к)). Упрощённый, но детерминированный алгоритм: интервалы строятся
    по task_id (delegated ts -> ts первого следующего lifecycle-события
    того же task_id, или конец окна, если такого нет); группа
    засчитывается, если хотя бы два интервала РАЗНЫХ task_id/worker_ref
    пересекаются."""
    opens: List[Tuple[datetime, datetime, str]] = []  # (start, end, task_id)
    by_task: Dict[str, List[Any]] = {}
    for pl in ctx.parsed_lines:
        tid = pl.data.get("task_id")
        if isinstance(tid, str) and tid:
            by_task.setdefault(tid, []).append(pl)
    for tid, group in by_task.items():
        group_sorted = sorted(group, key=lambda pl: (pl.ts or datetime.min, pl.line_no))
        delegated_events = [pl for pl in group_sorted if pl.data.get("event") == "delegated"]
        closers = [pl for pl in group_sorted
                   if pl.data.get("event") in ("accepted", "rejected", "escalated")]
        for d_pl in delegated_events:
            if d_pl.ts is None:
                continue
            end_ts = None
            for c_pl in closers:
                if c_pl.ts is not None and c_pl.ts >= d_pl.ts:
                    end_ts = c_pl.ts
                    break
            if end_ts is None:
                end_ts = ctx.window_end or d_pl.ts
            opens.append((d_pl.ts, end_ts, tid))
    groups = 0
    for i in range(len(opens)):
        for j in range(i + 1, len(opens)):
            s1, e1, t1 = opens[i]
            s2, e2, t2 = opens[j]
            if t1 == t2:
                continue
            if s1 < e2 and s2 < e1:
                groups += 1
    return groups


@dataclass
class RunContext:
    journal_ctx: JournalContext
    repo_root: str
    window_start_iso: str
    window_end_iso: str
    cli_deploys: Dict[str, str]
    config_path: Path
    deploy_cache: Dict[str, DeployResolution] = field(default_factory=dict)

    def deploy(self, name: str) -> DeployResolution:
        if name not in self.deploy_cache:
            self.deploy_cache[name] = resolve_deploy(name, self.cli_deploys, self.config_path)
        return self.deploy_cache[name]


def evaluate_predicate(value: str, run_ctx: RunContext) -> EvalResult:
    ctx = run_ctx.journal_ctx
    if value == "always":
        return EvalResult(alive=True, reason="always", empty_reasons_needed=False)

    if value.startswith("manual:"):
        why = value[len("manual:"):]
        return EvalResult(alive=True, reason=f"manual:{why} -- не читается пре-пассом "
                                              f"(цена/разрешения), всегда жив",
                           empty_reasons_needed=False)

    if value.startswith("script:"):
        name = value[len("script:"):]
        cmd = KNOWN_SCRIPT_COMMANDS.get(name, f"см. текст чека (script:{name})")
        return EvalResult(alive=True, reason=f"script:{name} -- команда: {cmd}",
                           empty_reasons_needed=False)

    if value.startswith("journal.") and not ctx.journal_available:
        # A8.5: отсутствующий журнал (ВСЕ заданные пути) -> журнальные
        # чеки ЖИВЫ (fail-closed) -- отличается от присутствующего
        # журнала с нулём событий в окне (A3.1, легитимный ПУСТ).
        return EvalResult(alive=True, reason=f"{value} -- журнал отсутствует, "
                                               f"ЖИВ (fail-closed)")

    if value == "journal.any":
        denom = ctx.in_window_count
        observed = denom
        return EvalResult(alive=observed > 0, observed=observed, denom=denom,
                           reason="journal.any")

    if value.startswith("journal.event:"):
        rest = value[len("journal.event:"):]
        parts = rest.split(",")
        event = parts[0]
        agent = None
        deploy_name = None
        for p in parts[1:]:
            if p.startswith("agent="):
                agent = p[len("agent="):]
            elif p.startswith("deploy="):
                deploy_name = p[len("deploy="):]
        observed = _count_journal_event(ctx, event, agent, deploy_name)
        denom = ctx.in_window_count
        return EvalResult(alive=observed > 0, observed=observed, denom=denom,
                           reason=value)

    if value.startswith("journal.field:"):
        rest = value[len("journal.field:"):]
        f_name, _, f_val = rest.partition("=")
        observed = _count_journal_field(ctx, f_name, f_val)
        denom = ctx.in_window_count
        return EvalResult(alive=observed > 0, observed=observed, denom=denom,
                           reason=value)

    if value == "journal.parallel_groups":
        observed = detect_parallel_groups(ctx)
        denom = ctx.in_window_count
        return EvalResult(alive=observed > 0, observed=observed, denom=denom,
                           reason="journal.parallel_groups")

    if value == "git.any":
        n = git_commit_count(run_ctx.repo_root, run_ctx.window_start_iso,
                              run_ctx.window_end_iso)
        if n is None:
            return EvalResult(alive=True, reason="git.any -- git недоступен, ЖИВ "
                                                   "(fail-closed)")
        return EvalResult(alive=n > 0, observed=n, denom=None, reason="git.any")

    if value.startswith("git.paths:"):
        rest = value[len("git.paths:"):]
        deploy_suffix = None
        for suf in ("@OS", "@AO3"):
            if rest.endswith(suf):
                deploy_suffix = suf
                rest = rest[: -len(suf)]
        globs = rest.split(",")
        n = git_commit_count(run_ctx.repo_root, run_ctx.window_start_iso,
                              run_ctx.window_end_iso, pathspecs=globs)
        if n is None:
            return EvalResult(alive=True, reason=f"{value} -- git недоступен, ЖИВ "
                                                   f"(fail-closed)")
        return EvalResult(alive=n > 0, observed=n, denom=None,
                           reason=value + (f" ({deploy_suffix})" if deploy_suffix else ""))

    if value.startswith("git.diff_lines:>"):
        threshold = int(value[len("git.diff_lines:>"):])
        n = git_diff_lines_total(run_ctx.repo_root, run_ctx.window_start_iso,
                                  run_ctx.window_end_iso)
        if n is None:
            return EvalResult(alive=True, reason=f"{value} -- git недоступен, ЖИВ "
                                                   f"(fail-closed)")
        return EvalResult(alive=n > threshold, observed=n, denom=None, reason=value)

    if value.startswith("path.exists:"):
        p = value[len("path.exists:"):]
        full = p if os.path.isabs(p) else os.path.join(run_ctx.repo_root, p)
        exists = os.path.exists(full)
        if not exists:
            # A3 edge 3: предикат на несуществующий источник -- ЖИВ
            # (fail-closed), причина дословно.
            return EvalResult(alive=True, reason=f"{value} -- путь не существует, "
                                                   f"ЖИВ (fail-closed)")
        return EvalResult(alive=True, reason=f"{value} -- путь существует")

    if value.startswith("deploy.exists:"):
        name = value[len("deploy.exists:"):]
        res = run_ctx.deploy(name)
        if res.path is None:
            # AM-3(4): не разрешено -> секция читается целиком.
            control = os.path.isdir(run_ctx.repo_root)
            return EvalResult(
                alive=True,
                reason=(f"деплой '{name}' не сконфигурирован -- секция читается "
                        f"целиком (позитивный контроль isdir(наш корень)={control})"),
            )
        if not res.exists:
            # AM-3(5): путь отсутствует -> ПУСТ + позитивный контроль той
            # же формы по корню нашего репо.
            control = os.path.isdir(run_ctx.repo_root)
            return EvalResult(
                alive=False, observed=0, denom=1,
                reason=(f"деплой '{name}' сконфигурирован ({res.source}) по пути "
                        f"{res.path!r}, но путь не существует -- ПУСТ "
                        f"(позитивный контроль isdir(наш корень)={control})"),
            )
        return EvalResult(
            alive=True,
            reason=f"деплой '{name}' обнаружен по пути {res.path!r} ({res.source})",
        )

    return EvalResult(alive=True, reason=f"неизвестный предикат {value!r} -- ЖИВ "
                                           f"(fail-closed)")


# ---------------------------------------------------------------------------
# Оркестрация оконного прогона: вердикты по чекам
# ---------------------------------------------------------------------------

@dataclass
class CheckVerdict:
    check_number: int
    id_str: str
    verdict: str  # ЖИВ | ПУСТ | РЕТИРОВАН | ДЕФЕРРЕД
    line_range: Tuple[int, int]  # 1-indexed, включительно
    byte_size: int
    reason: str
    has_header: bool
    perevzvedenie: Optional[str] = None


@dataclass
class SubitemVerdict:
    id_str: str
    verdict: str
    reason: str
    byte_size: int = 0
    perevzvedenie: Optional[str] = None


def build_window_report(
    protocol_path: Path, run_ctx: RunContext,
) -> Dict[str, Any]:
    lines, bounds, titles = load_protocol_structure(protocol_path)
    titles_by_number = {t.number: t for t in titles}
    ranges = check_ranges(titles, bounds[1])
    offsets = line_byte_offsets(lines)
    total_bytes = offsets[-1]

    raw_headers = find_raw_headers(lines, bounds)
    parsed_headers = [validate_header_semantics(r) for r in raw_headers if not r.malformed]
    top_header_by_number: Dict[int, ParsedHeader] = {}
    sub_headers_by_number: Dict[int, List[ParsedHeader]] = {}
    for ph in parsed_headers:
        if ph.errors or ph.check_number == -1:
            continue
        if ph.subitem_letter is None:
            top_header_by_number[ph.check_number] = ph
        else:
            sub_headers_by_number.setdefault(ph.check_number, []).append(ph)

    check_verdicts: List[CheckVerdict] = []
    subitem_verdicts: Dict[int, List[SubitemVerdict]] = {}
    perevzvedenie_lines: List[str] = []

    for number in sorted(ranges.keys()):
        start, end = ranges[number]  # 0-indexed inclusive
        byte_size = offsets[end + 1] - offsets[start]
        header = top_header_by_number.get(number)
        line_range = (start + 1, end + 1)

        if header is None:
            check_verdicts.append(CheckVerdict(
                check_number=number, id_str=str(number), verdict="ЖИВ",
                line_range=line_range, byte_size=byte_size,
                reason="чек без шапки -- ЖИВ (fail-closed, A3 edge 2)",
                has_header=False,
            ))
        else:
            status_val = header.fields.get("status", STATUS_LIVE)
            st_errors, status_kind, guard = validate_status(status_val)
            if status_kind == "ретирован":
                m = STATUS_RETIRED_RE.match(status_val)
                date_s, guard_id, liveness = m.group(1), m.group(2), m.group(3)
                check_verdicts.append(CheckVerdict(
                    check_number=number, id_str=header.id_str, verdict="РЕТИРОВАН",
                    line_range=line_range, byte_size=byte_size,
                    reason=(f"ретирован {date_s}; сторож:{guard_id}; "
                            f"живость:{liveness}"),
                    has_header=True,
                ))
            elif status_kind == "деферред":
                trigger_pred = status_val[len(STATUS_DEFERRED_PREFIX):]
                ev = evaluate_predicate(trigger_pred, run_ctx)
                cv = CheckVerdict(
                    check_number=number, id_str=header.id_str, verdict="ДЕФЕРРЕД",
                    line_range=line_range, byte_size=byte_size,
                    reason=f"деферред, триггер: {trigger_pred}",
                    has_header=True,
                )
                if ev.alive:
                    msg = (f"ПЕРЕВЗВЕДЕНИЕ: чек {header.id_str} -- деферред-триггер "
                           f"истинен ({trigger_pred}) -> находка прогона")
                    cv.perevzvedenie = msg
                    perevzvedenie_lines.append(msg)
                check_verdicts.append(cv)
            else:
                pred_val = header.fields.get("pred", "always")
                ev = evaluate_predicate(pred_val, run_ctx)
                verdict = "ЖИВ" if ev.alive else "ПУСТ"
                reason = ev.reason
                if not ev.alive and ev.empty_reasons_needed:
                    reason = (f"{ev.reason} -> {ev.observed if ev.observed is not None else 0} "
                              f"из {ev.denom if ev.denom is not None else 0} строк окна")
                cv = CheckVerdict(
                    check_number=number, id_str=header.id_str, verdict=verdict,
                    line_range=line_range, byte_size=byte_size, reason=reason,
                    has_header=True,
                )
                cand_val = header.fields.get("cand")
                if cand_val:
                    cand_ev = evaluate_predicate(cand_val, run_ctx)
                    if cand_ev.alive:
                        msg = (f"ПЕРЕВЗВЕДЕНИЕ: чек {header.id_str} -- "
                               f"кандидат-ретирования, триггер истинен ({cand_val}) "
                               f"-> находка прогона")
                        cv.perevzvedenie = msg
                        perevzvedenie_lines.append(msg)
                check_verdicts.append(cv)

        sub_list: List[SubitemVerdict] = []
        # Диапазоны подпунктов (только line-starting -- единственные, у
        # кого вообще есть под-шапка, П2): от своей строки-маркера до
        # строки ПЕРЕД следующим под-пунктом или до конца диапазона чека.
        # Нужны для адресного снятия байт РЕТИРОВАННОГО/ПУСТОГО
        # ФРАГМЕНТА из "к чтению" даже когда родитель в целом ЖИВ
        # (K1-K4 -- байтовый эффект ретирования именно на этом уровне).
        sorted_subs = sorted(sub_headers_by_number.get(number, []), key=lambda h: h.line_no)
        sub_ranges: Dict[str, Tuple[int, int]] = {}
        for idx, sh in enumerate(sorted_subs):
            sub_start = sh.line_no
            sub_end = sorted_subs[idx + 1].line_no - 1 if idx + 1 < len(sorted_subs) else end
            sub_ranges[sh.id_str] = (sub_start, sub_end)

        for sh in sorted_subs:
            sub_start, sub_end = sub_ranges[sh.id_str]
            sub_byte_size = offsets[sub_end + 1] - offsets[sub_start]
            sub_status_val = sh.fields.get("status", STATUS_LIVE)
            _e, sub_kind, _g = validate_status(sub_status_val)
            if sub_kind == "ретирован":
                m = STATUS_RETIRED_RE.match(sub_status_val)
                date_s, guard_id, liveness = m.group(1), m.group(2), m.group(3)
                sub_list.append(SubitemVerdict(
                    id_str=sh.id_str, verdict="РЕТИРОВАН", byte_size=sub_byte_size,
                    reason=f"ретирован {date_s}; сторож:{guard_id}; живость:{liveness}",
                ))
                continue
            if sub_kind == "деферред":
                trigger_pred = sub_status_val[len(STATUS_DEFERRED_PREFIX):]
                ev = evaluate_predicate(trigger_pred, run_ctx)
                sv = SubitemVerdict(id_str=sh.id_str, verdict="ДЕФЕРРЕД",
                                     byte_size=sub_byte_size,
                                     reason=f"деферред, триггер: {trigger_pred}")
                if ev.alive:
                    msg = (f"ПЕРЕВЗВЕДЕНИЕ: чек {sh.id_str} -- деферред-триггер "
                           f"истинен ({trigger_pred}) -> находка прогона")
                    sv.perevzvedenie = msg
                    perevzvedenie_lines.append(msg)
                sub_list.append(sv)
                continue
            pred_val = sh.fields.get("pred", "always")
            ev = evaluate_predicate(pred_val, run_ctx)
            verdict = "ЖИВ" if ev.alive else "ПУСТ"
            reason = ev.reason
            if not ev.alive and ev.empty_reasons_needed:
                reason = (f"{ev.reason} -> {ev.observed if ev.observed is not None else 0} "
                          f"из {ev.denom if ev.denom is not None else 0} строк окна")
            sv = SubitemVerdict(id_str=sh.id_str, verdict=verdict, byte_size=sub_byte_size,
                                 reason=reason)
            cand_val = sh.fields.get("cand")
            if cand_val:
                cand_ev = evaluate_predicate(cand_val, run_ctx)
                if cand_ev.alive:
                    msg = (f"ПЕРЕВЗВЕДЕНИЕ: чек {sh.id_str} -- кандидат-ретирования, "
                           f"триггер истинен ({cand_val}) -> находка прогона")
                    sv.perevzvedenie = msg
                    perevzvedenie_lines.append(msg)
            sub_list.append(sv)
        if sub_list:
            subitem_verdicts[number] = sub_list

    # ИТОГ: байты считаются на уровне АДРЕСНОГО ДИАПАЗОНА -- если у чека
    # есть под-шапки, его собственный диапазон делится на "остаток"
    # (governed родительским вердиктом) и байты каждого подпункта
    # (governed СВОИМ вердиктом); чек без под-шапок -- как раньше, целиком
    # по своему вердикту.
    to_read_bytes = 0
    for cv in check_verdicts:
        subs = subitem_verdicts.get(cv.check_number, [])
        subs_total_bytes = sum(s.byte_size for s in subs)
        if cv.verdict in ("ЖИВ", "ДЕФЕРРЕД"):
            remainder = cv.byte_size - subs_total_bytes
            to_read_bytes += remainder
            to_read_bytes += sum(s.byte_size for s in subs if s.verdict in ("ЖИВ", "ДЕФЕРРЕД"))
        # РЕТИРОВАН/ПУСТ на верхнем уровне -- ни остаток, ни подпункты не
        # читаются (статус сильнее, A3 edge 6).
    # Диапазоны вне чеков (заголовок протокола, преамбула чек-листа,
    # "Завершение прогона") всегда читаются -- добавляем остаток файла.
    checks_total_bytes = sum(cv.byte_size for cv in check_verdicts)
    outside_checks_bytes = total_bytes - checks_total_bytes
    to_read_bytes += outside_checks_bytes

    empty_lines: List[str] = [
        f"{cv.id_str} ПУСТ: {cv.reason}" for cv in check_verdicts if cv.verdict == "ПУСТ"
    ]
    for number, subs in subitem_verdicts.items():
        for sv in subs:
            if sv.verdict == "ПУСТ":
                empty_lines.append(f"{sv.id_str} ПУСТ: {sv.reason}")

    alive_count = sum(1 for cv in check_verdicts if cv.verdict in ("ЖИВ", "ДЕФЕРРЕД"))

    return {
        "titles": titles,
        "check_verdicts": check_verdicts,
        "subitem_verdicts": subitem_verdicts,
        "total_bytes": total_bytes,
        "to_read_bytes": to_read_bytes,
        "alive_count": alive_count,
        "total_checks": len(check_verdicts),
        "empty_lines": empty_lines,
        "perevzvedenie_lines": perevzvedenie_lines,
        "journal_ctx": run_ctx.journal_ctx,
    }


# ---------------------------------------------------------------------------
# A3.8 -- режим (обычный/контрольный) и сайдкар-реестр (Р7(A))
# ---------------------------------------------------------------------------

CONTROL_TRIGGER_N = 4


def read_registry(registry_path: Path) -> List[Dict[str, Any]]:
    if not registry_path.exists():
        return []
    out = []
    with open(registry_path, "r", encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


def last_header_touching_commit(repo_root: str, protocol_rel_path: str) -> Optional[str]:
    out = _run_git(["log", "-1", "--format=%H", "-S", "<!--CHK", "--", protocol_rel_path],
                    repo_root)
    if out is None:
        return None
    out = out.strip()
    return out or None


def determine_mode(
    registry_entries: List[Dict[str, Any]], repo_root: str, protocol_rel_path: str,
    explicit_control: bool,
) -> Tuple[str, str]:
    """Возвращает (mode, reason). mode in {"обычный","КОНТРОЛЬНЫЙ"}."""
    if explicit_control:
        return "КОНТРОЛЬНЫЙ", "явный флаг --control"

    last_commit = last_header_touching_commit(repo_root, protocol_rel_path)
    prev_seen_commit = None
    normal_run_count = 0
    for entry in reversed(registry_entries):
        if entry.get("mode", "").startswith("КОНТРОЛЬНЫЙ"):
            prev_seen_commit = entry.get("last_header_commit")
            break
        normal_run_count += 1
        if "last_header_commit" in entry:
            prev_seen_commit = prev_seen_commit or entry.get("last_header_commit")

    if last_commit is not None and last_commit != prev_seen_commit and registry_entries:
        return "КОНТРОЛЬНЫЙ", f"первый прогон после правки шапок (commit {last_commit[:8]})"

    if (normal_run_count + 1) % CONTROL_TRIGGER_N == 0:
        return "КОНТРОЛЬНЫЙ", f"периодический триггер N={CONTROL_TRIGGER_N}"

    return "обычный", f"до контрольного ({CONTROL_TRIGGER_N - ((normal_run_count + 1) % CONTROL_TRIGGER_N)} прогонов)"


def run_control_check(report: Dict[str, Any]) -> Tuple[int, int, List[str]]:
    """A3.8(в): каждый ПУСТ-вердикт сверяется с фактом (здесь -- фактом
    считается сам расчёт EvalResult, т.к. предикаты уже читают ПОЛНЫЙ
    объём окна; расхождение возможно только если наблюдённое>0, но
    вердикт всё равно ПУСТ -- структурно невозможно при текущей
    реализации, поэтому расхождений 0 в штатном случае; функция
    оставлена как явный именованный детектор, D-0049). Возвращает
    (n_empty, n_discrepancies, discrepancy_lines)."""
    empties = [cv for cv in report["check_verdicts"] if cv.verdict == "ПУСТ"]
    for subs in report["subitem_verdicts"].values():
        empties.extend(sv for sv in subs if sv.verdict == "ПУСТ")
    discrepancies: List[str] = []
    for e in empties:
        observed_marker = " из " in e.reason
        if not observed_marker:
            discrepancies.append(
                f"{e.id_str}: ПУСТ без явного счётчика 'X из Y' в причине -- "
                f"расхождение формы (класс F-30)"
            )
    return len(empties), len(discrepancies), discrepancies


# ---------------------------------------------------------------------------
# Рендер оконного отчёта
# ---------------------------------------------------------------------------

def render_window_report(
    report: Dict[str, Any], window_start_iso: str, window_end_iso: str,
    mode: str, mode_reason: str, journal_paths: List[str], protocol_path: Path,
    control_result: Optional[Tuple[int, int, List[str]]] = None,
) -> str:
    out: List[str] = []
    out.append(f"ОКНО: {window_start_iso} .. {window_end_iso}")
    out.append(f"РЕЖИМ: {mode} ({mode_reason})")

    out.append("\n=== КОНТРОЛЬ ИСТОЧНИКОВ ===")
    ctx = report["journal_ctx"]
    for jp in journal_paths:
        exists = os.path.exists(jp)
        if exists:
            total = sum(1 for _ in open(jp, "r", encoding="utf-8", errors="replace"))
        else:
            total = 0
        out.append(f"  журнал {jp}: exists={exists}, строк_всего={total}, "
                    f"в_окне={ctx.in_window_count}, непарсящихся={ctx.unparsable_count}")
    protocol_control = protocol_path.exists()
    out.append(f"  позитивный контроль (os.path.exists на заведомо существующем "
               f"{protocol_path}): {protocol_control}")
    if ctx.warnings:
        for w in ctx.warnings[:20]:
            out.append(f"  WARN: {w}")

    verdict_by_number = {cv.check_number: cv for cv in report["check_verdicts"]}
    for section_no in sorted(SECTION_NAMES):
        numbers = sorted(n for n, s in SECTION_BY_CHECK.items() if s == section_no
                          and n in verdict_by_number)
        if not numbers:
            continue
        out.append(f"\n=== {SECTION_NAMES[section_no]} ===")
        for n in numbers:
            cv = verdict_by_number[n]
            out.append(f"  {cv.id_str}: {cv.verdict} | строки {cv.line_range[0]}-"
                       f"{cv.line_range[1]} ({cv.byte_size} Б) | {cv.reason}")
            for sv in report["subitem_verdicts"].get(n, []):
                out.append(f"    {sv.id_str}: {sv.verdict} | {sv.reason}")

    out.append("\n=== ПУСТЫЕ ЧЕКИ (обязательная явная отметка) ===")
    if report["empty_lines"]:
        for ln in report["empty_lines"]:
            out.append(f"  {ln}")
    else:
        out.append("  (нет пустых чеков в этом окне)")

    out.append("\n=== ПЕРЕВЗВЕДЕНИЯ (находки прогона) ===")
    if report["perevzvedenie_lines"]:
        for ln in report["perevzvedenie_lines"]:
            out.append(f"  {ln}")
    else:
        out.append("  (перевзведений нет)")

    if control_result is not None:
        n_empty, n_disc, disc_lines = control_result
        out.append("\n=== КОНТРОЛЬНЫЙ ПРОЧИТ (A3.8) ===")
        out.append(f"  контрольный прочит: {n_empty} ПУСТ-вердиктов, расхождений {n_disc}")
        for ln in disc_lines:
            out.append(f"  РАСХОЖДЕНИЕ: {ln}")

    total = report["total_bytes"]
    to_read = report["to_read_bytes"]
    pct = (to_read / total * 100.0) if total else 0.0
    gate_diff = to_read - GATE_A_THRESHOLD_BYTES
    gate_verdict = "ВЗЯТ" if to_read <= GATE_A_THRESHOLD_BYTES else "НЕ ВЗЯТ"
    sign = "+" if gate_diff >= 0 else ""
    out.append(
        f"\nИТОГ: живых {report['alive_count']}/{report['total_checks']} · "
        f"к чтению {to_read} Б из {total} Б ({pct:.1f}%) · "
        f"гейт (а) ≤{GATE_A_THRESHOLD_BYTES} Б: {gate_verdict} ({sign}{gate_diff} Б)"
    )
    return "\n".join(out)


def write_registry_entry(
    registry_path: Path, window_start_iso: str, window_end_iso: str, mode: str,
    mode_reason: str, report: Dict[str, Any], last_commit: Optional[str],
) -> None:
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "window_start": window_start_iso,
        "window_end": window_end_iso,
        "mode": f"{mode} ({mode_reason})",
        "last_header_commit": last_commit,
        "alive_count": report["alive_count"],
        "total_checks": report["total_checks"],
        "to_read_bytes": report["to_read_bytes"],
        "total_bytes": report["total_bytes"],
        "verdicts": {cv.id_str: cv.verdict for cv in report["check_verdicts"]},
    }
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_deploys(items: Optional[List[str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"--deploy требует форму имя=путь, получено {item!r}")
        name, _, path = item.partition("=")
        if not name:
            raise ValueError(f"--deploy: пустое имя в {item!r}")
        out[name] = path
    return out


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0] if __doc__ else "",
    )
    p.add_argument("--window-start", default=None, help="ISO ts, включительно (>=)")
    p.add_argument("--window-end", default=None,
                    help="ISO ts, исключительно (<); по умолчанию -- системное время запуска")
    p.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    p.add_argument("--journal", action="append", default=None,
                    help="путь к routing-log.jsonl (можно повторять; по умолчанию -- OS-журнал)")
    p.add_argument("--deploy", action="append", default=None,
                    help="имя=путь резолюции внешнего деплоя (AM-3; можно повторять)")
    p.add_argument("--rule-coverage", default=str(DEFAULT_RULE_COVERAGE))
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    p.add_argument("--json", action="store_true")
    p.add_argument("--check-form", action="store_true")
    p.add_argument("--require-all", action="store_true")
    p.add_argument("--control", action="store_true")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    protocol_path = Path(args.protocol)
    rule_coverage_path = Path(args.rule_coverage)

    if args.check_form:
        try:
            result = run_check_form(protocol_path, rule_coverage_path, args.require_all)
        except ProtocolError as exc:
            print(f"calibration_prepass: {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps({
                "defects": result.defects,
                "checks": len(result.titles),
                "headers": len(result.headers),
            }, ensure_ascii=False, indent=2))
        else:
            print(render_check_form(result))
        return 1 if result.defects else 0

    if not args.window_start:
        print("calibration_prepass: нужен --window-start (или --check-form)",
              file=sys.stderr)
        return 2

    window_start = cc.parse_ts(args.window_start)
    if window_start is None:
        print(f"calibration_prepass: невалидный --window-start {args.window_start!r}",
              file=sys.stderr)
        return 2
    if args.window_end:
        window_end = cc.parse_ts(args.window_end)
        if window_end is None:
            print(f"calibration_prepass: невалидный --window-end {args.window_end!r}",
                  file=sys.stderr)
            return 2
        window_end_iso = args.window_end
    else:
        window_end = datetime.now()
        window_end_iso = window_end.isoformat(timespec="seconds")

    if window_end < window_start:
        print("calibration_prepass: --window-end раньше --window-start", file=sys.stderr)
        return 2

    try:
        cli_deploys = parse_deploys(args.deploy)
    except ValueError as exc:
        print(f"calibration_prepass: {exc}", file=sys.stderr)
        return 2

    journal_paths = args.journal or [str(DEFAULT_JOURNAL)]
    journal_ctx = build_journal_context(journal_paths, window_start, window_end)

    run_ctx = RunContext(
        journal_ctx=journal_ctx, repo_root=str(REPO_ROOT),
        window_start_iso=args.window_start, window_end_iso=window_end_iso,
        cli_deploys=cli_deploys, config_path=Path(args.config),
    )

    try:
        protocol_rel = str(protocol_path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        protocol_rel = str(protocol_path)

    registry_path = Path(args.registry)
    registry_entries = read_registry(registry_path)
    mode, mode_reason = determine_mode(
        registry_entries, str(REPO_ROOT), protocol_rel, args.control,
    )

    try:
        report = build_window_report(protocol_path, run_ctx)
    except ProtocolError as exc:
        print(f"calibration_prepass: {exc}", file=sys.stderr)
        return 2

    control_result = None
    if mode == "КОНТРОЛЬНЫЙ":
        control_result = run_control_check(report)

    last_commit = last_header_touching_commit(str(REPO_ROOT), protocol_rel)
    write_registry_entry(registry_path, args.window_start, window_end_iso, mode,
                          mode_reason, report, last_commit)

    if args.json:
        payload = {
            "window_start": args.window_start,
            "window_end": window_end_iso,
            "mode": mode,
            "mode_reason": mode_reason,
            "alive_count": report["alive_count"],
            "total_checks": report["total_checks"],
            "to_read_bytes": report["to_read_bytes"],
            "total_bytes": report["total_bytes"],
            "gate_a_threshold": GATE_A_THRESHOLD_BYTES,
            "verdicts": {cv.id_str: cv.verdict for cv in report["check_verdicts"]},
            "empty_lines": report["empty_lines"],
            "perevzvedenie_lines": report["perevzvedenie_lines"],
        }
        if control_result is not None:
            n_empty, n_disc, disc_lines = control_result
            payload["control"] = {"n_empty": n_empty, "n_discrepancies": n_disc,
                                    "discrepancies": disc_lines}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_window_report(
            report, args.window_start, window_end_iso, mode, mode_reason,
            journal_paths, protocol_path, control_result,
        ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
