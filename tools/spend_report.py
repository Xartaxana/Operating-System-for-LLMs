"""tools/spend_report.py -- spend-monitoring REPORT + CLI (B3,
docs/tasks/2026-08-13_spend-analytics.md section 4/6 node B3).

WHAT THIS MODULE DOES (nothing more -- formulas/schema are B1/B2's
tools/spend_model.py, this module only READS window_series/task_costs/
task_stage_costs/run_units and RENDERS them; the one exception is the
tier-family normalization POINT-FIX, which lives in spend_model.py
itself per the B3 spec, not here):
  1. Lazy import + rebuild + compute_window_series (R4.5 decision Г1)
     on every invocation, then renders the four report forms:
       R4.1 "окно к окну"        -- build_r4_1 / _r4_1_row / _flag_for_row
       R4.2 "ранжированные стоки" -- build_r4_2 (top_n_tasks + D-строки)
       R4.3 "здоровье измерения"  -- build_r4_3 (ALWAYS printed, accept
                                      key 3 -- built BEFORE window
                                      resolution so a window-resolution
                                      failure never suppresses it)
       R4.4 CLI                  -- main()/argparse
  2. --window-start/--window-end (O2's "Переопределение", exercised by
     the B3 adversarial battery) computes an AD-HOC window via
     spend_model.compute_all_window_metrics() directly -- NOT persisted
     to window_series (no "custom" window kind exists in that schema,
     and this module owns no schema changes, non-goals). "prev window"
     / trend lookups for a custom window degrade gracefully to "н/д"
     (no matching window_id prefix exists in the persisted table) --
     no special-casing needed, see _resolve_prev_window_id.

JUDGMENT CALLS made where the spec's own prose underspecifies a report-
layout detail (documented here, not silently decided -- same convention
B1/B2 used for their own judgment calls, listed in their handoff
reports; see this module's own B3 handoff report for the same list):
  - R4.1's "метрика" rows are EVERY window_series row of the resolved
    window (both M* and D* keys), not only the D1-D9 detectors --
    "суммы с unpriced" in the spec's own wording clearly targets $
    metrics like M2/M6/M10/M11/M12/M14, not just detectors. The "флаг"
    column is populated per detector-class rules (see _flag_for_row)
    and left blank ("") for plain M-metric rows -- they are not
    detectors and the spec never defines a flag formula for them.
  - Threshold class split (section 5's own text: "первая версия
    печатает базлайн и метит флаги «ПРЕДВАРИТЕЛЬНЫЙ ПОРОГ»"): D7 and D8
    have FULLY SPECIFIED formulas in the spec's own "порог" column
    ("контрфакт дешевле факта", "> 0 -- флаг всегда") -> real verdicts.
    Every other detector (D1-D6, D4:<tier>, D5, D9:*) has an
    UNDETERMINED "> X" threshold (развилка е not resolved) -> baseline
    direction+magnitude only, tagged "ПРЕДВАРИТЕЛЬНЫЙ ПОРОГ", no
    verdict -- this applies section 5's own instruction uniformly
    rather than re-deriving it per detector.
  - R4.2's "+ D-строки": top-N TASKS (one-off, single-window entities --
    a task by construction belongs to exactly one window, so "тренд K
    окон" cannot apply to it) are listed separately from RECURRING
    per-window detector buckets (D1-D9/D4:<tier>, which persist across
    windows and so DO have a meaningful multi-window trend). "детектор"
    column: for task rows, a cheap same-row marker ("rework" when
    rework_stages>0, else blank) -- not a cross-reference into D1-D9
    (the spec names no such cross-reference formula); for D-rows, the
    same verdict text as R4.1's flag column.
  - R4.3's per-section SCOPE: task_stage_costs/task_costs carry no
    window_id for non-calibrated rows (B1 finding 8б.5) and the E5
    orphan-sidechain bucket is PROJECT-WIDE by construction (B1's
    _orphan_sidechain_bucket, no time filter at all) -- these
    subsections are honestly labeled "по всей истории деплоя(ев)", not
    silently presented as window-scoped when the underlying tables
    cannot support that scope. Only "ходы без цены" (a raw cc_usage
    query) and RUNS_WITHOUT_UNITS' cc_usage join are inherently
    time-queryable, and RUNS_WITHOUT_UNITS deliberately searches ALL
    THREE deploys' projects regardless of --deploy (run_units carries
    no project column -- narrowing to one deploy's project risks a
    FALSE "dead" verdict for a real run whose session belongs to
    another project, per _session_cost_in_span's own docstring).
  - DEFAULT_TREND_WINDOWS = 6: the K-window trend length for R4.2's own
    D-rows (a value the spec never fixes for R4.2 specifically -- only
    R4.4's *user-facing* --series flag gets an explicit example value
    of 6 in the spec's own CLI example "--series M2 --last 6"). Reusing
    that same number for R4.2's internal default keeps the two "K
    окон" surfaces consistent without inventing an unrelated constant.

given: tools/spend_model.py (B1/B2, accepted); tools/calibration_counts.py
(load_journal/analyze_journal/parse_ts -- E13 candidate form, exit-2 CLI
validation form); tools/token_usage_stats.py (н/д forms, reconfigure);
tools/usage_report.py (import_transcripts/transcript_glob/db_path);
tools/savings_report.py (print_report section-header style).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import calibration_counts as cc_counts  # noqa: E402
import spend_model as sm  # noqa: E402
from usage_report import (  # noqa: E402
    db_path as _cc_db_path,
    import_transcripts,
    transcript_glob,
)

try:  # Windows narrow-codepage consoles (command hygiene p.9, class t-408)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

DEFAULT_TOP_N = 10
DEFAULT_TREND_WINDOWS = 6  # see module docstring "JUDGMENT CALLS"
_DEPLOY_CHOICES = ("shtab", "ao3", "dog", "all")


# ========================================================================
# 1. Small generic helpers.
# ========================================================================
def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _arrow(delta) -> str:
    if delta > 0:
        return "↑"  # ↑
    if delta < 0:
        return "↓"  # ↓
    return "="


def _cc_usage_table_exists(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM cc_usage LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


# ========================================================================
# 2. Window resolution (calibrated-last / monthly-all-scope-last /
#    explicit window_id / ad-hoc --window-start/--window-end).
# ========================================================================
def _window_metric_rows(conn: sqlite3.Connection, window_id: str) -> list:
    # window_series may not exist yet (a DB that never had spend_model's
    # rebuild()/compute_window_series() run against it -- a legitimate
    # first-run state, not a crash surface); CREATE TABLE IF NOT EXISTS
    # is idempotent and cheap, matching spend_model's own convention.
    sm._ensure_schema(conn)
    return sm._query_dicts(
        conn, "SELECT * FROM window_series WHERE window_id=? ORDER BY metric_key", (window_id,)
    )


def resolve_window(conn: sqlite3.Connection, deploy: str, which: str):
    """Returns (window_id, error_or_None). which="last" resolves the
    LAST calibrated window of `deploy` (shtab/ao3/dog) or the last
    shared monthly window (deploy="all"); an explicit window_id is
    looked up directly. Absence (no windows yet / bad explicit id) is a
    named reason, never a crash/exit (E3-adjacent -- an empty/first-run
    state is legitimate)."""
    if which == "last":
        if deploy == "all":
            spec = sm.resolve_last_monthly_all_scope_window(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
        else:
            spec = sm.resolve_last_calibrated_window(conn, deploy, sm.DEPLOYS)
        if spec is None:
            return None, f"нет окон для deploy={deploy!r} (первый прогон / нет calibrated-событий)"
        window_id = spec["window_id"]
    else:
        window_id = which
    rows = _window_metric_rows(conn, window_id)
    if not rows:
        return None, f"окно {window_id!r} не найдено в window_series"
    return window_id, None


def _window_spec_for_tasks(window_row: dict) -> dict:
    """Reconstructs a spend_model-shaped window_spec (kind/deploys) from
    a window_series row (or the synthetic row this module builds for a
    custom window) purely by parsing window_id's own established
    encoding (deploy_key:calibrated:i / deploy_key:monthly:label /
    all:monthly:label, spend_model.py section 4) -- no new state."""
    wid = window_row["window_id"]
    deploy_token = wid.split(":", 1)[0]
    if ":calibrated:" in wid:
        kind = "calibrated"
    elif ":monthly:" in wid:
        kind = "monthly"
    else:
        kind = "custom"
    deploys = list(dict(sm.DEPLOYS).keys()) if deploy_token == "all" else [deploy_token]
    return {
        "window_id": wid,
        "window_start": _parse_iso(window_row.get("window_start")),
        "window_end": _parse_iso(window_row.get("window_end")),
        "partial": window_row.get("partial"),
        "kind": kind, "scope": window_row.get("scope"), "deploys": deploys,
    }


def _custom_window_metrics(conn: sqlite3.Connection, deploy: str, ws_dt, we_dt):
    """Ad-hoc --window-start/--window-end window (O2's "Переопределение
    -- --window-start/--window-end"): computed fresh via
    spend_model.compute_all_window_metrics, never persisted (no schema
    change, non-goals)."""
    deploy_keys = list(dict(sm.DEPLOYS).keys()) if deploy == "all" else [deploy]
    scope = "all" if deploy == "all" else "deploy"
    window_id = (f"custom:{deploy}:{ws_dt.isoformat() if ws_dt else 'open'}"
                 f":{we_dt.isoformat() if we_dt else 'open'}")
    window_spec = {
        "window_id": window_id, "window_start": ws_dt, "window_end": we_dt,
        "partial": 0, "kind": "custom", "scope": scope, "deploys": deploy_keys,
    }
    metrics = sm.compute_all_window_metrics(conn, window_spec, sm.DEPLOY_PROJECT, sm.DEPLOYS)
    return window_spec, metrics


def _resolve_prev_window_id(conn: sqlite3.Connection, window_row: dict):
    """Immediately preceding window_id of the SAME series (same
    deploy-token:kind prefix), ordered by window_start -- SQLite orders
    NULL first in ASC, which is exactly where the first PARTIAL
    calibrated window (window_start=NULL) belongs. A custom window_id
    (never persisted) naturally has zero matching rows -> None, no
    special-casing needed."""
    wid = window_row["window_id"]
    parts = wid.split(":", 2)
    if len(parts) < 2:
        return None
    prefix = f"{parts[0]}:{parts[1]}:"
    rows = conn.execute(
        "SELECT DISTINCT window_id, window_start FROM window_series WHERE window_id LIKE ?"
        " ORDER BY window_start",
        (prefix + "%",),
    ).fetchall()
    ids = [r[0] for r in rows]
    if wid not in ids:
        return None
    idx = ids.index(wid)
    return ids[idx - 1] if idx > 0 else None


def _series_values_for_metric(conn: sqlite3.Connection, window_id: str, mkey: str, k: int) -> list:
    parts = window_id.split(":", 2)
    prefix = f"{parts[0]}:{parts[1]}:" if len(parts) >= 2 else window_id + ":"
    rows = sm._query_dicts(
        conn,
        "SELECT window_id, window_start, value FROM window_series"
        " WHERE window_id LIKE ? AND metric_key=? ORDER BY window_start",
        (prefix + "%", mkey),
    )
    return rows[-k:] if k else rows


def _trend_arrow(values: list):
    nums = [r["value"] for r in values if r["value"] is not None]
    if len(nums) < 2:
        return "=", "н/д (недостаточно точек ряда)"
    if nums[-1] > nums[0]:
        return "↑", None
    if nums[-1] < nums[0]:
        return "↓", None
    return "=", None


def _unpriced_models_in_window(conn: sqlite3.Connection, window_row: dict) -> list:
    spec = _window_spec_for_tasks(window_row)
    projects = [p for p in (sm.DEPLOY_PROJECT.get(d) for d in spec["deploys"]) if p]
    cc_rows = sm._cc_usage_rows_in_window(conn, projects, spec["window_start"], spec["window_end"])
    return sorted({r["model"] for r in cc_rows if r["accounted_cost_usd"] is None and r["model"]})


# ========================================================================
# 3. R4.1 "окно к окну".
# ========================================================================
def _flag_for_row(mkey: str, row: dict, prev: "dict | None") -> str:
    if mkey == "D7":
        if row["value"] is None:
            return row.get("reason") or "н/д"
        cf = row.get("denominator_value")
        if cf is None:
            return "н/д (контрфакт недоступен)"
        return ("ФЛАГ: эскалация дороже прямого (контрфакт дешевле факта)"
                if row["value"] > cf else "в норме (контрфакт не дешевле факта)")
    if mkey == "D8":
        if row["value"] is None:
            return row.get("reason") or "н/д"
        return "ФЛАГ: есть ходы с молчаливым $0" if row["value"] > 0 else "чисто"
    if mkey.startswith("M10") and row.get("reason"):
        # t-428 fix-batch item 6 "мелочь": M10's own reason ALWAYS carries
        # something meaningful now (either sm.M10_CAVEAT on a real value,
        # or a genuine н/д reason on a missing one) -- surfaced in the
        # flag column since M-rows otherwise print no reason at all.
        return row["reason"]
    if mkey.startswith("M"):
        return ""  # plain metric, not a detector -- no flag formula in the spec
    # D1-D6 / D4:<tier> / D5 / D9:* -- "> X" threshold undetermined (развилка е,
    # section 5's own "первая версия ... метит флаги «ПРЕДВАРИТЕЛЬНЫЙ ПОРОГ»").
    if row["value"] is None:
        return row.get("reason") or "н/д"
    if prev is None or prev.get("value") is None:
        return "ПРЕДВАРИТЕЛЬНЫЙ ПОРОГ (первое окно, нет прошлой точки)"
    delta = row["value"] - prev["value"]
    return f"ПРЕДВАРИТЕЛЬНЫЙ ПОРОГ ({_arrow(delta)} {round(delta, 4)})"


def _r4_1_row(mkey: str, row: dict, prev: "dict | None") -> dict:
    this_v = row["value"]
    prev_v = prev["value"] if prev else None
    delta = (this_v - prev_v) if (this_v is not None and prev_v is not None) else None
    return {
        "metric": mkey, "this_window": this_v,
        "this_unpriced_turns": row.get("unpriced_turns") or 0,
        "past_window": prev_v, "past_available": prev is not None,
        "delta": delta, "flag": _flag_for_row(mkey, row, prev),
        "reason": row.get("reason"),
    }


def _skill_cost_breakdown(metric_rows: list) -> list:
    """t-428 fix-batch item 5 (fork (а) resolution): 'из них <skill>:
    $X' -- one line per run_kind='skill' M6 key ACTUALLY PRESENT in the
    window (i.e. >=1 run_units row existed for that skill this window,
    from spend_model._m6_m7_m8_m12); a skill that never ran this window
    prints NOTHING at all (not 'н/д' noise, this task's own wording --
    contrast M6 itself, whose OWN absence when the registry is entirely
    empty is a single blanket 'н/д (реестра нет)', a different case)."""
    out = []
    for r in sorted(metric_rows, key=lambda r: r["metric_key"]):
        mkey = r["metric_key"]
        if not mkey.startswith("M6:skill:"):
            continue
        out.append({"name": mkey.split(":", 2)[2], "value": r["value"], "reason": r["reason"]})
    return out


def build_r4_1(conn: sqlite3.Connection, window_row: dict, metric_rows: list) -> dict:
    prev_id = _resolve_prev_window_id(conn, window_row)
    prev_map = {r["metric_key"]: r for r in _window_metric_rows(conn, prev_id)} if prev_id else {}
    any_unpriced = any(r.get("unpriced_turns") for r in metric_rows)
    unpriced_models = _unpriced_models_in_window(conn, window_row) if any_unpriced else []
    rows = [_r4_1_row(r["metric_key"], r, prev_map.get(r["metric_key"])) for r in metric_rows]
    return {"rows": rows, "unpriced_models": unpriced_models,
            "skill_breakdown": _skill_cost_breakdown(metric_rows)}


# ========================================================================
# 4. R4.2 "ранжированные стоки".
# ========================================================================
def build_r4_2(conn: sqlite3.Connection, window_row: dict, metric_rows: list,
               top_n: int, trend_k: int) -> dict:
    spec = _window_spec_for_tasks(window_row)
    task_rows = sm._tasks_in_window(conn, spec)
    top_tasks = sm.top_n_tasks(task_rows, top_n=top_n)
    total_cost = sm._sum_optional(t["cost_usd"] for t in task_rows)

    task_lines = []
    for t in top_tasks:
        share = (t["cost_usd"] / total_cost) if (total_cost and t["cost_usd"] is not None) else None
        task_lines.append({
            "sink": f"{t['deploy']}:{t['task_id']}", "cost_usd": t["cost_usd"],
            "share": share, "detector": "rework" if t.get("rework_stages") else "",
        })

    prev_id = _resolve_prev_window_id(conn, window_row)
    prev_map = {r["metric_key"]: r for r in _window_metric_rows(conn, prev_id)} if prev_id else {}
    metric_by_key = {r["metric_key"]: r for r in metric_rows}
    detector_lines = []
    for mkey in sorted(k for k in metric_by_key if k.startswith("D")):
        row = metric_by_key[mkey]
        values = _series_values_for_metric(conn, window_row["window_id"], mkey, trend_k)
        trend, trend_reason = _trend_arrow(values)
        detector_lines.append({
            "sink": mkey, "value": row["value"], "trend": trend, "trend_reason": trend_reason,
            "detector": _flag_for_row(mkey, row, prev_map.get(mkey)),
        })
    return {"top_tasks": task_lines, "detectors": detector_lines, "total_window_cost": total_cost}


# ========================================================================
# 5. R4.3 "здоровье измерения" -- ALWAYS built (accept key 3), never
#    gated behind window resolution.
# ========================================================================
def _unparsable_candidates(deploys: list) -> dict:
    """E13 candidates (mirrors calibration_counts' own "line N: error"
    form) -- a bad line never kills the run, printed here as a
    candidate, per O3/D-0063."""
    out = {}
    for deploy_key, journal_path in deploys:
        try:
            lines = cc_counts.load_journal(journal_path)
        except OSError:
            continue
        candidates = [{"line": pl.line_no, "error": pl.parse_error} for pl in lines if pl.data is None]
        if candidates:
            out[deploy_key] = candidates
    return out


def _missing_calibrated_windows(conn: sqlite3.Connection, deploy_keys: list,
                                 pre_recompute_present: "set | None" = None) -> dict:
    """Section 2's own detector: calibrated windows the journal implies
    (fresh calibrated_windows() recompute) that had no row in
    window_series -- t-428 fix-batch item 3: `pre_recompute_present`
    (when given) is a SNAPSHOT of window_series' own distinct window_ids
    taken by the CALLER BEFORE this run's own rebuild()/
    compute_window_series() call. Without it (the pre-fix shape, still
    the fallback when this function is called directly/standalone --
    e.g. build_r4_3() called on its own in a test, without a full
    main()-style recompute having just run), this queries the LIVE
    table as-is, which main()'s own call chain ALWAYS finds fully
    populated (compute_window_series() runs unconditionally right
    before build_report()) -- meaning this section STRUCTURALLY never
    fired in the CLI's normal path (critic t-428 finding, item 3): by
    the time the report is built, the very run building it has already
    backfilled every gap. The snapshot restores real detective value:
    it reports windows that were missing AT THE START of this
    invocation (a genuine staleness signal -- e.g. this DB hadn't been
    through a spend_report run since a NEW `calibrated` event was
    logged) even though, by print time, this same run's own recompute
    has already fixed them -- see render_text's own wording for this
    "audit of the run's start state, not a live watchdog" caveat."""
    missing = {}
    deploys_map = dict(sm.DEPLOYS)
    for deploy_key in deploy_keys:
        journal_path = deploys_map.get(deploy_key)
        if not journal_path:
            continue
        try:
            lines = cc_counts.load_journal(journal_path)
        except OSError:
            continue
        cal_tss = sorted(pl.ts for pl in lines
                          if pl.data and pl.data.get("event") == "calibrated" and pl.ts)
        expected = {w["window_id"] for w in sm.calibrated_windows(deploy_key, cal_tss)}
        if pre_recompute_present is not None:
            present = {wid for wid in pre_recompute_present if wid.startswith(f"{deploy_key}:calibrated:")}
        else:
            present = {r[0] for r in conn.execute(
                "SELECT DISTINCT window_id FROM window_series WHERE window_id LIKE ?",
                (f"{deploy_key}:calibrated:%",),
            )}
        gap = sorted(expected - present)
        if gap:
            missing[deploy_key] = gap
    return missing


def snapshot_calibrated_window_ids(conn: sqlite3.Connection) -> set:
    """t-428 fix-batch item 3: called by the CLI orchestration BEFORE
    its own rebuild()/compute_window_series() call, so _missing_
    calibrated_windows (via build_r4_3/build_report) can report the
    STATE THIS RUN STARTED WITH, not the state it just produced.
    sm._ensure_schema is idempotent/cheap (CREATE TABLE IF NOT EXISTS)
    -- safe to call on a DB that has never had window_series populated
    at all yet (first-ever run, legitimately empty snapshot)."""
    sm._ensure_schema(conn)
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT window_id FROM window_series WHERE window_id LIKE '%:calibrated:%'"
    )}


def _calibration_registry_gaps(conn: sqlite3.Connection) -> dict:
    """RUNS_WITHOUT_UNITS wiring (B6, B4 handoff question -- section 6
    node B4's own docstring flagged spend_model.calibration_runs_missing_
    from_registry() as ready+tested but NOT wired into this report,
    "owns-boundary question"): reuses that function (B1/B4's already-
    tested data primitive) IN ADDITION TO the bare "реестр пуст" stub
    below -- names the SPECIFIC calibrated window(s) a deploy's journal
    attests to but the run_units registry carries no run_kind='calibration'
    row for AT ALL. Window IDs are reconstructed by mapping each
    returned (missing) ts to its TRUE position in the deploy's FULL
    ascending calibrated-ts list (calibrated_windows()'s own
    i-th-ascending-ts -> window i numbering) -- NOT by enumerating the
    (possibly PARTIAL, t-428 fix-batch item 3) `missing` subset itself:
    since spend_model.calibration_runs_missing_from_registry now
    reports PER WINDOW (not all-or-nothing), a naive
    enumerate(sorted(ts_list), start=1) over just the missing subset
    would mislabel window 2 as "window 1" whenever window 1 happened to
    be covered -- this re-derives the REAL index from the deploy's own
    full calibrated-event list instead. Searches ALL THREE deploys
    (sm.DEPLOYS), same cross-deploy scope _runs_without_units below
    already uses for its `dead` list."""
    missing = sm.calibration_runs_missing_from_registry(conn, sm.DEPLOYS)
    out = {}
    deploys_map = dict(sm.DEPLOYS)
    for deploy_key, ts_list in missing.items():
        journal_path = deploys_map.get(deploy_key)
        try:
            lines = cc_counts.load_journal(journal_path) if journal_path else []
        except OSError:
            lines = []
        full_tss = sorted(pl.ts for pl in lines
                           if pl.data and pl.data.get("event") == "calibrated" and pl.ts)
        index_by_iso = {ts.isoformat(): i for i, ts in enumerate(full_tss, start=1)}
        out[deploy_key] = [f"{deploy_key}:calibrated:{index_by_iso[ts]}"
                            for ts in ts_list if ts in index_by_iso]
    return out


def _runs_without_units(conn: sqlite3.Connection) -> dict:
    """E7: run_units table/rows absent (B4 not dispatched yet) -> the
    LITERAL reason string the spec's own "given" section names
    ("реестр пуст, метрики скиллов н/д"). Searches ALL THREE deploys'
    projects regardless of --deploy -- see module docstring's
    JUDGMENT CALLS for why (run_units carries no project column).
    `calibration_registry_gaps` (B6) is always attached alongside --
    ADDITIVE, never replaces `status`/`dead` (D-0100 minimal-risk choice:
    an existing accepted test pins `status`'s literal wording on the
    total==0 branch).

    t-428 fix-batch item 4: TWO previously-conflated classes are now
    reported SEPARATELY (never double-counted between them):
      - `dead` = genuinely мёртвый прогон -- ts_end is None (open, never
        closed) OR (session_id WAS present and the run STILL found no
        cost). This is narrower than pre-fix (which put every
        session_id-absent run here too, mislabeling a legitimate
        fallback path as "dead").
      - `no_session_id` = run_units rows with session_id absent -- these
        go through spend_model.m6_run_cost's own project-wide TIME-SPAN
        fallback (item 4's "довести до работы", spec B4) instead of an
        automatic "н/д"; listed here purely informationally (cost_value
        may be a real number OR None -- either way it is NOT folded
        into `dead`)."""
    total = conn.execute("SELECT COUNT(*) FROM run_units").fetchone()[0]
    calibration_registry_gaps = _calibration_registry_gaps(conn)
    if total == 0:
        return {"status": "реестр пуст, метрики скиллов н/д", "dead": [], "no_session_id": [],
                "calibration_registry_gaps": calibration_registry_gaps}
    all_projects = [p for p in sm.DEPLOY_PROJECT.values() if p]
    level_rows = sm._query_dicts(conn, "SELECT * FROM run_units WHERE phase IS NULL")
    dead = []
    no_session_id = []
    for lr in level_rows:
        if not lr.get("ts_end"):
            dead.append({"run_id": lr.get("run_id"), "run_kind": lr.get("run_kind"),
                         "name": lr.get("name"), "reason": "мёртвый прогон (нет run_end)"})
            continue
        m = sm.m6_run_cost(conn, all_projects, lr)
        if not lr.get("session_id"):
            no_session_id.append({"run_id": lr.get("run_id"), "run_kind": lr.get("run_kind"),
                                   "name": lr.get("name"), "cost_value": m["value"],
                                   "note": m["reason"] or sm.SESSION_ID_FALLBACK_NOTE})
            continue
        if m["value"] is None:
            dead.append({"run_id": lr.get("run_id"), "run_kind": lr.get("run_kind"),
                         "name": lr.get("name"), "reason": m["reason"]})
    return {"status": "чисто" if not dead else "есть прогоны без денег", "dead": dead,
            "no_session_id": no_session_id, "calibration_registry_gaps": calibration_registry_gaps}


def build_r4_3(conn: sqlite3.Connection, deploy: str,
                pre_recompute_calibrated_window_ids: "set | None" = None) -> dict:
    deploy_keys = list(dict(sm.DEPLOYS).keys()) if deploy == "all" else [deploy]
    projects = [p for p in (sm.DEPLOY_PROJECT.get(d) for d in deploy_keys) if p]

    section = {}

    if deploy_keys:
        placeholders = ",".join("?" for _ in deploy_keys)
        section["unattributed_sidechains"] = sm._query_dicts(
            conn,
            "SELECT deploy, task_id, cost_usd, unpriced_turns, turns FROM task_costs"
            f" WHERE task_id='<unattributed>' AND deploy IN ({placeholders})",
            deploy_keys,
        )
        section["stages_not_measurable"] = conn.execute(
            f"SELECT COUNT(*) FROM task_stage_costs WHERE measurable=0 AND deploy IN ({placeholders})",
            deploy_keys,
        ).fetchone()[0]
        section["dead_dispatches_no_transcript"] = conn.execute(
            "SELECT COUNT(*) FROM task_stage_costs WHERE measurable=1 AND turns=0"
            f" AND cost_usd IS NULL AND deploy IN ({placeholders})",
            deploy_keys,
        ).fetchone()[0]
    else:
        section["unattributed_sidechains"] = []
        section["stages_not_measurable"] = 0
        section["dead_dispatches_no_transcript"] = 0

    if projects:
        p_placeholders = ",".join("?" for _ in projects)
        section["turns_without_price_all_time"] = conn.execute(
            f"SELECT COUNT(*) FROM cc_usage WHERE accounted_cost_usd IS NULL AND project IN ({p_placeholders})",
            projects,
        ).fetchone()[0]
    else:
        section["turns_without_price_all_time"] = 0

    section["unparsable_journal_lines"] = _unparsable_candidates(
        [(k, p) for k, p in sm.DEPLOYS if k in deploy_keys]
    )
    section["missing_calibrated_windows"] = _missing_calibrated_windows(
        conn, deploy_keys, pre_recompute_calibrated_window_ids
    )
    section["runs_without_units"] = _runs_without_units(conn)
    # t-428 fix-batch item 0: raskladka witness + invariant guard, both
    # deploy/project-scoped like this section's other subsections.
    section["shared_key_split"] = sm.shared_key_health(conn, deploy_keys)
    section["agent_id_session_invariant"] = sm.agent_id_session_invariant(conn, projects)
    return section


# ========================================================================
# 6. --series (R4.4).
# ========================================================================
def build_series(conn: sqlite3.Connection, window_id: str, mkey: str, k: int) -> dict:
    values = _series_values_for_metric(conn, window_id, mkey, k)
    return {
        "metric": mkey,
        "points": [{"window_id": r["window_id"], "window_start": r["window_start"], "value": r["value"]}
                   for r in values],
    }


# ========================================================================
# 7. Orchestration + rendering.
# ========================================================================
def build_report(conn: sqlite3.Connection, deploy: str, window_which: str, compare: bool,
                  top_n: int, series_key, series_last: int,
                  ws_dt=None, we_dt=None, trend_k: int = DEFAULT_TREND_WINDOWS,
                  pre_recompute_calibrated_window_ids: "set | None" = None) -> dict:
    # R4.3 health FIRST and unconditionally -- accept key 3 ("Секция
    # здоровья печатается всегда"): a window-resolution failure below
    # must never suppress it.
    report = {"r4_3": build_r4_3(conn, deploy, pre_recompute_calibrated_window_ids)}

    if ws_dt is not None or we_dt is not None:
        window_spec, metrics = _custom_window_metrics(conn, deploy, ws_dt, we_dt)
        window_row = {
            "window_id": window_spec["window_id"],
            "window_start": ws_dt.isoformat() if ws_dt else None,
            "window_end": we_dt.isoformat() if we_dt else None,
            "partial": 0, "scope": window_spec["scope"],
        }
        metric_rows = [dict(v, metric_key=k) for k, v in sorted(metrics.items())]
        window_error = None
    else:
        window_id, window_error = resolve_window(conn, deploy, window_which)
        if window_error:
            window_row, metric_rows = None, []
        else:
            metric_rows = _window_metric_rows(conn, window_id)
            window_row = metric_rows[0]

    if window_error:
        report["window_error"] = window_error
        return report

    report.update({
        "window_id": window_row["window_id"], "window_start": window_row.get("window_start"),
        "window_end": window_row.get("window_end"), "partial": window_row.get("partial"),
        "scope": window_row.get("scope"),
    })
    if compare:
        report["r4_1"] = build_r4_1(conn, window_row, metric_rows)
    report["r4_2"] = build_r4_2(conn, window_row, metric_rows, top_n, trend_k)
    if series_key:
        report["series"] = build_series(conn, window_row["window_id"], series_key, series_last)
    return report


def _fmt_num(v, unpriced_turns=0):
    if v is None:
        return "н/д"
    r = round(v, 4)
    return f">= {r} *" if unpriced_turns else r


def render_text(report: dict, deploy: str) -> str:
    lines = [f"=== SPEND REPORT (deploy={deploy}) ==="]

    if "window_error" in report:
        lines.append(f"  окно: {report['window_error']}")
    else:
        lines.append(
            f"window_id={report['window_id']} start={report['window_start']}"
            f" end={report['window_end']} partial={report['partial']} scope={report['scope']}"
        )

        if "r4_1" in report:
            lines.append("")
            lines.append("--- R4.1 окно к окну (метрика | это окно | прошлое | дельта | флаг) ---")
            r1 = report["r4_1"]
            if not r1["rows"]:
                lines.append("  (нет метрик в окне)")
            for row in r1["rows"]:
                this_s = _fmt_num(row["this_window"], row["this_unpriced_turns"])
                past_s = _fmt_num(row["past_window"]) if row["past_available"] else "н/д (первое окно)"
                delta_s = "н/д" if row["delta"] is None else round(row["delta"], 4)
                flag_s = row["flag"] or "-"
                lines.append(f"  {row['metric']:16} {str(this_s):>16} {str(past_s):>22}"
                             f" {str(delta_s):>10}  {flag_s}")
            if r1["unpriced_models"]:
                lines.append("  * без цены в этом окне: " + ", ".join(r1["unpriced_models"]))
            if r1["skill_breakdown"]:
                lines.append("  из них по скиллам (M6, только реально прогнанные в окне):")
                for sb in r1["skill_breakdown"]:
                    val_s = _fmt_num(sb["value"]) if sb["value"] is not None else (sb["reason"] or "н/д")
                    lines.append(f"    {sb['name']}: {val_s}")

        if "r4_2" in report:
            r2 = report["r4_2"]
            lines.append("")
            lines.append(f"--- R4.2 ранжированные стоки (топ-{len(r2['top_tasks'])} задач) ---")
            if not r2["top_tasks"]:
                lines.append("  (нет ценённых задач в окне)")
            for t in r2["top_tasks"]:
                share_s = "н/д" if t["share"] is None else f"{t['share']:.1%}"
                cost_s = "н/д" if t["cost_usd"] is None else round(t["cost_usd"], 4)
                lines.append(f"  {t['sink']:32} ${str(cost_s):>10} {share_s:>8}  {t['detector'] or '-'}")
            lines.append("  -- D-строки (детекторы, тренд за K окон) --")
            if not r2["detectors"]:
                lines.append("  (нет детекторов в окне)")
            for d in r2["detectors"]:
                val_s = "н/д" if d["value"] is None else round(d["value"], 4)
                lines.append(f"  {d['sink']:16} {str(val_s):>10} тренд={d['trend']}  {d['detector'] or '-'}")

    lines.append("")
    lines.append("--- R4.3 здоровье измерения ---")
    r3 = report["r4_3"]
    lines.append("  Неатрибутированные сайдчейны (<unattributed>, по всей истории деплоя(ев)):")
    if not r3["unattributed_sidechains"]:
        lines.append("    чисто")
    for row in r3["unattributed_sidechains"]:
        lines.append(f"    {row['deploy']}: cost={row['cost_usd']} turns={row['turns']}"
                     f" unpriced_turns={row['unpriced_turns']}")
    lines.append(f"  Стадии без формы agent:<id> (measurable=0, вся история): "
                 f"{r3['stages_not_measurable']}" + ("" if r3['stages_not_measurable'] else " -- чисто"))
    lines.append(f"  Мёртвые диспатчи (форма agent: есть, транскрипт не найден): "
                 f"{r3['dead_dispatches_no_transcript']}"
                 + ("" if r3['dead_dispatches_no_transcript'] else " -- чисто"))
    lines.append(f"  Ходы без цены (вся история деплоя(ев)): {r3['turns_without_price_all_time']}"
                 + ("" if r3['turns_without_price_all_time'] else " -- чисто"))
    lines.append("  Непарсящиеся строки журнала (кандидат, E13):")
    if not r3["unparsable_journal_lines"]:
        lines.append("    чисто")
    for dep, cands in r3["unparsable_journal_lines"].items():
        for c in cands:
            lines.append(f"    {dep} line {c['line']}: {c['error']}")
    lines.append("  Пропущенные окна (calibrated-окна, не имевшие строк window_series"
                 " ДО пересчёта ЭТИМ прогоном -- аудит состояния на старте прогона,"
                 " не постоянный сторож текущего состояния БД, t-428 item 3):")
    if not r3["missing_calibrated_windows"]:
        lines.append("    чисто")
    for dep, ids in r3["missing_calibrated_windows"].items():
        lines.append(f"    {dep}: {', '.join(ids)}")
    lines.append("  RUNS_WITHOUT_UNITS:")
    rwu = r3["runs_without_units"]
    if rwu["status"] == "реестр пуст, метрики скиллов н/д":
        lines.append("    реестр пуст, метрики скиллов н/д")
    elif not rwu["dead"]:
        lines.append("    чисто")
    else:
        for d in rwu["dead"]:
            lines.append(f"    run_id={d['run_id']} {d['run_kind']}:{d['name']}: {d['reason']}")
    lines.append("  Прогоны без session_id (M6 -- фолбэк по времени всего проекта, не 'мёртвый'):")
    no_sid = rwu.get("no_session_id") or []
    if not no_sid:
        lines.append("    чисто")
    for d in no_sid:
        cost_s = "н/д" if d["cost_value"] is None else round(d["cost_value"], 4)
        lines.append(f"    run_id={d['run_id']} {d['run_kind']}:{d['name']}: cost={cost_s} ({d['note']})")
    gaps = rwu.get("calibration_registry_gaps") or {}
    if gaps:
        for dep, wids in gaps.items():
            lines.append(f"    calibrated-окно(а) без строки реестра калибровки: {dep}: {', '.join(wids)}")

    shk = r3.get("shared_key_split") or {"stages": 0, "keys": 0, "cost_usd": 0.0}
    lines.append(f"  Стадий, делящих ключ: {shk['stages']} ({shk['keys']} ключей,"
                 f" ${round(shk['cost_usd'], 4)} под раскладкой)" + ("" if shk["stages"] else " -- чисто"))
    inv = r3.get("agent_id_session_invariant") or {"violations": []}
    lines.append("  Инвариант agent_id~session (агент_id уникален в рамках session+project):")
    if not inv["violations"]:
        lines.append("    чисто (0 нарушений)")
    else:
        for v in inv["violations"]:
            lines.append(f"    ФЛАГ: agent_id={v['agent_id']} project={v['project']}"
                         f" сессий={v['sessions']}")

    if "series" in report:
        s = report["series"]
        lines.append("")
        lines.append(f"--- СЕРИЯ {s['metric']} (последние {len(s['points'])} окон) ---")
        for p in s["points"]:
            lines.append(f"  {p['window_id']} start={p['window_start']}: {p['value']}")

    return "\n".join(lines)


# ========================================================================
# 8. CLI (R4.4) -- adversarial battery validation (section 6/DoD).
# ========================================================================
def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Spend-monitoring report + CLI (B3).")
    p.add_argument("--window", default="last", help="'last' or an explicit window_id")
    p.add_argument("--compare", choices=["prev"], default=None)
    p.add_argument("--series", default=None, help="metric_key, e.g. M2")
    p.add_argument("--last", type=int, default=6, help="K windows for --series (and R4.2 trend)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--top", type=int, default=DEFAULT_TOP_N)
    p.add_argument("--out", default=None, help="write report here instead of stdout (no default file)")
    p.add_argument("--deploy", choices=list(_DEPLOY_CHOICES), default="shtab")
    p.add_argument("--window-start", default=None, help="ISO local-naive; ad-hoc window override (O2)")
    p.add_argument("--window-end", default=None, help="ISO local-naive; ad-hoc window override (O2)")
    p.add_argument("--db", default=None, help="override gateway/requests.db path (tests)")
    p.add_argument("--skip-import", action="store_true",
                    help="skip the lazy transcript import (tests/CI)")
    p.add_argument("--dashboard", action="store_true",
                    help="B6: after the text report, also (re)generate the self-contained "
                         "HTML dashboard (logs/spend/dashboard.html) -- one entry point for "
                         "\"постоянная прозрачность\" (spec fork (д))")
    return p


def main(argv=None) -> int:
    args = _build_argparser().parse_args(argv)

    if args.top <= 0:
        print(f"spend_report: --top должен быть > 0, получено {args.top}", file=sys.stderr)
        return 2

    ws_dt = we_dt = None
    if args.window_start:
        ws_dt = cc_counts.parse_ts(args.window_start)
        if ws_dt is None:
            print(f"spend_report: невалидный --window-start {args.window_start!r}"
                  " (ожидается ISO, локальное наивное время)", file=sys.stderr)
            return 2
    if args.window_end:
        we_dt = cc_counts.parse_ts(args.window_end)
        if we_dt is None:
            print(f"spend_report: невалидный --window-end {args.window_end!r}"
                  " (ожидается ISO, локальное наивное время)", file=sys.stderr)
            return 2
    if ws_dt is not None and we_dt is not None and ws_dt > we_dt:
        print(f"spend_report: --window-start {args.window_start!r} позже --window-end"
              f" {args.window_end!r} -- отказ", file=sys.stderr)
        return 2

    db_file = Path(args.db) if args.db else _cc_db_path()

    # t-428 fix-batch item 6: t0 now spans the FULL pipeline (import +
    # rebuild + compute_window_series + render [+ dashboard]) -- E11's
    # 60s threshold applies to the SUM, not just the import step; the
    # full elapsed time is printed UNCONDITIONALLY (not only when it
    # exceeds the threshold), matching "печать ПОЛНОГО времени прогона".
    t0 = time.time()
    if not args.skip_import:
        import_transcripts(transcript_glob(), db_file)

    conn = sm.connect_db(db_file)
    try:
        if not _cc_usage_table_exists(conn):
            print("spend_report: в БД нет таблицы cc_usage -- отказ (E12 precondition;"
                  " запусти import_transcripts/usage_report сначала)", file=sys.stderr)
            return 2

        # E10 loud refusal (item 6), scoped: see
        # sm.resolve_project_or_refuse_if_data_elsewhere's own docstring
        # for why this is narrower than a blanket "0 rows -> refuse"
        # (a totally-empty cc_usage table is a legitimate bootstrap/
        # first-run state, preserved by the adversarial battery's own
        # pre-existing "пустой журнал -> прогон жив" contract).
        if args.deploy != "all":
            project = sm.DEPLOY_PROJECT.get(args.deploy)
            if not sm.resolve_project_or_refuse_if_data_elsewhere(conn, project):
                return 2

        pre_recompute_calibrated_ids = snapshot_calibrated_window_ids(conn)

        sm.rebuild(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
        sm.compute_window_series(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)

        report = build_report(conn, args.deploy, args.window, bool(args.compare), args.top,
                               args.series, args.last, ws_dt, we_dt,
                               pre_recompute_calibrated_window_ids=pre_recompute_calibrated_ids)

        dashboard_path = None
        if args.dashboard:
            # Local import (not module-level): spend_dashboard.py itself
            # imports THIS module (`import spend_report as sr`) for its own
            # reuse of resolve_window/build_r4_2/build_r4_3/etc (R9) -- a
            # top-level import here would be circular. `conn` is reused
            # AS-IS (already rebuilt + compute_window_series'd above by
            # this same call) -- no second rebuild.
            import spend_dashboard
            dashboard_path = spend_dashboard.generate_dashboard(
                conn, top_n=args.top, pre_recompute_calibrated_window_ids=pre_recompute_calibrated_ids
            )
    finally:
        conn.close()

    total_elapsed = time.time() - t0
    over_note = " (>60с, E11)" if total_elapsed > 60 else ""
    print(f"spend_report: полный прогон (импорт+rebuild+window_series+рендер"
          f"{'+дашборд' if args.dashboard else ''}) занял {total_elapsed:.1f}с{over_note}",
          file=sys.stderr)

    text = (json.dumps(report, ensure_ascii=False, indent=2, default=str)
            if args.json else render_text(report, args.deploy))
    if dashboard_path is not None:
        print(f"spend_report: dashboard written to {dashboard_path}")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"spend_report: written to {out_path}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
