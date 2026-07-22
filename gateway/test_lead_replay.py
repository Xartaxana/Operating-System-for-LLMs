"""Tests for the Lead-replay shadow harness (D-0080 п.3).

No live model/proxy required: litellm mock_response short-circuits the
shadow_eval.replay()/judge_pair() calls this module reuses (same trick as
test_shadow_eval.py). Git extraction tests run against THIS repo's own
real commits (the corpus IS this repo's history) -- that is deliberately
not mocked, per the corpus-real-commit requirement.

Run: python -m pytest gateway/test_lead_replay.py
"""

import subprocess
import sys
from pathlib import Path

import pytest

import metrics
from lead_replay import (
    DEFAULT_CORPUS_PATH,
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


# --- 1. git extraction on real corpus commits -------------------------------


def test_corpus_has_exactly_the_eight_yes_candidates():
    candidates = load_corpus(DEFAULT_CORPUS_PATH)
    tasks = {c["task"] for c in candidates}
    assert tasks == {"1", "2", "4", "5", "7", "11", "12", "15"}


def test_git_extraction_new_file_candidate_has_empty_preimage_and_nonempty_reference():
    # Corpus candidate #1 (t-040): brand-new files, no pre-image (spec's
    # explicit new-file case).
    candidate = next(c for c in load_corpus(DEFAULT_CORPUS_PATH) if c["task"] == "1")
    validate_commit(candidate["commit"])  # must not raise
    preimages = {p: git_preimage(candidate["commit"], p) for p in candidate["paths"]}
    assert candidate["paths"]  # sanity: paths is non-empty
    assert all(v is None for v in preimages.values())
    reference = git_reference_diff(candidate["commit"], candidate["paths"])
    assert reference.strip() != ""
    assert "new file mode" in reference


def test_git_extraction_existing_file_candidate_has_nonempty_preimage_and_reference():
    # Corpus candidate #4: toolkit/README.md pre-exists (banner removal).
    candidate = next(c for c in load_corpus(DEFAULT_CORPUS_PATH) if c["task"] == "4")
    preimages = {p: git_preimage(candidate["commit"], p) for p in candidate["paths"]}
    assert all(v is not None and v.strip() != "" for v in preimages.values())
    reference = git_reference_diff(candidate["commit"], candidate["paths"])
    assert reference.strip() != ""


def test_git_extraction_all_corpus_candidates_paths_and_reference_nonempty():
    # Blanket sweep over all 8 YES candidates: every one must yield a
    # non-empty paths list and a non-empty reference diff (or a legitimate
    # new-file pre-image of None, never a silent empty pre-image for an
    # existing file).
    for candidate in load_corpus(DEFAULT_CORPUS_PATH):
        assert candidate["paths"], candidate["task"]
        reference = git_reference_diff(candidate["commit"], candidate["paths"])
        assert reference.strip() != "", candidate["task"]


def test_validate_commit_raises_explicit_error_on_nonexistent_hash():
    with pytest.raises(LeadReplayError):
        validate_commit("0" * 40)


def test_git_reference_diff_raises_explicit_error_on_nonexistent_commit():
    # Must raise, never return an empty string that looks like "no changes".
    with pytest.raises(LeadReplayError):
        git_reference_diff("d" * 40, ["tools/exam_runner.py"])


def test_git_preimage_returns_none_not_raise_for_new_file_path():
    candidate = next(c for c in load_corpus(DEFAULT_CORPUS_PATH) if c["task"] == "1")
    assert git_preimage(candidate["commit"], candidate["paths"][0]) is None


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
    assert "новый файл" in content
    assert "DRAFT" in content


def test_build_target_prompt_instructs_full_files_not_diff():
    candidate = {"task": "x", "commit": "abc", "kind": "test",
                 "prompt": "DRAFT", "paths": ["a.py"]}
    content = build_target_prompt(candidate, {"a.py": "X"})[0]["content"]
    assert "ЦЕЛИКОМ" in content


# --- 3. replay/judge on litellm mock_response, no live proxy -----------------


def test_run_candidate_end_to_end_with_mock_response(monkeypatch):
    import lead_replay as lead_replay_module

    monkeypatch.setattr(lead_replay_module, "validate_commit", lambda h: None)
    monkeypatch.setattr(lead_replay_module, "git_preimage", lambda h, p: "PREIMAGE CONTENT")
    monkeypatch.setattr(lead_replay_module, "git_reference_diff", lambda h, ps: "REFERENCE DIFF TEXT")

    candidate = {"task": "1", "commit": "abc123", "kind": "script",
                 "prompt": "DRAFT PROMPT", "paths": ["a.py"]}
    result = run_candidate(
        candidate, "lead-sonnet", "judge-gemini", "http://localhost:4000",
        mock_response="EQUIVALENT",
    )
    assert result["error"] is None
    assert result["verdict"] == "equivalent"
    assert result["task"] == "1"
    assert result["commit"] == "abc123"


def test_run_candidate_uses_shadow_eval_replay_and_judge_pair_with_git_diff_as_answer_a(monkeypatch):
    # D-0075/D-0080 п.3: the ONLY calls to the gateway must go through
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
    result = run_candidate(candidate, "lead-sonnet", "judge-gemini", "http://localhost:4000")

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
    result = run_candidate(candidate, "lead-sonnet", "judge-gemini", "http://localhost:4000")
    assert result["verdict"] == "error"
    assert result["error"] is not None
    assert "boom" in result["error"]


# --- 4. CRITICAL: no calibration contamination --------------------------------


def _sample_result():
    return {"task": "1", "commit": "abc", "kind": "script", "verdict": "equivalent",
            "target_cost_usd": 0.01, "judge_cost_usd": 0.002, "truncated": False, "error": None}


def test_format_summary_line_sums_cost_across_results_n_greater_than_1():
    # D-0081 batch item (а) investigation: the described defect ("SUMMARY
    # prints MEAN cost instead of SUM at n>1") does not reproduce in
    # gateway/shadow_eval.py (no "SUMMARY" output there at all; its
    # per-category mean_*_cost_usd fields are the documented, tested
    # design -- see test_shadow_eval.py's test_aggregate_by_category).
    # The only literal "SUMMARY" text in this codebase is this function's
    # "shadow-replay SUMMARY" line, and reading it shows cost_target_total/
    # judge_cost_total are already sum(...), never divided by n -- but
    # no prior test exercised n>1 to lock that in. This test closes that
    # gap: 3 results with distinct costs must add up, not average.
    results = [
        {"task": "1", "commit": "a", "kind": "script", "verdict": "equivalent",
         "target_cost_usd": 0.01, "judge_cost_usd": 0.002, "truncated": False, "error": None},
        {"task": "2", "commit": "b", "kind": "script", "verdict": "equivalent",
         "target_cost_usd": 0.02, "judge_cost_usd": 0.003, "truncated": False, "error": None},
        {"task": "3", "commit": "c", "kind": "script", "verdict": "worse",
         "target_cost_usd": 0.03, "judge_cost_usd": 0.004, "truncated": True, "error": None},
    ]
    summary = format_summary_line("2026-07-22", "lead-sonnet", "judge-gemini", results)

    assert "n=3" in summary
    assert "equivalent=2/3" in summary
    # SUM (0.01+0.02+0.03=0.06), not mean (0.02) -- the assertion that
    # would fail if a future edit reintroduced a /n division.
    assert "cost_target_total=$0.0600" in summary
    assert "judge_cost_total=$0.0090" in summary
    assert "truncated=1" in summary


def test_evidence_lines_never_match_shadow_eval_line_regex():
    result = _sample_result()
    line = format_candidate_line("2026-07-18", result, "lead-sonnet", "judge-gemini")
    summary = format_summary_line("2026-07-18", "lead-sonnet", "judge-gemini", [result])

    # As they will actually appear in the log file: with the leading '- '
    # bullet append_replay_evidence adds.
    assert metrics._SHADOW_EVAL_LINE_RE.match(f"- {line}") is None
    assert metrics._SHADOW_EVAL_LINE_RE.match(f"- {summary}") is None


def test_parse_shadow_eval_log_ignores_replay_evidence_regression_detector():
    # The whole point of the separate 'shadow-replay' vocabulary (D-0080
    # п.3 spec, rule 5): appending our evidence must not move
    # metrics.parse_shadow_eval_log's per-category counts at all.
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
        format_candidate_line(date, result, "lead-sonnet", "judge-gemini"),
        format_summary_line(date, "lead-sonnet", "judge-gemini", [result]),
    ]
    polluted_log = append_replay_evidence(base_log, date, "lead-sonnet", entries)
    assert "shadow-replay" in polluted_log  # sanity: entries actually landed

    counts_after = metrics.parse_shadow_eval_log(polluted_log)
    assert counts_after == counts_before


