"""tools/test_claim_control_gate_md.py -- K-class resolver battery,
synced from HQ's tools/test_claim_control_gate_md.py (its K1 fix: an
explicitly requested sibling that does not exist fails LOUDLY --
pytest.fail naming the requested path -- instead of a silent fallback
to the live file).

SCOPE UPDATE (supersedes the SCOPE ADAPTATION note this docstring carried
under D5 -- same class as tools/test_negative_lint_md.py's own
docstring update): this kit's tools/claim_control_gate.py is NOW
region-aware (imports tools/md_regions.py, recognizes fenced/
blockquote/inline_code spans for the marker/token positions it scans,
B2 policy) -- ported in the same node as this test update. D5's
earlier reasoning ("md_regions integration is out of scope for this
port") no longer holds; the region test groups it explicitly did NOT
port are ADDED below.

NEGATIVE CONTROL, WITHOUT the sibling/live split: same finding as
tools/test_negative_lint_md.py's own docstring -- HQ's
MODULE_UNDER_TEST=live claim ("region-specific asserts... must turn
red on the live (non-region) target") is STALE on HQ's own tree too
(HQ folded region logic directly into the live file; both targets
resolve to the same region-aware module there). This port does not
inherit that claim: the region tests below use monkeypatch on
`m.scan` (the SAME mechanism the ported I-0 tests already exercise) as
the honest region-on/region-off pair, exactly as
test_negative_lint_md.py now does.

  - No tools/claim_control_gate_md.py sibling exists in this template
    (nor in HQ's own tree -- same historical-artifact-name situation
    as negative_lint_md.py). The K1 resolver below stays UNCHANGED --
    infrastructure, forward-compatible with a future region-aware
    sibling landing here.
  - HQ's region-specific test groups (И-0 md_regions-failure fallback,
    И-1/B2 lazy-scan, fenced/blockquote/inline_code policy, and the
    "discrimination" pair) ARE now ported below, adapted to the
    monkeypatch-based negative control described above (HQ's own
    MODULE_UNDER_TEST=live split is not reproduced -- see above for
    why). The positional-invariant regex-pin against a separately
    loaded _LIVE reference is NOT ported: `m` already IS the live
    module here (no sibling exists), so a self-comparison would be
    vacuous -- listed here with reason, not silently dropped.
  - The target-agnostic groups (base decide() regression -- path
    scoping, non-Edit/Write silence, malformed input -- and the
    subprocess adversarial battery), already present since D5, are
    UNCHANGED.

Run:  python -m pytest tools/test_claim_control_gate_md.py -q
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # K1 form (synced verbatim from HQ, docs/tasks/2026-08-25_
    # queue8-mechbatch-spec.md): default (MODULE_UNDER_TEST empty) --
    # sibling, IF it exists, else the live file, SILENTLY (no sibling
    # exists in this template today -- resolves to live). An explicitly
    # REQUESTED sibling (MODULE_UNDER_TEST set and not "live") that does
    # not exist -> LOUD pytest.fail, not a silent live substitution.
    live = TOOLS_DIR / "claim_control_gate.py"
    if MODULE_UNDER_TEST == "live":
        return live
    sibling = TOOLS_DIR / "claim_control_gate_md.py"
    if MODULE_UNDER_TEST == "":
        return sibling if sibling.exists() else live
    if not sibling.exists():
        pytest.fail(
            f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested sibling "
            f"{sibling} but it does not exist -- no silent live fallback (K1)"
        )
    return sibling


SCRIPT = _resolve_script_path()


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load(SCRIPT, f"claim_control_gate_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}")


def _run_hook(payload, ledger_dir=None, raw_input=None):
    env = os.environ.copy()
    if ledger_dir is not None:
        env["SEARCH_CONTROL_GATE_LEDGER_DIR"] = str(ledger_dir)
    else:
        env.pop("SEARCH_CONTROL_GATE_LEDGER_DIR", None)
    if raw_input is not None:
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=raw_input,
            capture_output=True,
            env=env,
        )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _write_payload(path, text, session_id="sess-1"):
    return {
        "session_id": session_id,
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": text},
    }


def _isolated_empty_ledger_dir():
    """A fresh, empty ledger directory outside the repo -- for
    in-process decide() tests (I-0/I-1 monkeypatch is not visible to a
    child process, see test_i0_scan_raises_falls_back_to_today_behavior),
    so a real logs/.search-ledger of this repo is never picked up."""
    return Path(tempfile.mkdtemp(prefix="claim_control_gate_md_test_"))


# ---------------------------------------------------------------------
# I-0: any md_regions failure -> this guard behaves EXACTLY as before
# region-awareness (see the module docstring, "SCOPE UPDATE", for why
# monkeypatch on m.scan is this port's negative-control mechanism, not
# HQ's stale MODULE_UNDER_TEST=live split).
# ---------------------------------------------------------------------


def test_i0_scan_raises_falls_back_to_today_behavior(monkeypatch, tmp_path):
    """Substitution IN a subprocess (_run_hook) is not visible to the
    child process's own module (its own fresh import) -- so decide()
    is called DIRECTLY IN the test process here, on the same object `m`
    monkeypatch is patching (the same indirection
    test_negative_lint_md.py already uses for find_violations())."""

    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    # byte-for-byte like a non-region linter: the quoted token IS counted anyway
    assert output is not None
    assert "RELATED_WORK" in output["hookSpecificOutput"]["additionalContext"]


def test_i0_scan_degraded_falls_back_to_today_behavior(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is not None
    assert "RELATED_WORK" in output["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------
# I-1 / B2: the scanner is called only after path-scoping and a marker
# hit (laziness)
# ---------------------------------------------------------------------


def test_i1_scan_not_called_when_no_marker_hit(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload("docs/notes.md", "Everything found and verified, all present.")
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is None
    assert calls["n"] == 0


def test_i1_scan_called_when_marker_hit_present(monkeypatch):
    """Positive control of the same form (command hygiene point 6):
    the same counting substitution, but WITH a real negative marker --
    scan() must be called at least once."""
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload("docs/notes.md", "The file docs/RELATED_WORK.md does not exist.")
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert calls["n"] >= 1


# ---------------------------------------------------------------------
# B2 policy: fenced/blockquote do not create a window and do not count
# tokens; inline_code counts
# ---------------------------------------------------------------------


def test_b2_marker_inside_blockquote_produces_no_window(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md does not exist anywhere in this repo.\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_b2_marker_inside_fenced_block_produces_no_window(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "```\ndocs/RELATED_WORK.md does not exist anywhere in this repo.\n```\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_b2_marker_inside_inline_code_still_counts(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "The claim `docs/RELATED_WORK.md does not exist` was made without checking.\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_b2_marker_in_prose_satisfied_by_ledger_search_still_silences(tmp_path):
    """Regression: the policy does not touch the existing ledger
    correlation path -- a prose marker + token SATISFIED by a positive
    search in the session stays silent."""
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["RELATED_WORK"])
    payload = _write_payload("docs/notes.md", "docs/RELATED_WORK.md does not exist.")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_b2_token_inside_quote_not_counted_even_when_marker_in_prose(tmp_path):
    """The marker itself is in prose (passes the region gate at the
    window level), but the ONLY claim token sits in a quote right
    before it (the "a line break does not split a sentence" class --
    none of the five existing regexes treats a quote's start as a
    boundary, the window normally captures both lines as one
    "sentence") -- the region filter must exclude the TOKEN specifically
    (not the whole window) -- "does not count tokens" is separate from
    "does not create a window"."""
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def _write_ledger(ledger_dir, session, terms):
    ledger_dir = Path(ledger_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{session}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for term in terms:
            fh.write(
                json.dumps(
                    {"ts": "2026-08-19T00:00:00", "tool": "Grep", "term": term, "empty": False},
                    ensure_ascii=False,
                )
                + "\n"
            )


# ---------------------------------------------------------------------
# DISCRIMINATION NEGATIVE CONTROL (mandatory): a quoted marker/token
# must not produce a window/count -- proven as a green/red PAIR against
# the SAME text (region working / region broken via monkeypatch, see
# test_i0_* above for the red half).
# ---------------------------------------------------------------------


def test_discrimination_marker_inside_quote_produces_no_window(tmp_path):
    """GREEN half (region filter active, the default): a marker inside
    a quote produces no window at all -- silent stdout. The RED half of
    this pair is test_i0_scan_raises_falls_back_to_today_behavior above
    -- the SAME text-class, scan() broken via monkeypatch -> the live
    algorithm treats it as an ordinary marker in an ordinary sentence
    and flags the unverified token -- both halves verified, verbatim in
    the builder report per command hygiene point 6."""
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md does not exist anywhere in this repo.\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_discrimination_token_inside_quote_not_counted(tmp_path):
    """Same class at the TOKEN level, not the marker -- see
    test_b2_token_inside_quote_not_counted_even_when_marker_in_prose's
    docstring. The red counterpart is the same
    test_i0_scan_raises_falls_back_to_today_behavior pairing above."""
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# Base behavior regression (target-agnostic: same for live and any
# future region-aware sibling)
# ---------------------------------------------------------------------


def test_f5_regression_empty_ledger_warns_related_work_smoke(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("docs/notes.md", "docs/RELATED_WORK.md does not exist.")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_vault_path_out_of_scope_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("vault/notes.md", "docs/RELATED_WORK.md does not exist.")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_non_edit_write_tool_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_input": {"command": "echo docs/RELATED_WORK.md does not exist"},
    }
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_exit_zero_on_malformed_json(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"{not valid json")
    assert result.returncode == 0


def test_exit_zero_on_non_dict_payload(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"[1, 2, 3]")
    assert result.returncode == 0


def test_adversarial_invalid_utf8_bytes_no_crash(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"\xff\xfe\x00\x01not json either")
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr
