r"""md_regions.py -- markdown-text region scanner: FACTS, not verdicts.

Class of problem this closes: a guard cannot tell an author's own
claim from quoted/nested content -- several guards (negative_lint,
claim_control_gate, owns_gate and others) regex-scan the RAW dispatch
text for markers/patterns without distinguishing "this is the
author's own claim" from "this sits inside a quote/fence/inline code
belonging to someone else's text". Design choice: a shared region
SCANNER -- yes (one source of facts, "which chunk of text is in which
region"); a shared POLICY -- no (what counts as a violation / what to
ignore is each guard's own call, that is its semantics, not the
scanner's).

STAGE 1: this module and its tests. The module is imported by NO
consumer until stage 2 lands its first consumer (negative_lint /
claim_control_gate integration -- a separate dispatch); until then the
module sits outside the mechanism net -- a mechanism-gate entry is
only warranted once a first consumer actually lands.

CONTRACT (A1): the public surface is FACTS ONLY. Kind constants
(KIND_*), the Region type, ScanResult, the scan()/line_kinds()/
kind_at() functions, limit constants (MAX_*). NO should_ignore/
is_quoted_claim/SILENCE_KINDS/policy names -- if a future edit ever
wants to add such a name to this file, that is a SIGNAL that a guard's
policy has leaked into the scanner, not a fact about a region;
test_public_api_surface_is_facts_only (a verbatim dir() pin) catches
this on EVERY new public name.

RESERVED KINDS: KIND_NOTES / KIND_EMBEDDED_DOC exist as constants (for
a future v2 -- notes/embedded documents as their own region kinds),
but scan() NEVER returns them in v1 -- pinned by
test_reserved_kinds_never_returned_by_scan_v1.

TWO EXISTING FENCE PARSERS -- DO NOT TOUCH, DO NOT ADD A THIRD:
tools/escape_check.py::extract_fenced_block -- statuses
ok/not_found/duplicate/empty/unterminated, its semantics pinned by its
own battery (tools/test_escape_check.py); tools/
critic_verdict_check.py::_FENCE_RE -- a one-line regex for the LAST
```json...``` fence, also pinned by its own test. Both solve a
NARROWER, different-shaped problem (extract ONE specific block by
marker/language), not "split the whole text into regions" -- this
module does not replace or migrate either of them.

FUTURE CONSUMER IMPORT (informational, stage 1 does not touch it --
the module itself imports only stdlib): the try/package, except/
sibling-module pattern used across this tool set:

    try:
        from tools.md_regions import scan, kind_at  # package-style
    except ImportError:
        from md_regions import scan, kind_at  # sibling-module fallback

RULE #1 -- OVERKILL ZONE: "the guard's input is a single line or a
structural field -> the scanner does NOT apply; it is only warranted
on multi-line author-written text". NON-consumers (the scanner is not
needed here and never will be): hygiene_gate (only checks shell
quoting, that class is closed), search_control_gate,
journal_echo/journal_validator, the closes:-token (out of class -- a
different surface entirely). Calling the scanner on a single-line/
structural field is not this problem, it is an unwarranted call.

FAIL-OPEN (A5): scan(None) / scan(<non-str>) -> ScanResult([], True,
"not_a_string") with NO exception; scan("") -> ScanResult([], False,
""). line_kinds() mirrors the same contract on its input (non-str ->
[] with no exception) -- this EXTENDS A5 past its literal wording
(which only talks about scan()), done for consistency: both functions
take the same "raw untrusted text" as their first argument, and a
silent traceback crash on line_kinds(None) would break the same
"never crash on broken input" contract A5 explicitly demands of
scan(). kind_at(result, offset) is a DIFFERENT case -- its FIRST
argument is already a built ScanResult (not raw text), it carries no
untrusted-input contract -- kind_at(None, 0) and similar garbage in
`result` CRASH as an ordinary call error (a bug in the caller, not an
input-text-parsing case). The one thing kind_at DOES keep fail-open on
is an OFFSET outside range (negative, past the text's length, exactly
at the end boundary of the last region): it returns () -- "kind
unknown", not an exception (tested both directions).

The module does NOT catch exceptions beyond the specifically stated
list in A5 (non-str input to scan()/line_kinds(), out-of-range offset
to kind_at()) -- if a valid str input triggers an internal exception,
that is a bug IN THE MODULE, not a sanctioned fail-open path. The
consumer (stage 2) wraps its own call to the scanner in its own
try/except -- invariant I-0 of the design: "any module failure ->
the guard behaves EXACTLY as it does today, byte for byte".

DEGRADATION (A4): once any of the three limits (MAX_TEXT_CHARS,
MAX_REGIONS, MAX_LINE_INLINE_SPANS) is exceeded, the whole result
collapses into ONE region covering the WHOLE text, kinds=(KIND_PROSE,),
degraded=True, reason=<specific cause>. This is "what a guard sees
today" (the whole text is prose, nothing is marked up) -- degradation
does NOT widen any silence zone (the guard still sees the whole text
and decides for itself), it only turns markup off. The full
byte-for-byte coverage invariant (A2, invariant 1) still holds under
degradation -- the one region covers [0, len(text)) in full.

PERFORMANCE PRE-CHECKS (DoD: a full 1MB scan <= 150ms, "no silent
slowdown"): _no_markers_whole_text()/_too_many_fence_opens() -- two
cheap (O(n), but with a tiny C-level constant) checks BEFORE the main
line-by-line parse; see each one's own docstring. Without them the
line-by-line parse (several Python-level passes per line) misses the
budget on inputs with very many short lines -- see the builder's
report (profile/witness) for this module's landing dispatch.

EDGE (c) -- UNTERMINATED FENCE: the module returns unterminated=True on
the Region, it does NOT render a verdict. Stage-2 consumers differ on
the default for this unclear case: negative_lint/claim_control_gate
default to "unclear -> the guard speaks" (caution toward firing);
owns_gate's default is the OPPOSITE (WARN-only, "never block" ->
unclear stays silent). This is a DIFFERENCE BETWEEN CONSUMERS, not in
the module -- recorded here explicitly so a future owns_gate consumer
(a different predicate) does not inherit the first wave's policy by
accident.

COMMONMARK-LITE -- EXPLICIT DEVIATIONS FROM FULL COMMONMARK (A3):
  1. 4-space indented code is NOT recognized as its own kind -- it
     stays ordinary prose (the fence/quote-marker regexes already
     reject >3 leading spaces as "not a marker", this is a SIDE
     EFFECT of that same check, there is no dedicated code kind for
     it).
  2. Lazy blockquote continuation is NOT implemented -- every quote
     line must carry its OWN `>`; a line without `>` that would
     continue the quote paragraph under full CommonMark rules is
     treated here as the END of the quote. The gap is pinned by a
     test, not closed.
  3. Quote nesting depth is not modeled -- `>>` (a 2-level nested
     quote) is recognized as ONE quote (only the first `>` is
     stripped); the second `>` stays part of the region's text
     (prose).
  4. Inline code -- ONLY backtick runs on ONE physical line; a pair
     split by a newline does not match and stays prose (this is the
     same real CommonMark rule -- "a backtick string of length N is
     closed by the next backtick string of length N" -- deliberately
     scoped here to a single line).
  5. A fence's info string (```lang) is NOT checked for an embedded
     backtick (full CommonMark forbids a backtick inside a backtick
     fence's info string) -- here the info string is simply
     "everything after the marker to end of line", with no semantics
     (info is stored as a fact, "info with no policy").
  6. No parsing of tables/lists/headings/HTML blocks -- out of scope
     for v1 (only prose/fence/blockquote/inline-code).

OFFSETS AND INDEXING: all offsets are in CHARACTERS (not bytes).
Region.start/Region.end -- like a slice text[start:end] (start
inclusive, end exclusive). Region.line_start/line_end -- 0-based line
numbers, BOTH inclusive (line_end is the number of the LAST line of
the region, also included). Regions in scan().regions are ordered by
increasing start; kind_at() looks them up via bisect. A ~~~ fence is
equivalent to a ``` fence (same marker, either of the two chars,
closed by the SAME char). No CLI is provided -- the module is import-
only.
"""

