"""Журнальный валидатор (t-031, D-0052/D-0053/D-0058) -- pre-commit-гейт
для logs/routing-log.jsonl: ловит кодом ровно те два прецедента, что уже
случались вживую -- дубль task_id (t-029, повторная выдача без
перечитывания хвоста) и F-29 (события с ts, написанным из повествования,
«в будущем»). Стиль вызова/структура повторяют tools/mechanism_gate.py
(D-0043, ось 1: тот же дом enforcement-цепочки): чистая decide(),
тестируемая без git, main() -- тонкая git-обвязка вокруг неё.

Область: ТОЛЬКО staged-версия logs/routing-log.jsonl против HEAD-версии
(git show :logs/... vs HEAD:logs/...). Файл не staged -> main() молча
возвращает 0 (гейт не пишет вообще ничего). Только детерминированно
решаемое -- присутствие/форма/типизированные поля; смысл notes НЕ
парсится (D-0063).

Проверки (нумерация -- как в спеке t-031 / CLAUDE.md «Журнал
маршрутизации»):
 1. Append-only: staged обязана начинаться с HEAD как префикс.
 2. Каждая НОВАЯ строка -- валидный JSON-объект в одну строку с полями
    ts/event/agent/category/notes (notes непустая).
 3. event из ENUM.
 4. model обязателен для delegated/escalated/accepted/rejected.
 5. task_id обязателен для delegated/accepted/rejected/escalated/
    defect_found, формат t-NNN (3+ цифр).
 6. rejected: attempt -- целое >=1; failure_class из ENUM.
 7. accepted с agent=builder: witness непустая строка.
 8. defect_found: ref непустой.
 9. Новизна/ссылочность task_id (ИСПРАВЛЕНО Lead-поправкой после живого
    прецедента -- «строго max+1» запрещал бы легальный critic-вход
    приёмки и ретрай после rejected). Для НОВОГО delegated:
    а) task_id == max(все t-NNN в файле до этой строки)+1 -- легально
       всегда (новая задача);
    б) task_id уже существует в файле И задача ОТКРЫТА (нет accepted
       с этим task_id выше по файлу) И agent новой строки отличается
       от agent ВСЕХ предыдущих delegated этого task_id -- легально
       (continuation-диспатч другого яруса, напр. critic-вход приёмки);
    в) task_id существует, задача открыта, agent совпадает с одним из
       предыдущих delegated -- легально ТОЛЬКО с полем attempt (целое
       >=2) И существующим выше rejected с тем же task_id (ретрай
       после отклонения);
    г) всё остальное -- FAIL (дубль-паттерн t-029: тот же agent, без
       attempt, без rejected; и delegated на ЗАКРЫТУЮ задачу -- reopen
       запрещён, коллизия = две задачи, D-0060).
    Для нового accepted/rejected/escalated/defect_found -- ссылается на
    task_id, уже встреченный выше в файле (HEAD или ранее в этом же
    коммите); без изменений.
10. ts новых строк монотонны относительно последней строки HEAD и
    между собой; не позже now+10 минут (F-29). Нижней границы нет.
11. Матрица D-0058 (только для НОВЫХ строк): новые accepted/rejected
    несут typed-поле "by". Для agent=lead матрица не применяется --
    "by" достаточно присутствия. Для agent из {scout,builder,critic}
    ТОЛЬКО accepted дополнительно легален, если tier(by) > tier(agent)
    (haiku<sonnet<opus<fable по agent: scout=haiku, builder=sonnet,
    critic=opus), либо typed-поле "basis" из {"critic",
    "queued-to-lead"}. Спека буквально требует tier/basis-проверку
    только для accepted, не rejected -- rejected несёт "by" без
    дальнейшей проверки (см. отчёт: буквальное чтение, не домысел).

12. Любой FAIL -> exit 1, по каждой нарушившей строке -- номер строки,
    event/task_id, какая проверка упала. Крэш валидатора (исключение,
    не FAIL валидации) -> exit 2 с трейсбеком (fail-closed, как
    mechanism_gate: cм. main()).
"""
from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
import traceback

JOURNAL_PATH = "logs/routing-log.jsonl"

