# -*- coding: utf-8 -*-
"""Экономический разрез обоих контуров для чека 18 еженедельной
калибровки (заказ оператора 2026-07-11): экономит ли система деньги,
и каков тренд.

Считает по cc_usage (субскрипционный контур) и requests (API-контур)
в gateway/requests.db, полные API-цены (list, без батча; кэш-скидки
read x0.1 / write x1.25 — реальный API-механизм):

1. Окна PRE (< --routed-start) и ROUTED (>= --routed-start [.. --until]):
   ходы, учётная стоимость, $/день, разбивка main/side по моделям.
2. Контрфакт делегирования: токен-профили routed-сайдчейнов,
   переоценённые по ценам Fable, против факта — брутто-экономия $ и %.
3. API-контур: запросы и учётная стоимость по traffic_kind.

Baseline первого замера (2026-07-11, сверка тренда):
docs/task_reports/2026-07-11_savings-analysis.md. Оговорки метода
(цензурированный baseline, нераздельность премии координации от
неделегируемой Lead-работы) записаны там же и остаются в силе.

Цены дублируют tools/usage_report.py PRICES_PER_TOKEN_USD осознанно
НЕ: импортируются оттуда — единственный владелец цен (ось 2).
"""
import argparse
import io
import sqlite3
import sys
from pathlib import Path

from usage_report import CACHE_READ_MULTIPLIER, CACHE_WRITE_MULTIPLIER, PRICES_PER_TOKEN_USD

FABLE_MODEL = "claude-fable-5"


def _cost(model: str, i: int, o: int, cw: int, cr: int):
    p = PRICES_PER_TOKEN_USD.get(model)
    if p is None:
        return None
    return (i * p[0] + o * p[1]
            + cw * p[0] * CACHE_WRITE_MULTIPLIER
            + cr * p[0] * CACHE_READ_MULTIPLIER)


def fable_counterfactual(i: int, o: int, cw: int, cr: int) -> float:
    """Тот же токен-профиль по ценам Fable — «а если бы это делал Lead»."""
    return _cost(FABLE_MODEL, i or 0, o or 0, cw or 0, cr or 0)


def window_summary(db: sqlite3.Connection, cond: str, params: tuple) -> dict:
    rows = db.execute(
        "select model, is_sidechain, count(*), sum(accounted_cost_usd),"
        " count(distinct session_id) from cc_usage where " + cond +
        " group by model, is_sidechain order by 4 desc", params).fetchall()
    days = db.execute(
        "select count(distinct substr(ts,1,10)) from cc_usage where " + cond,
        params).fetchone()[0]
    total_cost = sum(r[3] or 0 for r in rows)
    total_turns = sum(r[2] for r in rows)
    return {"rows": rows, "days": days, "total_cost": total_cost,
            "total_turns": total_turns,
            "per_day": total_cost / days if days else 0.0}


def counterfactual_summary(db: sqlite3.Connection, cond: str, params: tuple) -> dict:
    rows = db.execute(
        "select agent_type, model, count(*), sum(input_tokens), sum(output_tokens),"
        " sum(cache_creation_tokens), sum(cache_read_tokens), sum(accounted_cost_usd)"
        " from cc_usage where is_sidechain=1 and " + cond +
        " group by agent_type, model order by 8 desc", params).fetchall()
    detail = []
    actual = cf = 0.0
    for at, model, n, ti, to, tcw, tcr, cost in rows:
        f = fable_counterfactual(ti, to, tcw, tcr)
        actual += cost or 0
        cf += f
        detail.append({"agent_type": at, "model": model, "turns": n,
                       "actual": cost or 0, "as_fable": f})
    return {"detail": detail, "actual": actual, "as_fable": cf,
            "gross_savings": cf - actual,
            "savings_pct": (1 - actual / cf) * 100 if cf else 0.0}


def api_contour_summary(db: sqlite3.Connection) -> dict:
    kinds = db.execute(
        "select traffic_kind, count(*), sum(cost_usd) from requests"
        " group by traffic_kind order by 3 desc").fetchall()
    total = db.execute("select count(*), sum(cost_usd) from requests").fetchone()
    return {"kinds": kinds, "total_n": total[0], "total_cost": total[1] or 0.0}


def print_report(db_path: str, routed_start: str, until: str = None) -> None:
    db = sqlite3.connect(db_path)
    until_cond, until_params = ("", ()) if not until else (" and ts < ?", (until,))

    for label, cond, params in [
        ("PRE-ROUTING (< %s)" % routed_start, "ts < ?", (routed_start,)),
        ("ROUTED (>= %s%s)" % (routed_start, f" .. {until}" if until else ""),
         "ts >= ?" + until_cond, (routed_start,) + until_params),
    ]:
        w = window_summary(db, cond, params)
        print(f"\n===== {label} =====")
        for model, sc, n, cost, sess in w["rows"]:
            kind = "side" if sc else "main"
            print(f"  {model:28} {kind:4} turns={n:5} sess={sess:3}"
                  f" cost=${cost or 0:9.2f}  $/turn={((cost or 0) / n):.4f}")
        print(f"  ИТОГО: {w['total_turns']} ходов, ${w['total_cost']:.2f},"
              f" {w['days']} дней, ${w['per_day']:.2f}/день")

    c = counterfactual_summary(db, "ts >= ?" + until_cond,
                               (routed_start,) + until_params)
    print("\n===== КОНТРФАКТ: routed-сайдчейны по ценам Fable =====")
    for d in c["detail"]:
        print(f"  {str(d['agent_type']):16} {d['model']:28} turns={d['turns']:4}"
              f" факт=${d['actual']:8.2f} по-Fable=${d['as_fable']:8.2f}")
    print(f"  ИТОГО: факт=${c['actual']:.2f}  по-Fable=${c['as_fable']:.2f}"
          f"  брутто-экономия=${c['gross_savings']:.2f} ({c['savings_pct']:.0f}%)")

    a = api_contour_summary(db)
    print("\n===== API-КОНТУР (requests.db, вся история) =====")
    for kind, n, cost in a["kinds"]:
        print(f"  {kind:10} n={n:4} cost=${cost or 0:.4f}")
    print(f"  ИТОГО: {a['total_n']} запросов, ${a['total_cost']:.4f} учётно")

    print("\nВ notes события calibrated (чек 18): $/день ROUTED,"
          " брутто-экономия $ и %, факт сайдчейнов, API-итог;"
          " сравнить с прошлой точкой (baseline 2026-07-11:"
          " docs/task_reports/2026-07-11_savings-analysis.md).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Savings/trend report (calibration check 18)")
    ap.add_argument("--db", default=str(Path(__file__).resolve().parent.parent
                                        / "gateway" / "requests.db"))
    ap.add_argument("--routed-start", default="2026-07-08",
                    help="граница PRE/ROUTED (деплой роутинга на этом репо)")
    ap.add_argument("--until", default=None,
                    help="верхняя граница ROUTED-окна (для воспроизводимых срезов)")
    args = ap.parse_args(argv)
    print_report(args.db, args.routed_start, args.until)
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
