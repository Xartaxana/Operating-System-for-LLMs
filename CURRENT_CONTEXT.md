# Current Context

## Maintenance Rule (D-0038)

This file holds LIVE state only: the current milestone, the single
authoritative task (D-0025), the queue, condensed system state,
strategic guidance still steering decisions, and operational
environment notes. When a task or workstream CLOSES (review ACCEPTED
or Architect sign-off), the session that closes it moves the spec,
execution report and review VERBATIM to docs/task_reports/ and leaves
a one-line pointer here. Evidence is never deleted, only relocated.
Rationale: this file is loaded on every boot (BOOT.md); boot context
is a paid resource — the project's own subject.

## Current Milestone

Phase 1.5 — Real Telemetry and Claude Code Routing (D-0034), on top
of a complete Phase 1 MVP. Plan of record:
docs/UNIFIED_PLAN_2026-07-07.md (D-0034..D-0036).

## Current Task (Authoritative, D-0025): Delegated Task 3

For a CHEAPER model session (Middle-class — per our own table this
is builder-tier work, not Lead work). Phase 2 readiness digest in
metrics.py. Spec (Lead, 2026-07-07); executor does not self-certify —
Lead/Architect reviews before the next task starts.

Add a "Phase 2 readiness" section to the metrics.py text and JSON
digest: one line per ROADMAP gate criterion (G1, G2, R1-R5, C1-C3)
showing current value vs. threshold and met / not met /
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

