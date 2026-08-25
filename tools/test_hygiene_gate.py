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
import time
from pathlib import Path

import pytest

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


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True, гейт в проде): пин ПЕРЕВЁРНУТ на новое дефолтное поведение.
# ПРИЧИНА (записана ещё в пересдаче 3, П3): target "foo" -- НЕ корень
# репозитория -- под моделью cd-в-корень (П3) ЛЮБАЯ non-root цель -- WARN
# (MSG_CD_NON_ROOT_WARN), не MSG_CD_PREFIX (тот резервирован ТОЛЬКО за
# целью-корнем, деньги). Раньше (до включения) это было "предсказанной
# инверсией при будущем гипотетическом V5_ENABLED=True"; теперь это --
# фактическое поведение диска по умолчанию, не гипотеза.
def test_decide_powershell_tool_checked_too():
    payload = {"tool_name": "PowerShell", "tool_input": {"command": "cd foo && ls"}}
    exit_code, output = hygiene_gate.decide(payload)
    assert exit_code == 0
    assert output is not None
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_decide_clean_command_is_silent_pass():
    exit_code, output = hygiene_gate.decide(_bash_payload("python -m pytest tools/ -q"))
    assert exit_code == 0
    assert output is None


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ. ПРИЧИНА: target "gateway" -- НЕ корень
# репозитория -- под моделью cd-в-корень (П3) остаётся WARN
# (MSG_CD_NON_ROOT_WARN), не MSG_CD_PREFIX (тот теперь ТОЛЬКО для цели =
# корень репозитория).
def test_decide_cd_prefix_and_amp_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ, та же причина, что у
# test_decide_cd_prefix_and_amp_triggers выше -- target "gateway" не
# корень -> WARN (MSG_CD_NON_ROOT_WARN), не MSG_CD_PREFIX.
def test_decide_cd_prefix_with_semicolon_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway; python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


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


# F5(A) (сужение предиката pyc, 2026-08-25): фикстура была `print(1)` --
# доказанно ЧИСТЫЙ payload, при новой трёхклассовой классификации P ->
# ТИШИНА, что убило бы сам предмет пина ("python -c триггерит warn").
# Переведена на мутирующий payload (класс M), текст MSG_PYTHON_DASH_C
# НЕ меняется (F5b) -- см. отчёт builder'а t-605/спеку "ПОПРАВКА LEAD
# 16:35" за полный разбор.
def test_decide_python_dash_c_triggers():
    command = 'python -c "open(\'x.txt\',\'w\').write(\'x\')"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


# F5(A): та же причина, heredoc-форма -- фикстура на мутирующий payload.
def test_decide_python_heredoc_triggers():
    command = "python - <<EOF\nopen('x.txt','w').write('x')\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
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


# ---------------------------------------------------------------------
# v4 (П4, батч мелочей после калибровки №6) -- Set-Location-префикс +
# 2>&1-в-commit-сообщении.
# ---------------------------------------------------------------------


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ, та же причина, что у
# test_decide_cd_prefix_and_amp_triggers выше: target "gateway" не
# корень -> WARN (MSG_CD_NON_ROOT_WARN), не MSG_CD_PREFIX.
def test_p4_set_location_prefix_and_amp_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("Set-Location gateway && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ, та же PowerShell-форма точка-с-запятой,
# та же причина (target "gateway" не корень -> WARN).
def test_p4_set_location_prefix_with_semicolon_triggers():
    exit_code, output = hygiene_gate.decide(_bash_payload("Set-Location gateway; python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_p4_bare_set_location_without_continuation_does_not_trigger():
    # То же прежнее поведение хелпера, что и bare "cd" -- не расширяем.
    exit_code, output = hygiene_gate.decide(_bash_payload("Set-Location gateway"))
    assert exit_code == 0
    assert output is None


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ, та же причина: target "gateway"
# (регистронезависимо) не корень -> WARN (MSG_CD_NON_ROOT_WARN), не
# MSG_CD_PREFIX.
def test_p4_set_location_case_insensitive():
    exit_code, output = hygiene_gate.decide(_bash_payload("set-location gateway && ls"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_p4_2_greater_and_1_inside_commit_message_does_not_trigger():
    # Край спеки: "2>&1" ВНУТРИ текста -m/--message -- не про реальный
    # shell-редирект, не должен триггерить класс (б).
    command = 'git commit -m "note about pytest 2>&1 output redirection"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_p4_2_greater_and_1_outside_commit_message_still_triggers():
    # Контроль: РЕАЛЬНЫЙ 2>&1 (не внутри -m-сообщения) по-прежнему
    # триггерит -- фикс не ослабляет истинный позитив.
    exit_code, output = hygiene_gate.decide(
        _bash_payload('git commit -m "clean message" && python x.py 2>&1')
    )
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


def test_p4_heredoc_body_2_greater_and_1_still_warns_regression():
    # Регресс: heredoc-тело (-F - <<EOF) намеренно НЕ тронуто этим
    # фиксом -- см. существующий test_f1_heredoc_body_2_greater_and_1_
    # still_warns_class_b_raw_command_check выше (не дублируем, только
    # подтверждаем через новый хелпер напрямую).
    command = "git commit -F - <<EOF\nsome text with 2>&1 inside\nEOF"
    stripped = hygiene_gate._strip_commit_message_arg_only(command)
    assert "2>&1" in stripped


# --- инвариант (обязателен спекой): новый класс -- ТОЛЬКО warn -------


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ. ПРИЧИНА -- сама СУТЬ финального дизайна:
# класс (б) " 2>&1" здесь ОПРЕДЕЛЁННЫЙ (нет кавычек/heredoc вокруг него в
# "python x.py 2>&1") -> DENY; cd(gateway) -- не корень -> WARN
# (MSG_CD_NON_ROOT_WARN, не MSG_CD_PREFIX). "Новый класс НИКОГДА не несёт
# permissionDecision" перестало быть верным -- это и есть цель промоции
# класса 2>&1 (deny требует определённости, но этот 2>&1 определён).
def test_p4_new_class_never_carries_permission_decision():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('Set-Location gateway && python x.py 2>&1')
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_p4_journal_block_class_still_carries_permission_decision_regression():
    # Старый класс (г) по-прежнему БЛОК -- инвариант в ДРУГУЮ сторону,
    # регресс не задет этой правкой.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo done >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ -- target "gateway" не корень -> текст
# MSG_CD_NON_ROOT_WARN, не MSG_CD_PREFIX, рядом с блоком журнала (блок
# журнала сам остаётся первой причиной, не задет).
def test_p4_new_class_plus_journal_block_block_wins_new_class_added_alongside():
    # "команда, попадающая И в новый класс, И в блокирующий журнальный:
    # блок побеждает" -- И новый триггер (Set-Location) присутствует
    # РЯДОМ в additionalContext, не подменяя причину блока.
    command = "Set-Location gateway && echo evil >> logs/routing-log.jsonl"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK in hso["additionalContext"]


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


# M9 (пересдача 1, ЗАДОКУМЕНТИРОВАНО -- W3-сценарий спеки): под
# V5_ENABLED=True (пересдачи 1-2, ДО фикса П2) `permissionDecision`
# оставался "deny", но `permissionDecisionReason` ИНВЕРТИРОВАЛСЯ: ЧАСТЬ 1
# маскировала тело -c ПЕРЕД проверкой класса (г) -- "routing-log.jsonl"
# внутри payload'а не было видно _is_journal_bypass(masked),
# journal_hit=False; ЧАСТЬ 3 (write-намерение, читает СЫРОЕ тело)
# находила `open(...,'a')` и денала САМА, но через MSG_PYTHON_DASH_C, не
# MSG_JOURNAL_BLOCK.
#
# ПЕРЕСДАЧА 3 (координатор, БЛОКЕР П2, ЭТОТ ПИН СНОВА ЗЕЛЁНЫЙ, УЖЕ НЕ
# ИНВЕРТИРУЕТСЯ -- подтверждено эмпирически, безопасный in-process
# красный прогон): П2 прогоняет _is_journal_bypass ПОВТОРНО по СЫРОМУ
# телу payload'а (см. докстринг _collect_v5_signals в hygiene_gate.py) --
# `open('logs/routing-log.jsonl','a')` уже входит в набор _has_write_form
# (OPEN_WRITE_MODE_RE), значит journal_hit СНОВА становится True для
# ЭТОГО конкретного примера, и permissionDecisionReason возвращается к
# MSG_JOURNAL_BLOCK -- ВСЕ ТРИ ассерции этого теста, как написаны,
# ПРОХОДЯТ под V5_ENABLED=True без изменений тела.
#
# ПЕРЕСДАЧА 4 (перепроектировка, слово оператора): части 1/3 УДАЛЕНЫ
# ЦЕЛИКОМ -- этот пин ОСТАЁТСЯ зелёным (не инвертируется), ПРИЧИНА ТА ЖЕ
# -- `_is_journal_bypass` всегда читала СЫРУЮ команду напрямую (не через
# маскировку), класс (г) никогда не зависел от масковки/write-намерения
# вовсе (см. tools/hygiene_gate.py -- В4). Ссылки на
# `test_v5_write_intent_inside_dashc_denies_via_python_class_not_journal_
# class`/`test_v5_p2_open_write_mode_inside_dashc_denies_via_journal_
# class_after_blocker_fix` выше -- ИСТОРИЧЕСКИЕ (эти тесты удалены/
# переименованы в пересдаче 4 вместе с частью 3 -- см. текущий
# `test_v5_open_write_mode_inside_dashc_denies_via_journal_class` за тот
# же пример).
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


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, НЕ
# входит в буквальную четвёрку F5(A), см. отчёт builder'а t-605 п.5) --
# ОЖИДАНИЕ меняется, фикстура НЕ трогается (смысл пина -- "open
# read-mode -- не форма записи", менять сам payload на мутирующий
# исказил бы именно этот предмет): payload теперь ДОКАЗАННО чистый (P)
# для класса (в) тоже -- итог ПОЛНАЯ тишина (сильнее прежнего пина --
# подтверждает бездействие И класса (г), И класса (в) одновременно).
def test_vg5_python_open_read_mode_does_not_block_via_open_indicator():
    # open(path,'r') -- чтение, не форма записи; substring "routing-log"
    # есть, но ни один write-индикатор (redirect/printf/echo/sed-i/tee/
    # open-write-mode) в этом statement не совпадает.
    command = "python -c \"print(open('logs/routing-log.jsonl','r').read())\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


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


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ -- target "gateway" не корень -> WARN-текст
# MSG_CD_NON_ROOT_WARN, не MSG_CD_PREFIX, рядом с блоком журнала.
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
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in ctx


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ. ПРИЧИНА -- сама СУТЬ финального дизайна:
# " 2>&1" (класс б) в "python x.py 2>&1" ОПРЕДЕЛЁННЫЙ (нет кавычек/
# heredoc) -> DENY; cd(gateway) -- не корень -> WARN
# (MSG_CD_NON_ROOT_WARN). "Пустой WARN-only вызов" перестал быть
# пустым-от-deny -- вызов теперь ДЕЙСТВИТЕЛЬНО несёт deny-поля (та же
# причина, что test_p4_new_class_never_carries_permission_decision
# выше) -- имя теста ("has_no_deny_fields") теперь описывает то, что
# БОЛЬШЕ НЕ ВЕРНО для этой команды; функция сохранена (не переименована)
# для непрерывности M9-отслеживания, тело перевёрнуто.
def test_f53_pure_warn_call_has_no_deny_fields_regression():
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
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


# ---------------------------------------------------------------------
# F.3 (ремедиация калибровки №8, узел F.3, 2026-08-20) -- живой ложный
# БЛОК: чтение журнала read-only инструментом + НЕСВЯЗАННЫЙ редирект
# (`2>/dev/null`, `2>&1`, `> /tmp/out.txt`) в ТОМ ЖЕ statement денилось
# как класс (г) (журнал мимо Edit/Write), хотя редирект целится НЕ в
# журнал. См. _redirect_targets_journal/_READ_ONLY_HEAD_RE в
# hygiene_gate.py за полный разбор фикса.
# ---------------------------------------------------------------------


def test_f3_reported_bug_grep_dev_null_piped_no_block():
    # Живой репро координатора, ДОСЛОВНО.
    command = (
        'grep -c "reserve_engaged" logs/routing-log.jsonl tools/*.py '
        '2>/dev/null | grep -v ":0"'
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_f3_grep_dev_null_no_pipe_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('grep -c "reserve_engaged" logs/routing-log.jsonl 2>/dev/null')
    )
    assert exit_code == 0
    assert output is None


def test_f3_rg_dev_null_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload('rg "reserve_engaged" logs/routing-log.jsonl 2>/dev/null')
    )
    assert exit_code == 0
    assert output is None


def test_f3_cat_dev_null_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("cat logs/routing-log.jsonl 2>/dev/null")
    )
    assert exit_code == 0
    assert output is None


def test_f3_head_dev_null_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("head -n 5 logs/routing-log.jsonl 2>/dev/null")
    )
    assert exit_code == 0
    assert output is None


def test_f3_tail_dev_null_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("tail -n 5 logs/routing-log.jsonl 2>/dev/null")
    )
    assert exit_code == 0
    assert output is None


def test_f3_wc_dev_null_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("wc -l logs/routing-log.jsonl 2>/dev/null")
    )
    assert exit_code == 0
    assert output is None


