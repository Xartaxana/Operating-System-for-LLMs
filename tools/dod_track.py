"""dod_track.py (t-150, V3-Б) -- PostToolUse-хук Claude Code, копящий
трек правок и проверочных прогонов сессии/субагента, который читает
tools/dod_gate.py (SubagentStop-хук в этом же ките) для решения о
блокировке сдачи (D-0054/D-0052-механизация: "последняя правка РАНЬШЕ
последнего ЗЕЛЁНОГО проверочного прогона" -- детерминированный
инвариант, docs/tasks/2026-07-16_diet-b-design.md, «Кандидат v3-Б»).

===========================================================================
STAGING_HQ ВАРИАНТ (t-159, п.7 -- АКТИВИРОВАН 2026-07-16; исходно staging-копия для
ревью и постановки Lead'ом, D-0069). Отличия ОТ КИТА (exam_fullgates_kit/
tools/dod_track.py), явно, по пунктам:
 1. is_verification_command() НЕ применяет исключение "только
    самотесты гейтовой инфры" (kit-п.2а/_targets_only_gate_infra_tests
    ниже ОТСУТСТВУЕТ в этом файле совсем -- не просто выключена, а не
    перенесена). Причина: это исключение -- анти-геймификация ИМЕННО
    ЭКЗАМЕННОГО кита (билдер решает calculator/todo -- тесты гейтов
    ЗАВЕДОМО не его деливерабл, значит гонять их вместо своей задачи
    -- обход). В штабном деплое, КОГДА сессия реально РАЗРАБАТЫВАЕТ
    сами эти гейты (правка dispatch_gate.py/dod_gate.py и т.п.),
    `pytest tools/test_dispatch_gate.py` -- ЗАКОННЫЙ, единственно
    осмысленный прогон для ИМЕННО ЭТОЙ правки; кит-исключение сделало
    бы такой прогон невидимым гейту -- обратный эффект. Штабной
    канонический "python -m pytest tools/ gateway/ -q" и узкие
    таргеты (напр. "pytest tools/test_dispatch_gate.py -q") ОБА
    признаются verification-командой без исключений.
 2. build_fact() для edit-записей ДОПОЛНИТЕЛЬНО несёт "file_path"
    (из tool_input.file_path payload'а Edit/Write/MultiEdit/
    NotebookEdit) -- НОВОЕ поле, которого нет в kit-версии (там оно
    не требовалось). Нужно ТОЛЬКО штабным dod_gate.py/main_gate.py
    (staging_hq-варианты) для правила ".md/.json-only edits -- прогон
    не требуется" (см. их докстринги) -- без file_path эти гейты не
    могли бы определить расширение правленных файлов. tool_input для
    Edit/Write/MultiEdit/NotebookEdit несёт file_path ПОЛЕМ ВЕРХНЕГО
    УРОВНЯ (та же эмпирика метода, что и остальной контракт этого
    файла -- задокументированные схемы Zod в бандле для этих тулов
    единообразно называют путь именно "file_path"; отдельного живого
    смока под этот конкретный тул не делалось -- расширение по
    аналогии, не новая grep-вырезка, см. отчёт builder'а t-159).
===========================================================================

КОНТРАКТ PostToolUse -- ЭМПИРИКА, НЕ ПО ПАМЯТИ (спека t-150 требует
явно: "КОНТРАКТ payload'а PostToolUse сверь ЭМПИРИКОЙ смока, не по
памяти"). Метод и ОГРАНИЧЕНИЕ метода -- честно:
 - Источник: Zod-схемы события, извлечённые строковым grep'ом (не
   парсером/AST) из установленного бинарника Claude Code
   (`...\\npm\\node_modules\\@anthropic-ai\\claude-code\\bin\\claude.exe`).
   Контроль метода (F-30/F-34): позитивный (заведомо существующие
   имена полей схемы находятся) и негативный (заведомо
   несуществующая контрольная строка даёт 0 совпадений тем же
   grep'ом) прогнаны и подтвердили, что сам поиск работает, а не
   молчит "пусто" из-за промаха вызова.
 - НЕ выполнено: живой захват РЕАЛЬНОГО payload'а через настоящий
   PostToolUse-вызов под активным хуком (т.е. фактический перехват
   stdin в момент, когда харнесс реально шлёт событие). Это
   потребовало бы триггера через Task/Agent-тул (диспатч субагента)
   ИЛИ правки settings.json сессии, которой принадлежит этот
   процесс, -- оба пути вне роли builder на этой задаче (D-0037
   плоское делегирование запрещает первое; манифест t-150 запрещает
   второе -- owns ограничен exam_diet_policy_kit/**, штаб не
   трогать). Итог: контракт ниже -- ЛУЧШАЯ ДОСТУПНАЯ builder'у
   эмпирика (схема из бинарника, не из памяти/доков), но не
   100%-но живой захват; финальная сверка -- за Lead (см. отчёт).

Извлечённая схема (Zod, псевдоним в минифицированном бандле указан
для трассируемости, НЕ стабильный публичный API):
 - Базовые поля любого hook-события (функция n0() в бандле):
   session_id, transcript_path, cwd, prompt_id? (опц.), permission_mode?
   (опц.), agent_id? (опц. -- ИСПРАВЛЕНО t-159, см. ниже), agent_type?
   (опц.), effort? (опц., {level: str}). ПРЕЖНЯЯ версия этого докстринга
   (до t-159) перечисляла только session_id/transcript_path/cwd/
   prompt_id и ошибочно относила agent_id к SubagentStop-специфичной
   части -- находка t-159 (grep -a по тому же бинарнику, прямая
   выдержка .describe() из исходника): "agent_id:A.string().optional()
   .describe('Subagent identifier. Present only when the hook fires
   from within a subagent (e.g., a tool called by an AgentTool
   worker). Absent for the main thread, even in --agent sessions. Use
   this field (not agent_type) to distinguish subagent calls from
   main-thread calls.')" -- ЭТО ПОЛЕ БАЗОВОЕ, наследуется ЛЮБЫМ
   событием (включая PostToolUse), не только SubagentStop/SubagentStart.
   Используется build_fact() (_extract_agent_id) для различения
   main-thread/subagent записей -- см. правку t-159, очередь v5 п.1.
 - PostToolUse (схема NWb) добавляет: hook_event_name="PostToolUse",
   tool_name, tool_input, tool_response, tool_use_id, duration_ms?.
 - tool_response ДЛЯ Bash-тула конкретно (схемы Lkg/Pkg): {stdout:
   str, stderr: str, interrupted: bool, returnCodeInterpretation?:
   str, isImage?: bool, persistedOutputPath?: str,
   persistedOutputSize?: number}. Числового exit_code/rc-поля в ЭТОЙ
   схеме НЕТ (returnCodeInterpretation -- опциональная СТРОКА,
   заполняется только для "особых" ненулевых кодов, это не то же
   самое, что plain rc). Строка "exit_code" где-то в бинарнике
   действительно есть (21 совпадение строковым grep'ом), но
   строковый grep не даёт дерева разбора -- не подтверждено, что она
   принадлежит именно этой синхронной Bash-схеме (может быть полем
   другого тула/контекста, напр. фоновых команд). КОНСЕРВАТИВНОЕ
   допущение здесь: rc/exit_code СЧИТАЕТСЯ НЕДОСТУПНЫМ для Bash
   tool_response -- ветка спеки "rc==0, если rc доступен в payload"
   в этой среде практически НЕ применяется; исход определяется
   ТОЛЬКО текстовыми эвристиками по stdout+stderr (см.
   determine_outcome ниже). Функция всё же ПРОБУЕТ несколько
   правдоподобных числовых имён поля (rc/exit_code/returnCode) на
   случай, если живой смок Lead покажет иное, -- но в задокументированной
   выше схеме их нет, так что на практике эта ветка не сработает.

Хранилище: .claude/dod_track/<session_id>.json в cwd вызывающей
сессии (payload["cwd"] -- та же логика источника cwd, что в
tools/critic_gate.py, НЕ os.getcwd()). Формат файла (ПОЛЕ "agent_id"
добавлено t-159, очередь v5 п.1 -- см. build_fact/_extract_agent_id):
 {"edits": [{"ts": ISO, "tool_name": str, "agent_id": str|None}, ...],
  "runs":  [{"ts": ISO, "tool_name": str, "command": str,
             "outcome": "green"|"red", "agent_id": str|None}, ...],
  "gate_state": {...}}   -- поле "gate_state" пишет и читает
                             tools/dod_gate.py; этот файл его не
                             трогает и не удаляет, КОГДА КОРЕНЬ ФАЙЛА
                             ПАРСИТСЯ В dict (read-modify-write ниже
                             трогает ТОЛЬКО свои ключи "edits"/"runs" --
                             Q503 K1/K3, 2026-08-19, docs/tasks/
                             2026-08-19_q503-remediation-spec.md: ЭТОТ
                             АБЗАЦ ПРАВЛЕН ПРОТИВ ПРЕЖНЕЙ РЕДАКЦИИ,
                             которая заявляла сохранение БЕЗУСЛОВНО --
                             было НЕВЕРНО на двух ветках ниже, F-61
                             находка 1). На НЕРАСПАРСИВАЕМОМ тексте ИЛИ
                             не-dict корне (null/список/число/строка)
                             -- ОБЕ ветки "битого" файла -- ВСЕ ключи,
                             включая "gate_state"/"main_gate_state",
                             ТЕРЯЮТСЯ ИЗ ЖИВОГО файла (свежий
                             {"edits": [], "runs": []} замещает его
                             при следующей записи); сами БАЙТЫ при этом
                             не стираются молча -- уходят под
                             карантинное имя РЯДОМ (см.
                             _quarantine_bad_track(), имя НЕ
                             оканчивается на ".json" -- session_context.py
                             глобит "*.json" в этом же каталоге) для
                             форензики/ручного восстановления, но НЕ
                             восстанавливаются автоматически в
                             возвращаемый dict. "main_gate_state" --
                             аналогичное поле tools/main_gate.py
                             (СВОЙ, ОТДЕЛЬНЫЙ предохранитель-счётчик
                             от dod_gate.py -- один и тот же
                             session_id общий у main-хода и всех его
                             субагентов, общий счётчик дал бы ложную
                             интерференцию между Stop и SubagentStop
                             блокировками одной сессии).
   session_id ОБЩИЙ у главной сессии и ВСЕХ её субагентов (эмпирика
   t-159: конструктор события в бандле -- kf(e,void 0,i) -- всегда
   берёт session_id текущего процесса, agent_id -- отдельное поле,
   не отдельный session_id) -- значит БЕЗ "agent_id" в записи трек
   dod_track.py ДО t-159 неразличимо смешивал правки/прогоны
   main-хода и ЛЮБОГО параллельного/последовательного субагента в
   ОДНОМ файле. dod_gate.py (SubagentStop) читает ВСЕ записи, как
   раньше, -- НЕ фильтрует по agent_id (вне scope t-159, см. отчёт:
   находка-сиблинг, не фикс этим коммитом). tools/main_gate.py --
   новый читатель этого же файла t-159, фильтрует на agent_id is None
   (main-only).
ts -- локальное время без таймзоны, с системных часов в момент
обработки события хуком (F-29-конвенция), формат с микросекундами
(в отличие от logs/routing-log.jsonl) -- это внутренняя телеметрия
для dod_gate.py, не запись в маршрутизационный журнал, секундного
разрешения мало для надёжного сравнения "edit vs run" в пределах
одного инструментального хода.

ИЗВЕСТНОЕ ОГРАНИЧЕНИЕ (не решено этим коммитом, задокументировано):
при ПАРАЛЛЕЛЬНЫХ tool-вызовах в одном ходе харнесс может запускать
несколько PostToolUse-процессов почти одновременно; read-modify-write
здесь БЕЗ блокировки файла -- гонка возможна (последний write
"выигрывает", может потерять факт от параллельного вызова). Спека
t-150 такого сценария не описывает; фиксируется как то же по духу,
что self-documented ограничение critic_gate.py (state на каталог,
не на процесс) -- не решается кодом. F-61-БАТЧ (см. ниже) делает эту
гонку НЕ РАЗРУШИТЕЛЬНОЙ (уникальный tmp на каждую запись), но саму
гонку по-прежнему НЕ решает -- non-goal подтверждён буквально.

Хук НИКОГДА не блокирует (только логирует) -- exit 0 всегда, кроме
нераспознаваемого/несвязанного входа, тоже exit 0 без побочных
эффектов (fail open, тот же принцип, что critic_gate.py).

t-278 п.3: SCRATCHPAD-ИСКЛЮЧЕНИЕ. build_fact() для edit-тулов НЕ
записывает факт вовсе (возвращает None -- то же, что нерелевантный
тул), если file_path целиком лежит ВНЕ cwd (корня репо) -- буквально
"Scratchpad Directory" из системного промпта builder'а -- временный
каталог сессии ВНЕ репозитория -- всегда попадает под этот критерий.
Правки туда (временные скрипты харнесса, черновые файлы разбора)
исключены из main-edit-скоупа ЦЕЛИКОМ -- main_gate.py/dod_gate.py их
не видят ни для doc-only исключения, ни для green-инварианта, будто
их не было. Неизвестный file_path/cwd -- КОНСЕРВАТИВНО НЕ
scratchpad (fail-safe, симметрично doc-only-трактовке неизвестного
расширения в main_gate.py/dod_gate.py): отсутствие информации не даёт
права на исключение. См. _is_scratchpad_path().

СУЖЕНИЕ (критик t-278 (б), Lead-решение по батчу мелочей): раньше
здесь ДОПОЛНИТЕЛЬНО был отдельный, независимый от cwd критерий --
подстрока "scratchpad" в пути (case-insensitive). Убран: он был
избыточен к вне-cwd критерию для НАСТОЯЩЕГО харнесс-scratchpad'а (тот
и так вне cwd) и давал латентный fail-open на гипотетическом
РЕПО-файле, чьё имя просто содержит "scratchpad" (например,
tools/scratchpad_utils.py) -- такой файл раньше тихо исключался из
main-edit-скоупа, хотя лежит внутри репо. Рамка гейтинга ПО РЕПО
(per-repo), не по имени файла, принята координатором ранее; единственный
оставшийся критерий -- "путь целиком вне cwd" -- уже покрывает реальный
scratchpad-каталог харнесса без этой дыры.

===========================================================================
F-61 СИБЛИНГ (t-503, builder, 2026-08-19) -- узел A ремедиации F-61
(docs/tasks/2026-08-19_f61-f58-remediation-spec.md). Три правки поверх
всего вышеописанного, ПОИМЁННО:
 A1. ТОТАЛЬНЫЙ try в main(): весь код после _reconfigure_stderr_utf8()
     (которая остаётся ДО try) обёрнут в try/except Exception -- любое
     необработанное исключение схлопывается в ОДНУ строку stderr
     "dod_track.py: FAILED to save track (<Type>: <msg>)", return 0
     безусловен. Ничего из существующих ранних fail-open return'ов
     (битый JSON, не-dict payload, нет fact'а, нет session_id) не
     меняет поведение -- они по-прежнему тихие (без stderr), только
     ПОДЛИННО непредвиденное исключение (напр. PermissionError на
     записи трека, залоченный файл) теперь тоже exit 0, но ГРОМКО.
 A2. АТОМАРНАЯ ЗАПИСЬ: _save_track() больше не вызывает
     Path.write_text() на боевой путь напрямую -- mkdir(parents=True,
     exist_ok=True) СОХРАНЁН ДОСЛОВНО (регресс-пин), запись идёт в
     mkstemp-файл В ТОЙ ЖЕ папке, затем os.replace() поверх боевого
     пути -- см. _atomic_write_text(). Имя tmp: suffix=".tmp"
     ПОСЛЕДНИЙ и НЕ заканчивается на ".json" -- session_context.py:1616
     глобит "*.json" и берёт .stem как session_id; окончание ".json"
     заставило бы читателя принять осколок за чужой трек.
 A3. GUARD не-dict root И не-dict tool_input: build_fact() возвращает
     None молча (без исключения, без stderr) на не-dict payload и на
     не-dict tool_input -- тот же образец, что journal_echo.py:1885
     (`if not isinstance(payload, dict): return 0`). main() дублирует
     проверку payload не-dict ДО вызова build_fact() (belt-and-
     suspenders, тот же стиль, что остальной файл) -- оба уровня
     возвращают 0 тихо, не долетая до A1-обработчика (тот громкий,
     этот -- ожидаемый нераспознанный вход, тот же класс, что битый
     JSON выше).
===========================================================================

Q503 СИБЛИНГ (t-521, builder, 2026-08-19) -- узел N1 ремедиации t-503
(docs/tasks/2026-08-19_q503-remediation-spec.md), решение Р4(а)+(в):
потеря ЧУЖИХ ключей трека при битом JSON (F-61 находка 1, "ВТОРАЯ
ФОРМА"). Правка -- ТОЛЬКО _load_track() (+ новая _quarantine_bad_track()
рядом); _save_track()/_atomic_write_text()/весь остальной файл
дословно как в живом коде (регресс-пин).
 K1/K2. _load_track() различает ТРИ ветки: (а) файла нет -- дословно
     старое поведение; (б) текст НЕ парсится как JSON (вкл. 0 байт)
     ИЛИ парсится, но корень НЕ dict (null/список/число/строка) --
     ОБЕ КВАЛИФИЦИРУЮТСЯ КАК "битый" (Р4 "края": "та же ветка, что
     битый") -- КАРАНТИН: _quarantine_bad_track() переименовывает
     боевой файл на карантинное имя (НЕ ".json"), в памяти
     возвращается свежий {"edits": [], "runs": []} (fail-open в
     памяти НЕ меняется -- K4); (в) корень -- ВАЛИДНЫЙ dict -- ПО-
     КЛЮЧЕВАЯ ДЕГРАДАЦИЯ: если СВОИ ключи ("edits"/"runs") присутствуют,
     но неверного типа (не list) -- чинится ТОЛЬКО этот ключ (сброс на
     []), ЧУЖИЕ ключи (gate_state/main_gate_state/gate_log/...) НЕ
     ТРОГАЮТСЯ (ни типом не проверяются, ни значением) -- переносятся
     КАК ЕСТЬ, буквально Р4(в). Конфликтная пара 2 спеки: по-ключевая
     деградация применяется ТОЛЬКО в ветке (в) (распарсиваемый dict-
     корень) -- ветка (б) её не знает.
 K4. Fail-open БУКВАЛЬНО: rc-контракты main() не меняются -- ни одна
     из новых веток не поднимает исключение наружу (карантин сам
     проглатывает OSError, см. докстринг _quarantine_bad_track), A1
     (тотальный try) остаётся страховкой сверху на непредвиденное.
 Карантинные края: карантин уже существует под тем же префиксом --
     уникальность ОС-уровневая (mkstemp), отдельной ветки не требует;
     карантин НЕВОЗМОЖЕН (напр. каталог недоступен на запись) --
     _quarantine_bad_track проглатывает OSError молча, существующий
     fail-open (свежий словарь в памяти) остаётся ЕДИНСТВЕННЫМ
     эффектом, нового исключения наружу нет.
 Не-цели этого узла (см. owns-спека t-521): общий модуль-хелпер
     (_quarantine_bad_track -- ЛОКАЛЬНАЯ копия, дублирована в
     dod_gate_q503.py/main_gate_q503.py буквально, не импорт);
     decide()-уровневая устойчивость gate_log (см. отчёт builder'а --
     смежная находка, вне данного owns).
===========================================================================
"""

