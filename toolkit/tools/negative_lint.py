"""negative_lint.py -- PostToolUse hook in WARN MODE (NEVER blocks) for
subagent results (tool_name Task/Agent), plus a separate CLI mode for
linting an arbitrary text file.

MOTIVE: the criterion "a negative claim needs a positive same-form
control alongside it" (command hygiene point 6) is held by DoD text
and judge acceptance keys -- by discipline, not by a machine. This
class of miss recurs (a negative claim reviewed by two judges still
slipped through in the source deployment; a scout once asserted "this
directory does not exist" while it was actually present). This file
mechanizes the HINT (not the decision): WARN that a negative sits next
to no control, the final judgment (reject/not reject) stays with the
coordinator/critic/judge.

DESIGN (modeled on tools/hygiene_gate.py, tools/journal_echo.py,
tools/dispatch_gate.py, all read in full before implementation):

 - Matches the PostToolUse payload contract and the byte-safe stdin
   read -- literally the same pattern as hygiene_gate.py/
   journal_echo.py: sys.stdin.buffer.read() + decode("utf-8",
   errors="replace") -- bypasses the platform encoding of the text
   sys.stdin and fails open on non-UTF8 bytes (adversarial DoD key).
 - tool_name filter -- the SAME list tools/dispatch_gate.py already
   uses: `tool_name in ("Task", "Agent")` -- two literal values of one
   and the same PreToolUse/PostToolUse tool (the .claude/settings.json
   matcher already writes them as one pair joined by `|`), not
   RU/EN aliases of one word.
 - Hook response shape -- the SAME shape tools/journal_echo.py already
   uses on this harness: one JSON object on stdout,
   {"hookSpecificOutput": {"hookEventName": "PostToolUse",
   "additionalContext": "<string>"}}, WITHOUT permissionDecision (WARN,
   not a blocking decision -- the same caution tools/hygiene_gate.py
   takes for its own PreToolUse output: permissionDecision is
   deliberately absent here too). Exit code is ALWAYS 0 -- WARN mode
   per spec, never blocks.

EXTRACTING TEXT FROM tool_response (an explicit adversarial DoD case:
"a result object instead of a string (nested content)"): a subagent's
real tool_response shape on this harness has not been captured
first-hand from a live Task/Agent tool call outside the builder role
(the same limitation tools/dod_track.py already documents for its own
XWb/Task payload capture -- a live capture would require the Task/Agent
tool itself, outside the builder role, flat delegation). Extraction is
built to be maximally tolerant of different shapes, the same principle
as tools/dod_track.py._extract_text (a GIVEN example):

 1. tool_response -- a string -> used as-is.
 2. tool_response -- a dict with a "content" field that is a list of
    blocks (the Anthropic API content-block shape, {"type": "text",
    "text": ...} or a bare string element) -> the text of all "text"
    blocks is joined with a newline.
 3. Otherwise -- a dict with one of "text"/"output"/"stdout"/"stderr"
    (a string) -> the first one found is used.
 4. Otherwise (an unrecognized shape) -> json.dumps of the whole
    tool_response -- the regexes/markers still have something to search
    (the same fallback tools/dod_track.py._extract_text uses for an
    unfamiliar payload shape).
 5. tool_response absent/None -> an empty string -> analysis on empty
    text always gives "no violations" -> a silent exit 0 (an explicit
    positive case in DoD point 3: "payload without tool_response").

MARKERS (spec, literally two lists, RU+EN, case-insensitive; substring
comparison via .lower() -- NOT regex/word-boundary: the spec itself
requires triggering "mid-word" -- "отсутствует" must be caught by the
marker "отсутств", "не найдено ни" by the marker "не найден" -- both
verified by tools/test_negative_lint.py):

 NEGATIVE:  не найден / не существует / отсутств / нет ни одного /
            нигде не / 0 совпадений (RU) ;
            not found / does not exist / no such / absent / nowhere /
            0 matches (EN)
 CONTROL:   контрол / образец / позитивн / та же форм /
            известно-существующ / закрыто (RU, "закрыто" -- a
            control-form marker for a closed/resolved verdict, named
            explicitly by the spec as a control marker) ;
            control / known-present / same form / positive check (EN)

WINDOW +/-3 LINES (spec, literally): for a line carrying a negative
marker, a control is searched for in the range [i-3, i+3] by line
(7 lines including the negative line itself) -- a control EXACTLY 3
lines away from the negative falls inside the window (the WARN is
suppressed), 4 lines away is already OUTSIDE it (the WARN stays). Both
cases are separate boundary tests (rule 6a of the builder role).

VIOLATION PREVIEW (the spec quotes the format literally, but does NOT
name a truncation length for one line -- an engineering choice of this
implementation's own, documented rather than guessed silently): each
of the first 3 offending lines is truncated to PREVIEW_MAX_LEN=200
characters with an ellipsis "…" on truncation -- enough for the
coordinator to recognize the line, while capping the impact of an
adversarially huge single line on the size of additionalContext (the
same principle as MAX_MESSAGE_LEN in tools/journal_echo.py/
tools/tier_echo.py, a different number -- a different content class:
those cap a model name, this one an arbitrary line of subagent
output).

PERFORMANCE (an explicit DoD case: "1 MB of text (time < 2s)"): every
check is a substring test (`in`, CPython's efficient built-in
algorithm, no catastrophic backtracking) over LINES of text, the
control window is a fixed 7 lines per negative line, independent of
the text's total length -- linear in the number of lines and markers,
with no regex/nested quantifiers at all for the marker string search.

FAIL-OPEN (an explicit DoD case, "everything is fail-open: exit 0, no
traceback leaks out"): main() has ONE outer try/except around the
whole body (the same principle every other hook in this template
uses) -- any unforeseen exception (broken JSON, a non-dict payload,
non-UTF8 bytes, anything) -> a silent exit 0. decide()/find_violations()
are already defensively typed on their own (an isinstance check at
every step); the outer try/except is a second, coarser net for
anything that slips past that.

CLI MODE (spec: "`python tools/negative_lint.py --text <file>` lints
an arbitrary text file ... the same analysis, output to stdout, always
exit 0"): the file is read as BYTES and decoded utf-8 with
errors="replace" (the same fail-open principle as the hook path) --
using the same find_violations()/format_warning() as the hook. Silence
on clean text is this implementation's OWN choice (the spec does not
say explicitly what happens on clean input), chosen symmetrically with
the hook's own behavior ("the same analysis" in the literal sense --
the same silence/message criterion, not only the same detection
algorithm), documented here, not guessed silently.

REGION-AWARE (ported from the reference deployment's tools/negative_lint.py,
same class as docs/SIBLING_MAP.md's "a guard does not distinguish the
author's own claim from quoted/nested content"): substring matching in
a +/-3-line window alone cannot tell WHERE a marker physically sits --
in the author's own prose (a real claim/control) or inside a quote/
fence of someone else's text (not the author's own statement at all).
Symmetric for the negative marker itself.

POLICY (B1, literal): fenced/blockquote -- NOT a violation (and does
NOT count as a control), inline_code -- a violation (and DOES count as
a control). AN UNTERMINATED FENCE = PROSE (silence-looks-like-success
lesson -- a degraded module or unterminated markup must never WIDEN
the silence zone; safer to over-count an unterminated fence chunk as a
violation than to silently swallow it).

CLASSIFICATION PRIORITY of a single position (_classify, this
implementation's own engineering decision, not silently guessed --
justified here because the discrimination negative control below makes
the choice CHECKABLE, not arbitrary): Region.kinds is a tuple, may be
("blockquote", "fenced") or ("blockquote", "prose") or
("blockquote", "inline_code") etc. (md_regions.py). Rule, in order:
 1. unterminated AND KIND_FENCED in kinds -> "prose" (the "unterminated
    fence = prose" rule, BEFORE everything else -- overrides even
    blockquote nesting).
 2. KIND_FENCED in kinds -> "fenced" (fenced never mixes with
    inline_code -- fenced lines never go through md_regions.scan()'s
    inline splitter).
 3. KIND_INLINE_CODE in kinds -> "inline_code" (even inside a quote --
    "inline code is a violation" reads literally unconditional, not
    restricted by nesting in the spec).
 4. KIND_BLOCKQUOTE in kinds (without 1-3) -> "blockquote" (ordinary
    quoted prose, ("blockquote", "prose") in md_regions -- NOT a
    violation).
 5. else -> "prose" (top-level author prose, the default).
This resolves the spec's one explicit fork: "fenced/blockquote -- not
a violation, inline_code -- a violation" reads as PRIORITY ORDER
(1 > 2 > 3 > 4 > 5), not independent bits -- an alternative (e.g. "any
blockquote admixture silences, even alongside inline_code") would make
the discrimination negative control below INDISTINGUISHABLE (both
forms give the same result for the "control quoted, negative in prose"
test pair) -- ordered reading is the only one guaranteed to change the
result when the region filter is disabled.

POSITIONAL INVARIANT (literal): the +/-3-line window is computed over
the ORIGINAL text.splitlines() indices -- no index shifts or
renumbers because of a region (region filtering is an ADDITIONAL
predicate on a line found the ordinary way, not a re-indexing of the
line list). TEST PAIR "control quoted, negative in prose": the
negative sits in prose (violation candidate), the control marker sits
physically inside a quote within the +/-3 window -- the region filter
must tell the two cases apart and not let the quoted "control"
suppress a real violation (see test_negative_lint_md.py, the
discrimination section, plus a SEPARATE run with
MODULE_UNDER_TEST=live that suppresses the violation on the same text
-- a red run as the negative control, command hygiene point 6).

I-0 (ANY md_regions failure -- a module-wide ImportError, an exception
out of scan(), or a degraded=True result) -> this guard behaves EXACTLY
as before region-awareness: find_violations() runs the SAME algorithm
the pre-region file did (a +/-3-line window by substring match, no
region access at all) -- see _safe_scan and every "if scan_result is
not None:" branch below, which becomes a NO-OP when scan_result is
None -- the branching is not a separately-built code path, it is ONE
loop whose region branch goes dead.

I-1 (Rule #1, laziness): the scanner is called AFTER the cheap
pre-filter -- the cheap pre-filter here IS the already-existing O(n)
substring search for NEG_MARKERS over every line (find_violations
already did this FIRST); scan() is called EXACTLY ONCE per
find_violations call, and ONLY if that pre-filter found at least one
candidate line -- on text carrying no negative marker at all, scan()
is never called (count 0).

Import -- a try/except pair (the same pattern tools/owns_gate.py uses
for md_regions), scan staying None on failure (a missing sibling is
not a live error here -- md_regions.py is a standing module this kit
already carries, but I-0 must survive its complete absence too, the
same fallback as an exception out of an already-imported scan()).

ASYNC LAUNCH (a recurring finding on the source deployment): the
tool_response of an ASYNCHRONOUS Task/Agent launch (`isAsync: true` /
`status: "async_launched"`) is LAUNCH METADATA (agentId, description,
resolvedModel, an echo of the coordinator's own prompt in a "prompt"
field), NOT a worker's report. Such a dict has neither "content" nor
"text"/"output"/"stdout"/"stderr" -- `_extract_text` falls through to
the json.dumps fallback of the WHOLE payload and the linter ends up
scanning the COORDINATOR's OWN PROMPT (legitimate negative phrasing
from the spec text itself, with no control next to it -- a false
positive). Skipping this is legal: the worker's actual final result
arrives as a SEPARATE, later PostToolUse event and is linted normally
(the same decide()) -- there is simply nothing to analyze here. decide()
checks this BEFORE `_extract_text`: tool_response is a dict AND
(isAsync is True OR status == "async_launched") -> a silent (0, None).
A shape without these markers (isAsync missing/False, status not
"async_launched") goes through the ordinary path -- the json.dumps
fallback stays live for other unrecognized dict shapes.
"""

