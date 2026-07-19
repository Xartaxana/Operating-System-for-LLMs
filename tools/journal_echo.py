"""journal_echo.py -- PostToolUse-хук Claude Code, эхом валидирующий
СВЕЖЕЕ (только что записанное на диск) состояние logs/routing-log.jsonl
СРАЗУ после любого tool-вызова, чей tool_input несёт путь на этот файл --
ответ на находку N16 (11 дефектов в полевых журналах экзамен-клеток:
валидатор стоит только на COMMIT-пути, клетки не коммитят, встреча с
проверкой никогда не наступает). Дефект журнала теперь виден координатору
в момент записи, не только у того меньшинства сессий, что доходят до
git commit.

ПЕРЕИСПОЛЬЗОВАНИЕ -- ИМПОРТОМ, не subprocess, не копипаст логики (спека
явно требует это как альтернативу самодостаточности остальных хуков
кита, см. tools/tier_echo.py/tools/dod_track.py, оба явно НЕ импортируют
друг друга). journal_validator.decide(staged_text, head_text, now) --
ЕДИНСТВЕННАЯ вызываемая функция валидатора: она уже делает ровно то, что
просит спека (пп.2а) -- "новые строки = строки диска сверх HEAD-префикса,
валидируй ТОЛЬКО их, затравка состояния из HEAD как это делает main" --
decide() ВНУТРИ считает staged_lines/head_lines (split_lines),
check_append_only(staged, head), затем validate_new_lines(staged[len(head):],
head, now). Вызывать decide() целиком, а не растаскивать её тело руками
(split_lines/check_append_only/validate_new_lines по отдельности) --
осознанный выбор: это САМАЯ прямая форма переиспользования ("не
копипаст"), а не повторная реализация её внутренностей. Побочный эффект
(сознательно нужный, не просто терпимый): append-only-нарушения (правка
существующей строки журнала) тоже ловятся этим вызовом бесплатно -- DoD
этой задачи явно требует такую проверку в git-режиме (п.7), а decide()
её уже делает первым шагом.

СТАНДАЛОН-ФОЛБЭК (спека п.2б): "git недоступен/не репо/ошибка" --
включая случай, когда git РАБОТАЕТ, но файла на HEAD ещё нет (новый,
никогда не коммиченный журнал) -- ВСЕ эти случаи по факту сводятся к
одному: head_text = None. journal_validator.decide(disk_text, None, now)
уже ведёт себя как --standalone -- split_lines(None) даёт [], append-only
проходит вакуумно на пустом head, validate_new_lines видит КАЖДУЮ строку
диска как "новую" (см. докстринг journal_validator._run_standalone,
тот же принцип). Отдельной standalone-функции здесь заводить не нужно --
это ровно то же decide()-вызов с head_text=None, а не отдельная ветка
логики.

ТРИГГЕР (спека п.1): tool_input.file_path (метод извлечения -- буквально
как tools/dod_track.py.build_fact: `tool_input.get("file_path")`, никакой
доп. фильтрации по tool_name -- спека определяет триггер ИСКЛЮЧИТЕЛЬНО
через совпадение хвоста пути, не через список эдит-тулов; см. отчёт
builder'а за явную фиксацию этого чтения). Хвост нормализуется по ОБОИМ
видам сепараторов ('/' и '\\') и сравнивается покомпонентно с
("logs", "routing-log.jsonl") -- не substring-проверкой (иначе
"xlogs/routing-log.jsonl" или "logs/not-routing-log.jsonl" ложно
совпали бы).

КОРЕНЬ РЕПО (спека п.2): parent.parent от file_path -- каталог, что
СОДЕРЖИТ logs/, где сам journal_echo.py и его вызывающий хук находятся
безотносительно; корень НЕ обязан совпадать с cwd вызывающего процесса
(PostToolUse может исполняться из любого cwd) -- отсюда `git -C <root>`,
а не голый `git show` из текущей директории.

Git-вызов (эмпирика, не домысел): `git -C <root> show HEAD:logs/routing-log.jsonl`
подтверждён живым прогоном в этом самом репо (builder-отчёт задачи):
успех -> stdout = содержимое файла на HEAD, returncode 0; отсутствие
файла на HEAD -> returncode 128 + "fatal: path ... does not exist in
'HEAD'"; каталог не git-репозиторий -> returncode 128 + "fatal: not a
git repository"; несуществующий каталог -> returncode 128 + "fatal:
cannot change to ...". ВСЕ ошибочные формы дают returncode != 0 --
единственная развилка, нужная коду: returncode == 0 -> использовать
stdout как head_text, иначе -> head_text = None (см. "СТАНДАЛОН-ФОЛБЭК"
выше). Один subprocess-вызов, timeout=5с (спека: "~5s") -- FileNotFoundError
(бинарник git отсутствует) и subprocess.TimeoutExpired ловятся тем же
блоком, тоже дают None.

ПРОИЗВОДИТЕЛЬНОСТЬ (спека п.4): файл читается с диска ОДИН раз
(disk_text), git вызывается ОДИН раз (_get_head_text), decide() сама --
один линейный проход по новым строкам. Ни одна из этих операций не
повторяется на пути main().

ВЫВОД (спека п.3, УТОЧНЕНО Lead-правкой после критик-приёмки + Lead-смока
на живом харнессе -- ДВА РАЗНЫХ канала теперь несут ДВА РАЗНЫХ варианта
одной и той же строки, не идентичную копию): дефектов нет -> ПОЛНАЯ
тишина (ни stdout, ни stderr) -- не зашумлять каждую чистую запись.
Дефекты есть -> строка вида "JOURNAL ECHO: N дефект(ов) в новых строках:
<msg1>; <msg2>; <msg3>[; +K more]" (первые 3 сообщения валидатора
join'ятся "; ", если дефектов больше 3 -- дописывается "; +K more",
K = N-3, см. build_context()) идёт ОБОИМИ каналами, но с разной
обработкой динамики:

 - stdout: JSON {"hookSpecificOutput": {"hookEventName": "PostToolUse",
   "additionalContext": "<строка, СЫРАЯ, non-ASCII не тронут>"}} --
   канал, эмпирически подтверждённый доходящим до координатора (прогон
   №16 k6, см. докстринг tools/tier_echo.py). Lead-смок (живой харнесс,
   та же задача): additionalContext доставляется координатору UTF-8-
   безопасно уже СЕЙЧАС (живой прецедент -- tools/hygiene_gate.py шлёт
   ЭТИМ ЖЕ каналом полностью нетронутый русский текст, читаемо) --
   ASCII-replace здесь избыточен и портит читаемость сообщений
   валидатора для координатора. json.dumps(..., ensure_ascii=True) сам
   экранирует любой non-ASCII в безопасные \\uXXXX НА ПРОВОДЕ -- после
   json.loads() на стороне читателя текст восстанавливается ЧИТАЕМЫМ
   (см. _raw_sanitize -- только control-chars вырезаны и длина
   ограничена, БЕЗ ascii-replace).
 - stderr: голый текст (НЕ JSON, без \\u-эскейпинга) -- дубль,
   тот же паттерн, что tier_echo.py. Этот канал пишется НАПРЯМУЮ в
   cp1251-консольный поток этой машины -- здесь ASCII-replace
   (_ascii_sanitize) по-прежнему обязателен для динамической части, как
   было изначально (Lead: "stderr-дубль -- через _ascii_sanitize как
   сейчас").

В ОБОИХ вариантах: статический русский префикс/суффикс ("JOURNAL ECHO:
N дефект(ов) в новых строках: ", "; +K more") -- ЛИТЕРАЛ спеки п.3, НЕ
переменная -- никогда не проходит ни через один из санитайзеров (ни
_raw_sanitize, ни _ascii_sanitize не применяются к нему) -- см.
build_context(). Санитайз (в обеих формах) применяется ТОЛЬКО к
динамике -- КАЖДОМУ из вставляемых сообщений validate_new_lines()
индивидуально, ПЕРЕД join'ом -- тот же принцип, что tools/tier_echo.py.
build_line(): там санитайзится имя модели/declared_tier (динамика), а
статический английский префикс "TIER ECHO (measured): " остаётся как
есть.

ЛОКАЛЬНЫЕ КОПИИ _raw_sanitize/_ascii_sanitize (не импорт tier_echo --
каждый hook-скрипт кита самодостаточен по этому измерению, тот же
принцип дублирования, что уже применяют dod_track.py/tier_echo.py друг
к другу; единственное явное исключение из "самодостаточности" в этом
файле -- импорт journal_validator, который спека требует явно). max_len
(MAX_MESSAGE_LEN=500) применяется К КАЖДОМУ сообщению-элементу ОТДЕЛЬНО
(не к финальной строке целиком), в ОБОИХ вариантах -- больше, чем в
tier_echo (80, для короткого имени модели), т.к. одно сообщение
валидатора обычно длиннее одного имени модели, но всё ещё конечный
потолок -- адверсариальная защита от гигантского значения поля,
попавшего в текст нарушения через repr(). Собственное инженерное
решение (спека числа не называет), задокументировано.

FAIL-OPEN (спека п.1/везде): любой сбой разбора stdin-JSON, payload не
dict, file_path отсутствует/не строка/не журнальный путь, файл не
открылся с диска -- всюду тихий exit 0, ни один канал не трогается.
Один внешний try/except вокруг всего main() -- exit 0 на ЛЮБОЕ
непредвиденное исключение (тот же принцип, что во всех хуках кита)."""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal_validator  # noqa: E402  -- явный импорт по спеке, см. докстринг выше