import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

EDIT_TOOL_NAMES = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# "команда матчит pytest|python -m pytest|python .*test" -- буквально
# спека t-150, три альтернативы (первая уже покрывает вторую, но обе
# оставлены ради дословного соответствия тексту спеки).
VERIFICATION_COMMAND_RE = re.compile(
    r"pytest|python\s+-m\s+pytest|python\s+.*test", re.IGNORECASE
)

# STAGING_HQ: item-2а исключение "только самотесты гейтовой инфры"
# СОЗНАТЕЛЬНО НЕ ПЕРЕНЕСЕНО из kit-версии -- см. блок STAGING_HQ
# ВАРИАНТ в докстринге модуля выше за причину (в штабном деплое
# тесты гейтов МОГУТ быть законным деливераблом сессии).

# t-159 (очередь v5 п.2б): признать НЕ-pytest witness-формы --
# node-скрипт и UI-скриншот-прогон (прецедент №10б-t1: builder гонял
# НЕСВЯЗАННЫЙ pytest как обход, потому что его РЕАЛЬНЫЙ witness --
# node-скрипт/UI-прогон -- не распознавался VERIFICATION_COMMAND_RE и
# вообще не логировался в трек; DoD-гейт видел "нет зелёного прогона"
# при факте настоящей проверки).
#
# NODE_SCRIPT_RE: команда явно запускает .js/.mjs/.cjs-файл через
# node -- буквально спека т-159 ("node-скрипт (node .*\\.js)"),
# расширено на .mjs/.cjs (те же модули Node, тот же класс witness'а,
# не отдельная спека-ветка -- самостоятельное решение, задокументировано).
NODE_SCRIPT_RE = re.compile(r"\bnode\s+\S+\.(?:m?js|cjs)\b", re.IGNORECASE)

