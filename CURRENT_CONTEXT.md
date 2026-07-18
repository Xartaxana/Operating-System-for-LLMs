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
циклы (еженедельная калибровка; №2 выполнена 07-18, следующая
~07-25; тренд экономии) — штатные операции. Plan of record: docs/UNIFIED_PLAN_2026-07-07.md; гейты
Phase 2 — ROADMAP.md.

## Current Task (Authoritative, D-0025)

СЕССИЯ 07-16 ВЕЧЕР ЗАКРЫТА ЦЕЛИКОМ (t-159..t-172; гейты активны
19b4c91, тулкит v0.3.0, порт-батчи AO3) — VERBATIM:
docs/task_reports/2026-07-16_evening-closures-port-run11.md.
ОЧЕРЕДЬ ГЕЙТ-КАСАНИЯ (механизменно, с тестами; калибровка №2
подтвердила — ложных блоков сверх этих находок нет): (1) dotfiles
fail-closed (Rule #1 может сказать «не чинить»); (2) doc-only
«целиком-или-никак»; (3) gate_log без ts/agent_id; (4) предохранитель
consecutive_blocks session-global при per-agent решении + kit-сиблинг
dod_gate; на kit-касание также staging_hq/ не в песочницы + red-run
t2 флаг; «OPEN DISPATCH» хука не парсит закрытие-notes (10 ложных
«висяков» на боте 07-18) — фикс при касании session_context.
HYGIENE_GATE АКТИВЕН с 07-18 (t-177, warn-режим, живой смок в
сессии приёмки): не-блокеры критика при касании — литеральные
ложные срабатывания (warn-безвредны), python3 -c, doc-note;
сиблинг toolkit без hygiene_gate — порт-очередь D-0074.

ДЕНЬ 07-18 ЗАКРЫТ ЦЕЛИКОМ (калибровка №2 + D-0080/D-0081 + экзамены
№12–№14 + порты; VERBATIM — 2026-07-18_calibration2-closures.md +
2026-07-18_evening-run-series.md; t-173..t-193). ЖИВОЕ:
- coding->Middle REJECTED (fcef414); Router закрыт; пилот носителя
  закрыт, adoption = правило 4а (D-0080).
- D-0081 батчинг ВВЕДЁН; проверка — чек 22 против baseline 16.
- hygiene_gate АКТИВЕН (warn); не-блокеры при касании (литеральные
  ложные срабатывания, python3 -c).
- Shadow-реплей Lead-работ: 5/8 equivalent (стенд lead_replay.py;
  интерпретация с оговоркой накладных — калибровке №3).
- Экзамены: №12 Fable 0.95/$27; №13 A/Bfg4/C + №13c2 (политика 0.95
  против C 0.39–0.59 — подтверждено перезапуском); №14 critic-lite
  0.95/$11.43 (−37%) → ПОРТ пп.2–4 В ШТАБ 9a64c4d (регрессия
  критик-экзамена PASS t-192) И В AO3 bec081f (t-193). РЕЕСТР
  docs/EXAM_RESULTS.xlsx — живой (норма протокола, по-задачные
  скаляр/F). Кит экзамена = ветка штаба по умолчанию.
ОЧЕРЕДЬ 07-18: №15 — вторая точка critic-lite (калибровка №3);
экзамен Sonnet-координатора ждёт естественного батча (D-0080 п.4);
Get-Date в allowlist — решение оператора; опус-дизайнер продлён до
№3; чек-25-счёт сессии: F-30 ×3 (пересказ A-t1 defect_found t-185;
зелёный-до-замера ×2), python-c ×2, append-якорь ×1; шумная граница
decomposable (2 неоснователь­ных из 5, t-186/t-191) — кандидат
builder.md «возврат после пробы»; owns-пути в манифестах —
АБСОЛЮТНЫМИ (2 промаха грейдеров). AO3-ОЧЕРЕДЬ (их Lead): приёмка
окна 07-18 обязана включить bec081f + d951844 (F-47); hygiene_gate
адаптация под их канон; docs/06 «[план] board-inbound» протух;
at-bug-014 утечка кодификации; промпт-правка device-QA. Следующая
калибровка ~07-25.

API-ОКНО ЗАКРЫТО 2026-07-13 ($170.44, прокси опущен, сессии на
подписке) — дословно: docs/task_reports/2026-07-13_api-window-night.md
+ 2026-07-12_api-window-prep.md.

BOOT-БЮДЖЕТ: история раундов — коммиты диет; текущие мелкие
развёртки — на handoff (архив закрытого + указатель).

Рамки: ТУЛКИТ-МОРАТОРИЙ D-0074 (toolkit/ — батчем по слову;
порт-очередь ниже).

Закрытое 07-11/12 — индекс docs/task_reports/README.md; «haiku
сохраняем» в силе; старая очередь — on-touch/evidence-gated
(приоритеты 07-11 исчерпаны, драфты у оператора).

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
- Первая калибровка 07-11; вторая ВЫПОЛНЕНА 07-18 (calibrated в
  журнале); третья ~07-25 (staleness — Boot Report, D-0047).

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
  summarization/extraction/formatting->intern + все 4 строки
  Claude-контура (калибровка 07-11); rejected:
  classification->intern, coding->Middle (калибровка №2 07-18,
  fcef414 — на текущих привязках; evidence SHADOW_EVALUATION_LOG).

## Claude Code Baseline (Task 5, 2026-07-07 — live guidance)

- КАССА ПОДТВЕРЖДЕНА 2026-07-14 (скрин оператора, Usage credits):
  €1,253.33 кредитов сверх подписки за ~неделю (сброс Aug 1).
  Учётные за то же окно 07-07..14: $2,422.95 (usage_report --days 7;
  этот репо $1,959; cache-read 95.9%). Учётное > кассы — разницу
  поглощает подписка; биллинг сессиям НЕ виден, источник — только
  оператор. Вход для R5 и чеков 10/11 калибровки ~07-18.

- Исторические baseline-срезы (all-time $1,177 на 07-07, cache-reads
  97.6%, ретро-G1) — сняты с бут-пути: G1/G2 формально закрыты
  гейт-отчётом 07-13; живой тренд даёт savings_report каждой
  калибровкой (№2: $471/день, экономия 65%, $3.77/единицу — notes
  calibrated 07-18). Архив: calibration2-closures.md.
- SPEND MIX — ARCHITECT CORRECTION (2026-07-07): the baseline is
  CENSORED data (operator rationed frontier usage), so it cannot
  refute "the smartest model burns most". Correct reading — frontier
  burns FASTEST per unit: opus $0.264/turn, fable $0.216 vs sonnet
  $0.063-0.114 (2-4x). Consequences: (a) success metric is cost per
  accepted unit by tier + escalation rate, NOT frontier share;
  (b) the escalation journal measures the true tier boundary; the
  weekly loop watches the recent-window trend, not all-time totals.

## Remaining Lead-tier Queue (live only; закрытые блоки — evening-closures)

- WORKSTREAM 3 — ЗАКРЫТ ЦИКЛ: оценка носителей 07-13, пилот N1–N5
  done 07-18, adoption = D-0080 (правило 4а CLAUDE.md). Дальше по
  D-0059: код/автоматизация — только по evidence ценности артефакта.
  Архив блока: 2026-07-18_calibration2-closures.md.
- Упрочнение tier-гейта (WHEN: evidence первого инцидента):
  find_tier_declaration матчит первую tier:-строку — фикс: любую
  удовлетворяющую (критик t-068, не-блокер).
- ТУЛКИТ: релиз v0.3.0 вышел 07-16 (состав батча — VERBATIM
  evening-closures-port-run11.md; клон —
  D:\Improving_AI\Supervised-Delegation). ОЧЕРЕДЬ СЛЕДУЮЩЕГО БАТЧА
  D-0074 (по слову): 1) п.13 Safe telemetry — решение получено
  07-16 ~23:30 (дефолт GATEWAY_LOG_RAW_TEXT=false; raw только явно
  под Shadow Evaluation, честная строка конфига + предупреждение;
  TTL/purge при raw) — реализация первым пунктом; 2) п.15
  permission-audit (после проживания в корне); 3) хвост п.18
  (порядок boot-diet в свежей сессии — при касании session_context
  кита); 4) hygiene_gate + F-47 (порт-очередь 07-18).
  Мораторий в силе.