JOURNAL_TAIL = ("logs", "routing-log.jsonl")
GIT_TIMEOUT_SECONDS = 5
MAX_MESSAGE_LEN = 500
MAX_HEAD_MESSAGES = 3


def _raw_sanitize(s: str, max_len: int = MAX_MESSAGE_LEN) -> str:
    """Lead-правка (критик-приёмка, Lead-смок): control-chars вырезаны и
    длина ограничена ТЕМ ЖЕ потолком, что _ascii_sanitize, но БЕЗ
    ascii-замены -- не-ASCII (кириллица сообщений валидатора) остаётся
    как есть. Используется для JSON additionalContext (канал
    координатору): json.dumps(ensure_ascii=True) сам экранирует
    не-ASCII в безопасные \\uXXXX на проводе, а после json.loads() на
    стороне читателя текст восстанавливается читаемым -- эмпирика
    Lead-смока: hygiene_gate.py уже шлёт нетронутую кириллицу этим же
    JSON-каналом, читаемо. ASCII-replace здесь был бы избыточной
    порчей -- он нужен только там, где текст идёт СЫРЫМ (не через
    JSON-эскейпинг) в cp1251-консольный поток, см. _ascii_sanitize."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    return s[:max_len]


def _ascii_sanitize(s: str, max_len: int = MAX_MESSAGE_LEN) -> str:
    """Локальная копия подхода tools/tier_echo.py._ascii_sanitize (тот же
    принцип: cp1251-консоль, control-chars вырезаны, non-ASCII заменены
    на '?', длина ограничена) -- копия, не импорт, см. докстринг модуля.
    Используется ТОЛЬКО для stderr-дубля (голый текст, не JSON-эскейпленный
    -- пишется напрямую в cp1251-консольный поток этой машины)."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = s.encode("ascii", "replace").decode("ascii")
    return s[:max_len]


