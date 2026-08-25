"""Tests for the R3 MIRROR layer -- a warn-only guard on the write path
against a builder `accepted` line carrying neither a critic input nor a
"critic: skipped, <reason>" concession, implemented in
toolkit/tools/journal_echo.py (see its "R3 MIRROR" section for the full
design). WARN at write time, NEVER a block (this logic does not enter
journal_validator.decide()).

GAP: CLAUDE.md's acceptance-gate rule (critic is a mandatory acceptance
gate above a diff-size threshold, or waived by "critic: skipped,
<reason>") was held only by the acceptor's discipline at write time --
nothing on the write path detected a builder `accepted` line carrying
neither signal.

Style -- mirrors toolkit/tools/test_journal_echo_escalation.py (a
sibling echo layer of the same class): pure logic
(_collect_r3_events/_check_accepted_r3/_format_r3_line/
build_r3_segment) + a subprocess smoke test of main() through real
tmp_path git repos, plus a dedicated battery for the new stdout-deadline
helper (_write_stdout_deadline/_stdout_deadline_seconds) this same task
adds. Helpers (journal lines) are duplicated locally (the same
self-containment preference this toolkit's other test files already
document).

Covers:
 K1 signals S1-S5 per-test (silences + a negative twin) + the M2 detector.
 K2 the M1/M2 message texts verbatim (a literal-text pin).
 K3 process invariants (never blocks, silence check membership, the
    combine_context keyword-only barrier, segment order).
 K4 edges (missing/whitespace task_id, notes None, basis variants, agent
    filter, repeated task_id, retro NOT exempted, used_fallback runs
    the layer regardless, an empty/broken journal).
 K5 adversarial battery (skip-literal variants, non-matching phrasing,
    a special-char/huge/non-ASCII task_id, malformed JSON lines, a
    large batch capped with "+K more").
 K6 limits AT and BEYOND the boundary (rule 6a): MAX_R3_LINES,
    MAX_MESSAGE_LEN, MAX_R3_BYTES.
 K7 a fixed regression fixture (test_journal_echo_r3_fixture.jsonl)
    exercising every signal/edge together in one batch.
 K8 the stdout-deadline helper this task also adds to journal_echo.py:
    a non-draining consumer returns False within the deadline, a
    draining consumer returns True with full content delivered, env
    deadline parsing at/beyond its own boundary.

NOT ported from the reference deployment's sibling test file (out of
this task's scope, see the builder's report): a retro-measurement
battery against that deployment's OWN historical journal incidents (no
equivalent history exists here) and a dual-target sibling/live module
switch (this layer landed directly in the live journal_echo.py, no
staged-sibling file was ever used here).

Run from the repo root: python -m pytest toolkit/tools/test_journal_echo_r3.py -q
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import journal_echo as je  # noqa: E402

SCRIPT = TOOLS_DIR / "journal_echo.py"
FIXTURE = TOOLS_DIR / "test_journal_echo_r3_fixture.jsonl"


# =======================================================================
# helpers -- journal lines (pure-logic tests, no ts needed --
# _collect_r3_events never looks at ts at all)
# =======================================================================


def _l(event="accepted", agent="builder", task_id="t-001", **kw) -> str:
    obj = {"event": event, "agent": agent, "task_id": task_id}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


def _raw(**kw) -> str:
    """Builds a line WITHOUT the automatic event/agent/task_id -- for
    edge tests that need FULL control over the key set (e.g. "task_id
    is missing entirely")."""
    return json.dumps(kw, ensure_ascii=False)


def _accepted_events(new_lines, base_lines=()):
    return je._collect_r3_events(list(new_lines), list(base_lines))


def _kinds(events):
    return [(e[1], e[2]) for e in events]


# =======================================================================
# K1 -- signals S1-S5 per-test: silence + a negative twin
# =======================================================================


def test_s1_basis_critic_with_matching_delegation_fully_silent():
    base = [_l(event="delegated", agent="critic", task_id="t-001")]
    new = [_l(event="accepted", agent="builder", task_id="t-001", basis="critic")]
    assert _accepted_events(new, base) == []


def test_s1_basis_critic_without_delegation_suppresses_m1_but_m2_fires():
    # S1 silences M1 (no_input) unconditionally; M2 (phantom_basis) is
    # an INDEPENDENT detector, firing precisely because S1 is true and
    # there is no delegation.
    new = [_l(event="accepted", agent="builder", task_id="t-001", basis="critic")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-001")]


def test_s1_negative_twin_no_basis_warns_m1():
    new = [_l(event="accepted", agent="builder", task_id="t-001")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-001")]


def test_s2_notes_skip_silent():
    new = [_l(task_id="t-002", notes="critic: skipped, small diff")]
    assert _accepted_events(new) == []


def test_s2_negative_twin_unrelated_notes_warns():
    new = [_l(task_id="t-002", notes="just a regular note, no concession")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-002")]


def test_s3_delegated_critic_in_base_lines_silent():
    base = [_l(event="delegated", agent="critic", task_id="t-003")]
    new = [_l(task_id="t-003")]
    assert _accepted_events(new, base) == []


def test_s3_delegated_critic_after_accepted_in_same_batch_silent():
    # The batch is scanned in BOTH directions -- a critic delegation
    # AFTER the accepted line in the same batch also silences (a
    # pre-pass).
    new = [
        _l(task_id="t-003"),
        _l(event="delegated", agent="critic", task_id="t-003"),
    ]
    assert _accepted_events(new) == []


def test_s3_negative_twin_no_delegation_anywhere_warns():
    new = [_l(task_id="t-003")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-003")]


def test_s3_case_sensitive_task_id_does_not_match():
    base = [_l(event="delegated", agent="critic", task_id="T-500")]
    new = [_l(task_id="t-500")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-500")]


def test_s3_same_task_id_delegated_agent_not_critic_still_warns():
    base = [_l(event="delegated", agent="builder", task_id="t-003")]
    new = [_l(task_id="t-003")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-003")]


def test_s4_basis_judge_silences_unconditionally():
    # basis=="judge" silences EVEN with no critic delegation -- the M2
    # detector applies only to basis=="critic".
    new = [_l(task_id="t-004", basis="judge")]
    assert _accepted_events(new) == []


def test_s4_negative_twin_no_basis_warns():
    new = [_l(task_id="t-004")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-004")]


# =======================================================================
# M2 detector -- an isolated positive/negative pair
# =======================================================================


def test_m2_phantom_basis_positive():
    new = [_l(task_id="t-005", basis="critic")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-005")]


def test_m2_negative_twin_matching_delegation_no_phantom():
    base = [_l(event="delegated", agent="critic", task_id="t-005")]
    new = [_l(task_id="t-005", basis="critic")]
    assert _accepted_events(new, base) == []


# =======================================================================
# S5 -- a bare critic:t-NNN token in notes silences M1 AND M2, ONLY if
# t-NNN exists in the file as delegated(agent=critic).
# =======================================================================


def test_s5_valid_token_silences_m1():
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", notes="closes:t-005 critic:t-609 done")]
    assert _accepted_events(new, base) == []


def test_s5_invalid_token_does_not_silence_m1():
    # The token cites t-609, but there is no delegated(critic) with
    # that id in the file.
    new = [_l(task_id="t-006", notes="critic:t-609 done")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-006")]


def test_s5_valid_token_silences_m2_as_alternative_to_delegation():
    # M2's closing text: "close with a critic:t-NNN token ... OR a
    # delegated record" -- S5 is valid for basis="critic" even with no
    # direct delegation under this SAME task_id (the bundling pattern).
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", basis="critic", notes="critic:t-609")]
    assert _accepted_events(new, base) == []


def test_s5_invalid_token_does_not_silence_m2():
    new = [_l(task_id="t-006", basis="critic", notes="critic:t-999")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-006")]


def test_s5_cross_task_id_by_construction_unlike_s3():
    # S5 is explicitly CROSS-task_id (unlike S3, which requires the
    # SAME task_id) -- t-609 in the token is NOT equal to the line's own
    # task_id (t-006).
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", notes="critic:t-609")]
    assert _accepted_events(new, base) == []


def test_s5_multiple_tokens_any_valid_silences():
    base = [_l(event="delegated", agent="critic", task_id="t-609")]
    new = [_l(task_id="t-006", notes="critic:t-001 critic:t-609 critic:t-002")]
    assert _accepted_events(new, base) == []


# =======================================================================
# Priority: basis=critic with no delegation and no S5, but WITH the
# concession literal in notes -- M2 is correct (S2 does not silence a
# contradictory record).
# =======================================================================


def test_priority_basis_critic_plus_concession_literal_no_delegation_gives_m2():
    new = [_l(task_id="t-007", basis="critic", notes="critic: skipped, tiny diff")]
    events = _accepted_events(new)
    assert _kinds(events) == [("phantom_basis", "t-007")]


def test_task_id_empty_string_skips_line():
    new = [_l(task_id="")]
    assert _accepted_events(new) == []


def test_task_id_whitespace_only_skips_line():
    new = [_l(task_id="   ")]
    assert _accepted_events(new) == []


def test_task_id_whitespace_only_in_delegated_critic_not_absorbed():
    # The same check applies on the critic-presence side: a
    # delegated(critic) with a whitespace-only task_id does NOT enter
    # critic_task_ids.
    base = [_l(event="delegated", agent="critic", task_id="   ")]
    new = [_l(task_id="t-008")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-008")]


# =======================================================================
# K2 -- the M1/M2 texts verbatim
# =======================================================================


def test_m1_message_literal_text():
    event = (7, "no_input", "t-042", None)
    text = je._format_r3_line(event, ascii_only=False)
    expected = (
        "R3 MIRROR: line 7 accepted builder t-042: no critic "
        "input under this id and no concession - class-completeness review "
        "will read this acceptance as self-certification; close with "
        "delegated(critic) for t-042 / a critic:t-NNN token on the "
        'covering verdict / "critic: skipped, <reason>" (acceptor strictly '
        "above)"
    )
    assert text == expected


def test_m2_message_literal_text():
    event = (9, "phantom_basis", "t-777", None)
    text = je._format_r3_line(event, ascii_only=False)
    expected = (
        "R3 MIRROR: line 9 basis=critic for t-777, no "
        "delegated(critic) under this task_id - basis is not traceable; "
        "close with a critic:t-NNN token on the covering verdict OR a "
        "delegated record"
    )
    assert text == expected


def test_r3_literal_prefix_pinned():
    m1 = je._format_r3_line((1, "no_input", "t-1", None), False)
    m2 = je._format_r3_line((1, "phantom_basis", "t-1", None), False)
    assert m1.startswith("R3 MIRROR: line ")
    assert m2.startswith("R3 MIRROR: line ")


# =======================================================================
# K3 -- process invariants
# =======================================================================


class _FakeStdin:
    def __init__(self, data: bytes):
        import io
        self.buffer = io.BytesIO(data)


def _run_main_inprocess(payload_bytes: bytes, monkeypatch) -> int:
    monkeypatch.setattr(je.sys, "stdin", _FakeStdin(payload_bytes))
    return je.main()


def test_main_never_blocks_on_garbage_input(monkeypatch, capsys):
    rc = _run_main_inprocess(b"not even json{{{", monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert "permissionDecision" not in out.out


def test_r3_logic_not_in_journal_validator_decide():
    import inspect
    source = inspect.getsource(je.journal_validator.decide)
    assert "r3" not in source.lower()
    assert "R3 MIRROR" not in source


def test_full_silence_non_journal_path(monkeypatch, capsys):
    payload = json.dumps({
        "session_id": "s1", "cwd": ".", "tool_name": "Edit",
        "tool_input": {"file_path": "not-the-journal.txt"},
        "tool_response": {},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == ""


def test_r3_events_joins_the_same_silence_check_as_siblings():
    # A structural pin of main()'s source: r3_events must live in the
    # SAME `if (not violations and not tier_events and ...)` expression
    # as every other source, not a separate condition.
    import inspect
    source = inspect.getsource(je.main)
    match = re.search(r"if \(not violations.*?\):\s*\n\s*return 0", source, re.DOTALL)
    assert match is not None, "silence-check `if` block not found in main() source"
    block = match.group(0)
    for name in ("violations", "tier_events", "witness_visible", "ts_drift_events",
                 "escalation_events", "notes_len_events", "r3_events"):
        assert f"not {name}" in block, f"{name} missing from the shared silence check"


def test_combine_context_six_positional_arg_form_unchanged():
    # The same pin test_journal_echo_escalation.py /
    # test_journal_echo_noteslen.py already carry -- r3_events is added
    # strictly keyword-only, the six-positional call form stays
    # byte-for-byte unchanged.
    ev = (5, "attempt", "t-042", 3)
    ctx = je.combine_context([], [], None, None, [ev], "MARKER")
    assert ctx == je.build_escalation_segment([ev]) + "; MARKER"


def test_r3_events_keyword_only_enforced():
    with pytest.raises(TypeError):
        je.combine_context([], [], None, None, None, "", [(1, "no_input", "t-1", None)])


def test_r3_events_none_default_equivalent_to_absent():
    a = je.combine_context([], [])
    b = je.combine_context([], [], r3_events=None)
    assert a == b == ""


def test_r3_segment_last_content_before_fallback_marker():
    violations = ["bad line"]
    tier_events = []
    r3_ev = (3, "no_input", "t-9", None)
    ctx = je.combine_context(
        violations, tier_events, None, None, None, "MARKER",
        notes_len_events=[(2, "delegated", 900, 800)],
        r3_events=[r3_ev],
    )
    notes_len_idx = ctx.index("NOTES LEN")
    r3_idx = ctx.index("R3 MIRROR")
    marker_idx = ctx.index("MARKER")
    assert notes_len_idx < r3_idx < marker_idx


def test_build_context_header_unchanged():
    ctx = je.combine_context(["bad"], [])
    assert ctx.startswith("JOURNAL ECHO: 1 defect(s) in new lines: ")


def test_malformed_json_line_does_not_abort_collection():
    new = [
        "not json at all {{{",
        '"just a string"',
        "42",
        _l(task_id="t-010"),
    ]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-010")]


def test_collector_exception_falls_back_to_empty_list(monkeypatch, tmp_path):
    # The outer try/except in main() around _collect_r3_events -- a
    # second fail-open layer. The collector is broken unconditionally on
    # a REAL journal path (otherwise main() would return before ever
    # calling the collector, and the monkeypatch would prove nothing);
    # main() must continue without crashing (return 0), the r3 segment
    # simply absent.
    def _boom(new_lines, base_lines):
        raise RuntimeError("boom")
    monkeypatch.setattr(je, "_collect_r3_events", _boom)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    journal_path.write_text(_l(task_id="t-021") + "\n", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0


# =======================================================================
# K4 -- edges
# =======================================================================


def test_edge_task_id_missing_skips_line_entirely():
    new = [_raw(event="accepted", agent="builder")]
    assert _accepted_events(new) == []


def test_edge_task_id_non_string_skips_line_entirely():
    new = [_raw(event="accepted", agent="builder", task_id=12345)]
    assert _accepted_events(new) == []


def test_edge_notes_none_treated_as_no_signal():
    new = [_l(task_id="t-011", notes=None)]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-011")]


def test_edge_basis_missing_falls_through_to_s2_s3():
    new = [_l(task_id="t-012", notes="critic: skipped, tiny")]
    assert _accepted_events(new) == []  # S2 still applies


def test_edge_basis_queued_to_lead_does_not_silence():
    new = [_l(task_id="t-013", basis="queued-to-lead")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-013")]


def test_edge_agent_not_builder_silent():
    for agent in ("critic", "fable", "designer"):
        new = [_l(task_id="t-014", agent=agent)]
        assert _accepted_events(new) == [], agent


def test_edge_repeated_accepted_same_task_id_each_independent_no_signal():
    new = [_l(task_id="t-015"), _l(task_id="t-015")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-015"), ("no_input", "t-015")]


def test_edge_repeated_accepted_same_task_id_each_independent_with_delegation():
    base = [_l(event="delegated", agent="critic", task_id="t-015")]
    new = [_l(task_id="t-015"), _l(task_id="t-015")]
    assert _accepted_events(new, base) == []


def test_edge_retro_not_exempted():
    # Unlike WITNESS ECHO, this layer gives NO retro exemption.
    new = [_l(task_id="t-016", notes="retroactive accepted, retro fixup")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-016")]


def test_edge_used_fallback_layer_emits_r3_warning(monkeypatch, tmp_path, capsys):
    # used_fallback -> this layer RUNS (the TIER/WITNESS/ESCALATION
    # family, NOT the NOTES-LEN family). tmp_path is not a git repo ->
    # _get_head_text -> None -> the HEAD-diff fallback engages trivially
    # (used_fallback=True).
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    journal_path.write_text(_l(task_id="t-017") + "\n", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    captured = capsys.readouterr()
    assert je.FALLBACK_MARKER_TEXT in captured.err
    assert "R3 MIRROR" in captured.err
    assert "t-017" in captured.err


def test_edge_empty_journal_silent():
    assert _accepted_events([]) == []


def test_edge_non_journal_payload_early_exit(monkeypatch, capsys, tmp_path):
    other = tmp_path / "not-a-journal.txt"
    other.write_text("x", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(other)},
        "tool_response": {},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_edge_r3xr13_collision_s4_silences():
    new = [_l(task_id="t-018", basis="judge")]
    assert _accepted_events(new) == []


def test_edge_witness_field_ignored():
    new = [_l(task_id="t-019", witness="BATCH CANON: 4066 passed, 0 failed")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-019")]


# =======================================================================
# K5 -- adversarial battery
# =======================================================================


def test_battery_skip_in_witness_not_notes_still_warns():
    new = [_l(task_id="t-b1", witness="critic: skipped, small", notes="unrelated")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b1")]


@pytest.mark.parametrize("notes", [
    "critic: skipped",
    "Critic: Skipped",
    "critic:   skipped",
    "critic:skipped",
])
def test_battery_skip_variants_silence(notes):
    new = [_l(task_id="t-b2", notes=notes)]
    assert _accepted_events(new) == []


@pytest.mark.parametrize("notes", [
    "critic: skip",
    "no critic",
    "critic waived",
])
def test_battery_non_matching_phrasing_still_warns(notes):
    new = [_l(task_id="t-b3", notes=notes)]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b3")]


def test_battery_task_id_with_special_chars_sanitized_not_crashing():
    tid = "t-1  ; DROP TABLE"
    new = [_l(task_id=tid)]
    events = _accepted_events(new)
    line = je._format_r3_line(events[0], ascii_only=False)
    assert je._raw_sanitize(tid) in line


def test_battery_task_id_10000_chars_truncated():
    tid = "t-" + ("x" * 10000)
    new = [_l(task_id=tid)]
    events = _accepted_events(new)
    line = je._format_r3_line(events[0], ascii_only=False)
    assert je._raw_sanitize(tid) in line
    assert tid not in line
    assert len(je._raw_sanitize(tid)) == je.MAX_MESSAGE_LEN


def test_battery_non_ascii_task_id_both_channels():
    tid = "t-задача-42"
    new = [_l(task_id=tid)]
    events = _accepted_events(new)
    raw_line = je._format_r3_line(events[0], ascii_only=False)
    ascii_line = je._format_r3_line(events[0], ascii_only=True)
    assert tid in raw_line
    assert tid not in ascii_line
    assert "?" in ascii_line


def test_battery_non_object_json_skipped():
    new = ["42", "[1, 2, 3]", '"a string"', _l(task_id="t-b7")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b7")]


def test_battery_truncated_json_skipped_next_line_lives():
    new = ['{"event": "accepted", "agent": "builder"', _l(task_id="t-b8")]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b8")]


def test_battery_basis_non_string_not_a_signal():
    new = [_raw(event="accepted", agent="builder", task_id="t-b9", basis=123)]
    events = _accepted_events(new)
    assert _kinds(events) == [("no_input", "t-b9")]


def test_battery_event_agent_non_string_outside_trigger():
    new = [
        _raw(event=123, agent="builder", task_id="t-b10a"),
        _raw(event="accepted", agent=123, task_id="t-b10b"),
    ]
    assert _accepted_events(new) == []


def test_battery_batch_200_capped_at_max_r3_lines_rest_counted():
    # With this kit's short, ASCII M1 texts, MAX_R3_LINES=5 binds
    # BEFORE MAX_R3_BYTES=2600 for a typical short task_id (measured:
    # see test_limit_max_r3_lines_binds_before_bytes_for_typical_short_
    # task_id below) -- unlike the reference deployment's much longer,
    # non-ASCII-escaped M1/M2 texts, where the byte ceiling binds first.
    # The collector itself stays UNCAPPED (all 200 events); the segment
    # caps at MAX_R3_LINES with "+K more" for the rest.
    new = [_l(task_id=f"t-{i:03d}") for i in range(200)]
    events = _accepted_events(new)
    assert len(events) == 200  # collector itself uncapped
    seg = je.build_r3_segment(events)
    assert seg.count("R3 MIRROR") == je.MAX_R3_LINES
    assert seg.endswith(f"+{200 - je.MAX_R3_LINES} more")
    assert je._json_wire_len(seg) < je.MAX_R3_BYTES


def test_battery_strict_case_sensitive_task_id_warns():
    base = [_l(event="delegated", agent="critic", task_id="T-500")]
    new = [_l(task_id="t-500")]
    events = _accepted_events(new, base)
    assert _kinds(events) == [("no_input", "t-500")]


def test_battery_empty_file_silent():
    assert _accepted_events([]) == []


def test_battery_non_journal_payload_early_exit(monkeypatch, capsys, tmp_path):
    other = tmp_path / "unrelated.md"
    other.write_text("x", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(other)},
        "tool_response": {},
    }).encode("utf-8")
    rc = _run_main_inprocess(payload, monkeypatch)
    assert rc == 0
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


# =======================================================================
# K6 -- limits AT and BEYOND the boundary (rule 6a)
# =======================================================================


def test_limit_max_r3_lines_exactly_5_no_more_suffix():
    events = [(i, "no_input", f"t-{i:03d}", None) for i in range(1, je.MAX_R3_LINES + 1)]
    seg = je.build_r3_segment(events)
    assert seg.count("R3 MIRROR") == je.MAX_R3_LINES
    assert "more" not in seg


def test_limit_max_r3_lines_6_gives_plus_1_more():
    events = [(i, "no_input", f"t-{i:03d}", None) for i in range(1, je.MAX_R3_LINES + 2)]
    seg = je.build_r3_segment(events)
    assert seg.count("R3 MIRROR") == je.MAX_R3_LINES
    assert seg.endswith("+1 more")


def test_limit_max_message_len_exactly_500_whole():
    tid = "t-" + ("a" * 498)  # total length exactly 500
    assert len(tid) == 500
    assert je._raw_sanitize(tid) == tid


def test_limit_max_message_len_501_truncated():
    tid = "t-" + ("a" * 499)  # total length 501
    assert len(tid) == 501
    sanitized = je._raw_sanitize(tid)
    assert len(sanitized) == 500
    assert sanitized == tid[:500]


def test_limit_max_message_len_10000_truncated():
    tid = "t-" + ("a" * 9998)
    assert len(tid) == 10000
    sanitized = je._raw_sanitize(tid)
    assert len(sanitized) == je.MAX_MESSAGE_LEN


def _greedy_fit_count(line: str, cap: int) -> int:
    """How many COPIES of line fit in build_r3_segment by the SAME
    greedy measure (_json_wire_len of the accumulated body, joined by
    "; "), up to min(cap, MAX_R3_LINES) -- mirrors build_r3_segment
    literally, so tests aren't pinned to a specific magic line count
    (robust against future edits to the M1/M2 text length)."""
    total = 0
    count = 0
    while count < min(cap, je.MAX_R3_LINES):
        add = je._json_wire_len(line) + (2 if count else 0)
        if count and total + add > je.MAX_R3_BYTES:
            break
        total += add
        count += 1
    return count


def _two_line_body_bytes(tid_len: int):
    """The combined json-wire footprint of TWO IDENTICAL M1 lines with
    task_id "t-" + "a"*tid_len -- the SAME measure (_json_wire_len)
    build_r3_segment uses internally. Returns (bytes, tid)."""
    tid = "t-" + ("a" * tid_len)
    line = je._format_r3_line((1, "no_input", tid, None), False)
    body = "; ".join([line, line])
    return je._json_wire_len(body), tid


def test_limit_max_r3_bytes_boundary_at_and_beyond():
    # Programmatic search (no magic number): grow task_id until the
    # combined wire footprint of two lines reaches EXACTLY the
    # MAX_R3_BYTES ceiling (AT the boundary -- both lines visible, no
    # "+K more"), then one extra ASCII letter (+1 byte exactly) --
    # BEYOND the boundary (truncated to 1 line + "+1 more"). Robust
    # against future edits to the M1/M2 text length -- the boundary is
    # searched, not hardcoded.
    tid_len = 1
    bytes_at, tid_at = _two_line_body_bytes(tid_len)
    while bytes_at < je.MAX_R3_BYTES:
        tid_len += 1
        bytes_at, tid_at = _two_line_body_bytes(tid_len)
    if bytes_at > je.MAX_R3_BYTES:
        tid_len -= 1
        bytes_at, tid_at = _two_line_body_bytes(tid_len)
    assert bytes_at <= je.MAX_R3_BYTES, "could not construct an AT-boundary case"

    events_at = [(1, "no_input", tid_at, None), (2, "no_input", tid_at, None)]
    seg_at = je.build_r3_segment(events_at)
    assert seg_at.count("R3 MIRROR") == 2
    assert "more" not in seg_at

    # BEYOND the boundary: the same task_id + one ASCII letter --
    # guaranteed +1 byte per occurrence (task_id appears twice in the M1
    # text), the sum strictly > MAX_R3_BYTES.
    tid_over = tid_at + "a"
    events_over = [(1, "no_input", tid_over, None), (2, "no_input", tid_over, None)]
    seg_over = je.build_r3_segment(events_over)
    assert seg_over.count("R3 MIRROR") == 1
    assert seg_over.endswith("+1 more")


def test_limit_max_r3_lines_binds_before_bytes_for_typical_short_task_id():
    # FINDING (measured, not assumed -- see the builder's report): with
    # this kit's short, ASCII M1 text, MAX_R3_LINES=5 binds BEFORE
    # MAX_R3_BYTES=2600 for a typical short task_id ("t-001" etc.) --
    # all 5 lines fit comfortably under the byte ceiling. This is the
    # OPPOSITE of the reference deployment's own measured behavior
    # (there, the byte ceiling binds first, because its M1/M2 texts are
    # longer and non-ASCII-escaped to ~6 bytes/char on the wire) -- a
    # direct, expected consequence of this port's much shorter texts,
    # not a divergent implementation. The number is checked dynamically
    # (_greedy_fit_count mirrors build_r3_segment literally), not
    # hardcoded to "5".
    m1_line = je._format_r3_line((1, "no_input", "t-001", None), False)
    fit = _greedy_fit_count(m1_line, cap=je.MAX_R3_LINES)
    assert fit == je.MAX_R3_LINES, (
        "assumption stale: a typical short task_id no longer fits all "
        "MAX_R3_LINES lines under the byte cap -- update this test (and "
        "the finding note in the builder's report) if M1's text grew"
    )
    events = [(i, "no_input", f"t-{i:03d}", None) for i in range(1, je.MAX_R3_LINES + 1)]
    seg = je.build_r3_segment(events)
    assert seg.count("R3 MIRROR") == fit
    assert "more" not in seg
    assert je._json_wire_len(seg) < je.MAX_R3_BYTES


# =======================================================================
# K7 -- a fixed regression fixture exercising every signal/edge together
# =======================================================================


def test_k7_fixture_marks_exactly_the_expected_lines():
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    lines = [ln for ln in lines if ln.strip()]
    base = lines[:1]  # line 1: delegated(critic, t-100) -- pre-existing history
    new = lines[1:]   # lines 2-16: one PostToolUse batch
    events = je._collect_r3_events(new, base)
    assert [(e[0], e[1], e[2]) for e in events] == [
        (3, "phantom_basis", "t-101"),
        (9, "no_input", "t-106"),
        (10, "no_input", "t-107"),
        (13, "no_input", "t-109"),
        (14, "phantom_basis", "t-105"),
        (16, "no_input", "t-111"),
    ]


# =======================================================================
# K8 -- stdout-deadline helper (_write_stdout_deadline/
# _stdout_deadline_seconds). Real OS pipes (os.pipe()), NOT a mock -- a
# non-draining consumer exists only at the level of the real OS.
# =======================================================================


def _make_blocking_pipe_writer():
    """A real OS pipe -- the read end is NOT drained, a write beyond the
    OS buffer's capacity blocks inside write() until the deadline."""
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "r", encoding="utf-8", newline="")
    writer = os.fdopen(write_fd, "w", encoding="utf-8", newline="")
    return reader, writer


def _best_effort_release_pipe(reader, writer):
    try:
        reader.close()
    except Exception:
        pass
    time.sleep(0.05)
    try:
        writer.close()
    except Exception:
        pass


def test_stdout_deadline_non_draining_consumer_returns_false_within_deadline(monkeypatch):
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(je.sys, "stdout", writer)
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, "0.3")
    big_text = "x" * 200_000  # comfortably over any realistic OS pipe capacity
    t0 = time.monotonic()
    result = je._write_stdout_deadline(big_text)
    elapsed = time.monotonic() - t0
    assert result is False
    assert 0.25 <= elapsed < 1.3, f"should return within deadline+margin, took {elapsed:.3f}s"
    _best_effort_release_pipe(reader, writer)


def test_stdout_deadline_draining_consumer_returns_true_full_content_delivered(monkeypatch):
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(je.sys, "stdout", writer)
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, "3.0")
    big_text = "y" * 200_000
    collected = []

    def _drain():
        while True:
            chunk = reader.read(65536)
            if not chunk:
                break
            collected.append(chunk)

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()
    result = je._write_stdout_deadline(big_text)
    assert result is True
    writer.close()
    drainer.join(timeout=5)
    assert not drainer.is_alive(), "drainer thread did not see EOF in time"
    assert "".join(collected) == big_text
    reader.close()


@pytest.mark.parametrize(
    "raw_value,expected_is_default",
    [
        ("", True),
        ("abc", True),
        ("0", True),
        ("-1", True),
        ("601", True),
        ("600", False),
        ("0.1", False),
        ("5", False),
    ],
)
def test_stdout_deadline_env_parsing_branches(raw_value, expected_is_default, monkeypatch):
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, raw_value)
    result = je._stdout_deadline_seconds()
    if expected_is_default:
        assert result == je._STDOUT_DEADLINE_DEFAULT
    else:
        assert result == float(raw_value)


def test_stdout_deadline_env_absent_uses_default(monkeypatch):
    monkeypatch.delenv(je._STDOUT_DEADLINE_ENV, raising=False)
    assert je._stdout_deadline_seconds() == je._STDOUT_DEADLINE_DEFAULT == 5.0


def test_stdout_deadline_small_valid_deadline_blocking_write_returns_false(monkeypatch):
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(je.sys, "stdout", writer)
    monkeypatch.setenv(je._STDOUT_DEADLINE_ENV, "0.1")
    big_text = "z" * 200_000
    t0 = time.monotonic()
    result = je._write_stdout_deadline(big_text)
    elapsed = time.monotonic() - t0
    assert result is False
    assert elapsed < 1.0, f"a 0.1s deadline should return well under 1s, took {elapsed:.3f}s"
    _best_effort_release_pipe(reader, writer)


# =======================================================================
# WITNESS -- a subprocess-measured stdout byte count for a realistic
# 4-line "no critic input" case (a real subprocess, not an in-process
# import; stdout is drained normally -- this is a volume measurement,
# not the blocking test above).
# =======================================================================


def test_witness_four_lines_stdout_byte_count(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    journal_path = logs_dir / "routing-log.jsonl"
    lines = [json.dumps({
        "event": "accepted", "agent": "builder", "model": "sonnet",
        "task_id": f"t-{600 + i}", "category": "implementation", "by": "opus",
        "witness": "python -m pytest toolkit/tools/ -q -> 100 passed",
        "notes": "Acceptance with no critic input and no concession note -- a realistic record.",
    }, ensure_ascii=False) for i in range(4)]
    journal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    payload = json.dumps({
        "session_id": "s1", "cwd": str(tmp_path), "tool_name": "Edit",
        "tool_input": {"file_path": str(journal_path)},
        "tool_response": {"filePath": str(journal_path), "success": True},
    })
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15,
    )
    assert result.returncode == 0
    stdout_bytes = len(result.stdout)
    print(f"WITNESS: 4 accepted/builder lines with no critic input -> stdout bytes = {stdout_bytes}")
    assert stdout_bytes < 4096, (
        f"stdout for the 4-line no-input case is {stdout_bytes} B -- expected "
        "comfortably under the measured pipe-capacity class (4096 B)"
    )
