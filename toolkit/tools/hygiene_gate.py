"""hygiene_gate.py -- PreToolUse hook for command hygiene, for the
Bash|PowerShell tools. Mechanizes CLAUDE.md's "Command hygiene" points
3-5: a `cd`/`Set-Location` prefix into this repo's own root, a
` 2>&1` redirect, a `python -c`/`python - <<` edit bypassing
Edit/Write, and a journal write bypassing Edit/Write -- catches them
BEFORE the command runs.

DELIVERY CHANNEL (verified empirically against the installed harness
binary, not assumed from memory): the hook's response is delivered via
`hookSpecificOutput` on stdout, exit 0:

  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                           "additionalContext": "<list of matched classes>",
                           "permissionDecision": "deny",       # only on a BLOCK
                           "permissionDecisionReason": "..."}}  # only on a BLOCK

`permissionDecision` is OMITTED on WARN-only results: setting it to
"allow" would auto-approve the very command being flagged, silencing
the operator's own permission prompt. `additionalContext` ALWAYS
duplicates the first BLOCK reason too (belt-and-suspenders): if
`permissionDecision: "deny"` turns out to be inert on a given harness
build, a BLOCK class degrades back into a visible WARN, not silence.

DETECTION CLASSES:

 (a) cd/Set-Location prefix -- see "Determinism principle" below: BLOCK
     only when the target is unambiguously THIS repository's own root;
     any other target -- WARN (MSG_CD_NON_ROOT_WARN), never silence.
 (b) a ` 2>&1` redirect -- BLOCK only when unambiguous (no heredoc
     marker on the quote-masked text); WARN when a heredoc makes the
     body's contents unknowable; silent when the ` 2>&1` itself sits
     inside quotes (argument data, not a real redirect).
 (c) `python -c` or `python - <<` (literally "python", not "python3" --
     command hygiene names this exact form) -- \\b-bounded so
     "mypython -c" is not a substring match. WARN by default; BLOCK
     only when BOTH `PYC_DENY_ENABLED` is on (off by default -- see its
     own docstring below) AND the match is CERTAIN (unquoted, not
     inside a foreign heredoc body -- `_is_python_dash_c_certain`).
     Independently of BLOCK/WARN, the WARN TEXT is narrowed by the
     PAYLOAD'S CONTENT (`_classify_pyc_payload`, see its docstring): a
     certain payload proven to do nothing but read/compute stays
     completely silent; one that is opaque to static analysis
     (exec/eval/subprocess/dynamic dispatch/an unresolved mode) gets a
     dedicated `MSG_PYTHON_DASH_C_OPAQUE` text; a payload the gate
     cannot classify at all (quoted, embedded in a foreign heredoc/
     wrapper, or with no certain match) falls back to the OLD
     unconditional `MSG_PYTHON_DASH_C` text.
 (d) a journal write bypassing Edit/Write -- always BLOCK, unaffected
     by the determinism principle below (see "Class (d) is the
     exception" further down for why).

All classes are case-insensitive. Every check is a substring test
(`in`, O(n)) or a simple regex with no nested quantifiers -- no
`.*...*` chains that could cause catastrophic backtracking -- linear
in the length of the command.

Fail-open: a non-Bash/PowerShell tool, empty/malformed stdin, a
non-dict payload, or a missing/non-string/empty command all fall
through silently, with no stdout side effect. ANY exception raised
while classifying a real command also fails open, but VISIBLY -- see
"Fail-open with a visible marker" near decide() -- silent fail-open on
a genuine classification bug would be indistinguishable from "checked,
found nothing".

--- Determinism principle: "a BLOCK requires certainty; an ambiguous
input degrades to a WARN." -----------------------------------------
This gate does not try to tell code from data by parsing nested
command structure (an earlier design attempted exactly that --
masking nested `python -c`/heredoc payload bodies -- and was dropped:
the parsing complexity did not pay for itself against the false
positives it prevented, and introduced its own bugs). Instead, TWO
cheap, linear signals decide when a match is certain enough to BLOCK
rather than WARN:

 - QUOTES: `_mask_quoted_segments` blanks out the contents of single/
   double-quoted segments before a determinism-sensitive check runs.
   Quoted text is DATA by construction, regardless of which
   interpreter (cmd, sh, powershell, python, anything else) consumes
   it -- a hard-coded list of "risky interpreters" cannot keep up with
   every quoting form a new tool introduces, but quoting itself is a
   universal signal.
 - HEREDOC (`<<`): a heredoc's BODY can contain arbitrary text,
   including an accidental match of the pattern being searched for
   (a stray "2>&1" in prose). A `<<` marker on the quote-masked text
   downgrades a redirect match from BLOCK-certain to WARN-only
   ambiguous, rather than trying to parse where the heredoc actually
   ends.

Class (a) (cd/Set-Location) uses a THIRD kind of determinism instead of
quotes/heredoc: POSITION. `CD_PREFIX_START_RE` anchors on the absolute
start of the command (`.match()`, not `.search()`) -- a cd/Set-Location
verb that is genuinely the FIRST thing in the command is always a real
command, never data, regardless of what a payload elsewhere in the
string might contain. What determines BLOCK vs WARN for class (a) is
therefore not ambiguity at all, but WHERE the prefix targets (see
"Class (a): repo-root only" below) -- known limitation: a cd-to-root
that is NOT the first statement (e.g. `pwd; cd <root> && ...`) is not
detected at all, neither BLOCK nor WARN, since the position anchor only
looks at the absolute start of the command.

--- Class (a): repo-root only -----------------------------------------
An EARLIER, narrower design blocked `cd`/`Set-Location` whenever the
command carried a continuation (`&&`/`;`) -- ANY target. That produced
false positives on legitimate cd's into a different tree entirely (a
sibling deployment, an exam/test kit, a scratch directory, a sanctioned
subdirectory such as gateway/ for the proxy server, command hygiene
point 2) -- roughly half of all cd-class hits in a measured corpus, all
sharing the same excuse: their working directory IS the point, not a
hygiene slip. The class is narrowed to what command hygiene point 3
actually means -- "invoke from the repo root" -- by checking the
TARGET: BLOCK only when the cd/Set-Location prefix targets THIS
repository's own root (by basename, case-insensitive, computed
dynamically from this file's own location -- `Path(__file__).resolve()
.parents[1].name` -- so it survives a rename/relocation of the tree
without a constant edit); every OTHER target is a WARN
(MSG_CD_NON_ROOT_WARN), never silent.

A newline is treated as a THIRD, equal continuation separator alongside
`&&`/`;` (`cd "<root>"\ngit status` was previously invisible to either
class -- no `&&`/`;` anywhere) -- but a BARE `cd <root>` with NO
continuation at all (or with only a single trailing newline and nothing
real after it) stays completely legal: it is the only way back to the
repo root once a session's working directory has already legitimately
shifted via a WARN-class cd (e.g. `cd gateway` to run the proxy) --
forbidding the bare return would strand the session outside the root
with no way back, defeating the very point of "work from the root".

Target parsing handles an optional `-Path`/`-LiteralPath` PowerShell
flag (skipped before the target is read) and a quoted target containing
spaces (matched up to its PAIRED closing quote, not the first space
inside it) -- both via `_extract_cd_prefix_target`, the single shared
entry point for the repo-root check.

--- Class (b): ` 2>&1` --------------------------------------------------
`_collect_redirect_signal` computes `present`/`certain` against the
QUOTE-MASKED command (`_mask_quoted_segments`):
 - ` 2>&1` absent on the masked text -> the class does not fire at all
   (a quoted ` 2>&1` is argument data -- silence, not even a WARN);
 - ` 2>&1` present AND `<<` also present on the SAME masked text ->
   WARN (heredoc ambiguity -- the body could contain anything,
   including a coincidental "2>&1" as prose; note `<<` itself sits
   OUTSIDE any quotes even when its delimiter is quoted, e.g. `<<'PY'`,
   so it remains visible on the masked text);
 - ` 2>&1` present, no `<<` -> BLOCK.
This REPLACES an earlier git-commit-message-specific scrub for this
class entirely: quoting already handles a commit message's `-m` value
(always quoted by shell syntax), and a heredoc-form commit message
(`git commit -F - <<EOF ... EOF`) is now treated uniformly with any
other heredoc (ambiguous -> WARN, not silence).

--- Class (c): python -c / python - <<heredoc -------------------------
The RAW-command signal (`_is_python_dash_c`, `\\b`-bounded
`python\\s+-c` or `python\\s+-\\s*<<`) is unchanged in shape from the
original design and always fires the same as before. On top of it,
TWO independent narrowings decide BLOCK vs WARN and the WARN TEXT:

 - CERTAINTY (`_is_python_dash_c_certain`): the same determinism
   principle as classes (a)/(b) -- quotes and a FOREIGN heredoc body
   make the "python -c"/"python - <<" token ambiguous (data, not a
   real invocation: `git commit -m "run python -c to test"`, or a
   `bash <<EOF ... python -c ... EOF` wrapper whose OWN heredoc body
   is not this command's own payload). `_mask_heredoc_bodies` blanks
   every heredoc BODY in the command (any opener, not just a
   git-commit one -- a broader mask than `_strip_commit_messages`
   below), THEN `_mask_quoted_segments` blanks quoted segments; the
   token must survive BOTH masks to count as certain. `PYC_DENY_ENABLED`
   (off by default, see its own docstring) gates whether "certain"
   promotes class (c) to BLOCK at all -- with the switch off, class (c)
   never blocks, matching the original design exactly.
 - PAYLOAD CONTENT (`_classify_pyc_payload`, only evaluated when
   certain -- see its own docstring for the full "M"/"P"/"O"/"U"
   contract): a certain payload that AST-parses clean with no
   mutating or opaque call is silenced entirely (no WARN at all); one
   that is opaque to static analysis gets `MSG_PYTHON_DASH_C_OPAQUE`
   instead of the old text; a mutating or unclassifiable ("U", i.e.
   NOT certain, or certain but parsed with nothing conclusive) payload
   keeps the OLD unconditional `MSG_PYTHON_DASH_C` text -- so an
   uncertain match (a wrapper, a proze mention) is exactly as before
   this narrowing: always WARN, never silent.

A REPEATED-OPENER GUARD (`MAX_HEREDOC_OPENERS`, see its own docstring)
protects BOTH heredoc-body-masking paths in this file (this one, and
the pre-existing git-commit-message heredoc scrub below) from the same
catastrophic-backtracking shape: a command carrying more `<<` tokens
than the cap takes the cheap, CONSERVATIVE branch (certainty -> False,
journal-bypass -> False) instead of ever reaching the expensive regex.

--- Class (d) is the exception: the determinism principle does NOT
apply to it ------------------------------------------------------
The journal-bypass class stays a BLOCK unconditionally, without the
quote/heredoc downgrade classes (a)/(b) get. Concretely:
`python -c "open('logs/routing-log.jsonl','a').write(...)"` BLOCKS even
though it carries the same `-c` ambiguity signal class (c) warns on --
degrading class (d) the same way would OPEN a real bypass: that exact
command is BOTH ambiguous-by-form (like class (c)) AND a real journal
write at the same time, and if it degraded to a WARN, the write would
slip past append-only enforcement unnoticed. The asymmetry is
deliberate: classes (a)/(b) trade a false BLOCK for continued work (the
class exists to catch a hygiene slip, not to gate correctness); class
(d) trades a false WARN for a SILENT loss of the journal's append-only
guarantee -- the two classes have different error costs, and the
gate's determinism rule reflects that difference rather than applying
one recipe everywhere.

Target widened beyond the literal "routing-log": ANY `logs/*.jsonl`
path also counts (`JOURNAL_JSONL_UNDER_LOGS_RE`) -- other log/journal
files under the same directory, not just the routing journal by name.
Write forms recognized: a redirect (`>`/`>>`, on quote-masked text --
see `_mask_quoted_segments`, applied only to the redirect check, not to
the other write indicators), printf/echo, `sed -i` (in-place,
space-bounded so it doesn't match `-i` inside `--ignore-*`), `tee`
(this also matches PowerShell's `Tee-Object` for free -- `\\btee\\b`'s
word boundaries land correctly on both sides of "Tee" in
"Tee-Object"), Python `open(path, 'w'/'a'/'x')`, and the PowerShell
write cmdlets `Add-Content`/`Set-Content`/`Out-File` (PowerShell's
`>`/`>>` redirect is internally the same Out-File/-Append alias, so it
is already covered by the existing `>` check with no separate
indicator needed).

STATEMENT SCOPING: the command is split into shell statements on
`;`/`&`/`|`/newline (`_statements`, operating on the already
git-scrubbed text) -- class (d) triggers only when the SAME statement
carries both a journal target and a write form (`cat <journal>; echo
done` does not trigger: echo there does not write to the journal, it
lands in a different statement).

GIT-COMMIT-MESSAGE MASKING (`_strip_commit_messages`/
`_mask_git_statements`, class (d) only): a `-m`/`--message` argument or
a `-F - <<DELIM ... DELIM` heredoc body of `git commit`, and any
`git [-C <dir>] add/commit/push/diff/log/show/status ...` statement, is
masked before class (d) is evaluated -- prose in a commit message (a
journal path mentioned in text, an ASCII arrow containing `>`) must not
trigger the block on its own, and git itself is not a journal writer.
Known residual gap, accepted, not preemptively closed: a git
show/diff statement is masked WHOLLY, including a REAL `>` inside it --
an actual bypass via git plumbing (`git show HEAD:<path> > <path>`)
would also go undetected by this same masking.

Fail-open with a visible marker: any exception raised while
classifying a real (non-empty, correctly-typed) command is caught at
the decide() boundary and turned into exit 0 + an additionalContext
carrying `MSG_FAIL_OPEN_TEMPLATE` -- never a silent pass and never
`permissionDecision`. Fail-CLOSED here would mean rejecting every
Bash/PowerShell call of every session, including the ones fixing the
gate itself -- a stuck deployment with no way out; a silent fail-open
was rejected too, since a broken classifier would then be
indistinguishable from a genuinely clean command.

--- Reading stdin on a deadline ------------------------------------------
main() reads its harness-supplied JSON payload through a bounded
background-thread read (see the stdin-deadline helper near the bottom
of this file, the same shape as tools/session_context.py's own
stdin-deadline helper -- a LOCAL copy per hook, not a shared import, by
design). A harness that opens the pipe but never writes/closes it would
otherwise hang the PreToolUse check, and by extension the tool call
itself, forever; past the deadline the read degrades to "no payload"
(silent pass, exit 0) instead of blocking. `OSLLM_STDIN_TIMEOUT`
overrides the default; a background reader thread left blocked deep in
a platform read syscall can crash normal interpreter shutdown, so the
`if __name__ == "__main__"` guard escalates to `os._exit()` on a
timeout instead of falling through to the ordinary shutdown path.
"""

