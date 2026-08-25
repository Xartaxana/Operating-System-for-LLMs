"""Tests for tools/mechanism_gate.py -- the axis-block gate of CLAUDE.md
rule 10(b).

Axis heading/answer/skip vocabulary is English here ("## Axis N",
"axis N: ...", "axes: not a mechanism (...)") to match this template's
own docs/SIBLING_MAP.md and CLAUDE.md rule 10 -- verified empirically
against toolkit/docs/SIBLING_MAP.md's real headings before choosing
this vocabulary (the source deployment's Russian regexes matched zero
axes against this template's own map).
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import mechanism_gate as mg

MAP_SAMPLE = """# Sibling Map
## Axis 1 -- Deployments
...
## Axis 2 -- Contours
...
## Axis 6 -- Internal axes
...
## Checking the map itself
"""

# A config with a Claude binding (matching this template's own
# delegation.config.yaml) and one with a non-Claude binding.
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

CONFIG_SAMPLE_NON_CLAUDE = """
roles:
  lead:
    subscription:
      model:
    api:
      provider: groq
      model: llama-3.3-70b-versatile
      api_key_env: GROQ_API_KEY
"""

# A config with a Lead binding on opus -- used by the ladder tests
# below to exercise a Lead binding other than fable/non-Claude.
CONFIG_SAMPLE_OPUS = """
roles:
  lead:
    subscription:
      model: claude-opus-5
    api:
      provider:
      model:
      api_key_env:
