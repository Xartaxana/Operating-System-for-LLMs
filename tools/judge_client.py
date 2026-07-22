"""Snapshot from exam_hybrid_kit/tools/judge_client.py, 2026-07-22
(D-0081 batch item е): staffed operational detail of R13 (CLAUDE.md) --
the coordinator of a live session has nothing to call as a judge, so
this module gives it a plain HTTP client for the gateway-alias judge
form (judge-sonnet et al.), independent of the litellm SDK. Adapted
verbatim from the kit copy; no path/import changes were needed --
DEFAULT_GATEWAY, GATEWAY_API_KEY and the gateway/config.yaml
judge-sonnet alias this docstring references all match this repo's own
conventions (verified by reading gateway/shadow_eval.py and
gateway/config.yaml).

Original docstring follows.

---

Judge client (t-239, D-arm economy-exam orchestration): asks
judge-sonnet (calibrated 13/13, 2026-07-20 -- gateway/config.yaml) to
accept/reject one D-arm cell against a task's intent-keys, through the
litellm gateway's OpenAI-compatible /v1/chat/completions endpoint.

Uses stdlib urllib only -- no litellm import needed for a single chat
completion (spec: "litellm не нужен"). Judge cost lands in the Ledger
like every other judge call (gateway/shadow_eval.py's judge_pair is
the precedent this mirrors): metadata.traffic_kind = "judge" travels
in the JSON body's top-level "metadata" field -- the same field
gateway/sqlite_logger.py's callback reads via
`metadata.get("traffic_kind")`. No "openai/" model prefix here: that
prefix in shadow_eval.py's `litellm.completion(model="openai/...")` is
a litellm-SDK-only routing hint for its own client (telling it "call
an OpenAI-compatible api_base"), stripped before litellm builds the
wire body -- a raw HTTP call sends the bare alias "judge-sonnet" as
the JSON "model" field directly, matching gateway/config.yaml's
registered model_name (verified by reading gateway/shadow_eval.py's
replay()/judge_pair() docstrings and gateway/sqlite_logger.py's
traffic_kind read -- read beyond this task's given basket, reported in
the builder report).
"""

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_GATEWAY = "http://localhost:4000"
DEFAULT_MODEL = "judge-sonnet"

# Material cap (spec: "суммарный кап ~40К символов, при переполнении --
# усечение с пометкой"). Kept as a module constant so tests can pass a
# smaller cap to exercise the boundary without building a 40K-char fixture.
MATERIAL_CHAR_CAP = 40_000

# Directories never worth showing the judge (spec: "без venv/node_modules/
# .git"); __pycache__/.pytest_cache added for the same noise reason
# tools/exam_runner.py already excludes them from its own file-set diffs
# (SKIP_DIR_PARTS).
EXCLUDE_DIR_NAMES = {".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache"}

JUDGE_INSTRUCTION = (
    'Верни СТРОГО JSON {"accept": true|false, "feedback": "..."} и ничего '
    'кроме него. feedback при reject -- КОНКРЕТНЫЙ дефект сдачи (что именно '
    'не так в этой клетке), НЕ пересказ полного чек-листа ключей.'
)


class JudgeParseError(RuntimeError):
    """Raised when the judge's reply is not parseable as the required
    {"accept": bool, "feedback": str} JSON even after one retry call
    (spec: 'непарсибельный ответ = повторный вызов один раз, затем
    честная ошибка')."""


# ---------------------------------------------------------------------------
# material assembly (file tree + capped file contents)
# ---------------------------------------------------------------------------


