# Roadmap

Closed phases live in the archive per D-0038/D-0078 (boot-diet
round 11): full closure narratives, gate reports and evidence moved
VERBATIM to docs/task_reports/2026-07-15_roadmap-closed-phases.md;
each closed phase keeps a status pointer here. Live gates stay in
this file.

## Phase 0 — Foundation — CLOSED

All items [x]; exit criterion (Zero Context Recovery Test) passed
2026-07-03. Checklist:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 1 — Supervised Lead (MVP) — CLOSED 2026-07-11

All five steps (gateway, guard, ledger, analyst, shadow evaluation)
done with evidence; closed together with Phase 1.5, Architect
signature 2026-07-11. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 1.5 — Real Telemetry and Claude Code Routing (D-0034) — CLOSED 2026-07-11

Baseline telemetry, tiered routing deployed on both repos, weekly
calibration loop — the loop continues as a STANDING OPERATION, not
phase work. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 2 — Routing and Context Management Evaluation — CLOSED 2026-07-23

All four workstreams decided with evidence: common gate met 07-13
(G1 16/14, G2 13/13); context management closed by direct
measurement 07-13 (C3 0.11% vs ≥25%); task pipeline closed by
adoption D-0080 (07-18); Router opened 07-21 on the D-0086 revision
and CLOSED 2026-07-23 after the clean check-30 audit of calibration
#4 (8/8 judge-basis acceptances leaf-class, no judge hallucinations,
economics in Rule #1's favor) — leaf routing promoted to the kernel
default (D-0094); all six LLM-router candidates stay rejected by
evidence. Phase closure signature — Architect, in session
2026-07-23: «закрытие фазы 2 подтверждаю». Reopen triggers of the
deferred parallelism/isolation class moved to CURRENT_CONTEXT's
evidence-gated queue by this closing commit (F-48/D-0082 class).
Full narrative, gate decisions and criteria:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase transition procedure (standing)

When a gate's criteria are all green, the phase does not open
automatically: the gate report (numbers vs. thresholds) is written
into CURRENT_CONTEXT.md and the Architect signs the transition. The
first task of the opened workstream is always an evaluation of an
existing tool, never a build (D-0030).

## Phase 3 — Toolkit (D-0070) — CLOSED 2026-07-12

All six stages closed with evidence (intake t-044, packaging
decisions В1–В6, core spec v0, skeleton, both validation installs,
public wrap); the toolkit is public and released:
github.com/Xartaxana/Supervised-Delegation, tag v0.1.0 (latest
release: v0.5.0, 2026-07-23). Operator direction in session;
residuals live in CURRENT_CONTEXT's queue on their own evidence
triggers. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 4 — Hardening for Delivery (D-0098) — OPEN 2026-07-24

Opened by the operator's word in session 2026-07-24: finish every
tail and close POTENTIAL holes so the delivery is complete — the
priority shifts from building ourselves on our own violation
statistics to hunting holes no future user should ever hit
(promotion default flip for the delivered product, D-0098; D-0063
stays for staff-internal mechanisms). Entry evaluation (D-0033 —
first task is an evaluation, never a build): the 2026-07-24
enforcement-gap audit, t-312..t-315,
docs/task_reports/2026-07-24_enforcement-gap-audit.md.

Workstreams (live; execution queue in CURRENT_CONTEXT):

1. Stale-line hygiene — CURRENT_CONTEXT rewrite of the four audited
   stale items (audit §1).
2. Kit completeness — port batch t-316 (wiring_check code for
   D-0092, hygiene v3, journal_echo ts-drift/warn_stale,
   judge_prompt_pin, corpus rule, t-278 gate set in
   exam_fullgates_kit) + INSTALL escape-allowlist step.
3. E-layer closures (audit §2/§3): E1 escalation guard (attempt≥3
   without escalated → machine signal at write time), E4
   builder-role tools narrowing (both deployments + kit twin);
   remaining E-items get recorded "held by discipline" lines with
   named detectors (D-0064 form).
4. Re-audit and release — clean audit re-pass, then a kit minor via
   the kit-release skill (D-0097).

Gate (exit criteria):
(а) "promised by delivery, no code behind it" class = 0 (D-0092
    class closed and swept);
(б) every norm in the enforcement map carries either a machine
    layer or a recorded "held by discipline" line with a named
    detector (D-0064 form) — no unclassified gaps;
(в) a kit minor carrying the full port set is released through
    kit-release (D-0097);
(г) a re-pass of the enforcement-gap audit is clean; Architect
    signature closes the phase (standing procedure).
