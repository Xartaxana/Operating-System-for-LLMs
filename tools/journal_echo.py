# STAGED COPY (D-0069, тот же приём, что tools/test_witness_echo.py уже
# документировал для узла N2): tools/journal_echo.py -- ЖИВОЙ hook-путь,
# НЕ ТРОНУТ этой правкой. Этот файл = живой journal_echo.py (байт в байт,
# на момент копирования) + аддитивный TS DRIFT-слой ниже (константы
# TS_FUTURE_TOLERANCE_SECONDS/TS_STALE_TOLERANCE_SECONDS, функции
# _detect_ts_drift/_collect_ts_drift_events/_format_ts_drift_line/
# build_ts_drift_segment, точки вставки в combine_context() и main()).
# Lead ретаргетит вызывающий hook на этот путь при постановке и удаляет
# staged-копию (см. tools/test_journal_echo_tsdrift.py за парный тест-файл).
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
import tier_echo  # noqa: E402  -- TIER ECHO при записи (расширение этой задачи):
# импорт iter_transcript_models/count_models (замер, с их synthetic-фильтром)
# И KNOWN_TIER_WORDS (общий словарь ярусных слов) -- спека явно называет
# оба источника ("KNOWN_TIER_WORDS tier_echo"), переиспользование ИМПОРТОМ,
# не копипаст, тот же принцип, что journal_validator выше. journal_echo.py
# и tier_echo.py -- РАЗНЫЕ хуки (PostToolUse vs SubagentStop), но эта
# задача явно санкционирует межхуковый импорт (манифест: "импортируй, не
# копируй") -- единственное исключение из общей самодостаточности хуков
# кита, наравне с journal_validator.

JOURNAL_TAIL = ("logs", "routing-log.jsonl")
GIT_TIMEOUT_SECONDS = 5
MAX_MESSAGE_LEN = 500
MAX_HEAD_MESSAGES = 3

# --- TIER ECHO при записи (расширение этой задачи) ---------------------
# Триггер: НОВАЯ строка журнала с event из TIER_TRIGGER_EVENTS И worker_ref
# ВИДА "agent:<id>" (id = [a-z0-9-]+, ЦЕЛИКОМ -- fullmatch, не префикс) --
# только тогда есть смысл искать транскрипт субагента (worker_ref вида
# cli:.../retro:... не ссылается на файл субагента вовсе -- пропуск без
# предупреждения, см. _collect_tier_events).
TIER_TRIGGER_EVENTS = {"delegated", "accepted", "rejected", "escalated"}
AGENT_WORKER_REF_RE = re.compile(r"^agent:([a-z0-9-]+)$")
# Потолок TIER ECHO-строк на один вызов хука (спека п.4) -- отдельный от
# MAX_HEAD_MESSAGES (тот -- потолок дефектов формы, 3; этот -- потолок
# tier-строк, 5, независимая ось, спека называет число явно).
MAX_TIER_LINES = 5

# --- WITNESS ECHO при записи (расширение этой задачи, узел N2 волны
# «валидационный импорт», docs/tasks/2026-07-21_validation-import.md) ---
# Перекрёстная сверка witness (поле НОВОГО accepted-события) с РЕАЛЬНО
# наблюдавшимися прогонами ТЕКУЩЕЙ сессии -- .claude/dod_track/<session_id>.json,
# пишет tools/dod_track.py (PostToolUse-хук этого же кита; здесь ТОЛЬКО
# читается локальной формулой, не импортируется -- та же самодостаточность
# хуков кита, что уже объясняет докстринг этого файла для локальных копий
# _raw_sanitize/_ascii_sanitize; journal_validator и tier_echo -- ЕДИНСТВЕННЫЕ
# заявленные исключения из этого принципа). Триггер (спека B-N2, п.1): в
# НОВЫХ строках (ТЕ ЖЕ new_lines, что main() уже вычисляет для TIER ECHO
# выше) событие event=="accepted" agent=="builder" с непустым witness.
WITNESS_TRIGGER_EVENT = "accepted"
WITNESS_TRIGGER_AGENT = "builder"
# Потолок ВИДИМЫХ WITNESS ECHO-строк на один вызов хука -- независимая ось
# от MAX_HEAD_MESSAGES (потолок дефектов формы, 3) и MAX_TIER_LINES
# (потолок tier-строк, 5) -- то же по духу СОБСТВЕННОЕ инженерное решение,
# что MAX_TIER_LINES уже задокументировал этот файл (спека числа не
# называет): выбрано ТО ЖЕ число 5 -- тот же класс "предупреждение на новую
# запись", тот же порядок величины ожидаемых accepted-строк за один
# PostToolUse-вызов. Правило 6а (CLAUDE.md): граничные тесты на 5 и 6 --
# см. tools/test_witness_echo.py.
MAX_WITNESS_LINES = 5
# Литералы тихих note (спека B-N2-2, по смыслу, буквально процитированы
# спекой с «—»; здесь дефис вместо тире -- спека п.4 требует ASCII-
# сообщения, «—» не входит в ASCII).
NOTE_RETRO = "retro accepted - track incomparable"
NOTE_TRACK_EMPTY = "track empty/unreadable - witness incomparable"


