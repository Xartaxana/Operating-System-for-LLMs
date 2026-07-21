"""hygiene_gate.py (t-<текущая>) -- PreToolUse-хук командной гигиены в
WARN-РЕЖИМЕ (НЕ блокирующий) для тулов Bash|PowerShell. Механизирует
пп.3-5 секции «Командная гигиена» CLAUDE.md кита: cd-префикс, ` 2>&1`,
`python -c`/`python - <<` мимо Edit/Write, запись в журнал
routing-log мимо Edit/Write -- ловит их ДО выполнения команды и
показывает модели предупреждение с канонической альтернативой, но
НИКОГДА не блокирует вызов (в отличие от tools/dispatch_gate.py --
тот блокирует exit 2 + stderr; здесь всегда exit 0, побочный эффект
только на stdout при совпадении).

ЭМПИРИКА КАНАЛА ДОСТАВКИ (спека прямо просила сверить, не гадать):
корзина этой задачи утверждает, что tools/dispatch_gate.py и
tools/dod_track.py -- образцы «выхода через hookSpecificOutput». Это
НЕ подтвердилось: оба файла прочитаны целиком -- dispatch_gate.py
доставляет решение ИСКЛЮЧИТЕЛЬНО через exit-code (0/2) + текст в
stderr, dod_track.py вообще ничего не пишет в stdout/stderr (чистый
side-effect PostToolUse-хук, всегда exit 0 без вывода). Ни строки
"hookSpecificOutput" тем более "additionalContext" нет НИГДЕ в
репозитории -- контроль: `grep -i hookSpecific` по всему репо дал 0
совпадений; позитивный контроль тем же Grep-тулом на "dod_track" в
той же попытке дал 22 файла -- труба работает, отсутствие настоящее,
не промах вызова (F-30/F-34). Из образцов пришлось взять только их
байт-безопасный паттерн чтения stdin (sys.stdin.buffer.read() +
decode(errors="replace")) и fail-open на битый JSON -- ровно то, что
докстринг корзины и просил явно.

Раз образцы КИТА не дают канала для самого предупреждения, спека
прямо разрешает следующий шаг: «следуй образцам [метода] и
зафиксируй решение в отчёте». Решение: сверил РЕАЛЬНЫЙ контракт
харнесса тем же форензик-методом, что уже использован в этом ките
(докстринг tools/dod_track.py -- `grep -a` по установленному
`claude.exe`, позитив/негатив-контроль). Позитивный контроль:
`permissionDecision` (18 совпадений), `additionalContext` (43),
`hookSpecificOutput` (36) -- все найдены; негативный контроль
(заведомо не существующая строка) -- 0. Извлечённый контекст (Zod,
дословно из бинарника):

  A.object({hookEventName:A.literal("PreToolUse"),
            permissionDecision:Wqh().optional(),
            permissionDecisionReason:A.string().optional(),
            updatedInput:A.record(...).optional(),
            additionalContext:A.string().optional()})

и рантайм-ветка разбора ответа хука: `e.hookSpecificOutput?.
hookEventName==="PreToolUse"&&e.hookSpecificOutput.permissionDecision)
switch(e.hookSpecificOutput.permissionDecision){case"allow": ...`;
доквыдержка помощи: `permissionDecision:'"allow" | "deny" | "ask" |
"defer" (optional)'`. Это ДОСЛОВНО те три поля, что просила спека
(`hookSpecificOutput.permissionDecision="allow"` + `additionalContext`)
-- подтверждено эмпирикой бинарника, не домыслом по памяти. Формат
ответа хука здесь:

  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                           "additionalContext": "<список классов>"}}

(permissionDecision опущен НАМЕРЕННО -- блокер B1 критика t-177:
"allow" авто-аппрувил бы флагнутую команду, подавляя штатный
permission-prompt; спека предписывала "allow" -- дефект спеки Lead,
исправлен при приёмке.)

записан ОДНОЙ JSON-строкой в stdout при exit 0. Живого перехвата
реального PreToolUse-вызова под активным хуком НЕ делалось (та же
оговорка метода, что в dod_track.py: живой смок -- через
Task/Agent-диспатч или правку settings.json сессии, оба вне роли
builder на этой задаче/non-goals манифеста) -- финальная сверка на
реальном харнессе за Lead (см. отчёт).

ДЕТЕКТ-КЛАССЫ (все проверки НЕЗАВИСИМЫ, в additionalContext идёт
СПИСОК всех сработавших -- не первый найденный, как в dispatch_gate.py;
здесь нет конфликта "одно сообщение блокирует", WARN не эксклюзивен):

 (а) cd-префикс: команда начинается с `cd <непустой аргумент>`
     (реальный путь, не голое "cd" и не "cd&&...") И где-то дальше
     есть `&&` или `;`.
 (б) подстрока ` 2>&1` -- буквальная, как в спеке.
 (в) `python -c` или `python - <<` -- буквально "python" (НЕ
     "python3" -- спека называет ровно эти два токена, расширять
     самостоятельно не стал), \b-границы, чтобы не матчить
     "mypython -c" как substring (тот же принцип, что WRITE_INDICATORS_RE
     dispatch_gate.py после t-152 retry).
 (г) запись в журнал мимо Edit/Write -- САМОСТОЯТЕЛЬНОЕ инженерное
     решение по неоднозначной формулировке спеки, ЗАДОКУМЕНТИРОВАНО
     (тот же принцип "решение не молча", что t-152/dispatch_gate.py):
     буквальный текст спеки "редирект `>`/`>>` или printf/echo с
     подстрокой routing-log" грамматически допускает два прочтения --
     (i) ЛЮБОЙ редирект `>`/`>>` уже триггерит класс, ИЛИ printf/echo
     только когда есть "routing-log"; (ii) подстрока "routing-log"
     обязательна ДЛЯ ОБЕИХ форм (редирект И printf/echo). Выбрано
     (ii): заголовок класса в спеке -- «запись в журнал мимо
     Edit/Write» (не «любой редирект в файл мимо Edit/Write» --
     это уже покрыто отдельным правилом 4 CLAUDE.md про Edit/Write-
     тулы вообще, а классы (в)/(г) спеки специально РАЗДЕЛЕНЫ: (в) --
     правки/скрипты вообще (правило 4), (г) -- именно ЖУРНАЛ (правило
     5, "Записи в журнал — Edit/Write-тулом"). Прочтение (i) сделало
     бы класс (г) triggered на ЛЮБОЙ команде с `>` независимо от
     журнала (`ls > out.txt` и т.п.) -- расходится с заголовком и
     нормой-источником (правило 5), не про журнал вовсе. Прочтение
     (ii) -- единственное, соответствующее заголовку класса и норме.
     Impact низкий в любом случае (WARN, не блокирует), но выбор
     осознанный, не угадан молча.
     Условие: substring "routing-log" (case-insensitive) ЕСТЬ в
     команде И (есть `>` ИЛИ есть токен printf/echo).

     v2 (t-255, 2026-07-21) -- порт механики AO3 hygiene_gate v2
     (scripts/hygiene_gate.py, их коммит 990615e) на живой FP-класс
     этой сессии (git add/commit/push с путём logs/routing-log.jsonl
     в аргументах и/или в теле commit-сообщения -- git НИЧЕГО не
     пишет в журнал, это ложное срабатывание). У нас НЕТ АО3-шного
     "канонического CLI-вызова" (`python scripts/log_append.py`) --
     наша норма правило 5 CLAUDE.md кита это «журнал -- Edit/Write-
     тулом», а не отдельная команда, поэтому АО3-шная (в)-ветка
     ("_is_canonical_call") сюда НЕ портируется -- она про исключение
     другого рода (специфическая CLI-форма), не применимо. Портированы
     РОВНО два независимых механизма АО3 (спека прямо разделяет их
     "Порт (1)"/"Порт (2)" -- НЕ один общий фикс, каждый закрывает
     свой под-класс FP):

     (1) _strip_commit_messages -- вырезание содержимого -m/--message
         git commit ПЕРЕД проверками (а)/(б), регекс COMMIT_MESSAGE_ARG_RE
         -- ДОСЛОВНО регекс АО3 (все формы: -m "...", -m '...',
         --message="...", --message='...', -m @'...'@, -m @"..."@
         PowerShell here-string), уже эмпирически проверенный их живым
         FP2 (та же bash-герока форма `-m "$(cat <<'EOF' ... EOF)"`,
         что в evidence этой задачи -- char-класс `[^"\\]` матчит
         переводы строк без re.MULTILINE/DOTALL по built-in семантике
         Python re, DOTALL в компиляции нужен только веткам с `.`
         (here-string формы), убедился чтением семантики, не гаданием).
         Закрывает под-класс "путь/подстрока журнала ВНУТРИ текста
         commit-сообщения".

     (2) _mask_git_statements -- НОВЫЙ механизм (у АО3 его как
         отдельной функции нет -- их FP2 закрывался ТОЛЬКО вырезанием
         сообщения, потому что там `>` было исключительно внутри
         сообщения; наша evidence-форма имеет ТОТ ЖЕ паттерн, но
         спека явно требует отдельный, более широкий механизм для
         случая БЕЗ commit/-m вовсе -- напр. `git diff
         logs/routing-log.jsonl > /tmp/out.txt`, где путь журнала --
         аргумент git diff, а `>` -- редирект СОБСТВЕННОГО вывода git
         в другой файл, не связанный с журналом; вырезание сообщения
         тут бессильно, т.к. сообщения нет). Маскирует (заменяет
         пробелом) statement, начинающийся с `git ` + один из
         add/commit/push/diff/log/show/status (после начала команды
         ИЛИ сразу после разделителя цепочки `;`/`&&`/`||`/перевода
         строки -- регекс сохраняет САМ символ-разделитель в выводе
         через захватывающую группу, чтобы не склеивать соседние
         statement'ы), ДО проверок (а)/(б). Порядок: (1) сначала
         (message ещё может содержать `;`/`&`/`|` внутри текста,
         которые сломали бы наивный сплит по этим символам в (2), если
         бы (2) шёл первым), затем (2) на уже вырезанном тексте.

     Известная остаточная дыра (симметрично HoleA/HoleB АО3, принята
     тем же принципом "warn-режим -- не граница безопасности", не
     устраняется превентивно): git-statement для show/diff МАСКИРУЕТСЯ
     ЦЕЛИКОМ, включая любой РЕАЛЬНЫЙ `>` внутри него -- значит
     настоящий обход самим git (`git show HEAD:logs/routing-log.jsonl
     > logs/routing-log.jsonl`, реально перезаписывающий журнал через
     git plumbing) тоже гасится и НЕ детектится. Тот же принцип
     распространяется и на СИНТАКСИЧЕСКИ КРИВОЙ `git commit` (напр.
     -m с незакрытой кавычкой) -- маскирование statement'а не
     различает валидность вложенных кавычек, поэтому даже такой
     кривой вызов гасится наравне с валидным (см. тест
     test_v2_unclosed_quote_in_message_not_stripped_but_git_statement_still_masked
     в tools/test_hygiene_gate.py -- сознательное РАСХОЖДЕНИЕ с прямым
     портом одноимённого AO3-теста, у которого такого второго слоя
     нет). Ужесточение -- только по evidence реальной утечки этого
     вида (правило 10г кита), не превентивно; см. также непортированную сюда AO3-специфику
     PowerShell-токенов записи (Add-Content/Set-Content/Out-File) --
     наш детектор класса (г) их не знает вовсе (не в спеке этой
     задачи, non-goals прямо запрещают трогать другие детекторы;
     ЗАМЕЧЕННЫЙ СИБЛИНГ-ПРОБЕЛ для отчёта, не фикс: наш
     PRINTF_ECHO_RE тоже уже (не знает sed/tee/awk, которые знает
     AO3's WRITE_TOKEN_RE) -- существовал ДО этой задачи, не тронут).

Регистронезависимость -- для ВСЕХ классов (спека явно не оговаривает
per-класс регистр; выбран единообразный case-insensitive, тот же
подход, что MANIFEST_*_RE/LABEL_MODEL_PREFIX_RE в dispatch_gate.py).

БЕЗОПАСНОСТЬ НА БОЛЬШИХ ВХОДАХ (DoD п.3, адверсариальная батарея --
команда >100КБ): все проверки -- substring (`in`, O(n)) или простые
\b-регексы БЕЗ вложенных квантификаторов (никаких `.*...*` цепочек,
которые могли бы дать катастрофический backtracking) -- линейны по
длине команды.

Fail-open: не-Bash/PowerShell тул, пустой/битый stdin, payload не
dict, command не строка/пустая строка -- везде (0, None) -- тихий
пропуск без побочных эффектов на stdout. Хук НИКОГДА не возвращает
ненулевой exit code (WARN-режим по спеке п.4: "Ни при каких входах
не блокировать и не падать ненулевым кодом").
"""

