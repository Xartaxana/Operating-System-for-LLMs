"""Canonical ground truth for exam set2 fixture ("expense tracker").

Reads the three sandbox CSVs (bank_a.csv, bank_b.csv, bank_c.csv, sitting in
../sandbox/ relative to this file) and computes monthly expense totals under
the canonical decisions pinned in docs/tasks/2026-07-15_economy-exam-set2.md:

  - refunds/returns REDUCE the month's expense (not counted as negative
    "income" separately);
  - transfers between the account holder's own accounts are EXCLUDED from
    expense entirely (bank_b, description containing "Перевод");
  - an exact duplicate transaction is counted ONCE;
  - a structurally malformed CSV row is skipped and counted, not fatal;
  - bank_c dates are interpreted MM/DD/YYYY.

Writes expected.json next to this script. Deterministic: re-running produces
a byte-identical file (all money values are Decimal, serialized as fixed
2-decimal strings; iteration order over fixed dict/list structures is
already insertion-stable in this script).
"""
import csv
import json
import os
from decimal import Decimal, ROUND_HALF_UP

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.join(HERE, "..", "sandbox")
BANK_A = os.path.join(SANDBOX, "bank_a.csv")
BANK_B = os.path.join(SANDBOX, "bank_b.csv")
BANK_C = os.path.join(SANDBOX, "bank_c.csv")
OUT_PATH = os.path.join(HERE, "expected.json")

CENTS = Decimal("0.01")
MONTHS = ["2026-03", "2026-04", "2026-05"]


def q(d):
    return d.quantize(CENTS, rounding=ROUND_HALF_UP)


def s(d):
    return str(q(d))