"""


def test_parse_axes_follows_the_map_not_a_constant():
    # Axis count and numbers come from the map on every run; a gap in
    # numbering (2 -> 6) doesn't break the parser.
    assert mg.parse_axes(MAP_SAMPLE) == [1, 2, 6]
    assert mg.parse_axes("# empty\n") == []


def test_mechanism_paths_filters_prefixes_with_boundary():
    staged = ["CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
              ".claude/agents/scout.md", "gateway/metrics.py",
              "docs/RELATED_WORK.md", "logs/routing-log.jsonl"]
    assert mg.mechanism_paths(staged) == [
        "CLAUDE.md", "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        ".claude/agents/scout.md"]
    # Prefix boundary: file prefixes match exactly, not as a substring.
    assert mg.mechanism_paths(["CLAUDE.md.bak", "DECISIONS.md.orig",
                               "gateway/metrics.py"]) == []


def test_mechanism_paths_template_homes_and_self_protection():
    # Template MECHANISM_PREFIXES: known mechanism homes + self-protection
    # of the enforcement chain (this gate, the SessionStart hook it shares
    # a home with, the hooks dir, the hook registration file).
    extra = ["BOOT.md", "tools/mechanism_gate.py", "tools/session_context.py",
             ".githooks/commit-msg", ".claude/settings.json"]
    assert mg.mechanism_paths(extra) == extra
    # Narrowness is deliberate (ported from the source deployment):
    # other tools/ and gateway/ files stay outside the net.
    assert mg.mechanism_paths(["tools/usage_report.py",
                               "tools/test_mechanism_gate.py",
                               "gateway/config.yaml",
                               ".claude/settings.local.json",
                               "BOOT.md.bak"]) == []


def test_mechanism_prefixes_covers_the_three_ported_hooks():
    # The three hooks ported in the same batch (claim_control_gate.py /
    # search_control_gate.py / negative_lint.py) are named in the net --
    # entered AHEAD of the Lead's own wiring move (see the TEMPORAL
    # fixture test below), so the net stays green in BOTH worlds
    # (before and after .claude/settings.json actually wires them in).
    assert "tools/claim_control_gate.py" in mg.MECHANISM_PREFIXES
    assert "tools/search_control_gate.py" in mg.MECHANISM_PREFIXES
    assert "tools/negative_lint.py" in mg.MECHANISM_PREFIXES


# --- TEMPORAL: the net vs the live wiring -----------------------------
# The three ported hooks are NOT wired into the live .claude/settings.json
# yet (Lead's own move, at acceptance) -- entering them into
# MECHANISM_PREFIXES ahead of that move must not be dead weight, nor a
# false negative once the wiring lands. A FIXTURE settings.json (not the
# live file) stands in for "the world after Lead's wiring move" -- 12
# hook commands, fully covered by the net -- proving the net already
# covers the post-wiring world today, independent of whether the wiring
# move has happened yet.

_FIXTURE_SETTINGS_12_COMMANDS = {
    "hooks": {
        "SessionStart": [
            {"hooks": [{"type": "command", "command": "python tools/session_context.py"}]}
        ],
        "PreToolUse": [
            {
                "matcher": "Task|Agent",
                "hooks": [
                    {"type": "command", "command": "python tools/dispatch_gate.py"},
                    {"type": "command", "command": "python tools/critic_snapshot.py"},
                    {"type": "command", "command": "python tools/owns_gate.py"},
                ],
            },
            {
                "matcher": "Bash|PowerShell",
                "hooks": [{"type": "command", "command": "python tools/hygiene_gate.py"}],
            },
            {
                "matcher": "Edit|Write",
                "hooks": [{"type": "command", "command": "python tools/claim_control_gate.py"}],
            },
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell",
                "hooks": [
                    {"type": "command", "command": "python tools/dod_track.py"},
                    {"type": "command", "command": "python tools/journal_echo.py"},
                ],
            },
            {
                "matcher": "Bash|PowerShell|Grep|Glob|Read",
                "hooks": [{"type": "command", "command": "python tools/search_control_gate.py"}],
            },
            {
                "matcher": "Task|Agent",
                "hooks": [{"type": "command", "command": "python tools/negative_lint.py"}],
            },
        ],
        "SubagentStop": [
            {"hooks": [{"type": "command", "command": "python tools/dod_gate.py"}]}
        ],
        "Stop": [
            {"hooks": [{"type": "command", "command": "python tools/main_gate.py"}]}
        ],
    }
}


def _fixture_hook_commands(settings_data):
    commands = []
    for _event, groups in settings_data.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                if hook.get("type") == "command":
                    commands.append(hook["command"])
    return commands


def test_temporal_fixture_12_command_settings_fully_covered_by_net_pre_wiring():
    # WORLD A ("before" -- the wiring has not landed on the live file
    # yet, exercised here purely as a synthetic fixture): the net must
    # already cover every one of these 12 commands even though the live
    # .claude/settings.json does not reference the three new hooks yet
    # -- this is what "entered ahead of the wiring move" means in
    # practice.
    commands = _fixture_hook_commands(_FIXTURE_SETTINGS_12_COMMANDS)
    assert len(commands) == 12
    tool_paths = [c.split(" ", 1)[1] for c in commands]  # "python X" -> "X"
    uncovered = [p for p in tool_paths
                 if not any(mg._matches(p, pref) for pref in mg.MECHANISM_PREFIXES)]
    assert not uncovered, f"fixture commands outside the net: {uncovered}"


def test_temporal_fixture_12_command_settings_fully_covered_by_net_post_wiring():
    # WORLD B ("after" -- Lead has wired the three hooks into the live
    # file): the SAME fixture and the SAME net -- no change is needed
    # to MECHANISM_PREFIXES once the wiring move happens, proving the
    # net was entered correctly ahead of time rather than reactively.
    commands = _fixture_hook_commands(_FIXTURE_SETTINGS_12_COMMANDS)
    tool_paths = [c.split(" ", 1)[1] for c in commands]
    uncovered = [p for p in tool_paths
                 if not any(mg._matches(p, pref) for pref in mg.MECHANISM_PREFIXES)]
    assert not uncovered


def test_find_missing_reports_absent_axes_case_insensitive():
    text = "axis 1: covered -- CLAUDE.md both deployments\nAxis 2: n/a (no money involved)\n"
    assert mg.find_missing(text, [1, 2, 6]) == [6]
    assert mg.find_missing(text + "axis 6: queued (next touch)\n", [1, 2, 6]) == []
    # Digit boundary: "axis 15:" does not close axis 1.
    assert mg.find_missing("axis 15: covered\n", [1]) == [1]


def test_prose_answer_is_not_an_answer():
    # Recall-prose "axes are covered" does not satisfy the enumeration format.
    assert mg.find_missing("all axes are covered, checked", [1, 2]) == [1, 2]


def test_decide_skip_only_from_commit_message():
    # A skip line quoted in the DIFF (decision text) does NOT bypass the
    # gate; only the commit message counts.
    code, reason = mg.decide(
        msg="feat: mechanism X",
        block_extra="+ ... legal via the line \"axes: not a mechanism (<reason>)\" ...",
        staged=["CLAUDE.md"], map_text="## Axis 1 -- Deployments\n")
    assert code == 1 and "1" in reason
    code, _ = mg.decide(
        msg="docs: typo fix\n\naxes: not a mechanism (typo in rule 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 -- Deployments\n")
    assert code == 0


def test_decide_block_counted_from_message_and_decisions_diff_only():
    # Unrelated staged content does not close axes -- decide() receives
    # the diff of ONLY DECISIONS_FULL (here: DECISIONS.md), main() calls
    # it that way.
    code, _ = mg.decide(
        msg="feat: mechanism X\n\naxis 1: covered -- both deployments",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0
    code, _ = mg.decide(
        msg="feat: mechanism X",
        block_extra="+axis 1: covered -- both deployments (decision text)",
        staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


def test_decide_merge_and_non_mechanism_commits_pass():
    # Merge commits are not blocked -- merged commits already passed the
    # gate individually.
    code, _ = mg.decide(msg="Merge branch 'x'", block_extra="",
                        staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
                        merging=True)
    assert code == 0
    code, _ = mg.decide(msg="chore: telemetry", block_extra="",
                        staged=["gateway/metrics.py", "logs/routing-log.jsonl"],
                        map_text="## Axis 1 --\n")
    assert code == 0


def test_decide_fails_closed_without_map_or_axes():
    code, reason = mg.decide(msg="feat: X", block_extra="",
                             staged=["CLAUDE.md"], map_text=None)
    assert code == 1 and "fail-closed" in reason
    code, reason = mg.decide(msg="feat: X", block_extra="",
                             staged=["CLAUDE.md"], map_text="# map without axes\n")
    assert code == 1 and "fail-closed" in reason


def test_explicit_skip_line_matches():
    assert mg.SKIP_RE.search("axes: not a mechanism (typo fix in CLAUDE.md)")
    assert mg.SKIP_RE.search("Axes: not a mechanism (archival reshuffle)")
    assert not mg.SKIP_RE.search("axes are covered by not a mechanism")


# --- SKIP_RE line anchor -------------------------------------------------
# Contrast: TIER_LINE_RE was already anchored ^...$ MULTILINE; SKIP_RE was
# fail-open -- an unanchored .search() matched an inline quote of the
# skip syntax in the middle of commit-message prose, silencing the gate.


def test_skip_re_standalone_line_in_multiline_message():
    # (1) a standalone line inside a multi-line message -> active.
    msg = "feat: mechanism X\n\naxes: not a mechanism (reason)\n\nmore text\n"
    assert mg.SKIP_RE.search(msg)


def test_skip_re_standalone_line_with_space_indent():
    # (2) the same line indented with spaces -> active.
    msg = "feat: mechanism X\n\n   axes: not a mechanism (indented reason)\n"
    assert mg.SKIP_RE.search(msg)


def test_skip_re_inline_quote_mid_sentence_does_not_match():
    # (3) an inline quote in the middle of a sentence -> NOT active.
    msg = ("feat: mechanism X\n\nthe line \"axes: not a mechanism (example)\" "
           "would bypass the gate without the anchor\n")
    assert not mg.SKIP_RE.search(msg)


def test_skip_re_line_starting_with_guillemet_does_not_match():
    # (4) a line starting with a guillemet quote character -> NOT active
    # (a non-whitespace char precedes "axes", the ^\s* anchor rejects it).
    msg = "feat: mechanism X\n\n«axes: not a mechanism (example)»\n"
    assert not mg.SKIP_RE.search(msg)


def test_skip_re_line_starting_with_straight_quote_does_not_match():
    # (5) a line starting with a straight quote " -> NOT active.
    msg = 'feat: mechanism X\n\n"axes: not a mechanism (example)"\n'
    assert not mg.SKIP_RE.search(msg)


def test_skip_re_matches_on_crlf_message():
    # (6) CRLF message: a standalone line with \r\n endings -> active
    # (MULTILINE's ^ sits right after \n, with no leading \r on the line).
    msg = "feat: mechanism X\r\n\r\naxes: not a mechanism (reason)\r\n"
    assert mg.SKIP_RE.search(msg)


def test_skip_re_first_line_of_message_no_leading_newline_matches():
    # (6b, a sibling deployment's own review found this test gap) the skip line is the
    # VERY FIRST line of the message, with NO leading \n (unlike (1)/(2)/
    # (6) above, where the skip line is preceded by at least one newline)
    # -> active: MULTILINE ^ matches position 0 of the string too, not
    # only the position right after a \n.
    msg = "axes: not a mechanism (reason, no leading text)\n\nmore text\n"
    assert mg.SKIP_RE.search(msg)


def test_decide_first_line_skip_no_leading_newline_passes():
    # (8b, a sibling deployment's own review found this test gap) end-to-end via
    # decide(): the same message (skip line first, no leading \n)
    # actually passes a mechanism-touching commit with no axis block.
    msg = "axes: not a mechanism (typo in rule 3)\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 -- Deployments\n")
    assert code == 0


def test_decide_inline_quote_without_axis_block_blocks():
    # (7) end-to-end via decide(): a mechanism staged path, a message with
    # an INLINE quote of the skip syntax and NO axis block -> the gate
    # BLOCKS (code 1) -- the quote does not activate skip.
    msg = ("feat: mechanism X\n\nthe line \"axes: not a mechanism (example)\" "
           "would bypass the gate\n")
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                             map_text="## Axis 1 -- Deployments\n")
    assert code == 1 and "1" in reason


def test_decide_standalone_skip_line_passes():
    # (8) end-to-end: a real skip line as its own standalone line -> code 0.
    msg = "docs: typo fix\n\naxes: not a mechanism (typo in rule 3)\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 -- Deployments\n")
    assert code == 0


# --- Region-aware SKIP_RE/TIER_LINE_RE: a fenced/blockquoted line does
# NOT count as a declaration; the SAME line outside a fence DOES --
# a boundary pair per introduced-limit rule (6a): AT the region
# boundary (inside the fence) and BEYOND it (outside the fence).


def test_skip_line_inside_fence_does_not_pass_the_gate():
    # AT the boundary: the skip line's own position is fenced -> filtered
    # out, the gate still requires a real axis block -> code 1.
    msg = ("docs: showing the reader an example\n\n"
           "```\naxes: not a mechanism (example syntax for docs)\n```\n")
    code, reason = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                             map_text="## Axis 1 -- Deployments\n")
    assert code == 1
    assert "fail-closed" not in reason  # map exists -- rejected on the axis block, not the map
    assert "axis block is incomplete" in reason


def test_skip_line_outside_fence_passes_the_gate():
    # BEYOND the boundary: the identical text, NOT inside a fence -> counts,
    # code 0. Same message shape as the fenced case above, minus the fence.
    msg = "docs: showing the reader an example\n\naxes: not a mechanism (example syntax for docs)\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 -- Deployments\n")
    assert code == 0


def test_tier_line_inside_fence_gives_no_tier_line_error_not_pass():
    # AT the boundary: a tier line fenced as a format example -> filtered
    # out -> "No tier line" (not a silent pass, not "Not lead tier").
    msg = ("feat: mechanism X\n\naxis 1: covered\n"
           "Example of the declaration format:\n```\ntier: fable\n```\n")
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "No \"tier:" in reason


def test_tier_line_outside_fence_passes():
    # BEYOND the boundary: the identical tier line, NOT fenced -> counts,
    # matches the fable default binding -> code 0.
    msg = "feat: mechanism X\n\naxis 1: covered\ntier: fable\n"
    code, _ = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0


def test_fenced_wrong_tier_spoofer_ignored_missing_real_line_still_rejects():
    # ALL-MUST-PASS counts only UNQUOTED tier lines: a fenced line with a
    # deliberately WRONG value ("sonnet", binding defaults to fable) sits
    # next to the ABSENCE of any real prose tier line -- the fenced
    # spoofer is dropped from consideration entirely -> "No tier line"
    # (not "Not lead tier": the spoofer never entered the checked list).
    msg = ("feat: mechanism X\n\naxis 1: covered\n"
           "Format example (for documentation):\n```\ntier: sonnet\n```\n")
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "No \"tier:" in reason
    assert "Not lead tier" not in reason


def test_fenced_wrong_spoofer_beside_real_correct_prose_line_passes():
    # The same fenced wrong-value line, but a REAL correct prose tier line
    # is ALSO present -- the fenced spoofer is filtered out, only the real
    # prose line is checked, and it matches -> code 0.
    msg = ("feat: mechanism X\n\naxis 1: covered\n"
           "Format example (for documentation):\n```\ntier: sonnet\n```\n"
           "tier: fable\n")
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0, reason


def test_axis_line_inside_fence_still_counts_documented_non_goal():
    # Deliberate non-goal (see module docstring "AXIS LINES ARE NOT
    # FILTERED"): an axis line INSIDE a fence still closes the axis --
    # find_missing() is region-blind by design, not a gap.
    msg = "feat: mechanism X\n\n```\naxis 1: covered -- both deployments\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 --\n")
    assert code == 0


def test_block_extra_fenced_axis_text_not_region_scanned_documented_non_goal():
    # block_extra is never region-scanned (see module docstring "block_extra
    # IS NEVER REGION-SCANNED") -- a fence-shaped diff text with an axis
    # line still closes the axis via find_missing(), unaffected by region.
    code, _ = mg.decide(
        msg="feat: mechanism X", block_extra="+```\n+axis 1: covered\n+```\n",
        staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert code == 0


def test_scan_not_called_on_non_mechanism_commit(monkeypatch):
    # Laziness (I-1): zero scan() calls when the commit doesn't touch any
    # mechanism path -- the hits branch returns before _maybe_scan runs.
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


def test_scan_not_called_without_marker_hint(monkeypatch):
    # Laziness (I-1): no "axes"/"tier" literal in the message -> no scan
    # call, even with region marker characters present.
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide(msg="feat: X\n> just a quote with no keywords `code`\n",
              block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert calls["n"] == 0


def test_scan_not_called_without_region_marker_chars(monkeypatch):
    # Laziness (I-1): the message has a marker hint but no "`>~" at all ->
    # no scan call (md_regions would deterministically say "all prose").
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    mg.decide(msg="feat: X\n\naxis 1: covered\ntier: fable\n",  # no `>~ at all
              block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n")
    assert calls["n"] == 0


def test_scan_called_exactly_once_per_decide_full_call(monkeypatch):
    # Laziness (I-1): ONE scan() call for the whole decide_full(), reused
    # by both the skip check and the tier check.
    calls = {"n": 0}
    real_scan = mg.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(mg, "scan", _counting)
    msg = "feat: X\n\naxis 1: covered\n```\ntier: fable\n```\ntier: fable\n"
    mg.decide_full(msg=msg, block_extra="", staged=["CLAUDE.md"],
                    map_text="## Axis 1 --\n", config_text=None)
    assert calls["n"] == 1


def test_scan_failure_falls_back_to_pre_region_quoted_skip_silences_gate(monkeypatch):
    # Fail-open (see module docstring "FAIL-OPEN ON SCANNER FAILURE"): if
    # scan() raises, the region filter becomes a no-op -- the quoted skip
    # line silences the gate again (the same residual gap the pre-region
    # gate always had), NOT a new code path.
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(mg, "scan", _broken_scan)
    msg = "docs: example\n\n```\naxes: not a mechanism (example)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 -- Deployments\n")
    assert code == 0


def test_scan_degraded_falls_back_to_pre_region_quoted_skip_silences_gate(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(mg, "scan", lambda text: _FakeResult())
    msg = "docs: example\n\n```\naxes: not a mechanism (example)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 -- Deployments\n")
    assert code == 0


def test_scan_module_absent_falls_back_to_pre_region_quoted_skip_silences_gate(monkeypatch):
    monkeypatch.setattr(mg, "scan", None)
    msg = "docs: example\n\n```\naxes: not a mechanism (example)\n```\n"
    code, _ = mg.decide(msg=msg, block_extra="", staged=["CLAUDE.md"],
                        map_text="## Axis 1 -- Deployments\n")
    assert code == 0


# --- Tier declaration on the "mechanism" branch ---------------------------

def test_resolve_lead_binding_defaults_to_fable_without_config():
    assert mg.resolve_lead_binding(None) == "fable"
    assert mg.resolve_lead_binding("roles: {}\n") == "fable"
    assert mg.resolve_lead_binding("not: yaml: [broken\n") == "fable"


def test_resolve_lead_binding_reads_subscription_model():
    assert mg.resolve_lead_binding(CONFIG_SAMPLE) == "claude-fable-5"


def test_resolve_lead_binding_falls_back_to_api_for_non_claude():
    assert (mg.resolve_lead_binding(CONFIG_SAMPLE_NON_CLAUDE)
            == "llama-3.3-70b-versatile")


def test_tier_declared_ok_exact_and_family_vs_non_claude():
    assert mg.tier_declared_ok("claude-fable-5", "claude-fable-5")
    assert mg.tier_declared_ok("fable", "claude-fable-5")
    assert not mg.tier_declared_ok("sonnet", "claude-fable-5")
    # Non-Claude binding: no family, only an exact match qualifies.
    assert mg.tier_declared_ok("llama-3.3-70b-versatile",
                               "llama-3.3-70b-versatile")
    assert not mg.tier_declared_ok("fable", "llama-3.3-70b-versatile")


# --- config onboarding ladder (build_role_ladder / _resolve_ladder_rank /
# tier_declared_ok config_text) -- a full mirror of HQ's own gate logic.

CONFIG_LADDER_NON_CLAUDE = """
roles:
  critic:
    subscription:
      model: gpt-x
  lead:
    subscription:
      model: llama-3.3-70b-versatile
