r"""owns_gate_md.py -- region-aware sibling of tools/owns_gate.py (этап 2,
партия 2, узел D, t-530 / docs/tasks/2026-08-19_scanner-party2-spec.md).
Живой tools/owns_gate.py НЕ ТРОГАЕТСЯ (D-0069) -- этот файл нейтральный
сосед; посадка (переименование на боевой путь) -- акт Lead.

БАЗА: буквальная копия tools/owns_gate.py (extract_owns_paths, sidecar
registry: чтение/сверка/компакция/запись, normalize_path/paths_overlap,
main()) -- см. живой файл за полным происхождением каждого фикса
(T3/F6/F-59 подклассы 1-3/ПЕРЕСДАЧА/П3 многострочный блок и т.д.), здесь
НЕ повторяется. ЕДИНСТВЕННОЕ отличие по существу: региона-осведомлённый
предикат "строка маркера/строка продолжения -- прозa?" поверх
extract_owns_paths (:828-896 живого файла), НОВАЯ диагностика
QUOTED_OWNS_WARN в decide(), и правка протухшего докстринга живого файла
(:457-468, см. "ФЕНС -- ПЕРЕПИСАННЫЙ НЕ-ЦЕЛЬ" ниже).

НАХОДКА (t-528, повод узла D): протухший докстринг живого owns_gate.py
:457-468 утверждал, что общий модуль markdown-регионов "ОТВЕРГНУТ
координатором как ложная экономия" -- решение 08-16 (d3) это перевернуло:
сканер РЕШЕНО строить (docs/CURRENT_CONTEXT.md, класс "сторож не отличает
цитату от утверждения"); ФАКТИЧЕСКАЯ ДЫРА, которую эта неточность
маскировала: extract_owns_paths() до этой правки разбирал ОДНОСТРОЧНУЮ
декларацию внутри фенса, МНОГОСТРОЧНЫЙ блок внутри фенса, И декларацию
внутри цитаты `>` -- НАРАВНЕ с настоящей прозой автора, и писал
"владение" в боевой sidecar logs/owns_registry.jsonl по КАЖДОМУ такому
совпадению (пример: markdown-пример формата манифеста внутри тройного
backtick-блока, показывающий синтаксис "owns: D:/x/real.py" читателю,
регистрировался КАК РЕАЛЬНАЯ декларация -- ложное срабатывание в БОЕВОМ
реестре пересечений, класс SIBLING_MAP :496-510).

ПОЛИТИКА (D, буквально из спеки): декларация владения признаётся ТОЛЬКО
когда МАРКЕР (не путь!) стоит в регионе КАЧЕСТВА "прoза" -- НЕ fenced, НЕ
blockquote, НЕ inline_code (Ф5а: маркер внутри одинарных backtick тоже
исключён, `` `owns:` D:/x.py `` -- не декларация). Строка ПРОДОЛЖЕНИЯ
многострочного блока подчиняется ТОЙ ЖЕ проверке "прoза?" на СВОЁМ
собственном начале строки -- НОВОЕ, ЧЕТВЁРТОЕ стоп-условие
_paths_from_continuation(), встроенное МЕЖДУ существующими (1) пустая
строка / (2) секционный стоп-заголовок манифеста и (3) "первая строка без
path-токена" -- ДО токенизации этой строки, а не после (порядок стоп-
условий буквально из спеки узла D). ОБА прохода extract_owns_paths()
(word-boundary \bowns\b и подстрочный MANIFEST_OWNS_RE-фоллбек) несут
ОДИНАКОВУЮ фильтрацию -- ни один проход region-исключений не обходит.

АСИММЕТРИЯ ФИЛЬТРА -- ТОЛЬКО МАРКЕР, НЕ ПУТЬ (F-59-3 пин держится, ключ
D4): фильтруется позиция САМОГО МАРКЕРА owns/owns-подстроки на строке --
НЕ позиция найденных путевых токенов. Путь, обёрнутый одинарными
backtick-кавычками ("owns: `D:/repo/tools/a.py`") сидит формально ВНУТРИ
inline_code-региона md_regions -- но т.к. фильтр смотрит ТОЛЬКО на
позицию маркера ("owns", который стоит ДО backtick-обёртки, в прозе), а
не на позицию каждого отдельного токена, backtick-обёрнутые пути на
прозаической строке маркера продолжают разбираться как прежде
(_EDGE_TRIM_CHARS уже снимает backtick, T2/F-59 подкласс 3 живого файла)
-- пин test_f59_backtick_wrapped_path_single_line_recognized и его
многострочный близнец (константа _TARGET здесь, эквивалентно живому
tools/test_owns_gate.py) держатся байт-в-байт.

АСИММЕТРИЯ ПОЛЯРНОСТИ С ПАРТИЕЙ 1 (Ф5/Ф6, задокументировано явно, как
требует докстринг md_regions.py "ГРАНИЦА (в)"): у negative_lint_md/
claim_control_gate_md (партия 1, блокирующий/пред упреждающий сторож,
default "проза говорит") незакрытый фенс -> "проза" (правило "silence
looks like success" расширяет НАРУШЕНИЕ, не молчание). У owns_gate_md
(WARN-only, "никогда не блокировать", default "непонятное молчит")
ПРОТИВОПОЛОЖНЫЙ дефолт: незакрытый фенс НЕ переквалифицируется в прозу
-- остаётся "fenced" (исключён), декларация внутри него НЕ читается
(Ф6а). _classify() ниже поэтому НЕ несёт приоритетное правило
"unterminated И fenced -> prose", которое есть у партии 1 -- это
СОЗНАТЕЛЬНОЕ расхождение, не забытая копипаста.

QUOTED_OWNS_WARN (НОВОЕ, D6-диагностика третьего рода): decide()
различает ТРИ исхода при owns_paths == []:
  1. Маркер вообще не найден нигде -- read-only диспатч, тишина
     (НЕ ИЗМЕНИЛОСЬ).
  2. Маркер найден, И ХОТЯ БЫ ОДНО его вхождение -- в прозе (обычная
     декларация без путей, "слепа") -- BLIND_OWNS_WARN, ТА ЖЕ проверка
     (MANIFEST_OWNS_RE + WRITE_INDICATORS_RE на сыром prompt), что и
     живой файл, БАЙТ-В-БАЙТ (см. "И-0" ниже -- при недоступном сканере
     эта ветка -- ЕДИНСТВЕННАЯ, куда попадает [], полностью совпадая с
     живым поведением).
  3. Маркер найден, НО ВСЕ его вхождения -- в fenced/blockquote/
     inline_code (ни одного в прозе) -- QUOTED_OWNS_WARN (НОВОЕ):
     "owns объявлен только внутри цитаты/фенса/инлайн-кода -- не
     декларация". Приоритет 3 ПЕРЕД 2 -- если ВСЕ вхождения цитированы,
     старая "слепая" диагностика не применяется (её raw-substring
     проверка не знает о цитировании и дала бы неверный диагноз).
Ни исход 2, ни исход 3 не пишут в sidecar (D3) -- обе ветки, как и
живая BLIND-ветка, возвращаются РАНЬШЕ участка "сверка + запись"
decide().

ФЕНС -- ПЕРЕПИСАННЫЙ НЕ-ЦЕЛЬ (замена протухшего :457-468 живого файла,
D5 "старый пин по двум причинам"): маркер+путь внутри тройного backtick-
фенса теперь ИСКЛЮЧАЕТСЯ по позиции маркера (см. "ПОЛИТИКА" выше) --
модуль регионов, которого раньше не было, ТЕПЕРЬ разбирает фенс/цитату
как факт и предикат-потребитель (этот файл) решает игнорировать
декларацию внутри него. Существующий регресс-пин живого файла
(маркер "**owns (ABSOLUTE write paths):**" ОДНОЙ строкой ПРОЗОЙ, ЗАТЕМ
путь ВНУТРИ последующего fenced-блока продолжения) в сиблинге даёт ТОТ
ЖЕ пустой результат, что и раньше, но теперь -- ПО ДВУМ НЕЗАВИСИМЫМ
причинам одновременно: (а) старая причина живого файла -- строка-
ограничитель "```" сама не path-подобна, токенизация обрывает блок на
ней; (б) НОВАЯ причина -- строка "```" сама лежит в fenced-регионе,
четвёртое стоп-условие continuation обрывает блок там же, ДО того, как
тот же (а) сработал бы. См. test_d5_fenced_non_goal_pin_holds_for_two_
independent_reasons ниже -- обе причины проверяются раздельно
(тест И-0-отказа модуля даёт [] по причине (а) даже при выключенном
регионе; штатный прогон даёт [] по причине (б) первой).

И-0 (ЛЮБОЙ отказ md_regions -- отсутствующий модуль/исключение scan()/
degraded=True): region-фильтр становится НО-ОП -- КАЖДОЕ вхождение
маркера трактуется как "проза" (см. `if scan_result is not None:` перед
КАЖДОЙ проверкой региона ниже), extract_owns_paths()/decide() ведут себя
РОВНО как живой owns_gate.py, включая перехват цитируемой/фенсированной
декларации (D7 -- "И-0 включая перехват": деградация модуля откатывает
СИБЛИНГ к СЕГОДНЯШНЕМУ поведению живого файла целиком, БАГ включён --
это не новый путь кода, это ОДИН и тот же цикл с region-веткой, ставшей
мёртвой, тот же принцип негативного лога negative_lint_md).

И-1 (Rule #1, ленивость, тот же партийный инвариант, что и партия 1):
scan() вызывается НЕ БОЛЕЕ ОДНОГО РАЗА за вызов extract_owns_paths()
(единственная точка входа, которую decide() зовёт), И ТОЛЬКО когда (а)
хотя бы один owns-маркер (OWNS_WORD_RE ИЛИ MANIFEST_OWNS_RE) найден
ГДЕ-ТО в prompt, И (б) prompt несёт хотя бы один из символов "`>~"
(дешёвый предфильтр -- без них md_regions.scan() детерминированно вернул
бы "весь текст -- проза", вызов был бы потрачен впустую, см. md_regions.
_no_markers_whole_text). На тексте без маркера ИЛИ без единого "`>~"
символа -- 0 вызовов (счётчик, тест-пара).

ПОЗИЦИОННЫЕ ИНВАРИАНТЫ, НЕ ТРОНУТЫЕ НИ БАЙТОМ (D6): импорт четырёх имён
из ЖИВОГО tools/dispatch_gate.py (MANIFEST_OWNS_RE/OWNS_WORD_RE/
WRITE_INDICATORS_RE/is_path_like_token, порядок посадки безразличен);
_EDGE_TRIM_CHARS/_TRAILING_TRIM_CHARS/_SECTION_HEADER_STOP_RE/
CONTINUATION_LINE_LIMIT=40; normalize_path/paths_overlap (СЕМАНТИКА
ПЕРЕСЕЧЕНИЯ ПУТЕЙ); WINDOW_SECONDS=24ч (граница включительна);
REGISTRY_COMPACT_THRESHOLD_LINES=500 (500 -> append, 501 -> компакция);
порядок "сверка живых записей ВЫШЕ, запись НОВОЙ записи ПОСЛЕ" (само-
пересечение исключено структурно); exit_code ВСЕГДА 0 (WARN-режим). Ни
одна из этих функций/констант ниже НЕ изменена относительно живого
файла -- см. equivalence-run отчёта билдера (t-530) за прогон существующей
батареи tools/test_owns_gate.py на КОПИИ дерева с этим файлом под живым
именем.

Импорт md_regions -- пара try/except (образец negative_lint_md.py,
который сам следует tools/owns_gate.py:545-558) -- отсутствующий модуль
не боевая ошибка, а штатный "модуль ещё не посажен" путь (см. "И-0").
"""

