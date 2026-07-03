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

LLM judge DONE (2026-07-03). shadow_eval.py gained --judge-model
(judge through the gateway; verdicts override difflib in
decide_status via pass_rate >= --pass-threshold, default 0.75),
--calibrate (agreement report against judge_calibration.json), and
per-pair verdict logging. 31 tests pass.

Calibration history: middle-groq (Llama-3.3-70B via Groq free tier)
agreed 10/11 and was adopted 2026-07-03, then REPLACED the same day —
see below. lead-gemini as judge is impractical: free tier is 5
req/min (verified 429) and it would judge its own source answers
(self-preference bias). analyst (4B) not evaluated — no need while
Groq is free.

JUDGE UPGRADE (2026-07-03, later session): the fibonacci miss was NOT
strictness — diagnosis (asking the judge to explain) showed
Llama-3.3-70B hallucinates a bug while "tracing" the correct
`a, b = b, a + b` loop (claims the code returns b; it returns a).
Prompt hardening (judge only the explicit task; step-by-step check
before claiming a bug) did not flip it — a capability ceiling, not a
prompt problem. The hardened prompt was kept, and the judge was
upgraded: alias `judge-groq` = groq/openai/gpt-oss-120b (reasoning
model, same free Groq key), screened directly against the calibration
set (gpt-oss-120b 11/11; qwen3-32b 7/11 with rate-limit errors and a
real miss on pair #7), then officially calibrated through the gateway:
11/11. ADOPTED as default judge. judge-groq is a role alias (never a
traffic source), so judge cost stays separable in the Ledger and the
contamination filter has a second line of defense.

Judged runs done (2026-07-03), with two process lessons the hard way:

1. CONTAMINATION: the first judged run sampled 6/11 nested judge
   prompts — the failed lead-gemini calibration had logged its judge
   calls as regular lead-gemini traffic. Caught only because the
   Architect asked whether the chief judge (Claude) had reviewed the
   run. Fixed: sample_requests() excludes judge calls (prompt LIKE
   filter + test); contaminated log lines marked [RETRACTED].
2. JUDGE BIAS — RESOLVED (2026-07-03): root cause was middle-groq
   mis-tracing correct code, not strictness (see JUDGE UPGRADE above).
   Judge replaced with judge-groq (gpt-oss-120b), calibration 11/11.
   Lesson: when a judge misses, ask it to explain before tuning the
   prompt — the stated theory ("penalizes missing validation") was
   wrong, and two prompt fixes aimed at it changed nothing.

Process rule going forward: judge verdicts that CHANGE a table status
get a chief-judge (or Architect) review of the actual pairs before
the change is accepted; --update-table output is not self-certifying.
Extended 2026-07-03 into PROCESS/JUDGE_CALIBRATION_PROTOCOL.md
(D-0031): reviews grow judge_calibration.json, 1-2 random verdicts
audited per run, recalibration every ~5 new pairs, judge model
upgraded only on measured agreement drop below 90%.

Protocol applied same day: the two chief-judge-reviewed pairs from
the coding->middle-groq run appended to judge_calibration.json (now
13 pairs). First recalibration exposed verdict nondeterminism at
default temperature (borderline pair #7 flipped between runs:
11/11 -> 12/13); judge_pair now defaults to temperature=0.
Current baseline: judge-groq 13/13, reproduced twice.

DONE (2026-07-03): "Routine code generation -> Middle" tested with
middle-groq as TARGET, judge-groq as judge: n=2, pass_rate=1.00,
chief-judge review confirmed both pairs -> row validated with
tier-matching evidence (earlier evidence used intern as a stand-in).
shadow_eval.py gained --categories (whitelist) so a run aimed at one
row cannot update rows whose Delegate-to tier differs from the
target. 33 tests pass.

Next: (a) grow real traffic volume (n=2 per category is thin);
(b) once ANTHROPIC_API_KEY exists, repeat against the true paid Lead.

## Research Notes for Later Phases (2026-07-03)

Recorded in docs/RELATED_WORK.md and DELEGATION_TABLE.md
("External Evidence"); key operational implications:

- Phase 2 Router: evaluate RouteLLM (open source, OpenAI-compatible)
  before building our own; it trains on preference data the Ledger and
  Shadow Evaluation will produce.
- Context-repetition priors to confirm locally: 50–62% of spend is
  re-sent history, 30–40% of tokens are redundant.

This file is intended to be updated frequently.
