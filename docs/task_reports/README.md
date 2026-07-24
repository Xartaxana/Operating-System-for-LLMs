# Task Reports Archive

Closed work, archived out of the boot path per D-0038: when a task or
workstream closes (review ACCEPTED or Architect sign-off),
CURRENT_CONTEXT.md keeps only a one-line pointer and the full spec,
execution report and review move here VERBATIM in the same session.
Evidence is never deleted, only relocated.

## Index

- [2026-07-03_shadow-evaluation-and-llm-judge.md](2026-07-03_shadow-evaluation-and-llm-judge.md) —
  first Shadow Evaluation runs, LLM judge build/calibration history,
  contamination and judge-bias lessons, local-judge fallback
  measurement.
- [2026-07-03_research-notes.md](2026-07-03_research-notes.md) —
  related-work priors for later phases (also recorded in
  docs/RELATED_WORK.md and DELEGATION_TABLE.md).
- [2026-07-04_white-paper-iteration.md](2026-07-04_white-paper-iteration.md) —
  White Paper v0.1 log, Phase 2 gate definition, external review
  recording.
- [task-1-2_cost-accounting-and-traffic-kind.md](task-1-2_cost-accounting-and-traffic-kind.md) —
  Delegated Tasks 1–2: specs, execution reports, joint Lead review
  (ACCEPTED 2026-07-07).
- [task-4_test-isolation.md](task-4_test-isolation.md) —
  Delegated Task 4: spec, execution report, Lead review (ACCEPTED
  2026-07-07, commit 80b29b2), residual mock-row cleanup.
- [task-5_usage-report.md](task-5_usage-report.md) —
  Delegated Task 5: execution report, Lead review (ACCEPTED
  2026-07-07, commit 7e645e7), full strategic baseline findings text
  including the Architect's censored-data correction.
- [task-6_subagent-transcripts.md](task-6_subagent-transcripts.md) —
  Delegated Task 6: subagent transcripts visible to cc_usage; spec,
  execution report, Lead review (ACCEPTED 2026-07-08, commit
  75af5b5). First task executed by a live Sonnet builder subagent
  (D-0037/D-0040); sidechain telemetry = 7.2% of tokens, $100.03.
- [task-7_agent-attribution.md](task-7_agent-attribution.md) —
  Delegated Task 7: agent_id/agent_type in cc_usage + haiku pricing;
  spec, execution report, critic review, Lead review (ACCEPTED
  2026-07-08, commit 2f026f0). First journaled-at-dispatch delegation
  in this repo and first critic-tier dispatch; per-agent cost
  breakdown unlocked (R4/F-3 input).
- [2026-07-08_routing-dogfooding-day.md](2026-07-08_routing-dogfooding-day.md) —
  interim 18h routed-traffic read, dead-tier revival, F-1
  formalization (D-0041/D-0042), first degradation cycle, and the
  mechanism day: operator questions F-12..F-16 -> D-0044..D-0051
  (rejected/trail/calibration/map/handoff/boot-diet mechanisms).
- [2026-07-09_pi-exams-and-adoption-closures.md](2026-07-09_pi-exams-and-adoption-closures.md) —
  boot-diet archive (2026-07-10): t-013 closure, Pi-worker exam
  narrative (t-011/t-012/t-016 fabrication evidence), local-scout
  evaluation steps 1-3, evidence-acceptance stages 1-2
  (D-0052..D-0055, D-0060), eval-plan stage 1 (D-0057), F-22/D-0058 +
  F-23/D-0060 day narrative.
- [task-3_phase2-readiness.md](task-3_phase2-readiness.md) —
  Delegated Task 3: Phase 2 readiness digest in metrics.py; spec,
  execution report, critic review (ПРИНЯТЬ, 3 non-blocking findings),
  Lead acceptance decisions (ACCEPTED 2026-07-09, task_id t-002).
  First gate-criteria readout: G1/C2 met, R1 not met, rest honest
  gaps; G1 streak follow-up and traffic_kind drift check queued.
- [2026-07-10_queue-closures-archive.md](2026-07-10_queue-closures-archive.md) —
  D-0038 archiving pass over the queue: t-019 (quota_events digest
  line), GSD adoption A1 (t-017) / A2 (t-018) / B2-folded closures
  with accepted limitations, boot-diet morning pass narrative,
  AO3 session-handoff port (t-021).
- [2026-07-10_ranking-exam-run2-answers.md](2026-07-10_ranking-exam-run2-answers.md) —
  t-029 ranking-exam run 2 candidate answers verbatim (Sonnet 10/12,
  Opus 12/12 clean condition, plus the invalid Opus run kept as the
  policy-echo demonstration); grading lives in
  PROCESS/LEAD_RANKING_EXAM.md Runs log.