import fnmatch
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    from tools.dispatch_gate import (  # package-style
        MANIFEST_OWNS_RE,
        OWNS_WORD_RE,
        WRITE_INDICATORS_RE,
        is_path_like_token,
    )
except ImportError:
    from dispatch_gate import (  # sibling-module fallback
        MANIFEST_OWNS_RE,
        OWNS_WORD_RE,
        WRITE_INDICATORS_RE,
        is_path_like_token,
    )

try:
    from tools.md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE, KIND_INLINE_CODE  # package-style
except ImportError:
    try:
        from md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE, KIND_INLINE_CODE  # sibling-module fallback
    except ImportError:
        scan = None
        KIND_FENCED = "fenced"
        KIND_BLOCKQUOTE = "blockquote"
        KIND_INLINE_CODE = "inline_code"


# --- извлечение owns-путей из промпта -------------------------------

_PAREN_PREFIX_RE = re.compile(r"^\s*\([^)]*\)")
_JUNK_PREFIX_RE = re.compile(r"^[\s*:\-\u2014\u00ab\u00bb\"']+")
_TOKEN_SEPARATOR_RE = re.compile(r"[;,\n]")
_PROSE_TAIL_SEP = " \u2014 "  # пробел-эмтире-пробел -- см. докстринг живого owns_gate.py, п.3

