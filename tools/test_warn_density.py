"""Тесты tools/warn_density.py -- узел I (t-574, спека docs/tasks/
2026-08-20_nodeI-warn-density-spec.md).

Структура: структурное определение §1 (включая КРАСНЫЙ КОНТРОЛЬ DoD-2),
дедуп §3, реестр/--check DoD-4, все 12 краёв §6, границы (Лимиты),
адверсариальная батарея §6, фикстурный контроль (DoD-3, тест на
падение). Синтетика живёт в tmp_path -- боевые артефакты репозитория
(warn_layers.json, транскрипты вне репо) НЕ портятся; несколько тестов
читают РЕАЛЬНЫЙ tools/warn_layers.json и PROCESS/WEEKLY_CALIBRATION_
PROTOCOL.md read-only для интеграционной сверки с деревом.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import warn_density as wd  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _layer(
    id="L1", name="L1", carrier=None, symbol=None, literal="LIT WARN:",
    aliases=None, hook_event="PreToolUse", matcher="Task|Agent",
    denominator="Z1", listed=True,
    reachable="unmeasured", reachable_reason="reachable не объявлен в реестре",
) -> wd.LayerDef:
    # Узел B: reachable по умолчанию -- "unmeasured" с тем же синтетическим
    # reason, что validate_layers подставляет при ОТСУТСТВИИ поля в
    # реестре (см. warn_density.validate_layers) -- слои, СКОНСТРУИРОВАННЫЕ
    # напрямую (минуя validate_layers), ведут себя идентично реестровым.
    if reachable != "unmeasured":
        reachable_reason = None
    return wd.LayerDef(
        id=id, name=name, carrier=carrier or ["carrier.py"], symbol=symbol,
        literal=literal, aliases=aliases or [], hook_event=hook_event,
        matcher=matcher, denominator=denominator, listed_in_check_11v=listed,
        reachable=reachable, reachable_reason=reachable_reason,
    )


def _hook_success_line(
    uuid="u1", ts="2026-01-01T00:00:00.000Z", tool_use_id="tu1",
    hook_name="PreToolUse:Agent", additional_context="LIT WARN: hit",
    rec_type=None, extra_message=None, ensure_ascii=False,
) -> str:
    rec = {"uuid": uuid, "timestamp": ts}
    if rec_type:
        rec["type"] = rec_type
    if extra_message:
        rec["message"] = extra_message
    rec["attachment"] = {
        "type": "hook_success",
        "hookName": hook_name,
        "toolUseID": tool_use_id,
        "stdout": json.dumps(
            {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": additional_context}},
            ensure_ascii=ensure_ascii,
        ),
    }
    return json.dumps(rec, ensure_ascii=False)


def _tool_use_line(ts="2026-01-01T00:00:00.500Z", name="Agent", uuid="tu-line", input_=None, tool_use_id="tuX") -> str:
    item = {"type": "tool_use", "id": tool_use_id, "name": name}
    if input_ is not None:
        item["input"] = input_
    rec = {
        "uuid": uuid, "timestamp": ts, "type": "assistant",
        "message": {"content": [item]},
    }
    return json.dumps(rec, ensure_ascii=False)


def _write_lines(path: Path, lines) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# §1 -- структурное определение срабатывания
# ---------------------------------------------------------------------------

def test_hook_success_structural_counted(tmp_path):
    f = _write_lines(tmp_path / "s1.jsonl", [_hook_success_line()])
    rep = wd.process_corpus([f], [_layer()], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)


def test_prose_mention_not_counted():
    """КРАСНЫЙ КОНТРОЛЬ (DoD-2), часть 1: имя слоя в ТЕЛЕ СООБЩЕНИЯ
    ассистента -- НЕ hook_success -- счётчик обязан вернуть 0."""
    layer = _layer()
    tmp = _fixture_tmp()
    lines = [
        json.dumps({
            "uuid": "u-prose", "timestamp": "2026-01-01T00:00:00.000Z", "type": "assistant",
            "message": {"content": [{"type": "text", "text": "см. LIT WARN: в логе выше"}]},
        }, ensure_ascii=False)
    ]
    f = _write_lines(tmp / "prose.jsonl", lines)
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (0, 0)


def test_tool_use_result_not_counted():
    """КРАСНЫЙ КОНТРОЛЬ (DoD-2), часть 2: имя слоя в toolUseResult
    (вывод инструмента -- греп/ручной прогон) -- НЕ hook_success --
    счётчик обязан вернуть 0. Это ровно класс, что дал F10."""
    layer = _layer()
    tmp = _fixture_tmp()
    lines = [
        json.dumps({
            "uuid": "u-result", "timestamp": "2026-01-01T00:00:00.000Z", "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "grep: LIT WARN: found in source"}]},
        }, ensure_ascii=False)
    ]
    f = _write_lines(tmp / "result.jsonl", lines)
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (0, 0)


def test_both_red_controls_together_with_one_real_hit():
    """Смешанный файл: 1 реальный hook_success + prose-упоминание +
    toolUseResult-упоминание -- итог обязан быть РОВНО 1/1, а не 3."""
    layer = _layer()
    tmp = _fixture_tmp()
    lines = [
        _hook_success_line(uuid="u1", tool_use_id="tu1"),
        json.dumps({
            "uuid": "u-prose", "timestamp": "2026-01-01T00:00:01.000Z", "type": "assistant",
            "message": {"content": [{"type": "text", "text": "LIT WARN: упомянуто в проза"}]},
        }, ensure_ascii=False),
        json.dumps({
            "uuid": "u-result", "timestamp": "2026-01-01T00:00:02.000Z", "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "LIT WARN: в выводе инструмента"}]},
        }, ensure_ascii=False),
    ]
    f = _write_lines(tmp / "mixed.jsonl", lines)
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)


def test_hook_additional_context_ignored_entirely():
    """§3.1: второй след ТОГО ЖЕ срабатывания (hook_additional_context)
    игнорируется ЦЕЛИКОМ -- не даёт даже возможности что-то посчитать."""
    layer = _layer()
    tmp = _fixture_tmp()
    lines = [
        _hook_success_line(uuid="u1", tool_use_id="tu1"),
        json.dumps({
            "uuid": "u2", "timestamp": "2026-01-01T00:00:01.000Z",
            "attachment": {"type": "hook_additional_context", "hookName": "PreToolUse:Agent",
                            "toolUseID": "tu1"},
        }, ensure_ascii=False),
    ]
    f = _write_lines(tmp / "dup.jsonl", lines)
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.total_hook_additional_context == 1
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)


# ---------------------------------------------------------------------------
# Кратность (§1, Лимиты)
# ---------------------------------------------------------------------------

def test_multiplicity_one_line_calls1_lines1(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "m1.jsonl", [_hook_success_line(additional_context="LIT WARN: one")])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)


def test_multiplicity_five_lines_calls1_lines5(tmp_path):
    layer = _layer()
    ctx = "; ".join(["LIT WARN: rep"] * 5)
    f = _write_lines(tmp_path / "m5.jsonl", [_hook_success_line(additional_context=ctx)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 5)


# ---------------------------------------------------------------------------
# §3 -- дедуп
# ---------------------------------------------------------------------------

def test_dedup_cross_file_same_unit(tmp_path):
    """ЗФ-2 безопасен по построению: одно и то же (toolUseID, hookName)
    в РОДИТЕЛЬСКОМ файле и в файле subagent -- считается ОДИН раз,
    дубль снят и виден в dedup_dropped."""
    layer = _layer()
    f1 = _write_lines(tmp_path / "parent.jsonl", [_hook_success_line(uuid="pu1", tool_use_id="shared-tu")])
    f2 = _write_lines(tmp_path / "sub.jsonl", [_hook_success_line(uuid="su1", tool_use_id="shared-tu")])
    rep = wd.process_corpus([f1, f2], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.dedup_dropped == 1


def test_no_dedup_across_different_units(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "two.jsonl", [
        _hook_success_line(uuid="u1", tool_use_id="tu1"),
        _hook_success_line(uuid="u2", tool_use_id="tu2", ts="2026-01-01T00:00:01.000Z"),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (2, 2)


# ---------------------------------------------------------------------------
# Единицы счёта -- toolUseID / uuid fallback / line fallback (край 7)
# ---------------------------------------------------------------------------

def test_unit_key_uuid_fallback_when_no_tool_use_id(tmp_path):
    layer = _layer()
    rec = {
        "uuid": "sess-uuid-1", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "SessionStart:startup",
            "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": "LIT WARN: boot"}}),
        },
    }
    f = _write_lines(tmp_path / "boot.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.fallback_key_count == 0


def test_unit_key_line_fallback_when_no_uuid_no_tool_use_id(tmp_path):
    layer = _layer()
    rec = {
        "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent",
            "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": "LIT WARN: no-id"}}),
        },
    }
    f = _write_lines(tmp_path / "noid.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.fallback_key_count == 1
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)


# ---------------------------------------------------------------------------
# Реестр -- валидация формы (DoD-4, края 3.4/11, адверсариальная батарея)
# ---------------------------------------------------------------------------

def _raw_layer(**kw):
    base = {
        "id": "X", "name": "X", "carrier": ["c.py"], "symbol": None,
        "literal": "X WARN:", "aliases": [], "hook_event": "PreToolUse",
        "matcher": "Task|Agent", "denominator": "Z1", "listed_in_check_11v": True,
    }
    base.update(kw)
    return base


def test_registry_overlap_literal_is_substring_of_another():
    a = _raw_layer(id="A", literal="WARN:")
    b = _raw_layer(id="B", literal="OWNS WARN: extra")
    layers, defects = wd.validate_layers([a, b])
    assert any("перекрытие" in d.lower() for d in defects)


def test_registry_no_overlap_distinct_prefixes():
    a = _raw_layer(id="A", literal="AAA WARN:")
    b = _raw_layer(id="B", literal="BBB WARN:")
    layers, defects = wd.validate_layers([a, b])
    assert defects == []
    assert len(layers) == 2


def test_registry_brace_in_literal_is_defect():
    a = _raw_layer(id="A", literal="TEMPLATE {placeholder} WARN:")
    layers, defects = wd.validate_layers([a])
    assert any("{" in d for d in defects)
    assert layers == []


def test_registry_empty_carrier_list_is_defect():
    a = _raw_layer(id="A", carrier=[])
    layers, defects = wd.validate_layers([a])
    assert any("carrier" in d for d in defects)
    assert layers == []


def test_registry_duplicate_id_is_defect():
    a = _raw_layer(id="DUP")
    b = _raw_layer(id="DUP", literal="OTHER WARN:")
    layers, defects = wd.validate_layers([a, b])
    assert any("дубль id" in d for d in defects)


def test_registry_single_bad_entry_does_not_kill_others():
    """D-0043 'не трейсбек': дефект ОДНОЙ записи не рвёт прогон --
    остальные валидные записи измеряются."""
    good = _raw_layer(id="GOOD")
    bad = _raw_layer(id="BAD", carrier=[])
    layers, defects = wd.validate_layers([good, bad])
    assert len(layers) == 1 and layers[0].id == "GOOD"
    assert any("BAD" in d for d in defects)


# ---------------------------------------------------------------------------
# check_liveness -- включая находку про конкатенацию соседних строк
# ---------------------------------------------------------------------------

def test_liveness_found_plain(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text('MSG = "HELLO WARN: text"\n', encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], literal="HELLO WARN:")
    alive, _ = wd.check_liveness(layer, tmp_path)
    assert alive is True


def test_liveness_found_across_string_concat_seam(tmp_path):
    """НАХОДКА билдера: литерал, собранный СОСЕДНИМИ python-строками
    ('...this ' \\n '...session...'), живой в исходнике, но наивный
    substring-поиск по сырому тексту carrier'а его не находит без
    склейки шва конкатенации."""
    carrier = tmp_path / "carrier.py"
    carrier.write_text(
        'MSG_TEMPLATE = (\n'
        '    "Negative claim about to be written without a matching search/read this "\n'
        '    "session (rule 6)"\n'
        ')\n',
        encoding="utf-8",
    )
    layer = _layer(
        carrier=["carrier.py"],
        literal="Negative claim about to be written without a matching search/read this session",
    )
    alive, reason = wd.check_liveness(layer, tmp_path)
    assert alive is True, reason


def test_liveness_dead_literal_not_found(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text('MSG = "totally unrelated text"\n', encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], literal="MISSING WARN:")
    alive, reason = wd.check_liveness(layer, tmp_path)
    assert alive is False


def test_liveness_alias_counts_as_alive(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text('MSG = "OLD FORM WARN: legacy"\n', encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], literal="NEW FORM WARN:", aliases=["OLD FORM WARN:"])
    alive, _ = wd.check_liveness(layer, tmp_path)
    assert alive is True


def test_liveness_carrier_is_list_second_entry_carries_it(tmp_path):
    """Край 11: один литерал -- ДВА носителя (список); достаточно, что
    он жив ХОТЯ БЫ в одном."""
    c1 = tmp_path / "c1.py"
    c1.write_text("# nothing here\n", encoding="utf-8")
    c2 = tmp_path / "c2.py"
    c2.write_text('MSG = "FOUND HERE WARN: x"\n', encoding="utf-8")
    layer = _layer(carrier=["c1.py", "c2.py"], literal="FOUND HERE WARN:")
    alive, _ = wd.check_liveness(layer, tmp_path)
    assert alive is True


# ---------------------------------------------------------------------------
# --check (DoD-4) -- позитив/негатив
# ---------------------------------------------------------------------------

def test_check_clean_registry_exit0(tmp_path):
    reg = {"registry_version": 1, "layers": [_raw_layer(id="A", carrier=["c.py"], literal="A WARN:")]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text"\n', encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 0
    assert "дефектов нет" in text


def test_check_dead_literal_exit1_verbatim_defect_marker(tmp_path):
    reg = {"registry_version": 1, "layers": [_raw_layer(id="A", carrier=["c.py"], literal="MISSING WARN:")]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "unrelated"\n', encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 1
    assert "ДЕФЕКТ РЕЕСТРА" in text


def test_check_real_repo_registry_is_clean():
    """Интеграционный позитив: БОЕВОЙ tools/warn_layers.json read-only
    против БОЕВОГО дерева -- все 19 литералов живы (перепроверено
    чтением при постройке узла FRESHNESS, 2026-08-25 -- было 18)."""
    text, code = wd.run_check(wd.DEFAULT_REGISTRY, REPO_ROOT, transcripts_dir=None)
    assert code == 0, text
    assert "слоёв в реестре: 20 (валидных: 20)" in text


def test_check_source_empty_is_defect(tmp_path):
    reg = {"registry_version": 1, "layers": [_raw_layer(id="A", carrier=["c.py"], literal="A WARN:")]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text"\n', encoding="utf-8")
    empty_src = tmp_path / "empty_src"
    empty_src.mkdir()
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path, transcripts_dir=empty_src)
    assert code == 1
    assert "ИСТОЧНИК ПУСТ" in text


# ---------------------------------------------------------------------------
# Края §6 -- по номерам
# ---------------------------------------------------------------------------

def test_edge1_empty_window_prints_marker_exit0(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "any.jsonl", [_hook_success_line(ts="2020-01-01T00:00:00.000Z")])
    ws = _dt("2026-01-01T00:00:00")
    we = _dt("2026-01-02T00:00:00")
    rep = wd.process_corpus([f], [layer], ws, we, {}, compute_fixture=False)
    assert rep.in_window_records == 0
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "ОКНО ПУСТО: 0 записей" in text
    c = rep.counts["L1"]
    assert c.calls == 0


def test_edge2_zero_layer_alive_verdict(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text('MSG = "LIT WARN: exists"\n', encoding="utf-8")
    layer = _layer(carrier=["carrier.py"])
    f = _write_lines(tmp_path / "quiet.jsonl", [_tool_use_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "L1 [L1]: жив" in text


def test_edge2_zero_layer_dead_registry_verdict(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text('MSG = "unrelated"\n', encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], literal="NEVER PRESENT WARN:")
    f = _write_lines(tmp_path / "quiet2.jsonl", [_tool_use_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "L1 [L1]: ДЕФЕКТ РЕЕСТРА" in text


def test_edge3_source_missing_exit2():
    with pytest.raises(wd.SourceError):
        wd.enumerate_corpus_files(Path("Z:/definitely/not/here/xyz123"))


def test_edge3_source_exists_zero_files(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    files = wd.enumerate_corpus_files(empty)
    assert files == []


def test_edge4_broken_lines_n_minus_1_of_n_no_defect(tmp_path):
    f = tmp_path / "broken.jsonl"
    f.write_text("not json 1\nnot json 2\n" + _hook_success_line() + "\n", encoding="utf-8")
    layer = _layer()
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.broken_lines == 2 and rep.total_lines_seen == 3
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "ДЕФЕКТ ИСТОЧНИКА" not in text


def test_edge4_broken_lines_all_of_n_is_defect(tmp_path):
    f = tmp_path / "allbroken.jsonl"
    f.write_text("not json 1\nnot json 2\nnot json 3\n", encoding="utf-8")
    layer = _layer()
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.broken_lines == 3 and rep.total_lines_seen == 3
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "ДЕФЕКТ ИСТОЧНИКА: 100% строк биты (3/3)" in text


def test_edge5_sidecar_absent_first_run(tmp_path):
    sc = tmp_path / "sidecar.jsonl"
    assert not sc.exists()
    last, warns = wd.read_sidecar_last(sc)
    assert last is None and warns == []
    entry = {"ts": "x", "registry_sha": "abc"}
    warn = wd.write_sidecar_entry(sc, entry)
    assert warn is None
    assert sc.exists()


def test_edge5_sidecar_write_oserror_is_warn_not_exception(tmp_path):
    # директория вместо файла -- запись в неё вызовет OSError на open("a")
    bad_path = tmp_path / "not_writable_dir"
    bad_path.mkdir()
    warn = wd.write_sidecar_entry(bad_path, {"x": 1})
    assert warn is not None
    assert "сайдкар не записан" in warn


def test_edge6_no_timestamp_always_counted(tmp_path):
    layer = _layer()
    rec_no_ts = {
        "uuid": "u-no-ts",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent", "toolUseID": "tu-no-ts",
            "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": "LIT WARN: x"}}),
        },
    }
    f = _write_lines(tmp_path / "nots.jsonl", [json.dumps(rec_no_ts, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.no_timestamp == 1
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (0, 0)  # без времени -- в оконный счёт НЕ входит


def test_edge7_fallback_key_count_printed_when_zero(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "ok.jsonl", [_hook_success_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.fallback_key_count == 0
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "fallback-ключ" in text


def test_edge8_raw_fallback_separate_counter_ascii(tmp_path):
    """stdout НЕ парсится как JSON целиком (например, обрезан) --
    литерал ищется по СЫРОЙ строке, отдельный счётчик raw-match,
    НЕ смешивается с calls/lines."""
    layer = _layer(literal="LIT WARN:")
    rec = {
        "uuid": "u-raw", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent", "toolUseID": "tu-raw",
            "stdout": '{"hookSpecificOutput": {"additionalContext": "LIT WARN: truncat',  # обрезан
        },
    }
    f = _write_lines(tmp_path / "trunc.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (0, 0)
    assert (c.raw_calls, c.raw_lines) == (1, 1)
    assert rep.raw_parse_failed == 1


def test_edge8_9_raw_fallback_escaped_unicode_form(tmp_path):
    """НАХОДКА билдера: journal_echo.py печатает JSON с ensure_ascii=
    True -- кириллица в СЫРОМ stdout лежит как \\uXXXX, не байтами.
    raw-fallback обязан находить литерал и в ЭТОЙ форме, иначе
    ослепнет именно на кириллических слоях при обрезке (ЗФ-3)."""
    layer = _layer(literal="TIER ECHO: строка ")
    escaped = wd._json_escaped_form("TIER ECHO: строка ")
    raw_stdout = '{"hookSpecificOutput": {"additionalContext": "' + escaped + '42 measured..."'  # обрезан, без закрытия
    rec = {
        "uuid": "u-esc", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PostToolUse:Edit", "toolUseID": "tu-esc",
            "stdout": raw_stdout,
        },
    }
    f = _write_lines(tmp_path / "esc.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.raw_calls, c.raw_lines) == (1, 1)


def test_edge9_structural_priority_when_json_parses_raw_text_ignored(tmp_path):
    """Приоритет разбора: структурный ВСЕГДА первый. Если json.loads
    УСПЕШЕН, но additionalContext не несёт литерал (он есть только в
    ДРУГОМ, нерелевантном месте сырого текста -- напр. в permission
    reason), это НЕ считается ни структурно, ни как raw (raw вообще не
    запускается при успешном парсинге)."""
    layer = _layer(literal="LIT WARN:")
    stdout = json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecisionReason": "LIT WARN: this text lives OUTSIDE additionalContext",
            "additionalContext": "no match here",
        }
    })
    rec = {
        "uuid": "u-prio", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent", "toolUseID": "tu-prio",
            "stdout": stdout,
        },
    }
    f = _write_lines(tmp_path / "prio.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (0, 0)
    assert (c.raw_calls, c.raw_lines) == (0, 0)
    assert rep.raw_parse_failed == 0


def test_edge10_dead_registry_literal_still_counts_via_alias(tmp_path):
    """Второй конфликт §6: реестр объявляет 'мёртвый' (в текущем
    носителе не найденный) литерал, но он же (или алиас) даёт
    срабатывания в старых транскриптах -- срабатывания считаются, но
    ДЕФЕКТ РЕЕСТРА печатается всё равно (счёт и живость независимы)."""
    carrier = tmp_path / "carrier.py"
    carrier.write_text('MSG = "NEW FORM WARN: only this lives now"\n', encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], literal="NEW FORM WARN:", aliases=["OLD DEAD WARN:"])
    alive, _ = wd.check_liveness(layer, tmp_path)  # жив по 'NEW FORM WARN:'
    assert alive is True
    # реестр с ЕДИНСТВЕННО мёртвым литералом -- проверяем что счёт по алиасу
    # не зависит от отдельной (несвязанной) живости другого литерала слоя
    dead_layer = _layer(id="D", carrier=["carrier.py"], literal="TOTALLY DEAD WARN:", aliases=[])
    alive2, _ = wd.check_liveness(dead_layer, tmp_path)
    assert alive2 is False
    f = _write_lines(tmp_path / "old.jsonl", [
        _hook_success_line(additional_context="TOTALLY DEAD WARN: still fires from old transcript")
    ])
    rep = wd.process_corpus([f], [dead_layer], None, None, {}, compute_fixture=False)
    c = rep.counts["D"]
    assert (c.calls, c.lines) == (1, 1)  # срабатывание считается несмотря на мёртвый реестр


def test_edge11_carrier_list_two_files_not_a_defect():
    a = _raw_layer(id="A", carrier=["c1.py", "c2.py"])
    layers, defects = wd.validate_layers([a])
    assert defects == []
    assert layers[0].carrier == ["c1.py", "c2.py"]


def test_edge12_clock_both_representations_printed(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "clock.jsonl", [_hook_success_line()])
    ws = wd.parse_window_bound("2026-01-01T00:00:00")
    we = wd.parse_window_bound("2026-01-02T00:00:00")
    rep = wd.process_corpus([f], [layer], ws, we, {}, compute_fixture=False)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "локально" in text and "UTC" in text


# ---------------------------------------------------------------------------
# Лимиты -- границы (на границе И за ней, оба обязательны)
# ---------------------------------------------------------------------------

def test_limit_window_start_inclusive(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "inc.jsonl", [_hook_success_line(ts="2026-01-01T00:00:00.000Z")])
    ws = wd.parse_window_bound("2026-01-01T00:00:00")
    # локальная граница == UTC ts ровно -- заставим окно совпасть по UTC явно
    ws_utc = _dt("2026-01-01T00:00:00")
    rep = wd.process_corpus([f], [layer], ws_utc, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert c.calls == 1  # ts РОВНО start -- ВХОДИТ


def test_limit_window_end_exclusive(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "exc.jsonl", [_hook_success_line(ts="2026-01-01T00:00:00.000Z")])
    we_utc = _dt("2026-01-01T00:00:00")
    rep = wd.process_corpus([f], [layer], None, we_utc, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert c.calls == 0  # ts РОВНО end -- НЕ входит


def test_limit_window_just_before_end_included(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "just.jsonl", [_hook_success_line(ts="2025-12-31T23:59:59.999Z")])
    we_utc = _dt("2026-01-01T00:00:00")
    rep = wd.process_corpus([f], [layer], None, we_utc, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert c.calls == 1


def test_limit_matcher_one_calls_one_via_matcher_total(tmp_path):
    """МАТЧЕР-число (старый Z1, layer_matcher_total -- переименованный
    layer_denominator_value, Б-К2) сохраняется НЕЗАВИСИМО от достижимо."""
    layer = _layer(matcher="Agent")
    f = _write_lines(tmp_path / "one.jsonl", [
        _hook_success_line(),
        _tool_use_line(name="Agent"),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    matcher_total = wd.layer_matcher_total(layer, rep.tool_use_counts)
    c = rep.counts["L1"]
    assert matcher_total == 1 and c.calls == 1


def test_bk1_achievable_one_calls_one_is_100_percent(tmp_path):
    """Б-К1: доля теперь считается от ДОСТИЖИМО (не от матчера).
    Граница на достижимо==1, calls==1 -> 100.0% (Края спеки узла B)."""
    layer = _layer(matcher="Agent", reachable="subagent_type_builder")
    f = _write_lines(tmp_path / "one.jsonl", [
        _hook_success_line(),
        _tool_use_line(name="Agent", input_={"subagent_type": "builder"}),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    achievable, unreachable, matcher_total = wd.layer_population(layer, rep)
    assert (achievable, unreachable, matcher_total) == (1, 0, 1)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "достижимо=1 недостижимо=0 матчер=1" in text
    assert "доля=100.0%" in text


def test_bk3_unmeasured_layer_prints_reason_no_percent(tmp_path):
    """Б-К3: слой без объявленной популяции (reachable=unmeasured)
    печатает н-д с reason и НЕ печатает процент -- НЕ тихий откат к
    матчер-Z1 (это же слой раньше давал доля=100.0% при матчере==вызовам)."""
    layer = _layer(matcher="Agent", reachable="unmeasured", reachable_reason="тестовая причина")
    f = _write_lines(tmp_path / "unmeasured.jsonl", [
        _hook_success_line(),
        _tool_use_line(name="Agent"),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    achievable, unreachable, matcher_total = wd.layer_population(layer, rep)
    assert (achievable, unreachable, matcher_total) == (None, None, 1)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "достижимо=н-д недостижимо=н-д матчер=1" in text
    assert "доля=н-д (популяция не объявлена: тестовая причина)" in text
    assert "доля=100.0%" not in text
    assert "доля=0.0%" not in text


def test_edge_achievable_zero_matcher_positive_is_na_never_zero_percent(tmp_path):
    """Край спеки узла B: достижимо==0 при матчер>0 -- «н-д (достижимо 0
    из N)», НЕ 0.0%, НЕ деление на ноль (измеримый reachable, просто в
    этом окне ни один matcher-вызов не удовлетворил предикат)."""
    layer = _layer(matcher="Agent", reachable="subagent_type_builder")
    f = _write_lines(tmp_path / "zero.jsonl", [
        _hook_success_line(),
        _tool_use_line(name="Agent", input_={"subagent_type": "scout"}),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    achievable, unreachable, matcher_total = wd.layer_population(layer, rep)
    assert (achievable, unreachable, matcher_total) == (0, 1, 1)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "доля=н-д (достижимо 0 из 1)" in text
    assert "доля=0.0%" not in text


def test_limit_overlap_check_exit1_via_run_check(tmp_path):
    reg = {"registry_version": 1, "layers": [
        _raw_layer(id="A", carrier=["c.py"], literal="WARN:"),
        _raw_layer(id="B", carrier=["c.py"], literal="OWNS WARN: extra"),
    ]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "OWNS WARN: extra"\n', encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 1
    assert "перекрытие" in text.lower()


def test_limit_kratnost_boundary_1_vs_5(tmp_path):
    # уже покрыто test_multiplicity_*; здесь -- явная граница "1 vs >1"
    layer = _layer()
    f1 = _write_lines(tmp_path / "k1.jsonl", [_hook_success_line(additional_context="LIT WARN: x")])
    rep1 = wd.process_corpus([f1], [layer], None, None, {}, compute_fixture=False)
    assert (rep1.counts["L1"].calls, rep1.counts["L1"].lines) == (1, 1)


# ---------------------------------------------------------------------------
# Адверсариальная батарея (§6, R11(e))
# ---------------------------------------------------------------------------

def test_adversarial_invalid_iso_exit2_no_traceback():
    with pytest.raises(wd.ArgError):
        wd.parse_window_bound("not-a-date")


def test_adversarial_start_after_end_exit2(tmp_path, capsys):
    reg = wd.DEFAULT_REGISTRY
    code = wd.main([
        "--window-start", "2026-01-02T00:00:00",
        "--window-end", "2026-01-01T00:00:00",
        "--registry-file", str(reg),
        "--transcripts", str(tmp_path),
    ])
    assert code == 2


def test_adversarial_transcripts_on_a_file_exit2(tmp_path):
    f = tmp_path / "not_a_dir.jsonl"
    f.write_text("{}\n", encoding="utf-8")
    with pytest.raises(wd.SourceError):
        wd.enumerate_corpus_files(f)


def test_adversarial_path_with_spaces_and_cyrillic(tmp_path):
    d = tmp_path / "путь с пробелами и кириллицей"
    d.mkdir()
    layer = _layer()
    f = _write_lines(d / "file.jsonl", [_hook_success_line()])
    files = wd.enumerate_corpus_files(d)
    assert files == [f]
    rep = wd.process_corpus(files, [layer], None, None, {}, compute_fixture=False)
    assert rep.counts["L1"].calls == 1


def test_adversarial_bom_and_crlf(tmp_path):
    layer = _layer()
    f = tmp_path / "bomcrlf.jsonl"
    line = _hook_success_line()
    f.write_bytes(b"\xef\xbb\xbf" + line.encode("utf-8") + b"\r\n")
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.counts["L1"].calls == 1
    assert rep.broken_lines == 0


def test_adversarial_megabyte_line_streaming(tmp_path):
    layer = _layer()
    big_text = "x" * (2 * 1024 * 1024)  # 2 МБ мусора внутри поля -- не должно уронить/зависнуть
    rec = {
        "uuid": "u-big", "timestamp": "2026-01-01T00:00:00.000Z", "type": "assistant",
        "message": {"content": [{"type": "text", "text": big_text}]},
    }
    f = _write_lines(tmp_path / "big.jsonl", [json.dumps(rec, ensure_ascii=False), _hook_success_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.counts["L1"].calls == 1
    assert rep.broken_lines == 0


def test_adversarial_nested_escaped_quotes_and_emdash(tmp_path):
    """Реальные литералы owns_gate несут '—' (тире) и кавычки внутри
    additionalContext -- литерал находится ПОСЛЕ декодирования."""
    layer = _layer(literal='owns объявлен, путей не разобрано')
    ctx = 'owns объявлен, путей не разобрано \u2014 сверка \\"пересечений\\" слепа'
    rec = {
        "uuid": "u-dash", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent", "toolUseID": "tu-dash",
            "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": ctx}}, ensure_ascii=False),
        },
    }
    f = _write_lines(tmp_path / "dash.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.counts["L1"].calls == 1


def test_adversarial_empty_registry_check_exit1(tmp_path):
    (tmp_path / "empty_reg.json").write_text(json.dumps({"registry_version": 1, "layers": []}), encoding="utf-8")
    text, code = wd.run_check(tmp_path / "empty_reg.json", tmp_path)
    assert code == 0  # пустой реестр -- НЕ дефект формы САМ ПО СЕБЕ (0 записей, 0 дефектов)
    assert "слоёв в реестре: 0" in text


def test_adversarial_empty_registry_normal_run_prints_zero_layers(tmp_path):
    (tmp_path / "empty_reg.json").write_text(json.dumps({"registry_version": 1, "layers": []}), encoding="utf-8")
    _, raw_layers, _ = wd.read_registry_raw(tmp_path / "empty_reg.json")
    layers, defects = wd.validate_layers(raw_layers)
    assert layers == [] and defects == []


def test_adversarial_duplicate_id_check_exit1(tmp_path):
    reg = {"registry_version": 1, "layers": [
        _raw_layer(id="DUP", carrier=["c.py"], literal="A WARN:"),
        _raw_layer(id="DUP", carrier=["c.py"], literal="B WARN:"),
    ]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: B WARN:"\n', encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 1
    assert "дубль id" in text


def test_adversarial_brace_in_literal_check_exit1(tmp_path):
    reg = {"registry_version": 1, "layers": [_raw_layer(id="A", literal="TEMPLATE {x} WARN:")]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 1


def test_adversarial_registry_not_json_exit2(tmp_path):
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(wd.RegistryError):
        wd.read_registry_raw(tmp_path / "bad.json")


# ---------------------------------------------------------------------------
# Фикстурный контроль (DoD-3): фикстура ОБЯЗАНА мочь упасть
# ---------------------------------------------------------------------------

def test_fixture_control_passes_on_intact_registry():
    calls, lines = wd.fixture_control(_real_registry_layers())
    assert (calls, lines) == (wd.FIXTURE_EXPECTED_CALLS, wd.FIXTURE_EXPECTED_LINES)


def test_fixture_control_can_fail_when_literal_broken():
    """DoD-3: фикстурный контроль МОЖЕТ УПАСТЬ -- подменяем литерал
    слоя фикстуры на несуществующий в фикстурных данных текст, счётчик
    обязан вернуть 0/2, 0/3 (не 2/2, не молчаливый ноль без причины)."""
    layers = _real_registry_layers()
    broken = [
        wd.LayerDef(
            id=l.id, name=l.name, carrier=l.carrier, symbol=l.symbol,
            literal="THIS-NEVER-APPEARS-IN-FIXTURE-XYZ" if l.id == wd._FIXTURE_LAYER_ID else l.literal,
            aliases=[], hook_event=l.hook_event, matcher=l.matcher,
            denominator=l.denominator, listed_in_check_11v=l.listed_in_check_11v,
        )
        for l in layers
    ]
    calls, lines = wd.fixture_control(broken)
    assert (calls, lines) != (wd.FIXTURE_EXPECTED_CALLS, wd.FIXTURE_EXPECTED_LINES)
    assert (calls, lines) == (0, 0)


def test_fixture_control_missing_fixture_layer_returns_zero():
    layers = [_layer(id="OTHER", literal="OTHER WARN:")]
    calls, lines = wd.fixture_control(layers)
    assert (calls, lines) == (0, 0)


# ---------------------------------------------------------------------------
# proxy / denominator (Р1)
# ---------------------------------------------------------------------------

def test_proxy_true_when_matcher_shared_by_two_hooks(tmp_path):
    settings = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Task|Agent", "hooks": [{"type": "command", "command": "a"}, {"type": "command", "command": "b"}]},
            ]
        }
    }
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(settings), encoding="utf-8")
    pm = wd.load_hook_multiplicity(p)
    layer = _layer(hook_event="PreToolUse", matcher="Task|Agent")
    assert wd.layer_is_proxy(layer, pm) is True


def test_proxy_false_when_matcher_exclusive(tmp_path):
    settings = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash|PowerShell", "hooks": [{"type": "command", "command": "a"}]},
            ]
        }
    }
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(settings), encoding="utf-8")
    pm = wd.load_hook_multiplicity(p)
    layer = _layer(hook_event="PreToolUse", matcher="Bash|PowerShell")
    assert wd.layer_is_proxy(layer, pm) is False


def test_denominator_sums_matching_tool_names(tmp_path):
    """МАТЧЕР (не достижимо) -- layer_matcher_total, переименованный
    layer_denominator_value, семантика Z1 не изменилась."""
    layer = _layer(matcher="Task|Agent")
    f = _write_lines(tmp_path / "denom.jsonl", [
        _tool_use_line(name="Task", ts="2026-01-01T00:00:00.100Z", uuid="t1"),
        _tool_use_line(name="Agent", ts="2026-01-01T00:00:00.200Z", uuid="t2"),
        _tool_use_line(name="Bash", ts="2026-01-01T00:00:00.300Z", uuid="t3"),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    matcher_total = wd.layer_matcher_total(layer, rep.tool_use_counts)
    assert matcher_total == 2
    assert rep.total_tool_use_in_window == 3


# ---------------------------------------------------------------------------
# 11(в): парсер и сверка (интеграция, read-only)
# ---------------------------------------------------------------------------

def test_parse_check_11v_names_from_live_protocol():
    protocol_path = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
    text = protocol_path.read_text(encoding="utf-8")
    names = wd.parse_check_11v_names(text)
    assert names is not None
    for expected in ["NOTES LEN", "TIER ECHO", "R6-ЗЕРКАЛО", "GIVEN-PATH", "OWNS OVERLAP",
                      "NEGATIVE LINT", "Negative claim", "Search returned nothing"]:
        assert expected in names, (expected, names)


def test_diff_check_11v_matches_known_divergence():
    layers = _real_registry_layers()
    protocol_path = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
    names = wd.parse_check_11v_names(protocol_path.read_text(encoding="utf-8"))
    in_check_not_reg, in_reg_not_check = wd.diff_check_11v(layers, names)
    assert set(in_reg_not_check) == {"DOD-QUOTED", "MANIFEST-QUOTED", "JOURNAL ECHO", "Командная гигиена"}


# ---------------------------------------------------------------------------
# --json смоук
# ---------------------------------------------------------------------------

def test_json_output_is_valid_json(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "j.jsonl", [_hook_success_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    text = wd.render_json(rep, tmp_path, None)
    payload = json.loads(text)
    assert payload["layers"][0]["id"] == "L1"


# ---------------------------------------------------------------------------
# ПРАВКА БЛОКЕРА (критик, 2026-08-20): Ф1 честный знаменатель (main-only,
# субагентский поток невидим), Ф2 осиротевший hook_additional_context
# считается, Ф3 фикстура-дефект в выводе/exit code, Ф4 асимметрия дедупа
# названа строкой.
# ---------------------------------------------------------------------------

def test_f1_denominator_excludes_sidechain_tool_use(tmp_path):
    """Ф1: главный дефект БЛОКЕРА -- sidechain tool_use физически не
    может дать hook_success (структурная невидимость), но раньше шёл в
    Z1. Знаменатель теперь main-only."""
    layer = _layer(matcher="Agent")
    main_file = _write_lines(tmp_path / "main.jsonl", [
        _hook_success_line(), _tool_use_line(name="Agent"),
    ])
    sub_file = _write_lines(tmp_path / "session1" / "subagents" / "sub.jsonl", [
        _tool_use_line(name="Agent", uuid="sub-tu"),
    ])
    rep = wd.process_corpus([main_file, sub_file], [layer], None, None, {}, compute_fixture=False)
    matcher_total = wd.layer_matcher_total(layer, rep.tool_use_counts)
    assert matcher_total == 1
    assert rep.total_tool_use_in_window == 1
    assert rep.sidechain_tool_use_in_window == 1


def test_f1_sidechain_invisibility_line_printed(tmp_path):
    layer = _layer(matcher="Agent")
    main_file = _write_lines(tmp_path / "main.jsonl", [_tool_use_line(name="Agent")])
    sub_file = _write_lines(tmp_path / "session1" / "subagents" / "sub.jsonl", [
        _tool_use_line(name="Agent", uuid="sub-tu"),
    ])
    rep = wd.process_corpus([main_file, sub_file], [layer], None, None, {}, compute_fixture=False)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "субагентский поток невидим: 1 из 2 вызовов окна" in text


def test_f1_is_sidechain_file_classifier():
    assert wd.is_sidechain_file(Path("a/b/subagents/x.jsonl")) is True
    assert wd.is_sidechain_file(Path("a/b/x.jsonl")) is False
    assert wd.is_sidechain_file(Path("a/Subagents/x.jsonl")) is False  # регистр -- граница


def test_f2_orphan_hac_counted(tmp_path):
    """Ф2: осиротевшая (без пары hook_success) hook_additional_context
    -- ЕДИНСТВЕННЫЙ след срабатывания, обязана считаться."""
    layer = _layer(literal="Командная гигиена: ")
    rec = {
        "uuid": "u-orphan", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_additional_context", "hookName": "PreToolUse:Bash",
            "toolUseID": "tu-orphan", "content": ["Командная гигиена: test warn"],
        },
    }
    f = _write_lines(tmp_path / "orphan.jsonl", [json.dumps(rec, ensure_ascii=False)])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.orphan_hac_count == 1


def test_f2_paired_hac_still_not_double_counted(tmp_path):
    """Пара hook_success + hook_additional_context на ОДНОМ ключе --
    как раньше, второй след НЕ добавляет счёт (§3.1 не изменился);
    orphan_hac_count обязан остаться 0."""
    layer = _layer()
    f = _write_lines(tmp_path / "paired.jsonl", [
        _hook_success_line(uuid="u1", tool_use_id="tu1"),
        json.dumps({
            "uuid": "u2", "timestamp": "2026-01-01T00:00:01.000Z",
            "attachment": {"type": "hook_additional_context", "hookName": "PreToolUse:Agent",
                            "toolUseID": "tu1"},
        }, ensure_ascii=False),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.orphan_hac_count == 0


def test_f2_orphan_key_requires_both_tool_use_id_and_hook_name(tmp_path):
    """Граница ключа Ф2: тот же toolUseID, но ДРУГОЙ hookName -- пары
    НЕТ по ключу (toolUseID, hookName), запись всё равно осиротевшая."""
    layer = _layer(literal="Командная гигиена: ")
    f = _write_lines(tmp_path / "mismatch.jsonl", [
        json.dumps({
            "uuid": "u1", "timestamp": "2026-01-01T00:00:00.000Z",
            "attachment": {
                "type": "hook_success", "hookName": "PreToolUse:Bash", "toolUseID": "tu-shared",
                "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": "no match here"}}),
            },
        }, ensure_ascii=False),
        json.dumps({
            "uuid": "u2", "timestamp": "2026-01-01T00:00:01.000Z",
            "attachment": {
                "type": "hook_additional_context", "hookName": "PreToolUse:PowerShell",
                "toolUseID": "tu-shared", "content": ["Командная гигиена: mismatched hook"],
            },
        }, ensure_ascii=False),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.orphan_hac_count == 1


def test_f2_pair_found_regardless_of_file_order(tmp_path):
    """Ф2 порядко-независимость: пара может физически лежать в файле,
    читаемом ПОЗЖЕ (по алфавитной сортировке enumerate_corpus_files)
    относительно orphan-кандидата -- классификация разрешается ПОСЛЕ
    полного прохода по корпусу, не по мере чтения строк."""
    layer = _layer()
    f1 = _write_lines(tmp_path / "a_first.jsonl", [
        json.dumps({
            "uuid": "u2", "timestamp": "2026-01-01T00:00:01.000Z",
            "attachment": {"type": "hook_additional_context", "hookName": "PreToolUse:Agent",
                            "toolUseID": "tu-shared"},
        }, ensure_ascii=False),
    ])
    f2 = _write_lines(tmp_path / "z_second.jsonl", [
        _hook_success_line(uuid="u1", tool_use_id="tu-shared", ts="2026-01-01T00:00:00.000Z"),
    ])
    rep = wd.process_corpus([f1, f2], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.orphan_hac_count == 0


def test_f2_orphan_dedup_via_seen_set(tmp_path):
    """Дубль ОДНОЙ и той же осиротевшей записи (тот же ключ дважды) --
    считается ОДИН раз, снятие видно в dedup_dropped; orphan_hac_count
    считает КАЖДУЮ запись (сырое число), а не после дедупа."""
    layer = _layer(literal="Командная гигиена: ")
    rec = {
        "uuid": "u-orphan", "timestamp": "2026-01-01T00:00:00.000Z",
        "attachment": {
            "type": "hook_additional_context", "hookName": "PreToolUse:Bash",
            "toolUseID": "tu-orphan", "content": ["Командная гигиена: test warn"],
        },
    }
    rec2 = dict(rec)
    rec2["uuid"] = "u-orphan-2"
    rec2["timestamp"] = "2026-01-01T00:00:01.000Z"
    f = _write_lines(tmp_path / "dup_orphan.jsonl", [
        json.dumps(rec, ensure_ascii=False), json.dumps(rec2, ensure_ascii=False),
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    c = rep.counts["L1"]
    assert (c.calls, c.lines) == (1, 1)
    assert rep.orphan_hac_count == 2
    assert rep.dedup_dropped == 1


def test_f3_fixture_mismatch_prints_defect_line_and_nonzero_exit(monkeypatch, tmp_path):
    """DoD-3, перманентная регрессия: затираем fixture_control
    монки-патчем (живой файл НЕ портится) -- строка дефекта обязана
    появиться, wd.main() обязан вернуть НЕНУЛЕВОЙ код (Ф3 -- прогон
    состоялся, но exit больше не голый 0 без вердикта)."""
    def _broken_fixture(layers):
        return (0, 0)
    monkeypatch.setattr(wd, "fixture_control", _broken_fixture)

    empty_src = tmp_path / "empty_src"
    empty_src.mkdir()
    code = wd.main([
        "--registry-file", str(wd.DEFAULT_REGISTRY),
        "--transcripts", str(empty_src),
        "--sidecar", str(tmp_path / "sidecar.jsonl"),
    ])
    assert code == 1


def test_f3_fixture_mismatch_defect_line_via_render_text(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "any.jsonl", [_tool_use_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    import dataclasses
    broken_rep = dataclasses.replace(rep, fixture_calls=0, fixture_lines=0)
    text = wd.render_text(broken_rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "ДЕФЕКТ ИНСТРУМЕНТА: фикстура 0/2 calls, 0/3 lines не сходится" in text


def test_f3_fixture_ok_no_defect_line(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "any.jsonl", [_tool_use_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    import dataclasses
    ok_rep = dataclasses.replace(
        rep, fixture_calls=wd.FIXTURE_EXPECTED_CALLS, fixture_lines=wd.FIXTURE_EXPECTED_LINES,
    )
    text = wd.render_text(ok_rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "ДЕФЕКТ ИНСТРУМЕНТА" not in text


def test_f3_fixture_one_off_boundary_is_still_defect(tmp_path):
    """Граница: calls на ЕДИНИЦУ меньше ожидаемого -- всё равно дефект
    (не только голый ноль голосует за поломку)."""
    layer = _layer()
    f = _write_lines(tmp_path / "any.jsonl", [_tool_use_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    import dataclasses
    off_by_one = dataclasses.replace(
        rep, fixture_calls=wd.FIXTURE_EXPECTED_CALLS - 1, fixture_lines=wd.FIXTURE_EXPECTED_LINES,
    )
    defects = wd.compute_run_defects(off_by_one)
    assert any("ДЕФЕКТ ИНСТРУМЕНТА" in d for d in defects)


def test_f4_duplicate_tool_use_id_line_and_counter(tmp_path):
    """Ф4: асимметрия дедупа названа строкой -- НЕ исправляется (число
    НЕ вычитается из знаменателя), но измеряется живьём и печатается."""
    layer = _layer(matcher="Agent")
    f = _write_lines(tmp_path / "dup_id.jsonl", [
        _tool_use_line(name="Agent", uuid="a1", ts="2026-01-01T00:00:00.100Z"),
        _tool_use_line(name="Agent", uuid="a2", ts="2026-01-01T00:00:00.200Z"),  # тот же item id "tuX"
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.duplicate_tool_use_id_count == 1
    assert rep.total_tool_use_in_window == 2  # НЕ вычитается
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "дедуп асимметричен" in text
    assert "дублей id в окне: 1 из 2" in text


# ---------------------------------------------------------------------------
# Узел B -- пер-слойные знаменатели (Б-К1..Б-К8, спека docs/tasks/
# 2026-08-25_warn-class-fix-dag.md)
# ---------------------------------------------------------------------------

# --- предикаты reachable (B-К6: барьеры импортируются из гейтов) --------

def test_pop_journal_path_matches_routing_log(tmp_path):
    assert wd._population_journal_path("Edit", {"file_path": "logs/routing-log.jsonl"}) is True
    assert wd._population_journal_path("Edit", {"file_path": "logs\\routing-log.jsonl"}) is True


def test_pop_journal_path_rejects_other_file(tmp_path):
    assert wd._population_journal_path("Edit", {"file_path": "tools/warn_density.py"}) is False
    assert wd._population_journal_path("Edit", {}) is False


def test_pop_journal_path_rejects_wrong_tool_name(tmp_path):
    # барьер сам не фильтрует по tool_name (journal_echo._extract_file_path
    # без доп. фильтра), но предикат здесь ограничен матчер-группой слоя --
    # Task/Agent никогда не несёт достижимой journal_path-популяции.
    assert wd._population_journal_path("Task", {"file_path": "logs/routing-log.jsonl"}) is False


def test_pop_subagent_type_builder_matches_builder():
    assert wd._population_subagent_type_builder("Task", {"subagent_type": "builder"}) is True
    assert wd._population_subagent_type_builder("Agent", {"subagent_type": "builder"}) is True


def test_pop_subagent_type_builder_rejects_other_roles():
    assert wd._population_subagent_type_builder("Task", {"subagent_type": "scout"}) is False
    assert wd._population_subagent_type_builder("Task", {}) is False
    assert wd._population_subagent_type_builder("Bash", {"subagent_type": "builder"}) is False


def test_pop_search_tool_or_pattern_grep_glob_always_true():
    assert wd._population_search_tool_or_pattern("Grep", {}) is True
    assert wd._population_search_tool_or_pattern("Glob", {"command": "irrelevant"}) is True


def test_pop_search_tool_or_pattern_bash_needs_search_token():
    assert wd._population_search_tool_or_pattern("Bash", {"command": "grep -r foo ."}) is True
    assert wd._population_search_tool_or_pattern("Bash", {"command": "git status --short"}) is False


def test_pop_search_tool_or_pattern_read_never_reachable():
    """Барьер (а) §1 класса: Read -- в matcher'е SEARCH_RETURNED_NOTHING,
    но НЕ член SEARCH_TOOLS и не несёт `command` -- никогда достижим."""
    assert wd._population_search_tool_or_pattern("Read", {}) is False
    assert wd._population_search_tool_or_pattern("Read", {"command": "grep foo"}) is False


# --- узел FRESHNESS (docs/tasks/2026-08-25_freshness-layer-spec.md, Ф5b):
# dispatch_prompt_freshness_token -- новый вид населённости, ИМПОРТ трёх
# регексов из dispatch_gate. -------------------------------------------

def test_pop_freshness_token_class_v_relative_anchor_true():
    assert wd._population_dispatch_prompt_freshness_token(
        "Task", {"prompt": "tools/dispatch_gate.py:9999999"}
    ) is True


def test_pop_freshness_token_class_v_absolute_anchor_true():
    assert wd._population_dispatch_prompt_freshness_token(
        "Agent", {"prompt": r"D:\repo\tools\x.py:100"}
    ) is True


def test_pop_freshness_token_class_a_check_token_true():
    assert wd._population_dispatch_prompt_freshness_token(
        "Task", {"prompt": "чек 13(б)"}
    ) is True


def test_pop_freshness_token_no_candidate_false():
    assert wd._population_dispatch_prompt_freshness_token(
        "Task", {"prompt": "ничего похожего тут нет"}
    ) is False


def test_pop_freshness_token_wrong_tool_name_false():
    assert wd._population_dispatch_prompt_freshness_token(
        "Bash", {"prompt": "tools/dispatch_gate.py:9999999"}
    ) is False


def test_pop_freshness_token_missing_or_nonstring_prompt_false():
    assert wd._population_dispatch_prompt_freshness_token("Task", {}) is False
    assert wd._population_dispatch_prompt_freshness_token("Task", {"prompt": None}) is False


def test_pop_freshness_token_is_superset_of_actual_warn_battery():
    """Ф5b -- ИНВАРИАНТ, не просто пример: предикат обязан быть
    НАДМНОЖЕСТВОМ фактического условия freshness_warn() (иначе ДЕФЕКТ
    ПРЕДИКАТА, calls > achievable, exit 1) -- батарея прогоняет и
    квотированные, и подавленные (owns/run-line), и молчащие случаи:
    ВЕЗДЕ, где freshness_warn() дал непустой варн, предикат обязан
    вернуть True; обратное (предикат True, варн "") -- ЛЕГАЛЬНО
    (предикат сознательно шире)."""
    import dispatch_gate as _dg

    repo_root = str(Path(__file__).resolve().parent.parent)
    prompts = [
        "tools/dispatch_gate.py:9999999",
        "чек 77(а)",
        "чек 13(я)",
        "чек 13(a)",
        "```\ntools/dispatch_gate.py:9999999\n```\n",  # квотировано -- варн пуст
        "Прогон: python tools/dispatch_gate.py:9999999 -q",  # подавлено -- варн пуст
        "tools/dispatch_gate.py:10",  # в пределах -- варн пуст
        "чек 13(б)",  # существует -- варн пуст
    ]
    for prompt in prompts:
        payload = {
            "tool_name": "Task",
            "tool_input": {"subagent_type": "builder", "prompt": prompt},
            "cwd": repo_root,
        }
        warn = _dg.freshness_warn(payload)
        achievable = wd._population_dispatch_prompt_freshness_token(
            "Task", {"prompt": prompt}
        )
        if warn:
            assert achievable is True, (prompt, warn)


# --- Ф6b: POPULATION_RULE_VERSION -- пин на новое значение узла --------

def test_population_rule_version_bumped_to_2():
    assert wd.POPULATION_RULE_VERSION == 2


# --- layer_population / доля (Б-К1..Б-К3) -- см. также test_bk1_/test_bk3_/
# test_edge_achievable_zero_matcher_positive_ выше (раздел "Лимиты") -------

def test_two_layers_same_matcher_different_population_different_denominators(tmp_path):
    """Адверсариальная батарея узла B: два слоя с ОДИНАКОВЫМ matcher, но
    РАЗНОЙ reachable-популяцией -- знаменатели (достижимо) РАЗНЫЕ. Прямая
    проверка, что фикс сделал то, ради чего затеян (докстринг узла B)."""
    layer_a = _layer(id="A", matcher="Agent", reachable="subagent_type_builder")
    layer_b = _layer(id="B", matcher="Agent", reachable="unmeasured")
    f = _write_lines(tmp_path / "two.jsonl", [
        _tool_use_line(name="Agent", uuid="t1", ts="2026-01-01T00:00:00.100Z",
                        input_={"subagent_type": "builder"}),
        _tool_use_line(name="Agent", uuid="t2", ts="2026-01-01T00:00:00.200Z",
                        input_={"subagent_type": "scout"}),
    ])
    rep = wd.process_corpus([f], [layer_a, layer_b], None, None, {}, compute_fixture=False)
    achievable_a, _, matcher_a = wd.layer_population(layer_a, rep)
    achievable_b, _, matcher_b = wd.layer_population(layer_b, rep)
    assert matcher_a == matcher_b == 2  # тот же матчер
    assert achievable_a == 1            # только один builder-вызов
    assert achievable_b is None         # unmeasured -- н-д, не число


# --- Б-К4: ДЕТЕКТОР МЕХАНИЗМА -- calls > достижимо, границы обеих сторон -

def test_bk4_calls_equal_achievable_is_not_a_defect(tmp_path):
    layer = _layer(matcher="Agent", reachable="subagent_type_builder")
    f = _write_lines(tmp_path / "eq.jsonl", [
        _hook_success_line(),  # даёт c.calls == 1
        _tool_use_line(name="Agent", input_={"subagent_type": "builder"}),  # достижимо == 1
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    defects = wd.compute_run_defects(rep)
    assert not any("ДЕФЕКТ ПРЕДИКАТА" in d for d in defects)


def test_bk4_calls_exceeds_achievable_by_one_is_defect(tmp_path):
    """Б-К4, ГЛАВНЫЙ детектор узла B: calls == достижимо+1 -- ДЕФЕКТ
    ПРЕДИКАТА (предикат населённости, ставший уже реальности)."""
    layer = _layer(matcher="Agent", reachable="subagent_type_builder")
    f = _write_lines(tmp_path / "exceed.jsonl", [
        _hook_success_line(uuid="u1", tool_use_id="tu1"),
        _hook_success_line(uuid="u2", tool_use_id="tu2", ts="2026-01-01T00:00:01.000Z"),
        # calls == 2, но НИ ОДНОГО builder-вызова -- достижимо == 0
    ])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert rep.counts["L1"].calls == 2
    achievable, _, _ = wd.layer_population(layer, rep)
    assert achievable == 0
    defects = wd.compute_run_defects(rep)
    assert any("ДЕФЕКТ ПРЕДИКАТА: L1: calls=2 > достижимо=0" in d for d in defects)


def test_bk4_main_returns_exit1_on_predicate_defect(tmp_path, capsys):
    """Сквозной прогон через main(): ДЕФЕКТ ПРЕДИКАТА -- exit 1, строка в
    выводе (не только внутренний compute_run_defects()). GIVEN_PATH-слой
    ОБЯЗАН быть в реестре -- иначе fixture_control() сам даёт (0, 0) и
    exit=1 по НЕСВЯЗАННОЙ причине (ДЕФЕКТ ИНСТРУМЕНТА), тест перестал бы
    различать свою и чужую причину провала."""
    reg = _reg_with_fixture_layer(matcher="Agent", reachable="subagent_type_builder")
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text GIVEN-PATH WARN: text"\n', encoding="utf-8")
    corpus_dir = tmp_path / "corpus"
    _write_lines(corpus_dir / "hit.jsonl", [_hook_success_line(additional_context="A WARN: x")])
    code = wd.main([
        "--registry-file", str(tmp_path / "reg.json"),
        "--transcripts", str(corpus_dir),
        "--sidecar", str(tmp_path / "sidecar.jsonl"),
    ])
    out = capsys.readouterr().out
    assert code == 1
    assert "ДЕФЕКТ ПРЕДИКАТА: A: calls=1 > достижимо=0" in out


# --- реестр: валидация 'reachable'/'reason' (Б-К8, "тем же способом, что
# validate_layers для carrier/literal") -----------------------------------

def test_registry_reachable_absent_is_not_a_defect_and_defaults_unmeasured():
    a = _raw_layer(id="A")
    a.pop("reachable", None)
    layers, defects = wd.validate_layers([a])
    assert defects == []
    assert len(layers) == 1
    assert layers[0].reachable == "unmeasured"
    assert layers[0].reachable_reason == "reachable не объявлен в реестре"


def test_registry_reachable_known_kind_no_reason_needed():
    a = _raw_layer(id="A", reachable="journal_path")
    layers, defects = wd.validate_layers([a])
    assert defects == []
    assert layers[0].reachable == "journal_path"
    assert layers[0].reachable_reason is None


def test_registry_reachable_unmeasured_requires_reason():
    a = _raw_layer(id="A", reachable="unmeasured")  # 'reason' отсутствует
    layers, defects = wd.validate_layers([a])
    assert any("reachable=unmeasured требует непустой 'reason'" in d for d in defects)
    assert layers == []


def test_registry_reachable_unmeasured_with_reason_ok():
    a = _raw_layer(id="A", reachable="unmeasured", reason="тестовая причина")
    layers, defects = wd.validate_layers([a])
    assert defects == []
    assert layers[0].reachable_reason == "тестовая причина"


@pytest.mark.parametrize("bad_value", [
    "{template}",   # `{`-шаблон
    "",             # пустая строка
    0,              # число
    {"kind": "x"},  # вложенный объект
    ["journal_path"],  # список
])
def test_registry_reachable_malformed_is_defect_not_traceback(bad_value):
    """Адверсариальная батарея узла B: поле с {-шаблоном / пустой строкой
    / числом / вложенным объектом -- ДЕФЕКТ ФОРМЫ, не трейсбек."""
    a = _raw_layer(id="A", reachable=bad_value)
    layers, defects = wd.validate_layers([a])
    assert layers == []
    assert any("reachable" in d for d in defects)


def test_registry_reachable_unknown_kind_is_defect():
    a = _raw_layer(id="A", reachable="totally-unknown-kind")
    layers, defects = wd.validate_layers([a])
    assert layers == []
    assert any("неизвестного вида" in d for d in defects)


def test_registry_reachable_unknown_kind_check_exit1(tmp_path):
    reg = {"registry_version": 2, "layers": [_raw_layer(
        id="A", carrier=["c.py"], literal="A WARN:", reachable="bogus-kind",
    )]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text"\n', encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 1
    assert "неизвестного вида" in text


def test_registry_version_1_no_reachable_field_all_unmeasured_exit0(tmp_path):
    """Край спеки узла B: версия 1 (поле reachable нигде не объявлено) --
    читается, ВСЕ слои н-д, exit 0 (НЕ дефект -- обратная совместимость)."""
    reg = {"registry_version": 1, "layers": [_raw_layer(id="A", carrier=["c.py"], literal="A WARN:")]}
    (tmp_path / "reg.json").write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text"\n', encoding="utf-8")
    text, code = wd.run_check(tmp_path / "reg.json", tmp_path)
    assert code == 0
    assert "дефектов нет" in text
    _, raw_layers, _ = wd.read_registry_raw(tmp_path / "reg.json")
    layers, defects = wd.validate_layers(raw_layers)
    assert defects == []
    assert layers[0].reachable == "unmeasured"


# --- сайдкар: population_rule_version (Б-К7 / Р3(в)) ----------------------

def test_sidecar_entry_carries_population_rule_version(tmp_path):
    layer = _layer()
    f = _write_lines(tmp_path / "any.jsonl", [_tool_use_line()])
    rep = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    entry = wd.build_sidecar_entry(rep, "deadbeef")
    assert entry["population_rule_version"] == wd.POPULATION_RULE_VERSION


def _reg_with_fixture_layer(**extra_a_kw):
    """Реестр с ДВУМЯ слоями -- кастомным 'A' и обязательным GIVEN_PATH
    (иначе fixture_control() вернёт (0, 0) -- 'A' не совпадает с
    _FIXTURE_LAYER_ID -- и main() упадёт в ДЕФЕКТ ИНСТРУМЕНТА/exit 1 по
    ПРИЧИНЕ, не связанной с тестом; см. warn_density.fixture_control)."""
    a = _raw_layer(id="A", carrier=["c.py"], literal="A WARN:", **extra_a_kw)
    given = _raw_layer(id="GIVEN_PATH", carrier=["c.py"], literal="GIVEN-PATH WARN:")
    return {"registry_version": 2, "layers": [a, given]}


def test_main_warns_base_from_before_population_rule(tmp_path, capsys):
    """Р3(в): render_text печатает предупреждение при чтении сайдкар-базы,
    записанной ДО пер-слойного знаменателя -- даже если registry_sha
    ВЫДУМАННО совпал бы (population_rule_version отсутствует)."""
    reg = _reg_with_fixture_layer(reachable="subagent_type_builder")
    reg_path = tmp_path / "reg.json"
    reg_path.write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text GIVEN-PATH WARN: text"\n', encoding="utf-8")
    raw_bytes = reg_path.read_bytes()
    reg_hash = wd.registry_sha(raw_bytes)
    sidecar_path = tmp_path / "sidecar.jsonl"
    # старая запись -- registry_sha ТОТ ЖЕ (совпадение), но БЕЗ
    # population_rule_version (записана ДО этого узла).
    sidecar_path.write_text(json.dumps({"registry_sha": reg_hash, "ts": "x"}) + "\n", encoding="utf-8")
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    code = wd.main([
        "--registry-file", str(reg_path), "--transcripts", str(corpus_dir),
        "--sidecar", str(sidecar_path),
    ])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "БАЗА ДО ПЕР-СЛОЙНОГО ЗНАМЕНАТЕЛЯ" in out


def test_no_sidecar_flag_skips_read_and_write(tmp_path, capsys):
    """Р-В1: --no-sidecar -- ни читает, ни пишет сайдкар."""
    reg = _reg_with_fixture_layer(reachable="subagent_type_builder")
    reg_path = tmp_path / "reg.json"
    reg_path.write_text(json.dumps(reg), encoding="utf-8")
    (tmp_path / "c.py").write_text('X = "A WARN: text GIVEN-PATH WARN: text"\n', encoding="utf-8")
    sidecar_path = tmp_path / "sidecar.jsonl"
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    code = wd.main([
        "--registry-file", str(reg_path), "--transcripts", str(corpus_dir),
        "--sidecar", str(sidecar_path), "--no-sidecar",
    ])
    out = capsys.readouterr().out
    assert code == 0, out
    assert not sidecar_path.exists()
    assert "СВЕРКА ПРОПУЩЕНА (--no-sidecar)" in out


# --- layer_is_proxy: тег текста называет "матчер" (конфликтная пара 4) ---

def test_render_text_proxy_tag_says_matcher_not_bare_proxy(tmp_path):
    settings = {
        "hooks": {"PreToolUse": [
            {"matcher": "Task|Agent", "hooks": [{"type": "command", "command": "a"},
                                                  {"type": "command", "command": "b"}]},
        ]}
    }
    p = tmp_path / "settings.json"
    p.write_text(json.dumps(settings), encoding="utf-8")
    pm = wd.load_hook_multiplicity(p)
    layer = _layer(hook_event="PreToolUse", matcher="Task|Agent")
    f = _write_lines(tmp_path / "any.jsonl", [_tool_use_line(name="Agent")])
    rep = wd.process_corpus([f], [layer], None, None, pm, compute_fixture=False)
    text = wd.render_text(rep, tmp_path, None, "БАЗЫ НЕТ", None, source_empty=False)
    assert "матчер-proxy" in text
    assert " proxy " not in text and not text.rstrip().endswith(" proxy")


# ---------------------------------------------------------------------------
# Хелперы уровня модуля
# ---------------------------------------------------------------------------

def _fixture_tmp():
    import tempfile
    return Path(tempfile.mkdtemp(prefix="warn_density_test_"))


def _real_registry_layers():
    _, raw_layers, _ = wd.read_registry_raw(wd.DEFAULT_REGISTRY)
    layers, defects = wd.validate_layers(raw_layers)
    assert defects == []
    return layers
