# Current Context

## Maintenance Rule (D-0038)

This file holds LIVE state only: the current milestone, the single
authoritative task (D-0025), the queue, condensed system state,
strategic guidance still steering decisions, and operational
environment notes. When a task or workstream CLOSES (review ACCEPTED
or Architect sign-off), the session that closes it moves the spec,
execution report and review VERBATIM to docs/task_reports/ and leaves
a one-line pointer here. Evidence is never deleted, only relocated.
Rationale: this file is loaded on every boot (BOOT.md); boot context
is a paid resource — the project's own subject.

## Current Milestone

Phase 3 — Toolkit (D-0070): система как инструмент для чужих
проектов. Phases 1/1.5 ЗАКРЫТЫ 2026-07-11 (подпись оператора «да
закрывай», блок закрытия в ROADMAP.md); телеметрические циклы
(еженедельная калибровка, тренд экономии) — штатные операции, не
фазовая работа. Plan of record: docs/UNIFIED_PLAN_2026-07-07.md +
Phase 3 docs/TOOLKIT_INTAKE_2026-07-11.md.

## Current Task (Authoritative, D-0025)

TOOLKIT, стадия 5б — установка в ТРЕТИЙ проект оператора (путь
спросить у оператора при старте). Стадии 1–5а ЗАКРЫТЫ 2026-07-11:
первый пуш a0b3cd9 «v0.1.0-pre» (конвейер t-045..t-053); стадия 5а
ПРИНЯТА (t-055 — незнакомец на пустом проекте дошёл до первого
делегированного цикла, отчёт:
docs/task_reports/2026-07-11_toolkit-stage5a-stranger-report.md);
все 7 находок закрыты (t-058); роли ужесточены (t-057 scout 3/4 +
F-33 builder/critic, обе копии, гигиена п.6 обоих CLAUDE.md);
critic-экзамен СОЗДАН И ВАЛИДИРОВАН НА ОБОИХ ПОЛЮСАХ (D-0071:
PROCESS/CRITIC_EXAM.md, наш opus — PASS образцовый, контроль sonnet
— FAIL, инструмент ранжирует; скилл critic-exam-gen в шаблоне; ось
8 карты); фикс дайджеста t-054/t-056 принят с critic-входами;
ВТОРОЙ РЕЛИЗНЫЙ СНИМОК f91fb31 ЗАПУШЕН (слово оператора «пуш») —
staging toolkit/ и опубликованное синхронны (ось 7). Дословные
нарративы дня: docs/task_reports/2026-07-11_day-closures.md (утро)
+ docs/task_reports/2026-07-11_evening-closures.md (вечер,
boot-diet раунд 3).

СДЕЛАНО 2026-07-11 вечер (сессия t-062..t-065): штатный прогон
scout golden set ИСПОЛНЕН — FAIL по Q3 дважды → F-34 (форма
контроля), правило 4 дополнено в обеих копиях, решение оператора
«haiku сохраняем, пристальный взгляд на калибровке ~07-18»;
ретро-аудит негативов принятой записи — ложных приёмок нет;
критик-экзамен НЕ требовался (critic.md не правился). ПОВТОР 5а
принят (t-064, отчёт в task_reports), 6 находок → фиксы t-065
приняты; экзамен кандидата gpt-oss-120b закрыт операционным
вердиктом (см. журнал/Runs log). Контроль F-34 ЗАКРЫТ 2026-07-12
(t-066): штатный прогон golden set из свежей сессии — 6/7 PASS, Q3
PASS первым штатным диспатчем с дополненным правилом 4 (рецидивы
«ложно-пустого grep» не повторились; Q7 — пропуск model, рецидив
t-057 att.2); позитивная точка для чека 14в калибровки ~07-18,
решение «haiku сохраняем» в силе. СЛЕДУЮЩАЯ СЕССИЯ: стадия 5б — установка в
существующий проект оператора (слово оператора «5б будем делать в
следующей»); путь спросить на старте. Сразу ПОСЛЕ закрытия 5б — A3
выделенным проходом (приказ оператора, см. очередь). После 5а+5б
оператор раздаёт шаблон желающим; снятие pre-release = стадия 6;
полигон D:\Improving_AI\fresh-project удалить (второй прогон 5а
принят, отчёт заархивирован). Лицензия MIT ПОДТВЕРЖДЕНА оператором
2026-07-11.

