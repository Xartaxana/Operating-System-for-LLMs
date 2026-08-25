"""Battery for owns_gate.py's same-session retry exclusion (see its
module docstring, "Same-session retry exclusion (SAME_SESSION_RETRY)"):
a resubmission after a `rejected` (this kit's rule 6 PRESCRIBES exactly
that -- same task_id, same or WIDER owns) collides with ITSELF by
construction, because logs/owns_registry.jsonl records the START of a
writing dispatch and never learns of its COMPLETION. Fix -- K1: a live
record is excluded from the WARN check ENTIRELY (not path-by-path) when
it (a) belongs to the same session AND (b) its owns set is a subset (or
equal) of the new dispatch's owns set.

K-class resolver (MODULE_UNDER_TEST): unlike the staff deployment this
port is drawn from, this kit's same-session retry exclusion lives
DIRECTLY in the single owns_gate.py file -- there is no separate
sibling module to switch between (region-awareness and retry
exclusion were merged into the live gate from the start of this port).
The resolver below still follows the K-class
convention this batch's other *_md.py/​*_retry.py files use (no
silent fallback to a differently-named module when one is explicitly
requested): MODULE_UNDER_TEST unset/empty -> the live tools/owns_gate.py;
any OTHER non-empty value is read as an explicit request for a
DIFFERENTLY NAMED sibling file (MODULE_UNDER_TEST=<stem> ->
tools/<stem>.py) -- if that named file does not exist, a LOUD
pytest.fail naming the requested path, never a silent substitution of
the live file.

Run: python -m pytest toolkit/tools/test_owns_gate_retry.py -q
"""

import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip()


def _resolve_script_path() -> Path:
    live = TOOLS_DIR / "owns_gate.py"
    if MODULE_UNDER_TEST == "":
        return live
    requested = TOOLS_DIR / f"{MODULE_UNDER_TEST}.py"
    if not requested.exists():
        pytest.fail(
            f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested "
            f"{requested} but it does not exist -- no silent live "
            f"fallback (K-class convention, no silent substitution)"
        )
    return requested


SCRIPT = _resolve_script_path()


def _load_module():
    alias = "owns_gate_retry_target"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module()

_NOW = datetime(2026, 8, 25, 12, 0, 0)


def _write_registry_line(path: Path, ts, session_key, cwd: str, description: str, owns) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": ts, "session_key": session_key, "cwd": cwd, "description": description, "owns": owns}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _writing_payload(owns_text: str, session_id="s-1", cwd="D:\\repo", description="sonnet: write") -> dict:
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        f"owns: {owns_text}.\n"
        "Edit the files."
    )
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": description},
        "session_id": session_id,
        "cwd": cwd,
    }


def _ts(now: datetime) -> str:
    return now.strftime(m._TS_FORMAT)


# ---------------------------------------------------------------------
# K1 -- same-session retry, owns subset/equal -- warn EXCLUDED.
# ---------------------------------------------------------------------


def test_same_session_superset_owns_excluded_real_case(tmp_path):
    # attempt 1 owns {a.py, b.py, c.py}; attempt 2 (rejected retry, same
    # coordinator session) declares the SAME three plus a fourth d.py.
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-lead-1", "D:\\repo", "sonnet: attempt 1 (rejected)",
        [
            "D:\\repo\\tools\\a.py",
            "D:\\repo\\tools\\b.py",
            "D:\\repo\\tools\\c.py",
        ],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py, D:\\repo\\tools\\c.py, D:\\repo\\tools\\d.py",
        session_id="s-lead-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None, "a same-session retry (superset owns) is NOT a conflict (K1)"


def test_same_session_equal_owns_excluded_no_expansion(tmp_path):
    # A retry with NO scope expansion -- the sets are EQUAL (edge case:
    # "equal is a subset too, excluded").
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: attempt 1 (rejected)",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None


