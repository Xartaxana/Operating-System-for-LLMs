"""Battery for tools/judge_calib_sanitize.py (spec block П3: sanitized
live-probe input for the R13 subscription-judge role, gateway/
judge_calibration.json's key fields stripped before the Lead hands the
material to the judge).

Covers: key-field stripping (verdict/rationale/judge AND source_model/
target_model dropped, see the module's own docstring for why the latter
two are dropped though the spec's literal key-field list names only the
first three), kept-field fidelity, pair_index assignment and order
preservation, the "pair missing verdict" edge (does not crash, is
counted), the "non-dict pair" edge (skipped from output, still counted),
zero pairs (valid "[]" output, exit 0, non-empty stderr counter), the CLI
contract (default path against the real repo file, explicit path
argument, usage error, missing/invalid/non-array source file), and the
STDOUT ENCODING fix (t-354 blocker 1): output must be correct UTF-8
regardless of whether stdout is a pipe (subprocess capture, already
covered by every _run_cli()-based test above), a redirected file, or a
narrow-codepage console (cp1251 reproduced directly via
PYTHONIOENCODING, the exact failure mode reported: U+2192 in
gateway/judge_calibration.json pair 8's target_response used to raise
UnicodeEncodeError before the sys.stdout.buffer fix).

Run: python -m pytest tools/test_judge_calib_sanitize.py -q
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import judge_calib_sanitize as jcs
from wallclock_guard import WALLCLOCK_HARNESS_TIMEOUT

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "tools" / "judge_calib_sanitize.py"
REAL_CALIBRATION_PATH = REPO_ROOT / "gateway" / "judge_calibration.json"


def _run_subprocess_guarded(args, **kwargs):
    # F-60 (класс A), общий "хелпер" -- и _run_cli, и inline-сайты этого
    # файла, которым нужна форма stdout=<file> (несовместимая с
    # capture_output=True в _run_cli), проходят через эту функцию, так
    # что все они ловят TimeoutExpired одинаково (Ф8: обёртка на
    # хелперах, не на каждом сайте).
    kwargs.setdefault("timeout", WALLCLOCK_HARNESS_TIMEOUT)
    try:
        return subprocess.run(args, **kwargs)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"judge_calib_sanitize CLI exceeded WALLCLOCK_HARNESS_TIMEOUT="
            f"{kwargs['timeout']}s -- сторож стенных часов: проверь "
            "загрузку машины прежде, чем считать это дефектом (F-60)"
        )


def _run_cli(args, timeout=WALLCLOCK_HARNESS_TIMEOUT, env=None):
    return _run_subprocess_guarded(
        [sys.executable, str(SCRIPT_PATH)] + args,
        cwd=str(REPO_ROOT),
        capture_output=True,
        timeout=timeout,
        env=env,
    )


def _pair(**overrides):
    base = {
        "prompt": "sample prompt",
        "source_model": "lead-gemini",
        "source_response": "sample source response",
        "target_model": "intern",
        "target_response": "sample target response",
        "category": "coding",
        "judge": "claude-fable-5 (manual)",
        "verdict": "equivalent",
        "rationale": "sample rationale",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# sanitize_pairs(): key stripping, kept-field fidelity
# ---------------------------------------------------------------------------


def test_sanitize_strips_all_three_named_key_fields():
    sanitized, missing = sanitize_and_check([_pair()])
    assert missing == 0
    assert len(sanitized) == 1
    for key in ("verdict", "rationale", "judge"):
        assert key not in sanitized[0]


def sanitize_and_check(pairs):
    return jcs.sanitize_pairs(pairs)


def test_sanitize_also_drops_model_name_fields():
    # spec's explicit "остаются" enumeration lists only prompt/
    # source_response/target_response/category/pair_index -- source_model
    # and target_model are NOT in that list, matching JUDGE_SYSTEM_PROMPT's
    # own "never model names" anonymization principle (module docstring).
    sanitized, _ = sanitize_and_check([_pair()])
    assert "source_model" not in sanitized[0]
    assert "target_model" not in sanitized[0]


def test_sanitize_keeps_exactly_the_five_named_fields():
    sanitized, _ = sanitize_and_check([_pair()])
    assert set(sanitized[0].keys()) == {
        "pair_index", "prompt", "source_response", "target_response", "category",
    }


def test_sanitize_kept_field_values_unchanged():
    pair = _pair(prompt="EXACT PROMPT TEXT", category="summarization")
    sanitized, _ = sanitize_and_check([pair])
    assert sanitized[0]["prompt"] == "EXACT PROMPT TEXT"
    assert sanitized[0]["category"] == "summarization"
    assert sanitized[0]["source_response"] == pair["source_response"]
    assert sanitized[0]["target_response"] == pair["target_response"]


# ---------------------------------------------------------------------------
# pair_index / order preservation
# ---------------------------------------------------------------------------


def test_pair_index_is_one_based_and_matches_source_order():
    pairs = [_pair(prompt="first"), _pair(prompt="second"), _pair(prompt="third")]
    sanitized, _ = sanitize_and_check(pairs)
    assert [p["pair_index"] for p in sanitized] == [1, 2, 3]
    assert [p["prompt"] for p in sanitized] == ["first", "second", "third"]


def test_order_never_resorted_even_if_category_would_sort_differently():
    pairs = [
        _pair(prompt="z-prompt", category="zzz"),
        _pair(prompt="a-prompt", category="aaa"),
    ]
    sanitized, _ = sanitize_and_check(pairs)
    assert [p["prompt"] for p in sanitized] == ["z-prompt", "a-prompt"]
    assert [p["pair_index"] for p in sanitized] == [1, 2]


# ---------------------------------------------------------------------------
# edge: pair missing "verdict" -- does not crash, is counted
# ---------------------------------------------------------------------------


def test_pair_missing_verdict_field_does_not_crash_and_is_counted():
    incomplete = _pair(prompt="incomplete pair")
    del incomplete["verdict"]
    pairs = [_pair(prompt="complete pair"), incomplete]
    sanitized, missing = sanitize_and_check(pairs)
    assert missing == 1
    assert len(sanitized) == 2
    # the incomplete pair is still sanitized (kept fields survive)
    assert sanitized[1]["prompt"] == "incomplete pair"
    assert "verdict" not in sanitized[1]


def test_all_pairs_missing_verdict_counts_all():
    p1 = _pair(prompt="p1")
    p2 = _pair(prompt="p2")
    del p1["verdict"]
    del p2["verdict"]
    sanitized, missing = sanitize_and_check([p1, p2])
    assert missing == 2
    assert len(sanitized) == 2


# ---------------------------------------------------------------------------
# edge: a pair that is not a dict at all -- skipped from output, still
# counted as missing (it cannot have had a "verdict" key)
# ---------------------------------------------------------------------------


def test_non_dict_pair_skipped_from_output_but_counted():
    sanitized, missing = sanitize_and_check([_pair(prompt="ok"), "not-a-dict", 42])
    assert len(sanitized) == 1
    assert sanitized[0]["prompt"] == "ok"
    assert missing == 2


# ---------------------------------------------------------------------------
# edge: zero pairs -- valid "[]", not an error
# ---------------------------------------------------------------------------


def test_zero_pairs_returns_empty_list_and_zero_missing():
    sanitized, missing = sanitize_and_check([])
    assert sanitized == []
    assert missing == 0


# ---------------------------------------------------------------------------
# load_pairs(): file-level errors
# ---------------------------------------------------------------------------


def test_load_pairs_missing_file_fails_closed(tmp_path):
    pairs, err = jcs.load_pairs(str(tmp_path / "nope.json"))
    assert pairs is None
    assert err is not None


def test_load_pairs_invalid_json_fails_closed(tmp_path):
    p = tmp_path / "bad.json"
    p.write_bytes(b"{not valid json,,,")
    pairs, err = jcs.load_pairs(str(p))
    assert pairs is None
    assert "not valid JSON" in err


def test_load_pairs_non_array_root_fails_closed(tmp_path):
    p = tmp_path / "obj.json"
    p.write_bytes(json.dumps({"not": "an array"}).encode("utf-8"))
    pairs, err = jcs.load_pairs(str(p))
    assert pairs is None
    assert "not a JSON array" in err


def test_load_pairs_non_utf8_fails_closed(tmp_path):
    p = tmp_path / "bin.json"
    p.write_bytes(bytes([0xFF, 0xFE, 0x80, 0x81]) * 5)
    pairs, err = jcs.load_pairs(str(p))
    assert pairs is None
    assert "not valid UTF-8" in err


def test_load_pairs_valid_array_ok(tmp_path):
    p = tmp_path / "ok.json"
    p.write_bytes(json.dumps([_pair()]).encode("utf-8"))
    pairs, err = jcs.load_pairs(str(p))
    assert err is None
    assert len(pairs) == 1


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------


def test_cli_zero_pairs_prints_empty_array_exit_0(tmp_path):
    p = tmp_path / "empty.json"
    p.write_bytes(b"[]")
    result = _run_cli([str(p)])
    assert result.returncode == 0
    assert json.loads(result.stdout.decode("utf-8")) == []
    assert b"sanitized 0 pair" in result.stderr


def test_cli_explicit_path_sanitizes_fixture(tmp_path):
    p = tmp_path / "fixture.json"
    p.write_bytes(json.dumps([_pair(prompt="fixture prompt")]).encode("utf-8"))
    result = _run_cli([str(p)])
    assert result.returncode == 0
    out = json.loads(result.stdout.decode("utf-8"))
    assert len(out) == 1
    assert out[0]["prompt"] == "fixture prompt"
    assert "verdict" not in out[0]
    assert b"sanitized 1 pair" in result.stderr


def test_cli_missing_file_exit_1(tmp_path):
    result = _run_cli([str(tmp_path / "nope.json")])
    assert result.returncode == 1
    assert b"JUDGE CALIB SANITIZE FAILED" in result.stderr
    assert result.stdout == b""


def test_cli_invalid_json_exit_1(tmp_path):
    p = tmp_path / "bad.json"
    p.write_bytes(b"{not valid json,,,")
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert result.stdout == b""


def test_cli_non_array_root_exit_1(tmp_path):
    p = tmp_path / "obj.json"
    p.write_bytes(json.dumps({"nope": []}).encode("utf-8"))
    result = _run_cli([str(p)])
    assert result.returncode == 1
    assert result.stdout == b""


def test_cli_too_many_arguments_exit_2():
    result = _run_cli(["a", "b"])
    assert result.returncode == 2
    assert b"usage" in result.stderr


def test_cli_default_path_runs_against_real_repo_file():
    result = _run_cli([])
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    out = json.loads(result.stdout.decode("utf-8"))
    assert isinstance(out, list)
    assert len(out) == 13  # gateway/judge_calibration.json, D-0031 set size
    # negative claim (no key fields) valid only with a positive control
    # (command hygiene p.6): the same check finds "prompt" if the pipe
    # itself works.
    dumped = json.dumps(out)
    assert "prompt" in dumped  # positive control: the pipe finds a known field
    for field in ("verdict", "rationale", "judge"):
        assert '"%s"' % field not in dumped
    assert b"sanitized 13 pair" in result.stderr


def test_cli_default_path_pair_index_matches_real_file_order():
    with open(REAL_CALIBRATION_PATH, "r", encoding="utf-8") as fh:
        real_pairs = json.load(fh)
    result = _run_cli([])
    assert result.returncode == 0
    out = json.loads(result.stdout.decode("utf-8"))
    assert [p["pair_index"] for p in out] == list(range(1, len(real_pairs) + 1))
    assert [p["prompt"] for p in out] == [rp["prompt"] for rp in real_pairs]


# ---------------------------------------------------------------------------
# STDOUT ENCODING (t-354 blocker 1): output must be correct UTF-8 whether
# stdout is a pipe, a redirected file, or a narrow-codepage console -- see
# module docstring "STDOUT ENCODING" in judge_calib_sanitize.py itself.
# ---------------------------------------------------------------------------


def test_real_calibration_set_contains_the_reported_non_ascii_character():
    # fixation: pair 8's target_response carries U+2192 (RIGHTWARDS ARROW),
    # the exact character the coordinator's cp1251-console crash named.
    # If this ever stops being true the regression test below would pass
    # for the wrong reason (nothing non-ASCII left to trip on) -- pin the
    # premise explicitly.
    with open(REAL_CALIBRATION_PATH, "r", encoding="utf-8") as fh:
        real_pairs = json.load(fh)
    assert any(
        "→" in (p.get("target_response") or "") for p in real_pairs
    )


def test_cli_survives_narrow_codepage_console_environment():
    # regression test for the exact reported failure: PYTHONIOENCODING set
    # to a narrow codepage (cp1251, the machine's own default) used to
    # raise UnicodeEncodeError on U+2192 via a plain sys.stdout.write();
    # the sys.stdout.buffer byte-write path must be immune to this
    # environment variable entirely (module docstring: "no environment
    # precondition").
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1251"
    result = _run_cli([], env=env)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    out = json.loads(result.stdout.decode("utf-8"))
    assert len(out) == 13
    dumped = json.dumps(out, ensure_ascii=False)
    assert "→" in dumped  # the character that used to crash survives intact


def test_cli_stdout_redirected_to_file_is_byte_identical_utf8(tmp_path):
    # a different stdout target than a pipe: an actual file object, no
    # subprocess pipe buffering involved on the read side.
    out_path = tmp_path / "sanitized_out.json"
    with open(out_path, "wb") as out_fh:
        result = _run_subprocess_guarded(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=str(REPO_ROOT),
            stdout=out_fh,
            stderr=subprocess.PIPE,
            timeout=WALLCLOCK_HARNESS_TIMEOUT,
        )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    file_bytes = out_path.read_bytes()
    out = json.loads(file_bytes.decode("utf-8"))
    assert len(out) == 13
    dumped = json.dumps(out, ensure_ascii=False)
    assert "→" in dumped


def test_cli_pipe_file_and_narrow_console_all_agree_byte_for_byte(tmp_path):
    # the three redirection targets named in the spec's edge clause must
    # produce IDENTICAL bytes -- pipe (capture_output), file, and a
    # narrow-codepage console environment (env var only changes the
    # console's notional encoding, not the actual OS-level pipe/file
    # transport in a subprocess test, but it exercises the code path that
    # would differ if _write_stdout_utf8() ever regressed to text-mode
    # writes keyed off sys.stdout.encoding).
    pipe_result = _run_cli([])
    assert pipe_result.returncode == 0

    out_path = tmp_path / "out.json"
    with open(out_path, "wb") as out_fh:
        file_result = _run_subprocess_guarded(
            [sys.executable, str(SCRIPT_PATH)],
            cwd=str(REPO_ROOT), stdout=out_fh, stderr=subprocess.PIPE,
            timeout=WALLCLOCK_HARNESS_TIMEOUT,
        )
    assert file_result.returncode == 0

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1251"
    console_result = _run_cli([], env=env)
    assert console_result.returncode == 0

    assert pipe_result.stdout == out_path.read_bytes() == console_result.stdout
