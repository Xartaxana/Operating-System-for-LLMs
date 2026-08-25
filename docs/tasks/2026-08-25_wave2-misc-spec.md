# Спека билдера М — мелочи пунктов 5/6 очереди (волна 2)

Драфт Lead сам (dispatch_skipped designer — четыре пункта с готовыми
диагнозами t-603, сборка). Основание хода — слово оператора
«в параллели: 2, 4, 5, 6»; судьба пунктов —
docs/tasks/2026-08-25_queue8-closure.md, раздел «Волна».

## М1 — клещи $CLAUDE_PROJECT_DIR, OS-конец

Носитель: `tools/session_context.py:1630`
`_HOOK_COMMAND_RE = re.compile(r"^python tools/([^/\\]+\.py)$")`.
Требование: регексп принимает РОВНО ДВЕ формы, обе с захватом имени
файла той же группой: (1) `python tools/<file>.py` (как сейчас,
байт-в-байт); (2) `python "$CLAUDE_PROJECT_DIR/tools/<file>.py"` —
двойные кавычки, прямые слэши (каноническая форма Dog 14.08).
Инвариант (докстринг :1622-1629 обновить): ЛЮБАЯ иная форма — как
сейчас, честный «unparsed command» WARNING; парсер не становится
шире двух форм. Края (тест НА и ЗА): одинарные кавычки → unparsed;
без кавычек с $CLAUDE_PROJECT_DIR → unparsed; бэкслэши внутри формы
(2) → unparsed; хвостовые флаги → unparsed (как сейчас).
Кит-конец (toolkit wiring_check:217 свой экземпляр + нормализация
settings) — НЕ ЦЕЛЬ: именованная строка порт-очереди завтра.

## М2 — corpus_growth: Δ к границе окна (F15-ii)

Носитель: `tools/corpus_growth.py:425` — prev_entry берётся ПОСЛЕДНЕЙ
записью сайдкара; для чека 34 «Δ окна» нечитаемы без поправки.
Требование: аргумент `--baseline-ts <ISO>`: prev_entry = последняя
запись сайдкара с ts <= baseline-ts. Без аргумента — поведение
байт-в-байт как сейчас (негативный контроль: прогон без флага до и
после правки даёт идентичный вывод). Края: ни одной записи <= ts →
prev_entry None (Δ печатаются как сейчас при пустом сайдкаре);
битый ISO → понятная ошибка, exit != 0; ts точно равный записи →
запись включается (<=, граница названа тестом НА и ЗА).

## М3 — savings_report: оконные аргументы (F15-iii)

Носитель: `tools/savings_report.py:294-300` — контрфакт всегда от
начала routed-истории. Требование: `--window-start <ISO>` и
`--window-end <ISO>`: фильтруют УЧИТЫВАЕМЫЕ события по окну;
семантика контрфакта (`--routed-start` как база сравнения) НЕ
меняется — окна режут выборку, не переопределяют базу. При заданном
окне шапка вывода печатает границы. Без аргументов — вывод
байт-в-байт как сейчас (негативный контроль). Края: пустое окно →
нули, не падение; window-start > window-end → ошибка, exit != 0;
только один из двух флагов → законно (полуоткрытое окно).

## М4 — правило 9г journal_validator: семантика reopen соседа

Носитель: `tools/journal_validator.py`, докстринг ветки правила 9
(повторный delegated). ТОЛЬКО докстринг, ноль изменений поведения:
записать — у AO3 маркер `reopen:` в notes повторного delegated есть
ИХ легальное третье основание (их коммиты 441d322/6f97508); при
кросс-чтении ИХ журнала эту форму НАДО allowlist'ить; НАША семантика
не меняется (reopen запрещён, D-0060 — ядро). Тест не нужен;
негативный контроль — существующие батареи валидатора зелёные
без правок.

## Дано (D-0106): перечень выше (файл:строка из дайджеста t-603,
снят сегодня); дополнительно: logs/corpus_growth.jsonl (сайдкар —
только чтение), logs/routing-log.jsonl (только чтение),
docs/task_reports/2026-08-16_boot-diet-extractions.md:339-344 и :94-119
(тексты клещей и reopen — только чтение).

## owns (ПАРАЛЛЕЛЬНАЯ волна, R4): tools/session_context.py,
tools/corpus_growth.py, tools/savings_report.py,
tools/journal_validator.py + их тестовые файлы (существующие;
для savings_report при отсутствии теста — создать
tools/test_savings_report.py).

## non-goals: toolkit/** (мораторий D-0074); dispatch_gate/owns_gate/
hygiene_gate/warn_density/warn_layers (чужие волновые owns);
поведение валидатора; параметры по умолчанию всех трёх скриптов.

## СУЖЕННЫЙ witness (волна параллельна, R4 — канон НЕ гонять,
его снимет координатор на сходе): прогоны тестовых файлов ВСЕХ
owned-путей поимённо:
`python -m pytest tools/test_session_context.py tools/test_session_context_autoboot.py tools/test_session_context_layer_a.py tools/test_session_context_wiring.py tools/test_f61_halfstate.py tools/test_p4_stdin_deadline.py tools/test_wiring_check.py tools/test_journal_validator.py tools/test_corpus_growth.py tools/test_savings_report.py -q`
(состав проверен ls 16:15 — все десять файлов существуют) + оба
негативных контроля идентичности вывода (М2, М3) дословно.
