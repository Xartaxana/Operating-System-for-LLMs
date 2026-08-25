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
   переоценённые по цене модели, привязанной к roles.lead в
   delegation.config.yaml (резолюция -- mechanism_gate.resolve_lead_
   binding(), t-444), против факта — брутто-экономия $ и %. База
   контрфакта СМЕНЕНА 2026-08-16 (t-444): до -- зашитый id
   claude-fable-5, с -- привязка roles.lead (сегодня claude-opus-5);
   старая точка тренда воспроизводима флагом --counterfactual-model.
3. API-контур: запросы и учётная стоимость по traffic_kind.

--window-start/--window-end (M3, docs/tasks/2026-08-25_wave2-misc-spec.md,
F15-ii): сужают выборку учитываемых событий (PRE/ROUTED/контрфакт, п.1-2
выше) до окна [window-start, window-end) поверх существующих условий;
--routed-start остаётся базой PRE/ROUTED-разреза и контрфакта, окно её
не переопределяет. API-контур (п.3) остаётся "вся история", окном не
режется. Без обоих флагов -- вывод байт-в-байт как раньше.

Baseline первого замера (2026-07-11, сверка тренда):
docs/task_reports/2026-07-11_savings-analysis.md. Оговорки метода
(цензурированный baseline, нераздельность премии координации от
неделегируемой Lead-работы) записаны там же и остаются в силе.

Цены дублируют tools/usage_report.py PRICES_PER_TOKEN_USD осознанно
НЕ: импортируются оттуда — единственный владелец цен (ось 2).
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from usage_report import CACHE_READ_MULTIPLIER, CACHE_WRITE_MULTIPLIER, PRICES_PER_TOKEN_USD

# Резолюция привязки Lead (t-444, R-3): единственный носитель --
# mechanism_gate.resolve_lead_binding(); переиспользуем его, своего
# резолвера/таблицы "семейство->id" не заводим (R-1/R-4). Защищённый
# импорт -- та же форма, что tools/journal_validator.py:262-265
# (mg=None -> резолюция недоступна, ветка R-5 без TypeError, а не
# падение всего модуля на PyYAML): savings_report импортируется
# tools/spend_model.py на верхнем уровне, падение здесь уронило бы
# весь tools-прогон, не только контрфакт.
try:
    import mechanism_gate as mg
except ImportError:
    mg = None

# Оба потока: отчёт печатает кириллицу в stdout (заголовки секций, ИТОГО);
# без reconfigure Windows-консоль искажает её (класс найден в AO3-твине,
# их задача e4-impact-selection 2026-07-14; ось 1 SIBLING_MAP -- фикс парный,
# эталон -- tools/mechanism_gate.py). errors="replace" (порт AO3 «Мелкое
# хозяйство» п.1, 2026-07-18): голый encoding="utf-8" оставлял
# errors="strict" -- replace убирает последний шанс ValueError на
# повторной кодировке без потери диагностируемости (отчёт печатает текст,
# не бинарные данные). Заменяет прежний ad hoc `sys.stdout =
# io.TextIOWrapper(...)` под `if __name__ == "__main__":` -- тот чинил
# только stdout, только при прямом запуске скриптом (не при импорте
# модуля), и без errors="replace" (голый strict); оставлять оба
# механизма разом было бы конфликтом: TextIOWrapper без errors="replace"
# СНАЧАЛА переопределил бы sys.stdout заново на strict, отменяя эффект
# reconfigure ниже -- один канонический механизм, тот же, что и везде
# по SIBLING_MAP ось 1.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _cost(model: str, i: int, o: int, cw: int, cr: int):
    p = PRICES_PER_TOKEN_USD.get(model)
    if p is None:
        return None
    return (i * p[0] + o * p[1]
            + cw * p[0] * CACHE_WRITE_MULTIPLIER
            + cr * p[0] * CACHE_READ_MULTIPLIER)


