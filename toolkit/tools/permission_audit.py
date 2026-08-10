"""permission_audit -- reconstruct which Bash/PowerShell commands (including
subagents') LIKELY needed a manual permission prompt, and why.

Ported from HQ 2026-07-20. The heuristic logic (allowlist matching,
auto-allow, sandbox heuristics) is unchanged from the source. Two
refinements, found by an earlier pilot run of this script:

  (a) SNAPSHOT the list of transcripts and their sizes BEFORE scanning --
      a run during a live session keeps appending to the very transcript
      being scanned, so the "Scanned" count would otherwise drift between
      the start and the end of the script. Only the byte prefix fixed at
      snapshot time is read from each file, not whatever has landed there
      by the time it's actually read.
  (b) A MASKED-BY-BROAD-ALLOWLIST block -- both settings files are scanned
      for arbitrary-execution patterns (a bare interpreter / `-c` / `-e`
      before `*`, e.g. `Bash(python *)`) and an explicit warning is
      printed: such rules silently swallow part of the "no allowlist
      match" category below, without ever showing up as a suspect.

There is no direct log of "a permission dialog was shown", so the audit is
heuristic: it takes every tool_use from the current project's transcripts,
runs them through the same rules the harness itself uses (the
settings.json/settings.local.json allowlist + known auto-allow + the
"cannot be statically analyzed" sandbox heuristics), and prints the ones
that would NOT have passed without a prompt -- with a reason category and
a suggested fix.

Usage:  python tools/permission_audit.py [--minutes 120] [--all] [--session ID] [--summary]
  --minutes N  only look at commands from the last N minutes (default 180)
  --all        ignore the time-window filter
  --session S  only transcripts (main + subagents) whose path contains substring S
  --summary    a grouped summary instead of the full list

Hygiene-class breakdown of the permission audit -- a measurement, not
a decision, printed only in `--summary`
=========================================================================
Alongside the allowlist/sandbox suspect count, `--summary` also prints
a MEASUREMENT of how many scanned Bash/PowerShell calls tripped each of
tools/hygiene_gate.py's own detection classes (2>&1 / cd-Set-Location /
python -c-heredoc / a journal write bypassing Edit/Write) -- whether or
not that call ALSO needed a permission prompt. This block is a MEASURE
ONLY: it does not decide whether any class should move from WARN to
BLOCK, and it does not modify tools/hygiene_gate.py itself; that
decision, if ever made, is a separate, later move.

CLASSIFICATION SOURCE -- an IMPORT of tools/hygiene_gate.py, not a
second implementation of the same four classes (fix the class, not the
instance): `classify_hygiene()` below calls hygiene_gate's OWN signal
computation (`hygiene_gate._collect_signals`, the exact function
`_classify` itself uses to assemble a real decision) -- the same
regexes, the same scrubs (git-statement masking, -m/--message
stripping, quote-masking before a `>`/` 2>&1` check). ACCEPTED
LIMITATION: this measurement inherits whatever hygiene_gate itself is
blind to -- if the gate doesn't see some write form/pattern, this audit
doesn't either. That is the deliberate price of a single point of
truth (one classification, not two that can drift apart), not an
oversight of this addition.

The class breakdown is printed keyed by ALL SCANNED calls (comparable
to a measurement baseline that counted hits independently of the
allowlist), with, in parentheses, how many of those were ALSO suspects
(allowlist+sandbox). A single command can trip more than one class at
once -- the sum of per-class hits can EXCEED the count of commands with
>=1 class; the report prints both numbers explicitly rather than
leaving the reader to add them up.

ONE PASS, not two: `total`/suspects and the class counts are collected
by a SINGLE walk of the transcripts (`collect_audit_stats`) -- two
independent walks, each recomputing its own mtime cutoff
(`iter_tool_calls` computes `cutoff` fresh on each call), could let a
transcript whose mtime crosses the window boundary BETWEEN the two
walks land in one count and fall out of the other -- exactly the
"numbers drift" class this tool's own snapshot mechanism exists to
prevent (see "SNAPSHOT" above). `collect_suspects`/
`collect_hygiene_class_stats` remain as narrow wrappers over
`collect_audit_stats` (their own public signature/return shape is
unchanged) for any caller that only needs one of the two views; main()
below calls `collect_audit_stats()` directly, once, since it needs
both views consistently.
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

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

# A DIRECT sibling-module import only -- NOT a "try tools.hygiene_gate
# package-style, fall back to a sibling import" pattern. This kit's
# install tree lives inside a larger repository that ALSO carries its
# own top-level tools/ directory with a DIFFERENTLY BEHAVING
# hygiene_gate.py; a bare `import tools.hygiene_gate` can resolve
# "tools" as an implicit namespace package rooted at the CURRENT
# WORKING DIRECTORY (PEP 420 -- no __init__.py required) rather than
# at this file's own directory, silently picking up the WRONG module
# whenever the working directory happens to be that repo's root. The
# sys.path insertion above already guarantees a sibling `import
# hygiene_gate` resolves to THIS directory's own module unambiguously
# -- no package-style guess is needed or safe here.
import hygiene_gate

REPO = Path(__file__).resolve().parents[1]


def _default_project_key(repo: Path) -> str:
    """Derives this deployment's `~/.claude/projects/<slug>` directory name
    from its own absolute repo path, instead of hardcoding one deployment's
    slug -- a hardcoded slug would silently break this script for every
    OTHER install of this toolkit, since the slug is specific to where the
    repo happens to live on disk.

    The harness builds the slug by replacing path separators, the
    drive-letter colon, and underscores with a dash -- verified
    empirically against this machine's own `~/.claude/projects` listing
    (e.g. `D:\\Some_Repo` -> `D--Some-Repo`). Untested against every
    possible path character (dots, spaces); good enough as a default,
    override CLAUDE_PROJECTS directly if your deployment's slug does not
    match this pattern."""
    raw = str(repo.resolve())
    return re.sub(r"[\\/:_]", "-", raw)


def _resolve_claude_projects(repo: Path) -> Path:
    """The transcripts directory to scan. `CLAUDE_PROJECTS`, if set in the
    environment, is a FULL path override for this project's transcripts
    directory -- it takes precedence over the slug computed by
    `_default_project_key`, which is only a best-effort guess (see its
    docstring: untested against dots/spaces in the repo path). Use the
    override on any install where the guessed slug does not match this
    machine's actual `~/.claude/projects/<slug>` layout."""
    override = os.environ.get("CLAUDE_PROJECTS")
    if override:
        return Path(override)
    return Path(os.path.expanduser("~")) / ".claude" / "projects" / _default_project_key(repo)


