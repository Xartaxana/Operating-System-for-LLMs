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
e0754a6. Phases 1/1.5 закрыты 2026-07-11. Phase 2: гейт-отчёт
ПОДПИСАН 2026-07-13 — workstream 3 (task pipeline, D-0059) ОТКРЫТ;
Router закрыт (ждёт R1), Context закрыт прямым измерением (блок
решения — ROADMAP.md «Gate decision 2026-07-13»). Телеметрические
циклы (еженедельная калибровка ~07-18, тренд экономии) — штатные
операции. Plan of record: docs/UNIFIED_PLAN_2026-07-07.md; гейты
Phase 2 — ROADMAP.md.

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
Остатки окна ЗАКРЫТЫ: t-077 стриминг-тест, t-078 metrics-кэш,
t-079/D-0075 synthetic-тег, F-37, F-38 — нарратив ДОСЛОВНО:
docs/task_reports/2026-07-13_api-window-night.md.
BOOT-БЮДЖЕТ: boot-diet round 5 + глубокие срезы CLAUDE.md ИСПОЛНЕНЫ
2026-07-13 (одобрение оператора; 30.9К -> 24.7К, бюджет ~93.7К/100К;
спека среза: docs/CLAUDE_MD_DIET_PROPOSAL_2026-07-13.md; верификация
critic ACCEPT t-086 + golden set 7/7 t-087). Следующий резерв при
новом росте — ROADMAP 17.3К, отдельным предложением.
STAGE-2 ЦИКЛ №1 ЗАВЕРШЁН 2026-07-13 днём: прогон №3 n=19 (distinct
11) pass_rate=0.05 -> rejected, ЧЕТВЁРТЫЙ подряд reject-сигнал
coding->Middle; счёт R1 coding = 31 пара / 6 прогонов — ОБЪЁМ
НАБРАН (порог 30/2). Строка прогона + chief-judge (2 аудита,
вердикты защитимы) — docs/SHADOW_EVALUATION_LOG.md. Статус строки
двигает калибровка ~07-18 (кандидат-вердикт rejected; оговорка
distinct-промптов там же).
Сделано ночью (дословно — 2026-07-13_api-window-night.md): конвейер
t-082..t-085 (d90cd03), прогоны 1-2 — третий подряд reject-сигнал
coding->Middle. Счёт R1 coding: 12 пар / 5 прогонов из 30/2; после
№3 ~ 27-33. Гейт-отчёт Phase 2 ПОДПИСАН 2026-07-13 (блок ниже;
workstream 3 открыт — первая задача-оценка в очереди ниже).
Действующие рамки:
ТУЛКИТ-МОРАТОРИЙ D-0074 (правка toolkit/ — только проверенным
батчем по слову оператора; порт-очередь в очереди ниже).

Закрытое 2026-07-11/12 (Phase 3, A3/D-0073, D-0074, AO3-порт,
первая калибровка, paid baseline) — описания в индексе
docs/task_reports/README.md (единственный владелец). Живой остаток:
позитивная точка t-066 (golden set 6/7, Q3 PASS первым штатным
диспатчем) для чека 14в калибровки ~07-18; решение «haiku
сохраняем» в силе.

ПРИОРИТЕТ ОПЕРАТОРА 2026-07-11: текстовые задачи для API-builder
(builder-groq) забираются по ходу. Прочие нити: статья draft-C и
White Paper v0.2.0 — у оператора; остаток старой очереди —
on-touch/evidence-gated.

## Phase 2 Gate Report — ПОДПИСАН 2026-07-13, архивирован (D-0038)

Полный текст VERBATIM: docs/task_reports/2026-07-13_phase2-gate-report.md;
решение перехода — ROADMAP.md «Gate decision 2026-07-13».

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

- Фазы/гейты — владелец ROADMAP.md (Phase 0/1/1.5/3 закрыты там).
  Компоненты API-контура (Gateway/Guard/Ledger/Analyst/Shadow
  Evaluation) построены и живы; лог прогонов —
  docs/SHADOW_EVALUATION_LOG.md (t-054/t-056, пара оси 4).
- Judge: judge-groq (gpt-oss-120b, free) 13/13 x2; протокол
  PROCESS/JUDGE_CALIBRATION_PROTOCOL.md (D-0031) — статусные
  вердикты через chief-judge, 1-2 случайных аудита на прогон.
  Fallback: judge-groq > paid API judge > local 4B restricted
  (Qwen3-4B 11/13 — ниже бара). Второй судья judge-gemini (13/13,
  t-023) — кросс-семейная точечная работа (20 req/day):
  self-judging пары builder-groq.
- lead-gemini (2.5-flash) — API-contour Lead-baseline CANDIDATE
  (экзамен 07-10; evidence — evening-closures.md + Runs log
  LEAD_RANKING_EXAM.md); статусы двигает журнал+калибровка.
- traffic_kind live: real/synthetic/replay/judge; G1 считает только
  real; тег едет extra_body metadata (litellm metadata= kwarg до
  провода НЕ доезжает — verified, комментарии в sqlite_logger.py).
  С t-085 рядом едет ground-truth category (та же труба).
- Tests: каноническая форма python -m pytest tools/ gateway/ -q
  (352 passed на 2026-07-13); toolkit suite отдельно;
  gateway/conftest.py изолирует каждый тест.
- DELEGATION_TABLE.md: 4-state (D-0035). provisionally_validated:
  coding->Middle, summarization/extraction/formatting->intern, все
  4 строки Claude-контура (калибровка 07-11); rejected:
  classification->intern. Reject-тренд по coding->Middle копится
  (3 прогона подряд) — решает калибровка ~07-18.

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

