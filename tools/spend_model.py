"""tools/spend_model.py -- spend-monitoring CORE JOIN + derived tables
(B1, docs/tasks/2026-08-13_spend-analytics.md section 6, node B1).

WHAT THIS MODULE DOES (nothing more -- M1-M14/D1-D9 are node B2,
CLI/report/dashboard are B3/B6, the run_units.jsonl IMPORTER is B4):
  1. DEPLOYS config: (deploy_key, journal_path) for the three deploys
     on this machine, PLUS the empirically-established DEPLOY_PROJECT
     mapping deploy_key -> cc_usage.project (see "KEY-FORM PROBE"
     below for how this was verified, not assumed).
  2. Journal parsing -> STAGES (every journal.event == "delegated"
     line, O1). Reuses tools/calibration_counts.py wholesale for
     parsing/branch-classification/unparsable-candidates (given file,
     R9 reuse) instead of re-deriving that logic.
  3. JOIN stage -> cc_usage via agent_key = norm(worker_ref) (O1/E2).
  4. Derived tables task_stage_costs / task_costs / run_units (schema
     only, B4 fills rows) / window_series (schema only, B2 fills
     rows) in gateway/requests.db (Rule 0.2 -- no new storage). deploy
     is part of the PK of the first two (spec delta (з), E15).
  5. Two window KINDS: kind='calibrated' (per-deploy, O2) and
     kind='monthly' (shared across deploys, 14th-of-month boundary,
     same form as tools/token_usage_stats.py) -- see calibrated_windows()
     / compute_monthly_costs_independent().
  6. rebuild(conn, ...): DELETE+INSERT task_stage_costs/task_costs in
     one transaction; NEVER touches cc_usage or requests (E12). Caller
     is responsible for cc_usage already existing/being fresh (the
     LAZY IMPORT step, E11, is a separate call -- see run_selftest()).

KEY-FORM PROBE (accept key 1, empirically run as the FIRST move of
this task, before any code was written -- live gateway/requests.db,
2026-08-13): journal.worker_ref carries the form "agent:<id>";
cc_usage.agent_id carries the BARE id with NO "agent-" prefix (e.g.
worker_ref "agent:ad426657432db0805" <-> cc_usage.agent_id
"ad426657432db0805", both confirmed present with matching project for
t-416/417/418/419 after a lazy import -- cc_usage's cc_usage.ts had
been stale, max ts 2026-08-05, until the lazy import caught it up to
2026-08-13). A SINGLE normalization ("strip 'agent:' from the journal
side") is sufficient -- verified on real aggregate numbers: shtab
378/391 agent:-form worker_refs found >=1 cc_usage row (13 not found
-- dead/unfinished dispatches with no transcript, not a form
mismatch), ao3 286/327 found (41 not found, same class), dog 0/0 (its
journal never populates worker_ref at all -- see DEPLOY note below).
The spec's proposed SECOND normalization ("also strip 'agent-' from
cc_usage.agent_id") was never needed and is deliberately NOT coded --
inventing a fallback that empirically never fires is exactly the
"third normalization" the spec forbids inventing.

DEPLOY note (dog): D:\\Dog\\logs\\routing-log.jsonl's delegated events
NEVER carry a worker_ref field at all (26/26 delegated checked, all
None) -- not cli:/retro: (E9's named forms) but simply absent. Treated
identically to E9 (measurable=0, no crash) since None is "not an
agent:<id> form" trivially -- no new edge class needed. dog's own
journal DOES have 3 calibrated events (unlike ao3, which currently has
ZERO -- O2's "6 calibrated windows" is a shtab-specific empirical fact
from the spec, not a cross-deploy assumption; ao3 legitimately gets 0
calibrated windows today, tested as a real case not synthesized).

PRECONDITION on rebuild()/anything reading cc_usage: the caller
ensures the cc_usage table already exists (via a prior
usage_report.import_transcripts()/_connect() call, or in tests via
`conn.execute(usage_report.SCHEMA)`, mirroring
tools/test_token_usage_stats.py's `_make_db` fixture pattern). rebuild()
itself never creates/touches cc_usage (Rule 0.2 / E12) -- it CREATEs
(IF NOT EXISTS) only its OWN four tables.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import calibration_counts as cc_counts  # noqa: E402
import token_usage_stats as tus  # noqa: E402
from savings_report import fable_counterfactual  # noqa: E402
from usage_report import (  # noqa: E402
    accounted_cost,
    db_path as _cc_db_path,
    import_transcripts,
    transcript_glob,
)

try:  # Windows narrow-codepage consoles (command hygiene p.9)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------
# 1. DEPLOYS config + empirical deploy -> cc_usage.project mapping
#    (spec delta (з) point 1; probed via `SELECT DISTINCT project FROM
#    cc_usage`, see _slug_mapping_report()/accept key 2).
# --------------------------------------------------------------------
DEPLOYS = [
    ("shtab", str(REPO_ROOT / "logs" / "routing-log.jsonl")),
    ("ao3", r"D:\AO3_tests\logs\routing-log.jsonl"),
    ("dog", r"D:\Dog\logs\routing-log.jsonl"),
]

DEPLOY_PROJECT = {
    "shtab": "D--Improving-AI-Operating-System-for-LLMs",
    "ao3": "D--AO3-tests",
    "dog": "D--Dog",
}


# --------------------------------------------------------------------
# 2. Schema (section 3 + delta (з): deploy in PK of the first two,
#    scope column on window_series).
# --------------------------------------------------------------------
SCHEMA_TASK_STAGE_COSTS = """
CREATE TABLE IF NOT EXISTS task_stage_costs (
    deploy TEXT NOT NULL,
    task_id TEXT NOT NULL,
    stage_index INTEGER NOT NULL,
    journal_line INTEGER,
    ts_local TEXT,
    agent TEXT,
    model_declared TEXT,
    worker_ref TEXT,
    agent_key TEXT,
    project TEXT,
    turns INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    unpriced_turns INTEGER NOT NULL DEFAULT 0,
    models_measured TEXT,
    stage_kind TEXT,
    measurable INTEGER NOT NULL DEFAULT 0,
    is_rework INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (deploy, task_id, stage_index)
);
"""
# is_rework (B2 addition, O1's "delegated ПОСЛЕ первого rejected,
# replaces_worker НЕ реворк"): the SAME per-task classification
# _build_task_row already computed to produce task_costs.rework_stages
# (B1), now also recorded PER STAGE so M3 (cost of rework, not just its
# COUNT) can be computed by a plain SQL filter instead of re-deriving
# the journal-line comparison at every metrics run. Single source of
# truth: stages_and_tasks_for_deploy computes first_rejected_line ONCE
# per task and threads it into both this per-stage flag and
# _build_task_row's rework_stages count (see that function -- it now
# just sums this flag, no longer recomputes the comparison itself).

SCHEMA_TASK_COSTS = """
CREATE TABLE IF NOT EXISTS task_costs (
    deploy TEXT NOT NULL,
    task_id TEXT NOT NULL,
    first_delegated_ts TEXT,
    last_event_ts TEXT,
    window_id TEXT,
    category TEXT,
    stages INTEGER NOT NULL DEFAULT 0,
    rework_stages INTEGER NOT NULL DEFAULT 0,
    critic_entries INTEGER NOT NULL DEFAULT 0,
    rejected_count INTEGER NOT NULL DEFAULT 0,
    escalated_count INTEGER NOT NULL DEFAULT 0,
    accepted INTEGER NOT NULL DEFAULT 0,
    open_at_window_end INTEGER NOT NULL DEFAULT 0,
    self_exec INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL,
    unpriced_turns INTEGER NOT NULL DEFAULT 0,
    turns INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (deploy, task_id)
);
"""

# B4's table (E7: created by the first rebuild, no rows until B4/a
# skill run writes them -- legal per the spec's own carve-out).
SCHEMA_RUN_UNITS = """
CREATE TABLE IF NOT EXISTS run_units (
    run_id TEXT NOT NULL,
    run_kind TEXT,
    name TEXT,
    phase TEXT,
    ts_start TEXT,
    ts_end TEXT,
    session_id TEXT,
    unit_kind TEXT,
    unit_count INTEGER,
    source TEXT,
    PRIMARY KEY (run_id, phase)
);
"""

# B2's table (schema only here; metric rows are B2's job). scope
# (deploy | all) added by spec delta (з) point 3: a calibrated window
# is inherently deploy-scoped (its window_id is already deploy-
# prefixed, see calibrated_windows()); a monthly window can be
# computed either per-deploy (window_id "<deploy>:monthly:<label>",
# scope='deploy') or aggregated across all three (window_id
# "all:monthly:<label>", scope='all') -- window_id alone already
# disambiguates, `scope` is a queryable tag on top, not a second PK
# component.
SCHEMA_WINDOW_SERIES = """
CREATE TABLE IF NOT EXISTS window_series (
    window_id TEXT NOT NULL,
    window_start TEXT,
    window_end TEXT,
    partial INTEGER NOT NULL DEFAULT 0,
    scope TEXT NOT NULL DEFAULT 'deploy',
    metric_key TEXT NOT NULL,
    value REAL,
    denominator_kind TEXT,
    denominator_value REAL,
    unpriced_turns INTEGER,
    reason TEXT,
    computed_at TEXT,
    PRIMARY KEY (window_id, metric_key)
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    for ddl in (SCHEMA_TASK_STAGE_COSTS, SCHEMA_TASK_COSTS, SCHEMA_RUN_UNITS, SCHEMA_WINDOW_SERIES):
        conn.execute(ddl)
    # B2 migration: `CREATE TABLE IF NOT EXISTS` is a no-op on a table B1
    # already created live (this repo's own gateway/requests.db, canon
    # 2532 per t-420's accepted report) -- is_rework did not exist there.
    # ALTER TABLE ADD COLUMN with a NOT NULL DEFAULT backfills existing
    # rows legally in SQLite; guarded by PRAGMA table_info so a fresh
    # (test) DB that already has the column via SCHEMA_TASK_STAGE_COSTS
    # above is a no-op, never a duplicate-column error.
    existing_cols = {r[1] for r in conn.execute("PRAGMA table_info(task_stage_costs)")}
    if "is_rework" not in existing_cols:
        conn.execute("ALTER TABLE task_stage_costs ADD COLUMN is_rework INTEGER NOT NULL DEFAULT 0")
    conn.commit()


_STAGE_COLUMNS = [
    "deploy", "task_id", "stage_index", "journal_line", "ts_local", "agent",
    "model_declared", "worker_ref", "agent_key", "project", "turns",
    "input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens",
    "cost_usd", "unpriced_turns", "models_measured", "stage_kind", "measurable",
    "is_rework",
]
_INSERT_STAGE_SQL = (
    "INSERT INTO task_stage_costs (" + ", ".join(_STAGE_COLUMNS) + ") VALUES ("
    + ", ".join("?" for _ in _STAGE_COLUMNS) + ")"
)

_TASK_COLUMNS = [
    "deploy", "task_id", "first_delegated_ts", "last_event_ts", "window_id",
    "category", "stages", "rework_stages", "critic_entries", "rejected_count",
    "escalated_count", "accepted", "open_at_window_end", "self_exec",
    "cost_usd", "unpriced_turns", "turns",
]
_INSERT_TASK_SQL = (
    "INSERT INTO task_costs (" + ", ".join(_TASK_COLUMNS) + ") VALUES ("
    + ", ".join("?" for _ in _TASK_COLUMNS) + ")"
)


def _stage_to_tuple(s: dict) -> tuple:
    return tuple(s.get(c) for c in _STAGE_COLUMNS)


def _task_to_tuple(t: dict) -> tuple:
    return tuple(t.get(c) for c in _TASK_COLUMNS)


# --------------------------------------------------------------------
# 3. Clock normalization (E1 / SIBLING_MAP axis 2 ts-clock subclass) --
#    a dedicated, separately-tested function, per section 9's
#    "образец _normalize_ts_to_local_naive из карты" convention.
# --------------------------------------------------------------------
def normalize_cc_ts_to_local_naive(ts):
    """cc_usage.ts (UTC with 'Z', e.g. '2026-08-13T16:33:02.275Z') ->
    LOCAL NAIVE datetime, the same clock journal.ts values are already
    written in (E1, ~2h gap on this machine). Mirrors
    token_usage_stats.parse_ts_local's conversion
    (.replace('Z','+00:00').astimezone()) but additionally drops
    tzinfo so the result is directly comparable to a journal ts parsed
    via datetime.fromisoformat() (always naive, never carries tzinfo).
    Returns None for an absent/unparsable ts -- never raises (E1 is a
    join-precision concern, not a crash surface)."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone().replace(tzinfo=None)


def _monthly_bounds(wy: int, wm: int):
    """(start, end) of the [14.wm.wy, 14.wm+1.wy) window as NAIVE
    datetimes -- same math as token_usage_stats.window_end_dt but
    without the tz-aware wrapping (this module compares against
    already-local-naive values)."""
    ey, em = (wy + 1, 1) if wm == 12 else (wy, wm + 1)
    return datetime(wy, wm, tus.ANCHOR_DAY), datetime(ey, em, tus.ANCHOR_DAY)


# --------------------------------------------------------------------
# 4. Windows -- two kinds (spec delta (з) point 4).
# --------------------------------------------------------------------
def calibrated_windows(deploy: str, calibrated_tss: list) -> list:
    """O2: window = interval between adjacent journal.event=="calibrated"
    lines of THIS deploy's own journal, boundaries from `ts` (notes NOT
    parsed). n calibrated events -> n windows: window i = [ts[i-1] or
    -inf, ts[i]) for i=1..n (a virtual "calibrated event 0" at -inf),
    so window 1 is the partial leftover before calibration began
    (partial=1, per the spec's accept key 5 wording "6 calibrated-окон,
    первое partial=1" -- 6 windows for 6 calibrated EVENTS, not 5
    gaps). calibrated_tss must already be sorted ascending. A deploy
    with 0 calibrated events (ao3, live, 2026-08-13) legitimately
    returns []; not an error (O2 makes no cross-deploy count promise)."""
    windows = []
    prev_end = None
    for i, ts in enumerate(calibrated_tss, start=1):
        windows.append({
            "window_id": f"{deploy}:calibrated:{i}",
            "window_start": prev_end,
            "window_end": ts,
            "partial": 1 if i == 1 else 0,
        })
        prev_end = ts
    return windows


def _window_for_ts(windows: list, ts):
    """First window w with (w.start is None or ts >= w.start) and
    ts < w.end -- half-open [start, end) intervals, matching
    token_usage_stats' own >=start/<end convention. ts >= the LAST
    window's end (not yet closed by a calibration) or ts is None ->
    None (no window yet -- a real, expected state for in-flight
    work)."""
    if ts is None:
        return None
    for w in windows:
        start_ok = (w["window_start"] is None) or (ts >= w["window_start"])
        if start_ok and ts < w["window_end"]:
            return w
    return None


# --------------------------------------------------------------------
# 5. Journal -> stage key normalization (O1/E2/E9).
# --------------------------------------------------------------------
def norm_worker_ref(worker_ref):
    """O1's norm(x): strip the 'agent:' prefix from journal.worker_ref.
    Returns None for anything not in that exact form (missing, cli:,
    retro:, replaces_worker-only markers, etc. -- E9's class, plus
    dog's plain-absent worker_ref) -- caller sets measurable=0 for
    those, never a KeyError/crash. See module docstring "KEY-FORM
    PROBE" for why no second normalization is implemented."""
    if not isinstance(worker_ref, str) or not worker_ref.startswith("agent:"):
        return None
    key = worker_ref[len("agent:"):]
    return key or None


_TIER_FAMILIES = ("haiku", "sonnet", "opus", "fable")


def normalize_tier_family(model_declared) -> tuple:
    """model_declared -> (family, reason) for M10/D4 grouping (B3 point-
    fix, finding 8в.1: journal model_declared drifts across near-
    synonyms of the SAME tier -- fable / fable-5 / claude-fable-5 --
    fragmenting M10/D4 into several window_series rows for what is one
    tier). SUBSTRING match (case-insensitive) against the four
    CLAUDE.md tier words (haiku/sonnet/opus/fable): "fable-5" and
    "claude-fable-5" both contain "fable" and collapse to it. A string
    matching NONE of the four (e.g. "gpt-5", a real future case per
    spec section 8а's GPT-portability note) is returned RAW and
    UNCHANGED -- never silently remapped, never dropped (spec's own
    "не теряется и не мапится молча"). An empty/None model_declared
    buckets into the literal string "unknown" with a reason (spec's
    own wording, point 2) -- note _m10 below already filters falsy
    model_declared out BEFORE grouping (pre-existing behaviour, out of
    this point-fix's scope), so this branch is never actually reached
    from _m10 on live data; it exists so the function's OWN contract is
    TOTAL (every input has a defined output), independently verified by
    its own boundary tests rather than relying on a caller's
    pre-filtering to avoid it."""
    if not model_declared:
        return "unknown", "н/д (модель не указана)"
    s = model_declared.lower()
    for fam in _TIER_FAMILIES:
        if fam in s:
            return fam, None
    return model_declared, None


_STAGE_KIND_COLLAPSE = {
    "critic-вход": "critic",
    "retry": "retry",
    "replacement": "replacement",
    # calibration_counts' remaining branches (кандидат-дубль,
    # continuation, replacement-фиктивный, other) are anomalous/
    # ambiguous repeats -- the schema's stage_kind enum has exactly
    # 5 values (first|retry|critic|replacement|other), so they all
    # collapse to "other" (a candidate for the health section, not a
    # crash).
}


def _stage_kind(branch):
    if branch is None:
        return "first"
    return _STAGE_KIND_COLLAPSE.get(branch, "other")


# --------------------------------------------------------------------
# 6. cc_usage join (agent_id x project -> turns/tokens/cost).
# --------------------------------------------------------------------
def _agent_stats_for_project(conn: sqlite3.Connection, project: str) -> dict:
    """agent_id -> {turns, 4 token sums, cost_usd, unpriced_turns,
    models_measured} for one project, ONE query (not one per stage).
    cost_usd is None when NOT EVEN ONE matched row is priced (E6/section
    3's exact "NULL если ни одной ценённой строки" -- computed here,
    not via a raw SQL SUM that would silently fold all-NULL into 0)."""
    if not project:
        return {}
    rows = conn.execute(
        """
        SELECT agent_id, COUNT(*),
               SUM(input_tokens), SUM(output_tokens),
               SUM(cache_creation_tokens), SUM(cache_read_tokens),
               SUM(CASE WHEN accounted_cost_usd IS NOT NULL THEN accounted_cost_usd ELSE 0 END),
               SUM(CASE WHEN accounted_cost_usd IS NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN accounted_cost_usd IS NOT NULL THEN 1 ELSE 0 END),
               GROUP_CONCAT(DISTINCT model)
        FROM cc_usage WHERE project = ? AND agent_id IS NOT NULL
        GROUP BY agent_id
        """,
        (project,),
    ).fetchall()
    stats = {}
    for (agent_id, turns, inp, out, cw, cr, priced_sum, unpriced_turns,
         priced_turns, models) in rows:
        cost_usd = priced_sum if priced_turns else None
        models_measured = ",".join(sorted(set((models or "").split(",")))) if models else None
        stats[agent_id] = {
            "turns": turns, "input_tokens": inp or 0, "output_tokens": out or 0,
            "cache_creation_tokens": cw or 0, "cache_read_tokens": cr or 0,
            "cost_usd": cost_usd, "unpriced_turns": unpriced_turns,
            "models_measured": models_measured,
        }
    return stats


def _orphan_sidechain_bucket(conn: sqlite3.Connection, project: str, matched_keys: set):
    """E5: sidechain (subagent) cc_usage traffic whose agent_id is NEVER
    referenced by any journal delegated worker_ref of this deploy
    (interactive Task dispatches, e.g.) -> one aggregated bucket.
    Returns None when there are zero such rows (no placeholder row is
    inserted when the bucket is empty)."""
    if not project:
        return None
    rows = conn.execute(
        """
        SELECT agent_id, COUNT(*),
               SUM(CASE WHEN accounted_cost_usd IS NOT NULL THEN accounted_cost_usd ELSE 0 END),
               SUM(CASE WHEN accounted_cost_usd IS NULL THEN 1 ELSE 0 END),
               SUM(CASE WHEN accounted_cost_usd IS NOT NULL THEN 1 ELSE 0 END)
        FROM cc_usage WHERE project = ? AND is_sidechain = 1 AND agent_id IS NOT NULL
        GROUP BY agent_id
        """,
        (project,),
    ).fetchall()
    total_turns = 0
    total_cost = 0.0
    total_unpriced = 0
    has_priced = False
    for agent_id, turns, priced_sum, unpriced_turns, priced_turns in rows:
        if agent_id in matched_keys:
            continue
        total_turns += turns
        total_unpriced += unpriced_turns
        if priced_turns:
            has_priced = True
            total_cost += priced_sum
    if total_turns == 0:
        return None
    return {
        "first_delegated_ts": None, "last_event_ts": None, "window_id": None,
        "category": None, "stages": 0, "rework_stages": 0, "critic_entries": 0,
        "rejected_count": 0, "escalated_count": 0, "accepted": 0,
        "open_at_window_end": 0, "self_exec": 0,
        "cost_usd": total_cost if has_priced else None,
        "unpriced_turns": total_unpriced, "turns": total_turns,
    }


# --------------------------------------------------------------------
# 7. Stage/task row construction for one deploy.
# --------------------------------------------------------------------
def _build_task_row(deploy: str, task_id: str, stages: list, task_events: list, windows: list) -> dict:
    stages_sorted = sorted(stages, key=lambda s: s["stage_index"])
    first_ts_dt = stages_sorted[0]["ts_dt"] if stages_sorted else None
    first_ts_str = stages_sorted[0]["ts_local"] if stages_sorted else None
    all_ts = [pl.ts for pl in task_events if pl.ts is not None]
    last_ts_dt = max(all_ts) if all_ts else None
    last_ts_str = last_ts_dt.isoformat() if last_ts_dt else None

    category = None
    for pl in task_events:
        if pl.data.get("event") == "delegated":
            category = pl.data.get("category")
            break

    rejected_lines = [pl.line_no for pl in task_events if pl.data.get("event") == "rejected"]
    escalated_count = sum(1 for pl in task_events if pl.data.get("event") == "escalated")
    accepted = 1 if any(pl.data.get("event") == "accepted" for pl in task_events) else 0
    critic_entries = sum(1 for s in stages_sorted if s["agent"] == "critic")

    # Q1 rework_stages: delegated stages positioned after the task's
    # FIRST rejected, EXCLUDING replaces_worker legitimate replacements
    # (O1: "replaces_worker НЕ реворк"). B2 now computes the underlying
    # journal_line > first_rejected_line comparison ONCE, in
    # stages_and_tasks_for_deploy, and stamps it on each stage as
    # is_rework (single source of truth for both this COUNT and M3's
    # cost-of-rework SUM) -- this is just the sum of that flag.
    rework_stages = sum(1 for s in stages_sorted if s.get("is_rework"))

    win = _window_for_ts(windows, first_ts_dt) if first_ts_dt else None
    window_id = win["window_id"] if win else None
    # E8: task straddles a calibration boundary -- last activity ts
    # falls at/after the window's own end.
    open_at_window_end = 1 if (win is not None and last_ts_dt is not None
                                and last_ts_dt >= win["window_end"]) else 0

    measurable_stages = [s for s in stages_sorted if s["measurable"]]
    self_exec = 1 if not measurable_stages else 0  # E4
    turns = sum(s["turns"] for s in stages_sorted)
    priced = [s["cost_usd"] for s in stages_sorted if s["cost_usd"] is not None]
    cost_usd = sum(priced) if priced else None
    unpriced_turns = sum(s["unpriced_turns"] for s in stages_sorted)

    return {
        "deploy": deploy, "task_id": task_id,
        "first_delegated_ts": first_ts_str, "last_event_ts": last_ts_str,
        "window_id": window_id, "category": category,
        "stages": len(stages_sorted), "rework_stages": rework_stages,
        "critic_entries": critic_entries, "rejected_count": len(rejected_lines),
        "escalated_count": escalated_count, "accepted": accepted,
        "open_at_window_end": open_at_window_end, "self_exec": self_exec,
        "cost_usd": cost_usd, "unpriced_turns": unpriced_turns, "turns": turns,
    }


def stages_and_tasks_for_deploy(conn: sqlite3.Connection, deploy_key: str,
                                 journal_path: str, project: str):
    """Returns (stage_rows, task_rows, spend_only_reason). spend_only_reason
    is None normally; a string (E14) when the journal is absent/unreadable
    -- caller then simply omits this deploy's stage/task rows (the
    project's cc_usage rows still exist and are queryable elsewhere,
    "spend-only" mode), never a crash."""
    try:
        lines = cc_counts.load_journal(journal_path)
    except OSError as exc:
        return [], [], f"без журнала ({exc}) -- spend-only режим"

    analysis = cc_counts.analyze_journal(
        journal_path, None, None, cc_counts.parse_ts(cc_counts.DEFAULT_BY_SINCE)
    )
    branch_by_line = {d["line"]: d["branch"] for d in analysis["duplicate_delegates"]}

    events_by_task = defaultdict(list)
    delegated_by_task = defaultdict(list)
    calibrated_tss = []
    for pl in lines:
        if pl.data is None:
            continue
        ev = pl.data.get("event")
        if ev == "calibrated" and pl.ts is not None:
            calibrated_tss.append(pl.ts)
        tid = pl.data.get("task_id")
        if isinstance(tid, str) and tid:
            events_by_task[tid].append(pl)
            if ev == "delegated":
                delegated_by_task[tid].append(pl)
    calibrated_tss.sort()
    windows = calibrated_windows(deploy_key, calibrated_tss)

    agent_stats = _agent_stats_for_project(conn, project)

    stage_rows = []
    task_rows = []
    matched_agent_keys = set()

    for tid, pls in delegated_by_task.items():
        pls_sorted = sorted(pls, key=lambda pl: (pl.ts or datetime.min, pl.line_no))
        # O1/is_rework (B2): first_rejected_line computed ONCE per task,
        # from this task's own events -- the single source _build_task_row
        # now reads back via the summed is_rework flag below.
        rejected_lines_tid = [
            e.line_no for e in events_by_task[tid] if e.data.get("event") == "rejected"
        ]
        first_rejected_line = min(rejected_lines_tid) if rejected_lines_tid else None
        stages = []
        for idx, pl in enumerate(pls_sorted, start=1):
            branch = branch_by_line.get(pl.line_no)
            stage_kind = _stage_kind(branch)
            worker_ref = pl.data.get("worker_ref")
            agent_key = norm_worker_ref(worker_ref)
            measurable = 1 if agent_key is not None else 0
            stat = agent_stats.get(agent_key) if agent_key else None
            if agent_key:
                matched_agent_keys.add(agent_key)
            is_rework = 1 if (first_rejected_line is not None
                               and pl.line_no > first_rejected_line
                               and stage_kind != "replacement") else 0
            stage = {
                "deploy": deploy_key, "task_id": tid, "stage_index": idx,
                "journal_line": pl.line_no,
                "ts_local": pl.data.get("ts"), "ts_dt": pl.ts,
                "agent": pl.data.get("agent"), "model_declared": pl.data.get("model"),
                "worker_ref": worker_ref, "agent_key": agent_key, "project": project,
                "turns": stat["turns"] if stat else 0,
                "input_tokens": stat["input_tokens"] if stat else 0,
                "output_tokens": stat["output_tokens"] if stat else 0,
                "cache_creation_tokens": stat["cache_creation_tokens"] if stat else 0,
                "cache_read_tokens": stat["cache_read_tokens"] if stat else 0,
                "cost_usd": stat["cost_usd"] if stat else None,
                "unpriced_turns": stat["unpriced_turns"] if stat else 0,
                "models_measured": stat["models_measured"] if stat else None,
                "stage_kind": stage_kind, "measurable": measurable,
                "is_rework": is_rework,
            }
            stages.append(stage)
            stage_rows.append(stage)

        task_rows.append(_build_task_row(deploy_key, tid, stages, events_by_task[tid], windows))

    orphan = _orphan_sidechain_bucket(conn, project, matched_agent_keys)
    if orphan is not None:
        task_rows.append({**orphan, "deploy": deploy_key, "task_id": "<unattributed>"})

    return stage_rows, task_rows, None


# --------------------------------------------------------------------
# 8. rebuild -- DELETE+INSERT one transaction, own tables only (E12).
# --------------------------------------------------------------------
def rebuild(conn: sqlite3.Connection, deploys=None, deploy_project=None) -> dict:
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    _ensure_schema(conn)

    all_stage_rows = []
    all_task_rows = []
    spend_only = []
    for deploy_key, journal_path in deploys:
        project = deploy_project.get(deploy_key)
        stage_rows, task_rows, reason = stages_and_tasks_for_deploy(
            conn, deploy_key, journal_path, project
        )
        if reason:
            spend_only.append({"deploy": deploy_key, "reason": reason})
            continue
        all_stage_rows.extend(stage_rows)
        all_task_rows.extend(task_rows)

    try:
        conn.execute("DELETE FROM task_stage_costs")
        conn.execute("DELETE FROM task_costs")
        conn.executemany(_INSERT_STAGE_SQL, [_stage_to_tuple(s) for s in all_stage_rows])
        conn.executemany(_INSERT_TASK_SQL, [_task_to_tuple(t) for t in all_task_rows])
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()

    return {"stage_rows": len(all_stage_rows), "task_rows": len(all_task_rows), "spend_only": spend_only}


def _dump_derived_tables(conn: sqlite3.Connection) -> str:
    """Canonical byte-for-byte-comparable text dump of the two tables
    rebuild() actually populates, ORDER BY their own PK (accept key 3)."""
    parts = []
    for table, order in (("task_stage_costs", "deploy, task_id, stage_index"),
                          ("task_costs", "deploy, task_id")):
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY {order}").fetchall()
        parts.append(f"-- {table} ({len(rows)} rows) --")
        parts.extend(repr(r) for r in rows)
    return "\n".join(parts)


def cc_usage_invariant(conn: sqlite3.Connection) -> dict:
    """E12's guard witness: COUNT(*) / SUM(COALESCE(accounted_cost_usd,0))
    of cc_usage -- compare before/after rebuild()."""
    row = conn.execute(
        "SELECT COUNT(*), SUM(COALESCE(accounted_cost_usd, 0)) FROM cc_usage"
    ).fetchone()
    return {"count": row[0], "sum": row[1]}


# --------------------------------------------------------------------
# 9. Key-form probe (accept key 1) + slug mapping (accept key 2).
# --------------------------------------------------------------------
def probe_key_form(conn: sqlite3.Connection, deploys=None, deploy_project=None) -> dict:
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    result = {}
    for deploy_key, journal_path in deploys:
        project = deploy_project.get(deploy_key)
        try:
            lines = cc_counts.load_journal(journal_path)
        except OSError as exc:
            result[deploy_key] = {"error": f"без журнала ({exc})"}
            continue
        agent_stats = _agent_stats_for_project(conn, project)
        total_delegated = agent_form = found = notfound = 0
        for pl in lines:
            if pl.data is None or pl.data.get("event") != "delegated":
                continue
            total_delegated += 1
            key = norm_worker_ref(pl.data.get("worker_ref"))
            if key is None:
                continue
            agent_form += 1
            if key in agent_stats:
                found += 1
            else:
                notfound += 1
        result[deploy_key] = {
            "project": project, "total_delegated": total_delegated,
            "agent_form": agent_form, "found": found, "notfound": notfound,
        }
    return result


def project_has_rows(conn: sqlite3.Connection, project: str) -> bool:
    if not project:
        return False
    return conn.execute(
        "SELECT COUNT(*) FROM cc_usage WHERE project = ?", (project,)
    ).fetchone()[0] > 0


def print_distinct_projects(conn: sqlite3.Connection) -> list:
    rows = [r[0] for r in conn.execute(
        "SELECT DISTINCT project FROM cc_usage ORDER BY project"
    ).fetchall()]
    print("SELECT DISTINCT project FROM cc_usage:")
    for p in rows:
        print(f"  {p}")
    return rows


def resolve_project_or_refuse(conn: sqlite3.Connection, project: str) -> bool:
    """E10: mandatory project filter. True when `project` has >=1 row in
    cc_usage; on 0 rows, prints SELECT DISTINCT project (never a silent
    empty report) and returns False -- caller exits 2."""
    if project_has_rows(conn, project):
        return True
    print(f"spend_model: 0 строк в cc_usage для project={project!r} -- отказ (E10)",
          file=sys.stderr)
    print_distinct_projects(conn)
    return False


def _slug_mapping_report(conn: sqlite3.Connection, deploys=None, deploy_project=None) -> dict:
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    distinct = print_distinct_projects_silent(conn)
    mapping = {}
    for deploy_key, _path in deploys:
        project = deploy_project.get(deploy_key)
        if project in distinct and project_has_rows(conn, project):
            mapping[deploy_key] = {"project": project, "status": "OK"}
        else:
            mapping[deploy_key] = {"project": project, "status": "проект без трат в БД"}
    return {"distinct_projects_count": len(distinct), "mapping": mapping}


def print_distinct_projects_silent(conn: sqlite3.Connection) -> list:
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT project FROM cc_usage ORDER BY project"
    ).fetchall()]


