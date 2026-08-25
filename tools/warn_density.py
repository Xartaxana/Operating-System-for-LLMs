"""Измеритель доли срабатываний WARN-слоёв -- узел I (t-574/спека
docs/tasks/2026-08-20_nodeI-warn-density-spec.md).

Меряет СРАБАТЫВАНИЯ, а не УПОМИНАНИЯ (класс F10 калибровки №8: считались
имена слоёв, живущие в исходниках/тестах/отчётах/спеках, доли вышли
завышены на ПОРЯДОК величины). Срабатывание опознаётся СТРУКТУРНО:
запись транскрипта несёт `attachment.type == "hook_success"`, её
`attachment.stdout` (JSON-строка) декодируется `json.loads`, и в
`hookSpecificOutput.additionalContext` найден зарегистрированный литерал
слоя (tools/warn_layers.json). Разбор ТОЛЬКО через json.loads, НИКОГДА
грепом по сырому тексту -- ключ "stdout" встречается и у результатов
Bash (измерено), а имя слоя в теле сообщения/toolUseResult -- ровно тот
класс, что дал F10 (§1 спеки).

ИСТОЧНИК: транскрипты сессий JSONL этого деплоя -- верхний уровень
каталога `--transcripts` + `<session>/subagents/*.jsonl` (Р6б спеки;
`tool-results/` исключён НАМЕРЕННО -- там ВЫВОДЫ инструментов, тот же
класс, что дал F10). Знаменатель -- Z1 (вызовы tool_use, matching
матчер собственного хука слоя), а НЕ записи хука: контролируемый зонд
ЗФ-1 (отчёт диспатча t-574) показал, что молчаливый PreToolUse:Bash
хук (hygiene_gate.py на пустом `echo`) не оставляет В ТРАНСКРИПТЕ
ВООБЩЕ НИКАКОЙ attachment-записи между tool_use и tool_result -- не
только не hook_success с пустым stdout, а НИЧЕГО. Число вызовов хука
нельзя брать из записей хука (§2 гр.2 спеки).

ПРАВКА БЛОКЕРА (критик, 2026-08-20, ЗАНИЖЕНИЕ доли -- опаснее прежнего
завышения F10). Б1: Z1, собранный по ВСЕМ файлам корпуса (главные +
`subagents/`), считает и субагентские (sidechain) tool_use -- а
`hook_success` на sidechain-вызовах СТРУКТУРНО НЕ БЫВАЕТ НИ ОДНОЙ
записи (скан 441 файла корпуса критиком: 0 `hook_success` в 418
субагентских файлах). Знаменатель тогда мерил популяцию, которая
физически не может дать числитель, -- завышение x2..x8. Б2: хук на
sidechain СРАБАТЫВАЕТ (живой контроль критика: субагентский Bash
получил WARN, следующий отвергнут deny), но след не остаётся НИГДЕ --
ни `hook_success`, ни `hook_additional_context`. Это свойство НОСИТЕЛЯ
(субагентский поток структурно невидим), не дефект, который инструмент
может починить. Исправление (Ф1): Z1 и "ставка на 100 вызовов" считают
ТОЛЬКО main-файлы (`is_sidechain_file()` -- каталог `subagents/`);
sidechain-объём печатается КАЖДЫМ прогоном строкой «субагентский поток
невидим: N из M вызовов окна», а не молчит.

НАХОДКА билдера (сверх спеки, важна для raw-fallback, край 8/9):
tools/journal_echo.py печатает JSON с `ensure_ascii=True` (осознанно,
докстринг ~2207: "\\uXXXX на проводе -- сам json.dumps это делает"), а
остальные 5 носителей (dispatch_gate/owns_gate/hygiene_gate/
negative_lint/claim_control_gate/search_control_gate) -- с
`ensure_ascii=False`. Значит СЫРОЙ (нераспарсенный) stdout журнал-эха
несёт кириллицу как `\\uXXXX`-эскейпы, а не как литеральные байты;
raw-fallback (край 8, применяется ТОЛЬКО когда json.loads упал целиком)
ищет литерал в ОБЕИХ формах -- сырой и `\\uXXXX`-эскейпированной --
иначе fallback слепнет именно на слоях journal_echo при обрезанном
stdout (ЗФ-3).

Единицы счёта (§1.3): unit = (toolUseID, hookName); при отсутствии
toolUseID (SessionStart-класс) -- uuid записи; нет и его --
`fallback:<файл>:<строка>` (край 7). Кратность: `calls` -- вызовов,
помеченных слоем БИНАРНО (0/1 на unit); `lines` -- отдельных строк слоя
(str.count литерала+алиасов в найденном additionalContext). Дедуп --
глобальное множество `seen: {(unit, hookName, layer_id)}` по ВСЕМУ
корпусу (не по файлу) -- снимает дубль hook_success/
hook_additional_context на ТОМ ЖЕ ключе (unit, hookName) И дубль
родитель-транскрипт/субагент-файл при любом ответе ЗФ-2 (§3.2).

ПРАВКА БЛОКЕРА, Ф2 (Б3): `hook_additional_context` БЕЗ пары
`hook_success` по ключу (unit, hookName) -- ЕДИНСТВЕННЫЙ след
срабатывания (измерено критиком: 32 таких записи в текущем корпусе,
все несут литерал «Командная гигиена: » в поле `content` -- список
строк, НЕ вложенный JSON как у `hook_success.stdout`). Прежняя формула
«hook_additional_context игнорируется ЦЕЛИКОМ» опровергнута этим
классом: она выбрасывала 51% срабатываний слоя HYGIENE (окно №8).
Правило теперь: `hook_additional_context` игнорируется ТОЛЬКО когда
для его ключа найден `hook_success` (второй след ТОГО ЖЕ события,
§3.1 не изменился); ОСИРОТЕВШИЕ записи (без пары) считаются через тот
же дедуп-набор `seen` и печатаются отдельным счётчиком
(«осиротевших без пары hook_success: K»). Пара может физически лежать
ПОЗЖЕ той же строки в файле или в другом файле корпуса, поэтому
классификация "осиротевшая/парная" разрешается ПОСЛЕ полного прохода
по всем файлам (`hac_buffer` + `success_keys`), а не по мере чтения.

Денаминатор Z1 -- для каждого слоя: сумма вызовов tool_use (записи
type=="assistant", message.content[].type=="tool_use") с именем
инструмента, входящим в `matcher` слоя (split по "|"), в пределах
окна. `proxy=true` печатается, когда (hook_event, matcher) слоя
разделён С ДРУГИМ носителем в .claude/settings.json (несколько
хук-скриптов на одном матчере -- Z1 тогда мера трафика МАТЧЕРА, а не
исключительно этого носителя) -- вычисляется чтением settings.json
живьём, не хардкодом. Вторая колонка (Р1(г)) -- ставка на 100 вызовов
= calls / (СУММА tool_use ЛЮБОГО инструмента в окне) * 100 -- единая
база для ВСЕХ слоёв, поэтому сравнима МЕЖДУ слоями (доля -- нет, у неё
у каждого слоя свой знаменатель).

Окно: `--window-start`/`--window-end` -- ЛОКАЛЬНОЕ НАИВНОЕ время (Р7,
единая рука с журналом/calibration_prepass), полуоткрытый интервал
[start, end) -- ts РОВНО start ВХОДИТ, РОВНО end НЕ входит. Транскрипт
несёт UTC `...Z`; локальное наивное конвертируется в UTC через
`datetime.astimezone()` (Python интерпретирует наивный datetime как
системное локальное время). Отсутствие ОБОИХ границ = весь корпус без
фильтра по времени; отсутствие ОДНОЙ -- граница с этой стороны снята
(симметричная трактовка "optional" из формы §7 -- в спеке не
детализирована, интерпретация билдера). Запись без `timestamp` -- в
ЛЮБОЕ оконное измерение не входит (край 6), независимо от того, заданы
ли границы -- считается и печатается ВСЕГДА («без времени: N»).

Коды выхода: 0 -- прогон состоялся (в т.ч. при высоких долях --
измеритель, не гейт); 1 -- у --check при найденных дефектах формы
реестра, И у ОБЫЧНОГО прогона при дефекте ИНСТРУМЕНТА (Ф3-правка
блокера): 100% битых строк источника ИЛИ встроенная фикстура не
сошлась с ожиданием (`compute_run_defects()` -- «никогда голый ноль
без вердикта») ИЛИ найден ДЕФЕКТ ПРЕДИКАТА (Б-К4 ниже, calls > достижимо);
2 -- источник/аргументы не позволяют измерить вообще ничего
(--transcripts не каталог/отсутствует, --window-start/end не ISO,
start>=end, реестр не читается структурно).

УЗЕЛ B (t-589-bis, docs/tasks/2026-08-25_warn-class-fix-dag.md,
докстринг класса docs/tasks/2026-08-25_warn-population-class.md):
ПЕР-СЛОЙНЫЕ ЗНАМЕНАТЕЛИ. `layer_denominator_value()` (старое имя, ДО
этого узла) считал матчер-Z1 -- сумму tool_use ЛЮБОГО инструмента из
`matcher`, включая случаи, СТРУКТУРНО неспособные дать числитель слоя
(non-builder Task/Agent для трёх QUOTED-слоёв, любая правка не-журнала
для шести журнальных слоёв и т.д. -- полный список barrier'ов §1
класса). Реестр (registry_version 2) несёт декларативное поле
`reachable` -- ЗАКРЫТЫЙ словарь видов (`POPULATION_KINDS_ALL` ниже);
там, где барьер выражается дёшево -- `journal_path` (шесть журнальных
слоёв, барьер == `journal_echo._is_journal_path` БУКВАЛЬНО, импорт, не
копия), `subagent_type_builder` (три QUOTED-слоя, `tool_input.
subagent_type == "builder"`, dispatch_gate.py :1743/:1779/:1846),
`search_tool_or_pattern` (SEARCH_RETURNED_NOTHING, `search_control_
gate._looks_like_search` БУКВАЛЬНО, импорт); везде, где барьер --
свойство ОТВЕТА инструмента (NEGATIVE_LINT) или требует парсера гейта
(OWNS_OVERLAP/BLIND_OWNS/QUOTED_OWNS/NEGATIVE_CLAIM), либо развилка не
решена (HYGIENE) или слой не подкласса II (GIVEN_PATH/ROLE_TYPE,
подкласс I -- чинится узлом A) -- `reachable: "unmeasured"` с
обязательным `reason`. Барьеры импортируются из СОБСТВЕННЫХ модулей
гейтов (journal_echo/search_control_gate), а не копируются строкой --
единственная защита от рецидива того самого класса, который узел
чинит (константа гейта изменится -- изменится и предикат здесь, без
второй правки).

Три числа на слой (Б-К2): ДОСТИЖИМО (по declared `reachable`) /
НЕДОСТИЖИМО (= матчер - достижимо) / МАТЧЕР (старый Z1, сохранён --
Б-К5, ставка "calls/100 tool_use" остаётся на ЕДИНОЙ базе
total_tool_use_in_window, per-layer МАТЧЕР или ДОСТИЖИМО её не
заменяют). Доля (Б-К1) считается ТОЛЬКО от ДОСТИЖИМО. Слой без
declared reachable (`unmeasured`) печатает «н-д (популяция не
объявлена: <reason>)» и не печатает процент (Б-К3) -- НЕ тихий откат к
матчеру. `calls > достижимо` -- ДЕФЕКТ ПРЕДИКАТА, exit 1 (Б-К4,
`compute_run_defects()`).

Сайдкар несёт `population_rule_version` (Б-К7) -- машинно отличает
окна ДО и ПОСЛЕ этого узла (semантика ДОЛИ несравнима: `registry_sha`
УЖЕ меняется автоматически, потому что реестр правится байтово, но
явная версия -- страховка на случай совпадения sha при независимой
правке предиката). `--no-sidecar` (Р-В1) отключает и чтение, и запись
сайдкара для проверочных прогонов, не растящих `logs/warn_density.jsonl`.

CLI:
    python tools/warn_density.py [--window-start ISO] [--window-end ISO]
        [--registry-file PATH] [--transcripts DIR] [--journal PATH]
        [--sidecar PATH] [--json] [--no-sidecar]
    python tools/warn_density.py --check [--registry-file PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # безопасность вывода на Windows-консолях с не-UTF8 codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# Узел B: барьеры импортируются ИЗ ГЕЙТОВ, а не копируются строкой --
# см. докстринг модуля выше. Оба модуля лежат в tools/ рядом с этим
# файлом -- либо тем же sys.path[0], что Python выставляет при `python
# tools/warn_density.py`, либо явной вставкой sys.path в тестах
# (test_warn_density.py); оба уже импортируются как модули их
# собственными test_journal_echo.py/test_search_control_gate.py --
# import-safe (проверено чтением: ни один не исполняет код верхнего
# уровня вне `if __name__ == "__main__":`).
import journal_echo as _journal_echo_gate
import search_control_gate as _search_control_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGISTRY = REPO_ROOT / "tools" / "warn_layers.json"
DEFAULT_JOURNAL = REPO_ROOT / "logs" / "routing-log.jsonl"
DEFAULT_SIDECAR = REPO_ROOT / "logs" / "warn_density.jsonl"
DEFAULT_SETTINGS = REPO_ROOT / ".claude" / "settings.json"


def _default_transcripts_dir() -> Path:
    """Слаг каталога проекта Claude Code -- ЛЮБОЙ не-alnum символ
    абсолютного пути репо заменяется на '-' (наблюдаемая конвенция:
    'D:\\Improving_AI\\Operating-System-for-LLMs' ->
    'D--Improving-AI-Operating-System-for-LLMs', измерено чтением
    каталога .claude/projects/)."""
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(REPO_ROOT.resolve()))
    return Path.home() / ".claude" / "projects" / slug


DEFAULT_TRANSCRIPTS = _default_transcripts_dir()

FIXTURE_EXPECTED_CALLS = 2
FIXTURE_EXPECTED_LINES = 3
_FIXTURE_LAYER_ID = "GIVEN_PATH"
_FIXTURE_LITERAL = "GIVEN-PATH WARN:"

# ---------------------------------------------------------------------------
# Узел B -- пер-слойная популяция (реестр registry_version 2, поле
# `reachable`). Закрытый словарь видов -- см. докстринг модуля. Порядок
# в POPULATION_KINDS_MEASURED не значим (используется как множество
# членства); "unmeasured" -- отдельно, требует 'reason' (validate_layers).
# ---------------------------------------------------------------------------

POPULATION_KINDS_MEASURED = ("journal_path", "subagent_type_builder", "search_tool_or_pattern")
POPULATION_KINDS_ALL = POPULATION_KINDS_MEASURED + ("unmeasured",)

# Б-К7: версия ПРАВИЛА подсчёта популяции (не путать с registry_version
# самого реестра) -- пишется в КАЖДУЮ новую запись сайдкара, чтобы окна
# ДО и ПОСЛЕ этого узла были МАШИННО отличимы (а не только по памяти
# людей) -- даже если registry_sha по случайному совпадению не изменится.
POPULATION_RULE_VERSION = 1

# Наборы имён инструментов -- та же матчер-группа, что у соответствующих
# слоёв реестра (tools/warn_layers.json); ограничивают предикаты ниже,
# чтобы достижимость не считалась для инструмента, которого барьер
# структурно не касается (напр. subagent_type_builder -- только Task/Agent).
_JOURNAL_LAYER_TOOL_NAMES = {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash", "PowerShell"}
_QUOTED_LAYER_TOOL_NAMES = {"Task", "Agent"}
_SEARCH_LAYER_TOOL_NAMES = {"Bash", "PowerShell", "Grep", "Glob", "Read"}


def _population_journal_path(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Барьер шести журнальных слоёв (NOTES_LEN, TIER_ECHO, WITNESS_ECHO,
    TS_DRIFT, R6_ЗЕРКАЛО, JOURNAL_ECHO_BASE) -- журнал_эхо срабатывает
    ТОЛЬКО когда правится logs/routing-log.jsonl (journal_echo.py
    :2046-2048, :532-546, проверено чтением, B-К6). Импорт функции
    (не копия строки) -- изменится JOURNAL_TAIL/логика в journal_echo.py,
    изменится и этот предикат без второй правки."""
    if tool_name not in _JOURNAL_LAYER_TOOL_NAMES:
        return False
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return False
    return _journal_echo_gate._is_journal_path(file_path)


