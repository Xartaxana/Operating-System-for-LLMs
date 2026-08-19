r"""md_regions.py -- сканер регионов markdown-текста: ФАКТЫ, не вердикты.

Класс (docs/SIBLING_MAP.md, "Режимы отказа" :496-510): "сторож не
отличает утверждение автора от цитируемого/вложенного содержимого" --
несколько сторожей (negative_lint, claim_control_gate, owns_gate и
др.) регексово ищут маркеры/паттерны по СЫРОМУ тексту диспатча, не
различая "это утверждение автора" от "это внутри цитаты/фенса/инлайн-
кода в чужом тексте". Решение 08-16 (d3): общий СКАНЕР регионов -- да
(один источник фактов "какой кусок текста в каком регионе"), общая
ПОЛИТИКА -- нет (что считать нарушением/что игнорировать -- решает
каждый сторож сам, это его семантика, не сканера).

ЭТАП 1 (t-507): этот модуль и его тесты. Модуль НИКЕМ не импортируется
до посадки первого потребителя (этап 2, партия 1: negative_lint_md.py
/ claim_control_gate_md.py -- отдельный диспатч) -- D-0069 (билдер
хука не кладёт себя на путь) тут не задет, а mechanism_gate заводится
на модуль ТОЛЬКО ходом посадки первого потребителя (Р8(б) решения
Lead 08-19) -- до этого модуль вне невода.

КОНТРАКТ (A1): публичная поверхность -- ТОЛЬКО факты. Константы видов
(KIND_*), тип Region, ScanResult, функции scan()/line_kinds()/
kind_at(), константы лимитов (MAX_*). НИКАКИХ should_ignore/
is_quoted_claim/SILENCE_KINDS/политик -- если когда-нибудь в этот файл
захочется добавить такое имя, это ЗНАЧИТ, что в сканер поехала
политика сторожа, а не факт региона; test_public_api_surface_is_facts_only
(дословный список dir()) ловит это детектором на КАЖДОЕ новое
публичное имя.

ЗАРЕЗЕРВИРОВАННЫЕ ВИДЫ: KIND_NOTES / KIND_EMBEDDED_DOC существуют как
константы (для будущего v2 -- заметки/вложенные документы как
отдельные регионы), но scan() их НИКОГДА не возвращает в v1 -- пин
test_reserved_kinds_never_returned_by_scan_v1 (Р2(б) решения Lead
08-19).

ДВА СУЩЕСТВУЮЩИХ ПАРСЕРА ФЕНСОВ -- НЕ ТРОГАТЬ, ТРЕТЬЕГО НЕ ЗАВОДИТЬ
(Р7(б)): tools/escape_check.py::extract_fenced_block (:454-484) --
статусы ok/not_found/duplicate/empty/unterminated, семантика пришпилена
собственной батареей (tools/test_escape_check.py); tools/
critic_verdict_check.py::_FENCE_RE (:42) -- однострочный regex для
последнего ```json...``` фенса, тоже пришпилен своим тестом. Оба
решают УЗКУЮ задачу другого типа (извлечь ОДИН конкретный блок по
маркеру/языку), а не "разбить весь текст на регионы" -- этот модуль их
не заменяет и не мигрирует; см. РЕШЕНИЯ LEAD :17-18 задачи 2026-08-19.

ИМПОРТ БУДУЩИМ ПОТРЕБИТЕЛЕМ (справочно, этапа 1 не касается -- сам
модуль ничего не импортирует, кроме stdlib): по образцу
tools/owns_gate.py:545-558 -- пара try/except, package-style и
sibling-module fallback:

    try:
        from tools.md_regions import scan, kind_at  # package-style
    except ImportError:
        from md_regions import scan, kind_at  # sibling-module fallback

RULE #1 -- ЗОНА ОВЕРКИЛЛА (§7 драфта t-506): "вход сторожа -- одна
строка или структурное поле -> сканер НЕ применяется; оправдан только
на многострочном авторском тексте". НЕ-потребители (сканер им не
нужен и не будет): hygiene_gate (проверяет только shell-кавычки,
класс закрыт), search_control_gate, journal_echo/journal_validator,
closes:-токен (Р6а решения Lead 08-19 -- токен вне класса, это иная
поверхность). Вызов сканера на однострочном/структурном поле -- это
не эта задача, это неоправданный вызов.

FAIL-OPEN (A5): scan(None) / scan(<не-str>) -> ScanResult([], True,
"not_a_string") БЕЗ исключения; scan("") -> ScanResult([], False, "").
line_kinds() зеркалит тот же контракт входа (не-str -> [] без
исключения) -- это РАСШИРЕНИЕ A5 за пределы её буквальной формулировки
(та говорит только про scan()), сделанное ради согласованности: обе
функции принимают один и тот же "сырой недоверенный текст" как первый
аргумент, и молчаливое падение с трейсбеком на line_kinds(None) было
бы разрывом того же самого контракта "никогда не роняем на битом
входе", который A5 явно требует от scan(). kind_at(result, offset) --
ДРУГОЙ случай: её ПЕРВЫЙ аргумент -- это уже готовый ScanResult (не
сырой текст), контракта untrusted-input к нему нет -- kind_at(None, 0)
и подобный мусор в `result` РОНЯЮТ как обычная ошибка вызова (это
баг вызывающего кода, не входной текст для разбора). Единственное, что
kind_at держит fail-open -- OFFSET вне диапазона (отрицательный,
больше длины текста, точно на границе конца последнего региона):
возвращает () -- "факт неизвестен", не исключение (тест на оба
направления).

Модуль НЕ ловит исключения сверх специально оговорённого в A5 списка
(не-str на входе scan()/line_kinds(), offset вне диапазона на входе
kind_at()) -- если валидный str вызывает внутреннее исключение, это
баг МОДУЛЯ, не штатный fail-open путь. Потребитель (этап 2) оборачивает
вызов сканера своим собственным try/except -- инвариант И-0 спеки B
("любой отказ модуля -> сторож ведёт себя КАК СЕГОДНЯ побайтно").

ДЕГРАДАЦИЯ (A4): при превышении любого из трёх лимитов (MAX_TEXT_CHARS,
MAX_REGIONS, MAX_LINE_INLINE_SPANS) весь результат схлопывается в ОДИН
регион на ВЕСЬ текст, kinds=(KIND_PROSE,), degraded=True, reason=
<конкретная причина>. Это "сегодняшнее поведение сторожей" (весь текст
-- проза, ничего не размечено) -- деградация НЕ расширяет зону
молчания (сторож как и раньше видит весь текст и должен сам решать),
она просто отключает разметку. Инвариант полного побайтного покрытия
(A2, инвариант 1) держится и в деградированном состоянии -- один
регион покрывает [0, len(text)) целиком.

ПЕРФОРМАНС-ПРЕДПРОВЕРКИ (DoD: полный scan 1 МБ <= 150 мс, "не
молчаливое замедление"): _no_markers_whole_text()/_too_many_fence_opens()
-- две дешёвые (O(n), но с крошечной C-уровневой константой) проверки
ПЕРЕД основным по-строчным разбором; обе см. собственные докстринги.
Без них по-строчный разбор (несколько Python-уровневых проходов на
каждую строку) не укладывается в бюджет на текстах с очень большим
числом коротких строк -- см. отчёт билдера t-507 (профиль/witness).

ГРАНИЦА (в) -- НЕЗАКРЫТЫЙ ФЕНС: модуль возвращает unterminated=True в
Region, ВЕРДИКТА не выносит. У сторожей партии 1 (negative_lint,
claim_control_gate) дефолт для непонятного случая -- "проза -> сторож
говорит" (осторожность в сторону срабатывания); у owns_gate --
ПРОТИВОПОЛОЖНЫЙ дефолт (WARN-only, "никогда не блокировать" ->
непонятное молчит). Это расхождение МЕЖДУ ПОТРЕБИТЕЛЯМИ, не в модуле
-- зафиксировано здесь явно, чтобы будущий потребитель owns_gate (партия
2, другой предикат) не унаследовал политику партии 1 по ошибке.

COMMONMARK-LITE -- ЯВНЫЕ ОТСТУПЛЕНИЯ ОТ ПОЛНОГО COMMONMARK (A3):
  1. Отступный 4-пробельный код НЕ распознаётся как отдельный вид --
     остаётся обычной прозой (regex-и фенса/цитаты уже отсекают >3
     пробелов отступа как "не маркер", это ПОБОЧНЫЙ эффект той же
     проверки, отдельного вида кода для него нет).
  2. Ленивое продолжение цитаты НЕ реализуется (Р3(б) решения Lead
     08-19) -- каждая строка цитаты должна НЕСТИ собственный `>`;
     строка без `>`, продолжающая абзац цитаты по правилам полного
     CommonMark, здесь считается КОНЦОМ цитаты. Дыра пинуется тестом,
     не закрывается.
  3. Глубина цитаты не моделируется -- `>>` (вложенная цитата 2
     уровня) распознаётся как ОДНА цитата (снимается только первый
     `>`), второй `>` остаётся частью текста региона (прозы).
  4. Инлайн-код -- ТОЛЬКО backtick-серии одной физической строки; пара,
     разорванная переводом строки, не матчится и остаётся прозой (это
     то же самое реальное правило CommonMark "backtick string длины N
     закрывается следующей backtick-строкой длины N", ограниченное
     здесь одной строкой намеренно).
  5. Инфострока фенса (```lang) НЕ проверяется на отсутствие backtick
     внутри (полный CommonMark запрещает backtick в инфостроке
     backtick-фенса) -- здесь инфострока просто "всё после маркера до
     конца строки", без семантики (info хранится как факт, "info без
     политики", §12 драфта).
  6. Никакого разбора таблиц/списков/заголовков/HTML-блоков -- вне
     объёма v1 (только проза/фенс/цитата/инлайн-код).

СМЕЩЕНИЯ И ИНДЕКСАЦИЯ (§12 драфта): все смещения -- в СИМВОЛАХ (не
байтах). Region.start/Region.end -- как срез text[start:end] (start
включительно, end исключительно). Region.line_start/line_end -- номера
строк 0-based, ОБА включительно (line_end -- номер ПОСЛЕДНЕЙ строки
региона, тоже входит в регион). Регионы в scan().regions идут по
возрастанию start; kind_at() ищет по ним через bisect. ~~~ фенс
равноправен ``` фенсу (тот же маркер, любой из двух символов, закрытие
-- ТЕМ ЖЕ символом). CLI не предусмотрен -- модуль только импортируется.
"""

