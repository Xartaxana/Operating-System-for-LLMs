# Delegated Task 7 — Agent Attribution in cc_usage + Haiku Pricing

Closed 2026-07-08. Review: critic (Opus) ПРИНЯТЬ + Lead ACCEPTED.
Code commit: 2f026f0.

Process milestones: first task whose delegation was journaled at
dispatch time in THIS repo's routing-log.jsonl (with the mandatory
model field), and first critic-tier dispatch on either deployment —
the acceptance ran through the strengthened rule 3 (critic verdict as
mandatory acceptance input for schema/cost-accounting diffs) on the
same day the rule was written.

## Spec (Lead, 2026-07-08)

Builder-tier. Two telemetry gaps blocking the routing evidence loop:

GAP 1 — no agent attribution: subagent transcript lines carry agentId
(verified on all sidechain lines, Task 6), but it is not stored, so
cost per accepted unit per agent/category (F-3 metric, R4 input) is
not computable. Investigate what agent-identity fields actually exist
(a type/slug was suspected under the name "agentType").

GAP 2 — haiku unpriced: claude-haiku-4-5-20251001 has no
PRICES_PER_TOKEN_USD entry; scout-tier (haiku) traffic imports with
accounted_cost_usd=NULL (F-7 pattern, honest warning but a hole).

Requirements: (1) nullable agent columns + idempotent migration for
EXISTING DBs (ALTER TABLE guarded by PRAGMA table_info; fresh DBs via
SCHEMA); (2) populate at import, NULL for top-level lines;
(3) backfill pre-migration rows by dedupe_key + recompute NULL costs
from stored token counts, both idempotent; (4) haiku 4.5 at $1/$5 per
1M tokens, dated + bare key; (5) tests incl. old-schema migration
without data loss; (6) real-data evidence: sidechain rows attributed,
haiku NULL costs gone, second run changes 0 rows, top agents for
D--AO3-tests.

## Execution Report (Sonnet builder subagent, 2026-07-08 — verbatim)

**(a) What changed, file by file** (both under `tools/`, no other
files touched by me):

- `tools/usage_report.py` (+159/-4 lines):
  - `SCHEMA`: added nullable `agent_id TEXT`, `agent_type TEXT`
    columns.
  - `_TASK7_NEW_COLUMNS` constant + rewritten `_connect()`: checks
    `PRAGMA table_info(cc_usage)` and issues `ALTER TABLE cc_usage
    ADD COLUMN ...` for any missing column — idempotent, works on
    pre-existing DBs, never touches a DB that already has the columns.
  - `iter_assistant_turns()`: now yields `agent_id` (from
    `obj.get("agentId")`) and `agent_type` (from
    `obj.get("attributionAgent")`), both `None` on top-level lines.
  - `import_transcripts()`: INSERT now carries `agent_id`/`agent_type`.
    When `INSERT OR IGNORE` finds the row already present
    (`rowcount == 0`) and the transcript line has agent data, an
    `UPDATE ... SET agent_id = COALESCE(...), agent_type =
    COALESCE(...) WHERE dedupe_key = ? AND (agent_id IS NULL OR
    agent_type IS NULL)` backfills it. At the end of the loop,
    `backfill_costs(conn)` (new function) recomputes
    `accounted_cost_usd` for any row still `NULL`, using current
    prices and the row's already-stored token counts. No `--backfill`
    flag was added — both backfills run automatically as part of every
    normal import, since both are naturally idempotent (spec's "your
    choice, document it" — documented in `import_transcripts`'s
    docstring).
  - `PRICES_PER_TOKEN_USD`: added `"claude-haiku-4-5-20251001"` and
    `"claude-haiku-4-5"`, both `(1.00/1_000_000, 5.00/1_000_000)`.
  - Module docstring: added a "Delegated Task 7" section documenting
    the GAP 1 investigation (below).

