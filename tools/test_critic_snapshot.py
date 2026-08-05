"""Tests for tools/critic_snapshot.py (доборный батч t-353, 2026-08-05 --
корзина не дала owns на этот файл в исходном батче, gate у critic_snapshot
тестов не было ВООБЩЕ до этой правки: проверено `grep -r critic_snapshot
tools/` -- находил только сам critic_snapshot.py + докстринг-упоминания в
dispatch_gate.py/hygiene_gate.py + parity_manifest.json, 0 тестовых
файлов).

Стиль форм подачи payload -- ТОТ ЖЕ, что tools/test_dispatch_gate.py
использует для своих subprocess-смоков хука (`_run_hook`: sys.executable
+ SCRIPT, JSON payload через stdin, ensure_ascii=False -> encode utf-8) --
второй способ не изобретён (край (iii) спеки доборного батча).

Две ГРУППЫ тестов:
  (A) E2E через subprocess -- публичный контракт хука (какие payload'ы
      игнорируются, штатная запись снимка, cwd СТРОГО из payload, а не из
      реального процесса) -- см. `_run_hook`.
  (B) In-process прямой импорт `critic_snapshot` -- для веток, которые
      subprocess не даёт детерминированно вызвать (обход дерева ломается
      ИЛИ запись снимка ломается): монкипатчатся внутренние функции/
      `Path.write_text`/`sys.stdin` этого же процесса. Обоснование этого
      выбора (край (i) спеки): попытка "нечитаемого файла" через chmod на
      Windows ненадёжна -- NTFS-права владельца-процесса игнорируют
      read-only бит для чтения содержимого (только для записи), так что
      `chmod(0o000)` не помешал бы `Path.read_bytes()` в этом же
      процессе; вместо этого монкипатчится `Path.read_bytes` для ОДНОГО
      конкретного пути -- задокументировано здесь и в докстринге
      конкретного теста, не угадано молча.

КРАЙ (ii) спеки -- снимок пишется в cwd ИЗ PAYLOAD, не из реального
процесса (см. critic_snapshot.py main(): `cwd = Path(payload.get("cwd")
or ".")`): каждый пишущий тест ниже ЯВНО передаёт payload["cwd"] =
str(tmp_path); отдельный тест
(`test_real_repo_snapshot_untouched_by_tmp_path_dispatch`) утверждает
это отдельно -- снимает байты РЕАЛЬНОГО .claude/critic_snapshot.json ДО
и ПОСЛЕ прогона хука с cwd=tmp_path и сверяет их побайтово равными.

Run from the repo root: python -m pytest tools/test_critic_snapshot.py
"""

import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import critic_snapshot as cs  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "critic_snapshot.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_SNAPSHOT = _REPO_ROOT / ".claude" / "critic_snapshot.json"


def _run_hook(payload, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd) if cwd is not None else None,
    )


def _critic_payload(cwd: Path, tool_name="Task") -> dict:
    return {
        "tool_name": tool_name,
        "tool_input": {"subagent_type": "critic"},
        "cwd": str(cwd),
    }


class _FakeStdin:
    """Подаёт байты в sys.stdin.buffer для прямого вызова cs.main() --
    main() читает ТОЛЬКО sys.stdin.buffer.read() (staging_hq байтовый
    вариант, см. докстринг critic_snapshot.py), поэтому достаточно
    заменить .buffer, не весь sys.stdin API."""

    def __init__(self, data: bytes):
        self.buffer = io.BytesIO(data)


# ---------------------------------------------------------------------
# (A) E2E: фильтрация payload -- снимок НЕ пишется, exit всегда 0.
# ---------------------------------------------------------------------


def test_non_task_tool_name_no_snapshot_written_exit0(tmp_path):
    payload = {"tool_name": "Bash", "tool_input": {"subagent_type": "critic"}, "cwd": str(tmp_path)}
    result = _run_hook(payload)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()


def test_task_wrong_subagent_type_no_snapshot_written_exit0(tmp_path):
    payload = {"tool_name": "Task", "tool_input": {"subagent_type": "builder"}, "cwd": str(tmp_path)}
    result = _run_hook(payload)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert not (tmp_path / ".claude" / "critic_snapshot.json").exists()


def test_invalid_json_payload_fail_open_exit0_no_crash():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=b"{not valid json at all",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert result.returncode == 0
    assert result.stdout == b""


