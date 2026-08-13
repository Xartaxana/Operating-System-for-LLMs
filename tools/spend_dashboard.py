"""tools/spend_dashboard.py -- self-contained HTML spend dashboard (B6,
docs/tasks/2026-08-13_spend-analytics.md section 8 fork (д), node B6/N10).

WHAT THIS MODULE DOES (nothing more -- formulas/schema are B1/B2's
tools/spend_model.py, the four report forms are B3's tools/spend_report.py;
this module only READS window_series/task_costs/task_stage_costs/run_units/
cc_usage (SELECT-only, E12) via spend_model's/spend_report's own already-
tested functions and RENDERS one standalone HTML file):
  1. Zero external dependencies: inline <svg> line/bar charts, inline
     <style>, no CDN/JS libraries -- SVG <title> children give native
     browser tooltips, no vanilla JS needed at all.
  2. Six sections, one per operator-decided composition (fork (д),
     spec section 8):
       (а) build_stat_tile_group x2  -- last calibrated window (shtab) +
           last monthly all-scope window: $ окна / Σ M10 by tier /
           M4 (+M4b by model) / D5, each with a delta arrow vs the prior
           window of the SAME series.
       (б) build_trends            -- SVG line charts over the last K
           windows (--k, default 6): M1, M2, M4b:<model>, M10:<tier>, D5.
           A NULL point breaks the line (gap), never renders as 0.
       (в) build_sinks             -- horizontal bar chart of
           spend_model.top_n_tasks (stages/rework/critic columns) +
           the window's D-rows with spend_report's own flag/trend text.
       (г) build_monthly_report_table -- token_usage_stats' own
           aggregate()/_sum_group() (the SAME methodology numbers as
           logs/token_usage.xlsx), per project (shtab/ao3/dog) for the
           last COMPLETED monthly window, plus a convergence verdict
           against spend_model.convergence_check (spec delta (з) point 5).
       (д) health                  -- spend_report.build_r4_3(conn, "all")
           reused verbatim (same data as the text report's R4.3), plus
           the RUNS_WITHOUT_UNITS wiring spend_report.py now carries
           (calibration_registry_gaps).
       (е) header                  -- window dates, generated-at,
           `git rev-parse --short HEAD` (read-only subprocess).
  3. generate_dashboard(conn, ...) is a PURE RENDER: it assumes the
     caller already ran spend_model.rebuild()+compute_window_series()
     (spend_report.py's --dashboard flag reuses the SAME conn right
     after its own text-report rebuild -- no double rebuild). main()
     below is the STANDALONE orchestration entry point (lazy import +
     rebuild + compute, mirroring spend_report.main()'s own shape) for
     `python tools/spend_dashboard.py` used on its own.

given: tools/spend_model.py (B1/B2, accepted, NOT edited -- imported
only); tools/spend_report.py (B3, accepted -- resolve_window/
_window_metric_rows/_resolve_prev_window_id/_series_values_for_metric/
build_r4_2/build_r4_3/_flag_for_row/_arrow/_fmt_num/_window_spec_for_tasks
reused wholesale, R9, instead of re-deriving window/series/flag logic a
second time); tools/token_usage_stats.py (aggregate/_sum_group/window_of/
window_label/window_end_dt -- the monthly-report METHODOLOGY table (г)
must show the SAME numbers token_usage_stats itself would write to
logs/token_usage.xlsx, so it reuses that module's own functions rather
than spend_model's independent reimplementation, which is used only for
the convergence CHECK column, never for the displayed numbers
themselves); tools/usage_report.py (import_transcripts/transcript_glob/
db_path, mirroring spend_report.main()'s own lazy-import shape).

JUDGMENT CALLS (documented, not silently decided -- same convention
B1/B2/B3 used for their own):
  - "M10 суммарно" (spec section 8 fork (д) operator wording) has no
    single-scalar metric in window_series (M10 is written per TIER as
    M10:<tier> rows, B2's own judgment call) -- this tile SUMS every
    non-None M10:<tier>/bare-M10 value present in the window, labeled
    "Σ M10 по ярусам (приближение)" so the approximation is visible,
    never silently presented as a single precise metric.
  - Stat tiles are built for BOTH windows the spec names ("последнего
    calibrated-окна штаба + monthly all-scope") -- two independent tile
    GROUPS, not one merged group, since the spec lists both windows
    explicitly rather than picking one.
  - The monthly report table's convergence column reuses
    spend_model.convergence_check per project, matched to the SAME
    calendar window label build_monthly_report_table itself picked (the
    latest completed window across ALL cc_usage rows of any project,
    tus.window_end_dt-bounded) -- a project with zero rows that window
    or with an unpriced model in it gets an explicit "н/д" reason, never
    folded into "нет"/"да".
  - No vanilla JS is used (spec: "допустим, не обязателен") -- native
    SVG <title> elements already give hover tooltips in every browser,
    so adding JS would be an unforced dependency for zero gain.
"""
from __future__ import annotations

