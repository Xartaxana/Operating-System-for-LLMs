"""tools/test_owns_gate_md.py -- батарея сиблинга tools/owns_gate_md.py
(этап 2, партия 2, узел D, t-530 / docs/tasks/2026-08-19_scanner-party2-
spec.md). MODULE UNDER TEST переключается переменной окружения
MODULE_UNDER_TEST (образец конвенции F61_TARGET, tools/test_f61_
halfstate.py, и уже применённой формы tools/test_negative_lint_md.py
:43-64): default -> сиблинг tools/owns_gate_md.py (region-aware);
MODULE_UNDER_TEST=live -> живой tools/owns_gate.py БЕЗ единой правки --
используется здесь ТОЛЬКО как цель негативного контроля дискриминации
(§8 п.4 драфта партии 1, тот же принцип применён к узлу D): region-
специфичные assert'ы, зелёные на сиблинге, обязаны стать КРАСНЫМИ на
живую (нерегионную) цель.

Модуль резолвится через importlib.util по явному пути (сиблинг и живой
файл -- РАЗНЫЕ имена, owns_gate_md.py / owns_gate.py) -- та же индирекция,
что test_negative_lint_md.py._load_module().

Существующий tools/test_owns_gate.py (батарея живого файла) НЕ ТРОГАЕТСЯ
этим диспатчем -- прогоняется отдельно как подтверждение "живой не
задет" (DoD п.3), и ЕЩЁ РАЗ -- equivalence-run -- на КОПИИ дерева с
сиблингом под живым именем (DoD п.4, отдельная команда, см. отчёт
билдера).

Run (дефолт, сиблинг):        python -m pytest tools/test_owns_gate_md.py -q
Контр-прогон (дискриминация): MODULE_UNDER_TEST=live python -m pytest
    tools/test_owns_gate_md.py -q -k discrimination
"""

import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

MODULE_UNDER_TEST = os.environ.get("MODULE_UNDER_TEST", "").strip().lower()


def _resolve_script_path() -> Path:
    # f61-форма (образец test_negative_lint_md.py._resolve_script_path):
    # default -- сиблинг, ЕСЛИ он существует, иначе живой файл.
    if MODULE_UNDER_TEST == "live":
        return TOOLS_DIR / "owns_gate.py"
    sibling = TOOLS_DIR / "owns_gate_md.py"
    return sibling if sibling.exists() else TOOLS_DIR / "owns_gate.py"


SCRIPT = _resolve_script_path()


def _load_module():
    alias = f"owns_gate_target_{'live' if MODULE_UNDER_TEST == 'live' else 'sibling'}"
    spec = importlib.util.spec_from_file_location(alias, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = _load_module()

_REGION_ONLY = pytest.mark.skipif(
    MODULE_UNDER_TEST == "live",
    reason="region API (m.scan/_classify/_extract_owns_full/QUOTED_OWNS_"
    "WARN_MESSAGE/_safe_scan) exists only on the sibling; MODULE_UNDER_"
    "TEST=live targets tools/owns_gate.py verbatim, which has none of it",
)

_NOW = datetime(2026, 8, 19, 12, 0, 0)


def _writing_payload(prompt: str, session_id="s-1", cwd="D:\\repo", description="sonnet: write") -> dict:
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": description},
        "session_id": session_id,
        "cwd": cwd,
    }


def _run_hook(raw_input, cwd=None, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        cwd=str(cwd) if cwd is not None else None,
        **kwargs,
    )


# ---------------------------------------------------------------------
# Регрессия базового поведения (оба таргета -- живой файл не задет).
# ---------------------------------------------------------------------


def test_extract_owns_paths_canonical_single_path_form():
    prompt = "Дано: репо.\nowns (ABSOLUTE write paths): D:/repo/tools/only_one.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/only_one.py"]


def test_extract_owns_paths_ru_form():
    prompt = "owns (АБСОЛЮТНЫЕ пути записи): D:/repo/tools/x.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/x.py"]


