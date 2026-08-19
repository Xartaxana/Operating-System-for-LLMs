"""Battery for tools/md_regions.py (t-507, docs/tasks/2026-08-19_md-regions-scanner-spec.md,
"СПЕКА A -- модуль (этап 1)"). Module NOT yet imported by any consumer
(stage 2, separate dispatch) -- this file is the module's only test.

Run: python -m pytest tools/test_md_regions.py -q

Structure (DoD keys 1-5 of the spec's section 8, mapped to test groups
below by a comment marker "KEY N"):
  KEY 1 -- поверхность-пин (A1): dir() pin + reserved-kinds pin.
  KEY 2 -- инварианты A2: coverage, offsets/CRLF-CR-BOM, nesting stack,
           pure function -- one test group per invariant.
  KEY 3 -- края §5, поимённо: edge_a..edge_zh (Cyrillic а/б/в/д/е/ж
           transliterated a/b/v/d/e/zh in test names).
  KEY 4 -- лимиты, два теста на каждый (at the boundary / over it).
  KEY 5 -- батарея §6 (module part) + perf measurement (witness for the
           DoD's "полный scan 1 МБ <= 150 мс" budget).
Plus: A3 CommonMark-lite recognition/deviation pins, A5 fail-open cases,
kind_at()/line_kinds() dedicated tests.
"""

from __future__ import annotations

import time

import md_regions as mdr


def _coverage(text, result):
    """Concatenation of result.regions' slices, in order."""
    return "".join(text[r.start:r.end] for r in result.regions)


# ===================================================================
# KEY 1 -- поверхность-пин (A1)
# ===================================================================


def test_public_api_surface_is_facts_only():
    """Дословный список dir() (не-подчёркнутые имена). Новое публичное
    имя (should_ignore/is_quoted_claim/SILENCE_KINDS/любая политика)
    меняет этот список и валит тест -- детектор "в сканер поехала
    политика" (A1)."""
    expected = [
        "KIND_BLOCKQUOTE",
        "KIND_EMBEDDED_DOC",
        "KIND_FENCED",
        "KIND_INLINE_CODE",
        "KIND_NOTES",
        "KIND_PROSE",
        "List",
        "MAX_LINE_INLINE_SPANS",
        "MAX_REGIONS",
        "MAX_TEXT_CHARS",
        "NamedTuple",
        "Optional",
        "Region",
        "ScanResult",
        "Tuple",
        "annotations",
        "bisect",
        "kind_at",
        "line_kinds",
        "re",
        "scan",
    ]
    actual = sorted(n for n in dir(mdr) if not n.startswith("_"))
    assert actual == expected


def test_region_fields_are_exactly_the_spec_a2_fields():
    assert mdr.Region._fields == (
        "start",
        "end",
        "kinds",
        "line_start",
        "line_end",
        "unterminated",
        "info",
    )
    assert mdr.ScanResult._fields == ("regions", "degraded", "reason")


CORPUS_FOR_RESERVED_KIND_SWEEP = [
    "",
    "\n",
    "plain prose",
    "a `code` b",
    "> quote\n> more\nend",
    "```lang\ncontent\n```\n",
    "> ```\nquoted fence content\n> ```\nafter\n",
    ">" * 50 + " deep",
    "```" + "`" * 300 + "\ncontent\n" + "`" * 305 + "\n",
    "| ``` | table cell |\n",
    "    4 space indented, not code\n",
    "line one\r\nline two\r\nline three",
    "a\rb\rc",
    "﻿BOM at start\ntext",
]


def test_reserved_kinds_never_returned_by_scan_v1():
    """Р2(б): KIND_NOTES/KIND_EMBEDDED_DOC существуют как константы, но
    scan() их не возвращает -- ни на одном тексте корпуса."""
    assert mdr.KIND_NOTES == "notes"
    assert mdr.KIND_EMBEDDED_DOC == "embedded_doc"
    for text in CORPUS_FOR_RESERVED_KIND_SWEEP:
        result = mdr.scan(text)
        for region in result.regions:
            assert mdr.KIND_NOTES not in region.kinds
            assert mdr.KIND_EMBEDDED_DOC not in region.kinds
        for stack in mdr.line_kinds(text):
            assert mdr.KIND_NOTES not in stack
            assert mdr.KIND_EMBEDDED_DOC not in stack