# --------------------------------------------------------------------
# 10. Monthly-window convergence with token_usage_stats (accept key 7,
#     spec delta (з) point 5) -- an INDEPENDENT reimplementation (shares
#     only the price table/formula and window-boundary math), compared
#     against token_usage_stats.aggregate()+_sum_group(), never
#     self-certifying.
# --------------------------------------------------------------------
def compute_monthly_costs_independent(conn: sqlite3.Connection, project: str) -> dict:
    rows = conn.execute(
        "SELECT ts, model, input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens"
        " FROM cc_usage WHERE project = ?", (project,)
    ).fetchall()
    per_window_model = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    for ts, model, inp, out, cw, cr in rows:
        local_dt = normalize_cc_ts_to_local_naive(ts)
        if local_dt is None or not model:
            continue
        wkey = tus.window_of(local_dt)
        acc = per_window_model[wkey][model]
        acc[0] += inp or 0
        acc[1] += out or 0
        acc[2] += cw or 0
        acc[3] += cr or 0
    result = {}
    for wkey, models in per_window_model.items():
        cost = 0.0
        unpriced = []
        for model, (inp, out, cw, cr) in models.items():
            c, _w = accounted_cost(model, inp, out, cw, cr)
            if c is None:
                unpriced.append(model)
            else:
                cost += c
        result[wkey] = {"cost": cost, "unpriced": unpriced}
    return result