# UI_WITNESS_RE: спека т-159 явно оставляет выбор эвристики за
# builder'ом ("эвристика по команде -- задокументируй выбранную").
# ВЫБРАННАЯ эвристика: команда упоминает инструмент автоматизации
# браузера/захвата экрана (playwright/puppeteer/selenium/screencap)
# либо явное слово screenshot/скриншот -- это наиболее вероятные
# builder-обёртки для UI-witness прогона задачи с интерактивной
# поверхностью (CLAUDE.md кита правило 11: "witness включает ВОЖДЕНИЕ
# UI -- скриншот/запись до/после"). НЕ покрывает все мыслимые CLI --
# сознательный компромисс, не попытка угадать всё.
UI_WITNESS_RE = re.compile(
    r"screenshot|playwright|puppeteer|selenium|screencap|скриншот",
    re.IGNORECASE,
)

# "есть признаки прогона (passed|ok)" / "нет признаков провала
# (failed/error/Traceback)" -- буквально спека, case-insensitive
# (Traceback в реальном выводе Python пишется с большой буквы --
# без IGNORECASE эвристика никогда бы не сработала на настоящем
# трейсбеке). ОГРАНИЧЕНИЕ (t-159, задокументировано, не решено этим
# коммитом): determine_outcome() ниже применяется К ЛЮБОЙ распознанной
# verification-команде ОДИНАКОВО, включая node/UI-witness -- те же
# текстовые эвристики success/failure. Спека т-159 п.2б просит только
# ПРИЗНАТЬ форму командой (is_verification_command), не переопределяет
# determine_outcome отдельной веткой -- расширять эвристику outcome
# под node/UI вне объявленного scope этого пункта. ПОСЛЕДСТВИЕ: чисто
# побочный UI-скрипт БЕЗ текстового подтверждения (ни "passed"/"ok",
# ни "failed"/"error"/"traceback" в stdout/stderr -- например, скрипт,
# который молча сохраняет .png и завершается) по-прежнему попадёт в
# защитный дефолт "red" (см. determine_outcome) -- чтобы стабильно
# регистрироваться "green", witness-скрипт обязан печатать явное
# текстовое подтверждение (например "OK"/"passed"). Это РЕАЛЬНОЕ
# сужение пользы признания для молчаливых скриптов -- находка для
# отчёта, не блокер: recognized-но-red лучше, чем invisible (команда
# хотя бы попадает в трек как "run", а не пропадает вовсе, как было
# до этого пункта).
#
# t-275 (находка t-262 v1): голая подстрока "failed" БЕЗ границ слова
# ложно матчила "xfailed" ("2 xfailed" -> ошибочный "red" -- честная
# xfail-сдача builder'а получала блок dod_gate; воспроизведено:
# xfail -> блок, skip -> зелёно). Фикс -- вариант "границы слова" из
# двух, предложенных спекой ("границы слова ИЛИ парсинг сводки pytest"):
# выбран как минимальный точечный фикс, не трогающий остальную логику
# determine_outcome() и не ломающий не-pytest witness-формы (node/UI,
# см. выше), для которых полноценный парсер СВОДКИ pytest (вариант 2)
# был бы бесполезен (у них нет "N passed/failed" сводки вообще -- см.
# test_node_script_outcome_uses_same_text_heuristics: "All checks
# passed" без числа). \bfailed\b НЕ матчит "failed" как часть более
# длинного слова (ни "xfailed", ни "scaffailed") -- между двумя
# буквами (word-char) нет \b-перехода. SUCCESS_INDICATORS_RE
# дополнительно распознаёт голое "xfailed" (у "xpassed" уже было
# постфактум, "оно" по совпадению матчилось на подстроку "passed" --
# см. test_build_fact_bash_verification_command matrix) -- иначе
# "N xfailed" без других слов сводки падал бы в защитный дефолт "red"
# (см. determine_outcome), а спека т-262 явно требует, чтобы честный
# xfail НЕ блокировал сдачу (тот же исход, что честный skip уже давал).
# ПОСЛЕДСТВИЕ (документировано, не решено этим коммитом): "error" и
# "traceback" ниже остаются голыми подстроками без \b -- вне
# объявленного spec-scope этого пункта (спека называет только
# "failed"); при появлении аналогичной жалобы на "error"/"traceback"
# (напр. слово, содержащее "error" как подстроку) -- тот же класс,
# отдельный фикс.
FAILURE_INDICATORS_RE = re.compile(r"\bfailed\b|error|traceback", re.IGNORECASE)
SUCCESS_INDICATORS_RE = re.compile(r"passed|\bok\b|xfailed", re.IGNORECASE)