def test_extract_owns_paths_no_marker_is_readonly():
    assert m.extract_owns_paths("Прочитай файл и скажи, что там.") == []


def test_f59_backtick_wrapped_path_single_line_recognized():
    # F-59-3 (ключ D4): backtick-обёрнутый путь на прозаической строке
    # маркера -- фильтруется ПОЗИЦИЯ МАРКЕРА, не позиция токена (см.
    # докстринг owns_gate_md.py "АСИММЕТРИЯ ФИЛЬТРА") -- пин ДЕРЖИТСЯ.
    prompt = "owns: `D:/repo/tools/a.py`, `D:/repo/tools/b.py`"
    assert m.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_f59_backtick_wrapped_path_continuation_recognized():
    prompt = "owns:\n- `D:/repo/tools/a.py`\n- `D:/repo/tools/b.py`\n"
    assert m.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_multiline_bullet_block():
    prompt = "Дано: репо целиком.\nowns:\n- D:/repo/tools/a.py\n- D:/repo/tools/b.py\nПравь файлы."
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/a.py", "D:/repo/tools/b.py"]


def test_extract_owns_paths_fallback_substring_marker_when_no_word_boundary_line():
    prompt = "manifest_owns_блок; D:/repo/tools/a.py; D:/repo/tools/b.py\n"
    assert m.OWNS_WORD_RE.search(prompt) is None
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/a.py", "D:/repo/tools/b.py"]


# ---------------------------------------------------------------------
# D5: старый пин "фенс -- явный не-цель" держится ПО ДВУМ причинам.
# ---------------------------------------------------------------------


def test_d5_fenced_non_goal_pin_holds_reason_a_delimiter_not_path_shaped():
    # Причина (а), живая: строка-ограничитель "```" сама не path-подобна --
    # держится ДАЖЕ когда region-фильтр выключен (И-0-подобный сценарий:
    # на сиблинге -- через monkeypatch scan=None; на живой цели -- ВСЕГДА,
    # региона там нет вовсе).
    prompt = "**owns (ABSOLUTE write paths):**\n```\nD:/repo/tools/a.py\n```\n"
    assert m.extract_owns_paths(prompt) == []


@_REGION_ONLY
def test_d5_fenced_non_goal_pin_holds_reason_b_region_excludes_delimiter_line(monkeypatch):
    # Причина (б), НОВАЯ: даже если бы "```" ЧУДОМ был path-подобен,
    # четвёртое стоп-условие (строка продолжения не в прозе) обрывает
    # блок там же -- проверяем ИЗОЛИРОВАННО, подменяя _first_token_path
    # так, чтобы он ВСЕГДА бы принимал строку (нейтрализуем причину (а)),
    # и наблюдаем, что регион ВСЁ РАВНО обрывает блок раньше токенизации.
    monkeypatch.setattr(m, "_first_token_path", lambda line: "D:/would-be-a-path.py")
    prompt = "**owns (ABSOLUTE write paths):**\n```\nD:/repo/tools/a.py\n```\n"
    assert m.extract_owns_paths(prompt) == []


# ---------------------------------------------------------------------
# D1/D2: НЕГАТИВНЫЙ КОНТРОЛЬ ДИСКРИМИНАЦИИ -- маркер+путь ВНУТРИ фенса/
# цитаты не регистрируется на сиблинге, регистрируется (дыра) на живом.
# ---------------------------------------------------------------------


