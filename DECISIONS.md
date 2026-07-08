# Decisions Log (index)

One line per decision — the operative statement. Full texts
(rationale, history, rule-10 answers): docs/DECISIONS_FULL.md,
point-read on demand (D-0051). A new decision adds both the index
line and the full text in the same commit; entry counts must match
(calibration check 12).

- D-0001 — Git is the single source of truth.
- D-0002 — English is canonical; Russian is a synchronized translation.
- D-0003 — Engineering over Perfection.
- D-0004 — Project = White Paper + Architecture Spec + Reference Implementation.
- D-0005 — Kernel independent of any specific LLM.
- D-0006 — Project memory is layered.
- D-0007 — Every document reachable from repository navigation.
- D-0008 — Every Patch leaves the repository consistent and navigable.
- D-0009 — Repository content overrides chat history.
- D-0010 — BOOT.md defines the canonical loading sequence.
- D-0011 — SYSTEM_PROMPT.md defines permanent behavioural rules.
- D-0012 — Every commit improves the repository as a knowledge system.
- D-0013 — Recurring practices are documented as repository protocols.
- D-0014 — No important knowledge remains only in chat history.
- D-0015 — Repository stores both knowledge and engineering processes.
- D-0016 — One commit = one conceptual change.
- D-0017 — Validate Before Elaborating.
- D-0018 — Infrastructure Before Features.
- D-0019 — Patch Format v2; large documents modified incrementally.
- D-0020 — Human assistance is a fallback mechanism.
- D-0021 — The repository is executable engineering memory.
- D-0022 — Success criterion: Zero Context Recovery Test.
- D-0023 — Every boot produces a standardized Boot Report.
- D-0024 — Phase 0 completes only after a passed ZCRT.
- D-0025 — Exactly one current engineering task at all times.
- D-0026 — Direct git commits are standard; patches are fallback.
- D-0027 — Supervision split Guard/Ledger/Analyst; supervision must cost less than it saves (Rule #1).
- D-0028 — Delegation driven by DELEGATION_TABLE.md: estimated up front, refined by Shadow Evaluation; no long measurement phase.
- D-0029 — Router deferred until Phase 1 telemetry shows what to route.
- D-0030 — Prefer existing open source; custom code only where none fits or it is the contribution.
- D-0031 — The LLM judge is a supervised worker: chief-judge audits, calibration set, upgrade only on measured degradation.
- D-0032 — Accounting prices, not cash prices; free tiers are cash discounts, not zero cost.
- D-0033 — Phase gates are telemetry-computable; gate report + Architect signature; first task of a new workstream is an evaluation, never a build.
- D-0034 — Claude Code subscription is the real Lead; transcripts are first-class telemetry, accounted at API list prices.
- D-0035 — Four-state delegation statuses: estimated / provisionally_validated / production_validated / rejected.
- D-0036 — Phase 2 workstream 2 is Context Management Evaluation; cache-aware accounting first, provider caching before lossy compression.
- D-0037 — Flat delegation: workers never spawn workers; decomposition/specs/acceptance belong to the coordinator; "decomposable" is an escalation category.
- D-0038 — CURRENT_CONTEXT.md holds live state only; closed work is archived to docs/task_reports/; boot context is a paid resource.
- D-0039 — Lead degradation is explicit, scoped, reversible: lead_degraded/lead_restored; no table/gate/DECISIONS changes while degraded.
- D-0040 — Workers are dispatched in the background by default; Lead availability is the scarcest resource.
- D-0041 — Subscription-contour delegation is opt-in: policy must auto-load (CLAUDE.md); agents alone are insufficient (F-1).
- D-0042 — Operator-initiated downward model switch is a lead_degraded trigger; calibration cross-checks declared models vs cc_usage.
- D-0043 — Fix the class, not the instance: name the class, sweep siblings per SIBLING_MAP, rule at the highest binding level.
- D-0044 — Restoration from degradation includes acceptance of the degraded window (journal + diffs) in lead_restored notes.
- D-0045 — Rejections are journaled (`rejected`, model required); two on one task at one tier make escalation mandatory.
- D-0046 — Information workers are accepted by trail, not trust: scout Trail block, spot-checked claims; critic's ACCEPT carries its own trail.
- D-0047 — Weekly calibration leaves a `calibrated` run record; checklist in PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md; Boot Report watches staleness.
- D-0048 — The sibling map is verified externally (liveness, recurrence rule) and shrinks as well as grows.
- D-0049 — Rule 10(c) is a lifecycle invariant: every mechanism has a REGISTERED failure detector, or it is not a mechanism.
- D-0050 — Session close is checked symmetrically to open: session-handoff skill at Session End; the next Boot Report detects skipped handoffs.
- D-0051 — Boot diet: DECISIONS.md is this index; full texts in docs/DECISIONS_FULL.md; CLAUDE.md operative-only; CURRENT_CONTEXT archived per D-0038.
