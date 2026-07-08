# Task Reports Archive

Closed work, archived out of the boot path per D-0038: when a task or
workstream closes (review ACCEPTED or Architect sign-off),
CURRENT_CONTEXT.md keeps only a one-line pointer and the full spec,
execution report and review move here VERBATIM in the same session.
Evidence is never deleted, only relocated.

## Index

- [2026-07-03_shadow-evaluation-and-llm-judge.md](2026-07-03_shadow-evaluation-and-llm-judge.md) —
  first Shadow Evaluation runs, LLM judge build/calibration history,
  contamination and judge-bias lessons, local-judge fallback
  measurement.
- [2026-07-03_research-notes.md](2026-07-03_research-notes.md) —
  related-work priors for later phases (also recorded in
  docs/RELATED_WORK.md and DELEGATION_TABLE.md).
- [2026-07-04_white-paper-iteration.md](2026-07-04_white-paper-iteration.md) —
  White Paper v0.1 log, Phase 2 gate definition, external review
  recording.
- [task-1-2_cost-accounting-and-traffic-kind.md](task-1-2_cost-accounting-and-traffic-kind.md) —
  Delegated Tasks 1–2: specs, execution reports, joint Lead review
  (ACCEPTED 2026-07-07).
- [task-4_test-isolation.md](task-4_test-isolation.md) —
  Delegated Task 4: spec, execution report, Lead review (ACCEPTED
  2026-07-07, commit 80b29b2), residual mock-row cleanup.
- [task-5_usage-report.md](task-5_usage-report.md) —
  Delegated Task 5: execution report, Lead review (ACCEPTED
  2026-07-07, commit 7e645e7), full strategic baseline findings text
  including the Architect's censored-data correction.
- [task-6_subagent-transcripts.md](task-6_subagent-transcripts.md) —
  Delegated Task 6: subagent transcripts visible to cc_usage; spec,
  execution report, Lead review (ACCEPTED 2026-07-08, commit
  75af5b5). First task executed by a live Sonnet builder subagent
  (D-0037/D-0040); sidechain telemetry = 7.2% of tokens, $100.03.
- [task-7_agent-attribution.md](task-7_agent-attribution.md) —
  Delegated Task 7: agent_id/agent_type in cc_usage + haiku pricing;
  spec, execution report, critic review, Lead review (ACCEPTED
  2026-07-08, commit 2f026f0). First journaled-at-dispatch delegation
  in this repo and first critic-tier dispatch; per-agent cost
  breakdown unlocked (R4/F-3 input).
- [2026-07-08_routing-dogfooding-day.md](2026-07-08_routing-dogfooding-day.md) —
  interim 18h routed-traffic read, dead-tier revival, F-1
  formalization (D-0041/D-0042), first degradation cycle, and the
  mechanism day: operator questions F-12..F-16 -> D-0044..D-0051
  (rejected/trail/calibration/map/handoff/boot-diet mechanisms).