- `tools/test_usage_report.py` (+164/-0 lines): 6 new tests —
  old-schema migration without data loss, agent_id/agent_type captured
  for subagent-layout line, top-level line gets NULL agent fields,
  haiku cost with no warning (dated + bare id), and a backfill test
  that seeds a pre-Task-7 row (NULL agent fields, NULL cost for haiku)
  and asserts one import fills it, and a second import +
  `backfill_costs()` call update 0 rows.

**(b) GAP 1 investigation — real findings** (62 subagent files, 6631
lines, 3917 assistant lines, on this machine):

- `agentId`: top-level field on **every line** of every subagent file
  (6631/6631), not just assistant lines.
- A literal `agentType` key does **not exist** anywhere in the
  `.jsonl` lines (0/6631) — this contradicts Task 6's report phrasing
  ("agentType: test-maintainer"), which was describing a *value*, not
  a literal key.
- The literal key holding that value is **`attributionAgent`** —
  top-level on 3911/3917 assistant lines (the 6 missing are all
  `model == "<synthetic>"` stop-sequence lines, already skipped by
  `SKIP_MODELS`). Every `agentId` maps to exactly one
  `attributionAgent` value (0 files with a varying value).
- Separately, each subagent file has a **sidecar
  `agent-<id>.meta.json`** (not matched by any glob) containing a
  literal `{"agentType": "...", "description": ..., "toolUseId": ...,
  "spawnDepth": ...}`. Spot-checked:
  `agent-aade8b2de22556abd.meta.json` → `"agentType":"fix-verifier"`,
  and every assistant line in that agent's `.jsonl` carries
  `"attributionAgent":"fix-verifier"` — identical. Since
  `attributionAgent` is per-line and needs no extra file read, it —
  not the sidecar — is what feeds `agent_type`.
- Real `attributionAgent` values seen: `test-automator`,
  `general-purpose`, `qa-orchestrator`, `builder`, `test-maintainer`,
  `test-designer`, `fix-verifier`, `test-strategist`, `Explore`,
  `failure-analyst`, `bug-reporter`.

**(c) Test output before/after**: spec stated 25 green before; after
my changes `python -m pytest tools/ -q` → **31 passed**;
`python -m pytest tools/ gateway/ -q` → **80 passed**, both clean.

**(d) Real-data acceptance evidence** (ran the real importer against
`gateway/requests.db` multiple times):
- (a) Sidechain rows with `agent_id NOT NULL`: **1752/1752** (all of
  them) at first check, growing to 1759/1759 by the final check — see
  caveat below.
- (b) Remaining NULL-cost rows by model: **0 total**, including haiku
  (`claude-haiku-4-5-20251001`: 7 rows, 0 NULL after backfill).
- (c) Idempotency: verified deterministically via tests
  (`test_import_is_idempotent`,
  `test_import_transcripts_subagent_layout_is_idempotent`,
  `test_backfill_fills_agent_fields_and_null_costs_idempotently` all
  assert 0 on second run). On the **live** machine, however, repeated
  CLI runs kept importing a handful of genuinely new rows each time
  (53, then 5, then 2) — this is because this very delegated task runs
  as a subagent, whose own transcript (matched by the subagent glob)
  keeps growing while I execute shell commands, not a dedup bug.
  Confirmed no duplication: `COUNT(*) == COUNT(DISTINCT dedupe_key)`
  (11149 == 11149) throughout.
- (d) Distinct `agent_id`/`agent_type` for project `D--AO3-tests`,
  top 10 by row count: `a9ecb924d0178a1c8`/test-automator (208),
  `a22ec96553294deec`/test-automator (137),
  `afe13710cc574dbaa`/test-automator (123),
  `a291ad2f4830a9c04`/test-automator (119),
  `ab7e99c4dbea39a38`/builder (114),
  `acbe45540f4f4d151`/test-maintainer (75),
  `a6d823d469efb1e24`/test-automator (52),
  `a25cf94b21ceae2c5`/qa-orchestrator (47),
  `acf509eb44bdf01a0`/general-purpose (42),
  `a64c6b5ecbb15ac8f`/test-automator (39). By `agent_type` aggregate:
  test-automator 678 rows/6 agents, qa-orchestrator 148/7, builder
  114/1, general-purpose 108/4, test-maintainer 75/1, test-designer
  39/3, fix-verifier 30/2, test-strategist 29/2, failure-analyst 8/1,
  bug-reporter 3/1.

