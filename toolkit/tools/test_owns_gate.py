"""Unit/smoke tests for tools/owns_gate.py. Covers: overlap checking
(equal paths / a nested directory / a glob in either direction /
sibling directories with a common name prefix -- NOT an overlap), the
24h liveness window (ON the boundary -- still live; BEYOND it -- stale),
the cwd scope (a different cwd is ignored, the same cwd + a different
session_key -> WARN with a parallel-session label), a read-only
dispatch -- silence, the sidecar does not grow, a non-Task tool --
silence, a missing/malformed sidecar line -- fail-open, an adversarial
stdin battery (malformed JSON, non-UTF-8 bytes, a huge owns string
>1MB, a payload that isn't a dict) -- exit 0 everywhere, no traceback;
PLUS named regressions for each extraction class: canonical forms
(EN/RU, markdown bullet, guillemets, a prose-tail cut that preserves
paths with spaces), a marker false-positive on a Given line yielding to
a real owns line below, the empty-owns diagnostic (WARN, sidecar not
grown), WARN dedup for one path against several live records, and the
sidecar compaction boundary at 500/501 lines.

Run from the repo root: python -m pytest toolkit/tools/test_owns_gate.py
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import owns_gate  # noqa: E402
import dispatch_gate  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "owns_gate.py"


def _run_hook(raw_input, cwd=None, **kwargs) -> subprocess.CompletedProcess:
    # cwd is ALWAYS passed explicitly by tests that write through the
    # sidecar (payload["cwd"] determines the logs/owns_registry.jsonl
    # path, see owns_gate.py's docstring) -- otherwise the subprocess
    # would inherit the test runner's cwd and append to the REAL repo
    # file logs/owns_registry.jsonl.
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        cwd=str(cwd) if cwd is not None else None,
        **kwargs,
    )


def _writing_payload(owns_text: str, session_id="s-1", cwd="D:\\repo", description="sonnet: write") -> dict:
    # owns is on ITS OWN line (a realistic manifest form for this kit:
    # each manifest item is a separate bullet line).
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        f"owns: {owns_text}.\n"
        "Edit the files."
    )
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": description},
        "session_id": session_id,
        "cwd": cwd,
    }


def _write_registry_line(path: Path, ts: str, session_key: str, cwd: str, description: str, owns: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": ts, "session_key": session_key, "cwd": cwd, "description": description, "owns": owns}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------
# Extracting owns paths from the prompt.
# ---------------------------------------------------------------------


def test_extract_owns_paths_windows_absolute():
    paths = owns_gate.extract_owns_paths("Given: the repo. owns: D:\\repo\\tools\\x.py; D:\\repo\\tools\\y.py.")
    assert paths == ["D:\\repo\\tools\\x.py", "D:\\repo\\tools\\y.py"]


def test_extract_owns_paths_no_marker_is_readonly():
    assert owns_gate.extract_owns_paths("Read the file and tell me what's in it.") == []


def test_extract_owns_paths_drops_relative_prose_tokens():
    # "a line in .gitignore" is not a path-like token (no drive/slash
    # at the start, no "*") -- dropped by the is_path_token filter.
    paths = owns_gate.extract_owns_paths(
        "owns: D:\\repo\\tools\\x.py, a line in .gitignore (not a path)."
    )
    assert paths == ["D:\\repo\\tools\\x.py"]


# --- canonical form / RU form / markdown / guillemets / prose tail ----


def test_extract_owns_paths_canonical_single_path_form():
    prompt = "owns (ABSOLUTE write paths): D:/repo/tools/only_one.py"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/only_one.py"]


def test_extract_owns_paths_canonical_two_paths_form():
    prompt = "owns (ABSOLUTE write paths): D:/repo/tools/a.py; D:/repo/tools/b.py"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_ru_form():
    prompt = "owns (\u0410\u0411\u0421\u041e\u041b\u042e\u0422\u041d\u042bE \u043f\u0443\u0442\u0438 \u0437\u0430\u043f\u0438\u0441\u0438): D:/repo/tools/x.py"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/x.py"]


def test_extract_owns_paths_markdown_bullet_form():
    prompt = "- **owns**: D:/a.py; D:/b.py"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/a.py", "D:/b.py"]


def test_extract_owns_paths_guillemets_quoted_path():
    prompt = "owns: \u00abD:/a.py\u00bb"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/a.py"]


def test_extract_owns_paths_prose_tail_cut_preserves_path_with_space():
    # A tail " -- a new file" (space-emdash-space) is cut off the first
    # token; the SECOND token's path contains a space and must survive
    # WHOLE -- no split on a bare space.
    prompt = "owns: D:/a.py \u2014 a new file; D:/AI CRM/x/AGENTS.md"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/a.py",
        "D:/AI CRM/x/AGENTS.md",
    ]


# ---------------------------------------------------------------------
# Backtick-wrapped paths, quoted-with-space paths in the continuation
# form, and a bold marker + bulleted continuation below.
# ---------------------------------------------------------------------


def test_backtick_wrapped_path_single_line_recognized():
    prompt = "owns: `D:/repo/tools/a.py`, `D:/repo/tools/b.py`"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_backtick_wrapped_path_continuation_recognized():
    prompt = "owns:\n- `D:/repo/tools/a.py`\n- `D:/repo/tools/b.py`\n"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_quoted_path_with_space_continuation_preserved():
    prompt = 'owns:\n- "D:/repo/my folder/a.py"\n'
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/my folder/a.py"]


def test_backtick_path_with_space_continuation_preserved():
    prompt = "owns:\n- `D:/repo/my folder/a.py`\n"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/my folder/a.py"]


def test_unclosed_quote_continuation_falls_back_to_whitespace_split():
    # An unclosed quote -- _first_raw_token finds no matching character,
    # falls back to a plain space split; a path with no internal space
    # is recognized as before, the quote is edge-trimmed on one side.
    prompt = 'owns:\n- "D:/repo/tools/a.py\n'
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/a.py"]


def test_bold_marker_with_bulleted_continuation_below_parses_paths():
    prompt = (
        "DoD: acceptance criteria -- the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "**owns (ABSOLUTE write paths):**\n"
        "- D:\\repo\\tools\\dispatch_gate.py\n"
        "- D:\\repo\\tools\\owns_gate.py\n"
        "- D:\\repo\\tools\\test_dispatch_gate.py\n"
        "- D:\\repo\\tools\\test_owns_gate.py\n"
        "Edit the files per the spec."
    )
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:\\repo\\tools\\dispatch_gate.py",
        "D:\\repo\\tools\\owns_gate.py",
        "D:\\repo\\tools\\test_dispatch_gate.py",
        "D:\\repo\\tools\\test_owns_gate.py",
    ]


def test_decide_bold_marker_writes_declared_paths_to_sidecar(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: acceptance criteria -- the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "**owns (ABSOLUTE write paths):**\n"
        "- D:\\repo\\tools\\dispatch_gate.py\n"
        "- D:\\repo\\tools\\owns_gate.py\n"
        "Edit the files per the spec."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 8, 10, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == [
        "D:\\repo\\tools\\dispatch_gate.py",
        "D:\\repo\\tools\\owns_gate.py",
    ]


def test_two_bold_marker_manifests_with_overlap_detected(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 8, 10, 12, 0, 0)
    prompt1 = (
        "DoD: witness attached. Given: the whole repo.\n"
        "**owns (ABSOLUTE write paths):**\n"
        "- D:/repo/tools/shared.py\n"
        "Edit the files."
    )
    payload1 = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt1, "description": "sonnet: write A"},
        "session_id": "s-A",
        "cwd": "D:\\repo",
    }
    exit_code1, output1 = owns_gate.decide(payload1, registry_path=registry, now=now)
    assert exit_code1 == 0
    assert output1 is None

    prompt2 = (
        "DoD: witness attached. Given: the whole repo.\n"
        "**owns (ABSOLUTE write paths):**\n"
        "- D:/repo/tools/shared.py\n"
        "Edit the files."
    )
    payload2 = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt2, "description": "sonnet: write B"},
        "session_id": "s-B",
        "cwd": "D:\\repo",
    }
    exit_code2, output2 = owns_gate.decide(payload2, registry_path=registry, now=now)
    assert exit_code2 == 0
    assert output2 is not None
    assert "OWNS OVERLAP" in output2["hookSpecificOutput"]["additionalContext"]


def test_owns_bare_marker_without_any_paths_stays_empty():
    assert owns_gate.extract_owns_paths("**owns:**\n") == []
    assert owns_gate.extract_owns_paths("owns:") == []


def test_fenced_code_block_marker_not_specially_parsed_documented_non_goal():
    prompt = "**owns (ABSOLUTE write paths):**\n```\nD:/repo/tools/a.py\n```\n"
    assert owns_gate.extract_owns_paths(prompt) == []


# ---------------------------------------------------------------------
# is_path_token() no longer counts a bare "*" (markdown decoration) as
# a path -- a live sidecar could otherwise register prose containing
# "**" as an owns path.
# ---------------------------------------------------------------------


def test_markdown_bold_decoration_no_slash_not_a_path_single_line():
    prompt = "owns: the flip side.** A writing dispatch with no real path."
    assert owns_gate.extract_owns_paths(prompt) == []


def test_is_path_token_rejects_bare_star_without_slash_direct():
    assert owns_gate.is_path_token("**Attention") is False
    assert owns_gate.is_path_token("the flip side.**") is False
    # Positive control (command hygiene rule 6): a glob WITH a slash is
    # still path-like -- the negative above would not prove the
    # function's absence without this control.
    assert owns_gate.is_path_token("tools/*.py") is True
    assert owns_gate.is_path_token("D:/repo/tools/a.py") is True


def test_decide_prose_with_bare_star_does_not_register_in_sidecar(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "owns: the flip side.** A writing dispatch with no real path.\n"
        "Edit file x.py."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 8, 10, 12, 0, 0))
    assert exit_code == 0
    assert output is not None
    assert "blind" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


def test_is_continuation_path_token_delegates_to_shared_predicate():
    for tok in ("**Attention**:", "tools/test_*.py", "D:/repo/a.py", "flipside.**", "/repo/a.py"):
        assert owns_gate.is_path_token(tok) == owns_gate._is_continuation_path_token(tok), tok


def test_extract_owns_paths_marker_false_positive_line_skipped_for_valid_line_below():
    prompt = (
        "Given: edits to tools/owns_gate.py are already staged.\n"
        "owns: D:\\repo\\tools\\owns_gate.py.\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == ["D:\\repo\\tools\\owns_gate.py"]


# --- word-boundary line selection: a marker false-positive on a Given
# line, sitting next to real absolute paths, must not hijack the real
# owns line below. -------------------------------------------------

_CONTROL_INPUT_PROMPT = (
    "DoD: the test is green, witness attached.\n"
    "Given: D:/x/tools/owns_gate.py, D:/x/tools/dispatch_gate.py, D:/x/CLAUDE.md\n"
    "owns (ABSOLUTE write paths): D:/x/tools/owns_gate.py\n"
    "Edit the files."
)


def test_extract_owns_paths_given_line_with_owns_in_filename_does_not_hijack():
    # A class edge, not a one-off: a false marker + valid paths on the
    # SAME line. "_" is a word character, so "owns_gate.py" does not
    # give "\bowns\b" -- the real owns line BELOW is used instead.
    assert owns_gate.extract_owns_paths(_CONTROL_INPUT_PROMPT) == [
        "D:/x/tools/owns_gate.py"
    ]


def test_decide_given_line_with_owns_in_filename_writes_declared_owns_only(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": _CONTROL_INPUT_PROMPT,
            "description": "sonnet: write",
        },
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None  # no live records yet -- silence

    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(written) == 1
    assert written[0]["owns"] == ["D:/x/tools/owns_gate.py"]
    assert "D:/x/tools/dispatch_gate.py" not in written[0]["owns"]
    assert "D:/x/CLAUDE.md" not in written[0]["owns"]


# --- port adaptation: this kit's dispatch_gate.py carries only ONE
# owns marker regex, already word-bounded (MANIFEST_OWNS_RE) -- there
# is no separate, unbounded substring regex to fall back to (see the
# module docstring, "Owns MARKER"). A prompt whose only "owns" mention
# is embedded inside another word is therefore treated exactly like a
# prompt with no owns marker at all -- no fallback pass recovers it.
# ---------------------------------------------------------------------


def test_no_fallback_pass_substring_only_owns_mention_is_treated_as_readonly():
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "manifest_owns_block; D:/repo/tools/a.py; D:/repo/tools/b.py\n"
    )
    assert owns_gate.MANIFEST_OWNS_RE.search(prompt) is None  # no word-bounded match anywhere
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_word_boundary_line_without_paths_stays_empty():
    prompt = (
        "owns: to be filled in later\n"
        "Given: D:/x/tools/owns_gate.py, D:/x/CLAUDE.md\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_leading_star_glob_is_stripped_known_limitation():
    # A known limitation, pinned as current behavior (not fixed): a
    # leading `*` is one of the junk leading characters (there for
    # markdown "**owns**:") and gets eaten by the stripper. A glob with
    # a leading star falls outside rule 11's "ABSOLUTE write paths"
    # norm anyway.
    assert owns_gate.extract_owns_paths("owns: */tools/*") == ["/tools/*"]


# --- multi-line owns block ---------------------------------------------


def test_extract_owns_paths_multiline_bullet_block():
    prompt = (
        "Given: the whole repo.\n"
        "owns:\n"
        "- D:/repo/tools/a.py\n"
        "- D:/repo/tools/b.py\n"
        "Edit the files."
    )
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_multiline_star_and_middot_bullets():
    prompt = "owns:\n* D:/a.py\n\u2022 D:/b.py\n"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/a.py", "D:/b.py"]


def test_extract_owns_paths_multiline_bare_path_lines_no_bullets():
    prompt = "owns:\nD:/repo/tools/a.py\nD:/repo/tools/b.py\n"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_marker_line_with_paths_takes_priority_over_block_below():
    prompt = "owns: D:/repo/tools/only_this.py\n- D:/repo/tools/should_not_appear.py\n"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/only_this.py"]


def test_extract_owns_paths_empty_line_immediately_after_marker_ends_block():
    prompt = "owns:\n\n- D:/repo/tools/a.py\n"
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_non_goals_section_right_after_marker_ends_block():
    prompt = (
        "owns:\n"
        "non-goals: toolkit/**\n"
        "- D:/repo/tools/a.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_handoff_section_right_after_marker_ends_block():
    prompt = "owns:\nhandoff: see the report\n- D:/repo/tools/a.py\n"
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_given_ru_section_right_after_marker_ends_block():
    prompt = "owns:\n\u0434\u0430\u043d\u043e: the whole repo\n- D:/repo/tools/a.py\n"
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_continuation_stops_at_first_non_path_line():
    prompt = (
        "owns:\n"
        "- D:/repo/tools/a.py\n"
        "a prose line with no path\n"
        "- D:/repo/tools/should_not_appear.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/a.py"]


def test_decide_multiline_owns_block_writes_declared_paths_to_sidecar(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "owns:\n"
        "- D:/repo/tools/a.py\n"
        "- D:/repo/tools/b.py\n"
        "Edit the files."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == ["D:/repo/tools/a.py", "D:/repo/tools/b.py"]


# --- continuation-line limit (boundary-tested both sides) --------------


def test_extract_owns_paths_continuation_exactly_40_lines_returns_all():
    lines = ["owns:"] + [f"- D:/repo/tools/f{i}.py" for i in range(40)]
    prompt = "\n".join(lines) + "\n"
    result = owns_gate.extract_owns_paths(prompt)
    assert len(result) == 40
    assert result[0] == "D:/repo/tools/f0.py"
    assert result[-1] == "D:/repo/tools/f39.py"


def test_extract_owns_paths_continuation_41_lines_hits_limit_returns_empty():
    lines = ["owns:"] + [f"- D:/repo/tools/f{i}.py" for i in range(41)]
    prompt = "\n".join(lines) + "\n"
    # The block would STILL be continuing at line 41 -- hits the
    # limit, an empty list, not a silent truncation to the first 40.
    assert owns_gate.extract_owns_paths(prompt) == []


def test_decide_continuation_limit_hit_gives_blind_owns_warn(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    lines = ["owns:"] + [f"- D:/repo/tools/f{i}.py" for i in range(41)]
    prompt = (
        "DoD: the test is green, witness attached.\nGiven: the whole repo.\n"
        + "\n".join(lines) + "\nEdit file x.py."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is not None
    assert "blind" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


# --- "declaration, not prose" gate --------------------------------------


def test_regression_prose_owns_word_does_not_hijack_declaration_below():
    prompt = (
        "Task: fixing the gate.\n"
        "Don't go beyond the owns of this task.\n"
        "D:/repo/readme.md -- read before starting\n"
        "\n"
        "owns: D:/repo/real_target.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/real_target.py"]


def test_decide_regression_prose_owns_word_sidecar_gets_real_target(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "Task: fixing the gate.\n"
        "Don't go beyond the owns of this task.\n"
        "D:/repo/readme.md -- read before starting\n"
        "\n"
        "owns: D:/repo/real_target.py\n"
        "Edit the files."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == ["D:/repo/real_target.py"]


def test_prose_owns_word_mid_sentence_alone_gives_blind_warn_not_silence(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\nGiven: the whole repo.\n"
        "Don't go beyond the owns of this task.\n"
        "D:/repo/readme.md -- read before starting\n"
        "Edit file x.py."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is not None
    assert "blind" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


def test_markdown_bold_junk_line_under_marker_does_not_pollute_block():
    prompt = (
        "owns:\n"
        "**Attention**: write only here\n"
        "- D:/repo/tools/a.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_dod_line_under_marker_does_not_get_swallowed_whole():
    prompt = (
        "owns:\n"
        "DoD: run pytest tools/test_*.py -q\n"
        "- D:/repo/tools/a.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_numbered_list_recognized_as_bullet_form():
    prompt = "owns:\n1. D:/repo/tools/a.py\n2) D:/repo/tools/b.py\n"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_prose_tail_after_bullet_path_is_cut_not_swallowed_whole():
    prompt = "owns:\n- D:/repo/tools/a.py -- the main file\n"
    paths = owns_gate.extract_owns_paths(prompt)
    assert paths == ["D:/repo/tools/a.py"]
    assert owns_gate.paths_overlap(paths[0], "D:/repo/tools/a.py") is True


def test_is_continuation_path_token_rejects_bare_star_without_slash():
    assert owns_gate._is_continuation_path_token("**Attention**:") is False
    assert owns_gate._is_continuation_path_token("tools/test_*.py") is True
    assert owns_gate._is_continuation_path_token("D:/repo/a.py") is True


def test_strip_owns_marker_junk_50kb_paren_groups_completes_under_5s():
    junk = "(x)" * 16667  # 50 001 characters
    assert len(junk) >= 50000
    prompt = "owns " + junk + ": D:/repo/tools/a.py"
    started = time.time()
    paths = owns_gate.extract_owns_paths(prompt)
    elapsed = time.time() - started
    assert paths == ["D:/repo/tools/a.py"]
    assert elapsed < 5.0


# ---------------------------------------------------------------------
# Path overlap checking (boundary-tested).
# ---------------------------------------------------------------------


def test_equal_paths_overlap():
    assert owns_gate.paths_overlap("D:\\x\\y.py", "D:\\x\\y.py") is True


def test_nested_directory_overlaps():
    assert owns_gate.paths_overlap("D:\\x\\y", "D:\\x") is True
    assert owns_gate.paths_overlap("D:\\x", "D:\\x\\y") is True


def test_glob_overlaps_both_directions():
    assert owns_gate.paths_overlap("D:\\x\\*.py", "D:\\x\\y.py") is True
    assert owns_gate.paths_overlap("D:\\x\\y.py", "D:\\x\\*.py") is True


def test_sibling_directories_common_name_prefix_do_not_overlap():
    # D:\ab vs D:\abc -- NOT an overlap (a segment-boundary check, not a
    # bare substring prefix).
    assert owns_gate.paths_overlap("D:\\ab", "D:\\abc") is False
    assert owns_gate.paths_overlap("D:\\abc", "D:\\ab") is False


# ---------------------------------------------------------------------
# decide(): the 24h window -- ON the boundary and BEYOND it.
# ---------------------------------------------------------------------


def test_window_on_boundary_still_live(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    boundary_ts = (now - timedelta(seconds=owns_gate.WINDOW_SECONDS)).strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, boundary_ts, "s-1", "D:\\repo", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


def test_window_beyond_boundary_is_stale(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    stale_ts = (now - timedelta(seconds=owns_gate.WINDOW_SECONDS + 1)).strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, stale_ts, "s-1", "D:\\repo", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# Scope: cwd, NOT session_key (session_key is only a label).
# ---------------------------------------------------------------------


def test_scope_different_cwd_is_ignored(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, fresh_ts, "s-1", "D:\\OTHER_REPO", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    # Same session_key ("s-1"), but a DIFFERENT cwd -- ignored: the
    # check scope is the repo (cwd), not the session.
    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None


def test_scope_same_cwd_different_session_key_warns_with_parallel_session_label(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, fresh_ts, "s-OTHER", "D:\\repo", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "a different session" in ctx


# ---------------------------------------------------------------------
# WARN dedup: one new path against several live records.
# ---------------------------------------------------------------------


def test_dedup_single_path_multiple_live_records_one_warn_line(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    for i in range(3):
        _write_registry_line(
            registry, fresh_ts, f"s-other-{i}", "D:\\repo", f"sonnet: prior write {i}",
            ["D:\\repo\\tools\\shared.py"],
        )

    payload = _writing_payload("D:\\repo\\tools\\shared.py", session_id="s-me", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    # One WARN line for this path, not three -- at most 2 mentions +
    # an "and N more" tail.
    assert ctx.count("D:\\repo\\tools\\shared.py overlaps") == 1
    assert "and 1 more" in ctx


# ---------------------------------------------------------------------
# Diagnosing an empty owns: a marker + write indicator with no paths.
# ---------------------------------------------------------------------


def test_decide_blind_owns_warn_when_marker_present_but_no_paths_parsed(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: the test is green, witness attached.\n"
        "Given: the whole repo.\n"
        "owns: something unparseable here with no paths.\n"
        "Edit file x.py."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "blind" in ctx
    assert not registry.exists()


def test_decide_true_readonly_no_marker_no_write_indicator_is_silent(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "scout", "prompt": "Find the file and read it.", "description": "haiku: scout"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


# ---------------------------------------------------------------------
# A read-only dispatch -- silence, sidecar not grown.
# ---------------------------------------------------------------------


def test_readonly_dispatch_is_silent_and_sidecar_not_grown(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "scout", "prompt": "Find the file and read it.", "description": "haiku: scout"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


# ---------------------------------------------------------------------
# A non-Task tool -- silence.
# ---------------------------------------------------------------------


def test_non_task_tool_is_silent(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo owns: D:\\x"}}
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


# ---------------------------------------------------------------------
# A missing sidecar / a malformed line -- fail-open.
# ---------------------------------------------------------------------


def test_missing_registry_file_fail_open(tmp_path):
    registry = tmp_path / "does_not_exist" / "owns_registry.jsonl"
    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    # The new session's own write must still land after the fail-open read.
    assert registry.exists()


def test_malformed_registry_line_fail_open(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    registry.parent.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    with registry.open("a", encoding="utf-8") as f:
        f.write("{not valid json\n")
        f.write(json.dumps({
            "ts": fresh_ts, "session_key": "s-1", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:\\repo\\tools\\x.py"],
        }) + "\n")

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    assert "OWNS OVERLAP" in output["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------
# Sidecar compaction boundary at 500/501 lines.
# ---------------------------------------------------------------------


def test_registry_compaction_boundary_500_lines_appends(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    lines = [
        json.dumps({
            "ts": fresh_ts, "session_key": "s-1", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:\\x.py"],
        })
        for _ in range(owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES)
    ]
    registry.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # EXACTLY 500 existing lines -- not STRICTLY greater than the
    # threshold -> a plain append, not compaction.
    owns_gate._append_registry(registry, now, "s-2", "D:\\repo", "new write", ["D:\\y.py"])

    final_text = registry.read_text(encoding="utf-8")
    final_lines = [ln for ln in final_text.splitlines() if ln.strip()]
    assert len(final_lines) == owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES + 1
    # An append (not a rewrite/compaction): the first original line
    # stays byte-for-byte.
    assert final_lines[0] == lines[0]


def test_registry_compaction_boundary_501_lines_compacts(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    stale_ts = (now - timedelta(seconds=owns_gate.WINDOW_SECONDS + 1)).strftime(owns_gate._TS_FORMAT)

    live_lines = [
        json.dumps({
            "ts": fresh_ts, "session_key": "s-1", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:\\x.py"],
        })
        for _ in range(owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES)
    ]
    stale_line = json.dumps({
        "ts": stale_ts, "session_key": "s-1", "cwd": "D:\\repo",
        "description": "stale", "owns": ["D:\\stale.py"],
    })
    # 500 live + 1 stale = 501 existing lines -- strictly greater than
    # the threshold -> compaction.
    registry.write_text("\n".join(live_lines + [stale_line]) + "\n", encoding="utf-8")

    owns_gate._append_registry(registry, now, "s-2", "D:\\repo", "new write", ["D:\\y.py"])

    final_text = registry.read_text(encoding="utf-8")
    final_lines = [ln for ln in final_text.splitlines() if ln.strip()]
    # Compaction dropped the stale line: 500 live + 1 new = 501, not
    # 502 (which a naive append with no compaction would give) -- the
    # difference proves compaction actually ran at the 501 boundary.
    assert len(final_lines) == owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES + 1
    assert "stale.py" not in final_text


# ---------------------------------------------------------------------
# Adversarial stdin battery (boundaries + main()).
# ---------------------------------------------------------------------


def test_decide_payload_not_dict_fail_open():
    exit_code, output = owns_gate.decide(["not", "a", "dict"])
    assert exit_code == 0
    assert output is None


def test_echo_json_malformed_json_fails_open():
    result = _run_hook("{not valid json", text=True)
    assert result.returncode == 0
    assert result.stdout == ""


def test_echo_json_empty_stdin_fails_open():
    result = _run_hook(b"")
    assert result.returncode == 0


def test_echo_json_non_utf8_bytes_fail_open():
    result = _run_hook(b"\xff\xfe\x00\x01not json either")
    assert result.returncode == 0


def test_echo_json_huge_owns_string_completes_quickly(tmp_path):
    huge_owns = "D:\\repo\\tools\\huge_" + ("x" * (1024 * 1024)) + ".py"
    payload = _writing_payload(huge_owns, session_id="s-huge", cwd=str(tmp_path))
    started = time.time()
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    elapsed = time.time() - started
    assert result.returncode == 0
    assert elapsed < 5.0


def test_echo_json_valid_writing_dispatch_no_prior_records_is_silent(tmp_path):
    payload = _writing_payload(
        "D:\\repo\\tools\\brand_new_path_for_test.py", session_id="s-echo-1", cwd=str(tmp_path)
    )
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "logs" / "owns_registry.jsonl").exists()


# ---------------------------------------------------------------------
# A single point of truth for the owns marker: owns_gate.py carries NO
# local re.compile of its own for the bounded owns pattern -- it is
# imported from dispatch_gate.py (positive control: dispatch_gate.py
# DOES carry that compile -- a negative claim without a positive
# control of the same form does not prove absence, command hygiene
# rule 6).
# ---------------------------------------------------------------------


def test_owns_gate_source_has_no_local_owns_word_re_compile():
    needle = 're.compile(r"\\bowns\\b"'
    tools_dir = Path(__file__).resolve().parent
    dispatch_gate_src = (tools_dir / "dispatch_gate.py").read_text(encoding="utf-8")
    owns_gate_src = (tools_dir / "owns_gate.py").read_text(encoding="utf-8")

    assert needle in dispatch_gate_src  # positive control of the search form
    assert needle not in owns_gate_src  # owns_gate carries no local copy


def test_owns_gate_imports_is_path_like_token_from_dispatch_gate():
    assert owns_gate.is_path_token is not dispatch_gate.is_path_like_token
    for tok in ("D:/a.py", "/a.py", "tools/*.py", "**bold**", "relative/x.py", ""):
        assert owns_gate.is_path_token(tok) == dispatch_gate.is_path_like_token(tok), tok
