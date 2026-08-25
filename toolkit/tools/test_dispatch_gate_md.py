"""toolkit/tools/test_dispatch_gate_md.py -- region-aware / FRESHNESS
K-class battery for toolkit/tools/dispatch_gate.py (route port).

ADAPTATION FROM THE STAFF K-CLASS CONVENTION: the staff twin's own
tools/test_dispatch_gate_md.py resolves a MODULE_UNDER_TEST env var
between a separate _md.py SIBLING file (region-aware logic was staged
there before landing on the live path by byte-copy) and the live
tools/dispatch_gate.py -- a two-stage history this kit never had:
region-aware/FRESHNESS logic is built directly into
toolkit/tools/dispatch_gate.py from day one (per the batch spec's own
note for nodes D1-D3: "region logic is fused into the gate bodies ...
sync by function, mirror the live staff structure" -- the staff twin
itself no longer carries a separate dispatch_gate_md.py file either,
see its own module docstring: it was landed byte-copy onto the live
path). There is therefore no "live, non-region-aware" file in this
kit to discriminate against -- the discrimination-pair tests the staff
battery carries (green on the sibling, red on MODULE_UNDER_TEST=live)
have no kit equivalent and are NOT ported; this file tests the one
real module's actual behavior directly.

MODULE_UNDER_TEST is kept ONLY for the resolver CONVENTION itself
(route port DoD item 7): "" or "live" both resolve to the one real
module (toolkit/tools/dispatch_gate.py); any OTHER explicit value
names a module that does not exist in this kit -- pytest.fail, no
silent fallback to the live file under a different name (K1,
docs/tasks/2026-08-25_queue8-mechbatch-spec.md class).

Existing toolkit/tools/test_dispatch_gate.py (the live file's own
battery) is untouched by this file -- run separately as confirmation
that the live file is not disturbed.

Run: python -m pytest toolkit/tools/test_dispatch_gate_md.py -q
"""

import importlib.util
import os
import sys
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # No separate sibling ever existed in this kit -- "" and "live"
    # both resolve to the one real module. Any OTHER value is a
    # request for a module this kit does not have -- loud failure
    # (K1), not a silent substitution of the live file.
    live = TOOLS_DIR / "dispatch_gate.py"
    if MODULE_UNDER_TEST in ("", "live"):
        return live
    pytest.fail(
        f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested a module that "
        "does not exist in this kit -- toolkit/tools/dispatch_gate.py is "
        "the only target (region-aware/FRESHNESS logic lives directly on "
        "the live file, no separate _md sibling was ever staged here) -- "
        "no silent fallback (K1)."
    )


SCRIPT = _resolve_script_path()


def _load_module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module(SCRIPT, "dispatch_gate_under_test")

_REPO_ROOT = str(TOOLS_DIR.parent)  # toolkit/ -- dispatch_gate.py's own parents[1]


def _builder_payload(prompt: str, description=None, cwd=None) -> dict:
    tool_input = {"subagent_type": "builder", "prompt": prompt}
    if description is not None:
        tool_input["description"] = description
    payload = {"tool_name": "Task", "tool_input": tool_input}
    payload["cwd"] = cwd if cwd is not None else _REPO_ROOT
    return payload