def convergence_check(conn: sqlite3.Connection, project: str, now=None) -> list:
    """Completed (window end <= now), fully-priced monthly windows only
    -- own cost vs. token_usage_stats' own cost, side by side."""
    now = now or datetime.now()
    own = compute_monthly_costs_independent(conn, project)
    by_family, by_project, _period_sessions = tus.aggregate(conn)
    out = []
    for wkey in sorted(own):
        wy, wm = wkey
        _start, end = _monthly_bounds(wy, wm)
        if end > now:
            continue
        data = own[wkey]
        if data["unpriced"]:
            continue
        official_group = by_project.get(wkey, {}).get(project)
        if official_group is None:
            continue
        _s, official_cost, official_unpriced = tus._sum_group(official_group)
        if official_unpriced:
            continue
        out.append({
            "window": tus.window_label(wy, wm),
            "own_cost": round(data["cost"], 6),
            "official_cost": round(official_cost, 6),
            "match": abs(data["cost"] - official_cost) < 1e-6,
        })
    return out


# --------------------------------------------------------------------
# 11. selftest orchestration (E11 timing, all accept keys wired).
# --------------------------------------------------------------------
def run_selftest(db_file: Path, deploys=None, deploy_project=None, skip_import: bool = False) -> dict:
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    report = {}

    t0 = time.time()
    if skip_import:
        rows_imported, sessions, warnings = 0, set(), []
    else:
        rows_imported, sessions, warnings = import_transcripts(transcript_glob(), db_file)
    elapsed = time.time() - t0
    report["import"] = {
        "elapsed_sec": round(elapsed, 3), "rows_imported": rows_imported,
        "sessions": len(sessions), "warnings": warnings, "over_60s": elapsed > 60,
    }

    conn = sqlite3.connect(db_file)
    try:
        report["key_probe"] = probe_key_form(conn, deploys, deploy_project)
        report["slug_mapping"] = _slug_mapping_report(conn, deploys, deploy_project)

        before = cc_usage_invariant(conn)
        rebuild(conn, deploys, deploy_project)
        dump1 = _dump_derived_tables(conn)
        stats2 = rebuild(conn, deploys, deploy_project)
        dump2 = _dump_derived_tables(conn)
        after = cc_usage_invariant(conn)

        report["rebuild"] = {
            "idempotent": dump1 == dump2,
            "stage_rows": stats2["stage_rows"], "task_rows": stats2["task_rows"],
            "spend_only": stats2["spend_only"],
        }
        report["cc_usage_invariant"] = {"before": before, "after": after, "match": before == after}

        windows_report = {}
        for deploy_key, journal_path in deploys:
            try:
                lines = cc_counts.load_journal(journal_path)
            except OSError as exc:
                windows_report[deploy_key] = {"error": str(exc)}
                continue
            cal_tss = sorted(pl.ts for pl in lines
                              if pl.data and pl.data.get("event") == "calibrated" and pl.ts)
            windows = calibrated_windows(deploy_key, cal_tss)
            windows_report[deploy_key] = {
                "calibrated_count": len(windows),
                "first_partial": windows[0]["partial"] if windows else None,
            }
        report["windows"] = windows_report

        convergence = {}
        for deploy_key, _journal_path in deploys:
            project = deploy_project.get(deploy_key)
            if project_has_rows(conn, project):
                convergence[deploy_key] = convergence_check(conn, project)
            else:
                convergence[deploy_key] = "проект без трат в БД"
        report["convergence"] = convergence
    finally:
        conn.close()

    return report


