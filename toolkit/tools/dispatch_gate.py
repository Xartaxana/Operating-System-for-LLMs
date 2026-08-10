"""dispatch_gate.py -- PreToolUse hook for the Task/Agent tool that
checks the SHAPE of a dispatch before it goes out, enforcing two
CLAUDE.md rules in code rather than relying on discipline alone:
rule 11 (DoD-in-every-dispatch / dispatch-context-manifest) and rule 7
(the dispatch label starts with the worker's tier).

Contract (PreToolUse hook stdin JSON): {"tool_name": str,
"tool_input": {"subagent_type": str, "prompt": str,
"description": str}, "cwd": str, ...}. Only tool_name in
{"Task", "Agent"} is inspected -- any other tool passes silently
(exit 0, no output). Exit 2 with a message on stderr blocks the call;
exit 0 allows it. The BLOCKING gate is stateless: it never reads or
writes any file, it only inspects the payload it was given (the
given-path WARN layer added below is the one exception -- it reads the
filesystem to check path existence, but never writes anything and
never changes the exit code).

Cross-reference (a live example of a two-condition detector, see
critic.md's scoping-of-paired-conditions review norm): check 2 below
requires BOTH a given-marker and an owns-marker present in the SAME
prompt to count as a real manifest -- verifying each half in isolation
(a given-marker anywhere, an owns-marker anywhere, even from unrelated
mentions) would be exactly the false cross-match that norm warns
against.

Checks (blocking gate):
 1. subagent_type == "builder": tool_input["prompt"] must contain a
    DoD marker (DOD_MARKERS_RE). None found -> BLOCK
    (BLOCK_MESSAGE_NO_DOD).
 2. subagent_type == "builder" AND the prompt shows a write indicator
    -- a conservative heuristic: block ONLY when a write indicator is
    present AND BOTH manifest markers (MANIFEST_GIVEN_RE and
    MANIFEST_OWNS_RE) are missing -> BLOCK (BLOCK_MESSAGE_NO_MANIFEST).
    No write indicator -> check 2 is skipped entirely (a read-only
    dispatch needs no manifest). The write indicator is EITHER a match
    of WRITE_INDICATORS_RE (four write verbs -- see "Write-indicator
    discriminator" below for why the bare word "owns" is NOT one of
    them any more) OR owns_declaration_has_path_token(prompt) -- an
    owns: declaration that actually carries a path-like token, not
    just the bare word.
 3. ANY subagent_type (including critic/scout): tool_input["description"],
    IF PRESENT, must start with a leading token followed by a
    separator ([ :-]) -- LABEL_MODEL_PREFIX_RE below. This is a FORM
    check only, on purpose: this template has no fixed list of tier/
    model names (a deployment configures its own bindings in
    delegation.config.yaml), so the hook can only verify that the
    label carries *some* leading tag-like token, not that the token
    names a real tier. description absent from the payload -> check 3
    is skipped.
 4. critic/scout (any subagent_type != "builder") -- checks 1 and 2 do
    not apply to them; their own DoD shape is different (rule 11
    describes it in prose, not as a prompt-text pattern).

Priority when several checks fail at once: 1 -> 2 -> 3, the first one
found is the single stderr message (the hook blocks with one message,
not a list).

Fail-open on a payload that isn't valid JSON -- same principle as
every other hook in this file set: a hook that can't parse its input
must not block an unrelated tool call.

Marker word-boundary hardening: DOD_MARKERS_RE's "DoD"/"witness"
alternatives, and MANIFEST_GIVEN_RE/MANIFEST_OWNS_RE, are \\b-bounded
so a marker only matches as a standalone word, not as a substring
inside an unrelated longer token -- three concrete classes this
closes: a bare filename mentioning "dod" in the given basket (e.g.
"tools/dod_gate.py") no longer counts as a DoD marker; a filename
mentioning "witness" (e.g. "test_witness_echo.py") no longer counts as
a witness marker; an ordinary longer Cyrillic word that merely
CONTAINS the short Cyrillic given-marker root as a substring no longer
counts as a given-marker (same class as the write-indicator fix
below), and a filename merely containing "owns" as a substring no
longer counts as an owns-marker. The multi-word Cyrillic/English
alternatives (an acceptance-criteria phrase, a verification-run
phrase) are not bounded the same way: they are phrases with an
internal space, and no realistic filename/token in this repo's basket
contains that exact sequence of words as a false-positive substring,
so adding \\b there would be an unmotivated widening of the class the
substring bugs above actually belong to.

--- Write-indicator discriminator (owns as a path, not as a word) ---
Earlier, WRITE_INDICATORS_RE carried a bare "\\bowns\\b" alternative:
the WORD "owns" appearing anywhere in the prompt (a read-only recon
dispatch discussing the owns mechanism itself, a quote of rule 11, a
mention of this very file's name) counted as a write indicator. That
is too coarse: the word "owns" as a topic is not the same fact as a
prompt that actually DECLARES an owns path. "\\bowns\\b" is REMOVED
from WRITE_INDICATORS_RE; a writing dispatch is now detected either by
one of the four write verbs, or by owns_declaration_has_path_token()
below finding a real path-like token attached to an "owns" marker.

is_path_like_token(tok) -- a single, shared predicate for "does this
token look like a real path": a Windows absolute path (drive letter +
":" + slash), a POSIX absolute path (leading "/"), or a glob carrying
BOTH "*" and a slash. A bare "*" with no slash (e.g. markdown
"**bold**") is deliberately NOT a path -- a naive "any token with a
`*`" predicate would treat ordinary bold-text markup in a manifest
paragraph as a path token.

owns_declaration_has_path_token(prompt) -- the write predicate used by
check 2: True when the prompt carries at least one "owns" marker
(word-bounded) with at least one real path-like token either on the
SAME line after the marker, or on the line immediately below it (a
one-line lookahead: an "owns:" header followed by the actual path on
the next line, the same shape this repo's own manifests commonly use).
A bare "owns" mention with no attached path token anywhere nearby is
NOT a write indicator.

--- Role-type WARN layer (declared tier vs. loaded agent role) ------
A SEPARATE, informational-only layer, symmetric with the given-path
layer below: it never blocks (never returns exit 2, never adds a
permissionDecision), it only adds text to additionalContext, and only
when decide() has already returned (0, ""). Motivation: the dispatch
label's leading token (LABEL_MODEL_PREFIX_RE) is a self-declared tier
("opus: review the diff"), but the tier ACTUALLY applied to the
worker session is whatever role file loads for tool_input's
subagent_type -- and those two facts can silently diverge (a
subagent_type with no matching role file at all, e.g. "general-
purpose", runs with no role instructions loaded even though its label
claims a specific tier).

role_type_warn(payload) resolves subagent_type against
`.claude/agents/*.md` in THIS repo (AGENTS_DIR, a fixed path relative
to this script's own location, not to payload["cwd"] -- the agent
role files are a fixed asset of this deployment, not something named
in dispatch text): a role file's STEM (filename without ".md") or its
frontmatter `name:` field, matched case-insensitively with surrounding
quotes stripped, identifies the role; filename match takes priority
over a `name:` field match (closer to how the harness itself resolves
subagent_type -> role file). The role file's frontmatter `model:`
field gives its bound model; the same substring family heuristic used
elsewhere in this tool set (haiku/sonnet/opus/fable) reduces it to a
tier family and compares that against the label's declared family.

Edges (all silent, no WARN): description absent/not a string/empty;
a label with the "claude" prefix (no family can be inferred);
subagent_type absent/not a string/blank; the `.claude/agents/`
directory itself missing entirely (a fresh checkout with no role
files yet -- this layer is purely informational, warning on every
single dispatch in that state would be noise with no corresponding
enforcement value); a role file found but with no `model:` line
(a known role with an unstated model -- not the same fact as "role
unknown"); a `model:` value that doesn't resolve to a known family
(e.g. a bare "claude" or a custom id); families that match. A role
file that IS found for the subagent_type, but whose declared family
differs from the label -- WARN (mismatch). No role file found at all
for a real subagent_type -- WARN (unknown role). Any exception inside
this layer is swallowed -- fail-open, the same posture as
given_path_warn().

Two WARNs in one call are joined into ONE additionalContext string
("\\n\\n"-joined, given-path first, role-type second) -- the harness
parses a hook's response as a single JSON object, so two separate
JSON blobs on stdout would not both be read.

--- Given-path WARN layer -------------------------------------------
A NEW, independent layer on top of the blocking gate above: exit-2
branches of decide() (checks 1/2/3) are NOT touched by this layer.
given_path_warn() is a SEPARATE function; decide() never calls it and
its result never participates in the exit code. main() calls it ONLY
when decide() has already returned (0, "") -- if the gate blocks for
another reason, we don't go further (no WARN is printed in that case,
by design: the blocking message already tells the dispatcher what to
fix). The result is ONLY an additionalContext JSON on stdout; main()'s
exit code stays 0 on this branch.

Extraction (extract_given_candidates -> GIVEN_ABS_WIN_PATH_RE /
GIVEN_REPO_REL_PATH_RE): two kinds of local paths --
 (a) an absolute Windows path: `[A-Za-z]:[\\\\/]...\\.ext` -- the path
     BODY (_GIVEN_PATH_BODY_CHAR) excludes whitespace/quotes/angle
     brackets/pipe and, DELIBERATELY, placeholder characters
     `<>*{}$` -- any placeholder (`<name>`, `*.py`, `{name}`, `$VAR`)
     breaks the match before the mandatory `\\.ext`, so such forms are
     simply never extracted (no separate exclusion filter is needed);
     comma/semicolon/newline are excluded from the body too -- an
     engineering choice against a match greedily crossing over
     "path1.py,path2.py" (no space) into one false single match.
 (b) a repo-relative path: ONLY with one of a small set of known
     top-level prefixes (tools|gateway|PROCESS|docs|.claude|.githooks)
     and a file extension -- bare directories/names don't match
     structurally (the regex requires a trailing `\\.ext`). A negative
     lookbehind before the prefix closes two things at once: (1) don't
     match the prefix when it's part of a larger word, (2) don't match
     it as a SUBSTRING inside an already-extracted absolute path (e.g.
     "D:/repo/tools/x.py" -- the character right before "tools" there
     is "/", the lookbehind excludes it -- the absolute and relative
     forms of the same file are never double-counted).

Known root and foreign trees: an absolute path candidate is checked
ONLY if it lies INSIDE the CURRENT dispatch's own cwd (payload["cwd"],
the same reference point this repo's other sidecar checks already
use) -- `_is_under_root`, a normcase+normpath comparison. An absolute
path OUTSIDE that root (any other drive/tree) is not checked at all,
neither warned about nor treated as an error: a dispatch can
legitimately mention absolute paths belonging to a different
deployment or a sibling repo, and this layer has no way to tell
whether those exist without walking a filesystem it has no business
walking.

Noise threshold (GIVEN_PATH_WARN_SUMMARY_THRESHOLD = 10,
format_given_path_warn): <= 10 missing paths -> the full list; > 10 ->
a summary ("N paths do not exist, first 3: ..."); both branches print
a WARN, only the FORM differs -- a silent no-op above the threshold
would make the summary-format text dead code.

Fail-open: given_path_warn() returns "" on any unrecognized payload/
tool_input/prompt; main() additionally wraps the call in try/except
(belt-and-suspenders) -- an adversarial input must not crash the
BLOCKING hook over a WARN-layer failure.
"""

