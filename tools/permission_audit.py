"""permission_audit — восстановить, какие Bash/PowerShell-команды (включая субагентов)
вероятно требовали ручного подтверждения, и почему.

Порт из D:\\AO3_tests\\scripts\\permission_audit.py (t-106: принятая оценка пилота —
скрипт ловит, сигнал/шум хороший) под этот деплой. Логика эвристик (allowlist-матчинг,
auto-allow, sandbox-эвристики) — без изменений относительно оригинала. Две доработки,
найденные пилотом:

  (а) СНАПШОТ списка транскриптов и их размеров ДО скана — прогон в живой сессии
      дописывает сканируемый транскрипт, числа "Просканировано" иначе плывут между
      стартом и концом скрипта. Читаем только зафиксированный на старте префикс байт
      каждого файла, а не всё, что там окажется к моменту чтения.
  (b) Блок MASKED-BY-BROAD-ALLOWLIST — оба settings-файла сканируются на паттерны
      произвольного выполнения (голый интерпретатор/`-c`/`-e` перед `*`, например
      `Bash(python *)`) и печатается явное предупреждение: такие правила молча гасят
      часть категории «нет совпадения с allowlist», не показавшись как suspect вовсе.

Прямого лога «показан permission-диалог» нет, поэтому аудит эвристический:
берём все tool_use из транскриптов текущего проекта, прогоняем через те же правила,
что и харнесс (allowlist settings.json/settings.local.json + известные auto-allow +
sandbox-эвристики «cannot be statically analyzed»), и печатаем те, что НЕ прошли бы
без вопроса — с категорией причины и предложением фикса.

Запуск:  python tools/permission_audit.py [--minutes 120] [--all] [--session ID] [--summary]
  --minutes N  смотреть только команды за последние N минут (default 180)
  --all        игнорировать фильтр времени
  --session S  только транскрипты (main + subagents), чей путь содержит подстроку S
  --summary    сводка по группам вместо полного списка
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECT_KEY = "D--Improving-AI-Operating-System-for-LLMs"
CLAUDE_PROJECTS = Path(os.path.expanduser("~")) / ".claude" / "projects" / PROJECT_KEY

# --- команды, которые харнесс авто-разрешает без allowlist (усечённый практичный список) ---
AUTO_ALLOW_ANY_ARGS = {
    "cat", "head", "tail", "wc", "stat", "ls", "cd", "echo", "sleep", "which", "diff",
    "true", "false", "seq", "basename", "dirname", "realpath", "cut", "tr", "comm",
    "readlink", "expr", "type", "uname", "df", "du", "nl", "od", "id", "date",
}
AUTO_ALLOW_VALIDATED = {"grep", "rg", "find", "sort", "uniq", "jq", "sed", "ps", "xargs",
                        "file", "tree", "hostname", "pgrep", "lsof", "printf", "man"}
GIT_RO = {"status", "log", "diff", "show", "blame", "branch", "tag", "remote", "ls-files",
          "rev-parse", "describe", "reflog", "shortlog", "cat-file", "for-each-ref",
          "worktree", "stash"}

SANDBOX_HEURISTICS = [
    (re.compile(r'export\s+\w+="[^"]*\$\{?\w+'), "export VAR со ссылкой на другую переменную (array-subscript эвристика)"),
    (re.compile(r"\bnohup\b"), "nohup / ручной фон"),
    (re.compile(r"\$\("), "командная подстановка $(...)"),
    (re.compile(r"\bfor\s+\w+\s+in\b.*\bdo\b", re.S), "цикл for...do в shell"),
    (re.compile(r"\buntil\b|\bwhile\b.*\bdo\b", re.S), "цикл while/until"),
    (re.compile(r"&\s*$", re.M), "фоновый запуск через &"),
]

# --- доработка (b): паттерны allowlist, дающие практически произвольное выполнение кода ---
INTERPRETER_HEADS = {
    "python", "python3", "py", "node", "ruby", "perl", "bash", "sh", "zsh",
    "powershell", "pwsh", "osascript", "php",
}
CODE_FLAGS = {"-c", "-e", "--command"}


def _iter_allow_entries():
    """(file_name, tool, pattern) по обеим settings-файлам, сырые записи allow."""
    for name in ("settings.json", "settings.local.json"):
        p = REPO / ".claude" / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] не смог прочитать {name}: {e}", file=sys.stderr)
            continue
        for entry in data.get("permissions", {}).get("allow", []):
            m = re.match(r"^(\w+)\((.*)\)$", entry, re.S)
            if m:
                yield name, m.group(1), m.group(2)
            else:
                yield name, entry, ""  # голое имя тула, например WebSearch


def load_allow_patterns() -> list[tuple[str, str]]:
    """[(tool, pattern), ...] из settings.json + settings.local.json."""
    return [(tool, pat) for _name, tool, pat in _iter_allow_entries()]


def matches_allow(tool: str, cmd: str, patterns) -> bool:
    for ptool, pat in patterns:
        if ptool != tool:
            continue
        if not pat:
            return True
        if pat.endswith("*"):
            if cmd.startswith(pat[:-1]):
                return True
        elif " *" in pat:  # форма "foo *" — префикс до звёздочки
            if cmd.startswith(pat.split(" *")[0]):
                return True
        elif fnmatch.fnmatch(cmd, pat) or cmd == pat:
            return True
    return False


def is_auto_allowed(cmd: str) -> bool:
    """Грубая оценка встроенного auto-allow (только однострочные простые команды)."""
    if "\n" in cmd.strip():
        return False
    # цепочки — каждая часть должна быть auto-allowed
    parts = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd.strip())
    for part in parts:
        if not part:
            continue
        tokens = part.strip().split()
        if not tokens:
            continue
        head = tokens[0].strip('"')
        base = os.path.basename(head).lower().removesuffix(".exe")
        if base == "git" and len(tokens) > 1 and tokens[1] in GIT_RO:
            continue
        if base in AUTO_ALLOW_ANY_ARGS or base in AUTO_ALLOW_VALIDATED:
            continue
        return False
    return True


def sandbox_flags(cmd: str) -> list[str]:
    flags = [reason for rx, reason in SANDBOX_HEURISTICS if rx.search(cmd)]
    if "\n" in cmd.strip():
        flags.append("многострочная команда (несколько statement'ов в одном вызове)")
    return flags


_ENV_ASSIGN_RE = re.compile(r"^\w+=\S*$")


def is_broad_wildcard(tool: str, pat: str) -> str | None:
    """Если pat — allowlist-паттерн, пропускающий произвольное выполнение (голый
    интерпретатор перед `*`, интерпретатор с флагом -c/-e перед `*`, в т.ч. с
    незакрытой открывающей кавычкой сразу после флага, опционально за префиксом
    вида VAR=val) — вернуть причину строкой. Иначе None. Примеры находок пилота:
    Bash(python *), Bash(python -c ' *), Bash(PYTHONUTF8=1 python -c ' *)."""
    if tool not in ("Bash", "PowerShell"):
        return None
    p = pat.strip()
    if not p.endswith("*"):
        return None
    prefix = p[:-1].strip()
    tokens = prefix.split()
    while tokens and _ENV_ASSIGN_RE.match(tokens[0]):
        tokens = tokens[1:]  # пропустить VAR=val перед именем интерпретатора
    if not tokens:
        return None
    head = os.path.basename(tokens[0].strip("\"'")).lower().removesuffix(".exe")
    if head not in INTERPRETER_HEADS:
        return None
    rest = tokens[1:]
    if not rest:
        return f"голый интерпретатор без аргументов — пропускает произвольный код после «{head}»"
    if rest[0] in CODE_FLAGS:
        remainder = "".join(rest[1:]).strip("'\"")
        if not remainder:
            return f"«{head} {rest[0]}» — произвольный код одной строкой проходит без вопроса"
    # F2 ревью t-107: `<интерпретатор> -m *` пропускает произвольный МОДУЛЬ
    # (python -m http.server, -m pip, ...) — тот же класс, что -c/-e.
    if rest[0] == "-m" and not "".join(rest[1:]).strip("'\""):
        return f"«{head} -m» — произвольный модуль проходит без вопроса"
    return None


def scan_broad_wildcards() -> list[tuple[str, str, str, str]]:
    """[(settings-файл, tool, pattern, reason), ...] для широких wildcard-паттернов,
    молча гасящих категорию «нет совпадения с allowlist» (доработка b пилота)."""
    out = []
    for fname, tool, pat in _iter_allow_entries():
        reason = is_broad_wildcard(tool, pat)
        if reason:
            out.append((fname, tool, pat, reason))
    return out


def snapshot_transcripts(session: str | None = None) -> list[tuple[Path, str, int]]:
    """[(path, agent_type, size_at_snapshot), ...] — зафиксировать список
    транскриптов и их размеры ДО скана (доработка a пилота): прогон в живой сессии
    дописывает сканируемый транскрипт, и без снапшота числа "Просканировано" плывут
    между стартом и концом скрипта. Скан ниже читает только эти первые
    size_at_snapshot байт каждого файла — то, что дописано после снапшота, игнорируется."""
    files: list[tuple[Path, str]] = []
    for jl in CLAUDE_PROJECTS.glob("*.jsonl"):
        files.append((jl, "main"))
    for sub in CLAUDE_PROJECTS.glob("*/subagents/agent-*.jsonl"):
        if session and session not in str(sub):
            continue
        agent_type = "subagent"
        meta = sub.with_name(sub.name.replace(".jsonl", ".meta.json"))
        if meta.exists():
            try:
                agent_type = json.loads(meta.read_text(encoding="utf-8")).get("agentType", "subagent")
            except Exception:  # noqa: BLE001
                pass
        files.append((sub, agent_type))

    snapshot = []
    for path, source in files:
        if session and source == "main" and session not in path.name:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        snapshot.append((path, source, size))
    return snapshot


def _read_snapshot_lines(path: Path, size: int) -> list[str]:
    """Прочитать первые `size` байт файла (зафиксированные снапшотом) и вернуть
    полные строки; возможную обрезанную последнюю строку на границе отбрасываем."""
    try:
        with open(path, "rb") as fb:
            data = fb.read(size)
    except OSError:
        return []
    text = data.decode("utf-8", errors="replace")
    if not text.endswith("\n") and "\n" in text:
        text = text[: text.rfind("\n") + 1]
    elif not text.endswith("\n"):
        text = ""  # единственная строка в файле оборвана на границе снапшота
    return text.splitlines()


def iter_tool_calls(minutes: float | None, session: str | None = None,
                     snapshot: list[tuple[Path, str, int]] | None = None):
    """(when, source, agent_type, tool, command) по снапшоту транскриптов проекта."""
    cutoff = None if minutes is None else time.time() - minutes * 60
    if snapshot is None:
        snapshot = snapshot_transcripts(session)

    for path, source, size in snapshot:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if cutoff and mtime < cutoff:
            continue  # файл не менялся в окне — пропускаем целиком
        for line in _read_snapshot_lines(path, size):
            line = line.strip()
            if not line or '"tool_use"' not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            ts = obj.get("timestamp")
            when = None
            if ts:
                try:
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                except Exception:  # noqa: BLE001
                    pass
            if cutoff and when and when < cutoff:
                continue
            for item in obj.get("message", {}).get("content", []) or []:
                if isinstance(item, dict) and item.get("type") == "tool_use" \
                        and item.get("name") in ("Bash", "PowerShell"):
                    cmd = (item.get("input") or {}).get("command", "")
                    yield when, path.name, source, item["name"], cmd


def collect_suspects(minutes: float | None, session: str | None = None,
                      snapshot: list[tuple[Path, str, int]] | None = None):
    """Прогнать все tool_use через allowlist + sandbox-эвристики.

    Возвращает (suspects, total), где suspects — список
    (when, agent, tool, cmd, reason) для команд, которые ВЕРОЯТНО требовали
    ручного подтверждения. Вынесено из main() отдельной чистой функцией,
    чтобы юнит-тесты могли проверять фильтрацию без парсинга stdout.
    """
    patterns = load_allow_patterns()
    suspects = []
    total = 0
    for when, fname, agent, tool, cmd in iter_tool_calls(minutes, session, snapshot):
        total += 1
        allowed = matches_allow(tool, cmd, patterns)
        flags = sandbox_flags(cmd)
        if (allowed and not flags) or is_auto_allowed(cmd):
            continue
        reason = []
        if not allowed:
            reason.append("нет совпадения с allowlist")
        reason += flags
        suspects.append((when, agent, tool, cmd, reason))
    return suspects, total


def main(argv=None):
    if os.name == "nt":  # консоль Windows в cp866 душит кириллицу — форсим utf-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=180)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--session", help="фильтр: только транскрипты, чьи пути содержат эту подстроку (id сессии)")
    ap.add_argument("--summary", action="store_true", help="сводка по группам вместо полного списка")
    args = ap.parse_args(argv)
    minutes = None if getattr(args, "all") else args.minutes

    # доработка (b): предупреждение о широких allowlist-паттернах — перед сводкой
    broad = scan_broad_wildcards()
    if broad:
        print("MASKED-BY-BROAD-ALLOWLIST:")
        print("  Эти правила allowlist пропускают произвольное выполнение кода и МОЛЧА")
        print("  глушат часть категории «нет совпадения с allowlist» ниже — команды под")
        print("  ними даже не попадут в suspects, хотя по факту могут быть неверной формой:")
        for fname, tool, pat, reason in broad:
            print(f"  - {fname}: {tool}({pat}) — {reason}")
        print()

    snapshot = snapshot_transcripts(args.session)
    suspects, total = collect_suspects(minutes, args.session, snapshot)

    print(f"Просканировано вызовов Bash/PowerShell: {total}"
          + ("" if minutes is None else f" (за последние {minutes:g} мин)")
          + (f" · сессия *{args.session[:8]}*" if args.session else ""))
    print(f"Вероятно требовали подтверждения: {len(suspects)}\n")

    if args.summary:
        from collections import Counter
        by_agent = Counter(a for _, a, *_ in suspects)
        by_reason = Counter(r for *_, reasons in suspects for r in reasons)
        examples: dict[str, str] = {}
        for _, agent, _tool, cmd, reasons in suspects:
            for r in reasons:
                examples.setdefault(r, " ".join(cmd.split())[:110])
        print("По агентам:")
        for a, n in by_agent.most_common():
            print(f"  {n:4d}  {a}")
        print("\nПо причинам:")
        for r, n in by_reason.most_common():
            print(f"  {n:4d}  {r}")
            print(f"        пример: {examples[r]}")
    else:
        for when, agent, tool, cmd, reason in suspects:
            t = datetime.fromtimestamp(when, tz=timezone.utc).strftime("%H:%M:%S") if when else "--:--:--"
            one_line = " ".join(cmd.split())[:150]
            print(f"[{t}] {agent} / {tool}")
            print(f"  cmd: {one_line}")
            print(f"  причина: {'; '.join(reason)}")
            print()
    if suspects:
        print("Рекомендации по категориям:")
        print(" - «нет совпадения с allowlist» → добавить wildcard-паттерн в .claude/settings.json")
        print(" - «многострочная/цикл/nohup/подстановка» → allowlist НЕ поможет; перенести логику")
        print("   в именованную функцию/скрипт tools/ и запретить паттерн в .claude/agents/*.md")
        print(" - помнить: settings.json перечитывается только новыми (суб)агентами, не на лету")


if __name__ == "__main__":
    main()