from __future__ import annotations

import bisect
import re
from typing import List, NamedTuple, Optional, Tuple

# --- публичные константы видов -------------------------------------

KIND_PROSE = "prose"
KIND_FENCED = "fenced"
KIND_INLINE_CODE = "inline_code"
KIND_BLOCKQUOTE = "blockquote"
# зарезервированы v2, scan() их не возвращает (Р2(б), пин-тест)
KIND_NOTES = "notes"
KIND_EMBEDDED_DOC = "embedded_doc"

# --- публичные лимиты (A4) -------------------------------------------

MAX_TEXT_CHARS = 2_000_000
MAX_REGIONS = 20_000
MAX_LINE_INLINE_SPANS = 200


# --- публичный API-тип -------------------------------------------------


class Region(NamedTuple):
    start: int
    end: int
    kinds: Tuple[str, ...]
    line_start: int
    line_end: int
    unterminated: bool
    info: str


class ScanResult(NamedTuple):
    regions: List[Region]
    degraded: bool
    reason: str


# --- приватные regex-примитивы -----------------------------------------

_QUOTE_RE = re.compile(r"^ {0,3}>( ?)")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CLOSE_STRIP_RE = re.compile(r"^ {0,3}")
_BACKTICK_RUN_RE = re.compile(r"`+")


