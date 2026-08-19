r"""negative_lint_md.py -- region-aware sibling of tools/negative_lint.py
(этап 2, СПЕКА B, partия 1, t-509 / docs/tasks/2026-08-19_md-regions-
scanner-spec.md). Живой tools/negative_lint.py НЕ ТРОГАЕТСЯ (D-0069) --
это НЕЙТРАЛЬНЫЙ сосед; посадка (переименование на боевой путь +
регистрация) -- акт Lead.

КЛАСС (docs/SIBLING_MAP.md :496-510): "сторож не отличает утверждение
автора от цитируемого/вложенного содержимого". Для negative_lint это
конкретно means: substring-поиск CONTROL_MARKERS в окне ±3 строки не
различал, где ФИЗИЧЕСКИ лежит слово-контроль -- в прозе автора (значит,
это его собственная верификация) или внутри цитаты/фенса ЧУЖОГО текста
(значит, это не верификация автора вообще, а случайное слово внутри
цитируемого материала) -- ложное МОЛЧАНИЕ (силится реальное нарушение).
Симметрично для самого НЕГАТИВНОГО маркера: если он сидит в цитате/
фенсе, это не собственное утверждение автора -- не нарушение.

ПОЛИТИКА (B1, буквально из спеки): fenced/blockquote -- НЕ нарушение
(и НЕ засчитываются как контроль), inline_code -- нарушение (и
засчитывается как контроль). НЕЗАКРЫТЫЙ ФЕНС = ПРОЗА (урок "silence
looks like success" -- деградация модуля или незакрытость разметки не
должна РАСШИРЯТЬ зону молчания; безопаснее ошибочно посчитать нарушением
кусок незакрытого фенса, чем ошибочно его проглотить).

ПРИОРИТЕТ КЛАССИФИКАЦИИ ОДНОЙ ПОЗИЦИИ (_classify, собственное инженерное
решение, не угадано молча -- обосновано и разрешено ниже, а не оставлено
вопросом координатору, потому что негативный контроль дискриминации §8
п.4 драфта делает выбор ПРОВЕРЯЕМЫМ, а не произвольным): Region.kinds --
кортеж, может быть ("blockquote","fenced") или ("blockquote","prose")
или ("blockquote","inline_code") и т.д. (md_regions.py, edge (б) и
_inline_split). Правило buit here:
  1. unterminated И KIND_FENCED в kinds -> "prose" (правило "незакрытый
     фенс = проза", ПЕРЕД всем остальным -- перекрывает даже вложенность
     в цитату).
  2. KIND_FENCED в kinds -> "fenced" (фенс никогда не смешивается с
     inline_code -- фенсовые строки не проходят через инлайн-сплиттер
     md_regions.scan(), см. его исходник).
  3. KIND_INLINE_CODE в kinds -> "inline_code" (даже если в кавычке --
     "инлайн-код -- нарушение" читается буквально безусловно, ничем не
     ограничено по вложенности в спеке).
  4. KIND_BLOCKQUOTE в kinds (без 1-3) -> "blockquote" (обычная
     цитируемая проза, ("blockquote","prose") в md_regions -- НЕ
     нарушение).
  5. иначе -> "prose" (верхнеуровневая проза автора, дефолт).
Это разрешает единственный явный фор к спеки: правило "fenced/blockquote
-- не нарушение, inline_code -- нарушение" читается ПОРЯДКОМ приоритета
(1 > 2 > 3 > 4 > 5), а не независимыми битами -- альтернатива (например,
"любая примесь blockquote гасит, даже при наличии inline_code") сделала
бы негативный контроль дискриминации (см. ниже) НЕРАЗЛИЧИМЫМ (обе formы
дали бы одинаковый результат для теста-пары "контроль в цитате рядом с
негативом в прозе"), а спецификация §8 п.4 драфта требует, чтобы
отключение регион-фильтра реально МЕНЯЛО результат -- порядковое чтение
единственное, что это гарантирует.

ПОЗИЦИОННЫЙ ИНВАРИАНТ (буквально из спеки): окно ±3 строки вычисляется
по ИСХОДНЫМ индексам строк text.splitlines() -- ни один индекс не
сдвигается и не перенумеровывается из-за региона (фильтрация региона --
это ДОПОЛНИТЕЛЬНЫЙ предикат НА строке, найденной обычным способом, не
переиндексация списка строк). ТЕСТ-ПАРА "контроль в цитате рядом с
негативом в прозе": негатив сидит в прозе (кандидат в нарушение),
контрольное слово физически внутри цитаты в пределах окна ±3 -- регион-
фильтр обязан РАЗЛИЧИТЬ два случая и не дать цитируемому "контролю"
погасить реальное нарушение (см. test_negative_lint_md.py, discrimination
раздел, и ОТДЕЛЬНЫЙ прогон с MODULE_UNDER_TEST=live, который на этом же
тексте гасит нарушение -- красный прогон как негативный контроль §8 п.4).

И-0 (ЛЮБОЙ отказ модуля md_regions -- ImportError модуля целиком,
исключение из scan(), или scan()'а degraded=True результат) -> сторож
ведёт себя КАК СЕГОДНЯ побайтно: find_violations() тогда выполняет РОВНО
тот же алгоритм, что и живой tools/negative_lint.py (окно ±3 по
substring-совпадению, без единого обращения к региону) -- см. _safe_scan
и каждое "if scan_result is not None:" ниже, которое становится
NO-OP при scan_result is None -- ветвление НЕ пересобрано отдельным
путём кода, это ОДИН и тот же цикл с region-веткой, ставшей мёртвой.

И-1 (Rule #1, ленивость): сканер зовётся ПОСЛЕ дешёвого предфильтра --
дешёвый предфильтр здесь ЭТО УЖЕ существующий O(n) substring-поиск
NEG_MARKERS по всем строкам (find_violations всегда делал это ПЕРВЫМ
шагом); scan() вызывается РОВНО ОДИН РАЗ за весь вызов find_violations,
и ТОЛЬКО если этот предфильтр нашёл хотя бы одну строку-кандидата -- на
тексте без единого негативного маркера scan() не вызывается вовсе (счётчик
0, см. test_scan_not_called_when_no_negative_markers).

Импорт -- пара try/except (образец tools/owns_gate.py:545-558), плюс
ДОПОЛНИТЕЛЬНЫЙ внешний слой (owns_gate предполагает dispatch_gate.py
ГАРАНТИРОВАННО существующим соседом; md_regions.py по И-0 должен
переживать ПОЛНОЕ отсутствие -- отсутствующий сосед не боевая ошибка,
а штатный "модуль ещё не посажен" путь до появления первого
потребителя): при провале ОБЕИХ форм импорта `scan` остаётся None,
region-путь молча выключается (тот же I-0 фоллбек, что и на исключение
из уже импортированного scan()).
"""

