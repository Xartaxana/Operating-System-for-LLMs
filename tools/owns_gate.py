r"""owns_gate.py -- PreToolUse-хук Claude Code на Task/Agent, WARN-ONLY
(D-0063: сперва измеряем, потом решаем блокировать). Механизирует
машинную сверку непересечения owns-путей НОВОГО пишущего диспатча с
owns ЖИВЫХ диспатчей -- слой 1 защиты от коллизий параллельных
диспатчей (R4 CLAUDE.md кита: "параллельные specs декларируют path
ownership; Lead проверяет overlap перед запуском" -- ручная сверка
протухает по памяти координатора, эта проверка -- машинная страховка
поверх неё, не замена).

РЕТРАЙ (attempt 2, вердикт критика t-333): переписана экстракция owns
из промпта (B1/B2), область сверки sidecar переведена с session_key на
cwd (F2), добавлена дедупликация WARN (F4) и компакция sidecar (F1),
docstring-ограничения дополнены (F5). tools/owns_verify.py --git-diff
переписан отдельно (B3, см. его собственный докстринг).

ПОЧЕМУ НЕ logs/routing-log.jsonl (задокументировано явно, спека это
требует): `delegated`-события журнала маршрутизации пишутся ПОСЛЕ
возврата вызова диспатча и легально БАТЧАТСЯ к границе этапа (правило
4/D-0076/D-0079 CLAUDE.md кита -- "события накапливаются и пишутся
батчем на границе этапа"). Значит журнал ЗАПАЗДЫВАЕТ ровно в том окне,
где сталкиваются два одновременных запуска: если координатор
диспетчит два пишущих диспатча подряд БЕЗ промежуточной записи
журнала, второй диспатч уходит ДО того, как первый появился в
routing-log -- сверка по журналу ничего не увидит. PreToolUse -- это
единственная точка, где код гарантированно встречает КАЖДЫЙ диспатч
ДО его старта (тот же принцип "код гарантирует встречу", что правило
10г D-0063 CLAUDE.md кита) -- поэтому носитель живых owns -- ОТДЕЛЬНЫЙ
sidecar logs/owns_registry.jsonl (append-only, одна JSON-строка на
пишущий диспатч), не журнал маршрутизации.

КОНТРАКТ payload -- тот же эмпирически подтверждённый контракт, что
уже использует tools/dispatch_gate.py (payload["tool_name"] in
{"Task", "Agent"}, tool_input.prompt / tool_input.description,
payload["cwd"]) -- не переоткрыт заново, взят из образца.

ИЗВЛЕЧЕНИЕ OWNS-ПУТЕЙ ИЗ ПРОМПТА (decide -> extract_owns_paths),
ПЕРЕПИСАНО в attempt 2 по B1/B2, ОТБОР СТРОКИ УЖЕСТОЧЁН в attempt 3 по
блокеру контрольного входа критика (см. "ОТБОР СТРОКИ ПО ГРАНИЦЕ СЛОВА"
ниже):
 1. Owns-МАРКЕР -- ДВА уровня. (а) ОСНОВНОЙ отбор строки-кандидата --
    OWNS_WORD_RE = `\bowns\b`, регистронезависимо, ИМПОРТИРОВАННЫЙ из
    tools/dispatch_gate.py (батч 07-28 п.(б): бывший ЛОКАЛЬНЫЙ
    _OWNS_WORD_RE стал единой точкой правды с dispatch_gate.py -- тот
    же объект теперь используется и его блокирующей проверкой 2,
    D-0043): строка признаётся owns-декларацией, только если маркер
    стоит ОТДЕЛЬНЫМ СЛОВОМ. `_` -- словесный символ для `\b`, поэтому
    "owns_gate.py" (имя файла на Given-строке) НЕ матчится, а "owns:",
    "owns (ABSOLUTE write paths):", "**owns**:" -- матчатся.
    (б) ФОЛЛБЕК (только когда НИ ОДНА строка не дала совпадения по
    границе слова) -- прежний MANIFEST_OWNS_RE, ИМПОРТИРОВАННЫЙ из
    tools/dispatch_gate.py (не копия -- расхождение регексов между
    двумя гейтами есть отдельный класс дефекта D-0043); паттерн --
    `r"owns"`, регистронезависимо, БЕЗ границ слова.
    ПОЧЕМУ ФИЛЬТР ЛОКАЛЬНЫЙ, А НЕ ПРАВКА MANIFEST_OWNS_RE (обоснование
    D-0043, решение Lead): MANIFEST_OWNS_RE РАЗДЕЛЁН с
    tools/dispatch_gate.py, где он -- часть БЛОКИРУЮЩЕЙ проверки 2
    (write-признак И нет ОБОИХ манифест-маркеров -> exit 2). Добавление
    границ слова в общий регекс изменило бы поведение ТОГО гейта:
    промпты, где "owns" встречается только подстрокой, перестали бы
    считаться несущими манифест-маркер и начали БЛОКИРОВАТЬСЯ -- другой
    класс задачи с другой ценой ошибки, вне scope этой правки. Поэтому
    ужесточение живёт ЗДЕСЬ, в WARN-ONLY гейте, а общая точка правды
    остаётся байт-в-байт прежней.
 2. ПЕРЕБОР ВСЕХ СТРОК промпта, содержащих маркер (не только первой):
    для КАЖДОЙ такой строки от конца маркер-совпадения отрезается
    "мусор до путей" -- см. _strip_owns_marker_junk -- ИТЕРАТИВНО, в
    ЛЮБОМ порядке, снимает (а) необязательное скобочное уточнение
    `\([^)]*\)` (закрывает и `owns (ABSOLUTE write paths):`, и RU-форму
    `owns (АБСОЛЮТНЫЕ пути записи):`) и (б) ведущие символы класса
    `[\s*:\-\u2014\u00ab\u00bb"']` (закрывает markdown `**owns**:` --
    звёзды ДО двоеточия -- и обычное `owns:`), пока строка не
    стабилизируется. Остаток токенизируется (split_and_clean_tokens) и
    фильтруется is_path_token. СТРОКОЙ owns-декларации считается ПЕРВАЯ
    строка, давшая >=1 валидный path-токен -- строки с маркером БЕЗ
    путей (проза) молча пропускаются, перебор продолжается (ПРЕЖНЕЕ
    поведение "взять первую строку с маркером безусловно" было блокером
    B2 -- тихая деградация на прозе вместо диагностики).

ОТБОР СТРОКИ ПО ГРАНИЦЕ СЛОВА (attempt 3, блокер контрольного входа
критика) -- ЧТО ИМЕННО ЛОМАЛОСЬ. Перебор attempt 2 пропускал
маркер-строку БЕЗ путей, но НЕ строку, где ЛОЖНЫЙ маркер стоял РЯДОМ с
валидными путями. Сквозной вход критика:
    Дано: D:/x/tools/owns_gate.py, D:/x/tools/dispatch_gate.py,
    D:/x/CLAUDE.md
    owns (ABSOLUTE write paths): D:/x/tools/owns_gate.py
На Given-строке MANIFEST_OWNS_RE (голое `owns`) совпадал ВНУТРИ имени
файла "owns_gate.py"; остаток строки резался по запятой, 2-й и 3-й
токены -- валидные абсолютные пути -> extract_owns_paths возвращала ИХ
и останавливалась, настоящая owns-строка НИЖЕ не читалась. В sidecar
попадал ЛОЖНЫЙ owns из READ-ONLY файлов корзины "дано", а объявленный
путь записи терялся -- сверка пересечений становилась не просто слепой,
а ВРУЩЕЙ (WARN на чужой read-only путь, тишина на реальной коллизии).
ФИКС: первый проход отбирает строки строго по `\bowns\b`; ФОЛЛБЕК на
подстрочный перебор (прежнее поведение целиком) включается ТОЛЬКО если
по границе слова не совпала НИ ОДНА строка промпта -- сохранённая
толерантность к кривым формам, где "owns" вкраплён в слово и является
ЕДИНСТВЕННЫМ маркером промпта. Если строка по границе слова НАШЛАСЬ, но
путей не дала -- фоллбек НЕ включается: это диагностируемая пустота
(см. "ДИАГНОСТИКА ПУСТОГО OWNS"), а не повод вернуться к ложным
срабатываниям.

ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ ЭКСТРАКЦИИ (attempt 3, N2/N3 вердикта критика --
задокументированы явно, поведение НЕ меняется; оба запинены тестами):
 - ВЕДУЩАЯ ЗВЁЗДОЧКА ГЛОБА СЪЕДАЕТСЯ СТРИППЕРОМ: `*` входит в класс
   мусорных ведущих символов _JUNK_PREFIX_RE (он там ради markdown
   `**owns**:`), поэтому extract_owns_paths("owns: */tools/*") даёт
   ["/tools/*"], а не ["*/tools/*"] -- ведущая звезда потеряна.
   Известное ограничение, НЕ чинится: глоб с ведущей звездой не
   является абсолютным путём и потому лежит ВНЕ нормы правила 11
   CLAUDE.md кита ("owns (ABSOLUTE write paths)"); цена -- огрубление
   сверки на нештатной форме, WARN-ONLY. Пин --
   test_extract_owns_paths_leading_star_glob_is_stripped_known_limitation.
 - КВАДРАТИЧНОСТЬ _strip_owns_marker_junk ПО ЧИСЛУ МУСОРНЫХ СКОБОЧНЫХ
   ГРУПП: каждая итерация цикла срезает ОДНУ группу `([^)]*)` и делает
   СРЕЗ-КОПИЮ остатка строки, то есть стоимость ~O(n^2) по числу групп
   (замер критика: 240К групп ~ 3с). На РЕАЛИСТИЧНОМ потолке промпта
   это несущественно: мусорный префикс ~50КБ скобочных групп
   разбирается за доли секунды -- граничный тест величины
   test_strip_owns_marker_junk_50kb_paren_groups_completes_under_5s.
   Патологический вход (сотни тысяч групп) деградирует по времени, но
   НЕ роняет хук (exit 0 гарантирован main()); не оптимизируется
   превентивно -- цена простоты, WARN-ONLY инструмент.
 3. ИЗ ОСТАТКА СТРОКИ токены нарезаются `;`, `,`, переводом строки
    (_TOKEN_SEPARATOR_RE). У КАЖДОГО токена, ДО обрезки краёв,
    отрезается прозаический хвост, начинающийся с ПЕРВОЙ
    последовательности "пробел-эмтире-пробел" (_PROSE_TAIL_SEP =
    " \u2014 ") -- закрывает форму "D:/a.py \u2014 новый файл": хвост
    "\u2014 новый файл" отбрасывается, путь остаётся. НАРОЧНО не режем
    по голому пробелу -- легальные пути С пробелами (прецедент
    "D:/AI CRM/govard-crm/AGENTS.md") должны выжить целиком; только
    ИМЕННО тройка "пробел-эмтире-пробел" триггерит отрез.
 4. ПОСЛЕ отреза хвоста токен обрезается по краям: пробелы, затем
    ВЕДУЩИЕ кавычки/скобки/ёлочки (_EDGE_TRIM_CHARS -- расширен в
    attempt 2 гильеметами `\u00ab \u00bb` и типографскими кавычками
    `\u201e \u201c \u201d` поверх прежних `"'()[]{}`, закрывает форму
    "\u00abD:/a.py\u00bb"), затем ХВОСТОВЫЕ кавычки/скобки/точку конца
    предложения (_TRAILING_TRIM_CHARS) -- итеративно, см. _clean_token.
 5. ТОЛЬКО токены, похожие на ПУТЬ, оставляются: Windows-абсолютный
    (буква-диск, `:` и слэш), POSIX-абсолютный (начинается с `/`,
    покрывает git-bash `/d/...`), ЛИБО глоб (содержит `*`) --
    is_path_token(). ОТНОСИТЕЛЬНЫЕ пути НЕ распознаются как путь -- НЕ
    пробел спеки: R11 CLAUDE.md кита прямо требует "owns (ABSOLUTE
    write paths)".
 Owns-маркер не найден ни на одной строке -- read-only-диспатч,
 extract_owns_paths возвращает [] -- decide() ничего не пишет в
 sidecar и тихо выходит (0, None).

ДИАГНОСТИКА ПУСТОГО OWNS (B2, "тишина -> шум"): если extract_owns_paths
вернула [] (ни одна строка не дала путей), НО в промпте ЕСТЬ
owns-маркер (MANIFEST_OWNS_RE) И write-индикатор (WRITE_INDICATORS_RE,
ИМПОРТИРОВАННЫЙ из tools/dispatch_gate.py -- та же общая точка правды,
что и MANIFEST_OWNS_RE) -- decide() возвращает additionalContext-WARN
("owns объявлен, путей не разобрано -- сверка пересечений слепа на
этом диспатче; проверь форму owns-строки", см. BLIND_OWNS_WARN_MESSAGE)
и НЕ пишет в sidecar (сверка заведомо слепа -- писать в реестр
пустой/бессмысленный owns-набор не имеет смысла). Настоящий read-only
(маркера нет вовсе, ИЛИ маркер есть только как ложная подстрока без
границы слова -- см. WRITE_INDICATORS_RE в tools/dispatch_gate.py,
`\bowns\b` -- и потому write-индикатор не сработал) -- тишина, как и
раньше: ни WARN, ни запись.

SESSION_KEY (спека допускает выбор источника, требует задокументировать):
session_key = payload.get("session_id"), если это непустая строка,
ИНАЧЕ payload.get("cwd"). В attempt 2 (F2) session_key -- ТОЛЬКО
МЕТКА для сообщения ("параллельный диспатч этой же сессии" / "другая
сессия, класс D-0060"), НЕ область сверки -- см. следующий раздел.
Фоллбек session_id->cwd, когда session_id отсутствует, тем самым
маркировочный, а не скоуп-фоллбек: если у сессии нет session_id, её
метка совпадёт с cwd-скоупом и она будет ошибочно помечена "своей" для
любой другой такой же безымянной сессии в том же репо -- известное,
задокументированное огрубление меток (не скоупа).

ОБЛАСТЬ СВЕРКИ (F2, решение Lead): sidecar-записи фильтруются по
ОДИНАКОВОМУ cwd (репо-скоуп: репозиторий, из которого работает
координатор) -- НЕ по session_key. Одна и та же сессия, запустившая
два пишущих диспатча подряд (внутри-сессионная гонка), и ДВЕ РАЗНЫЕ
сессии в одном репо (межсессионная гонка, D-0060) -- ОБЕ категории
коллизий сверяются одинаково (обе живут в одном cwd), различается
только ТЕКСТ сообщения по session_key: пересечение с записью ТОГО ЖЕ
session_key -> "параллельный диспатч этой же сессии"; пересечение с
записью ДРУГОГО session_key -> "другая сессия (класс D-0060)".
Область cwd СРАВНИВАЕТСЯ буквальным равенством строк (без нормализации
регистра/слэшей) -- та же простая форма, что раньше использовалась для
session_key; известное огрубление (разные буквальные формы одного и
того же cwd не совпадут), не устранено превентивно -- вне scope этой
задачи.

ОКНО ЖИВОСТИ 24 ЧАСА -- запись sidecar считается "живой" (кандидатом
на пересечение), если delta = now - ts_записи УДОВЛЕТВОРЯЕТ
0 <= delta <= 86400 секунд -- ГРАНИЦА ВКЛЮЧИТЕЛЬНА (ровно 24:00:00 --
ещё живая; 24:00:01 -- уже нет). Запись из БУДУЩЕГО (delta < 0,
рассинхрон часов) КОНСЕРВАТИВНО исключается -- fail-safe в сторону
"не считать живым". Собственное инженерное решение (спека называет
только сам факт окна 24ч, не строгость границы), задокументировано.

СЕМАНТИКА ПЕРЕСЕЧЕНИЯ ПУТЕЙ (normalize_path/paths_overlap, ПРИБЛИЖЕНИЕ,
задокументировано явно, как спека требует): нормализация -- .lower(),
`\` -> `/`, срез хвостовых `/`. Совпадение = (а) точное равенство
нормализованных строк, ЛИБО (б) один путь -- каталожный ПРЕФИКС
другого ПО ГРАНИЦЕ СЕГМЕНТА (`a == b` или `b.startswith(a + "/")` --
не голый substring, поэтому `D:\ab` и `D:\abc` НЕ пересекаются), ЛИБО
(в) fnmatch В ЛЮБУЮ СТОРОНУ, когда ХОТЯ БЫ ОДИН из путей несёт `*` --
используется fnmatch.fnmatchcase (не fnmatch.fnmatch) НАРОЧНО --
одинаковое поведение на любой ОС, не зависящее от os.name на машине,
где гоняются тесты.

ДЕДУПЛИКАЦИЯ WARN (F4): один НОВЫЙ путь может пересечься с НЕСКОЛЬКИМИ
живыми записями сразу -- ПРЕЖНЕЕ поведение печатало по ОДНОЙ строке на
КАЖДУЮ такую пару (путь, запись), раздувая сообщение. Attempt 2
группирует пересечения ПО НОВОМУ ПУТИ (_find_overlaps возвращает
[(path, [(ts, desc, same_session), ...]), ...]) -- на путь ПРИХОДИТСЯ
ОДНА строка WARN, внутри неё показываются максимум ДВА упоминания
столкнувшихся записей через `;`, а если записей больше -- добавляется
хвост "и ещё N" (_format_path_line). Общее число ПУТЕЙ, попадающих в
итоговое сообщение, по-прежнему ограничено тремя (unchanged с attempt
1 -- собственное решение против неограниченно длинного
additionalContext).

КОМПАКЦИЯ SIDECAR (F1): sidecar -- append-only и НЕОГРАНИЧЕННО растёт
в долгоживущем репо. Attempt 2 добавляет компакцию ПРИ ЗАПИСИ: если
ЧИСЛО СТРОК, уже лежащих в файле ПЕРЕД записью новой, СТРОГО БОЛЬШЕ
REGISTRY_COMPACT_THRESHOLD_LINES (= 500) -- файл ПЕРЕЗАПИСЫВАЕТСЯ
целиком: только строки, чей ts попадает в окно живости 24ч (та же
граница, что _load_live_records, но БЕЗ фильтра по cwd/session --
компакция обслуживает файл ГЛОБАЛЬНО, не один конкретный диспатч),
плюс новая запись. Если строк <= 500 -- обычный append, без
перезаписи. ГРАНИЦА (правило 6а): РОВНО 500 существующих строк ->
обычный append (500 не строго больше 500); РОВНО 501 существующая
строка -> компакция (501 строго больше 500) -- см. именной граничный
тест test_registry_compaction_boundary_500_vs_501_lines.

SIDECAR -- logs/owns_registry.jsonl, ОТНОСИТЕЛЬНО payload["cwd"] (тот
же принцип, что tools/dod_track.py уже использует для своего трека).
Append-only (кроме компакции выше), одна JSON-строка на ПИШУЩИЙ
диспатч (read-only диспатчи И диспатчи с нераспознанным owns -- см.
"ДИАГНОСТИКА ПУСТОГО OWNS" -- НЕ порождают запись):
  {"ts": "YYYY-MM-DDTHH:MM:SS" (локальное время, без таймзоны),
   "session_key": str,
   "cwd": str или None (ДОБАВЛЕНО в attempt 2, F2 -- поле, по которому
          теперь фильтруются живые записи),
   "description": str (tool_input.description ИЛИ ""),
   "owns": [str, ...]}
Отсутствующий файл / битая JSON-строка внутри него -- fail-open
(строка молча пропускается, остальные читаются как обычно; отсутствие
файла -- пустой список живых записей).

ПОРЯДОК: новый диспатч СНАЧАЛА сверяется с уже существующими живыми
записями, ПОТОМ (после сверки, вне зависимости от её исхода) сам
дописывается в sidecar -- самопересечение диспатча с самим собой этим
порядком структурно исключено (спека требует явно).

ОБЩИЙ КОД С tools/owns_verify.py (спека требует ОДНУ реализацию
сверки на двоих, выбор направления задокументирован): normalize_path/
paths_overlap/split_and_clean_tokens определены ЗДЕСЬ (owns_gate.py) и
ИМПОРТИРУЮТСЯ в owns_verify.py -- owns_gate.py -- активный
PreToolUse-хук (регистрируется в settings.json, должен уметь работать
САМОСТОЯТЕЛЬНО без CLI-обвязки), тогда как owns_verify.py -- чистый
CLI, для которого лишняя зависимость от собственного модуля не создаёт
проблемы обратного направления.

ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ SIDECAR (F5, дополнено в attempt 2 -- список,
не устранённый превентивно, задокументирован явно):
 - ТОЧНОСТЬ WARN-FIRST: sidecar НЕ ЗНАЕТ о ЗАВЕРШЕНИИ воркера --
   запись живёт в окне 24ч независимо от того, отработал диспатч уже
   или нет; возможен WARN на уже полностью завершённый диспатч (цена
   warn-first, D-0063). Суждение о реальной живости -- за
   координатором.
 - КОНКУРЕНТНЫЙ APPEND ДВУХ СЕССИЙ: два процесса могут писать в
   sidecar одновременно; на большинстве ОС `open(..., "a")` атомарен
   для короткой строки, но НЕ гарантированно -- в пределе возможна
   рваная (перемежённая) строка. Читающая сторона (_load_live_records)
   fail-open пропускает такую строку как битый JSON -- приемлемо для
   WARN-ONLY инструмента (пропущенный WARN дешевле упавшего хука).
 - КОМПАКЦИЯ КАК ТОЧКА ПОТЕРИ: компакция (см. выше) ПЕРЕЗАПИСЫВАЕТ
   файл целиком -- если ВТОРОЙ процесс допишет строку МЕЖДУ чтением
   существующих строк этим процессом и его финальной перезаписью, эта
   строка будет потеряна (перезапись не увидела её). Редкий случай
   (требует совпадения компакции с конкурентной записью в узком окне),
   WARN-ONLY -- принято как цена простоты, не устранено превентивно.

FAIL-OPEN: payload не dict / tool_name не Task|Agent / tool_input не
dict / prompt не строка / owns-блок не найден -- везде (0, None),
никаких побочных эффектов. main() оборачивает decide() ещё одним
try/except (belt-and-suspenders, тот же принцип, что negative_lint.py)
-- адверсариальный вход (битый JSON, не-UTF8 байты, payload не dict,
огромная строка owns) не должен уронить хук трейсбеком; exit code
ВСЕГДА 0 (WARN-режим, спека прямо требует "никогда не блокировать")."""

