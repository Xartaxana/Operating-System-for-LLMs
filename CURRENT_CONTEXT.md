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
e0754a6. Phases 1/1.5 закрыты 2026-07-11. Phase 2: workstream 3
(task pipeline, D-0059) открыт 07-13; ROUTER WORKSTREAM ОТКРЫТ
2026-07-21 подписью Архитектора (все критерии D-0086-ревизии
зелёные, серии D№1–№6; блок — ROADMAP «Gate decision 2026-07-21»;
принятые следствия — D-0087 leaf routing + D-0088 однопутная
архитектура); Context закрыт прямым измерением (ROADMAP «Gate
decision 2026-07-13»). Телеметрические
циклы (еженедельная калибровка; №2 07-18, №3 07-19, №4 досрочно
07-23 по слову «запускай» — событие calibrated 07-23T14:44, чек 30
чист, экономия 65% стабильна; следующая штатная ~07-30) — штатные
операции. Plan of record: docs/UNIFIED_PLAN_2026-07-07.md; гейты
Phase 2 — ROADMAP.md.

## Current Task (Authoritative, D-0025)

СЕССИЯ 07-16 ВЕЧЕР ЗАКРЫТА ЦЕЛИКОМ (t-159..t-172; гейты активны
19b4c91, тулкит v0.3.0, порт-батчи AO3) — VERBATIM:
docs/task_reports/2026-07-16_evening-closures-port-run11.md.
ОЧЕРЕДЬ ГЕЙТ-КАСАНИЯ (механизменно, с тестами; калибровка №2
подтвердила — ложных блоков сверх этих находок нет): (1) dotfiles
fail-closed (Rule #1 может сказать «не чинить»); (2) doc-only
«целиком-или-никак»; (3) gate_log без ts/agent_id — форензик-ограничение ПОДТВЕРЖДЕНО
t-265 (поштучная привязка 8/10 блоков 07-21 недоказуема из
носителя); (4) предохранитель
consecutive_blocks session-global при per-agent решении + kit-сиблинг
dod_gate; на kit-касание также staging_hq/ не в песочницы + red-run
t2 флаг; (5) main_gate doc-only-баг РАЗОБРАН t-265: код-путь
205–216 (_all_edits_doc_only по ВСЕЙ истории сессии — ранний
code-edit гасит исключение навсегда), факт 10 блоков 07-21 + 5 за
07-22 (запись «3 блока» занижала 3+ раза), класс фикса
edits_after_green; смежный класс: dod_track не исключает
scratchpad-пути из main-скоупа; (6) journal_echo ts-drift замер
завышен на ~+31 мин константы (defect_found t-263 07-22, измерено:
оболочки+mtime согласны, выпадает хук; критик по R3 до фикса,
warn-only). Парсер OPEN DISPATCH починен 07-19 (closes:-токен, t-197).
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

- КАЛИБРОВКА №4 ИСПОЛНЕНА 07-23 (досрочно, слово «запускай»; полный
  разбор — notes calibrated 07-23T14:44): чек 30 — первое боевое
  judge-окно ПОДТВЕРЖДЕНО (8/8 лист-класс, галлюцинаций нет,
  экономика в плюс; MAY→дефолт — решение оператора); движений
  таблицы 0; срез карты осей AO3 догнан (+ось 10, их 2a2e671) и
  детектор среза зарегистрирован в чеке 12; Dog: ревизия леджера
  отсутствует — кросс-пункт (их f71685e). РЕЛИЗНЫЙ ГЕЙТ КИТА по
  чекам 30/31/экономике ПРОЙДЕН — релиз v0.5.0 ВЫШЕЛ 07-23
  (d0cfedc, блок релиза ниже). ОЧЕРЕДЬ ИЗ НАХОДОК №4 (статус 07-23 вечер, слово
  «доделываем весь хвост»): (1) ИСПОЛНЕН — прогон SCOUT_GOLDEN_SET
  PASS 7/7 (t-292, Runs log; вывод: рост recon-реджектов — свойство
  трудных лист-задач зеркала, не деградация яруса); (2) СНЯТ —
  ретро-closes не нужен: верификация t-293 (ПЕРВАЯ judge-приёмка
  дефолта D-0094) показала 17/18 давно закрытыми
  (токены t-197/t-200/t-203/t-207, t-029 accepted), t-184 закрыта
  decomposable; взамен находка: calibration_counts.py не читает
  closes:-токены/decomposable в блоке «незакрытые» (артефактный
  список) — фикс в следующий батч мелочей; (3) кандидаты
  решений — статус 07-23: git -C allowlist ИСПОЛНЕНО (вариант 1
  словом оператора: 20 узких read-only правил AO3/Dog в
  settings.local.json; пишущие формы остаются за запросом);
  форм-контроль негатива ЗАКРЫТ D-0094 (интент-ключи листа);
  оба оставшихся кандидата ОТЧЕКАНЕНЫ 07-23: D-0095 (скрипт-запуски
  — операции среды, вне skip-класса; детектор — чек 22) и D-0096
  (пятипунктовый чек-лист диспетчера в R11; детекторы — чеки
  13(г)/23); кит-строки rules 8/11/13 ИСПОЛНЕНЫ пре-релизным батчем
  07-23 (ниже); (4) ЗАКРЫТ 07-23 как superseded (проверка Lead по коду):
  редизайн канала эха после t-203 фактически исполнен слоями
  journal_echo (TIER/WITNESS на записи строки с worker_ref,
  доставка в PostToolUse координатора — t-258/t-277/t-279, ось 10);
  тайминг-зазор «результат использован до записи строки» держат
  названные детекторы D-0076/D-0079 + чеки 4/5/7; Stop-хук-кандидат
  воспроизвёл бы дефект-класс t-203 (SubagentStop доставляет не той
  стороне — свойство харнесса) — не строим; (5) ИСПОЛНЕН 07-23 —
  ПРЕ-РЕЛИЗНЫЙ БАТЧ МЕЛОЧЕЙ (слово «доделай все мелочи перед
  релизом»; t-294 инвентаризация 11 пунктов + t-295 builder, критик
  fit/0 блокеров, контрольный перегон Lead 1298+950 passed):
  кит-политика rules 8/11/13 = D-0094/95/96 (без штабных якорей —
  сверено критиком), hygiene_gate v2 в ките (166→264, FP-класс «>»
  в сообщениях закрыт), calibration_counts ×2 читает closes:-токены
  формой сканера + decomposable (недо-репорт reopen — признанное
  отличие: счётчик даёт кандидатов, приговор у session_context).
  ОСТАЮЩИЕСЯ УЗЛЫ РЕЛИЗНОГО БАТЧА (по релизному слову, НЕ мелочи):
  обобщённый tools/wiring_check.py в кит (D-0092/D-0093);
  exam_fullgates_kit полный гейт-набор t-278; D-0085 дефолт-привязки
  + judge-sonnet алиас + API-строка моста в кит-онбординг;
  судья-онбординг пользователя (сет 13 пар + подписочная процедура
  t-254); journal_echo witness/ts-drift слои в кит (дельта t-272
  пп.3-13).

- ОНБОРДИНГ D-0090 ОТЧЕКАНЕН И ВАЛИДИРОВАН ЦЕЛИКОМ 07-22 (оба
  полигона G/B зелёные; DAG docs/tasks/2026-07-22_onboarding-
  validation.md; блок VERBATIM — task_reports/2026-07-23_boot-diet-
  relocations.md §1). ЖИВОЕ: остатки у Dog — в ИХ носителе (D-0082);
  КИТ-БАТЧ (порт-очередь, по слову): онбординг-протокол + шаблон
  ledger + манифесты предпосылок + входы валидации (5 шагов
  INSTALL.md, headless-ветка, «хост применяет hook-конфиг сам»,
  экзамены отдельными диспатчами, Finding B/C); кейсы №4: два
  spec-дефекта DoD (t-269, t-271) + первый failed-back D-пути.

- WORKSTREAM 3 закрыт (adoption D-0080; дальше по evidence, D-0059;
  архив: 2026-07-18_calibration2-closures.md).
- ВАЛИДАЦИОННЫЙ СЛОЙ N1..N4 + ЧЕКАНКИ D-0091/D-0092 + АУДИТ
  ПОСТАВКИ (F-52) ЗАКРЫТЫ 07-22 — VERBATIM: docs/task_reports/
  2026-07-22_night-validation-closures.md + relocations-файл 07-23
  §2. ЖИВОЕ, очередь №4: аудит решения экзаменатора T-K3 (чек 14;
  генератор critic-exam-gen несёт несущую T-K3, след t-280) +
  первый прогон чека 32; релиз кита v0.5.0 ВЫШЕЛ 07-23 (d0cfedc);
  порт-очередь следующего минора: обобщённый
  tools/wiring_check.py в кит (D-0092); WP v0.2.2 ждёт читки
  Архитектора; батч мелочей hygiene-WARN закрыт t-289 (FP не
  воспроизвёлся — v2 t-255 уже покрывал).
- БАТЧ НАХОДОК DOG ЗАКРЫТ 07-23 (слово «делай все три пункта»; DAG
  docs/tasks/2026-07-23_dog-findings-batch.md; t-286..t-288, критик
  fit_with_fixes / 0 блокеров): D-0093 отчеканено (запечатанная
  поставка цепочки контроля — полный носитель исполняемого файла,
  проба живости, exec-биты как wiring), SKIP_RE заякорен на обоих
  носителях (сиблинг F-A, кросс-пункт Dog), 4 хука штаб+кит
  переведены в 100755 в индексе, детектор индексных мод/untracked в
  wiring-чеке, чек 32(г), INSTALL-раздел исполняемости,
  скилл-апгрейд п.5; кросс-пункты D-0082: Dog (якорь) и AO3 (якорь +
  их 100644) — в их носителях тем же ходом. Протухшая строка
  «Упрочнение tier-гейта (WHEN: первый инцидент)» снята — закрыта
  фиксом t-278 (find_tier_declarations, findall/fail-closed).
- ТУЛКИТ: релизы v0.4.0–v0.4.2 вышли 07-20, батчи 1–3 исполнены,
  кит в паритете со штабом, вопрос AO3-сканера отвечен (их
  closes-phantom-форма — признанное отличие) — VERBATIM:
  docs/task_reports/2026-07-20_router-day.md. Штабной логгер
  вступит при следующем старте прокси. Порт-очередь: пункты D-0085
  (блок «ПРИВЯЗКИ» ниже) + session_context wiring (t-257) +
  journal_echo witness (t-258) + critic-verdict (t-259) + F-50
  деливерабл-дрейф (шаг 2а handoff + чек 31 в кит-копиях
  session-handoff/калибровочного протокола) + t-261 близнецы
  toolkit/gateway/{shadow_eval,regression_runner}.py (judge_cost в
  calibrate + правило нарезки корпуса; фикс критика F2) + t-262
  escape-allowlist (escape_check.py + allowlist-шаблон + строка
  pre-commit в кит; норма D-0089 в кит-политику); мораторий
  до слова.
- РУТИНГ-ДЕНЬ 07-21 ЗАКРЫТ ЦЕЛИКОМ (гейт-отчёт → серии D№1–№6 →
  ROUTER-ГЕЙТ ОТКРЫТ подписью → гибрид H+C → D-0087 leaf routing
  (+вторая форма судьи 13/13 t-254) → D-0088 однопутная архитектура
  → hygiene_gate v2; 6/6 роутер-кандидатов отклонены, триггер
  переоткрытия labeled>=100) — VERBATIM:
  docs/task_reports/2026-07-21_leaf-routing-day.md; решение гейта —
  ROADMAP «Gate decision 2026-07-21»; журнал t-236..t-255. ЖИВОЕ:
  эксплуатация D-0087 — калибровка №4 (чек 30, первое окно
  judge-basis); дозаписи очереди №4: галлюцинация судьи (кандидат
  judge-детектора); синтетика окон серий D/H (D-0075) —
  инвентаризация ГОТОВА t-266 07-22: requests.db чист (0% untagged
  07-20/21), cc_usage не различает синтетику by design (real=3855
  за 07-19 / 590 в H-окне), H-прогон t-250 — единственное окно БЕЗ
  D-0075-пометки в журнале (ретро-пометка решением Lead на №4);
  main_gate ложные doc-only блоки (кандидат чека 26) — разбор
  ГОТОВ t-265 (пункт 5 очереди гейт-касаний выше); открытые слова
  дня закрыты (дубль как заграйжено, переигровка C-tb снята).
- ВХОДЯЩЕЕ ОТ AO3 «деливерабл-дрейф» ЗАКРЫТО 07-22 (F-50 + чек 31 +
  handoff 2а + ось 9; первый прогон чека 31 — №4) — VERBATIM:
  docs/task_reports/2026-07-22_night-validation-closures.md.
- СЕРИЯ №1–№4 ЗАКРЫТА 07-15 (VERBATIM —
  2026-07-15_exam-week-context-closures.md). ЖИВОЕ: window_load
  LIKE-исключение + ассерт «id без дефисов» (t-126, ось 2).
  AO3-порты 07-16 (3f4014b+bc297bc) и 07-18 (bec081f) закрыты;
  живой остаток AO3 — в их носителе docs/HANDOFF.md (D-0082).
- CLAUDE.md DEEP DIET ЗАВЕРШЁН 07-19 (D-0084, ядро EN; закрытый
  нарратив VERBATIM: docs/task_reports/2026-07-20_router-day.md).
  ЖИВОЕ — очередь калибровке №4: rejected-на-критик-отказ (кандидат
  чека); синтетика окон №15–№17 (D-0075); не-блокеры критика t-208
  (глоб → слаг репо; multi-tier model); main_gate ложно блокирует
  doc-only main-правки (3 блока сессии 07-21 на .md/.jsonl —
  doc-only-исключение не срабатывает для main-записей; кандидат
  чека 26, разбор до фикса). Пункт «пустые финал-сообщения воркеров»
  закрыт 07-21 механизмом F-49 (чек 29).
- НАБОР №2 закрыт 07-16 (economy-exam-runs5-6 + Runs log); остаток:
  раннер «пустой stdout при rc=0»; синтетика окон — пометка при
  прогоне.
- ЭКЗАМЕН-СЕРИЯ: №1–№14 закрыты (разборы — evening-closures +
  docs/tasks/*economy-exam* + evening-run-series); медиана малых
  0.88–0.95 копится; большой — по каденции; РЕЗЕРВ — генератор
  сайта.
- A5 witness auto-collection (WHEN: первый реальный builder-Pi
  цикл; Rule #1): обёртка гоняет канонический pytest после
  Pi-сессии, вывод = witness DRAFT; приёмка у Lead.
- ВНЕШНЕЕ РЕВЬЮ 07-13 закрыто (триаж 2026-07-14_external-review-
  triage.md); остаток: staleness цен — при касании учёта.
- ПИЛОТ OPUS-ДИЗАЙНЕРА: вердикт при №4 (designer=estimated;
  DAG-док 2026-07-14). ТОЧКА №3 получена 07-20 (t-223, эскалационный
  корпус): дизайнер поймал 3/5 рассогласованных пар task-коммит в
  брифе Lead ДО прогонов, развилки вернул — сильный кейс.
- ПРИВЯЗКИ API-КОНТУРА: D-0085 УТВЕРЖДЕНО 07-20 (вариант A — зеркало
  подписки; закрытый нарратив ночи и хвостов — VERBATIM:
  docs/task_reports/2026-07-20_router-day.md); статусные движения —
  калибровке №4. ЖИВОЕ: ПОРТ-ОЧЕРЕДЬ ТУЛКИТА (мораторий до слова):
  дефолт-привязки A + judge-sonnet алиас (drop_params) в
  кит-онбординг + строка API-дефолта в мост «Two Vocabularies»
  (ось 4/7 D-0085); + F-49-класс 07-21: правило финал-сообщений в
  кит-роли + подсказка пересдачи в BLOCK_MESSAGE kit
  toolkit/tools/dod_gate.py (ось 7); + D-0087 07-21: R13 (обе
  формы судьи вкл. подписочную) в кит-политику + basis judge в
  кит-валидатор + judge_accept в кит-tools (снимком из
  exam_hybrid_kit) (ось 7); + judge-онбординг пользователя (пробел
  вскрыт вопросом оператора 07-21): калибровочный сет 13 пар с
  ключом (generic, поставляем как есть) + подписочная процедура
  t-254 (сет через судью-субагента, сверка с ключом, планка 13/13)
  в кит-онбординг рядом с scout/critic-экзаменами — API пользователю
  НЕ нужен (лаборатория replay — наша, не продукта); ОНБОРДИНГ-ЭКЗАМЕН API-КОНТУРА ОСТАЁТСЯ (слово
  07-20): модели пользователя экзаменуются против референс-планок
  D-0085 «не хуже зеркала», кит-батч несёт планки ЧИСЛОМ; хвост №4:
  кросс-аудит gemini worse-вердиктов judge-sonnet по opus-целям
  (self-judging риск).
- БАТЧ МЕЛОЧЕЙ 07-20 ИСПОЛНЕН ЦЕЛИКОМ 07-22 (t-261, все 7 пунктов;
  находка (ж): +2ч разрыв ts-клоков — подкласс оси 2) — VERBATIM:
  docs/task_reports/2026-07-22_night-validation-closures.md.
- РЕЛИЗ КИТА v0.5.0 ВЫШЕЛ 07-23 (слово «делай релиз» после чистого
  гейта калибровки №4): публичный Supervised-Delegation d0cfedc +
  тег v0.5.0, снимок staging 11149b2, 42 файла +6883/−154, хуки в
  публичном индексе 100755 (D-0093). Снимок-ревизия кита для
  D-0091-леджеров хостов = v0.5.0/d0cfedc. Мораторий D-0074 на
  toolkit/ продолжает действовать (батчи по слову); следующий минор
  понесёт named-узлы из блока пре-релизного батча ниже. Процедура
  релиза отчеканена скиллом kit-release (D-0097, слово оператора
  07-23) — следующий релиз идёт им.
- ПОРТ-ОЧЕРЕДЬ exam_fullgates_kit (ось 4, условие приёмки t-278 —
  критик F2): перенести в кит-экзаменатор ПОЛНЫЙ гейт-набор t-278
  (main_gate/dod_gate edits_after_green + dotfiles, dod_track
  scratchpad-исключение + gate_log ts/agent_id, mechanism_gate
  find_tier_declarations, xfailed-фикс t-275) — при следующем
  касании exam_fullgates_kit.
- БАТЧ МЕЛОЧЕЙ ИСПОЛНЕН 07-23 (t-289, все 5 пунктов: returncode
  ls-files в wiring-чеке; тесты skip-первой-строки ×2; докстринги
  find_tier_declarations ×2; сужение _is_scratchpad_path до вне-cwd
  ×2 по решению t-278(б); hygiene-FP НЕ воспроизвёлся против v2
  t-255 — закрыт тест-гэп grep/rg, исходная заметка 07-22 была
  протухшей). Находка R9 в порт-очередь за релизным гейтом:
  toolkit/tools/hygiene_gate.py — версия БЕЗ v2/t-255 (латентный
  FP-класс на «>» внутри сообщений коммитов).
- БАТЧ МЕЛОЧЕЙ 07-22 ИСПОЛНЕН 14:41 (t-275; 978→992 passed;
  кит-сиблинги t-274; текст — relocations-файл 07-23 §3). ОСТАТОК в
  очередь гейт-касаний: битый (не отсутствующий) config.yaml глушит
  весь вывод session_context-хука через catch-all main() — к
  разбору вместе с п.(6) t-263.
- РЕТРО-БЭКЛОГ: docs/RETRO_PATTERNS.md (чек 0); UI-witness AO3 —
  их первый UI-диспатч.
- Evidence-gated residuals — 9 пунктов, каждый на своём триггере:
  полный список VERBATIM —
  docs/task_reports/2026-07-16_evidence-gated-residuals.md.
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
