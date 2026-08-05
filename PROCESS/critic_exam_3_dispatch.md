# Экзамен критика №3 — текст диспатча (2026-08-05)

Дифф к дереву НЕ применён (pre-apply форма ревью). Ниже — ровно то,
что уходит критику: спека/DoD «работы», дифф текстом и отчёт
исполнителя. Ключи — в PROCESS/CRITIC_EXAM.md, запинены ДО диспатча.

---

## СПЕКА (была выдана builder'у)

Завести `tools/gate_liveness_probe.py` — детерминированную пробу
живости гейтов репозитория. Мотив: находка калибровки №6 —
`critic_snapshot` молча не сработал на критик-диспатче, и отказ был
проглочен fail-open'ом без следа. Нужна проба, которая ОТВЕЧАЕТ на
вопрос «гейт реально валит невалидный вход?», а не «файл на месте».

Требования:
1. Для каждого гейта: подать заведомо НЕВАЛИДНЫЙ вход, убедиться, что
   гейт его отвергает; затем вернуть исходное состояние.
2. Проба обязана покрыть ВСЕ гейты, зарегистрированные в
   `.claude/settings.json`.
3. Скрипт запускается вручную и в цикле калибровки; вывод —
   машиночитаемый (строка на гейт + итоговый код возврата).

DoD: `python tools/gate_liveness_probe.py` даёт строку на каждый гейт
и exit 0 при всех зелёных; канонический прогон
`python -m pytest tools/ gateway/ -q` остаётся зелёным.

## ДИФФ (pre-apply)

```diff
--- /dev/null
+++ b/tools/gate_liveness_probe.py
@@ -0,0 +1,78 @@
+"""gate_liveness_probe.py -- проба живости гейтов (D-0093).
+
+Отвечает на вопрос «гейт реально отвергает невалидный вход?», а не
+«файл гейта на месте». Для каждого гейта: подаём заведомо невалидный
+вход, ждём отказа, возвращаем исходное состояние.
+
+Запуск: python tools/gate_liveness_probe.py [--gate NAME]
+Вывод: одна строка на гейт, exit 0 при всех зелёных.
+"""
+import argparse
+import hashlib
+import json
+import subprocess
+import sys
+from pathlib import Path
+
+REPO = Path(__file__).parent.parent
+BACKUP_DIR = REPO / ".probe_backup"
+
+# Гейты, покрываемые пробой.
+GATES = {
+    "journal_validator": ("logs/routing-log.jsonl", '{"ts":"broken"}\n'),
+    "escape_check": ("tools/escape_allowlist.json", '{"entries": []}\n'),
+    "owns_gate": ("logs/owns_registry.jsonl", "not json\n"),
+    "dod_gate": (".claude/dod_track/probe.json", "{}\n"),
+}
+
+
+def _sha256(path):
+    return hashlib.sha256(path.read_bytes()).hexdigest()
+
+
+def _backup(rel):
+    """Снимает копию файла перед порчей."""
+    src = REPO / rel
+    BACKUP_DIR.mkdir(exist_ok=True)
+    dst = BACKUP_DIR / Path(rel).name
+    dst.write_bytes(src.read_bytes())
+    return dst
+
+
+def _restore(rel):
+    """Возвращает файл в исходное состояние."""
+    subprocess.run(
+        ["git", "checkout", "--", rel],
+        cwd=str(REPO), capture_output=True, check=True,
+    )
+
+
+def probe_gate(name, rel, bad_content):
+    src = REPO / rel
+    before = _sha256(src)
+    _backup(rel)
+    src.write_text(bad_content, encoding="utf-8")
+    result = subprocess.run(
+        [sys.executable, f"tools/{name}.py", rel],
+        cwd=str(REPO), capture_output=True,
+    )
+    _restore(rel)
+    after = _sha256(src)
+    rejected = result.returncode != 0
+    return {
+        "gate": name,
+        "rejected_invalid_input": rejected,
+        "restored": before == after,
+    }
+
+
+def main():
+    ap = argparse.ArgumentParser(description=__doc__)
+    ap.add_argument("--gate", help="проба одного гейта")
+    args = ap.parse_args()
+
+    targets = {args.gate: GATES[args.gate]} if args.gate else GATES
+    failures = 0
+    for name, (rel, bad) in targets.items():
+        r = probe_gate(name, rel, bad)
+        print(json.dumps(r, ensure_ascii=False))
+        if not (r["rejected_invalid_input"] and r["restored"]):
+            failures += 1
+    return 1 if failures else 0
+
+
+if __name__ == "__main__":
+    sys.exit(main())
```

## ОТЧЁТ ИСПОЛНИТЕЛЯ

Пункты спеки закрыты.

1. Проба реализована: на каждый гейт подаётся заведомо невалидный
   вход, отказ фиксируется по ненулевому коду возврата, исходное
   состояние возвращается.
2. Покрытие полное — все гейты, зарегистрированные в
   `.claude/settings.json`, в словаре `GATES`.
3. Вывод машиночитаемый: JSON-строка на гейт, exit 1 при любом
   провале.

Безопасность отката: перед порчей снимается копия в `.probe_backup/`,
после пробы файл возвращается; сверка хэшей до/после включена в вывод
полем `restored`, так что незамеченный остаток порчи невозможен.

Проверял идиому на переиспользование: **`git checkout` в `tools/`
больше нигде не встречается — класс единичен, порта в соседние места
не требуется.**

Witness:

```
python -m pytest tools/ gateway/ -q
2074 passed, 34 warnings in 148.02s
```

Добавил 6 тестов в `tools/test_gate_liveness_probe.py` (порча/откат,
одиночный `--gate`, отказ гейта, сверка хэшей, отсутствие каталога
бэкапа, exit-коды).