EVENTS = {
    "delegated", "accepted", "rejected", "escalated", "decomposable",
    "dispatch_skipped", "defect_found", "lead_degraded", "lead_restored",
    "journal_created", "calibrated",
}
MODEL_REQUIRED_EVENTS = {"delegated", "escalated", "accepted", "rejected"}
TASK_ID_REQUIRED_EVENTS = {"delegated", "accepted", "rejected", "escalated", "defect_found"}
FAILURE_CLASSES = {"spec", "capability", "recon", "tooling"}
TIER_ORDER = {"haiku": 0, "sonnet": 1, "opus": 2, "fable": 3}
AGENT_TIER = {"scout": "haiku", "builder": "sonnet", "critic": "opus"}
BASIS_VALUES = {"critic", "queued-to-lead"}

TASK_ID_RE = re.compile(r"^t-(\d{3,})$")
# ISO без таймзоны: 'YYYY-MM-DDTHH:MM:SS' с опциональными микросекундами,
# БЕЗ 'Z'/смещения -- таймзона запрещена спекой (иначе пропадает
# однозначность монотонности между строками разных смещений).
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$")


def parse_ts(ts: str):
    if not isinstance(ts, str) or not TS_RE.match(ts):
        return None
    try:
        return datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None


def split_lines(text: str | None) -> list[str]:
    if not text:
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _try_parse_obj(line: str):
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def extract_task_ids(lines: list[str]) -> set[str]:
    """Все task_id (валидного формата t-NNN), встреченные в ЛЮБОМ событии
    этих строк -- используется и для множества "существующих выше", и
    как основа для max(...)+1."""
    ids = set()
    for line in lines:
        obj = _try_parse_obj(line)
        if obj is None:
            continue
        tid = obj.get("task_id")
        if isinstance(tid, str) and TASK_ID_RE.match(tid):
            ids.add(tid)
    return ids


def max_task_num(ids: set[str]) -> int:
    nums = [int(TASK_ID_RE.match(i).group(1)) for i in ids]
    return max(nums) if nums else 0


def _harvest_line_into(event, task_id, agent, delegated_agents: dict, closed_tasks: set,
                        rejected_tasks: set) -> None:
    """Правило 9(б/в) state: обновляет per-task_id историю ОДНОЙ строкой
    (используется и для затравки из HEAD, и построчно для новых строк --
    порядок вызовов = порядок появления строк в файле, так что состояние
    на момент проверки строки N отражает ровно "всё выше по файлу")."""
    if not (isinstance(task_id, str) and TASK_ID_RE.match(task_id)):
        return
    if event == "delegated" and isinstance(agent, str) and agent:
        delegated_agents.setdefault(task_id, set()).add(agent)
    elif event == "accepted":
        closed_tasks.add(task_id)
    elif event == "rejected":
        rejected_tasks.add(task_id)


def harvest_task_state(lines: list[str]):
    """Затравка состояния правила 9(б/в) из HEAD-версии (или любого
    префикса строк) -- (delegated_agents, closed_tasks, rejected_tasks)."""
    delegated_agents: dict[str, set] = {}
    closed_tasks: set = set()
    rejected_tasks: set = set()
    for line in lines:
        obj = _try_parse_obj(line)
        if obj is None:
            continue
        _harvest_line_into(obj.get("event"), obj.get("task_id"), obj.get("agent"),
                           delegated_agents, closed_tasks, rejected_tasks)
    return delegated_agents, closed_tasks, rejected_tasks


def _last_head_ts(head_lines: list[str]):
    """ts ПОСЛЕДНЕЙ строки HEAD-версии (правило 10: монотонность считается
    от неё, а не от максимума по файлу -- журнал append-only, поэтому
    последняя строка HEAD и есть хронологически последняя из старых)."""
    if not head_lines:
        return None
    obj = _try_parse_obj(head_lines[-1])
    if obj is None:
        return None
    return parse_ts(obj.get("ts"))


def check_append_only(staged_lines: list[str], head_lines: list[str]):
    """Правило 1: staged обязана начинаться с head как префикс (существующие
    строки не изменены и не удалены). Возвращает (ok, message)."""
    if len(staged_lines) < len(head_lines):
        return False, (
            f"append-only: staged содержит МЕНЬШЕ строк ({len(staged_lines)}) "
            f"чем HEAD ({len(head_lines)}) -- существующие строки удалены"
        )
    for i, head_line in enumerate(head_lines):
        if staged_lines[i] != head_line:
            return False, (
                f"append-only: строка {i + 1} расходится с HEAD -- "
                "существующие строки нельзя менять, только добавлять в конец"
            )
    return True, ""