- WORKSTREAM 3 — задача 1 (оценка носителей) закрыта 2026-07-13,
  отчёт docs/TASK_CARRIER_EVAL_2026-07-13.md. ПИЛОТ ОДОБРЕН
  оператором тем же днём с поправкой: полигон НЕ тулкит — задачи
  репо/AO3. ПИЛОТ ОТКРЫТ: docs/tasks/2026-07-13_calibration-week.md
  (цепочка недели калибровки ~07-18, N1 metrics-фикс уже в работе
  t-090); AO3 — кандидат второй точки после этого пилота;
  adoption-решение — по разбору пилота на калибровке (N5).
- Упрочнение tier-гейта (builder-class; WHEN: на evidence первого
  инцидента — Rule #1, критик t-068 находка 2 пометил не-блокером):
  find_tier_declaration матчит ПЕРВУЮ строку `tier:` — сообщение с
  посторонней строкой, начинающейся с tier:, даёт ложный reject;
  фикс — матчить любую удовлетворяющую строку.
- ПОРТ-ОЧЕРЕДЬ ТУЛКИТА (D-0074; staging не правим, снимок — только
  проверенный батч по слову оператора; смотрит чек 12). ТРИГГЕР
  НАЗНАЧЕН оператором 2026-07-13: порт-батч и релизный снимок —
  ПОСЛЕ закрытия Phase 2 (до того — только копить очередь):
  (1) D-0073 манифест — УЖЕ в staging (e363e44, внесён до приказа о
  моратории), в опубликованное НЕ уходит до верификации живыми
  диспатчами; (2) док-строка D-0072 — уже ушла снимком v0.1.0,
  закрыто; (3) кэш-колонки sqlite_logger (t-075) — в toolkit/gateway
  после верификации живым трафиком окна; (4) D-0075 — самотег-
  конвенция traffic_kind (генераторы) + F-37-маркер MODEL-строки
  session_context + чеки 13(ж-доп)/13(з) — батчем после проживания
  у нас; (5) stage-2 конвейер t-082..t-085: pace в evaluate,
  regression_runner + набор, колонка requests.category
  (ground-truth > эвристика, миграция образца t-075), верная
  формула cache_read_share (F-38) — тем же батчем; (6) readiness
  R2/C3 metrics.py (t-090): копия toolkit/gateway/metrics.py несёт
  ту же протухшую заглушку «currently 0» (доклад builder; их версия
  дивергентна — своя сигнатура phase2_readiness). Новых правок
  toolkit/ не
  делать — ось 7 в осевых блоках отвечается «в очередь порта» сюда.
- A5 witness auto-collection (builder-class; WHEN: first REAL
  builder-Pi work cycle — Rule #1: no wrapper before there are
  sessions to wrap; binding decided at calibration): wrapper runs
  the canonical pytest form after a Pi builder session and attaches
  verbatim output as a witness DRAFT; acceptance stays with Lead.
- Урок F-38 ярусам (оси 3/8; WHEN: следующее касание critic.md —
  regression-правило D-0057/чек 14 затребует прогона, — либо
  ревизия PROCESS/CRITIC_EXAM.md): (а) в critic.md — строка
  «сверка семантики ПОЛЯ источника — эмпирикой на живых данных, не
  чтением кода собрата» (F-30 для critic'а); (б) кейс-кандидат
  CRITIC_EXAM: пара «одна формула, разные раскладки полей»
  (подсаженный дифф класса F-38).
- metrics.py readiness-ветки R2/C3 (builder-class; WHEN: до
  калибровки ~07-18, т.к. она будет читать readiness): печатают
  протухшее «currently 0 traffic_kind='real' rows» при 345 живых
  real-строках — противоречат C1 того же прогона; найти условие
  ветки, обновить сообщение/логику (R2 теперь вычислим по
  categorize() на real-строках, C3 — по кэш-колонкам t-075; замер
  вручную уже в гейт-отчёте). Вскрыто пересмотром отчёта 07-13.
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
- Eval plan stage 2 — В РАБОТЕ (цикл №1 открыт 07-13, см. Current
  Task; конвейер d90cd03). Остаток плана: minimum-n / pass^k в
  Update Rules таблицы + numeric judge-human agreement в
  JUDGE_CALIBRATION_PROTOCOL (пороги — с данных калибровки). NOT
  taken: per-PR CI, полный bench-harness (Rule #1). Batch API
  candidate (одобрен 07-10): TRIGGER = реплеи регулярны; при
  адопции batch-эндпоинты минуют лог прокси — учётный путь в
  requests.db тем же ходом (ось 2, никогда молчаливый $0).
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
- White Paper: v0.2.1 написан 2026-07-13 по слову оператора («пиши
  v0.2.1, ревью сделаю сразу по ней») — evidence-апдейт 07-11..13:
  калибровка, тулкит v0.1.0 + обе установки, платный источник и
  4х-reject coding->Middle, C3=0.11% прямым замером, гейт-решение
  Phase 2, D-0069..75, F-37/38. AWAITING Architect review v0.2.1
  (цель ревью смещена с v0.2.0 её же словом).

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
- УРОК ДЕПЛОЯ (2026-07-13, стоил ~$0.3 дублей): правка gateway-кода
  (sqlite_logger/колбэки) при ЖИВОМ прокси не действует до рестарта
  прокси — процесс держит старый модуль; тесты это не ловят по
  построению (грузят свежий код). После правки gateway/*.py при
  активном API-окне: рестарт прокси оператором МЕЖДУ ходами сессии
  (сессия не убивает прокси сама — режет собственный стрим), затем
  PRAGMA/смок-сверка.
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
