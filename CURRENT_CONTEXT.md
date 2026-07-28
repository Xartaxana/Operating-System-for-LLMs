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
ПОРЯДОК (слово оператора 07-28): релиз минора — ПОСЛЕ калибровки
№5 (~07-30); порт-очередь минора пополнена батчем 07-28
(Guard-твин, гейт-твины, exam-кит, KIT-DRIFT-диспозиция, доки).
ВХОДЯЩЕЕ ОТ AO3 07-24 (дыра членства basis в их log_append) ЗАКРЫТО
ИМИ САМИМИ 07-28: их калибровка №4, коммит 30e79c8 —
_allowed_basis(tier(agent), tier(by)) кодом; фикс полного Lead с
нашей стороны НЕ НУЖЕН. Разбор твин-вопроса — очередь ниже
(разобран 07-28).

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

ДЕНЬ 07-18 и КАЛИБРОВКА №3 07-19 ЗАКРЫТЫ (VERBATIM —
calibration2-closures + evening-run-series; блок и его давно слитая
в очередь №5 стародавняя очередь — evening-closures.md §8).
AO3-ОЧЕРЕДЬ — в ИХ docs/HANDOFF.md (D-0082).

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

- **Кросс-пункт от AO3 07-28 РАЗОБРАН И ИСПОЛНЕН** (полный разбор
  VERBATIM — 2026-07-28_evening-closures.md §1): дыры «членство
  вместо пары» у нас НЕТ (B7 t-322 старше их вопроса); перенятая
  unknown-by дельта исполнена t-323 (996358e). ЖИВОЕ: передача
  твин-ответа AO3 в их HANDOFF.md при безопасном касании — пункт
  очереди №5 ниже.

- **РЕВЬЮ CODEX 07-24 РАЗОБРАНО 07-28, части (а)/(б) ИСПОЛНЕНЫ**
  (триаж — 2026-07-28_codex-review-triage.md; блок «принято в
  работу» VERBATIM — evening-closures.md §2; вход 07-24 был
  незакоммичен — пропуск handoff D-0050, материал чека №5):
  (а) Guard-проекция t-324; (б) scout-сужение t-327/t-329 +
  break-glass t-325; (в) дизайн режимов телеметрии — порт-очередь;
  кандидаты №5 и отклонения — в триаж-доке.
  ПОРТ-ОЧЕРЕДЬ КИТ-МИНОРА (пополнена вердиктом t-328, классовая
  полнота): (1) toolkit/gateway/guard.py + budgets-шаблон — порт
  t-324 (в кит-копии тот же P0; парити-пары guard.py/test_guard.py
  в tools/parity_manifest.json НЕТ — добавить при релизном --sync);
  (2) кит-твины main_gate/dod_gate/session_context — порт t-325
  после фиксов (уже в HQ-DRIFT парити-чека, легально по D-0074);
  (3) exam_fullgates_kit-сторона гейтов (ось 4) — unsafe_completion
  синком подготовки следующего прогона (прецедент tier_echo);
  (4) KIT-DRIFT пары CLAUDE.md↔toolkit/CLAUDE.md — ДИСПОЗИЦИЯ:
  легальный батч 07-28 по слову оператора (unknown-by формулировка
  + owns-на-пишущих-узлах R4 от 07-28), синк базлайна — релизным
  батчем минора; (4а) кандидаты порта слоя 1: owns_gate/owns_verify
  — по итогам штабной обкатки (warn-first), решение при релизном
  батче — при порте owns_gate word-boundary-класс обязан уехать и в
  кит-dispatch_gate ЦЕЛИКОМ: owns-регекс (доклад t-332 att.3) +
  given-регекс (ложный маркер «продано», t-335) + DoD-регекс
  (ложный маркер dod_gate.py в корзине, находка F1 критика t-336) —
  копия toolkit/tools/dispatch_gate.py несёт все три подстрочные
  слабости;
  (5) кит-твин toolkit/PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md —
  расширение чека 23 от 07-28 (обязательная атрибуция вердиктов,
  посадка в чеклист D-0096).

- ГЭП-БАТЧ ВАЛИДАЦИИ 07-23 и КАЛИБРОВКА №4 с очередью находок —
  ЗАКРЫТЫ ЦЕЛИКОМ (порт-очереди исполнены t-310/t-316 07-24) —
  VERBATIM: docs/task_reports/2026-07-24_phase4-hardening-closures.md
  §2–§3. ЖИВОЕ из них: adversarial-экзамен КООРДИНАТОРА (верхняя
  граница F-28; класс pi_run_guard — соблазн/фабрикация для
  Lead-поведений; дорого, по слову). NEGATIVE_LINT АКТИВЕН с 07-24
  (обкатка кандидата в кит идёт); находка №1 (async-FP, рецидив
  07-28) ЗАКРЫТА тюнингом t-331 — VERBATIM evening-closures.md §3.

