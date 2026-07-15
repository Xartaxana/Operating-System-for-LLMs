import csv
import json
import os
import sys

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expenses_state.json")

CATEGORIES = {
    "walmart": "groceries",
    "trader joe": "groceries",
    "safeway": "groceries",
    "whole foods": "groceries",
    "kroger": "groceries",
    "starbucks": "cafe",
    "chipotle": "cafe",
    "panera": "cafe",
    "dunkin": "cafe",
    "coffee": "cafe",
    "uber": "transport",
    "shell oil": "transport",
    "metro transit": "transport",
    "netflix": "subscriptions",
    "spotify": "subscriptions",
    "amazon prime": "subscriptions",
    "hulu": "subscriptions",
    "disney": "subscriptions",
    "amazon.com": "shopping",
    "target": "shopping",
    "best buy": "shopping",
    "ikea": "shopping",
    "etsy": "shopping",
    "cvs": "health",
    "walgreens": "health",
    "rite aid": "health",
    "amc": "entertainment",
    "steam": "entertainment",
    "regal": "entertainment",
    "pacific gas": "utilities",
    "water utility": "utilities",
    "comcast": "utilities",
}

# order matters for printing, not for matching
CATEGORY_ORDER = [
    "groceries",
    "cafe",
    "transport",
    "subscriptions",
    "shopping",
    "health",
    "entertainment",
    "utilities",
    "other",
]

TRANSACTIONS = []


def load_state():
    global TRANSACTIONS
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            TRANSACTIONS = json.load(f)
    else:
        TRANSACTIONS = []


def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump(TRANSACTIONS, f, indent=2)


def categorize(desc):
    for keyword, cat in CATEGORIES.items():
        if keyword in desc:
            return cat
    return "other"


def import_csv(path):
    load_state()
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            date = row[0]
            desc = row[1]
            amount = float(row[2])
            cat = categorize(desc)
            TRANSACTIONS.append({
                "date": date,
                "description": desc,
                "amount": amount,
                "category": cat,
            })
            count += 1
    save_state()
    print("imported %d transactions from %s" % (count, path))


def import_many(paths):
    for path in paths:
        import_csv(path)


def month_key(date):
    return date[5:7]


def month_name(key):
    names = {
        "01": "jan", "02": "feb", "03": "mar", "04": "apr",
        "05": "may", "06": "jun", "07": "jul", "08": "aug",
        "09": "sep", "10": "oct", "11": "nov", "12": "dec",
    }
    return names.get(key, key)


def report():
    load_state()
    if not TRANSACTIONS:
        print("no transactions yet, run import first")
        return

    by_cat = {}
    for t in TRANSACTIONS:
        amt = t["amount"]
        if amt < 0:
            spend = -amt
            by_cat[t["category"]] = by_cat.get(t["category"], 0) + spend

    print("=== spending by category ===")
    total = 0
    for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1]):
        print("%-15s %10.2f" % (cat, amt))
        total += amt
    print("%-15s %10.2f" % ("TOTAL", total))

    by_month = {}
    for t in TRANSACTIONS:
        amt = t["amount"]
        if amt < 0:
            m = month_key(t["date"])
            by_month[m] = by_month.get(m, 0) + (-amt)

    print()
    print("=== spending by month ===")
    for m in sorted(by_month.keys()):
        print("%s %10.2f" % (month_name(m), by_month[m]))


def report_by_category_and_month():
    load_state()
    if not TRANSACTIONS:
        print("no transactions yet, run import first")
        return

    grid = {}
    months = set()
    for t in TRANSACTIONS:
        amt = t["amount"]
        if amt >= 0:
            continue
        m = month_key(t["date"])
        months.add(m)
        cat = t["category"]
        grid.setdefault(cat, {})
        grid[cat][m] = grid[cat].get(m, 0) + (-amt)

    months = sorted(months)
    header = "%-15s" % "category"
    for m in months:
        header += " %10s" % month_name(m)
    print(header)
    for cat in CATEGORY_ORDER:
        if cat not in grid:
            continue
        line = "%-15s" % cat
        for m in months:
            line += " %10.2f" % grid[cat].get(m, 0)
        print(line)


def list_transactions():
    load_state()
    if not TRANSACTIONS:
        print("no transactions yet, run import first")
        return
    for i, t in enumerate(TRANSACTIONS):
        print("%4d  %s  %-30s %10.2f  %s" % (
            i, t["date"], t["description"], t["amount"], t["category"]))


def search(term):
    load_state()
    hits = 0
    for t in TRANSACTIONS:
        if term in t["description"]:
            print("%s  %-30s %10.2f  %s" % (
                t["date"], t["description"], t["amount"], t["category"]))
            hits += 1
    print("%d matches" % hits)


def categories_cmd():
    for cat in CATEGORY_ORDER:
        keywords = [k for k, v in CATEGORIES.items() if v == cat]
        print("%-15s %s" % (cat, ", ".join(keywords)))


def reset_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
        print("cleared saved transactions")
    else:
        print("nothing to clear")


def budget_status():
    print("budgets are not set up yet")


USAGE = """usage:
  expense_tracker.py import <file> [<file> ...]
  expense_tracker.py report
  expense_tracker.py report-grid
  expense_tracker.py list
  expense_tracker.py search <term>
  expense_tracker.py categories
  expense_tracker.py budget
  expense_tracker.py reset
"""


def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return

    cmd = sys.argv[1]
    if cmd == "import":
        if len(sys.argv) < 3:
            print("usage: expense_tracker.py import <file> [<file> ...]")
            return
        import_many(sys.argv[2:])
    elif cmd == "report":
        report()
    elif cmd == "report-grid":
        report_by_category_and_month()
    elif cmd == "list":
        list_transactions()
    elif cmd == "search":
        if len(sys.argv) < 3:
            print("usage: expense_tracker.py search <term>")
            return
        search(sys.argv[2])
    elif cmd == "categories":
        categories_cmd()
    elif cmd == "budget":
        budget_status()
    elif cmd == "reset":
        reset_state()
    else:
        print("unknown command: %s" % cmd)
        print(USAGE)


if __name__ == "__main__":
    main()