- СЕРИЯ №1–№4 ЗАКРЫТА 07-15 (VERBATIM —
  2026-07-15_exam-week-context-closures.md). ЖИВОЕ: window_load
  LIKE-исключение + ассерт «id без дефисов» (t-126, ось 2).
  AO3-порты 07-16 (3f4014b+bc297bc) и 07-18 (bec081f) закрыты;
  живой остаток AO3 их Lead'ом: B-1/B-2 не-блокеры log_append,
  «__file__-якорные скрипты», стейл-самоссылка порта, staging_gates
  не активирован (D-0069, их слово) — плюс новые пункты 07-18 в
  блоке ДЕНЬ выше.
- НАБОР №2 ЗАКРЫТ 07-16 (разбор —
  docs/tasks/2026-07-15_economy-exam-runs5-6.md + Runs log).
  ОСТАТОК: раннер «пустой stdout при rc=0» — фикс в очереди;
  синтетика окон — пометка в Runs log при следующем прогоне.
- ЭКЗАМЕН-СЕРИЯ: №1–№11 закрыты (разборы — evening-closures +
  docs/tasks/*economy-exam*), №12–№14 — 07-18 (evening-run-series).
  Кит = ветка штаба (правило протокола); медиана малых копится
  (№11 0.88, №12 0.95, №13-B 0.95, №14 0.95); большой — по каденции;
  РЕЗЕРВ — генератор сайта.
- A5 witness auto-collection (builder-class; WHEN: first REAL
  builder-Pi work cycle — Rule #1: no wrapper before there are
  sessions to wrap; binding decided at calibration): wrapper runs
  the canonical pytest form after a Pi builder session and attaches
  verbatim output as a witness DRAFT; acceptance stays with Lead.
- ВНЕШНЕЕ РЕВЬЮ 07-13 закрыто (триаж 2026-07-14_external-review-
  triage.md; 7/10 не берём — триггеры там). Остаток: staleness цен —
  мелкой builder-задачей при следующем касании учёта.
- ПОВЕСТКА КАЛИБРОВКИ ~07-18 РАЗОБРАНА ЦЕЛИКОМ — вердикты в notes
  calibrated 07-18; VERBATIM + вердикты:
  2026-07-18_calibration2-closures.md.
- ПИЛОТ OPUS-ДИЗАЙНЕРА ПРОДЛЁН до калибровки №3 (3 точки/0
  реджектов — мало; designer=estimated; DAG-док 2026-07-14).
- РЕТРО-БЭКЛОГ: docs/RETRO_PATTERNS.md (чек 0); UI-witness в AO3 не
  прожит — первый их UI-диспатч = проба.
- Evidence-gated residuals — 9 пунктов, каждый на своём триггере:
  полный список VERBATIM —
  docs/task_reports/2026-07-16_evidence-gated-residuals.md.
- Eval plan stage 2 — цикл №1 07-13 (d90cd03). Остаток:
  minimum-n/pass^k + numeric agreement (пороги с калибровки);
  Batch API — TRIGGER «реплеи регулярны», учёт requests.db тем же
  ходом; NOT taken: per-PR CI, bench-harness.
- NOT adopted (чтобы не пересуживать): GSD-координатор, auto-mode
  SQLite/crash recovery, supply-chain tags, WXP; OpenClaw: channels,
  delegate identity, compaction/memory, utilityModel. Обоснования —
  RELATED_WORK «OpenClaw survey» + evening-closures.
- Habr/LinkedIn (t-036): готово, публикация — слово оператора
  (docs/ARTICLE_BRIEF_2026-07-10.md + draft-{A,B,C}).
- White Paper v0.2.1 — AWAITING Architect review (кандидат v0.2.2:
  экзамены, policy-as-code, D-0076..81, critic-lite — после ревью).

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
