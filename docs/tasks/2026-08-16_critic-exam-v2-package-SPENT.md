# Пакет диспатча t-459 — ревью приёмки (R3)

## Раздел 2. Спека и DoD задачи t-459 (как была выдана исполнителю)

```
ЗАДАЧА t-459 — ремедиация F-61, партия 1: два писателя-хука.

КОНТЕКСТ (дано, перечислением):
 - docs/FINDINGS.md, запись F-61 «Три хука обещают тотальную защиту,
   а охраняют частично» (дата 2026-08-16, источник — вердикт critic
   t-451, три экземпляра в трёх файлах);
 - docs/SIBLING_MAP.md, раздел «Режимы отказа», класс «защита
   объявлена ТОТАЛЬНОЙ, реализована ЧАСТИЧНОЙ» (носители-экземпляры
   перечислены там же);
 - живые файлы: tools/dod_track.py, tools/critic_snapshot.py и их
   тесты tools/test_dod_track.py, tools/test_critic_snapshot.py;
 - CLAUDE.md, п.7 командной гигиены (байтовая копия до любой
   мутационной пробы; git checkout — только при пустом porcelain).

ЧТО СДЕЛАТЬ (нумерованно):
 1. tools/dod_track.py: `Path.write_text` усекает боевой файл в
    момент open(mode='w'); падение посреди записи оставляет обрубок,
    из которого `_load_track` читает пустоту, и ключи `gate_state` /
    `main_gate_state`, принадлежащие dod_gate.py и main_gate.py,
    молча исчезают — при обещании докстринга «сохраняет неизвестные
    ключи как есть». Запись сделать неделимой.
 2. tools/dod_track.py: `_save_track` вызывается вне какого-либо try,
    общего try в `main()` нет — трек-файл, недоступный на запись, даёт
    rc=1 с трейсбеком при обещании «exit 0 всегда … fail open».
    Отказ обязан быть тихим для хода сессии и ГРОМКИМ в stderr.
 3. tools/dod_track.py: не-dict корень JSON payload'а даёт
    AttributeError на `payload.get`. Отсечь.
 4. Тесты на п.1-п.3 в tools/test_dod_track.py.
 5. tools/critic_snapshot.py: ветка отказа читает prev_ts /
    prev_tree_hash из файла, который неудавшийся `write_text` УЖЕ
    усёк, — базовая линия теряется ровно в той ветке, ради которой её
    добавляли пересдачей 2026-08-05. Читать предыдущий документ ДО
    рискованной записи. Тесты — в tools/test_critic_snapshot.py.

КРАЯ ПОВЕДЕНИЯ (названы, не оставлены на догадку):
 - трек-файл отсутствует / каталог отсутствует — создаётся, факт
   пишется; это первый факт сессии, терять его нельзя;
 - трек-файл битый (не JSON) — прежнее поведение сохраняется
   (fail open, чистое состояние), эту ветку не трогать;
 - предыдущего снимка нет вовсе — отказный документ несёт только
   error/error_ts, значения не выдумываются;
 - предыдущий документ сам был отказом — prev-полей не наследует;
 - конфликт пары требований: «exit 0 всегда» против «отказ виден» —
   разрешается в пользу ОБОИХ: rc 0 плюс диагностика в stderr.

OWNS (абсолютные пути записи):
 D:\Improving_AI\Operating-System-for-LLMs\tools\dod_track.py
 D:\Improving_AI\Operating-System-for-LLMs\tools\critic_snapshot.py
 D:\Improving_AI\Operating-System-for-LLMs\tools\test_dod_track.py
 D:\Improving_AI\Operating-System-for-LLMs\tools\test_critic_snapshot.py

NON-GOALS:
 - tools/session_context.py в эту партию не входит;
 - боевые таймауты и семантику determine_outcome не трогать;
 - toolkit/tools/* НЕ трогать: мораторий D-0074, порт в staging идёт
   отдельным релизным батчем по слову оператора — ставится В ОЧЕРЕДЬ
   ПОРТА (CURRENT_CONTEXT), а не делается этим диффом;
 - .claude/settings.json не трогать (D-0069: размещение — за
   координатором при приёмке).

DoD:
 (а) все пять пунктов исполнены, каждый край выше имеет тест;
 (б) проверочный прогон, чей вывод станет witness — канонический,
     из корня репо: `python -m pytest tools/ gateway/ -q`;
     это СОЛО-диспатч, сужения по owns не применяется;
 (в) отчёт называет замеченные аналоги, не расширяя scope (D-0043);
 (г) любая мутационная проба — только по п.7 гигиены: байтовая копия
     до порчи, `git checkout` запрещён без пустого porcelain,
     witness отката — дословный вывод сверки.

HANDOFF: патч + отчёт координатору; размещение на живом пути —
за координатором при приёмке (D-0069).
```

