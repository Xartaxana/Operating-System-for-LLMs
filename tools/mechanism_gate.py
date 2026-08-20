"""tools/mechanism_gate.py -- Гейт правила 10(б) -- D-0055: коммит
механизмных файлов несёт осевой блок. Вызывается commit-msg-хуком
(.githooks/commit-msg). Живой файл, region-aware с 2026-08-19 (этап 2,
партия 2, узел E, t-530 / docs/tasks/2026-08-19_scanner-party2-spec.md).
Прежний (до-region) рационал модуля восстановлен здесь дословно из
HEAD c70030a (последняя версия живого файла ДО посадки байт-копией
region-сиблинга, которая заместила этот докстринг самоссылочной шапкой
-- находка координатора 2026-08-19, форма t-533, см. секцию "Рационал
ДО region-aware версии" ниже).

БАЗА: буквальная копия ДО-РЕГИОННОЙ версии tools/mechanism_gate.py
(mechanism_paths, find_missing, parse_axes, resolve_lead_binding/
lead_family/build_role_ladder/_resolve_ladder_rank/tier_declared_ok --
ВСЯ D-0099 лестница рангов, decide/decide_full/main) -- см. секцию
"Рационал ДО region-aware версии" ниже за полным
происхождением каждого правила (D-0055/D-0072/D-0093/D-0099), здесь не
повторяется. ЕДИНСТВЕННОЕ отличие по существу: региона-осведомлённая
фильтрация того, ЧТО СЧИТАЕТСЯ СОВПАДЕНИЕМ SKIP_RE/TIER_LINE_RE, скоуп
Ф7(б) решения Lead 08-19 (docs/tasks/2026-08-19_scanner-party2-spec.md).

НАХОДКА (родительская спека md_regions, §13 п.3): "mechanism_gate
(остаточная дыра «строка отказа внутри фенса»)" -- SKIP_RE/TIER_LINE_RE
ДО-региональной версии УЖЕ заякорены (^…$/MULTILINE, D-0093) против ИНЛАЙН-цитаты
синтаксиса посреди прозы одной строки -- но якорь НЕ проверяет, лежит ли
ЦЕЛАЯ строка внутри тройного backtick-фенса или markdown-цитаты `>` (обе
формы дают "отдельную строку" с точки зрения ^…$/MULTILINE ничуть не хуже
настоящей декларации). Пример: коммит-сообщение, ЦИТИРУЮЩЕЕ пример
синтаксиса отказа целой строкой внутри тройного backtick-блока (типичная
форма -- документация/PR-описание, показывающее читателю "как выглядит
skip"), СЕГОДНЯ гасит гейт целиком -- ложный пропуск проверки правила
10(б), класс SIBLING_MAP :496-510 применённый к commit-msg-гейту вместо
диспатч-гейта.

ПОЛИТИКА (E, скоуп Ф7(б) решения Lead 08-19, буквально из спеки): SKIP_RE
И TIER_LINE_RE (см. их определения ниже) -- совпадение, ЧЬЯ СОБСТВЕННАЯ
позиция лежит в fenced ИЛИ blockquote регионе commit-сообщения, НЕ
засчитывается (фильтруется ДО применения к вердикту decide()/
decide_full()). ГЕЙТ FAIL-CLOSED -- АСИММЕТРИЯ С dispatch_gate_md
ОСОЗНАННАЯ (задокументировано явно, как решение Ф1(а) требует):
dispatch_gate -- БЛОКИРУЮЩИЙ гейт, региона-фильтр там ТОЛЬКО снимает блок
(exit 2 -> exit 0 + WARN), никогда не добавляет. mechanism_gate -- ТОЖЕ
блокирующий, но фильтр здесь работает В ПРОТИВОПОЛОЖНУЮ СТОРОНУ: он
делает гейт СТРОЖЕ (цитируемая/фенсированная skip-строка или
tier-строка БОЛЬШЕ НЕ засчитывается как легитимная декларация, коммит,
который раньше молча проходил из-за цитаты, теперь ТРЕБУЕТ настоящей
незацитированной декларации) -- это ПРЯМОЕ следствие того, что фильтр
применяется К ВХОДУ ОТКАЗА (skip/tier), а не к входу БЛОКА: убрать
ложный "отказ" из рассмотрения -- то же самое, что ПРИБАВИТЬ строгости
вердикту. Оба гейта одинаково "региона-фильтр меняет строгость только в
БЕЗОПАСНУЮ сторону" -- для WARN-only dispatch_gate безопасная сторона
"снять блок пореже", для fail-closed mechanism_gate безопасная сторона
"принять декларацию пореже" -- то же самое направление осторожности,
выраженное в противоположных экzit-code эффектах, не противоречие.

ALL-MUST-PASS СЧИТАЕТ ТОЛЬКО НЕЦИТИРОВАННЫЕ TIER-СТРОКИ:
_region_filtered_tier_declarations() -- НОВЫЙ region-aware аналог
find_tier_declarations() -- возвращает ТОЛЬКО значения строк, чья
позиция -- прoза; decide_full()'s "ALL must pass" (t-278 п.5, см.
"Рационал ДО region-aware версии" ниже) применяется к ЭТОМУ
отфильтрованному списку. find_tier_declarations() (публичная) САМА
НЕ ТРОГАЕТСЯ -- региона-блинд, байт-в-байт (используется прямыми
вызовами батареи/равенства).

ОСЕВЫЕ СТРОКИ find_missing() -- ЯВНО НЕ ФИЛЬТРУЮТСЯ (Ф7 решения Lead
08-19, ОТЛОЖЕНО ДО ЗАМЕРА ЖИВОГО ЛОГА, R8f): "ось N: <вердикт>" внутри
фенса/цитаты СЧИТАЕТСЯ так же, как в прозе -- find_missing() этого файла
байт-в-байт копия ДО-региональной функции, region ей НЕ передаётся
вообще. Это
СОЗНАТЕЛЬНЫЙ НЕ-ЦЕЛЬ этой задачи, не забытая симметрия -- решение
координатора отложило этот скоуп до отдельного замера (детерминированный
скрипт, R8f, "при посадке").

BLOCK_EXTRA НЕ СКАНИРУЕТСЯ (Ф8 решения Lead 08-19): scan() вызывается
ТОЛЬКО на `msg` (текст сообщения коммита) -- НИКОГДА на `block_extra`
(git-дифф docs/DECISIONS_FULL.md). block_extra остаётся сырым текстом
диффа, участвующим ТОЛЬКО в find_missing(msg + "\\n" + block_extra, axes)
(осевые строки, НЕ фильтруемые region'ом вообще, см. выше) -- у diff-
текста нет осмысленной markdown-семантики "цитата/фенс" в том смысле, в
котором md_regions её парсит (унифицированный diff-формат — не markdown
статья), сканировать его region-сканером было бы категорийной ошибкой.

ПОРЯДОК ВЕТОК decide() НЕ МЕНЯЕТСЯ (буквально из спеки): hits -> merging
-> skip -> fail-closed (карта/оси) -> (decide_full) tier. Меняется ТОЛЬКО
ЧТО СЧИТАЕТСЯ СОВПАДЕНИЕМ SKIP_RE/TIER_LINE_RE внутри уже существующих
веток -- ни одна ветка не переставлена, не добавлена, не удалена.

И-1 (Rule #1, ленивость): scan(msg) вызывается НЕ БОЛЕЕ ОДНОГО РАЗА за
вызов decide()/decide_full() (общий _maybe_scan() -- ОДИН расчёт,
переиспользуемый И для skip-проверки, И для tier-проверки внутри ОДНОГО
decide_full()), И ТОЛЬКО когда (а) коммит реально трогает механизменные
пути И не мерж (E7 -- на любом другом коммите 0 вызовов, ветки
hits/merging возвращают РАНЬШЕ, чем _maybe_scan успевает решить звать
scan), (б) сообщение несёт дешёвый маркер-намёк (литерал "оси" ИЛИ
"tier", регистронезависимо -- домен-специфичный аналог "owns" в узле D),
И (в) сообщение несёт хотя бы один из символов "`>~" (без них
md_regions.scan() детерминированно дал бы "весь текст -- проза", вызов
был бы потрачен впустую).

И-0 (ЛЮБОЙ отказ md_regions -- отсутствующий модуль/исключение scan()/
degraded=True): region-фильтр становится НО-ОП -- SKIP_RE.search(msg) и
find_tier_declarations(msg) (region-БЛИНД версии) дают РОВНО те же
булевы/списочные ответы, что и ДО-региональная версия. Это означает:
если ТОЛЬКО цитируемый skip существует (E8, "цитированный skip снова
глушит -- объявленный фоллбек"), И-0 откатывает ЭТОТ ФАЙЛ к ПРЕЖНЕМУ
(ДО-региональному) поведению -- гейт СНОВА молчит на цитируемом skip
(тот же остаточный баг, что ДО-региональная версия несла) -- НЕ новый
путь кода, тот же цикл с region-веткой, ставшей мёртвой (тот же
принцип, что owns_gate.py/negative_lint.py).

--- Рационал ДО region-aware версии (восстановлено дословно из HEAD
c70030a, последняя правка живого файла ДО посадки байт-копией
region-сиблинга 2026-08-19, форма t-533) -------------------------------

Вызывается commit-msg-хуком (.githooks/commit-msg) с путём к файлу
сообщения коммита. Логика (полностью в чистой decide(), тестируемой
без git):

1. Staged-пути не задевают механизмные префиксы -> гейт молчит.
2. Merge-коммит (MERGE_HEAD существует) -> гейт молчит: слитые коммиты
   уже проходили его поодиночке; блокировать автосообщение мержа --
   ложное срабатывание, приучающее к --no-verify (ревью critic, F-C).
3. Строка отказа «оси: не-механизм (<причина>)» действует ТОЛЬКО из
   сообщения коммита -- это письменное заявление коммиттера, аналог
   dispatch_skipped. В диффе она не ищется: текст решения, цитирующий
   синтаксис отказа, обходил бы гейт (ревью critic, F-A -- блокер).
   Внутри самого сообщения строка действует ТОЛЬКО как ОТДЕЛЬНАЯ
   строка (якорь ^…$ с MULTILINE, допустим отступ пробелами) -- иначе
   инлайн-цитата синтаксиса посреди прозы коммит-сообщения глушила бы
   гейт целиком (полигон Dog, D-0093); якорь симметричен уже
   заякоренному TIER_LINE_RE ниже.
4. Осевой блок -- строки «ось N: <вердикт>» для КАЖДОЙ оси текущей
   docs/SIBLING_MAP.md -- ищется в сообщении коммита ПЛЮС в staged-диффе
   ОДНОГО файла docs/DECISIONS_FULL.md (канонический дом ответов
   правила 10). Весь дифф не сканируется: посторонний staged-контент
   с буквальными «ось N:» закрывал бы оси фиктивно (ревью critic, F-B).
   Число и номера осей читаются из карты при каждом запуске -- карта
   растёт и меняется (D-0048), гейт следует за ней.
5. Карта не читается / ноль осей -> fail-closed (F-7: молчаливый
   пропуск проверки неотличим от её прохождения).
6. D-0065 (F-25): невод расширен на известные дома механизмов
   (ARCHITECTURE.md, BOOT.md, gateway/PI_HARNESS.md) и самозащиту
   enforcement-цепочки (этот файл, .githooks/ -- правка гейта не должна
   обходить гейт, родство F-15). Широкие каталоги (tools/, gateway/)
   сознательно вне невода -- записанный выбор D-0055: ложные
   срабатывания приучают к --no-verify.
7. D-0072 (механизм 5, t-068): на ветке «механизм» (осевой блок
   пройден) сообщение коммита обязано нести ОТДЕЛЬНУЮ строку
   «tier: <значение>» -- самодекларация фактического яруса
   коммиттера, аналог dispatch_skipped. Ожидаемое значение --
   привязка roles.lead из delegation.config.yaml в корне репозитория;
   файла или ключа roles.lead нет -> дефолт семейства "fable"
   (субскрипционный дефолт Lead). Декларация принимается точным
   совпадением с моделью привязки ИЛИ вхождением её ярусного семейства
   (fable/opus/sonnet/haiku, по подстроке) -- для не-Claude привязки
   семейства нет, годится только точное совпадение model id. С 2026-08-04
   (D-0099) декларация СЕМЕЙСТВА, чей ранг СТРОГО ВЫШЕ ранга привязки
   (fable>opus>sonnet>haiku), тоже принимается -- переходный коммит
   перепривязки Lead коммитится ещё сессией старого, более высокого
   яруса, тот ярус выше привязки суть полный Lead (см. tier_declared_ok).
   D-0099 п.6 (тем же днём): ДОПОЛНИТЕЛЬНО источником рангов служит
   ПРОВЕРЕННАЯ ЛЕСТНИЦА КОНФИГА -- roles.{scout,builder,critic,lead,
   reserve} (каждая привязка прошла входной экзамен onboarding'а, порядок
   -- функциональная иерархия координации, reserve -- опциональная ступень
   строго выше lead, представление Fable-резерва); декларация резолвится
   в ранг лестницы точным id ИЛИ (для Claude-моделей, при единственной
   ступени того семейства) family-матчем, принимается при ранге >= ранга
   lead -- работает и для НЕ-Claude лестниц, где семейственная эвристика
   выше молчит (см. build_role_ladder/_resolve_ladder_rank). Обе ветки
   (семейственная и лестничная) сосуществуют и только РАСШИРЯЮТ множество
   принимаемых деклараций, никогда не сужая его.
   Skip-ветка («не-механизм») и merge-коммиты строку tier не требуют
   (тот же невод исключений, что и у осевого блока). Гейт НЕ проверяет
   истинность декларации -- двухслойный enforcement (D-0063): код
   гарантирует форму и присутствие строки, правдивость декларации
   судит калибровка по транскриптам ярусом выше (тот же детектор,
   что и D-0042/D-0056).
"""
from __future__ import annotations

