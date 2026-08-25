"""Tests for tools/critic_snapshot.py.

The payload-submission form mirrors tools/test_dispatch_gate.py's own
subprocess smokes for the hook (`_run_hook`: sys.executable + SCRIPT,
a JSON payload via stdin, ensure_ascii=False -> encode utf-8) -- a
second submission style is not invented.

Two GROUPS of tests:
  (A) E2E via subprocess -- the hook's public contract (which payloads
      are ignored, the normal snapshot write, cwd STRICTLY from the
      payload, not the real process) -- see `_run_hook`.
  (B) In-process, direct import of `critic_snapshot` -- for branches a
      subprocess cannot reliably trigger (the tree walk breaking, OR
      the snapshot write breaking): this monkeypatches internal
      functions / `Path.write_text` / `sys.stdin` of this same
      process. Rationale for this choice: emulating an "unreadable
      file" via chmod is unreliable on Windows -- NTFS's owning-process
      permissions ignore the read-only bit for reading content (it only
      blocks writes), so `chmod(0o000)` would not stop
      `Path.read_bytes()` from the same process; instead
      `Path.read_bytes` is monkeypatched for ONE specific target path --
      documented here and in the specific test's own docstring, not
      guessed silently.

EDGE -- the snapshot is written into the cwd FROM THE PAYLOAD, not the
real process (see critic_snapshot.py main(): `cwd = Path(payload.get
("cwd") or ".")`): every writing test below EXPLICITLY passes
payload["cwd"] = str(tmp_path); a dedicated test
(`test_real_repo_snapshot_untouched_by_tmp_path_dispatch`) asserts this
separately -- it snapshots the bytes of the REAL .claude/
critic_snapshot.json BEFORE and AFTER running the hook with
cwd=tmp_path and asserts they are byte-for-byte equal.

Run from the repo root: python -m pytest toolkit/tools/test_critic_snapshot.py
"""

import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import critic_snapshot as cs  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "critic_snapshot.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_SNAPSHOT = _REPO_ROOT / ".claude" / "critic_snapshot.json"


def _run_hook(payload, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd is not None else None,
    )


def _critic_payload(cwd: Path, tool_name="Task") -> dict:
    return {
        "tool_name": tool_name,
        "tool_input": {"subagent_type": "critic"},
        "cwd": str(cwd),
    }


class _FakeStdin:
    """Feeds bytes into sys.stdin.buffer for a direct call to cs.main()
    -- main() reads ONLY sys.stdin.buffer.read() (the raw-byte variant,
    see critic_snapshot.py's own docstring), so it's enough to replace
    .buffer, not the whole sys.stdin API."""

    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


# ---------------------------------------------------------------------
# (A) E2E: payload filtering -- no snapshot is written, exit is always 0.
# ---------------------------------------------------------------------


def test_non_task_tool_name_no_snapshot_written_exit0(tmp_path):
    payload = {"tool_name": "Bash", "tool_input": {"subagent_type": "critic"}, "cwd": str(tmp_path)}
    result = _run_hook(payload)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()


def test_task_wrong_subagent_type_no_snapshot_written_exit0(tmp_path):
    payload = {"tool_name": "Task", "tool_input": {"subagent_type": "builder"}, "cwd": str(tmp_path)}
    result = _run_hook(payload)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()


def test_invalid_json_payload_fail_open_exit0_no_crash():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=b"{not valid json at all",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0
    assert result.stdout == b""


# ---------------------------------------------------------------------
# (A) E2E: the normal path -- both Task AND Agent are recognized, the
# snapshot is written with all fields, cwd is strictly from the payload.
# ---------------------------------------------------------------------


