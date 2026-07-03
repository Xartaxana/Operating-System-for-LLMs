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

Test-traffic alias `lead-sonnet` (anthropic/claude-sonnet-5) added to
gateway/config.yaml for future Shadow Evaluation baselines, but unused
for now: no ANTHROPIC_API_KEY in this environment. Working set for
Shadow Evaluation instead generated via `intern` (Ollama, free): 6
requests across coding/summarization/extraction/classification/
formatting categories, logged in gateway/requests.db (38% context
repetition observed on this tiny sample — not meaningful yet, needs
volume).

Planned (not yet done): add Gemini and Groq free-tier aliases to
config.yaml for traffic diversity. Rationale: local Ollama traffic
alone can't validate delegation decisions against a real frontier
Lead — Gemini/Groq free tiers give real remote latency and real
provider pricing at $0, useful once comparing delegation candidates
against genuine frontier-Lead output (vs. `lead-sonnet` once a paid
key is available).

## Current Objective

Phase 1 step 5: Shadow Evaluation. gateway/shadow_eval.py is built and
tested (11 passing tests, no live model needed — mock_response like
test_analyst.py): samples successful requests for --source-model,
replays them on --target-model, compares via difflib similarity
(transparent heuristic, LLM judge deferred), aggregates by the same
task category metrics.py uses, and (--update-table) writes
validated/rejected verdicts into DELEGATION_TABLE.md + an evidence
log entry. Guards: refuses source==target (self-comparison is not
delegation evidence); a category stays "estimated" (inconclusive)
below --min-samples (default 2).

First real run completed 2026-07-03. Gemini free tier connected:
alias `lead-gemini` (gemini/gemini-2.5-flash; 2.0-flash has ZERO
free-tier quota on this key — 429, don't use it). Key lives in
gitignored gateway/.env; litellm did NOT auto-load it, export the
variable before starting the proxy. 10-request working set (2 per
category) replayed on `intern`; DELEGATION_TABLE.md now has its first
evidence-backed verdicts + a "Shadow Evaluation Log" section:
extraction 91% / formatting 60% / summarization 52% -> validated;
coding 10% / classification 4% -> rejected.

---

# Current Task (Authoritative)

Replace the difflib similarity heuristic in gateway/shadow_eval.py
with an LLM judge. The first real run (2026-07-03) showed the
heuristic is no longer sufficient: it produces false "rejected"
verdicts. Evidence: classification scored sim=4% although the answers
are likely semantically identical ("negative") — difflib compares
characters, so a verbose Qwen3 answer vs a terse Gemini answer scores
near zero even when the content is right. "validated" verdicts (high
similarity) are trustworthy; "rejected" ones are suspect and must be
re-checked by the judge before being treated as evidence.

Design constraints already anticipated in shadow_eval.py: the judge
slots in as a replacement for similarity()/decide_status inputs
without changing the pipeline; run it through the gateway under its
own alias (like analyst) so judge cost lands in the Ledger (Rule #1).
Candidate judges: `analyst` (local Qwen3-4B, free, may be too weak to
judge its own class) or `lead-gemini` (free tier, stronger, but
rate-limited and judging its own outputs on the source side — note
the self-preference bias).

Calibration set ready (2026-07-03): gateway/judge_calibration.json —
the 11 replay pairs manually labeled by Claude Fable 5 with verdicts
and rationales. Calibration procedure: run the automated judge on
these pairs and compare to the labels; it must reproduce them,
including the two difflib false rejections (coding) and the genuine
intern quality gap (classification pair 7). Manual review outcome
already applied to DELEGATION_TABLE.md: coding flipped to validated,
classification stays rejected with corrected rationale. No extra
data-gathering experiment needed before building the judge (D-0028
spirit); expand the set later with disagreement cases the judge gets
wrong. Groq (GROQ_API_KEY, free tier) is planned as a SEPARATE track:
a Middle-tier worker alias so "Routine code generation -> Middle" can
be tested against the tier the table actually names.

## Research Notes for Later Phases (2026-07-03)

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Context-repetition priors to confirm locally: 50–62% of spend is
  re-sent history, 30–40% of tokens are redundant.

This file is intended to be updated frequently.