**(e) Deviations / open questions**:
- No `--backfill` CLI flag was added; both backfills run
  unconditionally inside `import_transcripts()`. This matches the
  spec's "your choice" but a reviewer may want an explicit flag for
  visibility/control — flagging for awareness.
- `git status` also shows `CLAUDE.md` and `logs/routing-log.jsonl` as
  modified — I did **not** touch either file; `git diff` confirms
  these are the Lead's own concurrent routing-policy edit and a
  `delegated` journal entry for this task, made by the orchestrating
  session in parallel while I worked. `gateway/requests.db` updates
  are expected/allowed per spec and are gitignored (not tracked).
- Did not modify `format_report()`/`build_report()` to surface
  per-agent breakdowns in the printed report — out of spec's explicit
  scope (schema/import/backfill/pricing/tests only); the raw data is
  now in the DB for the routing calibration to consume directly.

## Critic Review (Opus subagent, 2026-07-08 — verbatim, first critic dispatch)

All 80 tests pass. I've traced the migration, backfill UPDATE,
`backfill_costs()`, and pricing paths line by line against the three
DB states. My verdict follows.

### 1. Findings (most severe first)

**No correctness findings.** I traced every path the spec flagged and
each is correct:

- **Migration `_connect()` (usage_report.py:315-333)** — idempotent
  and safe on all three states:
  - *Fresh DB:* `CREATE TABLE IF NOT EXISTS` builds the table already
    containing `agent_id`/`agent_type`; PRAGMA reports them present;
    the ALTER loop is a no-op.
  - *Old-schema DB with data:* CREATE is a no-op (table exists);
    PRAGMA returns the old column set lacking the two; each missing
    column is added via `ALTER TABLE ... ADD COLUMN ... TEXT`
    (nullable, no default → existing rows get NULL, no rewrite, no
    data loss). SQLite `ADD COLUMN` is a metadata-only op — no
    table-rewrite lock hazard.
  - *Current-schema DB:* columns already present → no ALTER.
  - The `{row[1] for row in PRAGMA table_info}` set-membership guard
    is exactly right (`row[1]` is the column name), so re-running
    never double-adds.

- **Agent-field backfill UPDATE (usage_report.py:432-445)** — cannot
  corrupt or miss:
  - Only fires on `cur.rowcount == 0` (INSERT OR IGNORE collided with
    an existing `dedupe_key`), and `dedupe_key` is UNIQUE, so the
    `WHERE dedupe_key = ?` touches exactly the one colliding row —
    never a wrong row.
  - `COALESCE(agent_id, ?)` preserves any already-present value; the
    `WHERE ... (agent_id IS NULL OR agent_type IS NULL)` clause means
    a fully-populated row is untouched. The partial case (agent_id
    set, agent_type NULL) correctly fills only the NULL side. Second
    run → WHERE is false → 0 rows. Idempotent.
  - The guard `turn["agent_id"] is not None or turn["agent_type"] is
    not None` correctly skips the UPDATE entirely for top-level
    (both-NULL) re-imports.

- **`backfill_costs()` (usage_report.py:336-365)** — recompute matches
  `accounted_cost()` exactly because it *calls* `accounted_cost()`
  with the row's stored token counts (same cache multipliers). Only
  rows with `accounted_cost_usd IS NULL` are candidates; unknown
  models return `None` → row stays NULL, never zeroed (Rule #1
  upheld). A legitimately-zero known-model row keeps cost `0.0` at
  insert time, so it's never in the NULL candidate set — no wrongful
  re-zero. Idempotent: priced rows leave the NULL set; unknown rows
  always recompute to `None` and are skipped → second call updates 0.

