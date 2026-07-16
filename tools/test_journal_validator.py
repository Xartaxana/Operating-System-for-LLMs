"""Tests for tools/journal_validator.py (t-031). Style mirrors
tools/test_mechanism_gate.py: decide() is a pure function, tested
directly with synthetic staged/head text -- no git needed for most
cases. One integration test at the bottom exercises the real git
wiring (is_journal_staged / get_staged_text / get_head_text) against a
real tmp_path git repo, and one exercises main()'s exit-2 crash path.

Run from the repo root: python -m pytest tools/test_journal_validator.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

try:
    import journal_validator_d0076 as jv
except ImportError:
    import journal_validator as jv

NOW = jv.datetime.datetime(2026, 7, 10, 12, 0, 0)


def _line(event="delegated", ts="2026-07-10T08:00:00", agent="builder",
          category="implementation", notes="note",
          worker_ref="cli:2026-07-10T08:00:00", **kw) -> str:
    obj = {"ts": ts, "event": event, "agent": agent, "category": category, "notes": notes,
           "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(event="delegated", task_id="t-001", model="sonnet", ts="2026-07-10T08:00:00")
HEAD_TEXT = HEAD_LINE + "\n"


def _staged(*new_lines: str) -> str:
    return HEAD_TEXT + "".join(l + "\n" for l in new_lines)


# ---- not staged at all -> main() must exit 0 silently (tested separately below) ----

# ---- positive case: valid new lines pass clean ----

def test_positive_case_valid_new_lines_pass(tmp_path):
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002", model="sonnet",
              notes="delegating t-002"),
        _line(event="accepted", ts="2026-07-10T08:20:00", agent="builder", task_id="t-002",
              model="sonnet", witness="pytest ... 1 passed", by="opus",
              notes="accepted t-002"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0
    assert violations == []


# ---- 1. append-only ----

def test_append_only_violation_when_existing_line_modified():
    tampered_head = json.loads(HEAD_LINE)
    tampered_head["notes"] = "rewritten"
    staged = json.dumps(tampered_head, ensure_ascii=False) + "\n"
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("append-only" in v for v in violations)


def test_append_only_violation_when_lines_removed():
    code, violations = jv.decide("", HEAD_TEXT, NOW)
    assert code == 1
    assert any("append-only" in v for v in violations)


# ---- 2. required fields ----

def test_missing_required_field_notes_fails():
    obj = json.loads(_line(event="dispatch_skipped", ts="2026-07-10T08:10:00",
                            agent="scout", category="recon", notes="x"))
    del obj["notes"]
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("notes" in v for v in violations)


def test_invalid_json_line_fails():
    staged = HEAD_TEXT + "{not valid json\n"
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("невалидный JSON" in v for v in violations)


# ---- 3. event enum ----

def test_unknown_event_fails():
    staged = _staged(_line(event="reticulated", ts="2026-07-10T08:10:00", agent="lead",
                            category="x", notes="x"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("enum" in v for v in violations)


# ---- 4. model required ----

def test_model_missing_for_delegated_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                            notes="no model"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("'model'" in v for v in violations)


# ---- 5. task_id required + format ----

def test_task_id_missing_for_delegated_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            notes="no task_id"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("'task_id'" in v for v in violations)


def test_task_id_bad_format_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-2", notes="bad format"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("формату t-NNN" in v for v in violations)


# ---- 5b. worker_ref required for delegated (D-0076) ----

def test_delegated_missing_worker_ref_fails():
    obj = json.loads(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", notes="no worker_ref"))
    del obj["worker_ref"]
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("worker_ref" in v for v in violations)


def test_delegated_empty_worker_ref_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", worker_ref="", notes="empty worker_ref"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("worker_ref" in v for v in violations)


def test_delegated_whitespace_worker_ref_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", worker_ref="   ", notes="whitespace worker_ref"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("worker_ref" in v for v in violations)


def test_delegated_nonstring_worker_ref_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", worker_ref=123, notes="nonstring worker_ref"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("worker_ref" in v for v in violations)


def test_delegated_valid_worker_ref_passes():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", worker_ref="cli:2026-07-10T08:10:00",
                            notes="valid worker_ref"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_escalated_needs_no_worker_ref():
    obj = json.loads(_line(event="escalated", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", notes="escalated, no worker_ref"))
    del obj["worker_ref"]
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


# ---- 6. rejected: attempt / failure_class ----

def test_rejected_invalid_attempt_and_failure_class_fail():
    staged = _staged(_line(event="rejected", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", attempt=0,
                            failure_class="mystery", by="opus", notes="bad rejected"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("'attempt'" in v for v in violations)
    assert any("'failure_class'" in v for v in violations)


# ---- 7. accepted + agent=builder: witness ----

def test_accepted_builder_missing_witness_fails():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", by="opus",
                            notes="no witness"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("'witness'" in v for v in violations)


# ---- 8. defect_found: ref ----

def test_defect_found_missing_ref_fails():
    staged = _staged(_line(event="defect_found", ts="2026-07-10T08:10:00", agent="builder",
                            task_id="t-001", notes="late defect"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("'ref'" in v for v in violations)


# ---- 9. task_id novelty / reference ----

def test_delegated_novelty_violation_wrong_number():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-005", notes="skipped ahead"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("новизна task_id" in v for v in violations)


def test_delegated_novelty_correct_max_plus_one_passes():
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", notes="correct next id"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_accepted_references_nonexistent_task_id_fails():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-099", witness="w", by="opus",
                            notes="dangling ref"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("не ссылается" in v for v in violations)


def test_accepted_can_reference_task_id_delegated_earlier_in_same_commit():
    # t-002 delegated and then accepted in the SAME staged batch -- rule 9
    # allows referencing task_ids introduced earlier in this very commit,
    # not only ones already in HEAD.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet", task_id="t-002",
              notes="new task"),
        _line(event="accepted", ts="2026-07-10T08:20:00", agent="builder", model="sonnet",
              task_id="t-002", witness="w", by="opus", notes="accept same-commit task"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


# ---- 9 (Lead correction, live precedent): re-delegated task_id --
# a/b/v legal, two g negatives (t-029 dup pattern; delegated after accepted) ----

def test_9a_new_task_max_plus_one_passes():
    # (a) restated for clarity alongside b/v/g below: a brand-new task_id
    # equal to max+1 is legal regardless of any b/v/g machinery.
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                            task_id="t-002", notes="new task, case a"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_9b_continuation_dispatch_different_agent_passes():
    # (b) t-001 delegated to builder in HEAD; task is still open (no
    # accepted yet); a NEW delegated on the SAME task_id but a DIFFERENT
    # agent (critic acceptance-gate entry) is legal with no attempt/
    # rejected needed -- exactly the t-027 precedent (builder then critic).
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001",
                            notes="critic-gate continuation dispatch, case b"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_9v_retry_after_rejected_with_attempt_passes():
    # (v) t-001 rejected, then re-delegated to the SAME agent (builder)
    # WITH attempt>=2 -- legal retry.
    staged = _staged(
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="opus", notes="first attempt rejected"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2, notes="retry after rejection, case v"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_9g_duplicate_pattern_t029_same_agent_no_attempt_no_rejected_fails():
    # (g) negative #1: the actual t-029 defect -- same agent re-delegated
    # on an open task_id, no attempt field, no rejected above. Must FAIL.
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", notes="t-029-class duplicate"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("запрещённый дубль" in v for v in violations)


def test_9g_delegated_after_accepted_fails_reopen_forbidden():
    # (g) negative #2: task_id already closed (accepted above) -- a new
    # delegated on it is a forbidden reopen (D-0060: treat as two tasks),
    # regardless of which agent issues it.
    head_with_accept = HEAD_TEXT + _line(
        event="accepted", ts="2026-07-10T08:05:00", agent="builder", model="sonnet",
        task_id="t-001", witness="pytest ok", by="opus", notes="t-001 already accepted",
    ) + "\n"
    staged = head_with_accept + _line(event="delegated", ts="2026-07-10T08:10:00", agent="critic",
                                       model="opus", task_id="t-001", notes="reopen attempt") + "\n"
    code, violations = jv.decide(staged, head_with_accept, NOW)
    assert code == 1
    assert any("reopen запрещён" in v for v in violations)


# ---- 9в2 (2026-07-15): replaces_worker -- dead-worker replacement branch ----

def test_9v2_replaces_worker_valid_marker_passes():
    # t-001 delegated to builder in HEAD with worker_ref "agent:OLD". A new
    # delegated on the SAME task_id, SAME agent, no attempt, no rejected --
    # but notes carry "replaces_worker:agent:OLD" referencing the exact
    # worker_ref of the prior delegated line. Legal replacement.
    head = HEAD_TEXT.replace("cli:2026-07-10T08:00:00", "agent:OLD")
    staged = head + _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder",
                           model="sonnet", task_id="t-001", worker_ref="agent:NEW",
                           notes="критик остановлен без вердикта, продолжает новый воркер "
                                 "replaces_worker:agent:OLD") + "\n"
    code, violations = jv.decide(staged, head, NOW)
    assert code == 0, violations


def test_9v2_replaces_worker_unknown_handle_fails():
    # marker present but the claimed prior worker_ref was never used for
    # this task_id -- protection against fake replacement (DoD #2).
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", worker_ref="agent:NEW",
                            notes="replaces_worker:agent:NEVER_EXISTED"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("фиктивная замена запрещена" in v for v in violations)
    assert any("replaces_worker" in v for v in violations)


def test_9g_duplicate_without_marker_still_fails_regression_and_hints_replaces_worker():
    # regression: plain duplicate (no marker, no attempt, no rejected) must
    # STILL fail (DoD #1 "дубль без маркера -- отказ"), and the failure
    # message must now hint at replaces_worker (DoD #3).
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", notes="t-029-class duplicate, no marker"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("запрещённый дубль" in v for v in violations)
    assert any("replaces_worker" in v for v in violations)


def test_9v2_replacement_then_normal_accepted_passes():
    # DoD #4: replacement followed later by a normal accepted on the same
    # task_id passes cleanly (task_id reference / closure logic unaffected).
    head = HEAD_TEXT.replace("cli:2026-07-10T08:00:00", "agent:OLD")
    staged = head + "".join(l + "\n" for l in (
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", worker_ref="agent:NEW",
              notes="replaces_worker:agent:OLD"),
        _line(event="accepted", ts="2026-07-10T08:20:00", agent="builder", model="sonnet",
              task_id="t-001", witness="pytest ... 1 passed", by="opus",
              notes="accepted after worker replacement"),
    ))
    code, violations = jv.decide(staged, head, NOW)
    assert code == 0, violations


def test_9v2_marker_with_wrong_agent_still_uses_case_b_not_marker():
    # sanity: a DIFFERENT agent continuation-dispatch (case b) stays legal
    # with or without a replaces_worker marker -- marker logic must not
    # interfere with the pre-existing (b) path.
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001",
                            notes="critic-gate continuation, unrelated replaces_worker text ignored"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


# ---- 9в2 adversarial regression locks (t-129 M3, critic t-127 session) ----

def test_9v2_replaces_worker_marker_does_not_save_reopen_of_closed_task():
    # (a) task_id t-001 is CLOSED (accepted above it in HEAD). A new
    # delegated on it carries a VALID replaces_worker marker (handle
    # matches the prior delegated's worker_ref exactly) -- must still
    # FAIL: reopen is forbidden regardless of the marker (checked before
    # the marker branch in validate_new_lines -- closed_tasks gate wins).
    head_with_accept = HEAD_TEXT + _line(
        event="accepted", ts="2026-07-10T08:05:00", agent="builder", model="sonnet",
        task_id="t-001", witness="pytest ok", by="opus", notes="t-001 already accepted",
    ) + "\n"
    staged = head_with_accept + _line(
        event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
        task_id="t-001", worker_ref="agent:NEW",
        notes="replaces_worker:cli:2026-07-10T08:00:00",  # matches HEAD_LINE's worker_ref exactly
    ) + "\n"
    code, violations = jv.decide(staged, head_with_accept, NOW)
    assert code == 1
    assert any("reopen запрещён" in v for v in violations)


def test_9v2_replaces_worker_self_reference_fails():
    # (b) the marker on the NEW delegated line references that SAME
    # line's OWN worker_ref, not a prior one. The replaced worker must
    # come from the past -- self-reference must FAIL as a fake
    # replacement (the new line's own worker_ref is only harvested into
    # task_worker_refs AFTER this line's checks run).
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", worker_ref="agent:SELF",
                            notes="replaces_worker:agent:SELF"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("фиктивная замена запрещена" in v for v in violations)
    assert any("replaces_worker" in v for v in violations)


# ---- 10. ts monotonicity / no narrative future ----

def test_ts_not_monotonic_relative_to_previous_new_line_fails():
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:20:00", model="sonnet", task_id="t-002",
              notes="later"),
        _line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet", task_id="t-003",
              notes="earlier than previous new line"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("не монотонен" in v for v in violations)


def test_ts_earlier_than_last_head_line_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T07:00:00", model="sonnet",
                            task_id="t-002", notes="before HEAD's last ts"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("не монотонен" in v for v in violations)


def test_ts_narrative_future_beyond_now_plus_10min_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-11T00:00:00", model="sonnet",
                            task_id="t-002", notes="far future (F-29)"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("F-29" in v for v in violations)


def test_ts_within_10min_future_grace_passes():
    staged = _staged(_line(event="delegated", ts="2026-07-10T12:05:00", model="sonnet",
                            task_id="t-002", notes="clock skew grace"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


# ---- 11. D-0058 acceptance matrix ----

def test_matrix_missing_by_fails():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", witness="w",
                            notes="no by field"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("'by'" in v for v in violations)


def test_matrix_scout_accepted_by_same_tier_without_basis_fails():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku",
                            notes="peer accepting peer, no basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("D-0058" in v for v in violations)


def test_matrix_scout_accepted_by_higher_tier_passes():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="opus",
                            notes="opus accepts scout"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_matrix_scout_accepted_same_tier_with_basis_passes():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku", basis="queued-to-lead",
                            notes="basis fallback"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_matrix_non_claude_by_requires_basis():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="gemini-2.5-flash",
                            notes="non-Claude by, no basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("D-0058" in v for v in violations)


def test_matrix_non_claude_by_with_basis_critic_passes():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="gemini-2.5-flash",
                            basis="critic", notes="non-Claude by, critic basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_matrix_agent_lead_needs_only_presence_of_by():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="lead",
                            model="fable", task_id="t-001", by="haiku",
                            notes="lead-tier accept, matrix not applied"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_matrix_rejected_only_needs_by_present_no_tier_check():
    # literal reading of the spec: tier/basis check text only names
    # "accepted"; rejected carries 'by' without a further tier/basis gate.
    staged = _staged(_line(event="rejected", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", attempt=1, failure_class="recon",
                            by="haiku", notes="rejected, same-tier by, no basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


# ---- HEAD empty (first-ever commit / fresh deploy) ----

def test_empty_head_first_delegated_must_be_t001():
    staged = _line(event="delegated", ts="2026-07-10T08:00:00", model="sonnet", task_id="t-001",
                   notes="very first task") + "\n"
    code, violations = jv.decide(staged, "", NOW)
    assert code == 0


def test_empty_head_no_lower_ts_bound():
    staged = _line(event="delegated", ts="2020-01-01T00:00:00", model="sonnet", task_id="t-001",
                   notes="old ts, no HEAD to compare against") + "\n"
    code, violations = jv.decide(staged, "", NOW)
    assert code == 0


# ---- crash path: main() fail-closed with exit 2 on unexpected exception ----

def test_main_crashes_exit_2_with_traceback(monkeypatch, capsys):
    def _boom():
        raise RuntimeError("simulated crash, not a validation FAIL")

    monkeypatch.setattr(jv, "is_journal_staged", _boom)
    code = jv.main([])
    assert code == 2
    err = capsys.readouterr().err
    assert "Traceback" in err
    assert "simulated crash" in err


# ---- real git integration: not-staged -> exit 0 silently; staged violation -> exit 1 ----

def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def _init_repo(root: Path):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def test_main_exits_zero_when_journal_not_staged(tmp_path, capsys, monkeypatch):
    root = tmp_path
    _init_repo(root)
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text(HEAD_TEXT, encoding="utf-8")
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    # nothing staged now (working tree clean)
    monkeypatch.chdir(root)
    code = jv.main([])
    assert code == 0
    assert capsys.readouterr().out == ""


def test_main_exits_one_on_real_staged_violation(tmp_path, capsys, monkeypatch):
    root = tmp_path
    _init_repo(root)
    (root / "logs").mkdir()
    (root / "logs" / "routing-log.jsonl").write_text(HEAD_TEXT, encoding="utf-8")
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    bad_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-999", model="sonnet",
                      notes="wrong novelty")
    (root / "logs" / "routing-log.jsonl").write_text(_staged(bad_line), encoding="utf-8")
    _git(root, "add", "logs/routing-log.jsonl")
    monkeypatch.chdir(root)
    code = jv.main([])
    assert code == 1
    err = capsys.readouterr().err
    assert "FAILED validation" in err
    assert "новизна task_id" in err


# ---- t-151: STANDALONE mode -- no silent exit-0-without-a-check outside git ----
#
# Precedent (docs/tasks/2026-07-16_policy-as-code-design.md, exams #5-B/#6-B/
# #8-t3): in a non-git sandbox, is_journal_staged() used to swallow git's
# failure (nonzero returncode never checked) and main() exited 0 silently,
# with zero lines validated -- a false "valid". These tests lock the fix:
# (a) auto-detect in a directory that is NOT a git repo at all validates the
# WHOLE file and can fail; (b) --standalone forces the same path even inside
# a working git repo; (c) a missing journal file gets an honest string, not
# a bare 0; (d) the existing git-repo "nothing staged" no-op (item 4 of the
# spec -- explicitly must not change) stays silent, proven with a violation
# actually present on disk to show it is a real, load-bearing case, not a
# vacuous one.

def _write_journal(root: Path, text: str) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-log.jsonl").write_text(text, encoding="utf-8")


def test_standalone_autodetect_not_a_git_repo_clean_passes(tmp_path, capsys, monkeypatch):
    # tmp_path is deliberately NEVER `git init`-ed -- this is the exact
    # sandbox shape from the exam precedent.
    clean_text = HEAD_TEXT + _line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet",
                                    task_id="t-002", notes="second task, clean") + "\n"
    _write_journal(tmp_path, clean_text)
    monkeypatch.chdir(tmp_path)
    code = jv.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "STANDALONE MODE" in out
    assert "проверен весь файл, 2 строк" in out


def test_standalone_autodetect_not_a_git_repo_violations_fail(tmp_path, capsys, monkeypatch):
    # Same non-git sandbox, but the journal actually carries the precedent's
    # class of defect (accepted missing 'category') -- must be CAUGHT, not
    # silently passed.
    bad_text = HEAD_TEXT + _line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                                  model="sonnet", task_id="t-001", by="opus", witness="w",
                                  category=None, notes="accepted with null category") + "\n"
    _write_journal(tmp_path, bad_text)
    monkeypatch.chdir(tmp_path)
    code = jv.main([])
    assert code == 1
    captured = capsys.readouterr()
    out, err = captured.out, captured.err
    assert "STANDALONE MODE" in out
    assert "append-only не проверяем" in out
    assert "FAILED validation (standalone)" in err
    assert "category" in err


def test_standalone_autodetect_not_a_git_repo_git_binary_missing_too(tmp_path, capsys, monkeypatch):
    # Belt-and-braces: even if git IS on PATH but the specific check used by
    # _git_available() blows up (simulated FileNotFoundError, e.g. git
    # genuinely absent from the sandbox), standalone must still engage
    # rather than propagate the exception or fall through to a silent 0.
    clean_text = HEAD_TEXT
    _write_journal(tmp_path, clean_text)
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise FileNotFoundError("git: command not found")

    monkeypatch.setattr(jv.subprocess, "run", _boom)
    code = jv.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "STANDALONE MODE" in out


def test_standalone_no_journal_file_is_honest_not_silent(tmp_path, capsys, monkeypatch):
    # No logs/ directory at all -- not the precedent's failure mode, but the
    # DoD explicitly calls out this must be an honest printed fact, not a
    # bare, unexplained exit 0.
    monkeypatch.chdir(tmp_path)
    code = jv.main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "нет файла журнала" in out


def test_standalone_forced_flag_overrides_inside_real_git_repo(tmp_path, capsys, monkeypatch):
    root = tmp_path
    _init_repo(root)
    _write_journal(root, HEAD_TEXT)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    # Modify the file on disk WITHOUT staging it -- normal mode would ignore
    # this entirely (see regression test below). --standalone must still
    # catch it, reading straight off disk.
    bad_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-999", model="sonnet",
                      notes="wrong novelty, unstaged")
    (root / "logs" / "routing-log.jsonl").write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    monkeypatch.chdir(root)
    code = jv.main(["--standalone"])
    assert code == 1
    captured = capsys.readouterr()
    out, err = captured.out, captured.err
    assert "STANDALONE MODE" in out
    assert "новизна task_id" in err


def test_standalone_forced_flag_clean_journal_passes_in_real_git_repo(tmp_path, capsys, monkeypatch):
    root = tmp_path
    _init_repo(root)
    _write_journal(root, HEAD_TEXT)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    monkeypatch.chdir(root)
    code = jv.main(["--standalone"])
    assert code == 0
    out = capsys.readouterr().out
    assert "STANDALONE MODE" in out
    assert "проверен весь файл, 1 строк" in out


def test_git_repo_nothing_staged_stays_silent_zero_even_with_violation_on_disk(tmp_path, capsys, monkeypatch):
    # Regression lock for spec item 4: a REAL git repo where git works fine
    # but the journal simply isn't staged in THIS commit must NOT switch to
    # standalone just because "nothing is staged" -- that is the existing,
    # explicitly-protected no-op (nothing to check in this commit, not "git
    # is unavailable"). Proven with an actual violation sitting unstaged on
    # disk, so this is not a vacuous pass.
    root = tmp_path
    _init_repo(root)
    _write_journal(root, HEAD_TEXT)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    bad_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-999", model="sonnet",
                      notes="wrong novelty, unstaged, no --standalone")
    (root / "logs" / "routing-log.jsonl").write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    # deliberately NOT `git add`-ed
    monkeypatch.chdir(root)
    code = jv.main([])
    assert code == 0
    assert capsys.readouterr().out == ""


def test_git_available_helper_true_in_real_repo(tmp_path, monkeypatch):
    root = tmp_path
    _init_repo(root)
    monkeypatch.chdir(root)
    assert jv._git_available() is True


def test_git_available_helper_false_outside_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # never git-init'ed
    assert jv._git_available() is False
