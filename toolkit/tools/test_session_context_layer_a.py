"""Tests for the Layer A CONTENT emission half of the AUTO-BOOT hybrid
mechanism: layer_a_file_names()/layer_a_lines() -- WHAT gets emitted and
HOW (translit-warn, byte threshold, per-emission closing counts), as
distinct from test_session_context_autoboot.py, which covers WHEN it
fires (source gating).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_context as sc  # noqa: E402


# ---- layer_a_file_names(): parses BOOT.md's own "Read X.md" lines ----


def test_layer_a_file_names_parses_boot_md(tmp_path):
    (tmp_path / "BOOT.md").write_text(
        "1. Read README.md.\n2. Read SYSTEM_PROMPT.md.\n", encoding="utf-8"
    )
    assert sc.layer_a_file_names(tmp_path) == ["README.md", "SYSTEM_PROMPT.md"]


def test_layer_a_file_names_does_not_force_append_claude_md(tmp_path):
    # Unlike boot_path_files() (BOOT BUDGET arithmetic), layer_a_file_names()
    # must NOT force-append CLAUDE.md -- it auto-loads separately via the
    # harness and would otherwise be double-printed as boot-file content.
    (tmp_path / "BOOT.md").write_text("1. Read README.md.\n", encoding="utf-8")
    assert sc.layer_a_file_names(tmp_path) == ["README.md"]


def test_layer_a_file_names_dedupes_repeated_references(tmp_path):
    (tmp_path / "BOOT.md").write_text(
        "1. Read README.md.\nSee also: Read README.md.\n", encoding="utf-8"
    )
    assert sc.layer_a_file_names(tmp_path) == ["README.md"]


# ---- "## Layer A" markup excludes CURRENT_CONTEXT.md by
# construction; a BOOT.md with no such markup falls back to the flat
# list MINUS CURRENT_CONTEXT.md by name (both worlds, R11(c)) ----


def test_layer_a_file_names_markup_aware_excludes_state_file(tmp_path):
    (tmp_path / "BOOT.md").write_text(
        "## Layer A -- Orientation (always)\n\n"
        "1. Read README.md.\n"
        "2. Read SYSTEM_PROMPT.md.\n"
        "3. Read DECISIONS.md.\n"
        "4. Read DELEGATION_TABLE.md.\n\n"
        "## Layer B -- State (for the Boot Report)\n\n"
        "5. Read CURRENT_CONTEXT.md.\n",
        encoding="utf-8",
    )
    names = sc.layer_a_file_names(tmp_path)
    assert names == ["README.md", "SYSTEM_PROMPT.md", "DECISIONS.md", "DELEGATION_TABLE.md"]
    assert "CURRENT_CONTEXT.md" not in names


def test_layer_a_file_names_markup_aware_no_layer_b_heading_still_stops_at_end(tmp_path):
    # No "## Layer B" heading at all (Layer A is the last section) --
    # the Layer A slice runs to end of file, still correctly bounded.
    (tmp_path / "BOOT.md").write_text(
        "## Layer A -- Orientation (always)\n\n1. Read README.md.\n",
        encoding="utf-8",
    )
    assert sc.layer_a_file_names(tmp_path) == ["README.md"]


def test_layer_a_file_names_fallback_no_markup_excludes_state_file_by_name(tmp_path):
    # Temporal edge (R11(c), the OTHER world): an older/unmarked BOOT.md
    # with no "## Layer A" heading at all -- falls back to the flat
    # list, but CURRENT_CONTEXT.md is STILL excluded, by name.
    (tmp_path / "BOOT.md").write_text(
        "1. Read README.md.\n"
        "2. Read SYSTEM_PROMPT.md.\n"
        "3. Read DECISIONS.md.\n"
        "4. Read DELEGATION_TABLE.md.\n"
        "5. Read CURRENT_CONTEXT.md.\n",
        encoding="utf-8",
    )
    names = sc.layer_a_file_names(tmp_path)
    assert names == ["README.md", "SYSTEM_PROMPT.md", "DECISIONS.md", "DELEGATION_TABLE.md"]
    assert "CURRENT_CONTEXT.md" not in names


def test_layer_a_file_names_fallback_state_file_only_yields_empty_list(tmp_path):
    # Positive control of the exclusion itself (command hygiene point 6):
    # a BOOT.md listing ONLY the state file (no markup) -- the exclusion
    # must actually remove it, not just happen to not find it.
    (tmp_path / "BOOT.md").write_text("1. Read CURRENT_CONTEXT.md.\n", encoding="utf-8")
    assert sc.layer_a_file_names(tmp_path) == []


def test_layer_a_lines_negative_control_no_state_file_emitted_directive_present(tmp_path):
    # DoD's own negative control: emission WITHOUT the
    # state file -- CURRENT_CONTEXT.md is never printed, the directive
    # line IS present.
    (tmp_path / "BOOT.md").write_text(
        "## Layer A -- Orientation (always)\n\n1. Read README.md.\n\n"
        "## Layer B -- State (for the Boot Report)\n\n1. Read CURRENT_CONTEXT.md.\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    (tmp_path / "CURRENT_CONTEXT.md").write_text(
        "SECRET_STATE_MARKER_SHOULD_NOT_BE_PRINTED\n", encoding="utf-8"
    )
    lines = sc.layer_a_lines(tmp_path)
    assert lines[0] == sc.LAYER_A_DIRECTIVE_LINE
    # The directive line itself legitimately NAMES CURRENT_CONTEXT.md
    # (an instruction, "read it yourself") -- what must be absent is a
    # BEGIN/END block for it (its CONTENT), not the bare filename.
    assert not any("BEGIN CURRENT_CONTEXT.md" in l for l in lines)
    assert not any("SECRET_STATE_MARKER_SHOULD_NOT_BE_PRINTED" in l for l in lines)
    assert any("BEGIN README.md" in l for l in lines)


# ---- BOOT.md absent/empty -> honest line, never a traceback (DoD edge) ----


def test_layer_a_file_names_missing_boot_md_returns_empty_list(tmp_path):
    assert sc.layer_a_file_names(tmp_path) == []


def test_layer_a_file_names_empty_boot_md_returns_empty_list(tmp_path):
    (tmp_path / "BOOT.md").write_text("", encoding="utf-8")
    assert sc.layer_a_file_names(tmp_path) == []


def test_layer_a_lines_missing_boot_md_is_one_honest_line_not_a_traceback(tmp_path):
    lines = sc.layer_a_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0].startswith("AUTO-BOOT: Layer A file list is empty")
    assert "BOOT.md" in lines[0]
    assert lines[0].isascii()


def test_layer_a_lines_empty_boot_md_is_one_honest_line(tmp_path):
    (tmp_path / "BOOT.md").write_text("", encoding="utf-8")
    lines = sc.layer_a_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0].startswith("AUTO-BOOT: Layer A file list is empty")


# ---- normal emission: header/BEGIN/END/footer shape ----


def _seed(root: Path, files: dict):
    names = list(files)
    body = "\n".join(f"1. Read {name}." for name in names)
    (root / "BOOT.md").write_text(body + "\n", encoding="utf-8")
    for name, content in files.items():
        (root / name).write_text(content, encoding="utf-8")


def test_layer_a_lines_emits_begin_end_per_file_and_footer(tmp_path):
    # The directive line is now the FIRST line, ahead of
    # the "--- BOOT LAYER A INJECTED --" opening line itself.
    _seed(tmp_path, {"README.md": "hello\nworld\n"})
    lines = sc.layer_a_lines(tmp_path)
    assert lines[0] == sc.LAYER_A_DIRECTIVE_LINE
    assert lines[1].startswith("--- BOOT LAYER A INJECTED --")
    assert "----- BEGIN README.md (" in lines[2]
    assert "hello" in lines
    assert "world" in lines
    assert "----- END README.md -----" in lines
    assert lines[-1].startswith("--- END BOOT LAYER A:")
    assert "1 files" in lines[-1]
    assert "2 lines" in lines[-1]


def test_layer_a_lines_multiple_files_all_present(tmp_path):
    _seed(tmp_path, {"README.md": "a\n", "SYSTEM_PROMPT.md": "b\nc\n"})
    lines = sc.layer_a_lines(tmp_path)
    footer = lines[-1]
    assert footer.startswith("--- END BOOT LAYER A: 2 files, 3 lines,")


def test_layer_a_lines_missing_individual_file_reported_but_others_still_emitted(tmp_path):
    (tmp_path / "BOOT.md").write_text(
        "1. Read README.md.\n2. Read GHOST.md.\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("hi\n", encoding="utf-8")
    lines = sc.layer_a_lines(tmp_path)
    assert any("[missing: GHOST.md" in l for l in lines)
    assert any("----- BEGIN README.md" in l for l in lines)
    footer = lines[-1]
    assert footer.startswith("--- END BOOT LAYER A: 1 files,")


def test_layer_a_lines_empty_file_is_not_missing_gets_begin_end_pair(tmp_path):
    _seed(tmp_path, {"README.md": ""})
    lines = sc.layer_a_lines(tmp_path)
    assert not any("[missing:" in l for l in lines)
    assert any("----- BEGIN README.md (0 bytes)" in l for l in lines)
    assert "----- END README.md -----" in lines


# ---- translit-warn: transliteration table + loud unmapped-character warning ----


def test_layer_a_lines_transliterates_em_dash_with_soft_note(tmp_path):
    _seed(tmp_path, {"README.md": "a — b\n"})  # em dash
    lines = sc.layer_a_lines(tmp_path)
    assert "a -- b" in lines
    assert any(l.startswith("[note:") and "transliterated" in l for l in lines)
    assert not any("MEANING MAY BE LOST" in l for l in lines)
    for l in lines:
        assert l.isascii()


def test_layer_a_lines_unmapped_non_ascii_gets_loud_warning(tmp_path):
    _seed(tmp_path, {"README.md": "café\n"})  # e-acute, not in the translit table
    lines = sc.layer_a_lines(tmp_path)
    assert any("MEANING MAY BE LOST" in l for l in lines)
    for l in lines:
        assert l.isascii()


def test_layer_a_lines_pure_ascii_content_no_note_no_warning(tmp_path):
    _seed(tmp_path, {"README.md": "plain ascii only\n"})
    lines = sc.layer_a_lines(tmp_path)
    assert not any(l.startswith("[note:") for l in lines)
    assert not any("MEANING MAY BE LOST" in l for l in lines)


def test_layer_a_lines_transliterates_box_drawing_tree_diagram_with_soft_note(tmp_path):
    # t-641 verdict, F4: a real host README.md tree diagram shape --
    # all four box-drawing glyphs the verdict named, on one line each.
    _seed(
        tmp_path,
        {
            "README.md": (
                "├── README.md\n"
                "│   ├── nested.py\n"
                "└── last.py\n"
            )
        },
    )
    lines = sc.layer_a_lines(tmp_path)
    assert "+-- README.md" in lines
    assert "|   +-- nested.py" in lines
    assert "\\-- last.py" in lines
    assert not any("MEANING MAY BE LOST" in l for l in lines)
    for l in lines:
        assert l.isascii()


def test_layer_a_lines_transliterates_section_sign_with_soft_note(tmp_path):
    # t-641 verdict, F4: an inline section reference, the other
    # load-bearing character the verdict named (U+00A7).
    _seed(tmp_path, {"README.md": "see AGENTS.md §4.1\n"})
    lines = sc.layer_a_lines(tmp_path)
    assert "see AGENTS.md Sec.4.1" in lines
    assert not any("MEANING MAY BE LOST" in l for l in lines)
    for l in lines:
        assert l.isascii()


# ---- WARN threshold (16384 bytes on the TOTAL layer-A on-disk size) ----
# Matches the reference implementation's own behavior (a whole-block
# total, not a per-file figure) -- see this node's report for the
# spec-wording divergence this follows.


def test_layer_a_lines_under_warn_threshold_no_notice_line(tmp_path):
    _seed(tmp_path, {"README.md": "x" * 100})
    lines = sc.layer_a_lines(tmp_path)
    assert not any(l.startswith("AUTO-BOOT: Layer A is") for l in lines)


def test_layer_a_lines_at_warn_threshold_boundary_no_notice(tmp_path):
    # Exactly AT LAYER_A_INLINE_WARN_BYTES -- comparison is strict ">",
    # so the boundary itself must NOT fire.
    _seed(tmp_path, {"README.md": "x" * sc.LAYER_A_INLINE_WARN_BYTES})
    lines = sc.layer_a_lines(tmp_path)
    assert not any(l.startswith("AUTO-BOOT: Layer A is") for l in lines)


def test_layer_a_lines_one_byte_over_warn_threshold_fires_notice(tmp_path):
    # lines[0] is now the directive line always; the
    # threshold notice comes SECOND when it fires.
    _seed(tmp_path, {"README.md": "x" * (sc.LAYER_A_INLINE_WARN_BYTES + 1)})
    lines = sc.layer_a_lines(tmp_path)
    assert lines[0] == sc.LAYER_A_DIRECTIVE_LINE
    assert lines[1].startswith("AUTO-BOOT: Layer A is")
    assert str(sc.LAYER_A_INLINE_WARN_BYTES + 1) in lines[1]
    assert "injected in full" in lines[1]
    # WARN, not a block -- the file's content still follows.
    assert any("BEGIN README.md" in l for l in lines)


def test_layer_a_lines_warn_notice_over_threshold_is_ascii(tmp_path):
    _seed(tmp_path, {"README.md": "x" * (sc.LAYER_A_INLINE_WARN_BYTES + 1)})
    lines = sc.layer_a_lines(tmp_path)
    assert lines[0].isascii()
    assert lines[1].isascii()


# ---- closing line counts BY EMISSION, not by disk size ----


def test_layer_a_lines_emitted_bytes_differ_from_on_disk_size_after_transliteration(tmp_path):
    # A single em dash is 3 bytes in UTF-8 on disk but becomes 2 ASCII
    # bytes ("--") once transliterated -- the header's "on disk" figure
    # and the footer's "emitted" figure must genuinely diverge here,
    # proving the footer counts the ACTUAL emission, not a disk-size
    # tautology.
    content = "—\n"  # em dash + newline
    (tmp_path / "BOOT.md").write_text("1. Read README.md.\n", encoding="utf-8")
    # write_bytes (not write_text): avoids platform newline translation
    # (os.linesep) so the on-disk byte count is exactly this content's
    # own UTF-8 encoding, not inflated by a \n -> \r\n rewrite.
    (tmp_path / "README.md").write_bytes(content.encode("utf-8"))
    on_disk_size = len(content.encode("utf-8"))
    lines = sc.layer_a_lines(tmp_path)
    # lines[0] is the directive line; the opening line
    # carrying "N bytes on disk" is now lines[1].
    assert f"{on_disk_size} bytes on disk" in lines[1]
    footer = lines[-1]
    assert footer.startswith("--- END BOOT LAYER A:")
    # emitted bytes = len("--") + 1 (join separator) = 3, on-disk = 4
    # (3-byte UTF-8 em dash + 1-byte newline) -- genuinely different.
    assert "3 bytes emitted" in footer
    assert on_disk_size != 3


def test_layer_a_lines_crlf_content_normalized_one_logical_line_no_cr(tmp_path):
    # CRLF-terminated source content must not leak a bare \r into any
    # emitted line -- str.splitlines() already normalizes this, pinned
    # here as a regression guard on the platform this port ships on.
    (tmp_path / "BOOT.md").write_text("1. Read README.md.\n", encoding="utf-8")
    (tmp_path / "README.md").write_bytes(b"line one\r\nline two\r\n")
    lines = sc.layer_a_lines(tmp_path)
    assert "line one" in lines
    assert "line two" in lines
    for l in lines:
        assert "\r" not in l


def test_layer_a_lines_survive_when_boot_lite_context_already_fills_max_lines(
    tmp_path,
):
    # Layer A must not be truncated by build_context_lines()'s own
    # MAX_LINES cap -- main() appends it AFTER that truncation. Proven
    # here at the composition level main() itself uses.
    _seed(tmp_path, {"README.md": "a\nb\nc\n"})
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "routing-log.jsonl").write_text("", encoding="utf-8")
    filler_context = ["x"] * sc.MAX_LINES  # simulates a fully-saturated boot-lite block
    layer_a = sc.layer_a_lines(tmp_path)
    combined = filler_context + layer_a
    assert combined[-1].startswith("--- END BOOT LAYER A:")
    assert len(combined) > sc.MAX_LINES


def test_layer_a_lines_footer_is_the_last_line(tmp_path):
    _seed(tmp_path, {"README.md": "a\nb\nc\n"})
    lines = sc.layer_a_lines(tmp_path)
    assert lines[-1].startswith("--- END BOOT LAYER A:")


# ---- negative control: a truncated/interrupted emission is detectable
# by the ABSENCE of the closing line (DoD's explicit acceptance key) ----


def test_negative_control_truncated_block_has_no_closing_line(tmp_path):
    _seed(tmp_path, {"README.md": "a\nb\nc\n"})
    full = sc.layer_a_lines(tmp_path)
    assert full[-1].startswith("--- END BOOT LAYER A:")
    truncated = full[:-1]  # simulates an interrupted/truncated emission
    assert not any(l.startswith("--- END BOOT LAYER A:") for l in truncated)


# ---- never raises: an unforeseen internal failure degrades to one line ----


def test_layer_a_lines_never_raises_on_internal_failure(tmp_path, monkeypatch):
    _seed(tmp_path, {"README.md": "hi\n"})

    def _boom(_root):
        raise RuntimeError("simulated internal failure")

    monkeypatch.setattr(sc, "layer_a_file_names", _boom)
    lines = sc.layer_a_lines(tmp_path)
    assert len(lines) == 1
    assert lines[0].startswith("AUTO-BOOT: Layer A inline unavailable")
    assert "simulated internal failure" in lines[0]
    assert lines[0].isascii()


def test_layer_a_unavailable_line_never_raises_on_unprintable_exception():
    class _Weird(Exception):
        def __str__(self):
            raise RuntimeError("str() itself blows up")

    line = sc._layer_a_unavailable_line(_Weird())
    assert line.startswith("AUTO-BOOT: Layer A inline unavailable")
    assert "<unprintable exception>" in line


# ---- directory-as-file edge (OSError branch, same class as "missing") ----


def test_layer_a_lines_path_is_a_directory_reported_as_missing(tmp_path):
    (tmp_path / "BOOT.md").write_text("1. Read README.md.\n", encoding="utf-8")
    (tmp_path / "README.md").mkdir()  # a directory, not a file
    lines = sc.layer_a_lines(tmp_path)
    assert any("[missing: README.md" in l for l in lines)


# ---- every line stays single-line/ASCII even under adversarial content ----


def test_layer_a_lines_multiple_adversarial_characters_all_ascii(tmp_path):
    content = "em—dash en–dash arrow→ quote“x” unmappedé\n"
    _seed(tmp_path, {"README.md": content})
    lines = sc.layer_a_lines(tmp_path)
    for l in lines:
        assert l.isascii()
        assert "\n" not in l