import ast
import json
import os
import re
import sys
import threading
from pathlib import Path

CD_PREFIX_START_RE = re.compile(r"^\s*(?:cd|Set-Location)\s+\S", re.IGNORECASE)
PY_DASH_C_RE = re.compile(r"\bpython\s+-c\b", re.IGNORECASE)
PY_HEREDOC_RE = re.compile(r"\bpython\s+-\s*<<", re.IGNORECASE)
PRINTF_ECHO_RE = re.compile(r"\b(printf|echo)\b", re.IGNORECASE)

# Additional shell-WRITE indicators for class (d): sed -i (in-place),
# tee (duplicates stdout into a file argument -- also matches
# PowerShell's Tee-Object, see the module docstring), python
# open(path,'a'/'w'/'x') -- all linear (simple \b-regexes / one
# negative char class with no nested quantifiers).
SED_INPLACE_RE = re.compile(r"\bsed\b[^\n]*\s-i(?:\s|$)", re.IGNORECASE)
TEE_RE = re.compile(r"\btee\b", re.IGNORECASE)
OPEN_WRITE_MODE_RE = re.compile(r"open\s*\([^)]*,\s*[\"'][wax]", re.IGNORECASE)

# PowerShell write cmdlets for class (d) -- see the module docstring,
# "Class (d)": Tee-Object is already covered by TEE_RE above (not
# duplicated here); PowerShell's `>`/`>>` redirect is already covered
# by the existing `>` check in _has_write_form (internally the same
# Out-File/-Append alias as bash's redirect, verified against
# about_Redirection).
_PS_WRITE_CMDLET_RE = re.compile(r"\b(?:Add-Content|Set-Content|Out-File)\b", re.IGNORECASE)

