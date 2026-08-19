"""mechanism_gate_md.py -- region-aware sibling of tools/mechanism_gate.py
(этап 2, партия 2, узел E, t-530 / docs/tasks/2026-08-19_scanner-party2-
spec.md). Живой tools/mechanism_gate.py НЕ ТРОГАЕТСЯ (D-0069) -- этот
файл нейтральный сосед; посадка (переименование на боевой путь +
регистрация в .githooks/commit-msg) -- акт Lead.

БАЗА: буквальная копия tools/mechanism_gate.py (mechanism_paths,
find_missing, parse_axes, resolve_lead_binding/lead_family/
build_role_ladder/_resolve_ladder_rank/tier_declared_ok -- ВСЯ D-0099
лестница рангов, decide/decide_full/main) -- см. живой файл за полным
происхождением каждого правила (D-0055/D-0072/D-0093/D-0099), здесь не
повторяется. ЕДИНСТВЕННОЕ отличие по существу: региона-осведомлённая
фильтрация того, ЧТО СЧИТАЕТСЯ СОВПАДЕНИЕМ SKIP_RE/TIER_LINE_RE, скоуп
Ф7(б) решения Lead 08-19 (docs/tasks/2026-08-19_scanner-party2-spec.md).

НАХОДКА (родительская спека md_regions, §13 п.3): "mechanism_gate
(остаточная дыра «строка отказа внутри фенса»)" -- SKIP_RE/TIER_LINE_RE
живого файла УЖЕ заякорены (^…$/MULTILINE, D-0093) против ИНЛАЙН-цитаты
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
(:194 живого файла) И TIER_LINE_RE (:95) -- совпадение, ЧЬЯ СОБСТВЕННАЯ
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
позиция -- прoза; decide_full()'s "ALL must pass" (t-278 п.5, живой
файл) применяется к ЭТОМУ отфильтрованному списку. find_tier_
declarations() (публичная, живая) САМА НЕ ТРОГАЕТСЯ -- региона-блинд,
байт-в-байт (используется прямыми вызовами батареи/равенства).

ОСЕВЫЕ СТРОКИ find_missing() -- ЯВНО НЕ ФИЛЬТРУЮТСЯ (Ф7 решения Lead
08-19, ОТЛОЖЕНО ДО ЗАМЕРА ЖИВОГО ЛОГА, R8f): "ось N: <вердикт>" внутри
фенса/цитаты СЧИТАЕТСЯ так же, как в прозе -- find_missing() этого файла
байт-в-байт копия живой функции, region ей НЕ передаётся вообще. Это
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
булевы/списочные ответы, что и живой файл. Это означает: если ТОЛЬКО
цитируемый skip существует (E8, "цитированный skip снова глушит --
объявленный фоллбек"), И-0 откатывает СИБЛИНГ к СЕГОДНЯШНЕМУ поведению
живого файла -- гейт СНОВА молчит на цитируемом skip (тот же остаточный
баг, что живой файл несёт сегодня) -- НЕ новый путь кода, тот же цикл с
region-веткой, ставшей мёртвой (тот же принцип, что owns_gate_md.py/
negative_lint_md.py).
"""
from __future__ import annotations

import bisect
import re
import subprocess
import sys
from pathlib import Path

import yaml

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
    "ARCHITECTURE.md",
    "ARCHITECTURE_BOOT.md",
    "BOOT.md",
    "gateway/PI_HARNESS.md",
    "tools/mechanism_gate.py",
    ".githooks/",
    ".claude/settings.json",
    "tools/session_context.py",
    "tools/dispatch_gate.py",
    "tools/critic_snapshot.py",
    "tools/owns_gate.py",
    "tools/hygiene_gate.py",
    "tools/claim_control_gate.py",
    "tools/dod_track.py",
    "tools/journal_echo.py",
    "tools/search_control_gate.py",
    "tools/negative_lint.py",
    "tools/md_regions.py",
    "tools/dod_gate.py",
    "tools/main_gate.py",
    "tools/journal_validator.py",
    "tools/escape_check.py",
    "tools/enforcement_probe.py",
    "docs/FINDINGS.md",
    "docs/RULE_COVERAGE.md",
    "tools/wiring_check.py",
    "tools/tier_echo.py",
    "tools/preflight_quota.py",
)

AXIS_HEADING_RE = re.compile(r"^##\s+Ось\s+(\d+)", re.MULTILINE)
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
    return [int(n) for n in AXIS_HEADING_RE.findall(map_text)]


def _matches(path: str, pref: str) -> bool:
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
    low = binding.lower()
    for fam in LEAD_FAMILIES:
        if fam in low:
            return fam
    return None


def find_tier_declarations(msg: str) -> list[str]:
    """Region-БЛИНД, БАЙТ-В-БАЙТ живая функция -- см. докстринг модуля
    "ALL-MUST-PASS СЧИТАЕТ ТОЛЬКО НЕЦИТИРОВАННЫЕ TIER-СТРОКИ": decide_full()
    region-aware отбор живёт в _region_filtered_tier_declarations() ниже,
    эта функция НЕ ТРОНУТА (сохранена ради прямых вызовов батареи и
    обратной совместимости, тот же принцип, что find_missing())."""
    return [m.strip() for m in TIER_LINE_RE.findall(msg)]


def find_tier_declaration(msg: str) -> str | None:
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


ROLE_RANKS = {"scout": 0, "builder": 1, "critic": 2, "lead": 3, "reserve": 4}


def _resolve_role_model(role_data) -> str | None:
    if not isinstance(role_data, dict):
        return None
    model = ((role_data.get("subscription") or {}).get("model")
             or (role_data.get("api") or {}).get("model"))
    return model or None


def build_role_ladder(config_text: str | None) -> list[tuple[int, str]]:
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
    search(msg) живого файла (см. докстринг модуля "И-0")."""
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
