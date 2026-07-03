"""Shadow Evaluation: replay sampled Lead requests on a cheaper model
and compare outputs, turning DELEGATION_TABLE.md estimates into
evidence-backed rows (ARCHITECTURE.md, "Shadow Evaluation"; D-0028).

For each sampled request: replay the same prompt on --target-model,
compare the replayed answer to the original. Two comparison modes:

- difflib character similarity (default) -- transparent but crude:
  it punishes verbose-but-correct answers (2 of 5 first-run verdicts
  were false rejections, see judge_calibration.json);
- --judge-model ALIAS -- an LLM judge through the gateway (so judge
  cost lands in the Ledger, Rule #1) that sees the task and both
  anonymized answers and rules EQUIVALENT/WORSE ignoring verbosity
  and formatting. Judge verdicts override difflib in decide_status.
  Calibrate the judge first: --calibrate judge_calibration.json
  --judge-model ALIAS reports agreement with the manual labels.

Results are grouped by the same keyword-heuristic task category
metrics.py uses, so a category can accumulate enough samples across
runs to cross the --min-samples bar.

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
DEFAULT_PASS_THRESHOLD = 0.75

# The judge sees only the task and two anonymized answers, never model
# names, and is instructed to ignore exactly what broke difflib:
# verbosity, formatting and phrasing (see judge_calibration.json).
# Neither clause fixed middle-groq's fibonacci miss: it hallucinates
# a bug while "tracing" a correct loop (claims the code returns b; it
# returns a) — a reasoning-capability ceiling, not a prompt problem
# (diagnosed 2026-07-03; the earlier "missing validation" theory was
# wrong). Fix was a stronger judge: judge-groq (gpt-oss-120b) scores
# 11/11 with this prompt. parse_verdict() takes the LAST keyword, so
# the judge may reason before the final verdict line.
# NOTE: sample_requests() filters judge contamination by matching the
# first sentence of this prompt — keep it stable or update the filter.
JUDGE_SYSTEM_PROMPT = (
    "You are an impartial judge comparing two answers to the same task. "
    "Decide whether Answer B accomplishes the task as well as Answer A. "
    "Judge ONLY against what the task explicitly asked for. "
    "Verbosity, formatting, phrasing, markdown fences and extra "
    "explanation do NOT matter. If Answer A includes extras the task "
    "did not ask for (input validation, error handling, edge-case "
    "tests, examples), Answer B is NOT worse for lacking them. "
    "First verify each answer against the task step by step; for code, "
    "trace the execution on one or two small inputs before claiming a "
    "bug. Then reply on the final line with exactly one word: "
    "EQUIVALENT if Answer B accomplishes what the task explicitly "
    "asked as well as Answer A (or better), or WORSE if Answer B "
    "fails or is incorrect at the explicit task."
)


def sample_requests(conn: sqlite3.Connection, source_model: str, days: int, limit: int):
    """Random sample of successful requests for source_model, most recent --days.

    Judge calls are excluded: when the judge model doubles as a traffic
    model, its judge prompts land in the log under the same alias, and
    replaying them contaminates the sample (observed 2026-07-03: a
    failed lead-gemini calibration polluted 6 of 11 sampled pairs)."""
    rows = conn.execute(
        "SELECT id, prompt, response, COALESCE(cost_usd, 0) FROM requests"
        " WHERE model = ? AND status = 'success' AND prompt IS NOT NULL"
        " AND response IS NOT NULL AND substr(ts, 1, 10) >= date('now', ?)"
        " AND prompt NOT LIKE '%impartial judge comparing two answers%'"
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


def parse_verdict(text: str):
    """Extracts the judge's verdict from its reply. Thinking models
    (Qwen3) may wrap reasoning in <think> blocks or restate both
    options — take the last keyword outside think blocks."""
    if not text:
        return None
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    matches = re.findall(r"\b(equivalent|worse)\b", cleaned, flags=re.IGNORECASE)
    if not matches:
        return None
    return "equivalent" if matches[-1].lower() == "equivalent" else "target_worse"


def judge_pair(task_prompt: str, source_answer: str, target_answer: str,
               judge_model: str, gateway: str, **kwargs):
    """Asks judge_model (through the gateway, so judge cost lands in
    the Ledger) whether the target answer is as good as the source's.
    Returns 'equivalent', 'target_worse', or None if unparseable."""
    response = litellm.completion(
        model=f"openai/{judge_model}",
        api_base=gateway.rstrip("/") + "/v1",
        api_key=os.environ.get("GATEWAY_API_KEY", "anything"),
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Task:\n{task_prompt}\n\n"
                f"Answer A:\n{source_answer}\n\n"
                f"Answer B:\n{target_answer}\n\nVerdict:",
            },
        ],
        **kwargs,
    )
    return parse_verdict(response.choices[0].message.content)


def last_user_content(messages: list) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content") or ""
    return ""


def evaluate(conn, source_model: str, target_model: str, gateway: str, days: int, sample_n: int, judge_model: str = None, **replay_kwargs):
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
        verdict = None
        if judge_model and error is None:
            try:
                verdict = judge_pair(
                    last_user_content(messages), row["response"], replayed_text,
                    judge_model, gateway, **replay_kwargs,
                )
            except Exception as exc:
                error = f"judge: {exc}"
        results.append(
            {
                "request_id": row["id"],
                "category": category,
                "source_cost_usd": row["cost_usd"],
                "target_cost_usd": replayed_cost,
                "similarity": similarity(row["response"], replayed_text) if error is None else 0.0,
                "verdict": verdict,
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
        judged = [i for i in items if i.get("verdict")]
        aggregated[category] = {
            "n": n,
            "mean_similarity": round(sum(i["similarity"] for i in items) / n, 4),
            "mean_source_cost_usd": round(sum(i["source_cost_usd"] for i in items) / n, 6),
            "mean_target_cost_usd": round(
                sum(i["target_cost_usd"] or 0 for i in items) / n, 6
            ),
            "errors": sum(1 for i in items if i["error"]),
            "pass_rate": round(
                sum(1 for i in judged if i["verdict"] == "equivalent") / len(judged), 4
            )
            if judged
            else None,
        }
    return aggregated


def decide_status(agg: dict, similarity_threshold: float, min_samples: int,
                  pass_threshold: float = DEFAULT_PASS_THRESHOLD) -> str:
    """"estimated" means inconclusive here (not enough evidence yet to
    move off the table's default), distinct from a positive validation.
    When judge verdicts are present (pass_rate) they override the
    difflib similarity — the heuristic produces false rejections on
    verbose-but-correct answers (see judge_calibration.json)."""
    if agg["n"] < min_samples or agg["errors"] == agg["n"]:
        return "estimated"
    if agg["mean_target_cost_usd"] > agg["mean_source_cost_usd"]:
        return "rejected"
    if agg.get("pass_rate") is not None:
        return "validated" if agg["pass_rate"] >= pass_threshold else "rejected"
    return "validated" if agg["mean_similarity"] >= similarity_threshold else "rejected"


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


def update_delegation_table(path: Path, date: str, source_model: str, target_model: str, aggregated: dict, statuses: dict, judge_model: str = None):
    text = path.read_text(encoding="utf-8")
    entries = []
    for category, task_type in CATEGORY_TO_TASK_TYPE.items():
        if category not in aggregated:
            continue
        agg = aggregated[category]
        status = statuses[category]
        judged = (
            f"  judge={judge_model} pass_rate={agg['pass_rate']:.2f}"
            if judge_model and agg.get("pass_rate") is not None
            else ""
        )
        entries.append(
            f"{date}  category={category}  source={source_model} target={target_model}"
            f"  n={agg['n']}  sim={agg['mean_similarity']:.2f}{judged}"
            f"  cost_source=${agg['mean_source_cost_usd']:.4f}"
            f" cost_target=${agg['mean_target_cost_usd']:.4f}  -> {status}"
        )
        if status in ("validated", "rejected"):
            text = update_table_status(text, task_type, status)
    if entries:
        text = append_evidence_log(text, entries)
    path.write_text(text, encoding="utf-8")


def calibrate(pairs: list, judge_model: str, gateway: str, **kwargs) -> dict:
    """Runs the judge on manually labeled pairs (judge_calibration.json)
    and reports agreement with the human labels. The judge must
    reproduce them before its verdicts are trusted in --update-table."""
    agreements, mismatches = 0, []
    for i, pair in enumerate(pairs):
        verdict = judge_pair(
            pair["prompt"], pair["source_response"], pair["target_response"],
            judge_model, gateway, **kwargs,
        )
        if verdict == pair["verdict"]:
            agreements += 1
        else:
            mismatches.append(
                {"index": i, "category": pair.get("category"),
                 "expected": pair["verdict"], "got": verdict,
                 "prompt": pair["prompt"][:80]}
            )
    return {"n": len(pairs), "agreements": agreements, "mismatches": mismatches}


def format_report(source_model, target_model, aggregated, statuses) -> str:
    lines = [f"SHADOW EVALUATION: {source_model} -> {target_model}", ""]
    if not aggregated:
        lines.append(f"  no successful {source_model!r} requests in range")
        return "\n".join(lines)
    for category, agg in sorted(aggregated.items()):
        mapped = CATEGORY_TO_TASK_TYPE.get(category, "(unmapped, table not updated)")
        judged = (
            f" pass_rate={agg['pass_rate']:.0%}" if agg.get("pass_rate") is not None else ""
        )
        lines.append(
            f"  {category} [{mapped}]: n={agg['n']} sim={agg['mean_similarity']:.0%}{judged}"
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
    parser.add_argument("--judge-model", help="gateway alias for the LLM judge; overrides difflib similarity")
    parser.add_argument("--pass-threshold", type=float, default=DEFAULT_PASS_THRESHOLD,
                        help="min share of 'equivalent' judge verdicts for 'validated'")
    parser.add_argument("--calibrate", metavar="PAIRS_JSON",
                        help="run --judge-model on labeled pairs and report agreement; no replay")
    parser.add_argument("--update-table", action="store_true")
    parser.add_argument(
        "--table",
        default=Path(__file__).parent.parent / "DELEGATION_TABLE.md",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.calibrate:
        if not args.judge_model:
            raise SystemExit("--calibrate requires --judge-model")
        pairs = json.loads(Path(args.calibrate).read_text(encoding="utf-8"))
        report = calibrate(pairs, args.judge_model, args.gateway)
        print(f"JUDGE CALIBRATION: {args.judge_model} on {report['n']} labeled pairs")
        print(f"  agreement: {report['agreements']}/{report['n']}")
        for m in report["mismatches"]:
            print(
                f"  MISMATCH #{m['index']} [{m['category']}]"
                f" expected={m['expected']} got={m['got']} :: {m['prompt']}"
            )
        return

    if not Path(args.db).exists():
        raise SystemExit(f"request log not found: {args.db}")
    if args.source_model == args.target_model:
        raise SystemExit(
            "source and target model must differ: comparing a model to itself"
            " is not evidence a cheaper tier can substitute for it"
        )

    conn = sqlite3.connect(args.db)
    results = evaluate(conn, args.source_model, args.target_model, args.gateway,
                       args.days, args.sample, judge_model=args.judge_model)
    aggregated = aggregate_by_category(results)
    statuses = {
        category: decide_status(agg, args.threshold, args.min_samples, args.pass_threshold)
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
            judge_model=args.judge_model,
        )


if __name__ == "__main__":
    main()
