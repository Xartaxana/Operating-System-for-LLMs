"""tools/test_negative_lint_md.py -- батарея сиблинга
tools/negative_lint_md.py (этап 2, СПЕКА B, партия 1, t-509 / docs/tasks/
2026-08-19_md-regions-scanner-spec.md). MODULE UNDER TEST переключается
переменной окружения MODULE_UNDER_TEST (образец конвенции F61_TARGET,
tools/test_f61_halfstate.py): default -> сиблинг tools/negative_lint_md.py
(region-aware); MODULE_UNDER_TEST=live -> живой tools/negative_lint.py
БЕЗ единой правки (тот же файл, что и test_negative_lint.py уже
покрывает) -- используется здесь ТОЛЬКО как цель негативного контроля
дискриминации (§8 п.4 драфта): region-специфичные assert'ы, зелёные на
сиблинге, обязаны стать КРАСНЫМИ на живой (нерегионной) цели.

Модуль резолвится через importlib.util по явному пути (не sys.path-игру
и не хардкод боевого пути в константе) -- сиблинг и живой файл РАЗНЫЕ
имена (negative_lint_md.py / negative_lint.py), поэтому обычный
`import negative_lint_md` не смог бы переключиться на живой файл под тем
же именем модуля; та же индирекция, что test_f61_halfstate.py._load().

Существующий tools/test_negative_lint.py (батарея живого файла) НЕ
ТРОГАЕТСЯ этим диспатчем -- прогоняется отдельно как подтверждение
"живой не задет" (см. отчёт билдера, DoD п.3).

Run (дефолт, сиблинг):    python -m pytest tools/test_negative_lint_md.py -q
Контр-прогон (дискриминация): MODULE_UNDER_TEST=live python -m pytest
    tools/test_negative_lint_md.py -q -k discrimination
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from wallclock_guard import WALLCLOCK_CATASTROPHE_CEILING  # noqa: E402

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # f61-форма (правка Lead при посадке партии 1): default — сиблинг,
    # ЕСЛИ он существует, иначе живой файл; после посадки байт-копией
    # default-прогон не падает на FileNotFoundError.
    if MODULE_UNDER_TEST == "live":
        return TOOLS_DIR / "negative_lint.py"
    sibling = TOOLS_DIR / "negative_lint_md.py"
    return sibling if sibling.exists() else TOOLS_DIR / "negative_lint.py"


SCRIPT = _resolve_script_path()


def _load_module():
    alias = f"negative_lint_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module()

_REGION_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live",
    reason="region API (m.scan/_classify/_safe_scan/_region_at) exists only "
    "on the sibling; MODULE_UNDER_TEST=live targets tools/negative_lint.py "
    "verbatim, which has none of it",
)


def _agent_payload(text) -> dict:
    return {"tool_name": "Task", "tool_input": {}, "tool_response": text}


def _run_hook(raw_input, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        **kwargs,
    )


# ---------------------------------------------------------------------
# И-0: любой отказ md_regions -> сторож ведёт себя КАК СЕГОДНЯ побайтно
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i0_scan_raises_falls_back_to_today_behavior(monkeypatch):
    """monkeypatch-подмена scan на бросающую (буквальная форма из спеки).
    Текст, где регион РЕАЛЬНО меняет результат (см.
    test_discrimination_* ниже) -- при сломанном scan() сторож обязан
    вести себя КАК ЖИВОЙ negative_lint.py (контроль в цитате гасит --
    т.е. НЕТ нарушений), не как region-aware сиблинг (который бы нашёл
    1 нарушение)."""

    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    text = (
        "Файл config.yaml не найден в репозитории.\n"
        "> Пример чужого отчёта: контроль пройден успешно.\n"
    )
    violations = m.find_violations(text)
    assert violations == []  # побайтно как живой файл: цитируемый контроль гасит


@_REGION_ONLY
def test_i0_scan_degraded_falls_back_to_today_behavior(monkeypatch):
    """Второй триггер И-0 -- scan() не бросает, а возвращает
    degraded=True (напр. лимит превышен). Тот же побайтный фоллбек."""

    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    text = (
        "Файл config.yaml не найден в репозитории.\n"
        "> Пример чужого отчёта: контроль пройден успешно.\n"
    )
    violations = m.find_violations(text)
    assert violations == []


# ---------------------------------------------------------------------
# И-1: сканер зовётся только после дешёвого предфильтра (ленивость)
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i1_scan_not_called_when_no_negative_marker(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    text = "Всё найдено, файл существует, задача выполнена штатно."
    violations = m.find_violations(text)
    assert violations == []
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_called_exactly_once_when_negative_marker_present(monkeypatch):
    """Позитивный контроль той же формы (командная гигиена п.6): та же
    подмена-счётчик, тот же текст-класс, но С негативным маркером --
    scan() обязан вызваться (иначе нулевой счётчик выше доказывал бы не
    ленивость, а сломанный вызов)."""
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    text = "Проверил каталог docs/book -- не существует такого пути."
    violations = m.find_violations(text)
    assert len(violations) == 1
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# B1 политика: fenced/blockquote -- не нарушение, inline_code -- нарушение
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_b1_negative_inside_fenced_block_is_not_a_violation():
    text = (
        "Пример из чужого отчёта:\n"
        "```\n"
        "Файл не найден в директории.\n"
        "```\n"
    )
    assert m.find_violations(text) == []


@_REGION_ONLY
def test_b1_negative_inside_blockquote_is_not_a_violation():
    text = "> Файл не найден в директории.\n"
    assert m.find_violations(text) == []


@_REGION_ONLY
def test_b1_negative_inside_inline_code_is_a_violation():
    text = "Смотри пример: `файл не найден в каталоге` — вот так.\n"
    violations = m.find_violations(text)
    assert len(violations) == 1


@_REGION_ONLY
def test_b1_negative_in_plain_prose_is_still_a_violation_regression():
    text = "Такого файла не существует в репозитории."
    violations = m.find_violations(text)
    assert len(violations) == 1


@_REGION_ONLY
def test_b1_unterminated_fence_treated_as_prose_is_a_violation():
    """A5/§5(в) urok "silence looks like success" -- незакрытый фенс НЕ
    расширяет зону молчания, содержимое считается прозой."""
    text = "```\nФайл не найден.\n"
    violations = m.find_violations(text)
    assert len(violations) == 1


# ---------------------------------------------------------------------
# ПОЗИЦИОННЫЙ ИНВАРИАНТ: окно ±3 по исходным индексам строк
# ---------------------------------------------------------------------


def test_control_exactly_3_lines_away_triggers_window_suppresses_warn():
    lines = [
        "filler line 1",
        "filler line 2",
        "filler line 3",
        "0 matches found in the search.",
        "filler line A",
        "filler line B",
        "control: known-present sample checked same form.",
    ]
    text = "\n".join(lines)
    violations = m.find_violations(text)
    assert violations == []


def test_control_4_lines_away_does_not_trigger_window_warn_remains():
    lines = [
        "filler line 1",
        "filler line 2",
        "filler line 3",
        "0 matches found in the search.",
        "filler line A",
        "filler line B",
        "filler line C",
        "control: known-present sample checked same form.",
    ]
    text = "\n".join(lines)
    violations = m.find_violations(text)
    assert len(violations) == 1
    assert violations[0][0] == 4


# ---------------------------------------------------------------------
# НЕГАТИВНЫЙ КОНТРОЛЬ ДИСКРИМИНАЦИИ (§8 п.4 драфта, обязателен)
# ---------------------------------------------------------------------


def test_discrimination_control_in_quote_does_not_silence_prose_negative():
    """С регион-фильтром (дефолт, сиблинг) цитируемое "контроль ..." НЕ
    гасит реальное нарушение в прозе -- assert ниже ЗЕЛЁН. Без регион-
    фильтра (MODULE_UNDER_TEST=live python -m pytest
    tools/test_negative_lint_md.py -q -k
    test_discrimination_control_in_quote_does_not_silence_prose_negative)
    substring-поиск живого алгоритма НАХОДИТ "контрол" внутри цитаты и
    гасит нарушение -- тот же assert становится КРАСНЫМ на live-цели, что
    и требуется §8 п.4 (обе половины -- красная и зелёная -- дословно в
    witness отчёта билдера)."""
    text = (
        "Файл config.yaml не найден в репозитории.\n"
        "> Пример чужого отчёта: контроль пройден успешно.\n"
    )
    violations = m.find_violations(text)
    assert len(violations) == 1
    assert violations[0][0] == 1


# ---------------------------------------------------------------------
# Регрессия базового поведения (оба таргета: сиблинг И живой)
# ---------------------------------------------------------------------


def test_decide_non_agent_tool_is_silent():
    payload = {"tool_name": "Bash", "tool_response": "файл не найден"}
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is None


def test_decide_text_without_negatives_is_silent():
    text = "Всё найдено, файл существует, задача выполнена штатно."
    exit_code, output = m.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_marker_case_insensitive_and_mid_word_otsutstvuet():
    text = "Файл ОТСУТСТВУЕТ в каталоге проекта."
    violations = m.find_violations(text)
    assert len(violations) == 1


def test_zakryto_form_suppresses_warn():
    text = (
        "Файл не найден по указанному пути.\n"
        "ЗАКРЫТО: проверено позитивным прогоном на заведомо существующем файле той же формы.\n"
    )
    exit_code, output = m.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_decide_async_launched_payload_is_silent():
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "isAsync": True,
            "status": "async_launched",
            "prompt": "Проверь: файл не найден нигде не встречается без контроля.",
        },
    }
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# Адверсариальная батарея (subprocess, hook-путь)
# ---------------------------------------------------------------------


def test_cli_broken_json_stdin_exit0_silent():
    result = _run_hook(b"{not valid json")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_empty_stdin_exit0_silent():
    result = _run_hook(b"")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_payload_without_tool_response_exit0_silent():
    payload = {"tool_name": "Task", "tool_input": {}}
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_nested_content_object_result_detected():
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "content": [
                {"type": "text", "text": "Проверка docs/book: каталог не существует."},
            ]
        },
    }
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    assert result.returncode == 0
    out = json.loads(result.stdout.decode("utf-8"))
    assert "NEGATIVE LINT" in out["hookSpecificOutput"]["additionalContext"]


def test_cli_1mb_text_no_catastrophic_blowup():
    line = "просто обычная строка отчёта без маркеров нужной длины для объёма. " * 3
    big_text = (line + "\n") * 15000
    assert len(big_text.encode("utf-8")) > 1_000_000
    payload = {"tool_name": "Task", "tool_response": big_text}
    started = time.perf_counter()
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    elapsed = time.perf_counter() - started
    assert result.returncode == 0
    assert elapsed < WALLCLOCK_CATASTROPHE_CEILING, (
        f"took {elapsed:.2f}s -- сторож стенных часов (F-60)"
    )


def test_cli_non_utf8_bytes_exit0_no_traceback():
    result = _run_hook(b"\xff\xfe\x00\x01not json either")
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr


def test_cli_emoji_unicode_no_crash():
    payload = {"tool_name": "Task", "tool_response": "Готово 🎉 файл не найден 🔎 нигде не встречается"}
    result = _run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert result.returncode == 0
    out = json.loads(result.stdout.decode("utf-8"))
    assert "NEGATIVE LINT" in out["hookSpecificOutput"]["additionalContext"]


def test_cli_text_mode_warns_on_negative_without_control(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("Такого файла не существует в репозитории.", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", str(f)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert b"NEGATIVE LINT" in result.stdout


def test_cli_text_mode_silent_on_clean_text(tmp_path):
    f = tmp_path / "report.txt"
    f.write_text("Всё найдено и подтверждено штатно.", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", str(f)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_text_mode_missing_file_exit0_no_traceback(tmp_path):
    missing = tmp_path / "does_not_exist_at_all.txt"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", str(missing)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr
