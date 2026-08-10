"""tools/wiring_check.py -- thin, standalone CLI wrapper around the
WIRING-INTEGRITY checks already implemented in tools/session_context.py
(the SessionStart hook's WIRING block: git_hooks_channel(),
harness_channel(), python_channel(), _ascii_sanitize()) -- see that
file's own "WIRING-INTEGRITY block" section, right before
build_context_lines(). This file does NOT reimplement any of that
logic: it imports the four functions above from session_context (a
plain `import session_context` resolves because when this script runs
as `python tools/wiring_check.py` from the repo root, Python inserts
this script's own directory -- tools/ -- at sys.path[0], and
session_context.py lives right next to it) and calls them. The ONE
piece of logic that is NEW here, not borrowed, is
`skills_casing_channel()` below -- see its own docstring.

ORIGIN (coordinator respec, 2026-07-29, following a spec-reality
divergence found and reported by the builder -- see the delivery
report / journal for the full exchange): the originating dispatch
(part D) assumed tools/wiring_check.py already existed as a
standalone module with its own established git-index-reading pattern
and WIRING line format. On THIS path (tools/wiring_check.py) it did
not -- the WIRING-INTEGRITY checks live inside tools/session_context.py
instead (this repo's actual pair on SIBLING_MAP axis 1, "session_context
hooks/index mods"). This file is the thin CLI the respec asks for: it
makes the ALREADY-LIVE session_context checks runnable as
`python tools/wiring_check.py` (the shape
tools/enforcement_probe.py's design already assumed), without
duplicating their logic.

KIT-TWIN NOTE (critic t-339, D-0043-class sibling report -- an
analog, not a fix, since the two files are not the same class of gap):
`toolkit/tools/wiring_check.py` DOES already exist, under a DIFFERENT
contract -- a read-only, general-purpose host-wiring auditor for ANY
repo the kit is installed into (its own `--check` CLI flag, no
dependency on this repo's tools/session_context.py, checks like
core.hooksPath / required-hook-tracking / harness-hook-existence /
adoption-ledger reconciliation -- see that file's own docstring). It
is NOT the same module as this one: this file is specific to THIS
repo (imports tools/session_context.py directly, no `--check` flag,
adds the skills-casing channel), and toolkit/tools/wiring_check.py is
under the D-0074 moratorium (out of scope for this delivery, not
touched). Whether the two should ever converge, and how axis 1 of
SIBLING_MAP should read once both tools/wiring_check.py files exist
side by side (one per repo, different contracts) is the Lead's call at
acceptance, not decided here.

session_context.py itself is NOT touched by this delivery (non-goal,
per D-0069: it is a self-activating SessionStart hook registered in
.claude/settings.json; wiring the skills-casing channel into IT, if
ever desired, is the coordinator's call at acceptance, not this
file's).

NEW: skills_casing_channel(root) (respec point 2) -- every git-INDEX
path under .claude/skills/ whose basename, lowercased, equals
"skill.md" must be tracked as EXACTLY "SKILL.md". Motive: on a
case-insensitive filesystem (this Windows host), a lowercase
skill.md already committed to the index makes a later `git add
.../SKILL.md` SILENTLY no-op (git treats the path as "the same file,
unchanged casing" case-insensitively) while the command itself reports
success -- the file that is actually live on disk never gets its
correct-cased entry into the index. This is the exact incident the
sibling Dog deployment hit on 2026-07-25 and reported again in its
2026-07-29 synk (docs/tasks/2026-07-29_dog-incoming-sync.md, item 2).
Same subprocess idiom as session_context.git_hooks_channel()'s own
`git ls-files -s` call: timeout=5, any failure (git missing, timeout,
non-zero exit) folds into ONE warning about unverifiability rather
than raising -- this channel is read-only and must never turn a
missing/broken git into a crash.

CLI CONTRACT (respec point 3): main() collects every warning string
from all four channels (git, harness, skills-casing, python). Empty ->
print ONE "WIRING: OK (git hooks: ...; harness hooks: N files
importable; skills casing: M ok; python: <path>)" line, exit 0.
Non-empty -> print one "WIRING WARNING: <fact>" line per fact, exit 1.
An internal, unforeseen failure (an exception escaping the channel
calls themselves, not one of their own already-folded warnings) prints
one warning line and ALSO exits 1 -- this is this file's ONE
deliberate divergence from session_context.wiring_lines()'s own
fail-OPEN contract (a wiring failure there degrades to a warning line
inside a SessionStart hook that must never block a session boot);
here, as a CHECKER meant to gate a commit (via
tools/enforcement_probe.py's subprocess call), a checker that
cannot even determine wiring state has to be reported as a failure,
not silently waved through as "nothing wrong found". Nothing about
this file registers it anywhere: it is not a hook, not referenced by
.claude/settings.json or .githooks/* -- tools/enforcement_probe.py
already targets `python tools/wiring_check.py` and will simply start
finding this file instead of failing to launch it, with no changes to
that file needed.

F3 (critic t-339) -- AUTOFIX FACTS ARE NOT WARNINGS: session_context.
git_hooks_channel() can return a fact prefixed with
session_context._AUTOFIX_FACT_PREFIX ("AUTOFIX: ...") when its
inherited VG-1 self-heal (`_try_hookspath_autofix`) successfully
writes `core.hooksPath` because it was UNSET -- this is a RESOLVED
discrepancy, not an open one, and treating it as an ordinary warning
would (a) misreport a fixed problem as still-broken in the printed
line and (b) wrongly flip the exit code to 1 on a commit whose wiring
is now actually fine. Fixed: main() below separates AUTOFIX-prefixed
facts from `git_warnings` BEFORE computing the warning list / exit
code, and renders EVERY fact (autofix or warning) through the SAME
imported `session_context._wiring_line_for()` helper that
session_context.py's own wiring_lines() already uses for this exact
distinction ("WIRING AUTOFIX: ..." vs "WIRING WARNING: ..."), instead
of reimplementing the prefix check here. An AUTOFIX line is always
printed (when present) whether or not the overall run exits 0 or 1 --
it is informational either way.

LEAD DECISION, RECORDED (per the coordinator's respec, not decided by
this file's author): autofix STAYS ENABLED. This CLI is therefore NOT
strictly read-only -- the inherited VG-1 self-heal writes local git
config (`git config --local core.hooksPath .githooks`) ONLY when
core.hooksPath is UNSET (never when it is set to something else, see
session_context._try_hookspath_autofix's own docstring for that
carve-out). This is intentional, including when this CLI runs from
inside a pre-commit context (via tools/enforcement_probe.py's
subprocess call) -- a commit that would otherwise be rejected purely
for an unset hooksPath instead self-heals and proceeds, which is
judged the more useful behavior than blocking on a gap this file can
already fix for free. This was NOT this builder's call; recorded here
per the coordinator's explicit instruction to fix it in the docstring.
"""
import subprocess
import sys
from pathlib import Path