# Single/double quotes -- their contents are masked before the `>`
# redirect check (class (d)) and before the ` 2>&1` check (class (b)) --
# see _mask_quoted_segments. The double-quote branch is the same
# escape-aware char class COMMIT_MESSAGE_ARG_RE below uses for the -m
# value (linear, no nested quantifiers); the single-quote branch is a
# plain `[^']*` (bash has no escaping inside '...').
QUOTED_SEGMENT_RE = re.compile(
    r"'[^']*'" r'|"(?:[^"\\]|\\.)*"',
    re.DOTALL,
)

# Class (d)'s target: the literal substring "routing-log" OR any
# `logs/*.jsonl` path -- covers sibling log/journal files under the
# same directory, not just routing-log.jsonl by name. Linear (negative
# char class, no nested quantifiers).
JOURNAL_JSONL_UNDER_LOGS_RE = re.compile(r"logs/[\w./-]*\.jsonl", re.IGNORECASE)

# --- strip -m/--message of git commit -----------------------------------
# All supported forms of the -m/--message value; DOTALL is needed only
# by the branches with `.` (the here-string forms) -- the plain-quote
# branches already match newlines via their negated char class. 0+
# repetitions of a `-C <dir>` global option are allowed between "git"
# and "commit" -- a `git -C <dir> commit ...` compound would otherwise
# break the match and produce a false class-(d) result on an innocent
# git compound.
GIT_COMMIT_RE = re.compile(r"\bgit\b(?:\s+-C\s+\S+)*\s+commit\b", re.IGNORECASE)

COMMIT_MESSAGE_ARG_RE = re.compile(
    r"-m\s+\"(?:[^\"\\]|\\.)*\""
    r"|-m\s+'[^']*'"
    r"|--message=\"(?:[^\"\\]|\\.)*\""
    r"|--message='[^']*'"
    r"|-m\s+@'.*?'@"
    r"|-m\s+@\".*?\"@",
    re.DOTALL,
)

# --- heredoc-body scrub for `git commit -F - <<DELIM ... DELIM` ---------
# Group 1 is the opener up through `<<DELIM` (kept verbatim in the
# replacement); group 2/3 are the optional quote char and the
# delimiter name; group 4 is anything AFTER `<<DELIM` on the SAME line
# (also kept verbatim -- a chained `&& echo ... >> journal` on that
# line stays visible); group 5 is the body plus the closing delimiter
# line (this is what gets cut, for class (d) only -- see
# _strip_commit_messages).
COMMIT_HEREDOC_RE = re.compile(
    r"(<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2)([^\n]*)(\n.*?^\3\s*$)",
    re.DOTALL | re.MULTILINE,
)

# A heredoc opener belonging to class (c) (`python - <<...`) is
# excluded from the commit scrub entirely -- such a heredoc is not a
# commit message; scrubbing it would hide a real journal write inside a
# `python - <<PY` body from the statement-scoped machinery below.
# Checked by a POST-MATCH scan (the text immediately before this
# heredoc match's own "<<"), not a lookbehind -- Python's `re` has no
# variable-length lookbehind for `\s+`.
_PY_HEREDOC_PREFIX_RE = re.compile(r"python\s+-\s*$", re.IGNORECASE)


def _is_python_heredoc_opener(text: str, match) -> bool:
    """True when the literal "<<" of this heredoc match is immediately
    preceded by "python -" (the same form PY_HEREDOC_RE matches as a
    whole) -- such a heredoc is not a commit message; the commit scrub
    must not touch it."""
    pos = match.start(1)  # the position of "<<" itself (group 1 starts there)
    return bool(_PY_HEREDOC_PREFIX_RE.search(text[:pos]))


def _heredoc_belongs_to_git_commit(text: str, match) -> bool:
    """True when this heredoc genuinely belongs to a STATEMENT
    containing `git commit`: finds the nearest preceding chain
    separator (`;`, `&`, `|`) before the START of the heredoc match;
    the text from there (or from the start of the command, if there is
    no separator) up to the heredoc -- "the current statement so far"
    -- must contain `git commit` (GIT_COMMIT_RE). Does not account for
    heredocs nested inside one another -- a documented residual
    limitation."""
    start = match.start()
    prefix = text[:start]
    sep_idx = max(prefix.rfind(";"), prefix.rfind("&"), prefix.rfind("|"))
    statement_prefix = prefix[sep_idx + 1:] if sep_idx != -1 else prefix
    return bool(GIT_COMMIT_RE.search(statement_prefix))


# --- mask a git statement (class (d) only) -------------------------------
# A statement starting with `git ` plus one of the listed subcommands
# (at the start of the command, or right after a chain separator
# `;`/`&`/`|`/newline). Group 1 is the separator itself (or an empty
# string at the start) -- kept UNTOUCHED in the replacement so adjacent
# statements are not glued together; group 2 (the statement body up to
# the next separator) is replaced with a single space. 0+ repetitions of
# `-C <dir>` are allowed, same as GIT_COMMIT_RE above.
GIT_STATEMENT_RE = re.compile(
    r"(^|[;&|\n])(\s*git\s+(?:-C\s+\S+\s+)*(?:add|commit|push|diff|log|show|status)\b[^;&|\n]*)",
    re.IGNORECASE,
)

# Rule-of-three shape (what's wrong / what breaks / what to do instead)
# for every WARN/BLOCK text below, kept consistent across all classes.
MSG_CD_PREFIX = (
    "a cd/Set-Location prefix ahead of a compound command does not match "
    "the allowlist -- an extra permission prompt, or the command gets "
    "refused outright; invoke from the root directly, with no cd "
    "(command hygiene point 3)"
)
MSG_REDIRECT_STDERR = (
    "a trailing \" 2>&1\" does not match the allowlist -- an extra "
    "permission prompt, or the command gets refused outright; drop "
    "\" 2>&1\" from the command (command hygiene point 3)"
)
MSG_PYTHON_DASH_C = (
    "the command edits a file inline via python -c/heredoc, bypassing "
    "Edit/Write -- such an edit skips ordinary diff review and risks "
    "silently corrupting the file; use the Edit/Write tool or a named "
    "script instead (command hygiene point 4)"
)
MSG_JOURNAL_BLOCK = (
    "the journal is written only via Edit/Write (command hygiene point 5); "
    "shell write to the journal blocked"
)
# Rule of three -- a short action clause with an imperative verb
# ("invoke") appended, KEPT SHORT to stay inside the WARN_TEXT_BUDGET_
# CHARS=550 ratchet once wrapped by "Command hygiene (WARN, does not
# block): " (see tools/test_warn_messages.py); the existing text is
# otherwise unchanged.
MSG_CD_NON_ROOT_WARN = (
    "cd/Set-Location -- a warning, not a block: the target does not look like "
    "this repository's own root (the working directory is load-bearing there -- "
    "e.g. a different tree/an exam kit/a nested kit install/scratchpad, or an "
    "authorized subdirectory such as gateway, command hygiene point 2 -- there "
    "is no 'invoke from the root' alternative for those); only an explicit cd "
    "INTO THIS repository's own root is blocked (command hygiene point 3). "
    "Not justified by the working tree? Invoke from the root, no cd."
)