def render_selftest(report: dict) -> str:
    lines = ["=== SPEND_MODEL SELFTEST ===", ""]

    imp = report["import"]
    lines.append(f"[import] {imp['elapsed_sec']}s, {imp['rows_imported']} rows, "
                 f"{imp['sessions']} sessions" + (" -- >60s (E11)" if imp["over_60s"] else ""))
    for w in imp["warnings"]:
        lines.append(f"  warning: {w}")

    lines.append("")
    lines.append("[key-form probe, accept key 1]")
    for deploy_key, p in report["key_probe"].items():
        if "error" in p:
            lines.append(f"  {deploy_key}: {p['error']}")
            continue
        lines.append(
            f"  {deploy_key} (project={p['project']}): из {p['agent_form']} worker_ref формы agent: "
            f"(всего delegated={p['total_delegated']}) нашли строки {p['found']}, не нашли {p['notfound']}"
        )

    lines.append("")
    lines.append("[slug mapping, accept key 2]")
    sm = report["slug_mapping"]
    lines.append(f"  distinct project count in cc_usage: {sm['distinct_projects_count']}")
    for deploy_key, m in sm["mapping"].items():
        lines.append(f"  {deploy_key} -> {m['project']}: {m['status']}")

    lines.append("")
    lines.append("[rebuild, accept keys 3/4]")
    rb = report["rebuild"]
    lines.append(f"  idempotent (byte-identical 2 runs): {rb['idempotent']}")
    lines.append(f"  stage_rows={rb['stage_rows']} task_rows={rb['task_rows']}")
    for so in rb["spend_only"]:
        lines.append(f"  spend-only: {so['deploy']}: {so['reason']}")
    cci = report["cc_usage_invariant"]
    lines.append(f"  cc_usage invariant before/after match: {cci['match']} "
                 f"(before={cci['before']}, after={cci['after']})")

    lines.append("")
    lines.append("[windows, accept key 5]")
    for deploy_key, w in report["windows"].items():
        if "error" in w:
            lines.append(f"  {deploy_key}: {w['error']}")
        else:
            lines.append(f"  {deploy_key}: calibrated_windows={w['calibrated_count']} "
                         f"first_partial={w['first_partial']}")

    lines.append("")
    lines.append("[monthly convergence with token_usage_stats, accept key 7]")
    for deploy_key, c in report["convergence"].items():
        if isinstance(c, str):
            lines.append(f"  {deploy_key}: {c}")
            continue
        if not c:
            lines.append(f"  {deploy_key}: нет завершённых полностью-ценённых месячных окон")
        for row in c:
            lines.append(f"  {deploy_key} {row['window']}: own=${row['own_cost']} "
                         f"official=${row['official_cost']} match={row['match']}")

    return "\n".join(lines)


# ========================================================================
# B2 -- METRICS (M1-M14 + M4b) AND DETECTORS (D1-D9), section 6 node B2.
#
# Every metric function returns a dict shaped exactly per accept key 3:
#   {"value", "denominator_kind", "denominator_value", "unpriced_turns",
#    "reason"} -- never a bare 0 for missing data (O3/E6): a `$` SUM
# with zero priced rows returns value=None + reason, a legitimate
# COUNT/SHARE of zero (e.g. "no rework happened") returns a real 0.0.
#
# Judgment calls made in this layer where the spec's own formulas don't
# fully fix a design choice (documented here, not silently decided --
# see the B2 handoff report for the same list with rationale):
#   - M5 ("top-N задач -- вход детектора") doesn't fit window_series'
#     one-scalar-per-metric_key shape; a single "M5" row stores the
#     top-1 task's cost (denominator_kind names its task_id), and
#     top_n_tasks() below is the full list for B3's report to consume
#     directly (not persisted).
#   - M10's "стадий agent=tier": 'ярус' per CLAUDE.md's Role != tier
#     table is the MODEL name (haiku/sonnet/opus/fable), carried by
#     journal delegated.model / task_stage_costs.model_declared -- NOT
#     the `agent` role field (builder/critic/scout/lead). Grouped by
#     the NORMALIZED tier FAMILY (normalize_tier_family, B3 point-fix
#     8в.1 -- collapses model_declared drift like fable-5/claude-fable-5
#     into one "fable" row), not the raw model_declared string; a row's
#     own denominator is "accepted tasks that had >=1 stage at that
#     tier" (a multi-tier task can appear in several tiers'
#     denominators).
#   - M13's "ПРОКСИ" caveat and M4b's "не-задачную работу координатора"
#     caveat are permanent, not conditional on value presence -- both
#     are folded into the `reason` field even when value is not None
#     (reason is documented in the schema as "почему NULL", a generic
#     TEXT field repurposed here for a standing caveat; no column for
#     a separate caveat exists).
#   - The window_series schema (B1, unchanged) has no `flag` column;
#     accept key 4's "поле flag='baseline'" is the schema's own
#     `denominator_kind` field (its comment already reads "'absolute'
#     для абсолютных") -- D1-D6 write denominator_kind='baseline' with
#     the delta in denominator_value; D7-D9 write denominator_kind=
#     'absolute' with the comparison value (D7: fable counterfactual)
#     in denominator_value. The boolean "flagged" verdict is then a
#     trivial reader-side comparison (value vs denominator_value, or
#     value>0), not a separate stored bit.
#   - D9 ("доля вне задач / стадии без транскрипта") is stored as TWO
#     labeled rows (D9:cost_outside_tasks, D9:stages_no_transcript)
#     rather than one combined number -- the two components are not
#     commensurable (a $ share and a stage-count share).
# ========================================================================