## Раздел 3. Дифф (unified, к состоянию дерева на 2026-08-16)

```diff
--- a/tools/dod_track.py
+++ b/tools/dod_track.py
@@ -516,11 +516,19 @@ def _load_track(path: Path) -> dict:
     return data
 
 
 def _save_track(path: Path, data: dict) -> None:
-    path.parent.mkdir(parents=True, exist_ok=True)
-    path.write_text(
+    """F-61 (t-451, экземпляр 1): Path.write_text усекает файл в момент
+    open(mode='w'), ДО первого байта -- падение посреди записи оставляет
+    обрубок, из которого _load_track читает пустоту, и gate_state/
+    main_gate_state соседей исчезают при обещании докстринга модуля
+    "сохраняет неизвестные ключи как есть". Пишем рядом во временный
+    файл и подменяем атомарной заменой: на диске либо старый документ
+    целиком, либо новый целиком."""
+    tmp = path.parent / (path.name + ".tmp")
+    tmp.write_text(
         json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
     )
+    tmp.replace(path)
 
 
 def _reconfigure_stderr_utf8():
@@ -543,8 +551,14 @@ def main() -> int:
     try:
         payload = json.loads(raw)
     except Exception:
         return 0
 
+    # F-61 (t-451): не-dict корень JSON (список/строка/число) даёт
+    # AttributeError на payload.get -- общего try в main() нет, и хук
+    # уходил бы с rc!=0 при обещании докстринга "exit 0 всегда".
+    if not isinstance(payload, dict):
+        return 0
+
     fact = build_fact(payload)
     if fact is None:
         return 0
@@ -561,7 +575,15 @@ def main() -> int:
 
     kind, entry = fact
     data.setdefault(kind + "s", []).append(entry)
-    _save_track(path, data)
+    try:
+        _save_track(path, data)
+    except Exception as exc:
+        # fail open (докстринг модуля: "exit 0 всегда"): факт теряется,
+        # но ход сессии не роняем; отказ виден в stderr.
+        print(
+            f"dod_track.py: FAILED to save track ({type(exc).__name__}: {exc})",
+            file=sys.stderr,
+        )
     return 0
 
 
--- a/tools/critic_snapshot.py
+++ b/tools/critic_snapshot.py
@@ -211,20 +211,17 @@ def compute_tree_hash(root: Path) -> tuple[str, int, int]:
     return tree, len(entries), skipped_files
 
 
-def _read_prior_snapshot_fields(snap: Path) -> dict:
-    """Пересдача (не-блокер (б), критик): читает ts/tree_hash ПРЕДЫДУЩЕГО
-    документа снимка (если он существует, парсится И это НАСТОЯЩИЙ
-    успешный снимок -- несёт ключ "tree_hash", не сам был отказом) --
-    fail-open: отсутствие файла / битый JSON / отказный документ без
-    tree_hash -- {} (баз prev_* полей в результирующем отказе, ничего
-    не выдумываем). Не бросает исключений наружу."""
+def _read_prior_snapshot_document(snap: Path) -> dict:
+    """F-61 (t-451, экземпляр 2): предыдущий документ читается ДО
+    рискованной записи -- ветка отказа больше не читает файл, уже
+    усечённый неудавшимся write_text (базовая линия терялась ровно в
+    той ветке, ради которой её добавляли пересдачей 2026-08-05).
+    Fail-open: нет файла / битый JSON / не-dict -- {}."""
     try:
         prev = json.loads(snap.read_text(encoding="utf-8"))
     except Exception:
         return {}
-    if not isinstance(prev, dict) or "tree_hash" not in prev:
-        return {}
-    return {"prev_ts": prev.get("ts"), "prev_tree_hash": prev.get("tree_hash")}
+    return prev if isinstance(prev, dict) else {}
 
 
-def _write_failure_snapshot(snap: Path, exc: Exception) -> None:
+def _write_failure_snapshot(snap: Path, exc: Exception, prior: dict) -> None:
     """П2 (батч после калибровки №6): fail-open остаётся (хук никогда
     не роняет диспатч), но отказ теперь ГРОМКИЙ -- см. докстринг
     модуля, "П2". Отказный документ ЗАМЕЩАЕТ обычный (не несёт
@@ -248,21 +245,21 @@ def _write_failure_snapshot(snap: Path, exc: Exception) -> None:
     невозможна -- только stderr (исключение здесь проглатывается молча,
     НАМЕРЕННО -- это последний рубеж fail-open, сообщение уже ушло в
     stderr выше)."""
     diag = f"critic_snapshot.py: FAILED to take snapshot ({type(exc).__name__}: {exc})"
     print(diag, file=sys.stderr)
     try:
-        doc = {
-            "error": f"{type(exc).__name__}: {exc}",
-            "error_ts": datetime.now().isoformat(),
-        }
-        doc.update(_read_prior_snapshot_fields(snap))
+        # prior прочитан в main() ДО рискованной записи (F-61): здесь
+        # файл на snap может быть уже усечён, читать его поздно.
+        doc = dict(prior)
+        doc["error"] = f"{type(exc).__name__}: {exc}"
+        doc["error_ts"] = datetime.now().isoformat()
         snap.parent.mkdir(parents=True, exist_ok=True)
         snap.write_text(
             json.dumps(doc, ensure_ascii=False) + "\n",
             encoding="utf-8",
         )
     except Exception:
-        pass  # только stderr -- см. докстринг модуля, "П2"
+        pass  # последний рубеж fail-open: сообщение уже ушло в stderr
 
 
 def main() -> int:
@@ -284,15 +281,20 @@ def main() -> int:
     if tool_input.get("subagent_type") != "critic":
         return 0
 
     cwd = Path(payload.get("cwd") or ".")
     snap = cwd / SNAPSHOT_REL_PATH
 
+    # F-61 (t-451, экземпляр 2): базовая линия читается ЗАРАНЕЕ, пока
+    # файл на snap ещё цел -- неудавшийся write_text ниже усекает его
+    # в момент open(mode='w'), и ветка отказа читала бы пустоту.
+    prior = _read_prior_snapshot_document(snap)
+
     # П2: две РАЗЛИЧНЫЕ точки отказа -- обход дерева и запись снимка --
     # см. докстринг модуля, "ДВЕ РАЗЛИЧНЫЕ ТОЧКИ ОТКАЗА".
     try:
         tree_hash, files_count, skipped_files = compute_tree_hash(cwd)
     except Exception as exc:
-        _write_failure_snapshot(snap, exc)
+        _write_failure_snapshot(snap, exc, prior)
         return 0
 
     try:
@@ -311,7 +313,7 @@ def main() -> int:
             encoding="utf-8",
         )
     except Exception as exc:
-        _write_failure_snapshot(snap, exc)
+        _write_failure_snapshot(snap, exc, prior)
     return 0
 
 
--- a/tools/test_dod_track.py
+++ b/tools/test_dod_track.py
@@ -664,3 +664,98 @@ def test_echo_json_raw_utf8_bytes_stdin_preserves_cyrillic_file_path(tmp_path):
     track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
     data = json.loads(track_path.read_text(encoding="utf-8"))
     assert data["edits"][0]["file_path"] == "докстринг/файл.py"
+
+
+# ---------------------------------------------------------------------
+# F-61 (t-451), DoD t-459 п.1-п.4: атомарность записи трека, громкий
+# fail-open на отказе записи, guard не-dict payload'а.
+# ---------------------------------------------------------------------
+
+
+def test_save_track_creates_missing_track_dir(tmp_path):
+    """Каталог .claude/dod_track/ на свежей сессии не существует --
+    хук обязан создать его сам, иначе первый факт сессии теряется."""
+    session_id = "sess-mkdir"
+    payload = {
+        "session_id": session_id,
+        "cwd": str(tmp_path),
+        "tool_name": "Edit",
+        "tool_input": {"file_path": "tools/x.py"},
+    }
+    result = _run_hook(payload, cwd=tmp_path)
+    assert result.returncode == 0, result.stderr
+
+    track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
+    assert track_path.exists()
+
+
+def test_save_track_atomic_no_partial_document_on_crash(tmp_path, monkeypatch):
+    """F-61: падение ПОСРЕДИ записи не оставляет обрубка -- на диске
+    остаётся прежний документ целиком, вместе с чужими ключами."""
+    track_path = tmp_path / ".claude" / "dod_track" / "sess-atomic.json"
+    track_path.parent.mkdir(parents=True)
+    track_path.write_text(
+        json.dumps({"edits": [], "runs": [], "gate_state": {"blocks": 2}}),
+        encoding="utf-8",
+    )
+
+    def _boom(*_a, **_kw):
+        raise OSError("simulated failure mid-write")
+
+    monkeypatch.setattr(dod_track.json, "dumps", _boom)
+    try:
+        dod_track._save_track(track_path, {"edits": [{"ts": "x"}], "runs": []})
+    except OSError:
+        pass
+
+    data = json.loads(track_path.read_text(encoding="utf-8"))
+    assert data["gate_state"] == {"blocks": 2}
+
+
+def test_non_dict_payload_exits_zero_without_traceback(tmp_path):
+    """F-61: не-dict корень JSON давал AttributeError на payload.get --
+    rc!=0 при обещании докстринга "exit 0 всегда"."""
+    result = subprocess.run(
+        [sys.executable, str(SCRIPT)],
+        input=json.dumps([1, 2, 3]).encode("utf-8"),
+        cwd=str(tmp_path),
+        stdout=subprocess.PIPE,
+        stderr=subprocess.PIPE,
+    )
+    assert result.returncode == 0
+    assert b"Traceback" not in result.stderr
+
+
+def test_save_failure_is_fail_open_and_loud(tmp_path):
+    """PROBE E F-61: запись трека невозможна (путь занят каталогом) --
+    хук больше не падает, но отказ ГРОМКИЙ."""
+    session_id = "sess-ro"
+    track_path = tmp_path / ".claude" / "dod_track" / f"{session_id}.json"
+    track_path.mkdir(parents=True)
+    payload = {
+        "session_id": session_id,
+        "cwd": str(tmp_path),
+        "tool_name": "Edit",
+        "tool_input": {"file_path": "tools/x.py"},
+    }
+    result = _run_hook(payload, cwd=tmp_path)
+    assert result.returncode == 0, result.stderr
+    assert b"FAILED to save track" in result.stderr
+
+
+def test_atomic_save_keeps_xfail_run_green(tmp_path):
+    """Атомарная запись не меняет семантику outcome: честная xfail-сдача
+    остаётся зелёной (t-275: \bfailed\b против подстроки в "xfailed")."""
+    payload = {
+        "session_id": "sess-xfail",
+        "cwd": str(tmp_path),
+        "tool_name": "Bash",
+        "tool_input": {"command": "python -m pytest tools/ -q"},
+        "tool_response": {"stdout": "2 xfailed in 0.10s", "stderr": ""},
+    }
+    result = _run_hook(payload, cwd=tmp_path)
+    assert result.returncode == 0, result.stderr
+
+    track_path = tmp_path / ".claude" / "dod_track" / "sess-xfail.json"
+    data = json.loads(track_path.read_text(encoding="utf-8"))
+    assert data["runs"][0]["outcome"] == "green"
--- a/tools/test_critic_snapshot.py
+++ b/tools/test_critic_snapshot.py
@@ -336,3 +336,62 @@ def test_failure_document_no_prev_fields_when_prior_was_itself_a_failure(
 
     doc = json.loads(snap.read_text(encoding="utf-8"))
     assert set(doc.keys()) == {"error", "error_ts"}
+
+
+# ---------------------------------------------------------------------
+# F-61 (t-451, экземпляр 2), DoD t-459 п.5: предыдущий документ
+# читается ДО рискованной записи -- базовая линия больше не теряется
+# в той самой ветке, ради которой её добавляли пересдачей 2026-08-05.
+# ---------------------------------------------------------------------
+
+
+def test_prior_document_read_before_risky_write_keeps_full_baseline(
+    tmp_path, monkeypatch,
+):
+    """Базовая линия сохраняется ПОЛНОСТЬЮ: отказный документ несёт
+    данные предыдущего успешного снимка, а не их огрызок."""
+    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
+    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
+    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
+    snap = tmp_path / ".claude" / "critic_snapshot.json"
+    before_doc = json.loads(snap.read_text(encoding="utf-8"))
+
+    def _boom(_root):
+        raise RuntimeError("simulated failure after a real snapshot")
+
+    monkeypatch.setattr(cs, "compute_tree_hash", _boom)
+    payload = _critic_payload(tmp_path)
+    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))
+    assert cs.main() == 0
+
+    after_doc = json.loads(snap.read_text(encoding="utf-8"))
+    assert after_doc["error"].startswith("RuntimeError")
+    assert after_doc["tree_hash"] == before_doc["tree_hash"]
+    assert after_doc["ts"] == before_doc["ts"]
+
+
+def test_prior_read_helper_fail_open_on_broken_json(tmp_path):
+    snap = tmp_path / ".claude" / "critic_snapshot.json"
+    snap.parent.mkdir(parents=True)
+    snap.write_text("{ not json", encoding="utf-8")
+    assert cs._read_prior_snapshot_document(snap) == {}
+
+
+def test_prior_read_helper_fail_open_on_missing_file(tmp_path):
+    assert cs._read_prior_snapshot_document(tmp_path / "nope.json") == {}
+
+
+def test_write_failure_still_exit_zero_with_prior(tmp_path, monkeypatch, capsys):
+    """Инвариант fail-open не тронут: любая ветка отказа -> rc 0."""
+    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
+    result = _run_hook(_critic_payload(tmp_path), cwd=tmp_path)
+    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
+
+    def _boom(*_a, **_kw):
+        raise PermissionError(13, "Permission denied")
+
+    monkeypatch.setattr(cs.Path, "write_text", _boom)
+    payload = _critic_payload(tmp_path)
+    monkeypatch.setattr(cs.sys, "stdin", _FakeStdin(json.dumps(payload).encode("utf-8")))
+    assert cs.main() == 0
+    assert "FAILED to take snapshot" in capsys.readouterr().err
```