import fnmatch
import json
import re
import sys
from datetime import datetime
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

try:
    from tools.dispatch_gate import (  # package-style
        MANIFEST_OWNS_RE,
        OWNS_WORD_RE,
        WRITE_INDICATORS_RE,
    )
except ImportError:
    from dispatch_gate import (  # sibling-module fallback
        MANIFEST_OWNS_RE,
        OWNS_WORD_RE,
        WRITE_INDICATORS_RE,
    )


# --- извлечение owns-путей из промпта -------------------------------

# БАТЧ 07-28 п.(б): отбор строки-кандидата owns-декларации (маркер
# обязан стоять ОТДЕЛЬНЫМ СЛОВОМ) больше НЕ живёт локальной копией --
# ИМПОРТИРОВАН из tools/dispatch_gate.py как OWNS_WORD_RE (единая точка
# правды, D-0043; dispatch_gate.py теперь тоже использует ЕГО в своей
# проверке 2, закрывая дыру t-332 подстрочного MANIFEST_OWNS_RE). Общий
# MANIFEST_OWNS_RE НАРОЧНО не трогаем -- фоллбек ниже, см. докстринг
# модуля, п.1(б) (обоснование D-0043).

_PAREN_PREFIX_RE = re.compile(r"^\s*\([^)]*\)")
_JUNK_PREFIX_RE = re.compile(r"^[\s*:\-\u2014\u00ab\u00bb\"']+")
_TOKEN_SEPARATOR_RE = re.compile(r"[;,\n]")
_PROSE_TAIL_SEP = " \u2014 "  # пробел-эмтире-пробел -- см. докстринг модуля, п.3