def _task_payload(prompt: str, cwd=None) -> dict:
    """Same shape as _builder_payload but cwd defaults to ABSENT (not
    _REPO_ROOT) -- freshness_warn() falls back to os.getcwd() on a
    missing cwd, and some tests below want that exact fallback path."""
    tool_input = {"subagent_type": "builder", "prompt": prompt}
    payload = {"tool_name": "Task", "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def _fw(prompt: str, cwd: str = _REPO_ROOT) -> str:
    return m.freshness_warn(_task_payload(prompt, cwd=cwd))


# =======================================================================
# Region-aware given-path WARN: four forms -- fenced no-WARN / prose
# WARN / inline-code (backticks) WARN / blockquote no-WARN. Polarity
# source: given_path_warn(), see the module docstring, "Region-aware
# filtering".
# =======================================================================

_MISSING = "tools/fake_md_no_such_file.py"


def test_given_path_fenced_no_warn():
    prompt = f"Example:\n```\nGiven: {_MISSING}\n```\n"
    warn = m.given_path_warn(_builder_payload(prompt))
    assert warn == ""


def test_given_path_prose_warns():
    prompt = f"Given: {_MISSING}. Read it."
    warn = m.given_path_warn(_builder_payload(prompt))
    assert "GIVEN-PATH WARN" in warn
    assert _MISSING in warn


def test_given_path_inline_code_backticks_warns():
    # Backticks are the CANONICAL manifest form in this kit ("owns:
    # `D:/x.py`") -- inline code is NOT a quote for this layer's
    # purposes (see "Region-aware filtering" in the module docstring).
    prompt = f"Given: `{_MISSING}`. Read it."
    warn = m.given_path_warn(_builder_payload(prompt))
    assert "GIVEN-PATH WARN" in warn
    assert _MISSING in warn


def test_given_path_blockquote_no_warn():
    prompt = f"> Given: {_MISSING}\n"
    warn = m.given_path_warn(_builder_payload(prompt))
    assert warn == ""


def test_given_path_any_unquoted_occurrence_qualifies_dedup_preserved():
    # The SAME path mentioned once fenced and once in prose -- dedup is
    # preserved, the WARN names the path exactly once.
    path = "tools/fake_md_dedup_no_such.py"
    prompt = f"Example:\n```\nGiven: {path}\n```\nGiven: {path}. Read it."
    warn = m.given_path_warn(_builder_payload(prompt))
    assert "GIVEN-PATH WARN" in warn
    assert warn.count(path) == 1


# =======================================================================
# decide()'s region-aware B2-write branch: a QUOTED owns-declaration
# with a real path token, and NO given marker anywhere (quoted or not)
# -- the block LIFTS (exit 0) on the region-aware file; the SAME text
# with the fence removed still blocks (positive control, command
# hygiene p.6).
# =======================================================================

_QUOTED_OWNS_PROMPT_FENCED = (
    "DoD: acceptance criteria -- the test is green, witness attached.\n"
    "An example of someone else's manifest, for illustration only:\n"
    "```\n"
    "owns (ABSOLUTE write paths): D:/repo/tools/foreign_example.py\n"
    "```\n"
    "Discuss the approach, do not act on it yourself."
)

_QUOTED_OWNS_PROMPT_UNFENCED = (
    "DoD: acceptance criteria -- the test is green, witness attached.\n"
    "An example of someone else's manifest, for illustration only:\n"
    "owns (ABSOLUTE write paths): D:/repo/tools/foreign_example.py\n"
    "Discuss the approach, do not act on it yourself."
)


def test_quoted_foreign_owns_declaration_lifts_block():
    exit_code, message = m.decide(_builder_payload(_QUOTED_OWNS_PROMPT_FENCED, description="sonnet: x"))
    assert exit_code == 0, message


def test_same_text_without_fence_still_blocks_positive_control():
    exit_code, message = m.decide(_builder_payload(_QUOTED_OWNS_PROMPT_UNFENCED, description="sonnet: x"))
    assert exit_code == 2, message
    assert "context manifest" in message


def test_manifest_quoted_warn_fires_on_lifted_block():
    warn = m.manifest_quoted_warn(_builder_payload(_QUOTED_OWNS_PROMPT_FENCED, description="sonnet: x"))
    assert "MANIFEST-QUOTED WARN" in warn
    assert "owns" in warn


# --- write_quoted_warn: the flip is never silent when NO manifest
# marker exists at all (a write verb quoted out, nothing else). -------

_WRITE_QUOTED_FENCED_PROMPT = (
    "DoD: acceptance criteria -- the test is green, witness attached.\n"
    "An example instruction for a different dispatch:\n"
    "```\n"
    "Edit file x.py per the spec.\n"
    "```\n"
    "Discuss the approach, do not act on it yourself."
)

_WRITE_QUOTED_BLOCKQUOTE_PROMPT = (
    "DoD: acceptance criteria -- the test is green, witness attached.\n"
    "> Edit file x.py per the spec.\n"
    "Discuss the approach, do not act on it yourself."
)


def test_write_quoted_warn_fenced_form_fires():
    payload = _builder_payload(_WRITE_QUOTED_FENCED_PROMPT, description="sonnet: x")
    exit_code, _ = m.decide(payload)
    assert exit_code == 0  # block lifted -- confirm the WARN is not mute
    warn = m.write_quoted_warn(payload)
    assert "WRITE-QUOTED WARN" in warn


def test_write_quoted_warn_blockquote_form_fires():
    payload = _builder_payload(_WRITE_QUOTED_BLOCKQUOTE_PROMPT, description="sonnet: x")
    exit_code, _ = m.decide(payload)
    assert exit_code == 0
    warn = m.write_quoted_warn(payload)
    assert "WRITE-QUOTED WARN" in warn


def test_write_quoted_warn_silent_when_manifest_marker_present():
    # Positive control (don't double the message): the owns-prompt
    # above already carries an owns marker (quoted) -- covered by
    # manifest_quoted_warn, write_quoted_warn stays silent.
    warn = m.write_quoted_warn(_builder_payload(_QUOTED_OWNS_PROMPT_FENCED, description="sonnet: x"))
    assert warn == ""


def test_write_quoted_warn_silent_when_no_flip():
    # Positive control: the write verb is NOT quoted -- the
    # region-aware signal is also True, no flip happened, silent.
    prompt = "DoD: acceptance criteria -- the test is green. Edit file x.py per the spec."
    warn = m.write_quoted_warn(_builder_payload(prompt, description="sonnet: x"))
    assert warn == ""


# --- dod_quoted_warn: DoD-marker-only-in-a-fence does not change
# decide() (B1 untouched), but the WARN fires additionally. -----------

_DOD_ONLY_FENCED_PROMPT = (
    "An example of a correct acceptance marker for a different dispatch:\n"
    "```\n"
    "DoD: acceptance criteria -- the test is green.\n"
    "```\n"
    "Read file x.py and describe its behavior, write nothing."
)


def test_dod_only_in_fence_exit0_unchanged():
    exit_code, message = m.decide(_builder_payload(_DOD_ONLY_FENCED_PROMPT, description="sonnet: read"))
    assert exit_code == 0, message


def test_dod_only_in_fence_warns():
    warn = m.dod_quoted_warn(_builder_payload(_DOD_ONLY_FENCED_PROMPT, description="sonnet: read"))
    assert "DOD-QUOTED WARN" in warn


# =======================================================================
# FRESHNESS layer -- class (v): a <path>.<ext>:N[-M] anchor pointing
# past the end of the real file (M3). Class (a), "check NN(x)
# references a nonexistent calibration-protocol subpoint", is NOT
# ported this increment -- see the module docstring of
# toolkit/tools/dispatch_gate.py, "FRESHNESS layer", for the measured
# reason (0 CHK-anchor occurrences in this kit's own calibration
# protocol vs. 64 in the staff twin).
# =======================================================================


def test_freshness_non_task_agent_tool_no_warn():
    warn = m.freshness_warn(
        {"tool_name": "Bash", "tool_input": {"prompt": "tools/dispatch_gate.py:999999"}}
    )
    assert warn == ""


def test_freshness_payload_not_dict_no_warn():
    assert m.freshness_warn("not a dict") == ""


def test_freshness_prompt_missing_no_warn():
    warn = m.freshness_warn({"tool_name": "Task", "tool_input": {"subagent_type": "builder"}})
    assert warn == ""


def test_freshness_prompt_empty_string_no_warn():
    assert _fw("") == ""


def test_freshness_prompt_not_string_no_warn():
    warn = m.freshness_warn(
        {"tool_name": "Task", "tool_input": {"subagent_type": "builder", "prompt": None}}
    )
    assert warn == ""


def test_freshness_no_candidates_no_warn():
    assert _fw("Given: the whole repo. Read the files carefully.") == ""


def test_freshness_no_candidates_zero_filesystem_opens(monkeypatch):
    # The prefilter must skip the filesystem entirely with no anchor
    # candidate at all (counted with a real open() wrapper).
    calls = {"n": 0}
    real_open = open

    def counting_open(*args, **kwargs):
        calls["n"] += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)
    warn = _fw("Given: the whole repo. Nothing anchor-shaped here at all.")
    assert warn == ""
    assert calls["n"] == 0


