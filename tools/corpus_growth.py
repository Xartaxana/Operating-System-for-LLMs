"""Детектор роста нормативного корпуса -- Phase 5 W3 (t-508).

Измеряет 12 нормативных артефактов манифеста tools/corpus_manifest.json
по метрике БАЙТ НА ЗАПИСЬ (bpr) и пишет каждый прогон строкой в сайдкар
logs/corpus_growth.jsonl (растёт вечно, Р11(A) спеки
docs/tasks/2026-08-19_w3-corpus-growth-spec.md). Инструмент-измеритель,
НЕ гейт: --check exit 0 даже при пробитом пороге (BREACH) -- гейт на
росте норм заблокировал бы законные нормы (Р6(A)); --check краснеет
ТОЛЬКО на дефектах ФОРМЫ манифеста/счётчика (пп. S7 спеки).

Единица -- БАЙТ НА ЗАПИСЬ (bpr = bytes / records, целое). Дельта-
правило "рост вглубь" печатается ВСЕГДА, независимо от порогов:
Δbpr>0 при Δrecords<=0 -- диагноз, не вердикт. Пороги (bpr_max)
назначает Lead ПОСЛЕ первого прогона (--init-thresholds печатает
предложение по формуле замер×1.15, манифест не правит).

Гигиена п.6 (счётчики): MISSING артефакт остаётся строкой MISSING, а
НЕ "0 байт" -- смешение это разные состояния. Непустой файл с нулём
записей -- ДЕФЕКТ "регекс протух", не "записей нет" (класс Р8(A),
сиблинги: test_findings_form, norm_retire, escape_check, prepass).
Каждый прогон печатает встроенный позитивный контроль счётчика
(фикстура "3/3") -- секция КОНТРОЛЬ ИСТОЧНИКОВ.

Манифест -- JSON-объект {"thresholds_version": int, "artifacts": [...]}.
Артефакт: {"path": <относительный от --root>, "unit": <текст>,
"record_re": <регекс>, "owner": corpus|corpus-archive|boot-mirror,
"bpr_max": int|null}. boot-mirror -- порог ЗАПРЕЩЁН (дефект формы);
печатается, в сумму/агрегат не входит (CLAUDE.md -- зеркало бут-пути
без собственного порога, владелец числа -- session_context).

Особый случай манифеста -- docs/RULE_COVERAGE.md, unit "строка
реестра": record_re хранится ДОСЛОВНО как в спеке ("^\\| + exclude
разделители/шапки") -- составная запись: базовый регекс до маркера
" + exclude" (здесь "^\\|", строки-начала таблицы) ПЛЮС программная
эксклюзия строк-разделителей markdown-таблицы ("|---|---|---|") и
строки-шапки (строка НЕПОСРЕДСТВЕННО ПЕРЕД разделителем) -- обе
исключаются из счёта записей. Это ИНТЕРПРЕТАЦИЯ builder'а составной
ячейки таблицы S1 спеки (см. отчёт диспатча t-508); закодирована как
общий маркер " + exclude" в record_re, не как хардкод пути, чтобы
не плодить path-специфичные ветки.

CLI:
    python tools/corpus_growth.py [--manifest PATH] [--registry PATH]
        [--root PATH] [--json] [--baseline-ts ISO]
    python tools/corpus_growth.py --check [...]
    python tools/corpus_growth.py --init-thresholds [...]

--baseline-ts ISO (M2, docs/tasks/2026-08-25_wave2-misc-spec.md, F15-ii):
    prev_entry берётся не последней записью сайдкара вообще, а
    последней записью с ts <= --baseline-ts (граница включительна).
    Без флага -- поведение байт-в-байт как раньше (последняя запись).
    Ни одной подходящей записи -> prev_entry=None, как при пустом
    сайдкаре. Невалидный ISO -> ошибка, exit 2 (не измерить ничего).

Коды выхода: 0 -- прогон состоялся (в т.ч. при BREACH, Р6(A));
1 -- ТОЛЬКО у --check при найденных дефектах формы; 2 -- IO/аргументы
(манифест отсутствует/не JSON/неверная структура верхнего уровня,
--root не каталог и т.п.) -- в этих мирах измерить вообще ничего
нельзя, в отличие от дефекта ОДНОЙ записи манифеста (тот не рвёт
прогон, D-0043-класс "не трейсбек", S7 край 13).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:  # безопасность вывода на Windows-консолях с не-UTF8 codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "tools" / "corpus_manifest.json"
DEFAULT_REGISTRY = REPO_ROOT / "logs" / "corpus_growth.jsonl"

VALID_OWNERS = {"corpus", "corpus-archive", "boot-mirror"}
MAX_RECORD_RE_BYTES = 200
WARN_FRACTION = 0.95
TABLE_EXCLUDE_MARKER = " + exclude"

# Встроенная фикстура -- позитивный контроль счётчика (гигиена п.6):
# известный текст с РОВНО 3 записями по известному регексу; печатается
# каждым прогоном как "фикстура <N>/3".
FIXTURE_TEXT = (
    "## D-0001 первая\nтело первой записи\n\n"
    "## D-0002 вторая\nтело второй записи\n\n"
    "## D-0003 третья\nтело третьей записи\n"
)
FIXTURE_RE = r"^## D-\d{4}\b"
FIXTURE_EXPECTED = 3


class ManifestError(Exception):
    """Манифест-уровневая ошибка -- маппится на exit 2 (не измерить
    вообще ничего): файл отсутствует, не JSON, структура верхнего
    уровня не распознана."""


class RootError(Exception):
    """--root указывает не на каталог -- exit 2."""


# ---------------------------------------------------------------------------
# Манифест: чтение и структурная (файловая) валидация
# ---------------------------------------------------------------------------

@dataclass
class Artifact:
    path: str
    unit: str
    record_re: str
    owner: str
    bpr_max: Optional[int]
    index: int


def read_manifest(manifest_path: Path) -> Tuple[int, List[Dict[str, Any]], bytes]:
    """Возвращает (thresholds_version, raw_artifact_dicts, raw_bytes).
    Ошибки формы верхнего уровня -> ManifestError (exit 2)."""
    if not manifest_path.exists():
        raise ManifestError(f"манифест не найден: {manifest_path}")
    raw = manifest_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestError(f"манифест не в UTF-8: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"манифест не JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(
            "манифест: верхний уровень должен быть JSON-объектом "
            f"{{thresholds_version, artifacts}}, получен {type(data).__name__}"
        )
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ManifestError(
            "манифест: поле 'artifacts' отсутствует или не список"
        )
    thresholds_version = data.get("thresholds_version", 0)
    if not isinstance(thresholds_version, int):
        raise ManifestError("манифест: 'thresholds_version' не целое число")
    for i, item in enumerate(artifacts):
        if not isinstance(item, dict):
            raise ManifestError(
                f"манифест: artifacts[{i}] не JSON-объект (получен "
                f"{type(item).__name__})"
            )
    return thresholds_version, artifacts, raw


def validate_entries(raw_artifacts: List[Dict[str, Any]]) -> Tuple[List[Artifact], List[str]]:
    """Возвращает (валидные_артефакты, дефекты_формы).

    Две независимые категории дефектов на запись:
    - СТРУКТУРНЫЙ дефект (path/unit/record_re/owner отсутствуют или
      неверны, дубль path) -- запись целиком ИСКЛЮЧАЕТСЯ из измерения
      (нечего мерить без валидного path/record_re/owner); дефект ОДНОЙ
      записи не рвёт прогон (S7 край 13, "не трейсбек") -- остальные
      записи продолжают измеряться.
    - дефект ПОРОГА (bpr_max<=0 / не число / назначен boot-mirror) --
      запись ВСЁ РАВНО измеряется (bytes/records/bpr считаются), но
      её эффективный bpr_max обнуляется до None (вердикт "-"), а
      дефект попадает в общий список.
    """
    defects: List[str] = []
    valid: List[Artifact] = []
    path_counts: Dict[str, int] = {}
    for item in raw_artifacts:
        p = item.get("path")
        if isinstance(p, str):
            path_counts[p] = path_counts.get(p, 0) + 1
    dup_reported: set = set()

    for idx, item in enumerate(raw_artifacts):
        label = item.get("path") if isinstance(item.get("path"), str) else f"artifacts[{idx}]"
        structural_ok = True

        path = item.get("path")
        if not isinstance(path, str) or not path:
            defects.append(f"ДЕФЕКТ формы: {label}: поле 'path' отсутствует/пустое")
            structural_ok = False
        else:
            if os.path.isabs(path) or re.match(r"^[A-Za-z]:[\\/]", path):
                defects.append(f"ДЕФЕКТ формы: {path}: абсолютный путь запрещён в манифесте")
                structural_ok = False
            if ".." in re.split(r"[\\/]+", path):
                defects.append(f"ДЕФЕКТ формы: {path}: '..' в пути запрещён")
                structural_ok = False
            if path_counts.get(path, 0) > 1:
                if path not in dup_reported:
                    defects.append(
                        f"ДЕФЕКТ формы: дубль path: {path} ({path_counts[path]} вхождений)"
                    )
                    dup_reported.add(path)
                structural_ok = False  # каждое вхождение дубля исключается из измерения

        unit = item.get("unit")
        if not isinstance(unit, str) or not unit:
            defects.append(f"ДЕФЕКТ формы: {label}: поле 'unit' отсутствует/пустое")
            structural_ok = False

        record_re = item.get("record_re")
        if not isinstance(record_re, str) or not record_re:
            defects.append(f"ДЕФЕКТ формы: {label}: поле 'record_re' отсутствует/пустое")
            structural_ok = False
        else:
            re_bytes = len(record_re.encode("utf-8"))
            if re_bytes > MAX_RECORD_RE_BYTES:
                defects.append(
                    f"ДЕФЕКТ формы: {label}: record_re длиннее {MAX_RECORD_RE_BYTES} Б "
                    f"UTF-8: {re_bytes} Б"
                )
                structural_ok = False
            base_pattern = record_re.split(TABLE_EXCLUDE_MARKER, 1)[0].strip()
            try:
                re.compile(base_pattern, re.MULTILINE)
            except re.error as exc:
                defects.append(f"ДЕФЕКТ формы: {label}: re.error в record_re: {exc}")
                structural_ok = False

        owner = item.get("owner")
        if owner not in VALID_OWNERS:
            defects.append(
                f"ДЕФЕКТ формы: {label}: owner {owner!r} не входит в закрытый энум "
                f"{sorted(VALID_OWNERS)}"
            )
            structural_ok = False

        bpr_max_raw = item.get("bpr_max", None)
        bpr_max: Optional[int] = None
        if bpr_max_raw is not None:
            if not isinstance(bpr_max_raw, (int, float)) or isinstance(bpr_max_raw, bool):
                defects.append(f"ДЕФЕКТ формы: {label}: bpr_max не число: {bpr_max_raw!r}")
            elif bpr_max_raw <= 0:
                defects.append(f"ДЕФЕКТ формы: {label}: bpr_max<=0 ({bpr_max_raw})")
            elif owner == "boot-mirror":
                defects.append(
                    f"ДЕФЕКТ формы: {label}: порог у boot-mirror запрещён (bpr_max={bpr_max_raw})"
                )
            else:
                bpr_max = int(bpr_max_raw)

        if not structural_ok:
            continue
        valid.append(Artifact(
            path=path, unit=unit, record_re=record_re, owner=owner,
            bpr_max=bpr_max, index=idx,
        ))
    return valid, defects


# ---------------------------------------------------------------------------
# Счётчик записей
# ---------------------------------------------------------------------------

_TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+$")


def _count_table_rows(lines: List[str], regex: "re.Pattern[str]") -> int:
    """Спец-логика RULE_COVERAGE.md: базовый regex matches ('^\\|'-строки),
    минус строки-разделители markdown-таблицы ('|---|---|---|') и строка
    ШАПКИ (та, что НЕПОСРЕДСТВЕННО перед разделителем) -- обе исключаются
    из счёта записей (S1 таблица, запись 'строка реестра')."""
    matched_idx = [i for i, ln in enumerate(lines) if regex.match(ln)]
    matched_set = set(matched_idx)
    exclude = set()
    for i in matched_idx:
        ln = lines[i]
        if _TABLE_SEP_RE.match(ln) and "-" in ln:
            exclude.add(i)
            if (i - 1) in matched_set:
                exclude.add(i - 1)
    return len([i for i in matched_idx if i not in exclude])


def count_records(text_normalized: str, record_re: str) -> int:
    """record_re уже прошёл валидацию (compile-able база). MULTILINE."""
    if TABLE_EXCLUDE_MARKER in record_re:
        base_pattern = record_re.split(TABLE_EXCLUDE_MARKER, 1)[0].strip()
        regex = re.compile(base_pattern, re.MULTILINE)
        lines = text_normalized.split("\n")
        return _count_table_rows(lines, regex)
    regex = re.compile(record_re, re.MULTILINE)
    return len(list(regex.finditer(text_normalized)))


def fixture_control() -> int:
    return len(list(re.finditer(FIXTURE_RE, FIXTURE_TEXT, re.MULTILINE)))


# ---------------------------------------------------------------------------
# Измерение одного артефакта
# ---------------------------------------------------------------------------

@dataclass
class Measurement:
    path: str
    unit: str
    owner: str
    bpr_max: Optional[int]
    exists: bool
    bytes_: Optional[int] = None
    records: Optional[int] = None
    bpr: Optional[int] = None
    state: str = ""
    reason: str = ""
    is_defect: bool = False
    decode_warn: bool = False


def measure_artifact(root: Path, art: Artifact) -> Measurement:
    full = root / art.path
    if not full.exists() or not full.is_file():
        return Measurement(
            path=art.path, unit=art.unit, owner=art.owner, bpr_max=art.bpr_max,
            exists=False, state="MISSING",
            reason=f"файл не найден: {full}", is_defect=True,
        )
    raw = full.read_bytes()
    size = len(raw)
    if size == 0:
        return Measurement(
            path=art.path, unit=art.unit, owner=art.owner, bpr_max=art.bpr_max,
            exists=True, bytes_=0, records=0, bpr=None, state="ПУСТ",
            reason="файл пуст (0 Б)", is_defect=False,
        )
    decode_warn = False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        decode_warn = True
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    records = count_records(normalized, art.record_re)
    if records == 0:
        return Measurement(
            path=art.path, unit=art.unit, owner=art.owner, bpr_max=art.bpr_max,
            exists=True, bytes_=size, records=0, bpr=None, state="ДЕФЕКТ",
            reason="непустой файл, ноль записей -- регекс протух (гигиена п.6)",
            is_defect=True, decode_warn=decode_warn,
        )
    bpr = int(round(size / records))
    if art.owner == "boot-mirror" or art.bpr_max is None:
        state = "—"
        reason = "порог не назначен" if art.owner != "boot-mirror" else "зеркало бут-пути, порог запрещён"
    else:
        warn_floor = art.bpr_max * WARN_FRACTION
        if bpr <= warn_floor:
            state, reason = "OK", f"<= 95% порога ({warn_floor:.1f})"
        elif bpr <= art.bpr_max:
            state, reason = "WARN", f"в полосе (95%..{art.bpr_max}]"
        else:
            state, reason = "BREACH", f"> порога {art.bpr_max}"
    return Measurement(
        path=art.path, unit=art.unit, owner=art.owner, bpr_max=art.bpr_max,
        exists=True, bytes_=size, records=records, bpr=bpr, state=state,
        reason=reason, is_defect=False, decode_warn=decode_warn,
    )


# ---------------------------------------------------------------------------
# Сайдкар: чтение/запись (образец prepass read_registry/write_registry_entry)
# ---------------------------------------------------------------------------

def read_registry(registry_path: Path) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Возвращает (entries, warnings). Битая строка -- пропуск + WARN
    (S7 край 7; отличие от prepass.read_registry, которая молча
    пропускает)."""
    if not registry_path.exists():
        return [], []
    entries: List[Dict[str, Any]] = []
    warnings: List[str] = []
    with open(registry_path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, ln in enumerate(fh, start=1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                entries.append(json.loads(ln))
            except json.JSONDecodeError as exc:
                warnings.append(f"битая строка сайдкара {registry_path}:{line_no}: {exc}")
    return entries, warnings


def manifest_sha(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def write_registry_entry(registry_path: Path, entry: Dict[str, Any]) -> Optional[str]:
    """Возвращает None при успехе, иначе строку WARN (S7 край 9 --
    сайдкар не пишется -> WARN, exit 0, не исключение наружу)."""
    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(registry_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return None
    except OSError as exc:
        return f"сайдкар не записан ({registry_path}): {exc}"


# ---------------------------------------------------------------------------
# Дельты / ВЫБЫЛИ / агрегат
# ---------------------------------------------------------------------------

def build_report(
    manifest_path: Path, registry_path: Path, root: Path,
    baseline_dt: Optional[datetime] = None,
) -> Dict[str, Any]:
    thresholds_version, raw_artifacts, raw_bytes = read_manifest(manifest_path)
    valid_artifacts, form_defects = validate_entries(raw_artifacts)

    measurements: List[Measurement] = [measure_artifact(root, a) for a in valid_artifacts]
    warnings: List[str] = []
    for m in measurements:
        if m.decode_warn:
            warnings.append(f"не-UTF8 в {m.path}: декод errors=replace, байты точны")

    registry_entries, sidecar_read_warnings = read_registry(registry_path)
    warnings.extend(sidecar_read_warnings)

    if baseline_dt is None:
        # M2 (docs/tasks/2026-08-25_wave2-misc-spec.md): без --baseline-ts --
        # поведение байт-в-байт как раньше -- последняя запись сайдкара.
        prev_entry = registry_entries[-1] if registry_entries else None
    else:
        # M2: prev_entry -- ПОСЛЕДНЯЯ запись сайдкара с ts <= baseline-ts
        # (граница включительна, "<="). Ни одной подходящей записи ->
        # prev_entry остаётся None (Δ печатаются как при пустом сайдкаре).
        prev_entry = None
        for entry in registry_entries:
            entry_ts = entry.get("ts")
            if not isinstance(entry_ts, str):
                continue
            try:
                entry_dt = datetime.fromisoformat(entry_ts)
            except ValueError:
                continue
            if entry_dt <= baseline_dt:
                prev_entry = entry
    base_status = "БАЗЫ НЕТ"
    prev_artifacts: Dict[str, Any] = {}
    if prev_entry is not None:
        prev_artifacts = prev_entry.get("artifacts", {}) or {}
        prev_sha = prev_entry.get("manifest_sha")
        if prev_sha != manifest_sha(raw_bytes):
            base_status = "БАЗА ОТ ДРУГОГО МАНИФЕСТА"
        else:
            base_status = "OK"

    deltas: Dict[str, Dict[str, Any]] = {}
    growth_deep_lines: List[str] = []
    current_paths = {m.path for m in measurements}
    for m in measurements:
        prev = prev_artifacts.get(m.path)
        if prev is None:
            deltas[m.path] = {"status": "новый"}
            continue
        prev_bytes = prev.get("bytes")
        prev_records = prev.get("records")
        prev_bpr = prev.get("bpr")
        if m.bytes_ is None or prev_bytes is None:
            deltas[m.path] = {"status": "н-д"}
            continue
        d_bytes = m.bytes_ - prev_bytes
        d_records = (m.records - prev_records) if (m.records is not None and prev_records is not None) else None
        d_bpr = (m.bpr - prev_bpr) if (m.bpr is not None and prev_bpr is not None) else None
        deltas[m.path] = {
            "status": "OK", "d_bytes": d_bytes, "d_records": d_records, "d_bpr": d_bpr,
        }
        if d_bpr is not None and d_bpr > 0 and d_records is not None and d_records <= 0:
            growth_deep_lines.append(
                f"РОСТ ВГЛУБЬ: {m.path} +{d_bpr} Б/запись при {d_records} новых записей"
            )

    departed: List[Dict[str, Any]] = []
    if prev_artifacts:
        for path, data in prev_artifacts.items():
            if path not in current_paths:
                departed.append({"path": path, **data})

    sum_bytes = sum(m.bytes_ for m in measurements if m.owner in ("corpus", "corpus-archive") and m.bytes_ is not None)
    assigned_k = sum(1 for a in valid_artifacts if a.bpr_max is not None)
    total_n = len(raw_artifacts)
    warn_count = sum(1 for m in measurements if m.state == "WARN")
    breach_count = sum(1 for m in measurements if m.state == "BREACH")

    # П.2 диспатча 2026-08-28 (ось 15 карты): "порогов k/N" вечно недо-
    # стижим до k/N-1, пока N считает boot-mirror (порог ЗАПРЕЩЁН формой
    # -- validate_entries выше). Новый знаменатель -- ТОЛЬКО артефакты,
    # которым порог РАЗРЕШЁН формой (owner != "boot-mirror"), считанные
    # ПО valid_artifacts (той же популяции, что и assigned_k, 1:1 с
    # measurements -- см. build_report выше measure_artifact). Недо-
    # стижимое (boot-mirror) печатается СВОИМ числом рядом, не молчит.
    # "БЕЗ ПОРОГА: <path>" (2б) -- порог разрешён, но НЕ назначен
    # (bpr_max is None у НЕ-boot-mirror артефакта) -- отдельная находка
    # для чека 34(в), не вычитаемая из дроби молча.
    threshold_denominator = sum(1 for a in valid_artifacts if a.owner != "boot-mirror")
    outside_threshold_boot_mirror = sum(1 for a in valid_artifacts if a.owner == "boot-mirror")
    no_threshold_paths = [
        a.path for a in valid_artifacts if a.owner != "boot-mirror" and a.bpr_max is None
    ]

    prev_sum_bytes = None
    if prev_entry is not None:
        prev_totals = prev_entry.get("totals", {}) or {}
        prev_sum_bytes = prev_totals.get("sum_bytes")
    delta_sum_bytes = (sum_bytes - prev_sum_bytes) if isinstance(prev_sum_bytes, int) else None

    fixture_n = fixture_control()

    return {
        "thresholds_version": thresholds_version,
        "manifest_sha": manifest_sha(raw_bytes),
        "manifest_path": str(manifest_path),
        "measurements": measurements,
        "form_defects": form_defects,
        "warnings": warnings,
        "base_status": base_status,
        "deltas": deltas,
        "growth_deep_lines": growth_deep_lines,
        "departed": departed,
        "sum_bytes": sum_bytes,
        "assigned_k": assigned_k,
        "total_n": total_n,
        "threshold_denominator": threshold_denominator,
        "outside_threshold_boot_mirror": outside_threshold_boot_mirror,
        "no_threshold_paths": no_threshold_paths,
        "warn_count": warn_count,
        "breach_count": breach_count,
        "delta_sum_bytes": delta_sum_bytes,
        "fixture_n": fixture_n,
        "registry_path": str(registry_path),
    }


# ---------------------------------------------------------------------------
# Рендер
# ---------------------------------------------------------------------------

def render_text(report: Dict[str, Any], sidecar_warn: Optional[str]) -> str:
    out: List[str] = []
    out.append("=== КОНТРОЛЬ ИСТОЧНИКОВ ===")
    out.append(f"  манифест: {report['manifest_path']} (существует={Path(report['manifest_path']).exists()})")
    out.append(f"  позитивный контроль счётчика (встроенная фикстура): "
               f"{report['fixture_n']}/{FIXTURE_EXPECTED}")
    out.append(f"  сайдкар: {report['registry_path']} | база: {report['base_status']}")
    for w in report["warnings"]:
        out.append(f"  WARN: {w}")
    if sidecar_warn:
        out.append(f"  WARN: {sidecar_warn}")

    out.append("\n=== АРТЕФАКТЫ ===")
    for m in report["measurements"]:
        d = report["deltas"].get(m.path, {})
        if d.get("status") == "новый":
            delta_str = "новый"
        elif d.get("status") == "н-д" or not d:
            delta_str = "—"
        else:
            delta_str = f"Δbytes={d.get('d_bytes')} Δrecords={d.get('d_records')} Δbpr={d.get('d_bpr')}"
        bpr_str = m.bpr if m.bpr is not None else "—"
        bytes_str = m.bytes_ if m.bytes_ is not None else "—"
        records_str = m.records if m.records is not None else "—"
        out.append(
            f"  {m.path} [{m.owner}, {m.unit}]: {m.state} | bytes={bytes_str} "
            f"records={records_str} bpr={bpr_str} | {delta_str} | {m.reason}"
        )

    out.append("\n=== ДЕФЕКТЫ ===")
    all_defects = list(report["form_defects"])
    for m in report["measurements"]:
        if m.is_defect:
            all_defects.append(f"ДЕФЕКТ: {m.path}: {m.reason}")
    if all_defects:
        for ln in all_defects:
            out.append(f"  {ln}")
    else:
        out.append("  (дефектов нет)")

    out.append("\n=== ВЫБЫЛИ ===")
    if report["departed"]:
        for dep in report["departed"]:
            out.append(
                f"  {dep['path']}: последние числа bytes={dep.get('bytes')} "
                f"records={dep.get('records')} bpr={dep.get('bpr')}"
            )
    else:
        out.append("  (выбывших нет)")

    out.append("\n=== ДЕЛЬТА-ПРАВИЛО (рост вглубь, без порогов) ===")
    if report["growth_deep_lines"]:
        for ln in report["growth_deep_lines"]:
            out.append(f"  {ln}")
    else:
        out.append("  (роста вглубь не обнаружено)")

    # П.2 диспатча 2026-08-28 (ось 15 карты): boot-mirror -- структурно
    # недостижимое для порога (запрещён формой), выводится из знаменателя
    # "порогов k/N" и печатается СВОИМ числом рядом, вместо молчаливого
    # вечного зазора k/(N-1). Артефакт с порогом РАЗРЕШЁННЫМ, но не
    # НАЗНАЧЕННЫМ -- отдельная строка БЕЗ ПОРОГА (находка чека 34(в),
    # видимая глазами, не вычитаемая из дроби); печатается ТОЛЬКО когда
    # такие артефакты есть (тот же приём, что WARN-строки выше -- не
    # раздувает вывод пустым "(нет)" в НОРМАЛЬНОМ (сегодняшнем) случае).
    for p in report["no_threshold_paths"]:
        out.append(f"БЕЗ ПОРОГА: {p}")

    d_sum = report["delta_sum_bytes"]
    d_sum_str = f"{d_sum:+d}" if isinstance(d_sum, int) else "—"
    out.append(
        f"\nИТОГ: сумма байт corpus={report['sum_bytes']} (Δ{d_sum_str}) · "
        f"порогов {report['assigned_k']}/{report['threshold_denominator']} · "
        f"вне порога (boot-mirror): {report['outside_threshold_boot_mirror']} · "
        f"WARN={report['warn_count']} BREACH={report['breach_count']}"
    )
    return "\n".join(out)


def measurement_to_json(m: Measurement) -> Dict[str, Any]:
    return {
        "path": m.path, "unit": m.unit, "owner": m.owner, "bpr_max": m.bpr_max,
        "exists": m.exists, "bytes": m.bytes_, "records": m.records, "bpr": m.bpr,
        "state": m.state, "reason": m.reason, "is_defect": m.is_defect,
        "decode_warn": m.decode_warn,
    }


def render_json(report: Dict[str, Any], sidecar_warn: Optional[str]) -> str:
    all_defects = list(report["form_defects"])
    for m in report["measurements"]:
        if m.is_defect:
            all_defects.append(f"ДЕФЕКТ: {m.path}: {m.reason}")
    payload = {
        "manifest_path": report["manifest_path"],
        "manifest_sha": report["manifest_sha"],
        "thresholds_version": report["thresholds_version"],
        "fixture_control": f"{report['fixture_n']}/{FIXTURE_EXPECTED}",
        "base_status": report["base_status"],
        "registry_path": report["registry_path"],
        "warnings": report["warnings"] + ([sidecar_warn] if sidecar_warn else []),
        "artifacts": [measurement_to_json(m) for m in report["measurements"]],
        "deltas": report["deltas"],
        "form_defects": all_defects,
        "departed": report["departed"],
        "growth_deep_lines": report["growth_deep_lines"],
        "totals": {
            "sum_bytes": report["sum_bytes"],
            "delta_sum_bytes": report["delta_sum_bytes"],
            "assigned_k": report["assigned_k"],
            "total_n": report["total_n"],
            # П.2 диспатча 2026-08-28: ключи ТОЛЬКО ДОБАВЛЯЮТСЯ рядом со
            # старыми assigned_k/total_n (те не переименовываются и не
            # меняют смысл -- IP1/консистентность с I3 п.1 этого же
            # диспатча). threshold_denominator -- новый знаменатель
            # "порогов k/N" (owner != boot-mirror); outside_threshold_
            # boot_mirror -- недостижимое формой рядом; no_threshold_
            # paths -- находка чека 34(в) (порог разрешён, не назначен).
            "threshold_denominator": report["threshold_denominator"],
            "outside_threshold_boot_mirror": report["outside_threshold_boot_mirror"],
            "no_threshold_paths": report["no_threshold_paths"],
            "warn_count": report["warn_count"],
            "breach_count": report["breach_count"],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_sidecar_entry(report: Dict[str, Any]) -> Dict[str, Any]:
    artifacts_map = {}
    for m in report["measurements"]:
        artifacts_map[m.path] = {
            "bytes": m.bytes_, "records": m.records, "bpr": m.bpr, "state": m.state,
        }
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "manifest_sha": report["manifest_sha"],
        "thresholds_version": report["thresholds_version"],
        "artifacts": artifacts_map,
        "totals": {
            "sum_bytes": report["sum_bytes"],
            "assigned_k": report["assigned_k"],
            "total_n": report["total_n"],
            "warn_count": report["warn_count"],
            "breach_count": report["breach_count"],
        },
    }


# ---------------------------------------------------------------------------
# --init-thresholds
# ---------------------------------------------------------------------------

INIT_THRESHOLD_FACTOR = 1.15


def render_init_thresholds(valid_artifacts: List[Artifact], measurements: List[Measurement]) -> str:
    out = ["=== ПРЕДЛОЖЕНИЕ ПОРОГОВ (замер x 1.15, Р1(D)) === "
           "(манифест НЕ правится -- запись порогов ход Lead)"]
    by_path = {m.path: m for m in measurements}
    for a in valid_artifacts:
        m = by_path.get(a.path)
        if m is None or m.bpr is None:
            out.append(f"  {a.path}: bpr недоступен ({m.state if m else 'н-д'}) -- порог не предложен")
            continue
        if a.owner == "boot-mirror":
            out.append(f"  {a.path}: boot-mirror -- порог запрещён, не предлагается")
            continue
        proposal = math.ceil(m.bpr * INIT_THRESHOLD_FACTOR)
        out.append(f"  {a.path}: замер bpr={m.bpr} -> предложение bpr_max={proposal}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    p.add_argument("--root", default=str(REPO_ROOT))
    p.add_argument("--json", action="store_true")
    p.add_argument("--check", action="store_true")
    p.add_argument("--init-thresholds", action="store_true")
    p.add_argument("--baseline-ts", default=None,
                    help="M2: prev_entry = последняя запись сайдкара с ts <= "
                         "этот ISO-момент (вместо последней записи вообще)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    root = Path(args.root)
    if not root.exists() or not root.is_dir():
        print(f"corpus_growth: --root не каталог: {root}", file=sys.stderr)
        return 2

    manifest_path = Path(args.manifest)
    registry_path = Path(args.registry)

    try:
        thresholds_version, raw_artifacts, raw_bytes = read_manifest(manifest_path)
    except ManifestError as exc:
        print(f"corpus_growth: {exc}", file=sys.stderr)
        return 2

    valid_artifacts, form_defects = validate_entries(raw_artifacts)

    if args.init_thresholds:
        measurements = [measure_artifact(root, a) for a in valid_artifacts]
        print(render_init_thresholds(valid_artifacts, measurements))
        return 0

    baseline_dt: Optional[datetime] = None
    if args.baseline_ts is not None:
        try:
            baseline_dt = datetime.fromisoformat(args.baseline_ts)
        except ValueError as exc:
            print(f"corpus_growth: --baseline-ts не ISO: {args.baseline_ts!r} ({exc})",
                  file=sys.stderr)
            return 2

    report = build_report(manifest_path, registry_path, root, baseline_dt=baseline_dt)

    # O2 (критик t-538): --check -- ТОЛЬКО измерение формы, оно не пишет
    # боевой сайдкар (образец contract calibration_prepass --check-form:
    # проверка формы не окно, см. её main()/write_registry_entry). Запись
    # сайдкара происходит ИСКЛЮЧИТЕЛЬНО в обычном (не --check) прогоне;
    # sidecar_warn=None на --check -- предупреждать нечего без попытки
    # записи (это не регресс: --check и раньше не проверял факт записи).
    if args.check:
        sidecar_warn = None
    else:
        sidecar_entry = build_sidecar_entry(report)
        sidecar_warn = write_registry_entry(registry_path, sidecar_entry)

    if args.json:
        print(render_json(report, sidecar_warn))
    else:
        print(render_text(report, sidecar_warn))

    all_defects_present = bool(report["form_defects"]) or any(
        m.is_defect for m in report["measurements"]
    )
    if args.check:
        return 1 if all_defects_present else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