def _is_fence_close(content: str, fence_char: str, fence_len: int) -> bool:
    m = _CLOSE_STRIP_RE.match(content)
    rest = content[m.end():]
    i = 0
    length = len(rest)
    while i < length and rest[i] == fence_char:
        i += 1
    if i < fence_len:
        return False
    return rest[i:].strip(" \t") == ""


def _find_fence_close(lines, start_idx: int, n: int, fence_char: str, fence_len: int, quote: bool):
    """Return (end_line_index, unterminated) for a fence opened at start_idx-1."""
    k = start_idx
    while k < n:
        text_k = lines[k][0]
        if quote:
            qm_k = _QUOTE_RE.match(text_k)
            if not qm_k:
                return k - 1, True
            content = text_k[qm_k.end():]
        else:
            content = text_k
        if _is_fence_close(content, fence_char, fence_len):
            return k, False
        k += 1
    return n - 1, True


def _maybe_marker(text_i: str) -> bool:
    """Cheap pre-filter (perf, DoD 1MB<=150ms): a line can only be a quote
    marker or a fence-open marker if one of '>','`','~' sits within its
    first 4 chars (<=3 leading spaces + the marker char). Skipping the two
    anchored regexes for the (overwhelmingly common) plain-line case is the
    dominant win on inputs with very many short lines -- see witness."""
    prefix = text_i[:4]
    return (">" in prefix) or ("`" in prefix) or ("~" in prefix)