from __future__ import annotations

import bisect
import re
from typing import List, NamedTuple, Optional, Tuple

# --- public kind constants -------------------------------------

KIND_PROSE = "prose"
KIND_FENCED = "fenced"
KIND_INLINE_CODE = "inline_code"
KIND_BLOCKQUOTE = "blockquote"
# reserved for v2, scan() never returns these (pinned)
KIND_NOTES = "notes"
KIND_EMBEDDED_DOC = "embedded_doc"

# --- public limits (A4) -------------------------------------------

MAX_TEXT_CHARS = 2_000_000
MAX_REGIONS = 20_000
MAX_LINE_INLINE_SPANS = 200


# --- public API type -------------------------------------------------


class Region(NamedTuple):
    start: int
    end: int
    kinds: Tuple[str, ...]
    line_start: int
    line_end: int
    unterminated: bool
    info: str


class ScanResult(NamedTuple):
    regions: List[Region]
    degraded: bool
    reason: str


# --- private regex primitives -----------------------------------------

_QUOTE_RE = re.compile(r"^ {0,3}>( ?)")
_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_CLOSE_STRIP_RE = re.compile(r"^ {0,3}")
_BACKTICK_RUN_RE = re.compile(r"`+")


def _is_fence_close(content: str, fence_char: str, fence_len: int) -> bool:
    m = _CLOSE_STRIP_RE.match(content)
    rest = content[m.end():]
    i = 0
    length = len(rest)
    while i < length and rest[i] == fence_char:
        i += 1
    if i < fence_len:
        return False
    return rest[i:].strip(" \t") == ""


