"""Юнит-смоки tools/tier_echo.py (SubagentStop-хук, измеряет
ФАКТИЧЕСКУЮ модель(и) завершившегося субагента из его jsonl-транскрипта
-- ответ на инцидент прогона №15, см. докстринг tools/tier_echo.py).

Покрывает DoD спеки этой задачи буквально:
 - валидный payload + транскрипт с одной моделью;
 - транскрипт с несколькими моделями (порядок вывода = порядок первого
   появления в файле);
 - MISMATCH-ветка (запрошен fable через description, измерен opus) и
   совпадение (запрошен opus, измерен opus -- без флага);
 - payload без нужных полей (agent_transcript_path отсутствует/пусто/
   не строка) -> тихий exit 0;
 - транскрипт отсутствует -> тихий exit 0;
 - битые jsonl-строки среди валидных -> не падает, считает валидные;
 - пустой транскрипт -> тихий exit 0;
 - model не-строка -> ход не считается, не падает;
 - граница формата префикса description: без двоеточия / "opus2:"
   (не ярусное слово ровно) -> флага нет.

Стиль -- по образцу tools/test_dod_gate.py: чистая логика (build_line/
count_models/_extract_*) юнит-тестами напрямую + subprocess-смок всего
хука через stdin, capture_output, encoding="utf-8"."""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tier_echo  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "tier_echo.py"


def _run_hook(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _write_transcript(tmp_path: Path, name: str, lines) -> Path:
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(line) if not isinstance(line, str) else line for line in lines) + "\n",
        encoding="utf-8",
    )
    return path


def _assistant_line(model):
    return {"type": "assistant", "message": {"model": model}}


def _stop_payload(transcript_path, description=None) -> dict:
    payload = {
        "session_id": "sess-1",
        "cwd": ".",
        "hook_event_name": "SubagentStop",
        "agent_id": "agent-1",
        "agent_type": "builder",
        "agent_transcript_path": str(transcript_path),
        "stop_hook_active": False,
    }
    if description is not None:
        payload["description"] = description
    return payload


# ---------------------------------------------------------------------
# _extract_agent_transcript_path -- pure logic
# ---------------------------------------------------------------------


def test_extract_agent_transcript_path_present():
    assert tier_echo._extract_agent_transcript_path({"agent_transcript_path": "/x/y.jsonl"}) == "/x/y.jsonl"


def test_extract_agent_transcript_path_missing():
    assert tier_echo._extract_agent_transcript_path({}) is None


def test_extract_agent_transcript_path_empty_string():
    assert tier_echo._extract_agent_transcript_path({"agent_transcript_path": ""}) is None


def test_extract_agent_transcript_path_not_a_string():
    assert tier_echo._extract_agent_transcript_path({"agent_transcript_path": 123}) is None


# ---------------------------------------------------------------------
# _extract_declared_tier -- pure logic, включая граничные форматы
# ---------------------------------------------------------------------


def test_extract_declared_tier_known_word():
    assert tier_echo._extract_declared_tier({"description": "opus: review the diff"}) == "opus"


def test_extract_declared_tier_missing_field():
    assert tier_echo._extract_declared_tier({}) is None


def test_extract_declared_tier_no_colon_is_undeterminable():
    # Граница: description без двоеточия -- недетерминируемо, None.
    assert tier_echo._extract_declared_tier({"description": "opus review the diff"}) is None


def test_extract_declared_tier_non_tier_word_prefix():
    # Граница: "opus2" -- НЕ ярусное слово ровно, недетерминируемо.
    assert tier_echo._extract_declared_tier({"description": "opus2: review the diff"}) is None


def test_extract_declared_tier_case_insensitive_and_stripped():
    assert tier_echo._extract_declared_tier({"description": " Fable :  do the plan"}) == "fable"


def test_extract_declared_tier_not_a_string():
    assert tier_echo._extract_declared_tier({"description": 42}) is None


# ---------------------------------------------------------------------
# count_models / build_line -- pure logic
# ---------------------------------------------------------------------


def test_count_models_single():
    assert tier_echo.count_models(["claude-opus-4-8", "claude-opus-4-8"]) == {"claude-opus-4-8": 2}


def test_count_models_preserves_first_seen_order():
    counts = tier_echo.count_models(["claude-sonnet-5", "claude-opus-4-8", "claude-sonnet-5"])
    assert list(counts.items()) == [("claude-sonnet-5", 2), ("claude-opus-4-8", 1)]