import bisect
import re
import subprocess
import sys
from pathlib import Path

import yaml

# Оба потока: тексты отказа гейта -- кириллица и в stdout, и в stderr;
# без reconfigure Windows-консоль искажает их (класс найден в AO3-твине,
# их задача e4-impact-selection 2026-07-14; ось 1 SIBLING_MAP -- фикс
# парный). errors="replace" (порт AO3 «Мелкое хозяйство» п.1,
# 2026-07-18): голый encoding="utf-8" оставлял errors="strict" --
# replace убирает последний шанс ValueError на повторной кодировке без
# потери диагностируемости.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "docs" / "SIBLING_MAP.md"
DECISIONS_FULL = "docs/DECISIONS_FULL.md"
CONFIG_PATH = REPO / "delegation.config.yaml"

try:
    from tools.md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE  # package-style
except ImportError:
    try:
        from md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE  # sibling-module fallback
    except ImportError:
        scan = None
        KIND_FENCED = "fenced"
        KIND_BLOCKQUOTE = "blockquote"

LEAD_FAMILIES = ("fable", "opus", "sonnet", "haiku")
TIER_LINE_RE = re.compile(r"^\s*tier\s*:\s*(\S.*?)\s*$", re.IGNORECASE | re.MULTILINE)

MECHANISM_PREFIXES = (
    "CLAUDE.md",
    "DECISIONS.md",
    "docs/DECISIONS_FULL.md",
    "docs/SIBLING_MAP.md",
    "PROCESS/",
    ".claude/agents/",
    ".claude/skills/",
    # D-0065: дома механизмов вне первоначального невода + самозащита
    "ARCHITECTURE.md",
    "ARCHITECTURE_BOOT.md",  # D-0067: boot-ядро несёт механизменный текст
    "BOOT.md",
    "gateway/PI_HARNESS.md",
    "tools/mechanism_gate.py",
    ".githooks/",
    # t-027 (critic B2): хуки харнесса = обязанности будущих сессий.
    ".claude/settings.json",
    # F-56 (2026-08-10, критерий принят от AO3): невод расширен на САМИ
    # гейты/валидаторы, на которые проводка (.claude/settings.json,
    # .githooks/) ПОКАЗЫВАЕТ -- правка любого из них раньше проходила
    # commit-msg без осевого блока. Критерий: в неводе -- то, чей отказ
    # или пропуск МЕНЯЕТ, что обязано случиться (код стоит на пути
    # исполнения вызова/коммита/сессии); генераторы/свиперы/измерители
    # остаются вне. Поимённо, не каталогом tools/ (широкий каталог
    # по-прежнему вне невода сознательно, п.6 выше, D-0055).
    "tools/session_context.py",      # SessionStart hook
    "tools/dispatch_gate.py",        # PreToolUse Task|Agent hook
    "tools/critic_snapshot.py",      # PreToolUse Task|Agent hook
    "tools/owns_gate.py",            # PreToolUse Task|Agent hook
    "tools/hygiene_gate.py",         # PreToolUse Bash|PowerShell hook
    "tools/claim_control_gate.py",   # PreToolUse Edit|Write hook
    "tools/dod_track.py",            # PostToolUse hook
    "tools/journal_echo.py",         # PostToolUse hook
    "tools/search_control_gate.py",  # PostToolUse hook
    "tools/negative_lint.py",        # PostToolUse Task|Agent hook
    # Р8(б) спеки md_regions (2026-08-19, F-48): общий сканер регионов
    # входит в невод ходом посадки ПЕРВОГО потребителя (партия 1:
    # negative_lint + claim_control_gate) -- его отказ меняет вердикты
    # двух сторожей на пути исполнения.
    "tools/md_regions.py",           # region scanner (потребители: 2 сторожа)
    "tools/dod_gate.py",             # SubagentStop hook
    "tools/main_gate.py",            # Stop hook
    "tools/journal_validator.py",    # .githooks/pre-commit
    "tools/escape_check.py",         # .githooks/pre-commit
    "tools/enforcement_probe.py",    # .githooks/pre-commit
    # Phase 5 W1 (2026-08-18, класс F-56 «защищена декларация, не
    # связанное»): docs/FINDINGS.md с посадкой правила ретирования
    # несёт ОБЯЗАННОСТИ будущих сессий (шапочные правила реестра +
    # D-0100 поля + долг ретирования) -- правка его текста без осевого
    # блока проходила commit-msg молча. Найдено дизайнером t-487/
    # критиком t-488. docs/RULE_COVERAGE.md несёт обязанность
    # поддержания «строка тем же коммитом» (его шапка) и меняет картину
    # сторожей; протухшая строка там = F-41.
    "docs/FINDINGS.md",
    "docs/RULE_COVERAGE.md",
    # 2026-08-20 (спека docs/tasks/2026-08-20_rule-coverage-bodies-spec.md,
    # решение Р7): тела карты docs/rule_coverage/*.md несут ту же
    # обязанность будущих сессий, что и сама карта -- правка тела без
    # осевого блока проходила бы commit-msg молча, ровно класс F-56.
    "docs/rule_coverage/",
    # tools/wiring_check.py -- найдено аудитом (T1): subprocess-вызывается
    # tools/enforcement_probe.py на pre-commit, ПЛЮС импортируется
    # tools/session_context.py внутри wiring_lines() для SessionStart --
    # двойная проводка на execution path.
    "tools/wiring_check.py",
    # t-382 (2026-08-10, критик опроверг билдерский вердикт): AST-
    # замыкание живой проводки нашло ДВА модуля, достигнутых ТРАНЗИТИВНЫМ
    # импортом из уже-механизменных хуков -- сам факт импорта делает их
    # отказ/порчу способной изменить, что обязано случиться. Отдельная,
    # до сих пор открытая находка (не решается этой правкой): собственный
    # докстринг tier_echo.py по-прежнему называет его "SubagentStop-хук"
    # -- но фактическая проводка идёт ЧЕРЕЗ импорт из journal_echo.py
    # (PostToolUse), не через собственную регистрацию в .claude/settings.json.
    "tools/tier_echo.py",
    # tools/session_context.py импортирует preflight_quota -- падение
    # импорта валит session_context на старте КАЖДОЙ сессии.
    "tools/preflight_quota.py",
    # Р12(A) спеки W4 (2026-08-19): после W4 пре-пасс -- носитель
    # ОБЯЗАННОСТИ ЧТЕНИЯ чек-листа калибровки (вердикты живости решают,
    # что читается; skip-каунтер и сторож -- машинные duty). Критерий
    # F-56: его отказ/порча меняет, что обязано случиться на прогоне.
    "tools/calibration_prepass.py",  # пре-пасс калибровки (W4, Р12)
)

