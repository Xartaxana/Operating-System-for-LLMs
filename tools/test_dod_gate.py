"""Юнит-смоки tools/dod_gate.py (штабной вариант, t-159 п.7 порт) --
покрывает все ветки, перечисленные DoD спеки t-150 (правка логируется
косвенно через dod_track, уже покрыт отдельным файлом; зелёный/красный
прогон различаются; stop-блок при правке-без-прогона; stop-пропуск при
прогоне-после-правки; пропуск без правок; предохранитель 2 блоков) --
kit-кейсы перенесены как есть (логика evaluate()/decide() базового
инварианта не менялась), ПЛЮС штабные doc-only кейсы (см. ниже).

ШТАБНОЕ ОТЛИЧИЕ ОТ КИТА: НОВОЕ правило -- правки ТОЛЬКО файлов с
расширениями .md/.json/.jsonl освобождают от инварианта целиком
(reason "doc-only-edits-exempt"); file_path=None -- fail-closed (НЕ
doc-only, инвариант в силе); смешанная правка (.md + .py) -- инвариант
в силе. .jsonl добавлен Lead'ом при приёмке порта (правка
logs/routing-log.jsonl -- штатная операция сессии, не должна ложно
блокировать сдачу) -- см. docstring tools/dod_gate.py."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dod_gate  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "dod_gate.py"


def _run_hook(payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _stop_payload(cwd: str, session_id: str = "sess-x") -> dict:
    return {
        "session_id": session_id,
        "cwd": cwd,
        "hook_event_name": "SubagentStop",
        "agent_type": "builder",
        "agent_id": "agent-1",
        "stop_hook_active": False,
    }


# ---------------------------------------------------------------------
# evaluate() -- pure logic (перенесено из кита, логика не менялась).
# ---------------------------------------------------------------------


def test_evaluate_no_edits_no_violation():
    violation, reason = dod_gate.evaluate({"edits": [], "runs": []})
    assert violation is False
    assert reason == "no-edits"


def test_evaluate_edit_without_any_run_is_violation():
    track = {"edits": [{"ts": "2026-07-16T10:00:00.000000"}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is True
    assert reason == "no-green-run"


def test_evaluate_edit_with_only_red_run_is_violation():
    track = {
        "edits": [{"ts": "2026-07-16T10:00:00.000000"}],
        "runs": [{"ts": "2026-07-16T10:00:01.000000", "outcome": "red"}],
    }
    violation, reason = dod_gate.evaluate(track)
    assert violation is True
    assert reason == "no-green-run"


def test_evaluate_green_run_before_edit_is_violation():
    track = {
        "edits": [{"ts": "2026-07-16T10:00:05.000000"}],
        "runs": [{"ts": "2026-07-16T10:00:00.000000", "outcome": "green"}],
    }
    violation, reason = dod_gate.evaluate(track)
    assert violation is True
    assert reason == "green-before-last-edit"


def test_evaluate_green_run_after_edit_is_not_violation():
    track = {
        "edits": [{"ts": "2026-07-16T10:00:00.000000"}],
        "runs": [{"ts": "2026-07-16T10:00:05.000000", "outcome": "green"}],
    }
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "green-after-last-edit"


# ---------------------------------------------------------------------
# STAGING_HQ: правило doc-only (.md/.json/.jsonl).
# ---------------------------------------------------------------------


def test_evaluate_doc_only_md_edits_no_violation():
    track = {"edits": [{"ts": "t1", "file_path": "docs/NOTES.md"}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "doc-only-edits-exempt"


def test_evaluate_doc_only_json_edits_no_violation():
    track = {"edits": [{"ts": "t1", "file_path": ".claude/settings.json"}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "doc-only-edits-exempt"


def test_evaluate_doc_only_jsonl_routing_log_edit_no_violation():
    # Обязательный кейс спеки: правка ТОЛЬКО logs/routing-log.jsonl --
    # штатная операция Lead'а при приёмке -- НЕ должна блокировать.
    track = {"edits": [{"ts": "t1", "file_path": "logs/routing-log.jsonl"}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "doc-only-edits-exempt"


def test_evaluate_doc_only_extension_case_insensitive():
    track = {"edits": [{"ts": "t1", "file_path": "docs/NOTES.MD"}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "doc-only-edits-exempt"


def test_evaluate_doc_only_multiple_edits_all_qualifying():
    track = {
        "edits": [
            {"ts": "t1", "file_path": "docs/NOTES.md"},
            {"ts": "t2", "file_path": "logs/routing-log.jsonl"},
            {"ts": "t3", "file_path": ".claude/settings.json"},
        ],
        "runs": [],
    }
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "doc-only-edits-exempt"


def test_evaluate_unknown_file_path_none_is_fail_closed():
    # file_path=None (искажённый payload либо старый трек до этой
    # правки) -- КОНСЕРВАТИВНО НЕ doc-only, инвариант в силе.
    track = {"edits": [{"ts": "t1", "file_path": None}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is True
    assert reason == "no-green-run"


def test_evaluate_missing_file_path_key_is_fail_closed():
    # Ключа file_path нет вовсе (старый трек, записанный до штабной
    # правки dod_track.py) -- .get() вернёт None -- тот же fail-closed.
    track = {"edits": [{"ts": "t1"}], "runs": []}
    violation, reason = dod_gate.evaluate(track)
    assert violation is True
    assert reason == "no-green-run"


def test_evaluate_mixed_md_and_py_edits_invariant_applies():
    # Смешанная правка (.md + .py) -- исключение НЕ применяется.
    track = {
        "edits": [
            {"ts": "t1", "file_path": "README.md"},
            {"ts": "t2", "file_path": "tools/x.py"},
        ],
        "runs": [],
    }
    violation, reason = dod_gate.evaluate(track)
    assert violation is True
    assert reason == "no-green-run"


def test_evaluate_mixed_extensions_with_green_run_after_last_edit_not_violation():
    # Смешанная правка НЕ освобождена от инварианта, но обычный путь
    # (зелёный прогон после последней правки) по-прежнему работает.
    track = {
        "edits": [
            {"ts": "2026-07-16T10:00:00.000000", "file_path": "README.md"},
            {"ts": "2026-07-16T10:00:01.000000", "file_path": "tools/x.py"},
        ],
        "runs": [{"ts": "2026-07-16T10:00:05.000000", "outcome": "green"}],
    }
    violation, reason = dod_gate.evaluate(track)
    assert violation is False
    assert reason == "green-after-last-edit"


# ---------------------------------------------------------------------
# decide() -- gate_state / предохранитель 2 блоков (перенесено из кита).
# ---------------------------------------------------------------------


def test_decide_blocks_on_first_violation():
    track = {"edits": [{"ts": "t1"}], "runs": []}
    exit_code, message, updated = dod_gate.decide(track)
    assert exit_code == 2
    assert "заблокирована" in message
    assert updated["gate_state"]["consecutive_blocks"] == 1
    assert updated["gate_log"][-1]["action"] == "blocked"


def test_decide_blocks_again_on_second_consecutive_violation():
    track = {"edits": [{"ts": "t1"}], "runs": [], "gate_state": {"consecutive_blocks": 1}}
    exit_code, message, updated = dod_gate.decide(track)
    assert exit_code == 2
    assert updated["gate_state"]["consecutive_blocks"] == 2


def test_decide_skips_on_third_consecutive_violation_safety_valve():
    track = {"edits": [{"ts": "t1"}], "runs": [], "gate_state": {"consecutive_blocks": 2}}
    exit_code, message, updated = dod_gate.decide(track)
    assert exit_code == 0
    assert "предохранитель" in message
    assert updated["gate_state"]["consecutive_blocks"] == 0
    assert updated["gate_log"][-1]["action"] == "skipped_after_2_blocks"


def test_decide_resets_counter_on_success():
    track = {
        "edits": [{"ts": "t1"}],
        "runs": [{"ts": "t2", "outcome": "green"}],
        "gate_state": {"consecutive_blocks": 1},
    }
    exit_code, message, updated = dod_gate.decide(track)
    assert exit_code == 0
    assert message == ""
    assert updated["gate_state"]["consecutive_blocks"] == 0


def test_decide_no_edits_passes_without_touching_counter():
    track = {"edits": [], "runs": [], "gate_state": {"consecutive_blocks": 0}}
    exit_code, message, updated = dod_gate.decide(track)
    assert exit_code == 0
    assert message == ""
    assert updated["gate_state"]["consecutive_blocks"] == 0
    assert "gate_log" not in updated


def test_decide_doc_only_edits_pass_without_touching_counter():
    track = {
        "edits": [{"ts": "t1", "file_path": "logs/routing-log.jsonl"}],
        "runs": [],
        "gate_state": {"consecutive_blocks": 1},
    }
    exit_code, message, updated = dod_gate.decide(track)
    assert exit_code == 0
    assert message == ""
    assert updated["gate_state"]["consecutive_blocks"] == 0


# ---------------------------------------------------------------------
# echo-JSON смок подпроцессом -- полный сценарий блок -> прогон -> пропуск
# (перенесено из кита) + штабные doc-only сценарии.
# ---------------------------------------------------------------------


def _write_track(tmp_path: Path, session_id: str, data: dict) -> Path:
    path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_echo_json_no_track_file_passes(tmp_path):
    # Сценарий scout/critic-класса: subagent вообще не правил файлы,
    # трек-файл никогда не создавался dod_track.py.
    result = _run_hook(_stop_payload(str(tmp_path), "sess-none"), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    # Настоящий пропуск -- хук не должен обрастить .claude/dod_track/
    # пустым файлом на ровном месте для субагента без единой правки.
    assert not (tmp_path / ".claude" / "dod_track" / "sess-none.json").exists()


def test_echo_json_blocks_when_edit_without_run(tmp_path):
    session_id = "sess-block"
    _write_track(tmp_path, session_id, {"edits": [{"ts": "t1", "tool_name": "Edit"}], "runs": []})

    result = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert result.returncode == 2
    assert "заблокирована" in result.stderr

    track = json.loads((tmp_path / ".claude" / "dod_track" / f"{session_id}.json").read_text())
    assert track["gate_state"]["consecutive_blocks"] == 1


def test_echo_json_passes_when_green_run_after_edit(tmp_path):
    session_id = "sess-green"
    _write_track(
        tmp_path,
        session_id,
        {
            "edits": [{"ts": "2026-07-16T10:00:00.000000", "tool_name": "Edit"}],
            "runs": [
                {
                    "ts": "2026-07-16T10:00:05.000000",
                    "tool_name": "Bash",
                    "command": "python -m pytest tools/ -q",
                    "outcome": "green",
                }
            ],
        },
    )

    result = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_echo_json_safety_valve_after_two_consecutive_blocks(tmp_path):
    session_id = "sess-valve"
    _write_track(tmp_path, session_id, {"edits": [{"ts": "t1"}], "runs": []})

    r1 = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert r1.returncode == 2

    r2 = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert r2.returncode == 2

    r3 = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert r3.returncode == 0
    assert "предохранитель" in r3.stderr

    track = json.loads((tmp_path / ".claude" / "dod_track" / f"{session_id}.json").read_text())
    assert track["gate_state"]["consecutive_blocks"] == 0
    actions = [g["action"] for g in track["gate_log"]]
    assert actions == ["blocked", "blocked", "skipped_after_2_blocks"]

    # Ещё одна попытка без прогона -- цикл предохранителя начинается
    # заново (блок #1 нового цикла), а не продолжает пропускать.
    r4 = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert r4.returncode == 2


def test_echo_json_doc_only_md_edit_passes_without_run(tmp_path):
    session_id = "sess-doc-only-md"
    _write_track(
        tmp_path,
        session_id,
        {"edits": [{"ts": "t1", "tool_name": "Edit", "file_path": "docs/NOTES.md"}], "runs": []},
    )

    result = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_echo_json_doc_only_jsonl_routing_log_edit_passes_without_run(tmp_path):
    session_id = "sess-doc-only-jsonl"
    _write_track(
        tmp_path,
        session_id,
        {
            "edits": [
                {"ts": "t1", "tool_name": "Edit", "file_path": "logs/routing-log.jsonl"}
            ],
            "runs": [],
        },
    )

    result = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_echo_json_unknown_file_path_still_blocks(tmp_path):
    session_id = "sess-unknown-path"
    _write_track(
        tmp_path,
        session_id,
        {"edits": [{"ts": "t1", "tool_name": "Edit", "file_path": None}], "runs": []},
    )

    result = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert result.returncode == 2
    assert "заблокирована" in result.stderr


def test_echo_json_mixed_extensions_still_blocks(tmp_path):
    session_id = "sess-mixed"
    _write_track(
        tmp_path,
        session_id,
        {
            "edits": [
                {"ts": "t1", "tool_name": "Edit", "file_path": "README.md"},
                {"ts": "t2", "tool_name": "Edit", "file_path": "tools/x.py"},
            ],
            "runs": [],
        },
    )

    result = _run_hook(_stop_payload(str(tmp_path), session_id), cwd=tmp_path)
    assert result.returncode == 2
    assert "заблокирована" in result.stderr


# ---------------------------------------------------------------------
# Byte-safe stdin: субпроцесс-смок сырыми UTF-8 байтами, БЕЗ
# text=True/encoding на subprocess -- по образцу kit test_dispatch_gate.
# ---------------------------------------------------------------------


def test_echo_json_raw_utf8_bytes_stdin_no_crash(tmp_path):
    payload = _stop_payload(str(tmp_path), "sess-utf8")
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw,
        cwd=str(tmp_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0


def test_echo_json_malformed_json_fails_open():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{not valid json",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stderr == ""
