"""Unit tests for tools/r3_integration_check.py -- ONLY against fixture
strings (git numstat output and routing-log.jsonl lines), with no real
git repository and no network/filesystem side effects (the spec: "the
script ONLY READS git and the journal" -- these tests don't exercise
that subprocess boundary, only the pure parse/search/classify
functions).

Covers the DoD: an empty window, a commit with no numstat pairs, a
journal with no critic events, broken journal JSON lines (skipped),
plus the >100-line threshold boundary (100 is small, 101 is large) and
the ts window boundary (inclusive on both sides).

Plus the anti-trail fix: "critic: skipped" is NOT counted as a critic
trail, a valid "critic:t-NNN" token form IS counted, a mixed line has
the valid token outweigh the anti-trail, and the printed notes fragment
is correctly clamped at string boundaries and sanitizes newlines.

Run: python -m pytest toolkit/tools/test_r3_integration_check.py -q
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import r3_integration_check as r3  # noqa: E402


COMMIT = r3.COMMIT_MARKER
SEP = "\x1f"


def _header(commit_hash: str, ts: str) -> str:
    return f"{COMMIT}{commit_hash}{SEP}{ts}"


def _line(obj) -> str:
    return json.dumps(obj)


# ---------------------------------------------------------------------
# parse_git_log_numstat
# ---------------------------------------------------------------------


def test_parse_empty_window_returns_empty_list():
    assert r3.parse_git_log_numstat("") == []


def test_parse_single_commit_sums_added_and_deleted():
    raw = "\n".join(
        [
            _header("aaa111", "2026-08-25T10:00:00"),
            "10\t5\ttools/x.py",
            "3\t2\ttools/y.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert len(commits) == 1
    assert commits[0]["hash"] == "aaa111"
    assert commits[0]["ts"] == "2026-08-25T10:00:00"
    assert commits[0]["lines_changed"] == 20  # 10+5+3+2


def test_parse_commit_without_numstat_pairs_is_zero_lines():
    # DoD edge: a merge commit (or an empty commit) -- a header exists,
    # no numstat lines at all. A record is still created, lines_changed=0.
    raw = "\n".join(
        [
            _header("mmm000", "2026-08-25T09:00:00"),
            "",
            _header("bbb222", "2026-08-25T11:00:00"),
            "1\t1\ttools/z.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert len(commits) == 2
    assert commits[0]["hash"] == "mmm000"
    assert commits[0]["lines_changed"] == 0
    assert commits[1]["lines_changed"] == 2


def test_parse_binary_file_numstat_contributes_zero():
    raw = "\n".join(
        [
            _header("ccc333", "2026-08-25T12:00:00"),
            "-\t-\tassets/image.png",
            "4\t1\ttools/w.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert commits[0]["lines_changed"] == 5  # a binary contributes 0, only 4+1


def test_parse_multiple_commits_preserves_order():
    raw = "\n".join(
        [
            _header("first0", "2026-08-25T08:00:00"),
            "1\t1\ta.py",
            _header("second0", "2026-08-25T09:00:00"),
            "2\t2\tb.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert [c["hash"] for c in commits] == ["first0", "second0"]


def test_parse_garbage_before_first_header_ignored():
    raw = "\n".join(
        [
            "some stray line not matching numstat format",
            _header("ddd444", "2026-08-25T13:00:00"),
            "6\t0\tc.py",
        ]
    )
    commits = r3.parse_git_log_numstat(raw)
    assert len(commits) == 1
    assert commits[0]["lines_changed"] == 6


# ---------------------------------------------------------------------
# classify_commits -- threshold >100 (boundaries 100/101) and window_start.
# ---------------------------------------------------------------------


def test_classify_threshold_boundary_at_100_is_small():
    commits = [{"hash": "h1", "ts": "2026-08-25T10:00:00", "lines_changed": 100}]
    classified = r3.classify_commits(commits)
    assert classified["large"] == []
    assert len(classified["small"]) == 1


def test_classify_threshold_boundary_at_101_is_large():
    commits = [{"hash": "h1", "ts": "2026-08-25T10:00:00", "lines_changed": 101}]
    classified = r3.classify_commits(commits)
    assert len(classified["large"]) == 1
    assert classified["small"] == []


def test_classify_window_start_is_previous_commit_ts_any_size():
    # The neighboring commit for the lower window bound is ANY commit of
    # the list (not only a large one) -- a builder design decision,
    # documented in classify_commits's own docstring.
    commits = [
        {"hash": "small1", "ts": "2026-08-25T08:00:00", "lines_changed": 10},
        {"hash": "large1", "ts": "2026-08-25T09:00:00", "lines_changed": 200},
    ]
    classified = r3.classify_commits(commits)
    assert len(classified["large"]) == 1
    assert classified["large"][0]["window_start"] == "2026-08-25T08:00:00"
    assert classified["large"][0]["window_end"] == "2026-08-25T09:00:00"


def test_classify_first_commit_has_no_window_start():
    commits = [{"hash": "large1", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    classified = r3.classify_commits(commits)
    assert classified["large"][0]["window_start"] is None


# ---------------------------------------------------------------------
# find_critic_trail
# ---------------------------------------------------------------------


def test_find_critic_trail_empty_journal_no_critic_events():
    # DoD edge: a journal with no critic events -- an empty result, not
    # an error.
    lines = [_line({"ts": "2026-08-25T10:00:00", "event": "accepted", "agent": "builder"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_matches_delegated_critic():
    lines = [
        _line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"})
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_matches_accepted_basis_critic():
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "basis": "critic",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_matches_notes_substring_critic_colon():
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: ACCEPT, zero findings",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_skipped_form_is_anti_trail_not_a_match():
    # "critic: skipped" is a record of the critic's ABSENCE, not a
    # trail. A live precedent (a 900-line commit with exactly this notes
    # line) used to print as FOUND before this fix -- a regression pin.
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: skipped -- reserve concession",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_skipped_form_no_space_is_also_anti_trail():
    # Case and the absence of a space after ":" must not bypass the
    # anti-trail ("critic:skipped", "Critic: SKIPPED").
    lines = [
        _line({"ts": "2026-08-25T10:00:00", "event": "accepted", "agent": "builder", "notes": "critic:skipped"}),
        _line({"ts": "2026-08-25T10:00:01", "event": "accepted", "agent": "builder", "notes": "Critic: SKIPPED, reason"}),
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_s5_token_form_is_a_match():
    # A valid "critic:t-NNN" token form still counts as a trail as
    # before (the anti-trail fix does not touch it).
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "closed by reference critic:t-593 on the verdict",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1
    assert result[0]["_notes_fragment"] is not None
    assert "critic:t-593" in result[0]["_notes_fragment"]


def test_find_critic_trail_mixed_skip_and_valid_token_is_a_match():
    # A mixed line -- an anti-trail PLUS a valid token later in the text
    # -- the valid token outweighs (an explicit requirement).
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: skipped on the first pass, later closed critic:t-593",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1
    assert "critic:t-593" in result[0]["_notes_fragment"]


def test_find_critic_trail_notes_fragment_none_for_non_notes_match():
    # A match via delegated/basis (not via notes) must carry a None
    # fragment -- the report builder must not print an empty fragment
    # line for these forms.
    lines = [_line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result[0]["_notes_fragment"] is None


def test_find_critic_notes_match_fragment_trimmed_at_string_start():
    # The +-40 boundary: a match right at the start of notes -- the
    # fragment doesn't run past the string's edge (no ValueError/negative
    # index, it's simply clamped).
    notes = "critic:t-1 " + ("x" * 60)
    matched, fragment = r3._find_critic_notes_match(notes)
    assert matched is True
    assert fragment.startswith("critic:t-1")


def test_find_critic_notes_match_fragment_trimmed_at_string_end():
    notes = ("y" * 60) + "critic:t-1"
    matched, fragment = r3._find_critic_notes_match(notes)
    assert matched is True
    assert fragment.endswith("critic:t-1")


def test_find_critic_notes_match_sanitizes_newlines_in_fragment():
    notes = "line one\ncritic:t-1\r\nline two"
    matched, fragment = r3._find_critic_notes_match(notes)
    assert matched is True
    assert "\n" not in fragment
    assert "\r" not in fragment


def test_find_critic_notes_match_no_occurrence_returns_false_none():
    matched, fragment = r3._find_critic_notes_match("no mention at all")
    assert matched is False
    assert fragment is None


def test_find_critic_trail_delegated_critic_outside_event_type_not_matched():
    # basis=critic on a NON-accepted event must not match (the condition
    # is tied to event=='accepted').
    lines = [
        _line(
            {
                "ts": "2026-08-25T10:00:00",
                "event": "delegated",
                "agent": "builder",
                "basis": "critic",
            }
        )
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_malformed_json_line_is_skipped():
    # DoD edge: broken journal JSON lines -- skipped, not an exception.
    lines = [
        "{not valid json",
        _line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"}),
    ]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1  # the second line parsed, the first silently skipped


def test_find_critic_trail_blank_lines_are_skipped():
    lines = ["", "   ", _line({"ts": "2026-08-25T10:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_event_missing_ts_is_skipped():
    lines = [_line({"event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_window_boundary_inclusive_start():
    # AT the boundary -- a ts exactly equal to window_start counts as
    # INSIDE the window (an inclusive boundary).
    lines = [_line({"ts": "2026-08-25T09:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_window_boundary_inclusive_end():
    lines = [_line({"ts": "2026-08-25T11:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert len(result) == 1


def test_find_critic_trail_before_window_start_excluded():
    # BEYOND the boundary -- one second earlier than the window -- does
    # NOT count (a boundary test alongside its AT-boundary sibling, rule 6a).
    lines = [_line({"ts": "2026-08-25T08:59:59", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_after_window_end_excluded():
    lines = [_line({"ts": "2026-08-25T11:00:01", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, "2026-08-25T09:00:00", "2026-08-25T11:00:00")
    assert result == []


def test_find_critic_trail_unbounded_window_start_none_accepts_any_earlier_ts():
    # window_start=None -- the lower bound is unbounded (the edge: "the
    # window's earliest commit, no previous commit in the repo").
    lines = [_line({"ts": "2000-01-01T00:00:00", "event": "delegated", "agent": "critic"})]
    result = r3.find_critic_trail(lines, None, "2026-08-25T11:00:00")
    assert len(result) == 1


# ---------------------------------------------------------------------
# build_report -- the end-to-end output shape (candidate / found / small).
# ---------------------------------------------------------------------


def test_build_report_prints_candidate_label_when_no_trail_found():
    commits = [{"hash": "large1longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    report = r3.build_report("24 hours ago", commits, [])
    assert "CANDIDATE" in report
    assert "the calibration check decides" in report


def test_build_report_prints_found_label_when_trail_present():
    commits = [{"hash": "large1longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    journal_lines = [_line({"ts": "2026-08-25T08:30:00", "event": "delegated", "agent": "critic"})]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T08:00:00")
    assert "FOUND" in report
    assert "CANDIDATE" not in report


def test_build_report_skip_only_notes_fixture_is_candidate():
    # A regression fixture, taken literally from a real incident: a
    # single accepted line with "critic: skipped" in the window + a
    # large (900-line-class) commit -> CANDIDATE, not FOUND.
    commits = [{"hash": "t593likehash", "ts": "2026-08-25T13:00:00", "lines_changed": 900}]
    journal_lines = [
        _line(
            {
                "ts": "2026-08-25T12:47:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "critic: skipped -- reserve concession",
            }
        )
    ]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T12:00:00")
    assert "CANDIDATE" in report
    assert "critic trail FOUND" not in report
    assert "critic trail NOT FOUND" in report


def test_build_report_prints_notes_fragment_for_notes_based_match():
    # The printed trail carries the notes fragment the match fired on.
    commits = [{"hash": "large2longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    journal_lines = [
        _line(
            {
                "ts": "2026-08-25T08:30:00",
                "event": "accepted",
                "agent": "builder",
                "notes": "closed by reference critic:t-593 on the verdict",
            }
        )
    ]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T08:00:00")
    assert "FOUND" in report
    assert "notes fragment" in report
    assert "critic:t-593" in report


def test_build_report_no_fragment_line_for_delegated_critic_match():
    # A delegated/basis match carries no fragment -- the "notes
    # fragment" line must not appear in the report for that case.
    commits = [{"hash": "large3longhash", "ts": "2026-08-25T09:00:00", "lines_changed": 200}]
    journal_lines = [_line({"ts": "2026-08-25T08:30:00", "event": "delegated", "agent": "critic"})]
    report = r3.build_report("24 hours ago", commits, journal_lines, boundary_ts="2026-08-25T08:00:00")
    assert "FOUND" in report
    assert "notes fragment" not in report


def test_build_report_counts_small_commits_for_cumulative_review():
    commits = [
        {"hash": "s1", "ts": "2026-08-25T08:00:00", "lines_changed": 10},
        {"hash": "s2", "ts": "2026-08-25T08:30:00", "lines_changed": 40},
    ]
    report = r3.build_report("24 hours ago", commits, [])
    assert "SMALL COMMITS" in report
    assert "cumulative-review" in report


def test_build_report_exit_semantics_line_present():
    report = r3.build_report("24 hours ago", [], [])
    assert "exit: 0" in report


def test_build_report_empty_journal_and_empty_window_honest_string_no_error():
    # DoD edge: an empty journal AND an empty commit window -> a
    # coherent, honest report (zero commits, no crash), not an
    # exception -- the informer must stay quiet-but-truthful on a
    # genuinely empty world.
    report = r3.build_report("24 hours ago", [], [])
    assert "commits in window: 0" in report
    assert "no large commits in this window" in report
    assert "SMALL COMMITS in this window (<= 100 lines): 0" in report
    assert "exit: 0" in report


def test_main_exits_zero_even_on_internal_exception(monkeypatch):
    # An informer, not a gate -- ANY internal error (here: git is
    # unavailable/raises) must not raise the exit code.
    def _boom(_since):
        raise RuntimeError("git unavailable (simulated)")

    monkeypatch.setattr(r3, "fetch_window_commits", _boom)
    exit_code = r3.main(["--since", "24 hours ago"])
    assert exit_code == 0
