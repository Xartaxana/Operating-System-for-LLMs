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
        arm_names.add(arm["name"])

    if not manifest["tasks"]:
        raise ValueError("manifest.tasks must be a non-empty list")
    task_ids = set()
    for task in manifest["tasks"]:
        if "id" not in task or "text" not in task:
            raise ValueError(f"task missing 'id' or 'text': {task}")
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
    order_index, task_id, arm, cwd (str), text (prefix+task+suffix),
    cmd (argv list for subprocess)."""
    polygon_root = Path(manifest["polygon_root"])
    arms_by_name = {a["name"]: a for a in manifest["arms"]}
    plan = []
    idx = 0
    for task in manifest["tasks"]:
        task_id = task["id"]
        for arm_name in manifest["order"][task_id]:
            arm = arms_by_name[arm_name]
            text = arm.get("prefix", "") + task["text"] + arm.get("suffix", "")
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
                "text": text,
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


def prepare(manifest, dry_run=False):
    """Idempotent polygon assembly: _src/ clones (pinned), then for
    every (task, arm) sandbox: template-layout base copy (git-free)
    followed by needs=click (repo copy WITH .git) and/or needs=todo
    (fixture files, overwriting any template README -- fixture copied
    AFTER the template layout, per spec). Writes
    <polygon_root>/baseline_manifest.json (non-dry-run only) recording
    each sandbox's file set right after assembly, consumed by
    collect()'s composition diff. Returns the list of action strings
    (also printed)."""
    polygon_root = Path(manifest["polygon_root"])
    src = manifest["src"]
    actions = []

    src_click = polygon_root / "_src" / "click"
    src_template = polygon_root / "_src" / "template"

    if dry_run:
        actions.append(f"[dry-run] ensure {src_click} at {src['click_git']}@{src['click_pin']}")
        actions.append(f"[dry-run] ensure {src_template} at {src['template_git']}@{src['template_ref']}")
    else:
        _ensure_src_repo(src_click, src["click_git"], src["click_pin"], actions)
        _ensure_src_repo(src_template, src["template_git"], src["template_ref"], actions)

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
                _copy_tree_excluding_git(src_template, sandbox)
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
        for name, dest, ref in (
            ("click", src_click, src["click_pin"]),
            ("template", src_template, src["template_ref"]),
        ):
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


def _execute_launch(launch, polygon_root):
    """Runs one launch and persists its FULL stdout to
    <polygon_root>/stdout/<arm>-<task>.txt (utf-8) -- run_log.json
    itself only keeps a 2000-char tail (chat-report friendly) plus the
    stdout_file path. Precedent: run #3's T2 chat reports were built
    off the tail alone and died truncated when the real content sat
    earlier in a long transcript."""
    start_ts = datetime.utcnow().isoformat() + "Z"
    proc = subprocess.run(
        launch["cmd"], cwd=launch["cwd"], input=launch["text"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    end_ts = datetime.utcnow().isoformat() + "Z"
    stdout = proc.stdout or ""

    stdout_dir = Path(polygon_root) / "stdout"
    stdout_dir.mkdir(parents=True, exist_ok=True)
    stdout_file = stdout_dir / f"{launch['arm']}-{launch['task_id']}.txt"
    stdout_file.write_text(stdout, encoding="utf-8")

    return {
        "order_index": launch["order_index"],
        "task_id": launch["task_id"],
        "arm": launch["arm"],
        "cwd": launch["cwd"],
        "start_ts": start_ts,
        "end_ts": end_ts,
        "rc": proc.returncode,
        "stdout_tail": stdout[-2000:],
        "stdout_file": str(stdout_file),
    }


def run(manifest, dry_run=False):
    """Executes (or, dry-run, just prints) the 9-launch plan built by
    build_launch_plan(), respecting manifest['order'] per-task arm
    order and bounding concurrency to manifest['parallel'] (default 1
    -- sequential, clean speed metric per spec). Non-dry-run writes
    <polygon_root>/run_log.json with start/end ts, rc, a 2000-char
    stdout tail, and stdout_file per launch -- the FULL stdout is
    persisted separately to <polygon_root>/stdout/<arm>-<task>.txt
    (2026-07-15 backlog fix 1)."""
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
    baseline_manifest.json, artifact-deliverable warning from
    <polygon_root>/stdout/<arm>-<task>.txt (2026-07-15 backlog fixes
    1-4); (3) window load table for OTHER projects in the exam's
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

                stdout_path = polygon_root / "stdout" / f"{arm['name']}-{task['id']}.txt"
                artifact_warning = (
                    detect_artifact_deliverable(stdout_path.read_text(encoding="utf-8", errors="replace"))
                    if stdout_path.exists() else False
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
