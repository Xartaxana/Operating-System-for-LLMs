"""Tests for Shadow Evaluation. No live model/proxy required:
litellm mock_response short-circuits replay() (same trick as test_analyst.py).

Run: python -m pytest gateway/test_shadow_eval.py
"""

import datetime
import json

import pytest

from shadow_eval import (
    aggregate_by_category,
    append_evidence_log,
    calibrate,
    decide_status,
    evaluate,
    judge_pair,
    parse_verdict,
    sample_requests,
    similarity,
    update_table_status,
)


@pytest.fixture()
def conn(tmp_path):
    import sqlite3

    from sqlite_logger import SCHEMA

    conn = sqlite3.connect(tmp_path / "requests.db")
    conn.execute(SCHEMA)
    return conn


def seed(conn, model, prompt_messages, response, cost=0.01, status="success", ts=None):
    conn.execute(
        "INSERT INTO requests (ts, model, status, cost_usd, prompt, response)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            ts or datetime.datetime.now().isoformat(),
            model,
            status,
            cost,
            json.dumps(prompt_messages),
            response,
        ),
    )
    conn.commit()


def test_similarity_identical_and_different():
    assert similarity("same text", "same text") == 1.0
    assert similarity("abc", "xyz") == 0.0
    assert 0 < similarity("summarize this please", "summarize this now") < 1


def test_sample_requests_filters_model_and_status(conn):
    seed(conn, "lead", [{"role": "user", "content": "hi"}], "hello")
    seed(conn, "intern", [{"role": "user", "content": "hi"}], "hello")
    seed(conn, "lead", [{"role": "user", "content": "fail"}], None, status="failure")

    rows = sample_requests(conn, "lead", days=7, limit=10)
    assert len(rows) == 1
    assert rows[0]["response"] == "hello"


def test_evaluate_uses_mock_response(conn):
    seed(conn, "lead", [{"role": "user", "content": "summarize this article"}], "a short summary")

    results = evaluate(
        conn, "lead", "intern", "http://localhost:4000", days=7, sample_n=10,
        mock_response="a short summary",
    )
    assert len(results) == 1
    assert results[0]["category"] == "summarization"
    assert results[0]["similarity"] == 1.0
    assert results[0]["error"] is None


def test_evaluate_records_replay_errors(conn):
    seed(conn, "lead", [{"role": "user", "content": "hi"}], "hello")

    results = evaluate(
        conn, "lead", "nonexistent-model-xyz", "http://localhost:4000", days=7, sample_n=10,
    )
    assert results[0]["error"] is not None
    assert results[0]["similarity"] == 0.0


def test_aggregate_by_category():
    results = [
        {"category": "coding", "source_cost_usd": 0.02, "target_cost_usd": 0.001, "similarity": 0.8, "error": None},
        {"category": "coding", "source_cost_usd": 0.03, "target_cost_usd": 0.002, "similarity": 0.6, "error": None},
        {"category": "other", "source_cost_usd": 0.01, "target_cost_usd": 0.0, "similarity": 0.0, "error": "boom"},
    ]
    agg = aggregate_by_category(results)
    assert agg["coding"]["n"] == 2
    assert agg["coding"]["mean_similarity"] == pytest.approx(0.7)
    assert agg["other"]["errors"] == 1


def test_decide_status_validated():
    agg = {"n": 3, "mean_similarity": 0.9, "mean_source_cost_usd": 0.02, "mean_target_cost_usd": 0.001, "errors": 0}
    assert decide_status(agg, similarity_threshold=0.5, min_samples=2) == "validated"


def test_decide_status_rejected_low_similarity():
    agg = {"n": 3, "mean_similarity": 0.1, "mean_source_cost_usd": 0.02, "mean_target_cost_usd": 0.001, "errors": 0}
    assert decide_status(agg, similarity_threshold=0.5, min_samples=2) == "rejected"


def test_decide_status_estimated_when_not_enough_samples():
    agg = {"n": 1, "mean_similarity": 0.9, "mean_source_cost_usd": 0.02, "mean_target_cost_usd": 0.001, "errors": 0}
    assert decide_status(agg, similarity_threshold=0.5, min_samples=2) == "estimated"