import argparse
import bisect
import json
import os
import sys
import threading
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    from md_regions import scan, KIND_FENCED, KIND_BLOCKQUOTE, KIND_INLINE_CODE
except ImportError:
    scan = None
    KIND_FENCED = "fenced"
    KIND_BLOCKQUOTE = "blockquote"
    KIND_INLINE_CODE = "inline_code"

NEG_MARKERS_RU = [
    "не найден",
    "не существует",
    "отсутств",
    "нет ни одного",
    "нигде не",
    "0 совпадений",
]
NEG_MARKERS_EN = [
    "not found",
    "does not exist",
    "no such",
    "absent",
    "nowhere",
    "0 matches",
]
NEG_MARKERS = NEG_MARKERS_RU + NEG_MARKERS_EN

CONTROL_MARKERS_RU = [
    "контрол",
    "образец",
    "позитивн",
    "та же форм",
    "известно-существующ",
    "закрыто",
]
CONTROL_MARKERS_EN = [
    "control",
    "known-present",
    "same form",
    "positive check",
]
CONTROL_MARKERS = CONTROL_MARKERS_RU + CONTROL_MARKERS_EN

WINDOW_RADIUS = 3
PREVIEW_MAX_LEN = 200
PREVIEW_HEAD_COUNT = 3