def _find_fence_close(lines, start_idx: int, n: int, fence_char: str, fence_len: int, quote: bool):
    """Return (end_line_index, unterminated) for a fence opened at start_idx-1."""
    k = start_idx
    while k < n:
        text_k = lines[k][0]
        if quote:
            qm_k = _QUOTE_RE.match(text_k)
            if not qm_k:
                return k - 1, True
            content = text_k[qm_k.end():]
        else:
            content = text_k
        if _is_fence_close(content, fence_char, fence_len):
            return k, False
        k += 1
    return n - 1, True


def _maybe_marker(text_i: str) -> bool:
    """Cheap pre-filter (perf, DoD 1MB<=150ms): a line can only be a quote
    marker or a fence-open marker if one of '>','`','~' sits within its
    first 4 chars (<=3 leading spaces + the marker char). Skipping the two
    anchored regexes for the (overwhelmingly common) plain-line case is the
    dominant win on inputs with very many short lines -- see witness."""
    prefix = text_i[:4]
    return (">" in prefix) or ("`" in prefix) or ("~" in prefix)


def _iter_block_runs(lines):
    """Yield (kinds_stack, line_start, line_end, fence_info_or_None) tuples
    covering every line exactly once, in order. fence_info is
    (fence_char, fence_len, info, unterminated) only when kinds_stack ends
    in KIND_FENCED, else None."""
    n = len(lines)
    i = 0
    mode = "TOP"
    run_start = 0
    while i < n:
        text_i = lines[i][0]
        if mode == "TOP":
            if not _maybe_marker(text_i):
                i += 1
                continue
            qm = _QUOTE_RE.match(text_i)
            if qm:
                if i > run_start:
                    yield (), run_start, i - 1, None
                mode = "QUOTE"
                run_start = i
                continue
            fm = _FENCE_OPEN_RE.match(text_i)
            if fm:
                if i > run_start:
                    yield (), run_start, i - 1, None
                fence_char = fm.group(1)[0]
                fence_len = len(fm.group(1))
                fence_info_str = fm.group(2)
                end_line, unterminated = _find_fence_close(
                    lines, i + 1, n, fence_char, fence_len, quote=False
                )
                yield (
                    (KIND_FENCED,),
                    i,
                    end_line,
                    (fence_char, fence_len, fence_info_str, unterminated),
                )
                i = end_line + 1
                run_start = i
                mode = "TOP"
                continue
            i += 1
            continue
        else:  # mode == "QUOTE"
            qm = _QUOTE_RE.match(text_i)
            if not qm:
                if i > run_start:
                    yield (KIND_BLOCKQUOTE,), run_start, i - 1, None
                mode = "TOP"
                run_start = i
                continue
            inner = text_i[qm.end():]
            fm = _FENCE_OPEN_RE.match(inner) if _maybe_marker(inner) else None
            if fm:
                if i > run_start:
                    yield (KIND_BLOCKQUOTE,), run_start, i - 1, None
                fence_char = fm.group(1)[0]
                fence_len = len(fm.group(1))
                fence_info_str = fm.group(2)
                end_line, unterminated = _find_fence_close(
                    lines, i + 1, n, fence_char, fence_len, quote=True
                )
                yield (
                    (KIND_BLOCKQUOTE, KIND_FENCED),
                    i,
                    end_line,
                    (fence_char, fence_len, fence_info_str, unterminated),
                )
                i = end_line + 1
                run_start = i
                mode = "TOP" if unterminated else "QUOTE"
                continue
            i += 1
            continue
    if run_start <= n - 1:
        tail_kind = (KIND_BLOCKQUOTE,) if mode == "QUOTE" else ()
        yield tail_kind, run_start, n - 1, None


