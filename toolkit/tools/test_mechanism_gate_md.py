"""tools/test_mechanism_gate_md.py -- K-resolver battery for the
region-aware SKIP_RE/TIER_LINE_RE behaviour of tools/mechanism_gate.py
(ported from the HQ mirror's own sibling-selector convention;
toolkit's own md_regions scanner, see toolkit/tools/md_regions.py).

TOOLKIT REALITY (a documented adaptation, not a missed symmetry): the
HQ mirror originally landed its region-aware rewrite via a temporary
byte-copy SIBLING module (mechanism_gate_md.py) so a red/green pair
could be compared before the merge, then folded the sibling directly
into the live gate and deleted the sibling file -- keeping this test's
resolver convention around as regression coverage. This kit's own
mechanism_gate.py went straight from non-region-aware to region-aware
in ONE edit (no intermediate sibling file was ever created here) --
so, AS OF TODAY, there is no separate non-region twin to discriminate
against: both selector values below resolve to the SAME file
(tools/mechanism_gate.py), and the "discrimination" tests exercise
real assertions against the merged, region-aware gate rather than
proving a live/sibling CONTRAST. The resolver mechanism (env var
selection, importlib.util loading by explicit path, the loud-fail-on-
missing-sibling rule) is ported verbatim for CONVENTION PARITY with
the rest of this port batch's own K-class test files (each following
the same MODULE_UNDER_TEST switch) -- not because a sibling currently
exists here.

MODULE_UNDER_TEST switch:
  unset/empty -> the sibling tools/mechanism_gate_md.py IF it exists,
                 else the live tools/mechanism_gate.py, silently (no
                 sibling exists today -- this always resolves to live).
  "live"      -> the live tools/mechanism_gate.py verbatim, explicitly
                 (kept for convention parity and as an explicit escape
                 hatch; today identical to the default resolution).
  anything else (e.g. "sibling") -> the sibling is REQUESTED explicitly;
                 its absence is a LOUD pytest.fail naming the requested
                 path -- never a silent fallback to live.

The existing tools/test_mechanism_gate.py (the live gate's own full
battery, including its own fence/prose boundary-pair tests) is NOT
touched by this file -- this file is an independent, resolver-driven
battery over the SAME region behaviour, run separately.

Run (default):                python -m pytest tools/test_mechanism_gate_md.py -q
Explicit live selection:      MODULE_UNDER_TEST=live python -m pytest tools/test_mechanism_gate_md.py -q
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # Default (MODULE_UNDER_TEST empty) -- the sibling IF it exists, else
    # the live file, silently (no sibling exists in this kit today -- see
    # module docstring "TOOLKIT REALITY"). A sibling REQUESTED EXPLICITLY
    # (MODULE_UNDER_TEST set and not "live") that does not exist -> a LOUD
    # failure, never a silent fallback to live.
    live = TOOLS_DIR / "mechanism_gate.py"
    if MODULE_UNDER_TEST == "live":
        return live
    sibling = TOOLS_DIR / "mechanism_gate_md.py"
    if MODULE_UNDER_TEST == "":
        return sibling if sibling.exists() else live
    if not sibling.exists():
        pytest.fail(
            f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested sibling "
            f"{sibling} but it does not exist -- no silent live fallback"
        )
    return sibling


SCRIPT = _resolve_script_path()


def _load_module():
    alias = f"mechanism_gate_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mg = _load_module()

_REGION_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live" and not (TOOLS_DIR / "mechanism_gate_md.py").exists(),
    reason="region-internals probes (mg.scan/_maybe_scan/_skip_declared/"
    "_region_filtered_tier_declarations) target the private surface of "
    "whatever SCRIPT resolved to; kept for convention parity with the "
    "resolver pattern -- see module docstring",
)

CONFIG_SAMPLE = """
roles:
  lead:
    subscription:
      model: claude-fable-5
    api:
      provider:
      model:
      api_key_env:
"""


# ---------------------------------------------------------------------
# Baseline behaviour regression (both selector values -- the live gate
# is not otherwise touched by this file).
# ---------------------------------------------------------------------


def test_parse_axes_follows_the_map():
    assert mg.parse_axes("## Axis 1 -- X\n## Axis 6 -- Y\n") == [1, 6]


def test_mechanism_paths_filters_prefixes_with_boundary():
    staged = ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md", "gateway/metrics.py"]
    assert mg.mechanism_paths(staged) == ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"]


def test_decide_merge_and_non_mechanism_commits_pass():
    code, _ = mg.decide(msg="Merge branch 'x'", block_extra="",
                        staged=["CLAUDE.md"], map_text="## Axis 1 --\n", merging=True)
    assert code == 0
    code, _ = mg.decide(msg="chore: telemetry", block_extra="",
                        staged=["gateway/metrics.py"], map_text="## Axis 1 --\n")
    assert code == 0


def test_decide_fails_closed_without_map_or_axes():
    code, reason = mg.decide(msg="feat: X", block_extra="", staged=["CLAUDE.md"], map_text=None)
    assert code == 1 and "fail-closed" in reason


def test_explicit_skip_line_in_prose_passes():
    code, _ = mg.decide(
        msg="docs: typo fix\n\naxes: not a mechanism (typo in rule 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 -- Deployments\n")
    assert code == 0


def test_axis_block_satisfies_gate():
    code, _ = mg.decide(
        msg="feat: mechanism X\n\naxis 1: covered -- both deployments",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


def test_find_tier_declarations_returns_all_lines_region_blind():
    # find_tier_declarations() -- region-BLIND, byte for byte (see the
    # gate's own module docstring, "ALL-MUST-PASS COUNTS ONLY UNQUOTED
    # TIER LINES") -- untouched by the region port.
    msg = "feat: X\n\ntier: sonnet\n\nSome other text\ntier: fable\n"
    assert mg.find_tier_declarations(msg) == ["sonnet", "fable"]


def test_decide_full_tier_fable_default_passes():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0


def test_decide_full_tier_mismatch_fails():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "Not lead tier" in reason


# ---------------------------------------------------------------------
# Axis lines: NOT region-filtered (a deliberate non-goal -- see the
# gate's own module docstring, "AXIS LINES ARE NOT FILTERED").
# ---------------------------------------------------------------------


def test_axis_line_inside_fence_still_counts_documented_non_goal():
    # Axis block INSIDE a fence still counts -- both selector values give
    # the SAME result -- NOT a discrimination case, a regression pin on
    # this port's own declared scope.
    msg = "feat: mechanism X\n\n```\naxis 1: covered -- both deployments\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


# ---------------------------------------------------------------------
# Fence-boundary pair (rule: at the boundary AND beyond it) -- a skip/
# tier line inside a fence does not count; the SAME line outside a
# fence does.
# ---------------------------------------------------------------------


def test_e1_skip_line_inside_fence_does_not_pass_the_gate():
    """AT the boundary: the region filter (default resolution -- see
    module docstring "TOOLKIT REALITY") makes the assert below GREEN --
    a skip line quoted whole inside a triple-backtick example does NOT
    count, the gate requires a real axis block -> code=1."""
    msg = (
        "docs: showing the reader an example of the skip format\n\n"
        "```\n"
        "axes: not a mechanism (example syntax for documentation)\n"
        "```\n"
    )
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 1
    assert "fail-closed" not in reason  # a map exists -- rejected on the axis block, not the map
    assert "axis block is incomplete" in reason


def test_e1b_same_skip_line_outside_fence_passes():
    """BEYOND the boundary: the identical text, NOT inside a fence ->
    counts, code=0 -- the positive counterpart of test_e1 above."""
    msg = "docs: showing the reader an example of the skip format\n\naxes: not a mechanism (example syntax for documentation)\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


def test_e2_blockquote_skip_line_structurally_never_matches_skip_re_either_selector():
    """An EMPIRICAL finding (command-hygiene rule 6), not a claimed
    discrimination: SKIP_RE = r"^\\s*axes\\s*:\\s*not\\s+a\\s+mechanism\\s*\\("
    anchors "^\\s*" (ONLY whitespace before the literal "axes") --
    a blockquote marker ">" (md_regions._QUOTE_RE) prepends a ">" to the
    line's content, which breaks this anchor STRUCTURALLY, with no
    involvement from the region filter at all -- "> axes: not a
    mechanism (...)" does not match SKIP_RE regardless of which file
    resolved (empirically verified below, a positive control on the
    bare regex, not through decide()). Symmetric for TIER_LINE_RE."""
    msg = "docs: quoting the skip format\n\n> axes: not a mechanism (quoted example)\n"
    # Positive control (command hygiene, rule 6): the same shape checked
    # directly against the regex, not through decide() -- proves the
    # cause is the anchor itself, not the region filter's presence.
    assert mg.SKIP_RE.search(msg) is None
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 1
    assert "axis block is incomplete" in reason


def test_e4_tier_line_inside_fence_gives_no_tier_line_error():
    """With the region filter active -- a tier line inside a fence does
    NOT count, the error is specifically "No tier line" (not "Not lead
    tier")."""
    msg = (
        "feat: mechanism X\n\naxis 1: covered\n"
        "Example declaration format:\n```\ntier: fable\n```\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "No \"tier:" in reason


def test_e4b_same_tier_line_outside_fence_passes():
    """BEYOND the boundary: the identical tier line, NOT fenced -> counts,
    matches the default fable binding -> code=0."""
    msg = "feat: mechanism X\n\naxis 1: covered\ntier: fable\n"
    code, _ = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0


def test_e3_fenced_spoofer_wrong_tier_ignored_missing_real_line_rejects():
    """ALL-MUST-PASS counts only UNQUOTED tier lines: a fenced line
    carrying a deliberately WRONG value ("sonnet", binding defaults to
    fable) sits alongside the ABSENCE of any real prose tier line -- the
    fenced spoofer is dropped from the checked list entirely -> code=1,
    "No tier line" (not "Not lead tier")."""
    msg = (
        "feat: mechanism X\n\naxis 1: covered\n"
        "Format example (for documentation):\n```\ntier: sonnet\n```\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "No \"tier:" in reason
    assert "Not lead tier" not in reason


def test_e3b_mixed_fenced_wrong_spoofer_and_real_prose_correct_tier():
    # The same fenced wrong-value line, but a REAL correct prose tier line
    # is ALSO present -- the fenced spoofer is filtered out, only the real
    # prose line is checked, and it matches -> code=0.
    msg = (
        "feat: mechanism X\n\naxis 1: covered\n"
        "Format example (for documentation):\n```\ntier: sonnet\n```\n"
        "tier: fable\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0, reason


# ---------------------------------------------------------------------
# block_extra is never region-scanned -- a fence-shaped diff text with
# an axis-like literal still closes the axis via find_missing().
# ---------------------------------------------------------------------


def test_block_extra_fenced_axis_text_not_region_scanned_documented_non_goal():
    code, _ = mg.decide(
        msg="feat: mechanism X", block_extra="+```\n+axis 1: covered\n+```\n",
        staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


# ---------------------------------------------------------------------
# Laziness (I-1): scan() runs at most once, only when warranted.
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i1_scan_not_called_on_non_mechanism_commit(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide_full(
        msg="```\naxes: not a mechanism (check)\n```\n", block_extra="",
        staged=["gateway/metrics.py"], map_text="## Axis 1 --\n", config_text=None)
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_not_called_on_merge_commit(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide_full(
        msg="Merge branch 'x'\n```\ntier: fable\n```\n", block_extra="",
        staged=["CLAUDE.md"], map_text="## Axis 1 --\n", config_text=None, merging=True)
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_not_called_without_marker_hint(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    # No "axes"/"tier" literal at all -- no scan call, even with ">"/"`"
    # present in the text.
    mg.decide(msg="feat: X\n> just a quote with no keywords `code`\n",
               block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_not_called_without_region_chars(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide(msg="feat: X\n\naxis 1: covered\ntier: fable\n",  # no `>~ at all
               block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_called_exactly_once_per_decide_full_call(monkeypatch):
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    msg = "feat: X\n\naxis 1: covered\n```\ntier: fable\n```\ntier: fable\n"
    mg.decide_full(msg=msg, block_extra="", staged=["CLAUDE.md"],
                    map_text="## Axis 1 --\n", config_text=None)
    # ONE call for the whole decide_full() -- reused by both the skip and
    # the tier check.
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# Fail-open (I-0): any scanner failure -> the region filter becomes a
# no-op, byte for byte the pre-region behaviour (including "a quoted
# skip silences the gate again").
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_e8_i0_scan_raises_falls_back_to_pre_region_quoted_skip_silences_gate(monkeypatch):
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(mg, "scan", _broken_scan)
    msg = "docs: example\n\n```\naxes: not a mechanism (example syntax)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


@_REGION_ONLY
def test_e8_i0_scan_degraded_falls_back_to_pre_region_quoted_skip_silences_gate(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(mg, "scan", lambda text: _FakeResult())
    # A fence, not a quote (see test_e2 above -- a quote structurally
    # never matches SKIP_RE at all, unusable as an I-0 probe here; a
    # fence does not break the anchor -- region, and only region,
    # decides whether the line counts).
    msg = "docs: example\n\n```\naxes: not a mechanism (example)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


@_REGION_ONLY
def test_e8_i0_scan_module_absent_falls_back_to_pre_region_quoted_skip_silences_gate(monkeypatch):
    monkeypatch.setattr(mg, "scan", None)
    msg = "docs: example\n\n```\naxes: not a mechanism (example)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0