import json
import os
import re
import sys
from pathlib import Path

# Fixed asset of this deployment -- see the module docstring,
# "Role-type WARN layer": the path is relative to this script's own
# location, not to payload["cwd"].
AGENTS_DIR = Path(__file__).resolve().parents[1] / ".claude" / "agents"

DOD_MARKERS_RE = re.compile(
    r"\bDoD\b|acceptance criteria|критери[ия] приёмки|\bwitness\b|"
    r"verification run|проверочн\w+ прогон",
    re.IGNORECASE,
)
# \b-bounded so a marker only matches as a whole word -- otherwise a
# short Cyrillic root (see WRITE_INDICATORS_RE below) would also
# match inside unrelated longer words sharing that root. "owns" is
# deliberately NOT one of these alternatives any more -- see the module
# docstring, "Write-indicator discriminator", for why the bare word is
# too coarse a signal and what replaces it
# (owns_declaration_has_path_token below).
WRITE_INDICATORS_RE = re.compile(
    r"\bwrite file\b|\bcreate file\b|\bedit file\b|\bmodify file\b|"
    r"\bзапиши\b|\bсоздай файл\b|\bправь\b|\bизмени файл\b",
    re.IGNORECASE,
)
# \b-bounded: an ordinary, longer Cyrillic word that merely CONTAINS
# the short given-marker root as a substring (e.g. an unrelated word
# meaning "sold out") must not count as a given-marker, same class as
# the write-indicator fix above.
MANIFEST_GIVEN_RE = re.compile(r"\bgiven\b|\bдано\b", re.IGNORECASE)
# \b-bounded: a filename merely containing "owns" as a substring in the
# given basket must not count as an owns-marker.
MANIFEST_OWNS_RE = re.compile(r"\bowns\b", re.IGNORECASE)
# Portable form check (see module docstring, check 3): a leading
# non-whitespace token followed by a separator. Deliberately NOT a
# fixed list of model/tier names -- this template doesn't know a
# deployment's actual bindings.
LABEL_MODEL_PREFIX_RE = re.compile(r"^\S+[ :-]")

