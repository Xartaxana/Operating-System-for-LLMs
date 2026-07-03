# Current Context

## Current Milestone

Phase 1 — Supervised Lead (MVP), step 3: Ledger.

## Current Status

Phase 0 closed 2026-07-03. Phase 1 steps 1–2 built and verified:

- Gateway (step 1): LiteLLM proxy + SQLite request logging (gateway/).
- Guard (step 2): deterministic daily per-model budgets as a pre-call
  hook over the same SQLite log; warn event at 80% (once per model per
  day), HTTP 429 at 100%. Verified end-to-end through the running
  proxy: over-budget request refused with 429 + block event, request
  at 80% passed with warn event. LiteLLM native budgets were evaluated
  per D-0030 and rejected (require Postgres+Redis, both deferred by
  ARCHITECTURE.md). Tests: gateway/test_guard.py, no API keys needed.

Open operational item (Architect): set ANTHROPIC_API_KEY and point real
traffic at the gateway (gateway/README.md). Telemetry for the Ledger
starts accumulating only after that.

## Current Objective

Phase 1 step 3: Ledger — metrics.py daily digest over the request log:
cost per model/day, task categories, context-repetition ratio
(see ARCHITECTURE.md, "Ledger"). Pure Python/SQL, no LLM.

---

# Current Task (Authoritative)

Implement the Ledger in gateway/ (or a sibling module): a metrics
script over requests.db producing a daily digest — tokens/cost per
model and per day, budget events, and the context-repetition ratio
(overlap between consecutive prompts of the same model). External
priors to confirm or refute with local data: 50–62% of spend is
re-sent history, 30–40% of tokens are redundant (docs/RELATED_WORK.md).
Output is human-readable text plus machine-readable rows the Analyst
(step 4) can consume. Covered by tests on a seeded database.

## Research Notes for Later Phases (2026-07-03)

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Shadow Evaluation compares total task cost including retry loops
  (DELEGATION_TABLE.md update rule 4).

This file is intended to be updated frequently.
