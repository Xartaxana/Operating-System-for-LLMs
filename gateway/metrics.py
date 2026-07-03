"""Ledger: deterministic analytics over the gateway request log.

ARCHITECTURE.md, "Ledger"; D-0027. Pure Python/SQL, no LLM.

Produces a daily digest: requests, tokens, cost, latency and response
length per model per day; budget events; task categories (transparent
keyword heuristics, always marked as such); and the context-repetition
ratio — the share of prompt characters already sent in the previous
request of the same model. External priors to beat: 50-62% of spend is
re-sent history (docs/RELATED_WORK.md).

Usage:
    python metrics.py [--db PATH] [--days N] [--json]
"""

import argparse
import json
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

# Transparent, deterministic heuristics. Categories are estimates for
# the delegation table, not ground truth; the Analyst refines them.
CATEGORY_RULES = [
    ("coding", ("```", "def ", "class ", "function", "traceback", "compile")),
    ("summarization", ("summarize", "summary", "tl;dr", "shorten")),
    ("extraction", ("extract", "to json", "parse", "convert")),
    ("classification", ("classify", "categorize", "label", "tag")),
    ("formatting", ("format", "markdown", "table")),
]


def categorize(prompt_text: str) -> str:
    lowered = (prompt_text or "").lower()
    for category, needles in CATEGORY_RULES:
        if any(needle in lowered for needle in needles):
            return category
    return "other"


def common_prefix_len(a: str, b: str) -> int:
    limit = min(len(a), len(b))
    i = 0
    while i < limit and a[i] == b[i]:
        i += 1
    return i


def repetition_by_model(rows) -> dict:
    """rows: (model, prompt) ordered by ts. Returns per-model ratio:
    repeated prompt chars / total prompt chars, over consecutive pairs."""
    previous = {}
    repeated = defaultdict(int)
    total = defaultdict(int)
    for model, prompt in rows:
        if not prompt:
            continue
        if model in previous:
            repeated[model] += common_prefix_len(previous[model], prompt)
            total[model] += len(prompt)
        previous[model] = prompt
    return {
        model: round(repeated[model] / total[model], 4)
        for model in total
        if total[model]
    }


def daily_digest(conn: sqlite3.Connection, days: int) -> dict:
    since = f"-{days} days"
    per_day = conn.execute(
        """
        SELECT substr(ts, 1, 10) AS day, model,
               COUNT(*) AS requests,
               SUM(status = 'failure') AS failures,
               COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
               COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
               COALESCE(SUM(cost_usd), 0) AS cost_usd,
               ROUND(AVG(latency_ms), 1) AS avg_latency_ms,
               ROUND(AVG(LENGTH(COALESCE(response, ''))), 1) AS avg_response_chars
        FROM requests
        WHERE day >= date('now', ?)
        GROUP BY day, model ORDER BY day, model
        """,
        (since,),
    ).fetchall()

    categories = defaultdict(lambda: {"requests": 0, "cost_usd": 0.0})
    prompts = conn.execute(
        "SELECT model, prompt, COALESCE(cost_usd, 0) FROM requests"
        " WHERE substr(ts, 1, 10) >= date('now', ?) ORDER BY ts",
        (since,),
    ).fetchall()
    for _, prompt, cost in prompts:
        bucket = categories[categorize(prompt)]
        bucket["requests"] += 1
        bucket["cost_usd"] = round(bucket["cost_usd"] + cost, 6)

    repetition = repetition_by_model((model, prompt) for model, prompt, _ in prompts)

    try:
        events = conn.execute(
            "SELECT substr(ts, 1, 10), model, level, spent_usd, budget_usd"
            " FROM budget_events WHERE substr(ts, 1, 10) >= date('now', ?)"
            " ORDER BY ts",
            (since,),
        ).fetchall()
    except sqlite3.OperationalError:
        events = []

    return {
        "days": days,
        "per_day": [
            {
                "day": r[0], "model": r[1], "requests": r[2], "failures": r[3],
                "prompt_tokens": r[4], "completion_tokens": r[5],
                "cost_usd": round(r[6], 6), "avg_latency_ms": r[7],
                "avg_response_chars": r[8],
            }
            for r in per_day
        ],
        "categories_heuristic": dict(categories),
        "context_repetition_ratio": repetition,
        "budget_events": [
            {"day": e[0], "model": e[1], "level": e[2],
             "spent_usd": e[3], "budget_usd": e[4]}
            for e in events
        ],
    }


def format_digest(digest: dict) -> str:
    lines = [f"LEDGER DIGEST (last {digest['days']} day(s))", ""]

    lines.append("Per model per day:")
    if not digest["per_day"]:
        lines.append("  no requests")
    for r in digest["per_day"]:
        lines.append(
            f"  {r['day']}  {r['model']}: {r['requests']} req"
            f" ({r['failures']} failed), {r['prompt_tokens']}+{r['completion_tokens']} tok,"
            f" ${r['cost_usd']:.4f}, {r['avg_latency_ms']} ms avg,"
            f" {r['avg_response_chars']} chars avg answer"
        )

    lines.append("")
    lines.append("Context repetition (share of prompt chars re-sent):")
    if not digest["context_repetition_ratio"]:
        lines.append("  not enough consecutive requests")
    for model, ratio in digest["context_repetition_ratio"].items():
        lines.append(f"  {model}: {ratio:.0%}")

    lines.append("")
    lines.append("Task categories (keyword heuristics, estimates):")
    for category, stats in sorted(digest["categories_heuristic"].items()):
        lines.append(
            f"  {category}: {stats['requests']} req, ${stats['cost_usd']:.4f}"
        )

    lines.append("")
    lines.append("Budget events:")
    if not digest["budget_events"]:
        lines.append("  none")
    for e in digest["budget_events"]:
        lines.append(
            f"  {e['day']}  {e['model']} {e['level'].upper()}:"
            f" ${e['spent_usd']:.4f} of ${e['budget_usd']:.2f}"
        )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Ledger daily digest")
    parser.add_argument(
        "--db",
        default=os.environ.get(
            "GATEWAY_DB_PATH", Path(__file__).parent / "requests.db"
        ),
    )
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not Path(args.db).exists():
        raise SystemExit(f"request log not found: {args.db}")

    conn = sqlite3.connect(args.db)
    digest = daily_digest(conn, args.days)
    print(json.dumps(digest, indent=2) if args.json else format_digest(digest))


if __name__ == "__main__":
    main()