# --- Write-indicator discriminator: a shared "is this a path token"
# predicate -- see the module docstring, "Write-indicator
# discriminator", for the full contract and rationale.
_PATH_TOKEN_WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")
_PATH_TOKEN_POSIX_ABS_RE = re.compile(r"^/")


def is_path_like_token(tok) -> bool:
    """The single, shared predicate for "does this token look like a
    path": a Windows absolute path (drive letter + ":" + slash), a
    POSIX absolute path (leading "/"), or a glob carrying BOTH "*" and
    a slash ("/" or "\\"). A bare "*" with no slash (e.g. markdown
    "**bold**") is NOT a path -- see the module docstring for the
    false-positive this excludes."""
    if not isinstance(tok, str) or not tok:
        return False
    if _PATH_TOKEN_WIN_ABS_RE.match(tok) or _PATH_TOKEN_POSIX_ABS_RE.match(tok):
        return True
    return "*" in tok and ("/" in tok or "\\" in tok)


# A closed set of manifest section headers (given -- or its Cyrillic
# equivalent marker, same short root discriminated \b-bounded in
# MANIFEST_GIVEN_RE above -- owns, non-goals, handoff) -- used only to
# know where an owns declaration's CONTINUATION line ends, so the
# one-line lookahead below does not wander into the next manifest
# section.
_OWNS_SECTION_STOP_RE = re.compile(
    r"^\s*(?:\*\*)?(given|дано|owns|non-goals|handoff)\b", re.IGNORECASE
)
# After the "owns" marker, when the marker's own line carries no path:
# "this is a declaration, not prose" only when what follows is, at
# most, an optional parenthetical note plus separator punctuation
# (colon/dash/asterisks/quotes/spaces) up to the end of the line.
_OWNS_MARKER_JUNK_ONLY_RE = re.compile(r"^(?:\s*\([^)]*\))?[\s*:\-—«»\"']*$")
_OWNS_DECLARATION_PREFIX_RE = re.compile(r"^\s*(?:[-*•]\s+)?(?:\*\*)?$")
_OWNS_TOKEN_SPLIT_RE = re.compile(r"[;,\s]+")
_OWNS_TOKEN_EDGE_STRIP = "\"'`()[]{}«»„“”.,:-"


