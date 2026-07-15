# ROADMAP closed phases — archive (boot-diet round 11, D-0078)

Verbatim closed-phase narratives moved out of ROADMAP.md on
2026-07-15 per D-0038/D-0078 (boot-diet round 11, Lead+Architect
decision): ROADMAP.md keeps a short pointer per closed phase
(status, close date, link here) plus the live Phase 2 gates;
evidence is never deleted, only relocated. Future phase closures
follow the same move: full closure narrative here, pointer stays
in ROADMAP.md.

## Phase 0 — Foundation

- [x] Automatic commits
- [x] Patch protocol
- [x] Project foundation
- [x] Memory architecture
- [x] Boot sequence
- [x] Architecture specification (ARCHITECTURE.md)
- [x] Preliminary delegation table (DELEGATION_TABLE.md)
- [x] Zero Context Recovery Test passes (exit criterion) — passed 2026-07-03

## Phase 1 — Supervised Lead (MVP)

Each step is useful on its own even if the next one is never built.

1. [x] Gateway built: LiteLLM proxy + SQLite request log (gateway/), logging path verified end-to-end.
   - [x] Operational — RESOLVED by D-0034 + live keys (bookkeeping
     2026-07-11): the sub-item predates D-0034, which redefined the
     real-traffic source — the operator's real Lead is the Claude
     Code subscription, measured from transcripts (cc_usage), NOT
     traffic to force through the proxy. The gateway's role is the
     API contour: lab runs + paid runs (ANTHROPIC_API_KEY live
     2026-07-10, lead/lead-sonnet verified end-to-end; first paid
     run 2026-07-11). "All real traffic through the gateway" stopped
     being an architecture goal on 2026-07-07.
2. [x] Guard: deterministic budget counters, 80% warning, 100% cutoff.
   Custom pre-call hook over the SQLite log (native LiteLLM budgets
   evaluated per D-0030 and rejected: they need Postgres+Redis).
3. [x] Ledger: metrics.py daily digest — cost, task categories (keyword
   heuristics), context-repetition ratio, budget events; text + JSON output.
4. [x] Analyst: local small model (Ollama, Qwen3-4B) answering questions
   over Ledger output through the gateway under its own alias.
5. [x] Shadow Evaluation: shadow_eval.py built and tested; first real
   run 2026-07-03 (lead-gemini -> intern, 10 requests) produced the
   first evidence-backed DELEGATION_TABLE.md verdicts. LLM judge
   built and calibrated (judge-groq 13/13; second judge judge-gemini
   13/13, t-023). Middle tier as replay target — DONE (runs
   2026-07-03 and 2026-07-11). Paid Lead baseline — DONE 2026-07-11
   (lead-sonnet working set + tier-matched replays, chief-judge
   reviewed; docs/SHADOW_EVALUATION_LOG.md). Residual "real
   API-contour traffic volume" is NOT phase work: it is already
   counted by Phase 2 gate criteria (G1/R1) and arrives with real
   deployments (Phase 3), not with more lab runs.

## Phase 1.5 — Real Telemetry and Claude Code Routing (D-0034)

The operator's real Lead is the Claude Code subscription; this
workstream measures and routes that traffic. Merged from the external
plan 2026-07-07 (docs/UNIFIED_PLAN_2026-07-07.md, which holds the
detailed specs and acceptance criteria). Like Phase 1, every step is
useful on its own:

1. [x] Baseline telemetry — DONE 2026-07-07 (Delegated Task 5):
   tools/usage_report.py parses Claude Code transcripts into per-day
   / per-model / per-session / per-project token and accounted-cost
   reports, cache-aware from day one; the baseline report over the
   full pre-routing history was delivered BEFORE routing changed
   behavior ($1,177 all-time, cache-read share 97.6% — the
   CURRENT_CONTEXT "Claude Code Baseline" section) and is now the
   PRE-window of tools/savings_report.py (calibration check 18).
2. [x] Routing in Claude Code: tiered subagents (scout=Haiku,
   builder=Sonnet, critic=Opus), routing policy + escalation rule in
   the project CLAUDE.md, delegation journal. Every routed category
   enters DELEGATION_TABLE.md as `estimated` (D-0028, D-0035); the
   escalation journal is its evidence stream. DEPLOYED 2026-07-07 as
   a pilot on the operator's second project (D:\AO3_tests) and
   2026-07-08 on this repository itself (reference deployment,
   D-0041), including Lead degradation/restore (D-0039/D-0042),
   universal skip events, class-fix discipline with the sibling map
   (D-0043) and /qa-loop journaling; builder/critic tiers have first
   accepted evidence (Tasks 6-7), agent-attributed telemetry live
   (cc_usage agent_id/agent_type). Policy text Architect-accepted
   2026-07-09 (171078c). Routed-traffic requirement satisfied
   2026-07-08..11 (147+ journal events, 39+ tasks, all four tiers,
   full degradation cycle) — the volume basis on which the operator
   authorized the first calibration early. DONE; marked [x]
   2026-07-11 (bookkeeping).