M4B_CAVEAT = ("M4b включает не-задачную работу координатора (диалог, бут, "
              "калибровка, релизы)")

PROTOCOL_PATH = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
_CHECK_HEADER_RE = re.compile(r"^\d+\. \*\*", re.MULTILINE)


def count_protocol_checks(path=None) -> "int | None":
    """M12 denominator: greps the numbered check headers of the weekly
    calibration protocol (same form the spec's own accept key uses to
    verify "33"). Returns None (never 0) when the protocol file is
    unreadable -- M12's own E-edge (accept key 7: "M12 при недоступном
    протоколе -> None + reason")."""
    p = Path(path) if path else PROTOCOL_PATH
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    return len(_CHECK_HEADER_RE.findall(text))


# --------------------------------------------------------------------
# 13. Generic helpers -- sums that never silently fold missing prices
#     to 0 (O3/E6), dict-shaped SQL rows, window-membership test.
# --------------------------------------------------------------------
def _metric(value=None, denominator_kind=None, denominator_value=None,
            unpriced_turns=0, reason=None) -> dict:
    return {"value": value, "denominator_kind": denominator_kind,
            "denominator_value": denominator_value,
            "unpriced_turns": unpriced_turns, "reason": reason}


def _sum_optional(values) -> "float | None":
    """SQL SUM()'s own null-handling, made explicit in Python: None
    entries are skipped (not folded into 0); the result is None ONLY
    when there was not a single non-None value (O3 -- a $0 result must
    never be indistinguishable from "no priced data")."""
    have_any = False
    total = 0.0
    for v in values:
        if v is not None:
            have_any = True
            total += v
    return total if have_any else None


def _query_dicts(conn: sqlite3.Connection, sql: str, params=()) -> list:
    cur = conn.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _ts_in_window(dt, window_start, window_end) -> bool:
    """Half-open [start, end) -- mirrors _window_for_ts's own convention
    (B1). dt=None is never "in" any window (E3-adjacent: unattributable,
    not silently bucketed)."""
    if dt is None:
        return False
    if window_start is not None and dt < window_start:
        return False
    if window_end is not None and dt >= window_end:
        return False
    return True


def _tasks_in_window(conn: sqlite3.Connection, window_spec: dict) -> list:
    """calibrated windows: task_costs.window_id already carries the
    EXACT same calibrated_windows() id (B1 computed it identically) --
    a plain equality filter, no ts re-derivation. monthly windows: no
    such precomputed column (B1's finding 8б.5 -- window_id there is
    calibrated-view only), so tasks are matched by first_delegated_ts
    falling in [window_start, window_end)."""
    deploys = window_spec["deploys"]
    if window_spec["kind"] == "calibrated":
        return _query_dicts(
            conn, "SELECT * FROM task_costs WHERE deploy=? AND window_id=?",
            (deploys[0], window_spec["window_id"]),
        )
    if not deploys:
        return []
    placeholders = ",".join("?" for _ in deploys)
    rows = _query_dicts(conn, f"SELECT * FROM task_costs WHERE deploy IN ({placeholders})", deploys)
    ws, we = window_spec["window_start"], window_spec["window_end"]
    out = []
    for r in rows:
        dt = cc_counts.parse_ts(r.get("first_delegated_ts"))
        if _ts_in_window(dt, ws, we):
            out.append(r)
    return out


def _stages_for_tasks(conn: sqlite3.Connection, deploys: list, task_rows: list) -> list:
    task_keys = {(t["deploy"], t["task_id"]) for t in task_rows}
    if not task_keys or not deploys:
        return []
    placeholders = ",".join("?" for _ in deploys)
    rows = _query_dicts(conn, f"SELECT * FROM task_stage_costs WHERE deploy IN ({placeholders})", deploys)
    return [s for s in rows if (s["deploy"], s["task_id"]) in task_keys]


def _cc_usage_rows_in_window(conn: sqlite3.Connection, projects: list, window_start, window_end) -> list:
    if not projects:
        return []
    placeholders = ",".join("?" for _ in projects)
    rows = _query_dicts(
        conn,
        "SELECT ts, project, model, is_sidechain, agent_id, accounted_cost_usd,"
        " input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,"
        f" session_id FROM cc_usage WHERE project IN ({placeholders})",
        projects,
    )
    out = []
    for r in rows:
        dt = normalize_cc_ts_to_local_naive(r["ts"])
        if _ts_in_window(dt, window_start, window_end):
            out.append(r)
    return out


# --------------------------------------------------------------------
# 14. Q1 -- M1/M2/M3/M4/M4b/M5 (section 1).
# --------------------------------------------------------------------
def _m1(task_rows: list) -> dict:
    if not task_rows:
        return _metric(reason="пустое окно (0 задач, E3)")
    accepted = sum(t["accepted"] for t in task_rows)
    stages = sum(t["stages"] for t in task_rows)
    if accepted == 0:
        return _metric(denominator_kind="accepted_tasks", denominator_value=0,
                        reason="0 принятых задач в окне")
    return _metric(stages / accepted, "accepted_tasks", accepted, 0, None)


def _m2(task_rows: list) -> dict:
    if not task_rows:
        return _metric(reason="пустое окно (0 задач, E3)")
    stages = sum(t["stages"] for t in task_rows)
    unpriced = sum(t["unpriced_turns"] for t in task_rows)
    if stages == 0:
        return _metric(denominator_kind="stages", denominator_value=0,
                        unpriced_turns=unpriced, reason="0 переключений в окне")
    cost_sum = _sum_optional(t["cost_usd"] for t in task_rows)
    if cost_sum is None:
        return _metric(denominator_kind="stages", denominator_value=stages,
                        unpriced_turns=unpriced, reason="все задачи окна без цены")
    return _metric(cost_sum / stages, "stages", stages, unpriced, None)


def _m3(task_rows: list, stage_rows: list) -> dict:
    if not task_rows:
        return _metric(reason="пустое окно (0 задач, E3)")
    task_cost_sum = _sum_optional(t["cost_usd"] for t in task_rows)
    unpriced = sum(t["unpriced_turns"] for t in task_rows)
    if task_cost_sum is None:
        return _metric(unpriced_turns=unpriced, reason="все задачи окна без цены")
    if task_cost_sum == 0:
        return _metric(denominator_kind="task_cost", denominator_value=0,
                        unpriced_turns=unpriced, reason="нулевая стоимость задач окна")
    rework_stage_costs = [s["cost_usd"] for s in stage_rows if s.get("is_rework")]
    if not rework_stage_costs:
        # No rework stages AT ALL this window -- a real, legitimate 0.0
        # (not "missing data": M3's own numerator population is empty
        # by construction, distinct from "rework happened but unpriced").
        return _metric(0.0, "task_cost", task_cost_sum, unpriced, None)
    rework_sum = _sum_optional(rework_stage_costs)
    rework_unpriced = sum(1 for c in rework_stage_costs if c is None)
    if rework_sum is None:
        return _metric(denominator_kind="task_cost", denominator_value=task_cost_sum,
                        unpriced_turns=unpriced + rework_unpriced,
                        reason="переделочные стадии окна без цены")
    return _metric(rework_sum / task_cost_sum, "task_cost", task_cost_sum,
                    unpriced + rework_unpriced, None)


def _m4(cc_rows: list) -> dict:
    if not cc_rows:
        return _metric(reason="пустое окно (нет cc_usage в диапазоне)")
    unpriced = sum(1 for r in cc_rows if r["accounted_cost_usd"] is None)
    denom = _sum_optional(r["accounted_cost_usd"] for r in cc_rows)
    if denom is None or denom == 0:
        return _metric(unpriced_turns=unpriced,
                        reason="все ходы окна без цены" if denom is None else "нулевая стоимость окна")
    main_rows = [r for r in cc_rows if not r["is_sidechain"]]
    if not main_rows:
        numer = 0.0  # real zero: no main-chain traffic at all this window
    else:
        numer = _sum_optional(r["accounted_cost_usd"] for r in main_rows)
        if numer is None:
            return _metric(denominator_kind="cc_usage_cost_all", denominator_value=denom,
                            unpriced_turns=unpriced, reason="main-chain строки окна без цены")
    return _metric(numer / denom, "cc_usage_cost_all", denom, unpriced, None)


def _m4b(cc_rows: list, task_rows: list) -> dict:
    accepted = sum(t["accepted"] for t in task_rows) if task_rows else 0
    main_rows = [r for r in cc_rows if not r["is_sidechain"]]
    by_model = defaultdict(list)
    for r in main_rows:
        by_model[r["model"] or "<нет>"].append(r["accounted_cost_usd"])
    if not by_model:
        return {"M4b": _metric(reason="нет main-chain трафика в окне")}
    out = {}
    for model, costs in sorted(by_model.items()):
        key = f"M4b:{model}"
        unpriced = sum(1 for c in costs if c is None)
        if accepted == 0:
            out[key] = _metric(denominator_kind="accepted_tasks", denominator_value=0,
                                unpriced_turns=unpriced, reason="0 принятых задач в окне")
            continue
        cost_sum = _sum_optional(costs)
        if cost_sum is None:
            out[key] = _metric(denominator_kind="accepted_tasks", denominator_value=accepted,
                                unpriced_turns=unpriced,
                                reason=f"main-chain {model} без цены в окне")
            continue
        out[key] = _metric(cost_sum / accepted, "accepted_tasks", accepted, unpriced, M4B_CAVEAT)
    return out