AXIS_HEADING_RE = re.compile(r"^##\s+Ось\s+(\d+)", re.MULTILINE)
# Якорь строки (D-0093, полигон Dog): без ^…$/MULTILINE фраза матчилась
# .search()'ом по ЛЮБОМУ месту сообщения -- инлайн-цитата синтаксиса
# отказа посреди прозы глушила бы гейт целиком. Симметрично уже
# заякоренному TIER_LINE_RE выше.
SKIP_RE = re.compile(r"^\s*оси\s*:\s*не-механизм\s*\(", re.IGNORECASE | re.MULTILINE)

# --- region-предикат (узел E, НОВОЕ) ----------------------------------

# Fail-closed асимметрия (см. докстринг модуля "ПОЛИТИКА"): ТОЛЬКО fenced
# и blockquote исключают SKIP_RE/TIER_LINE_RE совпадение -- inline_code
# структурно не может дать совпадение этих ДВУХ ЯКОРЕННЫХ-НА-ВСЮ-СТРОКУ
# regex'ов (backtick, будь то открывающий или одиночный внутри слова, не
# может стоять на позиции, где ^\s*(оси|tier) ожидает буквальный текст
# без ведущего backtick) -- поэтому KIND_INLINE_CODE даже не
# импортируется, класс структурно неприменим здесь (в отличие от узла D,
# где инлайн-код на marker-позиции ЯВНО достижим).
_EXCLUDED_KINDS = ("fenced", "blockquote")