PROJECT_KEY = _default_project_key(REPO)
CLAUDE_PROJECTS = _resolve_claude_projects(REPO)

# Hygiene-class labels -- VERBATIM the wording of CLAUDE.md's command
# hygiene points / tools/hygiene_gate.py's own class letters (a
# dispatcher decision, not a builder's own phrasing choice), so this
# report's lines line up with calibration wording without translation.
HYGIENE_CLASS_LABELS = [
    "2>&1",
    "cd/Set-Location",
    "python -c/heredoc",
    "journal write bypassing Edit/Write",
]

# --- commands the harness auto-allows with no allowlist entry (a practical, trimmed list) ---
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
    (re.compile(r'export\s+\w+="[^"]*\$\{?\w+'), "export VAR referencing another variable (array-subscript heuristic)"),
    (re.compile(r"\bnohup\b"), "nohup / manual backgrounding"),
    (re.compile(r"\$\("), "command substitution $(...)"),
    (re.compile(r"\bfor\s+\w+\s+in\b.*\bdo\b", re.S), "a for...do loop in shell"),
    (re.compile(r"\buntil\b|\bwhile\b.*\bdo\b", re.S), "a while/until loop"),
    (re.compile(r"&\s*$", re.M), "background launch via &"),
]

# --- refinement (b): allowlist patterns that amount to near-arbitrary code execution ---
INTERPRETER_HEADS = {
    "python", "python3", "py", "node", "ruby", "perl", "bash", "sh", "zsh",
    "powershell", "pwsh", "osascript", "php",
}
CODE_FLAGS = {"-c", "-e", "--command"}


