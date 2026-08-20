"""tools/ambient_noise_probe.py -- a PERMANENT, reusable CLI that
simulates the write activity of an AMBIENT (concurrent) session inside
a target directory, for reproducing the "canon test reads live state
and flakes under a concurrent writer" class (узел C, calibration №8
remediation, docs/tasks/2026-08-20_calibration-8-remediation.md, node
C). A ONE-OFF script for the same purpose would die with the
transcript that produced it (exactly the class узел F0 of this same
remediation had to recover from) -- this file is committed and carries
its own permanent test suite (tools/test_ambient_noise_probe.py).

WHAT IT DOES: writes a small number of marker-prefixed JSONL "noise"
files into a target directory, spaced by a configurable period, then
optionally HOLDS (sleeps) for a further window before exiting -- long
enough for a caller to run something else (a pytest invocation) while
the noise is present on disk. Cleanup of every file THIS invocation
created happens in a `finally` block: normal completion, an
argument-validation refusal, or an interruption (KeyboardInterrupt or
SIGTERM) all take the same cleanup path, unless `--persist` is given
(the noise is left behind for a caller-driven cleanup, e.g. a second
`--clean-manifest` invocation of this same script). SIGTERM is
remapped to KeyboardInterrupt by an installed handler (see
`_install_sigterm_handler`) precisely so it hits this SAME `except
KeyboardInterrupt` / `finally` path -- C-1 fix (критик-гейт t-554,
2026-08-20; this promise was made by an earlier revision of this
docstring with no `signal` import anywhere in the file to back it,
caught by `grep -i signal` coming up empty against the promise). The
handler is installed ONLY around the interruptible section inside
run() and restored to whatever it was before in `finally` --
`signal.signal()` mutates the process-wide disposition table, so a
handler left installed after run() returns would silently repoint
SIGTERM for the rest of the process (e.g. the rest of a pytest
session), not just for the schedule this call is protecting.
TESTABILITY BOUNDARY (docstring may not promise more than a test
proves, rule 6a): the handler is exercised in
tools/test_ambient_noise_probe.py via `signal.raise_signal(signal.
SIGTERM)`, which the Python docs describe as invoking the registered
handler synchronously, in-process. `os.kill(pid, signal.SIGTERM)` and
`subprocess.Popen.terminate()` are NOT exercised for this handler on
this platform: on Windows both hard-kill via `TerminateProcess`
unconditionally and never reach ANY Python-registered signal handler
(a documented Windows `os.kill` limitation, not a gap in this file) --
so the guarantee stated here is scoped to in-process signal delivery,
not to "kill this process from another process and the handler still
runs."

SAFETY RAILS (DoD point 7, this batch):
  1. Only ever CREATES files of its own, named
     "<marker-prefix><token>.jsonl" under the target directory --
     never opens an existing file for writing, never appends to one.
  2. Cleanup runs in `finally` -- an interrupted run removes exactly
     the files it itself already created, nothing else.
  3. subprocess launches of this script (see test suite) route stdin
     to devnull -- this script itself never reads stdin, so nothing to
     guard here directly, but the invariant is asserted by the tests
     that launch it as a subprocess.

LIMITS (rule 6a CLAUDE.md -- every boundary gets an AT and a BEYOND
test in tools/test_ambient_noise_probe.py):
  MAX_COUNT=200, MAX_PERIOD_SECONDS=5.0, MAX_HOLD_SECONDS=120.0,
  MAX_DURATION_SECONDS=300.0. All four are validated BEFORE any file
  is written -- an over-limit request writes NOTHING (refuse, exit 1),
  never a partial/clamped run. `--duration` is an explicit ceiling the
  caller states for the whole schedule (period * (count-1) + hold);
  a schedule that would exceed it is refused the same way.

NEGATIVE SECONDS: period/hold/duration accept 0 (valid -- "no wait")
but reject a NEGATIVE value (exit 1) -- a negative wait is nonsensical,
not merely a large one; kept as a separate check from the MAX-boundary
checks per the DoD's own adversarial-battery item list.

EXIT CODES: 0 ok; 1 argument/schedule validation refused (nothing
written); 2 a write itself failed mid-run (e.g. a read-only
target-dir -- files already created THIS run are still cleaned up
unless --persist); 130 interrupted (KeyboardInterrupt) -- same cleanup
guarantee as exit 2.

WHY NOT USED FOR узел C's A3 CASE: the only way to make
tools/test_critic_snapshot.py's A3 case observe a live diff is to
mutate the REAL .claude/critic_snapshot.json -- forbidden outright by
CLAUDE.md command-hygiene rule 7(г) ("боевой артефакт... не портится
ВОВСЕ"). A3's fix direction is therefore "stop reading the live file
at all" (see the accompanying test rewrite), not "reproduce the noise"
-- this probe is deliberately not pointed at .claude/ for that reason.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

DEFAULT_MARKER_PREFIX = "ambient-noise-probe-"

MAX_COUNT = 200
MAX_PERIOD_SECONDS = 5.0
MAX_HOLD_SECONDS = 120.0
MAX_DURATION_SECONDS = 300.0

EXIT_OK = 0
EXIT_ARG_ERROR = 1
EXIT_WRITE_ERROR = 2
EXIT_INTERRUPTED = 130


class ProbeArgError(Exception):
    """Raised for any argument-validation refusal -- caught once in
    main(), converted to a clean stderr message + EXIT_ARG_ERROR, never
    a traceback."""


def _sigterm_as_keyboard_interrupt(signum, frame) -> None:
    """C-1 fix: remaps SIGTERM onto the SAME `except KeyboardInterrupt`
    path that Ctrl+C already uses inside run() -- one cleanup path for
    both interruption forms, matching the module docstring's promise."""
    raise KeyboardInterrupt()