import argparse
import html as html_mod
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

_TOOLS_DIR = str(Path(__file__).resolve().parent)
if _TOOLS_DIR not in sys.path:
    sys.path.insert(0, _TOOLS_DIR)

import spend_model as sm  # noqa: E402
import spend_report as sr  # noqa: E402
import token_usage_stats as tus  # noqa: E402
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

DEFAULT_K = 6
DEFAULT_TOP_N = 10
DASHBOARD_PATH = sm.REPO_ROOT / "logs" / "spend" / "dashboard.html"

_NO_DATA = "данных нет"


def _esc(v) -> str:
    return html_mod.escape("" if v is None else str(v))


# ========================================================================
# 1. Small helpers.
# ========================================================================
def _git_short_rev() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(sm.REPO_ROOT), capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"н/д (git недоступен: {exc})"
    if proc.returncode != 0:
        return "н/д (git rev-parse завершился с ошибкой)"
    return (proc.stdout or "").strip() or "н/д"


def _metric_row(metric_rows: list, key: str):
    return next((r for r in metric_rows if r["metric_key"] == key), None)


def _m10_summed(metric_rows: list):
    rows = [r for r in metric_rows if r["metric_key"] == "M10" or r["metric_key"].startswith("M10:")]
    valued = [r["value"] for r in rows if r["value"] is not None]
    if not valued:
        reason = rows[0]["reason"] if rows else "нет данных M10 в окне"
        return None, reason
    return sum(valued), None


def _build_tile(label: str, value, prev_value, reason=None, is_share: bool = False) -> dict:
    if value is None:
        delta_display = "н/д"
        arrow = "="
    elif prev_value is None:
        delta_display = "н/д (нет прошлой точки)"
        arrow = "="
    else:
        delta = value - prev_value
        arrow = sr._arrow(delta)
        delta_display = f"{delta:+.1%}" if is_share else f"{delta:+.4f}"
    value_display = "н/д" if value is None else (f"{value:.1%}" if is_share else f"{value:.4f}")
    return {"label": label, "value_display": value_display, "delta_display": delta_display,
            "arrow": arrow, "reason": reason, "extra": []}


# ========================================================================
# 2. (а) STAT TILES.
# ========================================================================
def build_stat_tile_group(conn: sqlite3.Connection, window_row, metric_rows: list, group_label: str) -> dict:
    if window_row is None:
        return {"label": group_label, "window_id": None, "tiles": [], "reason": _NO_DATA}

    prev_id = sr._resolve_prev_window_id(conn, window_row)
    prev_rows = sr._window_metric_rows(conn, prev_id) if prev_id else []
    tiles = []

    m4 = _metric_row(metric_rows, "M4")
    prev_m4 = _metric_row(prev_rows, "M4")
    window_cost = m4["denominator_value"] if m4 else None
    prev_window_cost = prev_m4["denominator_value"] if prev_m4 else None
    tiles.append(_build_tile(
        "$ окна", window_cost, prev_window_cost,
        reason=(m4["reason"] if (m4 and window_cost is None) else (None if m4 else "нет данных M4"))))

    m10_sum, m10_reason = _m10_summed(metric_rows)
    prev_m10_sum, _r = _m10_summed(prev_rows) if prev_rows else (None, None)
    tiles.append(_build_tile("$/принятую (Σ M10 по ярусам, приближение)", m10_sum, prev_m10_sum, reason=m10_reason))

    m4_share = m4["value"] if m4 else None
    prev_m4_share = prev_m4["value"] if prev_m4 else None
    m4_reason = m4["reason"] if (m4 and m4_share is None) else (None if m4 else "нет данных M4")
    m4b_rows = sorted((r for r in metric_rows if r["metric_key"].startswith("M4b:")),
                       key=lambda r: r["metric_key"])
    m4_tile = _build_tile("доля координатора (M4)", m4_share, prev_m4_share, reason=m4_reason, is_share=True)
    m4_tile["extra"] = [{"label": r["metric_key"].split(":", 1)[1], "value": r["value"], "reason": r["reason"]}
                         for r in m4b_rows]
    tiles.append(m4_tile)

    d5 = _metric_row(metric_rows, "D5")
    prev_d5 = _metric_row(prev_rows, "D5")
    d5_val = d5["value"] if d5 else None
    prev_d5_val = prev_d5["value"] if prev_d5 else None
    d5_reason = d5["reason"] if (d5 and d5_val is None) else (None if d5 else "нет данных D5")
    tiles.append(_build_tile("cache-read share (D5)", d5_val, prev_d5_val, reason=d5_reason, is_share=True))

    return {"label": group_label, "window_id": window_row["window_id"], "tiles": tiles, "reason": None}


