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

---

## Phase 2 — решённые гейты: критерии, перенесённые VERBATIM из ROADMAP (диет 2026-07-22, слово оператора «обнови роадмап и почисти закрытые пункты»)

Все три гейта Phase 2 решены (Context закрыт 07-13; Task pipeline
открыт 07-13, workstream закрыт адопцией D-0080 07-18; Router открыт
07-21); тексты критериев ниже — дословный перенос из ROADMAP.md, в
котором остаются статус-указатели и живые блоки решений.

### Common gate (both workstreams)

- G1. >=14 consecutive days of REAL traffic: the operator's actual
  working traffic, measured at the gateway (traffic_kind='real') or
  from Claude Code transcripts (D-0034). Synthetic working sets and
  replay/judge calls never count. Transcript history may satisfy G1
  retroactively once usage_report.py can compute it.
- G2. The judge is calibrated per PROCESS/JUDGE_CALIBRATION_PROTOCOL.md
  at the moment of the gate check (currently met: 13/13).

### Router gate ("what is worth routing" is now known)

- R1. Evidence volume: >=30 judged Shadow Evaluation pairs per
  candidate category, across >=2 independent runs (n=2 is a signal,
  not a basis for routing).
- R2 (revised 2026-07-20, D-0086; original wording preserved in
  DECISIONS_FULL). Money on the table = COORDINATION OVERHEAD: the
  Lead-tier spend on allocate/dispatch/acceptance machinery accounts
  for >=25% of the construction's accounted spend over the G1 window,
  measured by the check-11 method (main-session vs sidechain split,
  both accounting contours). Rationale: the original
  validated-category criterion measured a prize the policy had
  already taken (measured 0.01%); the honest prize is the
  coordinator itself (measured 2026-07-20: ~85% — met).
- R3. Stability: category shares shift by <10 percentage points
  between the two halves of the G1 window (routing rules learned
  today must still apply tomorrow).
- R4 (revised 2026-07-20, D-0086; original wording preserved in
  DECISIONS_FULL). Economics by PRE-REGISTERED EXPERIMENT: the
  router construction (D-arm of DEPLOYMENT_ECONOMY_EXAM — automatic
  allocate + judge acceptance, Lead out of the dispatch loop) beats
  the pre-registered keys on the exam battery: median of >=3 runs
  with $/accepted <= arm C, quality >= arm B - 0.05, wall-clock <=
  arm B. Quality is non-negotiable: a cheaper-but-worse construction
  fails the gate regardless of savings.
- R5. A paid Lead is in production, OR the Architect explicitly
  accepts an accounted-price justification (routing free-tier traffic
  saves cash $0; the architecture must not be built on hypothetical
  savings without sign-off).

First Router task when the gate opens (revised, D-0086): run the
D-arm under the pre-registered keys — NOT adopt a router. The
original first task (evaluate RouteLLM, D-0030) was DELIVERED
2026-07-20 ahead of the gate: bert rejected on our ground truth
(AUC 0.60 on the exam slice), remaining candidates (causal_llm,
haiku-classifier) queued; evaluation plan and verdicts —
docs/tasks/2026-07-20_routellm-evaluation-plan.md.

### Context management gate (the cost driver is confirmed locally)

Reframed per D-0036: the workstream is Context Management Evaluation
(provider caching, compaction, retrieval/memory, semantic caching),
not compression alone. All C-criteria are measured CACHE-AWARE: what
matters is paid uncached re-sent input, not raw repetition.

- C1. Driver confirmed: context-repetition ratio >=40% measured on
  real multi-turn traffic (external prior 50–62%; if local traffic
  shows materially less, this lever is not ours).
- C2. Substance: >=20 real sessions of >=5 turns in the G1 window
  (compression of single-shot traffic is meaningless).
