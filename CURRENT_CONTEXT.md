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
решения — ROADMAP.md «Gate decision 2026-07-13»; полный отчёт —
docs/task_reports/2026-07-13_phase2-gate-report.md). Телеметрические
циклы (еженедельная калибровка ~07-18, тренд экономии) — штатные
операции. Plan of record: docs/UNIFIED_PLAN_2026-07-07.md; гейты
Phase 2 — ROADMAP.md.

## Current Task (Authoritative, D-0025)

ПЛАН СЕССИИ (слово оператора 07-16 ~15:30): пп.1–2 ВЫПОЛНЕНЫ 07-16
вечером (сессия приёмки):
1. [DONE] t-159 принят (critic-вход, 1 блокер D-0043 дочинен Lead),
   kit v5 запинован @ 46fb7a1.
2. [DONE] Перенос в основу: (а) 5 гейтов в tools/ + 131 тест t-161
   (610 passed) + АКТИВАЦИЯ .claude/settings.json — гейты гейтят все
   штабные сессии с 07-16 (коммит 19b4c91; .jsonl-фикс doc-only —
   правка Lead при приёмке; детектор — чек 26, пара kit<->штаб —
   ось 4 карты); (б) критик-на-план в правило 3 (ef30590, детектор —
   чек 2); (в) critic.md правила 13/14 + кейсы б/г CRITIC_EXAM +
   regression-прогон N1 PASS t-162 (2f082c7).
3. ПРОГОН №11: малый экзамен (набор №1) с обновлённой основой
   (B = штаб + гейты + новый critic.md; kit v5 @ 46fb7a1) —
   очередная точка медианы. ЖДЁТ СЛОВА.
   Живые смоки гейтов 07-16 (первая сессия): file_path-контракт
   подтверждён (11 edits с путями), agent_id=null у main подтверждён,
   Stop-события main_gate живьём (3 блока). ГЛАВНАЯ НАХОДКА первой
   сессии — КЛАСС t-151 «enforcement тихо-успешен вне среды» ПОЙМАН
   ЖИВЬЁМ И ЗАЧИНЕН: tool-matcher'ы гейтов были под kit-среду
   (CLI-песочницы: Bash, Task), штабная среда даёт PowerShell и
   Agent → прогоны штаба были НЕВИДИМЫ треку (runs=[] при фактически
   зелёных прогонах — все 3 блока no-green-run), Task-хуки не
   стреляли на Agent-диспатчи (critic_snapshot отсутствовал). Первые
   два нарратива Lead о блоках (dotfile/doc-only) были НЕВЕРНЫМИ
   прочтениями — опровергнуты форензикой трека (рецидив класса
   «прочтение Lead vs форензика», №9/№10 — в чек 25). Фикс 07-16:
   matcher'ы Task|Agent и +PowerShell, dod_track ветка PowerShell +
   2 теста; подхват подтверждён живым green run в треке. Kit НЕ
   тронут (его среда Bash/CLI — признанное отличие пары, докстринг).
   НАХОДКИ о гейтах (чек 26в) на калибровку ~07-18: (1) dotfiles без
   суффикса → fail-closed (грань дизайна; цена ~3с, Rule #1 может
   сказать «не чинить»); (2) doc-only «целиком-или-никак» — одна
   не-doc правка в треке лишает освобождения весь хвост сессии;
   (3) gate_log без ts — форензика хромает (записи не датированы);
   (4) dod_gate (SubagentStop) видит и MAIN-правки трека → в штабе с
   Lead-самоисполнением даёт блоки субагентам за чужие правки —
   кандидат разделения поверхностей (dod_gate = только agent_id!=
   null, main-правки = зона main_gate); (3)/(4) — механизменным
   касанием гейтов с тестами, не спешкой.

ЖИВАЯ ЗАДАЧА: пилот носителя task-графа — неделя калибровки ~07-18
(workstream 3, D-0059; DAG: docs/tasks/2026-07-13_calibration-week.md;
N1 закрыт, N2–N5 ждут окна). Вход N3: 4-й подряд reject-сигнал
coding->Middle, R1 = 31 пара / 6 прогонов — объём набран (порог
30/2); оговорки и строки — docs/SHADOW_EVALUATION_LOG.md; статус
двигает только калибровка.

MIDDLE-КАНДИДАТЫ: закрыто — архив 2026-07-13_middle-candidates-…md
+ SHADOW_EVALUATION_LOG. На калибровку ~07-18: override vs
инфра-непригодность middle-oss (статусный ход coding->Middle),
C3/F-40, judge_pair без max_tokens.

API-ОКНО ЗАКРЫТО 2026-07-13 ($170.44, прокси опущен, сессии на
подписке) — дословно: docs/task_reports/2026-07-13_api-window-night.md
+ 2026-07-12_api-window-prep.md.