def _iter_cell_files(cell_dir):
    """Sorted (rel_path, abs_path) pairs for every file under cell_dir,
    skipping EXCLUDE_DIR_NAMES at any depth. Deterministic order (sorted
    rglob) so build_material's truncation point is reproducible."""
    cell_dir = Path(cell_dir)
    if not cell_dir.exists():
        return []
    out = []
    for p in sorted(cell_dir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(cell_dir)
        if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
            continue
        out.append((rel, p))
    return out


# Sentinel distinct from `None`: build_material()/judge_verdict()'s
# baseline_files default. A caller that omits the argument entirely
# (every pre-blocker-3 call site and test) gets the byte-identical old
# behavior -- unfiltered material, no marker. Passing `None` EXPLICITLY
# means "checked, baseline_manifest.json is unavailable" (darm_orchestrator
# does this on purpose) -- same unfiltered listing, but with an explicit
# fallback marker in the material (spec block 3: "фолбэк на текущее
# поведение с явной пометкой"). Passing an actual set enables the
# exclusion filter.
_BASELINE_UNSET = object()

BASELINE_UNAVAILABLE_MARKER = (
    "(!) baseline_manifest.json недоступен -- материал показан без "
    "фильтрации клон-файлов (текущее поведение, фолбэк)"
)


def build_material(cell_dir, char_cap=MATERIAL_CHAR_CAP, baseline_files=_BASELINE_UNSET):
    """Renders the cell's file tree plus file contents into one string,
    capped at char_cap total characters. Once the running length would
    exceed the cap, the current file is cut short (if any budget remains)
    and a single truncation marker line replaces everything after it --
    never a silent stop (spec: "при переполнении -- усечение с пометкой").

    baseline_files (blocker 3, D-0043-class fix of run#3 C/t2's clone
    swamping the material): a set of rel-path strings (POSIX, as written
    by tools/exam_runner.py's prepare() into baseline_manifest.json) to
    EXCLUDE from both the tree listing and the content dump -- these are
    files the polygon assembly put there (e.g. a needs=click clone),
    not the session's own deliverable. Omitting the argument entirely
    (baseline_files left at its _BASELINE_UNSET default) reproduces the
    exact pre-blocker-3 behavior byte-for-byte (no filtering, no marker)
    so every existing caller/test that never mentions baseline_files is
    unaffected. Passing baseline_files=None explicitly means "checked,
    no baseline_manifest.json available" -- unfiltered listing PLUS an
    explicit BASELINE_UNAVAILABLE_MARKER line (spec: fallback with a
    visible note, not a silent one). Passing an actual set (possibly
    empty) filters exactly those rel-paths out of the tree/content --
    and, when that set is non-empty, adds ONE extra line naming exactly
    those excluded rel-paths ("UNCHANGED BASELINE (excluded from
    listing): a, b, ..."), t-245 fix: without this line the judge sees
    no trace at all of an excluded-but-untouched baseline file and can
    mistake "not in the listing" for "not on disk" (the darm_log.json
    run#1 t3 forensics: the judge rejected retry1/esc1 twice with
    "README.md отсутствует" even though README.md was a genuinely
    untouched baseline reference, correctly excluded, but invisible).
    An empty exclusion set adds no line at all (nothing was excluded,
    nothing to name).

    A file that is not valid UTF-8 is decoded with errors='replace'
    (adversarial case: this function never raises on file content, only
    a missing/unreadable file falls back to a placeholder line).

    An empty cell (no files at all, OR nothing left after baseline
    filtering, adversarial case either way) still returns a valid,
    non-crashing material string carrying an explicit "(empty cell --
    no files found)" marker instead of an empty tree.

    Returns (material_str, truncated_bool).
    """
    entries = _iter_cell_files(cell_dir)

    baseline_note = None
    if baseline_files is _BASELINE_UNSET:
        pass  # old behavior: no filtering, no marker
    elif baseline_files is None:
        baseline_note = BASELINE_UNAVAILABLE_MARKER
    else:
        baseline_set = set(baseline_files)
        entries = [
            (rel, path) for rel, path in entries
            if str(rel).replace("\\", "/") not in baseline_set
        ]
        if baseline_set:
            baseline_note = (
                "UNCHANGED BASELINE (excluded from listing): "
                + ", ".join(sorted(baseline_set))
            )

    tree_lines = ["FILE TREE:"]
    if baseline_note:
        tree_lines.append(baseline_note)
    if entries:
        tree_lines.extend(str(rel).replace("\\", "/") for rel, _ in entries)
    else:
        tree_lines.append("(empty cell -- no files found)")
    header = "\n".join(tree_lines) + "\n\n"

    parts = [header]
    used = len(header)
    truncated = False

    for rel, path in entries:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            text = f"<could not read file: {exc}>"
        rel_str = str(rel).replace("\\", "/")
        block = f"=== {rel_str} ===\n{text}\n"

        if used + len(block) > char_cap:
            budget = char_cap - used
            if budget > 0:
                parts.append(block[:budget])
                used += budget
            parts.append(
                f"\n[... material cap {char_cap} chars reached; "
                f"remaining files/content truncated ...]"
            )
            truncated = True
            break

        parts.append(block)
        used += len(block)

    return "".join(parts), truncated


def build_prompt(task_id, task_text, intent_keys, material, stdout_tail):
    keys_block = "\n".join(f"- {k}" for k in intent_keys) if intent_keys else "(нет ключей)"
    return (
        f"Задача {task_id}:\n{task_text}\n\n"
        f"Ключи приёмки (интент, дословно из набора):\n{keys_block}\n\n"
        f"Материал клетки (дерево файлов + содержимое):\n{material}\n\n"
        f"Хвост stdout сессии:\n{stdout_tail if stdout_tail else '(пусто)'}\n\n"
        f"{JUDGE_INSTRUCTION}"
    )


# ---------------------------------------------------------------------------
# HTTP call (stdlib only) + verdict parsing
# ---------------------------------------------------------------------------


def _post_chat_completion(prompt, gateway, model, api_key, timeout=120):
    """One POST to <gateway>/v1/chat/completions, stdlib urllib only.
    Returns {"content": str, "usage": {"prompt_tokens", "completion_tokens",
    "total_tokens"}, "cost_usd": float|None, "cost_source": "header"|"body"|
    "none"} (blocker 4: the judge call's own usage/cost, captured from THIS
    single response -- never a second call, so cost is never doubled).
    cost_usd prefers the response's x-litellm-response-cost header (the
    authoritative per-call price litellm attaches); falls back to a
    body-level "cost"/"response_cost" field; otherwise usage is returned
    without a price and cost_source is "none" (never invented as 0).
    Raises on transport or non-2xx errors (urllib.error.*), left to the
    caller."""
    url = gateway.rstrip("/") + "/v1/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "metadata": {"traffic_kind": "judge"},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        cost_header = resp.headers.get("x-litellm-response-cost")
        payload = json.loads(resp.read().decode("utf-8"))

    content = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage") or {}

    cost_usd = None
    cost_source = "none"
    if cost_header is not None:
        try:
            cost_usd = float(cost_header)
            cost_source = "header"
        except (TypeError, ValueError):
            cost_usd = None
    if cost_usd is None:
        body_cost = payload.get("cost")
        if body_cost is None:
            body_cost = payload.get("response_cost")
        if body_cost is not None:
            try:
                cost_usd = float(body_cost)
                cost_source = "body"
            except (TypeError, ValueError):
                cost_usd = None

    return {
        "content": content,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "cost_usd": cost_usd,
        "cost_source": cost_source,
    }


_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_verdict(text):
    """Best-effort extraction of {"accept": bool, "feedback": str} from
    the judge's raw reply: try the whole trimmed text as JSON first
    (the common case), then fall back to the largest {...} substring
    (a judge that wraps the JSON in prose or a markdown fence). Returns
    None (not a JudgeParseError) when nothing usable was found -- the
    caller decides retry vs. final failure."""
    if not text:
        return None

    obj = None
    try:
        obj = json.loads(text.strip())
    except (json.JSONDecodeError, TypeError):
        obj = None

    if not isinstance(obj, dict):
        match = _JSON_OBJ_RE.search(text)
        if match:
            try:
                candidate = json.loads(match.group(0))
            except json.JSONDecodeError:
                candidate = None
            if isinstance(candidate, dict):
                obj = candidate

    if not isinstance(obj, dict) or "accept" not in obj:
        return None
    return {"accept": bool(obj["accept"]), "feedback": str(obj.get("feedback", ""))}


def _sum_usage(calls):
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for call in calls:
        usage = call.get("usage") or {}
        for key in total:
            total[key] += usage.get(key) or 0
    return total


def _sum_cost(calls):
    """(cost_usd_or_None, cost_source) summed across calls -- cost_usd
    is None only when NONE of the calls carried a price (never invented
    as 0, spec point (c): a silent zero is worse than an honest None);
    cost_source is the single source name when all calls agree, else
    "+"-joined (mixed header/body/none across the internal parse-retry,
    an edge case worth surfacing rather than hiding)."""
    have_cost = [c["cost_usd"] for c in calls if c.get("cost_usd") is not None]
    total_cost = sum(have_cost) if have_cost else None
    sources = sorted({c.get("cost_source", "none") for c in calls})
    cost_source = sources[0] if len(sources) == 1 else "+".join(sources)
    return total_cost, cost_source


def judge_verdict(
    task_id,
    task_text,
    intent_keys,
    cell_dir,
    stdout_tail,
    baseline_files=_BASELINE_UNSET,
    gateway=None,
    model=None,
    api_key=None,
    char_cap=MATERIAL_CHAR_CAP,
    _post_fn=None,
):
    """Returns {"accept": bool, "feedback": str, "truncated": bool,
    "usage": {...}, "cost_usd": float|None, "cost_source": str} for one
    D-arm cell.

    baseline_files: forwarded to build_material() unchanged (see its
    docstring) -- omit entirely for the old unfiltered behavior, pass
    None for an explicit "baseline unavailable" marker, or a set to
    exclude those rel-paths from the judge's material (blocker 3).

    "truncated" (item 7) mirrors build_material()'s own truncated flag
    -- surfaced on the verdict so callers can persist it into the
    darm_log attempt record for audit, not just as a marker buried in
    the prompt text.

    "usage"/"cost_usd"/"cost_source" (blocker 4): SUMMED across every
    HTTP call this single judge_verdict() invocation made (normally
    one; two when the first reply was unparseable and the retry
    succeeded) -- one call's cost must count once, and a retry's cost
    must not be silently dropped either.

    _post_fn (test seam): callable(prompt, gateway, model, api_key) ->
    {"content": str, "usage": {...}, "cost_usd": float|None,
    "cost_source": str}, replacing the real HTTP call. Production
    callers never pass it (defaults to _post_chat_completion).

    Retry policy (spec): an unparseable judge reply triggers exactly ONE
    extra call with the SAME prompt; if that also fails to parse,
    raises JudgeParseError -- never a silent accept or reject."""
    gateway = gateway or os.environ.get("GATEWAY_URL", DEFAULT_GATEWAY)
    model = model or DEFAULT_MODEL
    api_key = api_key or os.environ.get("GATEWAY_API_KEY", "anything")
    post_fn = _post_fn or _post_chat_completion

    material, truncated = build_material(cell_dir, char_cap=char_cap, baseline_files=baseline_files)
    prompt = build_prompt(task_id, task_text, intent_keys, material, stdout_tail)

    calls = []
    parsed = None
    last_raw = None
    for _attempt in range(2):
        raw = post_fn(prompt, gateway, model, api_key)
        calls.append(raw)
        last_raw = raw
        parsed = _extract_verdict(raw["content"])
        if parsed is not None:
            break

    if parsed is None:
        raise JudgeParseError(
            f"judge response unparseable after retry for task {task_id!r}: "
            f"{last_raw['content']!r}"
        )

    usage = _sum_usage(calls)
    cost_usd, cost_source = _sum_cost(calls)
    return {
        "accept": parsed["accept"],
        "feedback": parsed["feedback"],
        "truncated": truncated,
        "usage": usage,
        "cost_usd": cost_usd,
        "cost_source": cost_source,
    }