"""

CONFIG_LADDER_NON_CLAUDE_WITH_RESERVE = """
roles:
  lead:
    subscription:
      model: llama-3.3-70b-versatile
  reserve:
    subscription:
      model: claude-fable-5
"""

CONFIG_LADDER_OPUS_LEAD_FABLE_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: claude-fable-5
"""

CONFIG_LADDER_AMBIGUOUS_FAMILY = """
roles:
  critic:
    subscription:
      model: claude-critic-opus-x
  reserve:
    subscription:
      model: claude-reserve-opus-y
  lead:
    subscription:
      model: llama-3.3-70b-versatile
"""

CONFIG_LADDER_WITH_NON_COORD_ROLES = """
roles:
  scout:
    subscription:
      model: claude-haiku-3
  builder:
    subscription:
      model: claude-sonnet-5
  critic:
    subscription:
      model: claude-opus-4
  lead:
    subscription:
      model: claude-opus-5
  judge:
    subscription:
      model: claude-judge-model
  analyst:
    subscription:
      model: claude-analyst-model
  designer:
    subscription:
      model: claude-designer-model
"""


def test_build_role_ladder_fixed_order_and_ranks():
    ladder = mg.build_role_ladder(CONFIG_LADDER_WITH_NON_COORD_ROLES)
    assert ladder == [
        (0, "claude-haiku-3"),
        (1, "claude-sonnet-5"),
        (2, "claude-opus-4"),
        (3, "claude-opus-5"),
    ]