- БАТЧ МЕЛОЧЕЙ 07-28 ИСПОЛНЕН ЦЕЛИКОМ (VERBATIM — evening-closures
  §4): (а) negative_lint async-skip t-331 (e98f56b); (б)
  word-boundary маркеры dispatch_gate t-335 (a8058d6, критик t-336
  fit_with_fixes — класс подстрочных ложных маркеров закрыт:
  owns/given/DoD/witness).

- OWNS_GATE АКТИВЕН с 07-28 (t-332 att.3 принят, хук в
  settings.json, warn-first обкатка как negative_lint): WARN-
  статистика и находки нумеруются здесь; промоция в блок — по ликам
  (D-0063), материал чека 25/23 №5. Sidecar logs/owns_registry.jsonl
  (gitignored, компакция >500). owns_verify — детерминированный шаг
  приёмки (D-0095).

- ВОТЧДОГ зависших/пустых воркеров (инсайт-разбор 07-28) — кандидат
  механизма, НЕ строится до evidence (Rule #1): триггер — статистика
  rejected/failure_class=tooling за окно калибровки №5 (зависания/
  пустые отчёты сейчас держит R6-зеркало + F-49-правила ролей).

- ОЧЕРЕДЬ КАЛИБРОВКИ №5 (~07-30, консолидирована диетой 07-24):
  НОВОЕ 07-28 (2): чек 23 с 07-28 ОБЯЗАТЕЛЕН и атрибутивен (правка
  протокола по слову оператора) — первый атрибутивный прогон на
  окне №5; окно несёт ЧЕТЫРЕ чек-23 кейса (t-324/t-325/t-332×2 —
  два reject t-332 по чистым spec-дефектам диспетчера дали R6-
  эскалацию на opus; развёрнуто — evening-closures.md §6) + инцидент
  D-0060 govard (протухание проверки чистоты за минуты) +
  гигиена-промахи Lead (2>&1, cd, кит-wiring вызов) + СМЕНА РЕЖИМА:
  /doctor 07-28 включил defaultMode=auto user-scope — permission-
  сигнал чека 25 станет тише, учесть при чтении окна. Golden set
  подтверждён штатно t-329 (6/7 PASS, девиация t-327 снята — §5).
  Триаж governance-промпта инсайтов 07-28 —
  2026-07-28_governance-guards-triage.md (4/6 стоит, 1 записанное
  решение, 1 дельта=слой 1; свита по HEAD чиста: 1625 passed,
  parity 40/7/0/3 все записанные). ЖИВАЯ КАРТА ПОКРЫТИЯ
  docs/RULE_COVERAGE.md заведена вечером 07-28 словом оператора
  (правило→сторож→режим; поддержание — пара оси 4 + чек 24; первый
  свежесть-проход — №5).
  НОВОЕ 07-28: чек кэш-экономики (слово оператора «поставь в очередь
  чек для кеша») — доля cache_creation_input_tokens в окне по обоим
  учётам (requests.db + cc_usage) и корреляция write-всплесков с
  паузами >TTL главного цикла; вопрос-источник: «не платим ли
  контекст заново после каждой задачи»; гипотеза от эмпирики
  95.9% cache-read — нет: платим на стартах сессий и паузах >TTL,
  не на длительности задач. Чек-23 кейс 07-28: spec-дефект
  диспетчера в t-324 — DoD (з) «тесты зелёные без правок»
  противоречил безусловной проекции с дефолтом 2048; вскрыт
  возвратом билдера (штатная аварийная сетка R11), решён вариантом
  C (data=None → легаси-путь). Второй чек-23 кейс 07-28: спека
  t-325 фиксировала ack-после-печати, не оговорив усечение
  MAX_LINES — билдер находку всплыл, координатор не отреагировал до
  критика (блокер t-328). Кандидат из t-328: форм-валидация by на
  соседях энум-гейта — rejected (сейчас by без матрицы, записанное
  решение), agent=lead (легальный by=operator, R11a), agent вне
  AGENT_TIER; сужение задокументировано в докстринге правила 11
  обоих валидаторов.
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
  python -c чтения, два F-29 Lead'а; пропуск handoff 07-24 —
  codex-файл незакоммичен, D-0050); кандидаты из триажа Codex 07-28
  (route-intent слой против самоисполнения Lead; привязка
  basis=judge к leaf-артефакту; liveness-пробы хуков в цикле
  калибровки — триаж-док §6–8); AO3-входящие: их кейс
  queued-to-lead×4 (материал чека 6/30; их log_append закрыт ими
  самими 30e79c8, разбор твин-вопроса 07-28 — выше) + передача
  твин-ответа AO3 при безопасном касании их HANDOFF.md (в тот же
  пункт: рекомендация E4-класса — сузить tools их scout-роли, Bash
  изъят у нас 07-28 по P0 внешнего ревью; + env-строка Windows их
  builder-роли — класс осей 1/3, наш builder.md п.9 от 07-28; +
  R4-твин owns-на-пишущих-узлах DAG от 07-28 — их CLAUDE.md, ось 1).

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