_REGION_MARKER_CHARS = ("`", ">", "~")
_MARKER_HINT_RE = re.compile(r"оси|tier", re.IGNORECASE)


def _has_region_marker_chars(text: str) -> bool:
    return any(ch in text for ch in _REGION_MARKER_CHARS)


def _safe_scan(text: str):
    """И-0: None при отсутствии модуля / исключении scan() / degraded=True
    -- region-фильтр становится но-оп (см. докстринг модуля "И-0")."""
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
    """См. докстринг модуля "ПОЛИТИКА": fenced (в т.ч. незакрытый -- нет
    приоритетного правила "unterminated -> prose", тот же fail-closed
    выбор, что и узел D: содержимое неопределённо закрытого фенса НЕ
    получает статус "прoза") > blockquote > prose."""
    if region is None:
        return "prose"
    if KIND_FENCED in region.kinds:
        return "fenced"
    if KIND_BLOCKQUOTE in region.kinds:
        return "blockquote"
    return "prose"


def _is_prose_position(scan_result, offset: int) -> bool:
    if scan_result is None:
        return True  # И-0: но-оп
    return _classify(_region_at(scan_result, offset)) not in _EXCLUDED_KINDS


def parse_axes(map_text: str) -> list[int]:
    """Номера осей из заголовков карты; порядок и разрывы нумерации не важны."""
    return [int(n) for n in AXIS_HEADING_RE.findall(map_text)]


