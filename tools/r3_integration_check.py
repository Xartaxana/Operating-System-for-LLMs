"""r3_integration_check -- детерминированный информатор чека 2 (Р-О5
ремедиации №8 + вход D-0110, docs/tasks/2026-08-25_kopilka-wave-spec.md
раздел "БИЛДЕР SE").

ЧТО ДЕЛАЕТ (без AI-суждения, только git и журнал):
    1. `git log --numstat` за окно (--since, дефолт "24 hours ago") --
       коммиты этого окна с суммой изменённых строк (add+del по
       numstat) > LARGE_COMMIT_THRESHOLD_LINES (100).
    2. Для каждого такого КРУПНОГО коммита -- поиск критик-следа в
       logs/routing-log.jsonl: delegated agent=critic, ЛИБО accepted
       basis=critic, ЛИБО подстрока "critic:" в notes accepted -- в
       окне ts МЕЖДУ СОСЕДНИМИ КОММИТАМИ (предыдущий коммит окна ..
       этот коммит; для самого раннего коммита окна нижняя граница --
       ближайший коммит СТРОГО ДО --since, либо неограничена, если
       такого нет). Это ЭВРИДистика (ts-окно, а не причинная связь) --
       печатается КАК эвристика, никогда как факт.
    3. Печать: коммиты без найденного следа -- КАНДИДАТЫ для чека 2
       ("кандидат, не вердикт -- чек 2 решает", Р-О5); коммиты со
       следом -- сам след печатается для чтения глазами. Отдельно --
       счёт МАЛЫХ коммитов окна (<=100 строк) как ВХОДНЫЕ ДАННЫЕ
       кумулятива D-0110; семантика "одна ли тема у серии мелких
       коммитов" НЕ автоматизируется этим скриптом -- решение Lead.

EXIT: ВСЕГДА 0 -- это информатор, не гейт (Р-О5: блок-гейт срабатывает
только по ЗАФИКСИРОВАННОМУ РЕЦИДИВУ, не по каждому прогону чека 2).
Даже внутренняя ошибка (git недоступен, журнал повреждён целиком)
печатается в stderr и НЕ поднимает код выхода -- намеренно, чтобы этот
скрипт никогда не стал случайным гейтом при вызове из session-handoff.

ГРАНИЦЫ ЧТЕНИЯ: скрипт ТОЛЬКО ЧИТАЕТ git (`git log`, read-only) и файл
logs/routing-log.jsonl (read-only). Никаких записей -- ни в журнал, ни
в git, ни куда-либо ещё.

ДИЗАЙН-РЕШЕНИЯ БИЛДЕРА (спека явно зовёт весь механизм эвристикой;
ниже -- конкретные развилки внутри неё, не покрытые спекой дословно):
    - "сосед-коммит" для нижней границы окна ts -- ЛЮБОЙ коммит окна
      (не только крупный), в хронологическом порядке; это точнее, чем
      "предыдущий крупный", т.к. не расширяет окно поиска через
      несвязанные промежуточные коммиты.
    - бинарный файл в numstat ("-\t-\tpath") -- вклад 0 строк (число
      строк неизвестно, не "много").
    - подстрока "critic:" в notes ищется дословно, НО форма
      "critic:<пробелы>skipped" (регистр неважен) -- АНТИ-след, не
      считается находкой (Ф2-фикс t-613, вердикт критика волны:
      живой прецедент t-593 печатал "critic: skipped" как НАЙДЕН,
      хотя это запись об ОТСУТСТВИИ критика); валидная S5-форма
      "critic:t-NNN" и любое другое НЕ-skipped вхождение считаются
      следом как раньше; смешанная строка (анти-след + валидный
      токен) -- МАТЧ (валидный токен перевешивает). Печать следа
      несёт фрагмент notes ±40 символов вокруг сработавшего
      вхождения (санитайз переводов строк) -- см.
      _find_critic_notes_match.
    - границы ts-окна ВКЛЮЧИТЕЛЬНЫ с обеих сторон.
    - таймстемпы сравниваются КАК СТРОКИ (ISO, локальное время без
      таймзоны -- формат журнала, CLAUDE.md; git-даты запрашиваются
      тем же форматом через --date=format-local, чтобы сравнение было
      корректным лексикографически без парсинга дат в Python).

CLI:
    python tools/r3_integration_check.py [--since <git-дата>]
        [--journal PATH] [--threshold N]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:  # безопасность вывода на Windows-консолях с не-UTF8 codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

LARGE_COMMIT_THRESHOLD_LINES = 100
COMMIT_MARKER = "COMMIT\x1f"
_FIELD_SEP = "\x1f"
DEFAULT_SINCE = "24 hours ago"
DEFAULT_JOURNAL_REL = "logs/routing-log.jsonl"


# ---------------------------------------------------------------------
# Чистые функции разбора -- тестируются на фикстурных строках, БЕЗ git.
# ---------------------------------------------------------------------


def _safe_int(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        return 0


def parse_git_log_numstat(raw: str) -> List[Dict[str, Any]]:
    """Разбирает вывод
    `git log --numstat --pretty=format:COMMIT<0x1f>%H<0x1f>%ad --reverse`
    (порядок хронологический задаёт вызывающий флагом --reverse, эта
    функция сохраняет порядок строк как есть).

    Возвращает список {"hash": str, "ts": str, "lines_changed": int} --
    по одной записи на коммит, в порядке появления заголовков в raw.

    Края: коммит без numstat-строк вовсе (merge-коммит без -m/--first-
    parent, пустой коммит) -- lines_changed=0, запись всё равно
    создаётся. Бинарный файл ("-\\t-\\tpath") -- вклад 0. Мусорные
    строки до первого заголовка COMMIT -- игнорируются. Пустой raw ->
    пустой список (край "пустое окно")."""
    commits: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in raw.splitlines():
        if line.startswith(COMMIT_MARKER):
            if current is not None:
                commits.append(current)
            parts = line[len(COMMIT_MARKER):].split(_FIELD_SEP)
            commit_hash = parts[0] if len(parts) > 0 else ""
            ts = parts[1] if len(parts) > 1 else ""
            current = {"hash": commit_hash, "ts": ts, "lines_changed": 0}
            continue
        if current is None:
            continue  # строка до первого заголовка -- не наш формат
        stripped = line.strip()
        if not stripped:
            continue  # пустая строка-разделитель git между блоками
        fields = line.split("\t")
        if len(fields) != 3:
            continue  # не numstat-пара (край: коммит без numstat-пар)
        added_raw, deleted_raw, _path = fields
        added = 0 if added_raw == "-" else _safe_int(added_raw)
        deleted = 0 if deleted_raw == "-" else _safe_int(deleted_raw)
        current["lines_changed"] += added + deleted
    if current is not None:
        commits.append(current)
    return commits


_CRITIC_MARKER = "critic:"
_NOTES_FRAGMENT_RADIUS = 40  # символов вокруг совпадения, печать следа (Ф2)

# Анти-след (Ф2 фикса t-613, вердикт критика волны): "critic: skipped"
# (в любом регистре, пробел после ":" не обязателен) -- буквальная
# запись об ОТСУТСТВИИ критика, не о его следе. Живой прецедент:
# t-593 отметил "critic: skipped -- концессия резерва" в notes
# accepted-события 900-строчного коммита -- до фикса это печаталось
# как НАЙДЕН, хотя критика не было вовсе.
_CRITIC_SKIP_AFTER_RE = re.compile(r"\s*skipped", re.IGNORECASE)


def _find_critic_notes_match(notes: str) -> "tuple[bool, Optional[str]]":
    """Сканирует ВСЕ вхождения буквальной подстроки "critic:" в notes
    слева направо. Вхождение вида "critic:<пробелы>skipped" (регистр
    неважен) -- анти-след, пропускается. Первое вхождение, которое НЕ
    анти-след (в т.ч. валидная S5-форма "critic:t-NNN"), даёт матч:
    возвращает (True, фрагмент ±40 символов вокруг вхождения, переводы
    строк заменены пробелом). Если ВСЕ вхождения -- анти-след (или
    вхождений нет вовсе) -- (False, None): смешанная строка вида
    "critic: skipped ... critic:t-593" даёт МАТЧ (валидный токен
    перевешивает анти-след), т.к. сканирование продолжается после
    пропуска анти-следа."""
    start = 0
    while True:
        idx = notes.find(_CRITIC_MARKER, start)
        if idx == -1:
            return False, None
        after = notes[idx + len(_CRITIC_MARKER):]
        if _CRITIC_SKIP_AFTER_RE.match(after):
            start = idx + len(_CRITIC_MARKER)
            continue  # анти-след -- ищем следующее вхождение
        frag_start = max(0, idx - _NOTES_FRAGMENT_RADIUS)
        frag_end = min(len(notes), idx + len(_CRITIC_MARKER) + _NOTES_FRAGMENT_RADIUS)
        fragment = notes[frag_start:frag_end].replace("\n", " ").replace("\r", " ")
        return True, fragment


def find_critic_trail(
    journal_lines: Iterable[str],
    window_start: Optional[str],
    window_end: str,
) -> List[Dict[str, Any]]:
    """Ищет критик-след в строках журнала (каждая -- одна JSON-строка
    routing-log.jsonl) в окне ts [window_start, window_end] (обе
    границы включительны; window_start=None -- нижняя граница не
    ограничена). Совпадение -- любое из:
        - event == "delegated" and agent == "critic"
        - event == "accepted" and basis == "critic"
        - event == "accepted" and валидное (не анти-след) вхождение
          "critic:" в notes -- см. _find_critic_notes_match (Ф2)
    Таймстемпы сравниваются как строки (формат журнала -- ISO
    локальное время без таймзоны, лексикографически сортируемый).

    Возвращает список КОПИЙ событий; у каждой добавлен служебный ключ
    "_notes_fragment" (фрагмент notes вокруг сработавшего совпадения,
    либо None, если матч дала не notes-эвристика) -- печатается в
    build_report, чтобы читатель отличал форму совпадения (Ф2, п.2).

    Края: битая JSON-строка -- пропуск (не считается ни находкой, ни
    её отсутствием, не роняет разбор -- край DoD "битые JSON-строки
    журнала"); строка без ts или ts не строка -- пропуск (не может
    быть размещена в окне); пустой журнал / все события вне окна ->
    пустой список (край "журнал без критик-событий"); notes вида
    "critic: skipped" -- АНТИ-след, не считается находкой (Ф2)."""
    matches: List[Dict[str, Any]] = []
    for raw_line in journal_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # битая строка -- пропуск, не ошибка разбора
        if not isinstance(obj, dict):
            continue
        ts = obj.get("ts")
        if not isinstance(ts, str) or not ts:
            continue
        if window_start is not None and ts < window_start:
            continue
        if ts > window_end:
            continue
        event = obj.get("event")
        agent = obj.get("agent")
        notes = obj.get("notes")
        notes_text = notes if isinstance(notes, str) else ""
        is_critic_delegated = event == "delegated" and agent == "critic"
        is_basis_critic = event == "accepted" and obj.get("basis") == "critic"
        notes_matched, notes_fragment = (
            _find_critic_notes_match(notes_text) if event == "accepted" else (False, None)
        )
        if is_critic_delegated or is_basis_critic or notes_matched:
            enriched = dict(obj)
            enriched["_notes_fragment"] = notes_fragment
            matches.append(enriched)
    return matches


def classify_commits(
    commits: List[Dict[str, Any]], threshold: int = LARGE_COMMIT_THRESHOLD_LINES
) -> Dict[str, List[Dict[str, Any]]]:
    """Делит хронологически упорядоченный список коммитов (см.
    parse_git_log_numstat) на "large" (lines_changed > threshold) и
    "small" (<= threshold). Возвращает {"large": [...], "small": [...]}
    -- каждый элемент large дополнительно несёт "window_start" (ts
    предыдущего коммита СПИСКА commits, любого размера, либо None для
    самого первого) и "window_end" (свой ts)."""
    large: List[Dict[str, Any]] = []
    small: List[Dict[str, Any]] = []
    prev_ts: Optional[str] = None
    for commit in commits:
        if commit["lines_changed"] > threshold:
            enriched = dict(commit)
            enriched["window_start"] = prev_ts
            enriched["window_end"] = commit["ts"]
            large.append(enriched)
        else:
            small.append(commit)
        prev_ts = commit["ts"]
    return {"large": large, "small": small}


# ---------------------------------------------------------------------
# Обвязка ввода-вывода -- git subprocess (read-only) и чтение журнала.
# ---------------------------------------------------------------------


def _run_git(args: List[str]) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def fetch_window_commits(since: str) -> List[Dict[str, Any]]:
    """git log --numstat, read-only, хронологический порядок
    (--reverse)."""
    raw = _run_git(
        [
            "log",
            f"--since={since}",
            "--numstat",
            "--date=format-local:%Y-%m-%dT%H:%M:%S",
            f"--pretty=format:{COMMIT_MARKER}%H{_FIELD_SEP}%ad",
            "--reverse",
        ]
    )
    return parse_git_log_numstat(raw)


def fetch_boundary_ts(since: str) -> Optional[str]:
    """ts ближайшего коммита СТРОГО ДО --since (нижняя граница окна
    самого раннего коммита окна). None, если такого коммита нет
    (--since раньше первого коммита репозитория)."""
    raw = _run_git(
        [
            "log",
            "-1",
            f"--before={since}",
            "--date=format-local:%Y-%m-%dT%H:%M:%S",
            "--pretty=format:%ad",
        ]
    )
    ts = raw.strip()
    return ts or None


def read_journal_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


# ---------------------------------------------------------------------
# Отчёт.
# ---------------------------------------------------------------------


def build_report(
    since: str,
    commits: List[Dict[str, Any]],
    journal_lines: List[str],
    threshold: int = LARGE_COMMIT_THRESHOLD_LINES,
    boundary_ts: Optional[str] = None,
) -> str:
    classified = classify_commits(commits, threshold=threshold)
    large = classified["large"]
    small = classified["small"]
    # window_start=None у самого первого large-коммита списка commits
    # означает "нет предыдущего коммита В ЭТОМ СПИСКЕ" -- подставляем
    # boundary_ts (ближайший коммит до --since), если он есть.
    lines: List[str] = []
    lines.append("=== r3_integration_check (Р-О5/D-0110) ===")
    lines.append(f'окно: --since="{since}"')
    lines.append(
        f"коммитов в окне: {len(commits)} "
        f"(крупных >{threshold} строк: {len(large)}, малых <= {threshold}: {len(small)})"
    )
    lines.append("")
    lines.append(
        f"--- КРУПНЫЕ КОММИТЫ (>{threshold} строк, потенциальные адресаты чека 2) ---"
    )
    if not large:
        lines.append("  (нет крупных коммитов в окне)")
    for commit in large:
        window_start = commit["window_start"]
        if window_start is None:
            window_start = boundary_ts  # может остаться None -- неограничено
        window_end = commit["window_end"]
        window_label = f"[{window_start if window_start is not None else '-inf'} .. {window_end}]"
        short_hash = commit["hash"][:8] if commit["hash"] else "?"
        lines.append(
            f"{short_hash} ts={commit['ts']} сумма={commit['lines_changed']}"
        )
        trail = find_critic_trail(journal_lines, window_start, window_end)
        if trail:
            lines.append(
                f"  критик-след НАЙДЕН ({len(trail)} событие(й) в окне {window_label}, эвристика по ts):"
            )
            for ev in trail:
                lines.append(
                    f"    - event={ev.get('event')} agent={ev.get('agent')} "
                    f"basis={ev.get('basis')} ts={ev.get('ts')}"
                )
                fragment = ev.get("_notes_fragment")
                if fragment:
                    lines.append(f'      notes-фрагмент: "...{fragment}..."')
        else:
            lines.append(f"  критик-след НЕ НАЙДЕН в окне {window_label}")
            lines.append(
                "  -> КАНДИДАТ, не вердикт -- чек 2 решает "
                '(эвристика: agent=critic delegated / basis=critic accepted / '
                'подстрока "critic:" в notes accepted, окно по ts между соседними коммитами)'
            )
    lines.append("")
    lines.append(f"--- МАЛЫЕ КОММИТЫ окна (<= {threshold} строк): {len(small)} ---")
    lines.append(
        '  входные данные кумулятива D-0110 ("одна ли тема" у серии малых '
        "коммитов -- решение Lead, этим скриптом НЕ автоматизируется)"
    )
    for commit in small:
        short_hash = commit["hash"][:8] if commit["hash"] else "?"
        lines.append(f"  {short_hash} ts={commit['ts']} сумма={commit['lines_changed']}")
    lines.append("")
    lines.append("exit: 0 (информатор, не гейт -- Р-О5: гейт только по рецидиву)")
    return "\n".join(lines)


# ---------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Детерминированный информатор чека 2 (Р-О5): крупные коммиты "
            "окна без найденного критик-следа в logs/routing-log.jsonl. "
            "Читает git и журнал, ничего не пишет. Exit всегда 0."
        )
    )
    parser.add_argument(
        "--since",
        default=DEFAULT_SINCE,
        help=f'нижняя граница окна, формат git --since (дефолт "{DEFAULT_SINCE}")',
    )
    parser.add_argument(
        "--journal",
        default=None,
        help=f"путь к журналу (дефолт {DEFAULT_JOURNAL_REL} от корня репо)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=LARGE_COMMIT_THRESHOLD_LINES,
        help=f"порог 'крупного' коммита в строках (дефолт {LARGE_COMMIT_THRESHOLD_LINES})",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = _repo_root()
        journal_path = (
            Path(args.journal) if args.journal else repo_root / DEFAULT_JOURNAL_REL
        )
        commits = fetch_window_commits(args.since)
        boundary_ts = fetch_boundary_ts(args.since)
        journal_lines = read_journal_lines(journal_path)
        report = build_report(
            args.since,
            commits,
            journal_lines,
            threshold=args.threshold,
            boundary_ts=boundary_ts,
        )
        print(report)
    except Exception as exc:  # noqa: BLE001 -- информатор никогда не гейт
        print(
            f"r3_integration_check: внутренняя ошибка, отчёт не построен: {exc}",
            file=sys.stderr,
        )
    return 0  # ВСЕГДА -- информатор, не гейт (Р-О5)


if __name__ == "__main__":
    sys.exit(main())
