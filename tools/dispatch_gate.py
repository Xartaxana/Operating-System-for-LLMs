"""dispatch_gate.py (t-152, policy-as-code «ход вниз») -- PreToolUse-хук
Claude Code на Task/Agent-тул, проверяющий ФОРМУ диспатча ДО отправки
(D-0054/D-0073/правило 7 CLAUDE.md кита): DoD-маркеры в промпте
builder'а, манифест-маркеры на пишущем диспатче, лейбл description
начинается с модели воркера. Механизация правила 11 CLAUDE.md
(«воркер вернёт вопросами» -> «диспатч не уйдёт вовсе», слово
оператора 07-16, docs/tasks/2026-07-16_policy-as-code-design.md
п.1 «ход ВНИЗ»).

КОНТРАКТ PreToolUse -- та же эмпирика, что в tools/critic_gate.py
этого кита (payload["tool_name"] in {"Task","Agent"} для вызова
субагента, tool_input.subagent_type, payload["cwd"], exit 0 без
вывода -- разрешить, exit 2 + stderr -- заблокировать). ДОПОЛНЕНО
СОБСТВЕННОЙ эмпирикой t-150 живых смоков (тот же кит,
scratchpad/t150_dod_smoke/smoke_builder4_transcript.jsonl): реальный
tool_input вызова Agent содержал поля {"description": str,
"subagent_type": str, "prompt": str, "run_in_background": bool} --
т.е. tool_input.description и tool_input.prompt -- РЕАЛЬНЫЕ,
подтверждённые живым payload'ом поля, не гипотеза. Если поле
description ОТСУТСТВУЕТ в tool_input -- проверка 3 (лейбл)
ПРОПУСКАЕТСЯ (не блокирует) -- задокументированный факт, спека т-152
прямо это разрешает («Если поля description в payload нет — пропуск,
задокументируй факт»).

ЭМПИРИКА ПОРЯДКА НЕСКОЛЬКИХ ХУКОВ НА ОДНОМ MATCHER (спека т-152 п.6
требует явно; смок -- отдельный probe в
scratchpad/t152_hook_order_probe/, НЕ в этом ките, дешёвый
диагностический эксперимент с двумя фиктивными хуками на
matcher="Bash"): несколько command-хуков под ОДНИМ matcher-блоком
PreToolUse ВСЕ выполняются, НЕЗАВИСИМО от exit_code друг друга --
exit 2 ПЕРВОГО хука НЕ отменяет запуск ВТОРОГО того же события
(зафиксировано: probe_a.py exit 2 + probe_b.py exit 0 на одном
Bash-вызове -- ОБА получили пару hook_started/hook_response в
transcript, ОБА дописали свою строку в лог; итоговая блокировка
тула -- ОБЪЕДИНЕНИЕ: любой exit 2 в массиве блокирует, но это НЕ
short-circuit цепочка).

ПОСЛЕДСТВИЕ ДЛЯ ЭТОГО КИТА (НАХОДКА, не решается этим файлом и вне
объявленного scope т-152 -- вынесена в отчёт координатору): порядок
регистрации (dispatch_gate ПЕРЕД critic_gate в settings.json, как
требует спека п.6) НЕ даёт защитный short-circuit. Если dispatch_gate
блокирует диспатч критика (например, из-за лейбла без модели),
critic_gate.py ВСЁ РАВНО выполнится на том же событии и, если это
первый вызов критика в сессии/каталоге, СПИШЕТ его "один вызов на
сессию" (создаст .claude/critic_used + critic_snapshot.json), хотя
сам диспатч был заблокирован dispatch_gate'ом и критик реально не
запустился. Это гонка/расход лимита на заблокированной попытке --
дефект ВЗАИМОДЕЙСТВИЯ двух гейтов, не самого dispatch_gate.py.

ПРОВЕРКИ (только для tool_name in {"Task","Agent"}; любой другой
тул -- пропуск exit 0 без побочных эффектов; хук STATELESS -- спека
п.5, никаких файлов состояния не создаёт и не читает):

 1. subagent_type == "builder": tool_input.prompt должен содержать
    DoD-маркер (DOD_MARKERS_RE ниже). Нет ни одного совпадения ->
    БЛОК (BLOCK_MESSAGE_NO_DOD).
 2. subagent_type == "builder" И prompt содержит признак записи
    (WRITE_INDICATORS_RE) -- КОНСЕРВАТИВНАЯ эвристика спеки:
    блокируем ТОЛЬКО когда есть write-признак И НЕТ ОБОИХ
    манифест-маркеров (MANIFEST_GIVEN_RE И MANIFEST_OWNS_RE, оба
    обязательны) -> БЛОК (BLOCK_MESSAGE_NO_MANIFEST). Write-признаков
    нет -> проверка 2 пропускается целиком (read-only диспатч
    манифеста не требует, правило 11 кита). "owns" сам по себе --
    одновременно write-признак И один из двух манифест-маркеров
    (спека явно: "если owns уже есть, значит манифест писали") --
    значит промпт, где встретилось только "owns" без "дано"/"given",
    ловится этой же проверкой (write-признак есть, манифест неполон).
 3. ЛЮБОЙ subagent_type (включая critic/scout): tool_input.description,
    ЕСЛИ ПРИСУТСТВУЕТ, должен начинаться с модели воркера
    (LABEL_MODEL_PREFIX_RE) -> иначе БЛОК (BLOCK_MESSAGE_NO_LABEL).
    description отсутствует в payload -> проверка 3 пропускается.
 4. critic/scout (и любой subagent_type != "builder") -- проверки 1
    и 2 НЕ применяются (их DoD-форма другая, спека явно ограничивает
    семантику текстом промпта только для builder'а).

ПРИОРИТЕТ при НЕСКОЛЬКИХ одновременных нарушениях: 1 -> 2 -> 3,
первое найденное -- единственное сообщение в stderr (хук блокирует
ОДНИМ exit 2, не накапливает список). Спека порядок конфликтующих
сообщений не определяет явно -- это самостоятельное инженерное
решение (естественный порядок перечисления проверок в спеке),
задокументировано, не молча.

Fail-open на нераспознаваемый JSON -- тот же принцип, что у
critic_gate.py/dod_track.py/dod_gate.py этого кита.

t-152 RETRY (координатор, 2026-07-16, чинит НАХОДКУ №2 из
builder-отчёта t-152): WRITE_INDICATORS_RE ПЕРЕВЕДЕНА на \\b-границы
слова (py3 re -- Unicode-aware по умолчанию для str-паттернов, \\b
корректно видит границу между кириллическими буквами и
пробелом/пунктуацией/началом строки). ДО этой правки "правь" (без
границ) матчился ПОДСТРОКОЙ внутри обычных слов -- "поправь",
"исправь", "заправь", "направь" -- т.к. между "о"/"с"/"а" и "п" нет
границы \\w|\\W, а буквальный текст спеки "правь" всё равно находился
как substring где угодно внутри слова. С \\b "\\bправь\\b" матчит
ТОЛЬКО "правь" как отдельный токен (после пробела/пунктуации/начала
строки, до пробела/пунктуации/конца строки) -- "поправь"/"исправь"
теперь НЕ триггерят write-признак (негативный лок --
test_dispatch_gate.py, test_pravj_word_boundary_does_not_match_
poprav_or_isprav). Остальные альтернативы (owns/запиши/создай
файл/измени файл) получили те же \\b-границы для единообразия
(координатор просил границы для write-признаков в целом, не только
для "правь"); MANIFEST_GIVEN_RE/MANIFEST_OWNS_RE НЕ тронуты --
retry-спека называла только WRITE_INDICATORS_RE, расширять на
манифест-маркеры сам не стал (не в объявленном scope этого ретрая).

t-159 ФИКС КОДИРОВКИ STDIN (очередь v5 п.3, найдено в журнале
№10б-t1): кириллические маркеры («Дано:», «критерии приёмки») не
распознавались на реальном харнессе. ЭМПИРИКА (позитивный/негативный
контроль, F-30/F-34): `sys.stdin.read()` -- текстовое чтение --
декодирует байты кодировкой `sys.stdin.encoding`, которая на этой
машине равна `locale.getpreferredencoding()` = "cp1251" (проверено
`python -c "import locale,sys;print(locale.getpreferredencoding(),
sys.stdin.encoding)"` -> "cp1251 cp1251"), НЕ UTF-8. Харнесс пишет
payload UTF-8-байтами -- при чтении через cp1251 кириллица
превращается в mojibake, регексы MANIFEST_GIVEN_RE/DOD_MARKERS_RE
перестают матчить. Прямое воспроизведение ДО фикса (subprocess с
СЫРЫМИ UTF-8-байтами на stdin, БЕЗ text=True/encoding -- ровно так,
как харнесс кормит дочерний процесс): промпт с "Дано: репо целиком.
owns: tools/x.py." и DoD-маркерами дал exit_code=2 с mojibake-
сообщением "манифеста ... не найден" -- ложный блок легального
пишущего диспатча (scratchpad-проба builder-сессии t-159).
ФИКС: читаем stdin БАЙТАМИ (`sys.stdin.buffer.read()`, обходит
текстовый слой и его платформенную кодировку) и декодируем ЯВНО UTF-8
с fallback `errors="replace"` (харнесс отправляет UTF-8 -- основной
путь; replace вместо strict -- защита от битых байтов, чтобы хук не
падал исключением на мусорном вводе, тот же fail-open принцип, что у
остального парсинга этого файла). Юнит-тест с кириллицей гоняется
ДВУМЯ формами (test_dispatch_gate.py): (1) через subprocess с
ASCII-safe JSON (`ensure_ascii=True` -- \\uXXXX-эскейпы, независимо от
платформенной кодировки, это была бы "случайно рабочая" форма и ДО
фикса) и (2) через subprocess с СЫРЫМИ UTF-8-байтами (`ensure_ascii=
False`, input=bytes без text=True) -- именно форма (2) ловит регресс
до фикса; обе обязаны проходить одинаково ПОСЛЕ фикса.

БАТЧ 07-28 п.(б): ПОДСТРОЧНАЯ СЛАБОСТЬ owns-СЛОВА В ПРОВЕРКЕ 2 (класс,
найденный в owns_gate.py при t-332 и доложенный его исполнителем как
живущий ЗДЕСЬ, в dispatch_gate.py, с ПРОТИВОПОЛОЖНОЙ ценой ошибки:
owns_gate -- WARN-only слепота/ложный WARN; здесь -- БЛОКИРУЮЩИЙ гейт,
цена ошибки -- либо молчаливый пропуск пишущего диспатча без реального
манифеста, либо ложный блок легального read-only). ДЫРА ДО ЭТОЙ ПРАВКИ
(эмпирически подтверждено юнит-тестом
test_b_owns_only_as_filename_substring_in_given_now_blocks_closed_hole
в test_dispatch_gate.py, см. пометку "ЗАКРЫТАЯ ДЫРА" на самом тесте
-- имя исправлено критиком t-336, F3, прежняя ссылка называла
несуществующий тест): MANIFEST_OWNS_RE = r"owns"
(голое, БЕЗ границ слова) использовался в проверке 2 как ВТОРОЙ
обязательный манифест-маркер (has_manifest = given И owns). Пишущий
builder-промпт, где owns-слово встречалось ТОЛЬКО подстрокой внутри
имени файла корзины "дано" (напр. "Дано: tools/owns_gate.py."), БЕЗ
единой настоящей owns-декларации -- давал MANIFEST_OWNS_RE.search()
== True (подстрока внутри имени файла) -> has_manifest ложно True ->
ГЕЙТ ПРОПУСКАЛ пишущий диспатч БЕЗ РЕАЛЬНОГО МАНИФЕСТА (правило
11/D-0073 нарушено молча). ФИКС: заведён ЭКСПОРТИРУЕМЫЙ OWNS_WORD_RE
(тот же паттерн с границей слова, что owns_gate.py уже вводил
ЛОКАЛЬНО для своей WARN-only экстракции при t-332/attempt 3 -- теперь
единая точка правды, D-0043; owns_gate.py импортирует ЕГО вместо
своей копии) -- проверка 2 отныне считает owns-маркер манифеста
присутствующим ТОЛЬКО по OWNS_WORD_RE. MANIFEST_OWNS_RE (голый, без
границ) СОХРАНЁН БАЙТ-В-БАЙТ как константа -- он больше НЕ участвует
в decide() этого файла, но остаётся ФОЛЛБЕК-потребителем owns_gate.py
(толерантность к кривым формам, где owns-слово вкраплено в слово и
является ЕДИНСТВЕННЫМ маркером промпта, см. докстринг owns_gate.py)
-- удаление константы сломало бы этот фоллбек, спека прямо запрещает
её удалять.

ОБРАТНАЯ ГРАНЬ ТОГО ЖЕ КЛАССА (доложена спекой как гипотеза, ПРОВЕРЕНА
ЭМПИРИЧЕСКИ, правило 3 роли): "если owns-слово участвует в
WRITE_INDICATORS_RE подстрокой -- read-only диспатч, называющий
owns_gate.py в корзине, ложно классифицируется пишущим и блокируется".
ФАКТ КОДА (уже на входе в эту правку, см. абзац "t-152 RETRY" выше и
тест test_pravj_word_boundary_does_not_match_poprav_or_isprav в
test_dispatch_gate.py): WRITE_INDICATORS_RE УЖЕ несёт owns-альтернативу
С ГРАНИЦЕЙ слова с retry t-152 -- переход на границы слова был сделан
для ВСЕХ пяти альтернатив этого регекса, не только "правь". Эта грань
класса, таким образом, УЖЕ ЗАКРЫТА до этой правки -- отдельного фикса
не требует; test_c_readonly_dispatch_mentioning_owns_gate_filename_in_
given_not_blocked в test_dispatch_gate.py (имя исправлено критиком
t-336, F3, прежняя ссылка называла несуществующий тест) фиксирует это
ЭМПИРИЧЕСКИ как регресс-пин (не как новую правку).

ОСМОТР MANIFEST_GIVEN_RE И WRITE_INDICATORS_RE НА ТУ ЖЕ СЛАБОСТЬ (п.2
спеки батча): WRITE_INDICATORS_RE осмотрена целиком -- ВСЕ пять
альтернатив (owns/запиши/создай файл/правь/измени файл) уже несут
границы слова с retry t-152, правка не нужна. MANIFEST_GIVEN_RE = r"дано
|given" (БЕЗ границ) НЕСЛА ТУ ЖЕ СЛАБОСТЬ, подтверждённую эмпирически:
русское слово "продано" (обычное "всё продано на складе") содержит
подстроку "дано" -- MANIFEST_GIVEN_RE.search() матчил её ДО фикса как
ложный given-маркер, хотя настоящего "Дано:"/"Given:" в промпте не было
(см. test_manifest_given_word_boundary_prodano_false_positive_fixed в
test_dispatch_gate.py). ФИКС: MANIFEST_GIVEN_RE переведена на границы
слова -- та же форма, что WRITE_INDICATORS_RE уже применяет. Чисто-
русские формы существующих тестов ("Дано:", "дано —", "Given:") имеют
небуквенное окружение (пробел/двоеточие/начало строки) с ОБЕИХ сторон
-- граница слова на них и раньше матчила идентично, правка ничего не
меняет для легальных форм (осмотр подтверждён прогоном существующих
тестов до и после правки, все прошли без изменения ассертов).

КРИТИК t-336 (вердикт fit_with_fixes по сдаче батча 07-28 п.(б)) --
F1, ТОТ ЖЕ КЛАСС В DOD_MARKERS_RE (главная доработка): проверка 1
(DOD_MARKERS_RE) несла ТОЧНО ТУ ЖЕ подстрочную слабость, что чинилась
выше в проверке 2 -- ДО этой правки `DOD_MARKERS_RE = r"DoD|критери[ия]
приёмки|witness|проверочн\\w+ прогон"` (БЕЗ границ слова у альтернатив
"DoD"/"witness"). ЭМПИРИКА КРИТИКА (живой прогон, (0,'') против (2,
блок) при замене имени файла): builder-промпт БЕЗ настоящего DoD-
маркера, называющий tools/dod_gate.py или tools/dod_track.py в корзине
"дано", давал ЛОЖНОЕ совпадение -- IGNORECASE-регекс "DoD" матчил
подстроку "dod" внутри "dod_gate.py"/"dod_track.jsonl" -> проверка 1
ложно пропускала диспатч БЕЗ DoD (правило 11 нарушено молча), симметрично
дыре t-332/OWNS_WORD_RE. ФИКС: `\\bDoD\\b` и `\\bwitness\\b` -- `\\bDoD\\b`
НЕ матчит "dod_gate.py"/"dod_track.jsonl" (`_` -- словесный символ,
границы нет), ПРОДОЛЖАЕТ матчить "DoD:" и "DoD-маркер" (`:`/`-` --
не-словесные, граница есть); `\\bwitness\\b` НЕ матчит
"test_witness_echo.py" (`_` после "witness"), матчит слово "witness"
само по себе. Многословные RU-альтернативы (`критери[ия] приёмки`,
`проверочн\\w+ прогон`) НЕ тронуты -- ОСМОТРЕНЫ (п.2 спеки батча) и
признаны не несущими той же слабости в реалистичных формах промпта:
это фразы из ≥2 слов с явными пробельными разделителями, тестовые
файлы/имена с такими последовательностями букв как ложный подстрочный
триггер координатором не найдены, границы слова для них -- ИЗБЫТОЧНАЯ
правка вне обоснованного класса (задокументировано явно, не молчаливое
решение). Именные тесты в test_dispatch_gate.py:
test_f_dod_marker_only_as_filename_substring_now_blocks_closed_hole
(закрытая дыра dod_gate.py/dod_track.py в корзине без настоящего DoD),
test_g_dod_word_boundary_recognizes_colon_and_hyphen_forms ("DoD:" и
"DoD-маркер" по-прежнему маркер),
test_h_witness_word_boundary_does_not_match_test_witness_echo_filename
(test_witness_echo.py в корзине без слова "witness" -- не маркер).

ЧАСТЬ A (t-343, батч 2 находок калибровки №5, D-0096 п.5 -> машинный
слой по рецидиву): WARN-слой «given-пути существуют». Мотив (чек 23
калибровки №5): спека t-338 утверждала существование
tools/wiring_check.py, файла не было -- вскрыто только возвратом
билдера, ХОТЯ это дешёвая детерминированная встреча (путь НАЗВАН в
тексте диспатча ДО отправки -- os.path.exists проверяем сразу).

КОНТРАКТ: НОВЫЙ независимый слой поверх БЛОКИРУЮЩЕГО гейта -- exit-2
ветки decide() (проверки 1/2/3 выше) НЕ ЗАТРОНУТЫ этой правкой ни
байтом; given_path_warn() -- ОТДЕЛЬНАЯ функция, decide() её не
вызывает и её результат НЕ участвует в exit_code. main() вызывает её
ТОЛЬКО когда decide() уже вернула (0, "") -- если гейт блокирует по
другой причине, дальше не идём (спека прямо разрешает не печатать WARN
в этом случае, "не усложняй"). Результат -- ТОЛЬКО additionalContext
JSON на stdout (тот же протокол, что owns_gate.py уже использует для
своего WARN-слоя), exit_code main() всегда 0 на этой ветке.

ИЗВЛЕЧЕНИЕ (extract_given_candidates -> GIVEN_ABS_WIN_PATH_RE /
GIVEN_REPO_REL_PATH_RE): два вида локальных путей --
 (а) абсолютный Windows-путь: `[A-Za-z]:[\\\\/]...\\.ext` -- тело пути
     (`_PATH_BODY_CHAR`) исключает пробелы/кавычки/ёлочки/пайп и,
     НАРОЧНО (спека п.4), плейсхолдер-символы `<>*{}$` -- любой
     плейсхолдер (`<имя>`, `*.py`, `{name}`, `$VAR`) обрывает
     совпадение ДО обязательного `\\.ext`, поэтому такие формы просто
     НЕ извлекаются (не требуют отдельного фильтра-исключения);
     запятая/точка-с-запятой ТОЖЕ исключены из тела -- собственное
     инженерное решение (спека их не называет явно) против жадного
     переползания через "path1.py,path2.py" без пробела в ОДНО ложное
     совпадение.
 (б) репо-относительный путь: ТОЛЬКО с одним из шести префиксов
     (tools|gateway|PROCESS|docs|\\.claude|\\.githooks) и расширением
     файла -- каталоги/голые имена не матчатся структурно (регекс
     требует `\\.ext` в хвосте). Отрицательный lookbehind
     `(?<![\\w/\\\\])` перед префиксом закрывает ДВЕ вещи разом: (1) не
     матчить префикс, если он часть большего слова, (2) НЕ матчить его
     как ПОДСТРОКУ внутри уже извлечённого абсолютного пути (напр.
     "D:/repo/tools/x.py" -- символ ПЕРЕД "tools" там "/", lookbehind
     не пропускает -- абсолютная и относительная формы одного файла не
     задваиваются).

ИЗВЕСТНЫЙ КОРЕНЬ И ЧУЖИЕ ДЕРЕВЬЯ (спека п.4, ФОРМУЛИРОВКА СПЕКИ
ДОПУСКАЛА ДВЕ РАЗНЫЕ ТРАКТОВКИ -- задокументировано явно как
СОБСТВЕННОЕ инженерное решение, не угадано молча): буквальный список
трёх путей в спеке (D:\\Improving_AI\\..., D:\\AO3_tests\\..., D:\\Dog\\...)
неоднозначен -- один из них ТЕКСТУАЛЬНО совпадает с корнем ЭТОГО
самого репо, и одновременно спека явно требует тестом "чужое дерево
(D:\\Dog\\нет.py) -> нет warn". Буквальное прочтение "все три -- всегда
исключение" сделало бы проверку абсолютных путей СОБСТВЕННОГО репо
(частый стиль в манифестах этого же кита: "owns (ABSOLUTE write
paths): D:/repo/tools/x.py") НИКОГДА не срабатывающей -- асимметрично
с относительными путями, которые проверяются всегда, и, похоже,
противоречит мотиву механизма (t-338 мог с равным успехом быть
абсолютным путём). РЕШЕНИЕ: "известный корень" = payload["cwd"] ТЕКУЩЕГО
диспатча (та же точка отсчёта, что owns_gate.py уже использует для
своего sidecar) -- абсолютный путь-кандидат ПРОВЕРЯЕТСЯ, только если он
лежит ВНУТРИ этого корня (_is_under_root, normcase+normpath сравнение);
абсолютный путь ВНЕ него (любой другой диск/дерево, включая примеры
спеки AO3_tests/Dog) -- НЕ проверяется вовсе, ни warn, ни ошибка. Это
одновременно закрывает ОБЯЗАТЕЛЬНЫЙ тест D:\\Dog\\нет.py (чужой корень)
И оставляет механизм РАБОТАЮЩИМ на собственном репо (мотивирующий
кейс). Координатору стоит подтвердить это прочтение отдельно -- см.
отчёт билдера.

ПОРОГ ШУМА (GIVEN_PATH_WARN_SUMMARY_THRESHOLD = 10, format_given_path_
warn): спека содержит два, на первый взгляд конфликтующих утверждения
-- "предупреждать только если несуществующих <= 10" (читается как "не
предупреждать вовсе выше порога") и тут же "больше -- ...печатай
сводкой «N путей не существует, первые 3: ...»" (читается как "печатай
[что-то], то есть ВСЁ ЖЕ предупреждай, просто в другой форме"). Если бы
выше порога вообще ничего не печаталось, инструкция про формат сводки
была бы мёртвым текстом. РЕШЕНИЕ (синтез обеих половин, задокументировано):
<= 10 -- полный список всех отсутствующих путей; > 10 -- сводка "N
путей не существует, первые 3: <path1>, <path2>, <path3>" -- ОБЕ ветки
печатают WARN, различается только ФОРМА. Граница тестирована ОБЕИМИ
сторонами (правило 6а): 10 -> полная форма, 11 -> сводка
(test_given_path_warn_threshold_boundary_10_vs_11 в
test_dispatch_gate.py).

FAIL-OPEN: given_path_warn() типизированно возвращает "" на любой
нераспознанный payload/tool_input/prompt; main() дополнительно
оборачивает вызов в try/except (belt-and-suspenders, тот же принцип,
что owns_gate.py) -- адверсариальный вход не должен уронить БЛОКИРУЮЩИЙ
хук трейсбеком из-за WARN-слоя."""

