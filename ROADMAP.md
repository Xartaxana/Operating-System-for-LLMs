# Roadmap

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

## Phase 2 — Routing and Context Management Evaluation (data-driven)

Entered only on evidence (D-0029, D-0033, D-0059). The workstreams
have separate gates because they attack different cost drivers; each
gate is computable from existing telemetry (requests.db, evidence
log, routing journal) — no new infrastructure is needed to decide
whether to build infrastructure.

All thresholds below are initial calibrations (estimated up front per
the D-0028 pattern); revising one requires a DECISIONS.md entry with
rationale, not silent editing.

### Common gate (both workstreams)

- G1. ≥14 consecutive days of REAL traffic: the operator's actual
  working traffic, measured at the gateway (traffic_kind='real') or
  from Claude Code transcripts (D-0034). Synthetic working sets and
  replay/judge calls never count. Transcript history may satisfy G1
  retroactively once usage_report.py can compute it.
- G2. The judge is calibrated per PROCESS/JUDGE_CALIBRATION_PROTOCOL.md
  at the moment of the gate check (currently met: 13/13).

### Router gate ("what is worth routing" is now known)

- R1. Evidence volume: ≥30 judged Shadow Evaluation pairs per
  candidate category, across ≥2 independent runs (n=2 is a signal,
  not a basis for routing).
- R2. Money on the table: validated-delegable categories together
  account for ≥25% of the Lead's accounted spend (D-0032 prices)
  over the G1 window.
- R3. Stability: category shares shift by <10 percentage points
  between the two halves of the G1 window (routing rules learned
  today must still apply tomorrow).
- R4. Economics (Rule #1 with margin): projected monthly savings from
  routing the validated categories ≥3x the router's own projected
  monthly cost (inference overhead + evaluation effort amortized).
- R5. A paid Lead is in production, OR the Architect explicitly
  accepts an accounted-price justification (routing free-tier traffic
  saves cash $0; the architecture must not be built on hypothetical
  savings without sign-off).

First Router task when the gate opens: evaluate RouteLLM (D-0030),
fed with the preference pairs Shadow Evaluation has accumulated —
NOT build a router.

### Context management gate (the cost driver is confirmed locally)

Reframed per D-0036: the workstream is Context Management Evaluation
(provider caching, compaction, retrieval/memory, semantic caching),
not compression alone. All C-criteria are measured CACHE-AWARE: what
matters is paid uncached re-sent input, not raw repetition.

- C1. Driver confirmed: context-repetition ratio ≥40% measured on
  real multi-turn traffic (external prior 50–62%; if local traffic
  shows materially less, this lever is not ours).
- C2. Substance: ≥20 real sessions of ≥5 turns in the G1 window
  (compression of single-shot traffic is meaningless).
- C3. Money on the table: PAID UNCACHED re-sent context accounts for
  ≥25% of total accounted input spend over the G1 window (context
  already served from provider cache is not on the table).

First task when the gate opens (evaluation order fixed by D-0036):
provider prompt caching measurement first; only if C3 stays green
net of caching, evaluate LLMLingua-2 / PCToolkit (token level) and
Letta-style recursive summarization (architectural) — validated by
the existing Shadow Evaluation harness (compressed vs. full context,
judge rules equivalence); never perplexity-compress code context
without validation (docs/RELATED_WORK.md).

### Task pipeline gate (externalize intake/scope/DAG/allocate, D-0059)

The four stages a big task passes through — intake (formalize the
request), scope (boundaries + task-level DoD), DAG generate
(decompose into a dependency graph), allocate (assign a tier to each
node) — currently run manually inside the Lead session per CLAUDE.md
policy; recon t-008 confirmed no code components of this class
exist, and per-dispatch DoD (D-0054) externalizes scope at dispatch
granularity only. The task-level DAG lives nowhere but the Lead
session's context and dies at the session boundary. Why this is
worth externalizing, and what exactly is missing: docs/TASK_PIPELINE.md
(rationale preserved per the operator's instruction, D-0059).

- P1. Scale: ≥3 tasks in the G1 window each spanning ≥5 routing-log
  events (delegated/rejected/escalated chains under one task_id or
  an explicit task family) or crossing ≥2 sessions — the size where
  an in-head DAG starts dropping edges.
- P2. Driver confirmed: ≥1 `defect_found` or finding in the window
  attributing a defect to a dependency/scope lost across a dispatch
  or session boundary (the failure mode these artifacts prevent),
  OR ≥2 `decomposable` returns showing decomposition arriving too
  late.
- P3. Economics (Rule #1): projected artifact upkeep (Lead minutes
  per task) ≤ projected rework avoided over the window.

First task when the gate opens: evaluate existing task-graph
carriers (Claude Code native task tools, a plain markdown template
in PROCESS/) against one real multi-session task — NOT build
pipeline code (D-0030). Build-out order is fixed by D-0059: task
brief (intake+scope) → explicit DAG artifact with node statuses →
allocate column per node derived from the routing rules → code /
automation last, and only if artifact discipline proves value.
Distinct from the Router gate above: the Router dispatches an
already-scoped subtask; the allocate stage is its manual precursor,
and the gates are independent. Decomposition authority stays with
the Lead (D-0037) — the artifacts externalize the stages' OUTPUT,
not the right to perform them.

### Phase transition procedure

When a gate's criteria are all green, the phase does not open
automatically: the gate report (numbers vs. thresholds) is written
into CURRENT_CONTEXT.md and the Architect signs the transition. The
first task of the opened workstream is always an evaluation of an
existing tool, never a build (D-0030).

## Phase 3 — Toolkit (D-0070, operator direction 2026-07-11)

The system becomes an installable tool for OTHER projects: core
packaged apart from this dogfooding repo (users never see our tasks
and plans), one-step model-to-role binding, models EXAMINED at
onboarding, delegation then runs itself with minimal-attention
notifications. Intake with the full gap map and open operator
questions: docs/TOOLKIT_INTAKE_2026-07-11.md.

Stage order (fixed; artifacts before code):

1. [~] Inventory evaluation: core vs dogfooding vs entangled, plus
   the exam assets' repo-specificity (recon t-044) — an evaluation,
   never a build (D-0030/D-0033).
2. [ ] Operator packaging decisions (В1–В6 of the intake: form/name/
   visibility/contours/license/language/exam mandatoriness).
3. [ ] Core spec v0: template file set, install path, binding+exam
   onboarding, notification contract.
4. [ ] Template skeleton to the spec.
5. [ ] Validation by TWO installs: a fresh empty project (third
   deployment, ZCRT-analog) and an existing project (fourth).
6. [ ] Public wrap (user README, license, release) — only after both
   validations pass.

Phase 3 runs alongside Phase 1.5/2 telemetry loops (weekly
calibration continues; its evidence feeds the toolkit's default
policy shipped to users).