def test_freshness_scan_unavailable_layer_silent_wholly(monkeypatch):
    # Unlike given_path_warn, freshness_warn has NO bare-regex I-0
    # fallback -- with no region info at all, the layer stays silent
    # entirely (see the module docstring, "FRESHNESS layer").
    monkeypatch.setattr(m, "_safe_scan", lambda text: None)
    assert _fw("tools/dispatch_gate.py:999999") == ""


# --- class (v) core: within/beyond bounds, missing file, foreign tree --


def test_freshness_class_v_within_bounds_no_warn():
    assert _fw("Given: tools/dispatch_gate.py:10.") == ""


def test_freshness_class_v_beyond_eof_warns_m3():
    warn = _fw("Given: tools/dispatch_gate.py:9999999.")
    assert "FRESHNESS WARN:" in warn
    assert "tools/dispatch_gate.py:9999999" in warn


def test_freshness_class_v_missing_file_no_warn():
    assert _fw("Given: tools/fake_freshness_no_such_file.py:5.") == ""


def test_freshness_class_v_absolute_within_bounds_no_warn():
    abs_path = str(Path(_REPO_ROOT) / "tools" / "dispatch_gate.py")
    assert _fw(f"Given: {abs_path}:10.") == ""


def test_freshness_class_v_absolute_beyond_eof_warns():
    abs_path = str(Path(_REPO_ROOT) / "tools" / "dispatch_gate.py")
    warn = _fw(f"Given: {abs_path}:9999999.")
    assert "FRESHNESS WARN:" in warn
    assert abs_path in warn


