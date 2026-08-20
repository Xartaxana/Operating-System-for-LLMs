"""tools/test_hook_liveness_probe.py -- unit + integration tests for
tools/hook_liveness_probe.py (t-387). Live gates are NEVER mutated by
these tests (CLAUDE.md command-hygiene rule 7g) -- verdict-classification
tests use small synthetic dummy scripts written to tmp_path; only the
final integration test exercises the REAL gates, through the probe's own
run_all(), which is itself isolation-safe by construction (see module
docstring of hook_liveness_probe.py, "ISOLATION" / "PRE/POST LIVE-STATE
CHECK").
"""

import importlib.util
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_liveness_probe as hlp  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- Q503 dual-world resolver (t-522, K13: docs/tasks/2026-08-19_q503-
# remediation-spec.md node N2) -- mirrors tools/test_f61_halfstate.py's
# _resolve_module_path/_load (:73-112) for the TWO pins below whose
# assertion shape genuinely differs between the two worlds (the rest of
# this file keeps using the plain `hlp` top-level import, unaffected).
# Q503_TARGET is a LOCAL copy of the same env var name
# test_q503_selfreport.py uses -- no shared helper module (non-goal,
# N1 sibling precedent: local copies).
Q503_TARGET = os.environ.get("Q503_TARGET", "").strip().lower()
_HLP_Q503_LIVE = REPO_ROOT / "tools" / "hook_liveness_probe.py"
_HLP_Q503_SIBLING = REPO_ROOT / "tools" / "hook_liveness_probe_q503.py"
_HLP_Q503_CACHE: dict = {}


def _resolve_hlp_q503_path():
    """(path, is_unpatched) -- same three-world semantics as
    test_f61_halfstate.py:73-90 / test_session_context_wiring.py's own
    _resolve_sc_q503_path: is_unpatched is True ONLY for Q503_TARGET=live
    while the sibling still exists (world 2, pre-landing counter-mode).
    Default (unset) -> the hook_liveness_probe_q503.py sibling when
    present (world 2, this dispatch's own fix), else the live file
    (world 3, post-landing -- is_unpatched is always False there)."""
    if Q503_TARGET == "live":
        return _HLP_Q503_LIVE, _HLP_Q503_SIBLING.exists()
    if _HLP_Q503_SIBLING.exists():
        return _HLP_Q503_SIBLING, False
    return _HLP_Q503_LIVE, False


def _load_hlp_q503():
    path, is_unpatched = _resolve_hlp_q503_path()
    key = str(path)
    if key not in _HLP_Q503_CACHE:
        alias = f"hlp_q503_pin_{'live' if path == _HLP_Q503_LIVE else 'sibling'}"
        spec = importlib.util.spec_from_file_location(alias, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _HLP_Q503_CACHE[key] = module
    return _HLP_Q503_CACHE[key], is_unpatched


def _write_script(tmp_path: Path, name: str, body: str) -> str:
    """Writes a small python script under tmp_path and returns its
    ABSOLUTE path -- run_subprocess_case accepts an already-absolute
    script path as-is (see its own docstring): pytest's tmp_path may sit
    on a DIFFERENT drive than hlp.REPO, so a repo-relative form via
    os.path.relpath would raise ValueError on a cross-drive host."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(path)


# --------------------------------------------------------------------
# format_excerpt -- boundary (rule 6a)
# --------------------------------------------------------------------


def test_format_excerpt_500_chars_kept_whole():
    s = "a" * 500
    assert hlp.format_excerpt(s) == s


def test_format_excerpt_501_chars_truncated_with_marker():
    s = "a" * 501
    out = hlp.format_excerpt(s)
    assert out.startswith("a" * 500)
    assert out != s
    assert "truncated" in out


def test_format_excerpt_none_is_empty_string():
    assert hlp.format_excerpt(None) == ""


# --------------------------------------------------------------------
# run_subprocess_case verdict classes, via synthetic dummy scripts
# --------------------------------------------------------------------


def test_missing_script_gives_missing_result(tmp_path):
    result = hlp.run_subprocess_case("tools/__does_not_exist_probe__.py", {})
    assert result == {"missing": True}
    verdict, _detail = hlp.check_response(result, 0, ("x",))
    assert verdict == hlp.MISSING


def test_ok_case_response(tmp_path):
    rel = _write_script(tmp_path, "ok_case.py", """
        import sys
        sys.stdout.write("PROBE-OK-MARK\\n")
        sys.exit(0)
    """)
    result = hlp.run_subprocess_case(rel, {"x": 1})
    verdict, detail = hlp.check_response(result, 0, ("PROBE-OK-MARK",))
    assert verdict == hlp.OK, detail


def test_dead_case_silent_output(tmp_path):
    rel = _write_script(tmp_path, "silent_case.py", """
        import sys
        sys.exit(0)
    """)
    result = hlp.run_subprocess_case(rel, {})
    verdict, detail = hlp.check_response(result, 0, ("EXPECTED-ANCHOR",))
    assert verdict == hlp.DEAD, detail


def test_mismatch_case_wrong_anchor(tmp_path):
    rel = _write_script(tmp_path, "wrong_anchor_case.py", """
        import sys
        sys.stdout.write("something unrelated\\n")
        sys.exit(0)
    """)
    result = hlp.run_subprocess_case(rel, {})
    verdict, detail = hlp.check_response(result, 0, ("EXPECTED-ANCHOR",))
    assert verdict == hlp.MISMATCH, detail
    assert "anchor missing" in detail


def test_mismatch_case_wrong_exit_code(tmp_path):
    rel = _write_script(tmp_path, "wrong_exit_case.py", """
        import sys
        sys.stdout.write("PROBE-OK-MARK\\n")
        sys.exit(0)
    """)
    result = hlp.run_subprocess_case(rel, {})
    verdict, detail = hlp.check_response(result, 2, ("PROBE-OK-MARK",))
    assert verdict == hlp.MISMATCH, detail
    assert "exit 0 != expected 2" in detail


def test_crash_case_unhandled_traceback(tmp_path):
    rel = _write_script(tmp_path, "crash_case.py", """
        raise RuntimeError("boom, deliberate probe crash")
    """)
    result = hlp.run_subprocess_case(rel, {})
    verdict, detail = hlp.check_response(result, 0, ())
    assert verdict == hlp.CRASH, detail
    assert "Traceback" in detail


def test_hung_case_killed_on_timeout(tmp_path):
    rel = _write_script(tmp_path, "sleepy_case.py", """
        import time
        time.sleep(3)
    """)
    result = hlp.run_subprocess_case(rel, {}, timeout=1)
    assert result.get("hung") is True
    verdict, _detail = hlp.check_response(result, 0, ())
    assert verdict == hlp.HUNG


def test_not_hung_when_instant_script_under_short_timeout(tmp_path):
    """Boundary companion to test_hung_case_killed_on_timeout: the SAME
    short timeout (1s) does NOT classify an instantaneous script as
    HUNG -- rule 6a requires both sides of a limit tested."""
    rel = _write_script(tmp_path, "instant_case.py", """
        import sys
        sys.stdout.write("FAST-MARK\\n")
        sys.exit(0)
    """)
    result = hlp.run_subprocess_case(rel, {}, timeout=1)
    assert result.get("hung") is not True
    verdict, detail = hlp.check_response(result, 0, ("FAST-MARK",))
    assert verdict == hlp.OK, detail


# --------------------------------------------------------------------
# artifact / response+artifact checkers
# --------------------------------------------------------------------


def test_artifact_only_dead_when_artifact_missing():
    result = {"returncode": 0, "stdout": "", "stderr": ""}
    verdict, detail = hlp.check_artifact_only(result, 0, False, "file not found")
    assert verdict == hlp.DEAD, detail


def test_artifact_only_ok_when_artifact_present_and_silent_response():
    result = {"returncode": 0, "stdout": "", "stderr": ""}
    verdict, detail = hlp.check_artifact_only(result, 0, True, "artifact present")
    assert verdict == hlp.OK, detail


def test_response_and_artifact_mismatch_when_artifact_missing_but_response_ok():
    result = {"returncode": 0, "stdout": "ANCHOR here", "stderr": ""}
    verdict, detail = hlp.check_response_and_artifact(
        result, 0, ("ANCHOR",), (), False, "artifact absent")
    assert verdict == hlp.MISMATCH, detail


def test_response_and_artifact_ok_when_both_present():
    result = {"returncode": 0, "stdout": "ANCHOR here", "stderr": ""}
    verdict, detail = hlp.check_response_and_artifact(
        result, 0, ("ANCHOR",), (), True, "artifact present")
    assert verdict == hlp.OK, detail


# --------------------------------------------------------------------
# const-ref / import-finding mechanism (Р3в)
# --------------------------------------------------------------------


def test_verify_const_ok_for_real_nonempty_string_constant():
    finding = hlp._verify_const("dispatch_gate", "BLOCK_MESSAGE_NO_DOD")
    assert finding == ""


def test_verify_const_finding_for_missing_attribute():
    # "dispatch_gate" IS one of the already-imported gate modules
    # (_GATE_MODULES) -- unlike an arbitrary stdlib module, this
    # exercises the "module imported fine, attribute missing" branch
    # specifically, not the "module not importable" branch.
    finding = hlp._verify_const("dispatch_gate", "NON_EXISTENT_CONST_XYZ_PROBE")
    assert "empty/missing" in finding


def test_verify_const_finding_for_unimportable_module():
    finding = hlp._verify_const("this_module_does_not_exist_probe_xyz", "ANYTHING")
    assert "not importable" in finding


def test_run_case_downgrades_ok_response_to_mismatch_on_broken_const(tmp_path):
    """A case whose response check alone would be OK, but whose declared
    const_ref points at a missing attribute, must NOT report OK -- a
    drifted/emptied source constant is itself a finding (module
    docstring, "WHY A DECLARATIVE CASES TABLE")."""
    rel = _write_script(tmp_path, "const_ok_case.py", """
        import sys
        sys.stdout.write("ANCHOR-HERE\\n")
        sys.exit(0)
    """)
    case = {
        "name": "synthetic-const-broken",
        "script": rel,
        "kind": "response",
        "isolation": "subprocess",
        "build": lambda: {"payload": {}, "env": None, "extra": {}},
        "expected_exit": 0,
        "anchors": ("ANCHOR-HERE",),
        "const_ref": ("os", "NON_EXISTENT_CONST_XYZ_PROBE"),
    }
    result = hlp.run_case(case)
    assert result["verdict"] == hlp.MISMATCH, result["detail"]
    assert "const-check" in result["detail"]


def test_run_case_import_failure_does_not_crash_probe(tmp_path):
    """A case referencing a module that fails to import must be logged
    as a finding, not raise out of run_case() -- see module docstring
    "WHY A DECLARATIVE CASES TABLE"."""
    rel = _write_script(tmp_path, "const_broken_import_case.py", """
        import sys
        sys.stdout.write("ANCHOR-HERE\\n")
        sys.exit(0)
    """)
    case = {
        "name": "synthetic-import-broken",
        "script": rel,
        "kind": "response",
        "isolation": "subprocess",
        "build": lambda: {"payload": {}, "env": None, "extra": {}},
        "expected_exit": 0,
        "anchors": ("ANCHOR-HERE",),
        "const_ref": ("this_module_does_not_exist_probe_xyz", "ANYTHING"),
    }
    result = hlp.run_case(case)  # must not raise
    assert result["verdict"] == hlp.MISMATCH
    assert "not importable" in result["detail"]


# --------------------------------------------------------------------
# composition sverka (both directions) -- CASE-MISSING / STALE-CASE
# --------------------------------------------------------------------


def test_classify_settings_commands_python_tool_and_info_line():
    pairs = [
        ("PreToolUse", "python tools/dispatch_gate.py"),
        ("SessionStart", "echo not-a-python-tool-hook"),
    ]
    scripts, info_lines = hlp.classify_settings_commands(pairs)
    assert scripts == {"tools/dispatch_gate.py"}
    assert len(info_lines) == 1
    assert "informational" in info_lines[0]


def test_check_composition_case_missing_when_settings_names_uncovered_script(monkeypatch):
    monkeypatch.setattr(
        hlp, "load_settings_hook_commands",
        lambda *a, **kw: [("PreToolUse", "python tools/totally_uncovered_gate.py")],
    )
    monkeypatch.setattr(hlp, "CASES", [])
    unreadable, case_missing, stale_case, _info = hlp.check_composition()
    assert unreadable is False
    assert case_missing == ["tools/totally_uncovered_gate.py"]
    assert stale_case == []


def test_check_composition_stale_case_when_case_names_unreferenced_script(monkeypatch):
    monkeypatch.setattr(hlp, "load_settings_hook_commands", lambda *a, **kw: [])
    monkeypatch.setattr(
        hlp, "CASES",
        [{"script": "tools/some_case_only_script.py"}],
    )
    unreadable, case_missing, stale_case, _info = hlp.check_composition()
    assert unreadable is False
    assert case_missing == []
    assert stale_case == ["tools/some_case_only_script.py"]


def test_check_composition_settings_unreadable(monkeypatch):
    monkeypatch.setattr(hlp, "load_settings_hook_commands", lambda *a, **kw: None)
    unreadable, case_missing, stale_case, info_lines = hlp.check_composition()
    assert unreadable is True
    assert case_missing == []
    assert stale_case == []
    assert info_lines == []


def test_load_settings_hook_commands_missing_file_returns_none(tmp_path):
    bad_path = str(tmp_path / "does_not_exist_settings.json")
    assert hlp.load_settings_hook_commands(bad_path) is None


def test_load_settings_hook_commands_malformed_json_returns_none(tmp_path):
    bad_path = tmp_path / "settings.json"
    bad_path.write_text("{ not valid json at all", encoding="utf-8")
    assert hlp.load_settings_hook_commands(str(bad_path)) is None


def test_load_settings_hook_commands_reads_real_settings():
    """Positive control paired with the two negative-form tests above
    (command hygiene p.6): same function, same call form, against a
    KNOWN-present file -- confirms an empty/None result elsewhere is a
    real negative, not a call miss."""
    pairs = hlp.load_settings_hook_commands()
    assert pairs is not None
    assert len(pairs) >= 12
    scripts, _info = hlp.classify_settings_commands(pairs)
    assert "tools/dispatch_gate.py" in scripts
    assert "tools/hygiene_gate.py" in scripts


# --------------------------------------------------------------------
# NO-CASES / empty CASES table
# --------------------------------------------------------------------


def test_run_all_no_cases(monkeypatch):
    monkeypatch.setattr(hlp, "CASES", [])
    report = hlp.run_all()
    try:
        assert report["no_cases"] is True
        assert hlp.overall_ok(report) is False
    finally:
        hlp._cleanup_temp_dirs(report)


def test_format_human_report_no_cases_line():
    report = {"no_cases": True}
    out = hlp.format_human_report(report)
    assert "NO-CASES" in out


# --------------------------------------------------------------------
# live-state fingerprint diff mechanics
# --------------------------------------------------------------------


def test_diff_live_state_detects_content_change(tmp_path):
    f = tmp_path / "state.txt"
    f.write_text("before", encoding="utf-8")
    before = {str(f): hlp._file_fingerprint(str(f))}
    f.write_text("after-changed", encoding="utf-8")
    after = {str(f): hlp._file_fingerprint(str(f))}
    diff = hlp.diff_live_state(before, after)
    assert str(f) in diff


def test_diff_live_state_no_diff_when_unchanged(tmp_path):
    f = tmp_path / "state.txt"
    f.write_text("stable", encoding="utf-8")
    snap = {str(f): hlp._file_fingerprint(str(f))}
    assert hlp.diff_live_state(snap, dict(snap)) == []


def test_diff_live_state_detects_new_file_appearing(tmp_path):
    before = {}
    f = tmp_path / "new_state.txt"
    f.write_text("brand new", encoding="utf-8")
    after = {str(f): hlp._file_fingerprint(str(f))}
    diff = hlp.diff_live_state(before, after)
    assert str(f) in diff


# --------------------------------------------------------------------
# M1 -- ambient (appeared-and-vanished) vs genuine leak attribution
# (batch 2026-08-20, follow-up to A4: the flake this closes is a path
# NOT present in the pre-run snapshot that is ALSO unreadable at
# check time -- it appeared and disappeared entirely inside the
# probe's own fingerprint window, e.g. another session's transient
# ambient file, never this probe's own isolation leaking).
# --------------------------------------------------------------------


def test_m1_appeared_and_vanished_path_is_ambient_not_leak_red_control(tmp_path):
    """RED CONTROL + fix, both shown (DoD point 2): the same diff entry
    -- a path absent from the "before" snapshot and unreadable right
    now -- classified TWO ways by the SAME function, differing only in
    whether `before` is supplied.

    RED (old mechanism, reproduced live): `attribute_live_state_diff`
    called WITHOUT `before` is still this function's documented
    back-compat default (tools/test_q503_selfreport.py's own pin uses
    exactly this one-argument form) -- it is the untouched shape the
    function had before this fix, and on this exact diff entry it
    gives the FALSE leak this batch closes.

    FIX: the SAME path, with `before` supplied and NOT containing it
    (never existed at "before" time), is reclassified ambient."""
    vanished_path = str(tmp_path / "ambient-appeared-and-gone.json")
    # Deliberately never created -- _content_contains_marker() returns
    # None (unreadable) for it, the "appeared and vanished inside the
    # window" shape the diagnosis describes.

    leaked_red, ambient_red = hlp.attribute_live_state_diff([vanished_path])
    assert leaked_red == [vanished_path], leaked_red
    assert ambient_red == [], ambient_red

    leaked_fixed, ambient_fixed = hlp.attribute_live_state_diff([vanished_path], before={})
    assert leaked_fixed == [], leaked_fixed
    assert ambient_fixed == [vanished_path], ambient_fixed


def test_m1_leak_when_path_existed_before_and_is_now_unreadable(tmp_path):
    """Boundary companion (rule 6a) -- "не переусердствуй" from the
    spec: the ONE combination the fix must NOT touch. A path that WAS
    present in `before` (existed, was fingerprinted) and is unreadable
    now (deleted mid-run, or a genuine permission error) stays on the
    leak side exactly as before this fix -- only "absent from before
    AND unreadable now" is reclassified, nothing else."""
    existed_path = str(tmp_path / "existed-then-vanished.json")
    before = {existed_path: (10, 123456789, "somehash")}  # fingerprinted at "before" time
    # file itself never created here -> unreadable "now"
    leaked, ambient = hlp.attribute_live_state_diff([existed_path], before=before)
    assert leaked == [existed_path], leaked
    assert ambient == []


def test_m1_positive_control_genuine_marker_content_leak_still_caught_with_before(tmp_path):
    """DoD point 3: a REAL leak (this probe's own marker landed in a
    path's readable CONTENT, the path itself stays present) must keep
    failing even when `before` is supplied and does not contain the
    path -- proves the fix narrows ONLY the unreadable+absent-before
    combination, never a genuine positive content match. Without this,
    the fix could simply be blinding the check instead of narrowing
    it."""
    leaked_file = tmp_path / "routing-log.jsonl"
    leaked_file.write_text(
        '{"worker_ref":"agent:' + hlp.LIVENESS_MARKER + 'xyz"}\n', encoding="utf-8"
    )
    leaked, ambient = hlp.attribute_live_state_diff([str(leaked_file)], before={})
    assert leaked == [str(leaked_file)], leaked
    assert ambient == []


def test_overall_ok_false_on_live_state_diff():
    # Р6(а) DUAL-WORLD PIN (K13, t-522, docs/tasks/2026-08-19_q503-
    # remediation-spec.md node N2). Old world (is_unpatched, live file
    # pre-landing): ANY live-state diff fails the run via the plain
    # "live_state_diff" key. New world (hook_liveness_probe_q503.py
    # sibling, this dispatch's own fix): only a MARKER-ATTRIBUTED leak
    # ("live_state_leaked") fails it -- K11's invariant that a genuine
    # leak still fails the run, even under the new attribution logic.
    mod, is_unpatched = _load_hlp_q503()
    if is_unpatched:
        report = {
            "no_cases": False, "settings_unreadable": False,
            "case_missing": [], "stale_case": [],
            "live_state_diff": ["some/path"],
            "results": [{"verdict": mod.OK}],
        }
    else:
        report = {
            "no_cases": False, "settings_unreadable": False,
            "case_missing": [], "stale_case": [],
            "live_state_leaked": ["liveness-probe-some/path"],
            "results": [{"verdict": mod.OK}],
        }
    assert mod.overall_ok(report) is False


def test_overall_ok_true_when_everything_clean():
    # Dual-world sibling of the pin above (K13) -- an empty diff/leak
    # list is OK in both worlds, no shape change to the assertion
    # itself, only to the report dict's key name.
    mod, is_unpatched = _load_hlp_q503()
    if is_unpatched:
        report = {
            "no_cases": False, "settings_unreadable": False,
            "case_missing": [], "stale_case": [],
            "live_state_diff": [],
            "results": [{"verdict": mod.OK}, {"verdict": mod.OK}],
        }
    else:
        report = {
            "no_cases": False, "settings_unreadable": False,
            "case_missing": [], "stale_case": [],
            "live_state_leaked": [],
            "results": [{"verdict": mod.OK}, {"verdict": mod.OK}],
        }
    assert mod.overall_ok(report) is True


# --------------------------------------------------------------------
# INTEGRATION: live run of all 13 real cases against the real gates
# --------------------------------------------------------------------


def test_live_run_of_all_cases_is_ok():
    """Узел C (ремедиация калибровки №8), A4 -- REWRITTEN 2026-08-20.
    ORIGINAL form asserted the RAW `live_state_diff` was empty -- but
    hook_liveness_probe.py's own before/after fingerprint spans the
    WHOLE run of all 13 cases (a multi-second window), and ANY
    concurrent session's own hook activity landing in that window
    (its OWN legitimate PostToolUse/PreToolUse writes into the same
    monitored paths, e.g. .claude/dod_track/<session>.json from a
    plain Edit call) makes the raw diff non-empty for reasons that
    have nothing to do with THIS probe's own isolation -- see узел C
    DAG instance A4 (confirmed twice independently: this узел's own
    W-A control run, and узел F.3's canon run on 2026-08-20, both
    diffed on a live session's own file).

    hook_liveness_probe.py itself already carries the fix for this
    (Р6(а)/t-522, 2026-08-19): `attribute_live_state_diff()` splits the
    raw diff into `live_state_leaked` (this probe's OWN isolation
    failing -- carries the "liveness-probe-" marker) and
    `live_state_ambient` (someone/something else's concurrent activity
    -- informational, never fails the run) -- `overall_ok()` already
    keys off `live_state_leaked` only. This TEST was the one part of
    the class not yet updated to match -- direction "касаться, но
    ОТЛИЧАТЬ ОКРУЖЕНИЕ" (узел C decision, A4 -- "не касаться" is
    explicitly forbidden here BY THE TEST'S OWN PURPOSE: it exists to
    prove the real gates do not leak into real paths, so it must keep
    reading real state, just attributed correctly).

    NON-GOAL (узел C non-goals): hook_liveness_probe.py itself is
    NOT edited here -- byte-for-byte, per the dispatch spec. This is a
    test-side fix only."""
    report = hlp.run_all()
    try:
        assert report["no_cases"] is False
        assert report["settings_unreadable"] is False
        assert report["case_missing"] == [], report["case_missing"]
        assert report["stale_case"] == [], report["stale_case"]
        assert report["live_state_leaked"] == [], report["live_state_leaked"]
        # live_state_ambient (unmarked concurrent activity from this SAME
        # session or another live one) is INFORMATIONAL ONLY -- it is
        # deliberately NOT asserted empty here; overall_ok() below does not
        # key off it either (see module docstring "EXIT CODE").
        assert report["import_findings"] == [], report["import_findings"]

        non_ok = [r for r in report["results"] if r["verdict"] != hlp.OK]
        assert non_ok == [], non_ok
        assert len(report["results"]) == 13

        assert hlp.overall_ok(report) is True
    finally:
        hlp._cleanup_temp_dirs(report)


def test_wd_red_half_synthetic_marker_path_flips_verdict_negative(tmp_path):
    """W-D red half for A4 (узел C DoD point 4): a SYNTHETIC diff entry
    whose path carries hook_liveness_probe.py's own LIVENESS_MARKER
    must be attributed as a genuine LEAK (`live_state_leaked`, not
    `live_state_ambient`), and `overall_ok()` on a report carrying it
    must be False -- proves `attribute_live_state_diff`/`overall_ok`
    actually discriminate a marked leak from ordinary ambient noise,
    not merely that a clean run happens to pass. Uses the REAL
    (unmodified, per non-goals) hook_liveness_probe.py functions
    against a purely synthetic path/report -- no live repo state is
    touched."""
    marked_path = str(tmp_path / f"{hlp.LIVENESS_MARKER}synthetic-leak.jsonl")
    Path(marked_path).write_text("noise", encoding="utf-8")

    leaked, ambient = hlp.attribute_live_state_diff([marked_path])
    assert leaked == [marked_path]
    assert ambient == []

    report = {
        "no_cases": False, "settings_unreadable": False,
        "case_missing": [], "stale_case": [],
        "live_state_leaked": leaked,
        "results": [{"verdict": hlp.OK}],
    }
    assert hlp.overall_ok(report) is False


def test_main_cli_exit_code_zero_on_live_gates(capsys):
    exit_code = hlp.main([])
    captured = capsys.readouterr()
    assert exit_code == 0, captured.out
    assert "OVERALL: OK" in captured.out
    assert "13/13" in captured.out


def test_main_cli_json_flag_produces_parseable_json(capsys):
    exit_code = hlp.main(["--json"])
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["no_cases"] is False
    assert len(data["results"]) == 13