import json
import re
import sys

CD_PREFIX_START_RE = re.compile(r"^\s*cd\s+\S", re.IGNORECASE)
PY_DASH_C_RE = re.compile(r"\bpython\s+-c\b", re.IGNORECASE)
PY_HEREDOC_RE = re.compile(r"\bpython\s+-\s*<<", re.IGNORECASE)
PRINTF_ECHO_RE = re.compile(r"\b(printf|echo)\b", re.IGNORECASE)

# --- v2 (t-255): порт (1) -- вырезание -m/--message git commit ------
# ДОСЛОВНО регекс АО3 scripts/hygiene_gate.py (коммит 990615e), см.
# докстринг класса (г) выше -- все поддерживаемые формы значения -m/
# --message; DOTALL нужен только веткам с `.` (here-string), простые
# кавычковые ветки матчят переводы строк через char-класс нативно.
GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)

COMMIT_MESSAGE_ARG_RE = re.compile(
    r"-m\s+\"(?:[^\"\\]|\\.)*\""
    r"|-m\s+'[^']*'"
    r"|--message=\"(?:[^\"\\]|\\.)*\""
    r"|--message='[^']*'"
    r"|-m\s+@'.*?'@"
    r"|-m\s+@\".*?\"@",
    re.DOTALL,
)