_EDGE_TRIM_CHARS = "\"'`()[]{}\u00ab\u00bb\u201e\u201c\u201d"
_TRAILING_TRIM_CHARS = _EDGE_TRIM_CHARS + "."

_BULLET_PREFIX_RE = re.compile(r"^\s*[-*•]\s+")
_NUMBERED_PREFIX_RE = re.compile(r"^\s*\d+[.)]\s+")
_SECTION_HEADER_STOP_RE = re.compile(
    r"^\s*(?:\*\*)?(given|дано|owns|non-goals|handoff)\b", re.IGNORECASE
)
_DECLARATION_PREFIX_RE = re.compile(r"^\s*(?:[-*•]\s+)?(?:\*\*)?$")
CONTINUATION_LINE_LIMIT = 40

# --- region-предикат (узел D, НОВОЕ) ---------------------------------

# Опозиция партии 1: ВСЕ ТРИ вида, отличные от "prose", исключают
# декларацию -- fenced (в т.ч. незакрытый, Ф6а), blockquote, inline_code
# (Ф5а). НЕТ приоритета "unterminated -> prose" -- см. докстринг модуля,
# "АСИММЕТРИЯ ПОЛЯРНОСТИ".
_EXCLUDED_KINDS = ("fenced", "blockquote", "inline_code")

