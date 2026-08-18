"""tools/test_norm_form.py -- W2b-8 (D-0054/D-0065) canonical form/keys
gate for the six converted Routing rules (R11/R8/R2/R13/R4/R1) in
CLAUDE.md, per docs/tasks/2026-08-18_w2b-claude-md-form-spec.md section
3.1a and docs/tasks/2026-08-18_w2b-transfer-maps.md.

Layer 1 (completeness): every key phrase registered for a converted
rule in tools/norm_keys.json is present, FOLD-WHITESPACE-CONTAINED, in
CLAUDE.md OR docs/POLICY_FULL.md. The fold contract is the SAME one
escape_check.py's leg (a) uses (_fold_whitespace: runs of
{space,tab,CR,LF} collapse to one space; '|' is never folded) --
codified 08-19 after a naive, non-folding key-check falsely flagged
phrases that cross a markdown line-wrap (docs/tasks/
2026-08-18_w2b-transfer-maps.md, "ПРАВИЛО КЛЮЧ-ПРОГОНА").

Layer 2 (form), applied to each of the six converted rules' registry
tables:
  - core prose is 3-8 physical lines (already-list blocks, e.g. R11's
    FIVE-POINT CHECKLIST, are excluded from that count -- spec 3.1
    rule 2);
  - every registry row is <=523 UTF-8 bytes (W2b-0 remeasure: the
    longest surviving normative row + 15%; supersedes the earlier
    400/460-byte figures from the pre-W2b-0 draft, see transfer-maps);
  - a rule carrying a registry table has at least one row (an empty
    table header is a defect -- spec 3.1 rule 7);
  - every '|' that is literal cell TEXT (not a column separator) is
    escaped as '\\|' (spec 3.1 rule 5);
  - every row's src identifier (D-NNNN) resolves two-carrier (Р11(A)):
    either a '## D-NNNN' section in docs/DECISIONS_FULL.md, or a
    '## RN'/'### RN' rationale section for that rule in
    docs/POLICY_FULL.md;
  - no escape_allowlist.json carrier_anchor living inside a converted
    rule's table is split across a cell boundary (folding removes
    line-wraps but never a literal '|').

Completeness assert: converted rule-ids UNION exempted rule-ids ==
{R1..R13, R11a} (Р12(B): R3/R5/R6/R7/R9/R10/R12/R11a carry no registry
block yet and are exempt until their first amendment creates one).

Boundaries (core 8/9, row 523/524, an unescaped '|', a split anchor,
an unresolved src, a missing key) are proven on SYNTHETIC text built
in-memory / under tmp_path -- never on a live repo file (command
hygiene p.7г).

Run: python -m pytest tools/test_norm_form.py -q
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from escape_check import _fold_whitespace

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
NORM_KEYS_PATH = SCRIPT_DIR / "norm_keys.json"
ESCAPE_ALLOWLIST_PATH = SCRIPT_DIR / "escape_allowlist.json"
CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"
POLICY_FULL_PATH = REPO_ROOT / "docs" / "POLICY_FULL.md"
DECISIONS_FULL_PATH = REPO_ROOT / "docs" / "DECISIONS_FULL.md"

ALL_RULE_IDS = {f"R{i}" for i in range(1, 14)} | {"R11a"}
CONVERTED_RULE_IDS = ("R1", "R2", "R4", "R8", "R11", "R13")

# W2b-0 remeasure (docs/tasks/2026-08-18_w2b-transfer-maps.md, "ЗАМЕНЯЕТ
# §3.1 пп.3-4"): longest surviving normative registry row + ~15%
# headroom. Supersedes the pre-W2b-0 draft's 400/460-byte figures.
ROW_BYTE_CAP = 523

CORE_MIN_LINES = 3
CORE_MAX_LINES = 8

RULE_HEADER_RE = re.compile(r"^(R\d+a?)\. \*\*", re.MULTILINE)
DECISION_HEADER_RE = re.compile(r"^## (D-\d{4})\b", re.MULTILINE)
POLICY_RULE_HEADER_RE = re.compile(r"^#{2,3} (R\d+a?)\b", re.MULTILINE)

# KNOWN FINDING (discovered by this test, W2b-8): R8's core (committed
# W2b-2, t-495, accepted before this node existed) is 9 physical lines
# -- one over this spec's own "core 3-8 lines" ceiling (docs/tasks/
# 2026-08-18_w2b-claude-md-form-spec.md 3.1 rule 2). Editing R8's rule
# CONTENT is outside this dispatch's owns (only the budget line and the
# key/form machinery are owned here) -- reported to the coordinator in
# the W2b-8 builder report, not silently fixed and not silently
# swallowed here. Pinned to the EXACT known count so a NEW, unrelated
# over-length rule still fails loudly instead of being absorbed by a
# growing allowlist.
# Пусто с 2026-08-19: единственный пин (R8: 9 строк, находка t-498)
# снят при посадке — Lead пере-перенёс строки ядра R8 в 8 (текст не
# менялся, ключи фолдят пробелы). Новая запись сюда = новая находка.
KNOWN_CORE_LINE_FINDINGS: dict = {}


def _read(path):
    return path.read_text(encoding="utf-8")


def _load_norm_keys():
    return json.loads(NORM_KEYS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------
# Layer 1: key completeness
# ---------------------------------------------------------------------


def _phrase_present(phrase, *carriers_text):
    folded_phrase = _fold_whitespace(phrase)
    return any(folded_phrase in _fold_whitespace(t) for t in carriers_text)


def _layer1_missing(data, *carriers_text):
    missing = []
    for rule_id, rows in data["converted"].items():
        for row in rows:
            for phrase in row["phrases"]:
                if not _phrase_present(phrase, *carriers_text):
                    missing.append((rule_id, row["row"], phrase))
    return missing


def test_layer1_all_converted_keys_present():
    data = _load_norm_keys()
    claude_text = _read(CLAUDE_MD_PATH)
    policy_text = _read(POLICY_FULL_PATH)
    missing = _layer1_missing(data, claude_text, policy_text)
    assert not missing, f"missing keys: {missing}"


def test_layer1_negative_control_missing_key_fails(tmp_path):
    """Adversarial control (D-0052 class, R11.l/m): an evergreen check
    that can never fail is indistinguishable from a broken one. Strikes
    one known-present phrase from a COPY of the carrier text (a
    tmp_path file -- the live CLAUDE.md is never touched, command
    hygiene p.7г) and asserts the layer-1 check reports exactly that
    phrase missing."""
    data = _load_norm_keys()
    claude_text = _read(CLAUDE_MD_PATH)
    policy_text = _read(POLICY_FULL_PATH)

    target_row = data["converted"]["R1"][0]
    target_phrase = target_row["phrases"][0]
    assert target_phrase == "any repo search, or more than"
    assert target_phrase in claude_text  # positive control: really there, unfolded

    doctored_path = tmp_path / "CLAUDE.doctored.md"
    doctored_path.write_text(
        claude_text.replace(target_phrase, "X" * len(target_phrase)),
        encoding="utf-8",
    )
    doctored_text = doctored_path.read_text(encoding="utf-8")
    assert target_phrase not in doctored_text  # confirms the strike landed

    missing = _layer1_missing(data, doctored_text, policy_text)
    assert ("R1", 1, target_phrase) in missing


# ---------------------------------------------------------------------
# Layer 2: form -- block/row extraction helpers
# ---------------------------------------------------------------------


def _routing_rules_section(text):
    start = text.index("## Routing rules")
    end = text.index("## Journal", start)
    return text[start:end]


def _split_rule_blocks(section_text):
    matches = list(RULE_HEADER_RE.finditer(section_text))
    blocks = {}
    for i, m in enumerate(matches):
        rid = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
        blocks[rid] = section_text[start:end].rstrip("\n")
    return blocks


def _core_lines(block_text):
    """Lines from the block's start up to (not including) the first
    markdown table row (a line starting with '|'); trailing blank
    lines trimmed. Content AFTER the table (e.g. R11's FIVE-POINT
    CHECKLIST) is never part of this -- it is a separate already-list
    block, excluded from the core count by spec 3.1 rule 2."""
    core = []
    for ln in block_text.split("\n"):
        if ln.startswith("|"):
            break
        core.append(ln)
    while core and core[-1].strip() == "":
        core.pop()
    return core


def core_line_count(block_text):
    return len(_core_lines(block_text))


def _table_rows(block_text):
    """Every '|'-prefixed line of the block, EXCLUDING the header row
    and the '|---|...' separator row (the first two such lines)."""
    pipe_lines = [ln for ln in block_text.split("\n") if ln.startswith("|")]
    return pipe_lines[2:]


def table_nonempty(block_text):
    return len(_table_rows(block_text)) > 0


def row_within_byte_cap(row_line, cap=ROW_BYTE_CAP):
    return len(row_line.encode("utf-8")) <= cap


def row_pipes_all_escaped(row_line, expected_cols=4):
    """A well-formed '| a | when | duty | src |' row has exactly
    expected_cols + 1 UNESCAPED '|' characters (one per column
    boundary, including the leading and trailing one). An unescaped
    '|' that is really part of a cell's TEXT throws that count off --
    the naive column-count check IS the unescaped-pipe detector (spec
    3.1 rule 5)."""
    unescaped = row_line.replace("\\|", "")
    return unescaped.count("|") == expected_cols + 1


def _row_cells(row_line):
    """Splits a table row into its cell texts, honoring '\\|' as a
    literal escaped pipe (not a column boundary). Drops the row's own
    leading/trailing empty cells (from the outer '|' delimiters)."""
    placeholder = "\x00"
    protected = row_line.replace("\\|", placeholder)
    raw_cells = protected.split("|")
    cells = [c.replace(placeholder, "\\|").strip() for c in raw_cells]
    if cells and cells[0] == "":
        cells = cells[1:]
    if cells and cells[-1] == "":
        cells = cells[:-1]
    return cells


def _decisions_full_headers(text):
    return set(DECISION_HEADER_RE.findall(text))


def _policy_full_rule_sections(text):
    return set(POLICY_RULE_HEADER_RE.findall(text))


def src_resolves(src_id, rule_id, decisions_headers, policy_rule_ids):
    if src_id in decisions_headers:
        return True
    if rule_id in policy_rule_ids:
        return True
    return False


def anchor_not_split_by_cell(anchor, block_text):
    folded_anchor = _fold_whitespace(anchor)
    for row_line in _table_rows(block_text):
        for cell in _row_cells(row_line):
            if folded_anchor in _fold_whitespace(cell):
                return True
    return False


# ---------------------------------------------------------------------
# Layer 2: boundaries on SYNTHETIC text (command hygiene p.7г -- the
# live CLAUDE.md is never mutated for these)
# ---------------------------------------------------------------------


def _synthetic_block(core_line_count_):
    core = ["RX. **Synthetic**: opening line of the core paragraph."]
    for i in range(core_line_count_ - 1):
        core.append(f"filler prose line {i}.")
    table = [
        "| RX | when | duty | src |",
        "|---|---|---|---|",
        "| a | trigger | duty text | D-0001 |",
    ]
    return "\n".join(core + [""] + table)


def test_core_boundary_8_lines_is_legal():
    block = _synthetic_block(8)
    n = core_line_count(block)
    assert n == 8
    assert CORE_MIN_LINES <= n <= CORE_MAX_LINES


def test_core_boundary_9_lines_is_over_limit():
    block = _synthetic_block(9)
    n = core_line_count(block)
    assert n == 9
    assert n > CORE_MAX_LINES


def _row_of_byte_length(n):
    prefix = "| a | w | "
    suffix = " | D-0001 |"
    fixed = (prefix + suffix).encode("utf-8")
    body_len = n - len(fixed)
    assert body_len >= 0
    return prefix + ("x" * body_len) + suffix


def test_row_boundary_523_bytes_is_legal():
    row = _row_of_byte_length(523)
    assert len(row.encode("utf-8")) == 523
    assert row_within_byte_cap(row)


def test_row_boundary_524_bytes_is_over_limit():
    row = _row_of_byte_length(524)
    assert len(row.encode("utf-8")) == 524
    assert not row_within_byte_cap(row)


def test_unescaped_pipe_inside_cell_is_flagged():
    row = "| a | trigger with a | bad pipe | duty text | D-0001 |"
    assert not row_pipes_all_escaped(row)


def test_escaped_pipe_inside_cell_is_legal():
    row = "| a | trigger with a \\| escaped pipe | duty text | D-0001 |"
    assert row_pipes_all_escaped(row)


def test_empty_table_zero_rows_is_flagged():
    block = "RX. **Synthetic**: opening.\n\n| RX | when | duty | src |\n|---|---|---|---|"
    assert not table_nonempty(block)


def test_table_with_one_row_is_legal():
    block = _synthetic_block(3)
    assert table_nonempty(block)


def test_src_resolves_via_decisions_full():
    assert src_resolves("D-0001", "RX", {"D-0001"}, set())


def test_src_does_not_resolve_when_absent_from_both_carriers():
    assert not src_resolves("D-0001", "RX", {"D-0002"}, set())


def test_src_resolves_via_policy_full_fallback():
    assert src_resolves("D-0009", "RX", {"D-0002"}, {"RX"})


def test_anchor_within_single_cell_is_legal():
    block = _synthetic_block(3).replace(
        "duty text", "the whole anchor phrase stays together"
    )
    assert anchor_not_split_by_cell("the whole anchor phrase stays together", block)


def test_anchor_split_by_cell_boundary_is_flagged():
    block = (
        "RX. **Synthetic**: opening.\n\n"
        "| RX | when | duty | src |\n|---|---|---|---|\n"
        "| a | the whole anchor | phrase stays together | D-0001 |"
    )
    assert not anchor_not_split_by_cell("the whole anchor phrase stays together", block)


# ---------------------------------------------------------------------
# Layer 2: applied to the six REAL converted rules
# ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def rule_blocks():
    text = _read(CLAUDE_MD_PATH)
    return _split_rule_blocks(_routing_rules_section(text))


def test_converted_rules_present_as_blocks(rule_blocks):
    for rule_id in CONVERTED_RULE_IDS:
        assert rule_id in rule_blocks


def test_converted_rules_core_length_within_limit_or_known_finding(rule_blocks):
    for rule_id in CONVERTED_RULE_IDS:
        n = core_line_count(rule_blocks[rule_id])
        if rule_id in KNOWN_CORE_LINE_FINDINGS:
            assert n == KNOWN_CORE_LINE_FINDINGS[rule_id], (
                f"{rule_id}: known finding count changed ({n} vs "
                f"{KNOWN_CORE_LINE_FINDINGS[rule_id]}) -- re-verify, don't just re-pin"
            )
            continue
        assert CORE_MIN_LINES <= n <= CORE_MAX_LINES, f"{rule_id}: core is {n} lines"


def test_converted_rules_tables_nonempty(rule_blocks):
    for rule_id in CONVERTED_RULE_IDS:
        assert table_nonempty(rule_blocks[rule_id]), rule_id


def test_converted_rules_rows_within_byte_cap(rule_blocks):
    offenders = [
        (rule_id, len(row.encode("utf-8")), row)
        for rule_id in CONVERTED_RULE_IDS
        for row in _table_rows(rule_blocks[rule_id])
        if not row_within_byte_cap(row)
    ]
    assert not offenders, offenders


def test_converted_rules_rows_have_no_unescaped_pipe(rule_blocks):
    offenders = [
        (rule_id, row)
        for rule_id in CONVERTED_RULE_IDS
        for row in _table_rows(rule_blocks[rule_id])
        if not row_pipes_all_escaped(row)
    ]
    assert not offenders, offenders


def test_converted_rules_src_resolves(rule_blocks):
    decisions_headers = _decisions_full_headers(_read(DECISIONS_FULL_PATH))
    policy_rule_ids = _policy_full_rule_sections(_read(POLICY_FULL_PATH))
    offenders = []
    for rule_id in CONVERTED_RULE_IDS:
        for row in _table_rows(rule_blocks[rule_id]):
            cells = _row_cells(row)
            src = cells[-1] if cells else ""
            if not src_resolves(src, rule_id, decisions_headers, policy_rule_ids):
                offenders.append((rule_id, src, row))
    assert not offenders, offenders


def test_escape_allowlist_anchors_not_split_by_cell(rule_blocks):
    allowlist = json.loads(_read(ESCAPE_ALLOWLIST_PATH))
    checked = 0
    for entry in allowlist["entries"]:
        if entry.get("carrier_file") != "CLAUDE.md":
            continue
        anchor = entry["carrier_anchor"]
        for rule_id in CONVERTED_RULE_IDS:
            if _phrase_present(anchor, rule_blocks[rule_id]):
                checked += 1
                assert anchor_not_split_by_cell(anchor, rule_blocks[rule_id]), (
                    rule_id,
                    anchor,
                )
    # positive control: at least one live carrier_anchor (R8.b,
    # "batching-blocking-self-execution") actually lives inside a
    # converted rule's table and was exercised by this check.
    assert checked >= 1


# ---------------------------------------------------------------------
# Completeness assert: converted UNION exempted == all routing rules
# ---------------------------------------------------------------------


def test_completeness_converted_union_exempted_equals_all_rules():
    data = _load_norm_keys()
    converted = set(data["converted"].keys())
    exempted = set(data["exempted"])
    assert converted & exempted == set(), converted & exempted
    assert converted | exempted == ALL_RULE_IDS, (converted | exempted) ^ ALL_RULE_IDS
    assert converted == set(CONVERTED_RULE_IDS)


def test_completeness_negative_control_dropped_rule_fails(tmp_path):
    """Negative control for the assert itself: if a rule silently
    dropped off BOTH lists, the union would no longer equal the full
    rule set -- confirms the assert can actually fail, not just always
    pass on today's data."""
    data = _load_norm_keys()
    incomplete_path = tmp_path / "norm_keys.incomplete.json"
    data["exempted"] = [r for r in data["exempted"] if r != "R12"]
    incomplete_path.write_text(json.dumps(data), encoding="utf-8")

    reloaded = json.loads(incomplete_path.read_text(encoding="utf-8"))
    converted = set(reloaded["converted"].keys())
    exempted = set(reloaded["exempted"])
    assert converted | exempted != ALL_RULE_IDS
    assert "R12" in (ALL_RULE_IDS - (converted | exempted))