BOOT-БЮДЖЕТ: раунды 5–11 — 07-13..15 (последний крупный: D-0078
глубокий срез ROADMAP 17.3К->10.1К, архив
docs/task_reports/2026-07-15_roadmap-closed-phases.md); текущие
мелкие развёртки — по ходу сессий (архив закрытого + указатель).

Рамки: ТУЛКИТ-МОРАТОРИЙ D-0074 (toolkit/ — батчем по слову;
порт-очередь ниже).

Закрытое 07-11/12 — индекс docs/task_reports/README.md. Живой
остаток: t-066 (golden set 6/7, Q3 PASS) для чека 14в; «haiku
сохраняем» в силе. ПРИОРИТЕТ 07-11: текстовые задачи builder-groq
по ходу (прокси на паузе); draft-C и WP v0.2.1 — у оператора;
старая очередь — on-touch/evidence-gated.

## Routing MVP — LIVE on both deployments

- Pilot: D:\AO3_tests (2026-07-07, commit b8125a0). Reference/
  dogfooding: THIS repo (2026-07-08). Each = auto-loaded CLAUDE.md
  policy + agents scout/builder/critic + logs/routing-log.jsonl
  (D-0041: always the three together).
- Policy text ARCHITECT-ACCEPTED 2026-07-09 (171078c); later policy
  changes follow the mechanism discipline.
- Evidence stream: logs/routing-log.jsonl (t-001..t-095); Claude-
  контурные строки таблицы provisionally_validated с первой
  калибровки 2026-07-11 (Update Rule 1, D-0047; evidence-блок в
  DELEGATION_TABLE.md).
- Retro baseline AO3 (cc_usage, pre-routing): $276.70 accounted +
  $57.82 sidechain self-correction (Task 6). Weekly loop compares
  cost per accepted unit + escalation rate, NOT frontier share alone
  (Architect correction — see baseline section below).
- Первая калибровка 07-11; вторая ~07-18 (трендовые чеки против
  baseline первого прогона; staleness — Boot Report, D-0047).

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
  (381 passed на 2026-07-14); toolkit suite отдельно;
  gateway/conftest.py изолирует каждый тест.
- DELEGATION_TABLE.md: 4-state (D-0035). provisionally_validated:
  coding->Middle, summarization/extraction/formatting->intern, все
  4 строки Claude-контура (калибровка 07-11); rejected:
  classification->intern. Reject-тренд по coding->Middle — см.
  Current Task (4 подряд, R1 набран); решает калибровка ~07-18.

## Claude Code Baseline (Task 5, 2026-07-07 — live guidance)

- КАССА ПОДТВЕРЖДЕНА 2026-07-14 (скрин оператора, Usage credits):
  €1,253.33 кредитов сверх подписки за ~неделю (сброс Aug 1).
  Учётные за то же окно 07-07..14: $2,422.95 (usage_report --days 7;
  этот репо $1,959; cache-read 95.9%). Учётное > кассы — разницу
  поглощает подписка; биллинг сессиям НЕ виден, источник — только
  оператор. Вход для R5 и чеков 10/11 калибровки ~07-18.

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

- WORKSTREAM 3 — оценка носителей закрыта 07-13
  (docs/TASK_CARRIER_EVAL_2026-07-13.md); ПИЛОТ ОТКРЫТ (полигон —
  задачи репо/AO3, НЕ тулкит; слово оператора):
  docs/tasks/2026-07-13_calibration-week.md — N1/N4 закрыты (статусы
  и досрочность N4 — в DAG-доке и приложении гейт-отчёта), N2/N3/N5
  ждут ~07-18; AO3 — кандидат второй точки; adoption — разбор N5.
