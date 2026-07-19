"""Тесты tools/journal_echo.py (PostToolUse-хук эха журнального
валидатора, N16). Стиль -- по образцу tools/test_tier_echo.py (юнит-тесты
чистой логики + subprocess-смок всего хука через stdin) и
tools/test_journal_validator.py (реальные tmp_path git-репо для
git-режима: _git/_init_repo/_write_journal -- та же схема).

Покрывает DoD спеки этой задачи буквально:
 1. не-журнальный путь -> тишина;
 2. журнал с чистой новой строкой (git-репо с HEAD) -> тишина;
 3. новая строка без category -> JSON с "JOURNAL ECHO: 1", текст дефекта
    совпадает с валидаторным;
 4. несколько дефектов -> счёт и "+K more" при >3;
 5. не-git каталог -> standalone-фолбэк работает (дефект ловится);
 6. битый payload/отсутствующий файл -> тихий exit 0;
 7. append-only нарушение (правка старой строки) -> ловится в git-режиме;
 8. non-ASCII в тексте дефекта -> ASCII-вывод.
Адверсариально: гигантская строка журнала не подвешивает (subprocess с
жёстким timeout -- падает громко TimeoutExpired, если код виснет).
Граничные тесты (правило 6а) для лимитов, введённых этим модулем:
MAX_HEAD_MESSAGES=3 (ровно 3 -- без суффикса; 4 -- "+1 more") и
MAX_CONTEXT_LEN=500 (ровно 500 -- не обрезано; 500+50 -- обрезано до 500),
плюс GIT_TIMEOUT_SECONDS (таймаут газа реально пробрасывается в
subprocess.run и обрабатывается как "нет HEAD").

Run from the repo root: python -m pytest tools/test_journal_echo.py -q
"""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import journal_echo  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "journal_echo.py"


# ---------------------------------------------------------------------
# helpers -- журнальные строки (по образцу test_journal_validator._line)
# ---------------------------------------------------------------------


def _line(event="delegated", ts="2026-07-10T08:00:00", agent="builder",
          category="implementation", notes="note",
          worker_ref="cli:2026-07-10T08:00:00", **kw) -> str:
    obj = {"ts": ts, "event": event, "agent": agent, "category": category,
           "notes": notes, "worker_ref": worker_ref}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


HEAD_LINE = _line(event="delegated", task_id="t-001", model="sonnet")
HEAD_TEXT = HEAD_LINE + "\n"


# ---------------------------------------------------------------------
# helpers -- real git repos (по образцу test_journal_validator._git/_init_repo)
# ---------------------------------------------------------------------


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")


def _init_repo(root: Path):
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")


def _write_journal(root: Path, text: str) -> None:
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-log.jsonl").write_text(text, encoding="utf-8")


def _seed_committed_journal(root: Path, text: str = HEAD_TEXT) -> Path:
    """git-init, пишет journal_path с text, коммитит -- HEAD теперь = text.
    Возвращает путь до journal-файла."""
    _init_repo(root)
    _write_journal(root, text)
    _git(root, "add", "logs/routing-log.jsonl")
    _git(root, "commit", "-q", "-m", "seed journal")
    return root / "logs" / "routing-log.jsonl"


# ---------------------------------------------------------------------
# helpers -- запуск хука
# ---------------------------------------------------------------------


def _post_tool_use_payload(file_path, tool_name="Edit") -> dict:
    return {
        "session_id": "sess-1",
        "transcript_path": "/x/transcript.jsonl",
        "cwd": ".",
        "hook_event_name": "PostToolUse",
        "tool_name": tool_name,
        "tool_input": {"file_path": str(file_path)},
        "tool_response": {"filePath": str(file_path), "success": True},
        "tool_use_id": "tu-1",
    }


def _run_hook(payload, timeout=10, env=None) -> subprocess.CompletedProcess:
    # env=None -> subprocess.run inherits the current process environment
    # unchanged (identical to the original behaviour before this parameter
    # existed). TIER ECHO subprocess-level tests pass a MODIFIED env (see
    # _env_with_home) so the CHILD process's Path.home() resolves to a
    # tmp_path sandbox -- monkeypatching journal_echo._projects_root in
    # THIS (parent) process has no effect on the subprocess, since main()
    # runs in a separate Python interpreter (empirically confirmed before
    # writing these tests: `Path.home()` in a subprocess DOES follow an
    # overridden USERPROFILE/HOME env var on this machine).
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        env=env,
    )


# ---------------------------------------------------------------------
# helpers -- TIER ECHO при записи: фейковый HOME + транскрипты субагентов
# ---------------------------------------------------------------------


def _assistant_line(model):
    return {"type": "assistant", "message": {"model": model}}


def _write_agent_transcript(home: Path, agent_id: str, lines,
                            proj="proj-slug", sess="sess-id") -> Path:
    """Пишет транскрипт по РЕАЛЬНОЙ структуре, эмпирически подтверждённой
    на этой машине (find по ~/.claude/projects перед реализацией):
    <home>/.claude/projects/<proj>/<sess>/subagents/agent-<id>.jsonl."""
    path = home / ".claude" / "projects" / proj / sess / "subagents" / f"agent-{agent_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(line) if not isinstance(line, str) else line for line in lines) + "\n",
        encoding="utf-8",
    )
    return path


