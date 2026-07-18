# Корпус shadow-реплея Lead-работ (D-0080 п.3)

Источник: scout t-178 (принят 2026-07-18 12:04, поправка Lead по
строке 14 внесена). 16 builder-классных dispatch_skipped окна
07-11..07-18; ниже — вердикты реплеябельности. Прогон: target =
lead-sonnet (первично; Middle — вторично, строка coding→Middle
rejected калибровкой №2), судья судит эквивалентность target-ответа
ФАКТИЧЕСКОМУ диффу Lead (git — ground truth).

| # | Работа | Коммит | Вердикт | Черновой replay-промпт |
|---|---|---|---|---|
| 1 | t-040 счётный скрипт калибровки | 3243e0e | YES | Напиши скрипт подсчёта метрик калибровки (чеки 3/13) по журналу routing-log.jsonl |
| 2 | savings_report (чек 18) | c5c3606 | YES | Добавь еженедельный расчёт экономии (PRE vs ROUTED) по цифрам usage_report с тестами |
| 3 | три doc-правки + порт shadow_eval | 276f211 | PARTIAL | смешанный дифф (doc + код) |
| 4 | снятие PRE-RELEASE баннера | 9f31cda | YES | Удали PRE-RELEASE баннер из toolkit/README (4 строки) |
| 5 | session_context F-37-маркер | 8fa8d65 | YES | Добавь маркер декларативности MODEL-строки + docstring-ограничение + 4 теста |
| 6 | F-38 metrics.py фикс формулы | 9a5386e | NO | требует эмпирики живых кэш-строк |
| 7 | алиасы middle-oss/middle-gemini | d91ec9b | YES | Добавь два алиаса в gateway/config.yaml |
| 8 | judge-haiku калибровка | — | NO | живой прогон-артефакт |
| 9 | фикстура экзамена №1 | 0cf1cd7 | NO | судейский дизайн с ключами |
| 10 | EN-перевод статьи | локальный docx | NO | авторский голос |
| 11 | t-117 фикс 1 (shutil.which) | e9f7f27 | YES | Почини резолв claude.cmd в exam_runner (CreateProcess/PATHEXT) |
| 12 | t-117 фикс 2 (stdin вместо argv) | 478c395 | YES | Передавай промпт субпроцессу через stdin (обход парсера cmd.exe) + смок |
| 13 | сборка kit v4 | манифест 888c50e | NO | операционное копирование |
| 14 | t-159 доработка (stdin.buffer) | 224eb57/19b4c91 (поправка Lead) | PARTIAL | механический фикс 6 строк / 3 файла |
| 15 | t-159 фикс matcher'ов | f1f4f18 | YES | Расширь settings.json matcher'ы + ветку dod_track для PowerShell + 2 теста |
| 16 | хвосты порт-хода | c551a38 | PARTIAL | три разнотипные операции |

Итог: 8 YES / 3 PARTIAL / 5 NO. Прогону подлежат YES: №1, 2, 4, 5,
7, 11, 12, 15.
