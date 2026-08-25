r"""tools/negative_lint.py -- PostToolUse-хук в WARN-РЕЖИМЕ (НИКОГДА не
блокирует) для результатов субагентов (tool_name Task/Agent), плюс
отдельный CLI-режим для линта произвольного текстового файла. Живой
файл, region-aware с 2026-08-19 (этап 2, СПЕКА B, партия 1, t-509 /
docs/tasks/2026-08-19_md-regions-scanner-spec.md, класс
docs/SIBLING_MAP.md :496-510 "сторож не отличает утверждение автора от
цитируемого/вложенного содержимого"). Прежний (до-region) рационал
модуля восстановлен здесь дословно из коммита e98f56b (последняя
правка живого файла ДО посадки байт-копией region-сиблинга 89b6142,
которая заместила этот докстринг самоссылочной шапкой -- находка
критика 2026-08-19).

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

--- Рационал ДО region-aware версии (восстановлено дословно из
e98f56b, см. шапку выше) -----------------------------------------

VG-3 (t-300): исходный t-300-механизм этого модуля -- WARN-линт
негативов без одноформенного контроля; region-осведомлённость (В1
выше) добавлена ПОВЕРХ него, не заменяет.

МОТИВ (спека буквально): критерий «негативное утверждение только с
позитивным одноформенным контролем» (командная гигиена CLAUDE.md п.6,
D-0094) держится ТЕКСТОМ DoD и судейскими ключами -- дисциплиной, не
машиной. Класс промахов рецидивирует (t-268/t-272 прошли двух судей;
2026-07-23 t-296 -- scout заявил «docs/book не существует» при
существующем каталоге). Порог промоции в машинный слой (D-0063)
пройден -- этот файл машинизирует ПОДСКАЗКУ (не решение): WARN, что
негатив стоит рядом БЕЗ соседнего контроля, конечное суждение
(reject/не reject) остаётся за координатором/критиком/судьёй.

УСТРОЙСТВО (образцы -- tools/hygiene_gate.py, tools/journal_echo.py,
tools/dispatch_gate.py, все прочитаны целиком перед реализацией):

 - Совпадение payload-контракта PostToolUse и байт-безопасного чтения
   stdin -- буквально тот же паттерн, что hygiene_gate.py/journal_echo.py:
   sys.stdin.buffer.read() + decode("utf-8", errors="replace") --
   обходит платформенную кодировку текстового sys.stdin и fail-open на
   не-UTF8 байты (адверсариальный ключ DoD п.3).
 - tool_name-фильтр -- ДОСЛОВНО тот же список, что уже использует
   tools/dispatch_gate.py (строка 168, читано перед реализацией, не
   угадано): `tool_name in ("Task", "Agent")` -- это ДВА литеральных
   значения одного и того же PreToolUse/PostToolUse-тула (matcher
   ".claude/settings.json" уже пишет их той же парой через `|`), не
   RU/EN алиасы одного слова -- сама спека задачи говорит "tool_name
   Agent/Task" тем же порядком слов, что этот эмпирический прецедент.
 - Формат ответа хука -- ТА ЖЕ форма, что journal_echo.py уже
   подтвердил живым Lead-смоком на этом харнессе (см. докстринг
   tools/journal_echo.py, "ВЫВОД"): один JSON-объект в stdout,
   {"hookSpecificOutput": {"hookEventName": "PostToolUse",
   "additionalContext": "<строка>"}}, БЕЗ permissionDecision (WARN,
   не blocking-решение -- та же осторожность, что B1 hygiene_gate.py:
   поле permissionDecision здесь тоже намеренно отсутствует). exit
   code ВСЕГДА 0 -- WARN-режим по спеке, никогда не блокирует.

ИЗВЛЕЧЕНИЕ ТЕКСТА ИЗ tool_response (спека DoD п.3: "результат-объект
вместо строки (вложенный content)" -- явный адверсариальный кейс):
tool_response субагента реальной формы этого харнесса эмпирически НЕ
захвачен (тот же ограничитель метода, что tools/dod_gate.py уже
документирует для XWb/Task-payload -- живой захват требовал бы
Task/Agent-тула вне роли builder, D-0037). Извлечение построено
максимально терпимо к разным формам, тем же принципом, что
tools/dod_track.py._extract_text (образец из GIVEN):

 1. tool_response -- строка -> используется как есть.
 2. tool_response -- dict с полем "content", являющимся списком блоков
    (форма content-блоков Anthropic API, {"type": "text", "text": ...}
    или голая строка-элемент) -> тексты всех "text"-блоков склеиваются
    через перевод строки.
 3. Иначе -- dict с одним из полей "text"/"output"/"stdout"/"stderr"
    (строка) -> используется первое найденное.
 4. Иначе (структура не опознана) -> json.dumps всего tool_response --
    регекспы/маркеры всё равно имеют, по чему искать (тот же фоллбек,
    что dod_track.py._extract_text для незнакомой формы payload'а).
 5. tool_response отсутствует/None -> пустая строка -> анализ на
    пустом тексте всегда даёт "нет нарушений" -> тихий exit 0 (спека
    DoD п.3: "payload без tool_response" -- отдельный позитивный
    кейс).

МАРКЕРЫ (спека, буквально два списка, RU+EN, регистронезависимо;
substring-сравнение по .lower() -- НЕ regex/word-boundary: спека сама
требует срабатывания "в середине слова" -- «отсутствует» должно ловиться
маркером «отсутств», «не найдено ни» -- маркером «не найден» -- оба
проверены тестами tools/test_negative_lint.py):

 НЕГАТИВ:  не найден / не существует / отсутств / нет ни одного /
           нигде не / 0 совпадений (RU) ;
           not found / does not exist / no such / absent / nowhere /
           0 matches (EN)
 КОНТРОЛЬ: контрол / образец / позитивн / та же форм /
           известно-существующ / закрыто (RU, "закрыто" -- форма
           ответа t-297, спека называет её явно как контрольный
           маркер) ;
           control / known-present / same form / positive check (EN)

ОКНО ±3 СТРОКИ (спека, буквально): для строки с негативным маркером
контроль ищется в диапазоне [i-3, i+3] построчно (7 строк включая саму
строку негатива) -- контроль РОВНО на 3-й строке от негатива входит в
окно (WARN гасится), на 4-й -- уже НЕ входит (WARN остаётся). Оба
случая -- отдельные граничные тесты (правило 6а CLAUDE.md).

ПРЕДПРОСМОТР НАРУШЕНИЙ (спека цитирует формат буквально, но НЕ
называет число символов усечения одной строки -- собственное
инженерное решение, задокументировано, не угадано молча): каждая из
первых 3 строк-нарушителей обрезается до PREVIEW_MAX_LEN=200 символов
с многоточием "…" при усечении -- достаточно для узнавания строки
координатором, но ограничивает воздействие адверсариально огромной
одной строки на размер additionalContext (тот же принцип конечного
потолка длины сообщения, что MAX_MESSAGE_LEN в journal_echo.py/
tier_echo.py, число другое -- другой класс контента: там имя модели,
здесь произвольная строка вывода субагента).

ПРОИЗВОДИТЕЛЬНОСТЬ (спека DoD п.3: "текст 1 МБ (время < 2с)") [до
region-aware версии 2026-08-19 -- region-путь добавляет один вызов
scan() на весь find_violations(), см. "И-1" выше; заявление ниже
описывает substring-часть алгоритма, не итоговую стоимость region-
пути]: все проверки -- substring (`in`, встроенный эффективный
алгоритм CPython, без катастрофического бэктрекинга) по СТРОКАМ
текста, окно контроля -- фиксированные 7 строк на каждую негативную
строку, независимо от общей длины текста -- линейно по числу строк и
маркеров, без вложенных квантификаторов/regex вовсе для строкового
поиска маркеров.

FAIL-OPEN (спека DoD п.3, "всё fail-open (exit 0, никаких трейсбеков
наружу)"): main() -- ОДИН внешний try/except вокруг всего тела (тот же
принцип, что остальные хуки кита) -- любое непредвиденное исключение
(битый JSON, payload не dict, не-UTF8 байты, что угодно) -> тихий
exit 0. decide()/find_violations() сами по себе уже защитно
типизированы (isinstance-проверки на каждом шаге), внешний try/except
-- вторая, более грубая сетка на случай пропуска.

CLI-РЕЖИМ (спека: "`python tools/negative_lint.py --text <файл>`
линтит произвольный текстовый файл ... тот же анализ, вывод в stdout,
exit 0 всегда"): файл читается БАЙТАМИ и декодируется utf-8 с
errors="replace" (тот же fail-open принцип, что и hook-путь) -- тем же
find_violations()/format_warning(), что и hook. Молчание на чистом
тексте -- СОБСТВЕННОЕ решение (спека не оговаривает вывод на чистом
входе явно), выбрано симметрично hook-поведению ("тот же анализ" в
буквальном смысле -- тот же критерий тишины/сообщения, не только тот
же алгоритм детекта), задокументировано здесь, не угадано молча.

ASYNC-ЗАПУСК (находка обкатки №1, 07-24, рецидив 07-28): tool_response
асинхронного запуска Agent/Task-тула (`isAsync: true` / `status:
"async_launched"`) -- это МЕТАДАННЫЕ ЗАПУСКА (agentId, description,
resolvedModel, эхо промпта координатора в поле "prompt"), НЕ отчёт
воркера. У такого dict нет ни "content", ни "text"/"output"/"stdout"/
"stderr" -- _extract_text проваливается в json.dumps-фоллбек всего
payload'а и линт сканирует ПРОМПТ координатора (легитимные негативные
формулировки спеки без соседнего контроля -- ложное срабатывание).
Пропуск легален: финальный результат воркера приходит ОТДЕЛЬНЫМ
PostToolUse-событием позже и линтится штатно (тем же decide()) --
здесь просто нечего анализировать. decide() проверяет это ДО
_extract_text: tool_response -- dict и (isAsync is True ИЛИ
status == "async_launched") -> тихий (0, None). Форма без этих
маркеров (isAsync=False/отсутствует, status != "async_launched")
проходит обычным путём -- json.dumps-фоллбек остаётся живым для
прочих неопознанных dict-форм.
"""

