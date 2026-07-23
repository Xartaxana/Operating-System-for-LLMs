"""Battery for tools/escape_check.py (N4, docs/tasks/2026-07-21_validation-import.md,
mechanism #3: hash-pinning of permanent escape/concession clauses to their
authorizing D-decision).

Covers: green path (all three legs alive), broken carrier anchor, missing
decision section, decision-section drift (hash mismatch, diagnostic names
entry+decision_id), duplicate section in the decision file, duplicate id in
the allowlist, broken JSON / non-object root / per-field schema violations,
empty entries -> OK 0, unknown CLI flag -> exit 2, --hash of a non-existent
decision -> exit 1, CRLF/LF hash-normalization equivalence, an
end-of-file section with no trailing newline, non-UTF-8 bytes in both the
allowlist and a decision/carrier file (fail-closed, ASCII diagnostic, no
traceback), and a live-repo anchor test: the real tools/escape_allowlist.json
must validate against the real working tree -- this is the test that BREAKS
the moment a pinned decision section drifts from what a carrier's escape
clause actually cites (mechanism N4, DAG validation-import); it is meant to
fail on real drift, not to be a synthetic fixture.

Run: python -m pytest tools/test_escape_check.py -q

RESOLVED OPEN QUESTION (see builder report, N4, docs/tasks/2026-07-21_validation-import.md,
open question #1): 2 of the 4 seeded escape_allowlist.json entries
(batching-blocking-self-execution/D-0081, retro-pair-journal/D-0056) cite a
carrier_anchor that, per the spec's literal text, is a single continuous
line -- but in the real CLAUDE.md that exact phrase is split by a markdown
soft line-wrap (a literal "\n" sits where the spec's anchor has a plain
space). Coordinator decision: leg (a) is a LIVENESS detector for the escape
clause (has it been deleted/substantively rewritten?), not a text-integrity
check -- that is leg (c)'s job via the section hash -- and carriers are
reflowable markdown, so a byte-exact anchor spanning a line-wrap point would
false-alarm on every reflow. Leg (a) now folds runs of whitespace
(space/tab/CR/LF) to a single space on BOTH sides of the containment check
before comparing (see escape_check._fold_whitespace() / module docstring
"Leg (a) contract"); this folding is scoped to leg (a) only -- legs (b)/(c)
keep the original CRLF/CR->LF-only normalization, so a decision section's
exact wording still hash-drifts on a whitespace-only reflow even though the
carrier anchor does not. The two previously-skipped live-repo tests are back
to plain (non-skipped) assertions below.

v3 (critic verdict fit_with_fixes, t-259): (1) retro-pair-journal was
repinned from D-0056 (a spec defect -- that section is Lead-tier-verification
text, not the retro-pair rule; CLAUDE.md's "(D-0056b)" was a dangling label
with no own DECISIONS_FULL.md section) to the new D-0089 (coordinator/Lead
fix, commit b00b279); carrier_anchor is unchanged (the norm's wording in
CLAUDE.md did not change, only the parenthetical decision tag). (2) hardening:
validate_entry_schema() now rejects a carrier_anchor that is non-empty but
folds to nothing/whitespace-only (see test_whitespace_only_carrier_anchor_*
below) -- such an anchor would make leg (a) vacuously true.

VG-2: a second, independent pin class -- judge_prompt_pin -- hash-pins
gateway/shadow_eval.py's JUDGE_SYSTEM_PROMPT to escape_allowlist.json's
top-level "judge_prompt_pin" section (AST-extracted, not imported: gateway/
modules use cwd-relative imports). Covered below: green path, drift (one
character changed after the digest was taken) with the exact recalibration
message, the section's ABSENCE from the allowlist (explicit fail, not a
silent pass), missing source file, symbol absent from source, duplicate
module-level assignment, a nested (non-module-level) same-named local NOT
matching, a non-string-literal value, a source syntax error, per-field
schema violations, a non-object pin, broken allowlist JSON (shared path),
CRLF/bare-CR source hashing identically to LF, and the --hash-judge-prompt
CLI mode (64-hex output, determinism, agreement with the real pin, usage
error on an extra argument). `_write_allowlist()`'s default now also writes
a valid judge_prompt_pin section transparently (see _default_judge_pin())
so every pre-existing, judge-pin-agnostic test in this file keeps passing
under the newly mandatory section without having to know it exists.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import escape_check as ec

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER_PATH = REPO_ROOT / "tools" / "escape_check.py"
REAL_ALLOWLIST_PATH = REPO_ROOT / "tools" / "escape_allowlist.json"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

DECISION_TEXT = (
    "preamble text, not part of any section\n"
    "\n"
    "## D-0001 -- first decision title\n"
    "body line one\n"
    "body line two\n"
    "\n"
    "## D-0002\n"
    "second decision body, no title suffix\n"
)

CARRIER_TEXT = (
    "Some prose leads in.\n"
    "ANCHOR-PHRASE-HERE is the load-bearing clause in this carrier file.\n"
    "More prose follows.\n"
)

# judge_prompt_pin (VG-2) fixtures: a tiny standalone "source" module with its
# own JUDGE_SYSTEM_PROMPT-alike constant, unrelated to CARRIER_TEXT/DECISION_TEXT
# above -- most existing tests don't care about this pin class at all, so
# _write_allowlist() below wires in a valid default pin automatically (see
# _default_judge_pin()) to keep them green without each one having to know
# about the new required section.
JUDGE_PROMPT_FIXTURE_TEXT = (
    "JUDGE_SYSTEM_PROMPT = (\n"
    "    \"fixture judge prompt line one \"\n"
    "    \"fixture judge prompt line two\"\n"
    ")\n"
)
JUDGE_PROMPT_FIXTURE_SYMBOL = "JUDGE_SYSTEM_PROMPT"
JUDGE_PROMPT_FIXTURE_SOURCE_NAME = "judge_source.py"


def _write_bytes(path, data):
    path.write_bytes(data)


def _write_text(path, text, encoding="utf-8"):
    path.write_bytes(text.encode(encoding))


def _make_tree(tmp_path, decision_text=DECISION_TEXT, carrier_text=CARRIER_TEXT):
    carrier = tmp_path / "CARRIER.md"
    decision = tmp_path / "DECISIONS.md"
    _write_text(carrier, carrier_text)
    _write_text(decision, decision_text)
    return carrier, decision


def _entry(**overrides):
    base = {
        "id": "sample-entry",
        "carrier_file": "CARRIER.md",
        "carrier_anchor": "ANCHOR-PHRASE-HERE",
        "decision_id": "D-0001",
        "decision_file": "DECISIONS.md",
        "section_sha256": None,  # filled by caller via real hash unless testing drift
        "affirmed": "2026-07-22",
        "note": "test fixture entry",
    }
    base.update(overrides)
    return base


def _real_digest(decision_text, decision_id):
    digest, status = ec.section_sha256(decision_text, decision_id)
    assert status == "ok", status
    return digest


_OMIT_JUDGE_PIN = object()


def _write_judge_source(tmp_path, text=JUDGE_PROMPT_FIXTURE_TEXT,
                         name=JUDGE_PROMPT_FIXTURE_SOURCE_NAME):
    p = tmp_path / name
    _write_text(p, text)
    return p


def _default_judge_pin(tmp_path, source_name=JUDGE_PROMPT_FIXTURE_SOURCE_NAME,
                        text=JUDGE_PROMPT_FIXTURE_TEXT,
                        symbol=JUDGE_PROMPT_FIXTURE_SYMBOL):
    """Write a valid judge-prompt fixture source file into tmp_path and
    return a judge_prompt_pin section dict whose sha256 actually matches
    it -- the default _write_allowlist() wires in so pre-existing,
    judge-pin-agnostic tests stay green under the new required section."""
    _write_judge_source(tmp_path, text, source_name)
    digest, status = ec.judge_prompt_sha256(text, symbol)
    assert status == "ok", status
    return {
        "source": source_name,
        "symbol": symbol,
        "sha256": digest,
        "evidence": "test fixture pin",
    }


def _write_allowlist(tmp_path, entries, name="allowlist.json",
                      judge_prompt_pin=_OMIT_JUDGE_PIN):
    """judge_prompt_pin: omit (default) for a valid auto-generated pin,
    None to omit the section entirely (tests the "section absent" case),
    or an explicit dict to test a broken/custom pin section."""
    if judge_prompt_pin is _OMIT_JUDGE_PIN:
        judge_prompt_pin = _default_judge_pin(tmp_path)
    root = {"entries": entries}
    if judge_prompt_pin is not None:
        root["judge_prompt_pin"] = judge_prompt_pin
    p = tmp_path / name
    p.write_bytes(json.dumps(root, ensure_ascii=False).encode("utf-8"))
    return p


def _run_cli(args, input_bytes=None, env=None):
    return subprocess.run(
        [sys.executable, str(CHECKER_PATH)] + args,
        cwd=str(REPO_ROOT),
        input=input_bytes,
        capture_output=True,
        timeout=15,
        env=env,
    )


# ---------------------------------------------------------------------------
# green path (all three legs alive)
# ---------------------------------------------------------------------------


def test_green_path_all_legs_alive(tmp_path):
    carrier, decision = _make_tree(tmp_path)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(section_sha256=digest)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok, errors
    assert count == 1


def test_green_path_multiple_entries(tmp_path):
    carrier, decision = _make_tree(tmp_path)
    d1 = _real_digest(DECISION_TEXT, "D-0001")
    d2 = _real_digest(DECISION_TEXT, "D-0002")
    entries = [
        _entry(id="e1", decision_id="D-0001", section_sha256=d1),
        _entry(id="e2", decision_id="D-0002", section_sha256=d2),
    ]
    allowlist = _write_allowlist(tmp_path, entries)

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok, errors
    assert count == 2


# ---------------------------------------------------------------------------
# leg (a): broken carrier anchor / missing carrier file
# ---------------------------------------------------------------------------


def test_broken_carrier_anchor_fails_and_names_entry(tmp_path):
    _make_tree(tmp_path)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(id="anchor-broken", carrier_anchor="THIS PHRASE IS NOT PRESENT", section_sha256=digest)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("anchor-broken" in e and "carrier leg failed" in e for e in errors)


def test_missing_carrier_file_fails(tmp_path):
    _make_tree(tmp_path)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(id="no-carrier", carrier_file="NOPE.md", section_sha256=digest)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("no-carrier" in e and "carrier leg failed" in e for e in errors)


# ---------------------------------------------------------------------------
# leg (a) whitespace-fold contract (coordinator decision, N4 open question #1
# follow-up): liveness detector, not a text-integrity check -- fold runs of
# space/tab/CR/LF to a single space on both sides before the containment
# check, scoped to leg (a) only.
# ---------------------------------------------------------------------------


def test_fold_whitespace_collapses_runs():
    assert ec._fold_whitespace("a   b\tc\r\nd\n\ne") == "a b c d e"


def test_anchor_spanning_carrier_linewrap_is_found(tmp_path):
    # spec-literal single-line anchor; carrier reflows it across a markdown
    # soft line-wrap -- exactly the batching-blocking-self-execution /
    # retro-pair-journal real-world case that opened this question.
    carrier_text = "Intro.\nthe quick brown\nfox jumps over lazy dogs.\nOutro.\n"
    _make_tree(tmp_path, carrier_text=carrier_text)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(
        id="wrap-ok",
        carrier_anchor="the quick brown fox jumps",
        section_sha256=digest,
    )
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok, errors


def test_anchor_with_double_space_matches_single_space_in_carrier(tmp_path):
    carrier_text = "Intro.\nalpha beta gamma delta.\nOutro.\n"
    _make_tree(tmp_path, carrier_text=carrier_text)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(
        id="dbl-space",
        carrier_anchor="alpha  beta   gamma",  # double/triple space in allowlist
        section_sha256=digest,
    )
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok, errors


def test_reordered_words_in_anchor_still_fails(tmp_path):
    # negative control: fold must NOT weaken detection of a substantively
    # rewritten/deleted clause -- only whitespace is folded, not word order.
    carrier_text = "Intro.\nalpha beta gamma delta.\nOutro.\n"
    _make_tree(tmp_path, carrier_text=carrier_text)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(
        id="reordered", carrier_anchor="alpha gamma beta", section_sha256=digest
    )
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("reordered" in e and "carrier leg failed" in e for e in errors)


def test_word_substitution_in_anchor_still_fails(tmp_path):
    # negative control, second variant: a changed (not just reordered) word.
    carrier_text = "Intro.\nalpha beta gamma delta.\nOutro.\n"
    _make_tree(tmp_path, carrier_text=carrier_text)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(
        id="substituted", carrier_anchor="alpha beta ZETA", section_sha256=digest
    )
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("substituted" in e and "carrier leg failed" in e for e in errors)


def test_hash_leg_stays_whitespace_sensitive_unlike_leg_a():
    # fixation test (coordinator ask #4): the fold is scoped STRICTLY to leg
    # (a) -- section_sha256() (legs (b)/(c)) must still change on a
    # whitespace-only reflow of the decision text (same words, different
    # line-wrap/spacing), unlike the now-fold-tolerant leg (a) anchor match.
    reflowed = DECISION_TEXT.replace(
        "body line one\nbody line two", "body line\none\nbody  line two"
    )
    original_digest = _real_digest(DECISION_TEXT, "D-0001")
    reflowed_digest, status = ec.section_sha256(reflowed, "D-0001")
    assert status == "ok"
    assert reflowed_digest != original_digest


# ---------------------------------------------------------------------------
# leg (b): missing decision section
# ---------------------------------------------------------------------------


def test_missing_decision_section_fails_and_names_entry_and_decision(tmp_path):
    _make_tree(tmp_path)
    entry = _entry(id="no-section", decision_id="D-0099", section_sha256="0" * 64)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "no-section" in e and "D-0099" in e and "not found" in e for e in errors
    )


def test_missing_decision_file_fails(tmp_path):
    _make_tree(tmp_path)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(id="no-decfile", decision_file="NOPE.md", section_sha256=digest)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("no-decfile" in e and "decision leg failed" in e for e in errors)


# ---------------------------------------------------------------------------
# leg (c): hash drift
# ---------------------------------------------------------------------------


def test_section_drift_fails_and_names_entry_and_decision(tmp_path):
    _make_tree(tmp_path)
    stale_digest = _real_digest(DECISION_TEXT, "D-0001")
    # amend the decision body after the digest was pinned -> drift
    drifted_text = DECISION_TEXT.replace("body line two", "body line two, EDITED")
    carrier, decision = _make_tree(tmp_path, decision_text=drifted_text)
    entry = _entry(id="drifted", section_sha256=stale_digest)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("drifted" in e and "D-0001" in e and "drift" in e for e in errors)


# ---------------------------------------------------------------------------
# duplicate section in the decision file
# ---------------------------------------------------------------------------


DUPLICATE_SECTION_TEXT = (
    "## D-0001\n"
    "first copy\n"
    "\n"
    "## D-0001 -- again\n"
    "second copy\n"
)


def test_duplicate_section_in_decision_file_fails_closed():
    section, status = ec.extract_decision_section(DUPLICATE_SECTION_TEXT, "D-0001")
    assert status == "duplicate"
    assert section is None


def test_duplicate_section_reported_via_run_validate(tmp_path):
    _make_tree(tmp_path, decision_text=DUPLICATE_SECTION_TEXT)
    entry = _entry(id="dup-section", section_sha256="0" * 64)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("dup-section" in e and "duplicated" in e for e in errors)


def test_near_miss_ids_do_not_match_word_boundary():
    text = "## D-00011\nnot the section\n\n## D-0001b\nalso not the section\n"
    section, status = ec.extract_decision_section(text, "D-0001")
    assert status == "not_found"


# ---------------------------------------------------------------------------
# duplicate id in the allowlist
# ---------------------------------------------------------------------------


def test_duplicate_id_in_allowlist_fails(tmp_path):
    _make_tree(tmp_path)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entries = [
        _entry(id="same-id", section_sha256=digest),
        _entry(id="same-id", section_sha256=digest),
    ]
    allowlist = _write_allowlist(tmp_path, entries)

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("duplicate entry id" in e and "same-id" in e for e in errors)


# ---------------------------------------------------------------------------
# broken JSON / non-object root / entries not a list
# ---------------------------------------------------------------------------


def test_broken_json_fails_closed(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_bytes(b"{not valid json,,,")
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("invalid JSON" in e for e in errors)


def test_root_array_instead_of_object_fails(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_bytes(b"[1, 2, 3]")
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("not an object" in e for e in errors)


def test_root_missing_entries_key_fails(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_bytes(json.dumps({"nope": []}).encode("utf-8"))
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("missing required field: entries" in e for e in errors)


def test_entries_not_a_list_fails(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_bytes(json.dumps({"entries": {"a": 1}}).encode("utf-8"))
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("must be an array" in e for e in errors)


def test_entry_not_an_object_fails(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_bytes(json.dumps({"entries": ["not-a-dict"]}).encode("utf-8"))
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("is not an object" in e for e in errors)


# ---------------------------------------------------------------------------
# per-field schema violations
# ---------------------------------------------------------------------------


def test_missing_required_field_named(tmp_path):
    _make_tree(tmp_path)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(id="missing-field", section_sha256=digest)
    del entry["carrier_anchor"]
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "missing-field" in e and "carrier_anchor" in e for e in errors
    )


def test_empty_string_id_fails():
    errors = ec.validate_entry_schema(_entry(id=""), 0)
    assert any("field 'id'" in e for e in errors)


def test_decision_id_bad_format_fails():
    errors = ec.validate_entry_schema(_entry(decision_id="D-56", section_sha256="0" * 64), 0)
    assert any("decision_id" in e for e in errors)


def test_decision_id_extra_digit_bad_format_fails():
    errors = ec.validate_entry_schema(_entry(decision_id="D-00561", section_sha256="0" * 64), 0)
    assert any("decision_id" in e for e in errors)


def test_section_sha256_wrong_length_fails():
    errors = ec.validate_entry_schema(_entry(section_sha256="abc123"), 0)
    assert any("section_sha256" in e for e in errors)


def test_section_sha256_uppercase_hex_fails():
    errors = ec.validate_entry_schema(_entry(section_sha256="A" * 64), 0)
    assert any("section_sha256" in e for e in errors)


def test_affirmed_bad_format_fails():
    errors = ec.validate_entry_schema(_entry(section_sha256="0" * 64, affirmed="22-07-2026"), 0)
    assert any("affirmed" in e for e in errors)


def test_affirmed_impossible_calendar_date_fails():
    errors = ec.validate_entry_schema(_entry(section_sha256="0" * 64, affirmed="2026-02-30"), 0)
    assert any("affirmed" in e for e in errors)


def test_note_wrong_type_fails():
    errors = ec.validate_entry_schema(_entry(section_sha256="0" * 64, note=123), 0)
    assert any("note" in e for e in errors)


def test_note_absent_is_valid():
    entry = _entry(section_sha256="0" * 64)
    del entry["note"]
    errors = ec.validate_entry_schema(entry, 0)
    assert errors == []


def test_carrier_file_empty_string_fails():
    errors = ec.validate_entry_schema(_entry(carrier_file="", section_sha256="0" * 64), 0)
    assert any("carrier_file" in e for e in errors)


def test_whitespace_only_carrier_anchor_fails_schema():
    # critic finding #2, N4 v3: non-empty but whitespace-only anchor folds
    # to "" and would make leg (a) vacuously true (substring of anything).
    errors = ec.validate_entry_schema(
        _entry(carrier_anchor="   \t\n  ", section_sha256="0" * 64), 0
    )
    assert any(
        "carrier_anchor" in e and "non-whitespace" in e for e in errors
    )


def test_single_space_carrier_anchor_fails_schema():
    errors = ec.validate_entry_schema(
        _entry(carrier_anchor=" ", section_sha256="0" * 64), 0
    )
    assert any(
        "carrier_anchor" in e and "non-whitespace" in e for e in errors
    )


def test_whitespace_only_carrier_anchor_rejected_via_run_validate(tmp_path):
    _make_tree(tmp_path)
    entry = _entry(id="ws-anchor", carrier_anchor="   ", section_sha256="0" * 64)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "ws-anchor" in e and "carrier_anchor" in e and "non-whitespace" in e
        for e in errors
    )


# ---------------------------------------------------------------------------
# empty entries -> OK 0
# ---------------------------------------------------------------------------


def test_empty_entries_is_ok_zero(tmp_path):
    allowlist = _write_allowlist(tmp_path, [])
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok, errors
    assert count == 0


def test_cli_empty_entries_prints_ok_zero(tmp_path):
    allowlist = _write_allowlist(tmp_path, [], name="escape_allowlist.json")
    # exercise run_validate directly with the same message format the CLI uses
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok and count == 0
    message = "ESCAPE ALLOWLIST OK: %d entries" % count
    assert message == "ESCAPE ALLOWLIST OK: 0 entries"


# ---------------------------------------------------------------------------
# CRLF/LF hash-normalization equivalence
# ---------------------------------------------------------------------------


def test_crlf_and_lf_decision_file_hash_identically():
    lf_text = DECISION_TEXT
    crlf_text = DECISION_TEXT.replace("\n", "\r\n")
    digest_lf, status_lf = ec.section_sha256(lf_text, "D-0001")
    digest_crlf, status_crlf = ec.section_sha256(crlf_text, "D-0001")
    assert status_lf == status_crlf == "ok"
    assert digest_lf == digest_crlf


def test_bare_cr_decision_file_hashes_same_as_lf():
    lf_text = DECISION_TEXT
    cr_text = DECISION_TEXT.replace("\n", "\r")
    digest_lf, status_lf = ec.section_sha256(lf_text, "D-0001")
    digest_cr, status_cr = ec.section_sha256(cr_text, "D-0001")
    assert status_lf == status_cr == "ok"
    assert digest_lf == digest_cr


# ---------------------------------------------------------------------------
# section at end of file with no trailing newline
# ---------------------------------------------------------------------------


def test_section_at_eof_no_trailing_newline():
    text = "## D-0001\nbody without a trailing newline"
    section, status = ec.extract_decision_section(text, "D-0001")
    assert status == "ok"
    assert section == "## D-0001\nbody without a trailing newline"


def test_section_at_eof_with_trailing_blank_lines_are_trimmed():
    text = "## D-0001\nbody\n\n\n"
    section, status = ec.extract_decision_section(text, "D-0001")
    assert status == "ok"
    assert section == "## D-0001\nbody"


def test_header_only_section_no_body():
    text = "## D-0001\n\n## D-0002\nbody\n"
    section, status = ec.extract_decision_section(text, "D-0001")
    assert status == "ok"
    assert section == "## D-0001"


# ---------------------------------------------------------------------------
# non-UTF-8 bytes: allowlist file, decision file, carrier file
# ---------------------------------------------------------------------------


def test_non_utf8_allowlist_file_fails_closed(tmp_path):
    p = tmp_path / "allowlist.json"
    p.write_bytes(bytes([0xFF, 0xFE, 0x80, 0x81]) * 10)
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("not valid UTF-8" in e for e in errors)
    # ASCII-only diagnostic
    "\n".join(errors).encode("ascii")


def test_non_utf8_decision_file_fails_closed(tmp_path):
    carrier, decision = _make_tree(tmp_path)
    decision.write_bytes(bytes([0xFF, 0xFE, 0x80, 0x81]) * 10)
    entry = _entry(section_sha256="0" * 64)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("not valid UTF-8" in e for e in errors)
    "\n".join(errors).encode("ascii")


def test_non_utf8_carrier_file_fails_closed(tmp_path):
    carrier, decision = _make_tree(tmp_path)
    carrier.write_bytes(bytes([0xFF, 0xFE, 0x80, 0x81]) * 10)
    digest = _real_digest(DECISION_TEXT, "D-0001")
    entry = _entry(section_sha256=digest)
    allowlist = _write_allowlist(tmp_path, [entry])

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("not valid UTF-8" in e for e in errors)
    "\n".join(errors).encode("ascii")


def test_non_ascii_id_diagnostic_stays_ascii(tmp_path):
    _make_tree(tmp_path)
    entry = _entry(id="дефект-якоря", carrier_anchor="NOT PRESENT", section_sha256="0" * 64)
    allowlist = _write_allowlist(tmp_path, [entry])
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    "\n".join(errors).encode("ascii")  # raises UnicodeEncodeError if not ASCII


# ---------------------------------------------------------------------------
# CLI contract: exit codes, unknown flag, argument-count boundaries
# ---------------------------------------------------------------------------


def test_cli_unknown_flag_exit_2():
    result = _run_cli(["--nope"])
    assert result.returncode == 2
    assert b"usage" in result.stderr


def test_cli_hash_flag_missing_argument_exit_2():
    result = _run_cli(["--hash"])
    assert result.returncode == 2


def test_cli_hash_flag_too_many_arguments_exit_2():
    result = _run_cli(["--hash", "D-0001", "extra"])
    assert result.returncode == 2


def test_cli_hash_nonexistent_decision_exit_1():
    result = _run_cli(["--hash", "D-9999"])
    assert result.returncode == 1
    assert b"not found" in result.stderr


def test_cli_hash_existing_decision_exit_0_prints_64_hex():
    result = _run_cli(["--hash", "D-0037"])
    assert result.returncode == 0
    out = result.stdout.decode("ascii").strip()
    assert len(out) == 64
    int(out, 16)  # raises ValueError if not hex


def test_cli_hash_is_deterministic_across_runs():
    r1 = _run_cli(["--hash", "D-0037"])
    r2 = _run_cli(["--hash", "D-0037"])
    assert r1.returncode == r2.returncode == 0
    assert r1.stdout == r2.stdout


def test_cli_no_args_output_is_ascii_regardless_of_verdict():
    result = _run_cli([])
    (result.stdout + result.stderr).decode("ascii")


def test_cli_stdin_invalid_bytes_do_not_affect_hash_mode():
    # --hash mode never reads stdin; feeding it garbage must not crash it.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = _run_cli(["--hash", "D-0037"], input_bytes=bytes([0xFF, 0xFE]) * 5, env=env)
    assert result.returncode == 0


# ---------------------------------------------------------------------------
# judge_prompt_pin (VG-2): AST-extracted JUDGE_SYSTEM_PROMPT hash-pinned to
# escape_allowlist.json's top-level "judge_prompt_pin" section, so a silent
# drift of gateway/shadow_eval.py's judge prompt invalidates check 30(a)'s
# calibration (t-254, D-0031) mechanically instead of by discipline alone.
# ---------------------------------------------------------------------------


def test_judge_prompt_pin_green_path(tmp_path):
    _make_tree(tmp_path)  # unrelated CARRIER/DECISIONS files; entries=[] below
    allowlist = _write_allowlist(tmp_path, [])
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert ok, errors


def test_judge_prompt_pin_drift_fails_with_recalibration_message(tmp_path):
    # pin computed against the ORIGINAL fixture text, but the source file on
    # disk is written with one character changed after the digest was taken
    # -- exactly the "single symbol changed" DoD case.
    pin = _default_judge_pin(tmp_path)
    drifted_text = JUDGE_PROMPT_FIXTURE_TEXT.replace("line two", "line TWO")
    _write_judge_source(tmp_path, text=drifted_text)
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)

    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "JUDGE_SYSTEM_PROMPT drifted from pinned hash" in e
        and "re-calibration" in e
        and "D-0031" in e
        for e in errors
    )


def test_judge_prompt_pin_missing_section_fails_explicitly(tmp_path):
    _make_tree(tmp_path)
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=None)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("missing required section: judge_prompt_pin" in e for e in errors)


def test_judge_prompt_pin_source_file_missing_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    pin["source"] = "NOPE_NOT_A_REAL_FILE.py"
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("judge_prompt_pin: source leg failed" in e for e in errors)


def test_judge_prompt_pin_symbol_absent_in_source_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    _write_judge_source(tmp_path, text="OTHER_NAME = 'not the judge prompt'\n")
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "judge_prompt_pin" in e and "not found" in e and JUDGE_PROMPT_FIXTURE_SYMBOL in e
        for e in errors
    )


def test_judge_prompt_pin_duplicate_symbol_assignment_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    dup_text = (
        "JUDGE_SYSTEM_PROMPT = 'first'\n"
        "JUDGE_SYSTEM_PROMPT = 'second'\n"
    )
    _write_judge_source(tmp_path, text=dup_text)
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("judge_prompt_pin" in e and "assigned more than once" in e for e in errors)


def test_judge_prompt_pin_not_a_string_literal_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    _write_judge_source(tmp_path, text="JUDGE_SYSTEM_PROMPT = 'a' + 'b'\n")
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("judge_prompt_pin" in e and "not a string literal" in e for e in errors)


def test_judge_prompt_pin_syntax_error_in_source_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    _write_judge_source(tmp_path, text="def broken(:\n    pass\n")
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("judge_prompt_pin" in e and "syntax error" in e for e in errors)


def test_judge_prompt_pin_nested_assignment_not_matched(tmp_path):
    # module-level match only: a same-named local inside a function must
    # not be mistaken for the pinned constant.
    pin = _default_judge_pin(tmp_path)
    nested_text = (
        "def f():\n"
        "    JUDGE_SYSTEM_PROMPT = 'local, not the pinned constant'\n"
        "    return JUDGE_SYSTEM_PROMPT\n"
    )
    _write_judge_source(tmp_path, text=nested_text)
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("judge_prompt_pin" in e and "not found" in e for e in errors)


def test_judge_prompt_pin_not_an_object_fails(tmp_path):
    _make_tree(tmp_path)
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin="not-an-object")
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any("judge_prompt_pin' is not an object" in e for e in errors)


def test_judge_prompt_pin_missing_field_named(tmp_path):
    pin = _default_judge_pin(tmp_path)
    del pin["evidence"]
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "judge_prompt_pin: missing required field: evidence" in e for e in errors
    )


def test_judge_prompt_pin_sha256_wrong_length_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    pin["sha256"] = "abc123"
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "judge_prompt_pin: field 'sha256' must be 64 lowercase hex" in e
        for e in errors
    )


def test_judge_prompt_pin_sha256_uppercase_hex_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    pin["sha256"] = "A" * 64
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "judge_prompt_pin: field 'sha256' must be 64 lowercase hex" in e
        for e in errors
    )


def test_judge_prompt_pin_empty_string_field_fails(tmp_path):
    pin = _default_judge_pin(tmp_path)
    pin["source"] = ""
    allowlist = _write_allowlist(tmp_path, [], judge_prompt_pin=pin)
    ok, errors, count = ec.run_validate(str(allowlist), str(tmp_path))
    assert not ok
    assert any(
        "judge_prompt_pin: field 'source' must be a non-empty string" in e
        for e in errors
    )


def test_judge_prompt_pin_broken_allowlist_json_fails_closed(tmp_path):
    # shared with the generic broken-JSON path (test_broken_json_fails_closed
    # above) -- restated here under the judge-pin battery per the DoD's
    # explicit adversarial list; the judge_prompt_pin check never runs when
    # the JSON itself doesn't parse (fails closed before any section check).
    p = tmp_path / "allowlist.json"
    p.write_bytes(b"{not valid json,,,")
    ok, errors, count = ec.run_validate(str(p), str(tmp_path))
    assert not ok
    assert any("invalid JSON" in e for e in errors)


def test_judge_prompt_pin_crlf_source_hashes_identically_to_lf():
    lf_text = JUDGE_PROMPT_FIXTURE_TEXT
    crlf_text = JUDGE_PROMPT_FIXTURE_TEXT.replace("\n", "\r\n")
    digest_lf, status_lf = ec.judge_prompt_sha256(lf_text, JUDGE_PROMPT_FIXTURE_SYMBOL)
    digest_crlf, status_crlf = ec.judge_prompt_sha256(crlf_text, JUDGE_PROMPT_FIXTURE_SYMBOL)
    assert status_lf == status_crlf == "ok"
    assert digest_lf == digest_crlf


def test_judge_prompt_pin_bare_cr_source_hashes_same_as_lf():
    lf_text = JUDGE_PROMPT_FIXTURE_TEXT
    cr_text = JUDGE_PROMPT_FIXTURE_TEXT.replace("\n", "\r")
    digest_lf, status_lf = ec.judge_prompt_sha256(lf_text, JUDGE_PROMPT_FIXTURE_SYMBOL)
    digest_cr, status_cr = ec.judge_prompt_sha256(cr_text, JUDGE_PROMPT_FIXTURE_SYMBOL)
    assert status_lf == status_cr == "ok"
    assert digest_lf == digest_cr


def test_judge_prompt_pin_real_repo_hash_matches_pinned_value():
    # dedicated live-repo check for THIS pin class (mirrors
    # test_live_repo_allowlist_is_valid_against_real_tree below, which
    # already covers this via the full run_validate() path) -- verifies the
    # --hash-judge-prompt CLI mode agrees with the value pinned in the real
    # escape_allowlist.json, the same "human paste == recomputed" guarantee
    # --hash D-XXXX gives for decision sections.
    with open(REAL_ALLOWLIST_PATH, "r", encoding="utf-8") as fh:
        real_root = json.load(fh)
    pinned = real_root["judge_prompt_pin"]["sha256"]
    result = _run_cli(["--hash-judge-prompt"])
    assert result.returncode == 0
    assert result.stdout.decode("ascii").strip() == pinned


def test_cli_hash_judge_prompt_prints_64_hex():
    result = _run_cli(["--hash-judge-prompt"])
    assert result.returncode == 0
    out = result.stdout.decode("ascii").strip()
    assert len(out) == 64
    int(out, 16)  # raises ValueError if not hex


def test_cli_hash_judge_prompt_is_deterministic_across_runs():
    r1 = _run_cli(["--hash-judge-prompt"])
    r2 = _run_cli(["--hash-judge-prompt"])
    assert r1.returncode == r2.returncode == 0
    assert r1.stdout == r2.stdout


def test_cli_hash_judge_prompt_extra_argument_exit_2():
    result = _run_cli(["--hash-judge-prompt", "extra"])
    assert result.returncode == 2
    assert b"usage" in result.stderr


# ---------------------------------------------------------------------------
# live-repo anchor test (mechanism N4, DAG validation-import): the real
# tools/escape_allowlist.json must validate clean against the real working
# tree. This is the test designed to BREAK the moment a pinned decision
# section drifts from the carrier clause it authorizes -- that is its job,
# not a defect in the test.
# ---------------------------------------------------------------------------


def test_live_repo_allowlist_is_valid_against_real_tree():
    ok, errors, count = ec.run_validate(str(REAL_ALLOWLIST_PATH), str(REPO_ROOT))
    assert ok, errors
    assert count == 4


def test_cli_live_repo_run_prints_ok_four_entries():
    result = _run_cli([])
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout.strip() == b"ESCAPE ALLOWLIST OK: 4 entries"