NUMERIC_RC_FIELDS = ("rc", "exit_code", "returnCode", "return_code")

# t-278 п.3: харнесс-scratchpad -- временный каталог сессии (см. системный
# промпт builder'а: "Scratchpad Directory", путь вида
# C:\Users\...\AppData\Local\Temp\claude\<repo>\<session_id>\scratchpad\...)
# -- правки ТУДА исключаются из main-edit-скоупа целиком: не считаются
# код-правками ни для doc-only исключения, ни для green-инварианта
# (main_gate.py/dod_gate.py). Критерий -- ИСКЛЮЧИТЕЛЬНО "путь целиком
# лежит вне cwd (корня репо)" (см. _is_scratchpad_path()); реальный
# харнесс-scratchpad всегда вне cwd, так что это его полностью покрывает.
#
# СУЖЕНИЕ (критик t-278 (б), Lead-решение): раньше здесь ДОПОЛНИТЕЛЬНО
# был литеральный паттерн "scratchpad" (подстрока в пути, case-
# insensitive) как отдельный, независимый от cwd критерий. Убран:
# избыточен к вне-cwd критерию для настоящего scratchpad'а и давал
# латентный fail-open на гипотетическом РЕПО-файле, чьё имя просто
# содержит "scratchpad" (напр. tools/scratchpad_utils.py) -- такой файл
# лежит ВНУТРИ репо и не должен исключаться из main-edit-скоупа. Рамка
# per-repo гейтинга (по расположению, не по имени файла) принята
# координатором ранее.