def test_f3_sed_dash_n_dev_null_no_block():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("sed -n '1,5p' logs/routing-log.jsonl 2>/dev/null")
    )
    assert exit_code == 0
    assert output is None


def test_f3_grep_redirect_to_unrelated_file_no_block():
    # Редирект СТДАУТ (не только stderr) в файл, не связанный с журналом.
    exit_code, output = hygiene_gate.decide(
        _bash_payload('grep -c "x" logs/routing-log.jsonl > /tmp/out.txt')
    )
    assert exit_code == 0
    assert output is None


def test_f3_read_only_redirect_that_actually_targets_journal_still_blocks():
    # Контроль: read-only голова, но редирект РЕАЛЬНО целится в журнал --
    # остаётся блоком (heredoc-форма уже покрыта test_vg5_block_heredoc_
    # redirect ниже -- это простой grep-эквивалент того же принципа).
    exit_code, output = hygiene_gate.decide(
        _bash_payload('cat notes.txt > logs/routing-log.jsonl')
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert output["hookSpecificOutput"]["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_f3_true_positive_echo_append_still_blocks_after_fix():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo x >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f3_true_positive_printf_append_still_blocks_after_fix():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("printf '%s\\n' '{}' >> logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f3_true_positive_tee_still_blocks_after_fix():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("echo hi | tee logs/routing-log.jsonl")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f3_true_positive_heredoc_redirect_still_blocks_after_fix():
    command = 'cat <<EOF >> logs/routing-log.jsonl\n{"event":"x"}\nEOF'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f3_git_rm_not_in_read_only_heads_unrelated_redirect_still_blocks():
    # Регресс-контроль ГРАНИЦЫ фикса (D-0043 -- не сиблинг этого дефекта,
    # "git" НЕ входит в _READ_ONLY_HEAD_RE): не трогать существующее
    # поведение неперечисленных git-подкоманд -- см. пины
    # test_v2_git_rm_not_in_whitelist_still_triggers_if_it_would_otherwise/
    # test_v2_git_reset_not_in_whitelist_still_triggers выше в этом файле
    # (тела которых этой правкой НЕ меняются).
    exit_code, output = hygiene_gate.decide(
        _bash_payload("git rm logs/routing-log.jsonl > /tmp/log.txt")
    )
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f3_redirect_targets_journal_unit_fd_dup_not_a_target():
    # Юнит на саму функцию: `2>&1` -- fd-дублирование, не файловый
    # таргет -- не засчитывается как редирект В журнал.
    assert hygiene_gate._redirect_targets_journal(
        'grep -c "x" logs/routing-log.jsonl 2>&1'
    ) is False


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


# ---------------------------------------------------------------------
# часть C (синк Dog 07-29, D-0082) -- heredoc-скраб тела git commit
# -F - <<EOF ... EOF во всех 4 написаниях делимитера (голый EOF,
# 'EOF', "EOF", <<-EOF); маркерные слова ("routing-log", "printf",
# "->") внутри тела не должны триггерить класс (г), т.к. git-statement
# маскирование (_mask_git_statements) само по себе останавливается на
# первом "\n" внутри heredoc-тела и НЕ достаёт до него -- ровно дыра,
# которую закрывает эта часть.
# ---------------------------------------------------------------------


def _heredoc_journal_command(opener, closer="EOF"):
    return (
        f"git commit -F - {opener}\n"
        "old logs/routing-log.jsonl -> renamed, see printf example\n"
        f"{closer}"
    )


def test_c_heredoc_bare_delimiter_journal_words_not_blocked():
    command = _heredoc_journal_command("<<EOF")
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_c_heredoc_single_quoted_delimiter_journal_words_not_blocked():
    command = _heredoc_journal_command("<<'EOF'")
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_c_heredoc_double_quoted_delimiter_journal_words_not_blocked():
    command = _heredoc_journal_command('<<"EOF"')
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_c_heredoc_dash_variant_delimiter_journal_words_not_blocked():
    command = _heredoc_journal_command("<<-EOF")
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, найдена
# ПОЛНЫМ прогоном узкого набора после правок девятки, не входит в
# буквальную девятку -- см. отчёт builder'а t-605 доп.): `print(1)` ->
# P -> тишина, ломало бы предмет пина ("heredoc всё ещё ловится
# классом в") -- фикстура на мутирующий payload сохраняет "ловится".
def test_c_python_heredoc_still_caught_class_v_regress():
    # python - <<EOF -- НЕ git commit, класс (в) должен по-прежнему
    # ловить: COMMIT_HEREDOC_RE применяется ТОЛЬКО под гардом
    # GIT_COMMIT_RE (см. _strip_commit_messages) -- python-heredoc её
    # не проходит и не задет этой правкой.
    exit_code, output = hygiene_gate.decide(
        _bash_payload("python - <<EOF\nopen('x.txt','w').write('x')\nEOF")
    )
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


def test_c_heredoc_body_unrelated_regression_still_blocks_real_write():
    # Контроль в другую сторону: НЕ git commit heredoc, реально
    # пишущий в журнал -- должен остаться БЛОКОМ (регресс
    # test_vg5_block_heredoc_redirect не задет частью C, гард
    # GIT_COMMIT_RE не совпадает с "cat <<EOF").
    command = 'cat <<EOF >> logs/routing-log.jsonl\n{"event":"x"}\nEOF'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_c_heredoc_unit_strip_commit_messages_removes_body():
    command = _heredoc_journal_command("<<EOF")
    stripped = hygiene_gate._strip_commit_messages(command)
    assert "routing-log" not in stripped.lower()
    assert "printf" not in stripped.lower()


# ---------------------------------------------------------------------
# F1 (критик t-339) -- две живые репродукции блокирующего класса (г):
# heredoc-скраб раньше (1) поглощал РЕАЛЬНУЮ команду на остатке строки-
# опенера heredoc'а и (2) глобально ел ЛЮБОЙ heredoc где-то ещё в
# составной команде, стоило встретиться "git commit" где угодно.
# ---------------------------------------------------------------------


def test_f1_critic_repro1_heredoc_with_real_write_on_opener_line_still_blocks():
    # Остаток строки-опенера (` && echo "{}" >> logs/routing-log.jsonl`)
    # -- РЕАЛЬНАЯ, отдельная shell-команда (heredoc не поглощает остаток
    # строки в bash), не часть heredoc-тела -- должна остаться видимой.
    command = (
        'git commit -F - <<EOF && echo "{}" >> logs/routing-log.jsonl\n'
        "irrelevant heredoc body text\n"
        "EOF"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f1_critic_repro1_control_same_command_without_heredoc_still_blocks():
    # Контроль критика: та же команда БЕЗ heredoc должна была и раньше,
    # и сейчас давать deny -- сверка, что F1 не сломал существующий
    # регресс (не только "новый" случай стал зелёным).
    command = 'git commit -F - "x" && echo "{}" >> logs/routing-log.jsonl'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_f1_critic_repro2_python_heredoc_after_git_commit_still_blocks():
    # heredoc `python - <<'PY'` НЕ относится к git commit (класс (в)
    # ловит его отдельно) -- его тело с реальной записью в журнал
    # должно остаться видимым классу (г), несмотря на "git commit"
    # где-то раньше в той же составной команде.
    command = (
        "git commit -m \"x\" && python - <<'PY'\n"
        "open('logs/routing-log.jsonl', 'a').write('x')\n"
        "PY"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# M9 (пересдача 1, ЗАДОКУМЕНТИРОВАНО, РАСХОЖДЕНИЕ СПЕКИ С РЕАЛЬНОСТЬЮ
# правило 3): инвертируется при V5_ENABLED=True (КРАСНЫЙ прогон,
# эмпирика). Спека M9 атрибутирует этот класс инверсии МАСКИРОВКЕ
# ("маскировка это отменяет намеренно") -- ЭМПИРИЧЕСКИ НЕ подтвердилось:
# `git commit -F - <<EOF` -- НЕ python/python3/py-heredoc,
# _mask_nested_payloads его вообще не трогает (нет литерала
# "python"/"py" перед "-...<<"), `masked` здесь идентичен исходной
# команде. РЕАЛЬНАЯ причина (пересдача 1) -- сама промоция класса (б)
# WARN->deny (часть 2) поверх УЖЕ СУЩЕСТВОВАВШЕГО (до этой задачи, см.
# докстринг COMMIT_HEREDOC_RE выше) остатка: " 2>&1" внутри
# git-commit-heredoc-тела не вырезался `_strip_commit_message_arg_only`
# (та вырезает только -m/--message, НЕ heredoc-тело `-F - <<EOF`) --
# уже раньше давало ложный WARN, тогда давало бы ложный DENY.
#
# ПЕРЕСДАЧА 2 (координатор, БЛОКЕР 1, ФИКС): класс (б) внутри
# `_decide_v5` тогда стал читать `_strip_commit_messages` (не
# `_strip_commit_message_arg_only`) -- heredoc-тело commit-сообщения
# ПОЛНОСТЬЮ вырезалось ДО проверки " 2>&1". ЭТОТ ПИН ПРОДОЛЖАЛ быть
# инвертированным (пересдачи 2-4) -- вырезание убирало саму ВИДИМОСТЬ
# " 2>&1" классу (б) СОВСЕМ, команда становилась ПОЛНОСТЬЮ тихой
# (`output is None`), а не "остаётся WARN, просто не денаит", как
# ожидали старые ассерции этого теста.
#
# ПЕРЕСДАЧА 5 (координатор, финальный фикс, третий критик-вход, Ф2,
# ЭТОТ ПИН СНОВА ЗЕЛЁНЫЙ, УЖЕ НЕ ИНВЕРТИРУЕТСЯ -- подтверждено
# эмпирически, безопасный in-process красный прогон): класс (б)
# полностью заменён на `_collect_redirect_signal` (кавычки через
# `_mask_quoted_segments`, НЕ git-специфичное вырезание) -- heredoc
# теперь трактуется ЕДИНООБРАЗНО (любой `<<` вне кавычек на
# маскированном тексте -> WARN, не тишина, не deny). Для ЭТОЙ команды:
# " 2>&1" видим (heredoc-тело -- НЕ кавычки), "<<" тоже видим (сам
# heredoc-опенер) -> WARN с MSG_REDIRECT_STDERR -- ВСЕ ассерции этого
# теста, как написаны, СНОВА проходят под V5_ENABLED=True без изменений
# тела (V4 и V5 теперь СОГЛАСНЫ на этом примере). См.
# test_v5_git_commit_heredoc_2_greater_1_now_warns_uniform_heredoc_rule
# ниже за тот же пример явно, под monkeypatch.
def test_f1_heredoc_body_2_greater_and_1_still_warns_class_b_raw_command_check():
    # Критик t-339: фикс закрывает ТОЛЬКО класс (г) -- классы (а)/(б)/(в)
    # считаются по СЫРОЙ команде (_collect_warn_classes), скраб их не
    # касается. " 2>&1" внутри git-commit-heredoc-тела по-прежнему
    # триггерит WARN класса (б) -- НЕ регресс, задокументированный
    # остаток (см. докстринг COMMIT_HEREDOC_RE).
    command = "git commit -F - <<EOF\nsome text with 2>&1 inside\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None
    assert "permissionDecision" not in output["hookSpecificOutput"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in output["hookSpecificOutput"]["additionalContext"]


def test_f1_heredoc_belongs_to_git_commit_unit():
    command = 'git commit -F - <<EOF\nbody\nEOF'
    match = hygiene_gate.COMMIT_HEREDOC_RE.search(command)
    assert match is not None
    assert hygiene_gate._heredoc_belongs_to_git_commit(command, match) is True


def test_f1_heredoc_not_belonging_to_git_commit_unit():
    command = "git commit -m \"x\" && cat <<EOF\nbody\nEOF"
    match = hygiene_gate.COMMIT_HEREDOC_RE.search(command)
    assert match is not None
    assert hygiene_gate._heredoc_belongs_to_git_commit(command, match) is False


def test_f1_is_python_heredoc_opener_unit():
    command = "python - <<'PY'\nbody\nPY"
    match = hygiene_gate.COMMIT_HEREDOC_RE.search(command)
    assert match is not None
    assert hygiene_gate._is_python_heredoc_opener(command, match) is True


def test_f1_non_python_heredoc_opener_unit():
    command = "git commit -F - <<EOF\nbody\nEOF"
    match = hygiene_gate.COMMIT_HEREDOC_RE.search(command)
    assert match is not None
    assert hygiene_gate._is_python_heredoc_opener(command, match) is False


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


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ -- target "gateway" не корень -> WARN-текст
# MSG_CD_NON_ROOT_WARN, не MSG_CD_PREFIX; " 2>&1" здесь ОПРЕДЕЛЁННЫЙ (вне
# кавычек -c-аргумента, heredoc нет) -> реально ДЕНАЕТ теперь (не только
# WARN); python -c остаётся отдельным WARN (класс в никогда не денает).
# F5(A) (сужение предиката pyc, 2026-08-25): фикстура `print(1)` была
# чистая (класс P -> pyc-строка исчезла бы из ctx) -- переведена на
# мутирующий payload, чтобы сохранить предмет пина ("все сработавшие
# классы перечислены в additionalContext").
def test_decide_multiple_classes_all_listed():
    command = 'cd gateway && python -c "open(\'x.txt\',\'w\').write(\'x\')" 2>&1'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx
    assert hygiene_gate.MSG_PYTHON_DASH_C in ctx


# M9 (пересдача 1, ЗАДОКУМЕНТИРОВАНО): под V5_ENABLED=True (пересдачи
# 1-2, ДО П3) инвертировался -- target "x" НЕ являлся "gateway" (B4
# исключение неприменимо в СТАРОЙ модели), значит cd-префикс денался как
# ОБЫЧНЫЙ (MSG_CD_PREFIX). ПЕРЕСДАЧА 3 (координатор, БЛОКЕР П3, ЭТОТ ПИН
# СНОВА ЗЕЛЁНЫЙ, УЖЕ НЕ ИНВЕРТИРУЕТСЯ -- подтверждено эмпирически,
# безопасный in-process красный прогон): условие ИНВЕРТИРОВАНО -- денает
# ТОЛЬКО target == корень репозитория; "x" НЕ является корнем (та же
# причина, что и не был "gateway"), значит под НОВОЙ моделью "cd x && y"
# -- WARN (MSG_CD_NON_ROOT_WARN), permissionDecision СНОВА отсутствует --
# ассерция теста, как написана, СНОВА проходит без изменений тела (два
# независимых инверсии условия "компенсировали" друг друга для ЭТОГО
# конкретного примера чисто случайно, не по замыслу).
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


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ -- та же причина, что
# test_f53_pure_warn_call_has_no_deny_fields_regression выше: cd(gateway)
# не корень -> WARN, но " 2>&1" -- реальный (определённый) DENY.
#
# СМОК-ТЕСТ УРОВНЯ SUBPROCESS -- ЗАВЯЗАН НА ДЕФОЛТ ДИСКА (задокументировано
# явно, как потребовал координатор): этот тест спавнит `hygiene_gate.py`
# ОТДЕЛЬНЫМ процессом (`_run_hook`), который читает `V5_ENABLED` из
# РЕАЛЬНОГО файла на диске -- monkeypatch здесь НЕ работает (другой
# процесс, своя копия модуля). Тест пинует ПОВЕДЕНИЕ ПРОДА В ТОЧНОСТИ,
# каким его увидит реальный харнесс -- в этом его ценность (единственная
# форма в этом файле, которая ловит "выключатель откатили на диске, а
# код забыли"). Он ОБЯЗАН упасть, если константу когда-либо откатят на
# `False` -- это ПРАВИЛЬНОЕ поведение (откат обязан быть виден по
# красным тестам, не пройти молча); НЕ чинить его при откате
# добавлением monkeypatch или изменением ожиданий -- красный цвет здесь
# и есть детектор регресса выключателя.
def test_echo_json_dirty_command_exit0_with_stdout_json():
    payload = _bash_payload("cd gateway && python x.py 2>&1")
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    data = json.loads(result.stdout)
    hso = data["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
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


# M9 (t-378, ВЫКЛЮЧАТЕЛЬ ВКЛЮЧЁН координатором 2026-08-09 -- ДЕФОЛТ ДИСКА
# ТЕПЕРЬ True): пин ПЕРЕВЁРНУТ. НЕ входил в предсказанный in-process
# список 11 пунктов (безопасный in-process прогон физически не мог его
# увидеть -- он спавнит хук ОТДЕЛЬНЫМ процессом через `_run_hook`,
# читающим `V5_ENABLED` с ДИСКА, а не из уже-импортированного объекта
# модуля; monkeypatch не долетает до дочернего процесса). Найден
# координатором на живой пробе включения, не мной. ПРИЧИНА -- ТА ЖЕ, что
# у test_echo_json_dirty_command_exit0_with_stdout_json: target "репо"
# не корень -> WARN (MSG_CD_NON_ROOT_WARN); " 2>&1" здесь определённый
# (кириллица не мешает -- маскировка кавычек не находит их вовсе, весь
# текст виден как есть) -> реальный DENY.
#
# СМОК-ТЕСТ УРОВНЯ SUBPROCESS -- ЗАВЯЗАН НА ДЕФОЛТ ДИСКА (та же оговорка,
# что у test_echo_json_dirty_command_exit0_with_stdout_json выше): пинует
# ПОВЕДЕНИЕ ПРОДА через реальный дочерний процесс, читающий диск, а НЕ
# monkeypatch-состояние. ОБЯЗАН упасть при откате `V5_ENABLED` на `False`
# -- это ПРАВИЛЬНОЕ поведение (детектор регресса выключателя, откат
# обязан быть виден по красным тестам).
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
    hso = data["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx


def test_adversarial_very_long_command_no_crash():
    long_command = "python -m pytest " + ("a" * 100_000) + " -q"
    payload = _bash_payload(long_command)
    result = _run_hook(json.dumps(payload), text=True, encoding="utf-8")
    assert result.returncode == 0
    assert result.stderr == ""


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, НЕ
# входит в буквальную четвёрку F5(A), см. отчёт builder'а t-605 п.6):
# исходный payload (`print('he said \"hi\" 2>&1')`) -- доказанно
# чистый (P), под новой классификацией decide() вернул бы ПОЛНУЮ
# тишину -- `json.loads(result.stdout)` упал бы на пустой строке.
# Фикстура переведена на мутирующий payload (класс M), нарощенная
# ТЕМ ЖЕ вложенно-кавычковым куском -- предмет пина ("вложенные
# кавычки не роняют subprocess") сохранён, additionalContext по-прежнему
# парсится и несёт MSG_PYTHON_DASH_C.
def test_adversarial_nested_quotes_no_crash():
    command = """python -c "print('he said \\"hi\\" 2>&1'); open('x.txt','w').write('x')" """
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


# =========================================================================
# V5 (эта задача, D-0069 выключатель) -- ВСЁ новое поведение ниже включено
# ТОЛЬКО через monkeypatch(hygiene_gate, "V5_ENABLED", True). Тесты
# СТАРОГО поведения выше эту константу НЕ трогают (она читается на каждый
# вызов decide() как модульный global -- см. её докстринг в hygiene_gate.py).
# =========================================================================


# --- ЧАСТЬ 1 (маскировка) УДАЛЕНА ЦЕЛИКОМ, ПЕРЕПРОЕКТИРОВКА (слово
# оператора): `_mask_nested_payloads`/`_split_nested_payloads`/
# `_nested_payload_bodies` и их юнит-тесты (test_mask_*) удалены вместе с
# кодом -- см. tools/hygiene_gate.py, докстринг раздела на месте бывшей
# части 1. Четыре теста decide()-уровня ниже переживают редизайн (логика
# по-прежнему верна БЕЗ масковки, по другим причинам) -- комментарии
# обновлены, чтобы не ссылаться на удалённый механизм.


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, НЕ
# входит в буквальную четвёрку F5(A), явно названа координатором в
# развилке t-605): исходный payload -- доказанно чистый (P) -> pyc-
# строка исчезла бы из ctx, ослабляя предмет пина. Фикстура переведена
# на мутирующий payload -- запись в ДРУГОЙ (не журнальный) файл
# "x.txt" -- сохраняет И предмет пина (класс в снова warn), И его
# ядро (класс г НЕ триггерит на "routing-log.jsonl" просто упомянутом
# как проза БЕЗ формы записи ПО ЭТОМУ target'у) -- даже строже
# прежнего: теперь видно, что РЕАЛЬНАЯ запись рядом (в другой файл) не
# путает журнальный класс.
def test_v5_python_c_body_mentioning_journal_path_as_prose_not_classified(monkeypatch):
    # Чистая проза внутри -c, упоминающая путь журнала, БЕЗ формы записи
    # (`>`/printf/echo/sed -i/tee/open-write/PS-командлет) -- журнальный
    # класс требует ОБЕИХ (target И форма) в одном statement (_is_journal_
    # bypass), только упоминания пути мало. cd/2>&1 тут вовсе нет в тексте.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        "python -c \"print('see routing-log.jsonl for details'); "
        "open('x.txt','w').write('x')\""
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]
    assert hygiene_gate.MSG_CD_PREFIX not in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR not in hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK not in hso["additionalContext"]


# ПОПРАВКА LEAD 17:2x, Ф1: ИСХОДНАЯ (до мутации) фикстура теста выше
# возвращается СОСЕДНИМ тестом -- честно, с ожиданием ПОЛНОЙ тишины
# (payload доказанно чист (P), журнальный класс и без того молчал --
# упоминание пути БЕЗ формы записи). Оба теста -- РАЗНЫЕ, законные
# пины: этот -- "чистое упоминание, класс в ТОЖЕ молчит", предыдущий
# (мутированный) -- "упоминание + РЕАЛЬНАЯ запись в ДРУГОЙ файл,
# класс (г) не путается, класс (в) warn".
def test_v5_python_c_body_mentioning_journal_path_as_prose_fully_silent_when_pure(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'python -c "print(\'see routing-log.jsonl for details\')"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# F5(A)-родственная правка -- та же причина/форма правки, что у теста
# выше (heredoc-двойник, координатор явно назвал его в развилке t-605).
def test_v5_python_c_heredoc_body_mentioning_journal_path_as_prose_not_classified(monkeypatch):
    # То же для heredoc-формы.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        "python - <<EOF\n"
        "print('see routing-log.jsonl for details')\n"
        "open('x.txt','w').write('x')\n"
        "EOF"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]
    assert hygiene_gate.MSG_CD_PREFIX not in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR not in hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK not in hso["additionalContext"]


# ПОПРАВКА LEAD 17:2x, Ф1: heredoc-двойник исходной (до мутации)
# фикстуры -- та же причина, что у теста выше.
def test_v5_python_c_heredoc_body_mentioning_journal_path_as_prose_fully_silent_when_pure(
    monkeypatch,
):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "python - <<EOF\nprint('see routing-log.jsonl for details')\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v5_real_cd_root_denies_regardless_of_quoted_text_elsewhere(monkeypatch):
    # Реальный cd-код (первый statement, корень репозитория) денает
    # независимо от того, что где-то дальше в команде лежит текст,
    # похожий на редирект внутри кавычек -c-аргумента -- `" 2>&1"` (с
    # ведущим пробелом) как ЛИТЕРАЛЬНАЯ подстрока здесь физически не
    # встречается (текст -- `'2>&1`, без пробела перед цифрой), поэтому
    # класс 2>&1 и без ambiguity-логики не сработал бы на этом конкретном
    # тексте -- регресс-контроль, что cd денает НЕЗАВИСИМО.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f'cd {hygiene_gate._REPO_ROOT_NAME} && python -c "print(\'2>&1 as data only\')"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX
    assert hygiene_gate.MSG_REDIRECT_STDERR not in hso["additionalContext"]


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, найдена
# полным прогоном, не входит в буквальную девятку -- см. отчёт
# builder'а t-605 доп.): фикстура -- РЕАЛЬНОЕ heredoc-тело собственного
# python-heredoc'а (certain=True), а его содержимое -- прозовое
# предложение, НЕ валидный Python (`ast.parse` падает) -- по новой
# классификации это класс O, текст -- MSG_PYTHON_DASH_C_OPAQUE, не
# старый MSG_PYTHON_DASH_C. Предмет пина (сообщение появляется РОВНО
# ОДИН раз, не дублируется) сохранён -- просто на актуальном тексте.
def test_v5_python_dash_c_message_appears_once_even_with_nested_mention(monkeypatch):
    # `_is_python_dash_c` -- булев флаг (не счётчик) -- сборка ответа
    # добавляет НОВЫЙ warn-текст класса (в) в контекст НЕ БОЛЕЕ одного
    # раза, независимо от того, сколько раз паттерн "python -c"
    # фактически встречается в сыром тексте команды (напр. один раз как
    # реальный опенер, ещё раз как упоминание внутри heredoc-тела).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        "python - <<EOF\n"
        "text mentions python -c \"nested as data\" here\n"
        "EOF"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    ctx = hso["additionalContext"]
    assert ctx.count(hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE) == 1


# --- ЧАСТЬ 2: блоки cd/Set-Location, 2>&1, gateway-исключение (B4) -----


def test_v5_cd_prefix_denies_with_replacement_text(monkeypatch):
    # ПЕРЕСДАЧА 3 (координатор, П3): денает ТОЛЬКО цель-корень репозитория
    # теперь -- "cd tools" (подкаталог) сам по себе НЕ денает больше, см.
    # test_v5_p3_cd_to_subdirectory_warns_not_denies ниже за контроль
    # ЭТОГО отдельно.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f"cd {hygiene_gate._REPO_ROOT_NAME} && python x.py"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX


def test_v5_redirect_stderr_denies_with_replacement_text(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload("python x.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


# ПЕРЕСДАЧА 3 (координатор/критик, П3, ИНВЕРСИЯ УСЛОВИЯ -- чинить КЛАСС,
# не экземпляр): исключение gateway УДАЛЕНО как отдельный случай --
# gateway теперь просто ОДИН ИЗ МНОГИХ non-root целей, попадающих в
# ОБЩИЙ WARN (MSG_CD_NON_ROOT_WARN), наравне с D:\AO3_tests/экзаменационными
# китами/toolkit/scratchpad (замер критика по истории). Тесты
# переименованы, чтобы имя отражало ТЕКУЩУЮ семантику (не "gateway
# exception" -- такого больше нет как отдельного механизма).


def test_v5_p3_gateway_falls_into_generic_non_root_warn_no_special_case(monkeypatch):
    # Координатор явно попросил проверить: литерал "gateway" после
    # инверсии условия НЕ нужен как отдельное исключение -- CONFIRMED,
    # эмпирически: "gateway" просто не совпадает с именем корня
    # репозитория, попадает в ОБЩУЮ WARN-ветку автоматически.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]
    assert not hasattr(hygiene_gate, "MSG_CD_GATEWAY_EXCEPTION")
    assert not hasattr(hygiene_gate, "_is_cd_to_gateway")


def test_v5_p3_non_root_cd_target_variants_all_warn_not_deny(monkeypatch):
    # Замер критика по истории (сиблинги того же класса, что gateway):
    # другое дерево (AO3_tests), экзаменационный кит, toolkit/, scratchpad
    # -- все НЕ являются корнем ЭТОГО репозитория, все остаются WARN.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    for command in [
        "cd gateway && ls",
        "Set-Location gateway; ls",
        "cd ./gateway && ls",
        'cd "gateway" && ls',
        "cd D:\\repo\\gateway && ls",
        "cd D:\\AO3_tests && ls",
        "cd D:\\Improving_AI\\exam_fullgates_kit && ls",
        "cd toolkit && ls",
        "cd scratchpad && ls",
    ]:
        exit_code, output = hygiene_gate.decide(_bash_payload(command))
        assert exit_code == 0
        hso = output["hookSpecificOutput"]
        assert "permissionDecision" not in hso, command
        assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"], command


def test_v5_p3_cd_to_subdirectory_of_repo_warns_not_denies(monkeypatch):
    # Контроль: cd В ПОДКАТАЛОГ этого же репозитория (не корень САМ) --
    # WARN, не блок; координатор явно назвал случаем "цель — корень",
    # не "любой путь внутри репозитория".
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload("cd tools && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_v5_p3_repo_root_target_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f"cd {hygiene_gate._REPO_ROOT_NAME} && python x.py"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX


def test_v5_p3_repo_root_target_case_insensitive_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f"cd {hygiene_gate._REPO_ROOT_NAME.upper()} && python x.py"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v5_p3_set_location_dash_path_flag_target_parsed_correctly(monkeypatch):
    # Координатор: "Set-Location -Path gateway — цель разбирается как
    # -Path" -- фикс _extract_cd_prefix_target должен пропускать флаг.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "Set-Location -Path gateway && ls"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_v5_p3_set_location_dash_path_flag_repo_root_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f"Set-Location -Path {hygiene_gate._REPO_ROOT_NAME} && ls"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_v5_p3_quoted_path_with_spaces_parsed_correctly_not_truncated(monkeypatch):
    # Координатор: "путь с пробелами в кавычках — цель обрезается по
    # первому пробелу" -- фикс должен читать ДО парной закрывающей кавычки.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'cd "some dir with spaces" && ls'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_v5_p3_extract_cd_prefix_target_unit_quoted_with_spaces():
    target = hygiene_gate._extract_cd_prefix_target('cd "some dir with spaces" && ls')
    assert target == '"some dir with spaces"'


def test_v5_p3_extract_cd_prefix_target_unit_dash_path_flag_skipped():
    target = hygiene_gate._extract_cd_prefix_target("Set-Location -Path gateway && ls")
    assert target == "gateway"


def test_v5_p3_extract_cd_prefix_target_unit_literal_path_flag_skipped():
    target = hygiene_gate._extract_cd_prefix_target("Set-Location -LiteralPath gateway && ls")
    assert target == "gateway"


def test_v5_p3_extract_cd_prefix_target_unit_bare_no_flag():
    target = hygiene_gate._extract_cd_prefix_target("cd gateway && ls")
    assert target == "gateway"


def test_v5_p3_extract_cd_prefix_target_unit_no_target_returns_none():
    assert hygiene_gate._extract_cd_prefix_target("cd") is None
    assert hygiene_gate._extract_cd_prefix_target("echo hi") is None


def test_v5_three_blocking_classes_all_listed_fixed_order(monkeypatch):
    # DoD: "три блокирующих класса разом -> перечислены все"; B5 --
    # фиксированный порядок журнал -> cd -> 2>&1. ПЕРЕСДАЧА 3 (П3): cd
    # должен реально ДЕНАТЬ здесь -- цель теперь корень репозитория, не
    # "tools" (подкаталог, который после П3 сам по себе только WARN).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        f"cd {hygiene_gate._REPO_ROOT_NAME} && echo x >> logs/routing-log.jsonl "
        "&& python y.py 2>&1"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_JOURNAL_BLOCK in ctx
    assert hygiene_gate.MSG_CD_PREFIX in ctx
    assert hygiene_gate.MSG_REDIRECT_STDERR in ctx
    assert (
        ctx.index(hygiene_gate.MSG_JOURNAL_BLOCK)
        < ctx.index(hygiene_gate.MSG_CD_PREFIX)
        < ctx.index(hygiene_gate.MSG_REDIRECT_STDERR)
    )


# =========================================================================
# ПЕРЕПРОЕКТИРОВКА (слово оператора) -- В1 (_is_ambiguous), В2 (2>&1
# требует определённости), В3 (newline закрывает cd-обход).
# =========================================================================


# --- Ф1/Ф2 (координатор, финальный фикс, заменяет В1/В2): список
# интерпретаторов `_is_ambiguous` удалён целиком -- класс 2>&1 решается
# через `_mask_quoted_segments` (кавычки), см. `_collect_redirect_signal`
# в hygiene_gate.py. Юнит-тесты на функцию -- на НОВУЮ точку входа.


def test_f2_collect_redirect_signal_unit_absent():
    assert hygiene_gate._collect_redirect_signal("git status") == {
        "present": False, "certain": False,
    }


def test_f2_collect_redirect_signal_unit_certain_deny():
    assert hygiene_gate._collect_redirect_signal("make 2>&1") == {
        "present": True, "certain": True,
    }


def test_f2_collect_redirect_signal_unit_ambiguous_heredoc_warn():
    command = "python - <<'PY'\nbody\nPY\nls 2>&1"
    signal = hygiene_gate._collect_redirect_signal(command)
    assert signal["present"] is True
    assert signal["certain"] is False


def test_f2_collect_redirect_signal_unit_quoted_2_greater_1_silent():
    command = "python -c \"print('ran 2>&1 here')\""
    assert hygiene_gate._collect_redirect_signal(command) == {
        "present": False, "certain": False,
    }


# --- Ф2: класс 2>&1 денает ТОЛЬКО при определённости (кавычки, не список) --


def test_f2_redirect_denies_when_no_quotes_no_heredoc(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload("python foo.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, найдена
# полным прогоном, не входит в буквальную девятку -- см. отчёт
# builder'а t-605 доп.): payload `print('ran 2>&1 here')` -- доказанно
# ЧИСТЫЙ (P) -- под новой классификацией класс (в) ТОЖЕ молчит (был
# "отдельный, независимый WARN" в прежнем дизайне, комментарий ниже
# оставлен как ИСТОРИЯ прежнего поведения). ОЖИДАНИЕ усилено до ПОЛНОЙ
# тишины -- фикстура не меняется (payload и так уже был чист, менять
# его на мутирующий стёр бы саму суть "2>&1 внутри кавычек не денит").
def test_f2_redirect_fully_silent_when_quoted(monkeypatch):
    # Координатор, проба определённости, дословно: `python -c "print('ran
    # 2>&1 here')"` -- ТИШИНА (не warn, не deny) -- " 2>&1" ЦЕЛИКОМ внутри
    # кавычек -c-аргумента, `_mask_quoted_segments` маскирует его прежде
    # проверки; класс 2>&1 НЕ срабатывает вовсе (класс (в) python -c/heredoc
    # -- раньше был ОТДЕЛЬНЫЙ, независимый WARN; теперь payload доказанно
    # чист (P) -- тоже молчит, итог ПОЛНАЯ тишина).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "python -c \"print('ran 2>&1 here')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, найдена
# полным прогоном, не входит в буквальную девятку -- см. отчёт
# builder'а t-605 доп.): ДВА certain-вызова -- payload "a" парсится,
# чист (P); payload "b 2>&1" -- НЕ валидный Python (`ast.parse` падает)
# -> O. Строжайший класс побеждает (F6/E7: M > O > P) -> итог O, текст
# -- MSG_PYTHON_DASH_C_OPAQUE, не старый MSG_PYTHON_DASH_C.
def test_f2_redirect_fully_silent_when_quoted_chain(monkeypatch):
    # Координатор, проба определённости, дословно: критик получал ложный
    # DENY на этой цепочке ДО фикса -- ОБА " 2>&1" здесь ВНУТРИ кавычек
    # (`"a"`/`"b 2>&1"`), маскируются, ТИШИНА по классу 2>&1 (класс (в)
    # остаётся -- python -c встречается дважды, но это ОДИН булев флаг).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'python -c "a" ; python -c "b 2>&1"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_REDIRECT_STDERR not in hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE in hso["additionalContext"]


def test_f2_redirect_warns_when_heredoc_present_unquoted(monkeypatch):
    # Координатор: `python - <<'PY' … PY … 2>&1` (редирект ВНЕ кавычек,
    # heredoc ЕСТЬ) -> WARN. Делимитер `'PY'` сам в кавычках (маскируется),
    # но токен `<<` СНАРУЖИ кавычек остаётся видимым.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "python - <<'PY'\nbody\nPY\nmake 2>&1"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_f2_redirect_denies_when_shift_operator_quoted_real_redirect_outside(monkeypatch):
    # Координатор: `python -c "print(1 << 3)" && ls 2>&1` -> DENY --
    # сдвиг `<<` ВНУТРИ кавычек -c-аргумента замаскирован, редирект ВНЕ
    # кавычек -- настоящий. Случай, где список интерпретаторов ошибался
    # (posчитал бы всю команду неоднозначной из-за самого факта "-c").
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'python -c "print(1 << 3)" && ls 2>&1'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


def test_f2_redirect_denies_plain_make(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload("make 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


def test_f2_redirect_warn_uses_verbatim_v4_text(monkeypatch):
    # "прежний V4-warn с прежним текстом" -- ТА ЖЕ константа, не новая.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "python - <<'PY'\nbody\nPY\nx 2>&1"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    # УЗЕЛ C (посадка 2026-08-25): текст переписан по правилу трёх; предмет
    # пина прежний — V4 и V5 делят ОДНУ константу.
    assert hygiene_gate.MSG_REDIRECT_STDERR == (
        "хвост \" 2>&1\" не проходит сверку по allowlist — лишний permission-промпт "
        "или отказ команды; убери \" 2>&1\" из команды (гигиена п.3)"
    )
    assert hygiene_gate.MSG_REDIRECT_STDERR in output["hookSpecificOutput"]["additionalContext"]


def test_f2_cmd_slash_c_quoted_redirect_fully_silent(monkeypatch):
    # Координатор, форма 1 из шести: `cmd /c "pi ... 2>&1"` -- тишина.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'cmd /c "pi some_pipeline 2>&1"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_f2_powershell_command_quoted_redirect_fully_silent(monkeypatch):
    # Координатор, форма 2 из шести: `powershell -Command "Set-Location
    # ...; pytest ... 2>&1 | ..."` -- тишина.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'powershell -Command "Set-Location tools; pytest . 2>&1 | tee out.txt"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_f2_gate_smoke_probe_json_line_fully_silent(monkeypatch):
    # Координатор, форма 3 из шести: смок-проба самого гейта -- команда
    # (echo | python tools/hygiene_gate.py), несущая JSON-строку с
    # "2>&1" ВНУТРИ значения "command" (двойные кавычки, экранированные
    # изнутри одинарными снаружи) -- тишина.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        "echo '{...\"command\":\"cd gateway && ls 2>&1\"}' "
        "| python tools/hygiene_gate.py"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# --- В3: newline закрывает cd-обход ---------------------------------


def test_v3_newline_separated_cd_root_denies(monkeypatch):
    # Координатор, проба закрытия newline-обхода, дословно:
    # `cd "<корень>"\ngit status` -- перевод строки, БЕЗ `&&` -- DENY.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f'cd "{hygiene_gate._REPO_ROOT_NAME}"\ngit status'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX


def test_v3_newline_separated_cd_non_root_warns_not_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "cd gateway\ngit status"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_NON_ROOT_WARN in hso["additionalContext"]


def test_v3_newline_bypass_unfixed_at_v4_regression(monkeypatch):
    # V4 (без исправления, И1 байт-в-байт): newline-обход по-прежнему НЕ
    # закрыт -- `_is_cd_prefix` (V4) не считает перевод строки
    # разделителем; этот пробел -- задокументированный, НЕ трогается
    # (закрыт ТОЛЬКО в V5).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)
    command = f'cd "{hygiene_gate._REPO_ROOT_NAME}"\ngit status'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v3_is_cd_prefix_v5_unit_newline_true():
    assert hygiene_gate._is_cd_prefix_v5("cd gateway\nls") is True


def test_v3_is_cd_prefix_v5_unit_bare_no_continuation_false():
    assert hygiene_gate._is_cd_prefix_v5("cd gateway") is False


def test_v3_is_cd_prefix_v5_unit_not_at_start_false():
    assert hygiene_gate._is_cd_prefix_v5("echo hi\ncd gateway") is False


# --- Ф3 (координатор, финальный фикс): trailing newline БЕЗ продолжения --
# ОДНА семантика с bare cd (не отдельная).


def test_f3_trailing_newline_no_continuation_is_none_not_deny(monkeypatch):
    # ДО фикса: `cd <корень>\n` (перевод строки в конце, НИЧЕГО после)
    # давал DENY -- "\n" in command истинно, хотя реального продолжения
    # нет. ПОСЛЕ фикса -- та же семантика, что bare `cd <корень>` (NONE).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f"cd {hygiene_gate._REPO_ROOT_NAME}\n"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_f3_trailing_newline_no_continuation_unit_false():
    assert hygiene_gate._is_cd_prefix_v5("cd gateway\n") is False


def test_f3_bare_cd_root_still_none_same_semantics(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = hygiene_gate._REPO_ROOT_NAME
    exit_code, output = hygiene_gate.decide(_bash_payload(f"cd {command}"))
    assert exit_code == 0
    assert output is None


def test_f3_trailing_double_ampersand_no_continuation_is_none():
    # То же для `&&` без реального продолжения (пробел/ничего после).
    assert hygiene_gate._is_cd_prefix_v5("cd gateway && ") is False


def test_f3_real_continuation_after_newline_still_true_regression():
    # Регресс: РЕАЛЬНОЕ продолжение после перевода строки по-прежнему
    # детектится (фикс не ослабляет истинный позитив В3).
    assert hygiene_gate._is_cd_prefix_v5("cd gateway\nls") is True


# --- B6: шесть отрицательных случаев (3 сценария x 2 состояния выключателя) ---


@pytest.mark.parametrize("v5", [False, True])
def test_b6_bare_cd_gateway_without_continuation_not_block_not_warn(monkeypatch, v5):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", v5)
    exit_code, output = hygiene_gate.decide(_bash_payload("cd gateway"))
    assert exit_code == 0
    assert output is None


@pytest.mark.parametrize("v5", [False, True])
def test_b6_cd_not_at_start_not_trigger(monkeypatch, v5):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", v5)
    exit_code, output = hygiene_gate.decide(_bash_payload("echo hi && cd gateway"))
    assert exit_code == 0
    assert output is None


@pytest.mark.parametrize("v5", [False, True])
def test_b6_redirect_inside_commit_message_not_trigger(monkeypatch, v5):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", v5)
    command = 'git commit -m "note about pytest 2>&1 output redirection"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# --- ЧАСТЬ 3 (write-намерение) УДАЛЕНА ЦЕЛИКОМ, ПЕРЕПРОЕКТИРОВКА (слово
# оператора): `_has_write_intent` и весь её набор регексов удалены вместе
# с кодом -- класс (в) (python -c/heredoc) ВСЕГДА warn теперь, как в V4
# (никогда не денает -- промоции, которую вносило write-намерение,
# больше нет). Журнальный класс (г) НЕ участвует в удалённой части (её
# признаки были СВОИ, независимые от _is_journal_bypass) -- продолжает
# ловить встроенные записи ЕСТЕСТВЕННО (см. ниже), т.к. никогда не
# зависел от маскировки/write-намерения вовсе.


# F5(A) (сужение предиката pyc, 2026-08-25): `print(1)` -> P -> тишина,
# ломало бы сам предмет пина -- фикстура на мутирующий payload.
def test_v5_python_c_always_warn_never_denies_class_v_removed(monkeypatch):
    # Класс (в) НИКОГДА не денает после удаления части 3 -- ровно V4-роль.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'python -c "open(\'x.txt\',\'w\').write(\'x\')"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_v5_python_c_with_open_write_mode_stays_warn_class_v_no_longer_denies(monkeypatch):
    # Регресс, задокументированный явно: ДО перепроектировки (пересдачи
    # 1-3) write-намерение промотировало `open(...,'w')` внутри -c в
    # DENY через класс (в); ПОСЛЕ удаления части 3 -- ТОЛЬКО WARN (класс
    # в никогда не денает). Реальная запись в ЖУРНАЛ по-прежнему ловится
    # -- НО через класс (г), см. тесты "denies_via_journal_class" ниже
    # (target+форма записи -- открытый текст в СЫРОЙ команде, journal
    # class никогда не зависел от write-намерения).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "python -c \"open('f.txt','w').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


# --- журнальный класс (г) ловит встроенные записи ЕСТЕСТВЕННО (никогда
# не зависел от масковки/write-намерения -- _is_journal_bypass всегда
# читала СЫРУЮ команду) -- регресс-набор, бывший "П2" прошлой пересдачи,
# теперь просто прямое следствие того, что часть 1 удалена.


def test_v5_os_system_inside_dashc_body_denies_via_journal_class(monkeypatch):
    # `os.system("echo x >> logs/routing-log.jsonl")` внутри heredoc-тела
    # -- target+форма записи лежат в ОТКРЫТОМ тексте СЫРОЙ команды,
    # _is_journal_bypass видит их напрямую (нет масковки, которая могла
    # бы их спрятать) -- ЕСТЕСТВЕННО денает через класс (г), без
    # специального механизма.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        "python - <<PY\n"
        "import os\n"
        'os.system("echo x >> logs/routing-log.jsonl")\n'
        "PY"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v5_subprocess_shell_true_inside_dashc_body_denies_via_journal_class(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = (
        'python -c "import subprocess; '
        "subprocess.run('echo x >> logs/routing-log.jsonl', shell=True)\""
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v5_open_write_mode_inside_dashc_denies_via_journal_class(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "python -c \"open('logs/routing-log.jsonl','a').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


def test_v5_os_system_without_journal_target_no_false_flood(monkeypatch):
    # Контроль: os.system/subprocess САМИ ПО СЕБЕ НЕ признаки (координатор
    # явно запретил их добавлять как таковые -- шквал) -- БЕЗ журнальной
    # цели+формы в аргументе класс (г) НЕ денает.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'python -c "import os; os.system(\'ls -la\')"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso


def test_v5_subprocess_diagnostic_without_journal_target_no_false_flood(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'python -c "import subprocess; subprocess.run([\'pytest\', \'tools/\'])"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso


# --- ВЫКЛЮЧАТЕЛЬ: V5_ENABLED=False -> ни блоков, ни маскировки -----------


def test_v5_disabled_no_new_blocks_stays_warn(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)
    exit_code, output = hygiene_gate.decide(_bash_payload("cd tools && python x.py 2>&1"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_CD_PREFIX in hso["additionalContext"]
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_v5_disabled_no_masking_journal_write_inside_dashc_still_journal_class(monkeypatch):
    # V5_ENABLED=False -> нет масковки части 1 -- журнальная запись внутри
    # -c payload'а ОСТАЁТСЯ видна классу (г), как в V4 (единственный БЛОК
    # V4-мира).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)
    command = "python -c \"open('logs/routing-log.jsonl','a').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


# --- Fail-open с видимым маркером (F1/F2), обе ветки ---------------------


def test_v5_fail_open_on_helper_exception(monkeypatch):
    # ФИНАЛЬНЫЙ ФИКС: `_is_ambiguous` удалена вместе со списком
    # интерпретаторов -- подменяем `_collect_redirect_signal` (Ф2, новая
    # точка входа классификации класса 2>&1, вызывается на каждом
    # вызове `_collect_v5_signals`) вместо неё.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)

    def _boom(_command):
        raise RuntimeError("boom")

    monkeypatch.setattr(hygiene_gate, "_collect_redirect_signal", _boom)
    exit_code, output = hygiene_gate.decide(_bash_payload("cd tools && python x.py"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert "hygiene_gate: внутренняя ошибка классификатора" in hso["additionalContext"]
    assert "RuntimeError" in hso["additionalContext"]
    assert "гигиена НЕ проверена" in hso["additionalContext"]


def test_v4_fail_open_on_helper_exception_too(monkeypatch):
    # F1 -- ОБЩИЙ для обеих веток (V4 и V5), не только новой.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)

    def _boom(_command):
        raise ValueError("kaboom")

    monkeypatch.setattr(hygiene_gate, "_is_journal_bypass", _boom)
    exit_code, output = hygiene_gate.decide(_bash_payload("echo x >> logs/routing-log.jsonl"))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert "ValueError" in hso["additionalContext"]
    assert "гигиена НЕ проверена" in hso["additionalContext"]


# =========================================================================
# ПЕРЕСДАЧА 2 (координатор, БЛОКЕР 1 + БЛОКЕР 2) -- дополнение к тому же
# диспатчу t-372. Оба фикса ЗА выключателем V5_ENABLED, см. докстринги
# _decide_v5 (БЛОКЕР 1) и _has_write_form (БЛОКЕР 2) в hygiene_gate.py.
# =========================================================================


# --- БЛОКЕР 1: heredoc-форма commit-сообщения для класса (б) -----------


def test_v5_git_commit_heredoc_2_greater_1_now_warns_uniform_heredoc_rule(monkeypatch):
    # ИСТОРИЯ (пересдачи 2-4, БЛОКЕР 1): heredoc-тело commit-сообщения
    # вырезалось СПЕЦИАЛЬНЫМ, git-специфичным механизмом
    # (`_strip_commit_messages`) ПЕРЕД проверкой класса (б), давая
    # ПОЛНУЮ ТИШИНУ здесь. ФИНАЛЬНЫЙ ФИКС (Ф2, координатор, третий
    # критик-вход): класс (б) больше НЕ зовёт `_strip_commit_messages`
    # вовсе -- git-commit-heredoc теперь трактуется ЕДИНООБРАЗНО с ЛЮБЫМ
    # heredoc (`_collect_redirect_signal` не различает "git commit" от
    # прочих форм) -- "<<" виден на маскированном (кавычки скрыты, но
    # heredoc-опенер САМ вне кавычек) тексте, " 2>&1" тоже виден (тело
    # heredoc -- НЕ кавычки) -> WARN, НЕ тишина. ИЗМЕНЕНИЕ ПОВЕДЕНИЯ
    # ОТНОСИТЕЛЬНО пересдач 2-4, ЗАДОКУМЕНТИРОВАНО явно (не молчаливый
    # регресс) -- задокументированный компромисс упрощения: единое
    # правило "heredoc -> неоднозначность" ценой git-специфичной
    # точности для ЭТОЙ узкой формы.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "git commit -F - <<EOF\nsome text with 2>&1 inside\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_REDIRECT_STDERR in hso["additionalContext"]


def test_v5_blocker1_real_redirect_outside_commit_message_still_denies(monkeypatch):
    # Контроль: РЕАЛЬНЫЙ 2>&1 (не внутри commit-сообщения) по-прежнему
    # денаит. МЕХАНИЗМ (пересдача 5, Ф2): не через вырезание -m-текста
    # (которое здесь уже не участвует), а через квотирование -- "clean
    # message" в кавычках маскируется, реальный " 2>&1" вне кавычек цел.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'git commit -m "clean message" && python x.py 2>&1'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR


def test_v5_blocker1_cd_inside_commit_heredoc_body_never_triggers_class_a(monkeypatch):
    # Координатор явно попросил проверить, нужен ли тот же вырез классу
    # (а) -- эмпирически НЕ нужен: `_is_cd_prefix` анкерена к
    # АБСОЛЮТНОМУ НАЧАЛУ всей команды (`.match()`, не `.search()`);
    # текст heredoc-тела git-commit-сообщения физически не может стоять
    # на позиции 0 всей команды (перед ним всегда идёт
    # "git commit -F - <<DELIM\n" или аналог).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "git commit -F - <<EOF\ncd x && y\nEOF"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v5_blocker1_dash_m_message_2_greater_1_still_fully_silent_regression(monkeypatch):
    # Регресс: -m/--message форма продолжает не триггерить. МЕХАНИЗМ
    # (пересдача 5, Ф2): значение -m ВСЕГДА в кавычках -- квотирование
    # (`_mask_quoted_segments`) маскирует его целиком, отдельный
    # git-специфичный механизм для ЭТОЙ формы больше не нужен.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = 'git commit -m "note about pytest 2>&1 output redirection"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


# --- БЛОКЕР 2: PowerShell-формы записи класса (г), за выключателем -----


@pytest.mark.parametrize(
    "cmdlet,args",
    [
        ("Add-Content", "-Path logs/routing-log.jsonl -Value x"),
        ("Set-Content", "-Path logs/routing-log.jsonl -Value x"),
        ("Out-File", "-FilePath logs/routing-log.jsonl"),
    ],
)
def test_v5_blocker2_ps_write_cmdlet_with_journal_target_denies(monkeypatch, cmdlet, args):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = f"{cmdlet} {args}"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK


@pytest.mark.parametrize(
    "cmdlet,args",
    [
        ("Add-Content", "-Path logs/routing-log.jsonl -Value x"),
        ("Set-Content", "-Path logs/routing-log.jsonl -Value x"),
        ("Out-File", "-FilePath logs/routing-log.jsonl"),
    ],
)
def test_v5_blocker2_ps_write_cmdlet_gated_off_at_v5_disabled(monkeypatch, cmdlet, args):
    # M8-инвариант для класса (г): при V5_ENABLED=False НЕ денаит по
    # НОВОЙ PowerShell-форме -- класс (г) уже живой в V4, но его
    # bash-детектор этих командлетов не знает вовсе (сегодняшнее
    # поведение байт-в-байт).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)
    command = f"{cmdlet} {args}"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


@pytest.mark.parametrize("v5", [False, True])
@pytest.mark.parametrize(
    "cmdlet,args",
    [
        ("Add-Content", "-Path notes.txt -Value x"),
        ("Set-Content", "-Path notes.txt -Value x"),
        ("Out-File", "-FilePath notes.txt"),
    ],
)
def test_v5_blocker2_ps_write_cmdlet_non_journal_target_never_blocks(monkeypatch, v5, cmdlet, args):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", v5)
    command = f"{cmdlet} {args}"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v5_blocker2_statement_scope_preserved_target_and_ps_form_in_different_statements(monkeypatch):
    # Стейтмент-скоуп (тот же принцип, что уже несёт _is_journal_bypass
    # для bash-форм): журнальная ЦЕЛЬ в одном statement, PS-форма записи
    # в ДРУГОМ statement, пишущая в НЕжурнальный файл -- не блок.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    command = "cat logs/routing-log.jsonl; Add-Content -Path notes.txt -Value x"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_v5_blocker2_tee_object_already_covered_by_existing_tee_re_both_states(monkeypatch):
    # Эмпирическая находка ПЕРЕД реализацией (scratchpad/check_tee_re.py,
    # см. отчёт): "Tee-Object" УЖЕ матчится существующим TEE_RE (`\btee\b`)
    # БЕЗ выключателя -- уже в V4, случайно (подстрока "Tee" + `\b` на
    # дефисе). Поэтому НЕ добавлен в _PS_WRITE_CMDLET_RE (не дублировать
    # детектор, D-0043) -- поведение ОДИНАКОВО в обоих состояниях.
    for v5 in (False, True):
        monkeypatch.setattr(hygiene_gate, "V5_ENABLED", v5)
        command = "Tee-Object -FilePath logs/routing-log.jsonl"
        exit_code, output = hygiene_gate.decide(_bash_payload(command))
        assert exit_code == 0, v5
        hso = output["hookSpecificOutput"]
        assert hso["permissionDecision"] == "deny", v5
        assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK, v5


# =========================================================================
# v6 (F.3, ремедиация калибровки №8, узел F.3, 2026-08-20) -- класс
# `python -c`/heredoc: WARN -> БЛОК, за выключателем PYC_DENY_ENABLED
# (D-0069, default False -- билдер НЕ переключает). Все тесты этого
# раздела monkeypatch'ат И V5_ENABLED, И PYC_DENY_ENABLED явно.
# =========================================================================


def test_p6_pyc_deny_enabled_default_is_false():
    # К3.2: значение НА СДАЧЕ -- билдер не переключает.
    assert hygiene_gate.PYC_DENY_ENABLED is False


def test_p6_existing_suite_byte_identical_with_switch_off():
    # К3.2 witness (дополнительно к полному прогону файла): значение
    # выключателя на диске -- False, что и проверяет ВЕСЬ остальной
    # существующий набор данного файла без правки тел (сам этот факт --
    # весь файл зелёный с дефолтным значением константы).
    assert hygiene_gate.PYC_DENY_ENABLED is False
    assert hygiene_gate.V5_ENABLED is True


def test_p6_dash_c_deny_basic(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1)"'))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_PYTHON_DASH_C_BLOCK
    assert hygiene_gate.MSG_PYTHON_DASH_C_BLOCK in hso["additionalContext"]


def test_p6_heredoc_opener_deny(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "python - <<'PY'\nprint(1)\nPY"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_PYTHON_DASH_C_BLOCK


# F5(A)-родственная правка (сужение предиката pyc, 2026-08-25, явно
# названа координатором в развилке t-605: "switch-off тест пинит
# «warn-не-deny» -- ему мутирующая фикстура"): `print(1)` -> P -> pyc-
# warn исчез бы, ломая проверку "остаётся WARN, не deny".
def test_p6_switch_off_stays_warn_even_under_v5(monkeypatch):
    # К3.2 регресс: V5 включён, выключатель НЕТ -- прежнее поведение
    # (WARN, MSG_PYTHON_DASH_C, без permissionDecision).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", False)
    command = 'python -c "open(\'x.txt\',\'w\').write(\'x\')"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_p6_v4_path_unaffected_by_switch(monkeypatch):
    # V5_ENABLED=False (V4 путь) -- _decide_v4 вообще не читает
    # PYC_DENY_ENABLED -- класс (в) остаётся WARN независимо.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1)"'))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


# --- Р17: неоднозначные формы остаются WARN с прежним текстом ----------


def test_p6_mention_inside_git_commit_message_stays_warn(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'git commit -m "run python -c to test this"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_p6_mention_inside_unrelated_heredoc_body_stays_warn(monkeypatch):
    # Живой корпусный FP (K3.3, 2026-08-20): "python -c" КАК ПРОЗА внутри
    # тела heredoc'а НЕ-python команды (напр. `cat <<EOF`) -- реальный
    # ВЫЗОВ здесь -- `cat`, не python. См. _mask_heredoc_bodies.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'cat <<EOF\nrun python -c "x" here\nEOF'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_p6_mention_inside_git_commit_heredoc_body_stays_warn_not_deny(monkeypatch):
    # ДОСЛОВНЫЙ живой репро координатора (K3.3): git commit -F -
    # <<'EOF' с телом сообщения, упоминающим "класс python -c/heredoc" --
    # РЕАЛЬНЫЙ, легальный git commit; до фикса _mask_heredoc_bodies
    # денался (см. отчёт).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = (
        "git add docs/x.md && git commit -F - <<'EOF'\n"
        "класс python -c/heredoc переводится в deny по слову оператора\n"
        "EOF"
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_p6_real_python_heredoc_own_body_mentioning_dash_c_still_denies(monkeypatch):
    # Контроль: РЕАЛЬНЫЙ python-heredoc-опенер, чьё СОБСТВЕННОЕ тело
    # упоминает "python -c" как данные (тестовый код) -- маска тела НЕ
    # трогает опенер-строку, денается по ОПЕНЕРУ.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "python - <<'PY'\ncmd = 'python -c \"print(1)\"'\nPY"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_PYTHON_DASH_C_BLOCK


# --- К3.5: адверсариальная мини-батарея ---------------------------------


def test_p6_adversarial_mypython_dash_c_boundary_not_covered(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('mypython -c "print(1)"'))
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_python3_dash_c_not_covered_known_limitation(monkeypatch):
    # Р16 (закрыто): токен-набор НЕ расширяется -- "python3"/"py"/
    # "pwsh -Command"/"node -e" остаются вне класса целиком.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('python3 -c "print(1)"'))
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_py_dash_c_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('py -c "print(1)"'))
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_pwsh_command_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('pwsh -Command "1+1"'))
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_absolute_path_python_still_denies(monkeypatch):
    # "/usr/bin/python -c" -- литерал "python" виден через \b на "/" ->
    # реальный, определённый вызов -- денает (НЕ про Р16 -- тот же
    # токен "python", просто с путём перед ним).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('/usr/bin/python -c "print(1)"'))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_case_insensitive_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('PYTHON -C "print(1)"'))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_double_space_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('python  -c "print(1)"'))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_crlf_heredoc_still_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "python - <<'PY'\r\nprint(1)\r\nPY"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_unclosed_quote_fail_safe_toward_detect_denies(monkeypatch):
    # Незакрытая кавычка НЕ матчится _mask_quoted_segments -- остаётся
    # как есть -- "python -c" (ПЕРЕД кавычкой) остаётся видимым --
    # fail-safe В СТОРОНУ детекта (тот же принцип, что везде в файле).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'python -c "print(unterminated'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_heredoc_continuation_after_delimiter_still_denies(monkeypatch):
    # `python - <<'PY'` с продолжением ПОСЛЕ разделителя на опенер-строке.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "python - <<'PY' # trailing comment\nprint(1)\nPY"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_emoji_non_ascii_payload_still_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "python -c \"print('\U0001F600 βήτα')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_bare_python_dash_c_no_payload_denies(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload("python -c"))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_p6_adversarial_empty_command_silent(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload(""))
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_missing_tool_input_silent(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide({"tool_name": "Bash"})
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_non_dict_payload_silent(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(["not", "a", "dict"])
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_non_bash_tool_silent(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    payload = {"tool_name": "Edit", "tool_input": {"command": 'python -c "print(1)"'}}
    exit_code, output = hygiene_gate.decide(payload)
    assert exit_code == 0
    assert output is None


def test_p6_adversarial_corrupted_stdin_bytes_subprocess_no_crash():
    # Битые байты stdin -- субпроцесс-уровень, читает ДИСКОВЫЙ дефолт
    # (PYC_DENY_ENABLED=False, monkeypatch не долетает до subprocess) --
    # переиспользует существующую адверсариальную инфраструктуру
    # (test_adversarial_malformed_json/test_adversarial_null_bytes_in_
    # json_string_no_crash выше), НЕ дублирует: тот же класс входа, тот
    # же гарантированный exit 0 без трейсбека для класса (в) в частности.
    result = _run_hook(b"\xff\xfe not json \x00")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# --- позиционный инвариант (К3, "ПОРЯДОК НЕСКОЛЬКИХ БЛОКОВ") ------------


def test_p6_positional_journal_deny_reason_unchanged_by_pyc_addition(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'echo x >> logs/routing-log.jsonl; python -c "print(1)"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    assert hygiene_gate.MSG_PYTHON_DASH_C_BLOCK in hso["additionalContext"]


def test_p6_positional_cd_root_deny_reason_unchanged_by_pyc_addition(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = f'cd {hygiene_gate._REPO_ROOT_NAME} && python -c "print(1)"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_CD_PREFIX
    assert hygiene_gate.MSG_PYTHON_DASH_C_BLOCK in hso["additionalContext"]


def test_p6_positional_redirect_certain_deny_reason_unchanged_by_pyc_addition(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'ls x.py 2>&1; python -c "print(1)"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_REDIRECT_STDERR
    assert hygiene_gate.MSG_PYTHON_DASH_C_BLOCK in hso["additionalContext"]


# --- К3, "Лимиты -- тест НА границе и ЗА ней" ---------------------------


def test_p6_limit_100kb_command_on_boundary(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    payload_body = "a" * 100_000
    command = f'python -c "print(\'{payload_body}\')"'
    t0 = time.perf_counter()
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    elapsed = time.perf_counter() - t0
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert elapsed < 2.0, f"decide() took {elapsed:.3f}s at 100KB -- linearity claim violated"


def test_p6_limit_1mb_command_beyond_boundary(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    payload_body = "a" * 1_000_000
    command = f'python -c "print(\'{payload_body}\')"'
    t0 = time.perf_counter()
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    elapsed = time.perf_counter() - t0
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    # ~10x рост длины входа -- утверждение линейности в докстринге
    # проверяется тем, что время растёт НЕ катастрофически (не более
    # чем на порядок величины сверх 100КБ-замера, щедрый потолок).
    assert elapsed < 5.0, f"decide() took {elapsed:.3f}s at 1MB -- linearity claim violated"


def test_p6_limit_500_statements_on_boundary(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "; ".join(["echo hi"] * 500) + '; python -c "print(1)"'
    t0 = time.perf_counter()
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    elapsed = time.perf_counter() - t0
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert elapsed < 2.0, f"decide() took {elapsed:.3f}s at 500 statements"


def test_p6_limit_5000_statements_beyond_boundary(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "; ".join(["echo hi"] * 5000) + '; python -c "print(1)"'
    t0 = time.perf_counter()
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    elapsed = time.perf_counter() - t0
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert elapsed < 5.0, f"decide() took {elapsed:.3f}s at 5000 statements"


def test_p6_limit_100_nested_quote_pairs_beyond_boundary(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    quotes = "".join(f'"{i}"' for i in range(100))
    command = f'python -c "print(1)" {quotes}'
    t0 = time.perf_counter()
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    elapsed = time.perf_counter() - t0
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert elapsed < 2.0, f"decide() took {elapsed:.3f}s at 100 quote pairs"


# --- ПЕРЕСДАЧА, п.5: "ОБЁРТОЧНАЯ ДЫРА" -- запинена как ИЗВЕСТНОЕ
# ОГРАНИЧЕНИЕ (очередь, решение оператора зафиксировано в докстринге
# `_mask_heredoc_bodies` выше -- НЕ чинится этой задачей: блок и без
# того нодж, Р16 уже оставил вне охвата python3/py/pwsh -c, закрывать
# ОДНУ из четырёх дыр интерпретаторным гардом непропорционально дорого
# относительно выгоды, Rule #1; вопрос "нодж или enforcement" возвращён
# оператору целиком вместе с Р16). Каждый тест пинует ОБА факта разом:
# (1) реальный, ИСПОЛНЯЮЩИЙ вызов НЕ денается (дыра реальна -- DENY
# отсутствует), (2) широкий сигнал `pyc` всё равно даёт WARN, НЕ тишину
# -- смягчение "деградация до warn, а не слепота" (см. её докстринг).


def _assert_wrapper_hole_warn_not_deny(command):
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None, "обёрточная дыра: ожидается WARN, не тишина"
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso, "обёрточная дыра: НЕ должна денать"
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


def test_p6_wrapper_bash_heredoc_python_dash_c_not_covered_known_limitation(monkeypatch):
    # Замер критика: `bash <<EOF ... python -c "..." ... EOF` реально
    # ИСПОЛНЯЕТ тело -- `_mask_heredoc_bodies` маскирует его наравне с
    # прозой, deny не срабатывает.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "bash <<'EOF'\necho start\npython -c \"print(1)\"\necho end\nEOF"
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_sh_heredoc_python_dash_c_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "sh <<EOF\npython -c \"print(1)\"\nEOF"
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_cat_pipe_bash_heredoc_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "cat <<'EOF' | bash\npython -c \"print(1)\"\nEOF"
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_ssh_heredoc_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "ssh host <<'EOF'\npython -c \"print(1)\"\nEOF"
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_docker_exec_heredoc_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "docker exec -i c bash <<'EOF'\npython -c \"print(1)\"\nEOF"
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_bash_dash_c_quoted_not_covered_known_limitation(monkeypatch):
    # Кавычковая маска (не heredoc): "python -c" стоит ВНУТРИ кавычек
    # аргумента `bash -c` -- `_mask_quoted_segments` маскирует его как
    # данные, хотя `bash -c` реально исполняет содержимое.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'bash -c \'python -c "print(1)"\''
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_sh_dash_c_quoted_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = "sh -c 'python -c \"print(1)\"'"
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_eval_quoted_not_covered_known_limitation(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'eval "python -c \'print(1)\'"'
    _assert_wrapper_hole_warn_not_deny(command)


def test_p6_wrapper_control_real_dash_c_still_denies(monkeypatch):
    # Контроль: НЕобёрнутый прямой вызов по-прежнему денается -- дыра
    # именно в обёртках, не общая деградация класса.
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1)"'))
    assert exit_code == 0
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


# =========================================================================
# СУЖЕНИЕ ПРЕДИКАТА pyc (2026-08-25, К3.6) -- новая трёхклассовая (плюс
# "U") семантика СОДЕРЖИМОГО certain-payload'а. См.
# docs/tasks/2026-08-25_pyc-narrow-spec.md + её "ПОПРАВКУ LEAD 16:35".
# Имена (закрыто дизайнером): ключ `pyc_payload`, функция
# `_classify_pyc_payload`, константа `MSG_PYTHON_DASH_C_OPAQUE`.
# =========================================================================


def _payload_class(command: str) -> str:
    return hygiene_gate._classify_pyc_payload(command)


# --- A1-A6: акцептанс -----------------------------------------------------


def test_pycnarrow_a1_pure_arithmetic_expression_silent():
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1+1)"'))
    assert exit_code == 0
    assert output is None


def test_pycnarrow_a1_pure_json_read_silent():
    command = 'python -c "import json; print(json.load(open(\'x.json\')))"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is None


def test_pycnarrow_a2_mutation_warns_old_text():
    command = "python -c \"open('x.txt','w').write('x')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE not in hso["additionalContext"]


def test_pycnarrow_a3_opaque_subprocess_warns_new_text_only():
    command = 'python -c "import subprocess; subprocess.run([\'ls\'])"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE in ctx
    # M-текст -- НЕ подстрока OPAQUE-текста, замена, не добавка (F6).
    assert hygiene_gate.MSG_PYTHON_DASH_C not in ctx


# A4: "новый тест асимметрии" -- чистый payload при PYC_DENY_ENABLED=True
# всё равно денает (I2: deny-путь не читает pyc_payload вовсе -- deny
# зависит ТОЛЬКО от pyc_certain, F4(A) принята явно).
def test_pycnarrow_a4_asymmetry_pure_payload_still_denies_when_switch_on(monkeypatch):
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", True)
    monkeypatch.setattr(hygiene_gate, "PYC_DENY_ENABLED", True)
    command = 'python -c "print(1+1)"'
    assert _payload_class(command) == "P"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_PYTHON_DASH_C_BLOCK


def test_pycnarrow_a6_v4_path_unaffected_by_new_classification(monkeypatch):
    # V5_ENABLED=False -- И4 (V4 путь байт-в-байт): чистый payload
    # по-прежнему безусловно warn старым текстом, payload_class
    # игнорируется целиком (_decide_v4 его не читает).
    monkeypatch.setattr(hygiene_gate, "V5_ENABLED", False)
    command = 'python -c "print(1+1)"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


# --- E1/E11/B8: пусто/неизвлечённый payload -> O ---------------------------


def test_pycnarrow_e1_bare_dash_c_no_argument_opaque():
    assert _payload_class("python -c") == "O"


def test_pycnarrow_e1_empty_quoted_argument_opaque():
    assert _payload_class('python -c ""') == "O"


def test_pycnarrow_e1_empty_heredoc_opaque():
    assert _payload_class("python - <<EOF\nEOF") == "O"


def test_pycnarrow_b8_heredoc_without_closer_opaque():
    # Героdoc без закрывателя -- extraction не находит ни одного
    # payload'а (regex требует закрывающую строку-делимитер).
    command = "python - <<EOF\nprint(1)\n"
    assert hygiene_gate._is_python_dash_c_certain(command) is True
    assert _payload_class(command) == "O"


# --- E3/E6/B10: строковый литерал/комментарий -- не код -> P --------------


def test_pycnarrow_e3_w_inside_string_literal_pure():
    assert _payload_class("python -c \"x = 'w'\"") == "P"


def test_pycnarrow_e6_comment_only_pure():
    assert _payload_class('python -c "# just a comment"') == "P"


def test_pycnarrow_b10_mutation_mentioned_in_string_literal_pure():
    # "open(f,'w')" -- ТЕКСТ (аргумент print), не РЕАЛЬНЫЙ вызов open().
    command = "python -c \"print('mentions open(f, mode w) as text')\""
    assert _payload_class(command) == "P"


# --- E5: регистрозависимость (легально, NameError в Python) ---------------


def test_pycnarrow_e5_uppercase_open_not_recognized_pure():
    assert _payload_class("python -c \"OPEN('x','w')\"") == "P"


def test_pycnarrow_e5_pyc_key_survives_uppercase_python_dash_c():
    # Ключ `pyc` (широкий, I1) -- регистронезависим, НЕ тронут этой
    # задачей; классификация СОДЕРЖИМОГО -- отдельный, регистрозависимый
    # вопрос (см. тест выше).
    signals = hygiene_gate._collect_v5_signals('PYTHON -C "OPEN(\'x\',\'w\')"')
    assert signals["pyc"] is True


# --- E7/B9/B11: несколько вызовов/вкладов -- строжайший класс -------------


def test_pycnarrow_e7_two_calls_different_classes_strictest_wins():
    command = 'python -c "print(1)" ; python -c "open(\'x\',\'w\')"'
    assert _payload_class(command) == "M"


def test_pycnarrow_b9_two_mutating_calls_one_warn_line():
    command = "python -c \"open('a','w').write('x'); open('b','w').write('y')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert ctx.count(hygiene_gate.MSG_PYTHON_DASH_C) == 1


def test_pycnarrow_b11_dunder_import_os_remove_opaque():
    # __import__('os').remove -- база `.remove` это ВЫЗОВ, не Name --
    # dotted-имя не строится, `.remove` НЕ засчитывается как os.remove;
    # вклад O даёт ТОЛЬКО сам __import__(...).
    assert _payload_class("python -c \"__import__('os').remove('f')\"") == "O"


def test_pycnarrow_b11_mutation_plus_opaque_together_mutation_wins():
    command = "python -c \"import subprocess; open('x','w').write('y')\""
    assert _payload_class(command) == "M"


# --- E8: open() -- полная матрица режимов ----------------------------------


def test_pycnarrow_e8_open_no_mode_pure():
    assert _payload_class("python -c \"open('x').read()\"") == "P"


def test_pycnarrow_e8_open_r_mode_pure():
    assert _payload_class("python -c \"open('x','r').read()\"") == "P"


def test_pycnarrow_e8_open_w_mode_mutation():
    assert _payload_class("python -c \"open('x','w')\"") == "M"


def test_pycnarrow_e8_open_a_mode_mutation():
    assert _payload_class("python -c \"open('x','a')\"") == "M"


def test_pycnarrow_e8_open_x_mode_mutation():
    assert _payload_class("python -c \"open('x','x')\"") == "M"


def test_pycnarrow_e8_open_rplus_mode_mutation():
    assert _payload_class("python -c \"open('x','r+')\"") == "M"


def test_pycnarrow_e8_open_mode_variable_opaque():
    assert _payload_class("python -c \"m='w'; open('x', m)\"") == "O"


def test_pycnarrow_e8_open_kwargs_unpack_opaque():
    assert _payload_class("python -c \"d={'mode':'w'}; open('x', **d)\"") == "O"


def test_pycnarrow_e8_open_mode_kwarg_w_mutation():
    assert _payload_class("python -c \"open('x', mode='w')\"") == "M"


# --- E9/B7: не-Python / незакрытая кавычка -- сбой парсера -> O -----------


def test_pycnarrow_e9_non_python_content_opaque():
    assert _payload_class('python -c "this is not { python : code"') == "O"


def test_pycnarrow_b7_unclosed_quote_opaque():
    assert _payload_class('python -c "print(\'unclosed') == "O"


# --- E10/B1/B2: лимит L1 -- ГРАНИЦА и ЗА ней (правило 6а) ------------------


def test_pycnarrow_b1_payload_exactly_l1_parses():
    body = "x = 1" + " " * (hygiene_gate.PYC_PAYLOAD_LIMIT - len("x = 1"))
    assert len(body) == hygiene_gate.PYC_PAYLOAD_LIMIT
    command = f'python -c "{body}"'
    assert _payload_class(command) == "P"


def test_pycnarrow_b2_payload_l1_plus_one_opaque_no_parse():
    body = "x" * (hygiene_gate.PYC_PAYLOAD_LIMIT + 1)
    command = f'python -c "{body}"'
    assert _payload_class(command) == "O"


# --- B4/B5: глубина вложенности -- ГРАНИЦА и ЗА ней ------------------------


def test_pycnarrow_b4_nesting_depth_50_pure():
    payload = "(" * 50 + "1" + ")" * 50
    assert _payload_class(f'python -c "{payload}"') == "P"


def test_pycnarrow_b5_nesting_depth_5000_no_traceback_opaque():
    payload = "(" * 5000 + "1" + ")" * 5000
    # "без трейсбека" -- сам вызов не должен поднять исключение наружу.
    result = _payload_class(f'python -c "{payload}"')
    assert result == "O"


# --- B3: 1МБ команда -- exit 0, время приложено числом --------------------


def test_pycnarrow_b3_1mb_command_exit0():
    command = 'python -c "print(\'' + ("a" * 1_000_000) + "')\""
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    # Payload (без учёта кавычек) > PYC_PAYLOAD_LIMIT -> O, без парсинга.
    assert output["hookSpecificOutput"]["additionalContext"].count(
        hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE
    ) == 1


# A8: замер времени 100КБ/1МБ -- ЧИСЛОМ, порогом НЕ гейтится (щедрый
# потолок ниже -- регресс-предохранитель на катастрофический скачок,
# не строгий perf-гейт; фактическое число -- в witness отчёта builder'а).
#
# ПОПРАВКА LEAD 17:2x, Ф3 (ОГОВОРКА, честно, не молчанием): число этого
# теста относится к ДОБРОКАЧЕСТВЕННОЙ форме -- ОДИН настоящий payload
# на 100КБ/1МБ. Критик-гейт зафиксировал ОТДЕЛЬНУЮ, ПРЕДСУЩЕСТВУЮЩУЮ
# квадратичность извлечения на АДВЕРСАРИАЛЬНОЙ форме "повторённые
# опенеры БЕЗ закрывателя" (много `python -c`/heredoc-подобных токенов
# подряд, каждый без своего аргумента/закрывающей строки) -- НЕ чинится
# этим раундом (Ф3 явно: "квадратичность НЕ чинить"); носитель очереди
# -- docs/tasks/2026-08-25_queue8-closure.md (не в owns этой задачи,
# billerd не пишет туда сам -- пункт для Lead/координатора).
def test_pycnarrow_perf_100kb_1mb_number_not_gated():
    cmd_100kb = 'python -c "print(\'' + ("a" * 100_000) + "')\""
    t0 = time.perf_counter()
    hygiene_gate.decide(_bash_payload(cmd_100kb))
    elapsed_100kb = time.perf_counter() - t0

    cmd_1mb = 'python -c "print(\'' + ("a" * 1_000_000) + "')\""
    t0 = time.perf_counter()
    hygiene_gate.decide(_bash_payload(cmd_1mb))
    elapsed_1mb = time.perf_counter() - t0

    assert elapsed_100kb < 2.0, f"pyc_payload classify 100KB: {elapsed_100kb:.4f}s"
    assert elapsed_1mb < 2.0, f"pyc_payload classify 1MB: {elapsed_1mb:.4f}s"


# --- B6: юникод (эмодзи/греческий) -> P ------------------------------------


def test_pycnarrow_b6_emoji_and_greek_pure():
    command = "python -c \"print('αβ\U0001F600')\""
    assert _payload_class(command) == "P"


# --- B12: null-байты в stdin -- subprocess-уровень, exit 0 без падения ----


def test_pycnarrow_b12_null_bytes_stdin_no_crash():
    result = _run_hook(b"\xff\xfe not json \x00")
    assert result.returncode == 0
    assert result.stdout.strip() == b""


# --- B13: payload из пробелов -> O -----------------------------------------


def test_pycnarrow_b13_whitespace_only_payload_opaque():
    assert _payload_class('python -c "   "') == "O"


# --- B14: журнал + pyc одновременно, payload чист -- журнал НЕ изменён,
# pyc-строки нет ----------------------------------------------------------


def test_pycnarrow_b14_journal_block_plus_clean_pyc_payload_no_pyc_line():
    command = (
        "echo x >> logs/routing-log.jsonl; python -c \"print(1+1)\""
    )
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == hygiene_gate.MSG_JOURNAL_BLOCK
    ctx = hso["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C not in ctx
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE not in ctx


# --- "U" (ПОПРАВКА LEAD 16:35): certain=False -- классификация НЕ
# считается, старый безусловный текст -----------------------------------


def test_pycnarrow_u_uncertain_form_not_classified():
    command = 'git commit -m "run python -c to test this"'
    assert hygiene_gate._is_python_dash_c_certain(command) is False
    assert _payload_class(command) == "U"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    hso = output["hookSpecificOutput"]
    assert "permissionDecision" not in hso
    assert hygiene_gate.MSG_PYTHON_DASH_C in hso["additionalContext"]


# --- I1/E15: ключ `pyc` (широкий) и измеритель -- НЕ переопределены -------


def test_pycnarrow_i1_pyc_key_unchanged_true_for_pure_payload():
    # Доказанно чистый (P) payload -- widely-signal `pyc` остаётся True
    # (I1: "всё, что давало pyc=True, даёт и после").
    command = 'python -c "print(1+1)"'
    signals = hygiene_gate._collect_v5_signals(command)
    assert signals["pyc"] is True
    assert signals["pyc_payload"] == "P"


def test_pycnarrow_i1_measurer_reads_pyc_not_pyc_payload():
    import permission_audit

    command = 'python -c "print(1+1)"'
    assert permission_audit.classify_hygiene(command) == ["python -c/heredoc"]


# --- негативный контроль трёх классов (по одной команде M/P/O, включая
# ту, что ОБЯЗАНА молчать) -- witness ----------------------------------


def test_pycnarrow_negative_control_m_class_warns_old_text():
    exit_code, output = hygiene_gate.decide(
        _bash_payload("python -c \"open('x.txt','w').write('x')\"")
    )
    assert exit_code == 0
    assert hygiene_gate.MSG_PYTHON_DASH_C in output["hookSpecificOutput"]["additionalContext"]


def test_pycnarrow_negative_control_p_class_fully_silent():
    exit_code, output = hygiene_gate.decide(_bash_payload('python -c "print(1+1)"'))
    assert exit_code == 0
    assert output is None


def test_pycnarrow_negative_control_o_class_warns_new_text():
    command = 'python -c "import subprocess; subprocess.run([\'ls\'])"'
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert hygiene_gate.MSG_PYTHON_DASH_C_OPAQUE in ctx


# =========================================================================
# ПОПРАВКА LEAD 17:2x -- фикс-раунд по вердикту критик-гейта (БЛОКЕР):
# реально пишущий код уходил в P (тишина) на алиасах импортов,
# from-импортах, цепочечных получателях и переприсваивании callable.
# Двенадцать замеренных атак -- КАЖДАЯ пином поимённо: вердикт ОБЯЗАН
# быть M или O (WARN), НИ ОДНА не молчит.
# =========================================================================


def _assert_never_silent(command: str, expected_class: str) -> None:
    assert _payload_class(command) == expected_class
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert output is not None, f"АТАКА ПРОШЛА МОЛЧА (регресс): {command}"
    assert "permissionDecision" not in output["hookSpecificOutput"]


# --- Ось A: алиасы импортов (import X as Y) -----------------------------


def test_pycnarrow_alias_1_import_as_qualified_os_remove_mutation():
    command = "python -c \"import os as o; o.remove('f.txt')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_2_import_as_qualified_shutil_rmtree_mutation():
    command = "python -c \"import shutil as sh; sh.rmtree('d')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_3_import_as_qualified_subprocess_opaque():
    command = "python -c \"import subprocess as sp; sp.run(['ls'])\""
    _assert_never_silent(command, "O")


# --- Ось A: from-импорты (from X import Y [as Z]) ------------------------


def test_pycnarrow_alias_4_from_import_bare_name_mutation():
    command = "python -c \"from os import remove; remove('f.txt')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_5_from_import_asname_mutation():
    command = "python -c \"from os import remove as rm; rm('f.txt')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_alias_6_from_import_opaque_name_opaque():
    command = "python -c \"from subprocess import run; run(['ls'])\""
    _assert_never_silent(command, "O")


# --- Ось B: цепочечные получатели (база вызова -- САМА вызов) ------------


def test_pycnarrow_chained_receiver_1_path_write_text_mutation():
    command = "python -c \"from pathlib import Path; Path('x.txt').write_text('x')\""
    _assert_never_silent(command, "M")


# Худший экземпляр критик-гейта, дословно.
def test_pycnarrow_chained_receiver_2_worst_case_journal_path_write_text_mutation():
    command = (
        "python -c \"from pathlib import Path; "
        "Path('logs/routing-log.jsonl').write_text('')\""
    )
    _assert_never_silent(command, "M")
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert hygiene_gate.MSG_PYTHON_DASH_C in output["hookSpecificOutput"]["additionalContext"]


def test_pycnarrow_chained_receiver_3_pathlib_path_open_w_mutation():
    # Методная форма open(mode) -- режим ПЕРВЫМ (не вторым) аргументом,
    # self неявен (см. _FREE_OPEN_DOTTED_NAMES докстринг).
    command = "python -c \"import pathlib; pathlib.Path('x').open('w')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_chained_receiver_4_io_open_write_mutation():
    command = "python -c \"import io; io.open('x','w').write('y')\""
    _assert_never_silent(command, "M")


def test_pycnarrow_chained_receiver_5_pandas_dataframe_to_csv_mutation():
    command = "python -c \"import pandas as pd; pd.DataFrame().to_csv('x.csv')\""
    _assert_never_silent(command, "M")


# --- Ось A: переприсваивание callable (w = open; w(p, 'w')) --------------


def test_pycnarrow_reassign_1_open_then_call_opaque():
    command = "python -c \"w = open; w('p', 'w')\""
    _assert_never_silent(command, "O")


def test_pycnarrow_reassign_2_os_remove_then_call_opaque():
    command = "python -c \"import os; r = os.remove; r('f')\""
    _assert_never_silent(command, "O")


# --- негативный контроль: переприсваивание НЕ callable-имени -- не O -----


def test_pycnarrow_reassign_control_non_mo_name_not_flagged_pure():
    # `x = 5` -- НЕ ссылается на open/M/O-имя -- НЕ должно давать O.
    command = 'python -c "x = 5; print(x)"'
    assert _payload_class(command) == "P"


# --- E8 регресс на методной форме open(mode) (Ось B доп.-фикс) -----------


def test_pycnarrow_e8_method_open_no_mode_pure():
    command = "python -c \"import pathlib; pathlib.Path('x').open()\""
    assert _payload_class(command) == "P"


def test_pycnarrow_e8_method_open_r_mode_pure():
    command = "python -c \"import pathlib; pathlib.Path('x').open('r')\""
    assert _payload_class(command) == "P"


# --- Ф1/Ф2/Ф3 -- подтверждения фикс-раунда -------------------------------


def test_pycnarrow_f2_certain_computed_once_signal_matches_direct_call():
    # Ф2: результат через `_collect_v5_signals` (готовый certain,
    # переданный параметром) совпадает с прямым вызовом без параметра.
    command = "python -c \"open('x.txt','w').write('x')\""
    signals = hygiene_gate._collect_v5_signals(command)
    assert signals["pyc_payload"] == hygiene_gate._classify_pyc_payload(command)


def test_pycnarrow_u_group_and_deny_bodies_still_green_after_fix_round():
    # Контроль DoD фикс-раунда: U-группа (обёртки/проза) и deny-тела
    # ПО-ПРЕЖНЕМУ зелены без правки -- пробный смок здесь, полное
    # покрытие -- существующие test_p6_wrapper_*/test_p6_mention_inside_*/
    # A4-список (весь узкий прогон -- witness отчёта).
    command = 'git commit -m "run python -c to test this"'
    assert hygiene_gate._classify_pyc_payload(command) == "U"
    exit_code, output = hygiene_gate.decide(_bash_payload(command))
    assert exit_code == 0
    assert hygiene_gate.MSG_PYTHON_DASH_C in output["hookSpecificOutput"]["additionalContext"]
