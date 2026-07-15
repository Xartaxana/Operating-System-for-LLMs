"""Tests for tools/exam_runner.py. No network, no `claude` invocations
(prohibited by spec's non-goals) -- prepare()'s git operations are
exercised against LOCAL fixture-factory git repos built inside
tmp_path (a `git clone <local-path> <dest>` is a filesystem-only
operation, no network I/O), which is how the spec's "мокнуть/обойти
параметром" instruction is satisfied here: the fake local repos ARE
the mock, exercising the real clone+checkout code path offline.

Run from tools/: python -m pytest test_exam_runner.py
Run from repo root (canonical form): python -m pytest tools/ gateway/ -q
"""

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

import usage_report
from exam_runner import (
    build_launch_plan,
    collect,
    detect_artifact_deliverable,
    load_manifest,
    prepare,
    project_slug,
    run,
    run_dossier_tests,
    sandbox_metrics,
    stall_estimate,
    validate_manifest,
    window_load,
)
from usage_report import SCHEMA


# ---------------------------------------------------------------------------
# fixture-factory helpers (local-only git repos, no network)
# ---------------------------------------------------------------------------


def _git(args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {args} failed in {cwd}: {result.stderr}"
    return result.stdout.strip()


def _make_local_repo(root, files):
    """Creates a real local git repo at `root` with `files` (dict of
    relative-path -> content), one commit, and returns its HEAD sha.
    Fully local -- no network involved (fixture factory per spec)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(["init"], root)
    _git(["-c", "user.name=test", "-c", "user.email=test@example.com", "add", "-A"], root)
    _git(["-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "init"], root)
    return _git(["rev-parse", "HEAD"], root)


def _base_manifest(tmp_path, click_repo, click_sha, template_repo, template_sha, fixture_dir):
    return {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": str(click_repo),
            "click_pin": click_sha,
            "template_git": str(template_repo),
            "template_ref": template_sha,
            "fixture_dir": str(fixture_dir),
        },
        "model": "sonnet",
        "parallel": 1,
        "arms": [
            {"name": "A", "layout": "empty", "prefix": "", "suffix": ""},
            {"name": "B", "layout": "template", "prefix": "", "suffix": ""},
            {"name": "C", "layout": "empty", "prefix": "WORKFLOW-PREFIX\n\n", "suffix": ""},
        ],
        "tasks": [
            {"id": "t1", "needs": [], "text": "Напиши мне калькулятор"},
            {"id": "t2", "needs": ["click"], "text": "разведка click"},
            {"id": "t3", "needs": ["todo"], "text": "почини todo"},
        ],
        "order": {"t1": ["B", "A", "C"], "t2": ["C", "B", "A"], "t3": ["A", "C", "B"]},
    }


# ---------------------------------------------------------------------------
# 1. manifest parsing / validation
# ---------------------------------------------------------------------------


def test_load_manifest_valid_sets_parallel_default(tmp_path):
    manifest = {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y",
            "fixture_dir": str(tmp_path),
        },
        "model": "sonnet",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "text": "hi", "needs": []}],
        "order": {"t1": ["A"]},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_manifest(path)
    assert loaded["parallel"] == 1


def test_validate_manifest_missing_required_field_raises():
    manifest = {
        "src": {}, "model": "sonnet", "arms": [], "tasks": [], "order": {},
    }
    with pytest.raises(ValueError, match="polygon_root"):
        validate_manifest(manifest)


def test_validate_manifest_missing_src_field_raises():
    manifest = {
        "polygon_root": "x",
        "src": {"click_git": "x"},
        "model": "sonnet",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "text": "hi"}],
        "order": {"t1": ["A"]},
    }
    with pytest.raises(ValueError, match="src"):
        validate_manifest(manifest)


def test_validate_manifest_unknown_layout_raises():
    manifest = {
        "polygon_root": "x",
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": "x",
        },
        "model": "sonnet",
        "arms": [{"name": "D", "layout": "bogus_layout"}],
        "tasks": [{"id": "t1", "text": "hi"}],
        "order": {"t1": ["D"]},
    }
    with pytest.raises(ValueError, match="unknown layout"):
        validate_manifest(manifest)


def test_validate_manifest_order_references_unknown_arm_raises():
    manifest = {
        "polygon_root": "x",
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": "x",
        },
        "model": "sonnet",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "text": "hi"}],
        "order": {"t1": ["ZZZ"]},
    }
    with pytest.raises(ValueError, match="unknown arm"):
        validate_manifest(manifest)


# ---------------------------------------------------------------------------
# 2. launch-plan generation (dry-run path)
# ---------------------------------------------------------------------------


def test_build_launch_plan_order_and_content(tmp_path):
    manifest = {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": str(tmp_path),
        },
        "model": "sonnet",
        "parallel": 1,
        "arms": [
            {"name": "A", "layout": "empty", "prefix": "", "suffix": ""},
            {"name": "B", "layout": "template", "prefix": "PFX: ", "suffix": " :SFX"},
        ],
        "tasks": [
            {"id": "t1", "text": "task one", "needs": []},
            {"id": "t2", "text": "task two", "needs": []},
        ],
        "order": {"t1": ["B", "A"], "t2": ["A", "B"]},
    }
    plan = build_launch_plan(manifest)

    assert len(plan) == 4
    # t1 first (manifest task order), arm order B then A within t1.
    assert [(p["task_id"], p["arm"]) for p in plan] == [
        ("t1", "B"), ("t1", "A"), ("t2", "A"), ("t2", "B"),
    ]
    assert [p["order_index"] for p in plan] == [0, 1, 2, 3]

    b_t1 = plan[0]
    assert b_t1["text"] == "PFX: task one :SFX"
    assert "sonnet" in b_t1["cmd"]
    # The prompt must NOT be an argv element: claude.cmd is a batch
    # shim and cmd.exe truncates batch arguments at the first newline
    # (runs 3/4 lost every C-arm task after the prefix's \n\n). The
    # text travels via stdin (_execute_launch input=), so multi-line
    # messages arrive byte-exact.
    assert "PFX: task one :SFX" not in b_t1["cmd"]
    assert "-p" in b_t1["cmd"]
    assert "--dangerously-skip-permissions" in b_t1["cmd"]
    assert b_t1["cwd"] == str(Path(manifest["polygon_root"]) / "B" / "t1")

    a_t1 = plan[1]
    assert a_t1["text"] == "task one"
    assert a_t1["cwd"] == str(Path(manifest["polygon_root"]) / "A" / "t1")


# ---------------------------------------------------------------------------
# 3. prepare() on tmp_path with fake local git src (no network)
# ---------------------------------------------------------------------------


def test_prepare_layouts_readme_overwrite_and_git_exclusion(tmp_path):
    click_repo = tmp_path / "fake_click"
    click_sha = _make_local_repo(click_repo, {"click_marker.txt": "click contents"})

    template_repo = tmp_path / "fake_template"
    template_sha = _make_local_repo(template_repo, {
        "README.md": "TEMPLATE README",
        "CLAUDE.md": "template policy",
    })

    fixture_dir = tmp_path / "todo_fixture"
    fixture_dir.mkdir()
    (fixture_dir / "todo.py").write_text("# todo cli", encoding="utf-8")
    (fixture_dir / "README.md").write_text("FIXTURE README", encoding="utf-8")

    manifest = _base_manifest(tmp_path, click_repo, click_sha, template_repo, template_sha, fixture_dir)
    prepare(manifest, dry_run=False)

    polygon = Path(manifest["polygon_root"])

    # A/t1: layout=empty, needs=[] -> nothing laid down.
    a_t1 = polygon / "A" / "t1"
    assert a_t1.exists()
    assert list(a_t1.iterdir()) == []

    # B/t1: layout=template -> template files present, .git NOT copied.
    b_t1 = polygon / "B" / "t1"
    assert (b_t1 / "README.md").read_text(encoding="utf-8") == "TEMPLATE README"
    assert (b_t1 / "CLAUDE.md").exists()
    assert not (b_t1 / ".git").exists()

    # A/t2: layout=empty, needs=[click] -> click copied WITH .git.
    a_t2 = polygon / "A" / "t2"
    assert (a_t2 / "click" / "click_marker.txt").read_text(encoding="utf-8") == "click contents"
    assert (a_t2 / "click" / ".git").exists()

    # B/t3: layout=template + needs=[todo] -> fixture README OVERWRITES
    # the template README (fixture copied after the template layout).
    b_t3 = polygon / "B" / "t3"
    assert (b_t3 / "README.md").read_text(encoding="utf-8") == "FIXTURE README"
    assert (b_t3 / "todo.py").exists()
    assert (b_t3 / "CLAUDE.md").exists()  # rest of the template layout untouched
    assert not (b_t3 / ".git").exists()

    # C/t3: layout=empty + needs=[todo] -> only fixture files, no template noise.
    c_t3 = polygon / "C" / "t3"
    assert (c_t3 / "README.md").read_text(encoding="utf-8") == "FIXTURE README"
    assert not (c_t3 / "CLAUDE.md").exists()

    # baseline_manifest.json recorded for every sandbox.
    baseline = json.loads((polygon / "baseline_manifest.json").read_text(encoding="utf-8"))
    assert "B/t3" in baseline
    assert "README.md" in baseline["B/t3"]
    assert "todo.py" in baseline["B/t3"]


def test_prepare_is_idempotent(tmp_path):
    click_repo = tmp_path / "fake_click"
    click_sha = _make_local_repo(click_repo, {"click_marker.txt": "click contents"})
    template_repo = tmp_path / "fake_template"
    template_sha = _make_local_repo(template_repo, {"README.md": "TEMPLATE README"})
    fixture_dir = tmp_path / "todo_fixture"
    fixture_dir.mkdir()
    (fixture_dir / "todo.py").write_text("# todo cli", encoding="utf-8")
    (fixture_dir / "README.md").write_text("FIXTURE README", encoding="utf-8")

    manifest = _base_manifest(tmp_path, click_repo, click_sha, template_repo, template_sha, fixture_dir)

    prepare(manifest, dry_run=False)
    # second run must not raise (no re-clone/re-checkout errors), and
    # the layout must remain correct.
    prepare(manifest, dry_run=False)

    polygon = Path(manifest["polygon_root"])
    assert (polygon / "B" / "t1" / "README.md").read_text(encoding="utf-8") == "TEMPLATE README"
    assert (polygon / "A" / "t2" / "click" / ".git").exists()


def test_prepare_rejects_drifted_sandbox_click(tmp_path):
    """Critic t-117 M2: skip-if-present must not silently accept a
    sandbox click clone standing at a DIFFERENT commit than the pinned
    _src state -- content drift would be invisible to collect()'s
    name-level diff."""
    click_repo = tmp_path / "fake_click"
    click_sha = _make_local_repo(click_repo, {"click_marker.txt": "click contents"})
    template_repo = tmp_path / "fake_template"
    template_sha = _make_local_repo(template_repo, {"README.md": "TEMPLATE README"})
    fixture_dir = tmp_path / "todo_fixture"
    fixture_dir.mkdir()
    (fixture_dir / "todo.py").write_text("# todo cli", encoding="utf-8")
    (fixture_dir / "README.md").write_text("FIXTURE README", encoding="utf-8")

    manifest = _base_manifest(tmp_path, click_repo, click_sha, template_repo, template_sha, fixture_dir)
    prepare(manifest, dry_run=False)

    # Advance the SANDBOX clone by one commit: it now diverges from the
    # pinned _src click while still having a .git (skip branch taken).
    sandbox_click = Path(manifest["polygon_root"]) / "A" / "t2" / "click"
    (sandbox_click / "drift.txt").write_text("drift", encoding="utf-8")
    _git(["-c", "user.name=test", "-c", "user.email=test@example.com", "add", "-A"], sandbox_click)
    _git(["-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "drift"], sandbox_click)

    with pytest.raises(RuntimeError, match="refusing"):
        prepare(manifest, dry_run=False)


def test_prepare_dry_run_has_no_side_effects(tmp_path):
    click_repo = tmp_path / "fake_click"
    click_sha = _make_local_repo(click_repo, {"click_marker.txt": "click contents"})
    template_repo = tmp_path / "fake_template"
    template_sha = _make_local_repo(template_repo, {"README.md": "TEMPLATE README"})
    fixture_dir = tmp_path / "todo_fixture"
    fixture_dir.mkdir()
    (fixture_dir / "todo.py").write_text("# todo cli", encoding="utf-8")

    manifest = _base_manifest(tmp_path, click_repo, click_sha, template_repo, template_sha, fixture_dir)
    prepare(manifest, dry_run=True)

    polygon = Path(manifest["polygon_root"])
    assert not polygon.exists()


# ---------------------------------------------------------------------------
# 4. collect-aggregation (sandbox_metrics/window_load/stall_estimate)
#    against a tmp sqlite db with synthetic cc_usage rows.
# ---------------------------------------------------------------------------


@pytest.fixture()
def cc_db(tmp_path):
    db_file = tmp_path / "requests.db"
    conn = sqlite3.connect(db_file)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def _insert_row(conn, project, session_id, dedupe_key, ts, output_tokens, cost, is_sidechain=0,
                 input_tokens=100):
    conn.execute(
        """
        INSERT INTO cc_usage
            (ts, project, session_id, turn_index, model, input_tokens, output_tokens,
             cache_creation_tokens, cache_read_tokens, accounted_cost_usd, traffic_kind,
             is_sidechain, dedupe_key)
        VALUES (?, ?, ?, 0, 'claude-sonnet-5', ?, ?, 0, 0, ?, 'real', ?, ?)
        """,
        (ts, project, session_id, input_tokens, output_tokens, cost, is_sidechain, dedupe_key),
    )
    conn.commit()


def test_sandbox_metrics_cost_side_wall_stall(cc_db):
    conn = cc_db
    proj = "D--fake-polygon-B-t1"
    # gap 1 (row1->row2): 70s, but row2's output (3000 tok) "eats" it
    # via the expected-generation-time formula (3000/40 + 10 = 85s >
    # 70s) -> stall contribution 0 for this gap.
    _insert_row(conn, proj, "s1", "s1:r1", "2026-07-07T12:00:00.000Z", 50, 0.01)
    _insert_row(conn, proj, "s1", "s1:r2", "2026-07-07T12:01:10.000Z", 3000, 0.05)
    # gap 2 (row2->row3): 200s, row3 output small (40 tok) -> expected
    # gen = 40/40 + 10 = 11s -> stall = 200 - 11 = 189s. row3 is a
    # sidechain (subagent) turn.
    _insert_row(conn, proj, "s1", "s1:r3", "2026-07-07T12:04:30.000Z", 40, 0.02, is_sidechain=1)

    metrics = sandbox_metrics(conn, proj)

    assert metrics["turns"] == 3
    assert metrics["cost_usd"] == pytest.approx(0.08)
    assert metrics["side_cost_usd"] == pytest.approx(0.02)
    assert metrics["side_share"] == pytest.approx(0.25)
    assert metrics["wall_start"] == "2026-07-07T12:00:00.000Z"
    assert metrics["wall_end"] == "2026-07-07T12:04:30.000Z"
    assert metrics["stall_est_seconds"] == pytest.approx(189.0)


def test_stall_estimate_gap_fully_eaten_by_generation_is_zero():
    turns = [
        ("2026-07-07T12:00:00.000Z", 50),
        ("2026-07-07T12:01:10.000Z", 3000),  # 70s gap, 85s expected gen
    ]
    assert stall_estimate(turns) == pytest.approx(0.0)


def test_stall_estimate_short_gaps_ignored():
    # Gaps <=60s never count, regardless of output size.
    turns = [
        ("2026-07-07T12:00:00.000Z", 5),
        ("2026-07-07T12:00:59.000Z", 5),
    ]
    assert stall_estimate(turns) == pytest.approx(0.0)


def test_window_load_separates_foreign_projects_and_respects_window(cc_db):
    conn = cc_db
    exam_proj = "D--fake-polygon-B-t1"
    other_in_window = "D--some-other-repo"
    other_outside_window = "D--another-repo-outside"

    _insert_row(conn, exam_proj, "s1", "s1:r1", "2026-07-07T12:00:00.000Z", 50, 0.01)
    _insert_row(conn, exam_proj, "s1", "s1:r2", "2026-07-07T12:05:00.000Z", 50, 0.01)

    # Foreign project active INSIDE the exam window -> must be counted.
    _insert_row(conn, other_in_window, "s2", "s2:r1", "2026-07-07T12:02:00.000Z", 400, 0.02)
    _insert_row(conn, other_in_window, "s2", "s2:r2", "2026-07-07T12:03:00.000Z", 600, 0.03)

    # Foreign project active OUTSIDE the exam window -> must be excluded.
    _insert_row(conn, other_outside_window, "s3", "s3:r1", "2026-07-07T13:30:00.000Z", 100, 0.01)

    load = window_load(
        conn, exclude_projects=[exam_proj],
        window_start="2026-07-07T12:00:00.000Z", window_end="2026-07-07T12:05:00.000Z",
    )

    projects_seen = {row["project"] for row in load}
    assert other_in_window in projects_seen
    assert exam_proj not in projects_seen
    assert other_outside_window not in projects_seen

    row = next(r for r in load if r["project"] == other_in_window)
    assert row["turns"] == 2
    assert row["out_tokens"] == 1000


# ---------------------------------------------------------------------------
# 5. project-name slug (~/.claude/projects encoding), pinned against
#    the real exam_release2 polygon on this machine.
# ---------------------------------------------------------------------------


def test_project_slug_matches_real_claude_projects_encoding():
    # Empirically confirmed 2026-07-15 against this machine's real
    # ~/.claude/projects listing for the given exam_release2 polygon
    # (D:\Improving_AI\exam_release2\{arm}\{task} sandboxes) -- every
    # one of the 12 real project dirs (A/B/C/B0 x t1/t2/t3) matches
    # this transform exactly. See builder report for the full listing.
    assert project_slug("D:/Improving_AI/exam_release2/A/t1") == "D--Improving-AI-exam-release2-A-t1"
    assert project_slug("D:\\Improving_AI\\exam_release2\\A\\t1") == "D--Improving-AI-exam-release2-A-t1"
    assert project_slug("D:/Improving_AI/exam_release2/B0/t2") == "D--Improving-AI-exam-release2-B0-t2"
    assert project_slug("D:/Improving_AI/exam_release2/C/t3") == "D--Improving-AI-exam-release2-C-t3"


def test_project_slug_matches_this_repo_own_project_dir():
    # A second, independent pin: this very repo's own project dir on
    # this machine is 'D--Improving-AI-Operating-System-for-LLMs'
    # (confirmed present in ~/.claude/projects during this task).
    assert (
        project_slug("D:/Improving_AI/Operating-System-for-LLMs")
        == "D--Improving-AI-Operating-System-for-LLMs"
    )


# ---------------------------------------------------------------------------
# 6. run() persists FULL stdout to a file, tail-only in run_log.json
#    (2026-07-15 backlog fix 1). subprocess.run is monkeypatched --
#    `claude` itself is never invoked here.
# ---------------------------------------------------------------------------


def _minimal_run_manifest(tmp_path, model="haiku"):
    return {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": str(tmp_path),
        },
        "model": model,
        "parallel": 1,
        "arms": [{"name": "A", "layout": "empty", "prefix": "", "suffix": ""}],
        "tasks": [{"id": "t1", "text": "hi", "needs": []}],
        "order": {"t1": ["A"]},
    }


def test_run_persists_full_stdout_and_truncates_run_log_tail(tmp_path, monkeypatch):
    import exam_runner as exam_runner_module

    long_stdout = ("X" * 3000) + "END_MARKER"

    class FakeProc:
        returncode = 0
        stdout = long_stdout

    def fake_subprocess_run(cmd, **kwargs):
        return FakeProc()

    monkeypatch.setattr(exam_runner_module.subprocess, "run", fake_subprocess_run)

    manifest = _minimal_run_manifest(tmp_path)
    results = run(manifest, dry_run=False)

    polygon_root = Path(manifest["polygon_root"])
    stdout_file = polygon_root / "stdout" / "A-t1.txt"
    assert stdout_file.exists()
    assert stdout_file.read_text(encoding="utf-8") == long_stdout

    run_log = json.loads((polygon_root / "run_log.json").read_text(encoding="utf-8"))
    assert run_log[0]["stdout_file"] == str(stdout_file)
    assert run_log[0]["stdout_tail"] == long_stdout[-2000:]
    assert len(run_log[0]["stdout_tail"]) == 2000
    assert results[0]["stdout_file"] == str(stdout_file)


# ---------------------------------------------------------------------------
# 7. run_dossier_tests() scopes discovery to session-created, non-click
#    test files (2026-07-15 backlog fix 2). Precedent: real run3c2
#    C/t2 dossier ran 33 of click's own upstream test_*.py files.
# ---------------------------------------------------------------------------


def test_run_dossier_tests_scopes_to_new_non_click_files(tmp_path):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    # Part of the prepared baseline layout (e.g. a template test file)
    # -- present in baseline_files, must NOT run.
    (sandbox / "test_baseline.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")

    # Session-created at top level -- MUST run.
    (sandbox / "test_new.py").write_text("def test_y():\n    assert True\n", encoding="utf-8")

    # Session-created INSIDE a needs=click clone subtree -- must NOT
    # run even though it is "new" relative to baseline, proving the
    # click/** exclusion is independent of (in addition to) the diff.
    click_dir = sandbox / "click"
    click_dir.mkdir()
    (click_dir / "test_click_new.py").write_text("def test_z():\n    assert True\n", encoding="utf-8")

    baseline_files = {"test_baseline.py"}
    results = run_dossier_tests(sandbox, baseline_files)

    assert {r["file"] for r in results} == {"test_new.py"}


# ---------------------------------------------------------------------------
# 8. sandbox_metrics() LIKE-slug aggregation (2026-07-15 backlog fix 3).
#    Precedent: real ~/.claude/projects dir
#    'D--Improving-AI-exam-run3c2-v020-sonnet-C-t2-click' next to
#    '...-C-t2' -- a sub-slug the plain equality match missed.
# ---------------------------------------------------------------------------


def test_sandbox_metrics_like_folds_in_sub_slug(cc_db):
    conn = cc_db
    proj = "D--fake-polygon-C-t2"
    sub_slug = proj + "-click"

    _insert_row(conn, proj, "s1", "s1:r1", "2026-07-07T12:00:00.000Z", 50, 0.10)
    _insert_row(conn, sub_slug, "s2", "s2:r1", "2026-07-07T12:01:00.000Z", 30, 0.05)

    metrics = sandbox_metrics(conn, proj)

    assert metrics["turns"] == 2
    assert metrics["cost_usd"] == pytest.approx(0.15)


def test_sandbox_metrics_like_does_not_match_unrelated_project(cc_db):
    conn = cc_db
    proj = "D--fake-polygon-C-t2"
    unrelated = "D--fake-polygon-C-t20"  # no '-' boundary after 't2' -> must NOT match

    _insert_row(conn, proj, "s1", "s1:r1", "2026-07-07T12:00:00.000Z", 50, 0.10)
    _insert_row(conn, unrelated, "s2", "s2:r1", "2026-07-07T12:01:00.000Z", 999, 9.99)

    metrics = sandbox_metrics(conn, proj)

    assert metrics["turns"] == 1
    assert metrics["cost_usd"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# 9. artifact-deliverable detection + full collect() wiring
#    (2026-07-15 backlog fix 4). Real precedent: A-t1 dossiers whose
#    deliverable was an Artifact link (dead outside the operator's own
#    account) -- see docs/tasks/2026-07-15_economy-exam-runs3-4.md
#    'evidence умирает с сессией'.
# ---------------------------------------------------------------------------


def test_detect_artifact_deliverable():
    assert detect_artifact_deliverable("built it: https://claude.ai/code/artifact/abc123") is True
    assert detect_artifact_deliverable("done, see gateway/test_metrics.py") is False
    assert detect_artifact_deliverable("") is False
    assert detect_artifact_deliverable(None) is False


def test_collect_wires_artifact_warning_test_scoping_and_like_metrics(tmp_path, monkeypatch):
    polygon_root = tmp_path / "polygon"
    sandbox = polygon_root / "A" / "t1"
    sandbox.mkdir(parents=True)
    (sandbox / "test_new.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    (polygon_root / "baseline_manifest.json").write_text(
        json.dumps({"A/t1": []}), encoding="utf-8"
    )

    stdout_dir = polygon_root / "stdout"
    stdout_dir.mkdir()
    (stdout_dir / "A-t1.txt").write_text(
        "report: https://claude.ai/code/artifact/deadbeef", encoding="utf-8"
    )

    db_file = tmp_path / "requests.db"
    conn = sqlite3.connect(db_file)
    conn.execute(SCHEMA)
    conn.commit()
    project = project_slug(sandbox)
    _insert_row(conn, project, "s1", "s1:r1", "2026-07-07T12:00:00.000Z", 50, 0.10)
    _insert_row(conn, project + "-click", "s2", "s2:r1", "2026-07-07T12:01:00.000Z", 30, 0.05)
    conn.close()

    monkeypatch.setattr(usage_report, "db_path", lambda: db_file)
    monkeypatch.setattr(usage_report, "transcript_glob", lambda: [])

    manifest = {
        "polygon_root": str(polygon_root),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": str(tmp_path),
        },
        "model": "haiku",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "text": "hi", "needs": []}],
        "order": {"t1": ["A"]},
    }
    validate_manifest(manifest)

    dossier = collect(manifest, dry_run=False)

    row = dossier["sandboxes"][0]
    assert row["cost_usd"] == pytest.approx(0.15)  # sub-slug folded in (fix 3)
    assert row["artifact_warning"] is True  # fix 4
    assert {t["file"] for t in row["tests"]} == {"test_new.py"}  # fix 2

    md = (polygon_root / "dossier.md").read_text(encoding="utf-8")
    assert "deliverable = внешний артефакт (может быть недоступен вне аккаунта)" in md


# ---------------------------------------------------------------------------
# 10. multi-session tasks (t-132, spec
#     docs/tasks/2026-07-15_economy-exam-set2.md): task['sessions'] is an
#     alternative to task['text'] -- N separate headless sessions run
#     SEQUENTIALLY in the same (task, arm) sandbox cwd, with per-session
#     run_log accounting and a default stop-the-chain on nonzero rc.
# ---------------------------------------------------------------------------


def test_validate_manifest_task_with_sessions_ok(tmp_path):
    manifest = {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": str(tmp_path),
        },
        "model": "haiku",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "sessions": ["do X", "do Y"], "needs": []}],
        "order": {"t1": ["A"]},
    }
    validated = validate_manifest(manifest)
    assert validated["parallel"] == 1


def test_validate_manifest_task_missing_text_and_sessions_raises():
    manifest = {
        "polygon_root": "x",
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": "x",
        },
        "model": "sonnet",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1"}],
        "order": {"t1": ["A"]},
    }
    with pytest.raises(ValueError, match="'text' or 'sessions'"):
        validate_manifest(manifest)


def test_validate_manifest_task_both_text_and_sessions_raises():
    manifest = {
        "polygon_root": "x",
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": "x",
        },
        "model": "sonnet",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "text": "hi", "sessions": ["hi"]}],
        "order": {"t1": ["A"]},
    }
    with pytest.raises(ValueError, match="both 'text' and 'sessions'"):
        validate_manifest(manifest)


def test_validate_manifest_task_sessions_empty_list_raises():
    manifest = {
        "polygon_root": "x",
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": "x",
        },
        "model": "sonnet",
        "arms": [{"name": "A", "layout": "empty"}],
        "tasks": [{"id": "t1", "sessions": []}],
        "order": {"t1": ["A"]},
    }
    with pytest.raises(ValueError, match="non-empty list of strings"):
        validate_manifest(manifest)


def test_build_launch_plan_sessions_wraps_each_with_arm_prefix_suffix(tmp_path):
    manifest = {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": str(tmp_path),
        },
        "model": "haiku",
        "parallel": 1,
        "arms": [{"name": "C", "layout": "empty", "prefix": "PFX\n\n", "suffix": "\n\nSFX"}],
        "tasks": [{"id": "t1", "sessions": ["session one", "session two"], "needs": []}],
        "order": {"t1": ["C"]},
    }
    plan = build_launch_plan(manifest)
    assert len(plan) == 1
    launch = plan[0]
    # The arm's prefix/suffix (the same mechanism the headless-escalation
    # protez suffix travels through, PROCESS/DEPLOYMENT_ECONOMY_EXAM.md)
    # is applied to EVERY session, not just the first.
    assert launch["sessions"] == ["PFX\n\nsession one\n\nSFX", "PFX\n\nsession two\n\nSFX"]
    # backward-compat 'text' field mirrors the first session.
    assert launch["text"] == launch["sessions"][0]
    assert launch["cwd"] == str(Path(manifest["polygon_root"]) / "C" / "t1")


def _multi_session_manifest(tmp_path, texts, model="haiku"):
    return {
        "polygon_root": str(tmp_path / "polygon"),
        "src": {
            "click_git": "x", "click_pin": "y",
            "template_git": "x", "template_ref": "y", "fixture_dir": str(tmp_path),
        },
        "model": model,
        "parallel": 1,
        "arms": [{"name": "A", "layout": "empty", "prefix": "", "suffix": ""}],
        "tasks": [{"id": "t1", "sessions": texts, "needs": []}],
        "order": {"t1": ["A"]},
    }


def test_run_multi_session_sequential_same_cwd_and_per_session_accounting(tmp_path, monkeypatch):
    import exam_runner as exam_runner_module

    calls = []

    def fake_subprocess_run(cmd, **kwargs):
        calls.append({"cwd": kwargs.get("cwd"), "input": kwargs.get("input")})

        class FakeProc:
            returncode = 0
            stdout = f"ok session {len(calls)}"
        return FakeProc()

    monkeypatch.setattr(exam_runner_module.subprocess, "run", fake_subprocess_run)

    manifest = _multi_session_manifest(tmp_path, ["do ping", "do pong"])
    results = run(manifest, dry_run=False)

    assert len(results) == 1
    entry = results[0]
    assert entry["sessions_total"] == 2
    assert entry["stopped_early"] is False
    assert len(entry["sessions"]) == 2
    assert entry["rc"] == 0

    # Both claude invocations targeted the SAME sandbox cwd (spec: one
    # cwd for the whole multi-session task).
    assert calls[0]["cwd"] == calls[1]["cwd"] == entry["cwd"]
    # Prompts delivered in session order via stdin (session N+1 only
    # after N -- guaranteed here by the plain in-process loop, verified
    # by the ordered fake_subprocess_run call log).
    assert calls[0]["input"] == "do ping"
    assert calls[1]["input"] == "do pong"

    polygon_root = Path(manifest["polygon_root"])
    s1 = entry["sessions"][0]
    s2 = entry["sessions"][1]
    assert s1["session_index"] == 0
    assert s2["session_index"] == 1
    assert s1["stdout_file"] == str(polygon_root / "stdout" / "A-t1-s1.txt")
    assert s2["stdout_file"] == str(polygon_root / "stdout" / "A-t1-s2.txt")
    assert Path(s1["stdout_file"]).read_text(encoding="utf-8") == "ok session 1"
    assert Path(s2["stdout_file"]).read_text(encoding="utf-8") == "ok session 2"
    assert s1["start_ts"] and s1["end_ts"]
    assert s2["start_ts"] and s2["end_ts"]

    run_log = json.loads((polygon_root / "run_log.json").read_text(encoding="utf-8"))
    assert run_log[0]["sessions_total"] == 2
    assert run_log[0]["stopped_early"] is False


def test_run_multi_session_stops_chain_on_nonzero_rc(tmp_path, monkeypatch):
    import exam_runner as exam_runner_module

    def fake_subprocess_run(cmd, **kwargs):
        idx = fake_subprocess_run.calls
        fake_subprocess_run.calls += 1

        class FakeProc:
            returncode = 1 if idx == 1 else 0
            stdout = f"session {idx}"
        return FakeProc()
    fake_subprocess_run.calls = 0

    monkeypatch.setattr(exam_runner_module.subprocess, "run", fake_subprocess_run)

    manifest = _multi_session_manifest(tmp_path, ["s1 ok", "s2 fails", "s3 never runs"])
    results = run(manifest, dry_run=False)

    entry = results[0]
    assert entry["sessions_total"] == 3
    assert entry["stopped_early"] is True
    assert len(entry["sessions"]) == 2  # s3 never launched -- chain stopped on s2's rc=1
    assert entry["rc"] == 1
    assert entry["sessions"][0]["rc"] == 0
    assert entry["sessions"][1]["rc"] == 1

    polygon_root = Path(manifest["polygon_root"])
    stdout_dir = polygon_root / "stdout"
    assert (stdout_dir / "A-t1-s1.txt").exists()
    assert (stdout_dir / "A-t1-s2.txt").exists()
    assert not (stdout_dir / "A-t1-s3.txt").exists()  # never invoked
    assert fake_subprocess_run.calls == 2


def test_run_classic_single_text_task_unaffected_by_sessions_feature(tmp_path, monkeypatch):
    """Backward compatibility (spec point 2): a classic single-'text'
    task's run_log entry keeps the exact pre-t-132 flat shape -- no
    'sessions'/'sessions_total'/'stopped_early' keys leak in."""
    import exam_runner as exam_runner_module

    class FakeProc:
        returncode = 0
        stdout = "classic ok"

    monkeypatch.setattr(exam_runner_module.subprocess, "run", lambda cmd, **kw: FakeProc())

    manifest = _minimal_run_manifest(tmp_path)
    results = run(manifest, dry_run=False)

    entry = results[0]
    assert "sessions" not in entry
    assert "sessions_total" not in entry
    assert "stopped_early" not in entry
    assert entry["rc"] == 0
    assert set(entry.keys()) == {
        "order_index", "task_id", "arm", "cwd",
        "start_ts", "end_ts", "rc", "stdout_tail", "stdout_file",
    }


# ---------------------------------------------------------------------------
# 11. collect() artifact-deliverable detection for multi-session tasks
#     (critic t-132 retry blocker, 2026-07-15): the classic
#     '<arm>-<task>.txt' filename reconstruction never matches a
#     multi-session task's '-sN.txt' stdout files, so the detector was
#     silently False for every multi-session sandbox. Fixed by reading
#     stdout_file paths off run_log.json's own entry (flat for
#     classic, per-session list for multi-session) instead of
#     reconstructing a name.
# ---------------------------------------------------------------------------


def _collect_db_setup(tmp_path, monkeypatch):
    """Empty cc_usage db + no real transcripts to import -- collect()
    still needs SOMETHING at usage_report.db_path()/transcript_glob()
    to run its import/metrics steps without touching the real machine
    state (same pattern as test_collect_wires_artifact_warning...)."""
    db_file = tmp_path / "requests.db"
    conn = sqlite3.connect(db_file)
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr(usage_report, "db_path", lambda: db_file)
    monkeypatch.setattr(usage_report, "transcript_glob", lambda: [])


def test_collect_artifact_warning_true_when_any_multi_session_stdout_has_url(tmp_path, monkeypatch):
    import exam_runner as exam_runner_module

    def fake_subprocess_run(cmd, **kwargs):
        call = fake_subprocess_run.calls
        fake_subprocess_run.calls += 1

        class FakeProc:
            returncode = 0
            # No marker in session 1's stdout; session 2's carries the
            # Artifact URL -- this is the exact shape the old
            # reconstruction missed (it only ever looked at a
            # '<arm>-<task>.txt' file that a multi-session run never
            # writes).
            stdout = (
                "session 1: nothing to see here"
                if call == 0
                else "session 2: report at https://claude.ai/code/artifact/deadbeef"
            )
        return FakeProc()
    fake_subprocess_run.calls = 0
    monkeypatch.setattr(exam_runner_module.subprocess, "run", fake_subprocess_run)

    manifest = _multi_session_manifest(tmp_path, ["s1 text", "s2 text"])
    run(manifest, dry_run=False)  # writes run_log.json + per-session stdout files

    _collect_db_setup(tmp_path, monkeypatch)
    dossier = collect(manifest, dry_run=False)

    row = dossier["sandboxes"][0]
    assert row["artifact_warning"] is True


def test_collect_artifact_warning_false_when_no_multi_session_stdout_has_url(tmp_path, monkeypatch):
    import exam_runner as exam_runner_module

    def fake_subprocess_run(cmd, **kwargs):
        class FakeProc:
            returncode = 0
            stdout = "plain text, no deliverable link in any session"
        return FakeProc()

    monkeypatch.setattr(exam_runner_module.subprocess, "run", fake_subprocess_run)

    manifest = _multi_session_manifest(tmp_path, ["s1 text", "s2 text"])
    run(manifest, dry_run=False)

    _collect_db_setup(tmp_path, monkeypatch)
    dossier = collect(manifest, dry_run=False)

    row = dossier["sandboxes"][0]
    assert row["artifact_warning"] is False
