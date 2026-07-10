# Queue closures archive — 2026-07-10 (D-0038 pass)

Verbatim relocation of CLOSED queue items from CURRENT_CONTEXT.md
(archiving pass ordered by the operator 2026-07-10; boot context is
a paid resource). Each block below is the exact text removed from
CURRENT_CONTEXT.md; one-line pointers remain there. Evidence chains:
logs/routing-log.jsonl under the named task_ids.

## t-019 — quota_events digest line (DONE 2026-07-10)

- t-019 DONE 2026-07-10: quota_events narrated in the Ledger digest
  (gateway/metrics.py, mirror of the budget_events block; 159
  passed; critic skipped — pattern-mirroring diff, note in accepted
  event).

## GSD Pi adoption plan — A1 (DONE 2026-07-09)

  - A1 zero-tool-call guard — DONE 2026-07-09 (t-017, builder+critic
    ПРИНЯТЬ+Lead witness; commit with full rule-10 block). Known
    limitations accepted (critic F2/F3, LOW): prose tool_call_id
    could inflate later-turn counts; contradictory dual-source
    aggregate untested.

## GSD Pi adoption plan — A2 (DONE 2026-07-09; open remainders stayed in queue)

  - A2 quota walls — DONE 2026-07-09 (t-018, builder attempt 2 after
    critic ДОРАБОТАТЬ; absorbed B2; NO fallback chains adopted —
    exam integrity, walls block loudly instead). REMAINS QUEUED from
    the original item: Pi prompt-slimming evaluation (skills/tools
    trim) against the builder-groq 8k TPM ceiling; GSD budget-mode
    token profile as prior art. From t-018 review: metrics.py
    digest line for quota_events — DONE 2026-07-10 (t-019);
    requests(model,ts) index candidate stays queued (Rule #1: only
    on latency evidence — spent_today shares the full-scan cost).

  Post-closure note (2026-07-10, F-27): the wall's first live
  incident showed it counts requests.db only — side-DB traffic
  (t013.db) is invisible to it; reconciliation with provider
  rate-limit headers queued (OpenClaw item 2, trigger fired).
  See docs/FINDINGS.md F-27.

## GSD Pi adoption plan — B2 (FOLDED into A2, closed with it)

  - B2 — FOLDED into A2: gateway budget walls are the same commit
    class (litellm NATIVE budgets/rate-limits per alias; evidence:
    t-015 TPD exhaustion — 98.5k/100k burned by earlier tasks
    before the exam got one token out).

## OS boot-diet morning pass (DONE 2026-07-10; re-breach stayed in queue as the open item)

- OS boot-diet pass — DONE 2026-07-10 (breach at 2026-07-09 handoff:
  104,052; peaked 105,374): closed narrative archived per D-0038 to
  docs/task_reports/2026-07-09_pi-exams-and-adoption-closures.md;
  boot path now 97,511 bytes (< 100KB restored), CURRENT_CONTEXT
  27.7 -> 19.8KB. RE-BREACHED same evening (handoff measure 102,173
  bytes; +4.8%/session, growth explained: D-0066 + OpenClaw plan +
  Batch candidate).

## AO3 session-handoff skill port (t-021, DONE 2026-07-10)

- AO3 session-handoff skill — DONE 2026-07-10 (t-021, AO3 commit
  0911cf6): six-step evening check mirroring the OS skill over AO3's
  OWN morning path + Session Start detector rule in docs/HANDOFF.md;
  first dry-run caught three real transfer gaps (unpushed dd72c4d,
  a pre-task_id journal orphan of 2026-07-08, stale factory-status
  missing AT-BUG-007/008) — all resolved at acceptance. SIBLING_MAP
  axes 1/4 updated same move.