- **Pricing keys (usage_report.py:188-189)** — `accounted_cost` uses
  exact `dict.get(model)`. The dated key `claude-haiku-4-5-20251001`
  matches the string that actually occurs (per docstring, 7 rows);
  the bare key is defensive. Both map to the same `(1/1M, 5/1M)`
  tuple; consistent with the other bare-id entries.

- **`build_report` / SELECT *** — reads columns by name via
  `sqlite3.Row`, so the two new columns are harmless to existing
  report logic.

**Minor (non-blocking) observations, not defects:**
- `backfill_costs()` discards the warning from `accounted_cost()`.
  For a NULL-cost row whose model is *still* unknown and whose
  transcript is no longer on disk, no warning is emitted during
  backfill (it still stays NULL and is counted in `build_report`'s
  `unknown_cost_rows`). Live transcript rows are still warned on the
  normal insert path (line 411). The "never silent $0" invariant
  holds; only the warning is skipped in this narrow backfill-only
  case.
- Test-coverage gaps (behavior is correct by trace, just not directly
  asserted): (a) no single test chains old-schema-DB → migrate →
  re-import fills agent fields (the migration ALTER and the
  agent-field UPDATE are each tested in isolation — the migration
  test uses a top-level fixture, the backfill test pre-inserts via
  the *new* SCHEMA); (b) the partial-fill case (agent_id present,
  agent_type NULL on the existing row) is not explicitly tested,
  though the COALESCE logic handles it.

### 2. Test-run result
`python -m pytest tools/ gateway/ -q` → **80 passed in 17.49s**. The
Task-7 tests genuinely exercise the target paths: the migration test
builds a literal old-schema table with a real row and confirms columns
are added while data (model, cost 0.001, NULLs) survives; the backfill
test confirms agent fields fill on a dedupe collision, the haiku row
gets a non-NULL positive cost, and a second run + direct
`backfill_costs()` both report 0 updates.

### 3. Verdict

**ПРИНЯТЬ.**

The change implements all five requirements correctly: idempotent,
data-safe ALTER migration guarded by `PRAGMA table_info`; correct
agent-field population and dedupe-key-scoped backfill that cannot
overwrite good data; a cost backfill that exactly mirrors
`accounted_cost()` and preserves the never-silent-$0 rule; consistent
haiku pricing keys; and a green suite that tests the real claims. The
two minor items above are optional hardening (add a partial-fill test
and, if desired, surface a warning for backfill-only unknown-model
rows), not conditions of acceptance.

## Lead Review (Claude Fable 5, 2026-07-08)

Verdict: ACCEPTED, with the critic's verdict as input (rule 3) plus
independent verification:

- Tests re-run by the Lead before the critic finished: 80/80.
- DB re-queried by the Lead: all 16 columns present; 1759/1759
  sidechain rows carry agent_id; 0 NULL-cost rows; 7 haiku rows priced
  ($0.13 total); 0 duplicate dedupe_keys. Per-agent AO3 cost breakdown
  now computable (test-automator $32.96 / builder $9.17 /
  qa-orchestrator $5.93 / ...), which is the R4/F-3 input this task
  existed to unlock.
- Critic's two non-blocking hardening notes (partial-fill test;
  warning in the backfill-only unknown-model path) are recorded here
  as optional follow-ups, not scheduled work.
- Spec errata (builder's investigation): there is no per-line
  agentType key; the real field is attributionAgent, while agentType
  exists only in agent-<id>.meta.json sidecar files. Both Task 6's
  report phrasing and this task's spec inherited the imprecision;
  corrected in the module docstring.
- Worker costs for the run: builder 124,907 subagent tokens / 55 tool
  calls / ~9.5 min; critic 58,855 tokens / 4 tool calls / ~2.7 min.
  Evidence stream: builder row n=2 accepted, 0 escalations; critic
  row n=1 accepted (first dispatch), verdict consistent with
  independent Lead verification. Statuses stay estimated (Update
  Rule 1 — volume comes from the weekly loop).