def _env_with_home(home: Path) -> dict:
    """Оверрайд USERPROFILE/HOME для ДОЧЕРНЕГО процесса хука -- Path.home()
    в main() тогда резолвится в песочницу tmp_path/"home", не в реальный
    домашний каталог этой машины (см. докстринг _run_hook)."""
    env = dict(os.environ)
    env["USERPROFILE"] = str(home)
    env["HOME"] = str(home)
    return env


def _parse_stdout_json(stdout: str) -> dict:
    payload = json.loads(stdout)
    hook_output = payload["hookSpecificOutput"]
    assert hook_output["hookEventName"] == "PostToolUse"
    return hook_output


# ---------------------------------------------------------------------
# _extract_file_path -- pure logic
# ---------------------------------------------------------------------


def test_extract_file_path_present():
    assert journal_echo._extract_file_path({"tool_input": {"file_path": "/x/y.jsonl"}}) == "/x/y.jsonl"


def test_extract_file_path_missing_tool_input():
    assert journal_echo._extract_file_path({}) is None


def test_extract_file_path_tool_input_not_dict():
    assert journal_echo._extract_file_path({"tool_input": "not-a-dict"}) is None


def test_extract_file_path_missing_file_path_key():
    assert journal_echo._extract_file_path({"tool_input": {}}) is None


def test_extract_file_path_not_a_string():
    assert journal_echo._extract_file_path({"tool_input": {"file_path": 42}}) is None


def test_extract_file_path_empty_string():
    assert journal_echo._extract_file_path({"tool_input": {"file_path": ""}}) is None


# ---------------------------------------------------------------------
# _is_journal_path -- pure logic, оба вида сепараторов + границы
# ---------------------------------------------------------------------


def test_is_journal_path_forward_slash():
    assert journal_echo._is_journal_path("D:/repo/logs/routing-log.jsonl") is True


def test_is_journal_path_backslash():
    assert journal_echo._is_journal_path("D:\\repo\\logs\\routing-log.jsonl") is True


def test_is_journal_path_mixed_separators():
    assert journal_echo._is_journal_path("D:\\repo/logs\\routing-log.jsonl") is True


def test_is_journal_path_relative_two_components():
    assert journal_echo._is_journal_path("logs/routing-log.jsonl") is True


def test_is_journal_path_different_filename():
    assert journal_echo._is_journal_path("D:/repo/logs/other-log.jsonl") is False


def test_is_journal_path_prefix_collision_not_a_match():
    # "xlogs" -- не "logs" покомпонентно, а не substring-совпадение.
    assert journal_echo._is_journal_path("D:/repo/xlogs/routing-log.jsonl") is False


def test_is_journal_path_single_component_not_enough():
    assert journal_echo._is_journal_path("routing-log.jsonl") is False


def test_is_journal_path_empty_string():
    assert journal_echo._is_journal_path("") is False


# ---------------------------------------------------------------------
# _repo_root -- pure logic
# ---------------------------------------------------------------------


def test_repo_root_is_parent_of_parent(tmp_path):
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    assert journal_echo._repo_root(str(journal_path)) == tmp_path.resolve()


# ---------------------------------------------------------------------
# build_context -- pure logic, включая границы MAX_HEAD_MESSAGES
# ---------------------------------------------------------------------


def test_build_context_single_violation_no_suffix():
    ctx = journal_echo.build_context(["line 2: msg one"])
    assert ctx == "JOURNAL ECHO: 1 дефект(ов) в новых строках: line 2: msg one"


def test_build_context_exactly_three_boundary_no_more_suffix():
    ctx = journal_echo.build_context(["m1", "m2", "m3"])
    assert ctx == "JOURNAL ECHO: 3 дефект(ов) в новых строках: m1; m2; m3"
    assert "more" not in ctx


def test_build_context_beyond_boundary_four_adds_one_more():
    ctx = journal_echo.build_context(["m1", "m2", "m3", "m4"])
    assert ctx == "JOURNAL ECHO: 4 дефект(ов) в новых строках: m1; m2; m3; +1 more"


def test_build_context_many_beyond_boundary_counts_correctly():
    msgs = [f"m{i}" for i in range(10)]
    ctx = journal_echo.build_context(msgs)
    assert ctx == "JOURNAL ECHO: 10 дефект(ов) в новых строках: m0; m1; m2; +7 more"


def test_build_context_static_russian_template_not_mangled():
    # Статический русский префикс -- ЛИТЕРАЛ спеки, не проходит через
    # ASCII-санитайзер (иначе обязательная формулировка стала бы
    # "??????(??)"-мусором) -- сверяем побайтово точную кириллицу.
    ctx = journal_echo.build_context(["msg"])
    assert ctx.startswith("JOURNAL ECHO: 1 дефект(ов) в новых строках: ")


def test_build_context_long_message_truncated_via_per_item_sanitize():
    # Default ascii_only=False (raw/stdout path) -- всё ещё усекается
    # тем же потолком MAX_MESSAGE_LEN, только без ascii-replace.
    long_msg = "m" * (journal_echo.MAX_MESSAGE_LEN + 100)
    ctx = journal_echo.build_context([long_msg])
    assert ("m" * journal_echo.MAX_MESSAGE_LEN) in ctx
    assert ("m" * (journal_echo.MAX_MESSAGE_LEN + 1)) not in ctx


