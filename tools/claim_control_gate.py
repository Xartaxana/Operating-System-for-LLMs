"""tools/claim_control_gate_md.py -- region-aware sibling of
tools/claim_control_gate.py (этап 2, СПЕКА B, партия 1, docs/tasks/
2026-08-19_md-regions-scanner-spec.md). Живой tools/claim_control_gate.py
НЕ ТРОГАЕТСЯ (D-0069) -- этот файл нейтральный сосед; посадка
(переименование на боевой путь + регистрация hook_liveness_probe) --
акт Lead.

БАЗА: буквальная копия tools/claim_control_gate.py (path-scoping,
markers, token shapes, ledger-корреляция, D1/D4b/D5/D6/D7/D8/t-022/F5
семантика) -- см. живой файл за полным происхождением каждого фикса,
здесь не повторяется. ЕДИНСТВЕННОЕ отличие по существу: региона-
осведомлённый шестой предикат поверх пяти существующих граничных
регексов (см. "ПОЗИЦИОННЫЙ ИНВАРИАНТ" ниже) в `_find_claim_token_groups`
и предфильтр в `decide()` (см. "И-1" ниже).

КЛАСС (docs/SIBLING_MAP.md :496-510): "сторож не отличает утверждение
автора от цитируемого/вложенного содержимого". Для claim_control_gate
это означает: маркер негативного утверждения ИЛИ токен-претензия могут
физически сидеть внутри цитаты/фенса (чужого/вложенного текста), а не в
собственной прозе автора -- пять существующих граничных регексов режут
текст на "предложения" ВНУТРИ одной физической строки/абзаца, но НИЧЕГО
не знают про markdown-цитаты/фенсы поперёк нескольких строк, поэтому
раньше флагали содержимое цитаты как если бы это было утверждение автора
(ложное срабатывание -- см. discrimination-тест ниже).

ПОЛИТИКА (B2, буквально из спеки): fenced/blockquote НЕ порождают окно
(маркер, чья СОБСТВЕННАЯ позиция попадает в fenced/blockquote регион, не
доходит даже до вычисления _sentence_window -- пропускается целиком, ни
одного токена из его окрестности не извлекается) И не засчитывают
токены (даже когда МАРКЕР сам в прозе и окно создаётся штатно, токен
ВНУТРИ этого окна, чья собственная позиция попадает в fenced/blockquote,
исключается из группы -- как если бы его не было); inline_code
засчитывается -- ни маркер, ни токен в inline_code не исключаются
регионом (то же приоритетное правило 1..5, что и в tools/
negative_lint_md.py._classify -- см. _classify ниже, идентичная логика,
задокументированная отдельно в этом файле, а не импортированная оттуда:
два разных сторожа с двумя разными политиками, D-0043 здесь не про общий
код классификации, а про общий СКАНЕР -- каждый потребитель решает
семантику сам, см. md_regions.py докстринг "Решение 08-16 (d3)").

ПОЗИЦИОННЫЙ ИНВАРИАНТ (буквально из спеки): пять граничных регексов
живого файла (_SENTENCE_PUNCT_RE, _PARAGRAPH_BREAK_RE,
_LIST_ITEM_BOUNDARY_RE, _TABLE_ROW_BOUNDARY_RE, _HEADING_BOUNDARY_RE и
их сборка _BOUNDARY_RES) скопированы сюда БАЙТ В БАЙТ, не изменены ни
байтом -- см. test_claim_control_gate_md.py::
test_five_boundary_regex_patterns_byte_identical_to_live, сверка
.pattern построчно против живого модуля -- регион здесь ШЕСТАЯ,
ДОПОЛНИТЕЛЬНАЯ граница, применяется ПОСЛЕ (не вместо) существующих пяти:
_find_claim_token_groups ниже вычисляет окно ТЕМ ЖЕ _sentence_window,
что и раньше, регион лишь (а) решает, создавать ли окно ВООБЩЕ для
данного вхождения маркера, и (б) фильтрует уже извлечённые токен-спаны
ДО их группировки _group_overlapping_spans (тоже нетронута). Р9(а)
решения Lead 08-19: границы claim_control_gate ВНУТРИ фенса НЕ
подавляются -- пять регексов матчатся по всему сырому тексту без
region-осведомлённости вообще (не проверяют, находятся ли они "внутри
фенса") -- ЭТОГО кода в файле попросту нет, что и есть буквальное
соблюдение Р9(а): нечего "не подавлять", раз это никогда не трогалось.

И-0 (ЛЮБОЙ отказ модуля md_regions) -> сторож ведёт себя КАК СЕГОДНЯ
побайтно: `_find_claim_token_groups(text, scan_result=None)` выполняет
РОВНО тот алгоритм живого файла (каждый `if scan_result is not None:`
ниже -- мёртвая ветка при None, тот же порядок вставки в `found`, тот же
результат) -- см. _safe_scan.

И-1 (Rule #1, ленивость) / B2 "вызов сканера после path-scoping и
маркер-хита": scan() вызывается РОВНО ОДИН РАЗ за весь decide(), и
ТОЛЬКО ПОСЛЕ (а) tool_name/tool_input/path/text прошли существующий
path-scoping (как и раньше -- ни один из этих шагов region не касается),
(б) дешёвая проверка "хотя бы один NEGATIVE_MARKERS-паттерн матчится
ГДЕ-ТО в тексте" (pattern.search, без вычисления окон/токенов) дала True
-- на тексте без единого маркера scan() не вызывается вовсе (счётчик 0).
"""
import bisect
import glob
import json
import os
import re
import sys

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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LEDGER_DIR = os.path.join(REPO, "logs", ".search-ledger")