def test_build_role_ladder_ignores_judge_and_analyst():
    ladder = mg.build_role_ladder(CONFIG_LADDER_WITH_NON_COORD_ROLES)
    ids = [model_id for _rank, model_id in ladder]
    assert "claude-judge-model" not in ids
    assert "claude-analyst-model" not in ids


def test_build_role_ladder_ignores_designer():
    # designer -- a standing function at the same tier as critic
    # (opus), but NOT a coordination rung of the ladder (roles.designer
    # is not in ROLE_RANKS) -- the same treatment as judge/analyst above.
    ladder = mg.build_role_ladder(CONFIG_LADDER_WITH_NON_COORD_ROLES)
    ids = [model_id for _rank, model_id in ladder]
    assert "claude-designer-model" not in ids
    assert len(ladder) == 4  # scout/builder/critic/lead only


def test_build_role_ladder_role_without_model_no_rung():
    # roles.reserve is present as a key, but with no model -- no rung.
    config = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model:
"""
    assert mg.build_role_ladder(config) == [(3, "claude-opus-5")]


def test_build_role_ladder_empty_without_config():
    assert mg.build_role_ladder(None) == []
    assert mg.build_role_ladder("") == []
    assert mg.build_role_ladder("not: yaml: [broken\n") == []


def test_tier_declared_ok_non_claude_ladder_exact_id_lead_passes():
    # A non-Claude LADDER: lead=llama-3.3-70b-versatile, critic=gpt-x --
    # an EXACT-id declaration of the lead rung passes.
    assert mg.tier_declared_ok(
        "llama-3.3-70b-versatile", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE)


def test_tier_declared_ok_non_claude_ladder_lower_rung_fails():
    # The same ladder -- a declaration of the critic rung (BELOW lead)
    # does not pass.
    assert not mg.tier_declared_ok(
        "gpt-x", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE)


def test_tier_declared_ok_reserve_exact_id_passes_at_non_claude_lead():
    # reserve=claude-fable-5 at a non-Claude lead -- an EXACT-id
    # declaration of the reserve rung (STRICTLY ABOVE lead) passes.
    assert mg.tier_declared_ok(
        "claude-fable-5", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE_WITH_RESERVE)


def test_tier_declared_ok_reserve_family_match_passes_at_non_claude_lead():
    # The same config -- a declaration of "fable" (a bare family, a
    # family match of EXACTLY ONE reserve rung) also passes.
    assert mg.tier_declared_ok(
        "fable", "llama-3.3-70b-versatile", CONFIG_LADDER_NON_CLAUDE_WITH_RESERVE)


def test_tier_declared_ok_real_shape_opus_lead_fable_reserve_passes():
    # The real shape (lead: claude-opus-5, reserve: claude-fable-5) --
    # "tier: fable" passes.
    assert mg.tier_declared_ok(
        "fable", "claude-opus-5", CONFIG_LADDER_OPUS_LEAD_FABLE_RESERVE)


def test_tier_declared_ok_no_reserve_tier_fable_still_passes_via_p2():
    # BOUNDARY (TEMPORAL, the current toolkit's own config): roles.reserve
    # is absent -- the ladder has no rung 4 at all -- "tier: fable" at
    # an opus-lead still passes, now via the FAMILY-STRICTLY-ABOVE-
    # BINDING branch of tier_declared_ok (fable's rank, index 0 in
    # LEAD_FAMILIES, is strictly above opus's rank, index 1) -- a full
    # mirror of HQ's own gate logic, not gated on roles.reserve
    # actually being configured.
    ladder = mg.build_role_ladder(CONFIG_SAMPLE_OPUS)
    assert all(rank != 4 for rank, _model in ladder)
    assert mg.tier_declared_ok("fable", "claude-opus-5", CONFIG_SAMPLE_OPUS)


# --- family-strictly-above-binding pair:
# above the binding passes, below the binding is rejected -- both
# forms explicit, not only inferred from the P2 test above.


def test_tier_declared_ok_family_above_binding_passes():
    # Binding opus, declaration fable (both the bare family and the
    # full model id) -- fable's rank (0) is STRICTLY ABOVE opus's rank
    # (1) -- accepted.
    assert mg.tier_declared_ok("fable", "claude-opus-5")
    assert mg.tier_declared_ok("claude-fable-5", "claude-opus-5")


def test_tier_declared_ok_family_below_binding_fails():
    # The same opus binding, a declaration BELOW it (sonnet/haiku) --
    # rejected.
    assert not mg.tier_declared_ok("sonnet", "claude-opus-5")
    assert not mg.tier_declared_ok("haiku", "claude-opus-5")


def test_tier_declared_ok_fable_binding_nothing_above_regression_pin():
    # BOUNDARY: a fable binding -- the "nothing above fable" regression
    # pin. fable's rank is already 0 (no smaller index exists), so a
    # declaration of opus/anything else still does not pass through
    # this branch (unchanged behavior).
    assert not mg.tier_declared_ok("opus", "claude-fable-5")
    assert not mg.tier_declared_ok("sonnet", "claude-fable-5")


def test_tier_declared_ok_non_claude_binding_unaffected_by_new_branch():
    # A non-Claude binding (fam(binding) is None) -- the function
    # returns False before this branch is even reached, regression pin.
    assert not mg.tier_declared_ok("fable", "llama-3.3-70b-versatile")


def test_tier_declared_ok_non_claude_declaration_does_not_match_higher_family():
    # The other edge of the new branch: a Claude binding (opus), but a
    # NON-CLAUDE declaration (declared_fam is None) -- this branch does
    # not match at all, fail-closed (only an exact match qualifies).
    assert not mg.tier_declared_ok("llama-3.3-70b-versatile", "claude-opus-5")


def test_decide_full_lead_binding_opus_tier_fable_passes():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE_OPUS)
    assert code == 0


def test_decide_full_lead_binding_opus_tier_sonnet_fails():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE_OPUS)
    assert code == 1
    assert "Not lead tier" in reason


def test_decide_full_lead_binding_fable_tier_opus_fails():
    # Regression pin: a fable binding -- "above" it does not exist,
    # "tier: opus" (below fable) is still rejected.
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: opus",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE)
    assert code == 1
    assert "Not lead tier" in reason


def test_decide_full_lead_binding_non_claude_tier_fable_fails():
    # Regression pin: a non-Claude binding -- a declaration higher by
    # rank does not save it (the branch is silent for fam(binding) is
    # None).
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE_NON_CLAUDE)
    assert code == 1
    assert "Not lead tier" in reason


def test_tier_declared_ok_ambiguous_family_match_does_not_resolve():
    # BOUNDARY (a documented fork): TWO rungs of the same Claude family
    # (critic and reserve, both "opus") -- the bare family "opus" does
    # NOT resolve via the ladder (ambiguity), and the binding (lead) is
    # non-Claude, so the family-substring branch is silent too -- the
    # result is FAIL.
    assert not mg.tier_declared_ok(
        "opus", "llama-3.3-70b-versatile", CONFIG_LADDER_AMBIGUOUS_FAMILY)


def test_tier_declared_ok_no_config_regression_pin_explicit_none():
    # Regression pin (config_text=None EXPLICITLY, not relying on a
    # real file): behaves exactly as before this port.
    assert mg.tier_declared_ok("claude-fable-5", "claude-fable-5", None)
    assert mg.tier_declared_ok("fable", "claude-fable-5", None)
    assert not mg.tier_declared_ok("sonnet", "claude-fable-5", None)


def test_decide_full_ladder_non_claude_lead_tier_exact_id_passes():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered -- both deployments\ntier: llama-3.3-70b-versatile",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_LADDER_NON_CLAUDE)
    assert code == 0


def test_decide_full_ladder_non_claude_lead_tier_lower_rung_fails():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered -- both deployments\ntier: gpt-x",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_LADDER_NON_CLAUDE)
    assert code == 1
    assert "Not lead tier" in reason


# --- family-strength guard on the ladder (BOTH the exact-id path and
# the family-match path) -- a nonsense config (a rung positionally
# above lead but weaker by family) must not silently resolve.

CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: claude-sonnet-5
"""