def test_build_context_default_ascii_only_false_keeps_cyrillic_readable():
    # Lead-правка: additionalContext (default -- ascii_only=False) несёт
    # СЫРУЮ (не '?'-мангленную) кириллицу динамики -- координатор видит
    # читаемый текст сообщения валидатора.
    ctx = journal_echo.build_context(["сообщение с кириллицей"])
    assert "сообщение с кириллицей" in ctx
    assert "?" not in ctx


def test_build_context_ascii_only_true_replaces_cyrillic_for_stderr():
    # ascii_only=True (используется для stderr-дубля) -- та же динамика
    # ascii-sanitize'на, как было изначально. Статический префикс сам
    # остаётся кириллицей (литерал, не динамика) -- поэтому ctx В ЦЕЛОМ
    # не обязана быть чистым ASCII, только ВСТАВЛЕННАЯ динамика.
    ctx = journal_echo.build_context(["сообщение с кириллицей"], ascii_only=True)
    assert "сообщение с кириллицей" not in ctx
    assert "?" in ctx


def test_build_context_static_prefix_never_sanitized_in_either_mode():
    # Статический русский префикс -- литерал спеки, НЕ проходит ни через
    # _raw_sanitize, ни через _ascii_sanitize, в ОБОИХ режимах.
    ctx_raw = journal_echo.build_context(["msg"], ascii_only=False)
    ctx_ascii = journal_echo.build_context(["msg"], ascii_only=True)
    prefix = "JOURNAL ECHO: 1 дефект(ов) в новых строках: "
    assert ctx_raw.startswith(prefix)
    assert ctx_ascii.startswith(prefix)


# ---------------------------------------------------------------------
# _raw_sanitize / _ascii_sanitize -- pure logic, включая границы MAX_MESSAGE_LEN
# ---------------------------------------------------------------------


def test_raw_sanitize_non_ascii_kept_as_is():
    result = journal_echo._raw_sanitize("клод")
    assert result == "клод"


def test_raw_sanitize_control_chars_stripped():
    result = journal_echo._raw_sanitize("a\x00b\x1fc")
    assert result == "abc"


def test_raw_sanitize_at_max_len_boundary_not_truncated():
    s = "a" * journal_echo.MAX_MESSAGE_LEN
    result = journal_echo._raw_sanitize(s)
    assert result == s
    assert len(result) == journal_echo.MAX_MESSAGE_LEN


def test_raw_sanitize_beyond_max_len_boundary_truncated():
    s = "a" * (journal_echo.MAX_MESSAGE_LEN + 50)
    result = journal_echo._raw_sanitize(s)
    assert len(result) == journal_echo.MAX_MESSAGE_LEN
    assert result == "a" * journal_echo.MAX_MESSAGE_LEN


def test_ascii_sanitize_non_ascii_replaced():
    result = journal_echo._ascii_sanitize("клод")
    assert result == "????"
    assert result.isascii()


def test_ascii_sanitize_control_chars_stripped():
    result = journal_echo._ascii_sanitize("a\x00b\x1fc")
    assert result == "abc"


def test_ascii_sanitize_at_max_len_boundary_not_truncated():
    s = "a" * journal_echo.MAX_MESSAGE_LEN
    result = journal_echo._ascii_sanitize(s)
    assert result == s
    assert len(result) == journal_echo.MAX_MESSAGE_LEN


def test_ascii_sanitize_beyond_max_len_boundary_truncated():
    s = "a" * (journal_echo.MAX_MESSAGE_LEN + 50)
    result = journal_echo._ascii_sanitize(s)
    assert len(result) == journal_echo.MAX_MESSAGE_LEN
    assert result == "a" * journal_echo.MAX_MESSAGE_LEN


# ---------------------------------------------------------------------
# _get_head_text -- git wiring, включая границу GIT_TIMEOUT_SECONDS
# ---------------------------------------------------------------------


def test_get_head_text_real_repo_success(tmp_path):
    _seed_committed_journal(tmp_path, HEAD_TEXT)
    assert journal_echo._get_head_text(tmp_path) == HEAD_TEXT


def test_get_head_text_not_a_repo_returns_none(tmp_path):
    # tmp_path НИКОГДА не git-init'ed.
    assert journal_echo._get_head_text(tmp_path) is None