_REGION_MARKER_CHARS = ("`", ">", "~")


def _has_region_marker_chars(text: str) -> bool:
    """И-1 дешёвый предфильтр: хотя бы один из символов, без которых
    fenced/blockquote/inline_code структурно невозможны (md_regions.
    _no_markers_whole_text несёт ТУ ЖЕ проверку) -- см. докстринг модуля."""
    return any(ch in text for ch in _REGION_MARKER_CHARS)


def _safe_scan(text: str):
    """И-0: None при отсутствии модуля / исключении scan() / degraded=True
    -- region-фильтр становится но-оп для вызывающего кода (см. докстринг
    модуля, "И-0")."""
    if scan is None:
        return None
    try:
        result = scan(text)
    except Exception:
        return None
    if result.degraded:
        return None
    return result


def _region_at(scan_result, offset: int):
    regions = scan_result.regions
    if not regions:
        return None
    import bisect
    starts = [r.start for r in regions]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        return None
    region = regions[idx]
    if region.start <= offset < region.end:
        return region
    return None


def _classify(region) -> str:
    """См. докстринг модуля "ПОЛИТИКА"/"АСИММЕТРИЯ ПОЛЯРНОСТИ": region
    None (нет региона на этой позиции -- конец текста, вне покрытия) ->
    "prose" (безопасный дефолт, как без региона вовсе). Приоритет: fenced
    (в т.ч. НЕЗАКРЫТЫЙ -- никакого "unterminated -> prose", Ф6а) >
    blockquote > inline_code > prose."""
    if region is None:
        return "prose"
    if KIND_FENCED in region.kinds:
        return "fenced"
    if KIND_BLOCKQUOTE in region.kinds:
        return "blockquote"
    if KIND_INLINE_CODE in region.kinds:
        return "inline_code"
    return "prose"


