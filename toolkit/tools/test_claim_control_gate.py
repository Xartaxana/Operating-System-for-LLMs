"""Tests for tools/claim_control_gate.py -- half B of the ported
negative-claim correlation gate (source: HQ's own
tools/claim_control_gate.py; half A: tools/search_control_gate.py
writes the session search ledger this module reads).

THIS TEMPLATE'S ADAPTATION: ROOT_FILES is rescoped to this template's
own root-level policy carriers -- see `test_in_scope_prefixes` below
(no ROADMAP/ARCHITECTURE*/WHITE_PAPER/PROJECT_*/ANTI_GOALS.md; adds
INSTALL.md, ADOPTION_LEDGER.template.md, delegation.config.yaml).

Run from the repo root: python -m pytest toolkit/tools/test_claim_control_gate.py -q
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import claim_control_gate as m  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "claim_control_gate.py"


def _run_hook(payload, ledger_dir=None, raw_input=None):
    env = os.environ.copy()
    if ledger_dir is not None:
        env["SEARCH_CONTROL_GATE_LEDGER_DIR"] = str(ledger_dir)
    else:
        env.pop("SEARCH_CONTROL_GATE_LEDGER_DIR", None)
    if raw_input is not None:
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=raw_input,
            capture_output=True,
            env=env,
        )
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def _write_ledger(ledger_dir, session, terms):
    ledger_dir = Path(ledger_dir)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{session}.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for term in terms:
            fh.write(
                json.dumps(
                    {"ts": "2026-07-28T00:00:00", "tool": "Grep", "term": term, "empty": False},
                    ensure_ascii=False,
                )
                + "\n"
            )


def _write_payload(path, text, session_id="sess-1"):
    return {
        "session_id": session_id,
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": text},
    }


# ---------------------------------------------------------------------
# regression, verbatim from HQ's own incident (module docstring /
# CLAUDE.md command hygiene point 6): a claim that a named doc "this
# deployment does not have" although nothing in that session ever
# searched for its token.
# ---------------------------------------------------------------------


def test_f5_regression_empty_ledger_warns_related_work(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        "check 16 names a RELATED_WORK section this deployment does not have",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() != ""
    data = json.loads(result.stdout)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert "RELATED_WORK" in ctx
    assert data["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert "permissionDecision" not in data


def test_f5_regression_ledger_with_matching_search_silences(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["docs/RELATED_WORK.md"])
    payload = _write_payload(
        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        "check 16 names a RELATED_WORK section this deployment does not have",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# out of scope: a vault/ path is never in scope, regardless of content
# ---------------------------------------------------------------------


def test_vault_path_out_of_scope_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "vault/wiki/some-page.md",
        "the RELATED_WORK section does not exist",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# no extractable token near the marker -- silent, nothing invented
# ---------------------------------------------------------------------


def test_no_extractable_token_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("docs/notes.md", "nothing was found here")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_ordinary_word_near_marker_silent_no_token_invented(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("docs/notes.md", "the feature does not exist yet")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# Russian marker + path-like token
# ---------------------------------------------------------------------


def test_russian_marker_with_path_token_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "DECISIONS.md",
        "модуль docs/RELATED_WORK.md отсутствует в репозитории",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    ctx = data["hookSpecificOutput"]["additionalContext"]
    assert "docs/RELATED_WORK.md" in ctx


def test_russian_marker_with_path_token_silenced_by_ledger(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["docs/RELATED_WORK.md"])
    payload = _write_payload(
        "DECISIONS.md",
        "модуль docs/RELATED_WORK.md отсутствует в репозитории",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# tool scoping, Edit vs Write field extraction
# ---------------------------------------------------------------------


def test_non_edit_write_tool_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-1",
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
    }
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_edit_tool_new_string_extracted_and_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-1",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
            "old_string": "old",
            "new_string": "check 16 names a RELATED_WORK section this deployment does not have",
        },
    }
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "RELATED_WORK" in data["hookSpecificOutput"]["additionalContext"]


def test_write_tool_missing_content_key_silent_no_crash(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = {
        "session_id": "sess-1",
        "tool_name": "Write",
        "tool_input": {"file_path": "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md"},
    }
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# session unknown -> read every ledger file (prefer reading more; a
# false silence is acceptable here, a false accusation is not)
# ---------------------------------------------------------------------


def test_unknown_session_reads_all_ledger_files(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "some-other-session", ["docs/RELATED_WORK.md"])
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
            "content": "check 16 names a RELATED_WORK section this deployment does not have",
        },
        # no session_id key at all
    }
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# exit code 0 on every path, including malformed JSON / non-dict payload
# ---------------------------------------------------------------------


def test_exit_zero_on_malformed_json(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"{not valid json")
    assert result.returncode == 0
    assert result.stdout.decode("utf-8", errors="replace").strip() == ""


def test_exit_zero_on_non_dict_payload(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook([1, 2, 3], ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_exit_zero_on_empty_stdin(tmp_path):
    ledger_dir = tmp_path / "ledger"
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=b"")
    assert result.returncode == 0


# ---------------------------------------------------------------------
# adversarial battery (interactive-surface DoD): invalid UTF-8 bytes, a
# ~1MB write payload, the stdin TTY guard.
# ---------------------------------------------------------------------


def test_adversarial_invalid_utf8_bytes_no_crash(tmp_path):
    ledger_dir = tmp_path / "ledger"
    raw = (
        b'{"tool_name": "Write", "tool_input": {"file_path": "DECISIONS.md", '
        b'"content": "\xff\xfe broken does not exist"}}'
    )
    result = _run_hook(None, ledger_dir=ledger_dir, raw_input=raw)
    assert result.returncode == 0


def test_adversarial_very_large_write_payload_no_crash(tmp_path):
    # Marker-DENSE payload (many occurrences + many boundaries), not
    # just a large blob without markers -- this is the form that
    # actually loads _sentence_window / _find_claim_token_groups.
    ledger_dir = tmp_path / "ledger"
    unit = "the file docs/RELATED_WORK.md does not exist. "
    content = unit * (150_000 // len(unit) + 1)
    payload = _write_payload("DECISIONS.md", content)
    import time

    started = time.monotonic()
    result = _run_hook(payload, ledger_dir=ledger_dir)
    elapsed = time.monotonic() - started
    assert result.returncode == 0
    # Generous ceiling (subprocess overhead included) -- catches a real
    # complexity regression without being flaky on a loaded CI box.
    assert elapsed < 5.0


def test_read_stdin_bytes_tty_guard_no_block(monkeypatch):
    class FakeStdin:
        def isatty(self):
            return True

    monkeypatch.setattr(m.sys, "stdin", FakeStdin())
    assert m._read_stdin_bytes() == b""


# ---------------------------------------------------------------------
# D1 matrix: overlapping tokens from ONE span must be grouped and
# satisfied by ANY member -- exercised across every recorded search FORM
# separately (a ledger fixture satisfying all forms at once would mask
# a grouping regression).
# ---------------------------------------------------------------------


_D1_CLAIM_TEXT = "the file docs/RELATED_WORK.md does not exist"


def test_d1_matrix_five_recorded_forms_all_silence_the_group(tmp_path):
    payload = _write_payload("DECISIONS.md", _D1_CLAIM_TEXT)
    forms = {
        "grep_tool_pattern": "RELATED_WORK",
        "bash_grep_rn": "grep -rn RELATED_WORK docs/",
        "bash_rg": "rg RELATED_WORK",
        "bash_find_name": "find . -name RELATED_WORK.md",
        "glob_pattern": "docs/RELATED_WORK.md",
    }
    for label, recorded_term in forms.items():
        ledger_dir = tmp_path / f"ledger-{label}"
        _write_ledger(ledger_dir, "sess-1", [recorded_term])
        result = _run_hook(payload, ledger_dir=ledger_dir)
        assert result.returncode == 0
        assert result.stdout.strip() == "", (
            f"form {label!r} (recorded term {recorded_term!r}) unexpectedly "
            f"warned: {result.stdout}"
        )


def test_d1_matrix_empty_ledger_still_warns(tmp_path):
    ledger_dir = tmp_path / "ledger-empty"
    payload = _write_payload("DECISIONS.md", _D1_CLAIM_TEXT)
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() != ""
    data = json.loads(result.stdout)
    assert "RELATED_WORK" in data["hookSpecificOutput"]["additionalContext"]


# ---------------------------------------------------------------------
# D5: widened marker lexicon -- new English paraphrases and new
# Russian markers must trigger the same as the original set.
# ---------------------------------------------------------------------


def test_d5_new_english_marker_has_no_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "the RELATED_WORK module has no matching entry"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_d5_new_english_marker_lacks_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "the RELATED_WORK section lacks detail here"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_d5_new_russian_marker_net_space_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "DECISIONS.md", "модуль RELATED_WORK нет в репозитории"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_d5_new_russian_marker_ne_udalos_nayti_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "DECISIONS.md", "не удалось найти файл docs/RELATED_WORK.md нигде"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


# ---------------------------------------------------------------------
# D6: session-specific ledger read must UNION unknown.jsonl, not
# read only <session>.jsonl -- a search recorded before session_id was
# ever observed present must still count.
# ---------------------------------------------------------------------


def test_d6_session_specific_read_unions_unknown_jsonl(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "unknown", ["docs/RELATED_WORK.md"])
    payload = _write_payload(
        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        "check 16 names a RELATED_WORK section this deployment does not have",
        session_id="sess-specific-and-different",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------
# D7: minimum recorded-term length + boundary-aware matching, INCLUDING
# the boundary itself (MIN_TERM_LEN=3): length 2 (below), length 3 (at
# threshold), length 4 (above) -- rule 6a of the builder role
# (a limit/boundary always gets an AT and a BEYOND test).
# ---------------------------------------------------------------------


def test_d7_min_term_length_rejects_generic_short_terms(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["py", "_"])
    payload = _write_payload(
        "docs/notes.md", "the script escape_check.py does not exist"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() != ""


def test_d7_boundary_aware_rejects_substring_inside_longer_identifier(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["grep -rn RELATED_WORKFLOW_NOTES vault/"])
    payload = _write_payload(
        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        "check 16 names a RELATED_WORK section this deployment does not have",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() != ""


def test_d7_boundary_aware_positive_control_still_matches(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["grep -rn RELATED_WORK vault/"])
    payload = _write_payload(
        "PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md",
        "check 16 names a RELATED_WORK section this deployment does not have",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_min_term_len_boundary_length_two_below_threshold_rejected():
    # length 2 < MIN_TERM_LEN(3) -- must not count as evidence in
    # either direction (needle-side check in _boundary_contains, and
    # the term-side pre-filter in _token_satisfied).
    assert not m._boundary_contains("ab something", "ab")
    assert not m._token_satisfied("xyz", ["ab"])


def test_min_term_len_boundary_length_three_at_threshold_accepted():
    # length 3 == MIN_TERM_LEN -- AT the boundary, must count.
    assert m._boundary_contains("see abc here", "abc")
    assert m._token_satisfied("abc", ["abc"])


def test_min_term_len_boundary_length_four_above_threshold_accepted():
    # length 4 > MIN_TERM_LEN -- past the boundary, must count.
    assert m._boundary_contains("see abcd here", "abcd")
    assert m._token_satisfied("abcd", ["abcd"])


# ---------------------------------------------------------------------
# D8: case-variant path and Git-Bash POSIX-drive absolute path.
# ---------------------------------------------------------------------


def test_d8_case_variant_path_in_scope():
    assert m._in_scope("Docs/notes.md")
    assert m._in_scope("Process/weekly.md")
    assert m._in_scope("decisions.md")  # lowercase root-file name


def test_d8_posix_drive_absolute_path_in_scope():
    drive = m.REPO[0].lower()
    rest = m.REPO[2:].replace("\\", "/")
    posix_repo = f"/{drive}{rest}"
    assert m._in_scope(posix_repo + "/docs/notes.md")
    assert m._in_scope(posix_repo + "/PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md")


def test_d8_posix_drive_absolute_path_warns_via_full_pipeline(tmp_path):
    ledger_dir = tmp_path / "ledger"
    drive = m.REPO[0].lower()
    rest = m.REPO[2:].replace("\\", "/")
    posix_path = f"/{drive}{rest}/DECISIONS.md"
    payload = _write_payload(posix_path, _D1_CLAIM_TEXT)
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


# ---------------------------------------------------------------------
# markers now match by word boundary: false forms must stay silent,
# real negatives must still fire. Unit level (the regex itself) + full
# pipeline (with a real extractable token nearby, otherwise
# _find_claim_token_groups gives no groups at all -- a separate,
# unrelated layer).
# ---------------------------------------------------------------------


def _marker_pattern(marker):
    return dict(m._MARKER_PATTERNS)[marker]


def test_marker_net_does_not_match_stanet_unit():
    assert _marker_pattern("нет ").search("он станет причиной") is None


def test_marker_net_does_not_match_internet_unit():
    assert _marker_pattern("нет ").search("проверь интернет и тест") is None


def test_marker_net_does_not_match_dostanet_unit():
    assert _marker_pattern("нет ").search("он достанет файл") is None


def test_marker_has_no_does_not_match_has_notes_unit():
    assert _marker_pattern("has no").search("the module has notes") is None


def test_marker_net_still_matches_real_negative_unit():
    assert _marker_pattern("нет ").search("файла нет в репо") is not None


def test_marker_has_no_still_matches_real_negative_unit():
    assert _marker_pattern("has no").search("has no tests") is not None


def test_otsutstvu_stem_marker_unaffected_unit():
    # Intentional exception (see _MARKER_NO_SUFFIX_BOUNDARY): the marker
    # -- a stem with no right word-edge -- must still match inside
    # its own inflected form asserted below.
    assert _marker_pattern("отсутству").search("файл отсутствует здесь") is not None


def test_full_pipeline_false_positive_stanet_with_token_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "модуль docs/RELATED_WORK.md станет важным позже"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_full_pipeline_false_positive_internet_with_token_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "модуль docs/RELATED_WORK.md проверь через интернет позже"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_full_pipeline_false_positive_dostanet_with_token_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "модуль docs/RELATED_WORK.md он достанет из архива позже"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_full_pipeline_false_positive_has_notes_with_token_silent(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "the module config.py has notes about usage"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_full_pipeline_real_negative_net_with_token_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload("docs/notes.md", "файла docs/RELATED_WORK.md нет в репо")
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_full_pipeline_real_negative_has_no_tests_with_token_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "the module config.py has no tests written"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "config.py" in result.stdout


# ---------------------------------------------------------------------
# decide() / helper unit coverage -- pure logic, no subprocess needed
# ---------------------------------------------------------------------


def test_decide_non_dict_payload_silent_pass():
    assert m.decide([1, 2, 3]) == (0, None)


def test_in_scope_prefixes():
    # This template's own ROOT_FILES (spec adaptation): no
    # ROADMAP/ARCHITECTURE*/WHITE_PAPER/PROJECT_*/ANTI_GOALS.md; adds
    # INSTALL.md/ADOPTION_LEDGER.template.md/delegation.config.yaml.
    assert m._in_scope("PROCESS/WEEKLY_CALIBRATION_PROTOCOL.md")
    assert m._in_scope("docs/RELATED_WORK.md")
    assert m._in_scope("logs/routing-log.jsonl")
    assert m._in_scope("CLAUDE.md")
    assert m._in_scope("BOOT.md")
    assert m._in_scope("DECISIONS.md")
    assert m._in_scope("DELEGATION_TABLE.md")
    assert m._in_scope("INSTALL.md")
    assert m._in_scope("README.md")
    assert m._in_scope("SYSTEM_PROMPT.md")
    assert m._in_scope("CURRENT_CONTEXT.md")
    assert m._in_scope("ADOPTION_LEDGER.template.md")
    assert m._in_scope("delegation.config.yaml")
    assert not m._in_scope("ROADMAP.md")  # this template has no ROADMAP.md
    assert not m._in_scope("ARCHITECTURE.md")
    assert not m._in_scope("WHITE_PAPER.md")
    assert not m._in_scope("ANTI_GOALS.md")
    # docs/FINDINGS.md is not a ROOT_FILES entry, but it IS under the
    # docs/ prefix (in scope regardless of ROOT_FILES membership) --
    # this template has no such file today, the prefix rule is general.
    assert m._in_scope("docs/FINDINGS.md")
    assert not m._in_scope("vault/wiki/page.md")
    assert not m._in_scope("tools/hygiene_gate.py")
    assert not m._in_scope("logs/other-file.jsonl")
    assert not m._in_scope("")
    assert not m._in_scope(None)


def test_in_scope_absolute_windows_style_path():
    abs_path = str(Path(m.REPO) / "PROCESS" / "WEEKLY_CALIBRATION_PROTOCOL.md")
    assert m._in_scope(abs_path)


def test_in_scope_absolute_out_of_repo_path_is_out_of_scope():
    assert not m._in_scope("C:/somewhere/else/PROCESS/file.md")


def test_token_satisfied_both_directions():
    assert m._token_satisfied("RELATED_WORK", ["docs/RELATED_WORK.md"])
    assert m._token_satisfied("docs/RELATED_WORK.md", ["RELATED_WORK"])
    assert not m._token_satisfied("RELATED_WORK", ["something-else.md"])


def test_extract_tokens_upper_snake_and_path_and_ext():
    tokens = m._extract_tokens(
        "see docs/RELATED_WORK.md and also SKIP_RE in config.py"
    )
    assert "docs/RELATED_WORK.md" in tokens
    assert "SKIP_RE" in tokens
    assert "config.py" in tokens


def test_extract_tokens_ordinary_words_not_captured():
    assert m._extract_tokens("this is just an ordinary sentence") == set()


# ---------------------------------------------------------------------
# D1/D7 unit coverage: grouping and boundary-aware matching
# ---------------------------------------------------------------------


def test_group_overlapping_spans_merges_nested_matches():
    window = "see docs/RELATED_WORK.md for detail"
    spans = m._extract_token_spans(window)
    groups = m._group_overlapping_spans(spans)
    assert len(groups) == 1
    assert groups[0] == frozenset(
        {"docs/RELATED_WORK.md", "RELATED_WORK.md", "RELATED_WORK"}
    )


def test_group_overlapping_spans_keeps_disjoint_tokens_separate():
    window = "see docs/RELATED_WORK.md and also SKIP_RE separately"
    spans = m._extract_token_spans(window)
    groups = m._group_overlapping_spans(spans)
    group_sets = set(groups)
    assert frozenset({"docs/RELATED_WORK.md", "RELATED_WORK.md", "RELATED_WORK"}) in group_sets
    assert frozenset({"SKIP_RE"}) in group_sets
    assert len(groups) == 2


def test_boundary_contains_rejects_embedded_substring():
    assert not m._boundary_contains("RELATED_WORKFLOW_NOTES", "RELATED_WORK")
    assert m._boundary_contains("docs/RELATED_WORK.md", "RELATED_WORK")
    assert m._boundary_contains("grep -rn RELATED_WORK vault/", "RELATED_WORK")


def test_boundary_contains_rejects_below_min_length():
    assert not m._boundary_contains("some escape_check.py text", "py")


# ---------------------------------------------------------------------
# D4b unit coverage: sentence-scoped windowing does not fracture
# a path/dotted token on its own internal dot.
# ---------------------------------------------------------------------


def test_sentence_window_does_not_split_on_filename_dot():
    text = "модуль docs/RELATED_WORK.md отсутствует в репозитории"
    idx = text.lower().find("отсутству")
    boundary_edges = m._sorted_boundary_edges(m._find_boundaries(text))
    start, end = m._sentence_window(text, idx, idx + len("отсутству"), boundary_edges)
    window = text[start:end]
    assert "docs/RELATED_WORK.md" in window


def test_sentence_window_splits_on_real_sentence_boundary():
    text = "First sentence ends here. RELATED_WORK does not exist in this one."
    idx = text.lower().find("does not exist")
    boundary_edges = m._sorted_boundary_edges(m._find_boundaries(text))
    start, end = m._sentence_window(text, idx, idx + len("does not exist"), boundary_edges)
    window = text[start:end]
    assert "First sentence" not in window
    assert "RELATED_WORK" in window


def test_sorted_boundary_edges_unit():
    text = "Para one ends here.\n\n- item one\n- item two does not exist."
    boundaries = m._find_boundaries(text)
    ends_sorted, starts_sorted = m._sorted_boundary_edges(boundaries)
    assert ends_sorted == sorted(ends_sorted)
    assert starts_sorted == sorted(starts_sorted)
    assert len(ends_sorted) == len(boundaries)
    assert len(starts_sorted) == len(boundaries)


# ---------------------------------------------------------------------
# a physical line break is a LINE break, not a SENTENCE break.
# ---------------------------------------------------------------------


def test_wrapped_line_joins_marker_and_token_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "The canonical form dies because gateway/requests.db\n"
        "does not exist on a subscription deployment.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "gateway/requests.db" in result.stdout


def test_same_claim_one_physical_line_still_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "The canonical form dies because gateway/requests.db "
        "does not exist on a subscription deployment.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "gateway/requests.db" in result.stdout


def test_wrapped_line_silenced_by_matching_ledger_entry(tmp_path):
    ledger_dir = tmp_path / "ledger"
    _write_ledger(ledger_dir, "sess-1", ["gateway/requests.db"])
    payload = _write_payload(
        "docs/notes.md",
        "The canonical form dies because gateway/requests.db\n"
        "does not exist on a subscription deployment.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_blank_line_still_separates_unrelated_token(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "See docs/RELATED_WORK.md for the full list.\n"
        "\n"
        "This section does not exist yet.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_two_list_items_still_separated(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "- See docs/RELATED_WORK.md for detail.\n"
        "- This entry does not exist yet.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_wrapped_russian_prose_warns(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "DECISIONS.md",
        "Файл docs/RELATED_WORK.md\nотсутствует в репозитории.",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "docs/RELATED_WORK.md" in result.stdout


def test_find_boundaries_blank_line_and_list_item():
    text = "Para one ends here.\n\n- item one\n- item two does not exist."
    boundaries = m._find_boundaries(text)
    assert any(text[s:e] == "." for s, e in boundaries)
    assert any(text[s:e].count("\n") == 2 for s, e in boundaries)
    assert any(text[s:e] == "\n" and text[e:e + 2] == "- " for s, e in boundaries)


# ---------------------------------------------------------------------
# markdown table/heading boundaries: the same boundary classes closed
# for paragraph/list above, extended to a table row (`\n` + horizontal
# whitespace + `|`) and a heading (`\n` + horizontal whitespace + `#`).
# ---------------------------------------------------------------------


def test_table_row_boundary_separates_marker_and_token(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "| RELATED_WORK | present |\n"
        "| this row does not exist | n/a |",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_heading_boundary_separates_marker_and_token(tmp_path):
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md",
        "See docs/RELATED_WORK.md for detail.\n"
        "## This section does not exist yet",
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_table_row_and_marker_same_row_still_warns(tmp_path):
    # Control: marker and token IN THE SAME table row -- must still
    # trigger (the boundary must not cut the row itself).
    ledger_dir = tmp_path / "ledger"
    payload = _write_payload(
        "docs/notes.md", "| docs/RELATED_WORK.md | does not exist |"
    )
    result = _run_hook(payload, ledger_dir=ledger_dir)
    assert result.returncode == 0
    assert "RELATED_WORK" in result.stdout


def test_find_boundaries_table_row_and_heading():
    text = "| a | b |\n| c does not exist | d |\n## Heading does not exist"
    boundaries = m._find_boundaries(text)
    assert any(text[s:e] == "\n" and text[e:e + 1] == "|" for s, e in boundaries)
    assert any(text[s:e] == "\n" and text[e:e + 2] == "##" for s, e in boundaries)
