r"""owns_gate.py -- a Claude Code PreToolUse hook on Task/Agent, WARN-ONLY
(measure first, decide whether to block later). Mechanizes a machine
check that a NEW writing dispatch's owns paths don't collide with the
owns paths of currently LIVE dispatches -- one layer of protection
against parallel-dispatch collisions (CLAUDE.md rule 4: "parallel
specs declare path ownership; the Lead checks overlap before
launching" -- a manual check decays with the coordinator's memory,
this is a machine backstop on top of it, not a replacement for it).

Why NOT logs/routing-log.jsonl: `delegated` events are written AFTER
the dispatch call returns and are legitimately BATCHED to a stage
boundary (rule 12 -- "events accumulate and are written as a batch at
the stage boundary"). That means the journal lags exactly in the
window where two simultaneous dispatches collide: if the coordinator
dispatches two writing tasks back to back with no journal write in
between, the second dispatch goes out BEFORE the first ever appears in
routing-log -- a journal-based check would see nothing. PreToolUse is
the one point where code is guaranteed to meet EVERY dispatch before
it starts -- so the carrier for live owns state is a SEPARATE sidecar,
logs/owns_registry.jsonl (append-only, one JSON line per writing
dispatch), not the routing journal.

Payload contract: the same one tools/dispatch_gate.py already uses
(payload["tool_name"] in {"Task", "Agent"}, tool_input.prompt /
tool_input.description, payload["cwd"]).

--- Extracting owns paths from the prompt (extract_owns_paths) ------
 1. Owns MARKER. This kit's tools/dispatch_gate.py already exports a
    single, WORD-BOUNDED owns marker (MANIFEST_OWNS_RE = r"\bowns\b",
    case-insensitive) -- this file imports it rather than keeping a
    local copy (shared point of truth: dispatch_gate.py's own check 2
    and this file's extraction must never drift apart). ADAPTATION
    FROM THE PORTED SOURCE: the source deployment's dispatch_gate.py
    carries TWO owns regexes -- a word-bounded primary one and a
    separate, bare (unbounded) fallback used ONLY when no line in the
    prompt matches the bounded form at all (tolerance for a mangled
    prompt where "owns" appears only as a substring of another word).
    This kit's dispatch_gate.py does not carry that second, unbounded
    regex (MANIFEST_OWNS_RE here is ALREADY the bounded form) -- there
    is nothing to fall back to, so this port runs a SINGLE pass over
    MANIFEST_OWNS_RE and has no substring-fallback pass. A prompt whose
    only mention of "owns" is embedded inside another word (e.g. a
    filename) is treated the same as a prompt with no owns marker at
    all: extract_owns_paths returns [] with no diagnostic. This is a
    conscious behavioral narrowing, not a partial port -- see the
    handoff report for the exact discrepancy this creates against the
    ported source.
 2. EVERY line of the prompt carrying the marker is tried in order
    (not just the first): for each such line, the text after the
    marker match has its "declaration junk" trimmed
    (_strip_owns_marker_junk) -- an optional parenthetical
    clarification `\([^)]*\)` (covers `owns (ABSOLUTE write paths):`)
    and leading punctuation `[\s*:\-\u2014\u00ab\u00bb"']` (covers
    markdown `**owns**:` and a plain `owns:`), iteratively, until the
    remainder stabilizes. What's left is tokenized
    (split_and_clean_tokens) and filtered by is_path_token. The owns
    declaration LINE is the FIRST line that yields >=1 valid path
    token -- a marker line with no path (prose) is silently skipped
    and the scan continues.

--- Line selection is declaration-aware, not "any line with the word"
The scan above only tries the MULTI-LINE continuation form (see below)
when the marker's OWN line is itself a genuine owns DECLARATION, not
prose that merely happens to contain the word "owns" ("don't go beyond
the owns of this task" is prose, not a declaration). A line qualifies
as a declaration line (_is_owns_declaration_line) when: (a) everything
BEFORE the marker match is only whitespace + an optional bullet
(`- `/`* `/`\u2022 `) + optional markdown `**`; (b) everything AFTER
the marker match, once junk-trimmed, is EMPTY. Both conditions are
required together -- a line that already yielded a path on its own
never reaches this check at all (the marker line's own paths win
first, unconditionally).

--- Known extraction limits (documented, not fixed; both pinned) ----
 - A LEADING GLOB STAR IS EATEN BY THE STRIPPER: `*` is one of the
   junk leading characters (_JUNK_PREFIX_RE, there for markdown
   `**owns**:`), so extract_owns_paths("owns: */tools/*") yields
   ["/tools/*"], not ["*/tools/*"] -- the leading star is lost. Known,
   not fixed: a glob with a leading star is not an absolute path and
   so falls outside this kit's rule 11 norm ("owns (ABSOLUTE write
   paths)") anyway; the cost is a coarser check on a non-canonical
   form, WARN-only.
 - _strip_owns_marker_junk IS QUADRATIC IN THE NUMBER OF JUNK
   PARENTHETICAL GROUPS: each loop iteration strips ONE `([^)]*)`
   group via a slice-copy of the remainder, so cost is roughly O(n^2)
   in the number of groups. Immaterial at any realistic prompt size; a
   pathological input degrades in time but never crashes the hook
   (main() always returns exit 0) -- not preemptively optimized, the
   price of simplicity in a WARN-only tool.
 3. The remainder is split on `;`, `,`, newline (_TOKEN_SEPARATOR_RE).
    Each raw token, before edge-trimming, has its prose tail cut at
    the FIRST "space-emdash-space" sequence (_PROSE_TAIL_SEP = " \u2014
    ") -- covers "D:/a.py \u2014 a new file": the tail "\u2014 a new
    file" is dropped, the path survives. Deliberately NOT split on a
    bare space -- a legal path containing spaces must survive whole.
 4. After the tail cut, each token is edge-trimmed: whitespace, then
    LEADING quotes/brackets/guillemets (_EDGE_TRIM_CHARS), then
    TRAILING quotes/brackets/guillemets/sentence-ending dot
    (_TRAILING_TRIM_CHARS) -- iteratively (see _clean_token).
 5. Only tokens that LOOK LIKE A PATH survive: a Windows absolute path
    (drive letter, `:`, slash), a POSIX absolute path (leading `/`,
    covers a git-bash `/d/...` form), or a glob carrying BOTH `*` and
    a slash -- is_path_token(), a thin wrapper over
    dispatch_gate.is_path_like_token() (the single shared predicate --
    see dispatch_gate.py's own docstring). RELATIVE paths are NOT
    recognized as paths -- not an oversight: this kit's rule 11
    explicitly requires "owns (ABSOLUTE write paths)".
 No owns marker on any line -- a read-only dispatch, extract_owns_paths
 returns [] -- decide() writes nothing to the sidecar and exits quietly
 (0, None).

--- Diagnosing an empty owns ("silence -> noise") --------------------
If extract_owns_paths returned [] (no line yielded any path) BUT the
prompt carries an owns marker (MANIFEST_OWNS_RE) AND a write indicator
(WRITE_INDICATORS_RE, imported from dispatch_gate.py -- the same
shared point of truth) -- decide() returns an additionalContext WARN
("an owns marker is present but no paths could be parsed out of it --
the overlap check is blind on this dispatch; check the owns line's
form", see BLIND_OWNS_WARN_MESSAGE) and does NOT write to the sidecar
(a check that's known to be blind gains nothing from registering an
empty/meaningless owns set). A genuinely read-only dispatch (no marker
at all, OR an owns marker with no OTHER write verb present -- see
WRITE_INDICATORS_RE in dispatch_gate.py, which no longer carries a
bare "owns" alternative) stays silent, same as before.

--- Registration does not depend on WRITE_INDICATORS_RE -------------
The MAIN sidecar-registration path (decide() -> extract_owns_paths())
does NOT consult WRITE_INDICATORS_RE at all -- it is unconditional on
"is this dispatch writing": the decision rests entirely on whether
REAL path tokens were found in an owns declaration. This is a
deliberate architectural choice: manifest correctness must not depend
on whether one of the four write verbs happens to appear elsewhere in
the prompt -- an owns declaration with real paths must register and be
checked regardless of the surrounding prose (same "code guarantees the
encounter" logic as the "Why NOT logs/routing-log.jsonl" section
above). The ONLY place this file consults WRITE_INDICATORS_RE at all
is the diagnostic branch above (owns declared, no paths parsed).

--- Multi-line owns block --------------------------------------------
The canonical form ("paths on the marker's own line") remains the
priority; the parser EXTENDS it: if an owns marker is found on a line
(word-bounded) but _paths_from_line() for THAT line returns [] (no
valid paths on the line itself), extract_owns_paths() tries
_paths_from_continuation() -- reads the FOLLOWING prompt lines as a
continuation of the block, until the first line that doesn't parse as
a path (a bulleted list `- path` / `* path` / `\u2022 path`, a
numbered list `1. path` / `2) path`, and/or bare path lines; each line
is tokenized/filtered by the same is_path_token machinery as the
single-line form). Paths found are returned IMMEDIATELY -- neither the
marker line itself nor the rest of the prompt is scanned further (the
same "first line that yields a path wins" rule as the single-line
case).

MARKER-LINE PRIORITY (mandatory): if the marker's OWN line already
yielded >=1 valid path, _paths_from_continuation() is never called at
all -- a block below, even if present, is never merged into the marker
line's own paths (an owns line + a list below it as an ADDITION, not
an alternative, would silently change already-accepted dispatches'
semantics -- not done here).

Stop conditions for the continuation block (_paths_from_continuation,
all three end the block, they don't "skip and continue"):
 1. A blank line (line.strip() == "") -- including immediately after
    the marker (a zero-length block -> []).
 2. A new manifest section header -- given/\u0434\u0430\u043d\u043e,
    owns, non-goals, handoff (_SECTION_HEADER_STOP_RE; a CLOSED set of
    manifest sections from this kit's rule 11 -- not an open guess) at
    the start of the line (after an optional markdown `**`) -- its
    content never joins owns, even if it formally contains something
    path-like (e.g. `non-goals: toolkit/**` contains `*`, which by
    itself would match is_path_token -- the section stop is checked
    FIRST, before tokenizing the line).
 3. The first line that yields NO path-like token at all, after
    stripping an optional bullet prefix (`- `/`* `/`\u2022 `) and the
    same junk-trimming the single-line form uses
    (_strip_owns_marker_junk + split_and_clean_tokens + is_path_token).

CONTINUATION-LINE LIMIT (protection against parsing the whole prompt,
boundary-tested BOTH sides): exactly 40 valid continuation lines,
naturally ended by a stop condition on line 41 (or the prompt's end) --
the 40 collected paths are returned as-is. If the block would STILL be
continuing at line 41 (that line too would yield >=1 path token) -- the
limit is hit: [] is returned (the same "blind owns" diagnostic then
fires through decide()), NOT a silent truncation to the first 40 --
a silently truncated owns set would be WORSE than explicit blindness
(the same principle behind the rest of this WARN-only tool: a silent
partial check is more dangerous than an explicitly flagged empty one).

--- "Declaration, not prose" gate: a regression this port pins ------
A marker line qualifies for continuation ONLY when it is itself a
genuine declaration, not ordinary prose that happens to contain the
standalone word "owns" (e.g. "don't go beyond the owns of this task.
D:/repo/readme.md -- read before starting\n\nowns: D:/repo/
real_target.py" -- the prose line must NOT hijack the real `owns:`
declaration two lines below it, stealing "D:/repo/readme.md" as if it
were the continuation's first path and never reaching the real
declaration). _is_owns_declaration_line() and the strict
_is_continuation_path_token() (requiring a real absolute path or a
`*`+slash glob, not a bare "any token with a `*`" match) both exist
specifically to prevent this -- ported here as the default behavior
(not a fix applied ON TOP of a simpler version, since this is a new
file in this kit).

--- Fenced code blocks: an explicit non-goal --------------------------
A marker/paths INSIDE a triple-backtick fenced block get no special
handling -- the fence delimiter lines are not path-like themselves, so
a continuation block simply stops on them with an empty result (the
same safe default -- "an empty check beats a wrong one" -- as the rest
of this WARN-only tool). A general markdown-region module (fenced /
inline / blockquote) that would distinguish "marker inside an example"
from "marker as a real declaration" is deliberately not built here.

--- Sidecar -------------------------------------------------------
logs/owns_registry.jsonl, relative to payload["cwd"] (the same
convention tools/dod_track.py already uses for its own track).
Append-only (except for compaction, below), one JSON line per WRITING
dispatch (read-only dispatches AND dispatches with an unparseable owns
-- see "Diagnosing an empty owns" -- produce no record):
  {"ts": "YYYY-MM-DDTHH:MM:SS" (local time, no timezone),
   "session_key": str,
   "cwd": str or None,
   "description": str (tool_input.description or ""),
   "owns": [str, ...]}
A missing file / a malformed JSON line inside it -- fail-open (the
line is silently skipped, the rest read normally; a missing file is an
empty list of live records).

ORDER: a new dispatch is checked against already-existing live records
FIRST, and only THEN (after the check, regardless of its outcome)
appended to the sidecar itself -- self-overlap of a dispatch with its
own record is structurally excluded by this order.

--- Shared code with tools/owns_verify.py -----------------------------
normalize_path/paths_overlap/split_and_clean_tokens are defined HERE
(owns_gate.py) and imported by owns_verify.py -- owns_gate.py is the
active PreToolUse hook (registered by the harness, must be able to run
standalone with no CLI scaffolding), while owns_verify.py is a plain
CLI, for which an extra dependency on owns_gate.py's own module
carries no reverse-direction problem.

--- Known sidecar limitations (a documented list, not preemptively
fixed) -------------------------------------------------------------
 - WARN-FIRST ACCURACY: the sidecar does not know when a worker
   FINISHES -- a record lives in the 24h window regardless of whether
   the dispatch has already completed; a WARN on an already-fully-
   completed dispatch is possible. Judging actual liveness is left to
   the coordinator.
 - CONCURRENT APPEND FROM TWO SESSIONS: two processes can write to the
   sidecar at once; on most OSes `open(..., "a")` is atomic for a
   short line, but not guaranteed -- a torn (interleaved) line is
   possible in the limit. The reading side (_load_live_records)
   fail-open skips such a line as malformed JSON -- acceptable for a
   WARN-ONLY tool (a missed WARN is cheaper than a crashed hook).
 - COMPACTION AS A LOSS POINT: compaction (below) rewrites the file
   whole -- if a SECOND process appends a line BETWEEN this process's
   read of the existing lines and its final rewrite, that line is lost
   (the rewrite never saw it). A rare case (requires compaction to
   coincide with a concurrent write in a narrow window), accepted as
   the price of simplicity for a WARN-only tool, not preemptively
   fixed.

FAIL-OPEN: payload not a dict / tool_name not Task|Agent / tool_input
not a dict / prompt not a string / no owns block found -- all of these
return (0, None), no side effects. main() wraps decide() in one more
try/except (belt-and-suspenders, the same principle as this tool set's
other WARN layers) -- an adversarial input (malformed JSON, non-UTF-8
bytes, a payload that isn't a dict, a huge owns string) must not crash
the hook with a traceback; the exit code is ALWAYS 0 (WARN mode -- this
layer never blocks)."""