CONFIG_LADDER_NO_LEAD_RESERVE_OPUS = """
roles:
  reserve:
    subscription:
      model: claude-opus-5
"""

CONFIG_LADDER_DUPLICATE_MODEL_ID = """
roles:
  builder:
    subscription:
      model: claude-fable-5
  lead:
    subscription:
      model: llama-3.3-70b-versatile
  reserve:
    subscription:
      model: claude-fable-5
"""


def test_resolve_ladder_rank_nonsense_reserve_below_lead_family_does_not_resolve():
    # reserve is configured with a model WEAKER than lead (sonnet <
    # opus by LEAD_FAMILIES) -- positionally reserve is rung 4, but the
    # family match does NOT resolve at all.
    assert mg._resolve_ladder_rank("sonnet", CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD) is None


def test_tier_declared_ok_nonsense_reserve_below_lead_tier_sonnet_fails():
    assert not mg.tier_declared_ok(
        "sonnet", "claude-opus-5", CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD)


def test_decide_full_nonsense_reserve_below_lead_tier_sonnet_fails():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_LADDER_NONSENSE_RESERVE_BELOW_LEAD)
    assert code == 1
    assert "Not lead tier" in reason


def test_resolve_ladder_rank_no_lead_rung_returns_none_even_with_reserve():
    # roles.lead is ABSENT, reserve=opus is configured -- the ladder
    # path resolves NOTHING (no reference rank), even though "opus"
    # would otherwise exact-match the reserve rung.
    assert mg._resolve_ladder_rank("claude-opus-5", CONFIG_LADDER_NO_LEAD_RESERVE_OPUS) is None
    assert mg._resolve_ladder_rank("opus", CONFIG_LADDER_NO_LEAD_RESERVE_OPUS) is None