# RULE-OF-THREE TEXT (synced from HQ's tools/negative_lint.py, where an
# ACTION imperative clause was added before the provenance parenthetical):
# what's wrong (a negative with no nearby control), what it risks (a
# reject candidate), the action (add a same-form control, or double-check
# it) -- the registry literal "NEGATIVE LINT: " kept byte-exact.
WARN_PREFIX_TEMPLATE = (
    "NEGATIVE LINT: {n} negative statement(s) with no same-form control "
    "nearby: {body}. A negative claim without a positive same-form "
    "control is a reject candidate; add a same-form control next to each "
    "statement, or double-check it (command hygiene point 6)."
)


def _line_has_any_marker(line_lower: str, markers: list) -> bool:
    return any(marker in line_lower for marker in markers)


# Regions whose kinds exclude a position from consideration (neither as
# a violation, nor as a control) -- see the module docstring, "POLICY".
_EXCLUDED_KINDS = ("fenced", "blockquote")


def _safe_scan(text: str):
    """I-0: None on a missing module / an exception out of scan() /
    a degraded=True result -- all three collapse to one "no region"
    signal for the caller (find_violations simply stops filtering by
    region, matching the pre-region algorithm exactly)."""
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
    """The same bisect algorithm as md_regions.kind_at(), but returns
    the WHOLE Region (not just its kinds) -- needed for .unterminated,
    the "unterminated fence = prose" rule."""
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


def _classify(region) -> str:
    """See the module docstring, "CLASSIFICATION PRIORITY". region is
    None (no region at this position, end of text, outside coverage)
    -> "prose" (the safe default -- behaves as if there were no region
    at all)."""
    if region is None:
        return "prose"
    if region.unterminated and KIND_FENCED in region.kinds:
        return "prose"
    if KIND_FENCED in region.kinds:
        return "fenced"
    if KIND_INLINE_CODE in region.kinds:
        return "inline_code"
    if KIND_BLOCKQUOTE in region.kinds:
        return "blockquote"
    return "prose"


def _line_start_offsets(text: str) -> list:
    """Start offset (in CHARACTERS of the original text) of every
    text.splitlines() line -- the same scheme as
    md_regions._split_lines() (splitlines(keepends=True), a cumulative
    sum of lengths)."""
    offsets = []
    pos = 0
    for wt in text.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(wt)
    return offsets


def _marker_offset_in_line(line_lower: str, markers: list) -> int:
    """Position of the first matched marker inside an ALREADY-found
    line (the line is guaranteed to carry at least one marker --
    called only after _line_has_any_marker returned True)."""
    for marker in markers:
        idx = line_lower.find(marker)
        if idx != -1:
            return idx
    return 0


def find_violations(text: str) -> list:
    """Returns a list of (line_no, 1-indexed, original_line_text) for
    every line of text carrying a negative marker with NO control
    marker in the +/-WINDOW_RADIUS-line window (including the line
    itself), with region policy B1 (fenced/blockquote excluded on
    BOTH sides, inline_code and prose count; an unterminated fence =
    prose) -- see the module docstring, "REGION-AWARE", in full.
    Empty text -> empty list (the silent path for both the hook and
    the CLI)."""
    if not text:
        return []
    lines = text.splitlines()
    lowered = [ln.lower() for ln in lines]

    negative_idxs = [i for i, low in enumerate(lowered) if _line_has_any_marker(low, NEG_MARKERS)]
    if not negative_idxs:
        return []  # I-1: scan() is NOT called -- nothing to check

    scan_result = _safe_scan(text)
    line_offsets = _line_start_offsets(text) if scan_result is not None else None

    violations = []
    for i in negative_idxs:
        if scan_result is not None:
            pos = _marker_offset_in_line(lowered[i], NEG_MARKERS)
            kind = _classify(_region_at(scan_result, line_offsets[i] + pos))
            if kind in _EXCLUDED_KINDS:
                continue  # B1: fenced/blockquote -- not a violation

        lo = max(0, i - WINDOW_RADIUS)
        hi = min(len(lines) - 1, i + WINDOW_RADIUS)
        window_has_control = False
        for j in range(lo, hi + 1):
            if not _line_has_any_marker(lowered[j], CONTROL_MARKERS):
                continue
            if scan_result is not None:
                cpos = _marker_offset_in_line(lowered[j], CONTROL_MARKERS)
                ckind = _classify(_region_at(scan_result, line_offsets[j] + cpos))
                if ckind in _EXCLUDED_KINDS:
                    continue  # a quoted/fenced "control" does not count
            window_has_control = True
            break
        if not window_has_control:
            violations.append((i + 1, lines[i]))
    return violations