_NOT_INSTALLED = object()
"""Sentinel returned ONLY by `_install_sigterm_handler()`'s `except`
branch (Ф1, критик-гейт t-554 batch 2 -- уборка при аварийном
завершении). `signal.signal()` can legally return None on a
SUCCESSFUL install too, when the previous disposition was not itself
set from Python -- that case must NOT be confused with "installation
itself failed, nothing to restore" (a bare `None` return used to mean
both, and the caller silently skipped restoration for the second
case, leaking this module's handler into the rest of the process).
`_NOT_INSTALLED` is never a valid *previous handler* value, so
`old_sigterm_handler is not _NOT_INSTALLED` in run()'s `finally`
cleanly separates the two."""


def _install_sigterm_handler():
    """Best-effort; SIGTERM is one of the signals Python explicitly
    allows registering on Windows too (see `signal.signal` docs), but a
    try/except guards against any interpreter/embedding context that
    forbids signal() outside the main thread -- silent no-op there,
    Ctrl+C (KeyboardInterrupt) still works regardless. Returns the
    PREVIOUS handler -- which may itself legitimately be None (see
    `_NOT_INSTALLED` above) -- or the `_NOT_INSTALLED` sentinel on
    failure, so the caller (run(), below) can restore it once the
    schedule this run() call is protecting is over -- installing it is
    process-global (signal.signal mutates the CURRENT process's
    disposition table, not just this call), so run() restores it in
    `finally` rather than leaving every future caller of this module in
    the SAME process silently repointed at this handler after just one
    run() call returns."""
    try:
        return signal.signal(signal.SIGTERM, _sigterm_as_keyboard_interrupt)
    except (ValueError, OSError, AttributeError):
        return _NOT_INSTALLED


def _validate_seconds(name: str, value: float, max_value: float) -> float:
    if value < 0:
        raise ProbeArgError(f"--{name} must not be negative (got {value!r})")
    if value > max_value:
        raise ProbeArgError(f"--{name} exceeds the hard limit {max_value} (got {value!r})")
    return value


def _validate_count(count: int) -> int:
    if count < 0:
        raise ProbeArgError(f"--count must not be negative (got {count!r})")
    if count > MAX_COUNT:
        raise ProbeArgError(f"--count exceeds the hard limit {MAX_COUNT} (got {count!r})")
    return count