def _extract_file_path(payload: dict):
    """tool_input.file_path -- буквально метод tools/dod_track.py.build_fact
    (`tool_input = payload.get("tool_input") or {}`; `.get("file_path")`),
    без доп. фильтра по tool_name (см. докстринг модуля, "ТРИГГЕР")."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    return file_path if isinstance(file_path, str) and file_path else None


def _is_journal_path(file_path: str) -> bool:
    """Нормализованный хвост пути == ("logs", "routing-log.jsonl"),
    покомпонентно (не substring) -- совпадает с обоими видами
    сепараторов пути ('/' и '\\')."""
    normalized = file_path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    return len(parts) >= 2 and tuple(parts[-2:]) == JOURNAL_TAIL


def _repo_root(file_path: str) -> Path:
    """Родитель родителя file_path -- каталог, содержащий logs/
    (спека п.2, буквально)."""
    return Path(file_path).resolve().parent.parent


def _get_head_text(root: Path):
    """git -C <root> show HEAD:logs/routing-log.jsonl -- ОДИН вызов,
    timeout ~5с. Возвращает stdout при returncode==0, иначе None (см.
    докстринг модуля за эмпирику всех трёх ошибочных форм -- не репо,
    файла нет на HEAD, каталог не существует -- returncode всегда
    ненулевой; FileNotFoundError/TimeoutExpired -- тот же None)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:logs/routing-log.jsonl"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def build_context(violations: list, ascii_only: bool = False) -> str:
    """"JOURNAL ECHO: N дефект(ов) в новых строках: <первые 3
    сообщения>[; +K more]" (спека п.3, буквально). Статический русский
    префикс/суффикс -- литерал спеки, НИКОГДА не проходит через
    санитайзер (ни в одном режиме -- см. докстринг модуля, "ВЫВОД").

    ascii_only=False (по умолчанию -- используется для JSON
    additionalContext, канал координатору): каждое сообщение-элемент
    прогоняется через _raw_sanitize (control-chars вырезаны, длина
    ограничена, но кириллица/не-ASCII остаётся читаемой -- Lead-правка
    после критик-приёмки: json.dumps(ensure_ascii=True) сам экранирует
    не-ASCII в проводе, координатор видит читаемый текст после
    json.loads(), ascii-replace здесь был бы избыточной порчей).

    ascii_only=True (используется ТОЛЬКО для stderr-дубля, голый текст
    не через JSON-эскейпинг, cp1251-консоль этой машины): каждое
    сообщение-элемент прогоняется через _ascii_sanitize (не-ASCII ->
    '?'), как было изначально."""
    n = len(violations)
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    head = [sanitize(v) for v in violations[:MAX_HEAD_MESSAGES]]
    rest = n - len(head)
    body = "; ".join(head)
    if rest > 0:
        body += f"; +{rest} more"
    return f"JOURNAL ECHO: {n} дефект(ов) в новых строках: {body}"


