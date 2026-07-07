# Delegated Tasks 1–2: Rule #1 Cost Accounting + traffic_kind Tagging

Archived verbatim from CURRENT_CONTEXT.md on 2026-07-07 (D-0038).
Both ACCEPTED 2026-07-07 by the joint Lead review below (commits
af2281d task 1, 55c570a task 2); Architect confirmed the review.
Review findings were folded into Delegated Task 4 (see
task-4_test-isolation.md).

---

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

---

# Delegated Task 1 (spec): Rule #1 cost accounting in shadow_eval.py

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

# Delegated Task 2 (spec): traffic_kind tagging in the request log

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
