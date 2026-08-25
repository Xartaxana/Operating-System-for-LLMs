"""tools/test_p4_stdin_deadline.py -- P4 batch battery (builder, 2026-08-19,
docs/tasks/2026-08-19_p4-stdin-deadline-spec.md): stdin-deadline for the
13 hooks that used to block forever on a non-TTY read with no EOF.

FORM (образец tools/test_f61_halfstate.py / tools/test_q503_trackkeys.py,
env P4_TARGET вместо F61_TARGET/Q503_TARGET): цель разрешается через
_resolve_module_path(), которая возвращает (путь, is_unpatched). ТРИ
МИРА (координатор fix Б2, 2026-08-19 -- is_unpatched теперь РЕАЛЬНО
используется, не просто возвращается и игнорируется):
 - Мир 1 (СЕГОДНЯ, default, P4_TARGET не задан): сиблинг tools/
   <name>_p4.py, если существует (сейчас существует всегда) -- иначе
   живой. is_unpatched=False.
 - Мир 2 (P4_TARGET=live, СЕГОДНЯ, сиблинг ещё существует): ВСЕГДА
   живой tools/<name>.py -- ЗАВЕДОМО непочиненный контр-прогон.
   is_unpatched=True. P4-специфичные тесты (хелпер, дедлайн-механика,
   call-site контракт) СКИПАЮТСЯ через _load_p4()/_script_for_p4() --
   на этом таргете ассертить нечего (нет ни маркеров, ни
   _read_stdin_bytes_deadline). Единственное исключение -- world-aware
   детекторы (test_k3_stray_read_detector_world_aware, K2 negative
   control), которые именно НА is_unpatched проверяют ПОЗИТИВНЫЙ
   контроль формы (детектор находит блуждающее чтение) вместо скипа.
 - Мир 3 (ПОСЛЕ посадки Lead, сиблингов больше нет): резолвер падает на
   живой файл, который к этому моменту несёт содержимое сиблинга --
   is_unpatched=False, батарея просто проверяет живой/починенный путь
   (RERUNNABLE без правки кода, test_f61_halfstate.py:73-90 за то же
   рассуждение).
Модуль резолвится и импортируется через importlib.util (sibling-first
индирекция, не хардкод боевого пути).

Ключи спеки (docs/tasks/2026-08-19_p4-stdin-deadline-spec.md, K1-K13):
 K1  -- хелпер ровно один раз, между маркерами, перед main()/_hook_main().
 K2  -- машинная идентичность 13 регионов против ПИНА (SHA-256 хеш
        региона, вычисленный один раз с этого же дерева и захардкоженный
        здесь как _CANONICAL_REGION_SHA256 -- избегает риска транскрипции
        кириллического текста региона внутрь этого файла символ-в-символ;
        хеш -- и есть "константа тест-модуля" K2). Негативный контроль --
        test_k2_negative_control_corrupted_region_detected_then_restored
        (копия ДЕРЕВА в tmp_path, не боевой сиблинг -- командная гигиена
        п.7г: не портить боевой артефакт, если то же самое доказывает
        порча копии). Живой демонстрационный прогон с байт-копией
        РЕАЛЬНОГО сиблинга -- в отчёте builder'а (witness), не здесь.
 K3  -- хелпер -- единственная точка чтения stdin (тест-греп с позитивным
        контролем формы: ОДИН мироосознанный тест
        (test_k3_stray_read_detector_world_aware) -- на is_unpatched
        target детектор ОБЯЗАН найти хотя бы одно совпадение (позитивный
        контроль, иначе проверка вакуумна), на починенном -- ноль).
 K4  -- не-таймаутные пути не меняются -- проверяется ОТДЕЛЬНЫМ прогоном
        существующих батарей всех 13 хуков (не здесь, см. отчёт builder'а,
        витнес-пункт 2).
 K5  -- на таймауте: rc==0, stdout ПУСТ (кроме session_context -- см.
        "Поправка Lead" в спеке: read_stdin_payload() возвращает None,
        не main(), поэтому session_context печатает ОБЫЧНЫЙ (непустой)
        контекст, как на пустом входе), stderr -- одна строка с
        префиксом имени файла.
 K6  -- OSLLM_STDIN_TIMEOUT: дефолт 10.0, ветки невалидного -> дефолт,
        600 проходит, тест на каждую ветку.
 K7  -- граница (~0.8 дедлайна с закрытием -> штатный путь) и за границей
        (writer не закрыт -> завершение в дедлайн+запас).
 K8  -- TTY-guard у всех 13 (образец test_session_context.py:812-821).
 K9  -- фейки stdin без isatty работают (образец test_critic_snapshot.py:74-77).
 K10 -- session_context на байтовый хелпер + decode("utf-8","replace");
        текстовый фейк (без .buffer) остаётся совместим.
 K11 -- кросс-ссылка search_control_gate на hygiene_gate._read_stdin_bytes
        снята в сиблинге (функция удалена целиком).
 K12 -- диагностика НЕ печатается ни на одном не-таймаутном пути.
 K13 -- try-граница вызова сохранена как была (никакого НОВОГО тотального
        try не добавлено к dispatch_gate/dod_gate/main_gate, Р3а F-61).

Красная по конструкции (реальное время): K7 (in-process, контролируемый
"writer") и K5 (subprocess, реальный OS-пайп держится открытым) --
и то и другое ждёт РЕАЛЬНОЕ время до дедлайна. Длительность этой части
измерена и названа в отчёте builder'а (R11.6а: граница + за границей).

Run: python -m pytest tools/test_p4_stdin_deadline.py -q
Контр-прогон (мир 2): P4_TARGET=live python -m pytest tools/test_p4_stdin_deadline.py -q
(зелен целиком -- P4-специфичные тесты скипают через is_unpatched,
world-aware детекторы проверяют позитивный контроль). Мир 3 (после
посадки Lead, сиблингов не будет) -- см. описание выше, не отдельный
режим запуска.
"""