def test_agent_tool_name_recognized_writes_snapshot_with_expected_fields(tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world", encoding="utf-8")

    result = _run_hook(_critic_payload(tmp_path, tool_name="Agent"), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    assert snap.exists()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"ts", "tree_hash", "files_count", "skipped_files"}
    assert doc["skipped_files"] == 0
    assert doc["files_count"] == 2

    # Cross-check: the same walk, called directly in this process,
    # gives the BIT-FOR-BIT same tree_hash/files_count -- not just "the
    # field exists", but "the field matches an independent computation".
    expected_hash, expected_count, expected_skipped = cs.compute_tree_hash(tmp_path)
    assert doc["tree_hash"] == expected_hash
    assert doc["files_count"] == expected_count
    assert doc["skipped_files"] == expected_skipped


def test_real_repo_snapshot_untouched_by_tmp_path_dispatch(tmp_path):
    # Edge: the snapshot is written into the cwd FROM THE PAYLOAD --
    # running the hook with cwd=tmp_path must never touch this repo's
    # real .claude/critic_snapshot.json, under any circumstance.
    before = _REAL_SNAPSHOT.read_bytes() if _REAL_SNAPSHOT.exists() else None
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    after = _REAL_SNAPSHOT.read_bytes() if _REAL_SNAPSHOT.exists() else None
    assert before == after, "the real .claude/critic_snapshot.json changed -- edge violation"


# ---------------------------------------------------------------------
# (B) in-process: a SINGLE unreadable tree file -- the walk does not fail.
# ---------------------------------------------------------------------


def test_compute_tree_hash_unreadable_single_file_increments_skipped_continues(tmp_path, monkeypatch):
    """Edge: chmod on Windows does not reliably make a file unreadable
    for the OWNING process (the NTFS read-only bit protects against
    writes, not against the same process reading content) -- instead
    Path.read_bytes is monkeypatched ONLY for the specific target path
    (bad.txt), every other call (including good.txt) goes through the
    original method."""
    good = tmp_path / "good.txt"
    good.write_text("readable", encoding="utf-8")
    bad = tmp_path / "bad.txt"
    bad.write_text("unreadable-in-this-test", encoding="utf-8")

    orig_read_bytes = Path.read_bytes
    bad_resolved = bad.resolve()

    def flaky_read_bytes(self):
        if self.resolve() == bad_resolved:
            raise PermissionError(f"simulated unreadable file: {self}")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read_bytes)

    tree_hash, files_count, skipped_files = cs.compute_tree_hash(tmp_path)

    assert skipped_files == 1
    assert files_count == 1  # only good.txt entered the tree

    # tree_hash must match a hash computed over good.txt ALONE (the
    # same formula compute_tree_hash uses internally).
    import hashlib
    rel = good.relative_to(tmp_path)
    digest = hashlib.sha256(orig_read_bytes(good)).hexdigest()
    expected_entry = f"{rel.as_posix()}:{digest}"
    expected_hash = hashlib.sha256(expected_entry.encode("utf-8")).hexdigest()
    assert tree_hash == expected_hash


# ---------------------------------------------------------------------
# (B) in-process: TWO DISTINCT failure points in main() -- the tree
# walk vs. writing the snapshot -- different resulting documents (see
# critic_snapshot.py's own docstring, "TWO DISTINCT FAILURE POINTS").
# ---------------------------------------------------------------------


def test_main_tree_walk_failure_writes_error_document_and_stderr(tmp_path, monkeypatch, capsys):
    def _boom(_root):
        raise RuntimeError("simulated tree-walk failure")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    assert snap.exists()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"error", "error_ts"}
    assert "RuntimeError" in doc["error"]
    assert "simulated tree-walk failure" in doc["error"]

    err = capsys.readouterr().err
    assert "FAILED to take snapshot" in err
    assert "RuntimeError" in err