def _owns_region_has_path_token(text: str) -> bool:
    for raw in _OWNS_TOKEN_SPLIT_RE.split(text):
        tok = raw.strip(_OWNS_TOKEN_EDGE_STRIP)
        if is_path_like_token(tok):
            return True
    return False


def owns_declaration_has_path_token(prompt: str) -> bool:
    """The write predicate used by check 2 (see the module docstring,
    "Write-indicator discriminator"): True when the prompt carries at
    least one "owns" marker (MANIFEST_OWNS_RE, word-bounded) with at
    least one real path-like token (is_path_like_token) either on the
    SAME line after the marker, or on the line immediately below it (a
    one-line lookahead: an "owns:" header followed by the actual path
    on the next line)."""
    if not isinstance(prompt, str) or not prompt:
        return False
    lines = prompt.splitlines()
    for i, line in enumerate(lines):
        m = MANIFEST_OWNS_RE.search(line)
        if not m:
            continue
        if _owns_region_has_path_token(line[m.end():]):
            return True
        prefix = line[: m.start()]
        remainder = line[m.end():]
        if not _OWNS_DECLARATION_PREFIX_RE.match(prefix):
            continue
        if not _OWNS_MARKER_JUNK_ONLY_RE.match(remainder):
            continue
        if i + 1 >= len(lines):
            continue
        cont = lines[i + 1]
        if cont.strip() == "" or _OWNS_SECTION_STOP_RE.match(cont):
            continue
        if _owns_region_has_path_token(cont):
            return True
    return False