_EDGE_TRIM_CHARS = "\"'()[]{}\u00ab\u00bb\u201e\u201c\u201d"
# Хвостовая пунктуация конца предложения (`.`) -- реальные манифесты
# этого кита пишут owns-буллет как законченное предложение, поэтому
# ТОЛЬКО с хвоста (rstrip, не lstrip -- ведущая точка защищена, чтобы
# не покалечить гипотетический относительный dot-путь) добавляется `.`
# к набору обрезаемых символов, ПОВЕРХ кавычек/скобок/ёлочек --
# собственное инженерное решение, задокументировано, не угадано молча.
_TRAILING_TRIM_CHARS = _EDGE_TRIM_CHARS + "."

_WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")
_POSIX_ABS_RE = re.compile(r"^/")


def _strip_owns_marker_junk(remainder: str) -> str:
    """Итеративно снимает с НАЧАЛА remainder необязательное скобочное
    уточнение `\\([^)]*\\)` и ведущие символы класса
    `[\\s*:\\-\\u2014\\u00ab\\u00bb"']` -- В ЛЮБОМ ПОРЯДКЕ (скобка может
    идти до ИЛИ после двоеточия, markdown `**owns**:` даёт звёзды до
    двоеточия) -- пока строка не стабилизируется. Оба паттерна всегда
    поглощают >=1 символ при совпадении, поэтому remainder строго
    укорачивается на каждой успешной итерации -- завершение
    гарантировано без отдельного счётчика итераций (см. докстринг
    модуля, п.2)."""
    prev = None
    while remainder != prev:
        prev = remainder
        m = _PAREN_PREFIX_RE.match(remainder)
        if m:
            remainder = remainder[m.end():]
            continue
        m2 = _JUNK_PREFIX_RE.match(remainder)
        if m2:
            remainder = remainder[m2.end():]
            continue
    return remainder