- [2026-07-10_f30-defense-build.md](2026-07-10_f30-defense-build.md) —
  t-027 F-30 defense layers 1-2: preflight_quota (measured GO/NO-GO,
  multi-db F-27 math, provider_model normalization discovery) +
  session_context SessionStart hook (clock, journal tail, calibration
  age, quota windows); builder report + critic review (ДОРАБОТАТЬ →
  B1/B2 closed by Lead: check 13ж detector, gate net extension) +
  acceptance verbatim.
- [2026-07-10_gemini-key-role-exam.md](2026-07-10_gemini-key-role-exam.md) —
  t-023/t-024 Gemini key exam (operator order, role ladder): key's
  pro tiers have zero free quota; gemini-3.5-flash 13/13 judge
  calibration but 20 req/day -> Lead rejected operationally, bound
  as cross-family judge-gemini; gemini-2.5-flash 12/13 + B1/B2
  passed -> API-contour Lead-baseline CANDIDATE. Verbatim exam
  prompts, answers, chief-judge grading, accounting.
- [2026-07-10_t015-llama70b-exam-closure.md](2026-07-10_t015-llama70b-exam-closure.md) —
  t-015 llama-70B scout re-exam closed FAIL after 4 attempts
  (3 tooling quota aborts + attempt-4 capability rejection: pseudo
  tool-call text + fabricated Trail, pipe excluded in-window by
  tools_stream_check PASS); local-scout thread fully closed, no
  cheap-Pi-worker recon row enters the table; first F-30 measured
  launch (preflight GO).
- [2026-07-10_ranking-exam-run3-gemini-answers.md](2026-07-10_ranking-exam-run3-gemini-answers.md) —
  t-030 ranking exam run 3, first cross-family candidate:
  gemini-2.5-flash 11/12 no zeros — pre-registered Lead bar passed;
  K5=1 same loss as Sonnet both runs (re-run requested from the same
  executor, not independent reproduction); independence micro-rank
  Opus 2/2 > Gemini 1/2 > Sonnet 0/2. Verbatim answers + conditions
  (old-corpus digest, clean-of-F-30 condition per run-2 lesson (б)).
- [2026-07-11_rule10-retro-sweep.md](2026-07-11_rule10-retro-sweep.md) —
  retro rule-10(б/г) sweep D-0028..D-0063: (б) no gaps, single (г)
  gap D-0040 closed in check 11; unrecognized-mechanism hunt over
  both repos' homes (t-041/t-042) found none at decision level;
  PI_HARNESS rule-0 retro four-questions backfilled here.
- [2026-07-11_savings-analysis.md](2026-07-11_savings-analysis.md) —
  baseline-vs-routed economics at full API prices: delegation gross
  savings 69% ($287/4 days), coordination premium not yet separable;
  trend baseline for calibration check 18 (tools/savings_report.py).
- [2026-07-11_day-closures.md](2026-07-11_day-closures.md) —
  verbatim closed blocks of 2026-07-11 (first weekly calibration,
  paid-Lead baseline run, t-040 counting script, retro sweep),
  unfolded from CURRENT_CONTEXT by the evening handoff boot-diet.
- [2026-07-11_toolkit-stage5a-stranger-report.md](2026-07-11_toolkit-stage5a-stranger-report.md) —
  verbatim STRANGER_REPORT.md of the stage-5a validation install
  (t-055, polygon D:\Improving_AI\From_Zero, Sonnet coordinator):
  first delegated cycle REACHED; 8 stumbles -> fixes t-057/t-058;
  Haiku failed the generated Q7 judgment trap -> scout rule 3
  hardened.
- [2026-07-11_evening-closures.md](2026-07-11_evening-closures.md) —
  boot-diet round-3 unroll: stage-4/5a narratives (t-045..t-061),
  closed queue blocks of 07-09..07-11 (A/B-series, F-30 layers,
  boot-diet rounds 1-2, F-17/eval-1, AO3 ports, Gemini exam
  evidence block), obsolete standing reminder.
- [2026-07-12_toolkit-stage5b-operator-install-report.md](2026-07-12_toolkit-stage5b-operator-install-report.md) —
  stage-5b validation install into the operator's EXISTING project
  (D:\Dog, operator self-install, Sonnet session): Path B +
  onboarding complete, critic exam caught a real trap miss
  (hinted-retry recorded honestly as their D-0001), first delegated
  cycle proven by transcript; findings F-35/F-36 + exam-retry and
  journal-leak candidates -> fix batch queued. ACCEPTED; closes
  D-0070 stage 5 (both installs).