# --- TS DRIFT ECHO при записи (расширение этой задачи, слово оператора
# 2026-07-22 «делай сразу с защитой в journal_echo») ---------------------
# ДЫРА (F-29): "ts события читается с системных часов НЕПОСРЕДСТВЕННО
# перед записью, не из повествования" держится дисциплиной -- выдуманный
# или несвежий ts на МОМЕНТЕ ЗАПИСИ никто не ловит. journal_validator
# проверяет ts на COMMIT-пути (правило 10: монотонность + "не позже
# now+10мин") -- но на коммите события УЖЕ легитимно старые (batch-
# каденция D-0079: события накапливаются в памяти сессии и пишутся на
# диск одним блоком в конце стадии, коммит может случиться часы спустя)
# -- дрейф-от-текущих-часов на коммите принципиально НЕ измерим этим
# инструментом: "старый ts на коммите" -- норма, не дефект. Единственный
# момент, где "ts свежий относительно часов ПРЯМО СЕЙЧАС" осмыслен --
# МОМЕНТ ЗАПИСИ строки на диск (этот PostToolUse-хук), не момент коммита.
# Отсюда: этот чек живёт ЗДЕСЬ (journal_echo), не в journal_validator.
#
# Два независимых порога (оба -- собственное инженерное решение, спека
# числа не называет, тот же класс, что MAX_TIER_LINES/MAX_WITNESS_LINES
# выше в этом файле):
TS_FUTURE_TOLERANCE_SECONDS = 120  # 2 минуты -- запас на обычный
# процессный джиттер (часы читаются, событие сериализуется, летит через
# хук) без ложных срабатываний на честный "только что записанный" ts;
# заметно меньше 10-минутного лимита journal_validator (правило 10) --
# этот слой предупреждает РАНЬШЕ и на МЕНЬШЕМ дрейфе, чем жёсткий gate.
TS_STALE_TOLERANCE_SECONDS = 1800  # 30 минут -- запас на ЛЕГИТИМНЫЙ
# batch (D-0079): ts читается один раз "непосредственно перед записью
# БАТЧА" -- сама пачка событий может копиться в памяти сессии некоторое
# время до дисковой записи, и разница между ts самого раннего события
# батча и моментом фактической записи на диск заведомо не нулевая.
# Полчаса -- порядок величины одной рабочей стадии (см. R12 "коарс
# каденция"); дрейф БОЛЬШЕ получаса означает: ts не был взят с часов
# непосредственно перед записью (F-29), это уже подозрительно даже под
# batch-дисциплиной, а не просто "пачка чуть задержалась".

# Критик-правка (BLOCKER 1, постановочный проход t-263): потолок ВИДИМЫХ
# TS DRIFT-строк на один вызов хука -- СИММЕТРИЧНО MAX_TIER_LINES/
# MAX_WITNESS_LINES выше в этом файле (та же классовая симметрия: три
# "echo-при-записи"-расширения этого файла, три построчных детектора --
# отсутствие потолка у одного из трёх было архитектурной асимметрией без
# обоснования, а не "спека не просила" -- признано на приёмке).
# Мотивация числа (то же само собственное инженерное решение, что и у
# соседей, спека числа не называет): при head_text=None (standalone-режим
# -- git недоступен, ЛИБО это самая первая, никогда не коммиченная запись
# журнала) _get_head_text() отдаёт None -> append_ok тривиально True на
# пустом HEAD -> new_lines = ВЕСЬ файл диска целиком (см. main(): "новые
# строки" -- срез staged_lines[len(head_lines):], head_lines=[] здесь).
# Журнал в сотни строк (реальный живой routing-log.jsonl уже такого
# порядка) БЕЗ потолка означало бы: одна пропущенная git-инициализация
# -- и additionalContext раздувается на сотни TS DRIFT-строк за один
# PostToolUse-вызов -- тот же риск, что MAX_TIER_LINES/MAX_WITNESS_LINES
# уже закрывают для своих детекторов (оба тоже построчно проходят те же
# new_lines и подвержены тому же head_text=None сценарию).
MAX_TS_DRIFT_LINES = 5


def _detect_ts_drift(ts, now: "datetime.datetime"):
    """Возвращает ("future", delta_seconds) | ("stale", delta_seconds) | None
    для одного значения поля ts. Парсинг -- ПЕРЕИСПОЛЬЗОВАН
    (journal_validator.parse_ts), не продублирован: тот же ISO-без-
    таймзоны формат, что уже разбирает валидатор для правила 10 (спека
    этой задачи п.1: "формат уже разбирается существующим кодом/
    валидатором -- переиспользуй"). Непарсибельный/отсутствующий ts ->
    None -- fail-open (спека п.3): формат ts уже отдельно ловится
    journal_validator/декодом JOURNAL ECHO как дефект формы, дублировать
    эту диагностику здесь не нужно и не должно.

    now -- то же наивное локальное datetime.datetime.now(), что журнал
    ts (та же конвенция, спека п.1/CLAUDE.md "ts ISO, локальное время,
    без таймзоны") -- обе стороны сравнения naive, конфликт aware/naive
    невозможен.

    Пороги СТРОГО (>), не (>=) -- граница сама по себе тиха (спека DoD:
    "future ровно на пороге -- тихо; порог+1с -- warn", симметрично для
    stale)."""
    parsed = journal_validator.parse_ts(ts) if isinstance(ts, str) else None
    if parsed is None:
        return None
    delta = (parsed - now).total_seconds()
    if delta > TS_FUTURE_TOLERANCE_SECONDS:
        return ("future", delta)
    stale_delta = -delta
    if stale_delta > TS_STALE_TOLERANCE_SECONDS:
        return ("stale", stale_delta)
    return None