def _cut_prose_tail(raw: str) -> str:
    """Отрезает у токена хвост от ПЕРВОЙ последовательности
    "пробел-эмтире-пробел" (_PROSE_TAIL_SEP) -- см. докстринг модуля,
    п.3. НЕ режет по голому пробелу -- пути с пробелами (напр.
    "D:/AI CRM/x/AGENTS.md") остаются целыми."""
    if not raw:
        return raw
    idx = raw.find(_PROSE_TAIL_SEP)
    if idx == -1:
        return raw
    return raw[:idx]


def _clean_token(raw: str) -> str:
    """Обрезает пробелы, затем ВЕДУЩИЕ кавычки/скобки/ёлочки
    (_EDGE_TRIM_CHARS) и ХВОСТОВЫЕ кавычки/скобки/ёлочки/точку
    (_TRAILING_TRIM_CHARS) -- ИТЕРАТИВНО (до стабилизации), чтобы
    вложенные комбинации вроде "(logs/owns_registry.jsonl)." (скобка
    ЗАТЕМ точка конца предложения) схлопывались до чистого пути в один
    проход цикла, не за один единственный strip()."""
    tok = raw.strip()
    prev = None
    while tok != prev:
        prev = tok
        tok = tok.lstrip(_EDGE_TRIM_CHARS)
        tok = tok.rstrip(_TRAILING_TRIM_CHARS)
        tok = tok.strip()
    return tok