def test_build_line_single_model_no_declared():
    line = tier_echo.build_line({"claude-opus-4-8": 3}, None)
    assert line == "TIER ECHO (measured): claude-opus-4-8=3"


def test_build_line_multiple_models_order():
    line = tier_echo.build_line({"claude-sonnet-5": 2, "claude-opus-4-8": 1}, None)
    assert line == "TIER ECHO (measured): claude-sonnet-5=2, claude-opus-4-8=1"


def test_build_line_mismatch_flag_when_declared_not_substring_of_any_measured():
    line = tier_echo.build_line({"claude-opus-4-8": 5}, "fable")
    assert line == "TIER ECHO (measured): claude-opus-4-8=5 MISMATCH vs declared 'fable'"


def test_build_line_no_mismatch_flag_when_declared_matches():
    line = tier_echo.build_line({"claude-opus-4-8": 5}, "opus")
    assert line == "TIER ECHO (measured): claude-opus-4-8=5"


def test_build_line_no_mismatch_flag_when_declared_matches_one_of_several():
    # Совпадение хотя бы одной измеренной модели -- флага нет, даже
    # если в счёте есть и другие модели.
    line = tier_echo.build_line({"claude-haiku-4-5": 1, "claude-opus-4-8": 4}, "opus")
    assert line == "TIER ECHO (measured): claude-haiku-4-5=1, claude-opus-4-8=4"


def test_build_line_no_declared_never_appends_flag():
    line = tier_echo.build_line({"claude-opus-4-8": 1}, None)
    assert "MISMATCH" not in line


def test_build_line_non_ascii_model_sanitized_to_ascii():
    # Критик attempt 2, п.2в: не-ASCII в имени модели (кириллица) не
    # должно попасть в вывод как есть -- _ascii_sanitize заменяет
    # не-ASCII байты на "?", строка остаётся чистым ASCII.
    line = tier_echo.build_line({"клод-опус": 2}, None)
    assert line == "TIER ECHO (measured): ????-????=2"
    assert line.isascii()


def test_build_line_non_ascii_declared_tier_sanitized_in_mismatch_suffix():
    line = tier_echo.build_line({"claude-opus-4-8": 1}, "фейбл")
    assert "MISMATCH vs declared '?????'" in line
    assert line.isascii()


# ---------------------------------------------------------------------
# iter_transcript_models -- pure logic, файловый ввод
# ---------------------------------------------------------------------


def test_iter_transcript_models_single_model(tmp_path):
    path = _write_transcript(tmp_path, "t1.jsonl", [_assistant_line("claude-opus-4-8")])
    assert list(tier_echo.iter_transcript_models(str(path))) == ["claude-opus-4-8"]


def test_iter_transcript_models_multiple_models_order(tmp_path):
    path = _write_transcript(
        tmp_path,
        "t2.jsonl",
        [
            _assistant_line("claude-sonnet-5"),
            {"type": "user", "message": {}},
            _assistant_line("claude-opus-4-8"),
            _assistant_line("claude-sonnet-5"),
        ],
    )
    assert list(tier_echo.iter_transcript_models(str(path))) == [
        "claude-sonnet-5",
        "claude-opus-4-8",
        "claude-sonnet-5",
    ]


def test_iter_transcript_models_skips_malformed_lines(tmp_path):
    path = _write_transcript(
        tmp_path,
        "t3.jsonl",
        [
            _assistant_line("claude-opus-4-8"),
            "{not valid json",
            _assistant_line("claude-opus-4-8"),
        ],
    )
    assert list(tier_echo.iter_transcript_models(str(path))) == [
        "claude-opus-4-8",
        "claude-opus-4-8",
    ]


def test_iter_transcript_models_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    assert list(tier_echo.iter_transcript_models(str(path))) == []


def test_iter_transcript_models_model_not_a_string_skipped(tmp_path):
    path = _write_transcript(
        tmp_path,
        "t4.jsonl",
        [
            {"type": "assistant", "message": {"model": 123}},
            {"type": "assistant", "message": {"model": None}},
            {"type": "assistant", "message": {}},
            _assistant_line("claude-opus-4-8"),
        ],
    )
    assert list(tier_echo.iter_transcript_models(str(path))) == ["claude-opus-4-8"]


