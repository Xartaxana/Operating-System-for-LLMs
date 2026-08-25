"""journal_echo.py -- PostToolUse hook that echo-validates the FRESH
(just-written-to-disk) state of logs/routing-log.jsonl immediately
after any tool call whose tool_input carries a path to this file. This
closes a class of defect: the pre-commit gate only sits on the COMMIT
path, so a session that never commits never meets the validator at
all. A journal defect is now visible to the coordinator at write time,
not only for the minority of sessions that reach a git commit.

REUSE BY IMPORT, not subprocess, not copy-paste (the same standard this
toolkit's other hooks hold each other to, see tools/tier_echo.py /
tools/dod_track.py, neither of which imports the other).
journal_validator.decide(staged_text, head_text, now) is the ONLY
function this hook calls on the validator: it already does exactly
what's needed -- new lines = the lines on disk beyond the HEAD prefix,
validate ONLY those, seeding state from HEAD the same way the
pre-commit gate does. Calling decide() as a whole, rather than pulling
its internals apart by hand, is the most direct form of reuse (not a
reimplementation of its insides). Side effect (deliberately wanted, not
just tolerated): append-only violations (editing an existing journal
line) are caught by this same call for free, since decide() already
does that check as its first step.

STANDALONE FALLBACK: "git unavailable / not a repo / an error" --
including the case where git WORKS but the file isn't on HEAD yet (a
new, never-committed journal) -- all of these reduce to one case:
head_text = None. journal_validator.decide(disk_text, None, now)
already behaves like a standalone run in that case: split_lines(None)
yields [], append-only passes vacuously against an empty head, and
validate_new_lines treats EVERY line on disk as "new". No separate
standalone function is needed here -- it's the same decide() call with
head_text=None, not a different logic branch.

TRIGGER: tool_input.file_path (extraction method: literally
`tool_input.get("file_path")`, with no additional filtering by
tool_name -- the trigger is defined purely by a path-tail match, not by
a list of edit tools). The tail is normalized for both separator styles
('/' and '\\\\') and compared component-wise against ("logs",
"routing-log.jsonl") -- not a substring check (otherwise
"xlogs/routing-log.jsonl" or "logs/not-routing-log.jsonl" would falsely
match).

REPO ROOT: parent.parent of file_path -- the directory that CONTAINS
logs/, regardless of where journal_echo.py itself and its calling hook
happen to sit; the root need not match the calling process's cwd (a
PostToolUse hook can run from any cwd) -- hence `git -C <root>`, not a
bare `git show` from the current directory.

Git call: `git -C <root> show HEAD:logs/routing-log.jsonl` -- success
gives stdout = the file's HEAD content, returncode 0; the file missing
on HEAD gives returncode 128 + "fatal: path ... does not exist in
'HEAD'"; a non-git directory gives returncode 128 + "fatal: not a git
repository"; a nonexistent directory gives returncode 128 + "fatal:
cannot change to ...". All error forms give a non-zero returncode --
the only branch the code needs: returncode == 0 -> use stdout as
head_text, otherwise -> head_text = None (see "STANDALONE FALLBACK"
above). One subprocess call, timeout=5s -- FileNotFoundError (the git
binary is missing) and subprocess.TimeoutExpired are caught by the same
block, also yielding None.

PERFORMANCE: the file is read from disk exactly ONCE (disk_text), git
is called exactly ONCE (_get_head_text), decide() itself does one
linear pass over the new lines. None of these operations repeat
anywhere on main()'s path.

OUTPUT: clean -> COMPLETE SILENCE (neither stdout nor stderr) -- don't
add noise to every clean write. Defects present -> a line of the form
"JOURNAL ECHO: N defect(s) in new lines: <msg1>; <msg2>; <msg3>[; +K
more]" (the first 3 validator messages joined with "; "; if there are
more than 3, "; +K more" is appended, K = N-3 -- see build_context())
goes out on BOTH channels, but with different dynamic-content handling:

 - stdout: JSON {"hookSpecificOutput": {"hookEventName": "PostToolUse",
   "additionalContext": "<string, RAW, non-ASCII left untouched>"}} --
   the channel confirmed to actually reach the coordinator (the same
   channel hygiene_gate.py uses). json.dumps(..., ensure_ascii=True)
   itself escapes any non-ASCII into safe \\uXXXX sequences on the
   wire; after json.loads() on the reader's side the text comes back
   readable -- so an ASCII-replace pass here would only degrade
   readability for no safety benefit.
 - stderr: plain text (NOT JSON, no \\u-escaping) -- a duplicate,
   written directly into this machine's console stream, where an
   ASCII-replace pass on the dynamic part is still required (some
   console codepages are not UTF-8).

In BOTH variants: the static English prefix/suffix ("JOURNAL ECHO: N
defect(s) in new lines: ", "; +K more") is a literal, never passed
through either sanitizer -- see build_context(). Sanitizing (in both
forms) applies ONLY to the dynamic part -- each inserted validator
message individually, BEFORE the join.

LOCAL COPIES of _raw_sanitize/_ascii_sanitize (not an import of
tier_echo -- every hook script in this toolkit is self-contained along
this dimension; the only explicit exception to self-containment in
this file is the journal_validator import, which is required by
design). MAX_MESSAGE_LEN=500 applies to EACH message item
INDIVIDUALLY (not to the final joined line), in BOTH variants --
larger than tier_echo's 80 (a validator message is typically longer
than a single model name), but still a finite ceiling -- an adversarial
guard against a giant field value ending up inside a violation message
via repr().

FAIL-OPEN (everywhere): any stdin-JSON parse failure, a non-dict
payload, a missing/non-string/non-journal file_path, a file that
doesn't open from disk -- all of these silently exit 0, neither channel
touched. One outer try/except around the whole of main() -- exit 0 on
ANY unexpected exception (the same principle as every hook in this
toolkit).

WITNESS ECHO at write time (this port's second extension): cross-checks
the `witness` field of a NEW `accepted`+agent=builder journal line
against the runs actually OBSERVED in the current session's own DoD
track (.claude/dod_track/<session_id>.json, written by
tools/dod_track.py -- read here only, by a LOCAL copy of its track-path
formula, never imported: the same hook self-containment principle this
file's module docstring already documents for _raw_sanitize/
_ascii_sanitize; journal_validator and tier_echo stay the only declared
import exceptions). Trigger: in the SAME new_lines/head_lines that TIER
ECHO already computes above, a line with event=="accepted",
agent=="builder", and a non-empty `witness` string.

Outcomes (per matching line):
 - notes contains "retroactive" -> silent (a retro-accepted witness is
   not comparable to the current session's own track by definition).
 - the current session's track is empty/unreadable (no file, empty
   file, broken JSON, not an object, "runs" missing/not a list) ->
   silent (nothing to compare against; not a violation).
 - the track is non-empty but NONE of its distinct normalized commands
   occur as a substring of the normalized witness text -> a soft
   warning (legitimate for a batch/cross-session/retro acceptance --
   verify manually).
 - a track command DOES occur in the witness text, and that command's
   LATEST run (by ts) was recorded "red" -> a loud warning naming the
   command and its last-red ts, once per such command.
 - a track command occurs in the witness text and its latest run was
   "green" -> complete silence on that line (same principle as TIER
   ECHO's "every measured model carries the word").
Normalization (for both the track command and the witness text, before
the substring check): every run of whitespace collapsed to one space
plus a strip -- so a witness text reflowed/wrapped differently from
the exact command still matches.

Ceiling: at most MAX_WITNESS_LINES=5 visible (warn_soft/warn_loud/
warn_stale) lines per hook call, "+K more" on top -- the same
independent-axis ceiling pattern as MAX_TIER_LINES, guarding the same
head_text=None ("new_lines = the whole file") scenario. The track is
read lazily and at most ONCE per hook call (session_id is shared by
every line in one PostToolUse event).

This extension shares main()'s outer try/except AND has its own local
try/except around the collection call, so a failure inside the
witness cross-check can never take down TIER ECHO or the form-defect
check running alongside it in the same call.

WITNESS ECHO STALENESS: a SECOND,
INDEPENDENT axis on top of the outcome lattice above -- a witness can
honestly cite a command whose LATEST run was green (outcome 5, silent
on that axis) and the session's track can STILL carry a code edit
LATER than that green run with no re-run since -- the same invariant
tools/dod_gate.py.evaluate() already enforces at SubagentStop ("the
last edit is before the last green run"), checked again here, at
write time, over the WHOLE session track (any agent_id, not just the
one filed on this journal line). Trigger: the track carries at least
one non-doc-only edit (`.claude/dod_track/<session_id>.json`'s "edits"
list, read the same lazy-once-per-call way as "runs") AND either no
green run exists at all, or the latest edit's ts is strictly later
than the latest green run's ts -- ("warn_stale", line_no, last_edit_ts,
last_green_ts_or_None), independent of (and additional to) whichever
of outcomes 3/4/5 above the SAME line also produced: a line can be
BOTH "matched, latest green" (silent on the command-match axis) AND
"warn_stale" (loud on the staleness axis) at the same time.

Doc-only edits (.md/.json/.jsonl, plus .gitignore/.gitattributes/
.editorconfig -- the SAME extension list tools/dod_gate.py's own
doc-only exemption uses, mirrored here as a local copy, not imported)
are EXCLUDED from "last edit" -- without this exemption, the Edit/
Write call that writes THIS accepted line into routing-log.jsonl
(itself a .jsonl file) would make itself its own "latest edit",
falsely staling every batched accepted line. An edit record with no
file_path (an old track, or a payload missing the field) is
conservatively treated as NOT doc-only (counted toward "last edit") --
missing information does not earn an exemption, the same fail-safe
default this whole file already applies elsewhere.

TS DRIFT ECHO at write time: the third
independent echo layer, closing a gap discipline alone was carrying
(a finding: a timestamp taken from the session's own narrative rather
than the clock): "ts is read from the system clock immediately before
writing, never narrated" is checked at COMMIT time by journal_validator (a
monotonicity + "not more than 10 minutes in the future" rule), but by
commit time an event is already legitimately old (batch
cadence: events accumulate in session memory and are written to disk
in one block at the end of a stage, the commit can follow hours
later) -- drift-from-the-clock-right-now is not meaningfully
checkable at commit time at all. The one moment where "is this ts
fresh against the clock RIGHT NOW" is meaningful is the moment the
line lands on disk -- this hook's own invocation -- so this check
lives HERE, not in journal_validator. Two independent thresholds (own
engineering decision, same class as MAX_TIER_LINES/MAX_WITNESS_LINES):
TS_FUTURE_TOLERANCE_SECONDS=120 (2 minutes -- headroom for ordinary
process jitter between reading the clock and this hook actually
running, well under journal_validator's own 10-minute hard limit, so
this layer warns EARLIER and on SMALLER drift than the hard gate) and
TS_STALE_TOLERANCE_SECONDS=1800 (30 minutes -- headroom for a
LEGITIMATE batch: the ts is read once "immediately before writing the
BATCH", and the batch itself may have sat in session memory for a
while before the actual disk write; half an hour is the rough order
of magnitude of one work stage -- a drift LARGER than that suggests
the ts was not, in fact, read from the clock right before writing,
which is worth flagging even under batch discipline). Both thresholds
are strict (`>`, not `>=`) -- exactly at the boundary stays silent.
Ceiling: MAX_TS_DRIFT_LINES=5 lines per hook call, "+K more" on top --
the same class of ceiling as MAX_TIER_LINES/MAX_WITNESS_LINES, guarding
the same head_text=None ("new_lines = the whole file") scenario;
without it, one missed git init on a repo with a journal already
hundreds of lines long would blow additionalContext up to hundreds of
TS DRIFT lines in one call. Warn-only, always visible (no silent
"note" branch, unlike WITNESS ECHO).

Both new layers share the payload-scoped echo base with TIER ECHO/
WITNESS ECHO (see "PAYLOAD-SCOPED ECHO BASE" below) -- a line already
evaluated by an earlier hook call is never re-evaluated by a later
one, for staleness OR for ts drift.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import journal_validator  # noqa: E402
import tier_echo  # noqa: E402  -- TIER ECHO at write time (this port's extension):
# imports iter_transcript_models/count_models (the measurement, with its
# synthetic-line filter already built in) AND KNOWN_TIER_WORDS (the
# shared tier-word vocabulary), reused BY IMPORT, not copy-paste, the
# same principle as the journal_validator import above. journal_echo.py
# and tier_echo.py are DIFFERENT hooks (PostToolUse vs SubagentStop),
# but this cross-hook import is a deliberate, sanctioned exception to
# the general hook self-containment principle, alongside
# journal_validator.

JOURNAL_TAIL = ("logs", "routing-log.jsonl")
GIT_TIMEOUT_SECONDS = 5
MAX_MESSAGE_LEN = 500
MAX_HEAD_MESSAGES = 3

# --- TIER ECHO at write time (this port's extension) --------------------
# Trigger: a NEW journal line with an event in TIER_TRIGGER_EVENTS AND a
# worker_ref shaped like "agent:<id>" (id = [a-z0-9-]+, the WHOLE
# string -- fullmatch, not a prefix) -- only then is it worth looking
# for the subagent's transcript (a worker_ref like cli:.../retro:...
# does not reference a subagent file at all -- skipped without warning,
# see _collect_tier_events).
TIER_TRIGGER_EVENTS = {"delegated", "accepted", "rejected", "escalated"}
AGENT_WORKER_REF_RE = re.compile(r"^agent:([a-z0-9-]+)$")
# Ceiling on TIER ECHO lines per hook call -- independent of
# MAX_HEAD_MESSAGES (that one caps form-defect messages at 3; this one
# caps tier lines at 5, an independent axis).
MAX_TIER_LINES = 5

# --- WITNESS ECHO at write time (this port's second extension) ---------
WITNESS_TRIGGER_EVENT = "accepted"
WITNESS_TRIGGER_AGENT = "builder"
# Ceiling on VISIBLE WITNESS ECHO lines per hook call -- independent
# axis from MAX_HEAD_MESSAGES (3) and MAX_TIER_LINES (5); same class of
# ceiling, same rationale (head_text=None makes new_lines the whole
# file -- an unbounded additionalContext otherwise).
MAX_WITNESS_LINES = 5
# Silent-note literals (never printed -- see build_witness_segment):
# returned from _collect_witness_events purely for testability of the
# outcome lattice.
NOTE_RETRO = "retro accepted - track incomparable"
NOTE_TRACK_EMPTY = "track empty/unreadable - witness incomparable"

# --- WITNESS ECHO STALENESS --------------------------------------------
# Mirror of tools/dod_gate.py.DOC_ONLY_EXTENSIONS/DOC_ONLY_DOTFILES --
# the SAME list, a LOCAL copy (not an import -- dod_gate.py stays
# outside this hook's self-containment boundary, the same principle the
# module docstring already applies to _raw_sanitize/_ascii_sanitize).
# A divergence between this list and dod_gate.py's own is its own class
# of pair defect (fix the class, not the instance) -- editing either
# list edits both in the same move.
DOC_ONLY_EXTENSIONS = {".md", ".json", ".jsonl"}
DOC_ONLY_DOTFILES = {".gitignore", ".gitattributes", ".editorconfig"}


def _is_doc_only_edit_path(file_path) -> bool:
    """Mirror of tools/dod_gate.py._is_doc_only_file -- the same logic:
    an unknown/empty/non-string file_path -> False (conservatively NOT
    doc-only -- missing information does not earn an exemption from
    "code edit", the same fail-safe principle dod_gate/dod_track
    already apply for their own doc-only/scratchpad exemptions); a
    dotfile in DOC_ONLY_DOTFILES -> True; otherwise the extension
    (case-insensitive) in DOC_ONLY_EXTENSIONS. .jsonl is in this list --
    covers BOTH logs/routing-log.jsonl itself (the very Edit/Write call
    writing THIS accepted line would otherwise stale itself) and any
    other .jsonl anywhere in the repo, with no separate, narrower
    "journal-specific" criterion needed."""
    if not isinstance(file_path, str) or not file_path:
        return False
    path = Path(file_path)
    if path.name.lower() in DOC_ONLY_DOTFILES:
        return True
    return path.suffix.lower() in DOC_ONLY_EXTENSIONS


# --- TS DRIFT ECHO at write time ----------------------------------------
# See the module docstring, "TS DRIFT ECHO at write time", for the full
# motivation and threshold rationale.
TS_FUTURE_TOLERANCE_SECONDS = 120
TS_STALE_TOLERANCE_SECONDS = 1800
# Ceiling on VISIBLE TS DRIFT ECHO lines per hook call -- symmetric with
# MAX_TIER_LINES/MAX_WITNESS_LINES above (the same three-collector
# class, the same head_text=None/new-lines-is-the-whole-file risk).
MAX_TS_DRIFT_LINES = 5


def _detect_ts_drift(ts, now: "datetime.datetime"):
    """Returns ("future", delta_seconds) | ("stale", delta_seconds) |
    None for one `ts` field value. Parsing is REUSED
    (journal_validator.parse_ts), not duplicated -- the same
    ISO-without-timezone format the validator already parses for its
    own rule 10. An unparseable/missing ts -> None -- fail-open: ts
    FORM is already caught separately as a form defect by
    journal_validator/JOURNAL ECHO, this layer doesn't duplicate that
    diagnosis.

    `now` is the same naive local datetime.datetime.now() as the
    journal's own ts convention (ISO, local time, no timezone) -- both
    sides of the comparison are naive, an aware/naive conflict is not
    possible.

    Thresholds are strict (`>`), not (`>=`) -- exactly at the boundary
    stays silent, symmetric for both future and stale."""
    parsed = journal_validator.parse_ts(ts) if isinstance(ts, str) else None
    if parsed is None:
        return None
    delta = (parsed - now).total_seconds()
    if delta > TS_FUTURE_TOLERANCE_SECONDS:
        return ("future", delta)
    stale_delta = -delta
    if stale_delta > TS_STALE_TOLERANCE_SECONDS:
        return ("stale", stale_delta)
    return None


def _collect_ts_drift_events(new_lines: list, head_lines: list, now: "datetime.datetime") -> list:
    """For EVERY new line (the same new_lines/head_lines TIER ECHO/
    WITNESS ECHO already use) with a parseable `ts` field --
    _detect_ts_drift. Per-line (not deduplicated by ts value -- several
    lines of one batch sharing an identical ts each produce their OWN
    independent result). Returns a list of (line_no, kind,
    delta_seconds).

    Fails open per line (the same pattern as _collect_tier_events/
    _collect_witness_events): a broken line's JSON -- try/except with
    `continue`, does not interrupt parsing the rest, does not crash the
    hook."""
    events = []
    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            result = _detect_ts_drift(obj.get("ts"), now)
            if result is None:
                continue
            kind, delta = result
            events.append((line_no, kind, delta))
        except Exception:
            continue
    return events


def _format_ts_drift_line(event: tuple) -> str:
    """Static ASCII literal + minimal dynamic content -- the same
    principle _format_tier_line/_format_witness_line already apply in
    this file. "line {N}" distinguishes several events of one batch
    sharing an identical ts when joined with "; " -- the same local
    pattern TIER ECHO/WITNESS ECHO already carry ("line N"). The only
    dynamic content here is integers (line_no, rounded drift seconds) --
    ASCII by construction, no sanitizer needed (unlike
    _format_witness_line, which interpolates real third-party track
    text)."""
    line_no, kind, delta = event
    seconds = int(round(abs(delta)))
    if kind == "future":
        return (f"TS DRIFT: line {line_no} event ts is {seconds}s in the FUTURE "
                 "(ts must be read from the system clock immediately before writing)")
    return (f"TS DRIFT: line {line_no} event ts is {seconds}s STALE "
            "(batch ts must still be read from the system clock right "
            "before writing the batch, not carried over from an earlier check)")


def build_ts_drift_segment(ts_drift_events: list, ascii_only: bool = False) -> str:
    """Assembles the TS DRIFT part of additionalContext -- joined with
    "; ", ceiling MAX_TS_DRIFT_LINES=5 lines per call with a "+K more"
    tail on top (the same pattern as build_tier_segment/
    build_witness_segment). ascii_only is accepted for signature
    uniformity with the other build_* functions and combine_context, but
    is actually a no-op here -- _format_ts_drift_line never inserts
    anything but integers, so there is no non-ASCII content to sanitize
    in either mode.

    An empty ts_drift_events -> "" (the caller treats an empty string as
    "no segment", same principle as the other build_* functions)."""
    if not ts_drift_events:
        return ""
    head = ts_drift_events[:MAX_TS_DRIFT_LINES]
    rest = len(ts_drift_events) - len(head)
    body = "; ".join(_format_ts_drift_line(ev) for ev in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


def _raw_sanitize(s: str, max_len: int = MAX_MESSAGE_LEN) -> str:
    """Control chars stripped and length capped at the same ceiling as
    _ascii_sanitize, but WITHOUT the ASCII replacement -- non-ASCII
    content (e.g. a validator message quoting a non-Latin field value)
    is left as-is. Used for the JSON additionalContext (the channel to
    the coordinator): json.dumps(ensure_ascii=True) itself escapes
    non-ASCII into safe \\uXXXX sequences on the wire, and after
    json.loads() on the reader's side the text comes back readable --
    an ASCII-replace pass here would be pure, needless degradation. It
    is needed only where text goes RAW (not JSON-escaped) into a
    console stream that may not be UTF-8, see _ascii_sanitize."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    return s[:max_len]


