"""Tests for the NOTES LEN ECHO layer -- a warn-only guard on the write
path against an oversized `notes` field burying a load-bearing fact in
prose, implemented in toolkit/tools/journal_echo.py (see its "NOTES LEN
ECHO" section for the full design). WARN at write time, NEVER a block
(returncode always 0, no channel ever carries permissionDecision).

Style -- mirrors toolkit/tools/test_journal_echo_escalation.py (a
sibling echo layer of the same class): pure logic
(_collect_notes_len_events/_format_notes_len_line/
build_notes_len_segment) + a subprocess smoke test of main() through
real tmp_path git repos. Helpers (git repos, hook launch, journal
lines) are duplicated locally (the same self-containment preference
this toolkit's other test files already document).

Covers the DoD literally:
 Boundaries (rule 6a, both sides of every limit):
  B1/B2/B3 -- threshold 800 (dispatch-cycle events): 800 silent, 801
             warns, 799 silent.
  B4/B5    -- threshold 15000 (calibrated): exactly 15000 silent, 15001
             warns.
 Line ceiling (MAX_NOTES_LEN_LINES=5):
  B6 -- exactly 5, no tail; 6 -- "; +1 more".
 Empty/broken (E4-E11):
  B7/B8/B9 -- notes missing/empty-or-whitespace/not a string -- silent,
             the form defect (journal_validator) is not double-warned.
  B10 -- one broken JSON line + a second valid long one -- warns
         exactly on the second, the hook doesn't crash.
  B11 -- an unknown/missing event -- silent.
 Selection base (the payload-scoped base, mirrors the F-57-class fix
 the sibling layers already carry):
  B12 -- an old long uncommitted line OUTSIDE this call's payload --
         zero events.
  B13 -- fallback mode -- the layer is FULLY disabled (zero events),
         the fallback marker still prints.
  B14 -- a non-journal edit -- the layer is inactive.
 Adversarial mini-battery:
  B15 -- notes 200000 chars -- exactly one message, the segment isn't
         bloated, no notes fragment leaks into the message.
  B16 -- control chars and non-ASCII in notes -- valid stdout JSON, the
         hook doesn't crash.
  B17 -- a batch of 200 lines, 100 long -- 5 messages + "; +95 more".
 combine_context keyword-only barrier:
  B18 -- pin: `je.combine_context([], [], None, None, [ev], "MARKER")`
         (6 positional) yields the prior result -- notes_len_events
         never inserts positionally.
 Segment order:
  B19 -- violations first (header literal unchanged), notes_len between
         escalation and the fallback marker, marker last.
 B20 -- returncode 0 throughout, never a permissionDecision.

Run from the repo root:
python -m pytest toolkit/tools/test_journal_echo_noteslen.py -q
"""

import datetime
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal_echo as je  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "journal_echo.py"


def _fresh_ts() -> str:
    # A fresh (relative to the REAL clock, at call time) ts -- the same
    # finding test_journal_echo_escalation.py._fresh_ts already
    # documents: a fixed historical ts fixture in a NEW journal line
    # (beyond HEAD) gets caught by the LIVE TS DRIFT ECHO layer as
    # STALE -- breaking asserts expecting complete silence / an exact
    # additionalContext match. Every _line() call below with no
    # explicit ts takes a fresh value.
    return datetime.datetime.now().isoformat(timespec="seconds")


# =======================================================================
# helpers -- journal lines (mirrors test_journal_echo_escalation._line)
# =======================================================================