def test_freshness_class_v_foreign_tree_not_under_root_no_warn():
    assert _fw(r"Given: D:\SomeOtherTree\fake.py:999999.") == ""


def test_freshness_class_v_directory_anchor_no_warn(tmp_path):
    d = tmp_path / "sub.py"
    d.mkdir()
    warn = _fw(f"{d}:1", cwd=str(tmp_path))
    assert warn == ""


def test_freshness_class_v_range_anchor_uses_max_bound():
    warn = _fw("Given: tools/dispatch_gate.py:5-9999999.")
    assert "FRESHNESS WARN:" in warn
    assert "tools/dispatch_gate.py:5-9999999" in warn


def test_freshness_class_v_range_anchor_within_both_bounds_no_warn():
    assert _fw("Given: tools/dispatch_gate.py:5-10.") == ""


def test_freshness_class_v_zero_line_never_warns():
    assert _fw("Given: tools/dispatch_gate.py:0.") == ""


def test_freshness_class_v_negative_number_not_extracted():
    assert m.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:-5") is None
    assert _fw("Given: tools/dispatch_gate.py:-5.") == ""


def test_freshness_class_v_leading_zeros_parsed_as_int():
    match = m.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:00012")
    assert match.group("n") == "00012"


def test_freshness_class_v_seven_digit_line_number_boundary_extracted():
    # L5 boundary (rule 6a): 7 digits match, 8 do not.
    assert m.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:9999999") is not None