def _strip_commit_messages(command: str) -> str:
    """Strips -m/--message arguments of a `git commit` invocation, AND a
    commit-message HEREDOC body (`git commit -F - <<EOF ... EOF`, any
    delimiter quoting), before class (d) is evaluated: commit-message
    TEXT (a journal path/substring in prose, `>` inside an ASCII arrow)
    must not trigger detection on its own. Only applied when the
    command contains `git commit`; the git add/commit paths themselves
    are untouched -- only the message argument/heredoc body is
    stripped. An unclosed quote does not match and is left as-is
    (fail-safe toward detection).

    The heredoc scrub cuts ONLY the body + closing delimiter line
    (group 5) -- the remainder of the opener line AFTER `<<DELIM` is
    preserved verbatim (`_heredoc_sub` keeps groups 1+4), so a chained
    `&& echo ... >> journal` on the SAME line stays visible; a heredoc
    opened by `python -...<<...` (class (c)) is excluded entirely
    (`_is_python_heredoc_opener`); the scrub is scoped to a heredoc
    that genuinely belongs to a STATEMENT containing `git commit`
    (`_heredoc_belongs_to_git_commit`) -- a heredoc of some other
    statement (e.g. `python - <<'PY'` after `&&`) is left untouched,
    its real write staying visible to the statement-scoped machinery
    below."""
    if not GIT_COMMIT_RE.search(command):
        return command
    stripped = COMMIT_MESSAGE_ARG_RE.sub(" ", command)

    def _heredoc_sub(m):
        if _is_python_heredoc_opener(stripped, m):
            return m.group(0)
        if not _heredoc_belongs_to_git_commit(stripped, m):
            return m.group(0)
        return m.group(1) + m.group(4) + " "

    return COMMIT_HEREDOC_RE.sub(_heredoc_sub, stripped)


def _mask_git_statements(command: str) -> str:
    """Masks `git [-C <dir>] add/commit/push/diff/log/show/status ...`
    statements (git is not a journal writer) before class (d) is
    evaluated -- see the module docstring's known residual gap
    (show/diff with a redirect that REALLY overwrites the journal via
    git plumbing -- accepted, not preemptively closed)."""
    return GIT_STATEMENT_RE.sub(lambda m: m.group(1) + " ", command)


_STATEMENT_SPLIT_RE = re.compile(r"[;&|\n]")


def _statements(scrubbed: str) -> list[str]:
    """Splits the already-scrubbed (git-masked) command into shell
    statements on the same separators GIT_STATEMENT_RE uses
    (`;`/`&`/`|`/newline) -- see the module docstring's "STATEMENT
    SCOPING". `&&`/`||` produce an empty element between the two
    separators -- harmless (matches none of the checks below)."""
    return _STATEMENT_SPLIT_RE.split(scrubbed)


def _has_journal_target(text: str) -> bool:
    """Class (d)'s target: the literal substring "routing-log"
    (case-insensitive) OR any `logs/*.jsonl` path (case-insensitive)."""
    return "routing-log" in text.lower() or bool(JOURNAL_JSONL_UNDER_LOGS_RE.search(text))


def _mask_quoted_segments(text: str) -> str:
    """A quoted `>` (e.g. the argument string of `grep -c ">" <journal>`,
    read-only) is not a shell redirect and must not count as a write
    form; a quoted ` 2>&1` is likewise argument data, not a real
    redirect. Blanks out single/double-quoted segments (the
    double-quote branch mirrors COMMIT_MESSAGE_ARG_RE's already-proven
    char class). An unclosed quote does not match and is left unmasked
    (fail-safe toward detection, same principle as the rest of this
    file)."""
    return QUOTED_SEGMENT_RE.sub(lambda m: " " * len(m.group(0)), text)


def _has_write_form(text: str) -> bool:
    """Shell WRITE forms for class (d): redirect `>`/`>>`, printf/echo,
    sed -i (in-place), tee, python open(...,'w'/'a'/'x'), and the
    PowerShell write cmdlets (Add-Content/Set-Content/Out-File). The
    redirect `>` check runs on text with quotes masked
    (_mask_quoted_segments) -- a quoted `>` no longer counts; the other
    indicators run on the UNMASKED text."""
    redirect_check_text = _mask_quoted_segments(text)
    return bool(
        ">" in redirect_check_text
        or PRINTF_ECHO_RE.search(text)
        or SED_INPLACE_RE.search(text)
        or TEE_RE.search(text)
        or OPEN_WRITE_MODE_RE.search(text)
        or _PS_WRITE_CMDLET_RE.search(text)
    )


def _is_journal_bypass(command: str) -> bool:
    """STATEMENT-SCOPED: triggers only when ONE AND THE SAME statement
    carries both the target (_has_journal_target) and a write form
    (_has_write_form) -- see the module docstring's "STATEMENT
    SCOPING" (e.g. `cat logs/routing-log.jsonl; echo done` does NOT
    trigger -- echo there writes nothing to the journal).

    Guarded by `MAX_HEREDOC_OPENERS` (see its own docstring, defined
    further down this file with the class (c) narrowing -- the SAME
    constant, not a second copy, D-0043-style): `_strip_commit_messages`
    below uses the SAME COMMIT_HEREDOC_RE.sub pattern that backtracks
    quadratically on a command carrying many unclosed heredoc openers
    together with `git commit`. Past the cap, this returns False
    directly, without ever reaching the scrub -- the CONSERVATIVE
    direction (journal BLOCK never widens from a pathological input
    the un-narrowed gate would have paid an expensive, but not
    necessarily bypass-detecting, price to evaluate)."""
    if command.count("<<") > MAX_HEREDOC_OPENERS:
        return False
    scrubbed = _mask_git_statements(_strip_commit_messages(command))
    return any(
        _has_journal_target(stmt) and _has_write_form(stmt)
        for stmt in _statements(scrubbed)
    )


# --- class (b): ` 2>&1` via quote-masking, no interpreter list ----------
# See the module docstring, "Determinism principle" / "Class (b)", for
# the full design and the rationale for replacing an earlier
# interpreter-name list with quote-masking (a list cannot enumerate
# every interpreter/quoting form; quoting itself is universal).


def _collect_redirect_signal(command: str) -> dict:
    """Computes `present`/`certain` for class (b) on the QUOTE-MASKED
    (via `_mask_quoted_segments`, the same function class (d) uses --
    not a second implementation) text -- see the module docstring's
    "Class (b)" for the three branches (absent / present+heredoc-
    ambiguous / present+certain)."""
    masked = _mask_quoted_segments(command)
    present = " 2>&1" in masked
    if not present:
        return {"present": False, "certain": False}
    ambiguous_heredoc = "<<" in masked
    return {"present": True, "certain": not ambiguous_heredoc}


# --- class (a): cd/Set-Location target parsing + repo-root check --------
# See the module docstring, "Class (a): repo-root only", for the full
# design.

_CD_PREFIX_VERB_RE = re.compile(r"^\s*(?:cd|Set-Location)\b", re.IGNORECASE)
_CD_PREFIX_PATH_FLAG_RE = re.compile(r"\s*-(?:Literal)?Path\b", re.IGNORECASE)
_CD_PREFIX_QUOTED_TARGET_RE = re.compile(r"\s*(\"(?:[^\"\\]|\\.)*\"|'[^']*')")
_CD_PREFIX_BARE_TARGET_RE = re.compile(r"\s*([^\s&;|]+)")


def _extract_cd_prefix_target(command: str) -> str | None:
    """Parses the target of a cd/Set-Location prefix: skips an optional
    `-Path`/`-LiteralPath` PowerShell flag, then reads the target --
    quoted (up to the paired closing quote, including any spaces
    inside) or bare (up to a space/`&`/`;`/`|`). Returns the RAW
    substring (quotes included, if any), or None if this is not a
    cd/Set-Location prefix with a non-empty argument at all (the same
    boundary _is_cd_prefix uses -- "cd"/"Set-Location" with no
    argument, "cd&&..." with no space -- is not a target)."""
    verb_m = _CD_PREFIX_VERB_RE.match(command)
    if not verb_m:
        return None
    pos = verb_m.end()
    if pos >= len(command) or not command[pos].isspace():
        return None
    flag_m = _CD_PREFIX_PATH_FLAG_RE.match(command, pos)
    if flag_m:
        pos = flag_m.end()
    qm = _CD_PREFIX_QUOTED_TARGET_RE.match(command, pos)
    if qm:
        return qm.group(1)
    bm = _CD_PREFIX_BARE_TARGET_RE.match(command, pos)
    if bm:
        return bm.group(1)
    return None