# --- v2 (t-255): порт (2) -- маскирование git-statement ----------
# statement, начинающийся с `git ` + один из перечисленных
# подкоманд (после начала команды либо сразу после разделителя
# цепочки `;`/`&`/`|`/перевода строки). Группа 1 -- сам разделитель
# (или пустая строка на старте) -- сохраняется в замене НЕТРОНУТЫМ,
# чтобы не склеивать соседние statement'ы; группа 2 (тело statement'а
# до следующего разделителя) заменяется одним пробелом. Простой
# негативный char-класс `[^;&|\n]*` без вложенных квантификаторов --
# линейно по длине (та же гигиена, что и остальные регексы файла).
GIT_STATEMENT_RE = re.compile(
    r"(^|[;&|\n])(\s*git\s+(?:add|commit|push|diff|log|show|status)\b[^;&|\n]*)",
    re.IGNORECASE,
)

MSG_CD_PREFIX = "не префиксуй cd, вызывай из корня (гигиена п.3)"
MSG_REDIRECT_STDERR = "не добавляй 2>&1 (гигиена п.3)"
MSG_PYTHON_DASH_C = "правки/скрипты — Edit/Write-тулом или именованным скриптом (гигиена п.4)"
MSG_JOURNAL_BYPASS = "журнал пишется только Edit/Write (гигиена п.5)"