import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import tokenize
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
P4_TARGET = os.environ.get("P4_TARGET", "").strip().lower()
MODULE_NAMES = (
    "session_context",
    "hygiene_gate",
    "journal_echo",
    "dispatch_gate",
    "owns_gate",
    "dod_track",
    "dod_gate",
    "main_gate",
    "negative_lint",
    "claim_control_gate",
    "search_control_gate",
    "critic_snapshot",
    "tier_echo",
)

_BEGIN_MARKER = "# --- BEGIN stdin-deadline helper"
_END_MARKER = "# --- END stdin-deadline helper ---"
_STDIN_DEADLINE_MSG = "stdin deadline exceeded -- fail-open, payload discarded"

# K2: SHA-256 of the canonical helper region (BEGIN..END inclusive, universal
# newlines), computed once from this very tree and pinned here as a literal
# constant of the TEST MODULE (K2's own wording) -- a hash sidesteps any risk
# of a hand-transcription mismatch of the (Cyrillic-heavy) docstring text
# inside this file, while still giving a byte-exact identity check per
# sibling: any single-character drift in any of the 13 regions changes the
# hash, this constant does not move with them.
_CANONICAL_REGION_SHA256 = "2d23f14c7e1db1157e8a9b3c07e30820c02356c63b1da25974d8131748420ca5"
_CANONICAL_REGION_LEN = 1893


def _resolve_module_path(base_name: str) -> "tuple[Path, bool]":
    """(путь, is_unpatched) -- та же форма, что test_f61_halfstate.py /
    test_q503_trackkeys.py. is_unpatched=True означает "цель заведомо
    непочинена" и легален ТОЛЬКО в контр-режиме P4_TARGET=live при
    существующем сиблинге."""
    live = TOOLS_DIR / f"{base_name}.py"
    sibling = TOOLS_DIR / f"{base_name}_p4.py"
    if P4_TARGET == "live":
        return live, sibling.exists()
    if sibling.exists():
        return sibling, False
    return live, False


_MODULE_CACHE: dict = {}


