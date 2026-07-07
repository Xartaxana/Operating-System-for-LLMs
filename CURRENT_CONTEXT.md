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

Phase 2 readiness digest in metrics.py. Spec (Lead, 2026-07-07);
Middle-class task; executor does not self-certify — Lead/Architect
reviews before the next task starts.

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

## Queue After Task 3 (unified plan §3)

1. Claude Code routing (Phase 1.5 step 2): .claude/agents/
   scout|builder|critic.md with model frontmatter, routing policy +
   escalation rule in the project CLAUDE.md, delegation journal hook
   (logs/routing-log.jsonl). Lead-tier: policy wording decides real
   behavior; needs Architect acceptance of the policy text. The
   policy MUST encode D-0037 flat delegation: subagents never spawn
   subagents; parallelism is Lead-side; "task is decomposable" is an
   escalation-journal category.
2. Weekly calibration loop (Phase 1.5 step 3): escalation journal +
   usage report reviewed, table statuses moved on evidence, policy
   adjusted. First loop after >=1 week of routed traffic.
3. Context Management Evaluation spec (D-0036): written only after
   the routing baseline exists; C3 is measured net of provider
   caching.

## System State (condensed, 2026-07-07)

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
  (Claude Code transcript telemetry, 8747+ turns, idempotent import).
- DELEGATION_TABLE.md: 4-state model (D-0035).
  provisionally_validated: coding -> Middle (tier-matching evidence),
  summarization / extraction / formatting -> intern; rejected:
  classification -> intern. Claude Code workstream rows: estimated.
  Flat delegation rule D-0037 recorded 2026-07-07.
- Delegated Tasks 1, 2, 4, 5: ACCEPTED and archived
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
- White Paper: §7 upkeep against the evidence log; Architect review
  of the draft; sync with D-0034..D-0038 once the unified plan's
  first steps land.

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

This file is intended to be updated frequently.