def _cd_prefix_target_basename(command: str) -> str | None:
    """The basename of a cd/Set-Location prefix's target (separators/
    quotes/a trailing slash normalized) -- None if there is no target
    at all, or it is empty after normalization."""
    raw_target = _extract_cd_prefix_target(command)
    if raw_target is None:
        return None
    target = raw_target.strip("\"'")
    if not target:
        return None
    normalized = target.replace("\\", "/").rstrip("/")
    if not normalized:
        return None
    return normalized.split("/")[-1]


_REPO_ROOT_NAME = Path(__file__).resolve().parents[1].name


def _is_cd_to_repo_root(command: str) -> bool:
    """True when a cd/Set-Location prefix in `command` targets THIS
    repository's own root (by basename). Does not itself check for a
    continuation (`&&`/`;`/newline) -- the caller (`_is_cd_prefix`)
    already guarantees something real follows the cd before asking
    about its target."""
    basename = _cd_prefix_target_basename(command)
    return basename is not None and basename.lower() == _REPO_ROOT_NAME.lower()


# A newline is a THIRD, equal continuation separator alongside `&&`/`;`
# (a command of the form `cd "<root>"\ngit status` -- a newline with NO
# `&&`/`;` anywhere -- would otherwise evade detection entirely). A
# BARE `cd <root>` with no continuation at all -- OR with only a single
# trailing newline and nothing real after it -- must stay legal: it is
# the only way back to the root once a session's working directory has
# already legitimately shifted (see the module docstring's "Class (a)"
# for why forbidding the bare return would be self-defeating). Known
# limitation, NOT addressed here: cd-to-root that is NOT the first
# statement of the command (e.g. `pwd; cd <root> && ...`) is not
# detected at all -- the position anchor (CD_PREFIX_START_RE.match)
# only looks at the absolute start of the command.
_CD_PREFIX_CONTINUATION_RE = re.compile(r"(?:&&|;|\n)(.*)$", re.DOTALL)


def _is_cd_prefix(command: str) -> bool:
    if not CD_PREFIX_START_RE.match(command):
        return False
    m = _CD_PREFIX_CONTINUATION_RE.search(command)
    if not m:
        return False
    return bool(m.group(1).strip())


def _is_python_dash_c(command: str) -> bool:
    return bool(PY_DASH_C_RE.search(command) or PY_HEREDOC_RE.search(command))


# =========================================================================
# Class (c) narrowing: certainty (BLOCK gate) + payload classification
# (WARN-text gate). See the module docstring's "Class (c)" section for
# the full design; the pieces below implement it.
# =========================================================================

# Off by default: with the switch off, class (c) NEVER promotes to
# BLOCK, regardless of `_is_python_dash_c_certain` -- byte-identical to
# the pre-narrowing behavior (always WARN, never BLOCK) on every
# existing command. Flipping it on is a deliberate, separate decision
# (owned by whoever operates this gate, not by this port) -- it is
# wired through so the machinery exists and is tested, without being
# live.
PYC_DENY_ENABLED = False

MSG_PYTHON_DASH_C_BLOCK = (
    "python -c/heredoc is blocked (command hygiene point 4) -- such an "
    "edit bypasses the normal diff-review path entirely; use the "
    "Edit/Write tool for file edits, or a named script for a one-off "
    "calculation/diagnostic (python <path>, including under scratchpad)"
)

# Every heredoc BODY in the command is blanked (any opener, not just a
# git-commit one -- broader than `_strip_commit_messages` above, which
# is git-commit-guarded). The opener line itself (groups 1+4 of
# COMMIT_HEREDOC_RE) is kept verbatim -- a real `python - <<DELIM`
# opener stays visible to PY_HEREDOC_RE even after this mask; only the
# BODY (group 5) is replaced with same-length whitespace, so a
# same-line chained command after the opener (`<<EOF && rm -rf x`)
# also stays visible.
def _mask_heredoc_bodies(text: str) -> str:
    """Masks the body of every heredoc in `text` (not git-commit
    specific): a `python -c`/`python - <<` token INSIDE a foreign
    heredoc's body (e.g. `bash <<EOF\\npython -c "print(1)"\\nEOF`) is
    prose to THIS command, not this command's own invocation -- the
    outer wrapper is what actually runs, the inner text merely rides
    along as its stdin. Masking it before the certainty check keeps
    such wrapper forms from being treated as a certain match, the same
    way a quoted mention already is."""
    return COMMIT_HEREDOC_RE.sub(
        lambda m: m.group(1) + m.group(4) + " " * len(m.group(5)), text
    )


# A cap on repeated, UNCLOSED heredoc openers in one command: without
# it, `_mask_heredoc_bodies`'s regex (COMMIT_HEREDOC_RE.sub, the same
# pattern `_strip_commit_messages` above uses) backtracks to the end of
# the text on EVERY opener that never finds its closing delimiter --
# quadratic in the number of such openers. The cheap prefilter below
# (`command.count("<<")`, a plain substring count, no backtracking) is
# checked FIRST; past the cap, the expensive regex path is skipped
# entirely and the caller takes its CONSERVATIVE branch (certainty ->
# False for class (c); not-a-bypass -> False for the journal-bypass
# scrub above) -- deny/block never WIDENS from this cap, it can only
# lose a possible (not guaranteed) block on a pathological input,
# degrading to the same WARN/silent outcome the un-narrowed gate always
# gave such a command. 64 is comfortably above any normal command's
# heredoc count (0-2 is typical); a false hit on an unrelated `<<`
# (e.g. a bit-shift literal inside a string) only makes the prefilter
# MORE conservative, never less.
MAX_HEREDOC_OPENERS = 64


def _is_python_dash_c_certain(command: str) -> bool:
    """A NARROWER signal than `_is_python_dash_c` above (which keeps its
    existing meaning unchanged -- `permission_audit.classify_hygiene`
    reads that key by name and must not see it redefined): True only
    when the "python -c"/"python - <<" token survives BOTH
    `_mask_heredoc_bodies` (a foreign heredoc's body is prose, not this
    command's own invocation) AND `_mask_quoted_segments` (the token is
    not sitting inside quotes as a data string, e.g. a git commit
    message). An ordinary `python -c "code"` call stays certain: the
    quotes there wrap the -c ARGUMENT, not the "python -c" token itself,
    which sits before the quote and is untouched by masking it. A real
    `python - <<DELIM` heredoc opener stays certain the same way -- the
    mask keeps the opener line, only the body is blanked.

    Guarded by `MAX_HEREDOC_OPENERS` (see its own docstring): past the
    cap, this returns False without ever calling the expensive mask."""
    if command.count("<<") > MAX_HEREDOC_OPENERS:
        return False
    masked = _mask_quoted_segments(_mask_heredoc_bodies(command))
    return bool(PY_DASH_C_RE.search(masked) or PY_HEREDOC_RE.search(masked))


# --- payload content classification: "M" (mutates) / "P" (proven pure) /
# "O" (opaque to static analysis) / "U" (not classified at all) --------
#
# Extraction (from the RAW command, before any masking -- the argument
# text itself is what gets parsed, quoting is just how the shell
# delimited it): the -c argument (quoted literal or a bare token up to
# whitespace) and/or a `python -...<<DELIM ... DELIM` heredoc body.
# Several matches in one command are each classified separately; the
# STRICTEST class wins (M > O > P) -- one mutating payload among several
# is enough to keep the old WARN text, one opaque payload among
# otherwise-pure ones is enough to switch to the opaque text.
_PY_DASH_C_ARG_RE = re.compile(
    r"\bpython\s+-c\s+"
    r"(?:"
    r'"(?P<dq>(?:[^"\\]|\\.)*)"'
    r"|'(?P<sq>[^']*)'"
    r"|(?P<bare>\S+)"
    r")",
    re.IGNORECASE | re.DOTALL,
)