# ========================================================================
# 3. (б) TRENDS.
# ========================================================================
def _distinct_metric_keys_for_prefix(conn: sqlite3.Connection, window_id: str, prefix: str) -> list:
    parts = window_id.split(":", 2)
    wprefix = f"{parts[0]}:{parts[1]}:" if len(parts) >= 2 else window_id + ":"
    rows = conn.execute(
        "SELECT DISTINCT metric_key FROM window_series WHERE window_id LIKE ? AND metric_key LIKE ?",
        (wprefix + "%", prefix + ":%"),
    ).fetchall()
    return sorted(r[0] for r in rows)


def build_trends(conn: sqlite3.Connection, window_row, k: int) -> dict:
    if window_row is None:
        return {"charts": [], "reason": _NO_DATA}
    window_id = window_row["window_id"]
    charts = []
    for mkey, title in (("M1", "M1 переключений/принятую"), ("M2", "M2 $/переключение"), ("D5", "D5 cache-read share")):
        series = sr._series_values_for_metric(conn, window_id, mkey, k)
        charts.append({"title": title, "lines": [{"label": mkey, "points": series}]})
    for prefix, title in (("M4b", "M4b по моделям (main-chain)"), ("M10", "M10 по ярусам")):
        keys = _distinct_metric_keys_for_prefix(conn, window_id, prefix)
        lines = []
        for mkey in keys:
            series = sr._series_values_for_metric(conn, window_id, mkey, k)
            suffix = mkey.split(":", 1)[1] if ":" in mkey else mkey
            lines.append({"label": suffix, "points": series})
        charts.append({"title": title, "lines": lines})
    return {"charts": charts, "reason": None}


# ========================================================================
# 4. (в) SINKS.
# ========================================================================
def build_sinks(conn: sqlite3.Connection, window_row, metric_rows: list, top_n: int, k: int) -> dict:
    if window_row is None:
        return {"top_tasks": [], "detectors": [], "reason": _NO_DATA}
    spec = sr._window_spec_for_tasks(window_row)
    task_rows = sm._tasks_in_window(conn, spec)
    top_tasks = sm.top_n_tasks(task_rows, top_n=top_n)
    r2 = sr.build_r4_2(conn, window_row, metric_rows, top_n=top_n, trend_k=k)
    return {"top_tasks": top_tasks, "detectors": r2["detectors"], "reason": None}


# ========================================================================
# 5. (г) MONTHLY REPORT TABLE -- token_usage_stats' own methodology.
# ========================================================================
def build_monthly_report_table(conn: sqlite3.Connection, now=None) -> dict:
    # Two clock conventions collide here (SIBLING_MAP axis 2's own
    # ts-clock subclass, E1): tus.window_end_dt() returns a TZ-AWARE
    # local datetime, while spend_model.convergence_check/_monthly_bounds
    # work in LOCAL NAIVE (E1's own normalization target). Normalize
    # whatever `now` arrives as (None, naive, or already aware) into
    # BOTH forms once, here, rather than letting either callee raise
    # "can't compare offset-naive and offset-aware datetimes".
    now_aware = (now or datetime.now()).astimezone()
    now_naive = now_aware.replace(tzinfo=None)
    by_family, by_project, period_sessions = tus.aggregate(conn)
    candidates = [wk for wk in period_sessions if tus.window_end_dt(*wk) <= now_aware]
    if not candidates:
        return {"window_label": None, "projects": [], "convergence": {}, "overall": "н/д (нет завершённых окон)"}
    wkey = max(candidates)
    label = tus.window_label(*wkey)

    projects_out = []
    convergence = {}
    for deploy_key in ("shtab", "ao3", "dog"):
        project = sm.DEPLOY_PROJECT.get(deploy_key)
        group = by_project.get(wkey, {}).get(project) if project else None
        model_rows = []
        if group:
            for model in sorted(group["models"]):
                a = group["models"][model]
                cost, _w = tus.accounted_cost(model, a["input"], a["output"], a["cache_write"], a["cache_read"])
                model_rows.append({"model": model, "requests": a["requests"], "input": a["input"],
                                    "output": a["output"], "cache_write": a["cache_write"],
                                    "cache_read": a["cache_read"], "cost": cost})
            s, total_cost, unpriced = tus._sum_group(group)
            totals = {"requests": s["requests"], "input": s["input"], "output": s["output"],
                       "cache_write": s["cache_write"], "cache_read": s["cache_read"],
                       "cost": (None if unpriced else total_cost), "unpriced_models": unpriced}
        else:
            totals = {"requests": 0, "input": 0, "output": 0, "cache_write": 0, "cache_read": 0,
                      "cost": None, "unpriced_models": []}
        projects_out.append({"deploy": deploy_key, "project": project, "models": model_rows, "totals": totals})

        conv_rows = sm.convergence_check(conn, project, now_naive) if project else []
        match_row = next((r for r in conv_rows if r["window"] == label), None)
        if match_row is not None:
            convergence[deploy_key] = "да" if match_row["match"] else "нет"
        elif totals["unpriced_models"]:
            convergence[deploy_key] = "н/д (модели без цены)"
        elif not group:
            convergence[deploy_key] = "н/д (нет трат в окне)"
        else:
            convergence[deploy_key] = "н/д"

    if any(v == "нет" for v in convergence.values()):
        overall = "нет"
    elif convergence and all(v == "да" for v in convergence.values()):
        overall = "да"
    else:
        overall = "н/д (не все деплои сравнимы)"

    return {"window_label": label, "projects": projects_out, "convergence": convergence, "overall": overall}