def test_decide_status_estimated_when_all_errored():
    agg = {"n": 2, "mean_similarity": 0.0, "mean_source_cost_usd": 0.02, "mean_target_cost_usd": 0.0, "errors": 2}
    assert decide_status(agg, similarity_threshold=0.5, min_samples=2) == "estimated"


def test_parse_verdict():
    assert parse_verdict("EQUIVALENT") == "equivalent"
    assert parse_verdict("The answer is WORSE.") == "target_worse"
    assert parse_verdict("<think>worse? no, equal quality</think>EQUIVALENT") == "equivalent"
    assert parse_verdict("no keyword here") is None
    assert parse_verdict("") is None
    # last keyword wins when the judge restates both options first
    assert parse_verdict("Either EQUIVALENT or WORSE... verdict: EQUIVALENT") == "equivalent"


def test_judge_pair_with_mock():
    verdict = judge_pair(
        "Summarize X", "short summary", "verbose but correct summary",
        "judge-alias", "http://localhost:4000", mock_response="EQUIVALENT",
    )
    assert verdict == "equivalent"


def test_evaluate_with_judge_records_verdict(conn):
    seed(conn, "lead", [{"role": "user", "content": "summarize this article"}], "a summary")

    results = evaluate(
        conn, "lead", "intern", "http://localhost:4000", days=7, sample_n=10,
        judge_model="judge-alias", mock_response="EQUIVALENT",
    )
    assert results[0]["verdict"] == "equivalent"


def test_aggregate_pass_rate():
    results = [
        {"category": "coding", "source_cost_usd": 0.02, "target_cost_usd": 0.001, "similarity": 0.1, "verdict": "equivalent", "error": None},
        {"category": "coding", "source_cost_usd": 0.03, "target_cost_usd": 0.002, "similarity": 0.1, "verdict": "target_worse", "error": None},
    ]
    agg = aggregate_by_category(results)
    assert agg["coding"]["pass_rate"] == pytest.approx(0.5)


def test_decide_status_judge_overrides_similarity():
    # low difflib sim but judge says equivalent -> validated
    agg = {"n": 2, "mean_similarity": 0.1, "mean_source_cost_usd": 0.02,
           "mean_target_cost_usd": 0.001, "errors": 0, "pass_rate": 1.0}
    assert decide_status(agg, similarity_threshold=0.5, min_samples=2) == "validated"
    # high sim but judge says worse -> rejected
    agg["pass_rate"] = 0.0
    agg["mean_similarity"] = 0.9
    assert decide_status(agg, similarity_threshold=0.5, min_samples=2) == "rejected"


def test_calibrate_reports_agreement_and_mismatches():
    pairs = [
        {"prompt": "task1", "source_response": "a", "target_response": "b",
         "category": "coding", "verdict": "equivalent"},
        {"prompt": "task2", "source_response": "a", "target_response": "b",
         "category": "classification", "verdict": "target_worse"},
    ]
    report = calibrate(pairs, "judge-alias", "http://localhost:4000",
                       mock_response="EQUIVALENT")
    assert report["n"] == 2
    assert report["agreements"] == 1
    assert report["mismatches"][0]["category"] == "classification"
    assert report["mismatches"][0]["got"] == "equivalent"


def test_update_table_status_replaces_only_matching_row():
    text = (
        "| Task type | Cost (Lead) | Value of Lead | Delegate to | Status |\n"
        "|---|---|---|---|---|\n"
        "| Summarization | Medium | Medium | Junior | estimated |\n"
        "| Classification, tagging | Low | Low | Junior | estimated |\n"
    )
    updated = update_table_status(text, "Summarization", "validated")
    assert "| Summarization | Medium | Medium | Junior | validated |" in updated
    assert "| Classification, tagging | Low | Low | Junior | estimated |" in updated


def test_append_evidence_log_creates_section_once():
    text = "# Delegation Table\n\nsome content\n"
    once = append_evidence_log(text, ["entry one"])
    assert "## Shadow Evaluation Log" in once
    assert "- entry one" in once

    twice = append_evidence_log(once, ["entry two"])
    assert twice.count("## Shadow Evaluation Log") == 1
    assert "- entry one" in twice
    assert "- entry two" in twice
