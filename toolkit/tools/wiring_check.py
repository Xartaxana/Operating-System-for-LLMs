"""wiring_check.py -- generalized host-wiring checker (D-0092/D-0093).

Read-only auditor of whether the kit's enforcement chain is actually
wired into a host repo, independent of what any single mechanism's own
SessionStart output claims. Patterns are drawn from the staff
deployment's wiring channel in tools/session_context.py (its
git_hooks_channel/harness_channel functions) -- this module is a
standalone, more general reimplementation, not an import of that file:
it is meant to run against ANY host repo this kit is installed into,
not just this one, and deliberately carries no dependency on
tools/session_context.py so the two can evolve independently. The
converse dependency direction IS used: tools/session_context.py imports
this module for its single summary WIRING line (see that file's
`wiring_summary_line`).

Division of labor with tools/session_context.py (avoids double-reporting
the same fact two different ways): this module is READ-ONLY -- it never
writes to git config or anywhere else. The one WRITE action in this
area (self-healing an unset core.hooksPath) lives in
tools/session_context.py's `hooks_path_autofix_line`, which runs once
per SessionStart, before this module's checks would otherwise flag the
same gap. Running `python tools/wiring_check.py --check` right after a
SessionStart that just autofixed hooksPath will therefore usually find
it already resolved.

CHECKS (each returns a list of issue strings; empty = that check is
clean):

 (1) check_git_hooks_path -- core.hooksPath resolves to <root>/.githooks.
 (2) check_required_hooks -- pre-commit and commit-msg are both present
     as files AND tracked in the git INDEX with mode 100755 (read via
     `git ls-files -s`, the INDEX, not the filesystem: a hook committed
     as mode 100644 is silently skipped by git on a Linux clone --
     Windows/NTFS carries no meaningful exec bit at all, so this cannot
     be observed via os.stat(); F-53/D-0093). Two independent sub-facts
     per hook, both reportable: untracked (missing from the index
     entirely -- a fresh clone gets NO gate at all, worse than
     non-executable) vs tracked-but-wrong-mode.
 (3) check_harness_hooks -- every "python tools/<file>.py" hook command
     named in .claude/settings.json points to a file that EXISTS.
     Existence only, deliberately no import check (unlike the staff
     deployment's harness_channel): this module runs against arbitrary
     host repos, and importing arbitrary host code as a side effect of
     a read-only auditor is out of scope.
 (4) check_adoption_ledger -- if <root>/ADOPTION_LEDGER.md exists (the
     host's filled-in copy of ADOPTION_LEDGER.template.md, not the
     template itself), every row whose Status cell is exactly "adopt"
     AND whose "Kit mechanism" cell names the git-hooks or
     harness-hooks machinery checks (1)-(3) above already cover is
     cross-checked against the issues those checks found (D-0092: an
     "adopt" row with an open issue on the wiring it claims is a WARN).
     Deliberately NARROW: reconciling an arbitrary ledger row ("Skills",
     "PROCESS docs", ...) against a concrete live fact is not
     well-defined for most rows in the template -- only rows naming
     git-hooks/harness-hooks machinery are reconciled; every other row
     is left alone rather than guessed at (silence there is not a false
     claim). No ADOPTION_LEDGER.md at all is not an error -- most hosts
     running this tool will not carry one yet. A ledger that exists but
     fails to read/parse degrades to ONE WARN naming the failure
     (fail-open: a corrupt ledger must not blank out the git/harness
     issues the checks above it already found).
 (5) check_untracked_enforcement_files -- a file present on disk under
     .githooks/ that git does not track AT ALL (beyond the two required,
     named hooks check (2) already covers by name) is a WARN: it was
     never `git add`-ed, so it is invisible to a fresh clone and does
     nothing there regardless of its content or permissions.

Every check function is self-contained and fails OPEN: a subprocess
call that cannot even run (git missing, timeout) or a file that cannot
be read becomes ONE issue string describing the failure, never an
uncaught exception -- check_wiring() itself has no try/except of its
own because every check it aggregates has already turned its own
failure modes into strings.

FORM (spec-required): a CLI (`python tools/wiring_check.py --check`,
exit 0 when clean / 1 when any issue was found, a human-readable
report on stdout) plus the importable `check_wiring(root) -> dict`
function -- the CLI is a thin wrapper around exactly that function,
so the two forms can never disagree.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

_GITHOOKS_DIRNAME = ".githooks"
_REQUIRED_GITHOOKS = ("pre-commit", "commit-msg")
_SETTINGS_RELPATH = Path(".claude") / "settings.json"
_ADOPTION_LEDGER_NAME = "ADOPTION_LEDGER.md"

# The one command shape every hook line in .claude/settings.json is
# expected to use: exactly "python tools/<file>.py", no extra flags,
# forward slashes. Anything else is reported as an honest "unparsed
# hook command" issue rather than guessed at. `[^/\\]+` (not `[\w ]+`)
# deliberately allows spaces in the filename so a path-with-spaces
# command is still recognized and checked, not silently misparsed.
_HOOK_COMMAND_RE = re.compile(r"^python tools/([^/\\]+\.py)$")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run_git(args: list, root: Path):
    """Runs a git subcommand with a short timeout, capturing output as
    text. Returns None (never raises) on ANY failure to even launch the
    process (git missing from PATH, a timeout, a permissions error) --
    callers treat None as "could not determine this fact", distinct
    from a clean non-zero exit (which git itself can produce for benign
    reasons, e.g. an unset config key)."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None