def test_append_replay_evidence_creates_subheading_and_h1_when_missing():
    text = ""
    result = _sample_result()
    entries = [format_candidate_line("2026-07-18", result, "lead-sonnet", "judge-gemini")]
    updated = append_replay_evidence(text, "2026-07-18", "lead-sonnet", entries)
    assert "# Shadow Evaluation Log" in updated
    assert "### SHADOW-REPLAY D-0080 п.3 (2026-07-18, target=lead-sonnet, ground truth = git-дифф Lead)" in updated
    assert "- 2026-07-18  shadow-replay" in updated


# --- 5. CLI adversarial battery ------------------------------------------------


def test_load_corpus_missing_file_raises_explicit_error(tmp_path):
    with pytest.raises(LeadReplayError, match="not found"):
        load_corpus(tmp_path / "does_not_exist.jsonl")


def test_load_corpus_empty_file_raises_explicit_error(tmp_path):
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
    # "гигантский дифф" adversarial case: a multi-megabyte pre-image/reference
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


def test_cli_missing_corpus_file_exits_cleanly_not_traceback(tmp_path):
    result = subprocess.run(
        [sys.executable, "lead_replay.py", "--dry-run",
         "--corpus", str(tmp_path / "nope.jsonl")],
        cwd=REPO_ROOT / "gateway",
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "not found" in result.stderr


def test_cli_missing_commit_in_corpus_exits_cleanly_not_traceback(tmp_path):
    corpus_path = tmp_path / "bad_commit.jsonl"
    corpus_path.write_text(
        '{"task": "1", "commit": "' + ("f" * 40) + '", "kind": "x",'
        ' "prompt": "p", "paths": ["tools/exam_runner.py"]}\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "lead_replay.py", "--dry-run", "--corpus", str(corpus_path)],
        cwd=REPO_ROOT / "gateway",
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert "commit not found" in result.stderr