import json
import os
import re
import sys

DOD_MARKERS_RE = re.compile(
    r"\bDoD\b|критери[ия] приёмки|\bwitness\b|проверочн\w+ прогон", re.IGNORECASE
)
WRITE_INDICATORS_RE = re.compile(
    r"\bowns\b|\bзапиши\b|\bсоздай файл\b|\bправь\b|\bизмени файл\b", re.IGNORECASE
)
# Батч 07-28 п.(б): границы слова -- "продано" содержит "дано" подстрокой
# без границы (см. докстринг модуля выше, "ОСМОТР MANIFEST_GIVEN_RE").
MANIFEST_GIVEN_RE = re.compile(r"\bдано\b|\bgiven\b", re.IGNORECASE)
# СОХРАНЕНА БАЙТ-В-БАЙТ (спека батча 07-28 запрещает удалять): голая,
# БЕЗ границы слова -- это дефект класса t-332 сам по себе (см.
# докстринг модуля выше), проверка 2 её больше НЕ использует, но
# owns_gate.py импортирует её как ФОЛЛБЕК своей экстракции.
MANIFEST_OWNS_RE = re.compile(r"owns", re.IGNORECASE)
# ЭКСПОРТИРУЕМЫЙ фикс дыры t-332: owns-маркер манифеста в проверке 2
# признаётся присутствующим ТОЛЬКО когда "owns" стоит ОТДЕЛЬНЫМ словом
# -- подстрока внутри имени файла ("owns_gate.py" в корзине "дано") НЕ
# является манифестом (класс, найденный в owns_gate.py при t-332,
# доложен исполнителем как живущий здесь же). Тот же паттерн, что
# owns_gate.py вводил локально -- теперь единая точка правды (D-0043),
# owns_gate.py импортирует ИМЕННО этот объект.
OWNS_WORD_RE = re.compile(r"\bowns\b", re.IGNORECASE)
LABEL_MODEL_PREFIX_RE = re.compile(r"^(haiku|sonnet|opus|fable|claude)[ :-]", re.IGNORECASE)

