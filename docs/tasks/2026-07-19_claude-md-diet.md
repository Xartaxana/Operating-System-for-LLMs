# CLAUDE.md deep diet — task DAG (started 2026-07-19)

Operator's word 2026-07-19: «делаем — начни с инвентаризации и собери
ядро-кандидат; язык можно английский, где возможно — mermaid».
Carrier per rule 4a (D-0080): the task spans ≥2 sessions by
construction (candidate → exam → cut decision).

## Criterion (D-0063 applied to the boot budget)

A rule earns its place in the always-loaded CLAUDE.md only if NOTHING
on the execution path guarantees the encounter with it. Everything
already gated by code (journal format → journal_validator, mechanism
block → mechanism_gate, hygiene → hygiene_gate WARN hook, open
dispatches → SessionStart hook) shrinks to a stub — the gate's own
error message carries the detail at exactly the moment of violation.
Norms stay in the kernel; rationale, precedents and dated history
relocate VERBATIM to docs/POLICY_FULL.md (created at cut time).

## Inventory (measured 2026-07-19, bytes UTF-8; targets are estimates)

| Section | Bytes | Encounter guarantor today | Disposition | Target |
|---|---:|---|---|---:|
| preamble | 588 | — (identity) | keep, EN | ~300 |
| Ярусы | 1367 | — (norm) | keep, EN table | ~700 |
| rule 1 recon | 1284 | discipline (checks F-9/22) | norm EN; precedents→FULL | ~700 |
| rule 2 builder | 1718 | validator (witness field) | norm EN; pilot→pointer | ~800 |
| rule 3 critic | 2726 | discipline + validator (basis) | norm EN; уроки→FULL | ~1200 |
| rule 4 parallel | 1252 | discipline | norm EN | ~600 |
| rule 5 flat | 223 | — | keep | ~150 |
| rule 6 escalation | 854 | validator branches + check 3 | norm EN | ~400 |
| rule 7 background | 835 | check 5 | norm EN | ~350 |
| rule 8 skip/batch | 1369 | validator (skip reason) + check 22 | norm EN | ~600 |
| rule 9 class | 1001 | critic duty + map | norm EN | ~500 |
| rule 10 mechanisms | 2489 | **mechanism_gate on commit path** | recognition test + 4 questions list + gate pointer | ~700 |
| rule 11а questions up | 1438 | discipline | norm EN | ~500 |
| rule 11 DoD/manifest | 2936 | worker-return net | norm EN | ~1100 |
| rule 12 cadence | 1060 | checks 11/25 | norm EN | ~350 |
| Журнал | 5916 | **journal_validator on commit path** («его отказ объясняет нарушение») + SessionStart hook | example + cadence + vocabulary; field details stay minimal | ~2300 |
| Роль ≠ ярус | 3126 | validator enforces by/basis matrix | **F-31 load-bearing** — full translation, no compression of the three definitions; matrix as table | ~1600 |
| Деградация Lead | 2964 | SessionStart MODEL line + journal events | mermaid state diagram + both-end checks; full text→FULL | ~1100 |
| Гигиена | 2584 | **hygiene_gate WARN hook** + allowlist itself | canonical forms + F-30 core | ~1000 |
| **TOTAL** | **35776** | | | **~14950** |

Language factor: EN halves the UTF-8 byte cost of Cyrillic (2→1
byte/char) and reduces token count; D-0002 (English canonical) and the
toolkit policy (EN) already point this way.

**N1 measured result (2026-07-19): kernel = 20 379 bytes (−43%), NOT
the ~15 K target** — the delta is the price of full norm fidelity
(nothing normative was dropped, only rationale/precedents). Second-
squeeze candidates, deliberately NOT taken before the exam (each
trades always-loaded text for gate-taught detail, and the gate fires
only at commit time — after a session has already composed the
artifact):
- journal typed-field list (~1 KB): validator error messages could
  teach it; risk — a mis-composed event costs a full cycle before the
  gate fires;
- R10 four-questions list (~0.5 KB): mechanism_gate rejection text
  could carry it; same latency trade;
- R3/R11 enumerated sub-cases (~1.5 KB): compressible at real risk of
  F-31-class collapse.
Exam N2 should run the 20 K kernel first; a 15 K variant only if the
20 K one holds the 0.95 bar and the second squeeze is separately
justified.

## Nodes

- **N1 — inventory + kernel candidate** [DONE 2026-07-19, Lead-tier,
  no dispatch]. Deliverables: this file;
  docs/POLICY_KERNEL_CANDIDATE.md (~15 KB target, EN + 2 mermaid
  diagrams). Candidate is NOT active policy; CLAUDE.md untouched.
- **N2 — exam: kernel vs current policy** [QUEUED; needs operator word
  — exam runs are paid]. Mechanics: deployment-economy exam
  (PROCESS/DEPLOYMENT_ECONOMY_EXAM.md, same harness as №12–№14) on a
  branch whose CLAUDE.md = kernel candidate; pre-registered keys;
  compare per-task scalars vs the №12–№14 baseline (0.95 median).
  Special scrutiny keys: Role≠tier matrix behavior (F-31 translation
  risk), journal typed-field compliance (details now taught by
  validator errors, not by the policy text), mechanism recognition
  (rule 10 stub sufficiency).
- **N3 — cut decision** [QUEUED; Lead+Architect, D-0068]. If GO, the
  cut commit (full rule-10 mechanism): CLAUDE.md := kernel;
  docs/POLICY_FULL.md created with VERBATIM relocation of removed
  rationale/precedents; SIBLING_MAP axis 4 gains the kernel↔FULL pair;
  class walk — AO3 CLAUDE.md (565 lines, same disease) queued to their
  carrier, toolkit policy per D-0074 port queue.
- **N4 — RU mirror decision** [QUEUED, optional]: Russian translation
  of the kernel off the boot path, for the operator's reading comfort.

## Risks

- F-31: retelling collapses load-bearing formulations — mitigated by
  full-fidelity translation of Role≠tier (no compression) and N2 exam
  keys targeting exactly those distinctions.
- Validator-taught details assume the violation HAPPENS to be caught
  at commit time; norms whose violation the validator cannot see
  (e.g. witness honesty) stay in the kernel text explicitly.
- Mermaid renders as text to models either way; diagrams are kept only
  where they genuinely replace longer prose (journal lifecycle,
  degradation), not as decoration.