# ===================================================================
# KEY 2 -- инварианты A2 (тест на каждый)
# ===================================================================

# --- инвариант 1: полное непересекающееся покрытие ------------------

COVERAGE_CORPUS = CORPUS_FOR_RESERVED_KIND_SWEEP + [
    "```",
    ">",
    "a\U0001F600b `\U0001F600` end",
    "привет `код` мир",
    "`a` " * 200,
]


def test_invariant1_full_coverage_concatenation_equals_source():
    for text in COVERAGE_CORPUS:
        result = mdr.scan(text)
        assert _coverage(text, result) == text


def test_invariant1_regions_are_non_overlapping_and_contiguous():
    for text in COVERAGE_CORPUS:
        result = mdr.scan(text)
        prev_end = 0
        for region in result.regions:
            assert region.start == prev_end
            assert region.end >= region.start
            prev_end = region.end
        assert prev_end == len(text)


# --- инвариант 2: смещения в исходном тексте; CRLF/CR/BOM/no-\n -----


def test_invariant2_offsets_hold_across_crlf_cr_mixed_bom_no_trailing_newline():
    samples = [
        "a\r\nb\r\nc",
        "a\rb\rc",
        "﻿a\nb",
        "a\nb\nc",
        "a\r\nb\nc\r",
        "no trailing newline at all",
        "trailing newline present\n",
    ]
    for text in samples:
        result = mdr.scan(text)
        assert _coverage(text, result) == text


def test_invariant2_offsets_are_character_offsets_not_byte_offsets():
    text = "a\U0001F600b `\U0001F600` end"  # astral char outside BMP
    result = mdr.scan(text)
    assert _coverage(text, result) == text
    # region boundaries must land on the single-character positions, not
    # split a surrogate pair / multi-byte encoding
    for region in result.regions:
        assert 0 <= region.start <= len(text)
        assert 0 <= region.end <= len(text)


# --- инвариант 3: вложенность стеком снаружи внутрь ------------------


def test_invariant3_nesting_stack_outer_to_inner_blockquote_then_fenced():
    text = "> ```\n> still quoted\n> ```\nafter\n"
    result = mdr.scan(text)
    fenced = [r for r in result.regions if mdr.KIND_FENCED in r.kinds]
    assert len(fenced) == 1
    assert fenced[0].kinds == (mdr.KIND_BLOCKQUOTE, mdr.KIND_FENCED)


def test_invariant3_top_level_fence_has_no_blockquote_in_stack():
    text = "```\ncode\n```\n"
    result = mdr.scan(text)
    assert result.regions[0].kinds == (mdr.KIND_FENCED,)


# --- инвариант 4: чистая функция -------------------------------------


def test_invariant4_pure_function_same_input_same_output_no_shared_state():
    text_a = "a `code` b\n> quote\nend"
    text_b = "```\nother\n```\n"
    r_a1 = mdr.scan(text_a)
    r_b = mdr.scan(text_b)
    r_a2 = mdr.scan(text_a)
    assert r_a1 == r_a2  # interleaved call to a DIFFERENT text didn't leak state
    assert r_a1.regions == r_a2.regions


def test_invariant4_does_not_mutate_input_text_identity():
    text = "a `code` b\n> quote\nend"
    original = str(text)
    mdr.scan(text)
    assert text == original


# ===================================================================
# KEY 3 -- края §5, поимённо (a/b/v/d/e/zh)
# ===================================================================


def test_edge_a_quote_marker_inside_fence_is_not_a_quote():
    """(а) '>' внутри фенса -- цитаты нет."""
    text = "```\n> not a quote, just fence content\n```\n"
    result = mdr.scan(text)
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_FENCED,)
    assert result.regions[0].unterminated is False


