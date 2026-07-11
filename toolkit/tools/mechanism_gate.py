"""Гейт правила 10(б) — D-0055: коммит механизмных файлов несёт осевой блок.

Вызывается commit-msg-хуком (.githooks/commit-msg) с путём к файлу
сообщения коммита. Логика (полностью в чистой decide(), тестируемой
без git):

1. Staged-пути не задевают механизмные префиксы → гейт молчит.
2. Merge-коммит (MERGE_HEAD существует) → гейт молчит: слитые коммиты
   уже проходили его поодиночке; блокировать автосообщение мержа —
   ложное срабатывание, приучающее к --no-verify (ревью critic, F-C).
3. Skip line "axes: not a mechanism (<reason>)" (this template's
   English phrasing, CLAUDE.md rule 10) works ONLY from the commit
   message -- a written statement by the committer, the same pattern
   as `dispatch_skipped`. Not looked up in the diff: decision text that
   quotes the skip syntax would otherwise bypass the gate.
4. Axis block -- lines "axis N: <verdict>" for EVERY axis of the
   current docs/SIBLING_MAP.md -- looked up in the commit message PLUS
   in the staged diff of ONE file, DECISIONS.md (this template ships a
   single decisions file; the source deployment's two-file split
   (DECISIONS.md summary + docs/DECISIONS_FULL.md detail) collapses to
   just DECISIONS.md here -- template dependency, toolkit transfer).
   The whole diff is not scanned: unrelated staged content with a
   literal "axis N:" would close axes fictitiously. Axis count and
   numbers are read from the map on every run -- the map grows and
   changes, the gate follows it.
5. Карта не читается / ноль осей → fail-closed (F-7: молчаливый
   пропуск проверки неотличим от её прохождения).
6. Net: known homes of mechanisms in this template (CLAUDE.md,
   DECISIONS.md, docs/SIBLING_MAP.md, PROCESS/, .claude/agents/,
   .claude/skills/, BOOT.md) plus self-protection of the enforcement
   chain itself (this file, tools/session_context.py -- the
   SessionStart hook, .githooks/, .claude/settings.json -- editing the
   gate or the hook registration must not bypass the gate). Wide
   directories (tools/, gateway/) are deliberately outside the net --
   false positives there train toward --no-verify (same tradeoff as
   the source deployment's D-0055).
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "docs" / "SIBLING_MAP.md"
# Template dependency (toolkit transfer): this template has ONE decisions
# file, DECISIONS.md -- not the source deployment's docs/DECISIONS_FULL.md.
DECISIONS_FULL = "DECISIONS.md"

MECHANISM_PREFIXES = (
    "CLAUDE.md",
    "DECISIONS.md",
    "docs/SIBLING_MAP.md",
    "PROCESS/",
    ".claude/agents/",
    ".claude/skills/",
    "BOOT.md",
    "tools/mechanism_gate.py",
    ".githooks/",
    # SessionStart hook duties are future-session obligations too.
    "tools/session_context.py",
    ".claude/settings.json",
)

# Template dependency (toolkit transfer, empirically verified against
# toolkit/docs/SIBLING_MAP.md and toolkit/CLAUDE.md rule 10): this
# template's map headings and its axis-answer/skip-line vocabulary are
# English ("## Axis N", "axis N: covered", "axes: not a mechanism
# (<reason>)") -- the source deployment's Russian regexes ("Ось N")
# silently matched zero axes against this template's own map (fail-
# closed on every mechanism commit); ported as English to match the
# artifact these regexes actually run against.
AXIS_HEADING_RE = re.compile(r"^##\s+Axis\s+(\d+)", re.MULTILINE)
SKIP_RE = re.compile(r"axes\s*:\s*not\s+a\s+mechanism\s*\(", re.IGNORECASE)


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
            if not re.search(rf"axis\s+{n}\s*:", text, re.IGNORECASE)]


def decide(msg: str, block_extra: str, staged: list[str],
           map_text: str | None, merging: bool = False) -> tuple[int, str]:
    """Чистое решение гейта. block_extra — дифф DECISIONS.md."""
    hits = mechanism_paths(staged)
    if not hits:
        return 0, ""
    if merging:
        return 0, ""
    if SKIP_RE.search(msg):  # только сообщение — F-A
        return 0, ""
    if map_text is None:
        return 1, (f"axis map not found ({MAP_PATH}) -- fail-closed, "
                   "commit rejected (rule 10(b))")
    axes = parse_axes(map_text)
    if not axes:
        return 1, ("no axis found in the map (## Axis N) -- "
                   "fail-closed (rule 10(b))")
    missing = find_missing(msg + "\n" + block_extra, axes)
    if missing:
        return 1, ("commit touches mechanism files:\n  " + "\n  ".join(hits)
                   + "\nRule 10(b)'s axis block is incomplete -- no verdict for axes: "
                   + ", ".join(str(n) for n in missing)
                   + "\nAdd \"axis N: covered / queued / n/a <why>\" for "
                   "every axis of the map (in the commit message or in the "
                   "decision text, DECISIONS.md), or an explicit skip in the "
                   "COMMIT MESSAGE: \"axes: not a mechanism (<reason>)\" "
                   "(rule 10(b)).")
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