def _load(base_name: str):
    """(module, path, is_unpatched) -- импортирует резолвленный файл через
    importlib.util (не sys.path-игру, не хардкод боевого пути)."""
    path, is_unpatched = _resolve_module_path(base_name)
    cache_key = (base_name, str(path))
    if cache_key not in _MODULE_CACHE:
        alias = f"p4_battery_{base_name}_{path.stem}"
        spec = importlib.util.spec_from_file_location(alias, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[cache_key] = (module, path, is_unpatched)
    return _MODULE_CACHE[cache_key]


# ---------------------------------------------------------------------------
# World-aware loading (coordinator fix, Б2, 2026-08-19): is_unpatched=True
# means the RESOLVED path is a target KNOWN not to carry the P4 machinery
# yet (P4_TARGET=live while a sibling still exists -- "мир 2", the
# counter-run). Every P4-SPECIFIC test (helper presence, env parsing,
# TTY/timeout mechanics, the call-site contract) has NOTHING to assert
# against on that target -- same shape as test_f61_halfstate.py's
# `if is_live: pytest.skip(...)` guard (see e.g. :338/:377), centralized
# HERE since virtually every test below needs it (previously is_unpatched
# was returned by the resolver but never actually READ anywhere -- P4_TARGET=
# live turned into ~150 hard failures instead of graceful skips). Only the
# WORLD-AWARE detector tests (K2 negative control, the merged K3 test)
# read is_unpatched directly instead of going through this skip wrapper --
# they branch ON it rather than skipping because of it.
# ---------------------------------------------------------------------------


def _load_p4(base_name: str):
    """(module, path) -- _load() + auto-skip when is_unpatched."""
    mod, path, is_unpatched = _load(base_name)
    if is_unpatched:
        pytest.skip(
            f"{base_name}: is_unpatched (P4_TARGET=live, sibling exists) -- "
            "the P4 helper does not exist on this target, nothing to assert"
        )
    return mod, path


def _script_for_p4(base_name: str) -> Path:
    _mod, path = _load_p4(base_name)
    return path


# ---------------------------------------------------------------------------
# K1/K2 helpers: locate + hash the marker region.
# ---------------------------------------------------------------------------


def _region_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    i = text.index(_BEGIN_MARKER)
    j = text.index(_END_MARKER, i) + len(_END_MARKER)
    return text[i:j]


def _region_sha256(path: Path) -> str:
    region = _region_text(path)
    return hashlib.sha256(region.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# K3 helpers: a stray stdin-read detector that ignores comments/docstrings
# (tokenize-based, not a naive substring grep -- these files' own historical
# docstrings/comments legitimately quote the OLD `sys.stdin.buffer.read()`
# call as prose; a naive grep would false-positive on those).
# ---------------------------------------------------------------------------

_STDIN_READ_RE = re.compile(r"sys\.stdin\.(buffer\.read|read|isatty)\s*\(")


def _blank_marker_block(text: str) -> str:
    """Replaces the whole BEGIN..END marker block with equal-length blank
    lines (preserves line numbers/newlines, keeps the rest syntactically
    intact) -- the canonical helper's OWN body legitimately calls
    sys.stdin.isatty()/.buffer/.read(), that's not a stray point."""
    lines = text.splitlines(keepends=True)
    out = []
    in_block = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(_BEGIN_MARKER):
            in_block = True
        if in_block:
            nl = ""
            body = line
            if body.endswith("\r\n"):
                nl = "\r\n"
                body = body[:-2]
            elif body.endswith("\n"):
                nl = "\n"
                body = body[:-1]
            out.append(" " * len(body) + nl)
        else:
            out.append(line)
        if stripped.startswith(_END_MARKER):
            in_block = False
    return "".join(out)


def _blank_comments_and_strings(text: str) -> str:
    """Blanks STRING/COMMENT token spans (docstrings, inline comments,
    quoted-code-in-prose) to spaces, keeping every other character (incl.
    line/col positions) intact -- Python's own tokenizer, not a hand-rolled
    triple-quote state machine, so it can't misparse an edge case a manual
    scanner would. Conservative fallback: if tokenize itself chokes (should
    not happen -- these files py_compile clean), returns text unchanged."""
    lines = text.splitlines(keepends=True)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except Exception:
        return text
    for tok in tokens:
        if tok.type not in (tokenize.STRING, tokenize.COMMENT):
            continue
        srow, scol = tok.start
        erow, ecol = tok.end
        if srow == erow:
            line = lines[srow - 1]
            lines[srow - 1] = line[:scol] + (" " * (ecol - scol)) + line[ecol:]
        else:
            first = lines[srow - 1]
            first_body_len = len(first.rstrip("\r\n"))
            lines[srow - 1] = first[:scol] + (" " * (first_body_len - scol)) + first[first_body_len:]
            for r in range(srow, erow - 1):
                mid = lines[r]
                body_len = len(mid.rstrip("\r\n"))
                lines[r] = (" " * body_len) + mid[body_len:]
            last = lines[erow - 1]
            lines[erow - 1] = (" " * ecol) + last[ecol:]
    return "".join(lines)


def _stray_stdin_reads(path: Path):
    """Список (line_no, line) с литералом чтения stdin ВНЕ marker-блока
    И вне комментариев/докстрингов -- K3."""
    text = path.read_text(encoding="utf-8")
    text = _blank_marker_block(text)
    text = _blank_comments_and_strings(text)
    violations = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _STDIN_READ_RE.search(line):
            violations.append((lineno, line))
    return violations


# ---------------------------------------------------------------------------
# Fakes for K7/K8/K9 in-process tests.
# ---------------------------------------------------------------------------


class _TtyStdin:
    """K8: TTY -- read() must never be called."""

    def __init__(self):
        self._read_called = False

    def isatty(self):
        return True

    def read(self):
        self._read_called = True
        raise AssertionError("read() must not be called when stdin is a TTY (K8)")


class _NoIsattyStdin:
    """K9 (образец test_critic_snapshot.py:73-77): фейк БЕЗ isatty вообще --
    только .buffer. _read_stdin_bytes_deadline()'s `except Exception: pass`
    around stdin.isatty() must swallow the AttributeError and proceed."""

    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


class _ControllableStdin:
    """Duck-stdin чей .read() блокируется до release() -- симулирует writer,
    который либо закрывает канал ДО дедлайна (release вызван вовремя), либо
    никогда не закрывает (release не вызван -> реальный таймаут, K7)."""

    def __init__(self, data: bytes = b"", tty: bool = False):
        self._data = data
        self._tty = tty
        self._release = threading.Event()
        self.buffer = self

    def isatty(self):
        return self._tty

    def read(self):
        self._release.wait(timeout=30)  # safety net: never hang a leaked thread forever
        return self._data

    def release(self):
        self._release.set()


# ---------------------------------------------------------------------------
# K1
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k1_marker_present_exactly_once_before_entry(base_name):
    _mod, path = _load_p4(base_name)
    text = path.read_text(encoding="utf-8")
    begin_count = text.count(_BEGIN_MARKER)
    end_count = text.count(_END_MARKER)
    assert begin_count == 1, f"{base_name}: BEGIN marker count={begin_count}"
    assert end_count == 1, f"{base_name}: END marker count={end_count}"
    begin_idx = text.index(_BEGIN_MARKER)
    end_idx = text.index(_END_MARKER)
    assert begin_idx < end_idx

    entry_name = "_hook_main" if "def _hook_main(" in text else "main"
    entry_idx = text.index(f"def {entry_name}(")
    assert end_idx < entry_idx, f"{base_name}: helper block must sit BEFORE {entry_name}()"


# ---------------------------------------------------------------------------
# K2
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k2_helper_region_matches_canonical_hash(base_name):
    _mod, path = _load_p4(base_name)
    region = _region_text(path)
    assert len(region) == _CANONICAL_REGION_LEN, (
        f"{base_name}: region length={len(region)}, expected {_CANONICAL_REGION_LEN}"
    )
    digest = hashlib.sha256(region.encode("utf-8")).hexdigest()
    assert digest == _CANONICAL_REGION_SHA256, (
        f"{base_name}: helper region drifted from the spec-pinned canonical text"
        f" (sha256={digest})"
    )


def test_k2_negative_control_corrupted_region_detected_then_restored(tmp_path):
    """Негативный контроль + откат байт-копией (командная гигиена п.7):
    копия ДЕРЕВА в tmp_path (не боевой сиблинг, п.7г -- порча копии
    доказывает то же самое) -- байт-копия ДО порчи, порча, КРАСНЫЙ
    детектор, восстановление ИЗ копии, witness -- хеш-сравнение.

    Координатор fix (Б2/2): путь идёт ЧЕРЕЗ РЕЗОЛВЕР
    (_resolve_module_path), не жёсткий TOOLS_DIR/"dispatch_gate_p4.py" --
    в мире 3 (после посадки, сиблингов нет) жёсткий путь дал бы
    FileNotFoundError; резолвер сам падает на живой файл, который к
    тому моменту несёт тот же регион. Под P4_TARGET=live (мир 2, регион
    ещё не существует на живом) -- skip, а не крах на text.index()."""
    src, is_unpatched = _resolve_module_path("dispatch_gate")
    if is_unpatched:
        pytest.skip("dispatch_gate: is_unpatched (P4_TARGET=live) -- no region to corrupt on this target")
    work = tmp_path / src.name
    shutil.copyfile(src, work)

    pristine_bytes = work.read_bytes()  # байт-копия ДО порчи (п.7а)
    pristine_hash = hashlib.sha256(pristine_bytes).hexdigest()
    assert hashlib.sha256(_region_text(work).encode("utf-8")).hexdigest() == _CANONICAL_REGION_SHA256

    text = work.read_text(encoding="utf-8")
    i = text.index(_BEGIN_MARKER)
    j = text.index(_END_MARKER, i)
    marker = "_STDIN_DEADLINE_DEFAULT = 10.0"
    assert marker in text[i:j]
    corrupted_region = text[i:j].replace(marker, "_STDIN_DEADLINE_DEFAULT = 99.0", 1)
    work.write_text(text[:i] + corrupted_region + text[j:], encoding="utf-8")

    # КРАСНЫЙ: детектор ловит искажение.
    corrupted_hash = hashlib.sha256(_region_text(work).encode("utf-8")).hexdigest()
    assert corrupted_hash != _CANONICAL_REGION_SHA256

    # Откат байт-копией (НЕ git checkout -- копия снята ДО порчи).
    work.write_bytes(pristine_bytes)
    restored_hash = hashlib.sha256(work.read_bytes()).hexdigest()
    assert restored_hash == pristine_hash  # witness: хеш, не слово "восстановлено"
    assert hashlib.sha256(_region_text(work).encode("utf-8")).hexdigest() == _CANONICAL_REGION_SHA256


# ---------------------------------------------------------------------------
# K3
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k3_stray_read_detector_world_aware(base_name):
    """Единый мироосознанный тест (координатор fix Б2/1): резолвит ТОТ ЖЕ
    путь, что и все остальные тесты (не отдельный жёсткий live-путь), и
    ветвится НА is_unpatched -- ровно образец test_f61_halfstate.py
    (:228 style if/else, не отдельный "positive control" тест сбоку):
     - is_unpatched=True (P4_TARGET=live, сиблинг существует -- мир,
       ЗАВЕДОМО непочиненный): детектор ОБЯЗАН найти >=1 -- это и есть
       позитивный контроль формы (доказывает детектор не вакуумен),
       здесь он относится ИМЕННО к текущему резолвленному пути, не к
       отдельному захардкоженному TOOLS_DIR/f"{base_name}.py" (который
       в мире 3, после посадки, был бы уже ПОЧИНЕН -- ложный позитив).
     - is_unpatched=False (миры 1 и 3 -- сиблинг СЕЙЧАС, либо живой
       ПОСЛЕ посадки): ноль блуждающих точек чтения -- K3 сам по себе."""
    _mod, path, is_unpatched = _load(base_name)
    violations = _stray_stdin_reads(path)
    if is_unpatched:
        assert len(violations) >= 1, (
            f"{base_name}: positive control failed -- detector found nothing on the "
            "is_unpatched (known-unfixed) target"
        )
    else:
        assert violations == [], f"{base_name}: stray stdin read(s) outside the P4 helper marker: {violations}"


@pytest.mark.parametrize("base_name", ["claim_control_gate", "search_control_gate"])
def test_k3_private_read_stdin_bytes_wrapper_removed(base_name):
    """claim_control_gate/search_control_gate имели СОБСТВЕННУЮ приватную
    `_read_stdin_bytes()` (TTY-guard + sys.stdin.buffer.read()) -- она
    удалена целиком в сиблинге, иначе это был бы ВТОРОЙ stdin-read point.
    Неприменимо на is_unpatched target (живой ДО посадки СОХРАНЯЕТ
    `_read_stdin_bytes` намеренно -- удаление живёт в сиблинге/после
    посадки) -- _load_p4 скипает эту ветку."""
    mod, _path = _load_p4(base_name)
    assert not hasattr(mod, "_read_stdin_bytes"), f"{base_name}: old private wrapper must be removed (K3)"


# ---------------------------------------------------------------------------
# K6
# ---------------------------------------------------------------------------

_K6_CASES = [
    ("", 10.0),
    ("abc", 10.0),
    ("0", 10.0),
    ("-1", 10.0),
    ("1e9", 10.0),
    ("600.1", 10.0),
    ("600", 600.0),
    ("5", 5.0),
    ("0.5", 0.5),
]


@pytest.mark.parametrize("base_name", MODULE_NAMES)
@pytest.mark.parametrize("raw_value,expected", _K6_CASES)
def test_k6_env_deadline_parsing_branches(base_name, raw_value, expected, monkeypatch):
    mod, _path = _load_p4(base_name)
    monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, raw_value)
    assert mod._stdin_deadline_seconds() == expected


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k6_env_absent_uses_default(base_name, monkeypatch):
    mod, _path = _load_p4(base_name)
    monkeypatch.delenv(mod._STDIN_DEADLINE_ENV, raising=False)
    assert mod._stdin_deadline_seconds() == mod._STDIN_DEADLINE_DEFAULT == 10.0


# ---------------------------------------------------------------------------
# K8 / K9
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k8_tty_guard_never_reads(base_name, monkeypatch):
    mod, _path = _load_p4(base_name)
    fake = _TtyStdin()
    monkeypatch.setattr(mod.sys, "stdin", fake)
    raw, timed_out = mod._read_stdin_bytes_deadline()
    assert raw == b""
    assert timed_out is False
    assert fake._read_called is False


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k9_fake_without_isatty_still_works(base_name, monkeypatch):
    mod, _path = _load_p4(base_name)
    fake = _NoIsattyStdin(b'{"a": 1}')
    monkeypatch.setattr(mod.sys, "stdin", fake)
    raw, timed_out = mod._read_stdin_bytes_deadline()
    assert timed_out is False
    assert raw == b'{"a": 1}'


# ---------------------------------------------------------------------------
# K7 (real wall-clock time, in-process -- controllable release event)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k7_boundary_release_before_deadline_returns_promptly(base_name, monkeypatch):
    mod, _path = _load_p4(base_name)
    monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, "0.6")
    fake = _ControllableStdin(data=b"payload-before-deadline")
    monkeypatch.setattr(mod.sys, "stdin", fake)
    timer = threading.Timer(0.48, fake.release)  # ~0.8 * 0.6s
    timer.start()
    t0 = time.monotonic()
    raw, timed_out = mod._read_stdin_bytes_deadline()
    elapsed = time.monotonic() - t0
    timer.cancel()
    assert timed_out is False
    assert raw == b"payload-before-deadline"
    assert elapsed < 0.6, f"{base_name}: should have returned promptly on release, took {elapsed:.3f}s"


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k7_beyond_deadline_writer_never_closes_times_out(base_name, monkeypatch):
    mod, _path = _load_p4(base_name)
    monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, "0.3")
    fake = _ControllableStdin(data=b"never delivered")
    monkeypatch.setattr(mod.sys, "stdin", fake)
    t0 = time.monotonic()
    raw, timed_out = mod._read_stdin_bytes_deadline()
    elapsed = time.monotonic() - t0
    assert timed_out is True
    assert raw == b""
    # Нижняя граница с запасом ~50ms (thread.join(timeout) на некоторых
    # платформах возвращается на сотые доли секунды РАНЬШЕ номинального
    # таймера -- не тот же класс, что "завис навсегда"; верхняя граница
    # (дедлайн+запас) -- собственно то, что K7 обязан доказать.
    assert 0.25 <= elapsed < 1.3, f"{base_name}: timeout should land within deadline+margin, took {elapsed:.3f}s"
    fake.release()  # отпускаем демон-поток, не оставляем его блокированным навсегда