BLOCK_MESSAGE_NO_DOD = (
    "Диспатч builder'а без DoD не уходит (правило 11): впиши критерии "
    "приёмки и проверочный прогон, чей вывод станет witness"
)
BLOCK_MESSAGE_NO_MANIFEST = (
    "Пишущий диспатч без манифеста контекста (given/owns) не уходит "
    "(правило 11/D-0073)"
)
BLOCK_MESSAGE_NO_LABEL = (
    "Лейбл диспатча начинается с модели воркера (правило 7): 'sonnet: …'"
)


def decide(payload: dict) -> tuple[int, str]:
    """Чистая логика решения, без I/O -- тестируемая напрямую (тот же
    стиль, что critic_gate.decide). Возвращает (exit_code,
    stderr_message); "" значит "ничего не писать в stderr"."""
    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, ""

    tool_input = payload.get("tool_input") or {}
    subagent_type = tool_input.get("subagent_type")
    prompt = tool_input.get("prompt") or ""
    description = tool_input.get("description")

    if subagent_type == "builder":
        if not DOD_MARKERS_RE.search(prompt):
            return 2, BLOCK_MESSAGE_NO_DOD

        if WRITE_INDICATORS_RE.search(prompt):
            # Батч 07-28 п.(б): owns-маркер манифеста -- ТОЛЬКО по
            # OWNS_WORD_RE (граница слова), не по голому MANIFEST_OWNS_RE
            # -- см. докстринг модуля, "БАТЧ 07-28 п.(б)".
            has_manifest = bool(MANIFEST_GIVEN_RE.search(prompt)) and bool(
                OWNS_WORD_RE.search(prompt)
            )
            if not has_manifest:
                return 2, BLOCK_MESSAGE_NO_MANIFEST

    if description is not None:
        if not LABEL_MODEL_PREFIX_RE.search(description):
            return 2, BLOCK_MESSAGE_NO_LABEL

    return 0, ""


