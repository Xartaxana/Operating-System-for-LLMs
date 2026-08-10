"""Tests for the Lead-replay shadow harness.

No live model/proxy required: litellm mock_response short-circuits the
shadow_eval.replay()/judge_pair() calls this module reuses (same trick as
test_shadow_eval.py). No API key or GATEWAY_API_KEY is read anywhere in
this file; mock_response short-circuits litellm before any network call
would happen (subscription contour, no keys needed).

Git extraction (section 1) is tested at TWO separate levels, deliberately
kept apart:

- SCHEMA level: the shipped corpus templates (lead_replay_corpus.template
  .jsonl, escalation_corpus.template.jsonl) are checked as parseable,
  field-complete candidates -- load_corpus()/select_candidates() only,
  no git call. The templates carry a PLACEHOLDER commit value
  (PLACEHOLDER_COMMIT, see below), not a real hash from this repo:
  shipping a real commit hash would (a) leak this deployment's own git
  history into a published, portable artifact (the same narrative-anchor
  class the rest of this port batch cleans out) and (b) simply not
  resolve in a host's own clone, which has its own, unrelated git
  history -- "works out of the box" for a template corpus can only ever
  mean "parses out of the box", never "replays out of the box" (a
  template's commit field is a slot the user must fill from their own
  history).
- FUNCTIONAL level: real git subprocess calls (validate_commit,
  git_preimage, git_reference_diff, dry_run_report) are exercised
  against a throwaway git repository built fresh in tmp_path (the
  tmp_git_repo fixture below) -- never against this deployment's own
  commit history, so the test suite carries no coupling to this repo's
  history either.
- The PLACEHOLDER-left-in-place case is itself tested explicitly: running
  --dry-run against the shipped template AS SHIPPED (nobody having
  edited the commit field yet) must produce a clean, named refusal
  ("commit not found", exit code 1), never a traceback -- this is
  exactly what a host sees on a fresh checkout before customizing the
  template, so it is the right thing to pin down.

Run: python -m pytest toolkit/gateway/test_lead_replay.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

import metrics
from lead_replay import (
    LeadReplayError,
    append_replay_evidence,
    build_target_prompt,
    dry_run_report,
    format_candidate_line,
    format_summary_line,
    git_preimage,
    git_reference_diff,
    load_corpus,
    run_candidate,
    select_candidates,
    validate_commit,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_CORPUS_PATH = Path(__file__).parent / "lead_replay_corpus.template.jsonl"
ESCALATION_TEMPLATE_PATH = Path(__file__).parent / "escalation_corpus.template.jsonl"
PLACEHOLDER_COMMIT = "REPLACE-WITH-A-COMMIT-HASH-FROM-YOUR-REPO"


def _run_git(args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


@pytest.fixture()
def tmp_git_repo(tmp_path):
    """A throwaway git repository, built fresh (never this deployment's
    own history): commit1 adds existing.txt; commit2 adds new_file.txt
    (the new-file case) and edits existing.txt (the existing-file case).
    Returns (repo_dir, commit1_hash, commit2_hash)."""
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _run_git(["init"], repo_dir)
    _run_git(["config", "user.email", "test@example.com"], repo_dir)
    _run_git(["config", "user.name", "Test"], repo_dir)

    (repo_dir / "existing.txt").write_text("original content\n", encoding="utf-8")
    _run_git(["add", "existing.txt"], repo_dir)
    _run_git(["commit", "-m", "commit1: add existing.txt"], repo_dir)
    commit1 = _run_git(["rev-parse", "HEAD"], repo_dir).stdout.strip()

    (repo_dir / "existing.txt").write_text("original content\nmore content\n", encoding="utf-8")
    (repo_dir / "new_file.txt").write_text("brand new\n", encoding="utf-8")
    _run_git(["add", "-A"], repo_dir)
    _run_git(["commit", "-m", "commit2: add new_file.txt, edit existing.txt"], repo_dir)
    commit2 = _run_git(["rev-parse", "HEAD"], repo_dir).stdout.strip()

    return repo_dir, commit1, commit2


# --- 1a. schema level: shipped templates parse, no git involved -------------


def test_template_corpus_has_exactly_the_two_shipped_candidates():
    candidates = load_corpus(TEMPLATE_CORPUS_PATH)
    tasks = {c["task"] for c in candidates}
    assert tasks == {"1", "2"}


def test_escalation_template_corpus_has_exactly_the_two_shipped_candidates():
    candidates = load_corpus(ESCALATION_TEMPLATE_PATH)
    tasks = {c["task"] for c in candidates}
    assert tasks == {"e1", "e2"}


def test_shipped_templates_are_schema_valid_with_placeholder_commit_no_git():
    # "accepts the template out of the box" at the SCHEMA level: every
    # required field is present and non-git-checked; select_candidates()
    # also works on the shipped file untouched.
    for path in (TEMPLATE_CORPUS_PATH, ESCALATION_TEMPLATE_PATH):
        candidates = load_corpus(path)
        assert candidates  # non-empty
        for candidate in candidates:
            assert candidate["commit"] == PLACEHOLDER_COMMIT
            assert candidate["paths"]
            assert candidate["prompt"]
        selected = select_candidates(candidates, only=candidates[0]["task"])
        assert len(selected) == 1


# --- 1b. functional level: real git calls against a throwaway repo ----------


def test_git_extraction_new_file_case_against_fixture_repo(monkeypatch, tmp_git_repo):
    import lead_replay as lead_replay_module

    repo_dir, commit1, commit2 = tmp_git_repo
    monkeypatch.setattr(lead_replay_module, "REPO_ROOT", repo_dir)

    validate_commit(commit2)  # must not raise
    preimage = git_preimage(commit2, "new_file.txt")
    assert preimage is None
    reference = git_reference_diff(commit2, ["new_file.txt"])
    assert reference.strip() != ""
    assert "new file mode" in reference


def test_git_extraction_existing_file_case_against_fixture_repo(monkeypatch, tmp_git_repo):
    import lead_replay as lead_replay_module

    repo_dir, commit1, commit2 = tmp_git_repo
    monkeypatch.setattr(lead_replay_module, "REPO_ROOT", repo_dir)

    preimage = git_preimage(commit2, "existing.txt")
    assert preimage == "original content\n"
    reference = git_reference_diff(commit2, ["existing.txt"])
    assert reference.strip() != ""
    assert "more content" in reference


def test_dry_run_report_end_to_end_against_fixture_repo(monkeypatch, tmp_git_repo):
    # Functional "dry-run" level: exercises dry_run_report -- the exact
    # function the CLI's --dry-run branch calls per candidate -- against a
    # throwaway git repo built in this test, never against this
    # deployment's own commit history.
    import lead_replay as lead_replay_module

    repo_dir, commit1, commit2 = tmp_git_repo
    monkeypatch.setattr(lead_replay_module, "REPO_ROOT", repo_dir)

    candidate = {
        "task": "1", "commit": commit2, "kind": "test",
        "prompt": "Add new_file.txt and extend existing.txt.",
        "paths": ["new_file.txt", "existing.txt"],
    }
    report = dry_run_report(candidate)
    assert "task=1" in report
    assert "new file mode" in report
    assert "more content" in report


def test_validate_commit_raises_explicit_error_on_nonexistent_hash():
    with pytest.raises(LeadReplayError):
        validate_commit("0" * 40)


def test_git_reference_diff_raises_explicit_error_on_nonexistent_commit():
    # Must raise, never return an empty string that looks like "no changes".
    with pytest.raises(LeadReplayError):
        git_reference_diff("d" * 40, ["gateway/lead_replay.py"])


def test_git_preimage_returns_none_not_raise_on_git_failure():
    # Same contract exercised at the unit level with a nonexistent commit
    # (the module's own documented behavior: a failed `git show` collapses
    # to None, treated by callers as "new file", never as an exception).
    assert git_preimage("0" * 40, "some/path.py") is None


# --- 1c. the placeholder-left-in-place case: clean named refusal ------------


def test_cli_placeholder_commit_in_shipped_template_gives_clean_named_refusal():
    # Edge case (c): a host running the shipped template WITHOUT replacing
    # the commit placeholder first must see a clean, NAMED refusal --
    # never a traceback. This is exactly what the kit ships today (the
    # template's commit field is the placeholder by construction) and
    # exactly what a fresh host checkout sees before customizing it.
    result = subprocess.run(
        [sys.executable, "lead_replay.py", "--dry-run",
         "--corpus", str(TEMPLATE_CORPUS_PATH)],
        cwd=REPO_ROOT / "gateway",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "commit not found" in result.stderr
    assert PLACEHOLDER_COMMIT in result.stderr


def test_cli_placeholder_commit_in_shipped_escalation_template_gives_clean_named_refusal():
    result = subprocess.run(
        [sys.executable, "lead_replay.py", "--dry-run",
         "--corpus", str(ESCALATION_TEMPLATE_PATH)],
        cwd=REPO_ROOT / "gateway",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "commit not found" in result.stderr
    assert PLACEHOLDER_COMMIT in result.stderr


# --- 2. prompt assembly -------------------------------------------------------


def test_build_target_prompt_includes_draft_and_all_preimages():
    candidate = {"task": "x", "commit": "abc", "kind": "test",
                 "prompt": "DRAFT_PROMPT_TEXT", "paths": ["a.py", "b.py"]}
    preimages = {"a.py": "CONTENT_A", "b.py": "CONTENT_B"}
    messages = build_target_prompt(candidate, preimages)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    content = messages[0]["content"]
    assert "DRAFT_PROMPT_TEXT" in content
    assert "CONTENT_A" in content and "CONTENT_B" in content
    assert "a.py" in content and "b.py" in content


def test_build_target_prompt_new_file_case_does_not_crash_and_marks_new_file():
    candidate = {"task": "x", "commit": "abc", "kind": "test",
                 "prompt": "DRAFT", "paths": ["new.py"]}
    preimages = {"new.py": None}
    messages = build_target_prompt(candidate, preimages)
    content = messages[0]["content"]
    assert "new file" in content
    assert "DRAFT" in content


def test_build_target_prompt_instructs_full_files_not_diff():
    candidate = {"task": "x", "commit": "abc", "kind": "test",
                 "prompt": "DRAFT", "paths": ["a.py"]}
    content = build_target_prompt(candidate, {"a.py": "X"})[0]["content"]
    assert "IN FULL" in content


# --- 3. replay/judge on litellm mock_response, no live proxy -----------------


def test_run_candidate_end_to_end_with_mock_response(monkeypatch):
    import lead_replay as lead_replay_module

    monkeypatch.setattr(lead_replay_module, "validate_commit", lambda h: None)
    monkeypatch.setattr(lead_replay_module, "git_preimage", lambda h, p: "PREIMAGE CONTENT")
    monkeypatch.setattr(lead_replay_module, "git_reference_diff", lambda h, ps: "REFERENCE DIFF TEXT")

    candidate = {"task": "1", "commit": "abc123", "kind": "script",
                 "prompt": "DRAFT PROMPT", "paths": ["a.py"]}
    result = run_candidate(
        candidate, "builder", "judge", "http://localhost:4000",
        mock_response="EQUIVALENT",
    )
    assert result["error"] is None
    assert result["verdict"] == "equivalent"
    assert result["task"] == "1"
    assert result["commit"] == "abc123"


def test_run_candidate_uses_shadow_eval_replay_and_judge_pair_with_git_diff_as_answer_a(monkeypatch):
    # The ONLY calls to the gateway must go through
    # shadow_eval.replay()/judge_pair(); Answer A handed to the judge must
    # be the git-diff reference, never the target's own answer twice.
    import lead_replay as lead_replay_module

    monkeypatch.setattr(lead_replay_module, "validate_commit", lambda h: None)
    monkeypatch.setattr(lead_replay_module, "git_preimage", lambda h, p: "PREIMAGE")
    monkeypatch.setattr(lead_replay_module, "git_reference_diff", lambda h, ps: "REFERENCE DIFF")

    def fake_replay(messages, target_model, gateway, db_path=None, max_tokens=None, **kwargs):
        return "TARGET ANSWER", 0.01, "stop"

    captured = {}

    def fake_judge_pair(task_prompt, source_answer, target_answer, judge_model, gateway, db_path=None, **kwargs):
        captured["task_prompt"] = task_prompt
        captured["source_answer"] = source_answer
        captured["target_answer"] = target_answer
        return "target_worse", 0.002

    monkeypatch.setattr(lead_replay_module.shadow_eval, "replay", fake_replay)
    monkeypatch.setattr(lead_replay_module.shadow_eval, "judge_pair", fake_judge_pair)

    candidate = {"task": "1", "commit": "abc", "kind": "script", "prompt": "DRAFT", "paths": ["a.py"]}
    result = run_candidate(candidate, "builder", "judge", "http://localhost:4000")

    assert captured["task_prompt"] == "DRAFT"
    assert captured["source_answer"] == "REFERENCE DIFF"
    assert captured["target_answer"] == "TARGET ANSWER"
    # shadow_eval's "target_worse" is mapped to this module's "worse" vocabulary
    assert result["verdict"] == "worse"
    assert result["target_cost_usd"] == 0.01
    assert result["judge_cost_usd"] == 0.002


def test_run_candidate_replay_error_produces_error_verdict_not_crash(monkeypatch):
    import lead_replay as lead_replay_module

    monkeypatch.setattr(lead_replay_module, "validate_commit", lambda h: None)
    monkeypatch.setattr(lead_replay_module, "git_preimage", lambda h, p: "PREIMAGE")
    monkeypatch.setattr(lead_replay_module, "git_reference_diff", lambda h, ps: "REFERENCE DIFF")

    def raising_replay(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(lead_replay_module.shadow_eval, "replay", raising_replay)

    candidate = {"task": "1", "commit": "abc", "kind": "script", "prompt": "DRAFT", "paths": ["a.py"]}
    result = run_candidate(candidate, "builder", "judge", "http://localhost:4000")
    assert result["verdict"] == "error"
    assert result["error"] is not None
    assert "boom" in result["error"]


# --- 4. CRITICAL: no calibration contamination --------------------------------


def _sample_result():
    return {"task": "1", "commit": "abc", "kind": "script", "verdict": "equivalent",
            "target_cost_usd": 0.01, "judge_cost_usd": 0.002, "truncated": False, "error": None}


def test_format_summary_line_sums_cost_across_results_n_greater_than_1():
    # cost_target_total/judge_cost_total must SUM across results, never
    # average -- a future edit reintroducing a /n division must fail this.
    results = [
        {"task": "1", "commit": "a", "kind": "script", "verdict": "equivalent",
         "target_cost_usd": 0.01, "judge_cost_usd": 0.002, "truncated": False, "error": None},
        {"task": "2", "commit": "b", "kind": "script", "verdict": "equivalent",
         "target_cost_usd": 0.02, "judge_cost_usd": 0.003, "truncated": False, "error": None},
        {"task": "3", "commit": "c", "kind": "script", "verdict": "worse",
         "target_cost_usd": 0.03, "judge_cost_usd": 0.004, "truncated": True, "error": None},
    ]
    summary = format_summary_line("2026-07-22", "builder", "judge", results)

    assert "n=3" in summary
    assert "equivalent=2/3" in summary
    # SUM (0.01+0.02+0.03=0.06), not mean (0.02) -- the assertion that
    # would fail if a future edit reintroduced a /n division.
    assert "cost_target_total=$0.0600" in summary
    assert "judge_cost_total=$0.0090" in summary
    assert "truncated=1" in summary


def test_evidence_lines_never_match_shadow_eval_line_regex():
    result = _sample_result()
    line = format_candidate_line("2026-07-18", result, "builder", "judge")
    summary = format_summary_line("2026-07-18", "builder", "judge", [result])

    # As they will actually appear in the log file: with the leading '- '
    # bullet append_replay_evidence adds.
    assert metrics._SHADOW_EVAL_LINE_RE.match(f"- {line}") is None
    assert metrics._SHADOW_EVAL_LINE_RE.match(f"- {summary}") is None


def test_parse_shadow_eval_log_ignores_replay_evidence_regression_detector():
    # The whole point of the separate 'shadow-replay' vocabulary: appending
    # our evidence must not move metrics.parse_shadow_eval_log's per-category
    # counts at all.
    base_log = (
        "# Shadow Evaluation Log\n\n"
        "Evidence for DELEGATION_TABLE.md Update Rule 1.\n\n"
        "- 2026-07-03  category=coding  source=lead-gemini target=intern"
        "  n=2  sim=0.10 judge=judge-groq pass_rate=0.50 judge_cost=$0.0004"
        "  cost_source=$0.0044 cost_target=$0.0000  -> rejected\n"
    )
    counts_before = metrics.parse_shadow_eval_log(base_log)
    assert counts_before  # sanity: the pre-existing line IS counted

    result = _sample_result()
    date = "2026-07-18"
    entries = [
        format_candidate_line(date, result, "builder", "judge"),
        format_summary_line(date, "builder", "judge", [result]),
    ]
    polluted_log = append_replay_evidence(base_log, date, "builder", entries)
    assert "shadow-replay" in polluted_log  # sanity: entries actually landed

    counts_after = metrics.parse_shadow_eval_log(polluted_log)
    assert counts_after == counts_before


def test_append_replay_evidence_creates_subheading_and_h1_when_missing():
    text = ""
    result = _sample_result()
    entries = [format_candidate_line("2026-07-18", result, "builder", "judge")]
    updated = append_replay_evidence(text, "2026-07-18", "builder", entries)
    assert "# Shadow Evaluation Log" in updated
    assert "### SHADOW-REPLAY (2026-07-18, target=builder, ground truth = git diff of Lead's own commit)" in updated
    assert "- 2026-07-18  shadow-replay" in updated


# --- 5. CLI adversarial battery ------------------------------------------------


def test_load_corpus_missing_file_raises_explicit_error(tmp_path):
    with pytest.raises(LeadReplayError, match="not found"):
        load_corpus(tmp_path / "does_not_exist.jsonl")


def test_load_corpus_empty_file_raises_explicit_error(tmp_path):
    # Chosen behavior for an empty (0-line) corpus: fail loud with
    # LeadReplayError, never silently proceed with zero candidates.
    corpus_path = tmp_path / "empty.jsonl"
    corpus_path.write_text("", encoding="utf-8")
    with pytest.raises(LeadReplayError, match="empty"):
        load_corpus(corpus_path)


def test_load_corpus_blank_lines_only_raises_explicit_error(tmp_path):
    corpus_path = tmp_path / "blank.jsonl"
    corpus_path.write_text("\n\n   \n", encoding="utf-8")
    with pytest.raises(LeadReplayError, match="empty"):
        load_corpus(corpus_path)


def test_load_corpus_broken_json_line_raises_explicit_error_with_line_number(tmp_path):
    # Chosen behavior for a broken JSONL line: fail loud, naming the
    # 1-based line number, never silently skip the bad line and continue.
    corpus_path = tmp_path / "broken.jsonl"
    corpus_path.write_text(
        '{"task": "1", "commit": "abc", "kind": "x", "prompt": "p", "paths": []}\n'
        'THIS IS NOT JSON\n',
        encoding="utf-8",
    )
    with pytest.raises(LeadReplayError, match="line 2"):
        load_corpus(corpus_path)


def test_load_corpus_missing_required_field_raises_explicit_error(tmp_path):
    corpus_path = tmp_path / "missing_field.jsonl"
    corpus_path.write_text(
        '{"task": "1", "commit": "abc", "kind": "x", "paths": []}\n',
        encoding="utf-8",
    )
    with pytest.raises(LeadReplayError, match="prompt"):
        load_corpus(corpus_path)


def test_select_candidates_unknown_only_id_raises_explicit_error():
    candidates = [{"task": "1", "commit": "a", "kind": "x", "prompt": "p", "paths": []}]
    with pytest.raises(LeadReplayError, match="99"):
        select_candidates(candidates, only="99")


def test_select_candidates_filters_to_requested_subset():
    candidates = [
        {"task": "1", "commit": "a", "kind": "x", "prompt": "p", "paths": []},
        {"task": "2", "commit": "b", "kind": "x", "prompt": "p", "paths": []},
        {"task": "4", "commit": "c", "kind": "x", "prompt": "p", "paths": []},
    ]
    selected = select_candidates(candidates, only="1,4")
    assert {c["task"] for c in selected} == {"1", "4"}


def test_dry_run_report_handles_huge_diff_without_crashing(monkeypatch):
    # "giant diff" adversarial case: a multi-megabyte pre-image/reference
    # must not crash dry_run_report, and must be truncated for display while
    # the underlying prompt data stays intact for a real (non-dry-run) call.
    import lead_replay as lead_replay_module

    huge_text = "x" * 5_000_000
    monkeypatch.setattr(lead_replay_module, "validate_commit", lambda h: None)
    monkeypatch.setattr(lead_replay_module, "git_preimage", lambda h, p: huge_text)
    monkeypatch.setattr(lead_replay_module, "git_reference_diff", lambda h, ps: huge_text)

    candidate = {"task": "1", "commit": "abc", "kind": "script", "prompt": "DRAFT", "paths": ["a.py"]}
    report = dry_run_report(candidate)
    assert "[truncated for display" in report
    assert len(report) < len(huge_text)  # actually truncated, not dumped whole

    # The untruncated data still reaches build_target_prompt/replay untouched.
    messages = build_target_prompt(candidate, {"a.py": huge_text})
    assert len(messages[0]["content"]) >= len(huge_text)


def test_cli_missing_corpus_file_exits_cleanly_with_named_exit_code(tmp_path):
    # Edge case (b) of the DoD: corpus not given/found -> a clean refusal
    # with a NAMED exit code (1, via SystemExit(str)), never a traceback.
    result = subprocess.run(
        [sys.executable, "lead_replay.py", "--dry-run",
         "--corpus", str(tmp_path / "nope.jsonl")],
        cwd=REPO_ROOT / "gateway",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "not found" in result.stderr


def test_cli_missing_commit_in_corpus_exits_cleanly_with_named_exit_code(tmp_path):
    corpus_path = tmp_path / "bad_commit.jsonl"
    corpus_path.write_text(
        '{"task": "1", "commit": "' + ("f" * 40) + '", "kind": "x",'
        ' "prompt": "p", "paths": ["gateway/lead_replay.py"]}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "lead_replay.py", "--dry-run", "--corpus", str(corpus_path)],
        cwd=REPO_ROOT / "gateway",
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert "commit not found" in result.stderr


## test_cli_accepts_shipped_template(_escalation)_corpus_out_of_the_box was
## removed here: "out of the box" for a template corpus with a
## PLACEHOLDER commit can only mean "parses out of the box" (schema level,
## see test_shipped_templates_are_schema_valid_with_placeholder_commit_no_git
## above) -- a live --dry-run against the shipped, unedited template is
## instead pinned to its correct outcome, a clean named refusal, by
## test_cli_placeholder_commit_in_shipped_template_gives_clean_named_refusal
## and its escalation-corpus sibling above (section 1c).