# Сентинел "config_text не передан явно" (R-2) -- та же форма, что
# tools/journal_validator.py:311-317 / tools/session_context.py:609-617
# (D-0099): явный YAML-текст -> резолвится он; явный None -> "конфига
# нет"; сентинел (обычные вызовы) -> ленивое кэшированное чтение
# mg.CONFIG_PATH один раз за процесс. Позиционный инвариант (R-2):
# резолюция -- НА ВЫЗОВЕ или лениво при ПЕРВОМ вызове, никогда на
# импорте модуля -- импорт savings_report обязан остаться свободным от
# чтения диска / требования PyYAML (на нём стоит верхнеуровневый импорт
# tools/spend_model.py и весь tools-прогон).
_CONFIG_TEXT_UNSET = object()
_cached_real_config_text = _CONFIG_TEXT_UNSET


def _read_real_config_text() -> str | None:
    """Ленивое кэшированное чтение REPO/delegation.config.yaml -- та же
    форма, что tools/journal_validator.py:_read_real_config_text()
    (mg is None -> None без чтения, ветка R-5 без попытки резолюции)."""
    global _cached_real_config_text
    if mg is None:
        return None
    if _cached_real_config_text is _CONFIG_TEXT_UNSET:
        path = mg.CONFIG_PATH
        _cached_real_config_text = (
            path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
        )
    return _cached_real_config_text


def _resolve_counterfactual_binding(config_text=_CONFIG_TEXT_UNSET,
                                     override_model: str | None = None) -> str:
    """Строка модели для контрфакта -- приоритет флаг > конфиг > R-5 (R-8).

    override_model (--counterfactual-model, R-8): id уже назван явно
    пользователем -- резолвер НЕ зовётся вовсе, это не "резолюция
    привязки" (R-1), а прямой оверрайд поверх неё.

    Иначе -- ДОСЛОВНО mg.resolve_lead_binding(config_text) (R-1,
    единственный носитель): голое слово семейства "fable" -- сентинел
    "привязки нет" (нет файла / нет ключа roles.lead / битый YAML /
    пустой model, см. докстринг resolve_lead_binding) -- ветка R-5
    подслучай (а) (цены на голое "fable" в PRICES_PER_TOKEN_USD нет,
    только на полные id вида "claude-fable-5", поэтому _cost() уже
    вернёт None сам по себе -- отдельного распознавания не требуется,
    R-4: отображение семейства в id не заводится).

    mg is None (R-3: mechanism_gate недоступен, PyYAML отсутствует) --
    резолвер вообще не существует, возвращается диагностическая строка
    вместо его результата (R-5 подслучай а, "mg is None" в перечне)."""
    if override_model:
        return override_model
    if mg is None:
        return "mechanism_gate недоступен (import mechanism_gate failed)"
    if config_text is _CONFIG_TEXT_UNSET:
        config_text = _read_real_config_text()
    return mg.resolve_lead_binding(config_text)


def lead_counterfactual(i: int, o: int, cw: int, cr: int,
                         config_text=_CONFIG_TEXT_UNSET,
                         override_model: str | None = None):
    """Тот же токен-профиль, переоценённый по цене модели, привязанной к
    roles.lead (delegation.config.yaml, резолюция --
    mechanism_gate.resolve_lead_binding(), R-1) — «а если бы это делал
    Lead». config_text/override_model — см. _resolve_counterfactual_
    binding(). R-5 (fail-soft "н/д"): None + WARNING в stderr с
    ФАКТИЧЕСКОЙ строкой привязки, когда для неё нет цены в
    usage_report.PRICES_PER_TOKEN_USD -- голое семейство "fable" (нет
    конфига/ключа/битый YAML/mg недоступен) ИЛИ валидный, но
    непрайсованный id (не-Claude привязка). Позиционные аргументы
    остаются 4 (R-9): tools/spend_model.py:2181 и его тест зовут
    fable_counterfactual(i, o, cw, cr) без новых обязательных
    параметров."""
    binding = _resolve_counterfactual_binding(config_text, override_model)
    cost = _cost(binding, i or 0, o or 0, cw or 0, cr or 0)
    if cost is None:
        print(f"WARNING: контрфакт Lead не определён -- привязка '{binding}'"
              " без цены в usage_report.PRICES_PER_TOKEN_USD", file=sys.stderr)
    return cost


# Алиас (R-6): держит tools/spend_model.py:86 (`from savings_report import
# fable_counterfactual`) и tools/test_spend_model.py -- оба вне owns этой
# задачи. Снятие алиаса -- отдельный пункт очереди (не эта задача).
fable_counterfactual = lead_counterfactual


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


def counterfactual_summary(db: sqlite3.Connection, cond: str, params: tuple,
                            config_text=_CONFIG_TEXT_UNSET,
                            override_model: str | None = None) -> dict:
    """config_text/override_model — проброшены вниз в lead_counterfactual()
    (R-2). R-5: пустое окно (нет сайдчейн-строк) даёт actual==as_lead==0.0
    (числовой ноль, не "нет данных" -- цикл ниже просто не выполняется,
    сохраняет K2(1)); непустое окно с непрайсованной привязкой -- as_lead
    ЦЕЛИКОМ None (одна привязка на всё окно, R-5 подслучай не может
    сработать частично на одних строках и не сработать на других) вместо
    молчаливого cf += None (TypeError, дефект правки, который эта ветка
    обязана закрыть)."""
    rows = db.execute(
        "select agent_type, model, count(*), sum(input_tokens), sum(output_tokens),"
        " sum(cache_creation_tokens), sum(cache_read_tokens), sum(accounted_cost_usd)"
        " from cc_usage where is_sidechain=1 and " + cond +
        " group by agent_type, model order by 8 desc", params).fetchall()
    detail = []
    actual = 0.0
    cf = 0.0
    cf_unresolved = False
    for at, model, n, ti, to, tcw, tcr, cost in rows:
        f = lead_counterfactual(ti, to, tcw, tcr, config_text, override_model)
        actual += cost or 0
        if f is None:
            cf_unresolved = True
        else:
            cf += f
        detail.append({"agent_type": at, "model": model, "turns": n,
                       "actual": cost or 0, "as_lead": f})
    if cf_unresolved:
        cf = None
    if cf is None:
        gross_savings = None
        savings_pct = None
    else:
        gross_savings = cf - actual
        savings_pct = (1 - actual / cf) * 100 if cf else 0.0
    return {"detail": detail, "actual": actual, "as_lead": cf,
            "gross_savings": gross_savings, "savings_pct": savings_pct}


def api_contour_summary(db: sqlite3.Connection) -> dict:
    kinds = db.execute(
        "select traffic_kind, count(*), sum(cost_usd) from requests"
        " group by traffic_kind order by 3 desc").fetchall()
    total = db.execute("select count(*), sum(cost_usd) from requests").fetchone()
    return {"kinds": kinds, "total_n": total[0], "total_cost": total[1] or 0.0}