def _matrix_d0058_violation(event: str, agent, by: str, obj: dict) -> str | None:
    """Правило 11. Возвращает текст нарушения или None. Применяется ТОЛЬКО
    к accepted (буквальное чтение спеки: "accepted легален, если...";
    rejected несёт "by" без дальнейшей tier/basis-проверки)."""
    if event != "accepted":
        return None
    if agent == "lead":
        return None  # Lead-tier работа: presence "by" уже проверена выше
    if agent not in AGENT_TIER:
        return None  # неизвестный agent -- матрица не определена спекой
    agent_tier = AGENT_TIER[agent]
    by_tier = TIER_ORDER.get(by)
    ok_tier = by_tier is not None and by_tier > TIER_ORDER[agent_tier]
    basis = obj.get("basis")
    ok_basis = basis in BASIS_VALUES
    if ok_tier or ok_basis:
        return None
    return (
        f"D-0058: agent={agent!r} принят by={by!r} (не строго выше яруса "
        f"исполнителя) и нет валидного basis (нужно critic/queued-to-lead)"
    )


def validate_new_lines(new_lines: list[str], head_lines: list[str],
                        now: datetime.datetime) -> list[str]:
    violations: list[str] = []
    seen_task_ids = extract_task_ids(head_lines)
    max_num = max_task_num(seen_task_ids)
    last_ts = _last_head_ts(head_lines)
    now_limit = now + datetime.timedelta(minutes=10)
    delegated_agents, closed_tasks, rejected_tasks = harvest_task_state(head_lines)

    for idx, line in enumerate(new_lines):
        line_no = len(head_lines) + idx + 1
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, TypeError) as e:
            violations.append(f"line {line_no}: невалидный JSON ({e})")
            continue
        if not isinstance(obj, dict):
            violations.append(f"line {line_no}: не JSON-объект")
            continue

        event = obj.get("event")
        task_id = obj.get("task_id")
        agent = obj.get("agent")
        tag = f"line {line_no} event={event!r} task_id={task_id!r}"

        ts = obj.get("ts")
        category = obj.get("category")
        notes = obj.get("notes")

        if not isinstance(ts, str) or not ts:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'ts'")
        if not isinstance(event, str) or not event:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'event'")
        if not isinstance(agent, str) or not agent:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'agent'")
        if not isinstance(category, str) or not category:
            violations.append(f"{tag}: отсутствует/невалидно обязательное поле 'category'")
        if not isinstance(notes, str) or not notes.strip():
            violations.append(f"{tag}: отсутствует/пустое обязательное поле 'notes'")

        if isinstance(event, str) and event and event not in EVENTS:
            violations.append(f"{tag}: 'event' не из enum ({event!r})")

        if event in MODEL_REQUIRED_EVENTS:
            model = obj.get("model")
            if not isinstance(model, str) or not model:
                violations.append(f"{tag}: 'model' обязателен для event={event}")

        if event in TASK_ID_REQUIRED_EVENTS:
            if not isinstance(task_id, str) or not task_id:
                violations.append(f"{tag}: 'task_id' обязателен для event={event}")
            elif not TASK_ID_RE.match(task_id):
                violations.append(f"{tag}: task_id {task_id!r} не соответствует формату t-NNN (3+ цифр)")

        if event == "rejected":
            attempt = obj.get("attempt")
            if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
                violations.append(f"{tag}: 'attempt' обязан быть целым >=1")
            failure_class = obj.get("failure_class")
            if failure_class not in FAILURE_CLASSES:
                violations.append(
                    f"{tag}: 'failure_class' обязан быть одним из {sorted(FAILURE_CLASSES)}"
                )

        if event == "accepted" and agent == "builder":
            witness = obj.get("witness")
            if not isinstance(witness, str) or not witness.strip():
                violations.append(f"{tag}: 'witness' обязателен (непустая строка) для accepted+agent=builder")

        if event == "defect_found":
            ref = obj.get("ref")
            if not isinstance(ref, str) or not ref:
                violations.append(f"{tag}: 'ref' обязателен (непустой) для defect_found")

        if event in ("accepted", "rejected"):
            by = obj.get("by")
            if not isinstance(by, str) or not by:
                violations.append(f"{tag}: 'by' обязателен (непустой) для {event} (матрица D-0058)")
            else:
                mv = _matrix_d0058_violation(event, agent, by, obj)
                if mv:
                    violations.append(f"{tag}: {mv}")

        valid_tid = isinstance(task_id, str) and TASK_ID_RE.match(task_id)
        if event == "delegated" and valid_tid:
            if task_id not in seen_task_ids:
                # (а) новая задача -- обязана быть ровно max+1.
                expected = max_num + 1
                actual = int(TASK_ID_RE.match(task_id).group(1))
                if actual != expected:
                    violations.append(
                        f"{tag}: новизна task_id нарушена -- ожидался t-{expected:03d} (max+1), получен {task_id}"
                    )
            elif task_id in closed_tasks:
                # (г) reopen запрещён -- коллизия = две задачи (D-0060).
                violations.append(
                    f"{tag}: delegated на ЗАКРЫТУЮ задачу {task_id!r} (выше уже есть accepted) -- "
                    "reopen запрещён, коллизия считается двумя задачами (D-0060)"
                )
            else:
                prior_agents = delegated_agents.get(task_id, set())
                if isinstance(agent, str) and agent and agent not in prior_agents:
                    pass  # (б) continuation-диспатч другого яруса -- легально
                else:
                    attempt = obj.get("attempt")
                    valid_attempt = (isinstance(attempt, int) and not isinstance(attempt, bool)
                                      and attempt >= 2)
                    if not (valid_attempt and task_id in rejected_tasks):
                        # (в) не выполнены условия ретрая -> (г) дубль-паттерн t-029
                        violations.append(
                            f"{tag}: повторный delegated тем же agent={agent!r} по task_id={task_id!r} "
                            "без attempt>=2 и существующего выше rejected -- запрещённый дубль "
                            "(класс t-029, D-0060)"
                        )
        elif event in ("accepted", "rejected", "escalated", "defect_found") and valid_tid:
            if task_id not in seen_task_ids:
                violations.append(
                    f"{tag}: task_id {task_id!r} не ссылается ни на что существующее выше в файле"
                )

        _harvest_line_into(event, task_id, agent, delegated_agents, closed_tasks, rejected_tasks)

        parsed_ts = parse_ts(ts) if isinstance(ts, str) else None
        if isinstance(ts, str) and ts and parsed_ts is None:
            violations.append(f"{tag}: ts {ts!r} не ISO-формат без таймзоны")
        if parsed_ts is not None:
            if last_ts is not None and parsed_ts < last_ts:
                violations.append(
                    f"{tag}: ts не монотонен -- {parsed_ts.isoformat()} раньше предыдущего {last_ts.isoformat()}"
                )
            if parsed_ts > now_limit:
                violations.append(
                    f"{tag}: ts {ts!r} позже now+10мин ({now_limit.isoformat()}) -- "
                    "повествовательное будущее (F-29)"
                )
            last_ts = parsed_ts

        if valid_tid:
            seen_task_ids.add(task_id)
            num = int(TASK_ID_RE.match(task_id).group(1))
            if num > max_num:
                max_num = num

    return violations


