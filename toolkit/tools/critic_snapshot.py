"""critic_snapshot.py -- PreToolUse hook that records a tree snapshot
every time a critic dispatch fires, so acceptance can tell whether the
final state of the repo was actually reviewed (rule 3: critic is a
mandatory acceptance gate). The hook itself never blocks anything --
it only writes a fact; the accepting session (or a grader) is the one
that judges the fact's meaning (code guarantees the check gets
encountered, a tier above judges what it means).

On every Task/Agent dispatch where tool_input["subagent_type"] ==
"critic", this hook computes a hash of the whole working tree and
writes it to .claude/critic_snapshot.json as
{"ts": ISO, "tree_hash": str, "files_count": int, "skipped_files":
int}, overwriting any previous snapshot. Comparing the LATEST snapshot
against the tree at the end of a session tells you whether anything
changed AFTER the last critic dispatch -- a mismatch means "the final
state was not reviewed", a fact worth surfacing at acceptance, not a
block by itself.

tree_hash is sha256 over the sorted list of "{rel_path}:{sha256}" for
every file in the tree, excluding .claude/.git/__pycache__/
.pytest_cache (by directory name, at any depth) and
logs/routing-log.jsonl (the routing log changes on essentially every
turn and would make the hash useless as a "did the reviewed code
change" signal).

DIVERGENCE SEMANTICS, PRECISELY: "the snapshot diverges from the
final tree" means specifically "the tree changed AFTER the last
Task/Agent DISPATCH of a critic" -- not "after the last critic review"
in general. The distinction matters: a critic can review several
times within one and the same dispatch (the agent reads, comments,
re-reads) without a single new Task/Agent call -- the snapshot is
written by PreToolUse ONCE, at dispatch time, BEFORE the critic has
actually read anything in that call; any tree edits happening AFTER
that dispatch moment will look like "divergence" to this hook even if
the critic honestly re-read them within the SAME call (this already
covers staleness within one call -- the hook cannot see inside a call,
only the before/after snapshot relative to the dispatch moment).

Known limitation, documented rather than solved here: if a
coordinator keeps talking to an ALREADY-dispatched critic agent
through a continuation/follow-up channel (not a new Task/Agent call),
this hook does not fire again -- its matcher is registered only on
Task/Agent tool calls. A critic that re-reviews a diff several times
within one continued conversation, without a new dispatch, will look
to a grader like "the snapshot is stale" even though the re-review
genuinely happened. This is a limitation of the snapshot as a
measuring instrument, not evidence that no review took place; whether
to widen the hook's matcher to also catch continuation calls is a
judgment call for whoever owns this deployment's hook configuration,
not something this file decides for you.

LOUD FAIL-OPEN. Motivating class of incident (own inline account): a
critic dispatch fired, but .claude/critic_snapshot.json was never
updated -- the cause was swallowed whole by a bare
`except Exception: return 0` in main(): there was no trace of the
failure AT ALL, so "the snapshot was never taken" was indistinguishable
from "the snapshot is just old". A likely candidate cause is a tree
file locked by an external application at the moment of the walk, but
the exact trigger is secondary to the fix: fail-open MUST STAY (the
hook still never fails a dispatch on any exception, exit code is
always 0 -- an invariant that needs its own pin test), but a failure
is now VISIBLE through two independent channels:
 1. A diagnostic line on stderr (`critic_snapshot.py: FAILED to take
    snapshot (<ExceptionType>: <msg>)`) -- see
    _write_failure_snapshot().
 2. The failure fact recorded INTO .claude/critic_snapshot.json itself
    -- fields `error`/`error_ts` (WITHOUT the usual ts/tree_hash/
    files_count/skipped_files -- the failure document REPLACES the
    normal snapshot, it is not merged with it: a mixed document
    carrying both shapes would make it harder for a grader to tell
    "a snapshot was taken, with a caveat" apart from "no snapshot was
    taken at all" -- an own decision, documented, not guessed
    silently), so "no snapshot was taken" reads differently from "the
    snapshot is old" (an old snapshot carries the REAL ts of the
    previous successful call; a failure document carries the error_ts
    of the failure moment -- two different, never-mixed document
    shapes).
If even writing the failure document is impossible (e.g. the .claude/
directory is also unwritable) -- stderr ONLY, exit 0 regardless (see
main()/_write_failure_snapshot(): an inner try/except around the
failure-write itself -- belt-and-suspenders on top of
belt-and-suspenders, the same principle already running through this
whole module).

A failure document does not erase the last successful baseline: if the
file at the snapshot path already carried a REAL successful snapshot
(it carries the key "tree_hash", and is not itself a failure
document), its ts/tree_hash are copied into the failure document under
SEPARATE keys `prev_ts`/`prev_tree_hash` -- _read_prior_snapshot_fields().
The invariant "a failure document never looks like a valid snapshot"
still holds: a failure document never carries the key "tree_hash"
itself (only "prev_tree_hash" -- a deliberately different name), so a
grader can still unambiguously tell "a snapshot was taken" apart from
"no snapshot was taken, but here is the previous one's data".

TWO DISTINCT FAILURE POINTS, BOTH COVERED: main() wraps (a) the tree
walk (compute_tree_hash()) and (b) writing the snapshot (snap.write_text)
in SEPARATE try/except blocks -- EITHER branch leads to
_write_failure_snapshot(), but they are semantically different
("could not compute the hash" vs. "computed it, but could not write
it") -- both _write_failure_snapshot()'s and main()'s docstrings name
both explicitly.

A SINGLE UNREADABLE TREE FILE -- DECISION (the spec for this class of
edit can leave the choice between "skip with a counter" and "fail the
whole walk" open; documented here, not guessed silently):
compute_tree_hash() SKIPS a file whose read_bytes() raises an
exception (PermissionError/OSError/anything), incrementing a
`skipped_files` counter -- it does NOT fail the whole walk.
Rationale: a tree snapshot missing one unreadable file (e.g. locked by
an external application) is more useful than a TOTAL snapshot failure
over a SINGLE file -- the same fail-open principle that already runs
through this whole module (the snapshot is a measuring instrument, not
a gate). compute_tree_hash() now returns a TRIPLE (tree_hash,
files_count, skipped_files) instead of the previous pair.
`skipped_files` is written into a NORMAL (successful) snapshot too
(even when 0) -- the same "never a silent 0" discipline this kit
applies to money-shaped counters elsewhere, applied here to walk
telemetry.
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

EXCLUDED_DIR_NAMES = {".claude", ".git", "__pycache__", ".pytest_cache"}
EXCLUDED_REL_FILES = {Path("logs") / "routing-log.jsonl"}
SNAPSHOT_REL_PATH = Path(".claude") / "critic_snapshot.json"


def compute_tree_hash(root: Path) -> tuple[str, int, int]:
    """Returns (tree_hash, files_count, skipped_files). A SINGLE
    unreadable file (read_bytes() raises) does NOT fail the whole
    walk -- it is skipped, incrementing skipped_files -- see the
    module docstring, "A SINGLE UNREADABLE TREE FILE -- DECISION"."""
    entries = []
    skipped_files = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
            continue
        if rel in EXCLUDED_REL_FILES:
            continue
        try:
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            skipped_files += 1
            continue
        entries.append(f"{rel.as_posix()}:{digest}")
    tree = hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()
    return tree, len(entries), skipped_files


def _read_prior_snapshot_fields(snap: Path) -> dict:
    """Reads ts/tree_hash of the PREVIOUS snapshot document (if it
    exists, parses, AND is a REAL successful snapshot -- carries the
    key "tree_hash", is not itself a failure document) -- fail-open: a
    missing file / broken JSON / a failure document with no tree_hash
    -- {} (no prev_* fields on the resulting failure document, nothing
    is invented). Never raises outward."""
    try:
        prev = json.loads(snap.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(prev, dict) or "tree_hash" not in prev:
        return {}
    return {"prev_ts": prev.get("ts"), "prev_tree_hash": prev.get("tree_hash")}


def _write_failure_snapshot(snap: Path, exc: Exception) -> None:
    """Fail-open stays (the hook never fails a dispatch), but a
    failure is now LOUD -- see the module docstring, "LOUD FAIL-OPEN".
    The failure document REPLACES the normal one (it does not carry
    ts/tree_hash/files_count/skipped_files) -- the two document shapes
    are never mixed -- the invariant "a failure document never looks
    like a valid snapshot" holds LITERALLY (no key "tree_hash" in a
    failure document).

    A failure document does not erase the last successful baseline: if
    the EXISTING file at snap is a real successful snapshot (carries
    "tree_hash"), its ts/tree_hash are copied into the failure document
    under SEPARATE keys `prev_ts`/`prev_tree_hash` (the shapes are NOT
    mixed -- the failure document still never carries "tree_hash"
    itself, only "prev_tree_hash", a distinguishable key) -- see
    _read_prior_snapshot_fields(). If writing the failure document is
    ALSO impossible -- stderr only (the exception here is swallowed
    silently, ON PURPOSE -- this is the last fail-open backstop, the
    message already went to stderr above)."""
    diag = f"critic_snapshot.py: FAILED to take snapshot ({type(exc).__name__}: {exc})"
    print(diag, file=sys.stderr)
    try:
        doc = {
            "error": f"{type(exc).__name__}: {exc}",
            "error_ts": datetime.now().isoformat(),
        }
        doc.update(_read_prior_snapshot_fields(snap))
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(
            json.dumps(doc, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass  # stderr only -- see the module docstring, "LOUD FAIL-OPEN"


def main() -> int:
    # Raw-byte stdin read, decoded explicitly as UTF-8 -- see
    # dispatch_gate.py's main() for why this matters on platforms
    # whose locale encoding isn't UTF-8.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0  # fail open: not our format, don't get in the way

    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    if tool_name not in ("Task", "Agent"):
        return 0
    if tool_input.get("subagent_type") != "critic":
        return 0

    cwd = Path(payload.get("cwd") or ".")
    snap = cwd / SNAPSHOT_REL_PATH

    # Two DISTINCT failure points -- the tree walk and the snapshot
    # write -- see the module docstring, "TWO DISTINCT FAILURE POINTS".
    try:
        tree_hash, files_count, skipped_files = compute_tree_hash(cwd)
    except Exception as exc:
        _write_failure_snapshot(snap, exc)
        return 0

    try:
        snap.parent.mkdir(parents=True, exist_ok=True)
        snap.write_text(
            json.dumps(
                {
                    "ts": datetime.now().isoformat(),
                    "tree_hash": tree_hash,
                    "files_count": files_count,
                    "skipped_files": skipped_files,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception as exc:
        _write_failure_snapshot(snap, exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