def _iter_allow_entries():
    """(file_name, tool, pattern) across both settings files, raw allow entries."""
    for name in ("settings.json", "settings.local.json"):
        p = REPO / ".claude" / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] could not read {name}: {e}", file=sys.stderr)
            continue
        for entry in data.get("permissions", {}).get("allow", []):
            m = re.match(r"^(\w+)\((.*)\)$", entry, re.S)
            if m:
                yield name, m.group(1), m.group(2)
            else:
                yield name, entry, ""  # a bare tool name with no pattern, e.g. WebSearch


def load_allow_patterns() -> list[tuple[str, str]]:
    """[(tool, pattern), ...] from settings.json + settings.local.json."""
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
        elif " *" in pat:  # the "foo *" form -- a prefix up to the asterisk
            if cmd.startswith(pat.split(" *")[0]):
                return True
        elif fnmatch.fnmatch(cmd, pat) or cmd == pat:
            return True
    return False


def is_auto_allowed(cmd: str) -> bool:
    """A rough approximation of the harness's built-in auto-allow (simple
    single-line commands only)."""
    if "\n" in cmd.strip():
        return False
    # a chain -- every part must be auto-allowed
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
        flags.append("a multi-line command (multiple statements in one call)")
    return flags


_ENV_ASSIGN_RE = re.compile(r"^\w+=\S*$")


def is_broad_wildcard(tool: str, pat: str) -> str | None:
    """If pat is an allowlist pattern that lets through arbitrary
    execution (a bare interpreter before `*`, an interpreter with a
    -c/-e flag before `*`, including one with an unclosed opening quote
    right after the flag, optionally behind a VAR=val prefix) -- return
    the reason as a string. Otherwise None. Example findings: Bash(python
    *), Bash(python -c ' *), Bash(PYTHONUTF8=1 python -c ' *)."""
    if tool not in ("Bash", "PowerShell"):
        return None
    p = pat.strip()
    if not p.endswith("*"):
        return None
    prefix = p[:-1].strip()
    tokens = prefix.split()
    while tokens and _ENV_ASSIGN_RE.match(tokens[0]):
        tokens = tokens[1:]  # skip VAR=val ahead of the interpreter name
    if not tokens:
        return None
    head = os.path.basename(tokens[0].strip("\"'")).lower().removesuffix(".exe")
    if head not in INTERPRETER_HEADS:
        return None
    rest = tokens[1:]
    if not rest:
        return f"a bare interpreter with no arguments -- lets arbitrary code through after '{head}'"
    if rest[0] in CODE_FLAGS:
        remainder = "".join(rest[1:]).strip("'\"")
        if not remainder:
            return f"'{head} {rest[0]}' -- arbitrary one-line code passes without a prompt"
    # `<interpreter> -m *` lets through an arbitrary MODULE (python -m
    # http.server, -m pip, ...) -- the same class as -c/-e.
    if rest[0] == "-m" and not "".join(rest[1:]).strip("'\""):
        return f"'{head} -m' -- an arbitrary module passes without a prompt"
    return None


def scan_broad_wildcards() -> list[tuple[str, str, str, str]]:
    """[(settings file, tool, pattern, reason), ...] for broad wildcard
    patterns that silently swallow the "no allowlist match" category
    (refinement b)."""
    out = []
    for fname, tool, pat in _iter_allow_entries():
        reason = is_broad_wildcard(tool, pat)
        if reason:
            out.append((fname, tool, pat, reason))
    return out


def check_transcripts_present(claude_projects: Path | None = None) -> bool:
    """Warn loudly on stderr (not an exception -- the scan continues with
    zero) when the transcripts directory does not exist, or exists but
    the glob finds zero files. Silent-zero symptom: an install whose
    computed/overridden slug does not match this machine's real
    `~/.claude/projects/<slug>` layout otherwise just prints "Scanned 0"
    with no hint why. Returns True iff it printed the warning."""
    cp = claude_projects if claude_projects is not None else CLAUDE_PROJECTS
    n = 0
    if cp.exists():
        n = len(list(cp.glob("*.jsonl"))) + len(list(cp.glob("*/subagents/agent-*.jsonl")))
    if not cp.exists() or n == 0:
        print(
            f"WARNING: 0 transcripts found at {cp} - likely a wrong project slug; "
            "set CLAUDE_PROJECTS to the correct '~/.claude/projects/<slug>' directory",
            file=sys.stderr,
        )
        return True
    return False