def test_tier_declared_ok_no_lead_reserve_opus_tier_opus_fails():
    # The "nothing above fable" pin holds even WITH a config present
    # (not only with config_text=None): roles.lead absent ->
    # resolve_lead_binding defaults to "fable" -- nothing beats fable,
    # neither by the ladder nor by the family branch.
    binding = mg.resolve_lead_binding(CONFIG_LADDER_NO_LEAD_RESERVE_OPUS)
    assert binding == "fable"
    assert not mg.tier_declared_ok("opus", binding, CONFIG_LADDER_NO_LEAD_RESERVE_OPUS)


def test_decide_full_no_lead_reserve_opus_tier_opus_fails():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: opus",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_LADDER_NO_LEAD_RESERVE_OPUS)
    assert code == 1
    assert "Not lead tier" in reason


CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: claude-sonnet-5
"""

CONFIG_LADDER_EXACT_STRONGER_FAMILY_AT_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-sonnet-5
  reserve:
    subscription:
      model: claude-opus-5
"""

CONFIG_LADDER_EXACT_NON_CLAUDE_STEP_AT_RESERVE = """
roles:
  lead:
    subscription:
      model: claude-opus-5
  reserve:
    subscription:
      model: llama-3.3-70b-versatile
"""


def test_resolve_ladder_rank_exact_match_weaker_family_at_reserve_does_not_resolve():
    # A nonsense config: reserve (positionally rung 4, ABOVE lead) is
    # configured with a model WEAKER than lead by family (sonnet <
    # opus) -- an EXACT id match with it no longer resolves at all
    # (the guard applies on this path too, symmetric with the
    # family-match path).
    assert mg._resolve_ladder_rank(
        "claude-sonnet-5", CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE) is None


def test_tier_declared_ok_exact_match_weaker_family_at_reserve_fails():
    assert not mg.tier_declared_ok(
        "claude-sonnet-5", "claude-opus-5", CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE)


def test_decide_full_exact_match_weaker_family_at_reserve_rejects():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: claude-sonnet-5",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_LADDER_EXACT_WEAKER_FAMILY_AT_RESERVE)
    assert code == 1
    assert "Not lead tier" in reason


def test_resolve_ladder_rank_exact_match_stronger_family_at_reserve_still_resolves():
    # Positive control of the same guard: a candidate STRONGER (not
    # weaker) than lead by family -- the guard does NOT discard it, an
    # exact match resolves as before.
    assert mg._resolve_ladder_rank(
        "claude-opus-5", CONFIG_LADDER_EXACT_STRONGER_FAMILY_AT_RESERVE) == 4


def test_resolve_ladder_rank_exact_match_non_claude_step_trusts_ladder_position():
    # The CANDIDATE rung's family is unresolvable (a non-Claude
    # model_id) -- the guard stays silent, TRUSTING THE LADDER'S
    # POSITION -- an exact match resolves (rank 4), as before this fix.
    assert mg._resolve_ladder_rank(
        "llama-3.3-70b-versatile", CONFIG_LADDER_EXACT_NON_CLAUDE_STEP_AT_RESERVE) == 4


def test_tier_declared_ok_exact_match_non_claude_step_trusts_ladder_position_passes():
    assert mg.tier_declared_ok(
        "llama-3.3-70b-versatile", "claude-opus-5", CONFIG_LADDER_EXACT_NON_CLAUDE_STEP_AT_RESERVE)


def test_resolve_ladder_rank_duplicate_model_id_takes_max_rank():
    # The SAME model_id sits on SEVERAL rungs (builder=1 AND reserve=4,
    # both "claude-fable-5") -- resolution takes the MAXIMUM rank among
    # exact matches (4), not the first one in ladder order (1).
    assert mg._resolve_ladder_rank(
        "claude-fable-5", CONFIG_LADDER_DUPLICATE_MODEL_ID) == 4


def test_tier_declared_ok_duplicate_model_id_passes_via_max_rank():
    assert mg.tier_declared_ok(
        "claude-fable-5", "llama-3.3-70b-versatile", CONFIG_LADDER_DUPLICATE_MODEL_ID)


def test_decide_full_duplicate_model_id_tier_fable_passes():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: claude-fable-5",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_LADDER_DUPLICATE_MODEL_ID)
    assert code == 0


def test_decide_full_missing_tier_line_fails():
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered -- both deployments",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "tier" in reason.lower()
    assert "Lead queue" in reason


def test_decide_full_tier_mismatch_fails_with_distinct_text():
    # Default lead binding (no config file) is "fable"; sonnet doesn't fit.
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: sonnet",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "Not lead tier" in reason
    # Distinct from the "missing line" text.
    assert "No \"tier:" not in reason


def test_decide_full_tier_fable_default_passes():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0


def test_decide_full_tier_exact_model_id_passes():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: claude-fable-5",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE)
    assert code == 0


