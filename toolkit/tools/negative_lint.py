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
import json
import sys
from pathlib import Path

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

WARN_PREFIX_TEMPLATE = (
    "NEGATIVE LINT: {n} negative statement(s) with no same-form control "
    "nearby: {body}. A negative claim without a positive same-form "
    "control is a reject candidate (command hygiene point 6)."
)


def _line_has_any_marker(line_lower: str, markers: list) -> bool:
    return any(marker in line_lower for marker in markers)


def find_violations(text: str) -> list:
    """Returns a list of (line_no, 1-indexed, original_line_text) for
    every line of text carrying a negative marker with NO control
    marker in the +/-WINDOW_RADIUS-line window (including the line
    itself). Empty text -> empty list (the silent path for both the
    hook and the CLI)."""
    if not text:
        return []
    lines = text.splitlines()
    lowered = [ln.lower() for ln in lines]
    violations = []
    for i, low in enumerate(lowered):
        if not _line_has_any_marker(low, NEG_MARKERS):
            continue
        lo = max(0, i - WINDOW_RADIUS)
        hi = min(len(lines) - 1, i + WINDOW_RADIUS)
        window_has_control = any(
            _line_has_any_marker(lowered[j], CONTROL_MARKERS)
            for j in range(lo, hi + 1)
        )
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


def _hook_main() -> int:
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
    sys.exit(main())
