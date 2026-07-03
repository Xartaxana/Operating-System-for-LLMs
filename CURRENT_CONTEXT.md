# Current Context

## Current Milestone

Phase 1 — Supervised Lead (MVP), step 4: Analyst.

## Current Status

Phase 0 closed 2026-07-03. Phase 1 steps 1–3 built and verified:

- Gateway (step 1): LiteLLM proxy + SQLite request logging (gateway/).
- Guard (step 2): daily per-model budgets as a pre-call hook; warn at
  80%, HTTP 429 at 100%; verified through the running proxy.
- Ledger (step 3): gateway/metrics.py — daily digest per model/day
  (requests, failures, tokens, cost, latency, answer length),
  context-repetition ratio (common-prefix overlap of consecutive
  prompts), keyword-heuristic task categories, budget events;
  human-readable text or --json for the Analyst. 12 tests pass,
  no API keys needed.

Open operational item (Architect): set ANTHROPIC_API_KEY and point real
traffic at the gateway (gateway/README.md). Telemetry starts
accumulating only after that — the Ledger digest is empty until then.

## Current Objective

Phase 1 step 4: Analyst — a small local model (Ollama, Qwen3-4B class)
that reads Ledger output (never raw conversations) and answers
"where did tokens go?" (see ARCHITECTURE.md, "Analyst").

---

# Current Task (Authoritative)

Implement the Analyst: a script that feeds the Ledger's --json digest
to a small local model (Ollama) and answers operator questions about
spending. Blocked on environment: requires Ollama with a Qwen3-4B-class
model on the Architect's machine — confirm availability before coding.
If Ollama is unavailable, the fallback per ARCHITECTURE.md is any cheap
API model, but local-first is preferred (cost of supervision rule).

Also pending: real traffic through the gateway (see operational item) —
without accumulated telemetry the Analyst has nothing to analyze, so
consider routing real traffic first.

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
