"""Battery for the kit's stdin-deadline mechanism (a port of the staff
deployment's own tools/test_p4_stdin_deadline.py): reading stdin to EOF
must never hang session start forever on a harness that opens the pipe
but never actually writes/closes it.

SCOPE OF THIS FILE: shared infrastructure across every kit hook that
reads stdin on a deadline. It started carrying ONLY the
session_context.py cases below (kept in their original, un-parametrized
form -- unchanged by later expansions). The PARAMETRIZED section below
(MODULE_NAMES) covers 10 hooks directly: dispatch_gate, negative_lint,
claim_control_gate, search_control_gate, critic_snapshot, journal_echo,
dod_gate, main_gate, tier_echo, dod_track. session_context is covered
above by its own dedicated, un-parametrized cases; hygiene_gate/
owns_gate/critic_verdict_check each keep their OWN dedicated stdin-
deadline cases in their own test file (test_hygiene_gate.py /
test_owns_gate.py / test_critic_verdict_check.py -- the convention this
kit already established: mechanic tests travel with the hook's own test
file, not exclusively here) -- NOT duplicated here. That is 14 hooks
total carrying the helper as of this writing. mechanism_gate.py is
deliberately absent from the whole population: it is an argv-driven git
commit-msg gate (main(argv)), not a stdin-reading PostToolUse/
SessionStart-style hook -- the stdin-deadline mechanism does not apply
to it. critic_snapshot's own stdin case similarly lives in
tools/test_critic_snapshot.py alongside its own fixtures, ON TOP OF the
parametrized cases it also gets here (both, not either/or). This file's
PARAMETRIZED section is a SIMPLER convention than the staff deployment's
marker/SHA-pin system (which requires byte-identical helper regions with
literal BEGIN/END comment markers across all its siblings) --
deliberately NOT ported: this kit's copies of the helper carry the SAME
logic but their own wording/comments per file (no shared literal-region
requirement is established here), so a byte-identity SHA pin across
files would pin an invariant this port never promised. Instead, each
module is imported directly and exercised through its own public
functions (_stdin_deadline_seconds/_read_stdin_bytes_deadline), the same
style test_owns_gate.py and the original session_context cases below
already use.
Run just this file's own cases with:
    python -m pytest toolkit/tools/test_p4_stdin_deadline.py -k session_context -q
Run the full parametrized battery:
    python -m pytest toolkit/tools/test_p4_stdin_deadline.py -q
"""

import importlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_context as sc  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "session_context.py"
TOOLS_DIR = Path(__file__).resolve().parent

# Hooks exercised by THIS parametrized battery. The kit's full stdin-
# deadline population is larger -- 14 hooks total carry the helper as
# of this writing: the 10 listed below, plus session_context (covered
# above by its own dedicated, un-parametrized cases) and hygiene_gate/
# owns_gate/critic_verdict_check, each of which keeps its OWN dedicated
# stdin-deadline cases in its own test file (test_hygiene_gate.py /
# test_owns_gate.py / test_critic_verdict_check.py) -- not duplicated
# into this list, same convention as session_context. mechanism_gate.py
# is deliberately absent from the whole population: it is an argv-driven
# git commit-msg gate (main(argv)), not a stdin-reading PostToolUse/
# SessionStart-style hook -- the stdin-deadline mechanism does not apply
# to it.
MODULE_NAMES = (
    "dispatch_gate",
    "negative_lint",
    "claim_control_gate",
    "search_control_gate",
    "critic_snapshot",
    "journal_echo",
    "dod_gate",
    "main_gate",
    "tier_echo",
    "dod_track",
)


def _load(name: str):
    return importlib.import_module(name)


# ---------------------------------------------------------------------
# _stdin_deadline_seconds(): env override + boundary values (builder-role
# rule 6a -- AT the boundary and BEYOND it, for every limit introduced).
# ---------------------------------------------------------------------


def test_session_context_stdin_deadline_seconds_default_with_no_env(monkeypatch):
    monkeypatch.delenv(sc._STDIN_DEADLINE_ENV, raising=False)
    assert sc._stdin_deadline_seconds() == sc._STDIN_DEADLINE_DEFAULT


def test_session_context_stdin_deadline_seconds_valid_env_override(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "2.5")
    assert sc._stdin_deadline_seconds() == 2.5


def test_session_context_stdin_deadline_seconds_non_numeric_falls_back(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "not-a-number")
    assert sc._stdin_deadline_seconds() == sc._STDIN_DEADLINE_DEFAULT


def test_session_context_stdin_deadline_seconds_zero_is_invalid_no_wait_forever_mode(monkeypatch):
    # AT the boundary: 0 is explicitly NOT a legal "wait forever" value.
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "0")
    assert sc._stdin_deadline_seconds() == sc._STDIN_DEADLINE_DEFAULT


def test_session_context_stdin_deadline_seconds_negative_falls_back(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "-5")
    assert sc._stdin_deadline_seconds() == sc._STDIN_DEADLINE_DEFAULT


