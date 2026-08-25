"""permission_audit — восстановить, какие Bash/PowerShell-команды (включая субагентов)
вероятно требовали ручного подтверждения, и почему.

Порт из D:\\AO3_tests\\scripts\\permission_audit.py (t-106: принятая оценка пилота —
скрипт ловит, сигнал/шум хороший) под этот деплой. Логика эвристик (allowlist-матчинг,
auto-allow, sandbox-эвристики) — без изменений относительно оригинала. Две доработки,
найденные пилотом:

  (а) СНАПШОТ списка транскриптов и их размеров ДО скана — прогон в живой сессии
      дописывает сканируемый транскрипт, числа "Просканировано" иначе плывут между
      стартом и концом скрипта. Читаем только зафиксированный на старте префикс байт
      каждого файла, а не всё, что там окажется к моменту чтения.
  (b) Блок MASKED-BY-BROAD-ALLOWLIST — оба settings-файла сканируются на паттерны
      произвольного выполнения (голый интерпретатор/`-c`/`-e` перед `*`, например
      `Bash(python *)`) и печатается явное предупреждение: такие правила молча гасят
      часть категории «нет совпадения с allowlist», не показавшись как suspect вовсе.

Прямого лога «показан permission-диалог» нет, поэтому аудит эвристический:
берём все tool_use из транскриптов текущего проекта, прогоняем через те же правила,
что и харнесс (allowlist settings.json/settings.local.json + известные auto-allow +
sandbox-эвристики «cannot be statically analyzed»), и печатаем те, что НЕ прошли бы
без вопроса — с категорией причины и предложением фикса.

Запуск:  python tools/permission_audit.py [--minutes 120] [--all] [--session ID] [--summary]
  --minutes N  смотреть только команды за последние N минут (default 180)
  --all        игнорировать фильтр времени
  --session S  только транскрипты (main + subagents), чей путь содержит подстроку S
  --summary    сводка по группам вместо полного списка

П6 (разбивка permission-аудита по классам гигиены, замер, не решение) --
=========================================================================
Мотив: калибровка №6 намерила за окно 290 вызовов Bash/PowerShell, 210 вне
allowlist, классы гигиены -- `2>&1` x10, `cd/Set-Location` x8,
`python -c/heredoc` x7, «журнал мимо Edit/Write» 0. Все три первых класса --
ЖИВЫЕ warn'ы гейта tools/hygiene_gate.py, которые поведения агента не
изменили (команда всё равно ушла в исполнение). Стоит вопрос -- промотировать
ли часть классов из warn в блок; решение отложено, нужен замер окна при
НЕИЗМЕННОМ скоупе гейта, агрегации попаданий по классам не существовало.

ГРАНИЦА (соблюдена строго, зафиксировано явной строкой по требованию спеки):
этот пункт даёт ТОЛЬКО ЗАМЕР -- новый блок «По классам гигиены» в выводе
`--summary`. Выбор warn->блок в задачу НЕ входит, норм CLAUDE.md не меняет,
решается ОТДЕЛЬНО калибровкой №7. tools/hygiene_gate.py этой правкой не
тронут ни строкой (non-goals манифеста).

ИСТОЧНИК КЛАССИФИКАЦИИ -- ИМПОРТ tools/hygiene_gate.py (решение диспетчера,
не выбор builder'а): вторая реализация тех же четырёх классов запрещена
(D-0043 -- фиксить класс, не плодить экземпляр). classify_hygiene() ниже
вызывает РОВНО те приватные хелперы гейта, что диктует манифест задачи
(`_is_cd_prefix`, `_strip_commit_message_arg_only`, `_is_python_dash_c`,
`_is_journal_bypass`) -- те же регексы, те же скрабы (git-statement
маскирование, вырезание -m/--message, маскирование кавычек под `>`).

ЗАПИСАННОЕ ОГРАНИЧЕНИЕ (по требованию спеки): измеритель наследует слепоту
измеряемого -- если hygiene_gate какой-то формы записи/паттерна не видит,
этот аудит её тоже не увидит. Это осознанная цена единой точки правды (одна
классификация, не две расходящиеся), а не недосмотр этой правки.

Новый блок печатается ТОЛЬКО в `--summary` (чек 25 калибровки гоняет именно
сводку); ключ по всем ПРОСКАНИРОВАННЫМ вызовам (сопоставимо с baseline №6),
в скобках рядом -- сколько из них ЕЩЁ И suspects (allowlist+sandbox). Одна
команда может задеть несколько классов сразу -- сумма попаданий по классам
может ПРЕВЫШАТЬ число команд с ≥1 классом, отчёт печатает оба числа явно
(не заставляет читателя складывать самостоятельно).

ПЕРЕСДАЧА (t-364 attempt 2, вердикт критика) -- две правки поверх исходной
приёмки:
  F9 -- `total`/suspects и классовые счёты собирались ДВУМЯ независимыми
        обходами транскриптов (`collect_suspects` + `collect_hygiene_class_stats`,
        каждый со своим пересчётом `mtime`-отсечки) -- числа могли разъехаться
        на транскрипте, посвежевшем МЕЖДУ проходами. Фикс -- `collect_audit_stats()`,
        ОДИН проход, main() зовёт ровно её (см. докстринг функции ниже).
  F10 -- классификация в `classify_hygiene()` копирует не только регексы
        `hygiene_gate`, но и СБОРКУ конкретных проверок (например, порядок
        применения `_strip_commit_message_arg_only` к классу `2>&1`) --
        при семантическом дрейфе сборки внутри `hygiene_gate._collect_warn_classes`
        это разошлось бы МОЛЧА. Тест `test_classify_hygiene_matches_gate_attribution`
        (tools/test_permission_audit.py) фиксирует РАВЕНСТВО результата
        `classify_hygiene()` и прямой атрибуции `hygiene_gate` на матрице
        команд (4 класса + 3 известных FP + компаунды с несколькими
        классами) -- проверено эмпирически: расхождений 0.

ПЕРЕСДАЧА 3 (координатор, БЛОКЕР П6, V5-задача tools/hygiene_gate.py,
t-372) -- ЭТОТ файл ТРОГАЕТСЯ ЯВНО ПО ИМЕНИ координатора (исходный
манифест той задачи держал `tools/permission_audit.py` non-goal --
"сам модуль"; координатор ЭТОЙ дозадачи прямо предписал: "классификация
аудита обязана идти тем же путём, что гейт, включая состояние
выключателя" -- невозможно без правки `classify_hygiene()`; расценено
как явное снятие non-goal ИМЕННО для этой узкой правки, не общее
разрешение трогать файл шире).

ПРОБЛЕМА (найдена критиком, красный прогон с принудительно включённым
выключателем НЕ шевельнул НИ ОДНОГО пина аудита): `classify_hygiene()`
звала СТАРЫЕ (V4-style) хелперы `hygiene_gate` НАПРЯМУЮ на СЫРОЙ команде,
НЕЗАВИСИМО от `hygiene_gate.V5_ENABLED` -- `decide()` не вызывался
вовсе. Тест равенства сравнивал результат с атрибуцией, собранной ИЗ ТЕХ
ЖЕ старых хелперов -- т.е. был структурно СЛЕП именно к дрейфу
"классификация не знает о выключателе".

ФИКС: `classify_hygiene()` теперь ветвится по `hygiene_gate.V5_ENABLED`
(читает МОДУЛЬНЫЙ global гейта на каждый вызов, тот же паттерн, что
`decide()`/`_decide_v5` самого гейта) -- при `V5_ENABLED=False` СТАРАЯ
V4-ветка НЕ ИЗМЕНЕНА ни строкой (та же сборка, что уже была, уже
покрыта тестом равенства); при `V5_ENABLED=True` зовёт
`hygiene_gate._collect_v5_signals(command)` -- ТУ ЖЕ функцию, что
`_decide_v5` использует для сборки JSON-ответа (D-0043, single source
of truth, см. её докстринг в tools/hygiene_gate.py) -- дрейф между
гейтом и измерителем становится СТРУКТУРНО невозможным, а не просто
"совпадает по тесту равенства на сегодняшний день".

ТЕСТ РАВЕНСТВА РАСШИРЕН (координатор явно потребовал): параметризован
по ОБОИМ состояниям выключателя + добавлен ОТДЕЛЬНЫЙ регресс-тест
(`test_classify_hygiene_diverges_between_switch_states_pattern_as_data`),
который ЛОВИТ дрейф "классификация не знает о выключателе" ПО
ПОСТРОЕНИЮ -- команда с 2>&1-как-ДАННЫМИ внутри `-c` payload'а: V4-ветка
её засчитывает (старые хелперы не маскируют payload), V5-ветка -- нет
(маскировка часть 1 скрывает данные от класса б); если `classify_hygiene`
когда-либо перестанет реально ветвиться по `V5_ENABLED`, оба набора
классов совпадут и тест провалится.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import hygiene_gate

REPO = Path(__file__).resolve().parents[1]
PROJECT_KEY = "D--Improving-AI-Operating-System-for-LLMs"

# П6: имена классов -- ДОСЛОВНО словами норм CLAUDE.md / чека 25 (решение
# диспетчера), чтобы строки этого отчёта складывались с формулировками
# калибровки без перевода.
HYGIENE_CLASS_LABELS = [
    "2>&1",
    "cd/Set-Location",
    "python -c/heredoc",
    "журнал мимо Edit/Write",
]


def _resolve_claude_projects() -> Path:
    """Каталог транскриптов для скана. CLAUDE_PROJECTS, если задан в
    окружении, — ПОЛНЫЙ путь-переопределение для этого проекта; он
    перекрывает захардкоженный PROJECT_KEY выше. Использовать на любой
    установке, где PROJECT_KEY этого файла не совпадает с реальным
    ~/.claude/projects/<slug> на данной машине."""
    override = os.environ.get("CLAUDE_PROJECTS")
    if override:
        return Path(override)
    return Path(os.path.expanduser("~")) / ".claude" / "projects" / PROJECT_KEY


CLAUDE_PROJECTS = _resolve_claude_projects()

# --- команды, которые харнесс авто-разрешает без allowlist (усечённый практичный список) ---
AUTO_ALLOW_ANY_ARGS = {
    "cat", "head", "tail", "wc", "stat", "ls", "cd", "echo", "sleep", "which", "diff",
    "true", "false", "seq", "basename", "dirname", "realpath", "cut", "tr", "comm",
    "readlink", "expr", "type", "uname", "df", "du", "nl", "od", "id", "date",
}
AUTO_ALLOW_VALIDATED = {"grep", "rg", "find", "sort", "uniq", "jq", "sed", "ps", "xargs",
                        "file", "tree", "hostname", "pgrep", "lsof", "printf", "man"}
GIT_RO = {"status", "log", "diff", "show", "blame", "branch", "tag", "remote", "ls-files",
          "rev-parse", "describe", "reflog", "shortlog", "cat-file", "for-each-ref",
          "worktree", "stash"}

SANDBOX_HEURISTICS = [
    (re.compile(r'export\s+\w+="[^"]*\$\{?\w+'), "export VAR со ссылкой на другую переменную (array-subscript эвристика)"),
    (re.compile(r"\bnohup\b"), "nohup / ручной фон"),
    (re.compile(r"\$\("), "командная подстановка $(...)"),
    (re.compile(r"\bfor\s+\w+\s+in\b.*\bdo\b", re.S), "цикл for...do в shell"),
    (re.compile(r"\buntil\b|\bwhile\b.*\bdo\b", re.S), "цикл while/until"),
    (re.compile(r"&\s*$", re.M), "фоновый запуск через &"),
]

# --- доработка (b): паттерны allowlist, дающие практически произвольное выполнение кода ---
INTERPRETER_HEADS = {
    "python", "python3", "py", "node", "ruby", "perl", "bash", "sh", "zsh",
    "powershell", "pwsh", "osascript", "php",
}
CODE_FLAGS = {"-c", "-e", "--command"}


def _iter_allow_entries():
    """(file_name, tool, pattern) по обеим settings-файлам, сырые записи allow."""
    for name in ("settings.json", "settings.local.json"):
        p = REPO / ".claude" / name
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[warn] не смог прочитать {name}: {e}", file=sys.stderr)
            continue
        for entry in data.get("permissions", {}).get("allow", []):
            m = re.match(r"^(\w+)\((.*)\)$", entry, re.S)
            if m:
                yield name, m.group(1), m.group(2)
            else:
                yield name, entry, ""  # голое имя тула, например WebSearch


def load_allow_patterns() -> list[tuple[str, str]]:
    """[(tool, pattern), ...] из settings.json + settings.local.json."""
    return [(tool, pat) for _name, tool, pat in _iter_allow_entries()]


def matches_allow(tool: str, cmd: str, patterns) -> bool:
    for ptool, pat in patterns:
        if ptool != tool:
            continue
        if not pat:
            return True
        if pat.endswith("*"):
            if cmd.startswith(pat[:-1]):
                return True
        elif " *" in pat:  # форма "foo *" — префикс до звёздочки
            if cmd.startswith(pat.split(" *")[0]):
                return True
        elif fnmatch.fnmatch(cmd, pat) or cmd == pat:
            return True
    return False


def is_auto_allowed(cmd: str) -> bool:
    """Грубая оценка встроенного auto-allow (только однострочные простые команды)."""
    if "\n" in cmd.strip():
        return False
    # цепочки — каждая часть должна быть auto-allowed
    parts = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd.strip())
    for part in parts:
        if not part:
            continue
        tokens = part.strip().split()
        if not tokens:
            continue
        head = tokens[0].strip('"')
        base = os.path.basename(head).lower().removesuffix(".exe")
        if base == "git" and len(tokens) > 1 and tokens[1] in GIT_RO:
            continue
        if base in AUTO_ALLOW_ANY_ARGS or base in AUTO_ALLOW_VALIDATED:
            continue
        return False
    return True


def sandbox_flags(cmd: str) -> list[str]:
    flags = [reason for rx, reason in SANDBOX_HEURISTICS if rx.search(cmd)]
    if "\n" in cmd.strip():
        flags.append("многострочная команда (несколько statement'ов в одном вызове)")
    return flags


_ENV_ASSIGN_RE = re.compile(r"^\w+=\S*$")


def is_broad_wildcard(tool: str, pat: str) -> str | None:
    """Если pat — allowlist-паттерн, пропускающий произвольное выполнение (голый
    интерпретатор перед `*`, интерпретатор с флагом -c/-e перед `*`, в т.ч. с
    незакрытой открывающей кавычкой сразу после флага, опционально за префиксом
    вида VAR=val) — вернуть причину строкой. Иначе None. Примеры находок пилота:
    Bash(python *), Bash(python -c ' *), Bash(PYTHONUTF8=1 python -c ' *)."""
    if tool not in ("Bash", "PowerShell"):
        return None
    p = pat.strip()
    if not p.endswith("*"):
        return None
    prefix = p[:-1].strip()
    tokens = prefix.split()
    while tokens and _ENV_ASSIGN_RE.match(tokens[0]):
        tokens = tokens[1:]  # пропустить VAR=val перед именем интерпретатора
    if not tokens:
        return None
    head = os.path.basename(tokens[0].strip("\"'")).lower().removesuffix(".exe")
    if head not in INTERPRETER_HEADS:
        return None
    rest = tokens[1:]
    if not rest:
        return f"голый интерпретатор без аргументов — пропускает произвольный код после «{head}»"
    if rest[0] in CODE_FLAGS:
        remainder = "".join(rest[1:]).strip("'\"")
        if not remainder:
            return f"«{head} {rest[0]}» — произвольный код одной строкой проходит без вопроса"
    # F2 ревью t-107: `<интерпретатор> -m *` пропускает произвольный МОДУЛЬ
    # (python -m http.server, -m pip, ...) — тот же класс, что -c/-e.
    if rest[0] == "-m" and not "".join(rest[1:]).strip("'\""):
        return f"«{head} -m» — произвольный модуль проходит без вопроса"
    return None


def scan_broad_wildcards() -> list[tuple[str, str, str, str]]:
    """[(settings-файл, tool, pattern, reason), ...] для широких wildcard-паттернов,
    молча гасящих категорию «нет совпадения с allowlist» (доработка b пилота)."""
    out = []
    for fname, tool, pat in _iter_allow_entries():
        reason = is_broad_wildcard(tool, pat)
        if reason:
            out.append((fname, tool, pat, reason))
    return out


def check_transcripts_present(claude_projects: Path | None = None) -> bool:
    """Громко предупредить в stderr (не исключение — скан продолжается с
    нулём), если каталог транскриптов не существует, либо существует, но
    глоб не находит ни одного файла. Класс «тихий ноль»: установка, чей
    PROJECT_KEY не совпадает с реальным ~/.claude/projects/<slug> на этой
    машине, иначе молча печатает «Просканировано: 0» без намёка на причину.
    Возвращает True, если предупреждение было напечатано."""
    cp = claude_projects if claude_projects is not None else CLAUDE_PROJECTS
    n = 0
    if cp.exists():
        n = len(list(cp.glob("*.jsonl"))) + len(list(cp.glob("*/subagents/agent-*.jsonl")))
    if not cp.exists() or n == 0:
        print(
            f"ВНИМАНИЕ: 0 транскриптов найдено в {cp} — вероятно неверный слаг проекта; "
            "установите CLAUDE_PROJECTS в правильный каталог '~/.claude/projects/<slug>'",
            file=sys.stderr,
        )
        return True
    return False


def snapshot_transcripts(session: str | None = None) -> list[tuple[Path, str, int]]:
    """[(path, agent_type, size_at_snapshot), ...] — зафиксировать список
    транскриптов и их размеры ДО скана (доработка a пилота): прогон в живой сессии
    дописывает сканируемый транскрипт, и без снапшота числа "Просканировано" плывут
    между стартом и концом скрипта. Скан ниже читает только эти первые
    size_at_snapshot байт каждого файла — то, что дописано после снапшота, игнорируется."""
    files: list[tuple[Path, str]] = []
    for jl in CLAUDE_PROJECTS.glob("*.jsonl"):
        files.append((jl, "main"))
    for sub in CLAUDE_PROJECTS.glob("*/subagents/agent-*.jsonl"):
        if session and session not in str(sub):
            continue
        agent_type = "subagent"
        meta = sub.with_name(sub.name.replace(".jsonl", ".meta.json"))
        if meta.exists():
            try:
                agent_type = json.loads(meta.read_text(encoding="utf-8")).get("agentType", "subagent")
            except Exception:  # noqa: BLE001
                pass
        files.append((sub, agent_type))

    snapshot = []
    for path, source in files:
        if session and source == "main" and session not in path.name:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        snapshot.append((path, source, size))
    return snapshot


def _read_snapshot_lines(path: Path, size: int) -> list[str]:
    """Прочитать первые `size` байт файла (зафиксированные снапшотом) и вернуть
    полные строки; возможную обрезанную последнюю строку на границе отбрасываем."""
    try:
        with open(path, "rb") as fb:
            data = fb.read(size)
    except OSError:
        return []
    text = data.decode("utf-8", errors="replace")
    if not text.endswith("\n") and "\n" in text:
        text = text[: text.rfind("\n") + 1]
    elif not text.endswith("\n"):
        text = ""  # единственная строка в файле оборвана на границе снапшота
    return text.splitlines()


def iter_tool_calls(minutes: float | None, session: str | None = None,
                     snapshot: list[tuple[Path, str, int]] | None = None):
    """(when, source, agent_type, tool, command) по снапшоту транскриптов проекта."""
    cutoff = None if minutes is None else time.time() - minutes * 60
    if snapshot is None:
        snapshot = snapshot_transcripts(session)

    for path, source, size in snapshot:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if cutoff and mtime < cutoff:
            continue  # файл не менялся в окне — пропускаем целиком
        for line in _read_snapshot_lines(path, size):
            line = line.strip()
            if not line or '"tool_use"' not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            ts = obj.get("timestamp")
            when = None
            if ts:
                try:
                    when = datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                except Exception:  # noqa: BLE001
                    pass
            if cutoff and when and when < cutoff:
                continue
            for item in obj.get("message", {}).get("content", []) or []:
                if isinstance(item, dict) and item.get("type") == "tool_use" \
                        and item.get("name") in ("Bash", "PowerShell"):
                    cmd = (item.get("input") or {}).get("command", "")
                    yield when, path.name, source, item["name"], cmd


def _suspect_reason(tool: str, cmd: str, patterns) -> list[str] | None:
    """Общее ядро suspect-определения, вынесенное из collect_suspects (D-0043
    -- та же логика нужна П6 collect_hygiene_class_stats ниже, вторая копия
    запрещена). None -- команда НЕ suspect; иначе список причин (как раньше)."""
    allowed = matches_allow(tool, cmd, patterns)
    flags = sandbox_flags(cmd)
    if (allowed and not flags) or is_auto_allowed(cmd):
        return None
    reason = []
    if not allowed:
        reason.append("нет совпадения с allowlist")
    reason += flags
    return reason


def collect_audit_stats(minutes: float | None, session: str | None = None,
                         snapshot: list[tuple[Path, str, int]] | None = None):
    """F9 (пересдача t-364 attempt 2, вердикт критика): ОДИН обход
    `iter_tool_calls` -- suspects, total И классовые счёты гигиены (П6)
    собираются из ОДНОЙ И ТОЙ ЖЕ выборки за ОДНУ итерацию, `mtime`-отсечка
    (вычисляется внутри `iter_tool_calls` при первом обращении к генератору)
    происходит РОВНО ОДИН РАЗ.

    ДО этой правки `collect_suspects` и `collect_hygiene_class_stats` были
    ДВА НЕЗАВИСИМЫХ обхода: каждый звал `iter_tool_calls(...)` заново, и
    каждый вызов заново вычислял `cutoff = time.time() - minutes * 60`
    (см. докстринг `iter_tool_calls`). Транскрипт, чей `mtime` пересёк
    границу окна МЕЖДУ двумя проходами (второй проход стартует на доли
    секунды позже первого, но при реальном окне в минуты этого достаточно
    для событий на самой границе), мог попасть в один набор чисел и
    выпасть из другого -- РОВНО класс «числа плывут», против которого сам
    инструмент изначально заводил снапшот транскриптов (см. докстринг
    модуля/`snapshot_transcripts`, доработка (a) пилота). Особенно
    неуместно для ИНСТРУМЕНТА ЗАМЕРА (П6): несопоставимые `total` и
    классовые счёты обесценивают сравнение с baseline калибровки №6.

    ФИКС: единственная точка входа для main() -- один проход по
    `iter_tool_calls(minutes, session, snapshot)`, `total`/`suspects`/
    классовые счёты аккумулируются В ОДНОМ ТЕЛЕ ЦИКЛА над одним и тем же
    `when/agent/tool/cmd`. `collect_suspects`/`collect_hygiene_class_stats`
    ниже СОХРАНЕНЫ как узкие обёртки (публичный контракт -- сигнатура и
    форма возврата -- не меняется, существующие тесты это подтверждают),
    но каждая по-прежнему делает СВОЙ отдельный вызов сюда, а значит СВОЙ
    отдельный обход -- если вызывающему нужны ОБА набора чисел
    одновременно и согласованно (main(), единственный такой вызывающий в
    этом файле), он обязан звать `collect_audit_stats()` напрямую ОДИН
    РАЗ, а не оба геттера по отдельности; main() ниже переписан именно так.

    Возвращает (suspects, total, class_counts, class_suspect_counts,
    any_class_count) -- те же формы значений, что были у двух функций
    раздельно, просто из одного прохода."""
    patterns = load_allow_patterns()
    suspects = []
    total = 0
    class_counts = {label: 0 for label in HYGIENE_CLASS_LABELS}
    class_suspect_counts = {label: 0 for label in HYGIENE_CLASS_LABELS}
    any_class_count = 0
    for when, fname, agent, tool, cmd in iter_tool_calls(minutes, session, snapshot):
        total += 1
        reason = _suspect_reason(tool, cmd, patterns)
        is_suspect = reason is not None
        if is_suspect:
            suspects.append((when, agent, tool, cmd, reason))
        classes = classify_hygiene(cmd)
        if classes:
            any_class_count += 1
            for c in classes:
                class_counts[c] += 1
                if is_suspect:
                    class_suspect_counts[c] += 1
    return suspects, total, class_counts, class_suspect_counts, any_class_count


def collect_suspects(minutes: float | None, session: str | None = None,
                      snapshot: list[tuple[Path, str, int]] | None = None):
    """Прогнать все tool_use через allowlist + sandbox-эвристики.

    Возвращает (suspects, total), где suspects — список
    (when, agent, tool, cmd, reason) для команд, которые ВЕРОЯТНО требовали
    ручного подтверждения. Вынесено из main() отдельной чистой функцией,
    чтобы юнит-тесты могли проверять фильтрацию без парсинга stdout.

    F9: узкая обёртка над `collect_audit_stats` (см. её докстринг) --
    сигнатура и форма возврата НЕ изменились, существующие тесты это
    подтверждают. Самостоятельный вызов этой функции -- по-прежнему
    отдельный проход; main() эту функцию НЕ зовёт (см. F9), чтобы не
    дублировать обход."""
    suspects, total, *_rest = collect_audit_stats(minutes, session, snapshot)
    return suspects, total


def classify_hygiene(command) -> list[str]:
    """П6: список СРАБОТАВШИХ классов гигиены для ОДНОЙ команды -- классы
    НЕЗАВИСИМЫ (одна команда может задеть несколько сразу, см. D5 спеки).
    Источник классификации -- ИМПОРТ tools/hygiene_gate.py (D-0043, см.
    докстринг модуля выше про унаследованную слепоту измерителя); вторая
    реализация тех же регексов/скрабов здесь ЗАПРЕЩЕНА.

    ПЕРЕСДАЧА 3 (координатор, БЛОКЕР П6, см. докстринг модуля выше за
    полный разбор): классификация ветвится по `hygiene_gate.V5_ENABLED`
    -- измеритель обязан идти ТЕМ ЖЕ путём, что гейт, включая состояние
    выключателя. `V5_ENABLED=False` -- СТАРАЯ ветка, НЕ изменена ни
    строкой. `V5_ENABLED=True` -- зовёт `hygiene_gate._collect_v5_signals`
    (ТУ ЖЕ функцию, что `_decide_v5` самого гейта использует для сборки
    ответа -- single source of truth, D-0043, не вторая реализация).

    ПЕРЕСДАЧА 4 (координатор, перепроектировка, В5): части 1/3
    (маскировка/write-намерение) в hygiene_gate.py удалены целиком,
    принцип "deny требует определённости" заменил их -- ключи
    `_collect_v5_signals()` изменились ПО СОСТАВУ (`cd_to_repo_root`/
    `redirect_certain`/`ambiguous` вместо `write_intent`), но ЧЕТЫРЕ
    ключа, которые ЭТА функция читает (`redirect`/`cd`/`pyc`/`journal`),
    сохранили СВОЙ смысл ("класс сработал ВООБЩЕ, deny или warn") --
    правка ниже НЕ потребовалась (естественное следствие, что ветка
    ссылается на сигналы по ИМЕНИ, не по позиции/структуре dict'а).
    ГРАНУЛЯРНОСТЬ deny-vs-warn ПО КЛАССАМ cd/2>&1 (В5: "метка на КАЖДЫЙ
    класс, deny и warn") ДОСТУПНА через `_collect_v5_signals()` напрямую
    (`cd_to_repo_root` vs `cd`, `redirect_certain` vs `redirect`) --
    ЭТА функция (`classify_hygiene`) сознательно НЕ меняет свой контракт
    возврата (плоский список из 4 строк) -- он используется для
    сравнения с baseline калибровки №6 (тот же формат меток
    HYGIENE_CLASS_LABELS); замер deny/warn-разбивки по корпусу сделан
    ОТДЕЛЬНЫМ скриптом (см. отчёт пересдачи 4, не постоянный код этого
    файла) -- РЕШЕНИЕ ЗАДОКУМЕНТИРОВАНО, не молчаливое: расширение
    ПОСТОЯННОГО формата отчёта `--summary` за рамки этой дозадачи, при
    сомнении -- вопрос координатору, не самостоятельный выбор формата.

    ПЕРЕСДАЧА 5 (координатор, финальный фикс, третий критик-вход, Ф1/Ф2):
    ключ `ambiguous` УДАЛЁН из `_collect_v5_signals()` вместе со списком
    интерпретаторов `_is_ambiguous` (заменён кавычками, см. докстринг
    `_collect_redirect_signal` в hygiene_gate.py) -- ЭТА функция его не
    читала и не читает, изменение НЕ потребовало правки здесь (тот же
    принцип: обращение по имени ключа, не по структуре dict'а).

    `command` не строка / None / пустая строка -> [] без исключения --
    класс не засчитывается, скрипт не падает (краевое поведение задано
    спекой явно).

    F3(A) (сужение предиката pyc, 2026-08-25, hygiene_gate.py К3.6):
    ЭТА функция читает `signals["pyc"]` -- ШИРОКИЙ, НЕИЗМЕНЁННЫЙ сигнал
    ("класс сработал вообще", I1) -- НЕ новый ключ `pyc_payload`. С
    К3.6 счёт класса ЗДЕСЬ (classify_hygiene помечает "python -c/heredoc"
    триггернутым по ШИРОКОМУ `pyc`) МОЖЕТ РАСХОДИТЬСЯ со счётом
    РЕАЛЬНЫХ warn-строк на стороне гейта (`_decide_v5`): certain-payload,
    доказанно чистый (`pyc_payload == "P"`), даёт `pyc == True` (класс
    ЗДЕСЬ засчитан), но САМ ГЕЙТ теперь МОЛЧИТ для этой же команды (ни
    строки в additionalContext) -- "счёт класса ≠ счёт варна". Это
    СОЗНАТЕЛЬНОЕ расхождение (F3(A), НЕ этот диспатч чинит baseline чека
    25 -- отдельный ход Lead), не дефект: измеритель остаётся на старом
    контракте (4-меточный список, сравнение с baseline), гейт получил
    новую, более узкую warn-семантику независимо от него."""
    if not isinstance(command, str) or not command:
        return []
    if hygiene_gate.V5_ENABLED:
        signals = hygiene_gate._collect_v5_signals(command)
        classes = []
        if signals["redirect"]:
            classes.append("2>&1")
        if signals["cd"]:
            classes.append("cd/Set-Location")
        if signals["pyc"]:
            classes.append("python -c/heredoc")
        if signals["journal"]:
            classes.append("журнал мимо Edit/Write")
        return classes
    classes = []
    if " 2>&1" in hygiene_gate._strip_commit_message_arg_only(command):
        classes.append("2>&1")
    if hygiene_gate._is_cd_prefix(command):
        classes.append("cd/Set-Location")
    if hygiene_gate._is_python_dash_c(command):
        classes.append("python -c/heredoc")
    if hygiene_gate._is_journal_bypass(command):
        classes.append("журнал мимо Edit/Write")
    return classes


def collect_hygiene_class_stats(minutes: float | None, session: str | None = None,
                                 snapshot: list[tuple[Path, str, int]] | None = None):
    """П6: прогнать ВСЕ просканированные вызовы (не только suspects -- D2:
    иначе замер несопоставим с baseline калибровки №6, где попадания
    считались независимо от allowlist) через classify_hygiene().

    Возвращает (class_counts, class_suspect_counts, any_class_count):
      - class_counts: {класс: N} -- число ПОПАДАНИЙ класса среди всех
        просканированных вызовов (двойной счёт: команда с двумя классами
        инкрементирует оба);
      - class_suspect_counts: {класс: N} -- тот же счёт, но только для
        вызовов, которые ЕЩЁ И suspects (тот же критерий, что
        collect_suspects, общее ядро _suspect_reason);
      - any_class_count: число КОМАНД (не попаданий), у которых сработал
        хотя бы один класс -- сумма class_counts.values() может ПРЕВЫШАТЬ
        это число при двойном срабатывании одной команды (D5).

    F9: узкая обёртка над `collect_audit_stats` (см. её докстринг) --
    сигнатура и форма возврата НЕ изменились. Самостоятельный вызов --
    по-прежнему отдельный проход; main() эту функцию НЕ зовёт (см. F9)."""
    _suspects, _total, class_counts, class_suspect_counts, any_class_count = (
        collect_audit_stats(minutes, session, snapshot))
    return class_counts, class_suspect_counts, any_class_count


def main(argv=None):
    if os.name == "nt":  # консоль Windows в cp866 душит кириллицу — форсим utf-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # тот же класс: [warn]-строки и WARNING-строка ниже тоже кириллица
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=180)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--session", help="фильтр: только транскрипты, чьи пути содержат эту подстроку (id сессии)")
    ap.add_argument("--summary", action="store_true", help="сводка по группам вместо полного списка")
    args = ap.parse_args(argv)
    minutes = None if getattr(args, "all") else args.minutes

    check_transcripts_present()

    # доработка (b): предупреждение о широких allowlist-паттернах — перед сводкой
    broad = scan_broad_wildcards()
    if broad:
        print("MASKED-BY-BROAD-ALLOWLIST:")
        print("  Эти правила allowlist пропускают произвольное выполнение кода и МОЛЧА")
        print("  глушат часть категории «нет совпадения с allowlist» ниже — команды под")
        print("  ними даже не попадут в suspects, хотя по факту могут быть неверной формой:")
        for fname, tool, pat, reason in broad:
            print(f"  - {fname}: {tool}({pat}) — {reason}")
        print()

    snapshot = snapshot_transcripts(args.session)
    # F9: ОДИН вызов collect_audit_stats -- total, suspects И классовые
    # счёты гигиены (П6) выходят из ОДНОГО прохода по одному и тому же
    # snapshot/mtime-отсечке (см. её докстринг). НЕ звать collect_suspects
    # + collect_hygiene_class_stats по отдельности здесь -- это вернуло бы
    # ровно тот баг, который F9 чинит (два независимых прохода, числа
    # плывут между ними).
    suspects, total, class_counts, class_suspect_counts, any_class_count = (
        collect_audit_stats(minutes, args.session, snapshot))

    print(f"Просканировано вызовов Bash/PowerShell: {total}"
          + ("" if minutes is None else f" (за последние {minutes:g} мин)")
          + (f" · сессия *{args.session[:8]}*" if args.session else ""))
    print(f"Вероятно требовали подтверждения: {len(suspects)}\n")

    if args.summary:
        from collections import Counter
        by_agent = Counter(a for _, a, *_ in suspects)
        by_reason = Counter(r for *_, reasons in suspects for r in reasons)
        examples: dict[str, str] = {}
        for _, agent, _tool, cmd, reasons in suspects:
            for r in reasons:
                examples.setdefault(r, " ".join(cmd.split())[:110])
        print("По агентам:")
        for a, n in by_agent.most_common():
            print(f"  {n:4d}  {a}")
        print("\nПо причинам:")
        for r, n in by_reason.most_common():
            print(f"  {n:4d}  {r}")
            print(f"        пример: {examples[r]}")

        # П6: замер по классам гигиены -- ДРУГАЯ выборка (все просканированные
        # вызовы, не только suspects), но ИЗ ТОГО ЖЕ прохода, что total/suspects
        # выше (F9) -- заголовок несёт это явно, чтобы читатель не сложил
        # несовместимые числа с блоками выше.
        print("\nПо классам гигиены (все просканированные вызовы; в скобках — сколько из них suspects):")
        for label in HYGIENE_CLASS_LABELS:
            print(f"  {class_counts[label]:4d}  {label}  (suspects: {class_suspect_counts[label]})")
        print(f"  команд с ≥1 классом: {any_class_count}")
    else:
        for when, agent, tool, cmd, reason in suspects:
            t = datetime.fromtimestamp(when, tz=timezone.utc).strftime("%H:%M:%S") if when else "--:--:--"
            one_line = " ".join(cmd.split())[:150]
            print(f"[{t}] {agent} / {tool}")
            print(f"  cmd: {one_line}")
            print(f"  причина: {'; '.join(reason)}")
            print()
    if suspects:
        print("Рекомендации по категориям:")
        print(" - «нет совпадения с allowlist» → добавить wildcard-паттерн в .claude/settings.json")
        print(" - «многострочная/цикл/nohup/подстановка» → allowlist НЕ поможет; перенести логику")
        print("   в именованную функцию/скрипт tools/ и запретить паттерн в .claude/agents/*.md")
        print(" - помнить: settings.json перечитывается только новыми (суб)агентами, не на лету")


if __name__ == "__main__":
    main()
