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

# Current Task (Authoritative): White Paper iteration

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
of the draft.

---

# Delegated Task Queue (for CHEAPER model sessions)

Execution order (each task reviewed by Lead/Architect before the
next starts; the executor does not self-certify):

1. Rule #1 cost accounting in shadow_eval.py (spec below). CODE
   WRITTEN AND SELF-TESTED 2026-07-04 by a Sonnet session, run
   immediately after task 2 in the same session (Architect judged the
   two independent — different concern, only incidental code overlap
   in replay()/judge_pair()) — see "Delegated Task 1 — Execution
   Report" below. AWAITING REVIEW (not Architect-signed).
2. Traffic-kind tagging in the request log (spec below; born from
   gate G1, D-0033). CODE WRITTEN AND SELF-TESTED 2026-07-04 by a
   Sonnet session — see "Delegated Task 2 — Execution Report" below.
   AWAITING REVIEW (not Architect-signed; do not treat as done).
3. metrics.py "Phase 2 readiness" digest section: print current
   values vs. the ROADMAP gate thresholds (G/R/C criteria) so gate
   progress is visible in every daily digest. Depends on task 2;
   spec to be written by the Lead after task 2 lands. NOT STARTED —
   task 2 is unreviewed, and this task still needs its spec written.

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