def _iter_block_runs(lines):
    """Yield (kinds_stack, line_start, line_end, fence_info_or_None) tuples
    covering every line exactly once, in order. fence_info is
    (fence_char, fence_len, info, unterminated) only when kinds_stack ends
    in KIND_FENCED, else None."""
    n = len(lines)
    i = 0
    mode = "TOP"
    run_start = 0
    while i < n:
        text_i = lines[i][0]
        if mode == "TOP":
            if not _maybe_marker(text_i):
                i += 1
                continue
            qm = _QUOTE_RE.match(text_i)
            if qm:
                if i > run_start:
                    yield (), run_start, i - 1, None
                mode = "QUOTE"
                run_start = i
                continue
            fm = _FENCE_OPEN_RE.match(text_i)
            if fm:
                if i > run_start:
                    yield (), run_start, i - 1, None
                fence_char = fm.group(1)[0]
                fence_len = len(fm.group(1))
                fence_info_str = fm.group(2)
                end_line, unterminated = _find_fence_close(
                    lines, i + 1, n, fence_char, fence_len, quote=False
                )
                yield (
                    (KIND_FENCED,),
                    i,
                    end_line,
                    (fence_char, fence_len, fence_info_str, unterminated),
                )
                i = end_line + 1
                run_start = i
                mode = "TOP"
                continue
            i += 1
            continue
        else:  # mode == "QUOTE"
            qm = _QUOTE_RE.match(text_i)
            if not qm:
                if i > run_start:
                    yield (KIND_BLOCKQUOTE,), run_start, i - 1, None
                mode = "TOP"
                run_start = i
                continue
            inner = text_i[qm.end():]
            fm = _FENCE_OPEN_RE.match(inner) if _maybe_marker(inner) else None
            if fm:
                if i > run_start:
                    yield (KIND_BLOCKQUOTE,), run_start, i - 1, None
                fence_char = fm.group(1)[0]
                fence_len = len(fm.group(1))
                fence_info_str = fm.group(2)
                end_line, unterminated = _find_fence_close(
                    lines, i + 1, n, fence_char, fence_len, quote=True
                )
                yield (
                    (KIND_BLOCKQUOTE, KIND_FENCED),
                    i,
                    end_line,
                    (fence_char, fence_len, fence_info_str, unterminated),
                )
                i = end_line + 1
                run_start = i
                mode = "TOP" if unterminated else "QUOTE"
                continue
            i += 1
            continue
    if run_start <= n - 1:
        tail_kind = (KIND_BLOCKQUOTE,) if mode == "QUOTE" else ()
        yield tail_kind, run_start, n - 1, None


