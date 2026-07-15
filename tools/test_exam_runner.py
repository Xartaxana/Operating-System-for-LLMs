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

from exam_runner import (
    build_launch_plan,
    load_manifest,
    prepare,
    project_slug,
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