# ========================================================================
# 6. Top-level data assembly + HTML rendering.
# ========================================================================
def build_dashboard_data(conn: sqlite3.Connection, k: int = DEFAULT_K, top_n: int = DEFAULT_TOP_N, now=None) -> dict:
    now = now or datetime.now()
    data = {"generated_at": now.isoformat(timespec="seconds"), "git_rev": _git_short_rev()}

    cal_window_id, cal_err = sr.resolve_window(conn, "shtab", "last")
    cal_metric_rows = sr._window_metric_rows(conn, cal_window_id) if cal_window_id else []
    cal_window_row = cal_metric_rows[0] if cal_metric_rows else None

    monthly_window_id, monthly_err = sr.resolve_window(conn, "all", "last")
    monthly_metric_rows = sr._window_metric_rows(conn, monthly_window_id) if monthly_window_id else []
    monthly_window_row = monthly_metric_rows[0] if monthly_metric_rows else None

    group_cal = build_stat_tile_group(conn, cal_window_row, cal_metric_rows, "Последнее calibrated-окно (shtab)")
    if cal_err and group_cal["reason"] is None:
        group_cal["reason"] = cal_err
    group_monthly = build_stat_tile_group(conn, monthly_window_row, monthly_metric_rows,
                                           "Последнее monthly-окно (все деплои)")
    if monthly_err and group_monthly["reason"] is None:
        group_monthly["reason"] = monthly_err
    data["stat_tiles"] = [group_cal, group_monthly]

    data["trends"] = build_trends(conn, cal_window_row, k)
    data["sinks"] = build_sinks(conn, cal_window_row, cal_metric_rows, top_n, k)
    data["monthly_table"] = build_monthly_report_table(conn, now)
    data["health"] = sr.build_r4_3(conn, "all")
    data["window_dates"] = {
        "calibrated": {"window_id": cal_window_id,
                        "start": cal_window_row.get("window_start") if cal_window_row else None,
                        "end": cal_window_row.get("window_end") if cal_window_row else None,
                        "error": cal_err},
        "monthly": {"window_id": monthly_window_id,
                    "start": monthly_window_row.get("window_start") if monthly_window_row else None,
                    "end": monthly_window_row.get("window_end") if monthly_window_row else None,
                    "error": monthly_err},
    }
    return data


# ------------------------------------------------------------------
# SVG chart rendering.
# ------------------------------------------------------------------
_COLORS = ["#7fd1ff", "#ffb37f", "#b3ff7f", "#ff7fd1", "#ffe97f", "#7fffe0", "#c8a2ff", "#ff9a9a"]


