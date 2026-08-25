"""Battery for owns_gate.py's region-aware prose predicate (see its
module docstring, "Region-aware prose predicate"): an owns declaration
is recognized only when the MARKER sits in a "prose" region -- not
fenced, not blockquote, not inline_code -- using this kit's standing
toolkit/tools/md_regions.py scanner. Covers the QUOTED_OWNS_WARN
diagnostic, the fenced/blockquote/inline_code exclusion classes, the
asymmetric continuation-line-start exclusion (fenced/blockquote only,
NOT inline_code), module-failure fallback (missing module / scan()
raising / a degraded result), and the lazy-scan contract (scan() called
at most once, only when worth it).

K-class resolver (MODULE_UNDER_TEST): same convention as
test_owns_gate_retry.py in this same batch node -- this kit's
region-aware pass lives DIRECTLY in the single owns_gate.py file (no
separate sibling module, see docs/tasks/2026-08-25_kit-v0.9.0-batch-
specs.md, node D2's breakdown note on D1-D3: "in the staff deployment
the region logic is merged into the gate bodies; the sibling *_gate_md.py
modules were removed" -- this kit mirrors that live structure directly,
never introducing the sibling in the first place). MODULE_UNDER_TEST
unset/empty -> the live tools/owns_gate.py; any OTHER non-empty value is
an explicit request for a DIFFERENTLY NAMED file (MODULE_UNDER_TEST=<stem>
-> tools/<stem>.py) -- missing -> a LOUD pytest.fail, never a silent
substitution of the live file.

Run: python -m pytest toolkit/tools/test_owns_gate_md.py -q
"""

import importlib.util
import json
import os
import subprocess
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
    alias = "owns_gate_md_target"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module()

_NOW = datetime(2026, 8, 25, 12, 0, 0)


def _writing_payload(prompt: str, session_id="s-1", cwd="D:\\repo", description="sonnet: write") -> dict:
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": description},
        "session_id": session_id,
        "cwd": cwd,
    }


def _run_hook(raw_input, cwd=None, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        cwd=str(cwd) if cwd is not None else None,
        **kwargs,
    )


# ---------------------------------------------------------------------
# Baseline regression (unaffected by the region layer).
# ---------------------------------------------------------------------


def test_extract_owns_paths_canonical_single_path_form():
    prompt = "Given: the repo.\nowns (ABSOLUTE write paths): D:/repo/tools/only_one.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/only_one.py"]


def test_extract_owns_paths_no_marker_is_readonly():
    assert m.extract_owns_paths("Read the file and tell me what's in it.") == []


def test_backtick_wrapped_path_single_line_recognized():
    # ASYMMETRY -- only the marker's position is filtered, not the
    # path's: a backtick-wrapped path on a prose marker line parses as
    # before.
    prompt = "owns: `D:/repo/tools/a.py`, `D:/repo/tools/b.py`"
    assert m.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_backtick_wrapped_path_continuation_recognized():
    prompt = "owns:\n- `D:/repo/tools/a.py`\n- `D:/repo/tools/b.py`\n"
    assert m.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_multiline_bullet_block():
    prompt = "Given: the whole repo.\nowns:\n- D:/repo/tools/a.py\n- D:/repo/tools/b.py\nEdit the files."
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/a.py", "D:/repo/tools/b.py"]


# ---------------------------------------------------------------------
# The old "fenced -- explicit non-goal" pin now holds for TWO
# independent reasons at once (see the module docstring, "Fenced code
# blocks").
# ---------------------------------------------------------------------


def test_fenced_non_goal_pin_holds_reason_a_delimiter_not_path_shaped(monkeypatch):
    # Reason (a), the old one: the "```" delimiter line is itself not
    # path-shaped -- holds even with the region filter neutralized.
    monkeypatch.setattr(m, "scan", None)
    prompt = "**owns (ABSOLUTE write paths):**\n```\nD:/repo/tools/a.py\n```\n"
    assert m.extract_owns_paths(prompt) == []


