"""tools/search_control_gate.py -- PostToolUse hook, WARN MODE
(non-blocking). Mechanizes the second half of CLAUDE.md command-hygiene
point 6: an empty content search is reportable only after a positive
control. The PreToolUse sibling (tools/hygiene_gate.py) catches
KNOWN-BAD invocations before they run; this one catches the case
command hygiene point 6 actually names -- a search that came back
empty -- and reminds at the moment the misleading result appears,
before it can be reported as absence.

ORIGIN: this file is a PORT of HQ's own tools/search_control_gate.py,
landing here as part of the toolkit full-mirror batch. Semantics of
the fixes below are preserved verbatim from the source; the
adaptations made FOR THE TOOLKIT are: (1) PowerShell -- this template
also uses the PowerShell tool, handled identically to Bash (term = the
whole command verbatim, searchability via SEARCH_TOKENS); "select-string"
added to SEARCH_TOKENS as PowerShell's grep-equivalent cmdlet;
(2) this docstring, rewritten for the template; (3) the CLAUDE.md rule
reference below points at this template's own command hygiene point 6.

DELIVERY NOTE (a self-activating hook file is never placed on its live
path by its own builder -- CLAUDE.md routing rule 2, the
enforcement-file-review rule): delivered by the builder as content /
under a sibling filename; Lead places it on the live path and
registers the PostToolUse hook in .claude/settings.json at acceptance.

WARN ONLY: always exits 0, never sets permissionDecision, never blocks.
Its effects are hookSpecificOutput.additionalContext on stdout (when a
search comes back empty) and a session ledger write (see the ledger
addition below) -- the ledger write is silent and has no bearing on
exit code or stdout.

WHY A PROBE-FRIENDLY DESIGN: the exact PostToolUse payload schema was
not verified from first-hand observation when this file was first
written at the source, only from a documentation summary. So the
script does not assume field names. It looks for the tool name and the
tool result under several plausible keys, and when it cannot read them
it writes the raw payload to `logs/posttooluse-schema-sample.json`
(path overridable via the SEARCH_CONTROL_GATE_SAMPLE_PATH env var --
see `_sample_path()` -- so tests can redirect it away from `logs/`)
instead of guessing. That file is the evidence for adjusting the key
list; its presence means the hook ran but could not read the payload,
which is itself the finding.

TRIGGERS on an empty result from a SEARCH only. A plain empty output is
not enough: `git status --short` on a clean tree is legitimately empty
and must not warn. The command (or tool) has to look like a content
search.

AN EARLIER FIX -- the probe was unreachable as designed, and a real
class of empty results was silently missed:

  1. The sample file used to write ONLY when tool_name AND result were
     BOTH unfindable. Known Claude Code payloads DO carry tool_name --
     so whenever the result lived under an unknown key, the hook
     passed silently forever and no evidence ever landed. Fixed: the
     sample now also writes when tool_name is present, the tool looks
     like a search, and the result is either missing or of an
     unrecognized (dict) shape -- see `_classify_result`'s
     "unjudgeable" outcome and `main()`'s `should_sample` logic.
  2. A dict-shaped tool_response used to serialize via `_as_text` into
     non-empty JSON text before any emptiness check ran -- so a
     genuinely empty structured result, e.g. {"stdout": ""}, became
     the non-empty-looking string '{"stdout": ""}' and `_is_empty_text`
     never recognized it as empty. Fixed: `_classify_result` now judges
     a dict result STRUCTURALLY, before any serialization -- see its
     own docstring for the recognized shapes (stdout / filenames+
     numFiles / content) and what happens when none of them match.

SESSION SEARCH LEDGER (half A of the negative-claim correlation gate;
see tools/claim_control_gate.py for half B):

WHY (carried verbatim from the source): more than once in one session
an agent asserted "X does not exist" without ever having searched for
X. CLAUDE.md command hygiene point 6 already forbids this; it was
enforced on discipline alone and discipline missed. This hook already
observes every search as it happens (PostToolUse on
Bash/PowerShell/Grep/Glob) -- so it is the natural place to RECORD what
was searched, per session, so a second hook (claim_control_gate.py,
PreToolUse on Edit|Write) can correlate an about-to-be-written negative
claim against what was actually searched this session, instead of
trusting the claim on its face.

WHAT IS RECORDED: one JSON line per OBSERVED SEARCH (i.e. only when
`_looks_like_search` judged the tool/command to look like a search --
a non-search Bash/PowerShell command, e.g. `git status`, is not
recorded, since there is nothing to correlate a later claim against),
PLUS one line per Read call. Each line:
`{"ts": ..., "tool": <tool name>, "term": <search term(s) or the read
file path>, "empty": <bool>}`. Term extraction, per spec: for
Grep/Glob, the pattern/path from tool_input (checked under a few
plausible keys, same probe-friendly philosophy as the rest of this
file); for Bash AND PowerShell (this template's adaptation -- see
"ORIGIN" above), the WHOLE command string verbatim -- the term is
embedded in it and half B does substring matching, so no attempt is
made to parse it out; for Read, the file_path from tool_input.

LEDGER LOCATION: `logs/.search-ledger/<session>.jsonl`, session
derived from a literal `session_id` key in the payload (see
`_session_id()`) -- ONE specific key is checked, deliberately, not a
guessed list of aliases: this is the same "unreachable probe" mistake
this file's own earlier fix already paid for once (a probe that never
fires because its trigger condition is too narrow, so no evidence ever
lands to correct it). If `session_id` is absent, the session is
recorded as the literal string "unknown" AND the raw payload is
written once via the EXISTING `_write_sample_once` mechanism (subject
to its own once-only guard) -- so if `session_id` turns out to be the
wrong key name, the sample file is the evidence to fix it from,
exactly like the tool_name/result probe above. Directory is
overridable via the SEARCH_CONTROL_GATE_LEDGER_DIR env var (see
`_ledger_dir()`), same pattern as `_sample_path()`, so tests never
write into the real `logs/` directory. A ledger write failure (no
permissions, disk full, directory missing) is wrapped in its own
try/except and never affects the exit code or the empty-search
warning -- this hook's primary behavior stays WARN-only and absolute.

FURTHER HARDENING FIXES (found by review on the source deployment;
D2/D3/D4a answered here; D1/D4b/D5/D6/D7/D8 live entirely on the half-B
side, see tools/claim_control_gate.py's own docstring):

  D3 -- stdin-hardening asymmetry. The PreToolUse side (tools/hygiene_gate.py)
  reads raw bytes with errors="replace" behind one fail-open try/except
  boundary around the WHOLE body of main(); the PostToolUse side (this
  file, an earlier version) read text via a bare `sys.stdin.read()` with
  NO surrounding try/except -- genuinely raising UnicodeDecodeError
  (exit 1) on invalid UTF-8 under a UTF-8-locked locale
  (`PYTHONIOENCODING=utf-8`), breaking the documented "exit 0 always"
  contract instead of merely risking it. Fixed: `_read_stdin_bytes()` +
  `_reconfigure_stdout_utf8()`, identical in shape to
  tools/hygiene_gate.py and to this delivery's own
  tools/claim_control_gate.py, and the entire body of `main()`
  (stdin read, JSON parse, ledger write, sample write, warn) now runs
  inside ONE fail-open try/except, mirroring those two files' `main()`.

  D4a -- Read calls are now ALSO recorded to the ledger (same line
  shape, tool="Read", term=the file_path from tool_input), alongside
  the existing search-tool recording -- see `EXAMINE_TOOLS` and
  `_extract_examine_term`. Rationale: command hygiene point 6 asks
  whether you LOOKED; reading a file is a positive control for that
  file's own existence, exactly as much as grepping for it. This does
  NOT make Read a general-purpose "search" for the empty-result warning
  above (Read is not added to `SEARCH_TOOLS`/`_looks_like_search` -- an
  empty file is not a miscall) -- it is purely an additional ledger
  source that half B's correlation can match against. See half B's own
  docstring for the residual this narrows but does not erase: a Read of
  file X defends a later claim ABOUT X's own existence, not claims
  about unrelated tokens X's content happens to mention.
"""
import json
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SAMPLE = os.path.join(REPO, "logs", "posttooluse-schema-sample.json")
_DEFAULT_LEDGER_DIR = os.path.join(REPO, "logs", ".search-ledger")

# A LEDGER-SIZE FIX (a live precedent: tools/owns_gate.py's own
# REGISTRY_COMPACT_THRESHOLD_LINES=500/_append_registry): ledger files
# (both session-specific and unknown.jsonl) are append-only and grow
# WITHOUT BOUND in a long-lived session/repo. Compaction happens AT
# WRITE TIME: when the line count IN THE FILE (before the new line is
# added) is STRICTLY GREATER than the threshold, ONLY THE TAIL (the
# last LEDGER_COMPACT_THRESHOLD_LINES lines, the MOST RECENT) is kept +
# the new line; the file is REWRITTEN. Unlike tools/owns_gate.py (a
# liveness filter on a 24h TTL), this is a plain FIFO tail-truncation --
# the ledger exists for claim_control_gate.py to CORRELATE against
# recent searches/reads, recent lines are worth more than old ones, no
# TTL semantics are needed. BOUNDARY (rule 6a of the builder role):
# EXACTLY 500 existing lines -> a plain append (500 is NOT strictly
# greater than 500); EXACTLY 501 existing lines -> compaction (501 IS
# strictly greater than 500) -- see
# test_ledger_compaction_boundary_500_vs_501_lines in
# tools/test_search_control_gate.py. Applies IDENTICALLY to
# session-specific files AND to unknown.jsonl -- no separate "unknown
# dominates" carve-out is added (a recorded decision, revisit after
# more field use).
LEDGER_COMPACT_THRESHOLD_LINES = 500

# Tools whose whole purpose is search: an empty result is always worth a nudge.
SEARCH_TOOLS = {"Grep", "Glob"}

# Tools that constitute a positive-control EXAMINATION (D4a) but are
# not themselves "search tools" for the empty-result warning above -- an
# empty file read is not a miscall the way an empty grep is.
EXAMINE_TOOLS = {"Read"}

# For Bash/PowerShell, only commands that actually search. Deliberately
# narrow: an empty result from `git status` or `ls` of an empty dir is
# not a miscall. "select-string" added (this template's PowerShell
# adaptation -- see module docstring "ORIGIN"): PowerShell's own
# grep-equivalent cmdlet, `Select-String`.
SEARCH_TOKENS = ("grep", "rg ", "ripgrep", "find ", "fd ", "ls -1", "awk ", "select-string")

# RULE-OF-THREE TEXT (synced from HQ's tools/search_control_gate.py,
# where the consequence clause below was added): what's wrong (an
# empty result may just mean a miscall), what it risks (reporting
# absence when the thing may be present), the action (run a same-form
# positive control) -- HQ's own literal wording kept, only the rule
# reference translated to this template's own numbering.
MSG = (
    "Search returned nothing. Command hygiene point 6: an empty result may "
    "simply mean the tool was miscalled, not that the thing is absent -- report "
    "absence ONLY after a positive control: run the same tool and syntax against "
    "a sample known to exist. Known miscall modes here: "
    "\\b does not fire on Cyrillic; shell-grep -i does not case-fold Cyrillic; "
    "single-language queries miss localised data; a marker searched in file "
    "bodies may be written in varying formats -- use a structural field."
)


def _sample_path():
    """The schema-sample file path. Overridable via the
    SEARCH_CONTROL_GATE_SAMPLE_PATH env var (read at call time, not at
    import time) so tests can redirect writes away from `logs/` without
    monkeypatching a module-level constant or reloading the module."""
    return os.environ.get("SEARCH_CONTROL_GATE_SAMPLE_PATH") or _DEFAULT_SAMPLE


def _ledger_dir():
    """The session-ledger directory. Overridable via the
    SEARCH_CONTROL_GATE_LEDGER_DIR env var, read at call time -- same
    pattern and rationale as `_sample_path()`. Shared, by env-var NAME,
    with tools/claim_control_gate.py's reader, since the two
    scripts must agree on where the ledger lives."""
    return os.environ.get("SEARCH_CONTROL_GATE_LEDGER_DIR") or _DEFAULT_LEDGER_DIR


def _first(payload, keys):
    for k in keys:
        if isinstance(payload, dict) and k in payload:
            return payload[k]
    return None


def _as_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, dict)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    return str(value)


def _command_text_for_classification(tool_name, tool_input_raw):
    """A CLASSIFICATION FIX (a live reproduction): search-classification
    MUST look at the COMMAND STRING ITSELF (tool_input.command for
    Bash/PowerShell), NOT at the JSON of the WHOLE tool_input. An
    earlier version had `_looks_like_search` receive
    `_as_text(tool_input_raw)`, which for a dict value serializes the
    ENTIRE tool_input (including, for example, a `description` field)
    -- a command like `git status --short` with description "Find
    modified files" was falsely classified as a search, because the
    substring "find " (SEARCH_TOKENS) was found in the description, not
    in the command itself. FIX: for Bash/PowerShell, ONLY
    tool_input.command is taken; for other tools (except Grep/Glob,
    which are already covered by SEARCH_TOOLS membership and don't need
    this function at all) it returns None -- no other text field is
    invented."""
    if tool_name in ("Bash", "PowerShell") and isinstance(tool_input_raw, dict):
        cmd = tool_input_raw.get("command")
        if isinstance(cmd, str):
            return cmd
    return None


def _looks_like_search(tool_name, command_text):
    if tool_name in SEARCH_TOOLS:
        return True
    if not command_text:
        return False
    low = command_text.lower()
    return any(tok in low for tok in SEARCH_TOKENS)


def _is_empty_text(result_text):
    if result_text is None:
        return False
    stripped = result_text.strip()
    if not stripped:
        return True
    # Common "nothing found" shapes that are not literally empty.
    return stripped in ("[]", "{}", '""') or stripped.lower() in (
        "no files found",
        "no matches found",
    )


def _classify_result(result):
    """Returns one of "missing", "empty", "nonempty", "unjudgeable".

    Judges dict-shaped structured tool_response values STRUCTURALLY,
    before any JSON serialization -- see the module docstring's earlier
    fix, point 2: a dict result used to serialize via `_as_text` into
    non-empty JSON text even when it represented an empty search
    (e.g. {"stdout": ""} -> the string '{"stdout": ""}', which
    `_is_empty_text` never recognized as empty).

    CONTENT/COUNT-MODE FALSE-POSITIVE FIX (a live reproduction,
    confirmed empirically against a live session's own ledger): this
    hook falsely warned "Search returned nothing" on genuinely
    NON-empty Grep results in content-mode (returned the matching line
    text) and count-mode (returned "N total occurrences"), while an
    empty Grep/Glob still correctly warned and a non-empty Glob still
    correctly stayed silent. Root cause, confirmed by re-ordering the
    checks below: this harness's Grep dict response carries EMPTY
    `filenames`/`numFiles` in content/count mode (the file list is only
    populated in files_with_matches mode) even when `content` itself is
    genuinely non-empty -- the OLD check order tested
    filenames/numFiles BEFORE content, so a real match was
    misclassified "empty" purely because the (irrelevant, in this mode)
    file-list fields were empty. FIXED, conservatively (no `mode` key
    invented -- none was present in any observed payload; no schema
    sample was ever written for this case either, since the old code
    classified it as a definite "empty", not "missing"/"unjudgeable",
    so the probe-sample mechanism never even saw it): a non-empty
    string `content` now WINS over empty-looking `filenames`/
    `numFiles` -- checked and short-circuited BEFORE that branch, not
    after. An EMPTY (or absent) `content` falls through to the
    filenames/numFiles branch UNCHANGED, so a genuinely empty
    files_with_matches-mode Grep/Glob result still classifies as
    "empty" exactly as before -- this is a strictly ADDITIVE fix, not a
    behavior change for any case this file's own existing tests already
    covered.

    Recognized dict shapes, checked in this order:
      - "stdout" key present (a Bash-shaped response): empty iff
        stdout is a string and, stripped, is empty. stderr is IGNORED
        entirely -- a command that found nothing on stdout but printed
        a warning to stderr is still an empty search result.
      - "content" present as a NON-EMPTY str: nonempty, unconditionally
        -- wins over filenames/numFiles below (see "CONTENT/COUNT-MODE
        FALSE-POSITIVE FIX" above).
      - "filenames" and/or "numFiles" present (a Grep/Glob-shaped
        response): empty iff numFiles == 0 or filenames == [].
      - "content" present as a str (now known empty, from the check
        above): empty.
    A dict with none of these keys is "unjudgeable" -- its shape is
    unknown, and guessing would repeat the exact mistake this fix
    corrects (silently treating an unrecognized shape as non-empty and
    never warning, and never leaving evidence either).

    None (no result key found under any of the plausible names) is
    "missing". Every non-dict, non-None value falls back to the
    original text-based check via `_as_text` + `_is_empty_text`
    (unchanged behavior for plain string results, the well-understood
    common case)."""
    if result is None:
        return "missing"
    if isinstance(result, dict):
        if "stdout" in result:
            stdout = result.get("stdout")
            if isinstance(stdout, str) and stdout.strip() == "":
                return "empty"
            return "nonempty"

        content = result.get("content")
        content_is_str = isinstance(content, str)
        if content_is_str and content.strip() != "":
            return "nonempty"

        if "filenames" in result or "numFiles" in result:
            num_files = result.get("numFiles")
            filenames = result.get("filenames")
            if num_files == 0 or filenames == []:
                return "empty"
            return "nonempty"

        if content_is_str:
            return "empty"

        return "unjudgeable"
    text = _as_text(result)
    if text is None:
        return "missing"
    return "empty" if _is_empty_text(text) else "nonempty"


def _write_sample_once(raw):
    """Writes the raw payload to _sample_path(), once only (same guard
    as before: skip if the file already exists). Never raises -- a
    write failure (missing logs/ directory unwritable, disk full) must
    not turn a WARN-mode hook into a crash."""
    try:
        path = _sample_path()
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(raw[:20000])
    except Exception:
        pass


def _session_id(payload):
    """The literal `session_id` key only -- deliberately not a list of
    guessed aliases (module docstring, ledger section). Returns the
    string value if present, else None."""
    if isinstance(payload, dict):
        value = payload.get("session_id")
        if isinstance(value, str) and value:
            return value
    return None


def _extract_term(tool_name, tool_input_raw, command_fallback):
    """Search-term extraction for the ledger, per spec: Grep/Glob take
    the pattern/path from tool_input; Bash AND PowerShell (this
    template's adaptation -- see module docstring "ORIGIN") take the
    WHOLE command string verbatim (no attempt to parse the term out --
    half B does substring matching against it). Falls back to a
    stringified tool_input when nothing more specific is found, so a
    ledger line is never silently empty for an observed search."""
    if tool_name in ("Bash", "PowerShell"):
        if isinstance(tool_input_raw, dict):
            cmd = tool_input_raw.get("command")
            if isinstance(cmd, str) and cmd:
                return cmd
        return command_fallback
    if tool_name in SEARCH_TOOLS and isinstance(tool_input_raw, dict):
        for key in ("pattern", "path", "glob"):
            value = tool_input_raw.get(key)
            if isinstance(value, str) and value:
                return value
    return command_fallback