# --- ЧАСТЬ A (t-343): WARN-слой "given-пути существуют" -----------------
# См. докстринг модуля, "ЧАСТЬ A", за полное обоснование дизайна. Этот
# слой НЕ участвует в decide() и не меняет exit_code -- отдельная
# функция, вызывается ТОЛЬКО из main(), ТОЛЬКО когда decide() уже
# вернула (0, "").

# Символы, исключённые из "тела" пути-кандидата: пробел/кавычки/ёлочки/
# пайп, плейсхолдер-символы `<>*{}$` (см. докстринг, "ИЗВЛЕЧЕНИЕ") и
# запятая/точка-с-запятой/перевод строки (списковые разделители --
# собственное решение против жадного переползания через список без
# пробелов, докстринг "ИЗВЛЕЧЕНИЕ" п.(а)).
_GIVEN_PATH_BODY_CHAR = r'[^\s"\'<>|?*{}$,;\n]'

GIVEN_ABS_WIN_PATH_RE = re.compile(
    r"(?<!\w)[A-Za-z]:[\\/]" + _GIVEN_PATH_BODY_CHAR + r"*\.[A-Za-z0-9]{1,10}\b"
)

_GIVEN_REPO_REL_PREFIX = r"(?:tools|gateway|PROCESS|docs|\.claude|\.githooks)"
GIVEN_REPO_REL_PATH_RE = re.compile(
    r"(?<![\w/\\])"
    + _GIVEN_REPO_REL_PREFIX
    + r"/"
    + _GIVEN_PATH_BODY_CHAR
    + r"*\.[A-Za-z0-9]{1,10}\b"
)