# --- path scoping (t-021 D8) ----------------------------------------------

ROOT_FILES = {
    "DECISIONS.md",
    "CURRENT_CONTEXT.md",
    "DELEGATION_TABLE.md",
    "CLAUDE.md",
    "SYSTEM_PROMPT.md",
    "README.md",
    "BOOT.md",
    "ROADMAP.md",
    "ARCHITECTURE.md",
    "ARCHITECTURE_BOOT.md",
    "MEMORY_ARCHITECTURE.md",
    "WHITE_PAPER.md",
    "PROJECT_CHARTER.md",
    "PROJECT_PHILOSOPHY.md",
    "ANTI_GOALS.md",
}
ROOT_FILES_LOWER = {f.lower() for f in ROOT_FILES}
ROUTING_LOG_PATH = "logs/routing-log.jsonl"

_POSIX_DRIVE_RE = re.compile(r"^/([A-Za-z])(/.*)?$")

# --- negative markers, case-insensitive, Russian and English -------------

NEGATIVE_MARKERS = (
    "не существует",
    "не найден",
    "отсутству",
    "нет ни одного",
    "нигде не",
    "не содержит",
    "не содержится",
    "не удалось найти",
    "нет ",
    "does not exist",
    "doesn't exist",
    "not found",
    "no such",
    "nowhere",
    "is absent",
    "are absent",
    "0 matches",
    "no matches",
    "does not have",
    "doesn't have",
    "never existed",
    "has no",
    "have no",
    "there is no",
    "there are no",
    "is missing",
    "are missing",
    "lacks",
    "never found",
)

_MARKER_NO_SUFFIX_BOUNDARY = {"отсутству"}

_WORD_CHAR_RE = re.compile(r"\w", re.UNICODE)


def _boundary_pattern_for_marker(marker: str) -> str:
    escaped = re.escape(marker)
    prefix = r"\b" if _WORD_CHAR_RE.match(marker[0]) else ""
    if marker in _MARKER_NO_SUFFIX_BOUNDARY:
        suffix = ""
    else:
        suffix = r"\b" if _WORD_CHAR_RE.match(marker[-1]) else ""
    return prefix + escaped + suffix


_MARKER_PATTERNS = tuple(
    (marker, re.compile(_boundary_pattern_for_marker(marker), re.IGNORECASE))
    for marker in NEGATIVE_MARKERS
)

# --- token shapes (spec point 4) ------------------------------------------

PATH_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_.\-]+(?:[/\\][A-Za-z0-9_.\-]+)+\.[A-Za-z0-9]+"
)
EXT_TOKEN_RE = re.compile(
    r"\b[A-Za-z0-9_\-]+\.(?:py|md|json|yaml|jsonl|js)\b"
)
UPPER_SNAKE_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

TOKEN_RES = (PATH_TOKEN_RE, EXT_TOKEN_RE, UPPER_SNAKE_RE)

MIN_TERM_LEN = 3

MSG_TEMPLATE = (
    "Negative claim about to be written without a matching search/read this "
    "session (rule 6, command hygiene): a positive control is required "
    "before reporting absence. Unverified token(s): {tokens}"
)


def _ledger_dir():
    return os.environ.get("SEARCH_CONTROL_GATE_LEDGER_DIR") or _DEFAULT_LEDGER_DIR


