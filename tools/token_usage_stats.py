# -*- coding: utf-8 -*-
"""Monthly token-usage statistics -> logs/token_usage.xlsx (append-only).

Monthly window is anchored on the 14th (first transcript data on this
machine starts 2026-06-14): a window is [14.M, 14.M+1) in LOCAL time.
A window enters the table only once COMPLETED (now >= window end);
re-running is idempotent -- periods already present in the sheet are
never appended twice, and a skipped month is healed by the next run
(every completed missing window is appended, not only the last one).

Accounting is NOT a third ledger: transcript discovery, dedupe
(sessionId:requestId), the cc_usage sqlite import, the price table
(PRICES_PER_TOKEN_USD) and the cost formula are all reused from
tools/usage_report.py (subscription-contour accounting, SIBLING_MAP
axis 2). A model absent from that price table yields cost "н/д" --
never a silent $0 (Rule #1); the fix for such a model is a price row
in usage_report.py, not here.

cc_usage.ts is UTC with 'Z' (axis-2 ts-clock subclass) -- window
bucketing converts to local time before comparing dates.

Scheduled run: Windows Task Scheduler, monthly on the 14th (task
"OS-LLM token usage monthly"), command:
  <python> tools/token_usage_stats.py
The xlsx lands in the repo working tree; it is committed by the next
session's normal batch (axis 9: acceptance vs durability -- the
catch-up logic above makes a lost/uncommitted file recoverable from
transcripts at any time).
"""
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from usage_report import (  # noqa: E402
    PRICES_PER_TOKEN_USD,
    CACHE_WRITE_MULTIPLIER,
    CACHE_READ_MULTIPLIER,
    accounted_cost,
    db_path,
    _connect,
    backfill_costs,
    import_transcripts,
    transcript_glob,
)

XLSX_PATH = Path(__file__).parent.parent / "logs" / "token_usage.xlsx"
SHEET = "usage"
ANCHOR_DAY = 14
# Earliest window written to the table. cc_usage starts 2026-06-13T19:06Z
# (21:06 local) -- a ~3h tail of the very first evening (293 rows, ~30M
# tokens) that would otherwise surface as a nearly-empty "14.05-14.06"
# period row; it is deliberately excluded (operator decision 2026-08-04).
EARLIEST_WINDOW = (2026, 6)

FAMILY_ORDER = ["Haiku", "Sonnet", "Opus", "Fable"]

METHODOLOGY = [
    "Статистика использования токенов Claude Code — все проекты машины (~/.claude/projects)",
    "Как считалось:",
    "— Источник: локальные транскрипты сессий; импорт и дедупликация (sessionId:requestId), синтетические записи исключены — через tools/usage_report.py (единый учёт субскрипционного контура).",
    "— Периоды: месячные окна с 14-го по 14-е, локальное время; окно записывается после своего завершения. Пропущенный запуск лечится следующим (дописываются все недостающие завершённые окна).",
    "— Цены — API-тарифы за 1 млн токенов из PRICES_PER_TOKEN_USD (usage_report.py): Haiku 4.5 $1/$5, Sonnet $3/$15, Opus $5/$25, Fable $10/$50 (input/output).",
    f"— Стоимость = input×Pin + output×Pout + cache_write×Pin×{CACHE_WRITE_MULTIPLIER} + cache_read×Pin×{CACHE_READ_MULTIPLIER}. Это оценка «сколько стоил бы тот же объём по API-ценам», а не биллинг подписки.",
    "— Модель без известной цены даёт «н/д» в столбце стоимости (никогда молчаливый $0); фикс — строка цены в usage_report.py.",
    "— Данные начинаются с 2026-06-13 21:06 (локальное); хвост вечера 13.06 (293 ответа, ~30 млн токенов) не образует полного окна и в таблицу не входит.",
]

HEADER = ["Период", "Модель", "Запросов", "Input", "Output", "Cache write",
          "Cache read", "Токены всего", "Стоимость по API, $"]


def family(model: str) -> str:
    m = (model or "").lower()
    if "fable" in m or "mythos" in m:
        return "Fable"
    if "opus" in m:
        return "Opus"
    if "sonnet" in m:
        return "Sonnet"
    if "haiku" in m:
        return "Haiku"
    return model or "unknown"


def parse_ts_local(s: str):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return None


def window_of(dt):
    """(start_y, start_m) of the [14.M, 14.M+1) window containing dt (local)."""
    if dt.day >= ANCHOR_DAY:
        return dt.year, dt.month
    return (dt.year - 1, 12) if dt.month == 1 else (dt.year, dt.month - 1)


