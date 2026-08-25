"""r3_integration_check -- a DETERMINISTIC informer for the "integration
review coverage" calibration check (a session-handoff/weekly-review
step): flags large commits in a recent window that carry no visible
critic trail in logs/routing-log.jsonl. No AI judgment anywhere in this
script -- only git and the journal.

WHAT IT DOES:
    1. `git log --numstat` over a window (--since, default "24 hours
       ago") -- every commit in that window, with its total changed
       line count (add+del from numstat) compared against
       LARGE_COMMIT_THRESHOLD_LINES (100).
    2. For every such LARGE commit -- search for a critic trail in
       logs/routing-log.jsonl: delegated agent=critic, OR accepted
       basis=critic, OR the substring "critic:" in an accepted line's
       notes -- inside a ts window BETWEEN NEIGHBORING COMMITS (the
       window's previous commit .. this commit; for the window's
       earliest commit, the lower bound is the nearest commit STRICTLY
       BEFORE --since, or unbounded if there is none). This is a
       HEURISTIC (a ts window, not causal linkage) -- always printed
       AS a heuristic, never as a fact.
    3. Prints: commits with no trail found are CANDIDATES for the
       calibration check ("a candidate, not a verdict -- the check
       decides"); commits with a trail print the trail itself for a
       human to read. Separately -- a count of the window's SMALL
       commits (<=100 lines) as INPUT DATA for a cumulative-review
       rule ("is this one topic across a series of small commits" is
       NOT automated by this script -- that judgment belongs to the
       Lead/coordinator).

EXIT: ALWAYS 0 -- this is an informer, not a gate (the block-gate for
this class of finding, if any, fires on a RECORDED RECURRENCE, not on
every run of this script). Even an internal error (git unavailable, the
journal entirely corrupt) is printed to stderr and does NOT raise the
exit code -- deliberately, so this script can never become an
accidental gate when called from session handoff.

READ BOUNDARIES: this script ONLY READS git (`git log`, read-only) and
the file logs/routing-log.jsonl (read-only). No writes at all -- not to
the journal, not to git, not anywhere else.

BUILDER DESIGN DECISIONS (the source spec calls the whole mechanism a
heuristic; the forks below are choices INSIDE that heuristic, not
covered by the spec literally):
    - the "neighboring commit" used for the window's lower ts bound is
      ANY commit of the window (not only a large one), in chronological
      order; this is more precise than "the previous LARGE commit",
      since it doesn't widen the search window across unrelated
      intermediate commits.
    - a binary file in numstat ("-\t-\tpath") contributes 0 lines (the
      line count is unknown, not "a lot").
    - the substring "critic:" in notes is searched literally, BUT the
      form "critic:<whitespace>skipped" (case-insensitive) is an
      ANTI-TRAIL, not counted as a find (a live precedent: a note
      literally reading "critic: skipped" was once printed as FOUND,
      even though it's a record of the critic's ABSENCE); a valid
      token form like "critic:t-NNN" and any other NON-skipped
      occurrence still count as a trail as before; a mixed line
      (anti-trail + a valid token) is a MATCH (the valid token
      outweighs the anti-trail). The printed trail carries the notes
      fragment +-40 characters around the matched occurrence
      (newlines sanitized) -- see _find_critic_notes_match.
    - the ts window's bounds are INCLUSIVE on both sides.
    - timestamps are compared AS STRINGS (ISO local time with no
      timezone -- this journal's own format; git dates are requested
      in the same format via --date=format-local, so the comparison is
      correct lexicographically with no date parsing in Python).

CLI:
    python tools/r3_integration_check.py [--since <git-date>]
        [--journal PATH] [--threshold N]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # safe output on Windows consoles with a non-UTF8 codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

LARGE_COMMIT_THRESHOLD_LINES = 100
COMMIT_MARKER = "COMMIT\x1f"
_FIELD_SEP = "\x1f"
DEFAULT_SINCE = "24 hours ago"
DEFAULT_JOURNAL_REL = "logs/routing-log.jsonl"


# ---------------------------------------------------------------------
# Pure parsing functions -- tested on fixture strings, WITHOUT git.
# ---------------------------------------------------------------------


def _safe_int(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        return 0


def parse_git_log_numstat(raw: str) -> List[Dict[str, Any]]:
    """Parses the output of
    `git log --numstat --pretty=format:COMMIT<0x1f>%H<0x1f>%ad --reverse`
    (chronological order is set by the caller's --reverse flag; this
    function preserves line order as-is).

    Returns a list of {"hash": str, "ts": str, "lines_changed": int} --
    one record per commit, in the order the headers appear in raw.

    Edges: a commit with no numstat lines at all (a merge commit
    without -m/--first-parent, an empty commit) -- lines_changed=0, a
    record is still created. A binary file ("-\\t-\\tpath") --
    contributes 0. Garbage lines before the first COMMIT header --
    ignored. An empty raw -> an empty list (the "empty window" edge)."""
    commits: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in raw.splitlines():
        if line.startswith(COMMIT_MARKER):
            if current is not None:
                commits.append(current)
            parts = line[len(COMMIT_MARKER):].split(_FIELD_SEP)
            commit_hash = parts[0] if len(parts) > 0 else ""
            ts = parts[1] if len(parts) > 1 else ""
            current = {"hash": commit_hash, "ts": ts, "lines_changed": 0}
            continue
        if current is None:
            continue  # a line before the first header -- not our format
        stripped = line.strip()
        if not stripped:
            continue  # a blank separator line git puts between blocks
        fields = line.split("\t")
        if len(fields) != 3:
            continue  # not a numstat triple (edge: a commit with no numstat pairs)
        added_raw, deleted_raw, _path = fields
        added = 0 if added_raw == "-" else _safe_int(added_raw)
        deleted = 0 if deleted_raw == "-" else _safe_int(deleted_raw)
        current["lines_changed"] += added + deleted
    if current is not None:
        commits.append(current)
    return commits


_CRITIC_MARKER = "critic:"
_NOTES_FRAGMENT_RADIUS = 40  # characters around a match, for the printed trail

# ANTI-TRAIL: "critic: skipped" (any case, the space after ":" is
# optional) -- a literal record of the critic's ABSENCE, not of its
# trail. Live precedent: a note reading "critic: skipped -- reserve
# concession" inside an accepted event of a 900-line commit used to
# print as FOUND before this fix, even though there was no critic at
# all.
_CRITIC_SKIP_AFTER_RE = re.compile(r"\s*skipped", re.IGNORECASE)


def _find_critic_notes_match(notes: str) -> "tuple[bool, Optional[str]]":
    """Scans EVERY occurrence of the literal substring "critic:" in
    notes, left to right. An occurrence shaped "critic:<whitespace>
    skipped" (any case) is an anti-trail, skipped over. The FIRST
    occurrence that is NOT an anti-trail (including a valid
    "critic:t-NNN" token form) gives a match: returns (True, the
    fragment +-40 characters around the occurrence, newlines replaced
    with a space). If EVERY occurrence is an anti-trail (or there are
    no occurrences at all) -- (False, None): a mixed line like
    "critic: skipped ... critic:t-593" is a MATCH (the valid token
    outweighs the anti-trail), since scanning continues past a
    skipped anti-trail."""
    start = 0
    while True:
        idx = notes.find(_CRITIC_MARKER, start)
        if idx == -1:
            return False, None
        after = notes[idx + len(_CRITIC_MARKER):]
        if _CRITIC_SKIP_AFTER_RE.match(after):
            start = idx + len(_CRITIC_MARKER)
            continue  # an anti-trail -- keep looking for the next occurrence
        frag_start = max(0, idx - _NOTES_FRAGMENT_RADIUS)
        frag_end = min(len(notes), idx + len(_CRITIC_MARKER) + _NOTES_FRAGMENT_RADIUS)
        fragment = notes[frag_start:frag_end].replace("\n", " ").replace("\r", " ")
        return True, fragment


def find_critic_trail(
    journal_lines: Iterable[str],
    window_start: Optional[str],
    window_end: str,
) -> List[Dict[str, Any]]:
    """Searches for a critic trail among journal lines (each one a
    single JSON line of routing-log.jsonl) inside the ts window
    [window_start, window_end] (both bounds inclusive; window_start=
    None means the lower bound is unbounded). A match is any of:
        - event == "delegated" and agent == "critic"
        - event == "accepted" and basis == "critic"
        - event == "accepted" and a valid (non-anti-trail) "critic:"
          occurrence in notes -- see _find_critic_notes_match
    Timestamps are compared as strings (this journal's own format --
    ISO local time with no timezone, lexicographically sortable).

    Returns a list of COPIES of the matching events; each carries an
    added internal key "_notes_fragment" (the notes fragment around
    the matched occurrence, or None if the match came from a
    non-notes signal) -- printed by build_report so a reader can tell
    which form of match fired.

    Edges: a broken JSON line -- skipped (counted as neither a find
    nor its absence, doesn't abort parsing -- the DoD edge "broken
    journal JSON lines"); a line with no ts, or a non-string ts --
    skipped (it can't be placed inside the window); an empty journal /
    every event outside the window -> an empty list (the "journal with
    no critic events" edge); notes shaped "critic: skipped" -- an
    ANTI-TRAIL, not counted as a find."""
    matches: List[Dict[str, Any]] = []
    for raw_line in journal_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # a broken line -- skip, not a parse failure
        if not isinstance(obj, dict):
            continue
        ts = obj.get("ts")
        if not isinstance(ts, str) or not ts:
            continue
        if window_start is not None and ts < window_start:
            continue
        if ts > window_end:
            continue
        event = obj.get("event")
        agent = obj.get("agent")
        notes = obj.get("notes")
        notes_text = notes if isinstance(notes, str) else ""
        is_critic_delegated = event == "delegated" and agent == "critic"
        is_basis_critic = event == "accepted" and obj.get("basis") == "critic"
        notes_matched, notes_fragment = (
            _find_critic_notes_match(notes_text) if event == "accepted" else (False, None)
        )
        if is_critic_delegated or is_basis_critic or notes_matched:
            enriched = dict(obj)
            enriched["_notes_fragment"] = notes_fragment
            matches.append(enriched)
    return matches


def classify_commits(
    commits: List[Dict[str, Any]], threshold: int = LARGE_COMMIT_THRESHOLD_LINES
) -> Dict[str, List[Dict[str, Any]]]:
    """Splits a chronologically ordered commit list (see
    parse_git_log_numstat) into "large" (lines_changed > threshold) and
    "small" (<= threshold). Returns {"large": [...], "small": [...]} --
    each "large" element additionally carries "window_start" (the ts of
    the PREVIOUS commit in the commits list, of any size, or None for
    the very first) and "window_end" (its own ts)."""
    large: List[Dict[str, Any]] = []
    small: List[Dict[str, Any]] = []
    prev_ts: Optional[str] = None
    for commit in commits:
        if commit["lines_changed"] > threshold:
            enriched = dict(commit)
            enriched["window_start"] = prev_ts
            enriched["window_end"] = commit["ts"]
            large.append(enriched)
        else:
            small.append(commit)
        prev_ts = commit["ts"]
    return {"large": large, "small": small}


# ---------------------------------------------------------------------
# I/O plumbing -- the git subprocess (read-only) and journal reading.
# ---------------------------------------------------------------------


def _run_git(args: List[str]) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def fetch_window_commits(since: str) -> List[Dict[str, Any]]:
    """git log --numstat, read-only, chronological order (--reverse)."""
    raw = _run_git(
        [
            "log",
            f"--since={since}",
            "--numstat",
            "--date=format-local:%Y-%m-%dT%H:%M:%S",
            f"--pretty=format:{COMMIT_MARKER}%H{_FIELD_SEP}%ad",
            "--reverse",
        ]
    )
    return parse_git_log_numstat(raw)


def fetch_boundary_ts(since: str) -> Optional[str]:
    """ts of the nearest commit STRICTLY BEFORE --since (the lower
    bound for the window's earliest commit). None if no such commit
    exists (--since is earlier than the repo's first commit)."""
    raw = _run_git(
        [
            "log",
            "-1",
            f"--before={since}",
            "--date=format-local:%Y-%m-%dT%H:%M:%S",
            "--pretty=format:%ad",
        ]
    )
    ts = raw.strip()
    return ts or None


def read_journal_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


# ---------------------------------------------------------------------
# The report.
# ---------------------------------------------------------------------


def build_report(
    since: str,
    commits: List[Dict[str, Any]],
    journal_lines: List[str],
    threshold: int = LARGE_COMMIT_THRESHOLD_LINES,
    boundary_ts: Optional[str] = None,
) -> str:
    classified = classify_commits(commits, threshold=threshold)
    large = classified["large"]
    small = classified["small"]
    # window_start=None on the list's very first large commit means
    # "no previous commit IN THIS LIST" -- substitute boundary_ts (the
    # nearest commit before --since), if there is one.
    lines: List[str] = []
    lines.append("=== r3_integration_check (integration review coverage informer) ===")
    lines.append(f'window: --since="{since}"')
    lines.append(
        f"commits in window: {len(commits)} "
        f"(large >{threshold} lines: {len(large)}, small <= {threshold}: {len(small)})"
    )
    lines.append("")
    lines.append(
        f"--- LARGE COMMITS (>{threshold} lines, potential targets for the calibration check) ---"
    )
    if not large:
        lines.append("  (no large commits in this window)")
    for commit in large:
        window_start = commit["window_start"]
        if window_start is None:
            window_start = boundary_ts  # may stay None -- unbounded
        window_end = commit["window_end"]
        window_label = f"[{window_start if window_start is not None else '-inf'} .. {window_end}]"
        short_hash = commit["hash"][:8] if commit["hash"] else "?"
        lines.append(
            f"{short_hash} ts={commit['ts']} total={commit['lines_changed']}"
        )
        trail = find_critic_trail(journal_lines, window_start, window_end)
        if trail:
            lines.append(
                f"  critic trail FOUND ({len(trail)} event(s) in window {window_label}, a ts heuristic):"
            )
            for ev in trail:
                lines.append(
                    f"    - event={ev.get('event')} agent={ev.get('agent')} "
                    f"basis={ev.get('basis')} ts={ev.get('ts')}"
                )
                fragment = ev.get("_notes_fragment")
                if fragment:
                    lines.append(f'      notes fragment: "...{fragment}..."')
        else:
            lines.append(f"  critic trail NOT FOUND in window {window_label}")
            lines.append(
                "  -> CANDIDATE, not a verdict -- the calibration check decides "
                '(heuristic: agent=critic delegated / basis=critic accepted / '
                'the substring "critic:" in an accepted line\'s notes, a ts window '
                "between neighboring commits)"
            )
    lines.append("")
    lines.append(f"--- SMALL COMMITS in this window (<= {threshold} lines): {len(small)} ---")
    lines.append(
        "  input data for the cumulative-review rule (\"is this one topic\" "
        "across a series of small commits is a Lead/coordinator judgment, "
        "NOT automated by this script)"
    )
    for commit in small:
        short_hash = commit["hash"][:8] if commit["hash"] else "?"
        lines.append(f"  {short_hash} ts={commit['ts']} total={commit['lines_changed']}")
    lines.append("")
    lines.append("exit: 0 (an informer, not a gate -- gating on this class of finding, if any, fires on a recorded recurrence)")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "A deterministic informer for the integration review coverage "
            "check: large commits in the window with no critic trail found "
            "in logs/routing-log.jsonl. Reads git and the journal, writes "
            "nothing. Exit is always 0."
        )
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=f'lower bound of the window, git --since format (default "{DEFAULT_SINCE}")',
    )
    parser.add_argument(
        "--journal",
        default=None,
        help=f"path to the journal (default {DEFAULT_JOURNAL_REL} from the repo root)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=LARGE_COMMIT_THRESHOLD_LINES,
        help=f"the 'large commit' threshold in lines (default {LARGE_COMMIT_THRESHOLD_LINES})",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = _repo_root()
        journal_path = (
            Path(args.journal) if args.journal else repo_root / DEFAULT_JOURNAL_REL
        )
        commits = fetch_window_commits(args.since)
        boundary_ts = fetch_boundary_ts(args.since)
        journal_lines = read_journal_lines(journal_path)
        report = build_report(
            args.since,
            commits,
            journal_lines,
            threshold=args.threshold,
            boundary_ts=boundary_ts,
        )
        print(report)
    except Exception as exc:  # noqa: BLE001 -- an informer is never a gate
        print(
            f"r3_integration_check: internal error, no report was built: {exc}",
            file=sys.stderr,
        )
    return 0  # ALWAYS -- an informer, not a gate


if __name__ == "__main__":
    sys.exit(main())