def _first(d, keys):
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return None


def _posix_drive_to_windows(p):
    m = _POSIX_DRIVE_RE.match(p)
    if not m:
        return None
    drive = m.group(1)
    rest = m.group(2) or "/"
    return f"{drive}:{rest}"


def _normalize_repo_relative(path_str):
    p = path_str.replace("\\", "/")
    posix_win = _posix_drive_to_windows(p)
    candidate = posix_win if posix_win is not None else path_str
    if posix_win is not None or os.path.isabs(candidate):
        try:
            rel = os.path.relpath(candidate, REPO).replace("\\", "/")
            if not rel.startswith(".."):
                return rel
        except Exception:
            pass
        repo_prefix = REPO.replace("\\", "/").rstrip("/") + "/"
        base = posix_win if posix_win is not None else p
        if base.lower().startswith(repo_prefix.lower()):
            return base[len(repo_prefix):]
        return base
    if p.startswith("./"):
        p = p[2:]
    return p


def _in_scope(path_str):
    if not path_str:
        return False
    rel = _normalize_repo_relative(path_str)
    rel_lower = rel.lower()
    if rel_lower.startswith("process/"):
        return True
    if rel_lower.startswith("docs/"):
        return True
    if rel_lower == ROUTING_LOG_PATH.lower():
        return True
    if "/" not in rel and rel_lower in ROOT_FILES_LOWER:
        return True
    return False


# --- text extraction (spec point 2) --------------------------------------

WRITE_TEXT_KEYS = ("content", "text", "file_text", "fileText", "new_content")
EDIT_TEXT_KEYS = ("new_string", "newString", "replacement", "new_text", "newText")


def _extract_text(tool_name, tool_input):
    if not isinstance(tool_input, dict):
        return None
    primary = WRITE_TEXT_KEYS if tool_name == "Write" else EDIT_TEXT_KEYS
    secondary = EDIT_TEXT_KEYS if tool_name == "Write" else WRITE_TEXT_KEYS
    for k in primary + secondary:
        v = tool_input.get(k)
        if isinstance(v, str):
            return v
    return None


# --- negative-claim scan: sentence-scoped windowing (t-021 D4b, t-022 fix) -
# ПОЗИЦИОННЫЙ ИНВАРИАНТ: пять регексов ниже -- байт-в-байт копия живого
# tools/claim_control_gate.py (:463-499 живого дерева на момент копии).
# НЕ РЕДАКТИРОВАТЬ без синхронной правки живого файла Lead'ом.

_SENTENCE_PUNCT_RE = re.compile(r"[.!?](?=\s|$)")
_PARAGRAPH_BREAK_RE = re.compile(r"\n[ \t]*\n[ \t]*")
_LIST_ITEM_BOUNDARY_RE = re.compile(
    r"\n[ \t]*(?=[-*+](?:[ \t]|$)|\d+\.(?:[ \t]|$))"
)
_TABLE_ROW_BOUNDARY_RE = re.compile(r"\n[ \t]*(?=\|)")
_HEADING_BOUNDARY_RE = re.compile(r"\n[ \t]*(?=#{1,6}(?:[ \t]|$))")

_BOUNDARY_RES = (
    _SENTENCE_PUNCT_RE,
    _PARAGRAPH_BREAK_RE,
    _LIST_ITEM_BOUNDARY_RE,
    _TABLE_ROW_BOUNDARY_RE,
    _HEADING_BOUNDARY_RE,
)
# --- конец байт-в-байт копии пяти регексов ---------------------------------


def _find_boundaries(text):
    spans = []
    for regex in _BOUNDARY_RES:
        for m in regex.finditer(text):
            spans.append((m.start(), m.end()))
    return spans


def _sorted_boundary_edges(boundaries):
    ends_sorted = sorted(b_end for _b_start, b_end in boundaries)
    starts_sorted = sorted(b_start for b_start, _b_end in boundaries)
    return ends_sorted, starts_sorted


def _sentence_window(text, marker_start, marker_end, boundary_edges):
    ends_sorted, starts_sorted = boundary_edges
    end_idx = bisect.bisect_right(ends_sorted, marker_start)
    start = ends_sorted[end_idx - 1] if end_idx > 0 else 0
    start_idx = bisect.bisect_left(starts_sorted, marker_end)
    end = starts_sorted[start_idx] if start_idx < len(starts_sorted) else len(text)
    return start, end


