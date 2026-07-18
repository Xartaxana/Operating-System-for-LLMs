"""Shadow-replay harness for Lead-tier dispatch_skipped work (D-0080 п.3).

Reuses gateway/shadow_eval.py's proxy-facing primitives (replay(),
judge_pair(), parse_verdict(), append_evidence_log()) instead of
duplicating them: this module owns only the git-corpus plumbing --
loading gateway/lead_replay_corpus.jsonl, pulling each candidate's
pre-image and reference (git-diff ground truth) out of the repo, and
formatting/recording the evidence lines -- never a request to the
gateway that bypasses shadow_eval's own two functions (D-0075).

Ground truth here is NOT the source model's own answer (shadow_eval's
usual A side) but the actual git diff Lead produced for the commit --
"source=git-lead" in every evidence line marks that difference. Answer
A = the unified diff from `git show <hash> -- <paths>`; Answer B = the
target model's from-scratch attempt at the same task, given only the
pre-image (files as they stood before the commit) and the corpus
draft prompt.

Usage:
    python lead_replay.py --dry-run
    python lead_replay.py --record-evidence
    python lead_replay.py --only 1,4 --target-model lead-sonnet
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import shadow_eval

# Both streams: candidate prompts/diffs are Cyrillic and go to both stdout
# and stderr (adversarial-battery error messages too) -- without
# reconfigure, some Windows consoles corrupt them (same class as
# tools/mechanism_gate.py's fix, discovered empirically while producing
# this module's own --dry-run witness output: a bare cp1251 stdout showed
# readable text on screen but the byte stream itself was mojibake once
# captured/piped -- reconfiguring to utf-8 fixed it). errors="replace"
# (not the bare default "strict") avoids a second-order UnicodeEncodeError
# on an even narrower console; the CLI prints diagnostic text, not binary
# data, so a replaced character costs nothing but readability at the margin.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_PATH = Path(__file__).parent / "lead_replay_corpus.jsonl"
DEFAULT_SHADOW_LOG_PATH = REPO_ROOT / "docs" / "SHADOW_EVALUATION_LOG.md"
DEFAULT_GATEWAY = "http://localhost:4000"
DEFAULT_TARGET_MODEL = "lead-sonnet"
DEFAULT_JUDGE_MODEL = "judge-gemini"
DEFAULT_PACE = 13.0
DEFAULT_MAX_TOKENS = 8192

REQUIRED_CANDIDATE_FIELDS = ("task", "commit", "kind", "prompt", "paths")

_DISPLAY_TRUNCATE_CHARS = 2000


class LeadReplayError(Exception):
    """Expected, reportable failure (bad corpus, missing commit, unreachable
    gateway) -- callers surface str(exc) to the user instead of a
    traceback (routing policy rule 11 adversarial-battery requirement)."""


# --- git plumbing ----------------------------------------------------------


def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def validate_commit(commit_hash: str) -> None:
    """Raises LeadReplayError if commit_hash does not resolve to a real
    commit in this repo -- called before any per-path git-show, so a typo'd
    or missing hash fails once, clearly, instead of surfacing as N mysterious
    per-path pre-image failures."""
    result = _git("cat-file", "-e", f"{commit_hash}^{{commit}}")
    if result.returncode != 0:
        raise LeadReplayError(f"commit not found: {commit_hash!r}")


def git_preimage(commit_hash: str, path: str) -> str | None:
    """Content of path as it stood immediately BEFORE commit_hash (i.e. in
    commit_hash^). Returns None for a path that did not exist in the parent
    commit -- the new-file case (corpus candidate #1, t-040): callers must
    treat None as "new file, empty pre-image", not as an extraction error."""
    result = _git("show", f"{commit_hash}^:{path}")
    if result.returncode != 0:
        return None
    return result.stdout


def git_reference_diff(commit_hash: str, paths: list) -> str:
    """Unified diff for exactly `paths` within commit_hash -- the ground
    truth Answer A. Raises LeadReplayError (not a silent empty string) if
    git itself fails, or if it succeeded but produced no diff body at all
    (a path list that doesn't intersect the commit is a corpus bug, not a
    legitimate empty result)."""
    result = _git("show", commit_hash, "--", *paths)
    if result.returncode != 0:
        raise LeadReplayError(
            f"git show failed for commit {commit_hash!r} paths {paths}: "
            f"{result.stderr.strip()}"
        )
    if not result.stdout.strip():
        raise LeadReplayError(
            f"empty reference diff for commit {commit_hash!r} paths {paths}"
            " (paths do not intersect this commit's changes)"
        )
    return result.stdout


# --- corpus loading ----------------------------------------------------------


def load_corpus(path) -> list:
    path = Path(path)
    if not path.exists():
        raise LeadReplayError(f"corpus file not found: {path}")
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise LeadReplayError(f"corpus file is empty: {path}")
    candidates = []
    for i, line in enumerate(lines, start=1):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LeadReplayError(
                f"corpus file {path} line {i}: invalid JSON ({exc})"
            ) from exc
        if not isinstance(candidate, dict):
            raise LeadReplayError(
                f"corpus file {path} line {i}: expected a JSON object, got {type(candidate).__name__}"
            )
        missing = [f for f in REQUIRED_CANDIDATE_FIELDS if f not in candidate]
        if missing:
            raise LeadReplayError(
                f"corpus file {path} line {i}: missing field(s) {missing}"
            )
        candidates.append(candidate)
    return candidates


def select_candidates(candidates: list, only: str = None) -> list:
    """only: comma-separated subset of candidate 'task' ids. Raises
    LeadReplayError naming the specific unknown id(s) instead of silently
    returning an empty/partial list."""
    if not only:
        return candidates
    wanted = {token.strip() for token in only.split(",") if token.strip()}
    by_task = {c["task"]: c for c in candidates}
    missing = wanted - set(by_task)
    if missing:
        raise LeadReplayError(f"--only requested unknown task id(s): {sorted(missing)}")
    return [by_task[task] for task in by_task if task in wanted]


# --- prompt assembly ----------------------------------------------------------


def build_target_prompt(candidate: dict, preimages: dict) -> list:
    """messages for the target model: the corpus draft prompt + each
    affected path's pre-image ("дано"), with an explicit instruction to
    return changed/new files IN FULL (not a diff) -- the target has no git
    access, so a diff-shaped reply would be unusable as an Answer B."""
    parts = [candidate["prompt"], ""]
    parts.append(
        "Ниже — текущее содержимое затронутых файлов (до изменения). "
        "Для новых файлов пре-имидж пуст (файл ещё не существует)."
    )
    for path in candidate["paths"]:
        content = preimages.get(path)
        if content is None:
            parts.append(f"=== {path} (новый файл, пусто) ===\n")
        else:
            parts.append(f"=== {path} ===\n{content}")
    parts.append(
        "Верни изменённые/новые файлы ЦЕЛИКОМ (полное содержимое каждого "
        "файла после правки, не диф), с явным указанием пути перед "
        "содержимым каждого файла."
    )
    return [{"role": "user", "content": "\n\n".join(parts)}]


def _truncate_for_display(text, limit: int = _DISPLAY_TRUNCATE_CHARS) -> str:
    """Console-only truncation for --dry-run output (a multi-MB pre-image
    or reference diff must not flood the terminal or otherwise misbehave --
    routing policy rule 11 adversarial battery, 'гигантский дифф'). The
    underlying data handed to build_target_prompt/replay/judge_pair is
    NEVER truncated -- only what gets printed here."""
    if text is None:
        return "(new file, no pre-image)"
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [truncated for display, {len(text)} chars total]"


# --- per-candidate run ----------------------------------------------------------


def run_candidate(candidate: dict, target_model: str, judge_model: str, gateway: str,
                  db_path=None, max_tokens: int = DEFAULT_MAX_TOKENS, **kwargs) -> dict:
    """Runs one candidate end-to-end: git extraction, target replay() call,
    judge_pair() call against the git-diff ground truth. verdict is one of
    'equivalent' | 'worse' | 'error' (never shadow_eval's raw
    'target_worse' -- mapped here to match this module's own evidence-line
    vocabulary)."""
    validate_commit(candidate["commit"])
    preimages = {path: git_preimage(candidate["commit"], path) for path in candidate["paths"]}
    reference = git_reference_diff(candidate["commit"], candidate["paths"])
    messages = build_target_prompt(candidate, preimages)

    error = None
    target_text, target_cost, truncated = None, None, False
    try:
        target_text, target_cost, finish_reason = shadow_eval.replay(
            messages, target_model, gateway, db_path=db_path,
            max_tokens=max_tokens, **kwargs,
        )
        truncated = finish_reason == "length"
    except Exception as exc:
        error = str(exc)

    verdict, judge_cost = "error", None
    if error is None:
        try:
            raw_verdict, judge_cost = shadow_eval.judge_pair(
                candidate["prompt"], reference, target_text,
                judge_model, gateway, db_path=db_path, **kwargs,
            )
            verdict = {"equivalent": "equivalent", "target_worse": "worse"}.get(raw_verdict, "error")
        except Exception as exc:
            error = f"judge: {exc}"
            verdict = "error"

    return {
        "task": candidate["task"],
        "commit": candidate["commit"],
        "kind": candidate["kind"],
        "verdict": verdict,
        "target_cost_usd": target_cost,
        "judge_cost_usd": judge_cost,
        "truncated": truncated,
        "error": error,
    }


# --- evidence formatting ----------------------------------------------------------


def _fmt_cost(cost) -> str:
    return f"${cost:.4f}" if cost is not None else "$unknown"


def format_candidate_line(date: str, result: dict, target_model: str, judge_model: str) -> str:
    """One line per candidate. Deliberately does NOT start with 'category='
    right after the date (metrics._SHADOW_EVAL_LINE_RE anchors on that) --
    'shadow-replay' occupies that slot instead, so this line can never be
    mistaken for a shadow_eval.py evidence line by the calibration parser."""
    return (
        f"{date}  shadow-replay  task={result['task']} commit={result['commit']}"
        f" kind={result['kind']}  source=git-lead target={target_model}"
        f"  verdict={result['verdict']}  judge={judge_model}"
        f" cost_target={_fmt_cost(result['target_cost_usd'])}"
        f" judge_cost={_fmt_cost(result['judge_cost_usd'])}"
        f"  truncated={int(bool(result['truncated']))}"
    )


def format_summary_line(date: str, target_model: str, judge_model: str, results: list) -> str:
    n = len(results)
    equivalent_n = sum(1 for r in results if r["verdict"] == "equivalent")
    # N1 (critic t-180): verdict=="error" покрывает и непарсимый вердикт судьи
    # при error=None -- иначе SUMMARY показал бы errors=0 при error-строках
    # кандидатов, вводя калибратора в заблуждение.
    errors = sum(1 for r in results if r["error"] is not None or r["verdict"] == "error")
    truncated_total = sum(1 for r in results if r["truncated"])
    cost_target_total = sum(r["target_cost_usd"] or 0 for r in results)
    judge_cost_total = sum(r["judge_cost_usd"] or 0 for r in results)
    return (
        f"{date}  shadow-replay SUMMARY  source=git-lead target={target_model}"
        f"  n={n}  equivalent={equivalent_n}/{n}  judge={judge_model}"
        f"  cost_target_total=${cost_target_total:.4f}"
        f" judge_cost_total=${judge_cost_total:.4f}"
        f"  errors={errors} truncated={truncated_total}"
    )


def append_replay_evidence(text: str, date: str, target_model: str, entries: list) -> str:
    """Appends entries (candidate lines + summary line, already formatted)
    under a fresh '### SHADOW-REPLAY D-0080 п.3 (...)' subheading, at the
    tail of docs/SHADOW_EVALUATION_LOG.md. Reuses shadow_eval's own H1
    ensure-logic (append_evidence_log with an empty entries list touches
    only the heading) so a fresh/empty log file still ends up with the
    correct '# Shadow Evaluation Log' H1 shadow_eval/metrics both key off
    of, without this module reimplementing that heading-creation branch."""
    text = shadow_eval.append_evidence_log(text, [])
    subheader = (
        f"### SHADOW-REPLAY D-0080 п.3 ({date}, target={target_model}, "
        "ground truth = git-дифф Lead)"
    )
    lines = text.splitlines()
    lines.append("")
    lines.append(subheader)
    lines.append("")
    for entry in entries:
        lines.append(f"- {entry}")
    return "\n".join(lines) + "\n"


def record_replay_evidence(shadow_log_path, date: str, target_model: str, entries: list) -> None:
    shadow_log_path = Path(shadow_log_path)
    log_text = shadow_log_path.read_text(encoding="utf-8") if shadow_log_path.exists() else ""
    log_text = append_replay_evidence(log_text, date, target_model, entries)
    shadow_log_path.write_text(log_text, encoding="utf-8")


# --- dry-run reporting ----------------------------------------------------------


def dry_run_report(candidate: dict) -> str:
    validate_commit(candidate["commit"])
    preimages = {path: git_preimage(candidate["commit"], path) for path in candidate["paths"]}
    reference = git_reference_diff(candidate["commit"], candidate["paths"])
    messages = build_target_prompt(candidate, preimages)
    prompt_text = messages[0]["content"]

    lines = [
        f"=== task={candidate['task']} commit={candidate['commit']} kind={candidate['kind']} ===",
        f"paths: {candidate['paths']}",
        f"draft prompt: {candidate['prompt']}",
        "reference diff (git show, ground truth):",
        _truncate_for_display(reference),
        "assembled target prompt:",
        _truncate_for_display(prompt_text),
    ]
    return "\n".join(lines)


# --- CLI ----------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Shadow-replay Lead-tier dispatch_skipped work against its own git diff (D-0080 п.3)"
    )
    parser.add_argument("--target-model", default=DEFAULT_TARGET_MODEL)
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    parser.add_argument("--pace", type=float, default=DEFAULT_PACE,
                        help="seconds between candidate pairs (free-tier RPM ceilings)")
    parser.add_argument("--record-evidence", action="store_true",
                        help="append run evidence to docs/SHADOW_EVALUATION_LOG.md")
    parser.add_argument("--dry-run", action="store_true",
                        help="show candidates, paths, reference diffs and assembled"
                             " prompts WITHOUT live model calls")
    parser.add_argument("--only", help="comma-separated subset of candidate task ids")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY)
    parser.add_argument(
        "--db", default=os.environ.get("GATEWAY_DB_PATH", Path(__file__).parent / "requests.db"),
    )
    parser.add_argument("--corpus", default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--shadow-log", default=DEFAULT_SHADOW_LOG_PATH)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    args = parser.parse_args()

    try:
        candidates = select_candidates(load_corpus(args.corpus), args.only)

        if args.dry_run:
            for candidate in candidates:
                print(dry_run_report(candidate))
                print()
            return

        date = datetime.date.today().isoformat()
        results = []
        for i, candidate in enumerate(candidates):
            if i and args.pace:
                time.sleep(args.pace)
            result = run_candidate(
                candidate, args.target_model, args.judge_model, args.gateway,
                db_path=args.db, max_tokens=args.max_tokens,
            )
            results.append(result)
            line = format_candidate_line(date, result, args.target_model, args.judge_model)
            print(line)
            if result["error"]:
                print(f"  error: {result['error']}")
    except LeadReplayError as exc:
        raise SystemExit(f"lead_replay: {exc}")

    summary = format_summary_line(date, args.target_model, args.judge_model, results)
    print(summary)

    if args.record_evidence:
        entries = [
            format_candidate_line(date, r, args.target_model, args.judge_model)
            for r in results
        ] + [summary]
        record_replay_evidence(args.shadow_log, date, args.target_model, entries)


if __name__ == "__main__":
    main()
