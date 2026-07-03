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
3. [x] Ledger: metrics.py daily digest — cost, task categories (keyword
   heuristics), context-repetition ratio, budget events; text + JSON output.
4. [x] Analyst: local small model (Ollama, Qwen3-4B) answering questions
   over Ledger output through the gateway under its own alias.
5. [~] Shadow Evaluation: shadow_eval.py built and tested; first real
   run 2026-07-03 (lead-gemini -> intern, 10 requests) produced the
   first evidence-backed DELEGATION_TABLE.md verdicts. LLM judge
   built and calibrated 11/11 (judge-groq = gpt-oss-120b via Groq
   free tier; replaced middle-groq, which mis-traced correct code).
   Remaining: traffic volume, middle tier as replay target, paid
   Lead baseline (see CURRENT_CONTEXT.md).

## Phase 2 — Routing and Compression (data-driven)

Entered only on evidence (D-0029, D-0033). The two workstreams have
separate gates because they attack different cost drivers; each gate
is computable from existing telemetry (requests.db, evidence log) —
no new infrastructure is needed to decide whether to build
infrastructure.

All thresholds below are initial calibrations (estimated up front per
the D-0028 pattern); revising one requires a DECISIONS.md entry with
rationale, not silent editing.

### Common gate (both workstreams)

- G1. ≥14 consecutive days of REAL traffic through the gateway.
  Synthetic working sets and replay/judge calls do not count
  (operational detail: real-vs-synthetic tagging in the log is part
  of the delegated task queue, see CURRENT_CONTEXT.md).
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

### Compression gate (the cost driver is confirmed locally)

- C1. Driver confirmed: Ledger context-repetition ratio ≥40% measured
  on real multi-turn traffic (external prior 50–62%; if local traffic
  shows materially less, compression is not our lever).
- C2. Substance: ≥20 real sessions of ≥5 turns in the G1 window
  (compression of single-shot traffic is meaningless).
- C3. Money on the table: re-sent context accounts for ≥25% of total
  accounted input spend over the G1 window.

First Compression task when the gate opens: evaluate LLMLingua-2 /
PCToolkit (token level) and Letta-style recursive summarization
(architectural) — validated by the existing Shadow Evaluation harness
(compressed vs. full context, judge rules equivalence); never
perplexity-compress code context without validation
(docs/RELATED_WORK.md).

### Phase transition procedure

When a gate's criteria are all green, the phase does not open
automatically: the gate report (numbers vs. thresholds) is written
into CURRENT_CONTEXT.md and the Architect signs the transition. The
first task of the opened workstream is always an evaluation of an
existing tool, never a build (D-0030).
