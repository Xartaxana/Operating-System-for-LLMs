# Task 3 — Phase 2 readiness digest in metrics.py (ACCEPTED 2026-07-09)

Journal task_id: t-002 (delegated 2026-07-09T01:22:08, accepted
2026-07-09T01:42:30). Builder: Sonnet subagent (background, D-0040).
Review: critic (Opus) dispatch per rule 3 (>100 lines) — verdict
ПРИНЯТЬ, 0 blockers. Lead witness: own canonical run 108/108 passed,
consistent with builder's and critic's runs.

## Spec (Lead, 2026-07-07; verbatim from CURRENT_CONTEXT.md)

For a CHEAPER model session (builder-tier work, not Lead work).
Phase 2 readiness digest in metrics.py. Spec (Lead, 2026-07-07);
executor does not self-certify — Lead/Architect reviews before the
next task starts.

Add a "Phase 2 readiness" section to the metrics.py text and JSON
digest: one line per ROADMAP gate criterion (G1, G2, R1-R5, C1-C3)
showing current value vs. threshold and met / not met /
"not computable yet (needs <what>)". Rules:

1. Deterministic Python/SQL over requests.db and
   DELEGATION_TABLE.md only — no LLM calls.
2. G1 counts DISTINCT days with traffic_kind='real' rows. R1 parses
   judged evidence lines from the Shadow Evaluation Log. G2, R5 and
   anything not derivable from telemetry print as "manual check"
   with a pointer — never a guessed value.
