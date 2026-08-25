"""Tests for tools/warn_density.py -- kit port.

Structure: registry validation (required fields, duplicate id, the "{"
adversarial battery, literal overlap, reachable/reason rules), the
structural hook_success/hook_additional_context definition (including a
RED CONTROL that a layer name inside a message body/toolUseResult must
NOT count), sidechain exclusion, dedup, orphan hac, window boundaries,
population predicates, compute_run_defects (including the calls>
achievable boundary), --check (registry + negative form), and CLI
--no-sidecar. Synthetic corpora live in tmp_path -- live repo artifacts
(warn_layers.json, real transcripts) are not mutated; a few tests read
the REAL tools/warn_layers.json read-only for an integration check
against the tree.
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
# Helpers
# ---------------------------------------------------------------------------

def _layer(
    id="L1", name="L1", carrier=None, symbol=None, literal="LIT WARN:",
    aliases=None, hook_event="PreToolUse", matcher="Task|Agent",
    denominator="Z1", listed=True,
    reachable="unmeasured", reachable_reason="reachable is not declared in the registry",
) -> wd.LayerDef:
    return wd.LayerDef(
        id=id, name=name, carrier=carrier or ["some/file.py"], symbol=symbol,
        literal=literal, aliases=aliases or [], hook_event=hook_event,
        matcher=matcher, denominator=denominator,
        listed_in_density_check=listed, reachable=reachable,
        reachable_reason=reachable_reason,
    )


def _raw_layer(**overrides):
    base = {
        "id": "L1", "name": "L1", "carrier": ["some/file.py"], "symbol": None,
        "literal": "LIT WARN:", "aliases": [], "hook_event": "PreToolUse",
        "matcher": "Task|Agent", "denominator": "Z1",
        "listed_in_density_check": True,
    }
    base.update(overrides)
    return base


def _hook_success_line(uuid, ts, tool_use_id, hook_name, context):
    return json.dumps({
        "uuid": uuid,
        "timestamp": ts,
        "attachment": {
            "type": "hook_success",
            "hookName": hook_name,
            "toolUseID": tool_use_id,
            "stdout": json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": context,
                }
            }),
        },
    })


def _tool_use_line(uuid, ts, tool_id, name, tool_input=None):
    return json.dumps({
        "uuid": uuid,
        "timestamp": ts,
        "type": "assistant",
        "message": {"content": [{
            "type": "tool_use", "id": tool_id, "name": name,
            "input": tool_input or {},
        }]},
    })


# ---------------------------------------------------------------------------
# Registry: required fields / duplicate id / "{" battery / overlap
# ---------------------------------------------------------------------------

def test_validate_layers_all_required_fields_present_ok():
    layers, defects = wd.validate_layers([_raw_layer()])
    assert defects == []
    assert len(layers) == 1
    assert layers[0].id == "L1"


@pytest.mark.parametrize("field", wd.REQUIRED_LAYER_FIELDS)
def test_validate_layers_missing_required_field_is_defect(field):
    raw = _raw_layer()
    del raw[field]
    layers, defects = wd.validate_layers([raw])
    assert layers == []
    assert any(field in d for d in defects)


def test_validate_layers_duplicate_id_is_defect():
    layers, defects = wd.validate_layers([_raw_layer(), _raw_layer()])
    assert layers == []
    assert any("duplicate id" in d for d in defects)


def test_validate_layers_brace_in_literal_is_defect():
    layers, defects = wd.validate_layers([_raw_layer(literal="LIT {n} WARN:")])
    assert layers == []
    assert any("'{'" in d for d in defects)


def test_validate_layers_brace_in_alias_is_defect():
    layers, defects = wd.validate_layers([_raw_layer(aliases=["ALIAS {n}"])])
    assert layers == []
    assert any("'{'" in d for d in defects)


def test_validate_layers_literal_without_brace_ok():
    # Boundary counterpart of the "{" battery: no brace at all -- must
    # NOT be flagged.
    layers, defects = wd.validate_layers([_raw_layer(literal="plain literal, no braces")])
    assert defects == []
    assert len(layers) == 1


def test_validate_layers_literal_overlap_is_defect():
    raw_a = _raw_layer(id="A", literal="FOO WARN:")
    raw_b = _raw_layer(id="B", literal="FOO WARN: extra")
    layers, defects = wd.validate_layers([raw_a, raw_b])
    assert any("literal overlap" in d for d in defects)


def test_validate_layers_one_bad_record_does_not_abort_others():
    good = _raw_layer(id="GOOD")
    bad = _raw_layer(id="BAD", literal="")
    layers, defects = wd.validate_layers([bad, good])
    ids = {l.id for l in layers}
    assert ids == {"GOOD"}
    assert defects  # bad record reported


# ---------------------------------------------------------------------------
# Registry: reachable / reason
# ---------------------------------------------------------------------------

def test_validate_layers_no_reachable_field_defaults_unmeasured():
    layers, defects = wd.validate_layers([_raw_layer()])
    assert defects == []
    assert layers[0].reachable == "unmeasured"
    assert layers[0].reachable_reason


def test_validate_layers_reachable_unmeasured_requires_reason():
    layers, defects = wd.validate_layers([_raw_layer(reachable="unmeasured")])
    assert layers == []
    assert any("requires a non-empty 'reason'" in d for d in defects)


def test_validate_layers_reachable_unmeasured_with_reason_ok():
    layers, defects = wd.validate_layers([_raw_layer(reachable="unmeasured", reason="why")])
    assert defects == []
    assert layers[0].reachable_reason == "why"


def test_validate_layers_reachable_measured_kind_ok_no_reason_needed():
    layers, defects = wd.validate_layers([_raw_layer(reachable="journal_path")])
    assert defects == []
    assert layers[0].reachable == "journal_path"
    assert layers[0].reachable_reason is None


def test_validate_layers_reachable_unknown_kind_is_defect():
    layers, defects = wd.validate_layers([_raw_layer(reachable="made_up_kind", reason="x")])
    assert layers == []
    assert any("unknown kind" in d for d in defects)


def test_validate_layers_reachable_brace_template_is_defect():
    layers, defects = wd.validate_layers([_raw_layer(reachable="{n}")])
    assert layers == []
    assert any("syntactically bad" in d for d in defects)


# ---------------------------------------------------------------------------
# read_registry_raw
# ---------------------------------------------------------------------------

def test_read_registry_raw_missing_file(tmp_path):
    with pytest.raises(wd.RegistryError):
        wd.read_registry_raw(tmp_path / "nope.json")


def test_read_registry_raw_not_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not json {", encoding="utf-8")
    with pytest.raises(wd.RegistryError):
        wd.read_registry_raw(p)


def test_read_registry_raw_top_level_not_object(tmp_path):
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(wd.RegistryError):
        wd.read_registry_raw(p)


def test_read_registry_raw_layers_field_missing(tmp_path):
    p = tmp_path / "nolayers.json"
    p.write_text(json.dumps({"registry_version": 1}), encoding="utf-8")
    with pytest.raises(wd.RegistryError):
        wd.read_registry_raw(p)


def test_read_registry_raw_ok(tmp_path):
    p = tmp_path / "ok.json"
    p.write_text(json.dumps({"registry_version": 1, "layers": [_raw_layer()]}), encoding="utf-8")
    version, layers, raw = wd.read_registry_raw(p)
    assert version == 1
    assert len(layers) == 1
    assert raw


# ---------------------------------------------------------------------------
# check_liveness / check_symbol_binding -- against the REAL kit tree
# ---------------------------------------------------------------------------

def test_check_liveness_real_registry_all_layers_alive():
    _, raw_layers, _ = wd.read_registry_raw(wd.DEFAULT_REGISTRY)
    layers, defects = wd.validate_layers(raw_layers)
    assert defects == [], f"real kit registry has form defects: {defects}"
    for layer in layers:
        alive, reason = wd.check_liveness(layer, REPO_ROOT)
        assert alive, f"{layer.id} not alive: {reason}"


def test_check_symbol_binding_real_registry_no_defects():
    _, raw_layers, _ = wd.read_registry_raw(wd.DEFAULT_REGISTRY)
    layers, _ = wd.validate_layers(raw_layers)
    for layer in layers:
        assert wd.check_symbol_binding(layer, REPO_ROOT) is None


def test_check_liveness_literal_not_in_carrier_is_dead(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text("print('hello')\n", encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], literal="NEVER THERE:")
    alive, reason = wd.check_liveness(layer, tmp_path)
    assert alive is False


def test_check_liveness_concat_seam_flattening(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text(
        'MSG = (\n    "part one "\n    "part two"\n)\n', encoding="utf-8",
    )
    layer = _layer(carrier=["carrier.py"], literal="part one part two")
    alive, reason = wd.check_liveness(layer, tmp_path)
    assert alive is True


def test_check_symbol_binding_missing_symbol_is_defect(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text("X = 1\n", encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], symbol="NOT_PRESENT")
    defect = wd.check_symbol_binding(layer, tmp_path)
    assert defect is not None
    assert "NOT_PRESENT" in defect


def test_check_symbol_binding_none_symbol_is_not_applicable(tmp_path):
    carrier = tmp_path / "carrier.py"
    carrier.write_text("X = 1\n", encoding="utf-8")
    layer = _layer(carrier=["carrier.py"], symbol=None)
    assert wd.check_symbol_binding(layer, tmp_path) is None


# ---------------------------------------------------------------------------
# Structural definition + RED CONTROL (process_corpus)
# ---------------------------------------------------------------------------

def test_process_corpus_counts_hook_success_only(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    lines = [
        _hook_success_line("u1", "2026-01-01T00:00:01.000Z", "tool-1", "PreToolUse:Agent", "MY WARN: x"),
        # RED CONTROL: layer name inside an assistant text body -- must
        # not count.
        json.dumps({
            "uuid": "u2", "timestamp": "2026-01-01T00:00:02.000Z", "type": "assistant",
            "message": {"content": [{"type": "text", "text": "see MY WARN: above"}]},
        }),
        # RED CONTROL: layer name inside a tool_result body -- must not
        # count.
        json.dumps({
            "uuid": "u3", "timestamp": "2026-01-01T00:00:03.000Z", "type": "user",
            "message": {"content": [{"type": "tool_result", "content": "grep: MY WARN: hit"}]},
        }),
    ]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.counts["L1"].calls == 1
    assert report.counts["L1"].lines == 1


def test_process_corpus_dedup_same_unit_hook(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    line = _hook_success_line("u1", "2026-01-01T00:00:01.000Z", "tool-1", "PreToolUse:Agent", "MY WARN: x")
    f.write_text(line + "\n" + line + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.counts["L1"].calls == 1
    assert report.dedup_dropped == 1


def test_process_corpus_sidechain_files_excluded_from_denominator(tmp_path):
    session_dir = tmp_path / "session1"
    session_dir.mkdir()
    subagents_dir = session_dir / "subagents"
    subagents_dir.mkdir()
    side_file = subagents_dir / "sub.jsonl"
    side_file.write_text(
        _tool_use_line("u1", "2026-01-01T00:00:01.000Z", "t1", "Bash") + "\n",
        encoding="utf-8",
    )
    assert wd.is_sidechain_file(side_file) is True
    layer = _layer(id="L1", literal="MY WARN:")
    report = wd.process_corpus([side_file], [layer], None, None, {}, compute_fixture=False)
    assert report.total_tool_use_in_window == 0
    assert report.sidechain_tool_use_in_window == 1


def test_process_corpus_orphan_hac_counted_once(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    hac = json.dumps({
        "uuid": "u1", "timestamp": "2026-01-01T00:00:01.000Z",
        "attachment": {
            "type": "hook_additional_context", "hookName": "PreToolUse:Agent",
            "toolUseID": "tool-1", "content": "MY WARN: only trace",
        },
    })
    f.write_text(hac + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.counts["L1"].calls == 1
    assert report.orphan_hac_count == 1


def test_process_corpus_hac_with_success_pair_ignored(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    success = _hook_success_line("u1", "2026-01-01T00:00:01.000Z", "tool-1", "PreToolUse:Agent", "MY WARN: x")
    hac = json.dumps({
        "uuid": "u2", "timestamp": "2026-01-01T00:00:02.000Z",
        "attachment": {
            "type": "hook_additional_context", "hookName": "PreToolUse:Agent",
            "toolUseID": "tool-1", "content": "MY WARN: second trace",
        },
    })
    f.write_text(success + "\n" + hac + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.counts["L1"].calls == 1
    assert report.orphan_hac_count == 0


def test_process_corpus_raw_fallback_on_broken_stdout_json(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    rec = {
        "uuid": "u1", "timestamp": "2026-01-01T00:00:01.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent",
            "toolUseID": "tool-1",
            "stdout": '{"hookSpecificOutput": {"additionalContext": "MY WARN: truncat',  # broken JSON
        },
    }
    f.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.raw_parse_failed == 1
    assert report.counts["L1"].raw_calls == 1
    assert report.counts["L1"].calls == 0


def test_process_corpus_broken_json_line_counted(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    f.write_text("{not json at all\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.broken_lines == 1
    assert report.total_lines_seen == 1


def test_process_corpus_no_timestamp_line_excluded(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    rec = {"uuid": "u1", "type": "assistant", "message": {"content": []}}
    f.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.no_timestamp == 1
    assert report.in_window_records == 0


def test_process_corpus_fallback_key_when_no_tool_use_id_and_no_uuid(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    rec = {
        "timestamp": "2026-01-01T00:00:01.000Z",
        "attachment": {
            "type": "hook_success", "hookName": "PreToolUse:Agent",
            "stdout": json.dumps({"hookSpecificOutput": {"additionalContext": "MY WARN: x"}}),
        },
    }
    f.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    assert report.fallback_key_count == 1
    assert report.counts["L1"].calls == 1


# ---------------------------------------------------------------------------
# Window boundaries (half-open interval [start, end))
# ---------------------------------------------------------------------------

def test_parse_window_bound_valid_iso():
    dt = wd.parse_window_bound("2026-01-01T00:00:00")
    assert dt is not None


def test_parse_window_bound_none_returns_none():
    assert wd.parse_window_bound(None) is None


def test_parse_window_bound_invalid_iso_raises():
    with pytest.raises(wd.ArgError):
        wd.parse_window_bound("not-a-date")


def test_main_rejects_start_ge_end(tmp_path, capsys):
    registry = tmp_path / "reg.json"
    registry.write_text(json.dumps({"registry_version": 1, "layers": [_raw_layer(literal="X WARN:")]}), encoding="utf-8")
    empty_transcripts = tmp_path / "transcripts"
    empty_transcripts.mkdir()
    code = wd.main([
        "--registry-file", str(registry), "--transcripts", str(empty_transcripts),
        "--window-start", "2026-01-01T00:00:00", "--window-end", "2026-01-01T00:00:00",
        "--no-sidecar",
    ])
    assert code == 2


def test_window_half_open_boundary_included_and_excluded(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:")
    f = tmp_path / "t.jsonl"
    at_start = _hook_success_line("u1", "2026-01-01T00:00:00.000Z", "t1", "PreToolUse:Agent", "MY WARN: a")
    at_end = _hook_success_line("u2", "2026-01-01T00:00:10.000Z", "t2", "PreToolUse:Agent", "MY WARN: b")
    f.write_text(at_start + "\n" + at_end + "\n", encoding="utf-8")
    start = wd.parse_transcript_ts("2026-01-01T00:00:00.000Z")
    end = wd.parse_transcript_ts("2026-01-01T00:00:10.000Z")
    report = wd.process_corpus([f], [layer], start, end, {}, compute_fixture=False)
    # ts == start is included, ts == end is excluded.
    assert report.counts["L1"].calls == 1


# ---------------------------------------------------------------------------
# Population predicates
# ---------------------------------------------------------------------------

def test_population_journal_path_true_for_journal_edit():
    assert wd._population_journal_path("Edit", {"file_path": "logs/routing-log.jsonl"}) is True


def test_population_journal_path_false_for_other_file():
    assert wd._population_journal_path("Edit", {"file_path": "tools/other.py"}) is False


def test_population_journal_path_false_for_non_journal_tool():
    assert wd._population_journal_path("Read", {"file_path": "logs/routing-log.jsonl"}) is False


def test_population_search_tool_or_pattern_true_for_grep():
    assert wd._population_search_tool_or_pattern("Grep", {"pattern": "x"}) is True


def test_population_search_tool_or_pattern_true_for_bash_grep_command():
    assert wd._population_search_tool_or_pattern("Bash", {"command": "grep -n foo file.py"}) is True


def test_population_search_tool_or_pattern_false_for_bash_non_search_command():
    assert wd._population_search_tool_or_pattern("Bash", {"command": "git status --short"}) is False


def test_population_search_tool_or_pattern_false_for_read():
    assert wd._population_search_tool_or_pattern("Read", {"file_path": "a.py"}) is False


# ---------------------------------------------------------------------------
# layer_population / compute_run_defects -- including the calls>achievable
# boundary
# ---------------------------------------------------------------------------

def test_layer_population_unmeasured_returns_none_none():
    layer = _layer(reachable="unmeasured", reachable_reason="x", matcher="Bash")
    report = wd.process_corpus([], [layer], None, None, {}, compute_fixture=False)
    achievable, unreachable, matcher_total = wd.layer_population(layer, report)
    assert achievable is None
    assert unreachable is None


def test_compute_run_defects_calls_equals_achievable_no_defect(tmp_path):
    layer = _layer(id="L1", literal="MY WARN:", matcher="Edit", reachable="journal_path")
    f = tmp_path / "t.jsonl"
    tool_use = _tool_use_line("u0", "2026-01-01T00:00:00.000Z", "tool-1", "Edit", {"file_path": "logs/routing-log.jsonl"})
    hook = _hook_success_line("u1", "2026-01-01T00:00:01.000Z", "tool-1", "PostToolUse", "MY WARN: x")
    f.write_text(tool_use + "\n" + hook + "\n", encoding="utf-8")
    report = wd.process_corpus([f], [layer], None, None, {}, compute_fixture=False)
    achievable, _, _ = wd.layer_population(layer, report)
    assert achievable == 1
    assert report.counts["L1"].calls == 1
    defects = [d for d in wd.compute_run_defects(report) if "PREDICATE DEFECT" in d]
    assert defects == []


def test_compute_run_defects_calls_exceeds_achievable_is_defect(tmp_path):
    # calls > achievable: two DIFFERENT firings on the SAME single
    # achievable tool_use -- constructed by two distinct tool_use ids
    # sharing one hook success unit is not realistic, so instead assert
    # the boundary directly via a synthetic Report.
    layer = _layer(id="L1", literal="MY WARN:", matcher="Edit", reachable="journal_path")
    report = wd.Report(
        layers=[layer], counts={"L1": wd.LayerCounts(calls=2, lines=2)},
        tool_use_counts={"Edit": 1}, total_tool_use_in_window=1, dedup_dropped=0,
        total_hook_success=2, total_hook_additional_context=0, silent_hook_success=0,
        raw_parse_failed=0, no_timestamp=0, fallback_key_count=0,
        transcripts_dir=Path("."), total_lines_seen=2, broken_lines=0, files_read=1,
        total_bytes=0, in_window_records=2, window_start=None, window_end=None,
        proxy_map={}, fixture_calls=wd.FIXTURE_EXPECTED_CALLS, fixture_lines=wd.FIXTURE_EXPECTED_LINES,
        sidechain_tool_use_in_window=0, orphan_hac_count=0, duplicate_tool_use_id_count=0,
        population_achievable_counts={"journal_path": 1, "search_tool_or_pattern": 0},
    )
    defects = wd.compute_run_defects(report)
    assert any("PREDICATE DEFECT: L1" in d for d in defects)


def test_compute_run_defects_fixture_mismatch_is_defect():
    layer = _layer(id="GIVEN_PATH", literal="GIVEN-PATH WARN:")
    report = wd.Report(
        layers=[layer], counts={"GIVEN_PATH": wd.LayerCounts()},
        tool_use_counts={}, total_tool_use_in_window=0, dedup_dropped=0,
        total_hook_success=0, total_hook_additional_context=0, silent_hook_success=0,
        raw_parse_failed=0, no_timestamp=0, fallback_key_count=0,
        transcripts_dir=Path("."), total_lines_seen=0, broken_lines=0, files_read=0,
        total_bytes=0, in_window_records=0, window_start=None, window_end=None,
        proxy_map={}, fixture_calls=0, fixture_lines=0,
        sidechain_tool_use_in_window=0, orphan_hac_count=0, duplicate_tool_use_id_count=0,
        population_achievable_counts={"journal_path": 0, "search_tool_or_pattern": 0},
    )
    defects = wd.compute_run_defects(report)
    assert any("TOOL DEFECT" in d for d in defects)


def test_compute_run_defects_all_lines_broken_is_defect():
    layer = _layer(id="L1")
    report = wd.Report(
        layers=[layer], counts={"L1": wd.LayerCounts()},
        tool_use_counts={}, total_tool_use_in_window=0, dedup_dropped=0,
        total_hook_success=0, total_hook_additional_context=0, silent_hook_success=0,
        raw_parse_failed=0, no_timestamp=0, fallback_key_count=0,
        transcripts_dir=Path("."), total_lines_seen=5, broken_lines=5, files_read=1,
        total_bytes=0, in_window_records=0, window_start=None, window_end=None,
        proxy_map={}, fixture_calls=wd.FIXTURE_EXPECTED_CALLS, fixture_lines=wd.FIXTURE_EXPECTED_LINES,
        sidechain_tool_use_in_window=0, orphan_hac_count=0, duplicate_tool_use_id_count=0,
        population_achievable_counts={"journal_path": 0, "search_tool_or_pattern": 0},
    )
    defects = wd.compute_run_defects(report)
    assert any("SOURCE DEFECT" in d for d in defects)


# ---------------------------------------------------------------------------
# Built-in fixture control (must be able to fail -- DoD red control)
# ---------------------------------------------------------------------------

def test_fixture_control_matches_expected_on_real_given_path_layer():
    layer = _layer(id="GIVEN_PATH", literal="GIVEN-PATH WARN:")
    calls, lines = wd.fixture_control([layer])
    assert calls == wd.FIXTURE_EXPECTED_CALLS
    assert lines == wd.FIXTURE_EXPECTED_LINES


def test_fixture_control_empty_when_no_fixture_layer():
    layer = _layer(id="SOMETHING_ELSE", literal="OTHER WARN:")
    calls, lines = wd.fixture_control([layer])
    assert (calls, lines) == (0, 0)


# ---------------------------------------------------------------------------
# --check (registry + negative control)
# ---------------------------------------------------------------------------

def test_run_check_real_kit_registry_is_green():
    text, code = wd.run_check(wd.DEFAULT_REGISTRY, REPO_ROOT, None)
    assert code == 0, text
    assert "(no defects)" in text


def test_run_check_negative_control_missing_field_is_red(tmp_path):
    # Negative control (D-0054/rule 6a): a deliberately absent required
    # field must turn --check red.
    bad_registry = tmp_path / "bad.json"
    raw = _raw_layer()
    del raw["carrier"]
    bad_registry.write_text(json.dumps({"registry_version": 1, "layers": [raw]}), encoding="utf-8")
    text, code = wd.run_check(bad_registry, REPO_ROOT, None)
    assert code == 1
    assert "carrier" in text


def test_run_check_dead_literal_is_red(tmp_path):
    bad_registry = tmp_path / "bad2.json"
    raw = _raw_layer(carrier=["tools/dispatch_gate.py"], literal="THIS LITERAL DOES NOT EXIST ANYWHERE:")
    bad_registry.write_text(json.dumps({"registry_version": 1, "layers": [raw]}), encoding="utf-8")
    text, code = wd.run_check(bad_registry, REPO_ROOT, None)
    assert code == 1
    assert "REGISTRY DEFECT" in text


def test_run_check_missing_registry_file_exit_2(tmp_path):
    text, code = wd.run_check(tmp_path / "nope.json", REPO_ROOT, None)
    assert code == 2


# ---------------------------------------------------------------------------
# CLI: main() end to end, --no-sidecar does not grow the sidecar
# ---------------------------------------------------------------------------

def test_main_no_sidecar_does_not_write_sidecar(tmp_path):
    sidecar = tmp_path / "sidecar.jsonl"
    assert not sidecar.exists()
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    f = transcripts / "session.jsonl"
    f.write_text(_hook_success_line("u1", "2026-01-01T00:00:01.000Z", "t1", "PreToolUse:Agent", "GIVEN-PATH WARN: x") + "\n", encoding="utf-8")
    code = wd.main([
        "--registry-file", str(wd.DEFAULT_REGISTRY),
        "--transcripts", str(transcripts),
        "--sidecar", str(sidecar),
        "--settings", str(REPO_ROOT / ".claude" / "settings.json"),
        "--no-sidecar",
    ])
    assert code == 0
    assert not sidecar.exists()


def test_main_writes_sidecar_when_not_suppressed(tmp_path):
    sidecar = tmp_path / "sidecar.jsonl"
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    code = wd.main([
        "--registry-file", str(wd.DEFAULT_REGISTRY),
        "--transcripts", str(transcripts),
        "--sidecar", str(sidecar),
        "--settings", str(REPO_ROOT / ".claude" / "settings.json"),
    ])
    assert code == 0
    assert sidecar.exists()
    entry = json.loads(sidecar.read_text(encoding="utf-8").splitlines()[0])
    assert entry["population_rule_version"] == wd.POPULATION_RULE_VERSION
    assert "registry_sha" in entry


def test_main_source_not_a_directory_exit_2(tmp_path):
    code = wd.main([
        "--registry-file", str(wd.DEFAULT_REGISTRY),
        "--transcripts", str(tmp_path / "does-not-exist"),
        "--no-sidecar",
    ])
    assert code == 2


def test_main_json_output_is_parseable(tmp_path, capsys):
    transcripts = tmp_path / "transcripts"
    transcripts.mkdir()
    code = wd.main([
        "--registry-file", str(wd.DEFAULT_REGISTRY),
        "--transcripts", str(transcripts),
        "--no-sidecar", "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert "layers" in payload
    assert "defects" in payload


# ---------------------------------------------------------------------------
# proxy detection from .claude/settings.json (real kit tree)
# ---------------------------------------------------------------------------

def test_load_hook_multiplicity_real_settings_pretooluse_task_agent_shared():
    m = wd.load_hook_multiplicity(REPO_ROOT / ".claude" / "settings.json")
    # PreToolUse Task|Agent carries dispatch_gate + critic_snapshot +
    # owns_gate -- three command hooks, so this matcher is shared.
    assert m.get(("PreToolUse", "Task|Agent"), 0) >= 2


def test_layer_is_proxy_true_when_matcher_shared():
    layer = _layer(hook_event="PreToolUse", matcher="Task|Agent")
    assert wd.layer_is_proxy(layer, {("PreToolUse", "Task|Agent"): 3}) is True


def test_layer_is_proxy_false_when_matcher_exclusive():
    layer = _layer(hook_event="PreToolUse", matcher="Edit|Write")
    assert wd.layer_is_proxy(layer, {("PreToolUse", "Edit|Write"): 1}) is False


# ---------------------------------------------------------------------------
# Integration: the real kit registry has no listed_in_density_check
# layer left uncovered by the calibration protocol's block (or, if the
# block isn't found, that is reported honestly rather than silently
# skipped).
# ---------------------------------------------------------------------------

def test_density_check_reconciliation_against_real_protocol():
    protocol_path = REPO_ROOT / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md"
    assert protocol_path.exists()
    check_names = wd.parse_density_check_names(protocol_path.read_text(encoding="utf-8"))
    assert check_names is not None, "WARN LAYER DENSITY block not recognized in the protocol"
    _, raw_layers, _ = wd.read_registry_raw(wd.DEFAULT_REGISTRY)
    layers, _ = wd.validate_layers(raw_layers)
    in_check_not_reg, in_reg_not_check = wd.diff_density_check(layers, check_names)
    assert in_check_not_reg == []
    assert in_reg_not_check == []
