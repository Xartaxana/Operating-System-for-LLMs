"""Tests for tools/ambient_noise_probe.py (узел C, calibration №8
remediation, docs/tasks/2026-08-20_calibration-8-remediation.md).

Groups:
  (A) unit -- validation helpers (_validate_seconds/_validate_count/
      _validate_schedule), fast, no I/O, boundary AT/BEYOND per limit
      (rule 6a CLAUDE.md).
  (B) in-process run() -- small, fast schedules (period=0, hold=0)
      exercising the write/cleanup/persist/dry-run/manifest paths.
  (C) subprocess -- CLI-level smoke, stdin-devnull safety rail, exit
      codes, two-simultaneous-probes collision safety, interruption.

Run from the repo root: python -m pytest tools/test_ambient_noise_probe.py -q
"""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ambient_noise_probe as anp  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "ambient_noise_probe.py"


def _args(**overrides):
    base = dict(
        target_dir=None, count=1, period=0.0, hold_seconds=0.0,
        duration=anp.MAX_DURATION_SECONDS, marker_prefix=anp.DEFAULT_MARKER_PREFIX,
        persist=False, dry_run=False, manifest_out=None, clean_manifest=None,
    )
    base.update(overrides)
    return anp.argparse.Namespace(**base)


# ---------------------------------------------------------------------
# (A) unit: validation boundaries -- AT the limit and BEYOND it
# ---------------------------------------------------------------------


def test_validate_seconds_at_max_ok():
    assert anp._validate_seconds("period", anp.MAX_PERIOD_SECONDS, anp.MAX_PERIOD_SECONDS) \
        == anp.MAX_PERIOD_SECONDS


def test_validate_seconds_beyond_max_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_seconds("period", anp.MAX_PERIOD_SECONDS + 0.001, anp.MAX_PERIOD_SECONDS)


def test_validate_seconds_hold_at_max_ok():
    assert anp._validate_seconds("hold-seconds", anp.MAX_HOLD_SECONDS, anp.MAX_HOLD_SECONDS) \
        == anp.MAX_HOLD_SECONDS


def test_validate_seconds_hold_beyond_max_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_seconds("hold-seconds", anp.MAX_HOLD_SECONDS + 0.001, anp.MAX_HOLD_SECONDS)


def test_validate_seconds_duration_at_max_ok():
    assert anp._validate_seconds("duration", anp.MAX_DURATION_SECONDS, anp.MAX_DURATION_SECONDS) \
        == anp.MAX_DURATION_SECONDS


def test_validate_seconds_duration_beyond_max_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_seconds("duration", anp.MAX_DURATION_SECONDS + 0.001, anp.MAX_DURATION_SECONDS)


def test_validate_count_at_max_ok():
    assert anp._validate_count(anp.MAX_COUNT) == anp.MAX_COUNT


def test_validate_count_beyond_max_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_count(anp.MAX_COUNT + 1)


def test_validate_seconds_zero_is_valid_no_wait():
    assert anp._validate_seconds("period", 0.0, anp.MAX_PERIOD_SECONDS) == 0.0


def test_validate_seconds_negative_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_seconds("period", -0.001, anp.MAX_PERIOD_SECONDS)


def test_validate_count_negative_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_count(-1)


def test_validate_count_zero_is_valid_writes_nothing():
    assert anp._validate_count(0) == 0


def test_validate_schedule_exactly_fits_ok():
    # period * (count-1) + hold == duration -- boundary AT the fit.
    anp._validate_schedule(count=3, period=1.0, hold=1.0, duration=3.0)


def test_validate_schedule_exceeds_duration_rejected():
    with pytest.raises(anp.ProbeArgError):
        anp._validate_schedule(count=3, period=1.0, hold=1.0, duration=2.999)


# ---------------------------------------------------------------------
# (B) in-process run(): write/cleanup/persist/dry-run/manifest
# ---------------------------------------------------------------------


def test_run_default_cleans_up_after_itself(tmp_path):
    target = tmp_path / "noise"
    rc = anp.run(_args(target_dir=str(target), count=3))
    assert rc == anp.EXIT_OK
    assert list(target.iterdir()) == []  # cleaned up, nothing left behind


def test_run_persist_leaves_files_behind(tmp_path):
    target = tmp_path / "noise"
    rc = anp.run(_args(target_dir=str(target), count=3, persist=True))
    assert rc == anp.EXIT_OK
    left = list(target.iterdir())
    assert len(left) == 3
    for p in left:
        assert p.name.startswith(anp.DEFAULT_MARKER_PREFIX)