3. Criteria whose inputs do not exist yet (e.g. C2 sessions before
   session identity lands, R2 spend shares before real traffic)
   MUST print "not computable yet" with the missing prerequisite —
   an honest gap, not a fake 0% (Rule #1 spirit).
4. Tests over a seeded tmp DB; existing tests stay green.

Acceptance: `python metrics.py --days 14` prints the section; JSON
output carries a `phase2_readiness` object with the same content.

Note (post-spec, Task 5 landed): the digest should count G1 days
over BOTH requests (traffic_kind='real') and cc_usage rows; if
reading cc_usage is deferred, the G1 line must say so explicitly.

## Builder execution report (verbatim)

### 1. Изменённые файлы

- **`gateway/metrics.py`** — добавлена секция "Phase 2 readiness":
  - `repetition_totals()` — рефакторинг `repetition_by_model()` для доступа к сырым суммам (нужно для агрегированного C1).
  - `parse_shadow_eval_log(text)` — парсит Shadow Evaluation Log из DELEGATION_TABLE.md: считает `pairs`/`runs` по категориям только для **judged** (`judge=` в строке) и **не-retracted** строк (`[OVERRULED]` считается, `[RETRACTED]` — нет).
  - `_g1_readiness`, `_c1_readiness`, `_c2_readiness`, `_r1_readiness` — вычисления по requests/cc_usage/DELEGATION_TABLE.md.
  - `phase2_readiness(conn, days, delegation_table_path=None)` — собирает все 10 критериев (G1, G2, R1-R5, C1-C3), каждый — `status ∈ {met, not_met, not_computable_yet, manual_check}` + `detail`/`needs`/`pointer`.
  - `format_phase2_line()` — рендер строки по статусу.
  - `daily_digest()` получил параметр `delegation_table_path=None` (сигнатура обратно совместима — существующие вызовы `daily_digest(conn, days=1)` не изменились) и кладёт `phase2_readiness` в возвращаемый dict.
  - `format_digest()` — секция "Phase 2 readiness" в конце текстового дайджеста.
  - `main()` — новый `--delegation-table` CLI-флаг (по умолчанию `<repo_root>/DELEGATION_TABLE.md`, резолвится через `Path(__file__).parent.parent`, не зависит от cwd).

- **`gateway/test_metrics.py`** — 19 новых тестов: парсинг Shadow Eval Log (judged/retracted/overruled), все 4 статуса для каждого вычислимого критерия (G1/C1/C2/R1 — met/not_met/not_computable), manual_check для G2/R5, not_computable+needs для R2/R3/R4/C3, граница sidechain-исключения для C2, форматирование строк, интеграция в `daily_digest`. Локальная копия минимальной cc_usage-схемы (та же, что в `tools/usage_report.py`) — без кросс-пакетного импорта из `tools/`.

### 2. Witness (фактический вывод)

Канонический прогон из корня:

```
$ python -m pytest tools/ gateway/ -q
........................................................................ [ 66%]
....................................                                     [100%]
108 passed in 19.15s
```

Проверочный прогон (из `gateway/`, см. вопрос 1 про cwd):

```
$ python metrics.py --days 14
...
Phase 2 readiness (ROADMAP.md "Phase 2" gate; Delegated Task 3):
  G1: 15 distinct real-traffic day(s) in the last 14 day(s) (requests real=0 + cc_usage real=15, union; day COUNT, not verified for consecutiveness) vs threshold >=14 consecutive days -> met
  G2: manual check (PROCESS/JUDGE_CALIBRATION_PROTOCOL.md -- last recorded result judge-groq 13/13 (see CURRENT_CONTEXT.md))
  R1: best candidate coding: 4 judged pair(s) across 2 run(s); all categories: classification=2/1, coding=4/2, extraction=2/1, formatting=2/1, summarization=2/1 vs threshold >=30 pairs across >=2 independent runs, per category -> not met
  R2: not computable yet (needs categorized real traffic (...))
  R3: not computable yet (needs the same categorized real traffic as R2, split into the two halves of the G1 window)
  R4: not computable yet (needs R1-R3 satisfied first, plus a projected router operating cost (no router built yet, D-0029))
  R5: manual check (ROADMAP.md Router gate R5 / CURRENT_CONTEXT.md Environment Notes -- no ANTHROPIC_API_KEY / paid Lead in production as of this digest)
  C1: not computable yet (needs real multi-turn traffic in requests (0 traffic_kind='real' rows...))
  C2: 32 real session(s) with >=5 top-level turns in the last 14 day(s) (cc_usage session_id, sidechain excluded) vs threshold >=20 -> met
  C3: not computable yet (needs a cache-aware repetition measure combining requests.db prompt content with cc_usage cache_read/cache_creation token accounting (not yet built); also blocked by 0 traffic_kind='real' rows in requests)
```

`python metrics.py --days 14 --json` подтверждён — `phase2_readiness` несёт тот же контент структурированно (10 ключей G1/G2/R1-R5/C1-C3, каждый с `status` + `detail`/`needs`/`pointer`).

### 3. Вопросы / расхождения со спекой

1. **Команда приёмки из корня буквально не работает**: `python metrics.py --days 14` из корня → `FileNotFoundError` (metrics.py лежит в `gateway/`). Это не новое расхождение — тот же паттерн уже задокументирован в `gateway/README.md`, ср. CLAUDE.md гигиена п.2 про прокси. Прогнал фактический эквивалент из `gateway/` — см. witness.
2. **G1 "consecutive" vs "distinct"**: спека прямо говорит "G1 counts DISTINCT days" — реализовано буквально (`COUNT(DISTINCT day)` по объединению requests+cc_usage), но ROADMAP.md формулирует критерий как "≥14 **consecutive** days". Проверка последовательности не достроена (не самовольно); в `detail` явная пометка "day COUNT, not verified for consecutiveness". Нужно подтверждение Lead.
3. **R1 "независимые runs"**: все строки Shadow Evaluation Log датированы одним днём (2026-07-03), поэтому "run" = одна строка-запись в логе (один вызов shadow_eval.py), а не календарная дата. Явное допущение, зафиксировано в докстринге `parse_shadow_eval_log`.
4. **C3 "не вычислимо"**: трактовано как "ещё не построено" — в кодовой базе нет функции, совмещающей character-level repetition (`requests.prompt`) с cache-экономикой (`cc_usage.cache_read_tokens`/`cache_creation_tokens`). `tools/usage_report.py` `cache_accounted_savings_usd` считает другую величину.

### 4. Замеченные sibling-дефекты (scope не расширялся)

- **Дрейф схемы `traffic_kind`**: `gateway/sqlite_logger.py` SCHEMA объявляет `traffic_kind TEXT NOT NULL DEFAULT 'real'`, но живая `gateway/requests.db` (PRAGMA table_info) имеет `dflt_value = "'synthetic'"` — старая база не мигрирована под новый дефолт в коде. Не чинился — вне scope Task 3.
- **`docs/SIBLING_MAP.md`** ось 2 ставит `gateway/metrics.py` в пару с `tools/usage_report.py`. Спека адресовала только metrics.py; зеркальной секции в usage_report.py нет — вне явного scope, доложено Lead.

### 5. Что не сделано и почему

- Реальная проверка "consecutive days" для G1 — не реализована (вопрос 2), по спеке буквально требовался счётчик distinct days.
- R2/R3/R4/C3 остаются `not_computable_yet` — по спеке корректно (входные данные не существуют).
- `tools/usage_report.py` (sibling) не тронут — вне scope написанной спеки.

## Critic review (Opus, verbatim; verdict ПРИНЯТЬ)

Дифф полностью удовлетворяет спеку. Прослежены R1-парсер на реальном `DELEGATION_TABLE.md`, G1/C2 на живой `requests.db`, семантика рефакторинга `repetition_totals`/`repetition_by_model`, честность всех 10 статусов. Тесты зелёные (108 passed весь набор, 24 в `test_metrics.py`).

### Проверка спеки построчно (пороги ROADMAP)

- G1 порог `>=14` ✓; G2 порог/пойнтер 13/13 ✓; R1 `>=30 pairs / >=2 runs per category` ✓; C1 `>=0.40` ✓; C2 `>=5 turns / >=20 sessions` ✓. Все пороги совпадают с ROADMAP.md, ни один не выдуман.
- Правило 1 (детерминизм, без LLM) ✓; правило 2 (G1 union, R1 judged-парсер, G2/R5 manual_check с pointer) ✓; правило 3 (not_computable_yet несёт needs) ✓; правило 4 (seeded tmp DB, существующие зелёные) ✓.
- Acceptance: `python metrics.py --days 14` печатает секцию ✓; JSON несёт `phase2_readiness` ✓ (`test_daily_digest_carries_phase2_readiness`).
- Post-spec note (G1 над requests+cc_usage; при отсутствии cc_usage — говорит явно) ✓ — на живой БД видно `requests real=0 + cc_usage real=15, union`.

### Находки (по убыванию тяжести; все NON-BLOCKING)

1. **G1 может выдать `status="met"` на НЕсмежных днях** (`_g1_readiness`). На живой БД: `15 distinct ... -> met`, при том что гейт ROADMAP G1 требует «≥14 **consecutive** days». `detail` честно оговаривает, но потребитель, читающий `status`, получит ложное «met». Спека явно разрешила счёт distinct-дней — это рассинхрон спека↔ROADMAP, решать Lead'у. Не блокер: транзит фазы подписывает Архитектор, читая detail.
2. **Окно `--days 14` фактически 15 календарных дней** (`since=f"-{days} days"` + `>=` включает оба конца). Косметика формулировки + лёгкий сдвиг границы; общий для оконных критериев (G1/C1/C2).
3. **Мелкая утечка изоляции в существующих тестах**: старые вызовы `daily_digest(conn, days=1)` теперь дёргают `_r1_readiness`, читающий РЕАЛЬНЫЙ DELEGATION_TABLE.md (default-путь). Read-only и безвредно, но тест зависит от файла репо. Новые тесты изолированы правильно. Ось 5 карты соблюдена; `CC_USAGE_SCHEMA` в тесте байт-в-байт совпадает с `usage_report.py:112-129`.

### Ответы на 4 вопроса builder'а (рекомендации)

(а) **Запуск только из gateway/**: принять как задокументированный паттерн (cwd-относительные импорты — действующая конвенция gateway/; строку в README, НЕ переархитектуривать). Каноническая тест-форма из корня работает.
(б) **G1 distinct vs consecutive**: честной оговорки в detail достаточно для ручного sign-off, но остаётся путь ложного `status="met"`. Рекомендация: follow-up — максимальный смежный прогон, `met` только при `>=14`; либо сознательное решение Lead с правкой текста G1 в ROADMAP (владелец гейтов — ROADMAP, ось 4).
(в) **R1 run=строка лога**: приемлемый прокси; сверено на реальных данных — 10 judged-строк, 0 молчаливо отброшенных, [RETRACTED]×4 исключены, [OVERRULED] засчитан. Принять.
(г) **C3 как «not yet built»**: корректно — ровно та честная дыра, которой требует правило 3 спеки. Принять.

### Вердикт по sibling-пунктам

(а) **Дрейф дефолта traffic_kind — ПОДТВЕРЖДЁН независимо**: живая БД `DEFAULT 'synthetic'` (PRAGMA), SCHEMA/CREATE = `DEFAULT 'real'` (sqlite_logger.py:33), миграция ALTER = `DEFAULT 'synthetic'` (строка 58). Предшествует диффу; дифф не вносит и не зависит (везде явные значения/фильтры). Оставить отдельной задачей.
(б) **Ось 2 (metrics.py ↔ usage_report.py) — зеркалирование НЕ нужно**: `phase2_readiness` — единый отчёт, уже читающий оба контура из одного места; экземпляра дефекта в usage_report.py нет. Rule 9 удовлетворён докладом builder'а; условие — пункт реально попадает в очередь (выполнено: CURRENT_CONTEXT).

### След (critic)

- Читал: gateway/metrics.py (весь дифф), gateway/test_metrics.py (весь дифф), gateway/conftest.py, ROADMAP.md Phase 2, DELEGATION_TABLE.md Shadow Evaluation Log, gateway/sqlite_logger.py:33/56/64/94, tools/usage_report.py:112-129, docs/SIBLING_MAP.md оси 2/5.
- Трассировал: `_SHADOW_EVAL_LINE_RE` на всех 10 judged-строках реального лога; рефакторинг `repetition_totals`; ветви `_g1/_c1/_c2` с/без cc_usage.
- Прогнал: `python -m pytest tools/ gateway/ -q` → 108 passed; `python -m pytest test_metrics.py -q` (из gateway/) → 24 passed; `python metrics.py --days 14` → секция печатается; живой `PRAGMA table_info(requests)`.

## Lead acceptance decisions (2026-07-09)

1. Запуск metrics.py из gateway/ принят как задокументированный
   паттерн (README-строка добавлена этим же коммитом); спека будущих
   задач называет команды с фактическим cwd.
2. G1 distinct-семантика оставлена по спеке; follow-up «максимальный
   смежный прогон, met только при >=14» поставлен в очередь
   (builder-tier). Текст гейта G1 в ROADMAP НЕ ослаблен (D-0033:
   ревизия порога/формулировки гейта — только записью в DECISIONS).
3. R1 run=строка лога принят как прокси; уточнение «independent =
   уникальная (дата, judge)» — по данным первой калибровки, если
   понадобится.
4. C3-трактовка принята.
5. traffic_kind default drift: в очередь на проверку намеренности
   (SCHEMA 'real' для новых БД vs миграция 'synthetic' для старых —
   похоже на осознанную семантику Tasks 1-2, но не задокументировано);
   если дефект — оформить defect_found с ref на Tasks 1-2.