def test_edge_b_fence_in_quote_closes_at_quote_end_unterminated():
    """(б) фенс в цитате -- ("blockquote","fenced"); не закрыт до конца
    цитаты -> закрывается концом цитаты, unterminated=True."""
    text = "> ```\n> line still quoted\n> another quoted line\nend of quote"
    result = mdr.scan(text)
    assert len(result.regions) == 2
    fenced_in_quote, tail_prose = result.regions
    assert fenced_in_quote.kinds == (mdr.KIND_BLOCKQUOTE, mdr.KIND_FENCED)
    assert fenced_in_quote.unterminated is True
    assert fenced_in_quote.line_start == 0
    assert fenced_in_quote.line_end == 2  # closes at the LAST quoted line
    assert tail_prose.kinds == (mdr.KIND_PROSE,)
    assert tail_prose.line_start == 3


def test_edge_v_unterminated_fence_no_verdict():
    """(в) незакрытый фенс -- модуль отдаёт unterminated, вердикта не
    выносит (нет отдельного 'verdict'/'violation' поля -- поле ровно
    то, что задано A2)."""
    text = "```python\nsome content with no closing fence"
    result = mdr.scan(text)
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.unterminated is True
    assert region.info == "python"
    assert region._fields == (
        "start", "end", "kinds", "line_start", "line_end", "unterminated", "info",
    )


def test_edge_d_inline_code_inside_prose_yields_prose_inline_prose_spans():
    """(д) инлайн внутри прозы -- спаны prose|inline_code|prose,
    покрытие держится."""
    text = "text `code` more text"
    result = mdr.scan(text)
    kinds_seq = [r.kinds for r in result.regions]
    assert kinds_seq == [
        (mdr.KIND_PROSE,),
        (mdr.KIND_INLINE_CODE,),
        (mdr.KIND_PROSE,),
    ]
    assert _coverage(text, result) == text


def test_edge_e_line_kinds_carries_only_the_block_stack_not_inline():
    """(е) line_kinds отдаёт только блочный стек, инлайн виден только
    через scan()."""
    text = "plain text\ntext with `code` here\n"
    stacks = mdr.line_kinds(text)
    assert stacks == [(), ()]  # identical -- inline code is invisible here
    scanned = mdr.scan(text)
    kinds_seq = [r.kinds for r in scanned.regions]
    # scan() DOES distinguish -- more than 2 regions because of the inline span
    assert len(kinds_seq) > 2
    assert (mdr.KIND_INLINE_CODE,) in kinds_seq


def test_edge_zh_degraded_means_all_prose_not_a_policy_verdict():
    """(ж) degraded = "всё проза" -- не политика, а отказ от разметки:
    даже реальные quote/fence-маркеры внутри схлопываются в единый
    прозаический регион на весь текст, без попытки быть "умным"."""
    inner = "> quote\n```\ncode\n```\n"
    text = inner + ("x" * (mdr.MAX_TEXT_CHARS + 1 - len(inner)))
    result = mdr.scan(text)
    assert result.degraded is True
    assert result.reason == "text_too_large"
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.kinds == (mdr.KIND_PROSE,)
    assert region.start == 0
    assert region.end == len(text)
    assert region.unterminated is False


# ===================================================================
# A3 -- CommonMark-lite распознавание, явные отступления (тест на
# каждое отступление, названное в докстринге модуля)
# ===================================================================


def test_a3_tilde_fence_equivalent_to_backtick_fence():
    text = "~~~\ncontent\n~~~\n"
    result = mdr.scan(text)
    assert result.regions[0].kinds == (mdr.KIND_FENCED,)
    assert result.regions[0].unterminated is False


def test_a3_fence_close_requires_same_char_not_mixed():
    text = "```\ncontent\n~~~\nmore\n```\n"
    result = mdr.scan(text)
    # the ~~~ line does NOT close a ``` fence -- it's just fence content;
    # the fence only closes at the final ``` line.
    assert len(result.regions) == 1
    assert result.regions[0].unterminated is False
    assert result.regions[0].line_end == 4


def test_a3_indented_4space_code_not_recognized_stays_prose():
    text = "    this looks like indented code but is not recognized\n"
    result = mdr.scan(text)
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_PROSE,)


def test_a3_inline_code_pair_broken_by_newline_stays_prose_pin():
    text = "open `here\nclose` there\n"
    result = mdr.scan(text)
    for region in result.regions:
        assert mdr.KIND_INLINE_CODE not in region.kinds
    assert _coverage(text, result) == text


