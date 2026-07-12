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

Phase 3 — Toolkit (D-0070) ЗАКРЫТА 2026-07-12 (приказ оператора
«давай закроем фазу 3» + релизное слово «пуш + тег v0.1.0»; блок
закрытия в ROADMAP.md): тулкит публичен и релизнут —
github.com/Xartaxana/Supervised-Delegation, тег v0.1.0, снимок
e0754a6. Phases 1/1.5 закрыты 2026-07-11. Все фазы плана до
Phase 2-гейтов закрыты; телеметрические циклы (еженедельная
калибровка ~07-18, тренд экономии) — штатные операции. Plan of
record: docs/UNIFIED_PLAN_2026-07-07.md; гейты Phase 2 — ROADMAP.md.

## Current Task (Authoritative, D-0025)

API-ОКНО АКТИВНО (2–3 дня с 2026-07-12 ~22:15; лимиты подписки
исчерпаны — цена равна). ПОДТВЕРЖДЕНО НА РАБОЧЕМ ТРАФИКЕ 22:20:
интерактивная сессия оператора идёт через шлюз (requests 527–531,
opus, real; cache_read 61541/63423 ≈97% из кэша, cost cache-aware) —
все условия t-075 закрыты; порт кэш-колонок в toolkit разблокирован
(батч по слову оператора, D-0074). ВАЖНО: через шлюз ходят только
ТЕРМИНАЛЬНЫЕ сессии claude — десктоп переопределяет BASE_URL и
остаётся на подписке (поправка 22:05). Носитель окна: env-блок в
C:\Users\user\.claude\settings.json (бэкап .bak-apiwindow рядом);
прокси — окно «API-WINDOW PROXY», перезапуск: pwsh -File
gateway\run_proxy.ps1; капы daily_usd fable 150 / sonnet-5 50 /
opus 50 / haiku 10 / sonnet-4-6 20 (Guard warn 80%). ЗАКРЫТИЕ ОКНА
= удалить env-блок из settings.json (или вернуть бэкап) + закрыть
окно прокси. Подготовка/смоки/поправка — дословно:
docs/task_reports/2026-07-12_api-window-prep.md.
Остатки в очереди: регресс-тест стриминга; metrics.py-нарратив
кэш-колонок; пробы SessionStart-хука тегать synthetic (примесь
real замечена 22:19; ось 2, on touch preflight_quota). Параллельно
одобрен первый цикл stage-2 реплеев — открыть следующей сессией.
Гейт-отчёт Phase 2 (ниже) ждёт подписи. Действующие рамки:
ТУЛКИТ-МОРАТОРИЙ D-0074 (правка toolkit/ — только проверенным
батчем по слову оператора; порт-очередь в очереди ниже).

Закрыто 2026-07-12: Phase 3 целиком (стадия 6 + релиз v0.1.0), A3
(D-0073 манифест), D-0074, AO3-порт целиком, гейт-отчёт Phase 2
написан. Нарративы ДОСЛОВНО: docs/task_reports/2026-07-12_phase3-closure.md
+ 2026-07-12_boot-diet-round4-unroll.md (A3/AO3/стадия 6/сводки
07-11). Закрыто 2026-07-11: day-closures.md (утро: первая
калибровка, paid baseline) + evening-closures.md (вечер:
t-054..t-061, очередь 07-09..11). Живой остаток: позитивная точка
t-066 (golden set 6/7, Q3 PASS первым штатным диспатчем) для чека
14в калибровки ~07-18; решение «haiku сохраняем» в силе.

ПРИОРИТЕТ ОПЕРАТОРА 2026-07-11: текстовые задачи для API-builder
(builder-groq) забираются по ходу. Прочие нити: статья draft-C и
White Paper v0.2.0 — у оператора; остаток старой очереди —
on-touch/evidence-gated.

## Phase 2 Gate Report — 2026-07-12 (по команде оператора; ЖДЁТ ПОДПИСИ Architect)

