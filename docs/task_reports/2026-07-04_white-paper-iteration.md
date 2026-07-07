# White Paper Iteration and Phase 2 Gates (2026-07-04)

Archived verbatim from CURRENT_CONTEXT.md on 2026-07-07 (D-0038).
Live remainder (White Paper §7 upkeep, Architect review, sync with
D-0034..D-0037) stays in CURRENT_CONTEXT.md's Lead-tier queue.

---

# Previous Lead-tier task (2026-07-04): White Paper iteration

Lead-tier task, prioritized by the Architect 2026-07-04 ("actions
that need the strongest model first"). Draft v0.1 of WHITE_PAPER.md
written 2026-07-04 (deliverable #1 of PROJECT_CHARTER.md): problem,
supervision decomposition, evidence-based delegation, the judge as a
supervised worker (capability tracks hierarchy: 4B 11/13, 70B 12/13,
120B 13/13), accounting prices, repository-as-memory/self-hosting,
positioning, honest empirical status (§7) and limitations. Next
iterations: keep §7 synchronized with the evidence log; add the
context-repetition section once local telemetry confirms or refutes
the 50-62% prior; Architect review of the draft.

DONE (2026-07-04): Phase 2 entry criteria defined (ROADMAP.md,
D-0033) — common gate (14 days real traffic, calibrated judge),
router gate (R1-R5: evidence volume, >=25% delegable share of
accounted Lead spend, mix stability, 3x economics, paid-Lead or
sign-off), compression gate (C1-C3: >=40% repetition confirmed
locally, >=20 multi-turn sessions, >=25% of input spend re-sent).
Green gate -> written report -> Architect signs; first task is
always an evaluation, never a build. Summarized in White Paper §10.

DONE (2026-07-04): White Paper §7/§10 synchronized after the
traffic_kind and Rule #1 cost-accounting implementation commits:
WHITE_PAPER.md now states that the hardening is implemented and
self-tested, but still awaiting Lead/Architect review before being
treated as signed process evidence. Canonical source range updated
to D-0001..D-0033.

DONE (2026-07-04): External review report recorded in
docs/EXTERNAL_REVIEW_CONTEXT_MANAGEMENT_2026-07-04.md and linked from
README.md + docs/README.md so it is discoverable after a fresh boot.
Key review recommendation: treat Phase 2 as Context Management
Evaluation, not only compression; evaluate provider prompt caching,
cache-aware Ledger accounting, session/turn identity, structured
compaction, retrieval/memory and memory governance under Rule #1.