def snapshot_transcripts(session: str | None = None) -> list[tuple[Path, str, int]]:
    """[(path, agent_type, size_at_snapshot), ...] -- fix the list of
    transcripts and their sizes BEFORE scanning (refinement a): a run
    during a live session keeps appending to the very transcript being
    scanned, and without a snapshot the "Scanned" count would drift
    between the start and the end of the script. The scan below reads
    only these first size_at_snapshot bytes of each file -- anything
    appended after the snapshot is ignored."""
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
    """Read the first `size` bytes of the file (fixed by the snapshot)
    and return complete lines; a possibly-truncated last line right at
    the boundary is dropped."""
    try:
        with open(path, "rb") as fb:
            data = fb.read(size)
    except OSError:
        return []
    text = data.decode("utf-8", errors="replace")
    if not text.endswith("\n") and "\n" in text:
        text = text[: text.rfind("\n") + 1]
    elif not text.endswith("\n"):
        text = ""  # the file's only line was cut off right at the snapshot boundary
    return text.splitlines()


def iter_tool_calls(minutes: float | None, session: str | None = None,
                     snapshot: list[tuple[Path, str, int]] | None = None):
    """(when, source, agent_type, tool, command) over the project's
    transcript snapshot."""
    cutoff = None if minutes is None else time.time() - minutes * 60
    if snapshot is None:
        snapshot = snapshot_transcripts(session)

    for path, source, size in snapshot:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if cutoff and mtime < cutoff:
            continue  # the file hasn't changed within the window -- skip it entirely
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


def _suspect_reason(tool: str, cmd: str, patterns) -> list[str] | None:
    """The shared suspect-determination core, pulled out of
    collect_suspects (fix the class, not the instance -- the same
    logic is needed by collect_hygiene_class_stats below; a second copy
    is not made). None -- the command is NOT a suspect; otherwise the
    list of reasons (as before)."""
    allowed = matches_allow(tool, cmd, patterns)
    flags = sandbox_flags(cmd)
    if (allowed and not flags) or is_auto_allowed(cmd):
        return None
    reason = []
    if not allowed:
        reason.append("no allowlist match")
    reason += flags
    return reason


def classify_hygiene(command) -> list[str]:
    """The list of hygiene classes a SINGLE command TRIPS -- classes are
    INDEPENDENT (one command can trip several at once). Classification
    source: an IMPORT of tools/hygiene_gate.py -- a second implementation
    of the same regexes/scrubs here is forbidden (see the module
    docstring's "CLASSIFICATION SOURCE"). Calls
    `hygiene_gate._collect_signals(command)` -- the exact function
    `_classify` itself uses to assemble a real decision -- a single
    source of truth, not a parallel one that can drift from the gate.

    `command` not a string / None / an empty string -> [] with no
    exception -- the class is simply not counted, the script does not
    crash."""
    if not isinstance(command, str) or not command:
        return []
    signals = hygiene_gate._collect_signals(command)
    classes = []
    if signals["redirect"]:
        classes.append("2>&1")
    if signals["cd"]:
        classes.append("cd/Set-Location")
    if signals["pyc"]:
        classes.append("python -c/heredoc")
    if signals["journal"]:
        classes.append("journal write bypassing Edit/Write")
    return classes


def collect_audit_stats(minutes: float | None, session: str | None = None,
                         snapshot: list[tuple[Path, str, int]] | None = None):
    """A SINGLE walk of `iter_tool_calls` -- suspects, total, AND the
    hygiene class counts are collected from the SAME sample in ONE
    iteration, with the mtime cutoff (computed inside `iter_tool_calls`
    on first use of the generator) happening EXACTLY ONCE.

    Two INDEPENDENT walks (each calling `iter_tool_calls(...)` afresh,
    each recomputing `cutoff = time.time() - minutes * 60` on its own)
    could let a transcript whose mtime crosses the window boundary
    BETWEEN the two walks land in one count and fall out of the other --
    exactly the "numbers drift" class this tool's own transcript
    snapshot exists to prevent (see the module docstring's
    "SNAPSHOT"/refinement (a)). Especially inappropriate for a
    MEASUREMENT tool (the hygiene-class breakdown): incomparable
    `total` and class counts would defeat any comparison against a
    calibration baseline.

    The single entry point for main(): one pass over
    `iter_tool_calls(minutes, session, snapshot)`, `total`/`suspects`/
    class counts all accumulated in ONE loop body over the same
    `when/agent/tool/cmd`. `collect_suspects`/
    `collect_hygiene_class_stats` below remain as narrow wrappers
    (their own public signature/return shape unchanged) -- but each
    still makes its OWN separate call here, i.e. its OWN separate walk
    -- a caller that needs BOTH sets of numbers at once and consistent
    (main(), the only such caller in this file) must call
    `collect_audit_stats()` directly, once, rather than both getters
    separately; main() below is written that way.

    Returns (suspects, total, class_counts, class_suspect_counts,
    any_class_count) -- the same value shapes the two functions had
    separately, just from one pass."""
    patterns = load_allow_patterns()
    suspects = []
    total = 0
    class_counts = {label: 0 for label in HYGIENE_CLASS_LABELS}
    class_suspect_counts = {label: 0 for label in HYGIENE_CLASS_LABELS}
    any_class_count = 0
    for when, fname, agent, tool, cmd in iter_tool_calls(minutes, session, snapshot):
        total += 1
        reason = _suspect_reason(tool, cmd, patterns)
        is_suspect = reason is not None
        if is_suspect:
            suspects.append((when, agent, tool, cmd, reason))
        classes = classify_hygiene(cmd)
        if classes:
            any_class_count += 1
            for c in classes:
                class_counts[c] += 1
                if is_suspect:
                    class_suspect_counts[c] += 1
    return suspects, total, class_counts, class_suspect_counts, any_class_count


def collect_suspects(minutes: float | None, session: str | None = None,
                      snapshot: list[tuple[Path, str, int]] | None = None):
    """Run every tool_use through the allowlist + sandbox heuristics.

    Returns (suspects, total), where suspects is a list of
    (when, agent, tool, cmd, reason) for commands that LIKELY needed a
    manual permission prompt. Pulled out of main() as a separate pure
    function so unit tests can check the filtering without parsing
    stdout.

    A narrow wrapper over `collect_audit_stats` (see its docstring) --
    signature and return shape are unchanged. Calling this function on
    its own is still a separate walk; main() does NOT call this
    function (see collect_audit_stats), to avoid walking twice."""
    suspects, total, *_rest = collect_audit_stats(minutes, session, snapshot)
    return suspects, total


def collect_hygiene_class_stats(minutes: float | None, session: str | None = None,
                                 snapshot: list[tuple[Path, str, int]] | None = None):
    """Run ALL scanned calls (not only suspects -- otherwise the
    measurement is not comparable to a calibration baseline that
    counted hits independently of the allowlist) through
    classify_hygiene().

    Returns (class_counts, class_suspect_counts, any_class_count):
      - class_counts: {class: N} -- the number of HITS of the class
        among all scanned calls (double-counted: a command with two
        classes increments both);
      - class_suspect_counts: {class: N} -- the same count, but only
        for calls that are ALSO suspects (the same criterion as
        collect_suspects, the shared _suspect_reason core);
      - any_class_count: the number of COMMANDS (not hits) that tripped
        at least one class -- the sum of class_counts.values() can
        EXCEED this number when one command trips more than one class.

    A narrow wrapper over `collect_audit_stats` (see its docstring) --
    signature and return shape are unchanged. Calling this function on
    its own is still a separate walk; main() does NOT call this
    function (see collect_audit_stats)."""
    _suspects, _total, class_counts, class_suspect_counts, any_class_count = (
        collect_audit_stats(minutes, session, snapshot))
    return class_counts, class_suspect_counts, any_class_count


def main(argv=None):
    if os.name == "nt":  # some Windows console codepages choke on non-ASCII -- force utf-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=180)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--session", help="filter: only transcripts whose path contains this substring (a session id)")
    ap.add_argument("--summary", action="store_true", help="a grouped summary instead of the full list")
    args = ap.parse_args(argv)
    minutes = None if getattr(args, "all") else args.minutes

    check_transcripts_present()

    # refinement (b): warn about broad allowlist patterns -- before the summary
    broad = scan_broad_wildcards()
    if broad:
        print("MASKED-BY-BROAD-ALLOWLIST:")
        print("  These allowlist rules let through arbitrary code execution and SILENTLY")
        print("  swallow part of the \"no allowlist match\" category below -- commands under")
        print("  them never even reach the suspects list, even though they may in fact be the wrong form:")
        for fname, tool, pat, reason in broad:
            print(f"  - {fname}: {tool}({pat}) -- {reason}")
        print()

    snapshot = snapshot_transcripts(args.session)
    # A SINGLE call to collect_audit_stats: total, suspects, AND the
    # hygiene-class counts all come from ONE pass over the same
    # snapshot/mtime cutoff (see its docstring). Do NOT call
    # collect_suspects + collect_hygiene_class_stats separately here --
    # that would reintroduce exactly the bug collect_audit_stats fixes
    # (two independent walks, numbers drifting between them).
    suspects, total, class_counts, class_suspect_counts, any_class_count = (
        collect_audit_stats(minutes, args.session, snapshot))

    print(f"Scanned Bash/PowerShell calls: {total}"
          + ("" if minutes is None else f" (in the last {minutes:g} min)")
          + (f" - session *{args.session[:8]}*" if args.session else ""))
    print(f"Likely needed confirmation: {len(suspects)}\n")

    if args.summary:
        from collections import Counter
        by_agent = Counter(a for _, a, *_ in suspects)
        by_reason = Counter(r for *_, reasons in suspects for r in reasons)
        examples: dict[str, str] = {}
        for _, agent, _tool, cmd, reasons in suspects:
            for r in reasons:
                examples.setdefault(r, " ".join(cmd.split())[:110])
        print("By agent:")
        for a, n in by_agent.most_common():
            print(f"  {n:4d}  {a}")
        print("\nBy reason:")
        for r, n in by_reason.most_common():
            print(f"  {n:4d}  {r}")
            print(f"        example: {examples[r]}")

        # A measurement, not a decision (see the module docstring): a
        # DIFFERENT sample (all scanned calls, not only suspects), but
        # from the SAME pass as total/suspects above -- the header says
        # so explicitly so the reader doesn't add incompatible numbers
        # from the blocks above.
        print("\nBy hygiene class (all scanned calls; in parens -- how many of them are suspects):")
        for label in HYGIENE_CLASS_LABELS:
            print(f"  {class_counts[label]:4d}  {label}  (suspects: {class_suspect_counts[label]})")
        print(f"  commands with >=1 class: {any_class_count}")
    else:
        for when, agent, tool, cmd, reason in suspects:
            t = datetime.fromtimestamp(when, tz=timezone.utc).strftime("%H:%M:%S") if when else "--:--:--"
            one_line = " ".join(cmd.split())[:150]
            print(f"[{t}] {agent} / {tool}")
            print(f"  cmd: {one_line}")
            print(f"  reason: {'; '.join(reason)}")
            print()
    if suspects:
        print("Recommendations by category:")
        print(" - \"no allowlist match\" -> add a wildcard pattern to .claude/settings.json")
        print(" - \"multi-line/loop/nohup/substitution\" -> the allowlist will NOT help; move the logic")
        print("   into a named function/script under tools/ and forbid the pattern in .claude/agents/*.md")
        print(" - remember: settings.json is only re-read by NEW (sub)agents, not on the fly")


if __name__ == "__main__":
    main()