- [2026-07-12_phase3-closure.md](2026-07-12_phase3-closure.md) —
  Phase 3 closure: stage-6 public wrap narrative (t-073 recon, D-0072
  tier doc-string in all three CLAUDE.md, PRE-RELEASE banner off,
  fourth snapshot e0754a6 + tag v0.1.0, polygon deleted) plus the
  verbatim CURRENT_CONTEXT unrolls of the 5b fix batch, stages 1–5a
  prehistory and the 07-11 evening block.
- [2026-07-12_boot-diet-round4-unroll.md](2026-07-12_boot-diet-round4-unroll.md) —
  boot-diet round-4 unroll (breach 101,952 after the Phase 2 gate
  report and D-0073/D-0074): verbatim CURRENT_CONTEXT blocks — closed
  A3/moratorium narrative, stage-6 duplicate, AO3-port paragraph,
  07-11 closure summaries, and the B4/F-34 queue block (live t-066
  residue kept in place).
- [2026-07-12_api-window-prep.md](2026-07-12_api-window-prep.md) —
  API-window preparation narrative (t-074 recon, t-075 gateway prep
  with critic entry, live-proxy cache smoke, PYTHONUTF8 lesson, the
  22:05 desktop-bypass correction, headless streaming check) and the
  final verification on the operator's real interactive traffic
  (~97% cache reads, cache-aware cost).
- [2026-07-13_api-window-night.md](2026-07-13_api-window-night.md) —
  API-window night narrative: t-077 streaming test, t-078 metrics
  cache fix, t-079/D-0075 synthetic self-tag + F-37 MODEL-line
  marker, F-38 cache_read_share fix, stage-2 pipeline t-082..t-085
  and shadow-eval runs 1-2 (third consecutive coding->Middle reject
  signal). Index line added 2026-07-13 day: the night session
  archived the file but skipped this index — caught by boot-diet
  round 5 step 3.
- [2026-07-13_phase2-gate-report.md](2026-07-13_phase2-gate-report.md) —
  Phase 2 gate report SIGNED 2026-07-13, verbatim from
  CURRENT_CONTEXT (boot-diet round 5): common + task-pipeline gates
  green, Router red (R1 12/30), Context closed by direct cache-aware
  measurement (C3 = 0.11% vs 25% threshold); the transition decision
  block lives in ROADMAP.md "Gate decision 2026-07-13".