def top_n_tasks(task_rows: list, top_n: int = 10) -> list:
    """M5's full ranked list (top-N by cost, the columns section 1 asks
    for) -- consumed directly by B3's R4.2 report, NOT persisted to
    window_series (see the module-level judgment-call note)."""
    priced = [t for t in task_rows if t.get("cost_usd") is not None]
    ranked = sorted(priced, key=lambda t: t["cost_usd"], reverse=True)
    return [
        {"deploy": t["deploy"], "task_id": t["task_id"], "stages": t["stages"],
         "rework_stages": t["rework_stages"], "critic_entries": t["critic_entries"],
         "cost_usd": t["cost_usd"], "accepted": t["accepted"]}
        for t in ranked[:top_n]
    ]


def _m5(task_rows: list) -> dict:
    top1 = top_n_tasks(task_rows, top_n=1)
    if not top1:
        return {"M5": _metric(reason="нет ценённых задач в окне (топ-N пуст)")}
    t = top1[0]
    return {"M5": _metric(
        t["cost_usd"], f"top1_task:{t['deploy']}:{t['task_id']}", None, 0,
        "M5 хранит топ-1 задачи окна; полный топ-N -- top_n_tasks() для отчёта B3",
    )}


# --------------------------------------------------------------------
# 15. Q2 -- M6/M7/M8/M12 (run_units-backed; E7: honest "н/д" while the
#     registry table has zero rows -- B4 not dispatched yet).
# --------------------------------------------------------------------
def _session_cost_in_span(conn: sqlite3.Connection, projects: list, session_id,
                           ts_start_dt, ts_end_dt):
    """Returns (cost_or_None, unpriced_count, reason_or_None). Searches
    ACROSS all `projects` in scope (run_units carries no project column
    of its own -- session_id is the join key, matched against whichever
    project it actually belongs to)."""
    if not projects or not session_id or ts_start_dt is None or ts_end_dt is None:
        return None, 0, "н/д (границы прогона неполны)"
    placeholders = ",".join("?" for _ in projects)
    rows = _query_dicts(
        conn,
        f"SELECT ts, accounted_cost_usd FROM cc_usage WHERE project IN ({placeholders}) AND session_id=?",
        list(projects) + [session_id],
    )
    costs, unpriced = [], 0
    for r in rows:
        dt = normalize_cc_ts_to_local_naive(r["ts"])
        if not _ts_in_window(dt, ts_start_dt, ts_end_dt):
            continue
        if r["accounted_cost_usd"] is None:
            unpriced += 1
        else:
            costs.append(r["accounted_cost_usd"])
    if not costs and unpriced == 0:
        return None, 0, "нет строк cc_usage в границах прогона"
    return (sum(costs) if costs else None), unpriced, None


def m6_run_cost(conn: sqlite3.Connection, projects: list, run_row: dict) -> dict:
    """M6 = Σ cost строк сессии в [ts_start, ts_end) прогона (section 1,
    Q2). `run_row` is a run_units row (a run-LEVEL row, phase IS NULL,
    per decision (б))."""
    ts_start = cc_counts.parse_ts(run_row.get("ts_start"))
    ts_end = cc_counts.parse_ts(run_row.get("ts_end"))
    cost, unpriced, reason = _session_cost_in_span(conn, projects, run_row.get("session_id"),
                                                     ts_start, ts_end)
    if reason:
        return _metric(unpriced_turns=unpriced, reason=reason)
    if cost is None:
        return _metric(unpriced_turns=unpriced, reason="строки прогона без цены")
    return _metric(cost, "run_session_span", None, unpriced, None)


def _run_units_level_rows_in_window(conn: sqlite3.Connection, ws, we) -> list:
    rows = _query_dicts(conn, "SELECT * FROM run_units WHERE phase IS NULL")
    out = []
    for r in rows:
        dt = cc_counts.parse_ts(r.get("ts_start"))
        if dt is not None and _ts_in_window(dt, ws, we):
            out.append(r)
    return out


def _run_units_phase_rows(conn: sqlite3.Connection, run_id) -> list:
    return _query_dicts(conn, "SELECT * FROM run_units WHERE run_id=? AND phase IS NOT NULL", (run_id,))


def _m6_m7_m8_m12(conn: sqlite3.Connection, projects: list, ws, we) -> dict:
    """M6 (Σ cost/run, per skill), M7 (per-phase share within a skill's
    runs), M8 ($/unit, per skill) and M12 ($/протокольный чек, one
    run_kind='calibration' slice, decision (б)) -- all Σ/Σ over the
    runs of each (run_kind, name) observed in the window, the same
    aggregation shape M1/M2/M9/M10 already use elsewhere in this file.
    E7 (run_units table/rows absent -- true today, B4 not dispatched):
    every one of the four keys below comes back "н/д (реестра нет)",
    never a crash, never a silent 0."""
    total_rows = conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0]
    na = _metric(reason="н/д (реестра нет)")
    if total_rows == 0:
        return {"M6": na, "M7": na, "M8": na, "M12": na}

    level_rows = _run_units_level_rows_in_window(conn, ws, we)
    if not level_rows:
        na_win = _metric(reason="н/д (нет прогонов реестра в окне)")
        return {"M6": na_win, "M7": na_win, "M8": na_win, "M12": na_win}

    out = {}
    by_kind_name = defaultdict(list)
    calib_rows = []
    for lr in level_rows:
        cm = m6_run_cost(conn, projects, lr)
        by_kind_name[(lr.get("run_kind"), lr.get("name"))].append((lr, cm))
        if lr.get("run_kind") == "calibration":
            calib_rows.append((lr, cm))

    for (run_kind, name), items in sorted(by_kind_name.items(), key=lambda kv: (kv[0][0] or "", kv[0][1] or "")):
        cost_sum = _sum_optional(m["value"] for _lr, m in items)
        unpriced = sum(m["unpriced_turns"] for _lr, m in items)
        key6 = f"M6:{run_kind}:{name}"
        if cost_sum is None:
            out[key6] = _metric(unpriced_turns=unpriced, reason="строки прогонов без цены")
        else:
            out[key6] = _metric(cost_sum, "run_count", len(items), unpriced, None)

        unit_sum = sum((lr.get("unit_count") or 0) for lr, _m in items if lr.get("unit_count"))
        key8 = f"M8:{run_kind}:{name}"
        if cost_sum is None or not unit_sum:
            out[key8] = _metric(unpriced_turns=unpriced, reason="нет unit_count или строки без цены")
        else:
            out[key8] = _metric(cost_sum / unit_sum, "unit_count", unit_sum, unpriced, None)

        phase_totals = defaultdict(list)
        for lr, _m in items:
            for pr in _run_units_phase_rows(conn, lr["run_id"]):
                phase_totals[pr.get("phase")].append(m6_run_cost(conn, projects, pr))
        if not phase_totals:
            out[f"M7:{run_kind}:{name}"] = _metric(reason="нет фазовых меток")
        elif cost_sum:
            for phase, pms in sorted(phase_totals.items()):
                pc = _sum_optional(m["value"] for m in pms)
                pu = sum(m["unpriced_turns"] for m in pms)
                key7 = f"M7:{run_kind}:{name}:{phase}"
                if pc is None:
                    out[key7] = _metric(unpriced_turns=pu, reason="фазовые строки без цены")
                else:
                    out[key7] = _metric(pc / cost_sum, "run_cost", cost_sum, pu, None)

    if calib_rows:
        calib_cost = _sum_optional(m["value"] for _lr, m in calib_rows)
        n_checks = count_protocol_checks()
        if calib_cost is None:
            out["M12"] = _metric(reason="строки калибровки без цены")
        elif not n_checks:
            out["M12"] = _metric(reason="протокол недоступен")
        else:
            out["M12"] = _metric(calib_cost / n_checks, "protocol_checks", n_checks, 0, None)
    else:
        out["M12"] = _metric(reason="н/д (нет прогона калибровки в окне)")

    out.setdefault("M6", _metric(reason="н/д (нет прогонов в окне)"))
    out.setdefault("M7", _metric(reason="нет фазовых меток"))
    out.setdefault("M8", _metric(reason="нет unit_count"))
    return out


# --------------------------------------------------------------------
# 16. Q3 -- M9/M10/M11/M13/M14 (section 1).
# --------------------------------------------------------------------
def _m9(sub_deploys_config: list, ws, we, m4_metric: dict) -> dict:
    total_events = 0
    any_journal = False
    for _deploy_key, journal_path in sub_deploys_config:
        try:
            analysis = cc_counts.analyze_journal(
                journal_path, ws, we, cc_counts.parse_ts(cc_counts.DEFAULT_BY_SINCE),
            )
        except OSError:
            continue
        any_journal = True
        total_events += analysis["in_window_count"]
    if not any_journal:
        return _metric(reason="журналы окна недоступны")
    if total_events == 0:
        return _metric(denominator_kind="in_window_count", denominator_value=0,
                        reason="0 событий журнала в окне")
    total_cost = m4_metric["denominator_value"] if m4_metric["denominator_kind"] == "cc_usage_cost_all" else None
    if total_cost is None:
        return _metric(denominator_kind="in_window_count", denominator_value=total_events,
                        unpriced_turns=m4_metric["unpriced_turns"], reason="нет ценённых ходов окна")
    return _metric(total_cost / total_events, "in_window_count", total_events,
                    m4_metric["unpriced_turns"], None)


def _m10(task_rows: list, stage_rows: list) -> dict:
    accepted_task_keys = {(t["deploy"], t["task_id"]) for t in task_rows if t["accepted"]}
    task_tiers = defaultdict(set)
    by_tier_cost = defaultdict(list)
    for s in stage_rows:
        raw_tier = s.get("model_declared")
        if not raw_tier:
            continue
        # B3 point-fix (8в.1): group by the NORMALIZED tier family, not
        # the raw declaration -- fable/fable-5/claude-fable-5 must land
        # in the same M10/D4 row (normalize_tier_family above).
        tier, _reason = normalize_tier_family(raw_tier)
        task_tiers[(s["deploy"], s["task_id"])].add(tier)
        by_tier_cost[tier].append(s["cost_usd"])
    if not by_tier_cost:
        return {"M10": _metric(reason="нет стадий с указанной моделью в окне")}
    out = {}
    for tier, costs in sorted(by_tier_cost.items()):
        key = f"M10:{tier}"
        unpriced = sum(1 for c in costs if c is None)
        denom = sum(1 for tk, tiers in task_tiers.items() if tier in tiers and tk in accepted_task_keys)
        if denom == 0:
            out[key] = _metric(denominator_kind="accepted_tier_tasks", denominator_value=0,
                                unpriced_turns=unpriced, reason=f"0 принятых задач яруса {tier} в окне")
            continue
        cost_sum = _sum_optional(costs)
        if cost_sum is None:
            out[key] = _metric(denominator_kind="accepted_tier_tasks", denominator_value=denom,
                                unpriced_turns=unpriced, reason=f"стадии яруса {tier} без цены")
            continue
        out[key] = _metric(cost_sum / denom, "accepted_tier_tasks", denom, unpriced, None)
    return out