def test_iter_transcript_models_skips_synthetic_among_normal(tmp_path):
    # Критик attempt 2, п.1/2а: "<synthetic>" (харнесс stop-sequence-
    # строка, tools/usage_report.py:317/401) не должна попадать в
    # список моделей -- нормальная модель по-прежнему считается.
    path = _write_transcript(
        tmp_path,
        "t5.jsonl",
        [
            _assistant_line("claude-opus-4-8"),
            {"type": "assistant", "message": {"model": "<synthetic>"}},
            _assistant_line("claude-opus-4-8"),
        ],
    )
    assert list(tier_echo.iter_transcript_models(str(path))) == [
        "claude-opus-4-8",
        "claude-opus-4-8",
    ]


def test_iter_transcript_models_only_synthetic_yields_nothing(tmp_path):
    # Критик attempt 2, п.2б: транскрипт ЦЕЛИКОМ из synthetic-строк --
    # контракт iter_transcript_models() зафиксирован здесь: пустой
    # список ходов (та же трактовка, что "нет assistant-строк вовсе"),
    # main() на пустом counts выходит тихо (см. subprocess-тест ниже).
    path = _write_transcript(
        tmp_path,
        "t6.jsonl",
        [
            {"type": "assistant", "message": {"model": "<synthetic>"}},
            {"type": "assistant", "message": {"model": "<synthetic>"}},
        ],
    )
    assert list(tier_echo.iter_transcript_models(str(path))) == []


def test_iter_transcript_models_non_ascii_model_passthrough(tmp_path):
    # Не-ASCII в message.model сам iter_transcript_models() не
    # фильтрует и не портит -- ASCII-санитайзер применяется позже, в
    # build_line() (см. test_build_line_non_ascii_model_sanitized и
    # test_echo_non_ascii_model_ascii_output ниже).
    path = _write_transcript(tmp_path, "t7.jsonl", [_assistant_line("клод-опус")])
    assert list(tier_echo.iter_transcript_models(str(path))) == ["клод-опус"]


def test_iter_transcript_models_invalid_utf8_bytes_in_file_no_crash(tmp_path):
    # Критик attempt 2, п.2г: НЕвалидные UTF-8 БАЙТЫ в самом файле
    # транскрипта (не stdin) -- errors="replace" не роняет чтение;
    # строка с битыми байтами становится невалидным JSON и просто
    # пропускается (как любая другая битая jsonl-строка), валидные
    # строки вокруг неё считаются нормально.
    path = tmp_path / "t8.jsonl"
    good_line_1 = json.dumps(_assistant_line("claude-opus-4-8")).encode("utf-8")
    bad_bytes = b'{"type": "assistant", "message": {"model": "bad-\xff\xfe"}}'
    good_line_2 = json.dumps(_assistant_line("claude-opus-4-8")).encode("utf-8")
    path.write_bytes(good_line_1 + b"\n" + bad_bytes + b"\n" + good_line_2 + b"\n")

    models = list(tier_echo.iter_transcript_models(str(path)))
    assert models.count("claude-opus-4-8") == 2


def test_iter_transcript_models_missing_file_raises_oserror():
    # main() ловит OSError и выходит тихо -- здесь проверяем контракт
    # самой функции (она НЕ глотает ошибку -- это забота main()).
    import pytest

    with pytest.raises(OSError):
        list(tier_echo.iter_transcript_models(str(Path("no-such-dir") / "no-such-file.jsonl")))


# ---------------------------------------------------------------------
# main() end-to-end -- subprocess-смок (образец test_dod_gate._run_hook)
# ---------------------------------------------------------------------


def test_echo_single_model_stderr_output(tmp_path):
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("claude-opus-4-8")])
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): claude-opus-4-8=1"


def test_echo_multiple_models_stderr_output(tmp_path):
    transcript = _write_transcript(
        tmp_path,
        "sub.jsonl",
        [_assistant_line("claude-sonnet-5"), _assistant_line("claude-opus-4-8"), _assistant_line("claude-sonnet-5")],
    )
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): claude-sonnet-5=2, claude-opus-4-8=1"


def test_echo_mismatch_declared_fable_measured_opus(tmp_path):
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("claude-opus-4-8")])
    result = _run_hook(_stop_payload(transcript, description="fable: do the architecture review"))
    assert result.returncode == 0
    assert result.stderr.strip() == (
        "TIER ECHO (measured): claude-opus-4-8=1 MISMATCH vs declared 'fable'"
    )


