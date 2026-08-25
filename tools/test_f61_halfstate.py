"""tools/test_f61_halfstate.py -- F-61 узел A батарея (builder t-503,
2026-08-19, docs/tasks/2026-08-19_f61-f58-remediation-spec.md).

ФОРМА (Р2а спеки, одна батарея с F61_TARGET, не 5 отдельных файлов):
цель разрешается через переменную окружения F61_TARGET:
 - F61_TARGET=live  -> ВСЕГДА живой tools/<name>.py (контр-прогон --
   должен быть КРАСНЫМ на дискриминирующих тестах, класс F-61 ещё не
   починен там).
 - F61_TARGET не задан (default) -> сиблинг tools/<name>_f61.py, если
   он существует, иначе МОЛЧА живой файл (см. _resolve_module_path) --
   RERUNNABLE кем угодно без правки кода, дух "сильнее негативного
   контроля" (t-469/t-470).
 - F61_TARGET на любое ДРУГОЕ непустое значение -> сиблинг ЗАПРОШЕН
   ЯВНО; при его отсутствии -- ГРОМКИЙ КРАС (pytest.fail, называющий
   запрошенный путь), НЕ тихая подмена живым (F1, ФИКС-РАУНД
   docs/tasks/2026-08-25_queue8-mechbatch-spec.md, тот же класс, что
   K1 узла t-601 уже чинил в MODULE_UNDER_TEST-файлах).
Модуль резолвится и импортируется через importlib.util (не
sys.path-игру, не хардкод боевого пути в SCRIPT-константе,
sibling-first индирекция -- принятая находка sonnet-контроля t-470:
"test_dod_track SCRIPT захардкожен на боевой путь -- без индирекции
e2e-смок гоняет НЕПАТЧЕННЫЙ файл всю дистанцию, зелёный прогон
доказывает не то").

Существующие тестовые файлы (tools/test_dod_track.py,
tools/test_critic_snapshot.py, tools/test_dod_gate.py,
tools/test_main_gate.py) НЕ ТРОГАЮТСЯ этим батчем -- их SCRIPT
жёстко на боевой путь (проверено: test_dod_track.py:31,
test_critic_snapshot.py:50, tools/test_dod_gate.py:29 (по аналогии),
tools/test_main_gate.py:25 (по аналогии)) -- их зелёный прогон БЕЗ
правок живых файлов доказывает A5 (существующие пины
test_critic_snapshot.py:289-291/296-315/317+ зелены без правок).

Ключи спеки (docs/tasks/2026-08-19_f61-f58-remediation-spec.md, узел A):
 A1 -- тотальный try в dod_track main(), одна строка stderr, rc=0.
 A2 -- атомарная запись (mkstemp в той же папке + os.replace, суффикс
      .tmp последний/не .json), mkdir(parents=True, exist_ok=True)
      сохранён дословно.
 A3 -- guard не-dict root И не-dict tool_input (dod_track, critic_snapshot).
 A4 -- critic_snapshot: prev-проекция читается ДО рискованной записи,
      передаётся параметром, _write_failure_snapshot файл не читает.
 A5 -- существующие пины critic_snapshot зелены БЕЗ правок (см. выше --
      доказывается тем, что этот батч живые файлы вообще не трогает).
 A6 -- дискриминирующий тест атомарности: мок РЕАЛЬНО усекает файл и
      лишь потом бросает.
 A7 -- dod_gate/main_gate получают ТОЛЬКО A2, без внешнего try.
 A8 -- проба "боевой артефакт недоступен на запись" на каждый пишущий
      хук батча (read-only файл; путь занят каталогом).

Run: python -m pytest tools/test_f61_halfstate.py -q
Контр-прогон: F61_TARGET=live python -m pytest tools/test_f61_halfstate.py -q -k f61
"""

import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
F61_TARGET = os.environ.get("F61_TARGET", "").strip().lower()
MODULE_NAMES = ("dod_track", "critic_snapshot", "dod_gate", "main_gate")

# Модули без A1 (тотальный try) -- только dod_track несёт его (A1
# буквально называет ТОЛЬКО dod_track); dod_gate/main_gate НАМЕРЕННО
# без total-try (A7/Р3а). critic_snapshot несёт СВОЙ fail-open (два
# раздельных try/except) с ДО этого батча -- не новый A1-стиль.
FAIL_OPEN_AT_MAIN_LEVEL = {"dod_track", "critic_snapshot"}
NO_FAIL_OPEN_AT_MAIN_LEVEL = {"dod_gate", "main_gate"}


def _resolve_module_path(base_name: str) -> "tuple[Path, bool]":
    """(путь, is_unpatched). ТРИ мира спеки (посадка Lead 2026-08-19,
    правка семантики второго поля): is_unpatched=True означает
    «цель ЗАВЕДОМО непочинена» и легален ТОЛЬКО в контр-режиме
    F61_TARGET=live ПРИ СУЩЕСТВУЮЩЕМ сиблинге (мир 2: живой файл ещё
    старый, сиблинг несёт фикс). После посадки (мир 3: сиблингов нет,
    живой файл = фикс) контр-режима не существует — is_unpatched
    всегда False, батарея проверяет починенное поведение на живом
    пути. Прежняя семантика (is_live по факту загрузки живого)
    ошибочно ждала старого поведения от починенного файла —
    дефект батареи против требования «зелена во всех трёх мирах».

    F1 (ФИКС-РАУНД, docs/tasks/2026-08-25_queue8-mechbatch-spec.md,
    _resolve_module_path -- ПЕРВОИСТОЧНИК конвенции, тот же класс, что
    уже чинился в пяти MODULE_UNDER_TEST-файлах узла K1): default
    (F61_TARGET пуст) -- сиблинг, ЕСЛИ он есть, иначе живой, МОЛЧА (мир
    3, поведение неизменно). F61_TARGET ЗАПРОШЕН ЯВНО (задан и НЕ
    "live") -- при отсутствии сиблинга ГРОМКИЙ КРАС, не тихая подмена
    живым."""
    live = TOOLS_DIR / f"{base_name}.py"
    sibling = TOOLS_DIR / f"{base_name}_f61.py"
    if F61_TARGET == "live":
        return live, sibling.exists()
    if F61_TARGET == "":
        return (sibling, False) if sibling.exists() else (live, False)
    if not sibling.exists():
        pytest.fail(
            f"F61_TARGET={F61_TARGET!r} requested sibling {sibling} but it "
            f"does not exist -- no silent live fallback (F1)"
        )
    return sibling, False


_MODULE_CACHE: dict = {}


def _load(base_name: str):
    """Импортирует модуль через importlib.util по резолвленному пути.
    Кэш по (base_name, путь) -- повторные вызовы в одном тесте не
    переимпортируют модуль заново (важно: свежий импорт на каждый тест
    всё равно происходит per pytest-процесс только один раз за
    ключ -- переиспользование безопасно, тестируемые функции чистые
    или явно управляются через monkeypatch per-test). Возвращает
    (module, script_path, is_live)."""
    path, is_live = _resolve_module_path(base_name)
    cache_key = (base_name, str(path))
    if cache_key not in _MODULE_CACHE:
        alias = f"f61_battery_{base_name}_{'live' if is_live else 'sibling'}"
        spec = importlib.util.spec_from_file_location(alias, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[cache_key] = module
    return _MODULE_CACHE[cache_key], path, is_live


class _FakeStdin:
    """Тот же приём, что tools/test_critic_snapshot.py._FakeStdin --
    main() всех четырёх модулей читает ТОЛЬКО sys.stdin.buffer.read()
    (байтовый staging_hq вариант)."""

    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


def _run_main(mod, payload_bytes: bytes, monkeypatch) -> int:
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin(payload_bytes))
    return mod.main()


def _dod_track_edit_payload(cwd: Path, session_id: str = "s-1", file_path=None) -> dict:
    fp = file_path if file_path is not None else str(cwd / "some_file.py")
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": fp},
        "session_id": session_id,
        "cwd": str(cwd),
    }


