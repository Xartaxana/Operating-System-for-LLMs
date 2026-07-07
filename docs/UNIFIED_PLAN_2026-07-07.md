# Unified Plan: Repository Roadmap + Claude Code Routing (2026-07-07)

Status: adopted 2026-07-07 (Architect decisions recorded this
session; D-0034, D-0035, D-0036). This document merges three inputs:

1. The repository state (Phase 1 nearly complete: Gateway, Guard,
   Ledger, Analyst, Shadow Evaluation with a 13/13-calibrated judge).
2. The external review of context management
   (EXTERNAL_REVIEW_CONTEXT_MANAGEMENT_2026-07-04.md).
3. The external plan "smart model routing and limit transparency"
   (EXTERNAL_PLAN_CLAUDE_CODE_ROUTING_2026-07-07.md, dated
   2026-07-07).

## 1. Comparison: which decisions win where

The two plans attack the same problem — the strongest model burns
its budget on work that does not need it — on different substrates.
Neither replaces the other; each is strongest where the other is
weakest.

### Kept from the repository (the external plan loses here)

| Decision | Why it wins |
|---|---|
| Evidence-based delegation (D-0028, Shadow Evaluation, calibrated judge) | The external plan's T0–T3 table is assigned by feel; its Phase 3 ("калибровка по фактам") re-invents Shadow Evaluation weekly and by hand. The repository already has the working validation machine, including a judge whose own reliability is measured (13/13). |
| Rule #1 + accounting prices (D-0027, D-0032) | The external plan names the risk ("оркестратор тоже тратит") but has no mechanism. The repository accounts supervision cost everywhere, including the judge, and prices free tiers/subscriptions at list prices. |
| Process discipline (DECISIONS.md, gates D-0033, retraction of contaminated data, judge protocol) | The external plan has none; its "статус: утверждён" is exactly the kind of chat-level authority D-0009 rejects. |
| Deterministic Guard | The external plan has reports only, no enforcement. (On the subscription contour enforcement is impossible anyway — see conflicts.) |

### Adopted from the external plan (the repository loses here)

| Decision | Why it wins |
|---|---|
| Claude Code transcripts as the telemetry source | The repository meticulously accounts $0.0004 Groq calls while the operator's actual expensive resource — subscription limits (Fable/Opus) — is completely unmeasured. Gate G1 had ZERO real traffic and no realistic path to any: the real Lead cannot be routed through the LiteLLM proxy. Transcripts are the real traffic. Verified 2026-07-07: they carry model, usage, cache_read/cache_creation tokens, per-session files. |
| Tiered subagents (scout=Haiku, builder=Sonnet, critic=Opus) | Immediately actionable delegation substrate for the operator's daily work; the repository's Intern/Junior/Middle hierarchy had no execution surface on the subscription side. Subagents also isolate context (the Lead session reads a digest, not file dumps). |
| Escalation journal as the evidence stream | On the subscription contour replay is impossible, so Shadow Evaluation cannot run there. Acceptance verdicts + escalations are the measurable substitute, and they double as preference data for a future Router (converges with what RouteLLM needs). |
| "Optimize Claude Code first, extract a system later" | Matches Engineering over Perfection; the gateway contour stays the reference implementation and the lab. |

### Conflicts and their resolutions

1. T0–T3 table "утверждена" vs D-0028/D-0035: resolved — every
   routed category enters DELEGATION_TABLE.md as `estimated` and is
   promoted only on evidence. The table rows exist as of 2026-07-07.
2. "Полностью автоматический роутинг с первого дня" vs D-0029
   (Router deferred): resolved — CLAUDE.md routing policy executed
   by the Lead session is not the deferred Router (no new inference
   infrastructure); the Router build decision still waits for the
   Phase 2 gate. The policy's aggressiveness is calibrated by the
   escalation journal.
3. Two telemetry silos (transcripts vs requests.db): resolved —
   one Ledger. usage_report.py writes normalized per-request rows
   into the same SQLite database (separate table, see spec), and
   reports read both. Session/turn identity comes free from
   transcripts and lands in the schema per the external review's
   recommendation #3.
4. External plan's `tools/usage_report.py` vs existing `metrics.py`:
   resolved — usage_report.py is a Ledger component, not a silo; the
   Phase 2 readiness digest (Delegated Task 3) reads both sources.

## 2. Merged architecture: two contours, one discipline

```
Subscription contour (the real Lead)          API contour (the lab)
Claude Code (Fable) --delegates--> subagents  Gateway (LiteLLM)
  scout=Haiku  builder=Sonnet  critic=Opus      intern/analyst/middle/judge aliases
        |                                             |
   transcripts ~/.claude/projects/**.jsonl       sqlite callback (traffic_kind)
        |                                             |
        +----------> one Ledger (SQLite + reports) <--+
                          |
              DELEGATION_TABLE.md (4-state, D-0035)
              evidence: escalation journal | Shadow Evaluation + judge
                          |
                  Architect signs gates (D-0033)
```

The discipline (Rule #1, accounting prices, evidence-gated statuses,
judge supervision) is identical on both contours; only the
measurement mechanism differs (acceptance/escalation vs replay/judge).