def _is_prose_position(scan_result, offset: int) -> bool:
    if scan_result is None:
        return True  # И-0: но-оп -- каждая позиция считается прозой
    return _classify(_region_at(scan_result, offset)) not in _EXCLUDED_KINDS


def _line_start_offsets(text: str) -> list:
    """Смещения начала каждой строки в СИМВОЛАХ исходного текста -- та
    же схема, что negative_lint_md._line_start_offsets / md_regions.
    _split_lines (splitlines(keepends=True), кумулятивная сумма длин)."""
    offsets = []
    pos = 0
    for wt in text.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(wt)
    return offsets


def _strip_owns_marker_junk(remainder: str) -> str:
    prev = None
    while remainder != prev:
        prev = remainder
        m = _PAREN_PREFIX_RE.match(remainder)
        if m:
            remainder = remainder[m.end():]
            continue
        m2 = _JUNK_PREFIX_RE.match(remainder)
        if m2:
            remainder = remainder[m2.end():]
            continue
    return remainder


def _cut_prose_tail(raw: str) -> str:
    if not raw:
        return raw
    idx = raw.find(_PROSE_TAIL_SEP)
    if idx == -1:
        return raw
    return raw[:idx]


def _clean_token(raw: str) -> str:
    tok = raw.strip()
    prev = None
    while tok != prev:
        prev = tok
        tok = tok.lstrip(_EDGE_TRIM_CHARS)
        tok = tok.rstrip(_TRAILING_TRIM_CHARS)
        tok = tok.strip()
    return tok


def split_and_clean_tokens(text: str) -> list:
    if not isinstance(text, str) or not text:
        return []
    cleaned = []
    for raw in _TOKEN_SEPARATOR_RE.split(text):
        raw = _cut_prose_tail(raw)
        tok = _clean_token(raw)
        if tok:
            cleaned.append(tok)
    return cleaned


def is_path_token(tok: str) -> bool:
    return is_path_like_token(tok)


BLIND_OWNS_WARN_MESSAGE = (
    "owns объявлен, путей не разобрано \u2014 сверка пересечений слепа "
    "на этом диспатче; проверь форму owns-строки"
)

# НОВОЕ (D6, узел D): все найденные owns-маркеры -- в fenced/blockquote/
# inline_code, ни одного в прозе -- см. докстринг модуля "QUOTED_OWNS_WARN".
QUOTED_OWNS_WARN_MESSAGE = (
    "owns объявлен только внутри цитаты/фенса/инлайн-кода \u2014 это не "
    "декларация владения, сверка пересечений не выполнена; перенеси "
    "owns-строку в обычную прозу диспатча"
)


def _paths_from_line(line: str, marker_end: int) -> list:
    remainder = _strip_owns_marker_junk(line[marker_end:])
    tokens = split_and_clean_tokens(remainder)
    return [t for t in tokens if is_path_token(t)]


def _is_owns_declaration_line(line: str, marker_start: int, marker_end: int) -> bool:
    prefix = line[:marker_start]
    if not _DECLARATION_PREFIX_RE.match(prefix):
        return False
    remainder_after_junk = _strip_owns_marker_junk(line[marker_end:])
    return remainder_after_junk.strip() == ""


def _is_continuation_path_token(tok: str) -> bool:
    return is_path_like_token(tok)


_QUOTE_OPEN_TO_CLOSE = {"\"": "\"", "'": "'", "`": "`", "\u00ab": "\u00bb"}


def _first_raw_token(body: str) -> str:
    if body and body[0] in _QUOTE_OPEN_TO_CLOSE:
        close_char = _QUOTE_OPEN_TO_CLOSE[body[0]]
        close_idx = body.find(close_char, 1)
        if close_idx != -1:
            return body[: close_idx + 1]
    return body.split(None, 1)[0]