def test_freshness_class_v_eight_digit_line_number_boundary_not_extracted():
    assert m.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:99999999") is None
    assert _fw("Given: tools/dispatch_gate.py:99999999.") == ""


def test_freshness_class_v_double_colon_form_only_first_pair():
    match = m.FRESHNESS_LINE_ANCHOR_RE.search("tools/dispatch_gate.py:12:34")
    assert match is not None
    assert match.group(0) == "tools/dispatch_gate.py:12"
    assert match.group("m") is None


# --- region awareness: the DoD's required negative control (a stale
# anchor in a test fixture -> WARN) plus fenced/blockquote suppression
# and the "fence with a declaration twin does not count" requirement.
# =======================================================================


def test_freshness_class_v_negative_control_stale_anchor_warns(tmp_path):
    """DoD item 4's required negative control: a deliberately STALE
    anchor (pointing well past a real fixture file's actual line
    count) triggers FRESHNESS WARN. Positive-control companion:
    test_freshness_class_v_within_bounds_no_warn above proves the same
    call is silent on a FRESH anchor -- the WARN above is not just
    "always fires"."""
    fixture = tmp_path / "stale_fixture.py"
    fixture.write_text("line1\nline2\nline3\n", encoding="utf-8")
    warn = _fw(f"Given: {fixture}:9999.", cwd=str(tmp_path))
    assert "FRESHNESS WARN:" in warn
    assert str(fixture) in warn


def test_freshness_class_v_fenced_quote_suppresses_warn():
    prompt = "text\n```\ntools/dispatch_gate.py:9999999\n```\nend"
    assert _fw(prompt) == ""


def test_freshness_class_v_blockquote_suppresses_warn():
    prompt = "> tools/dispatch_gate.py:9999999\nordinary text"
    assert _fw(prompt) == ""


def test_freshness_class_v_inline_code_backtick_still_warns():
    prompt = "see `tools/dispatch_gate.py:9999999` here"
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_class_v_unterminated_fence_reads_as_prose():
    prompt = "```\ntools/dispatch_gate.py:9999999\nno closing fence"
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_class_v_quoted_and_prose_occurrence_still_checked():
    prompt = (
        "```\ntools/dispatch_gate.py:9999999\n```\n"
        "and again: tools/dispatch_gate.py:9999999 in prose"
    )
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_fence_with_declaration_twin_does_not_count():
    """DoD item 5's fence-with-a-declaration-twin requirement, applied
    to FRESHNESS: a fenced EXAMPLE that carries a stale-looking anchor
    identical in shape to a real declaration must not, by itself,
    trigger a WARN when the ONLY occurrence is inside the fence --
    same test as fenced-suppression above, named explicitly against
    the DoD wording."""
    prompt = (
        "Example of a stale-anchor WARN for illustration:\n"
        "```\n"
        "FRESHNESS WARN: tools/dispatch_gate.py:9999999 points past EOF\n"
        "```\n"
        "This is just documentation, not a real anchor reference."
    )
    assert _fw(prompt) == ""


# --- summary threshold (20 vs. 21) ------------------------------------


def test_freshness_class_v_summary_threshold_boundary_20_vs_21():
    # 20/21 DISTINCT bounds violations on the SAME real, existing file
    # (M3 needs an EXISTING file -- a fake path is silently skipped as
    # missing, never a hit at all). L5 caps line numbers at 7 digits --
    # stay well under the 9999999/10000000 rollover tested separately.
    real = "tools/dispatch_gate.py"
    prompt_20 = " ".join(f"{real}:{9999900 + i}" for i in range(20))
    prompt_21 = " ".join(f"{real}:{9999900 + i}" for i in range(21))
    warn_20 = _fw(prompt_20)
    warn_21 = _fw(prompt_21)
    assert "FRESHNESS WARN:" in warn_20
    assert "first 3" not in warn_20
    assert "21 file:line anchors" in warn_21
    assert "first 3" in warn_21