def test_main_write_failure_only_stderr_no_file_written(tmp_path, monkeypatch, capsys):
    """The snapshot-WRITE failure branch ("stderr only, exit 0 -- the
    file cannot be written by construction"): Path.write_text ALWAYS
    raises -- both the normal write in main() and the retry write in
    _write_failure_snapshot() (the same path, the same failure cause)
    both fail, the failure document never appears, only the stderr
    diagnostic."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    def _always_raise(self, *a, **kw):
        raise OSError("simulated disk full")

    monkeypatch.setattr(Path, "write_text", _always_raise)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    assert not snap.exists()

    err = capsys.readouterr().err
    assert "FAILED to take snapshot" in err
    assert "OSError" in err


def test_failure_document_replaces_prior_success_shape_but_preserves_prev_fields(
    tmp_path, monkeypatch, capsys,
):
    """A failure document REPLACES the shape of a normal one (no key
    "tree_hash" -- see critic_snapshot.py's own docstring, the
    invariant "a failure document never looks like a valid snapshot"),
    but does NOT fully lose the previous REAL success's data:
    ts/tree_hash of the last snapshot are copied into
    prev_ts/prev_tree_hash -- a failure no longer erases the last
    successful baseline wholesale (a stale-but-REAL snapshot is more
    useful to a future grader than a total absence of tree_hash)."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    # 1) a normal successful call -- via subprocess (the real e2e path).
    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    snap = tmp_path / ".claude" / "critic_snapshot.json"
    before_doc = json.loads(snap.read_text(encoding="utf-8"))
    assert "tree_hash" in before_doc

    # 2) the next call, same snapshot path -- the tree walk now fails.
    def _boom(_root):
        raise RuntimeError("simulated second-call failure")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    after_doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(after_doc.keys()) == {"error", "error_ts", "prev_ts", "prev_tree_hash"}
    assert "tree_hash" not in after_doc  # the shape invariant holds
    assert "files_count" not in after_doc
    assert after_doc["prev_ts"] == before_doc["ts"]
    assert after_doc["prev_tree_hash"] == before_doc["tree_hash"]


def test_failure_document_no_prev_fields_when_no_prior_snapshot_exists(
    tmp_path, monkeypatch,
):
    # Control side: there is NO prior snapshot at all (a fresh
    # tmp_path) -- prev_ts/prev_tree_hash are NOT added (nothing to
    # copy, nothing is invented) -- a strict {"error","error_ts"}, as
    # before.
    def _boom(_root):
        raise RuntimeError("simulated failure, no prior snapshot")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"error", "error_ts"}


def test_failure_document_no_prev_fields_when_prior_was_itself_a_failure(
    tmp_path, monkeypatch,
):
    # A failure does NOT inherit prev_* from a PREVIOUS failure (that
    # one has no tree_hash of its own) -- otherwise a chain of failures
    # would drag old data forward indefinitely without re-evaluation.
    snap = tmp_path / ".claude" / "critic_snapshot.json"
    snap.parent.mkdir(parents=True)
    snap.write_text(json.dumps({"error": "prior failure", "error_ts": "x"}), encoding="utf-8")

    def _boom(_root):
        raise RuntimeError("simulated second failure in a row")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"error", "error_ts"}


# ---------------------------------------------------------------------
# M2-1: a dispatch that dispatch_gate.decide() ACTUALLY BLOCKS (exit 2 on the
# SAME payload) -- no snapshot is written, the prior snapshot stays
# byte-for-byte untouched. Three tests: block -> old snapshot intact,
# pass (not blocked) -> a new one is written, an exception out of
# dispatch_gate.decide -> written anyway (fail-open).
# ---------------------------------------------------------------------


def _blocked_critic_payload(cwd: Path) -> dict:
    """subagent_type=="critic" (the snapshot even considers this call),
    but a description with NO model-prefix separator at all -- this
    kit's actual dispatch_gate.decide() on this payload gives (2, ...)
    -- see LABEL_MODEL_PREFIX_RE in tools/dispatch_gate.py (checked
    empirically before writing this test: this kit's own
    LABEL_MODEL_PREFIX_RE = r"^\\S+[ :-]", broader than the reference
    deployment's tier-word-only form -- a description with no space/
    colon/dash separator anywhere fails it regardless)."""
    return {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "critic",
            "description": "nomodelprefixlabelatall",
            "prompt": "irrelevant",
        },
        "cwd": str(cwd),
    }


