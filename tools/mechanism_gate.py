"""Гейт правила 10(б) — D-0055: коммит механизмных файлов несёт осевой блок.

Вызывается commit-msg-хуком (.githooks/commit-msg) с путём к файлу
сообщения коммита. Логика (полностью в чистой decide(), тестируемой
без git):

1. Staged-пути не задевают механизмные префиксы → гейт молчит.
2. Merge-коммит (MERGE_HEAD существует) → гейт молчит: слитые коммиты
   уже проходили его поодиночке; блокировать автосообщение мержа —
   ложное срабатывание, приучающее к --no-verify (ревью critic, F-C).
3. Строка отказа «оси: не-механизм (<причина>)» действует ТОЛЬКО из
   сообщения коммита — это письменное заявление коммиттера, аналог
   dispatch_skipped. В диффе она не ищется: текст решения, цитирующий
   синтаксис отказа, обходил бы гейт (ревью critic, F-A — блокер).
   Внутри самого сообщения строка действует ТОЛЬКО как ОТДЕЛЬНАЯ
   строка (якорь ^…$ с MULTILINE, допустим отступ пробелами) — иначе
   инлайн-цитата синтаксиса посреди прозы коммит-сообщения глушила бы
   гейт целиком (полигон Dog, D-0093); якорь симметричен уже
   заякоренному TIER_LINE_RE ниже.
4. Осевой блок — строки «ось N: <вердикт>» для КАЖДОЙ оси текущей
   docs/SIBLING_MAP.md — ищется в сообщении коммита ПЛЮС в staged-диффе
   ОДНОГО файла docs/DECISIONS_FULL.md (канонический дом ответов
   правила 10). Весь дифф не сканируется: посторонний staged-контент
   с буквальными «ось N:» закрывал бы оси фиктивно (ревью critic, F-B).
   Число и номера осей читаются из карты при каждом запуске — карта
   растёт и меняется (D-0048), гейт следует за ней.
5. Карта не читается / ноль осей → fail-closed (F-7: молчаливый
   пропуск проверки неотличим от её прохождения).
6. D-0065 (F-25): невод расширен на известные дома механизмов
   (ARCHITECTURE.md, BOOT.md, gateway/PI_HARNESS.md) и самозащиту
   enforcement-цепочки (этот файл, .githooks/ — правка гейта не должна
   обходить гейт, родство F-15). Широкие каталоги (tools/, gateway/)
   сознательно вне невода — записанный выбор D-0055: ложные
   срабатывания приучают к --no-verify.
7. D-0072 (механизм 5, t-068): на ветке «механизм» (осевой блок
   пройден) сообщение коммита обязано нести ОТДЕЛЬНУЮ строку
   «tier: <значение>» — самодекларация фактического яруса
   коммиттера, аналог dispatch_skipped. Ожидаемое значение —
   привязка roles.lead из delegation.config.yaml в корне репозитория;
   файла или ключа roles.lead нет → дефолт семейства "fable"
   (субскрипционный дефолт Lead). Декларация принимается точным
   совпадением с моделью привязки ИЛИ вхождением её ярусного семейства
   (fable/opus/sonnet/haiku, по подстроке) — для не-Claude привязки
   семейства нет, годится только точное совпадение model id. С 2026-08-04
   (D-0099) декларация СЕМЕЙСТВА, чей ранг СТРОГО ВЫШЕ ранга привязки
   (fable>opus>sonnet>haiku), тоже принимается — переходный коммит
   перепривязки Lead коммитится ещё сессией старого, более высокого
   яруса, тот ярус выше привязки суть полный Lead (см. tier_declared_ok).
   D-0099 п.6 (тем же днём): ДОПОЛНИТЕЛЬНО источником рангов служит
   ПРОВЕРЕННАЯ ЛЕСТНИЦА КОНФИГА — roles.{scout,builder,critic,lead,
   reserve} (каждая привязка прошла входной экзамен onboarding'а, порядок
   — функциональная иерархия координации, reserve — опциональная ступень
   строго выше lead, представление Fable-резерва); декларация резолвится
   в ранг лестницы точным id ИЛИ (для Claude-моделей, при единственной
   ступени того семейства) family-матчем, принимается при ранге >= ранга
   lead — работает и для НЕ-Claude лестниц, где семейственная эвристика
   выше молчит (см. build_role_ladder/_resolve_ladder_rank). Обе ветки
   (семейственная и лестничная) сосуществуют и только РАСШИРЯЮТ множество
   принимаемых деклараций, никогда не сужая его.
   Skip-ветка («не-механизм») и merge-коммиты строку tier не требуют
   (тот же невод исключений, что и у осевого блока). Гейт НЕ проверяет
   истинность декларации — двухслойный enforcement (D-0063): код
   гарантирует форму и присутствие строки, правдивость декларации
   судит калибровка по транскриптам ярусом выше (тот же детектор,
   что и D-0042/D-0056).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

# Оба потока: тексты отказа гейта — кириллица и в stdout, и в stderr;
# без reconfigure Windows-консоль искажает их (класс найден в AO3-твине,
# их задача e4-impact-selection 2026-07-14; ось 1 SIBLING_MAP — фикс парный).
# errors="replace" (порт AO3 «Мелкое хозяйство» п.1, 2026-07-18): голый
# encoding="utf-8" оставлял errors="strict" — replace убирает последний
# шанс ValueError на повторной кодировке без потери диагностируемости
# (гейт печатает текст, не бинарные данные).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "docs" / "SIBLING_MAP.md"
DECISIONS_FULL = "docs/DECISIONS_FULL.md"
CONFIG_PATH = REPO / "delegation.config.yaml"

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
)

AXIS_HEADING_RE = re.compile(r"^##\s+Ось\s+(\d+)", re.MULTILINE)
# Якорь строки (D-0093, полигон Dog): без ^…$/MULTILINE фраза матчилась
# .search()'ом по ЛЮБОМУ месту сообщения — инлайн-цитата синтаксиса
# отказа посреди прозы («…строка «оси: не-механизм (пример)» обходила
# бы…») глушила гейт целиком. Симметрично уже заякоренному TIER_LINE_RE.
SKIP_RE = re.compile(r"^\s*оси\s*:\s*не-механизм\s*\(", re.IGNORECASE | re.MULTILINE)


def parse_axes(map_text: str) -> list[int]:
    """Номера осей из заголовков карты; порядок и разрывы нумерации не важны."""
    return [int(n) for n in AXIS_HEADING_RE.findall(map_text)]


def _matches(path: str, pref: str) -> bool:
    # Граница префикса (F-D): каталоги — по startswith, файлы — точно
    # (CLAUDE.md.bak не механизмный путь).
    if pref.endswith("/"):
        return path.startswith(pref)
    return path == pref


def mechanism_paths(staged: list[str]) -> list[str]:
    return [p for p in staged
            if any(_matches(p, pref) for pref in MECHANISM_PREFIXES)]


def find_missing(text: str, axes: list[int]) -> list[int]:
    return [n for n in axes
            if not re.search(rf"ось\s+{n}\s*:", text, re.IGNORECASE)]


def resolve_lead_binding(config_text: str | None) -> str:
    """Модель, привязанная к roles.lead в delegation.config.yaml (см.
    структуру в toolkit/delegation.config.yaml). Файл отсутствует, ключ
    roles.lead отсутствует, либо YAML не парсится → дефолт семейства
    "fable" (субскрипционный дефолт Lead, D-0072) — консервативный
    (fail-closed) выбор: требует явной декларации от кого угодно ниже
    top-tier. Самодекларация НЕ проверяется на истинность здесь (см.
    tier_declared_ok) — двухслойный enforcement D-0063: код гарантирует
    форму, правду судит калибровка по транскриптам ярусом выше."""
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
    sonnet/haiku); None — семейство не распознано (не-Claude привязка),
    тогда годится только точное совпадение model id."""
    low = binding.lower()
    for fam in LEAD_FAMILIES:
        if fam in low:
            return fam
    return None