def _is_cd_prefix(command: str) -> bool:
    if not CD_PREFIX_START_RE.match(command):
        return False
    return "&&" in command or ";" in command


def _is_python_dash_c(command: str) -> bool:
    return bool(PY_DASH_C_RE.search(command) or PY_HEREDOC_RE.search(command))


def _strip_commit_messages(command: str) -> str:
    """v2 порт (1) -- вырезает -m/--message аргументы git commit ДО
    проверок (а)/(б): текст commit-сообщения (пути/подстроки журнала
    в прозе, `>` в ASCII-стрелках) не должен триггерить детект.
    Применяется, только если команда содержит `git commit`; сами
    пути git add/commit НЕ трогаются -- вырезается только аргумент
    сообщения. Незакрытая кавычка не матчится и остаётся как есть
    (fail-safe в сторону детекта, см. докстринг класса (г))."""
    if not GIT_COMMIT_RE.search(command):
        return command
    return COMMIT_MESSAGE_ARG_RE.sub(" ", command)


def _mask_git_statements(command: str) -> str:
    """v2 порт (2) -- маскирует statement'ы `git add/commit/push/
    diff/log/show/status ...` (git НЕ писатель журнала) ДО проверок
    (а)/(б), см. докстринг класса (г) выше про порядок относительно
    _strip_commit_messages и известную остаточную дыру (show/diff с
    редиректом РЕАЛЬНО перезаписывающим журнал через git plumbing --
    принято, не устраняется превентивно)."""
    return GIT_STATEMENT_RE.sub(lambda m: m.group(1) + " ", command)