def _svg_line_chart(chart: dict, width: int = 560, height: int = 170, pad: int = 32) -> str:
    lines = chart["lines"]
    all_vals = [p["value"] for ln in lines for p in ln["points"] if p["value"] is not None]
    if not all_vals:
        return f'<div class="chart-title">{_esc(chart["title"])}</div><div class="chart-empty">{_NO_DATA}</div>'

    vmin, vmax = min(all_vals), max(all_vals)
    if vmin == vmax:
        vmin, vmax = vmin - 1, vmax + 1
    n_points = max((len(ln["points"]) for ln in lines), default=0)

    def x_for(i):
        if n_points <= 1:
            return pad + (width - 2 * pad) / 2
        return pad + i * (width - 2 * pad) / (n_points - 1)

    def y_for(v):
        return height - pad - (v - vmin) / (vmax - vmin) * (height - 2 * pad)

    parts = [f'<svg viewBox="0 0 {width} {height}" class="trend-svg" role="img" '
             f'aria-label="{_esc(chart["title"])}"><title>{_esc(chart["title"])}</title>']
    for li, ln in enumerate(lines):
        color = _COLORS[li % len(_COLORS)]
        segments, segment = [], []
        for i, p in enumerate(ln["points"]):
            if p["value"] is None:
                if segment:
                    segments.append(segment)
                    segment = []
                continue
            segment.append((x_for(i), y_for(p["value"]), p))
        if segment:
            segments.append(segment)
        for seg in segments:
            if len(seg) == 1:
                x, y, p = seg[0]
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}">'
                              f'<title>{_esc(ln["label"])} {_esc(p["window_id"])}: {p["value"]}</title></circle>')
            else:
                pts = " ".join(f"{x:.1f},{y:.1f}" for x, y, _p in seg)
                parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
                for x, y, p in seg:
                    parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{color}">'
                                  f'<title>{_esc(ln["label"])} {_esc(p["window_id"])}: {p["value"]}</title></circle>')
    parts.append("</svg>")
    legend = " ".join(f'<span class="legend-item" style="color:{_COLORS[i % len(_COLORS)]}">&#9632; {_esc(ln["label"])}</span>'
                       for i, ln in enumerate(lines))
    return (f'<div class="chart-title">{_esc(chart["title"])}</div>' + "".join(parts)
            + f'<div class="legend">{legend}</div>')


def _svg_bar_chart(top_tasks: list, width: int = 640, row_h: int = 26, pad_left: int = 230) -> str:
    if not top_tasks:
        return f'<div class="chart-empty">{_NO_DATA} (нет ценённых задач в окне)</div>'
    max_cost = max((t["cost_usd"] or 0) for t in top_tasks) or 1.0
    height = row_h * len(top_tasks) + 10
    parts = [f'<svg viewBox="0 0 {width} {height}" class="bar-svg" role="img" aria-label="топ задач по стоимости">']
    for i, t in enumerate(top_tasks):
        y = i * row_h + 5
        cost = t["cost_usd"] or 0.0
        bw = (cost / max_cost) * (width - pad_left - 20)
        label = f"{t['deploy']}:{t['task_id']}"
        title = (f"{label}: ${cost:.4f} stages={t['stages']} rework={t['rework_stages']} "
                 f"critic={t['critic_entries']} accepted={t['accepted']}")
        parts.append(f'<text x="0" y="{y + 15}" class="bar-label">{_esc(label)}</text>')
        parts.append(f'<rect x="{pad_left}" y="{y}" width="{max(bw, 1):.1f}" height="{row_h - 6}" fill="#7fd1ff">'
                      f'<title>{_esc(title)}</title></rect>')
        parts.append(f'<text x="{pad_left + bw + 6:.1f}" y="{y + 15}" class="bar-value">'
                      f'${cost:.4f} (rework={t["rework_stages"]}, critic={t["critic_entries"]})</text>')
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------------
# Full-page HTML assembly.
# ------------------------------------------------------------------
_CSS = """
:root { color-scheme: dark; }
body { background:#12151c; color:#e8ecf3; font-family: Consolas, "Segoe UI", monospace; margin:0; padding:24px; }
h1 { font-size:1.4em; margin:0 0 4px; }
h2 { font-size:1.1em; border-bottom:1px solid #2c3444; padding-bottom:4px; margin-top:32px; }
.subtle { color:#8a93a6; font-size:0.85em; }
section { margin-bottom:28px; }
.tile-group { margin-bottom:18px; }
.tile-group-label { font-weight:bold; color:#9fd0ff; margin-bottom:8px; }
.tiles { display:flex; flex-wrap:wrap; gap:14px; }
.tile { background:#1b2130; border:1px solid #2c3444; border-radius:6px; padding:10px 14px; min-width:190px; }
.tile-label { font-size:0.8em; color:#8a93a6; }
.tile-value { font-size:1.35em; font-weight:bold; margin:4px 0; }
.tile-delta { font-size:0.85em; }
.tile-delta.up { color:#7fef9a; }
.tile-delta.down { color:#ff8a8a; }
.tile-delta.flat { color:#8a93a6; }
.tile-extra { font-size:0.78em; color:#b7c0d4; margin-top:6px; }
.chart-title { font-weight:bold; margin:14px 0 4px; color:#c8d3e8; }
.chart-empty { color:#8a93a6; font-style:italic; padding:8px 0; }
.trend-svg, .bar-svg { background:#171c27; border:1px solid #262d3d; border-radius:6px; max-width:100%; }
.legend { font-size:0.8em; margin:4px 0 12px; }
.legend-item { margin-right:12px; }
.bar-label { fill:#c8d3e8; font-size:11px; }
.bar-value { fill:#e8ecf3; font-size:11px; }
table { border-collapse:collapse; width:100%; margin:8px 0 18px; font-size:0.85em; }
th, td { border:1px solid #2c3444; padding:4px 8px; text-align:right; }
th { background:#1b2130; color:#9fd0ff; }
td:first-child, th:first-child { text-align:left; }
.verdict-da { color:#7fef9a; font-weight:bold; }
.verdict-net { color:#ff8a8a; font-weight:bold; }
.verdict-na { color:#8a93a6; }
.health-clean { color:#7fef9a; }
.health-flag { color:#ffcf7f; }
ul.health-list { margin:4px 0; padding-left:20px; }
"""