def _ascii_sanitize(s: str, max_len: int = MAX_MESSAGE_LEN) -> str:
    """Local copy of the tools/tier_echo.py._ascii_sanitize approach
    (same principle: strip control chars, replace non-ASCII, cap
    length) -- a copy, not an import, see the module docstring. Used
    ONLY for the stderr duplicate (plain text, not JSON-escaped --
    written directly into this machine's console stream)."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)
    s = s.encode("ascii", "replace").decode("ascii")
    return s[:max_len]


def _extract_file_path(payload: dict):
    """tool_input.file_path -- literally
    (`tool_input = payload.get("tool_input") or {}`; `.get("file_path")`),
    with no extra tool_name filter (see the module docstring,
    "TRIGGER")."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    file_path = tool_input.get("file_path")
    return file_path if isinstance(file_path, str) and file_path else None


def _is_journal_path(file_path: str) -> bool:
    """Normalized path tail == ("logs", "routing-log.jsonl"),
    component-wise (not a substring check) -- matches both path
    separator styles ('/' and '\\\\')."""
    normalized = file_path.replace("\\", "/")
    parts = [p for p in normalized.split("/") if p]
    return len(parts) >= 2 and tuple(parts[-2:]) == JOURNAL_TAIL


def _repo_root(file_path: str) -> Path:
    """Parent of the parent of file_path -- the directory containing
    logs/ (see the module docstring, literally)."""
    return Path(file_path).resolve().parent.parent