def _is_scratchpad_path(file_path, cwd) -> bool:
    """True, если file_path -- путь целиком лежит ВНЕ корня репо (cwd) --
    буквально спека т-278 п.3 ("вне корня репо"); это и есть критерий
    харнесс-scratchpad (см. модульный комментарий выше за суженную
    границу -- подстрока "scratchpad" в имени БОЛЬШЕ НЕ триггерит
    исключение сама по себе, только расположение вне cwd). Консервативная
    трактовка (симметрично _is_doc_only_file): при НЕИЗВЕСТНОМ
    file_path/cwd -- False (НЕ исключается, инвариант в силе) --
    отсутствие информации не даёт права на исключение из main-edit-
    скоупа, тот же fail-safe принцип, что doc-only-исключение для
    неизвестного расширения."""
    if not isinstance(file_path, str) or not file_path:
        return False
    if not isinstance(cwd, str) or not cwd:
        return False
    try:
        p = Path(file_path)
        if not p.is_absolute():
            p = Path(cwd) / p
        resolved = p.resolve()
        root = Path(cwd).resolve()
    except Exception:
        return False
    try:
        return not resolved.is_relative_to(root)
    except Exception:
        return False


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")


def is_edit_tool(tool_name) -> bool:
    return tool_name in EDIT_TOOL_NAMES


