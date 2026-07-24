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
e0754a6. Phases 1/1.5 закрыты 2026-07-11. PHASE 2 ЗАКРЫТА 2026-07-23
подписью Архитектора в сессии («закрытие фазы 2 подтверждаю») после
чистого чека 30 калибровки №4: Router закрыт, лист-роутинг — дефолт
ядра (D-0094); блок — ROADMAP «Phase 2 — CLOSED», нарратив и
гейт-решения — в архиве D-0078; reopen-триггеры перенесены в
evidence-gated очередь ниже тем же коммитом. Телеметрические
циклы (еженедельная калибровка; №2 07-18, №3 07-19, №4 досрочно
07-23 по слову «запускай» — событие calibrated 07-23T14:44, чек 30
чист, экономия 65% стабильна; следующая штатная ~07-30) — штатные
операции. Plan of record: docs/UNIFIED_PLAN_2026-07-07.md; гейты
Phase 2 — ROADMAP.md.

PHASE 4 — HARDENING FOR DELIVERY (D-0098) ОТКРЫТА 2026-07-24 словом
оператора: дыры поставки закрываются ПРОАКТИВНО, до первого
пользователя (переворот дефолта D-0063 для продукта; для штабных
механизмов D-0063 в силе). Входная оценка исполнена — enforcement-gap
аудит 07-24 (t-312..t-315, отчёт
docs/task_reports/2026-07-24_enforcement-gap-audit.md). Workstreams и
гейт — ROADMAP «Phase 4». СТАТУС 07-24: WORKSTREAMS 1–3 ИСПОЛНЕНЫ
ЦЕЛИКОМ, критик-гейт t-318 fit/0 блокеров (перегоны: штаб 1538,
кит 1352, exam-kit 270 passed): ws1 — протухшие строки переписаны
(a9310db); ws2 — кит-полнота уложена (c0d25e2: wiring_check.py
закрыл D-0092 кодом, hygiene v3, 4 слоя journal_echo, judge_prompt_
pin, D-0085-доки, INSTALL escape-шаг; exam-кит 7b6b2fa); ws3 — E4
(2105d4f, вкл. внеплановую дыру кит-critic) + E1 страж R6-зеркала
(edfd134, обе стороны). Базлайн parity пере-снят 09:08 (50 пар
CLEAN). ЗАПЕЧЁННЫЙ ПОРТ-ДОЛГ (базлайн его не видит — явные строки):
кит-calibration_counts без accepted_tids-фикса t-309;
кит-usage_report без комментария-сверки. ХВОСТЫ Phase 4 (не гейт):
F2 критика — неэкранированный SQL LIKE (метасимвол _ в слагах,
класс t-126); F3 — кодировка piped-CLI соседей (точечный scout);
DOC_ONLY_EXTENSIONS без .yaml/.yml (решение Lead); строка-класс
справочных docs/*.md в номенклатуре леджера; exam-кит
mechanism_gate без тест-файла. ГЕЙТ: (а)+(б)+(г) ПРОЙДЕНЫ 07-24
(ре-аудит t-319..t-321: свип леджера 19/19 с файлами, 157 ссылок
резолвятся, слой E весь с named-детекторами, E1/E4 живы кодом,
метод протуханий доказан чувствительным на 2 исторических кейсах и
чист на HEAD; строка Gate status в ROADMAP); ОСТАЛОСЬ: (в) кит-минор
по релизному слову (kit-release, D-0097) + подпись Архитектора.
ВХОДЯЩЕЕ ОТ AO3 (их шапка (9), 07-24, очередь полного Lead их
носителем): их scripts/log_append.py валидирует basis только
членством множества, НЕ матрицей пар (by-ярус, agent-ярус) —
queued-to-lead-ошибка прошла их гейт дважды; наш валидатор матрицу
несёт (journal_validator 285-326) — сиблинг-пробел оси 1; фикс их
кода — при следующем AO3-касании полного Lead (их сессия 07-24 жива,
D-0060 — не трогать сейчас).

## Current Task (Authoritative, D-0025)

СЕССИЯ 07-16 ВЕЧЕР ЗАКРЫТА ЦЕЛИКОМ (t-159..t-172; гейты активны
19b4c91, тулкит v0.3.0, порт-батчи AO3) — VERBATIM:
docs/task_reports/2026-07-16_evening-closures-port-run11.md.
ОЧЕРЕДЬ ГЕЙТ-КАСАНИЙ ЗАКРЫТА ЦЕЛИКОМ (t-278 фиксы, t-308 батарея,
t-313 аудит) — VERBATIM: docs/task_reports/
2026-07-24_phase4-hardening-closures.md §1. Парсер OPEN DISPATCH
починен 07-19 (closes:-токен, t-197).
HYGIENE_GATE активен с 07-18 (t-177, warn; v2 07-21 убил
git-FP-класс, t-255): не-блокеры — python3 -c, doc-note;
toolkit-сиблинг v1 — порт-очередь.

ДЕНЬ 07-18 ЗАКРЫТ ЦЕЛИКОМ (калибровка №2 + D-0080/D-0081 + экзамены
№12–№14 + порты; VERBATIM — 2026-07-18_calibration2-closures.md +
2026-07-18_evening-run-series.md; t-173..t-193; нарративы там,
статусные факты живут своими носителями: таблица/DECISIONS/реестр).
КАЛИБРОВКА №3 ЗАКРЫТА 07-19 (внеплановая; полный разбор — notes
calibrated 07-19T14:11): находка F-48 → D-0082; рецидив F-47
ремедиирован (d951844); движений таблицы нет; чек 22: батчинг
подтверждён (1 skip vs 16).
ОЧЕРЕДЬ: вторая точка critic-lite — при №4 ~07-25 (номер «№15»
занят kernel-прогоном 07-19); экзамен Sonnet-координатора ждёт
естественного батча (D-0080 п.4); Get-Date/date-формы В ALLOWLIST
07-22 словом оператора (закрыт); опус-дизайнер: вердикт №4 (3
точки/0 реджектов);
чек-25-хвосты 07-18: decomposable-граница — кандидат builder.md
«возврат после пробы»; owns-пути АБСОЛЮТНЫМИ. AO3-ОЧЕРЕДЬ — в ИХ
docs/HANDOFF.md (D-0082).

API-ОКНО ЗАКРЫТО 2026-07-13 ($170.44, прокси опущен, сессии на
подписке) — дословно: docs/task_reports/2026-07-13_api-window-night.md
(+prep 07-12).

BOOT-БЮДЖЕТ: история — коммиты диет; мелкие развёртки — на handoff.

Рамки: ТУЛКИТ-МОРАТОРИЙ D-0074 (toolkit/ — батчем по слову;
порт-очередь ниже).

Закрытое 07-11/12 — индекс docs/task_reports/README.md; «haiku
сохраняем» в силе; старая очередь on-touch/evidence-gated.

## ЛИСТ-РОУТИНГ — ДЕФОЛТ ЯДРА (D-0094, 2026-07-23)

Промоция MAY→дефолт исполнена по чистому аудиту чека 30 калибровки
№4 (слово «делай дефолт»; окно и вердикты — notes calibrated
07-23T14:44). Лист-класс (разведка / реализация по спеке; БЕЗ
механизмов/политики/интеграции — R13, и БЕЗ денег/схемы/>100-строк
— там критик по R3) идёт D-путём по умолчанию: allocate-лестница →
воркер → судья-приёмка (`basis: "judge"`; подписочная форма —
судья-субагент с pinned JUDGE_SYSTEM_PROMPT ДОСЛОВНО, планка t-254;
шлюзовая — tools/judge_accept.py при живом прокси) → R6-зеркало.
Отклонение — только с записанной причиной (форма t-286, детектор
чек 30); интент-ключи разведки несут форм-контроль негативов
(D-0094). Трактовка R3-порога по несущей поверхности (t-264)
аудитом принята — прецедент стоит.

## Routing MVP — LIVE on both deployments

- Pilot: D:\AO3_tests (2026-07-07, commit b8125a0). Reference/
  dogfooding: THIS repo (2026-07-08). Each = auto-loaded CLAUDE.md
  policy + agents scout/builder/critic + logs/routing-log.jsonl
  (D-0041: always the three together).
- Policy text ARCHITECT-ACCEPTED 2026-07-09 (171078c); later policy
  changes follow the mechanism discipline.
- Evidence: logs/routing-log.jsonl; Claude-строки таблицы
  provisionally_validated с 07-11 (Update Rule 1, D-0047).
- Retro baseline AO3: $276.70 + $57.82 sidechain (Task 6); цикл
  меряет $/принятую + эскалации, не frontier share (baseline ниже).
- Калибровки: №1 07-11, №2 07-18, №3 07-19, №4 07-23 (досрочная);
  следующая ~07-30 (staleness — Boot Report, D-0047).

## System State (condensed, 2026-07-08; updates dated)

- Фазы/гейты — владелец ROADMAP.md (Phase 0/1/1.5/3 закрыты там).
  Компоненты API-контура (Gateway/Guard/Ledger/Analyst/Shadow
  Evaluation) построены и живы; лог прогонов —
  docs/SHADOW_EVALUATION_LOG.md (t-054/t-056, пара оси 4).
- Judge: judge-groq (gpt-oss-120b, free) 13/13 x2; протокол
  JUDGE_CALIBRATION_PROTOCOL.md (D-0031), chief-judge + 1-2
  аудита/прогон; fallback groq > paid > local (Qwen3-4B ниже бара);
  второй судья judge-gemini 13/13 (t-023) — точечная кросс-семейная
  (20 req/day).
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

- ГЭП-БАТЧ ВАЛИДАЦИИ 07-23 и КАЛИБРОВКА №4 с очередью находок —
  ЗАКРЫТЫ ЦЕЛИКОМ (порт-очереди исполнены t-310/t-316 07-24) —
  VERBATIM: docs/task_reports/2026-07-24_phase4-hardening-closures.md
  §2–§3. ЖИВОЕ из них: adversarial-экзамен КООРДИНАТОРА (верхняя
  граница F-28; класс pi_run_guard — соблазн/фабрикация для
  Lead-поведений; дорого, по слову). NEGATIVE_LINT АКТИВЕН с 07-24
  (регистрация словом оператора, пробы D-0093 живьём; полевая
  обкатка кандидата в кит идёт). Обкатка, находка №1 (07-24): FP на
  async_launched-метаданных Agent-вызова — линт сканирует эхо
  ПРОМПТА координатора в ответе тула; кандидат тюнинга: пропускать
  isAsync/status=async_launched payload'ы — при следующем касании
  линта.

- ОЧЕРЕДЬ КАЛИБРОВКИ №5 (~07-30, консолидирована диетой 07-24):
  вторая точка critic-lite; экзамен Sonnet-координатора (естественный
  батч, D-0080 п.4); вердикт опус-дизайнера (3 точки / 0 реджектов,
  DAG 2026-07-14); аудит решения экзаменатора T-K3 (чек 14, след
  t-280) + первый прогон чека 32; кросс-аудит gemini worse-вердиктов
  judge-sonnet по opus-целям (self-judging риск); rejected-на-критик-
  отказ (кандидат чека); галлюцинация судьи (кандидат
  judge-детектора); синтетика окон №15–№17 + ретро-пометка H-прогона
  t-250 (D-0075, решением Lead); кейсы онбординга — два spec-дефекта
  DoD (t-269/t-271) + первый failed-back D-пути; чек-25-хвосты
  (decomposable-граница builder.md; owns-пути АБСОЛЮТНЫМИ;
  гигиена-промахи сессий 07-23/07-24 — shell-правки мимо Edit,
  python -c чтения, два F-29 Lead'а); AO3-входящие: basis-матрица их
  log_append (фикс полного Lead при касании) + их кейс
  queued-to-lead×4 (материал чека 6/30).

- ОНБОРДИНГ D-0090 ОТЧЕКАНЕН И ВАЛИДИРОВАН ЦЕЛИКОМ 07-22 (оба
  полигона G/B зелёные; DAG docs/tasks/2026-07-22_onboarding-
  validation.md; блок VERBATIM — task_reports/2026-07-23_boot-diet-
  relocations.md §1). Кит-батч онбординга В STAGING (подтверждено
  аудитом t-307: скилл полный — ветки G/B, манифесты, экзамены
  отдельными диспатчами, headless, судья-онбординг). ЖИВОЕ: остатки
  у Dog — в ИХ носителе (D-0082); кейсы t-269/t-271 — очередь №5.

- WORKSTREAM 3 закрыт (adoption D-0080; дальше по evidence, D-0059;
  архив: 2026-07-18_calibration2-closures.md).
- ВАЛИДАЦИОННЫЙ СЛОЙ N1..N4 + ЧЕКАНКИ D-0091/D-0092 + АУДИТ
  ПОСТАВКИ (F-52) ЗАКРЫТЫ 07-22 — VERBATIM: docs/task_reports/
  2026-07-22_night-validation-closures.md + relocations-файл 07-23
  §2. ЖИВОЕ: WP v0.2.2 ждёт читки Архитектора; T-K3/чек-32 — в
  очереди №5 выше.
- БАТЧ НАХОДОК DOG ЗАКРЫТ 07-23 (t-286..t-288, критик
  fit_with_fixes/0; D-0093 отчеканено, SKIP_RE, хуки 100755,
  кросс-пункты Dog/AO3) — VERBATIM: 2026-07-24_phase4-hardening-
  closures.md §6 (последний пункт) + DAG
  docs/tasks/2026-07-23_dog-findings-batch.md.
- ТУЛКИТ: релизы v0.4.0–v0.4.2 (07-20), порт-очередь РАЗОБРАНА и
  ИСПОЛНЕНА 07-24 — VERBATIM: 2026-07-24_phase4-hardening-closures.md
  §4–§5. Штабной логгер вступит при следующем старте прокси;
  мораторий D-0074 в силе.
- РУТИНГ-ДЕНЬ 07-21 ЗАКРЫТ ЦЕЛИКОМ — VERBATIM:
  docs/task_reports/2026-07-21_leaf-routing-day.md; решение гейта —
  ROADMAP «Gate decision 2026-07-21»; журнал t-236..t-255.
  Синтетика D/H: инвентаризация готова t-266 (requests.db чист,
  cc_usage не различает by design); ретро-пометка t-250 — очередь №5.
- ВХОДЯЩЕЕ ОТ AO3 «деливерабл-дрейф» ЗАКРЫТО 07-22 (F-50 + чек 31 +
  handoff 2а + ось 9; первый прогон чека 31 — №4) — VERBATIM:
  docs/task_reports/2026-07-22_night-validation-closures.md.
- СЕРИЯ №1–№4 ЗАКРЫТА 07-15 (VERBATIM —
  2026-07-15_exam-week-context-closures.md); остаток t-126 ИСПОЛНЕН
  t-311 07-24 (архив §6). AO3-порты 07-16/07-18 закрыты; живой
  остаток AO3 — в их носителе docs/HANDOFF.md (D-0082).
- CLAUDE.md DEEP DIET ЗАВЕРШЁН 07-19 (D-0084, ядро EN; нарратив
  VERBATIM: docs/task_reports/2026-07-20_router-day.md). Остаток:
  не-блокеры критика t-208 (глоб → слаг репо; multi-tier model);
  прочее — очередь №5 / архив §6.
- НАБОР №2 закрыт 07-16; остаток «пустой stdout при rc=0» ИСПОЛНЕН
  t-311 07-24 (архив §6); синтетика окон — пометка при прогоне.
- ЭКЗАМЕН-СЕРИЯ: №1–№14 закрыты (разборы — evening-closures +
  docs/tasks/*economy-exam* + evening-run-series); медиана малых
  0.88–0.95 копится; большой — по каденции; РЕЗЕРВ — генератор
  сайта.
- A5 witness auto-collection (WHEN: первый реальный builder-Pi
  цикл; Rule #1): обёртка гоняет канонический pytest после
  Pi-сессии, вывод = witness DRAFT; приёмка у Lead.
- ВНЕШНЕЕ РЕВЬЮ 07-13 закрыто (триаж 2026-07-14_external-review-
  triage.md); остаток staleness цен ИСПОЛНЕН t-311 07-24 (архив §6).
- ПИЛОТ OPUS-ДИЗАЙНЕРА: вердикт — очередь №5 (designer=estimated;
  DAG-док 2026-07-14). ТОЧКА №3 получена 07-20 (t-223, эскалационный
  корпус): дизайнер поймал 3/5 рассогласованных пар task-коммит в
  брифе Lead ДО прогонов, развилки вернул — сильный кейс.
- ПРИВЯЗКИ API-КОНТУРА D-0085: порт-очередь тулкита ИСПОЛНЕНА
  (staging t-274/t-307 + дельты t-310 07-24) — VERBATIM: 2026-07-24_
  phase4-hardening-closures.md §5; нарратив ночи — router-day.md.
- БАТЧ МЕЛОЧЕЙ 07-20 ИСПОЛНЕН ЦЕЛИКОМ 07-22 (t-261, все 7 пунктов;
  находка (ж): +2ч разрыв ts-клоков — подкласс оси 2) — VERBATIM:
  docs/task_reports/2026-07-22_night-validation-closures.md.
- РЕЛИЗ КИТА v0.5.0 ВЫШЕЛ 07-23 (слово «делай релиз» после чистого
  гейта калибровки №4): публичный Supervised-Delegation d0cfedc +
  тег v0.5.0, снимок staging 11149b2, 42 файла +6883/−154, хуки в
  публичном индексе 100755 (D-0093). Снимок-ревизия кита для
  D-0091-леджеров хостов = v0.5.0/d0cfedc. Мораторий D-0074 в силе;
  СЛЕДУЮЩИЙ МИНОР ГОТОВ содержательно (порт-набор Phase 4 уложен,
  гейт (в) ждёт релизного слова) — идёт скиллом kit-release (D-0097).
- Батчи мелочей 07-22/07-23 (t-275/t-289) и порт exam_fullgates_kit
  — исполнены, остатки закрыты 07-24 — VERBATIM: 2026-07-24_phase4-
  hardening-closures.md §6.
- РЕТРО-БЭКЛОГ: docs/RETRO_PATTERNS.md (чек 0); UI-witness AO3 —
  их первый UI-диспатч.
- Evidence-gated residuals — 9 пунктов, каждый на своём триггере:
  полный список VERBATIM —
  docs/task_reports/2026-07-16_evidence-gated-residuals.md.
- STANDING-ТРИГГЕРЫ ИЗ ЗАКРЫВАЮЩЕГО КОММИТА PHASE 2 (07-23,
  обязанность F-48/D-0082 — триггер в архиве не передан):
  (а) per-unit worktree-изоляция (GSD, отвергнута Rule #1) — reopen:
  реальный параллельный объём диспатчей + инцидент коллизии путей
  (класс D-0060); (б) LLM-роутер-кандидаты (6 отвергнуты двумя
  волнами обзоров) — reopen: ≥100 размеченных примеров;
  (в) большая параллельность как workstream — reopen: числа
  P1-класса (задачи ≥5 событий / ≥2 сессий) показывают переполнение
  координационных артефактов.
- Eval plan stage 2 — цикл №1 07-13 (d90cd03); остаток:
  minimum-n/pass^k + numeric agreement; Batch API по триггеру
  «реплеи регулярны»; NOT taken: per-PR CI, bench-harness.
- NOT adopted (чтобы не пересуживать): GSD-координатор, auto-mode
  SQLite/crash recovery, supply-chain tags, WXP; OpenClaw: channels,
  delegate identity, compaction/memory, utilityModel. Обоснования —
  RELATED_WORK «OpenClaw survey» + evening-closures.
- White Paper v0.2.2 ГОТОВ К РЕВЬЮ АРХИТЕКТОРА (очередь пополнений
  исчерпана 07-22; §11 Limitations освежить по итогам №4 при ревью;
  нарратив пополнений — relocations-файл 07-23 §4).

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
- LITELLM-ПИН НА WINDOWS (находка t-242, 07-21): litellm >=1.92.0
  без универсального wheel — pip тянет sdist со сборкой Rust/Cargo
  и падает; рабочий пин litellm==1.91.0. КАСАЕТСЯ gateway при любой
  переустановке venv. Смежное: pip тоже бьётся о MAX_PATH (класс
  известен) — junction'ы C:\rlsp_a, C:\rlsp_b остались от t-242
  (безвредные ссылки в песочницу; удаление корневых путей защищено
  харнессом — убрать оператору: rmdir C:\rlsp_a C:\rlsp_b).
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