# ---------------------------------------------------------------------
# (A) E2E: штатный путь -- Task И Agent оба распознаются, снимок пишется
# со всеми полями, cwd -- строго из payload.
# ---------------------------------------------------------------------


def test_agent_tool_name_recognized_writes_snapshot_with_expected_fields(tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world", encoding="utf-8")

    result = _run_hook(_critic_payload(tmp_path, tool_name="Agent"), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    assert snap.exists()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"ts", "tree_hash", "files_count", "skipped_files"}
    assert doc["skipped_files"] == 0
    assert doc["files_count"] == 2

    # Кросс-проверка: тот же обход, вызванный напрямую в этом процессе,
    # даёт БИТ-В-БИТ тот же tree_hash/files_count -- не просто "поле
    # есть", а "поле совпадает с независимым вычислением".
    expected_hash, expected_count, expected_skipped = cs.compute_tree_hash(tmp_path)
    assert doc["tree_hash"] == expected_hash
    assert doc["files_count"] == expected_count
    assert doc["skipped_files"] == expected_skipped


def test_real_repo_snapshot_untouched_by_tmp_path_dispatch(tmp_path):
    # Край (ii): снимок пишется в cwd ИЗ PAYLOAD -- прогон хука с
    # cwd=tmp_path не должен трогать реальный .claude/critic_snapshot.json
    # этого репозитория НИ ПРИ КАКИХ условиях.
    before = _REAL_SNAPSHOT.read_bytes() if _REAL_SNAPSHOT.exists() else None
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    after = _REAL_SNAPSHOT.read_bytes() if _REAL_SNAPSHOT.exists() else None
    assert before == after, "реальный .claude/critic_snapshot.json изменился -- нарушение края (ii)"


# ---------------------------------------------------------------------
# (B) in-process: нечитаемый ОДИН файл дерева -- обход не падает.
# ---------------------------------------------------------------------


def test_compute_tree_hash_unreadable_single_file_increments_skipped_continues(tmp_path, monkeypatch):
    """Край (i): chmod на Windows не создаёт надёжно нечитаемый для
    ВЛАДЕЮЩЕГО процесса файл (NTFS read-only бит защищает от записи, не
    от чтения содержимого тем же процессом) -- вместо этого монкипатчим
    Path.read_bytes ТОЛЬКО для конкретного целевого пути (bad.txt),
    остальные вызовы (включая good.txt) идут через оригинальный метод."""
    good = tmp_path / "good.txt"
    good.write_text("readable", encoding="utf-8")
    bad = tmp_path / "bad.txt"
    bad.write_text("unreadable-in-this-test", encoding="utf-8")

    orig_read_bytes = Path.read_bytes
    bad_resolved = bad.resolve()

    def flaky_read_bytes(self):
        if self.resolve() == bad_resolved:
            raise PermissionError(f"simulated unreadable file: {self}")
        return orig_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", flaky_read_bytes)

    tree_hash, files_count, skipped_files = cs.compute_tree_hash(tmp_path)

    assert skipped_files == 1
    assert files_count == 1  # только good.txt вошёл в дерево

    # tree_hash должен совпадать с хэшем, посчитанным ТОЛЬКО по good.txt
    # (та же формула, что compute_tree_hash использует внутри).
    import hashlib
    rel = good.relative_to(tmp_path)
    digest = hashlib.sha256(orig_read_bytes(good)).hexdigest()
    expected_entry = f"{rel.as_posix()}:{digest}"
    expected_hash = hashlib.sha256(expected_entry.encode("utf-8")).hexdigest()
    assert tree_hash == expected_hash


# ---------------------------------------------------------------------
# (B) in-process: ДВЕ РАЗЛИЧНЫЕ точки отказа main() -- обход дерева vs
# запись снимка -- разные результирующие документы (см. докстринг
# critic_snapshot.py, "ДВЕ РАЗЛИЧНЫЕ ТОЧКИ ОТКАЗА").
# ---------------------------------------------------------------------


def test_main_tree_walk_failure_writes_error_document_and_stderr(tmp_path, monkeypatch, capsys):
    def _boom(_root):
        raise RuntimeError("simulated tree-walk failure")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    assert snap.exists()
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"error", "error_ts"}
    assert "RuntimeError" in doc["error"]
    assert "simulated tree-walk failure" in doc["error"]

    err = capsys.readouterr().err
    assert "FAILED to take snapshot" in err
    assert "RuntimeError" in err


