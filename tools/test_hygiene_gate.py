"""Юнит-смоки tools/hygiene_gate.py. Покрывает DoD спеки задачи:
(1) узкий прогон зелёный (сам этот файл), (2) 4 детект-класса
позитивно, чистая команда негативно, не-Bash тул, (3) адверсариальная
батарея интерактивной поверхности (правило 11 CLAUDE.md кита): пустой
stdin, битый JSON, кириллическая команда, очень длинная команда
(>100КБ), вложенные кавычки -- везде exit 0 без трейсбека.

VG-5 (2026-07-23) -- класс (г) (шелл-запись в журнал) промотирован
WARN -> БЛОК (permissionDecision="deny" + permissionDecisionReason,
БЕЗ смены exit-кода -- см. докстринг раздела v3 tools/hygiene_gate.py).
Тесты "..._journal_bypass_..."/"..._true_positive_..." для класса (г)
ОБНОВЛЕНЫ на проверку permissionDecision/permissionDecisionReason
вместо additionalContext (MSG_JOURNAL_BYPASS переименован в
MSG_JOURNAL_BLOCK). Добавлены (см. соответствующие секции ниже):
sed -i/tee/python-open-write-mode/heredoc-редирект как формы БЛОКА
(DoD п.1); tail/cat/wc read-only и echo-в-не-журнальный-файл как
НЕ-блок (DoD п.2); ./-путь, абсолютный путь, кавычки вокруг пути,
$-переменная (документированное честное ограничение), компаунд
"безобидная && пишущая" (DoD п.3); *.jsonl-под-logs/ (расширенная
цель, design-текст спеки); стейтмент-скоупинг (собственная живая
находка builder'а -- read+unrelated-write в разных statement'ах
БОЛЬШЕ НЕ триггерит); живой git -C FP координатора (регресс-тест
компаунда из трёх git -C команд).

F-53 (критик, доп. к VG-5, 2026-07-23) -- belt-and-suspenders:
additionalContext ВСЕГДА дублирует причину блока класса (г) (та же
строка, что permissionDecisionReason), не только когда одновременно
сработал прочий WARN-класс -- страховка на случай мёртвого
deny-канала на реальном харнессе (см. секцию "test_f53_*" ниже и
докстринг раздела v3 tools/hygiene_gate.py).

F-53-2 (Lead, liveness-проба D-0093, 2026-07-23, formal reject t-302
attempt 1) -- квотирование-осознанный редирект: `>` внутри одинарных/
двойных кавычек -- аргумент-строка (напр. grep'а), не shell-редирект
-- больше НЕ считается формой записи (см. секцию "test_f53_2_*" ниже
и _mask_quoted_segments в tools/hygiene_gate.py)."""

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


def test_decide_journal_bypass_redirect_blocks():
    # VG-5: класс (г) теперь БЛОК, не WARN -- permissionDecision="deny"
    # + permissionDecisionReason (ДОСЛОВНО MSG_JOURNAL_BLOCK), НЕ
    # additionalContext; exit_code остаётся 0 (см. докстринг раздела v3).
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_decide_journal_bypass_printf_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('printf \'{"event":"x"}\' logs/routing-log.jsonl')
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_decide_journal_bypass_requires_routing_log_substring():
    # Редирект в произвольный файл БЕЗ "routing-log" И вне logs/*.jsonl
    # -- не про журнал, класс (г) не триггерится (самостоятельное
    # решение, см. докстринг модуля -- заголовок класса "запись в
    # журнал", не "любой редирект").
    exit_code, output = hygiene_gate.decide(_bash_payload("ls > out.txt"))
    assert exit_code == 0
    assert output is None


def test_decide_journal_bypass_case_insensitive():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> LOGS/ROUTING-LOG.JSONL")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


# ---------------------------------------------------------------------
# VG-5 (2026-07-23) -- класс (г) БЛОК: остальные формы записи (DoD п.1)
# ---------------------------------------------------------------------