def test_get_head_text_file_not_on_head_returns_none(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "other.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "other.txt")
    _git(tmp_path, "commit", "-q", "-m", "no journal yet")
    assert journal_echo._get_head_text(tmp_path) is None


def test_get_head_text_timeout_returns_none(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=kwargs.get("timeout"))
    monkeypatch.setattr(journal_echo.subprocess, "run", fake_run)
    assert journal_echo._get_head_text(tmp_path) is None


def test_get_head_text_passes_configured_timeout(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout"))
    monkeypatch.setattr(journal_echo.subprocess, "run", fake_run)
    journal_echo._get_head_text(tmp_path)
    assert captured["timeout"] == journal_echo.GIT_TIMEOUT_SECONDS


def test_get_head_text_git_binary_missing_returns_none(monkeypatch, tmp_path):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("git not found")
    monkeypatch.setattr(journal_echo.subprocess, "run", fake_run)
    assert journal_echo._get_head_text(tmp_path) is None


# ---------------------------------------------------------------------
# main() end-to-end -- subprocess-смок, DoD 1-8 + adversarial
# ---------------------------------------------------------------------


def test_echo_non_journal_path_silent(tmp_path):
    # DoD 1: не-журнальный путь -> тишина, даже если файл существует.
    other_file = tmp_path / "not-a-journal.txt"
    other_file.write_text("irrelevant content", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(other_file))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_git_mode_clean_new_line_silent(tmp_path):
    # DoD 2: журнал с чистой новой строкой (git-репо с HEAD) -> тишина.
    journal_path = _seed_committed_journal(tmp_path)
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="sonnet", notes="second task, clean")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_git_mode_missing_category_defect(tmp_path):
    # DoD 3: новая строка без category -> JSON "JOURNAL ECHO: 1", текст
    # дефекта совпадает с валидаторным. Lead-правка: validate_new_lines()
    # само формулирует сообщение частично по-русски ("отсутствует/
    # невалидно обязательное поле") -- additionalContext (stdout, raw)
    # обязан нести это ЧИТАЕМЫМ; stderr (ascii-only дубль) -- тем же
    # текстом, но с кириллицей, заменённой на '?'.
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="sonnet", category="")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов) в новых строках:" in ctx
    assert "'category'" in ctx
    assert "отсутствует" in ctx  # читаемая кириллица валидаторного сообщения (raw-канал)
    # stdout wire bytes сами -- чистый ASCII (ensure_ascii=True экранирует
    # non-ASCII в \uXXXX на проводе, JSON-парсинг восстанавливает читаемый текст).
    assert result.stdout.isascii()
    # stderr -- голый текст, та же динамика ASCII-sanitize'на (не читаема как есть).
    assert "отсутствует" not in result.stderr
    assert "'category'" in result.stderr  # ASCII-часть сообщения остаётся как есть
    assert "?" in result.stderr


def test_echo_git_mode_multiple_defects_count_and_more_suffix(tmp_path):
    # DoD 4: несколько дефектов -> счёт и "+K more" при >3.
    journal_path = _seed_committed_journal(tmp_path)
    bad_lines = [
        _line(event="delegated", ts=f"2026-07-10T08:1{i}:00", task_id=f"t-00{i + 2}",
              model="sonnet", notes="")
        for i in range(4)
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in bad_lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 4 дефект(ов) в новых строках:" in ctx
    assert "+1 more" in ctx


def test_echo_standalone_fallback_non_git_dir_catches_defect(tmp_path):
    # DoD 5: не-git каталог -> standalone-фолбэк работает (дефект ловится).
    # tmp_path НИКОГДА не git-init'ed.
    bad_text = _line(event="delegated", ts="2026-07-10T08:00:00", task_id="t-001",
                      model="sonnet", agent="")
    _write_journal(tmp_path, bad_text + "\n")
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "JOURNAL ECHO: 1 дефект(ов)" in hook_output["additionalContext"]
    assert "'agent'" in hook_output["additionalContext"]


def test_echo_standalone_fallback_non_git_dir_clean_silent(tmp_path):
    # Симметричный позитивный случай standalone-фолбэка: чистый файл в
    # не-git каталоге -> тишина (не просто "фолбэк ловит дефект", но и
    # "фолбэк не ложно-срабатывает на чистом входе").
    _write_journal(tmp_path, HEAD_TEXT)
    journal_path = tmp_path / "logs" / "routing-log.jsonl"
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_malformed_json_payload_silent_exit():
    # DoD 6a: битый payload -> тихий exit 0.
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{not valid json",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_payload_not_a_dict_silent_exit():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="[1, 2, 3]",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_missing_file_on_disk_silent_exit(tmp_path):
    # DoD 6b: путь журнальный по форме, но файла на диске нет -> тихий exit 0.
    missing = tmp_path / "logs" / "routing-log.jsonl"
    result = _run_hook(_post_tool_use_payload(missing))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_git_mode_append_only_violation_caught(tmp_path):
    # DoD 7: правка СУЩЕСТВУЮЩЕЙ строки журнала (append-only нарушение)
    # -- ловится в git-режиме.
    journal_path = _seed_committed_journal(tmp_path)
    modified_head_line = _line(event="delegated", ts="2026-07-10T08:00:00", task_id="t-001",
                                model="sonnet", notes="ИЗМЕНЕНО задним числом")
    journal_path.write_text(modified_head_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "append-only" in hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов)" in hook_output["additionalContext"]


def test_echo_non_ascii_defect_text_readable_in_stdout_ascii_in_stderr(tmp_path):
    # DoD 8 (УТОЧНЕНО Lead-правкой после критик-приёмки + Lead-смока):
    # non-ASCII в тексте дефекта -- ДВА разных канала, ДВА разных
    # исхода. event -- не валидный enum-токен, но содержит кириллицу --
    # validate_new_lines вкладывает его в сообщение через repr()
    # буквально (не экранирует печатаемую кириллицу).
    #  - stdout (additionalContext, JSON, координатору): динамика
    #    остаётся ЧИТАЕМОЙ (raw) -- json.dumps(ensure_ascii=True) сам
    #    экранирует не-ASCII в \uXXXX на проводе, json.loads()
    #    восстанавливает читаемый текст; wire-байты стдаута при этом
    #    остаются чистым ASCII (сами \uXXXX-эскейпы -- ASCII).
    #  - stderr (голый текст, cp1251-консоль): та же динамика
    #    ASCII-sanitize'на -- кириллица заменена на '?', как раньше.
    journal_path = _seed_committed_journal(tmp_path)
    bad_line = _line(event="цель_событие", ts="2026-07-10T08:10:00")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0

    assert result.stdout.isascii()  # wire-байты стдаута -- чистый ASCII
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов) в новых строках:" in ctx  # статика цела
    assert "цель_событие" in ctx  # динамика ЧИТАЕМА после json.loads()

    assert "цель_событие" not in result.stderr  # динамика вычищена в stderr
    assert "?" in result.stderr  # кириллица динамики заменена на '?'


def test_echo_giant_line_does_not_hang(tmp_path):
    # Адверсариально: гигантская строка журнала не подвешивает хук.
    # Жёсткий subprocess-таймаут -- TimeoutExpired упадёт громко, если
    # код виснет, вместо того чтобы тест сам завис навечно.
    journal_path = _seed_committed_journal(tmp_path)
    giant_notes = "x" * (2 * 1024 * 1024)  # 2MB single-line payload
    giant_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                        model="sonnet", notes=giant_notes)
    journal_path.write_text(HEAD_TEXT + giant_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), timeout=20)
    assert result.returncode == 0
    # Строка валидна (все обязательные поля есть) -> тишина, несмотря на размер.
    assert result.stdout == ""
    assert result.stderr == ""