def _matches(path: str, pref: str) -> bool:
    # Граница префикса (F-D): каталоги -- по startswith, файлы -- точно
    # (CLAUDE.md.bak не механизмный путь).
    if pref.endswith("/"):
        return path.startswith(pref)
    return path == pref


def mechanism_paths(staged: list[str]) -> list[str]:
    return [p for p in staged
            if any(_matches(p, pref) for pref in MECHANISM_PREFIXES)]


def find_missing(text: str, axes: list[int]) -> list[int]:
    # Ф7 решения Lead 08-19: осевые строки НЕ фильтруются region'ом --
    # НЕ ТРОНУТО (см. докстринг модуля "ОСЕВЫЕ СТРОКИ").
    return [n for n in axes
            if not re.search(rf"ось\s+{n}\s*:", text, re.IGNORECASE)]


def resolve_lead_binding(config_text: str | None) -> str:
    """Модель, привязанная к roles.lead в delegation.config.yaml. Файл
    отсутствует, ключ roles.lead отсутствует, либо YAML не парсится ->
    дефолт семейства "fable" (субскрипционный дефолт Lead, D-0072) --
    консервативный (fail-closed) выбор: требует явной декларации от
    кого угодно ниже top-tier. Самодекларация НЕ проверяется на
    истинность здесь (см. tier_declared_ok) -- двухслойный enforcement
    D-0063: код гарантирует форму, правду судит калибровка по
    транскриптам ярусом выше."""
    if not config_text:
        return "fable"
    try:
        data = yaml.safe_load(config_text) or {}
    except yaml.YAMLError:
        return "fable"
    lead = (data.get("roles") or {}).get("lead") or {}
    model = ((lead.get("subscription") or {}).get("model")
             or (lead.get("api") or {}).get("model"))
    return model or "fable"


def lead_family(binding: str) -> str | None:
    """Ярусное семейство привязанной модели по подстроке (fable/opus/
    sonnet/haiku); None -- семейство не распознано (не-Claude привязка),
    тогда годится только точное совпадение model id."""
    low = binding.lower()
    for fam in LEAD_FAMILIES:
        if fam in low:
            return fam
    return None


def find_tier_declarations(msg: str) -> list[str]:
    """Region-БЛИНД, БАЙТ-В-БАЙТ функция ДО-региональной версии -- см.
    докстринг модуля "ALL-MUST-PASS СЧИТАЕТ ТОЛЬКО НЕЦИТИРОВАННЫЕ
    TIER-СТРОКИ": decide_full() region-aware отбор живёт в
    _region_filtered_tier_declarations() ниже, эта функция НЕ ТРОНУТА
    (сохранена ради прямых вызовов батареи и обратной совместимости,
    тот же принцип, что find_missing()).

    t-278 п.5 (критик t-068: find_tier_declaration матчил ТОЛЬКО первую
    строку «tier:» через .search() -- недостаточно: несколько
    механизмов в одном коммите МОГУТ нести отдельные tier-строки).
    РЕШЕНИЕ ПО СЕМАНТИКЕ: безопасная (fail-closed) семантика -- каждая
    найденная строка ДОЛЖНА пройти проверку (см. tier_declared_ok в
    decide_full ниже); отказ, если хоть ОДНА строка не совпадает с
    привязкой, даже если другая (например, настоящая, более поздняя)
    строка совпадает. Альтернатива ("проходит, если совпадает ХОТЯ БЫ
    ОДНА") была отклонена: при НЕСКОЛЬКИХ tier-строках в одном
    сообщении она позволила бы одной подставной/цитированной строке
    "tier: fable" маскировать РЕАЛЬНОЕ несовпадающее значение где-то
    ещё в том же сообщении."""
    return [m.strip() for m in TIER_LINE_RE.findall(msg)]