Все числа — прямые измерения 2026-07-12 15:51+ (gateway/metrics.py
--days 14 (дайджест Task 3), tools/usage_report.py --days 14,
агрегация logs/routing-log.jsonl PowerShell'ом); оценки помечены.

**Общий гейт: ЗЕЛЁНЫЙ.**
- G1: met — 14 real-дней из 14, непрерывная серия 14/14 (union
  requests real + cc_usage; ретроспективно >=20 дней с baseline).
- G2: met — judge-groq 13/13 (последнее подтверждение — калибровка
  2026-07-11).

**Router гейт: КРАСНЫЙ (не открывается).**
- R1: NOT met — лучшая категория coding: 6 judged-пар / 3 прогона
  при пороге >=30 пар на категорию (все: classification 2/1,
  coding 6/3, extraction 4/2, formatting 4/2, summarization 2/1).
- R2/R3/R4: не вычислимы (0 категоризуемых real-строк requests в
  окне; cc_usage без промпт-контента by design — D-0034).
- R5: paid Lead фактически есть (подписка = реальные деньги по
  учётным ценам D-0034; ANTHROPIC_API_KEY живой, paid baseline
  07-11) — но при красном R1 не решает.

**Context management гейт: НЕ открывается (деньги уже сняты со
стола кэшем провайдера).**
- C1: формально met — 77% повторов на real-строках requests, НО
  выборка крошечная (рабочий набор lead-gemini 2026-07-03, ~22
  запроса) — слабое evidence.
- C2: met — 50 real-сессий >=5 ходов за 14 дней (порог >=20).
- C3: точный расчёт не построен (дайджест: not computable), но
  cache-aware границы решают по существу: cache_read = 96.2%
  input-стороны за 14 дней; оплаченный некэшированный input ~0.9%
  input-расхода (оценка: взвешивание токенов множителями цен
  1.0/1.25/0.1) при пороге >=25%. Провайдерский кэш уже поглощает
  re-sent контекст — ровно порядок D-0036 (сначала мера кэша,
  потом компрессия). Кандидат-неоднозначность: cache-write'ы
  (rewrite-после-TTL неотделим от свежего контента) — даже их
  полный зачёт как re-sent даёт ~33% (грубая переоценка сверху);
  строить точный разрез — только если Architect захочет C-гейт
  всерьёз.

**Task pipeline гейт (D-0059): ЗЕЛЁНЫЙ.**
- P1: met — 9 задач с >=5 журнальными событиями за окно (t-015:9,
  t-057:7, t-037:7, t-009:6, t-043:6, t-063/t-002/t-018/t-062:5)
  при пороге >=3; плюс сквозные семейства (конвейер t-045..t-053,
  батч 5б) через >=2 сессии.
- P2: met — defect_found t-029 (дубль task_id: состояние диспатча
  умерло на границе перезапуска сессии) + finding F-36 (шаг
  «в очередь Lead» не имел носителя между сессиями); оба — класс
  «зависимость/scope потерян на границе диспатча/сессии».
  decomposable=0 (вторая ветка P2 не задействована).
- P3: met ПО ОЦЕНКЕ Lead (проекция по определению): upkeep =
  строки брифа/очереди, которые Lead уже пишет в CURRENT_CONTEXT;
  rework в окне — ремонт t-029 + батч фиксов F-36.

**Предложение Lead:** открыть ТОЛЬКО workstream 3 (task pipeline);
первая задача — ОЦЕНКА существующих носителей task-графа (нативные
task-тулы Claude Code vs markdown-шаблон в PROCESS/) на одной
реальной многосессионной задаче, НЕ стройка (D-0030; порядок
D-0059: brief → DAG → allocate → код последним). Router — ждать R1
(30 пар придёт с регрессионными реплеями stage-2 eval-плана);
Context — закрыт по evidence, реанимация только решением Architect.

**Подпись Architect:** ___ (переход не открывается без неё, D-0033).

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

- B4 ЗАКРЫТ 2026-07-11 (F-34 разбор + решение «haiku сохраняем» +
  экзамен gpt-oss-120b операционный FAIL) — дословно в
  docs/task_reports/2026-07-12_boot-diet-round4-unroll.md; живой
  остаток (точка t-066 для чека 14в) — в Current Task выше.
- Упрочнение tier-гейта (builder-class; WHEN: на evidence первого
  инцидента — Rule #1, критик t-068 находка 2 пометил не-блокером):
  find_tier_declaration матчит ПЕРВУЮ строку `tier:` — сообщение с
  посторонней строкой, начинающейся с tier:, даёт ложный reject;
  фикс — матчить любую удовлетворяющую строку.
- ПОРТ-ОЧЕРЕДЬ ТУЛКИТА (D-0074; staging не правим, снимок — только
  проверенный батч по слову оператора; смотрит чек 12):
  (1) D-0073 манифест — УЖЕ в staging (e363e44, внесён до приказа о
  моратории), в опубликованное НЕ уходит до верификации живыми
  диспатчами; (2) док-строка D-0072 — уже ушла снимком v0.1.0,
  закрыто; (3) кэш-колонки sqlite_logger (t-075) — в toolkit/gateway
  после верификации живым трафиком окна. Новых правок toolkit/ не
  делать — ось 7 в осевых блоках отвечается «в очередь порта» сюда.
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
  КАНОНИЧЕСКИЙ ЗАПУСК: pwsh -File gateway\run_proxy.ps1 (делает всё
  сам, вкл. PYTHONUTF8=1 — без него litellm-баннер падает на
  cp1251-консоли UnicodeEncodeError'ом, урок 2026-07-12). Ключи
  лежат в gateway\.env (GEMINI/GROQ/ANTHROPIC_API_KEY).
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
