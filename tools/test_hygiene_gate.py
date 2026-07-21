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


# ---------------------------------------------------------------------
# v2 (t-255) -- git-statement/commit-message ложные срабатывания класса (г)
# ---------------------------------------------------------------------


def test_v2_regress_fp_evidence_literal_add_commit_heredoc_push_no_warn():
    # (а) регресс -- сегодняшняя FP-форма ДОСЛОВНО (evidence задачи
    # t-255): git add путём журнала && git commit -m с bash-герокой,
    # содержащей путь журнала внутри текста, && git push -- git ничего
    # не пишет в журнал, WARN не должен сработать.
    command = (
        "git add logs/routing-log.jsonl && git commit -m \"$(cat <<'EOF'\n"
        "текст с путём logs/routing-log.jsonl внутри\n"
        "EOF\n"
        ')" && git push'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_git_add_path_alone_no_warn():
    # (б) git add путём журнала, без commit/push -- не про запись.
    exit_code, output = hygiene_gate.decide(_bash_payload("git add logs/routing-log.jsonl"))
    assert exit_code == 0
    assert output is None


def test_v2_git_commit_message_mentions_routing_log_and_arrow_no_warn():
    command = (
        'git commit -m "Update routing-log format: '
        'old-field -> new-field mapping documented"'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_git_diff_journal_path_with_unrelated_redirect_no_warn():
    # Мотивирующий случай порта (2), НЕ покрываемый вырезанием
    # сообщения (нет -m вовсе): git diff путём журнала как аргументом
    # + редирект СОБСТВЕННОГО вывода git в другой файл -- не про
    # запись в журнал.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git diff logs/routing-log.jsonl > /tmp/out.txt")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_log_journal_path_piped_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git log -- logs/routing-log.jsonl | head")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_show_journal_path_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git show HEAD:logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v2_git_status_journal_path_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git status logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_v2_unclosed_quote_in_message_not_stripped_but_git_statement_still_masked():
    # РАСХОЖДЕНИЕ с прямым портом AO3-теста, задокументировано честно:
    # у АО3 незакрытая кавычка в -m не матчится _strip_commit_messages
    # и остаётся как есть -- их детект триггерится, т.к. у АО3 НЕТ
    # второго слоя (git-statement масок). У НАС есть порт (2):
    # statement "git commit ..." (валидный ИЛИ с незакрытой кавычкой
    # -- маскирование не различает) целиком попадает под
    # GIT_STATEMENT_RE независимо от вложенной кавычки, поэтому
    # substring/индикатор ВНУТРИ него гасятся ВТОРЫМ слоем -- WARN не
    # срабатывает. Это РАСШИРЕНИЕ уже задокументированной остаточной
    # дыры класса (г) (см. докстринг модуля): git commit, даже
    # синтаксически кривой, не считается писателем журнала -- принято
    # тем же принципом "warn -- не граница безопасности", НЕ регресс
    # реальной защиты (echo/printf с незакрытой кавычкой по-прежнему
    # детектятся -- см. следующий тест).
    command = 'git commit -m "unterminated message mentions routing-log > oops'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_unclosed_quote_in_non_git_write_command_still_triggers():
    # Тот же класс "незакрытая кавычка не должна тихо гасить детект",
    # но на РЕАЛЬНОМ писателе (echo, не git) -- здесь ни
    # _strip_commit_messages (нет "git commit"), ни _mask_git_statements
    # (нет "git") не участвуют вовсе -- substring/индикатор остаются
    # видны детектору как раньше, WARN срабатывает. Это и есть
    # сохранённая, реально значимая часть fail-safe гарантии.
    command = 'echo "unterminated message mentions routing-log > oops'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None


def test_v2_powershell_herestring_message_fully_stripped_no_warn():
    command = (
        "git commit -m @'\n"
        "Update routing-log.jsonl format: old -> new mapping\n"
        "'@"
    )
    exit_code, output = hygiene_gate.decide(
        {"tool_name": "PowerShell", "tool_input": {"command": command}}
    )
    assert exit_code == 0
    assert output is None


def test_v2_two_message_arguments_both_stripped_no_warn():
    command = (
        'git commit -m "first paragraph, clean" '
        '-m "second paragraph mentions routing-log and > arrow"'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_all_crapola_inside_message_no_warn():
    command = 'git commit -m "echo > logs/routing-log.jsonl"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_single_quoted_message_stripped_no_warn():
    command = "git commit -m 'notes about routing-log.jsonl -> archived'"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_message_flag_long_form_equals_form_stripped_no_warn():
    command = '''git commit --message="routing-log rewritten, old -> new"'''
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v2_non_commit_git_command_not_scrubbed_by_message_stripper():
    # Вырезание сообщения применяется ТОЛЬКО к git commit.
    command = "echo x > logs/routing-log.jsonl"
    assert not hygiene_gate.GIT_COMMIT_RE.search(command)


# --- (в) истинные позитивы живы после портов (не ослаблены) ---


def test_v2_true_positive_echo_after_git_commit_chain_still_triggers():
    command = 'git commit -m "x" && echo evil >> logs/routing-log.jsonl'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert hygiene_gate.MSG_JOURNAL_BYPASS in output["hookSpecificOutput"]["additionalContext"]


def test_v2_true_positive_sed_inside_command_substitution_outside_message_still_triggers():
    command = "$(sed -n '1p' logs/routing-log.jsonl > logs/routing-log.jsonl.bak)"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None


def test_v2_true_positive_printf_still_triggers_regress():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('printf \'{"event":"x"}\' >> logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is not None


# --- граница whitelist'а: неперечисленная git-подкоманда НЕ гасится ---


def test_v2_git_rm_not_in_whitelist_still_triggers_if_it_would_otherwise():
    # "git rm" не входит в перечень (add/commit/push/diff/log/show/
    # status) -- искусственный, но прямой тест границы whitelist'а
    # (правило 6а кита): статья-конструкция всё равно детектится как
    # обычный "текст команды с путём и `>`", т.к. маскирование не
    # применяется к неперечисленным подкомандам.
    command = "git rm logs/routing-log.jsonl > /tmp/log.txt"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None


def test_v2_git_reset_not_in_whitelist_still_triggers():
    command = "git reset -- logs/routing-log.jsonl > /tmp/x.txt"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None


# --- subprocess-уровень smoke для evidence-формы (DoD) ---


def test_echo_json_v2_regress_evidence_exit0_no_stdout():
    command = (
        "git add logs/routing-log.jsonl && git commit -m \"$(cat <<'EOF'\n"
        "текст с путём logs/routing-log.jsonl внутри\n"
        "EOF\n"
        ')" && git push'
    )
    payload = _bash_payload(command)
    result = _run_hook(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    assert result.returncode == 0
    assert result.stdout.strip() == b""
    assert result.stderr == b""


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