def _inline_split(line_text: str, base_start: int, full_end: int, base_kinds, limit: int):
    """Split one physical line (line_text, without terminator) into
    (start, end, kinds) pieces covering [base_start, full_end) -- full_end
    includes the line terminator, if any. Returns None if the number of
    inline-code spans on this line exceeds `limit`."""
    full_len = full_end - base_start
    if "`" not in line_text:
        if full_len > 0:
            return [(base_start, full_end, base_kinds + (KIND_PROSE,))]
        return []
    runs = [(m.start(), m.end()) for m in _BACKTICK_RUN_RE.finditer(line_text)]
    if not runs:
        if full_len > 0:
            return [(base_start, full_end, base_kinds + (KIND_PROSE,))]
        return []

    by_length = {}
    for idx, (s, e) in enumerate(runs):
        by_length.setdefault(e - s, []).append(idx)

    pieces = []
    cursor = 0
    code_span_count = 0
    i = 0
    n_runs = len(runs)
    while i < n_runs:
        s_i, e_i = runs[i]
        length = e_i - s_i
        idx_list = by_length[length]
        pos = bisect.bisect_right(idx_list, i)
        if pos < len(idx_list):
            j = idx_list[pos]
            s_j, e_j = runs[j]
            if s_i > cursor:
                pieces.append((cursor, s_i, base_kinds + (KIND_PROSE,)))
            pieces.append((s_i, e_j, base_kinds + (KIND_INLINE_CODE,)))
            code_span_count += 1
            if code_span_count > limit:
                return None
            cursor = e_j
            i = j + 1
        else:
            i += 1

    if cursor < full_len:
        pieces.append((cursor, full_len, base_kinds + (KIND_PROSE,)))

    return [(base_start + s, base_start + e, k) for (s, e, k) in pieces]


_FENCE_OPEN_COUNT_RE = re.compile(r"^ {0,3}(?:`{3,}|~{3,})", re.MULTILINE)


def _no_markers_whole_text(text: str) -> bool:
    """Perf pre-check (DoD 1MB<=150ms): if none of '>' / backtick / '~'
    occurs ANYWHERE in the text, none of blockquote/fence/inline-code
    syntax can possibly be present (all three require at least one of
    these chars) -- a plain substring membership check (`in`, O(n) but a
    tiny C-level constant), not an approximation: when it returns True the
    whole-text-is-prose answer is EXACT, not a degraded fallback. Skips the
    per-line state machine entirely for the (very common) marker-free case,
    which is where that machine's per-line Python overhead dominates on
    inputs with very many short lines."""
    return ">" not in text and "`" not in text and "~" not in text


def _too_many_fence_opens(text: str) -> bool:
    """Perf pre-check (DoD 1MB<=150ms), companion to _no_markers_whole_text:
    counts '^ {0,3}(```+|~~~+)'-shaped line starts (re.MULTILINE, LF/CRLF
    line starts) with an early exit once the count exceeds MAX_REGIONS.
    Each such fence-open opens its OWN region that never merges with a
    sibling fenced region (only PROSE regions merge, see scan()) -- so a
    count over MAX_REGIONS is a SOUND lower bound on the eventual region
    count, not a heuristic: full processing of such a text is guaranteed to
    hit max_regions_exceeded too, this just reaches the same, otherwise
    identical, degraded result without paying the per-line loop first.
    re.MULTILINE's `^` anchors only after '\\n' -- a text using bare '\\r'
    line endings (no '\\n' at all) is undercounted here and simply falls
    through to the slower-but-correct per-line path (never a correctness
    risk, only a missed shortcut for that one exotic combination)."""
    count = 0
    for _ in _FENCE_OPEN_COUNT_RE.finditer(text):
        count += 1
        if count > MAX_REGIONS:
            return True
    return False