import fnmatch
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

# A DIRECT sibling-module import only -- NOT a "try tools.dispatch_gate
# package-style, fall back to a sibling import" pattern. This kit's
# install tree lives inside a larger repository that ALSO carries its
# own top-level tools/ directory with a DIFFERENTLY BEHAVING
# dispatch_gate.py; a bare `import tools.dispatch_gate` can resolve
# "tools" as an implicit namespace package rooted at the CURRENT
# WORKING DIRECTORY (PEP 420 -- no __init__.py required) rather than
# at this file's own directory, silently picking up the WRONG module
# whenever the working directory happens to be that repo's root. The
# sys.path insertion above already guarantees a sibling `import
# dispatch_gate` resolves to THIS directory's own module unambiguously
# -- no package-style guess is needed or safe here.
from dispatch_gate import (
    MANIFEST_OWNS_RE,
    WRITE_INDICATORS_RE,
    is_path_like_token,
)


# --- extracting owns paths from the prompt ----------------------------
# The word-bounded owns marker (MANIFEST_OWNS_RE = r"\bowns\b") is
# imported from tools/dispatch_gate.py rather than kept as a local
# copy -- a single shared point of truth between the blocking check
# (dispatch_gate.py's check 2) and this file's extraction. See the
# module docstring, "Owns MARKER", for why this port carries no
# separate unbounded fallback regex.