def find_tier_declarations(msg: str) -> list[str]:
    """t-278 п.5 (критик t-068: find_tier_declaration матчил ТОЛЬКО
    первую строку «tier:» через .search() -- недостаточно: несколько
    механизмов в одном коммите МОГУТ нести отдельные tier-строки, каждую
    свою). Возвращает ЗНАЧЕНИЯ ВСЕХ строк «tier: <значение>» в сообщении
    коммита (не из диффа) -- та же самодекларативная форма, что и
    skip-строка. РЕШЕНИЕ ПО СЕМАНТИКЕ (задокументировано, не молча):
    безопасная (fail-closed) семантика -- каждая найденная строка
    ДОЛЖНА пройти проверку (см. tier_declared_ok в decide_full ниже);
    отказ, если хоть ОДНА строка не совпадает с привязкой, даже если
    другая (например, настоящая, более поздняя) строка совпадает.
    Альтернатива ("проходит, если совпадает ХОТЯ БЫ ОДНА") была
    отклонена: при НЕСКОЛЬКИХ tier-строках в одном сообщении она
    позволила бы одной подставной/цитированной строке "tier: fable"
    маскировать РЕАЛЬНОЕ несовпадающее значение где-то ещё в том же
    сообщении.

    УТОЧНЕНИЕ ГРАНИЦЫ ГАРАНТИИ (критик t-278 (а) -- докстринг поправлен
    без изменения кода): "ALL must pass" защищает именно этот
    МНОГОСТРОЧНЫЙ случай (настоящая несовпадающая строка + спуфящая
    совпадающая строка рядом) -- ОДНОСТРОЧНЫЙ спуфер (единственная
    поддельная tier-строка, без настоящей) проходит ОБЕ семантики
    ОДИНАКОВО: эта функция вообще не проверяет, что заявленный ярус
    ПРАВДИВ, только что заявленная ФОРМА совпадает с привязкой (правда
    заявления -- зона калибровки по транскриптам, D-0063: код
    гарантирует форму, ярус выше судит смысл). Реальный эффект выбранной
    семантики -- fail-closed на цитатах/множественных строках (ложный
    отказ безопаснее пропуска), а не общая анти-спуфинг-гарантия."""
    return [m.strip() for m in TIER_LINE_RE.findall(msg)]