def test_a3_lazy_quote_continuation_not_implemented_pin():
    """Р3(б): строка без '>' сразу заканчивает цитату -- ленивое
    продолжение (как в полном CommonMark) не реализовано, дыра
    пинуется."""
    text = "> quoted line\nlazy continuation line without marker\n"
    result = mdr.scan(text)
    quote_regions = [r for r in result.regions if mdr.KIND_BLOCKQUOTE in r.kinds]
    assert len(quote_regions) == 1
    assert quote_regions[0].line_end == 0  # quote ends at line 0, not line 1
    prose_after = [r for r in result.regions if r.kinds == (mdr.KIND_PROSE,)]
    assert any(r.line_start == 1 for r in prose_after)


def test_a3_quote_depth_not_modeled():
    text = ">> nested-looking quote line\n"
    result = mdr.scan(text)
    assert len(result.regions) == 1
    region = result.regions[0]
    assert region.kinds == (mdr.KIND_BLOCKQUOTE, mdr.KIND_PROSE)
    # the second '>' is NOT stripped -- it stays inside the prose slice
    assert region.start == 0 and region.end == len(text)


# ===================================================================
# KEY 4 -- лимиты (A4), два теста на каждый: на границе / за
# ===================================================================


def test_limit_max_text_chars_at_boundary_not_degraded():
    text = "a" * mdr.MAX_TEXT_CHARS
    result = mdr.scan(text)
    assert result.degraded is False


def test_limit_max_text_chars_over_boundary_degrades():
    text = "a" * (mdr.MAX_TEXT_CHARS + 1)
    result = mdr.scan(text)
    assert result.degraded is True
    assert result.reason == "text_too_large"
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_PROSE,)


def _inline_pair_line_text(n):
    return "`x`\n" * n


def test_limit_max_regions_at_boundary_not_degraded():
    # `x`\n repeated MAX_REGIONS//2 times -> exactly MAX_REGIONS regions
    # (inline_code, prose(newline)) alternating, never merging (different
    # kinds each time) -- see witness for the empirical derivation.
    n = mdr.MAX_REGIONS // 2
    text = _inline_pair_line_text(n)
    result = mdr.scan(text)
    assert result.degraded is False
    assert len(result.regions) == mdr.MAX_REGIONS


def test_limit_max_regions_over_boundary_degrades():
    n = mdr.MAX_REGIONS // 2 + 1
    text = _inline_pair_line_text(n)
    result = mdr.scan(text)
    assert result.degraded is True
    assert result.reason == "max_regions_exceeded"
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_PROSE,)


def _inline_pairs_one_line(k):
    return ("`a` " * k).rstrip()


def test_limit_max_line_inline_spans_at_boundary_not_degraded():
    text = _inline_pairs_one_line(mdr.MAX_LINE_INLINE_SPANS)
    result = mdr.scan(text)
    assert result.degraded is False
    code_spans = [r for r in result.regions if r.kinds == (mdr.KIND_INLINE_CODE,)]
    assert len(code_spans) == mdr.MAX_LINE_INLINE_SPANS


def test_limit_max_line_inline_spans_over_boundary_degrades():
    text = _inline_pairs_one_line(mdr.MAX_LINE_INLINE_SPANS + 1)
    result = mdr.scan(text)
    assert result.degraded is True
    assert result.reason == "max_line_inline_spans_exceeded"
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_PROSE,)


# ===================================================================
# A5 -- fail-open
# ===================================================================


def test_a5_none_and_non_str_inputs_fail_open_no_exception():
    for bad in (None, b"bytes", {"a": 1}, 12345, 3.14, ["list"], object()):
        result = mdr.scan(bad)
        assert result.regions == []
        assert result.degraded is True
        assert result.reason == "not_a_string"


def test_a5_empty_string_valid_not_degraded():
    result = mdr.scan("")
    assert result.regions == []
    assert result.degraded is False
    assert result.reason == ""


def test_a5_single_newline_is_valid_and_covers():
    result = mdr.scan("\n")
    assert result.degraded is False
    assert _coverage("\n", result) == "\n"


