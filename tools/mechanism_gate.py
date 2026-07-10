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
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "docs" / "SIBLING_MAP.md"
DECISIONS_FULL = "docs/DECISIONS_FULL.md"

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
    code, reason = decide(msg, block_extra, staged, map_text, merging)
    if code:
        print("mechanism_gate: " + reason, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
