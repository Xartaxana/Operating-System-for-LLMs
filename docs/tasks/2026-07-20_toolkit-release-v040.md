# Toolkit release v0.4.0 — batch DAG (2026-07-20)

Operator word 2026-07-20: «делаем новый релиз со всеми исправлениями»
— the D-0074 moratorium batch is OPEN. CONSTRAINT (operator): the
dev-side cadence «calibration runs the small exam» must NOT ship —
that is our developer practice; onboarding exams of the USER's models
(scout/critic-exam-gen, LEAD_RANKING, judge calibration) stay.
Recon t-211: the shipped WEEKLY_CALIBRATION_PROTOCOL carries only
role-file-edit regression runs (onboarding-set class) — the exam
cadence is ABSENT already; the batch must not introduce it (critic
checks; release note states it).

## Batch composition (port queue items 1–6 + kernel)

- **P1 policy**: toolkit/CLAUDE.md ← адаптация нашего ядра (D-0084):
  event-shape table, closes: token, D-0082 generic cross-repo
  carrier rule, D-0083 measurement rule (journal_echo delivery),
  R11 inline-DoD, two-point enforcement clause. Deployment-agnostic
  (no AO3/штаб paths, no dated pilots, no exam-cadence).
- **P2 tools**: session_context.py (closes: parser) + hygiene_gate.py
  + journal_echo.py + tier_echo.py (библиотека замера) + их тесты;
  .claude/settings.json wiring (hygiene_gate PreToolUse Bash|
  PowerShell; journal_echo PostToolUse; tier_echo НЕ на SubagentStop
  — урок 9e18347).
- **P3 gateway (п.13 Safe telemetry, решение 07-16)**: default
  GATEWAY_LOG_RAW_TEXT=false; raw text logged only when explicitly
  enabled for Shadow Evaluation; honest config line + warning when
  raw is on; TTL/purge note for raw.
- **P4 skills**: permission-audit (п.15, прожил в корне с 07-14) —
  адаптированный порт в toolkit/.claude/skills/.
- **P5 п.18 хвост**: boot-diet skill of the kit — fresh-session
  order note (only after Boot Report + operator word) — verify
  present / add.
- **P6 release**: snapshot toolkit/ → D:\Improving_AI\
  Supervised-Delegation (procedure of v0.3.0), commit, tag v0.4.0,
  push. Release note lists the batch and states the exam-cadence
  exclusion explicitly.

## Nodes

- N1 recon [DONE t-211].
- N2 builder A: P1+P2+P4+P5 [dispatched t-212].
- N3 builder B: P3 [dispatched t-213].
- N4 critic release gate [DONE t-214: ПРИНЯТЬ; negative re-checked
  with positive form control; 4 non-blockers placed].
- N5 [DONE 2026-07-20]: staging commit f9598b1 (axes + tier),
  git-based tracked-only snapshot (86 files; caches with HQ paths
  excluded per critic NB-1), public clone commit d139f3a, tag
  v0.4.0 pushed. Release note states the exam-cadence exclusion.
  RESIDUALS → next batch queue (detail below).

## Next batch queue — detail (moratorium; opens by operator word)

1. **permission_audit: CLAUDE_PROJECTS env fallback + empty-dir
   warning** (critic NB-4). The ported script derives the
   transcripts directory from a slug computed off the repo path;
   the slug algorithm is empirically confirmed only for `:`/`\`/`_`
   → `-` (dots/spaces unverified), and the docstring's "override
   CLAUDE_PROJECTS" advice is not backed by code — the constant is
   computed unconditionally. On an unusual install path the tool
   silently reports "Scanned 0" (the silent-zero class, same family
   as the shadow_eval symptom). Fix shape: read a `CLAUDE_PROJECTS`
   env override; WARN when the computed directory does not exist or
   yields zero transcripts («likely wrong slug — set
   CLAUDE_PROJECTS»); tests for dot/space paths. Sibling check:
   штабной permission_audit has a hardcoded correct slug, but the
   warn-on-empty is the same class — port it home too.
2. **HQ-side port of GATEWAY_LOG_RAW_TEXT** (builder-B finding: our
   own gateway/sqlite_logger.py still writes prompt/response
   unconditionally). Needs a DEPLOYMENT DECISION, not just code: our
   pipelines READ raw text (Shadow Evaluation replay; metrics
   context-repetition C1; categorize() fallback), so flipping the
   default to false at HQ would silently starve them (the kit
   README documents this degradation). Recommended shape: port the
   flag with HQ default TRUE (behavior unchanged, gains the honest
   startup banner + the switch), flip to false only by operator
   word for privacy windows. Sibling: metrics.py degradation note —
   same doc line as the kit's.
3. **`error` column masking — operator decision**. Failure rows'
   `error` can echo provider exceptions that sometimes quote
   fragments of the prompt (content-policy errors especially); the
   kit masks prompt/response but not error — recorded decision
   (diagnostic field). Options: (а) leave as is; (б) at raw-off,
   truncate error to ~200 chars / first line — keeps the diagnosis,
   bounds the leak; (в) full masking (hurts debuggability).
   Recommendation: (б); trades a little forensics for bounded
   leakage — needs the word because it touches debuggability.
