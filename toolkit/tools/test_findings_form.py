"""Machine layer for the applicability-question norm in
docs/FINDINGS.md (see docs/FINDINGS.template.md's own "Norm: the
applicability question" section for the human-readable statement of
the rule this module checks).

Norm, restated precisely: an entry carrying a **Class.** section is
required to carry an **Applicability question.** section IMMEDIATELY
AFTER **Class.** (between them -- only blank lines / continuing prose
with no field marker of its own). An entry with no **Class.** section
needs no such field. UNLIKE a sibling deployment's own version of this
check (ported FROM by meaning, not by literal date-gated grandfather
clause), this template ships with ZERO live entries at install time --
there is no pre-existing corpus of old-format entries that would need
a cutoff-date exemption, so this check applies the rule to EVERY
entry, uniformly, from the first one on. A host that later wants a
grandfather clause for its OWN pre-adoption history is free to add one
in its own copy of this file; that is a host-specific decision, not
part of the norm this kit ships.

ANCHOR (deliberately narrow, same rationale as the sibling deployment
this was ported from): the marker within a fenced code block or a
blockquote line (`>`) is not a filled field -- "a quotation is not the
entry's own assertion". Before parsing, such ranges are masked (the
text is blanked with spaces, newlines preserved) so a marker
appearing only inside one of them never matches the regexes below.

Tolerant of variation in the UNCHECKED fields (Date/Observation/
Consequence/Status/anything else -- their exact form is never parsed,
only Class and Applicability question are).

Self-contained (re/dataclasses/pathlib/pytest only, no repo imports) --
matches the canonical run form (`python -m pytest tools/ -q` from the
toolkit root), and the narrow target
`python -m pytest toolkit/tools/test_findings_form.py -q`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

FINDINGS_PATH = Path(__file__).resolve().parent.parent / "docs" / "FINDINGS.md"

HEADER_RE = re.compile(r"(?m)^##\s+(F-\d+)\b.*$")
FENCE_RE = re.compile(r"(?ms)^```.*?^```")
QUOTE_LINE_RE = re.compile(r"(?m)^[ \t]*>.*$")

CLASS_RE = re.compile(r"\*\*Class\.?\*\*")
VOPROS_RE = re.compile(r"\*\*Applicability question\.?\*\*")
# any bold field marker starting a paragraph (Observation./Class./
# Consequence./Status./Date: and so on, including future variations --
# the parser is tolerant of their exact form, but must still RECOGNIZE
# that a paragraph starts a NEW field, not continuing prose of the
# previous one)
FIELD_MARKER_RE = re.compile(r"^\*\*[^*\n]{1,80}?[.:]\*\*")


def _mask(text: str) -> str:
    """Blanks fenced code blocks and blockquote lines (`>`) with
    spaces, preserving newlines -- a marker inside such a range stops
    matching the regexes below."""

    def _blank(m: "re.Match[str]") -> str:
        return "".join(ch if ch == "\n" else " " for ch in m.group(0))

    text = FENCE_RE.sub(_blank, text)
    text = QUOTE_LINE_RE.sub(_blank, text)
    # lines that became pure whitespace after masking -> empty, so the
    # paragraph split below treats them as a block separator
    lines = text.split("\n")
    lines = ["" if line.strip(" \t") == "" else line for line in lines]
    return "\n".join(lines)


def _paragraphs(masked: str) -> list[str]:
    """Paragraphs -- blocks of text separated by >=1 blank line (after
    masking). Empty paragraphs are dropped."""
    parts = re.split(r"\n{2,}", masked.strip("\n"))
    return [p for p in parts if p.strip() != ""]


@dataclass
class RecordCheck:
    name: str
    has_class: bool
    vopros_present_anywhere: bool
    vopros_immediately_after_class: bool

    @property
    def subject_to_rule(self) -> bool:
        return self.has_class

    @property
    def ok(self) -> bool:
        if not self.subject_to_rule:
            return True
        return self.vopros_immediately_after_class

    @property
    def reason(self) -> str:
        if self.ok:
            return "ok"
        if not self.vopros_present_anywhere:
            return "Applicability question is missing entirely"
        return "Applicability question is present, but not immediately after Class"


def parse_record(name: str, raw_body: str) -> RecordCheck:
    """Parses the body of ONE entry (the text between its `## F-NN`
    header and the next header/end of file) and returns a form
    verdict."""
    body = raw_body.replace("\r\n", "\n").replace("\r", "\n")
    masked = _mask(body)

    has_class = CLASS_RE.search(masked) is not None
    vopros_present_anywhere = VOPROS_RE.search(masked) is not None

    paragraphs = _paragraphs(masked)

    vopros_immediately_after = False
    if has_class:
        class_idx = None
        for i, p in enumerate(paragraphs):
            if CLASS_RE.match(p.lstrip()):
                class_idx = i
                break
        if class_idx is not None:
            # Class is a SECTION, not a single paragraph: continuing
            # prose (a paragraph NOT starting a new field marker) is
            # still part of Class ("between them -- only blank lines"
            # reads as "no OTHER field cut in"). The first paragraph
            # starting with ANY bold field marker is "the next field";
            # check whether it is Applicability question.
            for j in range(class_idx + 1, len(paragraphs)):
                nxt = paragraphs[j].lstrip()
                if VOPROS_RE.match(nxt):
                    vopros_immediately_after = True
                    break
                if FIELD_MARKER_RE.match(nxt):
                    # a different field cut in before Applicability question
                    vopros_immediately_after = False
                    break
                # else: continuing prose of Class, keep going

    return RecordCheck(
        name=name,
        has_class=has_class,
        vopros_present_anywhere=vopros_present_anywhere,
        vopros_immediately_after_class=vopros_immediately_after,
    )


def extract_records(full_text: str) -> list[tuple[str, str]]:
    """Splits a FINDINGS.md document into entries by `## F-NN`
    headers. Text before the first such header (the preamble,
    including this norm's own statement) never enters the parse -- not
    an entry."""
    text = full_text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(HEADER_RE.finditer(text))
    records = []
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        records.append((name, text[start:end]))
    return records


# ---------------------------------------------------------------------
# Adversarial battery on the parser (synthetic text).
# ---------------------------------------------------------------------


def test_empty_text():
    c = parse_record("F-EMPTY", "")
    assert c.has_class is False
    assert c.ok is True  # not subject at all -- an empty entry has no Class


def test_record_without_class():
    body = """
**Date:** 2026-08-09.

**Observation.** Something happened, but there is no Class section at all.

**Status.** Open.
"""
    c = parse_record("F-NOCLASS", body)
    assert c.has_class is False
    assert c.subject_to_rule is False
    assert c.ok is True


def test_vopros_marker_inside_fenced_code_block_does_not_count():
    body = """
**Date:** 2026-08-09.

**Class.** Text of the class of defect.

```
**Applicability question.** this is inside a code block, a quotation is not a fact.
```

**Status.** Open.
"""
    c = parse_record("F-FENCE", body)
    assert c.has_class is True
    assert c.subject_to_rule is True
    # the marker is physically present in the text but masked -- it
    # counts neither as "present anywhere" nor, a fortiori, as "right after"
    assert c.vopros_present_anywhere is False
    assert c.vopros_immediately_after_class is False
    assert c.ok is False


def test_vopros_marker_inside_blockquote_does_not_count():
    body = """
**Date:** 2026-08-09.

**Class.** Text of the class of defect.

> **Applicability question.** this is a quotation, not the entry's own assertion.

**Status.** Open.
"""
    c = parse_record("F-QUOTE", body)
    assert c.has_class is True
    assert c.subject_to_rule is True
    assert c.vopros_present_anywhere is False
    assert c.vopros_immediately_after_class is False
    assert c.ok is False


def test_crlf_text_parses_same_as_lf():
    body_lf = "**Date:** 2026-08-09.\n\n**Class.** Text.\n\n**Applicability question.** Question?\n"
    body_crlf = body_lf.replace("\n", "\r\n")
    c_lf = parse_record("F-LF", body_lf)
    c_crlf = parse_record("F-CRLF", body_crlf)
    assert c_lf.ok is True
    assert c_crlf.ok is True
    assert c_lf.vopros_immediately_after_class == c_crlf.vopros_immediately_after_class


def test_marker_case_variation_not_recognized():
    # Class/Applicability question are recognized in the canonical
    # capitalization (as the template actually spells them); a
    # lowercase variant of these TWO markers is NOT treated as a field
    # -- otherwise an ordinary mention of the word "class"/"question" in
    # prose would be falsely counted as a structural marker.
    body = """
**date:** 2026-08-09.

**class.** text of the class of defect, lowercase.

**applicability question.** question, lowercase.
"""
    c = parse_record("F-LOWER", body)
    assert c.has_class is False
    assert c.subject_to_rule is False  # no Class recognized -- the rule does not apply at all
    assert c.ok is True


def test_vopros_not_immediately_after_class_fails():
    body = """
**Date:** 2026-08-09.

**Class.** Text of the class.

**Consequence.** Some other field sits between Class and Applicability question.

**Applicability question.** A question, but not right after Class.
"""
    c = parse_record("F-NOTADJACENT", body)
    assert c.has_class is True
    assert c.subject_to_rule is True
    assert c.vopros_present_anywhere is True
    assert c.vopros_immediately_after_class is False
    assert c.ok is False


def test_vopros_immediately_after_class_passes():
    body = """
**Date:** 2026-08-09.

**Observation.** Something happened.

**Class.** Text of the class.

**Applicability question.** A question, right after class.

**Status.** Open.
"""
    c = parse_record("F-ADJACENT-OK", body)
    assert c.has_class is True
    assert c.subject_to_rule is True
    assert c.vopros_immediately_after_class is True
    assert c.ok is True


def test_class_multi_paragraph_continuation_still_counts_as_adjacent():
    # a Class section spanning several paragraphs of prose (no field
    # markers of their own) is still Class, not an intervening field;
    # Applicability question right after it is ok.
    body = """
**Date:** 2026-08-09.

**Class.** First paragraph of the class.

Second paragraph -- continuing prose of the class, no marker of its own.

Third paragraph -- likewise.

**Applicability question.** Question after a multi-paragraph class.

**Consequence.** Not yet resolved.
"""
    c = parse_record("F-MULTIPARA", body)
    assert c.has_class is True
    assert c.subject_to_rule is True
    assert c.vopros_immediately_after_class is True
    assert c.ok is True


def test_class_continuation_then_other_field_before_vopros_fails():
    # symmetric: a Class continuation paragraph is legal, but a
    # DIFFERENT field cutting in after it, before Applicability
    # question, still fails.
    body = """
**Date:** 2026-08-09.

**Class.** First paragraph of the class.

Second paragraph -- continuing prose of the class.

**Consequence.** This field cut in before Applicability question.

**Applicability question.** A question, but no longer right after Class.
"""
    c = parse_record("F-MULTIPARA-FAIL", body)
    assert c.vopros_immediately_after_class is False
    assert c.ok is False


def test_multiple_blank_lines_between_class_and_vopros_still_adjacent():
    # several consecutive blank lines -- still "right after" (their
    # count between fields is not limited)
    body = "**Date:** 2026-08-09.\n\n**Class.** Text.\n\n\n\n**Applicability question.** Question.\n"
    c = parse_record("F-MULTIBLANK", body)
    assert c.vopros_immediately_after_class is True
    assert c.ok is True


# ---------------------------------------------------------------------
# extract_records -- splitting a document by headers.
# ---------------------------------------------------------------------


def test_extract_records_splits_by_header_and_skips_preamble():
    doc = """# Findings

A preamble describing the norm, mentioning **Class.** and
**Applicability question.** only in prose -- this is NOT an entry.

---

## F-1 -- First finding

**Class.** Text.

## F-2 -- Second finding

**Class.** Text.
"""
    records = extract_records(doc)
    names = [n for n, _ in records]
    assert names == ["F-1", "F-2"]
    # the preamble did not leak into any entry
    assert all("preamble" not in body.lower() for _, body in records)


# ---------------------------------------------------------------------
# Live run against the actual docs/FINDINGS.md -- ALL records in the
# file are the scope (no cutoff/subset). The kit itself ships this
# template with ZERO entries (a host copies it before its first
# finding) -- both worlds are exercised: a missing file skips with a
# reason, an existing-but-empty file is vacuously green, and a
# non-empty file is checked entry by entry.
# ---------------------------------------------------------------------


def _read_live_text():
    if not FINDINGS_PATH.exists():
        return None
    return FINDINGS_PATH.read_text(encoding="utf-8")


def test_live_findings_file_form():
    text = _read_live_text()
    if text is None:
        pytest.skip(
            f"{FINDINGS_PATH} not present (pre-first-finding install state) -- nothing to check"
        )
    records = extract_records(text)
    if not records:
        return  # zero entries -- vacuously green, nothing to check
    failures = []
    for name, body in records:
        c = parse_record(name, body)
        if not c.ok:
            failures.append(f"{name}: {c.reason}")
    assert not failures, "; ".join(failures)
