"""Economy exam runner (t-117): drives an economy-exam polygon
(PROCESS/DEPLOYMENT_ECONOMY_EXAM.md) through prepare -> run -> collect
without operator hand-manipulation, given a run-manifest JSON.

CLI:
    python tools/exam_runner.py <prepare|run|collect|all> --manifest <path.json> [--dry-run]

Design notes (spec: Lead-accepted spec for the economy-exam-runner
task, 2026-07-15):

- Reuses tools/usage_report.py's import_transcripts()/db_path()/
  transcript_glob()/SCHEMA by import, not copy (SIBLING_MAP axis 2 --
  the manifest given a reuse instruction explicitly).
- No verdicts and no PROCESS/DEPLOYMENT_ECONOMY_EXAM.md Runs-log write
  here -- collect() only produces <polygon_root>/dossier.{md,json};
  acceptance/verdicts stay with Lead (non-goal, spec).
- prepare()'s git operations (clone+checkout) work identically against
  a real remote URL or a local filesystem path -- `git clone <path>
  <dest>` is a fully local operation with no network I/O, which is how
  tests exercise the exact same code path with fixture-factory local
  repos instead of mocking git out (spec's "мокнуть/обойти
  параметром" is satisfied by "мокнуть": the fake local repos ARE the
  mock, no separate bypass flag was needed).
- project_slug() mirrors Claude Code's ~/.claude/projects directory-
  naming scheme (see its own docstring for the empirical verification
  against real exam_release2 project dirs on this machine -- read
  beyond the manifest's read-only 'given' bucket, reported as such in
  the builder report).
- t-132 (multi-session task, spec
  docs/tasks/2026-07-15_economy-exam-set2.md): a task may carry
  'sessions': [text, ...] instead of 'text' -- N SEPARATE headless
  `claude -p` sessions run SEQUENTIALLY in the one (task, arm) sandbox
  cwd, session N+1 starting only after session N's rc is known. A
  non-zero rc stops the chain by default (no "continue on error"
  flag -- YAGNI, spec). Each session is a fresh process, not
  --continue/--resume (spec: a returning user opens a new chat; state
  lives in the sandbox's files, not session memory). The classic
  single-'text' task's run_log/stdout-file shape is unchanged
  (backward compatibility, spec point 2). Note: this classic shape is
  keyed off the RUNTIME session count (len(launch['sessions']) == 1),
  not off which manifest key the task used -- a task written as
  'sessions': [only_one_text] is therefore recorded in run_log.json
  exactly like a classic 'text' task (flat entry, no
  sessions_total/stopped_early, stdout file without the '-sN' suffix),
  not as a length-1 multi-session record.
"""

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import usage_report

# ---------------------------------------------------------------------------
# console output safe for a cp1251 console (CLAUDE.md command hygiene)
# ---------------------------------------------------------------------------


def _print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))


# ---------------------------------------------------------------------------
# manifest parsing / validation
# ---------------------------------------------------------------------------

REQUIRED_TOP_FIELDS = ("polygon_root", "src", "model", "arms", "tasks", "order")
REQUIRED_SRC_FIELDS = (
    "click_git", "click_pin", "template_git", "template_ref", "fixture_dir",
)
KNOWN_LAYOUTS = {"empty", "template"}