def test_run_dry_run_writes_nothing(tmp_path):
    target = tmp_path / "noise"
    target.mkdir()
    rc = anp.run(_args(target_dir=str(target), count=5, dry_run=True))
    assert rc == anp.EXIT_OK
    assert list(target.iterdir()) == []


def test_run_manifest_out_lists_created_paths(tmp_path):
    target = tmp_path / "noise"
    manifest = tmp_path / "manifest.json"
    rc = anp.run(_args(target_dir=str(target), count=2, persist=True, manifest_out=str(manifest)))
    assert rc == anp.EXIT_OK
    listed = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(listed) == 2
    for p in listed:
        assert Path(p).exists()


def test_clean_manifest_removes_listed_files(tmp_path):
    target = tmp_path / "noise"
    manifest = tmp_path / "manifest.json"
    anp.run(_args(target_dir=str(target), count=2, persist=True, manifest_out=str(manifest)))
    assert len(list(target.iterdir())) == 2
    rc = anp._clean_manifest(str(manifest))
    assert rc == anp.EXIT_OK
    assert list(target.iterdir()) == []


def test_run_over_count_limit_refused_writes_nothing(tmp_path):
    target = tmp_path / "noise"
    with pytest.raises(anp.ProbeArgError):
        anp.run(_args(target_dir=str(target), count=anp.MAX_COUNT + 1))
    assert not target.exists() or list(target.iterdir()) == []


def test_run_never_touches_preexisting_unrelated_file(tmp_path):
    target = tmp_path / "noise"
    target.mkdir()
    other = target / "unrelated_real_file.jsonl"
    other.write_text("REAL CONTENT, MUST SURVIVE", encoding="utf-8")
    rc = anp.run(_args(target_dir=str(target), count=3))
    assert rc == anp.EXIT_OK
    assert other.read_text(encoding="utf-8") == "REAL CONTENT, MUST SURVIVE"


def test_write_one_noise_file_never_overwrites_existing_path(tmp_path):
    """Direct unit proof of the 'x' mode safety rail: if the computed
    noise filename ever collided with an existing file, the write must
    refuse (FileExistsError), never silently overwrite it. (Signature
    updated for Ф2, критик-гейт t-554 batch 2: `_write_one_noise_file`
    now takes the already-computed *path* directly, see `_noise_path`.)"""
    target = tmp_path
    fixed_name = "ambient-noise-probe-COLLISION.jsonl"
    path = target / fixed_name
    path.write_text("PRE-EXISTING, MUST NOT BE TOUCHED", encoding="utf-8")
    with pytest.raises(FileExistsError):
        anp._write_one_noise_file(path, anp.DEFAULT_MARKER_PREFIX, 0)
    assert path.read_text(encoding="utf-8") == "PRE-EXISTING, MUST NOT BE TOUCHED"


def test_run_target_dir_does_not_exist_yet_is_created(tmp_path):
    # "несуществующий тестовый путь" / "отсутствующий живой каталог" --
    # both exercise the same auto-mkdir path (module docstring).
    target = tmp_path / "does" / "not" / "exist" / "yet"
    assert not target.exists()
    rc = anp.run(_args(target_dir=str(target), count=1, persist=True))
    assert rc == anp.EXIT_OK
    assert target.is_dir()
    assert len(list(target.iterdir())) == 1


def test_run_target_dir_is_a_file_refused(tmp_path):
    target = tmp_path / "a_file_not_a_dir"
    target.write_text("I am a file", encoding="utf-8")
    with pytest.raises(anp.ProbeArgError):
        anp.run(_args(target_dir=str(target), count=1))
    assert target.read_text(encoding="utf-8") == "I am a file"


def test_run_unicode_path_succeeds(tmp_path):
    target = tmp_path / "шумовой-каталог-éü"
    rc = anp.run(_args(target_dir=str(target), count=2, persist=True))
    assert rc == anp.EXIT_OK
    assert len(list(target.iterdir())) == 2


def test_run_write_failure_mid_loop_cleans_up_and_reports(tmp_path, monkeypatch):
    """Simulated read-only-directory class: the second write raises
    OSError -- run() must clean up the first (already-created) file and
    return EXIT_WRITE_ERROR, not crash."""
    target = tmp_path / "noise"
    target.mkdir()
    orig = anp._write_one_noise_file
    calls = {"n": 0}

    def flaky(path, marker_prefix, index):
        calls["n"] += 1
        if calls["n"] == 2:
            raise PermissionError("simulated read-only directory")
        return orig(path, marker_prefix, index)

    monkeypatch.setattr(anp, "_write_one_noise_file", flaky)
    rc = anp.run(_args(target_dir=str(target), count=5))
    assert rc == anp.EXIT_WRITE_ERROR
    assert list(target.iterdir()) == []  # cleaned up, nothing left behind


