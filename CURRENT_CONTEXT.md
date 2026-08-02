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

PHASE 4 — HARDENING FOR DELIVERY (D-0098) ЗАКРЫТА 2026-07-30
ПОДПИСЬЮ АРХИТЕКТОРА в сессии («подтверждаю закрытие фазы 4»):
все 4 критерия гейта пройдены — (а)+(б)+(г) ре-аудитом 07-24,
(в) релизом кит-минора v0.6.0 07-30 (публичный 02bac45 + тег,
снимок штаба aa725e6, цикл kit-release t-344..t-346). Блок —
ROADMAP «Phase 4 — CLOSED»; нарратив открытия/workstreams/гейта —
архив D-0078 + boot-diet-relocations 07-30 §1. Пост-релизная
очередь 07-30 (слово оператора) исполнена: T-K3-аудит ✓ (Runs log
CRITIC_EXAM.md), малый экзамен ✓ (№19, Runs log
DEPLOYMENT_ECONOMY_EXAM.md), boot-diet ✓ (этим коммитом).
ХВОСТЫ Phase 4 (не гейт, живые): F2 критика — неэкранированный SQL
LIKE (метасимвол _ в слагах, класс t-126); F3 — кодировка piped-CLI
соседей (точечный scout); DOC_ONLY_EXTENSIONS без .yaml/.yml
(решение Lead); строка-класс справочных docs/*.md в номенклатуре
леджера; exam-кит mechanism_gate без тест-файла.
Входящее от AO3 07-24 (membership basis) закрыто ими самими 07-28
— архив-переносы 07-30 §2.

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
- Калибровки: №1 07-11, №2 07-18, №3 07-19, №4 07-23 (досрочная),
  №5 07-29 (по слову); следующая ~08-05 (staleness — Boot Report,
  D-0047).

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

- **F-54 (2026-07-30, кросс-пункт AO3 по D-0082): открытый вопрос к
  DELEGATION_TABLE/туровому словарю** — оракулы корректности слепы к
  дефектам агрегированного ОПЫТА (полный текст — docs/FINDINGS.md
  F-54; прецедент BUG-017 AO3, ремедиация у них внедрена тем же днём:
  амплификация-тур + визуальный-свип-тур в шаблоне чартера). Решить:
  нужна ли та же ось эвристик другим деплоям (Dog) и штабному
  словарю; решения нет.

- **F-55 (2026-07-31, кросс-пункт AO3 по D-0082): кандидат-подкласс в
  чек F-30 WEEKLY_CALIBRATION_PROTOCOL** — «статус записи реестра из
  частичного чтения»: несущее утверждение о статусе записи
  append-only реестра валидно только чтением до статусной строки /
  grep'ом статусного поля, не присутствием шапки записи в окне чтения
  (полный текст — docs/FINDINGS.md F-55; прецедент: Lead-сводка AO3
  назвала resolved-эскалацию ESC-001 открытой — resolved-строка жила
  ниже окна limit=30; вскрыто вопросом оператора; ремедиация AO3 —
  grep-пары `^## ESC-|^- Статус:`). Решить при следующей калибровке:
  включать ли подкласс в чек F-30; решения нет.

- **КРОСС-ПУНКТ AO3 2026-07-31 (D-0082): порт ветки (д) в
  tools/journal_validator.py правило 9** — AO3 `scripts/log_append.py`
  получил третье легальное основание повторного `delegated` тем же
  агентом на открытый task_id: новая итерация жизненного цикла после
  настоящего `--reopen-task` (маркер `reopen: <причина>` в notes
  delegated-события ПОСЛЕ последнего delegated этого агента; применяется
  ТОЛЬКО когда ни `--attempt`, ни `--replaces-worker` не заданы). Мотив —
  их AT-BUG-033 (critic-вход другой природы на переоткрытой задаче);
  реализация прошла 2 rejected + эскалацию (регрессия B6: сужение
  rejected до per-agent ломало штатный критик-раунд — реплей их журнала,
  12 переворотов; откачено до task-level = паритет с нашим правилом 9).
  БЕЗ порта наше правило 9г («всё остальное — FAIL») отвергнет их
  легальные (д)-строки при кросс-чтении журнала калибровкой. Их коммиты:
  441d322 (код+тесты), 6f97508 (их CLAUDE.md). Смежный класс —
  их bugs/AT-BUG-034.md — **ЗАКРЫТ их стороной тем же днём («Добавление
  8» log_append.py, их коммит b37c3d8, критик-вход + реплей 516
  delegated 0 переворотов):** чужой task-level rejected легализует
  повторный вход агента ТОЛЬКО при сигнале новой версии объекта ревью
  строго ПОСЛЕ его последнего delegated — три сигнала: (1) delegated
  ДРУГОГО агента; (2) rejected(agent='lead') — Lead-rework не несёт
  своего delegated; (3) escalated(model='fable'); один сигнал = один
  вход (повторное потребление отклонено). Следствие для нас: паритет
  правила 9 с их гейтом нарушен ВТОРОЙ раз, теперь в строгую сторону
  с их стороны — наш `retry_ok = valid_attempt and task_id in
  rejected_tasks` (без анкера и сигналов) уязвим к классу B3 («ревьюер
  занимает чужой rejected без нового объекта ревью»); форма признака
  для порта готова у них (хелперы `_agent_has_own_rejected` /
  `_new_version_signal_since_agent_last_delegated` + 8 тестов).
  Известные остатки их признака (R-1..R-3: сигнал (1) не сужен до роли
  исполнителя; own-rejected не анкерован; escalated не ограничен
  агентом-автором) — явные строки их bugs/AT-BUG-034.md, двигаются по
  evidence рецидива. Решения нет (порт обеих веток — (д) и Добавление
  8 — одним касанием journal_validator).
  **Под-вопрос той же оси:** ловит ли НАШ mechanism-невод (D-0055,
  tools/mechanism_gate.py) правки tools/journal_validator.py — у AO3
  их log_append.py в неводе не был (три коммита без осевого блока,
  закрыто их 9dd5274); проверить нашу сторону на тот же класс.
  **Обновление 2026-08-02 (AO3 Lead, свежий evidence):** их критик при
  D1-верификации AT-BUG-034 точечно сверил НАШ
  tools/journal_validator.py:614 — строка `retry_ok = valid_attempt and
  task_id in rejected_tasks` (без анкера и сигналов) ЖИВА, дыра B3
  открыта у нас по-прежнему; их остатки R-1..R-3 эту нашу ось не
  называют (она наша, не их). Пункт не нов, но теперь подтверждён
  вторичной независимой сверкой; приоритет порта — наше решение.

- **ОТВЕТ AO3 (2026-08-02) на наш вопрос про basis=judge (кит v0.6.0,
  передан 2026-07-30):** класс **н-п** у AO3 — их
  `scripts/log_append.py` BASIS_VALUES = {critic, queued-to-lead},
  значения judge не существует вовсе (решение их Lead 2026-07-22 при
  разборе D-0087: «признанное отличие, BASIS_VALUES НЕ расширять» —
  их HANDOFF/09-history «Решения Lead по входящим OS 2026-07-22»).
  Твин нашего category/agent-гейта judge-ветки им не нужен, пока judge
  не заведён; если когда-нибудь заведут — форма фикса у нас готова
  (aa725e6, 7 judge-scope тестов). Вопрос закрыт их стороной.

- **ОТ AO3 2026-08-02 (разбор Lead-очереди, 2 класса-кандидата нашей
  сверки; их коммиты a731a7f, e356aea):**
  (1) **Небезопасный откат временной порчи файла:** идиома «порти +
  `git checkout -- <файл>`» в промпте/протоколе красной (мутационной)
  пробы сносит ЧУЖИЕ незакоммиченные изменения файла вместе с порчей —
  у AO3 живой инцидент 2026-08-02 (снесена незакоммиченная фикстура
  параллельного воркера в conftest.py; восстановлено по blob-хэшу).
  Их фикс: CLAUDE.md-правило «откат — только по байтовой копии;
  checkout легален лишь при пустом `git status --porcelain -- <файл>`
  до порчи; witness отката = дословный вывод сверки» + твин в промпте
  test-reviewer. НАМ: сверить свои промпты/протоколы проб (мутационные
  прогоны, red-probe, откаты) на ту же идиому — наш разбор, наше
  решение.
  (2) **Граница невода mechanism_gate для скриптовой обвязки:** AO3
  расширили MECHANISM_PREFIXES на все гейты/валидаторы пути исполнения
  (preflight, машина статусов, схемы выходов, хуки — 10 файлов), явно
  задекларировав границу «гейты — в неводе, генераторы/свиперы/локи —
  вне» комментарием в самом неводе. НАМ: кандидат сверки нашего
  tools/-невода тем же критерием (наш чек 8 — аудит распознавания —
  этот класс уже ловит; вопрос лишь полноты списка).

- **ВХОДЯЩЕЕ ОТ DOG 07-29 РАЗОБРАНО И ИСПОЛНЕНО** (t-337..t-340;
  корреляционная пара + probe + casing + heredoc активны warn-first;
  итог VERBATIM — dog-incoming-closure.md + boot-diet-relocations
  07-30 §3; пункт передачи AO3 исполнен d4ff7d4). ЖИВОЕ из разбора:
  - **ОБКАТКА пары корреляции** (warn-first; находки нумеруются
    здесь): №1 — FP «empty» на непустых dict-ответах Grep
    (content/count-режимы; вскрыт живой обкаткой 07-29, ЗАКРЫТ t-340
    тем же днём); №2 — D4b-резидуал: ретро-описание чужого ложного
    негатива триггерит собственную прозу (архив Dog-закрытия, 07-29)
    — задокументированное ограничение обеих копий, НЕ дефект; фикса
    не планируем без рецидива на живой политике.
  - **ОЧЕРЕДЬ ПЕРЕДАЧИ DOG (D-0082, при безопасном касании их
    носителя — в их дерево без протокола не пишем)**: (а) ответ
    синка: механизм принят и активен, предложения 1–4 исполнены, 6-е
    в кит-очереди, снятие 5/7 подтверждено; negative_lint им отдаём
    (их запись на синк 2 стоит); (б) находки t-339/t-340 по ИХ
    первоисточнику — их копия несёт классы: подстрочные маркеры без
    границ слова (наш закрытый t-332/t-335), таблицы markdown не
    границы предложения, квадратичность _sentence_window, unknown.jsonl
    без компакции (вырождение в молчаливый ложный ПРОПУСК),
    _looks_like_search по JSON всего input (ловит description),
    классификация dict-ответов Grep (filenames[] в content-режиме).
- Кросс-пункт от AO3 07-28 РАЗОБРАН И ИСПОЛНЕН целиком (твин-ответ
  передан d4ff7d4) — архив-переносы 07-30 §4.

- РЕВЬЮ CODEX 07-24: части (а)/(б) исполнены, порт-очередь
  кит-минора ИСПОЛНЕНА ЦЕЛИКОМ релизом v0.6.0 07-30 (сводка —
  архив-переносы 07-30 §5; триаж — codex-review-triage.md). ЖИВОЕ:
  (в) дизайн режимов телеметрии — порт-очередь.
  NAMED-УЗЛЫ СЛЕДУЮЩЕГО МИНОРА (явная очередь, мораторий D-0074
  снова в силе): (а) owns_gate/owns_verify — по итогам штабной
  обкатки (находки №1/№2 стоят, парсер-канон не устоялся);
  (б) correlation-пара search/claim_control_gate + negative_lint —
  обкатка продолжается; (в) exam_fullgates_kit-сторона гейтов —
  unsafe_completion синком подготовки следующего прогона (там же
  designer в AGENT_TIER замороженного корпуса — вердикт критика
  t-346); (г) designer-exam-gen — только по слову оператора
  (записанное решение: набора нет по построению).

- ГЭП-БАТЧ ВАЛИДАЦИИ 07-23 и КАЛИБРОВКА №4 с очередью находок —
  ЗАКРЫТЫ ЦЕЛИКОМ (порт-очереди исполнены t-310/t-316 07-24) —
  VERBATIM: docs/task_reports/2026-07-24_phase4-hardening-closures.md
  §2–§3. ЖИВОЕ из них: adversarial-экзамен КООРДИНАТОРА (верхняя
  граница F-28; класс pi_run_guard — соблазн/фабрикация для
  Lead-поведений; дорого, по слову). NEGATIVE_LINT АКТИВЕН с 07-24
  (обкатка кандидата в кит идёт); находка №1 (async-FP, рецидив
  07-28) ЗАКРЫТА тюнингом t-331 — VERBATIM evening-closures.md §3.

- БАТЧ МЕЛОЧЕЙ 07-28 ИСПОЛНЕН ЦЕЛИКОМ — архив-переносы 07-30 §6.

- OWNS_GATE АКТИВЕН с 07-28 (t-332 att.3 принят, хук в
  settings.json, warn-first обкатка как negative_lint): WARN-
  статистика и находки нумеруются здесь; промоция в блок — по ликам
  (D-0063), материал чека 25/23 №5. Sidecar logs/owns_registry.jsonl
  (gitignored, компакция >500). owns_verify — детерминированный шаг
  приёмки (D-0095). Находки обкатки 07-29: №1 (t-338/t-342) — пути,
  размещённые НИЖЕ строки маркера owns, парсером не разбираются НИ
  голым перечнем, НИ списком «- путь» (канон экстрактора: пути в
  СТРОКЕ маркера; три честных WARN-о-слепоте за день) — кандидат
  тюнинга: многострочный owns-блок; решение по рецидиву после смены
  формы диспатчей Lead. №2 (t-341) — read-only скаут-диспатч, где
  owns был ПРЕДМЕТОМ ВОПРОСА разведки, принят за пишущий манифест
  (родня «дано»-в-корзине t-332 att.3) — кандидат: не считать
  манифестом owns без пути в строке; РЕЦИДИВ №2 07-30 (критик-вход
  t-346: owns — предмет ревью, warn на read-only диспатче) — второй
  кейс класса, кандидат тюнинга стоит, промоция решением при ≥3.
  РЕЦИДИВ №1-класса 07-30 (t-347: owns прозой «всё под корень кроме
  logs» — путей в строке маркера нет, warn слепоты честный) — счёт
  класса 2. GIVEN-PATH-слой (t-343), обкатка тем же списком: №1 —
  ожидаемые WARN на файлах, СОЗДАВАЕМЫХ батчем (предсказан спекой
  t-346, не дефект); №2 — FP на repo-относительном пути ЧУЖОГО
  корня (t-347: tools/kit_diff_check.py экзамен-кита резолвится
  против штабного cwd) — кандидат: чужекорневой контекст;
  №3 (из №19) — область слоя: пути вне корня вне области по
  построению (1/19 диспатчей клеток в области) — кандидат
  расширения по рецидиву.

- ВОТЧДОГ зависших/пустых воркеров (инсайт-разбор 07-28) — кандидат
  механизма, НЕ строится (Rule #1): триггер №5 НЕ выстрелил
  (rejected/tooling окна: OS 0, AO3 1 — замер калибровки 07-29);
  стоит дальше на том же триггере к окну №6.

- КАЛИБРОВКА №5 ИСПОЛНЕНА 07-29 (calibrated 18:42, полный разбор в
  notes; итог-абзац — архив-переносы 07-30 §7; следующая штатная
  ~08-05). Статусы переносов на 07-30: T-K3-аудит ✓, малый экзамен ✓
  (№19); стоят: большой экзамен + critic-lite точка 2 (по слову),
  gemini-кросс-аудит (подъём прокси).
  ЖИВЫЕ кандидаты вне переносов (стоят по своим триггерам):
  rejected-на-критик-отказ, галлюцинация судьи, route-intent слой,
  привязка basis=judge к leaf-артефакту, liveness-пробы хуков в
  цикле калибровки (частично исполнено пробами D-0093 07-29),
  decomposable-граница builder.md, многострочный owns-парсер
  owns_gate (по рецидиву).

- ОНБОРДИНГ D-0090 ВАЛИДИРОВАН ЦЕЛИКОМ 07-22, кит-батч в staging
  (архив-переносы 07-30 §8). ЖИВОЕ: остатки у Dog — в ИХ носителе
  (D-0082); кейсы t-269/t-271 — очередь №5.

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
- ПИЛОТ OPUS-ДИЗАЙНЕРА ЗАКРЫТ калибровкой №5: designer — стоячая
  функция, provisionally_validated (2fa220d); в ките с v0.6.0
  (архив-переносы 07-30 §9; DAG-док 2026-07-14).
- ПРИВЯЗКИ API-КОНТУРА D-0085: порт-очередь тулкита ИСПОЛНЕНА
  (staging t-274/t-307 + дельты t-310 07-24) — VERBATIM: 2026-07-24_
  phase4-hardening-closures.md §5; нарратив ночи — router-day.md.
- БАТЧ МЕЛОЧЕЙ 07-20 ИСПОЛНЕН ЦЕЛИКОМ 07-22 (t-261, все 7 пунктов;
  находка (ж): +2ч разрыв ts-клоков — подкласс оси 2) — VERBATIM:
  docs/task_reports/2026-07-22_night-validation-closures.md.
- РЕЛИЗЫ КИТА: v0.5.0 07-23 (d0cfedc, снимок 11149b2); v0.6.0
  ВЫШЕЛ 07-30 (слово «делай релиз» 07-29 после калибровки №5,
  скилл kit-release): публичный 02bac45 + тег v0.6.0, снимок штаба
  aa725e6, 42 файла +10116/−280, хуки 100755, удалений 0.
  Снимок-ревизия для D-0091-леджеров = v0.6.0/02bac45. Мораторий
  D-0074 в силе (снятие действовало только на релизный батч).
  ТРИГГЕР «релизный снимок кита» ВЫСТРЕЛИЛ 07-30; малый экзамен
  ИСПОЛНЕН тем же днём (№19, Sonnet-координатор, кит 613fd06 эпохи
  v0.6.0 — синк t-347 с 8 записанными адаптациями; вердикт — строка
  Runs log). ОСТАЮТСЯ по слову: большой экзамен, critic-lite точка
  2. ОЧЕРЕДЬ ИЗ НАХОДОК №19: (а) упрочнение headless-протеза —
  прокси-вердикт обязан ограничивать деливерабл клеткой (t1 сдан
  Artifact+scratchpad вне клетки, ось D 0.20); (б) M2-регресс t3
  (граница класса пропущена спекой-перечнем И критиком — чек-23
  материал №6); (в) область given-path слоя: в клетках видел 1/19
  диспатчей (пути вне корня — вне области по построению) — кандидат
  расширения при рецидиве; (г) порт эпох hygiene_gate/journal_echo
  в exam-кит — отдельная оценённая задача (adapted-строки
  kit_sources.json).
  ПРОПУСК ОКНА ТРИГГЕРА (честная запись): T-K3-аудит стоял «до
  релизного слова кита» — слово пришло 07-29 21:26 до исполнения
  аудита; аудит НЕ гонялся — встаёт первым пунктом пост-релизной
  очереди, окно пропуска на счету следующей калибровки.
  КРОСС-ПУНКТ AO3 ПЕРЕДАН 07-30 (слово «передавай, их лид
  установит»): класс «basis=judge шире лист-класса» вписан в их
  docs/HANDOFF.md «Открытые хвосты», их коммит bc36279 (их ветку не
  пушили — там их незапушенная работа); установка за Lead AO3.
  ОТВЕТ LEAD AO3 (2026-07-30, кросс-коммит их Fable-сессии): класс
  установлен как Н-П для AO3 — их BASIS_VALUES={critic,queued-to-lead}
  (scripts/log_append.py:167), «judge» в словаре отсутствует,
  легализация ТОЛЬКО через allowlist-матрицу пар _allowed_basis
  (их калибровка №4); эмпирическая проба (не только чтение):
  builder+judge REJECTED, test-reviewer+judge REJECTED, контроль
  builder+critic ACCEPTED — неизвестный basis отвергается fail-closed
  на обоих классах. Твин фикса не требуется; полная запись — их
  журнал routing-log.jsonl, событие lead_restored 2026-07-30T08:28.
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