_PAREN_PREFIX_RE = re.compile(r"^\s*\([^)]*\)")
_JUNK_PREFIX_RE = re.compile(r"^[\s*:\-\u2014\u00ab\u00bb\"']+")
_TOKEN_SEPARATOR_RE = re.compile(r"[;,\n]")
_PROSE_TAIL_SEP = " \u2014 "  # space-emdash-space -- see the module docstring, point 3.

# Backtick "`" is included -- the same class of markdown decoration
# that quotes/guillemets already strip here.
_EDGE_TRIM_CHARS = "\"'`()[]{}\u00ab\u00bb\u201e\u201c\u201d"
# Trailing sentence-ending punctuation (`.`) -- this kit's real
# manifests write an owns bullet as a complete sentence, so ONLY the
# trailing dot (rstrip, not lstrip -- a leading dot is protected, in
# case of a hypothetical relative dot-path) joins the trimmed set, on
# top of quotes/brackets/guillemets.
_TRAILING_TRIM_CHARS = _EDGE_TRIM_CHARS + "."

_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")
_POSIX_ABS_RE = re.compile(r"^/")

# Multi-line owns block.
_BULLET_PREFIX_RE = re.compile(r"^\s*[-*\u2022]\s+")
# A numbered list ("1. path" / "2) path") is also recognized as a
# bullet-continuation form.
_NUMBERED_PREFIX_RE = re.compile(r"^\s*\d+[.)]\s+")
# A closed set of manifest sections (this kit's rule 11): given/
# \u0434\u0430\u043d\u043e, owns, non-goals, handoff -- an optional
# markdown `**` before the word.
_SECTION_HEADER_STOP_RE = re.compile(
    r"^\s*(?:\*\*)?(given|\u0434\u0430\u043d\u043e|owns|non-goals|handoff)\b", re.IGNORECASE
)
# Everything BEFORE the start of the owns-marker match must be only
# whitespace + an optional bullet + optional markdown `**` -- otherwise
# the marker's line is not a declaration, but prose that merely
# contains the word "owns" (see the module docstring, "Declaration, not
# prose").
_DECLARATION_PREFIX_RE = re.compile(r"^\s*(?:[-*\u2022]\s+)?(?:\*\*)?$")
CONTINUATION_LINE_LIMIT = 40