GIVEN_PATH_WARN_SUMMARY_THRESHOLD = 10


def extract_given_candidates(prompt: str) -> list:
    """Возвращает [(путь_как_в_тексте, is_absolute), ...] -- дедуп,
    порядок первого появления. См. докстринг модуля, "ИЗВЛЕЧЕНИЕ"."""
    if not isinstance(prompt, str) or not prompt:
        return []
    seen_set = set()
    candidates = []
    for m in GIVEN_ABS_WIN_PATH_RE.finditer(prompt):
        tok = m.group(0)
        if tok not in seen_set:
            seen_set.add(tok)
            candidates.append((tok, True))
    for m in GIVEN_REPO_REL_PATH_RE.finditer(prompt):
        tok = m.group(0)
        if tok not in seen_set:
            seen_set.add(tok)
            candidates.append((tok, False))
    return candidates


def _is_under_root(path_str: str, root: str) -> bool:
    """True, когда path_str лежит внутри root (включая сам root) --
    сравнение через normcase(normpath(...)) (регистронезависимо на
    Windows, разделители нормализованы). См. докстринг модуля,
    "ИЗВЕСТНЫЙ КОРЕНЬ И ЧУЖИЕ ДЕРЕВЬЯ"."""
    try:
        norm_path = os.path.normcase(os.path.normpath(path_str))
        norm_root = os.path.normcase(os.path.normpath(root))
    except Exception:
        return False
    return norm_path == norm_root or norm_path.startswith(norm_root + os.sep)