def split_and_clean_tokens(text: str) -> list:
    """Разбивает text по `;`/`,`/переводу строки, отрезает у каждого
    "сырого" токена прозаический хвост (_cut_prose_tail) и обрезает
    пробелы/кавычки/скобки/ёлочки (+ хвостовую точку, см.
    _clean_token) по краям. Общая функция -- см. докстринг модуля,
    "ОБЩИЙ КОД С tools/owns_verify.py"."""
    if not isinstance(text, str) or not text:
        return []
    cleaned = []
    for raw in _TOKEN_SEPARATOR_RE.split(text):
        raw = _cut_prose_tail(raw)
        tok = _clean_token(raw)
        if tok:
            cleaned.append(tok)
    return cleaned


def is_path_token(tok: str) -> bool:
    """Windows-абсолютный / POSIX-абсолютный / глоб с `*` -- см.
    докстринг модуля, п.5 "ИЗВЛЕЧЕНИЕ OWNS-ПУТЕЙ"."""
    if not isinstance(tok, str) or not tok:
        return False
    return bool(_WINDOWS_ABS_RE.match(tok) or _POSIX_ABS_RE.match(tok) or "*" in tok)


BLIND_OWNS_WARN_MESSAGE = (
    "owns объявлен, путей не разобрано \u2014 сверка пересечений слепа "
    "на этом диспатче; проверь форму owns-строки"
)


