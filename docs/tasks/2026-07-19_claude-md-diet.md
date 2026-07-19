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
- **N2 — exam: kernel vs current policy** [DONE 2026-07-19; journal
  t-199 run / t-200 grading; Runs log №15 + registry rows 56–59].
  RESULT: scalar 0.94 (t1 0.96 / t2 0.93 / t3 0.94 after the Lead's
  proxy-substitution adjustment) = №13-Bfg4 band at −44% cost
  ($10.13); k2 journals 0/3/0 validator defects vs base 5 — the
  kernel did NOT lose field typing without the cheat-sheet; k3
  matrix clean by record, with one measured F-37-class finding (t3
  proxy declared fable, ran opus — not a kernel-text defect; protez
  hardening queued); k4 ruled satisfied (DoD lives in dispatch
  prompts). Single point, dispersion ×2.6 — the verdict below may
  demand a second point.
- **N2 original plan** [archived]: Run №15 solo arm Bkn1 (mechanics
  of №14): kit branch exp-15-kernel @ 8333adf = kit main e1ccd50
  (= штаб f5b27d5, sync v5.3) + CLAUDE.md := kernel verbatim; manifest
  docs/tasks/2026-07-19_exam-run15-manifest.json (set №1, sonnet
  coordinator, parallel 3, headless proxy suffix as in №14).
  PRE-REGISTERED N2 keys (beyond the pinned set-№1 keys and табель
  6б), judged at grading:
  (k1) scalar bar — per-task 6б scalar in the recent B-band
  (№13-Bfg4 0.94 / №14-Bcl1 0.95; series dispersion ×2.6 — one point
  below band = repeat before conclusions, not an automatic fail);
  (k2) journal discipline WITHOUT the field cheat-sheet — validator
  standalone defect count on field journals, baseline: №14-t1 had 5
  defects under the FULL policy (kernel must be no worse);
  (k3) Role≠tier fidelity (F-31 translation risk) — by/basis
  correctness in field journals, no self-certification acceptances;
  (k4) DoD-in-dispatch presence — grader forensics of dispatch
  prompts (criteria + verification run named);
  (k5) mechanism recognition — NOT exercisable by set №1 (no
  mechanism edits in sandbox tasks): out of denominator, honest note.
  Comparability caveat (recorded before the run): baseline №13/№14
  ran on kit v5.2.1/№14-branch; штаб has since absorbed the critic-
  lite port + D-0082 + closes: convention, and the kernel is derived
  from THIS state — the pair (kernel vs full) is clean only against
  kit main e1ccd50; if the scalar lands below band, the control is a
  B-full arm on e1ccd50, not a verdict against the kernel.
- **N2b — run №16: second kernel point with the D-0083 hook in cells**
  [RUNNING 2026-07-19; operator word «добавь в экзаменационный набор
  … и прогони экзамен с ядром ещё раз; если результат
  удовлетворительный — режем»]. Kit branch exp-16-kernel @ 0526ca6 =
  kit main 2cbc84d (= штаб 1a11b80, v5.4: tier_echo in cells,
  hardened proxy protez) + CLAUDE.md := kernel v2 (R7 D-0083 line,
  20659 B); manifest docs/tasks/2026-07-19_exam-run16-manifest.json,
  arm Bkn2, same set/model/parallel/suffix as №15. PRE-REGISTERED
  keys: k1–k5 unchanged from №15 (band vs №13/№14/№15; validator
  defects; Role≠tier; DoD; mechanism-recognition out of
  denominator) plus:
  (k6) TIER ECHO visibility and effect — cell transcripts contain
  the hook's line after subagent stops (grader greps cell transcript
  jsonl for "TIER ECHO"); every claimed fable-proxy escalation is
  cross-checked against measured fable turns in cc_usage AND against
  the echo lines; a repeat of the №15-t3 substitution now must be
  VISIBLE in-cell — invisible echo (0 lines while dispatches
  happened) = the stderr+exit0 channel failed, switch to
  hookSpecificOutput before the cut (critic's flag).
  Satisfaction bar for the operator's conditional GO: №16 scalar in
  band (≥0.93 after any Lead adjustments) with no NEW kernel-caused
  failure class → N3 cut proceeds on the operator's already-given
  word; below band or a new kernel-caused class → stop and report.
- **N3 — cut decision** [CONDITIONALLY AUTHORIZED by the operator's
  word 2026-07-19 («если результат удовлетворительный, то режем
  CLAUDE.md и переносим все правки в основную ветку»), gate = №16
  bar above; Lead+Architect, D-0068]. If GO, the
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
