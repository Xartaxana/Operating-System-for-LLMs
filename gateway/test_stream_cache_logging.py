"""Regression tests for cache-token logging paths in sqlite_logger.

Covers _cache_tokens() and its integration into _success_row():

  Case 1 — direct attributes (cache_creation_input_tokens /
            cache_read_input_tokens on the Usage object itself).
  Case 2 — fallback via prompt_tokens_details (.cache_creation_tokens /
            .cached_tokens); direct attributes absent.  This is the
            primary regression guard: removing the fallback branch in
            _cache_tokens() would make this test fail while case 1
            continues to pass.
  Case 3 — non-Anthropic usage (no cache fields at all) -> (None, None),
            no exception.

Case 4 (integration through log_success_event + DB) is already covered
by test_success_row_fills_cache_tokens_from_usage and
test_success_row_defaults_cache_tokens_to_null_without_usage_fields in
test_sqlite_logger.py; this file focuses on the unit level.

No network, no API keys required.  Run:
    python -m pytest gateway/ -q
"""

import datetime
import sqlite3
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# _cache_tokens unit tests
# ---------------------------------------------------------------------------


def test_cache_tokens_direct_attributes():
    """Case 1: cache tokens set as direct attributes on Usage."""
    from sqlite_logger import _cache_tokens

    usage = SimpleNamespace(
        cache_creation_input_tokens=20,
        cache_read_input_tokens=30,
        prompt_tokens_details=None,
    )
    creation, read = _cache_tokens(usage)
    assert creation == 20
    assert read == 30


def test_cache_tokens_fallback_via_prompt_tokens_details():
    """Case 2: cache tokens available ONLY through prompt_tokens_details.

    Regression guard: if the fallback branch
        creation = getattr(details, 'cache_creation_tokens', None)
        read     = getattr(details, 'cached_tokens', None)
    is removed from _cache_tokens(), this test will fail (returns
    (None, None) instead of the expected values) while case 1 still
    passes.  That asymmetry is the point.
    """
    from sqlite_logger import _cache_tokens

    details = SimpleNamespace(
        cache_creation_tokens=15,
        cached_tokens=25,
    )
    # Direct attributes deliberately absent (getattr returns None default)
    usage = SimpleNamespace(
        prompt_tokens_details=details,
        # no cache_creation_input_tokens / cache_read_input_tokens
    )
    creation, read = _cache_tokens(usage)
    assert creation == 15, (
        "Expected 15 from prompt_tokens_details.cache_creation_tokens; "
        f"got {creation!r} — fallback branch may be missing"
    )
    assert read == 25, (
        "Expected 25 from prompt_tokens_details.cached_tokens; "
        f"got {read!r} — fallback branch may be missing"
    )


def test_cache_tokens_non_anthropic_returns_none_none():
    """Case 3: plain non-Anthropic usage — no cache fields — returns
    (None, None) without raising."""
    from sqlite_logger import _cache_tokens

    usage = SimpleNamespace(
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        # no cache attributes, no prompt_tokens_details
    )
    creation, read = _cache_tokens(usage)
    assert creation is None
    assert read is None


def test_cache_tokens_none_usage():
    """Edge case: usage=None returns (None, None)."""
    from sqlite_logger import _cache_tokens

    creation, read = _cache_tokens(None)
    assert creation is None
    assert read is None


# ---------------------------------------------------------------------------
# _success_row integration: fallback path reaches the DB columns
# ---------------------------------------------------------------------------


def test_success_row_cache_tokens_from_fallback_path():
    """Verifies that the fallback prompt_tokens_details path propagates
    all the way through _success_row() into the returned dict, so the
    values would land in the DB when log_success_event is called."""
    from sqlite_logger import _success_row

    details = SimpleNamespace(
        cache_creation_tokens=7,
        cached_tokens=42,
    )
    usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        prompt_tokens_details=details,
        # no direct cache_creation_input_tokens / cache_read_input_tokens
    )

    msg = SimpleNamespace(content="hello from cache")
    choice = SimpleNamespace(message=msg)
    response_obj = SimpleNamespace(usage=usage, choices=[choice])

    kwargs = {
        "model": "claude-sonnet-5",
        "messages": [{"role": "user", "content": "ping"}],
        "litellm_params": {"metadata": {}},
        "response_cost": 0.001,
    }
    now = datetime.datetime.now()
    row = _success_row(kwargs, response_obj, now, now)

    assert row["cache_creation_input_tokens"] == 7, (
        f"Expected 7, got {row['cache_creation_input_tokens']!r}"
    )
    assert row["cache_read_input_tokens"] == 42, (
        f"Expected 42, got {row['cache_read_input_tokens']!r}"
    )