# ---------------------------------------------------------------------------
# K5 / K12 (subprocess, real OS pipe)
# ---------------------------------------------------------------------------


def _run_holding_stdin_open(script: Path, deadline, extra_wait=2.0):
    """Запускает script как отдельный процесс, НЕ закрывая и НЕ записывая
    stdin -- пайп остаётся открытым (реальный "writer, который не
    закрылся"). deadline=None -> реальный дефолт (env не выставляется).

    НЕ использует Popen.communicate(): communicate() САМ закрывает
    stdin процесса сразу же (даже без input=), что даёт дочернему
    процессу немедленный EOF и полностью снимает симуляцию "writer не
    закрыл канал" -- эмпирика этой самой правки (первый прогон: rc=0,
    stderr пуст, процесс не таймаутил вообще). Вместо этого держим
    proc.stdin открытым явно и ждём выхода процесса через proc.wait()."""
    env = os.environ.copy()
    if deadline is not None:
        env["OSLLM_STDIN_TIMEOUT"] = str(deadline)
        wait_deadline = deadline
    else:
        env.pop("OSLLM_STDIN_TIMEOUT", None)
        wait_deadline = 10.0
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    # ДРЕНАЖ stdout/stderr ПАРАЛЛЕЛЬНО ожиданию (посадка D-0104, вердикт
    # критика t-595 по В5): обвязка обязана моделировать ОДИН отказ --
    # «писатель не закрыл stdin». Без дренажа она с посадкой Layer A
    # (выдача ~11 КБ > ёмкости пайпа 4096) начинала моделировать ВТОРОЙ,
    # независимый отказ -- «потребитель не читает», и тот маскировал
    # первый: стдаут-дедлайн хука истекал раньше stdin-проверки, вывод
    # пустел, K5/Ф1 краснели. Читающие потоки стартуют ДО proc.wait();
    # для модулей с малой выдачей дренаж -- no-op.
    drained: dict = {}

    def _drain(stream, key):
        try:
            drained[key] = stream.read()
        except Exception:
            drained[key] = b""

    t_out = threading.Thread(target=_drain, args=(proc.stdout, "out"), daemon=True)
    t_err = threading.Thread(target=_drain, args=(proc.stderr, "err"), daemon=True)
    t_out.start()
    t_err.start()
    try:
        proc.wait(timeout=wait_deadline + extra_wait)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    t_out.join(5.0)
    t_err.join(5.0)
    out = drained.get("out", b"")
    err = drained.get("err", b"")
    proc.stdin.close()
    proc.stdout.close()
    proc.stderr.close()
    return proc.returncode, out, err


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k12_no_diagnostic_stderr_on_empty_input(base_name):
    script = _script_for_p4(base_name)
    result = subprocess.run(
        [sys.executable, str(script)], input=b"", capture_output=True, timeout=15
    )
    assert result.returncode == 0
    assert result.stderr == b"", f"{base_name}: unexpected stderr on empty (non-timeout) input: {result.stderr!r}"