def is_verification_command(command: str) -> bool:
    command = command or ""
    if VERIFICATION_COMMAND_RE.search(command):
        # STAGING_HQ: без item-2а исключения -- ЛЮБОЙ pytest/python
        # test-таргет признаётся, включая самотесты гейтовой инфры.
        return True
    # t-159 п.2б: не-pytest witness-формы.
    if NODE_SCRIPT_RE.search(command):
        return True
    if UI_WITNESS_RE.search(command):
        return True
    return False


def _extract_rc(tool_response):
    """Пробует найти числовой код возврата в tool_response. По
    задокументированной эмпирике (докстринг модуля) для Bash-тула
    такого поля НЕТ -- эта функция почти всегда вернёт None в этой
    среде; оставлена на случай иной формы payload'а (не-Bash тул,
    либо живой смок Lead покажет обратное)."""
    if not isinstance(tool_response, dict):
        return None
    for key in NUMERIC_RC_FIELDS:
        value = tool_response.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
    return None


def _extract_text(tool_response) -> str:
    """Собирает текст для текстовых эвristик. Документированная форма
    Bash tool_response -- {"stdout": str, "stderr": str, ...}: обе
    части конкатенируются. Защитный фоллбек для иной формы (напр.
    {"type": "text", "text": ...} по примеру официальной страницы
    докво -- НЕ подтверждено эмпирикой, но безопасно попробовать) --
    если ни одно из ожидаемых полей не строка, сериализуем весь
    tool_response в JSON, чтобы регекспы всё равно имели, по чему
    искать."""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, dict):
        parts = []
        for key in ("stdout", "stderr", "text", "output"):
            value = tool_response.get(key)
            if isinstance(value, str):
                parts.append(value)
        if parts:
            return "\n".join(parts)
        try:
            return json.dumps(tool_response, ensure_ascii=False)
        except Exception:
            return str(tool_response)
    return str(tool_response)


def determine_outcome(tool_response) -> str:
    """"green" | "red". Спека: успех если (нет признаков провала И
    есть признаки прогона) ЛИБО rc==0 если rc доступен. rc, когда
    доступен, РЕШАЕТ безусловно (rc==0 -> green, rc!=0 -> red) --
    иначе текстовые эвристики. Если ни признаков провала, ни
    признаков успеха нет (неоднозначный вывод, напр. "no tests
    collected") -- ЗАЩИТНЫЙ дефолт "red": спека определяет, что
    считается зелёным прогоном, не что считается провалом;
    неопознанный вывод не является подтверждённым зелёным прогоном,
    а весь смысл гейта -- не пропускать сдачу без ПОДТВЕРЖДЁННОГО
    зелёного. Это самостоятельное инженерное решение (спека явно не
    описывает эту ветку), задокументировано здесь, а не молча."""
    rc = _extract_rc(tool_response)
    if rc is not None:
        return "green" if rc == 0 else "red"

    text = _extract_text(tool_response)
    has_failure = bool(FAILURE_INDICATORS_RE.search(text))
    has_success = bool(SUCCESS_INDICATORS_RE.search(text))

    if has_failure:
        return "red"
    if has_success:
        return "green"
    return "red"


def _extract_agent_id(payload: dict):
    """t-159 (очередь v5 п.1): различает main-thread от subagent-события
    БЕЗ строкового grep'а по памяти -- ПРЯМАЯ выдержка из Zod-исходника
    базовой схемы хуков (n0(), см. докстринг модуля выше), найденная
    тем же методом (grep -a по бинарнику claude.exe), что дал схемы
    XWb/NWb: "agent_id:A.string().optional().describe('Subagent
    identifier. Present only when the hook fires from within a
    subagent (e.g., a tool called by an AgentTool worker). Absent for
    the main thread, even in --agent sessions. Use this field (not
    agent_type) to distinguish subagent calls from main-thread
    calls.')" -- дословная цитата официального .describe() из
    бандла, не домысел: agent_id ЕСТЬ в БАЗОВОЙ схеме (наследуется
    ЛЮБЫМ hook-событием через n0(), включая PostToolUse и Stop), а не
    только в SubagentStop-специфичной части, как предполагал
    докстринг этого файла до t-159 (см. правку списка базовых полей
    выше). Возвращает str (subagent) | None (main thread) -- пустая
    строка тоже трактуется как None (защита от вырожденного payload)."""
    value = payload.get("agent_id")
    return value if isinstance(value, str) and value else None


