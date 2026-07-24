"""Tests for tools/parity_check.py (VG-6).

All fixtures live under pytest's tmp_path -- NEVER the live repo. The
tool is invoked two ways:
  - via subprocess (real process, real CLI, real stdout/exit code) for
    every case where "no traceback, explicit error" must be verified
    end-to-end;
  - via direct import of the module's functions for pure-logic unit
    checks (classify(), discover_pairs()) where subprocess overhead adds
    nothing.

Covers DoD:
 1. Four outcomes (clean/hq-drift/kit-drift/both-drift) distinguished
    correctly, one test per outcome plus a mixed-manifest run.
 2. --sync updates exactly one pair; --init without --force refuses to
    overwrite an existing manifest.
 3. Adversarial battery: pair file deleted; manifest broken JSON;
    duplicate pair in manifest; CRLF vs LF (t-309 addendum: NORMALIZED
    before hashing -- a checkout-only CRLF/LF difference is no longer
    drift, see the "t-309 addendum" section below for the boundary
    battery; a REAL content difference under a CRLF checkout is still
    detected); unicode filenames; empty file. All produce explicit
    errors, never a traceback.
 4. --init generates a manifest matching the live repo intersection
    rules (tested against a synthetic layout mirroring the real one,
    not the live repo itself).

No MAX_*/limit constants are introduced by this tool (manifest is an
unbounded JSON list, no depth/length ceilings) -- rule 6a's
boundary-test duty therefore has no target here; noted explicitly so
this isn't mistaken for an oversight.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parity_check  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "parity_check.py"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    # Windows fix (t-309): explicit encoding="utf-8" -- without it, text=True
    # falls back to locale.getpreferredencoding(False) (cp1251 observed on
    # this machine) to DECODE the child's stdout/stderr bytes. The child
    # (tools/parity_check.py) now explicitly reconfigures its own stdout to
    # UTF-8 (see parity_check._reconfigure_stdout_utf8) so unicode paths in
    # the manifest print cleanly instead of crashing -- but that fix alone
    # only fixes the WRITE side; the parent (this test harness) must decode
    # with the SAME encoding on the READ side, or UTF-8 bytes get
    # mis-decoded as cp1251 (mojibake, not a crash, but not equal to the
    # original string either -- see test_unicode_filenames_handled_cleanly).
    # errors="replace" keeps this fail-open/never-crash on the test side
    # too, matching the tool's own contract (module docstring, "EXIT CODE
    # CONTRACT": parity_check never raises on report formatting).
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def assert_no_traceback(proc: subprocess.CompletedProcess) -> None:
    combined = proc.stdout + proc.stderr
    assert "Traceback" not in combined, f"unexpected traceback:\n{combined}"


def write_pair(root: Path, hq_rel: str, kit_rel: str, hq_bytes: bytes, kit_bytes: bytes) -> None:
    hq_path = root / hq_rel
    kit_path = root / kit_rel
    hq_path.parent.mkdir(parents=True, exist_ok=True)
    kit_path.parent.mkdir(parents=True, exist_ok=True)
    hq_path.write_bytes(hq_bytes)
    kit_path.write_bytes(kit_bytes)


def manifest_entry(hq_rel: str, kit_rel: str, hq_bytes: bytes, kit_bytes: bytes, note: str = "") -> dict:
    return {
        "hq": hq_rel,
        "kit": kit_rel,
        "synced_hq_sha256": sha256_bytes(hq_bytes),
        "synced_kit_sha256": sha256_bytes(kit_bytes),
        "synced_at": "2026-07-01T00:00:00",
        "note": note,
    }


def write_manifest(root: Path, entries: list[dict]) -> Path:
    manifest_path = root / "tools" / "parity_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return manifest_path


# ---------------------------------------------------------------------------
# 1. classify() unit tests -- the four outcomes
# ---------------------------------------------------------------------------

def test_classify_clean():
    assert parity_check.classify("h", "k", "h", "k") == "clean"


def test_classify_hq_drift():
    assert parity_check.classify("h", "k", "H2", "k") == "hq-drift"


def test_classify_kit_drift():
    assert parity_check.classify("h", "k", "h", "K2") == "kit-drift"


def test_classify_both_drift():
    assert parity_check.classify("h", "k", "H2", "K2") == "both-drift"


# ---------------------------------------------------------------------------
# 1b. --check end-to-end: one manifest exercising all four outcomes at once
# ---------------------------------------------------------------------------

def test_check_reports_all_four_outcomes_and_exits_0(tmp_path):
    root = tmp_path
    entries = []

    # clean pair
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n")
    entries.append(manifest_entry("tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n"))

    # hq-drift: hq changed after sync, kit untouched
    write_pair(root, "tools/b.py", "toolkit/tools/b.py", b"hq new\n", b"kit old\n")
    entries.append(manifest_entry("tools/b.py", "toolkit/tools/b.py", b"hq old\n", b"kit old\n"))

    # kit-drift: kit changed after sync, hq untouched -- suspicious
    write_pair(root, "tools/c.py", "toolkit/tools/c.py", b"hq old\n", b"kit new\n")
    entries.append(manifest_entry("tools/c.py", "toolkit/tools/c.py", b"hq old\n", b"kit old\n"))

    # both-drift: both changed since baseline
    write_pair(root, "tools/d.py", "toolkit/tools/d.py", b"hq new\n", b"kit new\n")
    entries.append(manifest_entry("tools/d.py", "toolkit/tools/d.py", b"hq old\n", b"kit old\n"))

    write_manifest(root, entries)

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0
    out = proc.stdout
    assert "4 pair(s) in manifest" in out
    assert "CLEAN (1)" in out
    assert "tools/a.py" in out.split("CLEAN (1)")[1].split("HQ-DRIFT")[0]
    assert "HQ-DRIFT" in out and "(1)" in out.split("HQ-DRIFT")[1].split("\n")[0]
    assert "tools/b.py" in out.split("HQ-DRIFT")[1].split("KIT-DRIFT")[0]
    assert "tools/c.py" in out.split("KIT-DRIFT")[1].split("BOTH-DRIFT")[0]
    assert "tools/d.py" in out.split("BOTH-DRIFT")[1].split("ERRORS")[0]
    assert "ERRORS (0)" in out


# ---------------------------------------------------------------------------
# 2. --sync updates exactly one pair
# ---------------------------------------------------------------------------

def test_sync_updates_exactly_one_pair(tmp_path):
    root = tmp_path
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n")
    write_pair(root, "tools/b.py", "toolkit/tools/b.py", b"hq new\n", b"kit old\n")
    entries = [
        manifest_entry("tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n"),
        manifest_entry("tools/b.py", "toolkit/tools/b.py", b"hq old\n", b"kit old\n"),
    ]
    manifest_path = write_manifest(root, entries)
    before = json.loads(manifest_path.read_text())

    proc = run_cli(["--sync", "tools/b.py"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0

    after = json.loads(manifest_path.read_text())
    a_before = next(e for e in before if e["hq"] == "tools/a.py")
    a_after = next(e for e in after if e["hq"] == "tools/a.py")
    assert a_before == a_after  # untouched

    b_after = next(e for e in after if e["hq"] == "tools/b.py")
    assert b_after["synced_hq_sha256"] == sha256_bytes(b"hq new\n")
    assert b_after["synced_kit_sha256"] == sha256_bytes(b"kit old\n")
    assert b_after["synced_at"] != "2026-07-01T00:00:00"

    # confirm --check now reports both pairs clean
    proc2 = run_cli(["--check"], cwd=root)
    assert proc2.returncode == 0
    assert "CLEAN (2)" in proc2.stdout


def test_sync_no_match_is_explicit_error(tmp_path):
    root = tmp_path
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", b"x\n", b"x\n")
    write_manifest(root, [manifest_entry("tools/a.py", "toolkit/tools/a.py", b"x\n", b"x\n")])

    proc = run_cli(["--sync", "tools/nope.py"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "ERROR" in proc.stdout


def test_sync_ambiguous_match_is_explicit_error(tmp_path):
    # Same hq mapped to two different kit targets (not a manifest-level
    # duplicate since (hq, kit) differ) -- --sync must refuse, not guess.
    root = tmp_path
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", b"x\n", b"x\n")
    write_pair(root, "tools/a.py", "toolkit/tools/a2.py", b"x\n", b"x\n")
    entries = [
        manifest_entry("tools/a.py", "toolkit/tools/a.py", b"x\n", b"x\n"),
        manifest_entry("tools/a.py", "toolkit/tools/a2.py", b"x\n", b"x\n"),
    ]
    write_manifest(root, entries)

    proc = run_cli(["--sync", "tools/a.py"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "ambiguous" in proc.stdout.lower()


# ---------------------------------------------------------------------------
# 2b. --init refuses without --force, overwrites with --force
# ---------------------------------------------------------------------------

def _build_init_fixture(root: Path) -> None:
    """Mirror the real repo's shape closely enough for discover_pairs()."""
    write_pair(root, "tools/shared.py", "toolkit/tools/shared.py", b"shared hq\n", b"shared kit\n")
    (root / "tools" / "hq_only.py").parent.mkdir(parents=True, exist_ok=True)
    (root / "tools" / "hq_only.py").write_text("hq only\n")
    (root / "toolkit" / "tools").mkdir(parents=True, exist_ok=True)
    (root / "toolkit" / "tools" / "kit_only.py").write_text("kit only\n")

    write_pair(root, "gateway/shadow_eval.py", "toolkit/gateway/shadow_eval.py", b"se hq\n", b"se kit\n")

    write_pair(root, "PROCESS/SESSION_PROTOCOL.md", "toolkit/PROCESS/SESSION_PROTOCOL.md", b"proc hq\n", b"proc kit\n")

    write_pair(root, "CLAUDE.md", "toolkit/CLAUDE.md", b"claude hq\n", b"claude kit\n")


