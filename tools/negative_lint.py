"""negative_lint.py (VG-3) -- PostToolUse-хук в WARN-РЕЖИМЕ (НИКОГДА не
блокирует) для результатов субагентов (tool_name Task/Agent), плюс
отдельный CLI-режим для линта произвольного текстового файла.

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

ПРОИЗВОДИТЕЛЬНОСТЬ (спека DoD п.3: "текст 1 МБ (время < 2с)"): все
проверки -- substring (`in`, встроенный эффективный алгоритм CPython,
без катастрофического бэктрекинга) по СТРОКАМ текста, окно контроля --
фиксированные 7 строк на каждую негативную строку, независимо от
общей длины текста -- линейно по числу строк и маркеров, без вложенных
квантификаторов/regex вовсе для строкового поиска маркеров.

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
же алгоритм детекта), задокументировано здесь, не угадано молча."""

import argparse
import json
import sys
from pathlib import Path

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


def _line_has_any_marker(line_lower: str, markers: list) -> bool:
    return any(marker in line_lower for marker in markers)


def find_violations(text: str) -> list:
    """Возвращает список (line_no 1-индексированный, original_line_text)
    для каждой строки text, несущей негативный маркер БЕЗ контрольного
    маркера в окне ±WINDOW_RADIUS строк (включая саму строку). Пустой
    text -> пустой список (тихий путь и для hook, и для CLI)."""
    if not text:
        return []
    lines = text.splitlines()
    lowered = [ln.lower() for ln in lines]
    violations = []
    for i, low in enumerate(lowered):
        if not _line_has_any_marker(low, NEG_MARKERS):
            continue
        lo = max(0, i - WINDOW_RADIUS)
        hi = min(len(lines) - 1, i + WINDOW_RADIUS)
        window_has_control = any(
            _line_has_any_marker(lowered[j], CONTROL_MARKERS)
            for j in range(lo, hi + 1)
        )
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

    text = _extract_text(payload.get("tool_response"))
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