def test_a5_single_opening_fence_is_valid_and_covers():
    text = "```"
    result = mdr.scan(text)
    assert result.degraded is False
    assert _coverage(text, result) == text
    assert result.regions[0].unterminated is True


def test_a5_single_gt_is_valid_and_covers():
    text = ">"
    result = mdr.scan(text)
    assert result.degraded is False
    assert _coverage(text, result) == text
    assert result.regions[0].kinds == (mdr.KIND_BLOCKQUOTE, mdr.KIND_PROSE)


def test_a5_line_kinds_mirrors_fail_open_for_non_str():
    """Расширение A5 (см. докстринг модуля): line_kinds() тоже не
    роняет исключение на не-str входе -- возвращает []."""
    for bad in (None, b"bytes", {"a": 1}, 12345):
        assert mdr.line_kinds(bad) == []
    assert mdr.line_kinds("") == []


# ===================================================================
# kind_at() -- basic + out-of-range fail-open (offset dimension)
# ===================================================================


def test_kind_at_basic_lookup_matches_containing_region():
    text = "a `code` b"
    result = mdr.scan(text)
    assert mdr.kind_at(result, 0) == (mdr.KIND_PROSE,)
    assert mdr.kind_at(result, 2) == (mdr.KIND_INLINE_CODE,)
    assert mdr.kind_at(result, 7) == (mdr.KIND_INLINE_CODE,)
    assert mdr.kind_at(result, 8) == (mdr.KIND_PROSE,)


def test_kind_at_out_of_range_offset_returns_empty_tuple_boundary_and_over():
    text = "a `code` b"
    result = mdr.scan(text)
    # boundary: offset == len(text) is one PAST the last region -- no kind
    assert mdr.kind_at(result, len(text)) == ()
    # over: further out of range
    assert mdr.kind_at(result, len(text) + 100) == ()
    # negative offset
    assert mdr.kind_at(result, -1) == ()


def test_kind_at_on_empty_regions_result_returns_empty_tuple():
    result = mdr.scan("")
    assert mdr.kind_at(result, 0) == ()
    degraded_result = mdr.scan(None)
    assert mdr.kind_at(degraded_result, 0) == ()


# ===================================================================
# line_kinds() cross-check against scan()'s own block classification
# ===================================================================


def test_line_kinds_consistent_with_scan_block_stacks():
    text = "plain\n> quote1\n> quote2\nplain again\n```\ncode\n```\nafter\n"
    stacks = mdr.line_kinds(text)
    # line 0: top-level prose -> ()
    assert stacks[0] == ()
    # lines 1-2: blockquote
    assert stacks[1] == (mdr.KIND_BLOCKQUOTE,)
    assert stacks[2] == (mdr.KIND_BLOCKQUOTE,)
    # line 3: back to top-level
    assert stacks[3] == ()
    # lines 4-6: fenced
    assert stacks[4] == (mdr.KIND_FENCED,)
    assert stacks[5] == (mdr.KIND_FENCED,)
    assert stacks[6] == (mdr.KIND_FENCED,)
    # line 7: top-level again
    assert stacks[7] == ()


# ===================================================================
# KEY 5 -- батарея §6 (модульная часть)
# ===================================================================


def test_battery_1mb_opening_fences_time_not_quadratic():
    """1 МБ открывающих фенсов (время, не квадратично)."""
    text_1x = "```\n" * 250000  # 1,000,000 chars
    text_2x = "```\n" * 500000  # 2,000,000 chars == MAX_TEXT_CHARS boundary
    t0 = time.perf_counter()
    r1 = mdr.scan(text_1x)
    dt1 = time.perf_counter() - t0
    t0 = time.perf_counter()
    r2 = mdr.scan(text_2x)
    dt2 = time.perf_counter() - t0
    assert _coverage(text_1x, r1) == text_1x
    assert _coverage(text_2x, r2) == text_2x
    # non-quadratic: doubling input must not roughly quadruple the time;
    # generous margin (allow up to ~3x) to keep this robust on slow CI.
    assert dt2 < dt1 * 3 + 0.2


