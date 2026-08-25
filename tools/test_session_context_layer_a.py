"""Tests for tools/session_context_layer_a.py -- the D-0103 HYBRID sibling
that adds Layer A CONTENT injection on top of the existing AUTO-BOOT
directive (D-0069: a SessionStart hook is a self-activating enforcement
file, so this batch's builder delivers under a sibling name; Lead lands it
onto tools/session_context.py at acceptance). Spec:
docs/tasks/2026-08-25_autoboot-hybrid-spec.md -- AK1..AK12, battery B1..B19.

Run from the repo root: python -m pytest tools/test_session_context_layer_a.py -q
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

# Twin-mode import (D-0069, SAME precedented pattern test_session_context.py
# already uses for its own now-retired session_context_d0076 sibling):
# BEFORE posting, this sibling module exists and carries the D-0103 HYBRID
# additions; AFTER Lead lands it onto tools/session_context.py and deletes
# the sibling (handoff step 1), this import falls back to the LIVE module,
# which by then carries the identical names (_LAYER_A_FILES, layer_a_lines,
# _write_stdout_deadline, ...) -- this whole file keeps working unchanged
# across the posting boundary, rather than becoming a permanent collection
# error the moment the sibling is deleted (measured empirically while
# building the landing-simulation witness for this batch's report).
try:
    import session_context_layer_a as sc
except ImportError:
    import session_context as sc

# ==== shared fixtures/helpers ===============================================


def _seed_repo(tmp_path):
    """Minimal repo shape main()/_build_context_lines_and_pending_ack()
    need -- mirrors test_session_context_autoboot.py's own _seed_repo."""
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "gateway").mkdir(exist_ok=True)
    return tmp_path


def _seed_layer_a_files(root, contents=None, skip=None):
    """Writes the five Layer A files (sc._LAYER_A_FILES) with short
    deterministic ASCII placeholder text, one line per file plus its own
    name so failures are easy to eyeball; `contents` overrides individual
    files' text, `skip` omits a name entirely (simulates "file absent").

    R2-К3 class-completeness note (critic §11 "класс-полнота"): writes
    via write_bytes with an EXPLICIT utf-8 encode, deliberately NOT
    Path.write_text() -- write_text() opens in platform text mode, which
    on Windows silently translates '\\n' to '\\r\\n' on write. That
    translation would make every non-CRLF-specific fixture in this file
    secretly CRLF on disk, which used to be invisible only because the
    pre-fix footer computed "bytes emitted" from st_size too (the exact
    tautology R2-К2 closes) -- now that the footer counts actual emitted
    bytes (LF-normalized, \\r already stripped by splitlines()), a
    write_text-seeded fixture would make EVERY test needing on-disk vs.
    emitted parity (AK3) spuriously diverge on this platform. Tests that
    deliberately WANT CRLF or non-ASCII content (B11, B24, B8/B9, B25)
    still write their own bytes directly, bypassing this helper."""
    skip = skip or set()
    contents = contents or {}
    for name in sc._LAYER_A_FILES:
        if name in skip:
            continue
        text = contents.get(name, f"placeholder content for {name}\nsecond line\n")
        (root / name).write_bytes(text.encode("utf-8"))


class _FakeStdin:
    """Mirrors test_session_context_autoboot.py's own _FakeStdin -- text
    only, no .buffer; compatible with this module's byte-deadline stdin
    reader via its getattr(stdin, "buffer", stdin) fallback (see
    read_stdin_payload()'s own docstring)."""

    def __init__(self, text, tty=False):
        self._text = text
        self._tty = tty

    def isatty(self):
        return self._tty

    def read(self):
        return self._text


def _write_bg_fact(track_dir, session_id, ts="t1", reason="no-green-run"):
    track_dir.mkdir(parents=True, exist_ok=True)
    path = track_dir / f"{session_id}.json"
    path.write_text(
        json.dumps({"main_gate_state": {"unsafe_completion": {"ts": ts, "reason": reason}}}),
        encoding="utf-8",
    )
    return path


class _MarkerRaisingStdout:
    """Raises on the write() call whose argument contains `marker` --
    counts calls so B18 can pin "exactly one write, and it raised"."""

    def __init__(self, marker):
        self._marker = marker
        self.chunks = []
        self.write_calls = 0

    def write(self, s):
        self.write_calls += 1
        if self._marker in s:
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


def _run_main_startup(root, monkeypatch, capsys):
    fake = _FakeStdin(json.dumps({"source": "startup"}))
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    out = capsys.readouterr().out
    return code, out