def test_echo_no_mismatch_declared_opus_measured_opus(tmp_path):
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("claude-opus-4-8")])
    result = _run_hook(_stop_payload(transcript, description="opus: review the diff"))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): claude-opus-4-8=1"


def test_echo_synthetic_line_excluded_normal_model_counted(tmp_path):
    # Критик attempt 2, п.2а, subprocess-уровень: "<synthetic>" не
    # попадает в вывод, нормальная модель посчитана.
    transcript = _write_transcript(
        tmp_path,
        "sub.jsonl",
        [
            _assistant_line("claude-opus-4-8"),
            {"type": "assistant", "message": {"model": "<synthetic>"}},
            _assistant_line("claude-opus-4-8"),
        ],
    )
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert "<synthetic>" not in result.stderr
    assert result.stderr.strip() == "TIER ECHO (measured): claude-opus-4-8=2"


def test_echo_only_synthetic_lines_silent_exit(tmp_path):
    # Критик attempt 2, п.2б, subprocess-уровень: транскрипт целиком из
    # synthetic-строк -- как пустой транскрипт, тихий exit без строки.
    transcript = _write_transcript(
        tmp_path,
        "sub.jsonl",
        [
            {"type": "assistant", "message": {"model": "<synthetic>"}},
            {"type": "assistant", "message": {"model": "<synthetic>"}},
        ],
    )
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert result.stderr == ""


def test_echo_non_ascii_model_ascii_output(tmp_path):
    # Критик attempt 2, п.2в, subprocess-уровень: не-ASCII в
    # message.model (кириллица) -- вывод остаётся чистым ASCII.
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("клод-опус")])
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): ????-????=1"
    assert result.stderr.isascii()


def test_echo_invalid_utf8_bytes_in_transcript_file_no_crash(tmp_path):
    # Критик attempt 2, п.2г, subprocess-уровень: невалидные UTF-8
    # байты В ФАЙЛЕ транскрипта (не stdin) -- хук не падает, валидные
    # строки вокруг битой всё равно считаются.
    transcript = tmp_path / "sub.jsonl"
    good_line = json.dumps(_assistant_line("claude-opus-4-8")).encode("utf-8")
    bad_bytes = b'{"type": "assistant", "message": {"model": "bad-\xff\xfe"}}'
    transcript.write_bytes(good_line + b"\n" + bad_bytes + b"\n" + good_line + b"\n")

    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert "claude-opus-4-8=2" in result.stderr


def test_echo_missing_transcript_path_field_silent_exit(tmp_path):
    payload = {
        "session_id": "sess-1",
        "cwd": ".",
        "hook_event_name": "SubagentStop",
        "agent_id": "agent-1",
    }
    result = _run_hook(payload)
    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""


def test_echo_transcript_does_not_exist_silent_exit(tmp_path):
    missing = tmp_path / "does-not-exist.jsonl"
    result = _run_hook(_stop_payload(missing))
    assert result.returncode == 0
    assert result.stderr == ""


def test_echo_empty_transcript_silent_exit(tmp_path):
    transcript = tmp_path / "empty.jsonl"
    transcript.write_text("", encoding="utf-8")
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert result.stderr == ""


def test_echo_malformed_lines_among_valid_still_counts(tmp_path):
    transcript = _write_transcript(
        tmp_path,
        "sub.jsonl",
        [_assistant_line("claude-opus-4-8"), "{not valid json", _assistant_line("claude-opus-4-8")],
    )
    result = _run_hook(_stop_payload(transcript))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): claude-opus-4-8=2"


def test_echo_description_without_colon_no_mismatch_check(tmp_path):
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("claude-opus-4-8")])
    result = _run_hook(_stop_payload(transcript, description="opus review the diff"))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): claude-opus-4-8=1"


def test_echo_description_non_tier_word_prefix_no_mismatch_check(tmp_path):
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("claude-opus-4-8")])
    result = _run_hook(_stop_payload(transcript, description="opus2: review the diff"))
    assert result.returncode == 0
    assert result.stderr.strip() == "TIER ECHO (measured): claude-opus-4-8=1"


def test_echo_malformed_json_payload_fails_open():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="{not valid json",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_echo_payload_not_a_dict_fails_open():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="[1, 2, 3]",
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_echo_raw_utf8_bytes_stdin_no_crash(tmp_path):
    transcript = _write_transcript(tmp_path, "sub.jsonl", [_assistant_line("claude-opus-4-8")])
    payload = _stop_payload(transcript)
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=raw,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0
