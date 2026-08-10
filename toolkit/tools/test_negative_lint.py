"""Unit smokes for tools/negative_lint.py. Covers the task's DoD:
(1) positive cases -- a negative with no control warns, a negative with
a control in the window is silent, text with no negatives is silent, a
non-Agent/Task tool is silent; (2) boundaries -- a control exactly 3
lines away (window fires) and 4 lines away (does not fire), case/
mid-word matching; (3) adversarial battery -- broken JSON, empty
stdin, a payload with no tool_response, a result object with nested
content, 1 MB of text (<2s), non-UTF8 bytes, emoji/unicode -- all
fail-open; (4) a control-marker false positive -- the "ЗАКРЫТО: ..."
form must not produce a WARN.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import negative_lint  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "negative_lint.py"


def _run_hook(raw_input, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        **kwargs,
    )


def _agent_payload(text) -> dict:
    return {"tool_name": "Task", "tool_input": {}, "tool_response": text}


# ---------------------------------------------------------------------
# decide() -- pure logic, positive cases (DoD point 1)
# ---------------------------------------------------------------------


def test_decide_negative_without_control_warns():
    text = "Проверил каталог docs/book -- не существует такого пути."
    exit_code, output = negative_lint.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "NEGATIVE LINT" in ctx
    assert "1 negative statement" in ctx


def test_decide_negative_with_control_in_window_is_silent():
    text = (
        "Позитивный контроль тем же способом на известно-существующем файле дал совпадение.\n"
        "Проверил каталог docs/book -- не существует такого пути.\n"
    )
    exit_code, output = negative_lint.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_decide_text_without_negatives_is_silent():
    text = "Всё найдено, файл существует, задача выполнена штатно."
    exit_code, output = negative_lint.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_decide_non_agent_tool_is_silent():
    payload = {"tool_name": "Bash", "tool_response": "файл не найден"}
    exit_code, output = negative_lint.decide(payload)
    assert exit_code == 0
    assert output is None


def test_decide_non_dict_payload_silent_pass():
    assert negative_lint.decide([1, 2, 3]) == (0, None)
    assert negative_lint.decide("not a dict either") == (0, None)
    assert negative_lint.decide(None) == (0, None)


def test_cli_non_dict_payload_list_exit0_silent():
    result = _run_hook(b"[1, 2, 3]")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


def test_decide_agent_tool_name_also_triggers():
    # tools/dispatch_gate.py's own tool_name filter: tool_name in
    # ("Task", "Agent") -- both literal values are recognized.
    payload = {"tool_name": "Agent", "tool_response": "не найдено ни одного файла"}
    exit_code, output = negative_lint.decide(payload)
    assert exit_code == 0
    assert output is not None


# ---------------------------------------------------------------------
# boundaries (DoD point 2, rule 6a of the builder role)
# ---------------------------------------------------------------------


def test_control_exactly_3_lines_away_triggers_window_suppresses_warn():
    lines = [
        "filler line 1",
        "filler line 2",
        "filler line 3",
        "0 matches found in the search.",  # negative, index i (0-based) = 3
        "filler line A",
        "filler line B",
        "control: known-present sample checked same form.",  # i+3 = 6
    ]
    text = "\n".join(lines)
    violations = negative_lint.find_violations(text)
    assert violations == []


def test_control_4_lines_away_does_not_trigger_window_warn_remains():
    lines = [
        "filler line 1",
        "filler line 2",
        "filler line 3",
        "0 matches found in the search.",  # negative, index i (0-based) = 3
        "filler line A",
        "filler line B",
        "filler line C",
        "control: known-present sample checked same form.",  # i+4 = 7
    ]
    text = "\n".join(lines)
    violations = negative_lint.find_violations(text)
    assert len(violations) == 1
    assert violations[0][0] == 4  # line_no, 1-indexed


def test_marker_case_insensitive_and_mid_word_otsutstvuet():
    text = "Файл ОТСУТСТВУЕТ в каталоге проекта."
    violations = negative_lint.find_violations(text)
    assert len(violations) == 1


def test_marker_ne_naideno_ni_mid_phrase():
    text = "не найдено ни одного совпадения по запросу."
    violations = negative_lint.find_violations(text)
    assert len(violations) == 1


# ---------------------------------------------------------------------
# Async launch of Task/Agent -- launch metadata, not a worker report.
# ---------------------------------------------------------------------


def test_decide_async_launched_payload_is_silent():
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "isAsync": True,
            "status": "async_launched",
            "agentId": "abc123",
            "description": "sonnet: do the thing",
            "resolvedModel": "sonnet",
            "prompt": "Проверь: файл не найден нигде не встречается без контроля.",
        },
    }
    exit_code, output = negative_lint.decide(payload)
    assert exit_code == 0
    assert output is None


def test_decide_status_async_launched_alone_is_silent():
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "status": "async_launched",
            "prompt": "Такого файла не существует, негатив без контроля.",
        },
    }
    exit_code, output = negative_lint.decide(payload)
    assert exit_code == 0
    assert output is None


def test_decide_is_async_true_alone_is_silent():
    payload = {
        "tool_name": "Agent",
        "tool_response": {
            "isAsync": True,
            "prompt": "Отсутствует нужный файл, негатив без контроля.",
        },
    }
    exit_code, output = negative_lint.decide(payload)
    assert exit_code == 0
    assert output is None


def test_decide_beyond_skip_condition_completed_status_still_warns():
    # BEYOND the skip condition's boundary: isAsync=False and
    # status="completed" -- the json.dumps fallback stays live, the
    # WARN is not suppressed.
    payload = {
        "tool_name": "Task",
        "tool_response": {
            "isAsync": False,
            "status": "completed",
            "prompt": "Такого файла не существует в репозитории.",
        },
    }
    exit_code, output = negative_lint.decide(payload)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "NEGATIVE LINT" in ctx


def test_decide_plain_string_response_negative_still_warns_regression():
    # Regression of the main path: an ordinary string tool_response
    # with a negative and no control still warns (the async skip did
    # not affect the string form).
    text = "Проверил -- такого пути не существует в репозитории."
    exit_code, output = negative_lint.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is not None
    assert "NEGATIVE LINT" in output["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------
# control false positive -- the CLOSED-marker form (DoD point 4)
# ---------------------------------------------------------------------


def test_zakryto_form_suppresses_warn():
    text = (
        "Файл не найден по указанному пути.\n"
        "ЗАКРЫТО: проверено позитивным прогоном на заведомо существующем файле той же формы.\n"
    )
    exit_code, output = negative_lint.decide(_agent_payload(text))
    assert exit_code == 0
    assert output is None


def test_zakryto_lowercase_also_suppresses_case_insensitive():
    text = (
        "Такого файла не существует.\n"
        "закрыто: см. контрольный прогон выше.\n"
    )
    violations = negative_lint.find_violations(text)
    assert violations == []


# ---------------------------------------------------------------------
# adversarial battery (DoD point 3) -- through a real subprocess, hook path
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


def test_cli_1mb_text_under_2_seconds():
    line = "просто обычная строка отчёта без маркеров нужной длины для объёма. " * 3
    big_text = (line + "\n") * 15000  # significantly over 1 MB
    assert len(big_text.encode("utf-8")) > 1_000_000
    payload = {"tool_name": "Task", "tool_response": big_text}
    started = time.perf_counter()
    result = _run_hook(json.dumps(payload).encode("utf-8"))
    elapsed = time.perf_counter() - started
    assert result.returncode == 0
    assert elapsed < 2.0


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


# ---------------------------------------------------------------------
# CLI mode --text <file>
# ---------------------------------------------------------------------


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