def decide(staged_text: str | None, head_text: str | None,
           now: datetime.datetime | None = None) -> tuple[int, list[str]]:
    """Чистое решение гейта -- тестируется без git (см. tools/test_journal_validator.py)."""
    now = now or datetime.datetime.now()
    staged_lines = split_lines(staged_text)
    head_lines = split_lines(head_text)
    ok, msg = check_append_only(staged_lines, head_lines)
    if not ok:
        return 1, [msg]
    new_lines = staged_lines[len(head_lines):]
    violations = validate_new_lines(new_lines, head_lines, now)
    if violations:
        return 1, violations
    return 0, []


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def is_journal_staged(journal_path: str = JOURNAL_PATH) -> bool:
    proc = _git("diff", "--cached", "--name-only")
    return journal_path in proc.stdout.splitlines()


def get_staged_text(journal_path: str = JOURNAL_PATH) -> str:
    proc = _git("show", f":{journal_path}")
    return proc.stdout if proc.returncode == 0 else ""


def get_head_text(journal_path: str = JOURNAL_PATH) -> str:
    proc = _git("show", f"HEAD:{journal_path}")
    return proc.stdout if proc.returncode == 0 else ""


def _main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not is_journal_staged():
        return 0  # правило: файл не staged -> молча exit 0
    staged_text = get_staged_text()
    head_text = get_head_text()
    now = datetime.datetime.now()
    code, violations = decide(staged_text, head_text, now)
    if code:
        print(f"journal_validator: {JOURNAL_PATH} FAILED validation:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    """Внешняя граница: любое исключение (не FAIL валидации, а крэш самого
    валидатора) -> exit 2 с трейсбеком, fail-closed, как mechanism_gate."""
    try:
        return _main(argv)
    except Exception:
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    sys.exit(main())
