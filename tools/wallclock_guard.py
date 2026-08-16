"""Shared wall-clock guard constants + helper (F-60, docs/FINDINGS.md).

t-453: `python -m pytest tools/ gateway/ -q` was observed non-deterministic
under third-party CPU load on the host machine -- three consecutive runs on
the same tree gave `2812 passed + 2 failed`, each time DIFFERENT two tests,
every failure a wall-clock assertion (fixed subprocess timeouts / fixed
`assert elapsed < N`), not a logic defect. Full analysis: docs/FINDINGS.md
S F-60.

TWO unrelated semantics live in this one file on purpose (F-60's own
finding: a THIRD mechanism -- the DEFAULT/inline VALUE split within one
file -- was itself a distinct failure mode, so both numbers get a single
source of truth each, used by every site of their class):

  WALLCLOCK_HARNESS_TIMEOUT (class A) -- a safety net around a
  subprocess.run(timeout=...) call in test harness plumbing (`_run_hook` /
  `_run_cli` / `_git` helpers and their inline call sites). This is NOT an
  assertion about the tested subject -- it only stops a genuinely hung
  child process from hanging the whole suite. Raising it costs nothing
  observable (a truly hung process still surfaces, just after up to 60s
  instead of 10-20s, inside a suite that already runs minutes).

  WALLCLOCK_CATASTROPHE_CEILING (class B) -- a catastrophe watchdog
  (`assert elapsed < N`) guarding against a real complexity regression
  (e.g. quadratic behaviour on a large input) that would take MINUTES or
  hang, not a few seconds under load. It is deliberately NOT an SLO/latency
  assertion; see each call site's own comment for the class-specific
  wording this file's docstring does not repeat.

`assert_under()` exists so this file's OWN limit -- the ceiling value
itself -- gets a fast, deterministic boundary test (CLAUDE.md R11 "тест
НА границе и ЗА ней") without needing an integration test that actually
waits tens of seconds: tools/test_wallclock_guard.py feeds `elapsed` as a
plain argument, no real clock involved.

This module is NOT a hook and is never placed on any execution path
(D-0069 does not apply) -- it is imported by test files only.
"""

# Класс A: сетка против зависшего дочернего процесса в обвязке гарнеса
# (subprocess.run(timeout=...) в _run_hook/_run_cli/_git и их inline
# сайтах) -- НЕ утверждение о предмете теста.
WALLCLOCK_HARNESS_TIMEOUT = 60

# Класс B: сторож катастрофы (assert elapsed < N) -- не SLO задержки.
WALLCLOCK_CATASTROPHE_CEILING = 30


def assert_under(elapsed, ceiling, what):
    """Raises AssertionError with an F-60-aware message when `elapsed` is
    not strictly under `ceiling`.

    Comparison is strict (`elapsed < ceiling`): exactly `ceiling` fails
    (F-60 remediation, "Ф9" -- unchanged from every existing call site's
    prior `assert elapsed < N` form). `what` is a short human label for
    the timed operation, embedded in the failure message so a red run
    names what was slow without the reader having to find the call site
    first.
    """
    assert elapsed < ceiling, (
        f"{what}: {elapsed:.2f}s >= {ceiling}s -- "
        "сторож стенных часов: проверь загрузку машины прежде, чем "
        "считать это дефектом (F-60)"
    )