def _strip_owns_marker_junk(remainder: str) -> str:
    """Iteratively strips, from the START of remainder, an optional
    parenthetical clarification `\\([^)]*\\)` and leading characters of
    the class `[\\s*:\\-\\u2014\\u00ab\\u00bb"']` -- IN EITHER ORDER (the
    parenthetical may come before or after the colon; markdown
    `**owns**:` puts stars before the colon) -- until the string
    stabilizes. Both patterns always consume >=1 character on a match,
    so remainder strictly shortens on every successful iteration --
    termination is guaranteed with no separate iteration counter."""
    prev = None
    while remainder != prev:
        prev = remainder
        m = _PAREN_PREFIX_RE.match(remainder)
        if m:
            remainder = remainder[m.end():]
            continue
        m2 = _JUNK_PREFIX_RE.match(remainder)
        if m2:
            remainder = remainder[m2.end():]
            continue
    return remainder


def _cut_prose_tail(raw: str) -> str:
    """Cuts a token's tail at the FIRST "space-emdash-space" sequence
    (_PROSE_TAIL_SEP) -- see the module docstring, point 3. Does NOT
    split on a bare space -- a path containing spaces (e.g.
    "D:/AI CRM/x/AGENTS.md") stays whole."""
    if not raw:
        return raw
    idx = raw.find(_PROSE_TAIL_SEP)
    if idx == -1:
        return raw
    return raw[:idx]


