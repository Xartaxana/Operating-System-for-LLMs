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

--- Region-aware filtering (md_regions integration) -------------------
A guard cannot tell an author's own claim from quoted/nested content:
a bare regex match on DoD/given/owns/write markers does not know
whether it landed in the dispatcher's own prose or inside a fenced/
quoted EXAMPLE of someone else's manifest. toolkit/tools/md_regions.py
(imported below, try/except -- ImportError degrades this whole layer
to bare-regex behavior, see I-0 below) splits the prompt into regions
(prose / fenced / blockquote / inline_code); `_is_quoted(region)` is
the single polarity used by every layer in this file: fenced OR
blockquote -> quoted (excluded/flagged), prose and inline code are NOT
quoted (a manifest written in backticks, e.g. "owns: `D:/x.py`", still
counts) -- the same polarity given_path_warn already uses for its own
candidates. An UNTERMINATED fence is read as prose, not a quote (before
any other branch): treating it as a quote would only ever WIDEN the
silent zone, which is the wrong default for an ambiguous case.

I-0 (any md_regions failure -- ImportError, an exception inside
scan(), or a degraded=True result): every region-aware function below
falls back to the exact bare-regex behavior this file had before this
layer existed -- byte for byte. decide()'s check 2 (B2-write) is the
one branch where this file's exit code can legitimately change from
its pre-region-aware behavior: a write verb / owns-declaration whose
ONLY occurrence sits inside a quote no longer counts as a write
signal (`_region_aware_is_write`) -- this can only LOOSEN the block,
never tighten it (checks 1/3 and the given/owns manifest test itself
are untouched). Three new WARN-only layers make that direction
visible instead of silent: dod_quoted_warn/manifest_quoted_warn (the
ONLY marker match found is inside a quote -- decide() still counted
it, by design, this just flags it for a manual look) and
write_quoted_warn (the one case where a write signal WAS quoted-out of
check 2 with no given/owns marker present at all -- the quiet flip
gets a WARN so it is never a silent pass).

freshness_warn() (below) reuses the SAME scan()/_is_quoted() pair for
its own line-anchor check but does NOT get the bare-regex I-0
fallback: with no region info at all, the whole layer stays silent
(a dispatch text with no anchor/check-token candidate never touches
the filesystem or the scanner in the first place -- a cheap
"any candidate at all" prefilter runs before scan() is called).
"""

import bisect
import json
import os
import re
import sys
import threading
from pathlib import Path

try:
    from tools.md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE  # package-style
except ImportError:
    try:
        from md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE  # sibling-module fallback
    except ImportError:
        scan = None
        KIND_FENCED = "fenced"
        KIND_BLOCKQUOTE = "blockquote"

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
#
# ROOT-ONLY GUARD (route port, node D1, staff twin tools/dispatch_gate.py
# ~:863-884): both absolute regexes require >=1 SEGMENT character
# (not a slash, not whitespace) right after the root slash -- a bare
# root with no segment ("/", "//", "D:\\", "D:/") is not itself a path
# token. Before this guard, "/" and "D:\\" matched as valid path
# tokens: normalize_path("/") self-intersects with any other stray
# "/" in a prompt (a false owns-overlap-shaped positive on nearly any
# text carrying a bare slash), and "D:\\"/"D:/" normalize to "d:" --
# an intersection with the ENTIRE D: drive. A rootless phantom root is
# not an owned path in any practical sense. Only the ROOT-WITHOUT-A-
# SEGMENT class is excluded here -- a doubled root WITH a segment
# ("//foo", "//server/share", "D://x") still counts (the segment is
# present); "/etc" (one segment, no extension) is a token, "/" alone
# is not -- both edges are tested (rule 6a). The glob branch below
# ("*" + a slash) is unaffected -- this guard only narrows the two
# absolute-path regexes, checked first, same order as before.
_PATH_TOKEN_WIN_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]+[^\\/\s]")
_PATH_TOKEN_POSIX_ABS_RE = re.compile(r"^/+[^/\s]")


def is_path_like_token(tok) -> bool:
    """The single, shared predicate for "does this token look like a
    path": a Windows absolute path (drive letter + ":" + slash + a
    segment), a POSIX absolute path (leading "/" + a segment -- see
    "ROOT-ONLY GUARD" above), or a glob carrying BOTH "*" and
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


