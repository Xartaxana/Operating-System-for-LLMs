"""Юнит-смоки tools/owns_gate.py. Покрывает DoD спеки задачи (attempt 1
+ attempt 2 регрессы вердикта критика t-333): сверка пересечения
(равные пути / вложенный каталог / глоб обеими сторонами / соседние
каталоги с общим префиксом имени -- НЕ пересечение), окно живости 24ч
(НА границе -- ещё живая; ЗА границей -- уже нет), область сверки по
cwd (F2 -- другой cwd игнорируется, тот же cwd + другой session_key ->
WARN с меткой D-0060), read-only диспатч -- тишина и sidecar не
растёт, не-Task тул -- тишина, sidecar отсутствует/битая строка --
fail-open, адверсариальная батарея stdin (битый JSON, не-UTF8 байты,
огромная строка owns >1МБ, payload не dict) -- везде exit 0 без
трейсбека; ПЛЮС именные регрессы по каждому блокеру критика: B1
(каноническая форма 'owns (ABSOLUTE write paths):', RU-форма,
markdown-буллет, ёлочки, отрез прозаического хвоста с сохранением
путей-с-пробелами), B2 (marker-ложняк на Given-строке пропускается в
пользу настоящей owns-строки ниже; диагностика пустоты -> WARN, sidecar
не растёт), F4 (дедуп WARN на один путь против нескольких живых
записей), F1 (компакция sidecar на границе 500/501 строк).

ATTEMPT 3 (блокер контрольного входа критика): именной регресс НА ВЕТКУ
КЛАССА -- Given-строка, несущая "owns" ВНУТРИ имени файла И валидные
абсолютные пути через запятую, больше НЕ перехватывает разбор у
настоящей owns-строки ниже (проверка и на уровне extract_owns_paths, и
сквозным decide() -- в sidecar пишется ОБЪЯВЛЕННЫЙ путь, не пути
read-only корзины "дано"); тест ФОЛЛБЕК-ветки (word-boundary совпадений
нет вовсе -> подстрочный перебор прежнего вида работает); пин N2
(ведущая звезда глоба съедается стриппером -- known limitation) и
граничный тест величины N3 (мусорный префикс ~50КБ скобочных групп
разбирается < 5с)."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import owns_gate  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "owns_gate.py"


def _run_hook(raw_input, cwd=None, **kwargs) -> subprocess.CompletedProcess:
    # cwd -- ВСЕГДА передаётся явно тестами, что пишут через sidecar
    # (payload["cwd"] определяет путь logs/owns_registry.jsonl, см.
    # docstring owns_gate.py) -- иначе subprocess унаследовал бы cwd
    # тестового раннера и дописал бы РЕАЛЬНЫЙ repo-файл logs/
    # owns_registry.jsonl (тот же приём изоляции, что
    # tools/test_dod_track.py::_run_hook уже использует).
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw_input,
        capture_output=True,
        cwd=str(cwd) if cwd is not None else None,
        **kwargs,
    )


def _writing_payload(owns_text: str, session_id="s-1", cwd="D:\\repo", description="sonnet: write") -> dict:
    # owns -- НА СВОЕЙ строке (реалистичная форма манифеста этого кита:
    # каждый пункт МАНИФЕСТА -- отдельная строка-буллет, см. докстринг
    # owns_gate.py, "ИЗВЛЕЧЕНИЕ OWNS-ПУТЕЙ").
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        f"owns: {owns_text}.\n"
        "Правь файлы."
    )
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": description},
        "session_id": session_id,
        "cwd": cwd,
    }


def _write_registry_line(path: Path, ts: str, session_key: str, cwd: str, description: str, owns: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"ts": ts, "session_key": session_key, "cwd": cwd, "description": description, "owns": owns}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------
# Извлечение owns-путей из промпта.
# ---------------------------------------------------------------------


def test_extract_owns_paths_windows_absolute():
    paths = owns_gate.extract_owns_paths("Дано: репо. owns: D:\\repo\\tools\\x.py; D:\\repo\\tools\\y.py.")
    assert paths == ["D:\\repo\\tools\\x.py", "D:\\repo\\tools\\y.py"]


def test_extract_owns_paths_no_marker_is_readonly():
    assert owns_gate.extract_owns_paths("Прочитай файл и скажи, что там.") == []


def test_extract_owns_paths_drops_relative_prose_tokens():
    # "строка в .gitignore" -- не путь-подобный токен (нет диска/слэша
    # в начале, нет "*") -- отбрасывается фильтром is_path_token.
    paths = owns_gate.extract_owns_paths(
        "owns: D:\\repo\\tools\\x.py, строка в .gitignore (не путь)."
    )
    assert paths == ["D:\\repo\\tools\\x.py"]


# --- B1: каноническая форма/RU-форма/markdown/ёлочки/прозаический хвост -


def test_extract_owns_paths_canonical_single_path_form():
    # Каноническая форма R11 CLAUDE.md кита: "owns (ABSOLUTE write
    # paths): <path>" -- скобочное уточнение МЕЖДУ маркером и
    # двоеточием (блокер B1, форма НЕ была в ключах приёмки attempt 1).
    prompt = "owns (ABSOLUTE write paths): D:/repo/tools/only_one.py"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/only_one.py"]


def test_extract_owns_paths_canonical_two_paths_form():
    prompt = "owns (ABSOLUTE write paths): D:/repo/tools/a.py; D:/repo/tools/b.py"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_ru_form():
    prompt = "owns (АБСОЛЮТНЫЕ пути записи): D:/repo/tools/x.py"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/x.py"]


def test_extract_owns_paths_markdown_bullet_form():
    # "**owns**:" -- звёзды markdown ДО двоеточия, "-" буллет ДО
    # маркера (не влияет -- маркер ищется поиском внутри строки).
    prompt = "- **owns**: D:/a.py; D:/b.py"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/a.py", "D:/b.py"]


def test_extract_owns_paths_guillemets_quoted_path():
    prompt = "owns: \u00abD:/a.py\u00bb"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/a.py"]


def test_extract_owns_paths_prose_tail_cut_preserves_path_with_space():
    # Хвост " — новый файл" (пробел-эмтире-пробел) отрезается у
    # первого токена; путь ВТОРОГО токена содержит пробел (прецедент
    # "D:/AI CRM/...") и должен выжить ЦЕЛИКОМ -- по пробелу НЕ режем.
    prompt = "owns: D:/a.py \u2014 новый файл; D:/AI CRM/x/AGENTS.md"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/a.py",
        "D:/AI CRM/x/AGENTS.md",
    ]


def test_extract_owns_paths_marker_false_positive_line_skipped_for_valid_line_below():
    # "owns_gate.py" на Given-строке -- ложное срабатывание подстрочного
    # маркера, НЕ дающее path-токенов. Разбирается настоящая owns-строка
    # ниже (блокер B2; в attempt 3 та же строка отсеивается ещё раньше --
    # фильтром `\bowns\b`, см. регресс блокера ниже).
    prompt = (
        "Дано: правки в tools/owns_gate.py уже накоплены.\n"
        "owns: D:\\repo\\tools\\owns_gate.py.\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == ["D:\\repo\\tools\\owns_gate.py"]


# --- attempt 3: отбор строки по границе слова (блокер контрольного
# --- входа критика) + фоллбек + пины ограничений N2/N3 ---------------


# Сквозной вход критика ДОСЛОВНО: на Given-строке "owns" сидит ВНУТРИ
# имени файла И рядом стоят ВАЛИДНЫЕ абсолютные пути через запятую --
# прежний подстрочный перебор возвращал ИХ (пути read-only корзины
# "дано") и не доходил до настоящей owns-строки ниже.
_CRITIC_BLOCKER_PROMPT = (
    "DoD: тест зелёный, witness приложен.\n"
    "Дано: D:/x/tools/owns_gate.py, D:/x/tools/dispatch_gate.py, D:/x/CLAUDE.md\n"
    "owns (ABSOLUTE write paths): D:/x/tools/owns_gate.py\n"
    "Правь файлы."
)


def test_extract_owns_paths_given_line_with_owns_in_filename_does_not_hijack():
    # ВЕТКА КЛАССА, не экземпляр: ложный маркер + валидные пути на ОДНОЙ
    # строке. `_` -- словесный символ, поэтому "owns_gate.py" не даёт
    # `\bowns\b`; берётся настоящая owns-строка НИЖЕ.
    assert owns_gate.extract_owns_paths(_CRITIC_BLOCKER_PROMPT) == [
        "D:/x/tools/owns_gate.py"
    ]


def test_decide_given_line_with_owns_in_filename_writes_declared_owns_only(tmp_path):
    # Тот же блокер СКВОЗНЫМ decide(): в sidecar должен попасть ТОЛЬКО
    # объявленный путь записи, а не пути read-only корзины "дано"
    # (прежнее поведение писало в реестр ЛОЖНЫЙ owns -- сверка не просто
    # слепла, а врала).
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "builder",
            "prompt": _CRITIC_BLOCKER_PROMPT,
            "description": "sonnet: write",
        },
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None  # живых записей нет -- тишина

    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(written) == 1
    assert written[0]["owns"] == ["D:/x/tools/owns_gate.py"]
    assert "D:/x/tools/dispatch_gate.py" not in written[0]["owns"]
    assert "D:/x/CLAUDE.md" not in written[0]["owns"]


def test_extract_owns_paths_fallback_substring_marker_when_no_word_boundary_line():
    # ФОЛЛБЕК-ветка: `\bowns\b` не совпадает НИ НА ОДНОЙ строке (маркер
    # склеен словесными символами с обеих сторон) -- включается прежний
    # подстрочный перебор, пути берутся из этой самой строки
    # (сохранённая толерантность к кривым формам).
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "manifest_owns_блок; D:/repo/tools/a.py; D:/repo/tools/b.py\n"
    )
    assert owns_gate._OWNS_WORD_RE.search(prompt) is None  # предпосылка ветки
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_word_boundary_line_without_paths_no_fallback():
    # Строка ПО ГРАНИЦЕ СЛОВА нашлась, но путей не дала -> фоллбек НЕ
    # включается: [] уходит в диагностику пустого owns, а не откатывается
    # к ложным срабатываниям подстрочного маркера ниже/выше.
    prompt = (
        "owns: уточню позже\n"
        "Дано: D:/x/tools/owns_gate.py, D:/x/CLAUDE.md\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_leading_star_glob_is_stripped_known_limitation():
    # N2, ПИН ТЕКУЩЕГО ПОВЕДЕНИЯ (known limitation, поведение НЕ
    # менялось): ведущая `*` входит в класс мусорных ведущих символов
    # (он там ради markdown "**owns**:") и съедается стриппером. Глоб с
    # ведущей звездой -- вне нормы правила 11 ("ABSOLUTE write paths").
    assert owns_gate.extract_owns_paths("owns: */tools/*") == ["/tools/*"]


def test_strip_owns_marker_junk_50kb_paren_groups_completes_under_5s():
    # N3, ГРАНИЧНЫЙ ТЕСТ ВЕЛИЧИНЫ на РЕАЛИСТИЧНОМ потолке: срез мусора
    # квадратичен по числу скобочных групп (замер критика: 240К групп
    # ~3с). ~50КБ префикса из групп должны разбираться заведомо быстро.
    import time

    junk = "(x)" * 16667  # 50 001 символ
    assert len(junk) >= 50000
    prompt = "owns " + junk + ": D:/repo/tools/a.py"
    started = time.time()
    paths = owns_gate.extract_owns_paths(prompt)
    elapsed = time.time() - started
    assert paths == ["D:/repo/tools/a.py"]
    assert elapsed < 5.0


# ---------------------------------------------------------------------
# Сверка пересечения путей (правило 6а -- границы).
# ---------------------------------------------------------------------


def test_equal_paths_overlap():
    assert owns_gate.paths_overlap("D:\\x\\y.py", "D:\\x\\y.py") is True


def test_nested_directory_overlaps():
    assert owns_gate.paths_overlap("D:\\x\\y", "D:\\x") is True
    assert owns_gate.paths_overlap("D:\\x", "D:\\x\\y") is True


def test_glob_overlaps_both_directions():
    assert owns_gate.paths_overlap("D:\\x\\*.py", "D:\\x\\y.py") is True
    assert owns_gate.paths_overlap("D:\\x\\y.py", "D:\\x\\*.py") is True


def test_sibling_directories_common_name_prefix_do_not_overlap():
    # Граничный случай спеки, буквально: D:\ab vs D:\abc -- НЕ
    # пересечение (не голый substring-префикс, а по границе сегмента).
    assert owns_gate.paths_overlap("D:\\ab", "D:\\abc") is False
    assert owns_gate.paths_overlap("D:\\abc", "D:\\ab") is False


# ---------------------------------------------------------------------
# decide(): окно 24ч -- НА границе и ЗА ней (правило 6а).
# ---------------------------------------------------------------------


def test_window_on_boundary_still_live(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    boundary_ts = (now - timedelta(seconds=owns_gate.WINDOW_SECONDS)).strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, boundary_ts, "s-1", "D:\\repo", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "OWNS OVERLAP" in ctx


def test_window_beyond_boundary_is_stale(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    stale_ts = (now - timedelta(seconds=owns_gate.WINDOW_SECONDS + 1)).strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, stale_ts, "s-1", "D:\\repo", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None


# ---------------------------------------------------------------------
# F2: область сверки -- cwd, НЕ session_key (session_key -- метка).
# ---------------------------------------------------------------------


def test_scope_different_cwd_is_ignored(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, fresh_ts, "s-1", "D:\\OTHER_REPO", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    # Тот же session_key ("s-1"), но ДРУГОЙ cwd -- игнорируется: область
    # сверки -- репо (cwd), не сессия.
    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is None


def test_scope_same_cwd_different_session_key_warns_with_d0060_label(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    _write_registry_line(registry, fresh_ts, "s-OTHER", "D:\\repo", "sonnet: prior write", ["D:\\repo\\tools\\x.py"])

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "D-0060" in ctx


# ---------------------------------------------------------------------
# F4: дедупликация -- один новый путь против нескольких живых записей.
# ---------------------------------------------------------------------


def test_dedup_single_path_multiple_live_records_one_warn_line(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    for i in range(3):
        _write_registry_line(
            registry, fresh_ts, f"s-other-{i}", "D:\\repo", f"sonnet: prior write {i}",
            ["D:\\repo\\tools\\shared.py"],
        )

    payload = _writing_payload("D:\\repo\\tools\\shared.py", session_id="s-me", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    ctx = output["hookSpecificOutput"]["additionalContext"]
    # Одна строка WARN на этот путь, не три -- максимум 2 упоминания +
    # хвост "и ещё N" (F4).
    assert ctx.count("D:\\repo\\tools\\shared.py пересекается") == 1
    assert "и ещё 1" in ctx


# ---------------------------------------------------------------------
# B2: диагностика пустого owns -- маркер+write-индикатор без путей.
# ---------------------------------------------------------------------


def test_decide_blind_owns_warn_when_marker_present_but_no_paths_parsed(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "owns: непонятно что тут написано без путей.\n"
        "Правь файлы."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is not None
    ctx = output["hookSpecificOutput"]["additionalContext"]
    assert "слепа" in ctx
    assert not registry.exists()


def test_decide_true_readonly_no_marker_no_write_indicator_is_silent(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "scout", "prompt": "Найди файл и прочитай.", "description": "haiku: scout"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


# ---------------------------------------------------------------------
# read-only диспатч -- тишина и sidecar НЕ растёт.
# ---------------------------------------------------------------------


def test_readonly_dispatch_is_silent_and_sidecar_not_grown(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "scout", "prompt": "Найди файл и прочитай.", "description": "haiku: scout"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


# ---------------------------------------------------------------------
# Не-Task тул -- тишина.
# ---------------------------------------------------------------------


def test_non_task_tool_is_silent(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    payload = {"tool_name": "Bash", "tool_input": {"command": "echo owns: D:\\x"}}
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    assert not registry.exists()


# ---------------------------------------------------------------------
# sidecar отсутствует / битая строка -- fail-open.
# ---------------------------------------------------------------------


def test_missing_registry_file_fail_open(tmp_path):
    registry = tmp_path / "does_not_exist" / "owns_registry.jsonl"
    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 7, 28, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    # запись новой сессии всё равно должна дойти после fail-open чтения.
    assert registry.exists()


def test_malformed_registry_line_fail_open(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    registry.parent.mkdir(parents=True, exist_ok=True)
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    with registry.open("a", encoding="utf-8") as f:
        f.write("{not valid json\n")
        f.write(json.dumps({
            "ts": fresh_ts, "session_key": "s-1", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:\\repo\\tools\\x.py"],
        }) + "\n")

    payload = _writing_payload("D:\\repo\\tools\\x.py", session_id="s-1", cwd="D:\\repo")
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=now)
    assert exit_code == 0
    assert output is not None
    assert "OWNS OVERLAP" in output["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------
# F1: компакция sidecar на границе 500/501 строк.
# ---------------------------------------------------------------------


def test_registry_compaction_boundary_500_lines_appends(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    lines = [
        json.dumps({
            "ts": fresh_ts, "session_key": "s-1", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:\\x.py"],
        })
        for _ in range(owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES)
    ]
    registry.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # РОВНО 500 существующих строк -- НЕ строго больше порога -> обычный
    # append, не компакция.
    owns_gate._append_registry(registry, now, "s-2", "D:\\repo", "new write", ["D:\\y.py"])

    final_text = registry.read_text(encoding="utf-8")
    final_lines = [ln for ln in final_text.splitlines() if ln.strip()]
    assert len(final_lines) == owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES + 1
    # append (не перезапись/компакция): первая исходная строка осталась
    # байт-в-байт.
    assert final_lines[0] == lines[0]


def test_registry_compaction_boundary_501_lines_compacts(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 7, 28, 12, 0, 0)
    fresh_ts = now.strftime(owns_gate._TS_FORMAT)
    stale_ts = (now - timedelta(seconds=owns_gate.WINDOW_SECONDS + 1)).strftime(owns_gate._TS_FORMAT)

    live_lines = [
        json.dumps({
            "ts": fresh_ts, "session_key": "s-1", "cwd": "D:\\repo",
            "description": "d", "owns": ["D:\\x.py"],
        })
        for _ in range(owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES)
    ]
    stale_line = json.dumps({
        "ts": stale_ts, "session_key": "s-1", "cwd": "D:\\repo",
        "description": "stale", "owns": ["D:\\stale.py"],
    })
    # 500 живых + 1 протухшая = 501 существующих строк -- строго больше
    # порога -> компакция.
    registry.write_text("\n".join(live_lines + [stale_line]) + "\n", encoding="utf-8")

    owns_gate._append_registry(registry, now, "s-2", "D:\\repo", "new write", ["D:\\y.py"])

    final_text = registry.read_text(encoding="utf-8")
    final_lines = [ln for ln in final_text.splitlines() if ln.strip()]
    # Компакция отбросила протухшую строку: 500 живых + 1 новая = 501,
    # а НЕ 502 (что дал бы наивный append без компакции) -- разница
    # доказывает, что компакция действительно сработала на границе 501.
    assert len(final_lines) == owns_gate.REGISTRY_COMPACT_THRESHOLD_LINES + 1
    assert "stale.py" not in final_text


# ---------------------------------------------------------------------
# Адверсариальная батарея stdin (правило 6а/11 -- границы + main()).
# ---------------------------------------------------------------------


def test_decide_payload_not_dict_fail_open():
    exit_code, output = owns_gate.decide(["not", "a", "dict"])
    assert exit_code == 0
    assert output is None


def test_echo_json_malformed_json_fails_open():
    result = _run_hook("{not valid json", text=True)
    assert result.returncode == 0
    assert result.stdout == ""


def test_echo_json_empty_stdin_fails_open():
    result = _run_hook(b"")
    assert result.returncode == 0


def test_echo_json_non_utf8_bytes_fail_open():
    result = _run_hook(b"\xff\xfe\x00\x01not json either")
    assert result.returncode == 0


def test_echo_json_huge_owns_string_completes_quickly(tmp_path):
    import time

    huge_owns = "D:\\repo\\tools\\huge_" + ("x" * (1024 * 1024)) + ".py"
    payload = _writing_payload(huge_owns, session_id="s-huge", cwd=str(tmp_path))
    started = time.time()
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    elapsed = time.time() - started
    assert result.returncode == 0
    assert elapsed < 5.0


def test_echo_json_valid_writing_dispatch_no_prior_records_is_silent(tmp_path):
    payload = _writing_payload(
        "D:\\repo\\tools\\brand_new_path_for_test.py", session_id="s-echo-1", cwd=str(tmp_path)
    )
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "logs" / "owns_registry.jsonl").exists()
