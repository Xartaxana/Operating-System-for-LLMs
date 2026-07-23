"""Счётный скрипт чеков 3/13 еженедельной калибровки + A4 (правило 6) --
t-040. Снимает ручной подсчёт журнальных счётчиков с внимания ИИ
(D-0063): детерминированно решаемое (счёт, группировка, позиция в
файле) -- в код; ВЕРДИКТЫ (нарушение это или нет, например "тред
явно продолжен другим task_id" у t-012) остаются за Lead. Скрипт
печатает КАНДИДАТОВ, не приговоры.

Работает с ОБОИМИ форматами журнала маршрутизации:
  - OS  (D:\\...\\logs/routing-log.jsonl): JSON без пробелов, task_id t-NNN.
  - AO3 (D:\\AO3_tests\\logs/routing-log.jsonl): JSON С ПРОБЕЛАМИ после
    двоеточий, описательные task_id (at-bug-004 и т.п.).

Парсинг -- ТОЛЬКО json.loads построчно (урок первой калибровки: grep по
AO3-формату дал ложный пустой результат из-за пробелов после ':'; при
парсинге json.loads пробелы не имеют значения). Непарсящаяся строка --
кандидат-нарушение в отчёте, не молчаливый skip.

Exit code 0 всегда, кроме ошибок IO/аргументов -- скрипт измеритель, не
гейт (в отличие от tools/journal_validator.py, который блокирует коммит).

CLI:
    python tools/calibration_counts.py --journal PATH [--journal PATH ...]
        [--window-start ISO] [--window-end ISO] [--by-since ISO] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:  # безопасность вывода на Windows-консолях с не-UTF8 codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

DEFAULT_BY_SINCE = "2026-07-10T13:14:00"
# До-D-0053 эпоха OS-журнала (см. CLAUDE.md "Журнал маршрутизации" и
# WEEKLY_CALIBRATION_PROTOCOL чек 13): события со ts раньше этой границы
# читаются вручную, append-only, не в счёте кандидатов чека 3.
LEGACY_CUTOFF = "2026-07-08T20:00:00"

MODEL_REQUIRED_EVENTS = {"delegated", "escalated", "accepted", "rejected"}
TASK_ID_REQUIRED_EVENTS = {"delegated", "accepted", "rejected", "escalated", "defect_found"}
FAILURE_CLASSES = {"spec", "capability", "recon", "tooling"}
LIFECYCLE_EVENTS = {"delegated", "accepted", "rejected", "escalated"}
ALWAYS_REQUIRED_FIELDS = ("agent", "category", "notes")
# Маркер замены умершего воркера (2026-07-15, правило 9в2 / t-129 M1):
# литерал-зеркало REPLACES_WORKER_RE из journal_validator.py. Продублирован
# намеренно, не импортирован -- calibration_counts работает с ОБОИМИ
# журналами (OS/AO3) и не зависит от journal_validator (см. docstring
# файла); синхронизация конста проверяется тестом
# test_schema_constants_match_journal_validator в test_calibration_counts.py.
REPLACES_WORKER_RE = re.compile(r"replaces_worker:(\S+)")

# Незакрытые-задачи фикс (находка t-293): литерал-зеркало _CLOSES_RE из
# tools/session_context.py -- та же форма, что читает SessionStart-сканер
# (левый анкор \b, чтобы "discloses:t-001"/"encloses:t-133" не матчились
# как substring; значение -- ТОЛЬКО t-\d+, не произвольный non-whitespace
# токен -- это и есть форма сканера, не "первый non-whitespace фрагмент"
# буквально: хвостовая пунктуация типа "closes:t-042;" естественно
# отсекается самим \d+, не требует отдельной обрезки). Продублирован
# намеренно, не импортирован -- та же причина, что REPLACES_WORKER_RE
# выше (этот скрипт работает с ОБОИМИ журналами OS/AO3, не зависит от
# session_context.py, который специфичен для OS-хука).
CLOSES_RE = re.compile(r"(?<!\w)closes:(t-\d+)")


def extract_closes_tokens(notes: Optional[str]) -> List[str]:
    """closes:t-NNN токены из notes -- зеркало
    session_context._closes_task_ids: пустой список для не-строки/
    отсутствующего notes, никогда не бросает."""
    if not isinstance(notes, str):
        return []
    return CLOSES_RE.findall(notes)


def extract_replaces_worker(notes: Optional[str]) -> Optional[str]:
    """Правило 9(в2), сторона счётчика (не гейта): вытаскивает хэндл из
    маркера "replaces_worker:<хэндл>" в notes -- та же логика, что
    journal_validator.extract_replaces_worker, но эта копия только
    классифицирует ветку КАНДИДАТА для отчёта, ничего не блокирует."""
    if not isinstance(notes, str):
        return None
    m = REPLACES_WORKER_RE.search(notes)
    return m.group(1) if m else None


def parse_ts(ts: Optional[str]) -> Optional[datetime]:
    """Разбор ts. Возвращает None, если поле отсутствует/не строка/не
    парсится как ISO -- вызывающий код решает, что делать (кандидат
    "нет ts", не крэш)."""
    if not isinstance(ts, str) or not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


class ParsedLine:
    __slots__ = ("line_no", "raw", "data", "parse_error", "ts")

    def __init__(self, line_no: int, raw: str, data: Optional[Dict[str, Any]],
                 parse_error: Optional[str] = None):
        self.line_no = line_no
        self.raw = raw
        self.data = data
        self.parse_error = parse_error
        self.ts = parse_ts(data.get("ts")) if data else None


def load_journal(path: str) -> List[ParsedLine]:
    lines: List[ParsedLine] = []
    with open(path, "r", encoding="utf-8") as fh:
        for i, raw in enumerate(fh, start=1):
            stripped = raw.rstrip("\n\r")
            if not stripped.strip():
                continue
            try:
                data = json.loads(stripped)
                if not isinstance(data, dict):
                    lines.append(ParsedLine(i, stripped, None, "не JSON-объект (не dict)"))
                    continue
            except json.JSONDecodeError as exc:
                lines.append(ParsedLine(i, stripped, None, f"невалидный JSON: {exc}"))
                continue
            lines.append(ParsedLine(i, stripped, data))
    return lines


def _in_window(pl: ParsedLine, start: Optional[datetime], end: Optional[datetime]) -> bool:
    """Событие без парсящегося ts не исключается окном (нет данных для
    решения) -- считается "в окне"; отсутствие ts само по себе не
    проверяется этим скриптом отдельным чеком (ts обязателен структурно
    в журнале с первой строки, задача не просила это отдельно считать)."""
    if pl.ts is None:
        return True
    if start is not None and pl.ts < start:
        return False
    if end is not None and pl.ts >= end:
        return False
    return True


def analyze_journal(path: str, window_start: Optional[datetime], window_end: Optional[datetime],
                     by_since: datetime) -> Dict[str, Any]:
    all_lines = load_journal(path)
    unparsable = [
        {"line": pl.line_no, "error": pl.parse_error, "raw": pl.raw}
        for pl in all_lines if pl.data is None
    ]
    parsed_lines = [pl for pl in all_lines if pl.data is not None]
    in_window = [pl for pl in parsed_lines if _in_window(pl, window_start, window_end)]

    legacy_cutoff_dt = parse_ts(LEGACY_CUTOFF)

    # --- 1. Счёт по типам событий и по ярусам (agent x event) ---
    by_event: Dict[str, int] = {}
    by_agent_event: Dict[str, Dict[str, int]] = {}
    for pl in in_window:
        ev = pl.data.get("event", "<нет>")
        by_event[ev] = by_event.get(ev, 0) + 1
        agent = pl.data.get("agent")
        if isinstance(agent, str) and agent:
            by_agent_event.setdefault(agent, {})
            by_agent_event[agent][ev] = by_agent_event[agent].get(ev, 0) + 1

    # --- 2. Чек 3 / A4 (правило 6): rule-6 кандидаты ---
    # Группировка rejected по (task_id, agent) среди событий В ОКНЕ;
    # >=2 rejected -> ищем escalated с тем же task_id ПОЗЖЕ 2-й rejected
    # ПО ПОЗИЦИИ В ФАЙЛЕ (среди ВСЕХ распарсенных строк, не только окна --
    # эскалация могла лечь за границей окна).
    rejected_groups: Dict[Tuple[str, str], List[int]] = {}
    for pl in in_window:
        if pl.data.get("event") != "rejected":
            continue
        tid = pl.data.get("task_id")
        agent = pl.data.get("agent")
        if not tid:
            continue
        key = (tid, agent if isinstance(agent, str) else "<нет>")
        rejected_groups.setdefault(key, []).append(pl.line_no)

    escalated_by_task: Dict[str, List[int]] = {}
    for pl in parsed_lines:
        if pl.data.get("event") == "escalated":
            tid = pl.data.get("task_id")
            if tid:
                escalated_by_task.setdefault(tid, []).append(pl.line_no)

    rule6_candidates = []
    for (tid, agent), line_nos in rejected_groups.items():
        if len(line_nos) < 2:
            continue
        second_reject_line = sorted(line_nos)[1]
        esc_lines = [l for l in escalated_by_task.get(tid, []) if l > second_reject_line]
        if not esc_lines:
            rule6_candidates.append({
                "task_id": tid,
                "agent": agent,
                "rejected_lines": sorted(line_nos),
                "note": (
                    "кандидат; escalated с этим task_id после 2-й rejected не найден "
                    "(по позиции в файле). Ветка closed/superseded (тред продолжен другим "
                    "task_id) -- вердикт Lead, скрипту это не решить."
                ),
            })

    # --- 3. Пропуски типизированных полей (D-0053) ---
    field_violations = []
    legacy_events = []
    for pl in in_window:
        d = pl.data
        ev = d.get("event")
        tid = d.get("task_id")
        missing = []

        for f in ALWAYS_REQUIRED_FIELDS:
            v = d.get(f)
            if not isinstance(v, str) or not v.strip():
                missing.append(f)

        if ev in MODEL_REQUIRED_EVENTS:
            v = d.get("model")
            if not isinstance(v, str) or not v.strip():
                missing.append("model")

        if ev in TASK_ID_REQUIRED_EVENTS:
            if not isinstance(tid, str) or not tid.strip():
                missing.append("task_id")

        if ev == "rejected":
            fc = d.get("failure_class")
            if fc not in FAILURE_CLASSES:
                missing.append("failure_class")
            attempt = d.get("attempt")
            if not isinstance(attempt, int) or isinstance(attempt, bool):
                missing.append("attempt")

        if ev == "accepted" and d.get("agent") == "builder":
            w = d.get("witness")
            if not isinstance(w, str) or not w.strip():
                missing.append("witness")

        if ev == "defect_found":
            ref = d.get("ref")
            if not isinstance(ref, str) or not ref.strip():
                missing.append("ref")

        if not missing:
            continue

        entry = {"line": pl.line_no, "event": ev, "task_id": tid, "missing_fields": missing}
        if legacy_cutoff_dt is not None and pl.ts is not None and pl.ts < legacy_cutoff_dt:
            legacy_events.append(entry)
        else:
            field_violations.append(entry)

    # --- 4. by-пропуски относительно --by-since ---
    by_violations = []
    for pl in in_window:
        ev = pl.data.get("event")
        if ev not in ("accepted", "rejected"):
            continue
        if pl.ts is None or pl.ts < by_since:
            continue  # до активации валидатора -- легально
        by_val = pl.data.get("by")
        if not isinstance(by_val, str) or not by_val.strip():
            by_violations.append({
                "line": pl.line_no, "event": ev, "task_id": pl.data.get("task_id"),
                "ts": pl.data.get("ts"),
            })

    # --- 5. Целостность task_id: повторные delegated ---
    # Проходим В ПОРЯДКЕ ФАЙЛА (все distinct-parsed события, не только
    # окно, чтобы "последний lifecycle-статус" не терял историю до
    # окна) -- но регистрируем в отчёт только повторы, чьё delegated
    # само попадает в окно.
    last_status: Dict[str, str] = {}          # task_id -> event яруса lifecycle
    seen_delegated: Dict[str, bool] = {}      # task_id -> уже видели хоть один delegated
    # task_id -> множество worker_ref всех ПРЕДЫДУЩИХ delegated этого task_id
    # (любого agent) -- зеркало journal_validator.task_worker_refs, правило
    # 9в2. Пополняется ПОСЛЕ классификации текущей строки (harvest-after-
    # check порядок, как в валидаторе) -- self-reference (маркер ссылается
    # на worker_ref ЭТОЙ ЖЕ новой строки) не находит себя в prior_refs.
    task_worker_refs: Dict[str, set] = {}
    # Незакрытые-задачи фикс (находка t-293), часть (1): closes:-токены
    # собираются из notes ВСЕХ распарсенных строк (не только lifecycle-
    # событий -- токен может лежать в notes любого ПОЗДНЕГО события,
    # напр. dispatch_skipped/calibrated), по ВСЕМУ файлу, зеркаля
    # session_context.open_dispatches(), который тоже сканирует notes
    # безотносительно типа события. Простое присутствие токена закрывает
    # задачу для этого счётчика (не пытаемся воспроизвести полную
    # (ts, file_idx)-семантику "может ли более поздний delegated
    # переоткрыть после токена" из session_context.py -- этот скрипт
    # выдаёт КАНДИДАТОВ, не связывающий приговор; см. докстринг файла).
    closed_via_token: set = set()
    for pl in parsed_lines:
        for closed_tid in extract_closes_tokens(pl.data.get("notes")):
            closed_via_token.add(closed_tid)
    duplicate_delegates = []
    for pl in parsed_lines:
        d = pl.data
        ev = d.get("event")
        tid = d.get("task_id")
        if not isinstance(tid, str) or not tid:
            continue
        if ev == "delegated":
            agent = d.get("agent")
            attempt = d.get("attempt")
            has_attempt_ge2 = (isinstance(attempt, int) and not isinstance(attempt, bool)
                                and attempt >= 2)
            prior = last_status.get(tid)
            if seen_delegated.get(tid):
                # повторный delegated по уже виденному task_id
                if agent == "critic":
                    branch = "critic-вход"
                elif prior == "accepted" and not has_attempt_ge2:
                    branch = "кандидат-дубль"
                elif prior == "rejected":
                    branch = "continuation"
                elif has_attempt_ge2:
                    branch = "retry"
                else:
                    # (t-129 M1) замена умершего воркера (правило 9в2):
                    # маркер в notes + хэндл найден среди ПРЕДЫДУЩИХ
                    # worker_ref этого task_id -> легальная ветка
                    # "replacement"; маркер есть, но хэндл не встречается
                    # выше (или ссылается на самого себя -- ещё не
                    # harvest'нут) -> "replacement-фиктивный" (кандидат-
                    # нарушение). Без маркера -- прежний catch-all "other".
                    replaces_handle = extract_replaces_worker(d.get("notes"))
                    if replaces_handle is not None:
                        prior_refs = task_worker_refs.get(tid, set())
                        if replaces_handle in prior_refs:
                            branch = "replacement"
                        else:
                            branch = "replacement-фиктивный"
                    else:
                        branch = "other"
                if _in_window(pl, window_start, window_end):
                    duplicate_delegates.append({
                        "line": pl.line_no, "task_id": tid, "agent": agent,
                        "attempt": attempt, "prior_status": prior, "branch": branch,
                    })
            seen_delegated[tid] = True
            last_status[tid] = "delegated"
            worker_ref = d.get("worker_ref")
            if isinstance(worker_ref, str) and worker_ref.strip():
                task_worker_refs.setdefault(tid, set()).add(worker_ref.strip())
        elif ev in ("accepted", "rejected", "escalated"):
            last_status[tid] = ev
        elif ev == "decomposable":
            # Незакрытые-задачи фикс (находка t-293), часть (2): по
            # стейт-машине политики (CLAUDE.md mermaid-диаграмма журнала)
            # decomposable ЗАКРЫВАЕТ диспатч (возврат координатору под
            # тем же task_id) -- не остаётся "delegated" навечно.
            last_status[tid] = "decomposable"
        # defect_found не двигает lifecycle-статус исходной задачи (у него
        # свой task_id новой находки; ref указывает на исходную).

    # --- 6. ts-монотонность ---
    ts_anomalies = []
    prev_ts = None
    prev_line = None
    for pl in in_window:
        if pl.ts is None:
            continue
        if prev_ts is not None and pl.ts < prev_ts:
            ts_anomalies.append({
                "line": pl.line_no, "ts": pl.data.get("ts"),
                "prev_line": prev_line, "prev_ts": prev_ts.isoformat(),
            })
        prev_ts = pl.ts
        prev_line = pl.line_no

    # --- 7. Чек 13б: false-accept rate по ярусам ---
    defect_by_agent: Dict[str, int] = {}
    accepted_by_agent: Dict[str, int] = {}
    for pl in in_window:
        ev = pl.data.get("event")
        agent = pl.data.get("agent")
        if not isinstance(agent, str) or not agent:
            continue
        if ev == "defect_found":
            defect_by_agent[agent] = defect_by_agent.get(agent, 0) + 1
        elif ev == "accepted":
            accepted_by_agent[agent] = accepted_by_agent.get(agent, 0) + 1
    false_accept = {}
    for agent in set(list(defect_by_agent) + list(accepted_by_agent)):
        d_count = defect_by_agent.get(agent, 0)
        a_count = accepted_by_agent.get(agent, 0)
        rate = (d_count / a_count) if a_count else None
        false_accept[agent] = {"defect_found": d_count, "accepted": a_count, "rate": rate}

    # --- 8. Чек 13г: rejected по failure_class x agent x model ---
    rejected_distribution: Dict[Tuple[str, str, str], int] = {}
    for pl in in_window:
        if pl.data.get("event") != "rejected":
            continue
        fc = pl.data.get("failure_class", "<нет>")
        agent = pl.data.get("agent", "<нет>")
        model = pl.data.get("model", "<нет>")
        key = (fc, agent, model)
        rejected_distribution[key] = rejected_distribution.get(key, 0) + 1

    # --- 9. Деградация (чек 5): пары lead_degraded/lead_restored ---
    degradation_pairs = []
    open_degraded = None
    for pl in in_window:
        ev = pl.data.get("event")
        if ev == "lead_degraded":
            if open_degraded is not None:
                degradation_pairs.append({
                    "degraded_line": open_degraded["line"], "degraded_ts": open_degraded["ts"],
                    "restored_line": None, "restored_ts": None,
                    "note": "не закрыта следующей lead_degraded (ещё одна degraded раньше restored)",
                })
            open_degraded = {"line": pl.line_no, "ts": pl.data.get("ts")}
        elif ev == "lead_restored":
            if open_degraded is not None:
                degradation_pairs.append({
                    "degraded_line": open_degraded["line"], "degraded_ts": open_degraded["ts"],
                    "restored_line": pl.line_no, "restored_ts": pl.data.get("ts"),
                    "note": "closed",
                })
                open_degraded = None
            else:
                degradation_pairs.append({
                    "degraded_line": None, "degraded_ts": None,
                    "restored_line": pl.line_no, "restored_ts": pl.data.get("ts"),
                    "note": "lead_restored без предшествующей lead_degraded в окне",
                })
    if open_degraded is not None:
        degradation_pairs.append({
            "degraded_line": open_degraded["line"], "degraded_ts": open_degraded["ts"],
            "restored_line": None, "restored_ts": None,
            "note": "НЕЗАКРЫТА до конца окна/файла -- легально, если сессия ещё жива / "
                    "зафиксировано последним событием",
        })

    # --- 10. Незакрытые задачи ---
    # Находка t-293: "открыто" -- последний lifecycle-статус delegated
    # (decomposable теперь тоже lifecycle-статус, см. выше -- закрывает),
    # И задача НЕ отмечена closes:-токеном нигде в notes журнала.
    unclosed_tasks = []
    closed_by_decomposable = []
    for tid, status in last_status.items():
        if tid in closed_via_token:
            continue
        if status == "decomposable":
            closed_by_decomposable.append(tid)
            continue
        if status == "delegated":
            unclosed_tasks.append(tid)
    unclosed_tasks.sort()
    closed_by_decomposable.sort()

    return {
        "journal": path,
        "total_lines": len(all_lines),
        "parsed_lines": len(parsed_lines),
        "unparsable": unparsable,
        "in_window_count": len(in_window),
        "counts": {"by_event": by_event, "by_agent_event": by_agent_event},
        "rule6_candidates": rule6_candidates,
        "field_violations": field_violations,
        "legacy_events": legacy_events,
        "by_violations": by_violations,
        "duplicate_delegates": duplicate_delegates,
        "ts_anomalies": ts_anomalies,
        "false_accept": false_accept,
        "rejected_distribution": [
            {"failure_class": fc, "agent": a, "model": m, "count": c}
            for (fc, a, m), c in sorted(rejected_distribution.items())
        ],
        "degradation_pairs": degradation_pairs,
        "unclosed_tasks": unclosed_tasks,
        "closed_by_decomposable": closed_by_decomposable,
    }


def _fmt_section(title: str) -> str:
    return f"\n=== {title} ===\n"


def render_text(report: Dict[str, Any]) -> str:
    out = []
    out.append(f"# Журнал: {report['journal']}")
    out.append(f"Строк всего: {report['total_lines']}; распарсено: {report['parsed_lines']}; "
               f"в окне: {report['in_window_count']}")

    out.append(_fmt_section("Непарсящиеся строки (кандидат-нарушение)"))
    if report["unparsable"]:
        for u in report["unparsable"]:
            out.append(f"  line {u['line']}: {u['error']}")
    else:
        out.append("  (нет)")

    out.append(_fmt_section("Счёт по типам событий"))
    for ev, c in sorted(report["counts"]["by_event"].items()):
        out.append(f"  {ev}: {c}")

    out.append(_fmt_section("Счёт по ярусам x событиям (agent x event)"))
    for agent, evs in sorted(report["counts"]["by_agent_event"].items()):
        out.append(f"  {agent}: " + ", ".join(f"{ev}={c}" for ev, c in sorted(evs.items())))

    out.append(_fmt_section("Rule-6 / A4 кандидаты (пара rejected без escalated)"))
    if report["rule6_candidates"]:
        for c in report["rule6_candidates"]:
            out.append(f"  task_id={c['task_id']} agent={c['agent']} "
                       f"rejected_lines={c['rejected_lines']} -- {c['note']}")
    else:
        out.append("  (нет кандидатов)")

    out.append(_fmt_section("Пропуски типизированных полей (кандидат-нарушение, пост-legacy)"))
    if report["field_violations"]:
        for v in report["field_violations"]:
            out.append(f"  line {v['line']} event={v['event']} task_id={v['task_id']}: "
                       f"отсутствуют {v['missing_fields']}")
    else:
        out.append("  (нет)")

    out.append(_fmt_section(f"Legacy (ts < {LEGACY_CUTOFF}, не нарушения)"))
    out.append(f"  {len(report['legacy_events'])} событие(й) с пропусками полей до D-0053-эпохи")

    out.append(_fmt_section("by-пропуски (post by-since)"))
    if report["by_violations"]:
        for v in report["by_violations"]:
            out.append(f"  line {v['line']} event={v['event']} task_id={v['task_id']} ts={v['ts']}")
    else:
        out.append("  (нет)")

    out.append(_fmt_section("Повторные delegated по task_id (классификация ветки)"))
    if report["duplicate_delegates"]:
        for v in report["duplicate_delegates"]:
            note = (" (аномальный повтор вне канонических веток -- вердикт Lead)"
                    if v["branch"] == "other" else "")
            out.append(f"  line {v['line']} task_id={v['task_id']} agent={v['agent']} "
                       f"attempt={v['attempt']} prior_status={v['prior_status']} "
                       f"-> {v['branch']}{note}")
    else:
        out.append("  (нет повторов)")

    out.append(_fmt_section("ts-аномалии (информационно, известные классы F-23/F-29)"))
    if report["ts_anomalies"]:
        for a in report["ts_anomalies"]:
            out.append(f"  line {a['line']} ts={a['ts']} < line {a['prev_line']} "
                       f"prev_ts={a['prev_ts']}")
    else:
        out.append("  (нет)")

    out.append(_fmt_section("False-accept rate по ярусам (чек 13б)"))
    for agent, fa in sorted(report["false_accept"].items()):
        rate_s = f"{fa['rate']:.4f}" if fa["rate"] is not None else "н/д (accepted=0)"
        out.append(f"  {agent}: defect_found={fa['defect_found']} / accepted={fa['accepted']} "
                   f"= {rate_s}")

    out.append(_fmt_section("Rejected по failure_class x agent x model (чек 13г)"))
    if report["rejected_distribution"]:
        for r in report["rejected_distribution"]:
            out.append(f"  {r['failure_class']} / {r['agent']} / {r['model']}: {r['count']}")
    else:
        out.append("  (нет rejected в окне)")

    out.append(_fmt_section("Пары деградации lead_degraded/lead_restored (чек 5)"))
    if report["degradation_pairs"]:
        for p in report["degradation_pairs"]:
            out.append(f"  degraded(line={p['degraded_line']}, ts={p['degraded_ts']}) -> "
                       f"restored(line={p['restored_line']}, ts={p['restored_ts']}): {p['note']}")
    else:
        out.append("  (нет событий деградации в окне)")

    out.append(_fmt_section("Незакрытые задачи (последний lifecycle-эвент = delegated, "
                             "без closes:-токена)"))
    if report["unclosed_tasks"]:
        out.append("  " + ", ".join(report["unclosed_tasks"]))
    else:
        out.append("  (нет)")
    if report["closed_by_decomposable"]:
        out.append("  закрыта: decomposable -- " + ", ".join(report["closed_by_decomposable"]))

    return "\n".join(out)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--journal", action="append", required=True,
                    help="путь к routing-log.jsonl (можно повторять)")
    p.add_argument("--window-start", default=None, help="ISO ts, включительно (>=)")
    p.add_argument("--window-end", default=None, help="ISO ts, исключительно (<)")
    p.add_argument("--by-since", default=DEFAULT_BY_SINCE,
                    help="момент активации валидатора D-0069 (по умолчанию "
                         f"{DEFAULT_BY_SINCE})")
    p.add_argument("--json", action="store_true", help="машиночитаемый вывод")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    window_start = parse_ts(args.window_start) if args.window_start else None
    if args.window_start and window_start is None:
        print(f"calibration_counts: невалидный --window-start {args.window_start!r}",
              file=sys.stderr)
        return 2
    window_end = parse_ts(args.window_end) if args.window_end else None
    if args.window_end and window_end is None:
        print(f"calibration_counts: невалидный --window-end {args.window_end!r}",
              file=sys.stderr)
        return 2
    by_since = parse_ts(args.by_since)
    if by_since is None:
        print(f"calibration_counts: невалидный --by-since {args.by_since!r}", file=sys.stderr)
        return 2

    reports = []
    for path in args.journal:
        try:
            reports.append(analyze_journal(path, window_start, window_end, by_since))
        except OSError as exc:
            print(f"calibration_counts: не удалось прочитать {path!r}: {exc}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps({"journals": reports}, ensure_ascii=False, indent=2))
        return 0

    for report in reports:
        print(render_text(report))

    if len(reports) > 1:
        print(_fmt_section("СВОДКА по всем журналам"))
        for report in reports:
            n_rule6 = len(report["rule6_candidates"])
            n_field = len(report["field_violations"])
            n_by = len(report["by_violations"])
            n_dup = len(report["duplicate_delegates"])
            n_ts = len(report["ts_anomalies"])
            n_rejected = report["counts"]["by_event"].get("rejected", 0)
            print(f"  {report['journal']}: rejected={n_rejected}, rule6_candidates={n_rule6}, "
                  f"field_violations={n_field}, by_violations={n_by}, "
                  f"duplicate_delegates={n_dup}, ts_anomalies={n_ts}, "
                  f"unparsable={len(report['unparsable'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
