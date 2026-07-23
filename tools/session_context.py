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
  ONE line, 'session-context warning: ...', and exit 0 (fail-open).
  main() is the single try/except boundary -- see its docstring for why
  a per-section try/except was deliberately NOT used. The new
  open_dispatches()/open_dispatch_lines() functions follow the same
  rule: no local try/except, failures propagate to main()'s one
  boundary, exactly like quota_lines().
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
  formatted into a line.
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


# ---------------------------------------------------------------------------
# New in b3: MODEL line (D-0056a)
# ---------------------------------------------------------------------------


def read_stdin_payload():
    """Reads and JSON-parses stdin, but ONLY when stdin is not a TTY.
    A SessionStart hook receives the harness's JSON on stdin; a human
    running this script by hand from an interactive shell has no piped
    input, and blocking on sys.stdin.read() there would hang forever --
    the isatty() guard is what keeps both modes safe. Any failure
    (unreadable stdin, empty input, invalid JSON) returns None rather
    than raising; callers treat None exactly like "no model info"."""
    if sys.stdin.isatty():
        return None
    try:
        data = sys.stdin.read()
    except Exception:
        return None
    if not data or not data.strip():
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


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


def model_tier(model_id: str) -> str:
    low = model_id.lower()
    for substr, tier in _MODEL_TIER_SUBSTRINGS:
        if substr in low:
            return tier
    return "unknown"


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


def model_line(stdin_payload=None) -> str:
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
    liveness of this line -- check 13(zh)."""
    model_id = extract_model_id(stdin_payload)
    if not model_id:
        return "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    sanitized = _ascii_sanitize(model_id)
    if not sanitized:
        # whitespace-only (or entirely-stripped) model id: same fallback
        # as "no model id at all" -- there is nothing left to report.
        return "MODEL: not provided by hook input -- verify tier yourself (D-0056a)"
    tier = model_tier(sanitized)
    return (
        f"MODEL: {sanitized} -> tier {tier}"
        " (declared by harness, not measured -- F-37; Lead tier = fable)"
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

    lines = [base + missing_suffix + status_suffix]

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

    Returns the AUTOFIX fact (_AUTOFIX_FACT_PREFIX + "core.hooksPath set
    to .githooks") on a confirmed success: the `git config` write itself
    exited 0 AND both required hook files are actually present on disk
    under .githooks/ afterward (setting hooksPath to a directory whose
    hook files don't exist would "succeed" as a git operation while
    leaving the wiring exactly as broken as before). Any other outcome
    returns the ORIGINAL 'core.hooksPath not set' warning fact with an
    "; autofix failed: <reason>" suffix -- covering the three failure
    causes named in the spec: git itself unavailable/erroring (the write
    call raises), the config being unwritable e.g. read-only (the write
    call exits non-zero), and .githooks's required files missing even
    after a successful config write. Never raises -- same fail-open
    contract as the rest of this channel.

    Deliberately attempted ONLY for the UNSET case -- NOT when
    core.hooksPath already resolves to some OTHER path (that branch,
    handled entirely by the caller, never calls this function): an
    already-present value is somebody's explicit prior configuration
    (human or an earlier session), silently overwriting it is exactly
    the harm the spec's carve-out exists to prevent ("не перетирать
    чужой выбор молча"). Only a genuinely unset hooksPath is treated as
    "nothing to preserve, safe to wire up automatically"."""
    base_warning = f"core.hooksPath not set -- {reason}"
    try:
        set_result = subprocess.run(
            ["git", "config", "--local", "core.hooksPath", str(_GITHOOKS_DIRNAME)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as e:
        detail = _ascii_sanitize(f"git config write failed ({type(e).__name__})", 120)
        return f"{base_warning}; autofix failed: {detail}"

    if set_result.returncode != 0:
        stderr_lines = (set_result.stderr or "").strip().splitlines()
        raw_detail = stderr_lines[0] if stderr_lines else f"exit code {set_result.returncode}"
        detail = _ascii_sanitize(raw_detail, 120)
        return f"{base_warning}; autofix failed: git config write error ({detail})"

    missing = [
        name
        for name in _REQUIRED_GITHOOKS
        if not (root / _GITHOOKS_DIRNAME / name).is_file()
    ]
    if missing:
        missing_str = _ascii_sanitize(", ".join(missing), 120)
        return (
            f"{base_warning}; autofix set core.hooksPath but required"
            f" file(s) still missing: {missing_str}"
        )

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
    present with a mode other than 100755 (committed non-executable)."""
    root = Path(root)
    expected = (root / _GITHOOKS_DIRNAME).resolve()
    reason = "journal_validator/mechanism_gate do not run on commits"

    try:
        result = subprocess.run(
            ["git", "config", "core.hooksPath"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
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
            ["git", "ls-files", "-s", "--", _GITHOOKS_DIRNAME],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
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
    except Exception as e:
        return [
            _ascii_sanitize(
                f"WIRING WARNING: check failed internally ({type(e).__name__})",
                _WIRING_LINE_MAX_LEN,
            )
        ]

    warnings = list(git_warnings) + list(harness_warnings)
    if not python_path:
        warnings.append("python not found on PATH")

    if not warnings:
        python_safe = _ascii_sanitize(python_path, 150)
        line = (
            "WIRING: OK (git hooks: pre-commit, commit-msg;"
            f" harness hooks: {importable_count} files importable; python: {python_safe})"
        )
        return [_ascii_sanitize(line, _WIRING_LINE_MAX_LEN)]
    return [
        _ascii_sanitize(_wiring_line_for(w), _WIRING_LINE_MAX_LEN) for w in warnings
    ]


def build_context_lines(
    root: Path = None,
    now: datetime.datetime = None,
    stdin_payload=None,
) -> list:
    root = Path(root) if root else repo_root()
    now = now or datetime.datetime.now()
    gateway_root = root / "gateway"

    events = read_journal_events(root)

    lines = [now_line(now), model_line(stdin_payload), last_event_line(events)]

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

    return lines[:MAX_LINES]


def main(root: Path = None) -> int:
    """The ONE try/except boundary for the whole script (spec: 'НИКОГДА
    не падает -> одна строка -> exit 0'). Deliberately not per-section:
    a partially-built context (e.g. journal read fine, quota lookup
    half-crashed) is a worse failure mode than no context at all --
    a session trusting a half-populated 'reality' block is exactly the
    kind of silent gap this hook exists to prevent. So any error, from
    anywhere in reading stdin or build_context_lines(), discards
    everything gathered so far and prints only the warning line."""
    try:
        stdin_payload = read_stdin_payload()
        for line in build_context_lines(root, stdin_payload=stdin_payload):
            print(line)
    except Exception as e:  # fail-open: this hook must never break session start
        print(f"session-context warning: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