import argparse
import bisect
import json
import sys
from pathlib import Path

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

NEG_MARKERS_RU = [
    "не найден",
    "не существует",
    "отсутств",
    "нет ни одного",
    "нигде не",
    "0 совпадений",
]
NEG_MARKERS_EN = [
    "not found",
    "does not exist",
    "no such",
    "absent",
    "nowhere",
    "0 matches",
]
NEG_MARKERS = NEG_MARKERS_RU + NEG_MARKERS_EN

CONTROL_MARKERS_RU = [
    "контрол",
    "образец",
    "позитивн",
    "та же форм",
    "известно-существующ",
    "закрыто",
]
CONTROL_MARKERS_EN = [
    "control",
    "known-present",
    "same form",
    "positive check",
]
CONTROL_MARKERS = CONTROL_MARKERS_RU + CONTROL_MARKERS_EN

WINDOW_RADIUS = 3
PREVIEW_MAX_LEN = 200
PREVIEW_HEAD_COUNT = 3

WARN_PREFIX_TEMPLATE = (
    "NEGATIVE LINT: {n} негативных утверждений без соседнего контроля формы: "
    "{body}. Негатив без позитивного одноформенного контроля — кандидат в "
    "reject (гигиена п.6/D-0094)."
)

# regions чьи kinds исключают позицию из рассмотрения (ни как нарушение,
# ни как контроль) -- см. докстринг модуля, "ПОЛИТИКА".
_EXCLUDED_KINDS = ("fenced", "blockquote")


def _line_has_any_marker(line_lower: str, markers: list) -> bool:
    return any(marker in line_lower for marker in markers)


def _safe_scan(text: str):
    """И-0: None при отсутствии модуля / исключении scan() / degraded=True
    -- всё три триггера сводятся к одному сигналу "региона нет" для
    вызывающего кода (find_violations просто перестаёт фильтровать по
    региону, полностью совпадая со старым алгоритмом)."""
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
    """Тот же bisect-алгоритм, что md_regions.kind_at(), но возвращает
    ЦЕЛЫЙ Region (не только его kinds) -- нужен доступ к .unterminated
    для правила "незакрытый фенс = проза"."""
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
    """См. докстринг модуля, "ПРИОРИТЕТ КЛАССИФИКАЦИИ". region is None
    (нет региона на этой позиции, конец текста, вне покрытия) -> "prose"
    (безопасный дефолт -- поведение как без региона вовсе)."""
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


def _line_start_offsets(text: str) -> list:
    """Смещения начала каждой строки text.splitlines() в СИМВОЛАХ
    исходного текста -- та же схема, что md_regions._split_lines()
    (splitlines(keepends=True), кумулятивная сумма длин)."""
    offsets = []
    pos = 0
    for wt in text.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(wt)
    return offsets