# =======================================================================
# Region-aware helpers (md_regions integration) -- see the module
# docstring, "Region-aware filtering", for the full design rationale.
# =======================================================================


def _safe_scan(text: str):
    """I-0: None on a missing module / an exception inside scan() /
    degraded=True -- three failure shapes collapse to one "no region
    info" signal, so every caller below has exactly one fallback
    branch to write."""
    if scan is None:
        return None
    try:
        result = scan(text)
    except Exception:
        return None
    if result.degraded:
        return None
    return result


def _region_at(scan_result, offset: int):
    """bisect over scan_result.regions -- mirrors md_regions.kind_at(),
    but returns the WHOLE Region (needed for .unterminated, see
    _is_quoted)."""
    regions = scan_result.regions
    if not regions:
        return None
    starts = [r.start for r in regions]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        return None
    region = regions[idx]
    if region.start <= offset < region.end:
        return region
    return None


def _is_quoted(region) -> bool:
    """The single "quoted" polarity used by every region-aware layer in
    this file -- see the module docstring, "Region-aware filtering".
    region is None (end of text / outside coverage) -> NOT quoted (the
    prose default). An unterminated fence -> NOT quoted (checked
    BEFORE any other branch -- ambiguity must not widen the silent
    zone). Otherwise: fenced OR blockquote in kinds -> quoted; inline
    code and prose are NOT quoted (backticks don't silence a real
    manifest declaration)."""
    if region is None:
        return False
    if KIND_FENCED in region.kinds and region.unterminated:
        return False
    if KIND_FENCED in region.kinds or KIND_BLOCKQUOTE in region.kinds:
        return True
    return False


_QUOTE_TRIGGER_CHARS = "`>~"


def _prompt_has_quote_trigger(prompt: str) -> bool:
    """Cheap prefilter: without one of these characters anywhere in the
    text, no region can possibly be fenced/blockquote -- the same fact
    md_regions._no_markers_whole_text() uses internally."""
    return any(ch in prompt for ch in _QUOTE_TRIGGER_CHARS)


def _line_start_offsets(text: str) -> list:
    """Character offset of the start of each text.splitlines() line."""
    offsets = []
    pos = 0
    for wt in text.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(wt)
    return offsets


def _region_aware_write_indicator_present(prompt: str, scan_result) -> bool:
    """True when at least one WRITE_INDICATORS_RE match sits OUTSIDE a
    quote. scan_result is None -> I-0 fallback, bare bool(search())."""
    if scan_result is None:
        return bool(WRITE_INDICATORS_RE.search(prompt))
    for m in WRITE_INDICATORS_RE.finditer(prompt):
        if not _is_quoted(_region_at(scan_result, m.start())):
            return True
    return False


def _region_aware_owns_declaration_has_path_token(prompt: str, scan_result) -> bool:
    """Region-aware twin of owns_declaration_has_path_token() above --
    the SAME line-scanning algorithm (marker -> same-line path OR the
    next continuation line), with ONE addition: an owns-marker match
    that sits INSIDE a quote is skipped entirely (a quoted owns
    declaration does not feed check 2). scan_result is None -> I-0
    fallback to the bare function above, byte for byte."""
    if scan_result is None:
        return owns_declaration_has_path_token(prompt)
    if not isinstance(prompt, str) or not prompt:
        return False
    lines = prompt.splitlines()
    offsets = _line_start_offsets(prompt)
    for i, line in enumerate(lines):
        m = MANIFEST_OWNS_RE.search(line)
        if not m:
            continue
        marker_offset = offsets[i] + m.start()
        if _is_quoted(_region_at(scan_result, marker_offset)):
            continue  # a quoted owns-declaration does not feed check 2
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