def _inline_split(line_text: str, base_start: int, full_end: int, base_kinds, limit: int):
    """Split one physical line (line_text, without terminator) into
    (start, end, kinds) pieces covering [base_start, full_end) -- full_end
    includes the line terminator, if any. Returns None if the number of
    inline-code spans on this line exceeds `limit`."""
    full_len = full_end - base_start
    if "`" not in line_text:
        if full_len > 0:
            return [(base_start, full_end, base_kinds + (KIND_PROSE,))]
        return []
    runs = [(m.start(), m.end()) for m in _BACKTICK_RUN_RE.finditer(line_text)]
    if not runs:
        if full_len > 0:
            return [(base_start, full_end, base_kinds + (KIND_PROSE,))]
        return []

    by_length = {}
    for idx, (s, e) in enumerate(runs):
        by_length.setdefault(e - s, []).append(idx)

    pieces = []
    cursor = 0
    code_span_count = 0
    i = 0
    n_runs = len(runs)
    while i < n_runs:
        s_i, e_i = runs[i]
        length = e_i - s_i
        idx_list = by_length[length]
        pos = bisect.bisect_right(idx_list, i)
        if pos < len(idx_list):
            j = idx_list[pos]
            s_j, e_j = runs[j]
            if s_i > cursor:
                pieces.append((cursor, s_i, base_kinds + (KIND_PROSE,)))
            pieces.append((s_i, e_j, base_kinds + (KIND_INLINE_CODE,)))
            code_span_count += 1
            if code_span_count > limit:
                return None
            cursor = e_j
            i = j + 1
        else:
            i += 1

    if cursor < full_len:
        pieces.append((cursor, full_len, base_kinds + (KIND_PROSE,)))

    return [(base_start + s, base_start + e, k) for (s, e, k) in pieces]


_FENCE_OPEN_COUNT_RE = re.compile(r"^ {0,3}(?:`{3,}|~{3,})", re.MULTILINE)


def _no_markers_whole_text(text: str) -> bool:
    """Perf pre-check (DoD 1MB<=150ms): if none of '>' / backtick / '~'
    occurs ANYWHERE in the text, none of blockquote/fence/inline-code
    syntax can possibly be present (all three require at least one of
    these chars) -- a plain substring membership check (`in`, O(n) but a
    tiny C-level constant), not an approximation: when it returns True the
    whole-text-is-prose answer is EXACT, not a degraded fallback. Skips the
    per-line state machine entirely for the (very common) marker-free case,
    which is where that machine's per-line Python overhead dominates on
    inputs with very many short lines."""
    return ">" not in text and "`" not in text and "~" not in text


def _too_many_fence_opens(text: str) -> bool:
    """Perf pre-check (DoD 1MB<=150ms), companion to _no_markers_whole_text:
    counts '^ {0,3}(```+|~~~+)'-shaped line starts (re.MULTILINE, LF/CRLF
    line starts) with an early exit once the count exceeds MAX_REGIONS.
    Each such fence-open opens its OWN region that never merges with a
    sibling fenced region (only PROSE regions merge, see scan()) -- so a
    count over MAX_REGIONS is a SOUND lower bound on the eventual region
    count, not a heuristic: full processing of such a text is guaranteed to
    hit max_regions_exceeded too, this just reaches the same, otherwise
    identical, degraded result without paying the per-line loop first.
    re.MULTILINE's `^` anchors only after '\\n' -- a text using bare '\\r'
    line endings (no '\\n' at all) is undercounted here and simply falls
    through to the slower-but-correct per-line path (never a correctness
    risk, only a missed shortcut for that one exotic combination)."""
    count = 0
    for _ in _FENCE_OPEN_COUNT_RE.finditer(text):
        count += 1
        if count > MAX_REGIONS:
            return True
    return False


def _degrade(text: str, reason: str) -> ScanResult:
    no_term = text.splitlines()
    last_line = max(len(no_term) - 1, 0)
    region = Region(0, len(text), (KIND_PROSE,), 0, last_line, False, "")
    return ScanResult([region], True, reason)