BLOCK_MESSAGE_NO_DOD = (
    "A builder dispatch with no DoD does not go out (rule 11): add "
    "acceptance criteria and a verification run whose output becomes "
    "the witness."
)
BLOCK_MESSAGE_NO_MANIFEST = (
    "A writing dispatch with no context manifest (given/owns) does not "
    "go out (rule 11, dispatch-context-manifest rule)."
)
BLOCK_MESSAGE_NO_LABEL = (
    "The dispatch label starts with the worker's tier (rule 7): "
    "e.g. 'sonnet: ...'."
)


def decide(payload: dict) -> tuple[int, str]:
    """Pure decision logic, no I/O -- directly testable. Returns
    (exit_code, stderr_message); "" means "write nothing to stderr"."""
    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, ""

    tool_input = payload.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type")
    prompt = tool_input.get("prompt") or ""
    description = tool_input.get("description")

    if subagent_type == "builder":
        if not DOD_MARKERS_RE.search(prompt):
            return 2, BLOCK_MESSAGE_NO_DOD

        # The write signal is EITHER one of the four write verbs OR an
        # owns: declaration that actually carries a path-like token --
        # see the module docstring, "Write-indicator discriminator":
        # the bare word "owns" alone is no longer sufficient.
        is_write = bool(WRITE_INDICATORS_RE.search(prompt)) or owns_declaration_has_path_token(
            prompt
        )
        if is_write:
            has_manifest = bool(MANIFEST_GIVEN_RE.search(prompt)) and bool(
                MANIFEST_OWNS_RE.search(prompt)
            )
            if not has_manifest:
                return 2, BLOCK_MESSAGE_NO_MANIFEST

    if description is not None:
        if not LABEL_MODEL_PREFIX_RE.search(description):
            return 2, BLOCK_MESSAGE_NO_LABEL

    return 0, ""


# --- Given-path WARN layer ------------------------------------------------
# See the module docstring, "Given-path WARN layer", for the full
# design rationale. This layer does NOT participate in decide() and
# does not change the exit code -- a separate function, called ONLY
# from main(), ONLY when decide() has already returned (0, "").

# Characters excluded from the "body" of a path candidate: whitespace/
# quotes/angle brackets/pipe, placeholder characters `<>*{}$` (see the
# module docstring, "Extraction") and comma/semicolon/newline (list
# separators -- an engineering choice against greedily crossing over a
# no-space list like "path1.py,path2.py" into one false match).
_GIVEN_PATH_BODY_CHAR = r'[^\s"\'<>|?*{}$,;\n]'

# Critic finding: the greedy `*` on the path body made BOTH regexes
# QUADRATIC on long strings with no trailing dot-extension (measured:
# 9.8s on an 80KB pathological prompt, 89.5s on 240KB -- "C:/"*20000 +
# "a"*20000 -- a hang, not an exception, so the try/except around
# given_path_warn()/main() does not catch it). FIX: the body is bounded
# to {0,300} instead of `*` -- a linear upper bound on backtracking
# relative to the body length, not quadratic in the whole prompt's
# length. CONSEQUENCE (documented, not a bug): a path whose body is
# longer than 300 characters before the extension is simply NOT
# EXTRACTED by this regex (a truncation, not a partial match) -- no
# GIVEN-PATH WARN is promised for such a path; 300 is chosen with a
# generous margin over any realistic path length in this repo.
GIVEN_ABS_WIN_PATH_RE = re.compile(
    r"(?<!\w)[A-Za-z]:[\\/]" + _GIVEN_PATH_BODY_CHAR + r"{0,300}\.[A-Za-z0-9]{1,10}\b"
)