# =======================================================================
# TIER ECHO при записи (расширение этой задачи) -- pure logic
# =======================================================================


# ---------------------------------------------------------------------
# _extract_declared_word -- pure logic
# ---------------------------------------------------------------------


def test_extract_declared_word_direct_match():
    assert journal_echo._extract_declared_word("sonnet") == "sonnet"


def test_extract_declared_word_substring_in_full_model_id():
    assert journal_echo._extract_declared_word("claude-opus-4-8") == "opus"


def test_extract_declared_word_case_insensitive():
    assert journal_echo._extract_declared_word("Claude-FABLE-5") == "fable"


def test_extract_declared_word_not_a_string():
    assert journal_echo._extract_declared_word(None) is None
    assert journal_echo._extract_declared_word(42) is None


def test_extract_declared_word_empty_string():
    assert journal_echo._extract_declared_word("") is None


def test_extract_declared_word_no_known_word():
    assert journal_echo._extract_declared_word("gpt-4") is None


def test_extract_declared_word_picks_first_known_tier_words_order():
    # "opus-sonnet-hybrid" содержит ОБА слова подстрокой -- порядок выбора
    # -- порядок tier_echo.KNOWN_TIER_WORDS (haiku, sonnet, opus, fable),
    # НЕ порядок появления в самой строке ("opus" физически раньше в
    # строке, но "sonnet" раньше в KNOWN_TIER_WORDS).
    assert journal_echo._extract_declared_word("opus-sonnet-hybrid") == "sonnet"


# ---------------------------------------------------------------------
# _projects_root / _find_agent_transcript -- pure logic (monkeypatched)
# ---------------------------------------------------------------------


def test_find_agent_transcript_match(tmp_path, monkeypatch):
    path = _write_agent_transcript(tmp_path, "abc123", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    assert journal_echo._find_agent_transcript("abc123") == str(path)


def test_find_agent_transcript_id_with_dashes(tmp_path, monkeypatch):
    path = _write_agent_transcript(tmp_path, "abc-123-xyz", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    assert journal_echo._find_agent_transcript("abc-123-xyz") == str(path)


def test_find_agent_transcript_not_found(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    assert journal_echo._find_agent_transcript("no-such-id") is None


def test_find_agent_transcript_glob_error_returns_none(monkeypatch):
    class _BoomRoot:
        def glob(self, pattern):
            raise OSError("boom")

    monkeypatch.setattr(journal_echo, "_projects_root", lambda: _BoomRoot())
    assert journal_echo._find_agent_transcript("x") is None


# ---------------------------------------------------------------------
# _collect_tier_events -- pure logic (monkeypatched _projects_root)
# ---------------------------------------------------------------------


def _delegated_obj(**kw):
    obj = {"ts": "2026-07-10T08:10:00", "event": "delegated", "agent": "builder",
            "category": "implementation", "notes": "note", "task_id": "t-002",
            "model": "sonnet", "worker_ref": "agent:abc123"}
    obj.update(kw)
    return json.dumps(obj, ensure_ascii=False)


def test_collect_tier_events_full_match_silent(tmp_path, monkeypatch):
    _write_agent_transcript(tmp_path, "abc123", [_assistant_line("claude-sonnet-5")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(model="sonnet")], [])
    assert events == []


def test_collect_tier_events_mismatch(tmp_path, monkeypatch):
    _write_agent_transcript(tmp_path, "abc123", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(model="fable")], [])
    assert len(events) == 1
    line_no, kind, declared_word, counts = events[0]
    assert (line_no, kind, declared_word) == (1, "mismatch", "fable")
    assert counts == {"claude-opus-4-8": 1}


def test_collect_tier_events_partial_match_informational(tmp_path, monkeypatch):
    _write_agent_transcript(
        tmp_path, "abc123",
        [_assistant_line("claude-fable-1"), _assistant_line("claude-sonnet-5")],
    )
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(model="fable")], [])
    assert len(events) == 1
    assert events[0][1] == "info"