def _git_numstat_added_deleted(repo_root: str, since_dt, until_dt):
    """subprocess is explicitly allowed for this one purpose (section 9).
    Returns (total_added_plus_deleted, None) on success (0 is a REAL
    value here, e.g. genuinely zero commits/changes -- the caller, M11,
    decides how to fold that into "None" per accept key 7's literal
    "M11 при нуле коммитов окна -> None"), or (None, reason) when git
    itself is unavailable/errors -- never raises."""
    cmd = ["git", "log", "--numstat", "--pretty=format:"]
    if since_dt is not None:
        cmd.append(f"--since={since_dt.isoformat()}")
    if until_dt is not None:
        cmd.append(f"--until={until_dt.isoformat()}")
    try:
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"git недоступен в {repo_root} ({exc})"
    if proc.returncode != 0:
        # A brand-new repo with literally zero commits ever is git's own
        # "does not have any commits yet" failure (exit 128) -- a REAL
        # zero (no history to diff), not a git/repo-access failure; any
        # OTHER non-zero exit (not a repo, corrupted, etc.) stays a
        # genuine failure -> None+reason.
        if "does not have any commits yet" in (proc.stderr or ""):
            return 0, None
        return None, f"git log завершился с кодом {proc.returncode} в {repo_root}"
    total = 0
    for line in proc.stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 2:
            continue
        for v in parts[0], parts[1]:
            if v != "-":
                try:
                    total += int(v)
                except ValueError:
                    pass
    return total, None


def _m11(sub_deploys_config: list, stage_rows: list, ws, we) -> dict:
    critic_costs = [s["cost_usd"] for s in stage_rows if s.get("agent") == "critic"]
    if not critic_costs:
        return _metric(reason="нет critic-стадий в окне")
    cost_sum = _sum_optional(critic_costs)
    unpriced = sum(1 for c in critic_costs if c is None)
    if cost_sum is None:
        return _metric(unpriced_turns=unpriced, reason="critic-стадии окна без цены")
    total_lines = 0
    any_success = False
    failures = []
    for _deploy_key, journal_path in sub_deploys_config:
        repo_root = str(Path(journal_path).resolve().parent.parent)
        lines, reason = _git_numstat_added_deleted(repo_root, ws, we)
        if lines is None:
            failures.append(reason)
            continue
        any_success = True
        total_lines += lines
    if not any_success:
        return _metric(unpriced_turns=unpriced, reason="git diff недоступен: " + "; ".join(failures))
    if total_lines == 0:
        return _metric(unpriced_turns=unpriced, reason="0 коммитов в окне (M11 н/д)")
    return _metric(cost_sum / total_lines, "diff_lines", total_lines, unpriced, None)


def _m13(stage_rows: list) -> dict:
    scout_rows = [s for s in stage_rows if s.get("agent") == "scout"]
    if not scout_rows:
        return _metric(reason="нет scout-стадий в окне (M13 ПРОКСИ)")
    unpriced = sum(1 for s in scout_rows if s["cost_usd"] is None)
    cost_sum = _sum_optional(s["cost_usd"] for s in scout_rows)
    turns = sum(s.get("turns") or 0 for s in scout_rows)
    if cost_sum is None or turns == 0:
        return _metric(unpriced_turns=unpriced, reason="scout-стадии без цены/ходов (M13 ПРОКСИ)")
    return _metric(cost_sum / turns, "scout_turns", turns, unpriced,
                    "ПРОКСИ (байты чтения недоступны без нарушения приватностного контракта)")


def _m14(task_rows: list, stage_rows: list) -> dict:
    esc_tasks = [t for t in task_rows if (t.get("escalated_count") or 0) >= 1]
    if not esc_tasks:
        m = _metric(denominator_kind="escalated_tasks", denominator_value=0,
                     reason="нет эскалаций в окне")
        m["counterfactual_avg"] = None
        return m
    cost_sum = _sum_optional(t["cost_usd"] for t in esc_tasks)
    unpriced = sum(t["unpriced_turns"] for t in esc_tasks)
    count = len(esc_tasks)

    tokens_by_task = defaultdict(lambda: [0, 0, 0, 0])
    for s in stage_rows:
        acc = tokens_by_task[(s["deploy"], s["task_id"])]
        acc[0] += s.get("input_tokens") or 0
        acc[1] += s.get("output_tokens") or 0
        acc[2] += s.get("cache_creation_tokens") or 0
        acc[3] += s.get("cache_read_tokens") or 0
    cf_values = []
    for t in esc_tasks:
        i, o, cw, cr = tokens_by_task.get((t["deploy"], t["task_id"]), (0, 0, 0, 0))
        cf = fable_counterfactual(i, o, cw, cr)
        if cf is not None:
            cf_values.append(cf)
    cf_avg = (sum(cf_values) / len(cf_values)) if cf_values else None

    if cost_sum is None:
        m = _metric(denominator_kind="escalated_tasks", denominator_value=count,
                     unpriced_turns=unpriced, reason="эскалированные задачи окна без цены")
        m["counterfactual_avg"] = cf_avg
        return m
    m = _metric(cost_sum / count, "escalated_tasks", count, unpriced, None)
    m["counterfactual_avg"] = cf_avg
    return m


# --------------------------------------------------------------------
# 17. Q4 detectors -- D5/D7/D8/D9 (self-contained), D1/D2/D3/D4/D6
#     (baseline deltas over M4/M3/M2/M10/M1, see _compute_detectors).
# --------------------------------------------------------------------
def _d5(cc_rows: list) -> dict:
    """cache_read_share by cc_usage's DISJOINT columns (F-38) -- NOT
    gateway/metrics.py's requests-table formula (its prompt_tokens is
    INCLUSIVE of the cache columns, a different semantic entirely)."""
    if not cc_rows:
        return _metric(reason="пустое окно (нет cc_usage в диапазоне)")
    inp = sum(r["input_tokens"] or 0 for r in cc_rows)
    outp = sum(r["output_tokens"] or 0 for r in cc_rows)
    cw = sum(r["cache_creation_tokens"] or 0 for r in cc_rows)
    cr = sum(r["cache_read_tokens"] or 0 for r in cc_rows)
    denom = inp + outp + cw + cr
    if denom == 0:
        return _metric(reason="0 токенов в окне")
    return _metric(cr / denom, "tokens_all", denom, 0, None)


def _d7(m14_metric: dict) -> dict:
    cf = m14_metric.get("counterfactual_avg")
    if m14_metric["value"] is None or cf is None:
        return _metric(unpriced_turns=m14_metric["unpriced_turns"],
                        reason=m14_metric["reason"] or "контрфакт недоступен")
    return _metric(m14_metric["value"], "absolute", cf, m14_metric["unpriced_turns"], None)


def _d8(cc_rows: list) -> dict:
    if not cc_rows:
        return _metric(reason="пустое окно (нет cc_usage в диапазоне)")
    n_null = sum(1 for r in cc_rows if r["accounted_cost_usd"] is None)
    return _metric(float(n_null), "absolute", float(len(cc_rows)), 0, None)


def _d9(task_rows: list, stage_rows: list, cc_rows: list) -> dict:
    out = {}
    total_cost = _sum_optional(r["accounted_cost_usd"] for r in cc_rows)
    if not cc_rows or total_cost is None:
        out["D9:cost_outside_tasks"] = _metric(
            reason="пустое окно / нет ценённых ходов" if not cc_rows else "все ходы окна без цены")
    else:
        measurable_keys = {s["agent_key"] for s in stage_rows if s.get("measurable") and s.get("agent_key")}
        attributed = _sum_optional(
            r["accounted_cost_usd"] for r in cc_rows if r.get("agent_id") in measurable_keys
        ) or 0.0
        outside = max(total_cost - attributed, 0.0)
        out["D9:cost_outside_tasks"] = _metric(outside / total_cost, "cc_usage_cost_all",
                                                total_cost, 0, None)
    total_stages = len(stage_rows)
    if total_stages == 0:
        out["D9:stages_no_transcript"] = _metric(reason="нет стадий в окне")
    else:
        no_transcript = sum(1 for s in stage_rows if not s.get("measurable"))
        out["D9:stages_no_transcript"] = _metric(no_transcript / total_stages, "stages",
                                                   total_stages, 0, None)
    return out


def _baseline_delta(m: dict, prev_value) -> dict:
    """D1-D6 (Е3 chosen, section 5): no threshold in v1 -- value/delta
    only, denominator_kind='baseline' is the "flag" field (see the
    module docstring note)."""
    if m["value"] is None:
        return _metric(None, "baseline", None, m["unpriced_turns"], m["reason"])
    if prev_value is None:
        return _metric(m["value"], "baseline", None, m["unpriced_turns"], "первое окно (нет прошлой точки ряда)")
    return _metric(m["value"], "baseline", m["value"] - prev_value, m["unpriced_turns"], None)


def _compute_detectors(metrics: dict, prev_snapshot: dict) -> dict:
    mirrors = {"D1": "M4", "D2": "M3", "D3": "M2", "D6": "M1"}
    out = {}
    for dkey, mkey in mirrors.items():
        out[dkey] = _baseline_delta(metrics[mkey], prev_snapshot.get(mkey))
    for mkey, m in metrics.items():
        if mkey.startswith("M10:"):
            tier = mkey.split(":", 1)[1]
            out[f"D4:{tier}"] = _baseline_delta(m, prev_snapshot.get(mkey))
    return out


# --------------------------------------------------------------------
# 18. Window resolution + orchestration (compute_window_series).
# --------------------------------------------------------------------
def compute_all_window_metrics(conn: sqlite3.Connection, window_spec: dict,
                                deploy_project: dict, deploys_config=None) -> dict:
    deploys_config = DEPLOYS if deploys_config is None else deploys_config
    deploy_keys = window_spec["deploys"]
    projects = [p for p in (deploy_project.get(d) for d in deploy_keys) if p]
    ws, we = window_spec["window_start"], window_spec["window_end"]

    task_rows = _tasks_in_window(conn, window_spec)
    stage_rows = _stages_for_tasks(conn, deploy_keys, task_rows)
    cc_rows = _cc_usage_rows_in_window(conn, projects, ws, we)
    sub_deploys_config = [(k, p) for k, p in deploys_config if k in deploy_keys]

    out = {}
    out["M1"] = _m1(task_rows)
    out["M2"] = _m2(task_rows)
    out["M3"] = _m3(task_rows, stage_rows)
    out["M4"] = _m4(cc_rows)
    out.update(_m4b(cc_rows, task_rows))
    out.update(_m5(task_rows))
    out.update(_m6_m7_m8_m12(conn, projects, ws, we))
    out["M9"] = _m9(sub_deploys_config, ws, we, out["M4"])
    out.update(_m10(task_rows, stage_rows))
    out["M11"] = _m11(sub_deploys_config, stage_rows, ws, we)
    out["M13"] = _m13(stage_rows)
    out["M14"] = _m14(task_rows, stage_rows)
    out["D5"] = _d5(cc_rows)
    out.update(_d9(task_rows, stage_rows, cc_rows))
    out["D7"] = _d7(out["M14"])
    out["D8"] = _d8(cc_rows)
    return out