def find_tier_declaration(msg: str) -> str | None:
    """Обратная совместимость/удобство: значение ПЕРВОЙ строки «tier:
    <значение>» (см. find_tier_declarations() за полную семантику всех
    строк, которую использует decide_full())."""
    declarations = find_tier_declarations(msg)
    return declarations[0] if declarations else None


# D-0099 п.6 (2026-08-04): онбординг-лестница -- каждая привязанная модель
# прошла входной экзамен (exam.mandatory), roles.{scout,builder,critic,
# lead,reserve} в delegation.config.yaml И ЕСТЬ валидированная лестница
# деплоя, в этом фиксированном функциональном порядке. reserve (Fable-
# резерв) — единственная ступень СТРОГО ВЫШЕ lead; roles.judge/roles.analyst
# не координационные роли и в лестницу не входят. B4.3 (пересдача,
# критик-блокер): roles.designer ТОЖЕ не ступень лестницы -- designer
# стоячая функция того же яруса, что critic (opus, .claude/agents/
# designer.md), но НЕ координационная роль в смысле этой иерархии
# (координирует спеки, не диспетчит работу); как и judge/analyst, её ключ
# просто не входит в ROLE_RANKS и build_role_ladder() по построению его не
# читает -- см. test_build_role_ladder_ignores_designer.
ROLE_RANKS = {"scout": 0, "builder": 1, "critic": 2, "lead": 3, "reserve": 4}


def _resolve_role_model(role_data) -> str | None:
    """Модель ОДНОЙ роли по той же subscription/api-приоритетности, что и
    resolve_lead_binding() -- но БЕЗ дефолта "fable": роль без модели
    (ключа нет, или subscription.model/api.model оба пусты) просто не
    даёт ступени лестницы, это не то же самое, что привязка Lead
    конкретно (у которой отсутствие -- осмысленный субскрипционный
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
    (fail-open к существующей family-эвристике tier_declared_ok, которая
    ничего не знает про лестницу и работает как раньше)."""
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
    """D-0099 п.6: резолюция декларации в ранг лестницы.

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
        принятый и покрытый тестами кейс).
    None -- лестница без ступени lead, или declared не резолвится ни (а),
    ни (б) (в т.ч. не-Claude declared без точного id-совпадения --
    family-путь для него не определён)."""
    ladder = build_role_ladder(config_text)
    lead_rank = ROLE_RANKS["lead"]
    lead_models = [model_id for rank, model_id in ladder if rank == lead_rank]
    if not lead_models:
        return None  # B3: нет ступени lead -- лестничный путь не резолвит НИЧЕГО
    lead_model = lead_models[0]
    lead_fam = lead_family(lead_model)

    # П5(a): family-strength guard, теперь И на точном id-совпадении --
    # см. докстринг выше, "(а) ТОЧНОЕ совпадение", за полный разбор
    # развилки (сравнимые семейства -> guard; нерезолвимое семейство
    # ступени-кандидата -> доверие позиции лестницы).
    exact_matches = []
    for rank, model_id in ladder:
        if declared != model_id:
            continue
        cand_fam = lead_family(model_id)
        if lead_fam is not None and cand_fam is not None:
            if LEAD_FAMILIES.index(cand_fam) > LEAD_FAMILIES.index(lead_fam):
                continue  # нонсенс: ступень слабее lead семейством, отбрасываем
        exact_matches.append(rank)
    if exact_matches:
        return max(exact_matches)  # B4: максимальный ранг среди совпавших

    declared_fam = lead_family(declared)
    if declared_fam is None:
        return None
    candidates = []
    for rank, model_id in ladder:
        if lead_family(model_id) != declared_fam:
            continue
        # B3 edge (i): guard активен только когда family lead-ступени
        # известна (Claude lead) -- рангу-кандидату запрещено быть
        # СЛАБЕЕ lead по LEAD_FAMILIES ordinal (больший индекс = слабее).
        if lead_fam is not None:
            cand_fam = lead_family(model_id)
            if LEAD_FAMILIES.index(cand_fam) > LEAD_FAMILIES.index(lead_fam):
                continue  # нонсенс: позиционно >=lead, но семейством слабее
        candidates.append(rank)
    if len(candidates) == 1:
        return candidates[0]
    return None