- C3. Money on the table: PAID UNCACHED re-sent context accounts for
  >=25% of total accounted input spend over the G1 window (context
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

- P1. Scale: >=3 tasks in the G1 window each spanning >=5 routing-log
  events (delegated/rejected/escalated chains under one task_id or
  an explicit task family) or crossing >=2 sessions — the size where
  an in-head DAG starts dropping edges.
- P2. Driver confirmed: >=1 `defect_found` or finding in the window
  attributing a defect to a dependency/scope lost across a dispatch
  or session boundary (the failure mode these artifacts prevent),
  OR >=2 `decomposable` returns showing decomposition arriving too
  late.
- P3. Economics (Rule #1): projected artifact upkeep (Lead minutes
  per task) <= projected rework avoided over the window.

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

---

## Phase 2 — перенос закрывающего коммита 2026-07-23 (D-0078; подпись оператора в сессии: «закрытие фазы 2 подтверждаю»)

Блоки ниже — VERBATIM из ROADMAP.md на момент закрытия фазы.

### Gate status (all three DECIDED; criteria archived 2026-07-22)

Full criteria texts (G1/G2, R1–R5, C1–C3, P1–P3 and the
first-task paragraphs) moved VERBATIM to
docs/task_reports/2026-07-15_roadmap-closed-phases.md (roadmap diet
2026-07-22, operator word; D-0038 — relocated, not deleted).

- **Common gate**: met since 2026-07-13 (G1 16/14 real days, G2
  13/13).
- **Router**: OPENED 2026-07-21 — decision block below; the LAST
  live workstream of Phase 2 (closure path below).
- **Context management**: CLOSED by direct measurement 2026-07-13 —
  C3 truly-uncached paid input 0.11% vs ≥25% threshold (cache-aware,
  requests.db); provider caching works through the proxy.
  Reanimation only by explicit Architect decision.
- **Task pipeline (D-0059)**: OPENED 2026-07-13; WORKSTREAM CLOSED
  2026-07-18 by adoption D-0080 — markdown DAG in docs/tasks/ as the
  standard carrier (≥5 events or ≥2 sessions) + the
  delegation-boundary audit loop; evidence — calibration #2. Further
  automation only on evidence, build order fixed by D-0059.

### Deferred within Phase 2: multi-agent parallelism and isolation

Recorded 2026-07-11 (operator question surfaced the gap: these
decisions lived only in RELATED_WORK/queue, invisible at phase level).
Already IN policy, not deferred: parallel dispatches declare owned
paths (CLAUDE.md rule 4), parallel-session discipline (D-0060).
Deferred with named triggers, no work opened:

- Lane-contract manifest fields (Owns / Non-goals / Handoff,
  maxConcurrent caps; OpenClaw survey) — ADOPTED 2026-07-12 with the
  A3 pass (D-0073 dispatch context manifest: declarative on reads,
  normative on writes; fields mandatory on writing/parallel
  dispatches). Chat budget / Tool posture not taken (Rule #1).
  Evidence home: docs/RELATED_WORK.md "OpenClaw survey" item 3.
- Per-unit git worktree isolation (GSD) — REJECTED by Rule #1
  (harness worktree isolation exists; no parallel volume). Reopen
  trigger: real parallel-dispatch volume plus a path-collision
  incident (D-0060 evidence class). Evidence home:
  docs/RELATED_WORK.md "GSD" item 3.

The task-pipeline gate above (P1: tasks spanning >=5 events or >=2
sessions) is also the scale detector for this class: big-project
parallelism becomes a workstream only when that gate's numbers say
the coordination artifacts themselves are overflowing.

### Gate decision 2026-07-21 (Router; signature — Architect, in session: «подписываю открытие Router-гейта»)

- **Router workstream: OPENED.** Criteria per D-0086 revision, all
  green at signature: R1 (≥30 pairs / ≥2 runs: ~34 coding→Sonnet
  pair-instances over 5 runs, F-39 caveat recorded); R2' (coordination
  overhead ≥25%: measured ~85%, check-11 method); R3 (formally met);
  R5 (paid Lead live + D-0032 accounted-price justification; signed
  by operator 2026-07-21); R4' (pre-registered D-arm keys taken by
  series D№1–№6: $/accepted median $2.08 ≤ C $2.60; quality median
  0.975 ≥ 0.87; wall-clock median 17.1 ≤ 18 min with parallel
  launch — evidence: DEPLOYMENT_ECONOMY_EXAM Runs log 2026-07-21 +
  docs/tasks/2026-07-21_economy-exam-Darm-plan.md).
- The gate's first task per D-0086 (run the D-arm under the keys,
  NOT adopt a router) was DELIVERED by the same series that took
  R4'. The adopt decision was TAKEN the same day, informed by the
  hybrid H+C exam: D-0087 (leaf routing, kernel rule R13; two judge
  forms incl. the subscription subagent at 13/13 equivalence, t-254)
  + D-0088 (one architecture: the task path forks by SIZE at intake,
  contours demoted to supply channels). All six LLM-router
  candidates remain rejected by evidence (two survey waves; reopen
  trigger pre-registered at ≥100 labeled examples); the construction
  routes by the static category ladder + calibrated judge.
- **REMAINING TO CLOSE the workstream (and with it Phase 2):**
  leaf-routing exploitation mode is ACTIVE since 2026-07-22
  (operator word; CURRENT_CONTEXT carries the mode) — the first
  LIVE window of `basis: "judge"` acceptances accrued (07-22);
  calibration #4 RAN 2026-07-23 (early, operator word) and check 30
  came back CLEAN: 8/8 judge-basis acceptances leaf-class, no judge
  hallucinations found (2 judge-form cases recorded), economics in
  Rule #1's favor — see the `calibrated` 07-23 notes; on this
  audit the closure block lands here with the Architect's signature,
  and the closing commit moves the Phase 2 narrative to the archive
  home per D-0078. CLOSING-COMMIT DUTY (operator word 2026-07-22,
  F-48/D-0082 class): the reopen TRIGGERS of the deferred
  parallelism/isolation section below do not evaporate with the
  archived narrative — the same commit moves them into a LIVE
  carrier (CURRENT_CONTEXT evidence-gated queue) as standing items;
  a trigger living only in an archive file is not handed over.

### Gate decision 2026-07-13 (report of 2026-07-12, revised 07-13; signature — Architect, in session)

- **Task pipeline workstream (D-0059): OPENED.** Common gate green
  (G1 16/14 real days, G2 13/13), P1–P3 met (10 tasks ≥5 events vs
  threshold 3; boundary-loss drivers t-029 + F-36; upkeep ≤ rework).
  First task — an EVALUATION, not a build (D-0030): existing
  task-graph carriers (Claude Code native task tools vs a markdown
  template in PROCESS/) against one real multi-session task; build
  order thereafter fixed by D-0059.
- **Router workstream: stays CLOSED** — R1 red (coding 12 judged
  pairs / 5 runs vs ≥30/2 required; stage-2 replays are the feeder);
  R2/R3 computable for the first time since the API window — first
  honest slice at calibration ~07-18. Independent of this signature.
- **Context management workstream: CLOSED by direct measurement** —
  C3 truly-uncached paid input = 0.11% vs ≥25% threshold
  (cache-aware, requests.db, F-38-correct formula); provider caching
  works through the proxy. Reanimation only by explicit Architect
  decision.
- Report archived per D-0038: docs/task_reports/ (pointer in
  CURRENT_CONTEXT).