def test_collect_tier_events_synthetic_excluded_stays_silent(tmp_path, monkeypatch):
    # Транскрипт несёт РЕАЛЬНУЮ модель (совпадающую с заявленным ярусом) +
    # synthetic-строку -- фильтр tier_echo.iter_transcript_models должен
    # исключить synthetic, иначе она сломала бы "полное совпадение".
    _write_agent_transcript(
        tmp_path, "abc123",
        [_assistant_line("claude-sonnet-5"), {"type": "assistant", "message": {"model": "<synthetic>"}}],
    )
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(model="sonnet")], [])
    assert events == []


def test_collect_tier_events_transcript_not_found_silent(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj()], [])
    assert events == []


def test_collect_tier_events_no_declared_word_skips(tmp_path, monkeypatch):
    _write_agent_transcript(tmp_path, "abc123", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(model="gpt-4")], [])
    assert events == []


def test_collect_tier_events_event_outside_trigger_set_skipped(tmp_path, monkeypatch):
    _write_agent_transcript(tmp_path, "abc123", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(event="decomposable", model="fable")], [])
    assert events == []


def test_collect_tier_events_worker_ref_cli_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events(
        [_delegated_obj(worker_ref="cli:2026-07-10T08:00:00", model="fable")], [])
    assert events == []


def test_collect_tier_events_worker_ref_retro_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events(
        [_delegated_obj(worker_ref="retro:2026-07-10T08:00:00", model="fable")], [])
    assert events == []


def test_collect_tier_events_worker_ref_missing_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    obj = json.loads(_delegated_obj())
    del obj["worker_ref"]
    events = journal_echo._collect_tier_events([json.dumps(obj)], [])
    assert events == []


def test_collect_tier_events_agent_empty_id_boundary_skipped(tmp_path, monkeypatch):
    # Граница: worker_ref == "agent:" (id пуст) -- regex требует 1+ символ,
    # не матчит -- пропуск, не краш.
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events([_delegated_obj(worker_ref="agent:", model="fable")], [])
    assert events == []


def test_collect_tier_events_agent_id_with_dashes_boundary_matches(tmp_path, monkeypatch):
    _write_agent_transcript(tmp_path, "ab-12-cd", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events(
        [_delegated_obj(worker_ref="agent:ab-12-cd", model="fable")], [])
    assert len(events) == 1
    assert events[0][1] == "mismatch"


def test_collect_tier_events_malformed_json_line_skipped_not_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    events = journal_echo._collect_tier_events(["{not valid json"], [])
    assert events == []


def test_collect_tier_events_line_numbering_accounts_for_head_lines(tmp_path, monkeypatch):
    _write_agent_transcript(tmp_path, "abc123", [_assistant_line("claude-opus-4-8")])
    monkeypatch.setattr(journal_echo, "_projects_root", lambda: tmp_path / ".claude" / "projects")
    head_lines = ["dummy head line 1", "dummy head line 2"]
    events = journal_echo._collect_tier_events([_delegated_obj(model="fable")], head_lines)
    assert events[0][0] == 3  # len(head_lines) + idx(0) + 1


# ---------------------------------------------------------------------
# build_tier_segment -- pure logic, включая границы MAX_TIER_LINES
# ---------------------------------------------------------------------


def test_build_tier_segment_empty_list():
    assert journal_echo.build_tier_segment([]) == ""


def test_build_tier_segment_mismatch_exact_format():
    ev = (2, "mismatch", "fable", {"claude-opus-4-8": 1})
    seg = journal_echo.build_tier_segment([ev])
    assert seg == "TIER ECHO: строка 2 model='fable' vs measured claude-opus-4-8=1 MISMATCH"


def test_build_tier_segment_info_exact_format_no_mismatch_word():
    ev = (2, "info", "fable", {"claude-fable-1": 1, "claude-sonnet-5": 1})
    seg = journal_echo.build_tier_segment([ev])
    assert seg == "TIER ECHO: строка 2 measured claude-fable-1=1, claude-sonnet-5=1"
    assert "MISMATCH" not in seg


def test_build_tier_segment_exactly_five_boundary_no_more_suffix():
    events = [(i, "mismatch", "fable", {"claude-opus-4-8": 1}) for i in range(1, 6)]
    seg = journal_echo.build_tier_segment(events)
    assert "more" not in seg
    assert seg.count("TIER ECHO") == 5


def test_build_tier_segment_beyond_boundary_six_adds_one_more():
    events = [(i, "mismatch", "fable", {"claude-opus-4-8": 1}) for i in range(1, 7)]
    seg = journal_echo.build_tier_segment(events)
    assert seg.count("TIER ECHO") == 5
    assert seg.endswith("; +1 more")


def test_build_tier_segment_ascii_only_true_sanitizes_model_name():
    # Статический литерал "TIER ECHO: строка N ..." -- кириллица, остаётся
    # как есть даже в ascii_only-режиме (тот же принцип, что build_context
    # -- см. test_build_tier_segment_static_literal_stays_cyrillic_in_both_modes
    # ниже), поэтому строка ЦЕЛИКОМ не обязана быть чистым ASCII -- только
    # ДИНАМИКА (имя модели) обязана быть ascii-sanitize'на.
    ev = (2, "mismatch", "fable", {"клод-опус": 1})
    seg = journal_echo.build_tier_segment([ev], ascii_only=True)
    assert "клод-опус" not in seg
    assert "?" in seg


def test_build_tier_segment_ascii_only_false_keeps_model_name_readable():
    ev = (2, "mismatch", "fable", {"клод-опус": 1})
    seg = journal_echo.build_tier_segment([ev], ascii_only=False)
    assert "клод-опус" in seg


def test_build_tier_segment_static_literal_stays_cyrillic_in_both_modes():
    # "TIER ECHO: СТРОКА N ..." -- статический литерал спеки, тот же
    # принцип, что build_context: никогда не проходит через санитайзер,
    # ни в одном режиме (даже ascii_only=True).
    ev = (2, "mismatch", "fable", {"claude-opus-4-8": 1})
    seg_raw = journal_echo.build_tier_segment([ev], ascii_only=False)
    seg_ascii = journal_echo.build_tier_segment([ev], ascii_only=True)
    assert seg_raw.startswith("TIER ECHO: строка 2 model=")
    assert seg_ascii.startswith("TIER ECHO: строка 2 model=")


# ---------------------------------------------------------------------
# combine_context -- pure logic
# ---------------------------------------------------------------------


def test_combine_context_only_violations_matches_build_context_output():
    violations = ["line 2: msg one"]
    assert journal_echo.combine_context(violations, []) == journal_echo.build_context(violations)


def test_combine_context_only_tier_events_no_violations_still_prints():
    ev = (2, "mismatch", "fable", {"claude-opus-4-8": 1})
    ctx = journal_echo.combine_context([], [ev])
    assert ctx == journal_echo.build_tier_segment([ev])
    assert "JOURNAL ECHO" not in ctx


def test_combine_context_both_joined_with_semicolon():
    violations = ["line 2: msg one"]
    ev = (3, "mismatch", "fable", {"claude-opus-4-8": 1})
    ctx = journal_echo.combine_context(violations, [ev])
    assert ctx == journal_echo.build_context(violations) + "; " + journal_echo.build_tier_segment([ev])


def test_combine_context_both_empty_yields_empty_string():
    assert journal_echo.combine_context([], []) == ""


# =======================================================================
# TIER ECHO при записи -- subprocess end-to-end (DoD а-з + границы)
# =======================================================================


def test_echo_tier_dod_a_full_match_silent(tmp_path):
    # DoD (а): delegated с agent:<id>, транскрипт с одной моделью того же
    # яруса -> тишина.
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(home, "abc123", [_assistant_line("claude-sonnet-5")])
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="sonnet", worker_ref="agent:abc123", notes="clean tier match")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tier_dod_b_mismatch_fable_declared_opus_measured(tmp_path):
    # DoD (б): заявлен fable, транскрипт opus -> MISMATCH-строка.
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(home, "fbl001", [_assistant_line("claude-opus-4-8")])
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="fable", worker_ref="agent:fbl001", notes="mismatch case")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx == "TIER ECHO: строка 2 model='fable' vs measured claude-opus-4-8=1 MISMATCH"
    assert ctx in result.stderr