def _split_lines(text: str):
    no_term = text.splitlines()
    with_term = text.splitlines(keepends=True)
    lines = []
    pos = 0
    for nt, wt in zip(no_term, with_term):
        full_len = len(wt)
        lines.append((nt, pos, pos + full_len))
        pos += full_len
    return lines


# --- публичный API -------------------------------------------------------


def scan(text) -> ScanResult:
    if not isinstance(text, str):
        return ScanResult([], True, "not_a_string")
    if text == "":
        return ScanResult([], False, "")
    if len(text) > MAX_TEXT_CHARS:
        return _degrade(text, "text_too_large")

    if _no_markers_whole_text(text):
        last_line = max(len(text.splitlines()) - 1, 0)
        region = Region(0, len(text), (KIND_PROSE,), 0, last_line, False, "")
        return ScanResult([region], False, "")

    if _too_many_fence_opens(text):
        return _degrade(text, "max_regions_exceeded")

    lines = _split_lines(text)
    regions: List[Region] = []
    # `pending` -- a mutable [start, end, kinds, line_start, line_end] for an
    # open run of merged same-kind PROSE pieces; a plain list (not a Region)
    # so extending it on each matching line is a cheap in-place mutation
    # instead of rebuilding a NamedTuple via ._replace() on every line (perf
    # budget A4/DoD: 1MB scan <=150ms -- ._replace()-per-line measured as the
    # dominant cost on a 1MB plain-prose profile, see witness).
    pending = None

    for stack, i0, i1, fence_info in _iter_block_runs(lines):
        if fence_info is not None:
            if pending is not None:
                regions.append(Region(pending[0], pending[1], pending[2], pending[3], pending[4], False, ""))
                pending = None
                if len(regions) > MAX_REGIONS:
                    return _degrade(text, "max_regions_exceeded")
            fence_char, fence_len, info, unterminated = fence_info
            start_c = lines[i0][1]
            end_c = lines[i1][2]
            regions.append(Region(start_c, end_c, stack, i0, i1, unterminated, info))
            if len(regions) > MAX_REGIONS:
                return _degrade(text, "max_regions_exceeded")
            continue

        for li in range(i0, i1 + 1):
            nt, s, e = lines[li]
            pieces = _inline_split(nt, s, e, stack, MAX_LINE_INLINE_SPANS)
            if pieces is None:
                return _degrade(text, "max_line_inline_spans_exceeded")
            for (ps, pe, pk) in pieces:
                if pk[-1] == KIND_PROSE and pending is not None and pending[2] == pk and pending[1] == ps:
                    pending[1] = pe
                    pending[4] = li
                    continue
                if pending is not None:
                    regions.append(Region(pending[0], pending[1], pending[2], pending[3], pending[4], False, ""))
                    pending = None
                    if len(regions) > MAX_REGIONS:
                        return _degrade(text, "max_regions_exceeded")
                if pk[-1] == KIND_PROSE:
                    pending = [ps, pe, pk, li, li]
                else:
                    regions.append(Region(ps, pe, pk, li, li, False, ""))
                    if len(regions) > MAX_REGIONS:
                        return _degrade(text, "max_regions_exceeded")

    if pending is not None:
        regions.append(Region(pending[0], pending[1], pending[2], pending[3], pending[4], False, ""))
        if len(regions) > MAX_REGIONS:
            return _degrade(text, "max_regions_exceeded")

    return ScanResult(regions, False, "")


def line_kinds(text) -> List[Tuple[str, ...]]:
    if not isinstance(text, str) or text == "":
        return []
    lines = _split_lines(text)
    result: List[Optional[Tuple[str, ...]]] = [None] * len(lines)
    for stack, i0, i1, _fence in _iter_block_runs(lines):
        for li in range(i0, i1 + 1):
            result[li] = stack
    return result


def kind_at(result: ScanResult, offset: int) -> Tuple[str, ...]:
    regions = result.regions
    if not regions:
        return ()
    starts = [r.start for r in regions]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        return ()
    region = regions[idx]
    if region.start <= offset < region.end:
        return region.kinds
    return ()