def _clean_token(raw: str) -> str:
    """Strips whitespace, then LEADING quotes/brackets/guillemets
    (_EDGE_TRIM_CHARS) and TRAILING quotes/brackets/guillemets/dot
    (_TRAILING_TRIM_CHARS) -- ITERATIVELY (until stable), so nested
    combinations like "(logs/owns_registry.jsonl)." (a bracket then a
    sentence-ending dot) collapse to a clean path in one loop, not a
    single strip() call."""
    tok = raw.strip()
    prev = None
    while tok != prev:
        prev = tok
        tok = tok.lstrip(_EDGE_TRIM_CHARS)
        tok = tok.rstrip(_TRAILING_TRIM_CHARS)
        tok = tok.strip()
    return tok


def split_and_clean_tokens(text: str) -> list:
    """Splits text on `;`/`,`/newline, cuts each raw token's prose tail
    (_cut_prose_tail) and edge-trims whitespace/quotes/brackets/
    guillemets (+ a trailing dot, see _clean_token). A shared function
    -- see the module docstring, "Shared code with
    tools/owns_verify.py"."""
    if not isinstance(text, str) or not text:
        return []
    cleaned = []
    for raw in _TOKEN_SEPARATOR_RE.split(text):
        raw = _cut_prose_tail(raw)
        tok = _clean_token(raw)
        if tok:
            cleaned.append(tok)
    return cleaned


# A thin wrapper over dispatch_gate.is_path_like_token() -- a single
# shared point of truth, not a local copy. The name is_path_token is
# kept for readability at this file's call sites; behavior is
# identical to is_path_like_token.
def is_path_token(tok: str) -> bool:
    """Windows-absolute / POSIX-absolute / a glob with BOTH `*` and a
    slash -- see the module docstring, point 5, "Extracting owns paths
    from the prompt". Delegates to dispatch_gate.is_path_like_token()
    -- not independent logic."""
    return is_path_like_token(tok)


BLIND_OWNS_WARN_MESSAGE = (
    "an owns marker is present but no paths could be parsed out of it "
    "-- the overlap check is blind on this dispatch; check the owns line's form"
)


def _paths_from_line(line: str, marker_end: int) -> list:
    """The shared tail of the extraction pass: junk is trimmed from the
    end of the marker match (_strip_owns_marker_junk), the remainder is
    tokenized and filtered by is_path_token -- see the module
    docstring, points 2-5."""
    remainder = _strip_owns_marker_junk(line[marker_end:])
    tokens = split_and_clean_tokens(remainder)
    return [t for t in tokens if is_path_token(t)]


def _is_owns_declaration_line(line: str, marker_start: int, marker_end: int) -> bool:
    """True only when the marker's own line is itself an owns
    DECLARATION, not prose that merely contains the word "owns" inside
    a sentence -- see the module docstring, "Declaration, not prose",
    for the full rationale. Called ONLY when _paths_from_line() has
    already returned [] for this line (the line itself yielded no
    paths) -- decides whether trying a continuation below is worth it,
    or whether this line should be skipped entirely (prose must not
    hijack a real declaration that may be further down)."""
    prefix = line[:marker_start]
    if not _DECLARATION_PREFIX_RE.match(prefix):
        return False
    remainder_after_junk = _strip_owns_marker_junk(line[marker_end:])
    return remainder_after_junk.strip() == ""