- Упрочнение tier-гейта (builder-class; WHEN: на evidence первого
  инцидента — Rule #1, критик t-068 находка 2 пометил не-блокером):
  find_tier_declaration матчит ПЕРВУЮ строку `tier:` — сообщение с
  посторонней строкой, начинающейся с tier:, даёт ложный reject;
  фикс — матчить любую удовлетворяющую строку.
- ТУЛКИТ: релиз v0.2.0 вышел 07-14 (снимок 2200900; батч VERBATIM —
  docs/task_reports/2026-07-14_toolkit-v020-divergence-manifest.md).
  ПОРТ-ОЧЕРЕДЬ: п.9 ретро-контур (после >=1 прожитого прогона
  ~07-18); п.13 privacy-режимы (дефолт — решение оператора);
  п.15 permission-audit (t-107) — после проживания в корне; п.16
  builder-правило финальной сдачи (builder.md п.7); п.17 правило 11а
  маршрутизации вопросов (D-0077); п.18 хук-строка BREACH без
  императива + порядок запуска boot-diet в свежей сессии
  (session_context.py + SKILL.md, прецедент 07-15) + ветка
  replaces_worker валидатора/политики (t-127/t-129, если валидатор в
  ките) + DoD-батарея интерактивных поверхностей (правило 11,
  прецедент 9**9**9) + самопроверка диспатчера (правило 11, 07-16);
  п.19 policy-as-code гейты (5 хуков + штабные тесты + чек 26 +
  критик-на-план правила 3 + critic.md 13/14 — после проживания в
  штабе >=1 календарного окна, активированы 07-16).
  Мораторий D-0074 в силе: правок
  toolkit/ не делать — ось 7 отвечается «в очередь порта» сюда.
- СЕРИЯ №1–№4 ЗАКРЫТА 07-15 (табель 6б, метод метрики 4, протез,
  каденция раннер+Sonnet, D-0077; разборы —
  docs/tasks/2026-07-15_economy-exam-runs3-4.md + …run2.md; VERBATIM
  недели — docs/task_reports/2026-07-15_exam-week-context-closures.md).
  ЖИВЫЕ ОЧЕРЕДИ: window_load LIKE-исключение + ассерт «id без
  дефисов» (t-126, ось 2);
  AO3 — builder.md п.7-класс + правило 11а + ветка replaces_worker
  в их log_append.py и CLAUDE.md + DoD-батарея интерактивных
  поверхностей + самопроверка диспатчера (правило 11, 07-16) +
  правило 3: эмпирика-первым-шагом и DoD-самопрогон (07-16) в их
  правило 11/3 + ПРОВЕРКА log_append.py на класс «enforcement
  тихо-успешен вне среды» (критик t-151: не подтверждено, не
  опровергнуто) (их сессией или Lead при касании) +
  правило 3: критик-на-план (07-16) + порт policy-as-code гейтов
  (паттерн t-159/t-161: staging → ревью адаптаций Lead → тесты →
  активация settings их Lead'ом; штабные адаптации — образец) +
  critic.md правила 13/14 (семантика поля эмпирикой; поверхность
  дефекта) с прогоном их критик-регрессии;
  аналитика ретраев/холодного старта и окна прогонов в notes —
  калибровке.
- НАБОР №2 ЗАКРЫТ 07-16 (№5 0.64/0.70/0.70, №6 0.72/0.86/0.82,
  $128.69): docs/tasks/2026-07-15_economy-exam-runs5-6.md + Runs
  log. ОСТАТОК: раннер «пустой stdout при rc=0» — фикс в очереди;
  калибровке — синтетика окон (D-0075), счётчик возвратов, «Sonnet
  не держит текстом» в D-0058-разбор.
- ЭКЗАМЕН-СЕРИЯ 07-16 ЗАКРЫТА (№7–№10б; разбор+очередь v5 целиком —
  docs/tasks/2026-07-16_economy-exam-run7.md + строки Runs log).
  Диета критика закрыта (0.93/0.91/0.85/0.65); «текущее+гейты»:
  дисперсия ×2.6 — решает медиана калибровочных малых экзаменов.
  Устойчиво: 0 ложных блоков/4 прогона; снимок/standalone-валидатор/
  форензика работают; main-сессия — слепота (4 подтв.). Kit'ы:
  fullgates v4.1 @ 42b6812, diet v3 @ 61f3c8d. ОЧЕРЕДЬ v5 —
  6 пунктов в разбор-доке (Stop(main)-гейт; RE-заплатки; кириллица
  stdin; снимок-continuation; КРИТИК НА ПЛАН — слово 07-16; чек
  kit-сборки). Эмпирика+DoD-самопрогон ПЕРЕНЕСЕНЫ В ОСНОВУ
  (правило 3, слово 07-16).
  Порт гейтов в штаб/тулкит — слово оператора. Большой прогон — по
  каденции. РЕЗЕРВ — генератор сайта.
- A5 witness auto-collection (builder-class; WHEN: first REAL
  builder-Pi work cycle — Rule #1: no wrapper before there are
  sessions to wrap; binding decided at calibration): wrapper runs
  the canonical pytest form after a Pi builder session and attaches
  verbatim output as a witness DRAFT; acceptance stays with Lead.
- Уроки ярусам F-38 + 9**9**9 — ЗАКРЫТО 07-16 (коммит 2f082c7):
  (а)/(в) = critic.md правила 13/14, (б)/(г) = кейс-кандидаты
  CRITIC_EXAM, regression-прогон N1 PASS (t-162, Runs log). ЖИВОЙ
  остаток: кандидат (№9) DoD-самобатарея «уже выбранной формы»
  (гоняла «число OP число» — 2+2*2 прошёл мимо) — builder/DoD-класс
  (правило 11), не critic.md; на разбор калибровки.
- ВНЕШНЕЕ РЕВЬЮ 07-13 закрыто (триаж
  docs/task_reports/2026-07-14_external-review-triage.md; t-095
  принят — находки 2/11). На калибровку: staleness цен + economic
  margin; порт-п.13; 7/10 не берём (триггеры в триаже).
- КАНДИДАТЫ ПОВЕСТКИ КАЛИБРОВКИ ~07-18 (слово оператора не дано —
  решать на разборе): скип-порог числом (чеки 19/21/22); находки
  №1 (F-41/42/43); ступенька экономтренда после backfill t-094
  (коррекция учёта, не рост); первый прогон чека 25 + находки
  t-106 — промоушен-кандидат PreToolUse-хук против cd-префикса/2>&1
  (76% подозрительных вызовов, гл. нарушитель Lead; Rule #1 решает);
  фикс-у-источника ad-hoc Bash-чтений и разноформенного pytest.
  ПЛЮС от 07-15/16: рецидивы Lead (F-30 числа-до-замера ×2,
  append-якорь ×4, python-c ×2 — чек 25); счётчик возвратов
  воркеров; «Sonnet не держит текстом» в D-0058-разбор; синтетика
  окон экзаменов №5–№10б (D-0075).
- ПИЛОТ OPUS-ДИЗАЙНЕРА открыт 07-14:
  docs/tasks/2026-07-14_opus-designer-pilot.md — N≈5 спек
  чередованием до ~07-18; разбор — калибровка (чек 0);
  designer=estimated; пометка-пилот в правиле 2.
- РЕТРО-БЭКЛОГ: docs/RETRO_PATTERNS.md (чек 0); UI-witness в AO3 не
  прожит — первый их UI-диспатч = проба; F-41-стейлы — чек 24.
- AO3-ПОРТ D-0076 — ЗАКРЫТ 07-14 (t-100, critic ACCEPT, AO3-коммит
  1cfb8f8 запушен). Живой остаток по построению: порт-событие в ИХ
  журнале пишет их сессия (D-0060).
- Evidence-gated residuals — 9 пунктов, каждый на своём триггере:
  полный список VERBATIM —
  docs/task_reports/2026-07-16_evidence-gated-residuals.md.
- Eval plan stage 2 — В РАБОТЕ (цикл №1 07-13, конвейер d90cd03).
  Остаток: minimum-n/pass^k в Update Rules + numeric agreement в
  JUDGE_CALIBRATION_PROTOCOL (пороги с калибровки). NOT taken:
  per-PR CI, bench-harness (Rule #1). Batch API (одобрен 07-10):
  TRIGGER = реплеи регулярны; учётный путь requests.db тем же
  ходом (ось 2, никогда молчаливый $0).
- NOT adopted (чтобы не пересуживать): GSD-координатор, auto-mode
  SQLite/crash recovery, supply-chain tags, WXP; OpenClaw: channels,
  delegate identity, compaction/memory, utilityModel. Обоснования —
  RELATED_WORK «OpenClaw survey» + evening-closures.
- Habr/LinkedIn (t-036): статья вычитана 07-14, EN-перевод готов;
  NEXT: публикация — слово оператора (материалы —
  docs/ARTICLE_BRIEF_2026-07-10.md + draft-{A,B,C}).
- White Paper v0.2.1 написан 07-13 — AWAITING Architect review
  (кандидат-апдейт v0.2.2: экзамены №5–№10б, policy-as-code,
  D-0076..79 — после ревью).

## Environment Notes (this machine)

- ALLOWLIST СУЖЕН 2026-07-14 (слово оператора «да сужай до дефолта»):
  из .claude/settings.local.json удалены 4 правила произвольного
  выполнения (Bash(python *), два python -c, python -) — взамен узкий
  канон (обе pytest-формы, journal_validator, permission_audit *,
  json.tool *). MASKED-блок аудита пуст. Следствие: ad-hoc python -c
  теперь спрашивает — это штатное детекторное поведение (чек 25), не
  регресс; настройки перечитываются новыми (суб)агентами.

- Ollama 0.31.1 (winget); NVIDIA driver 582.28 — Qwen3-4B runs 100%
  on the GTX 1060 GPU (~5 s warm vs ~15 s CPU).
- ПРОКСИ — КОНВЕНЦИЯ ВЛАДЕНИЯ (слово оператора 2026-07-13): при
  длительном простое прокси ВЫКЛЮЧАЕТСЯ (оператором или сессией) и
  поднимается заново под конкретный прогон — никто не знает, когда
  будет следующая сессия. Следствие для сессий: НЕ предполагать
  состояние прокси («оставлен запущенным» не значит «запущен») —
  перед прогоном поднять/health-check, после блока работ погасить.
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
