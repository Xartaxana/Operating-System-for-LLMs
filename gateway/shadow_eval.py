"""Shadow Evaluation: replay sampled Lead requests on a cheaper model
and compare outputs, turning DELEGATION_TABLE.md estimates into
evidence-backed rows (ARCHITECTURE.md, "Shadow Evaluation"; D-0028).

For each sampled request: replay the same prompt on --target-model,
compare the replayed answer to the original with a transparent
heuristic (character-level similarity via difflib -- same "estimate,
mark it as such" spirit as metrics.categorize; an LLM judge can
replace this later without changing the pipeline). Results are
grouped by the same keyword-heuristic task category metrics.py uses,
so a category can accumulate enough samples across runs to cross the
--min-samples bar.

Per DELEGATION_TABLE.md Update Rule 4, cost comparison uses TOTAL
replay cost. Caveat: a single-shot replay does not measure retry
loops, so a "validated" verdict here only confirms one-shot quality,
not the retry-loop cost risk rule 4 warns about; note this in
DELEGATION_TABLE.md when relying on it.

Usage:
    python shadow_eval.py --source-model lead --target-model intern
    python shadow_eval.py --source-model lead --target-model intern --update-table
"""

import argparse
import difflib
import json
import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

import litellm

from metrics import categorize

# metrics.py category -> exact "Task type" cell text in DELEGATION_TABLE.md.
# Categories with no row (e.g. "other") are evaluated but never update the table.
CATEGORY_TO_TASK_TYPE = {
    "coding": "Routine code generation",
    "summarization": "Summarization",
    "extraction": "Data extraction, JSON conversion",
    "classification": "Classification, tagging",
    "formatting": "Formatting (Markdown, tables)",
}

DEFAULT_SIMILARITY_THRESHOLD = 0.5
DEFAULT_MIN_SAMPLES = 2


def sample_requests(conn: sqlite3.Connection, source_model: str, days: int, limit: int):
    """Random sample of successful requests for source_model, most recent --days."""
    rows = conn.execute(
        "SELECT id, prompt, response, COALESCE(cost_usd, 0) FROM requests"
        " WHERE model = ? AND status = 'success' AND prompt IS NOT NULL"
        " AND response IS NOT NULL AND substr(ts, 1, 10) >= date('now', ?)"
        " ORDER BY RANDOM() LIMIT ?",
        (source_model, f"-{days} days", limit),
    ).fetchall()
    return [
        {"id": r[0], "prompt": r[1], "response": r[2], "cost_usd": r[3]} for r in rows
    ]


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a or "", b or "").ratio()


def replay(messages: list, target_model: str, gateway: str, **kwargs):
    """Runs the same messages on target_model through the gateway.
    Returns (response_text, cost_usd). kwargs pass through to litellm
    (tests use mock_response to avoid a live model/proxy)."""
    response = litellm.completion(
        model=f"openai/{target_model}",
        api_base=gateway.rstrip("/") + "/v1",
        api_key=os.environ.get("GATEWAY_API_KEY", "anything"),
        messages=messages,
        **kwargs,
    )
    text = response.choices[0].message.content
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0
    return text, cost


def evaluate(conn, source_model: str, target_model: str, gateway: str, days: int, sample_n: int, **replay_kwargs):
    results = []
    for row in sample_requests(conn, source_model, days, sample_n):
        try:
            messages = json.loads(row["prompt"])
        except (TypeError, json.JSONDecodeError):
            continue
        category = categorize(row["prompt"])
        try:
            replayed_text, replayed_cost = replay(messages, target_model, gateway, **replay_kwargs)
            error = None
        except Exception as exc:
            replayed_text, replayed_cost, error = None, None, str(exc)
        results.append(
            {
                "request_id": row["id"],
                "category": category,
                "source_cost_usd": row["cost_usd"],
                "target_cost_usd": replayed_cost,
                "similarity": similarity(row["response"], replayed_text) if error is None else 0.0,
                "error": error,
            }
        )
    return results


def aggregate_by_category(results: list) -> dict:
    buckets = defaultdict(list)
    for r in results:
        buckets[r["category"]].append(r)

    aggregated = {}
    for category, items in buckets.items():
        n = len(items)
        aggregated[category] = {
            "n": n,
            "mean_similarity": round(sum(i["similarity"] for i in items) / n, 4),
            "mean_source_cost_usd": round(sum(i["source_cost_usd"] for i in items) / n, 6),
            "mean_target_cost_usd": round(
                sum(i["target_cost_usd"] or 0 for i in items) / n, 6
            ),
            "errors": sum(1 for i in items if i["error"]),
        }
    return aggregated