3. [x] Weekly calibration loop — FIRST RUN DONE 2026-07-11 (all 18
   checks incl. the economics trend added same day; `calibrated`
   event 08:55 with full counters; 4 Claude-contour table rows moved
   estimated -> provisionally_validated on journal evidence; F-32
   found and closed on the run itself). The loop is now a STANDING
   OPERATION, not phase work: recurring ~weekly (next ~2026-07-18),
   staleness watched by the Boot Report line and the SessionStart
   hook (D-0047). Executable checklist:
   PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md.

### Phase 1 + 1.5 closure (bookkeeping 2026-07-11; signature — Architect)

Every step above is done with evidence attached; the single honest
residual (real API-contour traffic volume) is not phase work — it is
counted by the Phase 2 gates (G1/R1) and arrives with real
deployments (Phase 3). The telemetry loops (weekly calibration,
savings trend) continue as standing operations.

**CLOSED 2026-07-11 — Architect confirmation given by the operator
in session («да закрывай»), recorded by the Lead the same turn.**

This workstream is NOT the deferred Router (D-0029): routing policy
is executed by the Lead session itself following documented rules,
no new inference infrastructure. The Router build decision still
waits for the Phase 2 gate.

## Phase 3 — Toolkit (D-0070, operator direction 2026-07-11)

The system becomes an installable tool for OTHER projects: core
packaged apart from this dogfooding repo (users never see our tasks
and plans), one-step model-to-role binding, models EXAMINED at
onboarding, delegation then runs itself with minimal-attention
notifications. Intake with the full gap map and open operator
questions: docs/TOOLKIT_INTAKE_2026-07-11.md.

Stage order (fixed; artifacts before code):

1. [x] Inventory evaluation: core vs dogfooding vs entangled, plus
   the exam assets' repo-specificity (recon t-044) — an evaluation,
   never a build (D-0030/D-0033). Closed 2026-07-11.
2. [x] Operator packaging decisions (В1–В6 of the intake: form/name/
   visibility/contours/license/language/exam mandatoriness). Closed
   2026-07-11 (MIT confirmed by the operator).
3. [x] Core spec v0: template file set, install path, binding+exam
   onboarding, notification contract. Closed 2026-07-11.
4. [x] Template skeleton to the spec — first push a0b3cd9
   "v0.1.0-pre" (github.com/Xartaxana/Supervised-Delegation), second
   release snapshot f91fb31. Closed 2026-07-11 (pipeline
   t-045..t-053; day/evening closure reports).
5. [x] Validation by TWO installs: a fresh empty project (third
   deployment, ZCRT-analog) — DONE 2026-07-11 (stage 5a, t-055 +
   repeat t-064, stranger reached the first delegated cycle) — and
   an existing project (fourth) — DONE 2026-07-12 (stage 5b, D:\Dog,
   operator self-install, ACCEPTED; report:
   docs/task_reports/2026-07-12_toolkit-stage5b-operator-install-report.md).
   Findings fix batch (F-35/F-36 + exam-retry + journal-leak) queued
   in CURRENT_CONTEXT — recommended before stage 6.
6. [x] Public wrap (user README, license, release) — DONE 2026-07-12:
   PRE-RELEASE banner off (В2: both validation installs passed), MIT
   license shipped since the first push, fourth release snapshot
   e0754a6 + annotated tag v0.1.0 (staging and published in sync,
   axis 7). Preceded, per the Lead recommendation, by the 5b findings
   fix batch (М1–М6, closed 2026-07-12 night, snapshot b92cbd2) and
   the D-0072 tier doc-string in all three CLAUDE.md copies (11f710b
   + AO3 0a1f01e). Narrative:
   docs/task_reports/2026-07-12_phase3-closure.md.

### Phase 3 closure (2026-07-12; подпись — оператор)

All six stages closed with evidence attached: intake t-044, operator
packaging decisions В1–В6, core spec v0, skeleton a0b3cd9, both
validation installs (5a stranger 2026-07-11, 5b operator self-install
2026-07-12), public wrap v0.1.0. The toolkit is public and released:
github.com/Xartaxana/Supervised-Delegation, tag v0.1.0. Residuals
(tier-gate hardening on first incident, A5 witness wrapper, etc.)
live in CURRENT_CONTEXT's queue on their own evidence triggers; user
deployments are outside axis 7 by design — their feedback arrives as
issues, not phase work.

**CLOSED 2026-07-12 — operator direction in session («давай закроем
фазу 3»); the release word (push + tag v0.1.0) given the same
session, recorded by the Lead the same turn.**

Phase 3 ran alongside Phase 1.5/2 telemetry loops (weekly calibration
continues; its evidence feeds the toolkit's default policy shipped to
users).
