# t-027 — постройка защиты F-30, слои 1–2 (2026-07-10)

Приказ оператора «делай эту защиту» (дизайн: F-30, «Дизайн защиты»
и «Карта покрытия слоёв»). Построены слой 1 («реальность фоном» —
SessionStart-хук) и слой 2 («код на необратимых путях» — preflight
квотного запуска). Конвейер: спека Lead (полный текст — журнал,
delegated t-027 08:35:12) → builder (Sonnet-субагент) → critic
(Opus-субагент, правило 3: дифф >100 строк) → приёмка Lead (Fable).

Слои 4а/4б/5 сознательно НЕ строились (data-gated, F-30); слой 6
лёг правилом 7 в PROCESS/JUDGE_CALIBRATION_PROTOCOL.md этим же
коммитом.

## Отчёт builder (verbatim)

### Сделано

Построены оба инструмента по спеке:

1. **`tools/preflight_quota.py`** — измеренный GO/NO-GO для квотного окна: маппинг alias→provider_model из config.yaml, лимиты из budgets.yaml/`--limit-tokens`, суммирование по ВСЕМ `gateway/*.db` с таблицей `requests` (F-27), расписание освобождения по часовым корзинам, `--probe` через прокси с парсом провайдерского 429, exit 0/1/2, `--json`.
2. **`tools/session_context.py`** — SessionStart-хук: NOW (системные часы, anti-F-29), хвост журнала, скан открытого/закрытого окна деградации по всему журналу, возраст последней калибровки, квотные окна (86400s) + счётчик запросов для gemini-алиасов. Fail-open единой try/except-границей, ASCII-safe, ≤25 строк.
3. **`.claude/settings.json`** — регистрация SessionStart-хука (файла не было, создан с нуля).
4. Тесты: `tools/test_preflight_quota.py` (28 тестов), `tools/test_session_context.py` (18 тестов).

### Witness — канонический прогон (DoD п.1), verbatim

```
$ python -m pytest tools/ gateway/ -q
........................................................................ [ 35%]
........................................................................ [ 70%]
.............................................................            [100%]
205 passed in 8.17s
```
(159 старых + 46 новых = 205, сходится.)

### Witness — демо на живом репо (DoD п.2), verbatim

```
$ python tools/preflight_quota.py --alias middle-groq --need 70000
PREFLIGHT QUOTA CHECK -- alias=middle-groq provider_model=llama-3.3-70b-versatile
  window: 86400s, now=2026-07-10T08:46:45.954703, since=2026-07-09T08:46:45.954703
  limit: 100000 tokens (measured source: budgets.yaml)
  used (measured, status=success, summed over 2 db(s) with a requests table):
    requests.db: 14175 tok
    t013.db: 68054 tok
  used total: 82229 tokens
  headroom: 17771 tokens (limit - used)
  need: 70000 tokens
VERDICT: NO-GO (exit 1)
  next possible GO (measured release schedule): ~2026-07-10T18:46:45.954703 (first hour headroom >= need)
  release schedule (hours where tokens fall out of the window, next 24h):
    +6h (2026-07-10T14:46:45.954703): -5166 tok released, headroom=22937
    +8h (2026-07-10T16:46:45.954703): -2541 tok released, headroom=25478
    +10h (2026-07-10T18:46:45.954703): -67772 tok released, headroom=93250
    +11h (2026-07-10T19:46:45.954703): -282 tok released, headroom=93532
    +14h (2026-07-10T22:46:45.954703): -4186 tok released, headroom=97718
    +18h (2026-07-11T02:46:45.954703): -2282 tok released, headroom=100000
EXIT=1
```

```
$ python tools/session_context.py
NOW: 2026-07-10 08:46:46 Friday (local system clock)
LAST EVENT: ts=2026-07-10T08:41:58 event=delegated agent=lead task_id=t-028
Last calibration: NONE
QUOTA middle-groq: 82229/100000 tok (24h); next release(s): 14:04, 14:06, 15:56
REQUESTS lead-gemini: 15 last 24h
REQUESTS judge-gemini: 22 last 24h
EXIT=0
```

The NO-GO number (82229 tokens used = 14175 requests.db + 68054 t013.db) exactly reproduces the F-27 finding numbers logged in the journal (t-015 attempt-3 rejection) — an independent confirmation the multi-db summation and provider-model grouping are correct on real data.

### Расхождение спеки с реальностью (значимая находка)