def test_same_session_subset_owns_different_case_and_separator(tmp_path):
    # Edge case: case/separator differences -- nesting by
    # normalize_path, not by raw string equality.
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: attempt 1 (rejected)",
        ["D:/REPO/TOOLS/a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# K2 (the battery's MAIN test) -- a partial overlap, NEITHER set nested
# in the other -- remains a conflict. Proves the fix does not switch
# the whole layer off.
# ---------------------------------------------------------------------


def test_partial_overlap_same_session_still_warns_not_full_subset(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: prior write",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    # The new dispatch owns {b.py, c.py} -- overlaps via b.py, but
    # NEITHER set is nested in the other ({a,b} is not a subset of
    # {b,c} or vice versa) -- a REAL conflict, the warn must stay.
    payload = _writing_payload(
        "D:\\repo\\tools\\b.py, D:\\repo\\tools\\c.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


# ---------------------------------------------------------------------
# Residual gaps D1/D2 of the K1 signal (documented, left open on
# purpose -- see the module docstring). Both tests PIN the current
# (falsely warning) behavior, not a regression check of the fix.
# ---------------------------------------------------------------------


def test_d1_narrowing_retry_residual_gap_still_warns_documented_limitation(tmp_path):
    # A legal case: attempt 2 SHRINKS owns after `rejected` (owns
    # {a.py} -- a STRICT SUBSET of attempt 1's {a.py, b.py}), same
    # session. The RECORD's owns ({a,b}) is NOT a subset of the NEW
    # dispatch's owns ({a}) -- K1 does not fire, the warn stays falsely.
    # A named, documented residual gap -- behavior is NOT changed on
    # purpose (widening K1 would make it indistinguishable from K2).
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: attempt 1 (rejected, wider)",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "residual gap D1: a narrowing retry falsely warns -- expected, documented"
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


def test_d2_cross_session_retry_residual_gap_still_warns_documented_limitation(tmp_path):
    # A legal case: the coordinator session died between attempt 1 and
    # attempt 2, a NEW session retries the same (or a wider) owns set --
    # session_key differs even though it is the same logical task. K3
    # ("a different session always warns") fires literally -- the warn
    # stays falsely. Partially damped by the liveness window (a record
    # older than WINDOW_SECONDS is no longer live), but WITHIN the
    # window (as here -- the same ts) the gap is live.
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-lead-OLD-SESSION", "D:\\repo", "sonnet: attempt 1 (rejected, session died)",
        ["D:\\repo\\tools\\a.py", "D:\\repo\\tools\\b.py"],
    )
    # A new coordinator session, the SAME or a WIDER owns declaration
    # (i.e. K1 would have fired had the session_key been the same).
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py, D:\\repo\\tools\\c.py",
        session_id="s-lead-NEW-SESSION", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "residual gap D2: a cross-session retry falsely warns -- expected, documented"
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


# ---------------------------------------------------------------------
# K3 -- a foreign session ALWAYS warns, regardless of nesting.
# ---------------------------------------------------------------------


def test_different_session_subset_owns_still_warns(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-OTHER", "D:\\repo", "sonnet: a different session",
        ["D:\\repo\\tools\\a.py"],
    )
    # A new dispatch that's a superset {a.py, b.py}, but a DIFFERENT
    # session -- not a retry of THIS session, the warn must stay.
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx
    assert "a different session" in ctx


# ---------------------------------------------------------------------
# Edge: a record's session_key missing/None -- fail-closed (warn),
# never treated as "own", even when the new dispatch's own session_key
# also happens to be missing/None.
# ---------------------------------------------------------------------


def test_record_missing_session_key_fail_closed_still_warns(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    # session_key field is ABSENT from the record entirely.
    entry = {
        "ts": _ts(_NOW), "cwd": "D:\\repo", "description": "sonnet: no session_key",
        "owns": ["D:\\repo\\tools\\a.py"],
    }
    registry.parent.mkdir(parents=True, exist_ok=True)
    with registry.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "record session_key missing -- fail-closed, the warn must stay"


def test_record_session_key_none_fail_closed_still_warns(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), None, "D:\\repo", "sonnet: session_key explicitly None",
        ["D:\\repo\\tools\\a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\b.py", session_id="s-1", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None, "record session_key explicitly None -- a foreign session, the warn must stay"


def test_helper_is_own_session_both_none_is_still_false_fail_closed():
    # A direct check at the helper level (the module docstring requires
    # exactly this flank: "even when the new dispatch's own session_key
    # also happens to be missing/None").
    rec = {"session_key": None}
    assert m._is_own_session(rec, None) is False
    rec_missing = {}
    assert m._is_own_session(rec_missing, None) is False


# ---------------------------------------------------------------------
# Edge: a record with an EMPTY owns ([] or missing) -- not a subset of
# anything, and structurally never produces an overlap match -- silence.
# ---------------------------------------------------------------------


def test_record_with_empty_owns_list_never_overlaps_stays_silent(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: empty owns", [],
    )
    payload = _writing_payload("D:\\repo\\tools\\a.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None


def test_helper_is_self_retry_record_empty_owns_returns_false_explicit():
    # A direct check of "empty owns is not a subset of anything" at the
    # helper level (not just the observable effect through decide()).
    rec = {"session_key": "s-1", "owns": []}
    new_owns = {"d:/repo/tools/a.py"}
    assert m._is_self_retry_record(rec, "s-1", new_owns) is False
    rec_missing = {"session_key": "s-1"}
    assert m._is_self_retry_record(rec_missing, "s-1", new_owns) is False


# ---------------------------------------------------------------------
# The "OWNS OVERLAP (warn): " literal prefix is preserved byte-for-byte
# (this kit's tools/warn_layers.json, if it declares this layer, would
# rely on it -- see the module docstring, K5-equivalent note).
# ---------------------------------------------------------------------


def test_owns_overlap_literal_prefix_preserved_byte_for_byte(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    _write_registry_line(
        registry, _ts(_NOW), "s-1", "D:\\repo", "sonnet: prior write",
        ["D:\\repo\\tools\\a.py"],
    )
    payload = _writing_payload(
        "D:\\repo\\tools\\a.py, D:\\repo\\tools\\c.py", session_id="s-OTHER-3", cwd="D:\\repo",
    )
    exit_code, output = m.decide(payload, registry_path=registry, now=_NOW)
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert ctx.startswith("OWNS OVERLAP (warn): ")


# ---------------------------------------------------------------------
# Sanity: the module resolved by the K-class resolver above loads
# independently and carries the expected surface.
# ---------------------------------------------------------------------


def test_target_module_loads_and_carries_retry_exclusion_surface():
    assert hasattr(m, "decide")
    assert hasattr(m, "_find_overlaps")
    assert hasattr(m, "_is_self_retry_record")
    assert hasattr(m, "_is_own_session")
