# 2026-07-08 — Routing dogfooding day (archived from CURRENT_CONTEXT, D-0038/D-0051)

Verbatim narrative moved out of the boot path. Closed items only;
live consequences remain in CURRENT_CONTEXT.md.

## Interim read after first routed ~18h (NOT the weekly loop — no status moves)

Journal 5 delegated / 4 accepted / 0 escalated, all
category=implementation (builder). Transcripts: sidechain 406 turns,
all sonnet-5, $19.05 ($0.047/turn) vs Lead main chain $0.242/turn —
63% of window turn volume ran off-frontier at 28% of window spend.
Journal-vs-transcript cross-check consistent on tier, but three
leaks: (a) 'model' field missing on all 5 delegated events (AO3's
log_append.py now enforces it); (b) one delegated (badge, 00:15) has
no accepted event — reconcile; (c) /qa-loop dispatches still
unjournaled (known), so the 406 sidechain turns >> the 5 journaled
delegations. scout and critic: ZERO dispatches at that point.
Router implications (D-0029): all observed dispatch was ONE
deterministic rule (scoped implementation -> sonnet) and zero
escalations = zero boundary data; a router trained on this would
learn "always sonnet", which a static rule already does. Router
stays deferred; the informative events are escalations and category
diversity.

Both interim action items CLOSED same day (operator-directed
"telemetry first, then revive tiers"):

1. TELEMETRY GAPS -> Delegated Task 7 ACCEPTED (commit 2f026f0,
   archived: task-7_agent-attribution.md). agent_id/agent_type live
   in cc_usage (1759/1759 sidechain rows attributed; per-line field
   is attributionAgent, NOT agentType — spec errata), haiku 4.5
   priced, 0 NULL-cost rows. Process firsts: delegation journaled at
   dispatch time in THIS repo, acceptance ran through a critic (Opus)
   dispatch — first critic evidence (ПРИНЯТЬ, 0 correctness
   findings, consistent with independent Lead verification).
2. DEAD TIERS REVIVED by policy (commits 3736ecd here, e32d955 AO3):
   rule 1 — scout is the DEFAULT for recon; rule 3 — critic verdict
   is a mandatory acceptance input for large/core diffs and unclear
   bugs; acceptance stays with the Lead (D-0037).

Note on test-reviewer.md (AO3): resolved — a parallel AO3 session
assigned it model: opus (all 13 AO3 agents carry a model; verified
2026-07-08).

## D-0043 adoption (operator directive; finding F-10)

"Fix the class, not the instance" — constitution level
(SYSTEM_PROMPT.md), rule 9 in both deployments' CLAUDE.md,
builder/critic role duties in both. Sweep remainder queued: the
"report sibling defects" line for the nine AO3 QA-pipeline agent
prompts on their next touch.

## First live verification (2026-07-07) and journal-gap closure

Routing WORKS: fresh AO3 session dispatched test-maintainer on
sonnet-5 (isSidechain=true), Lead stayed on Fable. The journal gap
(dispatch via /qa-loop wrote no delegated event) CLOSED 2026-07-08:
/qa-loop SKILL.md journals delegated/accepted/escalated via
log_append.py (AO3 commit a2cc949). The telemetry bug (subagent
transcripts invisible to cc_usage) was fixed as Task 6 (ACCEPTED
2026-07-08): sidechain traffic counted — 7.2% of all tokens, $100.03
accounted, of which AO3_tests $57.82; the AO3 retro baseline
($276.70) self-corrected upward by that amount.

DOGFOODING NOTE: Task 6 was the first task dispatched to a live
Claude Code subagent (Sonnet builder, background, D-0040), accepted
on first review — first "builder" row evidence (n=1). Dispatch was
manual because the routing policy was not yet deployed here — fixed
same day.

## Routing MVP deployed to THIS repo (reference/dogfooding, second after AO3)

Added: CLAUDE.md (routing policy, journal format, degradation,
permission hygiene adapted to this repo), .claude/agents/
{scout,builder,critic}.md, logs/routing-log.jsonl (seeded
journal_created + lead_degraded).

## F-1 recorded and formalized

The default Claude Code harness does NOT initiate delegation on its
own; left alone, the Lead does delegable work itself on the most
expensive tier. Formalized after restore: D-0041 (deploying routing
= auto-loaded policy + tier agents + journal, always together),
D-0042 (operator-initiated downward switch is a lead_degraded
trigger; telemetry cross-check backstops unjournaled switches).

## First degradation cycle complete

Operator switched Fable->Opus 4.8 via /model and back (~5 min
window). Full D-0039 cycle in logs/routing-log.jsonl (lead_degraded
-> lead_restored); while degraded only authorized work was done
(routing deploy + F-1 record, commit 7f60273), decisions deferred
and adopted after restore. Deployment divergence found and fixed:
operator-switch trigger wording was missing from the AO3 CLAUDE.md.

## Mechanism day (operator questions F-12..F-16 -> D-0044..D-0051)

Eight operator questions in one day, each exposing an unverifiable
mechanism (pattern F-11): degraded-window acceptance (F-12/D-0044),
rejected events + escalation trigger (F-13/D-0045), trail-based
acceptance of information workers (F-14/D-0046; first live scout
dispatch executed the full cycle same day), calibration run record +
Boot Report watcher (F-15/D-0047), sibling-map verification
(F-16/D-0048), rule 10(c) as lifecycle invariant (D-0049),
session-handoff skill (D-0050), boot diet (D-0051). Evals priors
from two Habr articles digested into RELATED_WORK; two-stage eval
adoption plan queued.
