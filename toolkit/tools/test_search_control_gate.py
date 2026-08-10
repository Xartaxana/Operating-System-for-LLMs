"""Tests for tools/search_control_gate.py -- the ported gate (source:
HQ's own tools/search_control_gate.py).

See the target module's docstring ("AN EARLIER FIX") for the two
problems being fixed at the source, both preserved here:
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
`_run_hook` and the regression test near the bottom).

THIS TEMPLATE'S ADAPTATION: PowerShell is handled identically to Bash
-- see "PowerShell" section below for the select-string ledger test
and the non-search-PowerShell-command regression.

Run from the repo root: python -m pytest toolkit/tools/test_search_control_gate.py -q
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import search_control_gate as scg  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "search_control_gate.py"


def _run_hook(payload, sample_path=None, ledger_dir=None, raw_input=None):
    env = os.environ.copy()
    if sample_path is not None:
        env["SEARCH_CONTROL_GATE_SAMPLE_PATH"] = str(sample_path)
    else:
        env.pop("SEARCH_CONTROL_GATE_SAMPLE_PATH", None)
    # NEVER leave the ledger dir unset -- that falls through to the
    # script's real logs/.search-ledger default. A fresh temp dir is
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
# (structural judgement before serialization)
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


def test_missing_result_on_search_tool_writes_sample(tmp_path):
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
# _looks_like_search must classify by the COMMAND STRING, not the
# whole serialized tool_input (an unrelated `description` field must
# not influence it).
# ---------------------------------------------------------------------


def test_description_field_does_not_make_non_search_command_look_like_search(tmp_path):
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


def test_command_text_classification_unit():
    assert scg._command_text_for_classification(
        "Bash", {"command": "git status --short", "description": "Find modified files"}
    ) == "git status --short"
    assert scg._looks_like_search(
        "Bash",
        scg._command_text_for_classification(
            "Bash", {"command": "git status --short", "description": "Find modified files"}
        ),
    ) is False


def test_command_itself_still_classified_as_search_unit():
    assert scg._looks_like_search(
        "Bash",
        scg._command_text_for_classification("Bash", {"command": "grep -rn foo ."}),
    ) is True


# ---------------------------------------------------------------------
# PowerShell (this template's adaptation): handled identically to Bash
# -- term = whole command verbatim, searchability via SEARCH_TOKENS,
# "select-string" added as PowerShell's own grep-equivalent cmdlet.
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
# CONTENT/COUNT-MODE FALSE-POSITIVE FIX: non-empty content must win
# over empty-looking filenames/numFiles.
# ---------------------------------------------------------------------


def test_classify_result_nonempty_content_wins_over_empty_filenames_num_files():
    # Regression for the live false positive: content-mode dict with a
    # real match but empty filenames/numFiles (file list not populated
    # outside files_with_matches mode) must classify as "nonempty".
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
    # Full-pipeline regression of the live false-positive form (a),
    # content-mode: a real Grep match must NOT warn and must record
    # "empty": false in the ledger.
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
    # Full-pipeline regression of the live false-positive form (b), count-mode.
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
    # Control (command hygiene point 6: a negative claim needs a
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
# half A: session search ledger (correlated against by
# tools/claim_control_gate.py, half B -- see tools/test_claim_control_gate.py)
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


def _real_ledger_snapshot():
    """A snapshot keyed by filename -> byte SIZE/CONTENT, not merely
    the set of filenames present -- blind to an APPEND to an existing
    file would miss a real leak into the live ledger."""
    real_ledger_dir = Path(scg.REPO) / "logs" / ".search-ledger"
    if not real_ledger_dir.exists():
        return {}
    return {
        p.name: p.read_bytes()
        for p in real_ledger_dir.glob("*.jsonl")
    }


def test_ledger_dir_honoured_from_env_var_not_real_logs(tmp_path):
    before = _real_ledger_snapshot()
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-env-check",
        "tool_name": "Grep",
        "tool_input": {"pattern": "envcheck-token"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert (ledger_dir / "sess-env-check.jsonl").exists()
    after = _real_ledger_snapshot()
    assert after == before


def test_ledger_dir_never_defaults_to_real_logs_directory(tmp_path):
    """Calling `_run_hook` WITHOUT an explicit ledger_dir must NOT fall
    through to the real logs/.search-ledger/unknown.jsonl -- see
    `_run_hook`'s own env-var handling above."""
    before = _real_ledger_snapshot()
    payload = {
        "session_id": "sess-d2-default-check",
        "tool_name": "Grep",
        "tool_input": {"pattern": "d2-default-check-token"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_hook(payload)
    assert result.returncode == 0
    after = _real_ledger_snapshot()
    assert after == before


# ---------------------------------------------------------------------
# ledger compaction at write time, tail kept -- boundary EXACTLY
# 500/501 existing lines (rule 6a of the builder role).
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
# adversarial battery (interactive-surface DoD): broken JSON (above), a
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


def test_read_stdin_bytes_tty_guard_no_block(monkeypatch):
    class FakeStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(scg.sys, "stdin", FakeStdin())
    assert scg._read_stdin_bytes() == b""


# ---------------------------------------------------------------------
# TEMPORAL runtime artifacts: logs/.search-ledger/ and
# logs/posttooluse-schema-sample.json -- BOTH worlds: the directory is
# absent (created silently) AND the directory cannot be created
# (fail-open, exit 0, no crash) -- rule 6a boundary discipline applied
# to a directory-existence limit, not just a numeric one.
# ---------------------------------------------------------------------


def test_ledger_dir_absent_created_silently_world_a(tmp_path):
    ledger_dir = tmp_path / "brand-new-ledger-dir"
    assert not ledger_dir.exists()
    payload = {
        "session_id": "sess-create-a",
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"numFiles": 1, "filenames": ["a.md"]},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert ledger_dir.is_dir()
    assert (ledger_dir / "sess-create-a.jsonl").exists()


def test_ledger_dir_cannot_be_created_fails_open_world_b(tmp_path):
    # A FILE occupies the path the ledger dir would need as its own
    # PARENT -- os.makedirs(ledger_dir, exist_ok=True) inside
    # _append_ledger_line raises (NotADirectoryError on POSIX,
    # FileNotFoundError/OSError on Windows) -- must fail open: exit 0,
    # no traceback, the empty-search WARN (an independent code path)
    # still fires.
    blocker = tmp_path / "blocker-file"
    blocker.write_text("not a directory", encoding="utf-8")
    unusable_ledger_dir = blocker / "ledger"
    payload = {
        "session_id": "sess-create-b",
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"numFiles": 0, "filenames": []},
    }
    result = _run_hook(payload, sample_path=tmp_path / "sample.json", ledger_dir=unusable_ledger_dir)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    # The empty-search WARN is an independent branch (ledger write is
    # wrapped in its own try/except in _process) -- it still fires.
    data = json.loads(result.stdout)
    assert scg.MSG in data["hookSpecificOutput"]["additionalContext"]
    assert not unusable_ledger_dir.exists()


def test_sample_parent_dir_absent_created_silently_world_a(tmp_path):
    sample_path = tmp_path / "brand-new-sample-dir" / "sample.json"
    assert not sample_path.parent.exists()
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"totally_unrecognized_key": 123},
    }
    result = _run_hook(payload, sample_path=sample_path)
    assert result.returncode == 0
    assert sample_path.exists()


def test_sample_parent_dir_cannot_be_created_fails_open_world_b(tmp_path):
    # A FILE occupies the path the sample file's PARENT directory would
    # need -- os.makedirs(parent, exist_ok=True) inside
    # `_write_sample_once` raises -- must fail open: exit 0, no
    # traceback, no sample written (the write is wrapped in its own
    # try/except and never affects the exit code).
    blocker = tmp_path / "blocker-file-2"
    blocker.write_text("not a directory", encoding="utf-8")
    unusable_sample_path = blocker / "sample.json"
    payload = {
        "tool_name": "Grep",
        "tool_input": {"pattern": "foo"},
        "tool_response": {"totally_unrecognized_key": 123},
    }
    result = _run_hook(payload, sample_path=unusable_sample_path)
    assert result.returncode == 0
    assert not unusable_sample_path.exists()
