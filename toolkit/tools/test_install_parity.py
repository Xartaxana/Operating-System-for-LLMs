"""Tests for install_parity.py.

K3 (mandatory half of the mechanism, "anti-staleness"): two tests that
would fail the moment the SHIPPED manifest (install_parity_anchors.json)
drifts from the kit content it describes -- see
test_manifest_anchors_match_live_sources (anchors no longer present in
their kit source) and test_manifest_covers_all_policy_carriers (a new
policy-carrier file with no manifest unit at all). Both are marked K3
below.

K4a/K4b (red runs): K4a is a small synthetic manifest/host pair proving
the mechanics; K4b is the REGRESSION proof against the real incident,
using the committed fixture (toolkit/tools/fixtures/host_pre_delivery_
CLAUDE.md -- ec4e6f0, see that file's own provenance header) -- no live
git-show into another repo from this test suite (forbidden by the
mechanism's own spec, B3).

K5 (a green run against a real, separate host tree) is NOT part of
this automated suite on purpose: it depends on another repository's
presence on the machine and is a manual witness command, not a
portable regression test.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import install_parity as ip  # noqa: E402


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SHIPPED_MANIFEST = HERE / "install_parity_anchors.json"
TOOLKIT_ROOT = HERE.parent


# ---------------------------------------------------------------------------
# normalize_text
# ---------------------------------------------------------------------------


def test_normalize_text_strips_bom_and_crlf():
    assert ip.normalize_text("\ufeffhello\r\nworld\r\n") == "hello\nworld\n"


def test_normalize_text_noop_on_plain_lf():
    assert ip.normalize_text("hello\nworld\n") == "hello\nworld\n"


# ---------------------------------------------------------------------------
# derive_anchors
# ---------------------------------------------------------------------------


def test_derive_anchors_headers_and_numbered_rules():
    text = "# Title\n\n## Sub\n\n1. First rule text here\n2. Second rule\n"
    anchors = ip.derive_anchors(text)
    assert "Title" in anchors
    assert "Sub" in anchors
    assert "1. First rule text here" in anchors
    assert "2. Second rule" in anchors


def test_derive_anchors_caps_marker_pure_run():
    text = "See the TWO-LAYER CRITIC ENTRY for details.\n"
    anchors = ip.derive_anchors(text)
    assert "TWO-LAYER CRITIC ENTRY" in anchors


def test_derive_anchors_caps_marker_with_glue_word_and_arrow():
    text = "DRAFTING -> designer BY DEFAULT is the threshold.\n"
    anchors = ip.derive_anchors(text)
    # the exact real-world marker (kit CLAUDE.md uses an actual arrow char,
    # this fixture uses the ASCII "->" -- the extraction logic doesn't care)
    assert any("DRAFTING" in a and "BY DEFAULT" in a for a in anchors)


def test_derive_anchors_strips_frontmatter_model_line():
    text = "---\nname: scout\nmodel: sonnet\ndescription: x\n---\n# scout\n\n## Rules\n"
    anchors = ip.derive_anchors(text)
    assert not any("model:" in a or "sonnet" in a for a in anchors)
    assert "scout" in anchors
    assert "Rules" in anchors


def test_derive_anchors_truncates_long_lines_to_max_len():
    long_line = "1. " + ("x" * 500)
    anchors = ip.derive_anchors(long_line + "\n")
    assert all(len(a) <= ip.MAX_ANCHOR_LEN for a in anchors)


def test_extract_caps_phrases_glue_run_boundary_3_ok_4_breaks():
    # 3 short glue words between two CAPS words -- still one phrase (<=3 allowed)
    line3 = "START a b c END"
    phrases3 = ip._extract_caps_phrases(line3)
    assert any(p.startswith("START") and p.endswith("END") for p in phrases3)
    # 4 short glue words -- breaks the run, START and END are NOT joined
    line4 = "START a b c d END"
    phrases4 = ip._extract_caps_phrases(line4)
    assert not any(p.startswith("START") and p.endswith("END") for p in phrases4)


def test_extract_caps_phrases_glue_word_len_boundary_14_ok_15_breaks():
    glue14 = "x" * 14
    glue15 = "x" * 15
    line_ok = f"START {glue14} END"
    line_break = f"START {glue15} END"
    phrases_ok = ip._extract_caps_phrases(line_ok)
    phrases_break = ip._extract_caps_phrases(line_break)
    assert any(p.startswith("START") and p.endswith("END") for p in phrases_ok)
    assert not any(p.startswith("START") and p.endswith("END") for p in phrases_break)


def test_derive_anchors_dedupes():
    text = "# Title\n\n# Title\n"
    anchors = ip.derive_anchors(text)
    assert anchors.count("Title") == 1


# ---------------------------------------------------------------------------
# manifest load + structural validation
# ---------------------------------------------------------------------------


def _unit(unit_id="u1", kit_path="toolkit/X.md", host_path="X.md", anchors=None, kind="anchor"):
    return {
        "unit_id": unit_id,
        "kit_path": kit_path,
        "host_path": host_path,
        "anchors": anchors if anchors is not None else ["hello"],
        "kind": kind,
    }


def _write_manifest(tmp_path: Path, units: list) -> Path:
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps(units, ensure_ascii=False), encoding="utf-8")
    return p


def test_load_manifest_happy_path(tmp_path):
    p = _write_manifest(tmp_path, [_unit()])
    units = ip.load_manifest(p)
    assert len(units) == 1


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(tmp_path / "nope.json")


def test_load_manifest_not_json(tmp_path):
    p = tmp_path / "m.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


def test_load_manifest_empty_list_is_zero_anchors_error(tmp_path):
    p = _write_manifest(tmp_path, [])
    with pytest.raises(ip.ManifestError, match="zero total anchors"):
        ip.load_manifest(p)


def test_load_manifest_not_a_list(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"a": 1}), encoding="utf-8")
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


def test_load_manifest_entry_not_object(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps([["a", "b"]]), encoding="utf-8")
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


def test_load_manifest_missing_field(tmp_path):
    entry = _unit()
    del entry["kind"]
    p = _write_manifest(tmp_path, [entry])
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


def test_load_manifest_wrong_type_field(tmp_path):
    entry = _unit()
    entry["unit_id"] = 123  # number instead of string
    p = _write_manifest(tmp_path, [entry])
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


def test_load_manifest_unknown_kind(tmp_path):
    entry = _unit(kind="bogus")
    p = _write_manifest(tmp_path, [entry])
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


def test_load_manifest_duplicate_unit_id(tmp_path):
    p = _write_manifest(tmp_path, [_unit(unit_id="dup"), _unit(unit_id="dup", host_path="Y.md")])
    with pytest.raises(ip.ManifestError, match="duplicate unit_id"):
        ip.load_manifest(p)


def test_load_manifest_duplicate_anchor_in_unit(tmp_path):
    p = _write_manifest(tmp_path, [_unit(anchors=["a", "a"])])
    with pytest.raises(ip.ManifestError, match="duplicate anchor"):
        ip.load_manifest(p)


def test_load_manifest_empty_anchor_string(tmp_path):
    p = _write_manifest(tmp_path, [_unit(anchors=["a", ""])])
    with pytest.raises(ip.ManifestError, match="empty/whitespace"):
        ip.load_manifest(p)


def test_load_manifest_whitespace_only_anchor(tmp_path):
    p = _write_manifest(tmp_path, [_unit(anchors=["a", "   "])])
    with pytest.raises(ip.ManifestError, match="empty/whitespace"):
        ip.load_manifest(p)


def test_load_manifest_anchor_at_max_len_ok(tmp_path):
    a200 = "x" * 200
    p = _write_manifest(tmp_path, [_unit(anchors=[a200])])
    units = ip.load_manifest(p)
    assert units[0]["anchors"] == [a200]


def test_load_manifest_anchor_over_max_len_fails(tmp_path):
    a201 = "x" * 201
    p = _write_manifest(tmp_path, [_unit(anchors=[a201])])
    with pytest.raises(ip.ManifestError, match="over 200"):
        ip.load_manifest(p)


def test_load_manifest_path_kind_with_anchors_fails(tmp_path):
    p = _write_manifest(tmp_path, [_unit(kind="path", anchors=["oops"])])
    with pytest.raises(ip.ManifestError, match="kind 'path'"):
        ip.load_manifest(p)


def test_load_manifest_path_kind_empty_anchors_ok_when_another_unit_has_anchor(tmp_path):
    p = _write_manifest(tmp_path, [_unit(unit_id="a1", kind="anchor"), _unit(unit_id="p1", kind="path", anchors=[])])
    units = ip.load_manifest(p)
    assert len(units) == 2


def test_load_manifest_dotdot_in_host_path_rejected(tmp_path):
    p = _write_manifest(tmp_path, [_unit(host_path="../../etc/passwd")])
    with pytest.raises(ip.ManifestError, match=r"\.\."):
        ip.load_manifest(p)


def test_load_manifest_dotdot_in_kit_path_rejected(tmp_path):
    p = _write_manifest(tmp_path, [_unit(kit_path="toolkit/../../secret.md")])
    with pytest.raises(ip.ManifestError, match=r"\.\."):
        ip.load_manifest(p)


def test_load_manifest_duplicate_json_keys_rejected(tmp_path):
    p = tmp_path / "m.json"
    # hand-write raw JSON with a duplicate key inside one object
    raw = '[{"unit_id": "a", "unit_id": "b", "kit_path": "x", "host_path": "x", "anchors": ["z"], "kind": "anchor"}]'
    p.write_text(raw, encoding="utf-8")
    with pytest.raises(ip.ManifestError, match="duplicate JSON key"):
        ip.load_manifest(p)


def test_load_manifest_list_of_lists_form_rejected(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps([["unit_id", "a"]]), encoding="utf-8")
    with pytest.raises(ip.ManifestError):
        ip.load_manifest(p)


# ---------------------------------------------------------------------------
# ledger: search order, parse, classify
# ---------------------------------------------------------------------------


def test_find_ledger_root_wins_over_docs(tmp_path):
    (tmp_path / "ADOPTION_LEDGER.md").write_text("x", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ADOPTION_LEDGER.md").write_text("y", encoding="utf-8")
    found, checked = ip.find_ledger(tmp_path, None)
    assert found == tmp_path / "ADOPTION_LEDGER.md"


def test_find_ledger_falls_back_to_docs(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ADOPTION_LEDGER.md").write_text("y", encoding="utf-8")
    found, checked = ip.find_ledger(tmp_path, None)
    assert found == tmp_path / "docs" / "ADOPTION_LEDGER.md"


def test_find_ledger_none_found_lists_checked(tmp_path):
    found, checked = ip.find_ledger(tmp_path, None)
    assert found is None
    assert len(checked) == 2


def test_find_ledger_explicit_arg_used(tmp_path):
    custom = tmp_path / "custom_ledger.md"
    custom.write_text("z", encoding="utf-8")
    found, checked = ip.find_ledger(tmp_path, str(custom))
    assert found == custom


def test_parse_ledger_basic_rows(tmp_path):
    p = tmp_path / "L.md"
    p.write_text(
        "# Ledger\n\n"
        "| Kit mechanism | Status | Basis |\n"
        "|---|---|---|\n"
        "| Routing policy (CLAUDE.md core rules) | adopt | x |\n"
        "| Skills (`.claude/skills/*`) | native-equivalent | y |\n",
        encoding="utf-8",
    )
    rows, corrupt = ip.parse_ledger(p)
    assert not corrupt
    assert ("Routing policy (CLAUDE.md core rules)", "adopt") in rows
    assert ("Skills (`.claude/skills/*`)", "native-equivalent") in rows


def test_parse_ledger_zero_rows(tmp_path):
    p = tmp_path / "L.md"
    p.write_text("# Ledger\n\nNo table here.\n", encoding="utf-8")
    rows, corrupt = ip.parse_ledger(p)
    assert rows == []
    assert not corrupt


def test_stems_plural_singular_and_punctuation():
    assert ip.stems("Role profiles") == {"role", "profile"}
    assert ip.stems("role-profiles:scout") == {"role", "profile", "scout"}


def test_ledger_key_strips_suffix():
    assert ip.ledger_key("role-profiles:scout") == "role-profiles"
    assert ip.ledger_key("routing-policy") == "routing-policy"


def test_classify_missing_no_ledger_is_unknown():
    assert ip.classify_missing("routing-policy", False, []) == "UNKNOWN"


def test_classify_missing_adopt_is_missing():
    rows = [("Routing policy (CLAUDE.md core rules)", "adopt")]
    assert ip.classify_missing("routing-policy", True, rows) == "MISSING"


def test_classify_missing_native_equivalent_is_informational():
    rows = [("Wiring integrity check (...)", "native-equivalent")]
    assert ip.classify_missing("wiring-integrity", True, rows) == "informational"


def test_classify_missing_deferred_is_informational():
    rows = [("Gateway / api-keys contour (...)", "deferred(trigger: contour changed)")]
    assert ip.classify_missing("gateway-contour", True, rows) == "informational"


def test_classify_missing_rejected_is_informational():
    rows = [("Non-Claude worker guard (...)", "rejected")]
    assert ip.classify_missing("non-claude-worker-guard", True, rows) == "informational"


def test_classify_missing_no_matching_row_is_unknown():
    rows = [("Something else entirely", "adopt")]
    assert ip.classify_missing("routing-policy", True, rows) == "UNKNOWN"


def test_classify_missing_unrecognized_status_is_unknown():
    rows = [("Routing policy (CLAUDE.md core rules)", "maybe later")]
    assert ip.classify_missing("routing-policy", True, rows) == "UNKNOWN"


def test_classify_missing_blank_status_is_unknown():
    rows = [("Routing policy (CLAUDE.md core rules)", "")]
    assert ip.classify_missing("routing-policy", True, rows) == "UNKNOWN"


# ---------------------------------------------------------------------------
# run_check: integration, edges, adversarial battery (M3/M4)
# ---------------------------------------------------------------------------


def _tree(tmp_path, files: dict) -> Path:
    root = tmp_path / "root"
    root.mkdir()
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8")
    return root


def test_run_check_root_not_a_directory(tmp_path):
    f = tmp_path / "afile.txt"
    f.write_text("x", encoding="utf-8")
    m = _write_manifest(tmp_path, [_unit()])
    rc = ip.run_check(m, f, None)
    assert rc == 2


def test_run_check_root_does_not_exist(tmp_path):
    m = _write_manifest(tmp_path, [_unit()])
    rc = ip.run_check(m, tmp_path / "nope", None)
    assert rc == 2


def test_run_check_manifest_missing(tmp_path, capsys):
    root = _tree(tmp_path, {})
    rc = ip.run_check(tmp_path / "no_manifest.json", root, None)
    assert rc == 2


def test_run_check_clean_no_ledger(tmp_path):
    root = _tree(tmp_path, {"X.md": "hello world"})
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_missing_anchor_no_ledger_is_unknown_exit1(tmp_path):
    root = _tree(tmp_path, {"X.md": "goodbye world"})
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 1


def test_run_check_missing_anchor_ledger_adopt_is_missing_exit1(tmp_path):
    root = _tree(
        tmp_path,
        {
            "X.md": "goodbye world",
            "ADOPTION_LEDGER.md": "| Kit mechanism | Status | Basis |\n|---|---|---|\n| u1 thing | adopt | x |\n",
        },
    )
    m = _write_manifest(tmp_path, [_unit(unit_id="u1-thing", anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 1


def test_run_check_missing_anchor_ledger_deferred_is_informational_exit0(tmp_path):
    root = _tree(
        tmp_path,
        {
            "X.md": "goodbye world",
            "ADOPTION_LEDGER.md": "| Kit mechanism | Status | Basis |\n|---|---|---|\n| u1 thing | deferred(trigger: x) | x |\n",
        },
    )
    m = _write_manifest(tmp_path, [_unit(unit_id="u1-thing", anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_host_file_absent_path_kind_ledger_adopt_missing(tmp_path):
    root = _tree(
        tmp_path,
        {
            "X.md": "hello",
            "ADOPTION_LEDGER.md": "| Kit mechanism | Status | Basis |\n|---|---|---|\n| model binding | adopt | x |\n",
        },
    )
    m = _write_manifest(
        tmp_path,
        [
            _unit(unit_id="a1", anchors=["hello"]),  # keeps total_anchor_count > 0
            _unit(unit_id="model-binding", kind="path", anchors=[], host_path="delegation.config.yaml"),
        ],
    )
    rc = ip.run_check(m, root, None)
    assert rc == 1


def test_run_check_host_file_empty_is_unconditional_missing(tmp_path):
    root = _tree(
        tmp_path,
        {
            "X.md": "",
            "ADOPTION_LEDGER.md": "| Kit mechanism | Status | Basis |\n|---|---|---|\n| u1 thing | rejected | x |\n",
        },
    )
    # even with a 'rejected' (=> would be informational) ledger row, an
    # EXISTING EMPTY file is always MISSING (M3: unconditional)
    m = _write_manifest(tmp_path, [_unit(unit_id="u1-thing", anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 1


def test_run_check_no_ledger_found_bootstrap_unknown(tmp_path):
    root = _tree(tmp_path, {"X.md": "nothing relevant"})
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 1


def test_run_check_ledger_zero_rows_parsed_still_unknown(tmp_path, capsys):
    root = _tree(tmp_path, {"X.md": "nothing relevant", "ADOPTION_LEDGER.md": "no table\n"})
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    out = capsys.readouterr().out
    assert "zero rows parsed" in out
    assert rc == 1


def test_parse_ledger_unreadable_file_is_fail_open_corrupt(tmp_path, monkeypatch):
    p = tmp_path / "L.md"
    p.write_text("| Kit mechanism | Status | Basis |\n|---|---|---|\n| x | adopt | y |\n", encoding="utf-8")

    real_read_text = Path.read_text

    def boom(self, *a, **kw):
        if self == p:
            raise OSError("simulated unreadable ledger")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    rows, corrupt = ip.parse_ledger(p)
    assert corrupt is True
    assert rows == []


def test_run_check_corrupt_ledger_fail_open_warn_not_exit2(tmp_path, monkeypatch, capsys):
    root = _tree(
        tmp_path,
        {"X.md": "hello world", "ADOPTION_LEDGER.md": "| Kit mechanism | Status | Basis |\n|---|---|---|\n| x | adopt | y |\n"},
    )
    ledger_path = root / "ADOPTION_LEDGER.md"
    real_read_text = Path.read_text

    def boom(self, *a, **kw):
        if self == ledger_path:
            raise OSError("simulated unreadable ledger")
        return real_read_text(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", boom)
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    out = capsys.readouterr().out
    assert "WARN" in out
    assert rc == 0  # anchor present, ledger corruption doesn't force exit 2


def test_run_check_one_character_anchor_is_valid(tmp_path):
    root = _tree(tmp_path, {"X.md": "a needle: Q, in the haystack"})
    m = _write_manifest(tmp_path, [_unit(anchors=["Q"])])
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_utf16_host_file_no_crash_warns(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "X.md").write_bytes("hello world".encode("utf-16"))
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    # UTF-16 bytes are not valid UTF-8 -> decoded with errors=replace,
    # WARN fires, no crash; content is garbled so the anchor legitimately
    # doesn't match (exit 1) -- the invariant under test is "never crashes"
    assert rc in (0, 1)


def test_run_check_non_utf8_host_file_warns_and_continues(tmp_path, capsys):
    root = tmp_path / "root"
    root.mkdir()
    (root / "X.md").write_bytes("hello \xff\xfe world".encode("latin-1"))
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    out = capsys.readouterr().out
    assert "WARN: non-UTF8" in out
    assert rc == 0


def test_run_check_crlf_and_bom_normalized_both_sides(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "X.md").write_bytes(b"\xef\xbb\xbfhello\r\nworld\r\n")
    m = _write_manifest(tmp_path, [_unit(anchors=["hello\nworld"])])
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_literal_substring_not_regex(tmp_path):
    root = _tree(tmp_path, {"X.md": "the pattern .*[ is here literally"})
    m = _write_manifest(tmp_path, [_unit(anchors=[".*["])])
    rc = ip.run_check(m, root, None)
    assert rc == 0  # literal substring match, not interpreted as regex


def test_run_check_cyrillic_cjk_anchor_and_path(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "\u041f\u0443\u0442\u044c.md").write_text("\u65e5\u672c\u8a9e \u043f\u0440\u0438\u0432\u0435\u0442", encoding="utf-8")
    m = _write_manifest(
        tmp_path,
        [_unit(host_path="\u041f\u0443\u0442\u044c.md", anchors=["\u65e5\u672c\u8a9e", "\u043f\u0440\u0438\u0432\u0435\u0442"])],
    )
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_manifest_dotdot_refused_before_read(tmp_path):
    root = _tree(tmp_path, {})
    entry = _unit(host_path="../outside.md")
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps([entry]), encoding="utf-8")
    rc = ip.run_check(p, root, None)
    assert rc == 2


def test_run_check_zero_anchors_manifest_exit2(tmp_path):
    root = _tree(tmp_path, {})
    m = _write_manifest(tmp_path, [_unit(kind="path", anchors=[])])
    rc = ip.run_check(m, root, None)
    assert rc == 2


def test_run_check_one_anchor_manifest_is_normal(tmp_path):
    root = _tree(tmp_path, {"X.md": "hello"})
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_500_missing_all_printed_no_truncation(tmp_path, capsys):
    anchors = [f"needle-{i}" for i in range(500)]
    root = _tree(tmp_path, {"X.md": "nothing matches any needle here"})
    m = _write_manifest(tmp_path, [_unit(anchors=anchors)])
    rc = ip.run_check(m, root, None)
    out = capsys.readouterr().out
    assert rc == 1
    for i in (0, 250, 499):
        assert f"needle-{i}" in out


def test_run_check_large_host_file_5mb_20k_lines(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    lines = [f"filler line number {i}\n" for i in range(20000)]
    lines.append("the-real-anchor-text\n")
    content = "".join(lines)
    while len(content.encode("utf-8")) < 5 * 1024 * 1024:
        content += "padding padding padding padding padding padding\n"
    (root / "X.md").write_text(content, encoding="utf-8")
    m = _write_manifest(tmp_path, [_unit(anchors=["the-real-anchor-text"])])
    rc = ip.run_check(m, root, None)
    assert rc == 0


def test_run_check_manifest_battery_number_instead_of_string(tmp_path):
    entry = _unit()
    entry["kit_path"] = 5
    p = tmp_path / "manifest.json"
    p.write_text(json.dumps([entry]), encoding="utf-8")
    rc = ip.run_check(p, _tree(tmp_path, {}), None)
    assert rc == 2


def test_run_check_root_is_symlink(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    (real / "X.md").write_text("hello", encoding="utf-8")
    link = tmp_path / "link"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted in this environment")
    m = _write_manifest(tmp_path, [_unit(anchors=["hello"])])
    rc = ip.run_check(m, link, None)
    assert rc == 0


# ---------------------------------------------------------------------------
# --emit-anchors CLI
# ---------------------------------------------------------------------------


def test_run_emit_anchors_bare_list(tmp_path, capsys):
    f = tmp_path / "S.md"
    f.write_text("# Title\n\n1. A rule\n", encoding="utf-8")
    rc = ip.run_emit_anchors(f, None, None, None, None)
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "Title" in data
    assert rc == 0


def test_run_emit_anchors_full_entry(tmp_path, capsys):
    f = tmp_path / "S.md"
    f.write_text("# Title\n", encoding="utf-8")
    rc = ip.run_emit_anchors(f, "u1", "toolkit/S.md", "S.md", "anchor")
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["unit_id"] == "u1"
    assert data["kind"] == "anchor"
    assert rc == 0


def test_run_emit_anchors_missing_source(tmp_path):
    rc = ip.run_emit_anchors(tmp_path / "nope.md", None, None, None, None)
    assert rc == 2


def test_run_emit_anchors_unit_id_without_other_fields_errors(tmp_path):
    f = tmp_path / "S.md"
    f.write_text("# Title\n", encoding="utf-8")
    rc = ip.run_emit_anchors(f, "u1", None, None, None)
    assert rc == 2


def test_main_no_mode_selected_errors(capsys):
    with pytest.raises(SystemExit):
        ip.main([])


# ---------------------------------------------------------------------------
# K3 -- anti-staleness (mandatory half of the mechanism)
# ---------------------------------------------------------------------------


def _resolve_kit_source(kit_path: str) -> Path | None:
    """Resolve a manifest unit's kit_path (always "toolkit/..." form, see
    install_parity.py's module docstring) against the HQ kit source tree:
    TOOLKIT_ROOT.parent / kit_path, e.g. "toolkit/CLAUDE.md" ->
    <repo_root>/toolkit/CLAUDE.md.

    This resolves ONLY the HQ layout on purpose (see
    test_manifest_anchors_match_live_sources for why a host-layout
    fallback is not attempted here)."""
    c = TOOLKIT_ROOT.parent / kit_path
    return c if c.is_file() else None


def test_manifest_anchors_match_live_sources():
    """K3(1): every anchor currently committed in install_parity_anchors.json
    for an 'anchor'-kind unit must still be a literal substring of that
    unit's CURRENT kit_path source. If someone edits toolkit/CLAUDE.md (or
    any tracked agent/PROCESS carrier) without regenerating the manifest,
    this test fails immediately -- the "trap decay" lesson from a host
    deployment's delivery findings applied to this mechanism's own
    manifest.

    This test runs ONLY on the HQ layout, where TOOLKIT_ROOT.parent/
    kit_path resolves to an independent kit SOURCE tree (kit_path and
    host_path are two distinct trees there). On a host/public-kit layout
    (no "toolkit/" subdir -- kit_path's prefix would have to be stripped
    to reach anything, and what it reaches is host_path itself, i.e. the
    DELIVERED copy, not an independent kit source) there is nothing
    separate left to check freshness against: host content is legitimately
    allowed to diverge from the kit's per the ledger's waiver table, and
    substring-asserting the manifest against the host's own delivered file
    would reject a legitimate customization as staleness (t-641 verdict:
    this was exactly the false-failure mode the earlier two-candidate
    fallback produced). So on a host layout this test SKIPS instead, with
    the reason printed; install_parity.py --check plus the ledger's waiver
    table cover host-layout freshness instead. This same suite is shipped
    as a sibling copy at <host_root>/tools/, where HQ's "toolkit/" prefix
    doesn't exist on disk -- that absence is exactly the skip trigger
    below (t-638 diagnosis: it used to be a FileNotFoundError instead)."""
    if not (TOOLKIT_ROOT.parent / "toolkit").is_dir():
        reason = (
            "manifest freshness is checked against the kit source tree; "
            "on a host layout use install_parity --check + the ledger waiver table"
        )
        print(reason)
        pytest.skip(reason)

    units = ip.load_manifest(SHIPPED_MANIFEST)
    stale = []
    unresolved = []
    for unit in units:
        if unit["kind"] != "anchor":
            continue
        src_path = _resolve_kit_source(unit["kit_path"])
        if src_path is None:
            unresolved.append((unit["unit_id"], str(TOOLKIT_ROOT.parent / unit["kit_path"])))
            continue
        text = ip.normalize_text(src_path.read_text(encoding="utf-8"))
        for a in unit["anchors"]:
            if ip.normalize_text(a) not in text:
                stale.append((unit["unit_id"], a))
    assert not unresolved, f"kit source not found under HQ layout: {unresolved[:10]}"
    assert not stale, f"stale anchors (manifest vs current kit source): {stale[:10]}"


def test_manifest_covers_all_policy_carriers():
    """K3(2): every currently-existing policy-carrier file (toolkit/CLAUDE.md,
    toolkit/.claude/agents/*.md, toolkit/PROCESS/*.md) has a corresponding
    'anchor'-kind unit in the manifest, by kit_path. Catches the OTHER
    staleness direction: a new carrier added with no manifest entry at
    all.

    Coverage is required only for carriers the KIT SHIPS. A host tree can
    carry files this test's glob also picks up that are host-LOCAL
    (generated at that host, never part of the kit delivery) -- e.g.
    PROCESS/CRITIC_EXAM.md and PROCESS/SCOUT_GOLDEN_SET*.md, generated by
    running exams on that host (t-638 diagnosis). A file with no manifest
    unit at all -- neither its kit_path form NOR its host_path form
    appears anywhere in the manifest -- is such a host-local carrier: it
    is skipped (name printed), not reported red. A file whose host_path
    DOES appear in the manifest (under a kit_path this glob didn't match)
    is a real anomaly and stays in `missing`."""
    units = ip.load_manifest(SHIPPED_MANIFEST)
    covered_kit_paths = {u["kit_path"] for u in units if u["kind"] == "anchor"}
    covered_host_paths = {u["host_path"] for u in units}

    expected = [TOOLKIT_ROOT / "CLAUDE.md"]
    expected += sorted((TOOLKIT_ROOT / ".claude" / "agents").glob("*.md"))
    expected += sorted((TOOLKIT_ROOT / "PROCESS").glob("*.md"))

    missing = []
    host_local_skipped = []
    for p in expected:
        rel_kit = "toolkit/" + str(p.relative_to(TOOLKIT_ROOT)).replace("\\", "/")
        if rel_kit in covered_kit_paths:
            continue
        rel_host = str(p.relative_to(TOOLKIT_ROOT)).replace("\\", "/")
        if rel_host not in covered_host_paths:
            host_local_skipped.append(rel_host)
            continue
        missing.append(rel_kit)
    if host_local_skipped:
        print(f"host-local policy carriers skipped (not a kit deliverable): {host_local_skipped}")
    assert not missing, f"policy carriers with no manifest unit: {missing}"


# ---------------------------------------------------------------------------
# K4a -- synthetic red run
# ---------------------------------------------------------------------------


def test_k4a_synthetic_red_run_missing_and_present_mixed(tmp_path):
    root = _tree(
        tmp_path,
        {
            "POLICY.md": "Rule ONE is here. Rule TWO TEXT is also here.",
            "ADOPTION_LEDGER.md": (
                "| Kit mechanism | Status | Basis |\n|---|---|---|\n"
                "| synthetic policy | adopt | x |\n"
            ),
        },
    )
    m = _write_manifest(
        tmp_path,
        [_unit(unit_id="synthetic-policy", host_path="POLICY.md", anchors=["Rule ONE", "Rule TWO TEXT", "Rule THREE MISSING"])],
    )
    rc = ip.run_check(m, root, None)
    assert rc == 1


# ---------------------------------------------------------------------------
# K4b -- regression proof against the real ec4e6f0 incident (fixture)
# ---------------------------------------------------------------------------

OUTBOUND_FIVE_MARKERS = [
    "DRAFTING",  # R2: designer-drafting-by-default threshold clause
    "TWO-LAYER CRITIC ENTRY",  # R3
    "SCOPE OF THE WITNESS RUN",  # R4
    "DETERMINISTIC SCRIPT RUNS",  # R8
    "13. Leaf routing",  # R13: whole rule absent
]


def test_k4b_regression_fixture_reports_all_five_outbound_markers(tmp_path, capsys):
    fixture_text = (FIXTURES / "host_pre_delivery_CLAUDE.md").read_text(encoding="utf-8")
    root = _tree(
        tmp_path,
        {
            "CLAUDE.md": fixture_text,
            "ADOPTION_LEDGER.md": (
                "| Kit mechanism | Status | Basis |\n|---|---|---|\n"
                "| Routing policy (CLAUDE.md core rules, Role != tier, Lead degradation, command hygiene) | adopt | x |\n"
            ),
        },
    )
    rc = ip.run_check(SHIPPED_MANIFEST, root, None)
    out = capsys.readouterr().out
    assert rc == 1
    for marker in OUTBOUND_FIVE_MARKERS:
        assert marker in out, f"OUTBOUND marker not found in --check output: {marker!r}"


def test_k4b_fixture_positive_control_marker_present_elsewhere_in_file():
    """Positive control for the above (command hygiene p.6): the fixture
    DOES contain plenty of routing-policy text that matches -- proving the
    empty MISSING result for a hypothetical clean file isn't a tool
    miscall. Rule 1 ('Recon -> scout by default...') is present verbatim
    in the ec4e6f0 fixture (it predates the regression) -- it must NOT be
    reported missing."""
    fixture_text = (FIXTURES / "host_pre_delivery_CLAUDE.md").read_text(encoding="utf-8")
    assert "Recon" in fixture_text and "scout by default" in fixture_text