_WINDOW_SERIES_COLUMNS = [
    "window_id", "window_start", "window_end", "partial", "scope", "metric_key",
    "value", "denominator_kind", "denominator_value", "unpriced_turns", "reason", "computed_at",
]
_INSERT_WINDOW_SERIES_SQL = (
    "INSERT INTO window_series (" + ", ".join(_WINDOW_SERIES_COLUMNS) + ") VALUES ("
    + ", ".join("?" for _ in _WINDOW_SERIES_COLUMNS) + ")"
)


def _window_series_row(window_spec: dict, metric_key: str, m: dict, computed_at: str) -> dict:
    return {
        "window_id": window_spec["window_id"],
        "window_start": window_spec["window_start"].isoformat() if window_spec["window_start"] else None,
        "window_end": window_spec["window_end"].isoformat() if window_spec["window_end"] else None,
        "partial": window_spec["partial"], "scope": window_spec["scope"],
        "metric_key": metric_key, "value": m["value"],
        "denominator_kind": m["denominator_kind"], "denominator_value": m["denominator_value"],
        "unpriced_turns": m["unpriced_turns"], "reason": m["reason"], "computed_at": computed_at,
    }


def _window_series_to_tuple(row: dict) -> tuple:
    return tuple(row.get(c) for c in _WINDOW_SERIES_COLUMNS)


def _monthly_window_specs(conn: sqlite3.Connection, deploys_config: list, deploy_project: dict,
                           scope: str, now: datetime) -> list:
    if scope == "all":
        deploy_keys = [k for k, _p in deploys_config]
        projects = [p for p in (deploy_project.get(k) for k in deploy_keys) if p]
        wid_prefix = "all"
    else:
        deploy_keys = [deploys_config[0][0]]
        projects = [p for p in (deploy_project.get(deploy_keys[0]),) if p]
        wid_prefix = deploy_keys[0]
    keys = set()
    if projects:
        placeholders = ",".join("?" for _ in projects)
        for (ts,) in conn.execute(f"SELECT DISTINCT ts FROM cc_usage WHERE project IN ({placeholders})", projects):
            dt = normalize_cc_ts_to_local_naive(ts)
            if dt is not None:
                keys.add(tus.window_of(dt))
    keys.add(tus.window_of(now))
    specs = []
    for wy, wm in sorted(keys):
        start, end = _monthly_bounds(wy, wm)
        label = tus.window_label(wy, wm)
        specs.append({
            "window_id": f"{wid_prefix}:monthly:{label}", "window_start": start, "window_end": end,
            "partial": 1 if end > now else 0, "kind": "monthly", "scope": scope, "deploys": deploy_keys,
        })
    return specs


def _process_window(conn: sqlite3.Connection, window_spec: dict, deploy_project: dict,
                     deploys_config: list, series_prev: dict, all_rows: list, computed_at: str) -> None:
    sid = f"{window_spec['kind']}:{window_spec['scope']}:{'+'.join(window_spec['deploys'])}"
    prev_snapshot = {k: v for (s, k), v in series_prev.items() if s == sid}
    metrics = compute_all_window_metrics(conn, window_spec, deploy_project, deploys_config)
    detectors = _compute_detectors(metrics, prev_snapshot)
    for mkey, m in metrics.items():
        all_rows.append(_window_series_row(window_spec, mkey, m, computed_at))
    for dkey, d in detectors.items():
        all_rows.append(_window_series_row(window_spec, dkey, d, computed_at))
    for mkey, m in metrics.items():
        if m["value"] is not None:
            series_prev[(sid, mkey)] = m["value"]


def compute_window_series(conn: sqlite3.Connection, deploys=None, deploy_project=None, now=None) -> dict:
    """Fills window_series for BOTH kinds and BOTH scopes (accept key 5):
    per deploy -- its own calibrated windows (scope=deploy) AND its own
    monthly windows (scope=deploy); PLUS one shared monthly series
    (scope=all) across every deploy. DELETE+INSERT one transaction,
    mirroring rebuild()'s own idempotency contract; computed_at is the
    ONE field expected to differ between two rebuilds of identical data
    -- _dump_window_series() (test helper) excludes it from the
    byte-comparison the idempotency test runs."""
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    now = now or datetime.now()
    computed_at = now.isoformat()
    _ensure_schema(conn)

    all_rows = []
    series_prev = {}
    calibrated_counts = {}

    for deploy_key, journal_path in deploys:
        try:
            lines = cc_counts.load_journal(journal_path)
        except OSError:
            calibrated_counts[deploy_key] = 0
            continue
        cal_tss = sorted(pl.ts for pl in lines
                          if pl.data and pl.data.get("event") == "calibrated" and pl.ts)
        windows = calibrated_windows(deploy_key, cal_tss)
        calibrated_counts[deploy_key] = len(windows)
        for w in windows:
            w["kind"] = "calibrated"; w["scope"] = "deploy"; w["deploys"] = [deploy_key]
            _process_window(conn, w, deploy_project, deploys, series_prev, all_rows, computed_at)

        for w in _monthly_window_specs(conn, [(deploy_key, journal_path)], deploy_project, "deploy", now):
            _process_window(conn, w, deploy_project, deploys, series_prev, all_rows, computed_at)

    for w in _monthly_window_specs(conn, deploys, deploy_project, "all", now):
        _process_window(conn, w, deploy_project, deploys, series_prev, all_rows, computed_at)

    try:
        conn.execute("DELETE FROM window_series")
        conn.executemany(_INSERT_WINDOW_SERIES_SQL, [_window_series_to_tuple(r) for r in all_rows])
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()

    return {"rows": len(all_rows), "calibrated_windows": calibrated_counts}


def _dump_window_series(conn: sqlite3.Connection) -> str:
    """Idempotency-test dump: excludes computed_at (the one column
    expected to differ between two otherwise-identical rebuilds)."""
    cols = [c for c in _WINDOW_SERIES_COLUMNS if c != "computed_at"]
    rows = conn.execute(
        f"SELECT {', '.join(cols)} FROM window_series ORDER BY window_id, metric_key"
    ).fetchall()
    return "\n".join(repr(r) for r in rows)


def resolve_last_calibrated_window(conn: sqlite3.Connection, deploy_key: str, deploys=None):
    deploys = DEPLOYS if deploys is None else deploys
    journal_path = dict(deploys).get(deploy_key)
    if not journal_path:
        return None
    try:
        lines = cc_counts.load_journal(journal_path)
    except OSError:
        return None
    cal_tss = sorted(pl.ts for pl in lines
                      if pl.data and pl.data.get("event") == "calibrated" and pl.ts)
    windows = calibrated_windows(deploy_key, cal_tss)
    if not windows:
        return None
    w = windows[-1]
    w["kind"] = "calibrated"; w["scope"] = "deploy"; w["deploys"] = [deploy_key]
    return w


def resolve_last_monthly_all_scope_window(conn: sqlite3.Connection, deploys=None,
                                           deploy_project=None, now=None):
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    now = now or datetime.now()
    specs = _monthly_window_specs(conn, deploys, deploy_project, "all", now)
    return specs[-1] if specs else None


def window_metric_rows_from_db(conn: sqlite3.Connection, window_id: str) -> dict:
    rows = _query_dicts(conn, "SELECT * FROM window_series WHERE window_id=? ORDER BY metric_key", (window_id,))
    return {"window_id": window_id, "metrics": rows}


def cmd_compute_window(db_file: Path, deploys=None, deploy_project=None,
                        skip_import: bool = False, which: str = "last") -> dict:
    deploys = DEPLOYS if deploys is None else deploys
    deploy_project = DEPLOY_PROJECT if deploy_project is None else deploy_project
    if not skip_import:
        import_transcripts(transcript_glob(), db_file)
    conn = sqlite3.connect(db_file)
    try:
        rebuild(conn, deploys, deploy_project)
        compute_window_series(conn, deploys, deploy_project)
        result = {}
        if which == "last":
            w1 = resolve_last_calibrated_window(conn, "shtab", deploys)
            result["calibrated_last_shtab"] = (
                window_metric_rows_from_db(conn, w1["window_id"]) if w1
                else {"error": "нет calibrated-окон shtab"}
            )
            w2 = resolve_last_monthly_all_scope_window(conn, deploys, deploy_project)
            result["monthly_all_scope_last"] = (
                window_metric_rows_from_db(conn, w2["window_id"]) if w2
                else {"error": "нет monthly-окон"}
            )
        else:
            result["window"] = window_metric_rows_from_db(conn, which)
        return result
    finally:
        conn.close()


# --------------------------------------------------------------------
# 12. CLI
# --------------------------------------------------------------------
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Spend-monitoring core join + derived tables (B1)."
    )
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--project", default=None,
                         help="E10: explicit cc_usage.project filter; 0 rows -> exit 2 (loud, never silent)")
    parser.add_argument("--db", default=None, help="override gateway/requests.db path (tests)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip-import", action="store_true",
                         help="skip the lazy transcript import (tests/CI -- no real ~/.claude/projects scan)")
    parser.add_argument("--compute-window", default=None,
                         help="B2: 'last' (calibrated-last-shtab + monthly-all-scope-last) "
                              "or an explicit window_id; rebuilds task tables + window_series first")
    args = parser.parse_args(argv)

    db_file = Path(args.db) if args.db else _cc_db_path()

    if args.project is not None:
        conn = sqlite3.connect(db_file)
        try:
            if not resolve_project_or_refuse(conn, args.project):
                return 2
        finally:
            conn.close()

    if args.selftest:
        report = run_selftest(db_file, skip_import=args.skip_import)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        else:
            print(render_selftest(report))
        return 0

    if args.compute_window:
        result = cmd_compute_window(db_file, skip_import=args.skip_import, which=args.compute_window)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            for label, section in result.items():
                print(f"=== {label} ===")
                if "error" in section:
                    print(f"  {section['error']}")
                    continue
                for row in section["metrics"]:
                    print(f"  {row['metric_key']}: value={row['value']} reason={row['reason']}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