_PY_HEREDOC_EXTRACT_RE = re.compile(
    r"\bpython\s+-\s*<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*"
    r"\n(?P<body>.*?)^\2\s*$",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)

# A single extracted payload over this many characters is classified
# "O" directly, with no attempt to `ast.parse` it at all -- a size cap
# independent of, and much smaller than, the whole-command length this
# file otherwise stays linear against; keeps a single classification
# call bounded regardless of how large one -c argument or heredoc body
# gets. Measured separately from whether decide() is gated by it (it
# is not -- see the perf test in the test suite for the actual numbers
# on 100KB/1MB commands).
PYC_PAYLOAD_LIMIT = 20_000

MSG_PYTHON_DASH_C_OPAQUE = (
    "the python -c/heredoc payload is opaque to static analysis "
    "(exec/eval/subprocess/dynamic dispatch, command hygiene point 4) "
    "-- the gate cannot prove it writes nothing; move the code into a "
    "named script instead (python <path>, including under scratchpad)"
)

# --- closed M/O lists ----------------------------------------------------
_PATH_MUTATING_METHOD_NAMES = {
    "write_text", "write_bytes", "unlink", "rename", "replace",
    "mkdir", "touch", "rmdir",
}
_OS_MUTATING_QUALIFIED = {
    "os.remove", "os.unlink", "os.rename", "os.replace", "os.rmdir",
    "os.mkdir", "os.makedirs", "os.truncate", "os.chmod",
}
_DUMP_QUALIFIED = {"json.dump", "pickle.dump", "csv.writer"}
_PANDAS_LIKE_METHOD_NAMES = {"to_csv", "to_excel"}
_WRITE_METHOD_NAMES = {"write", "writelines"}
_STDIO_DOTTED = {"sys.stdout", "sys.stderr"}

_OPAQUE_BARE_NAMES = {
    "exec", "eval", "compile", "__import__",
    "getattr", "setattr", "globals", "locals", "vars",
}
_OPAQUE_ROOT_MODULES = {
    "importlib", "subprocess", "ctypes", "marshal", "socket",
    "urllib", "requests", "multiprocessing", "pty", "builtins",
}


def _dotted_call_name(node):
    """Rebuilds a dotted name from an ast.Attribute/ast.Name chain
    (e.g. `os.path.remove` -> "os.path.remove"). None when the base is
    NOT a plain Name/Attribute chain (e.g. `__import__('os').remove`:
    the base of `.remove` is the CALL `__import__('os')`, not a Name --
    no dotted name is built, `.remove` is not credited as `os.remove`;
    only `__import__` itself contributes to the opaque class there)."""
    parts = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


# The free function `open(path, mode)`/`io.open(path, mode)` carries
# its mode as the 2nd positional argument (index 1, path is index 0);
# the METHOD form `X.open(mode)` (`Path(...).open('w')`,
# `pathlib.Path.open`, any file-like object) carries mode as the 1ST
# argument (index 0) -- self is implicit, there is no separate "path"
# argument at all. Distinguished ONLY by the RESOLVED dotted name
# (after the alias map): "open"/"io.open" is the free function; ANYTHING
# else (including None -- an unresolvable base, the common case for
# `Path(...).open(...)` where the base is itself a call) is the method
# form.
_FREE_OPEN_DOTTED_NAMES = {"open", "io.open"}


def _classify_open_call(node, dotted):
    """Classifies ONE `open(...)`/`X.open(...)` call: mode comes from
    the positional index above, OR the `mode` keyword (shared by both
    forms). A `**kwargs` spread hides the mode -> "O"; a literal mode
    string containing w/a/x/+ -> "M"; a literal mode string without
    those characters (e.g. "r", "rb") -> None (neutral, contributes to
    "P"); a non-literal mode (a variable, an f-string) -> "O"; no mode
    argument at all -> None (P)."""
    if any(kw.arg is None for kw in node.keywords):
        return "O"
    mode_index = 1 if dotted in _FREE_OPEN_DOTTED_NAMES else 0
    mode_node = node.args[mode_index] if len(node.args) > mode_index else next(
        (kw.value for kw in node.keywords if kw.arg == "mode"), None
    )
    if mode_node is None:
        return None
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return "M" if any(ch in mode_node.value for ch in "wax+") else None
    return "O"


