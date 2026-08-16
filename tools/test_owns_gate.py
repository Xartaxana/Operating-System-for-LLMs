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
граничный тест величины N3 (мусорный префикс ~50КБ скобочных групп не
деградирует на порядок -- сторож катастрофы, не SLO задержки, F-60,
t-453: было "< 5с", потолок поднят до WALLCLOCK_CATASTROPHE_CEILING)."""

import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import owns_gate  # noqa: E402
from wallclock_guard import WALLCLOCK_CATASTROPHE_CEILING  # noqa: E402

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


# ---------------------------------------------------------------------
# F-59 подкласс 3 (2026-08-10, T2): backtick-обёрнутые пути, пути с
# пробелами в кавычках/backtick в многострочном продолжении, и
# регресс-пин на markdown-жирный маркер + буллет-блок ниже (спека
# требовала инвертировать пин "markdown-жирное -> []" -- эмпирически
# эта КОНКРЕТНАЯ форма УЖЕ разбиралась верно до правки, см. докстринг
# модуля "F-59 ПОДКЛАСС 3"; ниже -- регресс-пин, ЛОКИРУЮЩИЙ это, плюс
# фактически найденный и зафиксированный баг того же класса -- backtick).
# ---------------------------------------------------------------------


def test_f59_backtick_wrapped_path_single_line_recognized():
    # Однострочная форма: путь в одинарных гравис-кавычках (markdown
    # "код-шрифт") -- ДО фикса backtick не входил в _EDGE_TRIM_CHARS,
    # `_WINDOWS_ABS_RE` не матчил токен, начинающийся с "`".
    prompt = "owns: `D:/repo/tools/a.py`, `D:/repo/tools/b.py`"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_f59_backtick_wrapped_path_continuation_recognized():
    # Многострочная форма (буллет + backtick) -- та же правка
    # (_EDGE_TRIM_CHARS) закрывает continuation через общий _clean_token.
    prompt = "owns:\n- `D:/repo/tools/a.py`\n- `D:/repo/tools/b.py`\n"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_f59_quoted_path_with_space_continuation_preserved():
    # T5 краевая форма: путь с пробелом в двойных кавычках в
    # продолжении -- ДО фикса _first_token_path резал по первому
    # пробелу ("D:/my), теряя хвост пути.
    prompt = 'owns:\n- "D:/repo/my folder/a.py"\n'
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/my folder/a.py"]


def test_f59_backtick_path_with_space_continuation_preserved():
    prompt = "owns:\n- `D:/repo/my folder/a.py`\n"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/my folder/a.py"]


def test_f59_unclosed_quote_continuation_falls_back_to_whitespace_split():
    # Незакрытая кавычка -- _first_raw_token не находит парный символ,
    # фоллбек на прежнее поведение (разбиение по пробелу); путь без
    # пробела внутри распознаётся как раньше, кавычка обрезается
    # _clean_token с ОДНОЙ стороны (та же логика edge-trim).
    prompt = 'owns:\n- "D:/repo/tools/a.py\n'
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/a.py"]


def test_f59_pin_v_bold_marker_with_bulleted_continuation_below_parses_paths():
    # Пин (в) спеки, реконструкция живого образца -- маркер
    # "**owns (АБСОЛЮТНЫЕ пути записи):**" ОДНОЙ строкой (жирный,
    # скобочное уточнение внутри "**") + пути реального репозитория
    # буллетами НИЖЕ -- ОБЯЗАН разбираться в точный список. РЕГРЕСС-ПИН
    # (не новый фикс, см. докстринг модуля "F-59 ПОДКЛАСС 3" --
    # эмпирически эта форма уже работала до правки этой задачи).
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "**owns (АБСОЛЮТНЫЕ пути записи):**\n"
        "- D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\dispatch_gate.py\n"
        "- D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\owns_gate.py\n"
        "- D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\test_dispatch_gate.py\n"
        "- D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\test_owns_gate.py\n"
        "Правь файлы по спеке."
    )
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\dispatch_gate.py",
        "D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\owns_gate.py",
        "D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\test_dispatch_gate.py",
        "D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\test_owns_gate.py",
    ]


def test_f59_pin_v_decide_bold_marker_writes_declared_paths_to_sidecar(tmp_path):
    # Тот же пин СКВОЗНЫМ decide() -- в sidecar попадает ОБЪЯВЛЕННЫЙ
    # список путей манифеста (в), не read-only-предположение.
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: критерии приёмки — тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "**owns (АБСОЛЮТНЫЕ пути записи):**\n"
        "- D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\dispatch_gate.py\n"
        "- D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\owns_gate.py\n"
        "Правь файлы по спеке."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 8, 10, 12, 0, 0))
    assert exit_code == 0
    assert output is None
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == [
        "D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\dispatch_gate.py",
        "D:\\Improving_AI\\Operating-System-for-LLMs\\tools\\owns_gate.py",
    ]


def test_f59_pin_v_two_bold_marker_manifests_with_overlap_detected(tmp_path):
    # T4: два синтетических манифеста markdown-жирной формы с
    # ПЕРЕСЕКАЮЩИМСЯ путём -- OVERLAP обязан сработать (доказывает, что
    # разобранные из markdown-формы пути реально участвуют в сверке,
    # не только извлекаются).
    registry = tmp_path / "owns_registry.jsonl"
    now = datetime(2026, 8, 10, 12, 0, 0)
    prompt1 = (
        "DoD: witness приложен. Дано: репо целиком.\n"
        "**owns (ABSOLUTE write paths):**\n"
        "- D:/repo/tools/shared.py\n"
        "Правь файлы."
    )
    payload1 = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt1, "description": "sonnet: write A"},
        "session_id": "s-A",
        "cwd": "D:\\repo",
    }
    exit_code1, output1 = owns_gate.decide(payload1, registry_path=registry, now=now)
    assert exit_code1 == 0
    assert output1 is None

    prompt2 = (
        "DoD: witness приложен. Дано: репо целиком.\n"
        "**owns (ABSOLUTE write paths):**\n"
        "- D:/repo/tools/shared.py\n"
        "Правь файлы."
    )
    payload2 = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt2, "description": "sonnet: write B"},
        "session_id": "s-B",
        "cwd": "D:\\repo",
    }
    exit_code2, output2 = owns_gate.decide(payload2, registry_path=registry, now=now)
    assert exit_code2 == 0
    assert output2 is not None
    assert "OWNS OVERLAP" in output2["hookSpecificOutput"]["additionalContext"]


def test_f59_owns_bare_marker_without_any_paths_stays_empty():
    # T5 краевая форма: "owns: без путей вовсе" -- маркер есть, тела
    # нет вовсе (конец промпта сразу после маркера) -- пустой список,
    # уходит в диагностику B2 на уровне decide(), не крашится.
    assert owns_gate.extract_owns_paths("**owns:**\n") == []
    assert owns_gate.extract_owns_paths("owns:") == []


def test_f59_fenced_code_block_marker_not_specially_parsed_documented_non_goal():
    # T5 краевая форма: маркер в fenced-блоке (тройной backtick) --
    # ЯВНЫЙ НЕ-ЦЕЛЬ (см. докстринг модуля "F-59 ПОДКЛАСС 3",
    # "ФЕНСИРОВАННЫЙ БЛОК"): ограничители "```" сами не path-подобны,
    # блок продолжения обрывается на них -- безопасный пустой результат,
    # не попытка распарсить содержимое фенса как декларацию.
    prompt = "**owns (ABSOLUTE write paths):**\n```\nD:/repo/tools/a.py\n```\n"
    assert owns_gate.extract_owns_paths(prompt) == []


# ---------------------------------------------------------------------
# F6 (t-384, критик, 2026-08-10): is_path_token() больше не засчитывает
# ГОЛОЕ "*" (markdown-decoration) как путь -- живой sidecar owns_gate
# зарегистрировал прозу с "**" как owns-путь на диспатче того же
# ревью. Реконструкция (см. handoff отчёта): строка "owns: обратная
# сторона.** Пишущий диспатч" -- ДО фикса is_path_token() матчила её
# ЦЕЛИКОМ как ОДИН "путь" (split по `;`/`,`/переводу строки не режет
# по пробелу, весь текст -- один токен; "*" внутри "**" засчитывался
# голой проверкой `"*" in tok`).
# ---------------------------------------------------------------------


def test_f6_markdown_bold_decoration_no_slash_not_a_path_single_line():
    prompt = "owns: обратная сторона.** Пишущий диспатч без реального пути."
    assert owns_gate.extract_owns_paths(prompt) == []


def test_f6_is_path_token_rejects_bare_star_without_slash_direct():
    # Прямая проверка регекса (симметрично _is_continuation_path_token,
    # которая эту строгость уже несла ДО F6, см. докстринг "F6").
    assert owns_gate.is_path_token("**Пишущий") is False
    assert owns_gate.is_path_token("обратная сторона.**") is False
    # Позитивный контроль (правило 6 гигиены): глоб СО слэшем по-прежнему
    # путь-подобен -- негатив выше не доказывал бы отсутствие функции.
    assert owns_gate.is_path_token("tools/*.py") is True
    assert owns_gate.is_path_token("D:/repo/tools/a.py") is True


def test_f6_decide_prose_with_bare_star_does_not_register_in_sidecar(tmp_path):
    # Сквозным decide(): прозаический диспатч (owns-слово + write-
    # индикатор "правь", БЕЗ реального пути) больше не пишет
    # ложную "прозу-как-путь" запись в sidecar -- уходит в диагностику
    # B2 (owns объявлен, путей не разобрано), sidecar не растёт.
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "owns: обратная сторона.** Пишущий диспатч без реального пути.\n"
        "Правь файлы."
    )
    payload = {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "builder", "prompt": prompt, "description": "sonnet: write"},
        "session_id": "s-1",
        "cwd": "D:\\repo",
    }
    exit_code, output = owns_gate.decide(payload, registry_path=registry, now=datetime(2026, 8, 10, 12, 0, 0))
    assert exit_code == 0
    assert output is not None
    assert "слепа" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


def test_f6_is_continuation_path_token_now_delegates_to_shared_predicate():
    # D-0043: is_path_token() и _is_continuation_path_token() теперь
    # ОБА делегируют dispatch_gate.is_path_like_token() -- поведение
    # идентично на одних и тех же формах (регресс-пин единства).
    for tok in ("**Внимание**:", "tools/test_*.py", "D:/repo/a.py", "обратная.**", "/repo/a.py"):
        assert owns_gate.is_path_token(tok) == owns_gate._is_continuation_path_token(tok), tok


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
    assert owns_gate.OWNS_WORD_RE.search(prompt) is None  # предпосылка ветки
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


# --- П3 (батч мелочей после калибровки №6): многострочный owns-блок --


def test_extract_owns_paths_multiline_bullet_block():
    prompt = (
        "Дано: репо целиком.\n"
        "owns:\n"
        "- D:/repo/tools/a.py\n"
        "- D:/repo/tools/b.py\n"
        "Правь файлы."
    )
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_multiline_star_and_middot_bullets():
    prompt = "owns:\n* D:/a.py\n\u2022 D:/b.py\n"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/a.py", "D:/b.py"]


def test_extract_owns_paths_multiline_bare_path_lines_no_bullets():
    prompt = "owns:\nD:/repo/tools/a.py\nD:/repo/tools/b.py\n"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_extract_owns_paths_marker_line_with_paths_takes_priority_over_block_below():
    # Строка маркера УЖЕ дала путь -- блок ниже НЕ подмешивается
    # (обязательный край спеки, не меняет семантику принятых диспатчей).
    prompt = "owns: D:/repo/tools/only_this.py\n- D:/repo/tools/should_not_appear.py\n"
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/only_this.py"]


def test_extract_owns_paths_empty_line_immediately_after_marker_ends_block():
    prompt = "owns:\n\n- D:/repo/tools/a.py\n"
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_non_goals_section_right_after_marker_ends_block():
    prompt = (
        "owns:\n"
        "non-goals: toolkit/**\n"
        "- D:/repo/tools/a.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_handoff_section_right_after_marker_ends_block():
    prompt = "owns:\nhandoff: см. отчёт\n- D:/repo/tools/a.py\n"
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_given_ru_section_right_after_marker_ends_block():
    prompt = "owns:\nдано: репо целиком\n- D:/repo/tools/a.py\n"
    assert owns_gate.extract_owns_paths(prompt) == []


def test_extract_owns_paths_continuation_stops_at_first_non_path_line():
    prompt = (
        "owns:\n"
        "- D:/repo/tools/a.py\n"
        "прозаическая строка без пути\n"
        "- D:/repo/tools/should_not_appear.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/tools/a.py"]


def test_decide_multiline_owns_block_writes_declared_paths_to_sidecar(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "owns:\n"
        "- D:/repo/tools/a.py\n"
        "- D:/repo/tools/b.py\n"
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
    assert output is None
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == ["D:/repo/tools/a.py", "D:/repo/tools/b.py"]


def test_extract_owns_paths_multiline_block_via_fallback_pass():
    # Фоллбек-проход (маркер БЕЗ границы слова) тоже получает
    # многострочную поддержку -- тот же helper переиспользован.
    prompt = (
        "manifest_owns_блок\n"
        "- D:/repo/tools/a.py\n"
        "- D:/repo/tools/b.py\n"
    )
    assert owns_gate.OWNS_WORD_RE.search(prompt) is None
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


# --- П3: предел 40 строк продолжения (правило 6а -- обе стороны) -----


def test_extract_owns_paths_continuation_exactly_40_lines_returns_all():
    lines = ["owns:"] + [f"- D:/repo/tools/f{i}.py" for i in range(40)]
    prompt = "\n".join(lines) + "\n"
    result = owns_gate.extract_owns_paths(prompt)
    assert len(result) == 40
    assert result[0] == "D:/repo/tools/f0.py"
    assert result[-1] == "D:/repo/tools/f39.py"


def test_extract_owns_paths_continuation_41_lines_hits_limit_returns_empty():
    lines = ["owns:"] + [f"- D:/repo/tools/f{i}.py" for i in range(41)]
    prompt = "\n".join(lines) + "\n"
    # Упор в предел (41-я строка ЕЩЁ продолжала бы блок) -- пустой
    # список, не тихое усечение до первых 40.
    assert owns_gate.extract_owns_paths(prompt) == []


def test_decide_continuation_limit_hit_gives_blind_owns_warn(tmp_path):
    registry = tmp_path / "owns_registry.jsonl"
    lines = ["owns:"] + [f"- D:/repo/tools/f{i}.py" for i in range(41)]
    prompt = (
        "DoD: тест зелёный, witness приложен.\nДано: репо целиком.\n"
        + "\n".join(lines) + "\nПравь файлы."
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
    assert "слепа" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


# --- Пересдача (блокер 2, критик, живая проба 2026-08-05) -----------


def test_p3_regression_prose_owns_word_does_not_hijack_declaration_below():
    # ОБЯЗАТЕЛЬНЫЙ ПИН, вход критика ДОСЛОВНО: "owns" -- обычное слово
    # ПОСРЕДИ прозы (не декларация), затем строка, стартующая с
    # "D:/..." (тоже НЕ декларация, просто бытовая заметка), затем
    # ПУСТАЯ строка, затем НАСТОЯЩАЯ декларация -- паритет с HEAD:
    # РОВНО ['D:/repo/real_target.py'], не хайджек прозы.
    prompt = (
        "Задача: правка гейта.\n"
        "Не выходи за owns этой задачи.\n"
        "D:/repo/readme.md -- прочитать перед началом\n"
        "\n"
        "owns: D:/repo/real_target.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == ["D:/repo/real_target.py"]


def test_p3_decide_regression_prose_owns_word_sidecar_gets_real_target(tmp_path):
    # Тот же вход СКВОЗНЫМ decide(): в sidecar должен попасть НАСТОЯЩИЙ
    # пишущий путь, а не прозаическая строка read-only заметки.
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\n"
        "Дано: репо целиком.\n"
        "Задача: правка гейта.\n"
        "Не выходи за owns этой задачи.\n"
        "D:/repo/readme.md -- прочитать перед началом\n"
        "\n"
        "owns: D:/repo/real_target.py\n"
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
    written = [json.loads(ln) for ln in registry.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert written[0]["owns"] == ["D:/repo/real_target.py"]


def test_p3_prose_owns_word_mid_sentence_alone_gives_blind_warn_not_silence(tmp_path):
    # Если НИКАКОЙ настоящей декларации нигде дальше в промпте нет,
    # прозаическое "owns" по-прежнему НЕ должно тихо хайджекать чужой
    # read-only путь -- итог [] уходит в диагностику пустого owns
    # (write-индикатор здесь -- сам "owns"-marker через WRITE_INDICATORS_RE).
    registry = tmp_path / "owns_registry.jsonl"
    prompt = (
        "DoD: тест зелёный, witness приложен.\nДано: репо целиком.\n"
        "Не выходи за owns этой задачи.\n"
        "D:/repo/readme.md -- прочитать перед началом\n"
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
    assert "слепа" in output["hookSpecificOutput"]["additionalContext"]
    assert not registry.exists()


# --- Пересдача (не-блокеры (а), той же пробой) -----------------------


def test_p3_markdown_bold_junk_line_under_marker_does_not_pollute_block():
    prompt = (
        "owns:\n"
        "**Внимание**: пиши только сюда\n"
        "- D:/repo/tools/a.py\n"
    )
    # Первая строка блока -- мусор (не путь) -> блок обрывается на ней,
    # ничего не собрано (та же строгая семантика "первая непарсящаяся
    # строка -- конец блока").
    assert owns_gate.extract_owns_paths(prompt) == []


def test_p3_dod_line_under_marker_does_not_get_swallowed_whole():
    prompt = (
        "owns:\n"
        "DoD: прогнать pytest tools/test_*.py -q\n"
        "- D:/repo/tools/a.py\n"
    )
    assert owns_gate.extract_owns_paths(prompt) == []


def test_p3_numbered_list_recognized_as_bullet_form():
    prompt = "owns:\n1. D:/repo/tools/a.py\n2) D:/repo/tools/b.py\n"
    assert owns_gate.extract_owns_paths(prompt) == [
        "D:/repo/tools/a.py",
        "D:/repo/tools/b.py",
    ]


def test_p3_prose_tail_after_bullet_path_is_cut_not_swallowed_whole():
    prompt = "owns:\n- D:/repo/tools/a.py -- главный файл\n"
    paths = owns_gate.extract_owns_paths(prompt)
    assert paths == ["D:/repo/tools/a.py"]
    # paths_overlap теперь распознаёт ту же строку как настоящий путь
    # (регресс критика: раньше вся строка целиком не совпадала).
    assert owns_gate.paths_overlap(paths[0], "D:/repo/tools/a.py") is True


def test_p3_is_continuation_path_token_rejects_bare_star_without_slash():
    # Юнит на ужесточённую проверку: "*" без слэша -- НЕ путь-подобный
    # токен продолжения (markdown "**...**:" не должен матчить).
    assert owns_gate._is_continuation_path_token("**Внимание**:") is False
    assert owns_gate._is_continuation_path_token("tools/test_*.py") is True
    assert owns_gate._is_continuation_path_token("D:/repo/a.py") is True


def test_strip_owns_marker_junk_50kb_paren_groups_no_catastrophic_blowup():
    # N3, ГРАНИЧНЫЙ ТЕСТ ВЕЛИЧИНЫ на РЕАЛИСТИЧНОМ потолке: срез мусора
    # квадратичен по числу скобочных групп (замер критика: 240К групп
    # ~3с до фикса -- катастрофа, которую ловит этот сторож). ~50КБ
    # префикса из групп должны разбираться заведомо быстро.
    #
    # F-60 (класс B): сторож катастрофы, не SLO задержки. Здоровое время
    # ~0.03с (замер этого прогона, --durations, t-453); катастрофа --
    # 240К групп ~3с до фикса (см. выше). СУЖЕНИЕ ПОКРЫТИЯ (было -> стало):
    # раньше тест утверждал "укладывается в 5 секунд"; теперь --
    # "предмет не деградировал на порядок". time.monotonic() вместо
    # time.time() (Ф10) -- немонотонные часы дают отрицательный elapsed
    # при переводе системного времени назад, и сторож молча зеленеет.
    import time

    junk = "(x)" * 16667  # 50 001 символ
    assert len(junk) >= 50000
    prompt = "owns " + junk + ": D:/repo/tools/a.py"
    started = time.monotonic()
    paths = owns_gate.extract_owns_paths(prompt)
    elapsed = time.monotonic() - started
    assert paths == ["D:/repo/tools/a.py"]
    assert elapsed < WALLCLOCK_CATASTROPHE_CEILING, (
        f"took {elapsed:.2f}s -- сторож стенных часов: проверь загрузку "
        "машины прежде, чем считать это дефектом (F-60)"
    )


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
    started = time.monotonic()
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    elapsed = time.monotonic() - started
    assert result.returncode == 0
    # F-60 (класс B): сторож катастрофы, не SLO задержки -- ЭТО тот самый
    # тест, на котором F-60 была замечена (0.25с здоровых в изоляции,
    # 11.8с под сторонней CPU-нагрузкой). Здоровое время этого прогона --
    # 0.15с (--durations, t-453). СУЖЕНИЕ ПОКРЫТИЯ (было -> стало): раньше
    # тест утверждал "укладывается в 5 секунд"; теперь -- "предмет не
    # деградировал на порядок". time.monotonic() вместо time.time() (Ф10)
    # -- немонотонные часы дают отрицательный elapsed при переводе
    # системного времени назад, и сторож молча зеленеет.
    assert elapsed < WALLCLOCK_CATASTROPHE_CEILING, (
        f"took {elapsed:.2f}s -- сторож стенных часов: проверь загрузку "
        "машины прежде, чем считать это дефектом (F-60)"
    )


def test_echo_json_valid_writing_dispatch_no_prior_records_is_silent(tmp_path):
    payload = _writing_payload(
        "D:\\repo\\tools\\brand_new_path_for_test.py", session_id="s-echo-1", cwd=str(tmp_path)
    )
    result = _run_hook(json.dumps(payload).encode("utf-8"), cwd=tmp_path)
    assert result.returncode == 0
    assert (tmp_path / "logs" / "owns_registry.jsonl").exists()


# ---------------------------------------------------------------------
# Батч 07-28 п.(б): пин единства источника OWNS_WORD_RE (D-0043) --
# owns_gate.py больше НЕ несёт свою локальную копию _OWNS_WORD_RE, а
# импортирует OWNS_WORD_RE из dispatch_gate.py (тот же объект, который
# теперь использует и блокирующая проверка 2 dispatch_gate'а).
# ---------------------------------------------------------------------


def test_owns_gate_source_has_no_local_owns_word_re_compile():
    # Критик t-336, F2: прежний тест сравнивал `owns_gate.OWNS_WORD_RE is
    # dispatch_gate.OWNS_WORD_RE` -- ВАКУУМНАЯ проверка, т.к. модуль `re`
    # КЭШИРУЕТ re.compile() по паре (pattern, flags): параллельная
    # re.compile(r"\bowns\b", re.IGNORECASE) в owns_gate.py, безо всякого
    # импорта, дала бы ТОТ ЖЕ объект и прошла бы is-ассерт (проба критика:
    # True/True из кэша, False после явного re.purge()) -- тест не мог
    # отличить "импортирован" от "случайно совпал по кэшу". ФИКС: проверка
    # по ИСТОЧНИКУ -- читаем текст файла owns_gate.py и убеждаемся, что он
    # НЕ содержит СВОЕЙ компиляции этого паттерна, плюс позитивный
    # контроль -- dispatch_gate.py ЭТУ компиляцию несёт (иначе negative
    # был бы бессмысленным по правилу 6 command hygiene: негатив без
    # позитивного контроля той же формы не доказывает отсутствие).
    needle = 're.compile(r"\\bowns\\b"'
    tools_dir = Path(__file__).resolve().parent
    dispatch_gate_src = (tools_dir / "dispatch_gate.py").read_text(encoding="utf-8")
    owns_gate_src = (tools_dir / "owns_gate.py").read_text(encoding="utf-8")

    assert needle in dispatch_gate_src  # позитивный контроль формы поиска
    assert needle not in owns_gate_src  # owns_gate больше не несёт своей копии