## 3. Plan of record

### Done 2026-07-07 (this session)

- Lead review of delegated tasks 1–2: ACCEPTED, 4 findings folded
  into Delegated Task 4 (see CURRENT_CONTEXT.md).
- D-0034..D-0036 recorded; ROADMAP Phase 1.5 added; C-gate made
  cache-aware; DELEGATION_TABLE moved to the 4-state model.

### Near-term queue (order matters; each step reviewed before the next)

1. Delegated Task 4 — test isolation + review follow-ups
   (spec in CURRENT_CONTEXT.md). Protects telemetry integrity first.
2. Delegated Task 5 — tools/usage_report.py baseline (spec in §4
   below). Deliverable: baseline report over existing transcript
   history BEFORE routing changes behavior — this is the external
   plan's Phase 0 and the measurement foundation for everything else.
3. Delegated Task 3 — Phase 2 readiness digest in metrics.py
   (spec in CURRENT_CONTEXT.md), now able to see both sources.
4. Claude Code routing (external plan Phase 1, repository ROADMAP
   Phase 1.5 step 2): .claude/agents/scout|builder|critic.md with
   model frontmatter, routing policy + escalation rule in CLAUDE.md,
   delegation journal hook (logs/routing-log.jsonl). Lead-tier task:
   policy wording decides real behavior; needs Architect acceptance
   of the policy text.
5. Weekly calibration loop (Phase 1.5 step 3): review escalation
   journal + usage report; upgrade/downgrade table rows on evidence;
   adjust policy. First loop after >=1 week of routed traffic.
6. Context Management Evaluation spec (D-0036, external review
   recs #1, #4, #5, #11): written only after the baseline report
   exists — the report's cache fields decide whether compression is
   even our lever (C3 net of caching).

### Deferred, unchanged

- Router build: waits for the Phase 2 R-gate (D-0029, D-0033).
  RouteLLM evaluation first, now with an AutoMix-style
  "small first, escalate on failed judge" baseline for comparison
  (external review, Routing and Cascades).
- Judge audit escalation ladder from the external review: adopt into
  PROCESS/JUDGE_CALIBRATION_PROTOCOL.md when judged runs resume on
  the API contour (no judged runs are planned until then).
- Graph memory, vector stores, custom compression: not before their
  gates (Non-Goals, external review).

## 4. Spec: Delegated Task 5 — tools/usage_report.py

Intended executor: CHEAPER model session (Middle-class; routine
build to a written spec). Reviewed by Lead/Architect before task 3
starts. Rules the executor must follow: verify data shapes
empirically against real transcript files before trusting this spec
(the lesson of tasks 1–2); escalate blockers, do not improvise
around them.

1. Input: `~/.claude/projects/*/*.jsonl` (one file per session;
   directory name encodes the project path). Each assistant message
   line carries `message.model` and `message.usage`
   (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
   `cache_read_input_tokens`) — verified live 2026-07-07 on this
   machine. Skip `model == "<synthetic>"` rows (harness-internal).
   Deduplicate by message `uuid`/`requestId` if replayed lines occur
   (VERIFY empirically whether they do).
2. Normalization: one row per assistant API turn into a new
   `cc_usage` table in the gateway SQLite database (do not touch the
   `requests` table): ts, project, session_id, turn_index, model,
   input_tokens, output_tokens, cache_creation_tokens,
   cache_read_tokens, accounted_cost_usd, traffic_kind='real'.
   Import is idempotent (re-running over the same transcripts must
   not duplicate rows).
3. Accounted cost (D-0032, D-0034): API list prices per model,
   including the cache write/read price distinction. Prices live in
   one obvious dict with a source comment; unknown models get
   cost=None and a WARNING in the report — never a silent $0
   (Rule #1).
4. Report (`python tools/usage_report.py --days 7`, text + --json):
   totals and per-day / per-model / per-project / per-session
   breakdowns of tokens and accounted cost; cache economics
   (cache_read share of input; accounted savings vs uncached price);
   top-5 sessions by cost. This is the external plan's baseline
   report, cache-aware from day one per D-0036.
5. Tests: parser on a small fixture transcript checked into
   tests/fixtures (sanitized), idempotent import, price math
   including cache rates, unknown-model warning path. No network, no
   LLM calls.
6. Non-goals for this task: no routing hook, no scheduler, no
   Anthropic Usage API (API-key accounting joins later on the API
   contour where the gateway already measures it).

Acceptance: baseline report over the operator's real transcript
history runs in one command and its per-model totals are spot-checked
against 2–3 transcript files by hand during review.

## 5. Non-goals of the merge

- No second source of truth: the external plan file itself is an
  input document; this plan and ROADMAP.md govern (D-0009).
- No enforcement on the subscription contour (nothing to enforce
  programmatically; Guard stays on the API contour).
- No LLM call per routing decision (external plan §7 is right):
  policy rules are static text the Lead follows; their calibration
  is the weekly loop, not per-request inference.
- No transcript content leaves the machine: usage_report.py reads
  token counts and metadata, not message bodies, and its reports
  contain no prompt text.
