# Delegated Task 6 — Subagent Transcripts in usage_report.py

Closed 2026-07-08. Review: ACCEPTED (Lead, Claude Fable 5).
Code commit: 75af5b5.

First delegated task executed as a live Claude Code subagent (Sonnet
builder, background dispatch per D-0040, flat delegation per D-0037)
rather than a separate operator-driven session. The Lead wrote the
spec, dispatched, and reviewed; the worker did not self-certify.

## Spec (Lead, 2026-07-07 — verbatim from CURRENT_CONTEXT.md)

Middle-class task (builder-tier). Bug: subagent transcripts live in
~/.claude/projects/<project>/<session-id>/subagents/agent-*.jsonl,
but transcript_glob() only matches <project>/*.jsonl — ALL sidechain
traffic is invisible to cc_usage (56 such files exist on this
machine already, 25 in D--AO3-tests). Verified live 2026-07-07:
a sonnet-5 subagent run (63 turns, isSidechain=true) landed only in
a subagents/ file.

1. Extend the import to also scan
   <projects>/<project>/*/subagents/*.jsonl. Verified facts about
   these files (2026-07-07, one file inspected — RE-VERIFY on more):
   per-line sessionId == the PARENT session UUID (so the existing
   sessionId-field preference already yields the right session);
   isSidechain true; assistant lines carry model + usage as usual;
   extra fields agentId, promptId exist.
2. Project attribution: Path(path).parent.name is 'subagents' for
   these files — derive the project from the correct ancestor
   (the directory directly under the projects root), for BOTH
   layouts, with a test for each.
3. Dedupe stays (session_id, requestId) — verify subagent lines
   carry requestId; if absent, the existing uuid fallback applies.
   Confirm no collision with parent-session rows on real data.
4. turn_index: per-file counter is acceptable (cosmetic, matches
   the accepted Task 5 note 1); do not renumber parent sessions.
5. Tests: fixture with a nested subagents/ layout; project
   attribution; idempotent re-import; existing 18 tools tests stay
   green. Acceptance: after import, cc_usage sidechain rows > 0 on
   this machine; the 2026-07-07 sonnet-5 subagent run (63 turns)
   appears under project D--AO3-tests with is_sidechain=1; re-run
   imports 0 new rows.

## Execution Report (Sonnet builder subagent, 2026-07-08 — verbatim)

### (a) What changed, file by file

**`tools/usage_report.py`**
- `transcript_glob(base_dir=None)`: now returns a **list** of two
  patterns instead of one string — `<base>/*/*.jsonl` (top-level) and
  `<base>/*/*/subagents/*.jsonl` (subagent/sidechain, new).
  Documented in its docstring.
- `iter_assistant_turns(path)`: project/session-id derivation now
  branches on whether `Path(path).parent.name == "subagents"`. For
  that layout, `project` is walked up 3 levels
  (`parent.parent.parent.name`) and the session-id fallback uses
  `parent.parent.name` (the `<session-id>` directory), not the file's
  own stem (which is the sub-agent id, e.g. `agent-a6d8...`, and
  would have been wrong). Top-level layout behavior is unchanged.
- `import_transcripts(glob_pattern, db_file)`: now accepts either a
  single glob string (backward compat) or a list/tuple of patterns;
  normalizes internally, dedupes matched paths via a `set` before
  processing so overlapping patterns can't double-process a file.
- `main()`/CLI: `--transcripts-glob` help text documents the new
  two-pattern default and that passing the flag replaces both
  defaults with one custom pattern (kept backward compatible — still
  a single string). The final print statement formats list vs. string
  patterns for readability.
- Module docstring extended with the re-verified empirical facts
  (below) and the `promptId` discrepancy.

**`tools/test_usage_report.py`**
- Added `_write_jsonl` / `_assistant_line` helpers to build tmp-dir
  fixture trees (can't hardcode the projects root per spec).
- 7 new tests: top-level project attribution, subagent project
  attribution, subagent session-id fallback (no `sessionId` field →
  must use directory name, not filename), `transcript_glob` returns
  2 patterns, combined-layout import (project/session/dedupe
  correctness across both layouts sharing one session id),
  subagent-layout idempotent re-import, and single-string-pattern
  backward compatibility.

### (b) Re-verification of spec's "verified facts" on real files

Scanned **all 61 real subagent files** on this machine (3829
assistant lines) rather than just one:
- `sessionId` == parent session directory name: **0 mismatches**
  (confirmed).
- `isSidechain`: **true on all 3829** lines (confirmed).
- `requestId`: **present on all 3829** lines, 0 missing — the `uuid`
  fallback path remains real-data-untested but is kept defensively.
- `agentId`: present on all 3829 lines (confirmed).
- `promptId`: **NOT found on any of the 3829 lines** — this
  contradicts the spec's claim. Noted in the docstring as a
  correction; harmless since neither field is read by the code.
- Dedupe collisions: checked across **all 14 sessions** that have a
  `subagents/` dir (parent-file turns vs. subagent-file turns, and
  subagent files vs. each other, by `session_id:requestId`) —
  **0 collisions** anywhere.

### (c) Test output

Before: 18 tests (per spec). After: **25 tests, all passing**
(`python -m pytest tools/ -q` → `25 passed`).

### (d) Real-import numbers

- Before: `cc_usage` had 9036 rows (top-level only, from Task 5).
- First real run (`python tools/usage_report.py --all`): **1941 new
  rows** imported from 87 session files (both patterns combined).
  Sidechain traffic now visible: 182,879,975 tok, $100.03 accounted,
  7.2% share of tokens, **1700 sidechain rows**.
- Final state: **10986 total rows, 1706 sidechain rows** (grew by 6
  more during my own live verification — see below).
- **The 2026-07-07 "63-turn sonnet-5 subagent run"**: I could not
  find a file with *exactly* 63 turns. Best match by every other
  criterion (project `D--AO3-tests`, session
  `45f39c87-c36e-4d9b-89ee-8a2744cacf9e`, `agentType:
  test-maintainer`, description "устранить BUG-002", model
  `claude-sonnet-5`, `isSidechain=true`, dated 2026-07-07) has
  **75 unique API turns** (161 raw JSONL lines) as of now. This
  session's subagent files (test-automator + fix-verifier +
  test-maintainer, all sonnet-5) total **145 sidechain rows** in
  `cc_usage` under `D--AO3-tests`/`is_sidechain=1` — confirmed
  present. My read: the file kept growing after the spec's same-day
  "63" snapshot; I flag this as a discrepancy rather than claiming an
  exact match.
- **Idempotency**: a naive second `python tools/usage_report.py` run
  showed 1–4 "new" rows per invocation — I traced this to **my own
  currently-running subagent session** (project
  `D--Improving-AI-Operating-System-for-LLMs`, `is_sidechain=1`)
  genuinely growing between separate tool calls (each Bash call is
  itself a new turn appended to that live transcript before the next
  run started) — not a dedup bug. Chaining two invocations in **one**
  Bash call (no intervening turn) gave the true answer: **`0 new
  row(s)`** on the second run. Idempotency confirmed.

### (e) Deviations / open questions

- `promptId` does not exist on this machine's subagent lines,
  contrary to the spec — documented, no functional impact.
- The "63 turns" figure in the spec/CURRENT_CONTEXT.md doesn't match
  any file today; I identified the best-match session by every other
  attribute and reported the actual current count (75) rather than
  forcing a match — worth a note back to whoever tracks that figure,
  since it will keep drifting on a live machine.
- No file/directory outside `tools/` was modified;
  `gateway/requests.db` was updated by the import as expected and is
  git-ignored (confirmed via `git status --ignored` / `.gitignore:3`).
- No commits were made, per constraints.

## Lead Review (Claude Fable 5, 2026-07-08)

Verdict: ACCEPTED. Independently verified, not taken from the report:

- Full diff reviewed: both layouts handled, path-set dedupe prevents
  double-processing on overlapping patterns, single-string backward
  compatibility preserved, code style matches the module.
- Tests re-run by the Lead: 74/74 green (25 tools + 49 gateway).
- DB re-queried by the Lead: 10986 total / 1706 sidechain rows;
  session 45f39c87 present under D--AO3-tests, is_sidechain=1,
  sonnet-5, 145 rows across its three subagent files ($4.84).
  Sidechain totals by project: D--AO3-tests 1232 rows $57.82,
  D--Dog 335 rows $25.41, this project 139 rows $17.01.
- The 63-vs-75-turn discrepancy is accepted as live-transcript drift
  (the spec's figure was a same-day snapshot); the executor's
  refusal to force a match is exactly the honesty the process wants.
- The "1–4 new rows between separate runs" investigation is correct
  and documents a real property: on a live machine the import is
  idempotent over a FIXED snapshot, while transcripts keep growing —
  future acceptance checks should chain the double-run in one command.
- Spec errata confirmed: promptId does not exist (0/3829 lines);
  requestId is universal, so the uuid fallback stays defensive-only.

Consequences recorded on acceptance:
- The AO3_tests retro baseline ($276.70, CURRENT_CONTEXT.md) now
  self-corrects: +$57.82 of previously invisible AO3 sidechain spend.
  All-projects sidechain share: 7.2% of tokens, $100.03 accounted.
- Delegation-table evidence (D-0034 stream): one builder-tier task
  spec'd, dispatched to a Sonnet subagent, executed with zero
  escalations and accepted on first review. Worker cost for the run:
  114,289 subagent tokens / 47 tool calls / ~8.4 min wall clock.
  First data point for "Implementation to a written spec, tests ->
  builder (Sonnet)" — status stays `estimated` (n=1; Update Rule 1
  needs volume before a status move).