def _region_aware_is_write(prompt: str) -> bool:
    """decide()'s check-2 write signal -- replaces the bare
    `bool(WRITE_INDICATORS_RE.search(prompt)) or
    owns_declaration_has_path_token(prompt)` computation. Two-part cheap
    prefilter before scan() is ever called: (a) a bare marker hit (the
    same pair of predicates decide() already computed) -- nothing found
    -> False, scan() not called; (b) no quote-trigger character
    anywhere in the text -- nothing to filter, the bare True result is
    returned directly. Only when BOTH conditions hold does scan() run,
    exactly once."""
    bare_write = bool(WRITE_INDICATORS_RE.search(prompt))
    bare_owns = owns_declaration_has_path_token(prompt)
    if not (bare_write or bare_owns):
        return False
    if not _prompt_has_quote_trigger(prompt):
        return True
    scan_result = _safe_scan(prompt)
    if scan_result is None:
        return True  # I-0: same bare result that gave True above
    return _region_aware_write_indicator_present(
        prompt, scan_result
    ) or _region_aware_owns_declaration_has_path_token(prompt, scan_result)


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
        # the bare word "owns" alone is no longer sufficient. Region-
        # aware (see "Region-aware filtering" in the module docstring):
        # a signal whose ONLY occurrence sits inside a quote no longer
        # counts -- the ONLY line in decide() this port's md_regions
        # integration changes.
        is_write = _region_aware_is_write(prompt)
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

# "logs" added (route port t-batch 2026-08-25, node D1) -- the staff
# twin's own prefix set carries it (docs/tasks/2026-08-25_kit-
# v0.9.0-batch-specs.md, node C3 delta 1): a given-basket entry naming
# a repo-relative logs/ path (e.g. "owns: logs/routing-log.jsonl")
# extracts and checks like any other known top-level directory.
_GIVEN_REPO_REL_PREFIX = r"(?:tools|gateway|PROCESS|docs|logs|\.claude|\.githooks)"
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


def extract_given_candidates_region_aware(prompt: str, scan_result) -> list:
    """Region-aware twin of extract_given_candidates() -- the SAME two
    regexes (unchanged), but each match is checked against its own
    position's quotedness. A token QUALIFIES (is included in the
    result) when AT LEAST ONE of its occurrences is NOT quoted -- even
    if OTHER occurrences of the same token sit inside a quote. Dedup
    preserved -- result order is the order of the first appearance of a
    qualifying token. scan_result is None -> I-0 fallback to the bare
    function above."""
    if scan_result is None:
        return extract_given_candidates(prompt)
    if not isinstance(prompt, str) or not prompt:
        return []
    order = []
    seen = {}
    for pattern, is_abs in ((GIVEN_ABS_WIN_PATH_RE, True), (GIVEN_REPO_REL_PATH_RE, False)):
        for m in pattern.finditer(prompt):
            tok = m.group(0)
            quoted = _is_quoted(_region_at(scan_result, m.start()))
            if tok not in seen:
                seen[tok] = {"is_abs": is_abs, "any_unquoted": not quoted}
                order.append(tok)
            elif not quoted:
                seen[tok]["any_unquoted"] = True
    return [(tok, seen[tok]["is_abs"]) for tok in order if seen[tok]["any_unquoted"]]


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


def _missing_given_paths_from_candidates(candidates: list, repo_root: str) -> list:
    """Shared existence-check body -- takes an already-extracted
    candidate list (bare or region-aware) instead of a prompt, so both
    given_path_warn() below (region-aware) and find_missing_given_paths()
    (bare, kept for its existing callers/tests) share one
    implementation."""
    missing = []
    for tok, is_abs in candidates:
        if is_abs:
            if not _is_under_root(tok, repo_root):
                continue
            exists = os.path.exists(tok)
        else:
            exists = os.path.exists(os.path.join(repo_root, tok))
        if not exists:
            missing.append(tok)
    return missing


