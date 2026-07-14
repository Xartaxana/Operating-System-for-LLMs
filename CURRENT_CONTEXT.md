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

ЖИВАЯ ЗАДАЧА: пилот носителя task-графа — неделя калибровки ~07-18
(workstream 3, D-0059). DAG: docs/tasks/2026-07-13_calibration-week.md.
N1 закрыт (t-090); N2–N5 ждут окна ~07-18. Ключевой вход N3: stage-2
цикл №1 завершён 2026-07-13 — прогон №3 rejected, ЧЕТВЁРТЫЙ подряд
reject-сигнал coding->Middle, R1 coding = 31 пара / 6 прогонов —
объём набран (порог 30/2); оговорка distinct-промптов (11/19) и
строки прогонов — docs/SHADOW_EVALUATION_LOG.md; статус двигает
только калибровка (кандидат-вердикт rejected).

MIDDLE-КАНДИДАТЫ: закрытая часть дня 07-13 — VERBATIM в
docs/task_reports/2026-07-13_middle-candidates-judge-haiku.md (там
же схема $0 судей и кандидат opus-4-8). Повтор A 07-14 НЕВАЛИДЕН
(defect_found ref=t-091, журнал 14:14): авто-floor max_tokens 8192
сам превышает Groq TPM 8000 — 0/6 пар, судья не задет; разбор —
SHADOW_EVALUATION_LOG «MIDDLE-КАНДИДАТЫ»; рекомендация Lead —
вердикт «инфра-непригоден» по прецеденту t-063. На калибровку
~07-18: override vs инфра-непригодность middle-oss (со статусным
ходом coding->Middle), C3/F-40, judge_pair без max_tokens.

API-ОКНО ЗАКРЫТО 2026-07-13 ($170.44, прокси опущен, сессии на
подписке) — дословно: docs/task_reports/2026-07-13_api-window-night.md
+ 2026-07-12_api-window-prep.md.

BOOT-БЮДЖЕТ: раунды 5–7 — 07-13/14; раунд 8 (диета после текстов
D-0076, пробой 102.6К) — 07-14. Резерв при новом росте — ROADMAP
17.3К, отдельным предложением Lead+Architect.

Действующие рамки: ТУЛКИТ-МОРАТОРИЙ D-0074 (правка toolkit/ —
только проверенным батчем по слову оператора; порт-очередь ниже).

Закрытое 07-11/12 — индекс docs/task_reports/README.md
(единственный владелец). Живой остаток: t-066 (golden set 6/7,
Q3 PASS) для чека 14в; «haiku сохраняем» в силе.