def _dod_track_bash_payload(cwd: Path, session_id: str = "s-1", command="pytest -q", stdout="1 passed", stderr="") -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "tool_response": {"stdout": stdout, "stderr": stderr},
        "session_id": session_id,
        "cwd": str(cwd),
    }


def _critic_payload(cwd: Path, session_id: str = "s-1") -> dict:
    return {
        "tool_name": "Task",
        "tool_input": {"subagent_type": "critic"},
        "session_id": session_id,
        "cwd": str(cwd),
    }


def _subagent_stop_payload(cwd: Path, session_id: str = "s-1", agent_id: str = "a-1") -> dict:
    return {
        "hook_event_name": "SubagentStop",
        "session_id": session_id,
        "cwd": str(cwd),
        "agent_id": agent_id,
    }


def _stop_payload(cwd: Path, session_id: str = "s-1") -> dict:
    return {"hook_event_name": "Stop", "session_id": session_id, "cwd": str(cwd)}


def _install_truncating_write_text_mock(monkeypatch, only_first_call=False):
    """Мок, РЕАЛЬНО усекающий файл (открывает 'w', пишет ПОЛОВИНУ
    текста, flush) и ЛИШЬ ПОТОМ бросает -- буквально спека A6 ("мок
    РЕАЛЬНО усекает файл и лишь потом бросает"), НЕ json.dumps-до-
    открытия. Патчится на уровне КЛАССА pathlib.Path -- тот же метод,
    что вызывают И боевой (небезопасный) код на БОЕВОМ пути напрямую,
    И _atomic_write_text() сиблингов на СВЕЖЕМ tmp-пути -- разница self
    и есть механизм различения (см. dod_track_f61.py._atomic_write_text
    докстринг за полное обоснование).

    only_first_call=True: усекает-и-бросает ТОЛЬКО на первом вызове
    write_text() в этом тесте, дальнейшие вызовы идут НЕТРОНУТЫМИ
    (реальная запись) -- нужно для A4-теста (первый вызов -- неудачная
    попытка успешного документа, второй -- запись отказного документа,
    которая обязана реально удаться)."""
    real_write_text = Path.write_text
    state = {"n": 0}

    def fake_write_text(self, text, *args, **kwargs):
        state["n"] += 1
        if only_first_call and state["n"] > 1:
            return real_write_text(self, text, *args, **kwargs)
        half = text[: max(1, len(text) // 2)]
        with open(str(self), "w", encoding="utf-8") as fh:
            fh.write(half)
            fh.flush()
        raise RuntimeError("simulated mid-write truncation (test)")

    monkeypatch.setattr(Path, "write_text", fake_write_text)


# ===========================================================================
# A1 -- тотальный try в dod_track main(), одна строка stderr, rc=0.
# ===========================================================================


def test_a1_dod_track_uncaught_write_failure_becomes_single_stderr_line_rc0(
    tmp_path, monkeypatch, capsys,
):
    mod, script, is_live = _load("dod_track")

    def _boom(_path, _data):
        raise PermissionError("simulated locked track file (A1 probe)")

    monkeypatch.setattr(mod, "_save_track", _boom)

    payload = _dod_track_edit_payload(tmp_path)

    raised = None
    rc = None
    try:
        rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    except Exception as exc:  # noqa: BLE001 -- exactly what we're probing
        raised = exc

    err = capsys.readouterr().err

    if is_live:
        # Живой dod_track.py: _save_track() вызывается ВНЕ какого-либо
        # try (FINDINGS F-61, экземпляр 1) -- исключение долетает до
        # main() и наружу НЕПОЙМАННЫМ. Это и есть дискриминатор A1.
        assert raised is not None, (
            "[live] ожидалось необработанное исключение (нет тотального "
            "try) -- если main() ЕГО поймал, дискриминатор A1 сломан"
        )
    else:
        assert raised is None, f"[sibling] main() не должен бросать наружу: {raised!r}"
        assert rc == 0
        lines = [ln for ln in err.splitlines() if ln.strip()]
        assert len(lines) == 1, f"ожидалась РОВНО одна строка stderr, получено: {lines!r}"
        assert lines[0] == (
            "dod_track.py: FAILED to save track "
            "(PermissionError: simulated locked track file (A1 probe))"
        )


def test_a1_dod_track_recognized_nonevents_stay_silent_rc0(tmp_path, monkeypatch, capsys):
    """A1 края: битый JSON / не-fact / нет session_id остаются ТИХИМИ
    (без stderr) -- total-try не должен превращать ожидаемые ранние
    return'ы в шумные диагностики."""
    mod, script, is_live = _load("dod_track")

    rc = _run_main(mod, b"{not valid json", monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""

    payload = {"tool_name": "SomeIrrelevantTool", "session_id": "s-1", "cwd": str(tmp_path)}
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""

    payload = _dod_track_edit_payload(tmp_path, session_id="")
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""


# ===========================================================================
# A3 -- guard не-dict root И не-dict tool_input (dod_track, critic_snapshot).
# ===========================================================================


@pytest.mark.parametrize("bad_root", [[], "just a string", 5, None, True])
def test_a3_dod_track_non_dict_root_returns_zero_silently(bad_root, tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load("dod_track")
    rc = _run_main(mod, json.dumps(bad_root).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""
    assert not (tmp_path / ".claude").exists()


@pytest.mark.parametrize("bad_tool_input", [[1, 2], "oops", 5, True])
def test_a3_dod_track_non_dict_tool_input_returns_zero_silently(
    bad_tool_input, tmp_path, monkeypatch, capsys,
):
    mod, script, is_live = _load("dod_track")
    payload = {
        "tool_name": "Edit",
        "tool_input": bad_tool_input,
        "session_id": "s-1",
        "cwd": str(tmp_path),
    }
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""
    assert not (tmp_path / ".claude").exists()

    # Прямой вызов build_fact -- то же самое на чистой функции, если
    # она существует в резолвленном модуле (и live, и сиблинг несут
    # build_fact под одним именем).
    assert mod.build_fact({"tool_name": "Edit", "tool_input": bad_tool_input}) is None
    assert mod.build_fact({"tool_name": "Bash", "tool_input": bad_tool_input}) is None


@pytest.mark.parametrize("bad_root", [[], "just a string", 5, None])
def test_a3_critic_snapshot_non_dict_root_returns_zero_silently(bad_root, tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load("critic_snapshot")
    rc = _run_main(mod, json.dumps(bad_root).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()


@pytest.mark.parametrize("bad_tool_input", [[1, 2], "oops", 5])
def test_a3_critic_snapshot_non_dict_tool_input_returns_zero_silently(
    bad_tool_input, tmp_path, monkeypatch, capsys,
):
    mod, script, is_live = _load("critic_snapshot")
    payload = {
        "tool_name": "Task",
        "tool_input": bad_tool_input,
        "session_id": "s-1",
        "cwd": str(tmp_path),
    }
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()


# ===========================================================================
# A2 -- имя tmp: суффикс .tmp последний, не .json (пин Р4а) + не
# подхватывается session_context.py:1616 glob("*.json").
# ===========================================================================


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_a2_tmp_name_suffix_is_tmp_last_and_not_json(base_name, tmp_path, monkeypatch):
    mod, script, is_live = _load(base_name)
    if is_live or not hasattr(mod, "_atomic_write_text"):
        pytest.skip(
            f"[{base_name}] живой (пред-фикс) модуль не несёт "
            "_atomic_write_text -- пин применим только к сиблингу"
        )

    seen_names = []
    real_mkstemp = tempfile.mkstemp

    def spy_mkstemp(*args, **kwargs):
        fd, name = real_mkstemp(*args, **kwargs)
        seen_names.append(name)
        return fd, name

    monkeypatch.setattr(tempfile, "mkstemp", spy_mkstemp)

    target = tmp_path / "some_track.json"
    mod._atomic_write_text(target, '{"ok": true}\n')

    assert seen_names, "mkstemp не был вызван -- атомарная запись не сработала"
    for name in seen_names:
        assert name.endswith(".tmp"), f"суффикс .tmp обязан быть ПОСЛЕДНИМ: {name!r}"
        assert not name.endswith(".json"), (
            f"осколок не должен заканчиваться на .json (session_context.py:1616 "
            f"glob('*.json') подхватил бы его как чужой трек): {name!r}"
        )
    assert target.read_text(encoding="utf-8") == '{"ok": true}\n'


@pytest.mark.parametrize("base_name", ["dod_track", "dod_gate", "main_gate"])
def test_a2_orphaned_tmp_after_replace_failure_is_invisible_to_json_glob(
    base_name, tmp_path, monkeypatch,
):
    """A2 края (конфликтная пара 2 спеки, "атомарность x glob('*.json')"):
    если os.replace() падает ПОСЛЕ успешной записи в tmp (симуляция --
    напр. диск переполнился ровно на шаге переименования), tmp-осколок
    может остаться на диске -- session_context.py:1616's
    glob("*.json") НЕ должен принять его за чужой трек сессии."""
    mod, script, is_live = _load(base_name)
    if is_live or not hasattr(mod, "_atomic_write_text"):
        pytest.skip(f"[{base_name}] живой модуль не несёт _atomic_write_text")

    real_replace = os.replace

    def flaky_replace(_src, _dst):
        raise OSError("simulated replace failure (test)")

    monkeypatch.setattr(os, "replace", flaky_replace)

    track_dir = tmp_path / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    target = track_dir / "s-orphan.json"

    with pytest.raises(OSError):
        mod._save_track(target, {"edits": [], "runs": []})

    # session_context.py:1616 читатель: sorted(track_dir.glob("*.json")).
    matched = sorted(track_dir.glob("*.json"))
    assert matched == [], (
        f"осколок подхвачен как чужой трек glob('*.json'): {matched!r}"
    )
    # tmp-осколок реально остался (иначе тест ничего не проверяет)?
    # НЕ обязателен по контракту (_atomic_write_text() старается unlink
    # tmp в except-ветке) -- документируем оба случая как приемлемые:
    # если он остался, он невидим glob'у (проверено выше); если он
    # успешно удалён -- тем более невидим. Явных .tmp-файлов быть не
    # должно ПОСЛЕ unlink; если остались -- это НЕ .json, что и требуется.
    leftovers = list(track_dir.glob("*"))
    for f in leftovers:
        assert f.name.endswith(".tmp"), f"неожиданный осколок: {f}"


# ===========================================================================
# A4 -- critic_snapshot: prev-проекция читается ДО рискованной записи,
# _write_failure_snapshot файл больше не читает.
# ===========================================================================


def test_a4_prev_fields_survive_write_failure_and_land_in_failure_doc(
    tmp_path, monkeypatch, capsys,
):
    """Первый write_text() -- попытка успешного документа, падает
    (усекает); ВТОРОЙ write_text() -- запись отказного документа,
    ОБЯЗАНА реально дойти до диска (only_first_call=True). На живом
    (непочиненном) модуле prev_ts/prev_tree_hash читаются ПОСЛЕ первого
    (уже усекающего) write_text -- т.е. из УЖЕ ИСПОРЧЕННОГО файла --
    инвариант "prev_* скопированы из предыдущего снимка" ломается
    (класс F-61, экземпляр 2, буквально)."""
    mod, script, is_live = _load("critic_snapshot")

    snap_dir = tmp_path / ".claude"
    snap_dir.mkdir(parents=True)
    snap = snap_dir / "critic_snapshot.json"
    prior_doc = {"ts": "2026-08-01T00:00:00.000000", "tree_hash": "PRIOR-HASH-ABC", "files_count": 3, "skipped_files": 0}
    snap.write_text(json.dumps(prior_doc), encoding="utf-8")

    _install_truncating_write_text_mock(monkeypatch, only_first_call=True)

    payload = _critic_payload(tmp_path)
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0

    doc = json.loads(snap.read_text(encoding="utf-8"))
    err = capsys.readouterr().err
    assert "FAILED to take snapshot" in err

    if is_live:
        # ДИСКРИМИНАТОР: живой critic_snapshot.py читает prev_* уже
        # ПОСЛЕ того, как первый (неудавшийся) snap.write_text() усёк
        # РЕАЛЬНЫЙ файл -- prev_ts/prev_tree_hash теряются.
        assert "prev_tree_hash" not in doc or doc.get("prev_tree_hash") != "PRIOR-HASH-ABC", (
            f"[live] ожидалась ПОТЕРЯ prev_tree_hash (класс F-61, экз.2), "
            f"но документ несёт корректный prev_tree_hash -- дискриминатор "
            f"не сработал: {doc!r}"
        )
    else:
        assert doc.get("prev_ts") == prior_doc["ts"]
        assert doc.get("prev_tree_hash") == prior_doc["tree_hash"]
        assert "tree_hash" not in doc
        assert "files_count" not in doc


# ===========================================================================
# A6 -- дискриминирующий тест атомарности (генеральный, все 4 писателя).
# ===========================================================================


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_a6_mid_write_failure_never_corrupts_the_original_file(
    base_name, tmp_path, monkeypatch, capsys,
):
    """ГЛАВНЫЙ дискриминирующий тест (A6): мок Path.write_text РЕАЛЬНО
    усекает файл (открывает 'w', пишет половину, flush) и ЛИШЬ ПОТОМ
    бросает -- НЕ json.dumps-до-открытия. На непатченном (живом) коде
    ОБЯЗАН быть красным (write_text вызывается на БОЕВОМ пути напрямую,
    self == боевой файл -- реальная порча); на атомарном (сиблинг)
    ОБЯЗАН быть зелёным (write_text вызывается на СВЕЖЕМ tmp-пути,
    self != боевой файл -- os.replace() до боевого пути так и не
    доходит)."""
    mod, script, is_live = _load(base_name)

    if base_name == "critic_snapshot":
        snap_dir = tmp_path / ".claude"
        snap_dir.mkdir(parents=True)
        target = snap_dir / "critic_snapshot.json"
        original = json.dumps({"ts": "SEED", "tree_hash": "SEED-HASH", "files_count": 1, "skipped_files": 0}) + "\n"
        # write_bytes, НЕ write_text: Path.write_text() на Windows
        # транслирует "\n" -> "\r\n" (universal-newlines на запись) --
        # это исказило бы seed ДО того, как мок вообще коснулся файла,
        # и сравнение байт-в-байт ниже стало бы ложноотрицательным.
        target.write_bytes(original.encode("utf-8"))

        _install_truncating_write_text_mock(monkeypatch)

        payload = _critic_payload(tmp_path)
        raised = None
        try:
            rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
        except Exception as exc:  # noqa: BLE001
            raised = exc
        # critic_snapshot несёт СВОЙ fail-open (предшествует F-61) --
        # обязан НИКОГДА не бросать, живой или сиблинг.
        assert raised is None, f"[{base_name}] main() бросил наружу: {raised!r}"
    else:
        track_dir = tmp_path / ".claude" / "dod_track"
        track_dir.mkdir(parents=True)
        target = track_dir / "s-a6.json"
        original = json.dumps({"edits": [], "runs": [], "marker": "SEED-ORIGINAL"}) + "\n"
        target.write_bytes(original.encode("utf-8"))  # см. комментарий выше -- write_bytes, не write_text

        _install_truncating_write_text_mock(monkeypatch)

        raised = None
        try:
            mod._save_track(target, {"edits": [{"marker": "NEW"}], "runs": []})
        except Exception as exc:  # noqa: BLE001
            raised = exc
        # _save_track() вызывается НАПРЯМУЮ (в обход main()) -- она
        # НИКОГДА не глотает исключение сама (ни в live, ни в сиблинге,
        # A2 не меняет это): раз write_text брошен, _save_track обязана
        # пробросить его дальше (main()/вызывающий код решает, что
        # делать -- A1 для dod_track, A7-отказ от try для gates).
        assert raised is not None, (
            f"[{base_name}] _save_track() неожиданно проглотила исключение"
        )

    after = target.read_bytes()
    original_bytes = original.encode("utf-8")

    target_label = f"[{base_name}, F61_TARGET={'live' if is_live else 'sibling'}]"
    assert after == original_bytes, (
        f"{target_label} ОРИГИНАЛ НЕ СОХРАНЁН после инжектированного сбоя "
        f"записи на полпути -- половинчатое состояние на диске (класс F-61): "
        f"{after!r} != seed {original_bytes!r}"
    )

    leftovers = list(target.parent.glob("*.tmp"))
    assert not leftovers, f"{target_label} осиротевший .tmp фрагмент: {leftovers}"


# ===========================================================================
# A7 -- dod_gate/main_gate получают ТОЛЬКО A2, БЕЗ внешнего try
# (enforcement выше косметики отказа -- гейты обязаны реально
# БЛОКИРОВАТЬ, не гаситься тихим fail-open).
# ===========================================================================


@pytest.mark.parametrize("base_name", ["dod_gate", "main_gate"])
def test_a7_gates_still_block_normally_no_total_try_added(base_name, tmp_path, monkeypatch, capsys):
    """Позитивная сторона A7: нормальный (без инжектированного сбоя)
    прогон гейта на реальном нарушении DoD-инварианта ДОЛЖЕН по-прежнему
    блокировать (exit 2 + BLOCK_MESSAGE) -- атомарная запись НЕ должна
    была случайно превратить гейт в fail-open по умолчанию."""
    mod, script, is_live = _load(base_name)

    if base_name == "dod_gate":
        payload = _subagent_stop_payload(tmp_path)
        track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
        track_path.parent.mkdir(parents=True)
        track_path.write_text(
            json.dumps({"edits": [{"ts": "2026-01-01T00:00:00.000000", "agent_id": "a-1", "file_path": "x.py"}], "runs": []}),
            encoding="utf-8",
        )
    else:
        payload = _stop_payload(tmp_path)
        track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
        track_path.parent.mkdir(parents=True)
        track_path.write_text(
            json.dumps({"edits": [{"ts": "2026-01-01T00:00:00.000000", "agent_id": None, "file_path": "x.py"}], "runs": []}),
            encoding="utf-8",
        )

    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    err = capsys.readouterr().err
    assert rc == 2, f"[{base_name}] ожидался блок (exit 2), получено rc={rc}, stderr={err!r}"
    assert "прогон" in err or "прогона" in err


# ===========================================================================
# A8 -- проба "боевой артефакт недоступен на запись" на КАЖДЫЙ пишущий
# хук батча: (i) файл read-only; (ii) путь занят каталогом.
# ===========================================================================


def _chmod_readonly(path: Path):
    os.chmod(path, stat.S_IREAD)


def _chmod_writable(path: Path):
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_a8_readonly_target_file(base_name, tmp_path, monkeypatch, capsys):
    """FINDINGS F-61, экземпляр 1, буквальная проба: "Проба на живом
    хуке: трек-файл только на чтение -> rc=1 с PermissionError в
    трейсбеке" -- воспроизводится здесь напрямую (реальный os.chmod,
    без мока: на Windows read-only бит реально блокирует open(mode='w'),
    ДО любого усечения содержимого -- см. tools/test_critic_snapshot.py:
    21-27 за ту же эмпирику)."""
    mod, script, is_live = _load(base_name)

    if base_name == "critic_snapshot":
        snap_dir = tmp_path / ".claude"
        snap_dir.mkdir(parents=True)
        target = snap_dir / "critic_snapshot.json"
        original = json.dumps({"ts": "SEED", "tree_hash": "SEED-HASH", "files_count": 0, "skipped_files": 0}) + "\n"
        target.write_bytes(original.encode("utf-8"))  # write_bytes -- см. test_a6 за причину
        _chmod_readonly(target)
        try:
            payload = _critic_payload(tmp_path)
            raised = None
            rc = None
            try:
                rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
            except Exception as exc:  # noqa: BLE001
                raised = exc
            assert raised is None, f"[{base_name}] main() бросил наружу: {raised!r}"
            assert rc == 0
            err = capsys.readouterr().err
            assert "FAILED to take snapshot" in err
            assert target.read_bytes() == original.encode("utf-8")
        finally:
            _chmod_writable(target)
        return

    track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
    track_path.parent.mkdir(parents=True)
    if base_name == "dod_track":
        original = json.dumps({"edits": [], "runs": []}) + "\n"
    elif base_name == "dod_gate":
        original = json.dumps({"edits": [], "runs": [], "gate_state": {"consecutive_blocks": 0, "per_agent": {}}}) + "\n"
    else:
        original = json.dumps({"edits": [], "runs": [], "main_gate_state": {"consecutive_blocks": 0}}) + "\n"
    track_path.write_bytes(original.encode("utf-8"))  # write_bytes -- см. test_a6 за причину
    _chmod_readonly(track_path)
    try:
        if base_name == "dod_track":
            payload = _dod_track_edit_payload(tmp_path)
        elif base_name == "dod_gate":
            payload = _subagent_stop_payload(tmp_path)
        else:
            payload = _stop_payload(tmp_path)

        raised = None
        rc = None
        try:
            rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
        except Exception as exc:  # noqa: BLE001
            raised = exc

        if base_name in FAIL_OPEN_AT_MAIN_LEVEL:
            if is_live:
                assert raised is not None, (
                    f"[live/{base_name}] ожидался НЕПОЙМАННЫЙ PermissionError "
                    "(нет тотального try) -- дискриминатор A1/A8 не сработал"
                )
            else:
                assert raised is None, f"[{base_name}] main() бросил наружу: {raised!r}"
                assert rc == 0
                err = capsys.readouterr().err
                assert "FAILED to save track" in err
        else:
            # dod_gate/main_gate (A7): НЕТ total-try ни в live, ни в
            # сиблинге -- ожидается пробрасывание исключения В ОБОИХ
            # случаях; атомарность (A2) НЕ гарантирует graceful exit
            # здесь по замыслу (Р3а -- enforcement выше косметики).
            assert raised is not None, (
                f"[{base_name}] ожидалось исключение наружу (A7 -- нет "
                f"total-try), получено rc={rc} без исключения"
            )

        assert track_path.read_bytes() == original.encode("utf-8"), (
            f"[{base_name}] read-only боевой файл был изменён -- "
            "open(mode='w') на read-only файле НЕ должен был даже "
            "начать усечение"
        )
    finally:
        _chmod_writable(track_path)


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_a8_path_occupied_by_directory(base_name, tmp_path, monkeypatch, capsys):
    """A8 вторая проба: путь трека/снимка занят КАТАЛОГОМ, не файлом --
    ни чтение (IsADirectoryError), ни os.replace() поверх каталога не
    должны привести к тихому молчаливому крашу без диагностики (для
    fail-open хуков) или к порче ЧЕГО-ЛИБО за пределами этого пути (для
    A7-хуков, где пробрасывание исключения -- ожидаемое поведение)."""
    mod, script, is_live = _load(base_name)

    if base_name == "critic_snapshot":
        snap_dir = tmp_path / ".claude"
        snap_dir.mkdir(parents=True)
        target = snap_dir / "critic_snapshot.json"
        target.mkdir()  # путь занят каталогом, не файлом
        payload = _critic_payload(tmp_path)
        raised = None
        rc = None
        try:
            rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
        except Exception as exc:  # noqa: BLE001
            raised = exc
        assert raised is None, f"[{base_name}] main() бросил наружу: {raised!r}"
        assert rc == 0
        err = capsys.readouterr().err
        assert "FAILED to take snapshot" in err
        assert target.is_dir(), "каталог не должен был исчезнуть/замениться файлом при отказе"
        return

    track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
    track_path.parent.mkdir(parents=True)
    track_path.mkdir()  # путь занят каталогом, не файлом

    if base_name == "dod_track":
        payload = _dod_track_edit_payload(tmp_path)
    elif base_name == "dod_gate":
        payload = _subagent_stop_payload(tmp_path)
    else:
        payload = _stop_payload(tmp_path)

    raised = None
    rc = None
    try:
        rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    except Exception as exc:  # noqa: BLE001
        raised = exc

    if base_name in FAIL_OPEN_AT_MAIN_LEVEL:
        if is_live:
            assert raised is not None, (
                f"[live/{base_name}] ожидался непойманный сбой на каталоге "
                "вместо файла -- дискриминатор A1/A8 не сработал"
            )
        else:
            assert raised is None, f"[{base_name}] main() бросил наружу: {raised!r}"
            assert rc == 0
    else:
        assert raised is not None, (
            f"[{base_name}] ожидалось исключение наружу (A7 -- нет total-try)"
        )

    assert track_path.is_dir(), "каталог не должен был исчезнуть/замениться файлом при отказе"
    # никаких .tmp-осколков рядом с (не тронутым) каталогом.
    leftovers = list(track_path.parent.glob("*.tmp"))
    assert not leftovers, f"[{base_name}] осиротевший .tmp фрагмент: {leftovers}"


# ===========================================================================
# Края спеки: stdin пуст, session_id отсутствует, cwd отсутствует, трека
# нет, каталога нет, битый JSON -- чистое состояние.
# ===========================================================================


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_edge_empty_stdin_returns_zero(base_name, tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load(base_name)
    rc = _run_main(mod, b"", monkeypatch)
    assert rc == 0
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("base_name", ["dod_track", "dod_gate", "main_gate"])
def test_edge_missing_session_id_returns_zero_no_track_dir(base_name, tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load(base_name)
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(tmp_path / "x.py")}, "cwd": str(tmp_path)}
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    assert not (tmp_path / ".claude").exists()


@pytest.mark.parametrize("base_name", ["dod_track", "dod_gate", "main_gate"])
def test_edge_cwd_missing_defaults_to_dot(base_name):
    mod, script, is_live = _load(base_name)
    path = mod._track_path(None, "sid-1")
    assert path == Path(".") / ".claude" / "dod_track" / "sid-1.json"


@pytest.mark.parametrize("base_name", ["dod_track", "dod_gate", "main_gate"])
def test_edge_missing_track_file_gives_default_shape(tmp_path, base_name):
    mod, script, is_live = _load(base_name)
    missing = tmp_path / "does" / "not" / "exist.json"
    data = mod._load_track(missing)
    assert data["edits"] == []
    assert data["runs"] == []


@pytest.mark.parametrize("base_name", ["dod_track", "dod_gate", "main_gate"])
def test_edge_corrupt_json_gives_clean_default_state(tmp_path, base_name):
    mod, script, is_live = _load(base_name)
    path = tmp_path / "bad.json"
    path.write_text("{this is not json", encoding="utf-8")
    data = mod._load_track(path)
    assert data["edits"] == []
    assert data["runs"] == []


@pytest.mark.parametrize("base_name", ["dod_track", "critic_snapshot"])
def test_edge_missing_directory_is_created_on_write(base_name, tmp_path, monkeypatch):
    """dod_gate/main_gate НЕ параметризованы здесь СТРУКТУРНО: они
    пишут трек ТОЛЬКО когда `existed_before or updated_track.get("edits")`
    -- а сами эти хуки НЕ добавляют edits (это делает dod_track), так
    что "каталога нет -> этот хук его создаёт" применимо только к
    dod_track (первым пишет edit-факт) и critic_snapshot (пишет снимок
    безусловно на признанном payload'е). Для dod_gate/main_gate
    непустой трек с edits уже подразумевает существующий каталог --
    сценарий структурно не воспроизводим на этих двух."""
    mod, script, is_live = _load(base_name)
    assert not (tmp_path / ".claude").exists()

    if base_name == "critic_snapshot":
        payload = _critic_payload(tmp_path)
        _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
        assert (tmp_path / ".claude" / "critic_snapshot.json").exists()
        return

    payload = _dod_track_edit_payload(tmp_path)
    _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert (tmp_path / ".claude" / "dod_track").is_dir()


def test_edge_session_id_with_path_separators_fixed_as_is(tmp_path):
    """Не-цель спеки: валидация session_id НЕ вводится -- путь с "../"
    фиксируется КАК ЕСТЬ (строкой очереди, не батч). Чистая функция,
    без реального I/O по опасному пути."""
    mod, script, is_live = _load("dod_track")
    path = mod._track_path(str(tmp_path), "../../evil")
    assert path == Path(str(tmp_path)) / ".claude" / "dod_track" / "../../evil.json"


# ===========================================================================
# Адверсариальная батарея: вложенность 200; payload 1МБ/5МБ; \x00 и
# \r\n; не-UTF8 (errors=replace -- пин).
# ===========================================================================


def _deeply_nested(depth: int):
    node = {"leaf": True}
    for _ in range(depth):
        node = {"nested": node}
    return node


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_adversarial_deep_nesting_200_does_not_crash(base_name, tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load(base_name)
    if base_name == "critic_snapshot":
        payload = _critic_payload(tmp_path)
    elif base_name == "dod_track":
        payload = _dod_track_edit_payload(tmp_path)
    elif base_name == "dod_gate":
        payload = _subagent_stop_payload(tmp_path)
    else:
        payload = _stop_payload(tmp_path)
    payload["extra_deep_field"] = _deeply_nested(200)

    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc in (0, 2)  # 2 -- легитимный блок gate'ов на нарушении инварианта


@pytest.mark.parametrize("size_bytes", [1_000_000, 5_000_000])
def test_adversarial_large_payload_1mb_5mb_dod_track(size_bytes, tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load("dod_track")
    big_stdout = ("x" * (size_bytes - len(" passed"))) + " passed"
    payload = _dod_track_bash_payload(tmp_path, stdout=big_stdout)
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0
    track_path = tmp_path / ".claude" / "dod_track" / "s-1.json"
    data = json.loads(track_path.read_text(encoding="utf-8"))
    assert data["runs"][0]["outcome"] == "green"


def test_adversarial_nul_and_crlf_in_command_dod_track(tmp_path, monkeypatch):
    mod, script, is_live = _load("dod_track")
    command = "pytest -q\r\n\x00 passed"
    payload = _dod_track_bash_payload(tmp_path, command=command, stdout="1 passed")
    rc = _run_main(mod, json.dumps(payload).encode("utf-8"), monkeypatch)
    assert rc == 0


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_adversarial_non_utf8_stdin_replaced_not_crashed(base_name, tmp_path, monkeypatch, capsys):
    """errors="replace" уже стоит на байтовом stdin-чтении -- пин: не
    ронять хук на невалидных UTF-8 байтах."""
    mod, script, is_live = _load(base_name)
    raw = b'{"tool_name": "Edit", "tool_input": {"file_path": "\xff\xfe bad utf8 name.py"}, "session_id": "s-1", "cwd": "' + str(tmp_path).encode("utf-8").replace(b"\\", b"\\\\") + b'"}'
    monkeypatch.setattr(mod.sys, "stdin", _FakeStdin(raw))
    rc = mod.main()
    assert rc in (0, 2)


# ===========================================================================
# Мини sibling-first e2e-смок (subprocess) -- по одному на модуль,
# доказывает, что резолвленный ФАЙЛ реально запускается как отдельный
# процесс-хук (не только импортируется).
# ===========================================================================


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_e2e_subprocess_irrelevant_payload_is_noop(base_name, tmp_path):
    _mod, script, is_live = _load(base_name)
    payload = {"tool_name": "SomeUnrelatedTool", "session_id": "s-1", "cwd": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload).encode("utf-8"),
        cwd=str(tmp_path),
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not (tmp_path / ".claude").exists()


# ===========================================================================
# УЗЕЛ B -- F-61 session_context (builder, 2026-08-19, docs/tasks/
# 2026-08-19_f61-f58-remediation-spec.md, узел B). Дозапись в этот файл
# (Р2а спеки): та же F61_TARGET индирекция, _load("session_context")
# резолвится в tools/session_context_f61.py, если он существует (default),
# либо в живой tools/session_context.py (F61_TARGET=live -- контр-прогон,
# КРАСНЫЙ до посадки: ack происходит ДО печати на живом коде, F-61 экз. 3).
#
# Ключи узла B:
#  B1 -- ack ТОЛЬКО после успешной выдачи, КОНСТРУКЦИЕЙ (ключи строк,
#        реально вошедших в срез и напечатанных), не позиционно.
#  B2 -- одна запись вывода + flush ВНУТРИ try.
#  B3/fix5 (критик, пересдача 2026-08-19, fit_with_fixes) -- предупреждение
#        СНАЧАЛА в stdout (та же строка, что видела бы здоровая выдача --
#        отказ СБОРКИ при исправном stdout обязан остаться видимым); ТОЛЬКО
#        если сама эта запись в stdout бросает (мёртвый канал) -- фолбэк в
#        stderr; оба канала мертвы -> rc=0 молча. Обе попытки внутри try.
#  fix4 -- str(e) санитизируется через СУЩЕСТВУЮЩИЙ (не новый)
#        session_context._ascii_sanitize(text, 300) перед форматированием
#        строки предупреждения, на любом канале.
#  B4 -- guard не-dict корня в read_stdin_payload (образец
#        journal_echo.py:1885). NB (расхождение спеки с реальностью,
#        см. отчёт builder): тот же ключ спеки называет ещё и guard
#        "не-dict tool_input" -- у SessionStart-payload'а этого хука нет
#        поля tool_input вообще (см. .claude/settings.json: session_context
#        зарегистрирован только на SessionStart, не на PostToolUse/
#        PreToolUse) -- второй половине ключа применять некуда.
#
# Существующие тесты tools/test_session_context.py И
# tools/test_session_context_autoboot.py НЕ трогаются этим батчем --
# ПЯТЬ их пинов канала/шва (перечитаны в этом дереве builder'ом узла B
# при пересдаче по вердикту критика 2026-08-19) требуют двухмирной
# правки. Эти правки НЕ выполняются здесь (живые тест-файлы вне owns
# узла B) -- они часть акта посадки Lead (см. handoff в отчёте
# builder'а, готовые диффы + witness проверки на копии дерева в
# scratchpad).
# ===========================================================================


def _seed_sc_repo(tmp_path: Path) -> Path:
    """Минимальный сид для session_context.main()/build_context_lines():
    только logs/routing-log.jsonl -- gateway/* НЕ обязателен (quota_lines
    уже fail-open на отсутствующем gateway/, проверено эмпирически)."""
    root = tmp_path
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    return root


def _write_bg_fact(track_dir: Path, session_id: str, ts: str = "t1", reason: str = "no-green-run") -> Path:
    track_dir.mkdir(parents=True, exist_ok=True)
    path = track_dir / f"{session_id}.json"
    path.write_text(
        json.dumps({"main_gate_state": {"unsafe_completion": {"ts": ts, "reason": reason}}}),
        encoding="utf-8",
    )
    return path


class _FakeTextStdin:
    """ДВУХМИРНЫЙ пин (перепин П4/K10, builder, 2026-08-19,
    docs/tasks/2026-08-19_p4-stdin-deadline-spec.md): этот файл всегда
    резолвит "session_context" на ЖИВОЙ tools/session_context.py (нет
    tools/session_context_f61.py -- F61_TARGET здесь не влияет), так что
    ниже проверяется ТЕКУЩИЙ мир этого файла буквально. Форма фейка,
    однако, специально совместима с ОБОИМИ мирами читателя:
     - МИР ДО посадки П4 (сегодняшний живой session_context.py):
       read_stdin_payload() читает sys.stdin.read() НАПРЯМУЮ (ТЕКСТ, не
       .buffer, в отличие от dod_track/critic_snapshot/dod_gate/
       main_gate) -- этот фейк подходит буквально (только .read()/
       .isatty(), без .buffer).
     - МИР ПОСЛЕ посадки П4 (tools/session_context_p4.py, живёт СЕЙЧАС
       рядом как сиблинг батча П4): read_stdin_payload() читает БАЙТЫ
       через общий stdin-deadline хелпер (`_read_stdin_bytes_deadline()`)
       + decode("utf-8", "replace") -- К10. Тот же фейк остаётся
       совместим и там: хелпер берёт `stream = getattr(stdin, "buffer",
       stdin)`, у этого фейка `.buffer` нет -- значит `stream` это сам
       фейк, `stream.read()` возвращает str, хелпер сам приводит
       нестрочный (не-bytes) результат через
       `str(data).encode("utf-8", "replace")` -- проверено отдельной
       батареей tools/test_p4_stdin_deadline.py
       (test_k10_session_context_text_only_fake_still_works). Отдельный
       фейк от _FakeStdin выше (та несёт .buffer, эта -- нет)."""

    def __init__(self, text: str, tty: bool = False):
        self._text = text
        self._tty = tty

    def isatty(self):
        return self._tty

    def read(self):
        return self._text


class _MarkerRaisingStdout:
    """Раскалывает ЛЮБОЙ write(), чей аргумент содержит `marker` -- всё,
    что было успешно записано ДО этого, накапливается в .chunks (можно
    проверить, дошло ли хоть что-то). На сиблинге (B2: одна запись) весь
    вывод -- ОДИН write()-вызов, так что маркер где угодно внутри рвёт
    этот единственный вызов целиком, ничего не доходит. На живом коде
    (много print()) маркер рвёт вызов ИМЕННО в этой позиции -- строки до
    неё уже могли быть напечатаны, но факт был ack'нут ещё РАНЬШЕ печати
    (F-61 экз. 3), так что ack-дискриминатор одинаково красен на всех трёх
    позициях маркера."""

    def __init__(self, marker: str):
        self._marker = marker
        self.chunks = []
        self.raised = False

    def write(self, s):
        if self._marker in s:
            self.raised = True
            raise OSError(f"simulated stdout failure at marker {self._marker!r} (test)")
        self.chunks.append(s)
        return len(s)

    def flush(self):
        pass


class _RecordingStream:
    def __init__(self):
        self.chunks = []

    def write(self, s):
        self.chunks.append(s)
        return len(s)

    def flush(self):
        pass


class _AlwaysRaisingStream:
    def write(self, s):
        raise OSError("simulated channel down (test)")

    def flush(self):
        raise OSError("simulated channel down (test)")


class _CountingStdout:
    """Оборачивает РЕАЛЬНЫЙ (уже подменённый capsys) sys.stdout -- считает
    write()/flush() вызовы, но реально делегирует запись, чтобы
    capsys.readouterr() продолжал видеть содержимое."""

    def __init__(self, real):
        self._real = real
        self.write_calls = 0
        self.flush_calls = 0

    def write(self, s):
        self.write_calls += 1
        return self._real.write(s)

    def flush(self):
        self.flush_calls += 1
        return self._real.flush()


# ---------------------------------------------------------------------
# B2 -- одна запись вывода + flush ВНУТРИ try.
# ---------------------------------------------------------------------


def test_session_context_b2_main_writes_output_exactly_once_with_flush(tmp_path, monkeypatch, capsys):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    spy = _CountingStdout(mod.sys.stdout)
    monkeypatch.setattr(mod.sys, "stdout", spy)

    rc = mod.main(root)

    assert rc == 0
    label = "live" if is_live else "sibling"
    assert spy.write_calls == 1, (
        f"[{label}] ожидалась РОВНО одна запись stdout (B2), вызовов: {spy.write_calls}"
    )
    assert spy.flush_calls >= 1, f"[{label}] flush() не был вызван внутри try (B2)"
    out = capsys.readouterr().out
    assert "NOW:" in out
    assert "AUTO-BOOT (D-0103" in out


# ---------------------------------------------------------------------
# B1 -- ack ТОЛЬКО после успешной выдачи, КОНСТРУКЦИЕЙ (не позиционно).
# Отказ канала на первой строке / в середине / на autoboot-блоке -- все
# три должны красно ловить ack-до-печати на живом коде (F-61, экз. 3).
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "marker",
    ["NOW:", "GATE BREAK-GLASS", "AUTO-BOOT (D-0103", "--- END BOOT LAYER A:"],
    ids=["first-line", "middle-break-glass", "autoboot-block", "layer-a-close"],
)
def test_session_context_b1_stdout_failure_leaves_break_glass_fact_unacked(marker, tmp_path, monkeypatch):
    mod, script, is_live = _load("session_context")
    if marker == "--- END BOOT LAYER A:" and not hasattr(mod, "_LAYER_A_FILES"):
        pytest.skip(
            "--- END BOOT LAYER A: marker: D-0104 HYBRID Layer A block not landed "
            "on this target yet, nothing to break on"
        )
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, "sess-b1")

    candidates_before = mod._break_glass_candidates(root)
    assert len(candidates_before) == 1, "sanity: ожидался ровно один pending-факт до прогона"
    fact_key = candidates_before[0]["key"]
    assert fact_key

    monkeypatch.setattr(mod.sys, "stdout", _MarkerRaisingStdout(marker))
    err_fake = _RecordingStream()
    monkeypatch.setattr(mod.sys, "stderr", err_fake)

    raised = None
    rc = None
    try:
        rc = mod.main(root)
    except Exception as exc:  # noqa: BLE001 -- exactly what we're probing
        raised = exc

    label = "live" if is_live else "sibling"
    assert raised is None, f"[{label}, marker={marker!r}] main() бросил наружу: {raised!r}"
    assert rc == 0

    ack_data = mod._load_break_glass_ack(mod._break_glass_ack_path(root))
    assert fact_key not in ack_data, (
        f"[{label}, marker={marker!r}] факт ack'нут ДО того, как его строка реально "
        f"была выдана (F-61, экз. 3: ack внутри build_context_lines ДО печати) -- "
        f"ack_data={ack_data!r}"
    )
    err_text = "".join(err_fake.chunks)
    assert "session-context warning:" in err_text, (
        f"[{label}, marker={marker!r}] fail-open предупреждение не дошло до stderr: {err_text!r}"
    )


# ---------------------------------------------------------------------
# B3/fix5 (критик, пересдача 2026-08-19: fit_with_fixes) -- предупреждение
# пишется СНАЧАЛА в stdout (та же строка, что видела бы здоровая выдача);
# фолбэк в stderr ТОЛЬКО если сама эта запись в stdout бросает (мёртвый
# канал, не просто отказ сборки); оба канала мертвы -> rc=0 молча.
# ---------------------------------------------------------------------


def test_session_context_fix5a_build_failure_with_healthy_stdout_shows_warning_on_stdout(
    tmp_path, monkeypatch, capsys
):
    """(а) отказ СБОРКИ (битый read_journal_events -- тот же класс, что
    исторический инцидент с битым журналом/quota) при ИСПРАВНОМ stdout:
    предупреждение обязано попасть в stdout (не потеряться в stderr,
    который сессия не обязательно читает), stderr остаётся пустым."""
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("boom-fix5a-healthy-stdout (test)")

    monkeypatch.setattr(mod, "read_journal_events", _boom)

    rc = mod.main(root)
    assert rc == 0

    label = "live" if is_live else "sibling"
    captured = capsys.readouterr()
    assert "session-context warning: boom-fix5a-healthy-stdout (test)" in captured.out, (
        f"[{label}] предупреждение не найдено в ИСПРАВНОМ stdout: {captured.out!r}"
    )
    assert captured.err == "", (
        f"[{label}] предупреждение утекло в stderr при исправном stdout: {captured.err!r}"
    )


def test_session_context_fix5b_dead_stdout_falls_back_to_stderr(tmp_path, monkeypatch):
    """(б) stdout ГЕНУИННО мёртв (сама запись предупреждения бросает, не
    только сборка) -> фолбэк на stderr, ТА ЖЕ строка."""
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)

    monkeypatch.setattr(mod.sys, "stdout", _AlwaysRaisingStream())
    err_fake = _RecordingStream()
    monkeypatch.setattr(mod.sys, "stderr", err_fake)

    raised = None
    rc = None
    try:
        rc = mod.main(root)
    except Exception as exc:  # noqa: BLE001
        raised = exc

    label = "live" if is_live else "sibling"
    assert raised is None, f"[{label}] main() бросил наружу при мёртвом stdout: {raised!r}"
    assert rc == 0
    err_text = "".join(err_fake.chunks)
    assert "session-context warning:" in err_text, (
        f"[{label}] предупреждение не дошло до stderr-фолбэка: {err_text!r}"
    )


def test_session_context_fix5c_both_channels_dead_returns_zero_silently(tmp_path, monkeypatch):
    """(в) оба канала мертвы -> rc=0 молча, никакого исключения наружу."""
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("boom-fix5c-both-dead (test)")

    monkeypatch.setattr(mod, "read_journal_events", _boom)
    monkeypatch.setattr(mod.sys, "stdout", _AlwaysRaisingStream())
    monkeypatch.setattr(mod.sys, "stderr", _AlwaysRaisingStream())

    raised = None
    rc = None
    try:
        rc = mod.main(root)
    except Exception as exc:  # noqa: BLE001
        raised = exc

    label = "live" if is_live else "sibling"
    assert raised is None, (
        f"[{label}] main() бросил наружу при отказе ОБОИХ каналов (rc=0 молча ожидался): {raised!r}"
    )
    assert rc == 0


# ---------------------------------------------------------------------
# fix4 (критик, пересдача 2026-08-19) -- str(e) санитизируется через
# СУЩЕСТВУЮЩИЙ session_context._ascii_sanitize(text, 300) (тот же хелпер,
# что уже используют MODEL/OPEN DISPATCH/WIRING -- НЕ новый хелпер, см.
# отчёт builder'а) перед форматированием строки предупреждения, на ЛЮБОМ
# канале. Лимит 300 -- НОВОЕ место применения этого хелпера в файле =>
# отдельный граничный тест (правило 6а), не только позитивный кейс с
# кириллицей/переводами строк.
# ---------------------------------------------------------------------


def test_session_context_fix4_warning_message_is_ascii_sanitized_single_line(
    tmp_path, monkeypatch, capsys
):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("клод\nпричина с кириллицей\r\nвторая строка")

    monkeypatch.setattr(mod, "read_journal_events", _boom)

    rc = mod.main(root)
    assert rc == 0

    label = "live" if is_live else "sibling"
    combined = capsys.readouterr().out  # здоровый stdout -> fix5(а) кладёт сюда
    warning_lines = [l for l in combined.splitlines() if l.startswith("session-context warning:")]
    assert len(warning_lines) == 1, (
        f"[{label}] ожидалась РОВНО одна строка предупреждения: {combined!r}"
    )
    assert warning_lines[0].isascii(), (
        f"[{label}] предупреждение не ASCII-safe (кириллица/не-ASCII не санитизированы): "
        f"{warning_lines[0]!r}"
    )


def test_session_context_fix4_warning_length_at_300_boundary_not_truncated(
    tmp_path, monkeypatch, capsys
):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("x" * 300)

    monkeypatch.setattr(mod, "read_journal_events", _boom)
    rc = mod.main(root)
    assert rc == 0
    combined = capsys.readouterr().out
    assert f"session-context warning: {'x' * 300}" in combined


def test_session_context_fix4_warning_length_beyond_300_boundary_truncated(
    tmp_path, monkeypatch, capsys
):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("y" * 301)

    monkeypatch.setattr(mod, "read_journal_events", _boom)
    rc = mod.main(root)
    assert rc == 0
    combined = capsys.readouterr().out
    label = "live" if is_live else "sibling"
    assert f"session-context warning: {'y' * 300}" in combined, (
        f"[{label}] за границей (301) ожидалось усечение ровно до 300 символов: {combined!r}"
    )
    assert "y" * 301 not in combined, (
        f"[{label}] полное непочиненное 301-символьное сообщение обнаружено -- нет усечения"
    )


# ---------------------------------------------------------------------
# B4 -- guard не-dict корня в read_stdin_payload.
# ---------------------------------------------------------------------


@pytest.mark.parametrize("bad_json", ["[1, 2, 3]", '"just a string"', "5", "true"])
def test_session_context_b4_read_stdin_payload_non_dict_root_returns_none(bad_json, tmp_path, monkeypatch):
    mod, script, is_live = _load("session_context")
    fake = _FakeTextStdin(bad_json, tty=False)
    monkeypatch.setattr(mod.sys, "stdin", fake)

    result = mod.read_stdin_payload()

    label = "live" if is_live else "sibling"
    assert result is None, (
        f"[{label}] non-dict корень {bad_json!r} должен давать None (B4), получено: {result!r}"
    )


def test_session_context_b4_read_stdin_payload_dict_root_still_returned(tmp_path, monkeypatch):
    mod, script, is_live = _load("session_context")
    fake = _FakeTextStdin('{"model": "claude-opus-4"}', tty=False)
    monkeypatch.setattr(mod.sys, "stdin", fake)
    assert mod.read_stdin_payload() == {"model": "claude-opus-4"}


# ---------------------------------------------------------------------
# Края: сайдкар отсутствует/битый -> повторный показ (fail-safe); битый
# трек пропускается по-файлово; границы MAX_LINES (25/26) и cap (5/6).
# ---------------------------------------------------------------------


def test_session_context_edge_sidecar_missing_is_treated_as_nothing_acked(tmp_path):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, "sess-sc-missing")
    ack_data = mod._load_break_glass_ack(mod._break_glass_ack_path(root))
    assert ack_data == {}


def test_session_context_edge_broken_sidecar_is_fail_safe_refires_fact(tmp_path):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, "sess-sc-broken")

    first = mod.break_glass_lines(root)
    assert len(first) == 1
    ack_path = track_dir / "break_glass_ack.json"
    assert ack_path.exists()

    ack_path.write_text("{not valid json", encoding="utf-8")  # corrupt the sidecar
    second = mod.break_glass_lines(root)
    assert len(second) == 1, "битый сайдкар должен fail-safe пересветить факт, а не проглотить его"


def test_session_context_edge_broken_track_file_skipped_per_file_siblings_still_shown(tmp_path):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    track_dir.mkdir(parents=True)
    (track_dir / "broken.json").write_text("{not valid json", encoding="utf-8")
    _write_bg_fact(track_dir, "sess-good")

    lines = mod.break_glass_lines(root)
    assert len(lines) == 1
    assert "sess-good" in lines[0]


def test_session_context_edge_max_lines_no_space_left_does_not_ack(tmp_path):
    # AT the MAX_LINES boundary, from the far side: 0 slots left (25 lines
    # of filler already fill the whole budget) -- the pending fact must be
    # neither shown nor acked.
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, "sess-edge-nospace")

    filler = ["x"] * mod.MAX_LINES  # space_left == 0
    shown = mod.select_and_ack_break_glass_lines(root, filler)
    assert shown == []

    shown_again = mod.select_and_ack_break_glass_lines(root, [])
    assert len(shown_again) == 1  # still pending -- never acked


def test_session_context_edge_max_lines_exact_one_slot_boundary_fits_and_acks(tmp_path):
    # 24 lines of filler -> exactly 1 slot left (25th line) -- AT the
    # boundary, the single pending fact fits and gets acked.
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, "sess-edge-oneslot")

    filler = ["x"] * (mod.MAX_LINES - 1)
    shown = mod.select_and_ack_break_glass_lines(root, filler)
    assert len(shown) == 1

    shown_again = mod.select_and_ack_break_glass_lines(root, [])
    assert shown_again == []  # already acked


def test_session_context_edge_fact_cap_exactly_five_no_summary(tmp_path):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    for i in range(5):
        _write_bg_fact(track_dir, f"sess-cap-{i}", ts=f"t{i}")

    lines = mod.break_glass_lines(root)
    assert len(lines) == 5
    assert not any("more unsafe-completion facts pending" in l for l in lines)


def test_session_context_edge_fact_cap_six_gets_summary_and_leaves_sixth_unacked(tmp_path):
    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    for i in range(6):
        _write_bg_fact(track_dir, f"sess-cap6-{i}", ts=f"t{i}")

    lines = mod.break_glass_lines(root)
    fact_lines = [l for l in lines if l.startswith("GATE BREAK-GLASS: session")]
    summary_lines = [l for l in lines if "more unsafe-completion facts pending" in l]
    assert len(fact_lines) == 5
    assert len(summary_lines) == 1
    assert "1 more" in summary_lines[0]

    # НЕ-ack невошедшего (шестого) факта: следующий вызов обязан его показать.
    second = mod.break_glass_lines(root)
    assert len(second) == 1
    assert second[0].startswith("GATE BREAK-GLASS: session")


# ---------------------------------------------------------------------
# Сторож неизменности РЕАЛЬНОГО .claude/ -- все пробы этой секции только
# на tmp-дереве. Снимок mtime всего дерева был бы флаки в этом окружении
# (CLAUDE.md: "в дереве работают параллельные воркеры" -- другие живые
# сессии тоже пишут в реальный .claude/dod_track/ конкурентно) -- вместо
# этого ищем УНИКАЛЬНЫЙ (uuid4) маркер синтетической сессии теста: его
# отсутствие в реальном дереве коллизионно невозможно спутать с чужой
# конкурентной активностью, а его присутствие в tmp-дереве (позитивный
# контроль) доказывает, что сам механизм поиска работает.
# ---------------------------------------------------------------------


def test_real_repo_claude_dir_untouched_by_session_context_battery(tmp_path):
    import uuid

    unique_session = f"f61-node-b-guard-{uuid.uuid4().hex}"
    real_claude = TOOLS_DIR.parent / ".claude"

    mod, script, is_live = _load("session_context")
    root = _seed_sc_repo(tmp_path)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, unique_session)
    mod.main(root)
    mod.break_glass_lines(root)

    # Позитивный контроль (rule 6): маркер ДЕЙСТВИТЕЛЬНО найден там, куда
    # тест сам писал (tmp-дерево) -- иначе отсутствие на боевой стороне
    # ничего не доказывает (пустой результат непроверенного поиска).
    tmp_hits = list(root.rglob(f"*{unique_session}*"))
    assert tmp_hits, "sanity: маркер не найден даже в tmp-дереве -- проверка сломана"

    name_hits = list(real_claude.rglob(f"*{unique_session}*")) if real_claude.exists() else []
    ack_path = real_claude / "dod_track" / "break_glass_ack.json"
    ack_hit = ack_path.exists() and unique_session in ack_path.read_text(
        encoding="utf-8", errors="replace"
    )
    assert not name_hits and not ack_hit, (
        f"боевой .claude/ репозитория несет след синтетической сессии теста "
        f"-- root= где-то внутри съехал на репозиторный корень по умолчанию: "
        f"name_hits={name_hits!r} ack_hit={ack_hit!r}"
    )