def test_fenced_non_goal_pin_holds_reason_b_region_excludes_delimiter_line(monkeypatch):
    # Reason (b), the new one: even if "```" were miraculously
    # path-shaped, the region-aware stop condition ends the block there
    # first -- checked in isolation by neutralizing reason (a) via
    # monkeypatching _first_token_path to always accept.
    monkeypatch.setattr(m, "_first_token_path", lambda line: "D:/would-be-a-path.py")
    prompt = "**owns (ABSOLUTE write paths):**\n```\nD:/repo/tools/a.py\n```\n"
    assert m.extract_owns_paths(prompt) == []


# ---------------------------------------------------------------------
# Marker + path fully inside a fenced/blockquote/inline_code region --
# NOT a declaration.
# ---------------------------------------------------------------------


def test_marker_and_path_fully_inside_fenced_block_not_declared():
    prompt = (
        "An example manifest format for future dispatches:\n"
        "```\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "```\n"
        "The actual task: read the file and summarize its contents.\n"
    )
    assert m.extract_owns_paths(prompt) == []


def test_marker_and_path_fully_inside_blockquote_not_declared():
    prompt = (
        "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "The actual task: read the file and summarize its contents.\n"
    )
    assert m.extract_owns_paths(prompt) == []


def test_marker_inside_inline_code_not_declared():
    # A marker inside single backticks (`` `owns:` ``) -- NOT a
    # declaration, even when the path after the backtick wrapper sits
    # in prose (the MARKER's position decides, not the path's).
    prompt = "`owns:` D:/repo/tools/real_target.py\n"
    assert m.extract_owns_paths(prompt) == []


def test_quoted_decoy_does_not_hijack_real_prose_declaration_below():
    # The line-by-line scan continues past a region-excluded marker --
    # the real declaration below (in prose) is found, not lost.
    prompt = (
        "> owns: D:/repo/tools/example_only.py\n"
        "owns: D:/repo/tools/real_target.py\n"
    )
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


# ---------------------------------------------------------------------
# decide(): QUOTED_OWNS_WARN, sidecar not grown.
# ---------------------------------------------------------------------


def test_decide_quoted_owns_warn_when_all_markers_are_quoted_sidecar_not_grown(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\nGiven: the whole repo.\n"
        "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "Edit file x.py as described above."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    assert not registry.exists()


def test_decide_quoted_owns_warn_not_printed_when_no_write_indicator_readonly(tmp_path):
    # The read-only half of the same rule: quoted owns markers, with NO
    # independent write indicator anywhere in the text -- silence, the
    # sidecar does not grow.
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\nGiven: the whole repo.\n"
        "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "Read the file and summarize its contents."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


def test_decide_quoted_owns_warn_message_content():
    assert "quote/fence/inline code" in m.QUOTED_OWNS_WARN_MESSAGE


def test_decide_blind_owns_warn_still_works_unquoted(tmp_path):
    # The old B2-style diagnostic still holds when the marker is in
    # prose but no paths were given (not region-related).
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\nGiven: the whole repo.\n"
        "owns: something unparseable here with no paths.\nEdit file x.py."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    assert "blind" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


def test_decide_normal_declaration_registers_and_no_warn(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\nGiven: the whole repo.\n"
        "owns: D:/repo/tools/real_target.py\nEdit the files."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == ["D:/repo/tools/real_target.py"]


# ---------------------------------------------------------------------
# Module failure: the region filter degrades to a no-op -- EVERY marker
# occurrence is treated as prose, matching the pre-region behavior
# exactly (including the quoted-declaration false-positive that
# behavior implies -- a deliberate fallback, not a new bug).
# ---------------------------------------------------------------------


def test_scan_raises_falls_back_to_no_region_filter(monkeypatch):
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    prompt = (
        "An example manifest format for future dispatches:\n"
        "```\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "```\n"
        "The actual task: read the file and summarize its contents.\n"
    )
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