def _tile_html(t: dict) -> str:
    arrow_cls = {"↑": "up", "↓": "down", "=": "flat"}.get(t["arrow"], "flat")
    extra_html = ""
    if t["extra"]:
        row_parts = []
        for e in t["extra"]:
            v_display = "н/д" if e["value"] is None else f'{e["value"]:.4f}'
            row_parts.append(f'<div>{_esc(e["label"])}: {v_display}</div>')
        extra_html = f'<div class="tile-extra">{"".join(row_parts)}</div>'
    reason_html = f'<div class="tile-extra">{_esc(t["reason"])}</div>' if t.get("reason") else ""
    return (
        f'<div class="tile"><div class="tile-label">{_esc(t["label"])}</div>'
        f'<div class="tile-value">{_esc(t["value_display"])}</div>'
        f'<div class="tile-delta {arrow_cls}">{t["arrow"]} {_esc(t["delta_display"])}</div>'
        f'{reason_html}{extra_html}</div>'
    )


def _stat_tiles_section(groups: list) -> str:
    parts = ['<section data-section="stat-tiles"><h2>(а) Стат-плитки</h2>']
    for g in groups:
        parts.append('<div class="tile-group">')
        parts.append(f'<div class="tile-group-label">{_esc(g["label"])}'
                      f' <span class="subtle">({_esc(g["window_id"]) if g["window_id"] else "-"})</span></div>')
        if not g["tiles"]:
            parts.append(f'<div class="chart-empty">{_NO_DATA}'
                          + (f': {_esc(g["reason"])}' if g.get("reason") else "") + '</div>')
        else:
            parts.append('<div class="tiles">' + "".join(_tile_html(t) for t in g["tiles"]) + '</div>')
        parts.append('</div>')
    parts.append('</section>')
    return "".join(parts)


def _trends_section(trends: dict) -> str:
    parts = ['<section data-section="trends"><h2>(б) Тренды (SVG, разрыв линии = NULL, не ноль)</h2>']
    if trends.get("reason"):
        parts.append(f'<div class="chart-empty">{_NO_DATA}: {_esc(trends["reason"])}</div>')
    for chart in trends.get("charts", []):
        parts.append(_svg_line_chart(chart))
    parts.append('</section>')
    return "".join(parts)


def _sinks_section(sinks: dict) -> str:
    parts = ['<section data-section="sinks"><h2>(в) Стоки (топ задач + детекторы)</h2>']
    if sinks.get("reason"):
        parts.append(f'<div class="chart-empty">{_NO_DATA}: {_esc(sinks["reason"])}</div>')
    else:
        parts.append(_svg_bar_chart(sinks["top_tasks"]))
        parts.append('<table><tr><th>детектор</th><th>значение</th><th>тренд</th><th>флаг</th></tr>')
        for d in sinks["detectors"]:
            val_s = "н/д" if d["value"] is None else round(d["value"], 4)
            parts.append(f'<tr><td>{_esc(d["sink"])}</td><td>{_esc(val_s)}</td>'
                         f'<td>{_esc(d["trend"])}</td><td>{_esc(d["detector"] or "-")}</td></tr>')
        parts.append('</table>')
    parts.append('</section>')
    return "".join(parts)