def tier_declared_ok(declared: str, binding: str, config_text: str | None = None) -> bool:
    """config_text (D-0099 п.6, опционально, дефолт None): онбординг-
    лестница -- строго ДОПОЛНЯЕТ существующие пути ниже, никогда их не
    сужает (см. докстринг _resolve_ladder_rank/build_role_ladder).
    Ветки 1-3 (точное совпадение с binding / вхождение её семейства /
    family строго выше ранга binding по LEAD_FAMILIES) — БЕЗ ИЗМЕНЕНИЙ.
    Не-Claude привязка (fam(binding) is None) БОЛЬШЕ НЕ обрывает функцию
    ранним return False -- ветки 1-3 просто молчат (семейства сравнивать
    не с чем), но ЛЕСТНИЧНАЯ резолюция (шаг 4, ниже) всё равно
    выполняется: не-Claude привязка с не-Claude лестницей резолвится
    точным id (см. edge "lead: llama-3.3-70b-versatile")."""
    if declared == binding:
        return True
    fam = lead_family(binding)
    if fam is not None:
        if fam in declared.lower():
            return True
        # D-0099 (2026-08-04): декларация семейства СТРОГО ВЫШЕ ранга
        # привязки тоже легальна — матрица Role != tier: ярусы выше
        # Lead-привязки суть полный Lead (переходный коммит самой
        # перепривязки коммитится ещё сессией старого, более высокого
        # яруса). Ранг — позиция в LEAD_FAMILIES (индекс 0 = высшее
        # семейство "fable"); "строго выше" значит МЕНЬШИЙ индекс.
        # Привязка fable — LEAD_FAMILIES.index("fable")==0, индексов
        # меньше 0 не существует, поэтому эта ветка молчит без отдельной
        # проверки: регресс-пин "выше fable ничего нет" сохраняется
        # автоматически арифметикой индекса. Не-Claude ДЕКЛАРАЦИЯ
        # (declared_fam is None) эту ветку не матчит — годится только
        # точное совпадение (шаг 1 выше) или лестница (шаг 4 ниже).
        declared_fam = lead_family(declared)
        if declared_fam is not None and LEAD_FAMILIES.index(declared_fam) < LEAD_FAMILIES.index(fam):
            return True
    # (4) D-0099 п.6: онбординг-лестница конфига -- принимается ранг
    # declared >= ранга ступени "lead" (ФИКСИРОВАННАЯ позиция ROLE_RANKS,
    # не зависящая от того, какие ступени сегодня сконфигурированы).
    declared_rank = _resolve_ladder_rank(declared, config_text)
    if declared_rank is not None and declared_rank >= ROLE_RANKS["lead"]:
        return True
    return False


def _tier_queue_note() -> str:
    return ("механизменный коммит — Lead-tier работа: сессия на ярусе "
            "ниже привязки lead НЕ коммитит механизм сама, а кладёт его "
            "в Lead-очередь CURRENT_CONTEXT.md; сессия lead-яруса "
            "добавляет строку «tier: <своя модель>» (D-0072).")


def decide(msg: str, block_extra: str, staged: list[str],
           map_text: str | None, merging: bool = False) -> tuple[int, str]:
    """Чистое решение гейта. block_extra — дифф docs/DECISIONS_FULL.md."""
    hits = mechanism_paths(staged)
    if not hits:
        return 0, ""
    if merging:
        return 0, ""
    if SKIP_RE.search(msg):  # только сообщение — F-A + только отдельная строка (якорь, D-0093)
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


def decide_full(msg: str, block_extra: str, staged: list[str],
                 map_text: str | None, config_text: str | None,
                 merging: bool = False) -> tuple[int, str]:
    """decide() плюс требование правила 7 (D-0072): строка tier на
    ветке «механизм» (осевой блок уже пройден, не skip, не merge).
    config_text — текст delegation.config.yaml (или None, если файла
    нет), тем же паттерном, что и map_text."""
    code, reason = decide(msg, block_extra, staged, map_text, merging)
    if code:
        return code, reason
    hits = mechanism_paths(staged)
    if not hits or merging or SKIP_RE.search(msg):
        return 0, ""
    binding = resolve_lead_binding(config_text)
    # t-278 п.5: ВСЕ найденные tier-строки должны пройти проверку —
    # отказ, если хоть ОДНА не совпадает с привязкой (см. докстринг
    # find_tier_declarations() за обоснование выбранной семантики).
    declared_list = find_tier_declarations(msg)
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
