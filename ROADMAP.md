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

### Phase transition procedure

When a gate's criteria are all green, the phase does not open
automatically: the gate report (numbers vs. thresholds) is written
into CURRENT_CONTEXT.md and the Architect signs the transition. The
first task of the opened workstream is always an evaluation of an
existing tool, never a build (D-0030).

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

## Phase 3 — Toolkit (D-0070) — CLOSED 2026-07-12

All six stages closed with evidence (intake t-044, packaging
decisions В1–В6, core spec v0, skeleton, both validation installs,
public wrap); the toolkit is public and released:
github.com/Xartaxana/Supervised-Delegation, tag v0.1.0. Operator
direction in session; residuals live in CURRENT_CONTEXT's queue on
their own evidence triggers. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.