# ==== AK1: _LAYER_A_FILES constant ==========================================


def test_ak1_layer_a_files_constant_order_and_names():
    assert sc._LAYER_A_FILES == [
        "README.md",
        "PROJECT_CHARTER.md",
        "ANTI_GOALS.md",
        "PROJECT_PHILOSOPHY.md",
        "ARCHITECTURE_BOOT.md",
    ]


def test_ak10_layer_a_files_matches_boot_md_layer_a_section_independently():
    """AK10: independently re-derive the list from the LIVE BOOT.md's own
    "## Layer A" section (own regex, not session_context's parser) so a
    drift between the doc (single owner) and the hardcoded constant fails
    the canon loudly."""
    root = sc.repo_root()
    text = (root / "BOOT.md").read_text(encoding="utf-8")
    start = text.index("## Layer A")
    rest = text[start:]
    next_heading = rest.find("\n## ", 1)
    section = rest if next_heading == -1 else rest[:next_heading]
    names = re.findall(r"Read ([A-Z_]+\.md)\.", section)
    assert names == sc._LAYER_A_FILES


# ==== AK5 / _ascii_content_line unit tests ==================================


def test_ak5_dash_and_arrow_translit_table():
    line, t, u = sc._ascii_content_line(
        "a — b → c – d ← e … f"
    )
    assert line == "a -- b -> c - d <- e ... f"
    assert t == 5
    assert u == 0


def test_ak5_quotes_and_nbsp_translit_table():
    line, t, u = sc._ascii_content_line(
        "« x » “ y ” ‘ z ’ a b"
    )
    assert line == '" x " " y " \' z \' a b'
    assert t == 7
    assert u == 0


def test_ak5_unmapped_non_ascii_replaced_and_counted():
    line, t, u = sc._ascii_content_line("АБ ok")  # Cyrillic AB
    assert line == "?? ok"
    assert u == 2
    assert t == 0


def test_b7_control_chars_stripped_tab_survives():
    line, t, u = sc._ascii_content_line("a\x00b\x1b[31mc\td")
    assert "\x00" not in line
    assert "\x1b" not in line
    assert "\t" in line
    assert t == 0
    assert u == 0


def test_b10_500_char_line_not_truncated_unit():
    long_line = "x" * 500
    line, t, u = sc._ascii_content_line(long_line)
    assert len(line) == 500
    assert line == long_line


# ==== AK8: directive text ====================================================


def test_ak8_directive_prefix_preserved_and_new_wording_present():
    lines = sc._AUTOBOOT_DIRECTIVE_LINES
    assert lines[0].startswith("AUTO-BOOT (D-0103")
    joined = "\n".join(lines)
    assert "PRINTED BELOW" in joined
    assert "Do NOT open or re-read those five files" in joined
    assert "Read the files listed in BOOT.md in order" not in joined
    for line in lines:
        assert line.isascii()


# ==== AK12: docstring updated ================================================


def test_ak12_module_docstring_documents_layer_a_addition():
    doc = sc.__doc__
    assert "D-0103 HYBRID addition" in doc
    assert "LAYER_A_INLINE_WARN_BYTES" in doc


# ==== AK3 / AK6: framing, and the closing line carries the ACTUAL count =====