def decide_status(agg: dict, similarity_threshold: float, min_samples: int) -> str:
    """"estimated" means inconclusive here (not enough evidence yet to
    move off the table's default), distinct from a positive validation."""
    if agg["n"] < min_samples or agg["errors"] == agg["n"]:
        return "estimated"
    if agg["mean_similarity"] >= similarity_threshold and agg["mean_target_cost_usd"] <= agg["mean_source_cost_usd"]:
        return "validated"
    return "rejected"


def update_table_status(text: str, task_type: str, new_status: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 6 and parts[1] == task_type:
            parts[-2] = new_status
            lines[i] = "| " + " | ".join(parts[1:-1]) + " |"
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def append_evidence_log(text: str, entries: list) -> str:
    heading = "## Shadow Evaluation Log"
    if heading not in text:
        text = text.rstrip("\n") + f"\n\n{heading}\n\nEvidence for Update Rule 1. One line per Shadow Evaluation run.\n\n"
    lines = text.splitlines()
    insert_at = len(lines)
    for entry in entries:
        lines.insert(insert_at, f"- {entry}")
        insert_at += 1
    return "\n".join(lines) + "\n"


def update_delegation_table(path: Path, date: str, source_model: str, target_model: str, aggregated: dict, statuses: dict):
    text = path.read_text(encoding="utf-8")
    entries = []
    for category, task_type in CATEGORY_TO_TASK_TYPE.items():
        if category not in aggregated:
            continue
        agg = aggregated[category]
        status = statuses[category]
        entries.append(
            f"{date}  category={category}  source={source_model} target={target_model}"
            f"  n={agg['n']}  sim={agg['mean_similarity']:.2f}"
            f"  cost_source=${agg['mean_source_cost_usd']:.4f}"
            f" cost_target=${agg['mean_target_cost_usd']:.4f}  -> {status}"
        )
        if status in ("validated", "rejected"):
            text = update_table_status(text, task_type, status)
    if entries:
        text = append_evidence_log(text, entries)
    path.write_text(text, encoding="utf-8")


def format_report(source_model, target_model, aggregated, statuses) -> str:
    lines = [f"SHADOW EVALUATION: {source_model} -> {target_model}", ""]
    if not aggregated:
        lines.append(f"  no successful {source_model!r} requests in range")
        return "\n".join(lines)
    for category, agg in sorted(aggregated.items()):
        mapped = CATEGORY_TO_TASK_TYPE.get(category, "(unmapped, table not updated)")
        lines.append(
            f"  {category} [{mapped}]: n={agg['n']} sim={agg['mean_similarity']:.0%}"
            f" cost {source_model}=${agg['mean_source_cost_usd']:.4f}"
            f" vs {target_model}=${agg['mean_target_cost_usd']:.4f}"
            f" errors={agg['errors']} -> {statuses[category]}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Shadow Evaluation: replay + compare")
    parser.add_argument("--source-model", default="lead", help="gateway alias whose requests to sample")
    parser.add_argument("--target-model", default="intern", help="cheaper gateway alias to replay on")
    parser.add_argument("--gateway", default="http://localhost:4000")
    parser.add_argument(
        "--db",
        default=os.environ.get("GATEWAY_DB_PATH", Path(__file__).parent / "requests.db"),
    )
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--sample", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    parser.add_argument("--min-samples", type=int, default=DEFAULT_MIN_SAMPLES)
    parser.add_argument("--update-table", action="store_true")
    parser.add_argument(
        "--table",
        default=Path(__file__).parent.parent / "DELEGATION_TABLE.md",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not Path(args.db).exists():
        raise SystemExit(f"request log not found: {args.db}")
    if args.source_model == args.target_model:
        raise SystemExit(
            "source and target model must differ: comparing a model to itself"
            " is not evidence a cheaper tier can substitute for it"
        )

    conn = sqlite3.connect(args.db)
    results = evaluate(conn, args.source_model, args.target_model, args.gateway, args.days, args.sample)
    aggregated = aggregate_by_category(results)
    statuses = {
        category: decide_status(agg, args.threshold, args.min_samples)
        for category, agg in aggregated.items()
    }

    if args.json:
        print(json.dumps({"aggregated": aggregated, "statuses": statuses, "results": results}, indent=2))
    else:
        print(format_report(args.source_model, args.target_model, aggregated, statuses))

    if args.update_table and aggregated:
        import datetime

        update_delegation_table(
            Path(args.table),
            datetime.date.today().isoformat(),
            args.source_model,
            args.target_model,
            aggregated,
            statuses,
        )


if __name__ == "__main__":
    main()
