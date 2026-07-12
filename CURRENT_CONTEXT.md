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
Остатки в очереди: регресс-тест стриминга ЗАКРЫТ (t-077,
gateway/test_stream_cache_logging.py, 5 тестов) + metrics.py-нарратив
кэш-колонок ЗАКРЫТ (t-078, cache_read/creation + cache_read_share,
знаменатель согласован с usage_report.py по оси 2) — оба 2026-07-12
opus-координатором в API-окне, приняты по witness (105 passed;
t-078 через critic-вход, attempt 1 rejected = ошибка Lead-спеки).
Остаток тегирования synthetic (смок 22:19 -> real) поднят в очередь
Lead как механизм (ось 2, вместе с F-37) — см. Remaining Lead-tier
Queue. Параллельно одобрен первый цикл stage-2 реплеев — открыть
следующей сессией.
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

## Phase 2 Gate Report — 2026-07-12, ОБНОВЛЁН 2026-07-13 ~00:20 (по команде оператора; ЖДЁТ ПОДПИСИ Architect)

Первичный замер 2026-07-12 15:51; ПЕРЕСМОТР 2026-07-13 по слову
оператора — после открытия API-окна (~22:15) через шлюз пошёл живой
платный трафик с кэш-колонками (t-075), что изменило вычислимость
R2/R3/C3. Все числа — прямые измерения 2026-07-13 00:0x
(gateway/metrics.py --days 14 пересчитан; SQL по requests.db;
агрегация routing-log). Пересмотр вскрыл F-38 (двойной счёт в
cache_read_share дайджеста; чинится t-080 параллельно отчёту —
числа ниже посчитаны ВЕРНОЙ формулой напрямую SQL).

**Общий гейт: ЗЕЛЁНЫЙ (окреп).**
- G1: met — 16 непрерывных real-дней из 14 требуемых (union
  requests real + cc_usage; дайджест 00:0x). Строки requests-real
  очищены от смок-примеси ретегом D-0075 (id 512–526 -> synthetic).
- G2: met — judge-groq 13/13 (последнее подтверждение — калибровка
  2026-07-11).

**Router гейт: КРАСНЫЙ (не открывается), но вычислимость пришла.**
- R1: NOT met, без изменений — coding: 6 judged-пар / 3 прогона при
  пороге >=30 (новых реплеев с 07-12 не было; фидер — stage-2
  реплеи, одобрены, открыть следующей сессией).
- R2/R3: были «не вычислимы» (0 категоризуемых real-строк) — ТЕПЕРЬ
  вычислимы впервые: API-окно дало 345 real-строк requests с
  промпт-контентом за 5 дней (248 за вечер 07-12 + окно живёт).
  Первый честный срез — калибровкой ~07-18 (окно к тому моменту
  закроется, срез будет полным). Известный residual: строки
  readiness-блока дайджеста для R2/C3 печатают протухшую ветку
  «currently 0 real rows» — противоречит собственному C1 того же
  прогона (92% на real); фикс ветки — в очереди ниже.
- R4: не вычислим (нужны R1-R3 + проектная стоимость роутера).
- R5: MET ФАКТОМ, сильнее прежнего — paid Lead В ПРОДАКШЕНЕ прямо
  сейчас: API-окно активно, интерактивные сессии (fable/opus) идут
  через шлюз на предоплаченных кредитах; расход окна $29.89 за
  первый вечер (22:15–00:0x, измерено requests.db). При красном R1
  по-прежнему не решает.

**Context management гейт: НЕ открывается — теперь ПРЯМЫМ
измерением на шлюзе, не оценкой.**
- C1: met, окреп — 92% context-repetition на real-строках requests
  (было 77% на ~22 запросах lead-gemini; теперь дайджест по
  сотням строк живого трафика).
- C2: met — 58 real-сессий >=5 ходов за 14 дней (порог >=20;
  было 50).
- C3: NOT met — ПРЯМОЕ cache-aware измерение окна (requests.db,
  real, с 22:15, все строки с кэш-колонками, NULL=0): input-сторона
  27.59M токенов, из них cache_read 26.51M (96.1%), cache_creation
  1.05M (3.8%), ИСТИННО некэшированный оплаченный input 29,350
  токенов = 0.11% при пороге >=25%. Семантика поля проверена
  эмпирически (prompt_tokens инклюзивен, F-38). Прежняя оценка
  сверху (~33% через cache-write'ы) снята прямым замером:
  провайдерский кэш работает и СКВОЗЬ прокси — деньги с этого
  стола сняты. Реанимация C-гейта — только решением Architect.

**Task pipeline гейт (D-0059): ЗЕЛЁНЫЙ (окреп).**
- P1: met — 10 задач с >=5 журнальными событиями за окно (t-015:9,
  t-037/t-043/t-057:7, t-009:6, t-002/t-018/t-062/t-063/t-078:5)
  при пороге >=3; плюс сквозные семейства (конвейер t-045..t-053,
  батч 5б, цепочка API-окна t-075..t-080) через >=2 сессии.
- P2: met — драйверные примеры прежние: defect_found t-029 (дубль
  task_id на границе перезапуска) + finding F-36 (шаг «в очередь
  Lead» без носителя между сессиями) — класс «зависимость/scope
  потерян на границе». Всего defect_found в окне теперь 5 (плюс
  F-29-ts, t-002-R1, F-37, F-38) — но три новых относятся к классу
  «честность измерения», в P2-драйвер их не записываем.
  decomposable=0 (вторая ветка P2 не задействована).
- P3: met ПО ОЦЕНКЕ Lead (проекция по определению): upkeep =
  строки брифа/очереди, которые Lead уже пишет в CURRENT_CONTEXT;
  rework в окне — ремонт t-029 + батч фиксов F-36.

**Предложение Lead (без изменений после пересмотра):** открыть
ТОЛЬКО workstream 3 (task pipeline); первая задача — ОЦЕНКА
существующих носителей task-графа (нативные task-тулы Claude Code
vs markdown-шаблон в PROCESS/) на одной реальной многосессионной
задаче, НЕ стройка (D-0030; порядок D-0059: brief → DAG → allocate
→ код последним). Router — ждать R1 (30 пар придёт с stage-2
реплеями; R2/R3 впервые вычислимы срезом калибровки ~07-18);
Context — закрыт ПРЯМЫМ измерением (C3 = 0.11% при пороге 25%),
реанимация только решением Architect.

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
- ОСЬ 2 / traffic_kind + F-37 — ЗАКРЫТО 2026-07-12 Fable-батчем
  (D-0075): дефолт 'real' остаётся (записанный выбор — органика
  passthrough не тегается), не-органические генераторы самотегаются
  (tools_stream_check.py закрыт t-079), смок-пачка id 512–526
  ретегирована synthetic громко, MODEL-строка хука несёт маркер
  «declared by harness, not measured -- F-37» (in-hook сверка с
  измерением отвергнута как нереализуемая на SessionStart —
  аддендум F-37). Детекторы: чеки 13(з) НОВЫЙ / 13(ж) / 5.
  Порт конвенции в toolkit — в порт-очередь ниже (D-0074).
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
  у нас. Новых правок toolkit/ не
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
