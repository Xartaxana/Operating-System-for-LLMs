# Current Context

## Current Milestone

Phase 1 — Supervised Lead (MVP), step 5: Shadow Evaluation.

## Current Status

Phase 0 closed 2026-07-03. Phase 1 steps 1–4 built and verified:

- Gateway (step 1): LiteLLM proxy + SQLite request logging.
- Guard (step 2): daily per-model budgets, warn 80% / refuse 100%.
- Ledger (step 3): metrics.py daily digest (text/JSON).
- Analyst (step 4): analyst.py feeds the Ledger digest to a local
  Qwen3-4B (Ollama) through the gateway under its own alias, so
  supervision cost is accounted separately. Verified live: answered
  a Russian operator question from real telemetry. Answer quality is
  Intern-class (numbers occasionally garbled) — acceptable for MVP,
  prompt to be tuned on real telemetry.

Free-telemetry mode is in place (no paid keys needed): local models
`intern` and `analyst` (Ollama Qwen3-4B) run through the gateway with
synthetic Haiku-class per-token prices, so Guard/Ledger money paths
work at $0. `lead` (Anthropic API, paid) stays optional.

Environment notes (this machine): Ollama 0.31.1 installed via winget.
NVIDIA driver updated 560.94 → 582.28 (last Pascal security branch),
which fixed the Ollama CUDA PTX error: Qwen3-4B now runs 100% on the
GTX 1060 GPU, warm requests ~5 s vs ~15 s on CPU. Proxy must be
started from gateway/ (callback imports are cwd-relative).

Open operational item (Architect): route real traffic through the
gateway to accumulate telemetry (free via intern/analyst;
lead needs ANTHROPIC_API_KEY, paid).

Test-traffic alias `lead-sonnet` (anthropic/claude-sonnet-5) added to
gateway/config.yaml for future Shadow Evaluation baselines, but unused
for now: no ANTHROPIC_API_KEY in this environment. Working set for
Shadow Evaluation instead generated via `intern` (Ollama, free): 6
requests across coding/summarization/extraction/classification/
formatting categories, logged in gateway/requests.db (38% context
repetition observed on this tiny sample — not meaningful yet, needs
volume).

Planned (not yet done): add Gemini and Groq free-tier aliases to
config.yaml for traffic diversity. Rationale: local Ollama traffic
alone can't validate delegation decisions against a real frontier
Lead — Gemini/Groq free tiers give real remote latency and real
provider pricing at $0, useful once comparing delegation candidates
against genuine frontier-Lead output (vs. `lead-sonnet` once a paid
key is available).

## Current Objective

Phase 1 step 5: Shadow Evaluation. gateway/shadow_eval.py is built and
tested (11 passing tests, no live model needed — mock_response like
test_analyst.py): samples successful requests for --source-model,
replays them on --target-model, compares via difflib similarity
(transparent heuristic, LLM judge deferred), aggregates by the same
task category metrics.py uses, and (--update-table) writes
validated/rejected verdicts into DELEGATION_TABLE.md + an evidence
log entry. Guards: refuses source==target (self-comparison is not
delegation evidence); a category stays "estimated" (inconclusive)
below --min-samples (default 2).

