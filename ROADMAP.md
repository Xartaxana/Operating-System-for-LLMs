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
   - [ ] Operational: all real traffic actually routed through the gateway (needs API keys configured by the Architect).
2. [x] Guard: deterministic budget counters, 80% warning, 100% cutoff.
   Custom pre-call hook over the SQLite log (native LiteLLM budgets
   evaluated per D-0030 and rejected: they need Postgres+Redis).
3. [ ] Ledger: metrics.py daily digest — cost, task categories, context-repetition ratio.
4. [ ] Analyst: local small model answering questions over Ledger output.
5. [ ] Shadow Evaluation: replay sampled Lead requests on cheaper models, update DELEGATION_TABLE.md.

## Phase 2 — Routing (data-driven)

Entered only when Phase 1 telemetry shows what is worth routing (D-0029).

- Router with confidence-based escalation
  (per D-0030: evaluate RouteLLM before building; see docs/RELATED_WORK.md).
- Context compression for the primary cost driver found in Phase 1.
