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
