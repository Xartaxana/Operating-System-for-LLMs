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
     command hygiene names this exact form) -- always WARN, never
     BLOCK; \\b-bounded so "mypython -c" is not a substring match.
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
Unchanged in shape from the original design: always WARN, `\\b`-bounded
`python\\s+-c` or `python\\s+-\\s*<<`, evaluated on the raw command.

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
"""

import json
import re
import sys
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

MSG_CD_PREFIX = "don't cd into this repo's own root, invoke from there directly (command hygiene point 3)"
MSG_REDIRECT_STDERR = "don't append 2>&1 (command hygiene point 3)"
MSG_PYTHON_DASH_C = "edits/scripts go through the Edit/Write tool or a named script (command hygiene point 4)"
MSG_JOURNAL_BLOCK = (
    "the journal is written only via Edit/Write (command hygiene point 5); "
    "shell write to the journal blocked"
)
MSG_CD_NON_ROOT_WARN = (
    "cd/Set-Location -- a warning, not a block: the target does not look like "
    "this repository's own root (the working directory is load-bearing there -- "
    "e.g. a different tree/an exam kit/a nested kit install/scratchpad, or an "
    "authorized subdirectory such as gateway, command hygiene point 2 -- there "
    "is no 'invoke from the root' alternative for those); only an explicit cd "
    "INTO THIS repository's own root is blocked (command hygiene point 3)"
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
    trigger -- echo there writes nothing to the journal)."""
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
      - `pyc` -- class (c), on the RAW command -- always WARN, never
        promoted to BLOCK."""
    cd_hit = _is_cd_prefix(command)
    redirect_signal = _collect_redirect_signal(command)
    return {
        "journal": _is_journal_bypass(command),
        "cd": cd_hit,
        "cd_to_repo_root": cd_hit and _is_cd_to_repo_root(command),
        "redirect": redirect_signal["present"],
        "redirect_certain": redirect_signal["certain"],
        "pyc": _is_python_dash_c(command),
    }


def _classify(command: str) -> tuple[int, dict | None]:
    """Assembles the JSON response from `_collect_signals` (see its
    docstring for what each signal means). See the module docstring for
    the full per-class BLOCK/WARN/silent rules.

    Fixed ORDER when several classes fire at once: journal -> cd ->
    2>&1. `permissionDecisionReason` is the FIRST BLOCK reason in that
    order; `additionalContext` (belt-and-suspenders) lists ALL BLOCK
    reasons in that order, then all remaining WARN reasons, as one
    string."""
    signals = _collect_signals(command)
    journal_hit = signals["journal"]
    cd_hit = signals["cd"]
    cd_to_repo_root = signals["cd_to_repo_root"]
    redirect_present = signals["redirect"]
    redirect_certain = signals["redirect_certain"]
    pyc_hit = signals["pyc"]

    deny_reasons = []
    if journal_hit:
        deny_reasons.append(MSG_JOURNAL_BLOCK)
    if cd_to_repo_root:
        deny_reasons.append(MSG_CD_PREFIX)
    if redirect_certain:
        deny_reasons.append(MSG_REDIRECT_STDERR)

    warn_reasons = []
    if cd_hit and not cd_to_repo_root:
        warn_reasons.append(MSG_CD_NON_ROOT_WARN)
    if redirect_present and not redirect_certain:
        warn_reasons.append(MSG_REDIRECT_STDERR)
    if pyc_hit:
        warn_reasons.append(MSG_PYTHON_DASH_C)

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


def main() -> int:
    _reconfigure_stdout_utf8()

    # Byte-safe stdin read: sys.stdin.buffer.read() bypasses the
    # platform text-mode encoding of sys.stdin, with an explicit
    # utf-8 decode (errors="replace") that fails open on bad bytes.
    raw_bytes = sys.stdin.buffer.read()
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
    sys.exit(main())