def _scan_negative_claims(text):
    """Немодифицированная форма (маркер, окно) -- сохранена для прямого
    юнит-тестирования/регресса паритета с живым файлом; region-осведом-
    лённый пайплайн (`_find_claim_token_groups` ниже) её НЕ вызывает --
    ему нужна ещё и позиция самого маркера (marker_start/marker_end) для
    региона, которую эта функция не отдаёт наружу."""
    boundary_edges = _sorted_boundary_edges(_find_boundaries(text))
    for marker, pattern in _MARKER_PATTERNS:
        for m in pattern.finditer(text):
            idx = m.start()
            marker_end = m.end()
            s, e = _sentence_window(text, idx, marker_end, boundary_edges)
            window = text[s:e].replace("\n", " ")
            yield marker, window


# --- token extraction + overlap grouping (t-021 D1) -----------------------


def _extract_token_spans(window):
    spans = []
    for regex in TOKEN_RES:
        for m in regex.finditer(window):
            spans.append((m.start(), m.end(), m.group(0)))
    return spans


def _extract_tokens(window):
    return {tok for _, _, tok in _extract_token_spans(window)}


def _group_overlapping_spans(spans):
    if not spans:
        return []
    ordered = sorted(spans, key=lambda t: (t[0], t[1]))
    groups = []
    current = [ordered[0]]
    current_end = ordered[0][1]
    for span in ordered[1:]:
        if span[0] < current_end:
            current.append(span)
            current_end = max(current_end, span[1])
        else:
            groups.append(current)
            current = [span]
            current_end = span[1]
    groups.append(current)
    return [frozenset(tok for _, _, tok in g) for g in groups]


# --- region gate (B2, t-509) -----------------------------------------------


def _safe_scan(text: str):
    """И-0: None при отсутствии md_regions / исключении scan() /
    degraded=True -- все три триггера сводятся к одному сигналу
    вызывающему коду (region-путь целиком отключается)."""
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
    starts = [r.start for r in regions]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        return None
    region = regions[idx]
    if region.start <= offset < region.end:
        return region
    return None


def _classify(region) -> str:
    """Тот же приоритет, что tools/negative_lint_md.py._classify (см.
    его докстринг для полного обоснования порядка) -- НАМЕРЕННО не
    импортирован оттуда: два сторожа, две отдельные семантики region-
    политики, D-0043 здесь про общий СКАНЕР, не общий predicate."""
    if region is None:
        return "prose"
    if region.unterminated and KIND_FENCED in region.kinds:
        return "prose"
    if KIND_FENCED in region.kinds:
        return "fenced"
    if KIND_INLINE_CODE in region.kinds:
        return "inline_code"
    if KIND_BLOCKQUOTE in region.kinds:
        return "blockquote"
    return "prose"


_EXCLUDED_KINDS = ("fenced", "blockquote")


def _find_claim_token_groups(text, scan_result=None):
    """Region-осведомлённая версия. scan_result=None (И-0 дефолт) ->
    ПОЛНОСТЬЮ совпадает с алгоритмом живого файла: каждый
    `if scan_result is not None:` ниже -- мёртвая ветка, тот же порядок
    matcherов (_MARKER_PATTERNS -> finditer), тот же порядок вставки в
    `found` (первый маркер группы побеждает) -- см. докстринг модуля
    "И-0". scan_result передан (region доступен) -> B2 политика: маркер,
    чья ПОЗИЦИЯ попадает в fenced/blockquote, не порождает окно вовсе
    (continue до _sentence_window); токен, чья ПОЗИЦИЯ (после перевода
    из window-относительных координат в абсолютные: s + rel_start --
    замена "\\n"->" " в window не меняет длину, абсолютное индексирование
    остаётся валидным) попадает в fenced/blockquote, не засчитывается --
    отфильтрован ДО _group_overlapping_spans, так что группа, все токены
    которой были только цитируемыми, исчезает целиком (frozenset()
    falsy -> `if group` ниже её отбрасывает, как и раньше для пустых
    групп)."""
    found = {}
    boundary_edges = _sorted_boundary_edges(_find_boundaries(text))
    for marker, pattern in _MARKER_PATTERNS:
        for m in pattern.finditer(text):
            idx = m.start()
            marker_end = m.end()
            if scan_result is not None:
                mkind = _classify(_region_at(scan_result, idx))
                if mkind in _EXCLUDED_KINDS:
                    continue  # B2: fenced/blockquote -- окно не создаётся
            s, e = _sentence_window(text, idx, marker_end, boundary_edges)
            window = text[s:e].replace("\n", " ")
            spans = _extract_token_spans(window)
            if scan_result is not None:
                spans = [
                    sp for sp in spans
                    if _classify(_region_at(scan_result, s + sp[0])) not in _EXCLUDED_KINDS
                ]
            for group in _group_overlapping_spans(spans):
                if group and group not in found:
                    found[group] = marker
    return found