def _first_token_path(line: str):
    body = _BULLET_PREFIX_RE.sub("", line, count=1)
    body = _NUMBERED_PREFIX_RE.sub("", body, count=1)
    body = body.strip()
    if not body:
        return None
    first_raw = _first_raw_token(body)
    tok = _clean_token(first_raw)
    if tok and _is_continuation_path_token(tok):
        return tok
    return None


def _paths_from_continuation(lines: list, start_idx: int, scan_result, line_offsets) -> list:
    """П3 (живой файл) + НОВОЕ четвёртое стоп-условие узла D: строка
    продолжения обязана сама лежать в "прoза" (см. докстринг модуля,
    "ПОЛИТИКА") -- проверяется ПОСЛЕ пустой строки/секционного стопа,
    ДО токенизации (_first_token_path), позиция буквально из спеки узла
    D. Якорь позиции -- НАЧАЛО физической строки (line_offsets[idx],
    символ 0 этой строки в исходном prompt): ЛЮБАЯ форма bullet-префикса
    ("- ", "* ", "1. ") ставит его перед backtick/кавычкой пути (F-59-3),
    поэтому проверка региона на offset 0 не задевает backtick-обёрнутые
    ПУТИ продолжения (см. докстринг модуля, "АСИММЕТРИЯ ФИЛЬТРА") -- она
    исключает только строки, чьё НАЧАЛО уже находится внутри fenced/
    blockquote/inline_code (напр. строка-ограничитель фенса "```" сама,
    или цитируемая "> - D:/x.py")."""
    collected = []
    idx = start_idx
    n = len(lines)
    lines_consumed = 0
    while idx < n:
        line = lines[idx]
        if line.strip() == "":
            break
        if _SECTION_HEADER_STOP_RE.match(line):
            break
        if not _is_prose_position(scan_result, line_offsets[idx]):
            break  # НОВОЕ (узел D): строка продолжения не в прозе -- конец блока
        path = _first_token_path(line)
        if path is None:
            break
        if lines_consumed >= CONTINUATION_LINE_LIMIT:
            return []
        collected.append(path)
        lines_consumed += 1
        idx += 1
    return collected


def _diag_for(saw_any_marker: bool, saw_prose_marker: bool):
    """Приоритет исходов decide()'а -- см. докстринг модуля,
    "QUOTED_OWNS_WARN": None (никакого маркера -- тишина), "quoted"
    (маркер(ы) есть, ВСЕ в цитате/фенсе/инлайн-коде), "blind" (хотя бы
    один маркер в прозе, но путей не дано -- старая B2-диагностика)."""
    if not saw_any_marker:
        return None
    if not saw_prose_marker:
        return "quoted"
    return "blind"


def _extract_owns_full(prompt: str):
    """Единая точка входа: ОДИН вызов _safe_scan() на весь разбор (И-1),
    возвращает (paths: list, diag: None|"blind"|"quoted") -- см.
    докстринг модуля. extract_owns_paths()/decide() -- тонкие обёртки
    поверх неё (decide() читает diag, extract_owns_paths() -- только
    paths, обратная совместимость прямых вызовов батареи)."""
    if not isinstance(prompt, str) or not prompt:
        return [], None

    saw_any_marker = False
    saw_prose_marker = False

    scan_result = None
    if (OWNS_WORD_RE.search(prompt) or MANIFEST_OWNS_RE.search(prompt)) and _has_region_marker_chars(prompt):
        scan_result = _safe_scan(prompt)

    lines = prompt.splitlines()
    line_offsets = _line_start_offsets(prompt)

    word_boundary_seen = False
    for i, line in enumerate(lines):
        m = OWNS_WORD_RE.search(line)
        if not m:
            continue
        saw_any_marker = True
        word_boundary_seen = True
        if not _is_prose_position(scan_result, line_offsets[i] + m.start()):
            continue  # Ф5а/Ф6а: маркер не в прозе -- эта строка не декларация
        saw_prose_marker = True
        paths = _paths_from_line(line, m.end())
        if paths:
            return paths, None
        if _is_owns_declaration_line(line, m.start(), m.end()):
            paths = _paths_from_continuation(lines, i + 1, scan_result, line_offsets)
            if paths:
                return paths, None

    if word_boundary_seen:
        return [], _diag_for(saw_any_marker, saw_prose_marker)

    for i, line in enumerate(lines):
        m = MANIFEST_OWNS_RE.search(line)
        if not m:
            continue
        saw_any_marker = True
        if not _is_prose_position(scan_result, line_offsets[i] + m.start()):
            continue
        saw_prose_marker = True
        paths = _paths_from_line(line, m.end())
        if paths:
            return paths, None
        paths = _paths_from_continuation(lines, i + 1, scan_result, line_offsets)
        if paths:
            return paths, None
    return [], _diag_for(saw_any_marker, saw_prose_marker)