Спека предполагала, что колонка `provider_model` в `requests.db` равна значению `litellm_params.model` из config.yaml дословно. Эмпирически (сверено по живым `gateway/requests.db` и `gateway/t013.db`) это не так: litellm логирует `provider_model` БЕЗ префикса провайдера (части до первого `/`). Примеры:
- `groq/openai/gpt-oss-120b` → в БД `openai/gpt-oss-120b`
- `groq/llama-3.3-70b-versatile` → в БД `llama-3.3-70b-versatile`
- `gemini/gemini-3.5-flash` → в БД `gemini-3.5-flash`
- `anthropic/claude-fable-5` (алиас `mock`) → в БД `claude-fable-5`

Без нормализации (`normalize_provider_model` — отсечение первого сегмента пути) сравнение `alias→provider_model` из конфига с колонкой БД никогда бы не совпало, и суммирование квоты дало бы 0 для любого алиаса. Задокументировано в докстринге `preflight_quota.py` и покрыто тестами (`test_normalize_provider_model_strips_first_segment_only`, `test_alias_provider_models_mapping`).

### Отклонения от спеки

- Добавлен необязательный флаг `--root` в CLI `preflight_quota.py` (не входил в заданный список флагов) — чисто аддитивный, для тестируемости без переменных окружения; не меняет поведение по умолчанию.
- Регекс парсинга ретрая в 429-тексте пришлось уточнить относительно докстрингового примера в спеке (символьный класс `[\dhms.]+` захватывал точку конца предложения после `3.1s.`) — исправлено на анкеринг к секундному суффиксу `(?:\d+h)?(?:\d+m)?\d+(?:\.\d+)?s`.

### Созданные файлы (owned paths, все в пределах заданных)

- tools/preflight_quota.py, tools/test_preflight_quota.py,
  tools/session_context.py, tools/test_session_context.py,
  .claude/settings.json

Ничего не закоммичено. Журнал маршрутизации не тронут. Дифф превышает ~100 строк — по правилу 3 обязателен вход critic до приёмки.

## Ревью critic (Opus, verbatim)

# Critic-ревью t-027 — вердикт: ДОРАБОТАТЬ

Код функционально корректен и соответствует спеке — блокеров в самом коде нет. Блокеры — механизменная гигиена коммита (правило 10), которую gate НЕ ловит на этих путях, поэтому Lead должен закрыть её сознательно. Ниже след, находки по серьёзности, и разбор по 9 вопросам ревью.

## СЛЕД (что читал / что запускал)

Читал: `tools/preflight_quota.py`, `tools/session_context.py`, `tools/test_preflight_quota.py`, `tools/test_session_context.py`, `.claude/settings.json`, `docs/SIBLING_MAP.md`, `gateway/config.yaml`, `gateway/budgets.yaml`, `tools/mechanism_gate.py`, `PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md` (grep).

Запускал (witness приложен):
- `python -m pytest tools/ gateway/ -q` → **205 passed in 7.98s** (совпадает с отчётом builder: 159+46).
- `SELECT DISTINCT model, provider_model FROM requests` по обеим БД. Живые пары: `groq/openai/gpt-oss-120b`→`openai/gpt-oss-120b`; `gemini/gemini-2.5-flash`→`gemini-2.5-flash`; `ollama_chat/qwen3:4b`→`qwen3:4b`; `anthropic/claude-fable-5`→`claude-fable-5`. **Отсечение первого сегмента верно для ВСЕХ провайдеров в живых данных** — находка builder о нормализации подтверждена.
- Трассировка `release_schedule` по `test_release_schedule_computes_go_at`: rows=[(now−22h,90000)], release@now+2h, headroom 10000<15000 до +2h, затем 100000 → go_at=now+2h. Совпадает. Часовые корзины оцениваются на КОНЦЕ часа (округление вверх, не оптимистично) — корректно.

## BLOCKING (закрыть до/при коммите; правка кода НЕ требуется)

**B1. Регистрация SessionStart-хука — механизм без зарегистрированного детектора отказа (правило 10(в)).**
`.claude/settings.json:3-5` + `tools/session_context.py` вводят обязанность на ВСЕ будущие сессии (печатают «реальность», которой сессия доверяет). Это механизм по D-0065. Grep `session_context|SessionStart|preflight_quota` по `PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md` — **нет совпадений**. Детектор отказа хука отсутствует. При fail-open дизайне сломанный хук печатает warning и exit 0 — тихо; ничто не проверяет, что NOW-строка ещё производится. Lead: зарегистрировать детектор тем же коммитом.

**B2. Осевой блок D-0055 не будет вынужден gate'ом — эти пути ВНЕ невода.**
`tools/mechanism_gate.py:42-57`: `MECHANISM_PREFIXES` содержит `.claude/agents/`, `.claude/skills/`, но НЕ `.claude/settings.json`; `tools/` сознательно вне невода. Значит коммит t-027 gate НЕ остановит. Это ровно случай «механизм вне невода» (D-0065). Lead: приложить осевой блок вручную (перечислением по осям 1-6, не прозой).

