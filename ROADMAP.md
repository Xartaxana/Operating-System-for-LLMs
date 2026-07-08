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

## Phase 1.5 — Real Telemetry and Claude Code Routing (D-0034)

The operator's real Lead is the Claude Code subscription; this
workstream measures and routes that traffic. Merged from the external
plan 2026-07-07 (docs/UNIFIED_PLAN_2026-07-07.md, which holds the
detailed specs and acceptance criteria). Like Phase 1, every step is
useful on its own:

1. [ ] Baseline telemetry: tools/usage_report.py parses Claude Code
   transcripts into per-day / per-model / per-session / per-project
   token and accounted-cost reports, cache-aware from day one
   (input vs cache_read vs cache_creation tokens — the fields exist
   in transcripts, verified 2026-07-07). First deliverable: a
   baseline report over the existing transcript history, BEFORE any
   routing changes behavior.
2. [~] Routing in Claude Code: tiered subagents (scout=Haiku,
   builder=Sonnet, critic=Opus), routing policy + escalation rule in
   the project CLAUDE.md, delegation journal. Every routed category
   enters DELEGATION_TABLE.md as `estimated` (D-0028, D-0035); the
   escalation journal is its evidence stream. DEPLOYED 2026-07-07 as
   a pilot on the operator's second project (D:\AO3_tests) and
   2026-07-08 on this repository itself (reference deployment,
   D-0041), including Lead degradation/restore (D-0039/D-0042),
   universal skip events, class-fix discipline with the sibling map
   (D-0043) and /qa-loop journaling; builder/critic tiers have first
   accepted evidence (Tasks 6-7), agent-attributed telemetry live
   (cc_usage agent_id/agent_type). Remaining: >=1 week of routed
   traffic incl. scout dispatches, then step 3's first loop.
3. [ ] Weekly calibration loop: escalation journal + usage report
   reviewed, table statuses upgraded/downgraded on evidence, routing
   rules adjusted. This is Shadow Evaluation's philosophy applied to
   the subscription contour (replay is impossible there; acceptance
   verdicts and escalations are the measurements). Executable
   checklist: PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md; each run ends
   with a `calibrated` journal event, staleness is surfaced by the
   Boot Report's Last Calibration line (D-0047).

This workstream is NOT the deferred Router (D-0029): routing policy
is executed by the Lead session itself following documented rules,
no new inference infrastructure. The Router build decision still
waits for the Phase 2 gate.

## Phase 2 — Routing and Context Management Evaluation (data-driven)

Entered only on evidence (D-0029, D-0033). The two workstreams have
separate gates because they attack different cost drivers; each gate
is computable from existing telemetry (requests.db, evidence log) —
no new infrastructure is needed to decide whether to build
infrastructure.

All thresholds below are initial calibrations (estimated up front per
the D-0028 pattern); revising one requires a DECISIONS.md entry with
rationale, not silent editing.

### Common gate (both workstreams)

- G1. ≥14 consecutive days of REAL traffic: the operator's actual
  working traffic, measured at the gateway (traffic_kind='real') or
  from Claude Code transcripts (D-0034). Synthetic working sets and
  replay/judge calls never count. Transcript history may satisfy G1
  retroactively once usage_report.py can compute it.
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

### Context management gate (the cost driver is confirmed locally)

Reframed per D-0036: the workstream is Context Management Evaluation
(provider caching, compaction, retrieval/memory, semantic caching),
not compression alone. All C-criteria are measured CACHE-AWARE: what
matters is paid uncached re-sent input, not raw repetition.

- C1. Driver confirmed: context-repetition ratio ≥40% measured on
  real multi-turn traffic (external prior 50–62%; if local traffic
  shows materially less, this lever is not ours).
- C2. Substance: ≥20 real sessions of ≥5 turns in the G1 window
  (compression of single-shot traffic is meaningless).
- C3. Money on the table: PAID UNCACHED re-sent context accounts for
  ≥25% of total accounted input spend over the G1 window (context
  already served from provider cache is not on the table).

First task when the gate opens (evaluation order fixed by D-0036):
provider prompt caching measurement first; only if C3 stays green
net of caching, evaluate LLMLingua-2 / PCToolkit (token level) and
Letta-style recursive summarization (architectural) — validated by
the existing Shadow Evaluation harness (compressed vs. full context,
judge rules equivalence); never perplexity-compress code context
without validation (docs/RELATED_WORK.md).

### Phase transition procedure

When a gate's criteria are all green, the phase does not open
automatically: the gate report (numbers vs. thresholds) is written
into CURRENT_CONTEXT.md and the Architect signs the transition. The
first task of the opened workstream is always an evaluation of an
existing tool, never a build (D-0030).