def _is_journal_bypass(command: str) -> bool:
    scrubbed = _mask_git_statements(_strip_commit_messages(command))
    if "routing-log" not in scrubbed.lower():
        return False
    has_redirect = ">" in scrubbed
    has_printf_echo = bool(PRINTF_ECHO_RE.search(scrubbed))
    return has_redirect or has_printf_echo


def decide(payload: dict) -> tuple[int, dict | None]:
    """Чистая логика, без I/O -- тестируемая напрямую (тот же стиль,
    что dispatch_gate.decide/dod_track.build_fact). exit_code ВСЕГДА
    0 (WARN-режим). Возвращает (0, None) на тихий пропуск, (0, dict)
    -- dict уже готов к json.dumps на stdout при совпадении хотя бы
    одного класса."""
    if not isinstance(payload, dict):
        return 0, None

    tool_name = payload.get("tool_name")
    if tool_name not in ("Bash", "PowerShell"):
        return 0, None

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0, None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0, None

    triggered = []
    if _is_cd_prefix(command):
        triggered.append(MSG_CD_PREFIX)
    if " 2>&1" in command:
        triggered.append(MSG_REDIRECT_STDERR)
    if _is_python_dash_c(command):
        triggered.append(MSG_PYTHON_DASH_C)
    if _is_journal_bypass(command):
        triggered.append(MSG_JOURNAL_BYPASS)

    if not triggered:
        return 0, None

    context = "Командная гигиена (WARN, не блокирует): " + "; ".join(triggered)
    # B1 (critic t-177): ключа permissionDecision здесь НЕТ НАМЕРЕННО --
    # "allow" авто-аппрувил бы флагнутую (грязную) команду, подавляя
    # permission-prompt оператора; additionalContext доставляется модели
    # и без него, а решение о разрешении остаётся штатному permission-пути.
    return 0, {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }


def _reconfigure_stdout_utf8():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    _reconfigure_stdout_utf8()

    # Тот же байт-безопасный паттерн, что t-159-фикс dispatch_gate.py/
    # dod_track.py этого кита: sys.stdin.buffer.read() обходит
    # платформенную кодировку текстового sys.stdin (cp1251 на этой
    # машине), явный decode utf-8 с errors="replace" -- fail-open на
    # битые байты.
    raw_bytes = sys.stdin.buffer.read()
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except Exception:
        return 0

    exit_code, output = decide(payload)
    if output is not None:
        sys.stdout.write(json.dumps(output, ensure_ascii=False) + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