def find_missing_given_paths(prompt: str, repo_root: str) -> list:
    """Возвращает НЕсуществующие пути (как в тексте) из
    extract_given_candidates(prompt) -- абсолютные пути ВНЕ repo_root
    (чужое дерево) пропускаются целиком, не считаются "несуществующими"
    (см. докстринг модуля, "ИЗВЕСТНЫЙ КОРЕНЬ И ЧУЖИЕ ДЕРЕВЬЯ")."""
    missing = []
    for tok, is_abs in extract_given_candidates(prompt):
        if is_abs:
            if not _is_under_root(tok, repo_root):
                continue
            exists = os.path.exists(tok)
        else:
            exists = os.path.exists(os.path.join(repo_root, tok))
        if not exists:
            missing.append(tok)
    return missing


def format_given_path_warn(missing: list) -> str:
    """"" на пустом списке; иначе полная форма (<=10) или сводка (>10)
    -- см. докстринг модуля, "ПОРОГ ШУМА"."""
    if not missing:
        return ""
    if len(missing) <= GIVEN_PATH_WARN_SUMMARY_THRESHOLD:
        listed = ", ".join(missing)
        return (
            "GIVEN-PATH WARN: в тексте диспатча названы несуществующие "
            f"пути: {listed} — сверь свежесть спеки с носителем (D-0096 п.5)"
        )
    head = ", ".join(missing[:3])
    return (
        f"GIVEN-PATH WARN: {len(missing)} путей не существует, первые 3: "
        f"{head} — сверь свежесть спеки с носителем (D-0096 п.5)"
    )