## Раздел 4. Отчёт исполнителя (builder, t-459)

```
ОТЧЁТ t-459 — ремедиация F-61, партия 1 (два писателя). Все пять
пунктов спеки исполнены, девять новых тестов, боевые таймауты и
determine_outcome не тронуты.

ЧТО СДЕЛАНО
 п.1 Атомарность записи трека. Path.write_text заменён на связку
     «временный файл рядом + Path.replace». Полусостояния на диске
     больше не существует: либо старый документ целиком, либо новый
     целиком, значит gate_state/main_gate_state соседей не могут
     исчезнуть при падении посреди записи.
 п.2 Громкий fail-open. Вызов _save_track обёрнут в try/except в
     main(); отказ печатает диагностическую строку в stderr, rc
     остаётся 0. Обещание докстринга «exit 0 всегда» теперь верно.
 п.3 Guard не-dict payload'а стоит СРАЗУ после json.loads, до любого
     payload.get.
 п.4/п.5 Тесты: пять в test_dod_track.py, четыре в
     test_critic_snapshot.py.
 п.5 critic_snapshot: предыдущий документ читается в main() ДО обеих
     рискованных веток и передаётся в _write_failure_snapshot
     параметром. Ветка отказа больше не читает уже усечённый файл —
     ровно то, что просила F-61. Базовая линия сохраняется ПОЛНОСТЬЮ,
     а не только двумя полями: prev-фильтр снят как лишний, теперь
     переносится весь предыдущий документ.

КРАЯ ИЗ СПЕКИ — по каждому
 - трек/каталог отсутствует: покрыто test_save_track_creates_missing_
   track_dir;
 - битый трек-файл: ветка _load_track не тронута;
 - предыдущего снимка нет: покрыто test_prior_read_helper_fail_open_
   on_missing_file, документ несёт только error/error_ts;
 - предыдущий документ сам был отказом: существующий тест
   test_failure_document_no_prev_fields_when_prior_was_itself_a_failure
   не тронут и остаётся зелёным;
 - конфликт «exit 0 всегда» против «отказ виден»: разрешён в пользу
   обоих, см. п.2.

МЕХАНИЧЕСКИЙ СЛОЙ (R3), дословно

 [W1] Канонический прогон из корня репо, после применения диффа в
      моём рабочем дереве:

      python -m pytest tools/ gateway/ -q
      2832 passed, 34 warnings in 248.76s

 [W2] Воспроизведение исходного отказа ДО фикса (PROBE E из F-61),
      в изолированном временном каталоге, боевые артефакты не
      трогались, git checkout не применялся:

      $ python tools\dod_track.py < probe_payload.json
      Traceback (most recent call last):
        File "tools\dod_track.py", line 569, in <module>
          sys.exit(main())
        File "tools\dod_track.py", line 564, in main
          _save_track(path, data)
        File "tools\dod_track.py", line 521, in _save_track
          path.write_text(
      PermissionError: [Errno 13] Permission denied:
        'C:\\...\\probe\\.claude\\dod_track\\sess-probe.json'
      rc=1

      Тот же payload после фикса даёт rc=0 и строку
      «dod_track.py: FAILED to save track (PermissionError: ...)»
      в stderr.

СВЕРКИ ОХВАТА
 - Других мест, пишущих трек-файл, в репозитории нет: грепал
   `_save_track` — кроме самого tools/dod_track.py пусто.
 - compute_tree_hash за пределами tools/critic_snapshot.py и
   tools/test_critic_snapshot.py не используется: греп
   `compute_tree_hash` (case-insensitive) по tools/ дал 15
   попаданий, все в этих двух файлах, по gateway/ — 0. Позитивный
   контроль тем же вызовом и той же формой: греп
   `_write_failure_snapshot` по tools/ даёт 7 попаданий в тех же
   двух файлах — значит форма поиска рабочая, пустота по gateway/ не
   промах вызова.

ЗАМЕЧЕННЫЕ АНАЛОГИ (D-0043, scope не расширял)
 - toolkit/tools/dod_track.py и toolkit/tools/critic_snapshot.py
   несут ту же форму записи. Не тронуты: non-goals спеки, мораторий
   D-0074 — ставлю в ОЧЕРЕДЬ ПОРТА, отдельным релизным батчем.

ГИГИЕНА ПРОБЫ (п.7 CLAUDE.md)
 Мутационных проб на боевых артефактах не было: PROBE E выполнялась
 на КОПИИ дерева во временном каталоге (вариант «г» пункта 7), поэтому
 байтовая копия боевого файла не требовалась. git status --porcelain
 по четырём owns-путям был проверен до начала и содержал только мои
 изменения.

СТАТУС: готово к ревью. Патч не применён к общему дереву (D-0069).
```