ПРИОРИТЕТ ОПЕРАТОРА 2026-07-11: закрытие Phase 2 — ПОСЛЕ первого
пуша тулкита (пуш состоялся — гейт-отчёт можно брать по команде);
текстовые задачи для API-builder (builder-groq) забираются по ходу
стройки. Прочие нити: вторая калибровка ~2026-07-18; статья draft-C
и White Paper v0.2.0 — у оператора; остаток старой очереди —
on-touch/evidence-gated. AO3-ПОРТ НАКОПЛЕН (на следующем касании их
репо): scout-правила 3+4 + гигиена «ложно-пустой поиск» + builder
«не изобретай» + critic «вердикт ≠ приёмка» (F-33) + D-0057-порт
role-файлов + log_append.py by/basis + словарная правка
defect_found (наблюдение калибровки).

Закрыто 2026-07-11 утро (нарративы дословно —
docs/task_reports/2026-07-11_day-closures.md): ПЕРВАЯ ЕЖЕНЕДЕЛЬНАЯ
КАЛИБРОВКА (18 чеков, 4 строки Claude-контура ->
provisionally_validated, false-accept: lead 2/8 vs воркеры 0/34);
PAID-LEAD BASELINE ($0.0232, урок «микрозадачи вниз не экономят»);
t-040 счётный скрипт чеков 3/13+A4; ретро-свип rule-10(б/г).
Экономический разрез: 2026-07-11_savings-analysis.md (чек 18).
Закрыто 2026-07-11 вечер (дословно —
docs/task_reports/2026-07-11_evening-closures.md): t-054..t-061 +
закрытые блоки очереди 07-09..07-11 (D-0043 остаток, локальный
scout, A1/A2/A4/B1/B2/B3, F-30 слои 1-2, boot-diet раунды 1-2,
rule-10 свип, F-17 стадии, eval-1, AO3 handoff/trim, Gemini-экзамен).

## Routing MVP — LIVE on both deployments

- Pilot: D:\AO3_tests (2026-07-07, commit b8125a0). Reference/
  dogfooding: THIS repo (2026-07-08). Each = auto-loaded CLAUDE.md
  policy + agents scout/builder/critic + logs/routing-log.jsonl
  (D-0041: always the three together).
- Policy text ARCHITECT-ACCEPTED 2026-07-09 (commit 171078c; closed
  the last open item of Phase 1.5 step 2). Later policy changes
  follow the normal mechanism discipline.
- Evidence stream: logs/routing-log.jsonl (t-001..t-061); Claude-
  контурные строки таблицы provisionally_validated с первой
  калибровки 2026-07-11 (Update Rule 1, D-0047; evidence-блок в
  DELEGATION_TABLE.md).
- Retro baseline AO3 (cc_usage, pre-routing): $276.70 accounted +
  $57.82 sidechain self-correction (Task 6). Weekly loop compares
  cost per accepted unit + escalation rate, NOT frontier share alone
  (Architect correction — see baseline section below).
- First weekly calibration DONE 2026-07-11; вторая — к ~2026-07-18
  (полновесное недельное окно, трендовые чеки 10/11 против baseline
  первого прогона; staleness watched by the Boot Report's Last
  Calibration line, D-0047).
- 2026-07-08 day narrative: archived —
  docs/task_reports/2026-07-08_routing-dogfooding-day.md.

## System State (condensed, 2026-07-08; updates dated)

- Phase 0 closed 2026-07-03 (Zero Context Recovery Test passed).
- Phase 1 steps 1-4 built and verified: Gateway (LiteLLM + SQLite
  request log), Guard (daily per-model budgets, warn 80% / refuse
  100%), Ledger (metrics.py digest), Analyst (Qwen3-4B via Ollama
  through the gateway under its own alias).