def _monthly_table_section(mt: dict) -> str:
    parts = ['<section data-section="monthly-table"><h2>(г) Месячный отчёт (методика token_usage_stats)</h2>']
    if not mt.get("window_label"):
        parts.append(f'<div class="chart-empty">{_NO_DATA}: {_esc(mt.get("overall") or "нет завершённых окон")}</div>')
        parts.append('</section>')
        return "".join(parts)
    parts.append(f'<div class="subtle">окно: {_esc(mt["window_label"])}</div>')
    for proj in mt["projects"]:
        parts.append(f'<h3 style="margin-bottom:2px">{_esc(proj["deploy"])} '
                      f'<span class="subtle">({_esc(proj["project"])})</span></h3>')
        parts.append('<table><tr><th>Модель</th><th>Запросов</th><th>Input</th><th>Output</th>'
                     '<th>Cache write</th><th>Cache read</th><th>Стоимость, $</th></tr>')
        for m in proj["models"]:
            cost_s = "н/д" if m["cost"] is None else round(m["cost"], 4)
            parts.append(f'<tr><td>{_esc(m["model"])}</td><td>{m["requests"]}</td><td>{m["input"]}</td>'
                         f'<td>{m["output"]}</td><td>{m["cache_write"]}</td><td>{m["cache_read"]}</td>'
                         f'<td>{_esc(cost_s)}</td></tr>')
        t = proj["totals"]
        total_cost_s = ("н/д (нет цены: " + ", ".join(t["unpriced_models"]) + ")"
                         if t["unpriced_models"] else ("н/д" if t["cost"] is None else round(t["cost"], 4)))
        parts.append(f'<tr><td><b>ИТОГО</b></td><td>{t["requests"]}</td><td>{t["input"]}</td>'
                     f'<td>{t["output"]}</td><td>{t["cache_write"]}</td><td>{t["cache_read"]}</td>'
                     f'<td><b>{_esc(total_cost_s)}</b></td></tr>')
        parts.append('</table>')
        conv = mt["convergence"].get(proj["deploy"], "н/д")
        conv_cls = "verdict-da" if conv == "да" else ("verdict-net" if conv == "нет" else "verdict-na")
        parts.append(f'<div class="subtle">сходится с методикой месячного отчёта: '
                     f'<span class="{conv_cls}">{_esc(conv)}</span></div>')
    overall = mt.get("overall", "н/д")
    overall_cls = "verdict-da" if overall == "да" else ("verdict-net" if overall == "нет" else "verdict-na")
    parts.append(f'<div style="margin-top:8px">ОБЩАЯ строка сверки -- сходится с методикой месячного отчёта: '
                 f'<span class="{overall_cls}">{_esc(overall)}</span></div>')
    parts.append('</section>')
    return "".join(parts)


def _health_section(health: dict) -> str:
    parts = ['<section data-section="health"><h2>(д) Здоровье измерения</h2>']

    def _clean_or(rows_present: bool, body_fn):
        if not rows_present:
            parts.append('<div class="health-clean">чисто</div>')
        else:
            body_fn()

    parts.append('<div><b>Неатрибутированные сайдчейны:</b></div>')
    _clean_or(bool(health["unattributed_sidechains"]), lambda: parts.append(
        "<ul class='health-list'>" + "".join(
            f"<li>{_esc(r['deploy'])}: cost={r['cost_usd']} turns={r['turns']}</li>"
            for r in health["unattributed_sidechains"]) + "</ul>"))

    parts.append(f'<div><b>Стадии без формы agent:&lt;id&gt;:</b> {health["stages_not_measurable"]}'
                 + ('' if health['stages_not_measurable'] else ' -- <span class="health-clean">чисто</span>') + '</div>')
    parts.append(f'<div><b>Мёртвые диспатчи (без транскрипта):</b> {health["dead_dispatches_no_transcript"]}'
                 + ('' if health['dead_dispatches_no_transcript'] else ' -- <span class="health-clean">чисто</span>') + '</div>')
    parts.append(f'<div><b>Ходы без цены (вся история):</b> {health["turns_without_price_all_time"]}'
                 + ('' if health['turns_without_price_all_time'] else ' -- <span class="health-clean">чисто</span>') + '</div>')

    parts.append('<div><b>Непарсящиеся строки журнала:</b></div>')
    _clean_or(bool(health["unparsable_journal_lines"]), lambda: parts.append(
        "<ul class='health-list'>" + "".join(
            f"<li>{_esc(dep)} line {c['line']}: {_esc(c['error'])}</li>"
            for dep, cands in health["unparsable_journal_lines"].items() for c in cands) + "</ul>"))

    parts.append('<div><b>Пропущенные окна (calibrated без строк window_series):</b></div>')
    _clean_or(bool(health["missing_calibrated_windows"]), lambda: parts.append(
        "<ul class='health-list'>" + "".join(
            f"<li>{_esc(dep)}: {_esc(', '.join(ids))}</li>"
            for dep, ids in health["missing_calibrated_windows"].items()) + "</ul>"))

    rwu = health["runs_without_units"]
    parts.append('<div><b>RUNS_WITHOUT_UNITS:</b></div>')
    if rwu["status"] == "реестр пуст, метрики скиллов н/д":
        parts.append('<div class="health-flag">реестр пуст, метрики скиллов н/д</div>')
    elif not rwu["dead"]:
        parts.append('<div class="health-clean">чисто</div>')
    else:
        parts.append("<ul class='health-list'>" + "".join(
            f"<li>run_id={_esc(d['run_id'])} {_esc(d['run_kind'])}:{_esc(d['name'])}: {_esc(d['reason'])}</li>"
            for d in rwu["dead"]) + "</ul>")
    gaps = rwu.get("calibration_registry_gaps") or {}
    if gaps:
        parts.append("<div class='health-flag'>calibrated-окно(а) без строки реестра калибровки: "
                     + "; ".join(f"{_esc(dep)}: {_esc(', '.join(wids))}" for dep, wids in gaps.items())
                     + "</div>")

    parts.append('</section>')
    return "".join(parts)