def test_scan_degraded_falls_back_to_no_region_filter(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    prompt = "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


def test_scan_module_absent_falls_back_to_no_region_filter(monkeypatch):
    monkeypatch.setattr(m, "scan", None)
    prompt = "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


# ---------------------------------------------------------------------
# Lazy scan: scan() called at most once per call, only after the cheap
# pre-filter finds it worthwhile.
# ---------------------------------------------------------------------


def test_scan_not_called_when_no_owns_marker(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    prompt = "Read the file `README.md` > end of text and summarize it.\n"
    assert m.extract_owns_paths(prompt) == []
    assert calls["n"] == 0


def test_scan_not_called_when_marker_present_but_no_region_chars(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    prompt = "owns: D:/repo/tools/real_target.py\n"  # no `, >, or ~
    assert "`" not in prompt and ">" not in prompt and "~" not in prompt
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]
    assert calls["n"] == 0


def test_scan_called_exactly_once_when_marker_and_region_chars_present(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    prompt = "> owns: D:/repo/tools/real_target.py\nowns: D:/repo/tools/second.py\n"
    m.extract_owns_paths(prompt)
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# Sidecar mechanics (window/compaction) are NOT touched by this layer
# -- a spot check (the exhaustive equivalence run is test_owns_gate.py
# itself, unaffected).
# ---------------------------------------------------------------------


def test_window_on_boundary_still_live(tmp_path):
    from datetime import timedelta

    registry = tmp_path / "owns_registry.jsonl"
    now = _NOW
    old_ts = now - timedelta(seconds=m.WINDOW_SECONDS)
    with registry.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": old_ts.strftime(m._TS_FORMAT), "session_key": "other", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:/repo/tools/real_target.py"],
        }) + "\n")
    prompt = "owns: D:/repo/tools/real_target.py\n"
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    assert "OWNS OVERLAP" in output["hookSpecificOutput"]["additionalContext"]


def test_window_beyond_boundary_is_stale(tmp_path):
    from datetime import timedelta

    registry = tmp_path / "owns_registry.jsonl"
    now = _NOW
    stale_ts = now - timedelta(seconds=m.WINDOW_SECONDS + 1)
    with registry.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": stale_ts.strftime(m._TS_FORMAT), "session_key": "other", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:/repo/tools/real_target.py"],
        }) + "\n")
    prompt = "owns: D:/repo/tools/real_target.py\n"
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# Adversarial battery (subprocess, hook path) -- fail-open holds.
# ---------------------------------------------------------------------


def test_cli_broken_json_stdin_exit0_silent(tmp_path):
    result = _run_hook(b"{not valid json", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_non_task_tool_silent(tmp_path):
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo owns: D:\\x"}}
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_quoted_declaration_via_hook_exit0(tmp_path):
    prompt = "> owns: D:/repo/tools/real_target.py\nRead it.\n"
    payload = _writing_payload(prompt)
    payload["cwd"] = str(tmp_path)
    result = _run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    registry = tmp_path / "logs" / "owns_registry.jsonl"
    assert not registry.exists()


def test_cli_non_utf8_bytes_exit0_no_traceback(tmp_path):
    result = _run_hook(b"\xff\xfe\x00\x01not json either", cwd=tmp_path)
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr


# ---------------------------------------------------------------------
# Sanity: the module resolved by the K-class resolver above loads
# independently and carries the region-integration surface.
# ---------------------------------------------------------------------


def test_target_module_loads_and_carries_region_surface():
    assert hasattr(m, "decide")
    assert hasattr(m, "extract_owns_paths")
    assert hasattr(m, "_extract_owns_full")
    assert hasattr(m, "QUOTED_OWNS_WARN_MESSAGE")
    assert hasattr(m, "_safe_scan")