# ---------------------------------------------------------------------------
# bank_a.csv: utf-8, ',', ISO dates (YYYY-MM-DD), single signed amount
# column (expense negative, refund/return positive). Header: date,description,amount
# ---------------------------------------------------------------------------
def parse_bank_a():
    monthly = {m: Decimal("0") for m in MONTHS}
    rows_read = 0
    duplicates_skipped = 0
    seen = set()
    all_rows = []  # (id, date, description, amount) in file order, pre-dedup
    kept_rows = []  # post-dedup rows actually counted

    with open(BANK_A, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["date", "description", "amount"], header
        for i, row in enumerate(reader, start=1):
            if not row:
                continue
            date, desc, amount_str = row[0], row[1], row[2]
            amount = Decimal(amount_str)
            rows_read += 1
            all_rows.append((i, date, desc, amount))
            key = (date, desc, amount_str)
            if key in seen:
                duplicates_skipped += 1
                continue
            seen.add(key)
            kept_rows.append((i, date, desc, amount))
            month = date[:7]
            if month in monthly:
                monthly[month] += -amount

    return {
        "monthly": monthly,
        "rows_read": rows_read,
        "duplicates_skipped": duplicates_skipped,
        "all_rows": all_rows,
        "kept_rows": kept_rows,
    }


# ---------------------------------------------------------------------------
# bank_b.csv: cp1251, ';', dates DD.MM.YYYY, amount always positive formatted
# "1 234,56", + "Тип" column (Дебет/Кредит), Russian descriptions.
# Header: Дата;Описание;Сумма;Тип
# Canonical: Дебет = expense (unless it's a transfer, excluded entirely);
# Кредит = reduces expense (refund-style).
# ---------------------------------------------------------------------------
def parse_ru_amount(raw):
    cleaned = raw.replace(" ", " ").replace(" ", "").replace(",", ".")
    return Decimal(cleaned)


def parse_bank_b():
    monthly = {m: Decimal("0") for m in MONTHS}
    rows_read = 0
    transfers_excluded = 0
    with open(BANK_B, "r", encoding="cp1251", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        header = next(reader)
        assert header == ["Дата", "Описание", "Сумма", "Тип"], header
        for row in reader:
            if not row:
                continue
            date, desc, amount_str, typ = row[0], row[1], row[2], row[3]
            amount = parse_ru_amount(amount_str)
            rows_read += 1
            d, m, y = date.split(".")
            month = f"{y}-{m}"
            is_transfer = "Перевод" in desc
            if is_transfer:
                transfers_excluded += 1
                contribution = Decimal("0")
            elif typ == "Дебет":
                contribution = amount
            elif typ == "Кредит":
                contribution = -amount
            else:
                raise ValueError("unknown Тип: %r" % typ)
            if month in monthly:
                monthly[month] += contribution
    return {
        "monthly": monthly,
        "rows_read": rows_read,
        "transfers_excluded": transfers_excluded,
    }


# ---------------------------------------------------------------------------
# bank_c.csv: utf-8 with BOM, dates MM/DD/YYYY (ambivalent pairs present;
# convention proven unambiguous by 05/31/2026), two amount columns
# (Debit/Credit, exactly one populated per well-formed row), one
# structurally broken row (missing the Credit column -> 3 fields instead of
# 4), blank lines, unicode descriptions. Header: Date,Description,Debit,Credit
# ---------------------------------------------------------------------------
def parse_bank_c():
    monthly = {m: Decimal("0") for m in MONTHS}
    rows_read = 0
    rows_skipped_malformed = 0
    blank_lines_skipped = 0
    with open(BANK_C, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == ["Date", "Description", "Debit", "Credit"], header
        for row in reader:
            if not row or all(field.strip() == "" for field in row):
                blank_lines_skipped += 1
                continue
            if len(row) != 4:
                rows_skipped_malformed += 1
                continue
            date, desc, debit, credit = row
            rows_read += 1
            mm, dd, yyyy = date.split("/")
            month = f"{yyyy}-{mm}"
            contribution = Decimal("0")
            if debit.strip():
                contribution += Decimal(debit)
            if credit.strip():
                contribution -= Decimal(credit)
            if month in monthly:
                monthly[month] += contribution
    return {
        "monthly": monthly,
        "rows_read": rows_read,
        "rows_skipped_malformed": rows_skipped_malformed,
        "blank_lines_skipped": blank_lines_skipped,
    }


# ---------------------------------------------------------------------------
# Battery proba 7: penny-precision control series -- the first 20
# chronological expense rows of bank_a.csv (file order == chronological
# order in this fixture), summed with Decimal. A float-summing
# implementation drifts away from this exact value.
# ---------------------------------------------------------------------------
def build_control_series(bank_a_all_rows):
    control = []
    for row_id, date, desc, amount in bank_a_all_rows:
        if amount < 0:
            control.append((row_id, date, desc, amount))
        if len(control) == 20:
            break
    total = sum((-amount for _, _, _, amount in control), Decimal("0"))
    return {
        "description": (
            "First 20 chronological expense rows of bank_a.csv (file order); "
            "Decimal sum must match exactly, a float implementation will drift."
        ),
        "rows": [
            {"id": rid, "date": date, "description": desc, "amount": s(-amount)}
            for rid, date, desc, amount in control
        ],
        "sum_expense": s(total),
    }


# ---------------------------------------------------------------------------
# S4 sanity chain: "naive" prototype-style May total (duplicate counted
# twice + transfer counted as an ordinary expense) must exceed the
# canonical May total for banks A+B combined.
# ---------------------------------------------------------------------------
def build_sanity_check_s4(bank_a_result, bank_b_result):
    canonical_may_a = bank_a_result["monthly"]["2026-05"]
    canonical_may_b = bank_b_result["monthly"]["2026-05"]
    canonical_may_ab = canonical_may_a + canonical_may_b

    # naive bank_a May: sum ALL May rows (including both copies of the
    # duplicate), refunds still reduce (S4 legend only names dup + transfer
    # as the naive deviations).
    naive_may_a = Decimal("0")
    for row_id, date, desc, amount in bank_a_result["all_rows"]:
        if date.startswith("2026-05"):
            naive_may_a += -amount

    # naive bank_b May: every Дебет row counts as expense, including the
    # transfer; Кредит still reduces (not part of the S4 legend's bug pair).
    naive_may_b = Decimal("0")
    with open(BANK_B, "r", encoding="cp1251", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            if not row:
                continue
            date, desc, amount_str, typ = row[0], row[1], row[2], row[3]
            d, m, y = date.split(".")
            if f"{y}-{m}" != "2026-05":
                continue
            amount = parse_ru_amount(amount_str)
            if typ == "Дебет":
                naive_may_b += amount
            elif typ == "Кредит":
                naive_may_b -= amount

    naive_may = naive_may_a + naive_may_b
    return {
        "canonical_may_bank_a": s(canonical_may_a),
        "canonical_may_bank_b": s(canonical_may_b),
        "canonical_may_a_plus_b": s(canonical_may_ab),
        "naive_may_prototype_style": s(naive_may),
        "naive_minus_canonical": s(naive_may - canonical_may_ab),
        "holds": naive_may > canonical_may_ab,
    }


def main():
    bank_a = parse_bank_a()
    bank_b = parse_bank_b()
    bank_c = parse_bank_c()

    monthly_expense = {}
    for m in MONTHS:
        a = bank_a["monthly"][m]
        b = bank_b["monthly"][m]
        c = bank_c["monthly"][m]
        monthly_expense[m] = {
            "bank_a": s(a),
            "bank_b": s(b),
            "bank_c": s(c),
            "total": s(a + b + c),
        }

    totals_all_months = {
        "bank_a": s(sum(bank_a["monthly"].values(), Decimal("0"))),
        "bank_b": s(sum(bank_b["monthly"].values(), Decimal("0"))),
        "bank_c": s(sum(bank_c["monthly"].values(), Decimal("0"))),
        "total": s(
            sum(bank_a["monthly"].values(), Decimal("0"))
            + sum(bank_b["monthly"].values(), Decimal("0"))
            + sum(bank_c["monthly"].values(), Decimal("0"))
        ),
    }

    march_april_total = s(
        bank_a["monthly"]["2026-03"] + bank_a["monthly"]["2026-04"]
        + bank_b["monthly"]["2026-03"] + bank_b["monthly"]["2026-04"]
        + bank_c["monthly"]["2026-03"] + bank_c["monthly"]["2026-04"]
    )

    result = {
        "generated_by": "ground_truth.py",
        "counters": {
            "bank_a": {
                "rows_read": bank_a["rows_read"],
                "duplicates_skipped": bank_a["duplicates_skipped"],
                "rows_skipped_malformed": 0,
            },
            "bank_b": {
                "rows_read": bank_b["rows_read"],
                "transfers_excluded": bank_b["transfers_excluded"],
                "rows_skipped_malformed": 0,
            },
            "bank_c": {
                "rows_read": bank_c["rows_read"],
                "rows_skipped_malformed": bank_c["rows_skipped_malformed"],
                "blank_lines_skipped": bank_c["blank_lines_skipped"],
            },
        },
        "monthly_expense": monthly_expense,
        "march_plus_april_total_all_banks": march_april_total,
        "totals_all_months": totals_all_months,
        "penny_precision_control": build_control_series(bank_a["all_rows"]),
        "sanity_check_s4": build_sanity_check_s4(bank_a, bank_b),
    }

    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")

    print("wrote", OUT_PATH)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