def _line(event="delegated", ts=None, agent="builder",
          category="implementation", notes="note",
          worker_ref="cli:2026-08-25T08:00:00", **kw) -> str:
    obj = {"ts": ts if ts is not None else _fresh_ts(), "event": event, "agent": agent,
           "category": category, "notes": notes, "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(event="delegated", ts="2026-08-25T08:00:00", task_id="t-001", model="sonnet")
HEAD_TEXT = HEAD_LINE + "\n"


# =======================================================================
# helpers -- real git repos
# =======================================================================


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def _init_repo(root: Path):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def _write_journal(root: Path, text: str) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-log.jsonl").write_text(text, encoding="utf-8")


def _seed_committed_journal(root: Path, text: str = HEAD_TEXT) -> Path:
    _init_repo(root)
    _write_journal(root, text)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    return root / "logs" / "routing-log.jsonl"


_NO_ORIGINAL_FILE = object()  # sentinel -- omit tool_response.originalFile entirely
# (exercises the HEAD-diff fallback path of _resolve_echo_base -- same
# convention as the sibling echo test files).


def _post_tool_use_payload(file_path, tool_name="Edit", original_file=_NO_ORIGINAL_FILE) -> dict:
    tool_response = {"filePath": str(file_path), "success": True}
    if original_file is not _NO_ORIGINAL_FILE:
        tool_response["originalFile"] = original_file
    return {
        "session_id": "sess-1",
        "transcript_path": "/x/transcript.jsonl",
        "cwd": ".",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": tool_response,
        "tool_use_id": "tu-1",
    }


def _run_hook(payload, timeout=10, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=env,
    )


def _parse_stdout_json(stdout: str) -> dict:
    payload = json.loads(stdout)
    hook_output = payload["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PostToolUse"
    return hook_output


# =======================================================================
# constants (A1)
# =======================================================================


def test_notes_len_thresholds_literal_values():
    assert je.NOTES_LEN_THRESHOLDS_CHARS == {
        "delegated": 800, "accepted": 800, "rejected": 800,
        "dispatch_skipped": 800, "escalated": 800, "defect_found": 800,
        "decomposable": 800, "calibrated": 15000,
    }
    assert je.MAX_NOTES_LEN_LINES == 5


# =======================================================================
# _collect_notes_len_events -- pure logic, both threshold boundaries (B1-B5)
# =======================================================================


def test_collect_notes_len_events_empty_new_lines():
    assert je._collect_notes_len_events([], []) == []


def test_collect_notes_len_events_short_notes_silent():
    line = _line(event="delegated", notes="short note", task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_exactly_threshold_800_silent():
    # B1
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * threshold
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_threshold_plus_one_801_warns():
    # B2
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    events = je._collect_notes_len_events([line], [])
    assert events == [(1, "delegated", threshold + 1, threshold)]


def test_collect_notes_len_events_threshold_minus_one_799_silent():
    # B3
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold - 1)
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_threshold_applies_per_event_type():
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["accepted"]
    assert threshold == 800
    notes = "x" * (threshold + 1)
    line = _line(event="accepted", notes=notes, task_id="t-002", model="sonnet",
                 by="opus", witness="ran: ok")
    events = je._collect_notes_len_events([line], [])
    assert events == [(1, "accepted", threshold + 1, threshold)]


def test_collect_notes_len_events_calibrated_exactly_threshold_15000_silent():
    # B4 -- the boundary itself stays silent, symmetric with the 800
    # threshold (B1).
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["calibrated"]
    notes = "x" * threshold
    line = _line(event="calibrated", notes=notes)
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_calibrated_15001_warns():
    # B5
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["calibrated"]
    notes = "x" * (threshold + 1)
    line = _line(event="calibrated", notes=notes)
    events = je._collect_notes_len_events([line], [])
    assert events == [(1, "calibrated", threshold + 1, threshold)]


def test_collect_notes_len_events_line_numbering_accounts_for_base_lines():
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    base_lines = ["dummy1", "dummy2"]
    line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet")
    events = je._collect_notes_len_events([line], base_lines)
    assert events[0][0] == 3  # len(base_lines) + idx(0) + 1


def test_collect_notes_len_events_batch_several_lines_per_event():
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    long_notes = "x" * (threshold + 1)
    lines = [
        _line(event="delegated", notes=long_notes, task_id="t-002", model="sonnet", worker_ref="cli:a"),
        _line(event="delegated", notes="short", task_id="t-003", model="sonnet", worker_ref="cli:b"),
        _line(event="delegated", notes=long_notes, task_id="t-004", model="sonnet", worker_ref="cli:c"),
    ]
    events = je._collect_notes_len_events(lines, [])
    assert [e[0] for e in events] == [1, 3]


# =======================================================================
# _collect_notes_len_events -- empty/broken (B7-B11, E4-E11)
# =======================================================================


def test_collect_notes_len_events_missing_notes_field_silent():
    # B7
    obj = json.loads(_line(event="delegated", task_id="t-002", model="sonnet"))
    del obj["notes"]
    assert je._collect_notes_len_events([json.dumps(obj)], []) == []


def test_collect_notes_len_events_empty_notes_silent():
    # B8
    line = _line(event="delegated", notes="", task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_whitespace_only_notes_silent():
    # B8
    line = _line(event="delegated", notes="   \n\t  ", task_id="t-002", model="sonnet")
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_non_string_notes_silent():
    # B9 -- int/list/None/dict, len() is never called on a non-string
    for bad in (12345, ["a", "list"], None, {"k": "v"}):
        obj = json.loads(_line(event="delegated", task_id="t-002", model="sonnet"))
        obj["notes"] = bad
        assert je._collect_notes_len_events([json.dumps(obj)], []) == []


def test_collect_notes_len_events_malformed_json_line_among_valid_not_raised():
    # B10
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    good_notes = "x" * (threshold + 1)
    good = _line(event="delegated", notes=good_notes, task_id="t-002", model="sonnet")
    events = je._collect_notes_len_events(["{not valid json", good], [])
    assert len(events) == 1
    assert events[0][0] == 2  # second line, first skipped


def test_collect_notes_len_events_not_a_dict_line_skipped():
    assert je._collect_notes_len_events(["[1, 2, 3]"], []) == []


def test_collect_notes_len_events_unknown_event_silent():
    # B11
    line = _line(event="journal_created", notes="x" * 5000)
    assert je._collect_notes_len_events([line], []) == []


def test_collect_notes_len_events_missing_event_field_silent():
    # B11
    obj = json.loads(_line(event="delegated", notes="x" * 5000, task_id="t-002", model="sonnet"))
    del obj["event"]
    assert je._collect_notes_len_events([json.dumps(obj)], []) == []


def test_collect_notes_len_events_event_field_unhashable_type_no_crash():
    # Adversarial defense beyond the literal DoD: event is not a
    # string, but an unhashable type (a list) -- must not crash collection.
    obj = json.loads(_line(event="delegated", notes="x" * 5000, task_id="t-002", model="sonnet"))
    obj["event"] = [1, 2, 3]
    assert je._collect_notes_len_events([json.dumps(obj)], []) == []


# =======================================================================
# _format_notes_len_line -- pure logic, the literal format
# =======================================================================


def test_format_notes_len_line_literal():
    line = je._format_notes_len_line((3, "delegated", 950, 800))
    assert line == (
        "NOTES LEN: line 3 event=delegated notes 950 chars > threshold 800 "
        "- an oversized note risks burying load-bearing "
        "facts in prose where they will not be found later; move load-bearing "
        "facts to typed fields / task carrier, keep only a pointer in notes"
    )


def test_format_notes_len_line_is_ascii():
    assert je._format_notes_len_line((1, "accepted", 1000, 800)).isascii()


def test_format_notes_len_line_never_contains_notes_fragment():
    line = je._format_notes_len_line((1, "calibrated", 20000, 15000))
    assert "chars" in line


# =======================================================================
# build_notes_len_segment -- MAX_NOTES_LEN_LINES ceiling (B6, rule 6a)
# =======================================================================


def test_build_notes_len_segment_empty_list():
    assert je.build_notes_len_segment([]) == ""


def test_build_notes_len_segment_single_event():
    ev = (1, "delegated", 900, 800)
    assert je.build_notes_len_segment([ev]) == je._format_notes_len_line(ev)


def test_build_notes_len_segment_exactly_five_no_more_suffix():
    events = [(i, "delegated", 900, 800) for i in range(1, je.MAX_NOTES_LEN_LINES + 1)]
    seg = je.build_notes_len_segment(events)
    assert seg.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert "more" not in seg


def test_build_notes_len_segment_six_adds_one_more():
    events = [(i, "delegated", 900, 800) for i in range(1, je.MAX_NOTES_LEN_LINES + 2)]
    seg = je.build_notes_len_segment(events)
    assert seg.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert seg.endswith("; +1 more")


def test_build_notes_len_segment_far_beyond_boundary_counts_correctly():
    events = [(i, "delegated", 900, 800) for i in range(1, je.MAX_NOTES_LEN_LINES + 6)]
    seg = je.build_notes_len_segment(events)
    assert seg.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert seg.endswith("; +5 more")


def test_build_notes_len_segment_ascii_only_param_is_noop():
    ev = (1, "delegated", 900, 800)
    assert je.build_notes_len_segment([ev], ascii_only=True) == je.build_notes_len_segment([ev], ascii_only=False)


# =======================================================================
# combine_context -- notes_len_events keyword-only (B18)
# =======================================================================


def test_combine_context_notes_len_only_segment():
    ev = (6, "delegated", 900, 800)
    ctx = je.combine_context([], [], None, None, None, "", notes_len_events=[ev])
    assert ctx == je.build_notes_len_segment([ev])


def test_combine_context_notes_len_keyword_only_enforced():
    with pytest.raises(TypeError):
        je.combine_context([], [], None, None, None, "", [(6, "delegated", 900, 800)])


def test_combine_context_six_positional_arg_form_unchanged_pin():
    # The same call form the live test_journal_echo_escalation.py pin
    # exercises (6 positional arguments, fallback_marker="MARKER"
    # positionally) -- the result must stay byte-for-byte unchanged
    # after adding notes_len_events.
    ev = (5, "attempt", "t-042", 3)
    ctx = je.combine_context([], [], None, None, [ev], "MARKER")
    assert ctx == je.build_escalation_segment([ev]) + "; MARKER"


def test_combine_context_all_empty_yields_empty_string():
    assert je.combine_context([], [], None, None, None, "", notes_len_events=None) == ""


def test_combine_context_notes_len_between_escalation_and_marker():
    esc_ev = (5, "attempt", "t-042", 3)
    notes_ev = (6, "delegated", 900, 800)
    ctx = je.combine_context([], [], None, None, [esc_ev], "MARKER", notes_len_events=[notes_ev])
    assert ctx == (je.build_escalation_segment([esc_ev]) + "; "
                   + je.build_notes_len_segment([notes_ev]) + "; MARKER")


def test_combine_context_full_order_and_header_literal():
    # B19 -- order of all segments: violations first (header literal
    # unchanged), notes_len between escalation and marker, marker last.
    violations = ["v"]
    tier_ev = (2, "mismatch", "fable", {"m": 1})
    witness_ev = ("warn_soft", 3)
    ts_ev = (4, "future", 10.0)
    esc_ev = (5, "attempt", "t-1", 3)
    notes_ev = (6, "delegated", 900, 800)
    ctx = je.combine_context(violations, [tier_ev], [witness_ev], [ts_ev], [esc_ev], "MARKER",
                              notes_len_events=[notes_ev])
    assert ctx.startswith("JOURNAL ECHO: 1 defect(s) in new lines: ")
    assert ctx.endswith("MARKER")
    i_journal = ctx.index("JOURNAL ECHO")
    i_tier = ctx.index("TIER ECHO")
    i_witness = ctx.index("WITNESS ECHO")
    i_ts = ctx.index("TS DRIFT")
    i_esc = ctx.index("ESCALATION")
    i_notes = ctx.index("NOTES LEN")
    i_marker = ctx.rindex("MARKER")
    assert i_journal < i_tier < i_witness < i_ts < i_esc < i_notes < i_marker


# =======================================================================
# main() end-to-end -- subprocess smoke
# =======================================================================


def test_echo_noteslen_e2e_800_silent(tmp_path):
    # B1, end-to-end
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * threshold
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:d1")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_noteslen_e2e_801_warns(tmp_path):
    # B2, end-to-end
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:d1")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert "NOTES LEN" in ctx
    assert f"notes {threshold + 1} chars" in ctx
    assert f"threshold {threshold}" in ctx


def test_echo_noteslen_e2e_never_blocks_no_permission_decision(tmp_path):
    # B20
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    notes = "x" * (threshold + 1)
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:d1")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "permissionDecision" not in hook_output
    assert "permissionDecision" not in result.stderr
    assert "deny" not in result.stderr


def test_echo_noteslen_non_journal_path_silent(tmp_path):
    # B14
    other_file = tmp_path / "not-a-journal.txt"
    other_file.write_text("irrelevant content", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(other_file))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_noteslen_earlier_uncommitted_long_line_outside_scope_silent(tmp_path):
    # B12 -- regression pin of the same class the sibling layers already
    # cover: line A (long) was added EARLIER (not by this call -- it's
    # already part of originalFile), line B (added by this call) is
    # short and clean -> zero NOTES LEN events.
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    line_a = _line(event="delegated", notes="x" * (threshold + 500), task_id="t-002",
                    model="sonnet", worker_ref="cli:a")
    after_call_a = HEAD_TEXT + line_a + "\n"
    line_b = _line(event="delegated", notes="short and clean", task_id="t-003",
                    model="sonnet", worker_ref="cli:b")
    journal_path.write_text(after_call_a + line_b + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=after_call_a))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_noteslen_fallback_disables_layer_entirely(tmp_path):
    # B13 -- used_fallback==True -> the layer is fully disabled, zero
    # events, even when notes is genuinely longer than the threshold;
    # the fallback marker still prints as usual (visible alongside
    # another defect -- an empty category makes JOURNAL ECHO visible).
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    bad_line = _line(event="delegated", notes="x" * (threshold + 500), task_id="t-002",
                      model="sonnet", worker_ref="cli:a", category="")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    payload = _post_tool_use_payload(journal_path)  # no original_file -> fallback engaged
    result = _run_hook(payload)
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "NOTES LEN" not in ctx
    assert je.FALLBACK_MARKER_TEXT in ctx


def test_echo_noteslen_giant_notes_one_message_not_bloated(tmp_path):
    # B15 -- adversarial: notes 200000 chars -- exactly one message, the
    # segment isn't bloated, no notes fragment leaks into the text.
    journal_path = _seed_committed_journal(tmp_path)
    marker_inside = "SECRET_MARKER_SHOULD_NOT_LEAK_INTO_MESSAGE"
    notes = marker_inside + ("y" * 200000)
    new_line = _line(event="delegated", notes=notes, task_id="t-002", model="sonnet", worker_ref="cli:giant")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert ctx.count("NOTES LEN") == 1
    assert marker_inside not in ctx
    assert len(ctx) < 1000


def test_echo_noteslen_control_chars_and_nonascii_notes_no_crash(tmp_path):
    # B16 -- control chars and non-ASCII in notes -- valid stdout JSON,
    # the hook doesn't crash on either channel.
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    weird_notes = "\x01\x02\x03" + ("control-mix-текст " * 60)
    assert len(weird_notes) > threshold
    new_line = _line(event="delegated", notes=weird_notes, task_id="t-002", model="sonnet",
                      worker_ref="cli:weird")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "NOTES LEN" in ctx
    assert ctx.isascii()  # json.dumps(ensure_ascii=True) on stdout


def test_echo_noteslen_batch_200_lines_100_long_ceiling_and_more_suffix(tmp_path):
    # B17 -- a batch of 200 lines, 100 long -- 5 messages + "; +95 more".
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    long_notes = "x" * (threshold + 1)
    lines = []
    for i in range(200):
        notes = long_notes if i % 2 == 0 else "short"
        lines.append(_line(event="delegated", notes=notes, task_id=f"t-{i + 2:03d}",
                            model="sonnet", worker_ref=f"cli:batch-{i}"))
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert ctx.count("NOTES LEN") == je.MAX_NOTES_LEN_LINES
    assert "; +95 more" in ctx


def test_echo_noteslen_combined_with_defect_one_context(tmp_path):
    # A form defect (empty category) + NOTES LEN together -- both
    # segments in one additionalContext, joined by "; " -- the same
    # combined pattern the sibling layers already exercise for their own.
    journal_path = _seed_committed_journal(tmp_path)
    threshold = je.NOTES_LEN_THRESHOLDS_CHARS["delegated"]
    bad_line = _line(event="delegated", notes="x" * (threshold + 1), task_id="t-002",
                      model="sonnet", worker_ref="cli:d1", category="")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path, original_file=HEAD_TEXT))
    assert result.returncode == 0
    ctx = _parse_stdout_json(result.stdout)["additionalContext"]
    assert "JOURNAL ECHO" in ctx
    assert "NOTES LEN" in ctx
    assert "; NOTES LEN" in ctx