- Shadow Evaluation (step 5) operational: shadow_eval.py with
  --judge-model, --calibrate, --categories, honest Rule #1 cost
  extraction; sampler excludes judge/replay traffic. 2026-07-11:
  reader (metrics.py R1) и writer (shadow_eval.py) переведены на
  docs/SHADOW_EVALUATION_LOG.md (t-054/t-056, пара оси 4 закрыта).
- Judge: judge-groq (groq/openai/gpt-oss-120b, free tier), calibrated
  13/13 at temperature=0, reproduced twice. Protocol:
  PROCESS/JUDGE_CALIBRATION_PROTOCOL.md (D-0031) — status-changing
  verdicts need chief-judge review; 1-2 random audits per run. No
  local judge on this hardware (Qwen3-4B 11/13, below the 90% bar);
  fallback order: judge-groq > paid API judge > local 4B restricted.
  Second judge judge-gemini (gemini-3.5-flash, 13/13, t-023) —
  cross-family point work only (20 req/day): builder-groq
  self-judging pairs.
- Gemini key role exam DONE 2026-07-10: lead-gemini (2.5-flash) —
  API-contour Lead-baseline CANDIDATE (12/13 + ranking 11/12, между
  Sonnet-контролем и Opus); полный evidence-блок дословно —
  docs/task_reports/2026-07-11_evening-closures.md + отчёты
  2026-07-10_gemini-key-role-exam.md /
  2026-07-10_ranking-exam-run3-gemini-answers.md + Runs log
  LEAD_RANKING_EXAM.md. Статусы двигает production-журнал +
  калибровка (D-0028/D-0035).
- traffic_kind tagging live: real/synthetic/replay/judge; gate G1
  counts only 'real'. The tag travels via extra_body metadata —
  litellm's metadata= kwarg does NOT reach the wire (verified; see
  comments in sqlite_logger.py / shadow_eval.py).
- Tests: suite 316 passed (2026-07-11 witness, t-056 acceptance;
  canonical form python -m pytest tools/ gateway/ -q); toolkit
  suite 311 passed отдельно. gateway/conftest.py isolates every
  test (tmp DB + full litellm callback-list snapshot/restore).
- requests.db: 199 rows на 2026-07-08 (+ прогоны 07-11: paid
  baseline, судейские); cc_usage table alongside (idempotent
  import, both transcript layouts, agent attribution, 0 NULL-cost
  rows).
- DELEGATION_TABLE.md: 4-state model (D-0035).
  provisionally_validated: coding -> Middle, summarization /
  extraction / formatting -> intern, ВСЕ 4 строки Claude-контура
  (калибровка 2026-07-11); rejected: classification -> intern.
- Delegated Tasks 1-7: ACCEPTED and archived (docs/task_reports/).

## Claude Code Baseline (Task 5, 2026-07-07 — live guidance)

- $1,177.48 accounted all-time (8747 turns, 79 sessions, 4 projects).
  Per model: sonnet-4-6 $735 / opus-4-8 $206 / fable-5 $198 /
  sonnet-5 $39.
- CACHE READS DOMINATE: 97.6% of input-side tokens are cache reads;
  accounted savings vs uncached $7,117 on a $1,178 total — first
  hard evidence for the D-0036 ordering (measure net-of-cache before
  building any compression).
- G1 LOOKS GREEN RETROACTIVELY: real traffic 20 consecutive days
  (>=14 required). Formal check = Task 3 digest + written gate
  report + Architect signature (D-0033). G2 (judge 13/13) holds.
- SPEND MIX — ARCHITECT CORRECTION (2026-07-07): the baseline is
  CENSORED data (operator rationed frontier usage), so it cannot
  refute "the smartest model burns most". Correct reading — frontier
  burns FASTEST per unit: opus $0.264/turn, fable $0.216 vs sonnet
  $0.063-0.114 (2-4x). Consequences: (a) success metric is cost per
  accepted unit by tier + escalation rate, NOT frontier share;
  (b) the escalation journal measures the true tier boundary; the
  weekly loop watches the recent-window trend, not all-time totals.

