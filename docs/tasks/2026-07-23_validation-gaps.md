# Закрытие гэпов валидации (гэп-анализ 2026-07-23, авторизация оператора «закрывай все пункты»)

Источник: гэп-анализ по t-296/t-297 (разведка + верификация негативов).
Ветка: claude/testing-gates-article-az920w. Форма: DAG (D-0080).

## Узлы

| Узел | Суть | Ярус | task_id | Статус |
|---|---|---|---|---|
| VG-1 | session_context: авто-починка core.hooksPath (WARN → auto-fix) + строка ts-дрейфа против хвоста журнала | builder | t-298 | in_progress |
| VG-2 | escape_check: sha256-пин JUDGE_SYSTEM_PROMPT (дрейф промпта судьи = блок pre-commit) | builder | t-299 | in_progress |
| VG-3 | negative_lint: PostToolUse-линт негативов без одноформенного контроля в результатах Agent (WARN) | builder | t-300 | in_progress |
| VG-4 | journal_echo WITNESS-слой: сверка witness с фактическим треком прогонов (команда+зелёность+пост-датирование правок) | builder | t-301 | in_progress |
| VG-5 | hygiene_gate: селективный блок класса «журнал мимо Edit/Write», ложные срабатывания git-команд — тесты и фикс | builder | t-302 | in_progress |
| VG-6 | parity_check: манифест паритета штаб↔toolkit-staging с хешами последнего синка, режим отчёта дрейфа | builder | t-303 | in_progress |
| VG-7 | П3-носители: очередь adversarial-экзаменов координатора, Next Required Action boot-diet, строка свежести DELEGATION_TABLE в калибровку | Lead | — | pending |
| VG-8 | critic-гейт по всем диффам VG-1..VG-6 (механизмы, R3 обязателен; механический слой = witness'ы + контрольный полный прогон Lead) | critic | — | pending |
| VG-9 | Приёмка, осевые блоки R10, детекторные строки (чеки 12/20/26/30а), порт-очередь тулкита (D-0074), коммиты через живые гейты | Lead | — | pending |

## Зависимости

VG-1..VG-6 независимы (владение путями не пересекается).
VG-8 после VG-1..VG-6. VG-9 после VG-8. VG-7 независим.

## Владение путями (R4)

- VG-1: tools/session_context.py, tools/test_session_context.py, tools/test_session_context_wiring.py
- VG-2: tools/escape_check.py, tools/test_escape_check.py, tools/escape_allowlist.json
- VG-3: tools/negative_lint.py (новый), tools/test_negative_lint.py (новый); .claude/settings.json НЕ трогает (сниппет контентом, ставит Lead — D-0069)
- VG-4: tools/journal_echo.py, tools/test_witness_echo.py, tools/test_journal_echo.py (только при необходимости)
- VG-5: tools/hygiene_gate.py, tools/test_hygiene_gate.py
- VG-6: tools/parity_check.py (новый), tools/test_parity_check.py (новый), tools/parity_manifest.json (новый)