import argparse
import bisect
import json
import os
import sys
import threading
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

# УЗЕЛ C (посадка Lead 2026-08-25, t-607): правило трёх — добавлено
# ДЕЙСТВИЕ повелительным глаголом перед провенансом; литерал реестра
# "NEGATIVE LINT: " байт-в-байт сохранён.
WARN_PREFIX_TEMPLATE = (
    "NEGATIVE LINT: {n} негативных утверждений без соседнего контроля формы: "
    "{body}. Негатив без позитивного одноформенного контроля — кандидат в "
    "reject; добавь контроль той же формы рядом с каждым утверждением или "
    "перепроверь его (гигиена п.6/D-0094)."
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
    """"NEGATIVE LINT: N негативных утверждений без соседнего контроля
    формы: <первые 3 строки-нарушителя усечённо>. Негатив без
    позитивного одноформенного контроля — кандидат в reject (гигиена
    п.6/D-0094)." -- буквальный текст спеки. Пустой violations -> ""
    (вызывающий код трактует пустую строку как тишину)."""
    if not violations:
        return ""
    n = len(violations)
    head = violations[:PREVIEW_HEAD_COUNT]
    parts = [f"line {line_no}: {_truncate(line_text)}" for line_no, line_text in head]
    body = "; ".join(parts)
    return WARN_PREFIX_TEMPLATE.format(n=n, body=body)


def _extract_text(tool_response) -> str:
    """См. докстринг модуля, "ИЗВЛЕЧЕНИЕ ТЕКСТА ИЗ tool_response" --
    строка как есть / content-список блоков / text|output|stdout|stderr
    / json.dumps фоллбек / None -> ""."""
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
    """Чистая логика, без I/O -- тестируемая напрямую (тот же стиль,
    что hygiene_gate.decide/dispatch_gate.decide). exit_code ВСЕГДА 0
    (WARN-режим). Возвращает (0, None) на тихий пропуск, (0, dict) --
    dict уже готов к json.dumps на stdout при найденных нарушениях."""
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
    """`python tools/negative_lint.py --text <файл>` -- см. докстринг
    модуля, "CLI-РЕЖИМ". Всегда возвращает 0."""
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


# --- BEGIN stdin-deadline helper (П4; ЛОКАЛЬНАЯ копия, общий модуль запрещён) ---
_STDIN_DEADLINE_DEFAULT = 10.0
_STDIN_DEADLINE_MAX = 600.0
_STDIN_DEADLINE_ENV = "OSLLM_STDIN_TIMEOUT"


def _stdin_deadline_seconds():
    """Секунды дедлайна: env-переопределение, иначе дефолт. Невалидное,
    нечисловое, <=0 и > _STDIN_DEADLINE_MAX -> дефолт; режима
    "0 = ждать вечно" НЕТ намеренно (он воскрешает саму дыру)."""
    try:
        value = float(os.environ.get(_STDIN_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDIN_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDIN_DEADLINE_MAX):
        return _STDIN_DEADLINE_DEFAULT
    return value


def _read_stdin_bytes_deadline():
    """(bytes, timed_out). Читает stdin до EOF, но не дольше дедлайна.
    Форма кроссплатформенная: select/poll на Windows не работает с
    пайпами, поэтому читает поток-демон, а дедлайн держит join(timeout).
    TTY -> b"" без чтения (прежний guard трёх файлов, теперь у всех).
    Любая ошибка чтения -> b"" (fail-open, как везде в этих хуках)."""
    stdin = getattr(sys, "stdin", None)
    if stdin is None:
        return b"", False
    try:
        if stdin.isatty():
            return b"", False
    except Exception:
        pass
    stream = getattr(stdin, "buffer", stdin)
    box = {}

    def _reader():
        try:
            box["data"] = stream.read()
        except Exception:
            box["data"] = b""

    thread = threading.Thread(target=_reader, name="stdin-deadline", daemon=True)
    thread.start()
    thread.join(_stdin_deadline_seconds())
    if thread.is_alive():
        return b"", True
    data = box.get("data") or b""
    if not isinstance(data, bytes):
        data = str(data).encode("utf-8", "replace")
    return data, False


_STDIN_DEADLINE_MSG = "stdin deadline exceeded -- fail-open, payload discarded"
# --- END stdin-deadline helper ---

# P4/В3.1 (К7-эмпирика): a background reader thread left blocked on the REAL
# stdin buffered-reader at normal interpreter shutdown crashes with "Fatal
# Python error: _enter_buffered_busy" instead of exiting cleanly. main()/
# _hook_main() are UNCHANGED (still a plain `return 0`, safe in-process);
# only the actual __main__ script-exit path below escalates to os._exit().
_STDIN_DEADLINE_STATE = {"hit": False}


def _hook_main() -> int:
    raw_bytes, timed_out = _read_stdin_bytes_deadline()
    if timed_out:
        _STDIN_DEADLINE_STATE["hit"] = True
        sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
        return 0
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
    _rc = main()
    if _STDIN_DEADLINE_STATE["hit"]:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(_rc)
    sys.exit(_rc)