def test_vg5_block_sed_inplace():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("sed -i 's/x/y/' logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_vg5_sed_without_dash_i_does_not_block():
    # Граница: sed БЕЗ -i (печатает, не правит на месте) -- НЕ форма
    # записи сама по себе (нет ">"/printf/echo/tee/open-write тоже).
    exit_code, output = hygiene_gate.decide(
        _bash_payload("sed -n '1p' logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_vg5_block_python_open_append_mode():
    command = "python -c \"open('logs/routing-log.jsonl','a').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    # python -c -- независимый WARN-класс (в) тоже сработал, инфа
    # рядом с блоком (см. докстринг раздела v3, "СЕМАНТИКА КОМБИНАЦИИ").
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_vg5_python_open_read_mode_does_not_block_via_open_indicator():
    # open(path,'r') -- чтение, не форма записи; substring "routing-log"
    # есть, но ни один write-индикатор (redirect/printf/echo/sed-i/tee/
    # open-write-mode) в этом statement не совпадает.
    command = "python -c \"print(open('logs/routing-log.jsonl','r').read())\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    # python -c сам по себе -- независимый WARN-класс (в), не блок.
    assert output is not None
    assert "permissionDecision" not in output["hookSpecificOutput"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in output["hookSpecificOutput"]["additionalContext"]


def test_vg5_block_tee():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo hi | tee logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_vg5_block_heredoc_redirect():
    command = 'cat <<EOF >> logs/routing-log.jsonl\n{"event":"x"}\nEOF'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


# ---------------------------------------------------------------------
# F-53-2 (Lead, liveness-проба D-0093, 2026-07-23) -- квотирование-
# осознанный редирект: живой ложный БЛОК на read-only
# `grep -c ">" logs/routing-log.jsonl` (formal reject t-302 attempt 1,
# failure_class spec) -- кавычённый `>` (аргумент-строка, не shell-
# редирект) НЕ должен считаться формой записи. Прочие индикаторы
# (printf/echo/sed -i/tee/open-write-mode) не задеваются.
# ---------------------------------------------------------------------


def test_f53_2_grep_dash_c_quoted_arrow_journal_read_no_warn():
    # Живой FP Lead'а, ДОСЛОВНО.
    exit_code, output = hygiene_gate.decide(
        _bash_payload('grep -c ">" logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is None


def test_f53_2_grep_quoted_arrow_journal_read_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('grep ">" logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is None


def test_f53_2_unquoted_redirect_single_still_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x > logs/foo.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f53_2_unquoted_redirect_append_still_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/foo.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f53_2_quoted_data_but_redirect_outside_quotes_still_blocks():
    # Кавычки вокруг ДАННЫХ ("x"), редирект `>` -- ВНЕ кавычек: реальная
    # запись, должна блокироваться, несмотря на маскирование кавычек.
    exit_code, output = hygiene_gate.decide(
        _bash_payload('echo "x" > logs/foo.jsonl')
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f53_2_quoted_arrow_as_data_plus_real_redirect_still_blocks():
    # Кавычённый '>' -- данные printf'а; реальный `>>` -- ВНЕ кавычек,
    # настоящий редирект в журнал -- должен блокироваться.
    command = "printf '%s\\n' '>' >> logs/foo.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f53_2_mask_quoted_segments_unit():
    # Юнит на саму функцию маскирования -- кавычки внутри маскируются,
    # текст вне кавычек не тронут.
    masked = hygiene_gate._mask_quoted_segments('grep -c ">" logs/x.jsonl')
    assert ">" not in masked
    assert "logs/x.jsonl" in masked


# ---------------------------------------------------------------------
# F-53 (критик, доп. к VG-5, 2026-07-23) -- belt-and-suspenders:
# additionalContext ВСЕГДА дублирует причину блока класса (г), не
# только permissionDecisionReason -- страховка на случай, если харнесс
# не исполняет permissionDecision="deny" (в репо на момент задачи нет
# живого прецедента deny -- единственный живой блокирующий гейт,
# dispatch_gate.py, блокирует через exit-код 2, другой канал). Мёртвый
# deny должен деградировать в видимый WARN (additionalContext), не в
# полную тишину.
# ---------------------------------------------------------------------


def test_f53_block_carries_both_deny_fields_and_matching_additional_context():
    # DoD п.2 (доработка): на блокирующем вызове ОБА поля присутствуют
    # -- permissionDecision="deny"+permissionDecisionReason=
    # MSG_JOURNAL_BLOCK И additionalContext, начинающийся с ТОЙ ЖЕ
    # причины (belt-and-suspenders -- дублирование, не замена).
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    assert "additionalContext" in hso
    assert hso["additionalContext"].startswith(
        "Командная гигиена: " + hygiene_gate.MSG_JOURNAL_BLOCK
    )


def test_f53_block_plus_other_warn_class_both_texts_present_not_overwritten():
    # DoD п.2: при одновременном срабатывании WARN-класса (а)/(б)/(в)
    # его текст присутствует В additionalContext РЯДОМ с причиной
    # блока -- ни один текст не затирает другой.
    command = "cd gateway && echo evil >> logs/routing-log.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK in ctx
    assert hygiene_gate.MSG_CD_PREFIX in ctx


def test_f53_pure_warn_call_has_no_deny_fields_regression():
    # DoD п.2 (регресс существующего поведения): вызов, который
    # триггерит ТОЛЬКО WARN-классы (а)/(б)/(в) -- БЕЗ класса (г) --
    # НЕ несёт ни permissionDecision, ни permissionDecisionReason;
    # additionalContext остаётся в прежнем WARN-формате.
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert "permissionDecisionReason" not in hso
    assert hygiene_gate.MSG_CD_PREFIX in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


# ---------------------------------------------------------------------
# VG-5 -- НЕ-блок: чтение журнала шеллом (DoD п.2, design п.2 спеки)
# ---------------------------------------------------------------------


def test_vg5_tail_journal_read_only_no_warn():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("tail -n 5 logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_vg5_cat_journal_read_only_no_warn():
    exit_code, output = hygiene_gate.decide(_bash_payload("cat logs/routing-log.jsonl"))
    assert exit_code == 0
    assert output is None


def test_vg5_wc_journal_read_only_no_warn():
    exit_code, output = hygiene_gate.decide(_bash_payload("wc -l logs/routing-log.jsonl"))
    assert exit_code == 0
    assert output is None


def test_vg5_echo_to_non_journal_file_stays_unclassified():
    # DoD п.2: echo >> в НЕ-журнальный файл -- ни блок, ни WARN (нет
    # класса (г); прочие классы этой команды тоже не триггерят).
    exit_code, output = hygiene_gate.decide(_bash_payload("echo hi >> notes.txt"))
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# VG-5 -- граничные/adversarial формы пути (DoD п.3)
# ---------------------------------------------------------------------


def test_vg5_relative_dot_slash_path_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> ./logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_vg5_absolute_path_blocks():
    command = "echo x >> /home/user/Operating-System-for-LLMs/logs/routing-log.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_vg5_quoted_path_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('echo x >> "logs/routing-log.jsonl"')
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_vg5_variable_path_not_recognized_no_block_honest_limitation():
    # Честное ограничение (спека прямо требует задокументировать, не
    # молчать): путь через $-переменную НЕ распознаётся как журнальный
    # -- не пойман статическим текстовым матчером, НЕ блок.
    exit_code, output = hygiene_gate.decide(_bash_payload("echo x >> $F"))
    assert exit_code == 0
    assert output is None


def test_vg5_compound_benign_then_write_blocks():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("ls -la && echo bad >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_vg5_broadened_target_other_jsonl_under_logs_blocks():
    # Design-текст спеки: "покрыть и *.jsonl под logs/", не только
    # буквально routing-log.jsonl.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/other-name.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_vg5_non_jsonl_file_under_logs_not_broadened_target():
    # Граница расширения: *.txt под logs/ -- НЕ подпадает под
    # JOURNAL_JSONL_UNDER_LOGS_RE (нет ".jsonl"), substring
    # "routing-log" тоже отсутствует -- не про журнал вовсе.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/other-name.txt")
    )
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# VG-5 -- стейтмент-скоупинг (собственная живая находка builder'а):
# цель и форма записи должны быть в ОДНОМ statement, не где угодно в
# команде (см. докстринг раздела v3, "СТЕЙТМЕНТ-СКОУПИНГ")
# ---------------------------------------------------------------------


def test_vg5_read_then_unrelated_write_different_statement_no_warn():
    # Живой FP builder'а этой сессии (форензика, не гипотеза): ДО
    # стейтмент-скоупинга substring "routing-log" (в первом statement)
    # + токен "echo" (во втором) триггерили класс (г) целиком по
    # команде, хотя echo пишет НЕ в журнал -- отдельный, невиновный
    # statement.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("cat logs/routing-log.jsonl; echo done")
    )
    assert exit_code == 0
    assert output is None


def test_vg5_journal_read_piped_to_unrelated_tee_no_warn():
    # Тот же класс: чтение журнала, пайп в tee С ДРУГИМ файлом --
    # аргумент tee не журнал, цель и форма записи в РАЗНЫХ statement'ах.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("cat logs/routing-log.jsonl | tee /tmp/out.txt")
    )
    assert exit_code == 0
    assert output is None


def test_vg5_write_and_target_in_same_statement_still_blocks():
    # Контрольная позитивная форма того же класса (не только
    # негативная сторона) -- когда target и write-форма В ОДНОМ
    # statement, блок остаётся.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl; echo unrelated")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# ---------------------------------------------------------------------
# VG-5 -- живой FP координатора: git -C <dir> компаунд (2026-07-23)
# ---------------------------------------------------------------------


def test_vg5_git_dash_capital_c_compound_add_commit_push_no_warn():
    # Живой FP координатора (доп. к спеке VG-5, 2026-07-23): команда
    # вида `git -C <dir> add ... logs/routing-log.jsonl ... && git -C
    # <dir> commit -m "..." && git -C <dir> push -u origin ...`
    # получила от hygiene_gate WARN "журнал пишется только Edit/Write"
    # -- GIT_COMMIT_RE/GIT_STATEMENT_RE (до фикса) требовали подкоманду
    # СРАЗУ после "git\s+", `-C <dir>` между ними ломал матч. Форма
    # координатора: git -C, компаунд из ТРЁХ git-команд, журнальный
    # путь среди НЕСКОЛЬКИХ аргументов add.
    command = (
        "git -C /home/user/Operating-System-for-LLMs add docs/x.md "
        "logs/routing-log.jsonl CURRENT_CONTEXT.md && "
        'git -C /home/user/Operating-System-for-LLMs commit -m "docs: old -> new" && '
        "git -C /home/user/Operating-System-for-LLMs push -u origin main"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_vg5_git_dash_capital_c_single_add_no_warn():
    # Форма-минимум того же фикса: одиночный git -C add без компаунда.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git -C /home/user/Operating-System-for-LLMs add logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_vg5_git_dash_capital_c_commit_message_arrow_stripped_no_warn():
    # -C + commit -m с "->" в тексте сообщения (не про журнал) --
    # message-стриппер тоже должен видеть "git -C ... commit".
    command = 'git -C /home/user/Operating-System-for-LLMs commit -m "routing-log: old -> new"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


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


def test_p5_grep_journal_path_read_only_no_warn():
    # П5 (handoff 07-22 вечер, батч мелочей) -- read-only обращение
    # grep'ом к журнальному пути. ЭМПИРИКА (правило 3): против ТЕКУЩЕГО
    # кода этого файла (уже несёт v2/t-255 порт) заявленный в спеке
    # false positive НЕ воспроизводится -- _is_journal_bypass() требует
    # ">" ИЛИ printf/echo в команде, простой grep без них не триггерит
    # ни до, ни после этого коммита; тест закрывает недостающий (ранее
    # непокрытый явным тестом) DoD-кейс, поведение не меняет.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("grep -n pattern logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_p5_rg_journal_path_read_only_no_warn():
    # П5, тот же класс, инструмент rg (ripgrep) вместо grep.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("rg pattern logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output is None


def test_p5_grep_with_context_flags_journal_path_no_warn():
    # Граница: -A/-B/-C context-флаги grep'а не вносят ">" в команду
    # (это НЕ shell-редирект) -- всё ещё тихо.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("grep -A2 -B2 pattern logs/routing-log.jsonl")
    )
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
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


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
    # VG-5: класс (г) теперь БЛОК -- проверяем permissionDecision/
    # permissionDecisionReason, не additionalContext (было MSG_JOURNAL_
    # BYPASS в additionalContext до промоции).
    command = 'git commit -m "x" && echo evil >> logs/routing-log.jsonl'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v2_true_positive_sed_inside_command_substitution_outside_message_still_triggers():
    command = "$(sed -n '1p' logs/routing-log.jsonl > logs/routing-log.jsonl.bak)"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v2_true_positive_printf_still_triggers_regress():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('printf \'{"event":"x"}\' >> logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


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
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v2_git_reset_not_in_whitelist_still_triggers():
    command = "git reset -- logs/routing-log.jsonl > /tmp/x.txt"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


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