def test_discrimination_d1_marker_and_path_fully_inside_fenced_block_not_declared():
    """С регион-фильтром (дефолт, сиблинг) -- assert ниже ЗЕЛЁН: маркер
    внутри тройного backtick-примера НЕ декларация, extract_owns_paths
    даёт []. Без регион-фильтра (MODULE_UNDER_TEST=live python -m pytest
    tools/test_owns_gate_md.py -q -k test_discrimination_d1) живой
    owns_gate.py находит "owns" внутри примера и РЕГИСТРИРУЕТ путь как
    настоящую декларацию -- тот же assert становится КРАСНЫМ (находка
    t-528, ключ D1)."""
    prompt = (
        "Пример формата манифеста для будущих диспатчей:\n"
        "```\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "```\n"
        "Реальный текст задачи: прочитай и перескажи содержимое файла.\n"
    )
    assert m.extract_owns_paths(prompt) == []


def test_discrimination_d2_marker_and_path_fully_inside_blockquote_not_declared():
    """Тот же класс, цитата `>` вместо фенса (ключ D2). Красный контроль:
    MODULE_UNDER_TEST=live python -m pytest tools/test_owns_gate_md.py
    -q -k test_discrimination_d2"""
    prompt = (
        "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "Реальный текст задачи: прочитай и перескажи содержимое файла.\n"
    )
    assert m.extract_owns_paths(prompt) == []


def test_discrimination_marker_inside_inline_code_not_declared_f5a():
    """Ф5а: маркер внутри одинарных backtick (`` `owns:` ``) -- НЕ
    декларация, даже когда путь ПОСЛЕ backtick-обёртки лежит в прозе
    (позиция МАРКЕРА решает, не позиция пути -- живой алгоритм случайно
    ТОЖЕ разбирает этот путь через итеративную чистку токена, что делает
    эту форму валидным дискриминационным контролем: красный на live)."""
    prompt = "`owns:` D:/repo/tools/real_target.py\n"
    assert m.extract_owns_paths(prompt) == []


def test_discrimination_quoted_decoy_does_not_hijack_real_prose_declaration_below():
    """Перебор всех строк продолжается ПОСЛЕ region-исключённого маркера
    -- настоящая декларация НИЖЕ (в прозе) находится, а не теряется
    (класс "молчаливая частичная сверка опаснее явно помеченной пустой",
    ПЕРЕНЕСЁННЫЙ на region-контекст). На живой цели ПЕРВОЕ (цитируемое)
    совпадение выигрывает -- регистрируется ЛОЖНЫЙ decoy-путь вместо
    настоящего -- assert ниже красный на MODULE_UNDER_TEST=live."""
    prompt = (
        "> owns: D:/repo/tools/example_only.py\n"
        "owns: D:/repo/tools/real_target.py\n"
    )
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


@_REGION_ONLY
def test_word_boundary_seen_stays_orthogonal_to_region_design_choice():
    """Собственное инженерное решение (задокументировано, не угадано
    молча -- см. докстринг owns_gate_md.py "QUOTED_OWNS_WARN" и код
    _extract_owns_full): word_boundary_seen считается по СЫРОМУ \\bowns\\b
    совпадению НЕЗАВИСИМО от региона (толерантность к кривым формам --
    забота ФОЛЛБЕК-прохода -- ортогональна цитированию). Практическое
    следствие: если ЕДИНСТВЕННОЕ word-boundary совпадение -- цитировано,
    фоллбек (подстрочный перебор) НЕ пробуется, даже если он нашёл бы
    что-то в прозе НИЖЕ -- сиблинг-специфичный тест поведения (не
    дискриминация: на живой цели фоллбек тоже не участвует, т.к.
    word-boundary строка сама даёт путь безусловно -- другая причина,
    тот же итоговый список делает эту форму НЕ дискриминационной)."""
    prompt = (
        "> owns: D:/repo/tools/quoted_only.py\n"
        "manifest_owns_блок; D:/repo/tools/fallback_target.py\n"
    )
    assert m.extract_owns_paths(prompt) == []


# ---------------------------------------------------------------------
# D6/D3: decide() -- QUOTED_OWNS_WARN, sidecar НЕ растёт.
# ---------------------------------------------------------------------


def test_decide_quoted_owns_warn_when_all_markers_are_quoted_sidecar_not_grown(tmp_path):
    """Дискриминация на уровне decide(): сиблинг -- QUOTED_OWNS_WARN,
    sidecar не создаётся (D3). На живой цели путь регистрируется молча
    (нет пересечений -> output=None) И sidecar СОЗДАЁТСЯ -- ОБА assert'а
    ниже красные на MODULE_UNDER_TEST=live (ключ D1/D3 сквозным путём)."""
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\nДано: репо целиком.\n"
        "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "Прочитай и перескажи содержимое файла."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    assert not registry.exists()


@_REGION_ONLY
def test_decide_quoted_owns_warn_message_content():
    registry_marker = "цитаты/фенса/инлайн-кода"
    assert registry_marker in m.QUOTED_OWNS_WARN_MESSAGE


def test_decide_blind_owns_warn_still_works_unquoted(tmp_path):
    # Старая B2-диагностика -- байт-в-байт держится, когда маркер в
    # прозе, но путей не дано (не region-related, оба таргета совпадают).
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\nДано: репо целиком.\n"
        "owns: непонятно что тут написано без путей.\nПравь файлы."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is not None
    assert "слепа" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


def test_decide_normal_declaration_registers_and_no_warn(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\nДано: репо целиком.\n"
        "owns: D:/repo/tools/real_target.py\nПравь файлы."
    )
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=_NOW)
    assert exit_code == 0
    assert output is None
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == ["D:/repo/tools/real_target.py"]


# ---------------------------------------------------------------------
# D6: механика реестра (окно 24ч, компакция 500/501) -- НЕ ТРОНУТА,
# спот-проверка (полная эквивалентность -- отдельный equivalence-run).
# ---------------------------------------------------------------------


def test_window_on_boundary_still_live(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = _NOW
    # ровно 24:00:00 в прошлом -- граница ВКЛЮЧИТЕЛЬНА (правило 6а).
    from datetime import timedelta

    old_ts = now - timedelta(seconds=86400)
    with registry.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": old_ts.strftime(m._TS_FORMAT), "session_key": "other", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:/repo/tools/real_target.py"],
        }) + "\n")
    prompt = "owns: D:/repo/tools/real_target.py\n"
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    assert "OWNS OVERLAP" in output["hookSpecificOutput"]["additionalContext"]


def test_window_beyond_boundary_is_stale(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = _NOW
    from datetime import timedelta

    stale_ts = now - timedelta(seconds=86401)
    with registry.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": stale_ts.strftime(m._TS_FORMAT), "session_key": "other", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:/repo/tools/real_target.py"],
        }) + "\n")
    prompt = "owns: D:/repo/tools/real_target.py\n"
    exit_code, output = m.decide(_writing_payload(prompt), registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None


def test_registry_compaction_boundary_500_lines_appends(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = _NOW
    fresh_ts = now.strftime(m._TS_FORMAT)
    with registry.open("a", encoding="utf-8") as f:
        for i in range(500):
            f.write(json.dumps({
                "ts": fresh_ts, "session_key": f"s{i}", "cwd": "D:\\repo",
                "description": "d", "owns": [f"D:/repo/tools/f{i}.py"],
            }) + "\n")
    prompt = "owns: D:/repo/tools/new_one.py\n"
    m.decide(_writing_payload(prompt), registry_path=registry, now=now)
    lines = [ln for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 501  # 500 -> append (500 не строго больше 500)


def test_registry_compaction_boundary_501_lines_compacts(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = _NOW
    fresh_ts = now.strftime(m._TS_FORMAT)
    with registry.open("a", encoding="utf-8") as f:
        for i in range(501):
            f.write(json.dumps({
                "ts": fresh_ts, "session_key": f"s{i}", "cwd": "D:\\repo",
                "description": "d", "owns": [f"D:/repo/tools/f{i}.py"],
            }) + "\n")
    prompt = "owns: D:/repo/tools/new_one.py\n"
    m.decide(_writing_payload(prompt), registry_path=registry, now=now)
    lines = [ln for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # 501 -> компакция (перезапись целиком), но все 501 -- свежие (та же
    # секунда) -> остаются живыми + новая запись = 502.
    assert len(lines) == 502


# ---------------------------------------------------------------------
# D7: И-0 -- отказ md_regions -> сиблинг ведёт себя КАК ЖИВОЙ файл
# БАЙТ-В-БАЙТ, ВКЛЮЧАЯ перехват цитируемой/фенсированной декларации.
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i0_scan_raises_falls_back_to_live_intercept_bug(monkeypatch):
    def _broken_scan(text):
        raise RuntimeError("md_regions exploded")

    monkeypatch.setattr(m, "scan", _broken_scan)
    prompt = (
        "Пример формата манифеста для будущих диспатчей:\n"
        "```\n"
        "owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
        "```\n"
        "Реальный текст задачи: прочитай и перескажи содержимое файла.\n"
    )
    # Перехват ВКЛЮЧЁН (D7) -- И-0 откатывает к БАГУ живого файла, а не
    # к пустому результату: тот же путь, что live даёт БЕЗ подмены.
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