def _build_import_alias_map(tree) -> dict:
    """Walks top-level `ast.Import`/`ast.ImportFrom` nodes (a full
    `ast.walk`, so it also catches imports nested inside `if`/`try`/a
    function body) and builds a flat "local name -> canonical path"
    map. `import os as o` -> {"o": "os"}; `import os` (no asname) ->
    {"os": "os"} (identity, harmless); `from os import remove` ->
    {"remove": "os.remove"}; `from os import remove as rm` ->
    {"rm": "os.remove"}. A relative `from . import x` (module is None)
    is skipped -- there is no canonical path to resolve it to (an
    honest boundary, not a crash)."""
    alias_map = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    alias_map[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    alias_map[top] = top
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                alias_map[local] = f"{node.module}.{alias.name}"
    return alias_map


def _resolve_dotted(raw_dotted, alias_map):
    """Substitutes the ROOT of a dotted chain through the alias map
    before matching against the M/O lists -- `o.remove` (map
    {"o":"os"}) -> "os.remove"; a bare `remove` (map
    {"remove":"os.remove"}) -> "os.remove" whole (ImportFrom maps the
    NAME to the FULL path, not just the root). No entry in the map ->
    the string is unchanged (ordinary names/builtin types)."""
    if raw_dotted is None:
        return None
    parts = raw_dotted.split(".")
    root = parts[0]
    if root in alias_map:
        parts[0] = alias_map[root]
        return ".".join(parts)
    return raw_dotted


def _is_known_mutating_or_opaque_name(dotted) -> bool:
    """True when the RESOLVED (post-alias-map) dotted name `dotted`
    itself refers to `open`, OR to any M/O name in the closed lists --
    used ONLY to detect a reassigned callable (`w = open`, `r =
    os.remove`) -- the assignment itself is not a call, but it makes a
    LATER call through `w`/`r` UNTRACKABLE by this classifier ->
    opaque, REGARDLESS of whether the original target class was M or O
    (a reassigned callable is opaque by definition here)."""
    if dotted is None:
        return False
    if dotted == "open":
        return True
    if dotted in _OPAQUE_BARE_NAMES or dotted in _OS_MUTATING_QUALIFIED or dotted in _DUMP_QUALIFIED:
        return True
    root = dotted.split(".", 1)[0]
    attr_last = dotted.rsplit(".", 1)[-1]
    if root in _OPAQUE_ROOT_MODULES or root == "shutil":
        return True
    if root == "os" and (attr_last in ("system", "popen") or attr_last.startswith("exec") or attr_last.startswith("spawn")):
        return True
    if attr_last in _PATH_MUTATING_METHOD_NAMES or attr_last in _PANDAS_LIKE_METHOD_NAMES or attr_last in _WRITE_METHOD_NAMES:
        return True
    return False


def _classify_single_payload(text: str) -> str:
    """Classifies ONE extracted payload -> "M"/"P"/"O": `ast.parse` +
    a tree walk; any parse failure -> "O"; over `PYC_PAYLOAD_LIMIT` or
    empty/whitespace-only -> "O" without attempting to parse at all.
    Both M and O can fire inside the SAME payload -- M wins (M > O > P).

    `attr` is read from `node.func.attr`/`node.func.id` INDEPENDENTLY
    of whether `dotted` resolves -- this is what lets a CHAINED
    receiver (`Path('x').write_text(...)` -- the base of `.write_text`
    is the CALL `Path('x')`, not a Name/Attribute chain, so
    `_dotted_call_name` returns None for it) still get caught by the
    attribute-based M checks (Path methods/`.to_csv`/`.to_excel`/
    `.write`/`.writelines`/`open`-as-an-attribute). The
    `sys.stdout`/`sys.stderr` exclusion for `.write`/`.writelines`
    applies ONLY when the base resolves; an unresolvable base (e.g.
    `io.open().write(...)` -- the base of `.write` is itself the CALL
    `io.open()`) is NOT excluded -> "M" (the conservative default). The
    import alias map (`_build_import_alias_map`) resolves `import os as
    o`/`from os import remove` before matching the qualified (non-
    attribute) M/O lists; a separate pass over `ast.Assign`/
    `ast.AnnAssign`/`ast.NamedExpr` catches a reassigned callable
    (`w = open`) -> "O"."""
    if len(text) > PYC_PAYLOAD_LIMIT:
        return "O"
    if not text.strip():
        return "O"
    try:
        tree = ast.parse(text)
        alias_map = _build_import_alias_map(tree)
        has_m = False
        has_o = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                value = node.value
                if isinstance(value, (ast.Name, ast.Attribute)):
                    resolved_value = _resolve_dotted(_dotted_call_name(value), alias_map)
                    if _is_known_mutating_or_opaque_name(resolved_value):
                        has_o = True
                continue
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Attribute):
                attr = node.func.attr
            elif isinstance(node.func, ast.Name):
                attr = node.func.id
            else:
                attr = None
            dotted = _resolve_dotted(_dotted_call_name(node.func), alias_map)
            root = dotted.split(".", 1)[0] if dotted else None

            if dotted in _OPAQUE_BARE_NAMES or root in _OPAQUE_ROOT_MODULES:
                has_o = True
                continue
            if root == "os" and attr in ("system", "popen"):
                has_o = True
                continue
            if root == "os" and attr and (attr.startswith("exec") or attr.startswith("spawn")):
                has_o = True
                continue
            if dotted == "fileinput.input" and any(kw.arg == "inplace" for kw in node.keywords):
                has_o = True
                continue

            if attr == "open":
                verdict = _classify_open_call(node, dotted)
                if verdict == "M":
                    has_m = True
                elif verdict == "O":
                    has_o = True
                continue
            if attr in _PATH_MUTATING_METHOD_NAMES:
                has_m = True
                continue
            if root == "os" and dotted in _OS_MUTATING_QUALIFIED:
                has_m = True
                continue
            if root == "shutil":
                has_m = True
                continue
            if dotted in _DUMP_QUALIFIED:
                has_m = True
                continue
            if attr in _PANDAS_LIKE_METHOD_NAMES:
                has_m = True
                continue
            if attr in _WRITE_METHOD_NAMES:
                base_dotted = (
                    _resolve_dotted(_dotted_call_name(node.func.value), alias_map)
                    if isinstance(node.func, ast.Attribute) else None
                )
                if base_dotted not in _STDIO_DOTTED:
                    has_m = True
                continue
            if dotted == "print" or attr == "print":
                file_kw = next((kw for kw in node.keywords if kw.arg == "file"), None)
                if file_kw is not None and _resolve_dotted(
                    _dotted_call_name(file_kw.value), alias_map
                ) not in _STDIO_DOTTED:
                    has_m = True
                continue
    except Exception:
        return "O"
    if has_m:
        return "M"
    if has_o:
        return "O"
    return "P"


def _classify_pyc_payload(command: str, certain: bool | None = None) -> str:
    """"M"|"P"|"O"|"U": "U" when `_is_python_dash_c_certain` is false --
    the classification is not attempted at all, and the caller stays on
    the OLD unconditional WARN text (see `_classify` below) -- an
    obfuscated/wrapped/quoted-as-data match is exactly the class this
    gate was already unable to prove anything about, so it keeps
    warning rather than going silent or picking a text implying more
    confidence than the gate actually has. Any exception inside is a
    fail-safe toward "O" (opaque), not toward crashing `_classify`
    entirely.

    `certain` is an OPTIONAL precomputed result of
    `_is_python_dash_c_certain` (`_collect_signals` below computes it
    once and passes it in, rather than computing it twice); the public
    one-argument call (`_classify_pyc_payload(command)`) still works,
    computing it itself by default."""
    if certain is None:
        certain = _is_python_dash_c_certain(command)
    if not certain:
        return "U"
    try:
        payloads = []
        for m in _PY_DASH_C_ARG_RE.finditer(command):
            if m.group("dq") is not None:
                payloads.append(m.group("dq"))
            elif m.group("sq") is not None:
                payloads.append(m.group("sq"))
            else:
                payloads.append(m.group("bare"))
        for m in _PY_HEREDOC_EXTRACT_RE.finditer(command):
            payloads.append(m.group("body"))
        if not payloads:
            return "O"
        classes = [_classify_single_payload(p) for p in payloads]
    except Exception:
        return "O"
    if "M" in classes:
        return "M"
    if "O" in classes:
        return "O"
    return "P"


def _collect_signals(command: str) -> dict:
    """The single point of computation for ALL signals -- used both by
    decide() (assembling the JSON response below) and by
    permission_audit.classify_hygiene (a measurement tool must walk the
    exact same logic the gate does) -- one computation, not two
    independently maintained copies. Returns BOOLEAN signals (not
    ready-made messages/ordering/deny-vs-warn -- that assembly stays
    with decide()).

      - `journal` -- class (d), on the RAW command (plus PS write
        forms, see _has_write_form).
      - `cd` -- ANY cd/Set-Location prefix with a real continuation
        (newline counts as a third separator, see _is_cd_prefix) -- the
        broader signal, useful to a measurement tool even when the
        target isn't the repo root.
      - `cd_to_repo_root` -- a NARROWER signal (the target IS this
        repo's own root) -- THIS ONE decides BLOCK vs WARN for class
        (a) below; unaffected by quote/heredoc ambiguity (class (a)'s
        determinism comes from position, not quoting -- see the module
        docstring).
      - `redirect` -- ` 2>&1` present on the quote-masked text -- ANY
        presence, for measurement.
      - `redirect_certain` -- `redirect` AND no `<<` on that same
        masked text -- THIS ONE decides BLOCK vs WARN for class (b).
      - `pyc` -- class (c), on the RAW command -- the BROAD signal,
        UNCHANGED (`permission_audit.classify_hygiene` reads this key
        by name; its meaning does not move).
      - `pyc_certain` -- a NARROWER signal (`_is_python_dash_c_certain`
        -- the same quote/heredoc-body masking principle as
        `redirect_certain`) -- decides BLOCK vs WARN for class (c),
        and ONLY when `PYC_DENY_ENABLED` is also on (off by default,
        see its own docstring).
      - `pyc_payload` -- "M"/"P"/"O"/"U" (`_classify_pyc_payload`, see
        its own docstring) -- decides the WARN TEXT for class (c) when
        it does not block; computed from the ALREADY-computed
        `pyc_certain` value (not recomputed a second time)."""
    cd_hit = _is_cd_prefix(command)
    redirect_signal = _collect_redirect_signal(command)
    pyc_certain_value = _is_python_dash_c_certain(command)
    return {
        "journal": _is_journal_bypass(command),
        "cd": cd_hit,
        "cd_to_repo_root": cd_hit and _is_cd_to_repo_root(command),
        "redirect": redirect_signal["present"],
        "redirect_certain": redirect_signal["certain"],
        "pyc": _is_python_dash_c(command),
        "pyc_certain": pyc_certain_value,
        "pyc_payload": _classify_pyc_payload(command, certain=pyc_certain_value),
    }


