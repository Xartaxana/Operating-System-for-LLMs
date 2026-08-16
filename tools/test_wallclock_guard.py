"""Tests tools/wallclock_guard.py (t-453, F-60 remediation).

Covers the DoD (T6) literally: assert_under's own boundary (R11 "тест НА
границе и ЗА ней") -- `N - 0.1` passes, exactly `N` fails, `N + 0.1`
fails, and the failure message names F-60. `elapsed` is always passed as
a plain argument -- no real clock is used anywhere in this file, so the
boundary is exact and instantaneous regardless of machine load (the exact
non-determinism this module exists to fix elsewhere, see F-60).

Run: python -m pytest tools/test_wallclock_guard.py -q
"""

import pytest

import wallclock_guard as wg


def test_constants_are_the_two_documented_values():
    # Ф1 (spec t-453): TWO numbers, not one -- class A gets 60s (safety
    # net), class B gets 30s (catastrophe ceiling). A silent future edit
    # collapsing them back to one shared number would defeat Ф1 unnoticed.
    assert wg.WALLCLOCK_HARNESS_TIMEOUT == 60
    assert wg.WALLCLOCK_CATASTROPHE_CEILING == 30


def test_assert_under_just_below_ceiling_passes():
    wg.assert_under(29.9, 30, "just below")  # no raise


def test_assert_under_exactly_at_ceiling_fails():
    # Ф9: comparison stays STRICT (elapsed < ceiling) -- exactly the
    # ceiling is a failure, not a pass.
    with pytest.raises(AssertionError):
        wg.assert_under(30.0, 30, "exactly at ceiling")


def test_assert_under_just_above_ceiling_fails():
    with pytest.raises(AssertionError):
        wg.assert_under(30.1, 30, "just above ceiling")


def test_assert_under_failure_message_names_f60():
    with pytest.raises(AssertionError, match="F-60"):
        wg.assert_under(30.1, 30, "just above ceiling")


def test_assert_under_failure_message_includes_what_label():
    with pytest.raises(AssertionError, match="my-operation-label"):
        wg.assert_under(99.0, 30, "my-operation-label")