def _header_section(data: dict) -> str:
    wd = data["window_dates"]
    cal = wd["calibrated"]
    monthly = wd["monthly"]
    return (
        '<section data-section="header">'
        '<h1>Spend-дашборд «агентская ОС»</h1>'
        f'<div class="subtle">generated-at: {_esc(data["generated_at"])} | '
        f'ревизия репо: {_esc(data["git_rev"])}</div>'
        f'<div class="subtle">calibrated-окно (shtab): {_esc(cal["window_id"] or (cal["error"] or "-"))} '
        f'[{_esc(cal["start"])} .. {_esc(cal["end"])}]</div>'
        f'<div class="subtle">monthly-окно (все деплои): {_esc(monthly["window_id"] or (monthly["error"] or "-"))} '
        f'[{_esc(monthly["start"])} .. {_esc(monthly["end"])}]</div>'
        '</section>'
    )


def render_html(data: dict) -> str:
    body = (
        _header_section(data)
        + _stat_tiles_section(data["stat_tiles"])
        + _trends_section(data["trends"])
        + _sinks_section(data["sinks"])
        + _monthly_table_section(data["monthly_table"])
        + _health_section(data["health"])
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru"><head><meta charset="utf-8">'
        "<title>Spend-дашборд</title>"
        f"<style>{_CSS}</style></head><body>{body}</body></html>\n"
    )


# ========================================================================
# 7. Public entry point + CLI.
# ========================================================================
def generate_dashboard(conn: sqlite3.Connection, out_path=None, k: int = DEFAULT_K,
                        top_n: int = DEFAULT_TOP_N, now=None) -> Path:
    """PURE render (SELECT-only on conn, E12) -- caller is responsible for
    conn already having a fresh rebuild()/compute_window_series() run
    against it (spend_report.py's --dashboard flag reuses its OWN prior
    call; this module's own main() below does it itself for standalone
    use)."""
    out_path = Path(out_path) if out_path else DASHBOARD_PATH
    data = build_dashboard_data(conn, k=k, top_n=top_n, now=now)
    text = render_html(data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return out_path


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Spend-monitoring self-contained HTML dashboard (B6).")
    p.add_argument("--k", type=int, default=DEFAULT_K, help="K windows for trend charts (default 6)")
    p.add_argument("--top", type=int, default=DEFAULT_TOP_N, help="top-N sinks (default 10)")
    p.add_argument("--out", default=None, help="override output path (default logs/spend/dashboard.html)")
    p.add_argument("--db", default=None, help="override gateway/requests.db path (tests)")
    p.add_argument("--skip-import", action="store_true",
                    help="skip the lazy transcript import (tests/CI)")
    return p


def main(argv=None) -> int:
    args = _build_argparser().parse_args(argv)

    if args.k <= 0:
        print(f"spend_dashboard: --k должен быть > 0, получено {args.k} (K=0 -- отказ)", file=sys.stderr)
        return 2
    if args.top <= 0:
        print(f"spend_dashboard: --top должен быть > 0, получено {args.top}", file=sys.stderr)
        return 2

    db_file = Path(args.db) if args.db else _cc_db_path()
    if not args.skip_import:
        import_transcripts(transcript_glob(), db_file)

    conn = sqlite3.connect(db_file)
    try:
        if not sr._cc_usage_table_exists(conn):
            print("spend_dashboard: в БД нет таблицы cc_usage -- отказ (E12 precondition;"
                  " запусти import_transcripts/usage_report сначала)", file=sys.stderr)
            return 2
        sm.rebuild(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
        sm.compute_window_series(conn, sm.DEPLOYS, sm.DEPLOY_PROJECT)
        out_path = generate_dashboard(conn, args.out, args.k, args.top)
    finally:
        conn.close()

    print(f"spend_dashboard: written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