- [2026-07-13_middle-candidates-judge-haiku.md](2026-07-13_middle-candidates-judge-haiku.md) — закрытая часть дня Middle-кандидатов: алиасы, первые прогоны (F-39/F-40), фикс стенда t-091, провал judge-haiku 11/13 и схема судейства; перенос boot-diet раунда 6 (2026-07-14).
- [2026-07-14_external-review-triage.md](2026-07-14_external-review-triage.md) — триаж внешнего ревью 2026-07-13 (Lead): 4/4 сверенных клейма подтверждены; вердикты по 12 находкам и 7 идеям — берём/в очереди/на калибровку/в порт/не берём с триггерами.
- [2026-07-14_toolkit-v020-divergence-manifest.md](2026-07-14_toolkit-v020-divergence-manifest.md) — манифест намеренных расхождений корень↔toolkit релиза v0.2.0 (DoD порт-батча t-101..t-105): что догнало корень, 10 намеренных расхождений (пустой VALIDATED_DELEGABLE, генерический regression-набор вместо утечки D-0070, эпоха-cutover'ы и пр.), что не портировано со своими гейтами (пп.9/10/13 + permission-audit).

- [2026-07-15_exam-week-context-closures.md](2026-07-15_exam-week-context-closures.md) — VERBATIM закрытого экзаменационного повествования недели из CURRENT_CONTEXT (boot-diet раунд 10): прогоны №2–№4 с вариациями, декомпозиция удвоения, D-0077-генезис, главный вывод и решения 07-15; полные разборы — docs/tasks/*economy-exam*, протокол Runs log.
- [2026-07-15_roadmap-closed-phases.md](2026-07-15_roadmap-closed-phases.md) — VERBATIM закрытых фаз ROADMAP.md (boot-diet раунд 11, D-0078): Phase 0, Phase 1, Phase 1.5 (с блоком закрытия 07-11), Phase 3 (с блоком закрытия 07-12); в ROADMAP.md — указатели-статусы, живые гейты Phase 2 остались на месте. Постоянный архивный дом закрытых фаз: будущие закрытия едут сюда же.
- [2026-07-16 evidence-gated residuals](2026-07-16_evidence-gated-residuals.md) — вынос очереди триггер-остатков при handoff-дожиме
- [2026-07-16 evening closures: порт-ход + прогон №11](2026-07-16_evening-closures-port-run11.md) — план сессии 07-16 целиком (приёмка t-159, порт гейтов в штаб/AO3/тулкит v0.3.0, прогон №11 скаляр 0.88, класс t-151 живьём), блок экзамен-серии №7–№10б, дубль AO3-порта D-0076
- [2026-07-18 закрытия калибровки №2](2026-07-18_calibration2-closures.md) — VERBATIM блоков CURRENT_CONTEXT, закрытых вторым еженедельным прогоном (повестка кандидатов с вердиктами, пилот носителя, находки гейтов 07-16 полными формулировками, baseline-буллеты Claude Code, опус-дизайнер продлён); итоги прогона — notes события calibrated 07-18
- [2026-07-18 вечер: серия экзаменов №12–№14 и порты](2026-07-18_evening-run-series.md) — хронология вечера (пробы границы D-0080, shadow-реплей 5/8, D-0081, экзамены №12/№13/№13c2/№14 с вердиктами оператора, порт critic-lite в штаб и AO3, процесс-находки дня) + VERBATIM калибровочного блока CURRENT_CONTEXT со статусом переноса
- [2026-07-21 день leaf routing](2026-07-21_leaf-routing-day.md) — VERBATIM закрытых блоков CURRENT_CONTEXT handoff-развёртки 07-21 (гейт-отчёт Router 07-20 superseded, блок «ЗАВТРА», пункты дня 1–2 и скамейки роутер-кандидатов обеих волн, подпись R5 + серии D№1–№6 + открытие Router-гейта + D-0087, закрытие входящего hygiene_gate); сами решения дня — D-0087/D-0088, ROADMAP «Gate decision 2026-07-21», Runs log серий D и гибрид-экзамена, план оценки RouteLLM с вердиктами волн
- [2026-07-20 день Router-гейта](2026-07-20_router-day.md) — VERBATIM закрытых блоков CURRENT_CONTEXT вечернего boot-diet (тулкит-релизы v0.4.0–0.4.2 с батчами 1–3 и ответом AO3-сканера; ночь «привязки API-контура» t-219..224 с пост-скриптумом добора; kernel-диет 07-19); сами решения дня — D-0085/D-0086, каверат-блоки SHADOW_EVALUATION_LOG, план оценки RouteLLM, строка Runs log №18/18b
- [2026-07-22 ночь валидационной волны](2026-07-22_night-validation-closures.md) — индекс закрытий ночи (экзамен №2 → промоушен critic.md rule 16, F-50 деливерабл-дрейф, N4 escape-allowlist + чеканка D-0089, ts-drift в journal_echo, WP §6.5/6.6, ROADMAP-диет, активация лист-роутинга) + VERBATIM блоков CURRENT_CONTEXT, снятых диетой: валидационный слой, входящее AO3, батч мелочей 07-20 с исходами, Habr-закрытие
- [2026-07-23 boot-diet: развёртка CURRENT_CONTEXT](2026-07-23_boot-diet-relocations.md) — VERBATIM четырёх закрытых блоков, снятых диетой 07-23 (онбординг D-0090 с валидацией обоих полигонов; валидационный слой + чеканки D-0091/D-0092 + аудит поставки F-52; батч мелочей t-275 с историческим текстом; нарратив пополнений White Paper до v0.2.2); живые остатки оставлены указателями на месте
- [2026-07-24 enforcement-gap аудит](2026-07-24_enforcement-gap-audit.md) — деливерабл входной оценки Phase 4 (D-0098, слово оператора): актуальность доков (4 протухания с носителями), карта enforcement по слоям A–E (gate/validator/WARN/чеки/дисциплина) с named-детекторами, ранжированные кандидаты промоции E1–E11 и рекомендации Lead; материал t-312..t-315
- [2026-07-24 Phase 4: закрытия дня](2026-07-24_phase4-hardening-closures.md) — VERBATIM блоков, снятых диетой 07-24 после исполнения батча Phase 4 (очередь гейт-касаний; гэп-батч 07-23 и калибровка №4 с очередью находок целиком; тулкит-порт-очереди и привязки D-0085; батчи мелочей 07-22/07-23, порт exam_fullgates_kit, дог-батч); все «остающиеся узлы» закрыты t-308..t-317, живые остатки консолидированы в очередь №5 CURRENT_CONTEXT