def _collect_ts_drift_events(new_lines: list, head_lines: list, now: "datetime.datetime") -> list:
    """Для КАЖДОЙ новой строки (те же new_lines/head_lines, что TIER ECHO/
    WITNESS ECHO уже используют в main()) с парсибельным полем ts --
    _detect_ts_drift. Построчно (спека п.6: "несколько строк батча с
    одним ts -- по-событийно") -- каждая строка даёт СВОЙ независимый
    результат, даже если несколько строк несут идентичный ts (не
    дедуплицируется по значению ts). Возвращает список (line_no, kind,
    delta_seconds).

    Fail-open построчно (спека п.3, тот же паттерн, что
    _collect_tier_events/_collect_witness_events): битый JSON одной
    строки -- try/except с `continue`, не роняет разбор остальных строк
    и не роняет хук."""
    events = []
    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            result = _detect_ts_drift(obj.get("ts"), now)
            if result is None:
                continue
            kind, delta = result
            events.append((line_no, kind, delta))
        except Exception:
            continue
    return events


def _format_ts_drift_line(event: tuple) -> str:
    """Спека п.2, буквально для FUTURE ("warn-строка вида"); STALE --
    тот же шаблон (спека обрывает цитату многоточием после "STALE" --
    буквальный текст после него на усмотрение реализации, см. отчёт
    билдера) -- симметричная параллель F-29/D-0079, тот же принцип
    "статический ASCII-литерал + минимум динамики", что уже применяют
    _format_tier_line/_format_witness_line в этом же файле.

    "line {N}" -- добавлено ПОВЕРХ буквальной цитаты спеки (которая сама
    не называет line N) по аналогии с TIER ECHO/WITNESS ECHO -- спека
    п.6 явно требует "по-событийно" (несколько строк одного батча с
    одинаковым ts различимы КАК СОБЫТИЯ) -- различить строки без номера
    было бы невозможно при склейке через "; " -- тот же локальный
    паттерн, что уже несёт весь остальной файл (TIER ECHO "строка N",
    WITNESS ECHO "line N").

    Динамика здесь -- ТОЛЬКО целые числа (line_no, округлённые секунды
    дрейфа), никогда не пользовательский текст -- ASCII по построению,
    без риска инъекции не-ASCII (спека п.4) -- сравнимо с этим санитайз
    не требуется (нет строкового значения стороннего JSON-поля для
    вставки, в отличие от _format_witness_line, где ts/cmd -- реальный
    текст трека)."""
    line_no, kind, delta = event
    seconds = int(round(abs(delta)))
    if kind == "future":
        return (f"TS DRIFT: line {line_no} event ts is {seconds}s in the FUTURE "
                 "(F-29: ts must be read from the system clock immediately before writing)")
    return (f"TS DRIFT: line {line_no} event ts is {seconds}s STALE "
            "(D-0079: batch ts must still be read from the system clock right "
            "before writing the batch, not carried over from an earlier check)")