_SHORT_DEADLINE = 1.0

# session_context, unlike the other 12, does substantial ADDITIONAL work
# after a stdin timeout (quota/wiring/boot-budget lines, incl. git
# subprocess.run() calls in git_hooks_channel()/_try_hookspath_autofix()
# AND, transitively, wiring_check(_p4).skills_casing_channel()). FIXED
# (Ф1, coordinator + critic empirics, 2026-08-19): those calls used to
# inherit a stuck/unclosed stdin pipe on the timeout path and stall for
# their own full timeout=5 EACH (observed before the fix: ~10-15s extra) --
# now all four carry stdin=subprocess.DEVNULL (see session_context_p4.py
# and the new wiring_check_p4.py sibling), measured ~1-2s extra post-fix.
# The margin below is generous headroom, not a workaround for a live bug.
_SESSION_CONTEXT_EXTRA_WAIT = 8.0


def _normalize_newlines(data: bytes) -> bytes:
    """Windows text-mode stderr/stdout translate '\\n' -> '\\r\\n' on WRITE;
    subprocess.Popen(..., stderr=PIPE) without text=True captures the RAW
    bytes as the child wrote them -- normalize before an exact-content
    comparison (same class as this repo's own text=True-mode tests, which
    get this handled for them by subprocess itself)."""
    return data.replace(b"\r\n", b"\n")


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_k5_timeout_rc_stderr_stdout_contract_short_deadline(base_name):
    script = _script_for_p4(base_name)
    extra_wait = _SESSION_CONTEXT_EXTRA_WAIT if base_name == "session_context" else 2.0
    rc, out, err = _run_holding_stdin_open(script, deadline=_SHORT_DEADLINE, extra_wait=extra_wait)
    assert rc == 0, f"{base_name}: rc={rc}, stderr={err!r}"
    expected_stderr = f"{script.name}: {_STDIN_DEADLINE_MSG}\n".encode("utf-8")
    assert _normalize_newlines(err) == expected_stderr, f"{base_name}: stderr={err!r}"
    if base_name == "session_context":
        # Lead's dispatch-time note: session_context's read_stdin_payload()
        # returns None on timeout, main() does NOT abort -- same as its own
        # empty-input path, which prints the FULL context, not nothing.
        assert out != b"", f"{base_name}: must still print the full context on a stdin timeout"
        assert b"NOW:" in out
    else:
        assert out == b"", f"{base_name}: stdout must be empty on a stdin timeout, got {out!r}"