def test_main_write_failure_only_stderr_no_file_written(tmp_path, monkeypatch, capsys):
    """Ветка отказа ЗАПИСИ снимка (спека доборного батча: "только stderr,
    exit 0 -- файл записать нельзя по построению"): Path.write_text
    ВСЕГДА кидает -- и штатная запись main(), и retry-запись
    _write_failure_snapshot() (тот же путь, та же причина отказа) обе
    проваливаются, документ отказа НЕ появляется, только диагностика в
    stderr."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    def _always_raise(self, *a, **kw):
        raise OSError("simulated disk full")

    monkeypatch.setattr(Path, "write_text", _always_raise)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    assert not snap.exists()

    err = capsys.readouterr().err
    assert "FAILED to take snapshot" in err
    assert "OSError" in err


def test_failure_document_replaces_prior_success_shape_but_preserves_prev_fields(
    tmp_path, monkeypatch, capsys,
):
    """Отказный документ ЗАМЕЩАЕТ ШЕЙП обычного (нет ключа "tree_hash" -- см.
    докстринг critic_snapshot.py, инвариант "отказ не выглядит валидным
    снимком"), но НЕ полностью теряет данные предыдущего РЕАЛЬНОГО успеха:
    ts/tree_hash прошлого снимка копируются в prev_ts/prev_tree_hash --
    ПЕРЕСДАЧА (не-блокер (б), критик 2026-08-05): раньше отказ ЗАТИРАЛ
    последний успешный снимок целиком, будущий грейдер терял ЛЮБУЮ базовую
    линию сверки "финал не ревьюился" (устаревший, но РЕАЛЬНЫЙ снимок был
    бы полезнее полного отсутствия tree_hash). Обновлено против прежней
    версии этого теста (строгое `set(...) == {"error","error_ts"}`) --
    это ИЗМЕНЕНИЕ семантики, запрошенное явно критиком, не молчаливое
    ослабление проверки."""
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")

    # 1) штатный успешный вызов -- через subprocess (реальный e2e путь).
    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    snap = tmp_path / ".claude" / "critic_snapshot.json"
    before_doc = json.loads(snap.read_text(encoding="utf-8"))
    assert "tree_hash" in before_doc

    # 2) следующий вызов, тем же снимком -- обход дерева теперь падает.
    def _boom(_root):
        raise RuntimeError("simulated second-call failure")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    after_doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(after_doc.keys()) == {"error", "error_ts", "prev_ts", "prev_tree_hash"}
    assert "tree_hash" not in after_doc  # инвариант шейпа сохранён
    assert "files_count" not in after_doc
    assert after_doc["prev_ts"] == before_doc["ts"]
    assert after_doc["prev_tree_hash"] == before_doc["tree_hash"]


def test_failure_document_no_prev_fields_when_no_prior_snapshot_exists(
    tmp_path, monkeypatch,
):
    # Контрольная сторона: НЕТ прежнего снимка вовсе (свежий tmp_path) --
    # prev_ts/prev_tree_hash НЕ добавляются (нечего копировать, не
    # выдумываем значения) -- строгое {"error","error_ts"}, как раньше.
    def _boom(_root):
        raise RuntimeError("simulated failure, no prior snapshot")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    snap = tmp_path / ".claude" / "critic_snapshot.json"
    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"error", "error_ts"}


def test_failure_document_no_prev_fields_when_prior_was_itself_a_failure(
    tmp_path, monkeypatch,
):
    # Отказ НЕ наследует prev_* от ПРЕДЫДУЩЕГО отказа (у него самого нет
    # tree_hash) -- иначе цепочка отказов бесконтрольно тащила бы старые
    # данные всё дальше без переоценки.
    snap = tmp_path / ".claude" / "critic_snapshot.json"
    snap.parent.mkdir(parents=True)
    snap.write_text(json.dumps({"error": "prior failure", "error_ts": "x"}), encoding="utf-8")

    def _boom(_root):
        raise RuntimeError("simulated second failure in a row")

    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
    payload = _critic_payload(tmp_path)
    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))

    rc = cs.main()
    assert rc == 0

    doc = json.loads(snap.read_text(encoding="utf-8"))
    assert set(doc.keys()) == {"error", "error_ts"}