def _marker_offset_in_line(line_lower: str, markers: list) -> int:
    """Позиция первого совпавшего маркера внутри УЖЕ найденной строки
    (строка гарантированно несёт хотя бы один маркер -- вызывается только
    после _line_has_any_marker вернул True). Позиция в lower()-строке --
    для ASCII/кириллицы набора маркеров .lower() не меняет длину, так что
    индекс совпадает с исходной строкой (нет модификаторов длины в этом
    алфавите)."""
    for marker in markers:
        idx = line_lower.find(marker)
        if idx != -1:
            return idx
    return 0


def find_violations(text: str) -> list:
    """Возвращает список (line_no 1-индексированный, original_line_text)
    для каждой строки text, несущей негативный маркер БЕЗ контрольного
    маркера в окне ±WINDOW_RADIUS строк (включая саму строку), с региона-
    политикой B1 (fenced/blockquote исключены с ОБЕИХ сторон, inline_code
    и проза учитываются; незакрытый фенс = проза) -- см. докстринг модуля
    целиком. Пустой text -> пустой список (тихий путь и для hook, и для
    CLI, не изменилось)."""
    if not text:
        return []
    lines = text.splitlines()
    lowered = [ln.lower() for ln in lines]

    negative_idxs = [i for i, low in enumerate(lowered) if _line_has_any_marker(low, NEG_MARKERS)]
    if not negative_idxs:
        return []  # И-1: scan() НЕ вызывается -- нечего проверять

    scan_result = _safe_scan(text)
    line_offsets = _line_start_offsets(text) if scan_result is not None else None

    violations = []
    for i in negative_idxs:
        if scan_result is not None:
            pos = _marker_offset_in_line(lowered[i], NEG_MARKERS)
            kind = _classify(_region_at(scan_result, line_offsets[i] + pos))
            if kind in _EXCLUDED_KINDS:
                continue  # B1: fenced/blockquote -- не нарушение

        lo = max(0, i - WINDOW_RADIUS)
        hi = min(len(lines) - 1, i + WINDOW_RADIUS)
        window_has_control = False
        for j in range(lo, hi + 1):
            if not _line_has_any_marker(lowered[j], CONTROL_MARKERS):
                continue
            if scan_result is not None:
                cpos = _marker_offset_in_line(lowered[j], CONTROL_MARKERS)
                ckind = _classify(_region_at(scan_result, line_offsets[j] + cpos))
                if ckind in _EXCLUDED_KINDS:
                    continue  # цитируемый/фенсовый "контроль" не считается
            window_has_control = True
            break
        if not window_has_control:
            violations.append((i + 1, lines[i]))
    return violations


def _truncate(s: str, max_len: int = PREVIEW_MAX_LEN) -> str:
    s = s.strip()
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def format_warning(violations: list) -> str:
    if not violations:
        return ""
    n = len(violations)
    head = violations[:PREVIEW_HEAD_COUNT]
    parts = [f"line {line_no}: {_truncate(line_text)}" for line_no, line_text in head]
    body = "; ".join(parts)
    return WARN_PREFIX_TEMPLATE.format(n=n, body=body)


def _extract_text(tool_response) -> str:
    if isinstance(tool_response, str):
        return tool_response
    if tool_response is None:
        return ""
    if isinstance(tool_response, dict):
        content = tool_response.get("content")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    t = block.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(block, str):
                    parts.append(block)
            if parts:
                return "\n".join(parts)
        for key in ("text", "output", "stdout", "stderr"):
            value = tool_response.get(key)
            if isinstance(value, str):
                return value
        try:
            return json.dumps(tool_response, ensure_ascii=False)
        except Exception:
            return str(tool_response)
    return str(tool_response)


def decide(payload: dict) -> tuple:
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, None

    tool_response = payload.get("tool_response")
    if isinstance(tool_response, dict) and (
        tool_response.get("isAsync") is True
        or tool_response.get("status") == "async_launched"
    ):
        return 0, None

    text = _extract_text(tool_response)
    violations = find_violations(text)
    if not violations:
        return 0, None

    context = format_warning(violations)
    return 0, {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _cli_main(text_path: str) -> int:
    try:
        raw_bytes = Path(text_path).read_bytes()
        text = raw_bytes.decode("utf-8", errors="replace")
        violations = find_violations(text)
        warning = format_warning(violations)
        if warning:
            print(warning)
    except Exception:
        pass
    return 0


def _hook_main() -> int:
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    exit_code, output = decide(payload)
    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return exit_code


def main() -> int:
    _reconfigure_stdout_utf8()
    try:
        argv = sys.argv[1:]
        if argv:
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument("--text")
            args, _unknown = parser.parse_known_args(argv)
            if args.text:
                return _cli_main(args.text)
        return _hook_main()
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