def validate_manifest(manifest):
    """Raises ValueError on any structural problem (missing required
    field, unknown layout, order referencing an unknown task/arm).
    Mutates manifest in place only to fill the 'parallel' default (1)
    when absent. Returns the manifest for chaining."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")

    missing = [k for k in REQUIRED_TOP_FIELDS if k not in manifest]
    if missing:
        raise ValueError(f"manifest missing required field(s): {missing}")

    if not isinstance(manifest["src"], dict):
        raise ValueError("manifest.src must be an object")
    missing_src = [k for k in REQUIRED_SRC_FIELDS if k not in manifest["src"]]
    if missing_src:
        raise ValueError(f"manifest.src missing required field(s): {missing_src}")

    if not manifest["arms"]:
        raise ValueError("manifest.arms must be a non-empty list")
    arm_names = set()
    for arm in manifest["arms"]:
        if "name" not in arm:
            raise ValueError(f"arm missing 'name': {arm}")
        if arm.get("layout") not in KNOWN_LAYOUTS:
            raise ValueError(
                f"unknown layout {arm.get('layout')!r} for arm {arm.get('name')!r} "
                f"(known layouts: {sorted(KNOWN_LAYOUTS)})"
            )
        has_template_git = "template_git" in arm
        has_template_ref = "template_ref" in arm
        if has_template_git != has_template_ref:
            raise ValueError(
                f"arm {arm.get('name')!r} has 'template_git' without 'template_ref' "
                f"(or vice versa) -- per-arm template override needs both fields "
                f"together or neither (falls back to manifest.src.template_*): {arm}"
            )
        arm_names.add(arm["name"])

    if not manifest["tasks"]:
        raise ValueError("manifest.tasks must be a non-empty list")
    task_ids = set()
    for task in manifest["tasks"]:
        if "id" not in task:
            raise ValueError(f"task missing 'id': {task}")
        has_text = "text" in task
        has_sessions = "sessions" in task
        if not has_text and not has_sessions:
            raise ValueError(f"task missing 'text' or 'sessions': {task}")
        if has_text and has_sessions:
            raise ValueError(
                f"task {task.get('id')!r} has both 'text' and 'sessions' -- "
                f"'sessions' is an alternative to 'text', not additive: {task}"
            )
        if has_sessions:
            sessions = task["sessions"]
            if not isinstance(sessions, list) or not sessions or not all(
                isinstance(s, str) for s in sessions
            ):
                raise ValueError(
                    f"task {task.get('id')!r} 'sessions' must be a non-empty list of strings: {task}"
                )
        task_ids.add(task["id"])

    if not isinstance(manifest["order"], dict):
        raise ValueError("manifest.order must be an object keyed by task id")
    for task_id in task_ids:
        if task_id not in manifest["order"]:
            raise ValueError(f"manifest.order missing entry for task {task_id!r}")
        for arm_name in manifest["order"][task_id]:
            if arm_name not in arm_names:
                raise ValueError(
                    f"manifest.order[{task_id!r}] references unknown arm {arm_name!r}"
                )

    manifest.setdefault("parallel", 1)
    return manifest


def load_manifest(path):
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    return validate_manifest(manifest)


# ---------------------------------------------------------------------------
# project-name slug (mirrors ~/.claude/projects directory naming)
# ---------------------------------------------------------------------------


def project_slug(path):
    """Mirrors Claude Code's ~/.claude/projects directory-naming
    scheme: every non-alphanumeric character of the (stringified,
    OS-native-separator) path is replaced 1:1 with '-', with no
    collapsing of consecutive replacements.

    Verified empirically 2026-07-15 against this machine's real
    ~/.claude/projects listing for the given exam_release2 polygon:
    D:\\Improving_AI\\exam_release2\\A\\t1 -> the real directory
    'D--Improving-AI-exam-release2-A-t1' (and all 8 sibling
    arm/task dirs, including the B0 control arm) -- confirmed by
    directly listing that directory on this machine, which is reading
    beyond the manifest's read-only 'given' bucket (~/.claude/projects
    is not in given); see builder report."""
    return re.sub(r"[^a-zA-Z0-9]", "-", str(path))


# ---------------------------------------------------------------------------
# run-plan / launch construction (shared by dry-run printing and real run)
# ---------------------------------------------------------------------------


def build_launch_plan(manifest):
    """Returns the flattened, ORDERED list of the 3x3 launches: for
    each task in manifest['tasks'] order, for each arm in
    manifest['order'][task_id] order, one launch dict with
    order_index, task_id, arm, cwd (str), cmd (argv list for
    subprocess), sessions (ORDERED list of prompt strings, each
    already wrapped in the arm's prefix/suffix -- len 1 for a classic
    single-'text' task, len N for a task['sessions'] list of N
    prompts), and text (== sessions[0], kept for backward
    compatibility with callers/tests reading the pre-t-132 single-text
    field).

    A task's 'sessions' list (t-132: multi-session task, spec
    docs/tasks/2026-07-15_economy-exam-set2.md) is an alternative to
    'text', not additive (enforced in validate_manifest). All N
    session prompts of such a task get the SAME arm prefix/suffix
    wrapping applied per-session -- this is the existing
    prefix+task+suffix mechanism (already how the headless-escalation
    suffix reaches a single-session task's prompt, per
    PROCESS/DEPLOYMENT_ECONOMY_EXAM.md 'Headless-протез эскалации'),
    extended to every session instead of only the first."""
    polygon_root = Path(manifest["polygon_root"])
    arms_by_name = {a["name"]: a for a in manifest["arms"]}
    plan = []
    idx = 0
    for task in manifest["tasks"]:
        task_id = task["id"]
        for arm_name in manifest["order"][task_id]:
            arm = arms_by_name[arm_name]
            raw_texts = task["sessions"] if "sessions" in task else [task["text"]]
            texts = [arm.get("prefix", "") + t + arm.get("suffix", "") for t in raw_texts]
            cwd = polygon_root / arm_name / task_id
            # Resolve the real executable: on Windows the npm shim is
            # claude.cmd, and CreateProcess does not apply PATHEXT to
            # a bare "claude" (FileNotFoundError on first real launch,
            # 2026-07-15 -- masked in tests, which mock the spawn).
            # shutil.which honours PATHEXT; fall back to the bare name
            # so dry-run plans still build on machines without claude.
            claude_exe = shutil.which("claude") or "claude"
            # The prompt goes via STDIN, not argv: claude.cmd is a
            # batch shim, and cmd.exe truncates a batch argument at
            # the first newline -- runs 3/4 delivered ONLY the C-arm
            # prefix (task text after \n\n silently lost; proven from
            # the sessions' own transcripts, 2026-07-15). stdin
            # bypasses cmd.exe argument parsing entirely, so the full
            # multi-line message arrives byte-exact.
            cmd = [
                claude_exe, "-p",
                "--model", manifest["model"],
                "--dangerously-skip-permissions",
            ]
            plan.append({
                "order_index": idx,
                "task_id": task_id,
                "arm": arm_name,
                "cwd": str(cwd),
                "text": texts[0],
                "sessions": texts,
                "cmd": cmd,
            })
            idx += 1
    return plan


def _print_plan(plan):
    _print(f"DRY RUN -- {len(plan)} launch(es) planned (no execution, no side effects)")
    for launch in plan:
        _print(
            f"[{launch['order_index'] + 1}/{len(plan)}] "
            f"task={launch['task_id']} arm={launch['arm']} cwd={launch['cwd']}"
        )
        if len(launch["sessions"]) > 1:
            _print(f"    sessions: {len(launch['sessions'])} (sequential, same cwd)")
        _print(f"    cmd: {launch['cmd']}")


# ---------------------------------------------------------------------------
# prepare
# ---------------------------------------------------------------------------


def _git(args, cwd=None):
    return subprocess.run(
        ["git", *args], cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def _git_rev_parse(repo_dir, rev):
    result = _git(["rev-parse", rev], cwd=repo_dir)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _ensure_src_repo(dest, source, ref, actions):
    """Idempotent clone+pin for one _src/ repo. `source` may be a git
    URL or a local filesystem path -- git clone treats both the same
    way and, for a local path, performs no network I/O at all (this is
    how tests exercise this exact function offline, per spec's
    'мокнуть/обойти параметром': fake local git repos ARE the mock)."""
    dest = Path(dest)
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        clone = _git(["clone", str(source), str(dest)])
        if clone.returncode != 0:
            raise RuntimeError(f"git clone failed for {source} -> {dest}: {clone.stderr}")
        actions.append(f"cloned {source} -> {dest}")
    else:
        actions.append(f"{dest} already cloned, skipping clone")

    current = _git_rev_parse(dest, "HEAD")
    target = _git_rev_parse(dest, ref)
    if target is None:
        raise RuntimeError(f"ref {ref!r} not resolvable in {dest}")
    if current != target:
        checkout = _git(["checkout", ref], cwd=dest)
        if checkout.returncode != 0:
            raise RuntimeError(f"git checkout {ref} failed in {dest}: {checkout.stderr}")
        actions.append(f"checked out {ref} in {dest}")
    else:
        actions.append(f"{dest} already at {ref}, skipping checkout")


def _copy_tree_excluding_git(src, dst):
    src = Path(src)
    dst = Path(dst)
    dst.mkdir(parents=True, exist_ok=True)

    def _ignore(dir_, names):
        return {".git"} if Path(dir_) == src else set()

    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=_ignore)


SKIP_DIR_PARTS = {".git", "__pycache__", ".pytest_cache"}


def _relative_file_set(root):
    """Set of POSIX-style relative file paths under root, excluding
    .git/__pycache__/.pytest_cache contents (used both to snapshot the
    baseline layout right after prepare() and to diff the current
    sandbox state against it in collect())."""
    root = Path(root)
    if not root.exists():
        return set()
    files = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIR_PARTS for part in rel.parts):
            continue
        files.add(str(rel).replace("\\", "/"))
    return files


def _template_source_map(manifest):
    """Resolves every template source the manifest references (t-141:
    per-arm template_git/template_ref override) into two dicts:

    - `sources`: dest Path (under polygon_root/_src) -> (git, ref) for
      every UNIQUE template source -- the manifest.src default PLUS
      one entry per DISTINCT (template_git, template_ref) override
      pair carried by an arm with layout=='template'. Two arms
      overriding to the identical (git, ref) pair share one dest (one
      clone), matching the spec's "for each unique source, own clone".
      The default is always included, even if no arm ends up using it
      (matches prepare()'s pre-t-141 behavior of unconditionally
      ensuring _src/template).
    - `arm_template_dest`: arm name -> the dest Path that arm's
      layout=='template' copy should read from (only populated for
      layout=='template' arms; an override on a non-template-layout
      arm is accepted by validate_manifest but never resolved into a
      clone here since layout=='empty' never reads a template source).

    Naming (existing-style extension): default dest is _src/template
    (unchanged); an override's dest is _src/template_<armname>, keyed
    off the FIRST arm that introduces that distinct source."""
    polygon_root = Path(manifest["polygon_root"])
    src = manifest["src"]
    default_source = (src["template_git"], src["template_ref"])
    default_dest = polygon_root / "_src" / "template"

    dest_by_source = {default_source: default_dest}
    arm_template_dest = {}

    for arm in manifest["arms"]:
        if arm.get("layout") != "template":
            continue
        if arm.get("template_git") and arm.get("template_ref"):
            key = (arm["template_git"], arm["template_ref"])
        else:
            key = default_source
        if key not in dest_by_source:
            dest_by_source[key] = polygon_root / "_src" / f"template_{arm['name']}"
        arm_template_dest[arm["name"]] = dest_by_source[key]

    sources = {dest: source for source, dest in dest_by_source.items()}
    return sources, arm_template_dest


def prepare(manifest, dry_run=False):
    """Idempotent polygon assembly: _src/ clones (pinned), then for
    every (task, arm) sandbox: template-layout base copy (git-free)
    followed by needs=click (repo copy WITH .git) and/or needs=todo
    (fixture files, overwriting any template README -- fixture copied
    AFTER the template layout, per spec). Writes
    <polygon_root>/baseline_manifest.json (non-dry-run only) recording
    each sandbox's file set right after assembly, consumed by
    collect()'s composition diff. Returns the list of action strings
    (also printed).

    t-141: an arm with layout=='template' may carry its own
    template_git/template_ref, overriding manifest.src's default for
    THAT arm only (comparing two policy-kit variants in one exam run).
    _template_source_map() resolves the set of unique template sources
    referenced (default plus every distinct override) -- prepare()
    clones/pins each of them under its own _src/template[_<armname>]
    dir and VERIFYs each one's HEAD, same as the pre-t-141 single
    _src/template did. An arm without an override reads the default
    _src/template exactly as before (byte-identical behavior)."""
    polygon_root = Path(manifest["polygon_root"])
    src = manifest["src"]
    actions = []

    src_click = polygon_root / "_src" / "click"
    template_sources, arm_template_dest = _template_source_map(manifest)

    if dry_run:
        actions.append(f"[dry-run] ensure {src_click} at {src['click_git']}@{src['click_pin']}")
        for dest, (git, ref) in template_sources.items():
            actions.append(f"[dry-run] ensure {dest} at {git}@{ref}")
    else:
        _ensure_src_repo(src_click, src["click_git"], src["click_pin"], actions)
        for dest, (git, ref) in template_sources.items():
            _ensure_src_repo(dest, git, ref, actions)

    baseline_manifest = {}
    for task in manifest["tasks"]:
        for arm in manifest["arms"]:
            sandbox = polygon_root / arm["name"] / task["id"]
            key = f"{arm['name']}/{task['id']}"
            if dry_run:
                actions.append(
                    f"[dry-run] sandbox {sandbox} layout={arm['layout']} needs={task.get('needs', [])}"
                )
                continue

            sandbox.mkdir(parents=True, exist_ok=True)
            if arm["layout"] == "template":
                _copy_tree_excluding_git(arm_template_dest[arm["name"]], sandbox)
            # layout == "empty": nothing to lay down beyond needs below.
            # (any other layout value was already rejected by
            # validate_manifest() at load time.)

            needs = task.get("needs", [])
            if "click" in needs:
                click_dest = sandbox / "click"
                if not (click_dest / ".git").exists():
                    shutil.copytree(src_click, click_dest, dirs_exist_ok=True)
                else:
                    # Already copied -- skip the copy. Re-copying over
                    # an existing click/ tree is not just redundant:
                    # git marks loose objects under .git/objects/
                    # read-only on Windows, so a second
                    # dirs_exist_ok=True copytree over them raises
                    # PermissionError (empirically found 2026-07-15
                    # running the idempotency test twice on this
                    # machine -- shutil.Error / [Errno 13] on
                    # .git/objects/**). Skip-if-present avoids the
                    # touch entirely, matching the idempotent pattern
                    # of _ensure_src_repo(). The skip must NOT be
                    # silent about drift, though (critic t-117 M2): a
                    # sandbox clone left at a different commit would
                    # otherwise pass as prepared while diverging from
                    # the pinned _src state -- content drift invisible
                    # to collect()'s name-level file diff.
                    sandbox_head = _git_rev_parse(click_dest, "HEAD")
                    src_head = _git_rev_parse(src_click, "HEAD")
                    if sandbox_head != src_head:
                        raise RuntimeError(
                            f"{click_dest} already exists at {sandbox_head}, "
                            f"but _src click is pinned at {src_head}; refusing "
                            f"silent drift -- remove the sandbox clone or "
                            f"rebuild the polygon"
                        )
                    actions.append(f"{click_dest} already present at pin, skipping copy")
            if "todo" in needs:
                fixture_dir = Path(src["fixture_dir"])
                for f in sorted(fixture_dir.iterdir()):
                    if f.is_file():
                        shutil.copy2(f, sandbox / f.name)

            baseline_manifest[key] = sorted(_relative_file_set(sandbox))
            actions.append(f"prepared {sandbox}")

    if not dry_run:
        verify_targets = [("click", src_click, src["click_pin"])]
        for dest, (git, ref) in template_sources.items():
            verify_targets.append((dest.name, dest, ref))
        for name, dest, ref in verify_targets:
            rev = _git_rev_parse(dest, "HEAD")
            actions.append(f"VERIFY {name}: HEAD={rev} (target {ref})")
        polygon_root.mkdir(parents=True, exist_ok=True)
        (polygon_root / "baseline_manifest.json").write_text(
            json.dumps(baseline_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    for a in actions:
        _print(a)
    return actions


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def _run_one_session(cmd, cwd, text, polygon_root, arm, task_id, filename_suffix):
    """Runs exactly one headless `claude -p` invocation and persists
    its FULL stdout to <polygon_root>/stdout/<arm>-<task><suffix>.txt
    (utf-8) -- the per-session unit both the classic single-session
    path and the t-132 multi-session path are built from. Returns the
    same {start_ts, end_ts, rc, stdout_tail, stdout_file} shape either
    way; the caller attaches order_index/task_id/arm/cwd (classic) or
    session_index (multi). When the persisted stdout is empty after
    .strip() (empty string or whitespace-only), independent of rc, the
    record ALSO carries "empty_stdout": true -- a marker that lost
    output is indistinguishable from a session that silently did
    nothing (2026-07-15 finding 3); the key is omitted entirely when
    stdout is non-empty, so classic run_log shape (spec point 2) is
    unaffected."""
    start_ts = datetime.utcnow().isoformat() + "Z"
    proc = subprocess.run(
        cmd, cwd=cwd, input=text,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    end_ts = datetime.utcnow().isoformat() + "Z"
    stdout = proc.stdout or ""

    stdout_dir = Path(polygon_root) / "stdout"
    stdout_dir.mkdir(parents=True, exist_ok=True)
    stdout_file = stdout_dir / f"{arm}-{task_id}{filename_suffix}.txt"
    stdout_file.write_text(stdout, encoding="utf-8")

    result = {
        "start_ts": start_ts,
        "end_ts": end_ts,
        "rc": proc.returncode,
        "stdout_tail": stdout[-2000:],
        "stdout_file": str(stdout_file),
    }
    if not stdout.strip():
        result["empty_stdout"] = True
    return result


def _execute_launch(launch, polygon_root):
    """Runs one launch. Classic (single-session, len(sessions)==1)
    launches keep the EXACT pre-t-132 run_log shape (order_index,
    task_id, arm, cwd, start_ts, end_ts, rc, stdout_tail, stdout_file)
    and stdout filename (<arm>-<task>.txt) -- backward compatibility,
    spec point 2.

    Multi-session (t-132) launches run every launch['sessions'] prompt
    SEQUENTIALLY in the SAME cwd -- session N+1 starts only after
    session N's rc is known -- each as a SEPARATE headless `claude -p`
    process (fresh context per session, per spec: a returning user
    opens a new chat, not --continue/--resume). A non-zero rc stops
    the chain by default (remaining sessions do not start); the
    aggregate carries per-session records under 'sessions', the last
    executed session's rc as the top-level 'rc', and an explicit
    'stopped_early' flag (True whenever fewer sessions ran than were
    planned) so the run_log makes the stop visible without the reader
    having to infer it from a short 'sessions' list."""
    sessions = launch["sessions"]

    if len(sessions) == 1:
        result = _run_one_session(
            launch["cmd"], launch["cwd"], sessions[0], polygon_root,
            launch["arm"], launch["task_id"], "",
        )
        return {
            "order_index": launch["order_index"],
            "task_id": launch["task_id"],
            "arm": launch["arm"],
            "cwd": launch["cwd"],
            **result,
        }

    session_results = []
    for i, text in enumerate(sessions):
        result = _run_one_session(
            launch["cmd"], launch["cwd"], text, polygon_root,
            launch["arm"], launch["task_id"], f"-s{i + 1}",
        )
        result["session_index"] = i
        session_results.append(result)
        if result["rc"] != 0:
            break

    return {
        "order_index": launch["order_index"],
        "task_id": launch["task_id"],
        "arm": launch["arm"],
        "cwd": launch["cwd"],
        "rc": session_results[-1]["rc"],
        "sessions_total": len(sessions),
        "stopped_early": len(session_results) < len(sessions),
        "sessions": session_results,
    }


def run(manifest, dry_run=False):
    """Executes (or, dry-run, just prints) the launch plan built by
    build_launch_plan(), respecting manifest['order'] per-task arm
    order and bounding concurrency to manifest['parallel'] (default 1
    -- sequential, clean speed metric per spec). Non-dry-run writes
    <polygon_root>/run_log.json with one entry per launch: a classic
    single-session launch keeps start/end ts, rc, a 2000-char stdout
    tail, and stdout_file (full stdout persisted separately to
    <polygon_root>/stdout/<arm>-<task>.txt, 2026-07-15 backlog fix 1);
    a t-132 multi-session launch (task['sessions']) instead carries a
    'sessions' list of that same per-session shape (stdout at
    <polygon_root>/stdout/<arm>-<task>-s<N>.txt) plus the aggregate
    'rc'/'sessions_total'/'stopped_early' -- see _execute_launch's
    docstring. Any per-session record (classic or within a 'sessions'
    list) whose persisted stdout is empty after .strip() additionally
    carries "empty_stdout": true, regardless of rc (2026-07-15 finding
    3); the key is absent when stdout is non-empty. Concurrency is
    bounded across LAUNCHES (distinct (task, arm) sandboxes); the
    sessions WITHIN one multi-session launch always run sequentially
    in the same cwd regardless of manifest['parallel']."""
    plan = build_launch_plan(manifest)
    if dry_run:
        _print_plan(plan)
        return plan

    parallel = max(1, int(manifest.get("parallel", 1)))
    results = [None] * len(plan)
    polygon_root = manifest["polygon_root"]

    if parallel == 1:
        # Plain loop: plan order is guaranteed by construction. A
        # Semaphore(1) over eagerly-started threads only orders by
        # which thread wins the acquire race, not by plan index --
        # empirically scrambled 20/20 under contention (critic t-117
        # M1), and the rotation order is a pinned protocol
        # requirement ("no favourite last arm").
        for i, launch in enumerate(plan):
            results[i] = _execute_launch(launch, polygon_root)
    else:
        sem = threading.Semaphore(parallel)

        def worker(i, launch):
            with sem:
                results[i] = _execute_launch(launch, polygon_root)

        threads = [threading.Thread(target=worker, args=(i, launch)) for i, launch in enumerate(plan)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    polygon_root = Path(manifest["polygon_root"])
    polygon_root.mkdir(parents=True, exist_ok=True)
    (polygon_root / "run_log.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return results


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


def _parse_ts(ts):
    if not ts:
        return None
    s = ts[:-1] + "+00:00" if ts.endswith("Z") else ts
    return datetime.fromisoformat(s)


def stall_estimate(turns):
    """turns: iterable of (ts_str, output_tokens) for one project's
    cc_usage rows (any order). Sums, over consecutive turns (sorted by
    ts) whose gap exceeds 60s, the gap MINUS the expected generation
    time of the turn ending the gap (output_tokens/40 tok/s + 10s
    overhead), clamped at 0 -- formula from
    docs/tasks/2026-07-14_economy-exam-run2.md 'ПОПРАВКА СКОРОСТИ'.
    Returns seconds (float)."""
    parsed = sorted(
        ((_parse_ts(ts), out) for ts, out in turns if ts),
        key=lambda x: x[0],
    )
    total = 0.0
    for (t0, _out0), (t1, out1) in zip(parsed, parsed[1:]):
        gap = (t1 - t0).total_seconds()
        if gap > 60:
            expected_gen = (out1 or 0) / 40.0 + 10.0
            total += max(0.0, gap - expected_gen)
    return total


def sandbox_metrics(conn, project):
    """turns/cost/side_cost/side_share/wall(min,max ts)/stall_est for
    one project's cc_usage rows, read from an open sqlite3 connection
    (schema per usage_report.SCHEMA).

    Matches project = slug OR project LIKE '<slug>-%' -- when a
    session (or a subagent it spawns) starts with cwd inside a
    sandbox subdirectory, Claude Code logs it under a distinct
    sub-slug project (e.g. '...-C-t2' plus '...-C-t2-click'), which a
    plain equality match would miss entirely. Precedent: run #3's C/t2
    rerun partly landed under such a sub-slug and undercounted."""
    rows = conn.execute(
        "SELECT ts, output_tokens, accounted_cost_usd, is_sidechain "
        "FROM cc_usage WHERE project = ? OR project LIKE ? ORDER BY ts",
        (project, project + "-%"),
    ).fetchall()
    turns = len(rows)
    total_cost = sum(r[2] or 0.0 for r in rows)
    side_cost = sum((r[2] or 0.0) for r in rows if r[3])
    side_share = (side_cost / total_cost) if total_cost else None
    ts_list = [r[0] for r in rows if r[0]]
    wall_start = min(ts_list) if ts_list else None
    wall_end = max(ts_list) if ts_list else None
    stall = stall_estimate([(r[0], r[1]) for r in rows])
    return {
        "project": project,
        "turns": turns,
        "cost_usd": total_cost,
        "side_cost_usd": side_cost,
        "side_share": side_share,
        "wall_start": wall_start,
        "wall_end": wall_end,
        "stall_est_seconds": stall,
    }


def window_load(conn, exclude_projects, window_start, window_end):
    """Turn count + summed output_tokens per OTHER project (not in
    exclude_projects) whose ts falls in [window_start, window_end] --
    the 'foreign load in the exam window' table, sorted by turns
    desc."""
    exclude_projects = list(exclude_projects)
    query = (
        "SELECT project, COUNT(*), SUM(output_tokens) "
        "FROM cc_usage WHERE ts >= ? AND ts <= ?"
    )
    params = [window_start, window_end]
    if exclude_projects:
        placeholders = ",".join("?" for _ in exclude_projects)
        query += f" AND project NOT IN ({placeholders})"
        params.extend(exclude_projects)
    query += " GROUP BY project ORDER BY 2 DESC"
    rows = conn.execute(query, params).fetchall()
    return [{"project": r[0], "turns": r[1], "out_tokens": r[2] or 0} for r in rows]


def run_dossier_tests(sandbox_dir, baseline_files):
    """Finds test_*.py under sandbox_dir (any depth, skipping
    .git/__pycache__/.pytest_cache) that the SESSION created --
    i.e. NOT present in baseline_files (the sandbox's file set right
    after prepare(), from baseline_manifest.json) -- AND not inside a
    needs=click clone subtree (click/**, the literal dest name used by
    prepare()'s needs=click copy). Runs `python -m pytest <file> -q`
    for each (this is NOT a claude invocation -- it genuinely executes,
    per spec), and returns a list of {file, rc, output_tail}.

    Precedent (run #3, C/t2): without this scoping, dossier test runs
    swept in click's own upstream test_*.py files (33 of them,
    click/tests/test_*.py) that were already part of the prepared
    baseline, not written by the session -- pure noise, some failing
    against the sandbox's system Python package rather than any
    session defect."""
    sandbox_dir = Path(sandbox_dir)
    results = []
    if not sandbox_dir.exists():
        return results
    baseline_files = set(baseline_files)
    for test_file in sorted(sandbox_dir.rglob("test_*.py")):
        rel = test_file.relative_to(sandbox_dir)
        if any(part in SKIP_DIR_PARTS for part in rel.parts):
            continue
        if rel.parts and rel.parts[0] == "click":
            continue
        rel_str = str(rel).replace("\\", "/")
        if rel_str in baseline_files:
            continue
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q"],
            cwd=str(sandbox_dir),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        tail = (proc.stdout or "")[-2000:]
        results.append({"file": rel_str, "rc": proc.returncode, "output_tail": tail})
    return results


ARTIFACT_URL_MARKER = "claude.ai/code/artifact/"


def _run_log_stdout_files(entry):
    """Returns the ORDERED list of stdout_file paths a run_log.json
    entry references -- one path for a classic single-session entry
    (its flat 'stdout_file'), one per session (session order) for a
    t-132 multi-session entry ('sessions'[i]['stdout_file']).

    collect()'s artifact-deliverable detection reads stdout_file paths
    off THIS (the entry actually written by run()) rather than
    reconstructing a '<arm>-<task>.txt' filename -- the reconstruction
    only ever matches a classic entry's stdout file and silently finds
    nothing for every multi-session sandbox (whose files are named
    '<arm>-<task>-s<N>.txt'), which disabled the detector across an
    entire multi-session run (critic t-132 retry blocker, 2026-07-15)."""
    if entry and "sessions" in entry:
        return [s["stdout_file"] for s in entry["sessions"] if s.get("stdout_file")]
    stdout_file = entry.get("stdout_file") if entry else None
    return [stdout_file] if stdout_file else []


def detect_artifact_deliverable(stdout_text):
    """True if stdout_text references an Artifact URL
    (claude.ai/code/artifact/) -- Artifacts are private to the
    operator's own claude.ai account and can go unreachable to anyone
    else reviewing the dossier later: the 'evidence dies with the
    session' class (alongside dead scratchpad files and truncated
    stdout tails, per docs/tasks/2026-07-15_economy-exam-runs3-4.md)."""
    return ARTIFACT_URL_MARKER in (stdout_text or "")


def _render_dossier_markdown(dossier):
    lines = [f"# Exam dossier -- {dossier['polygon_root']}", ""]
    lines.append(f"Window: {dossier['window']['start']} .. {dossier['window']['end']}")
    lines.append("")
    lines.append("| Arm | Task | Turns | Cost $ | Side $ | Side share | Stall est (s) |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in dossier["sandboxes"]:
        share = f"{r['side_share']:.1%}" if r["side_share"] is not None else "n/a"
        lines.append(
            f"| {r['arm']} | {r['task_id']} | {r['turns']} | {r['cost_usd']:.4f} | "
            f"{r['side_cost_usd']:.4f} | {share} | {r['stall_est_seconds']:.1f} |"
        )

    lines.append("")
    lines.append("## Artifact deliverable warnings")
    warned = [r for r in dossier["sandboxes"] if r.get("artifact_warning")]
    if not warned:
        lines.append("(none)")
    else:
        for r in warned:
            lines.append(
                f"- {r['arm']}/{r['task_id']}: deliverable = внешний артефакт "
                f"(может быть недоступен вне аккаунта)"
            )

    lines.append("")
    lines.append("## Tests (executed pytest, not claude)")
    for r in dossier["sandboxes"]:
        lines.append(f"### {r['arm']}/{r['task_id']}")
        if not r["tests"]:
            lines.append("(no test_*.py found)")
        for t in r["tests"]:
            lines.append(f"- {t['file']}: rc={t['rc']}")
            lines.append("```")
            lines.append(t["output_tail"])
            lines.append("```")

    lines.append("")
    lines.append("## File composition diff (current sandbox vs. baseline layout)")
    for r in dossier["sandboxes"]:
        lines.append(f"### {r['arm']}/{r['task_id']}")
        lines.append(f"added: {r['files_added']}")
        lines.append(f"removed: {r['files_removed']}")

    lines.append("")
    lines.append("## Window load (other projects active during the exam window)")
    lines.append("| Project | Turns | Out tokens |")
    lines.append("|---|---|---|")
    for w in dossier["window_load"]:
        lines.append(f"| {w['project']} | {w['turns']} | {w['out_tokens']} |")

    lines.append("")
    lines.append(
        f"Import: {dossier['import_summary']['rows_imported']} new row(s), "
        f"{dossier['import_summary']['sessions_seen']} session(s) seen this run."
    )
    if dossier["import_summary"]["warnings"]:
        lines.append("Warnings:")
        for w in dossier["import_summary"]["warnings"]:
            lines.append(f"  {w}")

    lines.append("")
    lines.append("No verdicts here -- acceptance and Runs-log entries stay with Lead.")
    return "\n".join(lines)


def collect(manifest, dry_run=False):
    """(1) imports fresh transcripts via usage_report.import_transcripts
    (real ~/.claude/projects glob + gateway db, reused by import per
    spec); (2) per sandbox: turns/cost/side/wall/stall from cc_usage
    (project=slug OR LIKE slug-% -- folds in sub-slug projects),
    dossier pytest runs scoped to session-created non-click test files
    (baseline_manifest.json diff), file-composition diff against
    baseline_manifest.json, artifact-deliverable warning aggregated
    over EVERY stdout file run_log.json's entry for that (arm, task)
    references (one file classic, one per session multi-session,
    t-132 retry fix -- ANY session's stdout carrying the marker warns
    the whole task; falls back to the classic '<arm>-<task>.txt'
    reconstruction when run_log.json is absent/has no matching entry,
    e.g. a stdout file assembled without a run) (2026-07-15 backlog
    fixes 1-4); (3) window load table for OTHER projects in the exam's
    [min..max] ts window; (4) writes <polygon_root>/dossier.{md,json}.
    No verdicts, no Runs-log write (non-goal). --dry-run: no-op (no
    side effects), per DoD."""
    if dry_run:
        _print("[dry-run] collect skipped (no side effects)")
        return None

    polygon_root = Path(manifest["polygon_root"])

    rows_imported, sessions_seen, warnings = usage_report.import_transcripts(
        usage_report.transcript_glob(), usage_report.db_path()
    )

    conn = sqlite3.connect(usage_report.db_path())
    try:
        baseline_manifest = {}
        baseline_path = polygon_root / "baseline_manifest.json"
        if baseline_path.exists():
            baseline_manifest = json.loads(baseline_path.read_text(encoding="utf-8"))

        run_log_by_key = {}
        run_log_path = polygon_root / "run_log.json"
        if run_log_path.exists():
            for entry in json.loads(run_log_path.read_text(encoding="utf-8")):
                run_log_by_key[(entry["arm"], entry["task_id"])] = entry

        results = []
        exclude_projects = []
        for task in manifest["tasks"]:
            for arm in manifest["arms"]:
                sandbox_dir = polygon_root / arm["name"] / task["id"]
                project = project_slug(sandbox_dir)
                exclude_projects.append(project)

                key = f"{arm['name']}/{task['id']}"
                baseline = set(baseline_manifest.get(key, []))
                current = _relative_file_set(sandbox_dir)

                metrics = sandbox_metrics(conn, project)
                tests = run_dossier_tests(sandbox_dir, baseline)

                run_log_entry = run_log_by_key.get((arm["name"], task["id"]))
                stdout_files = _run_log_stdout_files(run_log_entry)
                if not stdout_files:
                    # No run_log.json entry (or none matching) -- fall
                    # back to the classic single-file reconstruction
                    # (e.g. a stdout file assembled without a run()
                    # call, as the pre-t-132 dossier-wiring test does).
                    fallback = polygon_root / "stdout" / f"{arm['name']}-{task['id']}.txt"
                    stdout_files = [str(fallback)] if fallback.exists() else []
                artifact_warning = any(
                    detect_artifact_deliverable(
                        Path(p).read_text(encoding="utf-8", errors="replace")
                    )
                    for p in stdout_files if Path(p).exists()
                )

                results.append({
                    "arm": arm["name"],
                    "task_id": task["id"],
                    **metrics,
                    "tests": tests,
                    "files_added": sorted(current - baseline),
                    "files_removed": sorted(baseline - current),
                    "artifact_warning": artifact_warning,
                })

        starts = [r["wall_start"] for r in results if r["wall_start"]]
        ends = [r["wall_end"] for r in results if r["wall_end"]]
        window_start = min(starts) if starts else None
        window_end = max(ends) if ends else None
        load = (
            window_load(conn, exclude_projects, window_start, window_end)
            if window_start and window_end else []
        )
    finally:
        conn.close()

    dossier = {
        "polygon_root": str(polygon_root),
        "window": {"start": window_start, "end": window_end},
        "sandboxes": results,
        "window_load": load,
        "import_summary": {
            "rows_imported": rows_imported,
            "sessions_seen": len(sessions_seen),
            "warnings": warnings,
        },
    }

    polygon_root.mkdir(parents=True, exist_ok=True)
    (polygon_root / "dossier.json").write_text(
        json.dumps(dossier, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (polygon_root / "dossier.md").write_text(_render_dossier_markdown(dossier), encoding="utf-8")
    _print(f"dossier written: {polygon_root / 'dossier.md'}")
    return dossier


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Economy exam runner")
    parser.add_argument("command", choices=["prepare", "run", "collect", "all"])
    parser.add_argument("--manifest", required=True, help="Path to the run-manifest JSON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)

    if args.command == "prepare":
        prepare(manifest, dry_run=args.dry_run)
    elif args.command == "run":
        run(manifest, dry_run=args.dry_run)
    elif args.command == "collect":
        collect(manifest, dry_run=args.dry_run)
    elif args.command == "all":
        prepare(manifest, dry_run=args.dry_run)
        run(manifest, dry_run=args.dry_run)
        collect(manifest, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