@pytest.mark.parametrize("base_name", ["dispatch_gate", "session_context"])
def test_k5_timeout_with_real_default_deadline_no_override(base_name):
    """Доказывает, что ШИПНУТЫЙ дефолт (10.0, БЕЗ env override) реально
    работает end-to-end, не только под укороченным тестовым дедлайном."""
    script = _script_for_p4(base_name)
    extra_wait = _SESSION_CONTEXT_EXTRA_WAIT if base_name == "session_context" else 2.0
    rc, out, err = _run_holding_stdin_open(script, deadline=None, extra_wait=extra_wait)
    assert rc == 0
    expected_stderr = f"{script.name}: {_STDIN_DEADLINE_MSG}\n".encode("utf-8")
    assert _normalize_newlines(err) == expected_stderr
    if base_name == "session_context":
        assert out != b"" and b"NOW:" in out
    else:
        assert out == b""


# ---------------------------------------------------------------------------
# K10 -- session_context specifics
# ---------------------------------------------------------------------------


def test_k10_session_context_byte_read_with_buffer_fake(monkeypatch):
    mod, _path = _load_p4("session_context")
    fake = _NoIsattyStdin(json.dumps({"model": "claude-opus-4"}).encode("utf-8"))
    monkeypatch.setattr(mod.sys, "stdin", fake)
    assert mod.read_stdin_payload() == {"model": "claude-opus-4"}