def window_label(wy, wm):
    ey, em = (wy + 1, 1) if wm == 12 else (wy, wm + 1)
    return f"14.{wm:02d}.{wy}-14.{em:02d}.{ey}"


def window_end_dt(wy, wm):
    ey, em = (wy + 1, 1) if wm == 12 else (wy, wm + 1)
    return datetime(ey, em, ANCHOR_DAY).astimezone()


def aggregate(conn):
    """{(wy, wm): {family: {model: token-counters}}} from cc_usage."""
    agg = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    rows = conn.execute(
        "SELECT ts, model, input_tokens, output_tokens,"
        " cache_creation_tokens, cache_read_tokens FROM cc_usage"
    )
    for ts, model, inp, out, cw, cr in rows:
        dt = parse_ts_local(ts)
        if dt is None or not model:
            continue
        a = agg[window_of(dt)][family(model)][model]
        a["requests"] += 1
        a["input"] += inp or 0
        a["output"] += out or 0
        a["cache_write"] += cw or 0
        a["cache_read"] += cr or 0
    return agg


def family_rows(label, families):
    """Excel rows for one period: one per family (known order first) + total."""
    rows = []
    total = defaultdict(int)
    total_cost, cost_known = 0.0, True
    fams = [f for f in FAMILY_ORDER if f in families] + \
           [f for f in sorted(families) if f not in FAMILY_ORDER]
    for fam in fams:
        f_sum = defaultdict(int)
        f_cost, f_known, unpriced = 0.0, True, []
        for model, a in families[fam].items():
            for k in ("requests", "input", "output", "cache_write", "cache_read"):
                f_sum[k] += a[k]
            cost, _w = accounted_cost(model, a["input"], a["output"],
                                      a["cache_write"], a["cache_read"])
            if cost is None:
                f_known = False
                unpriced.append(model)
            else:
                f_cost += cost
        tokens = f_sum["input"] + f_sum["output"] + f_sum["cache_write"] + f_sum["cache_read"]
        cost_cell = round(f_cost, 2) if f_known else "н/д (нет цены: %s)" % ", ".join(unpriced)
        rows.append([label, fam, f_sum["requests"], f_sum["input"], f_sum["output"],
                     f_sum["cache_write"], f_sum["cache_read"], tokens, cost_cell])
        for k in f_sum:
            total[k] += f_sum[k]
        if f_known:
            total_cost += f_cost
        else:
            cost_known = False
    tokens = total["input"] + total["output"] + total["cache_write"] + total["cache_read"]
    rows.append([label, "ИТОГО", total["requests"], total["input"], total["output"],
                 total["cache_write"], total["cache_read"], tokens,
                 round(total_cost, 2) if cost_known else f">= {round(total_cost, 2)} (есть модели без цены)"])
    return rows


def open_or_create_workbook():
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font
    if XLSX_PATH.exists():
        wb = load_workbook(XLSX_PATH)
        return wb, wb[SHEET]
    XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET
    for line in METHODOLOGY:
        ws.append([line])
    ws.append([])
    ws.append(HEADER)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
    ws[1][0].font = Font(bold=True, size=12)
    widths = [22, 26, 10, 12, 12, 14, 16, 16, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(64 + i)].width = w
    return wb, ws


def existing_periods(ws):
    return {row[0].value for row in ws.iter_rows(min_row=1) if row[0].value}


def main():
    imported, sessions, warnings = import_transcripts(transcript_glob(), db_path())
    print(f"imported {imported} new rows from {len(sessions)} sessions")
    conn = _connect(db_path())
    try:
        backfilled = backfill_costs(conn)
        conn.commit()
        if backfilled:
            print(f"backfilled costs for {backfilled} rows")
        agg = aggregate(conn)
    finally:
        conn.close()
    for w in warnings:
        print(w)

    wb, ws = open_or_create_workbook()
    present = existing_periods(ws)
    now = datetime.now().astimezone()
    appended = []
    from openpyxl.styles import Font
    for wkey in sorted(agg):
        label = window_label(*wkey)
        if wkey < EARLIEST_WINDOW or label in present or window_end_dt(*wkey) > now:
            continue  # pre-history tail, already recorded, or window not finished
        for row in family_rows(label, agg[wkey]):
            ws.append(row)
            if row[1] == "ИТОГО":
                for cell in ws[ws.max_row]:
                    cell.font = Font(bold=True)
            for cell in ws[ws.max_row][2:8]:
                cell.number_format = "#,##0"
        appended.append(label)
    if appended:
        wb.save(XLSX_PATH)
        print(f"appended periods: {', '.join(appended)} -> {XLSX_PATH}")
    else:
        print("no new completed periods to append")


if __name__ == "__main__":
    main()