def given_path_warn(payload: dict) -> str:
    """"" -- ничего предупреждать не нужно (payload не Task/Agent, нет
    prompt, все кандидаты существуют/чужие/отсутствуют). Иначе --
    готовое текстовое сообщение WARN (см. format_given_path_warn)."""
    if not isinstance(payload, dict):
        return ""
    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return ""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str) or not prompt:
        return ""

    repo_root = payload.get("cwd")
    if not isinstance(repo_root, str) or not repo_root:
        repo_root = os.getcwd()

    missing = find_missing_given_paths(prompt, repo_root)
    return format_given_path_warn(missing)


def _reconfigure_stderr_utf8():
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stderr_utf8()

    # t-159: читаем БАЙТАМИ (sys.stdin.buffer), не через текстовый
    # sys.stdin.read() -- последний декодирует платформенной
    # кодировкой (cp1251 на этой машине, см. докстринг), а харнесс
    # шлёт UTF-8; явный decode(..., errors="replace") -- основной
    # путь UTF-8, replace -- fail-open защита от битых байтов.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        # Нераспознаваемый вход -- fail open, тот же принцип, что
        # остальные хуки этого кита.
        return 0

    exit_code, message = decide(payload)
    if exit_code == 2:
        sys.stderr.write(message + "\n")
        return 2

    # ЧАСТЬ A (t-343): WARN-слой -- считается ТОЛЬКО когда гейт САМ не
    # заблокировал (см. докстринг модуля, "ЧАСТЬ A"); try/except --
    # belt-and-suspenders, тот же принцип, что owns_gate.py -- WARN-слой
    # не должен уронить блокирующий хук трейсбеком.
    try:
        warn = given_path_warn(payload)
    except Exception:
        warn = ""
    if warn:
        _reconfigure_stdout_utf8()
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": warn,
            }
        }
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
