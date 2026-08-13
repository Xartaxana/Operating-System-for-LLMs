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
import sqlite3
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
    PRIMARY KEY (deploy, task_id, stage_index)
);
"""

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
    conn.commit()


_STAGE_COLUMNS = [
    "deploy", "task_id", "stage_index", "journal_line", "ts_local", "agent",
    "model_declared", "worker_ref", "agent_key", "project", "turns",
    "input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens",
    "cost_usd", "unpriced_turns", "models_measured", "stage_kind", "measurable",
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
    # (O1: "replaces_worker НЕ реворк") -- mirrors calibration_counts'
    # branch classification via the already-collapsed stage_kind.
    first_rejected_line = min(rejected_lines) if rejected_lines else None
    rework_stages = 0
    if first_rejected_line is not None:
        rework_stages = sum(
            1 for s in stages_sorted
            if s["journal_line"] > first_rejected_line and s["stage_kind"] != "replacement"
        )

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

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
