"""tools/test_claim_control_gate_md.py -- батарея сиблинга
tools/claim_control_gate_md.py (этап 2, СПЕКА B, партия 1, t-509 / docs/
tasks/2026-08-19_md-regions-scanner-spec.md). MODULE UNDER TEST
переключается переменной окружения MODULE_UNDER_TEST (образец конвенции
F61_TARGET, tools/test_f61_halfstate.py): пусто/не задано -> сиблинг
tools/claim_control_gate_md.py, ЕСЛИ он существует, иначе МОЛЧА живой
tools/claim_control_gate.py (temporal-край 5.4, поведение неизменно);
MODULE_UNDER_TEST=live -> живой tools/claim_control_gate.py БЕЗ единой
правки -- используется здесь ТОЛЬКО как цель негативного контроля
дискриминации (§8 п.4 драфта): region-специфичные assert'ы, зелёные на
сиблинге, обязаны стать КРАСНЫМИ на живой (нерегионной) цели; ЛЮБОЕ
ДРУГОЕ непустое значение (например MODULE_UNDER_TEST=sibling) -- сиблинг
ЗАПРОШЕН ЯВНО, при его отсутствии ГРОМКИЙ КРАС (pytest.fail, называющий
запрошенный путь), не тихая подмена живым (K1, docs/tasks/
2026-08-25_queue8-mechbatch-spec.md).

Существующий tools/test_claim_control_gate.py (батарея живого файла,
включая t-022/F5 пины) НЕ ТРОГАЕТСЯ этим диспатчем -- прогоняется
отдельно как подтверждение "живой не задет" (см. отчёт билдера, DoD п.3).

Run (дефолт, сиблинг):    python -m pytest tools/test_claim_control_gate_md.py -q
Контр-прогон (дискриминация): MODULE_UNDER_TEST=live python -m pytest
    tools/test_claim_control_gate_md.py -q -k discrimination
"""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # f61-форма (temporal-край 5.4): default (MODULE_UNDER_TEST пуст) --
    # сиблинг, ЕСЛИ он существует, иначе живой файл, МОЛЧА (поведение как
    # сегодня; после посадки байт-копией default-прогон не падает
    # FileNotFoundError). Сиблинг ЗАПРОШЕН ЯВНО (MODULE_UNDER_TEST задан и
    # НЕ "live") -- при отсутствии сиблинга ГРОМКИЙ КРАС, не тихая подмена
    # живым (K1, docs/tasks/2026-08-25_queue8-mechbatch-spec.md).
    live = TOOLS_DIR / "claim_control_gate.py"
    if MODULE_UNDER_TEST == "live":
        return live
    sibling = TOOLS_DIR / "claim_control_gate_md.py"
    if MODULE_UNDER_TEST == "":
        return sibling if sibling.exists() else live
    if not sibling.exists():
        pytest.fail(
            f"MODULE_UNDER_TEST={MODULE_UNDER_TEST!r} requested sibling "
            f"{sibling} but it does not exist -- no silent live fallback (K1)"
        )
    return sibling


SCRIPT = _resolve_script_path()


def _load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load(SCRIPT, f"claim_control_gate_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}")
# Живой модуль загружается ВСЕГДА (не зависит от MODULE_UNDER_TEST) --
# нужен для позиционного инварианта (сверка пяти регексов байт-в-байт),
# независимо от того, какая цель выбрана основной батареей.
_LIVE = _load(TOOLS_DIR / "claim_control_gate.py", "claim_control_gate_live_reference")

_REGION_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live",
    reason="region API (m.scan/_classify/_safe_scan/_find_claim_token_groups "
    "2-arg form) exists only on the sibling; MODULE_UNDER_TEST=live targets "
    "tools/claim_control_gate.py verbatim, which has none of it",
)