def _get_head_text(root: Path):
    """git -C <root> show HEAD:./logs/routing-log.jsonl -- ONE call,
    timeout ~5s. Returns stdout when returncode==0, otherwise None (see
    the module docstring for the empirics of all three error forms --
    not a repo, the file isn't on HEAD, the directory doesn't exist --
    returncode is always non-zero; FileNotFoundError/TimeoutExpired --
    also None).

    The "./" prefix on the colon-path makes it resolve relative to
    `-C <root>`'s own cwd -- WITHOUT it, bare "HEAD:<path>" resolves
    relative to the top of whatever git repo `root` sits inside, which
    silently diverges from cwd-relative resolution whenever `root` is
    a subdirectory of a larger repo rather than a repo root itself
    (see gateway/lead_replay.py's git_preimage docstring for the same
    class, verified empirically there)."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "show", "HEAD:./logs/routing-log.jsonl"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _projects_root() -> Path:
    """The root directory under which finished subagents' transcripts
    live (expanduser'd). A separate function (not an inline
    Path.home()) EXCLUSIVELY so it can be monkeypatched in tests, the
    same testability pattern as _get_head_text/subprocess.run above:
    the module-level function is swapped out, this machine's real
    Path.home() never participates in tests."""
    return Path.home() / ".claude" / "projects"


def _find_agent_transcript(agent_id: str):
    """Globs <projects_root>/*/*/subagents/agent-<id>.jsonl (two
    wildcard levels -- project slug, session id -- matching the real
    on-disk layout for finished-subagent transcripts). The FIRST match
    (an agent id is unique machine-wide -- ordering of the glob doesn't
    matter). Not found / any glob error (permissions, a broken path) --
    None -- the caller then silently skips the line (no measurement, no
    verdict; not a warning). This is the flat layout specifically; a
    workflow-style tool's deeper nesting
    (subagents/workflows/wf_*/agent-*.jsonl) is a known, documented
    neighbor this does not cover."""
    try:
        matches = list(_projects_root().glob(f"*/*/subagents/agent-{agent_id}.jsonl"))
    except Exception:
        return None
    return str(matches[0]) if matches else None


def _extract_declared_word(model):
    """The first (in tier_echo.KNOWN_TIER_WORDS order -- haiku/sonnet/
    opus/fable) tier word occurring as a case-insensitive SUBSTRING of
    the journal line's `model` field. This is NOT the same as
    tier_echo._extract_declared_tier (which requires a strict
    "word:" prefix in a dispatch description) -- here the source is the
    free-text `model` field (a self-declared tier, free-form by
    design), compared the same way tier_echo.build_line compares
    (`declared_tier in model.lower()`).

    None if model isn't a string/is empty, or if NO known word occurs
    as a substring -- the same fail-open logic as elsewhere: with no
    recognizable declared tier, neither MISMATCH nor the informational
    branch applies (both depend on an identified tier word from the
    model field) -- the line is silently skipped, the same way "no
    transcript found" is. Practically safe: `model` is already a
    REQUIRED field for every event in TIER_TRIGGER_EVENTS in
    journal_validator (MODEL_REQUIRED_EVENTS) -- its absence/invalidity
    is already caught as a separate form defect regardless of this
    branch."""
    if not isinstance(model, str) or not model:
        return None
    model_lower = model.lower()
    for word in tier_echo.KNOWN_TIER_WORDS:
        if word in model_lower:
            return word
    return None


def _collect_tier_events(new_lines: list, head_lines: list) -> list:
    """For each NEW line (the same new_lines that main() computes for
    decide(), see the module docstring) with an event in
    TIER_TRIGGER_EVENTS and a worker_ref shaped like "agent:<id>" --
    looks up the subagent's transcript, measures its models
    (tier_echo.iter_transcript_models + count_models, synthetic filter
    included), compares against the declared tier word from the model
    field. Returns a list of tuples (line_no, kind, declared_word,
    counts) -- kind in ("mismatch", "info"); a "full match" (every
    measured model carries the word) adds nothing (complete silence on
    that line). line_no uses the SAME formula as
    journal_validator.validate_new_lines (len(head_lines)+idx+1) -- the
    same line numbers form defects use in their own messages.

    Fails open per line: any failure (malformed JSON, a glob error, a
    transcript read failure, anything) -- a try/except around the body
    of ONE iteration, `continue` -- does not interrupt parsing the rest
    of the new lines, does not crash the hook (main()'s outer boundary
    is a second, coarser net)."""
    events = []
    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            event = obj.get("event")
            if event not in TIER_TRIGGER_EVENTS:
                continue
            worker_ref = obj.get("worker_ref")
            if not isinstance(worker_ref, str):
                continue
            m = AGENT_WORKER_REF_RE.match(worker_ref)
            if not m:
                continue
            agent_id = m.group(1)
            transcript_path = _find_agent_transcript(agent_id)
            if not transcript_path:
                continue
            models = list(tier_echo.iter_transcript_models(transcript_path))
            counts = tier_echo.count_models(models)
            if not counts:
                continue
            declared_word = _extract_declared_word(obj.get("model"))
            if declared_word is None:
                continue
            matched = [declared_word in mdl.lower() for mdl in counts]
            if not any(matched):
                events.append((line_no, "mismatch", declared_word, counts))
            elif not all(matched):
                events.append((line_no, "info", declared_word, counts))
            # else: every measured model carries the word -- complete silence on this line.
        except Exception:
            continue
    return events


def _format_measured(counts: dict, ascii_only: bool) -> str:
    """"<model>=<count>[, ...]" -- the same shape as
    tier_echo.build_line, but the sanitizer is chosen by channel (raw
    for stdout, ascii for stderr), same principle as build_context
    below."""
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    return ", ".join(f"{sanitize(model)}={count}" for model, count in counts.items())


def _format_tier_line(event: tuple, ascii_only: bool) -> str:
    """Literal formats:
      MISMATCH: "TIER ECHO: line N model='<declared>' vs measured
                 <model>=<count>[, ...] MISMATCH"
      informational: "TIER ECHO: line N measured <model>=<count>[, ...]"
    The literal's static parts are NOT sanitized (same principle as
    build_context); only the dynamic parts are sanitized (declared_word
    is always one of the 4 ASCII tier words, so sanitizing it is a
    no-op here but applied for uniformity; the measured model names are
    real transcript text, sanitizing them is required, same risk as
    tier_echo.build_line)."""
    line_no, kind, declared_word, counts = event
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    measured = _format_measured(counts, ascii_only)
    # Rule of three in both branches (what's wrong / what it risks / the
    # action, imperative verb) -- neither branch carried a verb before.
    if kind == "mismatch":
        return (f"TIER ECHO: line {line_no} declared tier '{sanitize(declared_word)}' "
                f"MISMATCH measured {measured} never confirm the declared tier - the "
                "worker may actually have run on a different model; check the tier and "
                "fix the record, or relaunch on the declared tier")
    return (f"TIER ECHO: line {line_no} declared tier '{sanitize(declared_word)}' "
            f"measured {measured} confirms it only partially - part of the transcript "
            "may have run on a different model; check the tier manually")


def build_tier_segment(tier_events: list, ascii_only: bool = False) -> str:
    """Assembles the TIER ECHO part of additionalContext from
    tier_events (at most MAX_TIER_LINES=5 lines per call, "+K more" on
    top -- the same pattern as build_context for form defects, an
    independent ceiling). An empty tier_events -> "" (an empty string,
    not None -- the caller checks its truthiness the same way it checks
    the violations list)."""
    if not tier_events:
        return ""
    head = tier_events[:MAX_TIER_LINES]
    rest = len(tier_events) - len(head)
    body = "; ".join(_format_tier_line(ev, ascii_only) for ev in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


def build_context(violations: list, ascii_only: bool = False) -> str:
    """"JOURNAL ECHO: N defect(s) in new lines: <first 3 messages>[; +K
    more]" (the literal). The static English prefix/suffix is never
    passed through a sanitizer (in either mode -- see the module
    docstring, "OUTPUT").

    ascii_only=False (the default -- used for the JSON
    additionalContext, the channel to the coordinator): each message
    item goes through _raw_sanitize (control chars stripped, length
    capped, but non-ASCII content stays readable -- json.dumps(
    ensure_ascii=True) itself escapes non-ASCII on the wire, the reader
    sees readable text after json.loads(); an ASCII-replace pass here
    would be needless degradation).

    ascii_only=True (used ONLY for the stderr duplicate, plain text not
    JSON-escaped, this machine's console stream): each message item
    goes through _ascii_sanitize (non-ASCII -> '?')."""
    n = len(violations)
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    head = [sanitize(v) for v in violations[:MAX_HEAD_MESSAGES]]
    rest = n - len(head)
    body = "; ".join(head)
    if rest > 0:
        body += f"; +{rest} more"
    return f"JOURNAL ECHO: {n} defect(s) in new lines: {body}"


def combine_context(violations: list, tier_events: list, witness_events: list = None,
                     ts_drift_events: list = None, escalation_events: list = None,
                     fallback_marker: str = "", *, notes_len_events: list = None,
                     r3_events: list = None,
                     ascii_only: bool = False) -> str:
    """One JSON additionalContext can carry form defects, TIER ECHO
    lines, WITNESS ECHO lines, TS DRIFT lines, ESCALATION lines, NOTES
    LEN lines, R3 MIRROR lines, and a fallback-base marker, joined by
    "; ". EIGHT INDEPENDENT segments -- build_context(violations) (as a
    whole, its own "JOURNAL ECHO: N defect(s)..." header unchanged),
    build_tier_segment(tier_events), build_witness_segment(
    witness_events), build_ts_drift_segment(ts_drift_events),
    build_escalation_segment(escalation_events),
    build_notes_len_segment(notes_len_events), build_r3_segment(
    r3_events), and fallback_marker -- joined with "; ", only when
    non-empty. Any subset empty -> the result is just the remaining
    non-empty segments, the JSON is still printed as long as at least
    one segment is non-empty. All empty -> "" -- the caller (main())
    treats an empty string as complete silence. ORDER is fixed:
    violations first (its "JOURNAL ECHO: N defect(s) in new lines: "
    header literal never changes), then tier/witness/ts-drift/
    escalation/notes-len/r3 in that order (r3_events is the LAST
    content segment, strictly before fallback_marker), fallback_marker
    LAST always -- no segment is a visibility condition for another,
    each makes the call visible on its own.

    fallback_marker -- a LITERAL (FALLBACK_MARKER_TEXT, see the
    "PAYLOAD-SCOPED ECHO BASE" section below), never sanitized (a
    static ASCII string, never third-party text -- same principle as
    build_context's static prefix). main() passes it as an empty
    string whenever TIER ECHO/WITNESS ECHO/TS DRIFT/ESCALATION did NOT
    degrade to the HEAD-diff fallback on this particular hook call (see
    _resolve_echo_base) -- so its absence in the old 2-/3-/4-positional
    call forms changes nothing.

    witness_events=None / ts_drift_events=None / escalation_events=None
    (default, NOT []) preserve every older call form (combine_context(
    violations, tier_events) through the 4-positional combine_context(
    violations, tier_events, witness_events, ts_drift_events))
    byte-for-byte: a None segment is "" exactly like an empty list, so
    every existing call/test using a shorter form is unaffected.
    escalation_events is a 5th positional parameter (BEFORE
    fallback_marker, which sits 6th) -- a prior edit of this file
    already established that shape; this task does not touch it.

    notes_len_events/r3_events are added STRICTLY KEYWORD-ONLY (after
    `*`, alongside ascii_only, which was already positional-or-keyword
    but in practice always called by name at every call site in this
    repo -- moving it past `*` too changes no existing call's
    behavior). Reason: a live pin test
    (test_journal_echo_escalation.py, test_combine_context_
    escalation_joined_with_fallback_marker) calls combine_context with
    SIX positional arguments, the sixth being the literal string
    "MARKER" as fallback_marker. Adding either new parameter as a
    further positional slot would silently turn that literal into
    notes_len_events on the next call sharing that arg count -- the
    test would either fail outright, or (worse) pass by accidental
    type coincidence. Keyword-only excludes this class of regression
    structurally: every existing 2-/3-/4-/5-/6-positional call in this
    repo stays byte-for-byte unchanged (see the pin test
    test_combine_context_six_positional_arg_form_unchanged in
    test_journal_echo_r3.py). notes_len_events/r3_events both default
    to None (not [] -- a None segment builds to "", identical to the
    parameter's absence)."""
    parts = []
    if violations:
        parts.append(build_context(violations, ascii_only))
    tier_segment = build_tier_segment(tier_events, ascii_only)
    if tier_segment:
        parts.append(tier_segment)
    witness_segment = build_witness_segment(witness_events or [], ascii_only)
    if witness_segment:
        parts.append(witness_segment)
    ts_drift_segment = build_ts_drift_segment(ts_drift_events or [], ascii_only)
    if ts_drift_segment:
        parts.append(ts_drift_segment)
    escalation_segment = build_escalation_segment(escalation_events or [], ascii_only)
    if escalation_segment:
        parts.append(escalation_segment)
    notes_len_segment = build_notes_len_segment(notes_len_events or [], ascii_only)
    if notes_len_segment:
        parts.append(notes_len_segment)
    r3_segment = build_r3_segment(r3_events or [], ascii_only)
    if r3_segment:
        parts.append(r3_segment)
    if fallback_marker:
        parts.append(fallback_marker)
    return "; ".join(parts)


# --- PAYLOAD-SCOPED ECHO BASE -------------------------------------------
# ROOT CAUSE / FIX / EMPIRICAL BASIS: TIER ECHO/WITNESS ECHO used to
# share ONE base with VALIDATION (HEAD-diff, cumulative across every
# PostToolUse call since the last commit), so a session appending lines
# across several tool calls without committing between them re-echoed
# the SAME already-reported event on every later call. The fix: derive
# the "new lines" base from the CURRENT tool call's OWN payload
# (tool_response.originalFile, empirically confirmed on BOTH Edit's and
# Write's Zod output schemas in the installed claude-code binary -- the
# full file content immediately BEFORE this specific tool call, string
# or null). DEFERRAL: this module carries NO ts-drift layer, and this
# section does not add one -- it only affects TIER ECHO/WITNESS ECHO;
# a sibling deployment's equivalent module fixes a TS DRIFT correctness
# bug with the identical base change, which does not apply here.
#
# FAIL-OPEN: tool_name outside {"Edit", "Write"}, a missing/malformed
# tool_response, an absent/wrongly-typed "originalFile" key, OR a
# recovered originalFile that disk_text does NOT extend as a strict
# append (a non-tail edit) -- ALL fall back to the SAME HEAD-diff
# computation this file used before this port (identical logic,
# unchanged) -- see _resolve_echo_base. The fallback is disclosed via
# FALLBACK_MARKER_TEXT, appended as combine_context's fourth segment --
# but ONLY when there is already something else to report (see main()):
# an otherwise-fully-clean call stays completely silent even in
# fallback, matching this file's pre-existing "no noise on a clean
# write" contract.
_ORIGINAL_FILE_UNAVAILABLE = object()
EDIT_LIKE_TOOL_NAMES = ("Edit", "Write")
FALLBACK_MARKER_TEXT = "echo base: HEAD-diff fallback"


def _extract_original_file(payload, tool_name):
    """tool_response.originalFile -- see the section docstring above.
    Returns _ORIGINAL_FILE_UNAVAILABLE when tool_name isn't Edit/Write,
    or tool_response isn't a dict, or the "originalFile" key is absent,
    or present with a type that's neither str nor None; "" when
    originalFile is None (a brand-new file); the string itself
    otherwise."""
    if tool_name not in EDIT_LIKE_TOOL_NAMES:
        return _ORIGINAL_FILE_UNAVAILABLE
    tool_response = payload.get("tool_response") if isinstance(payload, dict) else None
    if not isinstance(tool_response, dict):
        return _ORIGINAL_FILE_UNAVAILABLE
    if "originalFile" not in tool_response:
        return _ORIGINAL_FILE_UNAVAILABLE
    original_file = tool_response["originalFile"]
    if original_file is None:
        return ""
    if not isinstance(original_file, str):
        return _ORIGINAL_FILE_UNAVAILABLE
    return original_file


def _resolve_echo_base(payload, tool_name, staged_lines: list, head_lines: list):
    """Returns (echo_base_lines, echo_new_lines, used_fallback) -- the ONE
    base shared by TIER ECHO/WITNESS ECHO here (VALIDATION/
    JOURNAL ECHO stays on the separate, cumulative HEAD-diff base -- see
    main()). See the section docstring above for the primary/fallback
    logic."""
    original_file = _extract_original_file(payload, tool_name)
    if original_file is not _ORIGINAL_FILE_UNAVAILABLE:
        base_lines = journal_validator.split_lines(original_file)
        op_ok, _ = journal_validator.check_append_only(staged_lines, base_lines)
        if op_ok:
            return base_lines, staged_lines[len(base_lines):], False
    append_ok, _ = journal_validator.check_append_only(staged_lines, head_lines)
    new_lines = staged_lines[len(head_lines):] if append_ok else []
    return head_lines, new_lines, True


# ---------------------------------------------------------------------
# WITNESS ECHO at write time (this port's second extension) -- pure logic
# ---------------------------------------------------------------------


def _normalize_ws(s) -> str:
    """Collapses every run of whitespace (space/tab/newline) into a
    single space, then strips. Applied to BOTH the track's command
    string and the witness text before the substring comparison (a
    witness reflowed across lines still matches the recorded command).
    A non-string input -> "" (a safe default that never matches
    anything by substring)."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s).strip()


def _witness_track_path(cwd, session_id) -> Path:
    """.claude/dod_track/<session_id>.json under the calling session's
    cwd -- the SAME formula tools/dod_track.py uses for its own track
    file, reproduced locally (read-only) rather than imported: the
    hook self-containment principle this module's docstring already
    explains for _raw_sanitize/_ascii_sanitize. The track file's shape
    is a documented, stable contract between this toolkit's hooks, not
    an internal implementation detail of dod_track.py."""
    return Path(cwd or ".") / ".claude" / "dod_track" / f"{session_id}.json"


def _load_witness_runs(cwd, session_id):
    """Reads the current session's track "runs" list. Returns a list
    (possibly empty) on a successful read of a valid JSON object
    carrying a "runs" list field; None on ANY failure -- session_id not
    a non-empty string, no file, an empty/whitespace-only file, broken
    JSON, JSON not an object, or "runs" missing/not a list. The caller
    (_collect_witness_events) treats both None and an empty list the
    same way: "track empty/unreadable" -- there is nothing to compare
    the witness against either way."""
    if not isinstance(session_id, str) or not session_id:
        return None
    path = _witness_track_path(cwd, session_id)
    try:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return None
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        runs = data.get("runs")
        if not isinstance(runs, list):
            return None
        return runs
    except Exception:
        return None


def _load_witness_edits(cwd, session_id):
    """Reads the current session's track "edits" list (WITNESS ECHO
    STALENESS) -- structurally mirrors
    _load_witness_runs above (its OWN independent disk read, not a
    shared internal helper with it -- the same hook self-containment
    preference the module docstring already explains for the local
    _raw_sanitize/_ascii_sanitize copies: every track reader in this
    file is self-sufficient about reading, the only thing they share is
    the path formula, _witness_track_path). Returns a list (possibly
    empty) on a successful read; None on ANY failure (the same full set
    of failure modes as _load_witness_runs). The caller (_detect_staleness)
    treats both None and [] the same way: "no edits in the track to
    compare against"."""
    if not isinstance(session_id, str) or not session_id:
        return None
    path = _witness_track_path(cwd, session_id)
    try:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            return None
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        edits = data.get("edits")
        if not isinstance(edits, list):
            return None
        return edits
    except Exception:
        return None


def _last_edit_ts(edits: list):
    """The max ts among edits-records counted as a "code edit" (WITNESS
    ECHO STALENESS) -- the same lexicographic-==-chronological
    convention _last_by_ts already applies to runs (dod_track's ts
    values are fixed-width ISO with microseconds).

    Records whose file_path is doc-only (_is_doc_only_edit_path -- the
    mirror of tools/dod_gate.py._is_doc_only_file, the same extension
    list) are EXCLUDED from the max -- without this filter, the very
    Edit/Write call writing THIS accepted line into routing-log.jsonl
    (itself a .jsonl file, hence doc-only) would make itself the
    "latest edit", falsely staling every batched accepted line. A
    record with no file_path (None/non-string -- an old track, or a
    payload missing the field) is CONSERVATIVELY treated as NOT
    doc-only (_is_doc_only_edit_path(None) == False) -- counted as a
    code edit; missing information does not earn an exemption, the same
    fail-safe principle as the rest of this file.

    Records with a non-string "ts" (a corrupted third-party track entry)
    are also skipped -- a defensive default, does not break the max
    computation over the rest. Non-dict elements are skipped too. An
    empty/all-doc-only/all-broken edits list -> None (nothing to
    compare, see _detect_staleness)."""
    values = [e.get("ts") for e in edits
              if isinstance(e, dict) and isinstance(e.get("ts"), str)
              and not _is_doc_only_edit_path(e.get("file_path"))]
    return max(values) if values else None


def _last_green_ts(runs: list):
    """The max ts among runs-records with outcome=="green" (WITNESS
    ECHO STALENESS) -- the same defense against corrupted records as
    _last_edit_ts above. No green run at all (only red, or an entirely
    empty runs list) -> None."""
    values = [r.get("ts") for r in runs
              if isinstance(r, dict) and r.get("outcome") == "green"
              and isinstance(r.get("ts"), str)]
    return max(values) if values else None


def _detect_staleness(runs: list, edits: list):
    """WITNESS ECHO STALENESS: "the track's
    latest green run is dated AFTER the track's latest code edit" -- the
    SAME invariant tools/dod_gate.py.evaluate() already enforces at
    SubagentStop, checked again here at write time, over the whole
    session track (any agent_id -- not just the one filed on this
    journal line). See the module docstring, "WITNESS ECHO STALENESS",
    for the full comparison against dod_gate.py and what is deliberately
    NOT reused from it (per-agent filtering, the consecutive_blocks
    safeguard -- both are dod_gate.py's own acceptance-blocking POLICY,
    out of scope here).

    Returns None (silent -- the invariant holds, OR there is nothing to
    compare) | (last_edit_ts, last_green_ts_or_None) (violated --
    warn_stale, see _collect_witness_events).

    No edit at all in the track (last_edit_ts is None -- edits is
    empty/all-doc-only/all-broken/None) -> None with no further check --
    literally nothing to compare (the same "no data, no verdict"
    principle as the rest of this file).

    At least one edit: a violation is EITHER no green run at all in the
    track (last_green_ts is None) OR the latest edit strictly later than
    the latest green run (last_edit_ts > last_green_ts, a plain string
    comparison -- lexicographic ISO-with-microseconds, the same trick
    _last_by_ts already uses). An edit at EXACTLY the same ts as a green
    run (the boundary, in practice unreachable -- microsecond
    resolution makes a real collision vanishingly unlikely, but the
    strict `>` stays silent on equality anyway, symmetric with
    _detect_ts_drift elsewhere in this file) is NOT a violation -- a
    green run is not considered stale relative to an edit that happened
    no later than it."""
    last_edit_ts = _last_edit_ts(edits)
    if last_edit_ts is None:
        return None
    last_green_ts = _last_green_ts(runs)
    if last_green_ts is None or last_edit_ts > last_green_ts:
        return (last_edit_ts, last_green_ts)
    return None


def _group_runs_by_normalized_command(runs: list) -> dict:
    """{normalized_command: [(ts, outcome), ...]} over EVERY run in the
    track, of ANY agent_id (a builder subagent's run lives in the same
    <session_id>.json as the main thread's -- agent_id is not filtered
    here at all). A run with no usable command string (missing/empty
    after normalization) is skipped -- nothing to compare. A non-dict
    run entry (a corrupted track) is skipped silently. Grouping by
    DISTINCT command, not by individual run, keeps the later substring
    check to one probe per distinct command rather than one per run
    (a track with many repeats of the same verification command is the
    common case)."""
    groups: dict = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        norm = _normalize_ws(run.get("command"))
        if not norm:
            continue
        groups.setdefault(norm, []).append((run.get("ts"), run.get("outcome")))
    return groups


def _last_by_ts(entries: list):
    """The (ts, outcome) entry with the MAX ts among entries (a list of
    (ts, outcome) pairs, the shape _group_runs_by_normalized_command
    produces). dod_track.py's ts values are fixed-width ISO with
    microseconds, so plain string sorting is equivalent to chronological
    sorting here -- cheaper than parsing a real datetime for this
    purpose. A non-string/missing ts sorts as "" (a safe minimum that
    never wins "latest" over a real timestamp, without breaking the
    sort of the rest)."""
    def key(e):
        ts = e[0]
        return ts if isinstance(ts, str) else ""
    return sorted(entries, key=key)[-1]


def _match_witness(witness: str, runs: list):
    """For every DISTINCT normalized track command occurring as a
    substring of the normalized witness text, looks up that command's
    LATEST (by ts) run -- a "red" latest run is a candidate for a loud
    warning (outcome is a secondary signal here: determine_outcome's
    own safe default is "red" on an ambiguous run, so a red/green split
    alone does not yet mean "the witness lies" -- hence a WARN, never a
    hard block). Returns (matched_any: bool, loud: list[(cmd, ts)]).
    matched_any=False means the track was non-empty but no command in
    it occurs in the witness text at all -- the soft-warning case (see
    _collect_witness_events).

    Performance: exactly one substring probe per DISTINCT command in
    the track (after grouping), not one per individual run -- a track
    with hundreds of repeats of the same verification command collapses
    to one "in" check, not hundreds."""
    norm_witness = _normalize_ws(witness)
    groups = _group_runs_by_normalized_command(runs)
    matched_any = False
    loud = []
    for cmd, entries in groups.items():
        if cmd in norm_witness:
            matched_any = True
            ts, outcome = _last_by_ts(entries)
            if outcome == "red":
                loud.append((cmd, ts))
    return matched_any, loud


def _collect_witness_events(new_lines: list, head_lines: list, payload: dict) -> list:
    """For each NEW line (the same new_lines TIER ECHO already uses
    above) with event=="accepted", agent=="builder", and a non-empty
    `witness` string -- the outcome lattice:

      1. notes contains "retroactive" -> ("note", line_no, NOTE_RETRO):
         a retro-accepted witness is not comparable to the CURRENT
         session's own track by definition -- silent.
      2. the current session's track is empty/unreadable (see
         _load_witness_runs) -> ("note", line_no, NOTE_TRACK_EMPTY) --
         silent, not an exception.
      3. no track command occurs in the witness (matched_any=False) ->
         ("warn_soft", line_no) -- legitimate for a batch/cross-session/
         retro acceptance (verify manually).
      4. a matching command whose LATEST run was red -> ("warn_loud",
         line_no, command, ts), one entry per such command.
      5. otherwise (matched, latest run green) -> nothing added --
         complete silence on that line (same principle as TIER ECHO's
         "every measured model carries the word").
      6. (WITNESS ECHO STALENESS, INDEPENDENT of 1-5,
         see _detect_staleness): the track is non-empty (outcome 2 did
         not fire) AND carries at least one edit AND (no green run at
         all, OR the latest edit is LATER than the latest green run) ->
         ADDITIONALLY ("warn_stale", line_no, last_edit_ts,
         last_green_ts_or_None) -- orthogonal to outcomes 3/4: the
         SPECIFIC command cited in the witness can honestly match its
         own latest green run (outcome 5, silent on THAT axis) while
         the track as a whole still carries a LATER edit with no
         re-run since -- both axes print INDEPENDENTLY for one line
         when both fire.

    "note" events are NEVER printed (see build_witness_segment) --
    returned alongside warn events purely so the outcome lattice is
    directly testable.

    Fails open per line (same pattern as _collect_tier_events): any
    failure (malformed JSON, anything else) -- try/except around the
    body of ONE iteration, `continue` -- does not interrupt the rest
    of the new lines.

    The track is read LAZILY and AT MOST ONCE per hook call (session_id
    is shared across every line of one PostToolUse event) -- the same
    "read once" performance principle the module docstring documents
    for disk_text/git in main(). WITNESS ECHO STALENESS adds a SECOND,
    independent lazy-once cache for edits (_load_witness_edits) -- its
    own cache, not shared internal state with the runs cache (mirrors
    _load_witness_edits not being a shared helper with _load_witness_runs,
    see that function's own docstring)."""
    events = []
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    runs_loaded = False
    runs_cache = None
    edits_loaded = False
    edits_cache = None
    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            if obj.get("event") != WITNESS_TRIGGER_EVENT:
                continue
            if obj.get("agent") != WITNESS_TRIGGER_AGENT:
                continue
            witness = obj.get("witness")
            if not isinstance(witness, str) or not witness.strip():
                continue

            notes = obj.get("notes")
            if isinstance(notes, str) and "retroactive" in notes:
                events.append(("note", line_no, NOTE_RETRO))
                continue

            if not runs_loaded:
                runs_cache = _load_witness_runs(cwd, session_id)
                runs_loaded = True
            if not runs_cache:
                events.append(("note", line_no, NOTE_TRACK_EMPTY))
                continue

            # WITNESS ECHO STALENESS (outcome 6 above): computed IN
            # PARALLEL with the command matching below, not instead of
            # it.
            if not edits_loaded:
                edits_cache = _load_witness_edits(cwd, session_id)
                edits_loaded = True
            staleness = _detect_staleness(runs_cache, edits_cache or [])
            if staleness is not None:
                last_edit_ts, last_green_ts = staleness
                events.append(("warn_stale", line_no, last_edit_ts, last_green_ts))

            matched_any, loud = _match_witness(witness, runs_cache)
            if not matched_any:
                events.append(("warn_soft", line_no))
            else:
                for cmd, ts in loud:
                    events.append(("warn_loud", line_no, cmd, ts))
        except Exception:
            continue
    return events


def _format_witness_line(event: tuple, ascii_only: bool) -> str:
    """Static ASCII prefix "WITNESS ECHO: line N ..." plus dynamic
    content (command name, ts) run through the channel's sanitizer --
    same principle as _format_tier_line. ts from the track is dynamic
    too (a third-party JSON file's field value, not a literal of this
    module) and is sanitized symmetrically with cmd -- the "every
    dynamic part is sanitized" invariant this file already applies to
    _format_tier_line/_format_measured. In practice dod_track's
    _now_iso() output is always clean ASCII with no control chars, so
    sanitizing it here is a no-op in the ordinary case -- it exists to
    close the adversarial edge (a corrupted/foreign track with control
    chars or a giant ts value).

    "warn_stale" (WITNESS ECHO STALENESS): the track's
    ts values (last_edit_ts, and, if present, last_green_ts) are the
    SAME kind of third-party dynamic content as cmd/ts on warn_loud
    above, sanitized the same way. last_green_ts may be None (no green
    run at all in the track -- see _detect_staleness) -- rendered as
    the literal "none" (NOT sanitized -- a static ASCII literal of this
    module, not a value out of the track)."""
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    kind = event[0]
    line_no = event[1]
    # Rule of three in the warn_loud/warn_stale branches too (what's
    # wrong / what it risks / the action, imperative verb) -- warn_soft
    # already carried one ("verify manually").
    if kind == "warn_loud":
        _, _, cmd, ts = event
        return (f"WITNESS ECHO: line {line_no} contradiction - command "
                f"'{sanitize(cmd)}' recorded RED in session track at {sanitize(str(ts))} "
                "- this line's accepted witness may not be trustworthy; re-run the "
                "command and confirm it is green before relying on this acceptance")
    if kind == "warn_stale":
        _, _, last_edit_ts, last_green_ts = event
        green_part = sanitize(str(last_green_ts)) if last_green_ts is not None else "none"
        return (f"WITNESS ECHO: line {line_no} track staleness - last code edit at "
                f"{sanitize(str(last_edit_ts))} is after the last green run (last green: "
                f"{green_part}) - the witness predates the latest code change and may no "
                "longer match it; re-run the witness command after this edit and confirm "
                "it is green")
    # warn_soft
    return (f"WITNESS ECHO: line {line_no} witness command(s) not observed in "
            "session track - this acceptance cannot be confirmed automatically; verify "
            "manually that the witness is legitimate (batch/cross-session/retro "
            "acceptance is a valid reason)")


def build_witness_segment(witness_events: list, ascii_only: bool = False) -> str:
    """Assembles the WITNESS ECHO part of additionalContext -- ONLY
    from "warn_loud"/"warn_soft"/"warn_stale" events ("note" events are
    silent by definition, see _collect_witness_events); ceiling
    MAX_WITNESS_LINES (=5, boundary-tested at 5/6), same "+K more"
    pattern as build_tier_segment -- ONE shared ceiling across all
    visible kinds together (not a separate per-kind limit: one journal
    line can already produce several events of different kinds, see
    _collect_witness_events outcome 6, and this is not a NEW limit --
    MAX_WITNESS_LINES predates the staleness axis, only the list of
    kinds it counts is extended here). An empty visible-events list ->
    "" (the caller treats an empty string as "no segment", same
    principle as build_tier_segment)."""
    warn_events = [e for e in witness_events if e[0] in ("warn_loud", "warn_soft", "warn_stale")]
    if not warn_events:
        return ""
    head = warn_events[:MAX_WITNESS_LINES]
    rest = len(warn_events) - len(head)
    body = "; ".join(_format_witness_line(e, ascii_only) for e in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


# --- ESCALATION ECHO at write time --------------------------------------
# R6-escalation machine guard on the write path.
# GAP (R6, CLAUDE.md "Routing rules", rule 6 here): "two `rejected`
# events with the same task_id on the same tier make escalation
# mandatory" was held ONLY by discipline on the write path -- the ONLY
# existing detector was the WEEKLY CALIBRATION run (a journal-shaped
# check reading logs/routing-log.jsonl AFTER the fact, not at the
# moment the third same-tier retry actually gets written). This layer
# is a WARN, NOT a block (promotion to a hard block is a LATER step per
# the code-gates-execution clause, explicitly NOT this task -- NON-GOALS
# leave tools/journal_validator.py untouched): the same pattern TS
# DRIFT ECHO above already applies for the equivalent timestamp-drift
# case (warn at write time; a hard gate is a separate, coarser
# instrument, not engaged here).
#
# DETECTOR REGISTRATION (four-questions-per-mechanism rule, clause c):
# this layer's OWN failure detector is the deployment's weekly
# R6-escalation calibration check (CLAUDE.md rule 6 /
# PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md) -- a journal-shaped audit
# finding a same-tier third retry with
# no `escalated` event anywhere above it is exactly the case this WARN
# layer already flags at write time; a systematic miss here (a WARN
# that should have fired and didn't) would surface there as a case the
# calibration still had to catch post-hoc.
#
# TWO FORMS:
#  1. a new `delegated` line with a numeric `attempt` >= 3: if there is
#     NO `escalated` event with the same task_id anywhere above (base
#     history + already-processed lines of THIS same batch) -> WARN.
#  2. a new `delegated` line with NO `attempt` field at all, but whose
#     task_id already has >=2 `rejected` events above sharing the SAME
#     model, with no `escalated` event AFTER the second such rejected
#     -> the same WARN ("a retry that forgot to carry `attempt`").
#
# ONE SHARED DETECTOR (_escalation_group_unsatisfied): both forms
# reduce to ONE check -- grouping a task_id's known `rejected` events
# by model, ANY group of size >=2 with no `escalated` event recorded
# AFTER the SECOND (by line position) entry of that group is a
# violation. This naturally implements both legal exceptions (boundary
# tests on both sides -- see tools/test_journal_echo_escalation.py):
#  - "attempt>=3 with an escalated event already above" -- an
#    escalated event AFTER the group's second rejected clears it;
#  - "attempt=2" -- below the >=3 threshold, form 1 never triggers
#    (and form 2 doesn't either -- `attempt` IS present, just <3);
#  - "attempt>=3 with rejected events on DIFFERENT tiers" -- if the
#    task_id's rejected models never repeat (each occurs <2 times), NO
#    group ever reaches size 2 -- vacuously "nothing to warn about"
#    (the same mechanism silences form 2 too: without a matching model
#    pair its own trigger condition never finds a size->=2 group).
#
# EXCLUDED TRIGGERS (not retries -- CLAUDE.md's Routing log section,
# THREE legitimate forms of a REPEAT `delegated` on an open task):
# agent=="critic" (a critic entry) AND notes carrying
# "replaces_worker:<handle>" (journal_validator.extract_replaces_worker
# -- REUSED, the same formula the validator already applies for its
# own no-silent-reuse check, not hand-duplicated) -- neither is a
# retry, both forms of this layer skip such lines outright (see
# _check_delegated_retry).
#
# SOURCE OF "ABOVE" (spec: "consume ONLY the payload-scoped new lines
# as the TRIGGER; reading the file's history for CONTEXT is fine"):
# base_lines (payload-scoped -- see _resolve_echo_base; the primary
# path yields the FULL disk content immediately BEFORE this specific
# tool call, not just committed HEAD) PLUS the lines of THIS SAME batch
# already processed (new_lines[:idx]) -- ONE linear pass
# (_collect_escalation_events), a per-task_id state accumulated as it
# goes; a `delegated` line is checked against state accumulated
# STRICTLY BEFORE it (a `delegated` line itself never writes into
# state -- the update-vs-check order is irrelevant for it, but LATER
# lines of the SAME batch can still reference it if it happens to be
# `rejected`/`escalated`). "pos" is a plain, monotonically increasing
# integer line index of the single pass (base_lines, then new_lines) --
# comparing with ">" for "escalated AFTER the second rejected" needs no
# date parsing.
#
# NEVER BLOCKS (spec, literally: "exit 0, no permissionDecision"): this
# layer never changes main()'s exit code -- the WARN goes out on the
# SAME additionalContext/stderr channels as TIER/WITNESS/TS DRIFT (this
# file never prints permissionDecision at all -- see the module
# docstring, "OUTPUT").
#
# Fails open per line (the same pattern as _collect_tier_events/
# _collect_ts_drift_events): a broken line's JSON, a non-dict line --
# try/except with `continue` per line, does not interrupt parsing the
# rest of the batch, does not crash the hook.
MAX_ESCALATION_LINES = 5  # the same class of ceiling as MAX_TIER_LINES/
# MAX_WITNESS_LINES/MAX_TS_DRIFT_LINES above -- own engineering
# decision, the same number 5, the same motive (a standalone/large
# batch with no ceiling -> unbounded additionalContext on one hook
# call). Boundary-tested at 5/6 -- see
# tools/test_journal_echo_escalation.py.


def _escalation_group_unsatisfied(rejected: list, escalated: list) -> bool:
    """True -- for this task_id there IS at least one model-group of
    `rejected` events of size >=2 with no `escalated` event recorded
    AFTER the second (by position) entry of that group (see the section
    above for the full rationale -- the ONE shared detector for both
    forms of this layer's spec, implementing both legal exceptions
    "escalated above"/"rejected on different tiers" for free).

    rejected -- [(pos, model), ...], escalated -- [pos, ...] (positions
    are the integer line index of the single pass in
    _collect_escalation_events, monotonically increasing). A model that
    isn't a string (a broken/missing rejected.model) groups under its
    actual value as a dict key (including None) -- a defensive default,
    two records sharing the same "broken" value still form a group (does
    not crash the check); in practice `model` is a REQUIRED field on
    `rejected` (journal_validator), this layer does not rely on the form
    of the lines above being valid."""
    by_model: dict = {}
    for pos, model in rejected:
        by_model.setdefault(model, []).append(pos)
    for positions in by_model.values():
        if len(positions) >= 2:
            second_pos = sorted(positions)[1]
            if not any(epos > second_pos for epos in escalated):
                return True
    return False


def _check_delegated_retry(obj: dict, state: dict):
    """For ONE `delegated` line (obj -- an already-parsed dict), decides
    whether it triggers either of the two forms of this layer's spec,
    and if so, whether the detector (_escalation_group_unsatisfied) is
    violated for its task_id against the accumulated state (see
    _collect_escalation_events). Returns
    (trigger, task_id, attempt_display) | None.

    Excluded triggers (see the section above): agent=="critic" -> None
    immediately; notes carrying "replaces_worker:<handle>"
    (journal_validator.extract_replaces_worker(...) is not None) ->
    None immediately -- neither is a retry, regardless of attempt/
    task_id.

    task_id missing/not a string/empty -> None (nothing to check, the
    same fail-open principle as the rest of this file).

    `attempt` -- a number (int/float, WITHOUT bool -- isinstance(x,
    bool) is True for the literals True/False in Python, a defensive
    guard: bool is NOT the same thing as a numeric `attempt`, even
    though it's technically an int subclass). Form 1 (attempt>=3):
    trigger="attempt". Form 2 (`attempt` is ABSENT --
    obj.get("attempt") is None -- AND the task_id already has >=2
    `rejected` events accumulated, at least potentially from one
    model-group -- the final filter is below): trigger="no_attempt".
    Neither -> None (including attempt=1, attempt=2, a non-numeric
    attempt value other than None -- the spec's explicit legal cases).

    Final filter: _escalation_group_unsatisfied(rejected, escalated)
    False -> None (legitimate, see the section above). True -> a WARN
    tuple; attempt_display is the declared `attempt` for form 1, OR
    len(rejected)+1 for form 2 (an estimate of "which attempt number
    this delegated line effectively IS, since the field itself was
    forgotten" -- own engineering decision, the spec gives a literal
    "attempt N" template only for form 1, without pinning a number for
    form 2; documented here, flagged for Lead review)."""
    if obj.get("agent") == "critic":
        return None
    if journal_validator.extract_replaces_worker(obj.get("notes")) is not None:
        return None
    task_id = obj.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return None
    attempt = obj.get("attempt")
    is_attempt_number = isinstance(attempt, (int, float)) and not isinstance(attempt, bool)
    task_state = state.get(task_id, {"rejected": [], "escalated": []})
    rejected = task_state["rejected"]
    escalated = task_state["escalated"]
    if is_attempt_number and attempt >= 3:
        trigger = "attempt"
    elif attempt is None and len(rejected) >= 2:
        trigger = "no_attempt"
    else:
        return None
    if not _escalation_group_unsatisfied(rejected, escalated):
        return None
    attempt_display = attempt if trigger == "attempt" else len(rejected) + 1
    return (trigger, task_id, attempt_display)


def _collect_escalation_events(new_lines: list, base_lines: list) -> list:
    """One linear pass over base_lines (history -- CONTEXT, the spec
    explicitly allows this) then new_lines (the payload-scoped TRIGGER
    -- the check only runs on lines from here, per the spec: "consume
    ONLY the payload-scoped new lines"). Builds per-task_id state
    {"rejected": [(pos, model)], "escalated": [pos]} as it goes
    (_absorb) and, on EVERY `delegated` line FROM new_lines, checks it
    against state accumulated STRICTLY BEFORE it
    (_check_delegated_retry) -- only THEN (not before) is that same
    line itself absorbed into state, in case it is itself
    rejected/escalated (a `delegated` line never is, but later lines of
    THIS SAME batch may reference it).

    line_no uses the SAME formula as TIER ECHO/WITNESS ECHO/TS DRIFT
    ECHO (len(base_lines)+idx+1) -- consistent line numbers across the
    whole file.

    Fails open per line (the same pattern as _collect_tier_events/
    _collect_ts_drift_events): a broken line's JSON -- try/except with
    `continue`, does not interrupt parsing the rest of the batch."""
    events = []
    state: dict = {}

    def _touch(task_id):
        return state.setdefault(task_id, {"rejected": [], "escalated": []})

    def _absorb(obj, pos):
        event = obj.get("event")
        task_id = obj.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return
        if event == "rejected":
            _touch(task_id)["rejected"].append((pos, obj.get("model")))
        elif event == "escalated":
            _touch(task_id)["escalated"].append(pos)

    pos = 0
    for line in base_lines:
        pos += 1
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                _absorb(obj, pos)
        except Exception:
            continue

    for idx, line in enumerate(new_lines):
        pos += 1
        line_no = len(base_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            if obj.get("event") == "delegated":
                warn = _check_delegated_retry(obj, state)
                if warn is not None:
                    trigger, task_id, attempt_display = warn
                    events.append((line_no, trigger, task_id, attempt_display))
            _absorb(obj, pos)
        except Exception:
            continue
    return events


def _format_escalation_line(event: tuple, ascii_only: bool) -> str:
    """"ESCALATION: line N attempt A no escalated for task_id T - two
    rejected on the same tier with no escalation: a silent-retry loop
    goes unnoticed; escalate to the tier above and append an escalated
    event (rule 6)" -- rule of three ON TOP of the R6 rule's own
    wording. "line N" is added ON TOP of the message,
    by analogy with every other formatter in this file (TIER ECHO/
    WITNESS ECHO/TS DRIFT ECHO all carry "line N" -- distinguishing
    batch lines when joined with "; "); the task_id VALUE is
    substituted into the message (a warning with no concrete task_id
    would be practically useless to the coordinator, the same
    principle WITNESS ECHO already applies inserting cmd/ts, TIER ECHO
    inserting measured; own decision, documented, flagged for Lead
    review). task_id is dynamic third-party JSON content, sanitized
    PER CHANNEL (raw for stdout, ascii for stderr), the same principle
    _format_witness_line applies to cmd/ts."""
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    line_no, _trigger, task_id, attempt_display = event
    # Rule of three (what's wrong / what it risks / the action,
    # imperative verb "escalate").
    return (f"ESCALATION: line {line_no} attempt {attempt_display} no escalated "
            f"for task_id {sanitize(str(task_id))} - two rejected on the same tier "
            "with no escalation: a silent-retry loop goes unnoticed; escalate to the "
            "tier above and append an escalated event (rule 6)")


def build_escalation_segment(escalation_events: list, ascii_only: bool = False) -> str:
    """Assembles the ESCALATION part of additionalContext -- the SAME
    pattern as build_tier_segment/build_ts_drift_segment (ceiling
    MAX_ESCALATION_LINES=5 lines per call, "+K more" on top). An empty
    escalation_events -> "" (the caller treats an empty string as "no
    segment", same principle as the other build_* functions)."""
    if not escalation_events:
        return ""
    head = escalation_events[:MAX_ESCALATION_LINES]
    rest = len(escalation_events) - len(head)
    body = "; ".join(_format_escalation_line(ev, ascii_only) for ev in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


# --- NOTES LEN ECHO -----------------------------------------------------
# An oversized `notes` field risks burying a load-bearing fact in
# prose where no gate or later reader will find it again -- typed
# fields carry facts, notes stays a human-readable pointer (see
# CLAUDE.md's typed-fields rule). This layer warns (never blocks) when
# a NEW line's notes exceeds a per-event threshold, at write time --
# the same "close the gap before commit" motive TIER/WITNESS/TS DRIFT/
# ESCALATION ECHO already carry above in this file.
#
# EVENT OUTSIDE THE TABLE / no `event` field: silent -- no assigned
# threshold, no verdict (the same principle _extract_declared_word/
# _detect_ts_drift/_find_agent_transcript already apply above).
#
# UNIT -- CHARACTERS, not bytes: len() of the Python string, the same
# measure the constant name (NOTES_LEN_THRESHOLDS_CHARS) and the
# warning text ("chars") both name -- this targets the volume of prose
# a human reads, not the file's on-disk size; a byte measure would
# make the penalty language-dependent (non-ASCII text is wider in
# UTF-8 than plain ASCII).
#
# BASE: the SAME payload-scoped base (echo_new_lines/echo_base_lines
# from _resolve_echo_base) TIER/WITNESS/TS-DRIFT/ESCALATION ECHO
# already use above -- but, unlike those four, this layer is fully
# DISABLED when used_fallback == True (see main()): in fallback mode
# (an unreadable payload / a non-tail edit) it yields zero notes-len
# events rather than merely "less confident" -- otherwise it would
# re-evaluate the WHOLE uncommitted journal tail on every write, a
# growing false-positive class. FALLBACK_MARKER_TEXT still prints as
# usual regardless of this disablement -- "this layer stayed silent"
# remains visible through the existing marker, not a silent death.
#
# WARNING TEXT: a static ASCII template, WITHOUT a notes fragment (see
# _format_notes_len_line) -- every dynamic value inserted (line_no,
# length, threshold are integers; event is one of the fixed ASCII keys
# of NOTES_LEN_THRESHOLDS_CHARS, a closed set, never arbitrary
# third-party JSON text) carries no injection risk -- unlike cmd/ts in
# WITNESS ECHO or measured in TIER ECHO, no sanitizer is required here
# (the same "clean dynamics" class _format_ts_drift_line already
# establishes above for events carrying only integers).
#
# EDGES (fail-open, the same per-line try/except pattern every other
# _collect_* in this file already uses): notes missing/not a string/
# empty/whitespace-only -- silent (journal_validator already catches
# the form defect; a second warning about the same defect would be
# noise, not a new signal); a line that doesn't parse as JSON / isn't
# an object -- per-line `continue`, a broken line doesn't stop the
# rest of the same call from being parsed.
NOTES_LEN_THRESHOLDS_CHARS = {
    "delegated": 800,
    "accepted": 800,
    "rejected": 800,
    "dispatch_skipped": 800,
    "escalated": 800,
    "defect_found": 800,
    "decomposable": 800,
    "calibrated": 15000,
}
# No external threshold-config file is introduced: it would create a
# temporal edge ("before/after the file exists") and a second source
# of truth alongside the code -- thresholds live EXCLUSIVELY here, in
# this module constant.
MAX_NOTES_LEN_LINES = 5  # the same class of ceiling as MAX_TIER_LINES/
# MAX_WITNESS_LINES/MAX_TS_DRIFT_LINES/MAX_ESCALATION_LINES above in
# this file -- the same motive (a payload-scoped base with NO ceiling
# on a rare-but-real large batch -> unbounded additionalContext on one
# hook call). Boundary tests at 5/6 -- see test_journal_echo_noteslen.py.


def _collect_notes_len_events(new_lines: list, base_lines: list) -> list:
    """For EVERY new line (the same new_lines/base_lines pair TIER/
    WITNESS/TS-DRIFT/ESCALATION ECHO already use in main(), see
    _resolve_echo_base) whose event IS IN NOTES_LEN_THRESHOLDS_CHARS,
    and whose non-empty (after strip()) string notes is STRICTLY (>,
    not >=) longer than the assigned threshold -- appends (line_no,
    event, length, threshold) to the result. line_no is the SAME
    formula journal_validator.validate_new_lines and every other
    _collect_* in this file use (len(base_lines)+idx+1).

    Silent (adds nothing) on: event missing/not in the threshold table
    (no assigned threshold, no verdict); notes missing/not a string
    (including int/list/None/dict -- len() is never called on a
    non-string); notes empty/whitespace-only (the form defect is
    already caught by journal_validator); length <= threshold (the
    boundary itself stays silent).

    Length is measured on the RAW notes (len(notes), including any
    leading/trailing whitespace on otherwise non-empty content) -- the
    emptiness check (notes.strip()) is used ONLY as an "is there
    anything to evaluate" filter, not as preprocessing before the
    measurement (unit: characters of the Python string as-is).

    Fails open per line (the same pattern as every other _collect_* in
    this file): broken JSON / a non-dict line -- try/except with
    `continue`, does not stop parsing the rest of this call's lines
    and does not crash the hook."""
    events = []
    for idx, line in enumerate(new_lines):
        line_no = len(base_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            event = obj.get("event")
            threshold = NOTES_LEN_THRESHOLDS_CHARS.get(event)
            if threshold is None:
                continue
            notes = obj.get("notes")
            if not isinstance(notes, str):
                continue
            if not notes.strip():
                continue
            length = len(notes)
            if length > threshold:
                events.append((line_no, event, length, threshold))
        except Exception:
            continue
    return events


def _format_notes_len_line(event: tuple) -> str:
    """"NOTES LEN: line <N> event=<e> notes <L> chars > threshold <T> -
    ..." -- a static ASCII literal, WITHOUT the notes text itself
    (inserting notes text would need its own sanitizer and its own
    boundary tests -- deliberately not introduced). No part of this
    message needs sanitize (see the section docstring above -- all
    four substituted values are either plain integers or one of the
    fixed ASCII keys of NOTES_LEN_THRESHOLDS_CHARS) -- no ascii_only
    parameter, the same signature choice _format_ts_drift_line already
    makes above for the same reason. Rule of three: what's wrong (an
    oversized note), what it risks (burying load-bearing facts where
    they won't be found later), the action (move load-bearing facts to
    typed fields / task carrier, keep only a pointer in notes)."""
    line_no, event_name, length, threshold = event
    return (f"NOTES LEN: line {line_no} event={event_name} notes {length} chars "
            f"> threshold {threshold} - an oversized note risks burying load-bearing "
            "facts in prose where they will not be found later; move load-bearing "
            "facts to typed fields / task carrier, keep only a pointer in notes")


def build_notes_len_segment(events: list, ascii_only: bool = False) -> str:
    """Assembles the NOTES LEN part of additionalContext -- the SAME
    pattern as build_tier_segment/build_ts_drift_segment/
    build_escalation_segment (ceiling MAX_NOTES_LEN_LINES=5 lines per
    call, "+K more" on top). ascii_only is accepted for signature
    uniformity with the other build_*/combine_context in this file, but
    is actually a no-op here (the same choice build_ts_drift_segment
    already documents for the same reason -- _format_notes_len_line
    never inserts anything that would need sanitizing in either mode).
    An empty list -> "" -- the caller treats an empty string as "no
    segment", the same principle as the other build_* functions."""
    if not events:
        return ""
    head = events[:MAX_NOTES_LEN_LINES]
    rest = len(events) - len(head)
    body = "; ".join(_format_notes_len_line(ev) for ev in head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


# --- R3 MIRROR ------------------------------------------------------------
# GAP: the acceptance-gate rule (critic is mandatory above a diff-size
# threshold, or a data-schema/core/money diff, unless waived by
# "critic: skipped, <reason>") is held ONLY by the acceptor's
# discipline at write time -- nothing on the write path detects a
# builder `accepted` line carrying neither signal. This layer is WARN,
# NEVER a block (the same pattern ESCALATION ECHO/TS DRIFT ECHO
# already apply above for the escalation rule -- a warning at write
# time, a hard gate is a separate, coarser instrument, not engaged
# here; this logic does NOT enter journal_validator.decide()).
#
# TRIGGER: a NEW line (echo_new_lines) with event=="accepted",
# agent=="builder". Silent on the line at ANY of FIVE signals:
#   S1 basis=="critic"
#   S2 notes matches CRITIC_SKIP_RE (literally "critic: skipped",
#      ignorecase, flexible whitespace around the colon)
#   S3 delegated(agent=="critic") with the SAME task_id ANYWHERE in
#      the file -- base_lines (history) + the WHOLE current batch
#      (echo_new_lines) in BOTH directions (a critic delegation can sit
#      either before or after the accepted line within one batch) --
#      hence a full pre-pass over new_lines (alongside base_lines) for
#      critic delegations BEFORE the main trigger pass, see
#      _collect_r3_events.
#   S4 basis=="judge" (a leaf-class judge acceptance silences this
#      layer unconditionally)
#   S5 a bare `critic:t-NNN` token in notes (regex CRITIC_TOKEN_RE =
#      `\bcritic:(t-\d{3,})\b`, a literal -- the same case-sensitive
#      convention journal_validator's replaces_worker token uses --
#      NOT ignorecase, unlike CRITIC_SKIP_RE above) silences BOTH M1
#      and M2, but ONLY if the cited t-NNN actually EXISTS in the file
#      as delegated(agent=="critic") -- the check is free:
#      critic_task_ids is already collected for S3 by the same
#      pre-pass, S5 simply checks the extracted id against that same
#      set. A token citing a NON-EXISTENT verdict does NOT silence
#      (s5_valid stays False, the line falls through to the ordinary
#      M1/M2 branch as if the token weren't there). The form mirrors
#      the journal's own `closes:t-NNN` token -- several tokens in
#      notes are legal, ONE valid one is enough (see
#      _check_accepted_r3: `.finditer`, any match). UNLIKE S3 (requires
#      the SAME task_id), S5 is CROSS-task_id by construction: the
#      cited t-NNN can be ANY task_id in the file, as long as a
#      delegated(critic) actually stands under it -- this is exactly
#      the mechanism for "one bundling critic pass over several small
#      accepted lines".
#
# M2 DETECTOR (independent of M1, fires ONLY when S1 is true):
# basis=="critic" with NO delegated(agent=="critic") under this same
# task_id ANYWHERE in the file AND no valid S5 token -> "a claimed
# basis with no traceable delegation" (a phantom basis, class
# completeness checks will read this as a false basis). PRIORITY: a
# line with basis=="critic", no delegation, and no valid S5, but WITH
# the concession literal (S2, "critic: skipped") in notes -- is a
# CONTRADICTORY record, M2 is correct (silencing it via S2 would
# forgive the contradiction) -- structurally guaranteed by check order
# below: the basis=="critic" branch is checked FIRST and never looks
# at S2/the notes-skip literal at all (S2 is a branch of M1 only, not
# an alternative inside M2).
#
# EDGES: task_id missing/not a string/whitespace-only -> the whole
# line is skipped (neither M1 nor M2) -- the same check applies to
# critic_task_ids (_absorb_critic below -- a delegated(critic) with a
# whitespace-only task_id does not enter the set, fix the class not
# the instance); notes is None -> treated as empty (the S2/S5 regexes
# simply don't match a non-string); basis absent -> the check falls
# through S1/S4 to S2/S3/S5; basis=="queued-to-lead" -> does NOT
# silence (equal to neither "critic" nor "judge"); agent != builder ->
# outside the trigger, silent; a repeated accepted on one task_id ->
# each line is checked independently (the shared critic_task_ids is
# not consumed); a retro acceptance (notes contains "retroactive") ->
# NOT exempted from R3 (unlike WITNESS ECHO, this layer gives no retro
# exemption); used_fallback -> this layer runs REGARDLESS, on the
# fallback (cumulative HEAD-diff) base as-is -- the same "noisy but
# not correctness-false" class TIER/WITNESS/ESCALATION already are
# (critic input/basis/notes do not depend on how much time passed
# since an unrelated commit; there is no false verdict here, see
# main() -- r3_events is NOT gated by used_fallback, computed
# unconditionally); an empty journal/broken JSON/non-dict line ->
# skipped without interrupting the rest of the batch (fail-open per
# line, below); the `witness` field is NOT read by this layer (S2/S5
# match ONLY notes) -- BATCH CANON in witness is untouched by this
# layer entirely.
#
# Fails open per line (the same pattern as every other _collect_* in
# this file): broken JSON on one line -- try/except with `continue`,
# does not stop parsing the rest of the batch.
MAX_R3_LINES = 5  # the same class of ceiling as MAX_TIER_LINES/
# MAX_WITNESS_LINES/MAX_TS_DRIFT_LINES/MAX_ESCALATION_LINES/
# MAX_NOTES_LEN_LINES above in this file -- the same own engineering
# decision (5, "+K more" on top). Boundary tests at 5/6 -- see
# test_journal_echo_r3.py.
#
# MAX_R3_BYTES: a ceiling by BYTES on the segment's json-wire footprint
# (ensure_ascii bytes), INDEPENDENT of MAX_R3_LINES -- json.dumps(...,
# ensure_ascii=True) escapes every non-ASCII character into "\uXXXX"
# (6 ASCII bytes per character instead of 1-4 UTF-8 bytes), so a batch
# whose task_ids or static text happen to carry non-ASCII content can
# inflate the wire well beyond what MAX_R3_LINES alone would predict.
# Even with short ASCII-only text (as this port keeps), the byte
# ceiling stays a second, structural guard, independent of text
# length, against a batch of long task_ids: when exceeded, lines fold
# into "+K more" EARLIER than the line-count limit, even if
# MAX_R3_LINES=5 hasn't been reached yet.
MAX_R3_BYTES = 2600
CRITIC_SKIP_RE = re.compile(r"critic\s*:\s*skipped", re.IGNORECASE)
# The concession literal -- ONLY this form (ignorecase, flexible
# whitespace around the colon) matches; no free-form wording ("critic:
# skip", "no critic", "critic waived" -- do NOT match, see battery 3 in
# test_journal_echo_r3.py).
CRITIC_TOKEN_RE = re.compile(r"\bcritic:(t-\d{3,})\b")
# Case-sensitive literal (NOT ignorecase, symmetric with
# journal_validator's replaces_worker/closes token) -- a machine
# structural token, not free prose, unlike CRITIC_SKIP_RE above. Group
# 1 is the referenced task_id ("t-NNN"), checked against
# critic_task_ids in _check_accepted_r3.


def _json_wire_len(s: str) -> int:
    """Bytes s will add to the JSON additionalContext wire under
    ensure_ascii=True -- json.dumps itself escapes ANY non-ASCII
    character into a safe "\\uXXXX" sequence (six ASCII bytes per
    character instead of the native 1-4 UTF-8 bytes) and control
    characters into "\\n"/"\\t"/"\\uXXXX" -- json.dumps's result is
    ALWAYS pure ASCII, so len() of the Python string of that result ==
    bytes on the wire. `- 2` removes the wrapping quotes json.dumps
    adds for ANY string -- this function measures s's CONTRIBUTION to
    the overall additionalContext wire (s is joined with other
    segments via "; " INSIDE one larger JSON string, not as a separate
    JSON value of its own) -- see build_r3_segment for the running
    total this measure feeds."""
    return len(json.dumps(s, ensure_ascii=True)) - 2


def _collect_r3_events(new_lines: list, base_lines: list) -> list:
    """One linear pass, structurally a direct sibling of
    _collect_escalation_events above (the same base_lines(history) +
    new_lines(payload-scoped trigger) pair, the same line_no formula
    (len(base_lines)+idx+1), the same per-line fail-open).

    The one structural difference from that sibling (S3 is NOT
    positional -- the window is "anywhere in the file, in both
    directions"): critic presence (critic_task_ids) is collected by
    TWO full passes BEFORE the main trigger pass -- base_lines in full
    (history, naturally "already known") AND new_lines in full (a
    pre-pass over critic delegations, scanning the batch in BOTH
    directions) -- NOT accumulated line-by-line as the main pass goes,
    precisely because S3 must see a critic delegation standing AFTER
    an accepted line in the same batch, not only before it. The main
    trigger pass (only event=="accepted" agent=="builder" lines of
    new_lines) runs SECOND, against the already-fully-collected
    critic_task_ids -- the same "check against state accumulated
    BEFORE it" shape the sibling applies to delegated lines, here "before"
    means "after both pre-passes", not "after the earlier lines of the
    current pass".

    Returns a list of (line_no, kind, task_id, extra) -- kind in
    ("no_input", "phantom_basis"), extra reserved (always None -- this
    layer carries no extra data in either message kind, see
    _format_r3_line)."""
    events = []
    critic_task_ids: set = set()

    def _absorb_critic(lines):
        for line in lines:
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if obj.get("event") == "delegated" and obj.get("agent") == "critic":
                    task_id = obj.get("task_id")
                    # Fix the class, not the instance: a whitespace-only
                    # task_id is treated the same "not a valid id" way
                    # the trigger side applies in _check_accepted_r3
                    # below (task_id.strip() empty -> not valid).
                    if isinstance(task_id, str) and task_id.strip():
                        critic_task_ids.add(task_id)
            except Exception:
                continue

    _absorb_critic(base_lines)
    _absorb_critic(new_lines)  # pre-pass over the WHOLE batch

    for idx, line in enumerate(new_lines):
        line_no = len(base_lines) + idx + 1
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            warn = _check_accepted_r3(obj, critic_task_ids)
            if warn is not None:
                kind, task_id = warn
                events.append((line_no, kind, task_id, None))
        except Exception:
            continue
    return events


def _check_accepted_r3(obj: dict, critic_task_ids: set):
    """For ONE already-parsed dict line -- decides whether it triggers
    (event=="accepted" agent=="builder") and, if so, which kind of warn
    (or None -- complete silence) it produces against the already
    collected critic_task_ids (see _collect_r3_events for how it's
    collected). Split out as its own function by the same pattern
    _check_delegated_retry follows above for ESCALATION ECHO.

    S5 is computed ONCE (s5_valid) BEFORE the S1/S4 branching -- used
    in BOTH branches (M1 -- one more independent silencer alongside
    S2/S3; M2 -- an alternative to a delegated record under the SAME
    task_id, literally per M2's text: "close with a critic:t-NNN token
    ... OR a delegated record"). The M2 priority (basis=="critic" with
    no delegation and no S5, but WITH the concession literal in notes
    -- M2 is correct, NOT silenced by S2) holds STRUCTURALLY: the
    basis=="critic" branch is checked first and never looks at
    CRITIC_SKIP_RE/S2 at all -- S2 only participates in the M1 branch.

    Returns ("no_input", task_id) | ("phantom_basis", task_id) | None."""
    if obj.get("event") != "accepted":
        return None
    if obj.get("agent") != "builder":
        return None
    task_id = obj.get("task_id")
    if not isinstance(task_id, str) or not task_id.strip():
        return None  # edge: task_id missing/not a string/whitespace-only -> skip
    basis = obj.get("basis")
    notes = obj.get("notes")
    s5_valid = False
    if isinstance(notes, str):
        for m in CRITIC_TOKEN_RE.finditer(notes):
            if m.group(1) in critic_task_ids:
                s5_valid = True
                break
    if basis == "judge":
        return None  # S4
    if basis == "critic":
        if task_id in critic_task_ids or s5_valid:
            return None  # S1 confirmed by delegation OR a valid S5
        return ("phantom_basis", task_id)  # M2 (S2 is not consulted here)
    if isinstance(notes, str) and CRITIC_SKIP_RE.search(notes):
        return None  # S2
    if task_id in critic_task_ids:
        return None  # S3
    if s5_valid:
        return None  # S5
    return ("no_input", task_id)  # M1


def _format_r3_line(event: tuple, ascii_only: bool) -> str:
    """M1/M2 literals -- short by design (a byte-budgeted segment, see
    MAX_R3_BYTES above). The "R3 MIRROR: line " literal itself never
    changes. task_id is the only dynamic content, sanitized PER CHANNEL
    (the same principle _format_escalation_line applies above in this
    file) -- MAX_MESSAGE_LEN applies to it like any other dynamic
    element of this file (see _raw_sanitize/_ascii_sanitize).
    "critic:t-NNN" in both texts is a LITERAL (NNN is a literal format
    hint for the reader, not a real number, never substituted or
    sanitized). Rule of three per message: what's wrong, what it
    breaks, the closing action."""
    sanitize = _ascii_sanitize if ascii_only else _raw_sanitize
    line_no, kind, task_id, _extra = event
    tid = sanitize(str(task_id))
    if kind == "phantom_basis":
        return (
            f"R3 MIRROR: line {line_no} basis=critic for {tid}, no "
            "delegated(critic) under this task_id - basis is not traceable; "
            "close with a critic:t-NNN token on the covering verdict OR a "
            "delegated record"
        )
    # "no_input" (M1)
    return (
        f"R3 MIRROR: line {line_no} accepted builder {tid}: no critic "
        "input under this id and no concession - class-completeness review "
        "will read this acceptance as self-certification; close with "
        f"delegated(critic) for {tid} / a critic:t-NNN token on the "
        'covering verdict / "critic: skipped, <reason>" (acceptor strictly '
        "above)"
    )


def build_r3_segment(events: list, ascii_only: bool = False) -> str:
    """Assembles the R3 MIRROR part of additionalContext -- TWO
    INDEPENDENT ceilings: MAX_R3_LINES=5 lines (as before) AND
    MAX_R3_BYTES=2600 bytes of the accumulated json-wire body
    (_json_wire_len, see its docstring) -- whichever of the two fires
    FIRST, the truncation is the same: a "+K more" tail. Greedy pass: a
    line is added only if BOTH the line counter has NOT yet reached
    MAX_R3_LINES, AND (for the second and later lines) the byte
    contribution of the accumulated body (lines already added + "; " +
    the candidate) does NOT exceed MAX_R3_BYTES -- otherwise the loop
    stops, the candidate and everything after it fold into "+K more".

    The FIRST line of the segment is ALWAYS accepted unconditionally by
    bytes (`if head and ...` -- the byte-ceiling check is skipped while
    head is still empty) -- not a hole, a consequence of a measured
    fact: one line of this format with a task_id at the MAX_MESSAGE_LEN=500
    boundary weighs far less than MAX_R3_BYTES=2600 on the wire -- the
    two independent ceilings of this file (MAX_MESSAGE_LEN on task_id,
    the short M1/M2 texts) structurally prevent any single line from
    ever reaching the byte ceiling on its own -- the branch for "the
    first line alone exceeds the ceiling" would be unreachable
    (untestable without violating one of those two other invariants
    separately) -- deliberately not introduced.

    An empty events -> "" -- the caller (combine_context) treats an
    empty string as "no segment", the same principle as the other
    build_* functions."""
    if not events:
        return ""
    head: list = []
    for ev in events:
        if len(head) >= MAX_R3_LINES:
            break
        candidate_line = _format_r3_line(ev, ascii_only)
        candidate_body = "; ".join(head + [candidate_line])
        if head and _json_wire_len(candidate_body) > MAX_R3_BYTES:
            break
        head.append(candidate_line)
    # head is never empty here for a non-empty events (the first line
    # is always accepted, see the docstring above), so `body` is never
    # empty in the rest>0 branch either -- a plain join, no fallback
    # form for an empty body.
    rest = len(events) - len(head)
    body = "; ".join(head)
    if rest > 0:
        body += f"; +{rest} more"
    return body


# --- STDOUT DEADLINE HELPER -----------------------------------------------
# A non-draining consumer on the other end of the stdout pipe can hold
# sys.stdout.write() stuck inside the OS on a full pipe, hanging this
# hook (and the tool call waiting on it) forever. The final stdout
# write in main() therefore runs on a daemon writer thread, joined by
# the main thread with a deadline; if the writer thread is still alive
# once the deadline passes, the caller does an IMMEDIATE os._exit(0) --
# no further I/O on EITHER channel (stderr risks the same stuck-pipe
# class on the same non-draining consumer). This hook already ALWAYS
# returns 0 on the ordinary path (no legal form of an `accepted` line
# fails the write) -- this branch changes only HOW that rc=0 is
# reached on a non-draining consumer (previously: hang forever inside
# sys.stdout.write(); now: a fast rc=0 exit).
_STDOUT_DEADLINE_DEFAULT = 5.0
_STDOUT_DEADLINE_MAX = 600.0
_STDOUT_DEADLINE_ENV = "OSLLM_STDOUT_TIMEOUT"


def _stdout_deadline_seconds():
    """Seconds of the WRITE deadline -- invalid/non-numeric/<=0/>MAX ->
    the default."""
    try:
        value = float(os.environ.get(_STDOUT_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDOUT_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDOUT_DEADLINE_MAX):
        return _STDOUT_DEADLINE_DEFAULT
    return value


def _write_stdout_deadline(text: str) -> bool:
    """Writes text as ONE logical write (sys.stdout.write + flush) on a
    daemon thread; the main thread waits join(deadline). Returns True
    if the writer thread FINISHED in time (write+flush either
    succeeded, or raised a regular exception, re-raised here on the
    main thread AFTER join()), False if the thread is still alive once
    the deadline passes (a non-draining consumer is holding write()
    stuck inside the OS on a full pipe). On False the caller MUST
    os._exit(0) immediately and must not attempt to write ANYWHERE
    else (see main())."""
    box: dict = {}

    def _writer():
        try:
            sys.stdout.write(text)
            sys.stdout.flush()
        except BaseException as e:  # re-raised on the main thread below
            box["exc"] = e

    thread = threading.Thread(target=_writer, name="stdout-deadline", daemon=True)
    thread.start()
    thread.join(_stdout_deadline_seconds())
    if thread.is_alive():
        return False
    if "exc" in box:
        raise box["exc"]
    return True


def _reconfigure_streams_utf8():
    """The static text (see build_context) goes on BOTH channels --
    without an explicit reconfigure, this machine's default stdout/
    stderr encoding may not be UTF-8, and a subprocess smoke can hit a
    UnicodeDecodeError on the reading parent's side otherwise. The same
    pattern as tools/hygiene_gate.py._reconfigure_stdout_utf8 and
    tools/dod_track.py._reconfigure_stderr_utf8 -- here BOTH channels
    need it (this hook writes to both), a copy, not an import (see the
    module docstring)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# --- stdin deadline (P4 class; a LOCAL copy, no shared module -- the
# same helper toolkit/tools/owns_gate.py/dispatch_gate.py already carry
# -- this file already had the STDOUT half of P4 from an earlier wave,
# the STDIN half was still a bare sys.stdin.buffer.read())
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


def main() -> int:
    _reconfigure_streams_utf8()
    try:
        # P4: byte-safe read via the stdin-deadline helper (replaces
        # the former direct sys.stdin.buffer.read() -- bounded by
        # OSLLM_STDIN_TIMEOUT instead of blocking forever with no EOF).
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
        if not isinstance(payload, dict):
            return 0

        file_path = _extract_file_path(payload)
        if not file_path or not _is_journal_path(file_path):
            return 0

        try:
            disk_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0

        root = _repo_root(file_path)
        now = datetime.datetime.now()
        head_text = _get_head_text(root)

        # VALIDATION -- the cumulative HEAD-diff base: historical
        # uncommitted lines' FORM still needs catching before commit
        # regardless of which specific tool call is running now.
        _, violations = journal_validator.decide(disk_text, head_text, now)

        # ECHO LAYERS (TIER ECHO/WITNESS ECHO): ONE
        # payload-scoped base shared by both collectors (see
        # _resolve_echo_base/the "PAYLOAD-SCOPED ECHO BASE" section
        # above) -- replaces the old HEAD-diff base these two layers
        # used to share with VALIDATION (root cause: that base is
        # cumulative between commits, so every call re-echoed every
        # uncommitted line, not just the one THIS call added).
        staged_lines = journal_validator.split_lines(disk_text)
        head_lines = journal_validator.split_lines(head_text)
        tool_name = payload.get("tool_name")
        echo_base_lines, echo_new_lines, used_fallback = _resolve_echo_base(
            payload, tool_name, staged_lines, head_lines)

        tier_events = _collect_tier_events(echo_new_lines, echo_base_lines)

        # WITNESS ECHO at write time (this port's second extension --
        # see the module docstring): the SAME payload-scoped base as
        # TIER ECHO above. A second, outer try/except here (on top of
        # the per-line one inside _collect_witness_events itself) means
        # a failure in this cross-check can never take down JOURNAL
        # ECHO/TIER ECHO.
        try:
            witness_events = _collect_witness_events(echo_new_lines, echo_base_lines, payload)
        except Exception:
            witness_events = []
        # "note" events (retro / empty track) never make a line visible
        # -- only warn_loud/warn_soft/warn_stale trigger printing.
        witness_visible = any(e[0] != "note" for e in witness_events)

        # TS DRIFT ECHO at write time: the
        # SAME payload-scoped base as TIER ECHO/WITNESS ECHO above --
        # `now` is the SAME variable already computed above for
        # decide()/_get_head_text, not recomputed. Warn-only, always
        # visible (no "note" branch, unlike WITNESS ECHO).
        try:
            ts_drift_events = _collect_ts_drift_events(echo_new_lines, echo_base_lines, now)
        except Exception:
            ts_drift_events = []

        # ESCALATION ECHO (a machine guard mirroring the escalation
        # rule): the SAME payload-scoped base as
        # TIER/WITNESS/TS DRIFT above (see the "ESCALATION ECHO at write
        # time" section for how base_lines is used as history for
        # CONTEXT while the trigger stays on echo_new_lines). Fails open
        # as a second layer on top of the per-line try/except already
        # inside _collect_escalation_events itself -- the same pattern
        # as WITNESS ECHO/TS DRIFT ECHO above.
        try:
            escalation_events = _collect_escalation_events(echo_new_lines, echo_base_lines)
        except Exception:
            escalation_events = []

        # NOTES LEN ECHO: the SAME payload-scoped base as TIER/WITNESS/
        # TS-DRIFT/ESCALATION above -- but fully disabled when
        # used_fallback == True (see the "NOTES LEN ECHO" section above
        # for the motive: otherwise it would re-evaluate the WHOLE
        # uncommitted journal tail on every write). Fails open as a
        # second layer on top of the per-line try/except already inside
        # _collect_notes_len_events itself.
        if used_fallback:
            notes_len_events = []
        else:
            try:
                notes_len_events = _collect_notes_len_events(echo_new_lines, echo_base_lines)
            except Exception:
                notes_len_events = []

        # R3 MIRROR: the SAME payload-scoped base as TIER/WITNESS/
        # ESCALATION above -- this layer runs UNCONDITIONALLY, including
        # when used_fallback == True (see the "R3 MIRROR" section above:
        # critic input/basis/notes do not depend on how much time
        # passed since an unrelated commit -- the same "noisy but not
        # correctness-false" class TIER/WITNESS/ESCALATION already are,
        # NOT the class NOTES-LEN/TS-DRIFT belong to). Fails open as a
        # second layer on top of the per-line try/except already inside
        # _collect_r3_events itself.
        try:
            r3_events = _collect_r3_events(echo_new_lines, echo_base_lines)
        except Exception:
            r3_events = []

        if (not violations and not tier_events and not witness_visible
                and not ts_drift_events and not escalation_events
                and not notes_len_events and not r3_events):
            return 0

        # Fallback marker: visible ONLY when we're already
        # printing something else -- an otherwise fully clean call stays
        # silent even in fallback (see the section docstring above).
        fallback_marker = FALLBACK_MARKER_TEXT if used_fallback else ""

        context_for_stdout = combine_context(violations, tier_events, witness_events, ts_drift_events,
                                              escalation_events, fallback_marker,
                                              notes_len_events=notes_len_events, r3_events=r3_events,
                                              ascii_only=False)
        context_for_stderr = combine_context(violations, tier_events, witness_events, ts_drift_events,
                                              escalation_events, fallback_marker,
                                              notes_len_events=notes_len_events, r3_events=r3_events,
                                              ascii_only=True)

        sys.stderr.write(context_for_stderr + "\n")
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context_for_stdout,
            }
        }
        # ensure_ascii=True: the coordinator receives UTF-8-safe JSON --
        # non-ASCII is escaped to \uXXXX on the wire (json.dumps does
        # this itself), the reader recovers readable text via
        # json.loads(). This makes the standard call safe even without
        # a stream reconfigure -- the reconfigure is kept regardless, as
        # protection for the stderr channel.
        #
        # The final stdout write no longer calls sys.stdout.write()
        # directly -- it goes through _write_stdout_deadline() (see its
        # docstring/the "STDOUT DEADLINE HELPER" section above for the
        # full contract). False (a non-draining consumer is holding
        # write() stuck on a full pipe past the deadline) -> os._exit(0)
        # IMMEDIATELY, with NO further write (stderr risks the same
        # class of stuck pipe on the same non-draining consumer).
        stdout_text = json.dumps(output, ensure_ascii=True) + "\n"
        if not _write_stdout_deadline(stdout_text):
            os._exit(0)
        return 0
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
