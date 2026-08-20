#!/usr/bin/env python3
"""Node A key-runner (R11.l), calibration remediation #8.

Checks every key of docs/tasks/2026-08-20_nodeA-narrowing-spec.md §7
(Ш1) against its own carrier: chek 14(ж) narrowing (a1-a6), chek 22
"РЕЦИДИВ ВНУТРИ СЕССИИ" narrowing (b1-b6), LEAD_RANKING_EXAM.md
triggers section (c1-c2), CALIBRATION_HISTORY.md archive entries
(d1-d2), docs/RULE_COVERAGE.md pin/cell/dictionary (e1-e4), and one
anti-key (f1: absence of the old chek-14(ж) pin phrase at line 81).

Fold contract (_fold_whitespace, D-0054/08-19 finding t-496, same as
docs/tasks/2026-08-19_w2c2-keyrun.py):
  {space, tab, CR, LF}+ -> single space; '|' is NOT folded.

Usage:
  python 2026-08-20_nodeA-keyrun.py            # normal run
  python 2026-08-20_nodeA-keyrun.py --drop ID  # negative control:
                                                  pretend key ID is
                                                  absent from its
                                                  carrier

Exit code 0 = every positive key found at its own address AND the
anti-key (f1) is genuinely absent; 1 = failure (including an empty
key list, any positional mismatch, or the anti-key being present).
"""
import re
import sys
import argparse

ROOT = None  # set below

PROTOCOL = "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"
EXAM = "PROCESS/LEAD_RANKING_EXAM.md"
HISTORY = "PROCESS/CALIBRATION_HISTORY.md"
COVERAGE = "docs/RULE_COVERAGE.md"


def _fold_whitespace(s: str) -> str:
    # {space, tab, CR, LF}+ -> one space; '|' left alone.
    return re.sub(r"[ \t\r\n]+", " ", s)


# id, kind ("P" positive / "N" anti-key must be ABSENT), text, address
KEYS = [
    # chek 14(ж) narrowing (§2 ПОСЛЕ)
    ("a1", "P", "ПРЕДМЕТ ТРИГГЕРА — СОДЕРЖАТЕЛЬНАЯ правка Lead-политики", PROTOCOL),
    ("a2", "P", "ПРИ ПУСТОМ диффе `tools/norm_keys.json` того же коммита", PROTOCOL),
    ("a3", "P", "вердикт критика по форме образца W2c-V", PROTOCOL),
    ("a4", "P", "СМЕШАННЫЙ коммит (часть формы, часть нормы) содержателен ЦЕЛИКОМ", PROTOCOL),
    ("a5", "P", "АУДИТ ЧЕСТНОСТИ", PROTOCOL),
    ("a6", "P", "сужение относится ТОЛЬКО к триггеру 2", EXAM),
    # chek 22 "РЕЦИДИВ ВНУТРИ СЕССИИ" narrowing (§3 ПОСЛЕ)
    ("b1", "P", "события КЛАССА-ЛЬГОТЫ в ОДНОЙ сессии = НАРУШЕНИЕ САМО ПО СЕБЕ", PROTOCOL),
    ("b2", "P", "определяется НОРМОЙ-ИСТОЧНИКОМ skip'а", PROTOCOL),
    ("b3", "P", "СТОЯЧАЯ КОНЦЕССИЯ = норма требует события на КАЖДОМ применении", PROTOCOL),
    ("b4", "P", "перевод действует С ДАТЫ находки — прошедшие окна не", PROTOCOL),
    ("b5", "P", "СЧИТАЮТСЯ И НАЗЫВАЮТСЯ ЧИСЛОМ", PROTOCOL),
    ("b6", "P", "«рецидивов внутри сессии нет»", PROTOCOL),
    # LEAD_RANKING_EXAM.md triggers section
    ("c1", "P", "СОДЕРЖАТЕЛЬНАЯ правка Lead-политики ядра", EXAM),
    ("c2", "P", "Триггеры 1, 3 и 4 безусловны", EXAM),
    # CALIBRATION_HISTORY.md archive
    ("d1", "P", "прежняя редакция триггера Lead-экзамена v2 (учтена в чеке 14(ж))", HISTORY),
    ("d2", "P", "прежняя редакция абзаца «РЕЦИДИВ ВНУТРИ СЕССИИ» (учтена в чеке 22)", HISTORY),
    # docs/RULE_COVERAGE.md
    ("e1", "P", "чек 13(ж) (маркер AUTO-BOOT на fresh-транскрипте)", COVERAGE),
    ("e2", "P", "рецидивом считается повтор КЛАССА-ЛЬГОТЫ", COVERAGE),
    ("e3", "P", "рецидив КЛАССА-ЛЬГОТЫ ВНУТРИ ОДНОЙ", COVERAGE),
    ("e4", "P", "детектор — чек 14(ж); с 2026-08-20 триггер 2 сужен", COVERAGE),
    # anti-key: the old pin phrase must be GONE from docs/RULE_COVERAGE.md
    ("f1", "N", "чек 14(ж) (директива на fresh-транскрипте)", COVERAGE),
]


def load(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return _fold_whitespace(f.read())


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--drop", default=None, help="negative control: pretend this key id is absent from its carrier")
    args = ap.parse_args()
    ROOT = args.root

    if not KEYS:
        print("EMPTY KEY LIST -> FAIL (пустой список ключей = скрипт обязан упасть)")
        sys.exit(1)

    cache = {}

    def get(path):
        full = ROOT.rstrip("/\\") + "/" + path
        if full not in cache:
            cache[full] = load(full)
        return cache[full]

    ok = True
    rows = []
    for kid, kind, text, addr in KEYS:
        folded = _fold_whitespace(text)
        content = get(addr)

        if args.drop == kid:
            # negative control: pretend the key text was struck from
            # its own carrier by never finding it there.
            found = False
        else:
            found = folded in content

        if kind == "N":
            # anti-key: verdict is OK only when genuinely ABSENT
            verdict = not found
        else:
            verdict = found

        rows.append((kid, kind, addr, verdict))
        if not verdict:
            ok = False

    for kid, kind, addr, verdict in rows:
        print(f"{'OK ' if verdict else 'FAIL'}  {kid:4s} [{kind}]  {addr}")

    print()
    if not ok:
        for kid, kind, addr, verdict in rows:
            if not verdict:
                if kind == "N":
                    print(f"НЕНАЙДЕННЫЙ КЛЮЧ (анти-ключ присутствует, ожидалось отсутствие): {kid} @ {addr}")
                else:
                    print(f"НЕНАЙДЕННЫЙ КЛЮЧ: {kid} @ {addr}")
    print("RESULT:", "ALL KEYS OK" if ok else "FAILURE (see FAIL rows above)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
