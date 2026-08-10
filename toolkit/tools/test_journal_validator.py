"""Tests for tools/journal_validator.py. Style mirrors
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
    assert any("invalid JSON" in v for v in violations)


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
    assert any("t-NNN format" in v for v in violations)


# ---- 5b. worker_ref required for delegated ----

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
    assert any("task_id novelty" in v for v in violations)


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
    assert any("does not reference" in v for v in violations)


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
# a/b/v legal, two g negatives (a real duplicate-delegation defect once
# found in a production journal; delegated after accepted) ----

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
    # rejected needed -- exactly the pattern a real critic-gate
    # continuation dispatch needs (builder then critic).
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


def test_9g_duplicate_pattern_same_agent_no_attempt_no_rejected_fails():
    # (g) negative #1: an actual defect once found in a production
    # journal -- same agent re-delegated
    # on an open task_id, no attempt field, no rejected above. Must FAIL.
    staged = _staged(_line(event="delegated", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", notes="duplicate delegation, no attempt/rejected"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("forbidden duplicate" in v for v in violations)


# ---- 9c2. dead-worker replacement (replaces_worker marker) ----


def test_9c2_replaces_worker_matching_prior_ref_passes():
    # t-001 delegated to builder in HEAD with worker_ref
    # "cli:2026-07-10T08:00:00" (see HEAD_LINE's default worker_ref).
    # A NEW delegated by the SAME agent, no attempt, no rejected above
    # -- but notes carry a replaces_worker marker whose handle matches
    # that exact worker_ref -- legal (a dead-worker replacement, not a
    # rule-6 retry).
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", worker_ref="cli:2026-07-10T08:10:00",
              notes="replaces_worker:cli:2026-07-10T08:00:00 (worker died, no verdict)")
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_9c2_replaces_worker_fabricated_handle_fails():
    # The claimed handle does not match ANY earlier delegated
    # worker_ref for this task_id -- a fabricated replacement, FAIL.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", worker_ref="cli:2026-07-10T08:10:00",
              notes="replaces_worker:cli:2026-07-10T07:00:00 (never happened)")
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("fabricated replacement" in v for v in violations)


def test_9c2_replaces_worker_matches_ref_from_a_different_agents_delegated_line():
    # Rule 9(c2) searches worker_ref across delegated lines of ANY
    # agent for this task_id, not only lines by the same agent as the
    # new one: a critic-entry's worker_ref can legitimately be claimed
    # as replaced by a later builder retry.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="critic", model="opus",
              task_id="t-001", worker_ref="agent:critic-1",
              notes="critic-gate continuation dispatch, case b"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", worker_ref="agent:critic-2",
              notes="replaces_worker:agent:critic-1 (critic-1 died mid-review)"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_9c2_replaces_worker_handle_from_unrelated_task_id_does_not_count():
    # A handle that is a real worker_ref, but for a DIFFERENT task_id,
    # must not satisfy rule 9(c2) for this one -- the prior-refs set
    # is scoped per task_id.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", model="sonnet", task_id="t-002",
              worker_ref="cli:2026-07-10T08:10:00", notes="unrelated task"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="builder", model="sonnet",
              task_id="t-001", worker_ref="cli:2026-07-10T08:20:00",
              notes="replaces_worker:cli:2026-07-10T08:10:00 (wrong task's ref)"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("fabricated replacement" in v for v in violations)


def test_9c2_replaces_worker_does_not_require_attempt_field():
    # rule 9(c2) explicitly does not require attempt to grow -- a bare
    # replaces_worker marker with no attempt field at all is legal.
    obj = json.loads(
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", worker_ref="cli:2026-07-10T08:10:00",
              notes="replaces_worker:cli:2026-07-10T08:00:00")
    )
    assert "attempt" not in obj
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_9c2_replaces_worker_takes_priority_over_plain_duplicate_fail():
    # Sanity: without the marker, the same shape of line fails as a
    # plain duplicate (case d) -- proves the c2 test above is actually
    # exercising the marker branch, not some other path to a pass.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", notes="no replaces_worker marker here at all")
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("forbidden duplicate" in v for v in violations)


def test_9g_delegated_after_accepted_fails_reopen_forbidden():
    # (g) negative #2: task_id already closed (accepted above) -- a new
    # delegated on it is a forbidden reopen (treated as two tasks),
    # regardless of which agent issues it.
    head_with_accept = HEAD_TEXT + _line(
        event="accepted", ts="2026-07-10T08:05:00", agent="builder", model="sonnet",
        task_id="t-001", witness="pytest ok", by="opus", notes="t-001 already accepted",
    ) + "\n"
    staged = head_with_accept + _line(event="delegated", ts="2026-07-10T08:10:00", agent="critic",
                                       model="opus", task_id="t-001", notes="reopen attempt") + "\n"
    code, violations = jv.decide(staged, head_with_accept, NOW)
    assert code == 1
    assert any("reopen forbidden" in v for v in violations)


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
    assert any("not monotonic" in v for v in violations)


def test_ts_earlier_than_last_head_line_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-10T07:00:00", model="sonnet",
                            task_id="t-002", notes="before HEAD's last ts"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("not monotonic" in v for v in violations)


def test_ts_narrative_future_beyond_now_plus_10min_fails():
    staged = _staged(_line(event="delegated", ts="2026-07-11T00:00:00", model="sonnet",
                            task_id="t-002", notes="far future (narrative-future timestamp)"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("narrative-future" in v for v in violations)


def test_ts_within_10min_future_grace_passes():
    staged = _staged(_line(event="delegated", ts="2026-07-10T12:05:00", model="sonnet",
                            task_id="t-002", notes="clock skew grace"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


# ---- 11. role-vs-tier acceptance matrix ----

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
    assert any("role-vs-tier" in v for v in violations)


def test_matrix_scout_accepted_by_higher_tier_passes():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="opus",
                            notes="opus accepts scout"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0


def test_matrix_scout_accepted_same_tier_with_basis_now_fails_below_sonnet_floor():
    # CORRECTED: this used to assert code==0 under an old, bare membership
    # check ("basis in BASIS_VALUES", no by/agent pair check) -- the exact
    # class of hole a live leak exposed (queued-to-lead passing membership
    # regardless of WHICH by/agent). by="haiku" is a KNOWN tier strictly
    # below sonnet -- "Role != tier"
    # matrix: "below Sonnet: no coordination is provided for" -- no basis
    # rescues it now.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku", basis="queued-to-lead",
                            notes="basis fallback -- now illegal, by below sonnet"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v for v in violations)


def test_matrix_model_id_in_by_fails_as_unknown_tier():
    # RENAMED (a critic verdict): the old names/claims here were stale.
    # (a) test_matrix_non_claude_by_with_basis_critic_passes asserted
    # code==0 for a full model id in "by" with basis="critic" -- that was
    # EXACTLY the hole this revision closes, and became a
    # verbatim duplicate of test_b7_1_sonnet_by_builder_agent_critic_basis_ok
    # once "by" was corrected to a legal tier word -- deleted, no
    # information lost. (b) this test (test_matrix_non_claude_by_requires_basis)
    # asserted "requires basis" as if that were still a distinct rule --
    # it is not: a full model id in "by" is now simply an UNKNOWN-TIER
    # value, and fails identically WITH or WITHOUT basis (the enum gate
    # runs before any basis is even inspected). A model id belongs in
    # "model", never in "by" -- "by" is always a bare TIER_ORDER keyword,
    # even for non-Claude workers.
    staged_no_basis = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                                     model="sonnet", task_id="t-001", witness="w",
                                     by="gemini-2.5-flash",
                                     notes="model id in by, no basis -- unknown tier, not 'requires basis'"))
    code, violations = jv.decide(staged_no_basis, HEAD_TEXT, NOW)
    assert code == 1
    assert any("is not a known tier" in v for v in violations), violations

    staged_critic_basis = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                                         model="sonnet", task_id="t-001", witness="w",
                                         by="gemini-2.5-flash", basis="critic",
                                         notes="model id in by, critic basis -- still unknown tier, still fails"))
    code, violations = jv.decide(staged_critic_basis, HEAD_TEXT, NOW)
    assert code == 1
    assert any("is not a known tier" in v for v in violations), violations


# ---- an unknown "by" fails the role-vs-tier matrix UNCONDITIONALLY --
# a "by" outside TIER_ORDER is never legalized by any basis, including
# "judge"; the enum/shape check runs BEFORE every branch of
# _matrix_d0058_violation. ----

def test_unknown_by_fails_even_with_critic_basis():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="banana",
                            basis="critic", notes="unknown by, critic basis -- must fail"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("is not a known tier" in v and "banana" in v for v in violations), violations


def test_unknown_by_case_sensitive_fails_not_via_queued_to_lead_branch():
    # "Sonnet" (capitalized) is NOT the same key as "sonnet" in
    # TIER_ORDER -- case sensitivity is part of the enum check itself,
    # not a separate rule; must fail via the unknown-by branch, not
    # the queued-to-lead pair-message (rule e).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="Sonnet", basis="queued-to-lead",
                            notes="capitalized by -- unknown tier, not the legal 'sonnet'"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("is not a known tier" in v for v in violations), violations
    assert not any("queued-to-lead" in v for v in violations), violations


def test_unknown_by_fails_before_judge_branch_even_on_leaf_category():
    # the enum/shape check runs BEFORE basis=="judge" is even inspected
    # -- an unknown by fails even on a leaf-class category, where judge
    # would otherwise be by-independent.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="banana",
                            basis="judge", category="implementation",
                            notes="unknown by, judge basis, leaf category -- still fails"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("is not a known tier" in v for v in violations), violations
    assert not any("leaf-class dispatch" in v for v in violations), violations


def test_boundary_fable_known_tier_still_passes_via_ok_tier():
    obj = json.loads(_line(event="accepted", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001", by="fable",
                            notes="fable is a KNOWN tier -- ok_tier unaffected"))
    assert "basis" not in obj
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_boundary_haiku_known_tier_floor_message_unchanged():
    # regression pin: "haiku" IS a known tier (present in TIER_ORDER) --
    # the unknown-by branch must NOT fire for it; the pre-existing
    # floor message (rule c) still names it, byte-for-byte unchanged.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="haiku",
                            basis="critic", notes="known tier below sonnet -- floor, not the new branch"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("tier below sonnet" in v for v in violations), violations
    assert not any("is not a known tier" in v for v in violations), violations


# ---- role-vs-tier pair-legality table --
# membership-in-set replaced by legality-per-(by, agent)-pair, after a
# live leak (two different sonnet-tier coordinators accepted sonnet-class
# (builder) results via basis=queued-to-lead -- the validator at the
# time checked basis only by set membership). ----

def test_pair_sonnet_by_builder_agent_critic_basis_ok():
    # (1) by=sonnet/agent=builder/basis=critic -> OK (critic-tier opus is
    # strictly above builder-tier sonnet).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="sonnet",
                            basis="critic", notes="case 1: builder accepted by sonnet with critic basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_pair_sonnet_by_builder_agent_queued_to_lead_fails():
    # (2) by=sonnet/agent=builder/basis=queued-to-lead -> FAIL -- a
    # sonnet-tier coordinator accepting a sonnet-class (builder) result
    # via the "queued-to-lead" escape hatch, which the matrix reserves
    # for critic-class work only.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="sonnet",
                            basis="queued-to-lead",
                            notes="case 2: builder accepted by sonnet via queued-to-lead"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v and "queued-to-lead" in v and "builder" in v and "sonnet" in v
               for v in violations), violations


def test_pair_sonnet_by_critic_agent_queued_to_lead_ok():
    # (3) by=sonnet/agent=critic/basis=queued-to-lead -> OK (critic-class
    # work queued to the Lead through a sonnet coordinator is legal).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001", by="sonnet", basis="queued-to-lead",
                            notes="case 3: critic accepted by sonnet via queued-to-lead"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b7_4_opus_by_critic_agent_queued_to_lead_ok():
    # (4) by=opus/agent=critic/basis=queued-to-lead -> OK (equal tier,
    # the matrix explicitly allows the queue for critic-class work at an
    # opus coordinator).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001", by="opus", basis="queued-to-lead",
                            notes="B7 case 4: critic accepted by opus via queued-to-lead"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b7_5_opus_by_builder_agent_no_basis_ok_via_ok_tier():
    # (5) by=opus/agent=builder, no basis at all -> OK (ok_tier: opus
    # strictly above builder-tier sonnet -- no basis needed).
    obj = json.loads(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="opus",
                            notes="B7 case 5: builder accepted by opus, no basis, ok_tier"))
    assert "basis" not in obj
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b7_6_haiku_by_scout_agent_critic_basis_fork_decision_fails():
    # (6) by=haiku/agent=scout/basis=critic -- THE decision fork named in
    # the dispatch: the core rule's literal text ("OR the decision
    # carries a higher tier's input (a critic verdict)") would read this
    # as legal (critic-tier opus IS strictly above scout-tier haiku,
    # satisfying the basis="critic" rule in isolation). But the Role !=
    # tier matrix's "below Sonnet" row says, without exception, "no
    # coordination is provided for" -- a haiku-tier session is not a
    # functioning coordinator at all in this structure, regardless of
    # what verdict got attached to its acceptance event. DECISION
    # (documented per the dispatch's explicit instruction not to resolve
    # this silently): the floor wins -- FAIL. Both quotes:
    #   core: "the decision carries a higher tier's input (a critic
    #   verdict)"
    #   matrix: "| below Sonnet | no coordination is provided for | -- |"
    # Implemented as the FLOOR (checked before the basis=="critic"
    # branch) so it takes precedence for any by with a KNOWN tier
    # strictly below sonnet -- i.e. by=="haiku" specifically. basis==
    # "judge" is the one carve-out (checked first, unaffected by this
    # floor -- t-276/toolkit-native leaf-judge pairs with by=haiku remain
    # legal, see test_matrix_judge_basis_passes_on_recon_category above).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku", basis="critic",
                            notes="B7 case 6 (decision fork): scout accepted by haiku with critic basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v and "haiku" in v for v in violations), violations


def test_b7_boundary_fable_by_critic_agent_ok_via_ok_tier_no_basis_needed():
    # boundary companion to case 5/e: by=fable/agent=critic needs no
    # basis at all -- ok_tier alone covers it (fable strictly above opus).
    obj = json.loads(_line(event="accepted", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001", by="fable",
                            notes="fable accepts critic, no basis, ok_tier"))
    assert "basis" not in obj
    staged = _staged(json.dumps(obj, ensure_ascii=False))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b7_boundary_sonnet_by_critic_agent_no_basis_fails():
    # boundary companion to case 3: SAME pair (by=sonnet, agent=critic)
    # WITHOUT queued-to-lead -- must still FAIL (equal tier, no rescuing
    # basis at all).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001", by="sonnet",
                            notes="critic accepted by sonnet, no basis at all"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v for v in violations), violations


def test_b7_boundary_haiku_by_builder_agent_queued_to_lead_fails_floor():
    # boundary: by=haiku (known tier below sonnet) with agent=builder and
    # basis=queued-to-lead -- the floor fires before the queued-to-lead
    # branch is even reached; message must name the floor, not the
    # generic queued-to-lead pair message.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="haiku",
                            basis="queued-to-lead",
                            notes="builder accepted by haiku via queued-to-lead -- floor, not pair message"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("tier below sonnet" in v for v in violations), violations


def test_b7_boundary_haiku_by_judge_basis_leaf_still_passes_unaffected_by_floor():
    # boundary: by=haiku with basis=judge on a leaf category is NOT
    # touched by the new floor -- judge is checked first, independent of
    # by's tier (calibrated-judge acceptance is not a coordinator-tier
    # resolution at all). Regression lock alongside
    # test_matrix_judge_basis_passes_on_recon_category.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku", basis="judge",
                            category="recon", notes="judge on leaf, by=haiku -- floor does not apply"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


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


# ---- designer tier addendum (AGENT_TIER += "designer": "opus"):
# designer's deployment binding is opus (.claude/agents/designer.md),
# same tier as critic. ----

def test_matrix_designer_accepted_by_fable_passes():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="designer",
                            model="opus", task_id="t-001", by="fable",
                            notes="fable accepts designer's draft"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_designer_accepted_by_opus_without_basis_fails_equal_tier():
    # designer's own tier is opus (same as critic) -- an equal-tier
    # acceptance with no basis at all must still fail the matrix, same
    # class as test_matrix_scout_accepted_by_same_tier_without_basis_fails
    # above.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="designer",
                            model="opus", task_id="t-001", by="opus",
                            notes="peer accepting peer, no basis"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v for v in violations), violations


def test_matrix_agent_outside_agent_tier_regression_pin():
    # Regression pin: an agent name OUTSIDE AGENT_TIER (e.g. "analyst")
    # is documented, pre-existing behavior -- the matrix is simply not
    # defined for it (return None before any branch), unchanged by the
    # designer addition above.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="analyst",
                            model="haiku", task_id="t-001", by="haiku",
                            notes="agent outside AGENT_TIER -- matrix not applied"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


# ---- branch (5) queued-to-lead generalized to the upper-mid-tier CLASS
# (QUEUED_TO_LEAD_AGENTS = {critic, designer}), not the literal name
# "critic"; branch (1) judge narrowed to agent in {scout, builder} (a
# critic finding: designer+judge+category=implementation used to pass
# wrongly, since only category was checked, not agent). ----

def test_matrix_designer_by_opus_queued_to_lead_passes():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="designer",
                            model="opus", task_id="t-001", by="opus", basis="queued-to-lead",
                            notes="designer queued to Lead via an opus coordinator"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_designer_by_sonnet_queued_to_lead_passes():
    # the queue is legal from ANY coordinator tier not above designer's
    # own (sonnet here) -- same class as the existing critic/sonnet case.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="designer",
                            model="opus", task_id="t-001", by="sonnet", basis="queued-to-lead",
                            notes="designer queued to Lead via a sonnet coordinator"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_designer_by_opus_critic_basis_fails():
    # basis="critic" does NOT rescue designer -- critic (opus) is not
    # strictly above designer's own opus tier, same as it doesn't
    # rescue agent="critic" itself.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="designer",
                            model="opus", task_id="t-001", by="opus", basis="critic",
                            notes="designer accepted by opus via critic basis -- must fail"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v and "designer" in v for v in violations), violations
    # the fixed message names the ACTUAL agent and the actually-legal
    # path -- no stale advice about a literal agent='critic' path.
    assert not any("agent='critic'" in v for v in violations), violations


def test_matrix_designer_judge_basis_fails_regardless_of_category():
    for category in ("recon", "implementation", "review", None):
        kw = {} if category is None else {"category": category}
        staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="designer",
                                model="opus", task_id="t-001", by="opus", basis="judge",
                                notes="designer via judge -- must fail regardless of category",
                                **kw))
        code, violations = jv.decide(staged, HEAD_TEXT, NOW)
        assert code == 1, (category, violations)


def test_matrix_builder_judge_basis_implementation_still_passes_not_broken():
    # regression pin: the narrowing to agent in {scout, builder} must
    # not break the existing builder+judge+leaf-category path.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", witness="w", by="sonnet",
                            basis="judge", category="implementation",
                            notes="builder via judge on implementation -- still legal"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_scout_judge_basis_recon_still_passes_not_broken():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku",
                            basis="judge", category="recon",
                            notes="scout via judge on recon -- still legal"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_critic_judge_basis_leaf_category_now_fails():
    # a critic finding, adjacent surface: agent="critic" itself is ALSO
    # excluded from judge acceptance now (the review/spec class, not
    # just designer) -- even on an otherwise-leaf category.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="critic",
                            model="opus", task_id="t-001", by="opus",
                            basis="judge", category="implementation",
                            notes="critic via judge on implementation -- now fails"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations


# ---- 11b. basis "judge" -- legal ONLY on a leaf-class dispatch
# (category recon/implementation; this toolkit's own CLAUDE.md "Leaf
# routing" section -- see the module docstring's rule 11 NOTE for the
# empirical finding that the reference validator does not itself gate
# this, despite documenting the restriction). ----


def test_matrix_judge_basis_passes_on_recon_category():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="scout",
                            model="haiku", task_id="t-001", by="haiku", basis="judge",
                            category="recon", notes="judge accepts a recon leaf"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_judge_basis_passes_on_implementation_category():
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", by="sonnet", basis="judge",
                            category="implementation", witness="w",
                            notes="judge accepts an implementation leaf"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_matrix_judge_basis_fails_on_non_leaf_category():
    # boundary: "judge" is a KNOWN basis value, but the category on
    # THIS line is neither "recon" nor "implementation" -- must still
    # fail (a graph/review/mechanism-class dispatch is never
    # judge-acceptable).
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", by="sonnet", basis="judge",
                            category="review", witness="w",
                            notes="judge basis on a non-leaf category must fail"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v for v in violations)


def test_matrix_judge_basis_fails_when_category_missing():
    # a missing/invalid category is caught as its own separate form
    # defect (rule 2), but it must ALSO fail the leaf-class judge check
    # (category not in LEAF_CATEGORIES) rather than being silently
    # treated as a leaf by default.
    staged = _staged(_line(event="accepted", ts="2026-07-10T08:10:00", agent="builder",
                            model="sonnet", task_id="t-001", by="sonnet", basis="judge",
                            category="", witness="w",
                            notes="judge basis with an empty category must fail"))
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1
    assert any("role-vs-tier" in v for v in violations)


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
    assert "task_id novelty" in err


# =======================================================================
# The self/foreign-retry gap (rule 9c): "chuzhoi" (foreign) rejected --
# a rejected of an EXECUTOR does not, by itself, legalize a REVIEWER's
# repeat delegated on the same task_id; a foreign-retry entry is legal
# only with a new-version signal AFTER the re-entering agent's own last
# delegated. Self-retry (the same agent whose own result was rejected)
# stays unconditional, unchanged.
# =======================================================================


def test_b3_second_critic_entry_without_executor_rework_between_is_dup():
    # critic enters review (case b, first entry), then rejects builder's
    # result (rejected agent=builder) -- and tries a SECOND entry with
    # NOTHING reworked by builder in between (no new delegated builder,
    # no lead fix, no escalated). The unqualified old form would have
    # legalized this entry merely by the task carrying a rejected --
    # the fixed form must FAIL.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1, case b"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work"),
        _line(event="delegated", ts="2026-07-10T08:15:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 2, NO rework between -- must FAIL"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any('"foreign" rejected' in v for v in violations), violations


def test_b3_stale_rework_signal_from_earlier_round_does_not_legalize_next_round():
    # Round 1: builder reworks (own retry) AFTER critic's entry 1 -- a
    # valid "delegated of a different agent" signal, legalizing critic's
    # entry 2. Round 2: builder rejected AGAIN, critic tries a THIRD
    # entry citing the SAME (now stale, round-1) rework signal -- the
    # signal predates critic's entry-2 delegated (its own last
    # delegated), so it must NOT legalize round 2 -- FAIL.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="round 1 reject"),
        _line(event="delegated", ts="2026-07-10T08:15:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2, notes="builder self-retry -- also a rework SIGNAL for critic"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 2, legal via round-1 rework signal"),
        _line(event="rejected", ts="2026-07-10T08:25:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2, failure_class="spec", by="critic",
              notes="round 2 reject, no new rework signal since entry 2"),
        _line(event="delegated", ts="2026-07-10T08:30:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 3, citing STALE round-1 signal -- must FAIL"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any('"foreign" rejected' in v for v in violations), violations


def test_b3_self_retry_still_legal_without_any_other_agent_delegated_between():
    # (c-i) self-retry: builder rejected, then builder retries -- no
    # other agent delegated anywhere in between. Must stay legal
    # (unchanged class, a regression pin for the "as before" form).
    staged = _staged(
        _line(event="rejected", ts="2026-07-10T08:05:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="opus",
              notes="builder rejected"),
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2, notes="builder self-retry, nothing else happened between"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b3_new_delegated_of_different_agent_after_own_rejected_not_required():
    # (c-i) self-retry doesn't NEED a signal -- even though critic is
    # ALREADY present in this task's delegated_agents (entry 1),
    # builder's own retry after its OWN rejected does not require a
    # fresh critic delegated between the reject and the retry.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work"),
        _line(event="delegated", ts="2026-07-10T08:15:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2,
              notes="builder self-retry -- own rejected is enough, no fresh critic-delegated needed"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b3_lead_self_fix_rejected_signal_legalizes_review_round():
    # (c-ii) signal (2): a rejected event with agent=lead (a Lead
    # self-fix with no own delegated) counts as a new-version signal --
    # it legalizes critic's second entry even though nobody issued a
    # fresh delegated.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work"),
        _line(event="rejected", ts="2026-07-10T08:15:00", agent="lead", model="fable",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="Lead self-fixed the code directly, no own delegated -- the fix itself is the signal"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 2, legal via lead-self-fix signal"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b3_stale_lead_self_fix_signal_from_earlier_round():
    # Same staleness class as the rework-signal test, but with a
    # lead-self-fix signal: round 1's lead-fix legalizes entry 2, but
    # round 2's third entry cannot reuse that same, now-stale signal.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="round 1 reject"),
        _line(event="rejected", ts="2026-07-10T08:15:00", agent="lead", model="fable",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="Lead self-fix, round 1 signal"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 2, legal via round-1 lead-fix signal"),
        _line(event="rejected", ts="2026-07-10T08:25:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2, failure_class="spec", by="critic",
              notes="round 2 reject, no new lead-fix signal since entry 2"),
        _line(event="delegated", ts="2026-07-10T08:30:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 3, citing STALE round-1 lead-fix -- must FAIL"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any('"foreign" rejected' in v for v in violations), violations


def test_b3_escalated_signal_legalizes_review_round():
    # (c-ii) signal (3): a new escalated event on the task_id.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work"),
        _line(event="escalated", ts="2026-07-10T08:15:00", agent="builder", model="opus",
              task_id="t-001", notes="task escalated one tier up"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 2, legal via escalated signal"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_b3_stale_escalated_signal_from_earlier_round():
    # Staleness class for the escalated signal: round 1's escalated
    # legalizes entry 2, round 2's entry 3 cannot reuse it.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="round 1 reject"),
        _line(event="escalated", ts="2026-07-10T08:15:00", agent="builder", model="opus",
              task_id="t-001", notes="round 1 escalated signal"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 2, legal via round-1 escalated signal"),
        _line(event="rejected", ts="2026-07-10T08:25:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=2, failure_class="spec", by="critic",
              notes="round 2 reject, no new escalated signal since entry 2"),
        _line(event="delegated", ts="2026-07-10T08:30:00", agent="critic", model="opus",
              task_id="t-001", attempt=2, notes="critic entry 3, citing STALE round-1 escalated -- must FAIL"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any('"foreign" rejected' in v for v in violations), violations


def test_b3_boundary_signal_on_different_task_id_does_not_legalize_this_one():
    # A rework signal (delegated of a different agent) fired on t-002
    # must NOT legalize a foreign retry on t-001 -- signal_log is keyed
    # per task_id; this pins that isolation.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-002", notes="unrelated task t-002, NOT t-001 -- signal must not leak"),
        _line(event="delegated", ts="2026-07-10T08:10:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1 on t-001"),
        _line(event="rejected", ts="2026-07-10T08:15:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work on t-001"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2,
              notes="critic entry 2 on t-001, only signal available is on t-002 -- must FAIL"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any('"foreign" rejected' in v for v in violations), violations


# ---- failure text branches by valid_attempt FIRST, not by signal state -


def test_foreign_rejected_fresh_signal_but_missing_attempt_names_attempt_not_signal():
    # A foreign rejected EXISTS, a fresh valid signal (escalated by a
    # DIFFERENT agent, strictly after critic's own last delegated)
    # EXISTS -- but attempt on the repeat delegated is ABSENT. The
    # unbranched text would falsely claim "no signal, or stale"; the
    # fix must name attempt specifically and must NOT claim the signal
    # is absent/stale.
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work -- foreign rejected for critic"),
        _line(event="escalated", ts="2026-07-10T08:15:00", agent="builder", model="opus",
              task_id="t-001", notes="fresh valid signal, strictly after critic's entry 1"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 2, NO attempt field -- must FAIL naming attempt"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any("'attempt' field" in v for v in violations), violations
    assert not any('"foreign" rejected' in v for v in violations), violations


def test_same_history_with_valid_attempt_passes():
    # LITERALLY the same history, the only difference -- attempt=2 is
    # present on the repeat delegated -- legal (proves the signal really
    # was fresh and valid; the real defect above was attempt, not the
    # signal).
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work -- foreign rejected for critic"),
        _line(event="escalated", ts="2026-07-10T08:15:00", agent="builder", model="opus",
              task_id="t-001", notes="fresh valid signal, strictly after critic's entry 1"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2,
              notes="critic entry 2, attempt=2 present -- must PASS"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


def test_self_recorded_escalated_does_not_legalize_own_reentry():
    # critic records an escalated on its OWN task (agent=critic on the
    # escalated event), then tries a repeat entry citing that same
    # escalated as a new-version signal -- a self-legalizing loop, must
    # FAIL (escalated only counts as a signal when it names a DIFFERENT
    # agent).
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work -- foreign rejected for critic"),
        _line(event="escalated", ts="2026-07-10T08:15:00", agent="critic", model="opus",
              task_id="t-001", notes="critic escalates ITSELF on its own task_id"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2,
              notes="critic entry 2, citing its OWN escalated as signal -- must FAIL"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 1, violations
    assert any('"foreign" rejected' in v for v in violations), violations


def test_positive_pair_escalated_of_different_agent_still_legalizes():
    # The paired positive (same shape, but escalated by a DIFFERENT
    # agent, not critic) -- stays legal as before (the narrowing above
    # only excludes SELF-escalation, not escalated in general).
    staged = _staged(
        _line(event="delegated", ts="2026-07-10T08:05:00", agent="critic", model="opus",
              task_id="t-001", notes="critic entry 1"),
        _line(event="rejected", ts="2026-07-10T08:10:00", agent="builder", model="sonnet",
              task_id="t-001", attempt=1, failure_class="spec", by="critic",
              notes="critic rejects builder's work -- foreign rejected for critic"),
        _line(event="escalated", ts="2026-07-10T08:15:00", agent="builder", model="opus",
              task_id="t-001", notes="escalated by a different agent -- still a valid signal"),
        _line(event="delegated", ts="2026-07-10T08:20:00", agent="critic", model="opus",
              task_id="t-001", attempt=2,
              notes="critic entry 2, legal via a different-agent escalated"),
    )
    code, violations = jv.decide(staged, HEAD_TEXT, NOW)
    assert code == 0, violations


# ---- direct unit coverage of the harvest/signal helpers ---------------


def test_has_new_version_signal_direct_stale_vs_fresh_boundary():
    signal_log = {"t-001": [(5, "delegated", "builder"), (10, "escalated", "builder")]}
    # A signal at idx==after_idx is NOT strictly after -- stale.
    assert jv._has_new_version_signal("t-001", "critic", 5, signal_log) is True  # idx 10 > 5
    assert jv._has_new_version_signal("t-001", "critic", 10, signal_log) is False  # nothing > 10
    assert jv._has_new_version_signal("t-001", "critic", 11, signal_log) is False


def test_has_new_version_signal_ignores_same_agent_kinds():
    signal_log = {"t-001": [(5, "delegated", "critic"), (6, "escalated", "critic")]}
    # Both signals are BY the same agent asking the question -- neither
    # counts (a delegated/escalated must be of a DIFFERENT agent).
    assert jv._has_new_version_signal("t-001", "critic", 0, signal_log) is False


def test_harvest_task_state_returns_seven_tuple():
    delegated_agents, closed_tasks, rejected_tasks, task_worker_refs, rejected_by_agent, last_delegated_idx, signal_log = jv.harvest_task_state(
        [_line(event="delegated", ts="2026-07-10T08:00:00", task_id="t-001", agent="builder", model="sonnet")]
    )
    assert delegated_agents == {"t-001": {"builder"}}
    assert last_delegated_idx[("t-001", "builder")] == 0
    assert signal_log["t-001"] == [(0, "delegated", "builder")]