def _validate_schedule(count: int, period: float, hold: float, duration: float) -> None:
    """The whole planned schedule (writes spaced by *period*, plus the
    trailing *hold*) must fit inside the caller-stated *duration*
    ceiling -- refused up front, never truncated mid-run."""
    planned = period * max(count - 1, 0) + hold
    if planned > duration:
        raise ProbeArgError(
            f"planned schedule ({planned:.3f}s = period*{max(count - 1, 0)} + hold) "
            f"exceeds --duration {duration:.3f}s"
        )


def _validate_target_dir(target_dir: Path, dry_run: bool) -> None:
    if target_dir.exists() and not target_dir.is_dir():
        raise ProbeArgError(f"target-dir exists and is not a directory: {target_dir}")
    if dry_run:
        return
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ProbeArgError(f"cannot create/use target-dir {target_dir}: {exc}") from exc


def _noise_filename(marker_prefix: str, index: int) -> str:
    # pid + uuid4 -- unique across TWO simultaneous probes hitting the
    # same target-dir (adversarial battery item), never collides with
    # another invocation's own filenames.
    token = f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}-{os.getpid()}-{index}-{uuid.uuid4().hex[:8]}"
    return f"{marker_prefix}{token}.jsonl"


def _noise_path(target_dir: Path, marker_prefix: str, index: int) -> Path:
    """Computes the destination path WITHOUT creating anything -- split
    out from `_write_one_noise_file` (Ф2, критик-гейт t-554 batch 2) so
    that run()'s loop can register the path in its cleanup list BEFORE
    the file exists on disk, not after."""
    return target_dir / _noise_filename(marker_prefix, index)


def _write_one_noise_file(path: Path, marker_prefix: str, index: int) -> Path:
    """Writes ONE noise file at the given, already-computed *path*. Ф2
    (критик-гейт t-554 batch 2): the caller (run()) is expected to have
    already registered *path* in its own cleanup list before calling
    this -- registering only AFTER a successful return (the previous
    shape) left a window where a signal landing between `open()`
    succeeding and the caller regaining control created a file cleanup
    never learned about."""
    line = json.dumps(
        {
            "ts": datetime.now().isoformat(timespec="microseconds"),
            "marker": marker_prefix.rstrip("-"),
            "index": index,
            "pid": os.getpid(),
        },
        ensure_ascii=False,
    )
    # Own file only, created fresh -- "x" mode refuses to silently
    # overwrite anything that might already exist under this exact
    # (already near-unique) name, per the "never opens a foreign
    # existing file for writing" safety rail.
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return path


