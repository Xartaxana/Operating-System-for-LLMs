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
github.com/Xartaxana/Supervised-Delegation. Releases after closure:
v0.5.0 (07-23), v0.6.0 (07-30), v0.7.0 and v0.8.0 (08-10), v0.8.1
(08-10) — current. The delivery FILTER changed at v0.8.0 (D-0101):
the kit is a mirror of the staff branch minus development traces,
not a road-tested-only subset. Residuals live in CURRENT_CONTEXT's
queue on their own evidence triggers. Full narrative:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 4 — Hardening for Delivery (D-0098) — CLOSED 2026-07-30

All four workstreams done (07-24) and all four gate criteria passed:
(а)+(б)+(г) 07-24 re-audit t-319..t-321; (в) 2026-07-30 — kit minor
v0.6.0 released through kit-release (public 02bac45 + tag, staff
snapshot aa725e6, cycle t-344..t-346). Closure signature —
Architect, in session 2026-07-30: «подтверждаю закрытие фазы 4».
Full narrative and gate report:
docs/task_reports/2026-07-15_roadmap-closed-phases.md.

## Phase 5 — Norm Corpus (Нормативный корпус) — CLOSED 2026-08-20

Opened by the Architect's word in session 2026-08-18. The predecessor
section here («After Phase 4», 2026-08-16) recorded the basis as a
fact before the phase existed: the work that arrives now is CLASSES,
not components — the artifacts that grow are docs/FINDINGS.md, the
failure-mode register in docs/SIBLING_MAP.md and the calibration
checklist. The opening measurement (2026-08-18, deterministic git
run) confirmed and widened it: the normative corpus without an owner
or a retirement rule grew ~320 KB → ~904 KB in 38 days (×2.8), the
growth is INTO existing entries rather than by new ones (checks 33→34
while checklist bytes ×1.9 over the same window), and the costliest
byte is CLAUDE.md — auto-loaded by every session, +42% in 20 days.
Contrast held by the controlled artifacts: CURRENT_CONTEXT under the
D-0038 diet (38.9→19.7 KB), DELEGATION_TABLE flat, the boot path
under its 100 KB threshold — diet works where it exists.

Scope — make the norm corpus scale the way the boot path already
does: (W0) measure the supervision loop itself first (D-0030: the
first task is an evaluation with existing instruments, never a
build); (W1) every normative artifact gets an owner and a retirement
rule, or an explicit refusal line; (W2) registry form instead of
prose — norms as keyed rows grouped by problem/data source, full-text
rationale with its owner, the calibration checklist dispatched by
window-applicability instead of read linearly; (W3) a growth detector
for the class itself plus a standing calibration check (Architect's
word 2026-08-18): thematic layout holds, diets execute AND pay for
themselves, files have not grown against their own header rules and
our expectations. Node statuses, baseline numbers, gate criteria
(reading cost down at equal norm coverage; no norm lost — every
retired full text leaves an index line) and the Architect's forks:
docs/tasks/2026-08-18_phase5-norm-corpus.md. Standing operation
(weekly calibration — eight runs: 07-11, 07-18, 07-19, 07-23, 07-29,
08-05, 08-14, 08-20 — the kit port queue behind the D-0074 moratorium,
the finding→remediation loop) continues alongside, unchanged.

CLOSED 2026-08-20, both gates green: W0-W4 landed, gate (а) (reading
cost down at equal coverage) taken for the first time by actual
measurement (P=146000, K=1.05, ratchet from the 08-20 measurement),
gate (б) (no norm lost) verified by two git-audits — W4-V 0/0/0 and
W2c-V zero losses across six slices. Closure recorded by the
Architect's word in session 2026-08-20; the phase carrier keeps node
statuses and the K3 shortfall accepted by word:
docs/tasks/2026-08-18_phase5-norm-corpus.md. Closure was written to
CURRENT_CONTEXT only and reached this owner document with calibration
#8 (finding F8 of docs/task_reports/2026-08-20_calibration-8.md — an
F-41 instance against ROADMAP itself).
