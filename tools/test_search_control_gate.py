"""Tests for tools/search_control_gate.py -- the ported t-021 gate
(source: sibling Dog deployment's tools/search_control_gate.py, synk
2026-07-29, see the module's own docstring "ORIGIN").

See the target module's docstring ("t-017 FIX") for the two problems
being fixed at the source, both preserved here:
 1. The schema-sample probe was unreachable in practice: it only wrote
    when BOTH tool_name and result were unfindable, but known Claude
    Code payloads carry tool_name, so a result living under an unknown
    key made the hook pass silently forever with no evidence ever
    landing.
 2. A dict-shaped tool_response used to serialize to non-empty JSON
    text before any emptiness check ran, so a genuinely empty
    structured result (e.g. {"stdout": ""}) was never recognized as
    empty.

Every test drives the real script as a subprocess (same style as
tools/test_hygiene_gate.py's subprocess-level tests) with
SEARCH_CONTROL_GATE_SAMPLE_PATH pointed at a pytest tmp_path, so no
test ever writes into the real logs/ directory. The ledger dir is
NEVER left to default to the real logs/.search-ledger/ either (see
`_run_hook` and the D2-style regression test near the bottom).

THIS DEPLOY'S ADAPTATION (spec part A, к2): PowerShell is handled
identically to Bash -- see "PowerShell" section below for the
select-string ledger test and the non-search-PowerShell-command
regression.

MODULE UNDER TEST: imported as `scg` via a try/except alias --
`search_control_gate` (the neighbor file this delivery lands as,
per the enforcement-file-review rule) if present, else
`search_control_gate` (the live module name this content is meant to
occupy once the coordinator moves it at acceptance). SCRIPT (used by
the subprocess-level tests below) is resolved the same way, so the
suite still works after promotion without a ModuleNotFoundError
aborting collection.

Run from the repo root: python -m pytest tools/test_search_control_gate.py -q
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import search_control_gate as scg
except ImportError:
    import search_control_gate as scg

_SCRIPT_NEXT = Path(__file__).resolve().parent / "search_control_gate.py"
_SCRIPT_LIVE = Path(__file__).resolve().parent / "search_control_gate.py"
SCRIPT = _SCRIPT_NEXT if _SCRIPT_NEXT.exists() else _SCRIPT_LIVE

_UNSET = object()  # sentinel: "leave SEARCH_CONTROL_GATE_LEDGER_DIR unset", узел C


def _run_hook(payload, sample_path=None, ledger_dir=None, raw_input=None):
    env = os.environ.copy()
    if sample_path is not None:
        env["SEARCH_CONTROL_GATE_SAMPLE_PATH"] = str(sample_path)
    else:
        env.pop("SEARCH_CONTROL_GATE_SAMPLE_PATH", None)
    # D2-style guard: NEVER leave the ledger dir unset -- that falls through
    # to the script's real logs/.search-ledger default. A fresh temp dir is
    # used when the caller does not need to inspect the ledger afterward.
    if ledger_dir is None:
        ledger_dir = tempfile.mkdtemp(prefix="scg-ledger-")
    env["SEARCH_CONTROL_GATE_LEDGER_DIR"] = str(ledger_dir)
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


# ---------------------------------------------------------------------
# (i)/(ii) plain-string result -- unchanged behavior, regression
# ---------------------------------------------------------------------


def test_i_plain_string_empty_result_on_grep_warns(tmp_path):
    payload = {"tool_name": "Grep", "tool_input": {"pattern": "foo"}, "tool_response": ""}
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert scg.MSG in data["hookSpecificOutput"]["additionalContext"]
    assert data["hookSpecificOutput"]["hookEventName"] == "PostToolUse"


def test_ii_plain_string_nonempty_result_silent(tmp_path):
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": "file.md:1:foo match",
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# (iii) dict Bash response, empty stdout, on a grep command -- warns
# (t-017 fix point 2: structural judgement before serialization)
# ---------------------------------------------------------------------


def test_iii_dict_bash_empty_stdout_on_grep_command_warns(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "grep -r foo ."},
        "tool_response": {"stdout": "", "stderr": "some noise on stderr"},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert scg.MSG in data["hookSpecificOutput"]["additionalContext"]


def test_iii_dict_bash_nonempty_stdout_on_grep_command_silent(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "grep -r foo ."},
        "tool_response": {"stdout": "./file.md:1:foo", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# (iv) dict Grep response, numFiles 0 -- warns
# ---------------------------------------------------------------------


def test_iv_dict_grep_response_num_files_zero_warns(tmp_path):
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "подкосов"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert scg.MSG in data["hookSpecificOutput"]["additionalContext"]


def test_iv_dict_grep_response_with_filenames_silent(tmp_path):
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"numFiles": 2, "filenames": ["a.md", "b.md"]},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# (v) dict with unknown shape on a search tool -- sample written,
# not guessed at either way (no warn, since emptiness is unjudgeable)
# ---------------------------------------------------------------------


def test_v_dict_unknown_shape_on_search_tool_writes_sample(tmp_path):
    sample_path = tmp_path / "sample.json"
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"totally_unrecognized_key": 123},
    }
    result = _run_hook(payload, sample_path=sample_path)
    assert result.returncode == 0
    assert sample_path.exists()
    written = sample_path.read_text(encoding="utf-8")
    assert "totally_unrecognized_key" in written
    assert result.stdout.strip() == ""


def test_v_sample_write_is_once_only(tmp_path):
    sample_path = tmp_path / "sample.json"
    sample_path.write_text("PRE-EXISTING CONTENT", encoding="utf-8")
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"totally_unrecognized_key": 123},
    }
    result = _run_hook(payload, sample_path=sample_path)
    assert result.returncode == 0
    assert sample_path.read_text(encoding="utf-8") == "PRE-EXISTING CONTENT"


def test_d4_missing_result_on_search_tool_writes_sample(tmp_path):
    sample_path = tmp_path / "sample.json"
    payload = {"tool_name": "Grep", "tool_input": {"pattern": "foo"}}
    result = _run_hook(payload, sample_path=sample_path)
    assert result.returncode == 0
    assert sample_path.exists()
    written = sample_path.read_text(encoding="utf-8")
    assert "Grep" in written
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# (vi) non-search Bash, empty stdout -- silent
# ---------------------------------------------------------------------


def test_vi_non_search_bash_empty_stdout_silent(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "git status --short"},
        "tool_response": {"stdout": "", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# F4(2) (критик t-339, живая репродукция): _looks_like_search must
# classify by the COMMAND STRING, not the whole serialized tool_input
# (an unrelated `description` field must not influence it).
# ---------------------------------------------------------------------


def test_f4_description_field_does_not_make_non_search_command_look_like_search(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-f4",
        "tool_name": "Bash",
        "tool_input": {
            "command": "git status --short",
            "description": "Find modified files",
        },
        "tool_response": {"stdout": "", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    ledger_file = ledger_dir / "sess-f4.jsonl"
    assert not ledger_file.exists()


def test_f4_command_text_classification_unit():
    assert scg._command_text_for_classification(
        "Bash", {"command": "git status --short", "description": "Find modified files"}
    ) == "git status --short"
    assert scg._looks_like_search(
        "Bash",
        scg._command_text_for_classification(
            "Bash", {"command": "git status --short", "description": "Find modified files"}
        ),
    ) is False


def test_f4_command_itself_still_classified_as_search_unit():
    assert scg._looks_like_search(
        "Bash",
        scg._command_text_for_classification("Bash", {"command": "grep -rn foo ."}),
    ) is True


# ---------------------------------------------------------------------
# PowerShell (this deploy's adaptation, spec part A, к2): handled
# identically to Bash -- term = whole command verbatim, searchability
# via SEARCH_TOKENS, "select-string" added as PowerShell's own
# grep-equivalent cmdlet.
# ---------------------------------------------------------------------


def test_ps_select_string_search_records_ledger_line(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-ps-1",
        "tool_name": "PowerShell",
        "tool_input": {"command": "Select-String -Pattern RELATED_WORK -Path docs/*.md"},
        "tool_response": {"stdout": "", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    ledger_file = ledger_dir / "sess-ps-1.jsonl"
    assert ledger_file.exists()
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["tool"] == "PowerShell"
    assert lines[0]["term"] == "Select-String -Pattern RELATED_WORK -Path docs/*.md"
    # empty stdout on a search-shaped command -- also warns.
    data = json.loads(result.stdout)
    assert scg.MSG in data["hookSpecificOutput"]["additionalContext"]


def test_ps_non_search_command_not_recorded_and_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-ps-2",
        "tool_name": "PowerShell",
        "tool_input": {"command": "Get-ChildItem -Path docs/"},
        "tool_response": {"stdout": "", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    ledger_file = ledger_dir / "sess-ps-2.jsonl"
    assert not ledger_file.exists()
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# (vii) exit code 0 on every path -- spot-checked above per test; this
# adds a couple of edge/adversarial inputs to the same assertion.
# ---------------------------------------------------------------------


def test_vii_exit_zero_on_malformed_json(tmp_path):
    result = _run_hook(None, sample_path=tmp_path / "sample.json", raw_input=b"{not valid json")
    assert result.returncode == 0
    assert result.stdout.decode("utf-8", errors="replace").strip() == ""


def test_vii_exit_zero_on_empty_stdin(tmp_path):
    result = _run_hook(None, sample_path=tmp_path / "sample.json", raw_input=b"")
    assert result.returncode == 0


# ---------------------------------------------------------------------
# regression: the original schema-unknown case (both tool_name and
# result unfindable) still writes the sample and exits 0
# ---------------------------------------------------------------------


def test_regression_original_schema_unknown_case_writes_sample(tmp_path):
    sample_path = tmp_path / "sample.json"
    payload = {"totally_unknown_shape": True}
    result = _run_hook(payload, sample_path=sample_path)
    assert result.returncode == 0
    assert sample_path.exists()
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# _classify_result unit coverage (pure function, no subprocess needed)
# ---------------------------------------------------------------------


def test_classify_result_missing_is_missing():
    assert scg._classify_result(None) == "missing"


def test_classify_result_dict_stdout_ignores_stderr():
    assert scg._classify_result({"stdout": "", "stderr": "noise"}) == "empty"
    assert scg._classify_result({"stdout": "x", "stderr": ""}) == "nonempty"


def test_classify_result_dict_num_files_or_filenames():
    assert scg._classify_result({"numFiles": 0}) == "empty"
    assert scg._classify_result({"filenames": []}) == "empty"
    assert scg._classify_result({"numFiles": 1, "filenames": ["a.md"]}) == "nonempty"


def test_classify_result_dict_content_field():
    assert scg._classify_result({"content": "  "}) == "empty"
    assert scg._classify_result({"content": "text"}) == "nonempty"


# ---------------------------------------------------------------------
# CONTENT/COUNT-MODE FP FIX (Lead live repro, 2026-07-29): non-empty
# content must win over empty-looking filenames/numFiles.
# ---------------------------------------------------------------------


def test_classify_result_nonempty_content_wins_over_empty_filenames_num_files():
    # Regression for the live FP: content-mode dict with a real match
    # but empty filenames/numFiles (file list not populated outside
    # files_with_matches mode) must classify as "nonempty".
    result = {
        "filenames": [],
        "numFiles": 0,
        "content": 'tools/mechanism_gate.py:3: python scripts/mechanism_gate.py "$1"',
    }
    assert scg._classify_result(result) == "nonempty"


def test_classify_result_count_mode_nonempty_content_wins():
    # count-mode form: "N total occurrences" as content, still empty-
    # looking filenames/numFiles.
    result = {"numFiles": 0, "filenames": [], "content": "6 total occurrences"}
    assert scg._classify_result(result) == "nonempty"


def test_classify_result_empty_filenames_num_files_no_content_still_empty():
    # Prior behavior UNCHANGED: no content key at all, empty filenames/
    # numFiles -- still "empty" (a genuinely empty files_with_matches-
    # mode Grep/Glob result).
    assert scg._classify_result({"filenames": [], "numFiles": 0}) == "empty"


def test_classify_result_empty_string_content_falls_through_to_filenames():
    # content present but EMPTY (whitespace-only) -- must NOT force
    # "nonempty"; falls through to the filenames/numFiles branch as
    # before (still "empty" here since both are empty-looking).
    result = {"filenames": [], "numFiles": 0, "content": "   "}
    assert scg._classify_result(result) == "empty"


def test_classify_result_empty_content_but_nonempty_filenames_is_nonempty():
    # The other direction: content empty/absent but filenames say
    # nonempty -- filenames/numFiles branch still governs (unchanged).
    result = {"filenames": ["a.md"], "numFiles": 1, "content": ""}
    assert scg._classify_result(result) == "nonempty"


def test_content_count_mode_fp_full_pipeline_content_mode_no_warning(tmp_path):
    # Full-pipeline regression of the live FP form (a), content-mode:
    # a real Grep match must NOT warn and must record "empty": false
    # in the ledger.
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-fp-content",
        "tool_name": "Grep",
        "tool_input": {"pattern": "mechanism_gate"},
        "tool_response": {
            "filenames": [],
            "numFiles": 0,
            "content": 'tools/mechanism_gate.py:3: python scripts/mechanism_gate.py "$1"',
        },
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    ledger_file = ledger_dir / "sess-fp-content.jsonl"
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["empty"] is False


def test_content_count_mode_fp_full_pipeline_count_mode_no_warning(tmp_path):
    # Full-pipeline regression of the live FP form (b), count-mode.
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-fp-count",
        "tool_name": "Grep",
        "tool_input": {"pattern": "mechanism_gate"},
        "tool_response": {"numFiles": 0, "filenames": [], "content": "6 total occurrences"},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    ledger_file = ledger_dir / "sess-fp-count.jsonl"
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["empty"] is False


def test_content_count_mode_fp_full_pipeline_genuinely_empty_still_warns(tmp_path):
    # Control (правило 6 command hygiene: negative claim needs a
    # positive-form control): a GENUINELY empty Grep result (no
    # content key at all) must still warn, unaffected by the fix.
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-fp-genuine-empty",
        "tool_name": "Grep",
        "tool_input": {"pattern": "no-such-token-anywhere"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert scg.MSG in data["hookSpecificOutput"]["additionalContext"]
    ledger_file = ledger_dir / "sess-fp-genuine-empty.jsonl"
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert lines[0]["empty"] is True


def test_classify_result_dict_unknown_shape_is_unjudgeable():
    assert scg._classify_result({"weird": 1}) == "unjudgeable"


def test_classify_result_plain_string_falls_back_to_text_check():
    assert scg._classify_result("") == "empty"
    assert scg._classify_result("[]") == "empty"
    assert scg._classify_result("some match") == "nonempty"


# ---------------------------------------------------------------------
# t-021 half A: session search ledger (correlated against by
# tools/claim_control_gate_next.py, half B -- see tools/test_claim_control_gate.py)
# ---------------------------------------------------------------------


def test_ledger_grep_call_records_pattern(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-1",
        "tool_name": "Grep",
        "tool_input": {"pattern": "RELATED_WORK"},
        "tool_response": {"numFiles": 1, "filenames": ["docs/RELATED_WORK.md"]},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    ledger_file = ledger_dir / "sess-1.jsonl"
    assert ledger_file.exists()
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["tool"] == "Grep"
    assert lines[0]["term"] == "RELATED_WORK"
    assert lines[0]["empty"] is False


def test_ledger_bash_grep_records_whole_command(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-2",
        "tool_name": "Bash",
        "tool_input": {"command": "grep -r RELATED_WORK docs/"},
        "tool_response": {"stdout": "docs/RELATED_WORK.md:1:...", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    ledger_file = ledger_dir / "sess-2.jsonl"
    assert ledger_file.exists()
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["tool"] == "Bash"
    assert lines[0]["term"] == "grep -r RELATED_WORK docs/"
    assert lines[0]["empty"] is False


def test_ledger_non_search_bash_not_recorded(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-3",
        "tool_name": "Bash",
        "tool_input": {"command": "git status --short"},
        "tool_response": {"stdout": "", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    ledger_file = ledger_dir / "sess-3.jsonl"
    assert not ledger_file.exists()


def test_ledger_missing_session_id_records_under_unknown_and_does_not_crash(tmp_path):
    ledger_dir = tmp_path / "ledger"
    sample_path = tmp_path / "sample.json"
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_hook(payload, sample_path=sample_path, ledger_dir=ledger_dir)
    assert result.returncode == 0
    ledger_file = ledger_dir / "unknown.jsonl"
    assert ledger_file.exists()
    lines = [
        json.loads(line)
        for line in ledger_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == 1
    assert lines[0]["term"] == "foo"
    assert sample_path.exists()


# ---------------------------------------------------------------------
# узел C (ремедиация калибровки №8, F1/F14) REWRITE, 2026-08-20: the
# ORIGINAL form of the two tests below (a since-removed helper
# byte-snapshotting the REAL logs/.search-ledger/ before/after) read
# LIVE repo state -- any concurrent session's own search_control_gate
# hook writes (a real, expected effect of that OTHER session's
# Grep/Bash/PowerShell/Read calls) landed inside the SAME window this
# test's before/after compared, producing a false red on the canonical
# `python -m pytest tools/ gateway/ -q` run whenever it happened to run
# alongside another live session -- see docs/tasks/2026-08-20_
# calibration-8-remediation.md, узел C, instances A1/A2, and the
# Lead-closed decision there ("НЕ КАСАТЬСЯ ЖИВОГО").
#
# NEW DIRECTION: run a COPY of search_control_gate.py inside a fresh
# tmp tree (`_copy_gate_to_tmp_repo`). The copy's own module-level
# REPO constant (`REPO = os.path.dirname(os.path.dirname(os.path.
# abspath(__file__)))`) is computed from *the copy's own on-disk
# path* -- so its "battle" default ledger dir
# (`_DEFAULT_LEDGER_DIR = REPO/logs/.search-ledger`) resolves ENTIRELY
# inside tmp_path. It is structurally impossible for the copy to write
# into the real repo's logs/.search-ledger/ (no live read, no live
# write, ever) -- isolation no longer depends on timing or on nobody
# else touching the real ledger during the test window.
#
# Every caller below asserts BYTE EQUALITY of the copy against the
# live SCRIPT right after copying it (узел C spec: "спутник -- пин
# байтового равенства копии живому, иначе тестируется протухший
# клон"). C-2 FIX (критик-гейт t-554, 2026-08-20): that assert is
# TAUTOLOGICAL, not a staleness detector -- _copy_gate_to_tmp_repo()
# writes copy_path.write_bytes(SCRIPT.read_bytes()), so the assert
# compares SCRIPT.read_bytes() (copy time) against SCRIPT.read_bytes()
# (assert time) in the SAME test run; there is no code path in which
# the copy's bytes could differ from the live file's bytes at copy
# time, so it can only go red on a filesystem fault (a write/read
# mismatch), never on a "протухший клон" -- someone editing
# search_control_gate.py AFTER this test run does not make it go red
# either way (the copy is per-test, freshly written every time). The
# assert is harmless and stays as a cheap belt-and-suspenders check on
# the round-trip itself; the ACTUAL freshness pin against source-SHAPE
# drift lives in the W-D section below, `_write_broken_copy()`'s own
# `assert marker in src` -- that one DOES fail when the live source no
# longer contains the literal marker text a mutation probe expects to
# replace.
# ---------------------------------------------------------------------


def _copy_gate_to_tmp_repo(base_dir, dirname="repo_copy"):
    """Copies the LIVE search_control_gate.py (`SCRIPT`) into a fresh
    <base_dir>/<dirname>/tools/search_control_gate.py. Returns
    (copy_script_path, repo_root) -- repo_root/logs/.search-ledger is
    the copy's own module-level default ledger dir (see this section's
    banner comment above for why that is fully inside tmp_path).
    Byte equality with the live source is NOT asserted here -- every
    caller asserts it itself immediately after calling this helper
    (C-2 fix, критик-гейт t-554: that assert is a tautological
    round-trip check, not a staleness detector -- see the section
    banner comment above for why, and _write_broken_copy() below for
    the ACTUAL source-shape freshness pin)."""
    repo_root = Path(base_dir) / dirname
    tools_dir = repo_root / "tools"
    tools_dir.mkdir(parents=True)
    copy_path = tools_dir / "search_control_gate.py"
    copy_path.write_bytes(SCRIPT.read_bytes())
    return copy_path, repo_root


def _run_copy_hook(script_path, payload, sample_path, ledger_dir=_UNSET):
    """Same shape as `_run_hook` (subprocess + JSON stdin), but against
    an explicit *script_path* (a tmp-tree copy) and WITHOUT `_run_hook`'s
    own D2-style "always set a tmp ledger dir" convenience guard --
    that guard is exactly what made the ORIGINAL
    test_ledger_dir_never_defaults_to_real_logs_directory true by
    construction of the test HARNESS, not by anything the gate itself
    does (see узел C spec, Р6, "чтобы его ИМЯ стало правдой"). Passing
    ledger_dir=_UNSET (the default) leaves
    SEARCH_CONTROL_GATE_LEDGER_DIR UNSET in the child's env, exercising
    the script's OWN default; passing an explicit path (including
    None, which is treated the same as _UNSET is NOT supported --
    callers pass a real Path) sets the env var explicitly."""
    env = os.environ.copy()
    env["SEARCH_CONTROL_GATE_SAMPLE_PATH"] = str(sample_path)
    if ledger_dir is not _UNSET:
        env["SEARCH_CONTROL_GATE_LEDGER_DIR"] = str(ledger_dir)
    else:
        env.pop("SEARCH_CONTROL_GATE_LEDGER_DIR", None)
    return subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def test_ledger_dir_honoured_from_env_var_not_real_logs(tmp_path):
    """Узел C, A1 (rewritten, 'НЕ КАСАТЬСЯ ЖИВОГО'): the claim is now
    the STRONGER positive form the spec asks for -- not "nothing
    changed in a noisy directory" but "the copy's OWN default dir
    stayed EMPTY, and the env-pointed dir got EXACTLY the expected
    write" -- both fully inside tmp_path, no live read anywhere."""
    copy_script, repo_root = _copy_gate_to_tmp_repo(tmp_path)
    assert copy_script.read_bytes() == SCRIPT.read_bytes(), (
        "copy_path.write_bytes(SCRIPT.read_bytes()) failed to round-trip -- "
        "this is a FILESYSTEM fault (write/read mismatch), NOT a stale copy "
        "(C-2 fix, критик-гейт t-554: byte-identity holds BY CONSTRUCTION "
        "here, the copy's bytes come directly from SCRIPT.read_bytes() at "
        "copy time). The freshness pin against source-shape drift is "
        "_write_broken_copy()'s own `assert marker in src` below, not this one."
    )

    env_dir = tmp_path / "env-ledger"
    payload = {
        "session_id": "sess-env-check",
        "tool_name": "Grep",
        "tool_input": {"pattern": "envcheck-token"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_copy_hook(copy_script, payload, tmp_path / "sample.json", ledger_dir=env_dir)
    assert result.returncode == 0, result.stderr

    assert (env_dir / "sess-env-check.jsonl").exists()

    copy_default_ledger = repo_root / "logs" / ".search-ledger"
    assert not copy_default_ledger.exists() or list(copy_default_ledger.iterdir()) == [], (
        "env override honoured but the copy's OWN default dir ALSO received "
        f"a write: {list(copy_default_ledger.iterdir()) if copy_default_ledger.exists() else None}"
    )


def test_ledger_dir_never_defaults_to_real_logs_directory(tmp_path):
    """Узел C, A2 (rewritten -- FORM A, decision Р6: 'чтобы его ИМЯ
    стало правдой'). The ORIGINAL form of this test called `_run_hook`
    with no explicit ledger_dir -- but `_run_hook` ITSELF always sets
    SEARCH_CONTROL_GATE_LEDGER_DIR to a fresh tmp dir when the caller
    omits it (see `_run_hook`'s own "D2-style guard" comment above), so
    the ORIGINAL test could never actually exercise the SCRIPT's own
    default -- it verified the test HARNESS's convenience default, not
    the gate's. This form calls `_run_copy_hook` with
    ledger_dir=_UNSET (the SEARCH_CONTROL_GATE_LEDGER_DIR env var is
    left genuinely unset in the child process) against a tmp-tree copy
    -- so the copy's own `_DEFAULT_LEDGER_DIR` (== <repo_root>/logs/
    .search-ledger, fully inside tmp_path -- see this section's banner
    comment) is what actually gets exercised, and the assertion below
    is now literally true of the NAME."""
    copy_script, repo_root = _copy_gate_to_tmp_repo(tmp_path)
    assert copy_script.read_bytes() == SCRIPT.read_bytes(), (
        "copy_path.write_bytes(SCRIPT.read_bytes()) failed to round-trip -- "
        "this is a FILESYSTEM fault (write/read mismatch), NOT a stale copy "
        "(C-2 fix, критик-гейт t-554: byte-identity holds BY CONSTRUCTION "
        "here, the copy's bytes come directly from SCRIPT.read_bytes() at "
        "copy time). The freshness pin against source-shape drift is "
        "_write_broken_copy()'s own `assert marker in src` below, not this one."
    )

    payload = {
        "session_id": "sess-d2-default-check",
        "tool_name": "Grep",
        "tool_input": {"pattern": "d2-default-check-token"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_copy_hook(copy_script, payload, tmp_path / "sample.json")  # ledger_dir=_UNSET
    assert result.returncode == 0, result.stderr

    default_ledger_file = repo_root / "logs" / ".search-ledger" / "sess-d2-default-check.jsonl"
    assert default_ledger_file.exists(), (
        "the copy's OWN default ledger dir did not receive the write -- "
        f"contents of {repo_root / 'logs'}: "
        f"{list((repo_root / 'logs').iterdir()) if (repo_root / 'logs').exists() else 'MISSING'}"
    )


# ---------------------------------------------------------------------
# узел C, W-D red halves (DoD point 4): each injects ONE defect into a
# TMP-ONLY copy (command hygiene p.7(г) -- never the live artifact) and
# asserts the rewritten test's own OBSERVABLE symptom flips -- proving
# the detector, not merely re-running the gate. Permanent tests, not a
# one-off probe.
# ---------------------------------------------------------------------


def _write_broken_copy(base_dir, dirname, marker, replacement):
    src = SCRIPT.read_text(encoding="utf-8")
    assert marker in src, (
        "live search_control_gate.py source shape changed -- update this "
        "mutation probe's marker text"
    )
    broken_src = src.replace(marker, replacement)
    repo_root = Path(base_dir) / dirname
    tools_dir = repo_root / "tools"
    tools_dir.mkdir(parents=True)
    broken_path = tools_dir / "search_control_gate.py"
    broken_path.write_text(broken_src, encoding="utf-8")
    return broken_path, repo_root


def test_wd_red_half_ledger_dir_ignoring_env_breaks_a1_shape(tmp_path):
    """W-D red half for A1: a tmp-only copy whose `_ledger_dir()`
    IGNORES the env var override entirely (always returns its own
    `_DEFAULT_LEDGER_DIR`) must make the exact observable A1 checks --
    the env dir gets the write is a claim that becomes FALSE against
    this mutant."""
    broken_script, repo_root = _write_broken_copy(
        tmp_path, "repo_copy_broken_env",
        marker='return os.environ.get("SEARCH_CONTROL_GATE_LEDGER_DIR") or _DEFAULT_LEDGER_DIR',
        replacement="return _DEFAULT_LEDGER_DIR  # MUTATED (W-D probe): ignores env",
    )
    env_dir = tmp_path / "env-ledger-wd"
    payload = {
        "session_id": "sess-env-check-wd",
        "tool_name": "Grep",
        "tool_input": {"pattern": "envcheck-token-wd"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_copy_hook(broken_script, payload, tmp_path / "sample.json", ledger_dir=env_dir)
    assert result.returncode == 0, result.stderr

    # THE regression this probe exists to catch: with the mutation
    # applied, the env dir must NOT have received the write (A1's own
    # positive assertion would fail against this mutant).
    assert not (env_dir / "sess-env-check-wd.jsonl").exists(), (
        "mutation probe is broken: the mutated copy still honoured the env "
        "var -- update the marker/replacement text above"
    )
    # And per the mutation's OWN (wrong) logic, the write landed in the
    # copy's own default dir instead -- confirms the mutation actually
    # ran, not merely that the env write silently vanished.
    assert (repo_root / "logs" / ".search-ledger" / "sess-env-check-wd.jsonl").exists()


def test_wd_red_half_wrong_default_ledger_dir_breaks_a2_shape(tmp_path):
    """W-D red half for A2: a tmp-only copy whose `_DEFAULT_LEDGER_DIR`
    constant points at a WRONG location must make A2's own observable
    check (a write at <repo_root>/logs/.search-ledger/<session>.jsonl)
    false -- proving A2 actually discriminates a broken DEFAULT, not
    merely a broken env override (test_wd_red_half_ledger_dir_ignoring_
    env_breaks_a1_shape above covers that angle)."""
    broken_script, repo_root = _write_broken_copy(
        tmp_path, "repo_copy_broken_default",
        marker='_DEFAULT_LEDGER_DIR = os.path.join(REPO, "logs", ".search-ledger")',
        replacement='_DEFAULT_LEDGER_DIR = os.path.join(REPO, "logs", ".search-ledger-WD-WRONG")',
    )
    payload = {
        "session_id": "sess-d2-default-check-wd",
        "tool_name": "Grep",
        "tool_input": {"pattern": "d2-default-check-token-wd"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_copy_hook(broken_script, payload, tmp_path / "sample.json")  # ledger_dir=_UNSET
    assert result.returncode == 0, result.stderr

    expected_path = repo_root / "logs" / ".search-ledger" / "sess-d2-default-check-wd.jsonl"
    assert not expected_path.exists(), (
        "mutation probe is broken: the mutated copy still wrote to the "
        "expected default location -- update the marker/replacement text"
    )
    # Confirms the mutation actually ran (write landed at the WRONG path).
    assert (repo_root / "logs" / ".search-ledger-WD-WRONG" / "sess-d2-default-check-wd.jsonl").exists()


# ---------------------------------------------------------------------
# F8 (критик t-339, прецедент tools/owns_gate.py REGISTRY_COMPACT_
# THRESHOLD_LINES): компакция ledger-файла ПРИ ЗАПИСИ, хвост сохраняется
# -- граница РОВНО 500/501 существующих строк (правило 6а кита).
# ---------------------------------------------------------------------


def _write_n_ledger_lines(ledger_dir, session, n):
    ledger_dir = Path(ledger_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{session}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for i in range(n):
            fh.write(
                json.dumps(
                    {"ts": "2026-07-28T00:00:00", "tool": "Grep", "term": f"token-{i}", "empty": False},
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def test_ledger_compaction_boundary_at_exactly_500_existing_lines_plain_append(tmp_path):
    ledger_dir = tmp_path / "ledger"
    path = _write_n_ledger_lines(ledger_dir, "sess-500", 500)
    payload = {
        "session_id": "sess-500",
        "tool_name": "Grep",
        "tool_input": {"pattern": "new-term"},
        "tool_response": {"numFiles": 1, "filenames": ["a.md"]},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # 500 <= threshold -- plain append, nothing dropped: 500 + 1 new = 501.
    assert len(lines) == 501
    assert json.loads(lines[0])["term"] == "token-0"
    assert json.loads(lines[-1])["term"] == "new-term"


def test_ledger_compaction_boundary_at_exactly_501_existing_lines_compacts(tmp_path):
    ledger_dir = tmp_path / "ledger"
    path = _write_n_ledger_lines(ledger_dir, "sess-501", 501)
    payload = {
        "session_id": "sess-501",
        "tool_name": "Grep",
        "tool_input": {"pattern": "new-term"},
        "tool_response": {"numFiles": 1, "filenames": ["a.md"]},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    # 501 > threshold -- compacted to tail (last 500 of the 501 existing,
    # dropping token-0) + 1 new = 501 total.
    assert len(lines) == 501
    assert json.loads(lines[0])["term"] == "token-1"
    assert json.loads(lines[-1])["term"] == "new-term"


def test_ledger_compaction_applies_to_unknown_jsonl_too(tmp_path):
    ledger_dir = tmp_path / "ledger"
    path = _write_n_ledger_lines(ledger_dir, "unknown", 501)
    payload = {
        # no session_id key at all -> falls back to "unknown"
        "tool_name": "Grep",
        "tool_input": {"pattern": "new-term"},
        "tool_response": {"numFiles": 1, "filenames": ["a.md"]},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 501
    assert json.loads(lines[0])["term"] == "token-1"


def test_compact_ledger_lines_keeps_tail_unit():
    lines = [f"line-{i}" for i in range(600)]
    kept = scg._compact_ledger_lines(lines)
    assert len(kept) == 500
    assert kept[0] == "line-100"
    assert kept[-1] == "line-599"


# ---------------------------------------------------------------------
# adversarial battery (CLAUDE.md rule 11): broken JSON (above), a
# non-dict payload, empty stdin (above), invalid UTF-8 bytes, a
# ~1MB command, and the stdin TTY guard.
# ---------------------------------------------------------------------


def test_adversarial_non_dict_payload_list_no_crash(tmp_path):
    result = _run_hook(
        None, sample_path=tmp_path / "sample.json", raw_input=b"[1, 2, 3]"
    )
    assert result.returncode == 0


def test_adversarial_invalid_utf8_bytes_no_crash(tmp_path):
    raw = b'{"tool_name": "Grep", "tool_input": {"pattern": "\xff\xfe broken"}}'
    result = _run_hook(None, sample_path=tmp_path / "sample.json", raw_input=raw)
    assert result.returncode == 0


def test_adversarial_very_large_payload_no_crash(tmp_path):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "grep -r " + ("a" * 1_000_000) + " ."},
        "tool_response": {"stdout": "", "stderr": ""},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json")
    assert result.returncode == 0


def _p4_sibling_module_or_none(base_name: str):
    """Стенд-ин "мира после посадки П4" (координатор, t-535, 2026-08-19,
    Б1): tools/<base_name>_p4.py несёт содержимое, которое landing
    сольёт на боевой путь -- пока сиблинг существует, грузим его
    НАПРЯМУЮ (importlib), чтобы проверить пост-посадочную ветку прямо
    сейчас, не дожидаясь реальной посадки. None, если сиблинг уже снят
    (посадка прошла -- тогда живой модуль САМ несёт этот мир)."""
    path = Path(__file__).resolve().parent / f"{base_name}_p4.py"
    if not path.exists():
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"_p4_probe_{base_name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _assert_stdin_reader_tty_guard_no_block(mod, monkeypatch):
    """Двухмирная проверяемая форма (Б1): ДО посадки П4 модуль несёт
    приватную `_read_stdin_bytes()` (TTY guard + sys.stdin.buffer.read(),
    возвращает bytes); ПОСЛЕ посадки её заменяет П4-хелпер
    `_read_stdin_bytes_deadline()` (тот же TTY guard, форма
    (bytes, timed_out)) -- getattr выбирает точку чтения, реально
    присутствующую в mod, вместо жёсткого имени. Проверяемое
    утверждение теста сохранено буквально в обеих ветках: TTY -> пустые
    байты, read() не вызывается (не блокирует)."""

    class FakeStdin:
        def isatty(self):
            return True

        def read(self):
            raise AssertionError("read() must not be called when stdin is a TTY")

    monkeypatch.setattr(mod.sys, "stdin", FakeStdin())
    new_reader = getattr(mod, "_read_stdin_bytes_deadline", None)
    if new_reader is not None:
        raw, timed_out = new_reader()
        assert raw == b""
        assert timed_out is False
    else:
        assert mod._read_stdin_bytes() == b""


def test_read_stdin_bytes_tty_guard_no_block(monkeypatch):
    """ДВУХМИРНО зелен: (а) `scg` -- ЖИВОЙ модуль, каким бы он сейчас ни
    был (до посадки: несёт `_read_stdin_bytes`; после: несёт П4-хелпер
    -- getattr в _assert_stdin_reader_tty_guard_no_block решает сам);
    (б) `search_control_gate_p4.py`, если ещё существует как отдельный
    файл -- прямая проверка мира ПОСЛЕ посадки прямо сейчас, без
    ожидания реального landing."""
    _assert_stdin_reader_tty_guard_no_block(scg, monkeypatch)

    sibling = _p4_sibling_module_or_none("search_control_gate")
    if sibling is not None:
        _assert_stdin_reader_tty_guard_no_block(sibling, monkeypatch)