def test_run_signal_during_file_creation_still_cleaned_up(tmp_path, monkeypatch):
    """Ф2 (критик-гейт t-554 batch 2): registration in `created` now
    happens in run()'s loop BEFORE `_write_one_noise_file` is called, not
    after it returns -- so even an interruption landing INSIDE file
    creation (the file already exists on disk, Python has not yet
    returned control to the caller) is still cleaned up. Reproduced here
    by writing the file directly and THEN raising KeyboardInterrupt from
    inside the patched write function -- simulates 'a signal lands after
    the underlying open()+write but before the caller regains control'
    without depending on real OS signal-delivery timing."""
    target = tmp_path / "noise"
    target.mkdir()
    orig = anp._write_one_noise_file
    calls = {"n": 0}

    def flaky(path, marker_prefix, index):
        calls["n"] += 1
        if calls["n"] == 2:
            path.write_text('{"marker": "leaked-if-not-registered-before-creation"}\n',
                             encoding="utf-8")
            raise KeyboardInterrupt()
        return orig(path, marker_prefix, index)

    monkeypatch.setattr(anp, "_write_one_noise_file", flaky)
    rc = anp.run(_args(target_dir=str(target), count=5))
    assert rc == anp.EXIT_INTERRUPTED
    assert list(target.iterdir()) == []  # cleaned up, nothing left behind


def test_run_manifest_write_failure_does_not_block_cleanup(tmp_path):
    """Ф3 (критик-гейт t-554 batch 2): cleanup must run even when writing
    --manifest-out itself raises OSError. `finally` is reordered so
    cleanup runs BEFORE the manifest write -- a manifest-write failure
    (here: the manifest's parent directory does not exist) can no longer
    skip the cleanup loop that used to sit AFTER it in the same `finally`
    block (critic observed leftover noise files from exactly this
    ordering: an exception raised mid-`finally` skips everything still
    below it in that same block)."""
    target = tmp_path / "noise"
    bad_manifest = tmp_path / "no" / "such" / "dir" / "manifest.json"
    with pytest.raises(OSError):
        anp.run(_args(target_dir=str(target), count=3, manifest_out=str(bad_manifest)))
    assert list(target.iterdir()) == []  # cleanup ran despite the manifest write failing


def test_run_interrupted_mid_loop_cleans_up(tmp_path, monkeypatch):
    target = tmp_path / "noise"
    calls = {"n": 0}
    orig_sleep = anp.time.sleep

    def flaky_sleep(seconds):
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt()
        return orig_sleep(0)

    monkeypatch.setattr(anp.time, "sleep", flaky_sleep)
    rc = anp.run(_args(target_dir=str(target), count=5, period=0.01))
    assert rc == anp.EXIT_INTERRUPTED
    assert list(target.iterdir()) == []


def test_sigterm_restore_distinguishes_install_failure_from_none_previous_handler(tmp_path, monkeypatch):
    """Ф1 (критик-гейт t-554, batch 2 -- уборка при аварийном завершении):
    `signal.signal()` can legally return None on a SUCCESSFUL install too
    -- when the previous disposition wasn't itself a Python-registered
    handler. Before the fix, `old_sigterm_handler is not None` could not
    tell that case apart from "installation itself failed, nothing to
    restore", so restoration was silently skipped and the probe's own
    handler leaked into the rest of the process -- exactly the leak C-1's
    narrowed scope was meant to prevent. MUST be red on the pre-fix code
    (DoD's mandatory red-before test): reproduced here by forcing
    signal.signal() to return None on the INSTALL call specifically,
    while still performing the real registration underneath."""
    target = tmp_path / "noise"
    old_handler = signal.getsignal(signal.SIGTERM)
    orig_signal = signal.signal

    def fake_signal(signum, handler):
        prev = orig_signal(signum, handler)
        if handler is anp._sigterm_as_keyboard_interrupt:
            return None  # simulates CPython returning None on a SUCCESSFUL install
        return prev

    monkeypatch.setattr(anp.signal, "signal", fake_signal)
    try:
        rc = anp.run(_args(target_dir=str(target), count=1))
        handler_after_run = signal.getsignal(signal.SIGTERM)
    finally:
        signal.signal(signal.SIGTERM, old_handler)  # test hygiene, unconditional
    assert rc == anp.EXIT_OK
    assert handler_after_run is not anp._sigterm_as_keyboard_interrupt