_GIVEN_REPO_REL_PREFIX = r"(?:tools|gateway|PROCESS|docs|\.claude|\.githooks)"
GIVEN_REPO_REL_PATH_RE = re.compile(
    r"(?<![\w/\\])"
    + _GIVEN_REPO_REL_PREFIX
    + r"/"
    + _GIVEN_PATH_BODY_CHAR
    + r"{0,300}\.[A-Za-z0-9]{1,10}\b"
)

GIVEN_PATH_WARN_SUMMARY_THRESHOLD = 10


def extract_given_candidates(prompt: str) -> list:
    """Returns [(path_as_written, is_absolute), ...] -- deduplicated,
    order of first appearance. See the module docstring, "Extraction"."""
    if not isinstance(prompt, str) or not prompt:
        return []
    seen_set = set()
    candidates = []
    for m in GIVEN_ABS_WIN_PATH_RE.finditer(prompt):
        tok = m.group(0)
        if tok not in seen_set:
            seen_set.add(tok)
            candidates.append((tok, True))
    for m in GIVEN_REPO_REL_PATH_RE.finditer(prompt):
        tok = m.group(0)
        if tok not in seen_set:
            seen_set.add(tok)
            candidates.append((tok, False))
    return candidates


def _is_under_root(path_str: str, root: str) -> bool:
    """True when path_str lies inside root (root itself included) --
    compared via normcase(normpath(...)) (case-insensitive on Windows,
    separators normalized). See the module docstring, "Known root and
    foreign trees"."""
    try:
        norm_path = os.path.normcase(os.path.normpath(path_str))
        norm_root = os.path.normcase(os.path.normpath(root))
    except Exception:
        return False
    return norm_path == norm_root or norm_path.startswith(norm_root + os.sep)


def find_missing_given_paths(prompt: str, repo_root: str) -> list:
    """Returns the paths (as written) from extract_given_candidates(prompt)
    that do NOT exist -- an absolute path OUTSIDE repo_root (a foreign
    tree) is skipped entirely, never counted as "missing" (see the
    module docstring, "Known root and foreign trees")."""
    missing = []
    for tok, is_abs in extract_given_candidates(prompt):
        if is_abs:
            if not _is_under_root(tok, repo_root):
                continue
            exists = os.path.exists(tok)
        else:
            exists = os.path.exists(os.path.join(repo_root, tok))
        if not exists:
            missing.append(tok)
    return missing


def format_given_path_warn(missing: list) -> str:
    """"" on an empty list; otherwise the full form (<=10) or a
    summary (>10) -- see the module docstring, "Noise threshold"."""
    if not missing:
        return ""
    if len(missing) <= GIVEN_PATH_WARN_SUMMARY_THRESHOLD:
        listed = ", ".join(missing)
        return (
            "GIVEN-PATH WARN: the dispatch text names paths that do not "
            f"exist: {listed} -- check the spec's facts against their carrier."
        )
    head = ", ".join(missing[:3])
    return (
        f"GIVEN-PATH WARN: {len(missing)} paths do not exist, first 3: "
        f"{head} -- check the spec's facts against their carrier."
    )


def given_path_warn(payload: dict) -> str:
    """"" -- nothing to warn about (payload isn't Task/Agent, no
    prompt, every candidate exists/is foreign/there are none). Otherwise
    the ready-made WARN text (see format_given_path_warn)."""
    if not isinstance(payload, dict):
        return ""
    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return ""

    repo_root = payload.get("cwd")
    if not isinstance(repo_root, str) or not repo_root:
        repo_root = os.getcwd()

    missing = find_missing_given_paths(prompt, repo_root)
    return format_given_path_warn(missing)