Note (post-spec, Task 5 landed): cc_usage now exists in the same DB
as a second real-traffic source (D-0034 — transcripts count toward
G1). The digest should count G1 days over BOTH requests
(traffic_kind='real') and cc_usage rows; if reading cc_usage is
deferred, the G1 line must say so explicitly ("gateway contour only;
cc_usage not counted yet").

## Routing MVP — DEPLOYED (2026-07-07, Architect-approved
## reprioritization ahead of Task 3)

Phase 1.5 step 2 is LIVE as a pilot on the operator's second project
D:\AO3_tests (its own git repo, commit b8125a0):

- CLAUDE.md routing policy (tiers, flat delegation D-0037, escalation
  rule, Lead degradation/restore D-0039, journal format);
- new generic agents scout (haiku) / builder (sonnet) / critic (opus);
- model frontmatter assigned to all nine existing QA-pipeline agents
  (mechanics -> haiku/sonnet; failure-analyst, test-strategist ->
  opus). ALL assignments status=estimated (D-0028);
- logs/routing-log.jsonl journal (events: delegated, accepted,
  escalated, decomposable, lead_degraded, lead_restored).

Retro baseline for AO3_tests (from cc_usage, pre-routing): 1422
turns, $276.70 accounted; opus $125.63 + fable $124.18 vs sonnet
$26.88 — 90% of spend on frontier tiers. This is the number the
weekly loop compares against (per accepted unit + escalation rate,
NOT share alone — see Architect correction below).

Next for this workstream: accumulate >=1 week of routed traffic,
then the first weekly calibration loop (journal + usage_report ->
table status moves).

INTERIM READ AFTER FIRST ROUTED ~18h (2026-07-08; NOT the weekly
loop — no status moves): journal 5 delegated / 4 accepted /
0 escalated, all category=implementation (builder). Transcripts:
sidechain 406 turns, all sonnet-5, $19.05 ($0.047/turn) vs Lead main
chain $0.242/turn — 63% of window turn volume ran off-frontier at 28%
of window spend. Journal-vs-transcript cross-check consistent on tier,
but three leaks: (a) 'model' field missing on all 5 delegated events
(AO3's log_append.py now enforces it); (b) one delegated (badge,
00:15) has no accepted event — reconcile; (c) /qa-loop dispatches
still unjournaled (known), so the 406 sidechain turns >> the 5
journaled delegations — category labels exist only for the journaled
subset. scout (haiku) and critic (opus): ZERO dispatches — those
delegation-table rows are accumulating no evidence at all.
Router implications (D-0029): all observed dispatch is ONE
deterministic rule (scoped implementation -> sonnet) and zero
escalations = zero boundary data; a router trained on this would
learn "always sonnet", which a static rule already does. Router
stays deferred; the informative events for it are escalations and
category diversity, neither present yet.
Both interim-read action items CLOSED same day (2026-07-08,
operator-directed "telemetry first, then revive tiers"):

1. TELEMETRY GAPS -> Delegated Task 7 ACCEPTED (commit 2f026f0,
   archived: docs/task_reports/task-7_agent-attribution.md).
   agent_id/agent_type live in cc_usage (1759/1759 sidechain rows
   attributed, backfilled; the per-line type field is
   attributionAgent, NOT agentType — spec errata), haiku 4.5 priced,
   0 NULL-cost rows. Per-agent cost per project now computable (F-3
   metric, R4 input). Tests 80/80 (31 tools + 49 gateway).
   Process firsts: delegation journaled at dispatch time in THIS
   repo's journal, and the acceptance ran through a critic (Opus)
   dispatch — first critic evidence (ПРИНЯТЬ, 0 correctness findings,
   consistent with independent Lead verification). Evidence so far:
   builder n=2 accepted / 0 escalations, critic n=1 accepted; all
   statuses stay estimated (Update Rule 1).

2. DEAD TIERS REVIVED by policy (commits 3736ecd here, e32d955 AO3):
   rule 1 — scout is the DEFAULT for recon (>1-2 known files or any
   repo search; non-dispatch on a recon task is a journal event);
   rule 3 — critic verdict is a mandatory acceptance input for diffs
   >~100 lines / schema / core logic / cost accounting and for
   unclear bugs before the Lead debugs; acceptance stays with the
   Lead (D-0037). Watch scout dispatches — still zero anywhere.

Note: an untracked agent test-reviewer.md
appeared in AO3_tests during deployment (parallel session?) — no
model assigned to it; assign on the next touch.

FIRST LIVE VERIFICATION (2026-07-07, same day): routing WORKS —
the operator's fresh AO3 session dispatched test-maintainer and it
ran on sonnet-5 (isSidechain=true), Lead stayed on Fable. Open
finding: the session did NOT write the delegated event to
routing-log.jsonl (dispatch went through /qa-loop, whose prompt
predates the policy) — watch for a few days, then either duplicate
the journal rule inside /qa-loop or strengthen CLAUDE.md. The
telemetry bug found the same day (subagent transcripts invisible to
cc_usage) was fixed as Delegated Task 6 (ACCEPTED 2026-07-08, see
Archive): sidechain traffic is now counted — 7.2% of all tokens,
$100.03 accounted, of which AO3_tests $57.82. The AO3 retro baseline
($276.70) therefore self-corrected upward by that amount.

DOGFOODING NOTE (2026-07-08): Task 6 was the first task dispatched to
a live Claude Code subagent (Sonnet builder, background, D-0040) and
accepted on first review — first evidence point for the "builder"
row (n=1, status stays estimated). The dispatch was manual because
the routing policy was not yet deployed here — now fixed.

ROUTING MVP — DEPLOYED TO THIS REPO (2026-07-08, reference/dogfooding
deployment; second after the AO3_tests pilot). Added: CLAUDE.md
(routing policy, journal format, degradation D-0039, permission
hygiene adapted to this repo's commands — pytest tools/gateway,
proxy from gateway/), .claude/agents/{scout,builder,critic}.md
(haiku/sonnet/opus, generic, encode D-0037), logs/routing-log.jsonl
(seeded journal_created + lead_degraded). CLAUDE.md kept lean and
defers to BOOT.md for full recovery (D-0038 tension noted in-file).

FINDING F-1 RECORDED (docs/FINDINGS.md, new file for dogfooding
findings): the default Claude Code harness does NOT initiate
delegation on its own ("Do not spawn agents unless the user asks");
left alone, the Lead does delegable work itself on the most expensive
tier. Consequence: the routing policy MUST auto-load into the Lead's
context per-project (CLAUDE.md) — agent definitions alone are not
enough. White Paper material (contrapoint to "frameworks maximize
agent count" — the production default is the opposite, conservative).
F-1 FORMALIZED (2026-07-08, restored Lead, operator approval):
D-0041 — delegation on the subscription contour is opt-in; deploying
routing = auto-loaded policy + tier agents + journal, always together.
D-0042 — operator-initiated downward model switch is a lead_degraded
trigger; initiator goes in the event's notes, telemetry cross-check
is the backstop for unjournaled switches.

DEGRADATION CYCLE COMPLETE (2026-07-08): operator switched
Fable->Opus 4.8 via /model and back (~5 min window). Full D-0039
cycle recorded in logs/routing-log.jsonl (lead_degraded ->
lead_restored); while degraded only authorized work was done (routing
deploy + F-1 record, commit 7f60273), decisions were deferred and
adopted after restore. First live exercise of the mechanism.
Deployment divergence found and fixed: the operator-switch trigger
wording was missing from the AO3_tests pilot CLAUDE.md — synced per
D-0042.

## System State (condensed, 2026-07-08)

- Phase 0 closed 2026-07-03 (Zero Context Recovery Test passed).
- Phase 1 steps 1-4 built and verified: Gateway (LiteLLM + SQLite
  request log), Guard (daily per-model budgets, warn 80% / refuse
  100%), Ledger (metrics.py digest), Analyst (Qwen3-4B via Ollama
  through the gateway under its own alias).
- Shadow Evaluation (step 5) operational: shadow_eval.py with
  --judge-model, --calibrate, --categories, honest Rule #1 cost
  extraction (proxy-accounted costs; never a silent $0); sampler
  excludes judge/replay traffic. Remaining: traffic volume, paid-Lead
  baseline (needs ANTHROPIC_API_KEY).
- Judge: judge-groq (groq/openai/gpt-oss-120b, free tier), calibrated
  13/13 at temperature=0, reproduced twice. Protocol:
  PROCESS/JUDGE_CALIBRATION_PROTOCOL.md (D-0031) — status-changing
  verdicts need chief-judge review; 1-2 random audits per run. No
  local judge on this hardware (Qwen3-4B 11/13, below the 90% bar);
  fallback order: judge-groq > paid API judge > local 4B restricted.
- traffic_kind tagging live: real/synthetic/replay/judge; gate G1
  counts only 'real'. The tag travels via extra_body metadata —
  litellm's metadata= kwarg does NOT reach the wire (verified; see
  comments in sqlite_logger.py / shadow_eval.py).
- Tests: gateway 49/49, tools 18/18 green. gateway/conftest.py
  isolates every test (tmp DB + full litellm callback-list
  snapshot/restore — restoring litellm.callbacks alone is NOT enough,
  litellm copies the logger into six lists at call time).
- requests.db: 199 rows (judge 149, synthetic 50, real 0 — the API
  contour has carried no real traffic yet); cc_usage table alongside
  (Claude Code transcript telemetry, 11149+ turns of which 1759+
  sidechain, idempotent import; both transcript layouts scanned since
  Task 6; agent_id/agent_type attribution + haiku pricing since
  Task 7, 0 NULL-cost rows).
- DELEGATION_TABLE.md: 4-state model (D-0035).
  provisionally_validated: coding -> Middle (tier-matching evidence),
  summarization / extraction / formatting -> intern; rejected:
  classification -> intern. Claude Code workstream rows: estimated.
  Flat delegation rule D-0037 recorded 2026-07-07.
- Delegated Tasks 1, 2, 4, 5, 6, 7: ACCEPTED and archived
  (docs/task_reports/ — see Archive below).

## Claude Code Baseline (Task 5, 2026-07-07 — live guidance)

- $1,177.48 accounted all-time (8747 turns, 79 sessions, 4 projects).
  Per model: sonnet-4-6 $735 / opus-4-8 $206 / fable-5 $198 /
  sonnet-5 $39.
- CACHE READS DOMINATE: 97.6% of input-side tokens are cache reads;
  accounted savings vs uncached $7,117 on a $1,178 total. Provider
  caching already absorbs nearly all context repetition on the
  subscription contour — first hard evidence for the D-0036 ordering
  (measure net-of-cache before building any compression).
- G1 LOOKS GREEN RETROACTIVELY: real traffic every day
  2026-06-18..2026-07-07 (20 consecutive days, >=14 required).
  Formal check = Task 3 digest + written gate report + Architect
  signature (D-0033). G2 (judge 13/13) also holds.
- SPEND MIX — ARCHITECT CORRECTION (2026-07-07): the baseline is
  CENSORED data (the operator rationed frontier usage because limits
  run out), so it cannot refute "the smartest model burns most". The
  correct reading — frontier burns FASTEST per unit of work — is
  confirmed: opus-4-8 $0.264/turn, fable-5 $0.216 vs sonnet-4-6
  $0.114, sonnet-5 $0.063 (2-4x). Consequences for Phase 1.5:
  (a) success metric is cost per accepted unit of work by tier + the
  escalation rate, NOT frontier-share-of-spend alone (freeing limits
  may legitimately RAISE Fable's share on architecture work);
  (b) the escalation journal is the instrument that measures the
  true tier boundary — it only produces data once routing is live.
  The weekly loop watches the recent-window trend, not the all-time
  total (history mixes pre-Fable weeks).

## Remaining Lead-tier Queue

- Routing policy text (queue item 1 above) — Lead-tier.
- White Paper: Architect review IN PROGRESS (started 2026-07-07).
  Comment 1 addressed same day (v0.1.1): §4 diagram replaced with the
  full target scheme — judge loop and deferred Router — in Mermaid;
  ARCHITECTURE.md diagrams converted to Mermaid too. Awaiting further
  review comments. Still queued: §7 upkeep against the evidence log;
  full sync with D-0034..D-0038 (two contours, 4-state statuses in
  §5) once the unified plan's first steps land.

## Environment Notes (this machine)

- Ollama 0.31.1 (winget); NVIDIA driver 582.28 — Qwen3-4B runs 100%
  on the GTX 1060 GPU (~5 s warm vs ~15 s CPU).
- Proxy must be started from gateway/ (callback imports are
  cwd-relative). litellm does NOT auto-load gateway/.env — export
  GEMINI_API_KEY / GROQ_API_KEY before starting the proxy.
- lead-gemini = gemini/gemini-2.5-flash (2.0-flash has ZERO free-tier
  quota on this key — 429, don't use it). Gemini free tier is
  5 req/min.
- lead-sonnet alias (anthropic/claude-sonnet-5) exists in config.yaml
  but is unused: no ANTHROPIC_API_KEY in this environment.
- Free-telemetry mode: intern/analyst (Ollama) carry synthetic
  Haiku-class accounting prices, so Guard/Ledger money paths work at
  $0 cash.
- Open operational item (Architect): route real API-contour traffic
  through the gateway; lead needs ANTHROPIC_API_KEY (paid).

## Archive (D-0038 pointers)

Closed work lives in docs/task_reports/ (index in its README.md):

- 2026-07-03_shadow-evaluation-and-llm-judge.md — first Shadow
  Evaluation runs; judge build, contamination and judge-bias lessons,
  calibration history, local-judge fallback measurement.
- 2026-07-03_research-notes.md — related-work priors (canonical:
  docs/RELATED_WORK.md).
- 2026-07-04_white-paper-iteration.md — White Paper v0.1 log, Phase 2
  gate definition, external review recording.
- task-1-2_cost-accounting-and-traffic-kind.md — Tasks 1-2 specs,
  execution reports, joint Lead review (ACCEPTED 2026-07-07).
- task-4_test-isolation.md — Task 4 spec, execution report, Lead
  review (ACCEPTED 2026-07-07, commit 80b29b2), mock-row cleanups.
- task-5_usage-report.md — Task 5 execution report, Lead review
  (ACCEPTED 2026-07-07, commit 7e645e7), full strategic findings
  text.
- task-6_subagent-transcripts.md — Task 6 spec, execution report
  (Sonnet builder subagent), Lead review (ACCEPTED 2026-07-08,
  commit 75af5b5), sidechain telemetry numbers and spec errata.
- task-7_agent-attribution.md — Task 7 spec, execution report
  (builder), critic review (first critic dispatch), Lead review
  (ACCEPTED 2026-07-08, commit 2f026f0); attributionAgent errata,
  per-agent cost breakdown unlocked.

This file is intended to be updated frequently.