@_REGION_ONLY
def test_i0_scan_degraded_falls_back_to_live_intercept_bug(monkeypatch):
    class _FakeResult:
        degraded = True
        reason = "text_too_large"
        regions = []

    monkeypatch.setattr(m, "scan", lambda text: _FakeResult())
    prompt = "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


@_REGION_ONLY
def test_i0_scan_module_absent_falls_back_to_live_intercept_bug(monkeypatch):
    monkeypatch.setattr(m, "scan", None)
    prompt = "> owns (ABSOLUTE write paths): D:/repo/tools/real_target.py\n"
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]


# ---------------------------------------------------------------------
# D8/И-1: scan() <=1 раз за вызов, только после дешёвого предфильтра.
# ---------------------------------------------------------------------


@_REGION_ONLY
def test_i1_scan_not_called_when_no_owns_marker(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    prompt = "Прочитай файл `README.md` > конца текста и перескажи.\n"
    assert m.extract_owns_paths(prompt) == []
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_not_called_when_marker_present_but_no_region_chars(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    prompt = "owns: D:/repo/tools/real_target.py\n"  # ни `, ни >, ни ~
    assert "`" not in prompt and ">" not in prompt and "~" not in prompt
    assert m.extract_owns_paths(prompt) == ["D:/repo/tools/real_target.py"]
    assert calls["n"] == 0


@_REGION_ONLY
def test_i1_scan_called_exactly_once_when_marker_and_region_chars_present(monkeypatch):
    calls = {"n": 0}
    real_scan = m.scan

    def _counting(text):
        calls["n"] += 1
        return real_scan(text)

    monkeypatch.setattr(m, "scan", _counting)
    prompt = "> owns: D:/repo/tools/real_target.py\nowns: D:/repo/tools/second.py\n"
    m.extract_owns_paths(prompt)
    assert calls["n"] == 1


# ---------------------------------------------------------------------
# Адверсариальная батарея (subprocess, hook-путь) -- fail-open держится.
# ---------------------------------------------------------------------


def test_cli_broken_json_stdin_exit0_silent(tmp_path):
    result = _run_hook(b"{not valid json", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_non_task_tool_silent(tmp_path):
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo owns: D:\\x"}}
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_cli_quoted_declaration_via_hook_exit0(tmp_path):
    prompt = "> owns: D:/repo/tools/real_target.py\nПрочитай.\n"
    payload = _writing_payload(prompt)
    payload["cwd"] = str(tmp_path)
    result = _run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    registry = tmp_path / "logs" / "owns_registry.jsonl"
    assert not registry.exists()


def test_cli_non_utf8_bytes_exit0_no_traceback(tmp_path):
    result = _run_hook(b"\xff\xfe\x00\x01not json either", cwd=tmp_path)
    assert result.returncode == 0
    assert b"Traceback" not in result.stderr