def check_git_hooks_path(root: Path) -> list:
    """(1) core.hooksPath resolves to <root>/.githooks. READ-ONLY -- no
    autofix here (see module docstring: the one write action lives in
    tools/session_context.py, run once at SessionStart, before this
    check would otherwise flag the same gap)."""
    expected = (root / _GITHOOKS_DIRNAME).resolve()
    result = _run_git(["config", "core.hooksPath"], root)
    if result is None:
        return ["git config core.hooksPath failed to run (git unavailable?)"]

    raw = (result.stdout or "").strip()
    if result.returncode != 0 or not raw:
        return ["core.hooksPath not set"]

    configured = Path(raw)
    if not configured.is_absolute():
        configured = root / configured
    try:
        configured_resolved = configured.resolve()
    except OSError:
        configured_resolved = configured
    if configured_resolved != expected:
        return [f"core.hooksPath={raw!r} does not resolve to {expected}"]
    return []


def check_required_hooks(root: Path) -> list:
    """(2) pre-commit/commit-msg present as files AND tracked in the git
    INDEX with mode 100755 -- see the module docstring for why the
    index (not the filesystem) is the source of truth here."""
    issues = []
    for name in _REQUIRED_GITHOOKS:
        if not (root / _GITHOOKS_DIRNAME / name).is_file():
            issues.append(f"hook file missing: {_GITHOOKS_DIRNAME}/{name}")

    result = _run_git(["ls-files", "-s", "--", _GITHOOKS_DIRNAME], root)
    if result is None or result.returncode != 0:
        issues.append("git ls-files -s failed -- cannot verify hook exec bits")
        return issues

    modes = {}
    for line in (result.stdout or "").splitlines():
        meta, sep, path_part = line.partition("\t")
        if not sep:
            continue
        fields = meta.split()
        if not fields:
            continue
        modes[Path(path_part).name] = fields[0]

    for name in _REQUIRED_GITHOOKS:
        if name not in modes:
            issues.append(f"hook {name} untracked in git index -- clones get no gate")
        elif modes[name] != "100755":
            issues.append(
                f"hook {name} committed non-executable ({modes[name]}) --"
                " Linux clones get a silently dead gate (D-0093)"
            )
    return issues


def _parse_hook_commands(settings) -> list:
    """Walks every hooks section of a parsed .claude/settings.json,
    collecting each hook's raw command string. Tolerant of any
    malformed shape -- a piece that isn't a dict/list where expected is
    simply skipped, never raised on."""
    commands = []
    hooks_root = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks_root, dict):
        return commands
    for matchers in hooks_root.values():
        if not isinstance(matchers, list):
            continue
        for matcher in matchers:
            if not isinstance(matcher, dict):
                continue
            entries = matcher.get("hooks")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command")
                if isinstance(command, str) and command:
                    commands.append(command)
    return commands


def check_harness_hooks(root: Path) -> list:
    """(3) every "python tools/<file>.py" hook command in
    .claude/settings.json names a file that exists. Existence-only, see
    module docstring for why no import check is done here."""
    settings_path = root / _SETTINGS_RELPATH
    try:
        text = settings_path.read_text(encoding="utf-8")
    except Exception as e:
        # Broad catch, deliberately not just OSError: a settings.json
        # saved with invalid UTF-8 bytes raises UnicodeDecodeError (a
        # ValueError subclass, not an OSError) -- must fail open the
        # same as a permissions/missing-file error, not escape uncaught.
        return [f"{settings_path} not readable ({type(e).__name__})"]

    try:
        settings = json.loads(text)
    except Exception as e:
        return [f"{settings_path} not valid JSON ({type(e).__name__})"]

    issues = []
    seen = set()
    for command in _parse_hook_commands(settings):
        m = _HOOK_COMMAND_RE.match(command.strip())
        if not m:
            issues.append(f"unparsed hook command: {command.strip()}")
            continue
        filename = m.group(1)
        if filename in seen:
            continue
        seen.add(filename)
        if not (root / "tools" / filename).is_file():
            issues.append(f"hook file not found: tools/{filename}")
    return issues


def check_untracked_enforcement_files(root: Path) -> list:
    """(5) a file present on disk under .githooks/ that git does not
    track at all -- never `git add`-ed, invisible to a fresh clone. No
    .githooks/ directory at all is not itself an issue here (that gap
    is check_required_hooks's/check_git_hooks_path's job to report)."""
    githooks_dir = root / _GITHOOKS_DIRNAME
    if not githooks_dir.is_dir():
        return []

    try:
        on_disk = {p.name for p in githooks_dir.iterdir() if p.is_file()}
    except OSError:
        return []

    result = _run_git(["ls-files", "--", _GITHOOKS_DIRNAME], root)
    if result is None or result.returncode != 0:
        return ["git ls-files failed -- cannot verify untracked files under .githooks"]

    tracked = {Path(line).name for line in (result.stdout or "").splitlines() if line.strip()}
    untracked = sorted(on_disk - tracked)
    return [f"untracked enforcement file: {_GITHOOKS_DIRNAME}/{name}" for name in untracked]