# --- per-file / per-call budget boundaries (introduced limits get a
# test AT and BEYOND, rule 6a). -----------------------------------------


def test_freshness_class_v_file_size_limit_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "_FRESHNESS_MAX_FILE_BYTES", 5)
    f_at = tmp_path / "at.py"
    f_over = tmp_path / "over.py"
    f_at.write_bytes(b"a" * 5)
    f_over.write_bytes(b"a" * 6)
    warn_at = _fw(f"{f_at}:100", cwd=str(tmp_path))
    warn_over = _fw(f"{f_over}:100", cwd=str(tmp_path))
    assert "FRESHNESS WARN:" in warn_at  # exactly AT the limit -- still read
    assert warn_over == ""  # beyond the limit -- silent


def test_freshness_class_v_files_per_call_limit_boundary(tmp_path):
    files = []
    for i in range(9):
        fp = tmp_path / f"f{i}.py"
        fp.write_text("x\n", encoding="utf-8")
        files.append(fp)
    prompt = " ".join(f"{fp}:100" for fp in files)
    warn = _fw(prompt, cwd=str(tmp_path))
    for fp in files[:8]:
        assert str(fp) in warn
    assert str(files[8]) not in warn  # 9th file over budget -- silent, not mentioned


# --- L3 boundary: a prompt over the max-chars limit stays silent
# without reading the disk. -------------------------------------------


def test_freshness_l3_boundary_exactly_300000_still_scans():
    padding = "x" * (300_000 - len("Given: tools/dispatch_gate.py:9999999."))
    prompt = "Given: tools/dispatch_gate.py:9999999." + padding
    assert len(prompt) == 300_000
    assert "FRESHNESS WARN:" in _fw(prompt)


def test_freshness_l3_boundary_300001_layer_silent_no_disk(monkeypatch):
    calls = {"n": 0}
    real_open = open

    def counting_open(*args, **kwargs):
        calls["n"] += 1
        return real_open(*args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)
    padding = "x" * (300_001 - len("Given: tools/dispatch_gate.py:9999999."))
    prompt = "Given: tools/dispatch_gate.py:9999999." + padding
    assert len(prompt) == 300_001
    assert _fw(prompt) == ""
    assert calls["n"] == 0


# --- class (a) is NOT ported this increment: a "check NN(x)"-shaped
# reference is simply never extracted -- silent, not a crash, and NOT
# mistaken for class (v). This is the DoD's "on a tree with no staff
# carriers the layer stays silent, not falling over" requirement,
# demonstrated directly: this kit's own calibration protocol carries
# no machine-readable CHK anchors at all (0 occurrences, measured),
# and the layer never even tries to read it for class (a) -- there is
# no code path to read it on.
# =======================================================================


def test_freshness_class_a_check_reference_not_extracted_no_crash():
    assert not hasattr(m, "FRESHNESS_CHECK_TOKEN_RE")
    warn = _fw("see check 12(a) of the calibration protocol for details")
    assert warn == ""


def test_freshness_silent_on_tree_with_no_staff_carriers(tmp_path):
    """A cwd with NONE of the staff twin's carrier files (no tools/,
    no PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md) -- class (v) needs
    nothing but a path and a line count, so it stays correctly SILENT
    (the anchor's target file genuinely doesn't exist under this root)
    rather than raising."""
    warn = _fw("Given: tools/dispatch_gate.py:9999999.", cwd=str(tmp_path))
    assert warn == ""


def test_freshness_huge_prompt_with_many_anchors_under_5s():
    prompt = " ".join(f"tools/fake_perf_{i}.py:9999999" for i in range(500))
    start = time.monotonic()
    warn = _fw(prompt)
    elapsed = time.monotonic() - start
    assert elapsed < 5.0, f"took {elapsed:.2f}s"
    assert warn == ""  # none of these 500 fake files exist -- all silent