def test_k10_session_context_text_only_fake_still_works(monkeypatch):
    """Текстовый фейк (только .read() -> str, БЕЗ .buffer) -- тот же
    класс, что test_f61_halfstate.py's _FakeTextStdin (:971-984): P4's
    _read_stdin_bytes_deadline() falls back to `stream = stdin` (no
    .buffer attr) and coerces the returned str via .encode("utf-8",
    "replace") -- двухмирная совместимость K10."""
    mod, _path = _load_p4("session_context")

    class _TextOnlyStdin:
        def __init__(self, text):
            self._text = text

        def isatty(self):
            return False

        def read(self):
            return self._text

    fake = _TextOnlyStdin('{"model": "claude-sonnet-4"}')
    monkeypatch.setattr(mod.sys, "stdin", fake)
    assert mod.read_stdin_payload() == {"model": "claude-sonnet-4"}


def test_k10_session_context_nondict_root_returns_none(monkeypatch):
    mod, _path = _load_p4("session_context")
    fake = _NoIsattyStdin(b"[1, 2, 3]")
    monkeypatch.setattr(mod.sys, "stdin", fake)
    assert mod.read_stdin_payload() is None


def test_k10_session_context_tty_returns_none_instantly(monkeypatch):
    mod, _path = _load_p4("session_context")
    fake = _TtyStdin()
    monkeypatch.setattr(mod.sys, "stdin", fake)
    assert mod.read_stdin_payload() is None
    assert fake._read_called is False


def test_k10_session_context_timeout_returns_none_and_writes_stderr(monkeypatch):
    mod, _path = _load_p4("session_context")
    fake = _ControllableStdin(data=b"never delivered")
    monkeypatch.setattr(mod.sys, "stdin", fake)
    monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, "0.2")
    fake_stderr = io.StringIO()
    monkeypatch.setattr(mod.sys, "stderr", fake_stderr)
    assert mod.read_stdin_payload() is None
    assert "stdin deadline exceeded" in fake_stderr.getvalue()
    fake.release()