# --- ledger correlation (spec point 5, t-021 D6/D7) ------------------------


def _session_id(payload):
    if isinstance(payload, dict):
        value = payload.get("session_id")
        if isinstance(value, str) and value:
            return value
    return None


def _read_ledger_terms(session):
    terms = []
    try:
        ledger_dir = _ledger_dir()
        if not os.path.isdir(ledger_dir):
            return terms
        if session:
            names = [session + ".jsonl"]
            if session != "unknown":
                names.append("unknown.jsonl")
            paths = [os.path.join(ledger_dir, n) for n in names]
        else:
            paths = glob.glob(os.path.join(ledger_dir, "*.jsonl"))
        for path in paths:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    term = rec.get("term") if isinstance(rec, dict) else None
                    if isinstance(term, str) and term:
                        terms.append(term)
    except Exception:
        pass
    return terms


def _is_word_char(ch):
    return bool(ch) and (ch.isalnum() or ch == "_")


def _boundary_contains(haystack, needle):
    if len(needle) < MIN_TERM_LEN:
        return False
    h = haystack.lower()
    n = needle.lower()
    start = 0
    while True:
        idx = h.find(n, start)
        if idx == -1:
            return False
        before_ok = idx == 0 or not _is_word_char(h[idx - 1])
        after_pos = idx + len(n)
        after_ok = after_pos == len(h) or not _is_word_char(h[after_pos])
        if before_ok and after_ok:
            return True
        start = idx + 1


def _token_satisfied(token, terms):
    for term in terms:
        if len(term) < MIN_TERM_LEN:
            continue
        if _boundary_contains(term, token):
            return True
        if _boundary_contains(token, term):
            return True
    return False


def decide(payload):
    """Pure logic, no I/O beyond reading the ledger. exit_code ALWAYS 0.
    region-aware addition: scan() called at most once, AFTER path-scoping
    and a cheap "any marker occurs anywhere" pre-check (И-1)."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = _first(payload, ("tool_name", "toolName", "tool"))
    if tool_name not in ("Edit", "Write"):
        return 0, None

    tool_input = _first(payload, ("tool_input", "toolInput", "input", "parameters"))
    if not isinstance(tool_input, dict):
        return 0, None

    path = _first(tool_input, ("file_path", "path", "filePath", "file"))
    if not isinstance(path, str) or not _in_scope(path):
        return 0, None

    text = _extract_text(tool_name, tool_input)
    if not text:
        return 0, None

    # И-1: дешёвый предфильтр -- хотя бы один негативный маркер ГДЕ-ТО в
    # тексте, БЕЗ вычисления окон/токенов. На тексте без маркеров scan()
    # не вызывается вовсе (см. test_scan_not_called_when_no_marker_hit).
    if not any(pattern.search(text) for _marker, pattern in _MARKER_PATTERNS):
        return 0, None

    scan_result = _safe_scan(text)
    groups = _find_claim_token_groups(text, scan_result)
    if not groups:
        return 0, None

    terms = _read_ledger_terms(_session_id(payload))
    unsatisfied = {
        group: marker
        for group, marker in groups.items()
        if not any(_token_satisfied(tok, terms) for tok in group)
    }
    if not unsatisfied:
        return 0, None

    parts = []
    for group, marker in sorted(unsatisfied.items(), key=lambda kv: sorted(kv[0])[0]):
        rep = max(group, key=len)
        parts.append(f'"{rep}" (flagged by "{marker}")')
    context = MSG_TEMPLATE.format(tokens="; ".join(parts))
    return 0, {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _read_stdin_bytes():
    if sys.stdin.isatty():
        return b""
    return sys.stdin.buffer.read()


def main():
    try:
        _reconfigure_stdout_utf8()
        raw_bytes = _read_stdin_bytes()
        if not raw_bytes:
            return 0
        raw = raw_bytes.decode("utf-8", errors="replace")
        payload = json.loads(raw)
        exit_code, output = decide(payload)
        if output is not None:
            sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
        return exit_code
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