def extract_owns_paths(prompt: str) -> list:
    """Обратная совместимость с прямыми вызовами батареи (та же сигнатура,
    что живой owns_gate.py): [] на read-only, ИЛИ когда все owns-маркеры
    отфильтрованы регионом (см. decide() за диагностику ВТОРОГО рода)."""
    return _extract_owns_full(prompt)[0]


# --- нормализация и сверка путей (общий код с owns_verify.py) --------


def normalize_path(p: str) -> str:
    if not isinstance(p, str):
        return ""
    p = p.strip().lower().replace("\\", "/")
    while len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def paths_overlap(a: str, b: str) -> bool:
    na, nb = normalize_path(a), normalize_path(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na.startswith(nb + "/") or nb.startswith(na + "/"):
        return True
    if "*" in na or "*" in nb:
        if fnmatch.fnmatchcase(nb, na) or fnmatch.fnmatchcase(na, nb):
            return True
    return False


# --- sidecar: чтение живых записей + запись новой --------------------

WINDOW_SECONDS = 24 * 60 * 60
_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"
_DESC_TRUNC_LEN = 200
REGISTRY_COMPACT_THRESHOLD_LINES = 500


def _now_iso(now: datetime) -> str:
    return now.strftime(_TS_FORMAT)


def _registry_path_from_cwd(cwd) -> Path:
    return Path(cwd or ".") / "logs" / "owns_registry.jsonl"


def _load_live_records(registry_path: Path, cwd, now: datetime) -> list:
    if registry_path is None or not registry_path.exists():
        return []
    try:
        raw = registry_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    records = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("cwd") != cwd:
            continue
        ts_str = rec.get("ts")
        if not isinstance(ts_str, str):
            continue
        try:
            rec_ts = datetime.strptime(ts_str, _TS_FORMAT)
        except Exception:
            continue
        delta = (now - rec_ts).total_seconds()
        if delta < 0 or delta > WINDOW_SECONDS:
            continue
        owns = rec.get("owns")
        if not isinstance(owns, list):
            continue
        records.append(rec)
    return records


def _compact_live_lines(existing_lines: list, now: datetime) -> list:
    live = []
    for line in existing_lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        ts_str = rec.get("ts")
        if not isinstance(ts_str, str):
            continue
        try:
            rec_ts = datetime.strptime(ts_str, _TS_FORMAT)
        except Exception:
            continue
        delta = (now - rec_ts).total_seconds()
        if delta < 0 or delta > WINDOW_SECONDS:
            continue
        live.append(line)
    return live


def _append_registry(
    registry_path: Path, now: datetime, session_key, cwd, description: str, owns_paths: list
) -> None:
    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": _now_iso(now),
            "session_key": session_key,
            "cwd": cwd,
            "description": description or "",
            "owns": owns_paths,
        }
        entry_line = json.dumps(entry, ensure_ascii=False)

        existing_lines = []
        if registry_path.exists():
            try:
                raw = registry_path.read_text(encoding="utf-8", errors="replace")
                existing_lines = [ln for ln in raw.splitlines() if ln.strip()]
            except Exception:
                existing_lines = []

        if len(existing_lines) > REGISTRY_COMPACT_THRESHOLD_LINES:
            live_lines = _compact_live_lines(existing_lines, now)
            live_lines.append(entry_line)
            registry_path.write_text("\n".join(live_lines) + "\n", encoding="utf-8")
        else:
            with registry_path.open("a", encoding="utf-8") as f:
                f.write(entry_line + "\n")
    except Exception:
        pass


