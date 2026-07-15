# Roadmap

Closed phases live in the archive per D-0038/D-0078 (boot-diet
round 11): full closure narratives, gate reports and evidence moved
VERBATIM to docs/task_reports/2026-07-15_roadmap-closed-phases.md;
each closed phase keeps a status pointer here. Live gates stay in
this file.

## Phase 0 — Foundation — CLOSED

All items [x]; exit criterion (Zero Context Recovery Test) passed
2026-07-03. Checklist:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 1 — Supervised Lead (MVP) — CLOSED 2026-07-11

All five steps (gateway, guard, ledger, analyst, shadow evaluation)
done with evidence; closed together with Phase 1.5, Architect
signature 2026-07-11. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 1.5 — Real Telemetry and Claude Code Routing (D-0034) — CLOSED 2026-07-11

Baseline telemetry, tiered routing deployed on both repos, weekly
calibration loop — the loop continues as a STANDING OPERATION
(next ~2026-07-18), not phase work. This workstream is NOT the
deferred Router (D-0029): that build decision still waits for the
Phase 2 gate below. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

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

### Phase transition procedure

When a gate's criteria are all green, the phase does not open
automatically: the gate report (numbers vs. thresholds) is written
into CURRENT_CONTEXT.md and the Architect signs the transition. The
first task of the opened workstream is always an evaluation of an
existing tool, never a build (D-0030).

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

## Phase 3 — Toolkit (D-0070) — CLOSED 2026-07-12

All six stages closed with evidence (intake t-044, packaging
decisions В1–В6, core spec v0, skeleton, both validation installs,
public wrap); the toolkit is public and released:
github.com/Xartaxana/Supervised-Delegation, tag v0.1.0. Operator
direction in session; residuals live in CURRENT_CONTEXT's queue on
their own evidence triggers. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.
