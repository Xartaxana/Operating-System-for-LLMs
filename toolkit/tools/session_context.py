"""SessionStart hook: surfaces "reality in the background" -- a few
measured facts a fresh session shouldn't have to ask about before
trusting its own boot picture:

- MODEL: which tier is this session actually running on (a measured
  input for the in-session tier-check, not the session narrating its
  own model name).
- BOOT BUDGET: how big is the boot path right now, against WARN/BREACH
  thresholds, without waiting for a weekly calibration run or a manual
  byte count to notice a slow creep.
- OPEN DISPATCH: task_ids the routing journal still shows as
  outstanding. Class-defect this line guards against: a session wrote
  a `delegated` event to the routing log and never actually launched
  the worker -- a phantom open dispatch, the journal recording intent
  as fact (kin to the NOW line's anti-narrative-timestamp guard, but
  for task lifecycles instead of clocks). A task_id counts as OPEN iff
  its LAST lifecycle event (delegated/accepted/rejected/escalated/
  decomposable -- see _OPEN_LIFECYCLE_EVENTS) is `delegated`; anything
  else (dispatch_skipped, defect_found, lead_*, journal_created,
  calibrated) neither opens nor closes a task BY ITS OWN TYPE -- but its
  `notes` field is still scanned for a `closes:<task-id>` token (see
  _CLOSES_RE below), which DOES close a task regardless of the event's
  own type.

A SessionStart hook registered in .claude/settings.json is a
self-activating enforcement file: it was delivered under a sibling
filename and placed on this live path only at review/acceptance time,
not by whoever wrote it.

Adds the `closes:<task-id>` token scan
(previously, this hook read only event TYPES, so a plain-English
closing note in a later event's `notes` was invisible to it and
produced a false OPEN DISPATCH line for a task already closed out in
prose) and tightens the BOOT BUDGET breach line so it cannot be
misread as a self-authorizing command (see boot_budget_lines()).

Hard constraints (all load-bearing):
- NEVER breaks session start: any exception anywhere below collapses to
  ONE line, 'session-context warning: ...', and exit 0 (fail-open).
  main() is the single try/except boundary -- see its docstring for why
  a per-section try/except was deliberately NOT used. The
  open_dispatches()/open_dispatch_lines() functions follow the same
  rule: no local try/except, failures propagate to main()'s one
  boundary, exactly like quota_lines().
- Fast (<2s) and NO network at all (the NOW line's whole point is to
  guard against a narrative-future timestamp: read the system clock,
  not a narrated/inferred time).
- ASCII-safe output: some consoles run a non-UTF8 codepage. Every line
  built here is plain ASCII -- including the one line built from a
  NON-hardcoded source (MODEL from stdin), which goes through
  _ascii_sanitize (unsanitized stdin could break this invariant, inject
  lines past MAX_LINES, or crash print mid-flush). OPEN DISPATCH lines
  are built from journal-sourced task_id/agent/ts, also externally
  sourced (an agent field could in principle carry anything a session
  wrote into the journal) -- so each of those three values is routed
  through the same _ascii_sanitize helper before being formatted into
  a line.
- <=25 lines total (MAX_LINES) -- the OPEN DISPATCH addition can only
  ever add up to 4 lines (3 OPEN DISPATCH + 1 summary), and
  build_context_lines() still truncates to MAX_LINES at the end.
- Reading stdin must never block: only attempted when stdin is not a
  TTY (a manual `python tools/session_context.py` run from an
  interactive shell with nothing piped in must return instantly, not
  hang waiting for input that will never come).

Registered as the SessionStart hook via .claude/settings.json.

--- hardened after a live incident (two-part addition) ---

Part A: HOOKSPATH AUTOFIX (`hooks_path_autofix_line`). If
core.hooksPath comes back UNSET, this hook attempts a one-line
self-heal -- `git config --local core.hooksPath .githooks` -- before
falling back to a plain warning; a confirmed success prints "WIRING
AUTOFIX: core.hooksPath set to .githooks" instead. Deliberately scoped
to the UNSET case only: when core.hooksPath is already set to some
OTHER path, that is somebody's existing configuration (human or a
prior session) and is left alone -- only a genuinely empty value is
treated as safe to wire up automatically. This is the ONE write action
in the wiring area; tools/wiring_check.py (a separate, more general
auditor, see its own module docstring) is READ-ONLY by design and
never attempts this fix itself -- running it right after a
SessionStart that just autofixed hooksPath will usually find it
already resolved.

Part B: CLOCK DRIFT (`clock_drift_line`). When the journal tail
event's ts is more than `_CLOCK_DRIFT_THRESHOLD_SECONDS` (60s) AHEAD
of the system clock, prints "CLOCK DRIFT: ..." so a session notices a
clock mismatch between environments instead of silently producing
non-monotonic ts ordering on its next journal append. Fail-open on an
empty journal, a missing/blank tail ts, or a tail ts that does not
parse as the journal's naive-ISO format.

--- WIRING summary line (see tools/wiring_check.py for the actual checks) ---

`wiring_summary_line` calls tools/wiring_check.py's `check_wiring()`
and folds its result into ONE line here: "WIRING: OK" when clean, or
"WIRING: N issue(s), run tools/wiring_check.py --check" for the
details, rather than reproducing wiring_check's full multi-line report
inline -- this hook's own MAX_LINES budget (25 lines total, shared with
NOW/MODEL/JOURNAL/QUOTA/BOOT BUDGET) is not the place for a
potentially-long issue list; `python tools/wiring_check.py --check`
prints the full breakdown on demand. Wrapped in its own try/except
(same pattern as quota_lines()'s local catch): a wiring_check import or
call failure must not blank NOW/MODEL/JOURNAL/etc. via main()'s outer
boundary -- it degrades to one "WIRING: check unavailable (...)" line
instead.
"""

import datetime
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

# N4 (carried forward from review): this import used to sit
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

# Boot-budget thresholds (bytes).
BOOT_WARN_THRESHOLD = 90000
BOOT_BREACH_THRESHOLD = 100000
BOOT_BUDGET_LIMIT = 100000

_ALWAYS_INCLUDE_BOOT_FILE = "CLAUDE.md"

# Personal WARN threshold for the kit's OWN CLAUDE.md, layered on top of
# the whole-boot-path thresholds above (a narrower, earlier-firing signal:
# only the CLAUDE-layer of a boot diet is due, not necessarily the whole
# boot path). Simplified relative to the staff deployment's own ratchet
# (WARN-only here, no BREACH/ratchet-ceiling machinery -- not requested
# by this port): a fixed WARN constant with >=15% headroom over a
# measured baseline, re-derived by hand when it goes stale.
#
# Re-derived 2026-08-25 (kit-v0.9.0 port): toolkit/CLAUDE.md was 48716
# bytes AT THE TIME OF THIS MEASUREMENT -- taken AFTER an earlier
# port of toolkit/CLAUDE.md's content landed (the prior baseline below,
# 46323 bytes, was measured BEFORE that port and is now superseded).
# WARN = ceil(measured * 1.15 / 100) * 100:
# ceil(48716 * 1.15 / 100) * 100 = 56100 (margin over measured:
# (56100 - 48716) / 48716 = ~15.16%, >= the 15% floor).
# Prior measurement (now stale, kept for history): 2026-08-25 node C1,
# 46323 bytes -> CLAUDE_WARN = 53300.
# RE-DERIVE AT ONBOARDING: recompute this constant as
# ceil(os.path.getsize("CLAUDE.md") * 1.15 / 100) * 100 whenever it goes
# stale (kit CLAUDE.md size drifted) -- lowering is always safe; raising
# should keep the same >=15% margin.
CLAUDE_WARN = 56100

