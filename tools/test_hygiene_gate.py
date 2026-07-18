"""Юнит-смоки tools/hygiene_gate.py. Покрывает DoD спеки задачи:
(1) узкий прогон зелёный (сам этот файл), (2) 4 детект-класса
позитивно, чистая команда негативно, не-Bash тул, (3) адверсариальная
батарея интерактивной поверхности (правило 11 CLAUDE.md кита): пустой
stdin, битый JSON, кириллическая команда, очень длинная команда
(>100КБ), вложенные кавычки -- везде exit 0 без трейсбека."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hygiene_gate  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "hygiene_gate.py"


def _run_hook(raw_input, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        **kwargs,
    )


def _bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


# ---------------------------------------------------------------------
# decide() -- pure logic
# ---------------------------------------------------------------------


def test_decide_non_bash_tool_is_silent_pass():
    exit_code, output = hygiene_gate.decide({"tool_name": "Edit", "tool_input": {}})
    assert exit_code == 0
    assert output is None


def test_decide_powershell_tool_checked_too():
    payload = {"tool_name": "PowerShell", "tool_input": {"command": "cd foo && ls"}}
    exit_code, output = hygiene_gate.decide(payload)
    assert exit_code == 0
    assert output is not None
    assert hygiene_gate.MSG_CD_PREFIX in output["hookSpecificOutput"]["additionalContext"]


def test_decide_clean_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide(_bash_payload("python -m pytest tools/ -q"))
    assert exit_code == 0
    assert output is None


def test_decide_cd_prefix_and_amp_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py"))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_CD_PREFIX in ctx


def test_decide_cd_prefix_with_semicolon_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway; python x.py"))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_CD_PREFIX in ctx


def test_decide_bare_cd_without_continuation_does_not_trigger():
    # "cd gateway" в одиночку -- легальная форма (permission-запрос
    # оператору только за "своя форма" ПОСЛЕДОВАТЕЛЬНОСТИ cd&&/cd;).
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway"))
    assert exit_code == 0
    assert output is None


def test_decide_cd_in_middle_of_command_does_not_trigger():
    # cd не в начале команды -- не префикс.
    exit_code, output = hygiene_gate.decide(_bash_payload("echo hi && cd gateway"))
    assert exit_code == 0
    assert output is None


def test_decide_redirect_stderr_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("python x.py 2>&1"))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


def test_decide_python_dash_c_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1)"'))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_decide_python_heredoc_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("python - <<EOF\nprint(1)\nEOF"))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_decide_python3_dash_c_does_not_trigger():
    # Спека называет буквально "python -c" -- "python3 -c" не тот же
    # токен, самостоятельно расширять не стал (см. докстринг модуля).
    exit_code, output = hygiene_gate.decide(_bash_payload('python3 -c "print(1)"'))
    assert exit_code == 0
    assert output is None


def test_decide_python_dash_m_pytest_does_not_trigger_dash_c():
    exit_code, output = hygiene_gate.decide(_bash_payload("python -m pytest tools/ -q"))
    assert exit_code == 0
    assert output is None


def test_decide_word_boundary_mypython_does_not_trigger():
    exit_code, output = hygiene_gate.decide(_bash_payload("mypython -c foo"))
    assert exit_code == 0
    assert output is None


def test_decide_journal_bypass_redirect_triggers():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BYPASS in ctx


def test_decide_journal_bypass_printf_triggers():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('printf \'{"event":"x"}\' logs/routing-log.jsonl')
    )
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BYPASS in ctx


def test_decide_journal_bypass_requires_routing_log_substring():
    # Редирект в произвольный файл БЕЗ "routing-log" -- не про журнал,
    # класс (г) не триггерится (самостоятельное решение, см. докстринг
    # модуля -- заголовок класса "запись в журнал", не "любой редирект").
    exit_code, output = hygiene_gate.decide(_bash_payload("ls > out.txt"))
    assert exit_code == 0
    assert output is None


def test_decide_journal_bypass_case_insensitive():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> LOGS/ROUTING-LOG.JSONL")
    )
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BYPASS in ctx


def test_decide_multiple_classes_all_listed():
    command = 'cd gateway && python -c "print(1)" 2>&1'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_CD_PREFIX in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_decide_hook_specific_output_shape():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd x && y"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    # B1: permissionDecision отсутствует -- warn не трогает permission-путь.
    assert "permissionDecision" not in hso
    assert isinstance(hso["additionalContext"], str) and hso["additionalContext"]


def test_decide_missing_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide({"tool_name": "Bash", "tool_input": {}})
    assert exit_code == 0
    assert output is None


def test_decide_non_string_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide(
        {"tool_name": "Bash", "tool_input": {"command": 123}}
    )
    assert exit_code == 0
    assert output is None


def test_decide_non_dict_payload_is_silent_pass():
    exit_code, output = hygiene_gate.decide(["not", "a", "dict"])
    assert exit_code == 0
    assert output is None


def test_decide_non_dict_tool_input_is_silent_pass():
    exit_code, output = hygiene_gate.decide({"tool_name": "Bash", "tool_input": "oops"})
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# subprocess-уровень: exit code, stdout JSON, fail-open
# ---------------------------------------------------------------------


def test_echo_json_clean_command_exit0_no_stdout():
    payload = _bash_payload("python -m pytest tools/ -q")
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr == ""


def test_echo_json_dirty_command_exit0_with_stdout_json():
    payload = _bash_payload("cd gateway && python x.py 2>&1")
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_PREFIX in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_echo_json_non_bash_tool_exit0_no_stdout():
    payload = {"tool_name": "Task", "tool_input": {"subagent_type": "builder"}}
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# --- адверсариальная батарея (DoD п.3) ---


def test_adversarial_empty_stdin():
    result = _run_hook("", text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr == ""


def test_adversarial_malformed_json():
    result = _run_hook("{not valid json", text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stdout.strip() == ""
    assert result.stderr == ""


def test_adversarial_cyrillic_command_raw_utf8_bytes():
    # Сырые UTF-8-байты на stdin, БЕЗ text=True -- ровно та форма,
    # которой харнесс реально кормит дочерний процесс (см. докстринг
    # tools/dispatch_gate.py, t-159 stdin-фикс).
    payload = _bash_payload("cd репо && проверь 2>&1")
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = _run_hook(raw)
    assert result.returncode == 0
    stdout_text = result.stdout.decode("utf-8")
    data = json.loads(stdout_text)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_CD_PREFIX in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


def test_adversarial_very_long_command_no_crash():
    long_command = "python -m pytest " + ("a" * 100_000) + " -q"
    payload = _bash_payload(long_command)
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""


def test_adversarial_nested_quotes_no_crash():
    command = """python -c "print('he said \\"hi\\" 2>&1')" """
    payload = _bash_payload(command)
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""
    data = json.loads(result.stdout)
    assert hygiene_gate.MSG_PYTHON_DASH_C in data["hookSpecificOutput"]["additionalContext"]


def test_adversarial_null_bytes_in_json_string_no_crash():
    payload = {"tool_name": "Bash", "tool_input": {"command": "cd x && \x00 2>&1"}}
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""