## Remaining Lead-tier Queue (live only; закрытые блоки — evening-closures)

- B4 ЗАКРЫТ полным Lead 2026-07-11 21:26+ (разбор по приказу
  оператора): корень Q3-провала t-062 — правило 4 было ИСПОЛНЕНО и
  не спасло (Grep-тул регистрозависим, lowercase-паттерн +
  type-фильтры; контроль sqlite3 доказал трубу, не пустоту) — F-34;
  правило 4 дополнено (форма контроля = форма вызова, негатив
  только case-insensitive, фильтры в след) в обеих копиях scout.md
  + гигиена п.6 обоих CLAUDE.md; валидирующий прогон t-062 att.2
  (inline) — Q3 FAIL ПОВТОРНО при новом правиле в собственном
  промпте → эскалация оператору (правило 6; сигнал capability
  яруса). РЕШЕНИЕ ОПЕРАТОРА 2026-07-11: scout=haiku СОХРАНЯЕМ,
  пристальный взгляд на второй калибровке ~07-18 (чек 14в);
  ретро-аудит негативов принятой записи ложных приёмок не нашёл
  (F-34 аддендум). Экзамен второго кандидата gpt-oss-120b (t-063)
  ЗАКРЫТ операционным вердиктом: free-tier TPM 8000 = потолок ~3
  tool-хода/сессию, scout-функция невозможна (способность не
  измерялась; 0 фабрикаций за 6 сессий — позитив записан; Runs log
  SCOUT_GOLDEN_SET + разрыв №6 PI_HARNESS). scout=haiku без
  альтернативы с этого ключа. AO3-порт (очередь ниже) расширен
  дополнением правила 4.
- A3 dispatch context manifest (Lead-class, mechanism — full
  rule-10 treatment; WHEN: ВЫДЕЛЕННЫМ ПРОХОДОМ сразу ПОСЛЕ закрытия
  стадии 5б — приказ оператора 2026-07-11, заменил прежний пассивный
  триггер «next D-0054/rule-11 touch»): the dispatch text enumerates
  the exact files/data injected into the worker (GSD
  UnitContextManifest as prior art); lane-contract fields
  (Owns/Non-goals/Handoff, maxConcurrent — из OpenClaw-обзора)
  входят в шаблон манифеста тем же проходом.
- A5 witness auto-collection (builder-class; WHEN: first REAL
  builder-Pi work cycle — Rule #1: no wrapper before there are
  sessions to wrap; binding decided at calibration): wrapper runs
  the canonical pytest form after a Pi builder session and attaches
  verbatim output as a witness DRAFT; acceptance stays with Lead.
- Evidence-gated residuals (каждый — на своём триггере): provider
  column in sqlite_logger (N1/N2 root, axis 2); requests(model,ts)
  index (только на latency evidence); AO3 log_append.py port of
  by/basis + continuation/retry branches (axis 1, в AO3-порт выше);
  usage_report.py loud-fail on locked cc_usage DB (axis-2 candidate,
  on evidence); t-018 wall admission-math (candidate on calibration
  evidence, journal row 404); structured worker-report frames
  (deferred until dispatch volume); builder-groq = CANDIDATE
  API-contour builder binding (next text-shaped cycles dispatch
  there; self-judging caveat pinned in config.yaml); F-17 stage 3
  PreToolUse context-budget hook (data-gated: only if calibration
  checks 10/11 show the discipline leaks); per-file boot-budget
  breakdown в session-handoff чек 4 / SessionStart hook (on next
  touch, OpenClaw prior art).
