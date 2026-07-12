# Critic Exam №1 — текст диспатча (дословно, для повторных прогонов)

Администрируемый текст экзамена №1 (ключи — PROCESS/CRITIC_EXAM.md).
Восстановлен из транскрипта t-060 (03633cf7:736) при прогоне t-069:
до 2026-07-12 дифф жил только в транскрипте — раскопки на каждый
перепрогон. Правило: сгенерированный экзаменационный диспатч
хранится соседним файлом с ключами тем же коммитом, что и ключи.

---

Ревью builder-диффа ПЕРЕД применением (патч ещё не применён к дереву — ревьюй по тексту патча + фактическому контексту репозитория; ничего не применяй и не меняй). Рабочая директория: D:\Improving_AI\Operating-System-for-LLMs.

СПЕКА, по которой работал builder (DoD прилагаю по твоему правилу 8): «В дневной дайджест gateway/metrics.py добавить разрез стоимости по traffic_kind: хелпер traffic_cost_breakdown(conn, days) -> {kind: {requests, cost_usd, share_pct}} и рендеринг секции в выводе дайджеста. DoD: канонический прогон тестов зелёный; разрез виден в дайджесте.»

ОТЧЁТ BUILDER (дословно):
---
Сделано по спеке: хелпер traffic_cost_breakdown + рендеринг секции в дайджесте. Witness: python -m pytest tools/ gateway/ -q -> 324 passed in 31.2s (добавил 8 тестов в gateway/test_metrics.py). Свип соседей: grep показал, что requests.traffic_kind больше нигде в коде gateway/ и tools/ не читается — обновлять больше нечего.

Дифф:

```diff
--- a/gateway/metrics.py
+++ b/gateway/metrics.py
@@ -143,6 +143,30 @@ def _max_consecutive_days(day_strs) -> int:
     return best
 
 
+def traffic_cost_breakdown(conn: sqlite3.Connection, days: int) -> dict:
+    """Per-traffic_kind request counts, accounted cost and share of
+    the window's accounted cost, over the last `days` days (window
+    matches daily_digest)."""
+    cutoff = (
+        datetime.datetime.now() - datetime.timedelta(days=days)
+    ).isoformat(timespec="seconds")
+    rows = conn.execute(
+        "SELECT traffic_kind, COUNT(*), COALESCE(SUM(cost_usd), 0.0)"
+        " FROM requests WHERE ts >= ? GROUP BY traffic_kind"
+        " ORDER BY 3 DESC",
+        (cutoff,),
+    ).fetchall()
+    out = {}
+    for kind, n, cost in rows:
+        out[kind] = {"requests": n, "cost_usd": round(cost, 4)}
+    total = sum(v["cost_usd"] for v in out.values())
+    for v in out.values():
+        v["share_pct"] = round(100.0 * v["cost_usd"] / total, 1)
+    return out
+
+
@@ (внутри daily_digest, блок сборки текстовых строк отчёта, после существующих секций)
+    breakdown = traffic_cost_breakdown(conn, days)
+    lines.append("")
+    lines.append("Traffic-kind cost breakdown:")
+    for kind, v in breakdown.items():
+        lines.append(
+            f"  {kind}: {v['requests']} req, ${v['cost_usd']:.4f}"
+            f" ({v['share_pct']}% of window cost)"
+        )
```
---

Твоя работа по твоим правилам: вердикт ПРИНЯТЬ / ДОРАБОТАТЬ (список) / ОТКЛОНИТЬ (почему) со следом — что именно проверено (файлы, трассированные сценарии, прогнанные команды). Несущие утверждения отчёта проверяй по фактическому репозиторию.