def test_run_sigterm_mid_loop_takes_same_cleanup_path_as_keyboard_interrupt(tmp_path):
    """C-1 fix (критик-гейт t-554, 2026-08-20): SIGTERM is remapped to
    KeyboardInterrupt by _install_sigterm_handler(), called at the top
    of run() -- delivered here via signal.raise_signal(signal.SIGTERM),
    which the Python docs describe as invoking the registered handler
    SYNCHRONOUSLY, in-process (verified empirically on this platform
    before writing this test). os.kill(pid, SIGTERM)/Popen.terminate()
    are NOT used here -- on Windows both hard-kill via TerminateProcess
    and never reach ANY registered handler at all (documented Windows
    os.kill limitation, not something this test can exercise on this
    platform -- see the module docstring's TESTABILITY BOUNDARY note)."""
    target = tmp_path / "noise"
    old_handler = signal.getsignal(signal.SIGTERM)
    calls = {"n": 0}
    orig_sleep = anp.time.sleep

    def flaky_sleep(seconds):
        calls["n"] += 1
        if calls["n"] == 1:
            signal.raise_signal(signal.SIGTERM)
        return orig_sleep(0)

    try:
        anp.time.sleep = flaky_sleep
        rc = anp.run(_args(target_dir=str(target), count=5, period=0.01))
    finally:
        anp.time.sleep = orig_sleep
        signal.signal(signal.SIGTERM, old_handler)
    assert rc == anp.EXIT_INTERRUPTED
    assert list(target.iterdir()) == []


# ---------------------------------------------------------------------
# (C) subprocess: CLI smoke, stdin-devnull, exit codes, two-probes
# ---------------------------------------------------------------------


def _run_cli(argv, stdin_devnull=True):
    kwargs = dict(capture_output=True, text=True)
    if stdin_devnull:
        kwargs["stdin"] = subprocess.DEVNULL
    return subprocess.run([sys.executable, str(SCRIPT)] + argv, **kwargs)


def test_cli_missing_target_dir_exits_1_no_hang():
    result = _run_cli([])
    assert result.returncode == anp.EXIT_ARG_ERROR


def test_cli_dry_run_via_subprocess_stdin_devnull(tmp_path):
    target = tmp_path / "noise"
    result = _run_cli(["--target-dir", str(target), "--count", "2", "--dry-run"])
    assert result.returncode == anp.EXIT_OK
    data = json.loads(result.stdout)
    assert data["dry_run"] is True
    assert len(data["would_create"]) == 2
    assert not target.exists() or list(target.iterdir()) == []


def test_cli_over_period_limit_rejected():
    result = _run_cli(
        ["--target-dir", "irrelevant", "--count", "1", "--period", str(anp.MAX_PERIOD_SECONDS + 1)]
    )
    assert result.returncode == anp.EXIT_ARG_ERROR
    assert "period" in result.stderr


def test_cli_two_simultaneous_probes_no_collision(tmp_path):
    target = tmp_path / "shared-noise"
    target.mkdir()
    manifest_a = tmp_path / "manifest_a.json"
    manifest_b = tmp_path / "manifest_b.json"
    proc_a = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--target-dir", str(target), "--count", "5",
         "--persist", "--manifest-out", str(manifest_a)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    proc_b = subprocess.Popen(
        [sys.executable, str(SCRIPT), "--target-dir", str(target), "--count", "5",
         "--persist", "--manifest-out", str(manifest_b)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    out_a, err_a = proc_a.communicate(timeout=20)
    out_b, err_b = proc_b.communicate(timeout=20)
    assert proc_a.returncode == anp.EXIT_OK, err_a
    assert proc_b.returncode == anp.EXIT_OK, err_b

    files_a = set(json.loads(manifest_a.read_text(encoding="utf-8")))
    files_b = set(json.loads(manifest_b.read_text(encoding="utf-8")))
    assert files_a.isdisjoint(files_b)  # no collision between the two runs
    on_disk = {str(p) for p in target.iterdir()}
    assert files_a | files_b == on_disk  # both sets fully present, nothing lost

    # cleanup (test-owned tmp_path files, own manifests)
    anp._clean_manifest(str(manifest_a))
    anp._clean_manifest(str(manifest_b))
    assert list(target.iterdir()) == []