def run(args: argparse.Namespace) -> int:
    marker_prefix = args.marker_prefix
    count = _validate_count(args.count)
    period = _validate_seconds("period", args.period, MAX_PERIOD_SECONDS)
    hold = _validate_seconds("hold-seconds", args.hold_seconds, MAX_HOLD_SECONDS)
    duration = _validate_seconds("duration", args.duration, MAX_DURATION_SECONDS)
    _validate_schedule(count, period, hold, duration)

    target_dir = Path(args.target_dir)
    _validate_target_dir(target_dir, args.dry_run)

    if args.dry_run:
        planned = [str(target_dir / _noise_filename(marker_prefix, i)) for i in range(count)]
        print(json.dumps({"dry_run": True, "would_create": planned}, ensure_ascii=False))
        return EXIT_OK

    created: list = []
    interrupted = False
    write_error = None
    # C-1: installed ONLY around the interruptible section below, and
    # restored in `finally` -- signal.signal() is process-global, so
    # leaving it installed after run() returns would silently repoint
    # SIGTERM for the REST of the process (e.g. the rest of a pytest
    # session) at this handler, not just for the schedule THIS call is
    # protecting.
    old_sigterm_handler = _install_sigterm_handler()
    try:
        for i in range(count):
            path = _noise_path(target_dir, marker_prefix, i)
            # Ф2 (критик-гейт t-554 batch 2): register BEFORE the file is
            # created, not after `_write_one_noise_file` returns -- this
            # closes the window where an interruption landing between the
            # underlying open() succeeding and this line running used to
            # leave one noise file outside `created`'s reach. Worst case
            # on the OSError-failure branch below (nothing was actually
            # written), the entry is popped right back off; on a
            # KeyboardInterrupt/SIGTERM landing mid-write, cleanup below
            # simply attempts an unlink() on a path that may not exist
            # yet, which is a no-op (OSError caught).
            created.append(path)
            try:
                _write_one_noise_file(path, marker_prefix, i)
            except OSError as exc:
                created.pop()  # nothing was actually written for this entry
                write_error = exc
                break
            if i < count - 1 and period > 0:
                time.sleep(period)
        if write_error is None and hold > 0:
            time.sleep(hold)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        if old_sigterm_handler is not _NOT_INSTALLED:
            # old_sigterm_handler may itself legitimately be None here
            # (Ф1: the PREVIOUS disposition was not a Python-registered
            # handler -- signal.signal() returns None for that case on a
            # SUCCESSFUL install, same value it would give for a genuine
            # no-op). signal.signal() rejects None as a handler value
            # outright (TypeError), so APPROXIMATE with SIG_DFL -- the
            # closest legal value, not a byte-exact restore of whatever
            # non-Python disposition actually preceded this run().
            restore_to = old_sigterm_handler if old_sigterm_handler is not None else signal.SIG_DFL
            try:
                signal.signal(signal.SIGTERM, restore_to)
            except (ValueError, OSError, AttributeError):
                pass
        # Ф3 (критик-гейт t-554 batch 2): cleanup runs BEFORE the manifest
        # write, not after -- an OSError from Path.write_text used to sit
        # ahead of the cleanup loop in this same `finally` block, so a
        # failed manifest write (e.g. an unwritable --manifest-out parent)
        # propagated out immediately and skipped cleanup entirely, leaving
        # every noise file from this run on disk. Cleanup no longer
        # depends on the manifest write succeeding.
        if not args.persist:
            for p in created:
                try:
                    p.unlink()
                except OSError:
                    pass
        if args.manifest_out:
            Path(args.manifest_out).write_text(
                json.dumps([str(p) for p in created], ensure_ascii=False), encoding="utf-8"
            )

    if interrupted:
        print(f"ambient_noise_probe.py: interrupted after {len(created)} file(s), cleaned up",
              file=sys.stderr)
        return EXIT_INTERRUPTED
    if write_error is not None:
        print(
            f"ambient_noise_probe.py: write failed after {len(created)} file(s) "
            f"({type(write_error).__name__}: {write_error}), cleaned up",
            file=sys.stderr,
        )
        return EXIT_WRITE_ERROR
    print(json.dumps({"created_count": len(created), "persisted": bool(args.persist)},
                      ensure_ascii=False))
    return EXIT_OK


def _clean_manifest(manifest_path: str) -> int:
    """`--clean-manifest PATH` mode: removes exactly the files listed in
    a JSON array written by a prior `--persist --manifest-out` run --
    the caller-driven cleanup counterpart, same "own files only"
    discipline (never globs the directory, only unlinks paths this
    tool itself wrote to the manifest)."""
    try:
        paths = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"ambient_noise_probe.py: cannot read manifest {manifest_path}: {exc}",
              file=sys.stderr)
        return EXIT_ARG_ERROR
    removed = 0
    for p in paths:
        try:
            Path(p).unlink()
            removed += 1
        except OSError:
            pass
    print(json.dumps({"removed_count": removed}, ensure_ascii=False))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-dir", help="directory to write noise files into")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--period", type=float, default=0.0)
    parser.add_argument("--hold-seconds", type=float, default=0.0)
    parser.add_argument("--duration", type=float, default=MAX_DURATION_SECONDS)
    parser.add_argument("--marker-prefix", default=DEFAULT_MARKER_PREFIX)
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--manifest-out", default=None)
    parser.add_argument("--clean-manifest", default=None,
                         help="cleanup mode: remove files listed in this manifest JSON and exit")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.clean_manifest:
        return _clean_manifest(args.clean_manifest)

    if not args.target_dir:
        print("ambient_noise_probe.py: --target-dir is required (unless --clean-manifest)",
              file=sys.stderr)
        return EXIT_ARG_ERROR

    try:
        return run(args)
    except ProbeArgError as exc:
        print(f"ambient_noise_probe.py: {exc}", file=sys.stderr)
        return EXIT_ARG_ERROR


if __name__ == "__main__":
    sys.exit(main())
