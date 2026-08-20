"""SessionStart hook: "reality in the background" (t-027, F-30 layer 2)
plus the t-043 (B3 remainder) extension -- two more measured facts a
fresh session should not have to ask about before trusting its own boot
picture:

- MODEL: which tier is this session actually running on (D-0056a: the
  in-session self-check of D-0056/D-0058's tier matrix needs a measured
  input, not the session narrating its own model name).
- BOOT BUDGET: how big is the boot path right now, against the D-0068
  WARN/BREACH thresholds, without waiting for a weekly calibration run
  or a manual `wc -c` to notice a slow creep.

Plus the D-0076 extension: OPEN DISPATCH lines. Class-defect this line
guards against: a session wrote a `delegated` event to the routing log
and never actually launched the worker -- a phantom open dispatch, the
journal recording intent as fact (kin to F-29, which is the same failure
mode for timestamps instead of task lifecycles). A task_id counts as
OPEN iff its LAST lifecycle event (delegated/accepted/rejected/
escalated/decomposable -- see _OPEN_LIFECYCLE_EVENTS) is `delegated`;
anything else (dispatch_skipped, defect_found, lead_*, journal_created,
calibrated) neither opens nor closes a task and is ignored by this scan.

Built as a draft (session_context_b3.py) per D-0069 -- a SessionStart
hook registered in .claude/settings.json is a self-activating
enforcement file, so the builder delivered it under a sibling name and
Lead placed it on this path at acceptance (t-043; critic input: REWORK
on stdin sanitization, fixed attempt 2). Same pattern repeats here: this
D-0076 revision lands under yet another sibling name
(session_context_d0076.py) and Lead places it on the live path at
acceptance, with a critic-gate entry per CLAUDE.md rule 3.

Hard constraints inherited from t-027 (all still load-bearing, all
still true here, and still true after the D-0076 addition -- see 2.4 in
the spec this file was built from):
- NEVER breaks session start: any exception anywhere below collapses to
  ONE sanitized line, 'session-context warning: <ascii-safe detail>',
  and exit 0 (fail-open). main() is the single try/except boundary --
  see its docstring for why a per-section try/except was deliberately
  NOT used. The new open_dispatches()/open_dispatch_lines() functions
  follow the same rule: no local try/except, failures propagate to
  main()'s one boundary, exactly like quota_lines().
  CHANNEL (F-61 node B, fixes 4/5, 2026-08-19 critic revision -- this
  is the class "a guarantee announced totally but implemented partially"
  the fix itself must not repeat): the warning is attempted on STDOUT
  FIRST -- the same stream a healthy run would have used, so a build-
  time failure (broken journal, unreadable quota config -- both
  observed field incidents) stays VISIBLE to the session, not silently
  redirected to a stream nobody reads. Only when that stdout write
  itself raises (stdout genuinely dead, not merely the build) does the
  SAME line fall back to stderr; if BOTH channels are dead the warning
  is dropped silently and exit is still 0. See main()'s own docstring
  for the exact nested-try shape.
- Fast (<2s) and NO network at all (the NOW line's whole point is
  anti-F-29: read the system clock, not a narrated/inferred time).
- ASCII-safe output: this environment's console is cp1251. Every line
  built here is plain ASCII -- including the one line built from a
  NON-hardcoded source (MODEL from stdin), which goes through
  _ascii_sanitize (critic t-043 blocker: unsanitized stdin could break
  this invariant, inject lines past MAX_LINES, or crash print mid-flush).
  OPEN DISPATCH lines are built from journal-sourced task_id/agent/ts,
  also externally-sourced (an agent field could in principle carry
  anything a session wrote into the journal) -- so each of those three
  values is routed through the same _ascii_sanitize helper before being
  formatted into a line. F-61 node B (fix4, 2026-08-19): the fail-open
  WARNING line itself is the same class of externally-sourced content
  (str(e) can carry anything the failing code's exception message
  happened to hold, including non-ASCII text or embedded newlines) and
  used to be the ONE line in this file that bypassed _ascii_sanitize
  entirely -- critic-measured failure mode: a cp1251 console plus a
  non-cp1251-encodable message made the write itself raise, so the
  diagnostic died silently instead of degrading to a replacement-
  charactered but still-visible line. main() now routes str(e) through
  _ascii_sanitize(text, 300) before formatting it into the warning, on
  every channel attempt.
- <=25 lines total (MAX_LINES) -- not raised by this change; the D-0076
  addition can only ever add up to 4 lines (3 OPEN DISPATCH + 1 summary)
  and build_context_lines() still truncates to MAX_LINES at the end.
- Reading stdin must never block: only attempted when stdin is not a
  TTY (a manual `python tools/session_context.py` run from an
  interactive shell with nothing piped in must return instantly, not
  hang waiting for input that will never come).

Registered as the SessionStart hook via .claude/settings.json.

--- staged addition: WIRING-INTEGRITY block (N1, docs/tasks/
2026-07-21_validation-import.md; DAG node N1, t-256 verdict) ---
Hole this closes (class F-7): the enforcement chain (git hooks +
harness hooks in .claude/settings.json) dies SILENTLY when a hook file
is renamed, python is missing from PATH, or core.hooksPath is unset --
indistinguishable from "everything ran fine" because there is no
positive signal either way. This revision adds three read-only checks
(git-channel, harness-channel, python-channel -- see the "WIRING-
INTEGRITY" section below, right before build_context_lines()) that emit
either one "WIRING: OK (...)" line or one "WIRING WARNING: <fact>" line
per discrepancy, into the SAME output stream as boot_budget_lines() and
the rest of build_context_lines(). Per D-0069 this file is once again a
sibling copy, not the live hook -- Lead moves it onto tools/
session_context.py at acceptance. Fail-open discipline (spec point 3):
the wiring block never lets an internal failure of ITS OWN (a corrupt
settings.json, git missing, an unexpected exception in a helper) escape
past wiring_lines() -- each channel function already turns its known
failure modes into WARNING strings, and wiring_lines() itself adds one
more local try/except on top so a genuinely unforeseen bug in the
wiring code degrades to a single WARNING line instead of reaching
main()'s outer boundary and blanking the ENTIRE context block (NOW,
MODEL, JOURNAL, etc. would all be lost together, which is a strictly
worse failure than losing just the wiring lines). main()'s own
try/except is untouched.

--- VG-1 (two-part addition, one file) ---
Part A: the git-channel's "core.hooksPath not set" WARNING now attempts
a one-line self-heal FIRST -- `git config --local core.hooksPath
.githooks` -- before falling back to the warning; a confirmed success
prints "WIRING AUTOFIX: core.hooksPath set to .githooks" instead (see
_try_hookspath_autofix() and _AUTOFIX_FACT_PREFIX, right before
git_hooks_channel()). Deliberately scoped to the UNSET case only: when
core.hooksPath is already set to some OTHER path, that is somebody's
existing configuration (human or a prior session) and is left alone,
WARNING unchanged -- only a genuinely empty value is treated as safe to
wire up automatically. The exec-bit (D-0093) and required-file checks
below this branch are unmodified.

Part B: a CLOCK DRIFT line (clock_drift_line(), called from
build_context_lines() right after last_event_line()) -- field precedent
2026-07-23: a session's journal tail carried a ts LATER than the system
clock (a previous environment's clock ran ahead). When the tail event's
ts is more than 60s ahead of `now`, this prints "CLOCK DRIFT: last
journal ts is <N> min ahead of system clock -- new events will be
non-monotonic (D-0089: do not rewrite past lines)" so the mismatch is
visible instead of silently producing non-monotonic ts ordering on the
next append. Fail-open on an empty journal, a missing/blank tail ts, or
a tail ts that does not parse as the journal's naive-ISO format.
"""

import contextlib
import datetime
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

# N4 (critic t-027, carried forward unchanged): this import used to sit
# unguarded at module level -- a failure here (no yaml installed, a
# syntax error in preflight_quota.py, any exception at all) happened
# DURING IMPORT of this module itself, before main()'s try/except
# boundary even exists yet, and escaped as a bare traceback -- exactly
# the "session start breaks" failure mode this whole hook exists to
# prevent (spec: fail-open is a hard constraint, not best-effort).
# Deferring the failure into a stub that raises only when CALLED means
# main()'s single try/except (see its docstring for why it is
# deliberately the ONE boundary) now also covers import-time failures
# of this dependency, not just runtime ones.
_IMPORT_ERROR = None
try:
    from preflight_quota import (
        alias_provider_models,
        load_budgets,
        load_config,
        parse_ts,
        usage_in_window,
    )
except Exception as _e:  # noqa: BLE001 -- deliberately broad, see comment above
    _IMPORT_ERROR = _e

    def _reraise_import_error(*_args, **_kwargs):
        raise _IMPORT_ERROR

    alias_provider_models = _reraise_import_error
    load_budgets = _reraise_import_error
    load_config = _reraise_import_error
    parse_ts = _reraise_import_error
    usage_in_window = _reraise_import_error

MAX_LINES = 25
QUOTA_WINDOW_SECONDS = 86400

# D-0068/D-0038 boot-budget thresholds (bytes).
BOOT_WARN_THRESHOLD = 90000
BOOT_BREACH_THRESHOLD = 100000
BOOT_BUDGET_LIMIT = 100000

_ALWAYS_INCLUDE_BOOT_FILE = "CLAUDE.md"

# W2b-8 (D-0054/D-0065): CLAUDE.md's own personal ratchet, layered on
# top of the whole-boot-path thresholds above. CLAUDE_BREACH is the
# file's measured size at the START of the W2b form-refactor phase (a
# ratchet floor: the phase must not grow the file past its own
# starting point). CLAUDE_WARN = ceil(measured * 1.015 / 100) * 100,
# clamped to min(WARN, CLAUDE_BREACH - 300); the raw formula on the
# phase's final measured size (~36084 B) lands above that clamp floor,
# so the clamp fired -- a form-refactor that ends up near byte-neutral
# leaves no real growth margin. That is a recorded FINDING ("ratchet
# exhausted, W2c"), not a silent renumbering; see docs/tasks/
# 2026-08-18_w2b-transfer-maps.md for the measured inputs.
# W2c-4 re-derivation (WORD OF THE ARCHITECT 2026-08-20, not a silent
# raise): after the W2c diet the file grew by LEGITIMATE norms (node C
# F-58 branches, +535 B) to a measured 36102 B -- the old thresholds
# produced a permanent OVER on every SessionStart (the registered
# "guard trained to be ignored" class). Same W2b formula on the new
# measured size: WARN = ceil(36102*1.015/100)*100 = 36700; BREACH =
# WARN + 300. Ratchet discipline holds: raises happen only by
# operator word, recorded here and in the journal (t-538 window).
CLAUDE_BREACH = 37000
CLAUDE_WARN = 36700

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# D-0056a tier mapping: substring of the model id (lowercased) -> tier
# label. Order matters only in that each id is expected to match at
# most one of these; first match wins.
_MODEL_TIER_SUBSTRINGS = (
    ("fable", "Lead(top)"),
    ("opus", "critic-tier"),
    ("sonnet", "builder-tier"),
    ("haiku", "scout-tier"),
)

# D-0076: events that open/close a dispatch's lifecycle. A task_id is
# OPEN iff its LAST such event is 'delegated'. Events outside this set
# (dispatch_skipped, defect_found, lead_*, journal_created, calibrated)
# neither open nor close a task BY THEIR OWN TYPE -- but see _CLOSES_RE
# below: their `notes` field is still scanned for closes: tokens.
_OPEN_LIFECYCLE_EVENTS = {"delegated", "accepted", "rejected", "escalated", "decomposable"}