First real run completed 2026-07-03. Gemini free tier connected:
alias `lead-gemini` (gemini/gemini-2.5-flash; 2.0-flash has ZERO
free-tier quota on this key — 429, don't use it). Key lives in
gitignored gateway/.env; litellm did NOT auto-load it, export the
variable before starting the proxy. 10-request working set (2 per
category) replayed on `intern`; DELEGATION_TABLE.md now has its first
evidence-backed verdicts + a "Shadow Evaluation Log" section:
extraction 91% / formatting 60% / summarization 52% -> validated;
coding 10% / classification 4% -> rejected.

---

# Completed 2026-07-03: LLM Judge (built, calibrated, protocolized)

LLM judge DONE (2026-07-03). shadow_eval.py gained --judge-model
(judge through the gateway; verdicts override difflib in
decide_status via pass_rate >= --pass-threshold, default 0.75),
--calibrate (agreement report against judge_calibration.json), and
per-pair verdict logging. 31 tests pass.

Calibration history: middle-groq (Llama-3.3-70B via Groq free tier)
agreed 10/11 and was adopted 2026-07-03, then REPLACED the same day —
see below. lead-gemini as judge is impractical: free tier is 5
req/min (verified 429) and it would judge its own source answers
(self-preference bias). analyst (4B) not evaluated — no need while
Groq is free.

JUDGE UPGRADE (2026-07-03, later session): the fibonacci miss was NOT
strictness — diagnosis (asking the judge to explain) showed
Llama-3.3-70B hallucinates a bug while "tracing" the correct
`a, b = b, a + b` loop (claims the code returns b; it returns a).
Prompt hardening (judge only the explicit task; step-by-step check
before claiming a bug) did not flip it — a capability ceiling, not a
prompt problem. The hardened prompt was kept, and the judge was
upgraded: alias `judge-groq` = groq/openai/gpt-oss-120b (reasoning
model, same free Groq key), screened directly against the calibration
set (gpt-oss-120b 11/11; qwen3-32b 7/11 with rate-limit errors and a
real miss on pair #7), then officially calibrated through the gateway:
11/11. ADOPTED as default judge. judge-groq is a role alias (never a
traffic source), so judge cost stays separable in the Ledger and the
contamination filter has a second line of defense.

Judged runs done (2026-07-03), with two process lessons the hard way:

1. CONTAMINATION: the first judged run sampled 6/11 nested judge
   prompts — the failed lead-gemini calibration had logged its judge
   calls as regular lead-gemini traffic. Caught only because the
   Architect asked whether the chief judge (Claude) had reviewed the
   run. Fixed: sample_requests() excludes judge calls (prompt LIKE
   filter + test); contaminated log lines marked [RETRACTED].
2. JUDGE BIAS — RESOLVED (2026-07-03): root cause was middle-groq
   mis-tracing correct code, not strictness (see JUDGE UPGRADE above).
   Judge replaced with judge-groq (gpt-oss-120b), calibration 11/11.
   Lesson: when a judge misses, ask it to explain before tuning the
   prompt — the stated theory ("penalizes missing validation") was
   wrong, and two prompt fixes aimed at it changed nothing.

Process rule going forward: judge verdicts that CHANGE a table status
get a chief-judge (or Architect) review of the actual pairs before
the change is accepted; --update-table output is not self-certifying.
Extended 2026-07-03 into PROCESS/JUDGE_CALIBRATION_PROTOCOL.md
(D-0031): reviews grow judge_calibration.json, 1-2 random verdicts
audited per run, recalibration every ~5 new pairs, judge model
upgraded only on measured agreement drop below 90%.

Protocol applied same day: the two chief-judge-reviewed pairs from
the coding->middle-groq run appended to judge_calibration.json (now
13 pairs). First recalibration exposed verdict nondeterminism at
default temperature (borderline pair #7 flipped between runs:
11/11 -> 12/13); judge_pair now defaults to temperature=0.
Current baseline: judge-groq 13/13, reproduced twice.

Local-judge fallback measured (2026-07-04): Qwen3-4B (alias analyst,
GTX 1060) scored 11/13 (84.6%) on the calibration set — below the
90% protocol bar. Its two misses are exactly the discriminating
pairs: #2 fibonacci (code tracing — same failure mode as
Llama-3.3-70B) and #7 borderline sentiment. Judge capability tracks
the model hierarchy: 4B fails both hard pairs, 70B fails code
tracing, 120B reasoning passes all 13. Conclusion: no local judge on
this hardware; revisit only if the Groq free tier disappears
(fallback order: judge-groq > paid API judge > local 4B with
category restrictions). Caveat: Ollama default context window may
truncate the longest pairs — untested, could only improve the 4B.

DONE (2026-07-03): "Routine code generation -> Middle" tested with
middle-groq as TARGET, judge-groq as judge: n=2, pass_rate=1.00,
chief-judge review confirmed both pairs -> row validated with
tier-matching evidence (earlier evidence used intern as a stand-in).
shadow_eval.py gained --categories (whitelist) so a run aimed at one
row cannot update rows whose Delegate-to tier differs from the
target. 33 tests pass.

Next: (a) grow real traffic volume (n=2 per category is thin);
(b) once ANTHROPIC_API_KEY exists, repeat against the true paid Lead.

---

# Current Task (Authoritative): Unified Plan 2026-07-07 execution

Adopted 2026-07-07 (Architect + Lead session): the external plan
"routing in Claude Code" (docs/EXTERNAL_PLAN_CLAUDE_CODE_ROUTING_2026-07-07.md)
is merged with the repository roadmap into
docs/UNIFIED_PLAN_2026-07-07.md (D-0034..D-0036). Key facts fixed by
the Architect this session:

- The operator's REAL Lead is the Claude Code subscription
  (Fable/Opus), not an API key. Claude Code transcripts
  (~/.claude/projects/**/*.jsonl) become a first-class real-traffic
  telemetry source (D-0034); they natively carry model, usage,
  cache_read/cache_creation token fields and per-session files —
  verified live 2026-07-07.
- Priority: telemetry feeds both deliverables (white paper and
  day-to-day savings); one shared measurement foundation first.

Next engineering steps, in order (details in the unified plan):
Delegated Task 4 (test isolation), Delegated Task 5
(tools/usage_report.py baseline), then Claude Code routing
(subagents + policy + escalation journal).

---

# Previous Lead-tier task (2026-07-04): White Paper iteration

Lead-tier task, prioritized by the Architect 2026-07-04 ("actions
that need the strongest model first"). Draft v0.1 of WHITE_PAPER.md
written 2026-07-04 (deliverable #1 of PROJECT_CHARTER.md): problem,
supervision decomposition, evidence-based delegation, the judge as a
supervised worker (capability tracks hierarchy: 4B 11/13, 70B 12/13,
120B 13/13), accounting prices, repository-as-memory/self-hosting,
positioning, honest empirical status (§7) and limitations. Next
iterations: keep §7 synchronized with the evidence log; add the
context-repetition section once local telemetry confirms or refutes
the 50-62% prior; Architect review of the draft.

DONE (2026-07-04): Phase 2 entry criteria defined (ROADMAP.md,
D-0033) — common gate (14 days real traffic, calibrated judge),
router gate (R1-R5: evidence volume, >=25% delegable share of
accounted Lead spend, mix stability, 3x economics, paid-Lead or
sign-off), compression gate (C1-C3: >=40% repetition confirmed
locally, >=20 multi-turn sessions, >=25% of input spend re-sent).
Green gate -> written report -> Architect signs; first task is
always an evaluation, never a build. Summarized in White Paper §10.

DONE (2026-07-04): White Paper §7/§10 synchronized after the
traffic_kind and Rule #1 cost-accounting implementation commits:
WHITE_PAPER.md now states that the hardening is implemented and
self-tested, but still awaiting Lead/Architect review before being
treated as signed process evidence. Canonical source range updated
to D-0001..D-0033.

DONE (2026-07-04): External review report recorded in
docs/EXTERNAL_REVIEW_CONTEXT_MANAGEMENT_2026-07-04.md and linked from
README.md + docs/README.md so it is discoverable after a fresh boot.
Key review recommendation: treat Phase 2 as Context Management
Evaluation, not only compression; evaluate provider prompt caching,
cache-aware Ledger accounting, session/turn identity, structured
compaction, retrieval/memory and memory governance under Rule #1.

Remaining Lead-tier queue: White Paper §7 upkeep; Architect review
of the draft; sync the White Paper with D-0034..D-0036 (Claude Code
workstream, 4-state delegation statuses, Phase 2 as Context
Management Evaluation) once the unified plan's first steps land.

---

# Delegated Task Queue (for CHEAPER model sessions)

Execution order (each task reviewed by Lead/Architect before the
next starts; the executor does not self-certify):

1. Rule #1 cost accounting in shadow_eval.py (spec below).
   ACCEPTED 2026-07-07 by Lead review (see "Lead Review of Delegated
   Tasks 1-2" below); Architect confirmed the review this session.
2. Traffic-kind tagging in the request log (spec below; born from
   gate G1, D-0033). ACCEPTED 2026-07-07 by the same Lead review.
3. metrics.py "Phase 2 readiness" digest section: print current
   values vs. the ROADMAP gate thresholds (G/R/C criteria) so gate
   progress is visible in every daily digest. Spec written 2026-07-07
   (below). Execute AFTER task 4 (task 4 protects the telemetry the
   digest reads).
4. Test isolation + review follow-ups (spec below, born from the
   2026-07-07 Lead review findings). ACCEPTED 2026-07-07 by Lead
   review (commit 80b29b2; see "Lead Review of Delegated Task 4"
   below). Residual mock rows: Architect approved, deleted same day
   (24 rows, DB 223 -> 199).
5. tools/usage_report.py — Claude Code transcript telemetry
   (Phase 1.5 step 1, D-0034). Spec in
   docs/UNIFIED_PLAN_2026-07-07.md. NEXT IN LINE (task 4 accepted;
   task 3 also unblocked and may run after it).

## Lead Review of Delegated Tasks 1-2 (2026-07-07, Fable session)

Verdict: BOTH ACCEPTED. Diffs 55c570a (task 2) and af2281d (task 1)
re-read line by line; 48/48 tests re-run green on this machine;
requests.db verified: zero pre-migration rows tagged 'real'
(judge 161 / replay 8 / synthetic 70) — acceptance criteria met.
The two execution reports below remain the authoritative detail.

Findings (none blocking; all folded into Delegated Task 4):

1. TEST POLLUTION (real, contained): test_sqlite_logger.py sets
   litellm.callbacks = [logger_instance] globally and never restores
   it. With an unlucky test order, the mock litellm.completion calls
   in test_shadow_eval.py fire the real callback and write into
   gateway/requests.db. This HAPPENED 2026-07-04: 18 mock rows
   (models 'judge-alias' / 'nonexistent-model-xyz' / 'intern', two
   pytest clusters 19:08 and 19:10). Damage was contained by task 2
   itself — every stray row is tagged replay/judge/synthetic, so
   gate G1 math is unaffected. Alphabetical collection order
   currently hides the bug (test_shadow_eval < test_sqlite_logger).
2. Evidence-line coupling (minor, Rule #1 spirit): in
   update_delegation_table() the judged segment renders only when
   BOTH pass_rate AND mean_judge_cost_usd are present; if the judge
   ran but cost extraction returned None, the evidence line silently
   drops judge= pass_rate= even though verdicts drove the status —
   exactly the silent omission Rule #1 forbids. format_report()
   already decouples the two correctly.
3. Fallback timezone risk (minor): _extract_cost's requests.db
   fallback compares client-side naive datetime.now() with the
   proxy-logged ts; a timezone/clock mismatch would make
   ts >= call_start never match (returning None — honest, but the
   fallback would be dead code). The primary hidden_params path is
   live-verified; the fallback is verified only with mocks.
4. Schema-default divergence (cosmetic): migrated DBs carry
   DEFAULT 'synthetic' on traffic_kind, fresh DBs DEFAULT 'real'.
   Harmless — the logger always writes the field explicitly, and
   'synthetic' is the fail-closed direction for G1 — but keep the
   deviation from the spec's DEFAULT 'real' documented.

# Delegated Task 3 (spec, Lead 2026-07-07): Phase 2 readiness digest in metrics.py

Middle-class task. Add a "Phase 2 readiness" section to the metrics.py
text and JSON digest: one line per ROADMAP gate criterion (G1, G2,
R1-R5, C1-C3) showing current value vs. threshold and met / not met /
"not computable yet (needs <what>)". Rules:

1. Deterministic Python/SQL over requests.db and
   DELEGATION_TABLE.md only — no LLM calls.
2. G1 counts DISTINCT days with traffic_kind='real' rows. R1 parses
   judged evidence lines from the Shadow Evaluation Log. G2, R5 and
   anything not derivable from telemetry print as "manual check"
   with a pointer — never a guessed value.
3. Criteria whose inputs do not exist yet (e.g. C2 sessions before
   session identity lands, R2 spend shares before real traffic)
   MUST print "not computable yet" with the missing prerequisite —
   an honest gap, not a fake 0% (Rule #1 spirit).
4. Tests over a seeded tmp DB; existing tests stay green.

Acceptance: `python metrics.py --days 14` prints the section; JSON
output carries a `phase2_readiness` object with the same content.

# Delegated Task 4 (spec, Lead 2026-07-07): test isolation + review follow-ups

Middle-class task, born from the Lead review findings above.

1. Test isolation: add gateway/conftest.py with an autouse fixture
   that (a) points GATEWAY_DB_PATH at a tmp_path DB for EVERY test,
   (b) saves litellm.callbacks before each test and restores them
   after. Remove per-test monkeypatch.setenv duplication where it
   becomes redundant. Acceptance: running
   `pytest test_sqlite_logger.py test_shadow_eval.py` (exactly that
   order) leaves gateway/requests.db byte-identical.
2. Evidence-line decoupling in update_delegation_table(): show
   judge=... pass_rate=... whenever pass_rate is present; append
   judge_cost=$X.XXXX when known and judge_cost=unknown when the
   judge ran but cost is None. Test covers the None case.
3. One-time cleanup of the 18 mock rows in gateway/requests.db:
   DELETE FROM requests WHERE ts >= '2026-07-04T19:08' AND
   ts < '2026-07-04T19:11'; record the deleted row count in the
   commit message. (Local operational DB — the point is honest G1
   telemetry, not git state.)
4. All existing tests stay green.

## Delegated Task 4 — Execution Report (2026-07-07, Sonnet session)

Status: code written, self-tested, NOT Lead-reviewed (executor does
not self-certify). Execution was interrupted mid-task by a session
limit (after conftest.py creation and the item-3 cleanup) and resumed
in a fresh session on coordinator instruction; state was re-verified
from the repo and the DB before continuing.

Implemented:

1. gateway/conftest.py: autouse function-scoped fixture; (a)
   GATEWAY_DB_PATH -> per-test tmp_path DB for every test; a test's
   own monkeypatch.setenv still wins (LIFO teardown) — verified
   empirically with a throwaway 4-test file (not committed): conftest
   default lands in tmp_path, own monkeypatch overrides it, a
   deliberately leaked callback is restored before the next test.
   (b) saves/restores litellm callback lists around every test.
   Removed now-redundant GATEWAY_DB_PATH setenv from the db fixture
   (test_sqlite_logger.py) and env fixture (test_guard.py) — both set
   the byte-identical value the conftest already sets.
2. update_delegation_table() evidence line decoupled per the spec:
   judge=/pass_rate= renders whenever pass_rate is not None;
   judge_cost=$X.XXXX appended when known, judge_cost=unknown when
   the judge ran but cost is None. format_report() untouched. New
   test test_update_delegation_table_evidence_line_judge_cost_unknown.
3. Mock-row cleanup executed with the spec's exact WHERE clause:
   16 rows deleted (not ~18 — see deviations), requests.db
   239 -> 223 rows; the 19:08–19:11 window now has 0 rows and the DB
   has ZERO rows tagged 'real' anywhere (judge 153 + synthetic 70).

Empirical results:

- Tests: 48 before, 49 after (one new evidence-line test); full
  suite green. Polluting-order run
  `python -m pytest test_sqlite_logger.py test_shadow_eval.py`:
  37 passed.
- Acceptance hashes (git hash-object gateway/requests.db) around the
  polluting-order run: 5e40263484bbf0945abe875b6f8e5377245a2520
  before, 5e40263484bbf0945abe875b6f8e5377245a2520 after — identical;
  unchanged again after a 3 s delay AND after the full 49-test suite.

Spec deviations / empirical surprises (for Lead review):

1. SPEC ASSUMPTION WRONG (important): restoring litellm.callbacks
   alone does NOT fix the leak. First acceptance run with the naive
   conftest still wrote 1 row into the real requests.db (model
   'intern', traffic_kind 'real' — exactly the G1-poisoning shape).
   Verified on litellm 1.90.2: one completion call with
   litellm.callbacks=[logger] copies the logger into
   success_callback, failure_callback, input_callback,
   _async_success_callback, _async_failure_callback (function_setup
   copies at call time); the leaked success_callback then fires from
   a worker thread after env teardown. conftest.py now snapshots and
   restores all six lists. The pollution row my own run created
   (id 240) was deleted; second acceptance run clean.
2. 16 deleted, not ~18: the spec's exact WHERE window contained
   8 judge (judge-alias) + 6 replay (intern) + 2 replay
   (nonexistent-model-xyz) = 16. The expected "2 synthetic" rows
   (model 'mock', 19:02:58 and 19:06:03) sit BEFORE the 19:08 lower
   bound and were correctly not matched; they remain in the DB,
   tagged 'synthetic' (harmless to G1). Not deleted — the spec forbade
   widening the clause.
3. Residual non-window mock artifacts reported, not touched: 22 rows
   from 2026-07-03 (nonexistent-model-xyz -> 'synthetic',
   judge-alias -> 'judge') — earlier pre-migration test pollution,
   outside this task's scope; all tagged non-'real', so G1 math is
   unaffected. Left for a Lead decision.

## Lead Review of Delegated Task 4 (2026-07-07, Fable session)

Verdict: ACCEPTED (commit 80b29b2). Diff re-read line by line;
acceptance reproduced INDEPENDENTLY on this machine: polluting-order
run (test_sqlite_logger.py then test_shadow_eval.py, 37 passed) left
requests.db byte-identical (5e40263484bbf0945abe875b6f8e5377245a2520
before/after, and unchanged after the full 49-test suite); DB state
confirmed: 223 rows, 0 in the mock window, zero 'real' rows anywhere.

Review notes:

- The executor's deviation #1 (litellm copies the logger into six
  callback lists at call time; restoring litellm.callbacks alone is
  insufficient) is a REAL empirical find, verified in the committed
  conftest.py design and by my clean re-runs. This is the third
  spec-vs-reality gap caught by the mandatory verify-empirically
  rule (after metadata-vs-extra_body and the response-cost header) —
  the rule stays mandatory in all future specs.
- Deviation #2 (16 deleted, not ~18) is correct behavior: the spec's
  window bound excluded the two 19:02/19:06 'mock' rows, and the
  executor rightly refused to widen the clause on its own authority.
- RESOLVED 2026-07-07: Architect approved; the DELETE below was
  executed the same session. 24 rows deleted (verified: matched
  count 24, DB 223 -> 199; remaining models are only genuine gateway
  aliases: intern, lead-gemini, middle-groq, judge-groq, analyst;
  remaining kinds: judge 149, synthetic 50, real 0). Pre-cleanup
  backup kept in the session scratchpad.
  Original decision text (for the record): 24 residual mock-model rows remain
  (judge-alias 4, nonexistent-model-xyz 18, mock 2; from 2026-07-03
  and pre-window 2026-07-04) — test artifacts whose model names never
  existed in config.yaml. Harmless to gate G1 (all non-'real') but
  they appear as phantom models in per-model Ledger analytics. The
  Lead proposes deleting them with:
  DELETE FROM requests WHERE model IN
  ('judge-alias','nonexistent-model-xyz','mock');
  A permission guard correctly blocked the Lead from doing this
  unilaterally in-session (the executor had flagged it "left for
  your decision" and the Architect had not yet authorized it).
  Pre-cleanup backup exists in the session scratchpad. Execute only
  on explicit Architect approval, then record the deleted count here.

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

# Delegated Task (queued for a CHEAPER model session): Rule #1 cost accounting in shadow_eval.py

Intended executor: a CHEAPER model session (Middle-class task — the
delegation table itself says routine coding -> Middle, validated).
Planned by the Lead 2026-07-03 (D-0032); Lead/Architect reviews the
diff, per PROCESS/JUDGE_CALIBRATION_PROTOCOL.md spirit: the executor
does not self-certify.

Diagnosis (verified 2026-07-03, do not re-derive): proxy-side
accounting in gateway/requests.db is CORRECT — litellm prices the
underlying groq/gemini models at paid-tier rates (judge-groq 52 calls
= $0.0108, middle-groq $0.0191 logged). The costs are lost client-side
in gateway/shadow_eval.py only:

1. replay() computes cost via litellm.completion_cost on the ALIAS
   name ("openai/middle-groq"), which is not in the client pricing
   map -> exception -> cost_target=$0.0000 in every evidence-log line.
2. judge_pair() does not capture cost at all, so judge (supervision)
   spend never reaches the run report where the delegation decision
   is recorded.

Required changes (all in gateway/):

1. In replay() and judge_pair(), take the cost the PROXY accounted
   instead of recomputing client-side. Preferred source: the
   x-litellm-response-cost response header (in the litellm client:
   response._hidden_params, check "additional_headers"). VERIFY the
   exact key empirically with one live call through the gateway
   before wiring it up; if the header is absent, fallback = after the
   call, read the newest matching row from requests.db (same alias,
   ts >= call start). Do not keep completion_cost as silent fallback
   — a wrong $0 is worse than an explicit None.
2. evaluate() records per-pair judge_cost_usd; aggregate_by_category()
   adds mean_judge_cost_usd; format_report() and the evidence-log
   line in update_delegation_table() gain judge cost, e.g.
   "judge=judge-groq pass_rate=1.00 judge_cost=$0.0004".
3. Tests (mock _hidden_params / fallback path). All existing 33 tests
   must stay green; new behavior covered.
4. DELEGATION_TABLE.md: one caveat line noting that evidence entries
   dated <= 2026-07-03 show cost_target=$0.0000 as a client-side
   accounting artifact (real accounted costs are in requests.db), not
   an actual $0.
5. Do NOT change decide_status() semantics in this task; it already
   compares mean costs and will simply start seeing honest numbers.

Acceptance: a --categories coding run lead-gemini -> middle-groq
--judge-model judge-groq produces an evidence line where cost_target
and judge_cost are nonzero and match requests.db rows within
rounding; 33+ tests pass.

## Delegated Task 1 — Execution Report (2026-07-04, Sonnet session)

Status: code written, self-tested, NOT Architect-reviewed. Executor
does not self-certify (queue rule above) — next session must review
this diff (it lands together with task 2's, same session) before
task 3 starts.

Empirical verification FIRST (per the lesson from task 2 the same
session — do not trust a spec's assumed API shape, check it live):
the spec's preferred source was "the x-litellm-response-cost response
header ... response._hidden_params, check additional_headers". Live
call through the gateway (openai/middle-groq) showed two things the
spec got only half right:

1. additional_headers does carry the cost, but under a DIFFERENT key
   than assumed: "llm_provider-x-litellm-response-cost" (litellm
   prefixes provider-passthrough headers with "llm_provider-"), not
   the bare "x-litellm-response-cost".
2. There is a much simpler, more direct source that makes the header
   lookup unnecessary: response._hidden_params["response_cost"] is
   already the parsed float, and it matched the requests.db-logged
   cost for the same call exactly (2.813e-05 both places, live
   middle-groq call). Used this instead of parsing the header string.

Implemented in gateway/shadow_eval.py: new _extract_cost(response,
model, db_path, call_start) helper — hidden_params.response_cost
first, else newest matching gateway/requests.db row for that model
with ts >= call_start, else explicit None (never a silent $0, per
the spec's Rule #1 requirement). replay() and judge_pair() both use
it and gained a db_path= parameter; judge_pair() now returns
(verdict, cost) instead of just verdict — updated its two other
callers (evaluate(), calibrate()) accordingly. evaluate() threads
judge_cost_usd through; aggregate_by_category() adds
mean_judge_cost_usd (None when no judge ran, mirroring the existing
pass_rate pattern); format_report() and the evidence-log line in
update_delegation_table() both show judge_cost=$X.XXXX when present.
decide_status() untouched, as specced.

Tests: 48/48 pass (was 41 after task 2). New coverage: _extract_cost
hidden_params path, db fallback path, both-unavailable -> None path;
aggregate mean_judge_cost_usd with and without a judge; the
update_delegation_table evidence-line format. One pre-existing test
(test_judge_pair_with_mock) updated for the new (verdict, cost)
return shape.

Live acceptance run (same session, same throwaway --db discipline as
task 2 — real gateway process, GEMINI_API_KEY/GROQ_API_KEY from
gateway/.env, not the checked-in gateway/requests.db): seeded one
real lead-gemini "reverse a string" request, then `shadow_eval.py
--source-model lead-gemini --target-model middle-groq --judge-model
judge-groq --categories coding --sample 1 --days 1 --json`. Result:
cost_target=$0.00032122, judge_cost=$0.00034185, both matching the
corresponding requests.db rows exactly (traffic_kind 'replay' and
'judge' respectively, confirming task 1 and task 2 work correctly
together in the same run).

DELEGATION_TABLE.md gained the required caveat (item 4): all
evidence lines dated <= 2026-07-03 show cost_target=$0.0000 as a
client-side artifact of the bug this task fixes, not an actual $0.

Not done in this session: metrics.py Phase 2 readiness digest (task
3) — blocked on task 2 review and its own spec, per the queue note
above.

---

# Delegated Task 2: traffic_kind tagging in the request log

Purpose: gate G1 (ROADMAP.md, D-0033) counts only REAL traffic;
today real, synthetic, replay and judge requests are distinguishable
only by heuristics. Lead decisions below are made — do not redesign
them; escalate blockers instead of improvising around them.

Design (decided by the Lead 2026-07-04):

1. New column on requests: traffic_kind TEXT NOT NULL DEFAULT 'real',
   values: 'real' | 'synthetic' | 'replay' | 'judge'.
   - real: default; anything not explicitly tagged.
   - synthetic: working-set generation traffic.
   - replay: shadow_eval.py target-model calls.
   - judge: shadow_eval.py judge calls (calibration and evaluation).
2. The tag travels as litellm metadata from the CALLER, not by
   content sniffing: shadow_eval.py replay() sends
   metadata={"traffic_kind": "replay"}, judge_pair() sends "judge";
   any future synthetic generator must send "synthetic" (record this
   convention as a comment in sqlite_logger.py near the schema).
   gateway/sqlite_logger.py reads it in the callback (expected at
   kwargs["litellm_params"]["metadata"], but VERIFY the exact path
   empirically with one live call through the proxy before wiring;
   if client metadata does not reach the callback at all, STOP and
   escalate to the Lead — do not invent an alternative channel).
3. Migration: on logger init, ALTER TABLE ... ADD COLUMN when the
   column is missing (SQLite supports ADD COLUMN with DEFAULT).
   Backfill pre-migration rows honestly: rows matching the judge
   LIKE filter ('%impartial judge comparing two answers%') ->
   'judge'; ALL other pre-migration rows -> 'synthetic' (no real
   traffic has passed through the gateway yet — today's log is
   working sets, replays and tests; tagging it 'real' would poison
   gate G1 forever).
4. sample_requests() in shadow_eval.py additionally excludes
   traffic_kind IN ('replay', 'judge'). It deliberately KEEPS
   'synthetic' (replaying synthetic sources is legitimate for method
   development; gate math, not the sampler, excludes synthetic).
   The prompt LIKE filter STAYS as defense in depth
   (PROCESS/JUDGE_CALIBRATION_PROTOCOL.md rule 6).
5. Tests: migration adds the column to an existing db without data
   loss; callback writes each kind; untagged call logs 'real';
   backfill tags judge rows correctly; sampler excludes replay/judge
   but keeps synthetic. Existing tests stay green.

Acceptance: after one calibration run and one shadow_eval run against
the live proxy, requests.db contains correctly tagged 'judge' and
'replay' rows, a plain client call logs 'real', and
SELECT traffic_kind, COUNT(*) FROM requests GROUP BY 1 shows zero
pre-migration rows tagged 'real'.

## Delegated Task 2 — Execution Report (2026-07-04, Sonnet session)

Status: code written, self-tested, NOT Architect-reviewed. Executor
does not self-certify (queue rule above) — next session must review
the diff before task 1 or task 3 starts.

Implemented as specced in gateway/sqlite_logger.py and
gateway/shadow_eval.py: schema column with migration/backfill,
replay()/judge_pair() tag their own calls, sample_requests() excludes
replay/judge (keeps synthetic). Tests: 41/41 pass (was 33), including
new coverage for migration+backfill, tag-by-metadata, untagged->real,
and sampler exclusion (gateway/test_sqlite_logger.py,
gateway/test_shadow_eval.py).

SPEC DEVIATION FOUND BY EMPIRICAL VERIFICATION (the mandatory
"verify the exact path" step in item 2 above caught a real bug in the
spec's assumption, not just confirmed it):

litellm.completion(model=f"openai/{target_model}", api_base=<remote
gateway>, metadata={"traffic_kind": ...}) does NOT put metadata on
the wire. Proven live: with litellm.set_verbose + logging.DEBUG, the
actual POST body to the proxy was `{"messages": [...], "model": ...}`
— no metadata key at all. litellm.completion's own metadata= kwarg
only feeds ITS OWN local logging object; it is never serialized into
the HTTP request when the call target is a remote OpenAI-compatible
api_base (as opposed to metadata set by the proxy's own router,
e.g. model_group, which is a different code path already working).
First attempt at the live acceptance run confirmed this the hard way:
replay/judge rows landed in requests.db tagged 'real' instead of
'replay'/'judge'.

Fix: send the tag via extra_body={"metadata": {"traffic_kind": ...}}
instead — extra_body IS merged into the outgoing JSON body (verified
the same way: it appeared in the actual POST payload, and the
callback then saw kwargs["litellm_params"]["metadata"]["traffic_kind"]
correctly). Both replay() and judge_pair() now use extra_body; a code
comment documents the gotcha in both functions and near the schema
comment in sqlite_logger.py, so nobody re-discovers this by making
tagging silently no-op again.

Live acceptance run performed against a real gateway process (proxy
started from gateway/, GEMINI_API_KEY / GROQ_API_KEY from
gateway/.env), against a throwaway --db (not the checked-in
gateway/requests.db, to avoid polluting real gate-G1 telemetry with
verification noise): one real lead-gemini call, then
`shadow_eval.py --source-model lead-gemini --target-model middle-groq
--judge-model judge-groq --sample 1 --days 1` (no --update-table).
Result: lead-gemini row -> 'real', middle-groq row -> 'replay',
judge-groq row -> 'judge'. Matches the acceptance criterion exactly.

Also fixed in passing: the pre-existing test_failure_is_logged
asserted on r[-1] (last column) to find the error field; adding
traffic_kind as a new last column silently broke that assertion
(it started reading traffic_kind's value instead of error). Changed
to name-based column access (sqlite3.Row) — a latent fragility any
future column addition would have hit again.

Not done in this session (left for review before proceeding):
Rule #1 cost accounting (task 1) untouched; task 1's own live
verification (task 1 needs the x-litellm-response-cost header or a
requests.db fallback) has NOT been attempted and may hit a similar
spec-vs-reality gap — verify empirically before trusting the spec's
assumed header name, per the same lesson learned here.

## Research Notes for Later Phases (2026-07-03)

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Context-repetition priors to confirm locally: 50–62% of spend is
  re-sent history, 30–40% of tokens are redundant.
- Phase 2 compression (surveyed 2026-07-04): evaluate LLMLingua-2 /
  PCToolkit (token-level) and Letta-style recursive summarization
  (architectural) before building; validate with the existing Shadow
  Evaluation harness (compressed vs. full context, judge equivalence).
  Never perplexity-compress code context without validation.

This file is intended to be updated frequently.