_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# Tier mapping: substring of the model id (lowercased) -> tier
# label. Order matters only in that each id is expected to match at
# most one of these; first match wins.
_MODEL_TIER_SUBSTRINGS = (
    ("fable", "Lead(top)"),
    ("opus", "critic-tier"),
    ("sonnet", "builder-tier"),
    ("haiku", "scout-tier"),
)

# Events that open/close a dispatch's lifecycle. A task_id is OPEN iff
# its LAST such event is 'delegated'. Events outside this set
# (dispatch_skipped, defect_found, lead_*, journal_created, calibrated)
# neither open nor close a task BY THEIR OWN TYPE -- but see _CLOSES_RE
# below: their `notes` field is still scanned for closes: tokens.
_OPEN_LIFECYCLE_EVENTS = {"delegated", "accepted", "rejected", "escalated", "decomposable"}

# A bare `closes:<task-id>` token in ANY event's notes closes that
# task_id's open dispatch (CLAUDE.md's own convention for closing an
# open dispatch inside a later event's notes). The format is
# deliberately exact -- no whitespace after the colon, lowercase
# literal, the id must start with `t-` -- the same "bare token right
# after the colon" contract as `replaces_worker:` (a regex takes the
# first non-whitespace token, so loose punctuation right after the
# marker breaks the match by design).
#
# Left-anchored: an unanchored `closes:` substring would otherwise
# match INSIDE a longer word too -- `discloses:t-001` or
# `encloses:t-133` both contain the literal "closes:" and would
# silently close a task nobody meant to close (the dangerous
# direction: a false CLOSE hides a real phantom dispatch). `(?<!\w)`
# requires the character immediately before "closes:" to be either
# absent (start of string) or a non-word character -- so start-of-notes
# and punctuation/whitespace before the token are both legal, but a
# preceding letter/digit/underscore is not.
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


# Threshold (seconds)
# above which the tail journal event's ts being AHEAD of the system
# clock is worth a line of its own, rather than silent noise from
# ordinary sub-second/sub-minute scheduling jitter between when an
# event was written and when this hook happens to run.
_CLOCK_DRIFT_THRESHOLD_SECONDS = 60


def clock_drift_line(events: list, now: datetime.datetime = None) -> str:
    """NOW and LAST EVENT
    are printed side by side already; this makes an actual DRIFT
    between them visible instead of leaving a session to notice the
    mismatch by eye: if the tail event's ts is MORE than
    _CLOCK_DRIFT_THRESHOLD_SECONDS ahead of `now`, any event this
    session appends will sit, by ts, BEFORE that tail line -- not a
    rewrite of the past, but the same non-monotonic-journal symptom a
    reader would otherwise blame on a rewrite. Returns '' (no line)
    when the journal is empty, the tail event carries no/blank ts, that
    ts is not parseable as the journal's naive-ISO format, or the drift
    is at or under the threshold -- fail-open by construction, same
    contract as last_calibration_line()'s own parse_ts() use (a
    ValueError/TypeError from parse_ts on a malformed ts is caught
    here; an ImportError/SyntaxError from the deferred preflight_quota
    import itself is deliberately NOT caught, same as quota_lines()'s
    own re-raise of those two -- see the module-level N4 comment)."""
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
        " -- new events will be non-monotonic (do not rewrite past lines)"
    )