# Follow-up fix (t-133 remainder): open_dispatches() below used to read
# ONLY the event TYPE, never the `notes` field -- so a plain-English
# closing note ("Закрытие t-133: ...", CLAUDE.md's own convention for
# closing an open dispatch inside the next event's notes) was invisible
# to the scan, producing false OPEN DISPATCH lines for tasks a session
# had, in fact, already closed out in prose. Fix: a bare `closes:t-NNN`
# token in ANY event's notes (lifecycle or not) closes dispatch t-NNN.
# The format is deliberately exact -- no whitespace after the colon,
# lowercase literal, task id must start with `t-` -- the same "bare
# token right after the colon" contract as `replaces_worker:` (CLAUDE.md
# journal section: regex takes the first non-whitespace token, so loose
# punctuation right after the marker breaks the match by design).
#
# Left-anchored (critic-gate finding, t-133 remainder attempt 2): a bare
# `closes:` substring would otherwise match INSIDE a longer word too --
# `discloses:t-001` or `encloses:t-133` both contain the literal
# "closes:" and would silently close a task nobody meant to close (the
# dangerous direction: a false CLOSE hides a real phantom dispatch).
# `(?<!\w)` requires the character immediately before "closes:" to be
# either absent (start of string) or a non-word character -- so
# start-of-notes and punctuation/whitespace before the token are both
# legal, but a preceding letter/digit/underscore is not.
_CLOSES_RE = re.compile(r"(?<!\w)closes:(t-\d+)")


def _closes_task_ids(notes) -> list:
    """Extracts closes:t-NNN task ids from a notes field via findall.
    Returns [] for anything that is not a string (missing notes, or a
    malformed journal line where notes ended up a number/None in JSON)
    -- must never raise; open_dispatches() has no local try/except
    either, so this has to be safe on its own rather than relying on a
    boundary above it."""
    if not isinstance(notes, str):
        return []
    return _CLOSES_RE.findall(notes)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def journal_path(root: Path) -> Path:
    return Path(root) / "logs" / "routing-log.jsonl"


def read_journal_events(root: Path) -> list:
    path = journal_path(root)
    if not path.exists():
        return []
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def now_line(now: datetime.datetime = None) -> str:
    now = now or datetime.datetime.now()
    weekday = _WEEKDAYS[now.weekday()]
    return f"NOW: {now.strftime('%Y-%m-%d %H:%M:%S')} {weekday} (local system clock)"


def last_event_line(events: list) -> str:
    if not events:
        return "JOURNAL: empty or missing (logs/routing-log.jsonl)"
    e = events[-1]
    return (
        f"LAST EVENT: ts={e.get('ts')} event={e.get('event')}"
        f" agent={e.get('agent')} task_id={e.get('task_id') or '-'}"
    )


# VG-1 part B: threshold (seconds) above which the tail journal event's ts
# being AHEAD of the system clock is worth a line of its own, rather than
# silent noise from ordinary sub-second/sub-minute scheduling jitter
# between when an event was written and when this hook happens to run.
_CLOCK_DRIFT_THRESHOLD_SECONDS = 60


def clock_drift_line(events: list, now: datetime.datetime = None) -> str:
    """VG-1 part B (field precedent 2026-07-23: a session's journal tail
    carried ts=20:16:32 while the system clock read 19:45:56 -- a
    previous environment's clock ran ahead of this one). NOW and LAST
    EVENT are printed side by side already; this makes the DRIFT itself
    visible instead of leaving a session to notice the mismatch by eye
    and rediscover D-0089 the hard way: if the tail event's ts is MORE
    than _CLOCK_DRIFT_THRESHOLD_SECONDS ahead of `now`, any event this
    session appends will sit, by ts, BEFORE that tail line -- which is
    not a rewrite of the past (D-0089 is about literally editing old
    lines) but produces the same non-monotonic-journal symptom a reader
    would otherwise blame on a rewrite. Returns '' (no line) when the
    journal is empty, the tail event carries no/blank ts, that ts is not
    parseable as the journal's naive-ISO format, or the drift is at or
    under the threshold -- fail-open by construction, same contract as
    last_calibration_line()'s own parse_ts() use immediately above it (a
    ValueError/TypeError from parse_ts on a malformed ts is caught here;
    an ImportError/SyntaxError from the deferred preflight_quota import
    itself is deliberately NOT caught, for the same reason quota_lines()
    re-raises those two -- see this module's top-of-file N4 comment)."""
    if not events:
        return ""
    now = now or datetime.datetime.now()
    ts = events[-1].get("ts")
    if not ts:
        return ""
    try:
        last_ts = parse_ts(ts)
    except (ValueError, TypeError, AttributeError):
        return ""
    drift_seconds = (last_ts - now).total_seconds()
    if drift_seconds <= _CLOCK_DRIFT_THRESHOLD_SECONDS:
        return ""
    drift_minutes = round(drift_seconds / 60)
    return (
        f"CLOCK DRIFT: last journal ts is {drift_minutes} min ahead of system clock"
        " -- new events will be non-monotonic (D-0089: do not rewrite past lines)"
    )


def open_degradation_window(events: list):
    """Scans the WHOLE journal (not just the tail): an unclosed
    lead_degraded can be arbitrarily far back if lead_restored never
    followed (D-0039 p.4: a safety-reset can leave the window open with
    no restore event ever written). Pairs each lead_degraded with the
    next lead_restored in journal order; returns the ts of the
    currently-open one, or None if the last pair closed."""
    open_since = None
    for e in events:
        event = e.get("event")
        if event == "lead_degraded":
            if open_since is None:
                open_since = e.get("ts")
        elif event == "lead_restored":
            open_since = None
    return open_since


def open_dispatches(events: list) -> list:
    """A task_id is OPEN iff it has no `accepted` AND its LAST remaining
    event from _OPEN_LIFECYCLE_EVENTS is 'delegated' (D-0076: a delegated
    with no closing event is a phantom open dispatch -- the class-defect
    that motivated this hook line: a session wrote 'delegated' and never
    launched the worker). Returns those last-delegated event dicts sorted
    by ts ascending (oldest first). Continuation dispatches (critic-gate
    entry) and retries stay open until a closing event. No local
    try/except -- failures propagate to main()'s single fail-open
    boundary, like quota_lines().

    Closure by `accepted` is JOURNAL LAW, not event ordering: reopen
    after accepted is forbidden (D-0060, validator-enforced), so ANY
    accepted closes its task unconditionally -- regardless of where the
    line sits or what ts it carries. This is what survives both live
    journal anomalies, which lie in OPPOSITE directions: t-029 (orphan
    delegated inserted mid-file AFTER its accepted -- file position lies,
    ts is true) and t-007 (delegated ts written wrong, 13:05 vs actual
    ~12:26, admitted in the accepted's own notes -- ts lies, position is
    true). No (ts, position) ordering rule can resolve both; the law
    does not need to. For tasks WITHOUT an accepted, 'last' is judged by
    (ts, file position): max ts wins, file position only breaks exact ts
    ties (retro pairs -- D-0056b -- share one ts, and the closing line is
    written below the delegated one, so on a tie the later line wins).

    Follow-up fix (t-133 remainder): the check above only ever read
    event TYPE, so a prose closing note in a later event's `notes`
    ("Закрытие t-133: ...") was invisible to the scan -- 13 tasks that
    were, in fact, already closed out in the journal's own notes text
    still showed up as OPEN DISPATCH on boot. Fix: a bare `closes:t-NNN`
    token (see _CLOSES_RE) in ANY event's notes -- lifecycle or not,
    e.g. `calibrated`, `dispatch_skipped` -- is a closing TOUCH of that
    task, keyed by the marker-carrying event's own (ts, file_idx). Per
    task_id, every touch is compared as (ts, idx, sub): a real lifecycle
    event contributes sub=0, a closes: marker contributes sub=1 at the
    SAME (ts, idx) as the event it sits in -- so at an exact tie the
    marker outranks the lifecycle event it came from. The task is OPEN
    iff its overall-latest touch is a real `delegated` event: a later
    marker closes it (even one sitting in an unrelated event's notes); a
    later `delegated` (retry/replacement) reopens it past an earlier
    marker; and -- documented as a deliberate contract, not a bug -- a
    closes:t-X token placed in t-X's OWN delegated event's notes closes
    that same event, because its marker-touch key ties the lifecycle key
    and the marker wins ties. `accepted` does not participate in this
    ts/idx comparison at all: it stays the unconditional law above,
    checked first and independent of any marker."""
    accepted_tids = set()
    lifecycle_last = {}  # tid -> (ts_str, file_idx, event_dict): last real lifecycle touch
    close_last = {}  # tid -> (ts_str, file_idx): last closes: marker touch
    for idx, e in enumerate(events):
        ts_key = (str(e.get("ts") or ""), idx)

        for closed_tid in _closes_task_ids(e.get("notes")):
            if closed_tid not in close_last or ts_key > close_last[closed_tid]:
                close_last[closed_tid] = ts_key

        event = e.get("event")
        if event not in _OPEN_LIFECYCLE_EVENTS:
            continue
        tid = e.get("task_id")
        if not tid:
            continue
        if event == "accepted":
            accepted_tids.add(tid)
            continue
        if tid not in lifecycle_last or ts_key > lifecycle_last[tid][:2]:
            lifecycle_last[tid] = (ts_key[0], ts_key[1], e)

    opens = []
    for tid, (ts, idx, e) in lifecycle_last.items():
        if tid in accepted_tids:
            continue
        if e.get("event") != "delegated":
            continue
        marker = close_last.get(tid)
        if marker is not None and marker >= (ts, idx):
            continue
        opens.append(e)
    opens.sort(key=lambda e: str(e.get("ts") or ""))
    return opens


def open_dispatch_lines(events: list) -> list:
    """Up to 3 'OPEN DISPATCH: t-NNN agent=X since <ts>' lines (oldest
    first) plus one summary line when more than 3 are open. task_id,
    agent and ts are journal-sourced -> each goes through _ascii_sanitize
    (cp1251-console invariant). Empty when nothing is open."""
    opens = open_dispatches(events)
    if not opens:
        return []
    lines = []
    for e in opens[:3]:
        tid = _ascii_sanitize(str(e.get("task_id") or "-"))
        agent = _ascii_sanitize(str(e.get("agent") or "-"))
        ts = _ascii_sanitize(str(e.get("ts") or "-"))
        lines.append(f"OPEN DISPATCH: {tid} agent={agent} since {ts}")
    if len(opens) > 3:
        lines.append(f"OPEN DISPATCHES: {len(opens)} total, {len(opens) - 3} more not shown")
    return lines


def last_calibration_line(events: list, now: datetime.datetime = None) -> str:
    now = now or datetime.datetime.now()
    cal_events = [e for e in events if e.get("event") == "calibrated"]
    if not cal_events:
        return "Last calibration: NONE"
    ts = cal_events[-1].get("ts")
    try:
        days = (now - parse_ts(ts)).days
        return f"Last calibration: {ts} ({days} days ago)"
    except (ValueError, TypeError):
        return f"Last calibration: {ts} (age unknown -- unparsable ts)"


def gemini_aliases(config: dict) -> list:
    """Gateway aliases whose RAW litellm_params.model starts with
    'gemini/' -- Gemini free tier limits per-model requests/day, not
    tokens (spec: "лимиты не хардкодить, просто 'requests last 24h: N'")."""
    aliases = []
    for entry in config.get("model_list", []) or []:
        raw_model = (entry.get("litellm_params") or {}).get("model", "")
        if raw_model.startswith("gemini/"):
            name = entry.get("model_name")
            if name:
                aliases.append(name)
    return aliases