ПРИОРИТЕТ ОПЕРАТОРА 07-11: текстовые задачи builder-groq по ходу
(прокси опущен — на паузе). Прочее: draft-C и WP v0.2.1 — у
оператора; старая очередь — on-touch/evidence-gated.

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
  дивергентна — своя сигнатура phase2_readiness); (7) F-39 фикс
  shadow_eval (max_tokens в replay + truncated-счётчик, t-091) —
  копия toolkit/gateway/shadow_eval.py несёт тот же класс дефекта;
  (8) конвенция лейбла диспатча «модель: …» в правиле 7 политики
  (слово оператора 2026-07-13) — та же строка в toolkit/CLAUDE.md
  (EN); (9) ретро-контур калибровки (чеки 0/19–24 +
  docs/RETRO_PATTERNS.md) и gotcha-принцип onboarding-доков — порт
  в toolkit/PROCESS после >=1 прожитого прогона (~07-18);
  (10) экзамен экономии деплоя: прогон №1 (v0.1.0) ВЫПОЛНЕН
  2026-07-14, итоги — Runs log PROCESS/DEPLOYMENT_ECONOMY_EXAM.md
  (владелец цифр); следующий — после следующего релизного снимка
  (чек 14е); решение о поставке в шаблон — тем же батчем;
  (11) UI-witness строка правила 2 (вождение UI, скрин «до/после») —
  та же в toolkit/CLAUDE.md (EN); (12) toolkit/tools/usage_report.py
  + тесты — копия несёт F-42 (старый глоб subagents/*.jsonl,
  сверено critic t-093 байт-в-байт) и F-43 (first-occurrence дедуп)
  — порт фикса t-093 и будущего t-094 одним батчем;
  (13) из внешнего ревью (триаж 07-14): privacy-режимы sqlite_logger
  (no-raw-text + fingerprints + TTL/purge; дефолт — решение
  оператора) и onboarding-пробы моделей; в DoD батча — hash-сверка
  корень↔toolkit + манифест намеренных расхождений;
  (14) D-0076/F-44: правило порядка в toolkit/CLAUDE.md (EN),
  worker_ref в валидатор, OPEN DISPATCH в session_context, чек
  13(и) в протокол — после проживания у нас >=1 недели.
  Новых правок toolkit/ не
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
- ВНЕШНЕЕ РЕВЬЮ 07-13 закрыто (триаж
  docs/task_reports/2026-07-14_external-review-triage.md; t-095
  принят — находки 2/11). На калибровку: staleness цен + economic
  margin; порт-п.13; 7/10 не берём (триггеры в триаже).
- КАНДИДАТ ПОВЕСТКИ КАЛИБРОВКИ ~07-18 (предложение Lead 2026-07-14,
  слово оператора НЕ дано — решить на разборе): формализовать
  скип-порог числом на данных чеков 19/21/22 (сейчас порога нет:
  «~4 известных целей» у разведки, неписаное «правка меньше
  диспатча» у builder-класса; экзаменные ~10 мин — про вал системы,
  не про маржинальный скип). Также на разборе: находки прогона №1
  экзамена (F-41/42/43), ступенька экономтренда после backfill
  t-094 (+$57.5 к сайдчейнам — не рост расхода, коррекция учёта).
- ПИЛОТ OPUS-ДИЗАЙНЕРА ОТКРЫТ 2026-07-14 (слово оператора):
  docs/tasks/2026-07-14_opus-designer-pilot.md — N≈5 спек
  чередованием (fable-контроль / opus-дизайнер с блоком развилок)
  до ~07-18; разбор и решение — калибровка (чек 0 держит пункт);
  строка таблицы designer=estimated; пометка-пилот в правиле 2.
- РЕТРО-БЭКЛОГ КАЛИБРОВКИ: docs/RETRO_PATTERNS.md (12 паттернов с
  именованными триггерами, порядок важности — слово оператора
  2026-07-13; триггеры сверяет чек 0 протокола). Оттуда же:
  UI-witness «до/после» (расширение D-0052) — ВНЕДРЁН в приёмку
  экзамена 2026-07-14 (протокол, прецедент C-T1: визуальный дефект
  мимо кодовой приёмки, скрин оператора); для AO3-конвейера триггер
  прежний (первый UI-диспатч).
- AO3-ПОРТ D-0076 (ось 1; инцидент F-44 — там; исполняет сессия
  AO3 по слову оператора): правило порядка + worker_ref в
  log_append.py (их кодовый гейт при append) + сверка открытых
  диспатчей в хук/handoff; заодно давний остаток by/basis +
  continuation/retry ветки.
- Evidence-gated residuals (каждый — на своём триггере): provider
  column in sqlite_logger (N1/N2 root, axis 2); requests(model,ts)
  index (только на latency evidence);
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
- Habr/LinkedIn (t-036): статья оператора вычитана 07-14 (docx
  сессии не правят); EN-перевод: D:\Improving_AI\How I keep an eye
  on AI (EN).docx; денежная фраза подтверждена (КАССА выше). NEXT:
  публикация — слово оператора. Материалы:
  docs/ARTICLE_BRIEF_2026-07-10.md + draft-{A,B,C} + журнал t-036.
- White Paper: v0.2.1 написан 2026-07-13 по слову оператора («пиши
  v0.2.1, ревью сделаю сразу по ней») — evidence-апдейт 07-11..13:
  калибровка, тулкит v0.1.0 + обе установки, платный источник и
  4х-reject coding->Middle, C3=0.11% прямым замером, гейт-решение
  Phase 2, D-0069..75, F-37/38. AWAITING Architect review v0.2.1
  (цель ревью смещена с v0.2.0 её же словом).

## Environment Notes (this machine)

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