def open_degradation_window(events: list):
    """Scans the WHOLE journal (not just the tail): an unclosed
    lead_degraded can be arbitrarily far back if lead_restored never
    followed (a safety-reset can leave the window open with
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
    event from _OPEN_LIFECYCLE_EVENTS is 'delegated' (a delegated with
    no closing event is a phantom open dispatch -- the class-defect
    that motivated this hook line: a session wrote 'delegated' and
    never launched the worker). Returns those last-delegated event
    dicts sorted by ts ascending (oldest first). Continuation
    dispatches (critic-gate entry) and retries stay open until a
    closing event. No local try/except -- failures propagate to
    main()'s single fail-open boundary, like quota_lines().

    Closure by `accepted` is JOURNAL LAW, not event ordering: reopen
    after accepted is forbidden (validator-enforced), so ANY accepted
    closes its task unconditionally -- regardless of where the line
    sits or what ts it carries. This is what survives two live journal
    anomalies in opposite directions -- a mid-file retro insertion
    where position lies, and a mistyped ts where ts lies; the
    accepted-law resolves both. No (ts, position) ordering rule can
    resolve both directions at once; the law does not need to. For
    tasks WITHOUT an accepted, 'last' is judged by (ts, file position):
    max ts wins, file position only breaks exact ts ties (retro pairs
    share one ts, and the closing line is written below the delegated
    one, so on a tie the later line wins).

    A plain-English closing note in a later
    event's `notes` used to be invisible to this scan (it only ever
    read event TYPE), producing false OPEN DISPATCH lines for tasks
    already closed out in the journal's own prose. Fix: a bare
    `closes:t-NNN` token (see _CLOSES_RE) in ANY event's notes --
    lifecycle or not, e.g. `calibrated`, `dispatch_skipped` -- is a
    closing TOUCH of that task, keyed by the marker-carrying event's own
    (ts, file_idx). Per task_id, every touch is compared as
    (ts, idx, sub): a real lifecycle event contributes sub=0, a closes:
    marker contributes sub=1 at the SAME (ts, idx) as the event it sits
    in -- so at an exact tie the marker outranks the lifecycle event it
    came from. The task is OPEN iff its overall-latest touch is a real
    `delegated` event: a later marker closes it (even one sitting in an
    unrelated event's notes); a later `delegated` (retry/replacement)
    reopens it past an earlier marker; and -- documented as a
    deliberate contract, not a bug -- a closes:t-X token placed in t-X's
    OWN delegated event's notes closes that same event, because its
    marker-touch key ties the lifecycle key and the marker wins ties.
    `accepted` does not participate in this ts/idx comparison at all: it
    stays the unconditional law above, checked first and independent of
    any marker."""
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
    agent and ts are journal-sourced -> each goes through
    _ascii_sanitize (non-UTF8-console invariant). Empty when nothing is
    open."""
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
    tokens (spec: don't hardcode the limit, just report
    'requests last 24h: N')."""
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

    An EXISTING-but-unparseable config.yaml (corrupt YAML content, NOT
    absence -- preflight_quota.load_config() only guards absence, per
    its own docstring, and still lets yaml.YAMLError propagate on
    corrupt content) is caught HERE, locally, and reported as a single
    "quota: config unreadable (<reason>)" line instead of propagating
    uncaught to main()'s single fail-open boundary. This is a
    DELIBERATE, NARROW reversal of this file's general "half a context
    is worse than none" principle (see main()'s docstring) for JUST
    this one section: a session losing NOW/MODEL/LAST EVENT/BOOT
    BUDGET too, over a fault scoped entirely to the quota subsystem's
    own config file, is a strictly worse outcome than a full context
    with one line explicitly marked broken. Any OTHER, genuinely
    unforeseen failure below this point (e.g. an unreadable requests.db)
    still propagates unchanged to main()'s outer boundary -- this
    reversal was originally scoped to load_config() alone; a malformed
    budgets.yaml is a DIFFERENT (and now closed) case:
    preflight_quota.load_budgets() got its OWN internal parse-guard (see
    that function's docstring) -- it never raises on corrupt content in
    the first place, so there is nothing left here to catch for that
    path. This function surfaces load_budgets()'s honest "_parse_error"
    key (if present) as one additional "quota: budgets unreadable
    (<reason>)" line -- see the lines below load_config()'s try/except
    for that wiring; unlike the config.yaml case, a broken budgets.yaml
    does NOT blank the rest of quota_lines()'s output, because the
    failure is caught INSIDE load_budgets() itself, not by unwinding out
    of this function. ImportError/SyntaxError are deliberately
    RE-RAISED, not caught here (N4): those
    mean the quota subsystem ITSELF is unusable (missing yaml, a broken
    preflight_quota sibling module) -- a different failure class from
    "this config.yaml's own content is broken" -- and must still reach
    main()'s single fail-open boundary unchanged."""
    lines = []
    try:
        config = load_config(gateway_root)
    except (ImportError, SyntaxError):
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

    # load_budgets() now guards budgets.yaml parsing internally (see its
    # own docstring in preflight_quota.py) and honestly returns
    # "_parse_error" instead of raising -- this caller HAS an output
    # line for the reason, so it shows it: the rest of this section
    # (per-alias QUOTA/REQUESTS lines, built from config, not budgets)
    # still prints normally alongside it -- unlike a broken config.yaml
    # (which blanks this whole function to one marker line), a broken
    # budgets.yaml does not, because the failure is contained INSIDE
    # load_budgets() rather than caught here.
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
# MODEL line
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# stdin-deadline helper: reading stdin to EOF must never hang session start
# forever on a harness that opens the pipe but never actually writes/closes
# it. A daemon thread does the blocking read; the main thread joins on a
# deadline instead of calling sys.stdin.read() directly. TTY input is still
# never read at all (unchanged contract) -- read_stdin_payload() below keeps
# that guard. On a timeout, the payload degrades to "no payload" (None),
# never a crash -- the rest of this hook already treats None exactly like
# "no model info in the harness's stdin JSON".
# ---------------------------------------------------------------------------

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
    """Returns (bytes, timed_out). Reads stdin to EOF, bounded by the
    deadline above. A background daemon thread does the actual blocking
    read; the deadline is enforced via thread.join(timeout) -- portable
    across platforms where select/poll do not work on pipes (Windows).
    A TTY returns b"" immediately, without reading anything (same guard
    read_stdin_payload() used to apply itself). Any read error degrades to
    b"" -- fail-open, same discipline as the rest of this hook."""
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

# Set by read_stdin_payload() when a stdin read actually timed out. The
# stdin-reader thread above is left running as a daemon (it may still be
# blocked deep inside a platform read syscall) -- on normal interpreter
# shutdown, a background thread blocked on the real stdin buffered reader
# can crash the process ("Fatal Python error: _enter_buffered_busy")
# instead of exiting cleanly. main()'s own try/except does NOT see this
# (read_stdin_payload() already degraded to None, business as usual) --
# the crash would only surface LATER, at normal process exit. The
# __main__ guard at the bottom of this file checks this flag AFTER
# main() has fully returned and calls os._exit() instead of falling
# through to the normal interpreter shutdown path.
_STDIN_DEADLINE_STATE = {"hit": False}


def read_stdin_payload():
    """Reads and JSON-parses stdin, but ONLY when stdin is not a TTY.
    A SessionStart hook receives the harness's JSON on stdin; a human
    running this script by hand from an interactive shell has no piped
    input -- the TTY guard (now inside _read_stdin_bytes_deadline()) is
    what keeps both modes safe, and a non-TTY read that never reaches EOF
    is now bounded by the stdin deadline above instead of blocking
    forever. Any failure (unreadable stdin, empty input, invalid JSON, a
    stdin deadline) returns None rather than raising; callers treat None
    exactly like "no model info". Reads raw bytes via the deadline helper
    and decodes explicitly (utf-8, replace) rather than going through
    Python's platform-encoding text layer."""
    raw_bytes, timed_out = _read_stdin_bytes_deadline()
    if timed_out:
        _STDIN_DEADLINE_STATE["hit"] = True
        try:
            sys.stderr.write(f"{Path(__file__).name}: {_STDIN_DEADLINE_MSG}\n")
        except Exception:
            pass
        return None
    if not raw_bytes:
        return None
    data = raw_bytes.decode("utf-8", "replace")
    if not data.strip():
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# stdout-deadline helper: mirrors the stdin-deadline helper above (same
# daemon-thread-plus-join(deadline) shape), for WRITING instead of reading.
# A landed SessionStart hook can write several KB in one call; a harness
# that does not drain its child's stdout concurrently would otherwise block
# that write forever once the OS pipe fills -- session start would never
# return, which is strictly worse than every other failure mode this file
# already guards against (truncation, a blanked context). On a timeout,
# main() must call os._exit(0) immediately (see _write_stdout_deadline's
# own docstring below for why even a diagnostic write would hang the same
# way).
# ---------------------------------------------------------------------------

_STDOUT_DEADLINE_DEFAULT = 5.0
_STDOUT_DEADLINE_MAX = 600.0
_STDOUT_DEADLINE_ENV = "OSLLM_STDOUT_TIMEOUT"


def _stdout_deadline_seconds():
    """Seconds to wait for the write to complete: env override, else the
    default. Same validation shape as _stdin_deadline_seconds() above:
    invalid, non-numeric, <=0, or > _STDOUT_DEADLINE_MAX fall back to the
    default; no "0 = wait forever" mode, same reasoning as the read side."""
    try:
        value = float(os.environ.get(_STDOUT_DEADLINE_ENV, ""))
    except (TypeError, ValueError):
        return _STDOUT_DEADLINE_DEFAULT
    if not (0.0 < value <= _STDOUT_DEADLINE_MAX):
        return _STDOUT_DEADLINE_DEFAULT
    return value


def _write_stdout_deadline(text: str) -> bool:
    """Writes `text` in ONE logical write (sys.stdout.write + flush) on a
    daemon thread; the main thread joins on a deadline -- the write-side
    mirror of _read_stdin_bytes_deadline() above. The write stays exactly
    ONE call (never split into chunks): chunking would not help against a
    non-draining consumer -- it blocks on total volume, not on the size of
    a single call, and splitting would break the "one logical write"
    invariant the rest of this module relies on.

    Returns True if the writer thread finished within the deadline
    (write+flush either succeeded, or raised an ordinary exception -- see
    below); False if the thread is still alive when the deadline expires:
    a non-draining consumer left write() stuck inside the OS on a full,
    unread pipe.

    An exception raised INSIDE the writer thread (e.g. OSError on an
    already-closed stdout) is caught there and RE-RAISED here, on the
    main thread, after join() -- but only on the True path (the thread
    actually finished): callers see this exactly as they would have seen
    it from a direct sys.stdout.write() call, so main()'s existing
    fail-open except block is unchanged. On an actual timeout (False)
    there is no exception to raise -- the thread is still blocked inside
    the write syscall itself, not failed.

    CRITICAL for the caller: on False (timeout), it MUST call os._exit(0)
    immediately and attempt NO further writes anywhere -- not stdout (the
    same stuck channel), not stderr (often the same terminal/consumer).
    The writer thread is, at that moment, blocked inside the OS on a full
    pipe; any further write to the same class of resource would hang for
    the same reason, so attempting to report the timeout would itself
    become a second hang rather than a diagnostic. The thread stays a
    daemon and keeps hanging in the background after os._exit(0) --
    os._exit() does not wait for it or touch its state (interpreter
    shutdown/atexit is skipped entirely), which is what makes the
    immediate exit safe regardless of whether that thread ever unblocks."""
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


def extract_source(payload) -> "str | None":
    """Looks for the SessionStart "source" field on the harness payload
    (mirrors extract_model_id's defensive style). Returns
    payload.get("source") only when payload is a dict AND that value is
    a non-empty string; every other shape (non-dict payload, missing
    key, empty string, non-string value) returns None."""
    if not isinstance(payload, dict):
        return None
    source = payload.get("source")
    if isinstance(source, str) and source:
        return source
    return None


# Sources meaning "state already carries over" -- Layer A inline
# injection must NOT fire for these (re-injecting the whole boot-file
# block on every resume/compact would pay its full byte cost again, on
# top of what a resume/compact summary already covers). Any OTHER
# source string, including None (missing/unrecognized), still fires --
# fail TOWARD booting rather than silently going quiet on a future
# harness source value this module does not yet recognize.
_AUTOBOOT_NO_FIRE_SOURCES = {"resume", "compact"}


def should_emit_layer_a(source) -> bool:
    return source not in _AUTOBOOT_NO_FIRE_SOURCES


def model_tier(model_id: str) -> str:
    low = model_id.lower()
    for substr, tier in _MODEL_TIER_SUBSTRINGS:
        if substr in low:
            return tier
    return "unknown"


def _ascii_sanitize(s: str, max_len: int = 80) -> str:
    """Fix for the class "an output line built from a NON-hardcoded
    source must stay ASCII/single-line before a non-UTF8 console".
    MODEL was this module's only externally-sourced input at the time
    that class was named; the OPEN DISPATCH lines are the second
    consumer -- task_id/agent/ts there are journal-sourced (a session
    could in principle write anything into those fields), so they route
    through this same helper rather than getting a parallel one."""
    s = str(s).strip()
    s = re.sub(r"[\x00-\x1f\x7f]", "", s)  # control chars incl. \n \r \t
    s = s.encode("ascii", "replace").decode("ascii")
    return s[:max_len]


def model_line(stdin_payload=None) -> str:
    """The payload model is the harness's SessionStart
    DECLARATION, not a measurement -- it can be stale (observed live: a
    payload named a lower tier than the session actually ran on; the
    provider-side usage log was the ground truth). A present-but-stale
    id stated confidently is worse than an absent one, so the line
    carries the "declared by harness, not measured" marker. An
    in-hook measured cross-check is NOT implementable at SessionStart
    time: the session's own first request has not landed in the usage
    database yet, so the freshest rows there belong to a previous
    session -- a recorded limitation, not an oversight. The measured
    verification duty stays where it already lives: the tier-
    verification-at-entry check (in-session) and the weekly
    calibration's transcripts-vs-declarations check."""
    model_id = extract_model_id(stdin_payload)
    if not model_id:
        return "MODEL: not provided by hook input -- verify tier yourself"
    sanitized = _ascii_sanitize(model_id)
    if not sanitized:
        # whitespace-only (or entirely-stripped) model id: same fallback
        # as "no model id at all" -- there is nothing left to report.
        return "MODEL: not provided by hook input -- verify tier yourself"
    tier = model_tier(sanitized)
    return (
        f"MODEL: {sanitized} -> tier {tier}"
        " (declared by harness, not measured; Lead tier = fable)"
    )


# ---------------------------------------------------------------------------
# BOOT BUDGET line(s)
# ---------------------------------------------------------------------------


def boot_path_files(root: Path) -> list:
    """Parses BOOT.md's own "Read X.md" lines for the boot-path file
    list (BOOT.md stays the single owner of that list -- this hook only
    mirrors it for budget arithmetic, it does not maintain a second copy
    of the sequence), then always appends CLAUDE.md, which the harness
    auto-loads separately from the BOOT.md sequence but still
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
    crosses either the WARN (>90000) or BREACH (>100000) threshold."""
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
        # auto-run command -- boot recovery is not work authorization by
        # itself (a breach line is a flag for the report, not a silent
        # trigger to start the diet before the operator has seen it).
        status_suffix = " BREACH -> boot-diet due (report first, operator word starts it)"
    elif total > BOOT_WARN_THRESHOLD:
        status_suffix = " WARN"
    else:
        status_suffix = ""

    # Personal CLAUDE.md ratchet suffix -- printed ALWAYS (unlike the
    # WARN/BREACH pieces above, which only appear once the WHOLE boot
    # path is over threshold): this is a narrower, earlier signal that
    # only the CLAUDE.md layer of a boot diet is due. Comparison is
    # strictly ">", matching BOOT_WARN/BREACH above; a missing CLAUDE.md
    # prints "missing", never "under budget".
    claude_size = next(
        (size for name, size in sizes if name == _ALWAYS_INCLUDE_BOOT_FILE), 0
    )
    if _ALWAYS_INCLUDE_BOOT_FILE in missing:
        claude_suffix = f" | {_ALWAYS_INCLUDE_BOOT_FILE}: missing"
    else:
        claude_suffix = f" | {_ALWAYS_INCLUDE_BOOT_FILE}: {claude_size}/{CLAUDE_WARN}"
        if claude_size > CLAUDE_WARN:
            claude_suffix += (
                " OVER -> boot-diet due (CLAUDE layer; report first,"
                " operator word starts it)"
            )

    lines = [base + missing_suffix + status_suffix + claude_suffix]

    if status_suffix:
        top3 = sorted(sizes, key=lambda t: t[1], reverse=True)[:3]
        for name, size in top3:
            lines.append(f"  {size}  {name}")

    return lines


# ---------------------------------------------------------------------------
# HOOKSPATH AUTOFIX
# ---------------------------------------------------------------------------

_GITHOOKS_DIRNAME = ".githooks"
_REQUIRED_GITHOOKS = ("pre-commit", "commit-msg")

# A fact string returned by _try_hookspath_autofix() on a CONFIRMED
# success is prefixed with this marker so hooks_path_autofix_line() can
# tell it apart from an ordinary warning fact and render it as "WIRING
# AUTOFIX: ..." instead of "WIRING WARNING: ...".
_AUTOFIX_FACT_PREFIX = "AUTOFIX: "


def _try_hookspath_autofix(root: Path, reason: str) -> str:
    """core.hooksPath came back UNSET -- before falling back to the
    plain 'core.hooksPath not set' warning, attempt the one-line
    self-heal `git config --local core.hooksPath .githooks` (relative
    path, LOCAL repo config only -- never --global/--system) and
    recheck.

    Returns the AUTOFIX fact (_AUTOFIX_FACT_PREFIX + "core.hooksPath
    set to .githooks") on a confirmed success: the `git config` write
    itself exited 0 AND both required hook files are actually present
    on disk under .githooks/ afterward (setting hooksPath to a
    directory whose hook files don't exist would "succeed" as a git
    operation while leaving the wiring exactly as broken as before).
    Any other outcome returns the ORIGINAL 'core.hooksPath not set'
    warning fact with an "; autofix failed: <reason>" suffix -- git
    itself unavailable/erroring (the write call raises), the config
    being unwritable (the write call exits non-zero), or the required
    hook files missing even after a successful config write. Never
    raises -- same fail-open contract as the rest of this hook.

    Deliberately attempted ONLY for the UNSET case -- NOT when
    core.hooksPath already resolves to some OTHER path: an
    already-present value is somebody's explicit prior configuration
    (human or an earlier session), silently overwriting it is exactly
    the harm this carve-out exists to prevent. Only a genuinely unset
    hooksPath is treated as "nothing to preserve, safe to wire up
    automatically".

    GIT SUBPROCESS ENCODING FIX (2026-08-10, sibling of the same class
    fixed in tools/session_context.py's git_hooks_channel and
    toolkit/tools/wiring_check.py's `_run_git`): this call and
    hooks_path_autofix_line's `git config core.hooksPath` read below
    now pass `encoding="utf-8", errors="replace"` instead of a bare
    `text=True` -- a non-UTF-8 console locale would otherwise let
    Python decode git's always-UTF-8 output via
    locale.getpreferredencoding(), silently mojibake-ing a non-ASCII
    value before it is ever compared or reported. quotepath is not
    applicable here -- neither call lists tracked paths, only reads/
    writes a single config value."""
    base_warning = f"core.hooksPath not set -- {reason}"
    try:
        set_result = subprocess.run(
            ["git", "config", "--local", "core.hooksPath", str(_GITHOOKS_DIRNAME)],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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


def hooks_path_autofix_line(root: Path) -> str:
    """Checks core.hooksPath and, ONLY when it is UNSET, attempts the
    self-heal above and returns one WIRING line reporting the outcome
    ("WIRING AUTOFIX: ..." on success, "WIRING WARNING: ..." on
    failure). When core.hooksPath is already set to ANYTHING (correct
    or not), returns '' -- that broader mismatch is
    tools/wiring_check.py's job to report via wiring_summary_line()
    below, not duplicated here. Never raises: a git invocation that
    fails to even run degrades to '' (silently deferring the whole
    fact to wiring_summary_line(), which runs its own independent git
    check and reports it there instead of this function guessing at a
    warning message for a git failure it cannot itself diagnose)."""
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
        )
    except Exception:
        return ""

    raw = (result.stdout or "").strip()
    if result.returncode != 0 or not raw:
        fact = _try_hookspath_autofix(root, reason)
        if fact.startswith(_AUTOFIX_FACT_PREFIX):
            return f"WIRING {fact}"
        return f"WIRING WARNING: {fact}"

    # Already set to something -- correct or not, left to
    # wiring_summary_line()/tools/wiring_check.py to report; no
    # duplicate line from here.
    return ""


# ---------------------------------------------------------------------------
# GATE BREAK-GLASS surfacing (release-gate v0.8.1, F2 -- ported from
# tools/session_context.py's own select_and_ack_break_glass_lines()/
# break_glass_lines(); see that module's docstring above
# _break_glass_candidates() for the full attempt-2 rationale this port
# carries over unchanged: ack-only-shown-lines, the 5-fact cap, the
# read-only-tracks + sidecar-ack split, and the list-not-overwrite
# fix). tools/main_gate.py and tools/dod_gate.py's "skip the 3rd
# consecutive block" safety valve appends a persistent unsafe_completion
# fact into the dod_track file itself; this block is the surfacing
# half -- on the NEXT SessionStart, scan every
# .claude/dod_track/<session_id>.json for facts not yet acknowledged
# and print one loud line per fact (up to a cap), exactly once.
#
#  1. ACK ONLY SURVIVING LINES: candidate lines are built READ-ONLY
#     first (_break_glass_candidates, no ack write at all), and
#     select_and_ack_break_glass_lines() below is the ONLY place that
#     acknowledges -- it is called from build_context_lines() with the
#     lines ALREADY built so far, computes how much of the MAX_LINES
#     budget is actually left, and acks ONLY the facts whose lines fit
#     in that remaining space. A fact that does not fit is not acked
#     and resurfaces on the next SessionStart.
#  2. CAP. At most _BREAK_GLASS_LINE_CAP (5) individual fact lines per
#     call, plus one trailing "... and N more ... pending" summary
#     line when more remain -- N (and the facts behind it) are
#     explicitly NOT acked, so they queue for a future call. The
#     summary line itself carries no ack key (key=None).
#  3. .claude/dod_track/<session_id>.json files are shared, live state
#     -- a DIFFERENT/parallel session's PostToolUse hook may still be
#     read-modify-writing the SAME track file at the exact moment this
#     scan runs. This whole block is READ-ONLY on dod_track/*.json;
#     acknowledgement state lives in its OWN sidecar file,
#     .claude/dod_track/break_glass_ack.json, whose SOLE writer/owner
#     is this module. Fact identity for the ack key: session_id
#     (filename stem) + gate ("main"/"dod") + agent_key (per_agent's
#     own dict key, or "" for the agent-less main gate) + the fact's
#     own "ts" + the fact's INDEX within its own facts list -- the
#     index is load-bearing (not optional): "ts" ALONE can collide
#     (two facts of the same session/gate/agent observed with a
#     byte-identical ts).
#  4. This module reads BOTH the plural list ("unsafe_completions",
#     iterated in full) AND the legacy singular ("unsafe_completion")
#     dict, so an already-written singular-shaped track file, if one
#     ever existed on disk, is not silently orphaned.
#
# ASCII invariant: same discipline as MODEL/OPEN DISPATCH/WIRING above
# -- reason/ts/session_id/gate are all sourced from a dod_track JSON
# file a session itself wrote, so each goes through _ascii_sanitize
# before being interpolated.
#
# Fail-open per file: a corrupt/unreadable JSON file is skipped
# SILENTLY (no warning line, no exception) -- the sibling file next to
# it must still surface normally. A broken/unreadable sidecar file
# itself degrades to "treat as empty" (nothing acked yet) rather than
# raising -- see _load_break_glass_ack().
# ---------------------------------------------------------------------------

_DOD_TRACK_DIRNAME = Path(".claude") / "dod_track"
_BREAK_GLASS_ACK_FILENAME = "break_glass_ack.json"
_BREAK_GLASS_LINE_CAP = 5


def _extract_unsafe_list(state: dict) -> list:
    """One gate-state dict's (main_gate_state, or one gate_state.per_agent
    entry) unsafe-completion facts, oldest-first: the new plural list key
    "unsafe_completions" (append, never overwrite) PLUS the legacy
    singular "unsafe_completion" dict (kept readable for backward
    compatibility). Tolerant of any malformed shape -- a track file is
    data a hook wrote, not a schema this function enforces."""
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
    uniqueness: "ts" alone is NOT guaranteed unique -- two facts of the
    same session/gate/agent can carry a byte-identical ts (observed:
    Windows wall-clock granularity ~15.6ms repeated within one fast
    process), which would otherwise collapse two DISTINCT facts onto the
    same ack key -- acknowledging the first (because the budget cut lands
    between them) would silently acknowledge the second too, and it would
    never surface. Tolerant of any malformed shape."""
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
            # Index appended: "ts" alone can collide (see
            # _unsafe_completion_facts' docstring) -- the index makes the
            # key unique per fact even when two facts of the same
            # session/gate/agent share a byte-identical ts.
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


def select_and_ack_break_glass_lines(
    root: Path, lines_so_far: list, now: datetime.datetime = None
) -> list:
    """Point 1's fix, as its own testable unit: given the context lines
    ALREADY built (before break-glass lines are appended), returns the
    break-glass candidate lines that FIT within the module's MAX_LINES
    budget, and acknowledges (sidecar-writes) ONLY the individual facts
    behind those surviving lines -- a fact whose line does not fit is left
    unacknowledged and will be offered again on the next call/SessionStart.
    The trailing "... and N more" summary line (if present) is never
    itself ack-able (see _break_glass_candidates) regardless of whether it
    survives the cut."""
    candidates = _break_glass_candidates(root)
    if not candidates:
        return []
    space_left = MAX_LINES - len(lines_so_far)
    if space_left <= 0:
        return []
    shown = candidates[:space_left]
    _ack_break_glass_keys(root, [c["key"] for c in shown], now)
    return [c["line"] for c in shown]


def break_glass_lines(root: Path = None, now: datetime.datetime = None) -> list:
    """Convenience entry point for direct/standalone use (unit tests, ad
    hoc scripts): equivalent to select_and_ack_break_glass_lines() called
    with an EMPTY preceding-lines list, i.e. the full MAX_LINES budget is
    available -- only _BREAK_GLASS_LINE_CAP (point 2) limits the result,
    not the 25-line context budget. build_context_lines() itself does NOT
    call this: it calls select_and_ack_break_glass_lines() directly with
    the lines already built so far (see below), so a fact only gets acked
    when its line actually survives the real 25-line cut (point 1)."""
    root = Path(root) if root else repo_root()
    return select_and_ack_break_glass_lines(root, [], now)


# ---------------------------------------------------------------------------
# WIRING summary line -- see tools/wiring_check.py
# ---------------------------------------------------------------------------


def wiring_summary_line(root: Path) -> str:
    """Calls tools/wiring_check.py's check_wiring() and folds the
    result into ONE line (see the module docstring's "WIRING summary
    line" section for why this stays a single line rather than the
    full multi-line report). Wrapped in its own try/except -- an
    import or call failure here must not blank NOW/MODEL/JOURNAL/etc.
    via main()'s single outer boundary, same rationale as
    quota_lines()'s local catch.

    A non-empty "notices" list (a SEPARATE, non-blocking class -- see
    wiring_check.py's own check_install_parity_notices()) is appended
    as ", N notice(s)" -- on EITHER branch (OK or issue-count), never
    changing which branch fires; a missing/absent "notices" key (an
    older wiring_check.py, or a test double supplying only ok/issues)
    degrades to an empty list, not an exception."""
    try:
        import wiring_check

        result = wiring_check.check_wiring(root)
    except Exception as e:
        return f"WIRING: check unavailable ({type(e).__name__})"

    notice_count = len(result.get("notices") or [])
    notice_suffix = f", {notice_count} notice(s)" if notice_count else ""

    if result.get("ok"):
        return f"WIRING: OK{notice_suffix}"
    count = len(result.get("issues") or [])
    return f"WIRING: {count} issue(s){notice_suffix}, run tools/wiring_check.py --check"


# ---------------------------------------------------------------------------
# LAYER A CONTENT: prints the kit's own boot-file content verbatim,
# alongside the boot-lite context above, instead of leaving a session to
# go re-read those files itself. Ported from the staff deployment's
# equivalent AUTO-BOOT hybrid mechanism (its own session_context.py).
#
# RESOLVED (Lead decision: kit's Layer A
# = the boot list WITHOUT the state file): the kit's own BOOT.md now
# carries the SAME explicit split the staff deployment's BOOT.md
# carries -- a "## Layer A" heading (README/SYSTEM_PROMPT/DECISIONS/
# DELEGATION_TABLE) followed by a "## Layer B" heading
# (CURRENT_CONTEXT.md, the kit's own state file, read by the session
# itself, never injected here). layer_a_file_names() below parses ONLY
# the "Read X.md" lines that fall inside the "## Layer A" section (up
# to the next "## " heading, or end of file if there is none) --
# CURRENT_CONTEXT.md is excluded from injection by construction, the
# same way the staff deployment's own Layer A never includes its state
# file. TEMPORAL EDGE, BOTH WORLDS (R11(c)/D-0054): a BOOT.md that
# still carries no "## Layer A" heading at all (an older/unmarked form,
# or a fresh installation before this port ever landed) falls back to
# the OLD flat-list behavior, MINUS CURRENT_CONTEXT.md by NAME (a
# hardcoded exclusion, not a section boundary) -- the fallback still
# never injects the state file, it just cannot rely on markup that
# is not there.
# ---------------------------------------------------------------------------

# The state file this kit's own Layer A must never include, in BOTH the
# markup-aware path and the flat-list fallback (see above).
_LAYER_A_EXCLUDED_STATE_FILE = "CURRENT_CONTEXT.md"

# Node E item 8: a short, EN, imperative directive printed as the FIRST
# line of the injected block -- tells the reading session it does not
# need to re-read the files about to follow, and that Layer B (state)
# is its own separate responsibility. Placed ahead of the "--- BOOT
# LAYER A INJECTED ..." opening line itself (see layer_a_lines()).
# Prefix DELIBERATELY distinct from the "AUTO-BOOT: Layer A is <N>
# bytes..." threshold-notice line above (a different message on the
# same block) -- test_layer_a_lines_*_warn_threshold_* below asserts
# "AUTO-BOOT: Layer A is" absence/presence to detect ONLY that notice;
# a shared prefix would give it a false positive on every call.
LAYER_A_DIRECTIVE_LINE = (
    "AUTO-BOOT: read Layer A below -- do not re-read these files "
    "yourself; read Layer B (CURRENT_CONTEXT.md) yourself, it is not "
    "injected here; see the closing '--- END BOOT LAYER A: ...' line "
    "for the emission contract (a missing closing line means a "
    "truncated injection -- read the file(s) directly in that case)."
)

# WARN (not a hard cap): the total on-disk byte sum of every layer-A file
# crossing this threshold prints one loud notice line but never truncates
# or skips injection -- the threshold exists so growth of the boot-file
# set is a visible decision, not silent drift. Same value as the staff
# deployment's own constant (16384 bytes) -- a project constant, not
# derived from any one measurement, so it carries no monotonicity claim.
LAYER_A_INLINE_WARN_BYTES = 16384

# Meaning-preserving transliteration table for a narrow console codepage
# (this hook's own ASCII-safe-output invariant, see the module
# docstring): boot-file prose can legitimately carry em/en dashes,
# arrows, ellipses and curly quotes for MEANING, not decoration -- a raw
# non-ASCII print risks either an un-encodable write crashing mid-flush,
# or a silent meaning-losing '?' drop. Anything outside this table still
# degrades via encode("ascii","replace") rather than crashing the write,
# but is reported with a loud per-file WARNING line (see layer_a_lines()
# below) rather than silently swallowed -- meaning loss must never be
# silent.
_LAYER_A_TRANSLIT = {
    "—": "--",  # em dash
    "–": "-",  # en dash
    "→": "->",  # right arrow
    "←": "<-",  # left arrow
    "…": "...",  # ellipsis
    "«": '"',  # left guillemet
    "»": '"',  # right guillemet
    "“": '"',  # left double quote
    "”": '"',  # right double quote
    "‘": "'",  # left single quote
    "’": "'",  # right single quote
    " ": " ",  # non-breaking space
    # t-641 verdict, F4: a host tree's own README.md carries a directory
    # tree diagram (box-drawing) and inline section references (section
    # sign) -- both load-bearing for MEANING, not decoration, same
    # rationale as the entries above. Windows `tree`-style ASCII
    # stand-ins for the box-drawing glyphs (widely recognized, not an
    # invented notation).
    "─": "-",  # box drawing light horizontal (tree line)
    "│": "|",  # box drawing light vertical (tree line)
    "├": "+",  # box drawing light vertical and right (tree branch)
    "└": "\\",  # box drawing light up and right (tree last branch)
    "§": "Sec.",  # section sign
}
_LAYER_A_TRANSLATE_TABLE = str.maketrans(_LAYER_A_TRANSLIT)

# Control characters stripped from layer-A content lines -- same ranges
# _ascii_sanitize already strips (\x00-\x1f\x7f) EXCEPT \t (boot files
# may use it inside code fences). \r/\n are never seen here -- the
# caller already splits on them via str.splitlines() before calling
# _ascii_content_line per line.
_LAYER_A_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _ascii_content_line(s: str) -> "tuple[str, int, int]":
    """Returns (ascii_safe_line, translit_count, unmapped_count) for ONE
    logical line of layer-A file content. A deliberately separate helper
    from _ascii_sanitize above -- that one truncates to 80 chars, unusable
    for a prose line that can legitimately run past 500 characters. Never
    truncates, never raises on its own (its caller, layer_a_lines(),
    still wraps everything in its own try/except regardless).

    translit_count is how many characters were rewritten via the
    meaning-preserving table above -- reported by the caller as a soft
    "[note: ...]" line when it is the ONLY thing that fired for a file.
    unmapped_count is how many remaining non-ASCII characters, AFTER the
    table, had no mapping and were replaced with '?' -- reported by the
    caller as a loud "[WARNING: ... MEANING MAY BE LOST]" line."""
    s = _LAYER_A_CONTROL_RE.sub("", s)
    translit_count = sum(1 for ch in s if ch in _LAYER_A_TRANSLIT)
    s = s.translate(_LAYER_A_TRANSLATE_TABLE)
    unmapped_count = sum(1 for ch in s if ord(ch) > 127)
    if unmapped_count:
        s = s.encode("ascii", "replace").decode("ascii")
    return s, translit_count, unmapped_count


def _layer_a_unavailable_line(exc: Exception) -> str:
    """Single degraded line used both by layer_a_lines()'s own
    try/except AND by main()'s second, outer defensive wrapper around
    its call -- factored out so both print the IDENTICAL text rather
    than risking two messages that drift apart. f"{exc}" calls
    exc.__str__() implicitly, which could itself raise for a
    pathological exception subclass -- wrapped in its own try with a
    CONSTANT fallback, not a second str(exc) attempt that could raise
    the exact same way again."""
    try:
        detail = _ascii_sanitize(f"{type(exc).__name__}: {exc}", 200)
    except Exception:
        detail = f"{type(exc).__name__}: <unprintable exception>"
    return (
        f"AUTO-BOOT: Layer A inline unavailable ({detail}) -- read the "
        "files listed in BOOT.md yourself."
    )


# Node E item 8: the "## Layer A" heading BOOT.md now carries -- start
# of the markup-aware slice. Matched at the start of a line, tolerant
# of an em/en-dash or plain "--"/":" trailer after "Layer A" (the exact
# heading text is BOOT.md's own prose, not pinned character-for-
# character here).
_LAYER_A_HEADING_RE = re.compile(r"^##\s*Layer\s+A\b", re.IGNORECASE | re.MULTILINE)
# Any NEXT "## "-level heading (Layer B or otherwise) closes the Layer
# A slice -- the parser does not need to recognize "Layer B" BY NAME,
# only that Layer A's own section has ended.
_NEXT_HEADING_RE = re.compile(r"^##\s", re.MULTILINE)


def layer_a_file_names(root: Path) -> list:
    """Kit's own layer-A file list. MARKUP-AWARE: parses
    ONLY the "Read X.md" lines that fall inside BOOT.md's own
    "## Layer A" section (from that heading up to the next "## "
    heading, or end of file if there is none) -- this EXCLUDES
    CURRENT_CONTEXT.md by construction, the kit's own state file, which
    BOOT.md's "## Layer B" section lists instead (the session reads
    Layer B itself, it is never injected here). FALLBACK, both worlds
    (R11(c)): a BOOT.md carrying no "## Layer A" heading at all (an
    older/unmarked form) falls back to the flat list of every
    "Read X.md" line in the WHOLE file (same regex boot_path_files()
    above uses for BUDGET arithmetic), MINUS CURRENT_CONTEXT.md by
    NAME -- the fallback still never injects the state file, it simply
    cannot rely on section markup that is not there. WITHOUT
    force-appending CLAUDE.md in either path: CLAUDE.md auto-loads
    separately via the harness's own mechanism and must not be
    double-printed as boot-file content here. Missing/unreadable
    BOOT.md, or a BOOT.md that lists no "Read X.md" lines at all
    (in-scope or in the fallback), both yield an empty list --
    layer_a_lines() below turns that into one honest line, never a
    traceback."""
    boot_md = Path(root) / "BOOT.md"
    try:
        text = boot_md.read_text(encoding="utf-8")
    except OSError:
        text = ""

    heading_match = _LAYER_A_HEADING_RE.search(text)
    if heading_match is not None:
        start = heading_match.end()
        next_heading = _NEXT_HEADING_RE.search(text, start)
        end = next_heading.start() if next_heading is not None else len(text)
        scope = text[start:end]
    else:
        # Fallback: no "## Layer A" markup at all -- the whole file,
        # minus the state file by name.
        scope = text

    names = []
    for m in re.finditer(r"Read ([A-Z_]+\.md)", scope):
        name = m.group(1)
        if name == _LAYER_A_EXCLUDED_STATE_FILE:
            continue
        if name not in names:
            names.append(name)
    return names


def layer_a_lines(root: Path) -> list:
    """The layer-A content block, printed verbatim (one list element per
    output line; no element embeds an internal '\\n'). NEVER raises --
    the whole body is wrapped in its own try/except: an unforeseen
    failure anywhere in this function degrades to ONE line
    (_layer_a_unavailable_line) instead of propagating to main()'s outer
    boundary, which would discard NOW/MODEL/BOOT BUDGET/etc for the sake
    of an unprinted boot file -- strictly worse than just losing this
    block. (main() ALSO wraps its own call to this function a second
    time, belt-and-suspenders, in case a future edit replaces this
    function wholesale and bypasses this try/except entirely.)

    An empty file list (BOOT.md missing/empty/lists nothing -- the "not
    yet onboarded" world) prints ONE honest line, not an empty or
    malformed block and never a traceback.

    The HEADER's byte total ("N bytes on disk") is measured from
    st_size (os.stat), matching boot_budget_lines()'s own choice above.
    The FOOTER's byte total ("N bytes emitted") is DELIBERATELY a
    different measurement: st_size counts bytes ON DISK, while "emitted"
    is accumulated per LINE (len(ascii_line) + 1 for the join separator)
    as each line is actually appended to this function's own return
    value -- the two are expected to diverge on content with CRLF line
    endings or transliterated characters; this is what makes the closing
    line a genuine per-emission count, not a disk-size tautology, and
    lets a truncated/interrupted emission be detected by the closing
    line's simple ABSENCE (see test_session_context_layer_a.py's
    negative-control test).

    Missing/unreadable individual files (absent, or any OSError
    including "path is actually a directory") degrade to a single
    per-file "[missing: ...]" line; the block still includes every OTHER
    file. A present-but-EMPTY (0-byte) file is NOT missing -- it gets an
    empty BEGIN/END pair, deliberately distinguished from "absent"."""
    try:
        root = Path(root)
        names = layer_a_file_names(root)
        if not names:
            return [
                "AUTO-BOOT: Layer A file list is empty (BOOT.md is missing, "
                "unreadable, or lists no boot files yet) -- nothing to inject."
            ]

        sizes = []
        for name in names:
            try:
                size = (root / name).stat().st_size
            except OSError:
                size = None
            sizes.append((name, size))

        total_on_disk = sum(size for _name, size in sizes if size is not None)

        # Node E item 8: the directive line comes FIRST, ahead of the
        # opening "--- BOOT LAYER A INJECTED ..." line itself -- only
        # printed when there is actual content about to follow (the
        # empty-list path above already returned before this point).
        block = [LAYER_A_DIRECTIVE_LINE]
        if total_on_disk > LAYER_A_INLINE_WARN_BYTES:
            block.append(
                f"AUTO-BOOT: Layer A is {total_on_disk} bytes, over the "
                f"{LAYER_A_INLINE_WARN_BYTES} byte notice threshold -- "
                "injected in full; every fresh session now pays these "
                "bytes of context, the threshold exists so growth is a "
                "decision, not drift -- tell the operator the boot-file "
                "set has grown."
            )
        block.append(
            f"--- BOOT LAYER A INJECTED -- {len(names)} files, "
            f"{total_on_disk} bytes on disk ---"
        )

        emitted_files = 0
        emitted_lines = 0
        emitted_bytes = 0
        summary_notes = []

        for name, size in sizes:
            if size is None:
                block.append(f"[missing: {name} -- not injected, read this one file yourself]")
                continue
            path = root / name
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                block.append(f"[missing: {name} -- not injected, read this one file yourself]")
                continue

            raw_lines = text.splitlines()
            block.append(f"----- BEGIN {name} ({size} bytes) -----")
            file_translit = 0
            file_unmapped = 0
            for raw_line in raw_lines:
                ascii_line, t_count, u_count = _ascii_content_line(raw_line)
                file_translit += t_count
                file_unmapped += u_count
                block.append(ascii_line)
                emitted_lines += 1
                emitted_bytes += len(ascii_line) + 1
            block.append(f"----- END {name} -----")

            emitted_files += 1
            if file_unmapped:
                summary_notes.append(
                    f"[WARNING: {file_unmapped} unmapped non-ASCII characters "
                    f"in {name} were replaced with '?' -- MEANING MAY BE LOST; "
                    "tell the operator]"
                )
            elif file_translit:
                summary_notes.append(
                    f"[note: {file_translit} non-ASCII characters transliterated "
                    "for the console -- source files are unmodified]"
                )

        block.extend(summary_notes)
        block.append(
            f"--- END BOOT LAYER A: {emitted_files} files, "
            f"{emitted_lines} lines, {emitted_bytes} bytes emitted ---"
        )
        return block
    except Exception as e:
        return [_layer_a_unavailable_line(e)]


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

    autofix_line = hooks_path_autofix_line(root)
    if autofix_line:
        lines.append(autofix_line)
    lines.append(wiring_summary_line(root))

    # F2 (release-gate v0.8.1): pass the ALREADY-BUILT lines so this call
    # can compute how much of the MAX_LINES budget is actually left and
    # ack ONLY the facts whose lines survive the [:MAX_LINES] cut below --
    # see select_and_ack_break_glass_lines()'s own docstring.
    lines.extend(select_and_ack_break_glass_lines(root, lines, now))

    return lines[:MAX_LINES]


def main(root: Path = None) -> int:
    """The ONE try/except boundary for the whole script (spec: NEVER
    crashes -> one line -> exit 0). Deliberately not per-section:
    a partially-built context (e.g. journal read fine, quota lookup
    half-crashed) is a worse failure mode than no context at all --
    a session trusting a half-populated 'reality' block is exactly the
    kind of silent gap this hook exists to prevent. So any error, from
    anywhere in reading stdin, build_context_lines() or the layer-A
    block, discards everything gathered so far and prints only the
    warning line.

    ALL lines (boot-lite context + layer A, when it fires) are joined
    into ONE string and handed to a SINGLE _write_stdout_deadline() call,
    not one print() per line -- this is what makes "discards everything
    gathered so far" literally true on a mid-build failure: a build-time
    exception now always discards the whole partial context (never a
    partial print), while the warning line itself stays visible (see the
    except block below), so a build failure with a healthy stdout is
    never silent, only context-less.

    The single write runs on a deadline (_write_stdout_deadline): True
    means the write actually completed, or raised an ORDINARY exception
    that this function re-raises here into the SAME try -- caught by the
    except below exactly like a bare sys.stdout.write() call used to be.
    False means a non-draining consumer left the write stuck inside the
    OS on a full pipe past the deadline: os._exit(0) below terminates
    IMMEDIATELY, with NO further I/O of any kind (see the helper's own
    docstring for why even a diagnostic write would hang the same way)
    -- rc 0, not 1: this hook did not "crash", it emitted as much as
    made it through before the deadline, and session start must proceed
    regardless.

    The warning path itself (except block) is attempted on STDOUT FIRST
    -- a session must see it in the same stream a healthy build would
    have used (a broken journal/quota/wiring read must still surface as
    a visible line, not vanish into a stream nobody reads); only when
    THAT write itself raises (a genuinely dead stdout, not merely a
    build-time exception) does the same message fall back to stderr,
    under its own nested try -- if BOTH channels are down, the warning
    is silently dropped and this still returns 0: a SessionStart hook
    must never itself crash the session, on either channel. The
    exception's str(e) is routed through this module's own
    _ascii_sanitize(text, 300) before being formatted into the warning,
    on EVERY channel attempt -- an unsanitized non-ASCII or multi-line
    message could break a narrow-codepage console or the one-line/
    no-injected-newline invariant this hook otherwise holds everywhere
    else."""
    try:
        resolved_root = Path(root) if root else repo_root()
        stdin_payload = read_stdin_payload()
        lines = build_context_lines(resolved_root, stdin_payload=stdin_payload)

        source = extract_source(stdin_payload)
        if should_emit_layer_a(source):
            # Wrapped a SECOND time here, on top of layer_a_lines()'s own
            # internal try/except -- so even a future edit replacing
            # layer_a_lines() wholesale, bypassing its own guard entirely,
            # still cannot blow past THIS boundary and discard
            # NOW/MODEL/BOOT BUDGET/etc for the sake of an unprinted
            # boot file.
            try:
                lines = lines + layer_a_lines(resolved_root)
            except Exception as _layer_a_exc:
                lines = lines + [_layer_a_unavailable_line(_layer_a_exc)]

        output = "\n".join(lines)
        if lines:
            output += "\n"
        if not _write_stdout_deadline(output):
            os._exit(0)
    except Exception as e:  # fail-open: this hook must never break session start
        try:
            safe_detail = _ascii_sanitize(str(e), 300)
        except Exception:
            safe_detail = f"{type(e).__name__}: <unprintable exception>"
        warning = f"session-context warning: {safe_detail}\n"
        try:
            sys.stdout.write(warning)
            sys.stdout.flush()
        except Exception:
            try:
                sys.stderr.write(warning)
                sys.stderr.flush()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    _rc = main()
    if _STDIN_DEADLINE_STATE["hit"]:
        # A stdin-reader thread may still be blocked deep inside a
        # platform read syscall -- normal interpreter shutdown can crash
        # on that ("Fatal Python error: _enter_buffered_busy"). Flush
        # both streams defensively, then exit immediately without
        # running the normal shutdown sequence.
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