# See module docstring, check (4): deliberately narrow keyword sets --
# only ledger rows naming machinery checks (1)-(3) above already cover
# are reconciled; every other row is left alone.
_GIT_HOOKS_ROW_KEYWORDS = (".githooks", "hookspath", "commit-msg", "pre-commit", "mechanism gate")
_HARNESS_HOOKS_ROW_KEYWORDS = ("settings.json", "sessionstart", "session_context.py")

_LEDGER_ROW_RE = re.compile(r"^\|(.+?)\|(.+?)\|(.+?)\|\s*$")


def _parse_ledger_adopt_rows(text: str) -> list:
    """Parses ADOPTION_LEDGER.md's pipe-table rows, returns the "Kit
    mechanism" cell text of every row whose Status cell is exactly
    "adopt" (case-insensitive, trimmed). The header row's Status cell
    literally reads "Status" and the separator row is all dashes --
    neither matches "adopt", so both are skipped without special-casing
    them. A line that doesn't match the 3-cell pipe pattern (prose,
    section headers, a malformed row) is silently skipped, not raised
    on -- this function has no try/except of its own, callers decide
    whether a total parse failure (e.g. the read itself failing) is
    fail-open."""
    rows = []
    for line in text.splitlines():
        m = _LEDGER_ROW_RE.match(line.strip())
        if not m:
            continue
        mechanism, status, _basis = m.groups()
        if status.strip().lower() == "adopt":
            rows.append(mechanism.strip())
    return rows


def check_adoption_ledger(root: Path, git_issues: list, harness_issues: list) -> list:
    """(4, D-0092): see module docstring for the full rationale and its
    deliberately narrow scope. git_issues/harness_issues are the
    already-computed outputs of the checks above (passed in rather than
    recomputed) so the whole reconciliation reads one consistent
    snapshot of the wiring state, not a second, possibly-different git
    invocation."""
    ledger_path = root / _ADOPTION_LEDGER_NAME
    if not ledger_path.is_file():
        return []

    try:
        text = ledger_path.read_text(encoding="utf-8")
    except Exception as e:
        # Broad catch, deliberately not just OSError -- same rationale
        # as check_harness_hooks: an invalid-UTF-8 ledger file must
        # still fail open to a WARN, not raise UnicodeDecodeError past
        # check_wiring()'s "never raises" contract.
        return [f"{_ADOPTION_LEDGER_NAME} not readable ({type(e).__name__})"]

    try:
        adopt_rows = _parse_ledger_adopt_rows(text)
    except Exception as e:
        return [f"{_ADOPTION_LEDGER_NAME} not parseable ({type(e).__name__})"]

    issues = []
    has_git_issue = bool(git_issues)
    has_harness_issue = bool(harness_issues)
    for mechanism in adopt_rows:
        low = mechanism.lower()
        if has_git_issue and any(k in low for k in _GIT_HOOKS_ROW_KEYWORDS):
            issues.append(
                f"adoption ledger row '{mechanism}' is 'adopt' but git-hooks wiring has an open issue"
            )
        if has_harness_issue and any(k in low for k in _HARNESS_HOOKS_ROW_KEYWORDS):
            issues.append(
                f"adoption ledger row '{mechanism}' is 'adopt' but harness-hooks wiring has an open issue"
            )
    return issues


def check_wiring(root: Path = None) -> dict:
    """Runs every check above and aggregates them into
    {"ok": bool, "issues": [str, ...]}. Never raises: each check
    function already fails open (a subprocess/file/parse error becomes
    an issue string, not an exception) -- this is a thin aggregator
    with no I/O of its own beyond what the checks already perform."""
    root = Path(root) if root else repo_root()
    git_issues = check_git_hooks_path(root) + check_required_hooks(root)
    harness_issues = check_harness_hooks(root)
    untracked_issues = check_untracked_enforcement_files(root)
    ledger_issues = check_adoption_ledger(root, git_issues, harness_issues)
    issues = git_issues + harness_issues + untracked_issues + ledger_issues
    return {"ok": not issues, "issues": issues}


def main(argv=None) -> int:
    """CLI form: `python tools/wiring_check.py --check`. The --check
    flag is the documented invocation shape; this function runs the
    same check_wiring() regardless of argv (there is only one mode), so
    an unrecognized or missing flag never diverges from the importable
    function's own behavior."""
    _ = sys.argv[1:] if argv is None else argv
    root = repo_root()
    result = check_wiring(root)
    if result["ok"]:
        print("WIRING: OK")
        return 0
    print(f"WIRING: {len(result['issues'])} issue(s)")
    for issue in result["issues"]:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