def _paths_from_line(line: str, marker_end: int) -> list:
    """Общий хвост обоих проходов отбора: от конца совпадения маркера
    срезается мусор (_strip_owns_marker_junk), остаток токенизируется и
    фильтруется is_path_token -- см. докстринг модуля, пп.2-5."""
    remainder = _strip_owns_marker_junk(line[marker_end:])
    tokens = split_and_clean_tokens(remainder)
    return [t for t in tokens if is_path_token(t)]


def extract_owns_paths(prompt: str) -> list:
    """[] -- owns-блок не найден НИ на одной строке (read-only диспатч
    манифеста не требует, правило 11 CLAUDE.md кита) -- иначе список
    path-подобных токенов из ПЕРВОЙ строки, давшей >=1 такой токен.

    ДВА ПРОХОДА (attempt 3, блокер контрольного входа критика -- см.
    докстринг модуля, "ОТБОР СТРОКИ ПО ГРАНИЦЕ СЛОВА"):
     1. ОСНОВНОЙ -- только строки, где маркер стоит ОТДЕЛЬНЫМ СЛОВОМ
        (OWNS_WORD_RE = `\\bowns\\b`, импортирован из dispatch_gate.py,
        батч 07-28 п.(б)): "owns_gate.py" в корзине "дано" БОЛЬШЕ НЕ
        перехватывает разбор у настоящей owns-строки ниже.
     2. ФОЛЛБЕК -- прежний подстрочный перебор по MANIFEST_OWNS_RE,
        ВКЛЮЧАЕТСЯ ТОЛЬКО если по границе слова не совпала НИ ОДНА
        строка (сохранённая толерантность к кривым формам). Строка по
        границе слова нашлась, но путей не дала -> фоллбека НЕТ, []
        уходит в диагностику пустого owns (decide)."""
    if not isinstance(prompt, str) or not prompt:
        return []

    lines = prompt.splitlines()

    word_boundary_seen = False
    for line in lines:
        m = OWNS_WORD_RE.search(line)
        if not m:
            continue
        word_boundary_seen = True
        paths = _paths_from_line(line, m.end())
        if paths:
            return paths

    if word_boundary_seen:
        return []

    for line in lines:
        m = MANIFEST_OWNS_RE.search(line)
        if not m:
            continue
        paths = _paths_from_line(line, m.end())
        if paths:
            return paths
    return []