def _truncate(s: str, max_len: int = PREVIEW_MAX_LEN) -> str:
    s = s.strip()
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


def format_warning(violations: list) -> str:
    """"NEGATIVE LINT: N negative statement(s) with no same-form
    control nearby: <first 3 offending lines, truncated>. A negative
    claim without a positive same-form control is a reject candidate
    (command hygiene point 6)." -- the spec's literal text. Empty
    violations -> "" (the caller treats an empty string as silence)."""
    if not violations:
        return ""
    n = len(violations)
    head = violations[:PREVIEW_HEAD_COUNT]
    parts = [f"line {line_no}: {_truncate(line_text)}" for line_no, line_text in head]
    body = "; ".join(parts)
    return WARN_PREFIX_TEMPLATE.format(n=n, body=body)


def _extract_text(tool_response) -> str:
    """See the module docstring, "EXTRACTING TEXT FROM tool_response"
    -- a string as-is / a content-block list / text|output|stdout|stderr
    / a json.dumps fallback / None -> ""."""
    if isinstance(tool_response, str):
        return tool_response
    if tool_response is None:
        return ""
    if isinstance(tool_response, dict):
        content = tool_response.get("content")
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    t = block.get("text")
                    if isinstance(t, str):
                        parts.append(t)
                elif isinstance(block, str):
                    parts.append(block)
            if parts:
                return "\n".join(parts)
        for key in ("text", "output", "stdout", "stderr"):
            value = tool_response.get(key)
            if isinstance(value, str):
                return value
        try:
            return json.dumps(tool_response, ensure_ascii=False)
        except Exception:
            return str(tool_response)
    return str(tool_response)


def decide(payload: dict) -> tuple:
    """Pure logic, no I/O -- the same style as hygiene_gate.decide/
    dispatch_gate.decide. exit_code is ALWAYS 0 (WARN mode). Returns
    (0, None) on a silent pass, (0, dict) -- the dict already ready
    for json.dumps on stdout when violations are found."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, None

    tool_response = payload.get("tool_response")
    if isinstance(tool_response, dict) and (
        tool_response.get("isAsync") is True
        or tool_response.get("status") == "async_launched"
    ):
        return 0, None

    text = _extract_text(tool_response)
    violations = find_violations(text)
    if not violations:
        return 0, None

    context = format_warning(violations)
    return 0, {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _cli_main(text_path: str) -> int:
    """`python tools/negative_lint.py --text <file>` -- see the module
    docstring, "CLI MODE". Always returns 0."""
    try:
        raw_bytes = Path(text_path).read_bytes()
        text = raw_bytes.decode("utf-8", errors="replace")
        violations = find_violations(text)
        warning = format_warning(violations)
        if warning:
            print(warning)
    except Exception:
        pass
    return 0


# --- stdin deadline (P4 class; a LOCAL copy, no shared module -- the
# same helper toolkit/tools/owns_gate.py/dispatch_gate.py already carry)
# ------------------------------------------------------------------

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
# exiting cleanly. main()/_hook_main() are UNCHANGED (still a plain
# `return 0`, safe in-process); only the actual __main__ script-exit
# path below escalates to os._exit().
_STDIN_DEADLINE_STATE = {"hit": False}


def _hook_main() -> int:
    raw_bytes, timed_out = _read_stdin_bytes_deadline()
    if timed_out:
        _STDIN_DEADLINE_STATE["hit"] = True
        sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
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


def main() -> int:
    _reconfigure_stdout_utf8()
    try:
        argv = sys.argv[1:]
        if argv:
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument("--text")
            args, _unknown = parser.parse_known_args(argv)
            if args.text:
                return _cli_main(args.text)
        return _hook_main()
    except Exception:
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
