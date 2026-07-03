# Current Context

## Current Milestone

Phase 1 — Supervised Lead (MVP), step 2: Guard.

## Current Status

Phase 0 closed 2026-07-03 (Zero Context Recovery Test passed).

Phase 1 step 1 (Gateway) is built and verified: gateway/ contains the
LiteLLM proxy config and a SQLite logging callback. Verified end-to-end
locally: the proxy serves an OpenAI-compatible endpoint, success and
failure requests both produce rows in the log (gateway alias, provider
model, tokens, cost, latency, prompt JSON, response). Tests in
gateway/test_sqlite_logger.py pass without API keys.

Open operational item (Architect): set ANTHROPIC_API_KEY and point real
traffic at the gateway (gateway/README.md). Telemetry for the Ledger
starts accumulating only after that.

## Current Objective

Phase 1 step 2: Guard — deterministic budget counters in the request
path, warning at 80% of budget, hard cutoff at 100%. No LLM involved
(see ARCHITECTURE.md, "Guard"; D-0027).

---

# Current Task (Authoritative)

Implement the Guard in gateway/: per-model and per-day token/cost
counters, a warning at 80% of the configured budget, hard refusal
at 100%. Budgets are configuration, not code. The enforcement path
must be covered by tests that do not require API keys.

Per D-0030, first evaluate LiteLLM's native budget mechanisms
(virtual keys, per-key/per-team budgets, rate limits); write a custom
proxy hook only for whatever the native mechanisms cannot express
(e.g. the 80% warning semantics). See docs/RELATED_WORK.md,
"Cost telemetry / budget enforcement".

## Research Notes for Later Phases (2026-07-03)

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Shadow Evaluation compares total task cost including retry loops
  (DELEGATION_TABLE.md update rule 4).
- Context-repetition priors to confirm locally: 50–62% of spend is
  re-sent history, 30–40% of tokens are redundant.

This file is intended to be updated frequently.