def _reconfigure_streams_utf8():
    """Статический русский текст (см. build_context) идёт ОБОИМИ
    каналами -- без явного reconfigure default-encoding stdout/stderr
    процесса на этой машине НЕ utf-8 (эмпирика этой самой правки:
    subprocess-смок падал UnicodeDecodeError на стороне читающего
    родителя -- дочерний процесс писал байты в cp1251, не utf-8).
    Тот же паттерн, что tools/hygiene_gate.py._reconfigure_stdout_utf8
    и tools/dod_track.py._reconfigure_stderr_utf8 -- здесь нужны ОБА
    канала (мы пишем в оба), копия, не импорт (см. докстринг модуля)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main() -> int:
    _reconfigure_streams_utf8()
    try:
        raw_bytes = sys.stdin.buffer.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            return 0
        if not isinstance(payload, dict):
            return 0

        file_path = _extract_file_path(payload)
        if not file_path or not _is_journal_path(file_path):
            return 0

        try:
            disk_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0

        root = _repo_root(file_path)
        now = datetime.datetime.now()
        head_text = _get_head_text(root)

        _, violations = journal_validator.decide(disk_text, head_text, now)
        if not violations:
            return 0

        # Lead-правка (критик-приёмка + Lead-смок): два разных канала,
        # два разных варианта санитайза (см. докстринг build_context).
        context_for_stdout = build_context(violations, ascii_only=False)
        context_for_stderr = build_context(violations, ascii_only=True)

        sys.stderr.write(context_for_stderr + "\n")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context_for_stdout,
            }
        }
        # ensure_ascii=True (не False, как было изначально) -- координатору
        # доставляется UTF-8-безопасный JSON: не-ASCII экранируется в
        # \uXXXX на проводе (сам json.dumps это делает), читатель
        # восстанавливает читаемый текст через json.loads(). Это делает
        # стандартный вызов безопасным даже без reconfigure-потока --
        # reconfigure оставлен как есть (защита для stderr-канала).
        sys.stdout.write(json.dumps(output, ensure_ascii=True) + "\n")
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