def test_m2_1_blocked_dispatch_leaves_prior_snapshot_byte_identical(tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    # 1) a normal successful call -- creates a REAL snapshot with known
    # content (the "old" source of truth).
    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    snap = tmp_path / ".claude" / "critic_snapshot.json"
    before_bytes = snap.read_bytes()
    assert b"tree_hash" in before_bytes

    # 2) a dispatch dispatch_gate.decide() ACTUALLY BLOCKS (exit 2) --
    # the snapshot must not change by even one byte.
    result2 = _run_hook(_blocked_critic_payload(tmp_path), cwd=tmp_path)
    assert result2.returncode == 0, (
        "critic_snapshot's own exit must stay 0 even on the blocked "
        "branch: " + result2.stderr.decode("utf-8", errors="replace")
    )

    after_bytes = snap.read_bytes()
    assert after_bytes == before_bytes, (
        "a blocked dispatch overwrote the snapshot -- M2-1 edge (i) "
        "violated: the old snapshot must stay byte-for-byte untouched"
    )


def test_m2_1_non_blocked_dispatch_still_writes_new_snapshot(tmp_path):
    """Control (the positive side of the pair): a payload with a
    CORRECT model-prefix in description -- dispatch_gate.decide() does
    NOT block (0, '') -- the snapshot is written AS USUAL (the second
    call's ts must differ from the first's -- a real overwrite
    happened)."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "critic",
            "description": "sonnet: review the diff",
            "prompt": "irrelevant",
        },
        "cwd": str(tmp_path),
    }

    result = _run_hook(payload, cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    snap = tmp_path / ".claude" / "critic_snapshot.json"
    first_ts = json.loads(snap.read_text(encoding="utf-8"))["ts"]

    result2 = _run_hook(payload, cwd=tmp_path)
    assert result2.returncode == 0, result2.stderr.decode("utf-8", errors="replace")
    second_doc = json.loads(snap.read_text(encoding="utf-8"))
    assert "tree_hash" in second_doc
    assert second_doc["ts"] != first_ts, (
        "a non-blocked dispatch did not overwrite the snapshot -- "
        "regression of the normal M2-1 path"
    )


# ---------------------------------------------------------------------
# LOCAL IMPORT ("LOCAL IMPORT" in the module docstring):
# the dispatch_gate import lives INSIDE main(), locally, AFTER early
# exits -- an IMPORT failure (not just a decide() failure) is also
# under fail-open. Both failure scenarios -- IMPORT and decide() -- are
# checked via a subprocess on an ISOLATED copy of critic_snapshot.py
# (not module-attribute monkeypatch -- after moving the import inside
# the function, `cs.dispatch_gate` no longer exists as a module
# attribute of the critic_snapshot module at all; a subprocess is the
# REAL, not simulated, form of an import failure).
# ---------------------------------------------------------------------


def _write_isolated_copy(tmp_path, dirname: str, with_dispatch_gate: bool, broken_decide: bool = False):
    """A copy of critic_snapshot.py (NO mutation -- byte-for-byte) into
    an isolated tools/ directory. with_dispatch_gate=False -- the
    sibling is absent entirely (a real ImportError on both import
    forms -- neither the `tools` package nor a sibling module is
    visible on the subprocess's sys.path, whose script directory is
    the only relevant element). with_dispatch_gate=True,
    broken_decide=True -- the sibling is present, but its decide()
    unconditionally raises (a different failure point -- not the
    import, the call itself)."""
    repo_root = tmp_path / dirname
    tools_dir = repo_root / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "critic_snapshot.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    if with_dispatch_gate:
        dg_src = (SCRIPT.parent / "dispatch_gate.py").read_text(encoding="utf-8")
        if broken_decide:
            dg_src += (
                "\n\n# test probe: decide() unconditionally raises.\n"
                "def decide(payload):\n"
                '    raise RuntimeError("simulated dispatch_gate.decide failure")\n'
            )
        (tools_dir / "dispatch_gate.py").write_text(dg_src, encoding="utf-8")
    return tools_dir / "critic_snapshot.py"


def test_missing_dispatch_gate_sibling_fail_open_snapshot_written(tmp_path):
    """A literal witness case: running critic_snapshot WITHOUT the
    dispatch_gate.py sibling module -> rc 0, the snapshot is written
    fail-open (a normal successful snapshot, tree_hash present -- the
    IMPORT failed, gate_exit_code is treated as 0 -- "not blocked")."""
    script = _write_isolated_copy(tmp_path, "isolated_no_sibling", with_dispatch_gate=False)
    work_cwd = tmp_path / "work_no_sibling"
    work_cwd.mkdir()
    (work_cwd / "a.txt").write_text("hello", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(_critic_payload(work_cwd), ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(work_cwd),
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

    snap = work_cwd / ".claude" / "critic_snapshot.json"
    assert snap.exists()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert "tree_hash" in doc, (
        "a missing dispatch_gate.py sibling (ImportError) must "
        "fail-open write a normal snapshot, not block the write"
    )


def test_non_critic_dispatch_never_needs_sibling_import_at_all(tmp_path):
    """Structural proof of the cost argument (not timing -- an
    observable fact): WITHOUT the dispatch_gate.py sibling AT ALL, a
    non-critic dispatch (subagent_type="builder") passes cleanly -- the
    early exit (subagent_type != "critic") happens BEFORE the import
    line, so non-critic dispatches (the vast majority) NEVER pay the
    import cost -- if they did, there would be an ImportError here
    (the sibling is entirely absent), which main() would either not
    catch (pre-fix code -- a module-level import, caught even before
    main() runs) or would catch, but the test still would NOT prove
    "never needed at all" -- it would only prove "fail-open worked"."""
    script = _write_isolated_copy(tmp_path, "isolated_non_critic", with_dispatch_gate=False)
    work_cwd = tmp_path / "work_non_critic"
    work_cwd.mkdir()

    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder"},
        "cwd": str(work_cwd),
    }
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(work_cwd),
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not (work_cwd / ".claude" / "critic_snapshot.json").exists()


def test_dispatch_gate_decide_raises_fail_open_snapshot_written(tmp_path):
    """The second failure point (not the import -- the call to
    decide() itself): the sibling IS present, but its decide()
    unconditionally raises -- the same fail-open branch (one shared
    except around BOTH the import and the call)."""
    script = _write_isolated_copy(
        tmp_path, "isolated_broken_decide", with_dispatch_gate=True, broken_decide=True
    )
    work_cwd = tmp_path / "work_broken_decide"
    work_cwd.mkdir()
    (work_cwd / "a.txt").write_text("hello", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(_critic_payload(work_cwd), ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(work_cwd),
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

    snap = work_cwd / ".claude" / "critic_snapshot.json"
    assert snap.exists()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert "tree_hash" in doc


# ---------------------------------------------------------------------
# P4: stdin-deadline -- a hanging stdin degrades to
# no-payload (exit 0, no snapshot, no crash), bounded by
# OSLLM_STDIN_TIMEOUT rather than blocking forever.
# ---------------------------------------------------------------------


def test_stdin_deadline_hanging_pipe_degrades_to_no_payload(tmp_path):
    env = dict(__import__("os").environ, OSLLM_STDIN_TIMEOUT="0.3")
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
        env=env,
    )
    try:
        out, err = proc.communicate(timeout=10)
    finally:
        proc.stdin.close()
    assert proc.returncode == 0
    assert out.strip() == b""
    assert b"Traceback" not in err
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()