# --- нормализация и сверка путей (общий код с owns_verify.py) --------


def normalize_path(p: str) -> str:
    """.lower(), `\\` -> `/`, срез хвостовых `/` -- см. докстринг
    модуля, "СЕМАНТИКА ПЕРЕСЕЧЕНИЯ ПУТЕЙ"."""
    if not isinstance(p, str):
        return ""
    p = p.strip().lower().replace("\\", "/")
    while len(p) > 1 and p.endswith("/"):
        p = p[:-1]
    return p


def paths_overlap(a: str, b: str) -> bool:
    """Равенство / вложенность по границе сегмента / fnmatch в любую
    сторону при наличии глоба -- см. докстринг модуля,
    "СЕМАНТИКА ПЕРЕСЕЧЕНИЯ ПУТЕЙ" за обоснование fnmatchcase."""
    na, nb = normalize_path(a), normalize_path(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    if na.startswith(nb + "/") or nb.startswith(na + "/"):
        return True
    if "*" in na or "*" in nb:
        if fnmatch.fnmatchcase(nb, na) or fnmatch.fnmatchcase(na, nb):
            return True
    return False


# --- sidecar: чтение живых записей + запись новой --------------------

WINDOW_SECONDS = 24 * 60 * 60
_TS_FORMAT = "%Y-%m-%dT%H:%M:%S"
_DESC_TRUNC_LEN = 200
REGISTRY_COMPACT_THRESHOLD_LINES = 500


def _now_iso(now: datetime) -> str:
    return now.strftime(_TS_FORMAT)


def _registry_path_from_cwd(cwd) -> Path:
    return Path(cwd or ".") / "logs" / "owns_registry.jsonl"


def _load_live_records(registry_path: Path, cwd, now: datetime) -> list:
    """Fail-open: файл отсутствует / строка битая / поля неверного
    типа -- запись/строка молча пропускается, остальные читаются как
    обычно (см. докстринг модуля). Область (F2) -- ОДИНАКОВЫЙ cwd
    (буквальное равенство строк), НЕ session_key -- session_key внутри
    записи остаётся только для МЕТКИ в сообщении, см. _find_overlaps."""
    if registry_path is None or not registry_path.exists():
        return []
    try:
        raw = registry_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    records = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("cwd") != cwd:
            continue
        ts_str = rec.get("ts")
        if not isinstance(ts_str, str):
            continue
        try:
            rec_ts = datetime.strptime(ts_str, _TS_FORMAT)
        except Exception:
            continue
        delta = (now - rec_ts).total_seconds()
        if delta < 0 or delta > WINDOW_SECONDS:
            continue
        owns = rec.get("owns")
        if not isinstance(owns, list):
            continue
        records.append(rec)
    return records


def _compact_live_lines(existing_lines: list, now: datetime) -> list:
    """Компакция (F1): оставляет только СЫРЫЕ строки (str), чей ts
    попадает в окно живости 24ч -- ГЛОБАЛЬНО, БЕЗ фильтра по
    cwd/session (компакция обслуживает файл целиком, не один
    конкретный диспатч). Битая JSON-строка -- fail-open, молча
    отбрасывается при компакции (см. докстринг модуля, "ИЗВЕСТНЫЕ
    ОГРАНИЧЕНИЯ SIDECAR" -- компакция как точка возможной потери
    конкурентной записи)."""
    live = []
    for line in existing_lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        ts_str = rec.get("ts")
        if not isinstance(ts_str, str):
            continue
        try:
            rec_ts = datetime.strptime(ts_str, _TS_FORMAT)
        except Exception:
            continue
        delta = (now - rec_ts).total_seconds()
        if delta < 0 or delta > WINDOW_SECONDS:
            continue
        live.append(line)
    return live


def _append_registry(
    registry_path: Path, now: datetime, session_key, cwd, description: str, owns_paths: list
) -> None:
    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": _now_iso(now),
            "session_key": session_key,
            "cwd": cwd,
            "description": description or "",
            "owns": owns_paths,
        }
        entry_line = json.dumps(entry, ensure_ascii=False)

        existing_lines = []
        if registry_path.exists():
            try:
                raw = registry_path.read_text(encoding="utf-8", errors="replace")
                existing_lines = [ln for ln in raw.splitlines() if ln.strip()]
            except Exception:
                existing_lines = []

        # F1: компакция ТОЛЬКО когда строк СТРОГО БОЛЬШЕ порога (500 ->
        # обычный append; 501 -> компакция), см. докстринг модуля.
        if len(existing_lines) > REGISTRY_COMPACT_THRESHOLD_LINES:
            live_lines = _compact_live_lines(existing_lines, now)
            live_lines.append(entry_line)
            registry_path.write_text("\n".join(live_lines) + "\n", encoding="utf-8")
        else:
            with registry_path.open("a", encoding="utf-8") as f:
                f.write(entry_line + "\n")
    except Exception:
        # fail-open: невозможность дописать sidecar (например, диск
        # только для чтения) не должна ронять хук.
        pass