def quota_lines(gateway_root: Path, now: datetime.datetime = None) -> list:
    """One line per 86400s-window alias in budgets.yaml (used/limit +
    up to 3 nearest release moments), plus one line per Gemini alias's
    24h request count.

    t-278 п.6: an EXISTING-but-unparseable config.yaml (corrupt YAML
    content, NOT absence -- preflight_quota.load_config() only guards
    absence, per its own docstring, and still lets yaml.YAMLError
    propagate on corrupt content) is now caught HERE, locally, and
    reported as a single "quota: config unreadable (<reason>)" line
    instead of propagating uncaught to main()'s single fail-open
    boundary. This is a DELIBERATE, NARROW reversal of this file's
    general "half a context is worse than none" principle (see main()'s
    docstring) for JUST this one section: a session losing NOW/MODEL/
    LAST EVENT/BOOT BUDGET too, over a fault scoped entirely to the
    quota subsystem's own config file, is a strictly worse outcome than
    a full context with one line explicitly marked broken. Any OTHER,
    genuinely unforeseen failure below this point (e.g. an unreadable
    requests.db) still propagates unchanged to main()'s outer boundary
    -- this reversal was originally scoped to load_config() alone; a
    malformed budgets.yaml is a DIFFERENT (and now closed) case:
    t-278-дельта п.3 gave preflight_quota.load_budgets() its OWN
    internal parse-guard (see that function's docstring) -- it never
    raises on corrupt content in the first place, so there is nothing
    left here to catch for that path. This function surfaces
    load_budgets()'s honest "_parse_error" key (if present) as one
    additional "quota: budgets unreadable (<reason>)" line -- see the
    lines below load_config()'s try/except for that wiring; unlike the
    config.yaml case, a broken budgets.yaml does NOT blank the rest of
    quota_lines()'s output, because the failure is caught INSIDE
    load_budgets() itself, not by unwinding out of this function.
    ImportError/SyntaxError are deliberately RE-RAISED,
    not caught here (N4, critic t-027): those mean the quota subsystem
    ITSELF is unusable (missing yaml, a broken preflight_quota sibling
    module) -- a different failure class from "this config.yaml's own
    content is broken" -- and must still reach main()'s single
    fail-open boundary unchanged."""
    lines = []
    try:
        config = load_config(gateway_root)
    except (ImportError, SyntaxError):
        # N4 (critic t-027): an import-time failure of the preflight_quota
        # dependency itself (missing yaml, a broken sibling module) is a
        # DIFFERENT failure class from "this config.yaml's content is
        # broken" -- it means the whole quota subsystem is unusable, not
        # just this one file, and must still reach main()'s single
        # fail-open boundary unchanged (the deferred-raise stub at import
        # time surfaces exactly these two exception types -- see the
        # module-level _IMPORT_ERROR handling above).
        raise
    except Exception as e:
        # Single-line, ASCII-safe marker: yaml.YAMLError's own str() is
        # typically MULTI-LINE (a "problem" line plus a "in <file>, line
        # N, column N" context line) -- splitlines()[0] plus
        # _ascii_sanitize keep this section's failure honest without
        # letting it inject extra lines or non-ASCII bytes into the
        # console output (same invariant as MODEL/OPEN DISPATCH/WIRING).
        text = str(e).strip()
        reason = text.splitlines()[0] if text else type(e).__name__
        return [f"quota: config unreadable ({_ascii_sanitize(reason, 150)})"]
    budgets = load_budgets(gateway_root)
    mapping = alias_provider_models(config)

    # t-278-дельта п.3: load_budgets() теперь само гардит парсинг
    # budgets.yaml изнутри (см. её докстринг в preflight_quota.py) и
    # честно возвращает "_parse_error" вместо исключения -- этот
    # вызывающий ИМЕЕТ строку вывода для причины (в отличие от
    # "минимума" спеки), поэтому показывает её: остальные секции
    # (per-alias QUOTA/REQUESTS, построенные из config, не budgets)
    # печатаются штатно рядом -- в отличие от битого config.yaml (п.6),
    # битый budgets.yaml не гасит quota_lines() целиком, поскольку сбой
    # локализован ИЗНУТРИ load_budgets(), а не пойман снаружи неё.
    budgets_error = budgets.get("_parse_error")
    if budgets_error:
        lines.append(f"quota: budgets unreadable ({_ascii_sanitize(str(budgets_error), 150)})")

    for alias, windows in (budgets.get("quota_windows") or {}).items():
        matching = [w for w in windows if w.get("window_seconds") == QUOTA_WINDOW_SECONDS]
        if not matching or alias not in mapping:
            continue
        limit = matching[0].get("limit_tokens")
        provider_model = mapping[alias]
        usage = usage_in_window(gateway_root, provider_model, QUOTA_WINDOW_SECONDS, now)
        releases = sorted(
            ts + datetime.timedelta(seconds=QUOTA_WINDOW_SECONDS) for ts, _tok in usage["rows"]
        )
        next_releases = [r.strftime("%H:%M") for r in releases[:3]]
        releases_str = ", ".join(next_releases) if next_releases else "none pending"
        lines.append(
            f"QUOTA {alias}: {usage['used_tokens']}/{limit} tok (24h);"
            f" next release(s): {releases_str}"
        )

    for alias in gemini_aliases(config):
        provider_model = mapping.get(alias)
        if not provider_model:
            continue
        usage = usage_in_window(gateway_root, provider_model, QUOTA_WINDOW_SECONDS, now)
        lines.append(f"REQUESTS {alias}: {len(usage['rows'])} last 24h")

    return lines


# --- BEGIN stdin-deadline helper (П4; ЛОКАЛЬНАЯ копия, общий модуль запрещён) ---
_STDIN_DEADLINE_DEFAULT = 10.0
_STDIN_DEADLINE_MAX = 600.0
_STDIN_DEADLINE_ENV = "OSLLM_STDIN_TIMEOUT"