def test_echo_tier_dod_v_mid_worker_informational_no_mismatch(tmp_path):
    # DoD (в): mid-worker -- транскрипт fable+sonnet при заявленном fable
    # -> informational-строка без MISMATCH.
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(
        home, "mid001",
        [_assistant_line("claude-fable-1"), _assistant_line("claude-sonnet-5")],
    )
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="fable", worker_ref="agent:mid001", notes="mid-worker case")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx == "TIER ECHO: строка 2 measured claude-fable-1=1, claude-sonnet-5=1"
    assert "MISMATCH" not in ctx


def test_echo_tier_dod_g_worker_ref_cli_skipped_silent(tmp_path):
    # DoD (г), часть 1: worker_ref cli:xxx -> пропуск без warn (тишина).
    journal_path = _seed_committed_journal(tmp_path)
    new_line = _line(event="accepted", ts="2026-07-10T08:10:00", task_id="t-001",
                      agent="builder", by="opus", witness="tests pass", model="sonnet",
                      worker_ref="cli:2026-07-10T08:10:00", notes="accepted via cli ref")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tier_dod_g_worker_ref_retro_skipped_silent(tmp_path):
    # DoD (г), часть 2: worker_ref retro:xxx -> пропуск без warn.
    journal_path = _seed_committed_journal(tmp_path)
    new_line = _line(event="accepted", ts="2026-07-10T08:10:00", task_id="t-001",
                      agent="builder", by="opus", witness="tests pass", model="sonnet",
                      worker_ref="retro:2026-07-10T08:10:00", notes="accepted via retro ref")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tier_dod_g_worker_ref_absent_skipped_silent(tmp_path):
    # DoD (г), часть 3: worker_ref отсутствует вовсе -> пропуск без warn.
    journal_path = _seed_committed_journal(tmp_path)
    obj = {"ts": "2026-07-10T08:10:00", "event": "accepted", "agent": "builder",
           "category": "implementation", "notes": "accepted, no worker_ref field",
           "task_id": "t-001", "by": "opus", "witness": "tests pass", "model": "sonnet"}
    new_line = json.dumps(obj, ensure_ascii=False)
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tier_dod_d_transcript_not_found_silent(tmp_path):
    # DoD (д): транскрипт не найден -> тишина.
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"  # НЕ создаём никакого транскрипта здесь.
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="sonnet", worker_ref="agent:doesnotexist123", notes="clean")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tier_dod_e_form_defect_and_mismatch_together(tmp_path):
    # DoD (е): дефект формы + MISMATCH вместе -> оба в одном additionalContext.
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(home, "fbl002", [_assistant_line("claude-opus-4-8")])
    bad_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="fable", category="", worker_ref="agent:fbl002",
                      notes="defect and mismatch together")
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов)" in ctx
    assert "'category'" in ctx
    assert "TIER ECHO: строка 2 model='fable' vs measured claude-opus-4-8=1 MISMATCH" in ctx
    # Оба сегмента склеены через "; " (спека п.3).
    assert "; TIER ECHO" in ctx