Оба блокера — Lead-tier работа при коммите (D-0058), а не дефекты кода. Функционально работу принимаю.

## NON-BLOCKING (находки; чинить по решению Lead)

**N1. Нормализация теряет провайдера — латентная коллизия хвостов.** `preflight_quota.py:92-100`. Два РАЗНЫХ провайдера с одинаковым хвостом слились бы в одну квотную группу — неверно (квоты раздельные). Корень — сама БД хранит уже усечённое `provider_model`. Тул делает максимум по имеющимся данным; ограничение записать явно. **Замеченный аналог (ось 2 SIBLING_MAP), докладываю не чиня.**

**N2. Группировка сливает разные алиасы одного хвоста (живые примеры):** intern+analyst → qwen3:4b; lead+mock → claude-fable-5. Сегодня безвредно. Следствие N1.

**N3. Прогноз go_at не учитывает probe-истину.** `preflight_quota.py:462` — расписание от SQLite-суммы, вердикт при probe>локали верит провайдеру, но go_at оптимистичен.

**N4. Дыра в fail-open на импорте.** `session_context.py:33-39` — import-time отказ (нет yaml, синтакс-ошибка в preflight_quota) обойдёт try/except в main() и даст traceback вместо одной warning-строки.

**N5. Заблокированная БД в `usage_in_window` не защищена** (`preflight_quota.py:166-174`) — `database is locked` уронит CLI трейсбеком. Громкий отказ лучше тихого неверного числа, потому non-blocking.

**N6. Gemini «REQUESTS N last 24h» считает только status='success'** — счётчик слегка занижен (неуспешные тоже жгут request-cap). Индикатор, не гейт.

**N7. Лимит по алиасу vs расход по группе provider_model** — два алиаса одной группы с разными limit_tokens дали бы вердикт, зависящий от того, какой --alias передан. Config-фут-ган, не баг кода.

## Разбор по 9 вопросам

1. Оконная математика — OK (граница инклюзивна, оба ts-формата, корзины на конце часа, округление вверх).
2. Мульти-db — OK с оговоркой N5 (битые/без таблицы пропускаются).
3. Нормализация — верна для всех живых записей; коллизии N1/N2 латентны.
4. session_context fail-open — OK с оговоркой N4 (2 теста, runtime-сбои накрыты).
5. settings.json схема — валидна; относительная команда резолвится при cwd=repo-root.
6. Тесты — меряют заявленное, real sqlite + tmp_path, без самоисполняющихся моков.
7. SQL — статические SELECT с ?-параметрами, инъекций нет.
8. Классовая полнота — ось 2: тул только API-контур, у субскрипционного нет token-стен → н-п, N1 на этой оси доложена; ось 5: покрыта (паттерн изоляции соблюдён).
9. Rule #1 — лишней сложности нет; --root/--json/--probe оправданы; регекс-фикс сверен трассировкой.

## Итог

Код t-027 корректен, покрыт тестами (205 passed, witness выше), нормализация сверена с живыми БД, оконная/расписательная математика прослежена. **Функционально — принял бы.** Вердикт **ДОРАБОТАТЬ** из-за B1 и B2 — обе закрываются Lead при коммите без правки кода. N1-N7 — на усмотрение Lead; N1/N2 достаточно задокументировать как ограничение.

## Приёмка Lead (Fable)

- **B1 закрыт**: детектор хука и preflight-правила зарегистрирован —
  чек 13(ж) WEEKLY_CALIBRATION_PROTOCOL (NOW-строка в транскриптах
  окна; новый 429-tooling-rejected при существующем preflight =
  обход/утечка).
- **B2 закрыт классово**: `.claude/settings.json` добавлен в
  MECHANISM_PREFIXES гейта + twin-тест (будущие правки хуков сами
  попадут под гейт); осевой блок этого коммита приложен вручную.
- **N1/N2**: задокументированы блоком KNOWN LIMIT в докстринге
  preflight_quota.py (данных для различения провайдеров в БД нет;
  фикс = логировать провайдера в sqlite_logger — очередь, ось 2).
- **N3/N4/N5**: в B1-батч (очередь CURRENT_CONTEXT). N6/N7 —
  приняты как ограничения, записаны здесь.
- Правило запуска — в PI_HARNESS.md (разрыв №3); слой 6 — правило 7
  judge-протокола. Полный прогон после правок гейта: 206 passed
  (witness в журнале, accepted t-027).