def test_ak3_framing_and_closing_line_carries_actual_counts(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(
        root,
        contents={
            "README.md": "line1\nline2\n",
            "PROJECT_CHARTER.md": "a\n",
            "ANTI_GOALS.md": "b\n",
            "PROJECT_PHILOSOPHY.md": "c\n",
            "ARCHITECTURE_BOOT.md": "d\ne\nf\n",
        },
    )
    sizes = {name: (root / name).stat().st_size for name in sc._LAYER_A_FILES}
    total = sum(sizes.values())
    lines = sc.layer_a_lines(root)
    assert lines[0] == (
        f"--- BOOT LAYER A INJECTED (D-0103 hybrid) -- 5 files, {total} bytes on disk ---"
    )
    assert lines[-1] == f"--- END BOOT LAYER A: 5 files, 8 lines, {total} bytes emitted ---"
    assert f"----- BEGIN README.md ({sizes['README.md']} bytes) -----" in lines
    assert "----- END README.md -----" in lines


# ==== B1: one file absent ====================================================


def test_b1_missing_file_yields_missing_marker_others_injected(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root, skip={"ANTI_GOALS.md"})
    lines = sc.layer_a_lines(root)
    assert "[missing: ANTI_GOALS.md -- not injected, read this one file yourself]" in lines
    assert any(l.startswith("----- BEGIN README.md") for l in lines)
    assert lines[-1].startswith("--- END BOOT LAYER A: 4 files,")


# ==== B2: directory of the same name =========================================


def test_b2_directory_in_place_of_file_treated_as_missing(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root, skip={"PROJECT_CHARTER.md"})
    (root / "PROJECT_CHARTER.md").mkdir()
    lines = sc.layer_a_lines(root)
    assert "[missing: PROJECT_CHARTER.md -- not injected, read this one file yourself]" in lines
    assert lines[-1].startswith("--- END BOOT LAYER A: 4 files,")


# ==== B3: empty (0-byte) file -- distinguished from "missing" ===============


def test_b3_empty_file_is_begin_end_pair_not_missing(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    (root / "PROJECT_PHILOSOPHY.md").write_bytes(b"")
    lines = sc.layer_a_lines(root)
    assert (
        "[missing: PROJECT_PHILOSOPHY.md -- not injected, read this one file yourself]"
        not in lines
    )
    idx_begin = lines.index("----- BEGIN PROJECT_PHILOSOPHY.md (0 bytes) -----")
    assert lines[idx_begin + 1] == "----- END PROJECT_PHILOSOPHY.md -----"


# ==== AK4 / B4 / B5: WARN threshold boundary (rule 6a: AT and BEYOND) =======


def _write_files_summing_to(root, total_bytes):
    # 5 files, first one carries most of the weight, the rest 1 byte each
    # -- keeps every file non-empty (avoids overlapping the B3 case).
    sizes = [total_bytes - 4, 1, 1, 1, 1]
    for name, n in zip(sc._LAYER_A_FILES, sizes):
        (root / name).write_bytes(b"x" * n)


def test_b4_boundary_exact_threshold_no_warn(tmp_path):
    root = _seed_repo(tmp_path)
    _write_files_summing_to(root, sc.LAYER_A_INLINE_WARN_BYTES)
    lines = sc.layer_a_lines(root)
    assert not any(l.startswith("AUTO-BOOT: Layer A is ") for l in lines)
    assert lines[0].startswith("--- BOOT LAYER A INJECTED")


def test_b5_boundary_threshold_plus_one_warns_and_injects_full(tmp_path):
    root = _seed_repo(tmp_path)
    total = sc.LAYER_A_INLINE_WARN_BYTES + 1
    _write_files_summing_to(root, total)
    lines = sc.layer_a_lines(root)
    assert lines[0] == (
        f"AUTO-BOOT: Layer A is {total} bytes, over the "
        f"{sc.LAYER_A_INLINE_WARN_BYTES} byte notice threshold -- injected in full; "
        "every fresh session now pays these bytes of context, the "
        "threshold exists so growth is a decision, not drift -- tell "
        "the operator the orientation layer has grown."
    )
    assert any(l.startswith("--- BOOT LAYER A INJECTED") for l in lines)
    assert any(l.startswith("--- END BOOT LAYER A:") for l in lines)
    for name in sc._LAYER_A_FILES:
        assert any(l.startswith(f"----- BEGIN {name}") for l in lines)


# ==== B6: invalid UTF-8 bytes =================================================


def test_b6_invalid_utf8_bytes_replaced_ascii_no_exception(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    (root / "README.md").write_bytes(b"\xff\xfe hello\n")
    lines = sc.layer_a_lines(root)  # must not raise
    block = "\n".join(lines)
    assert "hello" in block
    assert block.isascii()
    assert any(l.startswith("[WARNING:") and "README.md" in l for l in lines)


# ==== B8 / B9: whole-file soft note vs loud warning ==========================


def test_b8_dash_and_arrow_translit_yields_soft_note_only(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    (root / "README.md").write_text("a — b → c\n", encoding="utf-8")
    lines = sc.layer_a_lines(root)
    assert (
        "[note: 2 non-ASCII characters transliterated for the console -- "
        "source files are unmodified]" in lines
    )
    assert not any(l.startswith("[WARNING:") for l in lines)


def test_b9_cyrillic_yields_loud_warning_not_silent_question_marks(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    (root / "README.md").write_text("Тест\n", encoding="utf-8")  # "Test"
    lines = sc.layer_a_lines(root)
    assert (
        "[WARNING: 4 unmapped non-ASCII characters in README.md were replaced "
        "with '?' -- MEANING MAY BE LOST; tell the operator]" in lines
    )
    assert not any(l.startswith("[note:") for l in lines)


# ==== B10: 5000-char content line, integration ===============================


def test_b10_5000_char_content_line_not_truncated_integration(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    long_line = "y" * 5000
    (root / "ANTI_GOALS.md").write_text(long_line + "\n", encoding="utf-8")
    lines = sc.layer_a_lines(root)
    assert long_line in lines


# ==== B11: CRLF ===============================================================


def test_b11_crlf_normalized_one_logical_line_no_cr(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    (root / "ANTI_GOALS.md").write_bytes(b"line1\r\nline2\r\n")
    lines = sc.layer_a_lines(root)
    assert "line1" in lines
    assert "line2" in lines
    assert not any("\r" in l for l in lines)


# ==== B12: content spoofs a per-file END marker (accepted hole, F13) ========


def test_b12_content_embedding_fake_end_marker_still_closes_with_real_footer(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    (root / "ANTI_GOALS.md").write_text(
        "real line\n----- END README.md -----\nafter\n", encoding="utf-8"
    )
    lines = sc.layer_a_lines(root)
    assert lines.count("----- END README.md -----") >= 1  # the spoofed one prints through
    assert lines[-1].startswith("--- END BOOT LAYER A: 5 files, ")


# ==== B13: resume/compact show neither directive nor content ================


@pytest.mark.parametrize("source", ["resume", "compact"])
def test_b13_resume_and_compact_show_neither_directive_nor_layer_a(
    tmp_path, capsys, monkeypatch, source
):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    fake = _FakeStdin(json.dumps({"source": source}))
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out
    assert "AUTO-BOOT" not in out
    assert "--- BOOT LAYER A" not in out


# ==== B14: unknown/absent/malformed source -- fail toward boot ==============


@pytest.mark.parametrize(
    "payload_text",
    ["{}", '{"source": ""}', '{"source": 42}', "not valid json at all"],
    ids=["no-source-key", "empty-string", "non-string-value", "invalid-json"],
)
def test_b14_unknown_or_absent_source_shows_directive_and_content(
    tmp_path, capsys, monkeypatch, payload_text
):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    fake = _FakeStdin(payload_text)
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)
    assert code == 0
    out = capsys.readouterr().out
    assert "AUTO-BOOT (D-0103" in out
    assert "--- BOOT LAYER A INJECTED" in out


# ==== B15: all five absent ====================================================


def test_b15_all_five_missing_header_five_missing_lines_and_closing(tmp_path):
    root = _seed_repo(tmp_path)
    lines = sc.layer_a_lines(root)
    assert lines[0] == "--- BOOT LAYER A INJECTED (D-0103 hybrid) -- 5 files, 0 bytes on disk ---"
    for name in sc._LAYER_A_FILES:
        assert f"[missing: {name} -- not injected, read this one file yourself]" in lines
    assert lines[-1] == "--- END BOOT LAYER A: 0 files, 0 lines, 0 bytes emitted ---"


# ==== AK2 / AK9 / B16: fail-open ==============================================


def test_ak2_internal_unexpected_failure_degrades_to_single_line(tmp_path, monkeypatch):
    """AK2: layer_a_lines() NEVER raises -- an unexpected (non-OSError)
    failure deep inside the read step degrades to ONE line via its OWN
    try/except, same pattern as wiring_lines()."""
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)

    def _boom(self, *a, **kw):
        raise RuntimeError("simulated non-OSError read failure (test)")

    monkeypatch.setattr(sc.Path, "read_text", _boom)
    lines = sc.layer_a_lines(root)
    assert len(lines) == 1
    assert lines[0].startswith("AUTO-BOOT: Layer A inline unavailable (")
    assert lines[0].endswith(") -- read the five files listed in BOOT.md yourself.")


def test_b16_layer_a_lines_replaced_wholesale_does_not_blank_context(
    tmp_path, capsys, monkeypatch
):
    """AK9 / "Fail-open строго сильнее": even when layer_a_lines() itself
    is monkeypatched to raise (bypassing its OWN try/except entirely),
    main()'s second, outer wrapper must still keep NOW/MODEL/BOOT
    BUDGET/... and the AUTO-BOOT directive intact, degrading only the
    Layer A block to the AK2 single line."""
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)

    def _boom(_root):
        raise RuntimeError("boom-layer-a (test)")

    monkeypatch.setattr(sc, "layer_a_lines", _boom)
    code, out = _run_main_startup(root, monkeypatch, capsys)
    assert code == 0
    assert "NOW:" in out
    assert "AUTO-BOOT (D-0103" in out
    assert "AUTO-BOOT: Layer A inline unavailable (" in out
    assert "--- BOOT LAYER A INJECTED" not in out


# ==== B26 (R2-К4/ФИКС 3): exception whose OWN __str__ raises ================


class _ThrowingStrException(Exception):
    """Deliberately pathological: __str__ itself raises. Both fail-open
    sites (layer_a_lines()'s own except -> _layer_a_unavailable_line, and
    main()'s outer except boundary) format str(exc)/f"{exc}" -- an
    exception this hostile used to escape both (critic-measured: rc=0,
    NOW present: False, WHOLE CONTEXT BLANKED: True)."""

    def __str__(self):
        raise RuntimeError("str() itself raises (test)")


def test_b26_layer_a_lines_own_except_survives_raising_str(tmp_path, monkeypatch):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)

    def _boom(self, *a, **kw):
        raise _ThrowingStrException("read boom")

    monkeypatch.setattr(sc.Path, "read_text", _boom)
    lines = sc.layer_a_lines(root)  # must not raise
    assert len(lines) == 1
    assert lines[0].startswith("AUTO-BOOT: Layer A inline unavailable (")


def test_b26_main_second_wrapper_survives_raising_str(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)

    def _boom(_root):
        raise _ThrowingStrException("boom-layer-a")

    monkeypatch.setattr(sc, "layer_a_lines", _boom)
    code, out = _run_main_startup(root, monkeypatch, capsys)
    assert code == 0
    assert "NOW:" in out
    assert "AUTO-BOOT (D-0103" in out
    assert "AUTO-BOOT: Layer A inline unavailable (" in out
    assert "--- BOOT LAYER A INJECTED" not in out


def test_b26_main_outer_except_survives_raising_str(tmp_path, monkeypatch):
    root = _seed_repo(tmp_path)

    def _boom(*a, **kw):
        raise _ThrowingStrException("outer boom")

    monkeypatch.setattr(sc, "_build_context_lines_and_pending_ack", _boom)
    fake = _FakeStdin(json.dumps({"source": "startup"}))
    monkeypatch.setattr(sys, "stdin", fake)
    code = sc.main(root)  # must not raise
    assert code == 0


# ==== B17: directive+content survive MAX_LINES boot-lite truncation =========


def test_b17_layer_a_survives_when_boot_lite_fills_max_lines(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    filler = [f"FILLER {i}" for i in range(sc.MAX_LINES)]
    monkeypatch.setattr(
        sc,
        "_build_context_lines_and_pending_ack",
        lambda *a, **kw: (filler, (root, [], None)),
    )
    code, out = _run_main_startup(root, monkeypatch, capsys)
    assert code == 0
    out_lines = out.strip().splitlines()
    assert out_lines[: sc.MAX_LINES] == filler
    rest = out_lines[sc.MAX_LINES :]
    assert any(l.startswith("AUTO-BOOT (D-0103") for l in rest)
    assert any(l.startswith("--- BOOT LAYER A INJECTED") for l in rest)


# ==== B18: stdout dies exactly on the Layer A marker =========================


def test_b18_stdout_failure_on_layer_a_marker_leaves_break_glass_unacked(tmp_path, monkeypatch):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    track_dir = root / ".claude" / "dod_track"
    _write_bg_fact(track_dir, "sess-b18")

    candidates_before = sc._break_glass_candidates(root)
    assert len(candidates_before) == 1, "sanity: expected exactly one pending fact before the run"
    fact_key = candidates_before[0]["key"]
    assert fact_key

    spy = _MarkerRaisingStdout("--- BOOT LAYER A")
    monkeypatch.setattr(sc.sys, "stdout", spy)
    err_fake = _RecordingStream()
    monkeypatch.setattr(sc.sys, "stderr", err_fake)

    fake = _FakeStdin(json.dumps({"source": "startup"}))
    monkeypatch.setattr(sys, "stdin", fake)
    rc = sc.main(root)

    assert rc == 0
    # B2: the single joined content write is all-or-nothing -- it raises
    # on the marker, so ZERO content bytes ever reach the stream (no
    # partial print). fix5's own OWN diagnostic retry then ALSO raises
    # here (its OSError's str(e) embeds repr(marker), which itself
    # contains the marker substring again) -- write_calls therefore
    # legitimately reaches 2 (content attempt + warning-on-stdout retry,
    # both failing), forcing the genuine stderr fallback asserted below;
    # what B2 actually guarantees -- no partial content chunk ever lands
    # -- is what spy.chunks == [] proves.
    assert spy.chunks == [], f"expected zero successfully-written chunks, got {spy.chunks!r}"
    # R2-К8 (ФИКС 6 критика): write_calls was tracked but never asserted
    # on (dead field) -- now used: exactly 2 attempts (the one content
    # write via the stdout-deadline thread, plus fix5's own diagnostic
    # retry ALSO landing on the marker-carrying stream), per this test's
    # own docstring above.
    assert spy.write_calls == 2, f"expected exactly 2 write attempts, got {spy.write_calls}"

    ack_data = sc._load_break_glass_ack(sc._break_glass_ack_path(root))
    assert fact_key not in ack_data, (
        f"fact was ack'd despite the write that would have shown it failing: {ack_data!r}"
    )
    err_text = "".join(err_fake.chunks)
    assert "session-context warning:" in err_text


# ==== B19: closing counts always match what was actually printed ============
# R2-К3 (ФИКС 2 критика): сверка ПРОТИВ st_size запрещена явно -- это была
# ровно та тавтология (st_size сверялся с подвалом, который ТОЖЕ был
# посчитан от st_size, ФИКС 1). Этот тест теперь парсит СОБСТВЕННЫЙ
# возврат функции по блокам BEGIN/END и считает байты от САМИХ строк
# содержимого (len(line) + 1 на строку, зеркально emitted_bytes внутри
# layer_a_lines()) -- os.stat() здесь не участвует вовсе.


def test_b19_closing_line_counts_match_actual_emitted_content(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root, skip={"PROJECT_PHILOSOPHY.md"})
    lines = sc.layer_a_lines(root)
    footer = lines[-1]
    m = re.match(r"--- END BOOT LAYER A: (\d+) files, (\d+) lines, (\d+) bytes emitted ---", footer)
    assert m, f"footer did not match the expected shape: {footer!r}"
    files_n, lines_n, bytes_n = (int(x) for x in m.groups())

    begin_count = sum(1 for l in lines if l.startswith("----- BEGIN "))
    assert files_n == begin_count

    content_line_total = 0
    content_byte_total = 0
    in_block = False
    for l in lines:
        if l.startswith("----- BEGIN "):
            in_block = True
            continue
        if l.startswith("----- END "):
            in_block = False
            continue
        if in_block:
            content_line_total += 1
            content_byte_total += len(l) + 1
    assert lines_n == content_line_total
    # R2-К3: parsed from the OWN emitted stream, NOT from os.stat() --
    # this is the actual regression guard against the footer silently
    # reverting to st_size (it would still equal content_byte_total on
    # THIS specific fixture only by the class B24/B25 name explicitly).
    assert bytes_n == content_byte_total


# ==== B24/B25 (R2-К2/R2-К3): footer bytes DIVERGE from on-disk st_size ======
# on real CRLF/transliterated content -- the positive proof the footer is
# no longer the st_size tautology ФИКС 1/2 named. Seeded via explicit
# write_bytes (not _seed_layer_a_files' helper) so ONLY the file under
# test carries the divergent content; the other four are the portable,
# LF-only placeholder from _seed_layer_a_files (see its own docstring).


def _footer_bytes(lines) -> int:
    footer = lines[-1]
    m = re.match(r"--- END BOOT LAYER A: (\d+) files, (\d+) lines, (\d+) bytes emitted ---", footer)
    assert m, f"footer did not match the expected shape: {footer!r}"
    return int(m.group(3))


def test_b24_crlf_content_footer_bytes_diverge_from_on_disk_size(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    # 3 CRLF pairs -- splitlines() treats \r\n as ONE break (\r stripped,
    # never reaches the footer's per-line count), so on-disk carries 3
    # bytes (one \r each) the footer does not.
    (root / "ANTI_GOALS.md").write_bytes(b"line1\r\nline2\r\nline3\r\n")
    lines = sc.layer_a_lines(root)
    bytes_n = _footer_bytes(lines)
    on_disk_total = sum((root / n).stat().st_size for n in sc._LAYER_A_FILES)
    assert bytes_n != on_disk_total
    assert on_disk_total - bytes_n == 3


def test_b25_transliterated_content_footer_bytes_diverge_from_on_disk_size(tmp_path):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root)
    # One em dash: 3 UTF-8 bytes on disk, translit table maps it to "--"
    # (2 ASCII bytes emitted) -- delta of exactly 1 byte for this file.
    (root / "README.md").write_bytes("a — b\n".encode("utf-8"))
    lines = sc.layer_a_lines(root)
    bytes_n = _footer_bytes(lines)
    on_disk_total = sum((root / n).stat().st_size for n in sc._LAYER_A_FILES)
    assert bytes_n != on_disk_total
    assert on_disk_total - bytes_n == 1


# ==== B20-B23 (R2-К1): stdout write deadline ================================
# Real OS pipes (os.pipe()), NOT mocks -- the critic's own measured class
# ("недренирующий потребитель" hangs a single write() past ~4096 B on this
# machine) only exists at the real-OS level; a Python-level fake stream
# cannot reproduce the actual blocking syscall. _write_stdout_deadline()
# itself is tested in-process here (never calls os._exit() -- only its
# CALLER in main() does, see the separate subprocess-level negative
# control below for that full end-to-end path).


def _make_blocking_pipe_writer():
    """A real OS pipe, unbuffered enough to reproduce the critic's own
    measured capacity class: the read end is returned UNDRAINED -- a
    caller writing more than the OS's pipe buffer to the write end will
    have that write() block inside the kernel until either something
    reads, or (this batch's whole point) a deadline gives up waiting."""
    read_fd, write_fd = os.pipe()
    reader = os.fdopen(read_fd, "r", encoding="utf-8", newline="")
    writer = os.fdopen(write_fd, "w", encoding="utf-8", newline="")
    return reader, writer


def _best_effort_release_pipe(reader, writer):
    """Cleanup for a pipe that may still have a daemon writer-thread
    blocked inside the OS on the other end (B20/B23): closing the READ
    end first typically breaks the pending write with a broken-pipe
    error, letting the still-alive daemon thread actually finish and
    release its fd. Nothing here is asserted -- daemon=True already
    guarantees a leftover blocked thread cannot hang the suite even if
    this best-effort release does not work on some platform."""
    try:
        reader.close()
    except Exception:
        pass
    time.sleep(0.05)
    try:
        writer.close()
    except Exception:
        pass


def test_b20_non_draining_consumer_write_returns_false_within_deadline(monkeypatch):
    """B20: a non-draining consumer (real OS pipe, read end never
    touched) past the pipe's capacity -- _write_stdout_deadline() must
    return False (not hang) once the deadline elapses. The DEADLINE ends
    the wait, not the consumer."""
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(sc.sys, "stdout", writer)
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "0.3")
    big_text = "x" * 200_000  # comfortably over the measured ~4096 B pipe capacity
    t0 = time.monotonic()
    result = sc._write_stdout_deadline(big_text)
    elapsed = time.monotonic() - t0
    assert result is False
    assert 0.25 <= elapsed < 1.3, f"should return within deadline+margin, took {elapsed:.3f}s"
    _best_effort_release_pipe(reader, writer)


def test_b21_draining_consumer_returns_true_full_content_delivered(monkeypatch):
    """B21: a draining consumer (a real reader thread continuously
    reading the OTHER end of the same real pipe) -- ordinary path,
    True, and the FULL text arrives byte for byte."""
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(sc.sys, "stdout", writer)
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "3.0")
    big_text = "y" * 200_000
    collected = []

    def _drain():
        while True:
            chunk = reader.read(65536)
            if not chunk:
                break
            collected.append(chunk)

    drainer = threading.Thread(target=_drain, daemon=True)
    drainer.start()
    result = sc._write_stdout_deadline(big_text)
    assert result is True
    writer.close()  # EOF -- lets the drainer thread's read() loop end
    drainer.join(timeout=5)
    assert not drainer.is_alive(), "drainer thread did not see EOF in time"
    assert "".join(collected) == big_text
    reader.close()


@pytest.mark.parametrize(
    "raw_value,expected",
    [
        ("", sc._STDOUT_DEADLINE_DEFAULT),
        ("abc", sc._STDOUT_DEADLINE_DEFAULT),
        ("0", sc._STDOUT_DEADLINE_DEFAULT),
        ("-1", sc._STDOUT_DEADLINE_DEFAULT),
        ("601", sc._STDOUT_DEADLINE_DEFAULT),
        ("600", 600.0),
        ("0.1", 0.1),
        ("5", 5.0),
    ],
)
def test_b22_env_deadline_parsing_branches(raw_value, expected, monkeypatch):
    """B22: нечисловое/0/отрицательное/>MAX -> дефолт (те же правила, что
    у stdin-хелпера's own _stdin_deadline_seconds())."""
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, raw_value)
    assert sc._stdout_deadline_seconds() == expected


def test_b22_env_absent_uses_default(monkeypatch):
    monkeypatch.delenv(sc._STDOUT_DEADLINE_ENV, raising=False)
    assert sc._stdout_deadline_seconds() == sc._STDOUT_DEADLINE_DEFAULT == 5.0


def test_b23_small_valid_deadline_blocking_write_returns_false(monkeypatch):
    """B23: a valid SMALL deadline (0.1s) against a guaranteed-blocking
    write -- exits by the deadline, reproducibly (bounded, well under a
    full second)."""
    reader, writer = _make_blocking_pipe_writer()
    monkeypatch.setattr(sc.sys, "stdout", writer)
    monkeypatch.setenv(sc._STDOUT_DEADLINE_ENV, "0.1")
    big_text = "z" * 200_000
    t0 = time.monotonic()
    result = sc._write_stdout_deadline(big_text)
    elapsed = time.monotonic() - t0
    assert result is False
    assert elapsed < 1.0, f"a 0.1s deadline should return well under 1s, took {elapsed:.3f}s"
    _best_effort_release_pipe(reader, writer)


# ==== R2-К1 DoD witness: full main()-level negative control, subprocess ====
# In-process tests above prove _write_stdout_deadline() itself; THIS test
# proves the full main()-level wiring -- os._exit(0) actually terminates
# the PROCESS on a genuinely undrained real OS pipe, not just that the
# helper function returns False. BEFORE this batch's fix, this exact
# probe (run against this very file, pre-edit, on this tree) blocked
# >8s with no exit; captured verbatim in the builder's report.


def test_negative_control_subprocess_undraining_consumer_exits_within_deadline():
    # Twin-mode script resolution (same rationale as the module's own
    # try/except import above): the sibling exists BEFORE posting; AFTER
    # Lead lands it and deletes the sibling, this falls back to the LIVE
    # (by then identical-content) tools/session_context.py -- a hardcoded
    # sibling-only path here would make this exact test the THING that
    # breaks post-landing (found empirically while building this batch's
    # own landing-simulation witness -- see the builder's report).
    tools_dir = Path(__file__).resolve().parent
    sibling = tools_dir / "session_context_layer_a.py"
    script = sibling if sibling.exists() else tools_dir / "session_context.py"
    env = os.environ.copy()
    env["OSLLM_STDOUT_TIMEOUT"] = "1.0"
    proc = subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    # stdin is fed a small payload and closed immediately -- isolates this
    # from the SEPARATE stdin-deadline machinery (test_p4_stdin_deadline.py
    # owns that axis); stdout is the pipe under test and is NEVER read
    # before proc.wait() returns, by design.
    proc.stdin.write(json.dumps({"source": "startup"}).encode("utf-8"))
    proc.stdin.close()
    t0 = time.monotonic()
    rc = proc.wait(timeout=6.0)  # 1.0s deadline + generous margin
    elapsed = time.monotonic() - t0
    assert rc == 0
    assert elapsed < 6.0, f"took {elapsed:.3f}s"
    # ПРИВЯЗКА К ВЕТКЕ ДЕДЛАЙНА (вердикт критика t-595, фикс 3): без неё
    # тест зелен и тогда, когда запись вообще не заблокировалась (вывод
    # меньше ёмкости пайпа) -- и в этом случае он молча прогонял бы
    # БОЕВОЙ хук на БОЕВОМ корне до конца, ack'ая реальные break-glass
    # факты; безопасность пробы держалась бы на том самом свойстве
    # среды (11 КБ > 4096), которое проба и проверяет -- класс «сторож,
    # обученный молчать». Порог 0.8 * дедлайн доказывает, что выход
    # произошёл ИМЕННО по ветке дедлайна, а не обычным завершением.
    deadline = float(env["OSLLM_STDOUT_TIMEOUT"])
    assert elapsed >= 0.8 * deadline, (
        f"exited in {elapsed:.3f}s < 0.8*{deadline}s -- запись не "
        "заблокировалась, проба не проверила ветку дедлайна (вывод "
        "меньше ёмкости пайпа?)"
    )
    proc.stdout.close()
    proc.stderr.close()


# ==== M4: reads from the root PASSED to main(), never a hardcoded repo_root =


def test_m4_layer_a_reads_from_passed_root_not_repo_root(tmp_path, capsys, monkeypatch):
    root = _seed_repo(tmp_path)
    _seed_layer_a_files(root, contents={"README.md": "custom marker unique xyz\n"})
    code, out = _run_main_startup(root, monkeypatch, capsys)
    assert code == 0
    assert "custom marker unique xyz" in out

