"""Tests for regression_runner.py (t-084).

No live proxy required: urllib.request.urlopen is mocked throughout.

Run: python -m pytest gateway/test_regression_runner.py
"""

import json
import time as time_module
import unittest.mock as mock
from pathlib import Path

import pytest

import regression_runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jsonl(tmp_path, rows):
    """Write a list of dicts as JSONL and return the path string."""
    p = tmp_path / "test_set.jsonl"
    p.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    return str(p)


def _fake_response(content: str = "hello", status: int = 200):
    """Return a mock object that looks like a urllib response."""
    body = json.dumps(
        {
            "choices": [
                {"message": {"content": content}, "finish_reason": "stop"}
            ]
        }
    ).encode("utf-8")
    resp = mock.MagicMock()
    resp.status = status
    resp.read.return_value = body
    # Support use as context manager (urlopen returns a context manager)
    resp.__enter__ = lambda s: s
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Test 1: payload is built correctly
# ---------------------------------------------------------------------------

def test_payload_structure(tmp_path):
    """build_payload produces model, messages, stream=False, synthetic tag."""
    rows = [
        {"prompt": "Write a hello-world function", "category": "coding", "source_task": "task-1"}
    ]
    set_path = _make_jsonl(tmp_path, rows)

    captured_payloads = []

    def fake_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        captured_payloads.append(body)
        return _fake_response("def hello(): pass")

    with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
        exit_code = regression_runner.run(
            set_path=set_path,
            model="lead-sonnet",
            base_url="http://localhost:4000",
            pace=0.0,
            timeout=10,
            max_n=0,
            dry_run=False,
        )

    assert exit_code == 0
    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert payload["model"] == "lead-sonnet"
    assert payload["stream"] is False
    assert payload["metadata"]["traffic_kind"] == "synthetic"
    assert payload["messages"] == [{"role": "user", "content": "Write a hello-world function"}]
    # t-085: ground-truth category from the regression set row reaches the payload
    assert payload["metadata"]["category"] == "coding"


# ---------------------------------------------------------------------------
# Test 2: pace — sleep called n-1 times for n rows
# ---------------------------------------------------------------------------

def test_pace_sleep_count(tmp_path, monkeypatch):
    """time.sleep is called exactly (n - 1) times between n requests."""
    rows = [
        {"prompt": f"prompt {j}", "category": "coding", "source_task": f"task-{j}"}
        for j in range(4)
    ]
    set_path = _make_jsonl(tmp_path, rows)

    sleep_calls = []
    monkeypatch.setattr(time_module, "sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr(regression_runner.time, "sleep", lambda s: sleep_calls.append(s))

    with mock.patch("urllib.request.urlopen", return_value=_fake_response()):
        exit_code = regression_runner.run(
            set_path=set_path,
            model="lead-sonnet",
            base_url="http://localhost:4000",
            pace=1.5,
            timeout=10,
            max_n=0,
            dry_run=False,
        )

    assert exit_code == 0
    # 4 rows → sleep called 3 times (between pairs, not before first)
    assert sleep_calls == [1.5, 1.5, 1.5]


# ---------------------------------------------------------------------------
# Test 3: --dry-run does not call urlopen
# ---------------------------------------------------------------------------

def test_dry_run_no_network(tmp_path):
    """--dry-run prints payloads and never calls urllib.request.urlopen."""
    rows = [
        {"prompt": "Implement a sort function", "category": "coding", "source_task": "task-1"},
        {"prompt": "Write a binary search", "category": "coding", "source_task": "task-2"},
    ]
    set_path = _make_jsonl(tmp_path, rows)

    mock_urlopen = mock.MagicMock()

    with mock.patch("urllib.request.urlopen", mock_urlopen):
        exit_code = regression_runner.run(
            set_path=set_path,
            model="lead-sonnet",
            base_url="http://localhost:4000",
            pace=2.0,
            timeout=120,
            max_n=2,
            dry_run=True,
        )

    assert exit_code == 0
    mock_urlopen.assert_not_called()