def _truncate(s: str, max_len: int = _DESC_TRUNC_LEN) -> str:
    s = (s or "").strip()
    if len(s) > max_len:
        return s[:max_len] + "\u2026"
    return s


def _find_overlaps(new_paths: list, records: list, session_key) -> list:
    grouped = []
    for p in new_paths:
        matches = []
        for rec in records:
            rec_owns = rec.get("owns") or []
            if any(paths_overlap(p, existing) for existing in rec_owns):
                same_session = rec.get("session_key") == session_key
                matches.append((rec.get("ts"), rec.get("description") or "", same_session))
        if matches:
            grouped.append((p, matches))
    return grouped


def _format_mention(ts, desc, same_session: bool) -> str:
    tag = (
        "параллельный диспатч этой же сессии"
        if same_session
        else "другая сессия (класс D-0060)"
    )
    return f"{ts} \u00ab{_truncate(desc)}\u00bb ({tag})"


def _format_path_line(p: str, matches: list) -> str:
    shown = matches[:2]
    mentions = "; ".join(_format_mention(ts, desc, same) for ts, desc, same in shown)
    extra = len(matches) - len(shown)
    if extra > 0:
        mentions += f"; и ещё {extra}"
    return f"путь {p} пересекается с {mentions}"


def _format_overlap_context(grouped: list) -> str:
    head = grouped[:3]
    parts = [_format_path_line(p, matches) for p, matches in head]
    return (
        "OWNS OVERLAP (warn): " + "; ".join(parts) + "; параллельная запись в "
        "общие пути \u2014 сериализуй или разведи owns"
    )


# --- decide() ----------------------------------------------------------


def decide(payload: dict, registry_path: Path = None, now: datetime = None) -> tuple:
    """Позиционный инвариант живого файла держится байт-в-байт (D6):
    сверка живых записей ВЫШЕ, запись новой -- ПОСЛЕ; exit_code ВСЕГДА 0.
    НОВОЕ -- приоритет исхода при owns_paths == [] (см. докстринг модуля,
    "QUOTED_OWNS_WARN"): quoted-диагностика ПЕРЕД старой blind-диагностикой."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, None

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0, None

    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""

    owns_paths, diag = _extract_owns_full(prompt)
    if not owns_paths:
        # НОВОЕ (D6): все найденные маркеры -- цитированы -- QUOTED_OWNS_WARN,
        # sidecar НЕ растёт (D3), приоритет ПЕРЕД старой blind-диагностикой.
        if diag == "quoted":
            return 0, {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": QUOTED_OWNS_WARN_MESSAGE,
                }
            }
        # B2 (живой файл, байт-в-байт, включая И-0-фоллбек): owns-маркер
        # объявлен, путей не разобрано -- сверка слепа, sidecar не растёт.
        if MANIFEST_OWNS_RE.search(prompt) and WRITE_INDICATORS_RE.search(prompt):
            return 0, {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": BLIND_OWNS_WARN_MESSAGE,
                }
            }
        return 0, None

    if now is None:
        now = datetime.now()
    cwd = payload.get("cwd")
    if registry_path is None:
        registry_path = _registry_path_from_cwd(cwd)

    session_id = payload.get("session_id")
    session_key = session_id if isinstance(session_id, str) and session_id else cwd

    description = tool_input.get("description")
    if not isinstance(description, str):
        description = ""

    records = _load_live_records(registry_path, cwd, now)
    grouped = _find_overlaps(owns_paths, records, session_key)

    output = None
    if grouped:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": _format_overlap_context(grouped),
            }
        }

    _append_registry(registry_path, now, session_key, cwd, description, owns_paths)

    return 0, output


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stdout_utf8()

    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    try:
        exit_code, output = decide(payload)
    except Exception:
        return 0

    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