def _classify(command: str) -> tuple[int, dict | None]:
    """Assembles the JSON response from `_collect_signals` (see its
    docstring for what each signal means). See the module docstring for
    the full per-class BLOCK/WARN/silent rules.

    Fixed ORDER when several classes fire at once: journal -> cd ->
    2>&1 -> python -c/heredoc. `permissionDecisionReason` is the FIRST
    BLOCK reason in that order; `additionalContext` (belt-and-
    suspenders) lists ALL BLOCK reasons in that order, then all
    remaining WARN reasons, as one string. The python -c/heredoc BLOCK
    is placed STRICTLY LAST: for every command that already denies
    today (journal/cd/2>&1), adding this class never changes
    `permissionDecisionReason` (it always takes the FIRST element of
    `deny_reasons`)."""
    signals = _collect_signals(command)
    journal_hit = signals["journal"]
    cd_hit = signals["cd"]
    cd_to_repo_root = signals["cd_to_repo_root"]
    redirect_present = signals["redirect"]
    redirect_certain = signals["redirect_certain"]
    pyc_hit = signals["pyc"]
    pyc_certain = signals["pyc_certain"]
    payload_class = signals["pyc_payload"]
    pyc_deny = PYC_DENY_ENABLED and pyc_certain

    deny_reasons = []
    if journal_hit:
        deny_reasons.append(MSG_JOURNAL_BLOCK)
    if cd_to_repo_root:
        deny_reasons.append(MSG_CD_PREFIX)
    if redirect_certain:
        deny_reasons.append(MSG_REDIRECT_STDERR)
    if pyc_deny:
        deny_reasons.append(MSG_PYTHON_DASH_C_BLOCK)

    warn_reasons = []
    if cd_hit and not cd_to_repo_root:
        warn_reasons.append(MSG_CD_NON_ROOT_WARN)
    if redirect_present and not redirect_certain:
        warn_reasons.append(MSG_REDIRECT_STDERR)
    # payload_class == "P" (certain AND provably clean) -> silence;
    # "O" -> the dedicated opaque text; "M"/"U" -> the old unconditional
    # text, verbatim (an uncertain match warns exactly as before this
    # narrowing).
    if pyc_hit and not pyc_deny and payload_class != "P":
        warn_reasons.append(
            MSG_PYTHON_DASH_C_OPAQUE if payload_class == "O" else MSG_PYTHON_DASH_C
        )

    if deny_reasons:
        context_parts = deny_reasons + warn_reasons
        return 0, {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": deny_reasons[0],
                "additionalContext": "Command hygiene: " + "; ".join(context_parts),
            }
        }

    if warn_reasons:
        return 0, {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    "Command hygiene (WARN, does not block): " + "; ".join(warn_reasons)
                ),
            }
        }

    return 0, None


# --- fail-open marker ----------------------------------------------------
MSG_FAIL_OPEN_TEMPLATE = (
    "hygiene_gate: internal classifier error ({exc_type}), hygiene was NOT checked"
)


def decide(payload: dict) -> tuple[int, dict | None]:
    """Entry point -- validates the payload (a silent pass on empty/
    malformed input), then classifies the command via `_classify`.
    exit_code is ALWAYS 0, including on a BLOCK: the block is signalled
    entirely via hookSpecificOutput.permissionDecision="deny" in the
    JSON on stdout, never through the process return code.

    Fail-open with a visible marker: ANY exception raised while
    classifying is caught HERE (not only in main()), so a direct
    decide() call in tests -- no subprocess -- also gets fail-open if a
    monkeypatched helper raises. `permissionDecision` never appears on
    this branch. See the module docstring's "Fail-open with a visible
    marker" for why fail-closed and silent fail-open were both
    rejected."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Bash", "PowerShell"):
        return 0, None

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0, None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0, None

    try:
        return _classify(command)
    except Exception as exc:  # noqa: BLE001 -- intentionally broad: see module docstring
        return 0, {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": MSG_FAIL_OPEN_TEMPLATE.format(
                    exc_type=type(exc).__name__
                ),
            }
        }


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# stdin-deadline helper: reading stdin to EOF must never hang a PreToolUse
# check (and by extension the tool call it gates) forever on a harness that
# opens the pipe but never actually writes/closes it. A daemon thread does
# the blocking read; the main thread joins on a deadline instead of calling
# sys.stdin.read() directly. On a timeout, the payload degrades to "no
# payload" (silent pass, same as empty/malformed stdin), never a hang or a
# crash. This is a LOCAL copy of the same helper tools/session_context.py
# carries -- by design, not an oversight: each hook stays self-contained
# (module docstring's "Reading stdin on a deadline").
# ---------------------------------------------------------------------------

_STDIN_DEADLINE_DEFAULT = 10.0
_STDIN_DEADLINE_MAX = 600.0
_STDIN_DEADLINE_ENV = "OSLLM_STDIN_TIMEOUT"


def _stdin_deadline_seconds():
    """Seconds to wait for stdin: env override, else the default.
    Invalid, non-numeric, <=0, or > _STDIN_DEADLINE_MAX all fall back to
    the default -- there is deliberately NO "0 = wait forever" mode (that
    would resurrect the exact hang this helper exists to close)."""
    try:
        value = float(os.environ.get(_STDIN_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDIN_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDIN_DEADLINE_MAX):
        return _STDIN_DEADLINE_DEFAULT
    return value


def _read_stdin_bytes_deadline():
    """Returns (bytes, timed_out). Reads stdin to EOF, bounded by the
    deadline above. A background daemon thread does the actual blocking
    read; the deadline is enforced via thread.join(timeout) -- portable
    across platforms where select/poll do not work on pipes (Windows).
    A TTY returns b"" immediately, without reading anything. Any read
    error degrades to b"" -- fail-open, same discipline as the rest of
    this file."""
    stdin = getattr(sys, "stdin", None)
    if stdin is None:
        return b"", False
    try:
        if stdin.isatty():
            return b"", False
    except Exception:
        pass
    stream = getattr(stdin, "buffer", stdin)
    box = {}

    def _reader():
        try:
            box["data"] = stream.read()
        except Exception:
            box["data"] = b""

    thread = threading.Thread(target=_reader, name="stdin-deadline", daemon=True)
    thread.start()
    thread.join(_stdin_deadline_seconds())
    if thread.is_alive():
        return b"", True
    data = box.get("data") or b""
    if not isinstance(data, bytes):
        data = str(data).encode("utf-8", "replace")
    return data, False


_STDIN_DEADLINE_MSG = "stdin deadline exceeded -- fail-open, payload discarded"

# Set when a stdin read actually timed out. The reader thread above is
# left running as a daemon (it may still be blocked deep inside a
# platform read syscall) -- on normal interpreter shutdown, a background
# thread blocked on the real stdin buffered reader can crash the process
# ("Fatal Python error: _enter_buffered_busy") instead of exiting
# cleanly. main() itself is unaffected (a plain `return`, safe
# in-process); only the actual __main__ script-exit path below
# escalates to os._exit() when this flag is set.
_STDIN_DEADLINE_STATE = {"hit": False}


def main() -> int:
    _reconfigure_stdout_utf8()

    # Byte-safe, deadline-bounded stdin read: the deadline helper reads
    # raw bytes via a background thread (bypassing the platform text-mode
    # encoding of sys.stdin, same as the direct sys.stdin.buffer.read()
    # this replaces), with an explicit utf-8 decode (errors="replace")
    # that fails open on bad bytes -- now additionally bounded by
    # OSLLM_STDIN_TIMEOUT instead of blocking forever with no EOF.
    raw_bytes, timed_out = _read_stdin_bytes_deadline()
    if timed_out:
        _STDIN_DEADLINE_STATE["hit"] = True
        try:
            sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
        except Exception:
            pass
        return 0
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    exit_code, output = decide(payload)
    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return exit_code


if __name__ == "__main__":
    _rc = main()
    if _STDIN_DEADLINE_STATE["hit"]:
        # A stdin-reader thread may still be blocked deep inside a
        # platform read syscall -- normal interpreter shutdown can crash
        # on that ("Fatal Python error: _enter_buffered_busy"). Flush
        # both streams defensively, then exit immediately without
        # running the normal shutdown sequence.
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(_rc)
    sys.exit(_rc)