def _population_subagent_type_builder(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Барьер трёх QUOTED-слоёв (WRITE_QUOTED, DOD_QUOTED, MANIFEST_QUOTED)
    -- ранний возврот "" при tool_input.subagent_type != "builder"
    (dispatch_gate.py :1743, :1779, :1846, все три идентичны, проверено
    чтением, B-К6)."""
    if tool_name not in _QUOTED_LAYER_TOOL_NAMES:
        return False
    return tool_input.get("subagent_type") == "builder"


def _population_search_tool_or_pattern(tool_name: str, tool_input: Dict[str, Any]) -> bool:
    """Барьер SEARCH_RETURNED_NOTHING -- Grep/Glob всегда, Bash/PowerShell
    только при поисковом виде команды (search_control_gate.py :190,
    :271-277, :561-568, проверено чтением, B-К6). НАХОДКА билдера при
    первом прогоне (B-К6 в деле): `_looks_like_search(tool_name,
    command_text)` САМА не гейтит command_text по tool_name -- строка
    "grep foo" в `command_text` дала бы True даже для tool_name="Read",
    если вызвать её напрямую с сырым `tool_input.get("command")`. Реальный
    барьер -- ДВЕ функции вместе: `_command_text_for_classification`
    (:251-268) отдаёт command_text ТОЛЬКО для Bash/PowerShell, None для
    всех прочих (в т.ч. Read) -- она гейтит ИМЕННО этот случай. Импорт
    ОБЕИХ функций гейта (не одной) -- иначе предикат здесь был бы
    ошибочно ШИРЕ настоящего барьера, ровно рецидив чинимого класса,
    только наоборот (переоценка, не недооценка)."""
    if tool_name not in _SEARCH_LAYER_TOOL_NAMES:
        return False
    command_text = _search_control_gate._command_text_for_classification(tool_name, tool_input)
    return _search_control_gate._looks_like_search(tool_name, command_text)


POPULATION_PREDICATES = {
    "journal_path": _population_journal_path,
    "subagent_type_builder": _population_subagent_type_builder,
    "search_tool_or_pattern": _population_search_tool_or_pattern,
}


class SourceError(Exception):
    """--transcripts не каталог / не существует -- exit 2."""


class RegistryError(Exception):
    """Реестр не читается СТРУКТУРНО (не JSON / не тот верхний уровень)
    -- exit 2, измерить нечего вообще."""


class ArgError(Exception):
    """Некорректные аргументы (ISO, start>=end) -- exit 2 без трейсбека."""


# ---------------------------------------------------------------------------
# Реестр
# ---------------------------------------------------------------------------

@dataclass
class LayerDef:
    id: str
    name: str
    carrier: List[str]
    symbol: Optional[str]
    literal: str
    aliases: List[str]
    hook_event: str
    matcher: str
    denominator: str
    listed_in_check_11v: bool
    index: int = 0
    reachable: str = "unmeasured"
    reachable_reason: Optional[str] = None

    def all_strings(self) -> List[str]:
        return [self.literal] + list(self.aliases)


def read_registry_raw(path: Path) -> Tuple[int, List[Dict[str, Any]], bytes]:
    if not path.exists():
        raise RegistryError(f"реестр не найден: {path}")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RegistryError(f"реестр не в UTF-8: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RegistryError(f"реестр не JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RegistryError("реестр: верхний уровень должен быть JSON-объектом")
    layers = data.get("layers")
    if not isinstance(layers, list):
        raise RegistryError("реестр: поле 'layers' отсутствует или не список")
    for i, item in enumerate(layers):
        if not isinstance(item, dict):
            raise RegistryError(f"реестр: layers[{i}] не JSON-объект")
    return data.get("registry_version", 0), layers, raw


REQUIRED_LAYER_FIELDS = [
    "id", "name", "carrier", "literal", "aliases", "hook_event",
    "matcher", "denominator", "listed_in_check_11v",
]


def validate_layers(raw_layers: List[Dict[str, Any]]) -> Tuple[List[LayerDef], List[str]]:
    """Возвращает (валидные_слои, дефекты_формы). Дефект ОДНОЙ записи не
    рвёт прогон (D-0043 "не трейсбек") -- запись исключается, остальные
    измеряются."""
    defects: List[str] = []
    valid: List[LayerDef] = []
    seen_ids: Dict[str, int] = {}
    for item in raw_layers:
        idv = item.get("id")
        if isinstance(idv, str):
            seen_ids[idv] = seen_ids.get(idv, 0) + 1
    dup_reported: set = set()

    for idx, item in enumerate(raw_layers):
        label = item.get("id") if isinstance(item.get("id"), str) else f"layers[{idx}]"
        ok = True
        for f in REQUIRED_LAYER_FIELDS:
            if f not in item:
                defects.append(f"ДЕФЕКТ формы: {label}: поле '{f}' отсутствует")
                ok = False
        if not ok:
            continue
        idv = item["id"]
        if not isinstance(idv, str) or not idv:
            defects.append(f"ДЕФЕКТ формы: {label}: 'id' не непустая строка")
            ok = False
        elif seen_ids.get(idv, 0) > 1:
            if idv not in dup_reported:
                defects.append(f"ДЕФЕКТ формы: дубль id: {idv} ({seen_ids[idv]} вхождений)")
                dup_reported.add(idv)
            ok = False
        carrier = item.get("carrier")
        if not isinstance(carrier, list) or not carrier:
            defects.append(f"ДЕФЕКТ формы: {label}: 'carrier' пуст или не список")
            ok = False
        elif not all(isinstance(c, str) and c for c in carrier):
            defects.append(f"ДЕФЕКТ формы: {label}: 'carrier' несёт нестроковый/пустой элемент")
            ok = False
        literal = item.get("literal")
        if not isinstance(literal, str) or not literal:
            defects.append(f"ДЕФЕКТ формы: {label}: 'literal' пуст или не строка")
            ok = False
        aliases = item.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            defects.append(f"ДЕФЕКТ формы: {label}: 'aliases' не список строк")
            ok = False
            aliases = []
        # адверсариальная батарея: "{" в литерале/алиасе -- шаблон формата
        # попал целиком, требование статического префикса.
        if isinstance(literal, str) and "{" in literal:
            defects.append(f"ДЕФЕКТ формы: {label}: '{{' в литерале -- требуется статический префикс")
            ok = False
        if isinstance(aliases, list):
            for a in aliases:
                if isinstance(a, str) and "{" in a:
                    defects.append(f"ДЕФЕКТ формы: {label}: '{{' в алиасе -- требуется статический префикс")
                    ok = False
        # Узел B (Б-К8, "тем же способом, что validate_layers для
        # carrier/literal"): 'reachable' -- ОПЦИОНАЛЬНОЕ поле (registry_
        # version 1 не несёт его вовсе -- край спеки "версия 1 без поля
        # читается, все слои н-д, exit 0", НЕ дефект). ПРИСУТСТВУЮЩЕЕ, но
        # синтаксически негодное значение ("{" -шаблон / пустая строка /
        # число / вложенный объект / вид вне закрытого словаря) -- ДЕФЕКТ
        # формы, вся запись исключается (та же дисциплина, что и carrier/
        # literal выше -- НЕ трейсбек, D-0043).
        reachable = "unmeasured"
        reachable_reason: Optional[str] = "reachable не объявлен в реестре"
        if "reachable" in item:
            reachable_raw = item.get("reachable")
            if not isinstance(reachable_raw, str) or not reachable_raw or "{" in reachable_raw:
                defects.append(f"ДЕФЕКТ формы: {label}: 'reachable' синтаксически негодно")
                ok = False
            elif reachable_raw not in POPULATION_KINDS_ALL:
                defects.append(f"ДЕФЕКТ формы: {label}: 'reachable' неизвестного вида: {reachable_raw!r}")
                ok = False
            else:
                reachable = reachable_raw
                if reachable == "unmeasured":
                    reason_raw = item.get("reason")
                    if not isinstance(reason_raw, str) or not reason_raw.strip():
                        defects.append(
                            f"ДЕФЕКТ формы: {label}: reachable=unmeasured требует непустой 'reason'"
                        )
                        ok = False
                    else:
                        reachable_reason = reason_raw
                else:
                    reachable_reason = None
        if not ok:
            continue
        valid.append(LayerDef(
            id=idv, name=item.get("name", idv), carrier=carrier,
            symbol=item.get("symbol"), literal=literal, aliases=aliases,
            hook_event=item.get("hook_event", ""), matcher=item.get("matcher", ""),
            denominator=item.get("denominator", "Z1"),
            listed_in_check_11v=bool(item.get("listed_in_check_11v", False)),
            index=idx, reachable=reachable, reachable_reason=reachable_reason,
        ))

    # Перекрытие литералов ЗАПРЕЩЕНО формой реестра (§3.4): проверяем ВСЕ
    # строки (литерал+алиасы) попарно МЕЖДУ РАЗНЫМИ слоями.
    all_strings: List[Tuple[str, str]] = []  # (layer_id, string)
    for l in valid:
        for s in l.all_strings():
            all_strings.append((l.id, s))
    for i, (lid_a, sa) in enumerate(all_strings):
        for lid_b, sb in all_strings:
            if lid_a == lid_b:
                continue
            if sa == sb:
                continue
            if sa in sb:
                msg = f"ДЕФЕКТ формы: перекрытие литералов: '{sa}' ({lid_a}) -- подстрока '{sb}' ({lid_b})"
                if msg not in defects:
                    defects.append(msg)

    return valid, defects


# НАХОДКА билдера: несколько носителей (dispatch_gate/negative_lint/
# claim_control_gate/search_control_gate) собирают длинные сообщения
# соседними Python-строковыми литералами ("...text one "\n    "text
# two..."), которые runtime склеивает в ОДНУ строку, а raw ИСХОДНЫЙ
# ТЕКСТ несёт между ними перевод строки и отступ. Наивный substring-
# поиск по сырому тексту carrier'а тогда ложно не находит ЖИВОЙ,
# верно работающий литерал (пример: MSG_TEMPLATE claim_control_gate.py
# несёт "...this " / "session..." на границе двух строк). Живость
# проверяется по ТЕКСТУ СО СКЛЕЕННЫМИ ШВАМИ конкатенации: закрывающая
# кавычка, только пробелы/перевод строки, открывающая кавычка ТОГО ЖЕ
# вида -- шов убирается, содержимое остаётся тем же самым (не
# изобретается).
_CONCAT_SEAM_RE = re.compile(r'"\s*\n\s*"|\'\s*\n\s*\'')


def _flatten_concat_seams(text: str) -> str:
    return _CONCAT_SEAM_RE.sub("", text)


def check_liveness(layer: LayerDef, root: Path) -> Tuple[bool, str]:
    """(i) живость литерала: литерал ОБЯЗАН найтись в файле carrier
    (чтением, не памятью). Любой carrier из списка, несущий литерал ИЛИ
    алиас -- достаточно (край 11: carrier -- список)."""
    for rel in layer.carrier:
        full = root / rel
        if not full.exists():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        flattened = _flatten_concat_seams(text)
        for s in layer.all_strings():
            if s in text or s in flattened:
                return True, f"жив в {rel}"
    return False, "не найден ни в одном carrier"


def check_symbol_binding(layer: LayerDef, root: Path) -> Optional[str]:
    """(ii) привязка к константе -- ТОЛЬКО когда symbol не null (§4(ii):
    не у всех слоёв есть константа, symbol ОБЯЗАН допускать null).
    Возвращает None (ок/не применимо) или строку дефекта."""
    if layer.symbol is None:
        return None
    for rel in layer.carrier:
        full = root / rel
        if not full.exists():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(rf"\b{re.escape(layer.symbol)}\b\s*(:.*)?=", text):
            return None
    return f"ДЕФЕКТ РЕЕСТРА: {layer.id}: symbol '{layer.symbol}' не найден как присвоение в carrier"


# ---------------------------------------------------------------------------
# Сверка с чеком 11(в) (§4(iii))
# ---------------------------------------------------------------------------

def parse_check_11v_names(protocol_text: str) -> Optional[List[str]]:
    """Извлекает имена слоёв из блока 11(в) PROCESS/WEEKLY_CALIBRATION_
    PROTOCOL.md. Возвращает None, если блок не найден (форма протокола
    разошлась -- печатается находкой, не падает)."""
    idx = protocol_text.find("11(в)")
    if idx == -1:
        return None
    end_idx = protocol_text.find("ПЕРЕЧЕНЬ ОТКРЫТ", idx)
    if end_idx == -1:
        end_idx = idx + 2000
    block = protocol_text[idx:end_idx]
    # начало перечня -- после "Слои и носители:"
    marker = "Слои и носители:"
    m_idx = block.find(marker)
    if m_idx == -1:
        return None
    block = block[m_idx + len(marker):]
    normalized = re.sub(r"\s+", " ", block).strip()
    names: List[str] = []
    for segment in normalized.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        # отрезаем " -- tools/....py" (носитель) справа
        seg = re.split(r"\s+—\s+tools/", segment)[0]
        seg = re.split(r"\s+--\s+tools/", seg)[0]
        # убираем скобочные пояснения "(...)"
        seg = re.sub(r"\([^)]*\)", "", seg)
        for name in seg.split(","):
            name = name.strip().strip(".")
            if name:
                names.append(name)
    return names


def diff_check_11v(layers: List[LayerDef], check_names: Optional[List[str]]) -> Tuple[List[str], List[str]]:
    """Возвращает (в_чеке_нет_в_реестре, в_реестре_нет_в_чеке)."""
    if check_names is None:
        return [], []
    check_set = set(check_names)
    registry_listed = {l.name for l in layers if l.listed_in_check_11v}
    registry_all = {l.name for l in layers}
    in_check_not_registry = sorted(check_set - registry_all)
    in_registry_not_check = sorted(registry_all - check_set)
    return in_check_not_registry, in_registry_not_check


# ---------------------------------------------------------------------------
# Настройки хуков -- proxy-определение (несколько скриптов на одном матчере)
# ---------------------------------------------------------------------------

def load_hook_multiplicity(settings_path: Path) -> Dict[Tuple[str, str], int]:
    """(hook_event, matcher) -> число зарегистрированных command-хуков.
    >1 -- Z1 этого матчера делится между носителями (proxy)."""
    result: Dict[Tuple[str, str], int] = {}
    if not settings_path.exists():
        return result
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        return result
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher", "")
            cmds = group.get("hooks", [])
            n = len(cmds) if isinstance(cmds, list) else 0
            key = (event, matcher)
            result[key] = result.get(key, 0) + n
    return result


# ---------------------------------------------------------------------------
# Время
# ---------------------------------------------------------------------------

ISO_LOCAL_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def parse_window_bound(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    if not ISO_LOCAL_RE.match(s):
        raise ArgError(f"не ISO локальное наивное время (YYYY-MM-DDTHH:MM:SS): {s!r}")
    try:
        naive = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ArgError(f"невалидная дата/время: {s!r} ({exc})") from exc
    # наивный datetime трактуется astimezone() как ЛОКАЛЬНОЕ время системы.
    return naive.astimezone()


def parse_transcript_ts(ts: Any) -> Optional[datetime]:
    if not isinstance(ts, str) or not ts:
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# JSON-эскейп литерала (для raw-fallback против ensure_ascii=True носителей,
# см. докстринг модуля -- journal_echo.py экранирует не-ASCII в \\uXXXX)
# ---------------------------------------------------------------------------

def _json_escaped_form(s: str) -> str:
    return json.dumps(s)[1:-1]


# ---------------------------------------------------------------------------
# Корпус: перечисление файлов (Р6б -- верхний уровень + subagents/)
# ---------------------------------------------------------------------------

def enumerate_corpus_files(transcripts_dir: Path) -> List[Path]:
    if not transcripts_dir.exists() or not transcripts_dir.is_dir():
        raise SourceError(f"--transcripts не каталог/не существует: {transcripts_dir}")
    files: List[Path] = sorted(transcripts_dir.glob("*.jsonl"))
    for sub in sorted(transcripts_dir.iterdir()):
        if not sub.is_dir():
            continue
        agents_dir = sub / "subagents"
        if agents_dir.is_dir():
            files.extend(sorted(agents_dir.glob("*.jsonl")))
    return files


def is_sidechain_file(path: Path) -> bool:
    """Субагентский (sidechain) файл -- лежит в `<session>/subagents/`
    (Р6б спеки). hook_success/hook_additional_context НЕ фиксируются НИ
    ОДНОЙ записью на субагентских вызовах (измерено критиком -- скан
    корпуса), поэтому tool_use ИЗ ЭТИХ файлов физически не может дать
    числитель -- честный знаменатель (Ф1) считает только main-файлы."""
    return path.parent.name == "subagents"


# ---------------------------------------------------------------------------
# Измерение
# ---------------------------------------------------------------------------

@dataclass
class LayerCounts:
    calls: int = 0
    lines: int = 0
    raw_calls: int = 0
    raw_lines: int = 0


@dataclass
class Report:
    layers: List[LayerDef]
    counts: Dict[str, LayerCounts]
    tool_use_counts: Dict[str, int]
    total_tool_use_in_window: int
    dedup_dropped: int
    total_hook_success: int
    total_hook_additional_context: int
    silent_hook_success: int
    raw_parse_failed: int
    no_timestamp: int
    fallback_key_count: int
    transcripts_dir: Path
    total_lines_seen: int
    broken_lines: int
    files_read: int
    total_bytes: int
    in_window_records: int
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    proxy_map: Dict[Tuple[str, str], int]
    fixture_calls: int
    fixture_lines: int
    sidechain_tool_use_in_window: int
    orphan_hac_count: int
    duplicate_tool_use_id_count: int
    population_achievable_counts: Dict[str, int]


def process_corpus(
    files: List[Path], layers: List[LayerDef],
    window_start: Optional[datetime], window_end: Optional[datetime],
    proxy_map: Dict[Tuple[str, str], int],
    transcripts_dir: Optional[Path] = None,
    compute_fixture: bool = True,
) -> Report:
    seen: set = set()
    seen_raw: set = set()
    counts: Dict[str, LayerCounts] = {l.id: LayerCounts() for l in layers}
    tool_use_counts: Dict[str, int] = {}
    total_tool_use_in_window = 0
    sidechain_tool_use_in_window = 0
    dedup_dropped = 0
    total_hook_success = 0
    total_hook_additional_context = 0
    silent_hook_success = 0
    raw_parse_failed = 0
    no_timestamp = 0
    fallback_key_count = 0
    total_lines_seen = 0
    broken_lines = 0
    total_bytes = 0
    in_window_records = 0
    duplicate_tool_use_id_count = 0
    # Узел B: сумма ДОСТИЖИМОЙ популяции по каждому виду `reachable`
    # (не по слою -- несколько слоёв делят один вид, напр. шесть
    # журнальных слоёв все читают ключ "journal_path"). Позиция --
    # РЯДОМ с is_sidechain_file, ПОСЛЕ проверки окна, ПЕРЕД
    # tool_use_counts[name] += 1 (B-К6, позиционный край спеки узла B).
    population_achievable_counts: Dict[str, int] = {k: 0 for k in POPULATION_KINDS_MEASURED}
    # Ф4: числитель дедуплицируется (`seen`), tool_use-знаменатель --
    # НЕ дедуплицируется (не подгонка под старое число из отчёта критика
    # -- измеряется ЖИВЬЁМ этим прогоном); дублирующийся id НЕ
    # вычитается из знаменателя (асимметрия остаётся, эффект незначим
    # СЕЙЧАС), но виден отдельной строкой -- при перезаписи транскрипта
    # он вырастет и снова занизит долю, если промолчать.
    tool_use_ids_seen: set = set()
    orphan_hac_count = 0

    # Ф2: hook_additional_context БЕЗ пары hook_success по ключу
    # (unit_key, hookName) -- единственный след срабатывания (Б3 находка
    # критика). Пары нельзя знать в момент чтения строки (пара может
    # физически лежать ПОЗЖЕ в файле или в другом файле корпуса) --
    # поэтому hac буферизуется и сверяется с success_keys ПОСЛЕ полного
    # прохода по всем файлам (порядко-независимо).
    success_keys: set = set()
    hac_buffer: List[Tuple[str, str, List[str]]] = []  # (unit_key, hook_name, content)

    escaped_strings: Dict[str, List[str]] = {
        l.id: [_json_escaped_form(s) for s in l.all_strings()] for l in layers
    }

    for f in files:
        is_side = is_sidechain_file(f)
        try:
            total_bytes += f.stat().st_size
        except OSError:
            pass
        try:
            fh = open(f, "r", encoding="utf-8-sig", errors="replace", newline=None)
        except OSError:
            continue
        with fh:
            for line_no, raw_ln in enumerate(fh, start=1):
                ln = raw_ln.strip()
                if not ln:
                    continue
                total_lines_seen += 1
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    broken_lines += 1
                    continue
                if not isinstance(rec, dict):
                    broken_lines += 1
                    continue

                ts_raw = rec.get("timestamp")
                dt = parse_transcript_ts(ts_raw)
                if dt is None:
                    no_timestamp += 1
                    continue
                if window_start is not None and dt < window_start:
                    continue
                if window_end is not None and dt >= window_end:
                    continue
                in_window_records += 1

                if rec.get("type") == "assistant":
                    msg = rec.get("message")
                    if isinstance(msg, dict):
                        content = msg.get("content")
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "tool_use":
                                    name = item.get("name")
                                    if isinstance(name, str):
                                        # Ф1: sidechain-вызовы физически не
                                        # могут дать hook_success (измерено
                                        # критиком) -- честный знаменатель
                                        # считает ТОЛЬКО main-поток;
                                        # sidechain учитывается отдельно
                                        # (строка невидимости в выводе).
                                        if is_side:
                                            sidechain_tool_use_in_window += 1
                                        else:
                                            item_id = item.get("id")
                                            if isinstance(item_id, str) and item_id:
                                                if item_id in tool_use_ids_seen:
                                                    duplicate_tool_use_id_count += 1
                                                else:
                                                    tool_use_ids_seen.add(item_id)
                                            # Узел B: ДОСТИЖИМАЯ популяция --
                                            # тот же tool_use item, ДО
                                            # tool_use_counts[name] += 1
                                            # (позиционный край B-К6, см.
                                            # выше). НЕ дедуплицируется --
                                            # тот же (сырой) режим счёта,
                                            # что и tool_use_counts/
                                            # total_tool_use_in_window,
                                            # иначе "недостижимо = матчер -
                                            # достижимо" разъедется по базе.
                                            tool_input = item.get("input")
                                            if not isinstance(tool_input, dict):
                                                tool_input = {}
                                            for kind, pred in POPULATION_PREDICATES.items():
                                                if pred(name, tool_input):
                                                    population_achievable_counts[kind] += 1
                                            tool_use_counts[name] = tool_use_counts.get(name, 0) + 1
                                            total_tool_use_in_window += 1

                att = rec.get("attachment")
                if not isinstance(att, dict):
                    continue
                atype = att.get("type")
                if atype not in ("hook_success", "hook_additional_context"):
                    continue

                tool_use_id = att.get("toolUseID")
                hook_name = att.get("hookName") or ""
                if isinstance(tool_use_id, str) and tool_use_id:
                    unit_key = tool_use_id
                else:
                    uuid_ = rec.get("uuid")
                    if isinstance(uuid_, str) and uuid_:
                        unit_key = f"uuid:{uuid_}"
                    else:
                        unit_key = f"fallback:{f}:{line_no}"
                        fallback_key_count += 1

                if atype == "hook_additional_context":
                    total_hook_additional_context += 1
                    content = att.get("content")
                    if isinstance(content, list):
                        texts = [c for c in content if isinstance(c, str)]
                    elif isinstance(content, str):
                        texts = [content]
                    else:
                        texts = []
                    hac_buffer.append((unit_key, hook_name, texts))
                    continue
                if atype != "hook_success":
                    continue
                total_hook_success += 1
                success_keys.add((unit_key, hook_name))

                stdout = att.get("stdout")
                if not isinstance(stdout, str) or stdout.strip() == "":
                    silent_hook_success += 1
                    continue

                ctx: Optional[str] = None
                parse_ok = True
                try:
                    obj = json.loads(stdout)
                except (json.JSONDecodeError, TypeError, ValueError):
                    parse_ok = False
                    obj = None

                if parse_ok:
                    if isinstance(obj, dict):
                        hso = obj.get("hookSpecificOutput")
                        if isinstance(hso, dict):
                            v = hso.get("additionalContext")
                            if isinstance(v, str):
                                ctx = v
                    if ctx is None:
                        continue
                    for layer in layers:
                        hits = sum(ctx.count(s) for s in layer.all_strings())
                        if hits <= 0:
                            continue
                        dkey = (unit_key, hook_name, layer.id)
                        if dkey in seen:
                            dedup_dropped += 1
                            continue
                        seen.add(dkey)
                        c = counts[layer.id]
                        c.calls += 1
                        c.lines += hits
                else:
                    raw_parse_failed += 1
                    for layer in layers:
                        hits = 0
                        for s in layer.all_strings():
                            hits += stdout.count(s)
                        for s_esc in escaped_strings[layer.id]:
                            if s_esc != layer.literal and s_esc not in layer.all_strings():
                                hits += stdout.count(s_esc)
                        if hits <= 0:
                            continue
                        dkey = (unit_key, hook_name, layer.id)
                        if dkey in seen_raw:
                            continue
                        seen_raw.add(dkey)
                        c = counts[layer.id]
                        c.raw_calls += 1
                        c.raw_lines += hits

    # Ф2, второй проход (в памяти, не по файлам): hac без пары hook_success
    # по (unit_key, hook_name) -- ЕДИНСТВЕННЫЙ след срабатывания, обязан
    # считаться. Тот же дедуп-набор `seen`, чтобы дубль orphan-записей
    # ТОГО ЖЕ ключа (наблюдалось: одна и та же (toolUseID, hookName) в
    # корпусе повторяется) не досчитался дважды.
    for unit_key, hook_name, texts in hac_buffer:
        if (unit_key, hook_name) in success_keys:
            continue  # есть пара -- не осиротевшая (§3.1, игнорируется целиком)
        orphan_hac_count += 1
        if not texts:
            continue
        for layer in layers:
            hits = sum(sum(t.count(s) for t in texts) for s in layer.all_strings())
            if hits <= 0:
                continue
            dkey = (unit_key, hook_name, layer.id)
            if dkey in seen:
                dedup_dropped += 1
                continue
            seen.add(dkey)
            c = counts[layer.id]
            c.calls += 1
            c.lines += hits

    if compute_fixture:
        fixture_calls, fixture_lines = fixture_control(layers)
    else:
        fixture_calls, fixture_lines = 0, 0

    return Report(
        layers=layers, counts=counts, tool_use_counts=tool_use_counts,
        total_tool_use_in_window=total_tool_use_in_window,
        dedup_dropped=dedup_dropped, total_hook_success=total_hook_success,
        total_hook_additional_context=total_hook_additional_context,
        silent_hook_success=silent_hook_success,
        raw_parse_failed=raw_parse_failed, no_timestamp=no_timestamp,
        fallback_key_count=fallback_key_count,
        transcripts_dir=transcripts_dir if transcripts_dir is not None else Path("."),
        total_lines_seen=total_lines_seen, broken_lines=broken_lines,
        files_read=len(files), total_bytes=total_bytes,
        in_window_records=in_window_records,
        window_start=window_start, window_end=window_end,
        proxy_map=proxy_map, fixture_calls=fixture_calls, fixture_lines=fixture_lines,
        sidechain_tool_use_in_window=sidechain_tool_use_in_window,
        orphan_hac_count=orphan_hac_count,
        duplicate_tool_use_id_count=duplicate_tool_use_id_count,
        population_achievable_counts=population_achievable_counts,
    )


# ---------------------------------------------------------------------------
# Встроенная фикстура (§7): позитив + заведомо непопадающее вхождение имени
# слоя в теле сообщения/toolUseResult -- КРАСНЫЙ КОНТРОЛЬ (DoD-2).
# ---------------------------------------------------------------------------

def _fixture_records() -> List[str]:
    """Синтетические JSONL-строки мини-транскрипта. Ожидание:
    calls=2 (два разных unit несут GIVEN-PATH WARN), lines=3 (1+2
    вхождения). Запись 3 (assistant-текст) и запись 4 (toolUseResult)
    несут ИМЯ СЛОЯ в НЕструктурном месте -- не должны прибавить НИЧЕГО
    (это и есть красный контроль DoD-2)."""
    rec1 = {
        "uuid": "fixture-uuid-1",
        "timestamp": "2026-01-01T00:00:01.000Z",
        "attachment": {
            "type": "hook_success",
            "hookName": "PreToolUse:Agent",
            "toolUseID": "fixture-tool-1",
            "stdout": json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": "GIVEN-PATH WARN: путей не существует: a",
                }
            }, ensure_ascii=False),
        },
    }
    rec2 = {
        "uuid": "fixture-uuid-2",
        "timestamp": "2026-01-01T00:00:02.000Z",
        "attachment": {
            "type": "hook_success",
            "hookName": "PreToolUse:Agent",
            "toolUseID": "fixture-tool-2",
            "stdout": json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": (
                        "GIVEN-PATH WARN: путей не существует: a; "
                        "GIVEN-PATH WARN: путей не существует: b"
                    ),
                }
            }, ensure_ascii=False),
        },
    }
    # НЕ hook_success -- имя слоя в ТЕЛЕ СООБЩЕНИЯ ассистента (красный
    # контроль): не должно попасть в счёт.
    rec3 = {
        "uuid": "fixture-uuid-3",
        "timestamp": "2026-01-01T00:00:03.000Z",
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": "см. GIVEN-PATH WARN: в логе выше"}]},
    }
    # НЕ hook_success -- имя слоя в toolUseResult (вывод инструмента,
    # ручной прогон/греп) -- красный контроль DoD-2.
    rec4 = {
        "uuid": "fixture-uuid-4",
        "timestamp": "2026-01-01T00:00:04.000Z",
        "type": "user",
        "message": {"content": [{
            "type": "tool_result",
            "content": "grep output: GIVEN-PATH WARN: путей не существует: z",
        }]},
    }
    # второй след ТОГО ЖЕ срабатывания -- игнорируется ЦЕЛИКОМ (§3.1).
    rec5 = {
        "uuid": "fixture-uuid-5",
        "timestamp": "2026-01-01T00:00:05.000Z",
        "attachment": {
            "type": "hook_additional_context",
            "hookName": "PreToolUse:Agent",
            "toolUseID": "fixture-tool-1",
        },
    }
    return [json.dumps(r, ensure_ascii=False) for r in (rec1, rec2, rec3, rec4, rec5)]


def fixture_control(layers: List[LayerDef]) -> Tuple[int, int]:
    """Прогоняет встроенную фикстуру ЧЕРЕЗ ТУ ЖЕ функцию process_corpus,
    что и боевые данные -- никакой отдельной логики счёта (иначе
    фикстура ничего не доказывает о реальном счётчике)."""
    fixture_layers = [l for l in layers if l.id == _FIXTURE_LAYER_ID]
    if not fixture_layers:
        # реестр без слоя фикстуры -- фикстура не может быть посчитана
        # (0/0 печатается явным дефектом вызывающей стороной).
        return 0, 0
    import tempfile
    import os as _os
    fd, path = tempfile.mkstemp(suffix=".jsonl", prefix="warn_density_fixture_")
    try:
        with _os.fdopen(fd, "w", encoding="utf-8") as fh:
            for ln in _fixture_records():
                fh.write(ln + "\n")
        rep = process_corpus(
            [Path(path)], fixture_layers, window_start=None, window_end=None,
            proxy_map={}, compute_fixture=False,
        )
        c = rep.counts[_FIXTURE_LAYER_ID]
        return c.calls, c.lines
    finally:
        try:
            _os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Сайдкар
# ---------------------------------------------------------------------------

def registry_sha(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def read_sidecar_last(path: Path) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    if not path.exists():
        return None, []
    warnings: List[str] = []
    last: Optional[Dict[str, Any]] = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, ln in enumerate(fh, start=1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                last = json.loads(ln)
            except json.JSONDecodeError as exc:
                warnings.append(f"битая строка сайдкара {path}:{line_no}: {exc}")
    return last, warnings


def write_sidecar_entry(path: Path, entry: Dict[str, Any]) -> Optional[str]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return None
    except OSError as exc:
        return f"сайдкар не записан ({path}): {exc}"


# ---------------------------------------------------------------------------
# Рендер
# ---------------------------------------------------------------------------

def _fmt_dt_both(dt: Optional[datetime]) -> str:
    if dt is None:
        return "(нет границы)"
    local_naive = dt.astimezone().replace(tzinfo=None).isoformat()
    utc = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"локально {local_naive} / UTC {utc}"


def layer_matcher_total(layer: LayerDef, tool_use_counts: Dict[str, int]) -> int:
    """Старый Z1 (ДО узла B) -- сумма tool_use ЛЮБОГО инструмента из
    matcher слоя, БЕЗ учёта достижимости. Узел B (Б-К2) печатает это как
    отдельное число «матчер» РЯДОМ с достижимо/недостижимо -- НЕ как
    знаменатель доли (Б-К1: доля теперь считается от достижимо, см.
    layer_population() ниже); Б-К5: «ставка на 100 вызовов» ТОЖЕ не
    использует это число -- она на total_tool_use_in_window, ЕДИНОЙ базе.
    Имя переименовано с layer_denominator_value -- старое имя больше не
    описывает роль числа честно (спека узла B, "Что ломается": смена
    сигнатуры/имени ожидаемо ломает пины трёх тестов, они в owns)."""
    names = [n for n in layer.matcher.split("|") if n]
    return sum(tool_use_counts.get(n, 0) for n in names)


def layer_population(layer: LayerDef, report: "Report") -> Tuple[Optional[int], Optional[int], int]:
    """Б-К1/Б-К2: возвращает (достижимо, недостижимо, матчер).
    достижимо/недостижимо -- None, когда layer.reachable == "unmeasured"
    (Б-К3: «н-д (популяция не объявлена: <reason>)», НЕ тихий откат к
    матчеру). Когда reachable -- измеримый вид: достижимо = сумма
    population_achievable_counts по этому виду за окно (та же основа,
    что и матчер -- сырой, не дедуплицированный счёт, см. process_corpus);
    недостижимо = матчер - достижимо (клип к 0 -- защитно, достижимо ⊆
    матчер по построению предикатов -- см. _JOURNAL_LAYER_TOOL_NAMES и
    сиблингов, ограничивающих предикат ТЕМИ ЖЕ именами инструментов, что
    у matcher слоя)."""
    matcher_total = layer_matcher_total(layer, report.tool_use_counts)
    if layer.reachable not in POPULATION_KINDS_MEASURED:
        return None, None, matcher_total
    achievable = report.population_achievable_counts.get(layer.reachable, 0)
    unreachable = max(matcher_total - achievable, 0)
    return achievable, unreachable, matcher_total


def layer_is_proxy(layer: LayerDef, proxy_map: Dict[Tuple[str, str], int]) -> bool:
    """proxy=true -- НЕСКОЛЬКО хук-скриптов зарегистрированы на ОДНОМ
    (hook_event, matcher) в .claude/settings.json -- МАТЧЕР этого слоя
    (Task|Agent и т.п.) есть трафик, делимый с ДРУГИМ носителем, не
    только этим. Узел B (конфликтная пара 4 спеки): это утверждение
    ПРО МАТЧЕР (layer_matcher_total выше), а не про ДОСТИЖИМУЮ
    популяцию (layer_population) -- пер-слойный знаменатель НЕ меняет
    эту логику (proxy остаётся свойством регистрации хука в settings.json,
    измеряется независимо от reachable), но текст обязан НАЗЫВАТЬ, что
    он про матчер, а не про достижимо -- иначе рецидив того же класса
    внутри той же функции (см. render_text: тег теперь «матчер-proxy»,
    не голое «proxy»)."""
    return proxy_map.get((layer.hook_event, layer.matcher), 0) > 1


def compute_run_defects(report: Report) -> List[str]:
    """Дефекты, печатаемые ОБОИМИ рендерами (text/json) и решающие exit
    code ОБЫЧНОГО прогона (Ф3) -- никогда голый ноль без вердикта.
    Узел B (Б-К4, ДЕТЕКТОР МЕХАНИЗМА): calls > достижимо -- предикат
    населённости, ставший уже реальности, ловится собственным замером."""
    defects: List[str] = []
    if report.total_lines_seen > 0 and report.broken_lines == report.total_lines_seen:
        defects.append(f"ДЕФЕКТ ИСТОЧНИКА: 100% строк биты ({report.broken_lines}/{report.total_lines_seen})")
    if report.fixture_calls != FIXTURE_EXPECTED_CALLS or report.fixture_lines != FIXTURE_EXPECTED_LINES:
        defects.append(
            f"ДЕФЕКТ ИНСТРУМЕНТА: фикстура {report.fixture_calls}/{FIXTURE_EXPECTED_CALLS} calls, "
            f"{report.fixture_lines}/{FIXTURE_EXPECTED_LINES} lines не сходится"
        )
    for layer in report.layers:
        achievable, _unreachable, _matcher = layer_population(layer, report)
        if achievable is None:
            continue
        c = report.counts.get(layer.id)
        if c is None:
            continue
        if c.calls > achievable:
            defects.append(
                f"ДЕФЕКТ ПРЕДИКАТА: {layer.id}: calls={c.calls} > достижимо={achievable}"
            )
    return defects


def render_text(
    report: Report, root: Path, check_names: Optional[List[str]],
    base_status: str, sidecar_warn: Optional[str], source_empty: bool,
) -> str:
    out: List[str] = []
    out.append("=== КОНТРОЛЬ ИСТОЧНИКОВ ===")
    out.append(f"  каталог: {report.transcripts_dir} (деплой: OS, чужие не измерены)")
    out.append(f"  файлов: {report.files_read} | байт: {report.total_bytes}")
    out.append(f"  окно: start={_fmt_dt_both(report.window_start)} end={_fmt_dt_both(report.window_end)}")
    out.append(f"  фикстура (встроенный позитивный+красный контроль): "
               f"{report.fixture_calls}/{FIXTURE_EXPECTED_CALLS} calls, "
               f"{report.fixture_lines}/{FIXTURE_EXPECTED_LINES} lines")
    out.append(f"  база: {base_status}")
    if sidecar_warn:
        out.append(f"  WARN: {sidecar_warn}")
    if source_empty:
        out.append("  ИСТОЧНИК ПУСТ: каталог существует, файлов 0")
    out.append(f"  дедуп: снято {report.dedup_dropped} записей-дублей")
    out.append(f"  вторых следов (hook_additional_context): {report.total_hook_additional_context} "
               f"(hook_success: {report.total_hook_success}, "
               f"осиротевших без пары hook_success: {report.orphan_hac_count})")
    _sidechain_total = report.total_tool_use_in_window + report.sidechain_tool_use_in_window
    out.append(
        f"  субагентский поток невидим: {report.sidechain_tool_use_in_window} "
        f"из {_sidechain_total} вызовов окна (знаменатель считает только main)"
    )
    out.append(
        f"  дедуп асимметричен: числитель дедуплицируется, tool_use-знаменатель -- нет; "
        f"дублей id в окне: {report.duplicate_tool_use_id_count} из "
        f"{report.total_tool_use_in_window} (не вычитаются -- эффект незначим, "
        f"растёт при перезаписи транскрипта)"
    )
    out.append(f"  без времени: {report.no_timestamp}")
    out.append(f"  fallback-ключ (нет toolUseID и uuid): {report.fallback_key_count}")
    out.append(f"  молчаливые hook_success (пустой stdout): {report.silent_hook_success}")
    out.append(f"  stdout не парсится как JSON (raw-fallback): {report.raw_parse_failed}")
    if report.total_lines_seen > 0:
        pct_broken = report.broken_lines / report.total_lines_seen * 100
        out.append(f"  битых строк JSONL: {report.broken_lines}/{report.total_lines_seen} ({pct_broken:.1f}%)")
    else:
        out.append("  битых строк JSONL: 0/0")
    if report.in_window_records == 0:
        out.append("ОКНО ПУСТО: 0 записей")

    out.append("\n=== СЛОИ ===")
    out.append(
        "  (доля: calls / ДОСТИЖИМО -- база РАЗНАЯ у каждого слоя, между слоями НЕ сравнима, Б-К1)"
    )
    out.append(
        "  (ставка: calls / total_tool_use_in_window*100 -- ЕДИНАЯ база для всех слоёв, "
        "сравнима МЕЖДУ слоями, Б-К5)"
    )
    not_fired: List[str] = []
    for layer in report.layers:
        c = report.counts[layer.id]
        achievable, unreachable, matcher_total = layer_population(layer, report)
        proxy = layer_is_proxy(layer, report.proxy_map)
        if achievable is None:
            pop_str = f"достижимо=н-д недостижимо=н-д матчер={matcher_total}"
            share_str = f"н-д (популяция не объявлена: {layer.reachable_reason})"
        else:
            pop_str = f"достижимо={achievable} недостижимо={unreachable} матчер={matcher_total}"
            if achievable == 0:
                share_str = f"н-д (достижимо 0 из {matcher_total})"
            else:
                share_str = f"{c.calls / achievable * 100:.1f}%"
        if report.total_tool_use_in_window == 0:
            rate_str = "н-д (знаменатель 0)"
        else:
            rate_str = f"{c.calls / report.total_tool_use_in_window * 100:.2f}/100"
        proxy_tag = " матчер-proxy" if proxy else ""
        out.append(
            f"  {layer.id} [{layer.name}]: calls={c.calls} lines={c.lines} "
            f"(+raw calls={c.raw_calls} lines={c.raw_lines}) "
            f"{pop_str}{proxy_tag} доля={share_str} ставка={rate_str} "
            f"11в={'да' if layer.listed_in_check_11v else 'нет'}"
        )
        if c.calls == 0 and report.in_window_records > 0:
            not_fired.append(layer.id)

    out.append("\n=== НЕ СРАБОТАЛИ ===")
    if not_fired:
        for lid in not_fired:
            layer = next(l for l in report.layers if l.id == lid)
            alive, reason = check_liveness(layer, root)
            verdict = f"жив ({reason})" if alive else "ДЕФЕКТ РЕЕСТРА (литерал не найден в carrier)"
            out.append(f"  {lid} [{layer.name}]: {verdict}")
    else:
        out.append("  (пусто)" if report.in_window_records > 0 else "  (окно пусто -- вердикт не выносится)")

    out.append("\n=== ДЕФЕКТЫ ===")
    defects: List[str] = compute_run_defects(report)
    if defects:
        for d in defects:
            out.append(f"  {d}")
    else:
        out.append("  (дефектов нет)")

    out.append("\n=== НАХОДКИ О ЧЕКЕ ===")
    in_check_not_reg, in_reg_not_check = diff_check_11v(report.layers, check_names)
    if check_names is None:
        out.append("  (11(в) не распознан в протоколе -- сверка пропущена)")
    else:
        if in_check_not_reg:
            out.append(f"  в чеке названо, в реестре нет: {', '.join(in_check_not_reg)}")
        if in_reg_not_check:
            out.append(f"  в реестре есть, в чеке не названо (НАХОДКА, чек ПЕРЕЧЕНЬ ОТКРЫТ): "
                       f"{', '.join(in_reg_not_check)}")
        if not in_check_not_reg and not in_reg_not_check:
            out.append("  (сходится)")

    total_calls = sum(c.calls for c in report.counts.values())
    out.append(f"\nИТОГ: слоёв {len(report.layers)} · calls всего {total_calls} · "
               f"tool_use в окне {report.total_tool_use_in_window}")
    return "\n".join(out)


def build_sidecar_entry(report: Report, registry_hash: str) -> Dict[str, Any]:
    layers_map = {}
    for layer in report.layers:
        c = report.counts[layer.id]
        achievable, unreachable, matcher_total = layer_population(layer, report)
        layers_map[layer.id] = {
            "calls": c.calls, "lines": c.lines,
            "raw_calls": c.raw_calls, "raw_lines": c.raw_lines,
            "denominator": matcher_total,  # старое имя поля -- совместимость со старыми 7 записями (тот же матчер-Z1)
            "reachable": layer.reachable,
            "achievable": achievable,
            "unreachable": unreachable,
            "matcher": matcher_total,
        }
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "registry_sha": registry_hash,
        "population_rule_version": POPULATION_RULE_VERSION,
        "window_start": report.window_start.isoformat() if report.window_start else None,
        "window_end": report.window_end.isoformat() if report.window_end else None,
        "layers": layers_map,
        "total_tool_use_in_window": report.total_tool_use_in_window,
    }


def render_json(report: Report, root: Path, check_names: Optional[List[str]]) -> str:
    layers_out = []
    for layer in report.layers:
        c = report.counts[layer.id]
        achievable, unreachable, matcher_total = layer_population(layer, report)
        layers_out.append({
            "id": layer.id, "name": layer.name, "calls": c.calls, "lines": c.lines,
            "raw_calls": c.raw_calls, "raw_lines": c.raw_lines,
            "denominator": matcher_total, "proxy": layer_is_proxy(layer, report.proxy_map),
            "reachable": layer.reachable, "reachable_reason": layer.reachable_reason,
            "achievable": achievable, "unreachable": unreachable, "matcher": matcher_total,
            "listed_in_check_11v": layer.listed_in_check_11v,
        })
    in_check_not_reg, in_reg_not_check = diff_check_11v(report.layers, check_names)
    payload = {
        "files_read": report.files_read, "total_bytes": report.total_bytes,
        "fixture_calls": report.fixture_calls, "fixture_lines": report.fixture_lines,
        "dedup_dropped": report.dedup_dropped,
        "no_timestamp": report.no_timestamp, "silent_hook_success": report.silent_hook_success,
        "raw_parse_failed": report.raw_parse_failed,
        "broken_lines": report.broken_lines, "total_lines_seen": report.total_lines_seen,
        "in_window_records": report.in_window_records,
        "total_tool_use_in_window": report.total_tool_use_in_window,
        "sidechain_tool_use_in_window": report.sidechain_tool_use_in_window,
        "orphan_hac_count": report.orphan_hac_count,
        "duplicate_tool_use_id_count": report.duplicate_tool_use_id_count,
        "layers": layers_out,
        "check_11v_diff": {"in_check_not_registry": in_check_not_reg, "in_registry_not_check": in_reg_not_check},
        "defects": compute_run_defects(report),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# --check
# ---------------------------------------------------------------------------

def scan_corpus_health(files: List[Path]) -> Tuple[int, int]:
    """(total_lines_seen, broken_lines) -- лёгкий скан БЕЗ разбора слоёв,
    только структурная целостность JSONL (--check не считает срабатывания,
    только форму: DoD-4 + края 3/4)."""
    total = 0
    broken = 0
    for f in files:
        try:
            fh = open(f, "r", encoding="utf-8-sig", errors="replace", newline=None)
        except OSError:
            continue
        with fh:
            for ln in fh:
                s = ln.strip()
                if not s:
                    continue
                total += 1
                try:
                    json.loads(s)
                except json.JSONDecodeError:
                    broken += 1
    return total, broken


def run_check(registry_path: Path, root: Path, transcripts_dir: Optional[Path] = None) -> Tuple[str, int]:
    out: List[str] = []
    try:
        _, raw_layers, _raw_bytes = read_registry_raw(registry_path)
    except RegistryError as exc:
        return f"warn_density --check: {exc}", 2
    layers, form_defects = validate_layers(raw_layers)
    defects = list(form_defects)
    for layer in layers:
        alive, reason = check_liveness(layer, root)
        if not alive:
            defects.append(f"ДЕФЕКТ РЕЕСТРА: {layer.id}: {reason}")
        sym_defect = check_symbol_binding(layer, root)
        if sym_defect:
            defects.append(sym_defect)
    out.append("=== --check: РЕЕСТР ===")
    out.append(f"  слоёв в реестре: {len(raw_layers)} (валидных: {len(layers)})")
    if defects:
        for d in defects:
            out.append(f"  {d}")
    else:
        out.append("  (дефектов нет)")

    # Края 3/4: --check ДОПОЛНИТЕЛЬНО реагирует на форму ИСТОЧНИКА, когда
    # он резолвится -- но НЕ требует его наличия (DoD-4 -- контракт
    # --check в первую очередь про реестр; жёсткое требование транскриптов
    # сделало бы --check хрупким к окружению, где .claude/projects/<slug>
    # не существует -- интерпретация билдера, названа в отчёте).
    if transcripts_dir is not None and transcripts_dir.exists() and transcripts_dir.is_dir():
        try:
            files = enumerate_corpus_files(transcripts_dir)
        except SourceError:
            files = []
        out.append("=== --check: ИСТОЧНИК ===")
        if not files:
            out.append(f"  ИСТОЧНИК ПУСТ: {transcripts_dir} существует, файлов 0")
            defects.append(f"ИСТОЧНИК ПУСТ: {transcripts_dir}")
        else:
            total, broken = scan_corpus_health(files)
            out.append(f"  файлов: {len(files)} | строк: {total} | битых: {broken}")
            if total > 0 and broken == total:
                msg = f"ДЕФЕКТ ИСТОЧНИКА: 100% строк биты ({broken}/{total})"
                out.append(f"  {msg}")
                defects.append(msg)

    return "\n".join(out), (1 if defects else 0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--window-start", default=None)
    p.add_argument("--window-end", default=None)
    p.add_argument("--registry-file", default=str(DEFAULT_REGISTRY))
    p.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS))
    p.add_argument("--journal", default=str(DEFAULT_JOURNAL))
    p.add_argument("--sidecar", default=str(DEFAULT_SIDECAR))
    p.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument(
        "--no-sidecar", action="store_true",
        help="Р-В1 (спека узла B): не читать и не писать logs/warn_density.jsonl -- "
             "для проверочных прогонов, не растящих сайдкар.",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    registry_path = Path(args.registry_file)
    root = REPO_ROOT

    if args.check:
        transcripts_dir = Path(args.transcripts) if args.transcripts else None
        text, code = run_check(registry_path, root, transcripts_dir)
        print(text)
        return code

    try:
        window_start = parse_window_bound(args.window_start)
        window_end = parse_window_bound(args.window_end)
    except ArgError as exc:
        print(f"warn_density: {exc}", file=sys.stderr)
        return 2
    if window_start is not None and window_end is not None and window_start >= window_end:
        print("warn_density: --window-start >= --window-end", file=sys.stderr)
        return 2

    try:
        _, raw_layers, raw_bytes = read_registry_raw(registry_path)
    except RegistryError as exc:
        print(f"warn_density: {exc}", file=sys.stderr)
        return 2
    layers, _form_defects = validate_layers(raw_layers)

    transcripts_dir = Path(args.transcripts)
    try:
        files = enumerate_corpus_files(transcripts_dir)
    except SourceError as exc:
        print(f"warn_density: {exc}", file=sys.stderr)
        return 2
    source_empty = len(files) == 0

    proxy_map = load_hook_multiplicity(Path(args.settings))
    report = process_corpus(files, layers, window_start, window_end, proxy_map, transcripts_dir)

    protocol_path = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
    check_names: Optional[List[str]] = None
    if protocol_path.exists():
        try:
            check_names = parse_check_11v_names(protocol_path.read_text(encoding="utf-8"))
        except OSError:
            check_names = None

    reg_hash = registry_sha(raw_bytes)
    if args.no_sidecar:
        # Р-В1: проверочный прогон -- НЕ читает и НЕ пишет сайдкар (файл
        # логов не растёт при DoD/адверсариальных прогонах).
        base_status = "СВЕРКА ПРОПУЩЕНА (--no-sidecar)"
        sidecar_warn: Optional[str] = None
    else:
        sidecar_path = Path(args.sidecar)
        last_entry, sidecar_read_warnings = read_sidecar_last(sidecar_path)
        if last_entry is None:
            base_status = "БАЗЫ НЕТ"
        elif last_entry.get("registry_sha") != reg_hash:
            base_status = "БАЗА ОТ ДРУГОГО РЕЕСТРА"
        elif last_entry.get("population_rule_version") != POPULATION_RULE_VERSION:
            # Р3(в): база записана ДО пер-слойного знаменателя (узел B) --
            # доли несравнимы с текущим прогоном, даже если registry_sha
            # случайно совпал бы (Б-К7: явная версия правила -- страховка
            # сверх авто-защиты по registry_sha, см. докстринг модуля).
            base_status = "БАЗА ДО ПЕР-СЛОЙНОГО ЗНАМЕНАТЕЛЯ (population_rule_version отсутствует/устарела)"
        else:
            base_status = "OK"

        sidecar_entry = build_sidecar_entry(report, reg_hash)
        sidecar_warn = write_sidecar_entry(sidecar_path, sidecar_entry)
        for w in sidecar_read_warnings:
            sidecar_warn = (sidecar_warn + "; " + w) if sidecar_warn else w

    if args.json:
        print(render_json(report, root, check_names))
    else:
        print(render_text(report, root, check_names, base_status, sidecar_warn, source_empty))
    # Ф3: фикстура, обязанная мочь упасть -- если она НЕ сошлась
    # (`compute_run_defects`), прогон СОСТОЯЛСЯ (числа напечатаны), но
    # exit code больше не голый 0 -- "никогда голый ноль" (карта, класс
    # D-0043). Битые 100% строк источника -- та же семья дефекта
    # инструмента и печатается ТЕМ ЖЕ списком.
    return 1 if compute_run_defects(report) else 0


if __name__ == "__main__":
    sys.exit(main())
