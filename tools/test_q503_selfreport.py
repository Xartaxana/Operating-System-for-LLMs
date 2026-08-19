"""tools/test_q503_selfreport.py -- Q503 remediation node N2 battery
(builder t-522, 2026-08-19, docs/tasks/2026-08-19_q503-remediation-spec.md).
Node N2 covers TWO independent fixes to session self-report honesty:
 - P3 (K6-K9): tools/session_context.py's _try_hookspath_autofix() --
   Р5(в) reorder: the required .githooks/* files are checked for
   presence BEFORE the `git config` write is attempted, not after.
 - P5 (K10-K13): tools/hook_liveness_probe.py's live-state diff --
   Р6(а) marker attribution: a diff is only a fatal LIVE-STATE-TOUCHED
   leak when it carries the "liveness-probe-" marker (path or content);
   otherwise it is the new, non-fatal LIVE-STATE-AMBIENT finding.

FORM (three-world resolver via Q503_TARGET, by the example of
tools/test_f61_halfstate.py:73-112):
 - Q503_TARGET=live -> ALWAYS the live tools/session_context.py /
   tools/hook_liveness_probe.py (counter-run -- must be RED on the
   discriminating tests below, the fix is not landed there yet).
 - Q503_TARGET unset (default) -> the tools/session_context_q503.py /
   tools/hook_liveness_probe_q503.py siblings when they exist (world 2,
   this dispatch's own fix), else the live files (world 3, post-landing
   -- no counter-mode exists anymore). RERUNNABLE by anyone with no
   code edit.

Both modules resolve off the SAME Q503_TARGET env var (one switch for
the whole node, per the dispatch's DoD commands).

Run: python -m pytest tools/test_q503_selfreport.py -q
Counter-run (must be RED): Q503_TARGET=live python -m pytest tools/test_q503_selfreport.py -q
"""

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
Q503_TARGET = os.environ.get("Q503_TARGET", "").strip().lower()

_SC_LIVE = REPO_ROOT / "tools" / "session_context.py"
_SC_SIBLING = REPO_ROOT / "tools" / "session_context_q503.py"
_HLP_LIVE = REPO_ROOT / "tools" / "hook_liveness_probe.py"
_HLP_SIBLING = REPO_ROOT / "tools" / "hook_liveness_probe_q503.py"

_MODULE_CACHE: dict = {}


def _resolve(live: Path, sibling: Path):
    """(path, is_unpatched) -- see module docstring "FORM"; is_unpatched
    is True ONLY for Q503_TARGET=live while the sibling still exists
    (world 2 counter-mode)."""
    if Q503_TARGET == "live":
        return live, sibling.exists()
    if sibling.exists():
        return sibling, False
    return live, False