import session_context


def skills_casing_channel(root):
    """(d) skills-casing channel -- see module docstring "NEW" section
    for the full incident motive. Returns (warnings, ok_count), same
    shape as session_context.harness_channel(): warnings is a list of
    detail strings (empty = every skill.md-named index path is
    correctly cased); ok_count is the number of correctly-cased
    SKILL.md index entries found, used for the OK line's "skills
    casing: M ok". Never raises: a git failure (missing binary,
    timeout, non-zero exit -- e.g. run outside a git repo) folds into
    ONE warning naming the check as unverifiable, the same fold-to-
    warning contract session_context.git_hooks_channel() already uses
    for its own `git ls-files -s` call.

    B8 FIX (2026-08-10, sibling of the same class fixed in
    session_context.git_hooks_channel() and toolkit/tools/wiring_check.py's
    `_run_git`): passes `encoding="utf-8", errors="replace"` instead of a
    bare `text=True` (a non-UTF-8 console locale -- cp1251 on this host --
    would otherwise silently MOJIBAKE any non-ASCII git output before this
    channel ever compares it), and runs with `-c core.quotepath=false` (a
    per-invocation override, does not touch the host repo's own config) --
    git's default quotepath=true octal-escapes a non-ASCII tracked path in
    `ls-files` output, which this function's `Path(path_str).name` parsing
    does not recognize, so a real mis-casing under a non-ASCII skill
    directory would go unreported. Same choices, same rationale as the two
    sibling fixes named above."""
    root = Path(root)
    unverifiable = "skills casing not verifiable"

    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "--", ".claude/skills/"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except Exception as e:
        detail = session_context._ascii_sanitize(
            f"git ls-files failed ({type(e).__name__})", 120
        )
        return [f"{detail} -- {unverifiable}"], 0

    if result.returncode != 0:
        detail = session_context._ascii_sanitize(
            f"git ls-files exited {result.returncode}", 120
        )
        return [f"{detail} -- {unverifiable}"], 0

    warnings = []
    ok_count = 0
    for line in (result.stdout or "").splitlines():
        path_str = line.strip()
        if not path_str:
            continue
        basename = Path(path_str).name
        if basename.lower() != "skill.md":
            continue
        if basename == "SKILL.md":
            ok_count += 1
            continue
        path_safe = session_context._ascii_sanitize(path_str, 150)
        warnings.append(
            f"skill file wrong case: {path_safe} -- on a case-insensitive"
            " filesystem `git add .../SKILL.md` silently no-ops against an"
            " already-tracked differently-cased skill.md (Dog 2026-07-25"
            " incident, synk 2026-07-29)"
        )

    return warnings, ok_count