def test_decide_full_skip_line_without_tier_passes():
    code, _ = mg.decide_full(
        msg="docs: typo fix\n\naxes: not a mechanism (typo in rule 3)",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0


def test_decide_full_merge_commit_without_tier_passes():
    code, _ = mg.decide_full(
        msg="Merge branch 'x'", block_extra="", staged=["CLAUDE.md"],
        map_text="## Axis 1 --\n", config_text=None, merging=True)
    assert code == 0


# --- ALL found tier lines must pass, not just the first ---


def test_find_tier_declarations_returns_all_lines_in_order():
    msg = "feat: X\n\ntier: sonnet\n\nSome other text\ntier: fable\n"
    assert mg.find_tier_declarations(msg) == ["sonnet", "fable"]


def test_find_tier_declaration_backward_compat_returns_first():
    msg = "feat: X\n\ntier: sonnet\n\ntier: fable\n"
    assert mg.find_tier_declaration(msg) == "sonnet"


def test_decide_full_first_line_garbage_second_real_still_rejects():
    # A quoted example line "tier: sonnet" (its own line, as if lifted
    # from a docstring example) followed by a REAL "tier: fable" line --
    # chosen semantics (ALL lines must pass) catches the garbage line
    # and rejects, even though a real matching line exists alongside it.
    msg = (
        "feat: mechanism X\n\naxis 1: covered\n\n"
        "Example from the docstring (quoted, its own line):\n"
        "tier: sonnet\n\n"
        "tier: fable\n"
    )
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "Not lead tier" in reason
    assert "sonnet" in reason


def test_decide_full_real_first_garbage_second_still_rejects():
    # Order does not matter -- every found line is checked regardless
    # of position.
    msg = "feat: mechanism X\n\naxis 1: covered\n\ntier: fable\ntier: sonnet\n"
    code, reason = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 1
    assert "Not lead tier" in reason


def test_decide_full_multiple_matching_tier_lines_passes():
    # Several mechanisms in one commit, both lines real and matching
    # the binding -- passes.
    msg = "feat: mechanism X\n\naxis 1: covered\n\ntier: fable\ntier: fable\n"
    code, _ = mg.decide_full(
        msg=msg, block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=None)
    assert code == 0


def test_decide_full_non_claude_lead_requires_exact_match():
    code, _ = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: llama-3.3-70b-versatile",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE_NON_CLAUDE)
    assert code == 0
    code, reason = mg.decide_full(
        msg="feat: mechanism X\n\naxis 1: covered\ntier: fable",
        block_extra="", staged=["CLAUDE.md"], map_text="## Axis 1 --\n",
        config_text=CONFIG_SAMPLE_NON_CLAUDE)
    assert code == 1
    assert "Not lead tier" in reason


# --- A self-closing test: the net must cover EVERYTHING the live
# wiring (.claude/settings.json, .githooks/pre-commit, .githooks/
# commit-msg) actually points at, not just a hand-transcribed list in
# MECHANISM_PREFIXES. Reads the LIVE repository files (not copies, not
# fixtures) -- a drift between the wiring and the net is REAL drift
# that must fail this test loudly, not pass silently.

REPO_ROOT = Path(__file__).resolve().parents[1]  # this template's install root -- same as mg.REPO
LIVE_SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"
LIVE_GITHOOKS_DIR = REPO_ROOT / ".githooks"

# tools/<...>.py -- matches both forward- and backslash path forms,
# stops at the first non-word/path separator (space/quote) -- does not
# chew into a trailing CLI argument.
_TOOL_CMD_RE = re.compile(r"tools[/\\][A-Za-z0-9_.\\/-]+\.py")


def _load_settings(path):
    # A missing/broken live file is NOT a reason to skip the check (see
    # the block comment above): assert/exception fail loudly, not
    # silently.
    assert path.exists(), (
        f"the live {path} was not found -- a self-closing test must "
        "fail loudly, not silently (silence is indistinguishable from coverage)"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _load_text(path):
    assert path.exists(), (
        f"the live {path} was not found -- a self-closing test must "
        "fail loudly, not silently (silence is indistinguishable from coverage)"
    )
    return path.read_text(encoding="utf-8")


def _iter_hook_commands(settings_data):
    """Every command string from EVERY group of EVERY hooks event --
    tolerant of an empty array at any level, and of missing keys."""
    hooks = settings_data.get("hooks", {}) or {}
    for _event, groups in hooks.items():
        for group in groups or []:
            for hook in group.get("hooks", []) or []:
                if hook.get("type") == "command" and "command" in hook:
                    yield hook["command"]


def _tool_paths_in_text(text):
    """Every occurrence of `tools/<name>.py` in *text* (a hook command,
    or the entire content of a .githooks/* script) -- backslash
    normalized to a forward slash before comparing against
    MECHANISM_PREFIXES."""
    return [m.group(0).replace("\\", "/") for m in _TOOL_CMD_RE.finditer(text)]


def _uncovered_tool_paths(texts):
    uncovered = []
    for text in texts:
        for tool_path in _tool_paths_in_text(text):
            if not any(mg._matches(tool_path, pref) for pref in mg.MECHANISM_PREFIXES):
                uncovered.append(tool_path)
    return uncovered


def test_every_live_settings_hook_command_is_covered_by_mechanism_prefixes():
    data = _load_settings(LIVE_SETTINGS_PATH)
    commands = list(_iter_hook_commands(data))
    assert commands, ("the live .claude/settings.json carries no hook "
                       "command at all -- empty is suspicious, not coverage")
    uncovered = _uncovered_tool_paths(commands)
    assert not uncovered, (
        f"hook commands in .claude/settings.json outside the MECHANISM_PREFIXES net: "
        f"{sorted(set(uncovered))}")


def test_every_githooks_script_reference_is_covered_by_mechanism_prefixes():
    pre_commit_text = _load_text(LIVE_GITHOOKS_DIR / "pre-commit")
    commit_msg_text = _load_text(LIVE_GITHOOKS_DIR / "commit-msg")
    referenced = _tool_paths_in_text(pre_commit_text) + _tool_paths_in_text(commit_msg_text)
    assert referenced, ("neither .githooks/pre-commit nor .githooks/commit-msg "
                         "references a single tools/*.py -- empty is suspicious")
    uncovered = _uncovered_tool_paths([pre_commit_text, commit_msg_text])
    assert not uncovered, (
        f"scripts invoked from .githooks/ outside the MECHANISM_PREFIXES net: "
        f"{sorted(set(uncovered))}")


# --- Transitive AST-import closure of the live wiring -------------------
# A direct hook command/.githooks script is not enough on its own: a
# wired script can itself `import` another tools/*.py module that is
# not a hook command in its own right -- corrupting/breaking THAT
# module still changes what the wired hook does, the same criterion as
# a direct hook command. This block collects the AST imports of
# tools/*-modules RECURSIVELY from every live starting script and
# asserts: every module reached is covered by MECHANISM_PREFIXES.

TOOLS_DIR = REPO_ROOT / "tools"


def _tools_module_names(tools_dir=TOOLS_DIR):
    """The set of module names (no .py) that actually exist as files in
    *tools_dir* -- the resolution boundary: an import whose name is NOT
    in this set is not a tools/-module (the standard library, gateway/,
    anything else) and is not part of the closure."""
    return {p.stem for p in tools_dir.glob("*.py")}


def _ast_tool_imports(source_text, tools_module_names):
    """Real (AST, not a string grep) top-level `import X` / `from X
    import ...` in *source_text*, X resolved ONLY against
    *tools_module_names* -- a standard-library/gateway/etc. import is
    simply not in that set and is silently excluded (not an error). A
    relative import (`from . import X`, node.level > 0) is NOT resolved
    this way -- not unwrapped separately here (relative imports between
    tools/*.py are not a style used in this repository; a documented
    narrowing, not a silent guess). ast.parse() raises SyntaxError on
    broken syntax -- NOT caught here: the caller decides whether to
    fail loudly or not."""
    tree = ast.parse(source_text)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top in tools_module_names:
                    found.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                top = node.module.split(".")[0]
                if top in tools_module_names:
                    found.add(top)
    return found


def _transitive_tool_module_closure(start_modules, tools_module_names, tools_dir=TOOLS_DIR):
    """BFS closure of tools/*-modules reachable by REAL imports from
    *start_modules* (bare module names, no .py) -- terminates on a
    cycle via the `seen` set: a module is added to seen BEFORE its
    source is read, so a repeat encounter of an already-seen name
    (including in a cycle) produces no new work. A module with no file
    on disk is silently skipped (best-effort, the same posture as this
    repository's other wiring readers)."""
    seen = set()
    frontier = list(start_modules)
    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        path = tools_dir / f"{name}.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for imported in _ast_tool_imports(text, tools_module_names):
            if imported not in seen:
                frontier.append(imported)
    return seen


def _live_wiring_start_tool_paths():
    """Every tools/*.py named DIRECTLY by the live wiring -- the same
    command/script set the direct tests above already check."""
    settings_data = _load_settings(LIVE_SETTINGS_PATH)
    commands = list(_iter_hook_commands(settings_data))
    pre_commit_text = _load_text(LIVE_GITHOOKS_DIR / "pre-commit")
    commit_msg_text = _load_text(LIVE_GITHOOKS_DIR / "commit-msg")
    paths = set()
    for command in commands:
        paths |= set(_tool_paths_in_text(command))
    paths |= set(_tool_paths_in_text(pre_commit_text))
    paths |= set(_tool_paths_in_text(commit_msg_text))
    return paths


def test_transitive_import_closure_of_live_wiring_is_covered_by_mechanism_prefixes():
    start_paths = _live_wiring_start_tool_paths()
    assert start_paths, "the live wiring names no starting tools/*.py at all"
    start_modules = {Path(p).stem for p in start_paths}
    tools_module_names = _tools_module_names()
    closure = _transitive_tool_module_closure(start_modules, tools_module_names)
    reached_paths = sorted(f"tools/{m}.py" for m in closure)
    uncovered = [p for p in reached_paths
                 if not any(mg._matches(p, pref) for pref in mg.MECHANISM_PREFIXES)]
    assert not uncovered, (
        "the transitive import closure of the live wiring reaches modules outside the "
        f"MECHANISM_PREFIXES net: {uncovered}\nfull closure: {reached_paths}")


# --- adversarial battery on closure completion ---------------------------


def test_ast_tool_imports_ignores_import_outside_tools():
    src = "import json\nimport os.path\nfrom pathlib import Path\n"
    assert _ast_tool_imports(src, {"tier_echo", "preflight_quota"}) == set()


def test_ast_tool_imports_finds_plain_and_from_import_forms():
    src = "import tier_echo\nfrom preflight_quota import load_config\n"
    names = {"tier_echo", "preflight_quota", "other_mod"}
    assert _ast_tool_imports(src, names) == {"tier_echo", "preflight_quota"}


def test_ast_tool_imports_ignores_relative_import():
    # A documented narrowing (see _ast_tool_imports' docstring) -- a
    # relative import is not resolved this way, not counted as reached.
    src = "from . import tier_echo\n"
    assert _ast_tool_imports(src, {"tier_echo"}) == set()


def test_ast_tool_imports_broken_syntax_raises_not_silently_skipped():
    import pytest

    with pytest.raises(SyntaxError):
        _ast_tool_imports("def broken(:\n", {"tier_echo"})


def test_transitive_closure_terminates_on_circular_import(tmp_path):
    # If the algorithm looped forever, this test would never finish
    # (an ordinary pytest-environment timeout) -- its own completion
    # with the right result IS proof the cycle was broken, not just the
    # final set.
    (tmp_path / "mod_a.py").write_text("import mod_b\n", encoding="utf-8")
    (tmp_path / "mod_b.py").write_text("import mod_a\n", encoding="utf-8")
    names = {"mod_a", "mod_b"}
    closure = _transitive_tool_module_closure({"mod_a"}, names, tools_dir=tmp_path)
    assert closure == {"mod_a", "mod_b"}


def test_transitive_closure_missing_module_file_skipped_not_raising(tmp_path):
    closure = _transitive_tool_module_closure(
        {"does_not_exist_mod"}, {"does_not_exist_mod"}, tools_dir=tmp_path)
    assert closure == {"does_not_exist_mod"}


def test_transitive_closure_self_import_does_not_loop(tmp_path):
    # A degenerate cycle of length 1 (a module imports itself) -- the
    # same seen-barrier must break this form too.
    (tmp_path / "mod_self.py").write_text("import mod_self\n", encoding="utf-8")
    closure = _transitive_tool_module_closure(
        {"mod_self"}, {"mod_self"}, tools_dir=tmp_path)
    assert closure == {"mod_self"}


# --- adversarial battery on the self-closing test's own parser ----------


def test_tool_cmd_re_command_form_with_extra_cli_arguments():
    cmd = "python tools/hygiene_gate.py --strict --config=foo.yaml"
    assert _tool_paths_in_text(cmd) == ["tools/hygiene_gate.py"]


def test_tool_cmd_re_forward_slash_path():
    assert _tool_paths_in_text("python tools/hygiene_gate.py") == ["tools/hygiene_gate.py"]


def test_tool_cmd_re_backslash_path_normalised_to_forward_slash():
    assert _tool_paths_in_text("python tools\\hygiene_gate.py") == ["tools/hygiene_gate.py"]


def test_tool_cmd_re_quoted_arg_after_path_does_not_leak_into_match():
    # .githooks/commit-msg form: `python tools/mechanism_gate.py "$1"`.
    cmd = 'python tools/mechanism_gate.py "$1"'
    assert _tool_paths_in_text(cmd) == ["tools/mechanism_gate.py"]


def test_iter_hook_commands_tolerates_empty_hooks_array():
    data = {"hooks": {"PreToolUse": [{"matcher": "X", "hooks": []}], "Stop": []}}
    assert list(_iter_hook_commands(data)) == []


def test_iter_hook_commands_tolerates_missing_hooks_key_entirely():
    assert list(_iter_hook_commands({})) == []


def test_uncovered_tool_paths_catches_drift_of_nonexistent_referenced_script():
    # The detector itself, on a synthetic input (not a live file) --
    # it must FIND a path that isn't in MECHANISM_PREFIXES, not
    # silently swallow the drift.
    drifted = "python tools/definitely_not_wired_anywhere_xyz.py --flag"
    uncovered = _uncovered_tool_paths([drifted])
    assert uncovered == ["tools/definitely_not_wired_anywhere_xyz.py"]


def test_uncovered_tool_paths_full_net_set_gives_empty():
    # The opposite boundary: a command set entirely within the net ->
    # empty.
    commands = [f"python {pref}" for pref in mg.MECHANISM_PREFIXES if pref.startswith("tools/")]
    assert _uncovered_tool_paths(commands) == []