def _stdin_deadline_seconds():
    """Секунды дедлайна: env-переопределение, иначе дефолт. Невалидное,
    нечисловое, <=0 и > _STDIN_DEADLINE_MAX -> дефолт; режима
    "0 = ждать вечно" НЕТ намеренно (он воскрешает саму дыру)."""
    try:
        value = float(os.environ.get(_STDIN_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDIN_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDIN_DEADLINE_MAX):
        return _STDIN_DEADLINE_DEFAULT
    return value


def _read_stdin_bytes_deadline():
    """(bytes, timed_out). Читает stdin до EOF, но не дольше дедлайна.
    Форма кроссплатформенная: select/poll на Windows не работает с
    пайпами, поэтому читает поток-демон, а дедлайн держит join(timeout).
    TTY -> b"" без чтения (прежний guard трёх файлов, теперь у всех).
    Любая ошибка чтения -> b"" (fail-open, как везде в этих хуках)."""
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
# --- END stdin-deadline helper ---

# P4/В3.1 (К7-эмпирика): a background reader thread left blocked on the REAL
# stdin buffered-reader at normal interpreter shutdown crashes with "Fatal
# Python error: _enter_buffered_busy" instead of exiting cleanly (reproduced
# empirically: this file's own main() does NOT abort on a stdin timeout --
# read_stdin_payload() returns None and main() keeps building/printing the
# full context, same as its empty-input path -- so the crash surfaces LATER,
# at main()'s own normal completion, not at the read call site itself).
# read_stdin_payload() is UNCHANGED in return contract (still returns None,
# safe in-process); it only flips this module-level flag, which the actual
# __main__ script-exit path below checks AFTER main() has fully returned.
_STDIN_DEADLINE_STATE = {"hit": False}


# ---------------------------------------------------------------------------
# New in b3: MODEL line (D-0056a)
# ---------------------------------------------------------------------------


def read_stdin_payload():
    """Reads and JSON-parses stdin, but ONLY when stdin is not a TTY.
    A SessionStart hook receives the harness's JSON on stdin; a human
    running this script by hand from an interactive shell has no piped
    input, and blocking on the read there would hang forever -- the
    TTY guard (now inside _read_stdin_bytes_deadline(), P4) is what
    keeps both modes safe, and a non-TTY read that never reaches EOF is
    now bounded by OSLLM_STDIN_TIMEOUT (P4 stdin-deadline batch) instead
    of blocking forever. Any failure (unreadable stdin, empty input,
    invalid JSON, a stdin deadline) returns None rather than raising;
    callers treat None exactly like "no model info". P4/K10: byte read
    via the deadline helper + decode("utf-8", "replace"), replacing the
    former direct sys.stdin.read() (removes the t-159-class carrier:
    this hook now reads bytes and decodes explicitly, same as the other
    12 P4 siblings, instead of going through Python's platform-encoding
    text layer)."""
    raw_bytes, timed_out = _read_stdin_bytes_deadline()
    if timed_out:
        _STDIN_DEADLINE_STATE["hit"] = True
        sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
        return None
    if not raw_bytes:
        return None
    data = raw_bytes.decode("utf-8", "replace")
    if not data or not data.strip():
        return None
    try:
        payload = json.loads(data)
    except Exception:
        return None
    # F-61/B4: guard a non-dict root HERE, at the read boundary (образец
    # journal_echo.py:1885's `if not isinstance(payload, dict): return 0`)
    # instead of trusting every caller to re-check -- valid JSON can be a
    # list/str/number/bool/null just as easily as an object, and callers
    # downstream (extract_model_id/extract_source) should never have to
    # special-case a non-dict shape arriving from here. NOTE (spec/reality
    # divergence, see report): the same acceptance key also names a
    # "не-dict tool_input" guard, mirroring dod_track/critic_snapshot's
    # PostToolUse payload shape -- this hook is SessionStart-only
    # (.claude/settings.json) and its payload never carries a tool_input
    # key at all, so there is no site to apply that half of the guard to.
    return payload if isinstance(payload, dict) else None


def extract_model_id(payload):
    """Looks for the model id under, in order: top-level "model" as a
    string; top-level "model" as a dict with an "id" or "model" key;
    top-level "model_id". Returns None if none of these yield a
    non-empty string (covers missing stdin, non-dict payload, and
    payloads that simply don't carry a model at all)."""
    if not isinstance(payload, dict):
        return None

    model = payload.get("model")
    if isinstance(model, str) and model:
        return model
    if isinstance(model, dict):
        for key in ("id", "model"):
            value = model.get(key)
            if isinstance(value, str) and value:
                return value

    model_id = payload.get("model_id")
    if isinstance(model_id, str) and model_id:
        return model_id

    return None


# ---------------------------------------------------------------------------
# AUTO-BOOT (D-0103, sibling copy per D-0069 -- Lead places this on the live
# tools/session_context.py path at acceptance): the operator opted into
# automatic full boot so a fresh session no longer has to type "стартуй с
# бут" by hand. FIRES on a genuinely fresh SessionStart ("startup"/"clear")
# OR when the source is missing/unrecognized -- fail TOWARD booting: a
# source value this hook does not know about (a harness field rename, a new
# source string added upstream) must not silently turn the feature off.
# DOES NOT fire on "resume"/"compact" -- those already carry state via the
# compact/resume summary, and re-injecting the boot directive there is pure
# waste (D-0103 rationale: ~100KB every time).
# ---------------------------------------------------------------------------


def extract_source(payload) -> str | None:
    """Looks for the SessionStart "source" field -- mirrors
    extract_model_id's defensive style. Returns payload.get("source")
    only when payload is a dict AND that value is a non-empty string;
    every other shape (non-dict payload, missing key, empty string,
    non-string value) returns None rather than raising."""
    if not isinstance(payload, dict):
        return None
    source = payload.get("source")
    if isinstance(source, str) and source:
        return source
    return None


# Sources that mean "state already carries over" -- auto-boot must NOT
# fire for these (spec: re-injecting the directive after resume/compact
# wastes ~100KB every time the compact summary already covers).
_AUTOBOOT_NO_FIRE_SOURCES = {"resume", "compact"}

# EXACT text (ASCII only, this file's hard invariant -- do not translate to
# Cyrillic): the AUTO-BOOT directive block, printed verbatim, one list
# entry per line.
_AUTOBOOT_DIRECTIVE_LINES = [
    "AUTO-BOOT (D-0103, operator opted in): fresh session start -- run the full boot now.",
    "  Read the files listed in BOOT.md in order, then produce a Boot Report per",
    "  PROCESS/BOOT_REPORT_PROTOCOL.md and STOP for work authorization.",
    "  (Boot recovery is not work authorization -- BOOT_REPORT_PROTOCOL rule 4.",
    "  This directive fires on a fresh start only, not after resume/compact.)",
]


def autoboot_lines(source) -> list:
    """Returns the AUTO-BOOT directive block (_AUTOBOOT_DIRECTIVE_LINES,
    verbatim) when auto-boot SHOULD fire for this SessionStart `source`,
    else []. Fires when source is "startup" or "clear", OR when source is
    None / any other unrecognized string (fail-toward-booting -- see the
    module comment above this section). Does NOT fire when source is
    "resume" or "compact"."""
    if source in _AUTOBOOT_NO_FIRE_SOURCES:
        return []
    return list(_AUTOBOOT_DIRECTIVE_LINES)


# D-0099 (2026-08-04): sentinel "config_text не передан явно" -- model_tier()
# reads the REAL delegation.config.yaml (via mechanism_gate.CONFIG_PATH)
# only when the caller does not override config_text at all; an explicit
# config_text=None means "нет конфига" (regression pin below) regardless
# of whether that None came from a real absent file or a test injecting
# it on purpose -- the two are deliberately the SAME signal, matching how
# tools/journal_validator.py / tools/mechanism_gate.py already treat an
# injected None (see their own test suites).
_LEAD_BINDING_CONFIG_UNSET = object()


def _lead_binding_family_for_label(config_text) -> str | None:
    """D-0099 binding-aware label resolution: returns the Lead-binding's
    tier family (fable/opus/sonnet/haiku), or None when there is genuinely
    no binding info to compare against -- "нет конфига" (config_text is
    None, whether real-disk-absent or explicitly injected) OR ANY
    exception while resolving it (missing yaml, a broken mechanism_gate
    import, a corrupt file read -- see model_tier()'s own docstring for
    the full fail-open contract). Both collapse to the same None signal on
    purpose: model_tier() treats None here as "today's static label,
    unchanged" either way. The mechanism_gate import happens HERE, inside
    the try, not at this module's top level -- this hook must never fail
    to import over a sibling tool being broken/missing (same discipline as
    the local `import wiring_check as _wc` inside wiring_lines() above)."""
    if config_text is None:
        return None
    try:
        import mechanism_gate as mg
        if config_text is _LEAD_BINDING_CONFIG_UNSET:
            config_text = (mg.CONFIG_PATH.read_text(encoding="utf-8", errors="replace")
                           if mg.CONFIG_PATH.exists() else None)
            if config_text is None:
                return None
        binding = mg.resolve_lead_binding(config_text)
        return mg.lead_family(binding)
    except Exception:
        return None


def model_tier(model_id: str, config_text=_LEAD_BINDING_CONFIG_UNSET) -> str:
    """D-0099 (2026-08-04): binding-aware tier label. The base label is
    still the static fable/opus/sonnet/haiku -> Lead(top)/critic-tier/
    builder-tier/scout-tier mapping (unchanged, still the fallback on any
    failure below -- fail-open, this is a SessionStart hook, D-0056a).
    On top of that, when the Lead-binding (roles.lead in
    delegation.config.yaml, resolved via mechanism_gate) is known:
      - the session's OWN family equals the binding's family -> "Lead(bound)"
        (D-0099: the full Lead is defined by the BINDING, not the name
        "fable" -- a session running the model the binding names IS the
        full Lead, whatever that model's static substring label would say).
      - the session is fable but the binding is NOT fable -> "top-reserve"
        (fable is still the standing top-tier MODEL, but Lead-function
        authority has moved to the binding; fable stays available as a
        reserve, not the acting Lead).
      - anything else -> the static label, unchanged.
    config_text is injectable for tests (explicit override, incl. explicit
    None for "нет конфига"); the default sentinel reads the REAL
    delegation.config.yaml lazily via mechanism_gate.CONFIG_PATH (absent
    file -> None -> "нет конфига" -> static label, same as before this
    change existed)."""
    low = model_id.lower()
    session_family = None
    static_label = "unknown"
    for substr, tier in _MODEL_TIER_SUBSTRINGS:
        if substr in low:
            session_family = substr
            static_label = tier
            break
    if session_family is None:
        return static_label  # "unknown" -- nothing to compare a binding against

    binding_family = _lead_binding_family_for_label(config_text)
    if binding_family is None:
        return static_label  # "нет конфига" (real or injected) / any failure -- regression pin

    if session_family == binding_family:
        return "Lead(bound)"
    if session_family == "fable":  # binding_family here is known != "fable" (equality already handled above)
        return "top-reserve"
    return static_label


def _ascii_sanitize(s: str, max_len: int = 80) -> str:
    """Fix for the class "an output line built from a NON-hardcoded
    source must stay ASCII/single-line before a cp1251 console" (critic
    t-043). MODEL was this module's only externally-sourced input at the
    time that class was named; D-0076's OPEN DISPATCH lines are the
    second consumer the t-043 docstring flagged as a future possibility
    -- task_id/agent/ts there are journal-sourced (a session could in
    principle write anything into those fields), so they route through
    this same helper rather than getting a parallel one."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # control chars incl. \n \r \t
    s = s.encode("ascii", "replace").decode("ascii")
    return s[:max_len]


def model_line(stdin_payload=None, config_text=_LEAD_BINDING_CONFIG_UNSET) -> str:
    """F-37 (2026-07-12): the payload model is the harness's SessionStart
    DECLARATION, not a measurement -- it can be stale (observed live:
    payload said sonnet-4-6 while the session actually ran opus-4-8;
    the proxy log was the ground truth). A present-but-stale id stated
    confidently is worse than an absent one, so the line now carries
    the "declared by harness, not measured" marker in both branches.
    An in-hook measured cross-check is NOT implementable at SessionStart
    time: the session's own first request has not landed in requests.db
    yet, so the freshest rows there belong to a previous session --
    recorded limitation, not an oversight. The measured verification
    duty stays where it already lives: D-0056 (first-Lead-action check
    in-session) and calibration check 5 (transcripts vs windows);
    liveness of this line -- check 13(zh).

    config_text (B1(b)/B5, пересдача D-0099, 2026-08-04): threaded
    straight through to model_tier() -- SAME sentinel default
    (_LEAD_BINDING_CONFIG_UNSET, reads the real delegation.config.yaml
    lazily) and same explicit-None-means-"нет конфига" semantics. Also
    drives the trailing "Lead tier = <...>" clause below (B5): no longer
    a hardcoded "fable" literal -- the ACTUAL bound family (or "fable"
    when there is no resolvable binding, same fallback model_tier() itself
    uses, regression pin for "без конфига -- как сегодня")."""
    model_id = extract_model_id(stdin_payload)
    if not model_id:
        return "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    sanitized = _ascii_sanitize(model_id)
    if not sanitized:
        # whitespace-only (or entirely-stripped) model id: same fallback
        # as "no model id at all" -- there is nothing left to report.
        return "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    tier = model_tier(sanitized, config_text)
    # B5: binding-aware "Lead tier" clause -- same resolution/fail-open
    # helper model_tier() itself uses; unresolvable (no config, non-Claude
    # binding, or any exception) falls back to the literal "fable", byte-
    # for-byte the same text this line always carried (regression pin).
    lead_tier_display = _lead_binding_family_for_label(config_text) or "fable"
    return (
        f"MODEL: {sanitized} -> tier {tier}"
        f" (declared by harness, not measured -- F-37; Lead tier = {lead_tier_display})"
    )


# ---------------------------------------------------------------------------
# New in b3: BOOT BUDGET line(s) (D-0068/D-0038)
# ---------------------------------------------------------------------------


def boot_path_files(root: Path) -> list:
    """Parses BOOT.md's own "Read X.md" lines for the boot-path file
    list (BOOT.md stays the single owner of that list -- this hook only
    mirrors it for budget arithmetic, it does not maintain a second copy
    of the sequence), then always appends CLAUDE.md, which the harness
    auto-loads separately from the BOOT.md sequence (D-0041) but still
    counts against the same boot-budget bytes. Missing BOOT.md (or an
    unreadable one) yields just the always-included CLAUDE.md, not an
    exception -- callers still get a usable, if degraded, budget line."""
    boot_md = Path(root) / "BOOT.md"
    names = []
    try:
        text = boot_md.read_text(encoding="utf-8")
    except OSError:
        text = ""
    for m in re.finditer(r"Read ([A-Z_]+\.md)", text):
        name = m.group(1)
        if name not in names:
            names.append(name)
    if _ALWAYS_INCLUDE_BOOT_FILE not in names:
        names.append(_ALWAYS_INCLUDE_BOOT_FILE)
    return names


def boot_budget_lines(root: Path) -> list:
    """Sums the byte size of every boot-path file that exists (a
    missing file counts as 0 bytes toward the total, and is called out
    by name so the gap is visible rather than silently absorbed into a
    lower total). Emits one summary line always, plus a top-3-by-size
    breakdown (one line each, "  <bytes>  <file>") whenever the total
    crosses either the WARN (>90000) or BREACH (>100000) threshold from
    D-0068/D-0038."""
    root = Path(root)
    names = boot_path_files(root)

    sizes = []
    missing = []
    for name in names:
        try:
            size = (root / name).stat().st_size
        except OSError:
            size = 0
            missing.append(name)
        sizes.append((name, size))

    total = sum(size for _name, size in sizes)
    base = f"BOOT BUDGET: {total} bytes / {BOOT_BUDGET_LIMIT} ({len(names)} files)"
    missing_suffix = "".join(f" [missing: {name}]" for name in missing)

    if total > BOOT_BREACH_THRESHOLD:
        # Informs the Boot Report's Next Required Action line; NOT an
        # auto-run command — boot recovery is not work authorization
        # (BOOT_REPORT_PROTOCOL rule 4; precedent 2026-07-15: a session
        # read the old "run boot-diet skill" wording as an imperative
        # and executed the diet before the Boot Report).
        status_suffix = " BREACH -> boot-diet due (D-0068; report first, operator word starts it)"
    elif total > BOOT_WARN_THRESHOLD:
        status_suffix = " WARN"
    else:
        status_suffix = ""

    # W2b-8: CLAUDE.md's own personal ratchet suffix -- printed ALWAYS
    # (unlike the WARN/BREACH pieces above, which only appear once the
    # whole boot path is over threshold). Breach of THIS threshold is
    # its own, narrower signal: only the CLAUDE layer of boot-diet is
    # due, not a full three-layer diet (.claude/skills/boot-diet/
    # SKILL.md). Comparison is strictly ">", matching BOOT_WARN/BREACH
    # above; a missing CLAUDE.md prints "missing", never "under budget".
    claude_size = next(
        (size for name, size in sizes if name == _ALWAYS_INCLUDE_BOOT_FILE), 0
    )
    if _ALWAYS_INCLUDE_BOOT_FILE in missing:
        claude_suffix = f" | {_ALWAYS_INCLUDE_BOOT_FILE}: missing"
    else:
        claude_suffix = f" | {_ALWAYS_INCLUDE_BOOT_FILE}: {claude_size}/{CLAUDE_WARN}"
        if claude_size > CLAUDE_WARN:
            claude_suffix += " OVER -> boot-diet (CLAUDE layer)"

    lines = [base + missing_suffix + status_suffix + claude_suffix]

    if status_suffix:
        top3 = sorted(sizes, key=lambda t: t[1], reverse=True)[:3]
        for name, size in top3:
            lines.append(f"  {size}  {name}")

    return lines


# ---------------------------------------------------------------------------
# Staged addition: WIRING-INTEGRITY block (N1, docs/tasks/
# 2026-07-21_validation-import.md). Three independent, read-only checks:
#
#   (a) git-channel   -- core.hooksPath resolves to <root>/.githooks AND
#                         both required git hook files exist under it.
#   (b) harness-channel -- every "python tools/<file>.py" hook command in
#                         .claude/settings.json names a file that exists
#                         and imports cleanly.
#   (c) python-channel -- shutil.which("python") finds an interpreter on
#                         THIS process's PATH.
#
# Each channel function turns its OWN known failure modes into WARNING
# detail strings rather than raising -- wiring_lines() below combines
# all three and additionally wraps the whole combination in one local
# try/except (spec point 3: a wiring-block failure must degrade to a
# WARNING line, not blank out the rest of build_context_lines() via
# main()'s outer boundary).
#
# ASCII invariant (Lead ruling, N1 spec correction): every WIRING line
# stays plain ASCII English, same as the rest of this file -- an earlier
# draft used the spec's illustrative Cyrillic wording verbatim, which
# conflicted with this file's own "Every line built here is plain ASCII"
# constraint (t-027/b3/D-0076); the Lead resolved it in favor of the
# existing invariant. Hardcoded text below is therefore English by
# construction, and every DYNAMIC piece that lands in a WIRING line
# (paths, raw git config output, raw command strings, exception class
# names) is routed through _ascii_sanitize before formatting -- same
# helper and same rationale as MODEL/OPEN DISPATCH above: a value this
# module does not fully control (a path containing non-ASCII characters,
# an unexpected exception __str__) must not be able to break the ASCII
# invariant or print a stray unbounded-length line.
# ---------------------------------------------------------------------------

_GITHOOKS_DIRNAME = ".githooks"
_REQUIRED_GITHOOKS = ("pre-commit", "commit-msg")
_SETTINGS_RELPATH = Path(".claude") / "settings.json"

# _ascii_sanitize's own default (80) is sized for single-token MODEL/OPEN
# DISPATCH content; a WIRING line legitimately carries a full repo path
# plus an explanatory clause, so the final backstop pass in wiring_lines()
# uses this wider bound instead. Per-component values (paths, commands,
# exception class names) are already capped tighter (120-150) before
# being interpolated into a line -- this is the outer cap on the WHOLE
# finished line, not the only one.
_WIRING_LINE_MAX_LEN = 300

# The one command shape every hook line in .claude/settings.json actually
# uses today (CLAUDE.md command-hygiene rule 2's canonical form): exactly
# "python tools/<file>.py", no extra flags, forward slashes. Anything
# else -- a different interpreter, extra arguments, a path outside
# tools/ -- is reported as an honest "unparsed command" WARNING (spec
# point 2б) rather than guessed at. `[^/\\]+` (not `[\w ]+`) deliberately
# allows spaces in the filename so a path-with-spaces command is still
# recognized and checked, not silently misparsed.
_HOOK_COMMAND_RE = re.compile(r"^python tools/([^/\\]+\.py)$")

# VG-1 part A: a fact string returned by _try_hookspath_autofix() on a
# CONFIRMED success is prefixed with this marker so wiring_lines() can
# tell it apart from an ordinary warning fact and render it as
# "WIRING AUTOFIX: ..." instead of "WIRING WARNING: ...". No other
# git/harness-channel fact ever starts with this literal string.
_AUTOFIX_FACT_PREFIX = "AUTOFIX: "


def _try_hookspath_autofix(root: Path, reason: str) -> str:
    """VG-1 part A: core.hooksPath came back UNSET -- before falling back
    to the plain 'core.hooksPath not set' WARNING, attempt the one-line
    self-heal `git config --local core.hooksPath .githooks` (relative
    path, LOCAL repo config only -- never --global/--system, per the
    spec's explicit constraint) and recheck.

    Р5(в) ORDER (2026-08-19, t-522, docs/tasks/2026-08-19_q503-
    remediation-spec.md node N2): the required .githooks/* files are
    checked for presence FIRST, BEFORE the `git config` write is even
    attempted -- not after the write, as an earlier version of this
    function did. Writing hooksPath at a directory whose hook files
    don't exist would "succeed" as a git operation while leaving the
    wiring exactly as broken as before, AND it would leave behind a
    config value nothing here can attribute or roll back afterward (a
    later run seeing hooksPath already set to .githooks has no way to
    tell "a human configured this deliberately" from "the autofix wrote
    it while the required files were still missing"). Checking first
    means that ambiguous, unrecoverable state is never CONSTRUCTED in
    the first place: on a missing-files finding, the `git config` write
    call is never made at all, and hooksPath is left exactly as this
    run found it (unset) -- the caller's own unconditional per-file
    "hook file missing" warning loop (git_hooks_channel, independent of
    this function) remains the safety net that keeps reporting the gap
    to the operator on every subsequent run, including the case where
    hooksPath was ALREADY correctly configured by someone else earlier
    and the files were deleted afterward.

    Returns the AUTOFIX fact (_AUTOFIX_FACT_PREFIX + "core.hooksPath set
    to .githooks") on a confirmed success: both required hook files were
    already present on disk under .githooks/ BEFORE the write was even
    attempted, AND the `git config` write itself then exited 0. Any
    other outcome returns the ORIGINAL 'core.hooksPath not set' warning
    fact with a suffix -- covering the three failure causes named in
    the spec: the required hook files missing (caught BEFORE any write
    is attempted -- suffix "; autofix skipped: ...", nothing was even
    tried), git itself unavailable/erroring (the write call raises --
    suffix "; autofix failed: ..."), and the config being unwritable
    e.g. read-only (the write call exits non-zero -- suffix "; autofix
    failed: ..."). Never raises -- same fail-open contract as the rest
    of this channel.

    Deliberately attempted ONLY for the UNSET case -- NOT when
    core.hooksPath already resolves to some OTHER path (that branch,
    handled entirely by the caller, never calls this function): an
    already-present value is somebody's explicit prior configuration
    (human or an earlier session), silently overwriting it is exactly
    the harm the spec's carve-out exists to prevent ("не перетирать
    чужой выбор молча"). Only a genuinely unset hooksPath is treated as
    "nothing to preserve, safe to wire up automatically"."""
    base_warning = f"core.hooksPath not set -- {reason}"

    missing = [
        name
        for name in _REQUIRED_GITHOOKS
        if not (root / _GITHOOKS_DIRNAME / name).is_file()
    ]
    if missing:
        missing_str = _ascii_sanitize(", ".join(missing), 120)
        return (
            f"{base_warning}; autofix skipped: required hook file(s)"
            f" missing under {_GITHOOKS_DIRNAME}/: {missing_str}"
            f" (git config left untouched -- writing core.hooksPath at a"
            f" directory with no hooks would create state this run"
            f" cannot roll back)"
        )

    try:
        set_result = subprocess.run(
            ["git", "config", "--local", "core.hooksPath", str(_GITHOOKS_DIRNAME)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        detail = _ascii_sanitize(f"git config write failed ({type(e).__name__})", 120)
        return f"{base_warning}; autofix failed: {detail}"

    if set_result.returncode != 0:
        stderr_lines = (set_result.stderr or "").strip().splitlines()
        raw_detail = stderr_lines[0] if stderr_lines else f"exit code {set_result.returncode}"
        detail = _ascii_sanitize(raw_detail, 120)
        return f"{base_warning}; autofix failed: git config write error ({detail})"

    return f"{_AUTOFIX_FACT_PREFIX}core.hooksPath set to {_GITHOOKS_DIRNAME}"


def git_hooks_channel(root: Path) -> list:
    """git-channel: core.hooksPath must resolve to <root>/.githooks, AND
    both .githooks/pre-commit and .githooks/commit-msg must exist --
    otherwise journal_validator/mechanism_gate never run on commits at
    all (silent death, class F-7). Returns a list of WARNING detail
    strings (empty = fully wired). The hooksPath comparison and the
    required-files check are independent and BOTH always evaluated (the
    spec's "И" is a conjunction of two separately-reportable facts, not
    a short-circuit) -- required files are always checked under the
    repo's OWN .githooks/, regardless of what hooksPath is misconfigured
    to, because that is the directory this repo actually maintains.
    Never raises: git being absent, the subprocess call failing, or any
    other problem while reading the config is itself folded into one
    WARNING string here (a more specific message than the generic one
    wiring_lines()'s own try/except would produce).

    THIRD, independent fact (D-0093, Dog range): a hook file existing
    and readable on disk is not enough -- git only executes a hook that
    is BOTH tracked as executable in the index (mode 100755) AND
    present on disk; a hook committed as 100644 is silently skipped by
    git on Linux clones (Windows/NTFS carries no meaningful exec bit at
    all, so this cannot be checked via the filesystem -- deliberately
    read from `git ls-files -s`, the INDEX, not os.stat()). Checked via
    the same subprocess idiom as the hooksPath call above: never raises,
    a failed invocation folds into one WARNING string same as the
    hooksPath failure path. Two sub-facts per required hook, both
    reported when true: not present in the index at all (untracked --
    a clone gets no gate whatsoever, worse than non-executable), or
    present with a mode other than 100755 (committed non-executable).

    B8 FIX (2026-08-10, sibling of the same class fixed in
    toolkit/tools/wiring_check.py's `_run_git`): all THREE git
    subprocess calls this module makes (this function's two, plus
    `_try_hookspath_autofix`'s write) now pass
    `encoding="utf-8", errors="replace"` instead of a bare `text=True`
    -- on a non-UTF-8 console locale (this host: cp1251) `text=True`
    alone lets Python decode git's always-UTF-8 output via
    locale.getpreferredencoding(), silently MOJIBAKE-ing any non-ASCII
    value (e.g. a Cyrillic core.hooksPath) before this channel ever
    compares or reports it. The `git ls-files -s` call ALSO now runs
    with `-c core.quotepath=false` (a per-invocation override, does not
    touch the host repo's own config) -- git's default quotepath=true
    would octal-escape a non-ASCII path in that output, which this
    function's `Path(path_part).name` parsing does not recognize; no
    live incident is known for THIS specific call today (both required
    hook names are plain ASCII), but the fix is applied here too so the
    class is closed uniformly rather than left latent for the day a
    non-ASCII file lands under .githooks/. Behavior on the two required
    hook names, and every existing warning string this channel
    produces, is unchanged -- this is an encoding/quoting fix only, not
    a change to what gets reported."""
    root = Path(root)
    expected = (root / _GITHOOKS_DIRNAME).resolve()
    reason = "journal_validator/mechanism_gate do not run on commits"

    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        detail = _ascii_sanitize(f"git config core.hooksPath failed ({type(e).__name__})", 120)
        return [f"{detail} -- {reason}"]

    raw = (result.stdout or "").strip()
    warnings = []
    if result.returncode != 0 or not raw:
        # VG-1 part A: attempt the self-heal before settling for the WARN
        # (see _try_hookspath_autofix's own docstring for the full
        # success/failure contract). Only reached when hooksPath is
        # UNSET -- the "set to something else" branch below never calls
        # this, by design (see that function's docstring).
        warnings.append(_try_hookspath_autofix(root, reason))
    else:
        configured = Path(raw)
        if not configured.is_absolute():
            configured = root / configured
        try:
            configured_resolved = configured.resolve()
        except OSError:
            configured_resolved = configured
        if configured_resolved != expected:
            raw_safe = _ascii_sanitize(raw, 150)
            expected_safe = _ascii_sanitize(str(expected), 150)
            warnings.append(
                f"core.hooksPath={raw_safe!r} does not resolve to {expected_safe} -- {reason}"
            )

    for name in _REQUIRED_GITHOOKS:
        if not (root / _GITHOOKS_DIRNAME / name).is_file():
            warnings.append(f"hook file missing: {_GITHOOKS_DIRNAME}/{name} -- {reason}")

    # D-0093: git-INDEX exec-bit check (never the filesystem -- see
    # docstring). Same subprocess idiom as the hooksPath call above;
    # a failed invocation folds into one WARNING, same treatment as
    # that call's own except-branch, and does not block the two checks
    # already computed above (each fact stays independently reportable).
    try:
        ls_result = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "-s", "--", _GITHOOKS_DIRNAME],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        detail = _ascii_sanitize(f"git ls-files -s failed ({type(e).__name__})", 120)
        warnings.append(f"{detail} -- {reason}")
        ls_result = None

    if ls_result is not None and ls_result.returncode != 0:
        # A non-zero returncode (e.g. empty stdout because git itself
        # errored -- not because the hooks are genuinely untracked) gets
        # the SAME one-WARNING-and-skip treatment as the except branch
        # above, instead of falling through into the loop below and
        # being silently misreported as "untracked" for both hooks
        # (critic t-288 finding).
        detail = _ascii_sanitize(
            f"git ls-files -s failed (returncode {ls_result.returncode})", 120
        )
        warnings.append(f"{detail} -- {reason}")
        ls_result = None

    modes = {}
    if ls_result is not None:
        for line in (ls_result.stdout or "").splitlines():
            meta, sep, path_part = line.partition("\t")
            if not sep:
                continue
            fields = meta.split()
            if not fields:
                continue
            modes[Path(path_part).name] = fields[0]

    if ls_result is not None:
        for name in _REQUIRED_GITHOOKS:
            if name not in modes:
                warnings.append(f"hook {name} untracked -- clones get no gate")
            elif modes[name] != "100755":
                warnings.append(
                    f"hook {name} committed non-executable ({modes[name]}) -- "
                    "Linux clones get silently dead gates (D-0093)"
                )

    return warnings


def _parse_hook_commands(settings) -> list:
    """Walks every hooks section of a parsed .claude/settings.json
    (structure: {"hooks": {"<Event>": [{"hooks": [{"command": "..."}]}]}}),
    collecting each hook's raw command string in encounter order.
    Tolerant of any malformed shape -- a piece that isn't a dict/list
    where expected is simply skipped, never raised on, because a
    malformed settings.json is exactly the condition this whole check
    exists to survive (fail-open, spec point 3)."""
    commands = []
    hooks_root = settings.get("hooks") if isinstance(settings, dict) else None
    if not isinstance(hooks_root, dict):
        return commands
    for matchers in hooks_root.values():
        if not isinstance(matchers, list):
            continue
        for matcher in matchers:
            if not isinstance(matcher, dict):
                continue
            entries = matcher.get("hooks")
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                command = entry.get("command")
                if isinstance(command, str) and command:
                    commands.append(command)
    return commands


def harness_channel(root: Path):
    """harness-channel: every hook command line in .claude/settings.json
    of the form "python tools/<file>.py" names a file that (a) exists
    and (b) imports cleanly via importlib (top-level of these modules is
    side-effect-free -- verified by critic t-256). Returns
    (warnings, importable_count) -- importable_count is the number of
    DISTINCT tools/<file>.py names that were checked and had NO warning
    (used by wiring_lines() for the OK line's "N files importable").
    Never raises: a missing/unreadable/invalid settings.json, a missing
    hook file, or an import failure all become WARNING strings.

    Hardening (Lead ruling on critic-gate note, t-257 attempt 2): exec_module
    below runs with stdout/stderr redirected to os.devnull. All 8 hook
    files checked today are top-level-silent (verified t-256), so this
    changes nothing for the current repo -- but a FUTURE hook file that
    prints at import time (debug leftover, a library that logs on load)
    would otherwise dump arbitrary, non-ASCII-sanitized text straight
    into this hook's own stdout, bypassing _ascii_sanitize entirely
    (nothing about that printed text would pass through git_hooks_channel/
    harness_channel's own return values at all -- it would just appear on
    the console, mid-context, unrouted). Redirecting during the import
    call closes that path structurally rather than relying on every
    future hook file staying disciplined."""
    root = Path(root)
    settings_path = root / _SETTINGS_RELPATH

    try:
        text = settings_path.read_text(encoding="utf-8")
    except OSError as e:
        path_safe = _ascii_sanitize(str(settings_path), 150)
        return [f"{path_safe} not readable ({type(e).__name__})"], 0

    try:
        settings = json.loads(text)
    except Exception as e:
        path_safe = _ascii_sanitize(str(settings_path), 150)
        return [f"{path_safe} not valid JSON ({type(e).__name__})"], 0

    commands = _parse_hook_commands(settings)
    warnings = []
    ok_files = set()
    seen_files = set()
    for command in commands:
        m = _HOOK_COMMAND_RE.match(command.strip())
        if not m:
            command_safe = _ascii_sanitize(command, 150)
            warnings.append(f"unparsed hook command: {command_safe}")
            continue
        filename = m.group(1)
        if filename in seen_files:
            continue
        seen_files.add(filename)

        file_path = root / "tools" / filename
        filename_safe = _ascii_sanitize(filename, 150)
        if not file_path.is_file():
            warnings.append(f"hook file not found: tools/{filename_safe}")
            continue

        module_name = f"_wiring_check_{re.sub(r'[^0-9A-Za-z_]', '_', file_path.stem)}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"no loader for {file_path}")
            module = importlib.util.module_from_spec(spec)
            # See harness_channel()'s docstring "Hardening" note: any
            # top-level print()/stderr write during this exec_module call
            # is swallowed here, not leaked into this hook's own output.
            with open(os.devnull, "w", encoding="utf-8") as _devnull, \
                    contextlib.redirect_stdout(_devnull), \
                    contextlib.redirect_stderr(_devnull):
                spec.loader.exec_module(module)
        except Exception as e:
            warnings.append(f"import failed: tools/{filename_safe} ({type(e).__name__})")
            continue

        ok_files.add(filename)

    return warnings, len(ok_files)


def python_channel():
    """python-channel: shutil.which("python") on THIS process's PATH.
    LIMITATION (spec point 2в, deliberately not fixable in-hook): this is
    a statement about the PATH of the process running this hook right
    now -- a SessionStart hook invocation. The PATH available to a git
    hook (pre-commit/commit-msg) at actual commit time is a SEPARATE
    shell invocation and can differ (different shell init, different cwd
    context); this check cannot observe that PATH from here. Returns the
    resolved path string, or None if no "python" was found."""
    return shutil.which("python")


def _wiring_line_for(fact: str) -> str:
    """VG-1 part A: formats one git/harness-channel fact into its final
    WIRING output line. A fact carrying _AUTOFIX_FACT_PREFIX (a CONFIRMED
    self-heal, see _try_hookspath_autofix) renders as 'WIRING AUTOFIX:
    ...' -- a discrepancy that got RESOLVED, not one still open -- so it
    must not read like a warning. Every other fact keeps the existing
    'WIRING WARNING: ...' rendering unchanged."""
    if fact.startswith(_AUTOFIX_FACT_PREFIX):
        return f"WIRING {fact}"
    return f"WIRING WARNING: {fact}"


def wiring_lines(root: Path = None) -> list:
    """Combines the three wiring-integrity channels into either a single
    'WIRING: OK (...)' line (spec point 1, everything wired), one
    'WIRING WARNING: <fact>' line per discrepancy, or a 'WIRING AUTOFIX:
    <fact>' line where the git-channel self-healed an unset
    core.hooksPath (VG-1 part A -- see _try_hookspath_autofix). Feeds the
    SAME output stream as boot_budget_lines() etc. (build_context_lines()
    below appends this list exactly like the others).

    Unlike quota_lines()/open_dispatches() -- which have no local
    try/except and rely entirely on main()'s single outer boundary --
    this function DOES wrap its own body in a try/except (spec point 3):
    a wiring-block failure must degrade to one WARNING line, not
    propagate to main()'s catch-all, which would discard every OTHER
    line already built for this session (NOW, MODEL, JOURNAL, quota,
    boot-budget -- see main()'s docstring for why that boundary discards
    everything gathered so far). Each channel function already turns its
    OWN known failure modes into WARNING strings; this outer try/except
    is strictly a backstop for anything unforeseen.

    ASCII invariant (Lead ruling): every line returned here is routed
    through _ascii_sanitize as a final backstop, on top of the
    per-component sanitization already applied inside git_hooks_channel()/
    harness_channel() -- belt and suspenders against a value this module
    does not fully control (e.g. an unexpected exception's __str__, or a
    filesystem path containing non-ASCII characters) slipping an
    unsanitized character or an overlong line into the finished text.
    _WIRING_LINE_MAX_LEN is wider than _ascii_sanitize's own 80-char
    default (used for the single-token MODEL/OPEN DISPATCH lines) because
    a WIRING line legitimately carries a full repo path plus an
    explanatory clause."""
    try:
        root = Path(root) if root else repo_root()
        git_warnings = git_hooks_channel(root)
        harness_warnings, importable_count = harness_channel(root)
        python_path = python_channel()
        # t-338 (Dog synk 07-29): the skills-casing channel lives in
        # tools/wiring_check.py (the standalone observer CLI, same
        # directory -- resolvable for the same sys.path[0] reason that
        # file imports session_context back); the Lead wired this call
        # in at acceptance per D-0069. Lazy import, fail-open: a
        # missing/broken wiring_check must never break SessionStart --
        # any failure degrades to one WARNING string, same contract as
        # the channels above.
        try:
            # P4 (coordinator fix Ф1 follow-up, builder t-536, 2026-08-19):
            # prefer the wiring_check_p4 SIBLING (carries stdin=DEVNULL on
            # its own git ls-files call -- see that file's own "P4 SIBLING
            # NOTE") over the live wiring_check, same sibling-first
            # discipline this whole batch already uses -- avoids the SAME
            # stuck-stdin-pipe hang class this batch fixes, one level
            # removed (skills_casing_channel's git call inherits a stuck
            # pipe just like session_context's own three git calls did).
            try:
                import wiring_check_p4 as _wc
            except ImportError:
                import wiring_check as _wc
            skills_warnings, skills_ok_count = _wc.skills_casing_channel(root)
        except Exception as e:
            skills_warnings = [
                f"skills-casing channel unavailable ({type(e).__name__})"
            ]
            skills_ok_count = 0
    except Exception as e:
        return [
            _ascii_sanitize(
                f"WIRING WARNING: check failed internally ({type(e).__name__})",
                _WIRING_LINE_MAX_LEN,
            )
        ]

    warnings = list(git_warnings) + list(harness_warnings) + list(skills_warnings)
    if not python_path:
        warnings.append("python not found on PATH")

    if not warnings:
        python_safe = _ascii_sanitize(python_path, 150)
        line = (
            "WIRING: OK (git hooks: pre-commit, commit-msg;"
            f" harness hooks: {importable_count} files importable;"
            f" skills casing: {skills_ok_count} ok; python: {python_safe})"
        )
        return [_ascii_sanitize(line, _WIRING_LINE_MAX_LEN)]
    return [
        _ascii_sanitize(_wiring_line_for(w), _WIRING_LINE_MAX_LEN) for w in warnings
    ]


# ---------------------------------------------------------------------------
# t-325 (P1, внешнее ревью): GATE BREAK-GLASS surfacing.
#
# Hole this closes: both tools/main_gate.py and tools/dod_gate.py carry a
# safety valve ("after 2 consecutive blocks, skip the 3rd -- exit 0, do not
# hang the session forever") that used to be invisible outside the gate's
# own append-only gate_log: nothing surfaced the fact that a session
# COMPLETED WITHOUT a green verification run. Their sibling edit (same task)
# makes the valve APPEND a persistent fact -- main_gate_state
# ["unsafe_completions"] (list) / gate_state.per_agent[<agent>]
# ["unsafe_completions"] (list) -- that survives later green runs (a
# green run only resets consecutive_blocks, never touches this key). This
# block is the surfacing half: on the NEXT SessionStart, scan every
# .claude/dod_track/<session_id>.json for facts not yet acknowledged and
# print one loud line per fact (up to a cap), exactly once.
#
# ATTEMPT 2 (critic-gate REJECTED attempt 1; three findings, Lead rulings
# below -- fixed here, not re-litigated):
#
#  1. ACK ONLY SURVIVING LINES. Attempt 1 acknowledged every fact BEFORE
#     build_context_lines()'s own `lines[:MAX_LINES]` (25-line budget) cut
#     the list -- a fact whose line got silently truncated was marked
#     acknowledged anyway and never surfaced again (verified failure: a
#     live repo already sits at 17/25 lines, 8 lines of headroom). Fix:
#     candidate lines are built READ-ONLY first (_break_glass_candidates,
#     no ack write at all), and select_and_ack_break_glass_lines() below
#     is the ONLY place that acknowledges -- it is called from
#     build_context_lines() with the lines ALREADY built so far, computes
#     how much of the 25-line budget is actually left, and acks ONLY the
#     facts whose lines fit in that remaining space. A fact that does not
#     fit is not acked and resurfaces on the next SessionStart.
#  2. CAP. At most _BREAK_GLASS_LINE_CAP (5) individual fact lines per
#     call, plus one trailing "... and N more ... pending" summary line
#     when more remain -- N (and the facts behind it) are explicitly NOT
#     acked, so they queue for a future call. The summary line itself
#     carries no ack key (key=None) -- it is never itself "acknowledged",
#     it just stops being emitted once the pending count drops back to
#     <= the cap.
#  3. D-0060 (SECOND finding): .claude/dod_track/<session_id>.json files
#     are shared, live state -- a DIFFERENT/parallel session's PostToolUse
#     hook may still be read-modify-writing the SAME track file
#     (tools/dod_track.py) at the exact moment SessionStart of a new
#     session runs this scan
#     -- attempt 1's own read-modify-write of that SAME file (to set
#     acknowledged_ts) could race and silently drop a concurrent edit/run
#     record. Fix: this whole module is READ-ONLY on dod_track/*.json,
#     full stop. Acknowledgement state lives in its OWN sidecar file,
#     .claude/dod_track/break_glass_ack.json, whose SOLE writer/owner is
#     this module (no gate, no dod_track.py, ever touches it) -- a
#     dedicated file has no concurrent writer to race with. Fact identity
#     for the ack key does not need any track-file mutation: session_id
#     (filename stem) + gate ("main"/"dod") + agent_key (per_agent's own
#     dict key, or "" for the agent-less main gate) + the fact's own "ts"
#     + the fact's INDEX within its own facts list (see
#     _unsafe_completion_facts) together identify it stably, written once
#     by the gate itself and never rewritten afterward. The index is NOT
#     optional (accept-with-fixup, critic-gate probe): "ts" ALONE can
#     collide -- two facts of the same session/gate/agent observed with a
#     byte-identical ts (Windows wall-clock granularity ~15.6ms repeated
#     within one fast process) would otherwise share one ack key, and
#     acknowledging the first (because the budget cut lands between them)
#     would silently swallow the second forever.
#  4. COLLISION (THIRD finding). Attempt 1's gates OVERWROTE a single
#     "unsafe_completion" dict on every valve trip -- a session tripping
#     the valve twice lost the first occurrence entirely. The gates' own
#     sibling fix (see tools/main_gate.py / tools/dod_gate.py) now APPENDS
#     to a list under the new key "unsafe_completions" instead. This module
#     reads BOTH: the new plural list (iterated in full) AND the legacy
#     singular "unsafe_completion" dict (kept for backward compatibility --
#     see _extract_unsafe_list()) so an already-written attempt-1-shaped
#     track file, if one ever existed on disk, is not silently orphaned.
#
# ASCII invariant (same Lead ruling already on record in this file's WIRING-
# INTEGRITY block, docstring "ASCII invariant" note above wiring_lines()):
# the spec's own illustrative wording for this line is Cyrillic, but this
# whole module's hard constraint is "every line built here is plain ASCII"
# (cp1251 console) -- the Lead already resolved this exact class of tension
# in favor of English ASCII for WIRING lines; the same resolution applies
# here rather than reopening the same question. reason/ts/session_id/gate
# are all sourced from a dod_track JSON file a session itself wrote, so each
# goes through _ascii_sanitize before being interpolated, same discipline as
# MODEL/OPEN DISPATCH/WIRING.
#
# Fail-open per file (DoD (д)): a corrupt/unreadable JSON file is skipped
# SILENTLY (no warning line, no exception) -- the sibling file next to it
# must still surface normally. This is a per-file try/except, deliberately
# narrower than wiring_lines()'s own whole-block backstop: there is no
# shared state across track files to protect here (the sidecar is a
# separate file, read/written once per call, not per track file), so
# isolating the failure to exactly the broken file is both sufficient and
# strictly better than an all-or-nothing guard. A broken/unreadable sidecar
# file itself degrades to "treat as empty" (nothing acked yet) rather than
# raising -- see _load_break_glass_ack().
# ---------------------------------------------------------------------------

_DOD_TRACK_DIRNAME = Path(".claude") / "dod_track"
_BREAK_GLASS_ACK_FILENAME = "break_glass_ack.json"
_BREAK_GLASS_LINE_CAP = 5


def _extract_unsafe_list(state: dict) -> list:
    """One gate-state dict's (main_gate_state, or one gate_state.per_agent
    entry) unsafe-completion facts, oldest-first: the new plural list key
    "unsafe_completions" (attempt 2 fix -- append, never overwrite) PLUS
    the legacy singular "unsafe_completion" dict (attempt 1 shape, kept
    readable for backward compatibility -- point 4 above), in that order.
    Tolerant of any malformed shape -- a track file is data a hook wrote,
    not a schema this function enforces."""
    items = []
    legacy = state.get("unsafe_completion")
    if isinstance(legacy, dict):
        items.append(legacy)
    plural = state.get("unsafe_completions")
    if isinstance(plural, list):
        items.extend(u for u in plural if isinstance(u, dict))
    return items


def _unsafe_completion_facts(data: dict) -> list:
    """Walks one parsed dod_track file's known gate-state sections and
    returns every (gate_label, agent_key, index, unsafe_completion_dict)
    quad found, regardless of acknowledged state (the caller filters).
    "main" -- tools/main_gate.py's main_gate_state (agent_key "": the Stop
    hook is always main-thread, there is no agent to key by). "dod" --
    tools/dod_gate.py's gate_state.per_agent[<agent_key>] (zero or more,
    one bucket per agent that ever tripped the valve in this session);
    agent_key is per_agent's own dict key (e.g. "agent-1" or the
    defensive-branch fallback "__none__"), used verbatim in the ack key so
    two agents' facts never collide.

    index -- this fact's position within its OWN state dict's combined
    facts list (_extract_unsafe_list: legacy singular first at index 0 if
    present, then the plural list in append order) -- STABLE across calls
    because that list is append-only, and load-bearing for ack-key
    uniqueness (critic-gate probe, attempt-2 accept-with-fixup): "ts"
    alone is NOT guaranteed unique -- two facts of the same session/gate/
    agent can carry a byte-identical ts (observed: Windows wall-clock
    granularity ~15.6ms repeated four times in one fast process), which
    would otherwise collapse two DISTINCT facts onto the same ack key --
    acknowledging the first (because the budget cut lands between them)
    would silently acknowledge the second too, and it would never
    surface. Tolerant of any malformed shape."""
    facts = []

    main_state = data.get("main_gate_state")
    if isinstance(main_state, dict):
        facts.extend(
            ("main", "", i, unsafe)
            for i, unsafe in enumerate(_extract_unsafe_list(main_state))
        )

    gate_state = data.get("gate_state")
    if isinstance(gate_state, dict):
        per_agent = gate_state.get("per_agent")
        if isinstance(per_agent, dict):
            for agent_key, agent_state in per_agent.items():
                if not isinstance(agent_state, dict):
                    continue
                facts.extend(
                    ("dod", str(agent_key), i, unsafe)
                    for i, unsafe in enumerate(_extract_unsafe_list(agent_state))
                )

    return facts


def _break_glass_ack_path(root: Path) -> Path:
    return Path(root) / _DOD_TRACK_DIRNAME / _BREAK_GLASS_ACK_FILENAME


def _load_break_glass_ack(path: Path) -> dict:
    """Fail-open: missing, unreadable, or non-dict sidecar content is
    treated as "nothing acknowledged yet" -- same principle as every other
    track/log reader in this file (a broken sidecar must not hide facts,
    at worst it re-surfaces something already seen once)."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_break_glass_ack(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _break_glass_candidates(root: Path) -> list:
    """READ-ONLY (point 3): scans .claude/dod_track/*.json (skipping the
    ack sidecar itself) and the ack sidecar, and returns a list of
    {"key": str|None, "line": str} dicts for facts NOT YET acknowledged --
    up to _BREAK_GLASS_LINE_CAP individual fact entries (deterministically
    sorted by their own key so results are stable across calls), plus one
    trailing summary entry (key=None, never ack-able) when more pending
    facts exist beyond the cap (point 2). Does NOT write anything, to
    either the track files or the ack sidecar -- callers decide how many
    of these survive their own outer truncation and ack accordingly (see
    select_and_ack_break_glass_lines())."""
    track_dir = root / _DOD_TRACK_DIRNAME
    if not track_dir.is_dir():
        return []

    facts = []
    for path in sorted(track_dir.glob("*.json")):
        if path.name == _BREAK_GLASS_ACK_FILENAME:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue  # fail-open, per-file: a broken track must not hide siblings
        if not isinstance(data, dict):
            continue

        session_id = path.stem
        for gate, agent_key, index, unsafe in _unsafe_completion_facts(data):
            # Index appended (critic-gate accept-with-fixup, attempt 2):
            # "ts" alone can collide (see _unsafe_completion_facts'
            # docstring) -- the index makes the key unique per fact even
            # when two facts of the same session/gate/agent share a
            # byte-identical ts.
            fact_ts = str(unsafe.get("ts") or "-")
            key = f"{session_id}:{gate}:{agent_key}:{fact_ts}:{index}"
            facts.append((key, session_id, gate, unsafe))

    ack_data = _load_break_glass_ack(_break_glass_ack_path(root))
    pending = [f for f in facts if f[0] not in ack_data]
    pending.sort(key=lambda f: f[0])

    shown = pending[:_BREAK_GLASS_LINE_CAP]
    cap_remainder = len(pending) - len(shown)

    candidates = []
    for key, session_id, gate, unsafe in shown:
        ts = _ascii_sanitize(str(unsafe.get("ts") or "-"), 60)
        reason = _ascii_sanitize(str(unsafe.get("reason") or "-"), 80)
        session_safe = _ascii_sanitize(session_id, 150)
        line = (
            f"GATE BREAK-GLASS: session {session_safe} ended via the {gate} gate's"
            f" safety valve without a green run ({ts}, reason={reason})"
        )
        candidates.append({"key": key, "line": line})

    if cap_remainder > 0:
        candidates.append(
            {
                "key": None,
                "line": (
                    f"GATE BREAK-GLASS: ... and {cap_remainder} more"
                    " unsafe-completion facts pending"
                ),
            }
        )

    return candidates


def _ack_break_glass_keys(root: Path, keys, now: datetime.datetime = None) -> None:
    """Writes the given fact keys into the ack sidecar as acknowledged
    (key=None entries -- the summary line -- are filtered out, they are
    never ack-able). A no-op (no file touched at all) when there is
    nothing new to write, so a call with an empty/all-None key list never
    creates the sidecar file on disk for no reason."""
    keys = [k for k in keys if k]
    if not keys:
        return
    now = now or datetime.datetime.now()
    path = _break_glass_ack_path(root)
    ack_data = _load_break_glass_ack(path)
    changed = False
    for key in keys:
        if key not in ack_data:
            ack_data[key] = now.strftime("%Y-%m-%dT%H:%M:%S.%f")
            changed = True
    if changed:
        try:
            _save_break_glass_ack(path, ack_data)
        except Exception:
            pass  # fail-open: printed line stands even if the ack-write fails


def _select_pending_break_glass_lines(root: Path, lines_so_far: list) -> list:
    """F-61/B1 fix: the SELECTION half of the old select_and_ack_break_
    glass_lines(), with the ACK half removed. Given the context lines
    ALREADY built (before break-glass lines are appended), returns the
    break-glass candidate {"key", "line"} dicts that FIT within the
    module's MAX_LINES budget -- but writes NOTHING to the ack sidecar.
    Acking is now the caller's responsibility, and per B1 it must happen
    ONLY after the corresponding lines have actually, successfully, been
    handed to the user (see main()) -- never at selection/construction
    time, which is what let a fact get marked "shown" (FINDINGS F-61,
    instance 3) even when the print that was supposed to show it never
    ran (broken output channel) or half-ran (multi-line print aborted
    partway). The trailing "... and N more" summary line (if present) is
    never itself ack-able (see _break_glass_candidates) regardless of
    whether it survives the cut."""
    candidates = _break_glass_candidates(root)
    if not candidates:
        return []
    space_left = MAX_LINES - len(lines_so_far)
    if space_left <= 0:
        return []
    return candidates[:space_left]


def select_and_ack_break_glass_lines(
    root: Path, lines_so_far: list, now: datetime.datetime = None
) -> list:
    """Immediate-ack convenience wrapper kept for standalone/ad-hoc use
    (break_glass_lines() below; NOT used by build_context_lines()/main()
    any more -- see _select_pending_break_glass_lines() and main()'s own
    docstring for why the real SessionStart path defers the ack past the
    point where output has actually, successfully, been produced).
    Selects via _select_pending_break_glass_lines() and acks the survivors
    immediately, synchronously, in the same call -- appropriate for a
    caller that does not itself have a "did this actually reach the user"
    boundary to defer to."""
    shown = _select_pending_break_glass_lines(root, lines_so_far)
    if not shown:
        return []
    _ack_break_glass_keys(root, [c["key"] for c in shown], now)
    return [c["line"] for c in shown]


def break_glass_lines(root: Path = None, now: datetime.datetime = None) -> list:
    """Convenience entry point for direct/standalone use (unit tests, ad
    hoc scripts): equivalent to select_and_ack_break_glass_lines() called
    with an EMPTY preceding-lines list, i.e. the full MAX_LINES budget is
    available -- only _BREAK_GLASS_LINE_CAP (point 2) limits the result,
    not the 25-line context budget. build_context_lines()/main() do NOT
    call this immediate-ack wrapper (see main()'s docstring)."""
    root = Path(root) if root else repo_root()
    return select_and_ack_break_glass_lines(root, [], now)


def build_context_lines(
    root: Path = None,
    now: datetime.datetime = None,
    stdin_payload=None,
    config_text=_LEAD_BINDING_CONFIG_UNSET,
) -> list:
    """config_text (B1(b), пересдача D-0099, 2026-08-04): threaded straight
    through to model_line() -- same sentinel/None-means-"нет конфига"
    contract as model_tier()/model_line() themselves; tests isolating
    themselves from the real (soon-to-exist) delegation.config.yaml pass
    config_text=None explicitly through this seam, not by monkeypatching
    mechanism_gate.CONFIG_PATH.

    F-61/B1: this function no longer acks break-glass facts as a side
    effect (that used to happen here, BEFORE any line was ever printed --
    FINDINGS F-61 instance 3). It only SELECTS which break-glass lines fit
    the MAX_LINES budget. Thin wrapper over
    _build_context_lines_and_pending_ack() for callers that only want the
    printable lines.

    Fix2 (critic verdict on узел B, 2026-08-19): this wrapper is a
    TEST/STANDALONE SEAM ONLY -- kept for callers that monkeypatch this
    exact public name (tests, ad-hoc scripts) or that only want the
    printable lines without the ack bookkeeping. The PRODUCTION path
    (main()) does NOT go through this function -- it calls
    _build_context_lines_and_pending_ack() directly, so it can also get
    the pending-ack keys build_context_lines() itself discards. A test
    that patches build_context_lines() to control main()'s output must
    patch _build_context_lines_and_pending_ack() on THIS module instead
    (or fall back to patching the public name when the private one is
    absent, e.g. against the live pre-fix file) -- this asymmetry (a seam
    that looks production-shaped but is not on main()'s actual call path)
    is registered as a SIBLING_MAP axis by Lead at posadka."""
    lines, _pending_ack = _build_context_lines_and_pending_ack(
        root, now, stdin_payload, config_text
    )
    return lines


def _build_context_lines_and_pending_ack(
    root: Path = None,
    now: datetime.datetime = None,
    stdin_payload=None,
    config_text=_LEAD_BINDING_CONFIG_UNSET,
) -> "tuple[list, tuple]":
    """Does the same assembly as build_context_lines(), but additionally
    returns (ack_root, pending_keys, ack_now) -- the arguments main() must
    later pass to _ack_break_glass_keys(), ONCE, and ONLY after the
    returned `lines` have actually been printed successfully. pending_keys
    already excludes the never-ack-able summary entry (key=None) and is
    exactly the set of keys whose lines survived the lines[:MAX_LINES] cut
    below -- constructively, from the same slice used to build `lines`,
    never by trusting a line's position in isolation (B1: "позиционное
    'перенёс ниже' без фильтра -- не принято")."""
    root = Path(root) if root else repo_root()
    now = now or datetime.datetime.now()
    gateway_root = root / "gateway"

    events = read_journal_events(root)

    lines = [now_line(now), model_line(stdin_payload, config_text), last_event_line(events)]

    drift_line = clock_drift_line(events, now)
    if drift_line:
        lines.append(drift_line)

    open_since = open_degradation_window(events)
    if open_since:
        lines.append(f"OPEN DEGRADATION WINDOW since {open_since}")

    lines.extend(open_dispatch_lines(events))

    lines.append(last_calibration_line(events, now))
    lines.extend(quota_lines(gateway_root, now))
    lines.extend(boot_budget_lines(root))
    lines.extend(wiring_lines(root))
    # t-325 attempt 2, point 1 (kept): pass the ALREADY-BUILT lines so this
    # call can compute how much of the 25-line budget is actually left.
    # F-61/B1 (this batch): selection only, no ack here -- see
    # _select_pending_break_glass_lines()'s own docstring.
    bg_shown = _select_pending_break_glass_lines(root, lines)
    lines.extend(c["line"] for c in bg_shown)
    pending_keys = [c["key"] for c in bg_shown if c["key"]]

    return lines[:MAX_LINES], (root, pending_keys, now)


def main(root: Path = None) -> int:
    """The ONE try/except boundary for the whole script (spec: 'НИКОГДА
    не падает -> одна строка -> exit 0'). Deliberately not per-section:
    a partially-built context (e.g. journal read fine, quota lookup
    half-crashed) is a worse failure mode than no context at all --
    a session trusting a half-populated 'reality' block is exactly the
    kind of silent gap this hook exists to prevent. So any error, from
    anywhere in reading stdin or build_context_lines(), discards
    everything gathered so far and prints only the warning line.

    F-61 remediation (node B), critic-revised contract (fit_with_fixes
    verdict, fixes 1/3/4/5, 2026-08-19) -- four changes from the pre-fix
    version:
    B2/fix1 -- ALL lines (context + autoboot) are joined into ONE string
    and handed to a SINGLE sys.stdout.write() + explicit flush(), both
    still INSIDE this try -- not one print() per line. This is what makes
    "discards everything gathered so far" literally true on a mid-build
    failure: a build-time exception now ALWAYS discards the whole partial
    context (never a partial print) -- but the warning line itself is
    still visible (see fix5 below), so a build failure with a healthy
    stdout is never silent, only context-less. B1 -- break-glass facts
    are ack'd (sidecar-written) ONLY AFTER that single write+flush has
    returned without raising -- never during
    _build_context_lines_and_pending_ack() itself (see that function's and
    _select_pending_break_glass_lines()'s docstrings). B3/fix5 -- the
    fail-open warning is attempted on STDOUT FIRST (a session must see it
    in the context stream it already reads, the same channel a healthy
    build would have used -- historical incident: a broken journal/quota
    read must still surface as a visible line, not vanish into a stream
    nobody is looking at) -- ONLY when that stdout write itself raises
    (a genuinely dead stdout, not merely a build-time exception) does the
    SAME message fall back to stderr, under its own nested try; if BOTH
    channels are down the warning is silently dropped and main() still
    returns 0 -- a SessionStart hook must never itself crash the session,
    on either channel. B4/fix4 -- the exception's str(e) is sanitized
    through this module's own _ascii_sanitize(text, 300) (same helper
    MODEL/OPEN DISPATCH/WIRING lines already use, see the module
    docstring's ASCII-safe-output paragraph) before it is formatted into
    the warning line, on EVERY channel attempt: an unsanitized non-ASCII
    or multi-line message could silently die against a cp1251 console
    (measured by critic) or blow the one-line/no-injected-newline
    invariant this hook otherwise holds everywhere else."""
    try:
        stdin_payload = read_stdin_payload()
        context_lines, pending_ack = _build_context_lines_and_pending_ack(
            root, stdin_payload=stdin_payload
        )
        # AUTO-BOOT (D-0103): computed as a separate block, deliberately
        # OUTSIDE build_context_lines()'s own MAX_LINES (25) truncation --
        # the directive must always survive regardless of how full the
        # boot-lite context already is -- but still folded into the SAME
        # single write below (B2), not a second print loop.
        autoboot = autoboot_lines(extract_source(stdin_payload))
        all_lines = context_lines + autoboot
        output = "\n".join(all_lines)
        if all_lines:
            output += "\n"
        sys.stdout.write(output)
        sys.stdout.flush()
        # B1: ack ONLY now, after the single write+flush above has
        # actually succeeded -- a failure anywhere above raises before
        # this line is ever reached, so no break-glass key is ever marked
        # acknowledged for content the user never actually saw.
        ack_root, pending_keys, ack_now = pending_ack
        _ack_break_glass_keys(ack_root, pending_keys, ack_now)
    except Exception as e:  # fail-open: this hook must never break session start
        # fix4: sanitize BEFORE formatting -- applies to whichever channel
        # below actually ends up carrying the line, not just one of them.
        safe_detail = _ascii_sanitize(str(e), 300)
        warning = f"session-context warning: {safe_detail}\n"
        try:
            # fix5: stdout FIRST -- a healthy stdout (the common case: a
            # broken journal/quota/wiring read, not a dead channel) must
            # show the warning in the same stream the session already
            # reads, exactly like the pre-B2 behavior did. This write is
            # a FRESH attempt, independent of the one above -- reaching
            # here means that one either never ran or raised before
            # completing, so there is no partial content underneath it.
            sys.stdout.write(warning)
            sys.stdout.flush()
        except Exception:
            # stdout is genuinely dead (not just the build) -- fall back
            # to stderr, same sanitized message, own try: if stderr is
            # ALSO unusable, swallow that too and still return 0 silently
            # rather than let a diagnostic-printing attempt itself crash
            # session start.
            try:
                sys.stderr.write(warning)
                sys.stderr.flush()
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
