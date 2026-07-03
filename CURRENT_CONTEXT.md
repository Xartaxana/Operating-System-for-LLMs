# Current Context

## Current Milestone

Phase 1 — Supervised Lead (MVP), step 5: Shadow Evaluation.

## Current Status

Phase 0 closed 2026-07-03. Phase 1 steps 1–4 built and verified:

- Gateway (step 1): LiteLLM proxy + SQLite request logging.
- Guard (step 2): daily per-model budgets, warn 80% / refuse 100%.
- Ledger (step 3): metrics.py daily digest (text/JSON).
- Analyst (step 4): analyst.py feeds the Ledger digest to a local
  Qwen3-4B (Ollama) through the gateway under its own alias, so
  supervision cost is accounted separately. Verified live: answered
  a Russian operator question from real telemetry. Answer quality is
  Intern-class (numbers occasionally garbled) — acceptable for MVP,
  prompt to be tuned on real telemetry.

Free-telemetry mode is in place (no paid keys needed): local models
`intern` and `analyst` (Ollama Qwen3-4B) run through the gateway with
synthetic Haiku-class per-token prices, so Guard/Ledger money paths
work at $0. `lead` (Anthropic API, paid) stays optional.

Environment notes (this machine): Ollama 0.31.1 installed via winget.
NVIDIA driver updated 560.94 → 582.28 (last Pascal security branch),
which fixed the Ollama CUDA PTX error: Qwen3-4B now runs 100% on the
GTX 1060 GPU, warm requests ~5 s vs ~15 s on CPU. Proxy must be
started from gateway/ (callback imports are cwd-relative).

Open operational item (Architect): route real traffic through the
gateway to accumulate telemetry (free via intern/analyst;
lead needs ANTHROPIC_API_KEY, paid).

## Current Objective

Phase 1 step 5: Shadow Evaluation — replay sampled requests on cheaper
models, compare outputs, update DELEGATION_TABLE.md with evidence
(see ARCHITECTURE.md, "Shadow Evaluation"; D-0028).

---

# Current Task (Authoritative)

Implement Shadow Evaluation: a script that samples logged requests
from requests.db, replays them on a cheaper model (start with
intern = local Qwen3-4B, free), and compares outputs (heuristics
first; LLM judge later). Results update DELEGATION_TABLE.md row
statuses per its update rules — including rule 4: compare TOTAL task
cost, counting retry loops. Prerequisite: some real traffic in the
log; if the log is still empty, generate a small working set by
routing this project's own tasks through the gateway first.

## Research Notes for Later Phases (2026-07-03)

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Context-repetition priors to confirm locally: 50–62% of spend is
  re-sent history, 30–40% of tokens are redundant.

This file is intended to be updated frequently.
