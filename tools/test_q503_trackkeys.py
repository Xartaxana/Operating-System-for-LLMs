"""tools/test_q503_trackkeys.py -- Q503 узел N1 батарея (builder t-521,
2026-08-19, docs/tasks/2026-08-19_q503-remediation-spec.md): К1-К5,
потеря ЧУЖИХ ключей трека при битом JSON, ТРИ писателя
(tools/dod_track.py, tools/dod_gate.py, tools/main_gate.py -- все три
"_load_track()" читают/пишут .claude/dod_track/<session_id>.json).

ФОРМА (образец tools/test_f61_halfstate.py:73-112, env Q503_TARGET
вместо F61_TARGET): цель разрешается per-модульно через
_resolve_module_path():
 - Q503_TARGET=live -> ВСЕГДА живой tools/<name>.py (контр-прогон --
   ОБЯЗАН быть КРАСНЫМ на дискриминирующих тестах ниже, класс Q503
   ещё не починен там).
 - Q503_TARGET не задан (default) -> сиблинг tools/<name>_q503.py,
   если он существует, иначе живой файл -- RERUNNABLE кем угодно без
   правки кода (посадка Lead уберёт сиблинги, мир 3: контр-режима
   тогда не существует, батарея просто проверяет живой/починенный
   путь -- см. test_f61_halfstate.py:73-90 за то же рассуждение).
Модуль резолвится и импортируется через importlib.util (sibling-first
индирекция, не хардкод боевого пути в SCRIPT-константе).

Существующие tools/test_dod_track.py, tools/test_dod_gate.py,
tools/test_main_gate.py НЕ ТРОГАЮТСЯ этим узлом -- их SCRIPT жёстко на
боевой путь (test_dod_track.py:31, аналогично dod_gate/main_gate) --
их зелёный прогон БЕЗ правок живых файлов доказывает, что эта батарея
не задевает существующее поведение.

Ключи спеки (docs/tasks/2026-08-19_q503-remediation-spec.md, узел N1):
 K1 -- класс ко ВСЕМ ТРЁМ писателям, перечисление с вердиктом, вкл.
      ветку "корень не-dict" у каждого (см. таблица ниже + тесты
      test_nondict_root_is_quarantined/test_own_section_broken_*).
 K2 -- форма Р4(а)+(в) реализована ОДИНАКОВО во всех трёх
      (_quarantine_bad_track -- ЛОКАЛЬНАЯ копия дословно в каждом из
      трёх сиблингов; проверяется тем, что ОДНА и та же батарея тестов
      параметризована по всем трём модулям и зелена на каждом).
 K3 -- докстринг dod_track_q503.py:104-150 (копия живых :104-150)
      приведён к правде -- прозаический K, проверяется чтением диффа
      в отчёте, не отдельным автотестом (докстринг -- не поведение).
 K4 -- fail-open буквально (rc-контракты не меняются) --
      test_subprocess_rc_contract_unchanged_under_corruption.
 K5 -- дискриминирующий тест "чужие ключи не исчезли" с красным
      контр-прогоном на живом коде -- ДВЕ формы (обе половины,
      quarantine-ветка и per-key-ветка):
       (i) test_unparseable_text_is_quarantined /
           test_zero_byte_file_is_quarantined /
           test_nondict_root_is_quarantined -- на LIVE ни один файл не
           заквантинен -> оригинальные байты (с любыми чужими ключами
           внутри) исчезают БЕССЛЕДНО при следующей перезаписи --
           красно; на FIXED -- квaрантинный файл с оригинальными
           байтами лежит рядом -- зелено.
       (ii) test_own_section_broken_*_preserves_foreign_key -- на
           LIVE своя секция неверного типа либо остаётся неисправленной
           (dod_track: setdefault не трогает существующий ключ), либо
           роняет _load_track() исключением (dod_gate/main_gate:
           `.setdefault()` на списке) -- красно в обоих случаях; на
           FIXED -- своя секция чинится, ЧУЖОЙ ключ доказуемо не
           тронут -- зелено.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TOOLS_DIR = Path(__file__).resolve().parent
Q503_TARGET = os.environ.get("Q503_TARGET", "").strip().lower()
MODULE_NAMES = ("dod_track", "dod_gate", "main_gate")


def _resolve_module_path(base_name: str) -> "tuple[Path, bool]":
    """(путь, is_unpatched) -- та же форма, что
    test_f61_halfstate.py:_resolve_module_path (образец, DoD "дано").
    is_unpatched=True означает "цель заведомо непочинена" и легален
    ТОЛЬКО в контр-режиме Q503_TARGET=live при существующем сиблинге."""
    live = TOOLS_DIR / f"{base_name}.py"
    sibling = TOOLS_DIR / f"{base_name}_q503.py"
    if Q503_TARGET == "live":
        return live, sibling.exists()
    if sibling.exists():
        return sibling, False
    return live, False


_MODULE_CACHE: dict = {}


def _load(base_name: str):
    path, _is_unpatched = _resolve_module_path(base_name)
    cache_key = (base_name, str(path))
    if cache_key not in _MODULE_CACHE:
        alias = f"q503_battery_{base_name}_{path.stem}"
        spec = importlib.util.spec_from_file_location(alias, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULE_CACHE[cache_key] = module
    return _MODULE_CACHE[cache_key], path


def _default_track_dict(mod, base_name: str) -> dict:
    if base_name == "dod_track":
        return {"edits": [], "runs": []}
    if base_name == "dod_gate":
        return {"edits": [], "runs": [], "gate_state": mod._default_gate_state()}
    if base_name == "main_gate":
        return mod._default_track()
    raise AssertionError(base_name)


def _track_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".claude" / "dod_track"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _run_hook(script_path: Path, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script_path)],
        input=json.dumps(payload),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------
# Край: "файла нет -> существующее поведение дословно" (regression pin)
# ---------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_missing_file_returns_documented_default(base_name, tmp_path):
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    path = track_dir / "no-such-session.json"
    assert not path.exists()
    result = mod._load_track(path)
    assert result == _default_track_dict(mod, base_name)
    # Read-only -- ничего не должно быть создано на диске.
    assert not path.exists()


# ---------------------------------------------------------------------
# K5(i) -- нераспарсиваемый текст / 0 байт / не-dict корень -> КАРАНТИН.
# Красный контр-прогон на живом коде: живой код НЕ квaрантинит --
# оригинальные байты (со всеми чужими ключами внутри) остаются на
# боевом пути ДО следующей перезаписи, но батарея проверяет само
# отсутствие карантина -- достаточный дискриминатор без ожидания
# перезаписи (K1: "не роняем хук" уже верно на живом, "не теряем
# чужое БЕЗ СЛЕДА при следующей записи" -- НЕТ).
# ---------------------------------------------------------------------


_FOREIGN_MARKER = "KEEP-ME-Q503-FOREIGN-MARKER"


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_unparseable_text_is_quarantined(base_name, tmp_path):
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    session_id = "sess-corrupt-1"
    path = track_dir / f"{session_id}.json"
    # Обрубок валидного JSON -- реалистичная форма (truncated write),
    # несёт УЗНАВАЕМУЮ подстроку с именем чужого ключа и маркером --
    # ровно то, что должно "не исчезнуть бесследно".
    corrupt_bytes = (
        '{"edits": [], "runs": [], "gate_state": {"marker": "'
        + _FOREIGN_MARKER
        + '"'
    ).encode("utf-8")
    path.write_bytes(corrupt_bytes)

    result = mod._load_track(path)

    assert result == _default_track_dict(mod, base_name), (
        "K4: fail-open в памяти на нераспарсиваемом тексте должен "
        "остаться прежним (свежий дефолт), а не измениться"
    )

    quarantine_files = [
        p for p in track_dir.iterdir() if p != path and p.name.startswith(session_id)
    ]
    assert quarantine_files, (
        "K5(i) КРАСНО НА ЖИВОМ: файл не заквантинен -- "
        f"маркер {_FOREIGN_MARKER!r} нигде не сохранён, будет стёрт "
        "бесследно при следующей записи трека"
    )
    for q in quarantine_files:
        assert not q.name.endswith(".json"), (
            "карантинное имя оканчивается на .json -- "
            "session_context.py:1649 глобит *.json и примет осколок "
            "за чужой session_id"
        )
    assert any(
        q.read_bytes() == corrupt_bytes for q in quarantine_files
    ), "оригинальные байты (с маркером) не совпадают ни с одним карантинным файлом"


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_zero_byte_file_is_quarantined(base_name, tmp_path):
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    session_id = "sess-empty-1"
    path = track_dir / f"{session_id}.json"
    path.write_bytes(b"")

    result = mod._load_track(path)

    assert result == _default_track_dict(mod, base_name)
    quarantine_files = [
        p for p in track_dir.iterdir() if p != path and p.name.startswith(session_id)
    ]
    assert quarantine_files, "K5(i) КРАСНО НА ЖИВОМ: 0-байтовый файл не заквантинен"
    for q in quarantine_files:
        assert not q.name.endswith(".json")
        assert q.read_bytes() == b""


@pytest.mark.parametrize("base_name", MODULE_NAMES)
@pytest.mark.parametrize(
    "root_json",
    ["null", "[1, 2, 3]", "42", '"just a string"'],
    ids=["null", "list", "number", "string"],
)
def test_nondict_root_is_quarantined(base_name, root_json, tmp_path):
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    session_id = f"sess-root-{hash(root_json) & 0xffff}"
    path = track_dir / f"{session_id}.json"
    path.write_text(root_json, encoding="utf-8")

    result = mod._load_track(path)

    assert result == _default_track_dict(mod, base_name), (
        "Р4 'края': корень не-dict -- та же ветка, что битый -- "
        "fail-open в памяти не меняется"
    )
    quarantine_files = [
        p for p in track_dir.iterdir() if p != path and p.name.startswith(session_id)
    ]
    assert quarantine_files, (
        f"K5(i) КРАСНО НА ЖИВОМ: не-dict корень ({root_json}) не заквантинен"
    )
    for q in quarantine_files:
        assert not q.name.endswith(".json")
        assert q.read_text(encoding="utf-8") == root_json


# ---------------------------------------------------------------------
# Карантинные края: уникализация mkstemp / карантин невозможен.
# Прямой тест _quarantine_bad_track() -- на LIVE атрибута нет вовсе
# (AttributeError -- легитимно красно, функция ещё не существует там).
# ---------------------------------------------------------------------


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_quarantine_filename_never_ends_with_json(base_name, tmp_path):
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    path = track_dir / "sess-name-1.json"
    path.write_bytes(b"not json {{{")

    mod._quarantine_bad_track(path)

    assert not path.exists()
    remaining = list(track_dir.glob("*"))
    assert len(remaining) == 1
    quarantine_path = remaining[0]
    assert not quarantine_path.name.endswith(".json")
    json_glob = list(track_dir.glob("*.json"))
    assert quarantine_path not in json_glob


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_quarantine_uniqueness_via_mkstemp(base_name, tmp_path):
    """Край спеки: "карантин существует -> уникализация mkstemp" --
    квaрантинить ДВАЖДЫ файл с ОДНИМ И ТЕМ ЖЕ исходным именем (второй
    воссоздан после первого карантина) не должно коллизировать --
    mkstemp сам гарантирует уникальное имя каждый раз."""
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    path = track_dir / "sess-dup-1.json"

    path.write_bytes(b"corrupt-one")
    mod._quarantine_bad_track(path)

    path.write_bytes(b"corrupt-two")
    mod._quarantine_bad_track(path)

    assert not path.exists()
    quarantine_files = list(track_dir.glob("*"))
    assert len(quarantine_files) == 2, "два карантина должны сосуществовать без коллизии"
    names = {p.name for p in quarantine_files}
    assert len(names) == 2, "карантинные имена должны быть РАЗНЫМИ (mkstemp-уникализация)"
    contents = {p.read_bytes() for p in quarantine_files}
    assert contents == {b"corrupt-one", b"corrupt-two"}, (
        "оба набора байт должны сохраниться, ни один не затёрт другим"
    )


@pytest.mark.parametrize("base_name", MODULE_NAMES)
def test_quarantine_impossible_is_fail_open(base_name, tmp_path, monkeypatch):
    """Край спеки: "карантин невозможен (read-only) -> существующий
    fail-open без нового исключения". Эмпирика (командная гигиена
    п.6): на этой Windows-машине ни read-only БИТ каталога (os.chmod),
    ни read-only БИТ самого файла реально НЕ блокируют
    tempfile.mkstemp()/os.replace() (проверено отдельно, вне этого
    файла -- os.replace успешно переименовывает read-only файл,
    mkstemp успешно создаёт файл в read-only каталоге) -- реального
    воспроизведения через chmod на этой машине НЕТ, поэтому
    механизм-уровневый мок (tempfile.mkstemp кидает OSError) --
    единственная ДЕТЕРМИНИРОВАННАЯ форма этого края здесь: это ровно
    та точка, которая реально не сможет создать файл на настоящем
    read-only каталоге."""
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    path = track_dir / "sess-ro-1.json"
    path.write_bytes(b"not json {{{")

    def _boom(*a, **kw):
        raise OSError("simulated read-only directory (Q503 quarantine-impossible probe)")

    monkeypatch.setattr(mod.tempfile, "mkstemp", _boom)

    mod._quarantine_bad_track(path)  # НЕ должно поднять исключение

    assert path.exists(), "карантин невозможен -- оригинальный файл должен остаться на месте"
    assert path.read_bytes() == b"not json {{{"
    other_files = [p for p in track_dir.iterdir() if p != path]
    assert other_files == [], "неудавшийся карантин не должен оставлять частичных артефактов"


# ---------------------------------------------------------------------
# K5(ii) -- корень dict, СВОЯ секция неверного типа -> по-ключевая
# деградация, ЧУЖОЙ ключ доказуемо сохранён.
# ---------------------------------------------------------------------


def test_own_section_broken_dod_track_preserves_foreign_keys(tmp_path):
    mod, _path = _load("dod_track")
    track_dir = _track_dir(tmp_path)
    path = track_dir / "sess-own-track.json"
    track = {
        "edits": "not-a-list",  # своя секция dod_track, неверный тип
        "runs": [],
        "gate_state": {"consecutive_blocks": 3, "marker": _FOREIGN_MARKER},
        "main_gate_state": {"marker": _FOREIGN_MARKER + "-2"},
    }
    path.write_text(json.dumps(track), encoding="utf-8")

    try:
        result = mod._load_track(path)
    except Exception as exc:  # pragma: no cover -- КРАСНО НА ЖИВОМ, если крашнется
        pytest.fail(
            f"K5(ii) КРАСНО НА ЖИВОМ: _load_track подняло {exc!r} вместо "
            "по-ключевой деградации своей секции"
        )

    assert isinstance(result["edits"], list), (
        "K5(ii) КРАСНО НА ЖИВОМ: своя секция 'edits' неверного типа НЕ "
        "починена (setdefault не трогает уже существующий ключ)"
    )
    assert result["gate_state"] == {"consecutive_blocks": 3, "marker": _FOREIGN_MARKER}
    assert result["main_gate_state"] == {"marker": _FOREIGN_MARKER + "-2"}


@pytest.mark.parametrize(
    "base_name,own_key,foreign_key",
    [
        ("dod_gate", "gate_state", "main_gate_state"),
        ("main_gate", "main_gate_state", "gate_state"),
    ],
)
def test_own_section_broken_preserves_foreign_key(base_name, own_key, foreign_key, tmp_path):
    mod, _path = _load(base_name)
    track_dir = _track_dir(tmp_path)
    path = track_dir / "sess-own-section.json"
    track = {
        "edits": [],
        "runs": [],
        own_key: ["oops"],  # своя секция, СПИСОК вместо dict
        foreign_key: {"marker": _FOREIGN_MARKER},
        "gate_log": [{"action": "blocked", "marker": _FOREIGN_MARKER + "-log"}],
    }
    path.write_text(json.dumps(track), encoding="utf-8")

    try:
        result = mod._load_track(path)
    except Exception as exc:
        pytest.fail(
            f"K5(ii) КРАСНО НА ЖИВОМ: _load_track({base_name}) подняло "
            f"{exc!r} вместо по-ключевой деградации '{own_key}' -- "
            "'.setdefault()' на списке крашится, dod_gate/main_gate без "
            "тотального try (Р3а/A7)"
        )

    assert isinstance(result[own_key], dict), (
        f"K5(ii) КРАСНО НА ЖИВОМ: своя секция '{own_key}' не починена"
    )
    assert result[own_key].get("consecutive_blocks") == 0
    assert result[foreign_key] == {"marker": _FOREIGN_MARKER}, (
        f"чужой ключ '{foreign_key}' должен быть перенесён КАК ЕСТЬ (Р4в)"
    )
    assert result["gate_log"] == [
        {"action": "blocked", "marker": _FOREIGN_MARKER + "-log"}
    ], "чужой gate_log должен быть перенесён КАК ЕСТЬ"


# ---------------------------------------------------------------------
# K4 -- fail-open буквально: rc-контракты не меняются под полным
# хуком (subprocess), не только под прямым вызовом _load_track().
# ---------------------------------------------------------------------


def test_subprocess_dod_track_rc_unchanged_under_corruption(tmp_path):
    mod, script = _load("dod_track")
    track_dir = _track_dir(tmp_path)
    session_id = "sess-sub-track"
    path = track_dir / f"{session_id}.json"
    path.write_bytes(b"not json {{{")

    target_file = tmp_path / "x.py"
    target_file.write_text("x = 1\n", encoding="utf-8")
    payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(target_file)},
        "tool_response": {},
    }
    proc = _run_hook(script, payload, tmp_path)

    assert proc.returncode == 0, (
        f"K4: dod_track rc-контракт (всегда 0) нарушен под битым треком: "
        f"rc={proc.returncode} stderr={proc.stderr!r}"
    )
    assert "Traceback" not in proc.stderr, (
        f"K4 КРАСНО НА ЖИВОМ, если крашится: stderr={proc.stderr!r}"
    )


@pytest.mark.parametrize(
    "base_name,hook_event,own_key",
    [
        ("dod_gate", "SubagentStop", "gate_state"),
        ("main_gate", "Stop", "main_gate_state"),
    ],
)
def test_subprocess_rc_unchanged_under_own_section_corruption(
    base_name, hook_event, own_key, tmp_path
):
    """K4 (совместно с K5ii): под ПОЛНЫМ хуком (subprocess, не только
    прямым вызовом _load_track) -- битая своя секция не должна ни
    ронять процесс (traceback/ненулевой неожиданный rc), ни менять
    документированный rc-контракт (0, т.к. нет edits после сброса --
    'no-edits'/'no-main-edits')."""
    mod, script = _load(base_name)
    track_dir = _track_dir(tmp_path)
    session_id = f"sess-sub-{base_name}"
    path = track_dir / f"{session_id}.json"
    track = {
        "edits": [],
        "runs": [],
        own_key: ["oops"],
        "some_foreign_marker_holder": {"marker": _FOREIGN_MARKER},
    }
    path.write_text(json.dumps(track), encoding="utf-8")

    payload = {
        "session_id": session_id,
        "cwd": str(tmp_path),
        "hook_event_name": hook_event,
        "agent_id": "agent-1" if hook_event == "SubagentStop" else None,
    }
    proc = _run_hook(script, payload, tmp_path)

    assert proc.returncode == 0, (
        f"K4 КРАСНО НА ЖИВОМ: {base_name} rc-контракт нарушен под битой "
        f"своей секцией: rc={proc.returncode} stderr={proc.stderr!r}"
    )
    assert "Traceback" not in proc.stderr, (
        f"K4 КРАСНО НА ЖИВОМ: {base_name} крашится под битой своей "
        f"секцией вместо fail-open: stderr={proc.stderr!r}"
    )