def _load(live: Path, sibling: Path, alias_stem: str):
    path, is_unpatched = _resolve(live, sibling)
    key = str(path)
    if key not in _MODULE_CACHE:
        alias = f"q503_battery_{alias_stem}_{'live' if path == live else 'sibling'}"
        spec = importlib.util.spec_from_file_location(alias, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[key] = module
    return _MODULE_CACHE[key], is_unpatched


def _load_sc():
    return _load(_SC_LIVE, _SC_SIBLING, "sc")


def _load_hlp():
    return _load(_HLP_LIVE, _HLP_SIBLING, "hlp")


def _git(args, cwd):
    return subprocess.run(
        ["git"] + args, cwd=str(cwd), capture_output=True, text=True, timeout=20,
    )


# ===========================================================================
# P3 -- K6/K7: Р5(в) reorder (check hook files BEFORE writing git config)
# ===========================================================================


def test_p3_autofix_never_writes_config_when_hook_files_missing(tmp_path):
    # K6 discriminator: old order writes core.hooksPath unconditionally
    # then catches the missing files on a post-write recheck (RED here,
    # config ends up written); new order checks first and never attempts
    # the write at all (GREEN, config stays unset -- no state this run
    # cannot roll back is ever constructed).
    sc_mod, _ = _load_sc()
    _git(["init", "-q"], tmp_path)
    (tmp_path / ".githooks").mkdir()
    # Deliberately do NOT create pre-commit/commit-msg.
    warnings = sc_mod.git_hooks_channel(tmp_path)
    assert any("autofix" in w and "missing" in w for w in warnings), warnings
    assert not any(w.startswith("AUTOFIX:") for w in warnings), warnings
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.returncode != 0 or not result.stdout.strip(), (
        "core.hooksPath was written even though the required hook files "
        "are missing -- Р5(в) reorder not in effect on this target"
    )


def test_p3_missing_githooks_directory_entirely_absent_is_also_skipped(tmp_path):
    # Edge: .githooks/ not just empty but entirely ABSENT -- same
    # "files absent, now checked before the write" branch, no crash.
    sc_mod, _ = _load_sc()
    _git(["init", "-q"], tmp_path)
    # .githooks/ never created at all.
    warnings = sc_mod.git_hooks_channel(tmp_path)
    assert any("autofix" in w and "missing" in w for w in warnings), warnings
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.returncode != 0 or not result.stdout.strip()


def test_p3_autofix_succeeds_when_files_already_present(tmp_path):
    # Regression (both worlds green): when the required files ARE
    # present, the order change is invisible -- write still happens and
    # still succeeds, same AUTOFIX fact as before.
    sc_mod, _ = _load_sc()
    _git(["init", "-q"], tmp_path)
    githooks = tmp_path / ".githooks"
    githooks.mkdir()
    (githooks / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
    (githooks / "commit-msg").write_text("#!/bin/sh\n", encoding="utf-8")
    warnings = sc_mod.git_hooks_channel(tmp_path)
    assert any(w == "AUTOFIX: core.hooksPath set to .githooks" for w in warnings), warnings
    result = _git(["config", "core.hooksPath"], tmp_path)
    assert result.stdout.strip() == ".githooks"


def test_p3_docstring_documents_the_new_order(tmp_path):
    # K7 discriminator: the live docstring's stale claim ("the `git
    # config` write itself exited 0 AND both required hook files are
    # actually present ... afterward") is replaced with an accurate
    # description of the pre-write check -- checked via a marker unique
    # to the corrected text.
    sc_mod, _ = _load_sc()
    doc = sc_mod._try_hookspath_autofix.__doc__ or ""
    assert "Р5(в)" in doc, doc


# ---------------------------------------------------------------------------
# K6/rule 6a boundary: the missing-file-list detail string stays capped at
# 120 chars (same _ascii_sanitize(..., 120) call as before, now reached via
# the pre-write skip branch instead of the post-write one) -- AT and PAST.
# ---------------------------------------------------------------------------


def test_p3_missing_files_detail_at_120_char_boundary_not_truncated(tmp_path, monkeypatch):
    sc_mod, _ = _load_sc()
    _git(["init", "-q"], tmp_path)
    (tmp_path / ".githooks").mkdir()
    long_name = "H" * 120  # single required name, joined string == the name itself
    monkeypatch.setattr(sc_mod, "_REQUIRED_GITHOOKS", (long_name,))
    warnings = sc_mod.git_hooks_channel(tmp_path)
    fact = next(w for w in warnings if "autofix" in w and "missing" in w)
    assert long_name in fact, fact


def test_p3_missing_files_detail_one_past_120_char_boundary_truncated(tmp_path, monkeypatch):
    sc_mod, _ = _load_sc()
    _git(["init", "-q"], tmp_path)
    (tmp_path / ".githooks").mkdir()
    long_name = "H" * 121  # one past the boundary
    monkeypatch.setattr(sc_mod, "_REQUIRED_GITHOOKS", (long_name,))
    warnings = sc_mod.git_hooks_channel(tmp_path)
    fact = next(w for w in warnings if "autofix" in w and "missing" in w)
    assert long_name[:120] in fact, fact
    assert long_name not in fact, fact


# ---------------------------------------------------------------------------
# П3 edge: "перечитка значения перед любой мутацией" -- verified BY
# CONSTRUCTION, not a new re-read step: _try_hookspath_autofix() is only
# ever called from git_hooks_channel()'s single UNSET branch, itself
# reached only after that function's own (single, synchronous, one-shot)
# `git config core.hooksPath` read -- there is exactly one read, and it
# strictly precedes the only mutation this module ever performs (no
# threads, no re-entrancy). This test pins that call-site invariant
# directly (both worlds: unaffected by the Р5(в) reorder, which only
# touched _try_hookspath_autofix's OWN internals).
# ---------------------------------------------------------------------------


def test_p3_autofix_only_called_from_the_unset_branch(tmp_path, monkeypatch):
    sc_mod, _ = _load_sc()
    calls = []
    real = sc_mod._try_hookspath_autofix

    def _spy(root, reason):
        calls.append(reason)
        return real(root, reason)

    monkeypatch.setattr(sc_mod, "_try_hookspath_autofix", _spy)
    # (a) hooksPath pointing elsewhere -- must NOT call autofix at all.
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    _git(["init", "-q"], tmp_path)
    _git(["config", "core.hooksPath", str(other_dir)], tmp_path)
    sc_mod.git_hooks_channel(tmp_path)
    assert calls == [], "autofix invoked even though hooksPath already resolves elsewhere"


# ===========================================================================
# P5 -- K10-K13: Р6(а) marker attribution of the live-state diff
# ===========================================================================


def test_p5_attribution_splits_marked_path_and_unmarked_content(tmp_path):
    # K10: attribution by marker in the PATH (leak) vs no marker at all
    # anywhere (ambient).
    hlp_mod, _ = _load_hlp()
    marked = tmp_path / "liveness-probe-abc123.json"
    marked.write_text("x", encoding="utf-8")
    unmarked = tmp_path / "routing-log.jsonl"
    unmarked.write_text("ordinary session activity, no marker", encoding="utf-8")
    leaked, ambient = hlp_mod.attribute_live_state_diff([str(marked), str(unmarked)])
    assert leaked == [str(marked)], leaked
    assert ambient == [str(unmarked)], ambient


def test_p5_single_file_without_marker_in_name_checked_by_content_clean(tmp_path):
    # K10/edge: a single named file whose PATH never carries the marker
    # (critic_snapshot.json / routing-log.jsonl shape) is cleared to
    # AMBIENT by inspecting its CONTENT, when that content has no marker.
    hlp_mod, _ = _load_hlp()
    critic_snapshot = tmp_path / "critic_snapshot.json"
    critic_snapshot.write_text('{"ordinary": "content"}', encoding="utf-8")
    leaked, ambient = hlp_mod.attribute_live_state_diff([str(critic_snapshot)])
    assert leaked == []
    assert ambient == [str(critic_snapshot)]


def test_p5_single_file_content_carries_marker_is_still_a_leak(tmp_path):
    # K10/K11: the same single-file-by-name case, but its CONTENT DOES
    # carry the marker (the probe leaked a session_id-tagged line into
    # it) -- content attribution, not just the path, must catch this.
    hlp_mod, _ = _load_hlp()
    routing_log = tmp_path / "routing-log.jsonl"
    routing_log.write_text(
        '{"worker_ref":"agent:liveness-probe-xyz"}\n', encoding="utf-8"
    )
    leaked, ambient = hlp_mod.attribute_live_state_diff([str(routing_log)])
    assert leaked == [str(routing_log)]
    assert ambient == []


def test_p5_unreadable_path_defaults_conservatively_to_leak(tmp_path):
    # Boundary of the tri-state classification: a path that cannot be
    # read at all right now (deleted between snapshots, permission
    # error) is UNDECIDABLE and must stay on the fail side, never
    # silently cleared to ambient.
    hlp_mod, _ = _load_hlp()
    gone = tmp_path / "vanished.json"  # never created
    leaked, ambient = hlp_mod.attribute_live_state_diff([str(gone)])
    assert leaked == [str(gone)]
    assert ambient == []


def test_p5_marked_leak_fails_overall_ok_even_with_ambient_noise_present(tmp_path):
    # K11 INVARIANT (mandatory per spec): a genuine, marker-attributed
    # leak keeps failing the run even when unrelated AMBIENT diffs are
    # present in the SAME report -- ambient noise never masks a real
    # leak. This is the discriminating counter-run test for K11/K12:
    # it fails on the live (old) module with a KeyError -- the
    # "live_state_leaked" key does not exist there at all yet.
    hlp_mod, _ = _load_hlp()
    report = {
        "no_cases": False, "settings_unreadable": False,
        "case_missing": [], "stale_case": [],
        "live_state_leaked": ["liveness-probe-leak.json"],
        "live_state_ambient": ["routing-log.jsonl"],
        "results": [{"verdict": hlp_mod.OK}],
    }
    assert hlp_mod.overall_ok(report) is False


def test_p5_ambient_only_does_not_fail_the_run(tmp_path):
    # K12: overall_ok changes EXACTLY in the live_state_diff/leaked
    # branch -- an ambient-only report (no leak) is OK.
    hlp_mod, _ = _load_hlp()
    report = {
        "no_cases": False, "settings_unreadable": False,
        "case_missing": [], "stale_case": [],
        "live_state_leaked": [],
        "live_state_ambient": ["routing-log.jsonl"],
        "results": [{"verdict": hlp_mod.OK}],
    }
    assert hlp_mod.overall_ok(report) is True


def test_p5_empty_diff_is_ok_no_noise_in_report(tmp_path):
    # "внутри сессии diff пуст -> OK без шума": an empty diff on both
    # sides produces no LIVE-STATE-* lines at all in the human report.
    hlp_mod, _ = _load_hlp()
    report = {
        "no_cases": False, "settings_unreadable": False,
        "case_missing": [], "stale_case": [],
        "live_state_leaked": [], "live_state_ambient": [],
        "results": [],
        "info_lines": [], "import_findings": [],
    }
    assert hlp_mod.overall_ok(report) is True
    out = hlp_mod.format_human_report(report)
    assert "LIVE-STATE-TOUCHED" not in out
    assert "LIVE-STATE-AMBIENT" not in out


def test_p5_ambient_finding_rendered_distinctly_from_touched(tmp_path):
    # K12: format_human_report renders the two findings with DIFFERENT
    # labels -- LIVE-STATE-AMBIENT is not silently folded into
    # LIVE-STATE-TOUCHED, and a leak's own line is not lost when ambient
    # entries are also present.
    hlp_mod, _ = _load_hlp()
    report = {
        "no_cases": False, "settings_unreadable": False,
        "case_missing": [], "stale_case": [],
        "live_state_leaked": ["liveness-probe-leak.json"],
        "live_state_ambient": ["routing-log.jsonl"],
        "results": [],
        "info_lines": [], "import_findings": [],
    }
    out = hlp_mod.format_human_report(report)
    assert "LIVE-STATE-TOUCHED: liveness-probe-leak.json" in out
    assert "LIVE-STATE-AMBIENT: routing-log.jsonl" in out


def test_p5_vocabulary_constant_exists():
    # K12: the LIVE-STATE-AMBIENT verdict is a named module constant,
    # not just an inline string literal -- discriminates against the
    # live module, which has no such constant at all.
    hlp_mod, _ = _load_hlp()
    assert hlp_mod.LIVE_STATE_AMBIENT == "LIVE-STATE-AMBIENT"