- Eval plan, stage 2 (needs >=1 week routed traffic): journal's
  accepted tasks as a regression set replayed on the API contour on
  model/price changes; minimum-n / pass^k in DELEGATION_TABLE Update
  Rules (thresholds from first-calibration data); numeric judge-human
  agreement in JUDGE_CALIBRATION_PROTOCOL. NOT taken: per-PR CI, full
  execution-based bench harness (Rule #1).
  - Batch API candidate (2026-07-10, operator-approved): judge/
    replay/golden-set traffic = independent request sets with no
    latency need — Message Batches profile (-50% input AND output;
    Groq/Gemini have analogs). TRIGGER (Rule #1): stage-2 regression
    replays run regularly — free-tier judge traffic gains $0 today.
    At adoption: batch endpoints bypass the proxy's request logging —
    the accounting path into requests.db must land in the same move
    (axis 2, never a silent $0).
- NOT adopted (recorded to stop re-litigating): GSD as coordinator
  (duplicates Lead), auto-mode SQLite state machine + crash recovery
  (our analog is session handoff), supply-chain audit tags, WXP;
  OpenClaw: channels, delegate identity, compaction/memory
  (harness-owned), utilityModel (duplicates D-0062). Прочее из
  OpenClaw-обзора закрыто или едет на своих носителях (см.
  evening-closures + RELATED_WORK «OpenClaw survey»).
- Habr article thread (t-036, 2026-07-10): blind A/B done — A=Sonnet,
  B=Opus, operator verdict B>A, neither publishable. draft-C written
  by Lead, role fixes v2 (d3e52d2) → F-31. NEXT: operator writes the
  final article based on docs/draft-C.md and hands it to Lead for
  proofreading + comparison against the three AI drafts. Brief + all
  drafts: docs/ARTICLE_BRIEF_2026-07-10.md, docs/draft-{A,B,C}.md.
- White Paper: v0.2.0 FULL REVISION done 2026-07-10 (охват — см.
  git log v0.2.0). AWAITING Architect review (operator reviews
  v0.2.0 directly; v0.1.x review thread superseded). NB: v0.2.0 не
  покрывает события 2026-07-11 (калибровка, тулкит, D-0070/71) —
  кандидат v0.2.1 после стадии 6.

## Environment Notes (this machine)

- Ollama 0.31.1 (winget); NVIDIA driver 582.28 — Qwen3-4B runs 100%
  on the GTX 1060 GPU (~5 s warm vs ~15 s CPU).
- Proxy must be started from gateway/ (callback imports are
  cwd-relative). litellm does NOT auto-load gateway/.env — export
  GEMINI_API_KEY / GROQ_API_KEY before starting the proxy.
- lead-gemini = gemini/gemini-2.5-flash (10 req/min, 250 req/day);
  judge-gemini = gemini/gemini-3.5-flash (5 req/min, 20 req/day
  rolling — pace >=13s, point work only). ZERO free quota on this
  key: 2.0-flash and ALL pro tiers — 429, don't use (probed
  2026-07-10).
- ANTHROPIC_API_KEY LIVE since 2026-07-10: lead (Fable) and
  lead-sonnet aliases operational end-to-end through the proxy;
  credits prepaid, expire 12 months from purchase, auto-reload off.
  Paid-Lead baseline и гейт R5 разблокированы; прогоны — по
  расписанию калибровки/очереди, не ad hoc.
- Free-telemetry mode: intern/analyst (Ollama) carry synthetic
  Haiku-class accounting prices, so Guard/Ledger money paths work at
  $0 cash.
- BSOD 2026-07-09 15:02 (bugcheck 0x3B in aehd.sys — Android
  Emulator Hypervisor Driver) while the AO3 pipeline exercised the
  emulator. Rule of thumb: do NOT run the Android emulator (AO3 QA
  pipeline) and local GPU inference (Ollama exam runs)
  simultaneously; sequence heavy workloads.

## Archive (D-0038 pointer)

Closed work lives in docs/task_reports/ — the annotated index is its
README.md (single owner since 2026-07-10; per-file descriptions were
duplicated here and are trimmed from the boot path).

This file is intended to be updated frequently.