# This check already requires "*" AND a slash together -- the same
# strictness dispatch_gate.is_path_like_token() applies as the shared
# point of truth (is_path_token() above simply matches it). Delegating
# removes duplication between two otherwise-identical implementations
# -- the name is kept for readability at this file's call sites.
def _is_continuation_path_token(tok: str) -> bool:
    """A continuation-block token must be a Windows/POSIX absolute path
    OR a glob carrying BOTH "*" and a slash -- see the module
    docstring, "A regression this port pins". Delegates to
    dispatch_gate.is_path_like_token()."""
    return is_path_like_token(tok)


# Open-to-close quote pairs: _first_raw_token looks for a matching
# closing character instead of splitting on the first space, so a
# continuation-line path WITH spaces inside quotes survives whole --
# the single-line form already tolerates spaces inside a path (it
# never splits on a bare space at all, see the module docstring,
# "Extracting owns paths", points 3-4), but a continuation line's ONLY
# token separator is whitespace, so an explicit quote/backtick/
# guillemet delimiter is needed here.
_QUOTE_OPEN_TO_CLOSE = {"\"": "\"", "'": "'", "`": "`", "\u00ab": "\u00bb"}


def _first_raw_token(body: str) -> str:
    """The raw (untrimmed) first token of body -- NORMALLY the first
    whitespace-delimited token (body.split(None, 1)[0]), BUT if body
    starts with an opening character from _QUOTE_OPEN_TO_CLOSE, the
    matching closing character is searched for further in the line --
    if found, everything between them (inclusive) is returned
    (quotes/backtick are stripped later by _clean_token, already
    included in _EDGE_TRIM_CHARS) -- spaces INSIDE are preserved. No
    closing character found -- falls back to a plain space split (does
    not regress behavior on an unclosed quote)."""
    if body and body[0] in _QUOTE_OPEN_TO_CLOSE:
        close_char = _QUOTE_OPEN_TO_CLOSE[body[0]]
        close_idx = body.find(close_char, 1)
        if close_idx != -1:
            return body[: close_idx + 1]
    return body.split(None, 1)[0]


def _first_token_path(line: str):
    """The FIRST token of a continuation line (after stripping a bullet
    `- `/`* `/`\u2022 ` OR a list number `1.`/`2)`), if it is valid per
    _is_continuation_path_token -- any prose tail after the first token
    is IGNORED entirely (it is not glued to the path through a missing
    comma separator). "First token" is found via _first_raw_token --
    normally the first whitespace-delimited one, but if the token opens
    with a quote/backtick/guillemet, everything up to the matching
    close is taken (spaces inside quotes no longer split the path in
    two). None -- the line does not parse as a continuation path (end
    of the block)."""
    body = _BULLET_PREFIX_RE.sub("", line, count=1)
    body = _NUMBERED_PREFIX_RE.sub("", body, count=1)
    body = body.strip()
    if not body:
        return None
    first_raw = _first_raw_token(body)
    tok = _clean_token(first_raw)
    if tok and _is_continuation_path_token(tok):
        return tok
    return None


def _paths_from_continuation(lines: list, start_idx: int) -> list:
    """Reads lines[start_idx:] as a continuation of the owns block --
    see the module docstring, "Multi-line owns block", for the full
    rationale of the stop conditions and the limit. [] on: a blank
    first line, a new manifest section line, the first line with no
    path token (_first_token_path), OR hitting
    CONTINUATION_LINE_LIMIT with the block still going. Each block line
    yields EXACTLY one path (its first valid token) -- see the module
    docstring, "A regression this port pins", point 2."""
    collected = []
    idx = start_idx
    n = len(lines)
    lines_consumed = 0
    while idx < n:
        line = lines[idx]
        if line.strip() == "":
            break
        if _SECTION_HEADER_STOP_RE.match(line):
            break
        path = _first_token_path(line)
        if path is None:
            break
        if lines_consumed >= CONTINUATION_LINE_LIMIT:
            # The limit is REACHED and the block would still be
            # continuing (this line is valid too) -- hit the limit, not
            # a silent truncation (see the module docstring, "Continuation
            # line limit").
            return []
        collected.append(path)
        lines_consumed += 1
        idx += 1
    return collected


def extract_owns_paths(prompt: str) -> list:
    """[] -- no owns block found on any line (a read-only dispatch
    needs no manifest, this kit's rule 11) -- otherwise the list of
    path-like tokens from the FIRST line (or its multi-line
    continuation) that yielded >=1 such token.

    A single pass over MANIFEST_OWNS_RE (word-bounded, imported from
    dispatch_gate.py) -- see the module docstring, "Owns MARKER", for
    why this port carries no separate substring-fallback pass. Each
    line carrying the marker is tried in ORDER: the line itself is
    checked first (_paths_from_line); if it yielded no paths, the
    multi-line continuation is tried ONLY when the line itself is a
    genuine declaration (_is_owns_declaration_line, see "Declaration,
    not prose") -- prose containing the bare word "owns" is skipped
    without stealing a real declaration further down."""
    if not isinstance(prompt, str) or not prompt:
        return []

    lines = prompt.splitlines()

    for i, line in enumerate(lines):
        m = MANIFEST_OWNS_RE.search(line)
        if not m:
            continue
        paths = _paths_from_line(line, m.end())
        if paths:
            return paths
        if _is_owns_declaration_line(line, m.start(), m.end()):
            paths = _paths_from_continuation(lines, i + 1)
            if paths:
                return paths

    return []


