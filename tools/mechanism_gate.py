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
   семейства нет, годится только точное совпадение model id.
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
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
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
SKIP_RE = re.compile(r"оси\s*:\s*не-механизм\s*\(", re.IGNORECASE)


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


def find_tier_declaration(msg: str) -> str | None:
    """Значение строки «tier: <значение>» — только из СООБЩЕНИЯ коммита
    (не из диффа), та же самодекларативная форма, что и skip-строка."""
    m = TIER_LINE_RE.search(msg)
    return m.group(1).strip() if m else None


def tier_declared_ok(declared: str, binding: str) -> bool:
    if declared == binding:
        return True
    fam = lead_family(binding)
    if fam is None:
        return False
    return fam in declared.lower()


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
    if SKIP_RE.search(msg):  # только сообщение — F-A
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
    declared = find_tier_declaration(msg)
    if declared is None:
        return 1, ("коммит трогает механизмные файлы:\n  " + "\n  ".join(hits)
                    + "\nНет строки «tier: <значение>» (привязка lead: "
                    + binding + ") — " + _tier_queue_note())
    if not tier_declared_ok(declared, binding):
        return 1, ("коммит трогает механизмные файлы:\n  " + "\n  ".join(hits)
                    + "\nЯрус не lead: «tier: " + declared
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