def find_tier_declaration(msg: str) -> str | None:
    """Обратная совместимость/удобство: значение ПЕРВОЙ строки «tier:
    <значение>» (см. find_tier_declarations() за полную семантику всех
    строк, которую использует decide_full())."""
    declarations = find_tier_declarations(msg)
    return declarations[0] if declarations else None


def _region_filtered_tier_declarations(msg: str, scan_result) -> list[str]:
    """НОВОЕ (узел E): TIER_LINE_RE-совпадение считается ТОЛЬКО когда его
    собственная позиция -- прoза (Ф7б) -- см. докстринг модуля
    "ALL-MUST-PASS". scan_result is None -- И-0, идентично find_tier_
    declarations() (каждое совпадение считается)."""
    result = []
    for match in TIER_LINE_RE.finditer(msg):
        if not _is_prose_position(scan_result, match.start()):
            continue
        result.append(match.group(1).strip())
    return result


# D-0099 п.6 (2026-08-04): онбординг-лестница -- каждая привязанная модель
# прошла входной экзамен (exam.mandatory), roles.{scout,builder,critic,
# lead,reserve} в delegation.config.yaml И ЕСТЬ валидированная лестница
# деплоя, в этом фиксированном функциональном порядке. reserve (Fable-
# резерв) -- единственная ступень СТРОГО ВЫШЕ lead; roles.judge/roles.analyst
# не координационные роли и в лестницу не входят. roles.designer ТОЖЕ не
# ступень лестницы -- designer стоячая функция того же яруса, что critic,
# но НЕ координационная роль в смысле этой иерархии; как и judge/analyst,
# её ключ просто не входит в ROLE_RANKS.
ROLE_RANKS = {"scout": 0, "builder": 1, "critic": 2, "lead": 3, "reserve": 4}


def _resolve_role_model(role_data) -> str | None:
    """Модель ОДНОЙ роли по той же subscription/api-приоритетности, что
    и resolve_lead_binding() -- но БЕЗ дефолта "fable": роль без модели
    просто не даёт ступени лестницы, это не то же самое, что привязка
    Lead конкретно (у которой отсутствие -- осмысленный субскрипционный
    дефолт, D-0072)."""
    if not isinstance(role_data, dict):
        return None
    model = ((role_data.get("subscription") or {}).get("model")
             or (role_data.get("api") or {}).get("model"))
    return model or None


def build_role_ladder(config_text: str | None) -> list[tuple[int, str]]:
    """D-0099 п.6: [(rank, model_id)] по ROLE_RANKS, в фиксированном
    порядке (scout=0 ... reserve=4) -- построена из roles.* в
    config_text, роль без сконфигурированной модели ступени не
    порождает. Пустой/битый/отсутствующий config_text -> пустая лестница
    (fail-open к существующей family-эвристике tier_declared_ok)."""
    if not config_text:
        return []
    try:
        data = yaml.safe_load(config_text) or {}
    except yaml.YAMLError:
        return []
    roles = data.get("roles")
    if not isinstance(roles, dict):
        return []
    ladder = []
    for role_name, rank in ROLE_RANKS.items():
        model = _resolve_role_model(roles.get(role_name))
        if model:
            ladder.append((rank, model))
    return ladder


