# Delegated Task 5: tools/usage_report.py — Claude Code Transcript Telemetry

Archived verbatim from CURRENT_CONTEXT.md on 2026-07-07 (D-0038).
ACCEPTED 2026-07-07 by Lead review (commit 7e645e7). Spec lives in
docs/UNIFIED_PLAN_2026-07-07.md section 4. The strategic baseline
findings (including the Architect's censored-data correction) are
kept LIVE in CURRENT_CONTEXT.md in condensed form; the full original
text is below.

---

## Delegated Task 5 — Execution Report (2026-07-07, Sonnet session)

Status: code written, self-tested, NOT Lead-reviewed (executor does
not self-certify). Execution was interrupted by a session limit
mid-task (after code, tests and the acceptance baseline were done but
before documentation/commit) and resumed on coordinator instruction;
state was re-verified against the repo and the DB before finishing.

Implemented (spec: docs/UNIFIED_PLAN_2026-07-07.md section 4):

1. tools/usage_report.py: parses ~/.claude/projects/*/*.jsonl
   (83 files on this machine; the glob naturally skips the memory/
   and tool-results/ subdirectories), reads ONLY message.model +
   message.usage + session/turn metadata (privacy rule: no message
   bodies, no prompt text in DB or reports), imports one row per
   assistant API turn into a NEW cc_usage table in the gateway
   SQLite DB (GATEWAY_DB_PATH respected; default gateway/requests.db;
   the existing requests table untouched — covered by a test that
   seeds a sentinel requests table and verifies it survives import).
   Import is idempotent via INSERT OR IGNORE on a UNIQUE dedupe_key.
   Report: --days N (default 7), --all, --json; totals, per-day /
   per-model / per-project breakdowns, top-5 sessions by accounted
   cost, cache economics (cache_read share of input; accounted
   savings vs uncached), sidechain share; text style follows
   gateway/metrics.py.
2. Accounted cost (D-0032/D-0034): one PRICES_PER_TOKEN_USD dict with
   a source comment (Anthropic list prices as cached in the bundled
   claude-api skill, cache date 2026-06-24: fable-5 $10/$50,
   opus-4-8 $5/$25, sonnet-5 and sonnet-4-6 $3/$15 per MTok;
   sonnet-5 priced at standard list rate, NOT the time-limited intro
   price, per Rule #1 "list prices"). Cache write = 1.25x base input
   (5-minute-TTL rate), cache read = 0.1x base input. Unknown models:
   cost=None + WARNING in the report, never a silent $0.
3. tools/test_usage_report.py + tools/fixtures/sample_transcript.jsonl
   (hand-built, synthetic numbers, no real prompt content): 18 tests
   covering parsing, <synthetic> skip, non-assistant line skip,
   requestId dedup / idempotent double-import, requests-table
   isolation, price math incl. distinct cache rates, unknown-model
   warning path, report breakdowns, sidechain flag, days filter.
   No network, no LLM calls.

Empirical findings from transcript verification (the mandatory
verify-before-trusting-the-spec step; finding #1 materially changed
the design):

1. DEDUP KEY: uuid is the WRONG key. One assistant API turn is split
   across MULTIPLE JSONL lines when the response has several content
   blocks (e.g. 4 tool_use blocks -> 4 lines): each line has a unique
   uuid but the SAME requestId and an IDENTICAL message.usage block.
   419 such multi-line requestId groups in this project's transcripts
   alone; naive uuid-keyed or per-line summing would multiply token
   counts by up to 4x. Dedupe key = (session_id, requestId), first
   occurrence wins. uuid kept only as a defensive fallback when
   requestId is absent (never observed).
2. model == "<synthetic>" rows are harness-internal rate-limit
   notices ("You've hit your session limit...", error rate_limit,
   isApiErrorMessage true) with all-zero usage — 64 across all
   projects, skipped per spec.
3. isSidechain: NO true rows exist anywhere on this machine (0 of
   ~16k assistant lines) — subagent traffic has simply not been
   generated yet. Column is populated anyway per the Lead
   clarification (sidechain = real but distinguishable).
4. Non-assistant line types observed (all skipped, none carry usage):
   user, ai-title, last-prompt, queue-operation, system, mode,
   permission-mode, file-history-snapshot, pr-link, attachment.
5. Filename stem == the per-line sessionId field in every real
   transcript (0 mismatches); parser prefers the JSON field and falls
   back to the filename.
6. Live-transcript caveat: transcripts of RUNNING sessions (including
   the executor's own) grow between runs, so consecutive imports pick
   up a few genuinely new rows — that is new data, not an idempotency
   failure (verified: re-import of unchanged files inserts 0).

Tests: tools suite 18/18 green; gateway suite still 49/49 green
(run after the tools work, from gateway/). Observed requests.db state
during the run matches the cleanup note above: 199 requests rows
(judge 149 + synthetic 50, zero 'real'), cc_usage added alongside.

Acceptance baseline over real history (all-time; history starts
2026-06-13 so the 30-day window is equivalent), run 2026-07-07:

- 8747 turns imported from 79 session files across 4 projects.
- Totals: 480,982 input + 5,901,656 output tokens, plus 54,152,697
  cache-write and 2,212,874,425 cache-read tokens;
  accounted cost $1177.48 (zero unknown-model rows, zero WARNINGs).
- Per model: sonnet-4-6 6433 turns / $735.29; opus-4-8 778 / $205.67;
  fable-5 918 / $197.59; sonnet-5 618 / $38.94.
- Cache economics: cache_read share of input 97.6%; accounted savings
  vs uncached input price $7117.03 — i.e. the operator's real spend
  profile is dominated by cache reads, directly relevant to the
  D-0036 "is compression even our lever" question (C3 net of cache).
- Sidechain share: 0 (no subagent traffic exists yet).
- Spot-check (hand-summed via a throwaway script vs imported rows),
  exact match on both files:
  329ed5da...9777: 169 turns, in 15,000 / out 94,084 /
  cache-write 220,219 / cache-read 19,448,832 — DB identical.
  f98ad354...9b40: 33 turns, in 9,351 / out 20,459 /
  cache-write 72,635 / cache-read 1,931,539 — DB identical.

Spec deviations (for Lead review):

1. Fixture location: spec item 5 says "tests/fixtures"; the task
   instructions and the repo layout (tests live next to code, no
   tests/ dir exists) say tools/fixtures/ — followed the latter.
2. Added is_sidechain INTEGER 0/1 and dedupe_key TEXT UNIQUE columns
   beyond the spec's field list — the former per the Lead
   clarification, the latter as the idempotency mechanism.
3. Prices: claude-fable-5 / claude-sonnet-5 / claude-opus-4-8 /
   claude-sonnet-4-6 postdate the executor's training data; treated
   the bundled claude-api skill's cached pricing table (2026-06-24)
   as the verified source instead of guessing or emitting a false
   "unknown model" warning for models that do have list prices.
   claude-sonnet-5 uses the standard $3/$15 list rate, not the intro
   promo — flagging in case the Lead prefers promo-rate accounting.
4. --all flag added (spec's acceptance mentions all-time "if trivial
   to add" — it was).

## Lead Review of Delegated Task 5 (2026-07-07, Fable session)

Verdict: ACCEPTED (commit 7e645e7). Code re-read in full; both test
suites re-run green on this machine (tools 18/18, gateway 49/49).
Acceptance reproduced independently: the all-time report ran clean
(8752 turns / $1178.78 at review time — slightly above the executor's
8747 / $1177.48 because live transcripts grew in between, exactly the
executor's finding #6, not an idempotency failure). Two INDEPENDENT
spot-checks on files the executor did NOT check, hand-summed with a
throwaway dedup script: 1b4caf23 (D--Dog, 3 turns) and 4000c434
(D--Dog, 27.2 MB, 485 turns, cache-read 229,876,370) — both exact
matches against cc_usage. requests table intact at 199 rows.

All four spec deviations accepted: (1) tools/fixtures is right for
this repo layout; (2) dedupe_key/is_sidechain columns are justified
(idempotency mechanism; sidechain = future subagent visibility);
(3) pricing from the bundled claude-api skill table was the correct
verified source, and standard-list-rate (not promo) accounting is
CONFIRMED as policy — D-0032 says list prices, promotions are cash
discounts; (4) --all was invited by the spec.

Non-blocking notes for a future touch (do NOT fix without a task):

1. turn_index counts pre-dedup assistant lines, so sessions have
   index gaps where multi-line turns were deduped. Ordering is
   preserved; cosmetic.
2. accounted_cost_usd is frozen at import time; a price correction
   requires rebuilding cc_usage (DROP TABLE + re-import — cheap,
   the table is derived data). Document-only caveat.
3. --json output omits the warnings list (unknown_cost_rows in
   totals carries the signal); cosmetic asymmetry with text output.

STRATEGIC BASELINE FINDINGS (Architect attention):

1. G1 LOOKS GREEN RETROACTIVELY: per-day report shows real traffic
   on every calendar day 2026-06-18..2026-07-07 — 20 consecutive
   days (>=14 required, D-0034 transcripts count). Some days are
   thin (3-6 turns). Formal gate check still goes through Task 3's
   readiness digest + a written gate report + Architect signature
   (D-0033); G2 (judge 13/13) also holds.
2. CACHE READS DOMINATE: 97.6% of input-side tokens are cache reads;
   accounted savings vs uncached input $7,117 on a $1,178 total.
   Provider caching is already absorbing nearly all context
   repetition on the subscription contour — first hard evidence for
   the D-0036 ordering (measure net-of-cache before building any
   compression).
3. SPEND MIX — CORRECTED BY THE ARCHITECT (2026-07-07): the Lead's
   first reading ("sonnet-4-6 carries 62% of spend, so the premise
   'the smartest model burns most' is refuted") was WRONG. The
   baseline is CENSORED data: the operator was rationing frontier
   usage precisely because limits would run out — the mix shows the
   rationing, not free demand. The premise reads correctly as "the
   smartest model burns tokens FASTEST", and the same baseline
   confirms it: accounted burn per turn is opus-4-8 $0.264 and
   fable-5 $0.216 vs sonnet-4-6 $0.114 and sonnet-5 $0.063 —
   frontier models burn 2-4x faster per unit of work.
   Two consequences for Phase 1.5:
   (a) Success metric: NOT "frontier share of spend falls vs
   baseline" alone — if routing frees up limits, Fable's share on
   architecture work may legitimately RISE while per-unit economics
   improve. Track cost per accepted unit of work by tier + the
   escalation rate; watch the frontier share only alongside them.
   (b) The baseline cannot say what the operator WOULD have used
   frontier models for without rationing; the escalation journal
   (junior failed -> escalate) is the instrument that measures the
   true boundary, and it only starts producing data once routing is
   live. (Also: history mixes pre-Fable weeks; the weekly loop
   watches the recent-window trend, not the all-time total.)