def _extract_examine_term(tool_input_raw):
    """D4a: the file path a Read call examined, checked under a
    few plausible key spellings (same probe-friendly philosophy as the
    rest of this file). None when unextractable -- callers must not
    write a ledger line with no term."""
    if isinstance(tool_input_raw, dict):
        for key in ("file_path", "path", "filePath", "file"):
            value = tool_input_raw.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _compact_ledger_lines(existing_lines):
    """Keeps only the TAIL -- the last LEDGER_COMPACT_THRESHOLD_LINES
    of *existing_lines* (raw strings, one per line, already stripped of
    blank entries by the caller) -- see the module-level constant's own
    docstring comment for the rationale (FIFO tail-keep, not a
    liveness/TTL filter)."""
    return existing_lines[-LEDGER_COMPACT_THRESHOLD_LINES:]


def _append_ledger_line(payload, tool_name, term, is_empty, raw):
    """Appends one JSON line to the session ledger for an observed
    search OR examination (D4a widened this from "search only").
    Wrapped by the caller in its own try/except -- see `_process` --
    so a ledger failure never affects exit code or the empty-search
    warning.

    Compacts the ledger file AT WRITE TIME when it has grown past
    LEDGER_COMPACT_THRESHOLD_LINES -- see that constant's own docstring
    comment for the boundary contract (500 -> plain append; 501 ->
    compact-then-append) and the tail-keep rationale. Applies
    identically to a session-specific file AND to unknown.jsonl -- no
    special-casing between them."""
    session = _session_id(payload)
    if session is None:
        session = "unknown"
        # session_id could not be found under its expected key -- record
        # the raw payload once (existing once-only mechanism) so the
        # real key name can be fixed from evidence, not another guess.
        _write_sample_once(raw)

    line = json.dumps(
        {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "tool": tool_name,
            "term": term,
            "empty": bool(is_empty),
        },
        ensure_ascii=False,
    )

    ledger_dir = _ledger_dir()
    os.makedirs(ledger_dir, exist_ok=True)
    ledger_path = os.path.join(ledger_dir, session + ".jsonl")

    existing_lines = []
    if os.path.isfile(ledger_path):
        with open(ledger_path, "r", encoding="utf-8") as fh:
            existing_lines = [ln for ln in fh.read().splitlines() if ln.strip()]

    if len(existing_lines) > LEDGER_COMPACT_THRESHOLD_LINES:
        kept_lines = _compact_ledger_lines(existing_lines)
        with open(ledger_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(kept_lines) + "\n" + line + "\n")
    else:
        with open(ledger_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def _process(payload, raw):
    """All payload-dependent logic, called from inside main()'s single
    fail-open try/except (D3) -- no exception raised here can
    turn this WARN-mode hook into a non-zero exit."""
    tool_name = _as_text(_first(payload, ("tool_name", "toolName", "tool"))) or ""
    tool_input_raw = _first(payload, ("tool_input", "toolInput", "input", "parameters"))
    tool_input = _as_text(tool_input_raw)
    raw_result = _first(
        payload,
        ("tool_output", "toolOutput", "tool_response", "toolResponse",
         "output", "result", "response"),
    )

    state = _classify_result(raw_result)
    # A CLASSIFICATION FIX: classification reads ONLY the command string
    # (or SEARCH_TOOLS membership), NOT the whole serialized tool_input
    # (which `tool_input` above still is, kept for _extract_term's own
    # unrelated fallback use below) -- see
    # _command_text_for_classification's own docstring.
    command_text = _command_text_for_classification(tool_name, tool_input_raw)
    is_search = _looks_like_search(tool_name, command_text)

    # Record every OBSERVED search to the session ledger, before any of
    # the existing sample/warn logic below. Wrapped so a ledger failure
    # never suppresses the empty-search warning.
    if is_search and tool_name:
        try:
            term = _extract_term(tool_name, tool_input_raw, tool_input)
            _append_ledger_line(payload, tool_name, term, state == "empty", raw)
        except Exception:
            pass
    elif tool_name in EXAMINE_TOOLS:
        # D4a: a Read is a positive control for the read file's own
        # existence, exactly like a search -- recorded the same way.
        try:
            term = _extract_examine_term(tool_input_raw)
            if term:
                _append_ledger_line(payload, tool_name, term, state == "empty", raw)
        except Exception:
            pass

    # Schema unknown, original case: neither tool_name nor result could
    # be found at all -- record the payload once so the key list can be
    # fixed from evidence rather than from another guess, then stop
    # (there is nothing else this hook can determine from this payload).
    if not tool_name and state == "missing":
        _write_sample_once(raw)
        return

    # Widening: tool_name IS present and the tool/command looks like a
    # search, but the result is missing or of an unrecognized shape --
    # this is exactly the case that used to pass silently forever with
    # no evidence ever landing (module docstring, earlier fix, point 1).
    if is_search and state in ("missing", "unjudgeable"):
        _write_sample_once(raw)

    if is_search and state == "empty":
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": MSG,
                    }
                },
                ensure_ascii=False,
            )
        )


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _read_stdin_bytes():
    """Reads stdin as raw bytes, but ONLY when stdin is not a TTY (same
    guard and rationale as tools/hygiene_gate.py's `_read_stdin_bytes`):
    a PostToolUse hook receives the harness's JSON on stdin, piped; a
    human running this script by hand from an interactive shell has no
    piped input, and blocking on a read there would hang forever.
    D3: this REPLACES an earlier bare `sys.stdin.read()`, which
    read stdin in TEXT mode via Python's default codec and had no
    surrounding try/except -- invalid UTF-8 on stdin under a
    UTF-8-locked locale (PYTHONIOENCODING=utf-8) raised
    UnicodeDecodeError and exited 1, breaking the "exit 0 always"
    contract this docstring documents everywhere else. Superseded by
    `_read_stdin_bytes_deadline()` below -- kept only
    as a documented predecessor, no longer called from `main()`."""
    if sys.stdin.isatty():
        return b""
    return sys.stdin.buffer.read()


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
# exiting cleanly. main() itself is UNCHANGED (still a plain
# `return 0`, safe in-process); only the actual __main__ script-exit
# path below escalates to os._exit().
_STDIN_DEADLINE_STATE = {"hit": False}


def main():
    """The ONE fail-open try/except boundary for the whole script
    (D3, mirrors tools/hygiene_gate.py's and this delivery's own
    tools/claim_control_gate.py's main()): WARN mode is absolute
    -- exit 0 on every path, including a TTY with nothing piped in,
    malformed stdin, invalid UTF-8 bytes, a non-dict payload, or any
    unexpected exception anywhere in `_process` (ledger I/O, sample
    I/O, the warn print). Never raises, never returns non-zero. P4: the
    former `_read_stdin_bytes()` is replaced by the deadline helper
    above; on a stdin deadline `_process` is deliberately NOT called
    (named deviation from the empty-input path, which DOES call
    `_process({}, "")` and writes the schema-sample warning)."""
    try:
        _reconfigure_stdout_utf8()
        raw_bytes, timed_out = _read_stdin_bytes_deadline()
        if timed_out:
            _STDIN_DEADLINE_STATE["hit"] = True
            sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
            return 0
        raw = raw_bytes.decode("utf-8", errors="replace") if raw_bytes else ""
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            payload = {}
        _process(payload, raw)
    except Exception:
        pass
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