def test_battery_10000_backticks_in_one_line():
    """10 000 backtick в строке (лимит спанов) -- must not hang/crash,
    and must degrade (well past MAX_LINE_INLINE_SPANS)."""
    text = ("`a` " * 10000).rstrip()
    t0 = time.perf_counter()
    result = mdr.scan(text)
    dt = time.perf_counter() - t0
    assert result.degraded is True
    assert result.reason == "max_line_inline_spans_exceeded"
    assert dt < 1.0

    # a single giant backtick run at line-start IS a fence-open marker
    # (A3: any >=3 run at line start) -- no closer found -> unterminated
    # fenced region, not a crash, not a spurious span-limit trip.
    single_run_line_initial = "`" * 10000
    result2 = mdr.scan(single_run_line_initial)
    assert result2.degraded is False
    assert result2.regions[0].kinds == (mdr.KIND_FENCED,)
    assert result2.regions[0].unterminated is True

    # the same giant run NOT at line start (mid-line) is an unmatched
    # INLINE delimiter (no same-length partner) -- stays prose, no crash.
    single_run_mid_line = "x " + "`" * 10000
    result3 = mdr.scan(single_run_mid_line)
    assert result3.degraded is False
    assert result3.regions[0].kinds == (mdr.KIND_PROSE,)


def test_battery_blockquote_nesting_x50():
    text = ">" * 50 + " deep quote text"
    result = mdr.scan(text)
    assert result.degraded is False
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_BLOCKQUOTE, mdr.KIND_PROSE)
    assert _coverage(text, result) == text


def test_battery_fence_200_backticks_closed_by_199_no_and_201_yes():
    open200 = "`" * 200
    close199 = "`" * 199
    close201 = "`" * 201
    text_no = open200 + "\n" + close199 + "\n"
    text_yes = open200 + "\n" + close201 + "\n"
    r_no = mdr.scan(text_no)
    r_yes = mdr.scan(text_yes)
    assert r_no.regions[0].unterminated is True  # 199 < 200 -- does NOT close
    assert r_yes.regions[0].unterminated is False  # 201 >= 200 -- closes


def test_battery_surrogates_cyrillic_emoji_offsets():
    samples = [
        "привет `код` мир",
        "a\U0001F600b `\U0001F600` end",
        "emoji fence:\n```\n\U0001F600\U0001F601\n```\n",
    ]
    for text in samples:
        result = mdr.scan(text)
        assert _coverage(text, result) == text


def test_battery_crlf_cr_mixed_bom_no_trailing_newline():
    samples = [
        "a\r\nb\r\nc\r\n",
        "a\rb\rc",
        "﻿a\nb\nc",
        "no newline at end",
        "a\r\nb\nc\r",
    ]
    for text in samples:
        result = mdr.scan(text)
        assert _coverage(text, result) == text


def test_battery_none_bytes_dict_int_fail_open_no_traceback():
    for bad in (None, b"raw bytes", {"k": "v"}, 42):
        result = mdr.scan(bad)
        assert result == mdr.ScanResult([], True, "not_a_string")


def test_battery_fence_marker_in_table_cell_is_not_a_block_fence():
    text = "| ``` | more |\n"
    result = mdr.scan(text)
    assert len(result.regions) == 1
    assert result.regions[0].kinds == (mdr.KIND_PROSE,)


def test_battery_perf_full_scan_1mb_within_150ms_budget():
    """DoD: полный scan 1 МБ <= 150 мс (бюджет, вывод замера в witness).
    Ordinary prose text -- the representative "nothing special" 1MB
    document (see also test_battery_1mb_opening_fences_time_not_quadratic
    for the fence-heavy construction)."""
    chunk = "Some ordinary prose line of moderate length here, nothing special.\n"
    text = (chunk * (1_000_000 // len(chunk) + 1))[:1_000_000]
    assert len(text) == 1_000_000
    t0 = time.perf_counter()
    result = mdr.scan(text)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    print("md_regions perf witness: scan(1MB ordinary prose) = %.2f ms" % elapsed_ms)
    assert result.degraded is False
    assert _coverage(text, result) == text
    assert elapsed_ms <= 150.0