# ---------------------------------------------------------------------------
# Ф1 -- session_context wiring on a real stdin timeout (координатор,
# критик-эмпирика 2026-08-19). BEFORE the stdin=subprocess.DEVNULL fix: a
# real unclosed stdin pipe on the timeout path was inherited by EVERY git
# subprocess.run() call reached afterward -- not just the three inside
# session_context_p4.py's own git_hooks_channel()/_try_hookspath_autofix(),
# but ALSO the one inside wiring_check.py's skills_casing_channel() (called
# transitively via wiring_lines()'s dynamic `import wiring_check`) -- each
# stalling for its own full timeout=5 and printing a FALSE "WIRING WARNING:
# ... TimeoutExpired" line, even though nothing is actually broken. Fixed on
# ALL FOUR calls: three directly in session_context_p4.py, the fourth via
# a NEW wiring_check_p4.py sibling (same stdin=DEVNULL addition, imported
# in preference to live wiring_check -- see both files' own docstrings).
# ---------------------------------------------------------------------------


def test_f1_session_context_timeout_no_false_wiring_warning():
    """rc=0, no false 'WIRING WARNING: ... TimeoutExpired' line, a healthy
    'WIRING: OK' line present -- real subprocess, real held-open stdin pipe
    (same harness as the K5 tests), short deadline to keep this fast."""
    script = _script_for_p4("session_context")
    rc, out, _err = _run_holding_stdin_open(script, deadline=1.0, extra_wait=8.0)
    assert rc == 0
    out_text = out.decode("utf-8", "replace")
    wiring_lines = [ln for ln in out_text.splitlines() if "WIRING" in ln]
    warning_lines = [ln for ln in wiring_lines if "WARNING" in ln]
    assert warning_lines == [], f"false WIRING WARNING line(s) on the stdin-timeout path: {warning_lines!r}"
    assert any(ln.startswith("WIRING: OK") for ln in wiring_lines), (
        f"expected a healthy 'WIRING: OK' line, got: {wiring_lines!r}"
    )


# ---------------------------------------------------------------------------
# K11 + named deviation -- search_control_gate specifics
# ---------------------------------------------------------------------------


def test_k11_cross_reference_removed_in_sibling():
    _mod, path = _load_p4("search_control_gate")
    text = path.read_text(encoding="utf-8")
    assert "hygiene_gate.py's `_read_stdin_bytes`" not in text


def test_named_deviation_search_control_gate_process_not_called_on_timeout(monkeypatch):
    """Края спеки: на ТАЙМАУТЕ _process НЕ зовётся -- единственное
    расхождение от пустого-входа-пути (который _process ЗОВЁТ)."""
    mod, _path = _load_p4("search_control_gate")
    calls = []
    monkeypatch.setattr(mod, "_process", lambda payload, raw: calls.append((payload, raw)))
    fake = _ControllableStdin(data=b"irrelevant")
    monkeypatch.setattr(mod.sys, "stdin", fake)
    monkeypatch.setenv(mod._STDIN_DEADLINE_ENV, "0.2")
    rc = mod.main()
    assert rc == 0
    assert calls == [], "search_control_gate must NOT call _process on a stdin timeout (named deviation)"
    fake.release()


def test_search_control_gate_empty_input_still_calls_process_unchanged(monkeypatch):
    """Регресс: НЕ-таймаутный пустой вход по-прежнему зовёт _process --
    расхождение Края касается ИМЕННО таймаута, не пустого входа вообще."""
    mod, _path = _load_p4("search_control_gate")
    calls = []
    monkeypatch.setattr(mod, "_process", lambda payload, raw: calls.append((payload, raw)))
    fake = _NoIsattyStdin(b"")
    monkeypatch.setattr(mod.sys, "stdin", fake)
    rc = mod.main()
    assert rc == 0
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# K13 -- no NEW total try around dispatch_gate/dod_gate/main_gate (Р3а F-61)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", ["dispatch_gate", "dod_gate", "main_gate"])
def test_k13_no_total_try_added_r3a(base_name):
    _mod, path = _load_p4(base_name)
    text = path.read_text(encoding="utf-8")
    after_helper = text.split(_END_MARKER, 1)[1]
    main_body = after_helper.split("def main() -> int:", 1)[1]
    # Непустые, НЕКОММЕНТАРНЫЕ строки тела main() (комментарий над
    # вызовом -- легальная call-site аннотация, не структурная правка).
    lines = [
        l.strip() for l in main_body.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    assert lines[0].startswith("_reconfigure_stderr_utf8()"), f"{base_name}: {lines[0]!r}"
    assert lines[1].startswith("raw_bytes, timed_out = _read_stdin_bytes_deadline()"), (
        f"{base_name}: {lines[1]!r} -- a NEW total try must not sit between reconfigure and the read call"
    )


# ---------------------------------------------------------------------------
# Import hygiene: threading present in every sibling (structural, cheap).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_threading_module_imported(base_name):
    mod, _path = _load_p4(base_name)
    assert hasattr(mod, "threading")
    assert mod.threading.__name__ == "threading"