def build_fact(payload: dict):
    """Чистая логика: по payload события решает, какой факт
    зафиксировать. Возвращает ("edit", {...}) | ("run", {...}) | None
    (событие не относится к DoD-треку). Побочных эффектов нет --
    тестируется напрямую, без I/O (тот же стиль, что critic_gate.decide).

    t-159: каждая запись несёт "agent_id" (str | None) -- None значит
    main-thread (payload без agent_id -- см. _extract_agent_id).
    tools/main_gate.py (Stop-хук) фильтрует по этому полю на
    main-only записи; tools/dod_gate.py (SubagentStop-хук) читает ВСЕ
    записи как раньше -- добавление поля НЕ ломает его логику (только
    новый ключ в уже существующих dict'ах edits/runs, старые ts/
    tool_name/command/outcome не тронуты).

    F-61 A3 (t-503): GUARD не-dict root И не-dict tool_input -- return
    None молча, тот же образец, что journal_echo.py:1885 (`if not
    isinstance(payload, dict): return 0`). Проверяется ОДИН раз здесь
    (не в каждой ветке отдельно, D-0100-сосед critic_snapshot несёт
    свою копию того же guard'а в своём main() -- см. критик_snapshot_f61.py)."""
    if not isinstance(payload, dict):
        return None

    tool_name = payload.get("tool_name")
    agent_id = _extract_agent_id(payload)

    tool_input_raw = payload.get("tool_input")
    if tool_input_raw is not None and not isinstance(tool_input_raw, dict):
        return None

    if is_edit_tool(tool_name):
        tool_input = tool_input_raw or {}
        file_path = tool_input.get("file_path")
        file_path = file_path if isinstance(file_path, str) else None
        # t-278 п.3: scratchpad/вне-корня правки исключены из
        # main-edit-скоупа ЦЕЛИКОМ -- не попадают в трек вовсе (не
        # просто "не код" -- их как будто не было для doc-only и
        # green-инвариантов main_gate.py/dod_gate.py).
        if file_path is not None and _is_scratchpad_path(file_path, payload.get("cwd")):
            return None
        return "edit", {
            "ts": _now_iso(),
            "tool_name": tool_name,
            "agent_id": agent_id,
            "file_path": file_path,
        }

    # STAGING_HQ доп. 2026-07-16 (форензика первой живой сессии, класс
    # t-151 "enforcement тихо-успешен вне среды"): штабные Windows-
    # сессии гоняют команды PowerShell-тулом, kit-среда (CLI-песочницы
    # экзаменов) -- Bash-тулом. Без PowerShell здесь (и в matcher'е
    # settings.json) verification-прогоны штаба НЕВИДИМЫ треку: три
    # no-green-run блока main_gate при фактически зелёных прогонах,
    # runs=[] в живом треке. Kit-версию не трогать -- её среда Bash.
    if tool_name in ("Bash", "PowerShell"):
        tool_input = tool_input_raw or {}
        command = tool_input.get("command") or ""
        if is_verification_command(command):
            outcome = determine_outcome(payload.get("tool_response"))
            return "run", {
                "ts": _now_iso(),
                "tool_name": tool_name,
                "command": command,
                "outcome": outcome,
                "agent_id": agent_id,
            }
        return None

    return None


def _track_path(cwd: str, session_id: str) -> Path:
    return Path(cwd or ".") / ".claude" / "dod_track" / f"{session_id}.json"


_QUARANTINE_SUFFIX = ".corrupt"  # НЕ ".json" -- см. _quarantine_bad_track


def _quarantine_bad_track(path: Path) -> None:
    """Q503 N1 (t-521, 2026-08-19), Р4(а)+(в) -- карантин
    нераспарсиваемого/не-dict-корневого трек-файла: переименовывает
    БИТЫЙ файл в уникальное имя, НЕ оканчивающееся на ".json"
    (session_context.py:1649 глобит "*.json" В ЭТОМ ЖЕ каталоге и
    берёт .stem как session_id -- окончание на ".json" заставило бы
    карантинный осколок притвориться чужой session_id-записью).
    Уникальность имени -- ОС-уровневая (mkstemp, та же схема
    prefix=path.name+"."+suffix, что _atomic_write_text ниже) --
    "карантин уже существует" НЕ требует отдельной ветки: mkstemp сам
    гарантирует новое уникальное имя при каждом вызове, коллизии с
    предыдущим карантинным файлом того же исходного имени не будет.
    Сам файл здесь НЕ читается и НЕ парсится -- вызывающий код
    (_load_track) уже установил, что он битый; эта функция только
    переносит байты с боевого пути на карантинный (os.replace,
    атомарно) -- оригинальное содержимое НЕ теряется, лежит рядом под
    новым именем для форензики/ручного восстановления (НЕ
    восстанавливается автоматически в возвращаемый dict).
    Fail-open (карантин невозможен -- напр. каталог недоступен на
    запись): ЛЮБАЯ OSError здесь проглатывается молча -- существующий
    fail-open вызывающего кода (свежий дефолт в памяти) остаётся
    ЕДИНСТВЕННЫМ эффектом, новое исключение наружу не всплывает
    (буквально K4/Р4: rc-контракты хуков не меняются)."""
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=_QUARANTINE_SUFFIX
        )
        os.close(fd)
    except OSError:
        return
    try:
        os.replace(str(path), tmp_name)
    except OSError:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass


def _load_track(path: Path) -> dict:
    if not path.exists():
        return {"edits": [], "runs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Q503 K1/Р4(а)+(в): нераспарсиваемый JSON (вкл. 0 байт) --
        # КАРАНТИН (не роняем хук, fail-open в памяти НЕ меняется:
        # edits/runs теряются ИЗ ЖИВОГО файла), но байты не стираются
        # молча -- уходят под карантинное имя (_quarantine_bad_track).
        _quarantine_bad_track(path)
        return {"edits": [], "runs": []}
    if not isinstance(data, dict):
        # Р4 "края": null/список/число/строка -- корень не-dict -- ТА
        # ЖЕ ветка, что нераспарсиваемый (нет dict-корня -- нет ключей,
        # которые можно было бы выборочно починить по-ключевой
        # деградацией) -- тот же карантин.
        _quarantine_bad_track(path)
        return {"edits": [], "runs": []}
    # Корень -- валидный dict: ЧУЖИЕ ключи (gate_state/main_gate_state/
    # gate_log/...) остаются КАК ЕСТЬ (ничего из кода ниже их не
    # трогает и не проверяет типом) -- по-ключевая деградация (Р4(в))
    # применяется ТОЛЬКО к СВОИМ ключам этого файла ("edits"/"runs"):
    # если один из них присутствует, но неверного типа (не list),
    # чинится ТОЛЬКО ОН, остальной словарь не тронут.
    if not isinstance(data.get("edits"), list):
        data["edits"] = []
    if not isinstance(data.get("runs"), list):
        data["runs"] = []
    return data


def _atomic_write_text(path: Path, text: str) -> None:
    """F-61 A2 (t-503): mkdir(parents=True, exist_ok=True) СОХРАНЁН
    ДОСЛОВНО (регресс-пин) -- запись идёт в mkstemp-файл В ТОЙ ЖЕ
    папке, что path, затем os.replace() поверх боевого пути.
    Уникальность имени -- ОС-уровневая (mkstemp, схема
    prefix=path.name+"." + suffix=".tmp", решение t-470/Р4а вместо
    ручного pid+uuid). Суффикс ".tmp" ПОСЛЕДНИЙ и НЕ ".json" --
    session_context.py:1616 глобит "*.json" и берёт .stem как
    session_id; окончание на ".json" заставило бы его прочитать
    осколок как чужой трек. Запись идёт через Path.write_text() на
    tmp-путь (НЕ через os.fdopen дескриптора mkstemp) НАМЕРЕННО:
    тот же вызываемый метод, что старый (небезопасный) код применял
    напрямую к боевому пути -- дискриминирующий мок
    tools/test_f61_halfstate.py патчит именно Path.write_text и
    полагается на то, что на НЕПАТЧЕННОМ коде self -- боевой файл
    (усечение реально), а на этом атомарном коде self -- временный
    файл (усечение свежесозданного tmp безвредно, боевой путь тронут
    не будет, пока os.replace не выполнится). Если запись в tmp
    падает -- сам tmp удаляется (best-effort, не роняет исходное
    исключение) и исключение перевыбрасывается вызывающему коду
    (main()/`_write_failure_snapshot`-эквивалент решают, что делать
    дальше -- эта функция не глотает ошибки сама)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(text, encoding="utf-8")
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _save_track(path: Path, data: dict) -> None:
    _atomic_write_text(
        path, json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    )


def _reconfigure_stderr_utf8():
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stderr_utf8()

    # F-61 A1 (t-503): ТОТАЛЬНЫЙ try -- ВЕСЬ код ниже (кроме
    # _reconfigure_stderr_utf8() выше, которая остаётся ДО try) обёрнут
    # в один try/except Exception. Существующие ранние fail-open
    # return'ы (битый JSON, не-dict payload, build_fact()->None, нет
    # session_id) остаются ТИХИМИ (это распознанный, ожидаемый
    # нерелевантный вход, не ошибка) -- только НЕПРЕДВИДЕННОЕ
    # исключение (напр. PermissionError записи трека, залоченный
    # файл -- живой инцидент 2026-08-04) долетает до except ниже и
    # схлопывается в ОДНУ строку stderr, return 0 безусловен.
    try:
        # STAGING_HQ: та же байтовая stdin-правка, что t-159 п.3
        # (dispatch_gate.py) -- платформенная кодировка stdin на Windows
        # (cp1251, эмпирика в tools/dispatch_gate.py кита) искажает
        # кириллицу при sys.stdin.read(); применено ко ВСЕМ staging_hq
        # хукам единообразно, не только к тому, что спека называла явно.
        raw_bytes = sys.stdin.buffer.read()
        raw = raw_bytes.decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except Exception:
            return 0

        if not isinstance(payload, dict):
            # F-61 A3: не-dict root -- тот же образец, что
            # journal_echo.py:1885. main() дублирует build_fact()'ову
            # проверку (belt-and-suspenders) ДО вызова build_fact,
            # чтобы не полагаться на то, что build_fact всегда успеет
            # выполниться первой (следующая строка всё равно вызывает
            # build_fact(payload), которое САМО тоже проверяет -- этот
            # ранний return лишь избегает лишнего вызова).
            return 0

        fact = build_fact(payload)
        if fact is None:
            return 0

        session_id = payload.get("session_id")
        if not session_id:
            # Без session_id некуда писать трек (файл именован по
            # session_id) -- fail open, факт теряется, но хук не падает.
            return 0

        cwd = payload.get("cwd") or "."
        path = _track_path(cwd, session_id)
        data = _load_track(path)

        kind, entry = fact
        data.setdefault(kind + "s", []).append(entry)
        _save_track(path, data)
        return 0
    except Exception as exc:
        print(
            f"dod_track.py: FAILED to save track ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        return 0


if __name__ == "__main__":
    sys.exit(main())