def _truncate(s: str, max_len: int = _DESC_TRUNC_LEN) -> str:
    s = (s or "").strip()
    if len(s) > max_len:
        return s[:max_len] + "\u2026"
    return s


def _find_overlaps(new_paths: list, records: list, session_key) -> list:
    """F4-дедуп: группирует пересечения ПО НОВОМУ ПУТИ, а не по паре
    (путь, запись) -- один новый путь, пересёкшийся с несколькими
    живыми записями, даёт ОДНУ запись в результате. Возвращает
    [(path, [(ts, description, same_session_bool), ...]), ...] --
    список путей в порядке new_paths, список совпавших записей внутри
    -- в порядке records. same_session_bool -- сравнение record's
    session_key с session_key ТЕКУЩЕГО диспатча (F2 -- метка, не
    фильтр области)."""
    grouped = []
    for p in new_paths:
        matches = []
        for rec in records:
            rec_owns = rec.get("owns") or []
            if any(paths_overlap(p, existing) for existing in rec_owns):
                same_session = rec.get("session_key") == session_key
                matches.append((rec.get("ts"), rec.get("description") or "", same_session))
        if matches:
            grouped.append((p, matches))
    return grouped


def _format_mention(ts, desc, same_session: bool) -> str:
    tag = (
        "параллельный диспатч этой же сессии"
        if same_session
        else "другая сессия (класс D-0060)"
    )
    return f"{ts} \u00ab{_truncate(desc)}\u00bb ({tag})"


def _format_path_line(p: str, matches: list) -> str:
    shown = matches[:2]
    mentions = "; ".join(_format_mention(ts, desc, same) for ts, desc, same in shown)
    extra = len(matches) - len(shown)
    if extra > 0:
        mentions += f"; и ещё {extra}"
    return f"путь {p} пересекается с {mentions}"


def _format_overlap_context(grouped: list) -> str:
    head = grouped[:3]
    parts = [_format_path_line(p, matches) for p, matches in head]
    return (
        "OWNS OVERLAP (warn): " + "; ".join(parts) + "; параллельная запись в "
        "общие пути \u2014 сериализуй или разведи owns"
    )


# --- decide() ----------------------------------------------------------


def decide(payload: dict, registry_path: Path = None, now: datetime = None) -> tuple:
    """Чистая-ПОЧТИ логика (с sidecar I/O внутри -- сверка живых owns
    неизбежно требует чтения перед решением и записи после, см.
    докстринг модуля "ПОРЯДОК") -- тестируемая напрямую передачей
    своего registry_path/now. exit_code ВСЕГДА 0 (WARN-режим).
    Возвращает (0, None) на тихий пропуск, (0, dict) -- dict уже готов
    к json.dumps на stdout при найденном пересечении owns ИЛИ при
    диагностике пустого owns (см. "ДИАГНОСТИКА ПУСТОГО OWNS")."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Task", "Agent"):
        return 0, None

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0, None

    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""

    owns_paths = extract_owns_paths(prompt)
    if not owns_paths:
        # B2: owns-маркер объявлен, но ни одна строка не дала
        # path-подобных токенов -- сверка слепа, WARN о слепоте вместо
        # тихого пропуска, sidecar НЕ растёт. Настоящий read-only
        # (маркера нет / нет write-индикатора) -- тишина.
        if MANIFEST_OWNS_RE.search(prompt) and WRITE_INDICATORS_RE.search(prompt):
            return 0, {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": BLIND_OWNS_WARN_MESSAGE,
                }
            }
        return 0, None

    if now is None:
        now = datetime.now()
    cwd = payload.get("cwd")
    if registry_path is None:
        registry_path = _registry_path_from_cwd(cwd)

    session_id = payload.get("session_id")
    session_key = session_id if isinstance(session_id, str) and session_id else cwd

    description = tool_input.get("description")
    if not isinstance(description, str):
        description = ""

    records = _load_live_records(registry_path, cwd, now)
    grouped = _find_overlaps(owns_paths, records, session_key)

    output = None
    if grouped:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": _format_overlap_context(grouped),
            }
        }

    # Порядок: сверка ВЫШЕ, запись -- ПОСЛЕ (самопересечение исключено
    # структурно, см. докстринг модуля "ПОРЯДОК").
    _append_registry(registry_path, now, session_key, cwd, description, owns_paths)

    return 0, output


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stdout_utf8()

    # Тот же байт-безопасный паттерн, что tools/dispatch_gate.py/
    # tools/hygiene_gate.py этого кита: sys.stdin.buffer.read() обходит
    # платформенную кодировку текстового sys.stdin, явный decode utf-8
    # с errors="replace" -- fail-open на битые байты.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    try:
        exit_code, output = decide(payload)
    except Exception:
        # belt-and-suspenders (тот же принцип, что negative_lint.py):
        # decide() уже защитно типизирован, но адверсариальный вход
        # (напр. неожиданная форма где-то глубже) не должен уронить
        # хук трейсбеком наружу.
        return 0

    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