def test_echo_tier_dod_zh_synthetic_lines_not_counted(tmp_path):
    # DoD (ж): synthetic-строки в транскрипте не считаются -- реальная
    # модель, совпадающая с заявленным ярусом, даёт полную тишину, а не
    # ложный mismatch/informational от учтённой synthetic-строки.
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(
        home, "syn001",
        [_assistant_line("claude-sonnet-5"), {"type": "assistant", "message": {"model": "<synthetic>"}}],
    )
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="sonnet", worker_ref="agent:syn001", notes="synthetic filtered")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_tier_dod_z_more_than_five_tier_lines_shows_more_suffix(tmp_path):
    # DoD (з): >5 tier-строк -> "+K more".
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    n = 6
    for i in range(n):
        _write_agent_transcript(home, f"agentid{i}", [_assistant_line("claude-opus-4-8")],
                                 proj=f"proj{i}", sess=f"sess{i}")
    new_lines = [
        _line(event="delegated", ts=f"2026-07-10T08:1{i}:00", task_id=f"t-00{2 + i}",
              model="fable", worker_ref=f"agent:agentid{i}", notes=f"mismatch #{i}")
        for i in range(n)
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in new_lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TIER ECHO") == 5
    assert "+1 more" in ctx


def test_echo_tier_exactly_five_tier_lines_no_more_suffix(tmp_path):
    # Граница (правило 6а): РОВНО 5 tier-строк -> без "+more".
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    n = 5
    for i in range(n):
        _write_agent_transcript(home, f"agentid{i}", [_assistant_line("claude-opus-4-8")],
                                 proj=f"proj{i}", sess=f"sess{i}")
    new_lines = [
        _line(event="delegated", ts=f"2026-07-10T08:1{i}:00", task_id=f"t-00{2 + i}",
              model="fable", worker_ref=f"agent:agentid{i}", notes=f"mismatch #{i}")
        for i in range(n)
    ]
    journal_path.write_text(HEAD_TEXT + "".join(l + "\n" for l in new_lines), encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert ctx.count("TIER ECHO") == 5
    assert "more" not in ctx


def test_echo_tier_worker_ref_agent_id_with_dashes_boundary(tmp_path):
    # Граница: id с дефисами -- полный проход по всему пайплайну (не
    # только _collect_tier_events напрямую).
    journal_path = _seed_committed_journal(tmp_path)
    home = tmp_path / "home"
    _write_agent_transcript(home, "ab-12-cd", [_assistant_line("claude-opus-4-8")])
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="fable", worker_ref="agent:ab-12-cd", notes="dashed id")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), env=_env_with_home(home))
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    assert "MISMATCH" in hook_output["additionalContext"]


def test_echo_tier_worker_ref_agent_empty_id_boundary_silent(tmp_path):
    # Граница: worker_ref == "agent:" (id пуст) -- полный пайплайн, тишина.
    journal_path = _seed_committed_journal(tmp_path)
    new_line = _line(event="delegated", ts="2026-07-10T08:10:00", task_id="t-002",
                      model="fable", worker_ref="agent:", notes="empty agent id")
    journal_path.write_text(HEAD_TEXT + new_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path))
    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_echo_giant_invalid_line_does_not_hang_and_reports(tmp_path):
    # Тот же гигантский размер, но строка ИМЕЕТ дефект (пустой notes) --
    # хук обязан и не зависнуть, и корректно доложить дефект (сообщение
    # само по себе короткое -- notes-значение не встраивается в текст
    # нарушения дословно, см. journal_validator.validate_new_lines).
    journal_path = _seed_committed_journal(tmp_path)
    giant_task_id_holder = "x" * (2 * 1024 * 1024)
    bad_line = json.dumps({
        "ts": "2026-07-10T08:10:00", "event": "delegated", "agent": "builder",
        "category": "implementation", "notes": "",
        "worker_ref": "cli:2026-07-10T08:10:00", "task_id": "t-002", "model": "sonnet",
        "_padding": giant_task_id_holder,
    }, ensure_ascii=False)
    journal_path.write_text(HEAD_TEXT + bad_line + "\n", encoding="utf-8")
    result = _run_hook(_post_tool_use_payload(journal_path), timeout=20)
    assert result.returncode == 0
    hook_output = _parse_stdout_json(result.stdout)
    ctx = hook_output["additionalContext"]
    assert "JOURNAL ECHO: 1 дефект(ов)" in ctx
    # Дефектное сообщение само по себе короткое (жалуется на пустой
    # 'notes', не встраивает значение поля-паддинга) -- гигантский
    # padding НЕ протекает в вывод.
    assert len(ctx) < 1000
