"""Sanitized-input feed for a live subscription-judge probe: the
carrier form of "does the judge role/prompt still reproduce its
calibration verdicts" checks (CLAUDE.md rule 13, judge acceptance).

Motive: periodically re-probe a live subscription-judge role (the
judge subagent carrying the pinned JUDGE_SYSTEM_PROMPT) against a
labeled calibration set (gateway/judge_calibration.json) to confirm
the equivalence point still holds for the current role-file/prompt
state. The judge must never see the KEY (the recorded verdict/
rationale, nor the "judge" attribution string naming who/what
produced them) -- only the acceptor holding the key can score the
probe's output against it. This script is the one place that performs
the split: it reads the single source of truth (gateway/
judge_calibration.json -- no second copy of the data is created,
SIBLING_MAP class: single-source-of-truth) and prints the key-stripped
material to stdout as JSON.

FIELD CONTRACT: the sanitized output for each pair carries EXACTLY
"prompt", "source_response", "target_response", "category" and a
1-based "pair_index" (its position in the source file, unchanged by
sanitizing -- the pair's identity for matching a judge verdict back to
the withheld key). "source_model"/"target_model" are dropped too, even
though the named key fields are only "verdict"/"rationale"/"judge":
gateway/shadow_eval.py's own JUDGE_SYSTEM_PROMPT docstring states the
judge "sees only the task and two anonymized answers, never model
names" -- carrying source_model/target_model into a judge-facing feed
would violate that same anonymization principle the prompt was
calibrated under, and the field list this script keeps is exactly
these five and no more. Flag this at acceptance if a given deployment
actually wants the model names kept.

EDGE BEHAVIOR:
  - A pair missing the "verdict" key (the calibration set could in
    principle be incomplete) does not raise -- it is sanitized like any
    other pair (whatever of the five kept fields it has), and counted.
  - Order is preserved exactly as read from the source file; pair_index is
    1-based and assigned by source position, never re-sorted.
  - Zero pairs is a valid result: stdout prints "[]", exit code 0, and a
    stderr line still reports the (zero) counter -- there is no special
    "nonzero exit for empty" case.
  - A counter is always written to stderr: "sanitized N pair(s) (M missing
    verdict field)" -- N is the total pairs processed, M counts pairs that
    lacked "verdict" specifically, regardless of N.

Usage:
    python tools/judge_calib_sanitize.py [path]
        path defaults to gateway/judge_calibration.json (repo-root-relative
        resolution via this script's own location, so it works regardless
        of the caller's cwd). An explicit path argument is a test/ops seam
        only -- production callers omit it.

Exit codes: 0 on success (including the zero-pairs case). 1 if the source
file cannot be read/decoded as UTF-8, is not valid JSON, or its root is not
a JSON array -- one ASCII diagnostic line on stderr, nothing on stdout
(fail-closed, mirrors this kit's other WARN-adjacent tools' style: no bare
traceback). 2 on a usage error (more than one CLI argument).

STDOUT ENCODING: the calibration set can carry non-ASCII characters
(observed: U+2192 RIGHTWARDS ARROW in one response text) that a plain
`sys.stdout.write(text)` can raise UnicodeEncodeError on -- not
intermittently, but DETERMINISTICALLY, whenever Python's stdout text
encoding is a narrow codepage (e.g. cp1251) rather than UTF-8. That
encoding choice depends on the console's codepage AND on environment
variables (PYTHONIOENCODING/PYTHONUTF8) that a caller may or may not
have set. Relying on the caller to set those variables is not
acceptable here (this script must be UTF-8 correct with no environment
precondition), so output is written as raw UTF-8 BYTES straight to
`sys.stdout.buffer`, bypassing the text-encoding layer entirely (see
`_write_stdout_utf8()`): this is correct and IDENTICAL whether stdout
is a real console (any codepage), redirected to a file, or captured
through a pipe (subprocess capture) -- there is no text-encoding step
left for the console's codepage to interfere with. `sys.stderr` is
never used for non-ASCII content in this script (only the fixed-format
counter line), so it is left as plain `sys.stderr.write()`.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_CALIBRATION_PATH = os.path.join(REPO_ROOT, "gateway", "judge_calibration.json")

KEY_FIELDS = ("verdict", "rationale", "judge")
KEPT_FIELDS = ("prompt", "source_response", "target_response", "category")


def _write_stdout_utf8(text):
    """Write text to stdout as raw UTF-8 bytes via sys.stdout.buffer,
    bypassing the platform/console text-encoding layer entirely -- see
    module docstring "STDOUT ENCODING". Falls back to a plain
    sys.stdout.write() only if stdout has no .buffer attribute at all
    (a text-only stream substituted by an unusual test harness); that
    fallback is best-effort and not the normal code path."""
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8"))
        buffer.flush()
    else:
        sys.stdout.write(text)


def load_pairs(path):
    """Return (pairs_list_or_None, error_str_or_None).

    Never raises: OSError, UnicodeDecodeError and json.JSONDecodeError are
    all converted into a single ASCII-safe error string; a root that
    parses but is not a JSON array is likewise reported as an error, not a
    crash.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return None, "cannot read file %s: %s" % (path, exc)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "file %s is not valid UTF-8" % path
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, "file %s is not valid JSON: %s" % (path, exc)
    if not isinstance(data, list):
        return None, "file %s: root is not a JSON array (type: %s)" % (
            path, type(data).__name__
        )
    return data, None


def sanitize_pairs(pairs):
    """Return (sanitized_list, missing_verdict_count).

    sanitized_list carries KEPT_FIELDS plus a 1-based "pair_index" per
    pair, in source order, unchanged. A pair missing any KEPT_FIELDS entry
    simply lacks that key in the sanitized dict (never invented as None or
    ""). A pair that is not itself a dict is skipped from the output but
    still occupies its pair_index position in the counting pass (it cannot
    have had a "verdict" key, so it counts toward missing_verdict_count).
    """
    sanitized = []
    missing_verdict = 0
    for idx, pair in enumerate(pairs, start=1):
        if not isinstance(pair, dict):
            missing_verdict += 1
            continue
        if "verdict" not in pair:
            missing_verdict += 1
        item = {"pair_index": idx}
        for field in KEPT_FIELDS:
            if field in pair:
                item[field] = pair[field]
        sanitized.append(item)
    return sanitized, missing_verdict


def main(argv):
    args = argv[1:]
    if len(args) > 1:
        sys.stderr.write("usage: judge_calib_sanitize.py [path]\n")
        return 2

    path = args[0] if args else DEFAULT_CALIBRATION_PATH

    pairs, err = load_pairs(path)
    if pairs is None:
        sys.stderr.write("JUDGE CALIB SANITIZE FAILED: %s\n" % err)
        return 1

    sanitized, missing_verdict = sanitize_pairs(pairs)
    _write_stdout_utf8(json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n")
    sys.stderr.write(
        "sanitized %d pair(s) (%d missing verdict field)\n"
        % (len(sanitized), missing_verdict)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
