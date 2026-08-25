r"""docs/tasks/2026-08-25_manifest-form-probe.py -- ОДНОРАЗОВЫЙ замер
трёх чисел, которые резервный ярус сам назвал как способные отменить
его проектное решение про given-манифест tools/dispatch_gate.py
(докстринг задачи: 2026-08-25, диспетчер -- резерв). Форма -- по
образцу docs/tasks/2026-08-20_nodeA-keyrun.py (одноразовый скрипт,
позитив + негативный контроль через флаг, а не постоянный CLI-инструмент
tools/).

ЭТОТ СКРИПТ ТОЛЬКО ИЗМЕРЯЕТ. Интерпретация (что из чисел следует для
проектного решения) -- чужая работа, здесь её нет, кроме обязательного
раздела "ЧЕГО ЭТОТ ЗАМЕР НЕ ПОКАЗЫВАЕТ" в отдельном md-отчёте.

ТРИ ВОПРОСА (дословно из спеки):
  З1 -- какая доля ПИШУЩИХ диспатчей несёт совпадение MANIFEST_GIVEN_RE
       ТОЛЬКО в несекционной прозе, а не в помеченной декларации.
  З2 -- раскладка отсутствующих (missing) путей слоя GIVEN_PATH по РОЛИ
       токена в промпте (INLINE-перечисление / POINTER-цель / OTHER).
  З3 -- reject-доли pointer_form vs inline_form given-деклараций
       пишущих диспатчей, по журналу.

РЕГЕКСЫ И ХЕЛПЕРЫ -- ИМПОРТИРУЮТСЯ из tools/dispatch_gate.py и
tools/warn_density.py, НЕ копируются (AK2 спеки): копия регекса
разошлась бы с живым гейтом молча -- отдельный класс дефекта в этом
репо (см. докстринг tools/dispatch_gate.py, класс "сторож не отличает
своё от чужого", и историю OWNS_WORD_RE/MANIFEST_GIVEN_RE в нём же).

РЕШЕНИЯ, ПРИНЯТЫЕ САМОСТОЯТЕЛЬНО ИЗ-ЗА МОЛЧАНИЯ СПЕКИ (перечислены
здесь И в отчёте -- по требованию задачи это недоработка диспетчера,
не билдера, честно называется вслух, а не молча реализуется):

  Р-1 "пишущий диспатч" (используется в З1/З3): спека не даёт формулы.
      Взято ТО ЖЕ условие, что decide()'s B2-manifest ветка реально
      применяет к манифест-требованию: subagent_type == "builder" И
      _region_aware_is_write(prompt) -- т.е. РОВНО та популяция,
      которую живой гейт заставляет нести given/owns. Для З2 популяция
      ДРУГАЯ и в спеке НЕ нуждается в этом решении: слой GIVEN_PATH
      живёт на матчере "Task|Agent" БЕЗ фильтра по subagent_type/
      is_write (см. tools/warn_layers.json registry) -- З2 поэтому
      берёт ВСЕ Task/Agent-диспатчи окна, не только "пишущие".

  Р-2 repo_root для find_missing_given_paths(): в живом хуке это
      payload["cwd"] (текущий рабочий каталог сессии в момент
      диспатча) -- транскрипт tool_use-записи этого поля не несёт.
      Единственный деплой этого корпуса -- сам этот репозиторий,
      поэтому взят REPO_ROOT (константа модуля) как repo_root для
      ВСЕХ диспатчей без исключения.

  Р-3 "два предшествующих окна" (З3): границы в logs/warn_density.jsonl
      НЕ образуют неперекрывающийся хронологический ряд -- запись
      "окна №8" (start=2026-08-14T12:12:34+02:00,
      end=2026-08-20T13:51:07+02:00) почти ЦЕЛИКОМ покрывает запись 1
      (тот же start, end на час раньше). "Предшествующих" здесь взято
      как "предшествующих ПО ПОРЯДКУ ЗАПИСИ В ФАЙЛЕ" (появившихся в
      сайдкаре раньше первого вхождения границ окна №8) -- это записи
      1 и 2 сайдкара, с ДРУГИМИ, не совпадающими с #8 границами.

  Р-4 З1 не привязан спекой ни к одному окну явно (в отличие от З2,
      которое явно называет "окно №8"). Взято окно №8 как основное
      (тот же контур, что и остальные два вопроса) + доп. строка по
      ВСЕМУ корпусу без фильтра по времени (не заменяет основной ответ,
      просто дешёвый бонус при уже собранной популяции).

  Р-5 классификатор З3 (pointer_form/inline_form): спека даёт формулу
      буквально ("<2 путь-токенов И нет перечня строк" / "≥2
      перечисленных элемента"), но не говорит, где считать путь-токены
      (весь промпт или секция given) и что считается "перечнем строк".
      Взято: N = len(extract_given_candidates(prompt)) по ВСЕМУ
      промпту (та же функция, что и остальной код), "перечень строк" =
      >=2 буллет/номерных строк ВНУТРИ секции given (та же форма,
      что _is_owns_continuation_line применяет к owns).

  Р-6 связывание (З3): спека допускает ТОЛЬКО worker_ref-извлечение
      "если id воркера извлекается из транскрипта" -- реализовано ТОЧНЫМ
      join через <session>/subagents/agent-<id>.meta.json поле
      "toolUseId" (== id самого tool_use Agent-записи в родительском
      транскрипте) -- это И ЕСТЬ "извлечение id воркера из
      транскрипта", просто через доступный ключ соединения, а не
      напрямую. ts+description -- запасной путь (окно ±15 минут,
      подстрока description в notes), используется, только когда
      meta-join не дал результата.

  Р-7 "корпус окна пуст" (края): расписано в спеке как CLI-семантика
      одного окна (как у warn_density). Здесь ОДИН прогон считает ТРИ
      окна из общей популяции диспатчей, поэтому "корпус пуст" сведён к
      буквальному "--transcripts существует, файлов 0" (проверяется
      ОДИН раз, до всего остального); "диспатчей 0" для КОНКРЕТНОГО
      окна печатается как факт ВНУТРИ раздела этого окна, без выхода.

Коды выхода: 0 -- прогон состоялся и встроенная фикстура сошлась;
1 -- фикстура (AK5) НЕ сошлась (ДЕФЕКТ ИНСТРУМЕНТА) ИЛИ вызван
--negative-control (сознательно должен падать -- см. AK5).

CLI:
    python docs/tasks/2026-08-25_manifest-form-probe.py
    python docs/tasks/2026-08-25_manifest-form-probe.py --negative-control
    python docs/tasks/2026-08-25_manifest-form-probe.py --transcripts DIR
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # безопасность вывода на Windows-консолях с не-UTF8 codepage (та же
    # форма, что tools/warn_density.py -- CLAUDE.md п.9).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.dispatch_gate import (  # noqa: E402
    MANIFEST_GIVEN_RE,
    OWNS_WORD_RE,
    _MANIFEST_SECTION_HEADER_RE,
    GIVEN_ABS_WIN_PATH_RE,
    GIVEN_REPO_REL_PATH_RE,
    extract_given_candidates,
    find_missing_given_paths,
    _region_aware_is_write,
    _section_map,
    _SECTION_BULLET_PREFIX_RE,
    _SECTION_NUMBERED_PREFIX_RE,
)
from tools.warn_density import (  # noqa: E402
    enumerate_corpus_files,
    is_sidechain_file,
    parse_transcript_ts,
    parse_window_bound,
    _default_transcripts_dir,
    ArgError,
)

DEFAULT_TRANSCRIPTS = _default_transcripts_dir()
DEFAULT_JOURNAL = REPO_ROOT / "logs" / "routing-log.jsonl"

# POINTER-триггер "глагол чтения" -- дословный список спеки (З2, метод):
# «прочти», «читай», «read», «см.», «носитель», «спека».
READ_VERB_RE = re.compile(r"прочти|читай|\bread\b|см\.|носитель|спека", re.IGNORECASE)

# Границы окон -- дословно из ДАНО спеки / logs/warn_density.jsonl (Р-3).
WINDOW_8 = ("#8 (основное)", "2026-08-14T12:12:34+02:00", "2026-08-20T13:51:07+02:00")
WINDOW_PREV_B = ("prev-B (сайдкар, запись 2)", "2026-08-20T12:51:07+02:00", "2026-08-20T23:06:37+02:00")
WINDOW_PREV_A = ("prev-A (сайдкар, запись 1)", "2026-08-14T12:12:34+02:00", "2026-08-20T12:51:07+02:00")
WINDOWS_Z3 = [WINDOW_8, WINDOW_PREV_B, WINDOW_PREV_A]

SIDECAR_GIVEN_PATH_CALLS_WINDOW8 = 27  # logs/warn_density.jsonl, запись за окно №8


# ---------------------------------------------------------------------------
# Время окна -- попытка переиспользовать parse_window_bound (Р-7 докстринга
# модуля тоже, "переиспользуй оттуда"), явная фиксация несовпадения формы.
# ---------------------------------------------------------------------------

def resolve_window_bound(raw: str) -> Tuple[datetime, str]:
    """Возвращает (aware datetime, находка). parse_window_bound() ждёт
    ЛОКАЛЬНОЕ НАИВНОЕ ISO без зоны -- границы окна №8 несут явное
    смещение (+02:00) и ОБЯЗАНЫ дать ArgError; это ожидаемо и
    печатается находкой, а не подгоняется молча (край спеки)."""
    try:
        dt = parse_window_bound(raw)
        return dt, f"parse_window_bound() принял {raw!r} напрямую (неожиданно -- проверь форму)"
    except ArgError as exc:
        dt2 = datetime.fromisoformat(raw)
        return dt2, (
            f"parse_window_bound() отклонил {raw!r} ({exc}) -- ожидаемо (несёт offset +02:00, "
            f"инструмент ждёт наивную локальную форму); приведено вручную через "
            f"datetime.fromisoformat() (сохраняет абсолютный момент времени)"
        )


# ---------------------------------------------------------------------------
# Извлечение диспатчей (Task/Agent tool_use) из корпуса -- ОДИН проход.
# ---------------------------------------------------------------------------

@dataclass
class Dispatch:
    file: Path
    line_no: int
    ts: datetime
    tool_use_id: str
    subagent_type: Optional[str]
    description: Optional[str]
    prompt: str


def collect_corpus(files: List[Path]) -> Tuple[List[Dispatch], List[datetime], Dict[str, int], int, int]:
    """Единый проход по ВСЕМ файлам корпуса. Возвращает:
    (main-диспатчи, ts всех Task/Agent-вызовов В SIDECHAIN-файлах
    [невидимые для измерения, AK4], счётчики skip, всего строк JSONL,
    битых строк)."""
    dispatches: List[Dispatch] = []
    sidechain_ts: List[datetime] = []
    skip_counts: Dict[str, int] = {}

    def bump(reason: str) -> None:
        skip_counts[reason] = skip_counts.get(reason, 0) + 1

    total_lines_seen = 0
    broken_lines = 0

    for f in files:
        is_side = is_sidechain_file(f)
        try:
            fh = open(f, "r", encoding="utf-8-sig", errors="replace", newline=None)
        except OSError:
            bump("файл не открылся")
            continue
        with fh:
            for line_no, raw_ln in enumerate(fh, start=1):
                ln = raw_ln.strip()
                if not ln:
                    continue
                total_lines_seen += 1
                try:
                    rec = json.loads(ln)
                except json.JSONDecodeError:
                    broken_lines += 1
                    bump("битая строка JSONL (json.JSONDecodeError)")
                    continue
                if not isinstance(rec, dict):
                    broken_lines += 1
                    bump("строка не JSON-объект")
                    continue
                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                ts = parse_transcript_ts(rec.get("timestamp"))
                for item in content:
                    if not isinstance(item, dict) or item.get("type") != "tool_use":
                        continue
                    if item.get("name") not in ("Task", "Agent"):
                        continue
                    if is_side:
                        if ts is not None:
                            sidechain_ts.append(ts)
                        continue
                    if ts is None:
                        bump("диспатч без времени (timestamp не распознан)")
                        continue
                    tool_use_id = item.get("id")
                    if not isinstance(tool_use_id, str) or not tool_use_id:
                        bump("tool_use без строкового id")
                        continue
                    inp = item.get("input")
                    if not isinstance(inp, dict):
                        bump("input не dict")
                        continue
                    if "prompt" not in inp:
                        bump("запись без поля промпта")
                        continue
                    prompt_raw = inp.get("prompt")
                    if not isinstance(prompt_raw, str):
                        bump("промпт не-строка")
                        continue
                    subagent_type = inp.get("subagent_type")
                    description = inp.get("description")
                    dispatches.append(Dispatch(
                        file=f, line_no=line_no, ts=ts, tool_use_id=tool_use_id,
                        subagent_type=subagent_type if isinstance(subagent_type, str) else None,
                        description=description if isinstance(description, str) else None,
                        prompt=prompt_raw,
                    ))
    return dispatches, sidechain_ts, skip_counts, total_lines_seen, broken_lines


def in_window(ts: datetime, start: datetime, end: datetime) -> bool:
    # полуоткрытый интервал -- та же семантика, что tools/warn_density.py.
    return start <= ts < end


def is_writing_dispatch(d: Dispatch) -> bool:
    # Р-1: builder + is_write -- РОВНО популяция decide()'s B2-manifest.
    return d.subagent_type == "builder" and _region_aware_is_write(d.prompt)


# ---------------------------------------------------------------------------
# З1 -- классификация MANIFEST_GIVEN_RE совпадений построчно.
# ---------------------------------------------------------------------------

def _line_offsets(prompt: str) -> List[int]:
    offsets = []
    pos = 0
    for l in prompt.splitlines(keepends=True):
        offsets.append(pos)
        pos += len(l)
    return offsets


def _line_index(offsets: List[int], pos: int) -> int:
    return bisect.bisect_right(offsets, pos) - 1


def classify_z1(prompt: str) -> Tuple[str, List[Tuple[str, str]]]:
    matches = list(MANIFEST_GIVEN_RE.finditer(prompt))
    if not matches:
        return "none", []
    lines = prompt.splitlines(keepends=True)
    offsets = _line_offsets(prompt)
    has_section = False
    has_prose = False
    examples: List[Tuple[str, str]] = []
    for m in matches:
        idx = _line_index(offsets, m.start())
        line = lines[idx] if 0 <= idx < len(lines) else ""
        if _MANIFEST_SECTION_HEADER_RE.match(line):
            has_section = True
            examples.append(("SECTION", line.strip()[:90]))
        else:
            has_prose = True
            examples.append(("PROSE", line.strip()[:90]))
    cls = "section" if has_section else "prose_only"
    return cls, examples


# ---------------------------------------------------------------------------
# З2 -- роль отсутствующего токена (INLINE / POINTER / OTHER).
# ---------------------------------------------------------------------------

def _contiguous_span(sections: List[str], idx: int) -> Tuple[int, int]:
    lo = idx
    while lo > 0 and sections[lo - 1] == sections[idx]:
        lo -= 1
    hi = idx
    while hi + 1 < len(sections) and sections[hi + 1] == sections[idx]:
        hi += 1
    return lo, hi


def _token_qualifying_position(prompt: str, tok: str, offsets: List[int], sections: List[str]):
    """Позиция токена, которая его "оправдывает" (лежит вне owns --
    та же логика, что find_missing_given_paths применил через
    _tokens_outside_owns_section, ЧТОБЫ токен вообще остался в missing).
    Несколько occurrences -- берём ПЕРВОЕ квалифицирующее (левее)."""
    for pattern in (GIVEN_ABS_WIN_PATH_RE, GIVEN_REPO_REL_PATH_RE):
        for m in pattern.finditer(prompt):
            if m.group(0) != tok:
                continue
            idx = _line_index(offsets, m.start())
            sec = sections[idx] if idx >= 0 else "none"
            if sec != "owns":
                return m.start(), sec
    pos = prompt.find(tok)
    if pos == -1:
        return None, None
    idx = _line_index(offsets, pos)
    sec = sections[idx] if idx >= 0 else "none"
    return pos, sec


def classify_z2_token(
    prompt: str, tok: str, offsets: List[int], sections: List[str],
    lines: List[str], all_candidate_tokens: List[str],
) -> Tuple[str, str]:
    """Решающее дерево (реализация формулировки спеки, дословно в
    докстринге модуля Р-... нет отдельного номера -- формула самой
    задачи, не придумана здесь):
      1. строка токена несёт глагол чтения -> POINTER (приоритет).
      2. токен вне какой-либо секции манифеста (section == "none")
         -> POINTER.
      3. токен внутри секции манифеста, той же секции >=2 путь-токена
         -> INLINE.
      4. токен внутри секции манифеста, единственный там -> POINTER.
      5. иначе -> OTHER (защитный случай, спекой явно требуется
         перечислить поштучно, если встретится)."""
    pos, sec = _token_qualifying_position(prompt, tok, offsets, sections)
    if pos is None:
        return "OTHER", "(повторный поиск не нашёл токен в тексте -- см. отчёт)"
    idx = _line_index(offsets, pos)
    line_text = lines[idx] if 0 <= idx < len(lines) else ""
    excerpt = line_text.strip()[:110]
    if READ_VERB_RE.search(line_text):
        return "POINTER", excerpt
    if sec == "none":
        return "POINTER", excerpt
    lo, hi = _contiguous_span(sections, idx)
    count_in_span = 0
    for other_tok in all_candidate_tokens:
        opos = prompt.find(other_tok)
        if opos == -1:
            continue
        oidx = _line_index(offsets, opos)
        if lo <= oidx <= hi:
            count_in_span += 1
    if count_in_span >= 2:
        return "INLINE", excerpt
    if count_in_span == 1:
        return "POINTER", excerpt
    return "OTHER", excerpt


def z2_missing_for_dispatch(prompt: str, repo_root: str) -> List[Tuple[str, str, str]]:
    """Возвращает [(token, class, excerpt), ...] для ОДНОГО диспатча."""
    missing = find_missing_given_paths(prompt, repo_root)
    if not missing:
        return []
    offsets, sections = _section_map(prompt)
    lines = prompt.splitlines(keepends=True)
    all_candidates = [tok for tok, _ in extract_given_candidates(prompt)]
    out = []
    for tok in missing:
        cls, excerpt = classify_z2_token(prompt, tok, offsets, sections, lines, all_candidates)
        out.append((tok, cls, excerpt))
    return out


# ---------------------------------------------------------------------------
# З3 -- форма given-декларации (pointer_form / inline_form / no_given).
# ---------------------------------------------------------------------------

def classify_z3_form(prompt: str) -> Tuple[str, int, bool]:
    """Р-5 (докстринг модуля): N -- путь-токены, считаются ТОЛЬКО внутри
    секции "given" (_section_map), НЕ по всему промпту -- иначе путь из
    owns-секции (та же форма регекса) искусственно раздувал бы N любого
    диспатча, несущего owns-путь (найдено ЭТИМ ЖЕ прогоном фикстуры,
    AK5: без этого сужения FX_Z3_POINTER ложно уходил в inline_form,
    так как owns: <path> добавлял второй "путь-токен" всему промпту)."""
    if not MANIFEST_GIVEN_RE.search(prompt):
        return "no_given_declaration", 0, False
    offsets, sections = _section_map(prompt)
    lines = prompt.splitlines(keepends=True)
    n = 0
    for tok, _is_abs in extract_given_candidates(prompt):
        pos = prompt.find(tok)
        if pos == -1:
            continue
        idx = _line_index(offsets, pos)
        sec = sections[idx] if 0 <= idx < len(sections) else "none"
        if sec == "given":
            n += 1
    bullet_lines = 0
    for i, line in enumerate(lines):
        sec = sections[i] if i < len(sections) else "none"
        if sec != "given":
            continue
        b1 = _SECTION_BULLET_PREFIX_RE.sub("", line, count=1)
        if b1 != line and b1.strip():
            bullet_lines += 1
            continue
        b2 = _SECTION_NUMBERED_PREFIX_RE.sub("", line, count=1)
        if b2 != line and b2.strip():
            bullet_lines += 1
    has_list = bullet_lines >= 2
    if n < 2 and not has_list:
        return "pointer_form", n, has_list
    return "inline_form", n, has_list


# ---------------------------------------------------------------------------
# Связывание с журналом (Р-6): meta.json toolUseId -- точный join.
# ---------------------------------------------------------------------------

def build_agent_meta_map(transcripts_dir: Path) -> Tuple[Dict[str, str], int, int]:
    """agent_id -> toolUseId, читая ВСЕ */subagents/agent-*.meta.json
    корпуса (без фильтра по окну -- дёшево, файлы малы)."""
    mapping: Dict[str, str] = {}
    total = 0
    broken = 0
    if not transcripts_dir.exists():
        return mapping, total, broken
    for sub in sorted(transcripts_dir.iterdir()):
        if not sub.is_dir():
            continue
        agents_dir = sub / "subagents"
        if not agents_dir.is_dir():
            continue
        for meta_path in sorted(agents_dir.glob("agent-*.meta.json")):
            total += 1
            name = meta_path.name
            agent_id = name[len("agent-"):-len(".meta.json")]
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8", errors="replace"))
            except (OSError, json.JSONDecodeError):
                broken += 1
                continue
            if not isinstance(data, dict):
                broken += 1
                continue
            tid = data.get("toolUseId")
            if isinstance(tid, str) and tid:
                mapping[agent_id] = tid
            else:
                broken += 1
    return mapping, total, broken


def load_journal(path: Path) -> Tuple[List[Dict[str, Any]], int]:
    events: List[Dict[str, Any]] = []
    broken = 0
    if not path.exists():
        return events, broken
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            s = ln.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                broken += 1
                continue
            if isinstance(obj, dict):
                events.append(obj)
            else:
                broken += 1
    return events, broken


def link_dispatch_outcome(
    d: Dispatch, tooluse_to_agent: Dict[str, str], journal_events: List[Dict[str, Any]],
) -> Tuple[str, Optional[str], Optional[str]]:
    """Возвращает (outcome, task_id, failure_class).
    outcome in {"rejected","accepted","other:<event>","open_no_followup","unknown"}.
    "unknown" -- НИКОГДА не считается "без reject" (край спеки, "молчаливый
    ноль") -- печатается отдельным классом."""
    agent_id = tooluse_to_agent.get(d.tool_use_id)
    idx_found = None
    task_id = None
    if agent_id is not None:
        wref = f"agent:{agent_id}"
        for i, ev in enumerate(journal_events):
            if ev.get("event") == "delegated" and ev.get("worker_ref") == wref:
                idx_found = i
                task_id = ev.get("task_id")
                break
    if idx_found is None:
        # запасной путь (Р-6): ts +/- 15 минут + подстрока description<->notes.
        desc = (d.description or "").strip()
        if desc:
            desc_key = desc[:40].lower()
            candidates = []
            for i, ev in enumerate(journal_events):
                if ev.get("event") != "delegated":
                    continue
                ev_ts_raw = ev.get("ts")
                if not isinstance(ev_ts_raw, str):
                    continue
                try:
                    ev_ts = datetime.fromisoformat(ev_ts_raw)
                except ValueError:
                    continue
                d_ts_naive = d.ts.astimezone().replace(tzinfo=None)
                delta = abs((ev_ts - d_ts_naive).total_seconds())
                if delta > 15 * 60:
                    continue
                notes = str(ev.get("notes", "")).lower()
                if desc_key and desc_key in notes:
                    candidates.append(i)
            if len(candidates) == 1:
                idx_found = candidates[0]
                task_id = journal_events[idx_found].get("task_id")
    if idx_found is None:
        return "unknown", None, None
    for j in range(idx_found + 1, len(journal_events)):
        ev = journal_events[j]
        if ev.get("task_id") != task_id:
            continue
        ev_type = ev.get("event")
        if ev_type == "rejected":
            return "rejected", task_id, ev.get("failure_class")
        if ev_type == "accepted":
            return "accepted", task_id, None
        return f"other:{ev_type}", task_id, None
    return "open_no_followup", task_id, None


# ---------------------------------------------------------------------------
# Фикстура (AK5) -- синтетические данные, известные ожидания, ПЕРВОЙ.
# ---------------------------------------------------------------------------

_FX_ROOT = str(REPO_ROOT) + "\\__fixture_nonexistent__\\"

FX_Z1_SECTION = (
    "sonnet: фикстура З1 -- секционная форма\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен, witness прилагается.\n\n"
    "## GIVEN (дано)\n"
    f"- {_FX_ROOT}a.py\n\n"
    "запиши результат.\n"
    "owns:\n"
    f"- {_FX_ROOT}out_a.py\n"
)
FX_Z1_PROSE = (
    "sonnet: фикстура З1 -- прозаическая форма\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен, witness прилагается.\n\n"
    "Замечу: given the context above, продолжи с той же спекой без нового брифа.\n\n"
    f"запиши результат в файл {_FX_ROOT}b.py.\n"
    f"owns: {_FX_ROOT}b.py\n"
)
FX_Z1_NONE = (
    "sonnet: фикстура З1 -- маркер отсутствует полностью\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен, witness прилагается.\n\n"
    f"запиши результат в файл {_FX_ROOT}c.py.\n"
    f"owns: {_FX_ROOT}c.py\n"
)
FX_Z1_PROMPTS = [FX_Z1_SECTION, FX_Z1_PROSE, FX_Z1_NONE]

FX_Z2_INLINE = (
    "sonnet: фикстура З2 -- INLINE\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    "## GIVEN (дано)\n"
    f"- {_FX_ROOT}i1.py\n"
    f"- {_FX_ROOT}i2.py\n\n"
    "запиши результат.\n"
    "owns:\n"
    f"- {_FX_ROOT}out1.py\n"
)
FX_Z2_POINTER_VERB = (
    "sonnet: фикстура З2 -- POINTER (глагол чтения)\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    "## GIVEN (дано)\n"
    f"Прочти спеку: {_FX_ROOT}p1.py перед началом.\n\n"
    "запиши результат.\n"
    "owns:\n"
    f"- {_FX_ROOT}out2.py\n"
)
FX_Z2_POINTER_NOSECTION = (
    "sonnet: фикстура З2 -- POINTER (вне секции)\n\n"
    f"Файл {_FX_ROOT}bare1.py упомянут вне манифеста, до всех заголовков.\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    "given: (весь контекст уже дан абзацем выше)\n\n"
    "запиши результат.\n"
    "owns:\n"
    f"- {_FX_ROOT}out3.py\n"
)
FX_Z2_PROMPTS = [FX_Z2_INLINE, FX_Z2_POINTER_VERB, FX_Z2_POINTER_NOSECTION]

FX_Z3_POINTER = (
    "sonnet: фикстура З3 -- pointer_form (rejected)\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    f"given: см. спеку {_FX_ROOT}spec1.py\n\n"
    "запиши результат.\n"
    f"owns: {_FX_ROOT}out4.py\n"
)
FX_Z3_INLINE = (
    "sonnet: фикстура З3 -- inline_form (accepted)\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    "given:\n"
    f"- {_FX_ROOT}spec2.py\n"
    f"- {_FX_ROOT}spec3.py\n\n"
    "запиши результат.\n"
    f"owns: {_FX_ROOT}out5.py\n"
)
FX_Z3_NO_GIVEN = (
    "sonnet: фикстура З3 -- маркер отсутствует полностью\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    f"запиши результат в файл {_FX_ROOT}out6.py.\n"
    f"owns: {_FX_ROOT}out6.py\n"
)
FX_Z3_POINTER_UNLINKED = (
    "sonnet: фикстура З3 -- pointer_form (unknown, не связан)\n\n"
    "DoD: критерии приёмки заданы, проверочный прогон обязателен.\n\n"
    f"given: {_FX_ROOT}spec4.py\n\n"
    "запиши результат.\n"
    f"owns: {_FX_ROOT}out7.py\n"
)

FIXTURE_EXPECTED = {
    "z1": {"section": 1, "prose_only": 1, "none": 1},
    "z2": {"INLINE": 2, "POINTER": 2, "OTHER": 0, "total_missing": 4},
    "z3": {
        "pointer_form": 2, "inline_form": 1, "no_given_declaration": 1,
        "linked": 2, "unknown": 1, "rejected": 1, "accepted": 1,
    },
}
# Негативный контроль (AK5): ОДНО ожидание сознательно сдвинуто --
# actual останется прежним (корректным), поэтому сравнение с ЭТИМ
# словарём ОБЯЗАНО провалиться. Сдвинуто z1.section: 1 -> 2.
FIXTURE_EXPECTED_WRONG = json.loads(json.dumps(FIXTURE_EXPECTED))
FIXTURE_EXPECTED_WRONG["z1"]["section"] = 2


def fixture_control() -> Dict[str, Dict[str, int]]:
    """Прогоняет ВСТРОЕННУЮ синтетическую фикстуру через ТЕ ЖЕ функции
    (classify_z1/z2_missing_for_dispatch/classify_z3_form), что и боевой
    прогон -- никакой отдельной логики счёта (тот же принцип, что
    tools/warn_density.fixture_control())."""
    actual: Dict[str, Dict[str, int]] = {
        "z1": {"section": 0, "prose_only": 0, "none": 0},
        "z2": {"INLINE": 0, "POINTER": 0, "OTHER": 0, "total_missing": 0},
        "z3": {
            "pointer_form": 0, "inline_form": 0, "no_given_declaration": 0,
            "linked": 0, "unknown": 0, "rejected": 0, "accepted": 0,
        },
    }
    for p in FX_Z1_PROMPTS:
        cls, _ = classify_z1(p)
        actual["z1"][cls] += 1

    for p in FX_Z2_PROMPTS:
        for tok, cls, excerpt in z2_missing_for_dispatch(p, str(REPO_ROOT)):
            actual["z2"][cls] += 1
            actual["z2"]["total_missing"] += 1

    fake_meta = {"fixtureagent1": "toolu_FIXTURE_POINTER", "fixtureagent2": "toolu_FIXTURE_INLINE"}
    # link_dispatch_outcome ждёт toolUseId -> agent_id (та же ориентация,
    # что main() строит из build_agent_meta_map через tooluse_to_agent) --
    # fake_meta выше идёт в ЕСТЕСТВЕННОЙ agent_id -> toolUseId форме
    # (как реальный meta.json), инвертируем здесь же (AK5 нашёл: без
    # инверсии ОБА связываемых диспатча ложно уходили в unknown).
    fake_tooluse_to_agent = {v: k for k, v in fake_meta.items()}
    fake_journal = [
        {"ts": "2026-01-01T00:00:00", "event": "delegated", "agent": "builder", "model": "sonnet",
         "task_id": "t-FIX1", "category": "implementation", "worker_ref": "agent:fixtureagent1",
         "notes": "fixture pointer"},
        {"ts": "2026-01-01T00:05:00", "event": "rejected", "agent": "builder", "model": "sonnet",
         "task_id": "t-FIX1", "category": "implementation", "by": "opus", "attempt": 1,
         "failure_class": "spec", "notes": "fixture reject"},
        {"ts": "2026-01-01T00:10:00", "event": "delegated", "agent": "builder", "model": "sonnet",
         "task_id": "t-FIX2", "category": "implementation", "worker_ref": "agent:fixtureagent2",
         "notes": "fixture inline"},
        {"ts": "2026-01-01T00:15:00", "event": "accepted", "agent": "builder", "model": "sonnet",
         "task_id": "t-FIX2", "category": "implementation", "by": "opus", "notes": "fixture accept",
         "witness": "fixture witness"},
    ]
    fx_dispatches = [
        (FX_Z3_POINTER, "toolu_FIXTURE_POINTER"),
        (FX_Z3_INLINE, "toolu_FIXTURE_INLINE"),
        (FX_Z3_NO_GIVEN, "toolu_FIXTURE_NOGIVEN"),
        (FX_Z3_POINTER_UNLINKED, "toolu_FIXTURE_UNLINKED"),
    ]
    for prompt, tool_use_id in fx_dispatches:
        cls, _n, _has_list = classify_z3_form(prompt)
        actual["z3"][cls] += 1
        if cls == "no_given_declaration":
            continue
        d = Dispatch(file=Path("<fixture>"), line_no=0, ts=datetime.now().astimezone(),
                     tool_use_id=tool_use_id, subagent_type="builder", description=None, prompt=prompt)
        outcome, _task_id, _fc = link_dispatch_outcome(d, fake_tooluse_to_agent, fake_journal)
        if outcome == "unknown":
            actual["z3"]["unknown"] += 1
        else:
            actual["z3"]["linked"] += 1
            if outcome == "rejected":
                actual["z3"]["rejected"] += 1
            elif outcome == "accepted":
                actual["z3"]["accepted"] += 1
    return actual


def compare_fixture(actual: Dict[str, Dict[str, int]], expected: Dict[str, Dict[str, int]]) -> List[str]:
    mismatches = []
    for q in ("z1", "z2", "z3"):
        for k, v in expected[q].items():
            got = actual[q].get(k)
            if got != v:
                mismatches.append(f"{q}.{k}: ожидание {v}, факт {got}")
    return mismatches


# ---------------------------------------------------------------------------
# Рендер / main
# ---------------------------------------------------------------------------

def fmt_frac(num: int, den: int) -> str:
    if den == 0:
        return f"{num}/0 (н-д, знаменатель 0)"
    return f"{num}/{den} ({num / den * 100:.1f}%)"


def print_fixture_section(actual: Dict[str, Dict[str, int]], expected: Dict[str, Dict[str, int]], label: str) -> List[str]:
    print(f"=== КОНТРОЛЬ ФИКСТУРЫ ({label}) ===")
    mism = compare_fixture(actual, expected)
    for q in ("z1", "z2", "z3"):
        print(f"  {q}: факт={actual[q]}")
        print(f"  {q}: ожидание={expected[q]}")
    if mism:
        print("  ДЕФЕКТ ИНСТРУМЕНТА: фикстура не сошлась с ожиданием:")
        for m in mism:
            print(f"    - {m}")
    else:
        print("  фикстура сошлась с ожиданием (дефектов нет)")
    return mism


def print_border_section(files_read: int, subagent_files: int, sidechain_calls: int, total_calls: int, skip_counts: Dict[str, int], total_lines: int, broken_lines: int) -> None:
    print("=== ГРАНИЦА НОСИТЕЛЯ (AK4) ===")
    print(f"  каталог: {DEFAULT_TRANSCRIPTS}")
    print(f"  файлов корпуса прочитано: {files_read} (из них subagent-файлов: {subagent_files})")
    print(f"  Task/Agent-вызовов: видимо (main) {total_calls} / невидимо (subagents/, вне измерения) {sidechain_calls}")
    print(f"  строк JSONL всего: {total_lines}, битых: {broken_lines}")
    if skip_counts:
        for reason, n in sorted(skip_counts.items()):
            print(f"  skipped: {reason} × {n}")
    else:
        print("  skipped: (нет)")


def run_z1(dispatches: List[Dispatch], label: str) -> None:
    writing = [d for d in dispatches if is_writing_dispatch(d)]
    counts = {"section": 0, "prose_only": 0, "none": 0}
    examples: Dict[str, List[str]] = {"section": [], "prose_only": [], "none": []}
    for d in writing:
        cls, exs = classify_z1(d.prompt)
        counts[cls] += 1
        if len(examples[cls]) < 3 and exs:
            examples[cls].append(f"[{exs[0][0]}] {exs[0][1]}")
    total_writing = len(writing)
    with_match = counts["section"] + counts["prose_only"]
    print(f"--- З1, {label}: пишущих диспатчей (subagent_type=builder И is_write) = {total_writing} ---")
    print(f"  section={counts['section']} prose_only={counts['prose_only']} none={counts['none']}")
    print(f"  доля prose_only от диспатчей с >=1 совпадением: {fmt_frac(counts['prose_only'], with_match)}")
    print(f"  доля prose_only от ВСЕХ пишущих диспатчей: {fmt_frac(counts['prose_only'], total_writing)}")
    for cls, exs in examples.items():
        for e in exs:
            print(f"    пример [{cls}]: {e}")


def run_z2(dispatches_window8: List[Dispatch]) -> None:
    print(f"--- З2, окно #8: диспатчей Task/Agent (ЛЮБОЙ subagent_type) = {len(dispatches_window8)} ---")
    fired = 0
    total_missing = 0
    class_counts = {"INLINE": 0, "POINTER": 0, "OTHER": 0}
    dispatch_class_counts = {"INLINE": 0, "POINTER": 0, "OTHER": 0}
    examples: Dict[str, List[str]] = {"INLINE": [], "POINTER": [], "OTHER": []}
    other_full: List[str] = []
    for d in dispatches_window8:
        results = z2_missing_for_dispatch(d.prompt, str(REPO_ROOT))
        if results:
            fired += 1
        classes_this_dispatch = set()
        for tok, cls, excerpt in results:
            total_missing += 1
            class_counts[cls] += 1
            classes_this_dispatch.add(cls)
            if len(examples[cls]) < 3:
                examples[cls].append(f"{tok[:60]} :: {excerpt}")
            if cls == "OTHER":
                other_full.append(f"{tok} :: {excerpt} (файл {d.file.name}:{d.line_no})")
        for c in classes_this_dispatch:
            dispatch_class_counts[c] += 1
    print(f"  реплицированное число диспатчей со срабатыванием (missing>0): {fired} "
          f"(сайдкар calls: {SIDECAR_GIVEN_PATH_CALLS_WINDOW8}, "
          f"расхождение: {fired - SIDECAR_GIVEN_PATH_CALLS_WINDOW8})")
    print(f"  всего отсутствующих токенов: {total_missing}")
    print(f"  INLINE={fmt_frac(class_counts['INLINE'], total_missing)} "
          f"POINTER={fmt_frac(class_counts['POINTER'], total_missing)} "
          f"OTHER={fmt_frac(class_counts['OTHER'], total_missing)}")
    print(f"  диспатчей по классам (диспатч может входить в >1, если несёт токены разных классов): "
          f"INLINE={dispatch_class_counts['INLINE']} POINTER={dispatch_class_counts['POINTER']} "
          f"OTHER={dispatch_class_counts['OTHER']}")
    for cls, exs in examples.items():
        for e in exs:
            print(f"    пример [{cls}]: {e}")
    if other_full:
        print("  OTHER -- ПОЛНЫЙ поштучный список (спека требует, не капается на 3):")
        for e in other_full:
            print(f"    OTHER: {e}")


def run_z3(dispatches: List[Dispatch], label: str, tooluse_to_agent: Dict[str, str], journal_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    writing = [d for d in dispatches if is_writing_dispatch(d)]
    form_counts = {"pointer_form": 0, "inline_form": 0, "no_given_declaration": 0}
    linked_pop = []  # (d, form_cls)
    for d in writing:
        cls, n, has_list = classify_z3_form(d.prompt)
        form_counts[cls] += 1
        if cls != "no_given_declaration":
            linked_pop.append((d, cls))
    outcome_by_form = {
        "pointer_form": {"rejected": 0, "accepted": 0, "unknown": 0, "other": 0},
        "inline_form": {"rejected": 0, "accepted": 0, "unknown": 0, "other": 0},
    }
    failure_class_by_form = {"pointer_form": {}, "inline_form": {}}
    linked_total = 0
    for d, cls in linked_pop:
        outcome, task_id, fc = link_dispatch_outcome(d, tooluse_to_agent, journal_events)
        if outcome == "unknown":
            outcome_by_form[cls]["unknown"] += 1
        else:
            linked_total += 1
            if outcome == "rejected":
                outcome_by_form[cls]["rejected"] += 1
                failure_class_by_form[cls][fc] = failure_class_by_form[cls].get(fc, 0) + 1
            elif outcome == "accepted":
                outcome_by_form[cls]["accepted"] += 1
            else:
                outcome_by_form[cls]["other"] += 1
    total_z3_pop = len(linked_pop)
    print(f"--- З3, {label}: пишущих диспатчей = {len(writing)}, "
          f"с given-декларацией (pointer+inline) = {total_z3_pop} ---")
    print(f"  pointer_form={form_counts['pointer_form']} inline_form={form_counts['inline_form']} "
          f"no_given_declaration={form_counts['no_given_declaration']}")
    print(f"  доля успешно связанных с журналом: {fmt_frac(linked_total, total_z3_pop)}")
    for cls in ("pointer_form", "inline_form"):
        pop = form_counts[cls]
        oc = outcome_by_form[cls]
        linked_this = oc["rejected"] + oc["accepted"] + oc["other"]
        print(f"  {cls}: связано {fmt_frac(linked_this, pop)}, "
              f"из связанных rejected={fmt_frac(oc['rejected'], linked_this)}, "
              f"accepted={fmt_frac(oc['accepted'], linked_this)}, "
              f"иной исход={oc['other']}, unknown={oc['unknown']}")
        if failure_class_by_form[cls]:
            print(f"    failure_class у {cls}: {failure_class_by_form[cls]}")
    return {"form_counts": form_counts, "outcome_by_form": outcome_by_form, "linked_total": linked_total, "total_pop": total_z3_pop}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--negative-control", action="store_true",
                     help="AK5: сверить фикстуру с СОЗНАТЕЛЬНО сдвинутым ожиданием -- обязан упасть")
    ap.add_argument("--transcripts", default=str(DEFAULT_TRANSCRIPTS))
    ap.add_argument("--journal", default=str(DEFAULT_JOURNAL))
    args = ap.parse_args(argv)

    transcripts_dir = Path(args.transcripts)

    if args.negative_control:
        actual = fixture_control()
        mism = print_fixture_section(actual, FIXTURE_EXPECTED_WRONG, "НЕГАТИВНЫЙ КОНТРОЛЬ, ожидание СОЗНАТЕЛЬНО сдвинуто z1.section 1->2")
        if not mism:
            print("НЕОЖИДАННО: негативный контроль НЕ нашёл расхождения -- контроль декоративен, это САМО ДЕФЕКТ.")
            return 1
        print("НЕГАТИВНЫЙ КОНТРОЛЬ ПОДТВЕРЖДЁН: расхождение найдено, как и ожидалось -- контроль не декоративен.")
        return 1

    # AK5: фикстура ПЕРВОЙ, с ПРАВИЛЬНЫМ ожиданием.
    actual = fixture_control()
    mism = print_fixture_section(actual, FIXTURE_EXPECTED, "боевое ожидание")
    fixture_defect = bool(mism)
    print()

    if not transcripts_dir.exists() or not transcripts_dir.is_dir():
        print(f"корпус пуст: --transcripts не существует/не каталог: {transcripts_dir}")
        return 0
    try:
        files = enumerate_corpus_files(transcripts_dir)
    except Exception as exc:  # SourceError и т.п. -- уже проверили exists выше
        print(f"корпус пуст: {exc}")
        return 0
    if not files:
        print(f"корпус пуст: 0 файлов в {transcripts_dir}")
        return 0

    subagent_files = sum(1 for f in files if is_sidechain_file(f))
    all_dispatches, sidechain_ts, skip_counts, total_lines, broken_lines = collect_corpus(files)

    print_border_section(len(files), subagent_files, len(sidechain_ts), len(all_dispatches), skip_counts, total_lines, broken_lines)
    print()

    # Границы окон -- Р-7/докстринг: попытка parse_window_bound() + fallback.
    print("=== ГРАНИЦЫ ОКОН (попытка reuse parse_window_bound, край спеки) ===")
    resolved_windows = []
    for label, raw_start, raw_end in WINDOWS_Z3:
        start_dt, note_s = resolve_window_bound(raw_start)
        end_dt, note_e = resolve_window_bound(raw_end)
        print(f"  {label}: start -> {note_s}")
        print(f"  {label}: end   -> {note_e}")
        resolved_windows.append((label, start_dt, end_dt))
    print()

    win8_label, win8_start, win8_end = resolved_windows[0]
    dispatches_win8 = [d for d in all_dispatches if in_window(d.ts, win8_start, win8_end)]
    if not dispatches_win8:
        print(f"окно {win8_label} пусто: 0 диспатчей (не ошибка инструмента -- факт окна)")

    print("=== З1: доля прозы против секции в MANIFEST_GIVEN_RE (пишущие диспатчи) ===")
    run_z1(dispatches_win8, win8_label)
    print(f"  доп. (вне контура спеки, бонус): весь корпус без фильтра по времени --")
    run_z1(all_dispatches, "весь корпус")
    print()

    print("=== З2: роль отсутствующих GIVEN_PATH-токенов, окно #8 ===")
    run_z2(dispatches_win8)
    print()

    print("=== З3: reject-доли pointer_form vs inline_form ===")
    meta_map, meta_total, meta_broken = build_agent_meta_map(transcripts_dir)
    print(f"  agent meta.json прочитано: {meta_total} (битых/без toolUseId: {meta_broken})")
    tooluse_to_agent = {}
    collisions = 0
    for agent_id, tool_use_id in meta_map.items():
        if tool_use_id in tooluse_to_agent:
            collisions += 1
            continue
        tooluse_to_agent[tool_use_id] = agent_id
    if collisions:
        print(f"  ПРЕДУПРЕЖДЕНИЕ: {collisions} toolUseId встретились у >1 agent-подпапки (коллизия join-ключа)")
    journal_events, journal_broken = load_journal(Path(args.journal))
    print(f"  журнал прочитан: {len(journal_events)} событий (битых строк: {journal_broken})")
    z3_summaries = []
    for label, start_dt, end_dt in resolved_windows:
        win_dispatches = [d for d in all_dispatches if in_window(d.ts, start_dt, end_dt)]
        if not win_dispatches:
            print(f"--- З3, {label}: окно пусто -- 0 диспатчей ---")
            continue
        z3_summaries.append(run_z3(win_dispatches, label, tooluse_to_agent, journal_events))
    if z3_summaries:
        pooled_form = {"pointer_form": 0, "inline_form": 0, "no_given_declaration": 0}
        pooled_outcome = {
            "pointer_form": {"rejected": 0, "accepted": 0, "unknown": 0, "other": 0},
            "inline_form": {"rejected": 0, "accepted": 0, "unknown": 0, "other": 0},
        }
        pooled_linked = 0
        pooled_pop = 0
        for s in z3_summaries:
            for k in pooled_form:
                pooled_form[k] += s["form_counts"][k]
            for cls in ("pointer_form", "inline_form"):
                for k in pooled_outcome[cls]:
                    pooled_outcome[cls][k] += s["outcome_by_form"][cls][k]
            pooled_linked += s["linked_total"]
            pooled_pop += s["total_pop"]
        print("--- З3, СВОДНО по трём окнам (не заменяет, а дополняет окна по отдельности) ---")
        print(f"  pointer_form={pooled_form['pointer_form']} inline_form={pooled_form['inline_form']} "
              f"no_given_declaration={pooled_form['no_given_declaration']}")
        print(f"  доля успешно связанных: {fmt_frac(pooled_linked, pooled_pop)}")
        for cls in ("pointer_form", "inline_form"):
            oc = pooled_outcome[cls]
            linked_this = oc["rejected"] + oc["accepted"] + oc["other"]
            print(f"  {cls}: связано {fmt_frac(linked_this, pooled_form[cls])}, "
                  f"rejected={fmt_frac(oc['rejected'], linked_this)}, "
                  f"accepted={fmt_frac(oc['accepted'], linked_this)}, "
                  f"unknown={oc['unknown']}")

    print()
    print("=== ИТОГ ===")
    if fixture_defect:
        print("ДЕФЕКТ ИНСТРУМЕНТА: встроенная фикстура не сошлась с ожиданием (см. раздел выше) -- exit 1")
        return 1
    print("фикстура сошлась, прогон состоялся -- exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