# --- path normalization and overlap (shared with owns_verify.py) ------


def normalize_path(p: str) -> str:
    """.lower(), `\\` -> `/`, trailing `/` sliced off -- see the module
    docstring, "Path overlap semantics"."""
    if not isinstance(p, str):
        return ""
    p = p.strip().lower().replace("\\", "/")
    while len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def paths_overlap(a: str, b: str) -> bool:
    """Equality / a directory-prefix relationship at a segment boundary
    / an fnmatch in either direction when at least one path carries a
    glob -- fnmatch.fnmatchcase (not fnmatch.fnmatch) is used on
    purpose, for identical behavior regardless of the OS the tests
    happen to run on."""
    na, nb = normalize_path(a), normalize_path(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na.startswith(nb + "/") or nb.startswith(na + "/"):
        return True
    if "*" in na or "*" in nb:
        if fnmatch.fnmatchcase(nb, na) or fnmatch.fnmatchcase(na, nb):
            return True
    return False


# --- sidecar: reading live records + writing a new one -----------------

WINDOW_SECONDS = 24 * 60 * 60
_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"
_DESC_TRUNC_LEN = 200
REGISTRY_COMPACT_THRESHOLD_LINES = 500


def _now_iso(now: datetime) -> str:
    return now.strftime(_TS_FORMAT)


def _registry_path_from_cwd(cwd) -> Path:
    return Path(cwd or ".") / "logs" / "owns_registry.jsonl"


def _load_live_records(registry_path: Path, cwd, now: datetime) -> list:
    """Fail-open: a missing file / a malformed line / a wrong-typed
    field -- the record/line is silently skipped, the rest read
    normally. The scope is the SAME cwd (a literal string comparison),
    NOT session_key -- session_key inside a record is only a LABEL for
    the WARN message, see _find_overlaps."""
    if registry_path is None or not registry_path.exists():
        return []
    try:
        raw = registry_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    records = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("cwd") != cwd:
            continue
        ts_str = rec.get("ts")
        if not isinstance(ts_str, str):
            continue
        try:
            rec_ts = datetime.strptime(ts_str, _TS_FORMAT)
        except Exception:
            continue
        delta = (now - rec_ts).total_seconds()
        if delta < 0 or delta > WINDOW_SECONDS:
            continue
        owns = rec.get("owns")
        if not isinstance(owns, list):
            continue
        records.append(rec)
    return records


def _compact_live_lines(existing_lines: list, now: datetime) -> list:
    """Compaction: keeps only the RAW lines (str) whose ts falls inside
    the 24h liveness window -- GLOBALLY, with no cwd/session filter
    (compaction serves the whole file, not one specific dispatch). A
    malformed JSON line -- fail-open, silently dropped during
    compaction (see the module docstring, "Known sidecar limitations"
    -- compaction as a possible loss point for a concurrent write)."""
    live = []
    for line in existing_lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        ts_str = rec.get("ts")
        if not isinstance(ts_str, str):
            continue
        try:
            rec_ts = datetime.strptime(ts_str, _TS_FORMAT)
        except Exception:
            continue
        delta = (now - rec_ts).total_seconds()
        if delta < 0 or delta > WINDOW_SECONDS:
            continue
        live.append(line)
    return live


def _append_registry(
    registry_path: Path, now: datetime, session_key, cwd, description: str, owns_paths: list
) -> None:
    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": _now_iso(now),
            "session_key": session_key,
            "cwd": cwd,
            "description": description or "",
            "owns": owns_paths,
        }
        entry_line = json.dumps(entry, ensure_ascii=False)

        existing_lines = []
        if registry_path.exists():
            try:
                raw = registry_path.read_text(encoding="utf-8", errors="replace")
                existing_lines = [ln for ln in raw.splitlines() if ln.strip()]
            except Exception:
                existing_lines = []

        # Compaction ONLY when the number of lines is STRICTLY GREATER
        # than the threshold (500 -> a plain append; 501 -> compaction),
        # see the module docstring.
        if len(existing_lines) > REGISTRY_COMPACT_THRESHOLD_LINES:
            live_lines = _compact_live_lines(existing_lines, now)
            live_lines.append(entry_line)
            registry_path.write_text("\n".join(live_lines) + "\n", encoding="utf-8")
        else:
            with registry_path.open("a", encoding="utf-8") as f:
                f.write(entry_line + "\n")
    except Exception:
        # fail-open: being unable to append to the sidecar (e.g. a
        # read-only disk) must not crash the hook.
        pass