def _run_hook(payload, ledger_dir=None, raw_input=None):
    env = os.environ.copy()
    if ledger_dir is not None:
        env["SEARCH_CONTROL_GATE_LEDGER_DIR"] = str(ledger_dir)
    else:
        env.pop("SEARCH_CONTROL_GATE_LEDGER_DIR", None)
    if raw_input is not None:
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=raw_input,
            capture_output=True,
            env=env,
        )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _write_ledger(ledger_dir, session, terms):
    ledger_dir = Path(ledger_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{session}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for term in terms:
            fh.write(
                json.dumps(
                    {"ts": "2026-08-19T00:00:00", "tool": "Grep", "term": term, "empty": False},
                    ensure_ascii=False,
                )
                + "\n"
            )


def _isolated_empty_ledger_dir():
    """Свежий пустой каталог-леджер вне репозитория -- для in-process
    decide()-тестов (И-0/И-1 monkeypatch не виден дочернему процессу,
    см. test_i0_scan_raises_falls_back_to_today_behavior), чтобы не
    подхватить реальный logs/.search-ledger этого репозитория."""
    import tempfile

    return Path(tempfile.mkdtemp(prefix="claim_control_gate_md_test_"))


def _write_payload(path, text, session_id="sess-1"):
    return {
        "session_id": session_id,
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": text},
    }


# ---------------------------------------------------------------------
# ПОЗИЦИОННЫЙ ИНВАРИАНТ: пять граничных регексов не меняются ни байтом
# ---------------------------------------------------------------------


def test_five_boundary_regex_patterns_byte_identical_to_live():
    names = (
        "_SENTENCE_PUNCT_RE",
        "_PARAGRAPH_BREAK_RE",
        "_LIST_ITEM_BOUNDARY_RE",
        "_TABLE_ROW_BOUNDARY_RE",
        "_HEADING_BOUNDARY_RE",
    )
    for name in names:
        sibling_pattern = getattr(m, name).pattern
        live_pattern = getattr(_LIVE, name).pattern
        assert sibling_pattern == live_pattern, f"{name} diverged from the live module"
    assert len(m._BOUNDARY_RES) == len(_LIVE._BOUNDARY_RES) == 5


# ---------------------------------------------------------------------
# И-0: любой отказ md_regions -> сторож ведёт себя КАК СЕГОДНЯ побайтно
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i0_scan_raises_falls_back_to_today_behavior(monkeypatch, tmp_path):
    """Подмена в подпроцессе (_run_hook) не видна модулю дочернего
    процесса (у него свой fresh import) -- поэтому здесь decide()
    вызывается ПРЯМО В ПРОЦЕССЕ теста, на том же объекте `m`, что и
    monkeypatch патчит (та же индирекция, что test_negative_lint_md.py
    уже использует для find_violations())."""

    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    # побайтно как живой файл: цитируемый токен ВСЁ РАВНО засчитан
    assert output is not None
    assert "RELATED_WORK" in output["hookSpecificOutput"]["additionalContext"]


@_REGION_ONLY
def test_i0_scan_degraded_falls_back_to_today_behavior(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is not None
    assert "RELATED_WORK" in output["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------
# И-1 / B2: сканер зовётся после path-scoping и маркер-хита (ленивость)
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i1_scan_not_called_when_no_marker_hit(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload("docs/notes.md", "Everything found and verified, all present.")
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert output is None
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_called_when_marker_hit_present(monkeypatch):
    """Позитивный контроль той же формы (командная гигиена п.6): тот же
    счётчик, но с реальным негативным маркером -- scan() обязан
    вызваться хотя бы раз."""
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    monkeypatch.setenv("SEARCH_CONTROL_GATE_LEDGER_DIR", str(_isolated_empty_ledger_dir()))
    payload = _write_payload("docs/notes.md", "The file docs/RELATED_WORK.md does not exist.")
    exit_code, output = m.decide(payload)
    assert exit_code == 0
    assert calls["n"] >= 1


# ---------------------------------------------------------------------
# B2 политика: fenced/blockquote не порождают окно и не засчитывают
# токены; inline_code засчитывается
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_b2_marker_inside_blockquote_produces_no_window(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md does not exist anywhere in this repo.\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


@_REGION_ONLY
def test_b2_marker_inside_fenced_block_produces_no_window(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "```\ndocs/RELATED_WORK.md does not exist anywhere in this repo.\n```\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


@_REGION_ONLY
def test_b2_marker_inside_inline_code_still_counts(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "The claim `docs/RELATED_WORK.md does not exist` was made without checking.\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


@_REGION_ONLY
def test_b2_marker_in_prose_satisfied_by_ledger_search_still_silences(tmp_path):
    """Регрессия: policy не задевает уже существующий путь корреляции с
    ledger -- прозаичный маркер + токен, ЗАСЧитанные позитивным поиском
    в сессии, по-прежнему тихие."""
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["RELATED_WORK"])
    payload = _write_payload("docs/notes.md", "docs/RELATED_WORK.md does not exist.")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


@_REGION_ONLY
def test_b2_token_inside_quote_not_counted_even_when_marker_in_prose(tmp_path):
    """Marker сам в прозе (проходит региона-гейт на уровне окна), но
    ЕДИНСТВЕННЫЙ токен претензии сидит в цитате прямо перед ним (t-022-
    класс "перенос строки не разбивает предложение" -- ни один из пяти
    существующих регексов не считает начало цитаты границей, окно
    штатно захватывает обе строки как одно "предложение") -- регион-
    фильтр обязан исключить ИМЕННО ТОКЕН (не всё окно) -- "не
    засчитывают токены" отдельно от "не порождают окно"."""
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# НЕГАТИВНЫЙ КОНТРОЛЬ ДИСКРИМИНАЦИИ (§8 п.4 драфта, обязателен)
# ---------------------------------------------------------------------


def test_discrimination_marker_inside_quote_produces_no_window(tmp_path):
    """С регион-фильтром (дефолт, сиблинг) маркер внутри цитаты не
    порождает окно вовсе -- assert ниже ЗЕЛЁН (пусто на stdout). Без
    регион-фильтра (MODULE_UNDER_TEST=live python -m pytest
    tools/test_claim_control_gate_md.py -q -k
    test_discrimination_marker_inside_quote_produces_no_window) живой
    алгоритм считает это обычным маркером в обычном предложении и
    флагает непроверенный токен -- тот же assert становится КРАСНЫМ на
    live-цели, что и требуется §8 п.4 (обе половины -- красная и
    зелёная -- дословно в witness отчёта билдера)."""
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md does not exist anywhere in this repo.\n",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_discrimination_token_inside_quote_not_counted(tmp_path):
    """Тот же класс на уровне ТОКЕНА, не маркера -- см. докстринг
    test_b2_token_inside_quote_not_counted_even_when_marker_in_prose.
    Красный контр-прогон:
    MODULE_UNDER_TEST=live python -m pytest
    tools/test_claim_control_gate_md.py -q -k
    test_discrimination_token_inside_quote_not_counted"""
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "> docs/RELATED_WORK.md\ndoes not exist in this deploy.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# Регрессия базового поведения (оба таргета: сиблинг и живой)
# ---------------------------------------------------------------------


def test_f5_regression_empty_ledger_warns_related_work_smoke(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("docs/notes.md", "docs/RELATED_WORK.md does not exist.")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_vault_path_out_of_scope_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("vault/notes.md", "docs/RELATED_WORK.md does not exist.")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_non_edit_write_tool_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_input": {"command": "echo docs/RELATED_WORK.md does not exist"},
    }
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_exit_zero_on_malformed_json(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"{not valid json")
    assert result.returncode == 0


def test_exit_zero_on_non_dict_payload(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"[1, 2, 3]")
    assert result.returncode == 0


def test_adversarial_invalid_utf8_bytes_no_crash(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"\xff\xfe\x00\x01not json either")
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr
