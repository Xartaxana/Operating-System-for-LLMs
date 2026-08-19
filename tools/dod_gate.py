"""dod_gate.py (t-150, V3-Б) -- SubagentStop-хук Claude Code,
блокирующий сдачу воркера, если после последней правки файлов нет
зелёного проверочного прогона (детерминированный инвариант "код
фиксирует ПОРЯДОК событий, смысл СУДИТ ярус выше" -- D-0063; тот же
класс механизма, что снимок дерева tools/critic_gate.py, V3-А).
Читает трек, который пишет tools/dod_track.py (PostToolUse-хук в этом
же ките) -- см. его докстринг за полную эмпирику payload'а
PostToolUse и её ограничения; здесь -- только контракт SubagentStop.

КОНТРАКТ SubagentStop -- ЭМПИРИКА (тот же метод/источник и то же
ОГРАНИЧЕНИЕ метода, что в tools/dod_track.py: Zod-схемы, извлечённые
строковым grep'ом с позитивным/негативным контролем из установленного
бинарника Claude Code, БЕЗ живого захвата реального payload'а через
настоящий диспатч субагента -- это потребовало бы Task/Agent-тула,
что вне роли builder, D-0037):

 - Payload (схема XWb): базовые поля (session_id, transcript_path,
   cwd, prompt_id?) + hook_event_name="SubagentStop",
   stop_hook_active: bool, agent_id, agent_transcript_path,
   agent_type, last_assistant_message?, background_tasks?.
 - Блокировка остановки -- ОБЩИЙ код раннера хуков для всех типов
   command-хуков (не специфичный для Stop): "заблокировано" =
   (exit code процесса == 2) ИЛИ (JSON на stdout при exit 0 несёт
   верхнеуровневое поле "decision": "block"). Для SubagentStop ОБА
   пути реально превентят остановку (в отличие от PostToolUse, где
   exit 2 -- НЕблокирующая ошибка, тул уже выполнился). Этот хук
   использует exit 2 + текст в stderr -- тот же контракт, что уже
   реализован и (частично) проверен смоком в tools/critic_gate.py
   этого кита, ради единообразия протокола на оба хука кита, а не
   потому что JSON-decision путь хуже задокументирован.
 - stop_hook_active (эмпирика, НЕ используется этим кодом как
   условие): раннер выставляет true при ПОВТОРНОМ вызове
   Stop-хука, случившемся ПОТОМУ ЧТО предыдущий вызов уже
   заблокировал остановку -- защита от бесконечного цикла на
   уровне харнесса; официальная рекомендация -- пропускать
   (return success), пока флаг истинный. Спека t-150 задаёт СВОЙ
   предохранитель поверх этого явно ("после 2 блоков подряд в
   одной сессии — пропустить") -- реализован ниже через СОБСТВЕННЫЙ
   счётчик в трек-файле (gate_state.consecutive_blocks), НЕ через
   stop_hook_active: независимая, более консервативная защита
   (счётчик переживает весь трек сессии; про поведение
   stop_hook_active харнесса на разных турнах эмпирики не хватает,
   чтобы полагаться только на него). Оба механизма не противоречат
   друг другу -- если Lead-смок покажет, что stop_hook_active сам по
   себе достаточен и делает счётчик избыточным, это находка для
   отдельного упрощения, не блокер для этой сдачи.

Логика (main()):
 1. Прочитать трек .claude/dod_track/<session_id>.json (тот же путь,
    что пишет tools/dod_track.py). Файла нет или "edits" пуст ->
    правок не было (типичный scout/critic-класс субагент) -> пропуск,
    exit 0, gate_state не трогаем.
 2. Правки были: сравнить max(ts правок) и max(ts ЗЕЛЁНЫХ прогонов).
    Зелёных прогонов нет ИЛИ последний зелёный раньше последней
    правки -> нарушение инварианта DoD.
 3. Нарушения нет (есть зелёный прогон после последней правки) ->
    exit 0; если до этого копился счётчик consecutive_blocks -- он
    сбрасывается в 0 (успешная сдача обнуляет предохранитель).
 4. Нарушение есть: смотрим gate_state.consecutive_blocks (0 по
    умолчанию).
      - Если < 2: блокируем (exit 2 + BLOCK_MESSAGE в stderr),
        счётчик += 1.
      - Если >= 2 (это был бы ТРЕТИЙ подряд блок): защита от
        вечного блока -- НЕ блокируем (exit 0), пишем
        предупреждение в stderr (SAFETY_SKIP_MESSAGE), счётчик
        сбрасывается в 0 (новый цикл), в трек добавляется факт
        gate_log-события "skipped_after_2_blocks" (видимость для
        witness/отладки -- не требование спеки буквально, но спека
        требует, чтобы "факт остаётся в треке", это оно и есть).
    В обеих ветках пишем gate_log-событие ("blocked" |
    "skipped_after_2_blocks") -- телеметрия для юнит-тестов и
    будущего разбора, ключ "gate_log" в том же файле трека, рядом с
    "edits"/"runs"/"gate_state"; tools/dod_track.py эти ключи не
    трогает и не удаляет при своих read-modify-write (сохраняет
    неизвестные ключи как есть -- КОГДА корень парсится в dict; на
    битом/не-dict входе действует карантин + по-ключевая деградация,
    см. _load_track/_quarantine_bad_track здесь и в dod_track.py
    (посадка q503, 2026-08-19).

Отсутствие session_id/трек-файла или неразборчивый payload -- fail
open (exit 0), тот же принцип, что в critic_gate.py и dod_track.py:
хук не должен ронять чужой субагент из-за собственной ошибки
парсинга, если задача НЕ распознана как "SubagentStop с правками".

===========================================================================
STAGING_HQ ВАРИАНТ (t-159, п.7 -- АКТИВИРОВАН 2026-07-16; исходно staging-копия для
ревью и постановки Lead'ом, D-0069). Отличия ОТ КИТА, явно:
 1. Байтовое чтение stdin (та же UTF-8-правка, что t-159 п.3/
    dispatch_gate.py) -- применено единообразно ко всем staging_hq
    хукам.
 2. НОВОЕ правило evaluate(): "правки ТОЛЬКО .md/.json файлов НЕ
    требуют прогона" (спека t-159 п.7, "док-правки без кода --
    легитимная сдача") -- если ВСЕ edit-записи трека несут
    file_path (см. staging_hq/tools/dod_track.py -- поле, которого
    нет в kit-версии) с расширением .md или .json, invariant
    ПРОПУСКАЕТСЯ целиком (не требуется НИ ОДНОГО прогона вообще, не
    только "прогон после последней"). Edit-запись с НЕИЗВЕСТНЫМ
    file_path (None -- либо старый трек до этой правки, либо
    payload без поля) трактуется КОНСЕРВАТИВНО как "не doc-only" --
    отсутствие информации НЕ даёт права на исключение (эта ОДНА
    ветка -- fail-CLOSED, в отличие от остального fail-open файла:
    спутать "не знаю" с "точно только доки" опаснее лишнего блока).
    Смешанная правка (хоть один .py/другой файл среди edits) --
    исключение НЕ применяется, обычный инвариант в силе.
 3. НОВОЕ (2026-07-16, находка 4 первой живой сессии, "разделение
    поверхностей гейтов"): evaluate()/decide() принимают agent_id --
    оценка DoD-инварианта ограничена ЗАПИСЯМИ СВОЕГО воркера
    (e.get("agent_id") == agent_id), а не всем треком сессии целиком.
    ДО этой правки dod_gate.py читал ВЕСЬ трек
    .claude/dod_track/<session>.json, включая main-правки координатора
    (agent_id=null) и правки ДРУГИХ параллельных субагентов -- живой
    gate_log этой сессии зафиксировал два реальных блока чистого
    воркера за чужие непрогнанные правки (плюс срабатывание
    предохранителя consecutive_blocks) прежде чем находка была
    замечена. Зона main-правок ЦЕЛИКОМ принадлежит tools/main_gate.py
    (Stop-хук, свой main_gate_state, свой JOURNAL-варнинг) --
    dod_gate.py (SubagentStop) их больше не видит ни при каком
    agent_id. Если SubagentStop-payload не несёт agent_id вовсе
    (defensive-ветка -- параметр agent_id=None) -- консервативный
    fallback "все НЕ-main записи" (agent_id непустой, любой субагент):
    main-правки исключены в любом случае, но субагенты между собой в
    этой ветке не различаются (эмпирики о payload недостаточно для
    точного различения -- см. main()). Побочный эффект: per-agent
    фильтр заодно исключает взаимные блокировки ПАРАЛЛЕЛЬНЫХ воркеров
    одной сессии (правило 4 политики маршрутизации -- разные воркеры
    делят session_id, но не должны блокировать друг друга чужими
    непрогнанными правками).
 4. t-278 п.4 (критик t-163, "остаток" находки 4 -- docs/task_reports/
    2026-07-18_calibration2-closures.md чек 26в п.4): пункт 3 выше
    расщепил ПРОВЕРКУ инварианта per-agent, но ПРЕДОХРАНИТЕЛЬ
    consecutive_blocks ДО этой правки оставался ОДНИМ на всю сессию
    (gate_state.consecutive_blocks, плоское число) -- асимметрия между
    "что проверяем" (per-agent) и "как считаем повторные блоки"
    (session-global). Следствие (fail-open в чужую пользу): воркер X,
    исчерпавший предохранитель на СВОИХ 2 блоках, "тратил" его же на
    воркера Y, впервые встретившего блок в этой сессии -- Y мог
    проскочить 3-й блок БЕЗ единого собственного зелёного прогона.
    Счётчик теперь -- gate_state["per_agent"][<agent_key>][
    "consecutive_blocks"], независимый per agent_id (fallback-ключ
    "__none__" для defensive-ветки без agent_id, см. _agent_state_key).
    Плоское поле gate_state["consecutive_blocks"] СОХРАНЕНО в схеме
    (обратная совместимость чтения старых треков), но БОЛЬШЕ НЕ
    используется для решения -- дублирующий приход из старых записей
    просто лежит рядом, не участвуя в новой логике.
 5. t-278 п.2: gate_log-записи несут ts (_now_iso(), тот же формат,
    что tools/dod_track.py) и agent_id (сдающего воркера) -- форензик-
    находка t-265: записи без ts/agent_id неразличимы по времени/автору
    при разборе смешанного gate_log нескольких воркеров одной сессии.
    Обратная совместимость: старые gate_log-записи без этих полей
    читаются без падения (append-only, ничто в этом файле их не
    парсит обратно программно).
 6. t-278-дельта п.1 (после приёмки v1, R9 -- тот же класс бага, что
    main_gate.py п.1 очереди t-278): doc-only исключение evaluate()
    теперь применяется "целиком-или-никак" К ПРАВКАМ ЭТОГО АГЕНТА
    ПОСЛЕ ЕГО ПОСЛЕДНЕГО ЗЕЛЁНОГО (edits_after_green), а НЕ ко всей
    его отфильтрованной истории в треке -- см. main_gate.evaluate() за
    полное обоснование класса (ранняя код-правка гасила doc-only
    исключение навсегда, даже после зелёного и чисто doc-only хвоста).
    Нет зелёного вообще -- анкера "после" нет, doc-only проверяется по
    ВСЕЙ отфильтрованной истории (поведение сохранено).
===========================================================================

F-61 СИБЛИНГ (t-503, builder, 2026-08-19) -- узел A ремедиации F-61
(docs/tasks/2026-08-19_f61-f58-remediation-spec.md), решение Р3а/A7:
"dod_gate/main_gate -- ТОЛЬКО A2, внешний try НЕ ставится" (enforcement
выше косметики отказа -- гейты обязаны продолжать реально БЛОКИРОВАТЬ
(exit 2), fail-open-обёртка поверх ВСЕГО main() смазала бы это). Ровно
ОДНА правка против живого файла: _save_track() пишет трек атомарно
(mkstemp в той же папке + os.replace, суффикс .tmp последний/не .json
-- та же локальная схема, что dod_track_f61.py/critic_snapshot_f61.py,
не общий модуль -- см. owns-спека, не-цели). mkdir(parents=True,
exist_ok=True) сохранён дословно. Никаких guard'ов/total-try здесь НЕ
добавлено -- вне scope A7.

Q503 СИБЛИНГ (t-521, builder, 2026-08-19) -- узел N1 ремедиации t-503
(docs/tasks/2026-08-19_q503-remediation-spec.md), решение Р4(а)+(в):
потеря ЧУЖИХ ключей трека при битом JSON (F-61 находка 1, "ВТОРАЯ
ФОРМА"), здесь -- КОНКРЕТНО именованный живой пример "секция чужая
битая" спеки: gate_state=список -> line 282-283 (`data["gate_state"]
.setdefault(...)`) падал бы AttributeError НЕ пойманным (dod_gate.py
НЕ несёт тотального try, решение Р3а/A7 выше -- enforcement важнее
косметики отказа). Правка -- ТОЛЬКО _load_track() (+ новая
_quarantine_bad_track() рядом, ЛОКАЛЬНАЯ копия дословно как в
dod_track_q503.py -- не общий модуль, K2/не-цели); _save_track()/
_atomic_write_text()/decide()/evaluate()/весь остальной файл дословно
как в живом коде (регресс-пин; decide()'s gate_log.append() остаётся
ВНЕ этого owns -- смежная находка того же класса, см. отчёт builder'а,
НЕ фикс этим коммитом).
 K1/K2. _load_track() различает ТРИ ветки, СИММЕТРИЧНО
     dod_track_q503.py: (а) файла нет -- дословно; (б) текст не
     парсится ИЛИ парсится в не-dict корень -- КАРАНТИН
     (_quarantine_bad_track, имя НЕ ".json"), в памяти -- свежий
     дефолт с gate_state; (в) корень -- dict -- ПО-КЛЮЧЕВАЯ
     ДЕГРАДАЦИЯ: если "gate_state" присутствует, но НЕ dict -- чинится
     ТОЛЬКО оно (сброс на _default_gate_state()), ЧУЖИЕ ключи
     ("edits"/"runs"/"main_gate_state"/"gate_log"/...) остаются КАК
     ЕСТЬ, буквально Р4(в).
 K4. rc-контракты main() (0 -- пропуск/успех, 2 -- блок) не меняются;
     карантин сам проглатывает OSError (см. докстринг
     _quarantine_bad_track в dod_track_q503.py -- дословная копия
     здесь), новое исключение наружу не всплывает.
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def _now_iso() -> str:
    # t-278 п.2: тот же формат, что tools/dod_track.py._now_iso().
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")


# t-278 п.4 (критик t-163, находка 4-остаток docs/task_reports/
# 2026-07-18_calibration2-closures.md чек 26в): consecutive_blocks
# СЧИТАЕТСЯ PER-AGENT, не глобально по сессии. ДО этой правки счётчик
# был ОДИН на всю сессию (gate_state.consecutive_blocks) -- воркер X,
# исчерпавший предохранитель (2 блока), "проскакивал" 3-й блок
# session-global счётчиком, а этот же исчерпанный счётчик МОГ ложно
# сработать и для СОВЕРШЕННО ДРУГОГО воркера Y, впервые встретившего
# блок в этой же сессии (fail-open в чужую пользу -- воркер Y пропускал
# бы верификацию, которую ещё ни разу не проходил). Счётчик теперь
# живёт в gate_state["per_agent"][<agent_key>], НЕЗАВИСИМО на каждого
# агента -- та же семантика "своей зоны", что per-agent-фильтр
# evaluate() (находка 4, 2026-07-16). _FALLBACK_AGENT_KEY -- ключ для
# defensive-ветки (payload без agent_id вовсе, см. evaluate()/decide()).
_FALLBACK_AGENT_KEY = "__none__"


def _agent_state_key(agent_id) -> str:
    return agent_id if agent_id else _FALLBACK_AGENT_KEY


def _default_gate_state() -> dict:
    return {"consecutive_blocks": 0, "per_agent": {}}

BLOCK_MESSAGE = (
    "Сдача заблокирована: после последней правки нет зелёного "
    "проверочного прогона. Прогони проверку по DoD (pytest/команду "
    "прогона) и сдавай зелёным. Пересдача = финальный отчёт ЦЕЛИКОМ "
    "заново (координатору доставляется только последнее сообщение — "
    "прежний текст ему не доставлен; ссылка на него запрещена, F-49)."
)

SAFETY_SKIP_MESSAGE = (
    "dod_gate: предохранитель от вечного блока сработал -- 2 блока "
    "подряд уже были в этой сессии, сдача пропущена БЕЗ зелёного "
    "прогона (факт зафиксирован в треке, не является заменой "
    "проверки). UNSAFE COMPLETION: завершение БЕЗ зелёного прогона -- "
    "работа не считается принятой, факт всплывёт при следующем "
    "SessionStart."
)

CONSECUTIVE_BLOCK_LIMIT = 2

# STAGING_HQ п.7: расширения, которые считаются "документацией/
# конфигом без кода" -- правка ТОЛЬКО такими файлами не требует
# прогона. .jsonl добавлен Lead'ом при приёмке порта (ревью t-159):
# правка logs/routing-log.jsonl -- штатная операция КАЖДОЙ штабной
# сессии; журнал -- данные, не код, и гейтится СВОИМ pre-commit
# валидатором (tools/journal_validator.py, D-0069) -- pytest к нему
# отношения не имеет; без .jsonl main_gate ложно блокировал бы
# сессию, правившую только журнал+доки.
DOC_ONLY_EXTENSIONS = {".md", ".json", ".jsonl"}

# t-278-дельта п.2 (Rule #1: чинить -- см. main_gate.py за полное
# обоснование и выбор финального списка по факту репо): dotfiles БЕЗ
# суффикса (Path.suffix пуст для ".gitignore") раньше fail-closed'ились
# даже для заведомо бескодового конфига.
DOC_ONLY_DOTFILES = {".gitignore", ".gitattributes", ".editorconfig"}


def _is_doc_only_file(file_path) -> bool:
    if not isinstance(file_path, str) or not file_path:
        return False  # неизвестный путь -- консервативно НЕ doc-only
    path = Path(file_path)
    if path.name.lower() in DOC_ONLY_DOTFILES:
        return True
    return path.suffix.lower() in DOC_ONLY_EXTENSIONS


def _all_edits_doc_only(edits) -> bool:
    """STAGING_HQ п.7: True, если В КАЖДОЙ edit-записи file_path
    известен И doc-only (.md/.json). См. докстринг модуля за
    обоснование fail-closed трактовки неизвестного file_path."""
    if not edits:
        return False
    return all(_is_doc_only_file(e.get("file_path")) for e in edits)


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
        return {"edits": [], "runs": [], "gate_state": _default_gate_state()}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Q503 K1/Р4(а)+(в): нераспарсиваемый JSON -- КАРАНТИН, не
        # роняем хук (fail-open в памяти НЕ меняется), байты уходят
        # под карантинное имя вместо молчаливой потери.
        _quarantine_bad_track(path)
        return {"edits": [], "runs": [], "gate_state": _default_gate_state()}
    if not isinstance(data, dict):
        # Р4 "края": корень не-dict -- ТА ЖЕ ветка карантина, что
        # нераспарсиваемый (нет dict-корня -- нет ключей для
        # по-ключевой деградации).
        _quarantine_bad_track(path)
        return {"edits": [], "runs": [], "gate_state": _default_gate_state()}
    data.setdefault("edits", [])
    data.setdefault("runs", [])
    # Q503 K1/Р4(в) -- живой пример спеки: "gate_state" (СВОЯ секция
    # этого файла) может присутствовать, но НЕ быть словарём (напр.
    # список) -- ".setdefault()" на строке ниже упал бы AttributeError
    # НЕ пойманным (dod_gate.py без тотального try, Р3а/A7). По-
    # ключевая деградация: чинится ТОЛЬКО "gate_state" (сброс на
    # дефолт), ЧУЖИЕ ключи (edits/runs/main_gate_state/gate_log/...)
    # остаются КАК ЕСТЬ, ни типом не проверяются, ни трогаются.
    if not isinstance(data.get("gate_state"), dict):
        data["gate_state"] = _default_gate_state()
    # Обратная совместимость: старые треки несут только плоский
    # "consecutive_blocks" (до per-agent-правки) -- "per_agent"
    # добавляется РЯДОМ, старое поле не трогается/не удаляется.
    data["gate_state"].setdefault("consecutive_blocks", 0)
    data["gate_state"].setdefault("per_agent", {})
    return data


def _atomic_write_text(path: Path, text: str) -> None:
    """F-61 A2 (t-503): mkdir(parents=True, exist_ok=True) СОХРАНЁН
    ДОСЛОВНО (регресс-пин) -- запись идёт в mkstemp-файл В ТОЙ ЖЕ
    папке, что path, затем os.replace() поверх боевого пути. Локальная
    копия -- та же схема, что dod_track_f61.py/critic_snapshot_f61.py
    (не общий модуль, см. докстринг модуля, не-цели owns-спеки).
    Суффикс ".tmp" ПОСЛЕДНИЙ и НЕ ".json" -- session_context.py:1616
    глобит "*.json" и берёт .stem как session_id."""
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


def evaluate(track: dict, agent_id: str | None = None) -> tuple[bool, str]:
    """Чистая логика инварианта, без I/O -- тестируемая напрямую.

    agent_id задан (штатный путь SubagentStop): edits и runs
    фильтруются до записей ИМЕННО этого агента (e.get("agent_id") ==
    agent_id) ДО применения остальной логики -- правки других
    воркеров и main-правки (agent_id null/пусто) этой оценке не
    видны (находка 4 первой живой сессии, 2026-07-16 -- см. блок
    STAGING_HQ ВАРИАНТ п.3 в докстринге модуля).
    agent_id НЕ задан (None -- payload без поля, defensive-ветка):
    консервативный fallback "все НЕ-main записи" (agent_id непустой)
    -- main-правки исключаются в любом случае (их зона -- зона
    tools/main_gate.py), но субагенты между собой не различаются.

    Возвращает (violation: bool, reason: str). reason -- только для
    отладки/тестов, не парсится вызывающим кодом.

    t-278-дельта п.1 (тот же фикс, что main_gate.py п.1 очереди t-278,
    портирован на per-agent-отфильтрованное подмножество этого воркера):
    doc-only исключение применяется "целиком-или-никак" К ПРАВКАМ ПОСЛЕ
    ПОСЛЕДНЕГО ЗЕЛЁНОГО (edits_after_green этого агента), а НЕ ко всей
    его истории в треке -- см. main_gate.evaluate() за полное обоснование
    класса бага (ранняя код-правка гасила doc-only исключение навсегда,
    даже после зелёного и чисто doc-only хвоста)."""
    all_edits = track.get("edits") or []
    if agent_id:
        edits = [e for e in all_edits if e.get("agent_id") == agent_id]
    else:
        edits = [e for e in all_edits if e.get("agent_id")]
    if not edits:
        return False, "no-edits"

    all_runs = track.get("runs") or []
    if agent_id:
        runs = [r for r in all_runs if r.get("agent_id") == agent_id]
    else:
        runs = [r for r in all_runs if r.get("agent_id")]

    green_runs = [r for r in runs if r.get("outcome") == "green"]

    if not green_runs:
        if _all_edits_doc_only(edits):
            return False, "doc-only-edits-exempt"
        return True, "no-green-run"

    last_green_ts = max(r["ts"] for r in green_runs)
    edits_after_green = [e for e in edits if e["ts"] > last_green_ts]

    if not edits_after_green:
        return False, "green-after-last-edit"

    if _all_edits_doc_only(edits_after_green):
        return False, "doc-only-edits-exempt"

    return True, "green-before-last-edit"


def decide(track: dict, agent_id: str | None = None) -> tuple[int, str, dict]:
    """Чистая логика решения ПОСЛЕ загрузки трека. agent_id прокидывается
    в evaluate() без изменений (см. его докстринг за семантику фильтра)
    И используется здесь для per-agent consecutive_blocks (t-278 п.4 --
    см. докстринг _FALLBACK_AGENT_KEY выше за находку/обоснование).
    Возвращает (exit_code, stderr_message, updated_track). updated_track --
    трек с обновлённым gate_state/добавленным gate_log-событием;
    запись на диск -- забота main()."""
    violation, reason = evaluate(track, agent_id)
    gate_state = track.setdefault("gate_state", _default_gate_state())
    gate_state.setdefault("per_agent", {})
    key = _agent_state_key(agent_id)
    agent_state = gate_state["per_agent"].setdefault(key, {"consecutive_blocks": 0})
    consecutive = agent_state.get("consecutive_blocks", 0)

    if not violation:
        if consecutive:
            agent_state["consecutive_blocks"] = 0
        return 0, "", track

    # t-278 п.2: gate_log-записи несут ts (_now_iso) и agent_id -- та же
    # эмпирика/трактовка, что tools/dod_track.py._extract_agent_id
    # (None -- main-thread, но здесь SubagentStop ВСЕГДА несёт agent_id,
    # если харнесс его прислал -- см. main()/_extract_agent_id_from_payload).
    # Обратная совместимость: старые gate_log-записи без этих полей
    # читаются без падения (append-only, ничто их не парсит обратно).
    if consecutive >= CONSECUTIVE_BLOCK_LIMIT:
        agent_state["consecutive_blocks"] = 0
        # t-325 (P1, внешнее ревью, сиблинг main_gate.py -- см. его decide()
        # за полное обоснование класса) attempt 2 (критик-фикс "COLLISION"):
        # persistent-факт в САМОМ agent_state (тот же словарь, где живёт
        # "consecutive_blocks" этого агента) -- то, что читает
        # session_context.py на следующем SessionStart. agent_id включён В
        # ЗНАЧЕНИЕ (не только в ключ per_agent) -- fallback-ветка
        # (agent_id=None) кладёт записи под ключ _FALLBACK_AGENT_KEY
        # ("__none__"), сам agent_id теряется, если его не сохранить рядом
        # явно. Не затирается последующим успешным прогоном: ветка
        # "not violation" ниже трогает только "consecutive_blocks" этого
        # agent_state, этот ключ не трогает. СПИСОК ("unsafe_completions"),
        # не одиночный словарь (attempt 1 ошибочно перезаписывал единственный
        # ключ на каждом срабатывании -- второй и последующий пропуск того же
        # агента в той же сессии молча стирал факт первого): append,
        # затирание запрещено.
        agent_state.setdefault("unsafe_completions", []).append(
            {"ts": _now_iso(), "reason": reason, "agent_id": agent_id}
        )
        track.setdefault("gate_log", []).append(
            {
                "action": "skipped_after_2_blocks",
                "reason": reason,
                "ts": _now_iso(),
                "agent_id": agent_id,
            }
        )
        return 0, SAFETY_SKIP_MESSAGE, track

    agent_state["consecutive_blocks"] = consecutive + 1
    track.setdefault("gate_log", []).append(
        {"action": "blocked", "reason": reason, "ts": _now_iso(), "agent_id": agent_id}
    )
    return 2, BLOCK_MESSAGE, track


def _reconfigure_stderr_utf8():
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _extract_agent_id_from_payload(payload: dict):
    """Достаёт agent_id из payload-поля верхнего уровня "agent_id" --
    та же трактовка пустоты, что tools/dod_track.py._extract_agent_id
    и tools/main_gate.py._is_main_entry (None/пустая строка -- не
    задан). Локальная копия, не импорт из dod_track.py/main_gate.py:
    тот же паттерн дублирования, что main_gate.py уже применяет
    (_is_main_entry) -- оба файла вне owns этой задачи (main_gate.py,
    dod_track.py -- НЕ трогать)."""
    value = payload.get("agent_id")
    return value if isinstance(value, str) and value else None


def main() -> int:
    _reconfigure_stderr_utf8()

    # STAGING_HQ: байтовое stdin-чтение (t-159 п.3-стиль правка).
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    session_id = payload.get("session_id")
    if not session_id:
        return 0

    cwd = payload.get("cwd") or "."
    path = _track_path(cwd, session_id)
    existed_before = path.exists()
    track = _load_track(path)

    agent_id = _extract_agent_id_from_payload(payload)
    exit_code, message, updated_track = decide(track, agent_id)

    # "Правок не было -> пропуск" (спека): если трек-файла ещё не
    # было И правок в этом вызове нет -- по-настоящему ничего не
    # делаем, файл не создаём (scout/critic-класс субагент не должен
    # обрастать пустым .claude/dod_track/<session_id>.json). Если
    # файл уже существовал (dod_track.py его создал раньше) --
    # пишем всегда, чтобы gate_state/gate_log были согласованы.
    if existed_before or updated_track.get("edits"):
        _save_track(path, updated_track)

    if message:
        sys.stderr.write(message + "\n")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