def test_init_generates_manifest_matching_live_layout(tmp_path):
    root = tmp_path
    _build_init_fixture(root)

    proc = run_cli(["--init"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0

    manifest_path = root / "tools" / "parity_manifest.json"
    data = json.loads(manifest_path.read_text())
    hqs = {e["hq"] for e in data}
    assert hqs == {
        "tools/shared.py",
        "gateway/shadow_eval.py",
        "PROCESS/SESSION_PROTOCOL.md",
        "CLAUDE.md",
    }
    # hq_only.py / kit_only.py must NOT appear (only one side exists)
    assert "tools/hq_only.py" not in hqs
    shared_entry = next(e for e in data if e["hq"] == "tools/shared.py")
    assert shared_entry["synced_hq_sha256"] == sha256_bytes(b"shared hq\n")
    assert shared_entry["synced_kit_sha256"] == sha256_bytes(b"shared kit\n")


def test_init_refuses_to_overwrite_without_force(tmp_path):
    root = tmp_path
    _build_init_fixture(root)
    manifest_path = root / "tools" / "parity_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("[]")

    proc = run_cli(["--init"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "ERROR" in proc.stdout
    assert manifest_path.read_text() == "[]"  # unchanged


def test_init_force_overwrites(tmp_path):
    root = tmp_path
    _build_init_fixture(root)
    manifest_path = root / "tools" / "parity_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("[]")

    proc = run_cli(["--init", "--force"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0
    data = json.loads(manifest_path.read_text())
    assert len(data) == 4


# ---------------------------------------------------------------------------
# 3. Adversarial battery
# ---------------------------------------------------------------------------

def test_pair_file_deleted_is_explicit_error_others_still_reported(tmp_path):
    root = tmp_path
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n")
    write_pair(root, "tools/b.py", "toolkit/tools/b.py", b"same\n", b"same\n")
    entries = [
        manifest_entry("tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n"),
        manifest_entry("tools/b.py", "toolkit/tools/b.py", b"same\n", b"same\n"),
    ]
    write_manifest(root, entries)

    (root / "toolkit" / "tools" / "b.py").unlink()

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "CLEAN (1)" in proc.stdout
    assert "ERRORS (1)" in proc.stdout
    assert "toolkit/tools/b.py" in proc.stdout
    assert "MISSING FILE" in proc.stdout


def test_manifest_broken_json_is_explicit_error(tmp_path):
    root = tmp_path
    manifest_path = root / "tools" / "parity_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("{not valid json,,,")

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "ERROR" in proc.stdout


def test_manifest_missing_file_entirely_is_explicit_error(tmp_path):
    root = tmp_path
    (root / "tools").mkdir(parents=True, exist_ok=True)
    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "ERROR" in proc.stdout
    assert "not found" in proc.stdout


def test_manifest_duplicate_pair_is_explicit_error(tmp_path):
    root = tmp_path
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n")
    entries = [
        manifest_entry("tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n"),
        manifest_entry("tools/a.py", "toolkit/tools/a.py", b"same\n", b"same\n"),
    ]
    write_manifest(root, entries)

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 1
    assert "ERROR" in proc.stdout
    assert "duplicate" in proc.stdout.lower()


# ---------------------------------------------------------------------------
# t-309 addendum (task 5): sha256_of() CRLF/LF normalization -- Lead finding
# that raw-byte hashing produced mass false KIT-DRIFT/BOTH-DRIFT on this
# Windows HQ (core.autocrlf=true) against a Linux-session baseline, while
# `git diff` (line-ending-aware) showed no real change. See parity_check.py
# module docstring, "HASHING IS CRLF/LF-NORMALIZED", for the full basis.
# ---------------------------------------------------------------------------


def test_sha256_of_crlf_and_lf_same_content_same_hash(tmp_path):
    # Boundary (a): a file checked out with CRLF and the SAME file checked
    # out with LF must hash IDENTICALLY -- the core invariant this fix adds.
    lf_path = tmp_path / "lf.py"
    crlf_path = tmp_path / "crlf.py"
    lf_path.write_bytes(b"line1\nline2\nline3\n")
    crlf_path.write_bytes(b"line1\r\nline2\r\nline3\r\n")
    assert parity_check.sha256_of(lf_path) == parity_check.sha256_of(crlf_path)


def test_crlf_vs_lf_checkout_no_longer_registers_as_drift(tmp_path):
    # e2e sibling of the unit test above, through --check: a pair whose
    # baseline was recorded against LF content, but whose CURRENT on-disk
    # bytes are CRLF (a re-checkout under different line-ending settings,
    # same text) -- must classify CLEAN, not KIT-DRIFT (this is the exact
    # false-positive class the Lead addendum reported: git diff empty,
    # parity_check drifted).
    root = tmp_path
    lf = b"line1\nline2\n"
    crlf = b"line1\r\nline2\r\n"
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", lf, lf)
    write_manifest(root, [manifest_entry("tools/a.py", "toolkit/tools/a.py", lf, lf)])

    # kit side re-checked out with CRLF line endings, same textual content
    (root / "toolkit" / "tools" / "a.py").write_bytes(crlf)

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0
    assert "CLEAN (1)" in proc.stdout
    assert "KIT-DRIFT -- SUSPICIOUS, staging touched out of band (0)" in proc.stdout
    assert "BOTH-DRIFT -- port likely happened, manifest baseline stale (0)" in proc.stdout


def test_crlf_checkout_with_real_content_difference_still_detected(tmp_path):
    # Boundary (b): normalization must NOT swallow a genuine content
    # difference just because line endings also differ -- a real edit
    # (different text, not just \r\n vs \n) under CRLF checkout must still
    # register as drift.
    root = tmp_path
    lf = b"line1\nline2\n"
    write_pair(root, "tools/a.py", "toolkit/tools/a.py", lf, lf)
    write_manifest(root, [manifest_entry("tools/a.py", "toolkit/tools/a.py", lf, lf)])

    # kit side: CRLF checkout AND a real edit (line2 -> line2-changed)
    (root / "toolkit" / "tools" / "a.py").write_bytes(b"line1\r\nline2-changed\r\n")

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0
    assert "KIT-DRIFT" in proc.stdout
    kit_drift_section = proc.stdout.split("KIT-DRIFT")[1].split("BOTH-DRIFT")[0]
    assert "tools/a.py" in kit_drift_section


def test_sha256_of_lone_cr_without_lf_untouched_deterministic(tmp_path):
    # Boundary (c): binary safety -- a lone b"\r" NOT followed by b"\n"
    # (old-Mac-style ending, or just a \r byte inside otherwise-binary
    # data) must NOT be touched by the CRLF-only substitution; the hash
    # must be deterministic (repeatable) and must differ from the same
    # bytes with \r\n actually present (proves the substitution really is
    # literal-\r\n-only, not "any \r").
    path_bare_cr = tmp_path / "bare_cr.bin"
    path_bare_cr.write_bytes(b"line1\rline2\r")
    first = parity_check.sha256_of(path_bare_cr)
    second = parity_check.sha256_of(path_bare_cr)
    assert first == second  # deterministic, repeat read gives same digest
    # sanity: bare \r bytes are NOT collapsed the way \r\n pairs are --
    # hashing the literal bytes directly (no replace at all) must agree.
    assert first == hashlib.sha256(b"line1\rline2\r").hexdigest()


def test_sha256_of_no_newlines_at_all_deterministic(tmp_path):
    # Boundary (c), sibling: a file with no line-ending bytes whatsoever
    # (single line, no trailing newline) -- substitution is a no-op,
    # hash equals the plain raw-bytes digest.
    path = tmp_path / "no_newline.py"
    path.write_bytes(b"just one line, no newline at all")
    assert parity_check.sha256_of(path) == hashlib.sha256(
        b"just one line, no newline at all"
    ).hexdigest()


def test_unicode_filenames_handled_cleanly(tmp_path):
    root = tmp_path
    hq_rel = "tools/документ_测试.py"
    kit_rel = "toolkit/tools/документ_测试.py"
    write_pair(root, hq_rel, kit_rel, b"content\n", b"content\n")
    write_manifest(root, [manifest_entry(hq_rel, kit_rel, b"content\n", b"content\n")])

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0
    assert "CLEAN (1)" in proc.stdout
    assert hq_rel in proc.stdout


def test_empty_file_handled_cleanly(tmp_path):
    root = tmp_path
    write_pair(root, "tools/empty.py", "toolkit/tools/empty.py", b"", b"")
    write_manifest(root, [manifest_entry("tools/empty.py", "toolkit/tools/empty.py", b"", b"")])

    proc = run_cli(["--check"], cwd=root)
    assert_no_traceback(proc)
    assert proc.returncode == 0
    assert "CLEAN (1)" in proc.stdout


# ---------------------------------------------------------------------------
# discover_pairs() direct unit test (order + both-sides-only filter)
# ---------------------------------------------------------------------------

def test_discover_pairs_order_and_filter(tmp_path):
    root = tmp_path
    _build_init_fixture(root)
    pairs = parity_check.discover_pairs(root)
    hqs = [p["hq"] for p in pairs]
    assert hqs == [
        "tools/shared.py",
        "gateway/shadow_eval.py",
        "PROCESS/SESSION_PROTOCOL.md",
        "CLAUDE.md",
    ]