def print_report(db_path: str, routed_start: str, until: str = None,
                  config_text=_CONFIG_TEXT_UNSET,
                  override_model: str | None = None,
                  window_start: str | None = None,
                  window_end: str | None = None) -> None:
    db = sqlite3.connect(db_path)
    until_cond, until_params = ("", ()) if not until else (" and ts < ?", (until,))

    # M3 (docs/tasks/2026-08-25_wave2-misc-spec.md, F15-iii): --window-start/
    # --window-end сужают выборку УЧИТЫВАЕМЫХ событий (PRE, ROUTED,
    # контрфакт -- все три cc_usage-секции разреза, item 1/2 докстринга
    # модуля) поверх существующих условий; --routed-start остаётся базой
    # сравнения PRE/ROUTED (окно её не переопределяет). API-контур (item 3,
    # requests.db, "вся история") НЕ окном -- отдельный контур с
    # намеренно неоконным охватом (собственная печать "вся история").
    # Границы: --window-start включительно (>=), --window-end
    # исключительно (< , тот же паттерн, что уже у --until выше) -- без
    # аргументов window_cond/window_params пусты, SQL и вывод байт-в-байт
    # как раньше (негативный контроль).
    window_cond = ""
    window_params: tuple = ()
    if window_start:
        window_cond += " and ts >= ?"
        window_params += (window_start,)
    if window_end:
        window_cond += " and ts < ?"
        window_params += (window_end,)
    if window_start or window_end:
        print(f"ОКНО: {window_start or '-'} .. {window_end or '-'}")

    for label, cond, params in [
        ("PRE-ROUTING (< %s)" % routed_start, "ts < ?" + window_cond,
         (routed_start,) + window_params),
        ("ROUTED (>= %s%s)" % (routed_start, f" .. {until}" if until else ""),
         "ts >= ?" + until_cond + window_cond,
         (routed_start,) + until_params + window_params),
    ]:
        w = window_summary(db, cond, params)
        print(f"\n===== {label} =====")
        for model, sc, n, cost, sess in w["rows"]:
            kind = "side" if sc else "main"
            print(f"  {model:28} {kind:4} turns={n:5} sess={sess:3}"
                  f" cost=${cost or 0:9.2f}  $/turn={((cost or 0) / n):.4f}")
        print(f"  ИТОГО: {w['total_turns']} ходов, ${w['total_cost']:.2f},"
              f" {w['days']} дней, ${w['per_day']:.2f}/день")

    c = counterfactual_summary(db, "ts >= ?" + until_cond + window_cond,
                               (routed_start,) + until_params + window_params,
                               config_text, override_model)
    # R-6/R-7: заголовок и подписи называют ФАКТИЧЕСКУЮ модель контрфакта
    # (или "н/д", когда as_lead не определён -- R-5), слова "Fable" не
    # остаётся, если база иная. binding резолвится тем же путём, что и
    # внутри counterfactual_summary -> lead_counterfactual (кэш
    # _read_real_config_text делает повторный вызов дешёвым).
    binding = _resolve_counterfactual_binding(config_text, override_model)
    model_label = binding if c["as_lead"] is not None else "н/д"
    print(f"\n===== КОНТРФАКТ: routed-сайдчейны по цене {model_label}"
          " (Lead-привязка) =====")
    for d in c["detail"]:
        as_lead_str = (f"${d['as_lead']:8.2f}" if d["as_lead"] is not None
                        else "     н/д")
        print(f"  {str(d['agent_type']):16} {d['model']:28} turns={d['turns']:4}"
              f" факт=${d['actual']:8.2f} по-{model_label}={as_lead_str}")
    if c["as_lead"] is not None:
        print(f"  ИТОГО: факт=${c['actual']:.2f}  по-{model_label}=${c['as_lead']:.2f}"
              f"  брутто-экономия=${c['gross_savings']:.2f} ({c['savings_pct']:.0f}%)")
    else:
        print(f"  ИТОГО: факт=${c['actual']:.2f}  по-{model_label}=н/д"
              "  брутто-экономия=н/д (привязка без цены -- см. WARNING выше)")
    print(f"  БАЗА КОНТРФАКТА СМЕНЕНА 2026-08-16: до -- claude-fable-5,"
          f" с -- привязка roles.lead ({binding}); точки тренда до и после"
          " напрямую несопоставимы, старая точка воспроизводится флагом"
          " --counterfactual-model claude-fable-5")

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
    ap.add_argument("--counterfactual-model", default=None,
                    help="переопределяет модель контрфакта поверх привязки"
                         " roles.lead (R-8; приоритет над конфигом); напр."
                         " --counterfactual-model claude-fable-5 воспроизводит"
                         " точку тренда до смены базы 2026-08-16. Неизвестный"
                         " id уходит в ту же ветку 'н/д', что и непрайсованная"
                         " привязка.")
    ap.add_argument("--window-start", default=None,
                    help="M3: нижняя граница окна учитываемых событий (ISO,"
                         " включительно) -- сужает выборку PRE/ROUTED/"
                         "контрфакта, НЕ переопределяет --routed-start как"
                         " базу сравнения")
    ap.add_argument("--window-end", default=None,
                    help="M3: верхняя граница окна учитываемых событий (ISO,"
                         " исключительно -- тот же паттерн, что --until)")
    args = ap.parse_args(argv)
    if args.window_start and args.window_end and args.window_start > args.window_end:
        print(f"savings_report: --window-start > --window-end "
              f"({args.window_start!r} > {args.window_end!r})", file=sys.stderr)
        return 2
    print_report(args.db, args.routed_start, args.until,
                 override_model=args.counterfactual_model,
                 window_start=args.window_start, window_end=args.window_end)
    return 0


if __name__ == "__main__":
    sys.exit(main())