def _resolve_ladder_rank(declared: str, config_text: str | None) -> int | None:
    """[до region-aware версии 2026-08-19 -- функция region'ом не
    затронута, докстринг перенесён дословно из HEAD c70030a] D-0099
    п.6: резолюция декларации в ранг лестницы.

    B3 (пересдача, критик-блокер): лестничный путь легален ТОЛЬКО когда в
    лестнице реально ЕСТЬ ступень "lead" (roles.lead сконфигурирована с
    моделью) -- без неё нет опорного ранга, относительно которого вообще
    можно сказать "выше/на уровне lead"; пустая лестница ИЛИ лестница без
    ступени lead -> None безусловно, ни (а), ни (б) ниже не пробуются
    (edge (ii): roles.lead отсутствует, но reserve=opus сконфигурирован --
    "tier: opus" не резолвится лестницей вовсе, регресс-пин "выше fable
    ничего нет" из существующих (не-лестничных) веток держится и с
    конфигом, не только с config_text=None).

    (а) ТОЧНОЕ совпадение с model_id какой-то ступени резолвится в ранг --
        B4 (пересдача, критик-блокер): если ОДИН И ТОТ ЖЕ model_id стоит
        на НЕСКОЛЬКИХ ступенях (админ буквально продублировал модель), из
        всех точных совпадений берётся МАКСИМАЛЬНЫЙ ранг, не первый по
        порядку лестницы (работает и для не-Claude ступеней -- "tier:
        llama-3.3-70b-versatile" матчит не-Claude ступень lead точным id).
        П5(a) (батч мелочей после калибровки №6, D-0081, остаток
        критик-ревью t-350): family-strength guard (тот же, что уже
        стоял на ветке (б) ниже) теперь ПРИМЕНЯЕТСЯ И ЗДЕСЬ -- до этой
        правки точное id-совпадение обходило guard целиком (напр.
        `tier: claude-sonnet-5`, а не голое `tier: sonnet`, резолвился
        бы через reserve-ступень СЛАБЕЕ lead безо всякой проверки,
        симметрично уже закрытому B3 edge (i), но НЕ покрытому там,
        т.к. B3 edge (i) проверялся только на family-пути). Развилка
        решена Lead (см. CURRENT_CONTEXT.md, битва "family-strength
        guard на exact-id пути"): СРАВНИМЫЕ семейства (и ранг lead-
        ступени, и ранг ступени-кандидата резолвятся в непустое
        LEAD_FAMILIES-значение) -> guard активен, кандидат СЛАБЕЕ lead
        по ordinal -- отбрасывается; НЕРЕЗОЛВИМОЕ семейство СТУПЕНИ-
        КАНДИДАТА (lead_family(model_id) is None -- напр. не-Claude
        model_id, точно совпавший с declared) -> guard молчит, ДОВЕРИЕ
        ПОЗИЦИИ ЛЕСТНИЦЫ (конфиг = слово оператора: раз админ поставил
        именно этот id на эту ступень, сравнивать не с чем -- позиция
        авторитетна). Аналогично, если family lead-ступени НЕ резолвится
        (не-Claude lead) -- guard тоже молчит (сравнивать не с чем,
        та же логика, что уже была на ветке (б)).
    (б) иначе, когда declared -- Claude-модель (lead_family(declared) не
        None), family-матч РОВНО ОДНОЙ ступени лестницы того же семейства
        резолвится в её ранг -- АМБИГУИТЕТ (>=2 ступени того же семейства)
        НЕ резолвится этим путём вовсе (документированная развилка,
        спека п.6: "если такая ступень одна"). B3 (пересдача, критик-
        блокер, edge (i)): ДОПОЛНИТЕЛЬНО кандидат-ступень должна иметь
        family НЕ СЛАБЕЕ (по LEAD_FAMILIES ordinal, где индекс 0 -- самое
        сильное семейство "fable") family самой ступени lead -- иначе
        нонсенс-конфиг (напр. reserve сконфигурирован МОДЕЛЬЮ СЛАБЕЕ lead,
        хотя позиционно reserve выше) не должен молча наследовать
        позиционный ранг 4 через family-эвристику. Guard применяется
        ТОЛЬКО когда family lead-ступени резолвится (Claude lead); при
        не-Claude lead (family lead не определена) сравнивать не с чем --
        guard не блокирует (см. edge "reserve при не-Claude lead" -- уже
        принятый и покрытым тестами кейс).
    None -- лестница без ступени lead, или declared не резолвится ни (а),
    ни (б) (в т.ч. не-Claude declared без точного id-совпадения --
    family-путь для него не определён)."""
    ladder = build_role_ladder(config_text)
    lead_rank = ROLE_RANKS["lead"]
    lead_models = [model_id for rank, model_id in ladder if rank == lead_rank]
    if not lead_models:
        return None
    lead_model = lead_models[0]
    lead_fam = lead_family(lead_model)

    exact_matches = []
    for rank, model_id in ladder:
        if declared != model_id:
            continue
        cand_fam = lead_family(model_id)
        if lead_fam is not None and cand_fam is not None:
            if LEAD_FAMILIES.index(cand_fam) > LEAD_FAMILIES.index(lead_fam):
                continue
        exact_matches.append(rank)
    if exact_matches:
        return max(exact_matches)

    declared_fam = lead_family(declared)
    if declared_fam is None:
        return None
    candidates = []
    for rank, model_id in ladder:
        if lead_family(model_id) != declared_fam:
            continue
        if lead_fam is not None:
            cand_fam = lead_family(model_id)
            if LEAD_FAMILIES.index(cand_fam) > LEAD_FAMILIES.index(lead_fam):
                continue
        candidates.append(rank)
    if len(candidates) == 1:
        return candidates[0]
    return None


def tier_declared_ok(declared: str, binding: str, config_text: str | None = None) -> bool:
    """config_text (D-0099 п.6, опционально, дефолт None): онбординг-
    лестница -- строго ДОПОЛНЯЕТ существующие пути ниже, никогда их не
    сужает. Ветки 1-3 (точное совпадение с binding / вхождение её
    семейства / family строго выше ранга binding по LEAD_FAMILIES) --
    БЕЗ ИЗМЕНЕНИЙ. Не-Claude привязка (fam(binding) is None) БОЛЬШЕ НЕ
    обрывает функцию ранним return False -- ветки 1-3 просто молчат, но
    ЛЕСТНИЧНАЯ резолюция (шаг 4) всё равно выполняется."""
    if declared == binding:
        return True
    fam = lead_family(binding)
    if fam is not None:
        if fam in declared.lower():
            return True
        declared_fam = lead_family(declared)
        if declared_fam is not None and LEAD_FAMILIES.index(declared_fam) < LEAD_FAMILIES.index(fam):
            return True
    declared_rank = _resolve_ladder_rank(declared, config_text)
    if declared_rank is not None and declared_rank >= ROLE_RANKS["lead"]:
        return True
    return False


def _tier_queue_note() -> str:
    return ("механизменный коммит — Lead-tier работа: сессия на ярусе "
            "ниже привязки lead НЕ коммитит механизм сама, а кладёт его "
            "в Lead-очередь CURRENT_CONTEXT.md; сессия lead-яруса "
            "добавляет строку «tier: <своя модель>» (D-0072).")


def _maybe_scan(msg: str, staged: list[str], merging: bool):
    """И-1/E7: scan(msg) вызывается ТОЛЬКО когда (а) коммит реально трогает
    механизменные пути И не мерж, (б) сообщение несёт дешёвый маркер-намёк
    ("оси"/"tier"), (в) сообщение несёт хотя бы один из "`>~" -- см.
    докстринг модуля "И-1". Возвращает None (0 вызовов scan) во ВСЕХ
    остальных случаях."""
    hits = mechanism_paths(staged)
    if not hits or merging:
        return None
    if not _MARKER_HINT_RE.search(msg):
        return None
    if not _has_region_marker_chars(msg):
        return None
    return _safe_scan(msg)