def build_ts_drift_segment(ts_drift_events: list, ascii_only: bool = False) -> str:
    """Собирает TS DRIFT-часть additionalContext -- склейка через "; ",
    потолок MAX_TS_DRIFT_LINES=5 строк на вызов хука с хвостом "+K more"
    сверху (критик-правка BLOCKER 1, t-263) -- ТОТ ЖЕ паттерн, что
    build_tier_segment/build_witness_segment (см. их докстринги и
    MAX_TS_DRIFT_LINES выше за мотивацию: head_text=None делает ВЕСЬ файл
    "новым", без потолка это неограниченный additionalContext). ascii_only
    принят для единообразия сигнатуры с build_tier_segment/
    build_witness_segment/build_context, но фактически no-op:
    _format_ts_drift_line не вставляет ничего, кроме целых чисел (см. её
    докстринг) -- нет не-ASCII, которое нужно было бы санитайзить ни в
    одном режиме.

    Пустой ts_drift_events -> "" (вызывающий код трактует пустую строку
    как отсутствие сегмента, тот же принцип, что остальные build_*)."""
    if not ts_drift_events:
        return ""
    head = ts_drift_events[:MAX_TS_DRIFT_LINES]
    rest = len(ts_drift_events) - len(head)
    body = "; ".join(_format_ts_drift_line(ev) for ev in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


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


def _projects_root() -> Path:
    """C:\\Users\\<user>\\.claude\\projects -- корень поиска транскриптов
    завершившихся субагентов (спека п.1, expanduser). Отдельная функция
    (не инлайн Path.home()) -- ИСКЛЮЧИТЕЛЬНО для monkeypatch в тестах,
    тот же паттерн тестируемости, что _get_head_text/subprocess.run выше:
    подменяется модульная функция, реальный Path.home() этой машины в
    тестах не участвует."""
    return Path.home() / ".claude" / "projects"


def _find_agent_transcript(agent_id: str):
    """Глоб <projects_root>/*/*/subagents/agent-<id>.jsonl (спека п.1,
    буквально -- ДВА уровня wildcard: project-slug, session-id --
    эмпирически подтверждено на этой машине живым `find` по
    ~/.claude/projects перед реализацией: реальная структура именно
    <project-slug>/<session-id>/subagents/agent-<id>.jsonl). ПЕРВОЕ
    совпадение (id уникален по машине -- спека явно это утверждает,
    порядок глоба не важен). Не найден / любая ошибка глоба (права
    доступа, битый путь) -- None -- вызывающий код тогда молча
    пропускает строку (спека п.1: "нет замера -- нет вердикта; НЕ
    warn"), НЕ единственная предполагаемая (плоская) вложенность --
    известный сосед usage_report.py документирует ЕЩЁ более глубокий
    вариант (subagents/workflows/wf_*/agent-*.jsonl, инструмент workflow,
    не Task/Agent-диспатч) -- эта задача его не покрывает (спека даёт
    ровно плоский паттерн; см. отчёт builder'а)."""
    try:
        matches = list(_projects_root().glob(f"*/*/subagents/agent-{agent_id}.jsonl"))
    except Exception:
        return None
    return str(matches[0]) if matches else None


def _extract_declared_word(model):
    """Первое (в порядке tier_echo.KNOWN_TIER_WORDS -- haiku/sonnet/opus/
    fable) ярусное слово, встречающееся ПОДСТРОКОЙ (регистронезависимо) в
    поле model журнальной строки (спека п.2). Это НЕ то же самое, что
    tier_echo._extract_declared_tier (тот требует строгого префикса
    "слово:" в description) -- здесь источник -- свободнотекстовое поле
    model (самодекларация яруса, D-0042/D-0053: "свободная форма"), сравнение
    -- substring, тот же принцип, что и сравнение в tier_echo.build_line
    (`declared_tier in model.lower()`).

    None, если model не строка/пусто, либо НИ ОДНО известное слово не
    встречается подстрокой -- логическое продолжение fail-open принципа
    спеки п.1 ("нет замера -- нет вердикта"): без опознанного заявленного
    яруса ни MISMATCH, ни informational-ветка спеки п.2 не применимы
    (обе явно завязаны на "ярусное слово из model-поля") -- строка
    тихо пропускается, тем же способом, что "транскрипт не найден".
    Практически безопасно: 'model' -- REQUIRED-поле для всех событий
    TIER_TRIGGER_EVENTS уже в journal_validator (MODEL_REQUIRED_EVENTS) --
    его отсутствие/невалидность УЖЕ ловится отдельным дефектом формы
    независимо от этой ветки."""
    if not isinstance(model, str) or not model:
        return None
    model_lower = model.lower()
    for word in tier_echo.KNOWN_TIER_WORDS:
        if word in model_lower:
            return word
    return None


def _collect_tier_events(new_lines: list, head_lines: list) -> list:
    """Для каждой НОВОЙ строки (те же new_lines, что уже вычисляет main()
    для decide(), см. докстринг модуля/спеку п.1/п.5) с event из
    TIER_TRIGGER_EVENTS и worker_ref вида "agent:<id>" -- ищет транскрипт
    субагента, меряет модели (tier_echo.iter_transcript_models +
    count_models, их synthetic-фильтр уже встроен там), сравнивает с
    заявленным ярусным словом поля model. Возвращает список кортежей
    (line_no, kind, declared_word, counts) -- kind in ("mismatch", "info");
    "полное совпадение" (все measured несут слово) не добавляет ничего
    (спека п.2: "тишина по этой строке"). line_no -- ТА ЖЕ формула, что
    journal_validator.validate_new_lines (len(head_lines)+idx+1) -- те же
    номера строк, что дефекты формы используют в своих сообщениях.

    Fail-open построчно (спека п.4): любой сбой (битый JSON строки, глоб,
    чтение транскрипта, что угодно) -- try/except вокруг ТЕЛА одной
    итерации, `continue` -- не прерывает разбор остальных новых строк,
    не роняет хук (внешняя граница main() -- вторая, более грубая сетка)."""
    events = []
    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            event = obj.get("event")
            if event not in TIER_TRIGGER_EVENTS:
                continue
            worker_ref = obj.get("worker_ref")
            if not isinstance(worker_ref, str):
                continue
            m = AGENT_WORKER_REF_RE.match(worker_ref)
            if not m:
                continue
            agent_id = m.group(1)
            transcript_path = _find_agent_transcript(agent_id)
            if not transcript_path:
                continue
            models = list(tier_echo.iter_transcript_models(transcript_path))
            counts = tier_echo.count_models(models)
            if not counts:
                continue
            declared_word = _extract_declared_word(obj.get("model"))
            if declared_word is None:
                continue
            matched = [declared_word in mdl.lower() for mdl in counts]
            if not any(matched):
                events.append((line_no, "mismatch", declared_word, counts))
            elif not all(matched):
                events.append((line_no, "info", declared_word, counts))
            # else: все measured несут слово -- полная тишина по строке.
        except Exception:
            continue
    return events


def _format_measured(counts: dict, ascii_only: bool) -> str:
    """"<model>=<счёт>[, ...]" -- та же форма, что tier_echo.build_line,
    но санитайз выбирается по каналу (raw для stdout, ascii для stderr),
    тот же принцип, что build_context ниже."""
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    return ", ".join(f"{sanitize(model)}={count}" for model, count in counts.items())


def _format_tier_line(event: tuple, ascii_only: bool) -> str:
    """Спека п.2, буквально:
      MISMATCH: "TIER ECHO: строка N model='<заявлено>' vs measured
                 <model>=<счёт>[, ...] MISMATCH"
      informational: "TIER ECHO: строка N measured <model>=<счёт>[, ...]"
    Статические части литерала -- НЕ санитайзятся (тот же принцип, что
    build_context); санитайзу подвергается только динамика (declared_word
    -- всегда одно из 4 ascii-слов, санитайз здесь no-op, но применяется
    для единообразия; measured-модели -- реальный текст транскрипта,
    санитайз обязателен, тот же риск, что в tier_echo.build_line)."""
    line_no, kind, declared_word, counts = event
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    measured = _format_measured(counts, ascii_only)
    if kind == "mismatch":
        return f"TIER ECHO: строка {line_no} model='{sanitize(declared_word)}' vs measured {measured} MISMATCH"
    return f"TIER ECHO: строка {line_no} measured {measured}"


def build_tier_segment(tier_events: list, ascii_only: bool = False) -> str:
    """Собирает TIER ECHO-часть additionalContext из tier_events (спека
    п.4: не более MAX_TIER_LINES=5 строк на вызов, "+K more" сверху --
    тот же паттерн, что build_context для дефектов формы, независимый
    потолок). Пустой tier_events -> "" (пустая строка, не None -- вызывающий
    код проверяет её истинность так же, как список violations)."""
    if not tier_events:
        return ""
    head = tier_events[:MAX_TIER_LINES]
    rest = len(tier_events) - len(head)
    body = "; ".join(_format_tier_line(ev, ascii_only) for ev in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


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


def combine_context(violations: list, tier_events: list, witness_events: list = None,
                     ts_drift_events: list = None, ascii_only: bool = False) -> str:
    """Спека п.3: "один JSON additionalContext может нести и дефекты
    формы, и TIER ECHO-строки (раздели '; ')". ЧЕТЫРЕ НЕЗАВИСИМЫХ
    сегмента -- build_context(violations) (ЦЕЛИКОМ, свой заголовок
    "JOURNAL ECHO: N дефект(ов)..." не меняется -- существующие тесты
    завязаны на этот формат буквально), build_tier_segment(tier_events),
    (расширение N2, узел «валидационный импорт»)
    build_witness_segment(witness_events) и (расширение этой задачи, TS
    DRIFT) build_ts_drift_segment(ts_drift_events) -- склеиваются через
    "; ", только если непусты. Любое подмножество сегментов пусто ->
    итог = склейка ОСТАВШИХСЯ непустых, JSON всё равно печатается, пока
    хоть один сегмент непуст. Все пусты -> "" -- вызывающий код (main())
    трактует пустую строку как полную тишину (та же проверка истинности,
    что раньше была `if not violations`).

    witness_events=None / ts_drift_events=None (значения по умолчанию,
    НЕ [] -- сохраняет старые 2- и 3-позиционные формы вызова
    combine_context(violations, tier_events[, witness_events]) БЕЗ
    изменения поведения: сегмент для None -> build_*([]) -> "", итог
    идентичен дотиерной/довитнесовой сигнатуре -- существующие вызовы/
    тесты, завязанные на короткую форму, продолжают работать буквально
    как раньше, см. tools/test_journal_echo.py)."""
    parts = []
    if violations:
        parts.append(build_context(violations, ascii_only))
    tier_segment = build_tier_segment(tier_events, ascii_only)
    if tier_segment:
        parts.append(tier_segment)
    witness_segment = build_witness_segment(witness_events or [], ascii_only)
    if witness_segment:
        parts.append(witness_segment)
    ts_drift_segment = build_ts_drift_segment(ts_drift_events or [], ascii_only)
    if ts_drift_segment:
        parts.append(ts_drift_segment)
    return "; ".join(parts)


# ---------------------------------------------------------------------
# WITNESS ECHO при записи (расширение N2) -- pure logic
# ---------------------------------------------------------------------


def _normalize_ws(s) -> str:
    """Схлопывает ЛЮБЫЕ пробельные символы (пробел/таб/перевод строки) в
    один пробел + strip -- та же нормализация применяется И к command из
    трека, И к тексту witness ПЕРЕД substring-сравнением (спека B-N2-1:
    "команда трека (после нормализации пробелов) входит подстрокой в
    текст witness (та же нормализация)"). Не-строка -> "" (пустая строка
    -- безопасный дефолт, никогда не матчит ничего подстрокой)."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _witness_track_path(cwd, session_id) -> Path:
    """.claude/dod_track/<session_id>.json в cwd вызывающей сессии --
    ТА ЖЕ формула, что tools/dod_track.py._track_path (Path(cwd or ".") /
    ".claude" / "dod_track" / f"{session_id}.json"), ЛОКАЛЬНАЯ копия (не
    импорт dod_track -- та же самодостаточность хуков кита, что уже
    объясняет докстринг модуля для _raw_sanitize/_ascii_sanitize; спека
    N2 п.6 явно запрещает трогать dod_track.py НА ЗАПИСЬ -- воспроизвести
    формулу его хранилища для ЧТЕНИЯ не нарушает это: формат файла --
    публичный контракт между хуками этого кита, задокументированный в
    докстринге dod_track.py, данном этой задаче контекстом)."""
    return Path(cwd or ".") / ".claude" / "dod_track" / f"{session_id}.json"


def _load_witness_runs(cwd, session_id):
    """Читает runs-список трека текущей сессии. Возвращает list (может
    быть ПУСТЫМ) при успешном чтении валидного JSON-объекта с полем
    "runs"-списком; None на ЛЮБОЙ отказ -- session_id не строка/пусто,
    файла нет, файл пуст/из одних пробелов, JSON битый, JSON не dict,
    "runs" отсутствует/не список. Вызывающий код (_collect_witness_events)
    трактует И None, И ПУСТОЙ список ОДИНАКОВО -- "трек пуст/нечитаем"
    (спека п.3, последний пункт: "трек-файл отсутствует / пуст / битый
    JSON" покрывает файл целиком; пустой runs-список -- то же самое по
    факту, сравнивать witness буквально не с чем)."""
    if not isinstance(session_id, str) or not session_id:
        return None
    path = _witness_track_path(cwd, session_id)
    try:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return None
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        runs = data.get("runs")
        if not isinstance(runs, list):
            return None
        return runs
    except Exception:
        return None


def _group_runs_by_normalized_command(runs: list) -> dict:
    """{normalized_command: [(ts, outcome), ...]} по ВСЕМ прогонам трека,
    ЛЮБОГО agent_id (спека: "Поиск по ВСЕМ agent_id -- прогон
    builder-субагента лежит в том же <session_id>.json", эмпирика
    t-159) -- agent_id НЕ фильтруется вовсе. Прогоны без командной
    строки (не строка/пустая после нормализации) пропускаются -- нечего
    сравнивать. Не dict-элементы runs (битый трек) пропускаются тихо.
    Группировка по РАЗЛИЧНЫМ командам (не по каждому прогону в
    отдельности) -- производительность (см. _match_witness докстринг)."""
    groups: dict = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        norm = _normalize_ws(run.get("command"))
        if not norm:
            continue
        groups.setdefault(norm, []).append((run.get("ts"), run.get("outcome")))
    return groups


def _last_by_ts(entries: list):
    """(ts, outcome) записи с МАКСИМАЛЬНЫМ ts среди entries (entries сами
    -- список (ts, outcome)-пар, та же форма, что кладёт
    _group_runs_by_normalized_command) -- ts треков
    dod_track.py -- ISO с микросекундами фиксированной ширины
    (dod_track._now_iso), поэтому обычная строковая сортировка
    эквивалентна хронологической -- дешевле честного datetime-парсинга,
    достаточно для этой цели. Не-строковый/отсутствующий ts сортируется
    как "" -- минимальный ключ, не ломает сортировку остальных, просто
    не выиграет место "последнего" (защитный дефолт на битую запись)."""
    def key(e):
        ts = e[0]
        return ts if isinstance(ts, str) else ""
    return sorted(entries, key=key)[-1]


def _match_witness(witness: str, runs: list):
    """Спека B-N2-1/решётка B-N2-2: для КАЖДОЙ различной нормализованной
    команды трека, встречающейся подстрокой в нормализованном witness,
    берёт ПОСЛЕДНИЙ по ts прогон ЭТОЙ команды -- red -> кандидат на
    громкий WARN ("outcome -- вторичный сигнал противоречия", спека:
    determine_outcome дефолтит red на неоднозначный тихий вывод, поэтому
    сама разница red/green ещё не значит "witness лжёт", формулировка
    WARN ниже -- "recorded RED", не "is a lie"). Возвращает (matched_any:
    bool, loud: list[(cmd, ts)]). matched_any=False -> ни одна команда
    трека не найдена в witness (спека: "трек непуст, но ни одна команда
    не входит" -- мягкий WARN, см. _collect_witness_events).

    Производительность (спека DoD: "10К+ witness и трек в сотни runs --
    без квадратичного взрыва"): substring-проверок ровно столько,
    сколько РАЗЛИЧНЫХ команд в треке (после группировки), НЕ столько,
    сколько прогонов -- сотни повторов одной и той же verification-
    команды (частый случай реальных треков, см. живые .claude/dod_track/
    *.json) схлопываются в одну проверку "in", а не N."""
    norm_witness = _normalize_ws(witness)
    groups = _group_runs_by_normalized_command(runs)
    matched_any = False
    loud = []
    for cmd, entries in groups.items():
        if cmd in norm_witness:
            matched_any = True
            ts, outcome = _last_by_ts(entries)
            if outcome == "red":
                loud.append((cmd, ts))
    return matched_any, loud


def _collect_witness_events(new_lines: list, head_lines: list, payload: dict) -> list:
    """Для каждой НОВОЙ строки (ТЕ ЖЕ new_lines, что TIER ECHO использует
    выше в main()) с event=="accepted", agent=="builder" и непустым
    witness -- решётка исходов B-N2-2:

      1. notes содержит "retroactive" -> ("note", line_no, NOTE_RETRO) --
         retro-приёмка несопоставима с треком ТЕКУЩЕЙ сессии по
         определению (D-0056b), тихо, БЕЗ WARN.
      2. трек текущей сессии пуст/нечитаем (см. _load_witness_runs) ->
         ("note", line_no, NOTE_TRACK_EMPTY) -- тихо, НЕ warn, НЕ
         исключение (спека п.3, последний пункт).
      3. ни одна команда трека не входит в witness (matched_any=False) ->
         ("warn_soft", line_no) -- легитимно для батч-/кросс-сессионной/
         retro-приёмки (D-0079/D-0056b), проверь руками.
      4. совпавшая команда с ПОСЛЕДНИМ по ts red-прогоном -> ("warn_loud",
         line_no, command, ts), ПО КАЖДОЙ такой команде отдельно.
      5. иначе (совпало, последний прогон green) -> ничего не
         добавляется -- полная тишина по строке (тот же принцип, что
         TIER ECHO "все measured несут слово -- тишина").

    "note"-события НИКОГДА не печатаются (см. build_witness_segment) --
    возвращаются наравне с warn-событиями исключительно для тестируемости
    решётки (см. tools/test_witness_echo.py).

    Fail-open построчно (спека п.4, тот же паттерн, что
    _collect_tier_events): любой сбой (битый JSON строки, что угодно) --
    try/except вокруг тела ОДНОЙ итерации, `continue` -- не прерывает
    разбор остальных новых строк.

    Трек читается ЛЕНИВО и НЕ БОЛЕЕ ОДНОГО РАЗА за вызов хука (session_id
    общий для всех строк одного PostToolUse-события) -- та же "прочитан
    один раз" производительность, что докстринг модуля декларирует для
    disk_text/git в main()."""
    events = []
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    runs_loaded = False
    runs_cache = None
    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            if obj.get("event") != WITNESS_TRIGGER_EVENT:
                continue
            if obj.get("agent") != WITNESS_TRIGGER_AGENT:
                continue
            witness = obj.get("witness")
            if not isinstance(witness, str) or not witness.strip():
                continue

            notes = obj.get("notes")
            if isinstance(notes, str) and "retroactive" in notes:
                events.append(("note", line_no, NOTE_RETRO))
                continue

            if not runs_loaded:
                runs_cache = _load_witness_runs(cwd, session_id)
                runs_loaded = True
            if not runs_cache:
                events.append(("note", line_no, NOTE_TRACK_EMPTY))
                continue

            matched_any, loud = _match_witness(witness, runs_cache)
            if not matched_any:
                events.append(("warn_soft", line_no))
            else:
                for cmd, ts in loud:
                    events.append(("warn_loud", line_no, cmd, ts))
        except Exception:
            continue
    return events


def _format_witness_line(event: tuple, ascii_only: bool) -> str:
    """Статический ASCII-префикс "WITNESS ECHO: line N ..." (спека п.4:
    сообщения ASCII) + динамика (имя команды, ts) через санитайзер по
    каналу -- тот же принцип, что _format_tier_line. Формулировки --
    смысл спеки B-N2-2 (спека даёт СМЫСЛ этих двух WARN-форм, не точный
    текст -- в отличие от NOTE_RETRO/NOTE_TRACK_EMPTY, которые спека
    цитирует буквально, см. их определение выше).

    Критик-хардининг (постановочный проход): ts из трека -- ТОЖЕ
    динамика (значение поля стороннего JSON-файла, не литерал этого
    модуля), симметрично с cmd обязана проходить через тот же
    sanitize -- инвариант "санитайзится КАЖДАЯ динамика" (см. и
    _format_tier_line/_format_measured выше, где то же правило уже
    применено ко всем частям measured). На практике ts из
    dod_track._now_iso всегда чистый ASCII без control-chars (см.
    tools/test_witness_echo.py за формат-тест) -- sanitize здесь no-op
    в штатном случае, но закрывает адверсариальный край (битый/
    сторонний трек с control-chars или гигантским значением в поле ts)."""
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    kind = event[0]
    line_no = event[1]
    if kind == "warn_loud":
        _, _, cmd, ts = event
        return (f"WITNESS ECHO: line {line_no} contradiction - command "
                f"'{sanitize(cmd)}' recorded RED in session track (last red at {sanitize(str(ts))})")
    # warn_soft
    return (f"WITNESS ECHO: line {line_no} witness command(s) not observed in "
            "session track (batch/cross-session/retro acceptance legitimate - verify manually)")


def build_witness_segment(witness_events: list, ascii_only: bool = False) -> str:
    """Собирает WITNESS ECHO-часть additionalContext -- ТОЛЬКО из
    "warn_loud"/"warn_soft" событий ("note" -- тихие по определению,
    НИКОГДА не печатаются, см. _collect_witness_events); потолок
    MAX_WITNESS_LINES=5 (правило 6а -- граничные тесты на 5/6), тот же
    "+K more"-паттерн, что build_tier_segment. Пустой список видимых
    событий -> "" (вызывающий код трактует пустую строку как отсутствие
    сегмента, тот же принцип, что build_tier_segment)."""
    warn_events = [e for e in witness_events if e[0] in ("warn_loud", "warn_soft")]
    if not warn_events:
        return ""
    head = warn_events[:MAX_WITNESS_LINES]
    rest = len(warn_events) - len(head)
    body = "; ".join(_format_witness_line(e, ascii_only) for e in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


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

        # TIER ECHO при записи (расширение этой задачи, спека п.1/п.5):
        # те же "новые строки", что decide() валидирует внутри себя --
        # вычисляем НЕЗАВИСИМО через те же публичные split_lines/
        # check_append_only (decide() не отдаёт new_lines наружу).
        # append-only НЕ держится -- staged не начинается с HEAD как
        # префикс -- "новые строки" неопределимы срезом (staged может
        # содержать изменённые/удалённые старые строки вперемешку) --
        # tier-события не считаем вовсе в этом случае (new_lines = []),
        # тот же дефект (append-only) уже покрыт отдельно через violations.
        staged_lines = journal_validator.split_lines(disk_text)
        head_lines = journal_validator.split_lines(head_text)
        append_ok, _ = journal_validator.check_append_only(staged_lines, head_lines)
        new_lines = staged_lines[len(head_lines):] if append_ok else []
        tier_events = _collect_tier_events(new_lines, head_lines)

        # WITNESS ECHO при записи (расширение N2, узел «валидационный
        # импорт» -- см. докстринг _collect_witness_events выше): ТЕ ЖЕ
        # new_lines/head_lines, что TIER ECHO -- append-only-неопределимость
        # (append_ok False) уже даёт new_lines=[] выше, witness-события
        # тогда тоже пусты без отдельной проверки. Fail-open ВТОРЫМ слоем
        # поверх построчного try/except внутри _collect_witness_events
        # самой (спека п.4: "весь блок в try/except" -- ни один сбой
        # сверки не роняет хук и не ломает существующие JOURNAL ECHO/
        # TIER ECHO функции).
        try:
            witness_events = _collect_witness_events(new_lines, head_lines, payload)
        except Exception:
            witness_events = []
        # "note"-события (retro/трек-пуст) НИКОГДА не делают строку
        # видимой -- только warn_loud/warn_soft триггерят печать (спека:
        # решётка B-N2-2 -- "всё warn-only", note -- тихая по определению).
        witness_visible = any(e[0] != "note" for e in witness_events)

        # TS DRIFT ECHO при записи (расширение этой задачи, слово
        # оператора 2026-07-22): ТЕ ЖЕ new_lines/head_lines, что TIER
        # ECHO/WITNESS ECHO -- append-only-неопределимость (append_ok
        # False) уже даёт new_lines=[] выше, ts-drift-события тогда тоже
        # пусты без отдельной проверки. `now` -- ТА ЖЕ переменная, уже
        # вычисленная выше для decide()/_get_head_text (спека п.1: "now =
        # datetime.now() -- та же конвенция, что ts журнала") -- не
        # вычисляется повторно. Warn-only, ВСЕГДА видимые (нет "note"-
        # варианта, в отличие от WITNESS ECHO -- спека п.3: канал
        # предупреждения, не блок, но и не имеет легитимно-тихой ветки).
        try:
            ts_drift_events = _collect_ts_drift_events(new_lines, head_lines, now)
        except Exception:
            ts_drift_events = []

        if not violations and not tier_events and not witness_visible and not ts_drift_events:
            return 0

        # Lead-правка (критик-приёмка + Lead-смок): два разных канала,
        # два разных варианта санитайза (см. докстринг build_context).
        # combine_context склеивает дефекты формы, TIER ECHO-строки,
        # (расширение N2) WITNESS ECHO-строки и (расширение этой задачи)
        # TS DRIFT-строки (спека п.3) -- см. докстринг combine_context.
        context_for_stdout = combine_context(violations, tier_events, witness_events, ts_drift_events, ascii_only=False)
        context_for_stderr = combine_context(violations, tier_events, witness_events, ts_drift_events, ascii_only=True)

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