# --- Role-type WARN layer -------------------------------------------
# See the module docstring, "Role-type WARN layer", for the full
# design rationale. Symmetric with the given-path layer above: does
# NOT participate in decide() and does not change the exit code --
# called ONLY from main(), ONLY when decide() has already returned
# (0, "").

ROLE_TYPE_WARN_MISMATCH = (
    "ROLE-TYPE WARN: the dispatch label declares tier '{declared_family}', "
    "but the role file .claude/agents/ for subagent_type='{subagent_type}' "
    "declares model: {bound_model} (family '{bound_family}') -- "
    "a type<->tier mismatch."
)
ROLE_TYPE_WARN_UNKNOWN_ROLE = (
    "ROLE-TYPE WARN: no role file in .claude/agents/ for type "
    "'{subagent_type}' -- the declared tier '{declared_family}' is not "
    "backed by any loaded role."
)

_FAMILY_NAMES = ("fable", "opus", "sonnet", "haiku")
# A non-greedy variant of LABEL_MODEL_PREFIX_RE's leading-token check,
# local to this layer: LABEL_MODEL_PREFIX_RE itself (`^\S+[ :-]`,
# greedy) is used unchanged by check 3 above and must not be touched;
# this layer additionally needs the FIRST separator's position (a
# lazy `\S+?` stops at the first match rather than backtracking from
# the end) to read out the leading token itself, not just confirm one
# exists.
_LABEL_LEADING_TOKEN_RE = re.compile(r"^(\S+?)[ :-]")
_FRONTMATTER_BLOCK_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)
_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(\S+)", re.MULTILINE)
_FRONTMATTER_MODEL_RE = re.compile(r"^model:\s*(\S+)", re.MULTILINE)


def _model_family(model_id) -> str | None:
    """The same substring heuristic used elsewhere in this tool set for
    a bound model's tier family -- implemented locally (this layer
    does not import any other gate module for it)."""
    if not isinstance(model_id, str) or not model_id:
        return None
    low = model_id.lower()
    for fam in _FAMILY_NAMES:
        if fam in low:
            return fam
    return None


def _strip_quotes(token: str) -> str:
    """Strips EXACTLY one pair of surrounding quotes (single or
    double) from a captured token. YAML frontmatter legally writes
    `name: "scout"` / `model: 'sonnet'`; \\S+ captures the quotes
    literally, and an exact comparison against a quoted value would
    otherwise never match. A quote INSIDE the value (not on both edges
    at once) is left untouched -- the condition requires the first and
    last character to match."""
    if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
        return token[1:-1]
    return token