def find_missing_given_paths(prompt: str, repo_root: str) -> list:
    """Returns the paths (as written) from extract_given_candidates(prompt)
    that do NOT exist -- an absolute path OUTSIDE repo_root (a foreign
    tree) is skipped entirely, never counted as "missing" (see the
    module docstring, "Known root and foreign trees"). Bare (not
    region-aware) -- kept as-is for its existing callers; given_path_warn()
    below calls the region-aware extraction directly."""
    return _missing_given_paths_from_candidates(extract_given_candidates(prompt), repo_root)


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
    the ready-made WARN text (see format_given_path_warn). Region-aware
    (see the module docstring, "Region-aware filtering"): a given-path
    candidate whose ONLY occurrence sits inside a quote is not checked
    for existence at all -- I-0 fallback to the bare
    find_missing_given_paths() when no region info is available."""
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

    scan_result = _safe_scan(prompt)
    if scan_result is None:
        missing = find_missing_given_paths(prompt, repo_root)
    else:
        candidates = extract_given_candidates_region_aware(prompt, scan_result)
        missing = _missing_given_paths_from_candidates(candidates, repo_root)
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

# Route port, node D1 (staff twin ~:1934/:1943): the single UNKNOWN-ROLE
# message split into two cases with OPPOSITE actions for the reader --
# a project role missing a file is a gap to CLOSE (add the role file),
# a harness built-in type missing a file is EXPECTED (nothing to add;
# just verify the tier separately if it matters). Both share the
# "no role file" substring byte for byte -- same rule-of-three prefix,
# one registry line covers either case, and any test pinning that
# phrase stays green regardless of which branch fires.
ROLE_TYPE_WARN_PROJECT = (
    "ROLE-TYPE WARN: no role file in .claude/agents/ for type "
    "'{subagent_type}' -- the declared tier '{declared_family}' is not "
    "backed by any loaded role, and the worker's actual model can "
    "silently diverge from what's declared -- add a role file with a "
    "model: field for this project role; or, if this is a harness "
    "built-in type not yet in the known list, verify the tier by a "
    "transcript measurement and add the type to the list."
)
ROLE_TYPE_WARN_BUILTIN_TYPE = (
    "ROLE-TYPE WARN: the harness built-in type '{subagent_type}' has no "
    "role file in .claude/agents/ -- expected, not a defect of this "
    "layer, but the declared tier '{declared_family}' stays unconfirmed "
    "and the worker's actual model can diverge from it unnoticed -- "
    "verify the tier by a transcript measurement if the dispatch "
    "decision depends on it."
)

# A CLOSED list of harness built-in subagent types that carry no
# project role file by design (route port, node D1, staff twin's
# _ROLE_TYPE_BUILTIN_HARNESS_TYPES): matched case-insensitively against
# the already-normalized subagent_type_norm. This list can go stale as
# the harness adds types -- that is a finding, not a silent failure:
# a miss falls through to ROLE_TYPE_WARN_PROJECT, whose text literally
# says "or, if this is a harness built-in type not yet in the known
# list ... add the type to the list", not a silent pass.
_ROLE_TYPE_BUILTIN_HARNESS_TYPES = frozenset(
    {"general-purpose", "claude-code-guide", "explore", "plan", "statusline-setup"}
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
            # PROJECT/BUILTIN_TYPE split (route port, node D1): the
            # branching LOGIC (what counts as an unknown role) is
            # untouched -- only the choice of TEXT differs.
            if subagent_type_norm in _ROLE_TYPE_BUILTIN_HARNESS_TYPES:
                return ROLE_TYPE_WARN_BUILTIN_TYPE.format(
                    subagent_type=subagent_type, declared_family=declared_family
                )
            return ROLE_TYPE_WARN_PROJECT.format(
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


# =======================================================================
# "Stricter, WARN-only" layers (route port, node D1): B1 (DoD-marker)
# and B2-manifest (given/owns) checks inside decide() are NOT touched --
# a quoted marker still counts exactly as it does today. These layers
# only INFORM: the sole marker match found sits inside a quote, so
# decide() may have counted a marker that isn't the author's own claim
# -- sanity-check it by hand.
# =======================================================================

_QUOTED_SNIPPET_MAX_LEN = 80

DOD_QUOTED_WARN_MESSAGE = (
    "DOD-QUOTED WARN: the only DoD marker found in this dispatch sits "
    "inside a quote/fence (\"{preview}\") -- check 1 counts it literally "
    "(decide() is untouched), but a quoted marker may be someone else's "
    "text, not the author's own DoD -- verify by hand (rule 11)."
)
MANIFEST_QUOTED_WARN_MESSAGE = (
    "MANIFEST-QUOTED WARN: every occurrence of the manifest marker "
    "'{marker}' found in this dispatch sits inside a quote/fence -- the "
    "declaration may be someone else's example, not the author's own "
    "manifest -- verify by hand (dispatch-context-manifest rule)."
)


def _truncate_snippet(s: str, max_len: int = _QUOTED_SNIPPET_MAX_LEN) -> str:
    s = s.strip()
    if len(s) > max_len:
        return s[:max_len] + "..."
    return s


def dod_quoted_warn(payload: dict) -> str:
    """"" -- nothing to warn about (not Task/Agent, not builder, prompt
    absent/empty, no DoD match at all, no quote-trigger character in
    the text at all, the module is unavailable/degraded, every match
    has at least one UNquoted occurrence). Otherwise -- EVERY
    DOD_MARKERS_RE match sits inside a fenced/blockquote region. Purely
    informational, symmetric with given_path_warn/role_type_warn --
    does not participate in the exit code, called ONLY from main(),
    ONLY when decide() has already returned (0, "")."""
    try:
        if not isinstance(payload, dict):
            return ""
        if payload.get("tool_name") not in ("Task", "Agent"):
            return ""
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return ""
        if tool_input.get("subagent_type") != "builder":
            return ""
        prompt = tool_input.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            return ""
        matches = list(DOD_MARKERS_RE.finditer(prompt))
        if not matches:
            return ""  # nothing to scan
        if not _prompt_has_quote_trigger(prompt):
            return ""  # no quote-capable character -- nothing can be quoted
        scan_result = _safe_scan(prompt)
        if scan_result is None:
            return ""  # I-0: no region info -- nothing to warn about
        if not all(_is_quoted(_region_at(scan_result, mm.start())) for mm in matches):
            return ""
        preview = _truncate_snippet(matches[0].group(0))
        return DOD_QUOTED_WARN_MESSAGE.format(preview=preview)
    except Exception:
        return ""


def manifest_quoted_warn(payload: dict) -> str:
    """"" -- nothing to warn about (symmetric with dod_quoted_warn
    above). Otherwise -- EVERY MANIFEST_GIVEN_RE match sits inside a
    quote, OR EVERY MANIFEST_OWNS_RE match sits inside a quote (given
    is checked first -- matches decide()'s has_manifest = given AND
    owns order). scan() is called AT MOST once -- computed once, reused
    for both checks."""
    try:
        if not isinstance(payload, dict):
            return ""
        if payload.get("tool_name") not in ("Task", "Agent"):
            return ""
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return ""
        if tool_input.get("subagent_type") != "builder":
            return ""
        prompt = tool_input.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            return ""
        given_matches = list(MANIFEST_GIVEN_RE.finditer(prompt))
        owns_matches = list(MANIFEST_OWNS_RE.finditer(prompt))
        if not given_matches and not owns_matches:
            return ""  # neither given nor owns -- nothing to scan
        if not _prompt_has_quote_trigger(prompt):
            return ""  # no quote-capable character
        scan_result = _safe_scan(prompt)
        if scan_result is None:
            return ""  # I-0: no region info -- nothing to warn about
        if given_matches and all(
            _is_quoted(_region_at(scan_result, mm.start())) for mm in given_matches
        ):
            return MANIFEST_QUOTED_WARN_MESSAGE.format(marker="given")
        if owns_matches and all(
            _is_quoted(_region_at(scan_result, mm.start())) for mm in owns_matches
        ):
            return MANIFEST_QUOTED_WARN_MESSAGE.format(marker="owns")
        return ""
    except Exception:
        return ""


# --- The one case where the region filter can flip decide()'s exit
# code with no manifest marker present at all -- see the module
# docstring, "Region-aware filtering": a write verb / owns-declaration
# whose ONLY occurrence is quoted, and neither given nor owns appears
# ANYWHERE else in the prompt. dod_quoted_warn/manifest_quoted_warn
# both stay silent in that case (nothing to flag -- no marker match
# exists at all). This layer signals the flip itself, so it is never a
# silent pass: the bare (pre-region) file would have blocked this same
# dispatch.
WRITE_QUOTED_WARN_MESSAGE = (
    "WRITE-QUOTED WARN: the only write signal found in this dispatch "
    "(a write verb / owns-declaration) sits inside a quote/fence -- the "
    "region filter lifted check 2's block, and no given/owns manifest "
    "marker appears anywhere in the text either -- this is not a silent "
    "pass: a bare-regex gate would have blocked this same dispatch -- "
    "verify by hand (dispatch-context-manifest rule)."
)


def write_quoted_warn(payload: dict) -> str:
    """"" -- nothing to warn about (not Task/Agent, not builder, prompt
    absent/empty, the bare write signal was never True -- no flip is
    even possible, ANY manifest marker (given OR owns) is present
    somewhere -- that case is already flagged by manifest_quoted_warn,
    silent here to avoid a duplicate message, the region-aware write
    signal stayed True -- no flip happened). Otherwise -- the bare
    write signal was True, the region-aware one became False, and no
    manifest marker exists at all -- the region filter silently lifted
    the block; this layer signals the flip itself."""
    try:
        if not isinstance(payload, dict):
            return ""
        if payload.get("tool_name") not in ("Task", "Agent"):
            return ""
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return ""
        if tool_input.get("subagent_type") != "builder":
            return ""
        prompt = tool_input.get("prompt")
        if not isinstance(prompt, str) or not prompt:
            return ""
        bare_is_write = bool(WRITE_INDICATORS_RE.search(prompt)) or owns_declaration_has_path_token(
            prompt
        )
        if not bare_is_write:
            return ""
        if MANIFEST_GIVEN_RE.search(prompt) or MANIFEST_OWNS_RE.search(prompt):
            return ""  # a manifest marker exists -- covered by manifest_quoted_warn
        if _region_aware_is_write(prompt):
            return ""  # no flip -- the region-aware signal is also True
        return WRITE_QUOTED_WARN_MESSAGE
    except Exception:
        return ""


# =======================================================================
# FRESHNESS layer (route port; staff twin's own FRESHNESS node):
# one of the staff twin's two anchor classes is ported -- class (v),
# "a <path>.<ext>:N[-M] anchor points past the end of the real file".
# The staff twin's OTHER class, "check NN(x) references a nonexistent
# calibration-protocol subpoint", is NOT ported this increment: it
# depends on a `<!--CHK NN|-->` machine-anchor convention inside
# WEEKLY_CALIBRATION_PROTOCOL.md that the kit's OWN copy does not carry
# yet (measured: 0 occurrences of "CHK" in
# toolkit/PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md vs. 64 in the staff
# twin) -- adopting that anchor convention is a decision for node C4
# (which owns that file), not this node; porting the check-number class
# now would be machinery for a convention the kit has not adopted. This
# is an honest population narrowing (see the module docstring, "Region-
# aware filtering"), not a silent invention: the layer still degrades
# correctly on a tree with no staff-shaped carriers (class (v) itself
# needs nothing but a path and a line count).
#
# decide() is NOT touched by this layer at all. Region-aware via the
# SAME _safe_scan()/_is_quoted() pair as the layers above -- but with
# NO bare-regex I-0 fallback: with no region info at all, the whole
# layer stays silent (a cheap "any candidate at all" prefilter runs
# BEFORE the filesystem or the scanner are ever touched).
# =======================================================================

FRESHNESS_WARN_PREFIX = "FRESHNESS WARN:"

_FRESHNESS_PATH_BODY_CHAR = r'[^\s"\'<>|?*{}$,;\n]'

FRESHNESS_LINE_ANCHOR_RE = re.compile(
    r"(?<![\w/\\])(?P<path>"
    + _GIVEN_REPO_REL_PREFIX
    + r"/"
    + _FRESHNESS_PATH_BODY_CHAR
    + r"{0,300}\.[A-Za-z0-9]{1,10})"
    + r":(?P<n>\d{1,7})(?:-(?P<m>\d{1,7}))?\b"
)

FRESHNESS_LINE_ANCHOR_ABS_RE = re.compile(
    r"(?<!\w)(?P<path>[A-Za-z]:[\\/]"
    + _FRESHNESS_PATH_BODY_CHAR
    + r"{0,300}\.[A-Za-z0-9]{1,10})"
    + r":(?P<n>\d{1,7})(?:-(?P<m>\d{1,7}))?\b"
)

_FRESHNESS_SUMMARY_THRESHOLD = 20
_FRESHNESS_MAX_FILE_BYTES = 2 * 1024 * 1024
_FRESHNESS_MAX_FILES_PER_CALL = 8
_FRESHNESS_MAX_PROMPT_CHARS = 300_000


def _freshness_m3_message(token_display: str, line_count: int, bound: int) -> str:
    return (
        f"{FRESHNESS_WARN_PREFIX} anchor {token_display} points past the "
        f"end of the file (it has {line_count} lines) -- the line moved "
        f"or was removed, acceptance will open the wrong place and sign "
        f"off on the wrong content -- re-read the carrier, update the "
        f"line number, or drop it and keep the path."
    )


def _freshness_line_anchor_candidates_region_aware(prompt: str, scan_result) -> list:
    """(path, is_abs, n, m) for anchors with >=1 occurrence OUTSIDE a
    quote -- dedup by (normcase(path), n, m), same polarity/shape as
    extract_given_candidates_region_aware."""
    order = []
    seen = {}
    for pattern, is_abs in (
        (FRESHNESS_LINE_ANCHOR_ABS_RE, True),
        (FRESHNESS_LINE_ANCHOR_RE, False),
    ):
        for m in pattern.finditer(prompt):
            path = m.group("path")
            n = int(m.group("n"))
            m_raw = m.group("m")
            mm = int(m_raw) if m_raw is not None else None
            key = (os.path.normcase(path), n, mm)
            quoted = _is_quoted(_region_at(scan_result, m.start()))
            if key not in seen:
                seen[key] = {
                    "path": path, "is_abs": is_abs, "n": n, "m": mm,
                    "any_unquoted": not quoted,
                }
                order.append(key)
            elif not quoted:
                seen[key]["any_unquoted"] = True
    return [seen[k] for k in order if seen[k]["any_unquoted"]]


def _freshness_class_v_hits(prompt: str, scan_result, repo_root: str) -> list:
    """WARN only when the file exists, is readable, and its line count
    is below max(N, M). _FRESHNESS_MAX_FILE_BYTES / _FRESHNESS_MAX_FILES_
    PER_CALL bound per-call cost; files over the per-call budget are
    silently skipped (never mentioned as "unchecked"). line_count is
    computed EXACTLY once per file within a call -- repeat anchors on
    the same file (different N/M) reuse the cached line count."""
    candidates = _freshness_line_anchor_candidates_region_aware(prompt, scan_result)
    if not candidates:
        return []
    checked_files: set = set()
    line_count_cache: dict = {}
    hits = []
    for cand in candidates:
        path, is_abs, n, m = cand["path"], cand["is_abs"], cand["n"], cand["m"]
        if is_abs:
            if not _is_under_root(path, repo_root):
                continue
            full_path = path
        else:
            full_path = os.path.join(repo_root, path)
        file_key = os.path.normcase(os.path.normpath(full_path))

        if file_key in line_count_cache:
            line_count = line_count_cache[file_key]
        else:
            if not os.path.isfile(full_path):
                continue  # silent: does not exist / is a directory
            if file_key not in checked_files:
                if len(checked_files) >= _FRESHNESS_MAX_FILES_PER_CALL:
                    continue  # per-call file budget
                checked_files.add(file_key)
            try:
                if os.path.getsize(full_path) > _FRESHNESS_MAX_FILE_BYTES:
                    continue  # per-file size budget
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            line_count = len(text.splitlines())
            line_count_cache[file_key] = line_count

        bound = max(n, m) if m is not None else n
        if line_count < bound:
            token_display = f"{path}:{n}" + (f"-{m}" if m is not None else "")
            hits.append((token_display, line_count, bound))
    return hits


def _freshness_format_class_v(hits: list) -> str:
    if not hits:
        return ""
    if len(hits) <= _FRESHNESS_SUMMARY_THRESHOLD:
        return "\n\n".join(_freshness_m3_message(*h) for h in hits)
    head = ", ".join(h[0] for h in hits[:3])
    return (
        f"{FRESHNESS_WARN_PREFIX} {len(hits)} file:line anchors point past "
        f"the end of their carrier -- lines moved or were removed, "
        f"acceptance will open the wrong place; first 3: {head} -- "
        f"re-read the carriers, update the line numbers, or drop them "
        f"and keep the paths."
    )


def freshness_warn(payload: dict) -> str:
    """"" -- nothing to warn about; pure, never raises outward. Not
    Task/Agent -- silent without touching the filesystem. No anchor
    candidate at all -> "" BEFORE the filesystem/scanner. Region
    scanner unavailable -> the layer stays silent ENTIRELY (no bare-
    regex I-0 fallback here, unlike given_path_warn -- see the module
    docstring)."""
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
    if len(prompt) > _FRESHNESS_MAX_PROMPT_CHARS:
        return ""  # stays silent without reading the disk

    has_v = bool(FRESHNESS_LINE_ANCHOR_ABS_RE.search(prompt)) or bool(
        FRESHNESS_LINE_ANCHOR_RE.search(prompt)
    )
    if not has_v:
        return ""

    scan_result = _safe_scan(prompt)
    if scan_result is None:
        return ""  # no region info -- the whole layer stays silent

    repo_root = payload.get("cwd")
    if not isinstance(repo_root, str) or not repo_root:
        repo_root = os.getcwd()

    return _freshness_format_class_v(
        _freshness_class_v_hits(prompt, scan_result, repo_root)
    )


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


# --- stdin deadline (P4 class; a LOCAL copy, no shared module -- the
# same helper toolkit/tools/owns_gate.py/session_context.py already
# carry)
# --------------------------------------------------------------------

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
    """Returns (bytes, timed_out). Reads stdin to EOF, but no longer
    than the deadline. Cross-platform by construction: select/poll do
    not work on pipes on Windows, so a background daemon thread does
    the actual blocking read and the deadline is enforced via
    thread.join(timeout). A TTY returns b"" without reading anything.
    Any read error degrades to b"" (fail-open)."""
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

# A background reader thread may still be blocked deep in a platform
# read syscall at normal interpreter shutdown, which can crash the
# process ("Fatal Python error: _enter_buffered_busy") instead of
# exiting cleanly. main() itself is UNCHANGED (still a plain
# `return 0`/`return 2`, safe in-process); only the actual __main__
# script-exit path below escalates to os._exit().
_STDIN_DEADLINE_STATE = {"hit": False}


def main() -> int:
    _reconfigure_stderr_utf8()

    # Byte-safe read via the stdin-deadline helper (replaces a former
    # direct, unbounded sys.stdin.buffer.read()) -- same decode utf-8/
    # errors="replace" fail-open contract, now bounded by
    # OSLLM_STDIN_TIMEOUT instead of blocking forever with no EOF.
    raw_bytes, timed_out = _read_stdin_bytes_deadline()
    if timed_out:
        _STDIN_DEADLINE_STATE["hit"] = True
        sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
        return 0
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

    # Every WARN layer below is considered only when the gate itself did
    # NOT block (see the module docstrings, "Given-path WARN layer" /
    # "Role-type WARN layer" / "Region-aware filtering" / "FRESHNESS
    # layer"); try/except on EACH is belt-and-suspenders -- no layer
    # must ever crash the blocking hook with a traceback. Fixed order:
    # given-path, role-type (unchanged), then the new region-aware
    # layers in the tail, write-quoted last among those (the newest),
    # freshness at the very end.
    try:
        warn_given = given_path_warn(payload)
    except Exception:
        warn_given = ""
    try:
        warn_role = role_type_warn(payload)
    except Exception:
        warn_role = ""
    try:
        warn_dod_quoted = dod_quoted_warn(payload)
    except Exception:
        warn_dod_quoted = ""
    try:
        warn_manifest_quoted = manifest_quoted_warn(payload)
    except Exception:
        warn_manifest_quoted = ""
    try:
        warn_write_quoted = write_quoted_warn(payload)
    except Exception:
        warn_write_quoted = ""
    try:
        warn_freshness = freshness_warn(payload)
    except Exception:
        warn_freshness = ""

    warn_parts = [
        w
        for w in (
            warn_given,
            warn_role,
            warn_dod_quoted,
            warn_manifest_quoted,
            warn_write_quoted,
            warn_freshness,
        )
        if w
    ]
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
    _rc = main()
    if _STDIN_DEADLINE_STATE["hit"]:
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