def _skip_declared(msg: str, scan_result) -> bool:
    """SKIP_RE-совпадение засчитывается ТОЛЬКО когда его позиция -- прoза
    (Ф7б) -- см. докстринг модуля "ПОЛИТИКА". scan_result is None -- И-0,
    ПЕРВОЕ совпадение (если есть) сразу True -- байт-в-байт SKIP_RE.
    search(msg) ДО-региональной версии (см. докстринг модуля "И-0")."""
    for match in SKIP_RE.finditer(msg):
        if scan_result is None:
            return True
        if _is_prose_position(scan_result, match.start()):
            return True
    return False


def _decide_core(msg: str, block_extra: str, staged: list[str],
                  map_text: str | None, merging: bool, scan_result) -> tuple[int, str]:
    """Чистое ядро decide() -- порядок веток hits->merging->skip->
    fail-closed НЕ МЕНЯЕТСЯ (см. докстринг модуля "ПОРЯДОК ВЕТОК")."""
    hits = mechanism_paths(staged)
    if not hits:
        return 0, ""
    if merging:
        return 0, ""
    if _skip_declared(msg, scan_result):
        return 0, ""
    if map_text is None:
        return 1, (f"карта осей не найдена ({MAP_PATH}) — fail-closed, "
                   "коммит отклонён (D-0055)")
    axes = parse_axes(map_text)
    if not axes:
        return 1, ("в карте не найдено ни одной оси (## Ось N) — "
                   "fail-closed (D-0055)")
    missing = find_missing(msg + "\n" + block_extra, axes)
    if missing:
        return 1, ("коммит трогает механизмные файлы:\n  " + "\n  ".join(hits)
                   + "\nОсевой блок правила 10(б) неполон — нет вердикта по осям: "
                   + ", ".join(str(n) for n in missing)
                   + "\nДобавь «ось N: покрыта / в очередь / н-п <почему>» на "
                   "каждую ось карты (в сообщение коммита или в текст решения "
                   "docs/DECISIONS_FULL.md), либо явный отказ в СООБЩЕНИИ: "
                   "«оси: не-механизм (<причина>)» (D-0055).")
    return 0, ""


def decide(msg: str, block_extra: str, staged: list[str],
           map_text: str | None, merging: bool = False) -> tuple[int, str]:
    """Чистое решение гейта. block_extra — дифф docs/DECISIONS_FULL.md
    (НЕ сканируется region'ом, см. докстринг модуля "BLOCK_EXTRA")."""
    scan_result = _maybe_scan(msg, staged, merging)
    return _decide_core(msg, block_extra, staged, map_text, merging, scan_result)


def decide_full(msg: str, block_extra: str, staged: list[str],
                 map_text: str | None, config_text: str | None,
                 merging: bool = False) -> tuple[int, str]:
    """decide() плюс требование правила 7 (D-0072): строка tier на ветке
    «механизм». И-1: ОДИН _maybe_scan() на весь вызов, переиспользуемый
    И для skip-проверки (через _decide_core), И для tier-проверки ниже —
    см. докстринг модуля "И-1"."""
    scan_result = _maybe_scan(msg, staged, merging)
    code, reason = _decide_core(msg, block_extra, staged, map_text, merging, scan_result)
    if code:
        return code, reason
    hits = mechanism_paths(staged)
    if not hits or merging or _skip_declared(msg, scan_result):
        return 0, ""
    binding = resolve_lead_binding(config_text)
    # НОВОЕ (узел E): region-aware отбор -- см. докстринг модуля
    # "ALL-MUST-PASS СЧИТАЕТ ТОЛЬКО НЕЦИТИРОВАННЫЕ TIER-СТРОКИ".
    declared_list = _region_filtered_tier_declarations(msg, scan_result)
    if not declared_list:
        return 1, ("коммит трогает механизмные файлы:\n  " + "\n  ".join(hits)
                    + "\nНет строки «tier: <значение>» (привязка lead: "
                    + binding + ") — " + _tier_queue_note())
    bad = [d for d in declared_list if not tier_declared_ok(d, binding, config_text)]
    if bad:
        return 1, ("коммит трогает механизмные файлы:\n  " + "\n  ".join(hits)
                    + "\nЯрус не lead: «tier: " + bad[0]
                    + "» не совпадает с привязкой (" + binding + ") — "
                    + _tier_queue_note())
    return 0, ""


def _git(*args: str) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.stdout or ""


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("mechanism_gate: нужен путь к файлу сообщения коммита", file=sys.stderr)
        return 1
    staged = _git("diff", "--cached", "--name-only").splitlines()
    merge_head = _git("rev-parse", "--git-path", "MERGE_HEAD").strip()
    merging = bool(merge_head) and Path(merge_head).exists()
    msg = Path(argv[0]).read_text(encoding="utf-8", errors="replace")
    block_extra = _git("diff", "--cached", "--", DECISIONS_FULL)
    map_text = (MAP_PATH.read_text(encoding="utf-8", errors="replace")
                if MAP_PATH.exists() else None)
    config_text = (CONFIG_PATH.read_text(encoding="utf-8", errors="replace")
                   if CONFIG_PATH.exists() else None)
    code, reason = decide_full(msg, block_extra, staged, map_text,
                               config_text, merging)
    if code:
        print("mechanism_gate: " + reason, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