def _read_frontmatter(path: Path):
    """The text of the frontmatter block (between the first and second
    "---" line) of a role file, or None -- the file is unreadable OR
    no frontmatter is anchored there (no opening/closing "---"). Any
    read exception is swallowed here -- see the module docstring,
    "Role-type WARN layer", "Edges"."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None
    m = _FRONTMATTER_BLOCK_RE.match(text)
    return m.group(1) if m else None


def _model_of(frontmatter) -> str | None:
    """The frontmatter's model: value (quotes stripped), None if there
    is no model: line."""
    m2 = _FRONTMATTER_MODEL_RE.search(frontmatter)
    return _strip_quotes(m2.group(1).strip()) if m2 else None


def _find_agent_role_model(subagent_type_norm: str):
    """subagent_type_norm is already .strip().lower(). Returns (True,
    model|None) when a `.claude/agents/*.md` file is found whose
    filename (without ".md") OR frontmatter `name:` field matches
    case-insensitively (surrounding quotes stripped); (False, None) --
    no file matched. model is that file's frontmatter model: value
    (None if the frontmatter is unreadable/unanchored/has no model:
    line) -- "a known role with no stated model" is not the same fact
    as "role unknown".

    PRIORITY: an exact FILENAME match resolves FIRST, before any
    `name:` field match -- closer to how the harness itself resolves
    subagent_type (matched against the FILENAME in the agents
    directory). The `name:` match is tried ONLY if no file in the
    directory matched by filename."""
    candidates = sorted(AGENTS_DIR.glob("*.md"))

    for path in candidates:
        if path.stem.strip().lower() == subagent_type_norm:
            frontmatter = _read_frontmatter(path)
            if frontmatter is None:
                return True, None
            return True, _model_of(frontmatter)

    for path in candidates:
        frontmatter = _read_frontmatter(path)
        if frontmatter is None:
            continue
        m = _FRONTMATTER_NAME_RE.search(frontmatter)
        if m and _strip_quotes(m.group(1).strip()).lower() == subagent_type_norm:
            return True, _model_of(frontmatter)

    return False, None


def role_type_warn(payload: dict) -> str:
    """"" -- nothing to warn about (payload isn't Task/Agent, required
    fields absent/not strings, a "claude:" label, the .claude/agents/
    directory missing, a known role with no model: in its frontmatter,
    or families matching). Otherwise the ready-made WARN text (a
    type<->tier mismatch OR a subagent_type with no role file). See the
    module docstring, "Role-type WARN layer", for the full contract.
    Wrapped entirely in try/except -- fail-open on ANY exception, the
    same posture as the rest of this file's WARN layers."""
    try:
        if not isinstance(payload, dict):
            return ""
        tool_name = payload.get("tool_name")
        if tool_name not in ("Task", "Agent"):
            return ""
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return ""
        subagent_type = tool_input.get("subagent_type")
        if not isinstance(subagent_type, str) or not subagent_type.strip():
            return ""
        description = tool_input.get("description")
        if not isinstance(description, str) or not description:
            return ""
        if not LABEL_MODEL_PREFIX_RE.search(description):
            return ""
        token_m = _LABEL_LEADING_TOKEN_RE.match(description)
        if not token_m:
            return ""
        declared_family = token_m.group(1).lower()
        if declared_family not in _FAMILY_NAMES:
            # Not a recognized tier family (e.g. "claude:", a custom
            # label token) -- no family to compare, silent.
            return ""
        if not AGENTS_DIR.is_dir():
            # The directory is missing entirely (a fresh checkout) --
            # silent, see the module docstring, "Edges".
            return ""

        subagent_type_norm = subagent_type.strip().lower()
        role_known, bound_model = _find_agent_role_model(subagent_type_norm)
        if not role_known:
            return ROLE_TYPE_WARN_UNKNOWN_ROLE.format(
                subagent_type=subagent_type, declared_family=declared_family
            )
        if not bound_model:
            return ""
        bound_family = _model_family(bound_model)
        if bound_family is None or bound_family == declared_family:
            return ""
        return ROLE_TYPE_WARN_MISMATCH.format(
            declared_family=declared_family,
            subagent_type=subagent_type,
            bound_model=bound_model,
            bound_family=bound_family,
        )
    except Exception:
        return ""


def _reconfigure_stderr_utf8():
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stderr_utf8()

    # Read stdin as raw bytes and decode explicitly as UTF-8 rather
    # than through the text-mode sys.stdin.read(): the latter decodes
    # with the platform's locale encoding, which on some systems (e.g.
    # Windows with a non-UTF-8 code page) is NOT UTF-8 and would
    # mangle any non-ASCII payload before the regexes above ever see
    # it. errors="replace" keeps this fail-open on malformed bytes.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        # Unparseable input -- fail open, same principle as every
        # other hook in this file set.
        return 0

    exit_code, message = decide(payload)
    if exit_code == 2:
        sys.stderr.write(message + "\n")
        return 2

    # Both WARN layers are considered only when the gate itself did NOT
    # block (see the module docstrings, "Given-path WARN layer" /
    # "Role-type WARN layer"); try/except on EACH is belt-and-
    # suspenders -- neither layer must ever crash the blocking hook
    # with a traceback. Given-path first, role-type second (fixed
    # order, see "Role-type WARN layer" -- two WARNs in one call").
    try:
        warn_given = given_path_warn(payload)
    except Exception:
        warn_given = ""
    try:
        warn_role = role_type_warn(payload)
    except Exception:
        warn_role = ""

    warn_parts = [w for w in (warn_given, warn_role) if w]
    if warn_parts:
        _reconfigure_stdout_utf8()
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n\n".join(warn_parts),
            }
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