def _truncate(s: str, max_len: int = _DESC_TRUNC_LEN) -> str:
    s = (s or "").strip()
    if len(s) > max_len:
        return s[:max_len] + "\u2026"
    return s


def _find_overlaps(new_paths: list, records: list, session_key) -> list:
    """Groups overlaps BY NEW PATH, not by (path, record) pair -- a
    single new path that collides with several live records gives ONE
    entry in the result. Returns
    [(path, [(ts, description, same_session_bool), ...]), ...] -- paths
    in the order of new_paths, matched records inside in the order of
    records. same_session_bool compares a record's session_key against
    the CURRENT dispatch's session_key (a label, not a scope filter)."""
    grouped = []
    for p in new_paths:
        matches = []
        for rec in records:
            rec_owns = rec.get("owns") or []
            if any(paths_overlap(p, existing) for existing in rec_owns):
                same_session = rec.get("session_key") == session_key
                matches.append((rec.get("ts"), rec.get("description") or "", same_session))
        if matches:
            grouped.append((p, matches))
    return grouped


def _format_mention(ts, desc, same_session: bool) -> str:
    tag = (
        "a parallel dispatch of this same session"
        if same_session
        else "a different session (a parallel-session collision)"
    )
    return f"{ts} \u00ab{_truncate(desc)}\u00bb ({tag})"


def _format_path_line(p: str, matches: list) -> str:
    shown = matches[:2]
    mentions = "; ".join(_format_mention(ts, desc, same) for ts, desc, same in shown)
    extra = len(matches) - len(shown)
    if extra > 0:
        mentions += f"; and {extra} more"
    return f"path {p} overlaps with {mentions}"


def _format_overlap_context(grouped: list) -> str:
    head = grouped[:3]
    parts = [_format_path_line(p, matches) for p, matches in head]
    return (
        "OWNS OVERLAP (warn): " + "; ".join(parts) + "; a parallel write to "
        "shared paths -- serialize the work or split up the owns paths"
    )


# --- decide() ----------------------------------------------------------


def decide(payload: dict, registry_path: Path = None, now: datetime = None) -> tuple:
    """Nearly-pure logic (with sidecar I/O inside -- checking live owns
    unavoidably requires a read before the decision and a write after,
    see the module docstring, "ORDER") -- directly testable by passing
    its own registry_path/now. exit_code is ALWAYS 0 (WARN mode).
    Returns (0, None) on a quiet skip, (0, dict) -- a dict already
    ready for json.dumps on stdout, either on a found owns overlap OR
    on the empty-owns diagnostic (see "Diagnosing an empty owns")."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, None

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0, None

    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""

    owns_paths = extract_owns_paths(prompt)
    if not owns_paths:
        # An owns marker is declared, but no line yielded any path-like
        # tokens -- the check is blind, WARN about the blindness
        # instead of a quiet skip, the sidecar does NOT grow. A
        # genuine read-only dispatch (no marker / no write indicator)
        # stays silent.
        if MANIFEST_OWNS_RE.search(prompt) and WRITE_INDICATORS_RE.search(prompt):
            return 0, {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": BLIND_OWNS_WARN_MESSAGE,
                }
            }
        return 0, None

    if now is None:
        now = datetime.now()
    cwd = payload.get("cwd")
    if registry_path is None:
        registry_path = _registry_path_from_cwd(cwd)

    session_id = payload.get("session_id")
    session_key = session_id if isinstance(session_id, str) and session_id else cwd

    description = tool_input.get("description")
    if not isinstance(description, str):
        description = ""

    records = _load_live_records(registry_path, cwd, now)
    grouped = _find_overlaps(owns_paths, records, session_key)

    output = None
    if grouped:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": _format_overlap_context(grouped),
            }
        }

    # Order: the check runs FIRST, the write happens AFTER (self-overlap
    # is excluded structurally, see the module docstring, "ORDER").
    _append_registry(registry_path, now, session_key, cwd, description, owns_paths)

    return 0, output


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stdout_utf8()

    # The same byte-safe pattern as this kit's dispatch_gate.py/
    # hygiene_gate.py: sys.stdin.buffer.read() bypasses the text-mode
    # sys.stdin's platform encoding, an explicit UTF-8 decode with
    # errors="replace" is fail-open on malformed bytes.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    try:
        exit_code, output = decide(payload)
    except Exception:
        # belt-and-suspenders: decide() is already defensively typed,
        # but an adversarial input (e.g. an unexpected shape somewhere
        # deeper) must not crash the hook with a traceback out.
        return 0

    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