def _degrade(text: str, reason: str) -> ScanResult:
    no_term = text.splitlines()
    last_line = max(len(no_term) - 1, 0)
    region = Region(0, len(text), (KIND_PROSE,), 0, last_line, False, "")
    return ScanResult([region], True, reason)


def _split_lines(text: str):
    no_term = text.splitlines()
    with_term = text.splitlines(keepends=True)
    lines = []
    pos = 0
    for nt, wt in zip(no_term, with_term):
        full_len = len(wt)
        lines.append((nt, pos, pos + full_len))
        pos += full_len
    return lines


# --- public API -------------------------------------------------------


def scan(text) -> ScanResult:
    if not isinstance(text, str):
        return ScanResult([], True, "not_a_string")
    if text == "":
        return ScanResult([], False, "")
    if len(text) > MAX_TEXT_CHARS:
        return _degrade(text, "text_too_large")

    if _no_markers_whole_text(text):
        last_line = max(len(text.splitlines()) - 1, 0)
        region = Region(0, len(text), (KIND_PROSE,), 0, last_line, False, "")
        return ScanResult([region], False, "")

    if _too_many_fence_opens(text):
        return _degrade(text, "max_regions_exceeded")

    lines = _split_lines(text)
    regions: List[Region] = []
    # `pending` -- a mutable [start, end, kinds, line_start, line_end] for an
    # open run of merged same-kind PROSE pieces; a plain list (not a Region)
    # so extending it on each matching line is a cheap in-place mutation
    # instead of rebuilding a NamedTuple via ._replace() on every line (perf
    # budget A4/DoD: 1MB scan <=150ms -- ._replace()-per-line measured as the
    # dominant cost on a 1MB plain-prose profile, see witness).
    pending = None

    for stack, i0, i1, fence_info in _iter_block_runs(lines):
        if fence_info is not None:
            if pending is not None:
                regions.append(Region(pending[0], pending[1], pending[2], pending[3], pending[4], False, ""))
                pending = None
                if len(regions) > MAX_REGIONS:
                    return _degrade(text, "max_regions_exceeded")
            fence_char, fence_len, info, unterminated = fence_info
            start_c = lines[i0][1]
            end_c = lines[i1][2]
            regions.append(Region(start_c, end_c, stack, i0, i1, unterminated, info))
            if len(regions) > MAX_REGIONS:
                return _degrade(text, "max_regions_exceeded")
            continue

        for li in range(i0, i1 + 1):
            nt, s, e = lines[li]
            pieces = _inline_split(nt, s, e, stack, MAX_LINE_INLINE_SPANS)
            if pieces is None:
                return _degrade(text, "max_line_inline_spans_exceeded")
            for (ps, pe, pk) in pieces:
                if pk[-1] == KIND_PROSE and pending is not None and pending[2] == pk and pending[1] == ps:
                    pending[1] = pe
                    pending[4] = li
                    continue
                if pending is not None:
                    regions.append(Region(pending[0], pending[1], pending[2], pending[3], pending[4], False, ""))
                    pending = None
                    if len(regions) > MAX_REGIONS:
                        return _degrade(text, "max_regions_exceeded")
                if pk[-1] == KIND_PROSE:
                    pending = [ps, pe, pk, li, li]
                else:
                    regions.append(Region(ps, pe, pk, li, li, False, ""))
                    if len(regions) > MAX_REGIONS:
                        return _degrade(text, "max_regions_exceeded")

    if pending is not None:
        regions.append(Region(pending[0], pending[1], pending[2], pending[3], pending[4], False, ""))
        if len(regions) > MAX_REGIONS:
            return _degrade(text, "max_regions_exceeded")

    return ScanResult(regions, False, "")


def line_kinds(text) -> List[Tuple[str, ...]]:
    if not isinstance(text, str) or text == "":
        return []
    lines = _split_lines(text)
    result: List[Optional[Tuple[str, ...]]] = [None] * len(lines)
    for stack, i0, i1, _fence in _iter_block_runs(lines):
        for li in range(i0, i1 + 1):
            result[li] = stack
    return result


def kind_at(result: ScanResult, offset: int) -> Tuple[str, ...]:
    regions = result.regions
    if not regions:
        return ()
    starts = [r.start for r in regions]
    idx = bisect.bisect_right(starts, offset) - 1
    if idx < 0:
        return ()
    region = regions[idx]
    if region.start <= offset < region.end:
        return region.kinds
    return ()