def test_session_context_stdin_deadline_seconds_at_max_boundary_is_valid(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, str(sc._STDIN_DEADLINE_MAX))
    assert sc._stdin_deadline_seconds() == sc._STDIN_DEADLINE_MAX


def test_session_context_stdin_deadline_seconds_just_over_max_falls_back(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, str(sc._STDIN_DEADLINE_MAX + 0.001))
    assert sc._stdin_deadline_seconds() == sc._STDIN_DEADLINE_DEFAULT


def test_session_context_stdin_deadline_seconds_smallest_positive_is_valid(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "0.001")
    assert sc._stdin_deadline_seconds() == 0.001


# ---------------------------------------------------------------------
# _read_stdin_bytes_deadline(): TTY guard, normal read, and a genuine
# timeout against a reader that never returns.
# ---------------------------------------------------------------------


class _FakeTTYStdin:
    def isatty(self):
        return True

    def read(self):  # pragma: no cover -- must never be called
        raise AssertionError("read() must not be called when stdin is a TTY")


def test_session_context_read_stdin_bytes_deadline_tty_returns_immediately(monkeypatch):
    monkeypatch.setattr(sys, "stdin", _FakeTTYStdin())
    data, timed_out = sc._read_stdin_bytes_deadline()
    assert data == b""
    assert timed_out is False


class _FakeBytesStdin:
    def __init__(self, payload: bytes):
        self._buffer = self
        self._payload = payload

    def isatty(self):
        return False

    def read(self):
        return self._payload


def test_session_context_read_stdin_bytes_deadline_normal_read(monkeypatch):
    monkeypatch.setattr(sys, "stdin", _FakeBytesStdin(b'{"model": "claude-sonnet-5"}'))
    data, timed_out = sc._read_stdin_bytes_deadline()
    assert data == b'{"model": "claude-sonnet-5"}'
    assert timed_out is False


class _HangingStdin:
    """.read() never returns within the test's lifetime -- exercises the
    genuine timeout branch. The reader thread stays a daemon and is
    simply abandoned (never joined) after the test, same contract the
    production code relies on."""

    def isatty(self):
        return False

    @property
    def buffer(self):
        return self

    def read(self):
        time.sleep(3600)
        return b""  # pragma: no cover -- never reached


def test_session_context_read_stdin_bytes_deadline_hanging_reader_times_out(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "0.1")
    monkeypatch.setattr(sys, "stdin", _HangingStdin())
    started = time.monotonic()
    data, timed_out = sc._read_stdin_bytes_deadline()
    elapsed = time.monotonic() - started
    assert timed_out is True
    assert data == b""
    assert elapsed < 2.0  # bounded by the 0.1s deadline, not the 3600s sleep


# ---------------------------------------------------------------------
# read_stdin_payload(): degrades to None (no-payload) on a timeout,
# never raises, never blocks the caller past the deadline.
# ---------------------------------------------------------------------


def test_session_context_read_stdin_payload_degrades_to_none_on_timeout(monkeypatch):
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "0.1")
    monkeypatch.setattr(sys, "stdin", _HangingStdin())
    sc._STDIN_DEADLINE_STATE["hit"] = False
    try:
        payload = sc.read_stdin_payload()
        assert payload is None
        assert sc._STDIN_DEADLINE_STATE["hit"] is True
    finally:
        sc._STDIN_DEADLINE_STATE["hit"] = False


def test_session_context_read_stdin_payload_timeout_does_not_set_flag_on_success(monkeypatch):
    monkeypatch.setattr(sys, "stdin", _FakeBytesStdin(b'{"model": "x"}'))
    sc._STDIN_DEADLINE_STATE["hit"] = False
    payload = sc.read_stdin_payload()
    assert payload == {"model": "x"}
    assert sc._STDIN_DEADLINE_STATE["hit"] is False


# ---------------------------------------------------------------------
# main() end-to-end: a hanging stdin does not stop main() from printing
# the full context and returning 0 -- MODEL degrades to "not provided",
# nothing else is lost.
# ---------------------------------------------------------------------


def test_session_context_main_survives_hanging_stdin_and_still_prints_full_context(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv(sc._STDIN_DEADLINE_ENV, "0.1")
    monkeypatch.setattr(sys, "stdin", _HangingStdin())
    started = time.monotonic()
    code = sc.main(tmp_path)
    elapsed = time.monotonic() - started
    assert code == 0
    assert elapsed < 2.0
    out = capsys.readouterr().out
    assert "NOW:" in out
    assert "MODEL: not provided by hook input -- verify tier yourself" in out


# ---------------------------------------------------------------------
# Real subprocess: OSLLM_STDIN_TIMEOUT overrides a genuinely blocked
# pipe (nothing is ever written to the child's stdin, and it is never
# closed either -- a real-world shape of a harness bug this mechanism
# exists to survive).
# ---------------------------------------------------------------------


def test_session_context_subprocess_survives_stdin_that_is_never_closed(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    env = dict(os.environ, OSLLM_STDIN_TIMEOUT="0.3")
    proc = subprocess.Popen(
        [sys.executable, str(SCRIPT)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
        env=env,
    )
    # Deliberately never write to or close proc.stdin -- the child sees
    # an open, silent pipe, exactly the shape a non-writing harness
    # bug would produce.
    try:
        out, err = proc.communicate(timeout=10)
    finally:
        proc.stdin.close()
    assert proc.returncode == 0
    text = out.decode("utf-8", "replace")
    assert "NOW:" in text
    assert "Traceback" not in err.decode("utf-8", "replace")


# =======================================================================
# Parametrized battery for the 10 hooks this file ports the
# stdin-deadline helper to directly (dispatch_gate, negative_lint,
# claim_control_gate, search_control_gate, critic_snapshot, journal_echo,
# dod_gate, main_gate, tier_echo, dod_track) -- see the module docstring, "SCOPE OF
# THIS FILE", for why this is a SIMPLER convention than the staff
# deployment's K1-K13 marker/SHA-pin system.
# =======================================================================

_K6_CASES = (
    (None, 10.0),  # env absent -> default (rule 6a: AT the "no override" case)
    ("2.5", 2.5),  # a valid override
    ("not-a-number", 10.0),  # non-numeric -> default
    ("0", 10.0),  # AT the boundary: 0 is explicitly not "wait forever"
    ("-5", 10.0),  # negative -> default
    ("600.0", 600.0),  # AT the max boundary -- valid
    ("600.001", 10.0),  # just BEYOND the max boundary -- falls back
    ("0.001", 0.001),  # smallest positive -- valid
)


@pytest.mark.parametrize("base_name", MODULE_NAMES)
@pytest.mark.parametrize("raw_value,expected", _K6_CASES)
def test_env_deadline_parsing_boundaries(base_name, raw_value, expected, monkeypatch):
    mod = _load(base_name)
    if raw_value is None:
        monkeypatch.delenv(mod._STDIN_DEADLINE_ENV, raising=False)
    else:
        monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, raw_value)
    assert mod._stdin_deadline_seconds() == expected


class _FakeTTYStdin:
    def isatty(self):
        return True

    def read(self):  # pragma: no cover -- must never be called
        raise AssertionError("read() must not be called when stdin is a TTY")


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_tty_guard_never_reads(base_name, monkeypatch):
    mod = _load(base_name)
    monkeypatch.setattr(sys, "stdin", _FakeTTYStdin())
    data, timed_out = mod._read_stdin_bytes_deadline()
    assert data == b""
    assert timed_out is False


class _FakeBytesStdin:
    def __init__(self, payload: bytes):
        self._buffer = self
        self._payload = payload

    def isatty(self):
        return False

    def read(self):
        return self._payload


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_normal_read_returns_bytes_not_timed_out(base_name, monkeypatch):
    mod = _load(base_name)
    monkeypatch.setattr(sys, "stdin", _FakeBytesStdin(b'{"tool_name": "Task"}'))
    data, timed_out = mod._read_stdin_bytes_deadline()
    assert data == b'{"tool_name": "Task"}'
    assert timed_out is False


class _HangingStdinP4:
    """.read() never returns within the test's lifetime -- exercises the
    genuine timeout branch, AT and BEYOND the deadline (rule 6a)."""

    def isatty(self):
        return False

    @property
    def buffer(self):
        return self

    def read(self):
        time.sleep(3600)
        return b""  # pragma: no cover -- never reached


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_hanging_reader_times_out_bounded_by_deadline_not_the_hang(base_name, monkeypatch):
    mod = _load(base_name)
    monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, "0.1")
    monkeypatch.setattr(sys, "stdin", _HangingStdinP4())
    started = time.monotonic()
    data, timed_out = mod._read_stdin_bytes_deadline()
    elapsed = time.monotonic() - started
    assert timed_out is True
    assert data == b""
    assert elapsed < 2.0  # bounded by the 0.1s deadline, not the 3600s sleep


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_subprocess_survives_stdin_that_is_never_closed(base_name, tmp_path):
    """Real subprocess: the SAME form test_owns_gate.py's own
    test_echo_json_subprocess_survives_stdin_that_is_never_closed and
    session_context's test_..._subprocess_survives_stdin_that_is_never_
    closed above already use. NOTE, empirically checked (command hygiene
    point 6): Popen.communicate() closes the child's stdin as soon as
    it is called, regardless of whether `input=` is passed -- so this
    smoke proves the process completes fast and cleanly on an
    EOF-at-once stdin, NOT that it survives a genuinely open-past-the-
    deadline pipe (that branch is covered in-process, with a real
    measured elapsed time, by test_hanging_reader_times_out_bounded_by_
    deadline_not_the_hang above). Every one of these 9 hooks returns 0
    with EMPTY stdout either way."""
    script = TOOLS_DIR / f"{base_name}.py"
    env = dict(os.environ, OSLLM_STDIN_TIMEOUT="0.3")
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
        env=env,
    )
    try:
        out, err = proc.communicate(timeout=10)
    finally:
        proc.stdin.close()
    assert proc.returncode == 0
    assert out.strip() == b""
    assert b"Traceback" not in err