def _run_channels(root):
    """Calls all four channels once; any exception escaping THIS call
    (as opposed to a warning each channel already folds internally) is
    left to propagate to main()'s own try/except -- see module
    docstring "CLI CONTRACT" for why that path is fail-CLOSED here,
    unlike session_context.wiring_lines()'s fail-open wrapper."""
    git_warnings = session_context.git_hooks_channel(root)
    harness_warnings, importable_count = session_context.harness_channel(root)
    skills_warnings, skills_ok_count = skills_casing_channel(root)
    python_path = session_context.python_channel()
    return git_warnings, harness_warnings, importable_count, skills_warnings, skills_ok_count, python_path


def main():
    """See module docstring "CLI CONTRACT" and "F3 -- AUTOFIX FACTS ARE
    NOT WARNINGS". Never raises out of __main__: an internal failure is
    caught here and reported as ONE warning line, with exit 1
    (fail-closed, this file's checker-vs-hook divergence from
    session_context.wiring_lines())."""
    try:
        root = session_context.repo_root()
        (
            git_warnings,
            harness_warnings,
            importable_count,
            skills_warnings,
            skills_ok_count,
            python_path,
        ) = _run_channels(root)
    except Exception as e:
        line = session_context._ascii_sanitize(
            f"WIRING WARNING: check failed internally ({type(e).__name__})",
            session_context._WIRING_LINE_MAX_LEN,
        )
        print(line)
        return 1

    # F3: AUTOFIX-prefixed facts (git_hooks_channel's VG-1 self-heal,
    # a RESOLVED discrepancy) are pulled out of git_warnings BEFORE the
    # warning list / exit-code decision below -- they never count as a
    # reason to exit 1, and are rendered via the SAME
    # session_context._wiring_line_for() helper session_context.py's
    # own wiring_lines() uses for this exact distinction.
    autofix_facts = [
        f for f in git_warnings if f.startswith(session_context._AUTOFIX_FACT_PREFIX)
    ]
    real_warnings = [
        f for f in git_warnings if not f.startswith(session_context._AUTOFIX_FACT_PREFIX)
    ]
    real_warnings += list(harness_warnings) + list(skills_warnings)
    if not python_path:
        real_warnings.append("python not found on PATH")

    for fact in autofix_facts:
        print(
            session_context._ascii_sanitize(
                session_context._wiring_line_for(fact), session_context._WIRING_LINE_MAX_LEN
            )
        )

    if not real_warnings:
        python_safe = session_context._ascii_sanitize(python_path, 150)
        line = (
            "WIRING: OK (git hooks: pre-commit, commit-msg;"
            f" harness hooks: {importable_count} files importable;"
            f" skills casing: {skills_ok_count} ok; python: {python_safe})"
        )
        print(session_context._ascii_sanitize(line, session_context._WIRING_LINE_MAX_LEN))
        return 0

    for w in real_warnings:
        line = session_context._ascii_sanitize(
            session_context._wiring_line_for(w), session_context._WIRING_LINE_MAX_LEN
        )
        print(line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
